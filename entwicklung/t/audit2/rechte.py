import json, re, sys
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def P(pfad, d, m="POST"):
    s, b, _ = rq(inh, m, "/api/" + pfad, d); j = J(b)
    if s >= 400: print("  !! Anlage", pfad, s, b[:120])
    return j
ma = P("mitarbeiter", {"vorname": "Max", "nachname": "Werk", "stundenlohn": 23.5, "iban": "DE02120300000000202051"}); mid = ma.get("id") or ma.get("mitarbeiter", {}).get("id")
ma2 = P("mitarbeiter", {"vorname": "Eva", "nachname": "Zwei", "stundenlohn": 31}); mid2 = ma2.get("id") or ma2.get("mitarbeiter", {}).get("id")
lf = P("lieferanten", {"kurzname": "Holz AG", "firma": "Holz AG", "iban": "DE02120300000000202051"})
zl = P("zahlungen", {"lieferant_id": lf.get("id"), "betrag": 1234.56, "rechnungsnummer": "RE-77", "datum": "2026-11-01", "faellig": "2026-11-20"})
hw = P("material/holzwerkstoffe", {"bezeichnung": "MDF 19", "preis": 12.34, "lieferant_id": lf.get("id")})
P("abwesenheiten", {"mitarbeiter_id": mid2, "art": "krank", "von": "2026-11-10", "bis": "2026-11-12", "status": "genehmigt", "bemerkung": "Grippe"})
k = P("kunden", {"kurzname": "Privat", "nachname": "Geheim", "strasse": "Weg 1", "plz": "88069", "ort": "Tettnang", "telefon": "0171 1234567", "email": "g@x.de", "iban": "DE02120300000000202051", "notizen": "zahlt schlecht"})
au = P("auftraege", {"kunde_id": k["id"], "bezeichnung": "Küche"})
po = P(f"auftraege/{au['id']}/positionen", {"text": "Schrank"}); pid = po.get("id") or po["position"]["id"]
P(f"positionen/{pid}", {"einzelpreis": 4321.0, "preis_manuell": 1}, "PUT")
bl = P(f"auftraege/{au['id']}/belege", {"art": "angebot"})
P("termine", {"auftrag_id": au["id"], "typ": "Montage", "von": "2026-11-16", "bis": "2026-11-17", "mitarbeiter": [mid]})
u1 = P("benutzer", {"name": "W", "login": "werk", "passwort": "geheim456", "rolle": "werkstatt", "mitarbeiter_id": mid})
u2 = P("benutzer", {"name": "M", "login": "mita", "passwort": "geheim456", "rolle": "mitarbeiter", "mitarbeiter_id": mid2})
u3 = P("benutzer", {"name": "B", "login": "buero", "passwort": "geheim456", "rolle": "buero"})
u4 = P("benutzer", {"name": "O", "login": "ohnepreis", "passwort": "geheim456", "rolle": "eigen", "eigen": {"bereiche": {k: 2 for k in ("start", "kunden", "auftraege", "op", "lieferanten", "material", "kalender", "personal", "einstellungen")}, "preise": False}})
import urllib.request
src = open("/home/claude/eberle-buero/app.py", encoding="utf-8").read() + open("/home/claude/eberle-buero/benutzer.py", encoding="utf-8").read()
res = sorted(set(re.findall(r'res == "([a-z_]+)"', src)) | set(re.findall(r'^    "([a-z_]+)": \(', src, re.M)) | set(re.findall(r'"([a-z_]+)": \(\[', src)) | {"mitarbeiter", "zeiten", "abwesenheiten", "konten", "lohn", "monatsbeleg", "stempel", "material", "lager", "materialsets", "auftragskosten", "protokoll", "benutzer"})
pfade = []
for r in res:
    pfade += [r, f"{r}/1", f"{r}/{au['id']}", f"{r}/1/positionen", f"{r}/1/belege", f"{r}/1/historie", f"{r}/1/kalkulation", f"{r}/1/zahlungen", f"{r}/liste", f"{r}/uebersicht", f"{r}?status=alle", f"{r}?jahr=2026", f"{r}?monat=2026-11", f"{r}?mitarbeiter_id={mid2}&monat=2026-11", f"{r}?q=Geheim", f"{r}/{mid2}"]
