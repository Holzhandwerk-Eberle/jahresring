"""Version 149, Paket Rechnen: kaufmännische Rundung (Umsatzsteuer, Menge × Einzelpreis, Rabatt, Abschlag), Zahlen als Text
in der Kalkulation, E-Rechnung und Belegprüfung bleiben stimmig. Erwartet eine frische Prüfinstanz (bash /tmp/claude-0/t/v25/neu.sh)."""
import json, sys, re, sqlite3, random, math
from decimal import Decimal, ROUND_HALF_UP
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
sys.path.insert(0, "/home/claude/eberle-buero")
import kern, kalkulation
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:400]))
    if not bed: fehler.append(name)
genau = lambda x, n=2: float((x if isinstance(x, Decimal) else Decimal(str(x))).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP))

print("== Rundung (kern.kfm)")
faelle = {2.675: 2.68, 1.005: 1.01, 0.285: 0.29, 0.125: 0.13, 0.375: 0.38, 2.5 * 0.19: 0.48, 102.5 * 19 / 100: 19.48, 0.5 * 4764.83: 2382.42, 1.5 * 231.69: 347.54, 29997.50 * 0.19: 5699.53,
          -2.675: -2.68, -0.004: 0.0, 0.004999: 0.0, 1e9 + 0.005: 1000000000.01, 0.0: 0.0}
falsch = {x: kern.kfm(x) for x, soll in faelle.items() if kern.kfm(x) != soll or str(kern.kfm(x)) == "-0.0"}
ok("Grenzfälle: 2,675 → 2,68 · 1,005 → 1,01 · 2,50 × 19 % → 0,48 · 0,5 × 4.764,83 → 2.382,42 · kein „−0,00“", not falsch, falsch)
ok("unendlich und „keine Zahl“ werden zu 0", kern.kfm(float("inf")) == 0 and kern.kfm(float("nan")) == 0 and kern.kfm(-float("inf")) == 0)
ok("andere Stellenzahlen: kfm(2,5; 0) = 3 · kfm(0,00005; 4) = 0,0001 · kfm(1,23456; 3) = 1,235", kern.kfm(2.5, 0) == 3 and kern.kfm(0.00005, 4) == 0.0001 and kern.kfm(1.23456, 3) == 1.235, (kern.kfm(2.5, 0), kern.kfm(0.00005, 4)))
ab = []
for satz in (19, 7):
    for cent in range(1, 1_000_001):
        soll = genau(Decimal(cent) * satz / Decimal(10000))
        if kern.kfm(cent / 100 * satz / 100) != soll: ab.append((cent / 100, satz, kern.kfm(cent / 100 * satz / 100), soll))
ok("Umsatzsteuer 19 % und 7 % auf jeden Nettobetrag von 0,01 € bis 10.000,00 €: 2.000.000 Rechnungen ohne Abweichung von der Handrechnung", not ab, ab[:5])
random.seed(5); ab = []
for _ in range(300000):
    menge = random.choice([0.5, 1.5, 2.5, 0.25, 0.75, 1.25, 3.35, 2.45, 7.15, 12.345, 0.125, 1.005, 33.3]); ep = random.randint(1, 500000) / 100
    soll = genau(Decimal(str(menge)) * Decimal(str(ep)))
    if kern.kfm(ep * menge) != soll: ab.append((menge, ep, kern.kfm(ep * menge), soll))
ok("Menge × Einzelpreis mit gebrochenen Mengen: 300.000 Zufallsfälle ohne Abweichung", not ab, ab[:5])
ab = []
for cent in range(1, 500_001, 7):
    for pz in (2, 3, 5, 7.5, 10, 12.5, 15):
        soll = genau(Decimal(cent) * Decimal(str(pz)) / Decimal(10000))
        if kern.kfm(cent / 100 * pz / 100) != soll: ab.append((cent / 100, pz))
ok("Rabatt 2 bis 15 % auf Beträge bis 5.000 €: ohne Abweichung", not ab, ab[:5])
ok("Anzeige: de(2.675) = 2,68 · de(1234.5) = 1.234,50 · de(-0.004) = 0,00", kern.de(2.675) == "2,68" and kern.de(1234.5) == "1.234,50" and kern.de(-0.004) == "0,00", (kern.de(2.675), kern.de(1234.5), kern.de(-0.004)))

