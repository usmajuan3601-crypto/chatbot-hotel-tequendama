# Enciende la API (http://127.0.0.1:8011/docs). Funciona desde cualquier carpeta.
Set-Location $PSScriptRoot
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creando entorno e instalando librerias (solo la primera vez)..."
    python -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}
& .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8011
