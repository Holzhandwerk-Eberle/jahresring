"""Sicherheits- und Rechteproben (Prüfung -148). Erwartet die Prüfinstanz nach t10.js (Inhaber jonas/geheim123)."""
import json, re, sys, base64, time
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); s, b, _ = rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}); print("Inhaber angemeldet", s)
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
def anmelden(login, pw):
    c = cl(); s, b, _ = rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": pw}); return c, s
mi = lambda d: (d.get("id") or d.get("mitarbeiter", {}).get("id"))
m1 = mi(A("POST", "mitarbeiter", {"vorname": "Max", "nachname": "Werk", "stundenlohn": 23.5}))
m2 = mi(A("POST", "mitarbeiter", {"vorname": "Eva", "nachname": "Zwei", "stundenlohn": 31}))
PW = "Pruefung#2026"
for lg, rolle, extra in (("werk", "werkstatt", {"mitarbeiter_id": m1}), ("mita", "mitarbeiter", {"mitarbeiter_id": m2}), ("buero", "buero", {}),
                         ("verw", "eigen", {"eigen": {"bereiche": {"einstellungen": 2, "start": 1}}})):
    r = A("POST", "benutzer", {"name": lg, "login": lg, "passwort": PW, "rolle": rolle, **extra}); print("Benutzer", lg, r["_s"], r.get("fehler", ""))
bel = A("GET", "belege")["liste"]; fest = [x for x in bel if x.get("status") == "fest"]; print("Belege", len(bel), "fest", len(fest))
bid = (fest or bel)[0]["id"]
print("\n== 1. Rohrouten je Rolle (200 = Zugriff)")
pfade = [f"/api/belege/{bid}/zugferd.xml", f"/api/belege/{bid}/xrechnung.xml", f"/druck/{bid}", f"/druck/{bid}.pdf", "/api/service/protokoll.csv", "/api/kalender/export.ics",
         f"/papier/1/laufzettel", "/liste/lager", "/zuschnitt/", "/api/unterschrift", "/api/vorlage/brief-1.svg", f"/druck/monatsbeleg/{m1}/2026-11", f"/druck/monatsbeleg/{m2}/2026-11",
         "/api/mahnungen/1/pdf", "/api/zahlungen/1/datei", "/druck/arbeitsschutz/notfall", "/druck/arbeitsschutz/gefahrstoffverzeichnis", f"/papier/projekt/1/zeitbericht"]
sitz = {lg: anmelden(lg, PW)[0] for lg in ("werk", "mita", "buero", "verw")}; sitz["anonym"] = cl()
for p in pfade:
    print("  %-44s" % p, " ".join(f"{lg}:{rq(c, 'GET', p)[0]}" for lg, c in sitz.items()))
print("\n== 2. Rechte selbst erweitern (Benutzer 'verw': eigene Rechte, nur Einstellungen=2)")
v = sitz["verw"]
r = A("GET", "lohn?monat=2026-11", c=v); print("  verw liest Lohn:", r["_s"])
r = A("POST", "benutzer", {"name": "x", "login": "hoch", "passwort": PW, "rolle": "inhaber"}, c=v); print("  verw legt Inhaber an:", r["_s"], r.get("fehler", "")[:60])
r = A("POST", "benutzer", {"name": "x", "login": "hoch2", "passwort": PW, "rolle": "eigen", "eigen": {"bereiche": {"personal": 2, "op": 2, "kunden": 2, "auftraege": 2, "lieferanten": 2}}}, c=v)
print("  verw legt Benutzer mit Personal=2 an:", r["_s"], r.get("fehler", "")[:60])
if r["_s"] == 200:
    c2, s2 = anmelden("hoch2", PW); r2 = A("GET", "lohn?monat=2026-11", c=c2); r3 = A("GET", "mitarbeiter", c=c2); print("   → neuer Benutzer liest Lohn:", r2["_s"], "Mitarbeiter:", r3["_s"])
ich = [u for u in A("GET", "benutzer", c=v).get("liste", []) if u.get("login") == "verw"]
if ich:
    r = A("PUT", f"benutzer/{ich[0]['id']}", {"eigen": {"bereiche": {"einstellungen": 2, "personal": 2, "op": 2}}}, c=v); print("  verw gibt sich selbst Personal=2:", r["_s"], r.get("fehler", "")[:60])
    print("   → verw liest Lohn danach:", A("GET", "lohn?monat=2026-11", c=v)["_s"])
