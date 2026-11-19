"""Version 152, Windows-Prüfung (Z13): was nur unter Windows vorkommt und deshalb in der Entwicklungsumgebung nie lief.
Zugangsdaten über die Datenschutz-API des Benutzerkontos, Autostart-Verknüpfung, PDF über Edge samt E-Rechnung, Programmstart über
start.bat im Hintergrund mit Symbol neben der Uhr, das in start.bat eingetragene Python-Installationsprogramm.
Erwartet eine frische Prüfinstanz (python entwicklung/pruefen.py windows152). Zeilen mit HINWEIS sind Auskünfte, keine Fehler."""
import json, sys, os, re, io, time, base64, sqlite3, subprocess, shutil, hashlib, platform, urllib.request, urllib.error
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
Q = "/home/claude/eberle-buero"
T = "/tmp/claude-0/t"
I = "/tmp/claude-0/t/v25/eberle-buero"
D = I + "/daten"
sys.path.insert(0, I); sys.path.insert(0, I + "/lib")   # Module aus der Prüfkopie, damit im Programmordner nichts angelegt wird
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:900]), flush=True)
    if not bed: fehler.append(name)
def hinweis(text): print("HINWEIS " + str(text)[:600], flush=True)
_T0 = time.time()
_druck = print
def print(*a, **k):   # Überschriften der Abschnitte mit der bis dahin vergangenen Zeit (hilft, langsame Schritte zu finden)
    if a and isinstance(a[0], str) and a[0].startswith("== "): hinweis(f"{time.time() - _T0:6.1f} s  {a[0][3:]}")
    _druck(*a, **k)
if os.name != "nt":
    print("Diese Prüfung läuft nur unter Windows."); print("FEHLER:", fehler); sys.exit(0)

PS_ZEITEN = []   # Dauer jedes PowerShell-Aufrufs dieser Prüfung in Sekunden
def ps(befehl, zeit=120, env=None):
    """PowerShell-Befehl ausführen, Ausgabe als Text"""
    t_ps = time.time()
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", befehl], capture_output=True, timeout=zeit, env=env)
    PS_ZEITEN.append(round(time.time() - t_ps, 1))
    return (r.stdout or b"").decode("utf-8", "replace").strip(), (r.stderr or b"").decode("utf-8", "replace").strip(), r.returncode

hinweis(f"Windows {platform.platform()} · Python {sys.version.split()[0]} · Benutzer {os.environ.get('USERNAME', '?')}")
shell_da = "explorer.exe" in subprocess.run(["tasklist", "/FI", "IMAGENAME eq explorer.exe"], capture_output=True, timeout=60).stdout.decode("cp850", "replace").lower()
hinweis("Windows-Oberfläche (explorer.exe) läuft: " + ("ja" if shell_da else "nein – das Symbol neben der Uhr lässt sich dann nicht prüfen"))

print("== Zugangsdaten: Datenschutz-API des Windows-Benutzerkontos")
import geheim
klar = "Sommer-2026!äöü€"
try:
    g = geheim.verschluesseln(klar)
    ok("Verschlüsselter Wert beginnt mit „dpapi:“ und enthält den Klartext nicht", g.startswith("dpapi:") and "Sommer" not in g and len(g) > 60, g[:80])
    ok("Entschlüsseln liefert den Klartext mit Umlauten und Eurozeichen zurück", geheim.entschluesseln(g) == klar, geheim.entschluesseln(g))
    ok("Ein schon verschlüsselter Wert wird nicht ein zweites Mal verschlüsselt", geheim.verschluesseln(g) == g)
    ok("Ein verfälschter Wert ergibt einen leeren Text statt eines Fehlers", geheim.entschluesseln("dpapi:" + base64.b64encode(b"x" * 90).decode()) == "" and geheim.entschluesseln("dpapi:kein-base64!") == "")
    ok("Leerer Wert bleibt leer", geheim.verschluesseln("") == "" and geheim.entschluesseln("") == "")
except Exception as f:  # noqa: BLE001
    ok("Verschlüsselung ohne Ausnahme", False, repr(f))

