"""Werkzeugverwaltung: Maschinen, Elektrowerkzeuge, Handwerkzeug, Software – mit Kaufdaten, Prüf- und Wartungsterminen."""
from datetime import date, datetime
from kern import kfm

SCHEMA = """
CREATE TABLE IF NOT EXISTS werkzeuge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer TEXT UNIQUE NOT NULL,
    bezeichnung TEXT DEFAULT '',
    art TEXT DEFAULT 'Elektrowerkzeug',
    hersteller TEXT DEFAULT '',
    artikelnr TEXT DEFAULT '',
    seriennr TEXT DEFAULT '',
    lieferant_id INTEGER,
    zahlung_id INTEGER,
    rechnung TEXT DEFAULT '',
    kaufdatum TEXT DEFAULT '',
    preis REAL DEFAULT 0,
    menge REAL DEFAULT 1,
    standort TEXT DEFAULT '',
    status TEXT DEFAULT 'in Betrieb',
    garantie_bis TEXT DEFAULT '',
    pruefung_bis TEXT DEFAULT '',
    wartung_bis TEXT DEFAULT '',
    bemerkungen TEXT DEFAULT '',
    nutzungsdauer REAL,
    angelegt TEXT, geaendert TEXT
);
"""
ARTEN = ["Stationäre Maschine", "Maschinenzubehör", "Elektrowerkzeug", "Akkuwerkzeug", "Druckluftwerkzeug", "Handwerkzeug",
         "Spannmittel", "Messwerkzeug", "Betriebs- und Lagerausstattung", "Sicherheitsausrüstung", "IT & Büro", "Software",
         "Fahrzeug/Anhänger", "Sonstiges"]
# Kategorienamen aus fremden Listen → eigene Art
ART_ALIAS = {"maschinen": "Stationäre Maschine", "maschine": "Stationäre Maschine", "stationäre maschinen": "Stationäre Maschine",
             "mess- und prüfmittel": "Messwerkzeug", "messmittel": "Messwerkzeug", "prüfmittel": "Messwerkzeug", "messwerkzeuge": "Messwerkzeug",
             "lager- und betriebsausstattung": "Betriebs- und Lagerausstattung", "betriebsausstattung": "Betriebs- und Lagerausstattung",
             "lagerausstattung": "Betriebs- und Lagerausstattung", "werkstattausstattung": "Betriebs- und Lagerausstattung",
             "büroausstattung": "IT & Büro", "it": "IT & Büro", "edv": "IT & Büro", "büro": "IT & Büro",
             "fahrzeuge": "Fahrzeug/Anhänger", "fahrzeug": "Fahrzeug/Anhänger", "anhänger": "Fahrzeug/Anhänger",
             "psa": "Sicherheitsausrüstung", "arbeitsschutz": "Sicherheitsausrüstung", "zubehör": "Maschinenzubehör"}
STATUS = ["in Betrieb", "in Reparatur", "verliehen", "defekt", "ausgemustert"]
FELDER = ["bezeichnung", "art", "hersteller", "artikelnr", "seriennr", "lieferant_id", "zahlung_id", "rechnung", "kaufdatum",
          "preis", "menge", "standort", "status", "garantie_bis", "pruefung_bis", "wartung_bis", "bemerkungen", "nutzungsdauer"]
GWG_GRENZE = 800.0  # Netto-Grenze für geringwertige Wirtschaftsgüter (§ 6 Abs. 2 EStG)
HERSTELLER = ["Festool", "Makita", "Bosch", "Metabo", "Mafell", "Hilti", "DeWalt", "Milwaukee", "Fein", "Lamello", "Domino",
              "Shaper", "Felder", "Hammer", "Altendorf", "Martin", "SCM", "Holz-Her", "Kreg", "Bessey", "Piher", "Würth", "Hettich",
              "Leitz", "Freud", "Festo", "Kärcher", "Stihl", "Hikoki", "Metabo HPT", "Proxxon", "Dremel", "Wolfcraft", "Knipex",
              "Wera", "Wiha", "Stanley", "Stabila", "Hultafors", "Miller"]


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def zahl(v):
    try:
        return float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) and "," in v else float(v or 0)
    except ValueError:
        return 0.0


def schema(con):
    con.executescript(SCHEMA)


