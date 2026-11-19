"""Mahnwesen: Mahnstufen (Zahlungserinnerung, Mahnung, Letzte Mahnung), Mahnvorschlag, Verzugszinsen und Druckinhalt."""
from datetime import date, timedelta
from kern import kfm

SCHEMA = """
CREATE TABLE IF NOT EXISTS mahnungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    op_id INTEGER, kunde_id INTEGER, auftrag_id INTEGER,
    stufe INTEGER, nummer TEXT, datum TEXT, frist TEXT,
    offen REAL DEFAULT 0, kosten_bisher REAL DEFAULT 0, gebuehr REAL DEFAULT 0, zinsen REAL DEFAULT 0,
    zinstage INTEGER DEFAULT 0, zinssatz REAL DEFAULT 0, pauschale REAL DEFAULT 0, gesamt REAL DEFAULT 0,
    anschrift TEXT, betreff TEXT, text TEXT, schluss TEXT, daten TEXT,
    pdf TEXT DEFAULT '', versendet TEXT DEFAULT '', versendet_an TEXT DEFAULT '', angelegt TEXT
);
"""

STUFEN = [
    {"kz": "M0", "name": "Zahlungserinnerung", "tage": 7, "frist": 10, "gebuehr": 0.0, "zinsen": False, "pauschale": False,
     "betreff": "Zahlungserinnerung zur Rechnung {nummer}",
     "text": "{anrede}\n\nsicher ist es Ihrer Aufmerksamkeit entgangen: Für meine Rechnung {nummer} vom {datum} konnte ich bis heute "
             "keinen vollständigen Zahlungseingang feststellen. Die Zahlung war am {faellig} fällig.\n\n"
             "Bitte überweisen Sie den offenen Betrag von {zahlbetrag} € bis zum {frist}. Sollten Sie die Zahlung in der "
             "Zwischenzeit bereits veranlasst haben, betrachten Sie dieses Schreiben bitte als gegenstandslos.",
     "schluss": "Mit freundlichen Grüßen",
     "mail_betreff": "Zahlungserinnerung zur Rechnung {nummer}",
     "mail_text": "{anrede}\n\nfür meine Rechnung {nummer} vom {datum} konnte ich bisher keinen vollständigen Zahlungseingang feststellen. "
                  "Im Anhang finden Sie die Zahlungserinnerung und zur Sicherheit noch einmal die Rechnung.\n\n"
                  "Bitte überweisen Sie den offenen Betrag von {zahlbetrag} € bis zum {frist}. Falls Sie schon bezahlt haben, "
                  "betrachten Sie diese Nachricht bitte als gegenstandslos.\n\nMit freundlichen Grüßen"},
    {"kz": "M1", "name": "Mahnung", "tage": 3, "frist": 10, "gebuehr": 2.5, "zinsen": False, "pauschale": False,
     "betreff": "Mahnung zur Rechnung {nummer}",
     "text": "{anrede}\n\nleider konnte ich trotz meiner Zahlungserinnerung vom {letzte_mahnung} bis heute keinen vollständigen "
             "Zahlungseingang für meine Rechnung {nummer} vom {datum} feststellen.\n\n"
             "Bitte überweisen Sie den unten aufgeführten Gesamtbetrag von {zahlbetrag} € bis spätestens {frist}.",
     "schluss": "Mit freundlichen Grüßen",
     "mail_betreff": "Mahnung zur Rechnung {nummer}",
     "mail_text": "{anrede}\n\nleider ist meine Rechnung {nummer} vom {datum} trotz Zahlungserinnerung noch offen. "
                  "Im Anhang erhalten Sie meine Mahnung.\n\nBitte überweisen Sie den Gesamtbetrag von {zahlbetrag} € bis spätestens {frist}.\n\n"
                  "Mit freundlichen Grüßen"},
    {"kz": "M2", "name": "Letzte Mahnung", "tage": 3, "frist": 7, "gebuehr": 5.0, "zinsen": False, "pauschale": False,
     "betreff": "Letzte Mahnung zur Rechnung {nummer}",
     "text": "{anrede}\n\ntrotz Zahlungserinnerung und Mahnung ist meine Rechnung {nummer} vom {datum} bis heute nicht beglichen.\n\n"
             "Ich fordere Sie hiermit letztmalig auf, den unten aufgeführten Gesamtbetrag von {zahlbetrag} € bis spätestens {frist} "
             "zu überweisen. Sollte die Zahlung bis dahin nicht eingehen, werde ich ohne weitere Ankündigung das gerichtliche "
             "Mahnverfahren einleiten. Die dadurch entstehenden Kosten gehen zu Ihren Lasten.",
     "schluss": "Mit freundlichen Grüßen",
     "mail_betreff": "Letzte Mahnung zur Rechnung {nummer}",
     "mail_text": "{anrede}\n\nmeine Rechnung {nummer} vom {datum} ist trotz Zahlungserinnerung und Mahnung weiterhin offen. "
                  "Im Anhang erhalten Sie meine letzte Mahnung.\n\nBitte überweisen Sie den Gesamtbetrag von {zahlbetrag} € bis spätestens {frist}. "
                  "Danach leite ich ohne weitere Ankündigung das gerichtliche Mahnverfahren ein.\n\nMit freundlichen Grüßen"},
]

