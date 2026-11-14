import json, base64, io, zipfile, csv, sys
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim123", "passwort2": "geheim123", "firma": "Testbetrieb"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
F = []
def P(pfad, d=None, m="POST", erwartet=200):
    s, b, _ = rq(inh, m, "/api/" + pfad, d)
    if s != erwartet: F.append((m, pfad, s, b[:200])); print("  !!", m, pfad, s, b[:200])
    return J(b)
def ok(n, b):
    print(("ok   " if b else "FEHL ") + n); b or F.append(n)
k = P("kunden", {"kurzname": "Müller \"Bau\"; GmbH", "firma": "Müller Bau GmbH", "strasse": "Weg 1", "plz": "88069", "ort": "Tettnang"})
a = P("auftraege", {"kunde_id": k["id"], "bezeichnung": "Küche"})
P(f"auftraege/{a['id']}/positionen", {"text": "Küche", "menge": 1, "einheit": "Stk.", "einzelpreis": 10000, "preis_manuell": 1})
ab = P(f"auftraege/{a['id']}/belege", {"art": "abschlag", "prozent": 30})
r_ab = P(f"belege/{ab['id']}/festschreiben", {})["beleg"]
sr = P(f"auftraege/{a['id']}/belege", {"art": "rechnung"})
r_sr = P(f"belege/{sr['id']}/festschreiben", {})["beleg"]
a2 = P("auftraege", {"kunde_id": k["id"], "bezeichnung": "Tisch"})
P(f"auftraege/{a2['id']}/positionen", {"text": "Tisch", "menge": 1, "einheit": "Stk.", "einzelpreis": 500, "preis_manuell": 1})
r3 = P(f"belege/{P(f'auftraege/{a2['id']}/belege', {'art': 'rechnung'})['id']}/festschreiben", {})["beleg"]
st = P(f"belege/{r3['id']}/storno", {})["beleg"]
print("Belege", [(b["nummer"], b["art"], b["brutto"], b["zahlbetrag"]) for b in (r_ab, r_sr, r3, st)])
l = P("lieferanten", {"kurzname": "Holz AG", "iban": "DE89370400440532013000"})
l2 = P("lieferanten", {"kurzname": "Schreinerei Fremd", "datev_konto": "3100"})
lk = P("lieferanten", {"kurzname": "AOK", "gruppe": "Krankenkasse"})
P("zahlungen", {"lieferant_id": l["id"], "belegnr": "RE 4711/A", "belegdatum": "2026-11-03", "betrag": 238.0, "vorsteuer": 19, "faellig": "2026-11-20"})
P("zahlungen", {"lieferant_id": l2["id"], "belegnr": "F-1", "belegdatum": "2026-11-04", "betrag": 1190.0, "vorsteuer": 19, "faellig": "2026-11-20"})
P("zahlungen", {"lieferant_id": lk["id"], "belegnr": "SV 10/2026", "belegdatum": "2026-11-04", "betrag": 900.0, "vorsteuer": 0, "faellig": "2026-11-26"})
von, bis = "2026-11-01", "2026-11-30"
P("service/datev", {"von": von, "bis": bis}, erwartet=400)
P("einstellungen", {"datev": {"berater": "1234567", "mandant": "10042", "skr": "03"}}, "PUT")
P("service/datev", {"von": "2026-11-01", "bis": "2027-01-31"}, erwartet=400)
r = P("service/datev", {"von": von, "bis": bis})
print("Export", r)
s, roh, _ = rq(inh, "GET", "/api/service/export/" + r["datei"], roh=True)
z = zipfile.ZipFile(io.BytesIO(roh))
print("ZIP:", z.namelist())
c = z.read(r["csv"])
text = c.decode("cp1252")
zeilen = text.split("\r\n")
ok("CRLF und letzte Zeile leer", zeilen[-1] == "" and "\n" not in text.replace("\r\n", ""))
kopf = next(csv.reader([zeilen[0]], delimiter=";"))
ok("Kopf 31 Felder", len(kopf) == 31)
print("  Kopf:", zeilen[0])
sp = next(csv.reader([zeilen[1]], delimiter=";"))
ok("125 Spalten", len(sp) == 125)
daten = [next(csv.reader([zl], delimiter=";")) for zl in zeilen[2:] if zl]
ok("jede Buchung 125 Felder", all(len(x) == 125 for x in daten))
for x in daten:
    print("  ", x[0], x[1], x[6], x[7], x[9], x[10], x[11], x[13], x[113], x[114], x[116])
ok("4 Ausgangs + 2 Eingang (ohne Krankenkasse)", len(daten) == 6)
umsatz = {x[10]: (x[0], x[1], x[7]) for x in daten}
ok("Abschlag 3570,00 S an 8400", umsatz[r_ab["nummer"]] == ("3570,00", "S", "8400"))
ok("Schlussrechnung nur Rest 8330,00", umsatz[r_sr["nummer"]] == ("8330,00", "S", "8400"))
ok("Storno im Haben", umsatz[st["nummer"]][1] == "H" and umsatz[st["nummer"]][0] == "595,00")
ok("Lieferant eigenes Konto 3100", any(x[6] == "3100" and x[7] == "70000" for x in daten))
ok("Belegfeld bereinigt", any(x[10] == "RE4711/A" for x in daten))
ok("Anführungszeichen ersetzt", "'Bau'" in text and "\"Bau\"" not in text.split("\r\n", 2)[2])
print("FEHLER:", F)
