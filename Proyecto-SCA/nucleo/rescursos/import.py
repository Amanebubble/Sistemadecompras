import requests
import pprint
import os
import json
from typing import Dict, Any, Optional
import pandas as pd

# --- Constantes ---
URL_CONSULTA_DTE = "https://admin.factura.gob.sv/prod/consultas/publica/simple/1"
AMBIENTE_PRODUCCION = "01"
# NIT de la empresa para la cual estamos procesando los documentos.
# Este es el dato clave para saber si es una compra o una venta.
# Lo he extraído de los JSON de ejemplo que me proporcionaste.
NIT_CLIENTE_PROPIO = "13271603261014"

# Headers para simular un navegador real y evitar bloqueos
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://admin.factura.gob.sv/consultaPublica"
}

# Diccionario para traducir los códigos de tipo de DTE a un formato legible.
DTE_TIPO_DOCUMENTO = {
    "01": "Factura",
    "03": "Comprobante de Crédito Fiscal",
    "04": "Nota de Remisión",
    "05": "Nota de Crédito",
    "06": "Nota de Débito",
    "07": "Comprobante de Retención",
    "11": "Factura de Exportación",
}


def consultar_dte_hacienda_real(codigo_generacion: str, fecha_emision: str) -> Optional[Dict[str, Any]]:
    """
    Consulta un Documento Tributario Electrónico (DTE) en el servicio web de Hacienda de El Salvador.
    Maneja respuestas JSON directas y respuestas HTML que contienen el JSON.
    Args:
        codigo_generacion: El código de generación único del DTE.
        fecha_emision: La fecha de emisión del DTE en formato 'YYYY-MM-DD'.

    Returns:
        Un diccionario con los datos del DTE si la consulta es exitosa (código 200).
        None si ocurre un error o si el DTE no es encontrado.
    """
    params = {
        "codigoGeneracion": codigo_generacion,
        "fechaEmi": fecha_emision,
        "ambiente": AMBIENTE_PRODUCCION
    }
    try:
        print(f"Consultando DTE en Hacienda: {codigo_generacion}...")
        with requests.Session() as session:
            respuesta = session.get(URL_CONSULTA_DTE, params=params, headers=HEADERS, timeout=15)

        print(f"Código de estado HTTP devuelto: {respuesta.status_code}")
        respuesta.raise_for_status()  # Lanza una excepción para códigos de error HTTP (4xx o 5xx)

        data = None
        try:
            # Intento 1: Asumir que la respuesta es JSON puro.
            data = respuesta.json()
        except json.JSONDecodeError:
            # Intento 2: Si falla, puede ser HTML con JSON dentro de <pre>, como lo observaste.
            print("  ↳ ⚠️  La respuesta no es JSON puro. Intentando extraer de posible HTML...")
            texto_respuesta = respuesta.text
            if "<pre>" in texto_respuesta and "</pre>" in texto_respuesta:
                try:
                    inicio = texto_respuesta.find("<pre>") + len("<pre>")
                    fin = texto_respuesta.find("</pre>", inicio)
                    json_texto = texto_respuesta[inicio:fin].strip()
                    data = json.loads(json_texto)
                    print("  ↳ ✅ Extracción de JSON desde HTML exitosa.")
                except json.JSONDecodeError:
                    print(f"  ↳ ❌ El contenido dentro de <pre> no es un JSON válido: {json_texto[:200]}...")
                    return None
            else:
                print("  ↳ ❌ La respuesta no es JSON y no se encontró la estructura <pre> esperada.")
                return None

        # Ahora validamos la estructura del JSON de la API de Hacienda.
        if data and data.get("status") == "OK" and "body" in data and data["body"]:
            return data["body"]  # Devolvemos solo el DTE
        else:
            print(f"  ↳ ⚠️  Hacienda respondió OK, pero el DTE no fue encontrado en el cuerpo de la respuesta.")
            return None

    except requests.exceptions.Timeout:
        print("❌ Error: La solicitud a Hacienda tardó demasiado tiempo en responder (timeout).")
    except requests.exceptions.HTTPError as e:
        print(f"❌ Error HTTP. El servidor respondió con código: {e.response.status_code}")
        print(f"   Detalle: {e.response.text[:300]}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión con el servidor de Hacienda: {e}")

    return None


