import plotly.graph_objects as go
import pandas as pd
import numpy as np
import os

# ==========================================
# FUNCIONES DE PROCESAMIENTO DE DATOS
# ==========================================

def obtener_df(path1, path2):
    """
    Lee todas las hojas de dos archivos Excel y las devuelve como listas de DataFrames.
    """
    # Leer todas las hojas de un Excel en un diccionario
    dfs_dict1 = pd.read_excel(path1, sheet_name=None)
    dfs1 = list(dfs_dict1.values())
    
    # Leer todas las hojas del segundo Excel
    dfs_dict2 = pd.read_excel(path2, sheet_name=None)
    dfs2 = list(dfs_dict2.values())

    return dfs1, dfs2

def obtener_desplazamientos_finales(df1, df2):
    """
    Extrae la columna 'Desplazamiento corregido' de dos DataFrames.
    """
    desplazamientos = [None, None]  
    desplazamientos[0] = df1['Desplazamiento corregido'].tolist()
    desplazamientos[1] = df2['Desplazamiento corregido'].tolist()
    return desplazamientos

def calcular_metricas_estadisticas(desplazamientos, valor_ref):
    """
    Calcula MAE, STD, RMSE y cantidad de outliers para:
        - CuplaA (Grado A)
        - CuplaB (Grado B)
        - Total combinado
    Outliers: valores fuera del rango [media ± 1.5*sigma] 
    """
    resultados = {}
    grupos = ['CuplaA', 'CuplaB', 'Total']

    # Convertir a arrays numpy
    data_A = np.array(desplazamientos[0])
    data_B = np.array(desplazamientos[1])
    data_total = np.concatenate([data_A, data_B])

    mu_total = np.mean(data_total)

    for nombre, datos in zip(grupos, [data_A, data_B, data_total]):
        errores = datos - valor_ref
        mean = np.mean(datos)
        mae = np.mean(np.abs(errores))
        std = np.std(datos)
        rmse = np.sqrt(np.mean(errores**2))
        outliers = np.sum(np.abs(datos - mu_total) > 1.5)

        resultados[nombre] = {
            "MEAN": mean,
            "MAE": mae,
            "STD": std,
            "RMSE": rmse,
            "Outliers": int(outliers)
        }

    return resultados

# ==========================================
# FUNCIONES DE GRAFICACIÓN (RESULTADOS)
# ==========================================

def graficar_mediciones(dfs1: list, dfs2: list, valor_referencia: float, flag_graficar=False):
    """
    Grafica la superposición de mediciones de 'desplazamiento corregido'.
    """
    fig = go.Figure()

    # Primeras (Grado A - LS - Azul)
    for i, df in enumerate(dfs1):
        fig.add_trace(go.Scatter(
            y=df["desplazamiento corregido"],
            mode="lines",
            line=dict(color="blue", width=1),
            name="Grado A" if i == 0 else None,
            showlegend=(i == 0)
        ))

    # Siguientes (Grado B - ARCS - Rojo)
    for i, df in enumerate(dfs2):
        fig.add_trace(go.Scatter(
            y=df["desplazamiento corregido"],
            mode="lines",
            line=dict(color="red", width=1),
            name="Grado B" if i == 0 else None,
            showlegend=(i == 0)
        ))

    # Línea horizontal de referencia
    fig.add_hline(
        y=valor_referencia,
        line=dict(color="green", dash="dash"),
        annotation_text=f"Valor esperado = {valor_referencia}mm",
        annotation_position="bottom left"
    )

    fig.update_layout(
        title="Superposición de mediciones por cada grado de acero",
        xaxis_title="Muestra",
        yaxis_title="Desplazamiento corregido [mm]",
        legend=dict(
            x=0.8, y=0.02,
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="black", borderwidth=1
        )
    )
    
    output_dir = "graficos"
    os.makedirs(output_dir, exist_ok=True)
    fig.write_image(f"{output_dir}/SuperposicionMedicionesPorGrado.pdf")
    
    if flag_graficar:
        fig.show()

def graficar_medicion_ttt(df):
    """
    Grafica la curva Torque-Desplazamiento.
    """
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["AAA"],
        y=df["SMU"],
        mode="lines",
        line=dict(color="blue", width=1),
        name="Torque-Desplazamiento",
        showlegend=True
    ))

    fig.update_layout(
        title='Curva Torque-Desplazamiento medida en una conexión de 1"',
        xaxis_title="Desplazamiento",
        yaxis_title="Torque",
        legend=dict(
            x=0.1, y=0.9,
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="black", borderwidth=1
        ),
        xaxis=dict(
            range=[0, df["AAA"].max()], 
            showticklabels=False, 
            showgrid=False 
        ),
        yaxis=dict(
            range=[0, df["SMU"].max()], 
            showticklabels=False, 
            showgrid=False 
        )
    )
    
    output_dir = "graficos"
    os.makedirs(output_dir, exist_ok=True)
    fig.write_image(f"{output_dir}/TT.jpg", scale=2)

