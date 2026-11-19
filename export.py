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
from kern import kfm, csv_zelle

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


def _ablegen(ziel):
    """Fertig geschriebene Datei (ziel + ".part") an ihren Platz legen. Ist eine frühere Fassung noch in einem anderen Programm
    geöffnet, lässt Windows das Ersetzen nicht zu – dann eine verständliche Meldung statt „Zugriff verweigert“."""
    try:
        os.replace(ziel + ".part", ziel)
    except PermissionError:
        try:
            os.remove(ziel + ".part")
        except OSError:
            pass
        raise Fehler(f"Die Datei {os.path.basename(ziel)} aus einem früheren Export ist noch in einem anderen Programm geöffnet. "
                     "Bitte dort schließen und den Export wiederholen.")


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
    # neuer Name „<Nummer>.pdf“, früherer „<Nummer>_<Belegart>_<Kunde>.pdf“, XRechnung „<Nummer>…_XRechnung.xml“
    return [os.path.join(archiv, f) for f in sorted(os.listdir(archiv)) if f.startswith(b["nummer"] + "_") or f.lower() == b["nummer"].lower() + ".pdf"]


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
    w.writerows([csv_zelle(v) for v in z] for z in zeilen)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def csv_pruefer(zeilen):
    """CSV nach Beschreibungsstandard: ohne Kopfzeile, Semikolon, CRLF, Text in Anführungszeichen, UTF-8 ohne BOM."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n", quotechar='"', quoting=csv.QUOTE_MINIMAL)
    for z in zeilen:
        w.writerow(["" if v is None else csv_zelle(v) for v in z])
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
        summe = {k: kfm(sum(float(b[k] or 0) for b in rech)) for k in ("netto", "ust", "brutto")}
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
    _ablegen(ziel)
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
    _ablegen(ziel)
    return {"datei": name, "groesse": os.path.getsize(ziel), "tabellen": {t[1]: len(t[5]) for t in tabellen}}


def liste():
    p = ordner()
    return [{"datei": f, "groesse": os.path.getsize(os.path.join(p, f)),
             "zeit": datetime.fromtimestamp(os.path.getmtime(os.path.join(p, f))).isoformat(timespec="minutes")}
            for f in sorted(os.listdir(p), key=lambda f: os.path.getmtime(os.path.join(p, f)), reverse=True) if f.endswith(".zip")]


# ---------------------------------------------------------------- DATEV-Buchungsstapel (EXTF, Formatversion 13)
DATEV_KONTEN = {
    "03": {"erloes_19": 8400, "erloes_7": 8300, "erloes_13b": 8337, "erloes_eu": 8336, "erloes_0": 8338,
           "aufwand_19": 3400, "aufwand_7": 3300, "aufwand_0": 3200, "debitor": 10000, "kreditor": 70000, "bank": 1200,
           "skonto_gew_19": 8736, "skonto_gew_7": 8731, "skonto_gew_0": 8730, "skonto_erh_19": 3736, "skonto_erh_7": 3731, "skonto_erh_0": 3730},
    "04": {"erloes_19": 4400, "erloes_7": 4300, "erloes_13b": 4337, "erloes_eu": 4336, "erloes_0": 4338,
           "aufwand_19": 5400, "aufwand_7": 5300, "aufwand_0": 5200, "debitor": 10000, "kreditor": 70000, "bank": 1800,
           "skonto_gew_19": 4736, "skonto_gew_7": 4731, "skonto_gew_0": 4730, "skonto_erh_19": 5736, "skonto_erh_7": 5731, "skonto_erh_0": 5730},
}
DATEV_KONTEN_TEXT = {"erloes_19": "Erlöse 19 % USt", "erloes_7": "Erlöse 7 % USt", "erloes_13b": "Erlöse § 13b UStG (Steuerschuld Leistungsempfänger)",
                     "erloes_eu": "Erlöse sonstige Leistungen EU (Reverse Charge)", "erloes_0": "Erlöse nicht steuerbar / steuerfrei",
                     "aufwand_19": "Wareneingang 19 % Vorsteuer", "aufwand_7": "Wareneingang 7 % Vorsteuer", "aufwand_0": "Wareneingang ohne Vorsteuer",
                     "debitor": "Debitor (Sammelkonto Kunden)", "kreditor": "Kreditor (Sammelkonto Lieferanten)", "bank": "Bankkonto (für Bankumsätze)",
                     "skonto_gew_19": "Gewährte Skonti 19 % USt", "skonto_gew_7": "Gewährte Skonti 7 % USt", "skonto_gew_0": "Gewährte Skonti ohne USt",
                     "skonto_erh_19": "Erhaltene Skonti 19 % Vorsteuer", "skonto_erh_7": "Erhaltene Skonti 7 % Vorsteuer",
                     "skonto_erh_0": "Erhaltene Skonti ohne Vorsteuer"}
DATEV_SPALTEN = (
    ["Umsatz (ohne Soll/Haben-Kz)", "Soll/Haben-Kennzeichen", "WKZ Umsatz", "Kurs", "Basis-Umsatz", "WKZ Basis-Umsatz", "Konto",
     "Gegenkonto (ohne BU-Schlüssel)", "BU-Schlüssel", "Belegdatum", "Belegfeld 1", "Belegfeld 2", "Skonto", "Buchungstext", "Postensperre",
     "Diverse Adressnummer", "Geschäftspartnerbank", "Sachverhalt", "Zinssperre", "Beleglink"]
    + [x for i in range(1, 9) for x in (f"Beleginfo - Art {i}", f"Beleginfo - Inhalt {i}")]
    + ["KOST1 - Kostenstelle", "KOST2 - Kostenstelle", "Kost-Menge", "EU-Land u. UStID", "EU-Steuersatz", "Abw. Versteuerungsart",
       "Sachverhalt L+L", "Funktionsergänzung L+L", "BU 49 Hauptfunktionstyp", "BU 49 Hauptfunktionsnummer", "BU 49 Funktionsergänzung"]
    + [x for i in range(1, 21) for x in (f"Zusatzinformation - Art {i}", f"Zusatzinformation- Inhalt {i}")]
    + ["Stück", "Gewicht", "Zahlweise", "Forderungsart", "Veranlagungsjahr", "Zugeordnete Fälligkeit", "Skontotyp", "Auftragsnummer",
       "Buchungstyp", "USt-Schlüssel (Anzahlungen)", "EU-Land (Anzahlungen)", "Sachverhalt L+L (Anzahlungen)", "EU-Steuersatz (Anzahlungen)",
       "Erlöskonto (Anzahlungen)", "Herkunft-Kz", "Buchungs GUID", "KOST-Datum", "SEPA-Mandatsreferenz", "Skontosperre", "Gesellschaftername",
       "Beteiligtennummer", "Identifikationsnummer", "Zeichnernummer", "Postensperre bis", "Bezeichnung SoBil-Sachverhalt",
       "Kennzeichen SoBil-Buchung", "Festschreibung", "Leistungsdatum", "Datum Zuord. Steuerperiode", "Fälligkeit", "Generalumkehr (GU)",
       "Steuersatz", "Land", "Abrechnungsreferenz", "BVV-Position", "EU-Mitgliedstaat u. UStID (Ursprung)", "EU-Steuersatz (Ursprung)",
       "Abw. Skontokonto"])
assert len(DATEV_SPALTEN) == 125
LOHN_GRUPPEN = ("Mitarbeiter", "Finanzamt", "Krankenkasse")


def datev_cfg(e):
    d = dict(e.get("datev") or {})
    skr = d.get("skr") if d.get("skr") in DATEV_KONTEN else "03"
    konten = dict(DATEV_KONTEN[skr])
    for k, v in (d.get("konten") or {}).items():
        if k in konten and str(v).strip().isdigit():
            konten[k] = int(v)
    return {"berater": str(d.get("berater") or "").strip(), "mandant": str(d.get("mandant") or "").strip(), "skr": skr,
            "wj_beginn": max(1, min(12, int(d.get("wj_beginn") or 1))), "sachkontenlaenge": max(4, min(8, int(d.get("sachkontenlaenge") or 4))),
            "konten": konten, "ausgang": d.get("ausgang", True) is not False, "eingang": d.get("eingang", True) is not False,
            "bankumsaetze": bool(d.get("bankumsaetze")), "skonto": d.get("skonto", True) is not False}


def _dt_text(t, n):
    # führende Formelzeichen (= + - @) entfallen: Wird der Stapel in einer Tabellenkalkulation geöffnet, bleibt der Text ein Text
    t = str(t or "").replace("€", "EUR").replace('"', "'").replace("\r", " ").replace("\n", " ").strip().lstrip("=+-@\t ")[:n]
    return '"' + t + '"'


def _dt_betrag(x):
    return f"{abs(float(x)):.2f}".replace(".", ",")


def _dt_beleg(t):
    return re.sub(r"[^A-Za-z0-9$&%*+\-/]", "", str(t or "")).lstrip("+-")[:36]


def _ttmm(iso):
    return f"{iso[8:10]}{iso[5:7]}" if iso and len(iso) >= 10 else ""


def _ttmmjjjj(iso):
    return f"{iso[8:10]}{iso[5:7]}{iso[:4]}" if iso and len(iso) >= 10 else ""


def datev_buchungen(con, von, bis, cfg):
    """Buchungen für den Zeitraum: Ausgangsrechnungen (Debitor an Erlöse) und Eingangsrechnungen (Aufwand an Kreditor), brutto,
    Automatikkonten ohne BU-Schlüssel. Schlussrechnungen nur mit dem Rest nach Abzug der schon gebuchten Abschläge."""
    k = cfg["konten"]
    aus, warnungen = [], []
    if cfg["ausgang"]:
        for b in rechnungen(con, von, bis):
            d = b["daten"]
            s = d.get("summen") or {}
            brutto = kfm(float(b["brutto"] or 0) - float(s.get("abzug_brutto") or 0))
            if abs(brutto) < 0.005:
                continue
            kunde = d.get("kunde") or {}
            satz = float(b["ust_satz"] or 0)
            ustid = re.sub(r"\s", "", str(kunde.get("ustid") or "")).upper()
            if satz >= 18.5:
                gegen = k["erloes_19"]
            elif satz >= 6.5:
                gegen = k["erloes_7"]
            elif d.get("steuer") == "13b":
                gegen = k["erloes_13b"]
            elif ustid and not ustid.startswith("DE"):
                gegen = k["erloes_eu"]
            else:
                gegen = k["erloes_0"]
            if 0 < satz < 6.5 or 7.5 < satz < 18.5:
                warnungen.append(f"{b['nummer']}: ungewöhnlicher Steuersatz {satz:g} % – Konto bitte prüfen")
            aus.append({"betrag": brutto, "sh": "S" if brutto > 0 else "H", "konto": k["debitor"], "gegen": gegen, "datum": b["datum"],
                        "beleg1": _dt_beleg(b["nummer"]), "beleg2": "", "text": f"{ARTNAME.get(b['art'], b['art'])} {kunde.get('kurzname') or ''}",
                        "leistung": b.get("leistungsdatum") or "", "faellig": b.get("faellig") or "",
                        "euid": ustid if ustid and not ustid.startswith("DE") else "", "auftrag": b.get("auftragsnr") or ""})
    if cfg["eingang"]:
        for z in zahlungsauftraege(con, von, bis):
            gruppe = con.execute("SELECT gruppe, datev_konto FROM lieferanten WHERE id=?", (z["lieferant_id"],)).fetchone()
            if gruppe and (gruppe["gruppe"] or "") in LOHN_GRUPPEN:
                continue   # Löhne, Lohnsteuer, Sozialversicherung bucht das Lohnbüro
            betrag = kfm(float(z["betrag"] or 0))
            if abs(betrag) < 0.005:
                continue
            vst = float(z["vorsteuer"] or 0)
            eigen = str((gruppe["datev_konto"] if gruppe else "") or "").strip()
            bu = ""
            if eigen.isdigit():
                konto = int(eigen)
                # kein Automatikkonto: Vorsteuer über den BU-Schlüssel nach dem Satz der Rechnung
                if _konto_steuer(con, cfg, konto) != "auto":
                    bu = "9" if vst >= 18.5 else "8" if vst >= 6.5 else ""
            else:
                konto = k["aufwand_19"] if vst >= 18.5 else k["aufwand_7"] if vst >= 6.5 else k["aufwand_0"]
            datum = z.get("belegdatum") or (z.get("angelegt") or "")[:10]
            aus.append({"betrag": betrag, "sh": "S" if betrag > 0 else "H", "konto": konto, "gegen": k["kreditor"], "datum": datum, "bu": bu,
                        "beleg1": _dt_beleg(z.get("belegnr") or z["nummer"]), "beleg2": _dt_beleg(z["nummer"])[:12],
                        "text": f"{z.get('lieferant') or ''} {z.get('belegnr') or ''}".strip(), "leistung": "", "faellig": z.get("faellig") or "",
                        "euid": "", "auftrag": z.get("auftragsnr") or ""})
    if cfg["bankumsaetze"]:
        offen = con.execute("SELECT COUNT(*) FROM bank_umsaetze WHERE buchung BETWEEN ? AND ? AND (status='offen' OR (status='ignoriert' AND konto IS NULL))",
                            (von, bis)).fetchone()[0]
        if offen:
            warnungen.append(f"{offen} Bankumsätze im Zeitraum ohne Zuordnung bzw. ohne Konto – nicht im Stapel")
        bank_gezahlt = {}   # Zahlungsauftrag → tatsächlich abgebuchter Betrag
        for u in con.execute("SELECT * FROM bank_umsaetze WHERE buchung BETWEEN ? AND ? AND (status='zugeordnet' OR (status='ignoriert' AND konto IS NOT NULL)) "
                             "ORDER BY buchung, id", (von, bis)):
            ziele = _jl(u["ziel"], [])
            bu, beleg = "", ""
            if u["status"] == "ignoriert":
                gegen = int(u["konto"])
                bu = {"v19": "9", "v7": "8", "u19": "3", "u7": "2"}.get(_konto_steuer(con, cfg, gegen), "")
            elif ziele and ziele[0].get("art") == "op":
                gegen, beleg = k["debitor"], ziele[0].get("nummer") or ""
            else:
                gegen, beleg = k["kreditor"], (ziele[0].get("nummer") if ziele else "") or ""
            text = (u["name"] or u["notiz"] or u["zweck"] or "")[:60]
            # auf mehrere Rechnungen aufgeteilt: eine Zeile je Rechnung, wenn die Einzelbeträge den Umsatz ergeben
            teile = [(t.get("nummer") or "", float(t.get("betrag") or 0)) for t in ziele] if u["status"] != "ignoriert" and len(ziele) > 1 else []
            if not teile or any(b_ <= 0 for _, b_ in teile) or abs(kfm(sum(b_ for _, b_ in teile)) - abs(kfm(u["betrag"]))) > 0.009:
                if len(ziele) > 1 and u["status"] != "ignoriert":
                    warnungen.append(f"Bankumsatz vom {_de(u['buchung'])} über {_z(abs(u['betrag']))} EUR gehört zu {len(ziele)} Rechnungen "
                                     f"({', '.join(str(t.get('nummer') or '') for t in ziele)[:80]}) – als eine Buchung im Stapel")
                teile = [(beleg, abs(u["betrag"]))]
            for beleg_, betrag_ in teile:
                aus.append({"betrag": kfm(betrag_), "sh": "S" if u["betrag"] > 0 else "H", "konto": k["bank"], "gegen": gegen, "datum": u["buchung"], "bu": bu,
                            "beleg1": _dt_beleg(beleg_), "beleg2": "", "text": text, "leistung": "", "faellig": "", "euid": "", "auftrag": ""})
            for t in ziele if u["status"] != "ignoriert" else []:
                if t.get("art") == "zahlung" and t.get("betrag") and t.get("rechnung"):
                    bank_gezahlt[int(t["id"])] = float(t["betrag"])
        if cfg["skonto"]:
            aus += _skonto_buchungen(con, von, bis, k, bank_gezahlt)
    return aus, warnungen


def _skonto_buchungen(con, von, bis, k, bank_gezahlt):
    """Skonto als eigene Buchungen, damit auf dem Personenkonto kein Rest bleibt: gewährtes Skonto (Skontokonto an Debitor) aus den
    Zahlungseingängen der Art Skonto; erhaltenes Skonto (Kreditor an Skontokonto) aus den im Zeitraum mit Skonto bezahlten
    Zahlungsaufträgen – nach dem abgebuchten Betrag, sonst nach der Regel des Programms (bezahlt bis zum Skontodatum)."""
    aus = []
    stufe = lambda satz: "19" if satz >= 18.5 else "7" if satz >= 6.5 else "0"   # noqa: E731
    for z in con.execute("SELECT z.datum, z.betrag, o.nummer, o.kunde_id, b.ust_satz, ku.kurzname FROM zahlungseingaenge z "
                         "JOIN offene_posten o ON o.id=z.op_id LEFT JOIN belege b ON b.id=o.beleg_id LEFT JOIN kunden ku ON ku.id=o.kunde_id "
                         "WHERE z.art='Skonto' AND z.datum BETWEEN ? AND ? ORDER BY z.datum, z.id", (von, bis)):
        betrag = kfm(float(z["betrag"] or 0))
        if abs(betrag) < 0.005:
            continue
        aus.append({"betrag": betrag, "sh": "S" if betrag > 0 else "H", "konto": k["skonto_gew_" + stufe(float(z["ust_satz"] if z["ust_satz"] is not None else 19))],
                    "gegen": k["debitor"], "datum": z["datum"], "bu": "", "beleg1": _dt_beleg(z["nummer"]), "beleg2": "",
                    "text": f"Skonto {z['kurzname'] or ''}".strip()[:60], "leistung": "", "faellig": "", "euid": "", "auftrag": ""})
    for z in con.execute("SELECT z.*, l.kurzname AS lieferant, l.gruppe FROM zahlungen z LEFT JOIN lieferanten l ON l.id=z.lieferant_id "
                         "WHERE substr(IFNULL(z.bezahlt,''),1,10) BETWEEN ? AND ? ORDER BY z.bezahlt, z.id", (von, bis)):
        if (z["gruppe"] or "") in LOHN_GRUPPEN or not (z["skonto"] or 0):
            continue
        voll = kfm(float(z["betrag"] or 0))
        if z["id"] in bank_gezahlt:
            skonto = kfm(voll - bank_gezahlt[z["id"]])
            if skonto > kfm(voll * float(z["skonto"]) / 100) + 0.02:   # mehr als das vereinbarte Skonto: keine Skontobuchung unterstellen
                continue
        elif z["skonto_bis"] and (z["bezahlt"] or "")[:10] <= z["skonto_bis"]:
            skonto = kfm(voll - kfm(voll * (1 - float(z["skonto"]) / 100)))
        else:
            continue
        if skonto < 0.005:
            continue
        aus.append({"betrag": skonto, "sh": "S", "konto": k["kreditor"], "gegen": k["skonto_erh_" + stufe(float(z["vorsteuer"] or 0))],
                    "datum": (z["bezahlt"] or "")[:10], "bu": "", "beleg1": _dt_beleg(z["belegnr"] or z["nummer"]), "beleg2": _dt_beleg(z["nummer"])[:12],
                    "text": f"Skonto {z['lieferant'] or ''}".strip()[:60], "leistung": "", "faellig": "", "euid": "", "auftrag": ""})
    return aus


def _konto_steuer(con, cfg, nummer):
    try:
        r = con.execute("SELECT steuer FROM konten WHERE skr=? AND nummer=?", (cfg["skr"], int(nummer))).fetchone()
    except Exception:   # noqa: BLE001 – Kontenplan fehlt
        return ""
    return r["steuer"] if r else ""


def datev_export(con, von, bis, wer=""):
    zeitraum_pruefen(von, bis)
    e = HILFE["einstellungen"](con)
    cfg = datev_cfg(e)
    if not (cfg["berater"].isdigit() and 1001 <= int(cfg["berater"]) <= 9999999) or not (cfg["mandant"].isdigit() and 1 <= int(cfg["mandant"]) <= 99999):
        raise Fehler("Für den DATEV-Export fehlen Berater- und Mandantennummer (vom Steuerberater) – bitte unten im DATEV-Bereich eintragen.")
    # ein Stapel darf nur ein Wirtschaftsjahr umfassen
    def wj(iso):
        j, m = int(iso[:4]), int(iso[5:7])
        return j if m >= cfg["wj_beginn"] else j - 1
    if wj(von) != wj(bis):
        raise Fehler("Ein DATEV-Stapel darf nur ein Wirtschaftsjahr umfassen – bitte den Zeitraum teilen.")
    wj_jahr = wj(von)
    buchungen, warnungen = datev_buchungen(con, von, bis, cfg)
    jetzt_ = datetime.now()
    bez = f"Jahresring {_de(von)[:5]}-{_de(bis)}"[:30]
    kopf = ['"EXTF"', "700", "21", '"Buchungsstapel"', "13", jetzt_.strftime("%Y%m%d%H%M%S") + f"{jetzt_.microsecond // 1000:03d}", "", '"RE"',
            _dt_text(wer or "Jahresring", 25), '""', cfg["berater"], cfg["mandant"], f"{wj_jahr}{cfg['wj_beginn']:02d}01", str(cfg["sachkontenlaenge"]),
            von.replace("-", ""), bis.replace("-", ""), _dt_text(bez, 30), '""', "1", "0", "0", '"EUR"', "", '""', "", "", f'"{cfg["skr"]}"', "", "", '""', '""']
    zeilen = [";".join(kopf), ";".join(f'"{s}"' for s in DATEV_SPALTEN)]
    for b in buchungen:
        f = [""] * 125
        f[0], f[1], f[2] = _dt_betrag(b["betrag"]), f'"{b["sh"]}"', '"EUR"'
        f[6], f[7] = str(b["konto"]), str(b["gegen"])
        f[8] = f'"{b["bu"]}"' if b.get("bu") else ""
        f[9], f[10], f[11] = _ttmm(b["datum"]), _dt_text(b["beleg1"], 36), _dt_text(b["beleg2"], 12)
        f[13] = _dt_text(b["text"], 60)
        f[39] = _dt_text(b["euid"], 15) if b["euid"] else ""
        f[94] = _dt_text(b["auftrag"], 30) if b["auftrag"] else ""
        f[113] = "0"
        f[114] = _ttmmjjjj(b["leistung"])
        f[116] = _ttmmjjjj(b["faellig"])
        for i in (3, 4, 5, 8, 11, 12, 14, 15, 16, 17, 18, 19):
            if f[i] == "":
                f[i] = '""' if i in (5, 8, 11, 15, 19) else ""
        zeilen.append(";".join(f))
    inhalt = ("\r\n".join(zeilen) + "\r\n").encode("cp1252", errors="replace")
    name = f"DATEV_{_sauber(e.get('firma') or 'Jahresring')}_{von}_bis_{bis}.zip".replace(" ", "_")
    csv_name = f"EXTF_Buchungsstapel_{von}_bis_{bis}.csv"
    ziel = os.path.join(ordner(), name)
    summe_aus = kfm(sum(b["betrag"] for b in buchungen if b["konto"] == cfg["konten"]["debitor"]))
    summe_ein = kfm(sum(b["betrag"] for b in buchungen if b["gegen"] == cfg["konten"]["kreditor"] and b["konto"] != cfg["konten"]["bank"]))
    n_bank = sum(1 for b in buchungen if b["konto"] == cfg["konten"]["bank"])
    skonto_konten = {v for k_, v in cfg["konten"].items() if k_.startswith("skonto_")}
    n_skonto = sum(1 for b in buchungen if b["konto"] in skonto_konten or b["gegen"] in skonto_konten)
    info = [f"DATEV-Buchungsstapel {e.get('firma') or ''} – Zeitraum {_de(von)} bis {_de(bis)}",
            f"Erstellt am {jetzt_:%d.%m.%Y %H:%M} mit Jahresring {HILFE['version']} von {wer}", "",
            f"Datei: {csv_name} (DATEV-Format, Buchungsstapel Version 13, Zeichensatz Windows-1252)",
            f"Beraternummer {cfg['berater']}, Mandantennummer {cfg['mandant']}, SKR {cfg['skr']}, Wirtschaftsjahr ab {cfg['wj_beginn']:02d}/{wj_jahr}",
            f"Buchungen: {len(buchungen)} (Ausgangsrechnungen brutto {_z(summe_aus)} EUR, Eingangsrechnungen brutto {_z(summe_ein)} EUR"
            + (f", {n_bank} Bankumsätze)" if n_bank else ")"), "",
            "Kontenzuordnung:"] + [f"  {DATEV_KONTEN_TEXT[k_]}: {v}" for k_, v in cfg["konten"].items()] + [
            "", "Ausgangsrechnungen: Debitor an Erlöskonto, Schlussrechnungen nur mit dem Rest nach Abzug der Abschlagsrechnungen.",
            "Eingangsrechnungen: Aufwandskonto (beim Lieferanten hinterlegt oder Wareneingang nach Vorsteuersatz) an Kreditor.",
            "Löhne, Lohnsteuer und Sozialversicherung sind nicht enthalten." + (" Bankumsätze: Bankkonto an Debitor/Kreditor bzw. an das zugeordnete Sachkonto, "
            "bei mehreren Rechnungen eine Zeile je Rechnung." + (" Skonto: gewährtes Skonto als Skontokonto an Debitor, erhaltenes als Kreditor an Skontokonto "
            f"({n_skonto} Buchungen); die Skontokonten sind Vorgaben und mit der Kanzlei abzustimmen." if cfg["skonto"] else " Skonto ist nicht als eigene Buchung enthalten.")
            if cfg["bankumsaetze"] else " Zahlungen (Bank) bucht die Kanzlei aus den Kontoumsätzen."),
            "Die Buchungen sind nicht festgeschrieben (Festschreibung 0)."] + (["", "Hinweise:"] + [f"  {w}" for w in warnungen] if warnungen else [])
    with zipfile.ZipFile(ziel + ".part", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(csv_name, inhalt)
        z.writestr("LIESMICH.txt", "\r\n".join(info).encode("utf-8"))
        for b in rechnungen(con, von, bis) if cfg["ausgang"] else []:
            for fpfad in belegdateien(b):
                z.write(fpfad, "Belege/Ausgangsrechnungen/" + os.path.basename(fpfad))
        for r in zahlungsauftraege(con, von, bis) if cfg["eingang"] else []:
            p = eingangsdatei(r)
            if p:
                z.write(p, "Belege/Eingangsrechnungen/" + os.path.basename(p))
    _ablegen(ziel)
    return {"datei": name, "groesse": os.path.getsize(ziel), "buchungen": len(buchungen), "ausgang": summe_aus, "eingang": summe_ein, "bank": n_bank,
            "warnungen": warnungen, "csv": csv_name}