def clasificar_documento(dte_data: Dict[str, Any], nit_propio: str) -> Dict[str, str]:
    """
    Clasifica un DTE, determinando el tipo de operación y el tipo de documento.

    Args:
        dte_data: El diccionario con los datos del DTE.
        nit_propio: El NIT de la empresa cliente para la clasificación.

    Returns:
        Un diccionario con la 'operacion' (Compra/Venta) y el 'tipo_documento'.
    """
    clasificacion = {}

    # 1. Clasificar Operación (Compra/Venta)
    nit_emisor = dte_data.get("emisor", {}).get("nit")
    nit_receptor = dte_data.get("receptor", {}).get("nit")

    if nit_receptor == nit_propio:
        clasificacion["operacion"] = "Compra"
    elif nit_emisor == nit_propio:
        clasificacion["operacion"] = "Venta"
    else:
        clasificacion["operacion"] = "Desconocido"

    # 2. Clasificar Tipo de Documento
    tipo_dte_codigo = dte_data.get("identificacion", {}).get("tipoDte")
    clasificacion["tipo_documento"] = DTE_TIPO_DOCUMENTO.get(tipo_dte_codigo, f"Código Desconocido ({tipo_dte_codigo})")

    return clasificacion

def extraer_datos_para_libro_compras(dte_data: Dict[str, Any], clasificacion: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Extrae y formatea los datos de un DTE para una fila del libro de compras.
    Maneja Notas de Crédito aplicando valores negativos.

    Args:
        dte_data: El diccionario con los datos del DTE.
        clasificacion: El diccionario de clasificación del documento.

    Returns:
        Un diccionario que representa una fila para el DataFrame de Pandas.
    """
    if clasificacion.get("operacion") != "Compra":
        return None

    # Las Notas de Crédito restan, por lo tanto, sus valores son negativos.
    signo = -1 if clasificacion.get("tipo_documento") == "Nota de Crédito" else 1

    resumen = dte_data.get("resumen", {})
    emisor = dte_data.get("emisor", {})
    identificacion = dte_data.get("identificacion", {})

    # Extraer tributos de forma segura
    credito_fiscal = 0
    fovial = 0
    cotrans = 0
    for tributo in resumen.get("tributos", []):
        if tributo.get("codigo") == "20": # IVA 13%
            credito_fiscal = tributo.get("valor", 0)
        elif tributo.get("codigo") == "D1": # FOVIAL
            fovial = tributo.get("valor", 0)
        elif tributo.get("codigo") == "C8": # COTRANS
            cotrans = tributo.get("valor", 0)

    fila = {
        "Fecha de Emisión": identificacion.get("fecEmi"),
        "Codigo de Generacion": identificacion.get("codigoGeneracion"),
        "NIT Proveedor": emisor.get("nit"),
        "Nombre del Proveedor": emisor.get("nombre"),
        "Compras Internas Exentas": resumen.get("totalExenta", 0) * signo,
        "Importaciones e Internaciones Exentas": 0.0, # Placeholder, no está en el DTE estándar
        "Compras Internas Gravadas": resumen.get("totalGravada", 0) * signo,
        "Credito Fiscal (IVA 13%)": credito_fiscal * signo,
        "Anticipo a cuenta IVA Percibido": resumen.get("ivaPerci1", 0) * signo,
        "FOVIAL": fovial * signo,
        "COTRANS": cotrans * signo,
        "Total Compra": resumen.get("montoTotalOperacion", 0) * signo,
    }

    return fila


def procesar_directorio_json(ruta_directorio: str) -> Optional[pd.DataFrame]:
    """
    Recorre un directorio, lee todos los archivos .json, extrae los datos
    necesarios y consulta el DTE en Hacienda.

    Args:
        ruta_directorio: La ruta a la carpeta que contiene los archivos JSON.
    """
    # Listas para almacenar los datos de cada libro
    filas_compras = []
    # En el futuro, aquí irían las listas para otros libros (ventas, etc.)

    # Crear el directorio para facturas no procesadas si no existe
    dir_invalidas = os.path.join(os.path.dirname(os.path.abspath(ruta_directorio)), "Facturas_Invalidas")
    os.makedirs(dir_invalidas, exist_ok=True)

    print(f"\n--- Iniciando procesamiento del directorio: {ruta_directorio} ---\n")

    # 1. Leer, consultar y clasificar cada archivo JSON
    for nombre_archivo in os.listdir(ruta_directorio):
        if nombre_archivo.endswith(".json"):
            ruta_completa = os.path.join(ruta_directorio, nombre_archivo)
            print(f"Procesando archivo: {nombre_archivo}")
            try:
                with open(ruta_completa, 'r', encoding='utf-8-sig') as f:
                    # Usamos utf-8-sig para manejar el posible BOM (Byte Order Mark) al inicio del archivo
                    dte_local = json.load(f)

                # Extraer datos del JSON local
                codigo_generacion = dte_local.get("identificacion", {}).get("codigoGeneracion")
                fecha_emision = dte_local.get("identificacion", {}).get("fecEmi")

                if not codigo_generacion or not fecha_emision:
                    print(f"  ↳ ⚠️  No se encontró 'codigoGeneracion' o 'fecEmi' en {nombre_archivo}. Saltando.")
                    continue

                # Consultar a Hacienda con los datos extraídos
                datos_oficiales = consultar_dte_hacienda_real(codigo_generacion, fecha_emision)

                # Si Hacienda no devolvió un DTE válido, movemos el archivo y continuamos.
                if not datos_oficiales:
                    print(f"  ↳ ❌ No se pudo validar en Hacienda. Moviendo archivo a '{os.path.basename(dir_invalidas)}'.")
                    ruta_destino = os.path.join(dir_invalidas, nombre_archivo)
                    try:
                        # Usamos rename para mover el archivo
                        os.rename(ruta_completa, ruta_destino)
                    except OSError as e:
                        print(f"    ↳ ❌ Error al mover el archivo: {e}")
                    continue # Pasamos al siguiente archivo

                print("  ↳ ✅ DTE obtenido y validado por Hacienda.")
                
                # --- INICIO DE LA CLASIFICACIÓN ---
                clasificacion = clasificar_documento(datos_oficiales, NIT_CLIENTE_PROPIO)
                print(f"  ↳ 📂 Clasificación: {clasificacion['operacion']} / {clasificacion['tipo_documento']}")

                # --- INICIO EXTRACCIÓN PARA LIBROS CONTABLES ---
                # Por ahora, solo manejamos el libro de compras
                if clasificacion['operacion'] == 'Compra':
                    fila_datos = extraer_datos_para_libro_compras(datos_oficiales, clasificacion)
                    if fila_datos:
                        filas_compras.append(fila_datos)
                        print("  ↳ 📊 Datos agregados al libro de compras.")
                else:
                    # Aquí iría la lógica para ventas u otros tipos
                    print("  ↳ ℹ️  Documento de venta no se procesa en el libro de compras.")

            except json.JSONDecodeError:
                print(f"  ↳ ❌ Error: El archivo {nombre_archivo} no es un JSON válido.")
            except Exception as e:
                print(f"  ↳ ❌ Ocurrió un error inesperado procesando {nombre_archivo}: {e}")
            print("-" * 20)

    # 2. Crear y devolver un diccionario de DataFrames, uno por cada libro
    dataframes = {}
    if filas_compras:
        dataframes['compras'] = pd.DataFrame(filas_compras)
    
    return dataframes


# --- Bloque de ejecución principal ---
if __name__ == "__main__":
    directorio_de_facturas = "Facturas_Nuevas"
    libros_contables = procesar_directorio_json(directorio_de_facturas)

    # Guardar cada libro en una hoja de un único archivo Excel
    if libros_contables:
        nombre_archivo_excel = "Libros_Contables.xlsx"
        with pd.ExcelWriter(nombre_archivo_excel, engine='openpyxl') as writer:
            if 'compras' in libros_contables:
                libros_contables['compras'].to_excel(writer, sheet_name='Libro de Compras', index=False)
                print("\n✅ Libro de Compras generado.")

        print(f"\n🎉 ¡Éxito! Se ha generado el archivo '{nombre_archivo_excel}' con los libros contables.")
    else:
        print("\nNo se generaron libros contables.")