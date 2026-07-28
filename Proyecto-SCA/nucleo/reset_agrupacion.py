import os
import shutil
import glob
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

carpetas_estado = [
    "Procesados",
    "Respaldo_PDF",
    "Errores",
    "Otros_Documentos_Clasificados",
    "Invalidos",
    "Duplicados"
]

print("=== RESET DE AGRUPACION ===")
# 1. Vaciar historial DB
db_path = os.path.join(BASE_DIR, "filtro-service", "filtro_dte.db")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dte_procesados")
    conn.commit()
    conn.close()
    print("\u2713 Base de datos limpiada (filtro_dte.db)")
else:
    print("\u2713 Base de datos no encontrada, omitiendo.")

# 2. Eliminar archivos en carpetas de estado
archivos_eliminados = 0
for carpeta in carpetas_estado:
    ruta = os.path.join(BASE_DIR, carpeta)
    if os.path.exists(ruta):
        for archivo in glob.glob(os.path.join(ruta, "*")):
            if os.path.isfile(archivo):
                os.remove(archivo)
                archivos_eliminados += 1
print(f"\u2713 {archivos_eliminados} archivos eliminados de las carpetas de estado.")

# 3. Eliminar carpeta dinámica mineria-finalizada
mineria = os.path.join(BASE_DIR, "mineria-finalizada")
if os.path.exists(mineria):
    shutil.rmtree(mineria, ignore_errors=True)
    print("\u2713 Carpeta mineria-finalizada/ eliminada por completo")

print("Reset de agrupación finalizado. Descarga-doc/ se mantuvo intacto.")
