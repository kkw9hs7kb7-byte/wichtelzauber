#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v tailscale >/dev/null 2>&1; then
  echo 'Bitte zuerst kostenlos Tailscale installieren und anmelden: https://tailscale.com/download'
  exit 1
fi
if [[ ! -f .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
if [[ ! -f data/wichtelzauber.sqlite3 ]]; then
  .venv/bin/python -m wichtelzauber.cli init-db
  echo 'Erstmalige Einrichtung des Administrators:'
  .venv/bin/python -m wichtelzauber.cli init-admin
fi
mkdir -p logs
export WZ_SECURE_COOKIES=1
if ! curl -fsS http://127.0.0.1:8000/ >/dev/null 2>&1; then
  nohup .venv/bin/python -m uvicorn wichtelzauber.app:app --host 127.0.0.1 --port 8000 > logs/webserver.log 2>&1 < /dev/null &
  sleep 2
fi
if ! curl -fsS http://127.0.0.1:8000/ >/dev/null; then
  echo 'Serverstart fehlgeschlagen. Logdatei: logs/webserver.log'
  exit 1
fi
echo 'Dein öffentliches HTTPS-Familienportal wird freigegeben ...'
tailscale funnel --bg 8000
tailscale funnel status
printf '\nWICHTIG: Computer eingeschaltet lassen! Bitte URL im Browser testen.\n'