inh = cl()
s0 = rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})[0]
s1 = rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})[0]
ok("Einrichten und Anmelden an der Prüfinstanz", s0 == 200 and s1 == 200, (s0, s1))
def A(m, p, d=None, h=None):
    s, b, hd = rq(inh, m, "/api/" + p, d, {"X-Rueckfrage": "1", **(h or {})}); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
A("PUT", "einstellungen", {"firma": "Muster Schreinerei", "firma_anschrift": "Weg 1\n88069 Tettnang", "firma_inhaber": "Jonas Muster", "steuernummer": "12/345/67890",
                           "firma_telefon": "07542 1", "firma_email": "a@b.example", "zugferd": True, "sepa_iban": "DE02120300000000202051", "sepa_bic": "BYLADEM1001"})
x = A("PUT", "einstellungen", {"mail": {"server": "smtp.beispiel.example", "port": 587, "benutzer": "buero@beispiel.example", "passwort": klar}})
ok("Mailzugang gespeichert", x["_s"] == 200, x)
con = sqlite3.connect(D + "/buero.db", timeout=30); con.row_factory = sqlite3.Row
mz = json.loads(con.execute("SELECT wert FROM einstellungen WHERE schluessel='mail'").fetchone()[0])
ok("In der Datenbank steht das Mailpasswort verschlüsselt (dpapi:), nicht im Klartext", str(mz.get("passwort", "")).startswith("dpapi:"), str(mz.get("passwort"))[:30])
ok("Derselbe Windows-Benutzer kann es wieder lesen", geheim.entschluesseln(mz.get("passwort")) == klar)
roh = b"".join(open(D + "/buero.db" + e, "rb").read() for e in ("", "-wal") if os.path.exists(D + "/buero.db" + e))
ok("Der Klartext steht nirgends in den Dateien der Datenbank", klar.encode("utf-8") not in roh and klar.encode("utf-16-le") not in roh)
e = A("GET", "einstellungen")
ok("Die Einstellungen geben das Passwort nicht heraus, nur „gesetzt“", klar not in json.dumps(e, ensure_ascii=False) and "dpapi:" not in json.dumps(e) and (e.get("mail") or {}).get("passwort_gesetzt") is True, e.get("mail"))
x = A("POST", "service/kennwort", {"kennwort": "Sicherung-2026-lang", "kennwort2": "Sicherung-2026-lang"})
sd = D + "/sicherung.schluessel"
ok("Sicherungskennwort gesetzt; der Schlüssel liegt an das Benutzerkonto gebunden in daten/sicherung.schluessel",
   x.get("gesetzt") is True and os.path.isfile(sd) and "dpapi:" in open(sd, encoding="utf-8").read() and "Sicherung-2026-lang" not in open(sd, encoding="utf-8").read(), (x, os.path.isfile(sd)))
x = A("POST", "service/kennwort", {"pruefen": True, "kennwort": "Sicherung-2026-lang"}); y = A("POST", "service/kennwort", {"pruefen": True, "kennwort": "falsch"})
ok("Kennwortprüfung: richtiges stimmt, falsches nicht", x.get("stimmt") is True and y.get("stimmt") is False, (x, y))

print("== Autostart")
lnk = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Jahresring.lnk")
if os.path.exists(lnk):
    hinweis("Auf diesem PC gibt es schon eine Autostart-Verknüpfung für Jahresring; sie wird nicht angefasst, die Prüfung des Autostarts entfällt.")
