"""Version 149, Paket Sicherheit: Passwort vergessen, Rechte außerhalb der Schnittstelle, Zahlen, Größen, Fehlertexte, Anmeldung.
Erwartet eine frische Prüfinstanz (bash /tmp/claude-0/t/v25/neu.sh)."""
import json, sys, os, re, io, time, base64, socket, socketserver, threading, sqlite3, email, email.policy, subprocess
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
if len(sys.argv) > 1: U = sys.argv[1]
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:400]))
    if not bed: fehler.append(name)
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
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    return j
def anmelden(login, pw):
    c = cl(); s, b, _ = rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": pw}); return c, s
def letzte_mail():
    time.sleep(0.4); return email.message_from_bytes(POST[-1], policy=email.policy.default) if POST else None
A("PUT", "einstellungen", {"firma": "Muster", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890", "sepa_iban": "DE02120300000000202051",
                           "mail": {"adresse": "betrieb@beispiel.de", "smtp_server": "127.0.0.1", "smtp_port": srv.server_address[1], "smtp_modus": "keine", "passwort": "x", "gesendet_ablegen": False}})
PW = "Pruefung#2026"
mid = lambda d: d.get("id") or d.get("mitarbeiter", {}).get("id")
m1 = mid(A("POST", "mitarbeiter", {"vorname": "Max", "nachname": "Werk", "email": "max@beispiel.de"})); m2 = mid(A("POST", "mitarbeiter", {"vorname": "Eva", "nachname": "Zwei", "email": "eva@beispiel.de"}))
m3 = mid(A("POST", "mitarbeiter", {"vorname": "Jonas", "nachname": "Chef", "email": "chef-privat@beispiel.de"}))
for lg, rolle, extra in (("werk", "werkstatt", {"mitarbeiter_id": m1}), ("mita", "mitarbeiter", {"mitarbeiter_id": m2}), ("buero", "buero", {"email": "buero@beispiel.de"}),
                         ("lohn", "eigen", {"eigen": {"bereiche": {"personal": 2}}}), ("ohnepreis", "eigen", {"eigen": {"bereiche": {"auftraege": 1, "material": 1}, "preise": False}})):
    r = A("POST", "benutzer", {"name": lg, "login": lg, "passwort": PW, "rolle": rolle, **extra}); ok(f"Benutzer {lg} angelegt", r["_s"] == 200, r.get("fehler"))
ok("PIN mit fünf Zeichen für die Rolle Mitarbeiter abgelehnt", A("POST", "benutzer", {"name": "k", "login": "kurz", "passwort": "12345", "rolle": "mitarbeiter"})["_s"] == 400)
ok("PIN mit sechs Zeichen angenommen", A("POST", "benutzer", {"name": "k", "login": "sechs", "passwort": "123456", "rolle": "mitarbeiter"})["_s"] == 200)
bl = A("GET", "benutzer")["liste"]; jo = [u for u in bl if u["login"] == "jonas"][0]
sitz = {lg: anmelden(lg, PW)[0] for lg in ("werk", "mita", "buero", "lohn", "ohnepreis")}

