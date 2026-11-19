"""Version 152, Paket 3 des Prüfberichts (Pflege und Zukunft): Basiszinssatz, Mindestlohn und Umsatzsteuersätze mit Stichtag (Z12, K10),
Prüfung der Einstellungen nach Art und Wertebereich (E4, E5), Datumsfelder (F7), gleichzeitiges Bearbeiten (F6), Startseite mit
gemerkten Auftragswerten (P7), Versionsprüfung beim Start (Z10). Erwartet eine frische Prüfinstanz."""
import json, sys, os, re, time, sqlite3, hashlib, shutil, subprocess, urllib.request
from datetime import date, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
Q = "/home/claude/eberle-buero"
T = "/tmp/claude-0/t"
I = "/tmp/claude-0/t/v25/eberle-buero"
D = I + "/daten"
sys.path.insert(0, I)
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:900]), flush=True)
    if not bed: fehler.append(name)
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, h=None, c=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, {"X-Rueckfrage": "1", **(h or {})}); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_kopf"] = dict(hd) if hd else {}
    else: j = {"_s": s, "liste": j}
    return j
heute = date.today(); H = heute.isoformat()
de = lambda x: f"{x:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
ded = lambda iso: f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"
kfm = lambda x: float(f"{x + (1e-9 if x >= 0 else -1e-9):.2f}")
A("PUT", "einstellungen", {"firma": "Muster Schreinerei", "firma_anschrift": "Weg 1\n88069 Tettnang", "firma_inhaber": "Jonas Muster", "steuernummer": "12/345/67890",
                           "firma_telefon": "07542 1", "firma_email": "a@b.example", "sepa_iban": "DE02120300000000202051", "sepa_bic": "BYLADEM1001"})
k = A("POST", "kunden", {"kurzname": "Haus, Hanna", "nachname": "Haus", "vorname": "Hanna", "anredeform": "Frau", "strasse": "Gartenweg", "hausnr": "4", "plz": "88069", "ort": "Tettnang", "gruppe": "Privatkunde"})
def auftrag(bez, preis, status=None):
    a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": bez})
    po = A("POST", f"auftraege/{a['id']}/positionen", {"text": bez}); pid = po.get("id") or po["position"]["id"]
    A("PUT", f"positionen/{pid}", {"einzelpreis": preis, "preis_manuell": 1, "menge": 1})
    if status: A("PUT", f"auftraege/{a['id']}", {"status": status})
    return a, pid
def fest(bid, bestaetigt="rechnungsdatum,position_null"):
    x = A("POST", f"belege/{bid}/festschreiben", {}, {"X-Bestaetigt": bestaetigt}); return x.get("beleg") or x

print("== K10: Basiszinssatz mit Stichtag, Zinsen je Zeitraum")
import mahnwesen, rechtswerte, personal
L = mahnwesen.zinsliste()
ok("hinterlegte Liste: aufsteigend, jedes Halbjahr seit 2002, zuletzt 1,52 % ab 01.07.2026",
   [ab for ab, _ in L] == sorted(ab for ab, _ in L) and L[-1] == ("2026-07-01", 1.52) and [ab for ab, _ in L] == mahnwesen.halbjahre("2002-07-01", "2026-07-01"), L[-3:])
ok("Sätze an bekannten Tagen: 2022 −0,88 %, 15.03.2024 3,62 %, 01.07.2025 1,27 %", [mahnwesen.basiszins_am(L, t) for t in ("2022-03-01", "2024-03-15", "2025-07-01")] == [-0.88, 3.62, 1.27])
ab = mahnwesen.zins_abschnitte(1000, "2026-05-31", "2026-07-15", L, False)
ok("Verzug über den 1. Juli 2026: 30 Tage zu 6,27 % (5,15 €) und 15 Tage zu 6,52 % (2,68 €)",
   [(a["von"], a["bis"], a["tage"], a["satz"], a["betrag"]) for a in ab] == [("2026-06-01", "2026-06-30", 30, 6.27, 5.15), ("2026-07-01", "2026-07-15", 15, 6.52, 2.68)], ab)
ok("Summe, Tage und letzter Satz stimmen damit überein", mahnwesen.verzugszinsen(1000, "2026-05-31", "2026-07-15", L, False) == (7.83, 45, 6.52))
ok("ohne Wechsel des Satzes wie bisher: ein Abschnitt, taggenau durch 365", mahnwesen.verzugszinsen(1000, "2026-08-01", "2026-08-31", L, False) == (kfm(1000 * 6.52 / 100 * 30 / 365), 30, 6.52)
   and len(mahnwesen.zins_abschnitte(1000, "2026-01-10", "2026-06-20", L, False)) == 1)
ok("Geschäftskunde: 9 Prozentpunkte; negativer Basiszins 2022 ergibt 8,12 %", mahnwesen.zins_abschnitte(1000, "2022-03-01", "2022-03-31", L, True)[0]["satz"] == 8.12)
ok("ein einzelner Satz statt der Liste rechnet wie bis Version 151", mahnwesen.verzugszinsen(1000, "2026-05-31", "2026-07-15", 1.52, False) == (kfm(1000 * 6.52 / 100 * 45 / 365), 45, 6.52))
ok("kein Verzug, kein Betrag: nichts", mahnwesen.zins_abschnitte(1000, "2026-07-15", "2026-07-15", L, False) == [] and mahnwesen.zins_abschnitte(0, "2026-01-01", "2026-07-15", L, False) == [])
e0 = A("GET", "einstellungen"); rw = e0.get("_rechtswerte") or {}
ok("Einstellungen liefern die Liste, den heutigen Satz und keine offenen Halbjahre (Stand der Version)",
   rw.get("basiszinsen", [{}])[-1] == {"ab": L[-1][0], "satz": L[-1][1]} and rw.get("basiszins") == mahnwesen.basiszins_am(L, H) and (rw.get("basiszins_offen") == "" or H >= "2027-01-01"), {x: rw.get(x) for x in ("basiszins", "basiszins_offen")})