else:
    try:
        t_as = time.time(); x = A("POST", "autostart", {"aktiv": True, "fenster": False})
        hinweis(f"Autostart einschalten (das Programm ruft dafür PowerShell auf): {time.time() - t_as:.1f} s")
        ok("Autostart einschalten legt die Verknüpfung im Autostart-Ordner an", x["_s"] == 200 and x.get("aktiv") is True and os.path.isfile(lnk), x)
        aus, err, rc = ps("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:JR_L); Write-Output ($s.TargetPath + '|' + $s.Arguments + '|' + $s.WorkingDirectory + '|' + $s.WindowStyle)", env=dict(os.environ, JR_L=lnk))
        ziel = (aus.split("|") + ["", "", "", ""])[:4]
        gleich = lambda a, b: os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))
        ok("Die Verknüpfung startet start.bat im Programmordner, ohne Fenster (kein-browser), minimiert", gleich(ziel[0], I + "/start.bat") and ziel[1] == "kein-browser" and gleich(ziel[2], I) and ziel[3] == "7", (aus, err))
        x = A("POST", "autostart", {"aktiv": True, "fenster": True})
        aus2 = ps("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:JR_L); Write-Output ('[' + $s.Arguments + ']')", env=dict(os.environ, JR_L=lnk))[0]
        ok("Mit „Fenster öffnen“ startet die Verknüpfung ohne den Zusatz; die Antwort nennt den neuen Stand", aus2 == "[]" and x.get("fenster") is True, (aus2, x))
        ok("Die Einstellungen zeigen danach denselben Stand", (A("GET", "einstellungen").get("_autostart") or {}).get("fenster") is True)
        x = A("POST", "autostart", {"aktiv": False, "fenster": False})
        ok("Autostart ausschalten entfernt die Verknüpfung", x["_s"] == 200 and x.get("aktiv") is False and not os.path.exists(lnk), x)
    finally:
        if os.path.exists(lnk): os.remove(lnk)

print("== PDF über Edge")
os.chdir(I)
import app as _programm   # nur für browser_finden: dieselbe Suche wie im Programm
exe = _programm.browser_finden()
ok("Edge oder Chrome gefunden", bool(exe), "kein Browser")
hinweis(f"PDF-Browser: {exe}")
from pypdf import PdfReader
k = A("POST", "kunden", {"kurzname": "Haus, Hanna", "nachname": "Haus", "vorname": "Hanna", "anredeform": "Frau", "strasse": "Gartenweg", "hausnr": "4", "plz": "88069", "ort": "Tettnang", "gruppe": "Privatkunde"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Einbauschrank Größe ÄÖÜ"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Einbauschrank in Eiche, geölt"}); pid = po.get("id") or po["position"]["id"]
A("PUT", f"positionen/{pid}", {"einzelpreis": 4200, "preis_manuell": 1, "menge": 1})
ang = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"})
t0 = time.time(); s, pdf, hd = rq(inh, "GET", f"/druck/{ang['id']}.pdf", roh=True); dauer = time.time() - t0
istpdf = s == 200 and isinstance(pdf, bytes) and pdf[:5] == b"%PDF-"
ok(f"Angebot als PDF erzeugt ({dauer:.1f} s)", istpdf, (s, pdf[:300] if isinstance(pdf, (bytes, str)) else pdf))
if istpdf:
    text = " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages)
    ok("Das PDF enthält Kunde, Position und Betrag (Umlaute lesbar)", "Hanna Haus" in text and "geölt" in text and "4.200,00" in text, text[:400])
    hinweis(f"Angebot: {len(PdfReader(io.BytesIO(pdf)).pages)} Seite(n), {len(pdf) // 1024} KB, erster Aufruf {dauer:.1f} s")
t0 = time.time(); s, pdf2, _ = rq(inh, "GET", f"/druck/{ang['id']}.pdf", roh=True); dauer2 = time.time() - t0
ok(f"Zweiter Aufruf liefert wieder ein PDF ({dauer2:.1f} s)", s == 200 and isinstance(pdf2, bytes) and pdf2[:5] == b"%PDF-", s)
A("PUT", f"belege/{ang['id']}", {"agv": 1})
s, pdf3, _ = rq(inh, "GET", f"/druck/{ang['id']}.pdf", roh=True)
if s == 200 and isinstance(pdf3, bytes):
    text3 = " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf3)).pages)
    ok("Mit dem Schalter „außerhalb der Geschäftsräume“ hängen Widerrufsbelehrung und Muster-Widerrufsformular am PDF", "Widerrufsbelehrung" in text3 and "Muster-Widerrufsformular" in text3 and len(PdfReader(io.BytesIO(pdf3)).pages) >= 3, text3[:300])
else:
    ok("PDF mit Widerrufsblatt", False, (s, str(pdf3)[:300]))
