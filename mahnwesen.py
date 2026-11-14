"""Mahnwesen: Mahnstufen (Zahlungserinnerung, Mahnung, Letzte Mahnung), Mahnvorschlag, Verzugszinsen und Druckinhalt."""
from datetime import date, timedelta

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

STANDARD = {"basiszins": 1.52, "stufen": STUFEN}
PAUSCHALE_B2B = 40.0  # § 288 Abs. 5 BGB


def einstellung(e):
    """Mahnwesen-Einstellungen mit Vorgaben aufgefüllt (fehlende Stufen/Felder ergänzt)."""
    m = dict(e.get("mahnwesen") or {})
    stufen = []
    for i, std in enumerate(STUFEN):
        eigen = (m.get("stufen") or [])[i] if i < len(m.get("stufen") or []) else {}
        stufen.append({**std, **{k: v for k, v in (eigen or {}).items() if v is not None}})
    return {"basiszins": float(m.get("basiszins", STANDARD["basiszins"]) or 0), "stufen": stufen}


def _d(iso):
    try:
        return date.fromisoformat((iso or "")[:10])
    except ValueError:
        return None


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


def verzugszinsen(offen, von_iso, bis_iso, basiszins, unternehmer):
    """Zinsen nach § 288 BGB: 5 (Verbraucher) bzw. 9 (Unternehmer) Prozentpunkte über dem Basiszinssatz, taggenau / 365."""
    von, bis = _d(von_iso), _d(bis_iso)
    if not von or not bis or bis <= von or offen <= 0:
        return 0.0, 0, 0.0
    satz = round(basiszins + (9 if unternehmer else 5), 2)
    tage = (bis - von).days
    return round(offen * satz / 100 * tage / 365, 2), tage, satz


def berechnen(op, letzte_liste, stufe_cfg, datum_iso, cfg, unternehmer, mit_zinsen=None, gebuehr=None, mit_pauschale=None):
    """Beträge einer neuen Mahnung. letzte_liste = bisherige Mahnungen dieses Postens (älteste zuerst)."""
    mit_zinsen = stufe_cfg.get("zinsen") if mit_zinsen is None else mit_zinsen
    mit_pauschale = stufe_cfg.get("pauschale") if mit_pauschale is None else mit_pauschale
    gebuehr = float(stufe_cfg.get("gebuehr") or 0) if gebuehr is None else float(gebuehr or 0)
    offen = round(op.get("offen") or 0, 2)
    kosten_bisher = round(op.get("mahnkosten") or 0, 2)
    zinsen, tage, satz = 0.0, 0, 0.0
    if mit_zinsen:
        # Zinsen ab Fälligkeit bzw. ab der letzten Mahnung, die schon Zinsen berechnet hat (nichts doppelt)
        von = op.get("faellig")
        for m in letzte_liste:
            if m.get("zinstage"):
                von = m["datum"]
        zinsen, tage, satz = verzugszinsen(offen, von, datum_iso, cfg["basiszins"], unternehmer)
    pauschale = 0.0
    if mit_pauschale and unternehmer and not any((m.get("pauschale") or 0) > 0 for m in letzte_liste):
        pauschale = PAUSCHALE_B2B
    gesamt = round(offen + kosten_bisher + gebuehr + zinsen + pauschale, 2)
    return {"offen": offen, "kosten_bisher": kosten_bisher, "gebuehr": round(gebuehr, 2), "zinsen": zinsen, "zinstage": tage,
            "zinssatz": satz, "pauschale": pauschale, "gesamt": gesamt}


def inhalt_html(m, d, hilfe):
    """Hauptteil des Mahnschreibens (ohne Briefbogen). m = Mahnung, d = Schnappschuss (m['daten'])."""
    h, de, de_datum, text_html = hilfe["h"], hilfe["de"], hilfe["de_datum"], hilfe["text_html"]
    r = d.get("rechnung") or {}
    zeilen = [(f"Rechnung {h(r.get('nummer', ''))} vom {de_datum(r.get('datum'))}, fällig am {de_datum(r.get('faellig'))}",
               f"{de(r.get('betrag', 0))} €")]
    bezahlt = round((r.get("betrag") or 0) - m["offen"], 2)
    if abs(bezahlt) >= 0.005:
        zeilen.append(("abzüglich bereits bezahlt", f"-{de(bezahlt)} €"))
        zeilen.append(("<b>offener Rechnungsbetrag</b>", f"<b>{de(m['offen'])} €</b>"))
    if m["kosten_bisher"]:
        zeilen.append(("Mahnkosten aus vorherigen Mahnungen", f"{de(m['kosten_bisher'])} €"))
    if m["gebuehr"]:
        zeilen.append(("Mahngebühr", f"{de(m['gebuehr'])} €"))
    if m["zinsen"]:
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
