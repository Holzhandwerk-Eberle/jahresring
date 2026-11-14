import base64, json
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
o = cl(); rq(o, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
rq(o, "PUT", "/api/einstellungen", {"projektpfad": "/tmp/claude-0/t/v25/projekte"})
a = json.loads(rq(o, "GET", "/api/auftraege")[1])[0]["id"]
print("ordner", rq(o, "POST", f"/api/auftraege/{a}/ordner", {})[1][:120])
for n, d in (("boese.html", b"<script>fetch('/api/kunden')</script>"), ("boese.svg", b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>"), ("ok.pdf", b"%PDF-1.4"), ("start.bat", b"calc.exe"), ("bild.png", b"\x89PNG")):
    s, b, _ = rq(o, "POST", f"/api/auftraege/{a}/hochladen", {"dateiname": n, "daten": base64.b64encode(d).decode()})
    s2, b2, h = rq(o, "GET", f"/api/auftraege/{a}/datei?pfad={n}")
    print(n, s, s2, h.get("Content-Type"), "|", h.get("Content-Disposition"), "|", h.get("Content-Security-Policy"))
print("bat öffnen:", rq(o, "POST", f"/api/auftraege/{a}/oeffnen", {"pfad": "start.bat"})[1][:110])
print("traversal:", rq(o, "GET", f"/api/auftraege/{a}/datei?pfad=../../eberle-buero/app.py")[0], rq(o, "GET", f"/api/auftraege/{a}/datei?pfad=..%2F..%2Feberle-buero%2Fdaten%2Fbuero.db")[0])
s, b, h = rq(o, "GET", "/"); print("Server-Header:", h.get("Server"))
import sys; sys.path.insert(0, "/tmp/claude-0/t/v25/eberle-buero"); import os; os.chdir("/tmp/claude-0/t/v25/eberle-buero"); import app
app.ANFRAGE.lokal = False
try: app.nur_am_pc("Öffnen"); print("FEHLER: fremdes Gerät durfte öffnen")
except app.ApiFehler as f: print("fremdes Gerät:", f)
