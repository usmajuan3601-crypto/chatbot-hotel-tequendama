Set-Location $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creando entorno e instalando librerias (solo la primera vez)..."
    python -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

$env:CHATBOT_API_URL = "http://127.0.0.1:8011"
$env:GROQ_MODEL = "openai/gpt-oss-20b"
$env:GROQ_API_KEY = ""

& .\.venv\Scripts\python.exe app_gradio.py