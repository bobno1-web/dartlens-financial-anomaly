@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo Starting Financial Anomaly Streamlit App...
echo Project directory: %CD%
echo.

if not exist "app.py" (
    echo ERROR: app.py not found. Please run this file from the project root.
    pause
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not available. Please install Python and try again.
    echo Then run: python -m pip install -r requirements.txt
    pause
    exit /b 1
)

python -m streamlit --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Streamlit is not installed.
    echo Please run: python -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Opening app at http://localhost:8501
echo Press Ctrl+C in this window to stop the app.
echo.

python -m streamlit run app.py

echo.
echo App stopped.
pause
