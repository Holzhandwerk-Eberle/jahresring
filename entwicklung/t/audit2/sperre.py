import json, gzip, urllib.request
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {"_roh": t[:200]}
def mk(login, pw):
    c = cl(); rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": pw})
    def A(m, p, d=None):
        s, b, _ = rq(c, m, "/api/" + p, d); j = J(b)
        return {"FEHLER": j.get("fehler", b[:100]), "code": s} if s >= 400 and isinstance(j, dict) else j
    return A
A = mk("jonas", "geheim123")
def ok(b, t): print(("ok   " if b else "FEHLER ") + t)
lf = A("POST", "lieferanten", {"kurzname": "Holz AG", "iban": "DE02120300000000202051"}); k = A("POST", "kunden", {"kurzname": "K"}); au = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "A"})
z = A("POST", "zahlungen", {"lieferant_id": lf["id"], "betrag": 119, "belegnr": "R1", "belegdatum": "2026-11-01"}); zid = z["id"]
ok(A("PUT", f"zahlungen/{zid}", {"betrag": 120}).get("betrag") == 120, "offen: Betrag änderbar")
ok(A("POST", "zahlungen/bezahlt", {"ids": [zid], "datum": "2026-11-10"}).get("anzahl") == 1, "bezahlt markiert")
ok(A("POST", "zahlungen/bezahlt", {"ids": [zid], "datum": "2026-11-12"}).get("anzahl") == 0 and A("GET", f"zahlungen/{zid}")["bezahlt"] == "2026-11-10", "zweites Markieren ändert das Datum nicht")
for feld, wert in (("betrag", 1), ("belegnr", "X"), ("belegdatum", "2026-01-01"), ("iban", "DE89370400440532013000"), ("bezahlt", ""), ("bezahlt", "2026-11-11"), ("vorsteuer", 7), ("skonto", 3), ("empfaenger", "Wer"), ("lieferant_id", lf["id"] + 99), ("faellig", "2027-01-01")):
    r = A("PUT", f"zahlungen/{zid}", {feld: wert}); ok(r.get("code") == 409, f"gesperrt: {feld} → {str(r.get('FEHLER'))[:50]}")
r = A("PUT", f"zahlungen/{zid}", {"bemerkung": "Notiz", "auftrag_id": au["id"], "bezahlung": "Bar"}); ok(r.get("bemerkung") == "Notiz" and r.get("auftrag_id") == au["id"] and r.get("bezahlung") == "Bar", "frei: Bemerkung, Auftrag, Zahlart")
ok(A("PUT", f"zahlungen/{zid}", {"betrag": 120, "bemerkung": "gleich"}).get("bemerkung") == "gleich", "unveränderter Betrag im selben Zug stört nicht")
ok(A("DELETE", f"zahlungen/{zid}").get("code") == 409, "bezahlt: Löschen gesperrt")
A("POST", "benutzer", {"name": "B", "login": "buero", "passwort": "geheim456", "rolle": "buero"}); A("POST", "benutzer", {"name": "W", "login": "werk", "passwort": "geheim456", "rolle": "werkstatt"}); A("POST", "benutzer", {"name": "M", "login": "mita", "passwort": "geheim456", "rolle": "mitarbeiter"})
A("POST", "benutzer", {"name": "E", "login": "eigen", "passwort": "geheim456", "rolle": "eigen", "eigen": {"bereiche": {"einstellungen": 2, "auftraege": 2, "kunden": 2, "lieferanten": 2}, "preise": True}})
B = mk("buero", "geheim456"); W = mk("werk", "geheim456"); M = mk("mita", "geheim456"); E = mk("eigen", "geheim456")
ok(B("POST", f"zahlungen/{zid}/oeffnen", {}).get("code") == 403, "Büro kann „bezahlt“ nicht zurücknehmen")
r = A("POST", f"zahlungen/{zid}/oeffnen", {}); ok(r.get("bezahlt") == "", "Inhaber nimmt „bezahlt“ zurück")
ok(A("PUT", f"zahlungen/{zid}", {"betrag": 130}).get("betrag") == 130 and A("DELETE", f"zahlungen/{zid}").get("ok"), "danach wieder änderbar und löschbar")
# Lager im Protokoll
m = A("POST", "material", {"kategorie": "holzwerkstoffe", "bezeichnung": "MDF", "einheit": "m²", "ek_preis": 10}); A("POST", "lager", {"material_id": m["id"], "art": "zugang", "menge": 10, "preis": 10})
A("POST", "lager", {"material_id": m["id"], "art": "inventur", "menge": 7, "bemerkung": "Jahresinventur"})
ak = A("POST", "auftragskosten", {"auftrag_id": au["id"], "material_id": m["id"], "menge": 2, "lager_abgang": 1}); A("DELETE", f"auftragskosten/{ak['id']}")
pr = A("GET", "service/protokoll"); txt = [e["text"] for e in pr["eintraege"] if e["art"].startswith(("lager", "zahlungsauftrag"))]
for t in txt: print("     ", t[:150])
ok(any("Inventur" in t and "10" in t and "7" in t for t in txt) and any("zurückgebucht" in t for t in txt) and not any("Zugang" in t for t in txt), "Protokoll: Inventur und gelöschte Buchung, kein gewöhnlicher Zugang")
ok(any("zurückgenommen" in t for t in txt) and any("Als bezahlt" in t for t in txt), "Protokoll: bezahlt / zurückgenommen")
ok(pr["pruefung"]["ok"], "Protokollkette in Ordnung")
# Einstellungen
eA, eB, eW, eM, eE = (X("GET", "einstellungen") for X in (A, B, W, M, E))
print("      Schlüssel Inhaber/Büro/Werkstatt/Mitarbeiter/Eigen:", len(eA), len(eB), len(eW), len(eM), len(eE))
ok("steuernummer" not in eW and "textbausteine" not in eW and "kalk_vorgaben" not in eM and "auftragsstatus" in eW and "termin_typen" in eW, "Werkstatt/Mitarbeiter: nur Arbeitslisten")
ok("sepa_iban" not in eB and "smtp_server" not in eB and "sepa_iban" in eA, "Büro: ohne Bank und Mail")
for X, n in ((B, "Büro"), (W, "Werkstatt"), (M, "Mitarbeiter"), (E, "Eigene Rechte mit Einstellungen=bearbeiten")):
    r1, r2, r3, r4 = X("PUT", "einstellungen", {"firma": "Gehackt"}), X("GET", "service/protokoll"), X("POST", "vorlagen/briefbogen", {"seiten": ["x"]}), X("GET", "benutzer")
    ok(all(r.get("code") == 403 for r in (r1, r2, r3, r4) if isinstance(r, dict)) and isinstance(r1, dict) and isinstance(r4, dict), f"{n}: Einstellungen ändern, Service, Vorlagen, Benutzer gesperrt")
ok(A("GET", "einstellungen")["firma"] != "Gehackt", "Firma unverändert")
# gzip nur übers Netz: lokal ungepackt
req = urllib.request.Request("http://127.0.0.1:8799/index.html", headers={"Accept-Encoding": "gzip"}); r = urllib.request.urlopen(req); print("      lokal: Content-Encoding =", r.headers.get("Content-Encoding"), len(r.read()), "Byte")
