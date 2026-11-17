import json, re, sys, base64, time
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
def anmelden(login, pw):
    c = cl(); s, b, _ = rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": pw}); return c, s
PW = "Pruefung#2026"
werk, _ = anmelden("werk", PW); mita, _ = anmelden("mita", PW)
e = A("GET", "einstellungen", c=mita)
for k_ in sorted(e):
    t = json.dumps(e[k_], ensure_ascii=False)
    print("  %-26s %s" % (k_, t[:150]))
print("\n== Lager/Werkzeug mit Werten als Werkstatt")
mat = A("POST", "material", {"bezeichnung": "Eiche Leimholz 27", "einheit": "m²", "ek_preis": 87.65, "preis": 87.65, "ek": 87.65, "bestand": 12, "kategorie": "Platten"}); print(" Material", mat["_s"], {k_: mat.get(k_) for k_ in ("id", "ek", "ek_preis", "preis", "fehler")})
ml = A("GET", "material"); print(" Felder Material:", sorted((ml.get("liste") or ml.get("material") or [{}])[0].keys())[:40])
wz = A("POST", "werkzeuge", {"bezeichnung": "Tauchsäge", "anschaffungswert": 612.5, "wert": 612.5, "preis": 612.5}); print(" Werkzeug", wz["_s"], [k_ for k_ in wz][:20])
for p in ("/liste/lager", "/liste/werkzeuge"):
    s, t, _ = rq(werk, "GET", p); print(" ", p, s, re.findall(r"\d[\d.]*,\d\d\s*(?:€|&euro;)", t)[:8], "| Spalten:", re.findall(r"<th[^>]*>([^<]*)", t)[:14])
s, t, _ = rq(werk, "GET", "/api/material"); print("  /api/material als werk:", s, re.findall(r'"(?:ek|preis|ek_preis|vk)[a-z_]*": [^,]+', t)[:6])
s, t, _ = rq(werk, "GET", "/api/werkzeuge"); print("  /api/werkzeuge als werk:", s, re.findall(r'"[a-z_]*(?:wert|preis)[a-z_]*": [^,]+', t)[:6])
print("\n== Papier Kosten als Werkstatt")
s, t, _ = rq(werk, "GET", "/papier/2/kosten"); txt = re.sub(r"<[^>]+>", " ", t); txt = re.sub(r"\s+", " ", txt); print(" ", s, txt[:700])
for art in ("sollist", "stunden", "zeitbericht"):
    s, t, _ = rq(werk, "GET", f"/papier/2/{art}"); txt = re.sub(r"<style.*?</style>", "", t, flags=re.S); txt = re.sub(r"<[^>]+>", " ", txt); txt = re.sub(r"\s+", " ", txt); print(" ", art, s, txt[:330])
print("\n== Papiere als Werkstatt, bereinigt")
for art in ("kosten", "sollist", "stunden", "werkstattauftrag", "stueckliste", "materialsummen"):
    s, t, _ = rq(werk, "GET", f"/papier/2/{art}"); txt = re.sub(r"<(style|script).*?</\1>", "", t, flags=re.S); txt = re.sub(r"<[^>]+>", " ", txt); txt = re.sub(r"\s+", " ", txt)
    print(" ", art, s, "| €-Stellen:", re.findall(r"[^ ]* ?[^ ]* \d[\d.]*,\d\d (?:€|&euro;)", txt)[:8]); print("     ", txt[200:620])
