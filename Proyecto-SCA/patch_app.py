import re
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_func = '''@app.route('/api/reportes/descargar/<cliente>/<ano>/<mes>', methods=['GET'])
def descargar_reporte(cliente, ano, mes):
    import glob
    from flask import send_file
    try:
        from src.config import CARPETA_REPORTES
        nombre_cliente_limpio = "".join([c if c.isalnum() else "_" for c in str(cliente)])
        nombre_base = f"{nombre_cliente_limpio}_{int(mes):02d}_{ano}_"
        
        patron = str(CARPETA_REPORTES / f"{nombre_base}*.xlsx")
        archivos = glob.glob(patron)
        if not archivos:
            return jsonify({"success": False, "error": "Reporte no encontrado"}), 404
            
        archivos.sort(reverse=True)
        return send_file(archivos[0], as_attachment=True)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500'''

new_func = '''@app.route('/api/reportes/descargar/<cliente>/<ano>/<mes>', methods=['GET'])
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
        return jsonify({"success": False, "error": str(e)}), 500'''

content = content.replace(old_func, new_func)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
