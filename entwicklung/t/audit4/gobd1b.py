"""GoBD-Proben: versendete Belege, Löschen/Ändern mit Spur, Erkennen von Eingriffen, Pflichtangaben, Datumslogik."""
import json, re, sys, base64, time, os, sqlite3, glob, socketserver, threading, hashlib, io, email, shutil
from datetime import date, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    return j
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
A("PUT", "einstellungen", {"mail": {"adresse": "ich@beispiel.de", "smtp_server": "127.0.0.1", "smtp_port": srv.server_address[1], "smtp_modus": "keine", "passwort": "x", "gesendet_ablegen": False}})
def prot_letzte(n=6):
    pr = A("GET", "service/protokoll"); return [(e.get("art"), e.get("text", "")[:150]) for e in (pr.get("eintraege") or [])[-n:]]
def pruefung():
    pr = A("GET", "service/protokoll?voll=1"); return pr.get("pruefung", {}), [f for f in (pr.get("belege", {}).get("fehler") or []) if "2026-0051" not in f and "2026-0052" not in f]
k = A("POST", "kunden", {"kurzname": "GoBD, Gustav", "nachname": "GoBD", "vorname": "Gustav", "strasse": "Weg", "hausnr": "1", "plz": "88069", "ort": "Tettnang", "email1": "gustav@beispiel.de"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Tisch"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Esstisch Eiche"}); pid = po.get("id") or po["position"]["id"]; A("PUT", f"positionen/{pid}", {"einzelpreis": 2000, "preis_manuell": 1, "menge": 1})
ERST = False
print("== 1. Versendetes Angebot: bleibt die versandte Fassung erhalten?")
an = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"}); bid = an["id"]
m = A("POST", f"belege/{bid}/mail", {"an": "gustav@beispiel.de", "betreff": "Angebot", "text": "Guten Tag", "anhaenge": ["beleg"]}); print("  Mail:", m["_s"], m.get("fehler", "")[:100]); time.sleep(0.4)
bb = A("GET", f"belege/{bid}"); print("  Angebot nach Versand: status=%s nummer=%s pdf=%r versendet=%r" % (bb.get("status"), bb.get("nummer"), str(bb.get("pdf"))[-40:], bb.get("versendet")))
ar = sorted(glob.glob(D + "/belege/**/*", recursive=True)); print("  Archiv:", [x.replace(D, "") for x in ar if bb.get("nummer", "?") in x])
h1 = hashlib.sha256(rq(inh, "GET", f"/druck/{bid}.pdf", roh=True)[1]).hexdigest()[:12]
r = A("PUT", f"positionen/{pid}", {"einzelpreis": 1500, "preis_manuell": 1, "menge": 1}); print("  Preis nach Versand geändert (2000 → 1500):", r["_s"], r.get("fehler", "")[:120])
bb2 = A("GET", f"belege/{bid}"); print("  Angebot danach: netto=%s (versandt wurden 2000)" % bb2.get("netto"))
ko = A("GET", f"korrespondenz?auftrag={a['id']}"); kl = ko.get("liste") or ko.get("eintraege") or []
print("  Schriftverkehr zum Auftrag:", [(x.get("art"), x.get("betreff"), bool(x.get("datei")), x.get("anhaenge")) for x in kl][:4])
for x in kl[:1]:
    s, t, _ = rq(inh, "GET", f"/api/korrespondenz/{x['id']}/eml", roh=True); 
    if s == 200:
        msg = email.message_from_bytes(t); print("  Gespeicherte Mail enthält Anhänge:", [(p.get_filename(), len(p.get_payload(decode=True) or b"")) for p in msg.walk() if p.get_filename()])
    else: print("  eml:", s)