def graficar_distribuciones_superpuestas(desplazamientos, valor_referencia, folder='AAA'):
    """
    Grafica histogramas superpuestos de desplazamientos finales (Grado A vs B).
    """
    grupo_nombres = ["Grado A", "Grado B"]
    colores = ["blue", "red"]

    data1 = np.array(desplazamientos[0])
    data2 = np.array(desplazamientos[1])
    data_total = np.concatenate((data1, data2))

    mediaT = np.mean(data_total)

    fig = go.Figure()

    # Histograma Grado B (rojo)
    fig.add_trace(go.Histogram(
        x=data2,
        nbinsx=15,
        name=grupo_nombres[1],
        marker_color=colores[1],
        opacity=0.75
    ))

    # Histograma Grado A (azul)
    fig.add_trace(go.Histogram(
        x=data1,
        nbinsx=15,
        name=grupo_nombres[0],
        marker_color=colores[0],
        opacity=0.75
    ))

    # Líneas verticales
    fig.add_vline(
        x=valor_referencia, line=dict(color="black", dash="dot"),
        annotation_text=f"Valor esperado {valor_referencia}", annotation_position="top right",
        annotation=dict(yshift=-10, xshift=10, textangle=-90)
    )
    fig.add_vline(
        x=mediaT-1.5, line=dict(color="black", dash="dot"),
        annotation_text="µT-1.5", annotation_position="top left",
        annotation=dict(yshift=-30, textangle=-90)
    )
    fig.add_vline(
        x=mediaT+1.5, line=dict(color="black", dash="dot"),
        annotation_text="µT+1.5", annotation_position="top right",
        annotation=dict(yshift=-30, textangle=-90)
    )

    fig.update_layout(
        title=dict(
            text="Distribución de desplazamientos en 200 simulaciones de<br>torqueo de varillas de bombeo mecánico con MVP-1",
            x=0.5, xanchor='center', yanchor='top',
            font=dict(size=16)
        ),
        xaxis_title="Desplazamiento [mm]",
        yaxis_title="Frecuencia",
        bargap=0.15,
        width=900, height=500,
        legend=dict(
            x=0.15, y=0.9,
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="black", borderwidth=1
        )
    )
    
    output_path = f"graficos/{folder}"
    os.makedirs(output_path, exist_ok=True)
    fig.write_image(f"{output_path}/DistribucionSuperpuesta.pdf")
    fig.write_image(f"{output_path}/DistribucionSuperpuesta.jpg", scale=2)

def graficar_distribuciones_superpuestas_mvps(desplazamientos, valor_referencia, folder='Comparacion'):
    """
    Grafica distribuciones para 3 MVPs distintos.
    """
    grupo_nombres = ["MVP-1", "MVP-2", "MVP-3"]
    colores = ["blue", "red", "green"]

    fig = go.Figure()
    for i, desp in enumerate(desplazamientos):
        data1 = np.array(desp[0])
        data2 = np.array(desp[1])
        data_total = np.concatenate((data1, data2))

        mediaT = np.mean(data_total)
        sigmaT = np.std(data_total)

        print(f'MVP-{i}: media: {mediaT:.2f} | desvio: {sigmaT:.2f}')

        fig.add_trace(go.Histogram(
            x=data_total,
            xbins=dict(
                start=valor_referencia-3,
                end=valor_referencia+3,
                size=0.1
            ),
            name=grupo_nombres[i],
            marker_color=colores[i],
            opacity=0.75
        ))
    
    fig.add_vline(
        x=valor_referencia, line=dict(color="black", dash="dot"),
        annotation_text=f"Valor esperado {valor_referencia}", annotation_position="top left",
        annotation=dict(yshift=-10, xshift=0, textangle=-90)
    )
    
    fig.update_layout(
        title=dict(
            text="Distribución de desplazamientos en 200 simulaciones de<br>torqueo con cada uno de los 3 MVP",
            x=0.5, xanchor='center', yanchor='top',
            font=dict(size=16)
        ),
        xaxis_title="Desplazamiento [mm]",
        yaxis_title="Frecuencia",
        bargap=0.15,
        width=900, height=500,
        legend=dict(
            x=0.15, y=0.9,
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="black", borderwidth=1
        )
    )
    
    output_path = f"graficos/{folder}"
    os.makedirs(output_path, exist_ok=True)
    fig.write_image(f"{output_path}/DistribucionSuperpuestaConjunta.pdf")
    fig.write_image(f"{output_path}/DistribucionSuperpuestaConjunta.jpg", scale=2)

