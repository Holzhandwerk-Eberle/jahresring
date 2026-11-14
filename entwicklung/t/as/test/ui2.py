from playwright.sync_api import sync_playwright
fehler = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for login, seiten, vp in (("werk", ["#/auftrag/1/werkstatt", "#/arbeitsschutz", "#/arbeitsschutz/gb/1", "#/arbeitsschutz/unterweisung/2"], (1400, 900)),
                              ("max", ["stempel"], (420, 860))):
        c = b.new_context(viewport={"width": vp[0], "height": vp[1]})
        c.request.post("http://127.0.0.1:8799/api/anmeldung/anmelden", data={"login": login, "passwort": "passwort123"})
        pg = c.new_page()
        pg.on("pageerror", lambda e: fehler.append(str(e)))
        pg.on("console", lambda m: fehler.append(m.text) if m.type == "error" else None)
        for i, s in enumerate(seiten):
            pg.goto("http://127.0.0.1:8799/" + s); pg.wait_for_timeout(1200)
            pg.screenshot(path=f"/tmp/claude-0/t/as/test/{login}{i}.png", full_page=True)
        if login == "max":
            pg.click("#mSig"); pg.wait_for_timeout(600); pg.screenshot(path="/tmp/claude-0/t/as/test/max1.png")
            pg.click("[data-uw]") if pg.query_selector("[data-uw]") else pg.click("[data-mo]"); pg.wait_for_timeout(800); pg.screenshot(path="/tmp/claude-0/t/as/test/max2.png", full_page=True)
            pg.click("#ueZu"); pg.click("#mSicher"); pg.wait_for_timeout(600); pg.screenshot(path="/tmp/claude-0/t/as/test/max3.png", full_page=True)
    b.close()
print(fehler)
