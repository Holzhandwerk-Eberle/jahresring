"""Exporte für Steuerberater (Belegpaket) und Betriebsprüfung (Datenträgerüberlassung nach § 147 Abs. 6 AO).

Belegpaket:  Ausgangsrechnungen (Archiv-PDF/ZUGFeRD, XRechnung), Eingangsrechnungen im Originalformat und Listen
             als CSV (Excel-tauglich), mit Prüfung der lückenlosen Rechnungsnummern.
Prüfer:      CSV-Tabellen nach dem „Beschreibungsstandard für die Datenträgerüberlassung“ (index.xml +
             gdpdu-01-09-2004.dtd) für die steuerlich relevanten Daten des Zeitraums, dazu die Belegdateien.
"""
import csv
import io
import json
import os
import re
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

# von app.py gesetzt
HILFE = {"daten": "", "basis": "", "einstellungen": None, "archiv_pdf": None, "klartext": None, "version": ""}


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def _de(iso):
    try:
        return datetime.strptime((iso or "")[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return ""


def _z(x, n=2):
    """Zahl für CSV: Komma als Dezimalzeichen, ohne Tausenderpunkte."""
    try:
        return f"{float(x or 0):.{n}f}".replace(".", ",")
    except (TypeError, ValueError):
        return ""


def _jl(t, std):
    try:
        return json.loads(t) if t else std
    except ValueError:
        return std


def _sauber(t):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(t or "")).strip()[:120] or "Datei"


def zeitraum_pruefen(von, bis):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", von or "") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", bis or "") or bis < von:
        raise Fehler("Bitte einen gültigen Zeitraum angeben.")


def ordner():
    p = os.path.join(HILFE["daten"], "exporte")
    os.makedirs(p, exist_ok=True)
    return p


# ---------------------------------------------------------------- Daten sammeln
def rechnungen(con, von, bis):
    aus = []
    for r in con.execute("SELECT b.*, k.nummer AS kundennr, a.nummer AS auftragsnr FROM belege b LEFT JOIN kunden k ON k.id=b.kunde_id "
                         "LEFT JOIN auftraege a ON a.id=b.auftrag_id WHERE b.art IN ('rechnung','abschlag','storno','gutschrift','korrektur') "
                         "AND b.status IN ('fest','storniert') AND b.datum BETWEEN ? AND ? ORDER BY b.datum, b.nummer", (von, bis)):
        b = dict(r)
        b["daten"] = _jl(b["daten"], {})
        aus.append(b)
    return aus


ARTNAME = {"rechnung": "Rechnung", "abschlag": "Abschlagsrechnung", "storno": "Stornorechnung", "gutschrift": "Gutschrift", "korrektur": "Rechnungskorrektur"}


def nummern_luecken(con, von, bis):
    """Fehlende laufende Nummern im Rechnungsnummernkreis der betroffenen Jahre (bis zur höchsten vergebenen Nummer)."""
    luecken = []
    for jahr in range(int(von[:4]), int(bis[:4]) + 1):
        nrn = {}
        for (n,) in con.execute("SELECT nummer FROM belege WHERE art IN ('rechnung','abschlag','storno','gutschrift','korrektur') AND nummer LIKE ?", (f"%{jahr}-%",)):
            m = re.search(rf"{jahr}-(\d+)$", n or "")
            if m:
                nrn[int(m.group(1))] = n
        if not nrn:
            continue
        erste = min(nrn)
        for i in range(erste, max(nrn) + 1):
            if i not in nrn:
                luecken.append(f"{jahr}-{i:04d}")
    return luecken


def belegdateien(b):
    """Archivdateien (PDF, XRechnung) eines Belegs."""
    archiv = os.path.join(HILFE["daten"], "belege", (b["datum"] or "")[:4] or "ohne-datum")
    if not os.path.isdir(archiv) or not b["nummer"]:
        return []
    return [os.path.join(archiv, f) for f in sorted(os.listdir(archiv)) if f.startswith(b["nummer"] + "_")]


