"""Version 149, Kontoauszüge: sichere Vorschläge einzeln neu prüfen, Wiedererkennen mit Buchungstag (auch für Auszüge aus
früheren Versionen), Hinweise auf Lücke, Summe, fremdes Konto und fremde Währung. Erwartet eine frische Prüfinstanz."""
import json, re, sys, base64, time, os, sqlite3, hashlib
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:500]))
    if not bed: fehler.append(name)
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None):
    s, b, hd = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
EIGEN, FREMD = "DE02120300000000202051", "DE89370400440532013000"
A("PUT", "einstellungen", {"sepa_iban": EIGEN, "firma": "Muster Schreinerei", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890", "firma_inhaber": "Jonas Muster"})
def ntry(betrag, name="Kunde", zweck="", iban="DE44500105175407324931", ref=None, tag="2026-11-10", cd="CRDT", ccy="EUR", sts="BOOK"):
    partei = f"<Dbtr><Nm>{name}</Nm></Dbtr>" if cd == "CRDT" else f"<Cdtr><Nm>{name}</Nm></Cdtr>"
    konto = f"<DbtrAcct><Id><IBAN>{iban}</IBAN></Id></DbtrAcct>" if cd == "CRDT" else f"<CdtrAcct><Id><IBAN>{iban}</IBAN></Id></CdtrAcct>"
    return (f'<Ntry><Amt Ccy="{ccy}">{betrag:.2f}</Amt><CdtDbtInd>{cd}</CdtDbtInd><Sts>{sts}</Sts><BookgDt><Dt>{tag}</Dt></BookgDt><ValDt><Dt>{tag}</Dt></ValDt>' + (f"<AcctSvcrRef>{ref}</AcctSvcrRef>" if ref else "") +
            f"<NtryDtls><TxDtls><RltdPties>{partei}{konto}</RltdPties><RmtInf><Ustrd>{zweck}</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>")
def camt(eintraege, nr="1", anf=0.0, ende=None, iban=EIGEN, von="2026-11-10", bis=None, anfang_art="PRCD"):
    summe = sum(float(re.search(r">(-?[\d.]+)</Amt>", e).group(1)) * (-1 if "<CdtDbtInd>DBIT" in e else 1) for e in eintraege if "<Sts>BOOK" in e)
    ende = anf + summe if ende is None else ende
    bal = lambda cd, betrag, tag: f'<Bal><Tp><CdOrPrtry><Cd>{cd}</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">{abs(betrag):.2f}</Amt><CdtDbtInd>{"CRDT" if betrag >= 0 else "DBIT"}</CdtDbtInd><Dt><Dt>{tag}</Dt></Dt></Bal>'
    return (f'<?xml version="1.0" encoding="UTF-8"?><Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><GrpHdr><MsgId>M{nr}</MsgId><CreDtTm>{von}T20:00:00</CreDtTm></GrpHdr><Stmt><Id>S{nr}</Id>'
            f'<CreDtTm>{von}T20:00:00</CreDtTm><FrToDt><FrDtTm>{von}T00:00:00</FrDtTm><ToDtTm>{bis or von}T23:59:59</ToDtTm></FrToDt><Acct><Id><IBAN>{iban}</IBAN></Id></Acct>{bal(anfang_art, anf, von)}{bal("CLBD", ende, bis or von)}{"".join(eintraege)}</Stmt></BkToCstmrStmt></Document>').encode()
def ein(roh, name="auszug.xml"):
    return A("POST", "bank/einlesen", {"daten": base64.b64encode(roh).decode(), "dateiname": name})
def offen(): return [u for u in A("GET", "bank?status=offen")["umsaetze"]]
k = A("POST", "kunden", {"kurzname": "Zahler, Zacharias", "nachname": "Zahler", "vorname": "Zacharias", "plz": "88069", "ort": "Tettnang"})
def rechnung(betrag):
    a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Bank"}); po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Leistung"}); pid = po.get("id") or po["position"]["id"]
    A("PUT", f"positionen/{pid}", {"einzelpreis": betrag, "preis_manuell": 1, "menge": 1}); b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); A("POST", f"belege/{b['id']}/festschreiben", {}); return A("GET", f"belege/{b['id']}")
