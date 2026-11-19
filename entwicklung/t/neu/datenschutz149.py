"""Version 149, Datenschutz: Anonymisieren entfernt auch Namen in freien Texten und alle abgelegten Dateien, die Belegprüfung
bleibt danach ohne Fehlalarm, Aufbewahrungsfrist einstellbar (8 bis 10 Jahre), alte Kontoauszüge löschbar, Vorsorgedaten auf
Wunsch nur für den Inhaber. Erwartet eine frische Prüfinstanz; der Server wird für den zweiten Teil mit dem Datum 2.1.2037
neu gestartet (libfaketime), damit die Fristen ohne Eingriff in die Datenbank ablaufen."""
import json, sys, os, re, io, time, base64, socketserver, threading, sqlite3, subprocess, glob
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
sys.path.insert(0, "/home/claude/eberle-buero")
import datenschutz
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:600]))
    if not bed: fehler.append(name)

print("== Namen in Texten (ohne Server)")
ks = {"vorname": "Peter", "nachname": "Schrank", "kurzname": "Schrank, Peter", "strasse": "Bachweg", "hausnr": "7", "email1": "peter@beispiel.de", "telefon": "07542 998877"}
t = datenschutz.schwaerzen_lang("Schrank Eiche massiv\nfür Herrn Schrank, Lieferung an Peter Schrank, Bachweg 7, Tel. 07542 998877\nSchranks Sohn holt ab; Rückfragen an peter@beispiel.de", ks)
ok("Positionstext: Name mit Anrede, mit Vornamen, Anschrift, Telefon und Mail entfernt – die Ware „Schrank Eiche“ bleibt", t.startswith("Schrank Eiche massiv\nfür …, Lieferung an …, …, Tel. …") and "Peter" not in t and "Bachweg" not in t and "peter@" not in t, t)
ok("Bezeichnung „Küche Schrank / Peter“ → jedes Namenswort entfernt", datenschutz.schwaerzen_kurz("Küche Schrank / Peter", ks) == "Küche … / …", datenschutz.schwaerzen_kurz("Küche Schrank / Peter", ks))
kw = {"vorname": "Ute", "nachname": "Weiß", "kurzname": "Weiß, Ute", "firma": "Schreinerei Weiß GmbH", "strasse": "Alte Gasse"}
ok("Kundin Weiß: „Front weiß lackiert“ bleibt, „Frau Weiß“ und „Ute Weiß“ verschwinden", datenschutz.schwaerzen_lang("Front weiß lackiert, Absprache mit Frau Weiß bzw. Ute Weiß", kw) == "Front weiß lackiert, Absprache mit … bzw. …", datenschutz.schwaerzen_lang("Front weiß lackiert, Absprache mit Frau Weiß bzw. Ute Weiß", kw))
ok("Allerweltswörter aus Firma und Straße bleiben („Schreinerei“, „Gasse“)", datenschutz.schwaerzen_kurz("Einbau Schreinerei Weiß, Alte Gasse", kw) == "Einbau Schreinerei …, Alte Gasse", datenschutz.schwaerzen_kurz("Einbau Schreinerei Weiß, Alte Gasse", kw))
ok("leere Angaben ändern nichts", datenschutz.schwaerzen_kurz("Tisch", {}) == "Tisch" and datenschutz.schwaerzen_lang("Tisch", {}) == "Tisch" and datenschutz.schwaerzen_lang(None, ks) is None)

POST = []
class H(socketserver.StreamRequestHandler):
    def handle(self):
        w = lambda t: self.wfile.write((t + "\r\n").encode())
        w("220 test ESMTP")
        while True:
            z = self.rfile.readline()
            if not z: return
            k = z.decode("utf-8", "replace").strip().upper()
            if k.startswith("EHLO"): w("250-test"); w("250-AUTH PLAIN LOGIN"); w("250 8BITMIME")
            elif k.startswith("AUTH"): w("235 ok")
            elif k.startswith("DATA"):
                w("354 los"); roh = b""
                while not roh.endswith(b"\r\n.\r\n"): roh += self.rfile.readline()
                POST.append(roh); w("250 ok")
            elif k.startswith("QUIT"): w("221 bye"); return
            else: w("250 ok")
srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, c=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
EIGEN = "DE02120300000000202051"
A("PUT", "einstellungen", {"firma": "Muster", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890", "sepa_iban": EIGEN, "firma_inhaber": "Jonas Muster",
                           "mail": {"adresse": "betrieb@beispiel.de", "smtp_server": "127.0.0.1", "smtp_port": srv.server_address[1], "smtp_modus": "keine", "passwort": "x", "gesendet_ablegen": False}})

