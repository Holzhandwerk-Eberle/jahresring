"""Zahlungsplan: Lieferzeit als Zahl oder Spanne („4-6“) – Satz im Beleg, Stichtag für die Anzahlung, Eingabeprüfung."""
import json, sys, re
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
if len(sys.argv) > 1: U = sys.argv[1]
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:400]))
    if not bed: fehler.append(name)
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None):
    s, b, _ = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    return j
def seite(bid):
    s, b, _ = rq(inh, "GET", f"/druck/{bid}"); return re.sub(r"<[^>]+>", " ", b)
k = A("POST", "kunden", {"kurzname": "Muster, Max", "nachname": "Muster"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Garderobe"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Garderobe"}); pid = po.get("id") or po["position"]["id"]
A("PUT", f"positionen/{pid}", {"einzelpreis": 1000, "preis_manuell": 1, "menge": 1})
b = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"}); bid = b["id"]
A("PUT", f"belege/{bid}", {"datum": "2026-11-17", "druck": {"konditionen": "plan", "plan_anzahlung": 45, "plan_rest": 10}})
t = seite(bid); ok("ohne Lieferzeit: kein Liefersatz", "45 % Anzahlung" in t and "Lieferung ca." not in t, t[-600:])
r = A("PUT", f"belege/{bid}", {"druck": {"plan_wochen": "4-6"}}); ok("Spanne 4-6 wird angenommen", r["_s"] == 200 and A("GET", f"belege/{bid}")["druck"].get("plan_wochen") == "4-6", r)
t = seite(bid); ok("Satz mit Spanne im Beleg, auch ohne geplante Ausführung", "Lieferung ca. 4 bis 6 Wochen nach Eingang der Anzahlung" in t and "Ausführung ca." not in t, t[-600:])
for ein, soll, satz in (("4–6", "4-6", "4 bis 6 Wochen"), ("4 bis 6", "4-6", "4 bis 6 Wochen"), ("6-4", "4-6", "4 bis 6 Wochen"), ("5", 5, "ca. 5 Wochen"), (8, 8, "ca. 8 Wochen"), ("4,5", 4.5, "ca. 4,5 Wochen"), ("2-2", 2, "ca. 2 Wochen")):
    A("PUT", f"belege/{bid}", {"druck": {"plan_wochen": ein}}); ist = A("GET", f"belege/{bid}")["druck"].get("plan_wochen"); t = seite(bid)
    ok(f"Eingabe {ein!r} → gespeichert {soll!r}, Satz „{satz}“", ist == soll and satz in t, (ist, t[-300:]))
r = A("PUT", f"belege/{bid}", {"druck": {"plan_wochen": "bald"}}); ok("Unsinn wird abgelehnt statt still verworfen", r["_s"] == 400 and "Spanne" in r.get("fehler", ""), r)
ok("… und der alte Wert bleibt", A("GET", f"belege/{bid}")["druck"].get("plan_wochen") == 2)
A("PUT", f"belege/{bid}", {"druck": {"plan_wochen": ""}}); t = seite(bid); ok("leer: Satz entfällt wieder", "Lieferung ca." not in t)
# mit geplanter Ausführung: Stichtag der Anzahlung rechnet mit der längeren Lieferzeit
A("PUT", f"auftraege/{a['id']}", {"plan_von": "2027-02-01", "plan_bis": "2027-02-12"}); A("POST", f"belege/{bid}/aktualisieren", {})
A("PUT", f"belege/{bid}", {"druck": {"plan_wochen": "4-6"}}); t = seite(bid)
ok("mit geplanter Ausführung: „bei Anzahlung bis“ = Beginn − 6 Wochen (21.12.2026)", "bei Anzahlung bis" in t and "21.12.2026" in t, [x for x in t.split("  ") if "Anzahlung" in x][:4])
print("FEHLER:", fehler); sys.exit(1 if fehler else 0)
