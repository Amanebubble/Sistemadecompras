"""
Entry point del módulo filtro-service.

Uso (desde la raíz del proyecto o desde cualquier lugar):
    python nucleo/filtro-service/main.py
"""

import json
import os
import sys
from pathlib import Path

# Calcular la raíz del proyecto dinámicamente:
# Este archivo vive en  <raiz>/nucleo/filtro-service/main.py
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent.parent

# Añadir filtro-service al path para que los imports internos funcionen
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gestor_filtro import GestorFiltro


def main():
    # Cargar settings
    ruta_settings = Path(__file__).resolve().parent / "settings.json"
    with open(ruta_settings, "r", encoding="utf-8") as f:
        settings = json.load(f)

    # Resolver rutas relativas contra la raíz del proyecto
    claves_rutas = [
        "carpeta_entrada", "carpeta_procesados", "carpeta_respaldo",
        "carpeta_invalido", "carpeta_error", "carpeta_duplicados",
        "otros_documentos", "ruta_bd",
    ]
    for clave in claves_rutas:
        if clave in settings:
            ruta = Path(settings[clave])
            if not ruta.is_absolute():
                settings[clave] = str(RAIZ_PROYECTO / ruta)

    print()
    print("=" * 60)
    print("  FILTRO-SERVICE: Clasificacion de DTEs")
    print("  Sistema de Contabilidad Automatizada (SCA)")
    print("=" * 60)
    print()
    print(f"  Entrada:    {settings['carpeta_entrada']}")
    print(f"  Procesados: {settings['carpeta_procesados']}")
    print(f"  Respaldo:   {settings['carpeta_respaldo']}")
    print(f"  Invalidos:  {settings['carpeta_invalido']}")
    print(f"  Errores:    {settings['carpeta_error']}")
    print()

    gestor = GestorFiltro(settings)
    contadores = gestor.ejecutar()

    # Exit code 0 si procesó algo, 1 si todo fueron errores
    if contadores["procesados"] == 0 and contadores["errores"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
