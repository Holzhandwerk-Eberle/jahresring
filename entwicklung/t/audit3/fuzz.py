import json, re, random, sys, collections
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
random.seed(7)
c = cl(); rq(c, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
src = "".join(open(f"/home/claude/eberle-buero/{f}", encoding="utf-8").read() for f in ("app.py", "personal.py", "material.py", "benutzer.py", "projekte.py", "korrespondenz.py", "montage.py", "bautagebuch.py", "werkzeuge.py", "mahnwesen.py", "reste.py", "vorlagen.py"))
res = sorted(set(re.findall(r'res == "([a-z_]+)"', src)) | set(re.findall(r'"([a-z_]+)": \(\[', src)) | {"mitarbeiter", "zeiten", "abwesenheiten", "konten", "lohn", "stempel", "material", "lager", "materialsets", "auftragskosten", "benutzer", "monatsbeleg"})
unter = sorted(set(re.findall(r'unter == "([a-z_]+)"', src)) | set(re.findall(r'teile\[1:\] == \["([a-z_]+)"\]', src)) | set(re.findall(r'teile\[2\] == "([a-z_]+)"', src)) | set(re.findall(r'teile\[1\] == "([a-z_]+)"', src)))
AUS = {"beenden", "autostart", "fenster", "kalendertest"}; AUS_U = {"ruecksichern", "testdaten", "sicherung", "echtbetrieb", "neustart", "senden", "abholen", "test", "pruefer", "belegpaket", "zertifikat", "wiederherstellen", "start", "kennwort", "notfall", "abmelden", "einrichten"}
werte = [None, "", "x", "ä" * 300, 0, -1, 1, 99999999, 1e308, "1e999", "NaN", True, [], [1, "a", None], {}, {"a": {"b": [1]}}, "2026-13-45", "../../etc/passwd", "<b>", "'; DROP TABLE kunden;--", "\x00", 3.14, "12,5", "1.234,56", "0x10", [[]], {"id": 1}]
felder = sorted(set(re.findall(r'd(?:aten)?\.get\("([a-z_0-9]+)"', src)) | set(re.findall(r'"([a-z_]+)"(?=, "[a-z_]+"[,\]])', src)))[:400]
def last():
    r = random.random()
    if r < 0.08: return random.choice([[], "text", 5, None, [1, 2], [{}]])
    return {random.choice(felder): random.choice(werte) for _ in range(random.randint(0, 9))}
zaehl = collections.Counter(); fuenf = collections.Counter(); bsp = {}
pfade = []
for r in res:
    if r in AUS: continue
    pfade += [r, f"{r}/1", f"{r}/2", f"{r}/0", f"{r}/-1", f"{r}/abc", f"{r}/99999"] + [f"{r}/{u}" for u in unter if u not in AUS_U][:60] + [f"{r}/1/{u}" for u in unter if u not in AUS_U]
print(len(res), "Ressourcen,", len(unter), "Unterpfade,", len(pfade), "Pfade")
n = 0
for p in pfade:
    for m in ("GET", "POST", "PUT", "DELETE"):
        if m == "DELETE" and (p.startswith(("benutzer/1", "einstellungen")) or p == "benutzer"): continue
        if p.startswith("service") and m != "GET": continue
        for k in range(1 if m in ("GET", "DELETE") else 3):
            q = "" if m != "GET" or k == 0 else ""
            d = last() if m in ("POST", "PUT") else None
            if p.startswith("benutzer") and isinstance(d, dict): d.pop("rolle", None); d.pop("aktiv", None); d.pop("passwort", None); d.pop("login", None)
            if p.startswith("einstellungen") and m != "GET": continue
            try: s, b, _ = rq(c, m, "/api/" + p + ("?" + "&".join(f"{random.choice(felder)}={random.choice(['', 'x', '-1', 'abc', '2026-99-99', '1e9'])}" for _ in range(3)) if m == "GET" else ""), d)
            except Exception as x: s, b = 599, str(x)
            n += 1; zaehl[s] += 1
            if s >= 500:
                try: t = json.loads(b).get("fehler", b)[:110]
                except Exception: t = b[:110]
                key = re.sub(r"\d+", "N", t); fuenf[key] += 1; bsp.setdefault(key, (m, p, json.dumps(d, ensure_ascii=False, default=str)[:160]))
print(n, "Anfragen; Statuscodes:", dict(sorted(zaehl.items())))
print(len(fuenf), "verschiedene Serverfehler (5xx):")
for k, v in fuenf.most_common(60): print(f"  {v:4}× {k}\n        z. B. {bsp[k][0]} {bsp[k][1]} {bsp[k][2]}")
s, b, _ = rq(c, "GET", "/api/version"); print("Server lebt noch:", s, b[:60])
s, b, _ = rq(c, "GET", "/api/service/protokoll?voll=1"); pr = json.loads(b); print("Protokoll nach dem Beschuss in Ordnung:", pr["pruefung"]["ok"], "| Belege:", pr["belege"]["ok"])
