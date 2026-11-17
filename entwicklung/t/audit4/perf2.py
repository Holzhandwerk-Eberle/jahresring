"""Geschwindigkeit bei sehr großer Datenbank: Schreiben, Sicherung, Exporte, gleichzeitige Zugriffe, Protokollprüfung."""
import json, re, sys, time, os, threading, sqlite3, glob, base64
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
U = "http://127.0.0.1:8797"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
def neu():
    c = cl(); rq(c, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}); return c
inh = neu()
def A(m, p, d=None, c=None, h=None):
    z = time.time(); s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    j["_ms"] = int((time.time() - z) * 1000); return j
PID = int(os.popen("for f in /proc/[0-9]*/environ; do grep -qa 'BUERO_PORT=8797' $f 2>/dev/null && basename $(dirname $f); done | head -1").read().strip() or 0)
rss = lambda: int([z for z in open(f"/proc/{PID}/status") if z.startswith("VmRSS")][0].split()[1]) // 1024
print("Server-Arbeitsspeicher zu Beginn:", rss(), "MB")
print("== Lesen (zweiter Aufruf, warm)")
for p in ("start?jahr=2026", "kunden?feld=alle&q=&gruppe=&status=aktiv", "kunden?feld=alle&q=Wolf&gruppe=&status=aktiv", "auftraege?q=&gruppe=&status=", "auftraege?q=K%C3%BCche&gruppe=&status=", "belege", "offeneposten?status=offen", "offeneposten?status=alle", "zahlungen?q=&status=alle&bezahlung=", "mitarbeiter?status=aktiv", "lohn?monat=2026-10", "zeiten?monat=2026-10", "kalender?von=2026-11-01&bis=2026-12-31", "suche?q=Wolf", "suche?q=Eiche", "suche?q=2019-8", "statistik?jahr=2025", "liquiditaet", "mahnwesen", "korrespondenz", "service/protokoll", "service/protokoll?voll=1", "material?kat=beschlaege&q=&gruppe=&status=", "material?kat=alle&q=Eiche", "projekte?q=&status=alle", "leitstand", "wiedervorlagen", "bank"):
    A("GET", p); x = A("GET", p); print("  %-52s %5d ms %8.1f MB  HTTP %s" % (p[:52], x["_ms"], len(x["_roh"]) / 1048576, x["_s"]))
print("== Schreiben")
k = A("POST", "kunden", {"kurzname": "Tempo, Tina", "nachname": "Tempo", "plz": "88069", "ort": "Tettnang"}); print("  Kunde anlegen %d ms" % k["_ms"])
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Großauftrag"}); print("  Auftrag anlegen %d ms" % a["_ms"])
zeiten = []
for i in range(120):
    po = A("POST", f"auftraege/{a['id']}/positionen", {"text": f"Position {i} Korpus Eiche"}); pid = po.get("id") or po["position"]["id"]; x = A("PUT", f"positionen/{pid}", {"einzelpreis": 100 + i, "preis_manuell": 1, "menge": 2}); zeiten.append(po["_ms"] + x["_ms"])
