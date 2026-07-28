# Sistema modular de descarga de DTE (Router + Manager)

Sistema que se conecta a **cualquier cantidad de cuentas de correo**
(IMAP, POP3, o Gmail con OAuth2) y descarga únicamente las facturas
electrónicas (DTE) adjuntas, validando su estructura antes de guardarlas.

Instalación pensada para tu equipo Windows, con el proyecto en:

```
C:\Users\Lenovo P52s\Desktop\Proyecto-SCA\conection-service
```

Y las facturas descargadas guardándose en:

```
C:\Users\Lenovo P52s\Desktop\Proyecto-SCA\Descarga-doc
```

Esa ruta ya está configurada en `settings.json` — no hace falta tocar
código para eso.

---

## 1. Checklist de requerimientos (instalar antes de usar)

| # | Requisito | Cómo verificar / instalar |
|---|---|---|
| 1 | **Python 3.10 o superior** | Abrí PowerShell y corré `python --version`. Si no lo tenés, descargalo de https://www.python.org/downloads/ (marcá la casilla "Add Python to PATH" durante la instalación). |
| 2 | **pip actualizado** | `python -m pip install --upgrade pip` |
| 3 | **Dependencias del proyecto** | Ver paso 2 más abajo (`requirements.txt`) |
| 4 | **Acceso IMAP habilitado** en cada cuenta de correo (dominios propios normalmente lo tienen activo por defecto; en Gmail vía IMAP con contraseña de app hay que habilitarlo manualmente) | Revisar en la configuración de seguridad del proveedor de cada correo |
| 5 | **Credenciales de Google Cloud** (solo si vas a usar `gmail_oauth` para el correo del dueño) | Ver sección 5 de este README |
| 6 | Carpeta de descargas creada | El script la crea sola si no existe, pero confirmá que la ruta en `settings.json` sea correcta para tu máquina |

---

## 2. Instalación de dependencias

Abrí PowerShell **dentro de la carpeta del proyecto**:

```powershell
cd "C:\Users\Lenovo P52s\Desktop\Proyecto-SCA\conection-service"
pip install -r requirements.txt
```

`requirements.txt` instala:
- `imap-tools` — para las cuentas IMAP.
- `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib` — solo necesarias si usás una cuenta `gmail_oauth`. Si no vas a usar Gmail con OAuth2 en el corto plazo, podés omitir esas tres líneas del archivo sin problema.

(`poplib`, `smtplib`, `email`, `json`, `urllib` son parte de la librería estándar de Python — no requieren instalación aparte.)

---

## 3. Estructura del proyecto

```
conection-service/
├── settings.json               <- Config global: carpeta de descargas, reintentos, notificaciones
├── accounts.json                <- Lista de cuentas de correo a revisar
├── main.py                      <- Punto de entrada
├── gestor_dte.py                 <- El "Manager": filtra, valida, descarga, loguea
├── notificador.py                <- Avisos por correo/Slack cuando una cuenta falla
├── requirements.txt
└── conectores/
    ├── base.py                    <- Interfaz común (contrato) para cualquier conector
    ├── imap_connector.py          <- Implementación IMAP
    ├── pop3_connector.py          <- Implementación POP3
    ├── gmail_oauth_connector.py   <- Implementación Gmail API (OAuth2)
    └── router.py                   <- El "Router": elige el conector según el protocolo
```

---

## 4. Configurar `settings.json`

```json
{
  "carpeta_descargas": "C:\\Users\\Lenovo P52s\\Desktop\\Proyecto-SCA\\Descarga-doc",
  "archivo_log": "log.csv",
  "reintentos_por_cuenta": 3,
  "espera_entre_reintentos_segundos": 10,
  "notificaciones": {
    "email": { "activo": false, ... },
    "slack": { "activo": false, ... }
  }
}
```