pfade += ["service/protokoll", "service/sicherungen", "service/projektsicherung", "material/holzwerkstoffe", "material/holzwerkstoffe/1", "material/statistik", f"auftraege/{au['id']}/auswertung", f"auftraege/{au['id']}/sollist", f"auftraege/{au['id']}/kunde", f"auftraege/{au['id']}/op", f"belege/{bl.get('id')}", f"belege/{bl.get('id')}/druck", f"positionen/{pid}", f"positionen/{pid}/kalkulation", f"kunden/{k['id']}", f"lieferanten/{lf.get('id')}", f"zahlungen/{zl.get('id')}", f"mitarbeiter/{mid2}", f"lohn/{mid2}", "einstellungen", "vorlagen", "kalkvorgaben", "nummernkreise", "start", "statistik?jahr=2026", "zahlungsstatistik", "offeneposten", "leitstand", "suche?q=Geheim", "suche?q=Holz", "kalender", "kalender/export.ics", f"termine?auftrag_id={au['id']}", "reste", "projekte", "briefe", "newsletter", "konten?jahr=2026", "zeiten?monat=2026-11", "abwesenheiten?jahr=2026", "monatsbeleg?monat=2026-11&mitarbeiter_id=" + str(mid2)]
GEHEIM = ["4321", "1234.56", "1234,56", "23.5", "23,5", "DE0212030", "zahlt schlecht", "Grippe", "krank", "0171 1234567", "12.34", "12,34", "5142", "5.142", "smtp", "passwort"]
def finde(obj, pfad="", aus=None):
    aus = aus if aus is not None else []
    if isinstance(obj, dict):
        for kk, v in obj.items(): finde(v, pfad + "." + str(kk), aus)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:40]): finde(v, pfad + "[]", aus)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if abs(obj) > 0 and re.search(r"(preis|ek$|vk$|\.ep$|\.gp$|einzel|gesamt|offen|bezahlt|saldo|soll|haben|limit|anzahl|zahlung|lohn|wert|kost|geld|eur|netto|brutto|summe|betrag)", pfad.lower()) and not re.search(r"(anzahl|zahlungsziel|tage|_id$|\.id$|menge|stunden|minuten|soll_min|haben_min|sollzeit)", pfad.lower()): aus.append((pfad, obj))
    elif isinstance(obj, str):
        for g in GEHEIM:
            if g.lower() in obj.lower(): aus.append((pfad, "…" + g + "…"))
        if re.search(r"\d,\d\d\s*€", obj): aus.append((pfad, obj[:60]))
    return aus
for login in ("werk", "mita", "ohnepreis", ""):
    c = cl()
    if login: rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": "geheim456"})
    print(f"\n===== {login or 'UNANGEMELDET'}"); offen = []; funde = {}
    for p in dict.fromkeys(pfade):
        s, b, _ = rq(c, "GET", "/api/" + p)
        if s == 200:
            offen.append(p)
            try: j = json.loads(b)
            except ValueError: j = b
            for pf, w in finde(j): funde.setdefault(p.split("?")[0] + " " + pf, w)
        elif s >= 500: print("   500!", p, b[:100])
    print("  200:", " ".join(offen)[:1500])
    for kk, v in list(funde.items())[:60]: print("   Fund:", kk[:90], "=", v)
    # Schreibversuche
    for m, p, d in [("PUT", f"positionen/{pid}", {"einzelpreis": 1}), ("DELETE", f"auftraege/{au['id']}", None), ("PUT", "einstellungen", {"firma": "X"}), ("POST", "kunden", {"kurzname": "x"}), ("PUT", f"benutzer/{u1.get('id')}", {"rolle": "inhaber"}), ("POST", "service/sicherung", {}), ("POST", "zahlungen", {"lieferant_id": 1, "betrag": 1}), ("POST", "termine", {"auftrag_id": au["id"], "typ": "Montage", "von": "2026-11-18", "bis": "2026-11-18"}), ("PUT", f"auftraege/{au['id']}", {"bezeichnung": "gehackt"}), ("PUT", f"mitarbeiter/{mid2}", {"stundenlohn": 99}), ("POST", "zeiten", {"mitarbeiter_id": mid2, "datum": "2026-11-13", "von": "08:00", "bis": "16:00"}), ("POST", "beenden", {})]:
        s, b, _ = rq(c, m, "/api/" + p, d)
        if s < 400: print(f"   SCHREIBEN ERLAUBT: {m} {p} → {s} {b[:80]}")
