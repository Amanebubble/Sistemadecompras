import re

def extraer_plantilla_shell(texto: str) -> dict:
    """Extrae datos específicamente para facturas de SHELL (Combustible)."""
    # Validar que sea de Shell
    if "1009-250468-001-9" not in texto and "SHELL EL PEDREGAL" not in texto.upper():
        return None
        
    print("    [FAST-TRACK] Molde 'SHELL' activado.")
    
    # UUID
    match_uuid = re.search(r'([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})', texto)
    uuid_val = match_uuid.group(1).upper() if match_uuid else ""
    
    # Control
    match_control = re.search(r'(DTE-03-[A-Z0-9]+-\d{15})', texto)
    control_val = match_control.group(1).upper() if match_control else ""
    
    # Fecha
    match_fecha = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
    fecha_val = match_fecha.group(1) if match_fecha else ""
    
    # Monto Total de la Operación
    match_total = re.search(r'Monto Total de la Operaci.n[:\s\$]*([\d,]+\.\d{2})', texto, re.IGNORECASE)
    total_val = float(match_total.group(1).replace(',', '')) if match_total else 0.0
    
    # IVA
    match_iva = re.search(r'IVA 13%[:\s\)\$]*([\d,]+\.\d{2})', texto, re.IGNORECASE)
    iva_val = float(match_iva.group(1).replace(',', '')) if match_iva else 0.0
    
    # FOVIAL ($0.20)
    match_fovial = re.search(r'FOVIAL.*?:[\s\$]*([\d,]+\.\d{2})', texto, re.IGNORECASE)
    fovial_val = float(match_fovial.group(1).replace(',', '')) if match_fovial else 0.0
    
    # COTRANS ($0.10)
    match_cotrans = re.search(r'COTRANS.*?:[\s\$]*([\d,]+\.\d{2})', texto, re.IGNORECASE)
    cotrans_val = float(match_cotrans.group(1).replace(',', '')) if match_cotrans else 0.0
    
    subtotal = total_val - iva_val - fovial_val - cotrans_val
    if subtotal < 0: subtotal = 0.0
    
    # Sello
    match_sello = re.search(r'Sello de Recepci.n[:\s]*([A-Z0-9]{30,45})', texto, re.IGNORECASE)
    sello_val = match_sello.group(1) if match_sello else ""
    
    return {
        "identificacion": {
            "codigoGeneracion": uuid_val,
            "numeroControl": control_val,
            "fecEmi": fecha_val,
            "tipoDte": "03"
        },
        "emisor": {
            "nrc": "222458-2",
            "nit": "1009-250468-001-9",
            "nombre": "RODRIGUEZ DURAN, ALFREDO ANTONIO (SHELL)"
        },
        "receptor": {
            "nombre": "TRANSPORTES EJECUTIVOS SHALOM,S.A DE C.V."
        },
        "resumen": {
            "montoTotalOperacion": total_val,
            "totalCompra": subtotal,
            "ivaPerci1": 0.0,
            "ivaRete1": 0.0,
            "tributos": [
                {"codigo": "20", "valor": iva_val},
                {"codigo": "D1", "valor": fovial_val},
                {"codigo": "D4", "valor": cotrans_val}
            ]
        },
        "selloRecibido": sello_val,
        "estado_revision": "VALIDO",
        "texto_crudo": "Extraído por Molde Fast-Track SHELL"
    }

def extraer_plantilla_intelfon(texto: str) -> dict:
    """Extrae datos específicamente para facturas de INTELFON (Red)."""
    # Validar que sea de Intelfon
    if "0614-160498-104-7" not in texto and "INTELFON" not in texto.upper():
        return None
        
    print("    [FAST-TRACK] Molde 'INTELFON' activado.")
    
    # UUID
    match_uuid = re.search(r'([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})', texto)
    uuid_val = match_uuid.group(1).upper() if match_uuid else ""
    
    # Control
    match_control = re.search(r'(DTE-03-[A-Z0-9]+-\d{15})', texto)
    control_val = match_control.group(1).upper() if match_control else ""
    
    # Fecha (buscamos FECHA DE EMISION o fecha sola)
    match_fecha = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
    fecha_val = match_fecha.group(1) if match_fecha else ""
    
    # Total de la Factura del mes (NO el saldo a pagar)
    match_total = re.search(r'Total Factura del Mes[\s\$]*([\d,]+\.\d{2})', texto, re.IGNORECASE)
    if not match_total:
        match_total = re.search(r'Total Facturado[\s\$]*([\d,]+\.\d{2})', texto, re.IGNORECASE)
    total_val = float(match_total.group(1).replace(',', '')) if match_total else 0.0
    
    # IVA
    match_iva = re.search(r'IVA[\s\$]*([\d,]+\.\d{2})', texto, re.IGNORECASE)
    iva_val = float(match_iva.group(1).replace(',', '')) if match_iva else 0.0
    
    subtotal = total_val - iva_val
    if subtotal < 0: subtotal = 0.0
    
    # Sello
    match_sello = re.search(r'Sello de recepci.n\s*[:=]\s*([A-Z0-9]{30,45})', texto, re.IGNORECASE)
    sello_val = match_sello.group(1) if match_sello else ""
    
    return {
        "identificacion": {
            "codigoGeneracion": uuid_val,
            "numeroControl": control_val,
            "fecEmi": fecha_val,
            "tipoDte": "03"
        },
        "emisor": {
            "nrc": "110924-3",
            "nit": "0614-160498-104-7",
            "nombre": "INTELFON, S.A. de C.V."
        },
        "receptor": {
            "nombre": "TRANSPORTES EJECUTIVOS SHALOM,S.A DE C.V."
        },
        "resumen": {
            "montoTotalOperacion": total_val,
            "totalCompra": subtotal,
            "ivaPerci1": 0.0,
            "ivaRete1": 0.0,
            "tributos": [
                {"codigo": "20", "valor": iva_val}
            ]
        },
        "selloRecibido": sello_val,
        "estado_revision": "VALIDO",
        "texto_crudo": "Extraído por Molde Fast-Track INTELFON"
    }

def procesar_con_plantillas(texto: str) -> dict:
    """Punto de entrada para probar todas las plantillas. Retorna el JSON si hubo un 'match' exitoso, o None."""
    # 1. SHELL
    resultado = extraer_plantilla_shell(texto)
    if resultado:
        return resultado
        
    # 2. INTELFON
    resultado = extraer_plantilla_intelfon(texto)
    if resultado:
        return resultado
        
    return None