jo = [u for u in A("GET", "benutzer").get("liste", []) if u.get("login") == "jonas"][0]
r = A("PUT", f"benutzer/{jo['id']}", {"passwort": "Gekapert#2026"}, c=v); print("  verw setzt Passwort des Inhabers:", r["_s"], r.get("fehler", "")[:60])
r = A("POST", "service/sicherung", {}, c=v); print("  verw erstellt Sicherung:", r["_s"]); r = A("GET", "service/sicherungen", c=v); print("  verw listet Sicherungen:", r["_s"])
print("\n== 3. Sitzung nach Sperren / Passwortwechsel")
bu = [u for u in A("GET", "benutzer").get("liste", []) if u.get("login") == "buero"][0]
print("  buero vorher:", A("GET", "kunden", c=sitz["buero"])["_s"])
A("PUT", f"benutzer/{bu['id']}", {"passwort": "Neu#Passwort77"}); print("  nach Passwortwechsel durch Inhaber:", A("GET", "kunden", c=sitz["buero"])["_s"])
cb, s = anmelden("buero", "Neu#Passwort77"); print("  neu angemeldet:", s)
A("PUT", f"benutzer/{bu['id']}", {"aktiv": 0}); print("  nach Sperren:", A("GET", "kunden", c=cb)["_s"], "| neue Anmeldung:", anmelden("buero", "Neu#Passwort77")[1])
A("PUT", f"benutzer/{bu['id']}", {"aktiv": 1})
print("\n== 4. Mitarbeiter-Rolle: fremde Daten")
mt = sitz["mita"]
for p in ("mitarbeiter", f"mitarbeiter/{m1}", f"zeiten?mitarbeiter_id={m1}&monat=2026-11", f"stempel", f"stempel/status", f"abwesenheiten?mitarbeiter_id={m1}", "kalender?von=2026-11-01&bis=2026-11-30", f"konten?mitarbeiter_id={m1}",
          f"monatsbeleg/{m1}/2026-11", "arbeitsschutz/uebersicht", "kunden", "start", "einstellungen", "benutzer", "suche?q=Max"):
    s, b, _ = rq(mt, "GET", "/api/" + p); print("  %-48s %s %s" % (p, s, (b[:110].replace("\n", " ") if s == 200 else "")))
print("\n== 5. Kopfzeilen und Fehlertexte")
s, b, hd = rq(inh, "GET", "/api/kunden"); print("  API:", {k: v[:60] for k, v in hd.items() if k.lower() in ("cache-control", "x-content-type-options", "referrer-policy", "content-security-policy", "x-frame-options", "strict-transport-security", "permissions-policy")})
s, b, hd = rq(inh, "GET", "/"); print("  Seite:", {k: v[:70] for k, v in hd.items() if k.lower() in ("cache-control", "x-content-type-options", "referrer-policy", "content-security-policy", "x-frame-options", "permissions-policy")})
s, b, _ = rq(inh, "PUT", "/api/positionen/1", {"menge": {"a": 1}}); print("  Fehlerform bei unsinniger Eingabe:", s, b[:160])
s, b, _ = rq(inh, "GET", "/api/belege/99999999"); print("  unbekannter Beleg:", s, b[:100])
s, b, _ = rq(inh, "POST", "/api/kunden", {"kurzname": "x" * 200000}); print("  200.000 Zeichen im Namen:", s, len(b))
print("\n== 6. Herkunftsprüfung (CSRF)")
s, b, _ = rq(inh, "POST", "/api/kunden", {"kurzname": "CSRF"}, {"Origin": "https://boese.example"}); print("  fremde Herkunft:", s, b[:60])
s, b, _ = rq(inh, "POST", "/api/kunden", {"kurzname": "CSRF2"}, {"Origin": "null"}); print("  Origin null:", s)
r = urllib.request.Request(U + "/api/kunden", method="POST", data=b'{"kurzname":"CSRF3"}', headers={"Content-Type": "text/plain"})
try: x = inh.open(r); print("  text/plain ohne Origin:", x.status)
except urllib.error.HTTPError as e: print("  text/plain ohne Origin:", e.code)
s, b, _ = rq(inh, "GET", "/api/kunden", None, {"Host": "boese.example"}); print("  fremder Host:", s)
