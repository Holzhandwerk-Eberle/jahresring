"""Jahresring – Einkaufspreise von Lieferanten einlesen (Datanorm 4/5 oder CSV/Excel-Preisliste).

Ablauf: Datei lesen → Artikel mit dem Materialstamm abgleichen (Bestellnummer des Lieferanten oder EAN) → Vorschau mit
altem und neuem Preis → nur die bestätigten Preise werden übernommen (mit Datum „Preis vom“; Verkaufspreise mit
Aufschlag werden wie beim Ändern von Hand nachgeführt). Der Materialstamm wird nie ungefragt verändert.
"""
import hashlib
import re
import threading
import time
from datetime import date

import kundenimport
import material

MAX_DATEI = 60 * 1024 * 1024
EINHEITEN = {"STK": "Stk.", "ST": "Stk.", "STÜCK": "Stk.", "STUECK": "Stk.", "PCE": "Stk.", "C62": "Stk.", "M2": "m²", "QM": "m²", "MTK": "m²",
             "M²": "m²", "M3": "m³", "CBM": "m³", "MTQ": "m³", "M³": "m³", "M": "lfm.", "LFM": "lfm.", "MTR": "lfm.", "LM": "lfm.",
             "PAA": "Paar", "PR": "Paar", "PAAR": "Paar", "SET": "Satz", "SATZ": "Satz", "L": "Liter", "LTR": "Liter", "LITER": "Liter",
             "KG": "kg", "KGM": "kg", "DOSE": "Dose", "ROLLE": "Rolle", "RO": "Rolle", "PAK": "Packung", "PCK": "Packung", "PAC": "Packung"}


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def _einheit(t):
    t = str(t or "").strip()
    return EINHEITEN.get(t.upper().replace(".", ""), t)