# Basiszinssatz nach § 247 BGB in Prozent, gültig ab dem genannten Tag (Bekanntmachungen der Deutschen Bundesbank). Er kann sich zum
# 1. Januar und zum 1. Juli ändern. Jedes Halbjahr steht hier, auch wenn der Satz gleich blieb – daran erkennt das Programm, bis wohin
# die Liste gepflegt ist. Neue Halbjahre trägt der Betrieb in den Einstellungen nach (mahnwesen.basiszinsen), bis ein Update sie mitbringt.
BASISZINSEN = [
    ("2002-07-01", 2.47), ("2003-01-01", 1.97), ("2003-07-01", 1.22), ("2004-01-01", 1.14), ("2004-07-01", 1.13), ("2005-01-01", 1.21),
    ("2005-07-01", 1.17), ("2006-01-01", 1.37), ("2006-07-01", 1.95), ("2007-01-01", 2.70), ("2007-07-01", 3.19), ("2008-01-01", 3.32),
    ("2008-07-01", 3.19), ("2009-01-01", 1.62), ("2009-07-01", 0.12), ("2010-01-01", 0.12), ("2010-07-01", 0.12), ("2011-01-01", 0.12),
    ("2011-07-01", 0.37), ("2012-01-01", 0.12), ("2012-07-01", 0.12), ("2013-01-01", -0.13), ("2013-07-01", -0.38), ("2014-01-01", -0.63),
    ("2014-07-01", -0.73), ("2015-01-01", -0.83), ("2015-07-01", -0.83), ("2016-01-01", -0.83), ("2016-07-01", -0.88), ("2017-01-01", -0.88),
    ("2017-07-01", -0.88), ("2018-01-01", -0.88), ("2018-07-01", -0.88), ("2019-01-01", -0.88), ("2019-07-01", -0.88), ("2020-01-01", -0.88),
    ("2020-07-01", -0.88), ("2021-01-01", -0.88), ("2021-07-01", -0.88), ("2022-01-01", -0.88), ("2022-07-01", -0.88), ("2023-01-01", 1.62),
    ("2023-07-01", 3.12), ("2024-01-01", 3.62), ("2024-07-01", 3.37), ("2025-01-01", 2.27), ("2025-07-01", 1.27), ("2026-01-01", 1.27),
    ("2026-07-01", 1.52),
]
STANDARD = {"basiszinsen": [], "stufen": STUFEN}
PAUSCHALE_B2B = 40.0  # § 288 Abs. 5 BGB


def _d(iso):
    try:
        return date.fromisoformat((iso or "")[:10])
    except (ValueError, TypeError):
        return None


def halbjahr(tag=None):
    """Erster Tag des Halbjahres, in dem der Tag liegt (1. Januar oder 1. Juli), als ISO-Datum."""
    t = tag if isinstance(tag, date) else (_d(tag) or date.today())
    return date(t.year, 1 if t.month < 7 else 7, 1).isoformat()


def halbjahre(von_iso, bis_iso):
    """Alle Halbjahresanfänge von … bis … (beide eingeschlossen), als ISO-Daten."""
    t, ende, aus = _d(halbjahr(von_iso)), _d(halbjahr(bis_iso)), []
    while t and ende and t <= ende:
        aus.append(t.isoformat())
        t = date(t.year + (1 if t.month == 7 else 0), 7 if t.month == 1 else 1, 1)
    return aus