print("== Zahlen als Text in der Kalkulation")
f = kalkulation.f
werte = {"12,5": 12.5, "40 €": 40.0, "1.234,56": 1234.56, "12.5": 12.5, " 7 ": 7.0, "": 0.0, None: 0.0, 3: 3.0, 2.5: 2.5, "abc": 0.0, "inf": 0.0, "nan": 0.0}
falsch = {str(k): f(k) for k, v in werte.items() if f(k) != v}
ok("„12,5“, „40 €“, „1.234,56“ werden gelesen (bisher 0); „abc“, „inf“, „nan“ zählen als 0", not falsch and f(float("inf")) == 0 and f(float("nan")) == 0 and f(10 ** 400) == 0, falsch)
kalk = kalkulation.vorgaben_kopie({})
pos = {"menge": 1, "stueckliste": [], "extras": {"kostenliste": [{"art": "zukauf", "text": "Griff", "menge": "2", "einheit": "Stk.", "preis": "12,5"}]}}
try:
    c1 = kalkulation.position_rechnen(pos, kalk); pos["extras"]["kostenliste"][0]["preis"] = "zwölf"; c2 = kalkulation.position_rechnen(pos, kalk)
    ok("Zukauf 2 × „12,5“ rechnet mit 25,00 € (bisher 0 €)", abs(c1["zukauf"] - 25) < 1e-9 and not c1["warnungen"], (c1["zukauf"], c1["warnungen"]))
    ok("Preis „zwölf“: gerechnet wird mit 0 und die Position zeigt eine Warnung", c2["zukauf"] == 0 and any("zwölf" in w and "keine Zahl" in w for w in c2["warnungen"]), (c2["zukauf"], c2["warnungen"]))
except Exception as e:
    ok("Kalkulation mit Textwerten rechnet", False, repr(e))

print("== Belege")
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None):
    s, b, hd = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
