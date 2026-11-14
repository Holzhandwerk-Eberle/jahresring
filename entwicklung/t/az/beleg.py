import sys, os, shutil, json
P = "/tmp/claude-0/t/az/app2"
shutil.rmtree(P, ignore_errors=True)
shutil.copytree("/home/claude/eberle-buero", P, ignore=shutil.ignore_patterns("daten", "__pycache__"))
sys.path.insert(0, P); os.chdir(P)
import app, erechnung, epruefung
app.init_db()
with app.verbindung() as con:
    app.api("PUT", ["einstellungen"], {}, {"firma": "Holzhandwerk Eberle", "firma_anschrift": "Hauptstr. 1\n88069 Tettnang", "steuernummer": "12/345/67890",
                                           "sepa_iban": "DE02120300000000202051", "firma_email": "a@b.de", "firma_telefon": "07542 1"})
    k = app.api("POST", ["kunden"], {}, {"kurzname": "Bau GmbH", "firma": "Bau GmbH", "strasse": "Weg 2", "plz": "88045", "ort": "Friedrichshafen", "gruppe": "Gewerbekunde", "ustid": "DE123456789"})
    a = app.api("POST", ["auftraege"], {}, {"kunde_id": k["id"], "bezeichnung": "Innenausbau"})
    aid = a["id"]
    app.api("POST", ["auftraege", str(aid), "positionen"], {}, {"text": "Einbauschrank", "menge": 1, "einheit": "Stk.", "einzelpreis": 1000, "preis_manuell": 1})
    con.commit()
    print("Varianten", [v["key"] for v in app.einstellungen(con)["beleg_varianten"]])
    r = app.api("POST", ["auftraege", str(aid), "belege"], {}, {"art": "rechnung", "variante": "v13b"})["id"]
    b = app.beleg_laden(con, r); print("13b", b["artname"], b["daten"].get("steuer"), b["netto"], b["ust"], b["brutto"])
    fb = app.beleg_festschreiben(con, r); con.commit(); print("fest", fb["nummer"], fb["op"])
    html = app.beleg_html(con, r) if hasattr(app, "beleg_html") else ""
    xml = erechnung.cii_xml(app.beleg_laden(con, r), False)
    xml = xml.decode() if isinstance(xml, bytes) else xml; print("AE" in xml, "VATEX-EU-AE" in xml)
    g = app.api("POST", ["auftraege", str(aid), "belege"], {}, {"art": "gutschrift", "frei": [{"text": "Kulanz Kratzer", "betrag": 100}], "bezug_id": r})["id"]
    gb = app.beleg_laden(con, g); print("Gutschrift", gb["artname"], gb["netto"], gb["brutto"], gb["daten"]["bezug"], gb["daten"].get("steuer"))
    gf = app.beleg_festschreiben(con, g); con.commit(); print("G fest", gf["nummer"], gf["op"]["offen"])
    xg = erechnung.cii_xml(app.beleg_laden(con, g), False); xg = xg.decode(); print("381" in xg, "Kulanz" in xg)
    rr = app.api("POST", ["auftraege", str(aid), "belege"], {}, {"art": "rechnung"})["id"]
    app.beleg_festschreiben(con, rr); con.commit()
    kk = app.api("POST", ["auftraege", str(aid), "belege"], {}, {"art": "korrektur", "frei": [{"text": "Mehraufwand Sockel", "betrag": 80}, {"text": "Minderung", "betrag": -30}], "bezug_id": rr})["id"]
    kb = app.beleg_laden(con, kk); print("Korrektur", kb["netto"], kb["ust"], kb["brutto"], kb["einleitung"][:80])
    app.api("PUT", ["belege", str(kk)], {}, {"frei": [{"text": "Mehraufwand Sockel", "betrag": 120}]})
    print("nach Änderung", app.beleg_laden(con, kk)["netto"])
    con.commit(); kf = app.beleg_festschreiben(con, kk); con.commit(); xk = erechnung.cii_xml(app.beleg_laden(con, kk), False).decode(); print("384" in xk, "InvoiceReferencedDocument" in xk)
    st = app.beleg_stornieren(con, g); print("Storno Gutschrift", st["brutto"], st["nummer"])
    try:
        app.api("POST", ["auftraege", str(aid), "belege"], {}, {"art": "korrektur", "frei": [{"text": "x", "betrag": 1}]})
    except Exception as e: print("ohne Bezug:", e)
    for bid in (r, g, kk):
        h = app.druck_html(con, bid)
        print("druck", bid, "Steuerschuldnerschaft" in h, "Gutschrift" in h, h.count("-100,00"))
    con.commit()
    if epruefung.verfuegbar():
        for n, x in (("13b", xml), ("gutschrift", xg), ("korrektur", xk)):
            e = epruefung.pruefen(x.encode()); print("Prüfung", n, json.dumps(e, ensure_ascii=False)[:600])
    else:
        print("epruefung nicht verfügbar")
    # Berichtigung ohne Betragsänderung
    rr2 = app.api("POST", ["auftraege", str(aid), "belege"], {}, {"art": "rechnung"})["id"]
    con.commit(); app.beleg_festschreiben(con, rr2); con.commit()
    orig = app.beleg_laden(con, rr2)
    be = app.api("POST", ["auftraege", str(aid), "belege"], {}, {"art": "korrektur", "modus": "berichtigen", "bezug_id": rr2})["id"]
    bb = app.beleg_laden(con, be)
    print("Berichtigung", bb["netto"], bb["daten"]["summen"]["netto"], orig["netto"], bb["einleitung"][:90], bb["druck"]["konditionen"], bb["druck"]["qr"])
    # Positionstext im Auftrag ändern, Preis gleich
    pos = con.execute("SELECT id FROM positionen WHERE auftrag_id=?", (aid,)).fetchone()["id"]
    app.api("PUT", ["positionen", str(pos)], {}, {"text": "Einbauschrank Eiche geölt"})
    app.api("POST", ["belege", str(be), "aktualisieren"], {}, {})
    print("Text neu:", app.beleg_laden(con, be)["daten"]["zeilen"][0]["text"])
    app.api("PUT", ["positionen", str(pos)], {}, {"einzelpreis": 1200, "preis_manuell": 1})
    try:
        app.api("POST", ["belege", str(be), "aktualisieren"], {}, {})
    except Exception as e2: print("Preis geändert:", str(e2)[:90])
    app.api("PUT", ["positionen", str(pos)], {}, {"einzelpreis": 1000, "preis_manuell": 1})
    con.commit()
    op_vor = con.execute("SELECT COUNT(*) FROM offene_posten").fetchone()[0]
    fb2 = app.beleg_festschreiben(con, be); con.commit()
    print("fest", fb2["nummer"], "OP neu:", con.execute("SELECT COUNT(*) FROM offene_posten").fetchone()[0] - op_vor, "Text nach Festschreiben:", fb2["daten"]["zeilen"][0]["text"])
    xb = erechnung.cii_xml(app.beleg_laden(con, be), False).decode()
    print("384", "<ram:TypeCode>384" in xb, "1190.00" in xb or "1190" in xb)
    e3 = epruefung.pruefen(xb.encode()); print("Prüfung Berichtigung", json.dumps(e3, ensure_ascii=False)[:300])
    h = app.druck_html(con, be); print("Druck: Summe im PDF", "1.190,00" in h, "ersetzt die Rechnung" in h)
    try: app.beleg_stornieren(con, be)
    except Exception as e4: print("Storno:", str(e4)[:60])
    print("Mail", app.mail_vorschlag(con, be)["betreff"] if hasattr(app, "mail_vorschlag") else "")
