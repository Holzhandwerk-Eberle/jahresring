from playwright.sync_api import sync_playwright
fehler = []
with sync_playwright() as p:
    b = p.chromium.launch(ignore_default_args=["--hide-scrollbars"]); c = b.new_context(viewport={"width": 1000, "height": 800})
    c.request.post("http://127.0.0.1:8799/api/anmeldung/anmelden", data={"login": "jonas", "passwort": "geheim123"})
    pg = c.new_page(); pg.on("pageerror", lambda e: fehler.append(str(e))); pg.on("console", lambda m: fehler.append(m.text) if m.type == "error" else None)
    for i, (r, w) in enumerate((("#/personal/lohn", 900), ("#/auftraege", 820), ("#/einstellungen/kalkulation/vorlagen", 1000), ("#/arbeitsschutz/unterweisungen", 700))):
        pg.set_viewport_size({"width": w, "height": 800})
        pg.goto("http://127.0.0.1:8799/" + r); pg.wait_for_timeout(1200)
        info = pg.evaluate("""() => [...document.querySelectorAll('.tab-scroll')].map(w => ({breit: w.scrollWidth, sicht: w.clientWidth, oben: !!(w.previousElementSibling && w.previousElementSibling.classList.contains('tab-oben') && w.previousElementSibling.classList.contains('an'))}))""")
        nav = pg.evaluate("() => { const n = document.querySelector('.lb-nav'); return {sw: n.scrollWidth, cw: n.clientWidth, voll: document.querySelector('#leiste').classList.contains('nav-voll'), pfeile: [...document.querySelectorAll('.lb-pfeil')].map(x => getComputedStyle(x).display)}; }")
        print(r, w, info[:4], nav)
        # Sync testen
        o = pg.query_selector(".tab-oben.an")
        if o:
            pg.evaluate("() => { const o = document.querySelector('.tab-oben.an'); o.scrollLeft = 120; }"); pg.wait_for_timeout(200)
            print("   sync:", pg.evaluate("() => { const o = document.querySelector('.tab-oben.an'); return [o.scrollLeft, o.nextElementSibling.scrollLeft]; }"))
        pg.screenshot(path=f"/tmp/claude-0/t/as/test/sc{i}.png")
    # Mausrad im Menü
    pg.set_viewport_size({"width": 900, "height": 700}); pg.goto("http://127.0.0.1:8799/#/start"); pg.wait_for_timeout(800)
    box = pg.query_selector(".lb-nav").bounding_box(); pg.mouse.move(box["x"] + 50, box["y"] + 20); pg.mouse.wheel(0, 300); pg.wait_for_timeout(300)
    print("rad scrollLeft", pg.evaluate("document.querySelector('.lb-nav').scrollLeft"))
    pg.click(".lb-pfeil >> nth=1"); pg.wait_for_timeout(600); print("pfeil", pg.evaluate("document.querySelector('.lb-nav').scrollLeft"))
    pg.goto("http://127.0.0.1:8799/#/arbeitsschutz"); pg.wait_for_timeout(900); print("aktiv sichtbar", pg.evaluate("(() => { const n=document.querySelector('.lb-nav').getBoundingClientRect(), a=document.querySelector('.lb-nav a.aktiv').getBoundingClientRect(); return a.left>=n.left-1 && a.right<=n.right+1; })()"))
    pg.screenshot(path="/tmp/claude-0/t/as/test/sc_nav.png")
    b.close()
print(fehler)