def graficar_boxplots_comparativos(desplazamientos, valor_referencia, folder='AAA'):
    """
    Grafica boxplots comparativos: Grado A, Grado B, y Ambos.
    """
    grupo_nombres = ["Grado A", "Grado B", "Ambos"]
    colores = ["blue", "red", "green"]

    data1 = np.array(desplazamientos[0])
    data2 = np.array(desplazamientos[1])
    data_total = np.concatenate((data1, data2))
    medias = [np.mean(data1), np.mean(data2), np.mean(data_total)]

    fig = go.Figure()

    # Boxplots
    for nombre, datos, color in zip(grupo_nombres, [data1, data2, data_total], colores):
        fig.add_trace(go.Box(
            y=datos,
            name=nombre,
            marker_color=color,
            boxmean=True,
            line=dict(width=1.5)
        ))

    # Línea de referencia
    fig.add_hline(
        y=valor_referencia,
        line=dict(color="black", width=3, dash="dot"),
        annotation_text=f"Valor esperado {valor_referencia:.2f} mm",
        annotation_position="top right",
        annotation=dict(yshift=-10, xshift=10)
    )

    # Líneas de media ± 1.5 mm
    for mu, color, nombre in zip(medias, colores, grupo_nombres):
        fig.add_hline(
            y=mu - 1.5,
            line=dict(color=color, dash="dash"),
            annotation_text=f"{nombre} μ -1.5",
            annotation_position="bottom left",
            annotation=dict(yshift=10)
        )
        fig.add_hline(
            y=mu + 1.5,
            line=dict(color=color, dash="dash"),
            annotation_text=f"{nombre} μ +1.5",
            annotation_position="top left",
            annotation=dict(yshift=-10)
        )

    fig.update_layout(
        title="Distribución comparativa de desplazamientos finales",
        yaxis_title="Desplazamiento [mm]",
        xaxis_title="Grupo",
        width=900, height=500,
        showlegend=False,
        plot_bgcolor="white",
        font=dict(size=12),
        margin=dict(l=60, r=60, t=80, b=60)
    )

    output_path = f"graficos/{folder}"
    os.makedirs(output_path, exist_ok=True)
    fig.write_image(f"{output_path}/BoxplotsComparativos.pdf")

def graficar_boxplots(gradoA, gradoB, folder):
    """
    Grafica boxplots simples para Grado A y Grado B.
    """
    fig = go.Figure()

    fig.add_trace(go.Box(
        y=gradoA, name="Grado A", marker_color="blue", line=dict(width=1.5)
    ))

    fig.add_trace(go.Box(
        y=gradoB, name="Grado B", marker_color="red", line=dict(width=1.5)
    ))

    fig.add_hline(
        y=3191.85, # Nota: Valor hardcodeado en la función original
        line=dict(color="black", dash="dash"),
        annotation_text="Valor esperado",
        annotation_position="top right",
        annotation=dict(xshift=-340)
    )

    fig.update_layout(
        title=dict(
            text="Distribución de mediciones de calibración en 10 rotaciones <br> de 20 vueltas",
            x=0.5, xanchor='center', yanchor='top',
            font=dict(size=16)
        ),
        yaxis_title="Desplazamiento medido [mm]",
        xaxis_title="Grado de acero",
        width=900, height=500,
        font=dict(size=13),
        legend=dict(
            x=0.9, y=0.99,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="black", borderwidth=1
        ),
        plot_bgcolor="white"
    )

    output_path = f"graficos/{folder}"
    os.makedirs(output_path, exist_ok=True)
    fig.write_image(f"{output_path}/BoxplotMedicionesCalibracion.jpg", scale=2)

def graficar_factor_calibracion(distancia, factor_calibracion):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=distancia, y=factor_calibracion,
        mode="lines+markers",
        name="Factor de calibración",
        line=dict(color="blue", width=2),
        marker=dict(symbol="circle", size=8, color="blue", line=dict(color="black", width=1))
    ))

    fig.update_layout(
        title=dict(
            text="Factor de calibración en función de la distancia 'sensor - cupla'",
            x=0.5, xanchor='center', yanchor='top',
            font=dict(size=16)
        ),
        xaxis_title="Distancia [mm]",
        yaxis_title="Factor de calibración",
        width=900, height=500,
        font=dict(size=13),
        plot_bgcolor="white",
        legend=dict(
            x=0.7, y=0.98,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="black", borderwidth=1
        )
    )
    
    os.makedirs("graficos/Lab-Distancias", exist_ok=True)
    fig.write_image("graficos/Lab-Distancias/FactorCalib.jpg", scale=2)

