"""Jahresring – Einkaufspreise von Lieferanten einlesen (Datanorm 4/5 oder CSV/Excel-Preisliste).

Ablauf: Datei lesen → Artikel mit dem Materialstamm abgleichen (Bestellnummer des Lieferanten oder EAN) → Vorschau mit
altem und neuem Preis → nur die bestätigten Preise werden übernommen (mit Datum „Preis vom“; Verkaufspreise mit
Aufschlag werden wie beim Ändern von Hand nachgeführt). Der Materialstamm wird nie ungefragt verändert.
"""
import hashlib
import io
import re
import threading
import time
from datetime import date

import zipfile

import kundenimport
import material

SCHEMA = """
CREATE TABLE IF NOT EXISTS preis_rabatte (
    lieferant_id INTEGER NOT NULL, gruppe TEXT NOT NULL, rabatt REAL NOT NULL DEFAULT 0, geaendert TEXT,
    PRIMARY KEY (lieferant_id, gruppe)
);
"""
HILFE = {}   # von app.py gesetzt: prot
MAX_ENTPACKT = 250 * 1024 * 1024

MAX_DATEI = 60 * 1024 * 1024
EINHEITEN = {"STK": "Stk.", "ST": "Stk.", "STÜCK": "Stk.", "STUECK": "Stk.", "PCE": "Stk.", "C62": "Stk.", "M2": "m²", "QM": "m²", "MTK": "m²",
             "M²": "m²", "M3": "m³", "CBM": "m³", "MTQ": "m³", "M³": "m³", "M": "lfm.", "LFM": "lfm.", "MTR": "lfm.", "LM": "lfm.",
             "PAA": "Paar", "PR": "Paar", "PAAR": "Paar", "SET": "Satz", "SATZ": "Satz", "L": "Liter", "LTR": "Liter", "LITER": "Liter",
             "KG": "kg", "KGM": "kg", "DOSE": "Dose", "ROLLE": "Rolle", "RO": "Rolle", "PAK": "Packung", "PCK": "Packung", "PAC": "Packung"}


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def schema(con):
    con.executescript(SCHEMA)


def _einheit(t):
    t = str(t or "").strip()
    return EINHEITEN.get(t.upper().replace(".", ""), t)


def _zahl(t):
    """Zahl aus einer Preisliste: deutsche Schreibweise (1.234,50), englische (1,234.50) und Schweizer (1'234.50)."""
    t = str(t or "").strip().replace(" ", "").replace("\u00a0", "").replace("€", "").replace("'", "").replace("’", "")
    if not t:
        return None
    if "," in t and "." in t:
        if t.rfind(".") > t.rfind(","):     # englisch: Komma trennt Tausender, Punkt die Nachkommastellen
            t = t.replace(",", "")
        else:
            t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _nr(t):
    return re.sub(r"[\s.\-/]", "", str(t or "")).upper().lstrip("0")


def gtin_ok(x):
    """EAN/GTIN mit 8, 12, 13 oder 14 Stellen und stimmender Prüfziffer."""
    if not re.fullmatch(r"\d{8}|\d{12,14}", x or ""):
        return False
    z = [int(c) for c in x]
    return (10 - sum(v * (3 if i % 2 == 0 else 1) for i, v in enumerate(reversed(z[:-1]))) % 10) % 10 == z[-1]


# ---------------------------------------------------------------- Datanorm
def _dn_preis(roh, version5):
    roh = (roh or "").strip()
    if not roh:
        return None
    if re.fullmatch(r"\d+", roh) and not version5:
        return int(roh) / 100   # Datanorm 4: Preis in Cent ohne Komma
    return _zahl(roh)


