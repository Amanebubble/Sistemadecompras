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

            if not mensaje_email.is_multipart():
                continue  # sin adjuntos posibles

            tiene_adjunto = any(
                parte.get_filename() for parte in mensaje_email.walk()
            )
            if not tiene_adjunto:
                continue
                
            message_id = mensaje_email.get("Message-ID")
            if not message_id:
                message_id = id_interno

            self._mensajes_por_id[id_interno] = mensaje_email
            candidatos.append(
                MensajeNormalizado(
                    id_interno=id_interno,
                    remitente=mensaje_email.get("From", ""),
                    asunto=mensaje_email.get("Subject", ""),
                    fecha=mensaje_email.get("Date", ""),
                    adjuntos_raw=None,  # se resuelve en obtener_adjuntos usando el cache
                    message_id=message_id,
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
        # Operación de solo lectura: la persistencia ahora es centralizada
        pass
