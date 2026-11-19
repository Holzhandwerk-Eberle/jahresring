"""Materialstamm und Lager: Holzwerkstoffe, Massivholz, Oberflächenstoffe, Chemisch-technische Produkte,
Beschläge, Beschlägesets, Artikel, Lager- und Auftragsbuchungen."""
import kern
from kern import kfm
import json
import sqlite3
from datetime import date, datetime

KATEGORIEN = {
    "holzwerkstoffe": "Holzwerkstoffe",
    "massivholz": "Massivholz",
    "beschichtung": "Oberflächenstoffe",
    "chemie": "Chemisch-technische Produkte",
    "beschlaege": "Beschläge",
    "artikel": "Artikel",
}
PRAEFIX = {"holzwerkstoffe": "H", "massivholz": "M", "beschichtung": "O", "chemie": "C", "beschlaege": "B", "artikel": "A"}
STANDARD_GRUPPEN = {
    "holzwerkstoffe": ["Platten", "Kanten", "Furnier", "Leimholz", "Sonstiges"],
    "massivholz": ["Schnittholz", "Kantholz", "Leisten", "Bohlen", "Sonstiges"],
    "beschichtung": ["Lack", "Öl", "Wachs", "Beize", "Grundierung", "Sonstiges"],
    "chemie": ["Leim", "Kleber", "Dichtstoff", "Schleifmittel", "Reiniger", "Verdünnung", "Sonstiges"],
    "beschlaege": ["Scharniere", "Auszüge", "Griffe", "Verbinder", "Bodenträger", "Sonstiges"],
    "artikel": ["keine"],
}
STANDARD_EINHEIT = {"holzwerkstoffe": "m²", "massivholz": "m³", "beschichtung": "m²", "chemie": "Stk.", "beschlaege": "Stk.", "artikel": "Stk."}
EINHEITEN = ["(keine)", "lfm.", "m²", "m³", "Stk.", "Std.", "Pauschale", "Paar", "Satz", "Garnitur", "Dose", "Rolle", "Tube",
             "Packung", "Liter", "kg"]
KOSTENARTEN = {"werkstoffe": "Werkstoffe", "beschlaege": "Beschläge", "oberflaeche": "Oberfläche", "kleinmaterial": "Kleinmaterial",
               "fremdleistungen": "Fremdleistungen", "zukauf": "Zukauf (Handelsware)", "sonder_fertigung": "Soko Fertigung", "sonder_vertrieb": "Soko Vertrieb"}