def zahlungsauftraege(con, von, bis):
    return [dict(r) for r in con.execute(
        "SELECT z.*, l.nummer AS liefnr, l.kurzname AS lieferant, l.ustid AS lief_ustid, a.nummer AS auftragsnr FROM zahlungen z "
        "LEFT JOIN lieferanten l ON l.id=z.lieferant_id LEFT JOIN auftraege a ON a.id=z.auftrag_id "
        "WHERE COALESCE(NULLIF(z.belegdatum,''), substr(z.angelegt,1,10)) BETWEEN ? AND ? ORDER BY z.belegdatum, z.nummer", (von, bis))]


def eingangsdatei(z):
    d = z.get("datei") or ""
    if not d:
        return None
    p = d if os.path.isabs(d) else os.path.join(HILFE["daten"], "eingangsrechnungen", d)
    return p if os.path.isfile(p) else None


def zahlungseingaenge(con, von, bis):
    return [dict(r) for r in con.execute(
        "SELECT z.*, o.nummer AS rechnungsnr, k.nummer AS kundennr FROM zahlungseingaenge z JOIN offene_posten o ON o.id=z.op_id "
        "LEFT JOIN kunden k ON k.id=o.kunde_id WHERE z.datum BETWEEN ? AND ? ORDER BY z.datum, z.id", (von, bis))]