def naechste_nummer(con):
    r = con.execute("SELECT nummer FROM werkzeuge WHERE nummer LIKE 'W%' ORDER BY CAST(SUBSTR(nummer,2) AS INTEGER) DESC LIMIT 1").fetchone()
    n = int(r["nummer"][1:]) + 1 if r and r["nummer"][1:].isdigit() else 1
    return f"W{n:04d}"


def hersteller_raten(text):
    t = (text or "").lower()
    for h in HERSTELLER:
        if h.lower() in t:
            return h
    return ""


def art_raten(text):
    t = (text or "").lower()
    if any(w in t for w in ("license", "lizenz", "software", "abo ")):
        return "Software"
    if any(w in t for w in ("akku", "accu", "18v", "18 v", "cordless")):
        return "Akkuwerkzeug"
    if any(w in t for w in ("zwinge", "clamp", "spann", "klemme")):
        return "Spannmittel"
    if any(w in t for w in ("formatkreis", "abricht", "dickte", "kantenanleim", "cnc", "bandsäge", "tischfräse", "absaug")):
        return "Stationäre Maschine"
    if any(w in t for w in ("maßstab", "massstab", "wasserwaage", "winkel", "messschieber", "laser")):
        return "Messwerkzeug"
    if any(w in t for w in ("säge", "saege", "fräse", "fraese", "schleifer", "bohr", "schrauber", "hobel", "kapex", "domino", "1.600 w")):
        return "Elektrowerkzeug"
    return "Handwerkzeug"


def anlegen(con, d):
    werte = {k: d.get(k) for k in FELDER if k in d}
    werte["preis"] = kfm(zahl(werte.get("preis")))
    werte["menge"] = zahl(werte.get("menge")) or 1
    if "nutzungsdauer" in werte:
        werte["nutzungsdauer"] = zahl(werte["nutzungsdauer"]) or None
    werte.setdefault("art", art_raten(werte.get("bezeichnung")))
    werte.setdefault("hersteller", hersteller_raten(werte.get("bezeichnung")))
    werte.setdefault("kaufdatum", date.today().isoformat())
    werte["nummer"] = d.get("nummer") or naechste_nummer(con)
    werte["angelegt"] = werte["geaendert"] = jetzt()
    cur = con.execute(f"INSERT INTO werkzeuge ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})", list(werte.values()))
    return laden(con, cur.lastrowid)


def laden(con, wid):
    r = con.execute("SELECT w.*, l.kurzname AS lieferant, z.nummer AS zahlungsnr FROM werkzeuge w "
                    "LEFT JOIN lieferanten l ON l.id=w.lieferant_id LEFT JOIN zahlungen z ON z.id=w.zahlung_id WHERE w.id=?", (wid,)).fetchone()
    if not r:
        raise Fehler("Werkzeug nicht gefunden", 404)
    return ergaenzen(dict(r))


def ergaenzen(w):
    heute = date.today().isoformat()
    w["gwg"] = 0 < (w["preis"] or 0) / (w["menge"] or 1) <= GWG_GRENZE
    w["pruefung_faellig"] = bool(w["pruefung_bis"]) and w["pruefung_bis"] <= heute and w["status"] != "ausgemustert"
    w["wartung_faellig"] = bool(w["wartung_bis"]) and w["wartung_bis"] <= heute and w["status"] != "ausgemustert"
    w["restwert"] = restwert(w)
    return w


def restwert(w, stichtag=None):
    """Linearer Buchwert zum Stichtag (monatsgenau, Kaufmonat zählt voll). None, wenn keine Nutzungsdauer oder kein Kaufdatum."""
    nd = w.get("nutzungsdauer") or 0
    kd = w.get("kaufdatum") or ""
    preis = w.get("preis") or 0
    if not nd or nd <= 0 or len(kd) < 7 or not preis:
        return None
    st = stichtag or date.today()
    try:
        y, m = int(kd[:4]), int(kd[5:7])
    except ValueError:
        return None
    monate = (st.year - y) * 12 + (st.month - m) + 1
    if monate <= 0:
        return kfm(preis)
    return kfm(max(0.0, preis * (1 - monate / (nd * 12))))