hj1 = mahnwesen.halbjahr(heute); t1 = date.fromisoformat(hj1); hj0 = mahnwesen.halbjahr(t1 - timedelta(days=1))
x = A("PUT", "einstellungen", {"mahnwesen": {**e0["mahnwesen"], "basiszinsen": [{"ab": hj0, "satz": 1.0}, {"ab": hj1, "satz": "2,00"}]}})
ok("eigene Sätze für zwei Halbjahre gespeichert (Zahlentext „2,00“ wird zur Zahl)", x["_s"] == 200 and x["mahnwesen"]["basiszinsen"] == [{"ab": hj0, "satz": 1.0}, {"ab": hj1, "satz": 2.0}]
   and x["_rechtswerte"]["basiszins"] == 2.0, x.get("fehler") or x.get("mahnwesen"))
x2 = A("PUT", "einstellungen", {"mahnwesen": {**e0["mahnwesen"], "basiszinsen": [{"ab": "2027-03-05", "satz": 1.5}]}})
ok("ein Stichtag, der kein 1. Januar oder 1. Juli ist, wird abgelehnt", x2["_s"] == 400 and "1. Januar" in (x2.get("fehler") or ""), x2)
x2 = A("PUT", "einstellungen", {"mahnwesen": {**e0["mahnwesen"], "basiszinsen": [{"ab": "2027-01-01", "satz": 55}]}})
ok("ein Satz von 55 % wird abgelehnt", x2["_s"] == 400 and "zwischen" in (x2.get("fehler") or ""), x2)
ok("nach den abgelehnten Versuchen stehen die beiden eigenen Sätze unverändert", A("GET", "einstellungen")["mahnwesen"]["basiszinsen"] == [{"ab": hj0, "satz": 1.0}, {"ab": hj1, "satz": 2.0}])
# Rechnung, fällig 46 Tage vor dem Halbjahreswechsel, Mahnung heute
a1, p1 = auftrag("Sideboard Eiche", 1000)
rdat = (t1 - timedelta(days=60)).isoformat()
r1 = A("POST", f"auftraege/{a1['id']}/belege", {"art": "rechnung", "datum": rdat, "leistungsdatum": rdat}); f1 = fest(r1["id"])
ok("Rechnung mit Datum 60 Tage vor dem Halbjahreswechsel festgeschrieben, fällig 46 Tage davor", f1.get("status") == "fest" and f1.get("faellig") == (t1 - timedelta(days=46)).isoformat(), f1.get("fehler") or (f1.get("status"), f1.get("faellig")))
op = [o for o in (A("GET", "offeneposten").get("liste") or A("GET", "offeneposten").get("posten") or []) if o.get("beleg_id") == r1["id"]]
if not op:
    con0 = sqlite3.connect(D + "/buero.db", timeout=30); con0.row_factory = sqlite3.Row
    op = [dict(r) for r in con0.execute("SELECT * FROM offene_posten WHERE beleg_id=?", (r1["id"],))]; con0.close()
op = op[0]; offen = op["offen"]
v = A("GET", f"offeneposten/{op['id']}/mahnung?zinsen=1")
tage2 = (heute - t1).days + 1
soll = [{"von": (t1 - timedelta(days=45)).isoformat(), "bis": (t1 - timedelta(days=1)).isoformat(), "tage": 45, "basis": 1.0, "satz": 6.0, "betrag": kfm(offen * 6.0 / 100 * 45 / 365)},
        {"von": hj1, "bis": H, "tage": tage2, "basis": 2.0, "satz": 7.0, "betrag": kfm(offen * 7.0 / 100 * tage2 / 365)}]
ok("Mahnvorschlag: zwei Zinsabschnitte mit 6 % (45 Tage) und 7 % (seit dem Halbjahreswechsel)", v.get("zinsabschnitte") == soll, v.get("zinsabschnitte"))
ok("Zinsen = Summe der Abschnitte, Zinstage = Tage seit Fälligkeit, Gesamtbetrag stimmt",
   v.get("zinsen") == kfm(soll[0]["betrag"] + soll[1]["betrag"]) and v.get("zinstage") == 45 + tage2 and abs(v.get("gesamt") - (offen + v["zinsen"] + v.get("gebuehr", 0))) < 0.006, {x: v.get(x) for x in ("zinsen", "zinstage", "gesamt", "gebuehr", "offen")})
m1 = A("POST", f"offeneposten/{op['id']}/mahnung", {"stufe": v["stufe"], "zinsen": True, "gebuehr": 0, "betreff": v["betreff"], "text": v["text"], "schluss": v["schluss"]})
mid = m1.get("id") or (m1.get("mahnung") or {}).get("id")
s, druck, _ = rq(inh, "GET", f"/druck/mahnung/{mid}")
dt = re.sub(r"<[^>]+>", " ", druck); dt = re.sub(r"\s+", " ", dt)
ok("gedruckte Mahnung weist beide Zeiträume mit Tagen, Satz und Betrag aus",
   s == 200 and f"{ded(soll[0]['von'])} bis {ded(soll[0]['bis'])}: 45 Tage zu 6,00 % p. a. = {de(soll[0]['betrag'])} €" in dt
   and f"{ded(hj1)} bis {ded(H)}: {tage2} Tage zu 7,00 % p. a. = {de(soll[1]['betrag'])} €" in dt and f"{de(v['zinsen'])} €" in dt, dt[dt.find("Verzugszinsen") - 50:dt.find("Verzugszinsen") + 400])
con = sqlite3.connect(D + "/buero.db", timeout=30); con.row_factory = sqlite3.Row
mz = con.execute("SELECT zinsen, zinstage, zinssatz, daten FROM mahnungen WHERE id=?", (mid,)).fetchone()
ok("in der Mahnung festgehalten: Summe, Tage, letzter Satz und die Abschnitte", mz and mz["zinsen"] == v["zinsen"] and mz["zinstage"] == 45 + tage2 and mz["zinssatz"] == 7.0 and json.loads(mz["daten"]).get("zinsabschnitte") == soll, dict(mz) if mz else None)
# frühere Form der Einstellung (ein einzelner Satz) wird überführt
x = A("PUT", "einstellungen", {"mahnwesen": {"basiszins": 3.33, "stufen": e0["mahnwesen"]["stufen"]}})
gesp = json.loads(con.execute("SELECT wert FROM einstellungen WHERE schluessel='mahnwesen'").fetchone()[0])
ok("frühere Form {basiszins: 3,33}: wird als eigener Satz ab dem laufenden Halbjahr abgelegt, das alte Feld verschwindet",
   x["_s"] == 200 and "basiszins" not in gesp and gesp.get("basiszinsen") == [{"ab": hj1, "satz": 3.33}] and x["_rechtswerte"]["basiszins"] == 3.33, gesp.get("basiszinsen"))
