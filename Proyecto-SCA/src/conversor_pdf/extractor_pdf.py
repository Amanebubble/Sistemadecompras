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
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.directorio_db import buscar_por_nrc

from src.config import CARPETA_COLA1, CARPETA_COLA0, CARPETA_REVISION, CARPETA_RESPALDO, RUTA_LOG_SISTEMA
RUTA_LOG = RUTA_LOG_SISTEMA

import sys
try:
    from src.auditoria import registrar_error as auditoria_registrar_error
except ImportError:
    auditoria_registrar_error = None

def registrar_error(nombre_archivo: str, motivo: str):
    """Registra un error en el log local y en la base de datos de auditoría."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(RUTA_LOG, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] Archivo: {nombre_archivo} - Error: {motivo}\n")
    if auditoria_registrar_error:
        auditoria_registrar_error("Extractor PDF", nombre_archivo, motivo)


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
    match_uuid = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', texto)
    uuid_val = match_uuid.group(0).upper() if match_uuid else ""
    
    # Sello de recepción: cadena alfanumérica larga
    match_sello = re.search(r'(?:sello\s+recepcion|sello\s+de\s+recepci[\w]*)\s*[:=]?\s*([a-zA-Z0-9]{30,50})', texto)
    sello_val = match_sello.group(1).upper() if match_sello else ""
    
    # Fecha de emisión
    match_fecha = re.search(r'(?:fecha|fecemi|fecha y h[\w\s]*emision|fecha y hora)[\s\w]*[:=]\s*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})', texto)
    fecha_val = match_fecha.group(1) if match_fecha else ""
    
    # Número de control (Mejora)
    match_control = re.search(r'(?:n[\w\W]{1,3}mero|no\.?)\s*(?:de\s*)?control\s*[:=]?\s*(dte-\d{2}-\w{8}-\d{15})', texto)
    control_val = match_control.group(1).upper() if match_control else ""

    # NRC (Mejora)
    match_nrc = re.search(r'nrc\s*[:=]?\s*.{0,50}?(\d{3,8}-\d|\d{3,8})', texto)
    nrc_val = match_nrc.group(1) if match_nrc else ""
    
    # NIT
    match_nit = re.search(r'nit\s*[:=]?\s*.{0,50}?(\d{4}-\d{6}-\d{3}-\d)', texto)
    nit_val = match_nit.group(1) if match_nit else ""
    
    # Monto total (Mejora para validación)
    raw_matches = re.findall(r'\b(\d{1,3}(?:,\d{3})*\.\d{2})\b', texto)
    floats = []
    for m in raw_matches:
        try:
            floats.append(float(m.replace(',', '')))
        except:
            pass
            
    subtotal = 0.0
    iva = 0.0
    total_val = 0.0
    percibido = 0.0
    retenido = 0.0
    
    found_pair = False
    for i in range(len(floats)):
        for j in range(len(floats)):
            if i != j:
                st = floats[i]
                iv = floats[j]
                if st > 0 and abs(st * 0.13 - iv) <= 0.03:
                    subtotal = st
                    iva = iv
                    found_pair = True
                    break
        if found_pair:
            break
            
    if floats:
        total_val = max(floats)
        
    if not found_pair and total_val > 0.0:
        subtotal = round(total_val / 1.13, 2)
        iva = round(subtotal * 0.13, 2)
        
    # Check for percibido/retenido
    if found_pair:
        for f in floats:
            if f > 0 and abs(subtotal * 0.01 - f) <= 0.02:
                if 'percibido' in texto.lower() and 'retenido' not in texto.lower():
                    percibido = f
                elif 'retenido' in texto.lower() and 'percibido' not in texto.lower():
                    retenido = f
                elif 'percibido' in texto.lower() and 'retenido' in texto.lower():
                    if 'percibido: 0' in texto.lower() or 'percibido: $0' in texto.lower():
                        retenido = f
                    else:
                        percibido = f
    
    # Búsqueda en base de datos para nombre de emisor
    nombre_emisor = "Extraido de PDF"
    nit_emisor = nit_val
    if nrc_val:
        entidad = buscar_por_nrc(nrc_val)
        if entidad:
            nombre_emisor = entidad.get("nombre", nombre_emisor)
            nit_emisor = nit_emisor or entidad.get("nit", "")
            
    # Validación de usuario: si no hay nombre o nit o nrc, mandar a revisión
    if nombre_emisor == "Extraido de PDF" and not nit_emisor:
        pass # We will handle the exception logic outside, but wait, the instruction says to raise exception if not found.
        # Actually, if we return "Extraido de PDF", the motor_stream might catch it? No, estandarizador catches it!
        # The user said: "si no encuentra el nombre o nit o nrc que lo envie a revision manual"
        # I can just keep it as "Extraido de PDF". Estandarizador ALREADY sends "Extraido de PDF" to manual if we change estandarizador.
        # BUT wait! Estandarizador currently ALLOWS "Extraido de PDF"!
        # Let's change estandarizador instead, or raise here.
        # Let's raise here, it's easier and stops processing early.
        pass

    if 'percibido' in texto.lower() and percibido == 0.0 and not re.search(r'percibido\s*[:=]\s*\$?0\.00', texto.lower()):
        # Mandatory manual review for complex unextracted percibido
        nombre_emisor = "Forzar_Revision"
        
    if 'retenido' in texto.lower() and retenido == 0.0 and not re.search(r'retenido\s*[:=]\s*\$?0\.00', texto.lower()):
        nombre_emisor = "Forzar_Revision"

    return {
        "identificacion": {
            "codigoGeneracion": uuid_val,
            "numeroControl": control_val,
            "fecEmi": fecha_val,
            "tipoDte": "03"  # Default fallback
        },
        "emisor": {
            "nrc": nrc_val,
            "nit": nit_emisor,
            "nombre": nombre_emisor
        },
        "receptor": {
            "nombre": "Extraido de PDF"
        },
        "resumen": {
            "montoTotalOperacion": total_val,
            "totalCompra": subtotal,
            "ivaPerci1": percibido,
            "ivaRete1": retenido,
            "tributos": [
                {"codigo": "20", "valor": iva}
            ]
        },
        "selloRecibido": sello_val,
        "texto_crudo": texto
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
        
        # Nivel 1: MarkItDown (Herramienta principal solicitada)
        texto = extraer_texto_nivel_2(pdf)
        
        # Nivel 2: pdfplumber (Fallback)
        if not texto:
            print("    [!] MarkItDown no extrajo texto. Intentando Nivel 2 (pdfplumber)...")
            texto = extraer_texto_nivel_1(pdf)
            
        if not texto:
            print("    [X] No se pudo extraer texto del PDF.")
            registrar_error(pdf.name, "Ambos niveles de extracción fallaron o texto vacío.")
            shutil.move(str(pdf), str(CARPETA_REVISION / pdf.name))
            ruta_json = CARPETA_REVISION / pdf.with_suffix(".json").name
            with open(ruta_json, 'w', encoding='utf-8') as f:
                json.dump({"identificacion": {"codigoGeneracion": ""}, "emisor": {"nombre": "Fallo Texto"}, "texto_crudo": ""}, f, ensure_ascii=False)
            print("    [!] Enviado a Revisión Manual con JSON parcial vacío.")
            continue
            
        # Extracción de datos
        datos_json = extraer_datos_regex(texto)
        
        if not datos_json["identificacion"]["codigoGeneracion"]:
            print("    [!] No se encontró UUID válido en el texto.")
            registrar_error(pdf.name, "No se encontró UUID en el texto extraído.")
            shutil.move(str(pdf), str(CARPETA_REVISION / pdf.name))
            ruta_json = CARPETA_REVISION / pdf.with_suffix(".json").name
            with open(ruta_json, 'w', encoding='utf-8') as f:
                json.dump(datos_json, f, ensure_ascii=False, indent=2)
            print("    [!] Enviado a Revisión Manual por falta de UUID.")
            continue
            
        if datos_json["emisor"]["nombre"] in ["Extraido de PDF", "Forzar_Revision"]:
            print("    [!] Faltan datos críticos del proveedor o finanzas complejas (Revisión manual requerida).")
            registrar_error(pdf.name, "No se encontró proveedor en BD o finanzas complejas no extraíbles.")
            shutil.move(str(pdf), str(CARPETA_REVISION / pdf.name))
            ruta_json = CARPETA_REVISION / pdf.with_suffix(".json").name
            with open(ruta_json, 'w', encoding='utf-8') as f:
                json.dump(datos_json, f, ensure_ascii=False, indent=2)
            print("    [!] Enviado a Revisión Manual por proveedor desconocido o finanzas complejas.")
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
            raise Exception("Error al guardar JSON extraído del PDF.")

        import time
        time.sleep(1.5)


if __name__ == "__main__":
    procesar_cola()
