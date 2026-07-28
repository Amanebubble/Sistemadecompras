"""
Gestor de Filtro — orquestador principal del pipeline de clasificación.

Lee archivos de Descarga-doc y los clasifica en 5 carpetas de destino:
  - Procesados:    JSON estandarizado generado desde DTE válido
  - Respaldo_PDF:  PDFs emparejados con su JSON (ya tienen su DTE en Procesados)
  - Invalidos:     JSON que no es DTE, o PDF sin contenido de factura
  - Errores:       JSON corrupto, PDF huérfano sin extractor implementado
  - Duplicados:    Archivos cuyo UUID ya fue procesado en una corrida anterior

Flujo:
  Pre-filtro: Deduplicación por UUID contra SQLite (sin abrir archivos)
  Paso 0: Emparejar PDFs con JSONs por UUID compartido en el nombre
  Paso 1: Clasificar JSONs (parseo + validación DTE) y PDFs huérfanos (keywords)
  Paso 2: Slow Path para PDFs huérfanos clasificados como DTE (hoy → placeholder)
"""

import json
import os
import re
import shutil
import unicodedata
from datetime import datetime

from bd_registro import inicializar_bd, registrar_procesado, ya_procesado
from extractor_slowpath import extraer_desde_pdf
from mapeador_fastpath import mapear_a_plantilla


