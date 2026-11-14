import sys, os, shutil, json
P = "/tmp/claude-0/t/az/app"
shutil.rmtree(P, ignore_errors=True)
shutil.copytree("/home/claude/eberle-buero", P, ignore=shutil.ignore_patterns("daten", "__pycache__"))
sys.path.insert(0, P); os.chdir(P)
import app, personal
app.init_db()
with app.verbindung() as con:
    app.api("PUT", ["einstellungen"], {}, {"sollplaene": [
        {"name": "38 Stunden flexibel", "regelung": "flexibel", "tage": [7.6]*5 + [0, 0], "max_woche": 43, "max_tag": 0},
        {"name": "40 Stunden fix", "regelung": "fix", "tage": [8]*5 + [0, 0]}],
        "feiertage_wahl": {"heiligabend": True}, "frei_wahl": {"silvester": True, "rosenmontag": True},
        "tage_eigene": [{"name": "Betriebsausflug", "datum": "17.07", "art": "frei"}]})
    pl = app.einstellungen(con)["sollplaene"]; print([(p["id"], p["name"]) for p in pl])
    ids = []
    for i, p in enumerate(pl):
        m = personal.mitarbeiter_speichern(con, None, {"vorname": p["name"][:5], "nachname": "Test", "lohnart": "stunde", "eintritt": "2026-01-01",
                                                      "modelle": [{"ab": "", "plan": p["id"], "tage": [], "urlaub": 30}]})
        ids.append(m["id"]); print("modell", m["modelle"])
        for tag in ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"]:
            personal.zeit_speichern(con, {"mitarbeiter_id": m["id"], "datum": tag, "beginn": "07:00", "ende": "16:00"})
        personal.zeit_speichern(con, {"mitarbeiter_id": m["id"], "datum": "2026-11-01", "beginn": "08:00", "ende": "11:00"})
        personal.zeit_speichern(con, {"mitarbeiter_id": m["id"], "datum": "2026-12-24", "beginn": "08:00", "ende": "10:00"})
    con.commit()
    for mid in ids:
        for mon in ("2026-10", "2026-11", "2026-12"):
            d = personal.monat_daten(con, mid, mon)
            print(mid, mon, "soll", d["summe"]["soll"], "ft", d["summe"]["feiertag"], "zuschl", [(z["name"], z["prozent"], z["stunden"]) for z in d["zuschlaege"]])
    d = personal.monat_daten(con, ids[0], "2026-12")
    for t in d["tage"]:
        if t["datum"] in ("2026-12-24", "2026-12-31"): print(t["datum"], t["feiertag"], "soll", t["soll"], "frei", t["frei"], "bez", t["bezahlt_ft"], t.get("feiertag_std"))
    print("Juli", [(t["datum"], t["feiertag"], t["soll"]) for t in personal.monat_daten(con, ids[0], "2026-07")["tage"] if t["feiertag"]])
    print("Feb", [(t["datum"], t["feiertag"]) for t in personal.monat_daten(con, ids[0], "2026-02")["tage"] if t["feiertag"]])
    html = personal.monatsbeleg_html(con, ids[1], "2026-10", "Firma")
    print("Beleg", "Zuschlagspflichtige" in html, "Überstunden Arbeitstag (25 %)" in html)
    # Plan ändern → Modell zieht nach
    pl[1]["tage"] = [7.5]*5 + [0, 0]
    app.api("PUT", ["einstellungen"], {}, {"sollplaene": pl})
    print("nachgezogen", personal.laden(con, ids[1])["modelle"][0]["tage"])
    print(app.api("GET", ["mitarbeiter", "arbeitszeit"], {"jahr": "2026"}, None)["vorschau"][:4])
