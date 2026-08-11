import json
import sqlite3
import shutil
import re
from pathlib import Path
from datetime import datetime

import sys
try:
    from src.auditoria import registrar_error as auditoria_registrar_error
except ImportError:
    auditoria_registrar_error = None
from src.config import (
    CARPETA_COLA0, CARPETA_PROCESADOS, CARPETA_REVISION, CARPETA_RESPALDO, CARPETA_OTROS_DTES, 
    RUTA_BD_CONTROL, RUTA_LOG_SISTEMA
)
from src.directorio_db import agregar_entidad
from .mapeador import mapear_a_plantilla
from src.archivador_sql import ArchivadorSQL


def _inicializar_bd(ruta_bd: str):
    """Inicializa la base de datos SQLite."""
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


def _ya_procesado(conexion, codigo_generacion: str) -> bool:
    """Verifica si el UUID ya existe en la base de datos."""
    if not codigo_generacion:
        return False
    cursor = conexion.cursor()
    cursor.execute('SELECT 1 FROM dte_procesados WHERE codigo_generacion = ?', (codigo_generacion,))
    return cursor.fetchone() is not None


def _registrar_procesado(conexion, codigo_generacion: str, nombre_cliente: str, fecha_descarga: str):
    """Registra el UUID como procesado en la base de datos."""
    if not codigo_generacion:
        return
    cursor = conexion.cursor()
    fecha_registro = datetime.now().isoformat(timespec="seconds")
    cursor.execute('''
        INSERT OR IGNORE INTO dte_procesados 
        (codigo_generacion, nombre_cliente, fecha_descarga, fecha_registro) 
        VALUES (?, ?, ?, ?)
    ''', (codigo_generacion, nombre_cliente, fecha_descarga, fecha_registro))
    conexion.commit()