def liste(con, q):
    sql = ("SELECT w.*, l.kurzname AS lieferant, z.nummer AS zahlungsnr FROM werkzeuge w "
           "LEFT JOIN lieferanten l ON l.id=w.lieferant_id LEFT JOIN zahlungen z ON z.id=w.zahlung_id WHERE 1=1")
    p = []
    st = q.get("status", "aktiv")
    if st == "aktiv":
        sql += " AND w.status<>'ausgemustert'"
    elif st == "faellig":
        sql += " AND w.status<>'ausgemustert' AND ((w.pruefung_bis<>'' AND w.pruefung_bis<=?) OR (w.wartung_bis<>'' AND w.wartung_bis<=?))"
        p += [date.today().isoformat()] * 2
    elif st:
        sql += " AND w.status=?"
        p.append(st)
    if q.get("art"):
        sql += " AND w.art=?"
        p.append(q["art"])
    such = (q.get("q") or "").strip().lower()
    if such:
        sql += " AND (ulower(w.bezeichnung) LIKE ? OR ulower(w.nummer) LIKE ? OR ulower(w.hersteller) LIKE ? OR ulower(w.seriennr) LIKE ? OR ulower(w.standort) LIKE ?)"
        p += [f"%{such}%"] * 5
    return [ergaenzen(dict(r)) for r in con.execute(sql + " ORDER BY w.nummer", p)]


