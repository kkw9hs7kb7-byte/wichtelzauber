# 🎄 Wichtelzauber

**Eine echte, selbst hostbare Wichtel-Web-App mit geheimen Losen, persönlicher PIN und Paarausschlüssen.** Die gesamte Oberfläche ist deutschsprachig und für Smartphones optimiert. Kein E-Mail-Dienst, kein Drittanbieter-Login und keine kostenpflichtige API sind erforderlich.

## Funktionsumfang

- Gruppen erstellen, bearbeiten, archivieren, endgültig löschen und fürs Folgejahr kopieren.
- Teilnehmer vom Admin vorbereiten lassen und über **einen** geheimen Gruppenlink einladen.
- Name wählen, eigene **sechsstellige PIN** festlegen, anschließend durch den Admin bestätigen lassen.
- Wiederanmeldung per Name und PIN; Vergessene PIN durch Admin zurücksetzen (keine neuen Lose).
- Paare **in beide Richtungen** ausschließen, zusätzlich einzelne gerichtete Ausschlüsse definieren.
- Eine gültige, vollständige Zuordnung serverseitig ermitteln und atomar in SQLite speichern. Bei bis zu 16 Personen werden alle gültigen vollständigen Auslosungen **gleich wahrscheinlich** gewählt.
- Persönliches Los mit Geschenk-Animation öffnen und jederzeit wieder ansehen.
- Wunschzettel erstellen und als Schenkender den Wunschzettel seines Empfängers ansehen.
- Schutz der Ergebnisse durch getrennte serverseitige Sessions und Zugriffsrechte. Adminoberfläche erhält **keine** Zuordnungsliste.
- Prüfung gegen doppelte Auslosung, unmögliche Ausschlüsse und wiederholte Registrierungen.
- Responsive Oberfläche, reduzierte Bewegung, installierbare PWA (bei HTTPS oder localhost).
- Ohne aktive Internetverbindung zum Dienstanbieter im lokalen Netzwerk nutzbar; der **eigene Server muss für alle Geräte erreichbar** sein.

## Technologie

