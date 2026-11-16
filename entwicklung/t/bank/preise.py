import json, base64
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
l = P("lieferanten", {"kurzname": "Häfele"})
m1 = P("material", {"kategorie": "beschlaege", "bezeichnung": "Topfscharnier", "ek_preis": 2.10, "einheit": "Stk.", "lieferant_id": l["id"], "bestellnr": "329.01.500", "aufschlag": 50})
m2 = P("material", {"kategorie": "beschlaege", "bezeichnung": "Auszug", "ek_preis": 20.0, "einheit": "Paar", "lieferant_id": l["id"], "bestellnr": "421.55.300"})
m3 = P("material", {"kategorie": "beschlaege", "bezeichnung": "Griff", "ek_preis": 5.0, "einheit": "Stk.", "lieferant_id": l["id"], "bestellnr": "", "ean": "4006381333931"})
m4 = P("material", {"kategorie": "beschlaege", "bezeichnung": "Schraube", "ek_preis": 1.0, "einheit": "Stk.", "lieferant_id": l["id"], "bestellnr": "999"})
dn = "\r\n".join([
    "V 040Häfele GmbH                  Preisliste 2027",
    "A;N;329.01.500;00;Topfscharnier 110°;Clip;2;0;STK;235;R1;HG;",
    "A;N;42155300;00;Vollauszug;500mm;1;0;PAA;4000;R2;HG;",   # Brutto 40,00 → mit 40 % Rabatt 24,00
    "A;N;777;00;Griff Edelstahl;;2;2;STK;61000;R1;HG;",          # 6.100 Cent je 100 = 0,61? → je 100 Stk 610,00 → 6,10 je Stk
    "B;N;777;GRIFF;12345678;;;;;4006381333931;",
    "A;N;999;00;Schraube;;2;0;KG;500;R1;HG;",
]).encode("cp850")
r = P("preisimport/lesen", {"dateiname": "DATANORM.001", "daten": base64.b64encode(dn).decode(), "lieferant_id": l["id"], "rabatt": "40"})
print(" ", r.get("format"), r.get("artikel"), r.get("hinweis"))
for t in r.get("treffer", []):
    print("  ", t["nummer"], t["bezeichnung"], t["ueber"], t["alt"], "→", t["neu"], t["diff"], t["einheit"], t["einheit_datei"], "vorschlag" if t["vorschlag"] else "-")
tr = {t["bezeichnung"]: t for t in r["treffer"]}
ok("Datanorm Cent", abs(tr["Topfscharnier"]["neu"] - 2.35) < 1e-6)
ok("Brutto mit Rabatt, Nummer ohne Punkte", abs(tr["Auszug"]["neu"] - 24.0) < 1e-6 and tr["Auszug"]["einheit_ok"])
ok("Preiseinheit 100 und EAN", abs(tr["Griff"]["neu"] - 6.10) < 1e-6 and tr["Griff"]["ueber"] == "EAN")
ok("Einheit weicht ab → kein Vorschlag", tr["Schraube"]["einheit_ok"] is False and not tr["Schraube"]["vorschlag"])
u = P("preisimport/uebernehmen", {"lieferant_id": l["id"], "dateiname": "DATANORM.001", "posten": [t for t in r["treffer"] if t["vorschlag"]]})
ok("3 übernommen", u.get("geaendert") == 3)
mm = P(f"material/{m1['id']}", m="GET")
ok("VK mit Aufschlag nachgeführt", abs(mm["ek_preis"] - 2.35) < 1e-6 and abs(mm["vk_preis"] - 3.53) < 0.011, ) 
print("  VK", mm["vk_preis"], mm["preis_vom"])
csvd = "Artikelnummer;Bezeichnung;Nettopreis;ME\n329.01.500;Topf;2,50;Stk\n421.55.300;Auszug;25,00;Paar\n".encode("utf-8")
r = P("preisimport/lesen", {"dateiname": "liste.csv", "daten": base64.b64encode(csvd).decode(), "lieferant_id": l["id"]})
print("  CSV", r.get("zuordnung"), [(t["bezeichnung"], t["neu"]) for t in r["treffer"]])
ok("CSV erkannt", len(r["treffer"]) == 2 and r["zuordnung"].get("preis") == 2)
r = P("preisimport/lesen", {"dateiname": "x.csv", "daten": base64.b64encode(b"a;b\n1;2\n").decode()})
ok("unbekannte Spalten: Kopfzeile zum Zuordnen statt Fehler", r.get("kopf") == ["a", "b"] and "nicht gefunden" in r.get("hinweis", "") and not r.get("treffer"))
# neue Artikel
dn2 = "\r\n".join(["V 040Test", "A;N;111.22.333;00;Möbelgriff Eiche;128 mm;2;0;STK;450;R1;Griffe;", "A;N;111.22.444;00;Möbelgriff Nuss;128 mm;2;0;STK;470;R1;Griffe;",
    "A;N;555;00;Schubkastenschiene;;1;0;PAA;2000;R2;Auszüge;", "A;N;329.01.500;00;Topfscharnier;;2;0;STK;235;R1;Scharniere;", "B;N;555;X;;;;;4006000000008;"]).encode("cp850")
