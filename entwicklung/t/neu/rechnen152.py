"""Version 152, Rechnen und Buchen: Einheiten und Umrechnung (K5), Material ohne Preis und Position zu 0,00 € (K6), Abschläge (F5),
Lohnanteil nach § 35a (K7), Menge mit drei Stellen (K8), negative Werte (K9), Datum im Hinweis der E-Rechnung (G6), Skonto im
DATEV-Stapel (F4/W2). Erwartet eine frische Prüfinstanz (bash /tmp/claude-0/t/v25/neu.sh)."""
import json, sys, re, sqlite3, zipfile, base64
from datetime import date, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
sys.path.insert(0, "/home/claude/eberle-buero")
import kern, kalkulation
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:700]))
    if not bed: fehler.append(name)
H = date.today().isoformat(); tag = lambda n: (date.today() + timedelta(days=n)).isoformat()

print("== K5: Einheit und Umrechnung in der Kalkulation")
def rechne(werkstoffe, teil, **pos):
    kalk = kalkulation.vorgaben_kopie({}); kalk["werkstoffe"] = werkstoffe
    return kalkulation.position_rechnen({"menge": 1, "stueckliste": [teil], **pos}, kalk)
teil_k = {"werkstoff": "P01", "stueck": 1, "laenge": 2000, "breite": 500, "kanten": {"oben": "K01"}}
P = {"k": "P01", "typ": "platte", "name": "Spanplatte", "preis": 10, "v": 0, "einheit": "m²"}
c = rechne([P, {"k": "K01", "typ": "kante", "name": "ABS", "preis": 1.5, "v": 0, "einheit": "lfm"}], teil_k)
ok("Kante je lfm: 2 m × 1,50 € = 3,00 €, keine Warnung", abs(c["werkstoffe"] - (10 + 3)) < 1e-9 and not c["warnungen"], (c["werkstoffe"], c["warnungen"]))
c = rechne([P, {"k": "K01", "typ": "kante", "name": "ABS Rolle", "preis": 100, "v": 0, "einheit": "Rolle"}], teil_k)
ok("Kante je Rolle ohne Umrechnung: Warnung nennt Einheit und Recheneinheit", any("Rolle" in w and "lfm" in w and "Umrechnung" in w for w in c["warnungen"]), c["warnungen"])
c = rechne([P, {"k": "K01", "typ": "kante", "name": "ABS Rolle", "preis": 100, "v": 0, "einheit": "Rolle", "um": 50}], teil_k)
ok("Kante je Rolle mit Umrechnung 1 Rolle = 50 lfm: 2 m kosten 4,00 € (bisher 200,00 €), keine Warnung", abs(c["werkstoffe"] - (10 + 4)) < 1e-9 and not c["warnungen"], (c["werkstoffe"], c["warnungen"]))
teil_o = {"werkstoff": "P01", "stueck": 1, "laenge": 1000, "breite": 1000, "oberflaeche": {"oben": "O01"}}
c0 = rechne([P, {"k": "O01", "typ": "oberflaeche", "name": "Lack", "preis": 100, "v": 0, "einheit": "m²"}], teil_o)
c1 = rechne([P, {"k": "O01", "typ": "oberflaeche", "name": "Lack", "preis": 100, "v": 0, "einheit": "Liter", "um": 8}], teil_o)
c2 = rechne([P, {"k": "O01", "typ": "oberflaeche", "name": "Lack", "preis": 100, "v": 0, "einheit": "Liter"}], teil_o)
ok("Lack je Liter mit Ergiebigkeit 8 m²: ein Achtel der Kosten je m²", c0["oberflaeche"] > 0 and abs(c1["oberflaeche"] - c0["oberflaeche"] / 8) < 1e-9 and not c1["warnungen"], (c0["oberflaeche"], c1["oberflaeche"], c1["warnungen"]))
ok("Lack je Liter ohne Umrechnung: Warnung", any("Liter" in w and "m²" in w for w in c2["warnungen"]), c2["warnungen"])
c = rechne([{"k": "P01", "typ": "platte", "name": "Tafel", "preis": 64.90, "v": 0, "einheit": "Tafel", "um": 5.796}], {"werkstoff": "P01", "stueck": 1, "laenge": 1000, "breite": 1000})
ok("Platte je Tafel (2800 × 2070 = 5,796 m²): 1 m² kostet 11,20 €", abs(c["werkstoffe"] - 64.90 / 5.796) < 1e-9 and not c["warnungen"], (c["werkstoffe"], c["warnungen"]))

