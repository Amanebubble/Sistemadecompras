"""
Conector Gmail (API oficial con OAuth2).

Implementa la misma interfaz que IMAPConnector y POP3Connector, así que
el Router y el Manager lo usan exactamente igual, sin saber que por
detrás hay una API distinta. Se recomienda para cuentas @gmail.com o de
Google Workspace, ya que no requiere guardar la contraseña de la cuenta
en ningún lado (solo un token de autorización renovable).

Requiere:
    pip install --break-system-packages google-api-python-client google-auth-httplib2 google-auth-oauthlib

Configuración esperada en accounts.json para este protocolo:
{
    "nombre": "Despacho - Gmail dueño",
    "protocolo": "gmail_oauth",
    "usuario": "dueno@gmail.com",
    "credentials_path": "credentials_dueno.json",
    "token_path": "token_dueno.json",
    "palabras_clave_asunto": ["DTE", "factura", "CCF"]
}

- credentials_path: archivo descargado desde Google Cloud Console
  (ver README para el paso a paso de cómo generarlo).
- token_path: se genera solo la primera vez que corrés el sistema
  (ahí se abre el navegador para que el dueño autorice el acceso). En
  las siguientes corridas se reutiliza y se refresca solo.
"""

import base64
import os
import socket
from pathlib import Path

# Timeout global para evitar bloqueos en la autenticación/descarga
socket.setdefaulttimeout(15)

from src.config import CREDENTIALS_DIR

def _resolver_ruta_config(ruta_relativa):
    ruta = Path(ruta_relativa)
    if not ruta.is_absolute():
        ruta = CREDENTIALS_DIR / ruta.name
    return str(ruta)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .base import MailConnector, MensajeNormalizado

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailOAuthConnector(MailConnector):

    def __init__(self, config_cuenta: dict):
        super().__init__(config_cuenta)
        self._servicio = None
        self._etiqueta_id = None
        self._mensajes_por_id = {}  # id -> payload completo del mensaje (para sacar adjuntos después)

    def conectar(self):
        credentials_path = self.config.get("credentials_path", "credentials.json")
        token_path = self.config.get("token_path", "token.json")

        credentials_path = _resolver_ruta_config(credentials_path)
        token_path = _resolver_ruta_config(token_path)

        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f"No se encontró '{credentials_path}'. Descargalo desde "
                        f"Google Cloud Console (ver README, sección Gmail OAuth2)."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())

        self._servicio = build("gmail", "v1", credentials=creds)

    def desconectar(self):
        # La librería de Google no requiere cierre explícito de sesión.
        pass

    def listar_candidatos(self):
        candidatos = []
        query = "has:attachment"

        siguiente_pagina = None
        while True:
            resultado = (
                self._servicio.users()
                .messages()
                .list(userId="me", q=query, pageToken=siguiente_pagina)
                .execute()
            )
            mensajes = resultado.get("messages", [])

            for m in mensajes:
                msg_id = m["id"]
                mensaje = (
                    self._servicio.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
                headers = mensaje["payload"].get("headers", [])
                remitente = next((h["value"] for h in headers if h["name"] == "From"), "")
                asunto = next((h["value"] for h in headers if h["name"] == "Subject"), "")
                fecha = next((h["value"] for h in headers if h["name"] == "Date"), "")
                message_id = next((h["value"] for h in headers if h["name"].lower() == "message-id"), msg_id)

                import email.utils
                from datetime import datetime
                try:
                    dt = email.utils.parsedate_to_datetime(fecha)
                    fecha_segura = dt.strftime("%d%m%Y")
                except Exception:
                    fecha_segura = datetime.now().strftime("%d%m%Y")

                self._mensajes_por_id[msg_id] = mensaje
                candidatos.append(
                    MensajeNormalizado(
                        id_interno=msg_id,
                        remitente=remitente,
                        asunto=asunto,
                        fecha=fecha_segura,
                        adjuntos_raw=None,
                        message_id=message_id,
                    )
                )

            siguiente_pagina = resultado.get("nextPageToken")
            if not siguiente_pagina:
                break

        return candidatos

    def _extraer_adjuntos_de_partes(self, msg_id, partes):
        resultado = []
        for parte in partes:
            if parte.get("parts"):
                resultado.extend(self._extraer_adjuntos_de_partes(msg_id, parte["parts"]))
                continue

            filename = parte.get("filename", "")
            if not filename:
                continue

            body = parte.get("body", {})
            attachment_id = body.get("attachmentId")
            if attachment_id:
                adjunto = (
                    self._servicio.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=msg_id, id=attachment_id)
                    .execute()
                )
                data = adjunto["data"]
            else:
                data = body.get("data")
                if not data:
                    continue

            contenido = base64.urlsafe_b64decode(data.encode("UTF-8"))
            resultado.append((filename, contenido))
        return resultado

    def obtener_adjuntos(self, mensaje: MensajeNormalizado):
        mensaje_completo = self._mensajes_por_id[mensaje.id_interno]
        partes = mensaje_completo["payload"].get("parts", [])
        return self._extraer_adjuntos_de_partes(mensaje.id_interno, partes)

    def marcar_procesado(self, mensaje: MensajeNormalizado):
        # Operación de solo lectura en servidor: ya no modificamos etiquetas
        pass
