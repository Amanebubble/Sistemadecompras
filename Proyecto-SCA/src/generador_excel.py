import sqlite3
import pandas as pd
from pathlib import Path
import os
from src.config import RUTA_BD_CONTROL, CARPETA_REPORTES

class GeneradorExcel:
    def __init__(self, ruta_bd: str = str(RUTA_BD_CONTROL), carpeta_salida: str = str(CARPETA_REPORTES)):
        self.ruta_bd = ruta_bd
        self.carpeta_salida = Path(carpeta_salida)
        self.carpeta_salida.mkdir(parents=True, exist_ok=True)

    def generar_reporte(self, cliente: str = None, ano: int = None, mes: int = None):
        conn = sqlite3.connect(self.ruta_bd)
        
        query = "SELECT * FROM libro_compras WHERE 1=1"
        params = []
        
        if cliente:
            query += " AND cliente = ?"
            params.append(cliente)
        if ano:
            query += " AND ano = ?"
            params.append(ano)
        if mes:
            query += " AND mes = ?"
            params.append(mes)
            
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            print(f"[GeneradorExcel] No hay datos para generar el reporte de {cliente} {ano}-{mes}")
            return None
            
        # Renombrar columnas para que coincidan con el LIBRO DE COMPRAS
        columnas_formato = {
            "id": "No. Correlativo",
            "fecha_emision": "Fecha de Emision",
            "codigo_generacion": "CODIGO DE GENERACION",
            "nrc": "N.R.C.",
            "nit_dui": "NIT,CIP,DUI del Sujeto Excluido",
            "proveedor": "Nombre del Proveedor",
            "compras_sujetos_excluidos": "Compras a Sujetos Excluidos",
            "fovial_cotrans_cesc": "FOVIAL/ COTRANS/ CESC",
            "compras_exentas_internas": "COMPRAS EXENTAS - Internas",
            "compras_exentas_importaciones": "COMPRAS EXENTAS - Importaciones",
            "compras_gravadas_internas": "COMPRAS GRAVADAS - Internas",
            "compras_gravadas_importaciones": "COMPRAS GRAVADAS - Importaciones",
            "iva_credito_fiscal": "Credito Fiscal",
            "iva_percibido": "IVA Percibido",
            "total_compras": "TOTAL Compras",
            "impuesto_002": "Impuesto 0.02",
            "impuesto_retenido": "Impuesto Retenido a Terceros",
            "compras_no_sujetas": "COMPRAS NO SUJETAS",
            "sello_recepcion": "SERIE / SELLO DE RECEPCION",
            "numero_control": "No DE CONTROL /RESOLUCION",
            "tipo_operacion": "TIPO DE OPERACION",
            "clasificacion": "CLASIFICACION",
            "tipo_costo_gasto": "TIPO DE COSTO /GASTO",
            "concepto_iva": "CONCEPTO IVA"
        }
        
        df_export = df.rename(columns=columnas_formato)
        columnas_ordenadas = [col for col in columnas_formato.values() if col in df_export.columns]
        df_export = df_export[columnas_ordenadas]
        
        # --- Lógica de Base de Datos de Referencia (Fallback de Proveedores) ---
        ruta_base_ref = Path(__file__).parent.parent / "2026 06 - JC FOOD SERVICE LIBROS DE IVA (1).xlsx"
        if ruta_base_ref.exists():
            try:
                # header=2 significa que la tercera fila (índice 2) tiene las cabeceras reales
                df_ref = pd.read_excel(str(ruta_base_ref), sheet_name="CLIENTES Y PROVEEDORES", header=2)
                
                mapa_nrc = {}
                mapa_nit = {}
                
                if "NRC" in df_ref.columns and "NOMBRE" in df_ref.columns:
                    for _, row in df_ref.dropna(subset=["NRC"]).iterrows():
                        nrc_str = str(row["NRC"]).strip()
                        nombre_str = str(row["NOMBRE"]).strip() if pd.notna(row["NOMBRE"]) else ""
                        if nrc_str and nombre_str:
                            mapa_nrc[nrc_str] = nombre_str
                            
                if "NIT" in df_ref.columns and "NOMBRE" in df_ref.columns:
                    for _, row in df_ref.dropna(subset=["NIT"]).iterrows():
                        nit_str = str(row["NIT"]).replace("-","").strip() # Normalizar NIT si es necesario
                        nombre_str = str(row["NOMBRE"]).strip() if pd.notna(row["NOMBRE"]) else ""
                        if nit_str and nombre_str:
                            mapa_nit[nit_str] = nombre_str
                
                # Aplicar relleno a los vacíos en df_export
                col_prov = "Nombre del Proveedor"
                col_nrc = "N.R.C."
                col_nit = "NIT,CIP,DUI del Sujeto Excluido"
                
                if col_prov in df_export.columns:
                    for idx, row in df_export.iterrows():
                        prov_actual = str(row[col_prov]).strip()
                        if pd.isna(row[col_prov]) or prov_actual == "" or prov_actual.lower() == "nan" or prov_actual.lower() == "none":
                            nrc = str(row.get(col_nrc, "")).strip()
                            nit = str(row.get(col_nit, "")).replace("-","").strip()
                            
                            nuevo_nombre = mapa_nrc.get(nrc) or mapa_nit.get(nit) or ""
                            if nuevo_nombre:
                                df_export.at[idx, col_prov] = nuevo_nombre
                                
            except Exception as e:
                print(f"[GeneradorExcel] Error al cruzar con BD de referencia: {e}")
        # -----------------------------------------------------------------------
        
        nombre_cliente_limpio = "".join([c if c.isalnum() else "_" for c in str(cliente)])
        
        from datetime import datetime
        fecha_descarga = datetime.now().strftime("%Y%m%d")
        nombre_archivo = f"{nombre_cliente_limpio}_{mes:02d}_{ano}_{fecha_descarga}.xlsx"
            
        ruta_archivo = self.carpeta_salida / nombre_archivo
        
        df_export.to_excel(ruta_archivo, index=False, sheet_name="LIBRO IVA COMPRA")
        print(f"[GeneradorExcel] Reporte generado exitosamente: {ruta_archivo}")
        return str(ruta_archivo)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generar Libro de Compras en Excel")
    parser.add_argument("--cliente", type=str, help="Nombre del cliente")
    parser.add_argument("--ano", type=int, help="Año")
    parser.add_argument("--mes", type=int, help="Mes")
    args = parser.parse_args()
    
    gen = GeneradorExcel()
    gen.generar_reporte(args.cliente, args.ano, args.mes)


