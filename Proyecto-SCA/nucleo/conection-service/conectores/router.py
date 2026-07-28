"""
Router de conectores.

Esta es la pieza que decide, para cada cuenta configurada en
accounts.json, qué conector concreto usar (IMAP o POP3). Es el único
lugar del sistema que conoce la lista de protocolos soportados — si en
el futuro agregás uno nuevo, solo hay que registrar su clase acá.
"""

from .base import MailConnector
from .imap_connector import IMAPConnector
from .pop3_connector import POP3Connector
from .gmail_oauth_connector import GmailOAuthConnector

_REGISTRO_PROTOCOLOS = {
    "imap": IMAPConnector,
    "pop3": POP3Connector,
    "gmail_oauth": GmailOAuthConnector,
}


def crear_conector(config_cuenta: dict) -> MailConnector:
    protocolo = config_cuenta.get("protocolo", "").lower()

    clase_conector = _REGISTRO_PROTOCOLOS.get(protocolo)
    if clase_conector is None:
        disponibles = ", ".join(_REGISTRO_PROTOCOLOS.keys())
        raise ValueError(
            f"Protocolo '{protocolo}' no soportado para la cuenta "
            f"'{config_cuenta.get('nombre', config_cuenta.get('usuario'))}'. "
            f"Protocolos disponibles: {disponibles}."
        )

    return clase_conector(config_cuenta)
