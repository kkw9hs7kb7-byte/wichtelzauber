# 🎄 Wichtelzauber – Kostenlos mit der Familie online nutzen

Die App ist ein funktionsfähiges **FastAPI + SQLite**-Projekt. Sie ist ohne zusätzliches Hostingkonto nicht automatisch öffentlich. Ein ZIP-Download ist *kein* Website-Link. Hier sind zwei Möglichkeiten, die Familienmitglieder ohne Installation über einen normalen HTTPS-Link erreichen.

## Möglichkeit A: Kostenlos online, ohne eigenen Dauer-PC – PythonAnywhere (EU)

**Für den Familienalltag am bequemsten**, sofern PythonAnywhere das kostenlose experimentelle ASGI-Hosting für dein neues Konto anbietet. Du brauchst einen eigenen kostenlosen Hostingaccount, keinen GitHub-Zugang und keine Zahlungsdaten in diesem Projekt.

> WICHTIG: Die ASGI-Funktion wird von PythonAnywhere als **Beta** eingestuft. Kostenlose neue Accounts haben **eine Web-App mit einer Laufzeit von einem Monat**, die rechtzeitig verlängert werden muss. Die Plattform weist darauf hin, dass sich die Betapreise/Bedienung künftig ändern können. Das ist also keine Garantie auf kostenloses, wartungsfreies Hosting auf Lebenszeit.

**Schritt für Schritt (einmalig durch den Admin):**

1. Auf **https://eu.pythonanywhere.com/** ein kostenloses *Beginner*-Konto anlegen und anmelden. Die EU-Variante ist sinnvoll, weil die Familie in Deutschland sitzt.
2. In den PythonAnywhere-Kontoeinstellungen unter **API token** einen Token für das offizielle Befehlszeilenwerkzeug generieren; den Token **nicht hier im Chat teilen**.
3. Im PythonAnywhere-Reiter **Files** die ZIP-Datei `Wichtelzauber_online_kostenlos.zip` hochladen.
4. Unter **Consoles** eine **Bash**-Konsole starten und die folgenden Befehle eingeben:

   ```bash
   cd ~
   unzip -o Wichtelzauber_online_kostenlos.zip
   cd wichtelzauber
   bash online/pythonanywhere_deploy.sh
   ```

5. Die Fragen beantworten und ein eigenes **Adminpasswort mit mindestens zwölf Zeichen** eingeben. Dabei wird kein Passwort im Skript gespeichert.
6. Wenn der Befehl erfolgreich war, lautet die App-Adresse beispielsweise `https://DEINBENUTZERNAME.eu.pythonanywhere.com/` (ersetze DEINBENUTZERNAME durch deinen echten Kontonamen). Der Adminbereich liegt unter `/admin`.
7. Öffne die Adresse auf dem Handy. Erst danach in der App die Wichtelgruppe erstellen und den **von der App erzeugten Gruppenlink** an deine Familie schicken.
8. **Regelmäßig verlängern:** Im PythonAnywhere-Konto rechtzeitig die kostenlose Web-App verlängern, sonst wird die Website deaktiviert. Prüfe für ASGI-Beta-Websites die aktuelle Verlängerungsmöglichkeit im Account; die Web-Verwaltung für ASGI ist eingeschränkt.

Die SQLite-Datei liegt dauerhaft in deinem PythonAnywhere-Dateisystem; sie darf **nicht** bei jedem Deploy überschrieben werden. Im ZIP liegt absichtlich **keine echte Datenbank mit Familie/PINs**.

### Falls PythonAnywhere beim Erstellen einen Fehler meldet

ASGI ist ein Beta-Feature. Prüfe im Konto, ob dein Plan es aktuell unterstützt und ob der API-Token erstellt wurde. PythonAnywhere dokumentiert es hier: https://help.pythonanywhere.com/pages/ASGICommandLine . Sollte dieses kostenlose Hosting derzeit nicht zugänglich sein, nutze **Möglichkeit B**. **Nicht** einfach Render/Netlify als Ersatz für das Backend nehmen, wenn deren kostenlose Dateisysteme keine dauerhafte SQLite-Speicherung gewährleisten.