def datanorm_lesen(text):
    zeilen = [z for z in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if z.strip()]
    version5 = any(re.match(r"V;0?5", z) for z in zeilen[:5])
    artikel, ean, pe_von, p_preise, rabatte, geloescht = {}, {}, {}, {}, {}, 0
    for z in zeilen:
        f = z.split(";")
        satz = f[0].strip().upper()
        if satz == "A" and len(f) > 9:
            nr = f[2].strip()
            if not nr:
                continue
            if f[1].strip().upper() == "L":   # Löschsatz: Artikel gibt es beim Lieferanten nicht mehr
                artikel.pop(nr, None)
                geloescht += 1
                continue
            pe_feld = f[7].strip()
            if version5:
                pe = int(pe_feld) if pe_feld.isdigit() and int(pe_feld) > 0 else 1
            else:
                pe = {"0": 1, "1": 10, "2": 100, "3": 1000}.get(pe_feld, 1)
            preis = _dn_preis(f[9], version5)
            if preis is None:
                continue
            pe_von[nr] = pe
            artikel[nr] = {"artnr": nr, "text": " ".join(x.strip() for x in f[4:6] if x.strip())[:120], "preis": round(preis / pe, 4),
                           "einheit": _einheit(f[8]), "netto": f[6].strip() == "2", "rabattgruppe": f[10].strip() if len(f) > 10 else "",
                           "warengruppe": f[11].strip() if len(f) > 11 else ""}
        elif satz == "B" and len(f) > 3:
            # EAN steht im 10. Feld; sonst die erste Zahl mit stimmender Prüfziffer (nicht die alternative Artikelnummer)
            kand = ([f[9].strip()] if len(f) > 9 else []) + [x.strip() for x in f[3:]]
            e = next((x for x in kand if len(x) >= 12 and gtin_ok(x)), None) or next((x for x in kand if gtin_ok(x) and len(f) > 9 and x == f[9].strip()), None)
            if e:
                ean[f[2].strip()] = e
        elif satz == "P":
            # Preisänderung: nach „P;Kennzeichen;“ bis zu drei Blöcke aus Artikelnummer, Preiskennzeichen, Preis und drei Rabattpaaren
            for i in range(2, len(f) - 2, 9):
                nr = f[i].strip()
                preis = _dn_preis(f[i + 2], version5) if nr else None
                if nr and preis is not None:
                    p_preise[nr] = (preis, f[i + 1].strip() == "2")
        elif satz == "R":
            # Rabattsatz: Blöcke aus Rabattgruppe, Kennzeichen (1 = Prozent, 2 = Multiplikator), Wert, Bezeichnung
            for i in range(2, len(f) - 2, 4):
                gr, kz, wert = f[i].strip(), f[i + 1].strip(), f[i + 2].strip()
                if not gr or not wert:
                    continue
                try:
                    if kz == "1":
                        pz = int(wert) / 100 if re.fullmatch(r"\d+", wert) else _zahl(wert)
                    elif kz == "2":
                        pz = (1 - (int(wert) / 1000 if re.fullmatch(r"\d+", wert) else _zahl(wert))) * 100
                    else:
                        continue
                except (TypeError, ValueError):
                    continue
                if pz is not None and 0 <= pz < 100:
                    rabatte[gr] = round(pz, 2)
    for nr, e in ean.items():
        if nr in artikel:
            artikel[nr]["ean"] = e
    # Preisänderungssätze: neuer Preis für bekannte Artikel der Datei; reine Preisdateien liefern Artikel ohne Text und Preiseinheit
    nur_preis = 0
    for nr, (preis, netto) in p_preise.items():
        if nr in artikel:
            artikel[nr].update(preis=round(preis / pe_von.get(nr, 1), 4), netto=netto)
        else:
            artikel[nr] = {"artnr": nr, "text": "", "preis": round(preis, 4), "einheit": "", "netto": netto, "rabattgruppe": "", "warengruppe": "",
                           "nur_preis": True}
            nur_preis += 1
    teile = []
    if nur_preis:
        teile.append(f"{nur_preis} Preise stammen aus Preisänderungssätzen ohne Artikeldaten: Sie aktualisieren nur vorhandenes Material. Die "
                     "Preiseinheit (je 1, 10, 100 oder 1000) steht dort nicht – das Programm wählt die, die zum bisherigen Preis passt; bitte prüfen.")
    if geloescht:
        teile.append(f"{geloescht} beim Lieferanten gelöschte Artikel wurden übersprungen.")
    return list(artikel.values()), " ".join(teile), rabatte


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
    "artnr": ("artikelnummer", "artikelnr", "artnr", "art nr", "bestellnummer", "bestellnr", "best nr", "artikel", "materialnummer", "sku", "item no", "item number", "part number", "part no", "nummer"),
    "ean": ("ean", "gtin", "ean13", "ean code", "barcode"),
    "text": ("bezeichnung", "artikelbezeichnung", "kurztext", "beschreibung", "description", "text", "name"),
    "preis": ("netto ek", "nettopreis", "netto", "ek", "einkaufspreis", "ek preis", "preis netto", "ihr preis", "net price", "preis", "price", "listenpreis", "vk"),
    "einheit": ("einheit", "me", "mengeneinheit", "verkaufseinheit", "unit", "uom"),
    "pe": ("preiseinheit", "pe", "preis je", "pro"),
    "gruppe": ("warengruppe", "artikelgruppe", "produktgruppe", "kategorie", "gruppe"),
}


