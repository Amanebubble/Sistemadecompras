import os, json, glob

invalidos_dir = r"C:\Users\Lenovo P52s\Desktop\Proyecto-SCA\Invalidos"
descarga_dir = r"C:\Users\Lenovo P52s\Desktop\Proyecto-SCA\Descarga-doc"

for ruta in glob.glob(os.path.join(invalidos_dir, "*.json")):
    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    if "metadatos_sistema" in data:
        native = {
            "identificacion": {
                "codigoGeneracion": data["metadatos_sistema"].get("codigo_generacion", ""),
                "numeroControl": data["metadatos_sistema"].get("numero_control", ""),
                "tipoDte": data["datos_documento"].get("tipo_documento", ""),
                "fecEmi": data["datos_documento"].get("fecha_emision", "")
            },
            "emisor": {
                "nrc": data["datos_proveedor"].get("nrc", ""),
                "nit": data["datos_proveedor"].get("nit", ""),
                "dui": data["datos_proveedor"].get("dui_sujeto_excluido", ""),
                "nombre": data["datos_proveedor"].get("nombre_razon_social", "")
            },
            "receptor": {},
            "resumen": {
                "totalCompra": data["detalle_financiero"].get("compras_sujetos_excluidos", 0.0),
                "totalExenta": data["detalle_financiero"].get("compras_exentas", {}).get("internas", 0.0),
                "totalGravada": data["detalle_financiero"].get("compras_gravadas", {}).get("internas", 0.0),
                "montoTotalOperacion": data["detalle_financiero"].get("total_compras", 0.0),
                "tributos": [{"codigo": "20", "valor": data["detalle_financiero"].get("iva_credito_fiscal", 0.0)}]
            },
            "selloRecibido": data["metadatos_sistema"].get("sello_recepcion", "")
        }
        
        # Guardar en Descarga-doc
        nombre_base = os.path.basename(ruta)
        with open(os.path.join(descarga_dir, nombre_base), "w", encoding="utf-8") as f2:
            json.dump(native, f2, ensure_ascii=False)
        os.remove(ruta)