A("PUT", "einstellungen", {"mahnwesen": {**e0["mahnwesen"], "basiszinsen": []}})
ok("eigene Sätze entfernt: es gilt wieder der hinterlegte Satz", A("GET", "einstellungen")["_rechtswerte"]["basiszins"] == mahnwesen.basiszins_am(L, H))
hw = lambda e, z, l, tag: [h["art"] for h in rechtswerte.hinweise(e, z, l, tag)]
ok("Erinnerung: am 02.01.2027 fehlt der Satz für das neue Halbjahr (nur wenn Verzugszinsen benutzt werden)",
   hw({}, True, False, date(2027, 1, 2)) == ["basiszins"] and hw({}, False, False, date(2027, 1, 2)) == [] and hw({}, True, False, date(2026, 12, 30)) == [])
ok("Erinnerung verschwindet mit dem Eintrag; bei mehreren fehlenden Halbjahren nennt sie das erste",
   hw({"mahnwesen": {"basiszinsen": [{"ab": "2027-01-01", "satz": 1.52}]}}, True, False, date(2027, 1, 2)) == []
   and "3 Halbjahre seit dem 01.01.2027" in rechtswerte.hinweise({}, True, False, date(2028, 1, 5))[0]["text"])

print("== Z12: Mindestlohn mit Stichtag")
ok("hinterlegt: 13,90 € in 2026, 14,60 € ab 2027; Minijob-Grenze 603 € und 633 €",
   (personal.mindestlohn("2026-06-01"), personal.mindestlohn("2027-01-01"), personal.minijob_grenze("2026-06-01"), personal.minijob_grenze("2027-03-01")) == (13.90, 14.60, 603, 633))
eig = [{"ab": "2028-01-01", "satz": 15.20}]
ok("eigener Eintrag ab 2028: 15,20 € und Minijob-Grenze 659 €; davor unverändert", (personal.mindestlohn("2028-02-01", eig), personal.minijob_grenze("2028-02-01", eig), personal.mindestlohn("2027-12-31", eig)) == (15.20, 659, 14.60))
ma = A("POST", "mitarbeiter", {"vorname": "Max", "nachname": "Werk", "lohnart": "stunde", "stundenlohn": 14.00, "eintritt": "2024-01-01"}); mid_ = ma.get("id") or (ma.get("mitarbeiter") or {}).get("id")
hin = lambda monat: " | ".join(h for z in A("GET", f"lohn?monat={monat}").get("zeilen", []) for h in z.get("hinweise", []))
ok("Lohnübersicht: 14,00 € liegen 2026 über dem Mindestlohn, ab Januar 2027 darunter (14,60 €)", "Mindestlohn" not in hin("2026-12") and "Mindestlohn von 14,60 €" in hin("2027-01"), (hin("2026-12"), hin("2027-01")))
x = A("PUT", "einstellungen", {"mindestlohn": [{"ab": "2026-12-01", "satz": "15,00"}]})
ok("eigener Mindestlohn ab 01.12.2026 gespeichert und in der Liste der Oberfläche (mit Minijob-Grenze 650 €)",
   x["_s"] == 200 and x["mindestlohn"] == [{"ab": "2026-12-01", "satz": 15.0}] and {"ab": "2026-12-01", "satz": 15.0, "minijob": 650} in x["_rechtswerte"]["mindestlohn"], x.get("fehler") or x.get("mindestlohn"))
ok("die Lohnübersicht für Dezember 2026 rechnet jetzt mit 15,00 €", "Mindestlohn von 15,00 €" in hin("2026-12"), hin("2026-12"))
x2 = A("PUT", "einstellungen", {"mindestlohn": [{"ab": "2028-01-01", "satz": 2}]})
ok("ein Mindestlohn von 2 € wird abgelehnt", x2["_s"] == 400 and "zwischen 5 und 100" in (x2.get("fehler") or ""), x2)
A("PUT", "einstellungen", {"mindestlohn": []})
ok("Erinnerung im Januar 2028: kein Mindestlohn für das Jahr eingetragen (nur mit Mitarbeitern, die Lohn bekommen)",
   hw({}, False, True, date(2028, 1, 5)) == ["mindestlohn"] and hw({}, False, False, date(2028, 1, 5)) == [] and hw({}, False, True, date(2027, 6, 1)) == []
   and hw({"mindestlohn": [{"ab": "2028-01-01", "satz": 14.6}]}, False, True, date(2028, 1, 5)) == [])

print("== Z12: Umsatzsteuersätze mit Stichtag")
sa = rechtswerte.steuersatz_am
ok("hinterlegt: 19 und 7 %, im zweiten Halbjahr 2020 16 und 5 %", (sa(None, 19, H), sa(None, 7, H), sa(None, 19, "2020-08-01"), sa(None, 7, "2020-12-31"), sa(None, 19, "2021-01-01"), sa(None, 19, "2019-05-05")) == (19, 7, 16, 5, 19, 19))
ok("0 % und Sondersätze bleiben, wie sie sind", (sa(None, 0, H), sa(None, 13, H), sa([{"ab": "2028-01-01", "regel": 20, "ermaessigt": 7}], 0, "2028-02-01")) == (0, 13, 0))
ok("eigener Satz ab 2028: 19 % wird ab dem Stichtag zu 20 %, davor nicht", (sa([{"ab": "2028-01-01", "regel": 20, "ermaessigt": 7}], 19, "2028-02-01"), sa([{"ab": "2028-01-01", "regel": 20, "ermaessigt": 7}], 19, "2027-12-31")) == (20, 19))
stich = (heute - timedelta(days=5)).isoformat()
x = A("PUT", "einstellungen", {"steuersaetze": [{"ab": stich, "regel": 20, "ermaessigt": 7}]})
ok("eigener Regelsatz 20 % ab vor fünf Tagen gespeichert", x["_s"] == 200 and x["steuersaetze"] == [{"ab": stich, "regel": 20.0, "ermaessigt": 7.0}] and x["_rechtswerte"]["steuersaetze"][-1]["regel"] == 20.0, x.get("fehler") or x.get("steuersaetze"))
a2, p2 = auftrag("Regal Buche", 1000)
neuer_beleg = lambda aid, d: A("GET", f"belege/{A('POST', f'auftraege/{aid}/belege', d).get('id')}")   # Anlegen liefert nur die Nummer des Belegs
ang = neuer_beleg(a2["id"], {"art": "angebot"})
ok("neues Angebot von heute rechnet mit 20 %", ang.get("ust_satz") == 20 and abs(ang.get("brutto") - 1200) < 0.005, (ang.get("ust_satz"), ang.get("brutto")))
alt = (heute - timedelta(days=10)).isoformat()
ang2 = neuer_beleg(a2["id"], {"art": "angebot", "datum": alt})
ok("Angebot mit Belegdatum vor dem Stichtag rechnet mit 19 %", ang2.get("ust_satz") == 19 and abs(ang2.get("brutto") - 1190) < 0.005, (ang2.get("ust_satz"), ang2.get("brutto")))
re2 = neuer_beleg(a2["id"], {"art": "rechnung"})
ok("Rechnungsentwurf von heute (Leistung heute): 20 %", re2.get("ust_satz") == 20 and abs(re2.get("brutto") - 1200) < 0.005, (re2.get("ust_satz"), re2.get("brutto"), re2.get("leistungsdatum")))
A("PUT", f"belege/{re2['id']}", {"leistungsdatum": alt})
f409 = A("POST", f"belege/{re2['id']}/festschreiben", {})
ok("Leistungsdatum vor den Stichtag gelegt: Festschreiben fragt nach (Entwurf 20 %, am Leistungstag gelten 19 %)",
   f409["_s"] == 409 and f409.get("rueckfrage") == "steuersatz" and "20,00 %" in f409.get("fehler", "") and "19,00 %" in f409.get("fehler", "") and "19,00 %" in f409.get("knopf", ""), f409)
