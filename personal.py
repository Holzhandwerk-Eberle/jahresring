"""Mitarbeiter, Zeiterfassung (Stempeluhr), Abwesenheiten, Stunden-/Urlaubskonten, Monatsbeleg und Lohnzahlungen."""
import kern
import calendar
import html
import json
import re
from datetime import date, datetime, timedelta

import benutzer

SCHEMA = """
CREATE TABLE IF NOT EXISTS mitarbeiter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer INTEGER UNIQUE,
    kuerzel TEXT DEFAULT '',
    vorname TEXT DEFAULT '', nachname TEXT DEFAULT '',
    strasse TEXT DEFAULT '', plz TEXT DEFAULT '', ort TEXT DEFAULT '',
    telefon TEXT DEFAULT '', email TEXT DEFAULT '',
    eintritt TEXT DEFAULT '', austritt TEXT DEFAULT '',
    aktiv INTEGER DEFAULT 1,
    lohnart TEXT DEFAULT 'stunde',
    lohngruppe TEXT DEFAULT '',
    stundenlohn REAL DEFAULT 0, gehalt REAL DEFAULT 0, kostensatz REAL DEFAULT 0,
    iban TEXT DEFAULT '', bic TEXT DEFAULT '',
    lieferant_id INTEGER, kasse_id INTEGER,
    modelle TEXT DEFAULT '[]',
    konten_ab TEXT DEFAULT '',
    ueberstunden_start REAL DEFAULT 0, urlaub_start REAL DEFAULT 0,
    bemerkungen TEXT DEFAULT '',
    angelegt TEXT, geaendert TEXT
);
CREATE TABLE IF NOT EXISTS zeiten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mitarbeiter_id INTEGER NOT NULL,
    datum TEXT NOT NULL, beginn TEXT NOT NULL, ende TEXT,
    auftrag_id INTEGER, kst TEXT DEFAULT '', taetigkeit TEXT DEFAULT '', notiz TEXT DEFAULT '',
    quelle TEXT DEFAULT 'pc',
    angelegt TEXT, geaendert TEXT, geaendert_von TEXT DEFAULT ''
);
DROP INDEX IF EXISTS zeiten_ma;
-- Zeitkonten: Die Prüfsumme je Mitarbeiter und Jahr liest nur diesen Index (alle nötigen Spalten stehen darin), nicht die Tabelle
CREATE INDEX IF NOT EXISTS zeiten_ma_zeit ON zeiten(mitarbeiter_id, datum, beginn, ende);
-- laufende (noch nicht beendete) Abschnitte: für Stempeluhr und Personalübersicht ohne Durchsuchen aller Zeiten
CREATE INDEX IF NOT EXISTS zeiten_offen ON zeiten(mitarbeiter_id) WHERE ende IS NULL;
CREATE TABLE IF NOT EXISTS stempel_ereignisse (
    client_id TEXT PRIMARY KEY, mitarbeiter_id INTEGER, zeit TEXT, aktion TEXT, daten TEXT, ergebnis TEXT, angelegt TEXT
);
CREATE TABLE IF NOT EXISTS abwesenheiten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mitarbeiter_id INTEGER NOT NULL,
    art TEXT NOT NULL, von TEXT NOT NULL, bis TEXT NOT NULL, halbtag INTEGER DEFAULT 0,
    status TEXT DEFAULT 'genehmigt', notiz TEXT DEFAULT '', angelegt TEXT
);
CREATE TABLE IF NOT EXISTS kontobuchungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mitarbeiter_id INTEGER NOT NULL, datum TEXT NOT NULL, konto TEXT NOT NULL, wert REAL DEFAULT 0, text TEXT DEFAULT '', angelegt TEXT
);
CREATE TABLE IF NOT EXISTS lohn (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mitarbeiter_id INTEGER NOT NULL, monat TEXT NOT NULL,
    brutto REAL DEFAULT 0, netto REAL DEFAULT 0, steuer REAL DEFAULT 0, sv REAL DEFAULT 0,
    auszahlung TEXT DEFAULT '', notiz TEXT DEFAULT '', zahlungen TEXT DEFAULT '{}',
    angelegt TEXT, geaendert TEXT, UNIQUE(mitarbeiter_id, monat)
);
"""

ABWESENHEIT = {
    "urlaub": ("Urlaub", True), "krank": ("Krank", True), "kind_krank": ("Kind krank", True), "schule": ("Berufsschule", True),
    "sonder": ("Sonderurlaub", True), "ueberstunden": ("Überstunden frei", False), "unbezahlt": ("Unbezahlt frei", False),
}
RUHEZEIT_STUNDEN = 11   # § 5 ArbZG: ununterbrochene Ruhezeit nach dem Ende der täglichen Arbeitszeit

# Gesetzlicher Mindestlohn je Stunde ab dem genannten Tag (Mindestlohngesetz, Anpassungsverordnungen). Die Minijob-Grenze folgt
# daraus: 130 Stunden im Vierteljahr zum Mindestlohn, auf volle Euro aufgerundet (§ 8 Abs. 1a SGB IV).
MINDESTLOHN = [("2024-01-01", 12.41), ("2025-01-01", 12.82), ("2026-01-01", 13.90), ("2027-01-01", 14.60)]


def mindestlohn(tag_iso):
    """Mindestlohn am genannten Tag (für spätere Jahre gilt der letzte bekannte Satz weiter)."""
    return next((w for ab, w in reversed(MINDESTLOHN) if ab <= str(tag_iso)[:10]), MINDESTLOHN[0][1])


def minijob_grenze(tag_iso):
    import math
    return math.ceil(round(mindestlohn(tag_iso) * 130 / 3, 4))


def lohn_hinweise(m, monat, ist_stunden, soll_stunden):
    """Hinweise zu Mindestlohn und Minijob-Grenze für einen Monat – nur Hinweise, gerechnet aus den Angaben im Mitarbeiterstamm."""
    aus = []
    stichtag = f"{monat}-01"
    ml = mindestlohn(stichtag)
    art = m["lohnart"]
    geld = lambda v: f"{v:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".") + " €"   # noqa: E731
    if art in ("stunde", "minijob") and 0 < (m["stundenlohn"] or 0) < ml - 0.004:
        aus.append(f"Stundenlohn {geld(m['stundenlohn'])} liegt unter dem gesetzlichen Mindestlohn von {geld(ml)}")
    if art == "gehalt" and (m["gehalt"] or 0) > 0 and soll_stunden > 0 and m["gehalt"] / soll_stunden < ml - 0.004:
        aus.append(f"Gehalt {geld(m['gehalt'])} bei {str(round(soll_stunden, 1)).replace('.', ',')} Sollstunden ergibt {geld(m['gehalt'] / soll_stunden)} je Stunde – "
                   f"unter dem gesetzlichen Mindestlohn von {geld(ml)}")
    if art == "minijob" and (m["stundenlohn"] or 0) > 0:
        grenze, verdienst = minijob_grenze(stichtag), (m["stundenlohn"] or 0) * ist_stunden
        if verdienst > grenze + 0.004:
            aus.append(f"Richtwert {geld(verdienst)} liegt über der Minijob-Grenze von {geld(grenze)} im Monat "
                       f"(bei {geld(m['stundenlohn'])} sind das höchstens {str(round(grenze / m['stundenlohn'], 1)).replace('.', ',')} Stunden)")
    return aus


LOHNARTEN = {"stunde": "Stundenlohn", "gehalt": "Monatsgehalt", "minijob": "Minijob", "azubi": "Auszubildende/r", "inhaber": "Inhaber (ohne Lohn)"}
KST_NAMEN = {"AVORBER": "Arbeitsvorbereitung", "ZUSCHNIT": "Zuschnitt", "KANTENMA": "Kantenmaschine", "SONST-MA": "Sonstige Maschinen",
             "BANKRAUM": "Bankraum", "OBERFLÄ": "Oberfläche", "MONTAGE": "Montage", "REPARAT": "Reparatur", "FAHRZEIT": "Fahrzeit",
             "HELFER": "Helfer"}
STANDARD_MODELL = {"ab": "", "tage": [8, 8, 8, 8, 8, 0, 0], "urlaub": 30}
WOCHENTAG = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
FELDER = ["nummer", "kuerzel", "vorname", "nachname", "strasse", "plz", "ort", "telefon", "email", "eintritt", "austritt", "aktiv",
          "lohnart", "lohngruppe", "stundenlohn", "gehalt", "kostensatz", "iban", "bic", "kasse_id", "konten_ab", "ueberstunden_start",
          "urlaub_start", "bemerkungen", "geburtsdatum"]

# von app.py gesetzt
HILFE = {"einstellungen": lambda con: {}, "lohnbasis": lambda con, aid: "", "zahlungsnummer": None, "kostenstellen": lambda con: []}


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def schema(con):
    con.executescript(SCHEMA)


def zahl(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s or 0)
    except ValueError:
        return 0.0


def h(x):
    return html.escape(str(x if x is not None else ""))


def de(z, n=2):
    s = f"{z:,.{n}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def de_datum(iso):
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso and len(iso) >= 10 else ""


# ---------------------------------------------------------------- Feiertage Baden-Württemberg
def ostern(j):
    a, b, c = j % 19, j // 100, j % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    hh = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - hh - k) % 7
    m = (a + 11 * hh + 22 * l) // 451
    monat = (hh + l - 7 * m + 114) // 31
    tag = (hh + l - 7 * m + 114) % 31 + 1
    return date(j, monat, tag)


# Feiertage und arbeitsfreie Tage (Einstellungen › Arbeitszeit). Schlüssel, Name, Datum im Jahr j, Vorgabe, Hinweis.
def _busstag(j):
    d = date(j, 11, 22)
    while d.weekday() != 2:   # Mittwoch zwischen 16. und 22. November
        d -= timedelta(1)
    return d


FEIERTAGE_KATALOG = [
    ("neujahr", "Neujahr", lambda j, o: date(j, 1, 1), True, ""),
    ("hl3k", "Heilige Drei Könige", lambda j, o: date(j, 1, 6), True, "nur Baden-Württemberg, Bayern und Sachsen-Anhalt"),
    ("frauentag", "Internationaler Frauentag", lambda j, o: date(j, 3, 8), False, "nur Berlin und Mecklenburg-Vorpommern"),
    ("karfreitag", "Karfreitag", lambda j, o: o - timedelta(2), True, ""),
    ("ostersonntag", "Ostersonntag", lambda j, o: o, False, "gesetzlich nur Brandenburg; zählt für den Feiertagszuschlag am Sonntag"),
    ("ostermontag", "Ostermontag", lambda j, o: o + timedelta(1), True, ""),
    ("maifeiertag", "Tag der Arbeit", lambda j, o: date(j, 5, 1), True, ""),
    ("himmelfahrt", "Christi Himmelfahrt", lambda j, o: o + timedelta(39), True, ""),
    ("pfingstsonntag", "Pfingstsonntag", lambda j, o: o + timedelta(49), False, "gesetzlich nur Brandenburg; zählt für den Feiertagszuschlag am Sonntag"),
    ("pfingstmontag", "Pfingstmontag", lambda j, o: o + timedelta(50), True, ""),
    ("fronleichnam", "Fronleichnam", lambda j, o: o + timedelta(60), True, "nur BW, BY, HE, NW, RP, SL, teilweise SN und TH"),
    ("friedensfest", "Augsburger Friedensfest", lambda j, o: date(j, 8, 8), False, "nur Stadt Augsburg"),
    ("mariae", "Mariä Himmelfahrt", lambda j, o: date(j, 8, 15), False, "nur Saarland und Teile Bayerns"),
    ("weltkindertag", "Weltkindertag", lambda j, o: date(j, 9, 20), False, "nur Thüringen"),
    ("einheit", "Tag der Deutschen Einheit", lambda j, o: date(j, 10, 3), True, ""),
    ("reformation", "Reformationstag", lambda j, o: date(j, 10, 31), False, "nur BB, HB, HH, MV, NI, SN, ST, SH, TH"),
    ("allerheiligen", "Allerheiligen", lambda j, o: date(j, 11, 1), True, "nur BW, BY, NW, RP und SL"),
    ("busstag", "Buß- und Bettag", lambda j, o: _busstag(j), False, "nur Sachsen"),
    ("heiligabend", "Heiligabend (bezahlt)", lambda j, o: date(j, 12, 24), False, "24.12. arbeitsfrei, die ausfallenden Stunden werden bezahlt"),
    ("weihnacht1", "1. Weihnachtstag", lambda j, o: date(j, 12, 25), True, ""),
    ("weihnacht2", "2. Weihnachtstag", lambda j, o: date(j, 12, 26), True, ""),
    ("silvester", "Silvester (bezahlt)", lambda j, o: date(j, 12, 31), False, "31.12. arbeitsfrei, die ausfallenden Stunden werden bezahlt"),
]
FREI_KATALOG = [
    ("weiberfastnacht", "Schmotziger Donnerstag", lambda j, o: o - timedelta(52), False, ""),
    ("fasnetfreitag", "Fasnetsfreitag", lambda j, o: o - timedelta(51), False, ""),
    ("rosenmontag", "Rosenmontag", lambda j, o: o - timedelta(48), False, ""),
    ("fasnetdienstag", "Fasnetsdienstag", lambda j, o: o - timedelta(47), False, ""),
    ("aschermittwoch", "Aschermittwoch", lambda j, o: o - timedelta(46), False, ""),
    ("heiligabend", "Heiligabend (unbezahlt)", lambda j, o: date(j, 12, 24), False, ""),
    ("silvester", "Silvester (unbezahlt)", lambda j, o: date(j, 12, 31), False, ""),
]
# Einstellungen, vom Programm beim Start und nach jedem Speichern gesetzt (tage_einstellen)
TAGE_CFG = {"feiertage": {}, "frei": {}, "eigene": [], "plaene": []}
_feiertage_cache = {}


