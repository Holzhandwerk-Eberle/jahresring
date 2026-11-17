"""Version 150: Datenbestand vom bisherigen PC übernehmen (Seite „Ersten Zugang anlegen“), Dateipfade nach einem
Ortswechsel, Rücksicherung einer Sicherung aus einem anderen Bestand.
Baut sich seine Instanzen selbst: „alter PC“ (Port 8798), „neuer PC“ (8797), fremder Bestand (8796) – jeweils in eigenen
Ordnern unter /tmp/claude-0/t/up150, damit die gespeicherten Dateipfade des alten Bestands am neuen Ort nicht stimmen."""
import base64, glob, http.cookiejar, json, os, shutil, sqlite3, subprocess, sys, time, urllib.error, urllib.request
from datetime import date

Q = "/home/claude/eberle-buero"; Z = "/tmp/claude-0/t/up150"
PY = os.environ.get("BUERO_PY", "python3")
fehler = []


def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:500]), flush=True)
    if not bed:
        fehler.append(name)


def prozesse(port):
    aus = []
    for f in os.listdir("/proc"):
        try:
            if f.isdigit() and f"BUERO_PORT={port}".encode() + b"\0" in open(f"/proc/{f}/environ", "rb").read() + b"\0":
                aus.append(int(f))
        except OSError:
            pass
    return aus


class PC:
    def __init__(self, name, port):
        self.name, self.port, self.u = name, port, f"http://127.0.0.1:{port}"
        self.basis = f"{Z}/{name}/Jahresring"; self.daten = self.basis + "/daten"
        self.sitzung()

    def sitzung(self):
        self.o = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def stoppen(self):
        for p in prozesse(self.port):
            try: os.kill(p, 15)
            except OSError: pass
        for i in range(40):
            if not prozesse(self.port): break
            time.sleep(0.25)

    def starten(self):
        log = open(f"{Z}/{self.name}/log.txt", "ab")
        subprocess.Popen([PY, "app.py", "kein-browser"], cwd=self.basis, stdout=log, stderr=log, start_new_session=True,
                         env={**os.environ, "BUERO_PORT": str(self.port), "BUERO_BROWSER": "/tmp/claude-0/t/fake/chrome"})
        for i in range(80):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(self.u + "/api/version", timeout=2).read(); return True
            except Exception: pass
        return False

    def frisch(self):
        """Programm neu aufspielen, ohne Daten (wie nach dem Setup)."""
        self.stoppen()
        shutil.rmtree(f"{Z}/{self.name}", ignore_errors=True); os.makedirs(self.basis)
        for x in os.listdir(Q):
            if x not in ("daten", "entwicklung", "__pycache__", ".git"):
                (shutil.copytree if os.path.isdir(f"{Q}/{x}") else shutil.copy2)(f"{Q}/{x}", f"{self.basis}/{x}")
        self.sitzung()
        return self.starten()

    def A(self, m, p, d=None, h=None, u=None):
        u = u or self.u
        r = urllib.request.Request(u + "/api/" + p, method=m, data=json.dumps(d).encode() if d is not None else None,
                                   headers={"Content-Type": "application/json", "Origin": u, **(h or {})})
        try:
            x = self.o.open(r, timeout=300); b = x.read().decode("utf-8", "replace"); s = x.status
        except urllib.error.HTTPError as e:
            b = e.read().decode("utf-8", "replace"); s = e.code
        j = json.loads(b) if b[:1] in "[{" else {"_text": b}
        if isinstance(j, dict): j["_s"] = s
        return j

    def roh(self, pfad):
        try:
            x = self.o.open(urllib.request.Request(self.u + pfad), timeout=60); return x.status, x.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def anmelden(self, login="jonas", pw="geheim123"):
        self.sitzung()
        return self.A("POST", "anmeldung/anmelden", {"login": login, "passwort": pw}).get("ok") is True

    def protokoll(self):
        pr = self.A("GET", "service/protokoll?voll=1")
        return pr.get("pruefung") or {}, pr.get("belege") or {}, pr.get("eintraege") or []

    def db(self, sql, *a):
        c = sqlite3.connect(self.daten + "/buero.db", timeout=20)
        try:
            r = c.execute(sql, a).fetchall(); c.commit(); return r
        finally:
            c.close()


def baum(o):
    """Dateien eines Ordners mit Größe und Änderungszeit (um zu zeigen, dass die Quelle unverändert bleibt)."""
    aus = {}
    for w, _, ds in os.walk(o):
        for d in ds:
            p = os.path.join(w, d); aus[os.path.relpath(p, o)] = (os.path.getsize(p), int(os.path.getmtime(p)))
    return aus


for port in (8796, 8797, 8798):
    for p in prozesse(port):
        os.kill(p, 15)
for x in ("alt", "altpc", "neupc", "fremd", "extern", "ablage"):
    shutil.rmtree(f"{Z}/{x}", ignore_errors=True)
os.makedirs(f"{Z}/ablage")

# ================================================================= alter PC: Bestand mit Dateien, Sicherungen, Kennwort
alt = PC("altpc", 8798)
ok("alter PC startet", alt.frisch())
alt.A("POST", "anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim123", "firma": "Holzwerkstatt Alt"})
ok("alter PC: Anmeldung", alt.anmelden())
alt.A("PUT", "einstellungen", {"firma": "Holzwerkstatt Alt", "firma_anschrift": "Weg 1\n88069 Tettnang", "firma_email": "a@b.de", "firma_telefon": "07542 1",
                               "ustid": "DE123456789", "sepa_iban": "DE89370400440532013000", "sicherung_ziel": f"{Z}/extern"})
