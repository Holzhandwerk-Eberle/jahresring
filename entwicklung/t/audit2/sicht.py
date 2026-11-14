import json
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
c = cl(); rq(c, "POST", "/api/anmeldung/anmelden", {"login": "mita", "passwort": "geheim456"})
e = json.loads(rq(c, "GET", "/api/einstellungen")[1]); print(len(e), "Schlüssel:", " ".join(sorted(e))[:3000])
for k in ("kalkulation", "steuernummer", "firma_anschrift", "ustid", "status_automatik", "_https", "_netz", "arbeitszeit", "benutzer"): print(k, "=", json.dumps(e.get(k), ensure_ascii=False)[:300])
c = cl(); rq(c, "POST", "/api/anmeldung/anmelden", {"login": "werk", "passwort": "geheim456"})
for p in ("auftraege/1", "lieferanten/1", "kunden/2", "leitstand", "start", "suche?q=Geheim", "material/platten", "reste"):
    s, b, _ = rq(c, "GET", "/api/" + p); print("\n##", p, s, b[:700])
