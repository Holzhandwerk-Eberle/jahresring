import sys, json
from playwright.sync_api import sync_playwright
seiten = ["#/arbeitsschutz", "#/arbeitsschutz/gb", "#/arbeitsschutz/gb/1", "#/arbeitsschutz/gb/2", "#/arbeitsschutz/ba", "#/arbeitsschutz/ba/1", "#/arbeitsschutz/ba/2",
          "#/arbeitsschutz/unterweisungen", "#/arbeitsschutz/unterweisungen/liste", "#/arbeitsschutz/unterweisungen/themen", "#/arbeitsschutz/unterweisung/1", "#/arbeitsschutz/thema/1",
          "#/arbeitsschutz/gefahrstoffe", "#/mat/1/sicherheit", "#/arbeitsschutz/notfall", "#/arbeitsschutz/nachweise", "#/start", "#/personal/beleg/1/2026-10"] + sys.argv[1:]
fehler = []
with sync_playwright() as p:
    b = p.chromium.launch(); c = b.new_context(viewport={"width": 1400, "height": 900})
    c.request.post("http://127.0.0.1:8799/api/anmeldung/anmelden", data={"login": "jonas", "passwort": "geheim123"})
    pg = c.new_page()
    pg.on("console", lambda m: fehler.append((pg.url, m.text)) if m.type == "error" else None)
    pg.on("pageerror", lambda e: fehler.append((pg.url, str(e))))
    for i, s in enumerate(seiten):
        pg.goto("http://127.0.0.1:8799/" + s); pg.wait_for_timeout(900)
        t = pg.inner_text("#inhalt")[:160].replace("\n", " | ")
        print(s, "→", t)
        pg.screenshot(path=f"/tmp/claude-0/t/as/test/ui{i}.png", full_page=True)
    b.close()
print("FEHLER", fehler)
