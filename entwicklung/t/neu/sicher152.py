"""Version 152, Zugriff und Datenschutz: Betriebsunterlagen nur für den Inhaber (S10), Fehlversuche begrenzt und gleiche Antwortzeit (S11),
Formelzeichen in Exportdateien (S12), Verschlüsselungsfehler wird gemeldet (S13), Suche nach Rechten (M6), Preisfelder (M7), Belege ohne
Preisrecht (M8), Anonymisieren mit Fundstellen (D7), Datenauskunft (D8), Löschliste (P6). Erwartet eine frische Prüfinstanz."""
import json, sys, re, sqlite3, time, zipfile, io, os, base64, statistics
from datetime import date, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
sys.path.insert(0, "/home/claude/eberle-buero")
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:700]))
    if not bed: fehler.append(name)
H = date.today().isoformat()
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, h=None, c=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, {"X-Rueckfrage": "1", **(h or {})}); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
ident = lambda d: d.get("id") or (d.get("position") or {}).get("id")
A("PUT", "einstellungen", {"firma": "Muster", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890", "sepa_iban": "DE02120300000000202051", "firma_inhaber": "Jonas Muster"})
PW = "Pruefung#2026"
for lg, rolle, extra in (("buero", "buero", {}), ("werk", "werkstatt", {}), ("emat", "eigen", {"eigen": {"bereiche": {"material": 1}, "preise": False}}),
                         ("eauf", "eigen", {"eigen": {"bereiche": {"auftraege": 1}, "preise": False}}), ("elief", "eigen", {"eigen": {"bereiche": {"lieferanten": 1}}}),
                         ("ekun", "eigen", {"eigen": {"bereiche": {"kunden": 1}}})):
    r = A("POST", "benutzer", {"name": lg.capitalize(), "login": lg, "passwort": PW, "rolle": rolle, **extra})
    assert r["_s"] == 200, r
def sitzung(login):
    c = cl(); s, b, _ = rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": PW}); assert s == 200, (login, s, b[:100]); return c
S = {l: sitzung(l) for l in ("buero", "werk", "emat", "eauf", "elief", "ekun")}

print("== S10: Betriebsunterlagen")
os.makedirs(D + "/dokumente", exist_ok=True)
for n in ("verfahrensdokumentation.html", "datenschutz.html"):
    open(f"{D}/dokumente/{n}", "w", encoding="utf-8").write("<html><body><h1>EIGENEFASSUNG-GEHEIM</h1><p>Sicherung liegt im Tresor hinter dem Bild.</p></body></html>")
anon = cl()
for n in ("verfahrensdokumentation.html", "datenschutz.html"):
    s0, b0, _ = rq(anon, "GET", "/hilfe/" + n); s1, b1, _ = rq(S["buero"], "GET", "/hilfe/" + n); s2, b2, _ = rq(inh, "GET", "/hilfe/" + n)
    ok(f"{n}: ohne Anmeldung nur die neutrale Vorlage", s0 == 200 and "EIGENEFASSUNG" not in b0 and len(b0) > 2000, (s0, b0[:80]))
    ok(f"{n}: Büro sieht die neutrale Vorlage, der Inhaber die Fassung des Betriebs", s1 == 200 and "EIGENEFASSUNG" not in b1 and s2 == 200 and "EIGENEFASSUNG" in b2, (s1, s2, b2[:60]))
ok("Handbuch bleibt ohne Anmeldung lesbar", rq(anon, "GET", "/hilfe/handbuch.html")[0] == 200)

print("== S11: Fehlversuche")
import benutzer
ok("Liste der Fehlversuche ist begrenzt (Obergrenze, Verfall, Länge des Namens)", benutzer.FEHLVERSUCHE_MAX == 5000 and benutzer.LOGIN_LAENGE == 100 and benutzer.FEHLVERSUCH_MERKEN == 900)
with benutzer._sperre: benutzer._fehlversuche.clear()
for i in range(12000): benutzer._fehlversuch(f"name{i}|10.0.0.{i % 250}")
ok("12.000 Fehlversuche mit verschiedenen Namen: höchstens 5.000 Einträge im Speicher", len(benutzer._fehlversuche) <= benutzer.FEHLVERSUCHE_MAX, len(benutzer._fehlversuche))
alt_zeit = time.time() - 2000
with benutzer._sperre:
    benutzer._fehlversuche.clear(); benutzer._fehlversuche.update({f"alt{i}|x": (2, 0, alt_zeit) for i in range(300)}); benutzer._fehlversuche["gesperrt|x"] = (9, time.time() + 100, alt_zeit)
    benutzer._aufraeumen(time.time())
ok("Zähler verfallen eine Viertelstunde nach dem letzten Versuch; laufende Sperren bleiben", list(benutzer._fehlversuche) == ["gesperrt|x"], list(benutzer._fehlversuche)[:5])
with benutzer._sperre: benutzer._fehlversuche.clear()
n5 = [benutzer._fehlversuch("a|1") for _ in range(5)]
ok("fünfter Fehlversuch sperrt wie bisher (10 Sekunden)", n5 == [1, 2, 3, 4, 5] and benutzer._gesperrt("a|1") and 8 < benutzer._fehlversuche["a|1"][1] - time.time() <= 10.5)
lang = "x" * 60000
s, b, _ = rq(cl(), "POST", "/api/anmeldung/anmelden", {"login": lang, "passwort": "falsch"})
ok("überlanger Benutzername: abgelehnt wie jeder falsche (kein Fehler des Programms)", s in (401, 413), (s, b[:80]))
def dauer(login, n=4):
    z = []
    for i in range(n):
        c = cl(); t0 = time.time(); rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": "falsch" + str(i)}); z.append(time.time() - t0)
    return statistics.median(z)
d_bekannt, d_fremd = dauer("buero"), dauer("gibtesnicht")
ok(f"Antwortzeit bei falschem Passwort: bekannter Name {d_bekannt * 1000:.0f} ms, unbekannter {d_fremd * 1000:.0f} ms (Unterschied unter 25 %)", abs(d_bekannt - d_fremd) / max(d_bekannt, d_fremd) < 0.25, (d_bekannt, d_fremd))
st = [rq(cl(), "POST", "/api/anmeldung/anmelden", {"login": f"niemand{i}", "passwort": "x"})[0] for i in range(14)]
ok("viele Fehlversuche von einem Gerät unter wechselnden Namen: ab dem zwanzigsten Wartezeit (429)", 429 in st, st)
s, b, _ = rq(cl(), "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
ok("solange die Gerätesperre läuft, wird auch die richtige Anmeldung von diesem Gerät abgewiesen", s == 429, (s, b[:80]))
time.sleep(11)
st2 = None
for _ in range(40):
    s, b, _ = rq(cl(), "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"}); st2 = s
    if s == 200: break
    time.sleep(2)
ok("nach der Wartezeit klappt die Anmeldung wieder", st2 == 200, st2)

print("== S12: Formelzeichen in Exportdateien")
k = A("POST", "kunden", {"kurzname": "=HYPERLINK(\"http://x\")", "firma": "=HYPERLINK(\"http://x\")", "plz": "88069", "ort": "+Tettnang"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "@SUM(1+1)*cmd"})
pid = ident(A("POST", f"auftraege/{a['id']}/positionen", {"text": "=SUMME(A1:A9) Schrank"})); A("PUT", f"positionen/{pid}", {"einzelpreis": 100, "preis_manuell": 1, "menge": 1})
b_ = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); A("POST", f"belege/{b_['id']}/festschreiben", {})
gs = A("POST", f"auftraege/{a['id']}/belege", {"art": "gutschrift", "frei": [{"text": "-Nachlass", "betrag": 10}]}); A("POST", f"belege/{gs['id']}/festschreiben", {})
pr = A("POST", "service/pruefer", {"von": H[:4] + "-01-01", "bis": H[:4] + "-12-31"})
ok("Datenträger für den Prüfer erstellt", pr["_s"] == 200 and pr.get("datei"), pr)
z = zipfile.ZipFile(D + "/exporte/" + pr["datei"]); zellen, boese = 0, []
for n in z.namelist():
    if not n.lower().endswith(".csv"): continue
    import csv
    for zeile in csv.reader(io.StringIO(z.read(n).decode("utf-8-sig")), delimiter=";"):
        for zelle in zeile:
            zellen += 1
            if zelle[:1] in "=+-@" and zelle and not re.fullmatch(r"[+-]?\d[\d.,]*%?", zelle): boese.append((n, zelle[:40]))
ok(f"Prüfer-CSV: keine der {zellen} Zellen beginnt mit = + - @ (außer Zahlen)", zellen > 50 and not boese, boese[:6])
alle = "".join(z.read(n).decode("utf-8-sig") for n in z.namelist() if n.lower().endswith(".csv"))
ok("die Texte stehen mit Hochkomma davor weiter in der Datei, negative Beträge unverändert", "'=SUMME(A1:A9) Schrank" in alle and "'=HYPERLINK" in alle and re.search(r";-\d+,\d\d", alle), alle[:300])
A("PUT", "einstellungen", {"datev": {"berater": "12345", "mandant": "100", "skr": "03"}})
dv = A("POST", "service/datev", {"von": H[:4] + "-01-01", "bis": H[:4] + "-12-31"})
zd = zipfile.ZipFile(D + "/exporte/" + dv["datei"]); stapel = zd.read(next(n for n in zd.namelist() if n.startswith("EXTF"))).decode("cp1252")
texte = [f for l in stapel.split("\r\n")[2:] if l for f in re.findall(r'"([^"]*)"', l)]
ok("DATEV-Stapel: kein Textfeld beginnt mit einem Formelzeichen", texte and not [t for t in texte if t[:1] in ("=", "+", "-", "@")], [t for t in texte if t[:1] in "=+-@"][:5])
rq(cl(), "POST", "/api/anmeldung/anmelden", {"login": "=cmd|' /C calc'!A0", "passwort": "x"})
s, pcsv, _ = rq(inh, "GET", "/api/service/protokoll.csv")
import kern
ok("Protokoll-CSV: Zellen mit Formelzeichen sind entschärft", s == 200 and not [c for zl in csv.reader(io.StringIO(pcsv.lstrip("﻿")), delimiter=";") for c in zl if c[:1] in "=+-@" and not re.fullmatch(r"[+-]?\d[\d.,]*%?", c)])
ok("kern.csv_zelle: Texte mit = + - @ bekommen ein Hochkomma, Zahlen und gewöhnliche Texte bleiben",
   [kern.csv_zelle(x) for x in ("=1+1", "+49 7542", "-12,50", "@x", "Schrank", 5, None, "-Rabatt")] == ["'=1+1", "'+49 7542", "-12,50", "'@x", "Schrank", 5, None, "'-Rabatt"])

print("== S13: Verschlüsselung der Zugangsdaten")
import geheim, types
import os as _os
ok("geheim.Fehler ist vorhanden; ohne Windows bleibt der Wert wie bisher unverändert, unter Windows wird er verschlüsselt",
   issubclass(geheim.Fehler, RuntimeError) and (geheim.verschluesseln("abc").startswith("dpapi:") if _os.name == "nt" else geheim.verschluesseln("abc") == "abc"))
class _Falsch:   # Windows-Schnittstelle, deren Verschlüsselung scheitert
    class crypt32:
        @staticmethod
        def CryptProtectData(*a): return 0
import ctypes
class _B(ctypes.Structure): _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]
alt_dpapi = geheim._dpapi
geheim._dpapi = lambda: (types.SimpleNamespace(windll=_Falsch, byref=ctypes.byref, create_string_buffer=ctypes.create_string_buffer, cast=ctypes.cast, POINTER=ctypes.POINTER, c_char=ctypes.c_char, string_at=ctypes.string_at), _B)
try:
    try: erg_ = geheim.verschluesseln("supergeheim"); gemeldet = False
    except geheim.Fehler as f: gemeldet = "nicht gespeichert" in str(f)
