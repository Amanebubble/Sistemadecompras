@echo off
title Sistema de Compras - Servidor
echo ==================================================
echo Iniciando Servidor del Sistema de Compras...
echo ==================================================
echo (Por favor, no cierres esta ventana negra mientras usas el sistema)
echo.

:: Asegurar que el directorio de trabajo es donde esta este archivo .bat
cd /d "%~dp0"

:: Verificar si Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en el PATH de esta computadora.
    echo Por favor instala Python 3 ^(preferiblemente 3.10 o superior^) y marca la opcion "Add Python to PATH" durante la instalacion.
    echo Puedes descargarlo desde: https://www.python.org/downloads/
    pause
    exit /b
)

:: Ingresar al directorio del proyecto
cd Proyecto-SCA

:: Si el venv no existe, ir directamente a reconstruirlo
if not exist "venv\Scripts\activate.bat" goto rebuild_venv

:: Si existe, intentar activarlo y comprobar si funciona
call venv\Scripts\activate.bat
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [ADVERTENCIA] El entorno virtual parece estar corrupto o es de otra PC.
    goto rebuild_venv
)

:: Si llego hasta aqui, el entorno esta sano
goto start_app

:rebuild_venv
echo [INFO] Configurando entorno virtual para esta computadora...
if exist "venv" (
    echo [INFO] Borrando entorno virtual anterior...
    rmdir /s /q venv
)
python -m venv venv
call venv\Scripts\activate.bat
echo [INFO] Instalando dependencias ^(puede tardar unos minutos^)...
python -m pip install --upgrade pip
pip install -r requirements.txt

:start_app
echo [INFO] Iniciando la aplicacion...
:: La aplicacion app.py se encargara de abrir el navegador automaticamente
python app.py

echo.
echo [INFO] El servidor se ha detenido o ha ocurrido un error.
pause