k = alt.A("POST", "kunden", {"kurzname": "Muster", "nachname": "Muster", "strasse": "Str 2", "plz": "88069", "ort": "Tettnang", "email": "k@x.de"})
a = alt.A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Tisch"})
po = alt.A("POST", f"auftraege/{a['id']}/positionen", {"text": "Tisch"}); pid = po.get("id") or po["position"]["id"]
alt.A("PUT", f"positionen/{pid}", {"einzelpreis": 100, "preis_manuell": 1, "menge": 1})
re_ = alt.A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"})
ok("alter PC: Rechnung festgeschrieben", alt.A("POST", f"belege/{re_['id']}/festschreiben", {})["_s"] == 200)
anh = alt.A("POST", "anhaenge", {"kunde_id": k["id"], "dateiname": "Aufmaß Küche.txt", "daten": base64.b64encode("Aufmaß 2,40 m".encode()).decode()})
ok("alter PC: Anhang abgelegt", anh.get("id") and anh.get("pfad", "").startswith(alt.daten), anh)
s, xml = alt.roh(f"/api/belege/{re_['id']}/zugferd.xml")
lf = alt.A("POST", "lieferanten", {"kurzname": "Holz Lieferant", "firma": "Holz Lieferant GmbH", "ustid": "DE123456789", "iban": "DE89370400440532013000"})
e = alt.A("POST", "eingang/lesen", {"daten": base64.b64encode(xml).decode(), "dateiname": "r.xml"})
kopf = {"belegnr": e["rechnung"]["nummer"], "belegdatum": e["rechnung"]["datum"], "betrag": e["rechnung"]["zahlbetrag"], "iban": e["lieferant"]["iban"]}
z = alt.A("POST", "eingang/buchen", {"token": e["token"], "endung": e["endung"], "lieferant_id": lf["id"], "kopf": kopf, "zeilen": []}, {"X-Bestaetigt": "iban"})
zid = z.get("zahlung_id")
ok("alter PC: Eingangsrechnung mit Originaldatei gebucht", z["_s"] == 200 and zid, z)
ok("alter PC: Dateipfad der Eingangsrechnung ist voll gespeichert", alt.db("SELECT datei FROM zahlungen WHERE id=?", zid)[0][0].startswith(alt.daten))
KW = "Holz und Leim 2026"
ok("alter PC: Sicherungskennwort gesetzt", alt.A("POST", "service/kennwort", {"kennwort": KW, "kennwort2": KW}).get("gesetzt") is True)
sich = alt.A("POST", "service/sicherung", {})
ok("alter PC: vollständige Sicherung, extern verschlüsselt", sich.get("name") and sich.get("verschluesselt") is True, sich)
pr, bel, _ = alt.protokoll()
ok("alter PC: Protokoll und Belegprüfung stimmen", pr.get("ok") and bel.get("ok") and bel.get("eingang_geprueft") == 1, (pr, bel))
ALT = {"anzahl": pr["anzahl"], "hash": pr["letzter_hash"], "kunden": len(alt.A("GET", "kunden?status=alle")), "belege": len(alt.A("GET", "belege"))}
alt.stoppen()   # wie beim Kopieren im Betrieb: die -wal-Datei bleibt liegen
for name, inhalt in (("zertifikat/ca.pem", "ALT"), ("protokoll.txt", "MELDUNGEN-ALT"), ("tmp/rest.txt", "x"), ("browser-profil/profil.txt", "x")):
    os.makedirs(os.path.dirname(f"{alt.daten}/{name}"), exist_ok=True); open(f"{alt.daten}/{name}", "w").write(inhalt)
os.makedirs(f"{Z}/alt/Jahresring"); shutil.move(alt.daten, f"{Z}/alt/Jahresring/daten"); shutil.rmtree(f"{Z}/altpc")
QUELLE = f"{Z}/alt/Jahresring/daten"
ZIP = f"{QUELLE}/backup/{sich['name']}"; JRS = f"{Z}/extern/{sich['name']}.jrs"
# Tagessicherung auf dem externen Ziel (die von heute im Ordner backup stammt vom ersten Start, also vom noch leeren Bestand)
os.makedirs(f"{Z}/extern/Jahresring-Datenbank", exist_ok=True); TAG_DB = f"{Z}/extern/Jahresring-Datenbank/buero_2026-11-16.db"
shutil.copytree(QUELLE, f"{Z}/ablage/fuer_tag", ignore=shutil.ignore_patterns("backup"))
c = sqlite3.connect(f"{Z}/ablage/fuer_tag/buero.db"); d = sqlite3.connect(TAG_DB); c.backup(d); d.execute("PRAGMA journal_mode=DELETE"); c.close(); d.close()
ok("alter PC: Sicherungen liegen bereit (ZIP, verschlüsselte Kopie, Tagessicherung)", os.path.isfile(ZIP) and os.path.isfile(JRS) and os.path.isfile(TAG_DB), (ZIP, JRS, TAG_DB))
ok("alter Bestand hat eine -wal-Datei (Kopie bei laufendem Programm)", os.path.getsize(QUELLE + "/buero.db-wal") > 0)
ok("die gespeicherten Pfade des alten PCs gibt es nicht mehr", not os.path.exists(anh["pfad"]))

# ================================================================= fremder Bestand (anderes Protokoll)
fremd = PC("fremd", 8796)
ok("fremder Bestand startet", fremd.frisch())
fremd.A("POST", "anmeldung/einrichten", {"name": "Fremd", "login": "fremd", "passwort": "fremd12345", "firma": "Andere Firma"})
fremd.anmelden("fremd", "fremd12345")
fremd_zip = fremd.A("POST", "service/sicherung", {}).get("name")
fremd.stoppen()
ok("fremder Bestand: Sicherung", bool(fremd_zip), fremd_zip)

