import json
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim123", "passwort2": "geheim123", "firma": "T"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def P(p, d=None, m="POST"):
    s, b, _ = rq(inh, m, "/api/" + p, d)
    if s >= 400: print("!!", p, s, b[:200])
    return J(b)
P("einstellungen", {"bezug_eigen": [{"k": "griffe", "name": "Griffe", "einheit": "St.", "quelle": "position"}]}, "PUT")
k = P("kunden", {"kurzname": "B", "plz": "1", "ort": "x", "strasse": "y"})
a = P("auftraege", {"kunde_id": k["id"], "bezeichnung": "B"})
pos = P(f"auftraege/{a['id']}/positionen", {"text": "Schrank", "menge": 1})
P(f"positionen/{pos['id']}", {"zeitmodus": "taetigkeiten", "extras": {"bezug_eigen": {"griffe": 8}},
     "zeiten": [{"kst": "BANKRAUM", "name": "Griffe montieren", "gruppe": "Standard", "minuten": 3, "bezug": "x_griffe", "ruest": 0, "helfer": 0}]}, "PUT")
def stunden():
    d = P(f"positionen/{pos['id']}", m="GET")
    return d["bezug"].get("x_griffe"), json.dumps(d["position"].get("calc") or d["position"].get("rechnung") or {})[:0], P(f"auftraege/{a['id']}", m="GET")
v1 = stunden()
r1 = P(f"auftraege/{a['id']}/rechnen", m="GET") if False else None
erg1 = P(f"auftraege/{a['id']}/positionen", m="GET")
def std(e):
    print(json.dumps(e)[:100]) if not isinstance(e, dict) else None
    for p in (e.get("positionen", []) if isinstance(e, dict) else e):
        if p["id"] == pos["id"]:
            return json.dumps(p.get("calc") or p.get("rechnung") or {k: p[k] for k in p if k not in ("text",)})[:4000]
            return {k: v for k, v in p.items() if any(w in k for w in ("std", "stunden", "zeit", "lohn", "ep", "einzelpreis"))}
print("vorher", v1[0], std(erg1))
P("einstellungen", {"bezug_eigen": []}, "PUT")
erg2 = P(f"auftraege/{a['id']}/positionen", m="GET")
d2 = P(f"positionen/{pos['id']}", m="GET")
print("nachher", d2["bezug"].get("x_griffe"), std(erg2))
import re
print(re.findall(r'"(?:zeit_h|stunden|h_gesamt|lohn)": [0-9.]+', std(erg1))[:4], re.findall(r'"(?:zeit_h|stunden|h_gesamt|lohn)": [0-9.]+', std(erg2))[:4])
print("GLEICH" if std(erg1) == std(erg2) and d2["bezug"].get("x_griffe") else "ANDERS")
# Bezugsgröße einer vorhandenen Zeile lässt sich nicht ändern
kat = P("kalkvorgaben", m="GET")["katalog"]
t = next(x for x in kat if x.get("bezug") == "platte")
P(f"positionen/{pos['id']}", {"zeiten": [{"tid": t["id"], "kst": t["kst"], "name": t["name"], "gruppe": "Standard", "minuten": 1, "bezug": "platte", "ruest": 0, "helfer": 0}]}, "PUT")
P(f"positionen/{pos['id']}", {"zeiten": [{"tid": t["id"], "kst": t["kst"], "name": t["name"], "gruppe": "Inhaber", "minuten": 2, "bezug": "kante", "ruest": 0, "helfer": 0}]}, "PUT")
z = P(f"positionen/{pos['id']}", m="GET")["position"]["zeiten"][0]
print("Bezug bleibt", z["bezug"], "Minuten geändert", z["minuten"], z["gruppe"], "OK" if z["bezug"] == "platte" and z["minuten"] == 2 else "FEHL")
# eigene Bezugsgröße bleibt im Auftrag, auch wenn sie in den Einstellungen gelöscht wird
P("einstellungen", {"bezug_eigen": [{"k": "fronten", "name": "Fronten", "einheit": "St.", "quelle": "position"}]}, "PUT")
a2 = P("auftraege", {"kunde_id": k["id"], "bezeichnung": "C"})
pos2 = P(f"auftraege/{a2['id']}/positionen", {"text": "Küche", "menge": 1})
P(f"positionen/{pos2['id']}", {"zeitmodus": "taetigkeiten", "extras": {"bezug_eigen": {"fronten": 10}},
   "zeiten": [{"tid": t["id"], "kst": t["kst"], "name": t["name"], "gruppe": "Standard", "minuten": 6, "bezug": "x_fronten", "ruest": 0, "helfer": 0}]}, "PUT")
def h(aid, pid):
    r = P(f"auftraege/{aid}/positionen", m="GET")
    for p in (r.get("positionen", []) if isinstance(r, dict) else r):
        if p["id"] == pid:
            return (p.get("calc") or {}).get("stunden")
h1 = h(a2["id"], pos2["id"])
P("einstellungen", {"bezug_eigen": []}, "PUT")
h2 = h(a2["id"], pos2["id"])
d = P(f"positionen/{pos2['id']}", m="GET")
print("Stunden vorher/nachher", h1, h2, "Bezug", d["bezug"].get("x_fronten"), d["position"]["zeiten"][0]["bezug"], "OK" if h1 and h1 == h2 and d["bezug"].get("x_fronten") else "FEHL")
