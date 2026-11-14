import json, sys
sys.path.insert(0, "/tmp/claude-0/t/sec"); 
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
ids = json.load(open("/tmp/claude-0/t/sec/ids.json"))
for lg in ("max", "werk"):
    o = cl(); rq(o, "POST", "/api/anmeldung/anmelden", {"login": lg, "passwort": "passwort123"})
    s, b, _ = rq(o, "GET", "/api/einstellungen"); e = json.loads(b)
    print(lg, "Einstellungen-Schlüssel:", len(e), sorted(e)[:80])
    print("   heikel:", {k: str(e[k])[:40] for k in e if any(x in k for x in ("iban", "steuer", "mail", "satz", "lohn", "stunden", "gk", "wagnis", "passwort", "sicherung", "notfall", "kalk"))})
    s, b, _ = rq(o, "GET", "/api/vorlagen"); print("   vorlagen", s, len(b), b[:150])
    if lg == "max":
        for p_ in ("/api/stempel/zeiten?mitarbeiter_id=2", "/api/stempel", "/api/stempel/konto?mitarbeiter_id=2", "/api/stempel/auftraege"):
            s, b, _ = rq(o, "GET", p_); print("   ", p_, s, b[:260])
    else:
        s, b, _ = rq(o, "GET", f"/api/auftraege/{ids['auftrag']}/positionen"); print("   pos", s, b[:900])
        s, b, _ = rq(o, "GET", f"/api/auftraege/{ids['auftrag']}"); d = json.loads(b); print("   auftrag keys", sorted(d)[:60]); print("   summen" , {k: d[k] for k in d if "summ" in k or "netto" in k or "preis" in k})
o = cl(); rq(o, "POST", "/api/anmeldung/anmelden", {"login": "werk", "passwort": "passwort123"})
s, b, _ = rq(o, "GET", f"/api/auftraege/{ids['auftrag']}/positionen"); d = json.loads(b)
def zahlen(x, pf=""):
    if isinstance(x, dict):
        for k, v in x.items(): yield from zahlen(v, pf + "." + k)
    elif isinstance(x, list):
        for i, v in enumerate(x[:3]): yield from zahlen(v, pf)
    elif isinstance(x, (int, float)) and not isinstance(x, bool) and x not in (0, 1): yield pf, x
print("WERK Zahlen:", sorted(set(zahlen(d)))[:60])
s, b, _ = rq(o, "GET", "/api/einstellungen"); e = json.loads(b)
print("WERK einst Zahlen:", [k for k, v in zahlen(e)][:80])
print([k for k in e if k > "taetigkeit_listen"])
