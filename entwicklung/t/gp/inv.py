import json, threading
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas Inhaber", "login": "jonas", "passwort": "geheim123", "passwort2": "geheim123", "firma": "Testbetrieb"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def P(pfad, d=None, m="POST", o=None):
    s, b, _ = rq(o or inh, m, "/api/" + pfad, d)
    if s >= 400: print("  !!", m, pfad, s, b[:200])
    return J(b)
mat = P("material", {"kategorie": "beschlaege", "nummer": "B-TST-1", "bezeichnung": "Testplatte", "ek_preis": 10, "einheit": "m²"})
print("mat", mat.get("id"), mat.get("bestand"))
k = P("kunden", {"name": "Kunde", "kurzname": "Kunde"}); a = P("auftraege", {"kunde_id": k["id"], "bezeichnung": "Test"})
P("lager", {"material_id": mat["id"], "menge": 10, "art": "zugang", "preis": 10})
ak = P("auftragskosten", {"auftrag_id": a["id"], "material_id": mat["id"], "menge": 3, "lager_abgang": 1})
P("lager", {"material_id": mat["id"], "menge": 7, "art": "inventur"})
print("loeschen", P(f"auftragskosten/{ak['id']}", m="DELETE"))
ak2 = P("auftragskosten", {"auftrag_id": a["id"], "material_id": mat["id"], "menge": 2, "lager_abgang": 1})
print("loeschen2", P(f"auftragskosten/{ak2['id']}", m="DELETE"))
m2 = P(f"material/{mat['id']}", m="GET"); bew = P(f"lager?material_id={mat['id']}", m="GET")
print("Bestand nach Inventur 7 und Löschen der Entnahme:", m2["bestand"], "Bewegungen", [(b["art"], b["menge"]) for b in bew], "Summe", sum(b["menge"] for b in bew))
# parallele Festschreibung
P(f"auftraege/{a['id']}/positionen", {"text": "Schrank", "menge": 1, "einheit": "Stk.", "einzelpreis": 1000, "preis_manuell": 1})
ids = [P(f"auftraege/{a['id']}/belege", {"art": "rechnung"})["id"] for i in range(8)]
erg = {}
def fest(i):
    o = cl(); o.cookies = inh.cookies if hasattr(inh, "cookies") else None
    s, b, _ = rq(inh, "POST", f"/api/belege/{i}/festschreiben", {})
    erg[i] = (s, J(b).get("beleg", J(b)).get("nummer"))
th = [threading.Thread(target=fest, args=(i,)) for i in ids]
[t.start() for t in th]; [t.join() for t in th]
print("parallel:", sorted(erg.values(), key=str))
th = [threading.Thread(target=lambda i=i: erg.__setitem__(i, rq(inh, "POST", f"/api/belege/{i}/storno", {})[:2])) for i in ids[:4]]
[t.start() for t in th]; [t.join() for t in th]
print("storno:", [(erg[i][0], J(erg[i][1]).get("beleg", {}).get("nummer")) for i in ids[:4]])
