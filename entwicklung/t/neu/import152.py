"""Version 152, Importe: Stücklistenimport meldet Unlesbares und erkennt den doppelten Import (I9), Preisimport fragt nach unbekannten
Einheiten und nennt doppelte Artikelnummern und Fremdwährung (I6, I11). Erwartet eine frische Prüfinstanz (bash /tmp/claude-0/t/v25/neu.sh)."""
import json, sys, base64
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
sys.path.insert(0, "/home/claude/eberle-buero")
import stuecklistenimport as si
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:600]))
    if not bed: fehler.append(name)
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, h=None):
    s, b, hd = rq(inh, m, "/api/" + p, d, {"X-Rueckfrage": "1", **(h or {})}); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j

print("== Stücklistenimport: strenges Lesen")
Z = si.zahl_lesen
ok("Zahlen: 600 · 2.000,0 · 1250,5 · 1250.5 werden gelesen", (Z("600"), Z("2.000,0"), Z("1250,5"), Z("1250.5")) == ((600.0, "ok"), (2000.0, "ok"), (1250.5, "ok"), (1250.5, "ok")), (Z("600"), Z("2.000,0"), Z("1250,5"), Z("1250.5")))
ok("„1250mm“, „ca. 600“, „12,5,3“ sind unlesbar; leer bleibt leer", Z("1250mm")[1] == Z("ca. 600")[1] == Z("12,5,3")[1] == "unlesbar" and Z("")[1] == "" and Z("  ")[1] == "")
ok("„1.250“: mit Dezimalkommas in der Datei eindeutig 1250, ohne Anhalt 1250 mit Hinweis, in einer Datei mit Dezimalpunkten 1,25",
   (Z("1.250", "komma"), Z("1.250"), Z("1.250", "punkt")) == ((1250.0, "ok"), (1250.0, "mehrdeutig"), (1.25, "ok")), (Z("1.250", "komma"), Z("1.250"), Z("1.250", "punkt")))
ok("in einer Datei mit Dezimalkommas ist „600.5“ keine Zahl", Z("600.5", "komma")[1] == "unlesbar")
text = "\n".join([
    ";Schrank;1;2.000,0;800,0;600,0",
    "P19;Seite;2;2.000,0;600,0;K1;;K1;K1",          # gut
    "P19;Boden;2;1250mm;600,0",                      # Länge unlesbar: weder Teil noch Beschlag
    "P19;Fach;0;764,0;580,0",                        # Stückzahl 0
    "P19;Blende;2,5;764,0;100,0",                    # Stückzahl gebrochen
    "P19;Rueckwand;1;1.250;780,0",                   # 1.250 in einer Komma-Datei = 1250
    "P19;Sockel;1;764,0;",                           # Breite fehlt
    "B77;Topfband;4",                                # Beschlag
    "B78;Griff;;",                                   # Anzahl fehlt → 1 mit Hinweis
    "B79;Leiste;-2",                                 # negativ
    "XX",                                            # zu wenige Felder
])
pos, teile, bs, erw, hin = si.zeilen_lesen(text)
fe = [h for h in hin if h["art"] == "fehler"]; hi = [h for h in hin if h["art"] == "hinweis"]
ok("gelesen werden 2 Teile und 2 Beschläge; die Positionszeile bleibt", len(teile) == 2 and len(bs) == 2 and pos and pos["h"] == 2000 and pos["menge"] == 1, (len(teile), len(bs), pos))
ok("die Zeile mit „1250mm“ wird nicht zum Beschlag umgedeutet", not any(b["nr"] == "P19" for b in bs) and any(h["zeile"] == 3 and "1250mm" in h["text"] and "keine Zahl" in h["text"] for h in fe), fe)
ok("Stückzahl 0, Stückzahl 2,5, fehlende Breite, negative Anzahl und zu wenige Felder werden ausgelassen und mit Zeilennummer gemeldet",
   sorted(h["zeile"] for h in fe) == [3, 4, 5, 7, 10, 11], sorted(h["zeile"] for h in fe))
