"""
Gestor de DTE (Manager).

Recibe mensajes ya normalizados desde CUALQUIER conector (IMAP o POP3,
da igual) y decide qué hacer con ellos: filtrar por asunto, validar que
el adjunto sea realmente un DTE, descargarlo, y dejar registro en un
CSV. No sabe nada de protocolos de correo — esa es la idea de la
separación modular.
"""

import csv
import json
import os
import re
import io
from datetime import datetime
import pdfplumber

from .conectores.base import MensajeNormalizado
from .bd_correos import bd


from src.config import CARPETA_DESCARGAS, RUTA_LOG_CORREOS

class GestorDTE:

    def __init__(
        self,
        carpeta_descargas=str(CARPETA_DESCARGAS),
        archivo_log=str(RUTA_LOG_CORREOS),
        palabras_clave_asunto=None,
        campos_dte_esperados=None,
        extensiones_validas=("json", "pdf"),
    ):
        self.carpeta_descargas = carpeta_descargas
        self.archivo_log = archivo_log
        self.palabras_clave_asunto = palabras_clave_asunto or []
        self.campos_dte_esperados = campos_dte_esperados or [
            "identificacion",
            "emisor",
            "receptor",
        ]
        self.extensiones_validas = extensiones_validas

        os.makedirs(self.carpeta_descargas, exist_ok=True)
        self._preparar_log()

    def _preparar_log(self):
        existe = os.path.exists(self.archivo_log)
        self._log_file = open(self.archivo_log, "a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._log_file)
        if not existe:
            self._writer.writerow(
                [
                    "fecha_procesado",
                    "cuenta",
                    "remitente",
                    "asunto",
                    "fecha_correo",
                    "nombre_adjunto",
                    "ruta_local",
                    "codigo_generacion_dte",
                ]
            )

    def cerrar(self):
        self._log_file.close()

    # -- filtros --

    def _asunto_coincide(self, asunto: str) -> bool:
        if not self.palabras_clave_asunto:
            return True
        asunto_lower = (asunto or "").lower()
        return any(p.lower() in asunto_lower for p in self.palabras_clave_asunto)

    def _es_json_dte_valido(self, contenido_bytes):
        try:
            data = json.loads(contenido_bytes.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            print(f"  [!] Archivo JSON rechazado por error de decodificación: {e}")
            return False, None
        
        if all(campo in data for campo in self.campos_dte_esperados):
            return True, data
            
        print("  [!] Archivo JSON rechazado: No contiene la estructura DTE esperada (faltan campos clave).")
        return False, None

    @staticmethod
    def _nombre_archivo_seguro(nombre: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", nombre)

    def _lectura_ligera_pdf(self, contenido_bytes: bytes) -> str:
        """Extrae el UUID, Sello o Número de Control de la primera página del PDF."""
        try:
            with pdfplumber.open(io.BytesIO(contenido_bytes)) as pdf:
                if not pdf.pages:
                    return ""
                texto = pdf.pages[0].extract_text()
                if not texto:
                    return ""
                
                # Buscar UUID
                match_uuid = re.search(r'[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}', texto)
                if match_uuid:
                    return match_uuid.group(0).upper()
                    
                # Buscar Sello
                match_sello = re.search(r'(?:sello\s+recepcion|sello\s+de\s+recepci[\w]*)\s*[:=]?\s*([a-zA-Z0-9]{30,45})', texto, re.IGNORECASE)
                if match_sello:
                    return match_sello.group(1).upper()
                    
                # Buscar Número de control
                match_control = re.search(r'(?:n[\w\W]{1,3}mero|no\.?)\s*(?:de\s*)?control\s*[:=]?\s*(dte-\d{2}-\w{8}-\d{15})', texto, re.IGNORECASE)
                if match_control:
                    return match_control.group(1).upper()
                    
        except Exception as e:
            print(f"  [!] Error en lectura ligera de PDF: {e}")
        return ""

    # -- procesamiento principal --

    def procesar_cuenta(self, nombre_cuenta: str, conector) -> dict:
        """Recorre los candidatos de un conector ya conectado y procesa
        sus adjuntos. Devuelve un pequeño resumen numérico."""
        revisados = 0
        descargados = 0

        candidatos = conector.listar_candidatos()

        for mensaje in candidatos:
            if bd.fue_procesado(nombre_cuenta, mensaje.message_id):
                continue
                
            revisados += 1

            if not self._asunto_coincide(mensaje.asunto):
                print(f"  [Omitido] Asunto no coincide: '{mensaje.asunto}'")
                bd.marcar_procesado(nombre_cuenta, mensaje.message_id)
                continue

            adjuntos = conector.obtener_adjuntos(mensaje)
            encontro_algo = False

            # -- Pasada previa: buscar codigoGeneracion en JSON, o lectura ligera en PDF --
            codigo_generacion_mensaje = ""
            # Primero intentar con JSON (más rápido)
            for filename, contenido in adjuntos:
                extension = filename.lower().split(".")[-1] if "." in filename else ""
                if extension == "json":
                    es_valido_pre, data_dte_pre = self._es_json_dte_valido(contenido)
                    if es_valido_pre:
                        codigo_generacion_mensaje = data_dte_pre.get("identificacion", {}).get("codigoGeneracion", "")
                        if codigo_generacion_mensaje:
                            break
                            
            # Si no hay JSON o no tiene UUID, intentar con el primer PDF
            if not codigo_generacion_mensaje:
                for filename, contenido in adjuntos:
                    extension = filename.lower().split(".")[-1] if "." in filename else ""
                    if extension == "pdf":
                        identificador_extraido = self._lectura_ligera_pdf(contenido)
                        if identificador_extraido:
                            codigo_generacion_mensaje = identificador_extraido
                            break

            # -- Pasada de guardado: usar el identificador compartido --
            for filename, contenido in adjuntos:
                extension = (
                    filename.lower().split(".")[-1] if "." in filename else ""
                )
                if extension not in self.extensiones_validas:
                    continue

                # Validar estructura DTE solo para JSON (PDF pasa sin validación)
                es_valido = True
                if extension == "json":
                    es_valido, _ = self._es_json_dte_valido(contenido)

                if not es_valido:
                    continue

                # Usar el código compartido del mensaje, o 'none' como fallback
                identificador = codigo_generacion_mensaje or "none"

                base_nombre = self._nombre_archivo_seguro(f"{nombre_cuenta}_{identificador}_{mensaje.fecha}")
                nombre_final = f"{base_nombre}.{extension}"
                ruta_destino = os.path.join(self.carpeta_descargas, nombre_final)
                
                # Manejo de colisiones (DDMMAAAA_NO)
                contador = 1
                while os.path.exists(ruta_destino):
                    nombre_final = f"{base_nombre}_{contador}.{extension}"
                    ruta_destino = os.path.join(self.carpeta_descargas, nombre_final)
                    contador += 1

                with open(ruta_destino, "wb") as f:
                    f.write(contenido)

                self._writer.writerow(
                    [
                        datetime.now().isoformat(timespec="seconds"),
                        nombre_cuenta,
                        mensaje.remitente,
                        mensaje.asunto,
                        mensaje.fecha,
                        filename,
                        ruta_destino,
                        codigo_generacion_mensaje,
                    ]
                )
                print(f"[Conexión - {nombre_cuenta}] Descargado documento '{nombre_final}'")
                encontro_algo = True
                descargados += 1

            if encontro_algo:
                conector.marcar_procesado(mensaje)
                
            bd.marcar_procesado(nombre_cuenta, mensaje.message_id)

        return {"revisados": revisados, "descargados": descargados}