- **`carpeta_descargas`**: ya está apuntando a tu ruta. En JSON, cada
  `\` de una ruta de Windows se escribe doble (`\\`) — ya está así en
  el archivo, no hace falta que lo edites a mano.
- **`reintentos_por_cuenta`** y **`espera_entre_reintentos_segundos`**:
  si una cuenta falla (servidor caído, contraseña vencida), el sistema
  reintenta automáticamente esa cantidad de veces, esperando esos
  segundos entre intento e intento.
- **`notificaciones`**: dejalas en `"activo": false` hasta que quieras
  activarlas (ver sección 6).

---

## 5. Configurar `accounts.json` — las 3 formas de conectar

Cada cuenta es un bloque en el array. `"protocolo"` define qué conector
usa el Router.

### a) IMAP (dominios propios, cPanel, Zoho, Outlook, o Gmail con contraseña de app)

```json
{
  "nombre": "JC-Foodservice - Facturacion",
  "protocolo": "imap",
  "servidor": "jc-foodservice.com",
  "puerto": 993,
  "usuario": "facturacionelectronica@jc-foodservice.com",
  "password_env": "PASS_JC_FOODSERVICE",
  "carpeta": "INBOX",
  "palabras_clave_asunto": []
}
```

### b) POP3

```json
{
  "nombre": "Cliente Ejemplo - POP3",
  "protocolo": "pop3",
  "servidor": "mail.clienteejemplo.com",
  "puerto": 995,
  "usuario": "facturas@clienteejemplo.com",
  "password_env": "PASS_CLIENTE_EJEMPLO",
  "palabras_clave_asunto": ["DTE", "factura", "CCF", "comprobante"]
}
```

### c) Gmail con OAuth2 (recomendado para el correo personal del dueño)

```json
{
  "nombre": "Despacho - Gmail dueño",
  "protocolo": "gmail_oauth",
  "usuario": "dueno@gmail.com",
  "credentials_path": "credentials_dueno.json",
  "token_path": "token_dueno.json",
  "palabras_clave_asunto": ["DTE", "factura", "CCF", "comprobante"]
}
```

Para esta opción necesitás generar `credentials_dueno.json` una sola vez:

1. Entrá a https://console.cloud.google.com/
2. Creá un proyecto (ej. "Sistema DTE Despacho").
3. **APIs y servicios > Biblioteca** → buscá **Gmail API** → **Habilitar**.
4. **APIs y servicios > Pantalla de consentimiento OAuth** → tipo **Externo** → agregá el correo del dueño en "Usuarios de prueba".
5. **APIs y servicios > Credenciales > Crear credenciales > ID de cliente de OAuth** → tipo **Aplicación de escritorio**.
6. Descargá el JSON generado, renombralo a `credentials_dueno.json` y ponelo en la carpeta del proyecto.
7. La primera vez que corras `main.py`, se abrirá el navegador para que el dueño autorice el acceso. Después se genera `token_dueno.json` y se refresca solo — no vuelve a pedir login.

No hace falta contraseña para esta cuenta en `accounts.json` (el campo `password_env` se ignora para `gmail_oauth`).

### Contraseñas (para `imap` y `pop3`)

**Nunca** se escriben en `accounts.json`. Se leen desde variables de entorno. En PowerShell, antes de correr el script:

```powershell
$env:PASS_JC_FOODSERVICE = "la_contraseña_real"
$env:PASS_CLIENTE_EJEMPLO = "otra_contraseña"
```

Si no las definís, el script te las va a pedir por consola (oculto) al momento de correr.

> Para que estas variables persistan entre reinicios de PowerShell (útil si vas a automatizar con el Programador de tareas), configuralas como variables de entorno del sistema: Panel de Control → Sistema → Configuración avanzada → Variables de entorno.

---

## 6. Notificaciones cuando una cuenta falla (opcional)

En `settings.json`, activá lo que quieras usar:

```json
"notificaciones": {
  "email": {
    "activo": true,
    "smtp_servidor": "smtp.gmail.com",
    "smtp_puerto": 587,
    "usuario": "alertas@tudespacho.com",
    "password_env": "NOTIF_EMAIL_PASSWORD",
    "destinatarios": ["dueno@tudespacho.com"]
  },
  "slack": {
    "activo": true,
    "webhook_url_env": "SLACK_WEBHOOK_URL"
  }
}
```

- **Email**: usa SMTP estándar (funciona con Gmail usando una contraseña de aplicación, o cualquier otro proveedor). Definí `NOTIF_EMAIL_PASSWORD` como variable de entorno.
- **Slack**: necesitás crear un "Incoming Webhook" en tu workspace de Slack (Slack → Administrar apps → Incoming Webhooks) y poner esa URL en la variable de entorno `SLACK_WEBHOOK_URL`.

Si una cuenta falla después de agotar los reintentos definidos en `settings.json`, se envía el aviso automáticamente con el nombre de la cuenta y el error, y el sistema sigue procesando las demás cuentas normalmente.

---

## 7. Ejecutar

```powershell
cd "C:\Users\Lenovo P52s\Desktop\Proyecto-SCA\conection-service"
python main.py
```

Salida esperada:

```
=== Procesando cuenta: JC-Foodservice - Facturacion (imap) ===
  -> [JC-Foodservice - Facturacion] Descargado: C:\Users\Lenovo P52s\Desktop\Proyecto-SCA\Descarga-doc\...
  Revisados: 12 | Descargados: 9

