"""
Conector POP3.

POP3 es más limitado que IMAP: no soporta búsquedas en el servidor ni
banderas persistentes. Por eso este conector lleva un registro local
(un archivo .json por cuenta) con los IDs de mensajes ya procesados,
usando el comando UIDL (identificador único de mensaje que la mayoría
de servidores POP3 soportan y que no cambia entre conexiones).

Si el servidor no soporta UIDL, como respaldo se usa un hash del
encabezado del mensaje (remitente + asunto + fecha), que es menos
robusto pero funciona en la gran mayoría de casos reales.
"""

import email
import hashlib
import json
import os
import poplib

from .base import MailConnector, MensajeNormalizado


class POP3Connector(MailConnector):

    def __init__(self, config_cuenta: dict):
        super().__init__(config_cuenta)
        self._conn = None
        self._mensajes_por_id = {}  # id_interno -> objeto email.message.Message
        self._ruta_estado = self._ruta_archivo_estado()
        self._procesados = self._cargar_estado()

    # -- manejo del estado local (reemplaza lo que IMAP resuelve con banderas) --

    def _ruta_archivo_estado(self):
        nombre_cuenta = self.config.get("nombre", self.config["usuario"])
        nombre_seguro = "".join(c if c.isalnum() else "_" for c in nombre_cuenta)
        carpeta_estado = "estado_pop3"
        os.makedirs(carpeta_estado, exist_ok=True)
        return os.path.join(carpeta_estado, f"{nombre_seguro}.json")

    def _cargar_estado(self):
        if os.path.exists(self._ruta_estado):
            with open(self._ruta_estado, "r", encoding="utf-8") as f:
                return set(json.load(f))
        return set()

    def _guardar_estado(self):
        with open(self._ruta_estado, "w", encoding="utf-8") as f:
            json.dump(sorted(self._procesados), f)

    # -- interfaz MailConnector --

    def conectar(self):
        servidor = self.config["servidor"]
        puerto = self.config.get("puerto", 995)
        usuario = self.config["usuario"]
        password = self.config["password"]

        self._conn = poplib.POP3_SSL(servidor, puerto)
        self._conn.user(usuario)
        self._conn.pass_(password)

    def desconectar(self):
        if self._conn:
            self._conn.quit()

    def listar_candidatos(self):
        candidatos = []

        cantidad_mensajes = len(self._conn.list()[1])

        # UIDL devuelve, por cada mensaje, un ID estable que no cambia
        # entre conexiones (a diferencia del número de mensaje, que sí
        # puede cambiar si se borran correos).
        try:
            respuesta_uidl = self._conn.uidl()
            lineas_uidl = respuesta_uidl[1]
            uidls = {}
            for linea in lineas_uidl:
                num, uid = linea.decode().split(" ", 1)
                uidls[int(num)] = uid
            soporta_uidl = True
        except Exception:
            soporta_uidl = False
            uidls = {}

        for num in range(1, cantidad_mensajes + 1):
            _, lineas, _ = self._conn.retr(num)
            contenido_bytes = b"\r\n".join(lineas)
            mensaje_email = email.message_from_bytes(contenido_bytes)

            if soporta_uidl and num in uidls:
                id_interno = uidls[num]
            else:
                # Respaldo si el servidor no soporta UIDL
                base = f"{mensaje_email.get('From','')}{mensaje_email.get('Subject','')}{mensaje_email.get('Date','')}"
                id_interno = hashlib.sha256(base.encode("utf-8", "ignore")).hexdigest()

            if id_interno in self._procesados:
                continue

            if not mensaje_email.is_multipart():
                continue  # sin adjuntos posibles

            tiene_adjunto = any(
                parte.get_filename() for parte in mensaje_email.walk()
            )
            if not tiene_adjunto:
                continue

            self._mensajes_por_id[id_interno] = mensaje_email
            candidatos.append(
                MensajeNormalizado(
                    id_interno=id_interno,
                    remitente=mensaje_email.get("From", ""),
                    asunto=mensaje_email.get("Subject", ""),
                    fecha=mensaje_email.get("Date", ""),
                    adjuntos_raw=None,  # se resuelve en obtener_adjuntos usando el cache
                )
            )

        return candidatos

    def obtener_adjuntos(self, mensaje: MensajeNormalizado):
        mensaje_email = self._mensajes_por_id[mensaje.id_interno]
        resultado = []
        for parte in mensaje_email.walk():
            filename = parte.get_filename()
            if not filename:
                continue
            contenido = parte.get_payload(decode=True)
            if contenido is None:
                continue
            resultado.append((filename, contenido))
        return resultado

    def marcar_procesado(self, mensaje: MensajeNormalizado):
        self._procesados.add(mensaje.id_interno)
        self._guardar_estado()
