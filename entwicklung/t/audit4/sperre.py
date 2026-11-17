import json, time
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
aus = []
for i in range(9):
    c = cl(); z = time.time(); s, b, _ = rq(c, "POST", "/api/anmeldung/anmelden", {"login": "werk", "passwort": f"falsch{i}"}); aus.append((s, round(time.time() - z, 2), json.loads(b).get("fehler", "")[:60] if b[:1] == "{" else ""))
print("9 falsche Anmeldungen:", aus)
c = cl(); s, b, _ = rq(c, "POST", "/api/anmeldung/anmelden", {"login": "werk", "passwort": "Pruefung#2026"}); print("richtiges Passwort direkt danach:", s, b[:90])
c = cl(); s, b, _ = rq(c, "POST", "/api/anmeldung/anmelden", {"login": "gibtsnicht", "passwort": "x"}); print("unbekannter Benutzer:", s, b[:90])
s, b, hd = rq(cl(), "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}); print("Cookie:", hd.get("Set-Cookie", "").split("=")[0], ";".join(hd.get("Set-Cookie", "").split(";")[1:]), "| Tokenlänge:", len(hd.get("Set-Cookie", "").split("=")[1].split(";")[0]))
s, b, _ = rq(cl(), "POST", "/api/anmeldung/einrichten", {"name": "H", "login": "h", "passwort": "hackhack1", "passwort2": "hackhack1"}); print("erneutes Einrichten ohne Anmeldung:", s, b[:80])