print("== S1 Passwort vergessen")
A("PUT", f"benutzer/{jo['id']}", {"mitarbeiter_id": m3})
r = A("PUT", f"mitarbeiter/{m3}", {"email": "angreifer@boese.example"}, c=sitz["lohn"]); ok("Vorbereitung: Benutzer mit Personalrecht ändert die Mailadresse im Mitarbeiterstamm", r["_s"] == 200, r.get("fehler"))
n0 = len(POST); s, t, _ = rq(cl(), "POST", "/api/anmeldung/vergessen", {"login": "jonas"}); m = letzte_mail()
ok("Code für den Inhaber geht an die Betriebsadresse, nicht an die Adresse aus dem Mitarbeiterstamm", len(POST) == n0 + 1 and "betrieb@beispiel.de" in str(m["To"]) and "boese" not in str(m["To"]), m and m["To"])
ok("der Code steht nicht im Betreff", m is not None and not re.search(r"\d{6}", str(m["Subject"])), m and m["Subject"])
code = re.search(r"Code: (\d{6})", m.get_body(preferencelist=("plain",)).get_content() if m else ""); ok("der Code steht im Text der Mail", bool(code))
n0 = len(POST); time.sleep(0.2); s, t, _ = rq(cl(), "POST", "/api/anmeldung/vergessen", {"login": "werk"}); time.sleep(0.5)
ok("Benutzer ohne eigene Adresse (nur Adresse im Mitarbeiterstamm): es wird keine Mail verschickt", s == 200 and len(POST) == n0, (s, t[:80], len(POST) - n0))
n0 = len(POST); s, t, _ = rq(cl(), "POST", "/api/anmeldung/vergessen", {"login": "buero"}); m = letzte_mail()
ok("Benutzer mit eigener Adresse bekommt den Code dorthin", len(POST) == n0 + 1 and "buero@beispiel.de" in str(m["To"]), m and m["To"])
# eigene Adresse nur mit Passwort ändern
s, t, _ = rq(sitz["buero"], "POST", "/api/anmeldung/email", {"email": "neu@beispiel.de"}); ok("eigene Mailadresse ohne Passwort ändern: abgelehnt", s == 400, (s, t[:80]))
s, t, _ = rq(sitz["buero"], "POST", "/api/anmeldung/email", {"email": "neu@beispiel.de", "passwort": PW}); ok("eigene Mailadresse mit Passwort ändern: angenommen", s == 200, (s, t[:80]))

print("== S2/S3 Rechte außerhalb der Schnittstelle")
k = A("POST", "kunden", {"kurzname": "Recht, Rita", "nachname": "Recht", "plz": "88069", "ort": "Tettnang"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Garderobe"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Garderobe"}); pid = po.get("id") or po["position"]["id"]; A("PUT", f"positionen/{pid}", {"einzelpreis": 1234.56, "preis_manuell": 1, "menge": 1})
b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); f = A("POST", f"belege/{b['id']}/festschreiben", {}); bid = b["id"]
erg = {lg: rq(c, "GET", f"/api/belege/{bid}/zugferd.xml")[0] for lg, c in sitz.items()}
# seit Version 152 auch für Benutzer ohne Preisrecht gesperrt (die E-Rechnung enthält alle Beträge)
ok("E-Rechnungs-XML: Werkstatt, Mitarbeiter, Lohnbüro und Benutzer ohne Preisrecht 403; Büro 200", erg == {"werk": 403, "mita": 403, "buero": 200, "lohn": 403, "ohnepreis": 403}, erg)
wz = A("POST", "werkzeuge", {"bezeichnung": "Tauchsäge", "preis": 612.5})
geld = lambda t: re.findall(r"\d[\d.]*,\d\d\s*(?:€|&euro;)", t)
for lg in ("werk", "ohnepreis"):
    c = sitz[lg]
    for art in ("kosten", "sollist", "lohnmaterial"):
        s, t, _ = rq(c, "GET", f"/papier/{a['id']}/{art}"); ok(f"{lg}: Papier {art} gesperrt", s == 403, s)
    s, t, _ = rq(c, "GET", f"/papier/{a['id']}/werkstattauftrag?preise=1"); ok(f"{lg}: Werkstattauftrag ohne Beträge, auch mit preise=1 in der Adresse", s == 200 and not geld(t), (s, geld(t)[:3]))
    s, t, _ = rq(c, "GET", "/liste/werkzeuge"); ok(f"{lg}: Werkzeugliste ohne Preise", s == 200 and not geld(t) and "Preis netto" not in t and "Anschaffungswert" not in t and "Tauchsäge" in t, (s, geld(t)[:3]))
    s, t, _ = rq(c, "GET", "/liste/lager"); ok(f"{lg}: Lagerliste ohne Preise und Werte", s == 200 and not geld(t) and "Lagerwert" not in t and "Preis je Einheit" not in t, (s, geld(t)[:3]))
    r = A("POST", f"auftraege/{a['id']}/papier", {"art": "kosten"}, c=c); ok(f"{lg}: Papier Kosten als PDF erzeugen abgelehnt", r["_s"] == 403, (r["_s"], r.get("fehler")))
    s, t, _ = rq(c, "GET", "/papier/projekt/1"); ok(f"{lg}: Projekt-Nachkalkulation gesperrt", s == 403, s)
