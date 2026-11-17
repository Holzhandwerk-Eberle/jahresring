"""Kontoauszugsimport: Formate, Doppelte, Lücken, fremdes Konto, Währung, Zuordnungsvorschläge."""
import json, re, sys, base64, time, os, io, zipfile
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None):
    z = time.time(); s, b, hd = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    j["_ms"] = int((time.time() - z) * 1000); return j
EIGEN = "DE02120300000000202051"
A("PUT", "einstellungen", {"sepa_iban": EIGEN, "firma": "Muster Schreinerei", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890"})
def ntry(betrag, name="Kunde", zweck="", iban="DE89370400440532013000", ref=None, tag="2026-11-10", cd="CRDT", ccy="EUR", sts="BOOK", v8=False, extra=""):
    partei = (f"<Dbtr><Pty><Nm>{name}</Nm></Pty></Dbtr>" if v8 else f"<Dbtr><Nm>{name}</Nm></Dbtr>") if cd == "CRDT" else (f"<Cdtr><Pty><Nm>{name}</Nm></Pty></Cdtr>" if v8 else f"<Cdtr><Nm>{name}</Nm></Cdtr>")
    konto = f"<DbtrAcct><Id><IBAN>{iban}</IBAN></Id></DbtrAcct>" if cd == "CRDT" else f"<CdtrAcct><Id><IBAN>{iban}</IBAN></Id></CdtrAcct>"
    status = f"<Sts><Cd>{sts}</Cd></Sts>" if v8 else f"<Sts>{sts}</Sts>"
    return (f'<Ntry><Amt Ccy="{ccy}">{betrag:.2f}</Amt><CdtDbtInd>{cd}</CdtDbtInd>{extra}{status}<BookgDt><Dt>{tag}</Dt></BookgDt><ValDt><Dt>{tag}</Dt></ValDt>' + (f"<AcctSvcrRef>{ref}</AcctSvcrRef>" if ref else "") +
            f"<NtryDtls><TxDtls><RltdPties>{partei}{konto}</RltdPties><RmtInf><Ustrd>{zweck}</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>")
def camt(eintraege, nr="1", anf=0.0, ende=None, iban=EIGEN, ver="02", art="053", von="2026-11-10"):
    ende = anf + sum(float(re.search(r">(-?[\d.]+)</Amt>", e).group(1)) * (-1 if "<CdtDbtInd>DBIT" in e else 1) for e in eintraege) if ende is None else ende
    wurzel, st = {"053": ("BkToCstmrStmt", "Stmt"), "052": ("BkToCstmrAcctRpt", "Rpt"), "054": ("BkToCstmrDbtCdtNtfctn", "Ntfctn")}[art]
    bal = lambda cd, betrag, tag: f'<Bal><Tp><CdOrPrtry><Cd>{cd}</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">{abs(betrag):.2f}</Amt><CdtDbtInd>{"CRDT" if betrag >= 0 else "DBIT"}</CdtDbtInd><Dt><Dt>{tag}</Dt></Dt></Bal>'
    return (f'<?xml version="1.0" encoding="UTF-8"?><Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.{art}.001.{ver}"><{wurzel}><GrpHdr><MsgId>M{nr}</MsgId><CreDtTm>{von}T20:00:00</CreDtTm></GrpHdr><{st}><Id>S{nr}</Id><ElctrncSeqNb>{nr}</ElctrncSeqNb><LglSeqNb>{nr}</LglSeqNb><CreDtTm>{von}T20:00:00</CreDtTm>'
            f'<Acct><Id><IBAN>{iban}</IBAN></Id></Acct>{bal("PRCD", anf, von)}{bal("CLBD", ende, von)}{"".join(eintraege)}</{st}></{wurzel}></Document>').encode()
def ein(roh, name="auszug.xml"):
    x = A("POST", "bank/einlesen", {"daten": base64.b64encode(roh).decode(), "dateiname": name}); return x
def umsaetze(): 
    x = A("GET", "bank"); return x
# offene Posten anlegen
k = A("POST", "kunden", {"kurzname": "Zahler, Zacharias", "nachname": "Zahler", "vorname": "Zacharias", "plz": "88069", "ort": "Tettnang"})
def rechnung(betrag):
    a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Import"}); po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Leistung"}); pid = po.get("id") or po["position"]["id"]
    A("PUT", f"positionen/{pid}", {"einzelpreis": betrag, "preis_manuell": 1, "menge": 1}); b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); f = A("POST", f"belege/{b['id']}/festschreiben", {}); return (f.get("beleg") or f)
