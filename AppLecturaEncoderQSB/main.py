import streamlit as st
import json
import time
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from collections import deque
import serial.tools.list_ports
from encoder_interface import detect_baudrate, configure_encoder, read_encoder, clear_encoder
import time

# =======================
# Parámetros de la app
# =======================
SAMPLING_FREQUENCY = 50         # Hz
UPDATE_INTERVAL = 1.0 / SAMPLING_FREQUENCY
MAX_DATA_POINTS = 500

TURNS_RATIO = 0.000234500434424684 # Relación de vueltas para 1", Calibrar con este parametro
TURNS_RATIO_7_8 = 1.8111/2 # Relación de vueltas para 7/8" repecto a 1"
TURNS_RATIO_3_4 = 1.625/2 # Relación de vueltas para 3/4" repecto a 1"

# =======================
# Clase principal
# =======================
class EncoderMonitor:
    def __init__(self):
        self.data_buffer = deque(maxlen=MAX_DATA_POINTS)
        self.time_buffer = deque(maxlen=MAX_DATA_POINTS)
        self.thresholds = self._load_thresholds()
        self.ser = None  # Objeto serial configurado
        print("\n\n----------------------------------- Ejecución app monitor de encoder -----------------------------------")

    def _load_thresholds(self):
        try:
            with open('thresholds.json','r') as f:
                print("[Enc] -> Abriendo thresholds.json...")
                return json.load(f)
        except FileNotFoundError:
            default = { g:{d:{"min":0,"max":100} for d in ["3/4","7/8","1"]}
                        for g in ["D","MMS","UHS","ARHS","ARCS"] }
            print("[Enc] -> No se encontro el archivo thresholds.json, creandolo...")
            with open('thresholds.json','w') as f:
                json.dump(default, f, indent=4)
            return default

    def get_thresholds(self, grade, diameter):
        return self.thresholds.get(grade,{}).get(diameter,{"min":0,"max":100})

    def list_com_ports(self):
        try:
            return [f"{p.device} - {p.description}" for p in serial.tools.list_ports.comports()]
        except:
            return []

    def extract_port(self, info):
        return info.split(" - ")[0] if " - " in info else info

    def monitor_clear_encoder(self):
        if self.ser is not None:
            clear_encoder(self.ser)

    def read_sensor(self, com_port,diameter="1"):
        if com_port is None:
            # Modo de simulación
            import random
            last = self.data_buffer[-1] if self.data_buffer else 0
            delta = random.uniform(-5000,15000)
            return max(0, last + delta)

        encoder_val = read_encoder(self.ser)  # Encoder real
        displacement = encoder_val * 1
        if diameter == "3/4":
            displacement*=TURNS_RATIO_3_4
        if diameter == "7/8":
            displacement*=TURNS_RATIO_7_8
        return displacement

    def add_point(self, val) -> None:
        now = datetime.now()
        self.data_buffer.append(val)
        self.time_buffer.append(now)
        return

    def df(self):
        return pd.DataFrame({'time': list(self.time_buffer),
                             'enc_value': list(self.data_buffer)})

    def clear(self) -> None:
        self.data_buffer.clear()
        self.time_buffer.clear()
        return

    def disconnect_serial(self) -> None:
        try:
            if self.ser is not None:
                if self.ser.is_open:
                    self.ser.close()
                self.ser = None   # 🔑 eliminar la referencia
                print("[Enc-Info] -> Puerto COM cerrado correctamente")
        except Exception as e:
            print(f"[Enc-Info] -> Se intento cerrar el puerto COM, pero ya se encontraba cerrado: {e}")
        return