s, t, _ = rq(sitz["werk"], "GET", f"/papier/{a['id']}/stunden"); ok("werk: Auswertung Stunden gesperrt (nur Werkstattpapiere)", s == 403, s)
s, t, _ = rq(sitz["ohnepreis"], "GET", f"/papier/{a['id']}/stunden"); ok("ohnepreis (alle Reiter, ohne Preise): Auswertung Stunden erlaubt", s == 200, s)
s, t, _ = rq(inh, "GET", f"/papier/{a['id']}/kosten"); ok("Inhaber: Papier Kosten mit Beträgen", s == 200 and "1.234,56" in t, s)
s, t, _ = rq(inh, "GET", "/liste/werkzeuge"); ok("Inhaber: Werkzeugliste mit Preisen", s == 200 and "612,50" in t and "Preis netto" in t, s)
s, t, _ = rq(sitz["buero"], "GET", f"/papier/{a['id']}/kosten"); ok("Büro: Papier Kosten erlaubt", s == 200 and "1.234,56" in t, s)
try:
    sys.path.insert(0, "/home/claude/eberle-buero/lib"); from pypdf import PdfReader
    s, t, _ = rq(sitz["werk"], "GET", "/liste/werkzeuge.pdf", roh=True); txt = " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(t)).pages) if s == 200 else ""
    ok("werk: Werkzeugliste als PDF ohne Preise (interne Erzeugung kennt die Einschränkung)", s == 200 and "Tauchsäge" in txt and "612" not in txt and "€" not in txt, (s, txt[:120]))
    s, t, _ = rq(inh, "GET", "/liste/werkzeuge.pdf", roh=True); txt = " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(t)).pages) if s == 200 else ""
    ok("Inhaber: Werkzeugliste als PDF mit Preisen", s == 200 and "612,50" in txt, (s, txt[:120]))
except ImportError: ok("pypdf vorhanden", False)
# alle Adressen außerhalb der Schnittstelle: ein Benutzer ganz ohne Rechte bekommt nichts (außer den bewusst freien)
roh_pfade = {f"/druck/{bid}.pdf": 403, "/api/vorlage/brief-1.svg": "frei", f"/api/belege/{bid}/xrechnung.xml": 403, f"/api/belege/{bid}/zugferd.xml": 403, "/druck/brief/1": 403, "/api/korrespondenz/1/eml": 403,
             f"/papier/bautagebuch/{a['id']}": 403, "/api/bautagebuch/foto/x.jpg": 403, "/papier/projekt/1/zeitbericht": 403, "/papier/projekt/1": 403, "/papier/montage/1": 403, f"/papier/{a['id']}/zuschnitt.csv": 403,
             f"/papier/{a['id']}/werkstattauftrag": 403, "/zuschnitt": 403, "/zuschnitt/": 403, "/liste/etiketten": 403, f"/druck/monatsbeleg/{m1}/2026-11": 403, "/druck/arbeitsschutz/gefahrstoffverzeichnis": 403,
             "/druck/mahnung/1": 403, "/api/mahnungen/1/pdf": 403, f"/druck/{bid}": 403, "/api/service/export/x.zip": 403, "/api/service/protokoll.csv": 403, "/api/kalender/export.ics": 403,
             "/api/bild/0123456789abcdef.jpg": 403, "/liste/lager": 403, "/api/eingang/datei/" + "0" * 32: 403, "/api/zahlungen/1/datei": 403, "/api/service/datei/x.zip": 403, "/api/unterschrift": 403, "/api/logo": "frei", f"/druck/{bid}/versandt/1.pdf": 403}