print("== K6: Material ohne Preis")
c = rechne([{"k": "P01", "typ": "platte", "name": "CADP19", "preis": 0, "v": 0, "einheit": "m²"}], {"werkstoff": "P01", "stueck": 1, "laenge": 1000, "breite": 1000})
ok("Werkstoff mit Preis 0: Warnung „hat keinen Preis“", any("CADP19" in w and "keinen Preis" in w for w in c["warnungen"]), c["warnungen"])
kalk = kalkulation.vorgaben_kopie({}); kalk["beschlaege"] = [{"k": "B01", "name": "Topfband neu", "preis": 0, "einheit": "Stk."}]
c = kalkulation.position_rechnen({"menge": 1, "stueckliste": [], "beschlaege": [{"k": "B01", "menge": 4}]}, kalk)
ok("Beschlag mit Preis 0 und Menge: Warnung", any("Topfband neu" in w and "keinen Preis" in w for w in c["warnungen"]), c["warnungen"])

print("== K9: negative Werte")
c = rechne([P], {"werkstoff": "P01", "stueck": -3, "laenge": 1000, "breite": 1000, "verwendung": "Boden"})
ok("negative Stückzahl: Teil zählt nicht (bisher −30 €), Warnung mit Zeile", c["werkstoffe"] == 0 and any("Zeile 1" in w and "Stückzahl" in w for w in c["warnungen"]), (c["werkstoffe"], c["warnungen"]))
c = rechne([P], {"werkstoff": "P01", "stueck": 1, "laenge": -1000, "breite": 1000})
ok("negatives Maß: Teil zählt nicht, Warnung", c["werkstoffe"] == 0 and any("Länge" in w for w in c["warnungen"]), (c["werkstoffe"], c["warnungen"]))
kalk = kalkulation.vorgaben_kopie({})
c = kalkulation.position_rechnen({"menge": 1, "stueckliste": [], "zeitmodus": "stunden", "zeiten": [{"kst": "MONTAGE", "stunden": -4}, {"kst": "MONTAGE", "stunden": 1}]}, kalk)
c_ = kalkulation.position_rechnen({"menge": 1, "stueckliste": [], "zeitmodus": "stunden", "zeiten": [{"kst": "MONTAGE", "stunden": 1}]}, kalk)
ok("negative Stunden: mit 0 gerechnet (Preis wie ohne die Zeile), Warnung", abs(c["selbstkosten"] - c_["selbstkosten"]) < 1e-9 and c["selbstkosten"] > 0 and any("negative Zeit" in w for w in c["warnungen"]), (c["selbstkosten"], c_["selbstkosten"], c["warnungen"]))
c = rechne([{**P, "v": -250}], {"werkstoff": "P01", "stueck": 1, "laenge": 1000, "breite": 1000})
ok("Verschnitt −250 %: Kosten 0 statt negativ, Warnung", c["werkstoffe"] == 0 and any("Verschnitt" in w for w in c["warnungen"]), (c["werkstoffe"], c["warnungen"]))
kalk = kalkulation.vorgaben_kopie({}); kalk["werkstoffe"] = [P]; kalk["wg"] = -300
c = kalkulation.position_rechnen({"menge": 1, "stueckliste": [{"werkstoff": "P01", "stueck": 1, "laenge": 1000, "breite": 1000}]}, kalk)
ok("Wagnis und Gewinn −300 %: Preis nicht unter 0, Warnung", c["einzelpreis"] >= 0 and any("Wagnis" in w for w in c["warnungen"]), (c["einzelpreis"], c["warnungen"]))

