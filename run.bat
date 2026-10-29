@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (py -3 -m venv .venv)
call .venv\Scriptsctivate.bat
pip install -q -r requirements.txt
playwright install chromium firefox webkit
if not exist .env copy .env.example .env >nul
echo Open http://localhost:8000 (phones on the same Wi-Fi: http://YOUR-PC-IP:8000)
python -m app.server