quelle = open("/home/claude/eberle-buero/app.py", encoding="utf-8").read(); teil = quelle[quelle.index("    def _verarbeiten(self, methode):"):quelle.index("            teile = [t for t in u.path[5:].split(\"/\") if t]")]
muster = re.findall(r'(?:re\.fullmatch\(r"|u\.path\.startswith\("|u\.path == "|u\.path in \()([^"]*"?[^)\n]{0,60})', teil)
anzahl = len(re.findall(r'^            (?:m = re\.fullmatch\(r"/|if re\.fullmatch\(r"/|if u\.path\.startswith\("/|if u\.path == "/|if u\.path in \("/)', teil, re.M))
ok(f"Prüfliste deckt alle {anzahl} Adressen außerhalb der Schnittstelle ab (kommt eine dazu, muss sie hier und in roh_recht ergänzt werden)", anzahl == 31, anzahl)
nix, _ = anmelden("sechs", "123456")
erg = {p: rq(nix, "GET", p)[0] for p in roh_pfade}
falsch = {p: s for p, s in erg.items() if (roh_pfade[p] == 403 and s != 403) or (roh_pfade[p] == "frei" and s == 403)}
ok("Benutzer ohne jedes Recht: alle Adressen außerhalb der Schnittstelle gesperrt (frei nur Briefbogen und Logo)", not falsch, falsch)

print("== S4 Zahlen")
for name, roh in (("1e999", '{"einzelpreis": 1e999, "preis_manuell": 1}'), ("Infinity", '{"einzelpreis": Infinity}'), ("NaN", '{"menge": NaN}'), ("-1e999", '{"einzelpreis": -1e999}')):
    r = urllib.request.Request(U + f"/api/positionen/{pid}", method="PUT", data=roh.encode(), headers={"Content-Type": "application/json"})
    try: x = inh.open(r); s = x.status
    except urllib.error.HTTPError as e: s = e.code
    ok(f"Zahl {name} wird abgelehnt", s == 400, s)
def streng(t):
    try: json.loads(t, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c))); return True
    except ValueError: return False
con = sqlite3.connect(D + "/buero.db", timeout=20); con.execute("UPDATE positionen SET einzelpreis=? WHERE id=?", (float("inf"), pid)); con.commit(); con.close()
aus = {p: streng(rq(inh, "GET", p)[1]) for p in (f"/api/auftraege/{a['id']}/positionen", "/api/start", "/api/auftraege")}
ok("steht doch eine unendliche Zahl in der Datenbank (Altbestand), bleiben die Antworten lesbar", all(aus.values()), aus)
A("PUT", f"positionen/{pid}", {"einzelpreis": 1234.56, "preis_manuell": 1, "menge": 1})

print("== S7/S8 Größen und Fehlertexte")
gross = b'{"x": "' + b"A" * (9 * 1024 * 1024) + b'"}'
def roh_post(c, pfad, daten):
    r = urllib.request.Request(U + pfad, method="POST", data=daten, headers={"Content-Type": "application/json"})
    try: x = c.open(r, timeout=60); return x.status, x.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()
    except Exception as e: return 0, type(e).__name__
