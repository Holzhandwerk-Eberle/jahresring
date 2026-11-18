"""Nachweis von Änderungen an Stammdaten und Einstellungen (GoBD: nachvollziehbar, wer wann was geändert hat).

Rechnungen frieren Kunde, Betrieb und Bankverbindung beim Festschreiben ein – der Beleg bleibt also richtig, auch wenn die
Stammdaten später anders lauten. Was bisher fehlte, ist die Spur der Änderung selbst: Wer hat wann die IBAN eines Lieferanten,
das Zahlungsziel eines Kunden oder die Bankverbindung des Betriebs geändert? Dieses Modul vergleicht den Stand vor und nach
einer Änderung und schreibt eine Zeile ins Protokoll.

Was im Protokoll steht, lässt sich nie mehr löschen. Deshalb gilt: Zahlen und Schalter mit ihrem alten und neuen Wert,
Bankverbindungen verkürzt (DE02 … 2051), Namen, Anschriften, Kontaktdaten und Lohnangaben nur als Tatsache („Anschrift
geändert“) – ohne den Inhalt. Die Person steht mit ihrer Nummer da, nicht mit ihrem Namen.
"""
import json

# von app.py gesetzt: prot(con, art, objekt, text, daten)
HILFE = {}


def maske(iban):
    """IBAN verkürzt: Anfang und Ende genügen, um eine Änderung zu erkennen."""
    t = "".join(str(iban or "").split()).upper()
    if not t:
        return "leer"
    return f"{t[:4]} … {t[-4:]}" if len(t) > 10 else "…" + t[-2:]


def _wert(v):
    if v in (None, ""):
        return "leer"
    if isinstance(v, bool):
        return "ein" if v else "aus"
    if isinstance(v, float) and v == int(v):
        v = int(v)
    return str(v)[:60]


# je Tabelle: Felder mit Wert, verkürzte Felder (Bankverbindung), Gruppen als bloße Tatsache
TABELLEN = {
    "kunden": {
        "name": "Kunde",
        "werte": {"zahlungsziel": "Zahlungsziel (Tage)", "skonto": "Skonto %", "skontotage": "Skontotage", "rabatt": "Rabatt %", "ust": "USt-Satz",
                  "preise": "Preisanzeige", "rechnungsformat": "Rechnungsformat", "gruppe": "Gruppe", "aktiv": "aktiv", "waehrung": "Währung",
                  "zahlungskonto": "Zahlungskonto"},
        "maske": {},
        "fakten": {"Name": ("kurzname", "anrede", "anredeform", "titel", "vorname", "nachname", "firma", "zusatz"),
                   "Anschrift": ("anschrift", "strasse", "hausnr", "plz", "ort", "land"),
                   "Rechnungsanschrift": ("rechnungsanschrift", "rechnungsort", "rechnungsland"),
                   "Lieferanschrift": ("lieferanschrift", "lieferort", "lieferland"),
                   "Kontaktdaten": ("telefon", "telefax", "email1", "email2", "email3", "email4", "website"),
                   "USt-IdNr.": ("ustid",), "Leitweg-ID": ("leitweg_id",), "Artikelpreise": ("artikelpreise",)},
    },
    "lieferanten": {
        "name": "Lieferant",
        "werte": {"zahlungsziel": "Zahlungsziel (Tage)", "skonto": "Skonto %", "skontotage": "Skontotage", "vorsteuer": "Vorsteuer %", "zahlkonto": "Zahlungskonto",
                  "datev_konto": "DATEV-Konto", "gruppe": "Gruppe", "aktiv": "aktiv", "bic": "BIC"},
        "maske": {"iban": "IBAN"},
        "fakten": {"Name": ("kurzname", "anrede", "anredeform", "titel", "vorname", "nachname", "firma", "zusatz"),
                   "Anschrift": ("anschrift", "strasse", "hausnr", "plz", "ort", "land"),
                   "Kontaktdaten": ("telefon", "telefax", "email1", "email2", "email3", "email4", "website"),
                   "abweichender Zahlungsempfänger": ("empfaenger",), "USt-IdNr.": ("ustid",), "unsere Kundennummer": ("unsere_kundennr",)},
    },
    "mitarbeiter": {
        "name": "Mitarbeiter",
        "werte": {"bic": "BIC"},
        "maske": {"iban": "IBAN"},
        "fakten": {"Name": ("vorname", "nachname", "kuerzel"), "Anschrift": ("strasse", "plz", "ort"), "Kontaktdaten": ("telefon", "email"),
                   "Lohnangaben": ("lohnart", "lohngruppe", "stundenlohn", "gehalt", "kostensatz"), "Eintritt, Austritt oder Status": ("eintritt", "austritt", "aktiv"),
                   "Arbeitszeitmodell": ("modelle",), "Startwerte der Zeitkonten": ("konten_ab", "ueberstunden_start", "urlaub_start"),
                   "Geburtsdatum": ("geburtsdatum",), "Krankenkasse oder Zuordnung": ("kasse_id", "lieferant_id")},
    },
}

