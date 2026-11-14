import json, urllib.request, urllib.error, http.cookiejar, time, sys
U = "http://127.0.0.1:8799"
def cl():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), type("N", (urllib.request.HTTPRedirectHandler,), {"redirect_request": lambda *a, **k: None})())
def rq(o, m, p, d=None, h=None, roh=False):
    r = urllib.request.Request(U + p, method=m, data=json.dumps(d).encode() if d is not None else None, headers={"Content-Type": "application/json", **(h or {})})
    try:
        x = o.open(r, timeout=60); b = x.read(); return x.status, (b if roh else b.decode("utf-8", "replace")), dict(x.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)
inh = cl()
print("einrichten", rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim123", "passwort2": "geheim123"})[0])
s, b, hd = rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}); print("login", s, hd.get("Set-Cookie", "")[:0] + ";".join(hd.get("Set-Cookie", "").split(";")[1:]))
rq(inh, "PUT", "/api/einstellungen", {"firma": "Muster", "mail_passwort": "supergeheim", "mail_benutzer": "a@b.de", "mail_server": "smtp.x.de"})
k = json.loads(rq(inh, "POST", "/api/kunden", {"kurzname": "Kunde <img src=x onerror=window.XSS=1>", "strasse": "Weg 1", "plz": "88069", "ort": "Tettnang"})[1])
a = json.loads(rq(inh, "POST", "/api/auftraege", {"kunde_id": k["id"], "bezeichnung": "<script>window.XSS=1</script>Test"})[1])
p = json.loads(rq(inh, "POST", f"/api/auftraege/{a['id']}/positionen", {"text": "<img src=x onerror=window.XSS=2><script>window.XSS=3</script><b>fett</b>"})[1])
pid = p.get("id") or p["position"]["id"]; rq(inh, "PUT", f"/api/positionen/{pid}", {"einzelpreis": 100, "preis_manuell": 1})
bl = json.loads(rq(inh, "POST", f"/api/auftraege/{a['id']}/belege", {"art": "angebot"})[1])
rq(inh, "PUT", f"/api/belege/{bl['id']}", {"einleitung": "<p onclick=alert(1)>Hallo</p><script>window.XSS=4</script><iframe src=javascript:alert(1)></iframe><a href='javascript:alert(1)'>x</a>", "schluss": "<img src=x onerror=window.XSS=5>"})
m = json.loads(rq(inh, "POST", "/api/mitarbeiter", {"vorname": "Max", "nachname": "M"})[1]); m2 = json.loads(rq(inh, "POST", "/api/mitarbeiter", {"vorname": "Eva", "nachname": "E"})[1])
for lg, rolle, mid in (("max", "mitarbeiter", m.get("id")), ("werk", "werkstatt", None), ("buero", "buero", None)):
    s, b, _ = rq(inh, "POST", "/api/benutzer", {"name": lg, "login": lg, "passwort": "passwort123", "rolle": rolle, "mitarbeiter_id": mid}); 
    if s != 200: print("Benutzer", lg, s, b[:100])
# 1 Mailpasswort in GET?
s, b, _ = rq(inh, "GET", "/api/einstellungen"); print("Mailpasswort in GET:", "supergeheim" in b)
# 2 ohne Anmeldung
anon = cl()
PF = ["/api/kunden", "/api/einstellungen", f"/api/belege/{bl['id']}", f"/druck/{bl['id']}", f"/druck/{bl['id']}.pdf", "/api/benutzer", "/api/service/sicherung", "/api/mitarbeiter", "/api/zeiten", "/api/protokoll",
      "/papier/1/laufzettel", "/liste/lager", "/api/start", "/api/auftraege", "/api/zahlungen", "/api/lohn", "/api/vorlagen", "/api/nummernkreise", "/zuschnitt", "/api/logo", "/api/version",
      "/daten/eberle.db", "/../app.py", "/..%2f..%2fapp.py", "/%2e%2e/app.py", "/hilfe/..%2f..%2fapp.py", "/static/../app.py", "/api/service/datei/..%2f..%2feberle.db", "/api/bautagebuch/foto/..%2fx"]
print("--- ohne Anmeldung"); print({p_: rq(anon, "GET", p_)[0] for p_ in PF})
print("POST ohne Anmeldung", rq(anon, "POST", "/api/kunden", {"kurzname": "x"})[0], rq(anon, "POST", "/api/beenden", {})[0], rq(anon, "POST", "/api/anmeldung/einrichten", {"name": "H", "login": "h", "passwort": "hackhack1", "passwort2": "hackhack1"})[0])
# 3 Rollen
for lg in ("max", "werk", "buero"):
    o = cl(); s = rq(o, "POST", "/api/anmeldung/anmelden", {"login": lg, "passwort": "passwort123"})[0]
    erg = {p_: rq(o, "GET", p_)[0] for p_ in PF[:20]}
    print("---", lg, s, erg)
    print("   schreiben:", {x: rq(o, mth, x, d)[0] for mth, x, d in (("PUT", "/api/einstellungen", {"firma": "Hack"}), ("POST", "/api/benutzer", {"name": "h", "login": "h2", "passwort": "hackhack1", "rolle": "inhaber"}),
          ("PUT", f"/api/benutzer/1", {"passwort": "neu12345678"}), ("POST", "/api/service/ruecksicherung", {}), ("DELETE", f"/api/kunden/{k['id']}", None), ("POST", "/api/beenden", {}),
          ("PUT", f"/api/positionen/{pid}", {"einzelpreis": 1}), ("GET", f"/api/stempel/zeiten?mitarbeiter_id={m2.get('id')}", None), ("GET", f"/api/stempel", None))})
    if lg == "werk":
        s, b, _ = rq(o, "GET", f"/api/auftraege/{a['id']}"); print("   Werkstatt sieht Preise:", any(x in b for x in ('"einzelpreis": 100', '"ep": 100', '"netto": 100')), s)
        s, b, _ = rq(o, "GET", f"/api/auftraege/{a['id']}/positionen"); print("   Werkstatt Positionen Preise:", '100.0' in b or '"einzelpreis": 100' in b, s, b[:0])
# 4 CSRF
print("--- CSRF fremde Origin:", rq(inh, "POST", "/api/kunden", {"kurzname": "csrf"}, {"Origin": "http://boese.example"})[0], "| ohne Origin text/plain:", rq(inh, "POST", "/api/kunden", {"kurzname": "csrf2"}, {"Content-Type": "text/plain"})[0])
# 5 Brute force
bf = cl(); codes = [rq(bf, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": f"falsch{i}"})[0] for i in range(9)]; print("--- Fehlversuche:", codes, rq(bf, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "falsch"})[1][:90])
# 6 Header
s, b, hd = rq(inh, "GET", "/"); print("--- Header:", {x: hd.get(x) for x in ("X-Frame-Options", "Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy", "Server")})
json.dump({"beleg": bl["id"], "auftrag": a["id"]}, open("/tmp/claude-0/t/sec/ids.json", "w"))