A("PUT", "einstellungen", {"firma": "Muster", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890", "sepa_iban": "DE02120300000000202051", "firma_inhaber": "Jonas Muster"})
def beleg(positionen, art="rechnung", kunde=None, fest=False, opts=None):
    k = A("POST", "kunden", {"kurzname": "Rund, Rita", "nachname": "Rund", "strasse": "Weg 2", "plz": "88069", "ort": "Tettnang", **(kunde or {})})
    a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Rundung"})
    for text, ep, menge in positionen:
        po = A("POST", f"auftraege/{a['id']}/positionen", {"text": text}); pid = po.get("id") or po["position"]["id"]; A("PUT", f"positionen/{pid}", {"einzelpreis": ep, "preis_manuell": 1, "menge": menge})
    b = A("POST", f"auftraege/{a['id']}/belege", {"art": art, **(opts or {})})
    if fest: b["_fest"] = A("POST", f"belege/{b['id']}/festschreiben", {})
    return A("GET", f"belege/{b['id']}"), a
b, _ = beleg([("Leiste", 2.50, 1)], fest=True); s = b["daten"]["summen"]
ok("Rechnung über 2,50 € netto: Umsatzsteuer 0,48 €, brutto 2,98 € (bisher 0,47 € und 2,97 €)", (s["netto"], s["ust"], s["brutto"]) == (2.5, 0.48, 2.98) and b["ust"] == 0.48 and b["brutto"] == 2.98, s)
b2, _ = beleg([("Platte", 4764.83, 0.5), ("Kante", 231.69, 1.5)], fest=True); z = [x for x in b2["daten"]["zeilen"] if x["typ"] == "pos"]; s2 = b2["daten"]["summen"]
ok("0,5 × 4.764,83 € = 2.382,42 € und 1,5 × 231,69 € = 347,54 € (bisher je 1 Cent weniger)", [x["gp"] for x in z] == [2382.42, 347.54], [x["gp"] for x in z])
ok("Summen dazu: netto 2.729,96 €, USt 518,69 €, brutto 3.248,65 €", (s2["netto"], s2["ust"], s2["brutto"]) == (2729.96, genau(Decimal("2729.96") * 19 / 100), genau(Decimal("2729.96") * 119 / 100)), s2)
b3, _ = beleg([("Tür", 102.50, 1)], kunde={"rabatt": 7.5}, art="angebot"); s3 = b3["daten"]["summen"]
soll_rab = genau(Decimal("102.50") * Decimal("7.5") / 100); soll_netto = genau(Decimal("102.50") - Decimal(str(soll_rab))); soll_ust = genau(Decimal(str(soll_netto)) * 19 / 100)
ok(f"Angebot mit 7,5 % Rabatt auf 102,50 €: Rabatt {soll_rab}, netto {soll_netto}, USt {soll_ust}", (s3["rabatt"], s3["netto"], s3["ust"]) == (soll_rab, soll_netto, soll_ust), s3)
b4, a4 = beleg([("Schrank", 2997.50, 1)], art="angebot")
ab = A("POST", f"auftraege/{a4['id']}/belege", {"art": "abschlag", "prozent": 33.33}); abd = A("GET", f"belege/{ab['id']}"); sa = abd["daten"]["summen"]
soll_n = genau(Decimal("2997.50") * Decimal("33.33") / 100)
ok(f"Abschlag 33,33 % von 2.997,50 €: netto {soll_n}, USt {genau(Decimal(str(soll_n)) * 19 / 100)}", sa["netto"] == soll_n and sa["ust"] == genau(Decimal(str(soll_n)) * 19 / 100), sa)

print("== E-Rechnung und Belegprüfung")
s_, xml, _ = rq(inh, "GET", f"/api/belege/{b['id']}/zugferd.xml")
zahlen = dict(re.findall(r"<ram:(TaxBasisTotalAmount|TaxTotalAmount|GrandTotalAmount|DuePayableAmount)[^>]*>([-\d.]+)<", xml))
ok("E-Rechnung zur 2,50-€-Rechnung nennt dieselben Beträge (2.50 / 0.48 / 2.98)", s_ == 200 and zahlen.get("TaxBasisTotalAmount") == "2.50" and zahlen.get("TaxTotalAmount") == "0.48" and zahlen.get("GrandTotalAmount") == "2.98", (s_, zahlen))
s_, xml2, _ = rq(inh, "GET", f"/api/belege/{b2['id']}/zugferd.xml")
zeilen = re.findall(r"<ram:LineTotalAmount>([-\d.]+)<", xml2)
ok("E-Rechnung zur zweiten Rechnung: Zeilenbeträge 2382.42 und 347.54, Summe 2729.96", s_ == 200 and zeilen == ["2382.42", "347.54", "2729.96"], (s_, zeilen))
# eine Rechnung aus der Zeit vor der Umstellung (Steuer 1 Cent niedriger gespeichert): Die E-Rechnung nennt die gespeicherten Beträge
import erechnung, copy
altb = copy.deepcopy(b); altb["daten"]["summen"].update(ust=0.47, brutto=2.97, zahlbetrag=2.97); altb.update(ust=0.47, brutto=2.97, zahlbetrag=2.97)
try:
    xml3 = erechnung.cii_xml(altb, False, None).decode("utf-8"); zahlen3 = dict(re.findall(r"<ram:(TaxTotalAmount|GrandTotalAmount|CalculatedAmount)[^>]*>([-\d.]+)<", xml3))
    ok("früher gerechnete Rechnung (USt 0,47 € gespeichert): die E-Rechnung nennt die gespeicherten Beträge (0.47 / 2.97), nicht neu gerechnete",
       zahlen3.get("TaxTotalAmount") == "0.47" and zahlen3.get("GrandTotalAmount") == "2.97" and zahlen3.get("CalculatedAmount") == "0.47", zahlen3)
except Exception as e:
    ok("E-Rechnung zu einer früher gerechneten Rechnung lässt sich erzeugen", False, repr(e))
con = sqlite3.connect(D + "/buero.db", timeout=20)
pr = A("GET", "service/protokoll?voll=1"); bel = pr.get("belege") or {}
ok("Belegprüfung: alle festgeschriebenen Rechnungen in Ordnung, Protokoll in Ordnung", pr["_s"] == 200 and pr["pruefung"]["ok"] and not (bel.get("fehler") or []), (pr["_s"], pr.get("pruefung"), str(bel)[:300]))
s_, html, _ = rq(inh, "GET", f"/druck/{b['id']}")
ok("Druckansicht der 2,50-€-Rechnung zeigt 0,48 € Umsatzsteuer und 2,98 € Gesamtbetrag", s_ == 200 and "0,48 €" in html and "2,98 €" in html, s_)
con.close()
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