print("  120 Positionen anlegen+bepreisen: erste %d ms, letzte %d ms, Summe %.1f s" % (zeiten[0], zeiten[-1], sum(zeiten) / 1000))
x = A("GET", f"auftraege/{a['id']}/positionen"); print("  Positionen des Auftrags (120) lesen: %d ms, %.2f MB" % (x["_ms"], len(x["_roh"]) / 1048576))
b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); print("  Rechnung aus 120 Positionen anlegen: %d ms" % b["_ms"])
f = A("POST", f"belege/{b['id']}/festschreiben", {}); print("  Festschreiben: %d ms %s %s" % (f["_ms"], f["_s"], (f.get("beleg") or f).get("nummer", f.get("fehler", ""))))
z = time.time(); s, t, _ = rq(inh, "GET", f"/druck/{b['id']}.pdf", roh=True); print("  PDF der Rechnung (120 Positionen, Übertrag an): %.1f s, %s, %.0f kB" % (time.time() - z, s, len(t) / 1024))
z = time.time(); s, t, _ = rq(inh, "GET", f"/druck/{b['id']}.pdf", roh=True); print("  PDF erneut (aus dem Archiv): %.2f s" % (time.time() - z))
an = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"}); A("PUT", f"belege/{an['id']}", {"druck": {"uebertrag": False}}); z = time.time(); s, t, _ = rq(inh, "GET", f"/druck/{an['id']}.pdf", roh=True); t1 = time.time() - z
A("PUT", f"belege/{an['id']}", {"druck": {"uebertrag": True}}); z = time.time(); s, t, _ = rq(inh, "GET", f"/druck/{an['id']}.pdf", roh=True); print("  Angebot-PDF 120 Positionen: ohne Übertrag %.1f s, mit Übertrag %.1f s" % (t1, time.time() - z))
print("== Sicherung und Exporte")
x = A("POST", "service/sicherung", {}); print("  Vollständige Sicherung: %.1f s, %s, %s" % (x["_ms"] / 1000, x.get("groesse"), x.get("name", x.get("fehler", ""))))
for art in ("datev", "belegpaket", "pruefer"):
    x = A("POST", f"service/{art}", {"von": "2025-01-01", "bis": "2025-12-31"}); print("  Export %-10s 2025: %.1f s, HTTP %s %s %s" % (art, x["_ms"] / 1000, x["_s"], x.get("groesse", ""), str(x.get("fehler") or x.get("buchungen") or x.get("datei") or "")[:120]))
print("== Gleichzeitige Zugriffe (8 lesende, 3 schreibende Benutzer, 25 s)")
stop = time.time() + 25; erg = {"lesen": [], "schreiben": [], "fehler": []}
def leser(i):
    c = neu(); pf = ["start?jahr=2026", "kunden?feld=alle&q=Wolf&gruppe=&status=aktiv", "auftraege?q=Tisch&gruppe=&status=", "offeneposten?status=offen", f"auftraege/{a['id']}/positionen", "suche?q=Becker"]
    n = 0
    while time.time() < stop:
        x = A("GET", pf[(n + i) % len(pf)], c=c); n += 1
        (erg["lesen"] if x["_s"] == 200 else erg["fehler"]).append((x["_ms"], x["_s"], x.get("fehler", "")[:80]))
def schreiber(i):
    c = neu(); n = 0
    aa = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": f"Parallel {i}"}, c=c)
    while time.time() < stop:
        po = A("POST", f"auftraege/{aa['id']}/positionen", {"text": f"P{n}"}, c=c); n += 1
        if po["_s"] != 200: erg["fehler"].append((po["_ms"], po["_s"], po.get("fehler", "")[:80])); continue
        pid = po.get("id") or po["position"]["id"]; x = A("PUT", f"positionen/{pid}", {"einzelpreis": 10 + n, "preis_manuell": 1, "menge": 1}, c=c)
        (erg["schreiben"] if x["_s"] == 200 else erg["fehler"]).append((po["_ms"] + x["_ms"], x["_s"], x.get("fehler", "")[:80]))
ths = [threading.Thread(target=leser, args=(i,)) for i in range(8)] + [threading.Thread(target=schreiber, args=(i,)) for i in range(3)]
[t.start() for t in ths]; [t.join() for t in ths]
ms = lambda l: (len(l), sorted(x[0] for x in l)[len(l) // 2] if l else 0, max(x[0] for x in l) if l else 0)
print("  Lesen: %d Anfragen, Median %d ms, längste %d ms | Schreiben: %d Vorgänge, Median %d ms, längster %d ms | Fehler: %d %s" % (*ms(erg["lesen"]), *ms(erg["schreiben"]), len(erg["fehler"]), erg["fehler"][:3]))
print("Server-Arbeitsspeicher am Ende:", rss(), "MB")
