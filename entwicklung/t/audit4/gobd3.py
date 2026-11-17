import json, re, sys, base64, time, os, sqlite3, glob, hashlib, shutil, socketserver, threading
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
con = sqlite3.connect(D + "/buero.db", timeout=20); con.row_factory = sqlite3.Row
k = A("POST", "kunden", {"kurzname": "Angebot, Anton", "nachname": "Angebot", "plz": "88069", "ort": "Tettnang", "email1": "anton@beispiel.de"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Bank"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Sitzbank"}); pid = po.get("id") or po["position"]["id"]; A("PUT", f"positionen/{pid}", {"einzelpreis": 800, "preis_manuell": 1, "menge": 1})
an = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"}); bid = an["id"]
def stand(was):
    b = A("GET", f"belege/{bid}"); pdf = con.execute("SELECT pdf FROM belege WHERE id=?", (bid,)).fetchone(); pdf = pdf[0] if pdf else ""
    dateien = {os.path.basename(f): hashlib.sha256(open(f, "rb").read()).hexdigest()[:10] for f in glob.glob(D + "/belege/**/*", recursive=True) if os.path.isfile(f) and (b.get("nummer") or "2026-0011") [:9] in f}
    print("  %-34s status=%s nummer=%s netto=%s | Archiv: %s" % (was, b.get("status"), b.get("nummer"), b.get("netto"), dateien))
    return b
stand("neu")
m = A("POST", f"belege/{bid}/mail", {"an": "anton@beispiel.de", "betreff": "Angebot", "text": "Guten Tag", "anhaenge": ["beleg"]}); time.sleep(0.3); b1 = stand("nach 1. Versand (800 €)")
A("PUT", f"positionen/{pid}", {"einzelpreis": 650, "preis_manuell": 1, "menge": 1}); r = A("POST", f"belege/{bid}/aktualisieren", {}); print("   aktualisieren:", r["_s"], r.get("fehler", "")[:100]); stand("Preis auf 650 geändert")
m = A("POST", f"belege/{bid}/mail", {"an": "anton@beispiel.de", "betreff": "Angebot neu", "text": "Guten Tag", "anhaenge": ["beleg"]}); time.sleep(0.3); print("   2. Mail:", m["_s"], m.get("fehler", "")[:100]); b2 = stand("nach 2. Versand (650 €)")
print("   Größe der versandten Anhänge:", [len(x) for x in POST])
print("   Protokoll zum Beleg:", [(r["art"], r["text"][:120]) for r in con.execute("SELECT art, text FROM protokoll WHERE text LIKE ? OR objekt LIKE ?", (f"%{b2['nummer']}%", f"%{b2['nummer']}%"))])
ko = A("GET", f"korrespondenz?auftrag={a['id']}"); print("   Schriftverkehr:", [(x.get("art"), x.get("betreff"), x.get("anhaenge")) for x in (ko.get("liste") or [])])
r = A("DELETE", f"belege/{bid}"); print("  Löschen des zweimal versandten Angebots:", r["_s"], r.get("fehler", "")[:140])
print("   Archivdateien danach:", [os.path.basename(f) for f in glob.glob(D + "/belege/**/*", recursive=True) if b2["nummer"] in f], "| Papierkorb:", [os.path.basename(f) for f in glob.glob(D + "/papierkorb/*")][:5])
ko = A("GET", f"korrespondenz?auftrag={a['id']}"); print("   Schriftverkehr danach:", [(x.get("art"), x.get("betreff"), x.get("anhaenge")) for x in (ko.get("liste") or [])])
print("   Protokoll:", [(r["art"], r["text"][:120]) for r in con.execute("SELECT art, text FROM protokoll ORDER BY nr DESC LIMIT 2")])
# Auftragsbestätigung (unterschrieben?) und Lieferschein löschbar?
ab = A("POST", f"auftraege/{a['id']}/belege", {"art": "ab"}); m = A("POST", f"belege/{ab['id']}/mail", {"an": "anton@beispiel.de", "betreff": "AB", "text": "Guten Tag", "anhaenge": ["beleg"]}); r = A("DELETE", f"belege/{ab['id']}"); print("  Versandte Auftragsbestätigung löschen:", r["_s"], r.get("fehler", "")[:140])
# Auftrag mit versandten Belegen löschen?
r = A("DELETE", f"auftraege/{a['id']}"); print("  Auftrag löschen (nach versandtem Angebot):", r["_s"], r.get("fehler", "")[:160])
