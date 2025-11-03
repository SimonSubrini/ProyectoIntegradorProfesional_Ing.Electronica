from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import os

# --- CONFIGURACIÓN ---
TEMPLATES_DIR = "templates"

def generar_reporte_pdf(datos, pdf_path, flag_html=False):
    # --- CARGA DE PLANTILLA ---
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("report_template.html")

    # --- RENDER HTML ---
    html_content = template.render(datos)
    if flag_html:
        with open("reporte_preview.html", "w", encoding="utf-8") as f:
            f.write(html_content)

    # --- EXPORTAR A PDF ---
    HTML(string=html_content, base_url=os.getcwd()).write_pdf(pdf_path)

    print(f"✅ PDF generado correctamente: {pdf_path}")
