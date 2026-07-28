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
    revision_dir = BASE_DIR / "Revision_Manual"

    descarga_count = len([f for f in descarga_dir.glob("*") if f.is_file()]) if descarga_dir.exists() else 0
    revision_count = len([f for f in revision_dir.glob("*") if f.is_file()]) if revision_dir.exists() else 0

    return jsonify({
        "descarga_count": descarga_count,
        "revision_count": revision_count,
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
        filtro_main = NUCLEO_DIR / "filtro-service" / "main.py"
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