# ---------------------------------------------------------------- CSV-Hilfen
def csv_excel(kopf, zeilen):
    """CSV für Excel (Semikolon, UTF-8 mit BOM)."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(kopf)
    w.writerows(zeilen)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def csv_pruefer(zeilen):
    """CSV nach Beschreibungsstandard: ohne Kopfzeile, Semikolon, CRLF, Text in Anführungszeichen, UTF-8 ohne BOM."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n", quotechar='"', quoting=csv.QUOTE_MINIMAL)
    for z in zeilen:
        w.writerow(["" if v is None else v for v in z])
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------- Belegpaket für den Steuerberater
def belegpaket(con, von, bis, wer=""):
    zeitraum_pruefen(von, bis)
    e = HILFE["einstellungen"](con)
    name = f"Belegpaket_{_sauber(e.get('firma') or 'Jahresring')}_{von}_bis_{bis}.zip".replace(" ", "_")
    ziel = os.path.join(ordner(), name)
    rech = rechnungen(con, von, bis)
    zahl = zahlungsauftraege(con, von, bis)
    eing = zahlungseingaenge(con, von, bis)
    fehlende_pdf, fehlende_datei = [], []
    with zipfile.ZipFile(ziel + ".part", "w", zipfile.ZIP_DEFLATED) as z:
        for b in rech:
            dateien = belegdateien(b)
            if not any(f.lower().endswith(".pdf") for f in dateien) and HILFE.get("archiv_pdf"):
                try:
                    HILFE["archiv_pdf"](con, b["id"])
                    dateien = belegdateien(b)
                except Exception:  # noqa: BLE001
                    pass
            if not dateien:
                fehlende_pdf.append(b["nummer"])
            for f in dateien:
                z.write(f, "Ausgangsrechnungen/" + os.path.basename(f))
        for r in zahl:
            p = eingangsdatei(r)
            if p:
                z.write(p, "Eingangsrechnungen/" + os.path.basename(p))
            else:
                fehlende_datei.append(f"{r['nummer']} {r.get('lieferant') or ''} {r.get('belegnr') or ''}".strip())
        z.writestr("Rechnungsausgangsliste.csv", csv_excel(
            ["Rechnungsnummer", "Art", "Rechnungsdatum", "Leistungsdatum", "Kundennummer", "Kunde", "USt-IdNr. Kunde", "Auftrag",
             "Netto", "USt-Satz %", "USt", "Brutto", "abzgl. Abschläge brutto", "Zahlbetrag", "Fällig", "Status", "Storno zu", "Datei"],
            [[b["nummer"], ARTNAME.get(b["art"], b["art"]), _de(b["datum"]), _de(b["leistungsdatum"]), b.get("kundennr") or "",
              (b["daten"].get("kunde") or {}).get("kurzname", ""), (b["daten"].get("kunde") or {}).get("ustid") or "", b.get("auftragsnr") or "",
              _z(b["netto"]), _z(b["ust_satz"], 0), _z(b["ust"]), _z(b["brutto"]),
              _z((b["daten"].get("summen") or {}).get("abzug_brutto", 0)), _z(b["zahlbetrag"]), _de(b["faellig"]),
              "storniert" if b["status"] == "storniert" else "festgeschrieben",
              (b["daten"].get("bezug") or {}).get("nummer", ""), "; ".join(os.path.basename(f) for f in belegdateien(b))] for b in rech]))
        z.writestr("Eingangsrechnungen.csv", csv_excel(
            ["Zahlungsauftrag", "Lieferantennummer", "Lieferant", "USt-IdNr. Lieferant", "Rechnungsnummer", "Rechnungsdatum", "Betrag brutto",
             "Vorsteuer %", "Skonto", "Skonto bis", "Fällig", "Bezahlt am", "Bezahlart", "Auftrag", "Bemerkung", "Datei"],
            [[r["nummer"], r.get("liefnr") or "", r.get("lieferant") or "", r.get("lief_ustid") or "", r.get("belegnr") or "", _de(r.get("belegdatum")),
              _z(r.get("betrag")), _z(r.get("vorsteuer"), 0), _z(r.get("skonto")), _de(r.get("skonto_bis")), _de(r.get("faellig")),
              _de(r.get("bezahlt")), r.get("bezahlung") or "", r.get("auftragsnr") or "", r.get("bemerkung") or "",
              os.path.basename(eingangsdatei(r) or "")] for r in zahl]))
        z.writestr("Zahlungseingaenge.csv", csv_excel(
            ["Datum", "Rechnungsnummer", "Kundennummer", "Betrag", "davon Mahnkosten", "Art", "Bemerkung"],
            [[_de(x["datum"]), x.get("rechnungsnr") or "", x.get("kundennr") or "", _z(x["betrag"]), _z(x.get("auf_mahnkosten")),
              x.get("art") or "", x.get("bemerkung") or ""] for x in eing]))
        luecken = nummern_luecken(con, von, bis)
        summe = {k: round(sum(float(b[k] or 0) for b in rech), 2) for k in ("netto", "ust", "brutto")}
        info = [f"Belegpaket {e.get('firma') or ''} – Zeitraum {_de(von)} bis {_de(bis)}",
                f"Erstellt am {datetime.now():%d.%m.%Y %H:%M} mit Jahresring {HILFE['version']} von {wer}", "",
                f"Ausgangsrechnungen: {len(rech)} (Netto {_z(summe['netto'])} €, USt {_z(summe['ust'])} €, Brutto {_z(summe['brutto'])} €)",
                f"Eingangsrechnungen / Zahlungsaufträge: {len(zahl)}",
                f"Zahlungseingänge: {len(eing)}", "",
                "Rechnungsnummern: " + ("lückenlos." if not luecken else "FEHLENDE NUMMERN: " + ", ".join(luecken[:50])),
                "Ausgangsrechnungen ohne Archivdatei: " + (", ".join(fehlende_pdf) or "keine"),
                "Zahlungsaufträge ohne Originaldatei (Papierbeleg?): " + (", ".join(fehlende_datei[:50]) or "keine"), "",
                "Ausgangsrechnungen: Archiv-PDF der festgeschriebenen Rechnung (bei E-Rechnung mit eingebettetem ZUGFeRD-Datensatz),",
                "ggf. XRechnung-Datei. Eingangsrechnungen: unveränderte Originaldatei wie empfangen.",
                "Die CSV-Dateien lassen sich mit Excel öffnen (Trennzeichen Semikolon)."]
        z.writestr("LIESMICH.txt", "\r\n".join(info).encode("utf-8"))
    os.replace(ziel + ".part", ziel)
    return {"datei": name, "groesse": os.path.getsize(ziel), "rechnungen": len(rech), "eingangsrechnungen": len(zahl),
            "zahlungseingaenge": len(eing), "luecken": luecken, "ohne_pdf": fehlende_pdf, "ohne_datei": fehlende_datei, "summen": summe}


# ---------------------------------------------------------------- Datenträgerüberlassung (Beschreibungsstandard)
A, N, D = "A", "N", "D"   # AlphaNumeric, Numeric (2 Stellen), Date