def eigene_saetze(liste):
    """Eigene Einträge aus den Einstellungen, geprüft: Stichtag ist ein 1. Januar oder 1. Juli, Satz zwischen −5 und 30 Prozent."""
    aus = {}
    for x in liste if isinstance(liste, list) else []:
        t = _d(x.get("ab")) if isinstance(x, dict) else None
        try:
            satz = round(float(x.get("satz")), 2) if t else None
        except (TypeError, ValueError):
            satz = None
        if t and satz is not None and (t.month, t.day) in ((1, 1), (7, 1)) and -5 <= satz <= 30 and t.year >= 2002:
            aus[t.isoformat()] = satz
    return [{"ab": ab, "satz": s} for ab, s in sorted(aus.items())]


def zinsliste(eigene=None):
    """Hinterlegte Sätze und eigene Einträge, aufsteigend nach Stichtag. Bei gleichem Stichtag zählt der eigene Eintrag."""
    d = dict(BASISZINSEN)
    for x in eigene_saetze(eigene):
        d[x["ab"]] = x["satz"]
    return sorted(d.items())


def basiszins_am(liste, tag_iso):
    """Basiszinssatz am genannten Tag; vor dem ersten Eintrag gilt der erste."""
    tag = str(tag_iso or "")[:10]
    return next((s for ab, s in reversed(liste) if ab <= tag), liste[0][1])


def umstellen(m, heute=None):
    """Frühere Einstellung „basiszins“ (ein Satz für alles) in die Liste mit Stichtagen überführen: Weicht der gespeicherte Satz vom
    hinterlegten Satz des laufenden Halbjahres ab, bleibt er als eigener Eintrag ab diesem Halbjahr erhalten."""
    m = dict(m or {})
    if "basiszins" not in m:
        return m
    alt = m.pop("basiszins")
    eigene = eigene_saetze(m.get("basiszinsen"))
    hj = halbjahr(heute)
    try:
        alt = round(float(alt), 2)
        if abs(alt - basiszins_am(zinsliste(eigene), hj)) > 0.004 and -5 <= alt <= 30:
            eigene = eigene_saetze(eigene + [{"ab": hj, "satz": alt}])
    except (TypeError, ValueError):
        pass
    m["basiszinsen"] = eigene
    return m


def einstellung(e, heute=None):
    """Mahnwesen-Einstellungen mit Vorgaben aufgefüllt (fehlende Stufen/Felder ergänzt). „basiszinsen“ ist die vollständige Liste
    (hinterlegt und eigene), „basiszins“ der heute gültige Satz, „fehlend“ die Halbjahre bis heute ohne Eintrag, „offen“ das erste davon."""
    heute = heute or date.today()
    m = umstellen(e.get("mahnwesen") or {}, heute)
    stufen = []
    for i, std in enumerate(STUFEN):
        eigen = (m.get("stufen") or [])[i] if i < len(m.get("stufen") or []) else {}
        stufen.append({**std, **{k: v for k, v in (eigen or {}).items() if v is not None}})
    eigene = eigene_saetze(m.get("basiszinsen"))
    liste = zinsliste(eigene)
    da = {ab for ab, _ in liste}
    fehlend = [h for h in halbjahre(BASISZINSEN[-1][0], heute) if h not in da]   # Halbjahre seit dem letzten hinterlegten ohne Eintrag
    return {"basiszins": basiszins_am(liste, heute.isoformat()), "basiszinsen": liste, "eigene": eigene,
            "offen": fehlend[0] if fehlend else "", "fehlend": fehlend, "stufen": stufen}


def vorschlag(op, letzte, stufen, heute=None):
    """Nächste Mahnstufe für einen offenen Posten. letzte = letzte Mahnung (dict) oder None.
    Ergebnis: {stufe, kz, name, ab (ISO), jetzt (bool)} oder None, wenn nichts (mehr) zu mahnen ist."""
    heute = heute or date.today()
    if (op.get("offen") or 0) < 0.005 or not op.get("faellig") or op.get("mahnsperre"):
        return None
    if letzte is None:
        n, basis = 0, _d(op["faellig"])
    else:
        n, basis = letzte["stufe"] + 1, _d(letzte.get("frist")) or _d(letzte.get("datum"))
    if basis is None:
        return None
    if n >= len(stufen):
        return {"stufe": None, "kz": "", "name": "alle Mahnstufen durchlaufen", "ab": "", "jetzt": False}
    ab = basis + timedelta(days=int(stufen[n].get("tage") or 0) + 1)
    return {"stufe": n, "kz": stufen[n]["kz"], "name": stufen[n]["name"], "ab": ab.isoformat(), "jetzt": heute >= ab}