print("== K8: Menge mit drei Nachkommastellen")
ok("de_menge: 1 · 2,50 · 0,393 · 0,996 · 12,346", [kern.de_menge(x) for x in (1, 2.5, 0.393, 0.996, 12.3456)] == ["1", "2,50", "0,393", "0,996", "12,346"], [kern.de_menge(x) for x in (1, 2.5, 0.393, 0.996, 12.3456)])

inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, h=None):
    s, b, hd = rq(inh, m, "/api/" + p, d, {"X-Rueckfrage": "1", **(h or {})}); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
def seite(p):
    return rq(inh, "GET", p)[1]
A("PUT", "einstellungen", {"firma": "Muster", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890", "sepa_iban": "DE02120300000000202051", "firma_inhaber": "Jonas Muster"})
con = sqlite3.connect(D + "/buero.db", timeout=30); con.row_factory = sqlite3.Row
def auftrag(positionen, kunde=None):
    k = A("POST", "kunden", {"kurzname": "Rund, Rita", "nachname": "Rund", "vorname": "Rita", "strasse": "Weg 2", "plz": "88069", "ort": "Tettnang", **(kunde or {})})
    a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Probe"})
    pids = []
    for text, ep, menge in positionen:
        po = A("POST", f"auftraege/{a['id']}/positionen", {"text": text}); pid = po.get("id") or po["position"]["id"]; pids.append(pid)
        A("PUT", f"positionen/{pid}", {"einzelpreis": ep, "preis_manuell": 1, "menge": menge})
    return a, k, pids
def fest(bid, bestaetigt=None):
    x = A("POST", f"belege/{bid}/festschreiben", {}, {"X-Bestaetigt": bestaetigt} if bestaetigt else None)
    if isinstance(x.get("beleg"), dict): x = {**x["beleg"], "_s": x["_s"]}
    return x
a, k, pids = auftrag([("Brett Eiche", 7239.18, 0.393)])
b = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"})
html = seite(f"/druck/{b['id']}")
ok("Angebot druckt „0,393“ (bisher „0,39“)", "0,393" in html and "0,39 " not in html.replace("0,393", ""), re.findall(r"0,39\d?", html)[:5])
po = A("GET", f"positionen/{pids[0]}"); ok("Menge 0,393 bleibt gespeichert", abs((po.get("position") or po)["menge"] - 0.393) < 1e-9)
A("PUT", f"positionen/{pids[0]}", {"menge": 1.23456}); po = A("GET", f"positionen/{pids[0]}")
ok("mehr als drei Stellen werden beim Speichern auf drei gerundet (1,235)", abs((po.get("position") or po)["menge"] - 1.235) < 1e-9, (po.get("position") or po)["menge"])

print("== K6: Rechnung mit Position zu 0,00 €")
a, k, pids = auftrag([("Schrank", 1000, 1), ("Lieferung", 0, 1)])
b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"})
x = fest(b["id"])
ok("Festschreiben mit einer Position zu 0,00 €: Rückfrage nennt die Position", x["_s"] == 409 and x.get("rueckfrage") == "position_null" and "Lieferung" in x.get("fehler", ""), x)
ok("Rechnung ist noch Entwurf", A("GET", f"belege/{b['id']}")["status"] == "entwurf")
x = fest(b["id"], "position_null")
ok("bestätigt: festgeschrieben", x["_s"] == 200 and x.get("status") == "fest", x)
a, k, pids = auftrag([("Schrank", 1000, 1)]); b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); x = fest(b["id"])
ok("Rechnung ohne Nullposition: keine Rückfrage", x["_s"] == 200 and x.get("status") == "fest", x)

print("== F5: Abschlagsrechnungen")
a, k, pids = auftrag([("Küche", 1000, 1)])   # 1.000,00 netto
x = A("POST", f"auftraege/{a['id']}/belege", {"art": "abschlag", "prozent": -20})
ok("Abschlag −20 %: abgelehnt", x["_s"] == 400 and "größer als 0" in x.get("fehler", ""), x)
x = A("POST", f"auftraege/{a['id']}/belege", {"art": "abschlag", "betrag": -500})
ok("Abschlag −500 €: abgelehnt", x["_s"] == 400, x)
b1 = A("POST", f"auftraege/{a['id']}/belege", {"art": "abschlag", "prozent": 80}); x = fest(b1["id"])
ok("erster Abschlag 80 %: ohne Rückfrage festgeschrieben", x["_s"] == 200 and x.get("status") == "fest", x)
b2 = A("POST", f"auftraege/{a['id']}/belege", {"art": "abschlag", "prozent": 80}); x = fest(b2["id"])
ok("zweiter Abschlag 80 %: Rückfrage mit Auftragssumme, bisherigen Abschlägen und Überschreitung",
   x["_s"] == 409 and x.get("rueckfrage") == "abschlag_hoehe" and "1.000,00" in x["fehler"] and "800,00" in x["fehler"] and "600,00" in x["fehler"], x)
x = A("PUT", f"belege/{b2['id']}", {"prozent": -5})
ok("Abschlag nachträglich auf −5 % ändern: abgelehnt", x["_s"] == 400, x)
x = A("PUT", f"belege/{b2['id']}", {"prozent": 20}); x = fest(b2["id"])
ok("auf 20 % geändert (zusammen 100 %): ohne Rückfrage", x["_s"] == 200 and x.get("status") == "fest", x)
b3 = A("POST", f"auftraege/{a['id']}/belege", {"art": "abschlag", "betrag": 50}); x = fest(b3["id"])
ok("weiterer Abschlag über 50 €: Rückfrage; bestätigt wird festgeschrieben", x["_s"] == 409 and fest(b3["id"], "abschlag_hoehe").get("status") == "fest", x)
sr = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); x = fest(sr["id"])
ok("Schlussrechnung mit Guthaben (Abschläge über dem Betrag): Rückfrage nennt das Guthaben", x["_s"] == 409 and x.get("rueckfrage") == "zahlbetrag_negativ" and "59,50" in x["fehler"], x)
x = fest(sr["id"], "zahlbetrag_negativ")
html = seite(f"/druck/{sr['id']}")
ok("Druck der Schlussrechnung: Abzüge mit einfachem Minus", x.get("status") == "fest" and "-952,00 €" in html and "-59,50 €" in html and "--" not in re.sub(r"<!--.*?-->|<style.*?</style>", "", html, flags=re.S), re.findall(r"-{1,2}\d[\d.,]* €", html)[:8])
st = A("POST", f"belege/{sr['id']}/storno", {})
sid = (st.get("storno") or st).get("id") or con.execute("select id from belege where bezug_id=? and art='storno'", (sr["id"],)).fetchone()[0]
html = seite(f"/druck/{sid}")
ok("Storno der Schlussrechnung druckt kein doppeltes Minus („--238,00“)", "--" not in re.sub(r"<!--.*?-->|<style.*?</style>", "", html, flags=re.S), re.findall(r"-{2}\d[\d.,]*", html)[:5])

