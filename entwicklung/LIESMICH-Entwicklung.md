# Entwicklung (nicht Teil der Auslieferung)

Dieser Ordner enthält die Prüfskripte, die Bauwerkzeuge für `Jahresring-Setup.exe` und die Generatoren der
Arbeitsschutz-Vorlagen. Er wird beim Bauen nicht mit ausgeliefert.

Die Skripte erwarten ihre Arbeitsordner unter `/tmp/claude-0/t/` (Linux-Testumgebung, Playwright und Chromium
vorhanden). Wiederherstellen:

    bash entwicklung/einrichten.sh

Danach gelten die Abläufe aus `docs/Technische_Dokumentation.md` (Abschnitt Tests), z. B.:

    bash /tmp/claude-0/t/lauf/teil1.sh   # Grundtests, Kalkulation, E-Rechnung
    bash /tmp/claude-0/t/lauf/teil2.sh   # Sicherheit, GoBD, Rechte, XSS
    bash /tmp/claude-0/t/lauf/teil3.sh   # Status, Kalender, Export, Fuzzing
    bash /tmp/claude-0/t/lauf/teil4.sh   # Arbeitsschutz, Layout, Dokument-PDFs
    bash /tmp/claude-0/t/lauf/teil5.sh   # Bank, DATEV, Preise, Wiedervorlagen, neue Prüfungen (neu/)
    bash /tmp/claude-0/t/lauf/teil6.sh   # Prüfungen zur Version 149: Sicherheit, Rechnen, Bank, Importe, Protokoll, Datenschutz, Personal, Druckweg, Zahleneingabe; Version 150: Datenübernahme; Version 151: Erinnerungen des Arbeitsschutzes auf der Startseite; Version 152: Umsetzung des zweiten Prüfberichts
    bash /tmp/claude-0/t/lauf/alle.sh    # alle sechs Teile nacheinander (etwa 50 Minuten); danach python3 /tmp/claude-0/t/lauf/auswerten.py
    bash /tmp/claude-0/t/lauf/tor.sh     # Schnellprüfung (etwa 25 Minuten): Syntax, doppelte Namen, Kalkulation, Kalender, die Prüfungen aus neu/, Datenübernahme, Oberfläche, Druckweg
    bash /tmp/claude-0/t/inst/bauen.sh   # Jahresring.zip und Jahresring-Setup.exe – läuft nur, wenn die Schnellprüfung besteht

Ergebnisse stehen in `/tmp/claude-0/t/lauf/*.txt`.

Zusätzlich nötig seit Version 149: `xvfb-run` für `neu/druckweg.js` (startet den Chromium von Playwright mit Fenster und druckt über den Druckweg des Browsers in eine PDF-Datei), das pip-Paket `libfaketime` für `neu/datenschutz149.py` (Zeitsprung hinter das Ende der Aufbewahrungsfrist). Mit `BUERO_PY=/pfad/zu/python3.14 bash /tmp/claude-0/t/lauf/tor.sh` läuft der Server der Prüfinstanz unter einer anderen Python-Version. `lauf/vergleich.py` vergleicht die Ausgaben einer Gesamtprüfung mit einem gesicherten Stand (`lauf/stand_<Version>/`). Die Skripte der Programmprüfung vom November 2026 liegen unter `t/audit4/` (Befunde in `befunde.md`, Umsetzung in `umsetzung.md`, Messung der Oberfläche `ui_stil.js` + `ui_auswert.py`, Ergänzungen der Unterlagen `doku/`).

Datenübernahme auf einen neuen PC (Version 150): `neu/uebernahme150.py` baut sich seine Instanzen selbst unter `/tmp/claude-0/t/up150/` – „alter PC“ (Port 8798, mit Rechnung, Anhang, Eingangsrechnung, Sicherungskennwort und externem Ziel), fremder Bestand (8796) und „neuer PC“ (8797) – jeweils in eigenen Ordnern, damit die gespeicherten Dateipfade des alten Bestands am neuen Ort nicht stimmen. Geprüft werden Suche, Ablehnungen, die Übernahme aus Ordner, zu tief kopiertem Ordner, verschlüsselter und unverschlüsselter Sicherung und Datenbanksicherung, derselbe PC nach Datenbankverlust, fremde Bestände im Echtbetrieb, die Rücksicherung fremder und eigener Sicherungen, der Zugriff über die Netzwerkadresse und die Bausteine für Windows mit nachgestellten Systemaufrufen. `neu/uebernahme_ui.js` geht danach die Seiten im Browser durch (braucht den alten Bestand aus dem ersten Skript und `t/up150/neupc.sh`; Bildschirmfotos in `/tmp/claude-0/t/up150/bild/`). Unter Windows selbst ist davon nichts erprobt: Laufwerkssuche, Auswahlfenster (PowerShell) und das Kopieren bei geöffnetem Programm gehören in die Funktionsprobe der Installationsanleitung.