def _zahl(t):
    t = str(t or "").strip().replace(" ", "").replace("€", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _nr(t):
    return re.sub(r"[\s.\-/]", "", str(t or "")).upper().lstrip("0")


# ---------------------------------------------------------------- Datanorm
def datanorm_lesen(text):
    zeilen = [z for z in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if z.strip()]
    version5 = any(re.match(r"V;0?5", z) for z in zeilen[:5])
    artikel, ean, p_saetze = {}, {}, 0
    for z in zeilen:
        f = z.split(";")
        satz = f[0].strip().upper()
        if satz == "A" and len(f) > 9:
            nr = f[2].strip()
            if not nr:
                continue
            pe_feld = f[7].strip()
            if version5:
                pe = int(pe_feld) if pe_feld.isdigit() and int(pe_feld) > 0 else 1
            else:
                pe = {"0": 1, "1": 10, "2": 100, "3": 1000}.get(pe_feld, 1)
            roh = f[9].strip()
            if not roh:
                continue
            if re.fullmatch(r"\d+", roh) and not version5:
                preis = int(roh) / 100   # Datanorm 4: Preis in Cent ohne Komma
            else:
                preis = _zahl(roh)
                if preis is None:
                    continue
            artikel[nr] = {"artnr": nr, "text": " ".join(x.strip() for x in f[4:6] if x.strip())[:120], "preis": round(preis / pe, 4),
                           "einheit": _einheit(f[8]), "netto": f[6].strip() == "2", "rabattgruppe": f[10].strip() if len(f) > 10 else "",
                           "warengruppe": f[11].strip() if len(f) > 11 else ""}
        elif satz == "B" and len(f) > 3:
            for x in f[3:]:
                x = x.strip()
                if re.fullmatch(r"\d{8}|\d{12,14}", x):
                    ean[f[2].strip()] = x
                    break
        elif satz == "P":
            p_saetze += 1
    for nr, e in ean.items():
        if nr in artikel:
            artikel[nr]["ean"] = e
    hinweis = ""
    if p_saetze and not artikel:
        hinweis = ("Die Datei enthält nur Preisänderungssätze (P-Sätze). Bitte beim Lieferanten die vollständige Datanorm-Datei mit "
                   "Artikelsätzen (A-Sätze) anfordern.")
    elif p_saetze:
        hinweis = f"{p_saetze} Preisänderungssätze (P-Sätze) wurden nicht ausgewertet; maßgeblich sind die Artikelsätze."
    return list(artikel.values()), hinweis


def datanorm_text(roh):
    """Datanorm 4 ist meist im DOS-Zeichensatz (CP850/437) geschrieben, neuere Dateien in ANSI oder UTF-8: nach den Umlaut-Bytes entscheiden."""
    try:
        return roh.decode("utf-8")
    except UnicodeDecodeError:
        pass
    dos = sum(roh.count(bytes([b])) for b in (0x81, 0x84, 0x94, 0x8E, 0x99, 0x9A, 0xE1))
    ansi = sum(roh.count(bytes([b])) for b in (0xFC, 0xE4, 0xF6, 0xC4, 0xD6, 0xDC, 0xDF))
    return roh.decode("cp850" if dos > ansi else "cp1252", errors="replace")


# ---------------------------------------------------------------- CSV / Excel
SPALTEN = {
    "artnr": ("artikelnummer", "artikelnr", "artnr", "art nr", "bestellnummer", "bestellnr", "best nr", "artikel", "materialnummer", "sku", "nummer"),
    "ean": ("ean", "gtin", "ean13", "ean code", "barcode"),
    "text": ("bezeichnung", "artikelbezeichnung", "kurztext", "beschreibung", "text", "name"),
    "preis": ("netto ek", "nettopreis", "netto", "ek", "einkaufspreis", "ek preis", "preis netto", "ihr preis", "preis", "listenpreis", "vk"),
    "einheit": ("einheit", "me", "mengeneinheit", "verkaufseinheit", "unit"),
    "pe": ("preiseinheit", "pe", "preis je", "pro"),
    "gruppe": ("warengruppe", "artikelgruppe", "produktgruppe", "kategorie", "gruppe"),
}


def spalten_vorschlag(kopf):
    k = [re.sub(r"[\s_./-]+", " ", (x or "").strip().lower()) for x in kopf]
    zu = {}
    for feld, namen in SPALTEN.items():
        for n in namen:
            i = next((i for i, x in enumerate(k) if x == n and i not in zu.values()), None)
            if i is None:
                i = next((i for i, x in enumerate(k) if n in x and i not in zu.values()), None)
            if i is not None:
                zu[feld] = i
                break
    return zu


def tabelle_artikel(zeilen, zuordnung):
    kopf, daten = zeilen[0], zeilen[1:]
    zu = {k: int(v) for k, v in (zuordnung or {}).items() if str(v).lstrip("-").isdigit() and int(v) >= 0} or spalten_vorschlag(kopf)
    if "preis" not in zu or not ("artnr" in zu or "ean" in zu):
        raise Fehler("In der Tabelle wurden die Spalten für Artikelnummer (oder EAN) und Preis nicht gefunden – bitte unten zuordnen.")
    aus = []
    for r in daten:
        def w(f):
            return r[zu[f]].strip() if f in zu and zu[f] < len(r) else ""
        preis = _zahl(w("preis"))
        if preis is None or not (w("artnr") or w("ean")):
            continue
        pe = _zahl(w("pe")) or 1
        aus.append({"artnr": w("artnr"), "ean": re.sub(r"\D", "", w("ean")), "text": w("text")[:120], "preis": round(preis / (pe or 1), 4),
                    "einheit": _einheit(w("einheit")), "netto": True, "warengruppe": w("gruppe")[:40]})
    return aus, zu


def lesen(roh, dateiname, zuordnung=None):
    if len(roh) > MAX_DATEI:
        raise Fehler("Die Datei ist zu groß (höchstens 60 MB).")
    n = (dateiname or "").lower()
    text = None if (n.endswith(".xlsx") or roh[:2] == b"PK") else kundenimport.dekodieren(roh)
    if text is not None and (re.search(r"datanorm|\.00\d$", n) or re.match(r"\s*V[ ;]", text[:200])) and re.search(r"(?m)^A;", text):
        art, hinweis = datanorm_lesen(datanorm_text(roh) or text)
        return {"format": "Datanorm", "artikel": art, "hinweis": hinweis, "kopf": [], "zuordnung": {}}
    try:
        zeilen = kundenimport.tabelle_lesen(roh, dateiname)
    except kundenimport.ImportFehler as f:
        raise Fehler(str(f))
    art, zu = tabelle_artikel(zeilen, zuordnung)
    return {"format": "Tabelle", "artikel": art, "hinweis": "", "kopf": zeilen[0], "zuordnung": zu}


# ---------------------------------------------------------------- Abgleich mit dem Materialstamm
def abgleich(con, lieferant_id, artikel, rabatt=0.0, nur_lieferant=True):
    sql = "SELECT id, nummer, bezeichnung, bestellnr, ean, ek_preis, einheit, preis_vom, lieferant_id, aktiv FROM material WHERE aktiv=1"
    par = []
    if lieferant_id and nur_lieferant:
        sql += " AND lieferant_id=?"
        par.append(lieferant_id)
    mats = [dict(r) for r in con.execute(sql, par)]
    je_nr, je_ean = {}, {}
    for a in artikel:
        if a.get("artnr"):
            je_nr.setdefault(_nr(a["artnr"]), a)
        if a.get("ean"):
            je_ean.setdefault(a["ean"].lstrip("0"), a)
    treffer = []
    for m in mats:
        a = je_nr.get(_nr(m["bestellnr"])) if (m["bestellnr"] or "").strip() else None
        ueber = "Bestellnummer"
        if a is None and (m.get("ean") or "").strip():
            a = je_ean.get(re.sub(r"\D", "", m["ean"]).lstrip("0"))
            ueber = "EAN"
        if a is None:
            continue
        neu = a["preis"] if a.get("netto", True) else a["preis"] * (1 - float(rabatt or 0) / 100)
        neu = round(neu, 4)
        alt = float(m["ek_preis"] or 0)
        diff = ((neu - alt) / alt * 100) if alt else None
        einheit_ok = not a.get("einheit") or not m["einheit"] or a["einheit"] == m["einheit"]
        auffaellig = (diff is not None and abs(diff) > 30) or not einheit_ok or neu <= 0
        treffer.append({"material_id": m["id"], "nummer": m["nummer"], "bezeichnung": (m["bezeichnung"] or "").split("\n")[0][:80],
                        "bestellnr": m["bestellnr"], "ueber": ueber, "alt": alt, "neu": neu, "diff": None if diff is None else round(diff, 1),
                        "einheit": m["einheit"], "einheit_datei": a.get("einheit") or "", "einheit_ok": einheit_ok, "preis_vom": m["preis_vom"],
                        "text_datei": a.get("text") or "", "gleich": abs(neu - alt) < 0.00005, "vorschlag": not auffaellig and abs(neu - alt) >= 0.00005})
    treffer.sort(key=lambda t: (t["gleich"], not t["vorschlag"], t["nummer"]))
    return {"treffer": treffer, "artikel": len(artikel), "materialien": len(mats),
            "ohne_treffer": sum(1 for m in mats if not any(t["material_id"] == m["id"] for t in treffer))}


def uebernehmen(con, posten, datum):
    n = 0
    geaendert = []
    for p in posten or []:
        try:
            mid, neu = int(p["material_id"]), round(float(p["neu"]), 4)
        except (KeyError, TypeError, ValueError):
            continue
        if neu <= 0:
            continue
        m = material.laden(con, mid)
        if abs((m["ek_preis"] or 0) - neu) < 0.00005:
            continue
        material.aendern(con, mid, {"ek_preis": neu, "preis_vom": datum})
        geaendert.append({"nummer": m["nummer"], "alt": m["ek_preis"], "neu": neu})
        n += 1
    return {"geaendert": n, "liste": geaendert}



# ---------------------------------------------------------------- Zwischenspeicher der zuletzt gelesenen Dateien
# Große Datanorm-Dateien (zehntausende Artikel) werden nur einmal hochgeladen; Suche und Anlegen arbeiten mit dem Schlüssel.
_SPEICHER = {}
_SPERRE = threading.Lock()


def merken(roh, erg):
    schluessel = hashlib.sha256(roh).hexdigest()[:32]
    with _SPERRE:
        _SPEICHER[schluessel] = (time.time(), erg)
        for k in sorted(_SPEICHER, key=lambda k: _SPEICHER[k][0])[:-3]:
            _SPEICHER.pop(k, None)
    return schluessel


def gemerkt(schluessel):
    with _SPERRE:
        e = _SPEICHER.get(str(schluessel or ""))
    if not e:
        raise Fehler("Die Preisdatei ist nicht mehr im Zwischenspeicher – bitte erneut wählen.", 410)
    return e[1]


# ---------------------------------------------------------------- Neue Artikel aus der Datei anlegen
def _bekannt(con):
    nr, ean = set(), set()
    for m in con.execute("SELECT bestellnr, ean FROM material"):
        if (m["bestellnr"] or "").strip():
            nr.add(_nr(m["bestellnr"]))
        if (m["ean"] or "").strip():
            ean.add(re.sub(r"\D", "", m["ean"]).lstrip("0"))
    return nr, ean


def neue(con, artikel, suche="", gruppe="", grenze=200):
    """Artikel der Datei, die es im Materialstamm (bei keinem Lieferanten) noch nicht gibt; mit Suche und Warengruppe."""
    nr, ean = _bekannt(con)
    frei = [a for a in artikel if not (a.get("artnr") and _nr(a["artnr"]) in nr) and not (a.get("ean") and a["ean"].lstrip("0") in ean)]
    gruppen = {}
    for a in frei:
        g = a.get("warengruppe") or ""
        if g:
            gruppen[g] = gruppen.get(g, 0) + 1
    worte = [w for w in re.split(r"\s+", str(suche or "").lower().strip()) if w]
    treffer = []
    for a in frei:
        if gruppe and (a.get("warengruppe") or "") != gruppe:
            continue
        if worte:
            heu = f"{a.get('artnr', '')} {a.get('ean', '')} {a.get('text', '')}".lower()
            if not all(w in heu for w in worte):
                continue
        treffer.append(a)
    return {"neu_gesamt": len(frei), "neu_treffer": len(treffer), "neu": treffer[:grenze],
            "gruppen": sorted(gruppen.items(), key=lambda x: (-x[1], x[0]))[:80]}


def anlegen(con, artikel, auswahl, kategorie, lieferant_id, rabatt=0.0):
    """Ausgewählte Artikel (Artikelnummern bzw. EAN aus der Datei) als Material anlegen. Schon vorhandene werden übersprungen."""
    if kategorie not in material.KATEGORIEN:
        raise Fehler("Bitte eine Materialart wählen.")
    wahl = {str(x) for x in auswahl or []}
    if not wahl:
        raise Fehler("Bitte mindestens einen Artikel anhaken.")
    if len(wahl) > 2000:
        raise Fehler("Höchstens 2000 Artikel auf einmal anlegen.")
    nr, ean = _bekannt(con)
    angelegt, uebersprungen = [], 0
    for a in artikel:
        schl = a.get("artnr") or a.get("ean") or ""
        if schl not in wahl:
            continue
        if (a.get("artnr") and _nr(a["artnr"]) in nr) or (a.get("ean") and a["ean"].lstrip("0") in ean):
            uebersprungen += 1
            continue
        preis = a["preis"] if a.get("netto", True) else a["preis"] * (1 - float(rabatt or 0) / 100)
        einheit = a.get("einheit") if a.get("einheit") in material.EINHEITEN else material.STANDARD_EINHEIT.get(kategorie, "Stk.")
        m = material.anlegen(con, {"kategorie": kategorie, "bezeichnung": (a.get("text") or a.get("artnr") or "Artikel")[:200],
                                   "bestellnr": (a.get("artnr") or "")[:60], "ean": (a.get("ean") or "")[:20], "einheit": einheit,
                                   "ek_preis": round(preis, 4), "preis_vom": date.today().isoformat(), "lieferant_id": lieferant_id or None,
                                   "gruppe": (a.get("warengruppe") or "")[:40]})
        angelegt.append({"id": m["id"], "nummer": m["nummer"], "bezeichnung": m["bezeichnung"], "ek_preis": m["ek_preis"]})
        if a.get("artnr"):
            nr.add(_nr(a["artnr"]))
        if a.get("ean"):
            ean.add(a["ean"].lstrip("0"))
    return {"angelegt": len(angelegt), "uebersprungen": uebersprungen, "liste": angelegt}