s, t = roh_post(sitz["mita"], "/api/stempel", gross); ok("Rolle Mitarbeiter: 9 MB werden abgewiesen (Grenze 8 MB)", s in (413, 0), (s, t[:80]))
s, t = roh_post(sitz["buero"], "/api/kunden", gross); ok("Büro: 9 MB werden gelesen (Grenze 300 MB)", s in (200, 400), (s, t[:80]))
r = A("POST", "kunden", {"kurzname": "x" * 301}); ok("Kurzname mit 301 Zeichen: verständliche Absage", r["_s"] == 400 and "Kurzname" in r.get("fehler", "") and "300" in r.get("fehler", ""), r.get("fehler"))
r = A("POST", "kunden", {"kurzname": "Lang, Lena", "bemerkungen": "y" * 5000}); ok("lange Bemerkung bleibt möglich", r["_s"] == 200, r.get("fehler"))
r = A("POST", "anhaenge", {"kunde_id": k["id"], "dateiname": "a" * 300 + ".txt", "daten": base64.b64encode(b"x").decode()})
ok("überlanger Dateiname wird gekürzt statt mit Fehler zu enden, die Endung bleibt", r["_s"] == 200 and len(r.get("dateiname", "")) <= 160 and r.get("dateiname", "").endswith(".txt"), (r["_s"], r.get("fehler"), len(r.get("dateiname", ""))))
r = urllib.request.Request(U + "/api/kunden", method="POST", data=b'{"kurzname": "Zeichen \\ud83d"}', headers={"Content-Type": "application/json"})
try: x = inh.open(r); s, t = x.status, x.read().decode()
except urllib.error.HTTPError as e: s, t = e.code, e.read().decode()
except Exception as e: s, t = 0, type(e).__name__
ok("ungültiges Unicode-Zeichen: Absage statt internem Fehler oder abgebrochener Verbindung", s == 400 and "ungültige Zeichen" in t, (s, t[:100]))
r = A("POST", f"belege/{bid}/mail", {"an": "kunde@beispiel.de", "betreff": "Rechnung\r\nBcc: heimlich@boese.example", "text": "Hallo", "anhaenge": ["beleg"]}); m = letzte_mail()
ok("Zeilenumbruch im Betreff: Mail geht ohne Fehler und ohne eingeschleuste Kopfzeile hinaus", r["_s"] == 200 and m is not None and m["Bcc"] is None and "Bcc: heimlich" in str(m["Subject"]).replace("\n", " "), (r["_s"], r.get("fehler"), m and m["Subject"]))

print("== S9 Härtungen")
s, t, _ = rq(inh, "POST", "/api/kunden", {"kurzname": "CSRF1"}, {"Origin": "null", "Sec-Fetch-Site": "cross-site"}); ok("Herkunft null von fremder Seite: abgelehnt", s == 403, s)
s, t, _ = rq(inh, "POST", "/api/kunden", {"kurzname": "CSRF2"}, {"Sec-Fetch-Site": "cross-site"}); ok("Kennzeichen cross-site ohne Herkunft: abgelehnt", s == 403, s)
s, t, _ = rq(inh, "POST", "/api/kunden", {"kurzname": "CSRF3"}, {"Origin": "null", "Sec-Fetch-Site": "same-origin"}); ok("Herkunft null aus der eigenen Seite: angenommen", s == 200, s)
s, t, _ = rq(inh, "POST", "/api/kunden", {"kurzname": "CSRF4"}, {"Origin": "https://boese.example"}); ok("fremde Herkunft: abgelehnt", s == 403, s)
s, t, _ = rq(inh, "POST", "/api/kunden", {"kurzname": "CSRF5"}, {"Origin": U, "Sec-Fetch-Site": "same-origin"}); ok("eigene Herkunft: angenommen", s == 200, s)
A("PUT", "einstellungen", {"google_kalender": [{"name": "T", "url": "file:///etc/hostname", "farbe": "#888", "aktiv": True}]})
kal = A("GET", "kalender?von=2026-11-01&bis=2026-11-30&neu=1"); txt = json.dumps(kal.get("extern_fehler") or kal, ensure_ascii=False)
ok("Kalenderadresse mit Dateipfad wird nicht gelesen", "https://" in txt and "muss mit" in txt, txt[:200])
A("PUT", "einstellungen", {"google_kalender": []})
con = sqlite3.connect(D + "/buero.db", timeout=20)
import hashlib
salz = "00" * 16; alt_hash = "pbkdf2$" + salz + "$" + hashlib.pbkdf2_hmac("sha256", PW.encode(), bytes.fromhex(salz), 200_000).hex()
con.execute("UPDATE benutzer SET pw_hash=? WHERE login='lohn'", (alt_hash,)); con.commit()
c9, s9 = anmelden("lohn", PW); neu_hash = con.execute("SELECT pw_hash FROM benutzer WHERE login='lohn'").fetchone()[0]
ok("Passwort im früheren Format (200.000 Runden) gilt weiter und wird bei der Anmeldung auf 600.000 Runden erneuert", s9 == 200 and neu_hash.startswith("pbkdf2$600000$"), (s9, neu_hash[:24]))
c9, s9 = anmelden("lohn", PW); ok("danach erneut anmelden", s9 == 200, s9)
ok("neue Passwörter werden mit 600.000 Runden abgelegt", con.execute("SELECT pw_hash FROM benutzer WHERE login='buero'").fetchone()[0].startswith("pbkdf2$600000$"))