=== Procesando cuenta: Despacho - Gmail dueño (gmail_oauth) ===
  Revisados: 5 | Descargados: 3

=== Resumen general ===
Cuentas procesadas correctamente: 2
Cuentas con error: 0
Total de facturas descargadas: 12
Carpeta de descargas: C:\Users\Lenovo P52s\Desktop\Proyecto-SCA\Descarga-doc
```

Todo queda en:
- **`Descarga-doc\`** (la ruta configurada) — los archivos JSON/PDF descargados, con el nombre de la cuenta como prefijo para que no se mezclen entre despachos/clientes.
- **`log.csv`** — detalle de cada descarga (cuenta, remitente, asunto, fecha, ruta local, código de generación del DTE).

---

## 8. Automatizar con el Programador de tareas de Windows

1. Abrí **Programador de tareas** → **Crear tarea básica**.
2. Desencadenador: por ejemplo, "Diariamente" repitiendo cada X horas, o al iniciar sesión.
3. Acción: **Iniciar un programa**.
   - Programa: la ruta a `python.exe` (verificala con `where python` en PowerShell).
   - Argumentos: `main.py`
   - Iniciar en: `C:\Users\Lenovo P52s\Desktop\Proyecto-SCA\conection-service`
4. En la pestaña **Condiciones/Configuración**, asegurate de que la tarea corra aunque no haya sesión iniciada si querés que funcione sin que el dueño tenga la PC abierta (requiere guardar la contraseña de Windows de la cuenta que ejecuta la tarea).
5. Importante: las variables de entorno con las contraseñas deben estar configuradas como **variables de entorno del sistema** (no solo de sesión de PowerShell) para que el Programador de tareas las vea.

---

## 9. Cómo evita reprocesar correos

- **IMAP**: usa la bandera "Destacado" (⭐) del servidor. Persiste sola.
- **Gmail OAuth2**: usa una etiqueta `DTE-Procesado` en la cuenta de Gmail.
- **POP3**: guarda un registro local en `estado_pop3\<nombre_cuenta>.json` con los IDs (UIDL) ya vistos. No borres esa carpeta o se volverá a descargar todo.

---

## 10. Agregar una cuenta nueva (ej. un cliente nuevo del despacho)

1. Conseguí sus datos de servidor (servidor, puerto, usuario, tipo de seguridad — como el pantallazo de configuración que ya usaste).
2. Agregá un bloque nuevo en `accounts.json`.
3. Si es IMAP/POP3: exportá su contraseña en la variable de entorno correspondiente. Si es Gmail OAuth2: generá sus credenciales según la sección 5c.
4. Corré `python main.py` de nuevo — no hace falta tocar el resto del código.