# ================================================================= neuer PC: Suche, Prüfen, Ablehnungen
neu = PC("neupc", 8797)
ok("neuer PC startet", neu.frisch())
st = neu.A("GET", "anmeldung")
ok("Status: nicht eingerichtet, Übernahme möglich", st.get("eingerichtet") is False and st.get("uebernahme") is True, st)
shutil.copytree(QUELLE, neu.daten + "/daten")                                            # eine Ebene zu tief kopiert
shutil.copytree(QUELLE, f"{Z}/neupc/Jahresring alt/daten")                               # daneben, mit Leerzeichen im Namen
os.makedirs(f"{Z}/neupc/leer/daten"); c = sqlite3.connect(neu.daten + "/buero.db"); d = sqlite3.connect(f"{Z}/neupc/leer/daten/buero.db"); c.backup(d); c.close(); d.close()
shutil.copy2(ZIP, f"{Z}/neupc/")                                                         # vollständige Sicherung
os.makedirs(f"{Z}/neupc/Sicherung/Jahresring-Datenbank"); shutil.copy2(JRS, f"{Z}/neupc/Sicherung/")
shutil.copy2(TAG_DB, f"{Z}/neupc/Sicherung/Jahresring-Datenbank/")
vorher_quelle = baum(f"{Z}/neupc/Jahresring alt/daten")
su = neu.A("GET", "anmeldung/uebernahme"); kand = su.get("kandidaten") or []
arten = [(x["art"], os.path.relpath(x["pfad"], f"{Z}/neupc")) for x in kand]
ok("Suche findet den zu tief kopierten Ordner und den Ordner daneben", ("ordner", "Jahresring/daten/daten") in arten and ("ordner", "Jahresring alt/daten") in arten, arten)
ok("Suche zeigt Firma, Stand und Umfang", all(x["firma"] == "Holzwerkstatt Alt" and x["benutzer"] == 1 and x["kunden"] == ALT["kunden"] and x["stand"] for x in kand if x["art"] == "ordner"), kand)
ok("Suche zeigt den leeren Bestand nicht an und nicht den eigenen Datenordner", not any("leer" in p or p == "Jahresring/daten" for _, p in arten), arten)
ok("Suche findet die vollständige Sicherung, die verschlüsselte und die Datenbanksicherung",
   ("sicherung", sich["name"]) in arten and ("sicherung", "Sicherung/" + sich["name"] + ".jrs") in arten
   and ("datenbank", "Sicherung/Jahresring-Datenbank/" + os.path.basename(TAG_DB)) in arten, arten)
ok("Ordner stehen vor den Sicherungen", [x["art"] for x in kand][:2] == ["ordner", "ordner"], arten)
vz = next(x for x in kand if x["pfad"].endswith(".jrs")); kz = next(x for x in kand if x["pfad"].endswith(sich["name"]))
ok("Sicherung: Version und PC aus der Sicherung, verschlüsselte als solche gekennzeichnet", kz["version"] and kz["rechner"] and vz["verschluesselt"] is True and kz["verschluesselt"] is False, (kz, vz))
ok("Auswahlfenster nur unter Windows", su.get("dialog") is False and neu.A("POST", "anmeldung/uebernahme", {"waehlen": "ordner"}).get("dialog") is False)
P = lambda pfad, **k: neu.A("POST", "anmeldung/uebernahme", {"pfad": pfad, "nur_pruefen": True, **k})
r = P(""); ok("Prüfen ohne Angabe", r["_s"] == 400 and "angeben" in r.get("fehler", ""), r)
r = P(f"{Z}/gibtsnicht"); ok("Prüfen: Ordner gibt es nicht", r["_s"] == 400 and "gibt es nicht" in r.get("fehler", ""), r)
r = P(f"{Z}/ablage"); ok("Prüfen: Ordner ohne buero.db", r["_s"] == 400 and "buero.db fehlt" in r.get("fehler", ""), r)
r = P(f"{Z}/neupc/leer"); ok("Prüfen: leerer Bestand ohne Benutzer", r["_s"] == 400 and "ohne Benutzer" in r.get("fehler", ""), r)
r = P(neu.daten); ok("Prüfen: der eigene Datenordner", r["_s"] == 400 and "Datenordner dieses PCs" in r.get("fehler", ""), r)
r = P(neu.basis); ok("Prüfen: der Programmordner (führt zum eigenen Datenordner)", r["_s"] == 400 and "Datenordner dieses PCs" in r.get("fehler", ""), r)
open(f"{Z}/ablage/notiz.txt", "w").write("x")
r = P(f"{Z}/ablage/notiz.txt"); ok("Prüfen: beliebige Datei", r["_s"] == 400 and "weder" in r.get("fehler", ""), r)
open(f"{Z}/ablage/kaputt.zip", "w").write("kein zip")
r = P(f"{Z}/ablage/kaputt.zip"); ok("Prüfen: beschädigte ZIP-Datei", r["_s"] == 400 and "beschädigt" in r.get("fehler", ""), r)
r = P(f'"{Z}/neupc/Jahresring alt"'); ok("Prüfen: Pfad in Anführungszeichen, Ordner über „daten“", r["_s"] == 200 and r.get("art") == "ordner" and r["pfad"].endswith("Jahresring alt/daten"), r)
r = P(f"{Z}/neupc/Jahresring alt/daten/buero.db"); ok("Prüfen: die Datei buero.db selbst", r["_s"] == 200 and r.get("art") == "ordner", r)
r = P(JRS); ok("Prüfen: verschlüsselte Sicherung", r["_s"] == 200 and r.get("verschluesselt") is True and r.get("art") == "sicherung", r)
r = P(TAG_DB); ok("Prüfen: Datenbanksicherung zeigt den Inhalt", r["_s"] == 200 and r.get("art") == "datenbank" and r.get("firma") == "Holzwerkstatt Alt", r)
# neuere Programmversion und beschädigte Datenbank werden abgelehnt, ohne dass sich hier etwas ändert
shutil.copytree(QUELLE, f"{Z}/ablage/neuer/daten", ignore=shutil.ignore_patterns("backup"))
c = sqlite3.connect(f"{Z}/ablage/neuer/daten/buero.db"); c.execute("UPDATE einstellungen SET wert='\"2099.01.01-1\"' WHERE schluessel='programm_version'"); c.commit(); c.close()
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": f"{Z}/ablage/neuer"}); ok("Bestand aus neuerer Programmversion abgelehnt", r["_s"] == 400 and "neueren Programmversion" in r.get("fehler", ""), r)
os.makedirs(f"{Z}/ablage/kaputt/daten"); roh = open(QUELLE + "/buero.db", "rb").read()
open(f"{Z}/ablage/kaputt/daten/buero.db", "wb").write(roh[:4096] + b"\0" * (len(roh) - 4096))
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": f"{Z}/ablage/kaputt"}); ok("beschädigte Datenbank abgelehnt", r["_s"] == 400 and ("beschädigt" in r.get("fehler", "") or "lesen" in r.get("fehler", "")), r)
ok("nach den Ablehnungen ist der PC unverändert leer", neu.A("GET", "anmeldung").get("uebernahme") is True and not glob.glob(neu.daten + "/protokoll/journal_*"))
ok("Fortschritt abrufbar", neu.A("GET", "anmeldung/uebernahme/stand").get("laeuft") is False)