print("== G6: Hinweistext der E-Rechnung")
xml = rq(inh, "GET", f"/api/belege/{sr['id']}/zugferd.xml")[1]
notizen = re.findall(r"<ram:Content>(Abzüglich[^<]*)</ram:Content>", xml)
t_ = date.today().strftime("%d.%m.%Y")
ok("Datum mit Punkten, Beträge mit Komma: „… vom TT.MM.JJJJ: netto 800,00 EUR …“", len(notizen) == 3 and all(f"vom {t_}:" in n for n in notizen) and "netto 800,00 EUR" in notizen[0], notizen)
sys.path.insert(0, "/home/claude/eberle-buero"); import epruefung
erg = epruefung.pruefen(xml.encode("utf-8"))
ok("E-Rechnung bleibt gültig nach EN 16931", not [f for f in (erg.get("fehler") if isinstance(erg, dict) else erg) or []], erg if not isinstance(erg, dict) else erg.get("fehler"))

print("== K7: Lohnanteil nach § 35a")
def lohn_rechnung(zeiten, extras=None, preis=None):
    k = A("POST", "kunden", {"kurzname": "Haus, Hans", "nachname": "Haus", "vorname": "Hans", "strasse": "Weg 3", "plz": "88069", "ort": "Tettnang", "gruppe": "Privatkunde"})
    a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Einbau"})
    po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Einbauschrank"}); pid = po.get("id") or po["position"]["id"]
    d = {"menge": 1, "zeitmodus": "stunden", "zeiten": zeiten}
    if extras: d["extras"] = extras
    if preis is not None: d.update(einzelpreis=preis, preis_manuell=1)
    A("PUT", f"positionen/{pid}", d)
    calc = (A("GET", f"positionen/{pid}").get("position") or {}).get("calc") or {}
    b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"})
    return A("GET", f"belege/{b['id']}"), calc
