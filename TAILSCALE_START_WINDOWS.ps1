# Kostenloser öffentlicher HTTPS-Zugriff mit Tailscale Funnel.
# Voraussetzung: Python (py), Tailscale installiert & dort eingeloggt.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (-not (Get-Command tailscale -ErrorAction SilentlyContinue)) {
  throw 'Bitte zuerst Tailscale installieren und dich anmelden: https://tailscale.com/download'
}
if (-not (Test-Path '.venv\Scripts\python.exe')) {
  py -m venv .venv
  & '.venv\Scripts\python.exe' -m pip install -r requirements.txt
}
if (-not (Test-Path 'data\wichtelzauber.sqlite3')) {
  & '.venv\Scripts\python.exe' -m wichtelzauber.cli init-db
  Write-Host 'Jetzt den ersten Admin erstellen:'
  & '.venv\Scripts\python.exe' -m wichtelzauber.cli init-admin
}
$env:WZ_SECURE_COOKIES = '1'
try {
  $web = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -TimeoutSec 2 -UseBasicParsing
} catch {
  Start-Process -FilePath (Resolve-Path '.venv\Scripts\python.exe').Path -ArgumentList @('-m','uvicorn','wichtelzauber.app:app','--host','127.0.0.1','--port','8000') -WorkingDirectory (Get-Location).Path -WindowStyle Hidden
  Start-Sleep -Seconds 3
}
$web = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -TimeoutSec 10 -UseBasicParsing
if ($web.StatusCode -ne 200) { throw 'Lokaler Server ist nicht erreichbar.' }
& tailscale funnel --bg 8000
& tailscale funnel status
Write-Host 'Fertig. Teile nur den HTTPS-Link, den Tailscale oben anzeigt. PC muss eingeschaltet bleiben.'