class Estandarizador:
    """Clase principal para estandarizar JSON de la cola0."""

    def __init__(
        self, 
        carpeta_cola0: Path = CARPETA_COLA0, 
        carpeta_procesados: Path = CARPETA_PROCESADOS, 
        carpeta_revision: Path = CARPETA_REVISION, 
        carpeta_respaldo: Path = CARPETA_RESPALDO,
        carpeta_otros_dtes: Path = CARPETA_OTROS_DTES, 
        ruta_bd: Path = RUTA_BD_CONTROL, 
        ruta_log: Path = RUTA_LOG_SISTEMA
    ):
        self.carpeta_cola0 = carpeta_cola0
        self.carpeta_procesados = carpeta_procesados
        self.carpeta_revision = carpeta_revision
        self.carpeta_respaldo = carpeta_respaldo
        self.carpeta_otros_dtes = carpeta_otros_dtes
        self.ruta_bd = ruta_bd
        self.ruta_log = ruta_log

        self.procesados = 0
        self.revision = 0
        self.errores = 0
        self.otros_dtes = 0

        self.conexion = None

        # Crear carpetas si no existen
        self.carpeta_procesados.mkdir(parents=True, exist_ok=True)
        self.carpeta_revision.mkdir(parents=True, exist_ok=True)
        self.carpeta_respaldo.mkdir(parents=True, exist_ok=True)

    def _extraer_identificador(self, nombre_archivo: str) -> str:
        """Extrae el identificador (UUID, Sello, Control) del nombre del archivo."""
        import re
        match = re.search(r'_([^_]+)_\d{8}(?:_\d+)?\.[a-zA-Z0-9]+$', nombre_archivo)
        if match:
            return match.group(1).upper()
        # Fallback a UUID regex si no viene en el formato esperado
        match = re.search(r'[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}', nombre_archivo)
        return match.group(0).upper() if match else None

    def _extraer_nombre_cliente(self, nombre_archivo: str) -> str:
        """Extrae el nombre del cliente del nombre del archivo."""
        identificador = self._extraer_identificador(nombre_archivo)
        if identificador:
            partes = nombre_archivo.split(f"_{identificador}_")
            if len(partes) > 1:
                import re
                nombre_bruto = partes[0]
                # Limpiar el "_UIDxxx" que inyectamos en gestor_dte.py
                nombre_limpio = re.sub(r'_UID\d+$', '', nombre_bruto)
                return nombre_limpio
        return nombre_archivo.split('_')[0]

    @staticmethod
    def _mover(ruta_origen: Path, carpeta_destino: Path):
        """Mueve un archivo manejando conflictos de nombres."""
        if not ruta_origen.exists():
            return
        destino = carpeta_destino / ruta_origen.name
        if destino.exists():
            nombre_base = ruta_origen.stem
            extension = ruta_origen.suffix
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            destino = carpeta_destino / f"{nombre_base}_{timestamp}{extension}"
        shutil.move(str(ruta_origen), str(destino))

    def _registrar_error(self, nombre_archivo: str, motivo: str):
        """Registra un error en el archivo de log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.ruta_log, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] Archivo: {nombre_archivo} - Error: {motivo}\n")

    def _mover_a_revision(self, archivo_json: Path, motivo: str):
        """Mueve un JSON a revisión manual y rescata su PDF original si existe."""
        self._mover(archivo_json, self.carpeta_revision)
        self._registrar_error(archivo_json.name, motivo)
        
        # Intentar rescatar el PDF original
        nombre_base = archivo_json.stem
        posible_pdf = self.carpeta_respaldo / f"{nombre_base}.pdf"
        posible_pdf_mayus = self.carpeta_respaldo / f"{nombre_base}.PDF"
        
        if posible_pdf.exists():
            self._mover(posible_pdf, self.carpeta_revision)
        elif posible_pdf_mayus.exists():
            self._mover(posible_pdf_mayus, self.carpeta_revision)

    def procesar_cola(self):
        """Procesa todos los archivos .json en la carpeta cola0."""
        archivos = list(self.carpeta_cola0.glob('*.json'))
        for archivo in archivos:
            nombre_archivo = archivo.name
            
            try:
                with open(archivo, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"[Estandarizador] [ERROR] JSON corrupto en '{nombre_archivo}'. Movido a Revisión.")
                self._mover_a_revision(archivo, f"Error al parsear JSON: {str(e)}")
                self.errores += 1
                continue

            try:
                nombre_cliente = self._extraer_nombre_cliente(nombre_archivo)
                identificador_archivo = self._extraer_identificador(nombre_archivo)
                
                # Mapear
                data_estandarizada = mapear_a_plantilla(data, "JSON_NATIVO", nombre_cliente)
                
                # Validación estricta ("Jefe Final")
                faltantes = []
                datos_doc = data_estandarizada.get('datos_documento', {})
                datos_prov = data_estandarizada.get('datos_proveedor', {})
                meta = data_estandarizada.get('metadatos_sistema', {})
                finanzas = data_estandarizada.get('detalle_financiero', {})

                # 1. Fechas (debe existir y tener un formato válido)
                fecha = str(datos_doc.get('fecha_emision', '')).strip()
                
                if not fecha or (not re.match(r'^\d{4}-\d{2}-\d{2}', fecha) and not re.match(r'^\d{2}/\d{2}/\d{4}', fecha)):
                    match_fecha_archivo = re.search(r'(\d{8})', nombre_archivo)
                    if match_fecha_archivo:
                        fecha_raw = match_fecha_archivo.group(1)
                        # Convertir DDMMAAAA a YYYY-MM-DD
                        fecha = f"{fecha_raw[4:8]}-{fecha_raw[2:4]}-{fecha_raw[0:2]}"
                        datos_doc['fecha_emision'] = fecha

                if not fecha:
                    faltantes.append("fecha_emision")
                elif not re.match(r'^\d{4}-\d{2}-\d{2}', fecha) and not re.match(r'^\d{2}/\d{2}/\d{4}', fecha):
                    faltantes.append(f"fecha_emision_invalida({fecha})")

                # 2. Metadatos del Sistema
                if not str(meta.get('codigo_generacion', '')).strip():
                    faltantes.append("codigo_generacion")
                if not str(meta.get('sello_recepcion', '')).strip():
                    faltantes.append("sello_recepcion")
                if not str(meta.get('numero_control', '')).strip():
                    faltantes.append("numero_control")

                # 3. Proveedor
                if not str(datos_prov.get('nombre_razon_social', '')).strip():
                    faltantes.append("nombre_razon_social (proveedor)")
                if not str(datos_prov.get('nrc', '')).strip():
                    faltantes.append("nrc (proveedor)")

                # 4. Tipo DTE (para control de signos)
                tipo_dte = str(datos_doc.get('tipo_documento', '')).strip()
                if not tipo_dte:
                    faltantes.append("tipo_dte")
                else:
                    validos_compras = ["03", "05", "06", "14"]
                    if tipo_dte not in validos_compras:
                        archivo_destino = self.carpeta_otros_dtes / nombre_archivo
                        shutil.copy2(str(archivo), str(archivo_destino))
                        archivo.unlink()
                        self.otros_dtes += 1
                        print(f"[Estandarizador] Omitido tipo {tipo_dte} (No Compra). Movido a Otros DTEs: '{nombre_archivo}'")
                        continue

                # 5. Finanzas (Rechazar si el total es 0.00, ej. PDFs crudos sin mapeo financiero)
                total = abs(finanzas.get('total_compras', 0.0))
                iva = abs(finanzas.get('iva_credito_fiscal', 0.0))
                if total == 0.0 and iva == 0.0:
                    faltantes.append("datos_financieros_faltantes (totales en 0)")

                if faltantes:
                    print(f"[Estandarizador] Faltan datos en '{nombre_archivo}': {', '.join(faltantes)}. A Revisión.")
                    self._mover_a_revision(archivo, f"Validación fallida, campos faltantes: {', '.join(faltantes)}")
                    self.revision += 1
                    continue

                # Éxito
                # Guardar en BD SQLite (ArchivadorSQL)
                archivador = ArchivadorSQL(str(self.ruta_bd))
                archivador.guardar(data_estandarizada)

                # Mover a carpeta procesados
                archivo_destino = self.carpeta_procesados / nombre_archivo
                with open(archivo_destino, 'w', encoding='utf-8') as f:
                    json.dump(data_estandarizada, f, ensure_ascii=False, indent=2)
                
                # Eliminar original si se copió con éxito
                archivo.unlink()
                
                # Registrar en BD de correos
                _registrar_procesado(self.conexion, identificador_archivo, nombre_cliente, datetime.now().isoformat())
                
                # Aprendizaje Continuo (Guardar nuevo proveedor en el directorio)
                if str(datos_prov.get('nombre_razon_social', '')).strip() != "Extraido de PDF":
                    agregar_entidad(
                        nrc=datos_prov.get('nrc', ''),
                        nit=datos_prov.get('nit', ''),
                        dui=datos_prov.get('dui_sujeto_excluido', ''),
                        nombre=datos_prov.get('nombre_razon_social', ''),
                        tipo="proveedor"
                    )

                self.procesados += 1
                print(f"[Estandarizador] ¡Éxito! Documento '{nombre_archivo}' ingresado a la Base de Datos.")

            except Exception as e:
                print(f"[Estandarizador] [ERROR] Falló procesamiento en '{nombre_archivo}': {e}")
                self._mover_a_revision(archivo, f"Excepción durante procesamiento: {str(e)}")
                self.errores += 1
                if auditoria_registrar_error:
                    auditoria_registrar_error("Estandarizador", nombre_cliente, f"Error: {e}")

            import time
            time.sleep(1.5)

    def ejecutar(self) -> dict:
        """Ejecuta el proceso principal."""
        self.conexion = _inicializar_bd(str(self.ruta_bd))
        try:
            self.procesar_cola()
        finally:
            if self.conexion:
                self.conexion.close()

        return {
            "procesados": self.procesados,
            "revision": self.revision,
            "errores": self.errores
        }




