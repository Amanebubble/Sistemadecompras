"""
SCA ETL Pipeline — Servidor Web Flask.
Punto de entrada único para administrar el pipeline desde el navegador.
"""

from pathlib import Path
import os
import subprocess
import glob
from flask import Flask, render_template, jsonify

# Raíz del proyecto (donde vive app.py)
BASE_DIR = Path(__file__).resolve().parent
NUCLEO_DIR = BASE_DIR / "nucleo"

app = Flask(
    __name__,
    template_folder=str(NUCLEO_DIR / "templates"),
)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/stats')
def get_stats():
    descarga_dir = BASE_DIR / "Descarga-doc"
    cola1_dir = NUCLEO_DIR / "filtro_service" / "cola1"
    cola0_dir = NUCLEO_DIR / "filtro_service" / "cola0"
    procesados_dir = NUCLEO_DIR / "Procesados"
    respaldo_dir = NUCLEO_DIR / "Respaldo_PDF"
    revision_dir = NUCLEO_DIR / "Revision_Manual"

    def count_files(dir_path):
        return len([f for f in dir_path.glob("*") if f.is_file()]) if dir_path.exists() else 0

    return jsonify({
        "descarga_count": count_files(descarga_dir),
        "cola1_count": count_files(cola1_dir),
        "cola0_count": count_files(cola0_dir),
        "procesados_count": count_files(procesados_dir),
        "respaldo_count": count_files(respaldo_dir),
        "revision_count": count_files(revision_dir),
    })