def spalten_vorschlag(kopf):
    k = [re.sub(r"[\s_./-]+", " ", (x or "").strip().lower()).strip() for x in kopf]
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
    if roh[:2] == b"PK" and not n.endswith(".xlsx"):
        roh2, namen = zip_inhalt(roh)
        if roh2 is not None:   # ZIP mit Datanorm-Dateien (Artikel, Preise, Rabatte): zusammen lesen
            erg = lesen(roh2, "datanorm.001", zuordnung)
            erg["hinweis"] = (f"Aus der ZIP-Datei gelesen: {', '.join(namen[:6])}{' …' if len(namen) > 6 else ''}. " + erg["hinweis"]).strip()
            return erg
    text = None if (n.endswith(".xlsx") or roh[:2] == b"PK") else kundenimport.dekodieren(roh)
    if text is not None and (re.search(r"datanorm|datpreis|\.00\d$|\.rab$", n) or re.match(r"\s*V[ ;]", text[:200])) and re.search(r"(?m)^[AP];", text):
        art, hinweis, rabatte = datanorm_lesen(datanorm_text(roh) or text)
        if not art:
            raise Fehler("In der Datanorm-Datei wurden keine Artikel- oder Preissätze gefunden.")
        return {"format": "Datanorm", "artikel": art, "hinweis": hinweis, "kopf": [], "zuordnung": {}, "rabatte_datei": rabatte}
    try:
        zeilen = kundenimport.tabelle_lesen(roh, dateiname)
    except kundenimport.ImportFehler as f:
        raise Fehler(str(f))
    try:
        art, zu = tabelle_artikel(zeilen, zuordnung)
    except Fehler as f:
        # Spalten nicht erkannt: Kopfzeile trotzdem zurückgeben, damit sie sich in der Oberfläche von Hand zuordnen lassen
        return {"format": "Tabelle", "artikel": [], "hinweis": str(f), "kopf": zeilen[0], "zuordnung": spalten_vorschlag(zeilen[0])}
    return {"format": "Tabelle", "artikel": art, "hinweis": "", "kopf": zeilen[0], "zuordnung": zu}


def zip_inhalt(roh):
    """Datanorm-Dateien aus einer ZIP-Datei (viele Händler liefern DATANORM.001, DATPREIS.001, DATANORM.RAB zusammen gepackt).
    Liefert (zusammengefügte Bytes, Dateinamen) oder (None, []) – dann ist es z. B. eine Excel-Datei."""
    try:
        z = zipfile.ZipFile(io.BytesIO(roh))
    except zipfile.BadZipFile:
        return None, []
    namen = z.namelist()
    if any(x.startswith("xl/") or x == "[Content_Types].xml" for x in namen):
        return None, []
    def rang(x):   # Artikel zuerst, dann Preise, dann Rabatte – damit Preisänderungen die Artikelsätze überschreiben
        u = x.upper()
        return (2 if u.endswith(".RAB") else 1 if "PREIS" in u else 0, u)
    wahl = sorted((x for x in namen if re.search(r"(?i)(\.\d{3}|\.rab|\.txt|\.dat)$", x) and not re.search(r"(?i)\.wrg$|liesmich|readme", x)), key=rang)
    if not wahl:
        raise Fehler("In der ZIP-Datei wurden keine Datanorm-Dateien gefunden (erwartet z. B. DATANORM.001). Excel- und CSV-Listen bitte entpackt wählen.")
    if sum(z.getinfo(x).file_size for x in wahl) > MAX_ENTPACKT:
        raise Fehler("Die entpackten Dateien sind zu groß (höchstens 250 MB).")
    teile = []
    for x in wahl:
        t = datanorm_text(z.read(x))
        if teile:   # Vorlaufsatz nur aus der ersten Datei (er legt die Version fest)
            t = "\n".join(zl for zl in t.replace("\r\n", "\n").replace("\r", "\n").split("\n") if not re.match(r"V[ ;]", zl))
        teile.append(t)
    return "\n".join(teile).encode("utf-8"), [x.rsplit("/", 1)[-1] for x in wahl]


