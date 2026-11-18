"""Version 149, Personal: Stempelzeiten, die nicht im Augenblick ankommen, werden gekennzeichnet; zu alte und solche in
abgerechneten Monaten werden abgelehnt, ohne die Warteschlange des Handys aufzuhalten; Hinweise zu Ruhezeit, Mindestlohn und
Minijob-Grenze; Personalübersicht schnell. Erwartet eine frische Prüfinstanz."""
import json, sys, time, sqlite3
from datetime import date, datetime, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
sys.path.insert(0, "/home/claude/eberle-buero")
import personal
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:600]))
    if not bed: fehler.append(name)

print("== Grenzwerte (ohne Server)")
ok("Mindestlohn: 12,82 € (2025), 13,90 € (2026), 14,60 € (2027 und danach)", (personal.mindestlohn("2025-06-01"), personal.mindestlohn("2026-01-01"), personal.mindestlohn("2026-12-31"), personal.mindestlohn("2027-01-01"), personal.mindestlohn("2030-05-05")) == (12.82, 13.90, 13.90, 14.60, 14.60))
ok("Minijob-Grenze: 556 € (2025), 603 € (2026), 633 € (2027)", (personal.minijob_grenze("2025-03-01"), personal.minijob_grenze("2026-03-01"), personal.minijob_grenze("2027-03-01")) == (556, 603, 633), (personal.minijob_grenze("2025-03-01"), personal.minijob_grenze("2026-03-01"), personal.minijob_grenze("2027-03-01")))
m_ = {"lohnart": "minijob", "stundenlohn": 13.90, "gehalt": 0}
ok("Minijob 13,90 € × 45 h = 625,50 € im Jahr 2026: Hinweis auf die Grenze von 603 € und die höchste Stundenzahl (43,4)", any("603,00 €" in h and "43,4 Stunden" in h for h in personal.lohn_hinweise(m_, "2026-11", 45, 0)), personal.lohn_hinweise(m_, "2026-11", 45, 0))
ok("… bei 43 Stunden kein Hinweis", personal.lohn_hinweise(m_, "2026-11", 43, 0) == [], personal.lohn_hinweise(m_, "2026-11", 43, 0))
ok("Stundenlohn 13,00 € im Jahr 2026: unter dem Mindestlohn; 13,90 € nicht; im Jahr 2027 sind 13,90 € zu wenig", "Mindestlohn von 13,90 €" in " ".join(personal.lohn_hinweise({"lohnart": "stunde", "stundenlohn": 13.0, "gehalt": 0}, "2026-11", 160, 160)) and personal.lohn_hinweise({"lohnart": "stunde", "stundenlohn": 13.9, "gehalt": 0}, "2026-11", 160, 160) == [] and "14,60 €" in " ".join(personal.lohn_hinweise({"lohnart": "stunde", "stundenlohn": 13.9, "gehalt": 0}, "2027-01", 160, 160)))
ok("Gehalt 2.200 € bei 173 Sollstunden (12,72 €/h): Hinweis; Auszubildende und Inhaber: keiner", any("12,72 €" in h for h in personal.lohn_hinweise({"lohnart": "gehalt", "stundenlohn": 0, "gehalt": 2200}, "2026-11", 173, 173)) and personal.lohn_hinweise({"lohnart": "azubi", "stundenlohn": 5, "gehalt": 900}, "2026-11", 160, 160) == [], personal.lohn_hinweise({"lohnart": "gehalt", "stundenlohn": 0, "gehalt": 2200}, "2026-11", 173, 173))

inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
ma = A("POST", "mitarbeiter", {"vorname": "Max", "nachname": "Werk", "lohnart": "minijob", "stundenlohn": 13.0, "eintritt": "2026-01-01"}); mid_ = ma.get("id") or ma.get("mitarbeiter", {}).get("id")
A("POST", "benutzer", {"name": "Max", "login": "max", "passwort": "246813", "rolle": "mitarbeiter", "mitarbeiter_id": mid_})
max_ = cl(); s, _, _ = rq(max_, "POST", "/api/anmeldung/anmelden", {"login": "max", "passwort": "246813"})
ok("Mitarbeiter mit Stempeluhr-Zugang angemeldet", s == 200, s)
con = sqlite3.connect(D + "/buero.db", timeout=20); con.row_factory = sqlite3.Row
def zeiten(): return [dict(r) for r in con.execute("SELECT * FROM zeiten WHERE mitarbeiter_id=? ORDER BY datum, beginn", (mid_,))]
jetzt = datetime.now(); iso = lambda d: d.strftime("%Y-%m-%dT%H:%M")

print("== M2: Stempelzeiten")
# gestern: live gestempelt geht nicht nachzustellen – deshalb heute, mit Abstand zu Mitternacht unkritisch
r = A("POST", "stempel", {"aktion": "start", "zeit": iso(jetzt - timedelta(hours=3)), "client_id": "c1"}, c=max_)
ende1 = jetzt - timedelta(hours=1)
if ende1.date() != (jetzt - timedelta(hours=3)).date():   # nachts zwischen 1 und 3 Uhr: Ende noch auf den Vortag legen, sonst reicht die Stempelung über Mitternacht
    ende1 = ende1.replace(hour=0, minute=0) - timedelta(minutes=1)
r2 = A("POST", "stempel", {"aktion": "ende", "zeit": iso(ende1), "client_id": "c2"}, c=max_)
z = zeiten()
ok("Beginn vor 3 Stunden und Ende vor 1 Stunde nachgereicht: übernommen (Handy ohne Netz kommt vor)", r["_s"] == 200 and r2["_s"] == 200 and len(z) == 1 and z[0]["ende"], (r, r2, z))
ok("… und gekennzeichnet: Eingangszeit und Verzug in Minuten (rund 180)", z and z[0]["eingang"][:10] == jetzt.strftime("%Y-%m-%d") and 170 <= z[0]["spaet"] <= 190, z and (z[0]["eingang"], z[0]["spaet"]))
r = A("POST", "stempel", {"aktion": "start", "zeit": iso(jetzt - timedelta(minutes=4)), "client_id": "c3"}, c=max_); z = zeiten()
ok("im Augenblick gestempelt: ohne Kennzeichen", r["_s"] == 200 and len(z) == 2 and z[-1]["spaet"] == 0 and z[-1]["eingang"], z[-1:])
A("POST", "stempel", {"aktion": "ende", "zeit": iso(jetzt), "client_id": "c3e"}, c=max_)
alt = jetzt - timedelta(days=9)
r = A("POST", "stempel", {"ereignisse": [{"aktion": "start", "zeit": iso(alt.replace(hour=5, minute=0)), "client_id": "c4"}, {"aktion": "ende", "zeit": iso(alt.replace(hour=19, minute=30)), "client_id": "c5"},
                                          {"aktion": "start", "zeit": iso(jetzt + timedelta(minutes=1)), "client_id": "c6"}]}, c=max_)
erg = r.get("ergebnisse") or []; z = zeiten()
ok("Sammelübertragung mit zwei Buchungen von vor 9 Tagen und einer von jetzt: die alten werden abgelehnt, die neue übernommen (Warteschlange läuft weiter)",
   r["_s"] == 200 and [e.get("abgelehnt", False) for e in erg] == [True, True, False] and not any(x["datum"] == alt.strftime("%Y-%m-%d") for x in z) and len(z) == 3, (r["_s"], erg, [(x["datum"], x["beginn"]) for x in z]))
