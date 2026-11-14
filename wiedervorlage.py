"""Jahresring – Wiedervorlagen nach Abschluss eines Auftrags (Nachfrage, Pflegeangebot, Ende der Gewährleistung).

Beim Festschreiben einer Rechnung (nicht Abschlag, Storno, Korrektur) legt das Programm die in den Einstellungen
aktivierten Wiedervorlagen an, gerechnet ab Leistungsdatum. Fällige stehen auf der Startseite; dort und im Auftrag lassen
sie sich erledigen oder verschieben. Wird die Rechnung storniert, fallen ihre offenen Wiedervorlagen weg.
"""
from datetime import date, datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS wiedervorlagen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auftrag_id INTEGER, kunde_id INTEGER, beleg_id INTEGER,
    art TEXT DEFAULT '', datum TEXT NOT NULL, text TEXT DEFAULT '',
    erledigt TEXT DEFAULT '', notiz TEXT DEFAULT '', angelegt TEXT, von TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_wiedervorlagen_datum ON wiedervorlagen(datum);
"""
REGELN = [
    {"art": "nachfrage", "text": "Beim Kunden nachfragen, ob alles passt – ggf. um eine Bewertung bitten", "tage": 30, "aktiv": True},
    {"art": "pflege", "text": "Pflege anbieten (z. B. geölte Flächen nachölen, Beschläge nachstellen)", "tage": 365, "aktiv": True},
    {"art": "gewaehrleistung", "text": "Gewährleistung endet bald – Abschlussbesichtigung anbieten", "tage": 700, "aktiv": True},
]
ARTEN = {"nachfrage": "Nachfrage", "pflege": "Pflege", "gewaehrleistung": "Gewährleistung", "eigen": "Wiedervorlage"}


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def schema(con):
    con.executescript(SCHEMA)


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def regeln(e):
    r = e.get("wiedervorlage_regeln")
    return r if isinstance(r, list) else REGELN


def nach_rechnung(con, b, e, wer=""):
    """Wiedervorlagen für eine festgeschriebene Rechnung anlegen (je Auftrag und Art nur einmal offen)."""
    if b.get("art") != "rechnung" or (b.get("daten") or {}).get("modus") == "berichtigen":
        return 0
    basis = date.fromisoformat((b.get("leistungsdatum") or b.get("datum") or date.today().isoformat())[:10])
    n = 0
    for r in regeln(e):
        if not r.get("aktiv") or not str(r.get("text") or "").strip():
            continue
        art = r.get("art") or "eigen"
        if con.execute("SELECT 1 FROM wiedervorlagen WHERE auftrag_id=? AND art=? AND erledigt=''", (b["auftrag_id"], art)).fetchone():
            continue
        tage = max(1, min(3650, int(r.get("tage") or 30)))
        con.execute("INSERT INTO wiedervorlagen (auftrag_id, kunde_id, beleg_id, art, datum, text, angelegt, von) VALUES (?,?,?,?,?,?,?,?)",
                    (b["auftrag_id"], b.get("kunde_id"), b["id"], art, (basis + timedelta(tage)).isoformat(), str(r["text"]).strip()[:300], jetzt(), wer))
        n += 1
    return n


def nach_storno(con, beleg_id):
    con.execute("DELETE FROM wiedervorlagen WHERE beleg_id=? AND erledigt=''", (beleg_id,))


def liste(con, q):
    sql = ("SELECT w.*, a.nummer AS auftragsnr, a.bezeichnung AS auftrag, k.kurzname AS kunde, k.telefon, k.email1 FROM wiedervorlagen w "
           "LEFT JOIN auftraege a ON a.id=w.auftrag_id LEFT JOIN kunden k ON k.id=COALESCE(w.kunde_id, a.kunde_id) WHERE 1=1")
    par = []
    if q.get("status", "offen") == "offen":
        sql += " AND w.erledigt=''"
    if q.get("bis"):
        sql += " AND w.datum<=?"
        par.append(q["bis"])
    if str(q.get("auftrag_id") or "").isdigit():
        sql += " AND w.auftrag_id=?"
        par.append(int(q["auftrag_id"]))
    if str(q.get("kunde_id") or "").isdigit():
        sql += " AND COALESCE(w.kunde_id, a.kunde_id)=?"
        par.append(int(q["kunde_id"]))
    sql += " ORDER BY w.erledigt<>'', w.datum, w.id LIMIT 500"
    aus = []
    for r in con.execute(sql, par):
        d = dict(r)
        d["art_name"] = ARTEN.get(d["art"], d["art"])
        d["telefon"] = (d.get("telefon") or "").split("\n")[0]
        aus.append(d)
    return aus


def api(con, methode, teile, q, d, wer=""):
    rid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
    if methode == "GET" and rid is None:
        return liste(con, q)
    if methode == "POST" and rid is None:
        datum = str(d.get("datum") or "")[:10]
        date.fromisoformat(datum)
        if not str(d.get("text") or "").strip():
            raise Fehler("Bitte einen Text eingeben.")
        aid = int(d["auftrag_id"]) if str(d.get("auftrag_id") or "").isdigit() else None
        kid = int(d["kunde_id"]) if str(d.get("kunde_id") or "").isdigit() else None
        if not aid and not kid:
            raise Fehler("Bitte einen Auftrag oder Kunden angeben.")
        cur = con.execute("INSERT INTO wiedervorlagen (auftrag_id, kunde_id, art, datum, text, angelegt, von) VALUES (?,?,?,?,?,?,?)",
                          (aid, kid, "eigen", datum, str(d["text"]).strip()[:300], jetzt(), wer))
        return {"id": cur.lastrowid}
    if rid and methode == "PUT":
        if not con.execute("SELECT 1 FROM wiedervorlagen WHERE id=?", (rid,)).fetchone():
            raise Fehler("Wiedervorlage nicht gefunden.", 404)
        w = {}
        if "datum" in d:
            date.fromisoformat(str(d["datum"])[:10])
            w["datum"] = str(d["datum"])[:10]
        if "text" in d:
            w["text"] = str(d["text"] or "").strip()[:300]
        if "notiz" in d:
            w["notiz"] = str(d["notiz"] or "")[:300]
        if "erledigt" in d:
            w["erledigt"] = date.today().isoformat() if d["erledigt"] else ""
        if w:
            con.execute(f"UPDATE wiedervorlagen SET {','.join(k + '=?' for k in w)} WHERE id=?", list(w.values()) + [rid])
        return {"ok": True}
    if rid and methode == "DELETE":
        con.execute("DELETE FROM wiedervorlagen WHERE id=?", (rid,))
        return {"ok": True}
    raise Fehler("Unbekannte Anfrage", 404)
