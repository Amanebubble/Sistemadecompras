"""
Punto de entrada para el módulo filtro_service.
"""
import sys
import json
from pathlib import Path

# Resolver la raíz del proyecto y agregar paths
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO / "nucleo" / "filtro_service"))

from enrutador import Enrutador

def main():
    directorio_actual = Path(__file__).resolve().parent
    ruta_settings = directorio_actual / "settings.json"
    
    with open(ruta_settings, 'r', encoding='utf-8') as f:
        settings = json.load(f)
        
    # Resolver rutas relativas a la raíz del proyecto
    for clave in settings:
        if clave.startswith("carpeta_") or clave == "ruta_bd":
            settings[clave] = str(RAIZ_PROYECTO / settings[clave])
            
    print("==================================================")
    print("       INICIANDO PROCESO DE ENRUTAMIENTO (SCA)")
    print("==================================================")
    
    enrutador = Enrutador(settings)
    resultados = enrutador.ejecutar()
    
    total_procesados = (
        resultados["cola0"] + 
        resultados["cola1"] + 
        resultados["respaldo"] + 
        resultados["invalidos"] + 
        resultados["otros"]
    )
    
    if total_procesados == 0 and resultados["errores"] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