ok("„1.250“ wird als 1250 mm gelesen (nicht 1,25)", any(t["verwendung"] == "Rueckwand" and t["laenge"] == 1250 for t in teile), teile)
ok("fehlende Anzahl beim Beschlag: 1 angenommen, als Hinweis gemeldet", any(b["nr"] == "B78" and b["menge"] == 1 for b in bs) and any(h["zeile"] == 9 and "1 angenommen" in h["text"] for h in hi), hi)
p2, t2, b2, _, h2 = si.zeilen_lesen("P19;Seite;2;1.250;600\nP19;Boden;1;800;400")
ok("ohne Dezimalkomma in der Datei: „1.250“ als 1250 gelesen und zur Prüfung gemeldet", t2[0]["laenge"] == 1250 and any("Tausenderzeichen" in h["text"] for h in h2), h2)
p3, t3, b3, _, h3 = si.zeilen_lesen("P19;Seite;2;1250.5;600.25\nP19;Boden;1;600.000;400.000")
ok("Datei mit Dezimalpunkten: 1250.5 und 600.000 (= 600) ohne Meldung", [t["laenge"] for t in t3] == [1250.5, 600.0] and not h3, (t3, h3))
p4, t4, b4, _, h4 = si.zeilen_lesen(";Schrank A;1;2000;800;600\nP19;Seite;2;2000;600\n;Schrank B;1;1000;800;600\nP19;Seite;2;1000;600")
ok("zweite Positionszeile in den Daten wird gemeldet", len(t4) == 2 and any(h["zeile"] == 3 and "weitere Positionszeile" in h["text"] for h in h4), h4)