# Einstellungen: mit Wert, verkürzt, als Schalter – alles Übrige als Tatsache mit dieser Bezeichnung (oder dem Schlüssel)
EINST_WERT = {"firma": "Firmenname", "firma_inhaber": "Inhaber", "steuernummer": "Steuernummer", "ustid": "USt-IdNr.", "sepa_bic": "BIC des Betriebs",
              "sepa_name": "Kontoinhaber", "bank_name": "Bank", "rechnungsnr_praefix": "Vorsatz der Rechnungsnummer", "sicherung_ziel": "Ziel der Sicherung",
              "projektpfad": "Projektordner", "sitzung_tage_buero": "Dauer der Anmeldung (Büro, Tage)", "sitzung_tage_mitarbeiter": "Dauer der Anmeldung (Mitarbeiter, Tage)",
              "frist_rechnung_jahre": "Aufbewahrungsfrist für Rechnungen (Jahre)", "umsatz_basis": "Umsatz nach", "lohnanteil": "Ausweis des Lohnanteils",
              "kundennr_start": "erste Kundennummer", "lieferantennr_start": "erste Lieferantennummer", "angebot_gueltig_tage": "Gültigkeit von Angeboten (Tage)",
              "lagerpreis_methode": "Bewertung des Lagers"}
EINST_MASKE = {"sepa_iban": "IBAN des Betriebs"}
EINST_SCHALTER = {"netzwerk": "Netzwerkfreigabe", "zugferd": "E-Rechnung im PDF (ZUGFeRD)", "girocode": "GiroCode auf Rechnungen", "briefvorlage_aktiv": "Briefbogen",
                  "seitenzahlen": "Seitenzahlen", "unten_buendig": "Schluss unten bündig", "uebertrag": "Übertrag bei mehrseitigen Belegen",
                  "vorsorge_nur_inhaber": "Vorsorge und Exposition nur für den Inhaber", "hinweis_14b": "Hinweis nach § 14b UStG", "status_automatik": "Status-Automatik",
                  "ordner_automatisch": "Projektordner automatisch anlegen", "app_fenster": "Programmfenster",
                  "start_arbeitsschutz": "Erinnerungen des Arbeitsschutzes auf der Startseite"}