def tage_einstellen(e):
    """Feiertage, arbeitsfreie Tage und Sollstundenpläne aus den Einstellungen übernehmen."""
    TAGE_CFG.update(feiertage=dict(e.get("feiertage_wahl") or {}), frei=dict(e.get("frei_wahl") or {}),
                    eigene=list(e.get("tage_eigene") or []), plaene=list(e.get("sollplaene") or []))
    _feiertage_cache.clear()
    _VORLAUF.clear()


def _tage_jahr(j):
    if j not in _feiertage_cache:
        o = ostern(j)
        ft, fr = {}, {}
        for k, n, fn, std, _ in FEIERTAGE_KATALOG:
            if TAGE_CFG["feiertage"].get(k, std):
                ft[fn(j, o).isoformat()] = n
        for k, n, fn, std, _ in FREI_KATALOG:
            iso = fn(j, o).isoformat()
            if TAGE_CFG["frei"].get(k, std) and iso not in ft:
                fr[iso] = n
        for x in TAGE_CFG["eigene"]:
            try:
                tt, mm = [int(v) for v in str(x.get("datum") or "").replace("-", ".").split(".")[:2]]
                iso = date(j, mm, tt).isoformat()
            except (ValueError, TypeError):
                continue
            if not (x.get("name") or "").strip():
                continue
            if x.get("art") == "frei":
                if iso not in ft:
                    fr[iso] = x["name"].strip()
            else:
                ft[iso] = x["name"].strip()
                fr.pop(iso, None)
        _feiertage_cache[j] = (ft, fr)
    return _feiertage_cache[j]


def feiertage(j):
    """Bezahlte Feiertage des Jahres {Datum: Name} (laut Einstellungen)."""
    return _tage_jahr(j)[0]


def freie_tage(j):
    """Arbeitsfreie, nicht bezahlte Tage des Jahres {Datum: Name} (Fasnet, Heiligabend unbezahlt …)."""
    return _tage_jahr(j)[1]


def feiertag(iso):
    return feiertage(int(iso[:4])).get(iso, "")


def arbeitsfrei(iso):
    return freie_tage(int(iso[:4])).get(iso, "")


def frei_oder_feiertag(iso):
    return feiertag(iso) or arbeitsfrei(iso)


# ---------------------------------------------------------------- Sollstundenpläne und Zuschläge
ZUSCHLAG_ARTEN = [("ueber", "Überstunden Arbeitstag", 25), ("sonntag", "Arbeit am Sonntag", 50), ("heiligabend", "Arbeit am 24.12.", 50),
                  ("ft_arbeitstag", "Feiertag ist Arbeitstag", 125), ("ft_frei", "Feiertag ist arbeitsfreier Tag", 50),
                  ("ft_sonntag", "Feiertag ist Sonntag", 50)]


def _z(v, d=0.0):
    try:
        return float(str(v).replace(",", ".")) if v not in (None, "") else d
    except ValueError:
        return d


def plaene_pruefen(liste):
    """Sollstundenpläne aus den Einstellungen bereinigen; neue bekommen eine Kennung p1, p2 …"""
    aus, nr = [], max([int("".join(c for c in str(x.get("id") or "") if c.isdigit()) or 0) for x in liste if isinstance(x, dict)] + [0])
    for x in liste:
        if not isinstance(x, dict):
            continue
        pid = str(x.get("id") or "")
        if not pid:
            nr += 1
            pid = f"p{nr}"
        tage = [round(max(0.0, min(24.0, _z(t))), 2) for t in (x.get("tage") or [])][:7]
        tage += [0.0] * (7 - len(tage))
        zs = x.get("zuschlaege") or {}
        aus.append({"id": pid, "name": (x.get("name") or "").strip() or "Sollstundenplan", "regelung": "fix" if x.get("regelung") == "fix" else "flexibel",
                    "tage": tage, "max_woche": round(max(0.0, _z(x.get("max_woche"))), 2), "max_tag": round(max(0.0, _z(x.get("max_tag"))), 2),
                    "zuschlaege": {k: round(max(0.0, _z(zs.get(k), std)), 1) for k, _, std in ZUSCHLAG_ARTEN}})
    return aus


def plan_von(pid):
    return next((p for p in TAGE_CFG["plaene"] if pid and p.get("id") == pid), None)


def plaene_uebertragen(con, plaene):
    """Geänderte Sollstundenpläne in die Arbeitszeitmodelle der Mitarbeiter übernehmen, die den Plan nutzen."""
    ids = {p["id"]: p for p in plaene}
    for m in con.execute("SELECT id, modelle FROM mitarbeiter").fetchall():
        mods, neu = modelle(m), False
        for x in mods:
            if x.get("plan"):
                p = ids.get(x["plan"])
                if not p:
                    x["plan"] = ""
                    neu = True
                elif x.get("tage") != p["tage"]:
                    x["tage"] = list(p["tage"])
                    neu = True
        if neu:
            con.execute("UPDATE mitarbeiter SET modelle=?, geaendert=? WHERE id=?", (json.dumps(mods), jetzt(), m["id"]))


def zuschlaege(con, m, von, bis):
    """Zuschlagspflichtige Stunden je Tag {Datum: {Art: Stunden}} nach dem Sollstundenplan des Mitarbeiters.
    Jede Stunde fällt in höchstens eine Art: Feiertag vor Sonntag vor 24.12.; Überstunden zählen nur an den übrigen Tagen.
    fix: Stunden über dem Wochensoll; flexibel: über der Höchstarbeitszeit der Woche (um Feiertage/Abwesenheiten gekürzt)
    und, falls eingestellt, über der Höchstarbeitszeit des Tages. Wochen werden immer ganz gerechnet (Mo–So)."""
    if m["lohnart"] == "inhaber":
        return {}
    d0 = date.fromisoformat(von)
    d1 = date.fromisoformat(bis)
    w0, w1 = d0 - timedelta(d0.weekday()), d1 + timedelta(6 - d1.weekday())
    alle = tage(con, m, w0.isoformat(), w1.isoformat())
    mods = modelle(m)
    aus = {}
    for i in range(0, len(alle), 7):
        woche = alle[i:i + 7]
        plan = plan_von(modell_am(mods, woche[0]["datum"]).get("plan"))
        if not plan:
            continue
        soll_woche = sum(t["soll"] for t in woche)
        if plan["regelung"] == "fix":
            grenze = soll_woche
        else:
            grenze = soll_woche + (plan["max_woche"] - sum(plan["tage"])) if plan["max_woche"] else None
        summe = bisher = 0.0
        for t in woche:
            wd = date.fromisoformat(t["datum"]).weekday()
            z = {}
            art = None
            if t.get("bezahlt_ft"):
                art = "ft_sonntag" if wd == 6 else ("ft_arbeitstag" if plan["tage"][wd] > 0 else "ft_frei")
            elif wd == 6:
                art = "sonntag"
            elif t["datum"][5:] == "12-24":
                art = "heiligabend"
            if art:
                if t["arbeit"]:
                    z[art] = t["arbeit"]
            else:
                tag_ueber = max(0.0, t["arbeit"] - plan["max_tag"]) if plan["regelung"] == "flexibel" and plan["max_tag"] else 0.0
                summe += t["arbeit"] - tag_ueber + t["abw_std"]
                woche_ueber = max(0.0, summe - grenze - bisher) if grenze is not None else 0.0
                bisher += woche_ueber
                if tag_ueber + woche_ueber > 0.004:
                    z["ueber"] = tag_ueber + woche_ueber
            if z and von <= t["datum"] <= bis:
                aus[t["datum"]] = {k: round(v, 2) for k, v in z.items()}
    return aus


# ---------------------------------------------------------------- Zeitrechnung
def minuten(hhmm):
    if not hhmm:
        return None
    try:
        s, m = hhmm.split(":")
        return int(s) * 60 + int(m)
    except ValueError:
        return None


def hhmm(minu):
    minu = max(0, min(24 * 60, int(round(minu))))
    return f"{minu // 60:02d}:{minu % 60:02d}"


def dauer(z):
    b, e = minuten(z["beginn"]), minuten(z["ende"])
    if b is None or e is None:
        return 0.0
    if e < b:
        e += 24 * 60
    return round((e - b) / 60, 4)


def uhrzeit_lesen(s):
    s = (s or "").strip().replace(".", ":").replace(",", ":")
    if not s:
        return ""
    if ":" not in s:
        s = s.zfill(4)
        s = s[:-2] + ":" + s[-2:] if len(s) > 2 else s + ":00"
    st, mi = s.split(":", 1)
    try:
        st, mi = int(st), int(mi or 0)
    except ValueError:
        raise Fehler(f"Uhrzeit „{s}“ nicht lesbar (z. B. 7:30).")
    if not (0 <= st <= 24 and 0 <= mi < 60) or (st == 24 and mi):
        raise Fehler(f"Uhrzeit „{s}“ nicht gültig.")
    return f"{st:02d}:{mi:02d}"


# ---------------------------------------------------------------- Mitarbeiter
def modelle(m):
    try:
        l = json.loads(m["modelle"] or "[]")
    except (ValueError, TypeError):
        l = []
    l = [x for x in l if isinstance(x, dict)]
    if not l:
        l = [dict(STANDARD_MODELL)]
    return sorted(l, key=lambda x: x.get("ab") or "")


def modell_am(mods, iso):
    akt = mods[0]
    for x in mods:
        if (x.get("ab") or "") <= iso:
            akt = x
    return akt


def name(m):
    return f"{m['vorname']} {m['nachname']}".strip() or m["kuerzel"] or f"Mitarbeiter {m['nummer']}"


def laden(con, mid):
    m = con.execute("SELECT * FROM mitarbeiter WHERE id=?", (mid,)).fetchone()
    if not m:
        raise Fehler("Mitarbeiter nicht gefunden.", 404)
    d = dict(m)
    d["modelle"] = modelle(m)
    d["name"] = name(m)
    d["benutzer"] = [dict(r) for r in con.execute("SELECT id, login, rolle, aktiv FROM benutzer WHERE mitarbeiter_id=?", (mid,))]
    return d


def konten_beginn(m):
    """Ab wann laufen Überstunden- und Urlaubskonto."""
    kandidaten = [x for x in (m["konten_ab"], m["eintritt"]) if x]
    if kandidaten:
        return max(kandidaten) if m["konten_ab"] else kandidaten[0]
    return date(date.today().year, 1, 1).isoformat()


def lieferant_pflegen(con, mid):
    """Für Lohnüberweisungen wird der Mitarbeiter als Zahlungsempfänger (Lieferantengruppe „Mitarbeiter“) geführt."""
    m = con.execute("SELECT * FROM mitarbeiter WHERE id=?", (mid,)).fetchone()
    if not m or not (m["iban"] or m["lieferant_id"]):
        return None
    werte = {"kurzname": f"Lohn {m['nachname']}, {m['vorname']}".strip(", "), "gruppe": "Mitarbeiter", "empfaenger": name(m),
             "iban": (m["iban"] or "").replace(" ", "").upper(), "bic": m["bic"] or "", "anschrift": f"{m['strasse']}",
             "plz": m["plz"] or "", "ort": m["ort"] or "", "vorsteuer": 0, "zahlungsziel": 0, "aktiv": 1 if m["aktiv"] else 0}
    if m["lieferant_id"] and con.execute("SELECT 1 FROM lieferanten WHERE id=?", (m["lieferant_id"],)).fetchone():
        con.execute(f"UPDATE lieferanten SET {','.join(k + '=?' for k in werte)}, geaendert=? WHERE id=?",
                    list(werte.values()) + [jetzt(), m["lieferant_id"]])
        return m["lieferant_id"]
    e = HILFE["einstellungen"](con)
    maxnr = con.execute("SELECT MAX(nummer) FROM lieferanten").fetchone()[0]
    werte["nummer"] = max(int(e.get("lieferantennr_start") or 700000), (maxnr or 0) + 1)
    werte["angelegt"] = werte["geaendert"] = jetzt()
    cur = con.execute(f"INSERT INTO lieferanten ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})", list(werte.values()))
    con.execute("UPDATE mitarbeiter SET lieferant_id=? WHERE id=?", (cur.lastrowid, mid))
    return cur.lastrowid


