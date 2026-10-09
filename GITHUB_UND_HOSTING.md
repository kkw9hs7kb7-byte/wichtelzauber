# Wichtelzauber über GitHub verwalten und veröffentlichen

## Warum GitHub Pages alleine nicht genügt

Die App hat ein Python/FastAPI-Backend und eine SQLite-Datenbank. GitHub Pages kann HTML, CSS und JavaScript ausliefern, **aber keinen Python-Server oder SQLite-Schreibzugriff bereitstellen**. Ein bloßes Hochladen der Dateien als GitHub Pages würde die Anmeldung, die Adminfunktionen und die geheime Auslosung außer Betrieb setzen.

## 1. GitHub-Repository erstellen

1. Unter https://github.com/new ein Repository `wichtelzauber` erstellen, vorzugsweise **Private** (Quellcode muss für die Familienmitglieder nicht öffentlich sein).
2. Keine zusätzliche README oder .gitignore erstellen, wenn dieses Paket hochgeladen werden soll.
3. Den Inhalt **dieses Ordners** (nicht die ZIP-Datei als eine einzelne Datei) über Git oder den GitHub-Dateiupload ins Repository laden.
4. Eine ChatGPT-GitHub-Verbindung benötigt Schreibzugriff auf das neu erstellte Repository, wenn ChatGPT künftig direkt Änderungen hochladen soll. Im GitHub-App-Setup gegebenenfalls dieses Repository freigeben.
5. Bei jedem Push startet `.github/workflows/tests.yml` den automatischen Testlauf.

**Nicht ins Repository hochladen:** `.env`, `data/`, `*.sqlite3`, Zugangsdaten, Admin-Passwörter oder produktive Datenbank-Backups. `.gitignore` ignoriert diese Dateien, aber der GitHub-Webupload ignoriert `.gitignore` nicht automatisch: beim Upload ausdrücklich prüfen.

## 2. Öffentlich erreichbare App

Ein freies Hosting-Angebot muss **Python/FastAPI sowie persistente SQLite-Dateien** unterstützen. Wenn ein Host seinen Speicher regelmäßig löscht, gehen bei SQLite die PINs und die ausgelosten Empfänger verloren. Prüfe dies vor der Veröffentlichung! Der unveränderte App-Code kann auf einem selbst betriebenen Rechner mit Tailscale Funnel öffentlich angeboten werden (Rechner muss laufen), auf einem geeigneten dauerhaft speichernden Python-Host oder auf einem bezahlten Server mit persistentem Datenträger.

**Cloudflare Workers und D1** können für kleine Gruppen im Gratis-Kontingent geeignet sein. Dafür muss das aktuelle Python/FastAPI-Backend jedoch in eine Worker-kompatible Laufzeit portiert und die Speicherung auf D1 umgestellt werden. Diese Fassung liegt **noch nicht** vor.

**Render Free** sollte für diese unveränderte SQLite-Anwendung NICHT verwendet werden: der Dateispeicher ist flüchtig und kann beim Schlafen/Neustart die Datenbank verlieren.

## 3. Sicherheit für den Internetbetrieb

- Immer HTTPS erzwingen und `WZ_SECURE_COOKIES=1` setzen.
- Admin über `python -m wichtelzauber.cli init-admin` auf dem Server selbst erstellen.
- Datenbank regelmäßig mit dem vorgesehenen Backup-Befehl sichern.
- Vor dem Familienwichteln einen vollständigen Durchlauf mit Testnamen einschließlich PIN-Reset und Neuanmeldung testen.

Die vollständige Installationsanleitung ist in `README.md`; weitere Hosting-Skripte in `online/`.