def graficar_error_vs_distancia(distancia, mae, std):
    fig = go.Figure()
    
    # MAE
    fig.add_trace(go.Scatter(
        x=distancia, y=mae,
        mode="lines+markers",
        name="Error absoluto medio (MAE)",
        line=dict(color="blue", width=2),
        marker=dict(symbol="circle", size=8, color="blue", line=dict(color="black", width=1))
    ))

    # STD
    fig.add_trace(go.Scatter(
        x=distancia, y=std,
        mode="lines+markers",
        name="Desviación estándar (STD)",
        line=dict(color="red", width=2),
        marker=dict(symbol="circle", size=8, color="red", line=dict(color="black", width=1))
    ))

    fig.update_layout(
        title=dict(
            text="Error de calibración en función de la distancia 'sensor - cupla'",
            x=0.5, xanchor='center', yanchor='top',
            font=dict(size=16)
        ),
        xaxis_title="Distancia [mm]",
        yaxis_title="Error absoluto medio y desvio estándar [mm]",
        width=900, height=500,
        font=dict(size=13),
        plot_bgcolor="white",
        legend=dict(
            x=0.6, y=0.98,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="black", borderwidth=1
        )
    )
    
    os.makedirs("graficos/Lab-Distancias", exist_ok=True)
    fig.write_image("graficos/Lab-Distancias/MAE-STD.jpg", scale=2)

def graficar_senal_25mm(path_excel):
    df = pd.read_excel(path_excel, sheet_name="25mm")
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%d/%m/%Y %H:%M:%S,%f")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["Corregido"],
        mode="lines",
        line=dict(color="blue", width=2),
        name="Desplazamiento corregido"
    ))

    fig.update_layout(
        title=dict(
            text="Señal medida durante la caracterización del sensor óptico<br>para una distancia Sensor–Cupla de 25mm",
            x=0.5, xanchor='center', yanchor='top',
            font=dict(size=16)
        ),
        xaxis_title="Tiempo",
        yaxis_title="Desplazamiento [mm]",
        width=950, height=500,
        font=dict(size=13),
        plot_bgcolor="white",
        legend=dict(
            x=0.7, y=0.98,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="black", borderwidth=1
        )
    )
    fig.update_xaxes(tickformat="%M:%S,%L")
    fig.update_xaxes(showticklabels=False)

    os.makedirs("graficos/Lab-Distancias", exist_ok=True)
    fig.write_image("graficos/Lab-Distancias/escalera_25mm.jpg", scale=2)

def graficar_enc_aaa(path_excel, name):
    df = pd.read_excel(path_excel, sheet_name=name)
    x = df["Desplazamiento Encoder"].values
    y = df["Desplazamiento AAA"].values
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y,
        mode="lines",
        line=dict(color="blue", width=2),
        name="Desplazamiento corregido"
    ))

    fig.update_layout(
        title=dict(
            text="Comparación de señales de desplazamiento,<br>obtenidas por el encoder incremental y el sensor óptico",
            x=0.5, xanchor='center', yanchor='top',
            font=dict(size=16)
        ),
        xaxis_title="Desplazamiento encoder [mm]",
        yaxis_title="Desplazamiento sensor óptico [mm]",
        width=950, height=500,
        font=dict(size=13),
        plot_bgcolor="white",
        legend=dict(
            x=0.7, y=0.98,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="black", borderwidth=1
        )
    )
    
    r = np.corrcoef(x, y)[0, 1]
    r2 = r**2
    print(f"{name} -> R²: {r2:.6f}")
    
    os.makedirs("graficos/AAA-vs-ENC-RIVA", exist_ok=True)
    fig.write_image(f"graficos/AAA-vs-ENC-RIVA/enc_aaa_{name}.jpg", scale=2)

def graficar_enc_aaa_error(path_excel, name):
    df = pd.read_excel(path_excel, sheet_name=name)
    df["muestra"] = range(1, len(df) + 1)

    x = df["muestra"].values
    y = df["Error absoluto"].values
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y,
        mode="lines",
        line=dict(color="blue", width=2),
        name="Desplazamiento corregido"
    ))

    fig.update_layout(
        title=dict(
            text="Error absoluto registrado entre el sensor óptico y el encoder incremental",
            x=0.5, xanchor='center', yanchor='top',
            font=dict(size=16)
        ),
        xaxis_title="Número de muestra",
        yaxis_title="Error absoluto [mm]",
        width=950, height=500,
        font=dict(size=13),
        plot_bgcolor="white",
        legend=dict(
            x=0.7, y=0.98,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="black", borderwidth=1
        )
    )
    
    # Se corrigieron las comillas anidadas en el f-string
    max_error = df["Error absoluto"].max()
    print(f"{name} -> máx: {max_error:.6f}")
    
    os.makedirs("graficos/AAA-vs-ENC-RIVA", exist_ok=True)
    fig.write_image(f"graficos/AAA-vs-ENC-RIVA/enc_aaa_err_{name}.jpg", scale=2)