def _spalten_xml(spalten, pk):
    teile = []
    for i, (name, typ, beschr) in enumerate(spalten):
        tag = "VariablePrimaryKey" if i < pk else "VariableColumn"
        art = {"A": "<AlphaNumeric/>", "N": "<Numeric><Accuracy>2</Accuracy></Numeric>", "N0": "<Numeric/>",
               "D": "<Date><Format>DD.MM.YYYY</Format></Date>"}[typ]
        teile.append(f"      <{tag}><Name>{escape(name)}</Name>{f'<Description>{escape(beschr)}</Description>' if beschr else ''}{art}</{tag}>")
    return "\n".join(teile)


def pruefer_export(con, von, bis, wer=""):
    zeitraum_pruefen(von, bis)
    e = HILFE["einstellungen"](con)
    kt = HILFE["klartext"]
    name = f"Datentraeger_GoBD_{von}_bis_{bis}.zip"
    ziel = os.path.join(ordner(), name)
    rech = rechnungen(con, von, bis)
    rnrn = {b["id"]: b["nummer"] for b in rech}
    zahl = zahlungsauftraege(con, von, bis)
    eing = zahlungseingaenge(con, von, bis)

    tabellen = []   # (datei, name, beschreibung, spalten, pk, zeilen, fremdschluessel)

    # Ausgangsrechnungen
    tabellen.append(("Ausgangsrechnungen.csv", "Ausgangsrechnungen", "Festgeschriebene Rechnungen, Abschlags- und Stornorechnungen",
        [("Rechnungsnummer", A, ""), ("Art", A, ""), ("Rechnungsdatum", D, ""), ("Leistungsdatum", D, ""), ("Kundennummer", A, ""),
         ("Kunde", A, ""), ("Auftragsnummer", A, ""), ("Netto", N, "Entgelt nach Rabatt"), ("Steuersatz", N, "Prozent"), ("Umsatzsteuer", N, ""),
         ("Brutto", N, ""), ("AbzugAbschlaege", N, "abgezogene Abschlagsrechnungen brutto"), ("Zahlbetrag", N, ""), ("Faellig", D, ""),
         ("Status", A, "festgeschrieben oder storniert"), ("StornoZu", A, "Nummer der stornierten Rechnung"), ("Versendet", A, ""),
         ("Datei", A, "Archivdatei im Ordner Belege")], 1,
        [[b["nummer"], ARTNAME.get(b["art"], b["art"]), _de(b["datum"]), _de(b["leistungsdatum"]), str(b.get("kundennr") or ""),
          (b["daten"].get("kunde") or {}).get("kurzname", ""), b.get("auftragsnr") or "", _z(b["netto"]), _z(b["ust_satz"]), _z(b["ust"]),
          _z(b["brutto"]), _z((b["daten"].get("summen") or {}).get("abzug_brutto", 0)), _z(b["zahlbetrag"]), _de(b["faellig"]),
          "storniert" if b["status"] == "storniert" else "festgeschrieben", (b["daten"].get("bezug") or {}).get("nummer", ""),
          (b.get("versendet") or "")[:16].replace("T", " "), "; ".join(os.path.basename(f) for f in belegdateien(b))] for b in rech],
        [("Kundennummer", "Kunden")]))
    # Positionen
    pos = []
    for b in rech:
        i = 0
        for zl in b["daten"].get("zeilen", []):
            if zl.get("typ") != "pos" or zl.get("info"):
                continue
            i += 1
            pos.append([b["nummer"], str(i), str(zl.get("posnr") or ""), _z(zl.get("menge"), 3), zl.get("einheit") or "", kt(zl.get("text") or "")[:1000],
                        _z(zl.get("ep")), _z(zl.get("gp")), "ja" if zl.get("zaehlt", True) else "nein"])
    tabellen.append(("Rechnungspositionen.csv", "Rechnungspositionen", "Positionen der Ausgangsrechnungen (eingefrorener Belegstand)",
        [("Rechnungsnummer", A, ""), ("Zeile", "N0", ""), ("Positionsnummer", A, ""), ("Menge", N, ""), ("Einheit", A, ""), ("Text", A, ""),
         ("Einzelpreis", N, "netto bzw. wie gedruckt"), ("Gesamtpreis", N, ""), ("InSumme", A, "nein = Alternativ-/Bedarfsposition")], 2, pos,
        [("Rechnungsnummer", "Ausgangsrechnungen")]))
    # Abschläge in Schlussrechnungen
    abz = [[b["nummer"], x.get("nummer") or "", _de(x.get("datum")), _z(x.get("netto")), _z(x.get("ust")), _z(x.get("brutto"))]
           for b in rech for x in (b["daten"].get("abzuege") or [])]
    tabellen.append(("Abschlagsverrechnung.csv", "Abschlagsverrechnung", "In Schlussrechnungen abgezogene Abschlagsrechnungen",
        [("Rechnungsnummer", A, "Schlussrechnung"), ("Abschlagsrechnung", A, ""), ("Datum", D, ""), ("Netto", N, ""), ("Umsatzsteuer", N, ""), ("Brutto", N, "")], 2, abz,
        [("Rechnungsnummer", "Ausgangsrechnungen")]))
    # Offene Posten
    ops = [dict(r) for r in con.execute("SELECT o.*, k.nummer AS kundennr FROM offene_posten o LEFT JOIN kunden k ON k.id=o.kunde_id "
                                        "WHERE o.beleg_id IN (%s)" % (",".join(str(i) for i in rnrn) or "0"))]
    tabellen.append(("OffenePosten.csv", "OffenePosten", "Forderungen aus den Ausgangsrechnungen (Stand bei Export)",
        [("Rechnungsnummer", A, ""), ("Kundennummer", A, ""), ("Datum", D, ""), ("Betrag", N, ""), ("Offen", N, "zum Exportzeitpunkt"), ("Faellig", D, ""),
         ("Mahnstufe", "N0", ""), ("Mahnkosten", N, "")], 1,
        [[o["nummer"], str(o.get("kundennr") or ""), _de(o["datum"]), _z(o["betrag"]), _z(o["offen"]), _de(o["faellig"]), str(o.get("mahnstufe") or 0),
          _z(o.get("mahnkosten"))] for o in ops], [("Rechnungsnummer", "Ausgangsrechnungen")]))
    # Zahlungseingänge
    tabellen.append(("Zahlungseingaenge.csv", "Zahlungseingaenge", "Erfasste Zahlungseingänge zu Ausgangsrechnungen",
        [("ID", "N0", ""), ("Datum", D, ""), ("Rechnungsnummer", A, ""), ("Kundennummer", A, ""), ("Betrag", N, ""), ("Mahnkosten", N, "davon auf Mahnkosten"),
         ("Art", A, ""), ("Bemerkung", A, "")], 1,
        [[str(x["id"]), _de(x["datum"]), x.get("rechnungsnr") or "", str(x.get("kundennr") or ""), _z(x["betrag"]), _z(x.get("auf_mahnkosten")),
          x.get("art") or "", x.get("bemerkung") or ""] for x in eing], [("Rechnungsnummer", "Ausgangsrechnungen")]))
    # Mahnungen
    mahn = [dict(r) for r in con.execute("SELECT m.*, o.nummer AS rechnungsnr FROM mahnungen m JOIN offene_posten o ON o.id=m.op_id "
                                         "WHERE m.datum BETWEEN ? AND ? ORDER BY m.datum", (von, bis))]
    tabellen.append(("Mahnungen.csv", "Mahnungen", "Mahnungen zu Ausgangsrechnungen",
        [("Mahnung", A, ""), ("Rechnungsnummer", A, ""), ("Stufe", "N0", ""), ("Datum", D, ""), ("Gebuehr", N, ""), ("Zinsen", N, ""), ("Pauschale", N, "")], 1,
        [[m.get("nummer") or str(m["id"]), m["rechnungsnr"], str(m.get("stufe") or 0), _de(m["datum"]), _z(m.get("gebuehr")), _z(m.get("zinsen")),
          _z(m.get("pauschale"))] for m in mahn], []))
    # Eingangsrechnungen
    tabellen.append(("Eingangsrechnungen.csv", "Eingangsrechnungen", "Erfasste Lieferantenrechnungen (Zahlungsaufträge)",
        [("Zahlungsauftrag", A, ""), ("Lieferantennummer", A, ""), ("Lieferant", A, ""), ("Rechnungsnummer", A, "des Lieferanten"), ("Rechnungsdatum", D, ""),
         ("BetragBrutto", N, ""), ("Vorsteuersatz", N, "Prozent"), ("Skonto", N, ""), ("Faellig", D, ""), ("BezahltAm", D, ""), ("Bezahlart", A, ""),
         ("Auftragsnummer", A, ""), ("Datei", A, "Originaldatei im Ordner Eingangsrechnungen")], 1,
        [[r["nummer"], str(r.get("liefnr") or ""), r.get("lieferant") or "", r.get("belegnr") or "", _de(r.get("belegdatum")), _z(r.get("betrag")),
          _z(r.get("vorsteuer")), _z(r.get("skonto")), _de(r.get("faellig")), _de(r.get("bezahlt")), r.get("bezahlung") or "", r.get("auftragsnr") or "",
          os.path.basename(eingangsdatei(r) or "")] for r in zahl], [("Lieferantennummer", "Lieferanten")]))
    # Stammdaten (nur die im Zeitraum vorkommenden)
    kids = {b["kunde_id"] for b in rech if b.get("kunde_id")}
    kunden = [dict(r) for r in con.execute("SELECT * FROM kunden WHERE id IN (%s) ORDER BY nummer" % (",".join(str(i) for i in kids) or "0"))]
    tabellen.append(("Kunden.csv", "Kunden", "Kunden der Ausgangsrechnungen im Zeitraum",
        [("Kundennummer", A, ""), ("Name", A, ""), ("Anschrift", A, ""), ("PLZ", A, ""), ("Ort", A, ""), ("Land", A, ""), ("UStIdNr", A, ""), ("Gruppe", A, "")], 1,
        [[str(k["nummer"]), k["kurzname"], (k.get("anschrift") or "").replace("\n", ", "), k.get("plz") or "", k.get("ort") or "", k.get("land") or "",
          k.get("ustid") or "", k.get("gruppe") or ""] for k in kunden], []))
    lids = {r["lieferant_id"] for r in zahl if r.get("lieferant_id")}
    lief = [dict(r) for r in con.execute("SELECT * FROM lieferanten WHERE id IN (%s) ORDER BY nummer" % (",".join(str(i) for i in lids) or "0"))]
    tabellen.append(("Lieferanten.csv", "Lieferanten", "Lieferanten der Eingangsrechnungen im Zeitraum",
        [("Lieferantennummer", A, ""), ("Name", A, ""), ("Anschrift", A, ""), ("PLZ", A, ""), ("Ort", A, ""), ("Land", A, ""), ("UStIdNr", A, ""), ("Gruppe", A, "")], 1,
        [[str(l["nummer"]), l["kurzname"], (l.get("anschrift") or "").replace("\n", ", "), l.get("plz") or "", l.get("ort") or "", l.get("land") or "",
          l.get("ustid") or "", l.get("gruppe") or ""] for l in lief], []))
    # Protokoll
    prot = [dict(r) for r in con.execute("SELECT * FROM protokoll WHERE zeit BETWEEN ? AND ? ORDER BY nr", (von, bis + "T99"))]
    tabellen.append(("Protokoll.csv", "Protokoll", "Unveränderbares Protokoll GoBD-relevanter Vorgänge (Hash-Kette SHA-256)",
        [("Nr", "N0", ""), ("Zeit", A, ""), ("Benutzer", A, ""), ("Vorgang", A, ""), ("Objekt", A, ""), ("Text", A, ""), ("Programmversion", A, ""),
         ("HashVorgaenger", A, ""), ("Hash", A, "")], 1,
        [[str(p["nr"]), p["zeit"], p["benutzer"], p["art"], p["objekt"], p["text"], p["version"], p["vorher"], p["hash"]] for p in prot], []))

    # index.xml
    tab_xml = []
    for datei, tname, beschr, spalten, pk, zeilen, fk in tabellen:
        fk_xml = "".join(f"\n      <ForeignKey><Name>{escape(a)}</Name><References>{escape(b)}</References></ForeignKey>" for a, b in fk)
        tab_xml.append(f"""    <Table>
      <URL>{escape(datei)}</URL>
      <Name>{escape(tname)}</Name>
      <Description>{escape(beschr)}</Description>
      <Validity><Range><From>{_de(von)}</From><To>{_de(bis)}</To></Range><Format>DD.MM.YYYY</Format></Validity>
      <UTF8/>
      <DecimalSymbol>,</DecimalSymbol>
      <DigitGroupingSymbol>.</DigitGroupingSymbol>
      <VariableLength>
      <ColumnDelimiter>;</ColumnDelimiter>
      <RecordDelimiter>&#13;&#10;</RecordDelimiter>
      <TextEncapsulator>"</TextEncapsulator>
{_spalten_xml(spalten, pk)}{fk_xml}
      </VariableLength>
    </Table>""")
    ort = " ".join(x for x in [(e.get("firma_anschrift") or "").replace("\n", ", ")] if x)
    index = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE DataSet SYSTEM "gdpdu-01-09-2004.dtd">