def api(con, methode, teile, q, daten):
    rid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
    if methode == "GET" and len(teile) == 2 and teile[1] == "meta":
        return {"arten": ARTEN, "status": STATUS, "gwg_grenze": GWG_GRENZE,
                "standorte": [r[0] for r in con.execute("SELECT DISTINCT standort FROM werkzeuge WHERE standort<>'' ORDER BY standort")]}
    if methode == "POST" and len(teile) == 2 and teile[1] == "import":
        return importieren(con, daten or {})
    if methode == "GET" and rid is None:
        return liste(con, q)
    if methode == "GET" and rid:
        return laden(con, rid)
    if methode == "POST" and rid is None:
        return anlegen(con, daten or {})
    if methode == "PUT" and rid:
        laden(con, rid)
        werte = {k: (daten or {})[k] for k in FELDER if k in (daten or {})}
        if "preis" in werte:
            werte["preis"] = kfm(zahl(werte["preis"]))
        if "menge" in werte:
            werte["menge"] = zahl(werte["menge"]) or 1
        if "nutzungsdauer" in werte:
            werte["nutzungsdauer"] = zahl(werte["nutzungsdauer"]) or None
        if werte:
            werte["geaendert"] = jetzt()
            con.execute(f"UPDATE werkzeuge SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [rid])
        return laden(con, rid)
    if methode == "DELETE" and rid:
        laden(con, rid)
        con.execute("DELETE FROM werkzeuge WHERE id=?", (rid,))
        return {"ok": True}
    raise Fehler("Unbekannte Anfrage", 404)


# ------------------------------------------------------------------ Import aus CSV / Excel
IMPORT_FELDER = [
    ("nummer", "Inventarnummer", ["inventarnummer", "inventar nr", "inventar-nr", "inv nr", "inv.-nr.", "nr", "nr.", "nummer", "lfd nr", "id"]),
    ("bezeichnung", "Bezeichnung", ["bezeichnung", "werkzeug", "maschine", "gerät", "geraet", "name", "artikel", "beschreibung"]),
    ("art", "Art / Kategorie", ["art", "kategorie", "gruppe", "werkzeugart", "geräteart", "typ art"]),
    ("hersteller", "Hersteller", ["hersteller", "marke", "fabrikat", "firma"]),
    ("artikelnr", "Modell / Artikelnummer", ["modell", "typ", "modellbezeichnung", "typbezeichnung", "artikelnummer", "artikel nr", "art nr", "art.-nr.", "bestellnummer", "bestell nr", "modellnummer"]),
    ("seriennr", "Seriennummer", ["seriennummer", "serien nr", "serien-nr", "sn", "s/n", "serial", "fabriknummer"]),
    ("standort", "Standort", ["standort", "ort", "lagerort", "raum", "platz", "fahrzeug"]),
    ("kaufdatum", "Kaufdatum", ["kaufdatum", "gekauft", "anschaffung", "anschaffungsdatum", "datum", "kauf", "baujahr", "jahr"]),
    ("preis", "Preis netto", ["preis", "preis netto", "anschaffungspreis", "anschaffungswert", "kaufpreis", "wert", "netto", "ek", "betrag", "kosten"]),
    ("menge", "Anzahl", ["anzahl", "menge", "stück", "stk", "stueck"]),
    ("nutzungsdauer", "Nutzungsdauer (Jahre, für Abschreibung)", ["nutzungsdauer", "dauer abschreibung", "abschreibung jahre", "afa jahre",
                                                                  "afa dauer", "nd", "dauer abschreibung (jahre)", "abschreibungsdauer"]),
    ("status", "Status", ["status", "zustand"]),
    ("lieferant", "Lieferant / Händler", ["lieferant", "händler", "haendler", "gekauft bei", "bezugsquelle", "shop"]),
    ("rechnung", "Rechnungsnummer", ["rechnung", "rechnungsnummer", "rechnungs nr", "beleg", "belegnummer"]),
    ("garantie_bis", "Garantie bis", ["garantie", "garantie bis", "gewährleistung"]),
    ("pruefung_bis", "Nächste Prüfung", ["prüfung", "pruefung", "nächste prüfung", "dguv", "e-check", "uvv", "prüfdatum", "geprüft bis"]),
    ("wartung_bis", "Nächste Wartung", ["wartung", "nächste wartung", "service", "inspektion"]),
    ("bemerkungen", "Bemerkungen (mehrere möglich)", ["bemerkung", "bemerkungen", "notiz", "notizen", "info", "zubehör", "zubehoer", "hinweis"]),
]
IMPORT_NAMEN = {k: n for k, n, _ in IMPORT_FELDER}


def _norm(s):
    import re
    return re.sub(r"[\s_]+", " ", (s or "").strip().lower())


def import_vorschlag(kopf):
    zuordnung, vergeben = {}, set()
    for exakt in (True, False):
        for i, h in enumerate(kopf):
            if str(i) in zuordnung:
                continue
            hn = _norm(h)
            if not hn:
                continue
            afa = any(w in hn for w in ("abschreib", "afa", "buchwert", "restwert"))
            for k, _, worte in IMPORT_FELDER:
                if k in vergeben and k != "bemerkungen":
                    continue
                if afa and k != "nutzungsdauer":
                    continue  # „Abschreibung/Jahr“, „Steuerl. Abschreibung Anzahl Jahre“ … nicht als Kaufdatum/Anzahl lesen
                if (exakt and hn in worte) or (not exakt and any(w in hn for w in worte if len(w) > 3)):
                    zuordnung[str(i)] = k
                    vergeben.add(k)
                    break
    return zuordnung


def datum_lesen(s):
    """dd.mm.yyyy, yyyy-mm-dd, mm/yyyy, nur Jahr oder Excel-Seriennummer → ISO-Datum."""
    import re
    from datetime import timedelta
    s = (s or "").strip()
    if not s:
        return ""
    if re.fullmatch(r"\d{5}(\.\d+)?", s):  # Excel-Datum
        try:
            return (date(1899, 12, 30) + timedelta(days=int(float(s)))).isoformat()
        except (ValueError, OverflowError):
            return ""
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, t = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.match(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", s)
        if m:
            t, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            y += 2000 if y < 100 else 0
        else:
            m = re.fullmatch(r"(\d{1,2})[./](\d{4})", s)
            if m:
                t, mo, y = 1, int(m.group(1)), int(m.group(2))
            elif re.fullmatch(r"(19|20)\d{2}", s):
                t, mo, y = 1, 1, int(s)
            else:
                return ""
    try:
        return date(y, mo, t).isoformat()
    except ValueError:
        return ""


def preis_lesen(s):
    import re
    s = re.sub(r"[^\d,.\-]", "", (s or "").replace("€", ""))
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):  # 8.900 oder 12.500 = Tausenderpunkte
        s = s.replace(".", "")
    try:
        return kfm(float(s))
    except ValueError:
        return 0.0


def _passend(wert, liste):
    w = _norm(wert)
    if not w:
        return ""
    for x in liste:
        if _norm(x) == w:
            return x
    for x in liste:
        if w in _norm(x) or _norm(x) in w:
            return x
    return ""


def import_datensatz(zeile, zuordnung):
    d, bem = {}, []
    for i, feld in zuordnung.items():
        if not feld:
            continue
        try:
            wert = (zeile[int(i)] or "").strip()
        except (IndexError, ValueError):
            continue
        if not wert or wert in ("-", "–", "—", "/", "?", "n/a", "k.a.", "k. a.", "0,00 €"):
            continue
        if feld == "bemerkungen":
            bem.append(wert)
        elif feld in d and feld in ("bezeichnung",):
            d[feld] += " " + wert
        else:
            d[feld] = wert
    if bem:
        d["bemerkungen"] = "\n".join(bem)
    if not d.get("bezeichnung"):
        if not (d.get("hersteller") or d.get("artikelnr") or d.get("seriennr")):
            return None
        d["bezeichnung"] = " ".join(x for x in (d.get("hersteller"), d.get("artikelnr")) if x) or "Werkzeug"
    for k in ("kaufdatum", "garantie_bis", "pruefung_bis", "wartung_bis"):
        if k in d:
            roh = d[k]
            d[k] = datum_lesen(roh)
            if not d[k] and roh:
                d["bemerkungen"] = (d.get("bemerkungen", "") + f"\n{IMPORT_NAMEN[k]}: {roh}").strip()
    d.setdefault("kaufdatum", "")
    d["preis"] = preis_lesen(d.get("preis"))
    d["menge"] = preis_lesen(d.get("menge")) or 1
    if "nutzungsdauer" in d:
        d["nutzungsdauer"] = preis_lesen(d["nutzungsdauer"]) or None
    roh_art = d.get("art", "")
    d["art"] = ART_ALIAS.get(_norm(roh_art)) or _passend(roh_art, ARTEN) or art_raten(f"{roh_art} {d['bezeichnung']}")
    roh_st = d.get("status", "")
    d["status"] = (_passend(roh_st, STATUS) or ("ausgemustert" if _norm(roh_st) in ("verkauft", "entsorgt", "weg", "verschrottet") else "")
                   or ("defekt" if _norm(roh_st) in ("kaputt", "reparaturbedürftig") else "in Betrieb"))
    if roh_st and _norm(roh_st) != _norm(d["status"]):
        d["bemerkungen"] = (d.get("bemerkungen", "") + f"\nZustand: {roh_st}").strip()
    d["hersteller"] = d.get("hersteller") or hersteller_raten(d["bezeichnung"])
    return d


def import_doppelt(con, d):
    if d.get("nummer"):  # Inventarnummer ist eindeutig – gleiche Bezeichnung mit anderer Nummer ist ein eigenes Stück
        r = con.execute("SELECT id FROM werkzeuge WHERE nummer=?", (d["nummer"],)).fetchone()
        return r["id"] if r else None
    if d.get("seriennr"):
        r = con.execute("SELECT id FROM werkzeuge WHERE ulower(seriennr)=?", (d["seriennr"].lower(),)).fetchone()
        if r:
            return r["id"]
    if d.get("nummer"):
        r = con.execute("SELECT id FROM werkzeuge WHERE nummer=?", (d["nummer"],)).fetchone()
        if r:
            return r["id"]
    r = con.execute("SELECT id FROM werkzeuge WHERE ulower(bezeichnung)=? AND IFNULL(kaufdatum,'')=?",
                    (d["bezeichnung"].lower(), d.get("kaufdatum") or "")).fetchone()
    return r["id"] if r else None


def importieren(con, d):
    import base64
    import kundenimport
    try:
        roh = base64.b64decode(d.get("daten") or "")
        info = {}
        blatt = d.get("blatt")
        if not blatt and roh[:2] == b"PK":  # Blatt „Inventur…“ / „Werkzeug…“ bevorzugen
            blatt = next((b for b in kundenimport.xlsx_blattnamen(roh) if any(w in b.lower() for w in ("inventur", "werkzeug", "maschine", "anlage"))), None)
        tab = kundenimport.tabelle_lesen(roh, d.get("dateiname"), blatt, info)
    except kundenimport.ImportFehler as f:
        raise Fehler(str(f))
    kopf = tab[0]
    gelb = {i - 1 for i in info.get("gelb", []) if i > 0}
    gelbe_weg = d.get("gelbe_ueberspringen", True) is not False
    alle_zeilen = tab[1:]
    zeilen = [z for i, z in enumerate(alle_zeilen) if not (gelbe_weg and i in gelb)]
    zuordnung = d.get("zuordnung") or import_vorschlag(kopf)
    lieferanten = {(r["kurzname"] or "").lower(): r["id"] for r in con.execute("SELECT id, kurzname FROM lieferanten")}

    def mit_lieferant(w):
        name = (w.pop("lieferant", "") or "").strip()
        if name:
            lid = lieferanten.get(name.lower()) or next((i for n, i in lieferanten.items() if n and (n in name.lower() or name.lower() in n)), None)
            if lid:
                w["lieferant_id"] = lid
            else:
                w["bemerkungen"] = (w.get("bemerkungen", "") + f"\nGekauft bei: {name}").strip()
        return w
    import collections
    nr_zaehler = collections.Counter((import_datensatz(z, zuordnung) or {}).get("nummer") for z in zeilen)
    doppelte_nummern = sorted(n for n, c in nr_zaehler.items() if n and c > 1)
    if not d.get("ausfuehren"):
        vorschau, dop = [], 0
        for z in zeilen:
            w = import_datensatz(z, zuordnung)
            if not w:
                continue
            ist = import_doppelt(con, w)
            dop += 1 if ist else 0
            if len(vorschau) < 8:
                vorschau.append({**w, "_doppelt": bool(ist)})
        gelbe = [import_datensatz(z, zuordnung) for i, z in enumerate(alle_zeilen) if i in gelb]
        gelbe = [w for w in gelbe if w]
        return {"kopf": kopf, "beispiele": zeilen[:5], "anzahl": sum(1 for z in zeilen if import_datensatz(z, zuordnung)),
                "zeilen": len(zeilen), "zuordnung": zuordnung,
                "blaetter": info.get("blaetter", []), "blatt": info.get("blatt", ""), "excel": "blaetter" in info,
                "gelb": len(gelbe), "gelb_summe": kfm(sum(w["preis"] for w in gelbe)),
                "gelb_beispiele": [w["bezeichnung"] for w in gelbe[:6]], "gelbe_ueberspringen": gelbe_weg,
                "doppelte_nummern": doppelte_nummern,
                "felder": [[k, n] for k, n, _ in IMPORT_FELDER], "vorschau": vorschau, "doppelte": dop,
                "summe": kfm(sum((import_datensatz(z, zuordnung) or {}).get("preis", 0) for z in zeilen))}
    modus = d.get("doppelte") or "ueberspringen"
    neu = aktualisiert = uebersprungen = leer = 0
    neue_ids, umnummeriert = set(), []
    for z in zeilen:
        w = import_datensatz(z, zuordnung)
        if not w:
            leer += 1
            continue
        w = mit_lieferant(w)
        ist = import_doppelt(con, w)
        if ist in neue_ids:  # gleiche Nr./Bezeichnung zweimal in derselben Datei → eigenes Stück
            ist = None
        if ist:
            if modus == "aktualisieren":
                werte = {k: v for k, v in w.items() if k in FELDER and v not in ("", None)}
                werte["geaendert"] = jetzt()
                con.execute(f"UPDATE werkzeuge SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [ist])
                aktualisiert += 1
            else:
                uebersprungen += 1
            continue
        nr = (w.get("nummer") or "").strip()
        if nr and con.execute("SELECT 1 FROM werkzeuge WHERE nummer=?", (nr,)).fetchone():
            neu_w = anlegen(con, {**{k: v for k, v in w.items() if k in FELDER}, "nummer": None,
                                  "bemerkungen": (w.get("bemerkungen", "") + f"\nIn der Importliste mit Nr. {nr} (doppelt vergeben)").strip()})
            umnummeriert.append(f"{w['bezeichnung']}: {nr} → {neu_w['nummer']}")
        else:
            neu_w = anlegen(con, {**{k: v for k, v in w.items() if k in FELDER}, "nummer": nr or None})
        neue_ids.add(neu_w["id"])
        neu += 1
    return {"neu": neu, "aktualisiert": aktualisiert, "uebersprungen": uebersprungen, "leer": leer, "umnummeriert": umnummeriert}
