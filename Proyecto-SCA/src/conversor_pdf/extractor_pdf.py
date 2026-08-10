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
import time

import pdfplumber
from markitdown import MarkItDown
from groq import Groq

ultimo_llamado_gemini = 0

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

def extraer_texto_ocr_nivel_4(ruta_pdf: Path) -> str:
    """Nivel 4: Convierte el PDF a imagen de alta resolución y aplica OCR local usando RapidOCR."""
    try:
        import fitz
        from rapidocr import RapidOCR
        import logging
        
        # Ocultar logs excesivos de RapidOCR
        logging.getLogger("RapidOCR").setLevel(logging.ERROR)
        
        ocr = RapidOCR()
        doc = fitz.open(str(ruta_pdf))
        texto_total = ""
        
        print(f"    [*] Nivel 4 OCR: Analizando {len(doc)} páginas con RapidOCR (Local)...")
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            result, elapse = ocr(img_bytes)
            if result:
                for line in result:
                    texto_total += line[1] + "\n"
                    
        return texto_total
    except ImportError:
        print("    [!] Error: Librerías PyMuPDF (fitz) o rapidocr no están instaladas.")
        return ""
    except Exception as e:
        print(f"    [!] Error en Nivel 4 OCR: {e}")
        return ""


def extraer_con_groq(ruta_pdf: Path) -> dict:
    global ultimo_llamado_gemini
    
    # Rate limit: 15 segundos entre llamadas
    ahora = time.time()
    if ahora - ultimo_llamado_gemini < 15:
        time.sleep(15 - (ahora - ultimo_llamado_gemini))
        
    ultimo_llamado_gemini = time.time()
    
    try:
        print("    [*] Extrayendo texto con pdfplumber para enviarlo a Groq...")
        
        texto_pdf = extraer_texto_nivel_1(ruta_pdf)
        if not texto_pdf.strip():
            print("    [X] pdfplumber no pudo extraer texto. Activando Nivel 4 (OCR Inteligente Local)...")
            texto_pdf = extraer_texto_ocr_nivel_4(ruta_pdf)
            
            if not texto_pdf.strip():
                print("    [X] Nivel 4 (OCR) también falló. Documento ilegible o dañado.")
                return None
            else:
                print("    [OK] Nivel 4 (OCR) rescató el texto con éxito.")
            
        print("    [*] Analizando texto con Groq (llama-3.3-70b-versatile)...")
        api_key = os.environ.get("GROQ_API_KEY")
        client = Groq(api_key=api_key)
        
        prompt = f"""
        Eres un experto extrayendo datos de documentos. Extrae los siguientes datos del siguiente texto de un DTE y devuélvelos en formato JSON estricto.
        IMPORTANTE: Si el documento NO es un DTE válido de El Salvador (tipos permitidos: 03, 05, 06, 14), o es ilegible, o no tiene relación con facturación, añade la clave "estado_revision" con el valor "INVALIDO". De lo contrario, pon "VALIDO".
        
        Formato JSON esperado:
        {{
            "identificacion": {{
                "codigoGeneracion": "<UUID de 36 caracteres>",
                "numeroControl": "<Ej. DTE-03-...>",
                "fecEmi": "<fecha de emisión>",
                "tipoDte": "<03, 05, 06 o 14>"
            }},
            "emisor": {{
                "nombre": "<Nombre del EMISOR (Quien emite la factura)>",
                "nrc": "<NRC>"
            }},
            "receptor": {{
                "nombre": "<Nombre del RECEPTOR (A quien se le emite la factura)>",
                "nit": "<NIT del Receptor, si lo tiene>"
            }},
            "resumen": {{
                "montoTotalOperacion": <flotante, total general>,
                "totalCompra": <flotante, subtotal o total sujeto a iva>,
                "totalExenta": <flotante>,
                "ivaPerci1": <flotante>,
                "ivaRete1": <flotante>,
                "tributos": [
                    {{"codigo": "20", "valor": <flotante, el IVA>}}
                ]
            }},
            "selloRecibido": "<sello de recepción>",
            "estado_revision": "VALIDO" o "INVALIDO",
            "texto_crudo": "Extraído por Groq IA"
        }}
        
        Texto del PDF:
        {texto_pdf}
        """
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        texto_res = response.choices[0].message.content.strip()
        return json.loads(texto_res)
    except Exception as e:
        print(f"    [X] Error en Groq AI: {e}")
        return None

