"""Jahresring – Prüfkette, unabhängig vom Betriebssystem (Windows und Linux).

Für jede Prüfung wird eine frische Instanz des Programms gestartet (eigener, leerer Datenordner, Port 8799); das Prüfskript aus
entwicklung/t läuft dagegen und meldet am Ende „FEHLER: []“. Die Skripte sind in der Entwicklungsumgebung entstanden und nennen
deren Pfade (/tmp/claude-0/t, /home/claude/eberle-buero); hier wird vor dem Lauf eine Kopie mit den Pfaden dieses Rechners
angelegt – die Skripte selbst bleiben, wie sie sind.

Aufruf:   python entwicklung/pruefen.py            alle Prüfungen der Liste (unter Windows zusätzlich die Windows-Prüfung)
          python entwicklung/pruefen.py rechnen152 widerruf152      nur die genannten
          python entwicklung/pruefen.py --liste    Namen der Prüfungen
Ergebnis: Zeile je Prüfung, am Ende „Prüfkette bestanden“ (Rückgabewert 0) oder „NICHT bestanden“ (1). Die Ausgaben der
          Prüfungen liegen im Arbeitsordner, der am Anfang genannt wird (Umgebungsvariable JR_PRUEF_ORDNER legt ihn fest).

Diese Kette prüft die Schnittstelle des Programms, seine Rechenwege und – unter Windows – das, was nur Windows kann
(Verschlüsselung der Zugangsdaten, Autostart, PDF über Edge, start.bat, Symbol neben der Uhr). Die Prüfungen der Bedienoberfläche
im Browser und der Bau des Installationsprogramms laufen in der Entwicklungsumgebung (entwicklung/t/lauf/tor.sh)."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace("\\", "/")
QUELLE_T = os.path.join(REPO, "entwicklung", "t")
PORT = 8799
URL = f"http://127.0.0.1:{PORT}"
OK = "FEHLER: []"

# (Name, Skript unter entwicklung/t, Merkmal des Erfolgs in der Ausgabe, frische Instanz davor, Zeitgrenze in Sekunden, wo)
# wo: "" überall · "linux" nur dort (die Prüfung stellt die Uhr des Programms um oder startet es selbst neu) · "windows" nur dort
PRUEFUNGEN = [
    ("namen", "neu/namen.py", OK, False, 120, ""),
    ("kalkulation", "audit/kalk_test.py", "alles stimmt", False, 300, ""),
    ("kalender", "neu/kalender_test.py", None, False, 300, ""),
    ("pruefungen", "neu/pruef.py", OK, True, 600, ""),
    ("pruefungen141", "neu/pruef141.py", OK, True, 600, ""),
    ("update_pdf", "neu/update_test.py", OK, False, 600, ""),
    ("kontoauszug_entfernen", "neu/bank_weg.py", OK, True, 600, ""),
    ("zahlungsplan", "neu/plan_wochen.py", OK, True, 600, ""),
    ("dateiname", "neu/dateiname.py", OK, True, 600, ""),
    ("uebertrag", "neu/uebertrag.py", OK, True, 600, ""),
    ("preisimport", "bank/preise.py", OK, True, 600, ""),
    ("sicher149", "neu/sicher149.py", OK, True, 900, "linux"),
    ("rechnen149", "neu/rechnen149.py", OK, True, 900, ""),
    ("bank149", "neu/bank149.py", OK, True, 600, ""),
    ("import149", "neu/import149.py", OK, True, 600, ""),
    ("nachweis149", "neu/nachweis149.py", OK, True, 600, ""),
    ("datenschutz149", "neu/datenschutz149.py", OK, True, 900, "linux"),
    ("personal149", "neu/personal149.py", OK, True, 600, ""),
    ("startas151", "neu/startas151.py", OK, True, 600, ""),
    ("bank152", "neu/bank152.py", OK, True, 600, ""),
    ("rechnen152", "neu/rechnen152.py", OK, True, 900, ""),
    ("import152", "neu/import152.py", OK, True, 600, ""),
    ("widerruf152", "neu/widerruf152.py", OK, True, 600, ""),
    ("sicher152", "neu/sicher152.py", OK, True, 900, ""),
    ("spur152", "neu/spur152.py", OK, True, 1500, ""),
    ("pflege152", "neu/pflege152.py", OK, True, 900, ""),
    ("windows152", "neu/windows152.py", OK, True, 1200, "windows"),
]

arbeit = os.environ.get("JR_PRUEF_ORDNER") or tempfile.mkdtemp(prefix="jr-pruefkette-")
arbeit = os.path.abspath(arbeit).replace("\\", "/")
T = arbeit + "/t"
INSTANZ = T + "/v25/eberle-buero"
ERSATZ_BROWSER = "/tmp/claude-0/t/fake/chrome"   # in der Entwicklungsumgebung gibt es kein Edge; dort druckt ein Ersatz die PDFs
laufend = {"p": None}


def ersetzen(text):
    """Pfade der Entwicklungsumgebung → Pfade dieses Rechners (mit Schrägstrichen, die auch Windows versteht)."""
    import re
    text = re.sub(r"/tmp/claude-0/-home-claude/[0-9a-f-]+/scratchpad", arbeit + "/ablage", text)
    text = text.replace(ERSATZ_BROWSER, "\0browser\0")   # der PDF-Ersatz der Entwicklungsumgebung bleibt, wo er ist
    return text.replace("/tmp/claude-0/t", T).replace("/home/claude/eberle-buero", REPO).replace("\0browser\0", ERSATZ_BROWSER)


def skripte_bereitstellen():
    for ordner in ("neu", "sec", "bank", "audit"):
        quelle, ziel = os.path.join(QUELLE_T, ordner), os.path.join(T, ordner)
        os.makedirs(ziel, exist_ok=True)
        for n in os.listdir(quelle):
            pfad = os.path.join(quelle, n)
            if not os.path.isfile(pfad):
                continue
            if n.endswith((".py", ".json", ".js", ".txt")):
                with open(pfad, encoding="utf-8") as f:
                    inhalt = f.read()
                with open(os.path.join(ziel, n), "w", encoding="utf-8", newline="\n") as f:
                    f.write(ersetzen(inhalt))
            else:
                shutil.copy2(pfad, os.path.join(ziel, n))
    for ordner in ("lauf", "v25", "v25/projekte"):
        os.makedirs(os.path.join(T, ordner), exist_ok=True)
    os.makedirs(arbeit + "/ablage", exist_ok=True)


def instanz_stoppen():
    p = laufend["p"]
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=20)
    laufend["p"] = None
    if os.path.isdir("/proc"):   # Linux: Zwei Prüfungen starten das Programm selbst neu – auch diese Instanz beenden
        for n in os.listdir("/proc"):
            if n.isdigit() and int(n) != os.getpid():
                try:
                    with open(f"/proc/{n}/environ", "rb") as f:
                        if f"BUERO_PORT={PORT}".encode() in f.read().split(b"\0"):
                            os.kill(int(n), 15)
                except OSError:
                    pass
        for _ in range(40):
            try:
                urllib.request.urlopen(URL + "/api/version", timeout=1).read()
                time.sleep(0.25)
            except OSError:
                break


def _leeren(pfad):
    """Ordner entfernen; unter Windows gibt ein eben beendetes Programm seine Dateien nicht sofort frei."""
    for _ in range(40):
        if not os.path.isdir(pfad):
            return
        shutil.rmtree(pfad, ignore_errors=True)
        if os.path.isdir(pfad):
            time.sleep(0.5)
    raise RuntimeError(f"Der Ordner {pfad} lässt sich nicht leeren.")


def umgebung(instanz=False):
    """Umgebung für das Programm (mit Port) bzw. für ein Prüfskript (ohne – zwei Skripte suchen das Programm an dieser Angabe)."""
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", JR_PRUEF_T=T, JR_PRUEF_REPO=REPO, JR_PRUEF_ORDNER=arbeit)
    env.pop("BUERO_PORT", None)
    if instanz:
        env["BUERO_PORT"] = str(PORT)
        if os.name != "nt" and "BUERO_BROWSER" not in env and os.path.isfile(ERSATZ_BROWSER):
            env["BUERO_BROWSER"] = ERSATZ_BROWSER
    return env


def instanz_neu():
    """Frische Instanz: Programmdateien ohne Datenordner in den Arbeitsordner kopieren und starten."""
    instanz_stoppen()
    _leeren(INSTANZ)
    _leeren(T + "/v25/projekte")
    os.makedirs(T + "/v25/projekte")
    shutil.copytree(REPO, INSTANZ, ignore=shutil.ignore_patterns("daten", ".git", ".github", "entwicklung", "__pycache__", "*.exe", "*.zip"))
    log = open(os.path.join(arbeit, "instanz.log"), "a", encoding="utf-8")
    log.write(f"\n===== frische Instanz {time.strftime('%H:%M:%S')}\n")
    log.flush()
    laufend["p"] = subprocess.Popen([sys.executable, "app.py", "--konsole", "--kein-browser"], cwd=INSTANZ, env=umgebung(True), stdout=log, stderr=subprocess.STDOUT)
    ende = time.time() + 120
    while time.time() < ende:
        if laufend["p"].poll() is not None:
            raise RuntimeError("Das Programm ist beim Start beendet worden – siehe instanz.log im Arbeitsordner.")
        try:
            with urllib.request.urlopen(URL + "/api/version", timeout=3) as r:
                if r.status == 200:
                    return
        except OSError:
            time.sleep(0.4)
    raise RuntimeError("Das Programm antwortet nach 120 Sekunden nicht.")


def pruefung(name, skript, merkmal, frisch, grenze, wo):
    if frisch:
        instanz_neu()
    ziel = os.path.join(arbeit, f"aus_{name}.txt")
    t0 = time.time()
    try:
        with open(ziel, "w", encoding="utf-8") as aus:
            rc = subprocess.run([sys.executable, os.path.join(T, skript)], cwd=arbeit, env=umgebung(), stdout=aus, stderr=subprocess.STDOUT, timeout=grenze).returncode
    except subprocess.TimeoutExpired:
        rc = -1
    with open(ziel, encoding="utf-8", errors="replace") as f:
        text = f.read()
    gut = rc == 0 and (merkmal is None or merkmal in text) and "Traceback (most recent call last)" not in text
    print(f"{'ok    ' if gut else 'FEHLER'} {name:<22} {time.time() - t0:6.1f} s" + ("" if gut else f"   (Ausgabe: {ziel})"), flush=True)
    for z in text.splitlines():
        if z.startswith("HINWEIS"):
            print("        " + z[:400], flush=True)
    if not gut:
        if rc == -1:
            print(f"        Zeitgrenze von {grenze} Sekunden überschritten", flush=True)
        alle = text.splitlines()
        zeilen = [z for z in alle if z.startswith("FEHLER")][:40]
        if "Traceback (most recent call last)" in text or not zeilen:   # Abbruch: das Ende der Ausgabe zeigt, wo
            zeilen += ["…"] + alle[-25:]
        print("\n".join("        " + z[:900] for z in zeilen), flush=True)
    return gut


def main():
    wahl = [a for a in sys.argv[1:] if not a.startswith("-")]
    hier = "windows" if os.name == "nt" else "linux"
    if "--liste" in sys.argv:
        print("\n".join(f"{p[0]:<24}{p[1]:<28}{p[5] and 'nur ' + p[5]}" for p in PRUEFUNGEN))
        return 0
    liste = [p for p in PRUEFUNGEN if (p[0] in wahl if wahl else p[5] in ("", hier))]
    unbekannt = [w for w in wahl if w not in [p[0] for p in PRUEFUNGEN]]
    if unbekannt:
        print("Unbekannte Prüfung:", ", ".join(unbekannt))
        return 1
    print(f"Jahresring-Prüfkette · Python {sys.version.split()[0]} · {sys.platform} · Arbeitsordner {arbeit}", flush=True)
    skripte_bereitstellen()
    fehler = []
    try:
        for p in liste:
            if not os.path.isfile(os.path.join(T, p[1])):
                print(f"FEHLER {p[0]:<22} Skript fehlt: {p[1]}", flush=True)
                fehler.append(p[0])
                continue
            try:
                if not pruefung(*p):
                    fehler.append(p[0])
            except Exception as f:  # noqa: BLE001 – eine Prüfung darf die übrigen nicht aufhalten
                print(f"FEHLER {p[0]:<22} {f}", flush=True)
                fehler.append(p[0])
    finally:
        instanz_stoppen()
    if os.path.isfile(os.path.join(arbeit, "instanz.log")):
        with open(os.path.join(arbeit, "instanz.log"), encoding="utf-8", errors="replace") as f:
            spur = [z for z in f.read().splitlines() if z.startswith("Traceback")]
        if spur:
            print(f"Hinweis: {len(spur)} unbehandelte Fehler im Protokoll der Instanzen (instanz.log im Arbeitsordner)", flush=True)
    ausgelassen = [p[0] for p in PRUEFUNGEN if not wahl and p[5] not in ("", hier)]
    if ausgelassen:
        print("Auf diesem System nicht vorgesehen: " + ", ".join(ausgelassen), flush=True)
    print(f"Prüfkette bestanden ({len(liste)} Prüfungen)" if not fehler else "Prüfkette NICHT bestanden: " + ", ".join(fehler), flush=True)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
