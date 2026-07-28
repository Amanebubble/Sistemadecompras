"""
Extractor Slow Path: extracción de datos DTE desde archivos PDF.
"""

import fitz
from pyzbar.pyzbar import decode
from PIL import Image
import re
import math
import shutil
import os
import io

def extraer_desde_pdf(ruta_pdf: str, carpeta_otros: str, carpeta_errores: str) -> dict | None:
    """Extrae datos de un DTE en formato PDF.

    Args:
        ruta_pdf: Ruta completa al archivo PDF.
        carpeta_otros: Ruta a la carpeta Otros_Documentos_Clasificados.
        carpeta_errores: Ruta a la carpeta Errores.

    Returns:
        dict con los datos extraídos listos para mapear a la plantilla, o None
        si se descartó por tipo o hubo fallo matemático.
    """
    try:
        doc = fitz.open(ruta_pdf)
    except Exception:
        if os.path.exists(ruta_pdf):
            shutil.move(ruta_pdf, os.path.join(carpeta_errores, os.path.basename(ruta_pdf)))
        return None

    # Extraer texto de la primera página
    try:
        page = doc[0]
        texto = page.get_text()
    except Exception:
        doc.close()
        if os.path.exists(ruta_pdf):
            shutil.move(ruta_pdf, os.path.join(carpeta_errores, os.path.basename(ruta_pdf)))
        return None

    texto_normalizado = texto.lower()

    # Buscar Número de Control
    match_control = re.search(r"dte-(\d{2})-[a-z0-9]+-\d+", texto_normalizado)
    if not match_control:
        doc.close()
        if os.path.exists(ruta_pdf):
            shutil.move(ruta_pdf, os.path.join(carpeta_otros, os.path.basename(ruta_pdf)))
        return None
    
    tipo_dte = match_control.group(1)
    numero_control = match_control.group(0).upper()
    
    # Atajo de Rendimiento
    if tipo_dte not in ["03", "05", "06", "14"]:
        doc.close()
        if os.path.exists(ruta_pdf):
            shutil.move(ruta_pdf, os.path.join(carpeta_otros, os.path.basename(ruta_pdf)))
        return None
        
    # Paso 3: Extracción Profunda
    uuid = None
    
    # Identidad: pyzbar (opera sobre la imagen, no afectado por texto_normalizado)
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image = Image.open(io.BytesIO(image_bytes))
            decoded = decode(image)
            for d in decoded:
                data = d.data.decode('utf-8')
                qr_match = re.search(r"([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})", data)
                if qr_match:
                    uuid = qr_match.group(1).upper()
                    break
        except Exception:
            continue
        if uuid:
            break
            
    # Si pyzbar falla, buscamos en el texto
    if not uuid:
        match_uuid = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", texto_normalizado)
        if match_uuid:
            uuid = match_uuid.group(1).upper()

    # Sello de Recepción
    sello = ""
    match_sello = re.search(r"sello.*?([a-z0-9]{40})", texto_normalizado)
    if match_sello:
        sello = match_sello.group(1).upper()

    # Proveedor: Extraer el NIT, Nombre y NRC
    match_nit = re.search(r"nit[:\s]+([\d-]+)", texto_normalizado)
    nit = match_nit.group(1).replace("-", "") if match_nit else ""
    
    match_nrc = re.search(r"nrc[:\s]+([\d-]+)", texto_normalizado)
    nrc = match_nrc.group(1).replace("-", "") if match_nrc else ""
    
    match_nombre = re.search(r"(?:nombre|señores|raz[óo]n social)[:\s]+([a-z0-9\s,.]+)", texto_normalizado)
    nombre = match_nombre.group(1).strip().upper() if match_nombre else ""
        
    # Financieros (ya operaba con ?i, pero simplificamos)
    match_total = re.search(r"(?:total a pagar|venta total|monto total de la operaci[óo]n)[:\s\|]*(?:us|usd|\$)?\s*([\d,]+\.\d{2})", texto_normalizado)
    match_subtotal = re.search(r"(?:sub-?total(?: de operaciones)?|suma total de operaciones)[:\s\|]*(?:us|usd|\$)?\s*([\d,]+\.\d{2})", texto_normalizado)
    match_iva = re.search(r"(?:impuesto al valor agregado(?: 13%)?|iva(?: 13%)?)[:\s\|]*(?:us|usd|\$)?\s*([\d,]+\.\d{2})", texto_normalizado)
    match_perci = re.search(r"(?:\(\+\)\s*)?(?:iva percibido(?: 1%)?)[:\s\|]*(?:us|usd|\$)?\s*([\d,]+\.\d{2})", texto_normalizado)
    
    total = float(match_total.group(1).replace(",", "")) if match_total else 0.0
    subtotal = float(match_subtotal.group(1).replace(",", "")) if match_subtotal else 0.0
    iva = float(match_iva.group(1).replace(",", "")) if match_iva else 0.0
    perci = float(match_perci.group(1).replace(",", "")) if match_perci else 0.0
    
    # Fecha de Emision (Bilingüe)
    fec_emi = ""
    match_fecha_iso = re.search(r"(\d{4}-\d{2}-\d{2})", texto_normalizado)
    if match_fecha_iso:
        fec_emi = match_fecha_iso.group(1)
    else:
        match_fecha_es = re.search(r"(\d{2})[/.-](\d{2})[/.-](\d{4})", texto_normalizado)
        if match_fecha_es:
            # Reordenar DD-MM-YYYY a YYYY-MM-DD
            fec_emi = f"{match_fecha_es.group(3)}-{match_fecha_es.group(2)}-{match_fecha_es.group(1)}"

    # === Respaldo: Extracción con Tablas ===
    if not fec_emi or not nit or not nrc or not nombre:
        try:
            for tabla in page.find_tables():
                for fila in tabla.extract():
                    for celda in fila:
                        if not celda: continue
                        celda_norm = str(celda).lower().replace("\n", " ").strip()
                        
                        if not fec_emi and ("mes" in celda_norm or "año" in celda_norm or "fecha" in celda_norm):
                            m_fiso = re.search(r"(\d{4}-\d{2}-\d{2})", celda_norm)
                            if m_fiso:
                                fec_emi = m_fiso.group(1)
                            else:
                                m_fes = re.search(r"(\d{2})[/.-](\d{2})[/.-](\d{4})", celda_norm)
                                if m_fes:
                                    fec_emi = f"{m_fes.group(3)}-{m_fes.group(2)}-{m_fes.group(1)}"
                                    
                        if not nrc and "nrc" in celda_norm:
                            m_nrc = re.search(r"nrc[:\s]*([\d-]+)", celda_norm)
                            if m_nrc: nrc = m_nrc.group(1).replace("-", "")
                            
                        if not nit and "nit" in celda_norm:
                            m_nit = re.search(r"nit[:\s]*([\d-]+)", celda_norm)
                            if m_nit: nit = m_nit.group(1).replace("-", "")
                            
                        if not nombre and ("nombre" in celda_norm or "señores" in celda_norm or "razón" in celda_norm or "razon" in celda_norm):
                            m_nom = re.search(r"(?:nombre|señores|raz[óo]n social)[:\s]+([a-z0-9\s,.]+)", celda_norm)
                            if m_nom: nombre = m_nom.group(1).strip().upper()
        except Exception:
            pass

    doc.close()

    # Paso 4: Salida
    # Devuelve el diccionario con la estructura JSON que espera el mapeador
    return {
        "selloRecibido": sello,
        "identificacion": {
            "codigoGeneracion": uuid or "",
            "numeroControl": numero_control,
            "tipoDte": tipo_dte,
            "fecEmi": fec_emi
        },
        "emisor": {
            "nit": nit,
            "nrc": nrc,
            "nombre": nombre
        },
        "resumen": {
            "totalGravada": subtotal,
            "tributos": [
                {"codigo": "20", "valor": iva}
            ],
            "ivaPerci": perci,
            "montoTotalOperacion": total,
            "totalCompra": total if tipo_dte == "14" else 0.0
        }
    }
