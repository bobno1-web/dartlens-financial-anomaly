@echo off
chcp 65001 >nul
setlocal
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "DARTLENS_OPEN_BROWSER=1"
cd /d "%~dp0"

echo ============================================================
echo   DARTLens - Financial anomaly screening (local web UI)
echo   A browser tab opens automatically. Enter a company there.
echo ============================================================
echo.

if not exist "app_flask.py" (
    echo [ERROR] app_flask.py not found next to this launcher.
    echo         Keep run_app.bat in the project root folder.
    echo         Current folder: %CD%
    pause
    exit /b 1
)

REM 1) Pick a Python launcher: prefer python, fall back to the py launcher.
set "PYCMD="
where python >nul 2>nul && set "PYCMD=python"
if not defined PYCMD (
    where py >nul 2>nul && set "PYCMD=py"
)
if not defined PYCMD (
    echo [ERROR] Python was not found on PATH.
    echo         Install Python 3.11+ from https://www.python.org/downloads/
    echo         During setup, check "Add python.exe to PATH", then re-run this file.
    pause
    exit /b 1
)

REM 2) Dependency check - inform only, never auto-install (policy: Loop 20-A).
%PYCMD% -c "import flask, pandas, yaml, openpyxl" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Required libraries are missing. Run this once, by hand:
    echo        %PYCMD% -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo === Starting the web server. A browser tab opens shortly. ===
echo   * Keep this window open - it hosts the local server.
echo   * To stop: press Ctrl+C here, or just close this window.
echo.

%PYCMD% app_flask.py

echo.
echo [STOPPED] The web server has stopped.
pause
endlocal