r, c = lohn_rechnung([{"kst": "BANKRAUM", "stunden": 10}, {"kst": "MONTAGE", "stunden": 4}, {"kst": "FAHRZEIT", "stunden": 1}])
la = r["daten"]["lohnanteil"]
wg = 1 + c["wg_pz"] / 100
ok("Kalkulation trennt die Arbeit beim Kunden: Montage und Fahrzeit, nicht die Werkstatt", 0 < c["lohn_gk_haushalt"] < c["lohn_gk"] * 0.5, (c.get("lohn_gk_haushalt"), c.get("lohn_gk")))
ok("Lohnanteil der Rechnung = Arbeit beim Kunden mit W+G (bisher alle Stunden)", abs(la["netto"] - kern.kfm(c["lohn_gk_haushalt"] * wg)) <= 0.02 and la["netto"] < kern.kfm(c["lohn_gk"] * wg) - 100, (la, c["lohn_gk_haushalt"] * wg, c["lohn_gk"] * wg))
html = seite(f"/druck/{r['id']}")
ok("Rechnung druckt den Satz mit „Leistungen in Ihrem Haushalt“ und dem Betrag", "Leistungen in Ihrem Haushalt" in html and kern.de(la["netto"]) in html, kern.de(la["netto"]))
r2, c2 = lohn_rechnung([{"kst": "BANKRAUM", "stunden": 10}])
ok("nur Werkstattstunden: Lohnanteil 0, der Satz entfällt", r2["daten"]["lohnanteil"]["netto"] == 0 and "35a" not in seite(f"/druck/{r2['id']}"), r2["daten"]["lohnanteil"])
r3, c3 = lohn_rechnung([], preis=480)
ok("fester Preis ohne Zeiten: Lohnanteil 0 (wie bisher)", r3["daten"]["lohnanteil"]["netto"] == 0, r3["daten"]["lohnanteil"])
r4, c4 = lohn_rechnung([], {"lohnanteil_pz": 100}, preis=480)
ok("fester Preis mit „Arbeit beim Kunden 100 %“: Lohnanteil 480,00 € netto, 571,20 € brutto", (r4["daten"]["lohnanteil"]["netto"], r4["daten"]["lohnanteil"]["brutto"]) == (480.0, 571.2), r4["daten"]["lohnanteil"])
r5, c5 = lohn_rechnung([], {"lohnanteil_pz": 40}, preis=1000)
ok("Anteil 40 % von 1.000 €: 400,00 € netto", r5["daten"]["lohnanteil"]["netto"] == 400.0, r5["daten"]["lohnanteil"])
A("PUT", "einstellungen", {"lohnanteil_kst": ["MONTAGE", "FAHRZEIT", "BANKRAUM"]})
r6, c6 = lohn_rechnung([{"kst": "BANKRAUM", "stunden": 10}, {"kst": "MONTAGE", "stunden": 4}, {"kst": "FAHRZEIT", "stunden": 1}])
ok("Kostenstellen sind wählbar: mit „BANKRAUM“ zählt auch die Werkstatt", abs(r6["daten"]["lohnanteil"]["netto"] - kern.kfm(c6["lohn_gk"] * (1 + c6["wg_pz"] / 100))) <= 0.02, (r6["daten"]["lohnanteil"], c6["lohn_gk"]))
A("PUT", "einstellungen", {"lohnanteil_kst": ["MONTAGE", "REPARAT", "FAHRZEIT"]})
e = A("GET", "einstellungen")
ok("Einstellungen liefern die Kostenstellen zur Auswahl und die Vorgabe", "MONTAGE" in e.get("_kostenstellen", []) and e.get("lohnanteil_kst") == ["MONTAGE", "REPARAT", "FAHRZEIT"], (e.get("_kostenstellen"), e.get("lohnanteil_kst")))
# Helferstunden bei der Montage zählen mit
kalk = kalkulation.vorgaben_kopie({}); kalk["_haushalt_kst"] = ["MONTAGE"]
kalk["loehne"] = [{"gruppe": g["gruppe"], "lohn": 30.0, "lnk": g.get("lnk", 0)} for g in kalk["loehne"]]
ch = kalkulation.position_rechnen({"menge": 1, "stueckliste": [], "zeiten": [{"kst": "MONTAGE", "minuten": 60, "helfer": 1.0, "name": "Einbau"}, {"kst": "BANKRAUM", "minuten": 60, "helfer": 1.0, "name": "Bau"}]}, kalk)
ok("Helfer bei der Montage zählt zur Arbeit beim Kunden, Helfer in der Werkstatt nicht", abs(ch["lohn_gk_haushalt"] - (30 * 2.3 + 30 * 2.1)) < 1e-6, ch["lohn_gk_haushalt"])

