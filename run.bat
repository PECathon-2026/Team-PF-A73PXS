@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (py -3 -m venv .venv)
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
if not exist .env copy .env.example .env >nul
echo.
echo Open http://localhost:8000
echo On a phone on the same Wi-Fi, open http://YOUR-PC-IP:8000 (run ipconfig to find the IP)
echo.
.venv\Scripts\python.exe -m app.server
