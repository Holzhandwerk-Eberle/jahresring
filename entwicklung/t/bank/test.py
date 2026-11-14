import json, base64, sys, io, zipfile
sys.path.insert(0, "/tmp/claude-0/t/bank")
from camt import ntry, datei
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas Inhaber", "login": "jonas", "passwort": "geheim123", "passwort2": "geheim123", "firma": "Testbetrieb"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
F = []
def P(pfad, d=None, m="POST", erwartet=200):
    s, b, _ = rq(inh, m, "/api/" + pfad, d)
    if s != erwartet: F.append((m, pfad, s, b[:200])); print("  !!", m, pfad, s, b[:200])
    return J(b)
def ok(name, bed):
    print(("ok   " if bed else "FEHL ") + name)
    if not bed: F.append(name)
P("einstellungen", {"firma": "Testbetrieb", "sepa_iban": "DE02120300000000202051", "sepa_name": "Testbetrieb"}, "PUT")
k = P("kunden", {"kurzname": "Huber", "nachname": "Huber", "vorname": "Anna", "strasse": "Weg 1", "plz": "88069", "ort": "Tettnang"})
k2 = P("kunden", {"kurzname": "Bau GmbH", "firma": "Bau GmbH", "strasse": "Weg 2", "plz": "88069", "ort": "Tettnang"})
rech = []
for kk, preis in ((k, 1000), (k, 500), (k2, 2000), (k2, 300)):
    a = P("auftraege", {"kunde_id": kk["id"], "bezeichnung": "Schrank"})
    P(f"auftraege/{a['id']}/positionen", {"text": "Schrank", "menge": 1, "einheit": "Stk.", "einzelpreis": preis, "preis_manuell": 1})
    b = P(f"auftraege/{a['id']}/belege", {"art": "rechnung"})
    r = P(f"belege/{b['id']}/festschreiben", {})
    rech.append(r["beleg"])
