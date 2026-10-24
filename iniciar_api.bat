@echo off
cd /d "%~dp0"
powershell -NoExit -ExecutionPolicy Bypass -File "iniciar_api.ps1"
