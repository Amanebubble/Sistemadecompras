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

        # Para Gmail, intentar acceder a la carpeta Todos los correos por defecto
        # si el usuario no especificó otra carpeta.
        if "gmail.com" in servidor.lower() and carpeta == "INBOX":
            try:
                self._mailbox = MailBox(servidor, port=puerto, timeout=600).login(
                    usuario, password, initial_folder="[Gmail]/Todos"
                )
                print(f"  [Conexión] Autodetectada carpeta '[Gmail]/Todos'")
                return
            except Exception:
                try:
                    self._mailbox = MailBox(servidor, port=puerto, timeout=600).login(
                        usuario, password, initial_folder="[Gmail]/All Mail"
                    )
                    print(f"  [Conexión] Autodetectada carpeta '[Gmail]/All Mail'")
                    return
                except Exception:
                    pass

        # Fallback normal
        self._mailbox = MailBox(servidor, port=puerto, timeout=600).login(
            usuario, password, initial_folder=carpeta
        )
        print(f"  [Conexión] Usando carpeta '{carpeta}'")

    def desconectar(self):
        if self._mailbox:
            self._mailbox.logout()

    def listar_candidatos(self):
        import json
        import os
        from pathlib import Path
        
        estado_file = Path(__file__).resolve().parent.parent / "estado_imap.json"
        estado_data = {}
        if estado_file.exists():
            try:
                with open(estado_file, "r", encoding="utf-8") as f:
                    estado_data = json.load(f)
            except Exception:
                pass
                
        cuenta_id = f"{self.config['usuario']}_{self._mailbox.folder.get()}"
        ultimo_uid = estado_data.get(cuenta_id, 1)

        candidatos = []
        if ultimo_uid > 1:
            criterio = f"UID {ultimo_uid}:*"
            print(f"  [Conexión] Sincronización Incremental (UID {ultimo_uid} en adelante)...")
        else:
            criterio = "ALL"
            print(f"  [Conexión] Sincronización Masiva Histórica detectada. Obteniendo TODOS los correos (puede tardar varios minutos)...")

        max_uid_visto = ultimo_uid

        # headers_only=True descarga solo asunto, remitente, uid, etc. (muy rápido)
        for msg in self._mailbox.fetch(criterio, mark_seen=False, headers_only=True):
            try:
                current_uid = int(msg.uid)
                if current_uid > max_uid_visto:
                    max_uid_visto = current_uid
            except ValueError:
                pass
                
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
                    adjuntos_raw=[], # Lo dejamos vacío, se descarga bajo demanda
                    message_id=message_id,
                )
            )
            
        # Guardar el nuevo estado si vimos algo nuevo
        if max_uid_visto > ultimo_uid:
            estado_data[cuenta_id] = max_uid_visto
            try:
                with open(estado_file, "w", encoding="utf-8") as f:
                    json.dump(estado_data, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"  [!] Error guardando estado IMAP: {e}")

        return candidatos

    def obtener_adjuntos(self, mensaje: MensajeNormalizado):
        resultado = []
        # Descargar el mensaje completo (cuerpo y adjuntos) solo para este UID
        for msg in self._mailbox.fetch(f"{mensaje.id_interno}", mark_seen=False):
            for adj in msg.attachments:
                resultado.append((adj.filename or "", adj.payload))
            break # Solo debería haber uno
        return resultado

    def marcar_procesado(self, mensaje: MensajeNormalizado):
        # Operación de solo lectura en servidor: ya no modificamos banderas
        pass