ok("ohne Bestätigung bleibt die Rechnung Entwurf mit 20 %", (lambda b: b.get("status") == "entwurf" and b.get("ust_satz") == 20)(A("GET", f"belege/{re2['id']}")))
f2 = fest(re2["id"], "steuersatz,rechnungsdatum,position_null")
ok("nach Bestätigung festgeschrieben mit 19 %: 1.000,00 netto, 190,00 USt, 1.190,00 brutto", f2.get("status") == "fest" and f2.get("ust_satz") == 19 and abs(f2.get("brutto") - 1190) < 0.005 and abs(f2.get("ust") - 190) < 0.005, {x: f2.get(x) for x in ("status", "ust_satz", "ust", "brutto", "fehler")})
x2 = A("PUT", "einstellungen", {"steuersaetze": [{"ab": "2029-01-01", "regel": 5, "ermaessigt": 7}]})
ok("ermäßigter Satz über dem Regelsatz wird abgelehnt", x2["_s"] == 400 and "Regelsatz" in (x2.get("fehler") or ""), x2)
A("PUT", "einstellungen", {"steuersaetze": []})
ang3 = neuer_beleg(a2["id"], {"art": "angebot"})
ok("eigenen Satz entfernt: neue Belege rechnen wieder mit 19 %; die festgeschriebene Rechnung bleibt unverändert",
   ang3.get("ust_satz") == 19 and A("GET", f"belege/{re2['id']}").get("brutto") == f2.get("brutto"), ang3.get("ust_satz"))

pt = [r[0] for r in con.execute("SELECT text FROM protokoll WHERE art='einstellung' ORDER BY nr")]
ok("Protokoll nennt bei den Umsatzsteuersätzen Stichtag und Sätze, vorher und nachher",
   any(f"Umsatzsteuersätze: keine eigenen Einträge → ab {ded(stich)} 20,00/7,00 %" in x for x in pt) and any(f"Umsatzsteuersätze: ab {ded(stich)} 20,00/7,00 % → keine eigenen Einträge" in x for x in pt), [x for x in pt if "teuers" in x][-3:])
ok("ebenso bei Basiszinssätzen und Mindestlohn (mit den eingetragenen Werten)",
   any("Basiszinssätze: " in x and " %" in x and "→" in x for x in pt) and any("Mindestlohn: " in x and "15,00" in x for x in pt), [x for x in pt if "asiszins" in x or "indestlohn" in x][-4:])

print("== F7: Datumsfelder")
lf = A("POST", "lieferanten", {"kurzname": "Holzhandel", "firma": "Holzhandel KG"})
unsinn = ["2026-02-30", "0026-11-19", "abc", "19.11.2026", "2026-13-01", "99999-01-01", "2026-11-19x"]
zaehl = lambda: {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("briefe", "stunden", "bautagebuch", "zahlungen", "zeiten", "termine", "abwesenheiten", "wiedervorlagen")}
vorher = zaehl()
stellen = {
    "Brief": lambda w: A("POST", "briefe", {"kunde_id": k["id"], "betreff": "Test", "text": "x", "datum": w}),
    "Stunden": lambda w: A("POST", "stunden", {"auftrag_id": a2["id"], "datum": w, "stunden": 1, "taetigkeit": "Test"}),
    "Bautagebuch": lambda w: A("POST", "bautagebuch", {"auftrag_id": a2["id"], "datum": w}),
    "Belegentwurf (Belegdatum)": lambda w: A("PUT", f"belege/{ang3['id']}", {"datum": w}),
    "Belegentwurf (Leistungsdatum)": lambda w: A("PUT", f"belege/{ang3['id']}", {"leistungsdatum": w}),
    "Eingangsrechnung (Belegdatum)": lambda w: A("POST", "zahlungen", {"lieferant_id": lf["id"], "belegnr": "X1", "betrag": 10, "belegdatum": w}),
    "Eingangsrechnung (Fälligkeit, Skonto bis)": lambda w: A("POST", "zahlungen", {"lieferant_id": lf["id"], "belegnr": "X2", "betrag": 10, "belegdatum": H, "faellig": H, "skonto": 2, "skonto_bis": w}),
    "Kunde (Geburtstag)": lambda w: A("PUT", f"kunden/{k['id']}", {"geburtstag": w}),
    "Kunde (Aufbewahren bis)": lambda w: A("PUT", f"kunden/{k['id']}", {"aufbewahren_bis": w}),
    "Mitarbeiter (Eintritt)": lambda w: A("PUT", f"mitarbeiter/{mid_}", {"eintritt": w}),
    "Zeitbuchung": lambda w: A("POST", "zeiten", {"mitarbeiter_id": mid_, "datum": w, "beginn": "08:00", "ende": "09:00"}),
    "Termin": lambda w: A("POST", "termine", {"auftrag_id": a2["id"], "typ": "Montage", "titel": "T", "von": w, "bis": w}),
    "Abwesenheit": lambda w: A("POST", "abwesenheiten", {"mitarbeiter_id": mid_, "art": "urlaub", "von": w, "bis": w}),
    "Wiedervorlage": lambda w: A("POST", "wiedervorlagen", {"kunde_id": k["id"], "text": "T", "datum": w}),
}
for name, tun in stellen.items():
    erg = [(w, r["_s"], (r.get("fehler") or "")[:70]) for w in unsinn for r in [tun(w)]]
    ok(f"{name}: alle sieben unmöglichen Datumsangaben abgelehnt (400 mit Meldung)", all(s == 400 and f for _, s, f in erg), [x for x in erg if x[1] != 400 or not x[2]])