# ---------------------------------------------------------------- Rabattgruppen je Lieferant
def rabatte_laden(con, lieferant_id):
    if not lieferant_id:
        return {}
    return {r["gruppe"]: r["rabatt"] for r in con.execute("SELECT gruppe, rabatt FROM preis_rabatte WHERE lieferant_id=?", (lieferant_id,))}


def rabatte_speichern(con, lieferant_id, rabatte):
    if not lieferant_id:
        raise Fehler("Bitte zuerst den Lieferanten wählen – die Rabatte werden bei ihm gespeichert.")
    n = 0
    for gr, wert in (rabatte or {}).items():
        gr = str(gr)[:40]
        pz = None if wert in (None, "") else _zahl(wert) if isinstance(wert, str) else float(wert)
        if pz is None:
            con.execute("DELETE FROM preis_rabatte WHERE lieferant_id=? AND gruppe=?", (lieferant_id, gr))
        elif 0 <= pz < 100:
            con.execute("INSERT OR REPLACE INTO preis_rabatte (lieferant_id, gruppe, rabatt, geaendert) VALUES (?,?,?,?)",
                        (lieferant_id, gr, round(pz, 2), date.today().isoformat()))
            n += 1
        else:
            raise Fehler("Ein Rabatt liegt zwischen 0 und 100 %.")
    return n


def rabatt_uebersicht(con, lieferant_id, erg, von_hand=None):
    """Rabattgruppen der Datei mit dem jeweils wirksamen Rabatt: von Hand in dieser Sitzung > beim Lieferanten gespeichert >
    Rabattsätze der Datei. Gruppe „“ steht für Listenpreise ohne Rabattgruppe (dort gilt der allgemeine Rabatt)."""
    zahl, gesp, datei = {}, rabatte_laden(con, lieferant_id), erg.get("rabatte_datei") or {}
    for a in erg["artikel"]:
        if not a.get("netto", True):
            zahl[a.get("rabattgruppe") or ""] = zahl.get(a.get("rabattgruppe") or "", 0) + 1
    aus, wirksam = [], {}
    for gr, n in sorted(zahl.items(), key=lambda x: (x[0] == "", x[0])):
        if not gr:
            continue
        hand = (von_hand or {}).get(gr)
        hand = _zahl(hand) if isinstance(hand, str) else hand
        wert, quelle = (hand, "eingegeben") if hand is not None else (gesp[gr], "gespeichert") if gr in gesp else (datei[gr], "aus der Datei") if gr in datei else (None, "")
        if wert is not None:
            wirksam[gr] = float(wert)
        aus.append({"gruppe": gr, "anzahl": n, "rabatt": wert, "quelle": quelle})
    return {"brutto": sum(zahl.values()), "rabattgruppen": aus}, wirksam


def _netto(a, rabatt, rabatte):
    """Einkaufspreis eines Artikels: Nettopreise unverändert, Listenpreise abzüglich des Rabatts seiner Rabattgruppe (sonst des allgemeinen)."""
    if a.get("netto", True):
        return a["preis"]
    pz = (rabatte or {}).get(a.get("rabattgruppe") or "")
    return a["preis"] * (1 - float(rabatt or 0 if pz is None else pz) / 100)


# ---------------------------------------------------------------- Abgleich mit dem Materialstamm
def abgleich(con, lieferant_id, artikel, rabatt=0.0, nur_lieferant=True, rabatte=None):
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
        neu = round(_netto(a, rabatt, rabatte), 4)
        alt = float(m["ek_preis"] or 0)
        pe_hinweis = ""
        if a.get("nur_preis") and alt > 0:
            # Preisänderungssatz ohne Preiseinheit: die Teilung wählen, die dem bisherigen Preis am nächsten kommt
            teiler = min((1, 10, 100, 1000), key=lambda t: abs(neu / t - alt))
            if teiler > 1:
                neu, pe_hinweis = round(neu / teiler, 4), f"Preis je {teiler} angenommen"
        diff = ((neu - alt) / alt * 100) if alt else None
        einheit_ok = not a.get("einheit") or not m["einheit"] or a["einheit"] == m["einheit"]
        auffaellig = (diff is not None and abs(diff) > 30) or not einheit_ok or neu <= 0
        treffer.append({"material_id": m["id"], "nummer": m["nummer"], "bezeichnung": (m["bezeichnung"] or "").split("\n")[0][:80],
                        "bestellnr": m["bestellnr"], "ueber": ueber, "alt": alt, "neu": neu, "diff": None if diff is None else round(diff, 1),
                        "einheit": m["einheit"], "einheit_datei": a.get("einheit") or "", "einheit_ok": einheit_ok, "preis_vom": m["preis_vom"],
                        "text_datei": a.get("text") or "", "brutto": not a.get("netto", True), "rabattgruppe": a.get("rabattgruppe") or "",
                        "pe_hinweis": pe_hinweis, "gleich": abs(neu - alt) < 0.00005, "vorschlag": not auffaellig and abs(neu - alt) >= 0.00005})
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
    frei = [a for a in artikel if not a.get("nur_preis") and not (a.get("artnr") and _nr(a["artnr"]) in nr)
            and not (a.get("ean") and a["ean"].lstrip("0") in ean)]
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


