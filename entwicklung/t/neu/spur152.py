"""Version 152, Spurprüfung: Ein breiter Bestand mit auffälligen Werten (Preise 7131,31 · 9292,92 · 8181,81 · 4646,46, Löhne 37,73 und
41,17, Personenangaben mit Kennwörtern) wird angelegt. Dann rufen Benutzer mit eingeschränkten Rechten alle bekannten lesenden Adressen
ab (rund 470 je Rolle) – in keiner Antwort darf eine Spur stehen, die diese Rolle nicht sehen darf. Findet neue Felder, die an der
Rechteprüfung vorbeirutschen (wie in Version 151 der höchste Zugangspreis im Material). Erwartet eine frische Prüfinstanz."""
import json, re, sys, io, subprocess
from datetime import date, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
T = "/tmp/claude-0/t"
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:1200]))
    if not bed: fehler.append(name)
aus = subprocess.run([sys.executable, T + "/neu/spur_seed.py", T + "/lauf/spur_ids.json"], capture_output=True, text=True, timeout=600)
ok("Bestand mit Spuren angelegt", aus.returncode == 0 and "fertig" in aus.stdout and "!!" not in aus.stdout, (aus.stdout[-600:], aus.stderr[-400:]))
ids = json.load(open(T + "/lauf/spur_ids.json"))
PW = "Pruefung#2026"
def anmelden(login, pw):
    c = cl(); s, b, _ = rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": pw}); assert s == 200, (login, s, b[:100]); return c
ROLLEN = ["buero", "werk", "mita", "mita1", "epers", "emat", "eauf", "ekal", "eop", "eas", "elief", "ekun", "estart"]
sitz = {r: anmelden(r, "246813" if r.startswith("mita") else PW) for r in ROLLEN}
sitz["anonym"] = cl()
heute = date.today(); mo = heute - timedelta(days=heute.weekday())
ersatz = {"{monat}": heute.strftime("%Y-%m"), "{mo}": mo.isoformat(), "{so}": (mo + timedelta(days=6)).isoformat(), "{w8}": (mo + timedelta(days=55)).isoformat(), "{j}": str(heute.year),
          "{von}": heute.replace(day=1).isoformat(), "{bis}": (heute + timedelta(days=45)).isoformat()}
adressen = []
for k in json.load(open(T + "/neu/spur_adressen.json")):
    for a, b in ersatz.items(): k = k.replace(a, b)
    adressen.append(k)
PREIS = ["7131.31", "7131,31", "9292.92", "9292,92", "8181.81", "8181,81", "4646.46", "4646,46", "9.292,92", "7.131,31", "8.181,81", "4.646,46", "11538.57", "11.538,57"]
LOHN = ["37.73", "37,73", "41.17", "41,17"]
PERSON = ["XSTRASSE", "XTELEFON", "1990-05-05", "05.05.1990", "XKRANKNOTIZ", "XURLAUBNOTIZ", "XZEIT"]
GESUND = ["XVORSORGE", "XARZT", "XEXPO", "XVERBAND"]
KUNDE = ["QXNACHQX", "QXTELQX", "QXBEMQX", "QXBANKNAMEQX", "QXNOTIZKQX", "QXBRIEFTEXTQX", "QXKORRTEXTQX", "QXWVQX"]
LIEFERANT = ["LXNOTIZLX", "LXBRIEFLX", "LXKORRLX"]   # Notiz, Brief und Anruf zu einem Lieferanten
ARTEN = {"preis": PREIS, "lohn": LOHN, "person": PERSON, "gesund": GESUND, "kunde": KUNDE, "lieferant": LIEFERANT}
# Was eine Rolle nicht sehen darf (der Kundenname steht für die Werkstatt in der Auftragsliste und zählt deshalb nicht dazu)
VERBOTEN = {"anonym": ["preis", "lohn", "person", "gesund", "kunde", "lieferant"], "werk": ["preis", "lohn", "gesund", "lieferant"], "mita": ["preis", "lohn", "kunde", "gesund", "lieferant"],
            "mita1": ["preis", "kunde", "lieferant"], "epers": ["kunde", "lieferant"], "emat": ["preis", "lohn", "person", "gesund", "kunde", "lieferant"],
            "eauf": ["preis", "lohn", "person", "gesund", "lieferant"], "ekal": ["preis", "lohn", "gesund", "lieferant"], "eop": ["lohn", "person", "gesund", "lieferant"],
            "eas": ["preis", "lohn", "kunde", "lieferant"], "elief": ["lohn", "person", "gesund", "kunde"], "ekun": ["lohn", "person", "gesund", "lieferant"],
            "estart": ["lohn", "person", "gesund", "lieferant"], "buero": ["lohn", "person"]}
sys.path.insert(0, "/home/claude/eberle-buero/lib")
def text_von(body):
    if body[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(body)).pages)
        except Exception: return ""
    return body.decode("utf-8", "replace")
funde, antworten, serverfehler = [], {r: 0 for r in sitz}, []
for pfad in adressen:
    for rolle, c in sitz.items():
        try: s, body, hd = rq(c, "GET", pfad, roh=True)
        except Exception as f: s, body = 0, b""
        if isinstance(body, str): body = body.encode("utf-8")
        if s >= 500: serverfehler.append((rolle, pfad, s))
        if s != 200: continue
        antworten[rolle] += 1
        if (hd.get("Content-Type") or "").startswith(("image/", "font/")) or pfad.startswith(("/api/vorlage/", "/api/logo", "/api/bild")): continue   # Grafiken: Zahlen darin sind Koordinaten
        t = text_von(body)
        for art in VERBOTEN[rolle]:
            sp = [w for w in ARTEN[art] if w in t]
            if sp: funde.append((rolle, pfad, art, sp[:3]))
print("Adressen:", len(adressen), "· Antworten mit Inhalt je Rolle:", antworten)
ok(f"{len(adressen)} lesende Adressen mit {len(sitz)} Rollen abgerufen, kein Fehler des Programms (HTTP 5xx)", len(adressen) > 400 and not serverfehler, serverfehler[:8])
ok("jede Rolle kommt an ihre Seiten (Inhaber-Probe entfällt, Büro über 150 Antworten, Mitarbeiter unter 60)", antworten["buero"] > 150 and antworten["mita"] < 60 and antworten["anonym"] < 30, antworten)
ok("keine Spur von Preisen, Löhnen, Personen- oder Gesundheitsangaben bei einer Rolle, die sie nicht sehen darf", not funde, funde[:12])
# Gegenprobe: Die Spuren sind überhaupt auffindbar (der Inhaber sieht sie), sonst wäre die Prüfung blind
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
gesehen = {art: False for art in ARTEN}
for pfad in ("/api/material", "/api/material/1", f"/druck/{ids['bel']['rechnung']}", "/api/mitarbeiter", f"/api/mitarbeiter/{ids['m1']}", "/api/arbeitsschutz/vorsorge", f"/api/kunden/{ids['k1']}", "/api/zahlungen", "/api/werkzeuge", "/api/notizen", "/api/briefe"):
    s, body, _ = rq(inh, "GET", pfad, roh=True); t = text_von(body if isinstance(body, bytes) else body.encode())
    for art, liste in ARTEN.items():
        if any(w in t for w in liste): gesehen[art] = True
ok("Gegenprobe: Der Inhaber sieht alle sechs Arten von Spuren", all(gesehen.values()), gesehen)
print("FEHLER:", fehler)