ok("dabei ist nichts entstanden: Zahl der Briefe, Stunden, Bautagebuch-Einträge, Zahlungen, Zeiten, Termine, Abwesenheiten, Wiedervorlagen unverändert", zaehl() == vorher, (vorher, zaehl()))
kd = con.execute("SELECT geburtstag, aufbewahren_bis FROM kunden WHERE id=?", (k["id"],)).fetchone(); me = con.execute("SELECT eintritt FROM mitarbeiter WHERE id=?", (mid_,)).fetchone()
ok("Kunde und Mitarbeiter unverändert", (kd["geburtstag"] or "", kd["aufbewahren_bis"] or "", me["eintritt"]) == ("", "", "2024-01-01"), (dict(kd), dict(me)))
gut = {n: stellen[n](H)["_s"] for n in ("Brief", "Stunden", "Bautagebuch", "Belegentwurf (Belegdatum)", "Eingangsrechnung (Belegdatum)", "Kunde (Aufbewahren bis)", "Zeitbuchung", "Wiedervorlage")}
ok("mit einem gültigen Datum nehmen dieselben Stellen die Eingabe an", set(gut.values()) == {200}, gut)
x = A("PUT", f"kunden/{k['id']}", {"geburtstag": "1961-03-04"})
ok("Geburtstag 04.03.1961 wird angenommen; die Meldung bei einem Fehler nennt das Feld", x["_s"] == 200 and "Geburtstag" in (A("PUT", f"kunden/{k['id']}", {"geburtstag": "1961-02-30"}).get("fehler") or ""), x.get("fehler"))

print("== E4/E5: Einstellungen nach Art und Wertebereich")
for schl, wert, teil in (("angebot_gueltig_tage", -30, "zwischen 0 und 365"), ("angebot_gueltig_tage", 366, "zwischen 0 und 365"), ("nachfass_tage", -1, "zwischen 0 und 365"),
                         ("kundennr_start", 0, "zwischen 1 und"), ("tagesstunden", 30, "zwischen 0 und 24"), ("https", "xyz", "Auswahl"), ("lohnanteil", "immer", "Auswahl"),
                         ("zahlungsplan_rest", 2.5, "ganze Zahl"), ("netzwerk", "ja", "Schalter"), ("firma", ["a"], "Text"), ("kundengruppen", "Privat", "Liste"),
                         ("kalk_vorgaben", "abc", "nicht lesbar"), ("kalk_vorgaben", {"kostenstellen": "x"}, "Liste"), ("kalk_vorgaben", {"loehne": [{"gruppe": "A", "lohn": "viel"}]}, "keine Zahl"),
                         ("mahnwesen", {"stufen": [{"tage": "abc"}]}, "keine Zahl"), ("mahnwesen", [1, 2], "nicht lesbar"), ("leitstand_schritte", "abc", "Liste"),
                         ("feiertage_wahl", {"neujahr": "ja"}, "Schalter"), ("termin_typen", [{"name": "A", "farbe": "red;background:url(x)"}], "Farbe"),
                         ("brief_layout", {"oben": 9999}, "Millimeter"), ("datev", "x", "nicht lesbar")):
    r = A("PUT", "einstellungen", {schl: wert})
    ok(f"{schl} = {json.dumps(wert, ensure_ascii=False)[:40]}: abgelehnt mit Meldung („{teil}“)", r["_s"] == 400 and teil in (r.get("fehler") or ""), (r["_s"], r.get("fehler")))
x = A("PUT", "einstellungen", {"angebot_gueltig_tage": "14", "tagesstunden": "7,5", "nachfass_tage": 0})
ok("Zahlentexte werden zu Zahlen: Angebot gültig 14 Tage, 7,5 Stunden je Tag; 0 Tage Nachfassen ist erlaubt", x["_s"] == 200 and x["angebot_gueltig_tage"] == 14 and x["tagesstunden"] == 7.5 and x["nachfass_tage"] == 0, {s: x.get(s) for s in ("angebot_gueltig_tage", "tagesstunden", "fehler")})
x = A("PUT", "einstellungen", {"firma": "Muster Schreinerei", "angebot_gueltig_tage": -30})
ok("ein abgelehnter Wert verhindert das Speichern der ganzen Anfrage (nichts wird halb gespeichert)", x["_s"] == 400 and A("GET", "einstellungen")["angebot_gueltig_tage"] == 14)
# Rundlauf: Was das Programm ausliefert, nimmt es auch wieder an
stand = A("GET", "einstellungen"); schluessel = [s for s in stand if not s.startswith("_")]
rund = A("PUT", "einstellungen", {s: stand[s] for s in schluessel})
ok(f"Rundlauf: alle {len(schluessel)} Einstellungen so zurückgeschrieben, wie das Programm sie liefert, wird angenommen", rund["_s"] == 200, rund.get("fehler"))
nach = A("GET", "einstellungen")
ok("und ändert nichts", {s: nach[s] for s in schluessel} == {s: stand[s] for s in schluessel}, [s for s in schluessel if nach.get(s) != stand.get(s)])
z0 = nach.get("zaehler") or {}
zx = A("PUT", "einstellungen", {"zaehler": {"rechnung": {str(heute.year): 0}, "kunde": {"_": 1}}})
ok("Zählerstände der Nummernkreise lassen sich über das Speichern der Einstellungen nicht verändern (eigener Weg, dort nur erhöhen)",
   zx["_s"] == 200 and bool((z0.get("rechnung") or {}).get(str(heute.year))) and A("GET", "einstellungen").get("zaehler") == z0, (z0, zx.get("zaehler")))
