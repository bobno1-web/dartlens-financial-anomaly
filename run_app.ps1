# DARTLens Flask launcher (Loop 20-A). run_app.bat 의 PowerShell 대체.
# 메시지는 인코딩 안전을 위해 ASCII로 유지. 자세한 안내는 README.md 참고.
# 실행:  powershell -ExecutionPolicy Bypass -File run_app.ps1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$env:DARTLENS_OPEN_BROWSER = "1"

if (-not (Test-Path "app_flask.py")) {
    Write-Host "[ERROR] app_flask.py not found. Run from the project root. cwd: $($PWD.Path)" -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

# Pick a Python launcher: prefer python, fall back to the py launcher (no secret / API key access)
$PY = $null
if (Get-Command python -ErrorAction SilentlyContinue) { $PY = "python" }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $PY = "py" }
if (-not $PY) {
    Write-Host "[ERROR] Python not found. Install Python 3, then: python -m pip install -r requirements.txt" -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

# Flask check (no auto-install)
& $PY -c "import flask" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Flask not installed. First run: $PY -m pip install -r requirements.txt" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"; exit 1
}

Write-Host "Starting DARTLens (Flask)... a browser tab opens shortly (stop with Ctrl+C)" -ForegroundColor Green
& $PY app_flask.py