print("== D3: Vorsorge und Exposition")
ma = A("POST", "mitarbeiter", {"vorname": "Max", "nachname": "Werk"}); mid_ = ma.get("id") or ma.get("mitarbeiter", {}).get("id")
A("POST", "benutzer", {"name": "Berta", "login": "buero", "passwort": "Pruefung#2026", "rolle": "buero"})
buero = cl(); rq(buero, "POST", "/api/anmeldung/anmelden", {"login": "buero", "passwort": "Pruefung#2026"})
A("POST", "arbeitsschutz/vorsorge", {"mitarbeiter_id": mid_, "art": "G 44 Hartholzstäube", "anlass": "Pflichtvorsorge", "datum": time.strftime("%Y-%m-%d"), "naechste": "2028-11-01", "ergebnis": "keine Bedenken", "arzt": "Dr. XARZT"})
v1, e1 = A("GET", "arbeitsschutz/vorsorge", c=buero), A("GET", "arbeitsschutz/exposition", c=buero)
ok("Vorgabe: das Büro sieht Vorsorge und Expositionsverzeichnis (wie bisher)", v1["_s"] == 200 and e1["_s"] == 200, (v1["_s"], e1["_s"]))
A("PUT", "einstellungen", {"vorsorge_nur_inhaber": True})
v2, e2, v3 = A("GET", "arbeitsschutz/vorsorge", c=buero), A("GET", "arbeitsschutz/exposition", c=buero), A("GET", "arbeitsschutz/vorsorge")
ok("mit dem Schalter „nur Inhaber“: Büro abgewiesen, Inhaber sieht weiter alles", v2["_s"] == 403 and e2["_s"] == 403 and v3["_s"] == 200 and "XARZT" in json.dumps(v3), (v2["_s"], e2["_s"], v3["_s"]))
ue = A("GET", "arbeitsschutz/uebersicht", c=buero)
ok("die Übersicht des Büros nennt dann keine Vorsorgetermine", ue["_s"] == 200 and "Vorsorge" not in json.dumps(ue.get("hinweise") or ue.get("faellig") or [], ensure_ascii=False), str(ue)[:300])

print("== Vorbereitung: ein Kunde mit allem, was dazugehört")
k = A("POST", "kunden", {"kurzname": "Schrank, Peter", "vorname": "Peter", "nachname": "Schrank", "strasse": "Bachweg", "hausnr": "7", "plz": "88069", "ort": "Tettnang", "email1": "peter@beispiel.de", "telefon": "07542 998877", "bemerkungen": "Hund im Garten"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Küche Schrank", "bemerkungen": "Schlüssel bei Peter abholen"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Schrank Eiche massiv\nfür Herrn Schrank, Lieferung an Peter Schrank, Bachweg 7"}); pid = po.get("id") or po["position"]["id"]
A("PUT", f"positionen/{pid}", {"einzelpreis": 1000, "preis_manuell": 1, "menge": 1})
an = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"})
m1 = A("POST", f"belege/{an['id']}/mail", {"an": "peter@beispiel.de", "betreff": "Angebot Küche Schrank", "text": "Sehr geehrter Herr Schrank", "anhaenge": ["beleg"]})
re1 = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); f1 = A("POST", f"belege/{re1['id']}/festschreiben", {}); rb = A("GET", f"belege/{re1['id']}")
ops = A("GET", "offeneposten?status=alle"); op = next(o for o in (ops.get("liste") or ops.get("posten") or []) if o.get("beleg_id") == re1["id"])
mahn = A("POST", f"offeneposten/{op['id']}/mahnung", {"stufe": 0, "text": "Sehr geehrter Herr Schrank, bitte zahlen Sie."})
def ntry(betrag, name, zweck, ref, tag):
    return (f'<Ntry><Amt Ccy="EUR">{betrag:.2f}</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>{tag}</Dt></BookgDt><ValDt><Dt>{tag}</Dt></ValDt><AcctSvcrRef>{ref}</AcctSvcrRef>'
            f"<NtryDtls><TxDtls><RltdPties><Dbtr><Nm>{name}</Nm></Dbtr><DbtrAcct><Id><IBAN>DE44500105175407324931</IBAN></Id></DbtrAcct></RltdPties><RmtInf><Ustrd>{zweck}</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>")