# ================================================================= Übernahme aus dem Ordner (mit -wal, anderer Ort)
journal_frisch = open(neu.daten + "/protokoll/journal.jsonl", encoding="utf-8").read()
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": f"{Z}/neupc/Jahresring alt"})
ok("Übernahme aus dem Ordner gelingt", r["_s"] == 200 and r.get("ok") and r.get("art") == "ordner" and r.get("firma") == "Holzwerkstatt Alt" and r.get("kunden") == ALT["kunden"], r)
ok("Quelle bleibt unverändert", baum(f"{Z}/neupc/Jahresring alt/daten") == vorher_quelle)
ok("Hinweise: bisherigen PC nicht weiter benutzen; nicht erreichbare Pfade nur wenn zutreffend", any("bisherigen PC" in h for h in r.get("hinweise", [])) and not any("nicht erreichbar" in h for h in r["hinweise"]), r.get("hinweise"))
st = neu.A("GET", "anmeldung"); ok("Status danach: eingerichtet, keine Übernahme mehr", st.get("eingerichtet") is True and "uebernahme" not in st and st.get("firma") == "Holzwerkstatt Alt", st)
r2 = neu.A("POST", "anmeldung/uebernahme", {"pfad": f"{Z}/neupc/Jahresring alt"}); ok("zweite Übernahme abgelehnt", r2["_s"] == 403, r2)
ok("Suche und Prüfen danach gesperrt", neu.A("GET", "anmeldung/uebernahme")["_s"] == 403 and P(QUELLE)["_s"] == 403)
ok("Anmeldung mit dem bisherigen Benutzer und Passwort", neu.anmelden())
pr, bel, ein = neu.protokoll()
ok("Protokoll stimmt (Hash-Kette, Datenbank und Journal)", pr.get("ok") is True, pr)
kette = {x["nr"]: x for x in ein}
ok("die Kette des alten Bestands läuft unverändert weiter", kette.get(ALT["anzahl"], {}).get("hash") == ALT["hash"] and pr["anzahl"] > ALT["anzahl"], (ALT, pr.get("anzahl")))
ueb = [x for x in ein if x["art"] == "uebernahme"]
ok("Protokoll: Übernahme und umgestellte Dateipfade festgehalten", len(ueb) == 2 and any("1 Anhang, 1 Eingangsrechnung." in x["text"] for x in ueb)
   and any("übernommen aus dem Ordner" in x["text"] and "journal_vor_uebernahme_" in x["text"] for x in ueb), [x["text"] for x in ueb])
ok("Belegprüfung stimmt, Eingangsrechnung mitgeprüft", bel.get("ok") is True and bel.get("eingang_geprueft") == 1, bel)
beiseite = glob.glob(neu.daten + "/protokoll/journal_vor_uebernahme_*.jsonl")
ok("das Journal der Erstinstallation ist aufbewahrt, nicht gelöscht", len(beiseite) == 1 and open(beiseite[0], encoding="utf-8").read() == journal_frisch, beiseite)
ok("Zahl der Kunden und Belege wie am alten PC", len(neu.A("GET", "kunden?status=alle")) == ALT["kunden"] and len(neu.A("GET", "belege")) == ALT["belege"])
s, b = neu.roh(f"/api/anhaenge/{anh['id']}/datei"); ok("Anhang lässt sich öffnen (Pfad umgestellt)", s == 200 and b.decode() == "Aufmaß 2,40 m", (s, b[:80]))
s, b = neu.roh(f"/api/zahlungen/{zid}/datei"); ok("Originaldatei der Eingangsrechnung lässt sich öffnen", s == 200 and b == xml, (s, b[:80]))
ok("gespeicherte Pfade zeigen in den Datenordner dieses PCs", neu.db("SELECT pfad FROM anhaenge")[0][0].startswith(neu.daten + "/anhaenge/") and neu.db("SELECT datei FROM zahlungen WHERE id=?", zid)[0][0].startswith(neu.daten + "/eingangsrechnungen/"))
rel = neu.A("GET", "service/relationen"); auff = [x for x in rel.get("pruefungen", []) if x["anzahl"]]
ok("Relationencheck ohne Befund", rel.get("probleme") == 0, auff)
ok("nicht kopiert: Zwischendateien, Browser-Profil, Zertifikat und Meldungen des alten PCs",
   not os.path.exists(neu.daten + "/tmp/rest.txt") and not os.path.exists(neu.daten + "/browser-profil/profil.txt")
   and not os.path.exists(neu.daten + "/zertifikat/ca.pem") and not os.path.exists(neu.daten + "/protokoll.txt"))
ok("alte Sicherungen sind mitgekommen", os.path.isfile(f"{neu.daten}/backup/{sich['name']}"))
heute_db = f"{neu.daten}/backup/buero_{date.today().isoformat()}.db"
c = sqlite3.connect(heute_db); n_b = c.execute("SELECT COUNT(*) FROM benutzer").fetchone()[0]; c.close()
ok("die Tagessicherung von heute enthält den übernommenen Bestand, nicht den leeren", n_b == 1, n_b)
c = sqlite3.connect(f"{neu.daten}/backup/stunde_aktuell.db"); n_b = c.execute("SELECT COUNT(*) FROM benutzer").fetchone()[0]; c.close()
ok("die stündliche Zwischensicherung ebenso", n_b == 1, n_b)
kw = neu.A("GET", "service/sicherungen").get("kennwort"); ok("Sicherungskennwort bleibt gesetzt", kw and kw.get("gesetzt") is True, kw)
n_vor = pr["anzahl"]
neu.stoppen(); ok("Neustart nach der Übernahme", neu.starten() and neu.anmelden())
pr, bel, ein = neu.protokoll()
ok("nach dem Neustart: Protokoll stimmt, Pfade werden nicht noch einmal umgestellt", pr.get("ok") is True and len([x for x in ein if x["art"] == "uebernahme"]) == 2 and bel.get("ok") is True, pr)

