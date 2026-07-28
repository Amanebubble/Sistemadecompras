"""
Registro de DTEs procesados en SQLite.

Mantiene un índice de todos los codigo_generacion ya procesados
para evitar reprocesar documentos en corridas posteriores.
La consulta usa la PRIMARY KEY como índice, O(log n) incluso
con cientos de miles de registros.
"""

import sqlite3
from datetime import datetime


def inicializar_bd(ruta_bd: str) -> sqlite3.Connection:
    """Crea la base de datos y la tabla si no existen. Retorna la conexión abierta.

    Args:
        ruta_bd: Ruta al archivo .db de SQLite.

    Returns:
        Conexión sqlite3 abierta y lista para usar.
    """
    conexion = sqlite3.connect(ruta_bd)
    conexion.execute("""
        CREATE TABLE IF NOT EXISTS dte_procesados (
            codigo_generacion TEXT PRIMARY KEY,
            nombre_cliente    TEXT NOT NULL,
            fecha_descarga    TEXT NOT NULL,
            fecha_registro    TEXT NOT NULL
        )
    """)
    conexion.commit()
    return conexion


def ya_procesado(conexion: sqlite3.Connection, codigo_generacion: str) -> bool:
    """Consulta si un codigo_generacion ya fue procesado.

    Usa SELECT 1 + PRIMARY KEY → O(log n).

    Args:
        conexion: Conexión sqlite3 abierta.
        codigo_generacion: UUID del DTE a consultar.

    Returns:
        True si ya existe en la tabla, False si no.
    """
    cursor = conexion.execute(
        "SELECT 1 FROM dte_procesados WHERE codigo_generacion = ?",
        (codigo_generacion,),
    )
    return cursor.fetchone() is not None


def registrar_procesado(
    conexion: sqlite3.Connection,
    codigo_generacion: str,
    nombre_cliente: str,
    fecha_descarga: str,
) -> None:
    """Registra un DTE como procesado.

    Usa INSERT OR IGNORE para no fallar si el registro ya existe.

    Args:
        conexion: Conexión sqlite3 abierta.
        codigo_generacion: UUID del DTE.
        nombre_cliente: Nombre de cuenta extraído del nombre del archivo.
        fecha_descarga: Fecha de descarga del archivo original (YYYY-MM-DD).
    """
    conexion.execute(
        """INSERT OR IGNORE INTO dte_procesados
           (codigo_generacion, nombre_cliente, fecha_descarga, fecha_registro)
           VALUES (?, ?, ?, ?)""",
        (
            codigo_generacion,
            nombre_cliente,
            fecha_descarga,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conexion.commit()
