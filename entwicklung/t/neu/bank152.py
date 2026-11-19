"""Version 152, Kontoauszüge und Skonto: Lieferanten-Skonto als Prozent (I14), Nachname statt Vorname (I7), bekanntes Zahlerkonto (I12),
Skonto bei Kundenzahlungen im Kontoauszug und von Hand (F4), Sammelüberweisung aus der eigenen SEPA-Datei (I8), Sammelbuchung ohne
Einzelbeträge und Rückbuchung (I12), Suchmuster je Nummer nur einmal (P5). Erwartet eine frische Prüfinstanz."""
import json, re, sys, base64, sqlite3, random
from datetime import date, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:600]))
    if not bed: fehler.append(name)
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, h=None):
    s, b, hd = rq(inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
RF = {"X-Rueckfrage": "1"}
EIGEN = "DE02120300000000202051"; H = date.today().isoformat(); tag = lambda n: (date.today() + timedelta(days=n)).isoformat()
A("PUT", "einstellungen", {"sepa_iban": EIGEN, "sepa_name": "Muster Schreinerei", "firma": "Muster Schreinerei", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890", "firma_inhaber": "Jonas Muster"})
def ntry(betrag, name="Kunde", zweck="", iban="DE44500105175407324931", ref=None, t=None, cd="CRDT", e2e="", extra="", txs=None):
    t = t or H
    partei = f"<Dbtr><Nm>{name}</Nm></Dbtr>" if cd == "CRDT" else f"<Cdtr><Nm>{name}</Nm></Cdtr>"
    konto = f"<DbtrAcct><Id><IBAN>{iban}</IBAN></Id></DbtrAcct>" if cd == "CRDT" else f"<CdtrAcct><Id><IBAN>{iban}</IBAN></Id></CdtrAcct>"
    details = txs if txs is not None else f"<TxDtls>{'<Refs><EndToEndId>' + e2e + '</EndToEndId></Refs>' if e2e else ''}<RltdPties>{partei}{konto}</RltdPties><RmtInf><Ustrd>{zweck}</Ustrd></RmtInf></TxDtls>"
    return (f'<Ntry><Amt Ccy="EUR">{betrag:.2f}</Amt><CdtDbtInd>{cd}</CdtDbtInd>{extra}<Sts>BOOK</Sts><BookgDt><Dt>{t}</Dt></BookgDt><ValDt><Dt>{t}</Dt></ValDt>' + (f"<AcctSvcrRef>{ref}</AcctSvcrRef>" if ref else "") +
            f"<NtryDtls>{details}</NtryDtls></Ntry>")
nr_datei = [0]
def camt(eintraege):
    nr_datei[0] += 1; nr = nr_datei[0]
    return (f'<?xml version="1.0" encoding="UTF-8"?><Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.052.001.02"><BkToCstmrAcctRpt><GrpHdr><MsgId>M{nr}</MsgId><CreDtTm>{H}T20:00:00</CreDtTm></GrpHdr><Rpt><Id>S{nr}</Id>'
            f'<CreDtTm>{H}T20:00:00</CreDtTm><Acct><Id><IBAN>{EIGEN}</IBAN></Id></Acct>{"".join(eintraege)}</Rpt></BkToCstmrAcctRpt></Document>').encode("utf-8")
def ein(eintraege): return A("POST", "bank/einlesen", {"daten": base64.b64encode(camt(eintraege)).decode(), "dateiname": f"auszug{nr_datei[0] + 1}.xml"})
def offen(): return A("GET", "bank?status=offen")["umsaetze"]
def umsatz(merk): return next((u for u in offen() if merk in (u.get("zweck") or "") + (u.get("name") or "") + (u.get("referenz") or "")), None)
con = sqlite3.connect(D + "/buero.db", timeout=30); con.row_factory = sqlite3.Row
def kunde(nach, vor, **mehr):
    k = A("POST", "kunden", {"kurzname": f"{nach}, {vor}", "nachname": nach, "vorname": vor, "plz": "88069", "ort": "Tettnang"})
    if mehr: A("PUT", f"kunden/{k['id']}", mehr)
    return k["id"]
def rechnung(kid, netto):
    a = A("POST", "auftraege", {"kunde_id": kid, "bezeichnung": "Bank"}); po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Leistung"}); pid = po.get("id") or po["position"]["id"]
    A("PUT", f"positionen/{pid}", {"einzelpreis": netto, "preis_manuell": 1, "menge": 1}); b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); A("POST", f"belege/{b['id']}/festschreiben", {})
    r = A("GET", f"belege/{b['id']}"); o = con.execute("select * from offene_posten where beleg_id=?", (b["id"],)).fetchone(); return r, dict(o)
def op(i): return dict(con.execute("select * from offene_posten where id=?", (i,)).fetchone())
def eing(i): return [(r["betrag"], r["art"]) for r in con.execute("select betrag, art from zahlungseingaenge where op_id=? order by id", (i,))]

print("== I7: Nachname statt Vorname, Umlaute")
k_maier = kunde("Maier", "Peter"); k_mueller = kunde("Müller", "Hans")
r1, o1 = rechnung(k_maier, 652.94)   # 777,00 brutto
ok("Rechnung über 777,00 € angelegt", abs(o1["betrag"] - 777.0) < 0.005, o1["betrag"])
ein([ntry(777.00, "Peter Schmidt", "Danke fuer alles", ref="A1")])
u = umsatz("Danke fuer alles"); v = u.get("vorschlag") or {}
ok("gleicher Vorname, anderer Nachname: Vorschlag nur zum Prüfen, nicht sicher", v and v.get("sicher") is False and "nur der Betrag" in v.get("grund", ""), v)
A("POST", f"bank/{u['id']}/konto", {"konto": 1800, "notiz": "Probe"}) if False else None
con.execute("delete from bank_umsaetze where id=?", (u["id"],)); con.commit()
ein([ntry(777.00, "PETER MAIER", "Vielen Dank", ref="A2")])
u = umsatz("Vielen Dank"); v = u.get("vorschlag") or {}
ok("Nachname passt: sicher (Betrag und Name)", v.get("sicher") is True and "Name" in v.get("grund", ""), v)
con.execute("delete from bank_umsaetze where id=?", (u["id"],)); con.commit()
r2, o2 = rechnung(k_mueller, 279.83)   # 333,00
ein([ntry(o2["betrag"], "HANS MUELLER", "Zahlung", ref="A3")])
u = umsatz("A3") or umsatz("HANS MUELLER"); v = (u or {}).get("vorschlag") or {}
ok("Müller zahlt als MUELLER: Name wird erkannt", v.get("sicher") is True, v)
z = A("POST", f"bank/{u['id']}/zuordnen", {"ziele": v["ziele"]}); ok("Zuordnung gebucht", z["_s"] == 200 and abs(op(o2["id"])["offen"]) < 0.005, z)

print("== I12: Konto, von dem der Kunde schon bezahlt hat")
r3, o3 = rechnung(k_mueller, 100.00)
ein([ntry(o3["betrag"], "Sparverein Tettnang eV", "ohne Angabe", iban="DE44500105175407324931", ref="A4")])
u = umsatz("Sparverein"); v = u.get("vorschlag") or {}
ok("Zahlung vom bekannten Konto des Kunden unter fremdem Namen: sicher", v.get("sicher") is True and "Konto" in v.get("grund", ""), v)
ok("Tabelle der Zahlerkonten enthält das Konto", con.execute("select count(*) from bank_kundenkonten where iban='DE44500105175407324931' and kunde_id=?", (k_mueller,)).fetchone()[0] == 1)
erste = con.execute("select id from bank_umsaetze where referenz='A3'").fetchone()[0]
A("POST", f"bank/{erste}/loesen", {})
v2 = (umsatz("Sparverein") or {}).get("vorschlag") or {}
ok("nach dem Lösen der ersten Zuordnung gilt das Konto nicht mehr als bekannt", v2.get("sicher") is False or not v2, v2)
con.execute("delete from bank_umsaetze where status='offen'"); con.commit()

print("== F4: Skonto bei Kundenzahlungen")
k_sk = kunde("Skontomann", "Sven", skonto=2, skontotage=10)
r4, o4 = rechnung(k_sk, 1000.00)
ok("offener Posten trägt Skontosatz und Frist der Rechnung", o4["skonto"] == 2 and o4["skonto_bis"] == tag(10), (o4["skonto"], o4["skonto_bis"]))
lst = A("GET", "offeneposten?status=offen"); zeile = next(x for x in (lst.get("liste") or []) if x["id"] == o4["id"])
ok("Liste der offenen Posten nennt den vereinbarten Skontobetrag (23,80 €)", abs(zeile.get("skonto_betrag", 0) - 23.80) < 0.005, zeile.get("skonto_betrag"))
ein([ntry(1166.20, "Sven Skontomann", f"Rechnung {r4['nummer']} abzgl. 2% Skonto", iban="DE91100000000123456789", ref="S1")])
u = umsatz("S1") or umsatz(r4["nummer"]); v = u.get("vorschlag") or {}
ok("Zahlung abzüglich 2 % mit Rechnungsnummer in der Frist: sicher, mit Skonto 23,80 €", v.get("sicher") is True and abs((v["ziele"][0].get("skonto") or 0) - 23.80) < 0.005 and "Skonto" in v.get("grund", ""), v)
z = A("POST", f"bank/{u['id']}/zuordnen", {"ziele": v["ziele"]})
ok("übernommen: Rechnung ausgeglichen, Zahlung 1.166,20 € und Skonto 23,80 € gebucht", z["_s"] == 200 and abs(op(o4["id"])["offen"]) < 0.005 and eing(o4["id"]) == [(1166.2, "Überweisung"), (23.8, "Skonto")], (z, op(o4["id"])["offen"], eing(o4["id"])))
los = A("POST", f"bank/{u['id']}/loesen", {})
ok("Zuordnung lösen nimmt Zahlung und Skonto zurück", los["_s"] == 200 and abs(op(o4["id"])["offen"] - 1190.0) < 0.005 and eing(o4["id"]) == [], (op(o4["id"])["offen"], eing(o4["id"])))
con.execute("update offene_posten set skonto_bis=? where id=?", (tag(-10), o4["id"])); con.commit()
v = (umsatz("S1") or umsatz(r4["nummer"])).get("vorschlag") or {}
ok("Frist seit zehn Tagen abgelaufen: Vorschlag nur zum Prüfen, nennt das Fristende", v.get("sicher") is False and "Skontofrist" in v.get("grund", ""), v)
con.execute("update offene_posten set skonto_bis=? where id=?", (tag(-2), o4["id"])); con.commit()
v = (umsatz("S1") or umsatz(r4["nummer"])).get("vorschlag") or {}
ok("Frist vor zwei Tagen abgelaufen: gilt noch als rechtzeitig (drei Tage Nachlauf)", v.get("sicher") is True, v)
con.execute("delete from bank_umsaetze where status='offen'"); con.execute("update offene_posten set skonto_bis=? where id=?", (tag(10), o4["id"])); con.commit()
ein([ntry(1166.20, "Sven Skontomann", "Danke", iban="DE91100000000123456789", ref="S2")])
v = (umsatz("S2") or umsatz("Danke")).get("vorschlag") or {}
ok("ohne Rechnungsnummer, Betrag = Rechnung abzüglich Skonto: Vorschlag zum Prüfen mit Skonto", v.get("sicher") is False and v.get("ziele") and abs((v["ziele"][0].get("skonto") or 0) - 23.80) < 0.005 and "Name passt" in v.get("grund", ""), v)
u = umsatz("S2") or umsatz("Danke")
z = A("POST", f"bank/{u['id']}/zuordnen", {"ziele": [{"art": "op", "id": o4["id"], "betrag": 1166.20, "skonto": 50.0}]})
ok("Skonto über den Rest hinaus wird beim Zuordnen abgewiesen", z["_s"] == 400 and "Skonto" in str(z.get("fehler")), z)
z = A("POST", f"bank/{u['id']}/zuordnen", {"ziele": [{"art": "op", "id": o4["id"], "betrag": 1166.20}]})
ok("ohne Skonto zugeordnet: 23,80 € bleiben offen", z["_s"] == 200 and abs(op(o4["id"])["offen"] - 23.80) < 0.005, op(o4["id"])["offen"])
zeile = next(x for x in (A("GET", "offeneposten?status=offen").get("liste") or []) if x["id"] == o4["id"])
ok("Liste: Rest entspricht dem vereinbarten Skonto (skonto_offen 23,80 €, kein neuer Vorschlag auf den Rest)", abs(zeile.get("skonto_offen", 0) - 23.80) < 0.005 and not zeile.get("skonto_betrag"), (zeile.get("skonto_offen"), zeile.get("skonto_betrag")))
x = A("POST", f"offeneposten/{o4['id']}/zahlung", {"betrag": 0, "skonto": 0, "datum": H}, RF)
ok("weder Betrag noch Skonto: abgewiesen", x["_s"] == 400, x)
x = A("POST", f"offeneposten/{o4['id']}/zahlung", {"betrag": 0, "skonto": 23.80, "datum": H}, RF)
ok("reiner Skontoabzug über den Rest: gebucht, Rechnung ausgeglichen", x["_s"] == 200 and abs(op(o4["id"])["offen"]) < 0.005 and eing(o4["id"])[-1] == (23.8, "Skonto"), (x, op(o4["id"])["offen"], eing(o4["id"])))
r5, o5 = rechnung(k_sk, 500.00)
x = A("POST", f"offeneposten/{o5['id']}/zahlung", {"betrag": 476.00, "skonto": 119.00, "datum": H}, RF)
ok("Skonto 20 % statt vereinbarter 2 %: Rückfrage", x["_s"] == 409 and "mehr als vereinbart" in str(x.get("fehler")), x)
con.execute("update offene_posten set skonto_bis=? where id=?", (tag(-30), o5["id"])); con.commit()
x = A("POST", f"offeneposten/{o5['id']}/zahlung", {"betrag": 583.10, "skonto": 11.90, "datum": H}, RF)
ok("Skonto nach Ablauf der Frist: Rückfrage nennt das Fristende", x["_s"] == 409 and "Skontofrist" in str(x.get("fehler")), x)
x = A("POST", f"offeneposten/{o5['id']}/zahlung", {"betrag": 583.10, "skonto": 11.90, "datum": H}, {"X-Rueckfrage": "1", "X-Bestaetigt": "zahlung"})
ok("nach Bestätigung wird trotzdem gebucht", x["_s"] == 200 and abs(op(o5["id"])["offen"]) < 0.005, (x, op(o5["id"])["offen"]))
r6, o6 = rechnung(k_maier, 200.00)
x = A("POST", f"offeneposten/{o6['id']}/zahlung", {"betrag": 228.00, "skonto": 10.00, "datum": H}, RF)
ok("Skonto bei einer Rechnung ohne vereinbartes Skonto: Rückfrage", x["_s"] == 409 and "kein Skonto vereinbart" in str(x.get("fehler")), x)
x = A("POST", f"offeneposten/{o6['id']}/zahlung", {"betrag": 100.00, "skonto": -5, "datum": H}, RF)
ok("negatives Skonto: abgewiesen", x["_s"] == 400, x)
con.execute("delete from bank_umsaetze where status='offen'"); con.commit()

print("== I14: Lieferanten-Skonto ist ein Prozentsatz")
lf = A("POST", "lieferanten", {"kurzname": "Holzhandel", "firma": "Holzhandel KG", "iban": "DE75512108001245126199"})
def za(belegnr, betrag, skonto=0):
    return A("POST", "zahlungen", {"lieferant_id": lf["id"], "belegnr": belegnr, "betrag": betrag, "vorsteuer": 19, "belegdatum": H, "faellig": tag(30), "skonto": skonto,
                                   "skonto_bis": tag(8) if skonto else "", "iban": "DE75512108001245126199", "empfaenger": "Holzhandel KG"})
z1, z2 = za("LS-7001", 1000.00, 2), za("LS-7002", 1000.00, 2)
ein([ntry(980.00, "Holzhandel KG", "LS-7001 abzgl. Skonto", iban="DE75512108001245126199", ref="L1", cd="DBIT"), ntry(998.00, "Holzhandel KG", "LS-7002", iban="DE75512108001245126199", ref="L2", cd="DBIT")])
v1, v2 = (umsatz("L1") or umsatz("LS-7001 abzgl")).get("vorschlag") or {}, (umsatz("L2") or {}).get("vorschlag") or {}
ok("Abbuchung 980,00 € auf 1.000,00 € mit 2 % Skonto und Belegnummer: sicher", v1.get("sicher") is True and v1["ziele"][0]["id"] == z1["id"], v1)
ok("Abbuchung 998,00 € (1.000 € minus 2 €) gilt nicht mehr als passend", not v2.get("sicher"), v2)
u = umsatz("L1") or umsatz("LS-7001 abzgl"); z = A("POST", f"bank/{u['id']}/zuordnen", {"ziele": v1["ziele"]})
ok("Zahlungsauftrag durch die Zuordnung als bezahlt markiert", z["_s"] == 200 and con.execute("select bezahlt from zahlungen where id=?", (z1["id"],)).fetchone()[0] == H, z)
con.execute("delete from bank_umsaetze where status='offen'"); con.commit()

print("== I8: Sammelüberweisung aus der eigenen SEPA-Datei")
z3, z4 = za("LS-8001", 300.00), za("LS-8002", 200.00, 2)
sp = A("POST", "zahlungen/sepa", {"ids": [z3["id"], z4["id"]], "ausfuehrung": H}); xml = str(sp.get("xml") or "")
msg = (re.search(r"<MsgId>([^<]+)</MsgId>", xml) or [None, ""])[1]
ok("SEPA-Datei über 496,00 € erzeugt (300,00 € und 200,00 € abzüglich 2 %), Sammelbuchung", abs(sp.get("summe", 0) - 496.00) < 0.005 and "<BtchBookg>true</BtchBookg>" in xml and msg, (sp.get("summe"), sp.get("fehler")))
gem = con.execute("select * from sepa_dateien order by id desc limit 1").fetchone()
ok("Inhalt der Datei festgehalten (Kennung, Summe, zwei Posten)", gem and gem["msg"] == msg and abs(gem["summe"] - 496.0) < 0.005 and len(json.loads(gem["posten"])) == 2, dict(gem) if gem else None)
ohne = f"<TxDtls><Refs><EndToEndId>{z3['nummer']}</EndToEndId></Refs><RltdPties><Cdtr><Nm>Holzhandel KG</Nm></Cdtr></RltdPties><RmtInf><Ustrd>Rg. LS-8001</Ustrd></RmtInf></TxDtls><TxDtls><Refs><EndToEndId>{z4['nummer']}</EndToEndId></Refs><RltdPties><Cdtr><Nm>Holzhandel KG</Nm></Cdtr></RltdPties><RmtInf><Ustrd>Rg. LS-8002</Ustrd></RmtInf></TxDtls>"
ein([ntry(496.00, "", "", ref="B1", cd="DBIT", txs=ohne)])
u = next(x for x in offen() if x["referenz"] == "B1"); v = u.get("vorschlag") or {}
ok("Sammelbuchung ohne Einzelbeträge heißt „Sammelbuchung (2 Posten)“, nicht wie der erste Posten", u["name"] == "Sammelbuchung (2 Posten)" and "LS-8001" not in (u["zweck"] or ""), (u["name"], u["zweck"]))
ok("Summe der eigenen SEPA-Datei erkannt: Vorschlag über beide Zahlungsaufträge, ohne Kennung nur zum Prüfen", v.get("sicher") is False and sorted(t["id"] for t in v.get("ziele", [])) == sorted([z3["id"], z4["id"]]) and "Sammelüberweisung" in v.get("grund", ""), v)
con.execute("delete from bank_umsaetze where status='offen'"); con.commit()
mit = f"<Btch><PmtInfId>{msg}-1</PmtInfId><NbOfTxs>2</NbOfTxs></Btch>"
ein([ntry(496.00, "", "", ref="B2", cd="DBIT", txs=mit)])
u = next(x for x in offen() if x["referenz"] == "B2"); v = u.get("vorschlag") or {}
ok("mit der Kennung der Datei im Umsatz: sicher", v.get("sicher") is True and len(v.get("ziele", [])) == 2, v)
z = A("POST", f"bank/{u['id']}/zuordnen", {"ziele": v["ziele"]})
bez = [r[0] for r in con.execute("select bezahlt from zahlungen where id in (?,?)", (z3["id"], z4["id"]))]
ok("übernommen: beide Zahlungsaufträge bezahlt, Beträge 300,00 € und 196,00 € festgehalten", z["_s"] == 200 and bez == [H, H] and sorted(t["betrag"] for t in z.get("liste") or z.get("ziele") or json.loads(con.execute("select ziel from bank_umsaetze where id=?", (u["id"],)).fetchone()[0])) == [196.0, 300.0], (z, bez))
los = A("POST", f"bank/{u['id']}/loesen", {})
ok("Lösen nimmt „bezahlt“ bei beiden zurück", los["_s"] == 200 and [r[0] for r in con.execute("select bezahlt from zahlungen where id in (?,?)", (z3["id"], z4["id"]))] == ["", ""], los)
z = A("POST", f"bank/{u['id']}/zuordnen", {"ziele": [{"art": "zahlung", "id": z3["id"], "betrag": 300.0}, {"art": "zahlung", "id": z4["id"], "betrag": 100.0}]})
ok("mehrere Zahlungsaufträge, deren Summe nicht passt: abgewiesen", z["_s"] == 400, z)
A("PUT", "einstellungen", {"sepa_einzelbuchung": True})
sp2 = A("POST", "zahlungen/sepa", {"ids": [z3["id"], z4["id"]], "ausfuehrung": H})
ok("Einstellung „einzeln abbuchen“: Datei verlangt Einzelbuchung", "<BtchBookg>false</BtchBookg>" in str(sp2.get("xml")), str(sp2.get("fehler")))
con.execute("delete from bank_umsaetze where status='offen'"); con.commit()

print("== I12: Rückbuchung")
r7, o7 = rechnung(k_maier, 50.00)
ein([ntry(o7["betrag"], "Peter Maier", f"Rechnung {r7['nummer']}", iban="DE12500105170648489890", ref="R1", e2e="E2E-R1")])
u = umsatz("R1") or umsatz(r7["nummer"]); A("POST", f"bank/{u['id']}/zuordnen", {"ziele": u["vorschlag"]["ziele"]})
ein([ntry(o7["betrag"], "Peter Maier", "Ruecklastschrift", iban="DE12500105170648489890", ref="R2", e2e="E2E-R1", cd="DBIT", extra="<RvslInd>true</RvslInd>")])
u = next(x for x in offen() if x["referenz"] == "R2")
ok("Rückbuchung: kein Vorschlag, aber Hinweis auf die betroffene Rechnung", not u.get("vorschlag") and "Rückbuchung" in (u.get("hinweis") or "") and r7["nummer"] in (u.get("hinweis") or ""), (u.get("vorschlag"), u.get("hinweis")))

print("== P5: Suchmuster je Nummer nur einmal, Ergebnis wie bisher")
sys.path.insert(0, "/home/claude/eberle-buero"); import bank
def alt_kommt_vor(nummer, text):
    n = bank._norm(nummer).strip()
    if len(n) < 4: return False
    return any(re.search(r"(?<![0-9A-Z])" + re.escape(v) + r"(?![0-9])", text) for v in {n, n.replace("-", ""), n.replace("-", " "), n.replace("-", "/")})
random.seed(152); abw = 0; n = 0
nummern = ["2026-0232", "2026-0001", "RE-2025-0917", "LS-7001", "0042", "A12B34", "2026-02", "ZA-2026-0003", "12", "9999-1"]
for _ in range(4000):
    nr = random.choice(nummern); var = random.choice([nr, nr.replace("-", ""), nr.replace("-", " "), nr.replace("-", "/"), nr[:-1], nr + "7", "X" + nr, nr.lower(), "1" + nr])
    text = bank._norm(random.choice(["Rechnung ", "RG.", "", "Zahlung fuer ", "KdNr 4711 "]) + var + random.choice(["", " Danke", "/2", " 2026", "A"]))
    a, b = alt_kommt_vor(nr, text), bank._kommt_vor(nr, text, bank._ziffern(text)); n += 1; abw += a != b
ok("4.000 Zufallsproben: neue Suche findet dasselbe wie die bisherige", abw == 0, f"{abw} Abweichungen von {n}")
ok("Zwischenspeicher der Suchmuster wird benutzt", bank._muster.cache_info().hits > 3000, bank._muster.cache_info())
print("FEHLER:", fehler)