# ==========================================
# BLOQUE PRINCIPAL (EJECUCIÓN)
# ==========================================

if __name__ == "__main__":
    
    # ----------------------------------------------------
    # 1. Graficar Torque-Desplazamiento (TTT)
    # ----------------------------------------------------
    # path_tt = "./Torque-Desplazamiento/TT.xlsx"
    # df_tt = pd.read_excel(path_tt, sheet_name="Hoja1")
    # graficar_medicion_ttt(df_tt)

    # ----------------------------------------------------
    # 2. Análisis de desplazamientos (Encoder vs AAA)
    # ----------------------------------------------------
    desplazamientos = []
    
    # --- Carga de datos MVP-1 (Encoder) ---
    path1_mvp1 = "./Encoder/RAW/Mediciones/CuplaA/resumen_mediciones.xlsx"
    path2_mvp1 = "./Encoder/RAW/Mediciones/CuplaB/resumen_mediciones.xlsx"
    
    df1_mvp1, df2_mvp1 = obtener_df(path1_mvp1, path2_mvp1)
    desp_mvp1 = obtener_desplazamientos_finales(df1_mvp1[0], df2_mvp1[0])
    desplazamientos.append(desp_mvp1)
    
    valor_ref = 13.74  # Desplazamiento para rotación de 31°
    graficar_distribuciones_superpuestas(desplazamientos[0], valor_ref, "Enc")

    # ----------------------------------------------------
    # 3. Ejemplos de uso de otras funciones (Historial)
    # ----------------------------------------------------
    
    # --- Carga MVP-2 y MVP-3 (para graficar_distribuciones_superpuestas_mvps) ---
    # path1_mvp2 = "./SLV/Mediciones/CuplaA/resumen_mediciones.xlsx"
    # path2_mvp2 = "./SLV/Mediciones/CuplaB/resumen_mediciones.xlsx"
    # df1_mvp2, df2_mvp2 = obtener_df(path1_mvp2, path2_mvp2)
    # desplazamientos.append(obtener_desplazamientos_finales(df1_mvp2[0], df2_mvp2[0]))
    
    # path1_mvp3 = "./AAA/Mediciones/CuplaA/resumen_mediciones.xlsx"
    # path2_mvp3 = "./AAA/Mediciones/CuplaB/resumen_mediciones.xlsx"
    # df1_mvp3, df2_mvp3 = obtener_df(path1_mvp3, path2_mvp3)
    # desplazamientos.append(obtener_desplazamientos_finales(df1_mvp3[0], df2_mvp3[0]))
    
    # --- Métricas Estadísticas ---
    # metricas = calcular_metricas_estadisticas(desplazamientos[0], valor_ref)
    # print("\n=== MÉTRICAS ESTADÍSTICAS ===")
    # for grupo, vals in metricas.items():
    #     print(f"\n {grupo}:")
    #     for k, v in vals.items():
    #         print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    # --- Boxplots Manuales ---
    # gradoA = (np.array([151.44,153.46,152.22,151.10,152.40])*20.4).tolist()
    # gradoB = (np.array([161.40,160.68,159.73,159.10,161.46])*20.4).tolist()
    # graficar_boxplots(gradoA, gradoB, 'SLV')

    # --- Calibración y Distancia ---
    # lista_distancia = [8, 15, 25, 40, 55]
    # lista_factor = [8.10, 6.62, 5.19, 4.04, 3.50]
    # lista_mae = [0.30, 0.13, 0.09, 0.11, 0.10]
    # lista_std = [0.19, 0.11, 0.05, 0.10, 0.04]
    # graficar_factor_calibracion(lista_distancia, lista_factor)
    # graficar_error_vs_distancia(lista_distancia, lista_mae, lista_std)

    # --- Comparación AAA vs Encoder ---
    # path_aaa_enc = "./AAA-vs-ENC-RIVA/AAA_ENC.xlsx"
    # graficar_enc_aaa(path_aaa_enc, '1')
    # graficar_enc_aaa_error(path_aaa_enc, '1')