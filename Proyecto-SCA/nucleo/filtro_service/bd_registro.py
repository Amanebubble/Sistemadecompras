"""
Módulo para el registro y deduplicación de DTEs procesados.
"""
import sqlite3
from datetime import datetime

def inicializar_bd(ruta_bd):
    """
    Crea o inicializa la tabla dte_procesados en la base de datos especificada.
    """
    conexion = sqlite3.connect(ruta_bd)
    cursor = conexion.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dte_procesados (
            codigo_generacion TEXT PRIMARY KEY,
            nombre_cliente TEXT NOT NULL,
            fecha_descarga TEXT NOT NULL,
            fecha_registro TEXT NOT NULL
        )
    ''')
    conexion.commit()
    return conexion

def ya_procesado(conexion, codigo_generacion):
    """
    Verifica si un DTE ya fue procesado mediante su código de generación (UUID).
    """
    cursor = conexion.cursor()
    cursor.execute('SELECT 1 FROM dte_procesados WHERE codigo_generacion = ?', (codigo_generacion,))
    resultado = cursor.fetchone()
    return resultado is not None

def registrar_procesado(conexion, codigo_generacion, nombre_cliente, fecha_descarga):
    """
    Registra un nuevo DTE en la base de datos de procesados.
    """
    cursor = conexion.cursor()
    fecha_registro = datetime.now().isoformat()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO dte_procesados (codigo_generacion, nombre_cliente, fecha_descarga, fecha_registro)
            VALUES (?, ?, ?, ?)
        ''', (codigo_generacion, nombre_cliente, fecha_descarga, fecha_registro))
        conexion.commit()
    except sqlite3.Error as e:
        print(f"Error al registrar {codigo_generacion}: {e}")