heute = time.strftime("%Y-%m-%d")
bal = lambda cd, betrag: f'<Bal><Tp><CdOrPrtry><Cd>{cd}</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">{betrag:.2f}</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>{heute}</Dt></Dt></Bal>'
camt = (f'<?xml version="1.0" encoding="UTF-8"?><Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><GrpHdr><MsgId>M1</MsgId><CreDtTm>{heute}T20:00:00</CreDtTm></GrpHdr><Stmt><Id>S1</Id><CreDtTm>{heute}T20:00:00</CreDtTm>'
        f'<FrToDt><FrDtTm>{heute}T00:00:00</FrDtTm><ToDtTm>{heute}T23:59:59</ToDtTm></FrToDt><Acct><Id><IBAN>{EIGEN}</IBAN></Id></Acct>{bal("PRCD", 0)}{bal("CLBD", rb["brutto"] + 55)}'
        + ntry(rb["brutto"], "Peter Schrank", f"Rechnung {rb['nummer']} Peter Schrank Bachweg", "K1", heute) + ntry(55, "Anna Fremd", "Spende Anna", "K2", heute) + "</Stmt></BkToCstmrStmt></Document>").encode()
ein = A("POST", "bank/einlesen", {"daten": base64.b64encode(camt).decode(), "dateiname": "auszug.xml"}); sich = A("POST", "bank/sichere", {})
A("POST", "termine", {"auftrag_id": a["id"], "typ": "Aufmaß", "titel": "Aufmaß bei Peter Schrank", "von": heute, "bis": heute, "notiz": "klingeln bei Schrank"})
A("POST", "notizen", {"kunde_id": k["id"], "auftrag_id": a["id"], "text": "Peter ruft zurück"})
br = A("POST", "briefe", {"kunde_id": k["id"], "betreff": "Terminbestätigung Herr Schrank", "text": "Sehr geehrter Herr Schrank,\nwir kommen am Montag."}); bp = A("POST", f"briefe/{br.get('id')}/pdf", {}) if br.get("id") else {}
bt = A("POST", "bautagebuch", {"auftrag_id": a["id"], "datum": heute, "arbeiten": "Korpus gestellt, Herr Schrank war anwesend", "besonderes": "Peter Schrank wünscht andere Griffe"})
vorb = {"Angebot gesendet": m1["_s"], "Rechnung fest": f1["_s"], "Mahnung": mahn["_s"], "Auszug": ein["_s"], "zugeordnet": sich.get("zugeordnet"), "Brief": br["_s"], "Bautagebuch": bt["_s"]}
ok("Angebot gesendet, Rechnung festgeschrieben, Mahnung, Zahlung über den Kontoauszug, Termin, Notiz, Brief, Bautagebuch", all(v in (200, 1) for v in vorb.values()), (vorb, mahn.get("fehler"), bt.get("fehler"), br.get("fehler")))
con = sqlite3.connect(D + "/buero.db", timeout=20); con.row_factory = sqlite3.Row
def dateien_da():
    return sorted(os.path.relpath(p, D) for muster in ("belege/*/*.pdf", "belege/*/*.xml", "belege/*/versandt/*.pdf", "mails/*/*.eml", "mahnungen/*/*.pdf", "briefe/*/*.pdf", "bank/*/*") for p in glob.glob(os.path.join(D, muster)))
vorher_dateien = dateien_da()
ok("abgelegt sind: Archiv-PDF, versandte Fassung, gesendete Mail, Mahnung, Kontoauszug", all(any(d.startswith(x) for d in vorher_dateien) for x in ("belege/", "mails/", "mahnungen/", "bank/")) and any("/versandt/" in d for d in vorher_dateien), vorher_dateien)

print("== D4: Frist")
i10 = A("GET", f"kunden/{k['id']}/anonymisieren"); jahr = int(heute[:4])
ok(f"Vorgabe 10 Jahre: anonymisieren gesperrt bis 31.12.{jahr + 10}", i10["frist_ende"] == f"{jahr + 10}-12-31" and not i10["erlaubt"], i10)
A("PUT", "einstellungen", {"frist_rechnung_jahre": 8}); i8 = A("GET", f"kunden/{k['id']}/anonymisieren")
ok(f"auf 8 Jahre gestellt: Fristende 31.12.{jahr + 8}", i8["frist_ende"] == f"{jahr + 8}-12-31", i8)
x3 = A("PUT", "einstellungen", {"frist_rechnung_jahre": 3}); i3 = A("GET", f"kunden/{k['id']}/anonymisieren")
ok("3 Jahre (unzulässig) werden seit Version 152 beim Speichern abgelehnt; es bleibt bei den eingestellten 8 Jahren",
   x3["_s"] == 400 and "zwischen 8 und 10" in (x3.get("fehler") or "") and i3["frist_ende"] == f"{jahr + 8}-12-31", (x3, i3))
