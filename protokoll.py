"""Unveränderbares Protokoll (Journal) der GoBD-relevanten Vorgänge.

Jeder Eintrag wird doppelt gespeichert:
1. in der Tabelle `protokoll` der Datenbank – Trigger verhindern UPDATE und DELETE,
2. in der Journaldatei daten/protokoll/journal.jsonl (eine JSON-Zeile je Eintrag, nur Anhängen).
Die Einträge bilden eine Hash-Kette (SHA-256 über Inhalt + Hash des Vorgängers). Jede nachträgliche
Änderung, Löschung oder Umsortierung bricht die Kette und wird bei der Prüfung angezeigt.
Die Journaldatei wird weder von der Rücksicherung noch von „Testdaten löschen“ verändert; fehlen nach
einer Rücksicherung Einträge in der Datenbank, werden sie beim Start aus der Journaldatei nachgetragen.
"""
import hashlib
import json
import os
import threading
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS protokoll (
    nr INTEGER PRIMARY KEY,
    zeit TEXT NOT NULL, benutzer TEXT DEFAULT '', art TEXT NOT NULL, objekt TEXT DEFAULT '',
    text TEXT DEFAULT '', daten TEXT DEFAULT '{}', version TEXT DEFAULT '', vorher TEXT NOT NULL, hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS protokoll_kein_update BEFORE UPDATE ON protokoll
BEGIN SELECT RAISE(ABORT, 'Das Protokoll ist unveränderbar (GoBD).'); END;
CREATE TRIGGER IF NOT EXISTS protokoll_kein_loeschen BEFORE DELETE ON protokoll
BEGIN SELECT RAISE(ABORT, 'Das Protokoll ist unveränderbar (GoBD).'); END;
"""

ARTEN = {
    "datenbank": "Datenbank optimiert",
    "echtbetrieb": "Echtbetrieb begonnen",
    "festschreiben": "Rechnung festgeschrieben",
    "storno": "Rechnung storniert",
    "archiv_pdf": "Archiv-PDF erzeugt",
    "beleg_geloescht": "Beleg gelöscht",
    "zahlungsauftrag_geaendert": "Zahlungsauftrag geändert",
    "zahlungsauftrag_geloescht": "Zahlungsauftrag gelöscht",
    "zahlungseingang_geloescht": "Zahlungseingang gelöscht",
    "mahnung_geloescht": "Mahnung gelöscht",
    "nummernkreis": "Nummernkreis geändert",
    "sicherung": "Vollständige Sicherung",
    "sicherung_kennwort": "Sicherungskennwort",
    "ruecksicherung": "Rücksicherung",
    "projektsicherung": "Sicherung des Projektordners",
    "zahlungsauftrag_bezahlt": "Zahlungsauftrag bezahlt",
    "zahlungsauftrag_geoeffnet": "Zahlungsauftrag: bezahlt zurückgenommen",
    "lager_inventur": "Lager: Inventur",
    "lager_buchung_geloescht": "Lager: Buchung gelöscht",
    "zertifikat": "https-Zertifikat",
    "testdaten_geloescht": "Testdaten gelöscht",
    "version": "Programmversion gewechselt",
    "export": "Datenexport",
    "journal": "Journal",
    "datenauskunft": "Datenauskunft (Art. 15 DSGVO)",
    "kunde_anonymisiert": "Kunde anonymisiert (Art. 17 DSGVO)",
    "kunde_geloescht": "Kunde gelöscht",
    "aufbewahrung_geaendert": "Aufbewahrungsfrist Kunde",
    "as_gb_freigabe": "Arbeitsschutz: Gefährdungsbeurteilung freigegeben",
    "as_ba_freigabe": "Arbeitsschutz: Betriebsanweisung freigegeben",
    "as_unterweisung": "Arbeitsschutz: Unterweisung abgeschlossen",
    "unterschrift_monatsbeleg": "Monatsbeleg unterschrieben",
}
START = "0" * 64
_sperre = threading.Lock()
_pfad = {"datei": None}


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def _hash(e, vorher):
    inhalt = json.dumps([e["nr"], e["zeit"], e["benutzer"], e["art"], e["objekt"], e["text"], e["daten"], e["version"]],
                        ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((vorher + inhalt).encode("utf-8")).hexdigest()


def datei_lesen():
    p = _pfad["datei"]
    if not p or not os.path.exists(p):
        return []
    aus = []
    with open(p, "r", encoding="utf-8") as f:
        for z in f:
            z = z.strip()
            if z:
                try:
                    aus.append(json.loads(z))
                except ValueError:
                    aus.append({"_kaputt": z})
    return aus


def _datei_ab(offset):
    """Einträge der Journaldatei ab Byte-Position offset (für die Prüfung nur der neuen Einträge)."""
    aus = []
    with open(_pfad["datei"], "rb") as f:
        f.seek(offset)
        for z in f.read().decode("utf-8").splitlines():
            z = z.strip()
            if z:
                try:
                    aus.append(json.loads(z))
                except ValueError:
                    aus.append({"_kaputt": z})
    return aus


def _letzter_datei():
    """Letzter Eintrag der Journaldatei, ohne die ganze Datei zu lesen."""
    p = _pfad["datei"]
    if not p or not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos, rest = f.tell(), b""
        while pos > 0:
            n = min(8192, pos)
            pos -= n
            f.seek(pos)
            rest = f.read(n) + rest
            zeilen = [z for z in rest.split(b"\n") if z.strip()]
            if len(zeilen) > 1 or (zeilen and pos == 0):
                try:
                    return json.loads(zeilen[-1].decode("utf-8"))
                except ValueError:
                    return None
    return None


def _anhaengen(e):
    with open(_pfad["datei"], "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _db_einfuegen(con, e):
    con.execute("INSERT OR IGNORE INTO protokoll (nr, zeit, benutzer, art, objekt, text, daten, version, vorher, hash) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (e["nr"], e["zeit"], e["benutzer"], e["art"], e["objekt"], e["text"],
                  json.dumps(e["daten"], ensure_ascii=False, sort_keys=True), e["version"], e["vorher"], e["hash"]))


def einrichten(con, daten_ordner, version):
    """Beim Start und nach einer Rücksicherung: Tabelle anlegen, Datei und Datenbank abgleichen."""
    ordner = os.path.join(daten_ordner, "protokoll")
    os.makedirs(ordner, exist_ok=True)
    _pfad["datei"] = os.path.join(ordner, "journal.jsonl")
    _STAND.clear()
    con.executescript(SCHEMA)
    with _sperre:
        datei = [e for e in datei_lesen() if "_kaputt" not in e]
        db_nr = {r[0] for r in con.execute("SELECT nr FROM protokoll")}
        # fehlende Einträge (z. B. nach einer Rücksicherung) aus der Journaldatei nachtragen
        for e in datei:
            if e.get("nr") not in db_nr:
                _db_einfuegen(con, e)
        # Journaldatei fehlt oder ist kürzer als die Datenbank: aus der Datenbank wiederherstellen und vermerken
        datei_nr = {e.get("nr") for e in datei}
        fehlend = [dict(r) for r in con.execute("SELECT * FROM protokoll ORDER BY nr") if r["nr"] not in datei_nr]
        if fehlend:
            for e in fehlend:
                e["daten"] = json.loads(e["daten"] or "{}")
                _anhaengen(e)
    if fehlend:
        eintragen(con, "journal", "", f"{len(fehlend)} Einträge fehlten in der Journaldatei und wurden aus der Datenbank wiederhergestellt.",
                  {"anzahl": len(fehlend)}, benutzer="Programm", version=version)


def neu_beginnen(con):
    """Protokoll der Testphase abschließen und leer neu beginnen (nur vor dem Echtbetrieb, vom Aufrufer zu prüfen).
    Die bisherige Journaldatei wird nicht gelöscht, sondern umbenannt (journal_testphase_<Zeit>.jsonl). Liefert (Anzahl, Dateiname)."""
    with _sperre:
        n = con.execute("SELECT COUNT(*) FROM protokoll").fetchone()[0]
        name = ""
        p = _pfad["datei"]
        if p and os.path.exists(p):
            name = f"journal_testphase_{datetime.now():%Y-%m-%d_%H%M%S}.jsonl"
            os.replace(p, os.path.join(os.path.dirname(p), name))
        con.execute("DROP TRIGGER IF EXISTS protokoll_kein_loeschen")
        con.execute("DELETE FROM protokoll")
        con.execute("CREATE TRIGGER IF NOT EXISTS protokoll_kein_loeschen BEFORE DELETE ON protokoll "
                    "BEGIN SELECT RAISE(ABORT, 'Das Protokoll ist unveränderbar (GoBD).'); END")
        _STAND.clear()
    return n, name


def letzter(con):
    r = con.execute("SELECT nr, hash FROM protokoll ORDER BY nr DESC LIMIT 1").fetchone()
    return (r["nr"], r["hash"]) if r else (0, START)


def eintragen(con, art, objekt, text, daten=None, benutzer="", version=""):
    """Schreibt einen Eintrag – zuerst in die Journaldatei (dauerhaft), dann in die Datenbank."""
    with _sperre:
        nr, vorher = letzter(con)
        zuletzt = _letzter_datei()
        if zuletzt and isinstance(zuletzt.get("nr"), int) and zuletzt["nr"] > nr:
            nr, vorher = zuletzt["nr"], zuletzt["hash"]
        e = {"nr": nr + 1, "zeit": jetzt(), "benutzer": benutzer or "", "art": art, "objekt": str(objekt or ""),
             "text": text or "", "daten": daten or {}, "version": version or "", "vorher": vorher}
        e["hash"] = _hash(e, vorher)
        _anhaengen(e)
        _db_einfuegen(con, e)
        return e


# Stand der letzten vollständigen, fehlerfreien Prüfung; danach werden beim Öffnen nur die neuen Einträge geprüft.
_STAND = {}


def pruefen(con, voll=False):
    """Prüft die Hash-Kette in Datenbank und Journaldatei und vergleicht beide.
    voll=False: nur die Einträge seit der letzten vollständigen Prüfung (die beim Programmstart im Hintergrund läuft)."""
    with _sperre:      # kein neuer Eintrag während der Prüfung
        return _pruefen(con, voll)


def _pruefen(con, voll):
    fehler = []
    p = _pfad["datei"]
    groesse = os.path.getsize(p) if p and os.path.exists(p) else 0
    st = dict(_STAND) if not voll else {}
    if st and (groesse < st["offset"] or st.get("datei") != p):
        st = {}
    ab_nr, start_hash = (st["nr"], st["hash"]) if st else (0, START)
    db = []
    for r in con.execute("SELECT * FROM protokoll WHERE nr>? ORDER BY nr", (ab_nr,)):
        e = dict(r)
        try:
            e["daten"] = json.loads(e["daten"] or "{}")
        except ValueError:
            e["daten"] = {}
        db.append(e)

    def kette(liste, name):
        vorher, nr = start_hash, ab_nr
        for e in liste:
            if "_kaputt" in e:
                fehler.append(f"{name}: unlesbare Zeile")
                continue
            nr += 1
            if e.get("nr") != nr:
                fehler.append(f"{name}: Eintrag {nr} fehlt oder Reihenfolge verändert (gefunden {e.get('nr')})")
                nr = e.get("nr") or nr
            if e.get("vorher") != vorher or _hash(e, vorher) != e.get("hash"):
                fehler.append(f"{name}: Eintrag {e.get('nr')} wurde verändert (Hash stimmt nicht)")
            vorher = e.get("hash") or vorher
        return vorher
    ende_db = kette(db, "Datenbank")
    datei = (_datei_ab(st["offset"]) if st else datei_lesen()) if groesse else []
    ende_datei = kette(datei, "Journaldatei")
    anzahl = ab_nr + len(db)
    gesamt_db = con.execute("SELECT COUNT(*) FROM protokoll").fetchone()[0]
    if gesamt_db != anzahl:
        fehler.append(f"Datenbank: {gesamt_db} Einträge, erwartet {anzahl} (Eintrag gelöscht oder eingefügt)")
    if len(datei) != len(db) or ende_db != ende_datei:
        fehler.append(f"Datenbank ({anzahl} Einträge) und Journaldatei ({ab_nr + len(datei)} Einträge) stimmen nicht überein")
    ok = not fehler
    if ok:
        _STAND.update(nr=anzahl, hash=ende_db, offset=groesse, datei=p,
                      voll_zeit=st.get("voll_zeit") if st else datetime.now().isoformat(timespec="seconds"))
    elif not st:
        _STAND.clear()
    return {"ok": ok, "fehler": fehler[:20], "anzahl": anzahl, "letzter_hash": ende_db, "datei": p,
            "umfang": "neu" if st else "voll", "geprueft": len(db), "voll_zeit": _STAND.get("voll_zeit", "")}


def liste(con, art=None, von=None, bis=None, suche=None, limit=2000):
    sql, par = "SELECT * FROM protokoll WHERE 1=1", []
    if art:
        sql += " AND art=?"
        par.append(art)
    if von:
        sql += " AND zeit>=?"
        par.append(von)
    if bis:
        sql += " AND zeit<=?"
        par.append(bis + "T99")
    if suche:
        sql += " AND (ulower(text) LIKE ? OR ulower(objekt) LIKE ? OR ulower(benutzer) LIKE ?)"
        par += [f"%{suche.lower()}%"] * 3
    sql += " ORDER BY nr DESC LIMIT ?"
    par.append(limit)
    aus = []
    for r in con.execute(sql, par):
        e = dict(r)
        e["daten"] = json.loads(e["daten"] or "{}")
        e["art_name"] = ARTEN.get(e["art"], e["art"])
        aus.append(e)
    return aus


def echtbetrieb(con):
    """Seit wann läuft der Echtbetrieb? (Eintrag in Datenbank ODER Journaldatei – überlebt Rücksicherungen)."""
    r = con.execute("SELECT zeit, benutzer FROM protokoll WHERE art='echtbetrieb' ORDER BY nr LIMIT 1").fetchone()
    if r:
        return {"seit": r["zeit"], "von": r["benutzer"]}
    for e in datei_lesen():
        if e.get("art") == "echtbetrieb":
            return {"seit": e.get("zeit"), "von": e.get("benutzer")}
    return None


def csv_text(con):
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Nr", "Zeit", "Benutzer", "Vorgang", "Objekt", "Text", "Daten", "Programmversion", "Hash Vorgänger", "Hash"])
    for e in reversed(liste(con, limit=10 ** 9)):
        w.writerow([e["nr"], e["zeit"], e["benutzer"], e["art_name"], e["objekt"], e["text"],
                    json.dumps(e["daten"], ensure_ascii=False, sort_keys=True), e["version"], e["vorher"], e["hash"]])
    return "﻿" + buf.getvalue()