r1, r2, r3, r4, r5 = [rechnung(x) for x in (1000, 2000, 500, 750, 300)]
print("Rechnungen:", [(r["nummer"], r["brutto"]) for r in (r1, r2, r3, r4, r5)])
n1, n2, n3, n4, n5 = [r["nummer"] for r in (r1, r2, r3, r4, r5)]
print("\n== 1. Formate")
for ver, art, v8 in (("02", "053", False), ("08", "053", True), ("08", "052", True), ("08", "054", True), ("13", "053", True)):
    x = ein(camt([ntry(11.11 + int(ver), "Format " + ver + art, f"Test {ver} {art}", ref=f"F{ver}{art}", v8=v8)], nr=ver + art, ver=ver, art=art)); print("  camt.%s.001.%s: HTTP %s neu=%s doppelt=%s %s" % (art, ver, x["_s"], x.get("neu"), x.get("doppelt"), x.get("fehler", "")))
mt940 = b":20:STARTUMS\r\n:25:12030000/202051\r\n:28C:1/1\r\n:60F:C261110EUR0,00\r\n:61:2611101110CR100,00NTRFNONREF\r\n:86:166?00Gutschrift?20Rechnung 1\r\n:62F:C261110EUR100,00\r\n-\r\n"
x = ein(mt940, "umsatz.sta"); print("  MT940 (.sta): HTTP %s %s" % (x["_s"], x.get("fehler", "")))
csv = "Buchungstag;Valuta;Name;Verwendungszweck;Betrag\n10.11.2026;10.11.2026;Zahler;Rechnung;100,00\n".encode("cp1252")
x = ein(csv, "umsaetze.csv"); print("  CSV aus dem Onlinebanking: HTTP %s %s" % (x["_s"], x.get("fehler", "")))
x = ein(b"%PDF-1.4 kein Auszug", "auszug.pdf"); print("  PDF: HTTP %s %s" % (x["_s"], x.get("fehler", "")))
x = ein(b"", "leer.xml"); print("  leere Datei: HTTP %s %s" % (x["_s"], x.get("fehler", "")))
print("\n== 2. Doppelte")
d1 = camt([ntry(50, "Anna A", "Miete", ref="R-1"), ntry(50, "Anna A", "Miete", ref="R-2")], nr="D1"); x = ein(d1); y = ein(d1); print("  dieselbe Datei zweimal: erst neu=%s, dann neu=%s doppelt=%s" % (x.get("neu"), y.get("neu"), y.get("doppelt")))
x = ein(camt([ntry(77, "Bernd B", "Abschlag Küche"), ntry(77, "Bernd B", "Abschlag Küche")], nr="D2")); print("  zwei gleiche Umsätze ohne Bankreferenz in einer Datei: neu=%s doppelt=%s (erwartet 2/0)" % (x.get("neu"), x.get("doppelt")))
x = ein(camt([ntry(88, "Clara C", "Rate Mai", ref="NONREF", tag="2026-11-03")], nr="D3")); y = ein(camt([ntry(88, "Dieter D", "Rate Juni", ref="NONREF", tag="2026-11-12")], nr="D4"))
print("  zwei VERSCHIEDENE Umsätze (anderer Tag, anderer Zahler), gleiche Referenz NONREF und gleicher Betrag: erst neu=%s, dann neu=%s doppelt=%s (erwartet neu=1)" % (x.get("neu"), y.get("neu"), y.get("doppelt")))
x = ein(camt([ntry(99, "Eva E", "Rate 1", tag="2026-11-04")], nr="D5")); y = ein(camt([ntry(99, "Eva E", "Rate 1", tag="2026-11-04")], nr="D6", anf=99)); print("  gleicher Umsatz ohne Referenz in zwei Dateien (Tages- und Monatsauszug): neu=%s, dann neu=%s doppelt=%s (erwartet doppelt=1)" % (x.get("neu"), y.get("neu"), y.get("doppelt")))
print("\n== 3. Vollständigkeit: Lücke, falsche Summe, fremdes Konto, Währung, vorgemerkt")
x = ein(camt([ntry(10, "L1", "Lücke 1", ref="L1")], nr="101", anf=1000, ende=1010)); y = ein(camt([ntry(10, "L3", "Lücke 3", ref="L3")], nr="103", anf=5000, ende=5010))
print("  Auszug 101 endet mit 1.010, Auszug 103 beginnt mit 5.000 (102 fehlt): HTTP %s, Hinweis: %s" % (y["_s"], json.dumps({k_: v for k_, v in y.items() if k_ in ("hinweis", "hinweise", "warnung", "warnungen", "luecke", "saldo")}, ensure_ascii=False)))
y = ein(camt([ntry(10, "S", "Summe", ref="S1")], nr="201", anf=100, ende=999)); print("  Anfang 100 + Umsatz 10 ≠ Endsaldo 999: HTTP %s, Hinweis: %s" % (y["_s"], json.dumps({k_: v for k_, v in y.items() if k_ in ("hinweis", "hinweise", "warnung", "warnungen", "saldo")}, ensure_ascii=False)))
y = ein(camt([ntry(10, "F", "fremd", ref="X1")], nr="301", iban="DE75512108001245126199")); print("  Auszug eines fremden Kontos: HTTP %s neu=%s, Hinweis: %s" % (y["_s"], y.get("neu"), json.dumps({k_: v for k_, v in y.items() if k_ in ("hinweis", "hinweise", "warnung", "warnungen", "fehler")}, ensure_ascii=False)))
y = ein(camt([ntry(250, "US Corp", "Invoice", ref="U1", ccy="USD")], nr="401")); print("  Umsatz in USD: HTTP %s neu=%s" % (y["_s"], y.get("neu")))
y = ein(camt([ntry(33, "Vorgemerkt", "kommt noch", ref="P1", sts="PDNG")], nr="402")); print("  vorgemerkter Umsatz (PDNG): neu=%s (erwartet 0)" % y.get("neu"))
y = ein(camt([ntry(40, "Storno", "Rückgabe Lastschrift", ref="RV1", cd="DBIT", extra="<RvslInd>true</RvslInd>")], nr="403")); print("  Rückbuchung (RvslInd, DBIT 40): neu=%s" % y.get("neu"))
print("\n== 4. Zuordnungsvorschläge")
faelle = [(r1["brutto"], f"Rechnung {n1}", "glatte Zahlung mit Nummer"), (r2["brutto"], "RE " + n2.replace("-", " "), "Nummer mit Leerzeichen"), (r3["brutto"], "Rg." + n3.replace("-", ""), "Nummer ohne Bindestrich"),
          (round(r4["brutto"] * 0.98, 2), f"{n4} abzgl. 2% Skonto", "2 % Skonto abgezogen"), (r5["brutto"], "Danke für die schöne Arbeit", "nur Betrag und Name passen")]