r = P("preisimport/lesen", {"dateiname": "DATANORM.002", "daten": base64.b64encode(dn2).decode(), "lieferant_id": l["id"], "rabatt": "40"})
ok("3 neue erkannt (Topfscharnier schon da)", r.get("neu_gesamt") == 3 and r.get("schluessel"))
print("  Gruppen", r.get("gruppen"))
n = P("preisimport/neue", {"schluessel": r["schluessel"], "suche": "griff eiche"})
ok("Suche", n["neu_treffer"] == 1 and n["neu"][0]["artnr"] == "111.22.333")
n = P("preisimport/neue", {"schluessel": r["schluessel"], "gruppe": "Auszüge"})
ok("Warengruppe", n["neu_treffer"] == 1)
a = P("preisimport/anlegen", {"schluessel": r["schluessel"], "auswahl": ["111.22.333", "555"], "kategorie": "beschlaege", "lieferant_id": l["id"], "rabatt": "40", "dateiname": "DATANORM.002"})
ok("2 angelegt", a.get("angelegt") == 2)
mats = {m["bestellnr"]: m for m in P("material?kategorie=beschlaege", m="GET")}
m5 = mats.get("555", {})
print("  ", m5.get("nummer"), m5.get("bezeichnung"), m5.get("ek_preis"), m5.get("einheit"), m5.get("ean"), m5.get("lieferant_id"), m5.get("gruppe"))
ok("Brutto mit Rabatt, Paar, EAN, Lieferant", abs(m5.get("ek_preis", 0) - 12.0) < 1e-6 and m5.get("einheit") == "Paar" and m5.get("ean") == "4006000000008" and m5.get("lieferant_id") == l["id"])
a = P("preisimport/anlegen", {"schluessel": r["schluessel"], "auswahl": ["111.22.333"], "kategorie": "beschlaege", "lieferant_id": l["id"]})
ok("doppelt übersprungen", a.get("angelegt") == 0 and a.get("uebersprungen") == 1)
r = P("preisimport/lesen", {"schluessel": r["schluessel"], "lieferant_id": l["id"], "rabatt": "40"})
ok("danach Treffer statt neu", r.get("neu_gesamt") == 1 and any(t["bestellnr"] == "555" for t in r["treffer"]))
P("preisimport/neue", {"schluessel": "xxx"}, erwartet=410)
P("preisimport/anlegen", {"schluessel": r["schluessel"], "auswahl": ["111.22.444"], "kategorie": "quatsch"}, erwartet=400)
# ---- Version -141: Rabattgruppen, gelöschte Artikel, ZIP, Preisänderungssätze, Zahlenformate
import io, zipfile, sys
sys.path.insert(0, "/home/claude/eberle-buero"); import preise as PR
ok("Zahlen: deutsch, englisch, Schweiz", PR._zahl("1.234,50") == 1234.5 and PR._zahl("1,234.50") == 1234.5 and PR._zahl("1'234.50") == 1234.5 and PR._zahl("12,5") == 12.5 and PR._zahl("12.50") == 12.5)
ok("EAN-Prüfziffer", PR.gtin_ok("4006381333931") and not PR.gtin_ok("4006381333932") and not PR.gtin_ok("12345678"))
l2 = P("lieferanten", {"kurzname": "Großhandel"})
a1 = P("material", {"kategorie": "beschlaege", "bezeichnung": "Scharnier R1", "ek_preis": 6.0, "einheit": "Stk.", "lieferant_id": l2["id"], "bestellnr": "S1"})
a2 = P("material", {"kategorie": "beschlaege", "bezeichnung": "Führung R2", "ek_preis": 30.0, "einheit": "Stk.", "lieferant_id": l2["id"], "bestellnr": "S2"})
a3 = P("material", {"kategorie": "beschlaege", "bezeichnung": "Schraube je 100", "ek_preis": 0.05, "einheit": "Stk.", "lieferant_id": l2["id"], "bestellnr": "S3"})
dn3 = "\r\n".join(["V 040Großhandel", "A;N;S1;00;Scharnier;;1;0;STK;1000;R1;WG;", "A;N;S2;00;Führung;;1;0;STK;5000;R2;WG;", "A;L;S9;00;Auslauf;;1;0;STK;900;R1;WG;",
                    "A;N;N1;00;Neu Brutto;;1;0;STK;2000;R2;WG;", "B;N;N1;NEU;87654321;;;;;4012345000016;"]).encode("cp850")