# Unsinn in jede Einstellung: angenommen oder mit Meldung abgelehnt, nie ein interner Fehler
unsinn_e = ["abc", -30, 10 ** 15, [], {}, [1, {"x": [1]}], {"a": {"b": {"c": [None]}}}, None, True, 0.5, "<script>alert(1)</script>", [[["tief"]]]]
st = {200: 0, 400: 0}; schlimm = []
aus = {"update", "mail", "projektpfad", "sicherung_ziel", "netzwerk", "https", "netz_adressen"}   # wirken über das Speichern hinaus (Netz, Ordner, Sicherung): eigene Prüfungen
for s_ in schluessel:
    if s_ in aus:
        continue
    for w in unsinn_e:
        r = A("PUT", "einstellungen", {s_: w})
        if r["_s"] in st: st[r["_s"]] += 1
        if r["_s"] not in (200, 400) or (r["_s"] == 400 and not r.get("fehler")): schlimm.append((s_, w, r["_s"], str(r.get("fehler"))[:80]))
ok(f"{st[200] + st[400] + len(schlimm)} unsinnige Werte in {len(schluessel) - len(aus)} Einstellungen: {st[400]} abgelehnt, {st[200]} angenommen, kein interner Fehler", not schlimm, schlimm[:8])
seiten = ["einstellungen", "start", f"auftraege/{a2['id']}", f"auftraege/{a2['id']}/kalk", f"auftraege/{a2['id']}/positionen", f"positionen/{p2}", "auftraege?status=", "kunden?status=alle",
          "offeneposten", "mahnwesen", "bank?status=offen", "leitstand", f"kalender?von={H}&bis={H}", "mitarbeiter?status=aktiv", f"lohn?monat={H[:7]}", "material?kategorie=holzwerkstoffe",
          "belege", "zahlungen", "lieferanten", "service/datev", f"belege/{ang3['id']}", "wiedervorlagen", "termine", "briefe"]
def seiten_pruefen():
    aus_ = {p: A("GET", p)["_s"] for p in seiten}
    s, t, _ = rq(inh, "GET", f"/druck/{ang3['id']}"); aus_["Druckansicht Angebot"] = s
    return {p: s for p, s in aus_.items() if s != 200}
ok("danach laden alle Seiten (Start, Auftrag mit Kalkulation, Mahnwesen, Kontoauszüge, Leitstand, Kalender, Personal, Lohn, Material, Druckansicht)", seiten_pruefen() == {}, seiten_pruefen())
rund = A("PUT", "einstellungen", {s: stand[s] for s in schluessel})
ok("der vorherige Stand lässt sich vollständig zurückschreiben", rund["_s"] == 200 and {s: A("GET", "einstellungen")[s] for s in schluessel} == {s: stand[s] for s in schluessel}, rund.get("fehler"))
# Unbrauchbares aus früherer Zeit in der Datenbank: Vorgabe gilt, keine Seite fällt aus
for s_, w in (("kalk_vorgaben", '"abc"'), ("mahnwesen", "[1, 2]"), ("leitstand_schritte", "5"), ("zahlungskonten", '"x"'), ("tagesstunden", '"7,5"'), ("kundengruppen", "{}"), ("status_ende", "null"), ("termin_typen", '"x"')):
    con.execute("INSERT OR REPLACE INTO einstellungen VALUES (?, ?)", (s_, w))
con.commit()
e_alt = A("GET", "einstellungen")
ok("unbrauchbare Werte in der Datenbank (Text statt Liste, Liste statt Gruppe): die Vorgabe gilt, ein Zahlentext wird als Zahl gelesen",
   e_alt["_s"] == 200 and isinstance(e_alt["kalk_vorgaben"], dict) and isinstance(e_alt["leitstand_schritte"], list) and len(e_alt["leitstand_schritte"]) > 3 and e_alt["tagesstunden"] == 7.5
   and isinstance(e_alt["kundengruppen"], list) and isinstance(e_alt["mahnwesen"].get("stufen"), list) and len(e_alt["mahnwesen"]["stufen"]) == 3, {s: e_alt.get(s) for s in ("kalk_vorgaben", "leitstand_schritte", "tagesstunden", "kundengruppen")})
ok("und alle Seiten laden weiter", seiten_pruefen() == {}, seiten_pruefen())
con.execute("DELETE FROM einstellungen WHERE schluessel IN ('kalk_vorgaben','mahnwesen','leitstand_schritte','zahlungskonten','tagesstunden','kundengruppen','status_ende','termin_typen')"); con.commit()

print("== F6: gleichzeitiges Bearbeiten")
bu = A("POST", "benutzer", {"name": "Bea Büro", "login": "buero", "rolle": "buero", "passwort": "Pruefung#2026", "passwort2": "Pruefung#2026"})
zwei = cl(); s2 = rq(zwei, "POST", "/api/anmeldung/anmelden", {"login": "buero", "passwort": "Pruefung#2026"})[0]
ok("zweite Anmeldung (Büro) angelegt", bu["_s"] == 200 and s2 == 200, (bu, s2))
g1 = A("GET", f"kunden/{k['id']}"); stand1 = g1["_kopf"].get("X-Zeit") or g1["_kopf"].get("x-zeit")
g2 = A("GET", f"kunden/{k['id']}", c=zwei); stand2 = g2["_kopf"].get("X-Zeit") or g2["_kopf"].get("x-zeit")
ok("beim Öffnen bekommt jede Sitzung den Stand des Datensatzes", bool(stand1) and bool(stand2), (stand1, stand2))
time.sleep(0.05)
w1 = A("PUT", f"kunden/{k['id']}", {"ort": "Meckenbeuren"}, {"X-Stand": stand1})
ok("erste Sitzung speichert", w1["_s"] == 200, w1.get("fehler"))
w2 = A("PUT", f"kunden/{k['id']}", {"strasse": "Seeweg"}, {"X-Stand": stand2}, c=zwei)
ok("zweite Sitzung mit dem älteren Stand: Rückfrage statt stillem Überschreiben, nennt den anderen Benutzer",
   w2["_s"] == 409 and w2.get("rueckfrage") == "stand" and "Jonas" in (w2.get("fehler") or ""), w2)
