import sys, os, time, json
P = "/tmp/claude-0/t/perf/app"; sys.path.insert(0, P); os.chdir(P)
import app
t = time.time(); app.init_db(); print("init_db %.2fs" % (time.time() - t))
con = app.verbindung()
for tab in ("kunden", "auftraege", "positionen", "belege", "zahlungen", "lieferanten", "protokoll", "termine", "material", "lagerbuchungen", "zeiten", "anhaenge", "offene_posten"):
    try: print(tab, con.execute(f"SELECT COUNT(*) FROM {tab}").fetchone()[0], end=" | ")
    except Exception as x: print(tab, "?", end=" | ")
print()
aid = con.execute("SELECT auftrag_id FROM positionen GROUP BY auftrag_id ORDER BY COUNT(*) DESC LIMIT 1 OFFSET 20").fetchone()[0]
kid = con.execute("SELECT kunde_id FROM auftraege GROUP BY kunde_id ORDER BY COUNT(*) DESC").fetchone()[0]
bid = con.execute("SELECT id FROM belege ORDER BY id DESC").fetchone()[0]
lid = (con.execute("SELECT lieferant_id FROM zahlungen GROUP BY lieferant_id ORDER BY COUNT(*) DESC").fetchone() or [1])[0]
tests = [["start"], ["statistik"], ["arbeitsschutz", "uebersicht"], ["arbeitsschutz", "matrix"], ["arbeitsschutz", "gb"], ["auftraege"], ["auftraege", str(aid)], ["auftraege", str(aid), "positionen"], ["auftraege", str(aid), "belege"], ["auftraege", str(aid), "auswertung"], ["auftraege", str(aid), "sollist"], ["auftraege", str(aid), "historie"],
         ["kunden"], ["kunden", str(kid)], ["kunden", str(kid), "statistik"], ["belege"], ["belege", str(bid)], ["offeneposten"], ["mahnwesen"], ["leitstand"], ["kalender"], ["lieferanten"], ["lieferanten", str(lid)], ["zahlungen"], ["zahlungsstatistik"],
         ["material", "holzwerkstoffe"], ["material", "beschlaege"], ["material", "statistik"], ["lager"], ["suche"], ["einstellungen"], ["service", "protokoll"], ["mitarbeiter"], ["zeiten"], ["lohn"], ["projekte"], ["briefe"], ["reste"], ["werkzeuge"], ["zahlungseingaenge"], ["korrespondenz"]]
for tl in tests:
    q = {"jahr": "2026", "q": "Müller", "monat": "2026-11", "status": ""} if tl[0] in ("suche", "statistik", "zeiten", "lohn") else {}
    try:
        s = time.time(); r = app.api("GET", tl, q, None); d = time.time() - s
        n = len(json.dumps(r, default=str))
        print(("LANGSAM " if d > 0.5 else "        ") + "%-34s %6.0f ms %8.0f kB" % ("/".join(tl), d * 1000, n / 1000))
    except Exception as x: print("   FEHLER %-30s %s" % ("/".join(tl), str(x)[:80]))
t = time.time(); r = app.belege_pruefen(con); print("belege_pruefen %.2fs" % (time.time() - t))
