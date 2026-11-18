"""Version 151: Die Erinnerungen des Arbeitsschutzes auf der Startseite lassen sich unter Einstellungen › Programm
ausschalten – nur sie, kein anderer Hinweis. Sind sie aus und Mitarbeiter angelegt, erfährt der Inhaber auf der Startseite,
dass er sie einschalten soll. Erwartet eine frische Prüfinstanz."""
import json, sqlite3
from datetime import date, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:600]))
    if not bed: fehler.append(name)

inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
def anmelden(login, pw):
    c = cl(); rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": pw}); return c
start = lambda c=None: A("GET", "start", c=c).get("arbeitsschutz")
prot = lambda: [e["text"] for e in A("GET", "service/protokoll?art=einstellung").get("eintraege", [])]

print("== Vorgabe")
e = A("GET", "einstellungen")
ok("Vorgabe: eingeschaltet; Zahl der Mitarbeiter für den Hinweis am Schalter 0", e.get("start_arbeitsschutz") is True and e.get("_mitarbeiter") == 0, (e.get("start_arbeitsschutz"), e.get("_mitarbeiter")))
ok("Startseite: Erinnerungen an, kein Hinweis", start() == {"anzeigen": True, "mitarbeiter": 0}, start())
wz = A("POST", "werkzeuge", {"bezeichnung": "Formatkreissäge", "art": "Stationäre Maschine"})
ueb = A("GET", "arbeitsschutz/uebersicht")
ok("es gibt etwas zu erinnern (Maschine ohne Gefährdungsbeurteilung)", wz["_s"] == 200 and any(p["stufe"] in ("rot", "gelb") for p in ueb.get("punkte", [])), (wz, ueb.get("punkte")))
andere_vorher = {k: e.get(k) for k in ("_ort_warnung", "_sicherung_erinnerung")}
ok("zum Vergleich: die Erinnerung an die Datensicherung steht an", bool(e.get("_sicherung_erinnerung")), andere_vorher)

print("== ausschalten")
r = A("PUT", "einstellungen", {"start_arbeitsschutz": False})
ok("ausschalten wird gespeichert", r["_s"] == 200 and r.get("start_arbeitsschutz") is False and A("GET", "einstellungen").get("start_arbeitsschutz") is False, r.get("start_arbeitsschutz"))
ok("Startseite: Erinnerungen aus; ohne Mitarbeiter kein Hinweis", start() == {"anzeigen": False, "mitarbeiter": 0}, start())
ok("im Protokoll festgehalten", any("Erinnerungen des Arbeitsschutzes auf der Startseite ausgeschaltet" in t for t in prot()), prot()[:3])
ok("die Übersicht des Arbeitsschutzes zeigt die Punkte unverändert", A("GET", "arbeitsschutz/uebersicht").get("punkte") == ueb.get("punkte"))
e2 = A("GET", "einstellungen")
ok("alle anderen Hinweise der Startseite stehen unverändert an", {k: e2.get(k) for k in andere_vorher} == andere_vorher, {k: e2.get(k) for k in andere_vorher})
# Es gibt keinen weiteren Schalter: Erfundene Namen und die berechneten Hinweise selbst lassen sich nicht setzen
r = A("PUT", "einstellungen", {"start_sicherung": False, "start_update": False, "start_hinweise": False, "start_wiedervorlagen": False,
                               "_sicherung_erinnerung": "", "_ort_warnung": "", "_update": {}, "sicherung_erinnerung": False})
e3 = A("GET", "einstellungen")
ok("andere Hinweise lassen sich nicht ausschalten (kein solcher Schalter, berechnete Hinweise nicht überschreibbar)",
   {k: e3.get(k) for k in andere_vorher} == andere_vorher and not any(k in e3 for k in ("start_sicherung", "start_update", "start_hinweise", "start_wiedervorlagen", "sicherung_erinnerung")),
   [k for k in e3 if k.startswith("start_")])
c = sqlite3.connect(D + "/buero.db"); schl = [r[0] for r in c.execute("SELECT schluessel FROM einstellungen")]; c.close()
ok("in der Datenbank steht nur der eine Schalter, keiner der berechneten Hinweise", [k for k in schl if k.startswith("start_")] == ["start_arbeitsschutz"]
   and not any(k in schl for k in ("_sicherung_erinnerung", "_ort_warnung", "_update", "sicherung_erinnerung")), [k for k in schl if k.startswith(("start_", "_"))])
sd = A("GET", "start")
ok("die übrigen Kästen der Startseite werden weiter geliefert", all(k in sd for k in ("kennzahlen", "laufend", "termine", "ueberfaellig", "zahlungen_faellig", "angebote", "anfragen", "wiedervorlagen", "geburtstage", "beschaffung")), sorted(sd))