print("== Stücklistenimport an der Schnittstelle")
k = A("POST", "kunden", {"kurzname": "Holz, Hanna", "nachname": "Holz", "plz": "88069", "ort": "Tettnang"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Schrank"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Schrank"}); pid = po.get("id") or po["position"]["id"]
v = A("POST", f"positionen/{pid}/stueckliste-import", {"text": text})
ok("Vorschau nennt 6 ausgelassene Zeilen und alle Hinweise", v["_s"] == 200 and v["ausgelassen"] == 6 and len(v["hinweise"]) >= 7 and v["teile"] == 2 and v["beschlaege"] == 2, (v.get("ausgelassen"), v.get("fehler")))
ok("Vorschau: noch nichts doppelt", v["doppelt"] == {"teile": 0, "beschlaege": 0, "alles": False}, v["doppelt"])
r = A("POST", f"positionen/{pid}/stueckliste-import", {"text": text, "ausfuehren": True, "zuordnung": {}})
ok("Import: 2 Teile, 2 Beschläge, 6 Zeilen ausgelassen gemeldet", r["_s"] == 200 and r["import"]["teile"] == 2 and r["import"]["beschlaege"] == 2 and r["import"]["ausgelassen"] == 6, r.get("import") or r)
p_ = A("GET", f"positionen/{pid}")
st = (p_.get("position") or p_).get("stueckliste") or []
ok("in der Stückliste stehen genau die zwei lesbaren Teile", len(st) == 2 and sorted(t["laenge"] for t in st) == [1250, 2000], st)
mats = A("GET", "material")["liste"]
ok("für die unlesbare Zeile wurde kein Beschlag „P19“ angelegt", not any((m.get("cad") or "") == "P19" and m["kategorie"] == "beschlaege" for m in mats), [(m["nummer"], m["kategorie"], m.get("cad")) for m in mats])
v2 = A("POST", f"positionen/{pid}/stueckliste-import", {"text": text})
ok("zweite Vorschau derselben Daten: alles schon enthalten", v2["doppelt"]["alles"] and v2["doppelt"]["teile"] == 2 and v2["doppelt"]["beschlaege"] == 2, v2["doppelt"])
r2 = A("POST", f"positionen/{pid}/stueckliste-import", {"text": text, "ausfuehren": True, "zuordnung": {}})
ok("derselbe Import noch einmal: Rückfrage statt doppelter Stückliste", r2["_s"] == 409 and r2.get("rueckfrage") == "stueckliste_doppelt", r2)
p_ = A("GET", f"positionen/{pid}"); st = (p_.get("position") or p_).get("stueckliste") or []
ok("nach der Rückfrage ist nichts verdoppelt", len(st) == 2, len(st))
r3 = A("POST", f"positionen/{pid}/stueckliste-import", {"text": text, "ausfuehren": True, "zuordnung": {}, "ersetzen": True})
p_ = A("GET", f"positionen/{pid}"); st = (p_.get("position") or p_).get("stueckliste") or []
ok("mit „ersetzen“ ohne Rückfrage, Stückliste bleibt bei 2 Teilen", r3["_s"] == 200 and len(st) == 2, (r3["_s"], len(st)))
r4 = A("POST", f"positionen/{pid}/stueckliste-import", {"text": text, "ausfuehren": True, "zuordnung": {}}, {"X-Bestaetigt": "stueckliste_doppelt"})
p_ = A("GET", f"positionen/{pid}"); st = (p_.get("position") or p_).get("stueckliste") or []
ok("bestätigt: wird angehängt (4 Teile)", r4["_s"] == 200 and len(st) == 4, (r4["_s"], len(st)))
r5 = A("POST", f"positionen/{pid}/stueckliste-import", {"text": "XX;Seite;zwei;lang;breit"})
ok("nur unlesbare Zeilen: klare Fehlermeldung mit Zeile", r5["_s"] == 400 and "Zeile 1" in r5.get("fehler", ""), r5)
# Umrechnung aus dem Materialstamm kommt in die Auftragswerte
m = A("POST", "material", {"kategorie": "holzwerkstoffe", "gruppe": "Kanten", "bezeichnung": "ABS-Kante Rolle 50 m", "einheit": "Rolle", "ek_preis": 60, "umrechnung": 50, "cad": "KRO"})
r6 = A("POST", f"positionen/{pid}/stueckliste-import", {"text": "P19;Tuer;1;700;400;KRO;KRO;KRO;KRO", "ausfuehren": True, "zuordnung": {}})
au = A("GET", f"auftraege/{a['id']}/kalk")
wk = [w for w in au["kalk"].get("werkstoffe", []) if w.get("matnr") == m.get("nummer")]
ok("Kante „Rolle“ aus dem Stamm kommt mit Umrechnung 50 in die Auftragswerte", r6["_s"] == 200 and wk and wk[0].get("um") == 50 and wk[0].get("einheit") == "Rolle", (r6.get("fehler"), wk))

print("== Preisimport: Einheiten, doppelte Nummern, Fremdwährung")
csv = "\n".join(["Artikelnummer;Bezeichnung;Preis;Einheit",
                 "T-1;Spanplatte 2800x2070;64,90;TAFEL", "T-2;Furnierblatt Eiche;18,50;BL", "T-3;PU-Lack 25 l;212,00;KAN", "T-4;Topfband;2,60;ST",
                 "T-4;Topfband ab 100;1,99;ST", "T-5;Schweizer Beschlag;CHF 9,80;ST", "T-6;Griff ohne Einheit;4,20;"])
def lesen_(inhalt, name="preise.csv"):
    return A("POST", "preisimport/lesen", {"daten": base64.b64encode(inhalt.encode("utf-8")).decode(), "dateiname": name})
