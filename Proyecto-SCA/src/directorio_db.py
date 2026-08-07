import sqlite3
from pathlib import Path
from typing import Optional, Dict

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import RUTA_BD_DIRECTORIO

def get_connection():
    return sqlite3.connect(RUTA_BD_DIRECTORIO)

def inicializar_bd():
    """Crea la tabla de directorio de entidades (clientes/proveedores) si no existe."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nrc TEXT,
            nit TEXT,
            dui TEXT,
            nombre TEXT NOT NULL,
            tipo TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Crear índices para búsqueda rápida
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nrc ON entidades(nrc)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nit ON entidades(nit)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nombre ON entidades(nombre)')
    conn.commit()
    conn.close()

def normalizar_cadena(cadena: str) -> str:
    """Limpia la cadena para guardarla o buscarla (quitar espacios extra, mayúsculas)."""
    if not cadena:
        return ""
    import re
    return re.sub(r'\s+', ' ', str(cadena)).strip().upper()

def agregar_entidad(nrc: str, nit: str, dui: str, nombre: str, tipo: str = "proveedor") -> bool:
    """
    Agrega una nueva entidad al directorio, o la actualiza si ya existe con el mismo NRC o NIT.
    Retorna True si fue insertada/actualizada.
    """
    if not nombre or nombre.upper() == "EXTRAIDO DE PDF" or nombre.upper() == "DESCONOCIDO":
        return False
        
    nrc_norm = normalizar_cadena(nrc)
    nit_norm = normalizar_cadena(nit)
    dui_norm = normalizar_cadena(dui)
    nombre_norm = normalizar_cadena(nombre)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Buscar si ya existe por NRC o NIT
    query_buscar = "SELECT id FROM entidades WHERE 1=0 "
    params_buscar = []
    
    if nrc_norm:
        query_buscar += " OR nrc = ?"
        params_buscar.append(nrc_norm)
    if nit_norm:
        query_buscar += " OR nit = ?"
        params_buscar.append(nit_norm)
        
    if params_buscar:
        cursor.execute(query_buscar, params_buscar)
        row = cursor.fetchone()
        if row:
            # Actualizar
            entidad_id = row[0]
            # Solo actualizamos los campos que no estén vacíos en la nueva entrada
            updates = []
            params_upd = []
            if nrc_norm: updates.append("nrc = ?"); params_upd.append(nrc_norm)
            if nit_norm: updates.append("nit = ?"); params_upd.append(nit_norm)
            if dui_norm: updates.append("dui = ?"); params_upd.append(dui_norm)
            if nombre_norm: updates.append("nombre = ?"); params_upd.append(nombre_norm)
            
            if updates:
                params_upd.append(entidad_id)
                query_upd = f"UPDATE entidades SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query_upd, params_upd)
                conn.commit()
                conn.close()
                return True
                
    # Si no existe, insertar nuevo
    cursor.execute('''
        INSERT INTO entidades (nrc, nit, dui, nombre, tipo) 
        VALUES (?, ?, ?, ?, ?)
    ''', (nrc_norm, nit_norm, dui_norm, nombre_norm, tipo.upper()))
    conn.commit()
    conn.close()
    return True

def buscar_por_nrc(nrc: str) -> Optional[Dict]:
    """Busca una entidad por su NRC."""
    nrc_norm = normalizar_cadena(nrc)
    if not nrc_norm:
        return None
        
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT nrc, nit, dui, nombre, tipo FROM entidades WHERE nrc = ? LIMIT 1", (nrc_norm,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None

def buscar_por_nit(nit: str) -> Optional[Dict]:
    """Busca una entidad por su NIT."""
    nit_norm = normalizar_cadena(nit)
    if not nit_norm:
        return None
        
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT nrc, nit, dui, nombre, tipo FROM entidades WHERE nit = ? LIMIT 1", (nit_norm,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None

# Autoejecutar inicialización
inicializar_bd()