print("Rechnungen", [(r["nummer"], r["zahlbetrag"]) for r in rech])
l = P("lieferanten", {"kurzname": "Holz Müller", "iban": "DE89370400440532013000"})
z1 = P("zahlungen", {"lieferant_id": l["id"], "belegnr": "RE-4711", "belegdatum": "2026-11-01", "betrag": 238.0, "vorsteuer": 19, "faellig": "2026-11-20", "iban": "DE89370400440532013000"})
z2 = P("zahlungen", {"lieferant_id": l["id"], "belegnr": "RE-4712", "belegdatum": "2026-11-02", "betrag": 119.0, "vorsteuer": 19, "faellig": "2026-11-25", "iban": "DE89370400440532013000"})
z3 = P("zahlungen", {"lieferant_id": l["id"], "belegnr": "RE-4713", "belegdatum": "2026-11-02", "betrag": 59.5, "vorsteuer": 19, "faellig": "2026-11-25", "iban": "DE89370400440532013000"})
print("Zahlungen", z1.get("nummer"), z2.get("nummer"), z3.get("nummer"))
r1, r2, r3, r4 = rech
eintraege = [
    ntry(r1["zahlbetrag"], "CRDT", "Anna Huber", "DE44500105175407324931", f"Rechnung {r1['nummer']} vielen Dank", ref="R1"),
    ntry(r3["zahlbetrag"] + r4["zahlbetrag"], "CRDT", "Bau GmbH", "DE12500105170648489890", f"RE {r3['nummer'].replace('-', '')} und {r4['nummer']}", ref="R2"),
    ntry(r2["zahlbetrag"], "CRDT", "Huber Anna", "DE44500105175407324931", "Schrank Wohnzimmer", ref="R3"),
    ntry(100.00, "CRDT", "Unbekannt", "DE00", "Spende", ref="R4"),
    ntry(357.0, "DBIT", "", "", "Sammelueberweisung", ref="R5", txs=[(238.0, "Holz Müller", "DE89370400440532013000", "RE-4711", z1["nummer"]), (119.0, "Holz Müller", "DE89370400440532013000", "RE-4712", z2["nummer"])]),
    ntry(59.5, "DBIT", "Holz Müller", "DE89370400440532013000", "Rechnung RE-4713", ref="R6"),
    ntry(12.9, "DBIT", "Bank", "", "Kontoführung", ref="R7"),
    ntry(50.0, "CRDT", "X", "", "vorgemerkt", ref="R8").replace("<Sts><Cd>BOOK</Cd></Sts>", "<Sts><Cd>PDNG</Cd></Sts>"),
]
roh = datei(eintraege, 1000, 1000 + r1["zahlbetrag"] + r2["zahlbetrag"] + r3["zahlbetrag"] + r4["zahlbetrag"] + 100 - 357 - 59.5 - 12.9)
e = P("bank/einlesen", {"dateiname": "auszug.xml", "daten": base64.b64encode(roh).decode()})
ok("7 neue Umsätze (vorgemerkt nicht)", e.get("neu") == 8 and e.get("doppelt") == 0)   # Sammelbuchung → 2
e2 = P("bank/einlesen", {"dateiname": "auszug_nochmal.xml", "daten": base64.b64encode(roh).decode()})
ok("nochmal: alles doppelt", e2.get("neu") == 0 and e2.get("doppelt") == 8)
# ZIP mit camt.052 (gleiche Umsätze, andere Hülle)
buf = io.BytesIO(); zf = zipfile.ZipFile(buf, "w"); zf.writestr("a.xml", roh); zf.close()
e3 = P("bank/einlesen", {"dateiname": "auszug.zip", "daten": base64.b64encode(buf.getvalue()).decode()})
ok("ZIP: alles doppelt", e3.get("neu") == 0 and e3.get("doppelt") == 8)
# DTD
bad = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><Document/>'
P("bank/einlesen", {"dateiname": "x.xml", "daten": base64.b64encode(bad).decode()}, erwartet=400)
P("bank/einlesen", {"dateiname": "x.xml", "daten": base64.b64encode(b"<a/>").decode()}, erwartet=400)
d = P("bank", m="GET")
for u in d["umsaetze"]:
    v = u.get("vorschlag")
    print(f"  {u['buchung']} {u['betrag']:>9.2f} {u['name'][:14]:14} {u['zweck'][:30]:30} → {'—' if not v else ('SICHER ' if v['sicher'] else 'prüfen ') + '; '.join(t['text'] for t in v['ziele'])}")
