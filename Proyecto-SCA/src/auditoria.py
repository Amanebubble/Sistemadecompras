import sqlite3
import os
from datetime import datetime
from pathlib import Path

# Obtener ruta a nucleo/
NUCLEO_DIR = Path(__file__).resolve().parent
DB_PATH = NUCLEO_DIR / "auditoria.db"

def inicializar_bd():
    """Inicializa la base de datos de auditoría si no existe."""
    with sqlite3.connect(DB_PATH) as conexion:
        cursor = conexion.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registro_errores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_hora TEXT NOT NULL,
                modulo TEXT NOT NULL,
                cuenta TEXT,
                mensaje_error TEXT NOT NULL
            )
        ''')
        conexion.commit()

def registrar_error(modulo: str, cuenta: str, mensaje: str):
    """
    Inserta un nuevo error en la tabla registro_errores.
    """
    # Asegurar que la tabla exista
    inicializar_bd()
    
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cuenta = cuenta if cuenta else "Desconocida"
    
    try:
        with sqlite3.connect(DB_PATH) as conexion:
            cursor = conexion.cursor()
            cursor.execute('''
                INSERT INTO registro_errores (fecha_hora, modulo, cuenta, mensaje_error)
                VALUES (?, ?, ?, ?)
            ''', (fecha_hora, modulo, cuenta, mensaje))
            conexion.commit()
    except Exception as e:
        # Fallback a console en caso extremo
        print(f"[!] Fallo al guardar en auditoría: {e}")
