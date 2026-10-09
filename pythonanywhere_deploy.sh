#!/usr/bin/env bash
set -euo pipefail

# Im Bash-Terminal von PythonAnywhere aus dem Wichtelzauber-Projektordner starten.
# Zuvor kostenloses PythonAnywhere-Konto anlegen und API-Token aktivieren.

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="$(whoami)"
VENV="$HOME/.virtualenvs/wichtelzauber"

printf '\n🎄 Wichtelzauber – PythonAnywhere (experimentelles ASGI-Hosting)\n'
printf 'Ordner: %s\n' "$PROJECT"

if [[ -z "${PA_REGION:-}" ]]; then
  read -rp 'EU-Konto (eu.pythonanywhere.com)? [J/n] ' choice
  if [[ "${choice:-J}" =~ ^[nN]$ ]]; then
    PA_REGION='us'
  else
    PA_REGION='eu'
  fi
fi

if [[ "$PA_REGION" == 'eu' ]]; then
  DOMAIN="$USER_NAME.eu.pythonanywhere.com"
else
  DOMAIN="$USER_NAME.pythonanywhere.com"
fi

printf '\n1/4 Python-Abhängigkeiten installieren ...\n'
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r "$PROJECT/requirements.txt"

printf '2/4 Datenbank initialisieren ...\n'
cd "$PROJECT"
"$VENV/bin/python" -m wichtelzauber.cli init-db

ADMIN_COUNT="$($VENV/bin/python - <<'PY'
from wichtelzauber.db import connect
with connect() as conn:
    print(conn.execute('SELECT COUNT(*) FROM admins').fetchone()[0])
PY
)"
if [[ "$ADMIN_COUNT" == "0" ]]; then
  echo 'Jetzt den ersten Administrator anlegen (Passwort wird nicht angezeigt):'
  "$VENV/bin/python" -m wichtelzauber.cli init-admin
else
  echo "Admin bereits vorhanden, bestehende Zugangsdaten bleiben erhalten."
fi

printf '3/4 PythonAnywhere-Webserver-Werkzeug installieren ...\n'
python3 -m pip install --quiet --user --upgrade pythonanywhere || {
  echo 'Automatische Installation fehlgeschlagen. Bitte in PythonAnywhere-Bash ausführen: pip install --user --upgrade pythonanywhere'
  exit 1
}
export PATH="$HOME/.local/bin:$PATH"
if ! command -v pa >/dev/null 2>&1; then
  echo 'PythonAnywhere-Befehl pa wurde nicht gefunden. Bash-Konsole neu öffnen und erneut ausführen.'
  exit 1
fi

printf '\n4/4 Veröffentlichung unter https://%s/\n' "$DOMAIN"
CMD="env WZ_SECURE_COOKIES=1 WZ_DATABASE=$PROJECT/data/wichtelzauber.sqlite3 $VENV/bin/uvicorn --app-dir $PROJECT --uds \${DOMAIN_SOCKET} wichtelzauber.app:app"
echo 'Hinweis: Dieser Host nutzt experimentelles ASGI-Hosting. Bei Problemen bitte Online-Anleitung lesen.'

if pa website get --domain "$DOMAIN" >/dev/null 2>&1; then
  echo 'Webseite existiert bereits. Konfiguration bitte im PythonAnywhere-Panel prüfen.'
  echo 'Zum Aktivieren von Codeänderungen:'
  echo "  pa website reload --domain '$DOMAIN'"
else
  pa website create --domain "$DOMAIN" --command "$CMD"
fi

printf '\n✅ Wenn der Webserver erfolgreich erstellt wurde, ist die Adresse:\n'
printf '   https://%s/\n' "$DOMAIN"
printf '   Admin: https://%s/admin\n\n' "$DOMAIN"
printf 'Prüfe im Browser, dass die Seite startet und der Admin-Login funktioniert.\n'
printf 'Gratis-Webapps müssen laut PythonAnywhere regelmäßig verlängert werden (neue Free-Konten: 1 Monat).\n'
