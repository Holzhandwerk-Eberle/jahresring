import json
from playwright.sync_api import sync_playwright
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
X = '<img src=x onerror=window.XSS=1><script>window.XSS=2</script>"\''
rq(inh, "PUT", "/api/arbeitsschutz/gb/1", {"titel": X, "bereich": X, "beteiligte": X, "zeilen": [{"g": X, "m": [{"t": X, "status": "umsetzen", "wer": X, "bis": "2026-12-01"}]}]})
rq(inh, "PUT", "/api/arbeitsschutz/ba/2", {"titel": X, "abschnitte": {"anwendung": X, "stoff": X, "gefahren": X}})
rq(inh, "PUT", "/api/arbeitsschutz/themen/1", {"titel": X, "text": "## " + X + "\n" + X})
rq(inh, "PUT", "/api/arbeitsschutz/gefahrstoff/1", {"h_saetze": X, "bereich": X, "psa": X})
rq(inh, "PUT", "/api/arbeitsschutz/organisation", {"notfall": {"unfall": X}, "organisation": {"fasi": X, "bereiche": [X]}})
rq(inh, "POST", "/api/arbeitsschutz/verbandbuch", {"name": X, "verletzung": X, "hergang": X})
rq(inh, "POST", "/api/arbeitsschutz/qualifikationen", {"name": X, "art": "Ersthelfer", "bemerkung": X})
u = J(rq(inh, "POST", "/api/arbeitsschutz/unterweisungen", {"thema_ids": [1], "mitarbeiter_ids": [1], "titel": X, "anlass": X, "ort": X, "unterweiser": X})[1])
rq(inh, "PUT", "/api/werkzeuge/1", {"bezeichnung": X})
rq(inh, "PUT", "/api/mitarbeiter/1", {"vorname": X})
rq(inh, "POST", "/api/arbeitsschutz/gb", {"art": "maschine", "werkzeug_ids": [1], "titel": X})
seiten = ["#/arbeitsschutz", "#/arbeitsschutz/gb", "#/arbeitsschutz/gb/1", "#/arbeitsschutz/ba", "#/arbeitsschutz/ba/2", "#/arbeitsschutz/unterweisungen", "#/arbeitsschutz/unterweisungen/liste",
          "#/arbeitsschutz/unterweisungen/themen", f"#/arbeitsschutz/unterweisung/{u['id']}", "#/arbeitsschutz/thema/1", "#/arbeitsschutz/gefahrstoffe", "#/mat/1/sicherheit",
          "#/arbeitsschutz/notfall", "#/arbeitsschutz/nachweise", "#/auftrag/1/werkstatt", "#/start",
          "/druck/arbeitsschutz/gb/1", "/druck/arbeitsschutz/ba/2?entwurf=1", f"/druck/arbeitsschutz/unterweisung/{u['id']}", "/druck/arbeitsschutz/gefahrstoffverzeichnis", "/druck/arbeitsschutz/notfall",
          "/papier/1/werkstattauftrag", "/papier/1/materialsummen"]
treffer = []
with sync_playwright() as p:
    b = p.chromium.launch(); c = b.new_context(viewport={"width": 1400, "height": 900})
    c.request.post(U + "/api/anmeldung/anmelden", data={"login": "jonas", "passwort": "geheim123"})
    pg = c.new_page(); pg.on("dialog", lambda d: (treffer.append(("dialog", pg.url)), d.dismiss()))
    for s in seiten:
        pg.goto(U + ("/" + s if s.startswith("#") else s)); pg.wait_for_timeout(900)
        x = pg.evaluate("window.XSS")
        if x: treffer.append((s, x))
        if "img src=x" in pg.inner_text("body") or True: pass
    b.close()
print("XSS-Treffer:", treffer)