class GestorFiltro:

    def __init__(self, settings: dict):
        self.carpeta_entrada = settings["carpeta_entrada"]
        self.carpeta_procesados = settings["carpeta_procesados"]
        self.carpeta_respaldo = settings["carpeta_respaldo"]
        self.carpeta_invalido = settings["carpeta_invalido"]
        self.carpeta_error = settings["carpeta_error"]
        self.carpeta_duplicados = settings["carpeta_duplicados"]
        self.carpeta_otros = settings.get("otros_documentos", os.path.join(os.path.dirname(self.carpeta_procesados), "Otros_Documentos_Clasificados"))
        self.carpeta_revision = os.path.join(os.path.dirname(self.carpeta_entrada), "Revision_Manual")
        self.ruta_bd = settings["ruta_bd"]
        self.patron_uuid = re.compile(settings["patron_uuid"])
        self.campos_dte_esperados = settings["campos_dte_esperados"]
        self.palabras_clave_tipos_dte = settings["palabras_clave_tipos_dte"]

        # Conexión a BD (se abre al inicio, se cierra al final)
        self.conexion = None

        # Contadores de resumen
        self.contadores = {
            "duplicados": 0,
            "procesados": 0,
            "respaldo": 0,
            "invalidos": 0,
            "errores": 0,
            "otros": 0,
            "revision": 0,
        }

        # Crear carpetas de destino
        for carpeta in [
            self.carpeta_procesados,
            self.carpeta_respaldo,
            self.carpeta_invalido,
            self.carpeta_error,
            self.carpeta_duplicados,
            self.carpeta_otros,
            self.carpeta_revision,
        ]:
            os.makedirs(carpeta, exist_ok=True)

    # ── Utilidades ─────────────────────────────────────────────────────────

    def _extraer_uuid(self, nombre_archivo: str) -> str | None:
        """Extrae el primer UUID del nombre de archivo."""
        match = self.patron_uuid.search(nombre_archivo)
        return match.group(0).upper() if match else None

    def _extraer_nombre_cliente(self, nombre_archivo: str) -> str:
        """Extrae el nombre de cuenta del nombre del archivo dividiendo por _."""
        if "_" in nombre_archivo:
            return nombre_archivo.split("_")[0]
        return "Desconocido"

    @staticmethod
    def _mover(ruta_origen: str, carpeta_destino: str) -> str:
        """Mueve un archivo a la carpeta destino, manejando conflictos de nombre."""
        nombre = os.path.basename(ruta_origen)
        destino = os.path.join(carpeta_destino, nombre)
        if os.path.exists(destino):
            base, ext = os.path.splitext(nombre)
            contador = 1
            while os.path.exists(destino):
                destino = os.path.join(carpeta_destino, f"{base}_{contador}{ext}")
                contador += 1
        shutil.move(ruta_origen, destino)
        return destino

    @staticmethod
    def _normalizar_texto(texto: str) -> str:
        """Normaliza texto eliminando acentos y pasando a minúsculas."""
        nfkd = unicodedata.normalize("NFKD", texto)
        sin_acentos = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
        return sin_acentos.lower()

    def _contiene_palabras_clave_dte(self, texto: str) -> bool:
        """Verifica si el texto contiene alguna palabra clave de tipo DTE."""
        texto_norm = self._normalizar_texto(texto)
        for palabra in self.palabras_clave_tipos_dte:
            if self._normalizar_texto(palabra) in texto_norm:
                return True
        return False

    @staticmethod
    def _fecha_descarga_de_archivo(ruta: str) -> str:
        """Obtiene la fecha de descarga del archivo original (mtime → YYYY-MM-DD)."""
        try:
            mtime = os.path.getmtime(ruta)
            return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        except OSError:
            return datetime.now().strftime("%Y-%m-%d")

    # ── Pre-filtro: Deduplicación ──────────────────────────────────────────

    def _prefiltro_duplicados(self) -> list[str]:
        """Recorre todos los archivos en Descarga-doc y mueve los duplicados.

        Para cada archivo:
          1. Extraer UUID del nombre (sin abrir el archivo)
          2. Si tiene UUID válido → consultar BD
          3. Si ya_procesado → mover a carpeta_duplicados
          4. Si no → dejarlo para el pipeline normal

        Returns:
            Lista de nombres de archivos que sobrevivieron el filtro
            (todavía en Descarga-doc).
        """
        print("=" * 60)
        print("  PRE-FILTRO: Deduplicacion por UUID (sin abrir archivos)")
        print("=" * 60)

        archivos = os.listdir(self.carpeta_entrada)
        sobrevivientes = []

        for nombre in archivos:
            ruta = os.path.join(self.carpeta_entrada, nombre)
            if not os.path.isfile(ruta):
                continue

            uuid = self._extraer_uuid(nombre)

            if uuid and ya_procesado(self.conexion, uuid):
                # Duplicado → mover sin abrir
                self._mover(ruta, self.carpeta_duplicados)
                self.contadores["duplicados"] += 1
                print(f"  [DUPLICADO] {nombre}")
            else:
                sobrevivientes.append(nombre)

        total_archivos = self.contadores["duplicados"] + len(sobrevivientes)
        print(
            f"\n  Resumen: {total_archivos} archivos, "
            f"{self.contadores['duplicados']} duplicados, "
            f"{len(sobrevivientes)} nuevos"
        )
        return sobrevivientes

    # ── Paso 0: Emparejamiento ─────────────────────────────────────────────

    def _paso_0_emparejar(self) -> list[str]:
        """Empareja PDFs con JSONs por UUID y mueve los PDFs emparejados a Respaldo.

        Returns:
            Lista de rutas de PDFs huérfanos que necesitan clasificación.
        """
        print()
        print("=" * 60)
        print("  PASO 0: Emparejamiento PDF-JSON por UUID")
        print("=" * 60)

        archivos = os.listdir(self.carpeta_entrada)
        jsons = []
        pdfs = []

        for nombre in archivos:
            ruta = os.path.join(self.carpeta_entrada, nombre)
            if not os.path.isfile(ruta):
                continue
            ext = nombre.lower().rsplit(".", 1)[-1] if "." in nombre else ""
            if ext == "json":
                jsons.append((nombre, ruta))
            elif ext == "pdf":
                pdfs.append((nombre, ruta))

        # Construir índice: uuid → ruta del JSON
        json_por_uuid = {}
        for nombre, ruta in jsons:
            uuid = self._extraer_uuid(nombre)
            if uuid:
                json_por_uuid[uuid] = ruta

        # Clasificar PDFs
        pdfs_huerfanos = []
        for nombre, ruta in pdfs:
            uuid_pdf = self._extraer_uuid(nombre)
            if uuid_pdf and uuid_pdf in json_por_uuid:
                # PDF emparejado → mover a Respaldo
                self._mover(ruta, self.carpeta_respaldo)
                self.contadores["respaldo"] += 1
                print(f"  [RESPALDO] {nombre}")
            else:
                # PDF huérfano → pasa a clasificación
                pdfs_huerfanos.append(ruta)

        print(
            f"\n  Resumen Paso 0: {len(jsons)} JSONs, {len(pdfs)} PDFs, "
            f"{self.contadores['respaldo']} emparejados, "
            f"{len(pdfs_huerfanos)} huerfanos"
        )
        return pdfs_huerfanos

    # ── Paso 1: Clasificación ──────────────────────────────────────────────

    def _paso_1_clasificar_jsons(self):
        """Clasifica todos los .json que quedan en carpeta_entrada."""
        print()
        print("=" * 60)
        print("  PASO 1a: Clasificacion de archivos JSON")
        print("=" * 60)

        archivos = os.listdir(self.carpeta_entrada)
        jsons = [
            (n, os.path.join(self.carpeta_entrada, n))
            for n in archivos
            if os.path.isfile(os.path.join(self.carpeta_entrada, n))
            and n.lower().endswith(".json")
        ]

        for nombre, ruta in jsons:
            # Capturar fecha_descarga ANTES de mover/eliminar el archivo
            fecha_descarga = self._fecha_descarga_de_archivo(ruta)
            uuid = self._extraer_uuid(nombre)
            nombre_cliente = self._extraer_nombre_cliente(nombre)

            # Intentar parsear
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                # JSON corrupto/malformado → Error
                self._mover(ruta, self.carpeta_error)
                self.contadores["errores"] += 1
                print(f"  [ERROR]    {nombre} (JSON corrupto: {e})")
                continue

            # Validar estructura DTE
            if not all(campo in data for campo in self.campos_dte_esperados):
                # JSON válido pero no es DTE → Inválido
                self._mover(ruta, self.carpeta_invalido)
                self.contadores["invalidos"] += 1
                print(f"  [INVALIDO] {nombre} (no es DTE)")
                continue

            # Verificar tipo de documento (solo 03 y 14)
            ident = data.get("identificacion", {})
            tipo_dte = ident.get("tipoDte", "")
            if not tipo_dte:
                match_control = re.search(r"DTE-(\d{2})", ident.get("numeroControl", ""))
                if match_control:
                    tipo_dte = match_control.group(1)

            if tipo_dte not in ["03", "05", "06", "14"]:
                # Descartar JSON
                self._mover(ruta, self.carpeta_otros)
                self.contadores["otros"] += 1
                print(f"  [OTROS]    {nombre} (JSON nativo: tipo {tipo_dte} descartado)")
                
                # Mover PDF emparejado desde Respaldo a Otros (si existe)
                if uuid:
                    for pdf_respaldo in os.listdir(self.carpeta_respaldo):
                        if uuid in pdf_respaldo:
                            pdf_ruta = os.path.join(self.carpeta_respaldo, pdf_respaldo)
                            self._mover(pdf_ruta, self.carpeta_otros)
                            self.contadores["respaldo"] -= 1
                            self.contadores["otros"] += 1
                            print(f"  [OTROS]    {pdf_respaldo} (PDF asociado descartado)")
                continue

            # DTE válido → Fast Path: mapear y guardar
            try:
                estandarizado = mapear_a_plantilla(data, "JSON_NATIVO", nombre_cliente)
                
                # VALIDACION ESTRICTA (Jefe Final)
                fec_emi = estandarizado.get("datos_documento", {}).get("fecha_emision")
                nombre_emisor = estandarizado.get("datos_proveedor", {}).get("nombre_razon_social")
                nrc_emisor = estandarizado.get("datos_proveedor", {}).get("nrc")
                sello_recepcion = estandarizado.get("metadatos_sistema", {}).get("sello_recepcion")
                
                if not fec_emi or not nombre_emisor or not nrc_emisor or not sello_recepcion:
                    self._mover(ruta, self.carpeta_revision)
                    self.contadores["revision"] += 1
                    faltantes = [k for k, v in [("fecha", fec_emi), ("nombre", nombre_emisor), ("nrc", nrc_emisor), ("sello", sello_recepcion)] if not v]
                    print(f"  [REVISION] {nombre} (Faltan: {', '.join(faltantes)})")
                    continue

                # Guardar con el mismo nombre de archivo original
                ruta_destino = os.path.join(self.carpeta_procesados, nombre)
                with open(ruta_destino, "w", encoding="utf-8") as f:
                    json.dump(estandarizado, f, ensure_ascii=False, indent=2)
                # Eliminar el JSON original de Descarga-doc
                os.remove(ruta)
                self.contadores["procesados"] += 1
                codigo = estandarizado.get("metadatos_sistema", {}).get(
                    "codigo_generacion", "?"
                )
                print(f"  [PROCESADO] {nombre} ({codigo})")

                # Registrar en BD
                if uuid and self.conexion:
                    registrar_procesado(
                        self.conexion, uuid, nombre_cliente, fecha_descarga
                    )

            except Exception as e:
                self._mover(ruta, self.carpeta_error)
                self.contadores["errores"] += 1
                print(f"  [ERROR]    {nombre} (mapeo fallo: {e})")

    def _paso_1_clasificar_pdfs_huerfanos(self, pdfs_huerfanos: list[str]):
        """Clasifica PDFs huérfanos por contenido de texto."""
        print()
        print("=" * 60)
        print("  PASO 1b: Clasificacion de PDFs huerfanos")
        print("=" * 60)

        if not pdfs_huerfanos:
            print("  (ninguno)")
            return

        try:
            import fitz  # PyMuPDF
        except ImportError:
            print(
                "  [WARN] PyMuPDF (fitz) no instalado. "
                "Todos los PDFs huerfanos van a Errores."
            )
            for ruta in pdfs_huerfanos:
                nombre = os.path.basename(ruta)
                if os.path.exists(ruta):
                    self._mover(ruta, self.carpeta_error)
                    self.contadores["errores"] += 1
                    print(f"  [ERROR]    {nombre} (PyMuPDF no disponible)")
            return

        pdfs_dte = []

        for ruta in pdfs_huerfanos:
            nombre = os.path.basename(ruta)
            if not os.path.exists(ruta):
                continue

            # Extraer texto para clasificar
            try:
                doc = fitz.open(ruta)
                texto = ""
                for pagina in doc:
                    texto += pagina.get_text()
                doc.close()
            except Exception as e:
                self._mover(ruta, self.carpeta_error)
                self.contadores["errores"] += 1
                print(f"  [ERROR]    {nombre} (no se pudo leer PDF: {e})")
                continue

            # Buscar palabras clave de DTE
            if not self._contiene_palabras_clave_dte(texto):
                # No es un DTE → Inválido
                self._mover(ruta, self.carpeta_invalido)
                self.contadores["invalidos"] += 1
                print(f"  [INVALIDO] {nombre} (sin palabras clave DTE)")
            else:
                # Es un DTE → pasa a Paso 2 (Slow Path)
                pdfs_dte.append(ruta)

        # Paso 2: Slow Path para PDFs que sí son DTE
        if pdfs_dte:
            self._paso_2_slow_path(pdfs_dte)

    # ── Paso 2: Slow Path ──────────────────────────────────────────────────

    def _paso_2_slow_path(self, pdfs_dte: list[str]):
        """Intenta extraer datos de PDFs DTE huérfanos usando el extractor lento."""
        print()
        print("=" * 60)
        print("  PASO 2: Slow Path (extraccion desde PDF)")
        print("=" * 60)

        for ruta in pdfs_dte:
            nombre = os.path.basename(ruta)
            if not os.path.exists(ruta):
                continue

            # Capturar metadatos antes de mover
            fecha_descarga = self._fecha_descarga_de_archivo(ruta)
            uuid = self._extraer_uuid(nombre)
            nombre_cliente = self._extraer_nombre_cliente(nombre)

            # extraer_desde_pdf puede mover el archivo a carpeta_otros o carpeta_error internamente
            resultado = extraer_desde_pdf(ruta, self.carpeta_otros, self.carpeta_error)

            if resultado is None:
                # El extractor falló o descartó el archivo. Revisar dónde terminó para el contador.
                if os.path.exists(os.path.join(self.carpeta_otros, nombre)):
                    self.contadores["otros"] += 1
                    print(f"  [OTROS]    {nombre} (Descartado rapido: no es 03 ni 14)")
                elif os.path.exists(os.path.join(self.carpeta_error, nombre)):
                    self.contadores["errores"] += 1
                    print(f"  [ERROR]    {nombre} (Fallo matematico u otro error de extraccion)")
                else:
                    # Fallback por si acaso no lo movió y devolvió None
                    if os.path.exists(ruta):
                        self._mover(ruta, self.carpeta_error)
                        self.contadores["errores"] += 1
                        print(f"  [ERROR]    {nombre} (extractor retorno None sin mover el archivo)")
            else:
                # Extracción exitosa → mapear y guardar
                try:
                    estandarizado = mapear_a_plantilla(resultado, "EXTRACCION_PDF", nombre_cliente)
                    
                    # VALIDACION ESTRICTA (Jefe Final)
                    fec_emi = estandarizado.get("datos_documento", {}).get("fecha_emision")
                    nombre_emisor = estandarizado.get("datos_proveedor", {}).get("nombre_razon_social")
                    nrc_emisor = estandarizado.get("datos_proveedor", {}).get("nrc")
                    sello_recepcion = estandarizado.get("metadatos_sistema", {}).get("sello_recepcion")
                    
                    if not fec_emi or not nombre_emisor or not nrc_emisor or not sello_recepcion:
                        if os.path.exists(ruta):
                            self._mover(ruta, self.carpeta_revision)
                        self.contadores["revision"] += 1
                        faltantes = [k for k, v in [("fecha", fec_emi), ("nombre", nombre_emisor), ("nrc", nrc_emisor), ("sello", sello_recepcion)] if not v]
                        print(f"  [REVISION] {nombre} (Faltan: {', '.join(faltantes)})")
                        continue

                    nombre_json = os.path.splitext(nombre)[0] + ".json"
                    ruta_destino = os.path.join(self.carpeta_procesados, nombre_json)
                    with open(ruta_destino, "w", encoding="utf-8") as f:
                        json.dump(estandarizado, f, ensure_ascii=False, indent=2)
                    # Mover el PDF original a Respaldo
                    self._mover(ruta, self.carpeta_respaldo)
                    self.contadores["procesados"] += 1
                    print(f"  [PROCESADO] {nombre} -> {nombre_json}")

                    # Registrar en BD
                    if uuid and self.conexion:
                        registrar_procesado(
                            self.conexion, uuid, nombre_cliente, fecha_descarga
                        )

                except Exception as e:
                    if os.path.exists(ruta):
                        self._mover(ruta, self.carpeta_error)
                    self.contadores["errores"] += 1
                    print(f"  [ERROR]    {nombre} (mapeo fallo: {e})")

    # ── Ejecución principal ────────────────────────────────────────────────

    def ejecutar(self) -> dict:
        """Ejecuta el pipeline completo de clasificación.

        Returns:
            Diccionario con contadores por carpeta de destino.
        """
        # Abrir conexión a BD
        self.conexion = inicializar_bd(self.ruta_bd)

        try:
            # Pre-filtro: Deduplicación por UUID
            self._prefiltro_duplicados()

            # Paso 0: Emparejar PDFs con JSONs
            pdfs_huerfanos = self._paso_0_emparejar()

            # Paso 1a: Clasificar JSONs
            self._paso_1_clasificar_jsons()

            # Paso 1b + Paso 2: Clasificar y procesar PDFs huérfanos
            self._paso_1_clasificar_pdfs_huerfanos(pdfs_huerfanos)

        finally:
            # Cerrar conexión a BD siempre
            if self.conexion:
                self.conexion.close()
                self.conexion = None

        # Resumen final
        print()
        print("=" * 60)
        print("  RESUMEN FINAL")
        print("-" * 60)
        print(f"  Duplicados:     {self.contadores['duplicados']}")
        print(f"  Procesados:     {self.contadores['procesados']}")
        print(f"  Respaldo PDF:   {self.contadores['respaldo']}")
        print(f"  Invalidos:      {self.contadores['invalidos']}")
        print(f"  Otros DTE:      {self.contadores['otros']}")
        print(f"  Errores:        {self.contadores['errores']}")
        print(f"  Revision M.:    {self.contadores['revision']}")
        total = sum(self.contadores.values())
        print(f"  Total movidos:  {total}")
        print("=" * 60)

        return self.contadores
