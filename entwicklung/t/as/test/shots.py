import sys
from playwright.sync_api import sync_playwright
seiten = sys.argv[1:]
with sync_playwright() as p:
    b = p.chromium.launch(); c = b.new_context(viewport={"width": 1300, "height": 900})
    c.request.post("http://127.0.0.1:8799/api/anmeldung/anmelden", data={"login": "jonas", "passwort": "geheim123"})
    pg = c.new_page()
    for i, s in enumerate(seiten):
        pg.goto("http://127.0.0.1:8799" + s); pg.wait_for_timeout(500)
        pg.screenshot(path=f"/tmp/claude-0/t/as/test/shot{i}.png", full_page=True)
    b.close()
