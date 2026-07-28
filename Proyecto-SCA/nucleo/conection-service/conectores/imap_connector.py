"""
Conector IMAP.

Soporta cualquier cuenta con acceso IMAP: dominios propios (cPanel,
Hostinger, etc.), Zoho, Outlook/Office365, y también Gmail si se usa
una contraseña de aplicación en vez de OAuth2.

Usa la bandera IMAP "Flagged" (la estrellita) para marcar los correos
ya procesados y no descargarlos de nuevo. IMAP guarda esto en el
servidor, así que persiste entre ejecuciones sin necesidad de un
archivo de estado local.
"""

from imap_tools import MailBox, AND, MailMessageFlags

from .base import MailConnector, MensajeNormalizado


class IMAPConnector(MailConnector):

    def __init__(self, config_cuenta: dict):
        super().__init__(config_cuenta)
        self._mailbox = None
        self._mensajes_por_uid = {}  # cache: uid -> objeto msg de imap_tools

    def conectar(self):
        servidor = self.config["servidor"]
        puerto = self.config.get("puerto", 993)
        usuario = self.config["usuario"]
        password = self.config["password"]  # ya resuelta por el router/main
        carpeta = self.config.get("carpeta", "INBOX")

        self._mailbox = MailBox(servidor, port=puerto).login(
            usuario, password, initial_folder=carpeta
        )

    def desconectar(self):
        if self._mailbox:
            self._mailbox.logout()

    def listar_candidatos(self):
        candidatos = []
        criterio = AND(flagged=False)

        for msg in self._mailbox.fetch(criterio, mark_seen=False):
            if not msg.attachments:
                continue

            self._mensajes_por_uid[msg.uid] = msg
            candidatos.append(
                MensajeNormalizado(
                    id_interno=msg.uid,
                    remitente=msg.from_,
                    asunto=msg.subject,
                    fecha=msg.date_str,
                    adjuntos_raw=msg.attachments,
                )
            )
        return candidatos

    def obtener_adjuntos(self, mensaje: MensajeNormalizado):
        resultado = []
        for adj in mensaje.adjuntos_raw:
            resultado.append((adj.filename or "", adj.payload))
        return resultado

    def marcar_procesado(self, mensaje: MensajeNormalizado):
        self._mailbox.flag(mensaje.id_interno, MailMessageFlags.FLAGGED, True)