# ================================================================= zu tief kopierter Ordner (im eigenen Datenordner)
ok("neuer PC frisch", neu.frisch())
shutil.copytree(QUELLE, neu.daten + "/daten")
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": neu.daten + "/daten"})
ok("Übernahme aus dem zu tief kopierten Ordner", r["_s"] == 200 and r.get("innen") is True and any("kann gelöscht werden" in h and neu.daten + "/daten" in h for h in r.get("hinweise", [])), r)
ok("der Ordner selbst bleibt liegen", os.path.isfile(neu.daten + "/daten/buero.db"))
ok("Anmeldung", neu.anmelden()); pr, bel, _ = neu.protokoll()
ok("Protokoll und Belegprüfung stimmen", pr.get("ok") is True and bel.get("ok") is True, (pr, bel))
s, b = neu.roh(f"/api/anhaenge/{anh['id']}/datei"); ok("Anhang liegt im Datenordner, nicht im Unterordner", s == 200 and neu.db("SELECT pfad FROM anhaenge")[0][0].startswith(neu.daten + "/anhaenge/"), s)

# ================================================================= verschlüsselte Sicherung
ok("neuer PC frisch", neu.frisch())
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": JRS}); ok("verschlüsselte Sicherung ohne Kennwort: Kennwort verlangt", r["_s"] == 428 and "Sicherungskennwort" in r.get("fehler", ""), r)
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": JRS, "kennwort": "falsches Kennwort"}); ok("falsches Kennwort abgelehnt", r["_s"] == 400 and "stimmt nicht" in r.get("fehler", ""), r)
ok("danach unverändert leer", neu.A("GET", "anmeldung").get("uebernahme") is True)
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": JRS, "kennwort": KW})
ok("Übernahme aus der verschlüsselten Sicherung", r["_s"] == 200 and r.get("art") == "sicherung" and r.get("dateien", 0) >= 5, r)
ok("Hinweis: Sicherungskennwort gilt weiter", any("gilt auf diesem PC weiter" in h for h in r.get("hinweise", [])), r.get("hinweise"))
ok("Anmeldung", neu.anmelden()); pr, bel, ein = neu.protokoll()
ok("Protokoll und Belegprüfung stimmen", pr.get("ok") is True and bel.get("ok") is True and bel.get("eingang_geprueft") == 1, (pr, bel))
ok("Protokoll nennt die Sicherung und das Kennwort", any(x["art"] == "uebernahme" and "aus der Sicherung" in x["text"] and "Sicherungskennwort" in x["text"] for x in ein))
kw = neu.A("GET", "service/sicherungen").get("kennwort"); ok("Sicherungskennwort ist auf diesem PC gesetzt und lesbar", kw == {"gesetzt": True, "lesbar": True}, kw)
s, b = neu.roh(f"/api/anhaenge/{anh['id']}/datei"); ok("Anhang aus der Sicherung lässt sich öffnen", s == 200 and b.decode() == "Aufmaß 2,40 m", s)
s, b = neu.roh(f"/api/zahlungen/{zid}/datei"); ok("Eingangsrechnung aus der Sicherung lässt sich öffnen", s == 200 and b == xml, s)

# ================================================================= nur die Datenbank
ok("neuer PC frisch", neu.frisch())
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": TAG_DB})
ok("Übernahme nur der Datenbank", r["_s"] == 200 and r.get("art") == "datenbank" and r.get("dateien") == 0 and "nur die Datenbank" in (r.get("hinweise") or [""])[0], r)
ok("Anmeldung", neu.anmelden()); pr, bel, ein = neu.protokoll()
ok("Protokoll stimmt (Journal aus der Datenbank neu geschrieben)", pr.get("ok") is True and any(x["art"] == "journal" for x in ein), pr)
ok("Belegprüfung meldet die fehlenden Dateien", bel.get("ok") is False, bel)

# ================================================================= vollständige Sicherung; danach derselbe PC nach Datenbankverlust
ok("neuer PC frisch", neu.frisch())
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": ZIP})
ok("Übernahme aus der vollständigen Sicherung", r["_s"] == 200 and r.get("art") == "sicherung" and r.get("journal_alt", "").startswith("journal_vor_uebernahme_"), r)
ok("Hinweis: Sicherungskennwort neu setzen", any("Sicherungskennwort" in h and "neu setzen" in h for h in r.get("hinweise", [])), r.get("hinweise"))
ok("Hinweis: externes Sicherungsziel nur, wenn es fehlt", not any("nicht erreichbar" in h for h in r["hinweise"]), r["hinweise"])
ok("Anmeldung", neu.anmelden()); pr, bel, _ = neu.protokoll()
ok("Protokoll und Belegprüfung stimmen", pr.get("ok") is True and bel.get("ok") is True, (pr, bel))
# im Bestand war ein Sicherungskennwort gesetzt, die unverschlüsselte Sicherung bringt keinen Schlüssel mit: nichts geht unverschlüsselt nach außen
kw = neu.A("GET", "service/sicherungen").get("kennwort"); ok("Sicherungskennwort gilt als gesetzt, aber auf diesem PC nicht lesbar", kw == {"gesetzt": True, "lesbar": False}, kw)
vor_extern = set(os.listdir(f"{Z}/extern"))
s1 = neu.A("POST", "service/sicherung", {}); ok("Sicherung: Kopie aufs externe Ziel unterbleibt mit klarer Meldung", str(s1.get("extern", "")).startswith("FEHLER") and "neu setzen" in s1["extern"], s1)
ok("… und es liegt nichts Unverschlüsseltes dort", set(os.listdir(f"{Z}/extern")) == vor_extern, set(os.listdir(f"{Z}/extern")) - vor_extern)
ok("Kennwort neu setzen ohne das alte", neu.A("POST", "service/kennwort", {"kennwort": KW, "kennwort2": KW}).get("gesetzt") is True and neu.A("GET", "service/sicherungen")["kennwort"] == {"gesetzt": True, "lesbar": True})
s2 = neu.A("POST", "service/sicherung", {}); ok("danach wieder verschlüsselte Kopie", s2.get("verschluesselt") is True and os.path.isfile(f"{Z}/extern/{s2.get('name')}.jrs"), s2)
neu.A("POST", "kunden", {"kurzname": "Nach der Übernahme", "nachname": "Neu", "strasse": "Weg 9", "plz": "88069", "ort": "Tettnang"})
eb = neu.A("POST", "service/echtbetrieb", {"bestaetigung": "ECHTBETRIEB"}); ok("Echtbetrieb begonnen", bool(eb.get("echtbetrieb")), eb)
eigene_sicherung = neu.A("POST", "service/sicherung", {}).get("name")
neu.A("POST", "kunden", {"kurzname": "Nach der Sicherung", "nachname": "Später", "strasse": "Weg 10", "plz": "88069", "ort": "Tettnang"})
pr, _, _ = neu.protokoll(); n_vor = pr["anzahl"]; hash_vor = pr["letzter_hash"]
neu.stoppen()
for x in glob.glob(neu.daten + "/buero.db*"): os.remove(x)      # Datenbank verloren, Journal und Dateien noch da
ok("Neustart ohne Datenbank", neu.starten())
st = neu.A("GET", "anmeldung"); ok("leerer PC mit vorhandenem Journal: Übernahme möglich", st.get("eingerichtet") is False and st.get("uebernahme") is True, st)
shutil.copytree(f"{Z}/fremd/Jahresring/daten", f"{Z}/ablage/fremd/daten")
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": f"{Z}/ablage/fremd"})
ok("fremder Bestand auf einem PC mit Protokoll im Echtbetrieb: abgelehnt", r["_s"] == 409 and "Echtbetrieb" in r.get("fehler", ""), r)
ok("danach unverändert: Journal an seinem Platz, nichts beiseitegelegt", neu.A("GET", "anmeldung").get("uebernahme") is True and len(glob.glob(neu.daten + "/protokoll/journal_vor_uebernahme_*")) == 1)
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": f"{neu.daten}/backup/{eigene_sicherung}"})
ok("eigene Sicherung desselben Protokolls wird übernommen, das Journal bleibt", r["_s"] == 200 and r.get("journal_alt") == "", r)
ok("Anmeldung", neu.anmelden()); pr, bel, ein = neu.protokoll()
ok("Protokoll stimmt; Einträge nach dem Sicherungszeitpunkt sind erhalten", pr.get("ok") is True and pr["anzahl"] > n_vor and {x["nr"]: x for x in ein}.get(n_vor, {}).get("hash") == hash_vor, (pr, n_vor))
ok("Echtbetrieb gilt weiter", bool(neu.A("GET", "service/protokoll").get("echtbetrieb")))
namen = [x["kurzname"] for x in neu.A("GET", "kunden?status=alle")]
ok("Stand der Sicherung: Kunde von vor der Sicherung da, der spätere fehlt", "Nach der Übernahme" in namen and "Nach der Sicherung" not in namen, namen)