pl = lesen_(csv)
ok("Preisdatei gelesen: 6 neue Artikel", pl["_s"] == 200 and pl["neu_gesamt"] == 6, (pl.get("fehler"), pl.get("neu_gesamt")))
ok("Hinweis nennt die doppelte Artikelnummer mit beiden Preisen", "mehrfach" in pl["hinweis"] and "T-4" in pl["hinweis"] and "2,60" in pl["hinweis"] and "1,99" in pl["hinweis"], pl["hinweis"])
ok("Hinweis nennt den Preis in CHF", "CHF" in pl["hinweis"] and "rechnet nicht um" in pl["hinweis"], pl["hinweis"])
neu = {x["artnr"]: x for x in pl["neu"]}
ok("Vorschau kennzeichnet unbekannte Einheiten (TAFEL, BL, KAN, leer) und lässt Stk. unmarkiert",
   all(neu[n]["einheit_unbekannt"] for n in ("T-1", "T-2", "T-3", "T-6")) and not neu["T-4"]["einheit_unbekannt"], {n: (x["einheit"], x["einheit_unbekannt"]) for n, x in neu.items()})
ok("Vorschau kennzeichnet die Fremdwährung am Artikel", neu["T-5"].get("waehrung") == "CHF" and not neu["T-4"].get("waehrung"), neu["T-5"])
an = A("POST", "preisimport/anlegen", {"schluessel": pl["schluessel"], "auswahl": ["T-1", "T-2", "T-3", "T-4", "T-6"], "kategorie": "holzwerkstoffe"})
ok("Anlegen ohne Zuordnung: nichts angelegt, die vier offenen Einheiten werden zurückgefragt",
   an["_s"] == 200 and an["angelegt"] == 0 and sorted(x["einheit"] for x in an.get("einheiten_fehlen", [])) == ["", "BL", "KAN", "TAFEL"], an)
ok("im Materialstamm ist noch nichts aus der Datei", not any((m_.get("bestellnr") or "").startswith("T-") for m_ in A("GET", "material")["liste"]))
an2 = A("POST", "preisimport/anlegen", {"schluessel": pl["schluessel"], "auswahl": ["T-1", "T-2", "T-3", "T-4", "T-6"], "kategorie": "holzwerkstoffe",
                                         "einheiten": {"TAFEL": "Stk.", "BL": "Stk.", "KAN": "Dose", "": "Stk."}})
stamm = {m_["bestellnr"]: m_ for m_ in A("GET", "material")["liste"] if (m_.get("bestellnr") or "").startswith("T-")}
ok("mit Zuordnung: 5 Artikel angelegt, Einheit wie gewählt (Tafel als Stk., nicht als m²)",
   an2["_s"] == 200 and an2["angelegt"] == 5 and stamm["T-1"]["einheit"] == "Stk." and stamm["T-3"]["einheit"] == "Dose" and stamm["T-6"]["einheit"] == "Stk." and stamm["T-4"]["einheit"] == "Stk.",
   (an2, {n: m_["einheit"] for n, m_ in stamm.items()}))
ok("bei doppelter Nummer gilt die erste Zeile (2,60)", abs(stamm["T-4"]["ek_preis"] - 2.60) < 1e-9, stamm["T-4"]["ek_preis"])
an3 = A("POST", "preisimport/anlegen", {"schluessel": pl["schluessel"], "auswahl": ["T-5"], "kategorie": "beschlaege"})
ok("Artikel mit CHF-Preis: Rückfrage vor dem Anlegen", an3["_s"] == 409 and an3.get("rueckfrage") == "fremdwaehrung", an3)
an4 = A("POST", "preisimport/anlegen", {"schluessel": pl["schluessel"], "auswahl": ["T-5"], "kategorie": "beschlaege"}, {"X-Bestaetigt": "fremdwaehrung"})
ok("bestätigt: wird angelegt", an4["_s"] == 200 and an4["angelegt"] == 1, an4)
# Preisabgleich: Fremdwährung nicht vorausgewählt, Rückfrage beim Übernehmen
pl2 = lesen_("Artikelnummer;Bezeichnung;Preis CHF;Einheit\nT-4;Topfband;2,90;ST\nT-1;Spanplatte;70,00;TAFEL")
tr = {t["bestellnr"]: t for t in pl2["treffer"]}
ok("Spalte „Preis CHF“: Treffer gekennzeichnet und nicht vorausgewählt", tr["T-4"]["waehrung"] == "CHF" and not tr["T-4"]["vorschlag"] and tr["T-1"]["waehrung"] == "CHF", tr)
ue = A("POST", "preisimport/uebernehmen", {"posten": [tr["T-4"]]})
ok("Übernehmen eines CHF-Preises: Rückfrage", ue["_s"] == 409 and ue.get("rueckfrage") == "fremdwaehrung", ue)
ok("Zählung „ohne Treffer“ stimmt weiter", pl2["materialien"] - len(pl2["treffer"]) == pl2["ohne_treffer"], (pl2["materialien"], len(pl2["treffer"]), pl2["ohne_treffer"]))

