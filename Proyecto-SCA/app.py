"""
SCA ETL Pipeline — Servidor Web Flask.
Punto de entrada único para administrar el pipeline desde el navegador.
"""

import sys
from pathlib import Path
import os
import subprocess
import glob
from flask import Flask, render_template, jsonify, request, send_from_directory
import webbrowser
from threading import Timer
import json
import shutil
import re

# Configuración Dinámica de sys.path para Portabilidad Total
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config import (
    CARPETA_DESCARGAS, CARPETA_COLA1, CARPETA_COLA0, CARPETA_PROCESADOS, 
    CARPETA_RESPALDO, CARPETA_REVISION, CARPETA_ERRORES, CARPETA_REPORTES, CARPETA_OTROS_DTES,
    ARCHIVO_CUENTAS, CREDENTIALS_DIR, RAIZ_PROYECTO, SRC_DIR
)

BASE_DIR = RAIZ_PROYECTO
ENV_FILE = BASE_DIR / ".env"

app = Flask(
    __name__,
    template_folder=str(SRC_DIR / "templates"),
)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/stats')
def get_stats():
    def count_files(dir_path):
        return len([f for f in dir_path.glob("*") if f.is_file()]) if dir_path.exists() else 0

    return jsonify({
        "descarga_count": count_files(CARPETA_DESCARGAS),
        "cola1_count": count_files(CARPETA_COLA1),
        "cola0_count": count_files(CARPETA_COLA0),
        "procesados_count": count_files(CARPETA_PROCESADOS),
        "respaldo_count": count_files(CARPETA_RESPALDO),
        "revision_count": count_files(CARPETA_REVISION),
        "otros_dtes_count": count_files(CARPETA_OTROS_DTES),
    })


