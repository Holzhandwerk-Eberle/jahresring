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
import base64

import benutzer
from kern import ApiFehler, de, de_datum, jl, zahl

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
CREATE TABLE IF NOT EXISTS bank_regeln (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suchtext TEXT NOT NULL, feld TEXT DEFAULT 'beide', richtung TEXT DEFAULT '', konto INTEGER NOT NULL,
    notiz TEXT DEFAULT '', angelegt TEXT, von TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_bank_umsaetze_buchung ON bank_umsaetze(buchung);
CREATE INDEX IF NOT EXISTS ix_bank_umsaetze_status ON bank_umsaetze(status);
"""

# von app.py gesetzt: prot, op_zahlung_buchen, zahlungseingang_loeschen, ich_login, daten, skr (fn con → "03"/"04")
HILFE = {}
MAX_DATEI = 50 * 1024 * 1024
MAX_ENTPACKT = 200 * 1024 * 1024


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def schema(con):
    con.executescript(SCHEMA)
    spalten = {r[1] for r in con.execute("PRAGMA table_info(bank_umsaetze)")}
    if "konto" not in spalten:
        con.execute("ALTER TABLE bank_umsaetze ADD COLUMN konto INTEGER")


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


def dateien(con, grenze=30):
    """Eingelesene Dateien (eine Datei kann mehrere Auszüge enthalten) mit Zeitraum, Zahl der Umsätze und der schon gebuchten."""
    gruppen = {}
    for a in zeilen(con.execute("SELECT * FROM bank_auszuege ORDER BY id DESC")):
        gruppen.setdefault(a["ablage"] or f"#{a['id']}", []).append(a)
    aus = []
    for g in list(gruppen.values())[:grenze]:
        ids = [a["id"] for a in g]
        marken = ",".join("?" * len(ids))
        n = con.execute(f"SELECT COUNT(*) AS n, SUM(CASE WHEN status<>'offen' THEN 1 ELSE 0 END) AS g FROM bank_umsaetze WHERE auszug_id IN ({marken})", ids).fetchone()
        saldo = max((a for a in g if a["saldo_ende"] is not None and a["saldo_datum"]), key=lambda a: (a["saldo_datum"], a["id"]), default=None)
        aus.append({"id": min(ids), "datei": g[0]["datei"], "format": g[0]["format"], "importiert": g[0]["importiert"], "benutzer": g[0]["benutzer"],
                    "von": min((a["von"] for a in g if a["von"]), default=""), "bis": max((a["bis"] for a in g if a["bis"]), default=""),
                    "neu": sum(a["neu"] or 0 for a in g), "doppelt": sum(a["doppelt"] or 0 for a in g), "auszuege": len(g),
                    "saldo_ende": saldo["saldo_ende"] if saldo else None, "umsaetze": n["n"] or 0, "gebucht": n["g"] or 0})
    return aus


def _nachtragen(con, ordner):
    """Nach dem Entfernen einer Datei: Umsätze, die auch in einer anderen, noch vorhandenen Datei stehen (dort als „schon vorhanden“
    gezählt), aus dieser wieder anlegen – sonst würden sie fehlen, obwohl ihr Auszug noch eingelesen ist."""
    n = 0
    for r in con.execute("SELECT ablage, MIN(datei) AS datei FROM bank_auszuege WHERE ablage<>'' GROUP BY ablage HAVING SUM(doppelt)>0").fetchall():
        try:
            with open(os.path.join(ordner, r["ablage"]), "rb") as f:
                auszuege = camt_lesen(f.read(), r["datei"])
        except Exception:   # noqa: BLE001 – Datei fehlt oder ist nicht mehr lesbar: dann bleibt es beim jetzigen Stand
            continue
        ids = [x["id"] for x in con.execute("SELECT id FROM bank_auszuege WHERE ablage=? ORDER BY id", (r["ablage"],))]
        for aid, a in zip(ids, auszuege):
            dazu = 0
            for u in schluessel_setzen(a["umsaetze"]):
                c = con.execute("INSERT OR IGNORE INTO bank_umsaetze (auszug_id, iban, buchung, valuta, betrag, name, gegen_iban, zweck, e2e, referenz, schluessel, angelegt) "
                                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (aid, u["iban"], u["buchung"], u["valuta"], u["betrag"], u["name"], u["gegen_iban"],
                                                                     u["zweck"], u["e2e"], u["referenz"], u["schluessel"], jetzt()))
                dazu += c.rowcount
            if dazu:
                con.execute("UPDATE bank_auszuege SET neu=neu+?, doppelt=MAX(0, doppelt-?) WHERE id=?", (dazu, dazu, aid))
                n += dazu
    return n


def datei_entfernen(con, aid, ordner):
    """Eine eingelesene Datei samt ihren Umsätzen wieder entfernen (z. B. falsches Konto, falscher Zeitraum). Geht nur, solange
    keiner ihrer Umsätze zugeordnet oder auf ein Konto gebucht ist – gebuchte Zahlungen bleiben so immer nachvollziehbar."""
    a = con.execute("SELECT * FROM bank_auszuege WHERE id=?", (aid,)).fetchone()
    if not a:
        raise ApiFehler("Kontoauszug nicht gefunden.", 404)
    ids = [r["id"] for r in con.execute("SELECT id FROM bank_auszuege WHERE ablage=?", (a["ablage"],))] if a["ablage"] else [aid]
    marken = ",".join("?" * len(ids))
    gebucht = con.execute(f"SELECT COUNT(*) FROM bank_umsaetze WHERE auszug_id IN ({marken}) AND status<>'offen'", ids).fetchone()[0]
    if gebucht:
        raise ApiFehler(f"{gebucht} {'Umsatz' if gebucht == 1 else 'Umsätze'} aus dieser Datei {'ist' if gebucht == 1 else 'sind'} schon zugeordnet oder auf ein Konto gebucht. "
                        "Bitte dort zuerst „Zuordnung lösen“ bzw. „Zurückholen“ wählen – danach lässt sich der Kontoauszug entfernen.", 409)
    n = con.execute(f"DELETE FROM bank_umsaetze WHERE auszug_id IN ({marken})", ids).rowcount
    con.execute(f"DELETE FROM bank_auszuege WHERE id IN ({marken})", ids)
    if a["ablage"]:
        try:
            os.remove(os.path.join(ordner, a["ablage"]))
        except OSError:
            pass
    wieder = _nachtragen(con, ordner)
    HILFE["prot"](con, "bank_entfernt", str(a["datei"] or "")[:80], f"Kontoauszug entfernt: {a['datei'] or ''} · {n} Umsätze gelöscht (keiner war zugeordnet)"
         + (f", {wieder} aus anderen eingelesenen Auszügen wieder angelegt" if wieder else ""),
         {"sha256": a["sha256"], "ablage": a["ablage"], "umsaetze": n, "wieder_angelegt": wieder, "eingelesen": a["importiert"]})
    return {"ok": True, "umsaetze": n, "wieder_angelegt": wieder}


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
    regeln = regeln_liste(con)
    namen = kontonamen(con)
    for u in us:
        u["ziel"] = json.loads(u["ziel"] or "[]")
        if u["konto"]:
            u["konto_text"] = f"{u['konto']} {namen.get(u['konto'], '')}".strip()
        if u["status"] == "offen":
            if alle_zas is None and any(x["betrag"] < 0 for x in us):
                alle_zas = zahlungsauftraege(con, offen_nur=False)
            u["vorschlag"] = vorschlag(u, ops, zas, alle_zas)
            if not u["vorschlag"]:
                r = regel_fuer(u, regeln)
                if r:
                    u["vorschlag"] = {"sicher": True, "grund": f"Regel: „{r['suchtext']}“ → Konto", "ziele": [], "konto": r["konto"],
                                      "konto_text": f"{r['konto']} {namen.get(r['konto'], '')}".strip(), "notiz": r["notiz"]}
    kontostand = kontostand_lesen(con)
    zaehler = {r["status"]: r["n"] for r in con.execute("SELECT status, COUNT(*) AS n FROM bank_umsaetze GROUP BY status")}
    return {"umsaetze": us, "kontostand": kontostand, "anzahl": zaehler, "dateien": dateien(con),
            "auszuege": zeilen(con.execute("SELECT id, datei, format, iban, von, bis, saldo_ende, saldo_datum, neu, doppelt, importiert, benutzer "
                                           "FROM bank_auszuege ORDER BY id DESC LIMIT 30"))}


def kontonamen(con):
    skr = HILFE["skr"](con) if HILFE.get("skr") else "03"
    try:
        return {r["nummer"]: r["bezeichnung"] for r in con.execute("SELECT nummer, bezeichnung FROM konten WHERE skr=?", (skr,))}
    except Exception:   # noqa: BLE001 – Kontenplan noch nicht angelegt
        return {}


def regeln_liste(con):
    return zeilen(con.execute("SELECT * FROM bank_regeln ORDER BY suchtext COLLATE NOCASE"))


def regel_fuer(u, regeln):
    """Erste Regel, deren Suchtext im Namen bzw. Verwendungszweck vorkommt (Groß-/Kleinschreibung egal) und deren Richtung passt."""
    name, zweck = _norm(u["name"]), _norm(u["zweck"])
    for r in regeln:
        t = _norm(r["suchtext"]).strip()
        if not t:
            continue
        if r["richtung"] == "+" and u["betrag"] < 0 or r["richtung"] == "-" and u["betrag"] > 0:
            continue
        feld = r["feld"] or "beide"
        if (feld in ("name", "beide") and t in name) or (feld in ("zweck", "beide") and t in zweck):
            return r
    return None


def kontostand_lesen(con):
    r = con.execute("SELECT saldo_ende, saldo_datum, iban FROM bank_auszuege WHERE saldo_ende IS NOT NULL AND saldo_datum<>'' "
                    "ORDER BY saldo_datum DESC, id DESC LIMIT 1").fetchone()
    return dict(r) if r else None


def kandidaten(con):
    """Für die Zuordnung von Hand: alle offenen Posten und offenen Zahlungsaufträge."""
    return {"op": [{"id": o["id"], "text": f"{o['art']} {o['nummer']} · {o['kurzname'] or ''}", "offen": o["offen"], "faellig": o["faellig"]} for o in offene_posten(con)],
            "zahlung": [{"id": z["id"], "text": f"{z['nummer']} · {z['lieferant'] or ''} · {z['belegnr'] or ''}", "offen": z["betrag"], "faellig": z["faellig"]}
                        for z in zahlungsauftraege(con)]}


# ---------------------------------------------------------------- Zuordnen, Lösen, Schnittstelle
def eingang_entfernt(con, zid):
    """Ein aus dem Kontoauszug gebuchter Zahlungseingang wurde von Hand gelöscht: den Umsatz wieder zur Zuordnung anbieten."""
    for r in con.execute("SELECT id, ziel FROM bank_umsaetze WHERE status='zugeordnet' AND ziel LIKE ?", (f"%{zid}%",)).fetchall():
        ziele = jl(r["ziel"], [])
        geaendert = False
        for t in ziele:
            if t.get("art") == "op" and zid in (t.get("eingaenge") or []):
                t["eingaenge"] = [i for i in t["eingaenge"] if i != zid]
                geaendert = True
        if not geaendert:
            continue
        rest = [t for t in ziele if t.get("art") == "zahlung" or t.get("eingaenge")]
        if rest:
            con.execute("UPDATE bank_umsaetze SET ziel=? WHERE id=?", (json.dumps(ziele, ensure_ascii=False), r["id"]))
        else:
            con.execute("UPDATE bank_umsaetze SET status='offen', ziel='[]', zugeordnet='', von='' WHERE id=?", (r["id"],))


def zuordnen(con, uid, ziele):
    u = con.execute("SELECT * FROM bank_umsaetze WHERE id=?", (uid,)).fetchone()
    if not u:
        raise ApiFehler("Umsatz nicht gefunden.", 404)
    if u["status"] != "offen":
        raise ApiFehler("Dieser Umsatz ist schon zugeordnet oder erledigt.", 409)
    ziele = [t for t in (ziele or []) if isinstance(t, dict) and t.get("art") in ("op", "zahlung") and str(t.get("id") or "").isdigit()]
    if not ziele:
        raise ApiFehler("Bitte einen offenen Posten oder Zahlungsauftrag wählen.")
    gutschrift = u["betrag"] > 0
    if any((t["art"] == "op") != gutschrift for t in ziele):
        raise ApiFehler("Gutschriften gehören zu offenen Posten (Kundenzahlungen), Abbuchungen zu Zahlungsaufträgen.")
    erg, texte = [], []
    if gutschrift:
        summe = round(sum(zahl(t.get("betrag"), float) for t in ziele), 2)
        if abs(summe - round(u["betrag"], 2)) > 0.009:
            raise ApiFehler(f"Die aufgeteilten Beträge ({de(summe)} €) ergeben nicht den Umsatz ({de(u['betrag'])} €).")
        for t in ziele:
            b = round(zahl(t.get("betrag"), float), 2)
            if b <= 0:
                continue
            op = con.execute("SELECT nummer FROM offene_posten WHERE id=?", (int(t["id"]),)).fetchone()
            ids = HILFE["op_zahlung_buchen"](con, int(t["id"]), {"betrag": b, "datum": u["buchung"] or date.today().isoformat(), "art": "Überweisung",
                                                        "bemerkung": f"Kontoauszug {de_datum(u['buchung'])}: {u['name']}"[:200]})
            erg.append({"art": "op", "id": int(t["id"]), "betrag": b, "eingaenge": ids, "nummer": op["nummer"] if op else ""})
            texte.append(f"{op['nummer'] if op else t['id']} {de(b)} €")
    else:
        if len(ziele) != 1:
            raise ApiFehler("Eine Abbuchung gehört zu genau einem Zahlungsauftrag.")
        t = ziele[0]
        z = con.execute("SELECT id, nummer, bezahlt, betrag FROM zahlungen WHERE id=?", (int(t["id"]),)).fetchone()
        if not z:
            raise ApiFehler("Zahlungsauftrag nicht gefunden.", 404)
        gesetzt = not z["bezahlt"]
        if gesetzt:
            tag = u["buchung"] or date.today().isoformat()
            con.execute("UPDATE zahlungen SET bezahlt=?, geaendert=? WHERE id=?", (tag, jetzt(), z["id"]))
            HILFE["prot"](con, "zahlungsauftrag_bezahlt", z["nummer"], f"Als bezahlt am {de_datum(tag)} markiert (Kontoauszug, damit gesperrt): {z['nummer']}",
                 {"nummern": [z["nummer"]], "bezahlt": tag, "bank_umsatz": uid})
        erg.append({"art": "zahlung", "id": z["id"], "betrag": -u["betrag"], "gesetzt": gesetzt, "nummer": z["nummer"]})
        texte.append(z["nummer"])
    con.execute("UPDATE bank_umsaetze SET status='zugeordnet', ziel=?, zugeordnet=?, von=? WHERE id=?",
                (json.dumps(erg, ensure_ascii=False), jetzt(), HILFE["ich_login"](), uid))
    HILFE["prot"](con, "bank_zuordnung", ", ".join(texte)[:80], f"Kontoumsatz {de_datum(u['buchung'])} {de(u['betrag'])} € ({u['name']}) zugeordnet: {', '.join(texte)}",
         {"umsatz": uid, "schluessel": u["schluessel"], "ziele": erg})
    return erg


def loesen(con, uid):
    u = con.execute("SELECT * FROM bank_umsaetze WHERE id=?", (uid,)).fetchone()
    if not u:
        raise ApiFehler("Umsatz nicht gefunden.", 404)
    ziele = jl(u["ziel"], [])
    if any(t.get("art") == "zahlung" and t.get("gesetzt") for t in ziele) and not benutzer.ist_inhaber():
        raise ApiFehler("„Bezahlt“ bei einem Zahlungsauftrag zurücknehmen kann nur der Inhaber.", 403)
    for t in ziele:
        if t.get("art") == "op":
            for zid in t.get("eingaenge") or []:
                HILFE["zahlungseingang_loeschen"](con, zid, aus_bank=True)
        elif t.get("art") == "zahlung" and t.get("gesetzt"):
            z = con.execute("SELECT nummer, bezahlt, betrag FROM zahlungen WHERE id=?", (t["id"],)).fetchone()
            if z and z["bezahlt"]:
                con.execute("UPDATE zahlungen SET bezahlt='', geaendert=? WHERE id=?", (jetzt(), t["id"]))
                HILFE["prot"](con, "zahlungsauftrag_geoeffnet", z["nummer"], f"„Bezahlt“ zurückgenommen (Zuordnung zum Kontoauszug gelöst): {z['nummer']}",
                     {"bezahlt_alt": z["bezahlt"], "betrag": z["betrag"], "bank_umsatz": uid})
    con.execute("UPDATE bank_umsaetze SET status='offen', ziel='[]', konto=NULL, notiz='', zugeordnet='', von='' WHERE id=?", (uid,))
    if u["status"] == "zugeordnet":
        HILFE["prot"](con, "bank_loesung", str(uid), f"Zuordnung des Kontoumsatzes {de_datum(u['buchung'])} {de(u['betrag'])} € ({u['name']}) gelöst", {"umsatz": uid, "ziele": ziele})
    return {"ok": True}


def konto_setzen(con, uid, konto, notiz="", regel=None):
    """Umsatz ohne Rechnung: Sachkonto aus dem Kontenplan (oder keins) und Notiz; auf Wunsch eine Regel für künftige Umsätze."""
    u = con.execute("SELECT * FROM bank_umsaetze WHERE id=?", (uid,)).fetchone()
    if not u:
        raise ApiFehler("Umsatz nicht gefunden.", 404)
    if u["status"] == "zugeordnet":
        raise ApiFehler("Bitte zuerst die Zuordnung lösen.", 409)
    nr = None
    if str(konto or "").strip():
        if not str(konto).strip().isdigit():
            raise ApiFehler("Bitte ein Konto aus dem Kontenplan wählen.")
        nr = int(str(konto).strip())
        skr = HILFE["skr"](con) if HILFE.get("skr") else "03"
        if not con.execute("SELECT 1 FROM konten WHERE skr=? AND nummer=? AND aktiv=1", (skr, nr)).fetchone():
            raise ApiFehler(f"Das Konto {nr} steht nicht im Kontenplan – bitte zuerst anlegen.")
    con.execute("UPDATE bank_umsaetze SET status='ignoriert', konto=?, notiz=?, zugeordnet=?, von=? WHERE id=?",
                (nr, str(notiz or "")[:200], jetzt(), HILFE["ich_login"](), uid))
    if regel and nr and str(regel.get("suchtext") or "").strip():
        feld = regel.get("feld") if regel.get("feld") in ("name", "zweck", "beide") else "beide"
        richtung = "+" if u["betrag"] > 0 else "-"
        text = str(regel["suchtext"]).strip()[:80]
        alt = con.execute("SELECT id FROM bank_regeln WHERE suchtext=? AND feld=? AND richtung=?", (text, feld, richtung)).fetchone()
        if alt:
            con.execute("UPDATE bank_regeln SET konto=?, notiz=? WHERE id=?", (nr, str(notiz or "")[:200], alt["id"]))
        else:
            con.execute("INSERT INTO bank_regeln (suchtext, feld, richtung, konto, notiz, angelegt, von) VALUES (?,?,?,?,?,?,?)",
                        (text, feld, richtung, nr, str(notiz or "")[:200], jetzt(), HILFE["ich_login"]()))
    return {"ok": True}


def web_api(con, methode, teile, q, d):
    sub = teile[1] if len(teile) > 1 else None
    uid = int(sub) if sub and sub.isdigit() else None
    aktion = teile[2] if len(teile) > 2 else None
    if methode == "GET" and sub is None:
        return liste(con, q)
    if methode == "GET" and sub == "kandidaten":
        return kandidaten(con)
    if methode == "POST" and sub == "einlesen":
        if not d.get("daten"):
            raise ApiFehler("Keine Datei übergeben.")
        roh = base64.b64decode(d["daten"])
        erg = einlesen(con, roh, str(d.get("dateiname") or "kontoauszug.xml")[:120], os.path.join(HILFE["daten"], "bank"), HILFE["ich_login"]())
        HILFE["prot"](con, "bank_import", str(d.get("dateiname") or "")[:80], f"Kontoauszug eingelesen: {d.get('dateiname') or ''} · {erg['neu']} neue Umsätze"
             + (f", {erg['doppelt']} schon vorhanden" if erg["doppelt"] else ""), {"sha256": erg["sha256"], "ablage": erg["ablage"], "neu": erg["neu"], "doppelt": erg["doppelt"]})
        return erg
    if methode == "DELETE" and sub == "auszuege" and aktion and aktion.isdigit():
        if not benutzer.ist_inhaber():
            raise ApiFehler("Einen eingelesenen Kontoauszug entfernt nur der Inhaber.", 403)
        return datei_entfernen(con, int(aktion), os.path.join(HILFE["daten"], "bank"))
    if methode == "POST" and sub == "sichere":
        # alle sicheren Vorschläge auf einmal übernehmen
        daten_ = liste(con, {"status": "offen"})
        n, fehler = 0, []
        for u in daten_["umsaetze"]:
            v = u.get("vorschlag")
            if v and v["sicher"]:
                try:
                    if v.get("konto"):
                        konto_setzen(con, u["id"], v["konto"], v.get("notiz") or "")
                    else:
                        zuordnen(con, u["id"], v["ziele"])
                    n += 1
                except ApiFehler as f:
                    fehler.append(f"{de_datum(u['buchung'])} {u['name']}: {f}")
        return {"zugeordnet": n, "fehler": fehler}
    if methode == "POST" and uid and aktion == "zuordnen":
        return {"ziele": zuordnen(con, uid, d.get("ziele"))}
    if methode == "POST" and uid and aktion == "loesen":
        return loesen(con, uid)
    if methode == "POST" and uid and aktion in ("ignorieren", "konto"):
        return konto_setzen(con, uid, d.get("konto"), d.get("notiz"), d.get("regel"))
    if methode == "GET" and sub == "regeln":
        namen = kontonamen(con)
        return [dict(r, konto_text=f"{r['konto']} {namen.get(r['konto'], '')}".strip()) for r in regeln_liste(con)]
    if methode == "DELETE" and sub == "regeln" and aktion and aktion.isdigit():
        con.execute("DELETE FROM bank_regeln WHERE id=?", (int(aktion),))
        return {"ok": True}
    raise ApiFehler("Unbekannte Anfrage", 404)