# =======================
# Función para graficar
# =======================
def create_plot(df, thresholds, grade, diameter):
    fig = go.Figure()

    if not df.empty:
        x0, x1 = df['time'].iloc[[0, -1]]

        # Área verde (zona segura)
        fig.add_trace(go.Scatter(
            x=[x0, x1, x1, x0],
            y=[thresholds['min'], thresholds['min'], thresholds['max'], thresholds['max']],
            fill='toself',
            fillcolor='rgba(0,255,0,0.1)',
            line=dict(color='rgba(0,0,0,0)'),
            hoverinfo='skip',         # no interactúa con el cursor
            showlegend=False
        ))

        # Señal del sensor
        fig.add_trace(go.Scatter(
            x=df['time'],
            y=df['enc_value'],
            mode='lines+markers',
            name='Encoder',
            line=dict(color='royalblue')
        ))

    fig.update_layout(
        title=f'Monitor de encoder - {grade} {diameter}\"',
        xaxis_title='Tiempo',
        yaxis_title='Desplazamiento (mm)',
        hovermode='x unified',
        height=500
    )

    return fig


# =======================
# Función principal
# =======================

def main():
    st.set_page_config(page_title="Monitor de Sensores", layout="wide")
    st.title("Monitor de Sensores en Tiempo Real")

    # Inicialización de variables de sesión
    if 'monitor' not in st.session_state:
        st.session_state.monitor = EncoderMonitor()
        st.session_state.is_running = False
        st.session_state.selected_com = None
        st.session_state.baud = None
        st.session_state.ser_configured = False
        st.session_state.ser_configured_button_enable = False
        st.session_state.diameter = "1"
        st.session_state.status_msg = None
        st.session_state.direction = 1

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Configuración")
        available_ports = st.session_state.monitor.list_com_ports()

        if available_ports:
            port_options = ["Ninguno (Datos de prueba)"] + available_ports
            selected_port_info = st.selectbox(
                "Puerto Serial",
                options=port_options,
                index=0,
                help="Selecciona el puerto COM para conectar con el sensor"
            )

            if selected_port_info == "Ninguno (Datos de prueba)":
                st.session_state.selected_com = None
                st.session_state.ser_configured = False
                st.info("Generando datos de prueba")
            else:
                com = st.session_state.monitor.extract_port(selected_port_info)
                if com != st.session_state.selected_com:
                    st.session_state.selected_com = com
                    st.session_state.ser_configured = False
                    st.session_state.status_msg = f"Conexión exitosa al puerto : {com}"
                
                if st.session_state.status_msg:
                    st.success(st.session_state.status_msg)

                if not st.session_state.ser_configured:
                    with st.spinner("Detectando baudrate y configurando encoder..."):
                        baud = 230400
                        st.session_state.monitor.disconnect_serial()
                        try:
                            baud = detect_baudrate(com)
                        except Exception as e:
                            err = e
                            print(f'Error detectando baudrate, se usara 230400')
                        ser = configure_encoder(com, baudrate=baud)
                        st.session_state.monitor.ser = ser
                        st.session_state.baud = baud
                        st.session_state.ser_configured = True
                        st.success(f"Encoder configurado a {baud} bps")
                        st.session_state.ser_configured_button_enable=True

        else:
            st.warning("No hay puertos COM disponibles")
            st.session_state.selected_com = None
            st.session_state.ser_configured = False
            st.session_state.ser_configured_button_enable=False

        # Botón para actualizar lista de puertos
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Actualizar Puertos"):
                print("[App-Func] -> Actualizando puertos")
                st.rerun()
        with col2:
            if st.button("🔌 Liberar puerto COM",disabled=not st.session_state.ser_configured_button_enable):
                print("[App-Func] -> Desconectando puerto COM")
                st.session_state.is_running = False   
                time.sleep(0.1)                  
                st.session_state.monitor.disconnect_serial()
                st.session_state.ser_configured_button_enable = False
                st.session_state.status_msg = "Puerto COM desconectado exitosamente"
                st.rerun()

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            grade = st.selectbox(
                "Grado de Acero",
                options=["D","MMS", "UHS", "ARHS", "ARCS"], #
                index=0
            )
        with col2:
            diameter = st.selectbox(
                "Diámetro",
                options=["3/4", "7/8", "1"],
                index=0,
                help='Desplazamientos ajustados a 3/4" FS, 7/8" FS y 1" SH; para otros diametros, se debe realizar corrección manual'
            )
        thr = st.session_state.monitor.get_thresholds(grade, diameter)
        st.subheader("📊 Umbrales óptimos")
        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"Mínimo: {thr['min']} mm")
        with col2:
            st.caption(f"Máximo: {thr['max']} mm")

        st.markdown("---")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("▶️ Play", disabled=st.session_state.is_running):
                print("[App-Func] -> Iniciando stream...")
                st.session_state.is_running = True
                st.rerun()
        with col2:
            if st.button("⏹️ Pause", disabled=not st.session_state.is_running):
                print("[App-Func] -> Deteniendo stream...")
                st.session_state.is_running = False
                time.sleep(0.2)
                st.rerun()
        with col3:
            if st.button("🗑️ Clear", disabled=st.session_state.is_running):
                print("[App-Func] -> Borrando puntos stream...")
                try:
                    st.session_state.monitor.monitor_clear_encoder()
                except Exception as e:
                    print(f"[App-Func] -> Error al eliminar los puntos de la gráfica (se desconecto la interfaz QSB-S): {e}")
                st.session_state.monitor.clear()
                st.rerun()

        st.markdown("---")

        if st.button("🔁 Invertir señal", disabled=not st.session_state.is_running):
            st.session_state.direction = -1 * st.session_state.direction
            st.rerun()

        st.markdown("---")

        current_df = st.session_state.monitor.df()

        
        try:
            if "csv_data" not in st.session_state or not current_df.equals(
                getattr(st.session_state, "last_df", pd.DataFrame())
            ):
                st.session_state.csv_data = current_df.to_csv(index=False).encode('utf-8')
                st.session_state.last_df = current_df.copy()
                
            if not current_df.empty:
                csv_bytes = current_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="💾 Guardar CSV",
                    data=csv_bytes,
                    file_name="datos_encoder.csv",
                    mime='text/csv',
                    disabled=st.session_state.is_running
                )
            else:
                st.info("No hay datos para exportar.")

        except MediaFileStorageError:
            print("[App-Func] -> Stream detenido, generando CSV")
            st.info("Error temporal al acceder al CSV. Intenta nuevamente.")
            
        except Exception as e:
            print(f"[App-Func] -> ⚠️ Error inesperado al generar botón CSV: {e}")

    # --- ÁREA PRINCIPAL ---
    df = st.session_state.monitor.df()

    cols = st.columns([2,1])
    with cols[0]:
        st.plotly_chart(create_plot(df, thr, grade, diameter), use_container_width=True)
    with cols[1]:
        if not df.empty:
            last = df['enc_value'].iloc[-1]
            if thr['min'] <= last <= thr['max']:
                status = "✅ EN RANGO OPTIMO"
                delta_color = "normal"
            else:
                status = "❌ FUERA DE RANGO OPTIMO"
                delta_color = "inverse"

            st.metric(
                "Desplazamiento final",
                f"{last:.2f} mm",
                delta=status,
                delta_color=delta_color
            )
            st.metric("Máximo", f"{df['enc_value'].max():.2f} mm")

            # Calcular diferencias entre puntos consecutivos
            time_diffs = df['time'].diff().dt.total_seconds().dropna()
            value_diffs = df['enc_value'].diff().dropna()

            # Calcular frecuencia de muestreo promedio ignorando pausas largas

            # Calcular pendiente máxima (mm/s)
            slopes = value_diffs / time_diffs
            max_slope = slopes.max()
            st.metric("Pendiente máxima", f"{max_slope:.2f} mm/s")

            start_time = df['time'].iloc[0]
            end_time = df['time'].iloc[-1]
            total_time = (end_time - start_time).total_seconds()
            st.metric("Duración", f"{total_time:.1f} s")
            st.metric("Puntos tomados", len(df))
        else:
            st.info("Sin datos disponibles. Pulsa ▶️ Play para iniciar.")

    # --- LECTURA CONTINUA ---
    if st.session_state.is_running:
        val = st.session_state.monitor.read_sensor(st.session_state.selected_com,diameter=st.session_state.diameter)
        print(f"Lectura encoder: {val}")
        val = val * st.session_state.direction * TURNS_RATIO
        print(f"Lectura encoder escalada: {val}\n")
        st.session_state.monitor.add_point(val)
        time.sleep(UPDATE_INTERVAL)
        st.rerun()

if __name__=="__main__":
    main()