print("== F4/W2: Skonto im DATEV-Stapel")
A("PUT", "einstellungen", {"datev": {"berater": "12345", "mandant": "100", "skr": "03", "bankumsaetze": True}})
kid = A("POST", "kunden", {"kurzname": "Skonto, Susi", "nachname": "Skonto", "vorname": "Susi", "plz": "88069", "ort": "Tettnang"})["id"]
A("PUT", f"kunden/{kid}", {"skonto": 2, "skontotage": 10})
a = A("POST", "auftraege", {"kunde_id": kid, "bezeichnung": "Skonto"}); po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Leistung"}); pid = po.get("id") or po["position"]["id"]
A("PUT", f"positionen/{pid}", {"einzelpreis": 1000, "preis_manuell": 1, "menge": 1}); b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); f_ = fest(b["id"])
o = dict(con.execute("select * from offene_posten where beleg_id=?", (b["id"],)).fetchone())
x = A("POST", f"offeneposten/{o['id']}/zahlung", {"betrag": 1166.20, "skonto": 23.80, "datum": H})
ok("Kundenzahlung mit 2 % Skonto gebucht", x["_s"] == 200 and abs(dict(con.execute("select offen from offene_posten where id=?", (o["id"],)).fetchone())["offen"]) < 0.005, x)
lf = A("POST", "lieferanten", {"kurzname": "Holzhandel", "firma": "Holzhandel KG", "iban": "DE75512108001245126199"})
z1 = A("POST", "zahlungen", {"lieferant_id": lf["id"], "belegnr": "LS-1", "betrag": 1000.00, "vorsteuer": 19, "belegdatum": H, "faellig": tag(30), "skonto": 3, "skonto_bis": tag(8),
                             "iban": "DE75512108001245126199", "empfaenger": "Holzhandel KG"})
