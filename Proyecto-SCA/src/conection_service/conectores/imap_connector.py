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

        self._mailbox = MailBox(servidor, port=puerto, timeout=30).login(
            usuario, password, initial_folder=carpeta
        )

    def desconectar(self):
        if self._mailbox:
            self._mailbox.logout()

    def listar_candidatos(self):
        candidatos = []
        # Eliminado filtro por flagged=False, ahora traemos todos
        criterio = "ALL"

        for msg in self._mailbox.fetch(criterio, mark_seen=False):
            if not msg.attachments:
                continue

            message_id = msg.headers.get('message-id', [msg.uid])[0]
            if isinstance(message_id, bytes):
                message_id = message_id.decode('utf-8', errors='ignore')

            import email.utils
            from datetime import datetime
            
            try:
                dt = email.utils.parsedate_to_datetime(msg.date_str)
                fecha_segura = dt.strftime("%d%m%Y")
            except Exception:
                fecha_segura = datetime.now().strftime("%d%m%Y")

            self._mensajes_por_uid[msg.uid] = msg
            candidatos.append(
                MensajeNormalizado(
                    id_interno=msg.uid,
                    remitente=msg.from_,
                    asunto=msg.subject,
                    fecha=fecha_segura,
                    adjuntos_raw=msg.attachments,
                    message_id=message_id,
                )
            )
        return candidatos

    def obtener_adjuntos(self, mensaje: MensajeNormalizado):
        resultado = []
        for adj in mensaje.adjuntos_raw:
            resultado.append((adj.filename or "", adj.payload))
        return resultado

    def marcar_procesado(self, mensaje: MensajeNormalizado):
        # Operación de solo lectura en servidor: ya no modificamos banderas
        pass