rab = "\r\n".join(["R;A;R1;1;4000;Beschlaege;R2;1;2500;Fuehrungen;"]).encode("cp850")
basis = {"dateiname": "DATANORM.001", "daten": base64.b64encode(dn3).decode(), "lieferant_id": l2["id"]}
r = P("preisimport/lesen", basis); tr = {t["bestellnr"]: t for t in r["treffer"]}
ok("Listenpreise werden gemeldet, Rabattgruppen aufgeführt", r.get("brutto") == 3 and [g["gruppe"] for g in r["rabattgruppen"]] == ["R1", "R2"] and r["rabattgruppen"][0]["rabatt"] is None)
ok("ohne Rabatt: Listenpreis, als Listenpreis gekennzeichnet", abs(tr["S1"]["neu"] - 10) < 1e-6 and tr["S1"]["brutto"] and tr["S1"]["rabattgruppe"] == "R1")
ok("gelöschter Artikel übersprungen", "gelöschte" in r.get("hinweis", "") and r["artikel"] == 3 and not any(n.get("artnr") == "S9" for n in r["neu"]))
ok("EAN aus dem richtigen Feld, nicht die alternative Artikelnummer", [n.get("ean") for n in r["neu"] if n["artnr"] == "N1"] == ["4012345000016"])
P("preisimport/rabatte", {"lieferant_id": l2["id"], "rabatte": {"R1": 40, "R2": "25,5"}})
r = P("preisimport/lesen", {"schluessel": r["schluessel"], "dateiname": "DATANORM.001", "lieferant_id": l2["id"]}); tr = {t["bestellnr"]: t for t in r["treffer"]}
ok("Rabatt je Rabattgruppe, beim Lieferanten gespeichert", abs(tr["S1"]["neu"] - 6.0) < 1e-6 and abs(tr["S2"]["neu"] - 37.25) < 1e-6 and r["rabattgruppen"][0]["quelle"] == "gespeichert")
r2 = P("preisimport/lesen", {"schluessel": r["schluessel"], "dateiname": "DATANORM.001", "lieferant_id": l2["id"], "rabatte": {"R2": 50}}); t2 = {t["bestellnr"]: t for t in r2["treffer"]}
ok("Rabatt nur für diese Sitzung geht vor", abs(t2["S2"]["neu"] - 25.0) < 1e-6 and r2["rabattgruppen"][1]["quelle"] == "eingegeben")
x = P("preisimport/anlegen", {"schluessel": r["schluessel"], "auswahl": ["N1"], "kategorie": "beschlaege", "lieferant_id": l2["id"], "dateiname": "DATANORM.001"})
ok("neu angelegt mit Rabatt der Gruppe (20,00 − 25,5 % = 14,90)", x.get("angelegt") == 1 and abs(x["liste"][0]["ek_preis"] - 14.9) < 1e-6)
z = io.BytesIO(); zf = zipfile.ZipFile(z, "w"); zf.writestr("DATANORM.001", dn3); zf.writestr("DATANORM.RAB", rab); zf.writestr("DATANORM.WRG", b"S;A;WG;Beschlaege;"); zf.close()
l3 = P("lieferanten", {"kurzname": "Zip-Händler"})
r = P("preisimport/lesen", {"dateiname": "DATANORM.ZIP", "daten": base64.b64encode(z.getvalue()).decode(), "lieferant_id": l3["id"], "alle": True}); tr = {t["bestellnr"]: t for t in r["treffer"]}
ok("ZIP gelesen, Rabattsätze der Datei als Vorschlag", r.get("format") == "Datanorm" and "ZIP" in r.get("hinweis", "") and [(g["rabatt"], g["quelle"]) for g in r["rabattgruppen"]] == [(40.0, "aus der Datei"), (25.0, "aus der Datei")]
   and abs(tr["S1"]["neu"] - 6.0) < 1e-6)