A("PUT", "einstellungen", {"frist_rechnung_jahre": 10})
A("PUT", "einstellungen", {"frist_rechnung_jahre": 10})
r = A("POST", f"kunden/{k['id']}/anonymisieren", {})
ok("vor Fristende wird nicht anonymisiert", r["_s"] == 400 and "Aufbewahrungsfrist" in r.get("fehler", ""), (r["_s"], r.get("fehler")))
con.close()

print("== Zeitsprung: Neustart am 2.1.2037")
def neustart(falsche_zeit=None):
    for f in os.listdir("/proc"):
        if f.isdigit():
            try:
                if b"BUERO_PORT=8799" in open(f"/proc/{f}/environ", "rb").read(): os.kill(int(f), 15)
            except OSError: pass
    time.sleep(1.5)
    zeit = (f'LD_PRELOAD=/usr/local/lib/python3.13/dist-packages/libfaketime/vendor/libfaketime/src/libfaketime.so.1 FAKETIME="@{falsche_zeit}" DONT_FAKE_MONOTONIC=1 FAKETIME_NO_CACHE=1 ' if falsche_zeit else "")
    subprocess.Popen(f"cd /tmp/claude-0/t/v25/eberle-buero && {zeit}BUERO_PORT=8799 BUERO_BROWSER=/tmp/claude-0/t/fake/chrome nohup ${{BUERO_PY:-python3}} app.py kein-browser >> /tmp/claude-0/t/v25/log.txt 2>&1 &", shell=True)
    for i in range(60):
        time.sleep(0.5)
        try: urllib.request.urlopen(U + "/api/version", timeout=2).read(); return True
        except Exception: pass
    return False
if not os.path.exists("/usr/local/lib/python3.13/dist-packages/libfaketime/vendor/libfaketime/src/libfaketime.so.1"):
    ok("libfaketime vorhanden (pip install libfaketime)", False); print("FEHLER:", fehler); sys.exit(1)
ok("Neustart mit Datum 2037", neustart("2037-01-02 10:00:00"))
inh = cl(); s, b, _ = rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
ok("Anmeldung im Jahr 2037", s == 200, (s, b[:100]))
pr = A("GET", "service/protokoll?voll=1"); bel = pr.get("belege") or {}
ok("vor dem Anonymisieren: Belegprüfung ohne Befund", bel.get("ok") is True, bel.get("fehler"))
fl = A("GET", "datenschutz/faellig")
ok("Löschprüfung nennt den Kunden und die abgelaufenen Kontoauszüge", any(x["id"] == k["id"] for x in fl.get("kunden") or []) and (fl.get("kontoauszuege") or {}).get("auszuege") == 1, (fl.get("kunden"), fl.get("kontoauszuege")))

