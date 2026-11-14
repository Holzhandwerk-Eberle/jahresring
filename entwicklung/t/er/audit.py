import sys, os, shutil, json, time, re
P = "/tmp/claude-0/t/er/app"
shutil.rmtree(P, ignore_errors=True)
shutil.copytree("/home/claude/eberle-buero", P, ignore=shutil.ignore_patterns("daten", "__pycache__"))
sys.path.insert(0, P); os.chdir(P)
import app, erechnung, epruefung
app.init_db()
print("Prüfer", epruefung.verfuegbar())
ERG = []
def pr(name, bid, con, xr=False):
    b = app.beleg_laden(con, bid)
    try:
        t0 = time.time(); x = erechnung.cii_xml(b, xr, app.auftrag_kunde(con, b["auftrag_id"])); dt = time.time() - t0
    except Exception as f:
        print(f"[{name}] XML-FEHLER: {f}"); return None
    e = epruefung.pruefen(x)
    msgs = [f'{m["regel"]}: {m["text"][:150]}' for s in e["schritte"] for m in s.get("meldungen", [])]
    s = b["daten"]["summen"]
    gp = re.search(rb"<ram:GrandTotalAmount>([^<]+)", x).group(1).decode(); due = re.search(rb"<ram:DuePayableAmount>([^<]+)", x).group(1).decode()
    print(f"[{name}] gueltig={e.get('gueltig')} brutto Beleg={s['brutto']} XML={gp} zahl={due} {dt*1000:.0f}ms", *msgs[:6], sep="\n   ")
    return x