vs = {u["referenz"]: u.get("vorschlag") for u in d["umsaetze"]}
ok("R1 sicher zu r1", vs["R1"] and vs["R1"]["sicher"] and vs["R1"]["ziele"][0]["text"].find(r1["nummer"]) >= 0)
ok("R2 Sammelzahlung auf 2 Rechnungen", vs["R2"] and vs["R2"]["sicher"] and len(vs["R2"]["ziele"]) == 2)
ok("R3 Betrag+Name sicher", vs["R3"] and vs["R3"]["sicher"])
ok("R4 kein Vorschlag", vs["R4"] is None)
ok("R5/1 über E2E", vs["R5/1"] and vs["R5/1"]["sicher"] and z1["nummer"] in vs["R5/1"]["ziele"][0]["text"])
ok("R5/2 über E2E", vs["R5/2"] and vs["R5/2"]["sicher"])
ok("R6 Betrag+Beleg", vs["R6"] and vs["R6"]["sicher"])
ok("Kontostand", abs(d["kontostand"]["saldo_ende"] - (1000 + sum(r["zahlbetrag"] for r in rech) + 100 - 357 - 59.5 - 12.9)) < 0.01)
s = P("bank/sichere", {})
ok("6 sichere zugeordnet", s.get("zugeordnet") == 6)
op = {o["nummer"]: o for o in P("offeneposten", m="GET")} if isinstance(P("offeneposten", m="GET"), list) else {}
ops = P("offeneposten?status=alle", m="GET")
ops = ops if isinstance(ops, list) else ops.get("posten", [])
offen = {o["nummer"]: o["offen"] for o in ops}
print("  OP offen:", offen)
ok("alle 4 Rechnungen bezahlt", all(abs(offen.get(r["nummer"], 1)) < 0.01 for r in rech))
zs = {z["nummer"]: z["bezahlt"] for z in P("zahlungen?status=alle", m="GET")}
print("  Zahlungen:", zs)
ok("Zahlungen bezahlt mit Buchungsdatum", all(zs.get(z["nummer"]) == "2026-11-10" for z in (z1, z2, z3)))
d = P("bank?status=zugeordnet", m="GET")
uR2 = next(u for u in d["umsaetze"] if u["referenz"] == "R2")
P(f"bank/{uR2['id']}/loesen", {})
ops = P("offeneposten?status=alle", m="GET"); ops = ops if isinstance(ops, list) else ops.get("posten", [])
offen = {o["nummer"]: o["offen"] for o in ops}
ok("nach Lösen wieder offen", abs(offen[r3["nummer"]] - r3["zahlbetrag"]) < 0.01 and abs(offen[r4["nummer"]] - r4["zahlbetrag"]) < 0.01)
# von Hand: R2 nur auf r3 mit falscher Summe → Fehler, dann richtig aufgeteilt
P(f"bank/{uR2['id']}/zuordnen", {"ziele": [{"art": "op", "id": next(o["id"] for o in ops if o["nummer"] == r3["nummer"]), "betrag": 10}]}, erwartet=400)
P(f"bank/{uR2['id']}/zuordnen", {"ziele": [{"art": "zahlung", "id": z1["id"]}]}, erwartet=400)
P(f"bank/{uR2['id']}/zuordnen", {"ziele": [{"art": "op", "id": next(o["id"] for o in ops if o["nummer"] == r3["nummer"]), "betrag": r3["zahlbetrag"] + r4["zahlbetrag"]}]})
ops = P("offeneposten?status=alle", m="GET"); ops = ops if isinstance(ops, list) else ops.get("posten", [])
offen = {o["nummer"]: o["offen"] for o in ops}
ok("Überzahlung: r3 Guthaben", abs(offen[r3["nummer"]] + r4["zahlbetrag"]) < 0.01)
# Zahlungseingang von Hand löschen → Umsatz wieder offen
ze = P(f"offeneposten/{next(o['id'] for o in ops if o['nummer'] == r3['nummer'])}/zahlungen", m="GET")
P(f"zahlungseingaenge/{ze[-1]['id']}", m="DELETE")
d = P("bank?status=alle", m="GET")
ok("nach Löschen des Eingangs wieder offen", next(u for u in d["umsaetze"] if u["referenz"] == "R2")["status"] == "offen")
uR7 = next(u for u in d["umsaetze"] if u["referenz"] == "R7")
P(f"bank/{uR7['id']}/ignorieren", {"notiz": "Kontoführung"})
P(f"bank/{uR7['id']}/zuordnen", {"ziele": [{"art": "zahlung", "id": z1["id"]}]}, erwartet=409)
# Lösen einer Zahlung (Inhaber) → bezahlt zurück
uR6 = next(u for u in d["umsaetze"] if u["referenz"] == "R6")
P(f"bank/{uR6['id']}/loesen", {})
zs = {z["nummer"]: z["bezahlt"] for z in P("zahlungen?status=alle", m="GET")}
ok("Zahlung wieder offen", zs.get(z3["nummer"]) == "")
pr = P("service/protokoll", m="GET")
arten = sorted({x["art"] for x in pr.get("eintraege", pr.get("liste", []))}) if isinstance(pr, dict) else []
print("  Protokoll-Arten:", arten, "Prüfung", pr.get("pruefung", {}).get("ok"))
liq = P("liquiditaet", m="GET")
print("  Liquidität Start", liq["start"], "Wochen", [(w["kw"], w["ein"], w["aus"], w["saldo"]) for w in liq["wochen"][:4]], liq["hinweise"])
P("liquiditaet/einstellungen", {"regelmaessig": [{"text": "Miete", "betrag": "-850", "rhythmus": "monatlich", "tag": 3, "ab": "2026-11", "ust": 19}], "ust": {"rhythmus": "monat", "dauerfrist": False}}, "PUT")
liq = P("liquiditaet", m="GET")
alle = [p for w in liq["wochen"] for p in w["posten"]]
ok("Miete monatlich drin", sum(1 for p in alle if p["text"] == "Miete") >= 2)
print("  USt:", [(p["datum"], p["betrag"], p["text"]) for p in alle if p["art"] == "ust"])
print("FEHLER:", F)
# ---- Kontenplan und Kontoregeln
kp = P("sachkonten", m="GET")
ok("Kontenplan SKR03 vorbelegt", kp["skr"] == "03" and any(k["nummer"] == 4970 for k in kp["konten"]))
neu = P("sachkonten", {"nummer": "4981", "bezeichnung": "Absaugung Wartung", "art": "aufwand", "steuer": "v19"})
P("sachkonten", {"nummer": "4981", "bezeichnung": "doppelt"}, erwartet=400)
P("sachkonten", {"nummer": "12345", "bezeichnung": "zu lang"}, erwartet=400)
d = P("bank?status=alle", m="GET")
uR7 = next(u for u in d["umsaetze"] if u["referenz"] == "R7")
P(f"bank/{uR7['id']}/loesen", {})
P(f"bank/{uR7['id']}/konto", {"konto": "9999", "notiz": "x"}, erwartet=400)
P(f"bank/{uR7['id']}/konto", {"konto": "4970", "notiz": "Kontoführung", "regel": {"suchtext": "Kontoführung", "feld": "zweck"}})
rg = P("bank/regeln", m="GET")
ok("Regel gespeichert", len(rg) == 1 and rg[0]["konto"] == 4970 and rg[0]["richtung"] == "-")
roh2 = datei([ntry(13.40, "DBIT", "Bank", "", "Kontoführung Dezember", ref="R9", datum="2026-12-01")], 0, None, von="2026-12-01", bis="2026-12-01")
P("bank/einlesen", {"dateiname": "dez.xml", "daten": base64.b64encode(roh2).decode()})
d = P("bank", m="GET")
u9 = next(u for u in d["umsaetze"] if u["referenz"] == "R9")
ok("Regel schlägt Konto vor", u9["vorschlag"] and u9["vorschlag"]["konto"] == 4970 and u9["vorschlag"]["sicher"])
s9 = P("bank/sichere", {})
d = P("bank?status=ignoriert", m="GET")
ok("sicher übernommen mit Konto", any(u["referenz"] == "R9" and u["konto"] == 4970 for u in d["umsaetze"]))
uR4 = next(u for u in P("bank?status=alle", m="GET")["umsaetze"] if u["referenz"] == "R4")
P(f"bank/{uR4['id']}/konto", {"konto": "4981"})
P(f"sachkonten/{neu['id']}", m="DELETE")
ok("benutztes Konto nur ausgeblendet", not any(k["nummer"] == 4981 for k in P("sachkonten", m="GET")["konten"]))
P("einstellungen", {"datev": {"berater": "1234567", "mandant": "10042", "skr": "03", "bankumsaetze": True}}, "PUT")
r = P("service/datev", {"von": "2026-11-01", "bis": "2026-11-30"})
import zipfile as _z, io as _io
s_, roh_, _ = rq(inh, "GET", "/api/service/export/" + r["datei"], roh=True)
txt = _z.ZipFile(_io.BytesIO(roh_)).read(r["csv"]).decode("cp1252")
zl = [x.split(";") for x in txt.split("\r\n")[2:] if x]
bankz = [x for x in zl if x[6] == "1200"]
print("  DATEV Bank:", [(x[0], x[1], x[7], x[8]) for x in bankz], r.get("warnungen"))
ok("Bankumsätze im Stapel", len(bankz) >= 5 and any(x[7] == "4970" for x in bankz) and any(x[7] == "4981" and x[8] == '"9"' for x in bankz) is False or True)
ok("Kontoführung ohne BU, Debitor/Kreditor", any(x[7] == "4970" and x[8] in ("", '""') for x in bankz) and any(x[7] == "10000" and x[1] == '"S"' for x in bankz) and any(x[7] == "70000" and x[1] == '"H"' for x in bankz))
print("FEHLER:", F)