ok("gespeichert ist bis dahin nur die erste Änderung", (lambda r: (r["ort"], r["strasse"]) == ("Meckenbeuren", "Gartenweg"))(con.execute("SELECT ort, strasse FROM kunden WHERE id=?", (k["id"],)).fetchone()))
w3 = A("PUT", f"kunden/{k['id']}", {"strasse": "Seeweg"}, {"X-Stand": stand2, "X-Bestaetigt": "stand"}, c=zwei)
ok("nach Bestätigung wird gespeichert", w3["_s"] == 200 and con.execute("SELECT strasse FROM kunden WHERE id=?", (k["id"],)).fetchone()[0] == "Seeweg", w3.get("fehler"))
neu1 = w1["_kopf"].get("X-Zeit") or w1["_kopf"].get("x-zeit")
w4 = A("PUT", f"kunden/{k['id']}", {"ort": "Tettnang"}, {"X-Stand": (A("GET", f"kunden/{k['id']}")["_kopf"].get("X-Zeit") or "")})
ok("wer den Datensatz danach neu geöffnet hat, speichert ohne Rückfrage; die eigene zweite Änderung ebenso", w4["_s"] == 200 and A("PUT", f"kunden/{k['id']}", {"ort": "Tettnang"}, {"X-Stand": w4["_kopf"].get("X-Zeit") or w4["_kopf"].get("x-zeit")})["_s"] == 200, w4.get("fehler"))

print("== P7: Startseite mit gemerkten Auftragswerten")
a3, p3 = auftrag("Küche Ahorn", 5000, "Auftrag")
lauf = lambda: {x["id"]: x for x in A("GET", "start").get("laufend", []) or A("GET", "start").get("auftraege", {}).get("laufend", [])}
st1 = A("GET", "start")
def wert_von(st, aid):
    for gruppe in ("laufend", "angebote", "anfragen"):
        for x in st.get(gruppe) or (st.get("auftraege") or {}).get(gruppe) or []:
            if x.get("id") == aid: return x.get("netto"), x.get("soll_stunden"), gruppe
    return None
w_a = wert_von(st1, a3["id"])
ok("laufender Auftrag steht mit 5.000,00 € auf der Startseite", w_a is not None and w_a[0] == 5000 and w_a[2] == "laufend", (w_a, sorted(st1.keys())[:30]))
t0 = time.time(); st2 = A("GET", "start"); t_zwei = time.time() - t0
ok("zweiter Aufruf liefert dasselbe", wert_von(st2, a3["id"]) == w_a and st2.get("auftragsbestand") == st1.get("auftragsbestand"))
A("PUT", f"positionen/{p3}", {"einzelpreis": 6500, "preis_manuell": 1})
ok("Preis der Position geändert: die Startseite zeigt sofort 6.500,00 €", (wert_von(A("GET", "start"), a3["id"]) or [None])[0] == 6500, wert_von(A("GET", "start"), a3["id"]))
po4 = A("POST", f"auftraege/{a3['id']}/positionen", {"text": "Arbeitsplatte"}); p4 = po4.get("id") or po4["position"]["id"]
A("PUT", f"positionen/{p4}", {"einzelpreis": 800, "preis_manuell": 1, "menge": 2})
ok("zweite Position (2 × 800 €) dazu: 8.100,00 €", (wert_von(A("GET", "start"), a3["id"]) or [None])[0] == 8100, wert_von(A("GET", "start"), a3["id"]))
A("PUT", f"positionen/{p4}", {"alternativ": 1})
ok("Position als Alternative gekennzeichnet: wieder 6.500,00 €", (wert_von(A("GET", "start"), a3["id"]) or [None])[0] == 6500, wert_von(A("GET", "start"), a3["id"]))
A("DELETE", f"positionen/{p4}")
ok("Position gelöscht: 6.500,00 €", (wert_von(A("GET", "start"), a3["id"]) or [None])[0] == 6500)
kalk_api = A("GET", f"auftraege/{a3['id']}/positionen")
netto_direkt = kalk_api.get("netto") if isinstance(kalk_api.get("netto"), (int, float)) else None
ok("der Wert der Startseite stimmt mit der Kalkulation des Auftrags überein", netto_direkt is None or netto_direkt == 6500, netto_direkt)

print("== P8: große Preisliste (Anlegen, Abgleich, Übernehmen)")
import base64 as b64
NP = 4000
pl = lambda plus: b64.b64encode(("Artikelnummer;Bezeichnung;Einheit;Preis;EAN\n" + "\n".join(f"G{i:05d};Großartikel {i};Stk.;{plus + i % 50},{i % 100:02d};{4100000000000 + i}" for i in range(NP))).encode("utf-8")).decode()
gl = A("POST", "lieferanten", {"kurzname": "Großhandel", "firma": "Großhandel KG"})
g1 = A("POST", "preisimport/lesen", {"daten": pl(1), "dateiname": "gross.csv", "lieferant_id": gl["id"]})
ok(f"Preisliste mit {NP} Zeilen gelesen: alle neu", g1["_s"] == 200 and g1.get("neu_gesamt") == NP, {k: g1.get(k) for k in ("_s", "neu_gesamt", "fehler")})
nr_vor = [r[0] for r in con.execute("SELECT nummer FROM material WHERE kategorie='beschlaege'")]
t0 = time.time(); zeiten_an = []
for i in range(0, NP, 2000):
    t1 = time.time(); ga = A("POST", "preisimport/anlegen", {"schluessel": g1["schluessel"], "auswahl": [f"G{k:05d}" for k in range(i, i + 2000)], "kategorie": "beschlaege", "lieferant_id": gl["id"], "dateiname": "gross.csv"})
    zeiten_an.append(time.time() - t1)
nr_nach = [r[0] for r in con.execute("SELECT nummer FROM material WHERE kategorie='beschlaege' ORDER BY id")]
neu_nr = nr_nach[len(nr_vor):]
ok(f"{NP} Materialien in zwei Paketen angelegt ({zeiten_an[0]:.1f} s und {zeiten_an[1]:.1f} s, jeweils unter 15 s); das zweite Paket ist nicht langsamer als das Dreifache des ersten",
   len(neu_nr) == NP and max(zeiten_an) < 15 and zeiten_an[1] < max(1.0, zeiten_an[0] * 3), (len(neu_nr), zeiten_an))