ok("der Hinweis nennt Tag, Uhrzeit, Grund und den Weg („im Büro nachtragen lassen“)", erg and "älter als 7 Tage" in erg[0]["hinweise"][0] and "05:00" in erg[0]["hinweise"][0] and "Büro" in erg[0]["hinweise"][0], erg[:1])
r = A("POST", "stempel", {"aktion": "start", "zeit": iso(alt.replace(hour=5, minute=0)), "client_id": "c4"}, c=max_)
ok("dieselbe Buchung noch einmal gesendet: gleiche Antwort, nichts doppelt", (r.get("ergebnisse") or [{}])[0].get("abgelehnt") is True and len(zeiten()) == 3, r.get("ergebnisse"))
A("POST", "stempel", {"aktion": "ende", "zeit": iso(jetzt + timedelta(minutes=2)), "client_id": "c6e"}, c=max_)
r = A("POST", "stempel", {"aktion": "start", "zeit": "2019-03-04T07:00", "client_id": "c7"}, c=max_)
ok("Zeit im Jahr 2019: abgelehnt", (r.get("ergebnisse") or [{}])[0].get("abgelehnt") is True and not any(x["datum"].startswith("2019") for x in zeiten()), r.get("ergebnisse"))
bz = A("GET", f"zeiten?mitarbeiter_id={mid_}&von={(jetzt - timedelta(days=12)).strftime('%Y-%m-%d')}&bis={jetzt.strftime('%Y-%m-%d')}"); bl = bz.get("liste") or bz.get("zeiten") or []
ok("das Büro bekommt Kennzeichen und Eingangszeit mitgeliefert", any(x.get("spaet") and x.get("eingang") for x in bl) and any(x.get("spaet") == 0 for x in bl), [(x.get("beginn"), x.get("spaet"), x.get("eingang")) for x in bl])

print("== abgerechneter Monat")
monat = jetzt.strftime("%Y-%m")
con.execute("INSERT INTO lohn (mitarbeiter_id, monat, brutto, netto, zahlungen, angelegt, geaendert) VALUES (?,?,?,?,?,?,?)", (mid_, monat, 500, 500, json.dumps({"netto": 1}), jetzt.isoformat(), jetzt.isoformat())); con.commit()
n0 = len(zeiten())
r = A("POST", "stempel", {"aktion": "start", "zeit": iso(jetzt + timedelta(minutes=3)), "client_id": "c8"}, c=max_); e8 = (r.get("ergebnisse") or [{}])[0]
ok("Stempelung in einen Monat, für den die Lohnzahlung schon angelegt ist: abgelehnt mit Begründung", e8.get("abgelehnt") is True and "abgerechneten Monat" in e8["hinweise"][0] and len(zeiten()) == n0, e8)
r = A("POST", "stempel/nachtrag", {"datum": jetzt.strftime("%Y-%m-%d"), "beginn": "06:00", "ende": "06:30"}, c=max_)
ok("eigener Nachtrag in diesen Monat: abgelehnt", r["_s"] == 400 and "abgerechnet" in r.get("fehler", ""), (r["_s"], r.get("fehler")))
zid = zeiten()[0]["id"]
r = A("PUT", f"zeiten/{zid}", {"notiz": "korrigiert"}, h={"X-Rueckfrage": "1"})
ok("Büro ändert eine Zeit in diesem Monat: Rückfrage statt stiller Änderung", r["_s"] == 409 and r.get("rueckfrage", "").startswith("lohnmonat-") and "Lohnzahlungen" in r.get("fehler", ""), (r["_s"], r.get("fehler"), r.get("rueckfrage")))
r = A("PUT", f"zeiten/{zid}", {"notiz": "korrigiert"}, h={"X-Rueckfrage": "1", "X-Bestaetigt": r.get("rueckfrage", "")})
ok("nach Bestätigung wird gespeichert", r["_s"] == 200 and zeiten()[0]["notiz"] == "korrigiert", (r["_s"], r.get("fehler")))
r = A("DELETE", f"zeiten/{zeiten()[-1]['id']}", None, h={"X-Rueckfrage": "1"})
ok("Löschen einer Zeit in diesem Monat: ebenfalls Rückfrage", r["_s"] == 409 and "Löschen" in r.get("fehler", ""), (r["_s"], r.get("fehler")))
con.execute("DELETE FROM lohn"); con.commit()