print("== Anmeldedauer einstellbar")
from datetime import datetime, timedelta
A("PUT", "einstellungen", {"sitzung_tage_buero": 2, "sitzung_tage_mitarbeiter": 9})
def ablauf_tage(login, pw):
    anmelden(login, pw); time.sleep(0.2)
    x = sqlite3.connect(D + "/buero.db", timeout=20); r = x.execute("SELECT s.ablauf FROM sitzungen s JOIN benutzer b ON b.id=s.benutzer_id WHERE b.login=? ORDER BY s.angelegt DESC, s.rowid DESC LIMIT 1", (login,)).fetchone(); x.close()
    return round((datetime.fromisoformat(r[0]) - datetime.now()).total_seconds() / 86400, 1)
tb, tm = ablauf_tage("buero", PW), ablauf_tage("sechs", "123456")
ok("Anmeldung im Büro gilt die eingestellten 2 Tage, die der Rolle Mitarbeiter 9 Tage", tb == 2.0 and tm == 9.0, (tb, tm))
A("PUT", "einstellungen", {"sitzung_tage_buero": 0, "sitzung_tage_mitarbeiter": 5000}); tb, tm = ablauf_tage("buero", PW), ablauf_tage("sechs", "123456")
ok("unsinnige Werte (0 und 5000 Tage) fallen auf die Vorgabe zurück (30 und 120 Tage)", tb == 30.0 and tm == 120.0, (tb, tm))
A("PUT", "einstellungen", {"sitzung_tage_buero": 30, "sitzung_tage_mitarbeiter": 120})

print("== M3 Anmeldungen im Protokoll")
for i in range(6): rq(cl(), "POST", "/api/anmeldung/anmelden", {"login": "werk", "passwort": f"falsch{i}"})
con.close(); con = sqlite3.connect(D + "/buero.db", timeout=20)
pr = [r for r in con.execute("SELECT art, text FROM protokoll WHERE art='anmeldung'")]
ok("gelungene Anmeldungen stehen im Protokoll", any("buero angemeldet" in t for _, t in pr), pr[:3])
ok("Sperre nach fünf Fehlversuchen steht genau einmal im Protokoll", sum(1 for _, t in pr if "„werk“" in t and "gesperrt" in t) == 1, [t for _, t in pr if "werk" in t])
pb = [r[0] for r in con.execute("SELECT text FROM protokoll WHERE art='benutzer'")]
ok("Änderung der eigenen Mailadresse steht im Protokoll (Adresse verkürzt)", any("E-Mail-Adresse" in t and "buero" in t and "neu@beispiel.de" not in t for t in pb), pb[:3])
con.close()

