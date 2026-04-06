@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "APP_PORT=8501"
set "APP_FILE=app.py"
set "PYTHON_CMD="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=%~dp0.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python non trovato. Installa Python oppure crea l'ambiente virtuale in .venv.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%APP_PORT% .*LISTENING"') do (
    echo Arresto il processo attivo sulla porta %APP_PORT% ^(PID %%P^)...
    taskkill /PID %%P /F >nul 2>&1
)

echo Avvio DietAPP su http://localhost:%APP_PORT% ...
start "DietAPP" "%PYTHON_CMD%" -m streamlit run "%APP_FILE%" --server.port %APP_PORT%

exit /b 0