KAT_KOSTENART = {"holzwerkstoffe": "werkstoffe", "massivholz": "werkstoffe", "beschichtung": "oberflaeche", "chemie": "kleinmaterial",
                 "beschlaege": "beschlaege", "artikel": "fremdleistungen"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS material (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kategorie TEXT NOT NULL,
    nummer TEXT UNIQUE NOT NULL,
    bezeichnung TEXT DEFAULT '',
    gruppe TEXT DEFAULT '',
    dicke REAL DEFAULT 0,
    ek_preis REAL DEFAULT 0,
    einheit TEXT DEFAULT 'Stk.',
    preis_vom TEXT DEFAULT '',
    vk_preis REAL DEFAULT 0, aufschlag REAL DEFAULT 0,
    vk_preis2 REAL DEFAULT 0, aufschlag2 REAL DEFAULT 0,
    vk_preis3 REAL DEFAULT 0, aufschlag3 REAL DEFAULT 0,
    verschnitt REAL DEFAULT 0,
    lieferant_id INTEGER,
    bestellnr TEXT DEFAULT '',
    bemerkungen TEXT DEFAULT '',
    lager INTEGER DEFAULT 0,
    lagerort TEXT DEFAULT '',
    mindestbestand REAL DEFAULT 0,
    bestand REAL DEFAULT 0,
    lagerpreis REAL DEFAULT 0,
    aktiv INTEGER DEFAULT 1,
    angelegt TEXT, geaendert TEXT
);
CREATE TABLE IF NOT EXISTS material_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer TEXT UNIQUE NOT NULL,
    bezeichnung TEXT DEFAULT '',
    bemerkungen TEXT DEFAULT '',
    angelegt TEXT, geaendert TEXT
);
CREATE TABLE IF NOT EXISTS material_set_pos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    set_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    menge REAL DEFAULT 1,
    sort INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS lagerbewegungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datum TEXT, material_id INTEGER NOT NULL,
    menge REAL, preis REAL DEFAULT 0, art TEXT,
    auftrag_id INTEGER, auftragskosten_id INTEGER,
    lagerort TEXT DEFAULT '', bemerkung TEXT DEFAULT '', angelegt TEXT
);
CREATE TABLE IF NOT EXISTS auftragskosten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datum TEXT, auftrag_id INTEGER NOT NULL, titel INTEGER DEFAULT 0,
    kostenart TEXT, material_id INTEGER, bezeichnung TEXT DEFAULT '',
    menge REAL DEFAULT 0, einheit TEXT DEFAULT '', einzelpreis REAL DEFAULT 0, betrag REAL DEFAULT 0,
    lager_abgang INTEGER DEFAULT 0, bemerkung TEXT DEFAULT '', angelegt TEXT
);
CREATE INDEX IF NOT EXISTS ix_material_kat ON material(kategorie);
CREATE INDEX IF NOT EXISTS ix_lager_mat ON lagerbewegungen(material_id);
CREATE INDEX IF NOT EXISTS ix_ak_auftrag ON auftragskosten(auftrag_id);
"""

FELDER = ["nummer", "bezeichnung", "gruppe", "dicke", "ek_preis", "einheit", "preis_vom", "vk_preis", "aufschlag", "vk_preis2",
          "aufschlag2", "vk_preis3", "aufschlag3", "verschnitt", "lieferant_id", "bestellnr", "ean", "cad", "bemerkungen", "lager", "lagerort",
          "mindestbestand", "aktiv", "kategorie", "plattenlaenge", "plattenbreite", "umrechnung"]
ZAHLEN = {"plattenlaenge", "plattenbreite", "dicke", "ek_preis", "vk_preis", "aufschlag", "vk_preis2", "aufschlag2", "vk_preis3", "aufschlag3", "verschnitt",
          "mindestbestand", "umrechnung"}


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def f(x):
    if isinstance(x, (int, float)):
        return float(x)
    t = str(x or "").strip().replace(" ", "").replace("€", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t) if t else 0.0
    except ValueError:
        return 0.0


def schema(con):
    con.executescript(SCHEMA)


def zeilen(rows):
    return [dict(r) for r in rows]


def naechste_nummer(con, kat):
    p = PRAEFIX.get(kat, "X")
    n = 1
    for r in con.execute("SELECT nummer FROM material WHERE nummer LIKE ?", (p + "%",)):
        rest = r["nummer"][len(p):]
        if rest.isdigit():
            n = max(n, int(rest) + 1)
    return f"{p}{n:04d}"


def werte_aus(d):
    w = {}
    for k in FELDER:
        if k in d:
            v = d[k]
            if k in ZAHLEN:
                v = round(f(v), 4)
            elif k in ("lager", "aktiv"):
                v = 1 if v in (1, True, "1", "true", "ja") else 0
            elif k == "lieferant_id":
                v = int(v) if str(v or "").strip().isdigit() else None
            elif v is None:
                v = ""
            w[k] = v.strip() if isinstance(v, str) else v
    return w


# Preis für Kalkulation und Auftragskosten bei Lagerartikeln: "mittel" = gleitender Durchschnitt, "hoechst" = höchster
# Einkaufspreis (EK im Stamm, Lagerpreis oder Zugänge der letzten 12 Monate). Wird von app.py aus den Einstellungen gesetzt.
PREISREGEL = {"methode": lambda con: "mittel"}
_HOECHST_SQL = ("(SELECT MAX(b.preis) FROM lagerbewegungen b WHERE b.material_id=m.id AND b.art='zugang' "
                "AND b.datum >= date('now','-365 day')) AS hoechst_zugang")


def _kalkpreis(m, methode):
    ek, lp = f(m.get("ek_preis")), f(m.get("lagerpreis"))
    if not m.get("lager"):
        return ek
    if methode == "hoechst":
        return max(ek, lp, f(m.get("hoechst_zugang")))
    return lp or ek


def mit_kalkpreis(con, m):
    m["kalkpreis"] = round(_kalkpreis(m, PREISREGEL["methode"](con)), 4)
    return m


def laden(con, mid):
    r = con.execute("SELECT m.*, l.kurzname AS lieferant, l.nummer AS lieferantennr, " + _HOECHST_SQL + " FROM material m "
                    "LEFT JOIN lieferanten l ON l.id=m.lieferant_id WHERE m.id=?", (mid,)).fetchone()
    if not r:
        raise Fehler("Material nicht gefunden", 404)
    return mit_kalkpreis(con, dict(r))


def liste(con, q):
    sql = ("SELECT m.*, l.kurzname AS lieferant, " + _HOECHST_SQL + " FROM material m LEFT JOIN lieferanten l ON l.id=m.lieferant_id WHERE 1=1")
    par = []
    if q.get("kat"):
        sql += " AND m.kategorie=?"
        par.append(q["kat"])
    if q.get("gruppe"):
        sql += " AND m.gruppe=?"
        par.append(q["gruppe"])
    status = q.get("status", "aktiv")
    if status == "aktiv":
        sql += " AND m.aktiv=1"
    elif status == "inaktiv":
        sql += " AND m.aktiv=0"
    if q.get("lager") == "1":
        sql += " AND m.lager=1"
    if q.get("unter_mindest") == "1":
        sql += " AND m.lager=1 AND m.bestand < m.mindestbestand"
    if q.get("q"):
        for wort in q["q"].split():
            sql += " AND (m.nummer LIKE ? OR m.bezeichnung LIKE ? OR m.bestellnr LIKE ? OR IFNULL(m.cad,'') LIKE ? OR IFNULL(l.kurzname,'') LIKE ?)"
            par += [f"%{wort}%"] * 5
    sql += " ORDER BY m.nummer COLLATE NOCASE LIMIT 2000"
    methode = PREISREGEL["methode"](con)
    return [{**z, "kalkpreis": round(_kalkpreis(z, methode), 4)} for z in zeilen(con.execute(sql, par))]


def anlegen(con, d):
    kat = d.get("kategorie")
    if kat not in KATEGORIEN:
        raise Fehler("Unbekannte Materialart.")
    w = werte_aus(d)
    w["kategorie"] = kat
    w["nummer"] = (w.get("nummer") or "").strip() or naechste_nummer(con, kat)
    if con.execute("SELECT 1 FROM material WHERE nummer=?", (w["nummer"],)).fetchone():
        raise Fehler(f"Die Nummer {w['nummer']} ist schon vergeben.")
    w.setdefault("einheit", STANDARD_EINHEIT.get(kat, "Stk."))
    w.setdefault("preis_vom", date.today().isoformat())
    w["angelegt"] = w["geaendert"] = jetzt()
    cur = con.execute(f"INSERT INTO material ({','.join(w)}) VALUES ({','.join('?' * len(w))})", list(w.values()))
    return laden(con, cur.lastrowid)


def aendern(con, mid, d):
    alt = laden(con, mid)
    w = werte_aus(d)
    w.pop("kategorie", None) if d.get("kategorie") not in KATEGORIEN else None
    # Die Nummer ist der feste Schlüssel des Werkstoffs (Stücklisten, CAD-Import, Lagerbuchungen): nach dem Anlegen nicht änderbar
    if "nummer" in w:
        if (w["nummer"] or "") != (alt["nummer"] or ""):
            raise Fehler("Die Nummer eines Werkstoffs kann nach dem Anlegen nicht mehr geändert werden; die Bezeichnung schon.")
        w.pop("nummer")
    if "ek_preis" in w and abs(w["ek_preis"] - (alt["ek_preis"] or 0)) > 1e-9 and "preis_vom" not in d:
        w["preis_vom"] = date.today().isoformat()
    # VK-Preis aus Aufschlag oder Aufschlag aus VK-Preis nachführen
    ek = w.get("ek_preis", alt["ek_preis"]) or 0
    for i in ("", "2", "3"):
        if f"aufschlag{i}" in d and f"vk_preis{i}" not in d:
            w[f"vk_preis{i}"] = kfm(ek * (1 + w[f"aufschlag{i}"] / 100))
        elif f"vk_preis{i}" in d and f"aufschlag{i}" not in d:
            w[f"aufschlag{i}"] = kfm((w[f"vk_preis{i}"] / ek - 1) * 100) if ek else 0
        elif "ek_preis" in d and f"vk_preis{i}" not in d and (alt[f"aufschlag{i}"] or 0):
            w[f"vk_preis{i}"] = kfm(ek * (1 + alt[f"aufschlag{i}"] / 100))
    if not w:
        return alt
    w["geaendert"] = jetzt()
    con.execute(f"UPDATE material SET {','.join(k + '=?' for k in w)} WHERE id=?", list(w.values()) + [mid])
    return laden(con, mid)


def kopieren(con, mid):
    m = laden(con, mid)
    d = {k: m[k] for k in FELDER if k in m}
    d["nummer"] = ""
    d["bezeichnung"] = (m["bezeichnung"] or "") + " (Kopie)"
    neu = anlegen(con, d)
    return neu


def loeschen(con, mid):
    laden(con, mid)
    benutzt = con.execute("SELECT (SELECT COUNT(*) FROM lagerbewegungen WHERE material_id=?) + "
                          "(SELECT COUNT(*) FROM auftragskosten WHERE material_id=?) + "
                          "(SELECT COUNT(*) FROM material_set_pos WHERE material_id=?)", (mid, mid, mid)).fetchone()[0]
    # Gefahrstoffangaben, Datenblätter und Betriebsanweisungen sind Arbeitsschutz-Nachweise: Material bleibt dann als inaktiv erhalten
    try:
        benutzt += con.execute("SELECT (SELECT COUNT(*) FROM as_dateien WHERE material_id=?) + (SELECT COUNT(*) FROM as_ba WHERE material_id=?) + "
                               "(SELECT COUNT(*) FROM as_gefahrstoffe WHERE material_id=? AND gefahrstoff=1)", (mid, mid, mid)).fetchone()[0]
    except sqlite3.OperationalError:
        pass
    if benutzt:
        con.execute("UPDATE material SET aktiv=0, geaendert=? WHERE id=?", (jetzt(), mid))
        return {"ok": True, "inaktiv": True}
    con.execute("DELETE FROM material WHERE id=?", (mid,))
    return {"ok": True}


# ---------------------------------------------------------------- Lager
BESTAND_GEAENDERT = []      # Rückrufe (con, material_id), z. B. Stückzahl im Plattenlager des Zuschnitts nachführen


def _bestand_geaendert(con, mid):
    for fn in BESTAND_GEAENDERT:
        fn(con, mid)


def lager_buchen(con, d, auftrag_id=None, ak_id=None):
    mid = int(d.get("material_id") or 0)
    m = laden(con, mid)
    menge = f(d.get("menge"))
    art = d.get("art") or "zugang"
    if art not in ("zugang", "abgang", "auftrag", "inventur"):
        raise Fehler("Unbekannte Buchungsart.")
    if art == "inventur":
        # gezählter Bestand: 0 ist eine gültige Zählung, ein leeres Feld oder eine negative Zahl nicht
        if d.get("menge") in (None, "") or menge < 0:
            raise Fehler("Bitte den gezählten Bestand eingeben (0 oder mehr).")
    elif not menge:
        raise Fehler("Bitte eine Menge eingeben.")
    elif art in ("zugang", "abgang") and menge < 0:
        raise Fehler("Bitte eine positive Menge eingeben – für eine Entnahme „Abgang“ wählen, für eine Korrektur „Inventur“.")
    preis = f(d.get("preis")) if d.get("preis") not in (None, "") else (m["lagerpreis"] or m["ek_preis"] or 0)
    bestand_alt = m["bestand"] or 0
    if art == "inventur":
        delta = menge - bestand_alt
    elif art == "zugang":
        delta = abs(menge)
    elif art == "auftrag":
        delta = -menge      # negative Menge in den Auftragskosten = Rückgabe ans Lager (passt zum Löschen der Buchung)
    else:
        delta = -abs(menge)
    neu_bestand = round(bestand_alt + delta, 4)
    if delta < 0 and neu_bestand < -1e-9 and art in ("abgang", "auftrag"):
        # Entnahme über den Bestand hinaus erst nach Rückfrage (nur im Büro-Programm; Scan und Stempeluhr buchen ohne)
        kern.rueckfrage("lager_negativ", f"Im Lager sind nur {kern.de(bestand_alt, 2)} {m['einheit'] or ''} von {m['nummer']} {(m['bezeichnung'] or '').splitlines()[0]}.\n\n"
                        f"Nach der Entnahme von {kern.de(-delta, 2)} {m['einheit'] or ''} stünde der Bestand bei {kern.de(neu_bestand, 2)}. "
                        "Stimmt der Bestand nicht, hilft eine Inventur.", "Trotzdem entnehmen")
    lagerpreis = m["lagerpreis"] or 0
    if art == "inventur" and not lagerpreis and neu_bestand > 0:
        # Bestand erstmals per Inventur erfasst: mit dem angegebenen Preis, sonst dem Einkaufspreis bewerten (sonst wäre der Lagerwert 0 €)
        lagerpreis = round(f(d.get("preis")) if d.get("preis") not in (None, "") else (m["ek_preis"] or 0), 4)
    if art == "zugang":
        # gleitender Durchschnittspreis
        basis = max(bestand_alt, 0)
        lagerpreis = round((basis * lagerpreis + delta * preis) / (basis + delta), 4) if basis + delta else preis
    con.execute("INSERT INTO lagerbewegungen (datum, material_id, menge, preis, art, auftrag_id, auftragskosten_id, lagerort, bemerkung, angelegt) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (d.get("datum") or date.today().isoformat(), mid, round(delta, 4), round(preis, 4), art, auftrag_id, ak_id,
                 d.get("lagerort") or m["lagerort"] or "", d.get("bemerkung") or "", jetzt()))
    con.execute("UPDATE material SET bestand=?, lagerpreis=?, lager=1, geaendert=? WHERE id=?", (neu_bestand, lagerpreis, jetzt(), mid))
    _bestand_geaendert(con, mid)
    return laden(con, mid)


def bewegungen(con, mid=None, limit=300):
    sql = ("SELECT b.*, m.nummer, m.bezeichnung, m.einheit, a.nummer AS auftrag FROM lagerbewegungen b "
           "JOIN material m ON m.id=b.material_id LEFT JOIN auftraege a ON a.id=b.auftrag_id")
    par = []
    if mid:
        sql += " WHERE b.material_id=?"
        par.append(mid)
    sql += " ORDER BY b.datum DESC, b.id DESC LIMIT ?"
    return zeilen(con.execute(sql, par + [limit]))


# ---------------------------------------------------------------- Auftragskosten
def ak_buchen(con, d):
    aid = int(d.get("auftrag_id") or 0)
    if not con.execute("SELECT 1 FROM auftraege WHERE id=?", (aid,)).fetchone():
        raise Fehler("Bitte einen Auftrag wählen.")
    art = d.get("kostenart") or "werkstoffe"
    if art not in KOSTENARTEN:
        raise Fehler("Unbekannte Kostenart.")
    m = laden(con, int(d["material_id"])) if str(d.get("material_id") or "").isdigit() else None
    menge = f(d.get("menge"))
    if d.get("betrag") not in (None, "") and not menge:
        menge = 1
    if not menge:
        raise Fehler("Bitte eine Menge eingeben.")
    lager = bool(d.get("lager_abgang")) and m is not None
    ep = f(d.get("einzelpreis")) if d.get("einzelpreis") not in (None, "") else (
        m["kalkpreis"] if lager and m else (m["ek_preis"] if m else 0))
    betrag = kfm(f(d.get("betrag"))) if d.get("betrag") not in (None, "") else kfm(menge * ep)
    cur = con.execute("INSERT INTO auftragskosten (datum, auftrag_id, titel, kostenart, material_id, bezeichnung, menge, einheit, einzelpreis, "
                      "betrag, lager_abgang, bemerkung, angelegt) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (d.get("datum") or date.today().isoformat(), aid, int(d.get("titel") or 0), art, m["id"] if m else None,
                       d.get("bezeichnung") or (m["bezeichnung"].split("\n")[0] if m else ""), menge,
                       d.get("einheit") or (m["einheit"] if m else ""), round(ep, 4), betrag, 1 if lager else 0,
                       d.get("bemerkung") or "", jetzt()))
    if lager:
        lager_buchen(con, {"material_id": m["id"], "menge": menge, "art": "auftrag", "preis": ep, "datum": d.get("datum"),
                           "bemerkung": d.get("bemerkung") or ""}, auftrag_id=aid, ak_id=cur.lastrowid)
    return dict(con.execute("SELECT * FROM auftragskosten WHERE id=?", (cur.lastrowid,)).fetchone())


def ak_loeschen(con, kid):
    r = con.execute("SELECT * FROM auftragskosten WHERE id=?", (kid,)).fetchone()
    if not r:
        raise Fehler("Buchung nicht gefunden", 404)
    hinweis = ""
    if r["lager_abgang"] and r["material_id"]:
        # Lagerabgang mit einer Gegenbuchung zurücknehmen: die ursprüngliche Bewegung bleibt stehen, damit Lagerjournal
        # und Bestand zu früheren Stichtagen unverändert bleiben. Wurde das Material danach inventiert, enthält der
        # gezählte Bestand die Korrektur bereits – dann keine Rückbuchung, sonst stimmte der Bestand nicht mehr.
        m = laden(con, r["material_id"])
        bew = con.execute("SELECT MAX(id) AS letzte, IFNULL(SUM(menge),0) AS s FROM lagerbewegungen WHERE auftragskosten_id=?", (kid,)).fetchone()
        menge = -(bew["s"] if bew["letzte"] else -(r["menge"] or 0))
        inventur = bew["letzte"] and con.execute("SELECT 1 FROM lagerbewegungen WHERE material_id=? AND art='inventur' AND id>?",
                                                 (m["id"], bew["letzte"])).fetchone()
        if inventur:
            hinweis = "Das Material wurde nach der Entnahme inventiert; der Lagerbestand bleibt deshalb unverändert."
        elif abs(menge) > 1e-9:
            con.execute("INSERT INTO lagerbewegungen (datum, material_id, menge, preis, art, auftrag_id, auftragskosten_id, lagerort, bemerkung, angelegt) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (date.today().isoformat(), m["id"], round(menge, 4), r["einzelpreis"] or 0, "rueckbuchung", r["auftrag_id"], None,
                         m["lagerort"] or "", f"Rückbuchung: Auftragskosten vom {r['datum'] or ''} gelöscht"[:200], jetzt()))
            con.execute("UPDATE material SET bestand=?, geaendert=? WHERE id=?", (round((m["bestand"] or 0) + menge, 4), jetzt(), m["id"]))
            _bestand_geaendert(con, m["id"])
        con.execute("UPDATE lagerbewegungen SET auftragskosten_id=NULL WHERE auftragskosten_id=?", (kid,))
    con.execute("DELETE FROM auftragskosten WHERE id=?", (kid,))
    return {"ok": True, "hinweis": hinweis} if hinweis else {"ok": True}


def ak_liste(con, aid=None, limit=500):
    sql = ("SELECT k.*, a.nummer AS auftrag, a.bezeichnung AS auftrag_bez, m.nummer AS matnr FROM auftragskosten k "
           "JOIN auftraege a ON a.id=k.auftrag_id LEFT JOIN material m ON m.id=k.material_id")
    par = []
    if aid:
        sql += " WHERE k.auftrag_id=?"
        par.append(aid)
    sql += " ORDER BY k.datum DESC, k.id DESC LIMIT ?"
    return zeilen(con.execute(sql, par + [limit]))


def ak_summen(con, aid, titel=None):
    """Ist-Kosten je Kostenart für Soll/Ist (optional nur eines Titels)."""
    s = {k: 0.0 for k in KOSTENARTEN}
    sql, par = "SELECT kostenart, SUM(betrag) AS b FROM auftragskosten WHERE auftrag_id=?", [aid]
    if titel is not None:
        sql += " AND IFNULL(titel,0)=?"
        par.append(int(titel))
    for r in con.execute(sql + " GROUP BY kostenart", par):
        if r["kostenart"] in s:
            s[r["kostenart"]] = r["b"] or 0
    return s


# ---------------------------------------------------------------- Beschlägesets
def set_laden(con, sid):
    s = con.execute("SELECT * FROM material_sets WHERE id=?", (sid,)).fetchone()
    if not s:
        raise Fehler("Set nicht gefunden", 404)
    s = dict(s)
    s["positionen"] = zeilen(con.execute(
        "SELECT p.*, m.nummer, m.bezeichnung, m.einheit, m.ek_preis, CASE WHEN m.kategorie IN ('beschlaege','artikel') THEN 0 ELSE m.verschnitt END AS verschnitt FROM material_set_pos p JOIN material m ON m.id=p.material_id "
        "WHERE p.set_id=? ORDER BY p.sort, p.id", (sid,)))
    s["summe"] = kfm(sum(p["menge"] * (p["ek_preis"] or 0) * (1 + (p["verschnitt"] or 0) / 100) for p in s["positionen"]))
    return s


def sets_liste(con, q):
    rows = zeilen(con.execute("SELECT * FROM material_sets ORDER BY nummer COLLATE NOCASE"))
    for r in rows:
        r.update({k: v for k, v in set_laden(con, r["id"]).items() if k in ("summe",)})
        r["anzahl"] = con.execute("SELECT COUNT(*) FROM material_set_pos WHERE set_id=?", (r["id"],)).fetchone()[0]
    if q.get("q"):
        w = q["q"].lower()
        rows = [r for r in rows if w in (r["nummer"] + " " + r["bezeichnung"]).lower()]
    return rows


def set_speichern(con, sid, d):
    if sid is None:
        nummer = (d.get("nummer") or "").strip()
        if not nummer:
            n = con.execute("SELECT COUNT(*) FROM material_sets").fetchone()[0] + 1
            nummer = f"SET{n:03d}"
        if con.execute("SELECT 1 FROM material_sets WHERE nummer=?", (nummer,)).fetchone():
            raise Fehler(f"Die Nummer {nummer} ist schon vergeben.")
        cur = con.execute("INSERT INTO material_sets (nummer, bezeichnung, bemerkungen, angelegt, geaendert) VALUES (?,?,?,?,?)",
                          (nummer, d.get("bezeichnung") or "", d.get("bemerkungen") or "", jetzt(), jetzt()))
        sid = cur.lastrowid
    else:
        set_laden(con, sid)
        w = {k: d[k] for k in ("nummer", "bezeichnung", "bemerkungen") if k in d}
        if w:
            w["geaendert"] = jetzt()
            con.execute(f"UPDATE material_sets SET {','.join(k + '=?' for k in w)} WHERE id=?", list(w.values()) + [sid])
    if isinstance(d.get("positionen"), list):
        con.execute("DELETE FROM material_set_pos WHERE set_id=?", (sid,))
        for i, p in enumerate(d["positionen"]):
            if str(p.get("material_id") or "").isdigit():
                con.execute("INSERT INTO material_set_pos (set_id, material_id, menge, sort) VALUES (?,?,?,?)",
                            (sid, int(p["material_id"]), f(p.get("menge")) or 1, i))
    return set_laden(con, sid)


# ---------------------------------------------------------------- Statistik
def statistik(con):
    lagerwert = zeilen(con.execute(
        "SELECT kategorie, COUNT(*) AS artikel, SUM(CASE WHEN lager=1 THEN 1 ELSE 0 END) AS gelagert, "
        "ROUND(SUM(CASE WHEN lager=1 AND bestand>0 THEN bestand*(CASE WHEN IFNULL(lagerpreis,0)>0 THEN lagerpreis ELSE IFNULL(ek_preis,0) END) ELSE 0 END),2) AS wert FROM material WHERE aktiv=1 GROUP BY kategorie"))
    knapp = zeilen(con.execute("SELECT id, kategorie, nummer, bezeichnung, einheit, bestand, mindestbestand FROM material "
                               "WHERE aktiv=1 AND lager=1 AND bestand < mindestbestand ORDER BY nummer"))
    jahr = str(date.today().year)
    verbrauch = zeilen(con.execute(
        "SELECT m.id, m.nummer, m.bezeichnung, m.einheit, m.kategorie, ROUND(SUM(k.menge),3) AS menge, ROUND(SUM(k.betrag),2) AS betrag, "
        "COUNT(DISTINCT k.auftrag_id) AS auftraege FROM auftragskosten k JOIN material m ON m.id=k.material_id "
        "WHERE substr(k.datum,1,4)=? GROUP BY m.id ORDER BY betrag DESC LIMIT 25", (jahr,)))
    kostenarten = zeilen(con.execute("SELECT kostenart, ROUND(SUM(betrag),2) AS betrag FROM auftragskosten WHERE substr(datum,1,4)=? "
                                     "GROUP BY kostenart", (jahr,)))
    alt = zeilen(con.execute("SELECT id, kategorie, nummer, bezeichnung, preis_vom FROM material WHERE aktiv=1 AND preis_vom<>'' "
                             "AND preis_vom < ? ORDER BY preis_vom LIMIT 25", (f"{int(jahr) - 1}{date.today().isoformat()[4:]}",)))
    return {"lagerwert": lagerwert, "knapp": knapp, "verbrauch": verbrauch, "kostenarten": kostenarten, "alte_preise": alt, "jahr": jahr}


def material_statistik(con, mid):
    m = laden(con, mid)
    return {"material": m, "bewegungen": bewegungen(con, mid, 200),
            "buchungen": zeilen(con.execute("SELECT k.*, a.nummer AS auftrag, a.bezeichnung AS auftrag_bez FROM auftragskosten k "
                                            "JOIN auftraege a ON a.id=k.auftrag_id WHERE k.material_id=? ORDER BY k.datum DESC LIMIT 200", (mid,))),
            "sets": zeilen(con.execute("SELECT s.id, s.nummer, s.bezeichnung, p.menge FROM material_set_pos p JOIN material_sets s ON s.id=p.set_id "
                                       "WHERE p.material_id=?", (mid,)))}


def kalk_typ(m):
    """Werkstoff-Typ der Auftragskalkulation für einen Materialstammsatz."""
    kat, gr = m["kategorie"], (m.get("gruppe") or "").lower()
    if kat == "holzwerkstoffe":
        if "kant" in gr:
            return "kante"
        if "furnier" in gr:
            return "furnier"
        return "platte"
    return {"massivholz": "massiv", "beschichtung": "oberflaeche", "chemie": "sonstig", "artikel": "sonstig"}.get(kat, "sonstig")


# ---------------------------------------------------------------- API
def einheiten(con):
    """Die Mengeneinheiten des Betriebs (Einstellungen), sonst die mitgelieferte Liste."""
    r = con.execute("SELECT wert FROM einstellungen WHERE schluessel='einheiten'").fetchone()
    try:
        eigene = json.loads(r["wert"]) if r else []
    except ValueError:
        eigene = []
    eigene = [x for x in eigene if isinstance(x, str)] if isinstance(eigene, list) else []
    return ["(keine)"] + [x for x in eigene if x != "(keine)"] if eigene else EINHEITEN


def api(con, methode, teile, q, daten):
    res = teile[0]
    rid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
    unter = teile[2] if len(teile) > 2 else None
    d = daten or {}
    if res == "material":
        if len(teile) > 1 and teile[1] == "statistik":
            return statistik(con)
        if len(teile) > 1 and teile[1] == "meta":
            return {"kategorien": KATEGORIEN, "einheiten": einheiten(con), "kostenarten": KOSTENARTEN, "standard_gruppen": STANDARD_GRUPPEN,
                    "kat_kostenart": KAT_KOSTENART}
        if rid is None:
            if methode == "GET":
                return liste(con, q)
            if methode == "POST":
                return anlegen(con, d)
        else:
            if methode == "GET" and unter is None:
                return laden(con, rid)
            if methode == "GET" and unter == "statistik":
                return material_statistik(con, rid)
            if methode == "PUT":
                return aendern(con, rid, d)
            if methode == "DELETE":
                return loeschen(con, rid)
            if methode == "POST" and unter == "kopieren":
                return kopieren(con, rid)
    if res == "materialsets":
        if rid is None and methode == "GET":
            return sets_liste(con, q)
        if rid is None and methode == "POST":
            return set_speichern(con, None, d)
        if rid and methode == "GET":
            return set_laden(con, rid)
        if rid and methode == "PUT":
            return set_speichern(con, rid, d)
        if rid and methode == "DELETE":
            con.execute("DELETE FROM material_set_pos WHERE set_id=?", (rid,))
            con.execute("DELETE FROM material_sets WHERE id=?", (rid,))
            return {"ok": True}
    if res == "lager":
        if methode == "GET":
            return bewegungen(con, int(q["material_id"]) if q.get("material_id", "").isdigit() else None)
        if methode == "POST":
            return lager_buchen(con, d)
    if res == "auftragskosten":
        if methode == "GET":
            return ak_liste(con, int(q["auftrag_id"]) if q.get("auftrag_id", "").isdigit() else None)
        if methode == "POST":
            return ak_buchen(con, d)
        if methode == "DELETE" and rid:
            return ak_loeschen(con, rid)
    raise Fehler("Unbekannte Anfrage", 404)