# ================================================================= Rücksicherung unter Einstellungen › Service
# im Echtbetrieb: Sicherung aus einem anderen Bestand wird abgelehnt und das festgehalten
shutil.copy2(f"{Z}/fremd/Jahresring/daten/backup/{fremd_zip}", f"{neu.daten}/backup/")
r = neu.A("POST", "service/ruecksichern", {"name": fremd_zip, "grund": "Probe mit fremder Sicherung"})
ok("Echtbetrieb: Sicherung aus einem anderen Bestand abgelehnt", r["_s"] == 400 and "anderen Datenbestand" in r.get("fehler", ""), r)
pr, _, ein = neu.protokoll()
ok("… im Protokoll festgehalten, Protokoll stimmt, Bestand unverändert", pr.get("ok") is True and any(x["art"] == "ruecksicherung" and "nicht ausgeführt" in x["text"] for x in ein)
   and "Nach der Übernahme" in [x["kurzname"] for x in neu.A("GET", "kunden?status=alle")], pr)
r = neu.A("POST", "service/ruecksichern", {"name": eigene_sicherung, "grund": "Probe mit eigener Sicherung"})
ok("Echtbetrieb: eigene Sicherung wird wie bisher zurückgesichert", r["_s"] == 200 and r.get("journal_alt") == "", r)
ok("Anmeldung danach", neu.anmelden()); pr, _, _ = neu.protokoll(); ok("Protokoll stimmt", pr.get("ok") is True, pr)
# der bisher beschriebene Weg nach einem Ausfall: frischer PC, Inhaber anlegen, Sicherung des alten PCs zurücksichern
ok("neuer PC frisch", neu.frisch())
neu.A("POST", "anmeldung/einrichten", {"name": "Neu", "login": "neu", "passwort": "geheim12345", "firma": "X"})
ok("Status mit eigenem Zugang: keine Übernahme mehr", "uebernahme" not in neu.A("GET", "anmeldung") and neu.A("GET", "anmeldung/uebernahme")["_s"] == 403)
neu.anmelden("neu", "geheim12345"); os.makedirs(neu.daten + "/backup", exist_ok=True); shutil.copy2(ZIP, neu.daten + "/backup/")
r = neu.A("POST", "service/ruecksichern", {"name": sich["name"], "grund": "Wiederherstellung nach Ausfall"})
ok("Rücksicherung einer Sicherung des alten PCs auf dem frisch eingerichteten", r["_s"] == 200 and r.get("journal_alt", "").startswith("journal_vor_ruecksicherung_"), r)
ok("Anmeldung mit dem bisherigen Benutzer", neu.anmelden()); pr, bel, ein = neu.protokoll()
ok("Protokoll stimmt jetzt auch auf diesem Weg", pr.get("ok") is True and bel.get("ok") is True, (pr, bel))
ok("Protokoll nennt das beiseitegelegte Journal", any(x["art"] == "ruecksicherung" and "journal_vor_ruecksicherung_" in x["text"] for x in ein))
ok("das Journal des frischen PCs ist aufbewahrt", len(glob.glob(neu.daten + "/protokoll/journal_vor_ruecksicherung_*.jsonl")) == 1)
kw = neu.A("GET", "service/sicherungen").get("kennwort"); ok("auch auf diesem Weg bleibt das Sicherungskennwort verlangt", kw == {"gesetzt": True, "lesbar": False}, kw)
s, b = neu.roh(f"/api/anhaenge/{anh['id']}/datei"); ok("Anhang lässt sich öffnen (Pfad umgestellt)", s == 200, s)

# ================================================================= nur am PC selbst
ok("neuer PC frisch", neu.frisch())
neu.stoppen(); neu.db("INSERT OR REPLACE INTO einstellungen (schluessel, wert) VALUES ('netzwerk', 'true')"); neu.starten()
ip = [x for x in subprocess.run("hostname -I", shell=True, capture_output=True, text=True).stdout.split() if not x.startswith("127.")][:1]
if not ip:
    print("     (kein Netzanschluss in dieser Umgebung – Zugriff von einem anderen Gerät nicht prüfbar)")
