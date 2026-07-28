"""
Mapeador Fast Path: JSON nativo de DTE → plantilla estandarizada.

Toma un diccionario ya parseado de un JSON DTE de Hacienda El Salvador
y lo transforma al esquema plano definido en plantilla_dte.json.

Correcciones aplicadas tras validación contra archivos reales:
  - resumen.ivaCredito       NO EXISTE → IVA 13% viene en resumen.tributos (codigo "20")
  - resumen.ivaPercibido     NO EXISTE → es ivaPerci1 (v3) o ivaPerci (v4)
  - resumen.ivaRetenido      NO EXISTE → es ivaRete1 (v3) o ivaRete (v4)
  - resumen.totalCompra      NO EXISTE en tipo 03 → solo existe en tipo 14 (sujeto excluido)
  - selloRecibido            ubicación variable → root o responseMH.selloRecibido
  - FOVIAL/COTRANS/CESC      vienen en resumen.tributos[] por código, no como campo plano
"""


def _safe_float(value, default=0.00):
    """Convierte a float con fallback seguro."""
    if value is None:
        return default
    try:
        return round(float(value), 2)
    except (ValueError, TypeError):
        return default


def _extraer_tributo(tributos, codigo):
    """Extrae el valor de un tributo específico del array resumen.tributos.

    Args:
        tributos: Lista de dicts con keys 'codigo' y 'valor', o None.
        codigo: Código del tributo a buscar (ej: "20", "C8", "D1", "D4").

    Returns:
        float del valor encontrado, o 0.00 si no existe.
    """
    if not tributos or not isinstance(tributos, list):
        return 0.00
    for tributo in tributos:
        if isinstance(tributo, dict) and str(tributo.get("codigo", "")) == codigo:
            return _safe_float(tributo.get("valor"))
    return 0.00


def _extraer_sello_recibido(data_dte):
    """Busca recursivamente cualquier llave que contenga 'sello' y captura su valor (>= 30 chars)."""
    def buscar_sello(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if "sello" in str(k).lower():
                    if isinstance(v, str) and len(v) >= 30:
                        return v.upper()
                res = buscar_sello(v)
                if res:
                    return res
        elif isinstance(obj, list):
            for item in obj:
                res = buscar_sello(item)
                if res:
                    return res
        return ""
    
    return buscar_sello(data_dte)


def _extraer_iva_percibido(resumen):
    """Extrae IVA percibido, compatible con v3 (ivaPerci1) y v4 (ivaPerci)."""
    valor = resumen.get("ivaPerci1")
    if valor is None:
        valor = resumen.get("ivaPerci")
    return _safe_float(valor)


def _extraer_iva_retenido(resumen):
    """Extrae IVA retenido, compatible con v3 (ivaRete1) y v4 (ivaRete)."""
    valor = resumen.get("ivaRete1")
    if valor is None:
        valor = resumen.get("ivaRete")
    return _safe_float(valor)


def mapear_a_plantilla(data_dte: dict, origen: str, nombre_cliente_limpio: str = "Desconocido") -> dict:
    """Mapea un DTE parseado al esquema estandarizado."""
    ident = data_dte.get("identificacion", {})
    emisor = data_dte.get("emisor", {})
    receptor = data_dte.get("receptor", {})
    resumen = data_dte.get("resumen", {})
    tributos = resumen.get("tributos")  # list | None

    # DTE-05 (Nota de Crédito) → montos negativos para auto-cuadrar en Excel
    tipo_dte = str(ident.get("tipoDte", ""))
    signo = -1 if tipo_dte == "05" else 1

    return {
        "metadatos_sistema": {
            "codigo_generacion": ident.get("codigoGeneracion", ""),
            "sello_recepcion": _extraer_sello_recibido(data_dte),
            "numero_control": ident.get("numeroControl", ""),
            "origen_datos": origen,
            "cliente_asignado": nombre_cliente_limpio,
        },
        "datos_documento": {
            "fecha_emision": ident.get("fecEmi", ""),
            "tipo_documento": tipo_dte,
        },
        "datos_proveedor": {
            "nrc": emisor.get("nrc", ""),
            "nit": emisor.get("nit", ""),
            "dui_sujeto_excluido": emisor.get("dui"),  # None si no aplica
            "nombre_razon_social": emisor.get("nombre", ""),
        },
        "datos_cliente": {
            "nombre_razon_social": receptor.get("nombre", ""),
        },
        "detalle_financiero": {
            "compras_sujetos_excluidos": signo * _safe_float(
                resumen.get("totalCompra")
            ),
            "compras_exentas": {
                "internas": signo * _safe_float(resumen.get("totalExenta")),
                "importaciones": 0.00,
            },
            "compras_gravadas": {
                "internas": signo * _safe_float(resumen.get("totalGravada")),
                "importaciones": 0.00,
            },
            "iva_credito_fiscal": signo * _extraer_tributo(tributos, "20"),
            "iva_percibido": signo * _extraer_iva_percibido(resumen),
            "impuestos_especificos": {
                "fovial": signo * _extraer_tributo(tributos, "D1"),
                "cotrans": signo * _extraer_tributo(tributos, "D4"),
                "cesc": signo * _extraer_tributo(tributos, "C8"),
                "impuestos_002": signo * _extraer_tributo(tributos, "59"),
            },
            "impuesto_retenido_terceros": signo * _extraer_iva_retenido(resumen),
            "compras_no_sujetas": signo * _safe_float(resumen.get("totalNoSuj")),
            "total_compras": signo * _safe_float(
                resumen.get("montoTotalOperacion")
            ),
        },
    }

