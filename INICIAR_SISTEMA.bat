@echo off
title Sistema de Compras - Servidor
echo ==================================================
echo Iniciando Servidor del Sistema de Compras...
echo ==================================================
echo (Por favor, no cierres esta ventana negra mientras usas el sistema)
echo.

:: Verificar si Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no esta en el PATH de esta computadora.
    echo Por favor instala Python 3 ^(preferiblemente 3.10 o superior^) y marca la opcion "Add Python to PATH" durante la instalacion.
    echo Puedes descargarlo desde: https://www.python.org/downloads/
    pause
    exit /b
)

:: Ingresar al directorio del proyecto
cd Proyecto-SCA

:: Verificar o crear entorno virtual
if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Detectando nueva computadora. Creando entorno virtual local...
    echo Esto solo pasara la primera vez.
    python -m venv venv
    
    echo [INFO] Activando entorno...
    call venv\Scripts\activate.bat
    
    echo [INFO] Instalando dependencias ^(puede tardar un momento^)...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    echo [INFO] Entorno virtual detectado. Activando...
    call venv\Scripts\activate.bat
)

echo [INFO] Iniciando la aplicacion...
:: La aplicacion app.py se encargara de abrir el navegador automaticamente
python app.py

echo.
echo [INFO] El servidor se ha detenido.
pause