with app.verbindung() as con:
    app.api("PUT", ["einstellungen"], {}, {"firma": "Muster & Söhne <GmbH>", "firma_inhaber": "Max Muster", "firma_anschrift": "Hauptstr. 1\n88069 Tettnang", "steuernummer": "12/345/67890",
                                           "ustid": "DE 123 456 789", "sepa_iban": "DE02 1203 0000 0000 2020 51", "sepa_bic": "BYLADEM1001", "firma_email": "a@b.de", "firma_telefon": "07542 1"})
    def kunde(**kw):
        d = {"kurzname": "K", "strasse": "Weg 2", "plz": "88045", "ort": "Friedrichshafen", "email1": "k@k.de"}; d.update(kw)
        return app.api("POST", ["kunden"], {}, d)["id"]
    def auftrag(kid, pos):
        aid = app.api("POST", ["auftraege"], {}, {"kunde_id": kid, "bezeichnung": "Test"})["id"]
        for p in pos:
            r = app.api("POST", ["auftraege", str(aid), "positionen"], {}, {"text": p.get("text", "Pos")})
            pid = r.get("id") or r["position"]["id"]
            app.api("PUT", ["positionen", str(pid)], {}, {k: v for k, v in p.items() if k != "text"} | {"preis_manuell": 1})
        con.commit(); return aid
    def rechnung(aid, art="rechnung", fest=True, **kw):
        bid = app.api("POST", ["auftraege", str(aid), "belege"], {}, {"art": art, **kw})["id"]; con.commit()
        if fest: app.beleg_festschreiben(con, bid); con.commit()
        return bid
    # 1 Einheiten + Nachkommastellen
    k1 = kunde(kurzname="Bau GmbH", firma="Bau GmbH", ustid="DE987654321")
    a1 = auftrag(k1, [dict(text="Schrank", menge=3, einheit="Stk.", einzelpreis=33.33), dict(text="Boden", menge=2.375, einheit="m²", einzelpreis=47.11),
                      dict(text="Leiste", menge=12.5, einheit="lfm", einzelpreis=9.99), dict(text="Montage", menge=7.25, einheit="Std.", einzelpreis=58),
                      dict(text="Kiste", menge=1, einheit="Kiste", einzelpreis=10), dict(text="Garnitur", menge=2, einheit="Garnitur", einzelpreis=5.5),
                      dict(text="Pauschale", menge=1, einheit="Pauschale", einzelpreis=100)])
    r1 = rechnung(a1); x1 = pr("Einheiten", r1, con)
    print("   Einheiten:", re.findall(rb'unitCode="(\w+)"', x1))
    pr("Einheiten XRechnung", r1, con, True)
    # 2 negative Position
    a2 = auftrag(k1, [dict(text="Schrank", menge=1, einzelpreis=1000), dict(text="Abzug Altholz", menge=1, einzelpreis=-50)])
    pr("negative Position", rechnung(a2), con)
    # 3 Rabatt + Skonto
    k3 = kunde(kurzname="Rabatt", rabatt=3, skonto=2, skontotage=10)
    a3 = auftrag(k3, [dict(text="Tisch", menge=1, einzelpreis=1234.56)])
    pr("Rabatt+Skonto", rechnung(a3), con); pr("Rabatt+Skonto XR", rechnung(a3), con, True)
    # 4 Brutto-Kunde
    k4 = kunde(kurzname="Privat", gruppe="Privatkunde", preise="brutto")
    a4 = auftrag(k4, [dict(text="Regal", menge=3, einzelpreis=84.03), dict(text="Hocker", menge=7, einzelpreis=13.45)])
    pr("Bruttokunde", rechnung(a4), con)
    # 5 Abschlag + Schluss
    a5 = auftrag(k1, [dict(text="Küche", menge=1, einzelpreis=10000)])
    ab = rechnung(a5, "abschlag", prozent=30); pr("Abschlag", ab, con)
    pr("Schlussrechnung", rechnung(a5), con)
    # 6 Sonderzeichen
    a6 = auftrag(k1, [dict(text="Tür \x0b mit & < > \" ' 😀 \x01 Steuerzeichen\nZweite Zeile", menge=1, einzelpreis=10)])
    pr("Steuerzeichen", rechnung(a6), con)
    # 7 Schweiz 0 %
    k7 = kunde(kurzname="Schweiz AG", firma="Schweiz AG", ust=0, plz="8000", ort="Zürich", land="Schweiz")
    a7 = auftrag(k7, [dict(text="Möbel", menge=1, einzelpreis=500)])
    pr("Schweiz 0 %", rechnung(a7), con)
    k7b = kunde(kurzname="Schweden", ust=0, plz="11122", ort="Stockholm", land="Schweden")
    x7b = pr("Schweden 0 %", rechnung(auftrag(k7b, [dict(text="Möbel", menge=1, einzelpreis=500)])), con)
    print("   Land Schweden →", re.findall(rb"<ram:CountryID>(\w+)", x7b))
    # 8 alternative/gesperrte Position
    a8 = auftrag(k1, [dict(text="A", menge=1, einzelpreis=100), dict(text="Alt", menge=1, einzelpreis=200, alternativ=1)])
    pr("Alternativposition", rechnung(a8), con)
    # 9 Storno, Gutschrift, Korrektur negativ
    st = app.beleg_stornieren(con, r1); con.commit(); pr("Storno", st["id"], con)
    g = rechnung(a1, "gutschrift", frei=[{"text": "Kulanz", "betrag": 99.99}], bezug_id=rechnung(a1)); pr("Gutschrift", g, con)
    kk = rechnung(a1, "korrektur", frei=[{"text": "Minderung", "betrag": -40}], bezug_id=r1); pr("Korrektur negativ", kk, con)
    # 10 Menge 0, Kunde ohne PLZ
    k10 = kunde(kurzname="OhnePLZ", plz="", ort="", strasse="")
    a10 = auftrag(k10, [dict(text="X", menge=0, einzelpreis=10), dict(text="Y", menge=1, einzelpreis=10)])
    pr("Menge 0 / ohne PLZ", rechnung(a10), con)
    # 11 Großauftrag
    a11 = auftrag(k1, [dict(text=f"Position {i} " + "Text " * 30, menge=(i % 7) + 0.5, einheit="m²", einzelpreis=17.37 + i) for i in range(400)])
    t0 = time.time(); r11 = rechnung(a11, fest=False); print("Großauftrag Beleg", round(time.time() - t0, 2), "s")
    con.commit(); t0 = time.time(); app.beleg_festschreiben(con, r11); con.commit(); print("festschreiben", round(time.time() - t0, 2), "s")
    t0 = time.time(); x11 = pr("400 Positionen", r11, con); print("   inkl. Prüfung", round(time.time() - t0, 2), "s", len(x11)//1024, "KB")
    # Roundtrip: eigenes ZUGFeRD-PDF wieder einlesen
    import eingangsrechnung as ein, xmlansicht
    from pypdf import PdfWriter
    w = PdfWriter(); w.add_blank_page(595, 842); w.write("/tmp/claude-0/t/er/leer.pdf")
    for name, bid in (("Einheiten", r1), ("Rabatt", None)):
        pass
    xr = erechnung.cii_xml(app.beleg_laden(con, r11), False)
    erechnung.zugferd_pdf("/tmp/claude-0/t/er/leer.pdf", xr, "/tmp/claude-0/t/er/rt.pdf", "R", "A")
    t0 = time.time(); e = ein.lesen(open("/tmp/claude-0/t/er/rt.pdf", "rb").read(), "rt.pdf", {}); dt = time.time() - t0
    print("Roundtrip 400 Pos", e["format"], e["rechnung"]["brutto"], len(e["zeilen"]), round(sum(z["netto"] for z in e["zeilen"]), 2), e["rechnung"]["netto"], f"{dt:.2f}s", e["zeilen"][0]["einheit"])
    a2x = erechnung.cii_xml(app.beleg_laden(con, app.api("POST", ["auftraege", str(a2), "belege"], {}, {"art": "rechnung"})["id"]), False)
    e2 = ein.lies_xml(a2x); print("negativ eingelesen", [(z["menge"], z["ep"], z["netto"]) for z in e2["zeilen"]])
    # Angriffe
    xxe = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]><rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">&x;</rsm:CrossIndustryInvoice>'
    lol = b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;"><!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]><Invoice>&c;</Invoice>'
    for n, x in (("XXE", xxe), ("Lachen", lol), ("UTF-16 XXE", xxe.decode().replace('encoding="UTF-8"', '').encode("utf-16"))):
        try: ein.lesen(x, "a.xml", {}); print(n, "GELESEN!")
        except ein.LeseFehler as f: print(n, "abgelehnt:", str(f)[:60])
        print("  prüfen:", epruefung.pruefen(x)["schritte"][0]["meldungen"][0]["text"][:50], "| ansicht:", epruefung.ansicht_html(x)[1], "| xmlansicht:", xmlansicht.pruefen(x)["pruefungen"][0]["text"][:40])