@app.route('/api/run/conection', methods=['POST'])
def run_conection():
    try:
        conection_main = SRC_DIR / "conection_service" / "main.py"
        result = subprocess.run(
            [sys.executable, str(conection_main)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONNOUSERSITE": "1"},
        )
        return jsonify({"success": result.returncode == 0, "output": result.stdout + "\n" + result.stderr})
    except Exception as e:
        return jsonify({"success": False, "output": str(e)})


@app.route('/api/run/filtro', methods=['POST'])
def run_filtro():
    try:
        # Ya no hay main en filtro, pero podemos lanzar orquestador con un flag o crear un wrapper
        # Por ahora lo dejamos atado a orquestador general
        return jsonify({"success": False, "output": "Filtro standalone deshabilitado, use Ejecutar Todo."})
    except Exception as e:
        return jsonify({"success": False, "output": str(e)})


@app.route('/api/run/conversor0', methods=['POST'])
def run_conversor0():
    try:
        return jsonify({"success": False, "output": "Conversor standalone deshabilitado, use Ejecutar Todo."})
    except Exception as e:
        return jsonify({"success": False, "output": str(e)})


@app.route('/api/run/conversor1', methods=['POST'])
def run_conversor1():
    try:
        conversor_main = SRC_DIR / "conversor_pdf" / "extractor_pdf.py"
        result = subprocess.run(
            [sys.executable, str(conversor_main)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONNOUSERSITE": "1"},
        )
        return jsonify({"success": result.returncode == 0, "output": result.stdout + "\n" + result.stderr})
    except Exception as e:
        return jsonify({"success": False, "output": str(e)})


@app.route('/api/reportes/lista', methods=['GET'])
def get_reportes_lista():
    from src.config import RUTA_BD_CONTROL
    import sqlite3
    try:
        if not os.path.exists(RUTA_BD_CONTROL):
            return jsonify({"success": True, "reportes": []})
        conn = sqlite3.connect(RUTA_BD_CONTROL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='libro_compras'")
        if not cursor.fetchone():
            return jsonify({"success": True, "reportes": []})
            
        cursor.execute("SELECT DISTINCT cliente, ano, mes FROM libro_compras")
        combinaciones = cursor.fetchall()
        reportes = []
        for c in combinaciones:
            reportes.append({"cliente": c[0], "ano": c[1], "mes": c[2]})
        

            
        conn.close()
        return jsonify({"success": True, "reportes": reportes})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/reportes/descargar/<cliente>/<ano>/<mes>', methods=['GET'])
def descargar_reporte(cliente, ano, mes):
    from flask import send_file
    try:
        from src.generador_excel import GeneradorExcel
        gen = GeneradorExcel()
        # Generar el excel en demanda (esto consultara la DB y sobreescribira/creara el archivo)
        ruta_archivo = gen.generar_reporte(cliente, int(ano), int(mes))
        if not ruta_archivo:
            return jsonify({"success": False, "error": "No hay datos para generar el reporte"}), 404
            
        return send_file(ruta_archivo, as_attachment=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

# Estado Global del Daemon
pipeline_status = {
    "estado_general": "Inactivo",
    "activo": False,
    "fase": "inactivo",
    "archivo": "",
    "progreso": 0,
    "logs": [],
    "error": False,
    "terminado": False,
    "estadisticas": {
        "correos_leidos": 0,
        "pdfs_extraidos": 0,
        "excels_generados": 0,
        "errores_imap": 0,
        "errores_pdf": 0,
        "errores_json": 0
    }
}

orquestador_process = None

def run_pipeline_background():
    global pipeline_status, orquestador_process
    import time
    
    pipeline_status["estado_general"] = "Procesando"
    pipeline_status["activo"] = True
    pipeline_status["fase"] = "Iniciando Orquestador Continuo"
    pipeline_status["progreso"] = 0
    pipeline_status["logs"] = ["=== Iniciando Motor Continuo ==="]
    pipeline_status["terminado"] = False
    pipeline_status["error"] = False
    pipeline_status["estadisticas"] = {
        "correos_leidos": 0,
        "pdfs_extraidos": 0,
        "excels_generados": 0,
        "errores_imap": 0,
        "errores_pdf": 0,
        "errores_json": 0
    }

    pipeline_status["nivel_semaforo"] = "active"

    cmd = [sys.executable, "-u", str(SRC_DIR / "orquestador.py")]
    
    try:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "PYTHONNOUSERSITE": "1"}
        orquestador_process = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1
        )
        
        for line in iter(orquestador_process.stdout.readline, ''):
            if not pipeline_status["activo"]:
                break
                
            line_stripped = line.strip()
            if not line_stripped:
                continue
                
            if "Procesando:" in line_stripped:
                pipeline_status["archivo"] = line_stripped.split("Procesando:")[-1].strip()
                
            if "DTE Extraído" in line_stripped or "Descargado:" in line_stripped:
                pipeline_status["estadisticas"]["correos_leidos"] += 1
            elif "Datos extraídos y enviados" in line_stripped:
                pipeline_status["estadisticas"]["pdfs_extraidos"] += 1
            elif "[OK] Creado:" in line_stripped or "Insertado/Actualizado DTE" in line_stripped:
                pipeline_status["estadisticas"]["excels_generados"] += 1
                
            # Fases del stream
            if "[FASE:" in line_stripped:
                pipeline_status["fase"] = line_stripped.split("[FASE:")[1].split("]")[0]
                
            # Semáforo jerárquico
            if "[SEMAFORO:" in line_stripped:
                nivel = line_stripped.split("[SEMAFORO:")[1].split("]")[0]
                pipeline_status["nivel_semaforo"] = nivel
                
            is_error = "[!]" in line_stripped or "[X]" in line_stripped or "Error" in line_stripped or "Exception" in line_stripped or "Fallo" in line_stripped
            
            if is_error:
                pipeline_status["error"] = True
                fase = pipeline_status.get("fase", "")
                if fase == "conection_service":
                    pipeline_status["estadisticas"]["errores_imap"] += 1
                elif fase == "conversor1_pdf":
                    pipeline_status["estadisticas"]["errores_pdf"] += 1
                elif fase == "conversor0_json":
                    pipeline_status["estadisticas"]["errores_json"] += 1
            
            pipeline_status["logs"].append(line_stripped)
            # Mantener solo los últimos 150 logs en memoria para la consola
            if len(pipeline_status["logs"]) > 150:
                pipeline_status["logs"] = pipeline_status["logs"][-150:]
        
        if orquestador_process:
            orquestador_process.stdout.close()
            orquestador_process.wait()
            
    except Exception as e:
        pipeline_status["logs"].append(f"[!] Excepción crítica: {str(e)}")
        pipeline_status["error"] = True
        pipeline_status["estado_general"] = "Completado con errores"
        pipeline_status["nivel_semaforo"] = "critical"
        
    pipeline_status["fase"] = "Detenido"
    pipeline_status["logs"].append("Pipeline detenido.")
    pipeline_status["terminado"] = True
    pipeline_status["activo"] = False
    pipeline_status["estado_general"] = "Inactivo"

@app.route('/api/run/all', methods=['POST'])
def run_all():
    global pipeline_status
    import threading
    
    if pipeline_status["activo"]:
        return jsonify({"success": False, "message": "El motor continuo ya está en ejecución"})
        
    thread = threading.Thread(target=run_pipeline_background)
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "Motor continuo iniciado"})

