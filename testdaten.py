"""Jahresring – Testdaten löschen (vor dem Echtbetrieb). Die Sperre im Echtbetrieb, die Sicherung vorher und der
Protokolleintrag liegen beim Aufrufer in app.py."""
import os
import shutil

import material

# von app.py gesetzt: daten, bilder, eingang_pfad, datei_weg
HILFE = {}


TESTDATEN_GRUPPEN = {
    "auftraege": ("Aufträge mit Positionen, Belegen (auch festgeschriebene Rechnungen), Offenen Posten, Mahnungen, Stunden, "
                  "Auftragskosten, Projekten, Auftragsterminen und auftragsbezogenen Briefen/Notizen/Anhängen", True),
    "zahlungen": ("Zahlungsaufträge / Eingangsrechnungen samt hochgeladener Rechnungsdateien", True),
    "personal": ("Arbeitszeiten, Stempelungen, Abwesenheiten, Kontobuchungen und Lohnzahlungen der Mitarbeiter", True),
    "kunden": ("Kunden mit ihrer Korrespondenz (Briefe, E-Mails), Notizen und Anhängen (setzt „Aufträge“ voraus)", False),
    "lieferanten": ("Lieferanten mit Notizen, Anhängen und Rechnungs-Zuordnungen (setzt „Zahlungsaufträge“ voraus)", False),
    "termine": ("Kalendertermine ohne Auftrag", False),
    "arbeitsschutz": ("Unterweisungen samt Unterschriften und Einträge im Verbandbuch aus der Testphase (Gefährdungsbeurteilungen, "
                      "Betriebsanweisungen, Unterweisungsthemen und Datenblätter bleiben)", False),
    "bank": ("Eingelesene Kontoauszüge mit ihren Umsätzen und Zuordnungen", True),
}