print("== S1 Umstellung bestehender Daten, S5 stumme Verbindungen (Neustart mit Netzfreigabe)")
A("PUT", "einstellungen", {"netzwerk": True})
con = sqlite3.connect(D + "/buero.db", timeout=20)
con.execute("DELETE FROM einstellungen WHERE schluessel='_reset_adresse_konto'"); con.execute("UPDATE benutzer SET email='' WHERE login IN ('werk', 'jonas')"); con.commit(); con.close()
def neustart():
    for f in os.listdir("/proc"):
        if f.isdigit():
            try:
                if b"BUERO_PORT=8799" in open(f"/proc/{f}/environ", "rb").read(): os.kill(int(f), 15)
            except OSError: pass
    time.sleep(1.5)
    subprocess.Popen("cd /tmp/claude-0/t/v25/eberle-buero && BUERO_PORT=8799 BUERO_BROWSER=/tmp/claude-0/t/fake/chrome nohup ${BUERO_PY:-python3} app.py kein-browser >> /tmp/claude-0/t/v25/log.txt 2>&1 &", shell=True)
    for i in range(40):
        time.sleep(0.5)
        try: urllib.request.urlopen(U + "/api/version", timeout=2).read(); return True
        except Exception: pass
    return False
ok("Neustart", neustart())
con = sqlite3.connect(D + "/buero.db", timeout=20)
adr = dict(con.execute("SELECT login, email FROM benutzer").fetchall()); con.close()
ok("Umstellung: Benutzer ohne eigene Adresse übernimmt einmalig die Adresse aus dem Mitarbeiterstamm", adr.get("werk") == "max@beispiel.de", adr)
ok("Umstellung: der Inhaber übernimmt keine Adresse aus dem Mitarbeiterstamm (für ihn gilt die Betriebsadresse)", adr.get("jonas") == "", adr)
ip = subprocess.run("hostname -I", shell=True, capture_output=True, text=True).stdout.split()
ip = [x for x in ip if not x.startswith("127.")][:1]
if not ip: print("     (kein Netzanschluss in dieser Umgebung – Verbindungsgrenze nicht prüfbar)")
else:
    ip = ip[0]; offen = []; t0 = time.time()
    for i in range(160):
        try: v = socket.create_connection((ip, 8799), timeout=5); offen.append(v)
        except OSError: pass
        time.sleep(0.004)   # nicht alle im selben Augenblick: sonst hält das Betriebssystem einen Teil selbst zurück
    time.sleep(1.0)
    def zu(v):
        v.settimeout(0.05)
        try: return v.recv(1) == b""
        except socket.timeout: return False
        except OSError: return True
    getrennt = sum(1 for v in offen if zu(v))
    ok("160 stumme Verbindungen aus dem Netz: 120 bleiben offen, die übrigen werden sofort getrennt", len(offen) == 160 and getrennt == 40, (len(offen), getrennt))
    t1 = time.time()
    try: s = urllib.request.urlopen(U + "/api/version", timeout=5).status
    except Exception as e: s = type(e).__name__
    ok("am PC selbst bleibt das Programm dabei sofort erreichbar", s == 200 and time.time() - t1 < 2, (s, round(time.time() - t1, 2)))
    try:
        v = socket.create_connection((ip, 8799), timeout=5); v.sendall(b"GET /api/version HTTP/1.0\r\nHost: %s:8799\r\n\r\n" % ip.encode()); v.settimeout(3); antwort = v.recv(200)
    except OSError as e: antwort = b""
    ok("aus dem Netz ist die Grenze in dieser Zeit erreicht (weitere Verbindung wird getrennt)", antwort == b"", antwort[:40])
    time.sleep(max(0, 33 - (time.time() - t0)))
    getrennt = sum(1 for v in offen if zu(v))
    ok("nach 30 Sekunden ohne Anfrage sind alle stummen Verbindungen getrennt", getrennt == 160, getrennt)
    try:
        v = socket.create_connection((ip, 8799), timeout=5); v.sendall(b"GET /api/version HTTP/1.0\r\nHost: %s:8799\r\n\r\n" % ip.encode()); v.settimeout(3); antwort = v.recv(200)
    except OSError as e: antwort = b""
    ok("danach ist das Programm aus dem Netz wieder erreichbar", antwort.startswith(b"HTTP/1.0 200"), antwort[:40])
    for v in offen: v.close()
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
