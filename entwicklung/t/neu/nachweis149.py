"""Version 149, Nachvollziehbarkeit: versandte Fassungen von Belegen und gesendete Mails bleiben erhalten, versandte Belege
werden nicht gelöscht; Änderungen an Stammdaten, Einstellungen, Benutzern und Rechten stehen im Protokoll (ohne persönliche
Inhalte); festgeschriebene Rechnungen ohne Protokolleintrag fallen auf. Erwartet eine frische Prüfinstanz."""
import json, sys, os, re, io, time, base64, socketserver, threading, sqlite3, email, email.policy, hashlib
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
sys.path.insert(0, "/home/claude/eberle-buero/lib")
from pypdf import PdfReader
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:500]))
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
def A(m, p, d=None, c=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
IBAN1, IBAN2 = "DE02120300000000202051", "DE89370400440532013000"
A("PUT", "einstellungen", {"firma": "Muster", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890", "sepa_iban": IBAN1, "firma_inhaber": "Jonas Muster",
                           "mail": {"adresse": "betrieb@beispiel.de", "smtp_server": "127.0.0.1", "smtp_port": srv.server_address[1], "smtp_modus": "keine", "passwort": "x", "gesendet_ablegen": False}})
def prot(art): return A("GET", f"service/protokoll?art={art}")["eintraege"]
def pdftext(roh): return " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(roh)).pages)

print("== G1: versandte Fassungen")
k = A("POST", "kunden", {"kurzname": "Versand, Vera", "nachname": "Versand", "vorname": "Vera", "strasse": "Hauptstraße 5", "plz": "88069", "ort": "Tettnang", "email1": "vera@beispiel.de"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Kommode"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Kommode Eiche"}); pid = po.get("id") or po["position"]["id"]; A("PUT", f"positionen/{pid}", {"einzelpreis": 800, "preis_manuell": 1, "menge": 1})
an = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"}); bid = an["id"]
m1 = A("POST", f"belege/{bid}/mail", {"an": "vera@beispiel.de", "betreff": "Angebot", "text": "Guten Tag", "anhaenge": ["beleg"]})
b1 = A("GET", f"belege/{bid}")
ok("Angebot über 800 € per E-Mail gesendet: eine Fassung festgehalten", m1["_s"] == 200 and len(b1.get("versand") or []) == 1 and b1["versand"][0]["weg"] == "E-Mail" and abs(b1["versand"][0]["brutto"] - 952) < 0.01, (m1["_s"], m1.get("fehler"), b1.get("versand")))
ok("die Antwort an die Oberfläche nennt den Ablagepfad der Mail nicht", "datei" not in m1 and "mails" not in json.dumps({k_: v_ for k_, v_ in m1.items() if k_ != "beleg"}), [x for x in m1 if x != "beleg"])
A("PUT", f"positionen/{pid}", {"einzelpreis": 650, "preis_manuell": 1, "menge": 1}); A("POST", f"belege/{bid}/aktualisieren", {})
time.sleep(1.1)
m2 = A("POST", f"belege/{bid}/mail", {"an": "vera@beispiel.de", "betreff": "Angebot neu", "text": "Guten Tag", "anhaenge": ["beleg"]})
b2 = A("GET", f"belege/{bid}"); v = b2.get("versand") or []
ok("auf 650 € geändert und unter derselben Nummer erneut gesendet: zwei Fassungen", m2["_s"] == 200 and len(v) == 2 and abs(v[1]["brutto"] - 773.5) < 0.01, v)
if len(v) == 2:
    s1, f1, _ = rq(inh, "GET", f"/druck/{bid}/versandt/{v[0]['id']}.pdf", roh=True); s2, f2, _ = rq(inh, "GET", f"/druck/{bid}/versandt/{v[1]['id']}.pdf", roh=True)
    t1, t2 = pdftext(f1) if s1 == 200 else "", pdftext(f2) if s2 == 200 else ""
    ok("die erste Fassung zeigt weiter 952,00 €, die zweite 773,50 €", "952,00" in t1 and "773,50" not in t1 and "773,50" in t2, (s1, s2, t1[-200:], t2[-200:]))
    anh = email.message_from_bytes(POST[-2], policy=email.policy.default)
    gesendet = next((p.get_payload(decode=True) for p in anh.iter_attachments() if p.get_content_type() == "application/pdf"), b"")
    ok("die festgehaltene Datei ist Byte für Byte der Anhang, der hinausging", s1 == 200 and gesendet == f1 and len(f1) > 1000, (len(gesendet), len(f1)))
pv = prot("beleg_versandt")
ok("im Protokoll stehen beide Versandvorgänge mit Prüfsumme", len(pv) == 2 and all("Fassung festgehalten" in e["text"] for e in pv), [e["text"][:90] for e in pv])
kor = A("GET", f"korrespondenz?kunde={k['id']}"); kl = kor.get("liste") or kor.get("eintraege") or []
mit_datei = [x for x in kl if x.get("art") == "mail_aus" and x.get("datei")]
ok("Schriftverkehr: zu beiden gesendeten Mails liegt die vollständige Mail (.eml)", len(mit_datei) == 2, [(x.get("art"), x.get("datei")) for x in kl])
if mit_datei:
    s_, eml, _ = rq(inh, "GET", f"/api/korrespondenz/{mit_datei[0]['id']}/eml", roh=True); msg = email.message_from_bytes(eml, policy=email.policy.default) if s_ == 200 else None
    ok("die abgelegte Mail enthält Empfänger, Betreff und das PDF als Anhang", s_ == 200 and "vera@beispiel.de" in str(msg["To"]) and any(p.get_content_type() == "application/pdf" for p in msg.iter_attachments()), s_)
r = A("DELETE", f"belege/{bid}")
ok("versandtes Angebot lässt sich nicht löschen (verständliche Begründung)", r["_s"] == 409 and "Schriftverkehr" in r.get("fehler", "") and "vera@beispiel.de" in r.get("fehler", ""), (r["_s"], r.get("fehler")))
an2 = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"}); r = A("DELETE", f"belege/{an2['id']}")
ok("ein nicht versandtes Angebot lässt sich weiter löschen", r["_s"] == 200, (r["_s"], r.get("fehler")))
an3 = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"}); r = A("POST", f"belege/{an3['id']}/versendet", {"weg": "Post"}); b3 = A("GET", f"belege/{an3['id']}")
ok("„Als versendet vermerken“ (Post): Fassung festgehalten", r["_s"] == 200 and len(b3.get("versand") or []) == 1 and b3["versand"][0]["weg"] == "Post", (r["_s"], r.get("fehler"), b3.get("versand")))
r = A("DELETE", f"belege/{an3['id']}")
ok("auch dieser Beleg lässt sich nicht löschen, mit Hinweis auf „Vermerk zurücknehmen“", r["_s"] == 409 and "Vermerk zurücknehmen" in r.get("fehler", ""), (r["_s"], r.get("fehler")))
A("DELETE", f"belege/{an3['id']}/versendet"); r = A("DELETE", f"belege/{an3['id']}")
ok("nach „Vermerk zurücknehmen“ ist das Löschen wieder möglich (Versehen)", r["_s"] == 200, (r["_s"], r.get("fehler")))
re1 = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); A("POST", f"belege/{re1['id']}/festschreiben", {})
mr = A("POST", f"belege/{re1['id']}/mail", {"an": "vera@beispiel.de", "betreff": "Rechnung", "text": "Guten Tag", "anhaenge": ["beleg"]}); br = A("GET", f"belege/{re1['id']}")
ok("festgeschriebene Rechnung per E-Mail: keine zusätzliche Fassung nötig (das Archiv-PDF ist unveränderlich)", mr["_s"] == 200 and br.get("versand") == [], (mr["_s"], br.get("versand")))
pr = A("GET", "service/protokoll?voll=1"); bel = pr.get("belege") or {}
ok("Belegprüfung: drei versandte Fassungen geprüft, alles in Ordnung", bel.get("ok") and bel.get("versandt_geprueft") == 3, bel)
con = sqlite3.connect(D + "/buero.db", timeout=20); con.row_factory = sqlite3.Row
dateien = [r["datei"] for r in con.execute("SELECT datei FROM beleg_versand ORDER BY id")]
p0 = os.path.join(D, "belege", dateien[0]); roh0 = open(p0, "rb").read(); open(p0, "wb").write(roh0 + b"\n% nachgetragen")
bel = (A("GET", "service/protokoll?voll=1").get("belege") or {})
ok("versandte Fassung nachträglich verändert: die Belegprüfung meldet es", not bel.get("ok") and any("nachträglich verändert" in f for f in bel.get("fehler") or []), bel.get("fehler"))
os.remove(p0); bel = (A("GET", "service/protokoll?voll=1").get("belege") or {})
ok("versandte Fassung gelöscht: die Belegprüfung meldet es", any("fehlt" in f and "Versandte Fassung" in f for f in bel.get("fehler") or []), bel.get("fehler"))
open(p0, "wb").write(roh0)