x = ein(camt([ntry(b_, "Zacharias Zahler", zw, ref=f"V{i}") for i, (b_, zw, _) in enumerate(faelle)] + [ntry(r1["brutto"] + r2["brutto"], "Zacharias Zahler", f"{n1} und {n2}", ref="V9"), ntry(123.45, "Unbekannt", "ohne Bezug", ref="V10"), ntry(r1["brutto"], "Zacharias Zahler", f"Rechnung {n1}1", ref="V11")], nr="501"))
bk = umsaetze(); ul = bk.get("umsaetze") or bk.get("liste") or []
print("  Schlüssel der Antwort:", [k_ for k_ in bk if not k_.startswith("_")][:12], "| Felder Umsatz:", sorted(ul[0].keys())[:24] if ul else "")
for u in ul:
    if (u.get("referenz") or "").startswith("V") or u.get("name") in ("US Corp", "Storno"):
        v = u.get("vorschlag") or {}
        print("  %-9s %9.2f %-34s → %s %s %s" % (u.get("referenz"), u.get("betrag"), (u.get("zweck") or "")[:34], "SICHER" if v.get("sicher") else ("unsicher" if v else "kein Vorschlag"), v.get("grund", ""), [(z.get("text", "")[:24], z.get("betrag")) for z in v.get("ziele", [])]))
print("\n== 5. Große Datei")
viele = camt([ntry(10 + i % 90, f"Zahler {i}", f"Zahlung {i}", ref=f"G{i}", tag=f"2026-10-{1 + i % 28:02d}") for i in range(5000)], nr="900")
x = ein(viele, "gross.xml"); print("  5.000 Umsätze einlesen: %.1f s, neu=%s" % (x["_ms"] / 1000, x.get("neu"))); y = umsaetze(); print("  Liste mit Vorschlägen danach: %.1f s, %.1f MB" % (y["_ms"] / 1000, len(y["_roh"]) / 1048576))