finally: geheim._dpapi = alt_dpapi
ok("scheitert die Windows-Verschlüsselung, wird ein Fehler gemeldet statt des Klartexts zurückgegeben", gemeldet)

print("== M6/M7/M8: Rechte")
kq = A("POST", "kunden", {"kurzname": "Zirbel, Zeno", "nachname": "Zirbel", "vorname": "Zeno", "plz": "88099", "ort": "Neukirch"})
lf = A("POST", "lieferanten", {"kurzname": "Zirbelholz AG", "firma": "Zirbelholz AG"})
mat = A("POST", "material", {"kategorie": "holzwerkstoffe", "bezeichnung": "Zirbe massiv", "einheit": "m²", "ek_preis": 7131.31, "aufschlag": 33.33, "lieferant_id": lf["id"]})
A("POST", "lager", {"material_id": mat["id"], "art": "zugang", "menge": 10, "preis": 7131.31})
az = A("POST", "auftraege", {"kunde_id": kq["id"], "bezeichnung": "Zirbenstube"})
pz = ident(A("POST", f"auftraege/{az['id']}/positionen", {"text": "Zirbenstube komplett"})); A("PUT", f"positionen/{pz}", {"einzelpreis": 9292.92, "preis_manuell": 1, "menge": 1})
ang = A("POST", f"auftraege/{az['id']}/belege", {"art": "angebot"}); rg = A("POST", f"auftraege/{az['id']}/belege", {"art": "rechnung"}); A("POST", f"belege/{rg['id']}/festschreiben", {})
ls = A("POST", f"auftraege/{az['id']}/belege", {"art": "lieferschein"})
arten = lambda c: sorted({x["art"] for x in A("GET", "suche?q=zirb", c=c)["liste"]})
ok("Suche als Inhaber: Kunde, Auftrag, Lieferant, Material", arten(inh) == ["Auftrag", "Kunde", "Lieferant", "Material"], arten(inh))
ok("nur Material: findet nur Material (bisher auch Kunde und Auftrag)", arten(S["emat"]) == ["Material"], arten(S["emat"]))
ok("nur Lieferanten: findet nur den Lieferanten", arten(S["elief"]) == ["Lieferant"], arten(S["elief"]))
ok("nur Kunden: findet nur den Kunden", arten(S["ekun"]) == ["Kunde"], arten(S["ekun"]))
ok("Werkstatt: Auftrag und Material, keine Kunden, Lieferanten oder Belege", arten(S["werk"]) == ["Auftrag", "Material"], arten(S["werk"]))
nr = A("GET", f"belege/{rg['id']}")["nummer"]
ok("Belegnummer: Büro findet die Rechnung, Benutzer ohne Preise nicht", any(x["titel"] == nr for x in A("GET", "suche?q=" + nr, c=S["buero"])["liste"])
   and not any(x["titel"] == nr for x in A("GET", "suche?q=" + nr, c=S["eauf"])["liste"]), A("GET", "suche?q=" + nr, c=S["eauf"])["liste"])