print("== G2: Stammdaten und Einstellungen")
n0 = len(prot("stammdaten"))
li = A("POST", "lieferanten", {"kurzname": "Holz Huber", "firma": "Holz Huber GmbH", "iban": IBAN1, "zahlungsziel": 14})
ok("Anlegen eines Lieferanten: kein Änderungseintrag", len(prot("stammdaten")) == n0)
A("PUT", f"lieferanten/{li['id']}", {"iban": "DE89 3704 0044 0532 0130 00", "zahlungsziel": 30, "strasse": "Neue Gasse 9"})
e = prot("stammdaten")[0] if prot("stammdaten") else {"text": "", "objekt": ""}
ok("Lieferant: neue IBAN und Zahlungsziel stehen im Protokoll – IBAN verkürzt, alt und neu", "IBAN DE02 … 2051 → DE89 … 3000" in e["text"] and "Zahlungsziel (Tage) 14 → 30" in e["text"] and "Anschrift geändert" in e["text"], e["text"])
ok("… ohne vollständige IBAN, ohne Straße, ohne Namen; bezeichnet mit der Lieferantennummer", IBAN2 not in e["text"] and "Neue Gasse" not in e["text"] and "Huber" not in e["text"] + e["objekt"] and str(li.get("nummer") or "") in e["objekt"], (e["objekt"], e["text"]))
n1 = len(prot("stammdaten")); A("PUT", f"lieferanten/{li['id']}", {"iban": IBAN2, "zahlungsziel": 30})
ok("Speichern ohne Änderung (IBAN nur anders geschrieben): kein Eintrag", len(prot("stammdaten")) == n1, prot("stammdaten")[0]["text"])
A("PUT", f"kunden/{k['id']}", {"zahlungsziel": 30, "skonto": 2, "skontotage": 10, "strasse": "Nebenweg 7", "nachname": "Neuname", "telefon": "07542 1234", "bemerkungen": "privat"})
e = prot("stammdaten")[0]
ok("Kunde: Zahlungsbedingungen mit Werten, Name/Anschrift/Kontakt nur als Tatsache", all(t in e["text"] for t in ("Skonto % leer → 2", "Skontotage leer → 10", "Name geändert", "Anschrift geändert", "Kontaktdaten geändert")) or all(t in e["text"] for t in ("Skonto % 0 → 2", "Name geändert", "Anschrift geändert", "Kontaktdaten geändert")), e["text"])
ok("… ohne Namen, Straße, Telefonnummer oder Bemerkung", not any(t in e["text"] + e["objekt"] for t in ("Neuname", "Versand", "Vera", "Nebenweg", "07542", "privat")), (e["objekt"], e["text"]))
ma = A("POST", "mitarbeiter", {"vorname": "Max", "nachname": "Muster", "stundenlohn": 18.5, "iban": IBAN1}); mid_ = ma.get("id") or ma.get("mitarbeiter", {}).get("id")
A("PUT", f"mitarbeiter/{mid_}", {"stundenlohn": 21.0, "iban": IBAN2})
e = prot("stammdaten")[0]
ok("Mitarbeiter: Lohnangaben als Tatsache (ohne Betrag), IBAN verkürzt", "Lohnangaben geändert" in e["text"] and "IBAN DE02 … 2051 → DE89 … 3000" in e["text"] and "21" not in e["text"].replace("2051", "") and "18,5" not in e["text"] and "Muster" not in e["text"] + e["objekt"], (e["objekt"], e["text"]))
n2 = len(prot("einstellung"))
A("PUT", "einstellungen", {"sepa_iban": IBAN2, "firma": "Muster & Sohn", "netzwerk": False, "zugferd": False, "firma_anschrift": "Neuer Weg 2\n88069 Tettnang"})
e = prot("einstellung")[0]
ok("Einstellungen: IBAN des Betriebs verkürzt, Firmenname mit Wert, Schalter, Anschrift als Tatsache", all(t in e["text"] for t in ("IBAN des Betriebs DE02 … 2051 → DE89 … 3000", "Firmenname Muster → Muster & Sohn", "E-Rechnung im PDF (ZUGFeRD) ausgeschaltet", "Firmenanschrift geändert")) and "Neuer Weg" not in e["text"], e["text"])
n3 = len(prot("einstellung")); A("PUT", "einstellungen", {"mail": {"adresse": "betrieb@beispiel.de", "smtp_server": "127.0.0.1", "smtp_port": srv.server_address[1], "smtp_modus": "keine", "gesendet_ablegen": False}})
ok("E-Mail-Einstellungen unverändert gespeichert (ohne neues Passwort): kein Eintrag", len(prot("einstellung")) == n3, prot("einstellung")[0]["text"])
A("PUT", "einstellungen", {"mail": {"adresse": "betrieb@beispiel.de", "smtp_server": "localhost", "smtp_port": srv.server_address[1], "smtp_modus": "keine", "gesendet_ablegen": False, "passwort": "neu-geheim"}})
e = prot("einstellung")[0]
ok("Server und Passwort des E-Mail-Versands geändert: genannt wird, was – nie der Inhalt", "E-Mail-Versand geändert" in e["text"] and "Postausgangsserver" in e["text"] and "Passwort" in e["text"] and "neu-geheim" not in json.dumps(e) and "localhost" not in e["text"], e["text"])
A("PUT", "einstellungen", {"mail": {"adresse": "betrieb@beispiel.de", "smtp_server": "127.0.0.1", "smtp_port": srv.server_address[1], "smtp_modus": "keine", "gesendet_ablegen": False, "passwort": "x"}})

