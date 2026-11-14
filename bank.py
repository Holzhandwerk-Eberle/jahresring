"""Jahresring – Kontoauszüge (CAMT.053/052) einlesen und Umsätze offenen Posten bzw. Zahlungsaufträgen zuordnen.

Ablauf: Datei (XML oder ZIP mit XML) → Umsätze speichern (doppelte über einen Schlüssel erkennen) → Vorschläge
→ der Benutzer bestätigt → Zahlungseingang beim offenen Posten bzw. „bezahlt“ beim Zahlungsauftrag.
Gebucht wird über Rückrufe aus app.py (dieselbe Logik wie beim Erfassen von Hand), damit Mahnkosten, Skonto
und Protokoll gleich behandelt werden.
"""
import hashlib
import io
import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS bank_auszuege (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datei TEXT DEFAULT '', ablage TEXT DEFAULT '', sha256 TEXT DEFAULT '', format TEXT DEFAULT '',
    iban TEXT DEFAULT '', von TEXT DEFAULT '', bis TEXT DEFAULT '',
    saldo_anfang REAL, saldo_ende REAL, saldo_datum TEXT DEFAULT '',
    neu INTEGER DEFAULT 0, doppelt INTEGER DEFAULT 0, importiert TEXT, benutzer TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bank_umsaetze (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auszug_id INTEGER, iban TEXT DEFAULT '', buchung TEXT DEFAULT '', valuta TEXT DEFAULT '', betrag REAL DEFAULT 0,
    name TEXT DEFAULT '', gegen_iban TEXT DEFAULT '', zweck TEXT DEFAULT '', e2e TEXT DEFAULT '', referenz TEXT DEFAULT '',
    schluessel TEXT UNIQUE, status TEXT DEFAULT 'offen', ziel TEXT DEFAULT '[]', notiz TEXT DEFAULT '',
    zugeordnet TEXT DEFAULT '', von TEXT DEFAULT '', angelegt TEXT
);
CREATE INDEX IF NOT EXISTS ix_bank_umsaetze_buchung ON bank_umsaetze(buchung);
CREATE INDEX IF NOT EXISTS ix_bank_umsaetze_status ON bank_umsaetze(status);
"""

MAX_DATEI = 50 * 1024 * 1024
MAX_ENTPACKT = 200 * 1024 * 1024


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def schema(con):
    con.executescript(SCHEMA)


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def zeilen(rows):
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- CAMT lesen
def _ln(tag):
    return tag.rsplit("}", 1)[-1]


def _kinder(el, name):
    return [k for k in list(el) if _ln(k.tag) == name] if el is not None else []


def _kind(el, *pfad):
    """Erstes Element entlang eines Pfads aus lokalen Namen (Namensraum egal)."""
    for name in pfad:
        if el is None:
            return None
        el = next((k for k in list(el) if _ln(k.tag) == name), None)
    return el


def _text(el, *pfad):
    e = _kind(el, *pfad)
    return (e.text or "").strip() if e is not None and e.text else ""


def _datum(el):
    """<Dt> oder <DtTm> unterhalb von el."""
    t = _text(el, "Dt") or _text(el, "DtTm")
    return t[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", t or "") else ""


def _betrag(el):
    t = _text(el, "Amt")
    try:
        b = float(t)
    except ValueError:
        return None
    return -b if _text(el, "CdtDbtInd") == "DBIT" else b


def _iban(t):
    return re.sub(r"\s", "", t or "").upper()


def _xml_pruefen(roh):
    if re.search(rb"<!\s*(DOCTYPE|ENTITY)", bytes(roh).replace(b"\x00", b""), re.I):
        raise Fehler("Die Datei enthält eine DTD bzw. Entity-Deklaration und wird aus Sicherheitsgründen nicht gelesen.")
    try:
        return ET.fromstring(roh)
    except ET.ParseError:
        raise Fehler("Die Datei ist kein lesbares XML (CAMT-Kontoauszug).")


def _name(rp, rolle):
    """Name aus RltdPties/<Dbtr|Cdtr> (CAMT .02: Dbtr/Nm, ab .08: Dbtr/Pty/Nm), sonst Ultimate-Partei."""
    for r in (rolle, "Ultmt" + rolle):
        n = _text(rp, r, "Nm") or _text(rp, r, "Pty", "Nm")
        if n:
            return n
    return ""


def _umsaetze_aus(stmt, iban, fmt):
    aus = []
    for nt in _kinder(stmt, "Ntry"):
        sts = _text(nt, "Sts") or _text(nt, "Sts", "Cd")
        if sts and sts not in ("BOOK",):
            continue   # vorgemerkte Umsätze (PDNG, INFO) erst übernehmen, wenn sie gebucht sind
        betrag = _betrag(nt)
        if betrag is None:
            continue
        buchung = _datum(_kind(nt, "BookgDt")) or _datum(_kind(nt, "ValDt"))
        valuta = _datum(_kind(nt, "ValDt")) or buchung
        ref = _text(nt, "AcctSvcrRef") or _text(nt, "NtryRef")
        zusatz = _text(nt, "AddtlNtryInf")
        txs = [t for d in _kinder(nt, "NtryDtls") for t in _kinder(d, "TxDtls")]
        teile = []
        for t in txs:
            tb = None
            for pfad in (("AmtDtls", "TxAmt"), ("AmtDtls", "InstdAmt")):
                e = _kind(t, *pfad)
                if e is not None and _text(e, "Amt"):
                    try:
                        tb = abs(float(_text(e, "Amt")))
                    except ValueError:
                        tb = None
                    break
            if tb is None and _text(t, "Amt"):
                try:
                    tb = abs(float(_text(t, "Amt")))
                except ValueError:
                    tb = None
            teile.append((t, tb))
        # Sammelbuchung mit Einzelbeträgen: jede Einzelzahlung als eigener Umsatz (z. B. ausgeführte SEPA-Sammelüberweisung)
        einzeln = len(teile) > 1 and all(tb is not None for _, tb in teile) and abs(sum(tb for _, tb in teile) - abs(betrag)) < 0.005
        if not einzeln:
            teile = [(teile[0][0] if teile else None, abs(betrag))]
        for nr, (t, tb) in enumerate(teile):
            vz = -1 if betrag < 0 else 1
            if t is not None and _text(t, "CdtDbtInd") in ("CRDT", "DBIT") and einzeln:
                vz = -1 if _text(t, "CdtDbtInd") == "DBIT" else 1
            gutschrift = vz > 0
            rp = _kind(t, "RltdPties") if t is not None else None
            name = _name(rp, "Dbtr" if gutschrift else "Cdtr") if rp is not None else ""
            konto = _iban(_text(rp, "DbtrAcct" if gutschrift else "CdtrAcct", "Id", "IBAN")) if rp is not None else ""
            zweck = []
            if t is not None:
                ri = _kind(t, "RmtInf")
                zweck += [(u.text or "").strip() for u in _kinder(ri, "Ustrd") if u.text]
                for s in _kinder(ri, "Strd"):
                    r = _text(s, "CdtrRefInf", "Ref")
                    if r:
                        zweck.append(r)
                if _text(t, "AddtlTxInf"):
                    zweck.append(_text(t, "AddtlTxInf"))
            e2e = _text(t, "Refs", "EndToEndId") if t is not None else ""
            if e2e.upper() in ("NOTPROVIDED", "NOT PROVIDED"):
                e2e = ""
            if not zweck and zusatz:
                zweck.append(zusatz)
            aus.append({"iban": iban, "buchung": buchung, "valuta": valuta, "betrag": round(vz * tb, 2),
                        "name": name[:140], "gegen_iban": konto, "zweck": " ".join(zweck)[:500], "e2e": e2e[:35],
                        "referenz": (ref + (f"/{nr + 1}" if einzeln else ""))[:60], "_ref_bank": bool(ref)})
    return aus


def camt_lesen(roh, dateiname=""):
    """Liest eine CAMT-Datei (oder ein ZIP mit mehreren). Ergebnis: Liste der Auszüge mit ihren Umsätzen."""
    if len(roh) > MAX_DATEI:
        raise Fehler("Die Datei ist zu groß (höchstens 50 MB).")
    if roh[:2] == b"PK":
        try:
            z = zipfile.ZipFile(io.BytesIO(roh))
        except zipfile.BadZipFile:
            raise Fehler("Das ZIP-Archiv ist beschädigt.")
        namen = [i for i in z.infolist() if i.filename.lower().endswith(".xml") and not i.is_dir()]
        if not namen:
            raise Fehler("Im ZIP-Archiv ist keine XML-Datei.")
        if len(namen) > 1000 or sum(i.file_size for i in namen) > MAX_ENTPACKT:
            raise Fehler("Das ZIP-Archiv ist zu groß.")
        aus = []
        for i in sorted(namen, key=lambda i: i.filename):
            aus += camt_lesen(z.read(i), i.filename)
        return aus
    wurzel = _xml_pruefen(roh)
    doc = next((k for k in list(wurzel) if _ln(k.tag).startswith("BkToCstm")), None)
    if doc is None:
        raise Fehler("Das ist kein CAMT-Kontoauszug (camt.052 oder camt.053).")
    fmt = {"BkToCstmrStmt": "camt.053", "BkToCstmrAcctRpt": "camt.052", "BkToCstmrDbtCdtNtfctn": "camt.054"}.get(_ln(doc.tag), _ln(doc.tag))
    aus = []
    for st in [k for k in list(doc) if _ln(k.tag) in ("Stmt", "Rpt", "Ntfctn")]:
        iban = _iban(_text(st, "Acct", "Id", "IBAN"))
        saldo = {}
        for b in _kinder(st, "Bal"):
            tp = _text(b, "Tp", "CdOrPrtry", "Cd")
            saldo[tp] = (_betrag(b), _datum(_kind(b, "Dt")))
        anf = saldo.get("OPBD") or saldo.get("PRCD")
        ende = saldo.get("CLBD") or saldo.get("ITBD") or saldo.get("CLAV")
        zr = _kind(st, "FrToDt")
        umsaetze = _umsaetze_aus(st, iban, fmt)
        tage = sorted(u["buchung"] for u in umsaetze if u["buchung"])
        aus.append({"datei": dateiname, "format": fmt, "iban": iban,
                    "von": (_text(zr, "FrDtTm") or _text(zr, "FrDt"))[:10] or (tage[0] if tage else ""),
                    "bis": (_text(zr, "ToDtTm") or _text(zr, "ToDt"))[:10] or (tage[-1] if tage else ""),
                    "saldo_anfang": anf[0] if anf else None, "saldo_ende": ende[0] if ende else None,
                    "saldo_datum": (ende[1] if ende else "") or (tage[-1] if tage else ""), "umsaetze": umsaetze})
    return aus


def schluessel_setzen(umsaetze):
    """Eindeutiger Schlüssel je Umsatz, damit sich überschneidende Auszüge (Tagesauszug + Monatsauszug) nichts doppelt
    anlegen. Mit Bankreferenz: Konto + Referenz; sonst Inhalt + laufende Nummer gleicher Umsätze in derselben Datei."""
    zaehler = {}
    for u in umsaetze:
        if u.pop("_ref_bank", False):
            basis = f"{u['iban']}|ref|{u['referenz']}|{u['betrag']:.2f}"
        else:
            basis = f"{u['iban']}|{u['buchung']}|{u['betrag']:.2f}|{u['name']}|{u['zweck']}|{u['e2e']}"
        zaehler[basis] = zaehler.get(basis, 0) + 1
        u["schluessel"] = hashlib.sha256(f"{basis}#{zaehler[basis]}".encode("utf-8")).hexdigest()
    return umsaetze


def einlesen(con, roh, dateiname, ablage_ordner, wer=""):
    auszuege = camt_lesen(roh, dateiname)
    if not auszuege:
        raise Fehler("In der Datei sind keine Kontoauszüge.")
    sha = hashlib.sha256(roh).hexdigest()
    jahr = date.today().year
    ordner = os.path.join(ablage_ordner, str(jahr))
    os.makedirs(ordner, exist_ok=True)
    sicher = re.sub(r"[^\w.\- ]", "_", os.path.basename(dateiname or "kontoauszug.xml"))[:80] or "kontoauszug.xml"
    ablage = os.path.join(str(jahr), f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{sicher}")
    with open(os.path.join(ablage_ordner, ablage), "wb") as f:
        f.write(roh)
    erg = {"auszuege": 0, "neu": 0, "doppelt": 0, "ids": []}
    for a in auszuege:
        us = schluessel_setzen(a["umsaetze"])
        cur = con.execute("INSERT INTO bank_auszuege (datei, ablage, sha256, format, iban, von, bis, saldo_anfang, saldo_ende, saldo_datum, importiert, benutzer) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (dateiname, ablage, sha, a["format"], a["iban"], a["von"], a["bis"],
                                                              a["saldo_anfang"], a["saldo_ende"], a["saldo_datum"], jetzt(), wer))
        aid = cur.lastrowid
        neu = doppelt = 0
        for u in us:
            try:
                c = con.execute("INSERT INTO bank_umsaetze (auszug_id, iban, buchung, valuta, betrag, name, gegen_iban, zweck, e2e, referenz, schluessel, angelegt) "
                                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (aid, u["iban"], u["buchung"], u["valuta"], u["betrag"], u["name"], u["gegen_iban"],
                                                                     u["zweck"], u["e2e"], u["referenz"], u["schluessel"], jetzt()))
                erg["ids"].append(c.lastrowid)
                neu += 1
            except Exception as f:   # noqa: BLE001 – UNIQUE: schon aus einem früheren Auszug vorhanden
                if "UNIQUE" not in str(f):
                    raise
                doppelt += 1
        con.execute("UPDATE bank_auszuege SET neu=?, doppelt=? WHERE id=?", (neu, doppelt, aid))
        erg["auszuege"] += 1
        erg["neu"] += neu
        erg["doppelt"] += doppelt
    erg["sha256"] = sha
    erg["ablage"] = ablage
    return erg


# ---------------------------------------------------------------- Vorschläge
def _norm(t):
    return re.sub(r"\s+", " ", str(t or "").upper())


def _kommt_vor(nummer, text):
    """Rechnungs-/Belegnummer im Verwendungszweck (auch ohne Bindestrich oder mit Leerzeichen statt Bindestrich)."""
    n = _norm(nummer).strip()
    if len(n) < 4:
        return False
    for v in {n, n.replace("-", ""), n.replace("-", " "), n.replace("-", "/")}:
        if re.search(r"(?<![0-9A-Z])" + re.escape(v) + r"(?![0-9])", text):
            return True
    return False


def _woerter(t):
    return {w for w in re.findall(r"[A-ZÄÖÜß]{4,}", _norm(t)) if w not in ("GMBH", "HERR", "FRAU", "FIRMA", "UND", "SEPA", "GUTSCHRIFT", "UEBERWEISUNG", "ÜBERWEISUNG")}


def offene_posten(con):
    return zeilen(con.execute(
        "SELECT o.id, o.nummer, o.art, o.offen, o.betrag, o.faellig, IFNULL(o.mahnkosten,0) AS mahnkosten, o.kunde_id, o.beleg_id, "
        "k.kurzname, k.nachname AS name, k.firma, k.vorname FROM offene_posten o LEFT JOIN kunden k ON k.id=o.kunde_id WHERE o.offen > 0.004 ORDER BY o.faellig, o.id"))


def zahlungsauftraege(con, offen_nur=True):
    return zeilen(con.execute(
        "SELECT z.id, z.nummer, z.belegnr, z.betrag, z.skonto, z.skonto_bis, z.faellig, z.bezahlt, z.iban, l.kurzname AS lieferant, l.iban AS lief_iban "
        "FROM zahlungen z LEFT JOIN lieferanten l ON l.id=z.lieferant_id " + ("WHERE IFNULL(z.bezahlt,'')='' " if offen_nur else "") + "ORDER BY z.faellig, z.id"))


def vorschlag(u, ops, zas, alle_zas=None):
    """Vorschlag für einen Umsatz: {"sicher": bool, "grund": text, "ziele": [{"art", "id", "betrag", "text"}]} oder None."""
    text = _norm(f"{u['zweck']} {u['e2e']}")
    b = round(u["betrag"], 2)
    if b > 0:
        treffer = [o for o in ops if _kommt_vor(o["nummer"], text)]
        if treffer:
            summe = round(sum(o["offen"] + o["mahnkosten"] for o in treffer), 2)
            summe_ohne_mk = round(sum(o["offen"] for o in treffer), 2)
            if len(treffer) == 1:
                o = treffer[0]
                genau = abs(b - o["offen"]) < 0.01 or abs(b - (o["offen"] + o["mahnkosten"])) < 0.01
                return {"sicher": genau, "grund": "Rechnungsnummer im Verwendungszweck" + ("" if genau else f", Betrag weicht ab (offen {o['offen']:.2f})"),
                        "ziele": [{"art": "op", "id": o["id"], "betrag": b, "text": f"{o['art']} {o['nummer']} · {o['kurzname'] or ''}"}]}
            if abs(b - summe) < 0.01 or abs(b - summe_ohne_mk) < 0.01:
                mit_mk = abs(b - summe) < 0.01 and abs(b - summe_ohne_mk) >= 0.01
                return {"sicher": True, "grund": f"{len(treffer)} Rechnungsnummern im Verwendungszweck, Summe passt",
                        "ziele": [{"art": "op", "id": o["id"], "betrag": round(o["offen"] + (o["mahnkosten"] if mit_mk else 0), 2),
                                   "text": f"{o['art']} {o['nummer']} · {o['kurzname'] or ''}"} for o in treffer]}
            rest, ziele = b, []
            for o in treffer:   # der Reihe nach, älteste zuerst
                teil = round(min(rest, o["offen"]), 2) if o is not treffer[-1] else round(rest, 2)
                if teil > 0:
                    ziele.append({"art": "op", "id": o["id"], "betrag": teil, "text": f"{o['art']} {o['nummer']} · {o['kurzname'] or ''}"})
                rest = round(rest - teil, 2)
            return {"sicher": False, "grund": "Mehrere Rechnungsnummern, Summe weicht ab – bitte prüfen", "ziele": ziele}
        gleich = [o for o in ops if abs(o["offen"] - b) < 0.01]
        if len(gleich) == 1:
            o = gleich[0]
            kunde = _woerter(" ".join(str(o.get(k) or "") for k in ("kurzname", "name", "firma", "vorname")))
            name_passt = bool(kunde & _woerter(u["name"]))
            return {"sicher": name_passt, "grund": "Betrag und Name passen" if name_passt else "nur der Betrag passt – bitte prüfen",
                    "ziele": [{"art": "op", "id": o["id"], "betrag": b, "text": f"{o['art']} {o['nummer']} · {o['kurzname'] or ''}"}]}
        return None
    # Lastschrift / Überweisung: Zahlungsaufträge
    aus_betrag = -b
    e2e = _norm(u["e2e"])
    for z in (alle_zas if alle_zas is not None else zas):
        if e2e and _norm(z["nummer"]) == e2e:
            return {"sicher": True, "grund": "Zahlungsauftrag aus der SEPA-Datei (Ende-zu-Ende-Referenz)" + (" – war schon als bezahlt markiert" if z["bezahlt"] else ""),
                    "ziele": [{"art": "zahlung", "id": z["id"], "betrag": aus_betrag, "text": f"{z['nummer']} · {z['lieferant'] or ''} · {z['belegnr'] or ''}",
                               "schon_bezahlt": bool(z["bezahlt"])}]}

    def passt(z):
        return abs(aus_betrag - z["betrag"]) < 0.01 or (z["skonto"] and abs(aus_betrag - (z["betrag"] - z["skonto"])) < 0.01)
    kand = [z for z in zas if passt(z)]
    for z in kand:
        if (z["nummer"] and _kommt_vor(z["nummer"], text)) or (z["belegnr"] and _kommt_vor(z["belegnr"], text)):
            return {"sicher": True, "grund": "Betrag und Beleg-/Auftragsnummer passen",
                    "ziele": [{"art": "zahlung", "id": z["id"], "betrag": aus_betrag, "text": f"{z['nummer']} · {z['lieferant'] or ''} · {z['belegnr'] or ''}"}]}
    gi = _iban(u["gegen_iban"])
    mit_iban = [z for z in kand if gi and gi in (_iban(z["iban"]), _iban(z["lief_iban"]))]
    if len(mit_iban) == 1:
        z = mit_iban[0]
        return {"sicher": True, "grund": "Betrag und IBAN passen",
                "ziele": [{"art": "zahlung", "id": z["id"], "betrag": aus_betrag, "text": f"{z['nummer']} · {z['lieferant'] or ''} · {z['belegnr'] or ''}"}]}
    if len(kand) == 1:
        z = kand[0]
        return {"sicher": False, "grund": "nur der Betrag passt – bitte prüfen",
                "ziele": [{"art": "zahlung", "id": z["id"], "betrag": aus_betrag, "text": f"{z['nummer']} · {z['lieferant'] or ''} · {z['belegnr'] or ''}"}]}
    return None


def liste(con, q):
    status = q.get("status") or "offen"
    sql, par = "SELECT * FROM bank_umsaetze WHERE 1=1", []
    if status != "alle":
        sql += " AND status=?"
        par.append(status)
    if q.get("von"):
        sql += " AND buchung>=?"
        par.append(q["von"])
    if q.get("bis"):
        sql += " AND buchung<=?"
        par.append(q["bis"])
    if q.get("q"):
        for w in q["q"].split()[:5]:
            sql += " AND (name LIKE ? OR zweck LIKE ? OR CAST(betrag AS TEXT) LIKE ?)"
            par += [f"%{w}%"] * 3
    sql += " ORDER BY buchung DESC, id DESC LIMIT 1000"
    us = zeilen(con.execute(sql, par))
    ops, zas = offene_posten(con), zahlungsauftraege(con)
    alle_zas = None
    for u in us:
        u["ziel"] = json.loads(u["ziel"] or "[]")
        if u["status"] == "offen":
            if alle_zas is None and any(x["betrag"] < 0 for x in us):
                alle_zas = zahlungsauftraege(con, offen_nur=False)
            u["vorschlag"] = vorschlag(u, ops, zas, alle_zas)
    kontostand = kontostand_lesen(con)
    zaehler = {r["status"]: r["n"] for r in con.execute("SELECT status, COUNT(*) AS n FROM bank_umsaetze GROUP BY status")}
    return {"umsaetze": us, "kontostand": kontostand, "anzahl": zaehler,
            "auszuege": zeilen(con.execute("SELECT id, datei, format, iban, von, bis, saldo_ende, saldo_datum, neu, doppelt, importiert, benutzer "
                                           "FROM bank_auszuege ORDER BY id DESC LIMIT 30"))}


def kontostand_lesen(con):
    r = con.execute("SELECT saldo_ende, saldo_datum, iban FROM bank_auszuege WHERE saldo_ende IS NOT NULL AND saldo_datum<>'' "
                    "ORDER BY saldo_datum DESC, id DESC LIMIT 1").fetchone()
    return dict(r) if r else None


def kandidaten(con):
    """Für die Zuordnung von Hand: alle offenen Posten und offenen Zahlungsaufträge."""
    return {"op": [{"id": o["id"], "text": f"{o['art']} {o['nummer']} · {o['kurzname'] or ''}", "offen": o["offen"], "faellig": o["faellig"]} for o in offene_posten(con)],
            "zahlung": [{"id": z["id"], "text": f"{z['nummer']} · {z['lieferant'] or ''} · {z['belegnr'] or ''}", "offen": z["betrag"], "faellig": z["faellig"]}
                        for z in zahlungsauftraege(con)]}