z2 = A("POST", "zahlungen", {"lieferant_id": lf["id"], "belegnr": "LS-2", "betrag": 500.00, "vorsteuer": 7, "belegdatum": H, "faellig": tag(30), "iban": "DE75512108001245126199", "empfaenger": "Holzhandel KG"})
x = A("PUT", f"zahlungen/{z1['id']}", {"bezahlt": H}); x2 = A("PUT", f"zahlungen/{z2['id']}", {"bezahlt": H})
if con.execute("select bezahlt from zahlungen where id=?", (z1["id"],)).fetchone()[0] != H:
    x = A("POST", "zahlungen/bezahlt", {"ids": [z1["id"], z2["id"]], "datum": H})
ok("Zahlungsaufträge als bezahlt markiert", [r[0] for r in con.execute("select bezahlt from zahlungen where id in (?,?)", (z1["id"], z2["id"]))] == [H, H], (x, x2))
dv = A("POST", "service/datev", {"von": H[:4] + "-01-01", "bis": H[:4] + "-12-31"})
ok("DATEV-Stapel erstellt", dv["_s"] == 200 and dv.get("datei"), dv)
z = zipfile.ZipFile(D + "/exporte/" + dv["datei"]); csvn = next(n for n in z.namelist() if n.startswith("EXTF")); zeilen = [l.split(";") for l in z.read(csvn).decode("cp1252").split("\r\n")[2:] if l]
skg = [l for l in zeilen if l[6] == "8736"]; ske = [l for l in zeilen if l[7] == "3736"]
ok("gewährtes Skonto: 23,80 € Soll 8736 an Debitor 10000 mit der Rechnungsnummer", len(skg) == 1 and skg[0][0] == "23,80" and skg[0][1] == '"S"' and skg[0][7] == "10000" and f_["nummer"].replace("-", "") in skg[0][10].replace("-", ""), skg)
ok("erhaltenes Skonto: 30,00 € Kreditor 70000 an 3736 mit der Belegnummer", len(ske) == 1 and ske[0][0] == "30,00" and ske[0][6] == "70000" and "LS-1" in ske[0][10], ske)
ok("Zahlungsauftrag ohne Skonto erzeugt keine Skontozeile", not any("LS-2" in l[10] and (l[7] in ("3731", "3736", "3730")) for l in zeilen))
info = z.read("LIESMICH.txt").decode("utf-8")
ok("Begleittext nennt die Skontobuchungen und die Abstimmung mit der Kanzlei", "Skonto" in info and "Kanzlei" in info and "Gewährte Skonti 19 % USt: 8736" in info, info[-900:])
A("PUT", "einstellungen", {"datev": {"berater": "12345", "mandant": "100", "skr": "04", "bankumsaetze": True, "skonto": False}})
dv2 = A("POST", "service/datev", {"von": H[:4] + "-01-01", "bis": H[:4] + "-12-31"})
z = zipfile.ZipFile(D + "/exporte/" + dv2["datei"]); zeilen2 = [l.split(";") for l in z.read(next(n for n in z.namelist() if n.startswith("EXTF"))).decode("cp1252").split("\r\n")[2:] if l]
ok("abgeschaltet: keine Skontozeilen (SKR 04: 4736, 5736)", not any(l[6] in ("4736", "5736") or l[7] in ("4736", "5736") for l in zeilen2), [l[:8] for l in zeilen2])
cfg = A("GET", "service/datev")
ok("Skontokonten erscheinen in der Kontenzuordnung (SKR 04: 4736 und 5736)", cfg["standard"].get("skonto_gew_19") == 4736 and cfg["standard"].get("skonto_erh_19") == 5736 and "skonto_gew_19" in cfg["texte"], cfg.get("standard"))
print("FEHLER:", fehler)