def anlegen(con, artikel, auswahl, kategorie, lieferant_id, rabatt=0.0, rabatte=None):
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
        if schl not in wahl or a.get("nur_preis"):
            continue
        if (a.get("artnr") and _nr(a["artnr"]) in nr) or (a.get("ean") and a["ean"].lstrip("0") in ean):
            uebersprungen += 1
            continue
        preis = _netto(a, rabatt, rabatte)
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


# ---------------------------------------------------------------- Schnittstelle (preisimport/…)
def web_api(con, teile, d):
    """POST preisimport/lesen | uebernehmen | neue | anlegen | rabatte."""
    import base64
    import json
    prot = HILFE["prot"]
    lid = int(d["lieferant_id"]) if str(d.get("lieferant_id") or "").isdigit() else None
    rab = _zahl(str(d.get("rabatt") or "0")) or 0.0
    lname = lambda: (lambda l: l["kurzname"] if l else "")(con.execute("SELECT kurzname FROM lieferanten WHERE id=?", (lid,)).fetchone() if lid else None)
    was = teile[1]
    if was == "rabatte":
        return {"gespeichert": rabatte_speichern(con, lid, d.get("rabatte")), "rabatte": rabatte_laden(con, lid)}
    if was == "lesen":
        if d.get("daten"):
            roh = base64.b64decode(d["daten"])
            erg = lesen(roh, str(d.get("dateiname") or ""), d.get("zuordnung"))
            schluessel = merken(roh + json.dumps(d.get("zuordnung") or {}).encode(), erg)
        elif d.get("schluessel"):
            erg, schluessel = gemerkt(d["schluessel"]), d["schluessel"]
        else:
            raise Fehler("Keine Datei übergeben.")
        ueb, wirksam = rabatt_uebersicht(con, lid, erg, d.get("rabatte"))
        ab = abgleich(con, lid, erg["artikel"], rab, nur_lieferant=not d.get("alle"), rabatte=wirksam)
        return {**{k: v for k, v in erg.items() if k not in ("artikel", "rabatte_datei")}, **ab, **neue(con, erg["artikel"]), **ueb, "schluessel": schluessel}
    if was == "neue":
        return neue(con, gemerkt(d.get("schluessel"))["artikel"], d.get("suche") or "", d.get("gruppe") or "")
    if was == "anlegen":
        g = gemerkt(d.get("schluessel"))
        _, wirksam = rabatt_uebersicht(con, lid, g, d.get("rabatte"))
        erg = anlegen(con, g["artikel"], d.get("auswahl"), d.get("kategorie"), lid, rab, wirksam)
        if erg["angelegt"]:
            prot(con, "preisimport", lname()[:80], f"{erg['angelegt']} Materialien aus „{str(d.get('dateiname') or '')[:80]}“ angelegt"
                 + (f" (Lieferant {lname()})" if lid else ""), {"angelegt": erg["liste"][:500]})
        return erg
    if was == "uebernehmen":
        erg = uebernehmen(con, d.get("posten"), date.today().isoformat())
        if erg["geaendert"]:
            prot(con, "preisimport", lname()[:80], f"{erg['geaendert']} Einkaufspreise aus „{str(d.get('dateiname') or '')[:80]}“ übernommen"
                 + (f" (Lieferant {lname()})" if lid else ""), {"liste": erg["liste"][:500]})
        return erg
    raise Fehler("Unbekannte Anfrage", 404)