def zins_abschnitte(offen, von_iso, bis_iso, basiszins, unternehmer):
    """Zinsen nach § 288 BGB: 5 (Verbraucher) bzw. 9 (Unternehmer) Prozentpunkte über dem Basiszinssatz, taggenau / 365. Verzinst
    werden die Tage nach „von“ bis einschließlich „bis“. Ändert sich der Basiszinssatz in dieser Zeit, entsteht je Zeitraum ein
    Abschnitt mit eigenem Satz und Betrag. basiszins: Liste [(Stichtag, Satz)] oder ein einzelner Satz."""
    von, bis = _d(von_iso), _d(bis_iso)
    if not von or not bis or bis <= von or offen <= 0:
        return []
    liste = basiszins if isinstance(basiszins, list) else [("0001-01-01", float(basiszins or 0))]
    grenzen = [g for g in (_d(ab) for ab, _ in liste) if g]
    zuschlag = 9 if unternehmer else 5
    aus, start = [], von + timedelta(days=1)
    while start <= bis:
        naechste = min((g for g in grenzen if g > start), default=None)
        ende = min(bis, naechste - timedelta(days=1)) if naechste else bis
        basis = basiszins_am(liste, start.isoformat())
        satz, tage = kfm(basis + zuschlag), (ende - start).days + 1
        if aus and abs(aus[-1]["basis"] - basis) < 0.0001:   # gleicher Satz über den Stichtag hinweg: ein Abschnitt
            aus[-1].update(bis=ende.isoformat(), tage=aus[-1]["tage"] + tage)
        else:
            aus.append({"von": start.isoformat(), "bis": ende.isoformat(), "tage": tage, "basis": basis, "satz": satz})
        start = ende + timedelta(days=1)
    for a in aus:
        a["betrag"] = kfm(offen * a["satz"] / 100 * a["tage"] / 365)
    return aus


def verzugszinsen(offen, von_iso, bis_iso, basiszins, unternehmer):
    """Summe der Verzugszinsen, Zinstage und der zuletzt geltende Zinssatz (siehe zins_abschnitte)."""
    ab = zins_abschnitte(offen, von_iso, bis_iso, basiszins, unternehmer)
    if not ab:
        return 0.0, 0, 0.0
    return kfm(sum(a["betrag"] for a in ab)), sum(a["tage"] for a in ab), ab[-1]["satz"]


def berechnen(op, letzte_liste, stufe_cfg, datum_iso, cfg, unternehmer, mit_zinsen=None, gebuehr=None, mit_pauschale=None):
    """Beträge einer neuen Mahnung. letzte_liste = bisherige Mahnungen dieses Postens (älteste zuerst)."""
    mit_zinsen = stufe_cfg.get("zinsen") if mit_zinsen is None else mit_zinsen
    mit_pauschale = stufe_cfg.get("pauschale") if mit_pauschale is None else mit_pauschale
    gebuehr = float(stufe_cfg.get("gebuehr") or 0) if gebuehr is None else float(gebuehr or 0)
    offen = kfm(op.get("offen") or 0)
    kosten_bisher = kfm(op.get("mahnkosten") or 0)
    zinsen, tage, satz, abschnitte = 0.0, 0, 0.0, []
    if mit_zinsen:
        # Zinsen ab Fälligkeit bzw. ab der letzten Mahnung, die schon Zinsen berechnet hat (nichts doppelt)
        von = op.get("faellig")
        for m in letzte_liste:
            if m.get("zinstage"):
                von = m["datum"]
        abschnitte = zins_abschnitte(offen, von, datum_iso, cfg.get("basiszinsen") or cfg.get("basiszins") or 0, unternehmer)
        if abschnitte:
            zinsen, tage, satz = kfm(sum(a["betrag"] for a in abschnitte)), sum(a["tage"] for a in abschnitte), abschnitte[-1]["satz"]
    pauschale = 0.0
    if mit_pauschale and unternehmer and not any((m.get("pauschale") or 0) > 0 for m in letzte_liste):
        pauschale = PAUSCHALE_B2B
    gesamt = kfm(offen + kosten_bisher + gebuehr + zinsen + pauschale)
    return {"offen": offen, "kosten_bisher": kosten_bisher, "gebuehr": kfm(gebuehr), "zinsen": zinsen, "zinstage": tage,
            "zinssatz": satz, "zinsabschnitte": abschnitte, "pauschale": pauschale, "gesamt": gesamt}


