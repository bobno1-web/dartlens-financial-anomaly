# Ralph Loop 4-B: PowerShell launcher (run_app.bat 대체용)
# 메시지는 인코딩 안전을 위해 ASCII로 유지. 자세한 설명/한글 안내는 README.md 참고.
# 실행:  powershell -ExecutionPolicy Bypass -File run_app.ps1   (또는 우클릭 > PowerShell로 실행)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path "app.py")) {
    Write-Host "[ERROR] app.py not found. Run from the project root. cwd: $($PWD.Path)" -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

# Python check (no secret / API key access)
$null = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $?) {
    Write-Host "[ERROR] Python not found. Install Python 3, then: python -m pip install -r requirements.txt" -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

# Streamlit check (no auto-install)
python -c "import streamlit" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Streamlit not installed. First run: python -m pip install -r requirements.txt" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"; exit 1
}

Write-Host "Starting Streamlit... open http://localhost:8501 (stop with Ctrl+C)" -ForegroundColor Green
python -m streamlit run app.py
