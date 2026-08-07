import os
import sqlite3
from datetime import datetime
from src.config import RUTA_BD_CORREOS

class BaseDatosCorreos:
    def __init__(self, ruta_db=str(RUTA_BD_CORREOS)):
        self.ruta_db = ruta_db
        self.inicializar_bd()

    def inicializar_bd(self):
        with sqlite3.connect(self.ruta_db) as conexion:
            cursor = conexion.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS correos_procesados (
                    cuenta TEXT,
                    message_id TEXT,
                    fecha_procesado TEXT,
                    PRIMARY KEY (cuenta, message_id)
                )
            ''')
            conexion.commit()

    def fue_procesado(self, cuenta: str, message_id: str) -> bool:
        with sqlite3.connect(self.ruta_db) as conexion:
            cursor = conexion.cursor()
            cursor.execute('''
                SELECT 1 FROM correos_procesados
                WHERE cuenta = ? AND message_id = ?
            ''', (cuenta, message_id))
            return cursor.fetchone() is not None

    def marcar_procesado(self, cuenta: str, message_id: str):
        fecha_procesado = datetime.now().isoformat(timespec="seconds")
        with sqlite3.connect(self.ruta_db) as conexion:
            cursor = conexion.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO correos_procesados (cuenta, message_id, fecha_procesado)
                VALUES (?, ?, ?)
            ''', (cuenta, message_id, fecha_procesado))
            conexion.commit()

# Instancia global por defecto
bd = BaseDatosCorreos()
