"""
Lógica central de enrutamiento para el filtro_service.
"""
import os
import re
import json
import shutil
from datetime import datetime
from pathlib import Path
from bd_registro import inicializar_bd, ya_procesado, registrar_procesado

class Enrutador:
    def __init__(self, settings: dict):
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

    def _extraer_uuid(self, nombre_archivo):
        """Extrae el primer UUID del nombre del archivo y lo retorna en mayúsculas."""
        match = self.patron_uuid.search(nombre_archivo)
        return match.group(0).upper() if match else None

    def _extraer_nombre_cliente(self, nombre_archivo):
        """Divide el nombre por '_' y retorna la primera parte."""
        partes = nombre_archivo.split('_')
        return partes[0] if partes else "Desconocido"

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
            
            uuid = self._extraer_uuid(archivo.name)
            if uuid and ya_procesado(self.conexion, uuid):
                self._mover(archivo, self.carpeta_duplicados)
                self.contadores["duplicados"] += 1
            else:
                sobrevivientes.append(archivo)
                
        print(f"Prefiltro: {self.contadores['duplicados']} duplicados encontrados.")
        return sobrevivientes

    def _paso_0_emparejar(self):
        """Empareja PDFs con JSONs basándose en el UUID."""
        archivos = list(self.carpeta_entrada.glob('*'))
        jsons = [a for a in archivos if a.suffix.lower() == '.json' and a.exists()]
        pdfs = [a for a in archivos if a.suffix.lower() == '.pdf' and a.exists()]
        
        indice_jsons = {}
        for j in jsons:
            uuid = self._extraer_uuid(j.name)
            if uuid:
                indice_jsons[uuid] = j
                
        pdfs_huerfanos = []
        for pdf in pdfs:
            if not pdf.exists():
                continue
            uuid = self._extraer_uuid(pdf.name)
            if uuid and uuid in indice_jsons:
                self._mover(pdf, self.carpeta_respaldo)
                self.contadores["respaldo"] += 1
            else:
                pdfs_huerfanos.append(pdf)
                
        print(f"Paso 0: {self.contadores['respaldo']} PDFs emparejados.")
        return pdfs_huerfanos

    def _clasificar_archivos(self, pdfs_huerfanos: list):
        """Clasifica JSONs restantes y PDFs huérfanos."""
        # Procesar JSONs
        jsons = list(self.carpeta_entrada.glob('*.json'))
        for j in jsons:
            if not j.exists():
                continue
            uuid = self._extraer_uuid(j.name)
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
                
                # Intentar mover el PDF de respaldo si existe
                if uuid:
                    for pdf_respaldo in self.carpeta_respaldo.glob(f"*{uuid}*.pdf"):
                        self._mover(pdf_respaldo, self.carpeta_otros)
            else:
                self._mover(j, self.carpeta_cola0)
                self.contadores["cola0"] += 1
                
                # Registrar como procesado
                if uuid:
                    nombre = self._extraer_nombre_cliente(j.name)
                    fecha = self._fecha_descarga_de_archivo(j)
                    registrar_procesado(self.conexion, uuid, nombre, fecha)

        # Procesar PDFs huérfanos
        for pdf in pdfs_huerfanos:
            # Los PDFs huérfanos van a cola1 para OCR/conversor
            if pdf.exists():
                self._mover(pdf, self.carpeta_cola1)
                self.contadores["cola1"] += 1

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
                
        print("\nResumen final del proceso:")
        for clave, valor in self.contadores.items():
            print(f"- {clave.capitalize()}: {valor}")
            
        return self.contadores