m_ = rq(S["emat"], "GET", f"/api/material/{mat['id']}")[1] + rq(S["emat"], "GET", "/api/material")[1] + rq(S["werk"], "GET", f"/api/material/{mat['id']}")[1]
ok("Material ohne Preisrecht: weder höchster Zugangspreis noch Aufschlag in den Daten", "7131" not in m_ and "33.33" not in m_ and "hoechst_zugang" not in m_ and '"aufschlag"' not in m_, re.findall(r'"(?:hoechst_zugang|aufschlag\d?)":[^,]*', m_)[:5])
m_i = rq(inh, "GET", f"/api/material/{mat['id']}")[1]
ok("der Inhaber sieht beides weiter", "7131.31" in m_i and "hoechst_zugang" in m_i, m_i[:200])
for pfad in (f"/druck/{rg['id']}", f"/druck/{rg['id']}.pdf", f"/druck/{ang['id']}", f"/api/belege/{rg['id']}/zugferd.xml", f"/api/belege/{rg['id']}/xrechnung.xml"):
    s, b, _ = rq(S["eauf"], "GET", pfad, roh=True)
    b = b if isinstance(b, bytes) else b.encode("utf-8")
    ok(f"ohne Preisrecht gesperrt: {pfad}", s == 403 and b"9292" not in b and b"11.058" not in b, (s, b[:80]))