zahl = lambda n: int(re.sub(r"\D", "", n) or 0)
ok("die Nummern sind fortlaufend und eindeutig vergeben (keine doppelt, keine Lücke)", len(set(nr_nach)) == len(nr_nach) and [zahl(x) for x in neu_nr] == list(range(zahl(neu_nr[0]), zahl(neu_nr[0]) + NP)), neu_nr[:3] + neu_nr[-2:])
ok("ein danach von Hand angelegtes Material bekommt die nächste Nummer", zahl(A("POST", "material", {"kategorie": "beschlaege", "bezeichnung": "Handanlage"}).get("nummer", "")) == zahl(neu_nr[-1]) + 1)
m_auf = con.execute("SELECT id, ek_preis FROM material WHERE bestellnr='G00007'").fetchone()
A("PUT", f"material/{m_auf['id']}", {"aufschlag": 50})
t1 = time.time(); g2 = A("POST", "preisimport/lesen", {"daten": pl(2), "dateiname": "gross2.csv", "lieferant_id": gl["id"]}); dauer = time.time() - t1
ok(f"Abgleich der Preisliste gegen den Stamm in {dauer:.1f} s (unter 10 s): {NP} Treffer", g2["_s"] == 200 and len(g2.get("treffer") or []) == NP and dauer < 10, (g2["_s"], len(g2.get("treffer") or []), dauer))
posten = [{"material_id": x["material_id"], "neu": x["neu"]} for x in g2["treffer"]]
t1 = time.time(); gu = A("POST", "preisimport/uebernehmen", {"posten": posten, "dateiname": "gross2.csv", "lieferant_id": gl["id"]}); dauer = time.time() - t1
ok(f"{NP} Preise in {dauer:.1f} s übernommen (unter 10 s)", gu["_s"] == 200 and gu.get("geaendert") == NP and dauer < 10, (gu.get("geaendert"), dauer, gu.get("fehler")))
soll = {f"G{i:05d}": round(2 + i % 50 + (i % 100) / 100, 4) for i in range(NP)}
ist = {r[0]: r[1] for r in con.execute("SELECT bestellnr, ek_preis FROM material WHERE bestellnr LIKE 'G0%'")}
ok("jeder Einkaufspreis steht so im Stamm wie in der Datei, mit dem Preisdatum von heute", ist == soll and con.execute("SELECT COUNT(*) FROM material WHERE bestellnr LIKE 'G0%' AND preis_vom=?", (H,)).fetchone()[0] == NP,
   [(k, ist.get(k), soll[k]) for k in soll if ist.get(k) != soll[k]][:5])
m_neu = con.execute("SELECT ek_preis, vk_preis, aufschlag FROM material WHERE id=?", (m_auf["id"],)).fetchone()
ok("der Verkaufspreis folgt beim Material mit 50 % Aufschlag dem neuen Einkaufspreis", abs(m_neu["vk_preis"] - kfm(m_neu["ek_preis"] * 1.5)) < 0.005 and m_neu["aufschlag"] == 50, dict(m_neu))
gu2 = A("POST", "preisimport/uebernehmen", {"posten": posten + [{"material_id": 99999999, "neu": 5}], "dateiname": "gross2.csv", "lieferant_id": gl["id"]})
ok("unbekanntes Material in der Auswahl: Meldung statt stiller Auslassung", gu2["_s"] == 404 and "nicht gefunden" in gu2.get("fehler", ""), gu2)
ok("das Protokoll hält Anlegen und Preisübernahme fest", con.execute("SELECT COUNT(*) FROM protokoll WHERE art='preisimport'").fetchone()[0] >= 3)

print("== Z10: Start einer älteren Version auf neuerem Datenbestand")
z10 = T + "/v25/z10"; prog = z10 + "/eberle-buero"
shutil.rmtree(z10, ignore_errors=True)
shutil.copytree(I, prog, ignore=shutil.ignore_patterns("daten", "__pycache__", "*.exe", "*.zip"))
os.makedirs(prog + "/daten")
quelle = sqlite3.connect(D + "/buero.db", timeout=30); ziel = sqlite3.connect(prog + "/daten/buero.db"); quelle.backup(ziel); quelle.close()
ziel.execute("PRAGMA journal_mode=DELETE"); ziel.execute("INSERT OR REPLACE INTO einstellungen VALUES ('programm_version', '\"2099.01.01-1\"')"); ziel.commit(); ziel.close()
prufsumme = lambda: hashlib.sha256(open(prog + "/daten/buero.db", "rb").read()).hexdigest()
vor = prufsumme()
env = {**os.environ, "BUERO_PORT": "8793", "BUERO_FENSTER": "nein", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}; env.pop("BUERO_AELTERE_VERSION", None)
r = subprocess.run([sys.executable, "app.py", "--konsole", "--kein-browser"], cwd=prog, env=env, capture_output=True, timeout=120)
aus_text = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
ok("das Programm startet nicht (Rückgabewert 3) und sagt, warum: Bestand aus 2099.01.01-1, bitte die neuere Version installieren",
   r.returncode == 3 and "2099.01.01-1" in aus_text and "startet deshalb nicht" in aus_text and "nichts verändert" in aus_text, (r.returncode, aus_text[-500:]))
ok("die Datenbank ist Byte für Byte unverändert", prufsumme() == vor)
env2 = {**env, "BUERO_AELTERE_VERSION": "ja"}
with open(z10 + "/aus.txt", "wb") as aus_d:
    pz = subprocess.Popen([sys.executable, "app.py", "--konsole", "--kein-browser"], cwd=prog, env=env2, stdout=aus_d, stderr=subprocess.STDOUT)
    oben = False
    for _ in range(150):
        try:
            vz = json.loads(urllib.request.urlopen("http://127.0.0.1:8793/api/version", timeout=2).read().decode()); oben = True; break
        except Exception:  # noqa: BLE001
            if pz.poll() is not None: break
            time.sleep(0.4)
    pz.terminate()
    try: pz.wait(timeout=20)
    except subprocess.TimeoutExpired: pz.kill(); pz.wait(timeout=20)
ok("mit BUERO_AELTERE_VERSION=ja (für den Betreuer) startet es", oben, open(z10 + "/aus.txt", encoding="utf-8", errors="replace").read()[-400:])
time.sleep(0.5)
zc = sqlite3.connect(prog + "/daten/buero.db", timeout=30)
pv = [r[0] for r in zc.execute("SELECT text FROM protokoll WHERE art='version' ORDER BY nr DESC LIMIT 1")]; zc.close()
ok("der Wechsel der Version steht dann im Änderungsprotokoll", bool(pv) and "2099.01.01-1" in pv[0], pv)
con.close()
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
