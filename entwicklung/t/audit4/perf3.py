import json, re, sys, time, os, threading
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
U = "http://127.0.0.1:8797"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
def rq2(o, m, p, d=None, zeit=600):
    r = urllib.request.Request(U + p, method=m, data=json.dumps(d).encode() if d is not None else None, headers={"Content-Type": "application/json"})
    try:
        x = o.open(r, timeout=zeit); b = x.read(); return x.status, b.decode("utf-8", "replace")
    except urllib.error.HTTPError as e: return e.code, e.read().decode("utf-8", "replace")
def neu():
    c = cl(); rq2(c, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}); return c
inh = neu()
def A(m, p, d=None, c=None):
    z = time.time(); s, b = rq2(c or inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    j["_ms"] = int((time.time() - z) * 1000); return j
PID = int(os.popen("for f in /proc/[0-9]*/environ; do grep -qa 'BUERO_PORT=8797' $f 2>/dev/null && basename $(dirname $f); done | head -1").read().strip() or 0)
rss = lambda: int([z for z in open(f"/proc/{PID}/status") if z.startswith("VmRSS")][0].split()[1]) // 1024
x = A("POST", "service/pruefer", {"von": "2025-01-01", "bis": "2025-12-31"}); print("Datenträgerüberlassung 2025: %.1f s, HTTP %s %s %s" % (x["_ms"] / 1000, x["_s"], x.get("groesse", ""), str(x.get("fehler") or x.get("datei") or "")[:120]), {k_: v for k_, v in x.items() if k_ in ("tabellen", "zeilen", "rechnungen")})
x = A("POST", "service/pruefer", {"von": "2012-01-01", "bis": "2026-12-31"}); print("Datenträgerüberlassung 15 Jahre: %.1f s, HTTP %s %s %s" % (x["_ms"] / 1000, x["_s"], x.get("groesse", ""), str(x.get("fehler") or x.get("datei") or "")[:120]))
print("RSS", rss(), "MB")
print("== Gleichzeitige Zugriffe (8 lesende, 3 schreibende Benutzer, 25 s)")
k = A("POST", "kunden", {"kurzname": "Parallel, Paula", "plz": "88069", "ort": "Tettnang"}); a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Parallel"})
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
# zwei Benutzer schreiben dieselbe Position (Stand-Schutz)
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Gemeinsam"}); pid = po.get("id") or po["position"]["id"]
print("Server-Arbeitsspeicher am Ende:", rss(), "MB")
