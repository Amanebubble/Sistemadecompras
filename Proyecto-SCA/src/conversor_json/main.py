import sys
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent.parent
NUCLEO_DIR = RAIZ_PROYECTO / "nucleo"

# Añadir el directorio propio al sys.path para importar correctamente el mapeador
sys.path.append(str(Path(__file__).resolve().parent))

from .estandarizador import Estandarizador

def main():
    carpeta_cola0 = NUCLEO_DIR / "filtro_service" / "cola0"
    carpeta_procesados = NUCLEO_DIR / "Procesados"
    carpeta_revision = NUCLEO_DIR / "Revision_Manual"
    ruta_bd = NUCLEO_DIR / "control_dte.db"
    ruta_log = Path(__file__).resolve().parent / "registro_errores.log"

    carpeta_respaldo = NUCLEO_DIR / "Respaldo_PDF"

    print("=======================================")
    print(" INICIANDO CONVERSOR0 JSON (SCA) ")
    print("=======================================")

    estandarizador = Estandarizador(
        carpeta_cola0=carpeta_cola0,
        carpeta_procesados=carpeta_procesados,
        carpeta_revision=carpeta_revision,
        carpeta_respaldo=carpeta_respaldo,
        ruta_bd=ruta_bd,
        ruta_log=ruta_log
    )

    resultados = estandarizador.ejecutar()

    if resultados["procesados"] == 0 and resultados["errores"] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