print("== Mitarbeiter angelegt")
A("POST", "mitarbeiter", {"vorname": "Jonas", "nachname": "Chef", "lohnart": "inhaber"})
ok("der Inhaber selbst zählt nicht als Mitarbeiter", start()["mitarbeiter"] == 0 and A("GET", "einstellungen").get("_mitarbeiter") == 0, start())
m1 = A("POST", "mitarbeiter", {"vorname": "Max", "nachname": "Werk", "lohnart": "minijob", "stundenlohn": 14.0, "eintritt": "2026-01-01"}); mid1 = m1.get("id") or m1.get("mitarbeiter", {}).get("id")
ok("ein Mitarbeiter angelegt: Hinweis für den Inhaber (Zahl 1)", start() == {"anzeigen": False, "mitarbeiter": 1} and A("GET", "einstellungen").get("_mitarbeiter") == 1, start())
m2 = A("POST", "mitarbeiter", {"vorname": "Nina", "nachname": "Neu", "lohnart": "stunde", "stundenlohn": 18.0, "eintritt": (date.today() + timedelta(days=20)).isoformat()}); mid2 = m2.get("id") or m2.get("mitarbeiter", {}).get("id")
ok("ein schon angelegter Mitarbeiter mit Eintritt in drei Wochen zählt mit", start()["mitarbeiter"] == 2, start())
A("PUT", f"mitarbeiter/{mid2}", {"aktiv": 0})
ok("ein nicht mehr aktiver Mitarbeiter zählt nicht", start()["mitarbeiter"] == 1, start())
A("PUT", f"mitarbeiter/{mid2}", {"aktiv": 1, "austritt": (date.today() - timedelta(days=3)).isoformat()})
ok("ein ausgetretener Mitarbeiter zählt nicht", start()["mitarbeiter"] == 1, start())

print("== andere Benutzer")
A("POST", "benutzer", {"name": "Berta Büro", "login": "berta", "passwort": "Pruefung#2026", "rolle": "buero"})
A("POST", "benutzer", {"name": "Willi Werkstatt", "login": "willi", "passwort": "Pruefung#2026", "rolle": "werkstatt"})
A("POST", "benutzer", {"name": "Max", "login": "max", "passwort": "246813", "rolle": "mitarbeiter", "mitarbeiter_id": mid1})
bu, we, ma = anmelden("berta", "Pruefung#2026"), anmelden("willi", "Pruefung#2026"), anmelden("max", "246813")
eb, ew = A("GET", "einstellungen", c=bu), A("GET", "einstellungen", c=we)
ok("Büro: Schalter kommt an, Erinnerungen aus, kein Hinweis zum Einschalten (das kann nur der Inhaber)", eb.get("start_arbeitsschutz") is False and "_mitarbeiter" not in eb and start(bu) == {"anzeigen": False, "mitarbeiter": 0}, (eb.get("start_arbeitsschutz"), eb.get("_mitarbeiter"), start(bu)))
ok("Werkstatt (gekürzte Einstellungen): der Schalter kommt trotzdem an", ew.get("start_arbeitsschutz") is False and "firma_anschrift" not in ew and "_mitarbeiter" not in ew, sorted(ew)[:8])
r = A("PUT", "einstellungen", {"start_arbeitsschutz": True}, c=bu)
ok("Büro kann den Schalter nicht umlegen", r["_s"] == 403 and A("GET", "einstellungen").get("start_arbeitsschutz") is False, r)
r = A("PUT", "einstellungen", {"start_arbeitsschutz": True}, c=we)
ok("Werkstatt kann den Schalter nicht umlegen", r["_s"] == 403 and A("GET", "einstellungen").get("start_arbeitsschutz") is False, r)
# Für die Beschäftigten selbst ändert der Schalter nichts: Sicherheit und Unterweisungen in der Stempeluhr
s1 = A("GET", "stempel/unterschriften", c=ma)
A("PUT", "einstellungen", {"start_arbeitsschutz": True})
s2 = A("GET", "stempel/unterschriften", c=ma)
ok("Stempeluhr des Mitarbeiters (Sicherheit, offene Unterweisungen): vom Schalter unberührt", s1["_s"] == 200 and s1 == s2, (s1.get("_s"), list(s1)[:6]))

print("== wieder einschalten")
ok("eingeschaltet: Startseite ohne Hinweis, Erinnerungen an", start() == {"anzeigen": True, "mitarbeiter": 0} and start(bu) == {"anzeigen": True, "mitarbeiter": 0}, (start(), start(bu)))
ok("im Protokoll festgehalten", any("Erinnerungen des Arbeitsschutzes auf der Startseite eingeschaltet" in t for t in prot()), prot()[:3])
pr = A("GET", "service/protokoll?voll=1").get("pruefung") or {}
ok("Protokoll stimmt", pr.get("ok") is True, pr)
# ungewöhnliche Werte: nur das ausdrückliche „aus“ schaltet aus
for wert, erwartet in ((0, True), ("", True), (None, True), ("false", True), (False, False), (True, True)):
    A("PUT", "einstellungen", {"start_arbeitsschutz": wert})
    ok(f"Wert {wert!r}: Erinnerungen {'an' if erwartet else 'aus'}", start()["anzeigen"] is erwartet, start())
print("FEHLER:", fehler)
