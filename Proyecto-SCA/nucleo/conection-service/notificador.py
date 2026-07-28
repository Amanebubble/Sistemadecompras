"""
Notificador de errores.

Cuando una cuenta falla incluso después de reintentar (contraseña
vencida, servidor caído, etc.), este módulo avisa por correo y/o Slack,
según lo que esté activado en settings.json. No lanza excepciones si
el envío falla — solo lo imprime en consola, para no interrumpir el
procesamiento del resto de las cuentas.
"""

import json
import os
import smtplib
import urllib.request
from email.mime.text import MIMEText


def notificar_error(settings: dict, asunto: str, mensaje: str):
    config_notif = settings.get("notificaciones", {})

    config_email = config_notif.get("email", {})
    if config_email.get("activo"):
        _enviar_email(config_email, asunto, mensaje)

    config_slack = config_notif.get("slack", {})
    if config_slack.get("activo"):
        _enviar_slack(config_slack, f"*{asunto}*\n{mensaje}")


def _enviar_email(config_email: dict, asunto: str, mensaje: str):
    try:
        password_env = config_email.get("password_env", "")
        password = os.environ.get(password_env, "")
        if not password:
            print(f"  [notificador] Falta la variable de entorno {password_env}, no se pudo enviar el correo de aviso.")
            return

        msg = MIMEText(mensaje)
        msg["Subject"] = asunto
        msg["From"] = config_email["usuario"]
        msg["To"] = ", ".join(config_email.get("destinatarios", []))

        with smtplib.SMTP(config_email["smtp_servidor"], config_email.get("smtp_puerto", 587)) as server:
            server.starttls()
            server.login(config_email["usuario"], password)
            server.sendmail(
                config_email["usuario"],
                config_email.get("destinatarios", []),
                msg.as_string(),
            )
        print("  [notificador] Aviso enviado por correo.")
    except Exception as exc:
        print(f"  [notificador] No se pudo enviar el correo de aviso: {exc}")


def _enviar_slack(config_slack: dict, texto: str):
    try:
        webhook_env = config_slack.get("webhook_url_env", "")
        webhook_url = os.environ.get(webhook_env, "")
        if not webhook_url:
            print(f"  [notificador] Falta la variable de entorno {webhook_env}, no se pudo enviar el aviso a Slack.")
            return

        data = json.dumps({"text": texto}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url, data=data, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
        print("  [notificador] Aviso enviado a Slack.")
    except Exception as exc:
        print(f"  [notificador] No se pudo enviar el aviso a Slack: {exc}")