print("== M3: Benutzer und Rechte")
u = A("POST", "benutzer", {"name": "Berta Büro", "login": "berta", "passwort": "Pruefung#2026", "rolle": "buero", "email": "berta@beispiel.de"})
A("PUT", f"benutzer/{u['id']}", {"rolle": "werkstatt"}); A("PUT", f"benutzer/{u['id']}", {"rolle": "eigen", "eigen": {"bereiche": {"auftraege": 2, "kunden": 1}, "preise": False}})
A("PUT", f"benutzer/{u['id']}", {"passwort": "Neues#Passwort1"}); A("PUT", f"benutzer/{u['id']}", {"aktiv": False}); A("PUT", f"benutzer/{u['id']}", {"aktiv": True, "email": "b2@beispiel.de"}); A("DELETE", f"benutzer/{u['id']}")
t = [e["text"] for e in prot("benutzer")][::-1]; alles = " | ".join(t)
ok("Anlegen mit Rolle", any("Benutzer „berta“ angelegt (Rolle Büro)" in x for x in t), alles)
ok("Rollenwechsel alt → neu", "Rolle Büro → Werkstatt" in alles, alles)
ok("eigene Rechte in Worten", "eigene Rechte: " in alles and "Aufträge bearbeiten" in alles and "Kunden & Briefe lesen" in alles and "ohne Preise" in alles, alles)
ok("Passwort neu gesetzt, gesperrt, wieder freigegeben, E-Mail-Adresse geändert, gelöscht", all(x in alles for x in ("Passwort bzw. PIN neu gesetzt", "gesperrt", "wieder freigegeben", "E-Mail-Adresse für „Passwort vergessen“ geändert", "Benutzer „berta“ gelöscht")), alles)
ok("… ohne Passwort und ohne die E-Mail-Adresse selbst", "Neues#Passwort1" not in alles and "b2@beispiel.de" not in alles and "berta@beispiel.de" not in alles, alles)
arten = A("GET", "service/protokoll")["arten"]
ok("die neuen Arten sind im Protokoll auswählbar", all(x in arten for x in ("anmeldung", "benutzer", "stammdaten", "einstellung", "beleg_versandt", "passwort")), [x for x in ("anmeldung", "benutzer", "stammdaten", "einstellung", "beleg_versandt", "passwort") if x not in arten])