<DataSet>
  <Version>1.0</Version>
  <DataSupplier>
    <Name>{escape(e.get('firma') or '')}</Name>
    <Location>{escape(ort)}</Location>
    <Comment>Datenträgerüberlassung nach § 147 Abs. 6 AO aus Jahresring {escape(HILFE['version'])}, Zeitraum {_de(von)} bis {_de(bis)}, erstellt {datetime.now():%d.%m.%Y %H:%M}</Comment>
  </DataSupplier>
  <Media>
    <Name>Jahresring {_de(von)} bis {_de(bis)}</Name>
{chr(10).join(tab_xml)}
  </Media>
</DataSet>
"""
    with zipfile.ZipFile(ziel + ".part", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("index.xml", index.encode("utf-8"))
        z.write(os.path.join(HILFE["basis"], "lib", "gdpdu-01-09-2004.dtd"), "gdpdu-01-09-2004.dtd")
        for datei, _, _, spalten, _, zeilen, _ in tabellen:
            z.writestr(datei, csv_pruefer(zeilen))
        for b in rech:
            for f in belegdateien(b):
                z.write(f, "Belege/Ausgangsrechnungen/" + os.path.basename(f))
        for r in zahl:
            p = eingangsdatei(r)
            if p:
                z.write(p, "Belege/Eingangsrechnungen/" + os.path.basename(p))
        z.writestr("LIESMICH.txt", "\r\n".join([
            f"Datenträgerüberlassung {e.get('firma') or ''} – Zeitraum {_de(von)} bis {_de(bis)}",
            f"Erstellt am {datetime.now():%d.%m.%Y %H:%M} mit Jahresring {HILFE['version']} von {wer}", "",
            "Aufbau nach dem Beschreibungsstandard für die Datenträgerüberlassung (index.xml, gdpdu-01-09-2004.dtd).",
            "Die CSV-Dateien haben keine Kopfzeile; Spalten, Datentypen und Schlüssel stehen in index.xml.",
            "Zeichensatz UTF-8, Trennzeichen Semikolon, Dezimalzeichen Komma, Datumsformat TT.MM.JJJJ.", "",
            "Tabellen:"] + [f"  {d}: {b} ({len(z_)} Datensätze)" for d, _, b, _, _, z_, _ in tabellen] + [
            "", "Belege/Ausgangsrechnungen: Archiv-PDF der festgeschriebenen Rechnungen (ZUGFeRD-Datensatz eingebettet), XRechnung.",
            "Belege/Eingangsrechnungen: Lieferantenrechnungen im Originalformat wie empfangen.",
            "Die Finanzbuchhaltung (Hauptbuch) führt der Steuerberater; deren Daten sind nicht Bestandteil dieses Exports."]).encode("utf-8"))
    os.replace(ziel + ".part", ziel)
    return {"datei": name, "groesse": os.path.getsize(ziel), "tabellen": {t[1]: len(t[5]) for t in tabellen}}


def liste():
    p = ordner()
    return [{"datei": f, "groesse": os.path.getsize(os.path.join(p, f)),
             "zeit": datetime.fromtimestamp(os.path.getmtime(os.path.join(p, f))).isoformat(timespec="minutes")}
            for f in sorted(os.listdir(p), key=lambda f: os.path.getmtime(os.path.join(p, f)), reverse=True) if f.endswith(".zip")]