print("== Kundenimport: Dubletten einzeln, nur Felder der Datei, Protokoll, Altbestand")
import sqlite3
DB = "/tmp/claude-0/t/v25/eberle-buero/daten/buero.db"
def db(sql, par=()):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    try: return [dict(r) for r in c.execute(sql, par)]
    finally: c.close()
def kimp(inhalt, name="kunden.csv", **kw):
    return A("POST", "kunden/import", {"daten": base64.b64encode(inhalt.encode("utf-8")).decode(), "dateiname": name, **kw})
gruppen = A("GET", "einstellungen").get("kundengruppen") or []
gk = next((g for g in gruppen if "privat" not in g.lower()), gruppen[-1] if gruppen else "Geschäftskunde")
berta = A("POST", "kunden", {"anredeform": "Frau", "vorname": "Berta", "nachname": "Bestand", "strasse": "Altweg", "hausnr": "5", "plz": "88069", "ort": "Tettnang",
                             "email1": "familie@bestand.example", "gruppe": gk, "rabatt": 5, "skonto": 2, "skontotage": 10, "zahlungsziel": 21})
A("PUT", f"kunden/{berta['id']}", {"anrede": "Liebe Berta,", "bemerkungen": "Schlüssel beim Nachbarn"})
clara = A("POST", "kunden", {"anredeform": "Frau", "vorname": "Clara", "nachname": "Gleich", "strasse": "Hauptstr.", "hausnr": "1", "plz": "88069", "ort": "Tettnang", "telefon": "07542 1"})
csvk = "\n".join(["Anrede;Vorname;Nachname;Straße;PLZ;Ort;E-Mail;Telefon;Bemerkung",
                  "Herr;Bernd;Bestand;Neuweg 9;01067;Dresden;familie@bestand.example;;Sohn",          # andere Person, gleiche Mailadresse
                  "Frau;Clara;Gleich;Hauptstr. 1;88069;Tettnang;clara@gleich.example;07542 999;",       # dieselbe Person: Name und PLZ
                  "Herr;Neo;Neu;Feldweg 3;88069;Tettnang;neo@neu.example;;"])
