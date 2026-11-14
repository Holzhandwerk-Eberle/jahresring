"""Jahresring – Kontenplan (Sachkonten nach SKR 03 / SKR 04) für die Zuordnung von Kontobewegungen und den DATEV-Export.

Vorbelegt mit den Konten, die ein Handwerksbetrieb mit Einnahmen-Überschuss-Rechnung üblicherweise braucht; eigene
Konten lassen sich anlegen, ändern und ausblenden. Maßgeblich ist der Kontenplan der Steuerberatung – die Vorgaben sind
Vorschläge. „steuer“ bestimmt den BU-Schlüssel im DATEV-Export: auto = Automatikkonto (Steuer steckt im Konto),
v19/v7 = Vorsteuer 19/7 % (BU 9/8), u19/u7 = Umsatzsteuer 19/7 % (BU 3/2), leer = ohne Steuer.
"""
import re
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS konten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skr TEXT NOT NULL DEFAULT '03', nummer INTEGER NOT NULL, bezeichnung TEXT NOT NULL DEFAULT '',
    art TEXT DEFAULT 'aufwand', steuer TEXT DEFAULT '', aktiv INTEGER DEFAULT 1, eigen INTEGER DEFAULT 0, angelegt TEXT,
    UNIQUE(skr, nummer)
);
"""
ARTEN = {"erloes": "Erlöse", "aufwand": "Aufwand", "bank": "Bank / Kasse", "privat": "Privat", "steuer": "Steuern / Abgaben",
         "lohn": "Lohn", "anlage": "Anlagen", "sonstig": "Sonstiges"}
STEUER = {"": "ohne Steuer", "auto": "Automatikkonto", "v19": "19 % Vorsteuer", "v7": "7 % Vorsteuer", "u19": "19 % Umsatzsteuer", "u7": "7 % Umsatzsteuer"}
BU = {"v19": "9", "v7": "8", "u19": "3", "u7": "2"}

# (SKR03, SKR04, Bezeichnung, Art, Steuer)
STANDARD = [
    (1000, 1600, "Kasse", "bank", ""),
    (1200, 1800, "Bank", "bank", ""),
    (1360, 1460, "Geldtransit", "bank", ""),
    (1590, 1370, "Durchlaufende Posten", "sonstig", ""),
    (1800, 2100, "Privatentnahmen allgemein", "privat", ""),
    (1890, 2180, "Privateinlagen", "privat", ""),
    (1780, 3820, "Umsatzsteuer-Vorauszahlungen", "steuer", ""),
    (1790, 3841, "Umsatzsteuer Vorjahr", "steuer", ""),
    (1740, 3720, "Verbindlichkeiten aus Lohn und Gehalt", "lohn", ""),
    (1741, 3730, "Verbindlichkeiten aus Lohn- und Kirchensteuer", "lohn", ""),
    (1742, 3740, "Verbindlichkeiten im Rahmen der sozialen Sicherheit", "lohn", ""),
    (480, 670, "Geringwertige Wirtschaftsgüter", "anlage", "v19"),
    (3100, 5900, "Fremdleistungen", "aufwand", "v19"),
    (3200, 5200, "Wareneingang", "aufwand", ""),
    (3300, 5300, "Wareneingang 7 % Vorsteuer", "aufwand", "auto"),
    (3400, 5400, "Wareneingang 19 % Vorsteuer", "aufwand", "auto"),
    (4120, 6020, "Gehälter", "lohn", ""),
    (4130, 6110, "Gesetzliche soziale Aufwendungen", "lohn", ""),
    (4210, 6310, "Miete (unbewegliche Wirtschaftsgüter)", "aufwand", ""),
    (4240, 6325, "Gas, Strom, Wasser", "aufwand", "v19"),
    (4360, 6400, "Versicherungen", "aufwand", ""),
    (4380, 6420, "Beiträge", "aufwand", ""),
    (4390, 6430, "Sonstige Abgaben", "aufwand", ""),
    (4510, 7685, "Kfz-Steuer", "aufwand", ""),
    (4520, 6520, "Kfz-Versicherungen", "aufwand", ""),
    (4530, 6530, "Laufende Kfz-Betriebskosten", "aufwand", "v19"),
    (4540, 6540, "Kfz-Reparaturen", "aufwand", "v19"),
    (4600, 6600, "Werbekosten", "aufwand", "v19"),
    (4650, 6640, "Bewirtungskosten", "aufwand", "v19"),
    (4670, 6670, "Reisekosten Unternehmer", "aufwand", "v19"),
    (4805, 6470, "Reparaturen und Instandhaltung Betriebs- und Geschäftsausstattung", "aufwand", "v19"),
    (4855, 6260, "Sofortabschreibung geringwertiger Wirtschaftsgüter", "aufwand", ""),
    (4900, 6300, "Sonstige betriebliche Aufwendungen", "aufwand", "v19"),
    (4910, 6800, "Porto", "aufwand", ""),
    (4920, 6805, "Telefon", "aufwand", "v19"),
    (4925, 6810, "Telefax und Internetkosten", "aufwand", "v19"),
    (4930, 6815, "Bürobedarf", "aufwand", "v19"),
    (4940, 6820, "Zeitschriften, Bücher", "aufwand", "v7"),
    (4945, 6821, "Fortbildungskosten", "aufwand", "v19"),
    (4950, 6825, "Rechts- und Beratungskosten", "aufwand", "v19"),
    (4955, 6830, "Buchführungskosten", "aufwand", "v19"),
    (4970, 6855, "Nebenkosten des Geldverkehrs", "aufwand", ""),
    (4985, 6845, "Werkzeuge und Kleingeräte", "aufwand", "v19"),
    (2100, 7300, "Zinsen und ähnliche Aufwendungen", "aufwand", ""),
    (2650, 7100, "Sonstige Zinsen und ähnliche Erträge", "erloes", ""),
    (8300, 4300, "Erlöse 7 % USt", "erloes", "auto"),
    (8400, 4400, "Erlöse 19 % USt", "erloes", "auto"),
    (8336, 4336, "Erlöse sonstige Leistungen EU (Steuerschuld Leistungsempfänger)", "erloes", ""),
    (8337, 4337, "Erlöse § 13b UStG", "erloes", ""),
    (8338, 4338, "Erlöse nicht steuerbar (Drittland)", "erloes", ""),
]


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def schema(con):
    con.executescript(SCHEMA)


def vorbelegen(con, skr):
    """Standardkonten des Kontenrahmens anlegen, soweit sie fehlen (eigene Änderungen bleiben)."""
    i = 0 if skr == "03" else 1
    for z in STANDARD:
        con.execute("INSERT OR IGNORE INTO konten (skr, nummer, bezeichnung, art, steuer, angelegt) VALUES (?,?,?,?,?,?)",
                    (skr, z[i], z[2], z[3], z[4], jetzt()))


def liste(con, skr, alle=False):
    if not con.execute("SELECT 1 FROM konten WHERE skr=? LIMIT 1", (skr,)).fetchone():
        vorbelegen(con, skr)
    sql = "SELECT * FROM konten WHERE skr=?" + ("" if alle else " AND aktiv=1") + " ORDER BY nummer"
    return [dict(r, art_name=ARTEN.get(r["art"], r["art"]), steuer_name=STEUER.get(r["steuer"], r["steuer"])) for r in con.execute(sql, (skr,))]


def laden(con, skr, nummer):
    r = con.execute("SELECT * FROM konten WHERE skr=? AND nummer=?", (skr, int(nummer))).fetchone()
    return dict(r) if r else None


def _pruefen(d, laenge):
    nr = str(d.get("nummer") or "").strip()
    if not re.fullmatch(r"\d{1,8}", nr):
        raise Fehler("Bitte eine Kontonummer aus Ziffern eingeben.")
    if len(nr) > laenge:
        raise Fehler(f"Sachkonten haben höchstens {laenge} Stellen (Sachkontenlänge in den DATEV-Einstellungen).")
    bez = str(d.get("bezeichnung") or "").strip()
    if not bez:
        raise Fehler("Bitte eine Bezeichnung eingeben.")
    art = d.get("art") if d.get("art") in ARTEN else "aufwand"
    st = d.get("steuer") if d.get("steuer") in STEUER else ""
    return int(nr), bez[:80], art, st


def api(con, methode, teile, q, d, skr, laenge=4, darf_aendern=False):
    kid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
    if methode == "GET" and kid is None:
        return {"konten": liste(con, skr, q.get("alle") == "1"), "arten": ARTEN, "steuer": STEUER, "skr": skr}
    if not darf_aendern:
        raise Fehler("Den Kontenplan ändert der Inhaber (Einstellungen).", 403)
    if methode == "POST" and kid is None:
        liste(con, skr)
        nr, bez, art, st = _pruefen(d, laenge)
        alt = laden(con, skr, nr)
        if alt and alt["aktiv"]:
            raise Fehler(f"Das Konto {nr} gibt es schon ({alt['bezeichnung']}).")
        if alt:
            con.execute("UPDATE konten SET bezeichnung=?, art=?, steuer=?, aktiv=1 WHERE id=?", (bez, art, st, alt["id"]))
            return laden(con, skr, nr)
        con.execute("INSERT INTO konten (skr, nummer, bezeichnung, art, steuer, eigen, angelegt) VALUES (?,?,?,?,?,1,?)", (skr, nr, bez, art, st, jetzt()))
        return laden(con, skr, nr)
    if kid and methode == "PUT":
        k = con.execute("SELECT * FROM konten WHERE id=?", (kid,)).fetchone()
        if not k:
            raise Fehler("Konto nicht gefunden.", 404)
        w = {}
        if "bezeichnung" in d:
            if not str(d["bezeichnung"] or "").strip():
                raise Fehler("Bitte eine Bezeichnung eingeben.")
            w["bezeichnung"] = str(d["bezeichnung"]).strip()[:80]
        if d.get("art") in ARTEN:
            w["art"] = d["art"]
        if "steuer" in d and d["steuer"] in STEUER:
            w["steuer"] = d["steuer"]
        if "aktiv" in d:
            w["aktiv"] = 1 if d["aktiv"] else 0
        if w:
            con.execute(f"UPDATE konten SET {','.join(k_ + '=?' for k_ in w)} WHERE id=?", list(w.values()) + [kid])
        return dict(con.execute("SELECT * FROM konten WHERE id=?", (kid,)).fetchone())
    if kid and methode == "DELETE":
        k = con.execute("SELECT * FROM konten WHERE id=?", (kid,)).fetchone()
        if not k:
            raise Fehler("Konto nicht gefunden.", 404)
        benutzt = con.execute("SELECT 1 FROM bank_umsaetze WHERE konto=? LIMIT 1", (k["nummer"],)).fetchone() or \
            con.execute("SELECT 1 FROM bank_regeln WHERE konto=? LIMIT 1", (k["nummer"],)).fetchone()
        if benutzt or not k["eigen"]:
            con.execute("UPDATE konten SET aktiv=0 WHERE id=?", (kid,))
            return {"ok": True, "ausgeblendet": True}
        con.execute("DELETE FROM konten WHERE id=?", (kid,))
        return {"ok": True}
    raise Fehler("Unbekannte Anfrage", 404)