re_ = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"})
f_ = A("POST", f"belege/{re_['id']}/festschreiben", {}, {"X-Bestaetigt": "position_null"}); f_ = f_.get("beleg") or f_
ok("Rechnung festgeschrieben", f_.get("status") not in (None, "entwurf") and f_.get("nummer"), f_)
s, rpdf, _ = rq(inh, "GET", f"/druck/{re_['id']}.pdf", roh=True)
if s == 200 and isinstance(rpdf, bytes) and rpdf[:5] == b"%PDF-":
    rd = PdfReader(io.BytesIO(rpdf)); namen = list((rd.attachments or {}).keys())
    ok("Die Rechnung ist eine E-Rechnung: PDF mit eingebetteter XML-Datei", any(n.lower().endswith(".xml") for n in namen), namen)
    sx, xml, _ = rq(inh, "GET", f"/api/belege/{re_['id']}/zugferd.xml")
    ok("Die XML-Datei der Rechnung nennt Rechnungsnummer und Bruttobetrag", sx == 200 and str(f_.get("nummer")) in xml and "4998.00" in xml, (sx, xml[:200]))
    arch = [os.path.join(w, n) for w, _, ns in os.walk(D) for n in ns if n.lower().endswith(".pdf") and str(f_.get("nummer")) in n]
    ok("Das PDF der Rechnung liegt im Archiv des Datenordners", bool(arch), [n for w, _, ns in os.walk(D) for n in ns if n.lower().endswith(".pdf")][:10])
else:
    ok("Rechnung als PDF", False, (s, str(rpdf)[:300]))
x = A("POST", "service/sicherung", {})
ok("Sicherung von Hand angelegt", x["_s"] == 200, x)
x = A("GET", "service/protokoll?voll=1"); bel = x.get("belege") or {}
ok("Belegprüfung nach Festschreiben ohne Befund", x["_s"] == 200 and bel.get("ok") is True, bel)
con.close()

print("== Zeitzone: Ortszeit des Programms ist die in Windows eingestellte")
PROBE = ("from datetime import datetime, timezone; "
         "print(int(datetime(2026, 11, 2, 12, tzinfo=timezone.utc).astimezone().utcoffset().total_seconds() // 60), "
         "int(datetime(2026, 6, 1, 12, tzinfo=timezone.utc).astimezone().utcoffset().total_seconds() // 60))")
def zone(vorweg="", tz=None):
    env = {k: v for k, v in os.environ.items() if k.upper() != "TZ"}
    if tz: env["TZ"] = tz
    r = subprocess.run([sys.executable, "-c", vorweg + PROBE], capture_output=True, timeout=120, env=env, cwd=I)
    return (r.stdout or b"").decode("utf-8", "replace").strip() or (r.stderr or b"").decode("utf-8", "replace").strip()[-300:]
z_win = zone()
z_tz = zone(tz="Europe/Berlin")
z_prog = zone("import kern; ", tz="Europe/Berlin")
hinweis(f"Abstand zur Weltzeit in Minuten (Winter Sommer): Windows {z_win} · mit Umgebungsvariable TZ=Europe/Berlin ohne Vorsorge {z_tz} · im Programm {z_prog}")
ok("mit einer Umgebungsvariable TZ rechnet das Programm trotzdem mit der Zeitzone von Windows", z_prog == z_win and bool(re.fullmatch(r"-?\d+ -?\d+", z_win)), (z_win, z_tz, z_prog))
ok("ohne die Variable ändert die Vorsorge nichts", zone("import kern; ") == z_win, zone("import kern; "))
if z_win != "60 120": hinweis("Der Prüfrechner steht nicht in der mitteleuropäischen Zeitzone; am Büro-PC wären es 60 und 120 Minuten.")

print("== Symbol neben der Uhr (nur Aufbau, ohne Anzeige)")
try:
    import tray
    ok("tray.py lässt sich laden; die Windows-Schnittstellen sind vorhanden", callable(tray.starten) and callable(tray.beenden))
except Exception as f:  # noqa: BLE001
    ok("tray.py lässt sich laden", False, repr(f))

