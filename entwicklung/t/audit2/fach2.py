import json, re, sys, datetime
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {"_roh": t[:200]}
c = cl(); rq(c, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None):
    s, b, _ = rq(c, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict) and s >= 400: j = {"FEHLER": j.get("fehler", b[:120]), "code": s}
    return j
def zeig(t, x): print(f"{t}: {json.dumps(x, ensure_ascii=False, default=str)[:260]}")
k = A("POST", "kunden", {"kurzname": "X"}); a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "L"})
print("######## LIEFERANTEN / ZAHLUNGEN")
lf = A("POST", "lieferanten", {"kurzname": "Holz AG", "iban": "DE02 1203 0000 0000 2020 51", "zahlungsziel": 30, "vorsteuer": 19})
zeig("Lieferant IBAN normalisiert", {x: lf.get(x) for x in ("id", "iban", "bic", "FEHLER")})
zeig("Lieferant falsche IBAN", A("POST", "lieferanten", {"kurzname": "Falsch", "iban": "DE02120300000000202052"}).get("FEHLER", "ANGENOMMEN"))
z1 = A("POST", "zahlungen", {"lieferant_id": lf["id"], "betrag": 1190, "belegnr": "RE-1", "belegdatum": "2026-11-01", "skonto": 2, "skonto_bis": "2026-11-10"}); zeig("Zahlung", {x: z1.get(x) for x in ("id", "nummer", "betrag", "vorsteuer", "faellig", "skonto", "iban", "FEHLER")})
z2 = A("POST", "zahlungen", {"lieferant_id": lf["id"], "betrag": 1190, "belegnr": "RE-1", "belegdatum": "2026-11-01"}); zeig("Doppelte Belegnummer", {x: z2.get(x) for x in ("id", "nummer", "warnung", "FEHLER")})
zeig("Negativer Betrag (Gutschrift)", {x: A("POST", "zahlungen", {"lieferant_id": lf["id"], "betrag": -50, "belegnr": "GS-1"}).get(x) for x in ("id", "betrag", "FEHLER")})
zeig("Betrag 0", {x: A("POST", "zahlungen", {"lieferant_id": lf["id"], "betrag": 0, "belegnr": "N-1"}).get(x) for x in ("id", "betrag", "FEHLER")})
zeig("Betrag Text", {x: A("POST", "zahlungen", {"lieferant_id": lf["id"], "betrag": "1.234,56", "belegnr": "T-1"}).get(x) for x in ("id", "betrag", "FEHLER")})
ls = A("GET", "zahlungen?status=offen"); zeig("offene Zahlungen", [(z.get("nummer"), z.get("betrag"), z.get("faellig"), z.get("zahlbetrag"), z.get("skonto_betrag")) for z in (ls if isinstance(ls, list) else ls.get("liste", []))][:6])
sx = A("POST", "zahlungen/sepa", {"ids": [z1["id"]], "ausfuehrung": "2026-11-09"}); zeig("SEPA", {x: (str(sx.get(x))[:300]) for x in sx})
xml = sx.get("xml") or sx.get("inhalt") or ""
if xml:
    print("  InstdAmt:", re.findall(r"<InstdAmt[^>]*>([^<]+)", xml), "CtrlSum:", re.findall(r"<CtrlSum>([^<]+)", xml), "Ustrd:", re.findall(r"<Ustrd>([^<]+)", xml), re.findall(r'xmlns="([^"]+)"', xml))
zeig("bezahlt setzen", {x: A("PUT", f"zahlungen/{z1['id']}", {"bezahlt": "2026-11-09"}).get(x) for x in ("bezahlt", "betrag", "FEHLER")})
zeig("bezahlte Zahlung Betrag ändern", {x: A("PUT", f"zahlungen/{z1['id']}", {"betrag": 1}).get(x) for x in ("betrag", "FEHLER")})
zeig("bezahlte Zahlung löschen", A("DELETE", f"zahlungen/{z1['id']}"))
zeig("Lieferant mit Zahlungen löschen", A("DELETE", f"lieferanten/{lf['id']}"))
zeig("Zahlungsstatistik", str(A("GET", "zahlungsstatistik"))[:200])
pr = A("GET", "service/protokoll"); zeig("Protokoll-Arten", sorted({e["art"] for e in pr.get("eintraege", [])}))