## Möglichkeit B: Kostenloser Familienlink über deinen eigenen PC mit Tailscale Funnel

Das ist der robustere Weg, **den existierenden Python-/SQLite-Code unverändert und ohne Cloud-Datenbank** zu nutzen. Tailscale Funnel stellt einen **öffentlichen HTTPS-Link** bereit, der von allen Familienmitgliedern **ohne Tailscale-App und ohne Login bei Tailscale** geöffnet werden kann. Dein Rechner muss dafür dauerhaft eingeschaltet und mit dem Internet verbunden sein. Der kostenlose Personalplan genügt üblicherweise für eine Familien-App.

**Einmaliger Start:**

1. Kostenloses Tailscale-Konto auf https://tailscale.com/ eröffnen und Tailscale auf dem Computer installieren und anmelden.
2. Python 3.11+ installieren, falls noch nicht vorhanden.
3. Das ZIP auf deinem Rechner entpacken.
4. **Windows:** Datei `online/TAILSCALE_START_WINDOWS.ps1` in PowerShell starten. Wenn Windows die Ausführung blockiert, die Datei in PowerShell gezielt mit `powershell -ExecutionPolicy Bypass -File .\online\TAILSCALE_START_WINDOWS.ps1` aus dem App-Ordner starten. **Mac/Linux:** im Terminal im Projektordner `bash online/TAILSCALE_START_LINUX_MAC.sh` ausführen.
5. Wenn Tailscale die einmalige Funnel-Freigabe im Browser verlangt, diese in deinem Tailscale-Konto bestätigen. Danach nochmals das Skript starten.
6. Die Ausgabe zeigt eine URL ähnlich `https://mein-pc.meinnetz.ts.net/`. **Nur den tatsächlich angezeigten Link teilen.**
7. Auf dem Handy im Mobilfunknetz testen, dass sowohl Startseite als auch Adminanmeldung laden. Dann Gruppe anlegen und Einladungslink weitergeben.

**Hinweise:** Falls Windows PowerShell 5.1 `Start-Process -Environment` nicht kennt, die App in einem zweiten PowerShell-Fenster manuell so starten:

```powershell
$env:WZ_SECURE_COOKIES = '1'
.\.venv\Scripts\python.exe -m uvicorn wichtelzauber.app:app --host 127.0.0.1 --port 8000
```

Im ersten Fenster dann `tailscale funnel --bg 8000` und `tailscale funnel status` eingeben. Dabei **keine Router-Portweiterleitung** öffnen. Rechner und Tailscale aktuell halten. Tailscale-Dokumentation: https://tailscale.com/docs/use-cases/application-testing/share-local-dev-server-with-internet

## Sicherheitsregeln für beide Varianten

- Öffne keine geheimen PINs über Screenshots oder WhatsApp.
- Verwende ein gutes, eigenes Adminpasswort und bestätige die Personen persönlich.
- Teile nur den Gruppenlink mit der Familie.
- Bewahre Datenbanksicherungen auf, insbesondere vor dem nächsten Wichteljahr.
- Teste den öffentlichen HTTPS-Link einmal auf einem anderen Gerät im Mobilfunknetz, bevor du ihn verteilst.

## Was kostet was?

| Betrieb | Preis | PC ständig an? | Hinweise |
|---|---:|---|---|
| PythonAnywhere Free (wenn ASGI-Beta verfügbar) | 0 € | Nein | Regelmäßige Verlängerung, begrenzte Ressourcen, Beta-Einschränkungen |
| Tailscale Funnel auf eigenem PC | 0 € Dienstkosten | Ja | Stromverbrauch möglich, öffentlicher Link nur bei laufendem PC |

**Weder dieses Dokument noch der Projektcode veröffentlichen von selbst eine Website.** Für einen echten öffentlichen Link ist einmalig das Hostingkonto oder das eigene Gerät des Nutzers erforderlich.
