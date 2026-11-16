"""Arbeitsschutz: Gefährdungsbeurteilungen, Betriebsanweisungen, Unterweisungen, Gefahrstoffe mit Datenblättern,
Erste Hilfe (Notfall-Aushang, Verbandbuch) sowie Beauftragte und Nachweise.

Grundlage sind die Vorlagen der Berufsgenossenschaft (arbeitsschutz_vorlagen.json): Gefährdungsbeurteilungen je
Arbeitsplatz/Maschine, Unterweisungsinhalte, Checkliste psychische Belastung. Freigaben und Unterweisungen werden am
Tablet unterschrieben (unterschrift.py); eine freigegebene Fassung bleibt unverändert gespeichert.
"""
import base64
import kern
import hashlib
import html
import json
import math
import os
import re
import secrets
from datetime import date, datetime, timedelta

import unterschrift

SCHEMA = """
CREATE TABLE IF NOT EXISTS as_daten (schluessel TEXT PRIMARY KEY, wert TEXT);
CREATE TABLE IF NOT EXISTS as_dateien (
    id INTEGER PRIMARY KEY AUTOINCREMENT, art TEXT DEFAULT 'sdb', titel TEXT DEFAULT '', dateiname TEXT DEFAULT '', pfad TEXT DEFAULT '',
    groesse INTEGER DEFAULT 0, sha256 TEXT DEFAULT '', material_id INTEGER, werkzeug_id INTEGER, qualifikation_id INTEGER,
    ausgabe TEXT DEFAULT '', aktuell INTEGER DEFAULT 1, angelegt TEXT, von TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS as_dateien_mat ON as_dateien(material_id);
CREATE TABLE IF NOT EXISTS as_gefahrstoffe (
    material_id INTEGER PRIMARY KEY, gefahrstoff INTEGER DEFAULT 1, ghs TEXT DEFAULT '[]', signalwort TEXT DEFAULT '',
    h_saetze TEXT DEFAULT '', p_saetze TEXT DEFAULT '', lagerklasse TEXT DEFAULT '', wgk TEXT DEFAULT '', menge TEXT DEFAULT '',
    bereich TEXT DEFAULT '', psa TEXT DEFAULT '', ersatz TEXT DEFAULT '', bemerkung TEXT DEFAULT '', geaendert TEXT);
CREATE TABLE IF NOT EXISTS as_gb (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nummer TEXT UNIQUE, titel TEXT DEFAULT '', art TEXT DEFAULT 'bereich', bereich TEXT DEFAULT '',
    werkzeug_ids TEXT DEFAULT '[]', vorlagen TEXT DEFAULT '[]', status TEXT DEFAULT 'entwurf', stand TEXT DEFAULT '', naechste TEXT DEFAULT '',
    intervall INTEGER DEFAULT 12, beteiligte TEXT DEFAULT '', mitgeltend TEXT DEFAULT '', bemerkung TEXT DEFAULT '', zeilen TEXT DEFAULT '[]',
    angelegt TEXT, geaendert TEXT);
CREATE TABLE IF NOT EXISTS as_ba (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nummer TEXT UNIQUE, titel TEXT DEFAULT '', art TEXT DEFAULT 'maschine', bereich TEXT DEFAULT '',
    werkzeug_ids TEXT DEFAULT '[]', material_id INTEGER, vorlage TEXT DEFAULT '', abschnitte TEXT DEFAULT '{}', symbole TEXT DEFAULT '[]',
    status TEXT DEFAULT 'entwurf', stand TEXT DEFAULT '', angelegt TEXT, geaendert TEXT);
CREATE TABLE IF NOT EXISTS as_fassungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT, art TEXT, bezug_id INTEGER, nr INTEGER, stand TEXT, inhalt TEXT, sha256 TEXT,
    signatur_id INTEGER, freigegeben_von TEXT, freigegeben_am TEXT);
CREATE TABLE IF NOT EXISTS as_themen (
    id INTEGER PRIMARY KEY AUTOINCREMENT, titel TEXT DEFAULT '', gruppe TEXT DEFAULT '', vorlage TEXT DEFAULT '', uwh TEXT DEFAULT '',
    abschnitte TEXT DEFAULT '[]', intervall INTEGER DEFAULT 12, alle INTEGER DEFAULT 1, mitarbeiter_ids TEXT DEFAULT '[]',
    werkzeug_ids TEXT DEFAULT '[]', ba_ids TEXT DEFAULT '[]', aktiv INTEGER DEFAULT 1, angelegt TEXT, geaendert TEXT);
CREATE TABLE IF NOT EXISTS as_unterweisungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nummer TEXT UNIQUE, datum TEXT, titel TEXT DEFAULT '', thema_ids TEXT DEFAULT '[]',
    anlass TEXT DEFAULT '', ort TEXT DEFAULT '', unterweiser TEXT DEFAULT '', inhalt TEXT DEFAULT '[]', ergaenzung TEXT DEFAULT '',
    verstaendnis TEXT DEFAULT '', dauer TEXT DEFAULT '', status TEXT DEFAULT 'offen', abgeschlossen TEXT DEFAULT '', angelegt TEXT, von TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS as_teilnehmer (
    id INTEGER PRIMARY KEY AUTOINCREMENT, unterweisung_id INTEGER NOT NULL, mitarbeiter_id INTEGER, name TEXT DEFAULT '',
    signatur_id INTEGER, unterschrieben TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS as_teilnehmer_u ON as_teilnehmer(unterweisung_id);
CREATE TABLE IF NOT EXISTS as_qualifikationen (
    id INTEGER PRIMARY KEY AUTOINCREMENT, mitarbeiter_id INTEGER, name TEXT DEFAULT '', art TEXT DEFAULT '', datum TEXT DEFAULT '',
    gueltig_bis TEXT DEFAULT '', bemerkung TEXT DEFAULT '', angelegt TEXT);
CREATE TABLE IF NOT EXISTS as_verbandbuch (
    id INTEGER PRIMARY KEY AUTOINCREMENT, zeit TEXT, ort TEXT DEFAULT '', name TEXT DEFAULT '', hergang TEXT DEFAULT '',
    verletzung TEXT DEFAULT '', zeugen TEXT DEFAULT '', hilfe_zeit TEXT DEFAULT '', massnahmen TEXT DEFAULT '', helfer TEXT DEFAULT '',
    angelegt TEXT, von TEXT DEFAULT '');
"""

GB_ARTEN = {"bereich": "Arbeitsbereich", "maschine": "Maschine / Arbeitsmittel", "taetigkeit": "Tätigkeit", "psychisch": "Psychische Belastung"}
GB_STATUS = {"entwurf": "Entwurf", "gueltig": "gültig", "ueberarbeitung": "in Überarbeitung", "archiv": "archiviert"}
BA_ARTEN = {"maschine": "Maschine / Arbeitsmittel", "gefahrstoff": "Gefahrstoff", "taetigkeit": "Tätigkeit"}
BA_ABSCHNITTE = {
    "maschine": [("anwendung", "Anwendungsbereich"), ("gefahren", "Gefahren für Mensch und Umwelt"), ("schutz", "Schutzmaßnahmen und Verhaltensregeln"),
                 ("stoerung", "Verhalten bei Störungen"), ("erstehilfe", "Verhalten bei Unfällen – Erste Hilfe"), ("instandhaltung", "Instandhaltung, Entsorgung")],
    "gefahrstoff": [("anwendung", "Anwendungsbereich"), ("stoff", "Gefahrstoffbezeichnung"), ("gefahren", "Gefahren für Mensch und Umwelt"),
                    ("schutz", "Schutzmaßnahmen und Verhaltensregeln"), ("gefahrfall", "Verhalten im Gefahrfall"), ("erstehilfe", "Erste Hilfe"),
                    ("entsorgung", "Sachgerechte Entsorgung")],
}
BA_ABSCHNITTE["taetigkeit"] = BA_ABSCHNITTE["maschine"]
DATEI_ARTEN = {"sdb": "Sicherheitsdatenblatt", "tdb": "Technisches Merkblatt", "ba": "Betriebsanleitung des Herstellers", "pruef": "Prüfnachweis",
               "nachweis": "Nachweis / Zertifikat", "sonst": "Sonstiges"}
QUALI = {"Ersthelfer": 24, "Brandschutzhelfer": 36, "Sicherheitsbeauftragter": 0, "Fahrausweis Flurförderzeuge": 0, "Hubarbeitsbühne (Bedienerausweis)": 0,
         "Befähigte Person Leitern und Tritte": 0, "Prüfung elektrischer Betriebsmittel": 0, "PSA gegen Absturz": 0, "Sonstiges": 0}
LAGERKLASSEN = ["1", "2A", "2B", "3", "4.1A", "4.1B", "4.2", "4.3", "5.1A", "5.1B", "5.1C", "5.2", "6.1A", "6.1B", "6.1C", "6.1D", "6.2", "7",
                "8A", "8B", "10", "11", "12", "13"]
WGK = ["nwg", "WGK 1", "WGK 2", "WGK 3"]
SIGNALWORTE = ["", "Achtung", "Gefahr"]
GHS_AUS_H = [(r"^H2(0|1)", "GHS01"), (r"^H22[0-8]|^H24[12]|^H25[0-2]|^H26[01]", "GHS02"), (r"^H27[0-2]", "GHS03"), (r"^H28[01]", "GHS04"),
             (r"^H290|^H314|^H318", "GHS05"), (r"^H30[01]|^H31[01]|^H33[01]", "GHS06"), (r"^H30[2]|^H31[25-7]|^H319|^H33[2,5,6]", "GHS07"),
             (r"^H304|^H334|^H34[01]|^H35[01]|^H36[01]|^H37[0-3]", "GHS08"), (r"^H400|^H41[01]", "GHS09")]
PLATZHALTER = "[aus SDB"
MASCHINE_STOERUNG = ["Bei Störungen Maschine ausschalten und gegen Wiedereinschalten sichern.",
                     "Störungen nur durch beauftragte und unterwiesene Personen beseitigen lassen.",
                     "Schäden an Schutzeinrichtungen sofort den Vorgesetzten melden; Maschine bis zur Instandsetzung nicht benutzen."]
MASCHINE_ERSTEHILFE = ["Maschine abschalten, Ruhe bewahren.", "Ersthelfer verständigen, Erste Hilfe leisten.", "Notruf 112 (Wo? Was? Wie viele Verletzte? Welche Verletzungen? Warten auf Rückfragen).",
                       "Unfall den Vorgesetzten melden, Eintrag ins Verbandbuch."]
MASCHINE_INSTANDHALTUNG = ["Instandhaltung nur durch beauftragte und unterwiesene Personen nach Betriebsanleitung des Herstellers.",
                           "Vor Arbeiten Maschine freischalten und gegen Wiedereinschalten sichern.",
                           "Regelmäßige Prüfung der Maschine und der Schutzeinrichtungen; Späne und Abfälle sachgerecht entsorgen."]


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def h(s):
    return html.escape(str(s if s is not None else ""))


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def jl(s, std):
    try:
        v = json.loads(s) if isinstance(s, str) and s else std
        return v if isinstance(v, type(std)) else std
    except ValueError:
        return std


def de_datum(iso):
    iso = str(iso or "")
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if len(iso) >= 10 else ""


