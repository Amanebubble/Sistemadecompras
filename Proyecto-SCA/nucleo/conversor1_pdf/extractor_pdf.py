"""
Extractor PDF: Extracción de datos DTE desde archivos PDF.

Este módulo lee los PDFs clasificados en la cola1, extrae su texto
usando una estrategia de dos niveles (pdfplumber -> markitdown),
normaliza el texto y extrae los campos clave (UUID, NRC, Sello) mediante Regex.
El resultado se guarda como un JSON "crudo" en la cola0 para que el
estandarizador lo procese en la siguiente etapa.
"""

import json
import re
import shutil
import traceback
from pathlib import Path
from datetime import datetime

import pdfplumber
from markitdown import MarkItDown

# ── Rutas dinámicas ────────────────────────────────────────────────────────
MODULO_DIR = Path(__file__).resolve().parent
NUCLEO_DIR = MODULO_DIR.parent
RAIZ_PROYECTO = NUCLEO_DIR.parent

CARPETA_COLA1 = NUCLEO_DIR / "filtro_service" / "cola1"
CARPETA_COLA0 = NUCLEO_DIR / "filtro_service" / "cola0"
CARPETA_REVISION = NUCLEO_DIR / "Revision_Manual"
CARPETA_RESPALDO = NUCLEO_DIR / "Respaldo_PDF"
RUTA_LOG = MODULO_DIR / "registro_errores.log"

# Asegurar que existan las carpetas necesarias
for carpeta in [CARPETA_COLA1, CARPETA_COLA0, CARPETA_REVISION, CARPETA_RESPALDO]:
    carpeta.mkdir(parents=True, exist_ok=True)


def registrar_error(nombre_archivo: str, motivo: str):
    """Registra un error en el archivo de log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(RUTA_LOG, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] Archivo: {nombre_archivo} - Error: {motivo}\n")


def aplanar_texto(texto: str) -> str:
    """Normaliza el texto: minúsculas, sin saltos de línea ni tabulaciones, espacios reducidos."""
    if not texto:
        return ""
    texto = texto.lower()
    texto = texto.replace('\n', ' ').replace('\t', ' ')
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def extraer_texto_nivel_1(ruta_pdf: Path) -> str:
    """Intenta extraer texto usando pdfplumber (Fast Path)."""
    texto_completo = []
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for page in pdf.pages:
                texto_pagina = page.extract_text()
                if texto_pagina:
                    texto_completo.append(texto_pagina)
        return aplanar_texto(" ".join(texto_completo))
    except Exception as e:
        print(f"    [!] Error en pdfplumber: {e}")
        return ""


def extraer_texto_nivel_2(ruta_pdf: Path) -> str:
    """Intenta extraer texto usando MarkItDown (Fallback)."""
    try:
        md = MarkItDown()
        resultado = md.convert(str(ruta_pdf))
        return aplanar_texto(resultado.text_content)
    except Exception as e:
        print(f"    [!] Error en MarkItDown: {e}")
        return ""


def extraer_datos_regex(texto: str) -> dict:
    """Extrae los campos clave usando expresiones regulares."""
    
    # UUID: 36 caracteres con guiones
    match_uuid = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', texto)
    uuid_val = match_uuid.group(0).upper() if match_uuid else ""
    
    # NRC: dígitos, posiblemente con guion (se toma la primera ocurrencia que suele ser el emisor)
    match_nrc = re.search(r'nrc\s*[:=]?\s*([\d-]+)', texto)
    nrc_val = match_nrc.group(1) if match_nrc else ""
    
    # Sello de recepción: cadena alfanumérica larga (usualmente >= 30 caracteres)
    match_sello = re.search(r'(?:sello\s+recepcion|sello\s+de\s+recepci[\w]*)\s*[:=]?\s*([a-z0-9]{30,45})', texto)
    sello_val = match_sello.group(1).upper() if match_sello else ""
    
    # Fecha de emisión (Intento extra para ayudar a pasar la validación del estandarizador)
    match_fecha = re.search(r'(?:fecha|fecemi|fecha y hora)[\s\w]*[:=]\s*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})', texto)
    fecha_val = match_fecha.group(1) if match_fecha else ""

    # Construir el diccionario crudo imitando la estructura de Hacienda
    # para que el conversor0_json lo pueda mapear.
    return {
        "identificacion": {
            "codigoGeneracion": uuid_val,
            "fecEmi": fecha_val,
            "tipoDte": "03"  # Default fallback
        },
        "emisor": {
            "nrc": nrc_val,
            "nombre": "Extraido de PDF" # Placeholder
        },
        "receptor": {
            "nombre": "Extraido de PDF"
        },
        "selloRecibido": sello_val,
        "texto_crudo": texto # Guardar todo el texto para visualizar montos y fechas
    }


def procesar_cola():
    """Procesa todos los PDFs pendientes en cola1."""
    print("=" * 60)
    print("  CONVERSOR1-PDF: Extracción desde PDF")
    print("=" * 60)

    pdfs = list(CARPETA_COLA1.glob("*.pdf"))

    if not pdfs:
        print("  No hay PDFs en cola1/ para procesar.")
        return

    print(f"  Se encontraron {len(pdfs)} PDFs. Iniciando procesamiento...\n")

    for pdf in pdfs:
        print(f"  Procesando: {pdf.name}")
        
        # Nivel 1
        texto = extraer_texto_nivel_1(pdf)
        
        # Nivel 2
        if not texto:
            print("    [!] pdfplumber no extrajo texto. Intentando Nivel 2 (MarkItDown)...")
            texto = extraer_texto_nivel_2(pdf)
            
        if not texto:
            print("    [X] No se pudo extraer texto del PDF.")
            registrar_error(pdf.name, "Ambos niveles de extracción fallaron o texto vacío.")
            # Mover a revisión manual
            shutil.move(str(pdf), str(CARPETA_REVISION / pdf.name))
            continue
            
        # Extracción de datos
        datos_json = extraer_datos_regex(texto)
        
        if not datos_json["identificacion"]["codigoGeneracion"]:
            print("    [!] No se encontró UUID válido en el texto.")
            registrar_error(pdf.name, "No se encontró UUID en el texto extraído.")
            shutil.move(str(pdf), str(CARPETA_REVISION / pdf.name))
            continue
            
        # Guardar el JSON en cola0
        nombre_json = pdf.with_suffix(".json").name
        ruta_json = CARPETA_COLA0 / nombre_json
        
        try:
            with open(ruta_json, 'w', encoding='utf-8') as f:
                json.dump(datos_json, f, ensure_ascii=False, indent=2)
            print(f"    [OK] Datos extraídos y enviados a cola0: {nombre_json}")
            
            # Mover el PDF procesado a Respaldo
            destino_pdf = CARPETA_RESPALDO / pdf.name
            if destino_pdf.exists():
                # Manejar colisión de nombres
                destino_pdf = CARPETA_RESPALDO / f"{pdf.stem}_{datetime.now().strftime('%H%M%S')}{pdf.suffix}"
            shutil.move(str(pdf), str(destino_pdf))
            
        except Exception as e:
            print(f"    [X] Error al guardar JSON: {e}")
            registrar_error(pdf.name, f"Error al guardar JSON extraído: {traceback.format_exc()}")
            shutil.move(str(pdf), str(CARPETA_REVISION / pdf.name))


if __name__ == "__main__":
    procesar_cola()
