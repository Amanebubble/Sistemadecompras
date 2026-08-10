"""
Lógica central de enrutamiento para el filtro_service.
"""
import os
import re
import json
import shutil
from datetime import datetime
from pathlib import Path
from .bd_registro import inicializar_bd, ya_procesado, registrar_procesado
from src.config import FILTRO_CONFIG

class Enrutador:
    def __init__(self, settings: dict = None):
        if settings is None:
            settings = FILTRO_CONFIG
        self.carpeta_entrada = Path(settings["carpeta_entrada"])
        self.carpeta_cola0 = Path(settings["carpeta_cola0"])
        self.carpeta_cola1 = Path(settings["carpeta_cola1"])
        self.carpeta_respaldo = Path(settings["carpeta_respaldo"])
        self.carpeta_invalido = Path(settings["carpeta_invalido"])
        self.carpeta_error = Path(settings["carpeta_error"])
        self.carpeta_duplicados = Path(settings["carpeta_duplicados"])
        self.carpeta_otros = Path(settings["carpeta_otros"])
        self.ruta_bd = Path(settings["ruta_bd"])
        
        self.patron_uuid = re.compile(settings["patron_uuid"])
        self.campos_dte_esperados = settings.get("campos_dte_esperados", [])
        self.tipos_dte_validos = settings.get("tipos_dte_validos", [])
        
        self.contadores = {
            "duplicados": 0,
            "cola0": 0,
            "cola1": 0,
            "respaldo": 0,
            "invalidos": 0,
            "errores": 0,
            "otros": 0
        }
        
        # Crear directorios
        for carpeta in [
            self.carpeta_cola0, self.carpeta_cola1, self.carpeta_respaldo,
            self.carpeta_invalido, self.carpeta_error, self.carpeta_duplicados,
            self.carpeta_otros, self.ruta_bd.parent
        ]:
            os.makedirs(carpeta, exist_ok=True)
            
        self.conexion = None

    def _extraer_identificador(self, nombre_archivo):
        """Extrae el identificador del nombre de archivo de forma robusta usando regex."""
        import re
        match = re.search(r'_([^_]+)_\d{8}(?:_\d+)?\.[a-zA-Z0-9]+$', nombre_archivo)
        if match:
            return match.group(1).upper()
        # Fallback a patron UUID
        match = self.patron_uuid.search(nombre_archivo)
        return match.group(0).upper() if match else None

    def _lectura_ligera_rescate(self, ruta_pdf):
        """Lee el PDF si el identificador es 'none' para intentar rescatar su UUID."""
        try:
            import pdfplumber
            with pdfplumber.open(str(ruta_pdf)) as pdf:
                if not pdf.pages:
                    return "NONE"
                texto = pdf.pages[0].extract_text()
                if not texto:
                    return "NONE"
                
                # Intentar buscar el código de generación UUID
                match_uuid = re.search(r'[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}', texto)
                if match_uuid:
                    return match_uuid.group(0).upper()
        except Exception:
            pass
        return "NONE"

    def _extraer_nombre_cliente(self, nombre_archivo):
        """Extrae el nombre del cliente del archivo quitando el identificador y fecha."""
        identificador = self._extraer_identificador(nombre_archivo)
        if identificador:
            partes = nombre_archivo.split(f"_{identificador}_")
            if len(partes) > 1:
                return partes[0]
        return nombre_archivo.split('_')[0]

    @staticmethod
    def _mover(ruta_origen, carpeta_destino):
        """Mueve un archivo, manejando conflictos de nombres agregando sufijos."""
        origen = Path(ruta_origen)
        destino = Path(carpeta_destino)
        ruta_destino = destino / origen.name
        
        contador = 1
        while ruta_destino.exists():
            ruta_destino = destino / f"{origen.stem}_{contador}{origen.suffix}"
            contador += 1
            
        shutil.move(str(origen), str(ruta_destino))
        return ruta_destino

    def _fecha_descarga_de_archivo(self, ruta):
        """Obtiene la fecha de modificación del archivo en formato YYYY-MM-DD."""
        ruta_obj = Path(ruta)
        if not ruta_obj.exists():
            print(f"    [WARN] Archivo no encontrado para metadatos: {ruta_obj.name}, usando fecha actual.")
            return datetime.now().strftime('%Y-%m-%d')
        mtime = os.path.getmtime(ruta_obj)
        return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')

    def _prefiltro_duplicados(self):
        """Filtra archivos cuyos UUIDs ya están procesados en la base de datos."""
        archivos = list(self.carpeta_entrada.glob('*'))
        sobrevivientes = []
        
        for archivo in archivos:
            if not archivo.is_file() or not archivo.exists():
                continue
            
            identificador = self._extraer_identificador(archivo.name)
            if identificador and identificador != "NONE" and ya_procesado(self.conexion, identificador):
                self._mover(archivo, self.carpeta_duplicados)
                self.contadores["duplicados"] += 1
            else:
                sobrevivientes.append(archivo)
                
        if self.contadores["duplicados"] > 0:
            print(f"[Enrutador] Descartados {self.contadores['duplicados']} archivos duplicados.")
        return sobrevivientes

    def _paso_0_emparejar(self):
        """Empareja PDFs con JSONs basándose en el UUID."""
        archivos = list(self.carpeta_entrada.glob('*'))
        jsons = [a for a in archivos if a.suffix.lower() == '.json' and a.exists()]
        pdfs = [a for a in archivos if a.suffix.lower() == '.pdf' and a.exists()]
        
        indice_jsons = {}
        for j in jsons:
            identificador = self._extraer_identificador(j.name)
            if identificador and identificador != "NONE":
                indice_jsons[identificador] = j
                
        pdfs_huerfanos = []
        for pdf in pdfs:
            if not pdf.exists():
                continue
            identificador = self._extraer_identificador(pdf.name)
            
            # Si el identificador es NONE, intentamos la lectura de rescate
            if identificador == "NONE":
                identificador = self._lectura_ligera_rescate(pdf)
                
            if identificador and identificador != "NONE" and identificador in indice_jsons:
                self._mover(pdf, self.carpeta_respaldo)
                self.contadores["respaldo"] += 1
            else:
                pdfs_huerfanos.append(pdf)
                
        if self.contadores["respaldo"] > 0:
            print(f"[Enrutador] Emparejados y respaldados {self.contadores['respaldo']} PDFs.")
        return pdfs_huerfanos

    def _clasificar_archivos(self, pdfs_huerfanos: list):
        """Clasifica JSONs restantes y PDFs huérfanos."""
        # Procesar JSONs
        jsons = list(self.carpeta_entrada.glob('*.json'))
        for j in jsons:
            if not j.exists():
                continue
            identificador = self._extraer_identificador(j.name)
            try:
                with open(j, 'r', encoding='utf-8-sig') as f:
                    datos = json.load(f)
            except Exception:
                self._mover(j, self.carpeta_error)
                self.contadores["errores"] += 1
                continue
                
            # Validar campos esperados
            if not all(campo in datos for campo in self.campos_dte_esperados):
                self._mover(j, self.carpeta_invalido)
                self.contadores["invalidos"] += 1
                continue
                
            # Extraer tipo DTE
            tipo_dte = None
            if "identificacion" in datos and "tipoDte" in datos["identificacion"]:
                tipo_dte = datos["identificacion"]["tipoDte"]
            else:
                # Intento de extracción por numeroControl
                if "identificacion" in datos and "numeroControl" in datos["identificacion"]:
                    numero_control = datos["identificacion"]["numeroControl"]
                    match = re.search(r'DTE-(\d{2})', numero_control)
                    if match:
                        tipo_dte = match.group(1)
            
            if tipo_dte and tipo_dte not in self.tipos_dte_validos:
                self._mover(j, self.carpeta_otros)
                self.contadores["otros"] += 1
                print(f"[Enrutador] Archivo '{j.name}' movido a Otros DTEs (No deducible)")
                
                # Intentar mover el PDF de respaldo si existe
                if identificador and identificador != "NONE":
                    for pdf_respaldo in self.carpeta_respaldo.glob(f"*{identificador}*.pdf"):
                        self._mover(pdf_respaldo, self.carpeta_otros)
            else:
                self._mover(j, self.carpeta_cola0)
                self.contadores["cola0"] += 1
                print(f"[Enrutador] Documento '{j.name}' movido a Cola JSON (cola0)")
                
                # Registrar como procesado
                if identificador and identificador != "NONE":
                    nombre = self._extraer_nombre_cliente(j.name)
                    fecha = self._fecha_descarga_de_archivo(j)
                    registrar_procesado(self.conexion, identificador, nombre, fecha)
            
            import time
            time.sleep(1.5)

        # Procesar PDFs huérfanos
        for pdf in pdfs_huerfanos:
            # Los PDFs huérfanos van a cola1 para OCR/conversor
            if pdf.exists():
                self._mover(pdf, self.carpeta_cola1)
                self.contadores["cola1"] += 1
                print(f"[Enrutador] Documento '{pdf.name}' movido a Cola PDF (cola1)")
            
            import time
            time.sleep(1.5)

    def ejecutar(self):
        """Inicia el proceso de enrutamiento."""
        self.conexion = inicializar_bd(self.ruta_bd)
        try:
            self._prefiltro_duplicados()
            pdfs_huerfanos = self._paso_0_emparejar()
            self._clasificar_archivos(pdfs_huerfanos)
        finally:
            if self.conexion:
                self.conexion.close()
            
        return self.contadores

