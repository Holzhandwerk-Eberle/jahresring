import json
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
c = cl(); rq(c, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
X = '"><img src=x onerror="window.__xss=(window.__xss||0)+1"><b x="'
def A(m, p, d=None):
    s, b, _ = rq(c, m, "/api/" + p, d); j = J(b)
    if s >= 400: print("  !!", p, s, b[:100])
    return j
k = A("POST", "kunden", {"kurzname": X + "K", "firma": X, "vorname": X, "nachname": X, "strasse": X, "ort": X, "plz": "1", "telefon": X, "email1": X, "bemerkungen": X, "merkmale": X, "zusatz": X, "anrede": X, "website": X, "ustid": X, "lieferanschrift": X, "leitweg_id": X})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": X + "A", "bemerkungen": X, "gruppe": X, "plan_von": "2026-11-16", "plan_bis": "2026-11-20"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": X + "P"}); pid = po.get("id") or po["position"]["id"]
A("PUT", f"positionen/{pid}", {"text": X, "langtext": X, "einheit": X, "einzelpreis": 5, "preis_manuell": 1, "bemerkung": X, "gruppe": X})
for art in ("angebot", "rechnung", "lieferschein"):
    b = A("POST", f"auftraege/{a['id']}/belege", {"art": art}); A("PUT", f"belege/{b.get('id')}", {"betreff": X, "kopftext": X, "fusstext": X, "anschrift": X})
ma = A("POST", "mitarbeiter", {"vorname": X, "nachname": X, "kuerzel": X, "bemerkung": X, "strasse": X, "ort": X}); maid = ma.get("id") or ma.get("mitarbeiter", {}).get("id")
A("POST", "termine", {"auftrag_id": a["id"], "typ": X, "titel": X, "notiz": X, "von": "2026-11-17", "bis": "2026-11-18", "mitarbeiter": [maid]})
A("POST", "termine", {"typ": "Montage", "titel": X, "notiz": X, "von": "2026-11-13", "bis": "2026-11-13"})
A("POST", "abwesenheiten", {"mitarbeiter_id": maid, "art": "urlaub", "von": "2026-11-19", "bis": "2026-11-19", "status": "genehmigt", "bemerkung": X})
lf = A("POST", "lieferanten", {"kurzname": X + "L", "anschrift": X, "ort": X, "telefon": X, "email1": X, "bemerkungen": X, "empfaenger": X, "unsere_kundennr": X, "website": X})
z = A("POST", "zahlungen", {"lieferant_id": lf["id"], "betrag": 10, "belegnr": X, "bemerkung": X, "empfaenger": X, "auftrag_id": a["id"]})
for kat in ("holzwerkstoffe", "massivholz", "beschichtung", "chemie", "beschlaege", "artikel"):
    m = A("POST", "material", {"kategorie": kat, "bezeichnung": X + kat, "gruppe": X, "einheit": X, "bemerkungen": X, "bestellnr": X, "lagerort": X, "ek_preis": 3, "lieferant_id": lf["id"]})
    if m.get("id"): A("POST", "lager", {"material_id": m["id"], "art": "zugang", "menge": 2, "preis": 3, "bemerkung": X, "lagerort": X}); A("POST", "auftragskosten", {"auftrag_id": a["id"], "material_id": m["id"], "menge": 1, "bezeichnung": X, "bemerkung": X})
A("POST", "werkzeuge", {"bezeichnung": X, "art": X, "hersteller": X, "seriennr": X, "standort": X, "bemerkung": X})
A("POST", "projekte", {"bezeichnung": X, "kunde_id": k["id"], "bemerkungen": X})
A("POST", "notizen", {"kunde_id": k["id"], "text": X}); A("POST", "notizen", {"auftrag_id": a["id"], "text": X})
A("POST", "stunden", {"auftrag_id": a["id"], "datum": "2026-11-12", "stunden": 2, "taetigkeit": X, "bemerkung": X, "mitarbeiter": X, "kst": X})
A("POST", "zeiten", {"mitarbeiter_id": maid, "datum": "2026-11-12", "beginn": "08:00", "ende": "12:00", "bemerkung": X, "kst": X, "auftrag_id": a["id"]})
A("POST", "benutzer", {"name": X, "login": "xssuser", "passwort": "geheim456", "rolle": "buero"})
A("PUT", "einstellungen", {"firma": X, "firma_inhaber": X, "firma_zusatz": X, "auftragsgruppen": [X], "kundengruppen": [X, "Privatkunde"], "lagerorte": [X], "textbausteine": [{"name": X, "text": X}], "bezahlarten": [X]})
A("POST", "briefe", {"kunde_id": k["id"], "betreff": X, "text": X})
print("Daten angelegt: Kunde", k.get("id"), "Auftrag", a.get("id"), "Position", pid, "Lieferant", lf.get("id"), "Zahlung", z.get("id"))
