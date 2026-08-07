import sqlite3
from datetime import datetime

class ArchivadorSQL:
    def __init__(self, ruta_bd: str):
        self.ruta_bd = ruta_bd
        self._inicializar_bd()

    def _inicializar_bd(self):
        conn = sqlite3.connect(self.ruta_bd)
        cursor = conn.cursor()
        
        # Crear tabla libro_compras si no existe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS libro_compras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT,
                ano INTEGER,
                mes INTEGER,
                fecha_emision TEXT,
                codigo_generacion TEXT UNIQUE,
                nrc TEXT,
                nit_dui TEXT,
                proveedor TEXT,
                compras_sujetos_excluidos REAL,
                fovial_cotrans_cesc REAL,
                compras_exentas_internas REAL,
                compras_exentas_importaciones REAL,
                compras_gravadas_internas REAL,
                compras_gravadas_importaciones REAL,
                iva_credito_fiscal REAL,
                iva_percibido REAL,
                total_compras REAL,
                impuesto_002 REAL,
                impuesto_retenido REAL,
                compras_no_sujetas REAL,
                sello_recepcion TEXT,
                numero_control TEXT,
                tipo_operacion TEXT,
                clasificacion TEXT,
                tipo_costo_gasto TEXT,
                concepto_iva TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    def _parsear_fecha(self, fecha_str):
        try:
            dt = datetime.strptime(fecha_str[:10], "%Y-%m-%d")
            return dt.year, dt.month
        except Exception:
            return datetime.now().year, datetime.now().month

    def guardar(self, datos: dict):
        meta = datos.get("metadatos_sistema", {})
        doc = datos.get("datos_documento", {})
        prov = datos.get("datos_proveedor", {})
        fin = datos.get("detalle_financiero", {})
        
        fecha_emision = doc.get("fecha_emision", "")
        ano, mes = self._parsear_fecha(fecha_emision)
        
        cliente = meta.get("cliente_asignado", "Desconocido")
        codigo_generacion = meta.get("codigo_generacion", "")
        nrc = prov.get("nrc", "")
        nit_dui = prov.get("nit") or prov.get("dui_sujeto_excluido") or ""
        proveedor = prov.get("nombre_razon_social", "")
        sello = meta.get("sello_recepcion", "")
        control = meta.get("numero_control", "")
        
        sujetos_excluidos = fin.get("compras_sujetos_excluidos", 0.0)
        
        imp_esp = fin.get("impuestos_especificos", {})
        fovial = imp_esp.get("fovial", 0.0)
        cotrans = imp_esp.get("cotrans", 0.0)
        cesc = imp_esp.get("cesc", 0.0)
        fovial_cotrans_cesc = round(fovial + cotrans + cesc, 2)
        
        exentas = fin.get("compras_exentas", {})
        exentas_internas = exentas.get("internas", 0.0)
        exentas_imp = exentas.get("importaciones", 0.0)
        
        gravadas = fin.get("compras_gravadas", {})
        gravadas_internas = gravadas.get("internas", 0.0)
        gravadas_imp = gravadas.get("importaciones", 0.0)
        
        iva_credito = fin.get("iva_credito_fiscal", 0.0)
        iva_percibido = fin.get("iva_percibido", 0.0)
        total = fin.get("total_compras", 0.0)
        imp_002 = imp_esp.get("impuestos_002", 0.0)
        imp_retenido = fin.get("impuesto_retenido_terceros", 0.0)
        no_sujetas = fin.get("compras_no_sujetas", 0.0)
        
        tipo_operacion = "1 Gravada" if gravadas_internas > 0 else ("2 No Gravada o Exenta" if exentas_internas > 0 else "")
        clasificacion = ""
        tipo_costo = ""
        concepto_iva = f"IVA CCF {codigo_generacion[:18]}" if iva_credito > 0 else ""
        
        conn = sqlite3.connect(self.ruta_bd)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO libro_compras (
                    cliente, ano, mes, fecha_emision, codigo_generacion, nrc, nit_dui, proveedor,
                    compras_sujetos_excluidos, fovial_cotrans_cesc, compras_exentas_internas,
                    compras_exentas_importaciones, compras_gravadas_internas, compras_gravadas_importaciones,
                    iva_credito_fiscal, iva_percibido, total_compras, impuesto_002, impuesto_retenido,
                    compras_no_sujetas, sello_recepcion, numero_control, tipo_operacion, clasificacion,
                    tipo_costo_gasto, concepto_iva
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cliente, ano, mes, fecha_emision, codigo_generacion, nrc, nit_dui, proveedor,
                sujetos_excluidos, fovial_cotrans_cesc, exentas_internas, exentas_imp,
                gravadas_internas, gravadas_imp, iva_credito, iva_percibido, total,
                imp_002, imp_retenido, no_sujetas, sello, control, tipo_operacion,
                clasificacion, tipo_costo, concepto_iva
            ))
            conn.commit()
            print(f"  -> [ArchivadorSQL] Guardado en BD: {codigo_generacion}")
        except sqlite3.IntegrityError:
            print(f"  -> [ArchivadorSQL] Ignorado (Ya existe): {codigo_generacion}")
            pass
        finally:
            conn.close()

