import os
import pandas as pd
import matplotlib.pyplot as plt

def generar_histogramas(df, output_dir) -> None:
    
    orden_diametros = ["1", "7/8", "3/4"]
    
    df_filtrado = df[~df['comentario'].str.contains("reassembly", case=False, na=False)].copy()
    df_filtrado['diametro'] = pd.Categorical(df_filtrado['diametro'], categories=orden_diametros, ordered=True)
    
    os.makedirs(output_dir, exist_ok=True)
    
    grupos = df_filtrado.groupby(['diametro', 'grado_acero'])
    output_paths=[]
    
    for (diametro, grado), grupo in grupos:
        desplazamientos = grupo['desplazamiento'].astype(float)
        umbral_min = grupo['umbral_min'].iloc[0]
        umbral_max = grupo['umbral_max'].iloc[0]
        
        plt.figure(figsize=(6, 4))  
        plt.hist(desplazamientos, bins=10, color='steelblue', edgecolor='black', alpha=0.7)
        
        plt.axvline(umbral_min, color='red', linestyle='--', linewidth=2, label=f'Umbral min ({umbral_min:.2f})')
        plt.axvline(umbral_max, color='green', linestyle='--', linewidth=2, label=f'Umbral max ({umbral_max:.2f})')
        
        plt.title(f"Histograma - {grado} - Ø {diametro}", fontsize=12, fontweight='bold')
        plt.xlabel("Desplazamiento [mm]", fontsize=10)
        plt.ylabel("Frecuencia", fontsize=10)
        plt.grid(alpha=0.3)
        plt.legend(fontsize=8, loc='upper right', frameon=True)
        plt.tight_layout()
        
        filename = f"hist_{grado}_{diametro}.jpg".replace("/", "-")  # evitar conflictos con nombres tipo 3/4
        path = os.path.join(output_dir, filename)
        output_paths.append({"titulo": "{grado} {diametro}", "imagen": path})
        plt.savefig(path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"[OK] Guardado: {path}")
    return output_paths