Erinnerungen des Arbeitsschutzes auf der Startseite (Version 151): `neu/startas151.py` erwartet eine frische Prüfinstanz (`bash /tmp/claude-0/t/v25/neu.sh`) und prüft an der Schnittstelle Vorgabe, Aus- und Einschalten, Protokoll, die unveränderte Übersicht, die übrigen Hinweise, die Zählung der Mitarbeiter und die Rechte von Büro und Werkstatt. `neu/startas_ui.js` baut sich die Instanz selbst auf und prüft dasselbe im Browser (Schalter unter Einstellungen › Programm, Kachel und Hinweis auf der Startseite, Vermerk in der Übersicht); Bildschirmfotos in `/tmp/claude-0/t/lauf/bild151/`.

Probe eines Updates mit vorhandenen Daten: `t/up148/` setzt eine Instanz mit dem Programmstand 148 auf, legt Daten an (Rechnung im Echtbetrieb, versandtes Angebot, Kontoauszug, Mitarbeiter mit vierstelliger PIN, Stempelzeiten), spielt dann den aktuellen Stand darüber und prüft Anmeldung, Datenbankumbau, Protokoll, Belegprüfung, Dublettenerkennung und alle Seiten. Ablauf im Kopf von `neu148.sh`.

Umsetzung des zweiten Prüfberichts (Version 152): `neu/bank152.py` (Skonto, Zahlerkonten, Sammelbuchung), `rechnen152.py` (Einheiten, Warnungen, Abschläge, Lohnanteil, DATEV-Skonto), `import152.py` (Stückliste, Preisliste, Kunden), `widerruf152.py`, `sicher152.py` (Zugriff, Fehlversuche, Exportdateien, Anonymisieren), `spur152.py` (legt mit `spur_seed.py` einen Bestand mit auffälligen Werten an und ruft je eingeschränkter Rolle die Adressen aus `spur_adressen.json` ab) und `pflege152.py` (gesetzliche Werte mit Stichtag, Prüfung der Einstellungen und Datumsfelder, gleichzeitiges Bearbeiten, Startseite, große Preisliste, Versionsprüfung beim Start; startet dafür eine zweite Instanz auf Port 8793) erwarten jeweils eine frische Prüfinstanz. `neu/widerruf_ui.js` und `neu/ui152.js` bauen sich ihre Instanz selbst auf; `ui152.js` misst auf rund 130 Seiten Höhen, Beschriftungen und Überstand (390 und 820 Pixel) und geht die Seite „Gesetzliche Werte“ durch.

Prüfkette auf jedem Betriebssystem: `python3 entwicklung/pruefen.py` (unter Windows `python entwicklung\pruefen.py`) führt die Prüfungen der Schnittstelle ohne die Linux-Umgebung aus – je Prüfung eine frische Instanz auf Port 8799 in einem Arbeitsordner (`JR_PRUEF_ORDNER`, sonst im Temp-Ordner), die Pfade der Skripte werden in Kopien ersetzt. `--liste` nennt die Prüfungen, einzelne Namen wählen aus. `neu/windows152.py` läuft nur unter Windows (PDF über Edge, DPAPI, start.bat, Autostart, Taskleistensymbol). Bei GitHub läuft die Kette mit jeder neuen `version.txt` auf einem Windows-Rechner (`.github/workflows/pruefkette-windows.yml`, auch von Hand zu starten); das Ergebnis steht dort unter „Actions“. Die Browserprüfungen (Playwright) laufen weiter nur unter Linux.

Messungen (Version 152): `lauf/p5_bench.py` rechnet die Vorschläge der Kontoauszüge an erzeugten Daten ohne Instanz; `lauf/p6_mess.py` (Löschliste, Startseite) und `lauf/p7_prof.py` (Startseite mit Profil) erwarten den Großbestand unter `/tmp/claude-0/t/perf152/`; `lauf/p8_bench.py` (Preisliste mit 21.000 Zeilen anlegen, abgleichen, übernehmen) läuft gegen eine frische Prüfinstanz.