def op_von(nummer): return next(o for o in (lambda x: x.get("liste") or x.get("posten") or [])(A("GET", "offeneposten?status=alle")) if o["nummer"] == nummer)

print("== I1: sichere Vorschläge")
r1, r2, r3 = rechnung(1000), rechnung(2000), rechnung(500)
x = ein(camt([ntry(1190, "Zacharias Zahler", f"Rechnung {r1['nummer']}", ref="A1"),              # Nummer + Betrag: sicher
              ntry(1190, "Zacharias Zahler", "Vielen Dank", ref="A2"),                             # nur Betrag + Name: derselbe Posten
              ntry(1190, "Zacharias Zahler", f"Rechnung {r1['nummer']} nochmal", ref="A3"),        # doppelt überwiesen
              ntry(2380, "Zacharias Zahler", f"RE {r2['nummer']}", ref="A4"),
              ntry(2380, "Z. Zahler", "Zahlung", ref="A5", tag="2026-11-11")], nr="1", bis="2026-11-11"))
ok("Auszug eingelesen (5 Umsätze)", x["_s"] == 200 and x["neu"] == 5, x)
us = offen(); sich = [u for u in us if (u.get("vorschlag") or {}).get("sicher")]
ok("von drei Umsätzen zu Rechnung 1 gilt nur einer als sicher, von zweien zu Rechnung 2 ebenfalls", len(sich) == 2 and {u["referenz"] for u in sich} == {"A1", "A4"}, [(u["referenz"], u["vorschlag"]["sicher"], u["vorschlag"]["grund"]) for u in us if u.get("vorschlag")])
ok("die übrigen nennen den Grund („derselbe Posten passt auch zum Umsatz vom …“)", sum(1 for u in us if "derselbe Posten passt auch" in ((u.get("vorschlag") or {}).get("grund") or "")) >= 2, [(u["referenz"], (u.get("vorschlag") or {}).get("grund")) for u in us])
s = A("POST", "bank/sichere", {})
o1, o2 = op_von(r1["nummer"]), op_von(r2["nummer"])
ok("„Alle sicheren übernehmen“ bucht zwei Umsätze – jede Rechnung genau einmal bezahlt (offen 0,00, nicht negativ)", s["zugeordnet"] == 2 and abs(o1["offen"]) < 0.005 and abs(o2["offen"]) < 0.005, (s, o1["offen"], o2["offen"]))
us = offen()
ok("die drei weiteren Umsätze bleiben offen und ohne sicheren Vorschlag", len(us) == 3 and not any((u.get("vorschlag") or {}).get("sicher") for u in us), [(u["referenz"], u.get("vorschlag")) for u in us])
# Stand ändert sich zwischen Anzeige und Übernahme: zwei Umsätze, die erst nacheinander passen
r4, r5 = rechnung(300), rechnung(300)
x = ein(camt([ntry(357, "Zacharias Zahler", f"Rechnung {r4['nummer']}", ref="B1", tag="2026-11-12"), ntry(357, "Zacharias Zahler", f"Rechnung {r4['nummer']}", ref="B2", tag="2026-11-12")], nr="2", anf=7140, von="2026-11-12"))
s = A("POST", "bank/sichere", {}); o4, o5 = op_von(r4["nummer"]), op_von(r5["nummer"])
ok("zwei gleiche Zahlungen mit derselben Rechnungsnummer: eine wird gebucht, die Rechnung ist nicht überzahlt, die zweite Rechnung bleibt offen", s["zugeordnet"] == 1 and abs(o4["offen"]) < 0.005 and abs(o5["offen"] - 357) < 0.005, (s, o4["offen"], o5["offen"]))