@app.route('/api/run/stop', methods=['POST'])
def stop_pipeline():
    global pipeline_status, orquestador_process
    if not pipeline_status["activo"]:
        return jsonify({"success": False, "message": "El motor ya está detenido"})
        
    pipeline_status["activo"] = False
    pipeline_status["logs"].append(">>> Solicitud de parada recibida. Abortando motor...")
    
    if orquestador_process:
        try:
            import signal
            # Mata el proceso de forma agresiva para que no se quede bloqueado
            if sys.platform == "win32":
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(orquestador_process.pid)])
            else:
                os.killpg(os.getpgid(orquestador_process.pid), signal.SIGTERM)
        except Exception as e:
            print(f"Error al matar proceso: {e}")
            
    return jsonify({"success": True, "message": "Motor detenido"})

@app.route('/api/errores', methods=['GET'])
def get_errores():
    try:
        import sqlite3
        db_path = SRC_DIR / "auditoria.db"
        if not db_path.exists():
            return jsonify({"success": True, "errores": []})
            
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT fecha_hora, modulo, cuenta, mensaje_error FROM registro_errores ORDER BY id DESC LIMIT 50")
            errores = [{"fecha": row[0], "modulo": row[1], "cuenta": row[2], "mensaje": row[3]} for row in cursor.fetchall()]
        return jsonify({"success": True, "errores": errores})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/status', methods=['GET'])
def get_status():
    global pipeline_status
    return jsonify(pipeline_status)


@app.route('/api/reportes/opciones', methods=['GET'])
def get_report_options():
    try:
        import sqlite3
        if not RUTA_BD_CONTROL.exists():
            return jsonify({"success": True, "clientes": []})
            
        conn = sqlite3.connect(RUTA_BD_CONTROL)
        cursor = conn.cursor()
        
        # Obtener clientes únicos
        cursor.execute("SELECT DISTINCT cliente FROM libro_compras WHERE cliente IS NOT NULL AND cliente != '' ORDER BY cliente")
        clientes = [row[0] for row in cursor.fetchall()]
        
        if not clientes:
            return jsonify({"success": True, "clientes": []})
            
        # Para cada cliente, obtener años y meses
        datos = []
        for c in clientes:
            cursor.execute("SELECT DISTINCT ano FROM libro_compras WHERE cliente = ? ORDER BY ano DESC", (c,))
            anos = []
            for row_ano in cursor.fetchall():
                ano = row_ano[0]
                cursor.execute("SELECT DISTINCT mes FROM libro_compras WHERE cliente = ? AND ano = ? ORDER BY mes DESC", (c, ano))
                meses = [row_mes[0] for row_mes in cursor.fetchall()]
                anos.append({"ano": ano, "meses": meses})
            datos.append({"cliente": c, "anos": anos})
            
        conn.close()
        return jsonify({"success": True, "datos": datos})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/reportes/generar', methods=['POST'])