def inhalt_html(m, d, hilfe):
    """Hauptteil des Mahnschreibens (ohne Briefbogen). m = Mahnung, d = Schnappschuss (m['daten'])."""
    h, de, de_datum, text_html = hilfe["h"], hilfe["de"], hilfe["de_datum"], hilfe["text_html"]
    r = d.get("rechnung") or {}
    zeilen = [(f"Rechnung {h(r.get('nummer', ''))} vom {de_datum(r.get('datum'))}, fällig am {de_datum(r.get('faellig'))}",
               f"{de(r.get('betrag', 0))} €")]
    bezahlt = kfm((r.get("betrag") or 0) - m["offen"])
    if abs(bezahlt) >= 0.005:
        zeilen.append(("abzüglich bereits bezahlt", f"-{de(bezahlt)} €"))
        zeilen.append(("<b>offener Rechnungsbetrag</b>", f"<b>{de(m['offen'])} €</b>"))
    if m["kosten_bisher"]:
        zeilen.append(("Mahnkosten aus vorherigen Mahnungen", f"{de(m['kosten_bisher'])} €"))
    if m["gebuehr"]:
        zeilen.append(("Mahngebühr", f"{de(m['gebuehr'])} €"))
    if m["zinsen"]:
        teile = d.get("zinsabschnitte") or []
        if len(teile) > 1:   # der Basiszinssatz hat sich im Verzugszeitraum geändert: jeden Zeitraum mit seinem Satz ausweisen
            klein = "<br>".join(f"{de_datum(a['von'])} bis {de_datum(a['bis'])}: {a['tage']} Tage zu {de(a['satz'])} % p. a. = {de(a['betrag'])} €" for a in teile)
            zeilen.append((f"Verzugszinsen auf {de(m['offen'])} € für {m['zinstage']} Tage<br><small>{klein}</small>", f"{de(m['zinsen'])} €"))
        else:
            zeilen.append((f"Verzugszinsen {de(m['zinssatz'])} % p. a. auf {de(m['offen'])} € für {m['zinstage']} Tage", f"{de(m['zinsen'])} €"))
    if m["pauschale"]:
        zeilen.append(("Verzugspauschale nach § 288 Abs. 5 BGB", f"{de(m['pauschale'])} €"))
    zeilen.append((f"<b>Zu zahlen bis {de_datum(m['frist'])}</b>", f"<b>{de(m['gesamt'])} €</b>"))
    tabelle = "".join(f'<tr><td>{a}</td><td class="r nw">{b}</td></tr>' for a, b in zeilen)
    vorher = d.get("vorherige") or []
    vorher_html = ""
    if vorher:
        vorher_html = '<p class="klein">Bisher: ' + ", ".join(f"{h(x['name'])} vom {de_datum(x['datum'])}" for x in vorher) + "</p>"
    return f"""
<h1>{h(d.get('stufenname') or '')}</h1>
<div class="betreff">{h(m.get('betreff') or '')}</div>
<div class="einl rt">{text_html(m.get('text') or '', False)}</div>
<table class="mahn">{tabelle}</table>
{vorher_html}
{hilfe.get('zahlung') or ''}
<div class="ende"><div class="schluss rt">{text_html(m.get('schluss') or '', False)}</div>
{hilfe.get('gruss_html') or '<div class="gruss">' + h(hilfe.get('gruss') or '') + '</div>'}</div>
<style>
table.mahn {{ width: 100%; border-collapse: collapse; margin: 4mm 0 2mm; page-break-inside: avoid; }}
table.mahn td {{ padding: 1.6mm 1.5mm; border-bottom: .3pt solid #ccc; vertical-align: top; }}
table.mahn tr:last-child td {{ border-top: .8pt solid #333; border-bottom: .8pt solid #333; }}
</style>"""