print("== Programmstart über start.bat")
SB = T + "/v25/startbat"; ZP = SB + "/Jahresring"; PORT2 = 8795; U2 = f"http://127.0.0.1:{PORT2}"
def stoppen_hart():
    ps("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*startbat*Jahresring*app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
roh_bat = open(Q + "/start.bat", "rb").read()
ok("start.bat hat Windows-Zeilenenden (CRLF) und nur ASCII-Zeichen", roh_bat.count(b"\r\n") == roh_bat.count(b"\n") > 50 and all(b < 128 for b in roh_bat), (roh_bat.count(b"\r\n"), roh_bat.count(b"\n")))
for dn in ("einrichten.bat", "Handy-Freigabe.bat"):
    r_ = open(Q + "/" + dn, "rb").read()
    ok(f"{dn} hat Windows-Zeilenenden", r_.count(b"\r\n") == r_.count(b"\n") > 5, (r_.count(b"\r\n"), r_.count(b"\n")))
try:
    stoppen_hart(); shutil.rmtree(SB, ignore_errors=True)
    shutil.copytree(Q, ZP, ignore=shutil.ignore_patterns("daten", ".git", ".github", "entwicklung", "__pycache__", "*.exe", "*.zip"))
    env = {k_: v for k_, v in os.environ.items() if k_ not in ("BUERO_BROWSER",)}; env["BUERO_PORT"] = str(PORT2)
    with open(SB + "/start_aus.txt", "wb") as aus_d:
        p = subprocess.Popen(["cmd.exe", "/c", "start.bat", "kein-browser"], cwd=ZP.replace("/", "\\"), env=env, stdout=aus_d, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        try: rc = p.wait(timeout=240)
        except subprocess.TimeoutExpired: rc = None; p.kill()
    ausgabe = open(SB + "/start_aus.txt", "rb").read().decode("utf-8", "replace")
    ok("start.bat läuft durch und endet ohne Fehler (das Programm arbeitet im Hintergrund weiter)", rc == 0, (rc, ausgabe[-600:]))
    oben = False
    for i in range(240):
        try:
            v = json.loads(urllib.request.urlopen(U2 + "/api/version", timeout=3).read().decode()); oben = True; break
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    soll = re.search(r'^VERSION = "([^"]+)"', open(Q + "/app.py", encoding="utf-8").read(), re.M).group(1)
    ok("Das über start.bat gestartete Programm antwortet und nennt seine Version", oben and v.get("version") == soll, (oben, v if oben else ausgabe[-600:]))
    aus, err, rc_ = ps("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*startbat*Jahresring*app.py*' } | ForEach-Object { Write-Output ($_.Name + '|' + $_.ExecutablePath + '|' + $_.CommandLine) }")
    hinweis("Prozess nach start.bat: " + aus.replace("\r", "").replace("\n", " ;; ")[:500])
    pyv = re.search(r"Python\\(\d+\.\d+\.\d+)\\", aus)
    if pyv: hinweis(f"start.bat hat Python {pyv.group(1)} gewählt (das neueste auf diesem Rechner); das Programm läuft damit.")
    ok("Es läuft im Hintergrund über pythonw.exe (ohne Konsolenfenster) mit dem Zusatz --hintergrund", "pythonw.exe|" in aus.lower() and "--hintergrund" in aus and "--kein-browser" in aus, aus[:600])
    time.sleep(3)
    pt = ZP + "/daten/protokoll.txt"; ptext = open(pt, encoding="utf-8", errors="replace").read() if os.path.isfile(pt) else ""
    ok("Die Meldungen des Programms stehen in daten/protokoll.txt", "läuft auf" in ptext and soll in ptext, ptext[-500:])
    if shell_da:
        ok("Das Symbol neben der Uhr wurde angelegt (keine Meldung „Taskleistensymbol nicht verfügbar“)", "Taskleistensymbol nicht verfügbar" not in ptext, ptext[-500:])
    else:
        hinweis("Symbol neben der Uhr: " + ("angelegt" if "Taskleistensymbol nicht verfügbar" not in ptext else "nicht verfügbar (keine Windows-Oberfläche in dieser Umgebung)"))
    o2 = cl()
    def rq2(m, pf, d=None):
        r = urllib.request.Request(U2 + pf, method=m, data=json.dumps(d).encode() if d is not None else None, headers={"Content-Type": "application/json"})
        try:
            x_ = o2.open(r, timeout=60); return x_.status, x_.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as f: return f.code, f.read().decode("utf-8", "replace")
    rq2("POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
    rq2("POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
    sb_, bb_ = rq2("POST", "/api/beenden", {})
    zu = False
    for i in range(60):
        try: urllib.request.urlopen(U2 + "/api/version", timeout=2).read(); time.sleep(0.5)
        except Exception: zu = True; break  # noqa: BLE001
    ok("„Beenden“ in der Oberfläche beendet das Programm samt Symbol", sb_ == 200 and zu, (sb_, bb_[:200], zu))
    aus, _, _ = ps("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*startbat*Jahresring*app.py*' } | Measure-Object | ForEach-Object { $_.Count }")
    ok("Danach läuft kein Prozess des Programms mehr", aus.strip() in ("0", ""), aus)
except Exception as f:  # noqa: BLE001
    import traceback
    ok("Programmstart über start.bat ohne Ausnahme", False, traceback.format_exc()[-800:])
finally:
    stoppen_hart()

print("== Python-Installationsprogramm aus start.bat")
bat = roh_bat.decode("ascii", "replace")
m = re.search(r"https://www\.python\.org/ftp/python/(\d+\.\d+\.\d+)/python-\1-amd64\.exe", bat)
ok("start.bat nennt eine feste Ausgabe von Python zum Nachladen", bool(m), bat[1500:2200])
if m:
    adr, ausgabe_nr = m.group(0), m.group(1)
    ziel = T + "/lauf/python-setup-pruefung.exe"
    try:
        with urllib.request.urlopen(urllib.request.Request(adr, headers={"User-Agent": "Jahresring-Pruefkette"}), timeout=180) as r_, open(ziel, "wb") as f_d:
            shutil.copyfileobj(r_, f_d)
        geladen = True
    except urllib.error.HTTPError as f:
        geladen = False; ok(f"Python {ausgabe_nr} liegt unter der Adresse aus start.bat", False, f"HTTP {f.code} für {adr}")
    except Exception as f:  # noqa: BLE001
        geladen = False; hinweis(f"python.org war nicht erreichbar ({f}); das Installationsprogramm wurde nicht geprüft.")
    if geladen:
        aus, err, rc_ = ps("$s=Get-AuthenticodeSignature $env:JR_F; Write-Output ($s.Status.ToString() + '|' + $s.SignerCertificate.Subject)", env=dict(os.environ, JR_F=ziel.replace("/", "\\")))
        ok(f"Python {ausgabe_nr}: Signatur gültig und von der Python Software Foundation (dieselbe Prüfung macht start.bat vor dem Installieren)", aus.startswith("Valid|") and "Python Software Foundation" in aus, (aus, err))
        h = hashlib.sha256(open(ziel, "rb").read()).hexdigest()
        hinweis(f"Python {ausgabe_nr} amd64: {os.path.getsize(ziel) // 1024} KB, SHA-256 {h}")
        os.remove(ziel)
    try:
        liste = urllib.request.urlopen(urllib.request.Request("https://www.python.org/ftp/python/", headers={"User-Agent": "Jahresring-Pruefkette"}), timeout=60).read().decode("utf-8", "replace")
        reihe = ".".join(ausgabe_nr.split(".")[:2]); neuere = sorted({int(n) for n in re.findall(r'href="' + re.escape(reihe) + r'\.(\d+)/"', liste) if int(n) > int(ausgabe_nr.split(".")[2])}, reverse=True)
        fertig = None
        for n in neuere:
            try:
                urllib.request.urlopen(urllib.request.Request(f"https://www.python.org/ftp/python/{reihe}.{n}/python-{reihe}.{n}-amd64.exe", method="HEAD", headers={"User-Agent": "Jahresring-Pruefkette"}), timeout=60); fertig = n; break
            except Exception: pass  # noqa: BLE001
        hinweis(f"Python {reihe}: " + (f"neuere Ausgabe {reihe}.{fertig} verfügbar – beim nächsten Bau in start.bat eintragen" if fertig else f"{ausgabe_nr} ist die neueste Ausgabe mit Installationsprogramm"))
    except Exception as f:  # noqa: BLE001
        hinweis(f"Liste der Python-Ausgaben nicht abrufbar ({f})")
hinweis(f"PowerShell-Aufrufe der Prüfung: {len(PS_ZEITEN)}, Dauer in Sekunden {PS_ZEITEN}")
hinweis(f"{time.time() - _T0:6.1f} s  Ende")
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