else:
    netz = f"http://{ip[0]}:8797"
    st = neu.A("GET", "anmeldung", u=netz); ok("über die Netzwerkadresse: Status ohne Übernahme", st["_s"] == 200 and "uebernahme" not in st, st)
    ok("über die Netzwerkadresse: Suche, Prüfen, Übernahme und Fortschritt abgelehnt",
       [neu.A("GET", "anmeldung/uebernahme", u=netz)["_s"], neu.A("POST", "anmeldung/uebernahme", {"pfad": QUELLE, "nur_pruefen": True}, u=netz)["_s"],
        neu.A("POST", "anmeldung/uebernahme", {"pfad": QUELLE}, u=netz)["_s"], neu.A("GET", "anmeldung/uebernahme/stand", u=netz)["_s"]] == [403] * 4)
    ok("am PC selbst weiter möglich", neu.A("GET", "anmeldung").get("uebernahme") is True)
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": QUELLE}, {"Origin": "http://boese.example"}); ok("Anfrage von einer fremden Seite abgelehnt", r["_s"] == 403, r)
# Hinweise zu nicht erreichbaren Pfaden und zum Netzwerk
shutil.copytree(QUELLE, f"{Z}/ablage/pfade/daten", ignore=shutil.ignore_patterns("backup"))
c = sqlite3.connect(f"{Z}/ablage/pfade/daten/buero.db")
NIE = f"{Z}/ablage/notiz.txt"   # unter einer Datei lässt sich kein Ordner anlegen
for s_, w in (("sicherung_ziel", NIE + "/ziel"), ("projektpfad", NIE + "/projekte"), ("netzwerk", True), ("https", "zusaetzlich")):
    c.execute("INSERT OR REPLACE INTO einstellungen (schluessel, wert) VALUES (?, ?)", (s_, json.dumps(w)))
c.commit(); c.close()
r = neu.A("POST", "anmeldung/uebernahme", {"pfad": f"{Z}/ablage/pfade"}); hw = " | ".join(r.get("hinweise", []))
ok("Hinweise nennen Sicherungsziel, Projektordner, Netzwerk und https", r["_s"] == 200 and NIE + "/ziel" in hw and NIE + "/projekte" in hw and "Netzwerk freigegeben" in hw and "eigenes Zertifikat" in hw, hw)
neu.stoppen()

# ================================================================= Bausteine: Pfade umstellen
sys.path.insert(0, Q)
import uebernahme
ok("Windows-Pfad eines Anhangs", uebernahme._umgesetzt(r"C:\Alt\Jahresring\daten\anhaenge\10001\Plan.pdf", "/n/daten", "anhaenge") == "/n/daten/anhaenge/10001/Plan.pdf")
ok("Ordnername in beliebiger Schreibweise, letzter Treffer zählt", uebernahme._umgesetzt("D:/anhaenge/x/Daten/Anhaenge/L7/a b.pdf", "/n/daten", "anhaenge") == "/n/daten/anhaenge/L7/a b.pdf")
ok("Pfad ohne den Ordner bleibt", uebernahme._umgesetzt(r"C:\Sonstwo\Plan.pdf", "/n/daten", "anhaenge") == "" and uebernahme._umgesetzt("/x/anhaenge/../geheim", "/n", "anhaenge") == "")
ok("Versionsvergleich", uebernahme.version_zahl("2026.11.01-150") > uebernahme.version_zahl("2026.11.01-149") > uebernahme.version_zahl("2026.9.30-999") and uebernahme.version_zahl("x") == ())
d = f"{Z}/ablage/pf"; alt_o = f"{Z}/ablage/pf_alt/daten/anhaenge/10001"; os.makedirs(d + "/anhaenge/10001"); os.makedirs(alt_o)
for name, inhalt in (("da.txt", "x"), ("beide.txt", "gleich"), ("anders.txt", "neu und länger"), ("groesse.txt", "12345")): open(f"{d}/anhaenge/10001/{name}", "w").write(inhalt)
open(alt_o + "/beide.txt", "w").write("gleich"); open(alt_o + "/anders.txt", "w").write("alt"); open(f"{Z}/ablage/liegt.txt", "w").write("x")
c = sqlite3.connect(":memory:"); c.execute("CREATE TABLE anhaenge (id INTEGER PRIMARY KEY, pfad TEXT, groesse INTEGER DEFAULT 0)"); c.execute("CREATE TABLE zahlungen (id INTEGER PRIMARY KEY, datei TEXT)")
c.executemany("INSERT INTO anhaenge (pfad, groesse) VALUES (?, ?)", [
    (r"C:\Alt\daten\anhaenge\10001\da.txt", 1),          # 1 alter Ort fehlt, hier vorhanden, Größe stimmt → umstellen
    (r"C:\Alt\daten\anhaenge\10001\fehlt.txt", 0),       # 2 hier nicht vorhanden → bleibt
    (d + "/anhaenge/10001/da.txt", 1),                      # 3 liegt schon hier → bleibt
    (f"{Z}/ablage/liegt.txt", 1),                           # 4 außerhalb, ohne Ordner anhaenge → bleibt
    ("relativ/anhaenge/10001/da.txt", 1),                   # 5 kein voller Pfad → bleibt
    (alt_o + "/beide.txt", 6),                              # 6 an beiden Orten gleich → umstellen
    (alt_o + "/anders.txt", 0),                             # 7 an beiden Orten, aber verschieden groß → bleibt
    (r"D:\x\anhaenge\10001\groesse.txt", 99)])            # 8 hier vorhanden, gespeicherte Größe passt nicht → bleibt
erg = uebernahme.pfade_anpassen(c, d); pf = [x[0] for x in c.execute("SELECT pfad FROM anhaenge ORDER BY id")]
ok("umgestellt wird nur dieselbe Datei im Datenordner dieses PCs", erg == {"anhaenge": 2} and pf[0] == d + "/anhaenge/10001/da.txt" and pf[5] == d + "/anhaenge/10001/beide.txt"
   and pf[1].startswith("C:") and pf[3].endswith("liegt.txt") and pf[4].startswith("relativ") and pf[6].startswith(alt_o) and pf[7].startswith("D:"), (erg, pf))
ok("zweiter Lauf ändert nichts", uebernahme.pfade_anpassen(c, d) == {})