z2 = io.BytesIO(); zipfile.ZipFile(z2, "w").writestr("liesmich.pdf", b"x"); s_, b_, _ = rq(inh, "POST", "/api/preisimport/lesen", {"dateiname": "x.zip", "daten": base64.b64encode(z2.getvalue()).decode()})
ok("ZIP ohne Datanorm: verständliche Meldung", s_ == 400 and "keine Datanorm-Dateien" in b_)
pd = "\r\n".join(["V 040Großhandel", "P;A;S1;2;650;;;;;;;S3;2;600;;;;;;;"]).encode("cp850")
r = P("preisimport/lesen", {"dateiname": "DATPREIS.001", "daten": base64.b64encode(pd).decode(), "lieferant_id": l2["id"]}); tr = {t["bestellnr"]: t for t in r["treffer"]}
ok("reine Preisänderungsdatei: Preise für vorhandenes Material, nichts Neues", abs(tr["S1"]["neu"] - 6.5) < 1e-6 and r["neu_gesamt"] == 0 and "Preisänderungssätzen" in r["hinweis"])
ok("Preiseinheit passend zum bisherigen Preis gewählt (6,00 je 100 → 0,06)", abs(tr["S3"]["neu"] - 0.06) < 1e-6 and "je 100" in tr["S3"]["pe_hinweis"])
kombi = dn3 + b"\r\n" + "P;A;S1;2;700;;;;;;;".encode()
r = P("preisimport/lesen", {"dateiname": "DATANORM.001", "daten": base64.b64encode(kombi).decode(), "lieferant_id": l2["id"]}); tr = {t["bestellnr"]: t for t in r["treffer"]}
ok("Preisänderungssatz überschreibt den Artikelsatz (netto 7,00)", abs(tr["S1"]["neu"] - 7.0) < 1e-6 and not tr["S1"]["brutto"])
en = "Item No,Description,Price,Unit\nS1,Hinge,\"1,234.50\",pcs\n".encode()
r = P("preisimport/lesen", {"dateiname": "prices.csv", "daten": base64.b64encode(en).decode(), "lieferant_id": l2["id"]})
ok("englische Liste: Spalten erkannt, 1,234.50 = 1234,50", r["treffer"] and abs(r["treffer"][0]["neu"] - 1234.5) < 1e-6)

print("FEHLER:", F)