def testdaten_loeschen(con, gruppen, zaehler_zuruecksetzen=False, behalten=()):
    """behalten: Auftrags-IDs, die samt allem, was an ihnen hängt (Positionen, Belege, Termine, Notizen, Anhänge, Kosten),
    und samt ihrem Kunden und Projekt erhalten bleiben – für echte Angebote, die schon in der Testphase entstanden sind."""
    g = set(gruppen or [])
    keep = sorted({int(x) for x in behalten or [] if str(x).isdigit()} & {r[0] for r in con.execute("SELECT id FROM auftraege")})
    K = "(" + ",".join(str(i) for i in keep) + ")"          # nur geprüfte Zahlen
    nicht_k = f"(auftrag_id IS NULL OR auftrag_id NOT IN {K})" if keep else ""
    und_nicht_k = f" AND auftrag_id NOT IN {K}" if keep else ""
    if "kunden" in g:
        g.add("auftraege")
    if "lieferanten" in g:
        g.add("zahlungen")
    spalten = {t: {r[1] for r in con.execute(f'PRAGMA table_info("{t}")')}
               for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    pflicht = {t: {r[1] for r in con.execute(f'PRAGMA table_info("{t}")') if r[3]} for t in spalten}   # NOT-NULL-Spalten
    geleert, erg = set(), {}

    def weg(tabelle, wo="", *a):
        if tabelle not in spalten:
            return
        n = con.execute(f"DELETE FROM {tabelle}{' WHERE ' + wo if wo else ''}", a).rowcount
        erg[tabelle] = erg.get(tabelle, 0) + n
        if not wo:
            geleert.add(tabelle)

    def dateien_weg(tabelle, spalte, wo):
        """Zu löschende Zeilen: zugehörige Dateien (E-Mails als .eml, Brief-PDFs) mit entfernen."""
        if tabelle not in spalten or spalte not in spalten[tabelle]:
            return
        for (d,) in con.execute(f"SELECT {spalte} FROM {tabelle} WHERE IFNULL({spalte},'')<>''" + (f" AND ({wo})" if wo else "")).fetchall():
            p = os.path.normpath(d if os.path.isabs(d) else os.path.join(HILFE["daten"], d))
            if p.startswith(os.path.join(HILFE["daten"], "")):
                HILFE["datei_weg"](p)

    def loesen(spalte, ausser=(), ausser_ids=""):
        """Verweise auf gelöschte Datensätze lösen; ist die Spalte Pflicht (NOT NULL), hängt die Zeile ganz daran
        (z. B. cad_importe.auftrag_id) und wird mit gelöscht. ausser_ids: „(1,2)“ – Verweise auf diese bleiben."""
        zusatz = f" AND {spalte} NOT IN {ausser_ids}" if ausser_ids else ""
        for t, cols in spalten.items():
            if spalte in cols and t not in ausser:
                if spalte in pflicht.get(t, ()):
                    con.execute(f"DELETE FROM {t} WHERE {spalte} IS NOT NULL{zusatz}")
                else:
                    con.execute(f"UPDATE {t} SET {spalte}=NULL WHERE {spalte} IS NOT NULL{zusatz}")

    if "auftraege" in g:
        for r in con.execute("SELECT id FROM auftragskosten" + (f" WHERE {nicht_k}" if keep else "")).fetchall():
            material.ak_loeschen(con, r["id"])   # bucht Lagerabgänge zurück
        erg["auftragskosten"] = erg.get("auftragskosten", 0)
        for r in con.execute("SELECT pdf FROM mahnungen WHERE IFNULL(pdf,'')<>''" + (f" AND {nicht_k}" if keep else "")):
            HILFE["datei_weg"](r["pdf"])
        if keep:
            weg("zahlungseingaenge", f"op_id NOT IN (SELECT id FROM offene_posten WHERE auftrag_id IN {K})")
        else:
            weg("zahlungseingaenge")
        for t in ("mahnungen", "offene_posten", "belege", "stunden", "positionen", "montageberichte", "bautagebuch"):
            weg(t, nicht_k) if keep else weg(t)
        dateien_weg("korrespondenz", "datei", "auftrag_id IS NOT NULL" + und_nicht_k)
        dateien_weg("briefe", "pdf", "auftrag_id IS NOT NULL" + und_nicht_k)
        for t in ("termine", "briefe", "notizen", "lagerbewegungen", "korrespondenz", "wiedervorlagen"):
            weg(t, "auftrag_id IS NOT NULL" + und_nicht_k)
        for r in con.execute("SELECT pfad FROM anhaenge WHERE auftrag_id IS NOT NULL" + und_nicht_k):
            HILFE["datei_weg"](r["pfad"])
        weg("anhaenge", "auftrag_id IS NOT NULL" + und_nicht_k)
        loesen("auftrag_id", ausser=("auftraege",), ausser_ids=K if keep else "")
        if keep:
            weg("auftraege", f"id NOT IN {K}")
            weg("projekte", "id NOT IN (SELECT projekt_id FROM auftraege WHERE projekt_id IS NOT NULL)")
            # Dateien: nur entfernen, was zu keinem behaltenen Auftrag gehört (Archiv-PDFs, Positionsbilder); Rapport-, Bautagebuch-
            # und Exportordner bleiben dann unangetastet
            pdfs = {os.path.normcase(os.path.abspath(r["pdf"] if os.path.isabs(r["pdf"]) else os.path.join(HILFE["daten"], r["pdf"])))
                    for r in con.execute("SELECT pdf FROM belege WHERE IFNULL(pdf,'')<>''")}
            for ordner, _, namen in os.walk(os.path.join(HILFE["daten"], "belege")):
                for n in namen:
                    if os.path.normcase(os.path.abspath(os.path.join(ordner, n))) not in pdfs:
                        HILFE["datei_weg"](os.path.join(ordner, n))
            text = " ".join(str(v) for t in ("positionen", "belege") for r in con.execute(f"SELECT * FROM {t}") for v in tuple(r) if isinstance(v, str))
            if os.path.isdir(HILFE["bilder"]):
                alle = os.listdir(HILFE["bilder"])
                benutzt = [os.path.splitext(f)[0] for f in alle if f in text]
                for f in alle:   # Bildvarianten heißen wie das Original mit Zusatz (<Stamm>_<Art>.jpg) und bleiben mit ihm
                    if f not in text and not any(f.startswith(st + "_") for st in benutzt):
                        HILFE["datei_weg"](os.path.join(HILFE["bilder"], f))
        else:
            weg("auftraege")
            weg("projekte")
            shutil.rmtree(os.path.join(HILFE["daten"], "belege"), ignore_errors=True)
            shutil.rmtree(os.path.join(HILFE["daten"], "montage"), ignore_errors=True)
            shutil.rmtree(os.path.join(HILFE["daten"], "bautagebuch"), ignore_errors=True)
            shutil.rmtree(os.path.join(HILFE["daten"], "exporte"), ignore_errors=True)
            if os.path.isdir(HILFE["bilder"]):
                for f in os.listdir(HILFE["bilder"]):
                    HILFE["datei_weg"](os.path.join(HILFE["bilder"], f))
    if "zahlungen" in g:
        for r in con.execute("SELECT datei FROM zahlungen WHERE IFNULL(datei,'')<>''"):
            d = r["datei"]
            HILFE["datei_weg"](d if os.path.isabs(d) else os.path.join(HILFE["eingang_pfad"], d))
        loesen("zahlung_id", ausser=("zahlungen",))
        weg("zahlungen")
        dateien_weg("rechnungspost", "datei", "")
        weg("rechnungspost")
    def signaturen_weg(wo, *a):
        if "signaturen" not in spalten:
            return
        for (d,) in con.execute(f"SELECT datei FROM signaturen WHERE {wo}", a).fetchall():
            if d:
                HILFE["datei_weg"](os.path.join(HILFE["daten"], "unterschriften", os.path.basename(d)))
        weg("signaturen", wo, *a)

    if "personal" in g:
        weg("stunden", "zeit_id IS NOT NULL")
        for t in ("zeiten", "stempel_ereignisse", "abwesenheiten", "kontobuchungen", "lohn"):
            weg(t)
        signaturen_weg("art='monatsbeleg'")
    if "bank" in g:
        weg("bank_umsaetze")
        weg("bank_auszuege")
        shutil.rmtree(os.path.join(HILFE["daten"], "bank"), ignore_errors=True)
    elif "auftraege" in g or "zahlungen" in g:
        # Zuordnungen zu gelöschten Rechnungen bzw. Zahlungsaufträgen lösen; die Umsätze werden wieder zur Zuordnung angeboten
        con.execute("UPDATE bank_umsaetze SET status='offen', ziel='[]', zugeordnet='', von='' WHERE status='zugeordnet'")
    if "arbeitsschutz" in g:
        # Nachweise aus der Testphase; Gefährdungsbeurteilungen, Betriebsanweisungen, Themen und Datenblätter bleiben
        signaturen_weg("art='unterweisung'")
        weg("as_teilnehmer")
        weg("as_unterweisungen")
        weg("as_verbandbuch")
    if "kunden" in g:
        # Kunden der behaltenen Aufträge (und der behaltenen Projekte) bleiben mit ihrer Korrespondenz
        kk = sorted({r[0] for r in con.execute("SELECT kunde_id FROM auftraege WHERE kunde_id IS NOT NULL")}
                    | {r[0] for r in con.execute("SELECT kunde_id FROM projekte WHERE kunde_id IS NOT NULL")}) if keep else []
        KK = "(" + ",".join(str(i) for i in kk) + ")"
        und_nicht_kk = f" AND kunde_id NOT IN {KK}" if kk else ""
        # Korrespondenz der Kunden (E-Mails mit ihren .eml-Dateien, Briefe mit PDF)
        dateien_weg("korrespondenz", "datei", "kunde_id IS NOT NULL" + und_nicht_kk)
        dateien_weg("briefe", "pdf", "kunde_id IS NOT NULL" + und_nicht_kk)
        weg("korrespondenz", "kunde_id IS NOT NULL" + und_nicht_kk)
        weg("briefe", "kunde_id IS NOT NULL" + und_nicht_kk)
        for r in con.execute("SELECT pfad FROM anhaenge WHERE kunde_id IS NOT NULL" + und_nicht_kk):
            HILFE["datei_weg"](r["pfad"])
        for t in ("anhaenge", "notizen", "briefe"):
            weg(t, "kunde_id IS NOT NULL" + und_nicht_kk)
        loesen("kunde_id", ausser=("kunden",), ausser_ids=KK if kk else "")
        weg("kunden", f"id NOT IN {KK}") if kk else weg("kunden")
    if "lieferanten" in g:
        dateien_weg("korrespondenz", "datei", "lieferant_id IS NOT NULL")
        weg("korrespondenz", "lieferant_id IS NOT NULL")
        for r in con.execute("SELECT pfad FROM anhaenge WHERE lieferant_id IS NOT NULL"):
            HILFE["datei_weg"](r["pfad"])
        for t in ("anhaenge", "notizen"):
            weg(t, "lieferant_id IS NOT NULL")
        weg("zuordnungen")
        loesen("lieferant_id", ausser=("lieferanten",))
        weg("lieferanten")
    if "termine" in g:
        weg("termine", "auftrag_id IS NULL")
    if zaehler_zuruecksetzen:
        con.execute("DELETE FROM einstellungen WHERE schluessel='zaehler'")
    # laufende IDs der geleerten Tabellen wieder bei 1 beginnen lassen
    for t in geleert:
        con.execute("DELETE FROM sqlite_sequence WHERE name=?", (t,))
    return {"geloescht": {k: v for k, v in erg.items() if v}, "gruppen": sorted(g),
            "behalten": [r["nummer"] for r in con.execute(f"SELECT nummer FROM auftraege WHERE id IN {K} ORDER BY nummer")] if keep else []}