v = kimp(csvk)
dub = {x["datei"]["kurzname"]: x for x in v.get("dubletten", [])}
ok("Vorschau nennt die zwei Dubletten einzeln mit Grund", v["_s"] == 200 and v["doppelte"] == 2 and set(dub) == {"Bestand, Bernd", "Gleich, Clara"} and dub["Bestand, Bernd"]["grund"] == "E-Mail" and dub["Gleich, Clara"]["grund"] == "Name und PLZ", (v.get("fehler"), dub))
ok("gleiche Mailadresse, anderer Name: als unsicher gekennzeichnet; gleicher Name: sicher", dub["Bestand, Bernd"]["sicher"] is False and dub["Gleich, Clara"]["sicher"] is True)
ok("Vorschau zeigt, was sich ändern würde (Telefon, E-Mail bei Clara)", {a[0] for a in dub["Gleich, Clara"]["aenderungen"]} >= {"Telefon", "E-Mail"}, dub["Gleich, Clara"]["aenderungen"])
vor_prot = len(db("SELECT nr FROM protokoll"))
r = kimp(csvk, ausfuehren=True, doppelte="aktualisieren", bestaetigt=[dub["Gleich, Clara"]["zeile"]], altbestand=False)
ok("Import: 1 neu, 1 aktualisiert, 1 nicht bestätigte Dublette bleibt unverändert", r["_s"] == 200 and (r["neu"], r["aktualisiert"], r["unbestaetigt"]) == (1, 1, 1), r)
b2 = A("GET", f"kunden/{berta['id']}"); b2 = b2.get("kunde") or b2
ok("der fremde Mensch mit gleicher Mailadresse hat den Bestandskunden nicht überschrieben", (b2["vorname"], b2["strasse"], b2["plz"], b2["ort"]) == ("Berta", "Altweg", "88069", "Tettnang"), b2)
c2 = A("GET", f"kunden/{clara['id']}"); c2 = c2.get("kunde") or c2
ok("bestätigte Dublette: Telefon und E-Mail aus der Datei übernommen", c2["telefon"] == "07542 999" and c2["email1"] == "clara@gleich.example", (c2["telefon"], c2["email1"]))
neo = db("SELECT * FROM kunden WHERE nachname='Neu'")[0]
ok("als Kontakte importiert: neuer Kunde ohne Aufbewahrungsfrist", not (neo["aufbewahren_bis"] or ""), neo["aufbewahren_bis"])
p_neu = db("SELECT art, objekt, text, daten FROM protokoll ORDER BY nr")[vor_prot:]
ok("Protokoll: ein Eintrag für den Import (Datei, Zahlen, Benutzer) und einer für den geänderten Kunden",
   any(p["art"] == "kundenimport" and "kunden.csv" in p["text"] and "1 neu" in p["text"] and "1 aktualisiert" in p["text"] for p in p_neu)
   and any(p["art"] == "stammdaten" and "Kontaktdaten geändert" in p["text"] for p in p_neu), [(p["art"], p["text"]) for p in p_neu])
ok("Protokoll hält die Prüfsumme der Datei fest", any(p["art"] == "kundenimport" and len(json.loads(p["daten"]).get("sha256", "")) == 64 for p in p_neu))
# bestätigt man die unsichere Dublette doch: nur Felder der Datei, Gepflegtes bleibt
r2 = kimp(csvk, ausfuehren=True, doppelte="aktualisieren", bestaetigt=[dub["Bestand, Bernd"]["zeile"]], altbestand=False)
b3 = A("GET", f"kunden/{berta['id']}"); b3 = b3.get("kunde") or b3
ok("ausdrücklich bestätigt: Name und Anschrift kommen aus der Datei", r2["aktualisiert"] == 1 and (b3["vorname"], b3["strasse"], b3["plz"]) == ("Bernd", "Neuweg", "01067"), (r2, b3["vorname"], b3["strasse"], b3["plz"]))
ok("Gruppe, Konditionen und die von Hand gesetzte Briefanrede bleiben (stehen nicht in der Datei)",
   b3["gruppe"] == gk and b3["rabatt"] == 5 and b3["skonto"] == 2 and b3["zahlungsziel"] == 21 and b3["anrede"] == "Liebe Berta,", (b3["gruppe"], b3["rabatt"], b3["skonto"], b3["zahlungsziel"], b3["anrede"]))