- **Backend:** Python, [FastAPI](https://fastapi.tiangolo.com/) und Uvicorn; bewusst statt Flask gewählt, um die vollständige Implementierung hier ausführbar und testbar zu halten.
- **Frontend:** einfaches HTML/CSS und Vanilla JavaScript, keine externen Skripte oder Fonts.
- **Datenbank:** SQLite mit Fremdschlüsseln, atomaren Schreibtransaktionen und WAL-Modus.
- **Anmeldung:** Argon2id-Hashing (auch für sechsstellige PINs), opaque Sessions in der Datenbank, HttpOnly-Cookies, CSRF-Token, Rate-Limit/Sperre nach fünf falschen Versuchen.

Die App benutzt **keine** externe Laufzeit-API. Die einmalige Installation der quelloffenen Python-Pakete über `pip` benötigt üblicherweise eine Internetverbindung.

## Schnellstart: Windows, macOS oder Linux

**Voraussetzung:** Python 3.11 oder neuer, Terminal/Konsole.

1. Den Projektordner entpacken und im Terminal öffnen.
2. Virtuelle Umgebung erstellen und Pakete installieren:

   **macOS/Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

   **Windows (PowerShell)**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

3. Datenbank vorbereiten und **den ersten Admin interaktiv anlegen**:
   ```bash
   python -m wichtelzauber.cli init-db
   python -m wichtelzauber.cli init-admin
   ```
   Einen Admin-Benutzernamen und ein Passwort mit mindestens zwölf Zeichen auswählen. Es gibt **keinen** vorgegebenen Adminzugang.

4. Server lokal starten:
   ```bash
   python -m uvicorn wichtelzauber.app:app --host 127.0.0.1 --port 8000
   ```

5. Im Browser `http://127.0.0.1:8000` öffnen. Der Adminbereich ist unter `http://127.0.0.1:8000/admin` erreichbar.

**Wichtig:** Das Projekt enthält keine vorinstallierten Teilnehmer, keine Demo-PINs und keine vorausgelosten Ergebnisse.

### Für Smartphones im selben WLAN

Starte den Server im lokalen Netzwerk:

```bash
python -m uvicorn wichtelzauber.app:app --host 0.0.0.0 --port 8000
```

Die Familienmitglieder verwenden die LAN-IP des Servers (etwa `http://192.168.1.30:8000`) sowie den Gruppenlink. Gegebenenfalls müssen Firewall und Netzwerkfreigaben angepasst werden. Die IP ist nur ein **Beispiel**.

Im lokalen WLAN über HTTP funktioniert die Website, **aber** PWA-Installation und manche moderne Browserfunktionen benötigen HTTPS bzw. localhost. Für Zugriff von unterwegs den Abschnitt **Öffentlicher Betrieb** beachten.

### Konfiguration

Die App liest diese Umgebungsvariablen beim Start:

| Variable | Zweck | Standard |
|---|---|---|
| `WZ_DATABASE` | Pfad zur SQLite-Datei | `./data/wichtelzauber.sqlite3` im Projekt |
| `WZ_SECURE_COOKIES` | `1`: Cookies nur per HTTPS übertragen | `0` für lokalen HTTP-Test |

Unter Linux kannst du Variablen beispielsweise so setzen:

```bash
export WZ_DATABASE=/home/pi/wichtelzauber-data/wichtelzauber.sqlite3
export WZ_SECURE_COOKIES=0
python -m uvicorn wichtelzauber.app:app --host 0.0.0.0 --port 8000
```

Bei **echtem HTTPS-Betrieb unbedingt** `WZ_SECURE_COOKIES=1` setzen und HTTP auf HTTPS umleiten. Eine `.env.example` ist als Vorlage dabei, wird aber aus Sicherheits- und Einfachheitsgründen **nicht automatisch eingelesen**.

## Ablauf in der Familie

1. Admin unter `/admin` anmelden und Wichtelgruppe erstellen.
2. Namen im Reiter **Teilnehmer** hinzufügen (z. B. sechs bis zehn).
3. Unter **Paare & Regeln** Partnerpaare oder weitere Ausschlüsse festlegen.
4. Über **Einladungslink kopieren** den Link an die Familie senden.
5. Jede Person wählt ihren Namen und richtet die PIN ein.
6. Im Reiter **Freigaben** alle Identitäten persönlich prüfen und bestätigen.
7. Unter **Auslosung** den Start bestätigen. Unmögliche Regeln werden abgewiesen.
8. Teilnehmer melden sich mit ihrem Namen und ihrer PIN an und öffnen ihr Geschenk.
9. Persönliche Ergebnisse bleiben bis zur Löschung der Gruppe erhalten.

### Nachträgliche Änderung oder Ausfall

Nach dem Auslosen können **Teilnehmer und Ausschlüsse nicht geändert** werden. Um diese zu ändern, kann der Admin die Runde im Reiter **Auslosung** ausdrücklich mit `NEUSTART` annullieren. Die alten Lose sind dann ungültig und es kann eine neue Auslosung gestartet werden.

In der App erscheint für alle Teilnehmer beim nächsten Besuch ein gut sichtbarer Hinweis. **Es werden keine externen Push-Nachrichten, SMS oder E-Mails verschickt.** Der Admin sollte die Familie bei einer Annullierung zusätzlich selbst informieren, etwa über WhatsApp.

Ein PIN-Reset ist auch nach einer Auslosung möglich und **ändert das Los nicht**.

## Sicherheit und realistische Grenzen

- Namen/Links allein gewähren keinen Zugriff auf persönliche Ergebnisse. Es braucht eine gültige Teilnehmer-Session.
- Pro Name kann nur **eine** Registrierung gleichzeitig offen sein; die Adminbestätigung verhindert in der Familie Verwechslungen, soweit der Admin die Identität tatsächlich prüft.
- PINs liegen ausschließlich als Argon2id-Hash vor. Weil sechsstellige PINs wenig Entropie haben, sind wiederholte Fehlversuche limitiert. Starke individuelle PINs verwenden.
- Der Admin sieht über seine normalen Endpunkte weder die ganze Zuordnungsliste noch andere private Lose. Das gilt ausdrücklich **nicht** für jemanden mit vollem Datenbankzugriff oder missbräuchlich zurückgesetzten PINs.
- Sessions sind in der Datenbank gespeichert und können beim PIN-Reset sofort widerrufen werden. Session-Cookies sind HttpOnly und SameSite=Lax. Änderungen benötigen einen CSRF-Token.
- Kein öffentliches Gruppenverzeichnis; Einladungstokens werden mit einem kryptografischen Zufallsgenerator erstellt.
- Für Internetbetrieb sind **HTTPS, abgesicherter Serverzugang, Firewall und regelmäßige Updates** notwendig.
- Sicherungen und eventuelle alte SQLite-Dateien enthalten weiterhin historische Gruppeninformationen. Bei endgültiger Löschung sollten auch passende Backups nach dem eigenen Aufbewahrungsplan bereinigt werden.
- Die App ist für Familienbetrieb gedacht, nicht als Audit- oder Compliance-Sicherheitslösung.

## Datensicherung / Wiederherstellung

Während der Server läuft, **nicht** die einzelne SQLite-Datei per normalem `cp` kopieren (WAL-Modus). Stattdessen den eingebauten SQLite-Backupmechanismus verwenden:

```bash
python -m wichtelzauber.cli backup /pfad/zu/backup/wichtelzauber-2026-12-01.sqlite3
```

Regelmäßige Sicherungen können unter Linux über `cron` eingerichtet werden; Dateipfad, Dateirechte und Aufbewahrung sind auf die eigene Umgebung abzustimmen. Beispiel (jede Nacht um 3 Uhr):

```cron
0 3 * * * cd /home/pi/wichtelzauber && /home/pi/wichtelzauber/.venv/bin/python -m wichtelzauber.cli backup /home/pi/backups/wichtelzauber-latest.sqlite3
```

Dies überschreibt `latest` täglich. Für historische Sicherungen ein datiertes Rotationsskript verwenden.

Zur Wiederherstellung Server stoppen, Originaldatei samt vorhandener `-wal`-/`-shm`-Dateien sicher weglegen und die Sicherungsdatei an den in `WZ_DATABASE` angegebenen Ort kopieren; anschließend neu starten. Wiederherstellung **vorher separat testen**.

## Docker (optional)

```bash
docker compose up --build -d
docker compose exec wichtelzauber python -m wichtelzauber.cli init-admin
```

Danach lokal `http://127.0.0.1:8000` öffnen. Der Docker-Compose-Port ist absichtlich **nur an localhost** gebunden. Für Zugriff aus anderen Netzen Reverse Proxy, HTTPS und geeignete Firewallregeln verwenden. Die Datenbank befindet sich in einem persistenten Volume.

## Öffentlicher Betrieb / eigener Linux-Server

Die Web-App muss unter einer dauerhaft erreichbaren Adresse laufen, sonst können Familienmitglieder von unterwegs keine Ergebnisse abrufen. **Eine Domain oder ein gehosteter Server kann optional Geld kosten**, der App-Code benötigt allerdings keinerlei kostenpflichtige Dienste.

Empfohlene Lösung: Python-Prozess im Hintergrund über `systemd` (oder Docker) starten und einen freien HTTPS-Reverse-Proxy wie Caddy oder Nginx davor schalten. Ein beispielhafter Caddyfile ist im Projekt enthalten.

- App-Prozess nur lokal über `127.0.0.1:8000` bereitstellen.
- Über die eigene Domain ausschließlich HTTPS-Port 443 anbieten.
- `WZ_SECURE_COOKIES=1` konfigurieren.
- Sichere Admin-Zugangsdaten benutzen, Updates und Backups einrichten.
- Bei Heimhosting können Portweiterleitung und öffentliche Erreichbarkeit besondere Sicherheitsvorkehrungen erfordern. Niemals eine ungeschützte SQLite-Datei oder das `data/`-Verzeichnis ins Web stellen.

Für eine reine Familienrunde im eigenen WLAN ist keine öffentliche Domain nötig. Für PWA auf verschiedenen Geräten außerhalb von localhost ist HTTPS erforderlich.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Die automatisierten Integrationstests prüfen PIN-Freigaben und -Sperren, CSRF, verbotene Ergebniszugriffe, Paar-Ausschlüsse, unmögliche Auslosungen, doppelten Start, Annullierung, PIN-Reset ohne Ergebnisverlust, Archivierung/Löschen und Kopieren ohne Übernahme geheimer Ergebnisse.

Die Anwendung wurde mit Backendintegrationstests und Syntaxprüfung des Frontends kontrolliert. **Eine vollständige visuelle Browser-Abnahme auf allen Smartphone-Modellen und ein Sicherheitspenetrationstest sind noch nicht durchgeführt.** Vor der erstmaligen öffentlichen Bereitstellung bitte mit eurer Familie eine vollständige Proberunde durchspielen.

## Projektstruktur

```text
wichtelzauber/
├── wichtelzauber/
│   ├── app.py                 # REST-Backend, Rollen und Berechtigungen
│   ├── db.py                  # SQLite-Schema und atomare Transaktionen
│   ├── security.py            # Argon2id, Sessions, Token
│   ├── lottery.py             # Sichere Zuordnung mit Ausschlüssen
│   ├── cli.py                 # Admin erstellen, Datenbank sichern
│   └── static/
│       ├── index.html         # App-Grundgerüst
│       ├── app.js             # Mobile UI und alle Abläufe
│       ├── styles.css         # Weihnachtliches Design
│       ├── icon.svg           # Eigenes Wichtelsymbol
│       ├── manifest.webmanifest
│       └── service-worker.js  # Cache nur für öffentliche statische Dateien
├── tests/test_app.py
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── compose.yaml
└── README.md
```

**Viel Freude beim geheimen Verschenken!** 🎁
