import json, base64, io
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
from PIL import Image, ImageDraw
buf = io.BytesIO(); im = Image.new("RGB", (300, 100), "white"); ImageDraw.Draw(im).line((10, 50, 290, 60), fill="black", width=4); im.save(buf, "PNG")
PNG = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
for lg, rolle, mid in (("werk", "werkstatt", None), ("max", "mitarbeiter", 1), ("buero", "buero", None)):
    print(lg, rq(inh, "POST", "/api/benutzer", {"name": lg.title(), "login": lg, "passwort": "passwort123", "rolle": rolle, "mitarbeiter_id": mid})[0])
# Auftrag mit Lack über Auftragskosten
k = J(rq(inh, "POST", "/api/kunden", {"kurzname": "Kunde", "ort": "Tettnang"})[1]); a = J(rq(inh, "POST", "/api/auftraege", {"kunde_id": k["id"], "bezeichnung": "Tisch"})[1])
s, b, _ = rq(inh, "POST", "/api/auftragskosten", {"auftrag_id": a["id"], "material_id": 1, "menge": 2, "kostenart": "werkstoffe", "bezeichnung": "Klarlack"}); print("ak", s, b[:100])
print("auftrag box", rq(inh, "GET", f"/api/arbeitsschutz/auftrag/{a['id']}")[1][:300])
s, b, _ = rq(inh, "GET", f"/papier/{a['id']}/werkstattauftrag"); print("papier", s, "Gefahrstoffe und Datenblätter" in b, "/api/arbeitsschutz/datei/" in b)
s, b, _ = rq(inh, "GET", f"/papier/{a['id']}/montageauftrag"); print("montage", s, "digital im Rapport" in b, "Unterschrift Auftraggeber" in b)
# neue Unterweisung für Max
uw = J(rq(inh, "POST", "/api/arbeitsschutz/unterweisungen", {"thema_ids": [3], "mitarbeiter_ids": [1, 2]})[1]); print("uw", uw.get("id"))
def T(o, m, p, d=None): return rq(o, m, p, d)[0]
o = {}
for lg in ("werk", "max", "buero"):
    o[lg] = cl(); rq(o[lg], "POST", "/api/anmeldung/anmelden", {"login": lg, "passwort": "passwort123"})
P = ["/api/arbeitsschutz/uebersicht", "/api/arbeitsschutz/gb", "/api/arbeitsschutz/gb/1", "/api/arbeitsschutz/ba", "/api/arbeitsschutz/verbandbuch", "/api/arbeitsschutz/datei/2",
     "/druck/arbeitsschutz/ba/1", "/druck/arbeitsschutz/ba/2", "/druck/arbeitsschutz/gb/1", "/druck/arbeitsschutz/notfall", "/api/arbeitsschutz/gefahrstoff/1", f"/api/arbeitsschutz/auftrag/{a['id']}",
     "/druck/monatsbeleg/1/2026-10", "/druck/monatsbeleg/2/2026-10", "/api/stempel/unterschriften", f"/api/stempel/unterweisung/{uw['id']}", "/api/arbeitsschutz/qualifikationen"]
for lg in o:
    print(lg, {p.replace("/api/arbeitsschutz", "AS"): T(o[lg], "GET", p) for p in P})
    print("  schreiben", {
        "gb PUT": T(o[lg], "PUT", "/api/arbeitsschutz/gb/1", {"bemerkung": "x"}),
        "gb frei": T(o[lg], "POST", "/api/arbeitsschutz/gb/1/freigeben", {"name": "x", "png": PNG}),
        "vb POST": T(o[lg], "POST", "/api/arbeitsschutz/verbandbuch", {"name": "x", "verletzung": "y"}),
        "uw sign TN": T(o[lg], "POST", f"/api/arbeitsschutz/unterweisungen/{uw['id']}/unterschreiben", {"mitarbeiter_id": 2, "name": "Azubi Jung", "png": PNG}),
        "uw sign UW": T(o[lg], "POST", f"/api/arbeitsschutz/unterweisungen/{uw['id']}/unterschreiben", {"rolle": "unterweiser", "name": "x", "png": PNG}),
        "gefahrstoff PUT": T(o[lg], "PUT", "/api/arbeitsschutz/gefahrstoff/1", {"bemerkung": "x"}),
        "mb sign AG": T(o[lg], "POST", "/api/monatsbeleg/1/unterschreiben", {"monat": "2026-10", "rolle": "arbeitgeber", "png": PNG}),
        "stempel uw": T(o[lg], "POST", f"/api/stempel/unterweisung/{uw['id']}", {"png": PNG}),
        "stempel mb": T(o[lg], "POST", "/api/stempel/monatsbeleg", {"monat": "2026-10", "png": PNG}),
        "stempel vb": T(o[lg], "POST", "/api/stempel/verbandbuch", {"verletzung": "Splitter"}),
    })
print("stempel AS max", rq(o["max"], "GET", "/api/stempel/unterschriften")[1][:400])
# Fuzz: kaputte Eingaben
for m, p, d in (("PUT", "/api/arbeitsschutz/gb/1", {"zeilen": "kaputt"}), ("PUT", "/api/arbeitsschutz/gb/1", {"zeilen": [{"m": "x"}, 5]}), ("PUT", "/api/arbeitsschutz/gb/1", {"intervall": "abc"}),
                ("POST", "/api/arbeitsschutz/gb", {"vorlage": "gibtsnicht"}), ("PUT", "/api/arbeitsschutz/ba/1", {"abschnitte": [1]}), ("POST", "/api/arbeitsschutz/dateien", {"material_id": 1, "dateiname": "x.exe", "daten": "AA"}),
                ("POST", "/api/arbeitsschutz/dateien", {"material_id": 999, "dateiname": "x.pdf", "daten": "QUFB"}), ("PUT", "/api/arbeitsschutz/gefahrstoff/1", {"signalwort": "Hallo"}),
                ("POST", "/api/arbeitsschutz/unterweisungen", {"thema_ids": "x"}), ("GET", "/api/arbeitsschutz/gb/999", None), ("GET", "/api/monatsbeleg/1/unterschriften?monat=x", None),
                ("POST", "/api/monatsbeleg/1/unterschreiben", {"monat": "2099-01", "png": PNG}), ("POST", "/api/arbeitsschutz/gb/1/freigeben", {"name": "x", "png": "data:image/png;base64,AAAA"}),
                ("GET", "/druck/arbeitsschutz/gb/999", None), ("GET", "/api/arbeitsschutz/datei/999", None), ("PUT", "/api/arbeitsschutz/organisation", {"organisation": {"bereiche": "x"}}),
                ("POST", "/api/arbeitsschutz/qualifikationen", {"art": "Ersthelfer"}), ("DELETE", "/api/arbeitsschutz/verbandbuch/1", None)):
    s, b, _ = rq(inh, m, p, d); print("fuzz", m, p, s, b[:90] if s >= 400 else "")
