import json, re, sys
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def streng(t):
    try: json.loads(t, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c))); return "gültig"
    except ValueError as f: return f"UNGÜLTIG für Browser ({f})"
s, t, _ = rq(inh, "POST", "/api/kunden", {"kurzname": "Inf-Test", "plz": "88069", "ort": "Tettnang"}); k = J(t)
s, t, _ = rq(inh, "POST", "/api/auftraege", {"kunde_id": k["id"], "bezeichnung": "Inf"}); a = J(t)
s, t, _ = rq(inh, "POST", f"/api/auftraege/{a['id']}/positionen", {"text": "Pos"}); po = J(t); pid = po.get("id") or po["position"]["id"]
r = urllib.request.Request(U + f"/api/positionen/{pid}", method="PUT", data=b'{"einzelpreis": 1e999, "preis_manuell": 1, "menge": 1}', headers={"Content-Type": "application/json"})
x = inh.open(r); t = x.read().decode(); print("PUT-Antwort:", streng(t), re.findall(r'"[a-z_]+": (?:-?Infinity|NaN)', t)[:6])
for p in (f"/api/auftraege/{a['id']}", f"/api/auftraege/{a['id']}/positionen", f"/api/auftraege/{a['id']}/kalk", "/api/auftraege", "/api/start", f"/api/kunden/{k['id']}"):
    s, t, _ = rq(inh, "GET", p); print("  %-34s %s %s %s" % (p, s, streng(t), re.findall(r'"[a-z_]+": (?:-?Infinity|NaN)', t)[:4]))
s, t, _ = rq(inh, "POST", f"/api/auftraege/{a['id']}/belege", {"art": "angebot"}); b = J(t); print("Angebot:", s, streng(t), t[:160])
if b.get("id"):
    s, t, _ = rq(inh, "GET", f"/druck/{b['id']}"); print("Druck:", s, re.findall(r"(?:inf|nan)[^<]{0,20}", t)[:4])
    s, t, _ = rq(inh, "GET", "/api/belege"); print("Belegliste:", s, streng(t))
# aufräumen: Preis zurück
rq(inh, "PUT", f"/api/positionen/{pid}", {"einzelpreis": 10, "preis_manuell": 1, "menge": 1})