def generar_reporte():
    try:
        data = request.json
        cliente = data.get('cliente')
        ano = data.get('ano')
        mes = data.get('mes')
        
        if not cliente or not ano or not mes:
            return jsonify({"success": False, "error": "Faltan parámetros (cliente, ano, mes)"})
            
        from src.generador_excel import GeneradorExcel
        gen = GeneradorExcel(str(RUTA_BD_CONTROL), str(CARPETA_REPORTES))
        ruta = gen.generar_reporte(cliente, int(ano), int(mes))
        
        if not ruta:
            return jsonify({"success": False, "error": "No hay datos para generar el reporte"})
            
        return jsonify({"success": True, "mensaje": "Reporte generado con éxito", "archivo": Path(ruta).name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/open_explorer', methods=['POST'])
def open_explorer():
    try:
        CARPETA_REPORTES.mkdir(parents=True, exist_ok=True)
        os.startfile(str(CARPETA_REPORTES))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/revision/list')
def revision_list():
    if not CARPETA_REVISION.exists():
        return jsonify({"casos": []})
        
    jsons = list(CARPETA_REVISION.glob('*.json'))
    pdfs_revision = list(CARPETA_REVISION.glob('*.pdf'))
    pdfs_respaldo = list(CARPETA_RESPALDO.glob('*.pdf')) if CARPETA_RESPALDO.exists() else []
    todos_pdfs = pdfs_revision + pdfs_respaldo
    
    patron_uuid = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
    
    casos = []
    for j in jsons:
        if not j.is_file(): continue
        stem = j.stem
        match = patron_uuid.search(stem)
        uuid = match.group(0).upper() if match else stem.upper()
        
        pdf_name = None
        for p in todos_pdfs:
            if uuid in p.name.upper():
                pdf_name = p.name
                break
                
        casos.append({
            "stem": stem,
            "json": j.name,
            "pdf": pdf_name
        })
            
    return jsonify({"casos": casos})

@app.route('/api/revision/file/<path:filename>')
def revision_file(filename):
    if (CARPETA_REVISION / filename).exists():
        return send_from_directory(str(CARPETA_REVISION), filename)
    elif (CARPETA_RESPALDO / filename).exists():
        return send_from_directory(str(CARPETA_RESPALDO), filename)
    return "File not found", 404

@app.route('/api/revision/reinject', methods=['POST'])
def revision_reinject():
    try:
        data = request.json
        stem = data.get('stem')
        if not stem:
            return jsonify({"success": False, "error": "Missing stem"})
            
        # Build Hacienda native JSON format
        hacienda_json = {
            "identificacion": {
                "codigoGeneracion": str(data.get("codigoGeneracion", "")).strip(),
                "numeroControl": str(data.get("numeroControl", "")).strip(),
                "fecEmi": str(data.get("fecEmi", "")).strip(),
                "tipoDte": str(data.get("tipoDte", "")).strip()
            },
            "emisor": {
                "nrc": str(data.get("nrc", "")).strip(),
                "nombre": str(data.get("nombre", "")).strip()
            },
            "resumen": {
                "totalCompra": float(data.get("subTotal") or 0.0),
                "totalGravada": float(data.get("subTotal") or 0.0),
                "totalExenta": float(data.get("exentos") or 0.0),
                "ivaPerci1": float(data.get("ivaPercibido") or 0.0),
                "ivaRete1": float(data.get("ivaRetenido") or 0.0),
                "montoTotalOperacion": float(data.get("totalGeneral") or 0.0),
                "tributos": [
                    {"codigo": "20", "valor": float(data.get("iva") or 0.0)},
                    {"codigo": "D1", "valor": float(data.get("fovial") or 0.0)},
                    {"codigo": "D4", "valor": float(data.get("cotrans") or 0.0)}
                ]
            },
            "selloRecibido": str(data.get("selloRecibido", "")).strip()
        }
        
        # Guardar en cola0
        with open(CARPETA_COLA0 / f"{stem}.json", "w", encoding="utf-8-sig") as f:
            json.dump(hacienda_json, f, indent=4)
            
        # Limpiar originales en Revision_Manual y mover PDF a Respaldo_PDF si está en Revision
        pdf_name = data.get('pdf')
        if pdf_name:
            pdf_path_rev = CARPETA_REVISION / pdf_name
            if pdf_path_rev.exists():
                shutil.move(str(pdf_path_rev), str(CARPETA_RESPALDO / pdf_name))
        
        json_path = CARPETA_REVISION / f"{stem}.json"
        if json_path.exists():
            os.remove(str(json_path))
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/shutdown', methods=['POST', 'GET'])
def shutdown():
    """Apaga el servidor Flask de forma forzada para el modo --noconsole."""
    def kill_server():
        import time
        time.sleep(0.5)
        os._exit(0)
    
    import threading
    threading.Thread(target=kill_server).start()
    return jsonify({"success": True, "message": "Apagando el servidor..."})


# ─── Configuración de Cuentas ───────────────────────────────────────────────
from werkzeug.utils import secure_filename

# Mapeo de proveedores IMAP conocidos
IMAP_SERVERS = {
    "gmail": {"servidor": "imap.gmail.com", "puerto": 993},
    "outlook": {"servidor": "outlook.office365.com", "puerto": 993},
    "yahoo": {"servidor": "imap.mail.yahoo.com", "puerto": 993},
}

def _leer_accounts():
    """Lee accounts.json devolviendo lista vacía si no existe."""
    if not ARCHIVO_CUENTAS.exists():
        return []
    with open(ARCHIVO_CUENTAS, "r", encoding="utf-8") as f:
        return json.load(f)

def _guardar_accounts(cuentas):
    """Escribe la lista de cuentas en accounts.json."""
    with open(ARCHIVO_CUENTAS, "w", encoding="utf-8") as f:
        json.dump(cuentas, f, indent=2, ensure_ascii=False)

def _env_set_key(key, value):
    """Añade o actualiza una variable en el archivo .env de forma segura."""
    lines = []
    found = False
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    
    if not found:
        new_lines.append(f"{key}={value}\n")
    
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    # Inyectar en el proceso actual para que subprocess la herede
    os.environ[key] = value


@app.route('/api/config/accounts', methods=['GET'])
def config_list_accounts():
    """Devuelve la lista de cuentas configuradas con estado de salud."""
    cuentas = _leer_accounts()
    safe_list = []
    
    import socket
    import imaplib
    
    for c in cuentas:
        estado = "Activa"
        color = "green"
        motivo = "Lista para procesar"
        
        protocolo = c.get("protocolo", "")
        
        if protocolo == "gmail_oauth":
            cred_path = CREDENTIALS_DIR / Path(c.get("credentials_path", "")).name
            token_path = CREDENTIALS_DIR / Path(c.get("token_path", "")).name
            
            if not cred_path.exists():
                estado = "Inactiva"
                color = "red"
                motivo = "Falta client_secret.json"
            elif not token_path.exists():
                estado = "Pendiente"
                color = "yellow"
                motivo = "Falta autorizar (Token). Se autorizará en la primera ejecución."
        else:
            # IMAP
            env_key = c.get("password_env", "")
            if not os.environ.get(env_key):
                estado = "Inactiva"
                color = "red"
                motivo = f"Falta contraseña en el .env ({env_key})"
            else:
                # Intento de ping (solo red, no auth, para no bloquear la app con timeouts largos de login)
                servidor = c.get("servidor", "")
                puerto = c.get("puerto", 993)
                try:
                    socket.create_connection((servidor, puerto), timeout=3).close()
                except Exception as e:
                    estado = "Inactiva"
                    color = "red"
                    motivo = f"Servidor inaccesible: {str(e)}"
        
        safe_list.append({
            "nombre": c.get("nombre", ""),
            "usuario": c.get("usuario", ""),
            "protocolo": protocolo,
            "servidor": c.get("servidor", ""),
            "auth_method": "oauth2" if protocolo == "gmail_oauth" else "password",
            "estado": estado,
            "color": color,
            "motivo": motivo
        })
    return jsonify({"accounts": safe_list})


@app.route('/api/config/account', methods=['POST'])
def config_add_account():
    """Agrega una nueva cuenta de correo al sistema."""
    try:
        nombre = request.form.get("nombre", "").strip()
        correo = request.form.get("correo", "").strip()
        proveedor = request.form.get("proveedor", "").strip().lower()
        auth_method = request.form.get("auth_method", "password").strip()
        password = request.form.get("password", "").strip()
        servidor_custom = request.form.get("servidor_custom", "").strip()
        puerto_custom = request.form.get("puerto_custom", "993").strip()

        if not nombre or not correo:
            return jsonify({"success": False, "error": "Nombre y correo son obligatorios."})

        # Sanitizar nombre: solo alfanumérico sin espacios en mayúsculas
        nombre = re.sub(r'[^A-Za-z0-9]', '', nombre).upper()
        if not nombre:
            return jsonify({"success": False, "error": "El nombre debe contener letras o números."})

        # Sanitizar nombre para generar la variable de entorno
        env_key = "PASS_" + nombre

        palabras_clave = [
            "DTE", "factura", "CCF", "comprobante",
            "documento tributario", "documento electrónico", "documento electronico"
        ]

        if auth_method == "oauth2":
            # --- Flujo OAuth2 (Gmail) ---
            cred_file = request.files.get("credentials_file")
            if not cred_file:
                return jsonify({"success": False, "error": "Debe subir el archivo .json de credenciales OAuth2."})

            safe_name = secure_filename(f"client_secret_{nombre}.json")
            cred_path = CREDENTIALS_DIR / safe_name
            cred_file.save(str(cred_path))

            nueva_cuenta = {
                "nombre": nombre,
                "protocolo": "gmail_oauth",
                "usuario": correo,
                "credentials_path": f"{safe_name}",
                "token_path": f"token_{nombre}.json",
                "palabras_clave_asunto": palabras_clave,
            }
        else:
            # --- Flujo IMAP con contraseña ---
            if not password:
                return jsonify({"success": False, "error": "Debe proporcionar la contraseña de aplicación."})

            if proveedor == "custom":
                servidor = servidor_custom
                puerto = int(puerto_custom)
            else:
                info = IMAP_SERVERS.get(proveedor, IMAP_SERVERS["gmail"])
                servidor = info["servidor"]
                puerto = info["puerto"]

            nueva_cuenta = {
                "nombre": nombre,
                "protocolo": "imap",
                "servidor": servidor,
                "puerto": puerto,
                "usuario": correo,
                "password_env": env_key,
                "carpeta": "INBOX",
                "palabras_clave_asunto": palabras_clave,
            }

            # Escribir la contraseña en .env
            _env_set_key(env_key, password)

        # Agregar al array de cuentas
        cuentas = _leer_accounts()
        cuentas.append(nueva_cuenta)
        _guardar_accounts(cuentas)

        return jsonify({"success": True, "message": f"Cuenta '{nombre}' registrada exitosamente."})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/config/account', methods=['DELETE'])
def config_delete_account():
    """Elimina una cuenta del sistema por nombre."""
    try:
        data = request.json
        nombre_target = data.get("nombre", "")
        cuentas = _leer_accounts()
        cuentas_filtradas = [c for c in cuentas if c.get("nombre") != nombre_target]
        
        if len(cuentas_filtradas) == len(cuentas):
            return jsonify({"success": False, "error": f"Cuenta '{nombre_target}' no encontrada."})
        
        _guardar_accounts(cuentas_filtradas)
        return jsonify({"success": True, "message": f"Cuenta '{nombre_target}' eliminada."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ─── Carga inicial del .env ─────────────────────────────────────────────────
def _cargar_env():
    """Carga las variables del .env al entorno del proceso actual."""
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ[key.strip()] = value.strip()

_cargar_env()


if __name__ == '__main__':
    def abrir_navegador():
        """Abre la UI en el navegador por defecto."""
        webbrowser.open("http://127.0.0.1:5000/")
        
    # Inicia un hilo que espera 1.5s antes de abrir el navegador
    Timer(1.5, abrir_navegador).start()
    
    app.run(debug=True, use_reloader=False, port=5000)