print("== M5: Ruhezeit, Mindestlohn, Minijob")
ma2 = A("POST", "mitarbeiter", {"vorname": "Rita", "nachname": "Ruhe", "lohnart": "minijob", "stundenlohn": 13.0, "eintritt": "2026-01-01"}); m2 = ma2.get("id") or ma2.get("mitarbeiter", {}).get("id")
mo = date.today().replace(day=1); wt = [mo + timedelta(i) for i in range(10) if (mo + timedelta(i)).weekday() < 4][:2]
while (wt[1] - wt[0]).days != 1: wt = [wt[1], wt[1] + timedelta(1)]
for datum, von, bis in ((wt[0], "10:00", "22:30"), (wt[1], "06:00", "12:00")):
    A("POST", "zeiten", {"mitarbeiter_id": m2, "datum": datum.isoformat(), "beginn": von, "ende": bis})
md = A("GET", f"mitarbeiter/{m2}/monat?monat={wt[0].strftime('%Y-%m')}"); tage_ = {t["datum"]: t for t in md.get("tage") or []}
if not tage_:
    s_, t_, _ = rq(inh, "GET", f"/druck/monatsbeleg/{m2}/{wt[0].strftime('%Y-%m')}"); hin = t_
else: hin = tage_.get(wt[0].isoformat(), {}).get("hinweis", "") + " | " + tage_.get(wt[1].isoformat(), {}).get("hinweis", "")
ok("12,5 Stunden Arbeit, danach nur 7,5 Stunden Pause bis zum nächsten Beginn: Hinweise „mehr als 10 h“ und „Ruhezeit nur 7,5 h (mindestens 11 h)“", "mehr als 10 h Arbeitszeit" in hin and "Ruhezeit nur 7,5 h (mindestens 11 h)" in hin, hin[-600:] if len(hin) > 600 else hin)
for i in range(4, 12):   # weitere Tage, damit der Minijob über die Grenze kommt: 8 × 8 h
    d = mo + timedelta(i)
    if d not in wt: A("POST", "zeiten", {"mitarbeiter_id": m2, "datum": d.isoformat(), "beginn": "08:00", "ende": "16:00"})
ll = A("GET", f"lohn?monat={mo.strftime('%Y-%m')}"); zr = next((x for x in ll.get("zeilen") or [] if x["mitarbeiter"]["id"] == m2), {})
ok("Lohnliste: Hinweis auf den Mindestlohn (13,00 € < 13,90 €) und auf die Minijob-Grenze", any("Mindestlohn" in h for h in zr.get("hinweise") or []) and any("Minijob-Grenze" in h for h in zr.get("hinweise") or []), zr.get("hinweise"))

print("== P2: Übersicht")
plan = [r[3] for r in con.execute("EXPLAIN QUERY PLAN SELECT COUNT(*), TOTAL(id) FROM zeiten WHERE mitarbeiter_id=? AND datum BETWEEN ? AND ?", (1, "2026-01-01", "2026-12-31"))]
plan2 = [r[3] for r in con.execute("EXPLAIN QUERY PLAN SELECT * FROM zeiten INDEXED BY zeiten_offen WHERE mitarbeiter_id=? AND ende IS NULL", (1,))]
ok("Zeitkonten lesen nur den Index, laufende Abschnitte haben einen eigenen", any("COVERING INDEX zeiten_ma_zeit" in p for p in plan) and any("zeiten_offen" in p for p in plan2), (plan, plan2))
z0 = time.time(); ml = A("GET", "mitarbeiter"); dauer = time.time() - z0
ok(f"Personalübersicht antwortet ({dauer * 1000:.0f} ms) mit Überstunden und Resturlaub", ml["_s"] == 200 and len(ml["liste"]) == 2 and all("ueberstunden" in x for x in ml["liste"]), ml["_s"])
con.close()
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