print("  Protokoll:", [p for p in prot_letzte(8) if "ngebot" in p[1] or "mail" in p[0]][-3:])
print("\n== 2. Rechnung: Änderungen nach dem Festschreiben")
re_ = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); rid = re_["id"]; f = A("POST", f"belege/{rid}/festschreiben", {}); nr = (f.get("beleg") or f).get("nummer"); print("  Rechnung", nr, "netto", (f.get("beleg") or f).get("netto"))
rq(inh, "GET", f"/druck/{rid}.pdf", roh=True)
for was, d in (("Einleitung", {"einleitung": "geändert"}), ("Datum", {"datum": "2026-01-01"}), ("Status zurück", {"status": "entwurf"}), ("Nummer", {"nummer": "2026-9999"}), ("Druck: Übertrag", {"druck": {"uebertrag": False}}), ("Druck: Zahlungsziel", {"druck": {"zahlungsziel": 99}}), ("Kunde", {"kunde_id": 1}), ("Betrag", {"netto": 1, "brutto": 1})):
    r = A("PUT", f"belege/{rid}", d); n = A("GET", f"belege/{rid}")
    print("  %-22s HTTP %s %s" % (was, r["_s"], r.get("fehler", "")[:90] or "ANGENOMMEN → " + str({k_: n.get(k_) for k_ in d if k_ != "druck"} or n.get("druck"))[:120]))
r = A("DELETE", f"belege/{rid}"); print("  Löschen der Rechnung: HTTP", r["_s"], r.get("fehler", "")[:100])
r = A("PUT", f"positionen/{pid}", {"einzelpreis": 999, "preis_manuell": 1}); n = A("GET", f"belege/{rid}"); print("  Auftragsposition nachträglich geändert → Rechnung netto bleibt:", n.get("netto"))
r = A("PUT", f"kunden/{k['id']}", {"strasse": "Neue Straße", "kurzname": "Umbenannt, Gustav"}); n = A("GET", f"belege/{rid}"); print("  Kunde umbenannt → Anschrift der Rechnung:", repr(n.get("anschrift"))[:80])
pr, bf = pruefung(); print("  Prüfung:", pr.get("ok"), bf[:3])
print("\n== 3. Eingriffe an Datenbank und Archiv werden erkannt?")
con = sqlite3.connect(D + "/buero.db", timeout=20); con.row_factory = sqlite3.Row
row = con.execute("SELECT * FROM belege WHERE id=?", (rid,)).fetchone(); print("  Spalten belege:", [k_ for k_ in row.keys() if any(w in k_ for w in ("hash", "sha", "fest", "pdf", "brutto", "netto"))])
con.execute("UPDATE belege SET brutto=brutto-100 WHERE id=?", (rid,)); con.commit(); pr, bf = pruefung(); print("  a) Bruttobetrag in der DB um 100 gesenkt →", bf[:2] or "NICHT ERKANNT")
con.execute("UPDATE belege SET brutto=brutto+100 WHERE id=?", (rid,)); con.commit()
pdf = row["pdf"]; print("  Archiv-PDF:", str(pdf).replace(D, ""))
if pdf and os.path.isfile(pdf):
    shutil.copy(pdf, pdf + ".orig"); open(pdf, "ab").write(b"\n% manipuliert\n"); pr, bf = pruefung(); print("  b) Archiv-PDF verändert →", bf[:2] or "NICHT ERKANNT"); shutil.move(pdf + ".orig", pdf)
tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
pcols = [r[1] for r in con.execute("PRAGMA table_info(protokoll)")]; print("  Spalten protokoll:", pcols)
letzte = con.execute("SELECT * FROM protokoll ORDER BY nr DESC LIMIT 1").fetchone()
mitte = con.execute("SELECT * FROM protokoll WHERE art='festschreiben' ORDER BY nr DESC LIMIT 1").fetchone()
con.execute("UPDATE protokoll SET text=replace(text, 'brutto', 'BRUTTO') WHERE nr=?", (mitte["nr"],)); con.commit(); pr, bf = pruefung(); print("  c) Protokolltext geändert →", (pr.get("ok"), str(pr.get("fehler") or pr.get("text") or pr)[:160]))
con.execute("UPDATE protokoll SET text=? WHERE nr=?", (mitte["text"], mitte["nr"])); con.commit()
kopie = [tuple(r) for r in con.execute("SELECT * FROM protokoll WHERE nr>=?", (letzte["nr"] - 1,))]
con.execute("DELETE FROM protokoll WHERE nr>=?", (letzte["nr"] - 1,)); con.commit(); pr, bf = pruefung(); print("  d) die letzten zwei Protokollzeilen gelöscht →", (pr.get("ok"), str(pr.get("fehler") or pr.get("text") or "")[:200]))
con.executemany(f"INSERT INTO protokoll VALUES ({','.join('?' * len(pcols))})", kopie); con.commit()
pr, bf = pruefung(); print("  wiederhergestellt:", pr.get("ok"), bf[:2])
trig = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'")]; print("  Datenbank-Trigger (Schutz auf DB-Ebene):", trig or "keine")
print("\n== 4. Zahlungseingang löschen, Stammdaten ändern: Spur im Protokoll?")
ops = A("GET", "offeneposten"); op = [o for o in (ops.get("liste") or ops.get("posten") or []) if o.get("beleg_id") == rid][0]
A("POST", f"offeneposten/{op['id']}/zahlung", {"datum": date.today().isoformat(), "betrag": 500, "art": "Bar"}); zl = A("GET", f"offeneposten/{op['id']}/zahlungen")["liste"]; print("  Zahlung gebucht:", [(z.get("betrag"), z.get("art")) for z in zl])
r = A("DELETE", f"zahlungseingaenge/{zl[0]['id']}"); print("  Zahlung gelöscht:", r["_s"], r.get("fehler", "")[:80], "| Protokoll:", [p for p in prot_letzte(4) if "ahlung" in p[1]][-2:])
n0 = len(A("GET", "service/protokoll").get("eintraege") or [])
li = A("POST", "lieferanten", {"kurzname": "Holz AG", "iban": "DE02120300000000202051"}); A("PUT", f"lieferanten/{li['id']}", {"iban": "DE89370400440532013000"})
A("PUT", "einstellungen", {"sepa_iban": "DE89370400440532013000"}); A("PUT", "einstellungen", {"sepa_iban": "DE02120300000000202051"})
A("PUT", f"kunden/{k['id']}", {"ust": 7})
print("  Protokoll nach IBAN-Wechsel Lieferant, IBAN-Wechsel Betrieb, USt-Satz Kunde:", [p for p in prot_letzte(6)][-(len(A("GET", "service/protokoll").get("eintraege") or []) - n0) or 99:] if len(A("GET", "service/protokoll").get("eintraege") or []) > n0 else "KEIN EINTRAG")
print("\n== 5. Datumslogik beim Festschreiben")
for dat, was in (((date.today() - timedelta(days=400)).isoformat(), "Vorjahr"), ((date.today() + timedelta(days=60)).isoformat(), "in 60 Tagen")):
    x = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); r1 = A("PUT", f"belege/{x['id']}", {"datum": dat}); f = A("POST", f"belege/{x['id']}/festschreiben", {}, h={"X-Rueckfrage": "1"})
    print("  Rechnungsdatum %s (%s): setzen %s, festschreiben %s %s %s" % (dat, was, r1["_s"], f["_s"], (f.get("beleg") or f).get("nummer", ""), (f.get("fehler") or f.get("frage") or f.get("rueckfrage") or "")[:160]))
    if f["_s"] != 200: A("DELETE", f"belege/{x['id']}")
print("\n== 6. Zahlarten / Kasse")
src = open("/home/claude/eberle-buero/app.py", encoding="utf-8").read()
print("  Zahlarten im Code:", sorted(set(re.findall(r'"(Bar|Überweisung|EC|Karte|Scheck|Lastschrift|PayPal|Barzahlung)"', src))), "| Kassenbuch im Code:", "kassenbuch" in src.lower(), "| TSE:", "tse" in src.lower().split())
con.close()
