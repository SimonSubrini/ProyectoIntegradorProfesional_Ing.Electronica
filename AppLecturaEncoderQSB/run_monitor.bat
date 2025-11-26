@echo off
REM run_monitor.bat - Inicia Streamlit usando el python del virtualenv sensor_env (si existe).
REM Debe colocarse en la carpeta raíz del proyecto (junto a main.py).

cd /d "%~dp0"

REM python del virtualenv relativo
set "VENV_PY=%~dp0sensor_env\Scripts\python.exe"

if exist "%VENV_PY%" (
    echo Usando Python del virtualenv: "%VENV_PY%"
    set "PY_EXEC=%VENV_PY%"
) else (
    echo No se encontró "%~dp0sensor_env\Scripts\python.exe". Intentando 'python' del PATH.
    set "PY_EXEC=python"
)

echo.
echo Iniciando Monitor de Encoder (Streamlit)...
echo ------------------------------------------

REM 1) Lanzar Streamlit en una nueva ventana (no bloquea esta ventana)
start "" /min "%PY_EXEC%" -m streamlit run "%~dp0main.py" --server.port=8501 --server.headless=true

REM 2) Lanzar script que abrirá el navegador cuando el server responda. Se inicia minimizado.
start "" /min "%PY_EXEC%" "%~dp0open_when_ready.py" "http://localhost:8501" 30

REM Salimos del .bat: Streamlit sigue corriendo en la nueva ventana.
exit /b 0
