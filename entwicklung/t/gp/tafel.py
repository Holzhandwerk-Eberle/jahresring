from playwright.sync_api import sync_playwright
fehler = []
with sync_playwright() as p:
    b = p.chromium.launch(); c = b.new_context(viewport={"width": 1400, "height": 900})
    c.request.post("http://127.0.0.1:8799/api/anmeldung/anmelden", data={"login": "jonas", "passwort": "geheim123"})
    pg = c.new_page()
    pg.on("console", lambda m: fehler.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: fehler.append(str(e)))
    for url in ["#/arbeitsschutz/unterweisung/1", "#/arbeitsschutz/thema/1"]:
        pg.goto("http://127.0.0.1:8799/" + url); pg.wait_for_timeout(1000)
        seiten = len(c.pages)
        pg.click("a[data-tafel]"); pg.wait_for_timeout(2500)
        n = pg.eval_on_selector_all(".as-tafel canvas", "e => e.map(c => c.width + 'x' + c.height)")
        print(url, "Canvas", n, "neue Fenster", len(c.pages) - seiten)
        pg.screenshot(path=f"/tmp/claude-0/t/gp/tafel_{url.split('/')[-2]}.png")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        print("offen nach Esc", pg.locator(".as-tafel").count())
    # Stempeluhr
    pg.goto("http://127.0.0.1:8799/stempel"); pg.wait_for_timeout(1200)
    print(pg.inner_text("body")[:200].replace("\n", " | "))
    b.close()
print("FEHLER", fehler)
