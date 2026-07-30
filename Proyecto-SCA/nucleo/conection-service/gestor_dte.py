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
from datetime import datetime

from conectores.base import MensajeNormalizado


class GestorDTE:

    def __init__(
        self,
        carpeta_descargas="facturas_descargadas",
        archivo_log="log.csv",
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

    # -- procesamiento principal --

    def procesar_cuenta(self, nombre_cuenta: str, conector) -> dict:
        """Recorre los candidatos de un conector ya conectado y procesa
        sus adjuntos. Devuelve un pequeño resumen numérico."""
        revisados = 0
        descargados = 0

        candidatos = conector.listar_candidatos()

        for mensaje in candidatos:
            revisados += 1

            if not self._asunto_coincide(mensaje.asunto):
                print(f"  [Omitido] Asunto no coincide: '{mensaje.asunto}'")
                continue

            adjuntos = conector.obtener_adjuntos(mensaje)
            encontro_algo = False

            # -- Pasada previa: buscar codigoGeneracion en el primer JSON DTE --
            codigo_generacion_mensaje = ""
            for filename, contenido in adjuntos:
                extension = (
                    filename.lower().split(".")[-1] if "." in filename else ""
                )
                if extension == "json":
                    es_valido_pre, data_dte_pre = self._es_json_dte_valido(
                        contenido
                    )
                    if es_valido_pre:
                        codigo_generacion_mensaje = data_dte_pre.get(
                            "identificacion", {}
                        ).get("codigoGeneracion", "")
                        if codigo_generacion_mensaje:
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

                # Usar el código compartido del mensaje, o el ID interno como respaldo
                identificador = codigo_generacion_mensaje or mensaje.id_interno

                nombre_final = self._nombre_archivo_seguro(
                    f"{nombre_cuenta}_{identificador}_{filename}"
                )
                ruta_destino = os.path.join(self.carpeta_descargas, nombre_final)

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
                print(f"  -> [{nombre_cuenta}] Descargado: {ruta_destino}")
                encontro_algo = True
                descargados += 1

            if encontro_algo:
                conector.marcar_procesado(mensaje)

        return {"revisados": revisados, "descargados": descargados}