s, b, _ = rq(S["eauf"], "GET", f"/druck/{ls['id']}")
ok("Lieferschein (ohne Preise) bleibt für Benutzer ohne Preisrecht ansehbar", s == 200 and "9292" not in b and "9.292" not in b, (s, b[:80]))
s, b, _ = rq(S["buero"], "GET", f"/druck/{rg['id']}")
ok("Büro sieht die Rechnung wie bisher", s == 200 and "9.292,92" in b, s)

print("== D7/D8: Anonymisieren und Datenauskunft")
con = sqlite3.connect(D + "/buero.db", timeout=30); con.row_factory = sqlite3.Row
k = A("POST", "kunden", {"kurzname": "Quittenbaum, Zacharias", "vorname": "Zacharias", "nachname": "Quittenbaum", "strasse": "Feigenhain", "hausnr": "7", "plz": "88099", "ort": "Neukirch", "telefon": "07542 918273", "email1": "zq@quittenbaum.example"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Küche Quittenbaum"})
texte = ["Einbauschrank für Herrn Quittenbaum, Schlafzimmer", "Sideboard Quittenbaum Wohnzimmer", "Regal, Abholung durch Zacharias am Freitag", "Garderobe laut Skizze Quittenbaum Zacharias",
         "Nachttisch für Tochter Mirabell Quittenbaum", "Tisch für QUITTENBAUM", "Quittenbaum-Regal nach Art des Hauses"]
for t in texte:
    pid = ident(A("POST", f"auftraege/{a['id']}/positionen", {"text": t})); A("PUT", f"positionen/{pid}", {"einzelpreis": 100, "preis_manuell": 1, "menge": 1})
ang2 = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"}); ab2 = A("POST", f"auftraege/{a['id']}/belege", {"art": "ab"})
png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
A("POST", f"belege/{ab2['id']}/unterschreiben", {"bild": png, "name": "Zacharias Quittenbaum", "ort": "Neukirch"})
A("POST", "termine", {"typ": "Aufmaß", "titel": "Aufmaß Quittenbaum", "von": H, "bis": H})
A("POST", "termine", {"typ": "Sonstiges", "titel": "Zahnarzt", "von": H, "bis": H})
A("POST", "stunden", {"auftrag_id": a["id"], "datum": H, "stunden": 2, "taetigkeit": "Montage Quittenbaum", "kst": "MONTAGE"})
A("POST", "auftragskosten", {"auftrag_id": a["id"], "bezeichnung": "Sonderbestellung Quittenbaum", "betrag": 50, "menge": 1, "datum": H})
bt = A("POST", "bautagebuch", {"auftrag_id": a["id"], "datum": H}); A("PUT", f"bautagebuch/{bt.get('id')}", {"arbeiten": "Küche gestellt, Quittenbaum hat geholfen", "wetter": "trocken"})
A("POST", "wiedervorlagen", {"kunde_id": k["id"], "text": "Nachfassen Küche", "datum": H})
con.execute("INSERT OR REPLACE INTO bank_kundenkonten (iban, kunde_id, zuletzt) VALUES ('DE89370400440532013000', ?, ?)", (k["id"], H)); con.commit()
ak = A("GET", f"kunden/{k['id']}/auskunft")
ok("Datenauskunft nennt Wiedervorlagen, Bautagebuch, digitale Unterschriften und das gemerkte Zahlerkonto",
   len(ak.get("wiedervorlagen", [])) == 1 and len(ak.get("bautagebuch", [])) == 1 and len(ak.get("unterschriften", [])) == 1 and ak["unterschriften"][0]["name"] == "Zacharias Quittenbaum"
   and len(ak.get("zahlerkonten", [])) == 1, {x: ak.get(x) for x in ("wiedervorlagen", "bautagebuch", "unterschriften", "zahlerkonten")})
ab_ = A("POST", f"kunden/{k['id']}/auskunft", {})
brief_text = json.dumps(ab_, ensure_ascii=False)
ok("der Auskunftsbrief enthält die drei neuen Abschnitte", all(t in brief_text for t in ("Wiedervorlagen", "Bautagebuch", "Digitale Unterschriften auf Belegen", "Nachfassen Küche")), brief_text[:300])
info = A("GET", f"kunden/{k['id']}/anonymisieren")
ok("vor Fristablauf: nicht erlaubt, keine Fundstellen berechnet", info["erlaubt"] is False and "fundstellen" not in info, {x: info.get(x) for x in ("erlaubt", "frist_ende")})
for t, sp, wo, arg in (("belege", "datum", "auftrag_id=?", a["id"]), ("auftraege", "angelegt", "id=?", a["id"]), ("auftraege", "geaendert", "id=?", a["id"]), ("termine", "von", "auftrag_id=?", a["id"])):
    con.execute(f"UPDATE {t} SET {sp}='2013-03-05' WHERE {wo}", (arg,))
con.execute("UPDATE kunden SET angelegt='2013-01-01', geaendert='2013-01-01', aufbewahren_bis='' WHERE id=?", (k["id"],)); con.commit()
info = A("GET", f"kunden/{k['id']}/anonymisieren"); fu = info.get("fundstellen") or []
tx = {f["text"]: f for f in fu}
ok("nach Fristablauf: Vorschau zeigt die Stellen, an denen der Name allein steht", info["erlaubt"] and all(any(t in x for x in tx) for t in ("Sideboard Quittenbaum Wohnzimmer", "Abholung durch Zacharias", "Tochter Mirabell Quittenbaum", "Tisch für QUITTENBAUM",
   "Montage Quittenbaum", "Sonderbestellung Quittenbaum", "Aufmaß Quittenbaum", "Quittenbaum hat geholfen")), sorted(tx))
ok("Stellen mit Anrede oder vollem Namen stehen nicht in der Liste (sie werden ohnehin ersetzt)", not any("Herrn Quittenbaum" in x or "Quittenbaum Zacharias" in x for x in tx), sorted(tx))
ok("der fremde Termin „Zahnarzt“ steht nicht in der Liste", not any("Zahnarzt" in x for x in tx))
f_side = next(f for f in fu if "Sideboard" in f["text"])
ok("eine Fundstelle fasst Position und eingefrorenen Belegstand zusammen", any(w.startswith("Position in Auftrag") for w in f_side["wo"]) and sum(1 for w in f_side["wo"] if w.startswith("Beleg")) == 2, f_side)
behalten = next(f for f in fu if "Quittenbaum-Regal" in f["text"])
wahl = [f["id"] for f in fu if f["id"] != behalten["id"]]
erg = A("POST", f"kunden/{k['id']}/anonymisieren", {"schwaerzen": wahl})
ok("ausgeführt: ausgewählte Stellen geschwärzt, eine auf Wunsch belassen", erg["_s"] == 200 and erg.get("erledigt") and erg["geschwaerzt"] == len(wahl) and erg["belassen"] == 1, {x: erg.get(x) for x in ("erledigt", "geschwaerzt", "belassen", "fehler")})
SUCH = re.compile(r"(?i)quittenbaum|zacharias|feigenhain|918273|zq@")
funde = {}
for t in [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    try:
        for r in con.execute(f'SELECT * FROM "{t}"'):
            for sp in r.keys():
                v = r[sp]
                if isinstance(v, str) and SUCH.search(v): funde.setdefault(t, []).append(v[max(0, SUCH.search(v).start() - 30):SUCH.search(v).start() + 40])
    except sqlite3.Error: pass
erlaubt = {"positionen", "belege", "protokoll"}
ok("der Name steht danach nur noch im Protokoll und an der bewusst belassenen Stelle (Position und ihre Belegzeilen)",
   set(funde) <= erlaubt and all("Quittenbaum-Regal" in v for t in ("positionen", "belege") for v in funde.get(t, [])), {t: v[:3] for t, v in funde.items()})
pt = [r["text"] for r in con.execute("select text from positionen where auftrag_id=? order by id", (a["id"],))]
ok("Positionstexte: „Sideboard … Wohnzimmer“, „Abholung durch … am Freitag“, „Tisch für …“", pt[1] == "Sideboard … Wohnzimmer" and pt[2] == "Regal, Abholung durch … am Freitag" and pt[5] == "Tisch für …", pt)
bz = [z["text"] for r in con.execute("select daten from belege where auftrag_id=?", (a["id"],)) for z in json.loads(r["daten"]).get("zeilen", []) if z.get("typ") == "pos"]
ok("eingefrorene Belegzeilen sind genauso geschwärzt", "Sideboard … Wohnzimmer" in bz and not any("Sideboard Quittenbaum" in x for x in bz), bz[:8])
ok("Stundenbuchung, Auftragskosten und der Termin ohne Auftrag sind geschwärzt; „Zahnarzt“ ist unberührt",
   con.execute("select taetigkeit from stunden where auftrag_id=?", (a["id"],)).fetchone()[0] == "Montage …"
   and con.execute("select bezeichnung from auftragskosten where auftrag_id=?", (a["id"],)).fetchone()[0] == "Sonderbestellung …"
   and sorted(r[0] for r in con.execute("select titel from termine where auftrag_id is null")) == ["Aufmaß …", "Zahnarzt"],
   [tuple(r) for r in con.execute("select titel from termine where auftrag_id is null")])
ok("das gemerkte Zahlerkonto ist gelöscht", not con.execute("select 1 from bank_kundenkonten where kunde_id=?", (k["id"],)).fetchone())
pz_ = [r["text"] for r in con.execute("select text from protokoll where art='kunde_anonymisiert'")]
ok("Protokoll nennt geschwärzte und belassene Textstellen", pz_ and "Textstellen mit einzeln stehendem Namen geschwärzt" in pz_[-1] and "belassen" in pz_[-1], pz_[-1:])

print("== P6: Löschliste")
t0 = time.time(); lp = A("GET", "datenschutz/faellig"); t1 = time.time()
ok("Löschliste wird geliefert, Kunden mit frischen Belegen stehen nicht darin", lp["_s"] == 200 and not any(x["id"] in (kq["id"],) for x in lp.get("kunden", [])), lp.get("kunden"))
import datenschutz
aufrufe = []
datenschutz.faellig(con, lambda c, kid: (aufrufe.append(kid), {"erlaubt": False})[1])
ok("die ausführliche Prüfung läuft nur noch für Kunden ohne Beleg aus den letzten sechs Jahren", kq["id"] not in aufrufe and len(aufrufe) < con.execute("select count(*) from kunden").fetchone()[0], aufrufe)
print("FEHLER:", fehler)
