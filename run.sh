#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
playwright install chromium firefox webkit
[ -f .env ] || cp .env.example .env
echo "Open http://localhost:8000 (phones on the same Wi-Fi: http://YOUR-PC-IP:8000)"
python -m app.server
