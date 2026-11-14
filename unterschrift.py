"""Digitale Unterschriften (am Tablet oder Handy mit Finger bzw. Stift).

Jede Unterschrift wird als PNG-Datei gespeichert und mit Zeitpunkt, Name, angemeldetem Benutzer, Gerät und einem
Fingerabdruck (SHA-256) des unterschriebenen Inhalts festgehalten. Unterschriften werden nie geändert oder gelöscht;
eine erneute Unterschrift (z. B. nach einer Korrektur) kommt als weiterer Eintrag hinzu.
"""
import base64
import hashlib
import json
import os
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS signaturen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    art TEXT NOT NULL,            -- monatsbeleg, unterweisung, gb_freigabe, ba_freigabe
    bezug TEXT NOT NULL,          -- z. B. "12:2026-10" (Mitarbeiter:Monat) oder die ID des Dokuments
    rolle TEXT DEFAULT '',        -- mitarbeiter, arbeitgeber, teilnehmer, unterweiser, unternehmer
    name TEXT DEFAULT '',
    benutzer TEXT DEFAULT '',     -- angemeldeter Benutzer beim Unterschreiben
    mitarbeiter_id INTEGER,
    datei TEXT DEFAULT '',
    bild_sha256 TEXT DEFAULT '',
    inhalt_sha256 TEXT DEFAULT '',
    geraet TEXT DEFAULT '',
    zeit TEXT
);
CREATE INDEX IF NOT EXISTS signaturen_bezug ON signaturen(art, bezug);
"""


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def schema(con):
    con.executescript(SCHEMA)


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def inhalt_hash(obj):
    """Fingerabdruck eines Inhalts (JSON, Schlüssel sortiert) – zeigt später, ob sich der Inhalt nach der Unterschrift geändert hat."""
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def png_pruefen(b64):
    try:
        roh = base64.b64decode((b64 or "").split(",")[-1], validate=False)
    except (ValueError, TypeError):
        roh = b""
    if roh[:8] != b"\x89PNG\r\n\x1a\n" or len(roh) < 200:
        raise Fehler("Die Unterschrift fehlt. Bitte im Feld unterschreiben.")
    if len(roh) > 3 * 1024 * 1024:
        raise Fehler("Die Unterschrift ist zu groß.")
    return roh


def speichern(con, ordner, art, bezug, rolle, name, png_b64, benutzer="", mitarbeiter_id=None, inhalt_sha="", geraet=""):
    name = str(name or "").strip()
    if not name:
        raise Fehler("Bitte den Namen angeben.")
    roh = png_pruefen(png_b64)
    os.makedirs(ordner, exist_ok=True)
    zeit = jetzt()
    bild_sha = hashlib.sha256(roh).hexdigest()
    datei = f"{art}_{str(bezug).replace(':', '-').replace('/', '-')}_{rolle}_{zeit.replace(':', '').replace('-', '')}_{bild_sha[:8]}.png"
    with open(os.path.join(ordner, datei), "wb") as f:
        f.write(roh)
    sid = con.execute("INSERT INTO signaturen (art, bezug, rolle, name, benutzer, mitarbeiter_id, datei, bild_sha256, inhalt_sha256, geraet, zeit) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (art, str(bezug), rolle, name[:120], benutzer or "", mitarbeiter_id, datei, bild_sha, inhalt_sha or "", (geraet or "")[:200], zeit)).lastrowid
    return dict(con.execute("SELECT * FROM signaturen WHERE id=?", (sid,)).fetchone())


def liste(con, art, bezug):
    return [dict(r) for r in con.execute("SELECT * FROM signaturen WHERE art=? AND bezug=? ORDER BY id", (art, str(bezug)))]


def letzte(con, art, bezug, rolle, mitarbeiter_id=None):
    sql = "SELECT * FROM signaturen WHERE art=? AND bezug=? AND rolle=?"
    p = [art, str(bezug), rolle]
    if mitarbeiter_id:
        sql += " AND mitarbeiter_id=?"
        p.append(mitarbeiter_id)
    r = con.execute(sql + " ORDER BY id DESC LIMIT 1", p).fetchone()
    return dict(r) if r else None


def bild_url(ordner, sig):
    """Unterschrift als data-URL zum Einbetten in HTML/PDF (prüft dabei, ob die Bilddatei unverändert ist)."""
    if not sig or not sig.get("datei"):
        return ""
    pfad = os.path.join(ordner, os.path.basename(sig["datei"]))
    if not os.path.exists(pfad):
        return ""
    with open(pfad, "rb") as f:
        roh = f.read()
    if sig.get("bild_sha256") and hashlib.sha256(roh).hexdigest() != sig["bild_sha256"]:
        return ""
    return "data:image/png;base64," + base64.b64encode(roh).decode("ascii")


def oeffentlich(sig):
    """Was das Programm über eine Unterschrift anzeigt (ohne Dateinamen)."""
    if not sig:
        return None
    return {k: sig.get(k) for k in ("id", "rolle", "name", "benutzer", "mitarbeiter_id", "zeit", "inhalt_sha256")}