# Beschreibung über eine Arbeitskopie, wenn SQLite den Pfad als Adresse nicht annimmt (Netzwerkpfad)
echt_p2u = uebernahme.pathname2url
try:
    uebernahme.pathname2url = lambda p: "//nas/freigabe/buero.db"
    b = uebernahme.db_beschreiben(TAG_DB)
    ok("Beschreibung gelingt auch, wenn der Pfad als Adresse nicht taugt", b["benutzer"] == 1 and b["firma"] == "Holzwerkstatt Alt", b)
finally:
    uebernahme.pathname2url = echt_p2u
# Journal tauschen: schlägt das Einsetzen fehl, liegt das bisherige wieder an seinem Platz
import protokoll
jo = f"{Z}/ablage/jo"; os.makedirs(jo); open(jo + "/journal.jsonl", "w").write('{"nr": 1, "hash": "a"}\n')
merk = dict(protokoll._pfad); protokoll._pfad["datei"] = jo + "/journal.jsonl"
try:
    try:
        protokoll.journal_ersetzen(f"{Z}/ablage", "probe"); gescheitert = False      # ein Ordner lässt sich nicht als Datei einsetzen
    except OSError:
        gescheitert = True
    ok("gescheiterter Journaltausch: bisheriges Journal unverändert, nichts beiseitegelegt", gescheitert and open(jo + "/journal.jsonl").read() == '{"nr": 1, "hash": "a"}\n' and os.listdir(jo) == ["journal.jsonl"], os.listdir(jo))
    open(f"{Z}/ablage/neues_journal.jsonl", "w").write('{"nr": 1, "hash": "b"}\n')
    name, n = protokoll.journal_ersetzen(f"{Z}/ablage/neues_journal.jsonl", "probe")
    ok("Journaltausch: neues eingesetzt, bisheriges unter eigenem Namen aufbewahrt", n == 1 and name.startswith("journal_probe_") and open(f"{jo}/{name}").read().count('"a"') == 1 and '"b"' in open(jo + "/journal.jsonl").read(), (name, n))
    protokoll.journal_zurueck(name)
    ok("Tausch zurücknehmen: bisheriges Journal wieder an seinem Platz", os.listdir(jo) == ["journal.jsonl"] and '"a"' in open(jo + "/journal.jsonl").read(), os.listdir(jo))
finally:
    protokoll._pfad.update(merk)

# ================================================================= Bausteine für Windows (hier nur die eigene Logik, mit nachgestellten Windows-Aufrufen)
import ctypes, types, subprocess as sp
class _K32:
    def GetLogicalDrives(self): return 0b1011100                      # C, D, E, G
    def GetDriveTypeW(self, w): return {"C:\\": 3, "D:\\": 5, "E:\\": 2, "G:\\": 4}[w.value]   # fest, CD, wechselbar, Netz
    def SetErrorMode(self, m): return 0
class _Reg:
    HKEY_CURRENT_USER = 1
    class _Schl:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    def OpenKey(self, *a): return self._Schl()
    def QueryValueEx(self, k, name):
        if name == "Personal": raise OSError("fehlt")
        return ({"Desktop": "/verlegt/Desktop", "{374DE290-123F-4565-9164-39C4925E467B}": "/verlegt/Downloads"}[name], 1)
ctypes.windll = types.SimpleNamespace(kernel32=_K32()); sys.modules["winreg"] = _Reg()
echt_run = sp.run
try:
    os.name = "nt"
    ok("Laufwerke: wechselbare und feste getrennt, CD- und Netzlaufwerke bleiben aus", uebernahme._laufwerke() == (["E:\\"], ["C:\\"]), uebernahme._laufwerke())
    eo = uebernahme._eigene_ordner()
    ok("verlegte Ordner Desktop und Downloads aus der Registrierung, fehlender Eintrag stört nicht", "/verlegt/Desktop" in eo and "/verlegt/Downloads" in eo and len(eo) == 6, eo)
    aufrufe = []
    def nach(cmd, **k):
        aufrufe.append((cmd, k)); return types.SimpleNamespace(stdout=("Hinweis\r\nJR:" + base64.b64encode("E:\\Büro alt\\daten".encode()).decode() + "\r\n").encode("ascii"))
    sp.run = nach
    ok("Auswahlfenster: gewählter Pfad mit Umlaut und Leerzeichen kommt unverändert an", uebernahme.auswahl_dialog("ordner") == "E:\\Büro alt\\daten")
    cmd, k = aufrufe[-1]
    ok("Auswahlfenster: PowerShell ohne Fenster, Befehl nur aus Grundzeichen, Texte über die Umgebung", cmd[0] == "powershell" and cmd[-1].isascii() and "FolderBrowserDialog" in cmd[-1]
       and k["env"]["JR_ART"] == "ordner" and "daten" in k["env"]["JR_TITEL"] and k.get("timeout") and k.get("stdin") == sp.DEVNULL, (cmd[:5], sorted(k)))
    uebernahme.auswahl_dialog("datei"); ok("Auswahlfenster für die Sicherungsdatei", aufrufe[-1][1]["env"]["JR_ART"] == "datei" and "*.jrs" in aufrufe[-1][1]["env"]["JR_FILTER"])
    sp.run = lambda cmd, **k: types.SimpleNamespace(stdout=b"JR:\r\n")
    ok("Auswahlfenster abgebrochen: leerer Pfad", uebernahme.auswahl_dialog("ordner") == "")
    def kaputt(cmd, **k): raise FileNotFoundError("powershell")
    sp.run = kaputt
    ok("Auswahlfenster nicht verfügbar: None statt Fehler", uebernahme.auswahl_dialog("ordner") is None)
    sp.run = lambda cmd, **k: types.SimpleNamespace(stdout=b"irgendein Fehlertext")
    ok("Auswahlfenster ohne verwertbare Antwort: None", uebernahme.auswahl_dialog("ordner") is None)
finally:
    os.name = "posix"; sp.run = echt_run; del sys.modules["winreg"]
ok("ohne Windows: kein Auswahlfenster, keine Laufwerksliste", uebernahme.auswahl_dialog("ordner") is None and uebernahme._laufwerke() == ([], []))

for pc in (alt, fremd, neu):
    pc.stoppen()
print("FEHLER:", fehler)