@app.route('/api/run/conection', methods=['POST'])
def run_conection():
    try:
        conection_dir = NUCLEO_DIR / "conection-service"
        result = subprocess.run(
            ["python", "main.py"],
            cwd=str(conection_dir),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return jsonify({"success": result.returncode == 0, "output": result.stdout + "\n" + result.stderr})
    except Exception as e:
        return jsonify({"success": False, "output": str(e)})


@app.route('/api/run/filtro', methods=['POST'])
def run_filtro():
    try:
        filtro_main = NUCLEO_DIR / "filtro_service" / "main.py"
        result = subprocess.run(
            ["python", str(filtro_main)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return jsonify({"success": result.returncode == 0, "output": result.stdout + "\n" + result.stderr})
    except Exception as e:
        return jsonify({"success": False, "output": str(e)})


@app.route('/api/run/conversor0', methods=['POST'])
def run_conversor0():
    try:
        conversor_main = NUCLEO_DIR / "conversor0_json" / "main.py"
        result = subprocess.run(
            ["python", str(conversor_main)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return jsonify({"success": result.returncode == 0, "output": result.stdout + "\n" + result.stderr})
    except Exception as e:
        return jsonify({"success": False, "output": str(e)})


@app.route('/api/run/conversor1', methods=['POST'])
def run_conversor1():
    try:
        conversor_main = NUCLEO_DIR / "conversor1_pdf" / "extractor_pdf.py"
        result = subprocess.run(
            ["python", str(conversor_main)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return jsonify({"success": result.returncode == 0, "output": result.stdout + "\n" + result.stderr})
    except Exception as e:
        return jsonify({"success": False, "output": str(e)})


@app.route('/api/run/all', methods=['POST'])
def run_all():
    modules = [
        {"name": "conection-service", "cmd": ["python", "main.py"], "cwd": str(NUCLEO_DIR / "conection-service")},
        {"name": "filtro_service", "cmd": ["python", str(NUCLEO_DIR / "filtro_service" / "main.py")], "cwd": str(BASE_DIR)},
        {"name": "conversor1_pdf", "cmd": ["python", str(NUCLEO_DIR / "conversor1_pdf" / "extractor_pdf.py")], "cwd": str(BASE_DIR)},
        {"name": "conversor0_json", "cmd": ["python", str(NUCLEO_DIR / "conversor0_json" / "main.py")], "cwd": str(BASE_DIR)},
        {"name": "excel_services", "cmd": ["python", str(NUCLEO_DIR / "excel_services" / "generador_excel.py")], "cwd": str(BASE_DIR)},
    ]
    
    full_output = ""
    for mod in modules:
        try:
            full_output += f"\n=== Ejecutando {mod['name']} ===\n"
            result = subprocess.run(
                mod["cmd"],
                cwd=mod["cwd"],
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            full_output += result.stdout + "\n" + result.stderr
            
            if result.returncode != 0:
                full_output += f"\n[!] Advertencia: Módulo {mod['name']} terminó con código {result.returncode}\n"
        except Exception as e:
            full_output += f"\n[!] Advertencia: Excepción en {mod['name']}: {str(e)}\n"
            
    return jsonify({
        "success": True, 
        "message": "Pipeline completo ejecutado exitosamente",
        "output": full_output
    })


@app.route('/api/run/excel', methods=['POST'])
def run_excel():
    try:
        excel_main = NUCLEO_DIR / "excel_services" / "generador_excel.py"
        result = subprocess.run(
            ["python", str(excel_main)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return jsonify({"success": result.returncode == 0, "output": result.stdout + "\n" + result.stderr})
    except Exception as e:
        return jsonify({"success": False, "output": str(e)})


@app.route('/api/open_explorer', methods=['POST'])
def open_explorer():
    try:
        target_dir = BASE_DIR / "mineria-finalizada"
        target_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(target_dir))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


from flask import request, send_from_directory
import json
import shutil

import re

@app.route('/api/revision/list')
def revision_list():
    revision_dir = NUCLEO_DIR / "Revision_Manual"
    respaldo_dir = NUCLEO_DIR / "Respaldo_PDF"
    
    if not revision_dir.exists():
        return jsonify({"casos": []})
        
    jsons = list(revision_dir.glob('*.json'))
    pdfs_revision = list(revision_dir.glob('*.pdf'))
    pdfs_respaldo = list(respaldo_dir.glob('*.pdf')) if respaldo_dir.exists() else []
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
    revision_dir = NUCLEO_DIR / "Revision_Manual"
    respaldo_dir = NUCLEO_DIR / "Respaldo_PDF"
    if (revision_dir / filename).exists():
        return send_from_directory(str(revision_dir), filename)
    elif (respaldo_dir / filename).exists():
        return send_from_directory(str(respaldo_dir), filename)
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
        cola0_dir = NUCLEO_DIR / "filtro_service" / "cola0"
        with open(cola0_dir / f"{stem}.json", "w", encoding="utf-8-sig") as f:
            json.dump(hacienda_json, f, indent=4)
            
        # Limpiar originales en Revision_Manual y mover PDF a Respaldo_PDF si está en Revision
        revision_dir = NUCLEO_DIR / "Revision_Manual"
        respaldo_dir = NUCLEO_DIR / "Respaldo_PDF"
        
        pdf_name = data.get('pdf')
        if pdf_name:
            pdf_path_rev = revision_dir / pdf_name
            if pdf_path_rev.exists():
                shutil.move(str(pdf_path_rev), str(respaldo_dir / pdf_name))
        
        json_path = revision_dir / f"{stem}.json"
        if json_path.exists():
            os.remove(str(json_path))
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ─── Configuración de Cuentas ───────────────────────────────────────────────
from werkzeug.utils import secure_filename

CONECTION_DIR = NUCLEO_DIR / "conection-service"
ACCOUNTS_FILE = CONECTION_DIR / "accounts.json"
ENV_FILE = BASE_DIR / ".env"
CREDENTIALS_DIR = CONECTION_DIR / "credentials"
CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

# Mapeo de proveedores IMAP conocidos
IMAP_SERVERS = {
    "gmail": {"servidor": "imap.gmail.com", "puerto": 993},
    "outlook": {"servidor": "outlook.office365.com", "puerto": 993},
    "yahoo": {"servidor": "imap.mail.yahoo.com", "puerto": 993},
}

def _leer_accounts():
    """Lee accounts.json devolviendo lista vacía si no existe."""
    if not ACCOUNTS_FILE.exists():
        return []
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _guardar_accounts(cuentas):
    """Escribe la lista de cuentas en accounts.json."""
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
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
    """Devuelve la lista de cuentas configuradas (sin contraseñas)."""
    cuentas = _leer_accounts()
    safe_list = []
    for c in cuentas:
        safe_list.append({
            "nombre": c.get("nombre", ""),
            "usuario": c.get("usuario", ""),
            "protocolo": c.get("protocolo", ""),
            "servidor": c.get("servidor", ""),
            "auth_method": "oauth2" if c.get("protocolo") == "gmail_oauth" else "password",
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

        # Sanitizar nombre para generar la variable de entorno
        env_key = "PASS_" + re.sub(r'[^A-Za-z0-9]', '_', nombre).upper()

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
                "credentials_path": f"credentials/{safe_name}",
                "token_path": f"credentials/token_{nombre}.json",
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
    app.run(debug=True, use_reloader=False, port=5000)
