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
m3 = P("material", {"kategorie": "beschlaege", "bezeichnung": "Griff", "ek_preis": 5.0, "einheit": "Stk.", "lieferant_id": l["id"], "bestellnr": "", "ean": "4006123456789"})
m4 = P("material", {"kategorie": "beschlaege", "bezeichnung": "Schraube", "ek_preis": 1.0, "einheit": "Stk.", "lieferant_id": l["id"], "bestellnr": "999"})
dn = "\r\n".join([
    "V 040Häfele GmbH                  Preisliste 2027",
    "A;N;329.01.500;00;Topfscharnier 110°;Clip;2;0;STK;235;R1;HG;",
    "A;N;42155300;00;Vollauszug;500mm;1;0;PAA;4000;R2;HG;",   # Brutto 40,00 → mit 40 % Rabatt 24,00
    "A;N;777;00;Griff Edelstahl;;2;2;STK;61000;R1;HG;",          # 6.100 Cent je 100 = 0,61? → je 100 Stk 610,00 → 6,10 je Stk
    "B;N;777;GRIFF;;;;;4006123456789;",
    "A;N;999;00;Schraube;;2;0;KG;500;R1;HG;",
    "P;A;329.01.500;2;240;;;;;",
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
r = P("preisimport/lesen", {"dateiname": "x.csv", "daten": base64.b64encode(b"a;b\n1;2\n").decode()}, erwartet=400)
# neue Artikel
dn2 = "\r\n".join(["V 040Test", "A;N;111.22.333;00;Möbelgriff Eiche;128 mm;2;0;STK;450;R1;Griffe;", "A;N;111.22.444;00;Möbelgriff Nuss;128 mm;2;0;STK;470;R1;Griffe;",
    "A;N;555;00;Schubkastenschiene;;1;0;PAA;2000;R2;Auszüge;", "A;N;329.01.500;00;Topfscharnier;;2;0;STK;235;R1;Scharniere;", "B;N;555;X;;;;;4006000000001;"]).encode("cp850")
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
ok("Brutto mit Rabatt, Paar, EAN, Lieferant", abs(m5.get("ek_preis", 0) - 12.0) < 1e-6 and m5.get("einheit") == "Paar" and m5.get("ean") == "4006000000001" and m5.get("lieferant_id") == l["id"])
a = P("preisimport/anlegen", {"schluessel": r["schluessel"], "auswahl": ["111.22.333"], "kategorie": "beschlaege", "lieferant_id": l["id"]})
ok("doppelt übersprungen", a.get("angelegt") == 0 and a.get("uebersprungen") == 1)
r = P("preisimport/lesen", {"schluessel": r["schluessel"], "lieferant_id": l["id"], "rabatt": "40"})
ok("danach Treffer statt neu", r.get("neu_gesamt") == 1 and any(t["bestellnr"] == "555" for t in r["treffer"]))
P("preisimport/neue", {"schluessel": "xxx"}, erwartet=410)
P("preisimport/anlegen", {"schluessel": r["schluessel"], "auswahl": ["111.22.444"], "kategorie": "quatsch"}, erwartet=400)
print("FEHLER:", F)
