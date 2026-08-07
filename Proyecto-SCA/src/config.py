"""
Configuración centralizada de rutas para el Proyecto-SCA.
Este archivo actúa como la única fuente de la verdad para todas las rutas del sistema,
haciendo que el proyecto sea 100% portable sin importar desde dónde se ejecute.
"""

from pathlib import Path
import os
import json

# Raíz del proyecto: este archivo está en src/config.py, así que la raíz es parent.parent
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

# ─── Carpetas de Datos (Almacenamiento Centralizado) ────────────────────────
DATA_DIR = RAIZ_PROYECTO / "data"

CARPETA_DESCARGAS    = DATA_DIR / "01_descargas"
CARPETA_COLA1        = DATA_DIR / "02_cola1_pdf"
CARPETA_COLA0        = DATA_DIR / "03_cola0_json"
CARPETA_PROCESADOS   = DATA_DIR / "04_procesados"
CARPETA_RESPALDO     = DATA_DIR / "05_respaldo_pdf"
CARPETA_REVISION     = DATA_DIR / "06_revision"
CARPETA_ERRORES      = DATA_DIR / "07_errores"
CARPETA_BASES_DATOS  = DATA_DIR / "bases_de_datos"

# ─── Asegurar que las carpetas existan ──────────────────────────────────────
for carpeta in [
    CARPETA_DESCARGAS, CARPETA_COLA1, CARPETA_COLA0,
    CARPETA_PROCESADOS, CARPETA_RESPALDO, CARPETA_REVISION,
    CARPETA_ERRORES, CARPETA_BASES_DATOS
]:
    carpeta.mkdir(parents=True, exist_ok=True)

# ─── Archivos y Bases de Datos Específicos ──────────────────────────────────
RUTA_BD_CONTROL = CARPETA_BASES_DATOS / "control_dte.db"
RUTA_BD_AUDITORIA = CARPETA_BASES_DATOS / "auditoria.db"
RUTA_BD_CORREOS = CARPETA_BASES_DATOS / "correos_procesados.db"
RUTA_BD_DIRECTORIO = CARPETA_BASES_DATOS / "directorio.db"

# Logs globales
RUTA_LOG_SISTEMA = CARPETA_ERRORES / "sistema.log"
RUTA_LOG_CORREOS = CARPETA_ERRORES / "log_correos.csv"

# ─── Configuración Interna de Servicios ─────────────────────────────────────
SRC_DIR = RAIZ_PROYECTO / "src"
CONECTION_DIR = SRC_DIR / "conection_service"
ARCHIVO_CUENTAS = CONECTION_DIR / "accounts.json"
CREDENTIALS_DIR = CONECTION_DIR / "credentials"
CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

PLANTILLA_DTE_PATH = SRC_DIR / "plantilla_dte.json"

# ─── Configuración del Enrutador (Filtro Service) ───────────────────────────
FILTRO_CONFIG = {
    "carpeta_entrada": CARPETA_DESCARGAS,
    "carpeta_cola0": CARPETA_COLA0,
    "carpeta_cola1": CARPETA_COLA1,
    "carpeta_respaldo": CARPETA_RESPALDO,
    "carpeta_invalido": CARPETA_ERRORES,
    "carpeta_error": CARPETA_ERRORES,
    "carpeta_duplicados": CARPETA_ERRORES,
    "carpeta_otros": CARPETA_ERRORES,
    "ruta_bd": RUTA_BD_CONTROL,
    "patron_uuid": r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}",
    "campos_dte_esperados": ["identificacion", "emisor", "receptor"],
    "tipos_dte_validos": ["03", "05", "06", "14"]
}

# ─── Funciones Utilitarias Compartidas ──────────────────────────────────────
def registrar_error(modulo: str, archivo_o_entidad: str, motivo: str):
    """Registra un error en el log unificado del sistema."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mensaje = f"[{timestamp}] [{modulo}] Entidad: {archivo_o_entidad} - Error: {motivo}\n"
    print(mensaje.strip())
    with open(RUTA_LOG_SISTEMA, 'a', encoding='utf-8') as f:
        f.write(mensaje)
    
    # Intenta también escribir en la DB de auditoría si está disponible
    try:
        from src.auditoria import registrar_error as db_registrar_error
        db_registrar_error(modulo, archivo_o_entidad, motivo)
    except Exception as e:
        pass

CARPETA_HISTORICO = DATA_DIR / "04_procesados" / "historico"
CARPETA_REPORTES = DATA_DIR / "08_reportes"
CARPETA_OTROS_DTES = DATA_DIR / "09_otros_dtes"
CARPETA_HISTORICO.mkdir(parents=True, exist_ok=True)
CARPETA_REPORTES.mkdir(parents=True, exist_ok=True)
CARPETA_OTROS_DTES.mkdir(parents=True, exist_ok=True)