print("== G4: festgeschriebene Rechnung ohne Protokolleintrag")
def fremd_einfuegen(nummer, lfd):
    r = dict(con.execute("SELECT * FROM belege WHERE id=?", (re1["id"],)).fetchone()); r.pop("id"); r.update(nummer=nummer, lfd=lfd, geaendert=time.strftime("%Y-%m-%dT%H:%M:%S"), angelegt=time.strftime("%Y-%m-%dT%H:%M:%S"))
    con.execute(f"INSERT INTO belege ({','.join(r)}) VALUES ({','.join('?' * len(r))})", list(r.values())); con.commit()
fremd_einfuegen("2026-9001", 9001)
bel = (A("GET", "service/protokoll?voll=1").get("belege") or {})
ok("vor dem Echtbetrieb: zählt als „ohne Protokolleintrag“ (Testphase, Datenübernahme)", bel.get("ohne_protokoll") == 1 and not any("ohne Eintrag im Protokoll" in f for f in bel.get("fehler") or []), bel)
time.sleep(1.2); r = A("POST", "service/echtbetrieb", {"bestaetigung": "ECHTBETRIEB"}); time.sleep(1.2)
fremd_einfuegen("2026-9002", 9002)
bel = (A("GET", "service/protokoll?voll=1").get("belege") or {})
ok("im Echtbetrieb: eine an der Festschreibung vorbei entstandene Rechnung wird als Fehler gemeldet", r["_s"] == 200 and any("2026-9002" in f and "ohne Eintrag im Protokoll" in f for f in bel.get("fehler") or []) and not any("2026-9001" in f for f in bel.get("fehler") or []), (r["_s"], r.get("fehler"), bel.get("fehler")))
con.close()
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