EINST_FAKT = {"firma_anschrift": "Firmenanschrift", "firma_telefon": "Telefon des Betriebs", "firma_email": "E-Mail des Betriebs", "firma_web": "Internetadresse",
              "firma_zusatz": "Zusatzzeile des Betriebs", "absenderzeile": "Absenderzeile", "mail": "E-Mail-Versand", "update": "Update-Einstellungen",
              "https": "https-Zugang", "projektsicherung": "Sicherung des Projektordners", "mahnwesen": "Mahnwesen (Stufen, Gebühren, Zinsen)", "datev": "DATEV-Export",
              "kalk_vorgaben": "Kalkulationsvorgaben", "zaehler": "Zählerstände", "zahlungskonten": "Zahlungskonten", "bezahlarten": "Zahlarten",
              "beleg_texte": "Belegtexte", "beleg_varianten": "eigene Belegarten", "mail_texte": "Mailtexte", "brief_layout": "Maße des Briefbogens",
              "agb_bei": "AGB-Zuordnung", "pdf_ordner": "Ablageordner der PDFs", "ordnerschema": "Schema der Projektordner", "unterordner": "Unterordner im Projektordner",
              "sollplaene": "Arbeitszeitpläne", "feiertage_wahl": "Feiertage", "frei_wahl": "arbeitsfreie Tage", "tage_eigene": "eigene freie Tage",
              "google_kalender": "abonnierte Kalender", "netz_adressen": "zugelassene Adressen im Netz", "verfahrensdoku": "Verfahrensdokumentation",
              "datenschutzdoku": "Datenschutzunterlagen", "text_14b": "Text des Hinweises nach § 14b UStG", "rechnung_zusatz": "Zusatztext auf Rechnungen",
              "text_lohnanteil": "Text zum Lohnanteil", "zahlungsplan_text": "Text des Zahlungsplans", "kundengruppen": "Kundengruppen",
              "lieferantengruppen": "Lieferantengruppen", "auftragsstatus": "Auftragsstatus", "wiedervorlage_regeln": "Regeln für Wiedervorlagen"}
# Einstellungen, die sich bei der täglichen Arbeit von selbst ändern oder nur die Anzeige betreffen: kein Protokolleintrag
EINST_STILL = {"auskunft_speicherorte", "auskunft_empfaenger"}


def zeile(con, tabelle, rid):
    try:
        r = con.execute(f"SELECT * FROM {tabelle} WHERE id=?", (rid,)).fetchone()
    except Exception:  # noqa: BLE001 – Tabelle gibt es (noch) nicht
        return None
    return dict(r) if r else None


def _gleich(a, b):
    if a in (None, "") and b in (None, ""):
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def stammdaten(con, tabelle, vorher, nachher):
    """Vergleicht zwei Stände einer Stammdatenzeile und schreibt bei Unterschieden eine Protokollzeile."""
    cfg = TABELLEN[tabelle]
    if not vorher or not nachher:
        return None
    teile, felder, werte = [], [], {}
    for k, name in cfg["werte"].items():
        if k in vorher and not _gleich(vorher.get(k), nachher.get(k)):
            teile.append(f"{name} {_wert(vorher.get(k))} → {_wert(nachher.get(k))}")
            felder.append(k)
            werte[k] = [vorher.get(k), nachher.get(k)]
    for k, name in cfg["maske"].items():
        if k in vorher and not _gleich("".join(str(vorher.get(k) or "").split()).upper(), "".join(str(nachher.get(k) or "").split()).upper()):
            teile.append(f"{name} {maske(vorher.get(k))} → {maske(nachher.get(k))}")
            felder.append(k)
    for name, gruppe in cfg["fakten"].items():
        geaendert = [k for k in gruppe if k in vorher and not _gleich(vorher.get(k), nachher.get(k))]
        if geaendert:
            teile.append(f"{name} geändert")
            felder += geaendert
    if not teile:
        return None
    nr = nachher.get("nummer") or vorher.get("nummer") or nachher.get("id")
    return HILFE["prot"](con, "stammdaten", f"{cfg['name']} {nr}", f"{cfg['name']} {nr} geändert: " + "; ".join(teile),
                         {"tabelle": tabelle, "id": nachher.get("id"), "felder": felder, "werte": werte})


def einstellungen_stand(con):
    return {r[0]: r[1] for r in con.execute("SELECT schluessel, wert FROM einstellungen")}


GEHEIM = {"mail": "passwort", "update": "schluessel"}   # verschlüsselt abgelegte Angaben: Der Ablagewert ändert sich bei jedem Speichern