print("== D1/D2: Anonymisieren")
r = A("POST", f"kunden/{k['id']}/anonymisieren", {})
ok("Anonymisieren ausgeführt", r["_s"] == 200 and r.get("erledigt") and r.get("dateien", 0) >= 4, r)
con = sqlite3.connect(D + "/buero.db", timeout=20); con.row_factory = sqlite3.Row
kd = dict(con.execute("SELECT * FROM kunden WHERE id=?", (k["id"],)).fetchone())
ok("Kundenstamm: Name, Anschrift, Kontakt leer; Postleitzahl und Ort bleiben für die Gebietsauswertung", kd["kurzname"].startswith("anonymisiert") and not kd["nachname"] and not kd["strasse"] and not kd["email1"] and kd["plz"] == "88069" and kd["ort"] == "Tettnang", {x: kd[x] for x in ("kurzname", "nachname", "strasse", "email1", "plz", "ort")})
spuren = []
for tab in [r_[0] for r_ in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    if tab in ("protokoll", "sqlite_sequence", "benutzer", "sitzungen", "einstellungen", "mitarbeiter", "as_vorsorge"):
        continue
    for zeile in con.execute(f"SELECT * FROM {tab}"):
        text = json.dumps(dict(zeile), ensure_ascii=False, default=str)
        for wort in ("Peter", "Bachweg", "peter@beispiel.de", "07542 998877", "Herr Schrank", "Herrn Schrank", "Hund im Garten"):
            if wort in text: spuren.append((tab, wort, text[max(0, text.index(wort) - 40):text.index(wort) + 40]))
ok("in keiner Tabelle steht noch Name, Straße, Mailadresse, Telefon oder Bemerkung des Kunden", not spuren, spuren[:6])
pt = con.execute("SELECT text FROM positionen WHERE id=?", (pid,)).fetchone()[0]; bez = con.execute("SELECT bezeichnung FROM auftraege WHERE id=?", (a["id"],)).fetchone()[0]
ok("Positionstext behält die Ware („Schrank Eiche massiv“), die Auftragsbezeichnung lautet „Küche …“", pt.startswith("Schrank Eiche massiv") and "…" in pt and bez == "Küche …", (pt, bez))
bu = [dict(r_) for r_ in con.execute("SELECT name, zweck, gegen_iban, betrag, status FROM bank_umsaetze ORDER BY id")]
ok("zugeordneter Kontoumsatz: Name, Zweck und Gegenkonto entfernt, Betrag und Zuordnung bleiben; der fremde Umsatz ist unberührt", bu[0]["name"] == "anonymisiert" and bu[0]["zweck"] == "" and bu[0]["gegen_iban"] == "" and abs(bu[0]["betrag"] - rb["brutto"]) < 0.01 and bu[0]["status"] != "offen" and bu[1]["name"] == "Anna Fremd", bu)
nachher = dateien_da()
ok("gelöscht sind Archiv-PDF, versandte Fassung, gesendete Mails, Mahnungs-PDF; der Kontoauszug liegt noch da", not any(d.startswith(("belege/", "mails/", "mahnungen/", "briefe/")) for d in nachher) and any(d.startswith("bank/") for d in nachher), nachher)
pe = [dict(r_) for r_ in con.execute("SELECT objekt, text, daten FROM protokoll WHERE art='kunde_anonymisiert'")]
ok("Protokoll: Kunde mit Nummer (ohne Namen) und Liste der entfernten Dateien", len(pe) == 1 and "Schrank" not in pe[0]["objekt"] + pe[0]["text"] and len(json.loads(pe[0]["daten"]).get("dateien") or []) >= 4, pe)
pr = A("GET", "service/protokoll?voll=1"); bel = pr.get("belege") or {}
ok("Belegprüfung danach: kein Fehlalarm (weder „Archiv-PDF fehlt“ noch „Inhalt weicht ab“ noch „versandte Fassung fehlt“)", bel.get("ok") is True and bel.get("anonymisiert") == 1, (bel.get("fehler"), bel.get("anonymisiert")))
bn = A("GET", f"belege/{re1['id']}")
ok("die Rechnung behält Nummer, Datum und Beträge", bn["nummer"] == rb["nummer"] and bn["brutto"] == rb["brutto"] and bn["datum"] == rb["datum"] and bn["anschrift"] == "anonymisiert", (bn.get("nummer"), bn.get("brutto")))
s_, t_, _ = rq(inh, "GET", f"/druck/{re1['id']}")
ok("ihre Druckansicht lässt sich weiter öffnen und nennt den Kunden nicht mehr", s_ == 200 and "Peter" not in t_ and "Bachweg" not in t_ and "Schrank Eiche massiv" in t_, s_)

print("== Kontoauszüge nach Fristablauf")
r = A("POST", "datenschutz/kontoauszuege", {}, c=None)
bu = [dict(r_) for r_ in con.execute("SELECT name, zweck, gegen_iban, betrag FROM bank_umsaetze ORDER BY id")]
ok("alte Kontoauszüge gelöscht: Datei weg, auch der fremde Umsatz ohne Name und Zweck, Beträge bleiben", r["_s"] == 200 and r["dateien"] == 1 and not any(d.startswith("bank/") for d in dateien_da()) and bu[1]["name"] == "anonymisiert" and bu[1]["zweck"] == "" and bu[1]["betrag"] == 55, (r, bu, dateien_da()))
pe = [dict(r_) for r_ in con.execute("SELECT text FROM protokoll WHERE art='bank_auszug_geloescht'")]
ok("der Vorgang steht im Protokoll", len(pe) == 1 and "1 Kontoauszugsdateien" in pe[0]["text"], pe)
fl = A("GET", "datenschutz/faellig")
ok("die Löschprüfung ist danach leer", (fl.get("kontoauszuege") or {}).get("auszuege") in (0, 1) and (fl.get("kontoauszuege") or {}).get("umsaetze", 0) == 0 and not any(x["id"] == k["id"] for x in fl.get("kunden") or []), fl)
con.close()
neustart()
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