def monate_plus(iso, n):
    d = date.fromisoformat(iso[:10])
    m = d.month - 1 + int(n)
    j, m = d.year + m // 12, m % 12 + 1
    tag = min(d.day, [31, 29 if j % 4 == 0 and (j % 100 or j % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date(j, m, tag).isoformat()


def datum_ok(v):
    v = str(v or "").strip()[:10]
    if not v:
        return ""
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        raise Fehler(f"Ungültiges Datum: {v}")


def neue_id():
    return secrets.token_hex(4)


def ids_liste(v):
    if isinstance(v, str):
        v = jl(v, [])
    return [int(x) for x in (v or []) if str(x).lstrip("-").isdigit()]


_VORLAGEN = {}


def vorlagen():
    if not _VORLAGEN:
        pfad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arbeitsschutz_vorlagen.json")
        with open(pfad, encoding="utf-8") as f:
            _VORLAGEN.update(json.load(f))
    return _VORLAGEN


def schema(con):
    con.executescript(SCHEMA)


# ---------------------------------------------------------------- Einstellungen des Bereichs
ORG_STANDARD = {"betreuung": "", "betreuung_seit": "", "fasi": "", "betriebsarzt": "", "sibe": "", "bg": "", "bg_nr": "", "bereiche": [],
                "vorsorge": "", "pruefung_elektro": "", "hinweis": ""}


def daten_lesen(con, key, std):
    r = con.execute("SELECT wert FROM as_daten WHERE schluessel=?", (key,)).fetchone()
    v = jl(r["wert"], type(std)()) if r else type(std)()
    return {**std, **v} if isinstance(std, dict) else (v or std)


def daten_schreiben(con, key, wert):
    con.execute("INSERT OR REPLACE INTO as_daten (schluessel, wert) VALUES (?, ?)", (key, json.dumps(wert, ensure_ascii=False)))


def organisation(con):
    o = daten_lesen(con, "organisation", ORG_STANDARD)
    o["bereiche"] = [str(b).strip() for b in (o.get("bereiche") or []) if str(b).strip()]
    return o


def notfall(con):
    return daten_lesen(con, "notfall", {k: "" for k, _ in vorlagen()["notfall"]})


# ---------------------------------------------------------------- Personen
def mitarbeiter_liste(con, alle=False):
    heute = date.today().isoformat()
    spalten = {r[1] for r in con.execute("PRAGMA table_info(mitarbeiter)")}
    geb = "geburtsdatum" if "geburtsdatum" in spalten else "'' AS geburtsdatum"
    zeilen = con.execute(f"SELECT id, nummer, vorname, nachname, kuerzel, eintritt, austritt, aktiv, lohnart, {geb} FROM mitarbeiter ORDER BY nachname, vorname").fetchall()
    aus = []
    for m in zeilen:
        aktiv = m["aktiv"] and (not m["austritt"] or m["austritt"] >= heute)
        if not alle and not aktiv:
            continue
        d = dict(m)
        d["name"] = f"{m['vorname']} {m['nachname']}".strip()
        d["inhaber"] = m["lohnart"] == "inhaber"
        d["jugendlich"] = jugendlich(m["geburtsdatum"])
        d["aktiv"] = bool(aktiv)
        aus.append(d)
    return aus


def jugendlich(geburtsdatum, stichtag=None):
    g = str(geburtsdatum or "")[:10]
    if len(g) < 10:
        return False
    try:
        gd = date.fromisoformat(g)
    except ValueError:
        return False
    s = stichtag or date.today()
    alter = s.year - gd.year - ((s.month, s.day) < (gd.month, gd.day))
    return alter < 18


def beschaeftigte(con):
    """Wer unterwiesen werden muss: aktive Mitarbeiter, die eingetreten sind (ohne Inhaber)."""
    heute = date.today().isoformat()
    return [m for m in mitarbeiter_liste(con) if not m["inhaber"] and (not m["eintritt"] or m["eintritt"] <= heute)]


# ---------------------------------------------------------------- Dateien (Datenblätter, Nachweise)
def dateien_ordner(daten):
    return os.path.join(daten, "arbeitsschutz", "dateien")


def datei_info(r):
    d = dict(r)
    d.pop("pfad", None)
    d["art_name"] = DATEI_ARTEN.get(d["art"], d["art"])
    return d


def dateien(con, q):
    sql, p = "SELECT * FROM as_dateien WHERE 1=1", []
    for k, sp in (("material", "material_id"), ("werkzeug", "werkzeug_id"), ("qualifikation", "qualifikation_id")):
        if q.get(k):
            sql += f" AND {sp}=?"
            p.append(int(q[k]))
    return [datei_info(r) for r in con.execute(sql + " ORDER BY aktuell DESC, art, COALESCE(NULLIF(ausgabe,''), angelegt) DESC, id DESC", p)]


def datei_hochladen(con, daten, d, wer):
    name = os.path.basename(str(d.get("dateiname") or "").replace("\\", "/")).strip() or "Datei.pdf"
    endung = os.path.splitext(name)[1].lower()
    if endung not in (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".txt", ".doc", ".docx", ".xls", ".xlsx"):
        raise Fehler("Bitte eine PDF- oder Bilddatei hochladen.")
    try:
        roh = base64.b64decode(str(d.get("daten") or ""), validate=False)
    except (ValueError, TypeError):
        raise Fehler("Die Datei konnte nicht gelesen werden.")
    if not roh:
        raise Fehler("Die Datei ist leer.")
    if len(roh) > 60 * 1024 * 1024:
        raise Fehler("Die Datei ist zu groß (höchstens 60 MB).", 413)
    art = d.get("art") if d.get("art") in DATEI_ARTEN else "sonst"
    mid = int(d["material_id"]) if str(d.get("material_id") or "").isdigit() else None
    wid = int(d["werkzeug_id"]) if str(d.get("werkzeug_id") or "").isdigit() else None
    qid = int(d["qualifikation_id"]) if str(d.get("qualifikation_id") or "").isdigit() else None
    if not (mid or wid or qid):
        raise Fehler("Die Datei gehört zu keinem Material, Werkzeug oder Nachweis.")
    if mid and not con.execute("SELECT 1 FROM material WHERE id=?", (mid,)).fetchone():
        raise Fehler("Material nicht gefunden.", 404)
    if wid and not con.execute("SELECT 1 FROM werkzeuge WHERE id=?", (wid,)).fetchone():
        raise Fehler("Werkzeug nicht gefunden.", 404)
    ordner = dateien_ordner(daten)
    os.makedirs(ordner, exist_ok=True)
    sha = hashlib.sha256(roh).hexdigest()
    ziel = os.path.join(ordner, f"{date.today().isoformat()}_{sha[:12]}{endung}")
    with open(ziel, "wb") as f:
        f.write(roh)
    ausgabe = datum_ok(d.get("ausgabe"))
    # eine neue Fassung des Sicherheitsdatenblatts/Merkblatts löst die bisherige ab (die alte bleibt als frühere Fassung erhalten)
    if mid and art in ("sdb", "tdb"):
        con.execute("UPDATE as_dateien SET aktuell=0 WHERE material_id=? AND art=? AND aktuell=1", (mid, art))
    titel = str(d.get("titel") or "").strip() or os.path.splitext(name)[0]
    fid = con.execute("INSERT INTO as_dateien (art, titel, dateiname, pfad, groesse, sha256, material_id, werkzeug_id, qualifikation_id, ausgabe, aktuell, angelegt, von) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?)", (art, titel[:200], name[:200], os.path.basename(ziel), len(roh), sha, mid, wid, qid, ausgabe, jetzt(), wer)).lastrowid
    return datei_info(con.execute("SELECT * FROM as_dateien WHERE id=?", (fid,)).fetchone())


def datei_pfad(con, daten, fid):
    r = con.execute("SELECT * FROM as_dateien WHERE id=?", (fid,)).fetchone()
    if not r:
        raise Fehler("Datei nicht gefunden.", 404)
    pfad = os.path.join(dateien_ordner(daten), os.path.basename(r["pfad"]))
    if not os.path.exists(pfad):
        raise Fehler("Die Datei fehlt im Datenordner.", 404)
    return r, pfad


# ---------------------------------------------------------------- Gefahrstoffe
def h_codes(text):
    return [c.upper() for c in re.findall(r"\b(EUH\s?\d{3}|H\d{3}[A-Za-z]{0,2})\b", str(text or ""), re.I)]


def ghs_vorschlag(h_saetze):
    aus = []
    for c in h_codes(h_saetze):
        for muster, g in GHS_AUS_H:
            if re.match(muster.replace(",", ""), c) and g not in aus:
                aus.append(g)
    if "GHS05" in aus and "GHS07" in aus and any(c in ("H315", "H319") for c in h_codes(h_saetze)) and not any(c in ("H302", "H312", "H332", "H317", "H335", "H336") for c in h_codes(h_saetze)):
        aus.remove("GHS07")   # Reizung neben Ätzwirkung: Ausrufezeichen entfällt
    return sorted(aus)


def gefahrstoff(con, mid):
    r = con.execute("SELECT * FROM as_gefahrstoffe WHERE material_id=?", (mid,)).fetchone()
    d = dict(r) if r else {"material_id": mid, "gefahrstoff": 0, "ghs": "[]", "signalwort": "", "h_saetze": "", "p_saetze": "", "lagerklasse": "", "wgk": "",
                           "menge": "", "bereich": "", "psa": "", "ersatz": "", "bemerkung": "", "geaendert": ""}
    d["ghs"] = jl(d["ghs"], [])
    return d


def gefahrstoff_speichern(con, mid, d):
    if not con.execute("SELECT 1 FROM material WHERE id=?", (mid,)).fetchone():
        raise Fehler("Material nicht gefunden.", 404)
    alt = gefahrstoff(con, mid)
    neu = dict(alt)
    for k in ("signalwort", "h_saetze", "p_saetze", "lagerklasse", "wgk", "menge", "bereich", "psa", "ersatz", "bemerkung"):
        if k in d:
            neu[k] = str(d[k] or "").strip()[:2000]
    if "gefahrstoff" in d:
        neu["gefahrstoff"] = 1 if d["gefahrstoff"] in (1, True, "1", "true") else 0
    if "ghs" in d:
        neu["ghs"] = [g for g in (d["ghs"] if isinstance(d["ghs"], list) else []) if re.fullmatch(r"GHS0[1-9]", str(g))]
    if neu["signalwort"] not in SIGNALWORTE:
        raise Fehler("Signalwort bitte „Achtung“ oder „Gefahr“.")
    con.execute("INSERT OR REPLACE INTO as_gefahrstoffe (material_id, gefahrstoff, ghs, signalwort, h_saetze, p_saetze, lagerklasse, wgk, menge, bereich, psa, ersatz, bemerkung, geaendert) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (mid, neu["gefahrstoff"], json.dumps(neu["ghs"]), neu["signalwort"], neu["h_saetze"], neu["p_saetze"], neu["lagerklasse"],
                                                         neu["wgk"], neu["menge"], neu["bereich"], neu["psa"], neu["ersatz"], neu["bemerkung"], jetzt()))
    return gefahrstoff(con, mid)


def aktuelle_datei(con, mid, art):
    r = con.execute("SELECT * FROM as_dateien WHERE material_id=? AND art=? AND aktuell=1 ORDER BY id DESC LIMIT 1", (mid, art)).fetchone()
    return datei_info(r) if r else None


def ba_zu_material(con, mid):
    r = con.execute("SELECT id, nummer, titel, status FROM as_ba WHERE material_id=? AND status<>'archiv' ORDER BY (status='gueltig') DESC, id DESC LIMIT 1", (mid,)).fetchone()
    return dict(r) if r else None


def verzeichnis(con):
    """Gefahrstoffverzeichnis (§ 6 Abs. 12 GefStoffV)."""
    aus = []
    for r in con.execute("SELECT g.*, m.nummer, m.bezeichnung, m.kategorie, m.aktiv, l.kurzname AS lieferant FROM as_gefahrstoffe g JOIN material m ON m.id=g.material_id "
                         "LEFT JOIN lieferanten l ON l.id=m.lieferant_id WHERE g.gefahrstoff=1 AND IFNULL(m.aktiv,1)=1 ORDER BY m.bezeichnung"):
        d = dict(r)
        d["ghs"] = jl(d["ghs"], [])
        d["name"] = (d["bezeichnung"] or "").split("\n")[0]
        d["sdb"] = aktuelle_datei(con, d["material_id"], "sdb")
        d["tdb"] = aktuelle_datei(con, d["material_id"], "tdb")
        d["ba"] = ba_zu_material(con, d["material_id"])
        aus.append(d)
    return aus


def material_sicherheit(con, mid):
    """Alles zu einem Material: Gefahrstoffangaben, Datenblätter, Betriebsanweisung."""
    return {"gefahrstoff": gefahrstoff(con, mid), "dateien": dateien(con, {"material": mid}), "ba": ba_zu_material(con, mid),
            "auswahl": {"lagerklassen": LAGERKLASSEN, "wgk": WGK, "signalworte": SIGNALWORTE[1:], "datei_arten": DATEI_ARTEN},
            "ghs_vorschlag": None}


def auftrag_materialien(con, nummern, ids):
    """Gefahrstoffe und Datenblätter der Materialien eines Auftrags (für die Werkstatt)."""
    mids = set(int(i) for i in ids if i)
    if nummern:
        ph = ",".join("?" * len(nummern))
        mids |= {r["id"] for r in con.execute(f"SELECT id FROM material WHERE nummer IN ({ph})", list(nummern))}
    aus = []
    for mid in sorted(mids):
        m = con.execute("SELECT id, nummer, bezeichnung FROM material WHERE id=?", (mid,)).fetchone()
        if not m:
            continue
        g = gefahrstoff(con, mid)
        dat = [x for x in dateien(con, {"material": mid}) if x["aktuell"] and x["art"] in ("sdb", "tdb")]
        ba = ba_zu_material(con, mid)
        if not (g["gefahrstoff"] or dat or ba):
            continue
        aus.append({"id": mid, "nummer": m["nummer"], "name": (m["bezeichnung"] or "").split("\n")[0], "gefahrstoff": bool(g["gefahrstoff"]),
                    "ghs": g["ghs"], "signalwort": g["signalwort"], "psa": g["psa"], "dateien": dat, "ba": ba if ba and ba["status"] == "gueltig" else None})
    aus.sort(key=lambda x: (not x["gefahrstoff"], x["name"]))
    return aus


def links_je_nummer(con):
    """Materialnummer → {sdb, tdb, ba, gefahrstoff} für die Werkstattpapiere."""
    aus = {}
    for r in con.execute("SELECT d.id, d.art, m.nummer FROM as_dateien d JOIN material m ON m.id=d.material_id WHERE d.aktuell=1 AND d.art IN ('sdb','tdb') ORDER BY d.id"):
        aus.setdefault(r["nummer"], {})[r["art"]] = r["id"]
    for r in con.execute("SELECT g.material_id, g.ghs, m.nummer FROM as_gefahrstoffe g JOIN material m ON m.id=g.material_id WHERE g.gefahrstoff=1"):
        aus.setdefault(r["nummer"], {})["gefahrstoff"] = jl(r["ghs"], []) or True
    for r in con.execute("SELECT b.id, m.nummer FROM as_ba b JOIN material m ON m.id=b.material_id WHERE b.status='gueltig'"):
        aus.setdefault(r["nummer"], {})["ba"] = r["id"]
    return aus


# ---------------------------------------------------------------- Gefährdungsbeurteilungen
P_WORTE = ("gehörschutz", "schutzbrille", "augenschutz", "handschuh", "sicherheitsschuh", "schutzschuh", "atemschutz", "schutzkleidung", "schürze",
           "schutzhelm", "psa", "hautschutz", "warnweste", "auffanggurt", "gesichtsschutz", "persönliche schutz")
O_WORTE = ("unterweis", "betriebsanweisung", "prüf", "beauftrag", "vorsorge", "organis", "erlaubnis", "festleg", "dokumentier", "kennzeichn",
           "regelmäßig", "anweis", "schulung", "ausbild", "informier", "freigabe", "zugelassen", "nur von", "nur durch", "plan", "verbot", "rauchverbot")


def top_raten(text):
    t = str(text or "").lower()
    if any(w in t for w in P_WORTE):
        return "P"
    if any(w in t for w in O_WORTE):
        return "O"
    return "T"


def massnahme(text, art=None):
    return {"id": neue_id(), "t": str(text or "").strip(), "art": art or top_raten(text), "status": "offen", "wer": "", "bis": "", "erledigt": "",
            "wirksam": 0, "wirksam_am": "", "wirksam_wer": ""}


def zeilen_aus_vorlage(vid):
    v = next((x for x in vorlagen()["gb"] if x["id"] == vid), None)
    if not v:
        raise Fehler("Vorlage nicht gefunden.", 404)
    return [{"id": neue_id(), "g": g["g"], "risiko": "", "quelle": v["name"], "m": [massnahme(t) for t in g["m"]]} for g in v["gef"]], v


def zeilen_psychisch():
    aus = []
    for b in vorlagen()["psych"]:
        for m in b["merkmale"]:
            for p in m["punkte"]:
                aus.append({"id": neue_id(), "gruppe": f"{b['bereich']} › {m['merkmal']}", "g": p["text"], "auto": 1 if p["auto"] else 0,
                            "trifft": None, "risiko": "", "hinweis": m["massnahmen"], "m": []})
    return aus


def naechste_nummer(con, tabelle, praefix):
    n = 0
    for r in con.execute(f"SELECT nummer FROM {tabelle} WHERE nummer LIKE ?", (praefix + "%",)):
        tail = r["nummer"][len(praefix):]
        if tail.isdigit():
            n = max(n, int(tail))
    return f"{praefix}{n + 1:03d}"


def gb_laden(con, gid):
    r = con.execute("SELECT * FROM as_gb WHERE id=?", (gid,)).fetchone()
    if not r:
        raise Fehler("Gefährdungsbeurteilung nicht gefunden.", 404)
    d = dict(r)
    d["werkzeug_ids"] = ids_liste(d["werkzeug_ids"])
    d["vorlagen"] = jl(d["vorlagen"], [])
    d["zeilen"] = jl(d["zeilen"], [])
    d["art_name"] = GB_ARTEN.get(d["art"], d["art"])
    d["status_name"] = GB_STATUS.get(d["status"], d["status"])
    d["werkzeuge"] = werkzeug_namen(con, d["werkzeug_ids"])
    d["fassungen"] = [dict(x) for x in con.execute("SELECT f.id, f.nr, f.stand, f.freigegeben_von, f.freigegeben_am, f.sha256, s.name AS unterschrift "
                                                   "FROM as_fassungen f LEFT JOIN signaturen s ON s.id=f.signatur_id WHERE f.art='gb' AND f.bezug_id=? ORDER BY f.nr DESC", (gid,))]
    d["offen"] = gb_offene(d)
    return d


def werkzeug_namen(con, ids):
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    return [dict(r) for r in con.execute(f"SELECT id, nummer, bezeichnung, art, standort, status FROM werkzeuge WHERE id IN ({ph}) ORDER BY nummer", ids)]


def gb_offene(g):
    """Zählt Handlungsbedarf: Maßnahmen „umsetzen“ ohne Erledigt-Datum, ungeprüfte Maßnahmen/Punkte."""
    umsetzen = ueberfaellig = ungeprueft = 0
    heute = date.today().isoformat()
    for z in g["zeilen"]:
        if g["art"] == "psychisch" and z.get("trifft") is None:
            ungeprueft += 1
        for m in z.get("m") or []:
            if m.get("status") == "offen":
                ungeprueft += 1
            elif m.get("status") == "umsetzen" and not m.get("erledigt"):
                umsetzen += 1
                if m.get("bis") and m["bis"] < heute:
                    ueberfaellig += 1
    return {"umsetzen": umsetzen, "ueberfaellig": ueberfaellig, "ungeprueft": ungeprueft}


def zeilen_bereinigen(zeilen):
    if not isinstance(zeilen, list):
        raise Fehler("Die Zeilen der Gefährdungsbeurteilung haben nicht den erwarteten Aufbau.")
    aus = []
    for z in zeilen[:500]:
        if not isinstance(z, dict):
            continue
        ms = []
        for m in (z.get("m") or [])[:200]:
            if not isinstance(m, dict):
                continue
            st = m.get("status") if m.get("status") in ("offen", "vorhanden", "umsetzen", "entfaellt") else "offen"
            ms.append({"id": str(m.get("id") or neue_id())[:16], "t": str(m.get("t") or "")[:2000], "art": m.get("art") if m.get("art") in ("T", "O", "P", "S") else "",
                       "status": st, "wer": str(m.get("wer") or "")[:120], "bis": datum_ok(m.get("bis")), "erledigt": datum_ok(m.get("erledigt")),
                       "wirksam": 1 if m.get("wirksam") in (1, True, "1") else 0, "wirksam_am": datum_ok(m.get("wirksam_am")), "wirksam_wer": str(m.get("wirksam_wer") or "")[:120]})
        trifft = z.get("trifft")
        aus.append({"id": str(z.get("id") or neue_id())[:16], "g": str(z.get("g") or "")[:2000], "gruppe": str(z.get("gruppe") or "")[:200],
                    "risiko": z.get("risiko") if z.get("risiko") in ("gering", "mittel", "hoch") else "", "quelle": str(z.get("quelle") or "")[:200],
                    "auto": 1 if z.get("auto") else 0, "trifft": None if trifft is None else bool(trifft), "hinweis": str(z.get("hinweis") or "")[:2000], "m": ms})
    return aus


def gb_anlegen(con, d):
    art = d.get("art") if d.get("art") in GB_ARTEN else "bereich"
    titel = str(d.get("titel") or "").strip()
    vorl = [str(v) for v in (d.get("vorlagen") or ([d["vorlage"]] if d.get("vorlage") else [])) if v]
    zeilen, namen = [], []
    if art == "psychisch":
        zeilen = zeilen_psychisch()
        titel = titel or "Psychische Belastung"
        vorl = ["BGHM FI 0052/0053"]
    else:
        for vid in vorl:
            z, v = zeilen_aus_vorlage(vid)
            zeilen += z
            namen.append(v["name"])
    if not titel:
        titel = namen[0] if namen else ""
    if not titel:
        raise Fehler("Bitte einen Titel angeben.")
    nr = naechste_nummer(con, "as_gb", "GB-")
    gid = con.execute("INSERT INTO as_gb (nummer, titel, art, bereich, werkzeug_ids, vorlagen, status, intervall, mitgeltend, zeilen, angelegt, geaendert) "
                      "VALUES (?,?,?,?,?,?,'entwurf',?,?,?,?,?)",
                      (nr, titel[:200], art, str(d.get("bereich") or "")[:200], json.dumps(ids_liste(d.get("werkzeug_ids"))), json.dumps(namen or vorl, ensure_ascii=False),
                       24 if art == "psychisch" else 12, "Betriebsanweisung, Bedienungsanleitung des Herstellers" if art == "maschine" else "",
                       json.dumps(zeilen, ensure_ascii=False), jetzt(), jetzt())).lastrowid
    return gb_laden(con, gid)


def gb_aendern(con, gid, d):
    g = gb_laden(con, gid)
    if g["status"] == "archiv" and d.get("status") != "entwurf":
        raise Fehler("Diese Gefährdungsbeurteilung ist archiviert.", 409)
    werte = {}
    for k in ("titel", "bereich", "beteiligte", "mitgeltend", "bemerkung"):
        if k in d:
            werte[k] = str(d[k] or "")[:4000]
    if "intervall" in d:
        try:
            werte["intervall"] = max(1, min(60, int(d["intervall"] or 12)))
        except (TypeError, ValueError):
            raise Fehler("Prüfintervall bitte in Monaten angeben.")
    if "werkzeug_ids" in d:
        werte["werkzeug_ids"] = json.dumps(ids_liste(d["werkzeug_ids"]))
    if "zeilen" in d:
        werte["zeilen"] = json.dumps(zeilen_bereinigen(d["zeilen"]), ensure_ascii=False)
    if "vorlage" in d and d["vorlage"]:
        z, v = zeilen_aus_vorlage(str(d["vorlage"]))
        werte["zeilen"] = json.dumps(jl(werte.get("zeilen"), g["zeilen"]) + z, ensure_ascii=False)
        werte["vorlagen"] = json.dumps(g["vorlagen"] + [v["name"]], ensure_ascii=False)
    if d.get("status") == "archiv":
        werte["status"] = "archiv"
    elif d.get("status") == "entwurf" and g["status"] == "archiv":
        werte["status"] = "ueberarbeitung" if g["fassungen"] else "entwurf"
    if not werte:
        return g
    inhaltlich = set(werte) - {"status"}
    if g["status"] == "gueltig" and inhaltlich:
        werte["status"] = "ueberarbeitung"   # die freigegebene Fassung bleibt gültig, bis die neue freigegeben ist
    werte["geaendert"] = jetzt()
    con.execute(f"UPDATE as_gb SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [gid])
    return gb_laden(con, gid)


def gb_pruefen(g):
    """Was einer Freigabe noch entgegensteht."""
    fehlt = []
    if not g["zeilen"]:
        fehlt.append("Es sind noch keine Gefährdungen eingetragen.")
    offen_psych = sum(1 for z in g["zeilen"] if g["art"] == "psychisch" and z.get("trifft") is None)
    if offen_psych:
        fehlt.append(f"{offen_psych} Aussage(n) der Checkliste noch nicht beantwortet („trifft zu“ oder „trifft nicht zu“).")
    for z in g["zeilen"]:
        kurz = (z.get("g") or "")[:60]
        if g["art"] == "psychisch":
            if z.get("trifft") is None:
                pass
            elif z.get("trifft") and z.get("auto") and not [m for m in z.get("m") or [] if m.get("status") != "entfaellt"]:
                fehlt.append(f"Handlungsbedarf ohne Maßnahme: {kurz}")
        for m in z.get("m") or []:
            if m.get("status") == "offen":
                fehlt.append(f"Maßnahme noch nicht bewertet: {kurz} – {(m.get('t') or '')[:50]}")
            if m.get("status") == "umsetzen" and not m.get("erledigt") and not (m.get("wer") and m.get("bis")):
                fehlt.append(f"Für eine umzusetzende Maßnahme fehlen „wer“ und „bis wann“: {(m.get('t') or '')[:60]}")
    return fehlt


def fassung_anlegen(con, art, bezug_id, inhalt, sig):
    nr = (con.execute("SELECT MAX(nr) FROM as_fassungen WHERE art=? AND bezug_id=?", (art, bezug_id)).fetchone()[0] or 0) + 1
    roh = json.dumps(inhalt, ensure_ascii=False, sort_keys=True, default=str)
    fid = con.execute("INSERT INTO as_fassungen (art, bezug_id, nr, stand, inhalt, sha256, signatur_id, freigegeben_von, freigegeben_am) VALUES (?,?,?,?,?,?,?,?,?)",
                      (art, bezug_id, nr, inhalt.get("stand") or date.today().isoformat(), roh, hashlib.sha256(roh.encode("utf-8")).hexdigest(),
                       sig["id"], sig["name"], sig["zeit"])).lastrowid
    return fid, nr


def gb_freigeben(con, daten, gid, d, wer):
    g = gb_laden(con, gid)
    if g["status"] == "archiv":
        raise Fehler("Diese Gefährdungsbeurteilung ist archiviert.", 409)
    fehlt = gb_pruefen(g)
    if fehlt:
        raise Fehler("Noch nicht freigabebereit: " + "; ".join(fehlt[:5]) + (f" (und {len(fehlt) - 5} weitere)" if len(fehlt) > 5 else ""), 409)
    stand = datum_ok(d.get("stand")) or date.today().isoformat()
    naechste = monate_plus(stand, g["intervall"] or 12)
    inhalt = {k: g[k] for k in ("nummer", "titel", "art", "art_name", "bereich", "werkzeuge", "vorlagen", "beteiligte", "mitgeltend", "bemerkung", "zeilen", "intervall")}
    inhalt.update({"stand": stand, "naechste": naechste})
    sig = unterschrift.speichern(con, sig_ordner(daten), "gb_freigabe", gid, "unternehmer", d.get("name"), d.get("png"), wer,
                                 inhalt_sha=unterschrift.inhalt_hash(inhalt), geraet=d.get("geraet"))
    fid, nr = fassung_anlegen(con, "gb", gid, inhalt, sig)
    con.execute("UPDATE as_gb SET status='gueltig', stand=?, naechste=?, geaendert=? WHERE id=?", (stand, naechste, jetzt(), gid))
    return gb_laden(con, gid), nr


def sig_ordner(daten):
    return os.path.join(daten, "unterschriften")


def gb_liste(con):
    aus = []
    for r in con.execute("SELECT * FROM as_gb ORDER BY status='archiv', nummer"):
        d = dict(r)
        d["werkzeug_ids"] = ids_liste(d["werkzeug_ids"])
        z = jl(d.pop("zeilen"), [])
        d["offen"] = gb_offene({"art": d["art"], "zeilen": z})
        d["anzahl"] = len(z)
        d["art_name"] = GB_ARTEN.get(d["art"], d["art"])
        d["status_name"] = GB_STATUS.get(d["status"], d["status"])
        d["werkzeuge"] = werkzeug_namen(con, d["werkzeug_ids"])
        d["fassungen"] = con.execute("SELECT COUNT(*) FROM as_fassungen WHERE art='gb' AND bezug_id=?", (d["id"],)).fetchone()[0]
        aus.append(d)
    return aus


def gb_loeschen(con, gid):
    g = gb_laden(con, gid)
    if g["fassungen"]:
        raise Fehler("Eine freigegebene Gefährdungsbeurteilung wird nicht gelöscht, sondern archiviert.", 409)
    con.execute("DELETE FROM as_gb WHERE id=?", (gid,))


def vorschlag_vorlage(name):
    """Passende Vorlage zum Namen einer Maschine (z. B. „Formatkreissäge Altendorf“ → Tisch-/Formatkreissäge)."""
    n = str(name or "").lower()
    regeln = [("formatkreis", "tisch-formatkreissaege"), ("tischkreis", "tisch-formatkreissaege"), ("kreissäge", "tisch-formatkreissaege"),
              ("plattensäge", "plattensaege-vertikal"), ("plattenaufteil", "plattensaege-horizontal"), ("kapp", "gehrungskappkreissaege"),
              ("bandsäge", "tischbandsaegemaschine"), ("tischfräs", "tischfraesmaschine"), ("abricht", "abrichthobelmaschine"),
              ("dickenhobel", "dickenhobelmaschine"), ("dickte", "dickenhobelmaschine"), ("cnc", "cnc-oberfraesmaschine-cnc-bearbeitungszentrum"),
              ("bearbeitungszentrum", "cnc-oberfraesmaschine-cnc-bearbeitungszentrum"), ("kantenanleim", "kantenanleimmaschine"), ("kantenleim", "kantenanleimmaschine"),
              ("breitband", "breitbandschleifmaschine"), ("kantenschleif", "kanten-langband-tellerschleifmaschine"), ("langband", "kanten-langband-tellerschleifmaschine"),
              ("tellerschleif", "kanten-langband-tellerschleifmaschine"), ("furnierpresse", "furnierpresse"), ("presse", "rahmen-und-korpuspresse"),
              ("ständerbohr", "staenderbohrmaschine"), ("bohrmaschine", "handbohrmaschine-schrauber"), ("dübelbohr", "mehrfachbohrmaschine-mit-handbeschickung"),
              ("langloch", "kettenfraesmaschine"), ("kettenfräs", "kettenfraesmaschine"), ("absaug", "spaene-absaugung"), ("silo", "spaenesilo"),
              ("kompressor", "kompressor-druckbehaelter"), ("schleifbock", "schleifbock-bandschleifmaschine"), ("handkreis", "handkreissaege"),
              ("tauchsäge", "handkreissaege"), ("oberfräse", "handoberfraese"), ("handhobel", "handhobelmaschine"), ("stichsäge", "stichsaege-saebelsaege"),
              ("säbelsäge", "stichsaege-saebelsaege"), ("flachdübel", "flachduebelfraese"), ("domino", "flachduebelfraese"), ("nagler", "eintreibgeraete-druckluftnagler"),
              ("tacker", "eintreibgeraete-druckluftnagler"), ("exzenter", "exzenterschleifer-schwingschleifer"), ("schwingschleif", "exzenterschleifer-schwingschleifer"),
              ("schleifer", "exzenterschleifer-schwingschleifer"), ("akkuschrauber", "handbohrmaschine-schrauber"), ("winkelschleif", "winkelschleifer"),
              ("flex", "winkelschleifer"), ("stapler", "flurfoerderzeuge-ffz"), ("hubwagen", "manuelles-mitgaenger-ffz-hubwagen-ameise"),
              ("leiter", "steh-und-anlegeleiter-tritte"), ("gerüst", "fahrbare-arbeitsbuehne-und-kleingerueste"), ("hammer", "elektrohammer"),
              ("vierseit", "vierseitenhobelmaschine"), ("kehlmaschine", "vierseitenhobelmaschine"), ("leimauftrag", "walzen-leimauftragmaschine"),
              ("zapfen", "zapfenschneid-und-schlitzmaschine"), ("trockenraum", "trockenraum"), ("kettensäge", "handkettensaege")]
    ids = {x["id"] for x in vorlagen()["gb"]}
    for wort, vid in regeln:
        if wort in n and vid in ids:
            return vid
    return ""


def uwh_zu_vorlage(vid):
    """Unterweisungshilfe passend zu einer GB-Vorlage (für Betriebsanweisung und Unterweisungsthema)."""
    v = next((x for x in vorlagen()["gb"] if x["id"] == vid), None)
    if not v:
        return ""
    for t in vorlagen()["themen"]:
        if v["name"] in (t.get("gbo") or []):
            return t["id"]
    return ""


# ---------------------------------------------------------------- Betriebsanweisungen
def ba_laden(con, bid):
    r = con.execute("SELECT * FROM as_ba WHERE id=?", (bid,)).fetchone()
    if not r:
        raise Fehler("Betriebsanweisung nicht gefunden.", 404)
    d = dict(r)
    d["werkzeug_ids"] = ids_liste(d["werkzeug_ids"])
    d["abschnitte"] = jl(d["abschnitte"], {})
    d["symbole"] = jl(d["symbole"], [])
    d["art_name"] = BA_ARTEN.get(d["art"], d["art"])
    d["status_name"] = GB_STATUS.get(d["status"], d["status"])
    d["gliederung"] = BA_ABSCHNITTE.get(d["art"], BA_ABSCHNITTE["maschine"])
    d["werkzeuge"] = werkzeug_namen(con, d["werkzeug_ids"])
    d["material"] = None
    if d["material_id"]:
        m = con.execute("SELECT id, nummer, bezeichnung FROM material WHERE id=?", (d["material_id"],)).fetchone()
        if m:
            d["material"] = {"id": m["id"], "nummer": m["nummer"], "name": (m["bezeichnung"] or "").split("\n")[0]}
    d["fassungen"] = [dict(x) for x in con.execute("SELECT id, nr, stand, freigegeben_von, freigegeben_am FROM as_fassungen WHERE art='ba' AND bezug_id=? ORDER BY nr DESC", (bid,))]
    return d


def ba_anlegen(con, d):
    art = d.get("art") if d.get("art") in BA_ARTEN else "maschine"
    wids = ids_liste(d.get("werkzeug_ids"))
    mid = int(d["material_id"]) if str(d.get("material_id") or "").isdigit() else None
    titel = str(d.get("titel") or "").strip()
    abschnitte, symbole, vorlage = {k: "" for k, _ in BA_ABSCHNITTE[art]}, [], str(d.get("vorlage") or "")
    org = organisation(con)
    if art == "gefahrstoff":
        if not mid:
            raise Fehler("Bitte den Gefahrstoff (Material) wählen.")
        m = con.execute("SELECT m.*, l.kurzname AS lieferant FROM material m LEFT JOIN lieferanten l ON l.id=m.lieferant_id WHERE m.id=?", (mid,)).fetchone()
        if not m:
            raise Fehler("Material nicht gefunden.", 404)
        g = gefahrstoff(con, mid)
        name = (m["bezeichnung"] or "").split("\n")[0]
        titel = titel or name
        hs = vorlagen()["h_saetze"]
        codes = h_codes(g["h_saetze"])
        abschnitte["anwendung"] = (g["bereich"] or "Arbeitsbereich und Tätigkeit eintragen") + "\n"
        abschnitte["stoff"] = name + (f" ({m['lieferant']})" if m["lieferant"] else "")
        abschnitte["gefahren"] = "\n".join(([f"Signalwort: {g['signalwort']}"] if g["signalwort"] else [])
                                           + [f"{c}: {hs[c]}" if c in hs else f"{c}: [aus SDB Abschnitt 2 ergänzen]" for c in codes]
                                           or ["[aus SDB Abschnitt 2 ergänzen: Gefahren für Mensch und Umwelt]"])
        abschnitte["schutz"] = "\n".join(["[aus SDB Abschnitt 7 und 8 ergänzen: Handhabung, Lüftung, Lagerung]",
                                          f"Persönliche Schutzausrüstung: {g['psa']}" if g["psa"] else "[aus SDB Abschnitt 8 ergänzen: persönliche Schutzausrüstung]",
                                          "Am Arbeitsplatz nicht essen, trinken oder rauchen.", "Behälter geschlossen halten und nur in gekennzeichneten Gebinden aufbewahren."])
        abschnitte["gefahrfall"] = "[aus SDB Abschnitt 5 und 6 ergänzen: Brandbekämpfung, Maßnahmen bei unbeabsichtigter Freisetzung]\nNotruf 112"
        abschnitte["erstehilfe"] = "[aus SDB Abschnitt 4 ergänzen: Erste-Hilfe-Maßnahmen]\nErsthelfer verständigen, Unfall melden, Eintrag ins Verbandbuch."
        abschnitte["entsorgung"] = "[aus SDB Abschnitt 13 ergänzen: Entsorgung]"
        symbole = list(g["ghs"])
    else:
        werkzeuge = werkzeug_namen(con, wids)
        uwh = next((t for t in vorlagen()["themen"] if t["id"] == vorlage), None) if vorlage else None
        if not uwh and werkzeuge:
            vid = vorschlag_vorlage(werkzeuge[0]["bezeichnung"])
            tid = uwh_zu_vorlage(vid) if vid else ""
            uwh = next((t for t in vorlagen()["themen"] if t["id"] == tid), None)
            vorlage = tid
        titel = titel or (werkzeuge[0]["bezeichnung"] if werkzeuge else (uwh["titel"] if uwh else ""))
        if not titel:
            raise Fehler("Bitte einen Titel angeben.")
        abschnitte["anwendung"] = "\n".join([f"{w['bezeichnung']} ({w['nummer']}){', Standort ' + w['standort'] if w['standort'] else ''}" for w in werkzeuge] or [titel])
        # Gefahren aus einer Gefährdungsbeurteilung dieser Maschine, sonst aus der passenden Vorlage
        gef = []
        for r in con.execute("SELECT zeilen, werkzeug_ids FROM as_gb WHERE status<>'archiv'"):
            if set(ids_liste(r["werkzeug_ids"])) & set(wids):
                gef += [z["g"] for z in jl(r["zeilen"], []) if z.get("g")]
        if not gef and uwh:
            for gname in uwh.get("gbo") or []:
                v = next((x for x in vorlagen()["gb"] if x["name"] == gname), None)
                gef += [x["g"] for x in (v or {}).get("gef", [])]
        abschnitte["gefahren"] = "\n".join(dict.fromkeys(gef)) if gef else ""
        abschnitte["schutz"] = "\n".join(p for a in (uwh or {}).get("abschnitte", []) for p in a["punkte"])
        abschnitte["stoerung"] = "\n".join(MASCHINE_STOERUNG)
        abschnitte["erstehilfe"] = "\n".join(MASCHINE_ERSTEHILFE)
        abschnitte["instandhaltung"] = "\n".join(MASCHINE_INSTANDHALTUNG)
        schutz = abschnitte["schutz"].lower()
        symbole = [c for c, w in (("M003", "gehörschutz"), ("M004", "schutzbrille"), ("M008", "sicherheitsschuh"), ("M009", "handschuh"), ("M017", "atemschutz")) if w in schutz]
    nr = naechste_nummer(con, "as_ba", "BA-")
    bid = con.execute("INSERT INTO as_ba (nummer, titel, art, bereich, werkzeug_ids, material_id, vorlage, abschnitte, symbole, status, angelegt, geaendert) "
                      "VALUES (?,?,?,?,?,?,?,?,?,'entwurf',?,?)",
                      (nr, titel[:200], art, str(d.get("bereich") or (org["bereiche"][0] if org["bereiche"] else ""))[:200], json.dumps(wids), mid, vorlage,
                       json.dumps(abschnitte, ensure_ascii=False), json.dumps(symbole), jetzt(), jetzt())).lastrowid
    return ba_laden(con, bid)


def ba_aendern(con, bid, d):
    b = ba_laden(con, bid)
    werte = {}
    for k in ("titel", "bereich"):
        if k in d:
            werte[k] = str(d[k] or "")[:200]
    if "abschnitte" in d:
        if not isinstance(d["abschnitte"], dict):
            raise Fehler("Die Abschnitte haben nicht den erwarteten Aufbau.")
        werte["abschnitte"] = json.dumps({k: str(d["abschnitte"].get(k, b["abschnitte"].get(k, "")) or "")[:8000] for k, _ in b["gliederung"]}, ensure_ascii=False)
    if "symbole" in d:
        werte["symbole"] = json.dumps([str(s)[:12] for s in (d["symbole"] if isinstance(d["symbole"], list) else []) if re.fullmatch(r"[A-Z-]{1,4}\d{3}|GHS0\d", str(s))][:16])
    if "werkzeug_ids" in d:
        werte["werkzeug_ids"] = json.dumps(ids_liste(d["werkzeug_ids"]))
    if d.get("status") == "archiv":
        werte["status"] = "archiv"
    elif d.get("status") == "entwurf" and b["status"] == "archiv":
        werte["status"] = "ueberarbeitung" if b["fassungen"] else "entwurf"
    if not werte:
        return b
    if b["status"] == "gueltig" and set(werte) - {"status"}:
        werte["status"] = "ueberarbeitung"
    werte["geaendert"] = jetzt()
    con.execute(f"UPDATE as_ba SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [bid])
    return ba_laden(con, bid)


def ba_freigeben(con, daten, bid, d, wer):
    b = ba_laden(con, bid)
    leer = [t for k, t in b["gliederung"] if not str(b["abschnitte"].get(k) or "").strip()]
    if leer:
        raise Fehler("Noch nicht ausgefüllt: " + ", ".join(leer), 409)
    if any(PLATZHALTER in str(v) for v in b["abschnitte"].values()):
        raise Fehler("Es sind noch Angaben aus dem Sicherheitsdatenblatt zu ergänzen (Stellen mit „[aus SDB …]“).", 409)
    stand = datum_ok(d.get("stand")) or date.today().isoformat()
    inhalt = {k: b[k] for k in ("nummer", "titel", "art", "art_name", "bereich", "abschnitte", "symbole", "werkzeuge", "material")}
    inhalt["stand"] = stand
    inhalt["gliederung"] = b["gliederung"]
    sig = unterschrift.speichern(con, sig_ordner(daten), "ba_freigabe", bid, "unternehmer", d.get("name"), d.get("png"), wer,
                                 inhalt_sha=unterschrift.inhalt_hash(inhalt), geraet=d.get("geraet"))
    _, nr = fassung_anlegen(con, "ba", bid, inhalt, sig)
    con.execute("UPDATE as_ba SET status='gueltig', stand=?, geaendert=? WHERE id=?", (stand, jetzt(), bid))
    return ba_laden(con, bid), nr


def ba_liste(con, nur_gueltig=False):
    aus = []
    for r in con.execute("SELECT b.*, m.nummer AS mat_nummer FROM as_ba b LEFT JOIN material m ON m.id=b.material_id "
                         + ("WHERE b.status IN ('gueltig','ueberarbeitung') AND EXISTS (SELECT 1 FROM as_fassungen f WHERE f.art='ba' AND f.bezug_id=b.id) " if nur_gueltig else "")
                         + "ORDER BY b.status='archiv', b.art, b.titel"):
        d = dict(r)
        d.pop("abschnitte", None)
        d["symbole"] = jl(d["symbole"], [])
        d["werkzeug_ids"] = ids_liste(d["werkzeug_ids"])
        d["werkzeuge"] = werkzeug_namen(con, d["werkzeug_ids"])
        d["art_name"] = BA_ARTEN.get(d["art"], d["art"])
        d["status_name"] = GB_STATUS.get(d["status"], d["status"])
        aus.append(d)
    return aus


def ba_loeschen(con, bid):
    b = ba_laden(con, bid)
    if b["fassungen"]:
        raise Fehler("Eine freigegebene Betriebsanweisung wird nicht gelöscht, sondern archiviert.", 409)
    con.execute("DELETE FROM as_ba WHERE id=?", (bid,))


def fassung(con, fid):
    r = con.execute("SELECT * FROM as_fassungen WHERE id=?", (fid,)).fetchone()
    if not r:
        raise Fehler("Fassung nicht gefunden.", 404)
    d = dict(r)
    d["inhalt"] = jl(d["inhalt"], {})
    d["unverändert"] = hashlib.sha256(r["inhalt"].encode("utf-8")).hexdigest() == r["sha256"]
    return d


def letzte_fassung(con, art, bezug_id):
    r = con.execute("SELECT id FROM as_fassungen WHERE art=? AND bezug_id=? ORDER BY nr DESC LIMIT 1", (art, bezug_id)).fetchone()
    return fassung(con, r["id"]) if r else None


# ---------------------------------------------------------------- Unterweisungsthemen
def text_zu_abschnitten(text):
    """Einfache Schreibweise: Zeilen mit „## “ sind Überschriften, alle anderen Zeilen Punkte."""
    aus, akt = [], None
    for z in str(text or "").splitlines():
        z = z.strip()
        if not z:
            continue
        if z.startswith("#"):
            akt = {"titel": z.lstrip("# ").strip(), "punkte": []}
            aus.append(akt)
            continue
        if akt is None:
            akt = {"titel": "", "punkte": []}
            aus.append(akt)
        akt["punkte"].append(z.lstrip("•-* ").strip())
    return aus


def abschnitte_zu_text(ab):
    zeilen = []
    for a in ab or []:
        if a.get("titel"):
            zeilen.append("## " + a["titel"])
        zeilen += a.get("punkte") or []
        zeilen.append("")
    return "\n".join(zeilen).strip()


def thema_laden(con, tid):
    r = con.execute("SELECT * FROM as_themen WHERE id=?", (tid,)).fetchone()
    if not r:
        raise Fehler("Thema nicht gefunden.", 404)
    return thema_aus(con, r)


def thema_aus(con, r):
    d = dict(r)
    d["abschnitte"] = jl(d["abschnitte"], [])
    d["text"] = abschnitte_zu_text(d["abschnitte"])
    for k in ("mitarbeiter_ids", "werkzeug_ids", "ba_ids"):
        d[k] = ids_liste(d[k])
    d["ba"] = [dict(x) for x in con.execute(f"SELECT id, nummer, titel, status FROM as_ba WHERE id IN ({','.join('?' * len(d['ba_ids'])) or 'NULL'})", d["ba_ids"])]
    d["werkzeuge"] = werkzeug_namen(con, d["werkzeug_ids"])
    return d


def themen(con, alle=False):
    return [thema_aus(con, r) for r in con.execute("SELECT * FROM as_themen" + ("" if alle else " WHERE aktiv=1") + " ORDER BY gruppe, titel")]


def thema_anlegen(con, d):
    v = next((t for t in vorlagen()["themen"] if t["id"] == d.get("vorlage")), None) if d.get("vorlage") else None
    titel = str(d.get("titel") or (v["titel"] if v else "")).strip()
    if not titel:
        raise Fehler("Bitte einen Titel angeben.")
    ab = v["abschnitte"] if v else text_zu_abschnitten(d.get("text"))
    tid = con.execute("INSERT INTO as_themen (titel, gruppe, vorlage, uwh, abschnitte, intervall, alle, mitarbeiter_ids, werkzeug_ids, ba_ids, aktiv, angelegt, geaendert) "
                      "VALUES (?,?,?,?,?,12,1,'[]',?,?,1,?,?)",
                      (titel[:200], (v["gruppe"] if v else str(d.get("gruppe") or "Betrieb"))[:80], v["id"] if v else "", (v or {}).get("uwh", ""),
                       json.dumps(ab, ensure_ascii=False), json.dumps(ids_liste(d.get("werkzeug_ids"))), json.dumps(ids_liste(d.get("ba_ids"))), jetzt(), jetzt())).lastrowid
    return thema_laden(con, tid)


def thema_aendern(con, tid, d):
    thema_laden(con, tid)
    werte = {}
    for k in ("titel", "gruppe"):
        if k in d:
            werte[k] = str(d[k] or "").strip()[:200]
    if "text" in d:
        werte["abschnitte"] = json.dumps(text_zu_abschnitten(d["text"]), ensure_ascii=False)
    if "intervall" in d:
        try:
            werte["intervall"] = max(1, min(60, int(d["intervall"] or 12)))
        except (TypeError, ValueError):
            raise Fehler("Intervall bitte in Monaten angeben.")
    for k in ("alle", "aktiv"):
        if k in d:
            werte[k] = 1 if d[k] in (1, True, "1") else 0
    for k in ("mitarbeiter_ids", "werkzeug_ids", "ba_ids"):
        if k in d:
            werte[k] = json.dumps(ids_liste(d[k]))
    if werte:
        werte["geaendert"] = jetzt()
        con.execute(f"UPDATE as_themen SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [tid])
    return thema_laden(con, tid)


def thema_loeschen(con, tid):
    benutzt = any(tid in ids_liste(r["thema_ids"]) for r in con.execute("SELECT thema_ids FROM as_unterweisungen"))
    if benutzt:
        con.execute("UPDATE as_themen SET aktiv=0 WHERE id=?", (tid,))
        return {"inaktiv": True}
    con.execute("DELETE FROM as_themen WHERE id=?", (tid,))
    return {"ok": True}


# ---------------------------------------------------------------- Unterweisungen
def letzte_unterweisungen(con):
    """(mitarbeiter_id, thema_id) → Datum der letzten unterschriebenen Unterweisung."""
    aus = {}
    for r in con.execute("SELECT t.mitarbeiter_id, u.datum, u.thema_ids FROM as_teilnehmer t JOIN as_unterweisungen u ON u.id=t.unterweisung_id "
                         "WHERE t.signatur_id IS NOT NULL AND t.mitarbeiter_id IS NOT NULL"):
        for tid in ids_liste(r["thema_ids"]):
            k = (r["mitarbeiter_id"], tid)
            if r["datum"] and r["datum"] > aus.get(k, ""):
                aus[k] = r["datum"]
    return aus


def matrix(con):
    heute = date.today().isoformat()
    bald = (date.today() + timedelta(days=30)).isoformat()
    mas, th = beschaeftigte(con), themen(con)
    letzte = letzte_unterweisungen(con)
    zeilen = []
    for m in mas:
        felder = {}
        for t in th:
            if not t["alle"] and m["id"] not in t["mitarbeiter_ids"]:
                continue
            l = letzte.get((m["id"], t["id"]))
            iv = min(6, t["intervall"]) if m["jugendlich"] else t["intervall"]
            if not l:
                felder[t["id"]] = {"status": "fehlt", "letzte": "", "faellig": m["eintritt"] or heute, "intervall": iv}
                continue
            f = monate_plus(l, iv)
            felder[t["id"]] = {"status": "ueberfaellig" if f < heute else "bald" if f <= bald else "ok", "letzte": l, "faellig": f, "intervall": iv}
        zeilen.append({"mitarbeiter": {k: m[k] for k in ("id", "name", "kuerzel", "eintritt", "jugendlich")}, "themen": felder})
    return {"themen": [{"id": t["id"], "titel": t["titel"], "gruppe": t["gruppe"], "intervall": t["intervall"]} for t in th], "zeilen": zeilen}


def unterweisung_laden(con, uid, daten=None):
    r = con.execute("SELECT * FROM as_unterweisungen WHERE id=?", (uid,)).fetchone()
    if not r:
        raise Fehler("Unterweisung nicht gefunden.", 404)
    d = dict(r)
    d["thema_ids"] = ids_liste(d["thema_ids"])
    d["inhalt"] = jl(d["inhalt"], [])
    d["teilnehmer"] = []
    for t in con.execute("SELECT t.*, s.zeit AS sig_zeit, s.name AS sig_name FROM as_teilnehmer t LEFT JOIN signaturen s ON s.id=t.signatur_id "
                         "WHERE t.unterweisung_id=? ORDER BY t.name", (uid,)):
        d["teilnehmer"].append({"id": t["id"], "mitarbeiter_id": t["mitarbeiter_id"], "name": t["name"], "unterschrieben": t["sig_zeit"] or "", "signatur_id": t["signatur_id"]})
    u = unterschrift.letzte(con, "unterweisung", uid, "unterweiser")
    d["unterweiser_signatur"] = unterschrift.oeffentlich(u)
    d["inhalt_hash"] = unterweisung_hash(d)
    return d


def unterweisung_hash(d):
    return unterschrift.inhalt_hash({"datum": d["datum"], "inhalt": d["inhalt"], "ergaenzung": d["ergaenzung"], "anlass": d["anlass"]})


def inhalt_aus_themen(con, tids):
    aus = []
    for tid in tids:
        t = thema_laden(con, tid)
        ba = t["ba"]
        if t["vorlage"] == "gefahrstoffe":
            ba = ba + [{"id": b["id"], "nummer": b["nummer"], "titel": b["titel"], "status": b["status"]} for b in ba_liste(con, True) if b["art"] == "gefahrstoff" and b["id"] not in t["ba_ids"]]
        aus.append({"thema_id": t["id"], "titel": t["titel"], "abschnitte": t["abschnitte"], "uwh": t["uwh"],
                    "ba": [{"id": b["id"], "nummer": b["nummer"], "titel": b["titel"]} for b in ba if b.get("status") in ("gueltig", "ueberarbeitung")]})
    return aus


def unterweisung_anlegen(con, d, wer, wer_name):
    tids = [t for t in ids_liste(d.get("thema_ids")) if con.execute("SELECT 1 FROM as_themen WHERE id=?", (t,)).fetchone()]
    if not tids:
        raise Fehler("Bitte mindestens ein Thema wählen.")
    mids = ids_liste(d.get("mitarbeiter_ids"))
    if not mids:
        raise Fehler("Bitte die Teilnehmer wählen.")
    datum = datum_ok(d.get("datum")) or date.today().isoformat()
    inhalt = inhalt_aus_themen(con, tids)
    titel = str(d.get("titel") or "").strip() or ", ".join(t["titel"] for t in inhalt)
    nr = naechste_nummer(con, "as_unterweisungen", f"UW-{datum[:4]}-")
    uid = con.execute("INSERT INTO as_unterweisungen (nummer, datum, titel, thema_ids, anlass, ort, unterweiser, inhalt, status, angelegt, von) VALUES (?,?,?,?,?,?,?,?, 'offen', ?, ?)",
                      (nr, datum, titel[:300], json.dumps(tids), str(d.get("anlass") or "")[:200], str(d.get("ort") or "")[:200],
                       str(d.get("unterweiser") or wer_name or wer)[:120], json.dumps(inhalt, ensure_ascii=False), jetzt(), wer)).lastrowid
    namen = {m["id"]: m["name"] for m in mitarbeiter_liste(con, True)}
    for mid in mids:
        if mid in namen:
            con.execute("INSERT INTO as_teilnehmer (unterweisung_id, mitarbeiter_id, name) VALUES (?,?,?)", (uid, mid, namen[mid]))
    return unterweisung_laden(con, uid)


def unterweisung_aendern(con, uid, d):
    u = unterweisung_laden(con, uid)
    if u["status"] != "offen":
        raise Fehler("Die Unterweisung ist abgeschlossen und kann nicht mehr geändert werden.", 409)
    unterschrieben = any(t["unterschrieben"] for t in u["teilnehmer"]) or u["unterweiser_signatur"]
    werte = {}
    for k in ("ort", "verstaendnis", "dauer", "unterweiser"):
        if k in d:
            werte[k] = str(d[k] or "")[:2000]
    if "unterweiser" in werte and u["unterweiser_signatur"] and werte["unterweiser"] != u["unterweiser"]:
        raise Fehler("Die unterweisende Person hat schon unterschrieben; der Name bleibt deshalb unverändert.", 409)
    inhaltlich = {k for k in ("datum", "anlass", "ergaenzung", "thema_ids", "titel") if k in d}
    if inhaltlich and unterschrieben:
        raise Fehler("Es wurde schon unterschrieben – Inhalt, Datum und Anlass bleiben deshalb unverändert.", 409)
    if "datum" in d:
        werte["datum"] = datum_ok(d["datum"]) or u["datum"]
    for k in ("anlass", "ergaenzung", "titel"):
        if k in d:
            werte[k] = str(d[k] or "")[:4000]
    if "thema_ids" in d:
        tids = ids_liste(d["thema_ids"])
        if not tids:
            raise Fehler("Bitte mindestens ein Thema wählen.")
        werte["thema_ids"] = json.dumps(tids)
        werte["inhalt"] = json.dumps(inhalt_aus_themen(con, tids), ensure_ascii=False)
    if "mitarbeiter_ids" in d:
        neu = set(ids_liste(d["mitarbeiter_ids"]))
        namen = {m["id"]: m["name"] for m in mitarbeiter_liste(con, True)}
        da = {t["mitarbeiter_id"]: t for t in u["teilnehmer"]}
        for mid, t in da.items():
            if mid not in neu and not t["unterschrieben"]:
                con.execute("DELETE FROM as_teilnehmer WHERE id=?", (t["id"],))
        for mid in neu - set(da):
            if mid in namen:
                con.execute("INSERT INTO as_teilnehmer (unterweisung_id, mitarbeiter_id, name) VALUES (?,?,?)", (uid, mid, namen[mid]))
    if werte:
        con.execute(f"UPDATE as_unterweisungen SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [uid])
    return unterweisung_laden(con, uid)


def unterweisung_unterschreiben(con, daten, uid, d, wer, eigener_mitarbeiter=None):
    u = unterweisung_laden(con, uid)
    if u["status"] != "offen":
        raise Fehler("Die Unterweisung ist bereits abgeschlossen.", 409)
    rolle = "unterweiser" if d.get("rolle") == "unterweiser" else "teilnehmer"
    if rolle == "unterweiser":
        if eigener_mitarbeiter is not None:
            raise Fehler("Die unterweisende Person unterschreibt im Büro bzw. am Tablet des Betriebs.", 403)
        sig = unterschrift.speichern(con, sig_ordner(daten), "unterweisung", uid, "unterweiser", d.get("name") or u["unterweiser"], d.get("png"), wer,
                                     inhalt_sha=u["inhalt_hash"], geraet=d.get("geraet"))
        if (d.get("name") or "").strip() and d["name"].strip() != u["unterweiser"]:
            con.execute("UPDATE as_unterweisungen SET unterweiser=? WHERE id=?", (d["name"].strip()[:120], uid))
        return unterweisung_laden(con, uid)
    if eigener_mitarbeiter is not None:
        t = next((x for x in u["teilnehmer"] if x["mitarbeiter_id"] == eigener_mitarbeiter), None)
    else:
        t = next((x for x in u["teilnehmer"] if str(x["id"]) == str(d.get("teilnehmer_id")) or (d.get("mitarbeiter_id") and x["mitarbeiter_id"] == int(d["mitarbeiter_id"]))), None)
    if not t:
        raise Fehler("Diese Person steht nicht auf der Teilnehmerliste.", 404)
    if t["unterschrieben"]:
        raise Fehler(f"{t['name']} hat bereits unterschrieben.", 409)
    sig = unterschrift.speichern(con, sig_ordner(daten), "unterweisung", uid, "teilnehmer", d.get("name") or t["name"], d.get("png"), wer,
                                 mitarbeiter_id=t["mitarbeiter_id"], inhalt_sha=u["inhalt_hash"], geraet=d.get("geraet"))
    con.execute("UPDATE as_teilnehmer SET signatur_id=?, unterschrieben=? WHERE id=?", (sig["id"], sig["zeit"], t["id"]))
    return unterweisung_laden(con, uid)


def unterweisung_abschliessen(con, uid):
    u = unterweisung_laden(con, uid)
    if u["status"] != "offen":
        raise Fehler("Die Unterweisung ist bereits abgeschlossen.", 409)
    if not u["unterweiser_signatur"]:
        raise Fehler("Die unterweisende Person hat noch nicht unterschrieben.", 409)
    if not any(t["unterschrieben"] for t in u["teilnehmer"]):
        raise Fehler("Es hat noch kein Teilnehmer unterschrieben.", 409)
    entfernt = [t["name"] for t in u["teilnehmer"] if not t["unterschrieben"]]
    con.execute("DELETE FROM as_teilnehmer WHERE unterweisung_id=? AND signatur_id IS NULL", (uid,))
    con.execute("UPDATE as_unterweisungen SET status='abgeschlossen', abgeschlossen=? WHERE id=?", (jetzt(), uid))
    return unterweisung_laden(con, uid), entfernt


def unterweisung_loeschen(con, uid):
    u = unterweisung_laden(con, uid)
    if u["status"] != "offen" or u["unterweiser_signatur"] or any(t["unterschrieben"] for t in u["teilnehmer"]):
        raise Fehler("Eine Unterweisung mit Unterschriften bleibt als Nachweis erhalten.", 409)
    con.execute("DELETE FROM as_teilnehmer WHERE unterweisung_id=?", (uid,))
    con.execute("DELETE FROM as_unterweisungen WHERE id=?", (uid,))


def unterweisungen(con):
    aus = []
    for r in con.execute("SELECT * FROM as_unterweisungen ORDER BY datum DESC, id DESC"):
        d = dict(r)
        d.pop("inhalt", None)
        tn = con.execute("SELECT COUNT(*) AS n, SUM(signatur_id IS NOT NULL) AS s FROM as_teilnehmer WHERE unterweisung_id=?", (r["id"],)).fetchone()
        d["teilnehmer"] = tn["n"] or 0
        d["unterschrieben"] = tn["s"] or 0
        d["namen"] = [x["name"] for x in con.execute("SELECT name FROM as_teilnehmer WHERE unterweisung_id=? ORDER BY name", (r["id"],))]
        aus.append(d)
    return aus


def offene_fuer(con, mid):
    """Offene Unterweisungen, die dieser Mitarbeiter noch unterschreiben kann (Stempeluhr)."""
    return [{"id": r["id"], "nummer": r["nummer"], "datum": r["datum"], "titel": r["titel"]} for r in con.execute(
        "SELECT u.* FROM as_unterweisungen u JOIN as_teilnehmer t ON t.unterweisung_id=u.id WHERE u.status='offen' AND t.mitarbeiter_id=? AND t.signatur_id IS NULL "
        "ORDER BY u.datum", (mid,))]


# ---------------------------------------------------------------- Qualifikationen, Verbandbuch
def qualifikationen(con):
    heute = date.today().isoformat()
    aus = []
    for r in con.execute("SELECT q.*, m.vorname, m.nachname FROM as_qualifikationen q LEFT JOIN mitarbeiter m ON m.id=q.mitarbeiter_id ORDER BY q.art, q.name"):
        d = dict(r)
        d["name"] = f"{r['vorname'] or ''} {r['nachname'] or ''}".strip() or r["name"]
        d["gueltig"] = not d["gueltig_bis"] or d["gueltig_bis"] >= heute
        d["dateien"] = dateien(con, {"qualifikation": r["id"]})
        aus.append(d)
    return aus


def quali_speichern(con, qid, d):
    werte = {}
    if "mitarbeiter_id" in d:
        werte["mitarbeiter_id"] = int(d["mitarbeiter_id"]) if str(d.get("mitarbeiter_id") or "").isdigit() else None
    for k in ("name", "art", "bemerkung"):
        if k in d:
            werte[k] = str(d[k] or "").strip()[:300]
    for k in ("datum", "gueltig_bis"):
        if k in d:
            werte[k] = datum_ok(d[k])
    if qid is None:
        if not werte.get("art"):
            raise Fehler("Bitte die Art angeben (z. B. Ersthelfer).")
        if not werte.get("mitarbeiter_id") and not werte.get("name"):
            raise Fehler("Bitte die Person wählen.")
        if werte.get("datum") and not werte.get("gueltig_bis") and QUALI.get(werte["art"]):
            werte["gueltig_bis"] = monate_plus(werte["datum"], QUALI[werte["art"]])
        werte["angelegt"] = jetzt()
        qid = con.execute(f"INSERT INTO as_qualifikationen ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})", list(werte.values())).lastrowid
    elif werte:
        con.execute(f"UPDATE as_qualifikationen SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [qid])
    return next((q for q in qualifikationen(con) if q["id"] == qid), None)


VB_FELDER = ("zeit", "ort", "name", "hergang", "verletzung", "zeugen", "hilfe_zeit", "massnahmen", "helfer")


def verbandbuch_eintragen(con, d, wer):
    w = {k: str(d.get(k) or "").strip()[:2000] for k in VB_FELDER}
    if not w["name"] or not w["verletzung"]:
        raise Fehler("Bitte Name der verletzten Person und Art der Verletzung angeben.")
    w["zeit"] = w["zeit"][:16] or jetzt()[:16]
    vid = con.execute(f"INSERT INTO as_verbandbuch ({','.join(VB_FELDER)}, angelegt, von) VALUES ({','.join('?' * len(VB_FELDER))},?,?)",
                      [w[k] for k in VB_FELDER] + [jetzt(), wer]).lastrowid
    return {"id": vid}


def verbandbuch(con):
    grenze = (date.today() - timedelta(days=5 * 365 + 1)).isoformat()
    return [dict(r, abgelaufen=(r["zeit"] or "")[:10] < grenze) for r in con.execute("SELECT * FROM as_verbandbuch ORDER BY zeit DESC, id DESC")]


def verbandbuch_loeschen(con, vid):
    r = con.execute("SELECT zeit FROM as_verbandbuch WHERE id=?", (vid,)).fetchone()
    if not r:
        raise Fehler("Eintrag nicht gefunden.", 404)
    if (r["zeit"] or "")[:10] >= (date.today() - timedelta(days=5 * 365 + 1)).isoformat():
        raise Fehler("Einträge im Verbandbuch werden mindestens fünf Jahre aufbewahrt.", 409)
    con.execute("DELETE FROM as_verbandbuch WHERE id=?", (vid,))


# ---------------------------------------------------------------- Übersicht
def bedarf(n):
    ersthelfer = 0 if n < 2 else 1 if n <= 20 else math.ceil(n * 0.1)
    brandschutz = max(1, math.ceil(n * 0.05)) if n else 0
    return {"beschaeftigte": n, "ersthelfer": ersthelfer, "brandschutzhelfer": brandschutz, "sibe": n > 20}


def uebersicht(con, inhaber=False):
    heute = date.today().isoformat()
    bald = (date.today() + timedelta(days=30)).isoformat()
    punkte = []

    def p(stufe, text, link, datum=""):
        punkte.append({"stufe": stufe, "text": text, "link": link, "datum": datum})
    gbs = gb_liste(con)
    for g in gbs:
        if g["status"] == "archiv":
            continue
        if g["status"] in ("gueltig", "ueberarbeitung") and g["naechste"] and g["naechste"] < heute:
            p("rot", f"Gefährdungsbeurteilung {g['nummer']} {g['titel']}: Überprüfung war fällig am {de_datum(g['naechste'])}", f"#/arbeitsschutz/gb/{g['id']}", g["naechste"])
        elif g["status"] == "gueltig" and g["naechste"] and g["naechste"] <= bald:
            p("gelb", f"Gefährdungsbeurteilung {g['nummer']} {g['titel']}: Überprüfung fällig am {de_datum(g['naechste'])}", f"#/arbeitsschutz/gb/{g['id']}", g["naechste"])
        if g["status"] == "entwurf":
            p("gelb", f"Gefährdungsbeurteilung {g['nummer']} {g['titel']} ist noch nicht freigegeben", f"#/arbeitsschutz/gb/{g['id']}")
        if g["status"] == "ueberarbeitung":
            p("info", f"Gefährdungsbeurteilung {g['nummer']} {g['titel']} wird überarbeitet (neue Freigabe nötig)", f"#/arbeitsschutz/gb/{g['id']}")
        if g["offen"]["ueberfaellig"]:
            p("rot", f"{g['nummer']} {g['titel']}: {g['offen']['ueberfaellig']} Maßnahme(n) überfällig", f"#/arbeitsschutz/gb/{g['id']}")
        elif g["offen"]["umsetzen"]:
            p("info", f"{g['nummer']} {g['titel']}: {g['offen']['umsetzen']} Maßnahme(n) umzusetzen", f"#/arbeitsschutz/gb/{g['id']}")
    mit_gb = {w for g in gbs if g["status"] != "archiv" for w in g["werkzeug_ids"]}
    maschinen = [dict(r) for r in con.execute("SELECT id, nummer, bezeichnung FROM werkzeuge WHERE art='Stationäre Maschine' AND IFNULL(status,'') NOT IN ('ausgemustert','defekt') ORDER BY nummer")]
    ohne_gb = [m for m in maschinen if m["id"] not in mit_gb]
    if ohne_gb:
        p("gelb", f"{len(ohne_gb)} Maschine(n) ohne Gefährdungsbeurteilung: " + ", ".join(m["bezeichnung"] for m in ohne_gb[:6]) + (" …" if len(ohne_gb) > 6 else ""), "#/arbeitsschutz/gb")
    pr = con.execute("SELECT COUNT(*) FROM werkzeuge WHERE pruefung_bis<>'' AND pruefung_bis<? AND IFNULL(status,'') NOT IN ('ausgemustert')", (heute,)).fetchone()[0]
    if pr:
        p("rot", f"{pr} Arbeitsmittel mit überfälliger Prüfung", "#/material/werkzeuge")
    m = matrix(con)
    fehlt = sum(1 for z in m["zeilen"] for f in z["themen"].values() if f["status"] == "fehlt")
    ueber = sum(1 for z in m["zeilen"] for f in z["themen"].values() if f["status"] == "ueberfaellig")
    baldu = sum(1 for z in m["zeilen"] for f in z["themen"].values() if f["status"] == "bald")
    if fehlt:
        p("rot", f"{fehlt} Unterweisung(en) noch nie durchgeführt (Erstunterweisung)", "#/arbeitsschutz/unterweisungen")
    if ueber:
        p("rot", f"{ueber} Unterweisung(en) überfällig", "#/arbeitsschutz/unterweisungen")
    if baldu:
        p("gelb", f"{baldu} Unterweisung(en) in den nächsten 30 Tagen fällig", "#/arbeitsschutz/unterweisungen")
    offen_u = con.execute("SELECT COUNT(*) FROM as_unterweisungen WHERE status='offen'").fetchone()[0]
    if offen_u:
        p("info", f"{offen_u} Unterweisung(en) noch nicht abgeschlossen (Unterschriften fehlen)", "#/arbeitsschutz/unterweisungen/liste")
    vz = verzeichnis(con)
    ohne_sdb = [x for x in vz if not x["sdb"]]
    if ohne_sdb:
        p("rot", f"{len(ohne_sdb)} Gefahrstoff(e) ohne Sicherheitsdatenblatt: " + ", ".join(x["name"] for x in ohne_sdb[:5]), "#/arbeitsschutz/gefahrstoffe")
    alt = [x for x in vz if x["sdb"] and (x["sdb"]["ausgabe"] or x["sdb"]["angelegt"][:10]) < (date.today() - timedelta(days=3 * 365)).isoformat()]
    if alt:
        p("info", f"{len(alt)} Sicherheitsdatenblatt/-blätter älter als drei Jahre – beim Lieferanten nach einer aktuellen Fassung fragen", "#/arbeitsschutz/gefahrstoffe")
    ohne_ba = [x for x in vz if not x["ba"] or x["ba"]["status"] == "entwurf"]
    if ohne_ba:
        p("gelb", f"{len(ohne_ba)} Gefahrstoff(e) ohne freigegebene Betriebsanweisung", "#/arbeitsschutz/gefahrstoffe")
    qs = qualifikationen(con)
    for q in qs:
        if q["gueltig_bis"] and q["gueltig_bis"] < heute:
            p("rot", f"{q['art']} {q['name']}: abgelaufen am {de_datum(q['gueltig_bis'])}", "#/arbeitsschutz/nachweise", q["gueltig_bis"])
        elif q["gueltig_bis"] and q["gueltig_bis"] <= (date.today() + timedelta(days=60)).isoformat():
            p("gelb", f"{q['art']} {q['name']}: gültig bis {de_datum(q['gueltig_bis'])} – Fortbildung planen", "#/arbeitsschutz/nachweise", q["gueltig_bis"])
    if inhaber:
        n_alt = sum(1 for x in verbandbuch(con) if x["abgelaufen"])
        if n_alt:
            p("info", f"{n_alt} Eintrag/Einträge im Verbandbuch älter als fünf Jahre (können gelöscht werden)", "#/arbeitsschutz/notfall")
    reihen = {"rot": 0, "gelb": 1, "info": 2}
    punkte.sort(key=lambda x: (reihen[x["stufe"]], x["datum"] or "9999"))

    # Grundpflichten
    org, nf = organisation(con), notfall(con)
    n = len([x for x in mitarbeiter_liste(con) if not x["inhaber"]]) + (1 if any(x["inhaber"] for x in mitarbeiter_liste(con)) else 0)
    b = bedarf(n)
    eh = len({q["mitarbeiter_id"] or q["name"] for q in qs if q["art"] == "Ersthelfer" and q["gueltig"]})
    bh = len({q["mitarbeiter_id"] or q["name"] for q in qs if q["art"] == "Brandschutzhelfer" and q["gueltig"]})
    sb = any(q["art"] == "Sicherheitsbeauftragter" and q["gueltig"] for q in qs)
    gueltige = [g for g in gbs if g["status"] in ("gueltig", "ueberarbeitung") and g["fassungen"]]
    psych = any(g["art"] == "psychisch" for g in gueltige)
    pflichten = [
        {"text": "Sicherheitstechnische und betriebsärztliche Betreuung festgelegt", "ok": bool(org["betreuung"]),
         "hinweis": org["betreuung"] or "Regelbetreuung oder alternative bedarfsorientierte Betreuung (Unternehmermodell der Berufsgenossenschaft)", "link": "#/arbeitsschutz/nachweise"},
        {"text": "Fachkraft für Arbeitssicherheit und Betriebsarzt benannt", "ok": bool(org["fasi"] and org["betriebsarzt"]) or (org["betreuung"].startswith("Unternehmermodell") and bool(org["betriebsarzt"] or org["fasi"])),
         "hinweis": " · ".join(x for x in (org["fasi"], org["betriebsarzt"]) if x) or "beim Unternehmermodell: Ansprechpartner für den Bedarfsfall", "link": "#/arbeitsschutz/nachweise"},
        {"text": f"Ersthelfer ({eh} von mindestens {b['ersthelfer']})", "ok": eh >= b["ersthelfer"], "hinweis": "Aus- und Fortbildung alle zwei Jahre", "link": "#/arbeitsschutz/nachweise"},
        {"text": f"Brandschutzhelfer ({bh} von mindestens {b['brandschutzhelfer']})", "ok": bh >= b["brandschutzhelfer"], "hinweis": "in der Regel 5 % der Beschäftigten", "link": "#/arbeitsschutz/nachweise"},
    ]
    if b["sibe"]:
        pflichten.append({"text": "Sicherheitsbeauftragter bestellt (ab 21 Beschäftigten)", "ok": sb, "hinweis": "", "link": "#/arbeitsschutz/nachweise"})
    pflichten += [
        {"text": "Notfall-Aushang (Rufnummern, Ersthelfer) ausgefüllt", "ok": bool(nf.get("unfall") and nf.get("rettung")), "hinweis": "", "link": "#/arbeitsschutz/notfall"},
        {"text": "Gefährdungsbeurteilungen freigegeben", "ok": bool(gueltige) and not ohne_gb, "hinweis": f"{len(gueltige)} freigegeben" + (f", {len(ohne_gb)} Maschine(n) ohne" if ohne_gb else ""), "link": "#/arbeitsschutz/gb"},
        {"text": "Psychische Belastung beurteilt", "ok": psych, "hinweis": "Checkliste der Berufsgenossenschaft", "link": "#/arbeitsschutz/gb"},
        {"text": "Gefahrstoffverzeichnis mit Sicherheitsdatenblättern", "ok": None if not vz else not ohne_sdb, "hinweis": f"{len(vz)} Gefahrstoff(e)" if vz else "noch keine Gefahrstoffe erfasst", "link": "#/arbeitsschutz/gefahrstoffe"},
        {"text": "Betriebsanweisungen für Gefahrstoffe", "ok": None if not vz else not ohne_ba, "hinweis": "", "link": "#/arbeitsschutz/ba"},
        {"text": "Unterweisungen aktuell", "ok": None if not m["themen"] else not (fehlt or ueber), "hinweis": "mindestens jährlich, Jugendliche halbjährlich" if m["themen"] else "noch keine Unterweisungsthemen angelegt", "link": "#/arbeitsschutz/unterweisungen"},
        {"text": "Prüfung der Arbeitsmittel aktuell", "ok": not pr, "hinweis": "Prüftermine stehen bei den Werkzeugen", "link": "#/material/werkzeuge"},
    ]
    return {"punkte": punkte, "pflichten": pflichten, "bedarf": b, "zahlen": {"gb": len([g for g in gbs if g["status"] != "archiv"]), "maschinen_ohne_gb": ohne_gb,
            "gefahrstoffe": len(vz), "unterweisungen_offen": offen_u}}


# ---------------------------------------------------------------- Stempeluhr (Mitarbeiter)
def fuer_mitarbeiter(con, mid):
    return {"unterweisungen": offene_fuer(con, mid),
            "betriebsanweisungen": [{"id": b["id"], "nummer": b["nummer"], "titel": b["titel"], "art_name": b["art_name"]} for b in ba_liste(con, True)],
            "gefahrstoffe": [{"id": x["material_id"], "name": x["name"], "ghs": x["ghs"], "sdb": (x["sdb"] or {}).get("id"), "tdb": (x["tdb"] or {}).get("id"),
                              "ba": x["ba"]["id"] if x["ba"] and x["ba"]["status"] != "entwurf" else None} for x in verzeichnis(con)]}


# ---------------------------------------------------------------- Druckseiten (HTML → PDF)
CSS = """
@page { size: A4; margin: 12mm 12mm 14mm 14mm; }
body { font: 9pt/1.35 Calibri, "Segoe UI", Arial, sans-serif; color: #222; margin: 0; }
.kopf { display:flex; justify-content:space-between; align-items:flex-end; border-bottom:.8pt solid #333; padding-bottom:2mm; margin-bottom:3mm; gap:6mm } .kopf > div:last-child { flex:0 0 auto; white-space:nowrap }
h1 { font-size:14pt; margin:0; } h2 { font-size:10.5pt; margin:4mm 0 1.5mm; } .unter { color:#555; }
table { border-collapse:collapse; width:100%; } th { text-align:left; font-size:8pt; border-bottom:.8pt solid #333; padding:1mm 1.2mm; vertical-align:bottom }
td { padding:1mm 1.2mm; border-bottom:.25pt solid #ccc; vertical-align:top } .k { color:#666; font-size:7.8pt } .nw { white-space:nowrap }
ul { margin:0; padding-left:4.5mm } li { margin:.4mm 0 }
.ok { color:#2e6b2e } .rot { color:#a33 } .klein { font-size:7.6pt; color:#555 }
.sig { display:flex; gap:10mm; margin-top:8mm; page-break-inside:avoid } .sig > div { flex:1 } .sig img { height:16mm; display:block }
.sig .linie { border-top:.6pt solid #333; padding-top:1mm; font-size:7.8pt; color:#444 }
.pz img { height:13mm; margin-right:1.5mm }
"""


DRUCK_SKRIPT = kern.skript(kern.DRUCKEN_JS)


def seite(titel, kopf_rechts, inhalt, firma, als_pdf, quer=False, extra_css=""):
    vorschau = "" if als_pdf else ("html{background:#888} body{background:#fff;width:%s;margin:10mm auto;padding:12mm 12mm 14mm 14mm;box-sizing:border-box;box-shadow:0 2px 12px rgba(0,0,0,.3)}"
                                   % ("297mm" if quer else "210mm"))
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8"><title>{h(titel)}</title><style>{CSS}{"@page{size:A4 landscape}" if quer else ""}{vorschau}{extra_css}</style></head><body>'
            f'<div class="kopf"><div><h1>{h(titel)}</h1></div><div class="unter" style="text-align:right">{h(firma)}<br>{kopf_rechts}</div></div>{inhalt}'
            + ("" if als_pdf else DRUCK_SKRIPT) + "</body></html>")


def sig_block(daten, sig, beschriftung):
    bild = unterschrift.bild_url(sig_ordner(daten), sig) if sig else ""
    return (f'<div>{f"<img src={chr(34)}{bild}{chr(34)} alt={chr(34)}Unterschrift{chr(34)}>" if bild else "<div style=height:16mm></div>"}'
            f'<div class="linie">{h(beschriftung)}{(": " + h(sig["name"]) + ", " + de_datum(sig["zeit"]) + " " + sig["zeit"][11:16] + " Uhr") if sig else ""}</div></div>')


def gb_html(con, daten, g, firma, als_pdf, fassung_info=None):
    """g: aktuelle GB (gb_laden) oder Inhalt einer Fassung."""
    risiko = {"gering": "gering", "mittel": "mittel", "hoch": "hoch"}
    st = {"vorhanden": "✓ vorhanden", "umsetzen": "umsetzen", "entfaellt": "entfällt", "offen": "noch offen"}
    psych = g.get("art") == "psychisch"
    zeilen = []
    gruppe = None
    for z in g["zeilen"]:
        if psych and z.get("gruppe") != gruppe:
            gruppe = z.get("gruppe")
            zeilen.append(f'<tr><td colspan="6" style="background:#efebe5"><b>{h(gruppe)}</b></td></tr>')
        ms = z.get("m") or []
        trifft = "" if not psych else ("<br><b>trifft zu</b>" + (" – automatischer Handlungsbedarf" if z.get("auto") else "") if z.get("trifft")
                                         else "<br>trifft nicht zu" if z.get("trifft") is False else "<br>nicht beantwortet")
        erst = f'<td rowspan="{max(1, len(ms))}"><b>{h(z.get("g"))}</b>{trifft}{("<div class=k>" + h(z.get("quelle")) + "</div>") if z.get("quelle") and not psych else ""}</td>' \
               f'<td rowspan="{max(1, len(ms))}">{risiko.get(z.get("risiko"), "")}</td>'
        if not ms:
            zeilen.append(f"<tr>{erst}<td colspan='4' class='k'>{'keine Maßnahme erforderlich' if psych and z.get('trifft') is False else ''}</td></tr>")
            continue
        for i, m in enumerate(ms):
            wer = " · ".join(x for x in (m.get("wer"), ("bis " + de_datum(m["bis"])) if m.get("bis") else "", ("erledigt " + de_datum(m["erledigt"])) if m.get("erledigt") else "") if x)
            wirk = (("✓ " + de_datum(m.get("wirksam_am"))) + (" " + h(m.get("wirksam_wer")) if m.get("wirksam_wer") else "")) if m.get("wirksam") else ""
            zeilen.append(f'<tr>{erst if i == 0 else ""}<td>{h(m.get("t"))}</td><td class="nw">{h(m.get("art") or "")}</td>'
                          f'<td class="nw">{st.get(m.get("status"), "")}{("<div class=k>" + h(wer) + "</div>") if wer else ""}</td><td class="nw">{wirk}</td></tr>')
    werkz = ", ".join(f'{w["bezeichnung"]} ({w["nummer"]})' for w in g.get("werkzeuge") or [])
    kopfdaten = (f'<table style="margin-bottom:3mm"><tr><td class="k" style="width:28mm">Art</td><td>{h(g.get("art_name"))}</td><td class="k" style="width:28mm">Arbeitsbereich</td><td>{h(g.get("bereich"))}</td></tr>'
                 + (f'<tr><td class="k">Maschinen</td><td colspan="3">{h(werkz)}</td></tr>' if werkz else "")
                 + f'<tr><td class="k">Beteiligte</td><td>{h(g.get("beteiligte"))}</td><td class="k">Mitgeltend</td><td>{h(g.get("mitgeltend"))}</td></tr>'
                 + (f'<tr><td class="k">Grundlage</td><td colspan="3">{h(", ".join(g.get("vorlagen") or []))}</td></tr>' if g.get("vorlagen") else "")
                 + (f'<tr><td class="k">Bemerkung</td><td colspan="3">{h(g.get("bemerkung"))}</td></tr>' if g.get("bemerkung") else "") + "</table>")
    tabelle = (f'<table><tr><th style="width:26%">{"Merkmal (kritische Ausprägung)" if psych else "Gefährdung"}</th><th style="width:7%">Risiko</th><th>Schutzmaßnahme</th>'
               f'<th style="width:4%">T/O/P</th><th style="width:15%">Umsetzung</th><th style="width:11%">Wirksam</th></tr>{"".join(zeilen)}</table>')
    if fassung_info:
        sig = con.execute("SELECT * FROM signaturen WHERE id=?", (fassung_info["signatur_id"],)).fetchone()
        unten = (f'<div class="sig">{sig_block(daten, dict(sig) if sig else None, "Freigegeben (Unternehmer)")}'
                 f'<div class="klein">Fassung {fassung_info["nr"]} vom {de_datum(g.get("stand"))} · nächste Überprüfung {de_datum(g.get("naechste"))}<br>'
                 f'Prüfsumme {fassung_info["sha256"][:16]}{"" if fassung_info.get("unverändert", True) else " <b class=rot>– Inhalt verändert!</b>"}</div></div>')
        rechts = f'Fassung {fassung_info["nr"]} · Stand {de_datum(g.get("stand"))}'
    else:
        unten = '<p class="klein">Arbeitsfassung – noch nicht freigegeben. Gültig ist die zuletzt freigegebene Fassung.</p>' if g.get("status") != "gueltig" else ""
        rechts = f'{h(g.get("status_name", ""))}' + (f' · Stand {de_datum(g.get("stand"))}' if g.get("stand") else "")
    erl = '<p class="klein">T = technische, O = organisatorische, P = personenbezogene Maßnahme. Risiko: Einschätzung ohne zusätzliche Maßnahmen.</p>'
    return seite(f'Gefährdungsbeurteilung {g.get("nummer", "")} {g.get("titel", "")}', rechts, kopfdaten + tabelle + erl + unten, firma, als_pdf, quer=True)


def ba_html(con, daten, b, firma, als_pdf, fassung_info=None):
    farbe = "#c8501e" if b.get("art") == "gefahrstoff" else "#1f5aa6"
    gl = b.get("gliederung") or BA_ABSCHNITTE.get(b.get("art"), BA_ABSCHNITTE["maschine"])
    symbole = b.get("symbole") or []
    ghs = [s for s in symbole if s.startswith("GHS")]
    sonst = [s for s in symbole if not s.startswith("GHS")]
    teile = []
    for k, titel in gl:
        text = str((b.get("abschnitte") or {}).get(k) or "").strip()
        zeilen = [z.strip().lstrip("•-* ") for z in text.splitlines() if z.strip()]
        bilder = ""
        if k == "gefahren" and ghs:
            bilder = '<div class="pz">' + "".join(f'<img src="/arbeitsschutz/zeichen/{h(s)}.png" alt="{h(s)}">' for s in ghs) + "</div>"
        if k == "schutz" and sonst:
            bilder = '<div class="pz">' + "".join(f'<img src="/arbeitsschutz/zeichen/{h(s)}.png" alt="{h(s)}">' for s in sonst) + "</div>"
        inhalt = (f"<b>{h(zeilen[0])}</b>" if k in ("stoff",) and zeilen else
                  "<ul>" + "".join(f"<li>{h(z)}</li>" for z in zeilen) + "</ul>" if len(zeilen) > 1 or k not in ("anwendung",) else h(zeilen[0] if zeilen else ""))
        teile.append(f'<div class="ab"><div class="abk">{h(titel)}</div><div class="abi">{bilder}<div style="flex:1">{inhalt}</div></div></div>')
    rechts = f'Nr. {h(b.get("nummer"))}' + (f' · Stand {de_datum(b.get("stand"))}' if b.get("stand") else "")
    extra = (".ab{border:1.6pt solid F;border-top:0} .ab:first-of-type{border-top:1.6pt solid F} "
             ".abk{background:F;color:#fff;font-weight:700;text-align:center;padding:1mm;font-size:10pt;letter-spacing:.03em} "
             ".abi{display:flex;gap:3mm;padding:2mm 3mm;min-height:10mm;align-items:flex-start} .abi .pz{display:flex;flex-direction:column;gap:1.5mm;flex:0 0 14mm} "
             ".abi .pz img{width:14mm;height:14mm;margin:0} .bkopf{background:F;color:#fff;text-align:center;padding:2mm;font-size:13pt;font-weight:700} "
             ".bkopf small{display:block;font-size:9pt;font-weight:400}").replace("F", farbe)
    sig = ""
    if fassung_info:
        s = con.execute("SELECT * FROM signaturen WHERE id=?", (fassung_info["signatur_id"],)).fetchone()
        sig = f'<div class="sig">{sig_block(daten, dict(s) if s else None, "Freigegeben (Unternehmer)")}<div class="klein">Fassung {fassung_info["nr"]} · Prüfsumme {fassung_info["sha256"][:16]}</div></div>'
    elif b.get("status") != "gueltig":
        sig = '<p class="klein">Entwurf – noch nicht freigegeben.</p>'
    inhalt = (f'<div class="bkopf">BETRIEBSANWEISUNG<small>{h(b.get("art_name"))} · {h(b.get("titel"))}{" · Arbeitsbereich: " + h(b["bereich"]) if b.get("bereich") else ""}</small></div>'
              + "".join(teile) + sig)
    return seite(f'Betriebsanweisung {b.get("titel", "")}', rechts, inhalt, firma, als_pdf, extra_css=extra)


def unterweisung_html(con, daten, u, firma, als_pdf):
    th = "".join(f'<h2>{h(t["titel"])}</h2>' + "".join((f'<div class="k" style="margin-top:1mm"><b>{h(a["titel"])}</b></div>' if a.get("titel") else "")
                                                     + "<ul>" + "".join(f"<li>{h(p)}</li>" for p in a.get("punkte") or []) + "</ul>" for a in t.get("abschnitte") or [])
                 + ("<div class=k>Betriebsanweisungen: " + h(", ".join(f'{b["nummer"]} {b["titel"]}' for b in t["ba"])) + "</div>" if t.get("ba") else "")
                 for t in u["inhalt"])
    if u.get("ergaenzung"):
        th += f'<h2>Ergänzungen</h2><div>{h(u["ergaenzung"]).replace(chr(10), "<br>")}</div>'
    tn = []
    for t in u["teilnehmer"]:
        s = con.execute("SELECT * FROM signaturen WHERE id=?", (t["signatur_id"],)).fetchone() if t["signatur_id"] else None
        bild = unterschrift.bild_url(sig_ordner(daten), dict(s)) if s else ""
        tn.append(f'<tr><td>{h(t["name"])}</td><td>{f"<img src={chr(34)}{bild}{chr(34)} style=height:11mm>" if bild else ""}</td>'
                  f'<td class="nw">{(de_datum(t["unterschrieben"]) + " " + t["unterschrieben"][11:16]) if t["unterschrieben"] else "<span class=k>offen</span>"}</td></tr>')
    sig = unterschrift.letzte(con, "unterweisung", u["id"], "unterweiser")
    kopfdaten = (f'<table style="margin-bottom:2mm"><tr><td class="k" style="width:30mm">Datum</td><td>{de_datum(u["datum"])}</td><td class="k" style="width:30mm">Anlass</td><td>{h(u["anlass"])}</td></tr>'
                 f'<tr><td class="k">Unterweisende Person</td><td>{h(u["unterweiser"])}</td><td class="k">Ort / Dauer</td><td>{h(" · ".join(x for x in (u["ort"], u["dauer"]) if x))}</td></tr>'
                 + (f'<tr><td class="k">Verständnis geprüft</td><td colspan="3">{h(u["verstaendnis"])}</td></tr>' if u.get("verstaendnis") else "") + "</table>"
                 '<p class="klein">Unterweisung nach § 12 ArbSchG und § 4 DGUV Vorschrift 1' + (", § 14 GefStoffV" if any("GefStoffV" in t["titel"] for t in u["inhalt"]) else "")
                 + (", § 29 JArbSchG" if "JArbSchG" in (u.get("anlass") or "") else "") + "</p>")
    unten = (f'<h2>Teilnehmer</h2><p class="klein">Mit der Unterschrift bestätigt die Person, dass sie an der Unterweisung teilgenommen und den Inhalt verstanden hat.</p>'
             f'<table><tr><th>Name</th><th>Unterschrift</th><th>Datum</th></tr>{"".join(tn)}</table>'
             f'<div class="sig">{sig_block(daten, sig, "Unterweisende Person")}<div class="klein">Nr. {h(u["nummer"])} · {"abgeschlossen am " + de_datum(u["abgeschlossen"]) if u["status"] == "abgeschlossen" else "noch nicht abgeschlossen"}'
             f'<br>Prüfsumme Inhalt {u["inhalt_hash"][:16]}</div></div>')
    return seite(f'Unterweisungsnachweis: {u["titel"]}', f'Nr. {h(u["nummer"])}', kopfdaten + th + unten, firma, als_pdf)


def verzeichnis_html(con, firma, als_pdf):
    zeilen = []
    for x in verzeichnis(con):
        zeilen.append(f'<tr><td><b>{h(x["name"])}</b><div class="k">{h(x["nummer"])}{" · " + h(x["lieferant"]) if x["lieferant"] else ""}</div></td>'
                      f'<td class="pz">{"".join(f"<img src=/arbeitsschutz/zeichen/{h(s)}.png style=height:8mm>" for s in x["ghs"])}</td>'
                      f'<td>{h(x["signalwort"])}</td><td>{h(", ".join(h_codes(x["h_saetze"])) or x["h_saetze"])}</td><td>{h(x["menge"])}</td><td>{h(x["bereich"])}</td>'
                      f'<td class="nw">{h(x["lagerklasse"])}{" · " + h(x["wgk"]) if x["wgk"] else ""}</td>'
                      f'<td class="nw">{de_datum((x["sdb"] or {}).get("ausgabe") or ((x["sdb"] or {}).get("angelegt") or "")[:10]) if x["sdb"] else "<b class=rot>fehlt</b>"}</td>'
                      f'<td class="nw">{h(x["ba"]["nummer"]) if x["ba"] else "–"}</td></tr>')
    inhalt = (f'<p class="klein">Verzeichnis nach § 6 Abs. 12 Gefahrstoffverordnung. Die Sicherheitsdatenblätter sind im Programm beim jeweiligen Material hinterlegt.</p>'
              f'<table><tr><th>Gefahrstoff</th><th>Piktogramme</th><th>Signalwort</th><th>H-Sätze</th><th>Menge (Bereich)</th><th>Arbeitsbereich</th><th>Lagerklasse / WGK</th>'
              f'<th>SDB vom</th><th>BA</th></tr>{"".join(zeilen) or "<tr><td colspan=9>Noch keine Gefahrstoffe erfasst.</td></tr>"}</table>')
    return seite("Gefahrstoffverzeichnis", f"Stand {date.today().strftime('%d.%m.%Y')}", inhalt, firma, als_pdf, quer=True)


def notfall_html(con, firma, als_pdf):
    nf = dict(notfall(con))
    eh = [q["name"] for q in qualifikationen(con) if q["art"] == "Ersthelfer" and q["gueltig"]]
    if eh and not (nf.get("ersthelfer1") or nf.get("ersthelfer2")):
        nf["ersthelfer1"] = ", ".join(eh)   # aus den Nachweisen, solange im Aushang nichts eingetragen ist
    zeilen = "".join(f'<tr><td style="width:45%;font-size:11pt">{h(t)}</td><td style="font-size:13pt"><b>{h(nf.get(k, ""))}</b></td></tr>' for k, t in vorlagen()["notfall"] if nf.get(k))
    inhalt = (f'<div style="background:#1f7a3a;color:#fff;text-align:center;padding:4mm;font-size:22pt;font-weight:700">NOTFALL<br><span style="font-size:13pt">Rufnummern</span></div>'
              f'<div style="display:flex;gap:6mm;align-items:center;margin:5mm 0"><img src="/arbeitsschutz/zeichen/E003.png" style="height:22mm"><img src="/arbeitsschutz/zeichen/E004.png" style="height:22mm">'
              f'<div style="font-size:26pt;font-weight:700;color:#a3231c">112 <span style="font-size:13pt;color:#222">Rettungsdienst / Feuerwehr</span><br>110 <span style="font-size:13pt;color:#222">Polizei</span></div></div>'
              f'<table>{zeilen}</table>'
              f'<h2 style="margin-top:6mm">Notruf: Wo? Was? Wie viele Verletzte? Welche Verletzungen? Warten auf Rückfragen!</h2>'
              f'<p>Jeden Unfall und jede Erste-Hilfe-Leistung melden und im Verbandbuch eintragen.</p>')
    return seite("Notfall – Erste Hilfe", f"Stand {date.today().strftime('%d.%m.%Y')}", inhalt, firma, als_pdf)