def mitarbeiter_speichern(con, mid, d):
    werte = {}
    for k in FELDER:
        if k not in d:
            continue
        v = d[k]
        if k in ("stundenlohn", "gehalt", "kostensatz", "ueberstunden_start", "urlaub_start"):
            v = round(zahl(v), 2)
        elif k in ("aktiv",):
            v = 1 if v else 0
        elif k in ("nummer", "kasse_id"):
            v = int(v) if str(v or "").strip() else None
        elif k == "lohnart" and v not in LOHNARTEN:
            v = "stunde"
        else:
            v = (v or "").strip() if isinstance(v, str) else v
        werte[k] = v
    if "iban" in werte:
        werte["iban"] = (werte["iban"] or "").replace(" ", "").upper()
    if "modelle" in d:
        mods = []
        for x in d["modelle"] or []:
            tage = [round(max(0.0, min(24.0, zahl(t))), 2) for t in (x.get("tage") or [])][:7]
            tage += [0.0] * (7 - len(tage))
            plan = plan_von(x.get("plan"))
            if plan:
                tage = list(plan["tage"])
            mods.append({"ab": x.get("ab") or "", "tage": tage, "urlaub": round(zahl(x.get("urlaub")), 1), "plan": plan["id"] if plan else ""})
        werte["modelle"] = json.dumps(sorted(mods, key=lambda x: x["ab"]) or [STANDARD_MODELL])
    if "nummer" in werte and werte["nummer"]:
        r = con.execute("SELECT id FROM mitarbeiter WHERE nummer=?", (werte["nummer"],)).fetchone()
        if r and r["id"] != mid:
            raise Fehler(f"Die Personalnummer {werte['nummer']} ist schon vergeben.")
    werte["geaendert"] = jetzt()
    if mid is None:
        if not werte.get("nummer"):
            werte["nummer"] = (con.execute("SELECT MAX(nummer) FROM mitarbeiter").fetchone()[0] or 4999) + 1
        werte.setdefault("modelle", json.dumps([STANDARD_MODELL]))
        jahresbeginn = date(date.today().year, 1, 1).isoformat()
        werte.setdefault("konten_ab", max(werte.get("eintritt") or jahresbeginn, jahresbeginn))
        werte["angelegt"] = jetzt()
        cur = con.execute(f"INSERT INTO mitarbeiter ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})", list(werte.values()))
        mid = cur.lastrowid
    else:
        con.execute(f"UPDATE mitarbeiter SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [mid])
    if any(k in werte for k in ("iban", "bic", "vorname", "nachname", "strasse", "plz", "ort", "aktiv")):
        lieferant_pflegen(con, mid)
    return laden(con, mid)


def mitarbeiter_liste(con, q):
    sql = "SELECT * FROM mitarbeiter"
    if q.get("status", "aktiv") == "aktiv":
        sql += " WHERE aktiv=1"
    aus = []
    heute = date.today()
    for m in con.execute(sql + " ORDER BY aktiv DESC, nummer"):
        d = dict(m)
        d["name"] = name(m)
        d["lohnart_name"] = LOHNARTEN.get(m["lohnart"], m["lohnart"])
        mod = modell_am(modelle(m), heute.isoformat())
        d["wochenstunden"] = round(sum(mod["tage"]), 2)
        d["urlaub_jahr"] = mod["urlaub"]
        try:
            k = konten(con, m, heute)
            d["ueberstunden"], d["resturlaub"] = k["ueberstunden"], k["urlaub_rest"]
            if m["lohnart"] == "inhaber":
                d["ueberstunden"] = None
        except Exception:  # noqa: BLE001
            d["ueberstunden"] = d["resturlaub"] = None
        lauf = con.execute("SELECT z.*, a.nummer AS auftragsnr FROM zeiten z INDEXED BY zeiten_offen LEFT JOIN auftraege a ON a.id=z.auftrag_id "
                           "WHERE z.mitarbeiter_id=? AND z.ende IS NULL ORDER BY z.datum DESC, z.beginn DESC LIMIT 1", (m["id"],)).fetchone()
        d["laeuft"] = dict(lauf) if lauf else None
        d["benutzer"] = [r["login"] for r in con.execute("SELECT login FROM benutzer WHERE mitarbeiter_id=?", (m["id"],))]
        aus.append(d)
    return aus


# ---------------------------------------------------------------- Zeiten ↔ Auftragsstunden
def stunden_abgleichen(con, zid):
    """Hält die Auftragsstunden (Nachkalkulation) passend zu einem Zeitabschnitt."""
    z = con.execute("SELECT * FROM zeiten WHERE id=?", (zid,)).fetchone()
    alt = con.execute("SELECT id FROM stunden WHERE zeit_id=?", (zid,)).fetchone()
    if not z or not z["auftrag_id"] or not z["ende"] or dauer(z) <= 0:
        if alt:
            con.execute("DELETE FROM stunden WHERE id=?", (alt["id"],))
        return
    m = con.execute("SELECT * FROM mitarbeiter WHERE id=?", (z["mitarbeiter_id"],)).fetchone()
    gruppe = (m["lohngruppe"] if m and m["lohngruppe"] else "") or HILFE["lohnbasis"](con, z["auftrag_id"])
    text = " · ".join(x for x in [m["kuerzel"] or name(m) if m else "", z["taetigkeit"]] if x)
    werte = (z["auftrag_id"], z["datum"], round(dauer(z), 2), z["kst"] or "", gruppe, text, z["mitarbeiter_id"], z["titel"] or 0)
    if alt:
        con.execute("UPDATE stunden SET auftrag_id=?, datum=?, stunden=?, kst=?, gruppe=?, taetigkeit=?, mitarbeiter_id=?, titel=? WHERE id=?",
                    werte + (alt["id"],))
    else:
        con.execute("INSERT INTO stunden (auftrag_id, datum, stunden, kst, gruppe, taetigkeit, mitarbeiter_id, titel, zeit_id, angelegt) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)", werte + (zid, jetzt()))


def zeit_pruefen(con, mid, datum, beginn, ende, ohne_id=None):
    if not datum or len(datum) != 10:
        raise Fehler("Bitte ein Datum angeben.")
    b = minuten(beginn)
    e = minuten(ende) if ende else None
    if e is not None and e <= b:
        raise Fehler("Das Ende muss nach dem Beginn liegen (über Mitternacht bitte als zwei Einträge).")
    for z in con.execute("SELECT * FROM zeiten WHERE mitarbeiter_id=? AND datum=? AND id<>?", (mid, datum, ohne_id or 0)):
        zb = minuten(z["beginn"])
        ze = minuten(z["ende"]) if z["ende"] else 24 * 60
        eigen_e = e if e is not None else 24 * 60
        if b < ze and zb < eigen_e:
            raise Fehler(f"Überschneidet sich mit {z['beginn']}–{z['ende'] or 'läuft'} am {de_datum(datum)}.")


def zeit_speichern(con, d, zid=None, von=""):
    alt = con.execute("SELECT * FROM zeiten WHERE id=?", (zid,)).fetchone() if zid else None
    if zid and not alt:
        raise Fehler("Eintrag nicht gefunden.", 404)
    mid = int(d.get("mitarbeiter_id") or (alt["mitarbeiter_id"] if alt else 0))
    if not mid:
        raise Fehler("Bitte einen Mitarbeiter wählen.")
    datum = d.get("datum", alt["datum"] if alt else "")
    beginn = uhrzeit_lesen(d["beginn"]) if "beginn" in d else (alt["beginn"] if alt else "")
    ende = (uhrzeit_lesen(d["ende"]) or None) if "ende" in d else (alt["ende"] if alt else None)
    if not beginn:
        raise Fehler("Bitte den Beginn angeben.")
    zeit_pruefen(con, mid, datum, beginn, ende, zid)
    for mo in {str(datum or "")[:7], (alt["datum"] if alt else "")[:7]} - {""}:
        if monat_abgerechnet(con, mid, mo) and d.get("quelle") != "nachtrag":
            # Büro: möglich, aber nur nach Rückfrage – der Lohn dieses Monats ist schon zur Zahlung angelegt
            kern.rueckfrage(f"lohnmonat-{mid}-{mo}", f"Für {mo[5:7]}/{mo[:4]} sind die Lohnzahlungen dieses Mitarbeiters schon angelegt.\n\n"
                            "Eine Änderung der Zeiten ändert die Stunden, nach denen abgerechnet wurde. Bitte danach den Lohn prüfen.", "Trotzdem ändern")
    auftrag = d.get("auftrag_id", alt["auftrag_id"] if alt else None)
    auftrag = int(auftrag) if auftrag else None
    titel = d.get("titel", (alt["titel"] if alt else 0) if not ("auftrag_id" in d and alt and auftrag != alt["auftrag_id"]) else 0)
    titel = int(titel or 0) if auftrag else 0
    if titel and (not alt or titel != (alt["titel"] or 0)) and HILFE.get("titel_buchbar"):
        titel = HILFE["titel_buchbar"](con, auftrag, titel)
    werte = {"mitarbeiter_id": mid, "datum": datum, "beginn": beginn, "ende": ende, "auftrag_id": auftrag, "titel": titel,
             "kst": d.get("kst", alt["kst"] if alt else "") or "", "taetigkeit": d.get("taetigkeit", alt["taetigkeit"] if alt else "") or "",
             "notiz": d.get("notiz", alt["notiz"] if alt else "") or "", "geaendert": jetzt(), "geaendert_von": von}
    if alt:
        con.execute(f"UPDATE zeiten SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [zid])
    else:
        werte["quelle"] = d.get("quelle") or "pc"
        werte["angelegt"] = jetzt()
        zid = con.execute(f"INSERT INTO zeiten ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})", list(werte.values())).lastrowid
    stunden_abgleichen(con, zid)
    return zid


def zeit_loeschen(con, zid):
    con.execute("DELETE FROM stunden WHERE zeit_id=?", (zid,))
    con.execute("DELETE FROM zeiten WHERE id=?", (zid,))


def zeiten_liste(con, mid, von, bis):
    return [dict(r, stunden=round(dauer(r), 2)) for r in con.execute(
        "SELECT z.*, a.nummer AS auftragsnr, a.bezeichnung AS auftrag, k.kurzname AS kunde FROM zeiten z "
        "LEFT JOIN auftraege a ON a.id=z.auftrag_id LEFT JOIN kunden k ON k.id=a.kunde_id "
        "WHERE z.mitarbeiter_id=? AND z.datum BETWEEN ? AND ? ORDER BY z.datum, z.beginn", (mid, von, bis))]


# ---------------------------------------------------------------- Tagesrechnung, Konten
def abwesenheiten_im(con, mid, von, bis, nur_genehmigt=True):
    sql = "SELECT * FROM abwesenheiten WHERE mitarbeiter_id=? AND bis>=? AND von<=?"
    if nur_genehmigt:
        sql += " AND status='genehmigt'"
    return [dict(r) for r in con.execute(sql + " ORDER BY von", (mid, von, bis))]


def tage(con, m, von, bis):
    """Liste je Kalendertag mit Soll, Ist, Pausen, Abwesenheit, Saldo."""
    mods = modelle(m)
    d0, d1 = date.fromisoformat(von), date.fromisoformat(bis)
    zeiten = {}
    for z in con.execute("SELECT * FROM zeiten WHERE mitarbeiter_id=? AND datum BETWEEN ? AND ? ORDER BY datum, beginn",
                         (m["id"], von, bis)):
        zeiten.setdefault(z["datum"], []).append(z)
    abw = abwesenheiten_im(con, m["id"], von, bis)
    inhaber = m["lohnart"] == "inhaber"
    aus = []
    # Ruhezeit (§ 5 ArbZG): Ende des letzten Arbeitstags vor dem Zeitraum, um den ersten Tag prüfen zu können
    v = con.execute("SELECT datum, MAX(ende) AS ende FROM zeiten WHERE mitarbeiter_id=? AND datum<? AND datum>=? AND ende IS NOT NULL GROUP BY datum ORDER BY datum DESC LIMIT 1",
                    (m["id"], von, (d0 - timedelta(2)).isoformat())).fetchone()
    feierabend = datetime.fromisoformat(f"{v['datum']}T{v['ende']}") if v and v["ende"] else None
    t = d0
    while t <= d1:
        iso = t.isoformat()
        beschaeftigt = (not m["eintritt"] or iso >= m["eintritt"]) and (not m["austritt"] or iso <= m["austritt"])
        modell_tag = modell_am(mods, iso)["tage"][t.weekday()] if beschaeftigt else 0.0
        soll_basis = 0.0 if inhaber else modell_tag  # Inhaber: nur Iststunden, kein Soll
        ft = feiertag(iso)
        fr = "" if ft else arbeitsfrei(iso)   # arbeitsfreier Tag: kein Soll, aber auch nicht bezahlt
        tag = {"datum": iso, "wt": WOCHENTAG[t.weekday()], "feiertag": ft or fr, "frei": bool(fr), "bezahlt_ft": bool(ft),
               "soll": 0.0 if ft or fr else soll_basis, "arbeit": 0.0,
               "produktiv": 0.0, "gemein": 0.0, "pause": 0.0, "abw": "", "abw_std": 0.0, "urlaubstage": 0.0, "kst": {},
               "beginn": "", "ende": "", "laeuft": False, "hinweis": ""}
        if ft and soll_basis:
            tag["feiertag_std"] = soll_basis
        segs = zeiten.get(iso, [])
        letzte = None
        for z in segs:
            if z["ende"] is None:
                tag["laeuft"] = True
                if iso == date.today().isoformat():
                    jetzt_min = datetime.now().hour * 60 + datetime.now().minute
                    std = max(0, jetzt_min - minuten(z["beginn"])) / 60
                else:
                    std = 0.0
                    tag["hinweis"] = "Ende fehlt"
            else:
                std = dauer(z)
            tag["arbeit"] += std
            if z["auftrag_id"]:
                tag["produktiv"] += std
            else:
                tag["gemein"] += std
            schl = z["kst"] or ("ohne Kostenstelle" if z["auftrag_id"] else "Sonstiges")
            tag["kst"][schl] = tag["kst"].get(schl, 0) + std
            if letzte is not None and minuten(z["beginn"]) > letzte:
                tag["pause"] += (minuten(z["beginn"]) - letzte) / 60
            letzte = minuten(z["ende"]) if z["ende"] else None
            tag["beginn"] = tag["beginn"] or z["beginn"]
            tag["ende"] = z["ende"] or ""
        for a in abw:
            if a["von"] <= iso <= a["bis"]:
                tag["abw"] = a["art"]
                faktor = 0.5 if a["halbtag"] else 1.0
                if modell_tag and not ft and not fr:
                    if ABWESENHEIT.get(a["art"], ("", True))[1]:
                        tag["abw_std"] = round(soll_basis * faktor, 2)
                    elif a["art"] == "unbezahlt":
                        tag["soll"] = round(soll_basis * (1 - faktor), 2)
                    if a["art"] == "urlaub":
                        tag["urlaubstage"] = faktor
                break
        tag["ist"] = round(tag["arbeit"] + tag["abw_std"], 2)
        tag["zukunft"] = iso > date.today().isoformat()
        tag["saldo"] = 0.0 if tag["zukunft"] else round(tag["ist"] - tag["soll"], 2)
        for k in ("arbeit", "produktiv", "gemein", "pause"):
            tag[k] = round(tag[k], 2)
        if tag["arbeit"] > 9 and tag["pause"] < 0.75:
            tag["hinweis"] = tag["hinweis"] or "über 9 h: 45 min Pause nötig"
        elif tag["arbeit"] > 6 and tag["pause"] < 0.5:
            tag["hinweis"] = tag["hinweis"] or "über 6 h: 30 min Pause nötig"
        if tag["arbeit"] > 10:
            tag["hinweis"] = "mehr als 10 h Arbeitszeit"
        if segs and not inhaber:
            try:
                beginn_dt = datetime.fromisoformat(f"{iso}T{segs[0]['beginn']}")
                if feierabend and timedelta(0) < beginn_dt - feierabend < timedelta(hours=RUHEZEIT_STUNDEN):
                    ruhe = (beginn_dt - feierabend).total_seconds() / 3600
                    tag["hinweis"] = (tag["hinweis"] + " · " if tag["hinweis"] else "") + f"Ruhezeit nur {str(round(ruhe, 1)).replace('.', ',')} h (mindestens {RUHEZEIT_STUNDEN} h)"
                letztes = max((z["ende"] for z in segs if z["ende"]), default=None)
                feierabend = datetime.fromisoformat(f"{iso}T{letztes}") if letztes else None
            except ValueError:
                feierabend = None
        aus.append(tag)
        t += timedelta(1)
    return aus


def urlaub_anspruch(m, jahr):
    mods = modelle(m)
    anspruch = modell_am(mods, f"{jahr}-12-31")["urlaub"]
    monate = 12
    if m["eintritt"] and m["eintritt"][:4] == str(jahr):
        monate = 12 - int(m["eintritt"][5:7]) + (1 if m["eintritt"][8:10] == "01" else 0)
    if m["austritt"] and m["austritt"][:4] == str(jahr):
        ende = int(m["austritt"][5:7]) - (0 if m["austritt"][8:10] >= "28" else 1)
        start = 12 - monate + 1
        monate = max(0, ende - start + 1)
    if monate >= 12:
        return anspruch
    roh = anspruch * monate / 12
    return round(roh * 2 + 0.4999) / 2  # auf halbe Tage aufrunden


_VORLAUF = {}


def _vorlauf(con, m, von, bis):
    """Summe der Tagessalden und genommene Urlaubstage je Jahr von … bis (abgeschlossene Monate). Gerechnet und
    zwischengespeichert wird je Kalenderjahr: Eine nachträgliche Korrektur rechnet nur das betroffene Jahr neu,
    nicht die ganze Betriebszugehörigkeit."""
    saldo, urlaub = 0.0, {}
    for j in range(int(von[:4]), int(bis[:4]) + 1):
        a, b = max(von, f"{j}-01-01"), min(bis, f"{j}-12-31")
        if a > b:
            continue
        s_, u_ = _vorlauf_abschnitt(con, m, a, b)
        saldo += s_
        for k, v in u_.items():
            urlaub[k] = urlaub.get(k, 0) + v
    return saldo, urlaub


def _vorlauf_abschnitt(con, m, von, bis):
    z = con.execute("SELECT COUNT(*), TOTAL(id), TOTAL(julianday(datum) * (id % 83 + 1)), "
                    "TOTAL((CAST(substr(beginn,1,2) AS INTEGER) * 60 + CAST(substr(beginn,4,2) AS INTEGER)) * (id % 97 + 1)), "
                    "TOTAL((CAST(substr(IFNULL(ende,'99:99'),1,2) AS INTEGER) * 60 + CAST(substr(IFNULL(ende,'99:99'),4,2) AS INTEGER)) * (id % 89 + 1)) "
                    "FROM zeiten WHERE mitarbeiter_id=? AND datum BETWEEN ? AND ?", (m["id"], von, bis)).fetchone()
    a = con.execute("SELECT group_concat(id || art || von || bis || halbtag || IFNULL(status,''), '|') FROM abwesenheiten "
                    "WHERE mitarbeiter_id=? AND von<=? AND bis>=?", (m["id"], bis, von)).fetchone()[0]
    schluessel = (m["id"], von, bis, json.dumps(dict(m), sort_keys=True, default=str), tuple(z), a or "", date.today().isoformat())
    if schluessel in _VORLAUF:
        return _VORLAUF[schluessel]
    saldo, urlaub = 0.0, {}
    for t in tage(con, m, von, bis):
        saldo += t["saldo"]
        if t["urlaubstage"]:
            j = int(t["datum"][:4])
            urlaub[j] = urlaub.get(j, 0) + t["urlaubstage"]
    if len(_VORLAUF) > 3000:
        _VORLAUF.clear()
    _VORLAUF[schluessel] = (saldo, urlaub)
    return saldo, urlaub


def konten(con, m, stichtag):
    """Überstundenkonto und Urlaubskonto zum Stichtag (date)."""
    if isinstance(m, int):
        m = con.execute("SELECT * FROM mitarbeiter WHERE id=?", (m,)).fetchone()
    beginn = konten_beginn(m)
    st = stichtag.isoformat()
    ueber = m["ueberstunden_start"] or 0.0
    jahr_urlaub = {}
    if st >= beginn:
        # Abgeschlossene Monate (bis Ende Vormonat) aus dem Zwischenspeicher, nur der laufende Monat wird neu gerechnet;
        # jede Änderung an Zeiten, Abwesenheiten oder Mitarbeiterdaten davor ändert den Fingerabdruck und rechnet neu.
        grenze = (stichtag.replace(day=1) - timedelta(1)).isoformat()
        ab = beginn
        if grenze >= beginn:
            saldo_v, urlaub_v = _vorlauf(con, m, beginn, grenze)
            ueber += saldo_v
            for j, u in urlaub_v.items():
                jahr_urlaub[j] = jahr_urlaub.get(j, 0) + u
            ab = (date.fromisoformat(grenze) + timedelta(1)).isoformat()
        for t in tage(con, m, ab, st):
            ueber += t["saldo"]
            if t["urlaubstage"]:
                j = int(t["datum"][:4])
                jahr_urlaub[j] = jahr_urlaub.get(j, 0) + t["urlaubstage"]
    korr = {"ueberstunden": 0.0}
    korr_urlaub = {}
    for k in con.execute("SELECT * FROM kontobuchungen WHERE mitarbeiter_id=? AND datum<=?", (m["id"], st)):
        if k["konto"] == "ueberstunden":
            korr["ueberstunden"] += k["wert"]
        else:
            j = int(k["datum"][:4])
            korr_urlaub[j] = korr_urlaub.get(j, 0) + k["wert"]
    ueber += korr["ueberstunden"]
    # Urlaub: Jahr für Jahr ab Beginn
    rest = m["urlaub_start"] or 0.0
    j0 = int(beginn[:4])
    zeilen = []
    neu_eingetreten = bool(m["eintritt"]) and beginn <= m["eintritt"]
    for j in range(j0, stichtag.year + 1):
        # Startjahr: „urlaub_start“ = am Konten-Beginn noch offener Urlaub (inkl. Übertrag); nur bei Eintritt kommt der Anspruch dazu
        anspruch = urlaub_anspruch(m, j) if j > j0 or neu_eingetreten or beginn[5:] == "01-01" else 0.0
        uebertrag = rest
        genommen = jahr_urlaub.get(j, 0)
        k = korr_urlaub.get(j, 0)
        rest = round(uebertrag + anspruch + k - genommen, 2)
        zeilen.append({"jahr": j, "uebertrag": round(uebertrag, 2), "anspruch": anspruch, "korrektur": round(k, 2),
                       "genommen": genommen, "rest": rest})
    geplant = 0.0
    for a in abwesenheiten_im(con, m["id"], (stichtag + timedelta(1)).isoformat(), f"{stichtag.year}-12-31"):
        if a["art"] == "urlaub":
            for t in tage(con, m, max(a["von"], (stichtag + timedelta(1)).isoformat()), min(a["bis"], f"{stichtag.year}-12-31")):
                geplant += t["urlaubstage"]
    return {"ueberstunden": round(ueber, 2), "urlaub_rest": rest, "urlaub_geplant": geplant,
            "urlaub_jahre": zeilen, "beginn": beginn}


def monat_daten(con, mid, monat):
    m = con.execute("SELECT * FROM mitarbeiter WHERE id=?", (mid,)).fetchone()
    if not m:
        raise Fehler("Mitarbeiter nicht gefunden.", 404)
    j, mo = int(monat[:4]), int(monat[5:7])
    von = date(j, mo, 1)
    bis = date(j, mo, calendar.monthrange(j, mo)[1])
    ts = tage(con, m, von.isoformat(), bis.isoformat())
    summe = {k: round(sum(t[k] for t in ts), 2) for k in ("soll", "ist", "arbeit", "produktiv", "gemein", "pause", "saldo", "urlaubstage")}
    je_abw = {}
    for t in ts:
        if t["abw"]:
            je_abw[t["abw"]] = round(je_abw.get(t["abw"], 0) + t["abw_std"], 2)
    summe["feiertag"] = round(sum(t.get("feiertag_std", 0) for t in ts), 2)
    kst = {}
    for t in ts:
        for k, v in t["kst"].items():
            kst[k] = round(kst.get(k, 0) + v, 2)
    zs_tage = zuschlaege(con, m, von.isoformat(), bis.isoformat())
    zs = {}
    for v in zs_tage.values():
        for k, h_ in v.items():
            zs[k] = round(zs.get(k, 0) + h_, 2)
    plan = plan_von(modell_am(modelle(m), bis.isoformat()).get("plan"))
    zs_liste = [{"art": k, "name": n, "prozent": plan["zuschlaege"].get(k, std) if plan else std, "stunden": zs[k]}
                for k, n, std in ZUSCHLAG_ARTEN if zs.get(k)]
    k_ende = konten(con, m, min(bis, date.today()) if von <= date.today() else bis)
    k_vor = konten(con, m, von - timedelta(1))
    return {"mitarbeiter": dict(m, name=name(m)), "monat": monat, "tage": ts, "summe": summe, "abwesenheit": je_abw,
            "kostenstellen": kst, "konten": k_ende, "konten_vormonat": k_vor,
            "zuschlaege": zs_liste, "plan": {"name": plan["name"], "regelung": plan["regelung"]} if plan else None,
            "korrekturen": [dict(r) for r in con.execute("SELECT * FROM kontobuchungen WHERE mitarbeiter_id=? AND datum BETWEEN ? AND ? "
                                                         "ORDER BY datum", (mid, von.isoformat(), bis.isoformat()))],
            "abw_namen": {k: v[0] for k, v in ABWESENHEIT.items()}, "kst_namen": KST_NAMEN}


def monatsbeleg_html(con, mid, monat, firma, als_pdf=False, sig=None):
    d = monat_daten(con, mid, monat)
    m = d["mitarbeiter"]
    s = d["summe"]
    n = lambda v: de(v) if v else ""  # noqa: E731
    zeilen = []
    for t in d["tage"]:
        we = t["wt"] in ("Sa", "So") or t["feiertag"]
        abw = ABWESENHEIT.get(t["abw"], ("", True))[0]
        zeilen.append(
            f'<tr class="{"we" if we else ""}"><td class="nw">{t["wt"]} {t["datum"][8:10]}.{t["datum"][5:7]}.</td>'
            f'<td>{h(t["feiertag"] or abw)}{" ½" if t["urlaubstage"] == 0.5 else ""}</td>'
            f'<td class="nw">{t["beginn"]}{"–" + t["ende"] if t["ende"] else ("–…" if t["laeuft"] else "")}</td>'
            f'<td class="r">{n(t["pause"])}</td><td class="r">{n(t["produktiv"])}</td><td class="r">{n(t["gemein"])}</td>'
            f'<td class="r">{n(t["abw_std"])}</td><td class="r">{n(t["soll"])}</td><td class="r">{n(t["ist"])}</td>'
            f'<td class="r {"neg" if t["saldo"] < 0 else ""}">{de(t["saldo"]) if t["saldo"] or t["soll"] or t["ist"] else ""}</td>'
            f'<td class="hin">{h(t["hinweis"])}</td></tr>')
    kst = "".join(f'<tr><td>{h(KST_NAMEN.get(k, k))}</td><td class="r">{de(v)} h</td></tr>'
                  for k, v in sorted(d["kostenstellen"].items(), key=lambda x: -x[1]))
    abw = "".join(f'<tr><td>{h(ABWESENHEIT.get(k, (k,))[0])}</td><td class="r">{de(v)} h</td></tr>' for k, v in d["abwesenheit"].items())
    if s["feiertag"]:
        abw += f'<tr><td>Feiertage (bezahlt, nicht im Soll)</td><td class="r">{de(s["feiertag"])} h</td></tr>'
    zsb = "".join(f'<tr><td>{h(z["name"])} ({de(z["prozent"], 0)} %)</td><td class="r">{de(z["stunden"])} h</td></tr>' for z in d["zuschlaege"])
    if d["plan"]:
        zsb = (f'<tr><td colspan="2" style="color:#555">{h(d["plan"]["name"])} · {"fix: Überstunden werden ausgezahlt" if d["plan"]["regelung"] == "fix" else "flexibel: Arbeitszeitkonto"}</td></tr>'
               + (zsb or '<tr><td colspan="2">keine</td></tr>'))
    korr = "".join(f'<tr><td>{de_datum(k["datum"])} {h(k["text"] or "Korrektur")}</td><td class="r">{de(k["wert"])} {"h" if k["konto"] == "ueberstunden" else "Tage"}</td></tr>'
                   for k in d["korrekturen"])
    kv, ke = d["konten_vormonat"], d["konten"]
    monat_name = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"][int(monat[5:7]) - 1]
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Monatsbeleg {h(m['name'])} {monat}</title><style>
@page {{ size: A4; margin: 12mm 12mm 14mm 14mm; }}
body {{ font: 8.6pt/1.3 Calibri, "Segoe UI", Arial, sans-serif; color: #222; margin: 0; }}
{"" if als_pdf else "@media screen{html{background:#888} body{background:#fff;width:210mm;margin:10mm auto;padding:12mm 12mm 14mm 14mm;box-sizing:border-box;box-shadow:0 2px 12px rgba(0,0,0,.3)}}"}
.kopf {{ display:flex; justify-content:space-between; align-items:flex-end; border-bottom:.8pt solid #333; padding-bottom:2mm; margin-bottom:3mm; }}
h1 {{ font-size:14pt; margin:0; }} .unter {{ color:#555; }}
table {{ border-collapse:collapse; }} table.t {{ width:100%; }}
table.t th {{ text-align:right; font-size:7.6pt; border-bottom:.8pt solid #333; padding:1mm 1.2mm; }} table.t th.l {{ text-align:left; }}
table.t td {{ padding:.55mm 1.2mm; border-bottom:.25pt solid #ddd; }} tr.we td {{ background:#f2f0ec; }}
.r {{ text-align:right; }} .nw {{ white-space:nowrap; }} .neg {{ color:#a33; }} .hin {{ color:#a33; font-size:7.4pt; }}
tr.sum td {{ font-weight:700; border-top:.8pt solid #333; border-bottom:.8pt solid #333; }}
.unten {{ display:flex; gap:8mm; margin-top:5mm; page-break-inside:avoid; }} .unten > div {{ flex:1; }}
.unten table {{ width:100%; }} .unten th {{ text-align:left; border-bottom:.8pt solid #333; padding:1mm; font-size:8pt; }}
.unten td {{ padding:.6mm 1mm; border-bottom:.25pt solid #ddd; }} .ges td {{ font-weight:700; }}
.sig {{ margin-top:10mm; display:flex; gap:20mm; page-break-inside:avoid; }} .sig > div {{ width:65mm; }} .sig img {{ height:15mm; display:block; }}
.sig .l {{ border-top:.6pt solid #333; padding-top:1mm; color:#555; font-size:7.6pt; }} .sig .leer {{ height:15mm; }} .sig .warn {{ color:#a33; font-size:7.4pt; }}
</style></head><body>
<div class="kopf"><div><h1>Monatsbeleg {monat_name} {monat[:4]}</h1><div class="unter">{m['nummer']} · {h(m['name'])}</div></div>
<div class="unter" style="text-align:right">{h(firma)}<br>erstellt am {date.today().strftime('%d.%m.%Y')}</div></div>
<table class="t"><thead><tr><th class="l">Datum</th><th class="l">Feiertag / Abwesenheit</th><th class="l">Arbeitszeit</th><th>Pause</th><th>Produktiv</th>
<th>Nicht direkt</th><th>Abwes.</th><th>Soll</th><th>Ist</th><th>Saldo</th><th class="l"></th></tr></thead><tbody>{''.join(zeilen)}
<tr class="sum"><td colspan="3">Summe {monat_name}</td><td class="r">{de(s['pause'])}</td><td class="r">{de(s['produktiv'])}</td><td class="r">{de(s['gemein'])}</td>
<td class="r">{de(sum(d['abwesenheit'].values()))}</td><td class="r">{de(s['soll'])}</td><td class="r">{de(s['ist'])}</td><td class="r">{de(s['saldo'])}</td><td></td></tr></tbody></table>
<div class="unten">
<div><table><tr><th colspan="2">Stunden nach Tätigkeit</th></tr>{kst or '<tr><td colspan="2">keine</td></tr>'}</table></div>
<div><table><tr><th colspan="2">Abwesenheiten</th></tr>{abw or '<tr><td colspan="2">keine</td></tr>'}</table>
{f'<table style="margin-top:4mm"><tr><th colspan="2">Zuschlagspflichtige Stunden</th></tr>{zsb}</table>' if zsb else ''}</div>
<div><table><tr><th colspan="2">Konten</th></tr>
<tr><td>Überstunden Vormonat</td><td class="r">{de(kv['ueberstunden'])} h</td></tr>
<tr><td>Saldo {monat_name}</td><td class="r">{de(s['saldo'])} h</td></tr>{korr}
<tr class="ges"><td>Überstunden Ende {monat_name}</td><td class="r">{de(ke['ueberstunden'])} h</td></tr>
<tr><td>Urlaub genommen {monat_name}</td><td class="r">{de(s['urlaubstage'], 1)} Tage</td></tr>
<tr class="ges"><td>Resturlaub</td><td class="r">{de(ke['urlaub_rest'], 1)} Tage</td></tr></table></div></div>
{sig_html(sig or {})}
{'' if als_pdf else kern.skript(kern.DRUCKEN_JS)}
</body></html>"""


def sig_html(sig):
    """Unterschriftsfelder im Monatsbeleg: digitale Unterschrift (Tablet/Stempeluhr) oder leere Linie."""
    teile = []
    for rolle, text in (("mitarbeiter", "Unterschrift Mitarbeiter"), ("arbeitgeber", "Unterschrift Arbeitgeber")):
        x = sig.get(rolle)
        if x and x.get("bild"):
            z = x["zeit"]
            teile.append(f'<div><img src="{x["bild"]}" alt="Unterschrift"><div class="l">{text}: {h(x["name"])}, {z[8:10]}.{z[5:7]}.{z[:4]} {z[11:16]} Uhr'
                         + (' <span class="warn">– Zeiten danach geändert</span>' if x.get("geaendert") else "") + "</div></div>")
        else:
            teile.append(f'<div><div class="leer"></div><div class="l">Datum, {text}</div></div>')
    return '<div class="sig">' + "".join(teile) + "</div>"


# ---------------------------------------------------------------- Kalender
def kalender_eintraege(con, von, bis, mit_grund=True):
    """Abwesenheiten (genehmigt und beantragt) und Feiertage für den Kalender.
    Ohne Personalrecht wird nur „abwesend“ gezeigt, nicht der Grund (z. B. Krankheit)."""
    abw = []
    for a in con.execute("SELECT a.*, m.vorname, m.nachname, m.kuerzel FROM abwesenheiten a JOIN mitarbeiter m ON m.id=a.mitarbeiter_id "
                         "WHERE a.status IN ('genehmigt','beantragt') AND a.bis>=? AND a.von<=? ORDER BY a.von", (von, bis)):
        art = a["art"] if mit_grund else "abwesend"
        abw.append({"id": a["id"], "mitarbeiter_id": a["mitarbeiter_id"], "name": f"{a['vorname']} {a['nachname']}".strip(),
                    "kuerzel": a["kuerzel"] or a["vorname"], "art": art,
                    "art_name": ABWESENHEIT.get(art, ("abwesend",))[0] if mit_grund else "abwesend",
                    "von": a["von"], "bis": a["bis"], "halbtag": a["halbtag"], "beantragt": a["status"] == "beantragt"})
    ft = []
    for j in range(int(von[:4]), int(bis[:4]) + 1):
        ft += [{"datum": d, "name": n} for d, n in sorted(feiertage(j).items()) if von <= d <= bis]
        ft += [{"datum": d, "name": f"{n} (arbeitsfrei)", "frei": True} for d, n in sorted(freie_tage(j).items()) if von <= d <= bis]
    return {"abwesenheiten": abw, "feiertage": ft}


# ---------------------------------------------------------------- Kapazität
def verfuegbar_tage(con, m, von, bis):
    """{Datum: verfügbare Stunden} eines Mitarbeiters: Arbeitszeitmodell (auch beim Inhaber), ohne Feiertage,
    abzüglich genehmigter Abwesenheiten (Urlaub, Krank, Berufsschule …; halbe Tage zur Hälfte)."""
    mods = modelle(m)
    abw = abwesenheiten_im(con, m["id"], von, bis)
    aus = {}
    t, ende = date.fromisoformat(von), date.fromisoformat(bis)
    while t <= ende:
        iso = t.isoformat()
        h = 0.0
        if (not m["eintritt"] or iso >= m["eintritt"]) and (not m["austritt"] or iso <= m["austritt"]) and not frei_oder_feiertag(iso):
            h = float(modell_am(mods, iso)["tage"][t.weekday()] or 0)
            for a in abw:
                if a["von"] <= iso <= a["bis"]:
                    h *= 0.5 if a["halbtag"] else 0.0
                    break
        aus[iso] = h
        t += timedelta(1)
    return aus


def kapazitaet(con, von, bis, termine, tagesstunden=8.0):
    """Kapazität je Mitarbeiter und Woche (Montag): verfügbar, verplant (Termine mit Mitarbeitern), frei.
    Ein Termin mit Stunden verteilt diese gleichmäßig auf seine Mitarbeiter und deren verfügbare Tage; ohne Stunden ist
    jeder zugeordnete Mitarbeiter an diesen Tagen voll verplant. Termine ohne Mitarbeiter stehen unter „nicht zugeordnet“."""
    def woche(iso):
        d = date.fromisoformat(iso)
        return (d - timedelta(d.weekday())).isoformat()
    mas = [dict(r) for r in con.execute("SELECT * FROM mitarbeiter WHERE aktiv=1 ORDER BY nummer")]
    mas = [m for m in mas if (not m["austritt"] or m["austritt"] >= von) and (not m["eintritt"] or m["eintritt"] <= bis)]
    # Termine können vor „von“ beginnen bzw. nach „bis“ enden: für die Verteilung den ganzen Zeitraum kennen
    ganz_von = min([von] + [t["von"] for t in termine]); ganz_bis = max([bis] + [t["bis"] for t in termine])
    verf = {m["id"]: verfuegbar_tage(con, m, ganz_von, ganz_bis) for m in mas}
    zeilen = {m["id"]: {"id": m["id"], "name": name(m), "kuerzel": m["kuerzel"] or (m["vorname"] or "")[:3], "wochen": {}} for m in mas}
    ohne = {}

    def buche(mid, iso, h, art):
        if not (von <= iso <= bis):
            return
        if mid is None:
            ohne[woche(iso)] = ohne.get(woche(iso), 0) + h
            return
        w = zeilen[mid]["wochen"].setdefault(woche(iso), {"verfuegbar": 0.0, "verplant": 0.0})
        w[art] += h
    for mid, tage in verf.items():
        for iso, h in tage.items():
            buche(mid, iso, h, "verfuegbar")
    for t in termine:
        if t.get("erledigt") and t["bis"] < date.today().isoformat():
            continue
        try:
            ids = [int(x) for x in json.loads(t.get("mitarbeiter") or "[]") if int(x) in zeilen]
        except (ValueError, TypeError):
            ids = []
        tage_alle = []
        d = date.fromisoformat(t["von"])
        while d <= date.fromisoformat(t["bis"]):
            tage_alle.append(d.isoformat())
            d += timedelta(1)
        if not ids:
            werk = [x for x in tage_alle if date.fromisoformat(x).weekday() < 5 and not frei_oder_feiertag(x)] or tage_alle
            ges = t["stunden"] if t.get("stunden") is not None else len(werk) * tagesstunden
            for x in werk:
                buche(None, x, ges / len(werk), "verplant")
            continue
        for mid in ids:
            tage = [x for x in tage_alle if verf[mid].get(x, 0) > 0]
            if t.get("stunden") is not None:
                if not tage:   # Mitarbeiter an allen Tagen abwesend: Stunden nicht verlieren, sondern als offen zeigen
                    werk = [x for x in tage_alle if date.fromisoformat(x).weekday() < 5 and not frei_oder_feiertag(x)] or tage_alle
                    for x in werk:
                        buche(None, x, t["stunden"] / len(ids) / len(werk), "verplant")
                    continue
                anteil = t["stunden"] / len(ids)
                summe_v = sum(verf[mid][x] for x in tage)
                for x in tage:
                    buche(mid, x, anteil * verf[mid][x] / summe_v, "verplant")
            else:
                for x in tage:
                    buche(mid, x, verf[mid][x], "verplant")
    for z in zeilen.values():
        for w in z["wochen"].values():
            w["verfuegbar"], w["verplant"] = round(w["verfuegbar"], 1), round(w["verplant"], 1)
            w["frei"] = round(w["verfuegbar"] - w["verplant"], 1)
    return {"mitarbeiter": list(zeilen.values()), "ohne_zuordnung": {k: round(v, 1) for k, v in ohne.items()}}


# ---------------------------------------------------------------- Lohnzahlungen
def bankarbeitstag_zurueck(t, n=0):
    """n-ter Bankarbeitstag vom Ende (n=0: letzter) eines Datums aus rückwärts."""
    while True:
        if t.weekday() < 5 and not feiertag(t.isoformat()) and not (t.month == 12 and t.day in (24, 31)):
            if n == 0:
                return t
            n -= 1
        t -= timedelta(1)


def lohn_faelligkeiten(monat):
    j, mo = int(monat[:4]), int(monat[5:7])
    ende = date(j, mo, calendar.monthrange(j, mo)[1])
    folgemonat = ende + timedelta(1)
    steuer = date(folgemonat.year, folgemonat.month, 10)
    while steuer.weekday() >= 5 or feiertag(steuer.isoformat()):
        steuer += timedelta(1)
    return {"netto": bankarbeitstag_zurueck(ende).isoformat(), "sv": bankarbeitstag_zurueck(ende, 2).isoformat(),
            "steuer": steuer.isoformat()}


def lohn_liste(con, monat):
    j, mo = int(monat[:4]), int(monat[5:7])
    von, bis = f"{monat}-01", f"{monat}-{calendar.monthrange(j, mo)[1]:02d}"
    aus = []
    for m in con.execute("SELECT * FROM mitarbeiter WHERE (aktiv=1 OR austritt>=?) AND (eintritt='' OR eintritt<=?) AND lohnart<>'inhaber' "
                         "ORDER BY nummer", (von, bis)):
        l = con.execute("SELECT * FROM lohn WHERE mitarbeiter_id=? AND monat=?", (m["id"], monat)).fetchone()
        ts = tage(con, m, von, bis)
        zahl_ids = json.loads(l["zahlungen"] or "{}") if l else {}
        zahlungen_d = {k: dict(r) for k, zid in zahl_ids.items()
                for r in [con.execute("SELECT id, nummer, betrag, faellig, bezahlt FROM zahlungen WHERE id=?", (zid,)).fetchone()] if r}
        aus.append({"mitarbeiter": dict(m, name=name(m), lohnart_name=LOHNARTEN.get(m["lohnart"], m["lohnart"])),
                    "lohn": dict(l) if l else None, "zahlungen": zahlungen_d,
                    "stunden": round(sum(t["arbeit"] for t in ts), 2), "ist": round(sum(t["ist"] for t in ts), 2),
                    "soll": round(sum(t["soll"] for t in ts), 2),
                    "urlaub": sum(t["urlaubstage"] for t in ts), "krank": sum(1 for t in ts if t["abw"] in ("krank", "kind_krank") and t["soll"]),
                    "schaetzung": round(m["stundenlohn"] * sum(t["ist"] for t in ts), 2) if m["lohnart"] in ("stunde", "minijob") else m["gehalt"],
                    "hinweise": lohn_hinweise(m, monat, sum(t["ist"] for t in ts), sum(t["soll"] + (t.get("feiertag_std") or 0) for t in ts))})
    e = HILFE["einstellungen"](con)
    return {"monat": monat, "zeilen": aus, "faellig": lohn_faelligkeiten(monat), "finanzamt_id": e.get("lohn_finanzamt_id"),
            "empfaenger": [dict(r) for r in con.execute("SELECT id, kurzname, gruppe, iban FROM lieferanten WHERE aktiv=1 AND gruppe<>'Mitarbeiter' "
                                                        "ORDER BY gruppe='Finanzamt' DESC, kurzname")]}


def lohn_speichern(con, mid, monat, d):
    werte = {k: round(zahl(d[k]), 2) for k in ("brutto", "netto", "steuer", "sv") if k in d}
    if "notiz" in d:
        werte["notiz"] = d["notiz"] or ""
    werte["geaendert"] = jetzt()
    if con.execute("SELECT 1 FROM lohn WHERE mitarbeiter_id=? AND monat=?", (mid, monat)).fetchone():
        con.execute(f"UPDATE lohn SET {','.join(k + '=?' for k in werte)} WHERE mitarbeiter_id=? AND monat=?", list(werte.values()) + [mid, monat])
    else:
        werte.update({"mitarbeiter_id": mid, "monat": monat, "angelegt": jetzt()})
        con.execute(f"INSERT INTO lohn ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})", list(werte.values()))
    return con.execute("SELECT * FROM lohn WHERE mitarbeiter_id=? AND monat=?", (mid, monat)).fetchone()


def lohn_zahlungen(con, monat, d):
    """Erzeugt Zahlungsaufträge: Netto je Mitarbeiter, Lohnsteuer gesammelt ans Finanzamt, SV je Krankenkasse."""
    e = HILFE["einstellungen"](con)
    fa = int(d.get("finanzamt_id") or e.get("lohn_finanzamt_id") or 0)
    if d.get("finanzamt_id"):
        con.execute("INSERT OR REPLACE INTO einstellungen VALUES ('lohn_finanzamt_id', ?)", (json.dumps(fa),))
    fae = lohn_faelligkeiten(monat)
    mon_text = f"{monat[5:7]}/{monat[:4]}"
    neu, fehlt = [], []

    def zahlung(lid, betrag, faellig, bemerkung, belegnr):
        l = con.execute("SELECT * FROM lieferanten WHERE id=?", (lid,)).fetchone()
        werte = {"nummer": HILFE["zahlungsnummer"](con), "lieferant_id": lid, "belegnr": belegnr, "belegdatum": date.today().isoformat(),
                 "bemerkung": bemerkung, "empfaenger": l["empfaenger"] or l["kurzname"], "iban": l["iban"], "bic": l["bic"],
                 "betrag": round(betrag, 2), "vorsteuer": 0, "faellig": faellig, "bezahlung": "Überweisung",
                 "angelegt": jetzt(), "geaendert": jetzt()}
        cur = con.execute(f"INSERT INTO zahlungen ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})", list(werte.values()))
        neu.append(werte["nummer"])
        return cur.lastrowid

    steuer_summe, steuer_namen = 0.0, []
    sv_je_kasse = {}
    lohn_zeilen = []
    for l in con.execute("SELECT l.*, m.vorname, m.nachname, m.kasse_id, m.lieferant_id AS ma_lief, m.iban FROM lohn l "
                         "JOIN mitarbeiter m ON m.id=l.mitarbeiter_id WHERE l.monat=?", (monat,)):
        if d.get("nur") and l["mitarbeiter_id"] not in d["nur"]:
            continue
        lohn_zeilen.append(l)
        z = json.loads(l["zahlungen"] or "{}")
        nm = f"{l['vorname']} {l['nachname']}".strip()
        if l["netto"] and not z.get("netto"):
            lid = lieferant_pflegen(con, l["mitarbeiter_id"])
            if not lid or not l["iban"]:
                fehlt.append(f"{nm}: keine IBAN hinterlegt")
            else:
                z["netto"] = zahlung(lid, l["netto"], fae["netto"], f"Lohn/Gehalt {mon_text}", f"Lohn {mon_text}")
        if l["steuer"] and not z.get("steuer"):
            steuer_summe += l["steuer"]
            steuer_namen.append(l["id"])
        if l["sv"] and not z.get("sv"):
            if not l["kasse_id"]:
                fehlt.append(f"{nm}: keine Krankenkasse beim Mitarbeiter gewählt")
            else:
                sv_je_kasse.setdefault(l["kasse_id"], []).append(l["id"])
        con.execute("UPDATE lohn SET zahlungen=? WHERE id=?", (json.dumps(z), l["id"]))
    if steuer_summe:
        if not fa:
            fehlt.append("Lohnsteuer: bitte das Finanzamt (Lieferant) wählen")
        else:
            zid = zahlung(fa, steuer_summe, fae["steuer"], f"Lohnsteuer-Anmeldung {mon_text}", f"LStA {mon_text}")
            for lid in steuer_namen:
                r = con.execute("SELECT zahlungen FROM lohn WHERE id=?", (lid,)).fetchone()
                z = json.loads(r["zahlungen"] or "{}")
                z["steuer"] = zid
                con.execute("UPDATE lohn SET zahlungen=? WHERE id=?", (json.dumps(z), lid))
    for kasse, ids in sv_je_kasse.items():
        betrag = sum(con.execute("SELECT sv FROM lohn WHERE id=?", (i,)).fetchone()["sv"] for i in ids)
        zid = zahlung(kasse, betrag, fae["sv"], f"Beitragsnachweis {mon_text}", f"SV {mon_text}")
        for i in ids:
            r = con.execute("SELECT zahlungen FROM lohn WHERE id=?", (i,)).fetchone()
            z = json.loads(r["zahlungen"] or "{}")
            z["sv"] = zid
            con.execute("UPDATE lohn SET zahlungen=? WHERE id=?", (json.dumps(z), i))
    return {"neu": neu, "fehlt": fehlt}


# ---------------------------------------------------------------- Stempeluhr (eigene Zeiten)
def eigener_mitarbeiter(con):
    b = benutzer.aktuell()
    if not b or not b["mitarbeiter_id"]:
        raise Fehler("Dieser Benutzer ist keinem Mitarbeiter zugeordnet. Bitte im Büro unter Einstellungen > Benutzer verknüpfen.", 403)
    m = con.execute("SELECT * FROM mitarbeiter WHERE id=? AND aktiv=1", (b["mitarbeiter_id"],)).fetchone()
    if not m:
        raise Fehler("Der zugeordnete Mitarbeiter ist nicht aktiv.", 403)
    return m


def offene_auftraege(con):
    e = HILFE["einstellungen"](con)
    ende = tuple(e.get("status_ende") or ["Abgerechnet", "Erledigt", "Abgesagt"])
    aktiv = ("Auftrag", "Fertigung", "Montage")
    zeilen = con.execute(f"SELECT a.id, a.nummer, a.bezeichnung, a.status, a.titel, k.kurzname AS kunde FROM auftraege a JOIN kunden k ON k.id=a.kunde_id "
                         f"WHERE IFNULL(a.status,'') NOT IN ({','.join('?' * len(ende))}) ORDER BY a.nummer DESC", ende).fetchall()
    aus = []
    for r in zeilen:
        a = dict(r)
        try:
            tl = json.loads(a.get("titel") or "[]")
        except ValueError:
            tl = []
        # buchbare Titel (abgeschlossene nicht mehr anbieten)
        a["titel"] = [{"nr": t.get("nr"), "name": t.get("name") or ""} for t in tl if t.get("nr") and not t.get("buchung_gesperrt")]
        aus.append(a)
    return sorted(aus, key=lambda a: (a["status"] not in aktiv,))


def taetigkeiten(con):
    e = HILFE["einstellungen"](con)
    kst = [k for k in HILFE["kostenstellen"](con) if k]
    return {"produktiv": [{"kst": k, "name": KST_NAMEN.get(k, k.title())} for k in kst],
            "gemein": list(e.get("zeit_gemeinkosten") or [])}


def mein_plan(con, m, tage_voraus=6):
    """Termine, denen der Mitarbeiter zugeordnet ist, von heute bis in tage_voraus Tagen (für Stempeluhr und Wochenplan)."""
    heute = date.today().isoformat()
    bis = (date.today() + timedelta(tage_voraus)).isoformat()
    try:
        rows = con.execute("SELECT t.id, t.typ, t.titel, t.von, t.bis, t.zeit_von, t.zeit_bis, t.notiz, t.auftrag_id, t.mitarbeiter, "
                           "a.nummer AS auftragsnr, a.bezeichnung, k.kurzname AS kunde FROM termine t LEFT JOIN auftraege a ON a.id=t.auftrag_id "
                           "LEFT JOIN kunden k ON k.id=a.kunde_id WHERE t.bis>=? AND t.von<=? AND COALESCE(t.erledigt,0)=0 "
                           "ORDER BY t.von, t.zeit_von", (heute, bis)).fetchall()
    except Exception:  # noqa: BLE001  ältere Datenbank ohne Spalte
        return []
    aus = []
    for r in rows:
        try:
            ids = {int(x) for x in json.loads(r["mitarbeiter"] or "[]")}
        except (ValueError, TypeError):
            ids = set()
        if m["id"] in ids:
            d = dict(r)
            d.pop("mitarbeiter", None)
            d["heute"] = d["von"] <= heute <= d["bis"]
            aus.append(d)
    return aus


def stempel_status(con, m):
    heute = date.today().isoformat()
    offen = con.execute("SELECT z.*, a.nummer AS auftragsnr, a.bezeichnung AS auftrag FROM zeiten z INDEXED BY zeiten_offen LEFT JOIN auftraege a ON a.id=z.auftrag_id "
                        "WHERE z.mitarbeiter_id=? AND z.ende IS NULL ORDER BY z.datum DESC, z.beginn DESC LIMIT 1", (m["id"],)).fetchone()
    montag = (date.today() - timedelta(date.today().weekday())).isoformat()
    woche = tage(con, m, montag, heute)
    k = konten(con, m, date.today())
    letzte = con.execute("SELECT z.auftrag_id, z.kst, z.taetigkeit, z.titel FROM zeiten z WHERE z.mitarbeiter_id=? ORDER BY z.datum DESC, z.beginn DESC LIMIT 1",
                         (m["id"],)).fetchone()
    return {"mitarbeiter": {"id": m["id"], "name": name(m), "kuerzel": m["kuerzel"]}, "plan": mein_plan(con, m),
            "laeuft": dict(offen) if offen and offen["datum"] == heute else None,
            "vergessen": dict(offen) if offen and offen["datum"] < heute else None,
            "heute": zeiten_liste(con, m["id"], heute, heute), "heute_std": woche[-1]["arbeit"], "heute_pause": woche[-1]["pause"],
            "woche_std": round(sum(t["arbeit"] for t in woche), 2), "woche_soll": round(sum(t["soll"] for t in woche), 2),
            "ueberstunden": k["ueberstunden"], "urlaub_rest": k["urlaub_rest"], "urlaub_geplant": k["urlaub_geplant"],
            "letzte": dict(letzte) if letzte else None, "inhaber": m["lohnart"] == "inhaber", "serverzeit": datetime.now().isoformat(timespec="seconds")}


# Die Stempeluhr am Handy arbeitet auch ohne Netz und überträgt später – die Uhrzeit kommt dann vom Handy. Damit das Büro sieht,
# was nicht im Augenblick des Stempelns ankam: Ab STEMPEL_TOLERANZ Minuten Verzug wird der Eintrag als „nachträglich eingegangen“
# gekennzeichnet. Was älter als STEMPEL_MAX_TAGE Tage ist, wird nicht mehr übernommen (dafür gibt es den Nachtrag bzw. das Büro).
STEMPEL_TOLERANZ = 15
STEMPEL_MAX_TAGE = 7


def monat_abgerechnet(con, mid, monat):
    """Für diesen Monat sind schon Lohnzahlungen angelegt: Die Zeiten dahinter sollen sich nicht mehr unbemerkt ändern."""
    l = con.execute("SELECT zahlungen FROM lohn WHERE mitarbeiter_id=? AND monat=?", (mid, monat)).fetchone()
    try:
        return bool(l and json.loads(l["zahlungen"] or "{}"))
    except ValueError:
        return False


def stempeln(con, m, ev):
    """Ein Stempel-Ereignis verarbeiten. ev: {client_id, aktion: start|pause|ende, zeit: 'YYYY-MM-DDTHH:MM', auftrag_id, kst, taetigkeit}"""
    cid = str(ev.get("client_id") or "")[:64]
    if cid:
        alt = con.execute("SELECT ergebnis FROM stempel_ereignisse WHERE client_id=?", (cid,)).fetchone()
        if alt:
            return json.loads(alt["ergebnis"] or "{}")
    zeit = (ev.get("zeit") or datetime.now().isoformat(timespec="minutes"))[:16]
    try:
        zp = datetime.fromisoformat(zeit)
    except ValueError:
        raise Fehler("Zeitpunkt nicht lesbar.")
    eingang = datetime.now()
    if zp > eingang + timedelta(minutes=10):
        zp = eingang  # Handyuhr geht vor
    datum, uhr = zp.date().isoformat(), zp.strftime("%H:%M")
    aktion = ev.get("aktion")
    verzug = max(0, int((eingang - zp).total_seconds() // 60))
    spaet = verzug if verzug > STEMPEL_TOLERANZ else 0
    grund = ""
    if verzug > STEMPEL_MAX_TAGE * 1440:
        grund = f"ist älter als {STEMPEL_MAX_TAGE} Tage"
    elif monat_abgerechnet(con, m["id"], datum[:7]):
        grund = f"fällt in den schon abgerechneten Monat {datum[5:7]}/{datum[:4]}"
    if grund and aktion in ("start", "pause", "ende"):
        # Nicht übernehmen, aber als erledigt beantworten: Das Handy soll die Buchung aus seiner Warteschlange nehmen und die folgenden senden.
        erg = {"ok": False, "abgelehnt": True, "id": None,
               "hinweise": [f"Die Stempelung vom {de_datum(datum)}, {uhr} Uhr {grund} und wurde nicht übernommen. Bitte die Zeit im Büro nachtragen lassen."]}
        if cid:
            con.execute("INSERT INTO stempel_ereignisse VALUES (?,?,?,?,?,?,?)", (cid, m["id"], zeit, aktion, json.dumps(ev, ensure_ascii=False), json.dumps(erg), jetzt()))
        return erg
    hinweise = []
    offen = con.execute("SELECT * FROM zeiten INDEXED BY zeiten_offen WHERE mitarbeiter_id=? AND ende IS NULL ORDER BY datum DESC, beginn DESC", (m["id"],)).fetchall()
    for o in offen:
        if o["datum"] == datum:
            if minuten(uhr) <= minuten(o["beginn"]):
                if minuten(uhr) == minuten(o["beginn"]):
                    con.execute("DELETE FROM zeiten WHERE id=?", (o["id"],))  # in derselben Minute umentschieden
                    stunden_abgleichen(con, o["id"])
                    continue
                uhr_ende = o["beginn"]
                hinweise.append("Zeitpunkt lag vor dem Beginn – Abschnitt mit 0 Minuten geschlossen.")
            else:
                uhr_ende = uhr
            con.execute("UPDATE zeiten SET ende=?, geaendert=?, eingang=?, spaet=MAX(IFNULL(spaet,0), ?) WHERE id=?", (uhr_ende, jetzt(), jetzt(), spaet, o["id"]))
        else:
            # vergessener Feierabend an einem früheren Tag: offen lassen wäre falsch, Ende = Beginn + Hinweis
            con.execute("UPDATE zeiten SET ende=beginn, notiz=TRIM(notiz || ' Feierabend nicht gestempelt – bitte korrigieren'), geaendert=? WHERE id=?",
                        (jetzt(), o["id"]))
            hinweise.append(f"Am {de_datum(o['datum'])} fehlte der Feierabend – bitte im Büro korrigieren lassen.")
        stunden_abgleichen(con, o["id"])
    neu_id = None
    if aktion == "start":
        aid = int(ev["auftrag_id"]) if ev.get("auftrag_id") else None
        if aid and not con.execute("SELECT 1 FROM auftraege WHERE id=?", (aid,)).fetchone():
            aid = None
        titel = 0
        if aid and ev.get("titel") and HILFE.get("titel_buchbar"):
            try:
                titel = HILFE["titel_buchbar"](con, aid, ev.get("titel"))
            except Exception as f:  # noqa: BLE001  abgeschlossener Titel: trotzdem stempeln, ohne Titel
                hinweise.append(str(f) + " Die Zeit läuft ohne Titel.")
        neu_id = con.execute("INSERT INTO zeiten (mitarbeiter_id, datum, beginn, ende, auftrag_id, kst, taetigkeit, titel, quelle, angelegt, geaendert, eingang, spaet) "
                             "VALUES (?,?,?,NULL,?,?,?,?,?,?,?,?,?)",
                             (m["id"], datum, uhr, aid, ev.get("kst") or "", ev.get("taetigkeit") or "", titel,
                              "stempel", jetzt(), jetzt(), jetzt(), spaet)).lastrowid
    elif aktion not in ("pause", "ende"):
        raise Fehler("Unbekannte Stempel-Aktion.")
    erg = {"ok": True, "id": neu_id, "hinweise": hinweise}
    if cid:
        con.execute("INSERT INTO stempel_ereignisse VALUES (?,?,?,?,?,?,?)",
                    (cid, m["id"], zeit, aktion, json.dumps(ev, ensure_ascii=False), json.dumps(erg), jetzt()))
    return erg


def vergessen_nachtragen(con, m, d):
    """Feierabend eines früheren Tages nachtragen."""
    o = con.execute("SELECT * FROM zeiten WHERE id=? AND mitarbeiter_id=? AND ende IS NULL", (int(d.get("id") or 0), m["id"])).fetchone()
    if not o:
        raise Fehler("Kein offener Eintrag gefunden.")
    ende = uhrzeit_lesen(d.get("ende"))
    if not ende or minuten(ende) <= minuten(o["beginn"]):
        raise Fehler(f"Bitte eine Uhrzeit nach {o['beginn']} eingeben.")
    con.execute("UPDATE zeiten SET ende=?, notiz=TRIM(notiz || ' Feierabend nachgetragen'), geaendert=? WHERE id=?", (ende, jetzt(), o["id"]))
    stunden_abgleichen(con, o["id"])


# ---------------------------------------------------------------- API
def api(con, methode, teile, q, daten):
    res = teile[0]
    d = daten or {}
    rid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
    wer = (benutzer.aktuell() or {"login": "intern"})["login"]

    if res == "mitarbeiter" and teile[1:] == ["arbeitszeit"] and methode == "GET":
        j = int(q.get("jahr") or date.today().year)
        o = ostern(j)
        kat = lambda liste, wahl: [{"k": k, "name": n, "vorgabe": std, "an": wahl.get(k, std), "hinweis": hin, "datum": fn(j, o).isoformat()}
                                   for k, n, fn, std, hin in liste]
        return {"jahr": j, "feiertage": kat(FEIERTAGE_KATALOG, TAGE_CFG["feiertage"]), "frei": kat(FREI_KATALOG, TAGE_CFG["frei"]),
                "vorschau": sorted([{"datum": d_, "name": n, "art": "feiertag"} for d_, n in feiertage(j).items()]
                                   + [{"datum": d_, "name": n, "art": "frei"} for d_, n in freie_tage(j).items()], key=lambda x: x["datum"]),
                "zuschlag_arten": [{"k": k, "name": n, "vorgabe": std} for k, n, std in ZUSCHLAG_ARTEN]}

    if res == "stempel":
        m = eigener_mitarbeiter(con)
        if methode == "GET" and len(teile) == 1:
            st = stempel_status(con, m)
            if q.get("mit") == "listen":
                st["auftraege"] = offene_auftraege(con)
                st["taetigkeiten"] = taetigkeiten(con)
            return st
        if methode == "POST" and len(teile) == 1:
            evs = d.get("ereignisse") or [d]
            ergebnisse = [stempeln(con, m, ev) for ev in sorted(evs, key=lambda e: e.get("zeit") or "")]
            return {"ergebnisse": ergebnisse, "status": stempel_status(con, m)}
        if methode == "POST" and teile[1:] == ["vergessen"]:
            vergessen_nachtragen(con, m, d)
            return stempel_status(con, m)
        if methode == "GET" and teile[1:] == ["monat"]:
            return monat_daten(con, m["id"], q.get("monat") or date.today().isoformat()[:7])
        if methode == "GET" and teile[1:] == ["zeiten"]:
            return zeiten_liste(con, m["id"], q.get("von"), q.get("bis"))
        if methode == "POST" and teile[1:] == ["nachtrag"]:
            grenze = (date.today() - timedelta(14)).isoformat()
            if (d.get("datum") or "") < grenze or (d.get("datum") or "") > date.today().isoformat():
                raise Fehler("Nachtragen geht für die letzten 14 Tage. Ältere Korrekturen bitte im Büro.")
            if monat_abgerechnet(con, m["id"], (d.get("datum") or "")[:7]):
                raise Fehler("Dieser Monat ist schon abgerechnet. Bitte die Zeit im Büro nachtragen lassen.")
            zid = zeit_speichern(con, {**d, "mitarbeiter_id": m["id"], "quelle": "nachtrag"}, None, wer)
            return {"id": zid}
        if methode == "DELETE" and len(teile) == 3 and teile[1] == "zeiten":
            z = con.execute("SELECT * FROM zeiten WHERE id=? AND mitarbeiter_id=?", (int(teile[2]), m["id"])).fetchone()
            if not z or z["quelle"] != "nachtrag" or z["datum"] < (date.today() - timedelta(14)).isoformat():
                raise Fehler("Nur eigene Nachträge der letzten 14 Tage können gelöscht werden.")
            zeit_loeschen(con, z["id"])
            return {"ok": True}
        if methode == "GET" and teile[1:] == ["abwesenheiten"]:
            return [dict(a, art_name=ABWESENHEIT.get(a["art"], (a["art"],))[0]) for a in
                    abwesenheiten_im(con, m["id"], f"{date.today().year - 1}-01-01", f"{date.today().year + 1}-12-31", False)]
        if methode == "POST" and teile[1:] == ["urlaub"]:
            if not d.get("von") or not d.get("bis") or d["bis"] < d["von"]:
                raise Fehler("Bitte Von und Bis angeben.")
            con.execute("INSERT INTO abwesenheiten (mitarbeiter_id, art, von, bis, halbtag, status, notiz, angelegt) VALUES (?,?,?,?,?,?,?,?)",
                        (m["id"], "urlaub", d["von"], d["bis"], 1 if d.get("halbtag") else 0, "beantragt", d.get("notiz") or "", jetzt()))
            return {"ok": True}
        raise Fehler("Unbekannte Anfrage", 404)

    darf_schreiben = benutzer.darf("personal", 2)
    if methode != "GET" and not darf_schreiben:
        raise Fehler("Dafür fehlt die Berechtigung.", 403)

    if res == "mitarbeiter":
        if methode == "GET" and teile[1:] == ["meta"]:
            return {"lohnarten": LOHNARTEN, "abwesenheit": {k: v[0] for k, v in ABWESENHEIT.items()}, "taetigkeiten": taetigkeiten(con),
                    "auftraege": offene_auftraege(con), "kst_namen": KST_NAMEN, "wochentage": WOCHENTAG,
                    "kassen": [dict(r) for r in con.execute("SELECT id, kurzname, gruppe FROM lieferanten WHERE aktiv=1 AND gruppe<>'Mitarbeiter' ORDER BY kurzname")],
                    "naechste_nr": (con.execute("SELECT MAX(nummer) FROM mitarbeiter").fetchone()[0] or 4999) + 1}
        if methode == "GET" and rid is None:
            return mitarbeiter_liste(con, q)
        if methode == "GET" and rid and len(teile) == 2:
            m = laden(con, rid)
            m["konten"] = konten(con, rid, date.today())
            return m
        if methode == "POST" and rid is None:
            return mitarbeiter_speichern(con, None, d)
        if methode == "PUT" and rid:
            laden(con, rid)
            return mitarbeiter_speichern(con, rid, d)
        if methode == "DELETE" and rid:
            if con.execute("SELECT 1 FROM zeiten WHERE mitarbeiter_id=? UNION SELECT 1 FROM lohn WHERE mitarbeiter_id=?", (rid, rid)).fetchone():
                raise Fehler("Zu diesem Mitarbeiter gibt es Zeiten oder Lohndaten. Bitte stattdessen ein Austrittsdatum eintragen und auf inaktiv setzen.")
            if con.execute("SELECT 1 FROM as_teilnehmer WHERE mitarbeiter_id=? AND signatur_id IS NOT NULL", (rid,)).fetchone():
                raise Fehler("Dieser Mitarbeiter hat Unterweisungen unterschrieben; die Nachweise bleiben erhalten. Bitte stattdessen ein "
                             "Austrittsdatum eintragen und auf inaktiv setzen.")
            m = laden(con, rid)
            # Nachweise (Ersthelfer usw.) behalten den Namen, offene Teilnahmen entfallen
            con.execute("UPDATE as_qualifikationen SET name=?, mitarbeiter_id=NULL WHERE mitarbeiter_id=?", (name(m), rid))
            con.execute("DELETE FROM as_teilnehmer WHERE mitarbeiter_id=? AND signatur_id IS NULL", (rid,))
            con.execute("UPDATE benutzer SET mitarbeiter_id=NULL WHERE mitarbeiter_id=?", (rid,))
            con.execute("DELETE FROM abwesenheiten WHERE mitarbeiter_id=?", (rid,))
            con.execute("DELETE FROM kontobuchungen WHERE mitarbeiter_id=?", (rid,))
            con.execute("DELETE FROM mitarbeiter WHERE id=?", (rid,))
            return {"ok": True}

    if res == "zeiten":
        if methode == "GET":
            mid = int(q.get("mitarbeiter") or 0)
            von = q.get("von") or date.today().isoformat()
            bis = q.get("bis") or von
            if mid:
                return zeiten_liste(con, mid, von, bis)
            aus = []
            for m in con.execute("SELECT id FROM mitarbeiter WHERE aktiv=1"):
                aus += [dict(z, mitarbeiter_id=m["id"]) for z in zeiten_liste(con, m["id"], von, bis)]
            return aus
        if methode == "POST" and rid is None:
            return {"id": zeit_speichern(con, d, None, wer)}
        if methode == "PUT" and rid:
            return {"id": zeit_speichern(con, d, rid, wer)}
        if methode == "DELETE" and rid:
            z = con.execute("SELECT mitarbeiter_id, datum FROM zeiten WHERE id=?", (rid,)).fetchone()
            if z and monat_abgerechnet(con, z["mitarbeiter_id"], z["datum"][:7]):
                kern.rueckfrage(f"lohnmonat-{z['mitarbeiter_id']}-{z['datum'][:7]}", f"Für {z['datum'][5:7]}/{z['datum'][:4]} sind die Lohnzahlungen dieses Mitarbeiters schon angelegt.\n\n"
                                "Das Löschen ändert die Stunden, nach denen abgerechnet wurde. Bitte danach den Lohn prüfen.", "Trotzdem löschen")
            zeit_loeschen(con, rid)
            return {"ok": True}

    if res == "abwesenheiten":
        if methode == "GET":
            von = q.get("von") or f"{date.today().year}-01-01"
            bis = q.get("bis") or f"{date.today().year}-12-31"
            sql = ("SELECT a.*, m.vorname, m.nachname, m.kuerzel FROM abwesenheiten a JOIN mitarbeiter m ON m.id=a.mitarbeiter_id "
                   "WHERE a.bis>=? AND a.von<=?")
            p = [von, bis]
            if q.get("mitarbeiter"):
                sql += " AND a.mitarbeiter_id=?"
                p.append(int(q["mitarbeiter"]))
            if q.get("status"):
                sql += " AND a.status=?"
                p.append(q["status"])
            aus = []
            for a in con.execute(sql + " ORDER BY a.von", p):
                x = dict(a, art_name=ABWESENHEIT.get(a["art"], (a["art"],))[0])
                m = con.execute("SELECT * FROM mitarbeiter WHERE id=?", (a["mitarbeiter_id"],)).fetchone()
                x["arbeitstage"] = sum(1 for t in tage(con, m, a["von"], a["bis"]) if t["soll"] or t["abw_std"]) * (0.5 if a["halbtag"] else 1)
                aus.append(x)
            return aus
        werte = {}
        if methode in ("POST", "PUT"):
            for k in ("mitarbeiter_id", "art", "von", "bis", "halbtag", "status", "notiz"):
                if k in d:
                    werte[k] = d[k]
            if "art" in werte and werte["art"] not in ABWESENHEIT:
                raise Fehler("Unbekannte Abwesenheitsart.")
            if "halbtag" in werte:
                werte["halbtag"] = 1 if werte["halbtag"] else 0
        if methode == "POST" and rid is None:
            if not werte.get("mitarbeiter_id") or not werte.get("von"):
                raise Fehler("Bitte Mitarbeiter und Datum angeben.")
            werte.setdefault("bis", werte["von"])
            if werte["bis"] < werte["von"]:
                raise Fehler("Bis liegt vor Von.")
            werte.setdefault("status", "genehmigt")
            werte["angelegt"] = jetzt()
            return {"id": con.execute(f"INSERT INTO abwesenheiten ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})",
                                      list(werte.values())).lastrowid}
        if methode == "PUT" and rid:
            if werte:
                con.execute(f"UPDATE abwesenheiten SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [rid])
            return {"ok": True}
        if methode == "DELETE" and rid:
            con.execute("DELETE FROM abwesenheiten WHERE id=?", (rid,))
            return {"ok": True}

    if res == "konten":
        if methode == "GET" and rid:
            k = konten(con, rid, date.fromisoformat(q["stichtag"]) if q.get("stichtag") else date.today())
            k["buchungen"] = [dict(r) for r in con.execute("SELECT * FROM kontobuchungen WHERE mitarbeiter_id=? ORDER BY datum DESC", (rid,))]
            return k
        if methode == "POST" and rid:
            if d.get("konto") not in ("ueberstunden", "urlaub"):
                raise Fehler("Bitte Konto wählen.")
            wert = zahl(d.get("wert"))
            if not wert:
                raise Fehler("Bitte einen Wert eingeben (negativ = abziehen).")
            con.execute("INSERT INTO kontobuchungen (mitarbeiter_id, datum, konto, wert, text, angelegt) VALUES (?,?,?,?,?,?)",
                        (rid, d.get("datum") or date.today().isoformat(), d["konto"], wert, d.get("text") or "", jetzt()))
            return {"ok": True}
        if methode == "DELETE" and len(teile) == 3 and teile[1] == "buchung":
            con.execute("DELETE FROM kontobuchungen WHERE id=?", (int(teile[2]),))
            return {"ok": True}

    if res == "monatsbeleg" and methode == "GET" and rid:
        return monat_daten(con, rid, q.get("monat") or date.today().isoformat()[:7])

    if res == "lohn":
        monat = q.get("monat") or (teile[2] if len(teile) > 2 else "") or date.today().isoformat()[:7]
        if methode == "POST" and teile[1:] == ["zahlungen"]:
            monat = d.get("monat") or monat
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", str(monat)):
            raise Fehler("Bitte einen gültigen Monat angeben (JJJJ-MM).")
        if methode == "GET":
            return lohn_liste(con, monat)
        if methode == "PUT" and rid:
            return dict(lohn_speichern(con, rid, monat, d))
        if methode == "POST" and teile[1:] == ["zahlungen"]:
            return lohn_zahlungen(con, monat, d)
    raise Fehler("Unbekannte Anfrage", 404)