def _teile(k, a, n, neu_gesetzt):
    """Welche Angaben einer zusammengesetzten Einstellung (E-Mail-Versand, Update) sich geändert haben – nie mit Inhalt.
    Das Passwort zählt nur, wenn wirklich ein neues eingegeben wurde."""
    a, n = (a if isinstance(a, dict) else {}), (n if isinstance(n, dict) else {})
    namen = {"adresse": "Adresse", "name": "Absendername", "smtp_server": "Postausgangsserver", "smtp_port": "Port", "smtp_modus": "Verschlüsselung",
             "benutzer": "Benutzername", "passwort": "Passwort", "schluessel": "Zugangsschlüssel", "imap_server": "Posteingangsserver",
             "gesendet_ablegen": "Ablage im Ordner „Gesendet“", "kopie_an_mich": "Kopie an mich", "html": "Darstellung", "logo_in_signatur": "Logo in der Signatur"}
    g = [namen.get(x, x) for x in sorted(set(a) | set(n)) if x != GEHEIM[k] and a.get(x) != n.get(x)]
    if neu_gesetzt:
        g.append(namen[GEHEIM[k]])
    return g[:10]


def einstellungen(con, vorher, nachher, geheim_neu=()):
    teile, felder, werte = [], [], {}
    for k in sorted(set(vorher) | set(nachher)):
        alt, neu = vorher.get(k), nachher.get(k)
        if alt == neu or k.startswith("_") or k in EINST_STILL:
            continue
        try:
            a, n = (json.loads(alt) if alt is not None else None), (json.loads(neu) if neu is not None else None)
        except ValueError:
            a, n = alt, neu
        if a == n:
            continue
        felder.append(k)
        if k in EINST_WERT:
            teile.append(f"{EINST_WERT[k]} {_wert(a)} → {_wert(n)}")
            werte[k] = [a if not isinstance(a, (dict, list)) else None, n if not isinstance(n, (dict, list)) else None]
        elif k in EINST_MASKE:
            teile.append(f"{EINST_MASKE[k]} {maske(a)} → {maske(n)}")
        elif k in EINST_SCHALTER:
            teile.append(f"{EINST_SCHALTER[k]} {'ein' if n else 'aus'}geschaltet")
            werte[k] = [bool(a), bool(n)]
        elif k in GEHEIM:
            g = _teile(k, a, n, k in geheim_neu)
            if not g:
                felder.pop()
                continue
            teile.append(f"{EINST_FAKT[k]} geändert ({', '.join(g)})")
        else:
            teile.append(f"{EINST_FAKT.get(k) or 'Einstellung „' + k + '“'} geändert")
    if not teile:
        return None
    text = "Einstellungen geändert: " + "; ".join(teile)
    return HILFE["prot"](con, "einstellung", "Einstellungen", text[:900] + (" …" if len(text) > 900 else ""), {"felder": felder, "werte": werte})


class Rahmen:
    """Umschließt eine schreibende Anfrage: hält vorher den Stand fest und schreibt nach gelungener Änderung ins Protokoll.
    Verwendung: with verbindung() as con, nachweis.Rahmen(con, methode, teile, daten): …"""

    def __init__(self, con, methode, teile, daten=None):
        self.con, self.art, self.rid, self.vorher = con, None, None, None
        if methode != "PUT" or not teile:
            return
        # (vor dem Speichern festhalten – danach steht dort der verschlüsselte Wert)
        self.geheim_neu = {k for k, feld in GEHEIM.items() if isinstance((daten or {}).get(k), dict) and daten[k].get(feld)}
        if teile[0] in TABELLEN and len(teile) == 2 and teile[1].isdigit():
            self.art, self.rid = teile[0], int(teile[1])
        elif teile[0] == "einstellungen" and len(teile) == 1:
            self.art = "einstellungen"

    def __enter__(self):
        if self.art == "einstellungen":
            self.vorher = einstellungen_stand(self.con)
        elif self.art:
            self.vorher = zeile(self.con, self.art, self.rid)
        return self

    def __exit__(self, typ, wert, spur):
        if typ is None and self.art and self.vorher is not None:
            try:
                if self.art == "einstellungen":
                    einstellungen(self.con, self.vorher, einstellungen_stand(self.con), self.geheim_neu)
                else:
                    stammdaten(self.con, self.art, self.vorher, zeile(self.con, self.art, self.rid))
            except Exception as f:  # noqa: BLE001 – der Nachweis darf das Speichern nicht verhindern
                print("Nachweis der Änderung nicht geschrieben:", f)
        return False
