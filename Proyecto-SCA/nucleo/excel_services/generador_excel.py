"""
Generador Excel: Exporta JSONs estandarizados a libros Excel agrupados por Cliente/Año/Mes.
"""

import glob
import json
import os
import re
import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime

# Raíz del proyecto: <raiz>/nucleo/excel_services/generador_excel.py -> <raiz>
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent.parent
NUCLEO_DIR = RAIZ_PROYECTO / "nucleo"

CARPETA_PROCESADOS = NUCLEO_DIR / "Procesados"
CARPETA_HISTORICO = NUCLEO_DIR / "Historico_Procesados"
CARPETA_MINERIA = RAIZ_PROYECTO / "mineria-finalizada"

def limpiar_nombre_carpeta(nombre) -> str:
    """Limpia un string para que sea un nombre de carpeta seguro en Windows."""
    if pd.isna(nombre) or not str(nombre).strip():
        return "Cliente_Desconocido"
    # Remover caracteres no permitidos en rutas Windows
    limpio = re.sub(r'[<>:"/\\|?*]', '', str(nombre))
    return limpio.strip()

def generar_reportes_agrupados():
    print("=" * 60)
    print("  EXCEL-SERVICES: Generador de Reportes Minados")
    print("=" * 60)

    # 1. Obtener todos los JSON de la carpeta Procesados
    patron_json = str(CARPETA_PROCESADOS / "*.json")
    archivos = glob.glob(patron_json)
    
    if not archivos:
        print("  No se encontraron archivos en Procesados/ para exportar.")
        return

    print(f"  > Se encontraron {len(archivos)} JSONs para procesar.")

    # 2. Leer JSONs
    datos_planos = []
    
    for ruta in archivos:
        nombre_archivo = os.path.basename(ruta)
        
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  [ERROR] No se pudo leer {nombre_archivo}: {e}")
            continue
            
        data["Ruta_Original"] = ruta # Para poder moverlo después
        datos_planos.append(data)
        
    if not datos_planos:
        print("  No se pudo extraer data válida de los JSONs.")
        return

    # 3. Aplanar todo a un DataFrame
    df = pd.json_normalize(datos_planos)
    
    # 4. Procesar Metadatos en el DataFrame (Fechas y Cliente)
    # Fecha:
    col_fecha = "datos_documento.fecha_emision"
    if col_fecha in df.columns:
        # Convertir a datetime y extraer año/mes. Si falla, queda NaT.
        fechas = pd.to_datetime(df[col_fecha], errors='coerce')
        df["Año"] = fechas.dt.strftime("%Y").fillna("0000")
        df["Mes"] = fechas.dt.strftime("%m").fillna("00")
        df[col_fecha] = fechas.dt.date
    else:
        df["Año"] = "0000"
        df["Mes"] = "00"

    # Cliente:
    col_cliente = "metadatos_sistema.cliente_asignado"
    if col_cliente in df.columns:
        df["Cliente"] = df[col_cliente].apply(limpiar_nombre_carpeta)
    else:
        df["Cliente"] = "Cliente_Desconocido"

    # 5. Agrupar y exportar
    grupos = df.groupby(["Cliente", "Año", "Mes"])
    archivos_generados = 0
    jsons_movidos = 0
    
    CARPETA_HISTORICO.mkdir(parents=True, exist_ok=True)
    
    for (cliente, año, mes), grupo_df in grupos:
        # Armar ruta dinámica
        ruta_dinamica = CARPETA_MINERIA / str(cliente) / str(año) / str(mes)
        ruta_dinamica.mkdir(parents=True, exist_ok=True)
        
        # Archivo Excel
        ruta_excel = ruta_dinamica / "compras_mineria.xlsx"
        
        # Quitamos la columna Ruta_Original para que no salga en el Excel
        df_exportar = grupo_df.drop(columns=["Ruta_Original"])
        
        try:
            # Lógica para evitar sobrescritura (Concatenar si existe)
            if ruta_excel.exists():
                df_existente = pd.read_excel(str(ruta_excel))
                df_exportar = pd.concat([df_existente, df_exportar], ignore_index=True)
                accion = "Actualizado"
            else:
                accion = "Creado"

            df_exportar.to_excel(str(ruta_excel), index=False)
            archivos_generados += 1
            print(f"  [OK] {accion}: {cliente}/{año}/{mes} -> compras_mineria.xlsx ({len(df_exportar)} filas totales)")
            
            # Mover JSONs al histórico
            rutas_origen = grupo_df["Ruta_Original"].tolist()
            for r in rutas_origen:
                if os.path.exists(r):
                    shutil.move(r, str(CARPETA_HISTORICO / os.path.basename(r)))
                    jsons_movidos += 1
        except Exception as e:
            print(f"  [ERROR] Fallo al exportar Excel para {cliente}: {e}")

    print("\n" + "=" * 60)
    print("  RESUMEN EXPORTACION EXCEL")
    print("-" * 60)
    print(f"  Excels generados:  {archivos_generados}")
    print(f"  JSONs archivados:  {jsons_movidos}")
    print("=" * 60)

if __name__ == "__main__":
    generar_reportes_agrupados()
