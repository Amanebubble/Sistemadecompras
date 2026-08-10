# Sistema de Compras Automatizado (SCA) - v1.9 Final Release

Este repositorio contiene la versión 1.9 (Release Final) del **Sistema de Compras Automatizado**. 
Es una herramienta monolítica que procesa correos electrónicos de facturación (IMAP/OAuth2), extrae archivos adjuntos (PDFs, JSON), los clasifica y extrae sus datos usando Inteligencia Artificial (Groq - Llama 3) para generar reportes en Excel.

## 🚀 Instalación Rápida para Producción / USB

El sistema está diseñado para ser portátil y auto-instalable en entornos Windows.

1. Clonar o descargar el repositorio.
2. Copiar el archivo `INICIAR_SISTEMA.bat` y la carpeta `Proyecto-SCA` a la PC destino.
3. Asegurarse de tener instalado **Python 3.10+**.
4. Crear un archivo `.env` en la ruta `Proyecto-SCA/.env` y agregar la clave de Groq:
   ```env
   GROQ_API_KEY=gsk_tu_clave_api
   ```
5. Ejecutar **`INICIAR_SISTEMA.bat`**. Este script detectará automáticamente si faltan dependencias, creará el entorno virtual (`venv`), instalará los requerimientos de `requirements.txt` y abrirá el servidor en `http://127.0.0.1:5000/`.

## 🏗️ Arquitectura del Proyecto

Todo el código fuente y los datos viven dentro de la carpeta `Proyecto-SCA`.

### 📂 Estructura Principal
- `app.py`: El orquestador principal. Levanta el servidor Flask, expone los endpoints de la API REST y sirve la interfaz frontend (`index.html`). Controla el pipeline de procesamiento.
- `requirements.txt`: Dependencias de Python sin versiones ancladas (para máxima compatibilidad multiplataforma en compilación).
- `INICIAR_SISTEMA.bat`: Script maestro de arranque en Windows.
- `limpiar_carpetas.py`: Script de utilidad para purgar todas las bases de datos y carpetas temporales para un inicio limpio.

### ⚙️ Módulos (`src/`)
- `conection_service/`: Módulo encargado de conectarse a cuentas de correo (vía IMAP o Gmail OAuth2). Descarga los correos no leídos y extrae los adjuntos.
- `filtro_service/`: Clasifica los documentos descargados. Identifica qué archivos son PDFs de compras, cuáles son JSON y cuáles son irrelevantes, enviándolos a sus respectivas colas.
- `conversor_pdf/`: El núcleo de extracción. Utiliza `pdfplumber` para extraer texto de PDFs complejos y la API de **Groq** (`llama-3.3-70b-versatile`) para parsear la información tributaria y estructurarla en JSON.
- `excel_services/`: Toma los datos procesados en la base de datos (DTEs) y genera los "Libros de Compras" y reportes consolidados en formato `.xlsx`.

### 💾 Datos (`data/`)
- `bases_de_datos/`: Contiene los archivos SQLite (`control_dte.db`, `correos_procesados.db`, `directorio.db`) que mantienen el estado de los correos y documentos procesados.
- `Descargas/`, `Procesados/`, `Invalidos/`: Carpetas utilizadas durante el ciclo de vida del pipeline para almacenar temporalmente los documentos físicos.

### 🌐 Frontend (`templates/` y `static/`)
- La interfaz de usuario es una Single Page Application (SPA) monolítica (`index.html`) estilizada con Tailwind CSS y alimentada por vanilla JavaScript. Toda la comunicación con el backend se realiza vía endpoints de la API (`/api/...`).

## 🔐 Manejo de Credenciales y Seguridad
- **Cuentas de Correo**: Las cuentas IMAP se agregan a través de la interfaz web (`Panel de Control -> Cuentas de Correo`). Las contraseñas de aplicación ingresadas en la UI se guardan automáticamente por el backend en el archivo `.env` de forma local.
- **Groq API**: Requiere que el usuario defina `GROQ_API_KEY` manualmente en el archivo `.env` antes del primer uso.

---
**Nota del Desarrollador:** Esta versión (1.9) marca el cierre de este proyecto y su estabilización total para despliegue. En el futuro, la lógica de abstracción de datos con IA de este proyecto será reutilizada para integrarse con ERPNext o programas contables / auditoría más grandes.
