import os
import shutil
import glob
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DESCARGA_DOC = os.path.join(BASE_DIR, "Descarga-doc")

carpetas_estado = [
    "Procesados",
    "Respaldo_PDF",
    "Errores",
    "Otros_Documentos_Clasificados",
    "Invalidos",
    "Duplicados",
    "Historico_Procesados"
]

print("=== RESET DEL ENTORNO ===")
# 1. Vaciar historial DB
db_path = os.path.join(BASE_DIR, "filtro-service", "filtro_dte.db")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dte_procesados")
    conn.commit()
    conn.close()
    print("✓ Base de datos limpiada (filtro_dte.db)")
else:
    print("✓ Base de datos no encontrada, omitiendo.")

# 2. Restaurar archivos
os.makedirs(DESCARGA_DOC, exist_ok=True)
archivos_movidos = 0
for carpeta in carpetas_estado:
    ruta = os.path.join(BASE_DIR, carpeta)
    if os.path.exists(ruta):
        for archivo in glob.glob(os.path.join(ruta, "*")):
            if os.path.isfile(archivo):
                shutil.move(archivo, os.path.join(DESCARGA_DOC, os.path.basename(archivo)))
                archivos_movidos += 1
print(f"✓ {archivos_movidos} archivos devueltos a Descarga-doc/")

# 3. Eliminar carpetas
mineria = os.path.join(BASE_DIR, "mineria-finalizada")
if os.path.exists(mineria):
    shutil.rmtree(mineria)
    print("✓ Carpeta mineria-finalizada/ eliminada por completo")

print("Reset finalizado. Entorno listo para la prueba.")
