"""
Punto de entrada del sistema.

Flujo:
  1. Lee settings.json (carpeta de descargas, reintentos, notificaciones).
  2. Lee accounts.json (la lista de buzones a revisar).
  3. Para cada cuenta, resuelve la contraseña desde una variable de
     entorno (nunca queda escrita en accounts.json).
  4. El ROUTER (conectores/router.py) elige el conector correcto según
     el protocolo declarado (imap/pop3/gmail_oauth).
  5. El MANAGER (gestor_dte.py) usa ese conector para filtrar, validar
     y descargar los DTE, sin importarle qué protocolo hay detrás.
  6. Si una cuenta falla, se reintenta automáticamente (con espera
     entre intentos). Si sigue fallando después de agotar los
     reintentos, se envía una notificación (correo y/o Slack, según
     settings.json) y se continúa con las demás cuentas.

Para agregar una cuenta nueva: solo hay que agregar un bloque más en
accounts.json y definir su variable de entorno con la contraseña. No
hace falta tocar código.
"""

import json
import os
import time
from pathlib import Path

# Raíz del proyecto: <raiz>/nucleo/conection-service/main.py -> <raiz>
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent.parent

from conectores import crear_conector
from gestor_dte import GestorDTE
from notificador import notificar_error

ARCHIVO_CUENTAS = "accounts.json"
ARCHIVO_SETTINGS = "settings.json"


def cargar_settings():
    with open(ARCHIVO_SETTINGS, "r", encoding="utf-8") as f:
        return json.load(f)


def cargar_cuentas():
    with open(ARCHIVO_CUENTAS, "r", encoding="utf-8") as f:
        cuentas = json.load(f)

    for cuenta in cuentas:
        # gmail_oauth no usa contraseña, usa credentials.json/token.json
        if cuenta.get("protocolo") == "gmail_oauth":
            continue

        variable_password = cuenta.get("password_env")
        password = os.environ.get(variable_password, "") if variable_password else ""

        if not password:
            import getpass
            password = getpass.getpass(
                f"Contraseña para {cuenta['usuario']} "
                f"(o exportá {variable_password} como variable de entorno): "
            )

        cuenta["password"] = password

    return cuentas


def procesar_cuenta_con_reintentos(config_cuenta, settings):
    """Intenta procesar una cuenta hasta agotar los reintentos definidos
    en settings.json. Devuelve el resultado o None si falló siempre."""
    nombre = config_cuenta.get("nombre", config_cuenta.get("usuario", "cuentasin nombre"))
    max_intentos = settings.get("reintentos_por_cuenta", 3)
    espera = settings.get("espera_entre_reintentos_segundos", 10)

    ultimo_error = None

    for intento in range(1, max_intentos + 1):
        conector = crear_conector(config_cuenta)
        gestor = GestorDTE(
            carpeta_descargas=settings.get("carpeta_descargas", "facturas_descargadas"),
            archivo_log=settings.get("archivo_log", "log.csv"),
            palabras_clave_asunto=config_cuenta.get("palabras_clave_asunto", []),
        )
        try:
            conector.conectar()
            resultado = gestor.procesar_cuenta(nombre, conector)
            return resultado
        except Exception as exc:
            ultimo_error = exc
            print(f"  Intento {intento}/{max_intentos} falló para '{nombre}': {exc}")
            if intento < max_intentos:
                print(f"  Reintentando en {espera} segundos...")
                time.sleep(espera)
        finally:
            try:
                conector.desconectar()
            except Exception:
                pass
            gestor.cerrar()

    # Si llegamos acá, se agotaron los reintentos
    mensaje = (
        f"No se pudo procesar la cuenta '{nombre}' después de {max_intentos} intentos.\n"
        f"Último error: {ultimo_error}"
    )
    print(f"  {mensaje}")
    notificar_error(
        settings,
        asunto=f"[Sistema DTE] Falló la cuenta '{nombre}'",
        mensaje=mensaje,
    )
    return None


def main():
    settings = cargar_settings()

    carpeta_rel = settings.get("carpeta_descargas", "Descarga-doc")
    carpeta_descargas = str(RAIZ_PROYECTO / carpeta_rel)
    settings["carpeta_descargas"] = carpeta_descargas
    os.makedirs(carpeta_descargas, exist_ok=True)

    cuentas = cargar_cuentas()

    resumen_total = {"cuentas_ok": 0, "cuentas_error": 0, "descargados": 0}

    for config_cuenta in cuentas:
        nombre = config_cuenta.get("nombre", config_cuenta["usuario"])
        print(f"\n=== Procesando cuenta: {nombre} ({config_cuenta['protocolo']}) ===")

        resultado = procesar_cuenta_con_reintentos(config_cuenta, settings)

        if resultado is not None:
            print(
                f"  Revisados: {resultado['revisados']} | "
                f"Descargados: {resultado['descargados']}"
            )
            resumen_total["cuentas_ok"] += 1
            resumen_total["descargados"] += resultado["descargados"]
        else:
            resumen_total["cuentas_error"] += 1

    print("\n=== Resumen general ===")
    print(f"Cuentas procesadas correctamente: {resumen_total['cuentas_ok']}")
    print(f"Cuentas con error: {resumen_total['cuentas_error']}")
    print(f"Total de facturas descargadas: {resumen_total['descargados']}")
    print(f"Carpeta de descargas: {os.path.abspath(carpeta_descargas)}")


if __name__ == "__main__":
    main()