print("== I2: Wiedererkennen")
x = ein(camt([ntry(50, "Anna Alt", "Miete", ref="NONREF", tag="2026-11-13"), ntry(50, "Bernd Blau", "Spende", ref="NONREF", tag="2026-11-14"), ntry(50, "Anna Alt", "Miete", ref="NONREF", tag="2026-11-14")], nr="3", anf=7854, von="2026-11-13", bis="2026-11-14"))
ok("drei verschiedene Umsätze mit dem Platzhalter „NONREF“ und gleichem Betrag: alle drei werden angelegt (bisher nur einer)", x["neu"] == 3 and x["doppelt"] == 0, x)
x2 = ein(camt([ntry(50, "Anna Alt", "Miete", ref="NONREF", tag="2026-11-13"), ntry(50, "Bernd Blau", "Spende", ref="NONREF", tag="2026-11-14"), ntry(50, "Anna Alt", "Miete", ref="NONREF", tag="2026-11-14")], nr="3b", anf=7854, von="2026-11-13", bis="2026-11-14"), "nochmal.xml")
ok("dieselben drei noch einmal eingelesen: alle als „schon vorhanden“ erkannt", x2["neu"] == 0 and x2["doppelt"] == 3, x2)
x = ein(camt([ntry(77, "Carla", "Abschlag", ref="REF-77", tag="2026-11-15")], nr="4", anf=8004, von="2026-11-15"))
x2 = ein(camt([ntry(77, "Carla", "Abschlag", ref="REF-77", tag="2026-11-17")], nr="5", anf=8081, von="2026-11-17"))
ok("gleiche Bankreferenz und gleicher Betrag an einem anderen Buchungstag: eigener Umsatz (bisher verworfen)", x["neu"] == 1 and x2["neu"] == 1 and x2["doppelt"] == 0, (x, x2))
x3 = ein(camt([ntry(77, "Carla", "Abschlag", ref="REF-77", tag="2026-11-15"), ntry(77, "Carla", "Abschlag", ref="REF-77", tag="2026-11-17")], nr="6", anf=8004, von="2026-11-15", bis="2026-11-17"), "monat.xml")
ok("Monatsauszug mit beiden: beide als „schon vorhanden“ erkannt", x3["neu"] == 0 and x3["doppelt"] == 2, x3)
# Umsätze, die eine frühere Programmversion eingelesen hat (Schlüssel ohne Buchungstag)
con = sqlite3.connect(D + "/buero.db", timeout=20)
def alt_schluessel(iban, ref, betrag, nr=1): return hashlib.sha256(f"{iban}|ref|{ref}|{betrag:.2f}#{nr}".encode()).hexdigest()
aid = con.execute("INSERT INTO bank_auszuege (datei, ablage, format, iban, von, bis, saldo_anfang, saldo_ende, saldo_datum, importiert) VALUES ('alt.xml','','camt.053',?,?,?,?,?,?,?)", (EIGEN, "2026-10-01", "2026-10-02", 0, 311, "2026-10-02", "2026-10-02T08:00:00")).lastrowid
for ref, betrag, name, zweck, tag, nr in (("ALT-1", 111.0, "Dora", "Rechnung alt", "2026-10-01", 1), ("NONREF", 100.0, "Emil", "Pacht", "2026-10-01", 1), ("NONREF", 100.0, "Emil", "Pacht", "2026-10-02", 2)):
    con.execute("INSERT INTO bank_umsaetze (auszug_id, iban, buchung, valuta, betrag, name, gegen_iban, zweck, e2e, referenz, schluessel, angelegt) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (aid, EIGEN, tag, tag, betrag, name, "DE44500105175407324931", zweck, "", ref, alt_schluessel(EIGEN, ref, betrag, nr), "2026-10-02T08:00:00"))
con.commit(); con.close()
x = ein(camt([ntry(111, "Dora", "Rechnung alt", ref="ALT-1", tag="2026-10-01"), ntry(100, "Emil", "Pacht", ref="NONREF", tag="2026-10-01"), ntry(100, "Emil", "Pacht", ref="NONREF", tag="2026-10-02"),
              ntry(100, "Frieda", "Beitrag", ref="NONREF", tag="2026-10-02"), ntry(111, "Dora", "Rechnung neu", ref="ALT-1", tag="2026-10-05")], nr="7", anf=0, von="2026-10-01", bis="2026-10-05"), "oktober.xml")
ok("Auszug, den eine frühere Version schon eingelesen hat: 3 Umsätze wiedererkannt, 2 wirklich neue angelegt", x["doppelt"] == 3 and x["neu"] == 2, x)

print("== I3: Hinweise")
con = sqlite3.connect(D + "/buero.db", timeout=20); con.execute("DELETE FROM bank_umsaetze"); con.execute("DELETE FROM bank_auszuege"); con.commit(); con.close()
x = ein(camt([ntry(10, "A", "eins", ref="H1", tag="2026-09-01")], nr="10", anf=1000, von="2026-09-01"), "h1.xml")
ok("vollständiger erster Auszug des eigenen Kontos: kein Hinweis", x["_s"] == 200 and x["hinweise"] == [], x.get("hinweise"))
x = ein(camt([ntry(10, "A", "zwei", ref="H2", tag="2026-09-02")], nr="11", anf=1010, von="2026-09-02"), "h2.xml")
ok("lückenlos anschließender Auszug: kein Hinweis", x["hinweise"] == [], x.get("hinweise"))
x = ein(camt([ntry(10, "A", "vier", ref="H4", tag="2026-09-04")], nr="12", anf=5000, von="2026-09-04"), "h4.xml")
ok("Anfangssaldo passt nicht zum letzten Endsaldo: Hinweis auf einen fehlenden Auszug", len(x["hinweise"]) == 1 and "fehlt mindestens ein Auszug" in x["hinweise"][0] and "1.020,00 €" in x["hinweise"][0] and "5.000,00 €" in x["hinweise"][0], x.get("hinweise"))
x = ein(camt([ntry(10, "A", "fünf", ref="H5", tag="2026-09-05")], nr="13", anf=5010, ende=5999, von="2026-09-05"), "h5.xml")
ok("Umsätze ergeben nicht den Endsaldo: Hinweis auf eine unvollständige Datei", any("unvollständig" in h and "5.999,00 €" in h for h in x["hinweise"]), x.get("hinweise"))
x = ein(camt([ntry(10, "A", "fremd", ref="H6", tag="2026-09-06")], nr="14", anf=0, iban=FREMD, von="2026-09-06"), "fremd.xml")
ok("Auszug eines anderen Kontos: Hinweis mit beiden Kontonummern", any(FREMD in h and EIGEN in h and "eigenes Konto" in h for h in x["hinweise"]), x.get("hinweise"))
x = ein(camt([ntry(10, "A", "fremd 2", ref="H7", tag="2026-09-07")], nr="15", anf=10, iban=FREMD, von="2026-09-07"), "fremd2.xml")
ok("zweiter Auszug desselben (nun bekannten) Kontos: kein Hinweis mehr", x["hinweise"] == [], x.get("hinweise"))
x = ein(camt([ntry(25, "US Customer", "Invoice", ref="H8", tag="2026-09-08", ccy="USD")], nr="16", anf=5999, von="2026-09-08"), "usd.xml")
ok("Umsatz in US-Dollar: Hinweis, dass ohne Umrechnung übernommen wurde", any("USD" in h and "ohne Umrechnung" in h for h in x["hinweise"]), x.get("hinweise"))
x = ein(camt([ntry(10, "A", "gebucht", ref="H9", tag="2026-09-09"), ntry(99, "B", "vorgemerkt", ref="H9b", tag="2026-09-09", sts="PDNG")], nr="17", anf=6024, von="2026-09-09"), "vorgemerkt.xml")
ok("Auszug mit einem vorgemerkten Umsatz: der wird nicht übernommen, eine Summenprüfung gibt es dann nicht (kein falscher Alarm)", x["neu"] == 1 and not any("unvollständig" in h for h in x["hinweise"]), x)
d = A("GET", "bank?status=alle")["dateien"]; mit = {f["datei"]: f.get("hinweise") for f in d}
ok("die Hinweise stehen dauerhaft an der Datei (Liste „Eingelesene Dateien“)", len(mit.get("h4.xml") or []) == 1 and len(mit.get("usd.xml") or []) >= 1 and (mit.get("h1.xml") or []) == [], mit)
pr = A("GET", "service/protokoll?art=bank_import")["eintraege"]
ok("und im Protokoll des Einlesens", any("Hinweise:" in e["text"] and "fehlt mindestens ein Auszug" in e["text"] for e in pr), [e["text"][:120] for e in pr[:3]])
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