def procesar_cola():
    """Procesa todos los PDFs pendientes en cola1."""
    pdfs = list(CARPETA_COLA1.glob("*.pdf"))

    if not pdfs:
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
            
        datos_json = None
        usar_gemini = False
        
        if not texto:
            print(f"[Inteligencia Artificial] Falló OCR local en '{pdf.name}'. Enviando a Groq IA...")
            usar_gemini = True
        else:
            # NIVEL 1.5: FAST-REJECT (Cortafuegos para descartar No-DTEs rápidos)
            texto_upper = texto.upper()
            if not any(kw in texto_upper for kw in ["DOCUMENTO TRIBUTARIO", "CREDITO FISCAL", "CRÉDITO FISCAL", "DTE-", "FACTURA", "COMPROBANTE"]):
                print(f"    [FAST-REJECT] El documento '{pdf.name}' no parece ser un DTE. Descartando a Otros DTEs...")
                from src.config import BASE_DIR
                CARPETA_OTROS = BASE_DIR / 'data' / '09_otros_dtes'
                shutil.move(str(pdf), str(CARPETA_OTROS / pdf.name))
                continue
                
            # NIVEL 2.5: FAST-TRACK (Plantillas Heurísticas para Proveedores Frecuentes)
            try:
                from src.conversor_pdf.plantillas_frecuentes import procesar_con_plantillas
                datos_json = procesar_con_plantillas(texto)
            except Exception as e:
                print(f"    [!] Error en Fast-Track: {e}")
                datos_json = None
                
            if not datos_json:
                # Si falló el Fast-Track, intentamos Regex General
                datos_json = extraer_datos_regex(texto)
                if not datos_json["identificacion"]["codigoGeneracion"] or datos_json["emisor"]["nombre"] in ["Extraido de PDF", "Forzar_Revision"]:
                    print(f"[Inteligencia Artificial] Regex incompleto en '{pdf.name}'. Enviando a Groq IA...")
                    usar_gemini = True
                
        if usar_gemini:
            datos_json = extraer_con_groq(pdf)
            if not datos_json:
                print(f"[Inteligencia Artificial] [ERROR] Groq falló al procesar '{pdf.name}'")
                registrar_error(pdf.name, "Todos los niveles (incluida la IA) fallaron.")
                shutil.move(str(pdf), str(CARPETA_REVISION / pdf.name))
                ruta_json = CARPETA_REVISION / pdf.with_suffix(".json").name
                with open(ruta_json, 'w', encoding='utf-8') as f:
                    json.dump({"identificacion": {"codigoGeneracion": ""}, "emisor": {"nombre": "Fallo IA"}, "texto_crudo": ""}, f, ensure_ascii=False)
                print(f"[Inteligencia Artificial] Documento '{pdf.name}' enviado a Revisión Manual.")
                continue
                
        try:
            # Verificar si Groq lo marcó como INVALIDO
            if datos_json.get("estado_revision") == "INVALIDO":
                print(f"[Inteligencia Artificial] Documento '{pdf.name}' detectado como INVÁLIDO. Moviendo a Otros DTEs.")
                from src.config import BASE_DIR
                CARPETA_OTROS = BASE_DIR / 'data' / '09_otros_dtes'
                shutil.move(str(pdf), str(CARPETA_OTROS / pdf.name))
                ruta_json = CARPETA_OTROS / pdf.with_suffix(".json").name
                with open(ruta_json, 'w', encoding='utf-8') as f:
                    json.dump(datos_json, f, ensure_ascii=False, indent=2)
                continue
                
            # Validación final por si se omitió INVALIDO pero faltan datos
            identificacion = datos_json.get("identificacion", {})
            emisor = datos_json.get("emisor", {})
            codigo_gen = identificacion.get("codigoGeneracion")
            
            if not codigo_gen:
                print(f"[Inteligencia Artificial] Faltan UUID en '{pdf.name}'. Enviado a Revisión Manual.")
                registrar_error(pdf.name, "No se encontró UUID en el texto extraído.")
                shutil.move(str(pdf), str(CARPETA_REVISION / pdf.name))
                ruta_json = CARPETA_REVISION / pdf.with_suffix(".json").name
                with open(ruta_json, 'w', encoding='utf-8') as f:
                    json.dump(datos_json, f, ensure_ascii=False, indent=2)
                continue
                
            nombre_emisor = emisor.get("nombre", "")
            if nombre_emisor in ["Extraido de PDF", "Forzar_Revision", "", None]:
                print(f"[Inteligencia Artificial] Falta proveedor en '{pdf.name}'. Enviado a Revisión Manual.")
                registrar_error(pdf.name, "Proveedor desconocido.")
                shutil.move(str(pdf), str(CARPETA_REVISION / pdf.name))
                ruta_json = CARPETA_REVISION / pdf.with_suffix(".json").name
                with open(ruta_json, 'w', encoding='utf-8') as f:
                    json.dump(datos_json, f, ensure_ascii=False, indent=2)
                continue
                
            # Guardar el JSON en cola0
            nombre_json = pdf.with_suffix(".json").name
            ruta_json = CARPETA_COLA0 / nombre_json
            
            with open(ruta_json, 'w', encoding='utf-8') as f:
                json.dump(datos_json, f, ensure_ascii=False, indent=2)
            print(f"[Inteligencia Artificial] Datos extraídos con éxito: '{nombre_json}'")
            
            # Mover el PDF procesado a Respaldo
            destino_pdf = CARPETA_RESPALDO / pdf.name
            if destino_pdf.exists():
                # Manejar colisión de nombres
                destino_pdf = CARPETA_RESPALDO / f"{pdf.stem}_{datetime.now().strftime('%H%M%S')}{pdf.suffix}"
            shutil.move(str(pdf), str(destino_pdf))

        except Exception as e:
            print(f"[Inteligencia Artificial] [ERROR] Fallo crítico en '{pdf.name}': {e}")
            print(traceback.format_exc())
            registrar_error(pdf.name, f"Error fatal: {e}")
            try:
                shutil.move(str(pdf), str(CARPETA_REVISION / pdf.name))
            except:
                pass
            continue

        import time
        time.sleep(1.5)


if __name__ == "__main__":
    procesar_cola()
