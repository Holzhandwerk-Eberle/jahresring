"""Dateiname der Belege: nur die Belegnummer – im Mail-Anhang, im Archiv und im Projektordner. Vorhandene Dateien unter dem
früheren Namen (Nummer_Belegart_Kunde) werden weiterverwendet: festgeschriebene unverändert, änderbare umbenannt."""
import json, sys, os, glob, hashlib, socketserver, threading, email
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
if len(sys.argv) > 1: U = sys.argv[1]
DATEN = sys.argv[2] if len(sys.argv) > 2 else "/tmp/claude-0/t/v25/eberle-buero/daten"
PROJ = "/tmp/claude-0/t/v25/projekte"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:500]))
    if not bed: fehler.append(name)
# --- kleiner Postausgang zum Mitlesen der gesendeten Nachricht
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
def A(m, p, d=None):
    s, b, _ = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    return j
os.makedirs(PROJ, exist_ok=True)
A("PUT", "einstellungen", {"firma": "Muster", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890", "sepa_iban": "DE02120300000000202051", "projektpfad": PROJ,
                           "mail": {"adresse": "ich@beispiel.de", "smtp_server": "127.0.0.1", "smtp_port": srv.server_address[1], "smtp_modus": "keine", "passwort": "x", "gesendet_ablegen": False}})
k = A("POST", "kunden", {"kurzname": "Rittler, Nina und David", "nachname": "Rittler", "strasse": "Weg 2", "plz": "88099", "ort": "Neukirch", "email1": "kunde@beispiel.de"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Garderobe"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Garderobe"}); pid = po.get("id") or po["position"]["id"]
A("PUT", f"positionen/{pid}", {"einzelpreis": 1000, "preis_manuell": 1, "menge": 1})
archiv = lambda: sorted(os.path.basename(f) for f in glob.glob(os.path.join(DATEN, "belege", "*", "*")))
projekt = lambda: sorted(os.path.basename(f) for f in glob.glob(os.path.join(PROJ, "**", "*.*"), recursive=True) if f.lower().endswith((".pdf", ".xml")))
def anhaenge(roh):
    return [t.get_filename() for t in email.message_from_bytes(roh).walk() if t.get_filename()]
# --- Angebot
ang = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"}); nr = A("GET", f"belege/{ang['id']}")["nummer"]
v = A("GET", f"belege/{ang['id']}/mail"); ok("Mail-Vorschlag: Anhang heißt nur nach der Angebotsnummer", [x["name"] for x in v["anhaenge"]] == [nr + ".pdf"], v.get("anhaenge"))
# Arbeitskopie unter dem früheren Namen liegt schon im Archiv und im Projektordner
alt = f"{nr}_Angebot_Rittler, Nina und David.pdf"
r = A("POST", f"belege/{ang['id']}/pdf", {}); ok("PDF erzeugt", r["_s"] == 200 and archiv() == [nr + ".pdf"], (r, archiv()))
pordner = os.path.dirname([f for f in glob.glob(os.path.join(PROJ, "**", nr + ".pdf"), recursive=True)][0])
ok("Projektordner: Datei heißt nur nach der Nummer", projekt() == [nr + ".pdf"], projekt())
jahr = os.path.dirname(glob.glob(os.path.join(DATEN, "belege", "*", nr + ".pdf"))[0])
os.rename(os.path.join(jahr, nr + ".pdf"), os.path.join(jahr, alt)); os.rename(os.path.join(pordner, nr + ".pdf"), os.path.join(pordner, alt))
A("POST", f"belege/{ang['id']}/pdf", {})
ok("frühere Namen eines änderbaren Belegs werden umbenannt, keine zweite Datei", archiv() == [nr + ".pdf"] and projekt() == [nr + ".pdf"], (archiv(), projekt()))
s = A("POST", f"belege/{ang['id']}/mail", {"an": "kunde@beispiel.de", "betreff": "Angebot", "text": "Hallo", "anhaenge": ["beleg"]})
ok("Angebot gesendet: Anhang heißt nur nach der Nummer", s["_s"] == 200 and POST and anhaenge(POST[-1]) == [nr + ".pdf"], (s, POST and anhaenge(POST[-1])))
# --- Rechnung: festgeschrieben, Archiv-PDF unter dem früheren Namen bleibt unverändert
re_ = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); A("POST", f"belege/{re_['id']}/festschreiben", {})
rn = A("GET", f"belege/{re_['id']}")["nummer"]; A("POST", f"belege/{re_['id']}/pdf", {})
ok("neue Rechnung: Archiv-PDF heißt nur nach der Rechnungsnummer", rn + ".pdf" in archiv(), archiv())
pr = A("GET", "service/protokoll?voll=1"); ok("Belegprüfung findet das Archiv-PDF unter dem neuen Namen (ohne Abweichung)", not (pr.get("belege") or {}).get("fehler") and (pr.get("belege") or {}).get("ok", True) is not False, pr.get("belege"))
ralt = f"{rn}_Rechnung_Rittler, Nina und David.pdf"; rp = os.path.join(jahr, rn + ".pdf")
os.rename(rp, os.path.join(jahr, ralt)); h1 = hashlib.sha256(open(os.path.join(jahr, ralt), "rb").read()).hexdigest()
n_prot = len([x for x in A("GET", "service/protokoll").get("eintraege", []) if x["art"] == "archiv_pdf"])
A("POST", f"belege/{re_['id']}/pdf", {})
h2 = hashlib.sha256(open(os.path.join(jahr, ralt), "rb").read()).hexdigest()
n_prot2 = len([x for x in A("GET", "service/protokoll").get("eintraege", []) if x["art"] == "archiv_pdf"])
ok("festgeschriebene Rechnung mit früherem Namen: Datei unverändert, kein zweites Archiv-PDF, kein neuer Protokolleintrag",
   h1 == h2 and rn + ".pdf" not in archiv() and ralt in archiv() and n_prot == n_prot2, (archiv(), n_prot, n_prot2))
s = A("POST", f"belege/{re_['id']}/mail", {"an": "kunde@beispiel.de", "betreff": "Rechnung", "text": "Hallo", "anhaenge": ["beleg"]})
ok("… der Kunde bekommt sie trotzdem als <Nummer>.pdf", s["_s"] == 200 and anhaenge(POST[-1]) == [rn + ".pdf"], (s, anhaenge(POST[-1])))
ok("Projektordner: Rechnung nur nach der Nummer", rn + ".pdf" in projekt() and ralt not in projekt(), projekt())
# --- Entwurf ohne Nummer
e2 = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); v = A("GET", f"belege/{e2['id']}/mail")
ok("Rechnungsentwurf ohne Nummer: Vorschlag „Rechnung.pdf“", [x["name"] for x in v["anhaenge"]][:1] == ["Rechnung.pdf"], v.get("anhaenge"))
print("FEHLER:", fehler); sys.exit(1 if fehler else 0)
