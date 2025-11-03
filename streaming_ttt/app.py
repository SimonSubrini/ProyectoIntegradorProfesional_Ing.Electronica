import streamlit as st
import matplotlib.pyplot as plt
import altair as alt
import pandas as pd
import time
import os
import json
from io import StringIO
from datetime import datetime
from sensor import SpiSensor
from report_generator import generar_reporte_pdf
from histograms import generar_histogramas

# ==============================
# CARGA DE CONFIGURACIONES
# ==============================
THRESHOLDS_PATH = "thresholds.json"
with open(THRESHOLDS_PATH, "r") as f:
    THRESHOLDS = json.load(f)

# ==============================
# CONFIGURACIÓN INICIAL
# ==============================
st.set_page_config(page_title="Monitor de desplazamiento", layout="wide")
st.title("Monitor de desplazamiento")

# ==== VARIABLES DE SESIÓN ====
defaults = {
    "medicion_activa": False,
    "datos": pd.DataFrame(columns=["timestamp", "dx_mm", "dy_mm", "x_mm", "y_mm", "desp_total"]),
    "factor": 6.46,
    "x_acum": 0.0,
    "y_acum": 0.0,
    "sensor_value": 0.0,
    "sensor_inicializado": False,
    "sensor": None,
    "ultima_lectura": (0.0, 0.0, 0.0, 0.0, 0.0),
    "pozo_df": None,
    "total_conexiones": 0,
    "conexiones_realizadas": 0,
    "flag_terminado":False,
    "resultados":pd.DataFrame(columns=["id_conexion", "diametro", "grado_acero", "umbral_min", "umbral_max", "desplazamiento", "comentario"])
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==== CONFIGURACIÓN DE DIRECTORIOS ====
HIST_DIR = "data/histogramas"
PDF_DIR = "data/pdf"
os.makedirs(HIST_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)


# ==============================
# FUNCIONES
# ==============================
def inicializar_sensor():
    try:
        sensor = SpiSensor()
        sensor.initialize(timeout=10)
        st.session_state.sensor = sensor
        st.session_state.sensor_inicializado = True
        _,_ = sensor.read_sensor()
    except Exception as e:
        st.error(f"Error al inicializar el sensor: {e}")
        st.session_state.sensor_inicializado = False


def leer_sensor():
    try:
        sensor = st.session_state.sensor
        if sensor is None:
            return

        dx_raw, dy_raw = sensor.read_sensor(timeout=0.2)
        factor = st.session_state.factor

        dx_mm = dx_raw * factor / 1000.0 if dx_raw else 0.0
        dy_mm = dy_raw * factor / 1000.0 if dy_raw else 0.0

        st.session_state.x_acum += dx_mm
        st.session_state.y_acum += dy_mm

        desp_total = round((st.session_state.x_acum**2 + st.session_state.y_acum**2) ** 0.5, 3)
        st.session_state.sensor_value = desp_total
        st.session_state.ultima_lectura = (dx_mm, dy_mm, st.session_state.x_acum, st.session_state.y_acum, desp_total)

        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        row = pd.DataFrame([[ts, dx_mm, dy_mm, st.session_state.x_acum, st.session_state.y_acum, desp_total]],
                           columns=["timestamp", "dx_mm", "dy_mm", "x_mm", "y_mm", "desp_total"])
        if len(st.session_state.datos)>0:
            st.session_state.datos = pd.concat([st.session_state.datos, row], ignore_index=True)
        else:
            st.session_state.datos = row

    except Exception as e:
        st.error(f"Error durante la lectura: {e}")
        st.session_state.medicion_activa = False

def actualizar_umbral_actual():
    idx = st.session_state.conexiones_realizadas
    if "df_expandido" not in st.session_state or st.session_state.df_expandido.empty:
        return
    
    # Asegurar que el índice no supere el total
    if idx >= len(st.session_state.df_expandido):
        return
    
    fila = st.session_state.df_expandido.iloc[idx]
    grado = str(fila["Grado de acero"]).strip()
    diametro = str(fila["Diametro"]).strip()

    try:
        umbrales = THRESHOLDS[grado][diametro]
        st.session_state.umbral_min = umbrales["min"]
        st.session_state.umbral_max = umbrales["max"]
    except KeyError:
        st.session_state.umbral_min = None
        st.session_state.umbral_max = None
        st.warning(f"No hay umbrales definidos para {grado} - {diametro}")

def registrar_resultado(id_conexion, diametro, grado_acero, umbral_min, umbral_max, desplazamiento, comentario):
    row = {
        "id_conexion": id_conexion+1,
        "diametro": diametro,
        "grado_acero": grado_acero,
        "umbral_min": umbral_min,
        "umbral_max": umbral_max,
        "desplazamiento": desplazamiento,
        "comentario": comentario
    }
    if len(row)>0:
        if len(st.session_state.resultados)>0:
            st.session_state.resultados = pd.concat(
                [st.session_state.resultados, pd.DataFrame([row])],
                ignore_index=True,
            )
        else:
            st.session_state.resultados = pd.DataFrame([row])

# ==============================
# INTERFAZ DE USUARIO
# ==============================
col_controles, col_grafico, col_metricas = st.columns([1, 3, 1])

# ---- Columna 1: Controles, calibración y descarga ----
with col_controles:
    st.subheader("Diseño de pozo")

    # === Subir archivo CSV ===
    uploaded_file = st.file_uploader("Subir diseño de pozo (.csv)", type=["csv"])

    if uploaded_file is not None:
        pozo_df = pd.read_csv(uploaded_file)
        if not {"Cantidad", "Diametro", "Grado de acero"}.issubset(pozo_df.columns):
            st.error("El archivo CSV debe contener las columnas: Cantidad, Diámetro, Grado de acero.")
        else:
            st.session_state.pozo_df = pozo_df
            df_expandido = pozo_df.loc[pozo_df.index.repeat(pozo_df["Cantidad"])].reset_index(drop=True)
            st.session_state.df_expandido = df_expandido
            st.session_state.total_conexiones = pozo_df["Cantidad"].sum()
            st.success(f"Diseño cargado correctamente, ({st.session_state.total_conexiones} conexiones por realizar).")
            actualizar_umbral_actual()
    else:
        st.info("Esperando archivo de diseño de pozo...")

    # Deshabilitar botones si no hay CSV cargado
    botones_habilitados = st.session_state.pozo_df is not None

    st.divider()
    st.subheader("Control de medición")

    if st.button("🔌 Inicializar sensor", use_container_width=True, disabled=not botones_habilitados):
        inicializar_sensor()

    subcol1, subcol2 = st.columns(2)
    with subcol1:
        if st.button("▶️ Play", use_container_width=True, disabled=not botones_habilitados or not st.session_state.sensor_inicializado or st.session_state.medicion_activa):
            if not st.session_state.sensor_inicializado:
                st.warning("Inicializá el sensor antes de iniciar.")
            else:
                st.session_state.medicion_activa = True
    with subcol2:
        if st.button("⏸ Pausa", use_container_width=True, disabled=not botones_habilitados or not st.session_state.sensor_inicializado or not st.session_state.medicion_activa):
            st.session_state.medicion_activa = False

    st.divider()

    st.subheader("Calibración")
    factor_input = st.number_input(
        "Factor de calibración (mm por unidad)",
        min_value=0.001, max_value=100.0,
        value=st.session_state.factor,
        step=0.001,
        disabled=not botones_habilitados
    )
    st.session_state.factor = factor_input


# ---- Columna 2: Gráficos ----
with col_grafico:
    st.subheader("Gráfico de desplazamiento de conexiones")
    if st.session_state.datos.empty:
        df_plot = pd.DataFrame({"timestamp": [0], "desp_total": [0.0]})
    else:
        df_plot = st.session_state.datos[["timestamp", "desp_total"]].tail(100)

    base_chart = (
        alt.Chart(df_plot)
        .mark_line()
        .encode(
            x=alt.X("timestamp", title="Tiempo"),
            y=alt.Y("desp_total", title="Desplazamiento [mm]"),
            tooltip=["timestamp", "desp_total"]
        )
    )
    if st.session_state.get("umbral_min") is not None:
        min_line = alt.Chart(pd.DataFrame({"y": [st.session_state.umbral_min]})).mark_rule(color="red", strokeDash=[4, 2]).encode(y="y")
        max_line = alt.Chart(pd.DataFrame({"y": [st.session_state.umbral_max]})).mark_rule(color="green", strokeDash=[4, 2]).encode(y="y")
        chart = (base_chart + min_line + max_line).properties(width="container", height=400)
    else:
        chart = base_chart.properties(width="container", height=400)

    st.altair_chart(chart, use_container_width=True)

    subcol1, subcol2 = st.columns(2)
    with subcol1:    
        if st.button("🔄 Repetir conexión", use_container_width=True, disabled=not botones_habilitados or not st.session_state.sensor_inicializado or st.session_state.flag_terminado or not st.session_state.medicion_activa):
            idx = st.session_state.conexiones_realizadas
            fila = st.session_state.df_expandido.iloc[idx]
            
            grado_acero = str(fila["Grado de acero"]).strip()
            diametro = str(fila["Diametro"]).strip()
            umbral_min = st.session_state.umbral_min
            umbral_max = st.session_state.umbral_max
            desplazamiento = st.session_state.sensor_value 
            comentario = "NO OK - reassembly"

            registrar_resultado(idx, diametro, grado_acero, umbral_min, umbral_max, desplazamiento, comentario)
        
            st.session_state.x_acum = 0.0
            st.session_state.y_acum = 0.0
            
            if st.session_state.conexiones_realizadas==st.session_state.total_conexiones:
                st.session_state.flag_terminado=False
                st.session_state.medicion_activa = True
    with subcol2:
        if st.button("➡️ Siguiente conexión", use_container_width=True, disabled=not botones_habilitados or not st.session_state.sensor_inicializado or st.session_state.flag_terminado or not st.session_state.medicion_activa):
            idx = st.session_state.conexiones_realizadas
            fila = st.session_state.df_expandido.iloc[idx]
            
            grado_acero = str(fila["Grado de acero"]).strip()
            diametro = str(fila["Diametro"]).strip()
            umbral_min = st.session_state.umbral_min
            umbral_max = st.session_state.umbral_max
            desplazamiento = st.session_state.sensor_value 
            comentario = "OK" if umbral_min <= desplazamiento <= umbral_max else "NO OK"

            registrar_resultado(idx, diametro, grado_acero, umbral_min, umbral_max, desplazamiento, comentario)
        
            st.session_state.x_acum = 0.0
            st.session_state.y_acum = 0.0
            st.session_state.conexiones_realizadas += 1
            if st.session_state.conexiones_realizadas==st.session_state.total_conexiones:
                st.session_state.flag_terminado=True
                st.session_state.medicion_activa = False
            actualizar_umbral_actual()

    st.divider()

    st.subheader("Descarga de datos")
    subcol1, subcol2, subcol3 = st.columns(3)

    subcol1, subcol2, subcol3 = st.columns(3)

    # --- CSV RAW ---
    with subcol1:
        st.markdown("**CSV RAW**")
        if not st.session_state.datos.empty and botones_habilitados:
            csv_bytes = st.session_state.datos.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar CSV",
                data=csv_bytes,
                file_name=f"raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("No hay datos para descargar.")

    # --- CSV Conexiones ---
    with subcol2:
        st.markdown("**CSV Conexiones**")
        if not st.session_state.resultados.empty and botones_habilitados:
            csv_bytes = st.session_state.resultados.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar CSV",
                data=csv_bytes,
                file_name=f"conexiones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("No hay datos para descargar.")


    # --- PDF Informe ---
    with subcol3:
        st.markdown("**Informe PDF**")

        # Botón habilitado solo si hay resultados
        pdf_btn_disabled = not botones_habilitados or st.session_state.resultados.empty

        # Estado del formulario (muestra/oculta)
        if "mostrar_form_pdf" not in st.session_state:
            st.session_state.mostrar_form_pdf = False

        if st.button("Generar PDF", use_container_width=True, disabled=pdf_btn_disabled):
            st.session_state.mostrar_form_pdf = not st.session_state.mostrar_form_pdf

    if st.session_state.mostrar_form_pdf:
        with st.expander("Datos del informe (cabecera)", expanded=True):
            with st.form("form_cabecera_pdf"):
                st.write("Completá los datos que irán en el encabezado del informe.")

                col1, col2 = st.columns(2)
                with col1:
                    fecha = st.text_input("Fecha", value=datetime.now().strftime("%d/%m/%Y"))
                    cliente = st.text_input("Cliente", value="")
                    yacimiento = st.text_input("Yacimiento", value="")
                    equipo = st.text_input("Equipo", value="")
                    responsable_tenaris = st.text_input("Resp. Tenaris (FISE)", value="")
                with col2:
                    numero_parte = st.text_input("Número de parte", value="")
                    responsable_cliente = st.text_input("Responsable cliente", value="")
                    pozo = st.text_input("Pozo", value="")
                    motivo = st.text_input("Motivo de intervención", value="")
                    unidad_ligera = st.text_input("Unidad liviana (patente)", value="")

                enviar = st.form_submit_button("Generar y exportar PDF")

            if enviar:
                # === Construcción de resumen ===
                total = int(len(st.session_state.resultados))
                ok = int((st.session_state.resultados["comentario"] == "OK").sum())
                nok = int((st.session_state.resultados["comentario"] == "NO OK").sum())
                nok_r = total - ok - nok

                hist_dir = HIST_DIR
                os.makedirs(hist_dir, exist_ok=True)

                with st.spinner("Generando histogramas..."):
                    rutas_histo = generar_histogramas(st.session_state.resultados, output_dir=hist_dir)


                datos = {
                    "cabecera": {
                        "Numero_de_parte": numero_parte,
                        "Fecha": fecha,
                        "Nombre_cliente": cliente,
                        "Nombre_persona_responsable": responsable_cliente,
                        "Nombre_yacimiento": yacimiento,
                        "Nombre_equipo": equipo,
                        "Nombre_pozo": pozo,
                        "Motivo_intervención": motivo,
                        "Nombre_de_FISE": responsable_tenaris,
                        "Patente_vehículo": unidad_ligera,
                    },
                    "tabla_resumen": {
                        "Total": total,
                        "OK": ok,
                        "NO_OK": nok,
                        "NO_OK_Reassembly": nok_r,
                    },
                    "histograms": rutas_histo,
                    "mediciones": st.session_state.resultados.to_dict(orient="records"),
                }
                
                pdf_name = f"Informe_Parte_{datos['cabecera']['Numero_de_parte']}_{datetime.now().strftime('%Y%m%d')}.pdf"
                pdf_path = os.path.join(PDF_DIR, pdf_name)
                with st.spinner("Generando PDF..."):
                    try:
                        generar_reporte_pdf(datos=datos, pdf_path=pdf_path)
                    except Exception as e:
                        st.error(f"Error al generar PDF: {e}")
                        raise

                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                    st.success("Informe generado correctamente.")
                    st.download_button(
                        "Descargar informe PDF",
                        data=pdf_bytes,
                        file_name=pdf_name,
                        mime="application/pdf",
                        use_container_width=True,
                    )


# ---- Columna 3: Métricas ----
with col_metricas:
    st.subheader("Lecturas en tiempo real")
    if botones_habilitados and st.session_state.conexiones_realizadas < st.session_state.total_conexiones:
        fila_actual = st.session_state.df_expandido.iloc[st.session_state.conexiones_realizadas]
        grado_actual = str(fila_actual["Grado de acero"]).strip()
        diametro_actual = str(fila_actual["Diametro"]).strip()
        st.markdown(f"**Conexión actual:** Grado {grado_actual} | Diámetro {diametro_actual}")
    else:
        st.markdown("**Conexión actual:** N/A")
    dx_val, dy_val, x_val, y_val, desplazamiento = st.session_state.ultima_lectura
    if st.session_state.get("umbral_min") is not None and st.session_state.get("umbral_max") is not None:
        dentro_umbral = st.session_state.umbral_min <= desplazamiento <= st.session_state.umbral_max
        color_emoji = "🟢" if dentro_umbral else "🔴"
        st.metric(f"Desplazamiento [mm] {color_emoji}", f"{desplazamiento:.3f}")
    else:
        st.metric("Desplazamiento [mm]", f"{desplazamiento:.3f}")

    st.metric("Conexiones realizadas", f"{st.session_state.conexiones_realizadas}/{st.session_state.total_conexiones}")


# ---- Loop de adquisición discreta ----
if st.session_state.medicion_activa:
    leer_sensor()
    time.sleep(0.05)  # 20 Hz
    st.rerun()

# ---- Pie de página ----
st.markdown("---")
st.caption("Simón Subrini - Proyecto Integrador Profesional - UNCo / Tenaris")