ok("gepflegte Bemerkung bleibt, der Text der Datei wird angehängt", b3["bemerkungen"].startswith("Schlüssel beim Nachbarn") and "Sohn" in b3["bemerkungen"], b3["bemerkungen"])
r3 = kimp("Nachname;Vorname;PLZ;Ort\nAlt;Anna;88069;Tettnang", ausfuehren=True, altbestand=True)
alt = db("SELECT * FROM kunden WHERE nachname='Alt'")[0]
ok("als Altbestand importiert: Aufbewahrungsfrist gesetzt", r3["neu"] == 1 and (alt["aufbewahren_bis"] or "").endswith("-12-31"), alt["aufbewahren_bis"])
r4 = kimp("Nachname;Vorname;PLZ;Ort\nAlt;Anna;88069;Tettnang\nAlt;Anna;88069;Tettnang\nZwei;Zora;88069;Tettnang\nZwei;Zora;88069;Tettnang", ausfuehren=True, altbestand=False)
ok("dieselbe Zeile zweimal in einer Datei wird nur einmal angelegt", (r4["neu"], r4["uebersprungen"]) == (1, 3), r4)

print("== Kundenimport: Postleitzahl und Telefon aus Excel")
import kundenimport as ki
k1 = ki.datensatz(["Sachse", "1067", "Dresden", "351123456", "Deutschland"], {"0": "nachname", "1": "plz", "2": "ort", "3": "telefon", "4": "land"}, [], "")
k2 = ki.datensatz(["Wiener", "1070", "Wien", "", "Österreich"], {"0": "nachname", "1": "plz", "2": "ort", "3": "telefon", "4": "land"}, [], "")
k3 = ki.datensatz(["Offen", "1067", "Dresden", "", ""], {"0": "nachname", "1": "plz", "2": "ort", "3": "telefon", "4": "land"}, [], "")
k4 = ki.datensatz(["Offen", "1067", "Dresden", "", ""], {"0": "nachname", "1": "plz", "2": "ort", "3": "telefon", "4": "land"}, [], "", True)
ok("Land Deutschland: 1067 wird zu 01067", k1["plz"] == "01067")
ok("Land Österreich: 1070 bleibt 1070", k2["plz"] == "1070" and not k2.get("_plz_vier"))
ok("ohne Landesangabe: bleibt 1067 und wird gemeldet; mit gewählter Ergänzung 01067", k3["plz"] == "1067" and k3.get("_plz_vier") and k4["plz"] == "01067")
ok("Telefonnummer ohne führende Null wird gemeldet, nicht verändert", k1.get("_tel_ohne_null") and k1["telefon"] == "351123456")
v5 = kimp("Nachname;PLZ;Ort;Telefon\nSachse;1067;Dresden;351123456\nSchwabe;88069;Tettnang;07542 5")
ok("Vorschau nennt vierstellige Postleitzahl und Telefonnummer ohne Null mit Beispiel",
   v5["plz_vier"]["anzahl"] == 1 and "1067" in v5["plz_vier"]["beispiele"][0] and v5["tel_ohne_null"]["anzahl"] == 1 and "351123456" in v5["tel_ohne_null"]["beispiele"][0], (v5.get("plz_vier"), v5.get("tel_ohne_null")))
r5 = kimp("Nachname;PLZ;Ort;Telefon\nSachse;1067;Dresden;351123456", ausfuehren=True, altbestand=False, plz_auffuellen=True)
ok("mit „ergänzen“ importiert: 01067", db("SELECT plz FROM kunden WHERE nachname='Sachse'")[0]["plz"] == "01067")
import time as _t
gross = "Nachname;Vorname;PLZ;Ort;E-Mail\n" + "\n".join(f"Masse{i};Max;88069;Tettnang;m{i}@masse.example" for i in range(3000))
t0 = _t.time(); kimp(gross, ausfuehren=True, altbestand=False); t1 = _t.time(); vg = kimp(gross); t2 = _t.time()
ok(f"3.000 Kunden: Import {t1 - t0:.1f} s, erneute Vorschau mit 3.000 Dubletten {t2 - t1:.1f} s (jeweils unter 15 s)", t1 - t0 < 15 and t2 - t1 < 15 and vg["doppelte"] == 3000, (t1 - t0, t2 - t1, vg.get("doppelte")))
print("FEHLER:", fehler)
