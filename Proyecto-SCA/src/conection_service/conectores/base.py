"""
Interfaz común para cualquier conector de correo.

El Manager (gestor_dte.py) solo conoce esta interfaz. No sabe ni le
importa si por debajo hay IMAP, POP3, o cualquier otro protocolo que se
agregue en el futuro. Esto es lo que permite que el sistema sea
"modular": para soportar un protocolo nuevo, solo hay que crear una
clase nueva que herede de MailConnector e implementar estos métodos.
"""

from abc import ABC, abstractmethod


class MensajeNormalizado:
    """Representación uniforme de un correo, sin importar el protocolo
    de origen. Los conectores concretos deben devolver una lista de
    estos objetos."""

    def __init__(self, id_interno, remitente, asunto, fecha, adjuntos_raw, message_id):
        self.id_interno = id_interno      # ID único dentro de esa cuenta (UID de IMAP, número de mensaje en POP3, etc.)
        self.remitente = remitente
        self.asunto = asunto or ""
        self.fecha = fecha or ""
        self.adjuntos_raw = adjuntos_raw  # lista de objetos específicos del protocolo, se procesan con obtener_adjuntos()
        self.message_id = message_id      # Message-ID persistente del correo


class MailConnector(ABC):
    """Clase base abstracta. Cualquier conector nuevo (IMAP, POP3, etc.)
    debe heredar de esta clase e implementar todos estos métodos."""

    def __init__(self, config_cuenta: dict):
        """config_cuenta trae, como mínimo:
        {
            "nombre": "Despacho - Facturas",
            "protocolo": "imap" | "pop3",
            "servidor": "jc-foodservice.com",
            "puerto": 993,
            "usuario": "facturacionelectronica@jc-foodservice.com",
            "password_env": "JC_FOODSERVICE_PASSWORD"  # nombre de variable de entorno, no la contraseña en sí
        }
        """
        self.config = config_cuenta

    @abstractmethod
    def conectar(self):
        """Abre la conexión con el servidor de correo."""
        raise NotImplementedError

    @abstractmethod
    def desconectar(self):
        """Cierra la conexión de forma segura."""
        raise NotImplementedError

    @abstractmethod
    def listar_candidatos(self) -> list[MensajeNormalizado]:
        """Devuelve los mensajes que aún no han sido procesados y que
        tienen al menos un adjunto (filtro mínimo a nivel de protocolo;
        el filtrado fino de contenido lo hace el Manager)."""
        raise NotImplementedError

    @abstractmethod
    def obtener_adjuntos(self, mensaje: MensajeNormalizado) -> list[tuple[str, bytes]]:
        """Devuelve una lista de tuplas (nombre_archivo, contenido_bytes)
        para los adjuntos de ese mensaje."""
        raise NotImplementedError

    @abstractmethod
    def marcar_procesado(self, mensaje: MensajeNormalizado):
        """Marca el mensaje como ya procesado para no repetirlo en la
        siguiente corrida."""
        raise NotImplementedError
