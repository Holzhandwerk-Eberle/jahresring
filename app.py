#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jahresring – lokale Auftrags- und Kundenverwaltung
Start: Doppelklick auf start.bat (Windows) bzw. "python app.py"
Benötigt nur Python 3.8+ (keine Zusatzpakete).
"""
import base64
import pdfseiten
import io
import uuid
import hashlib
import json
import mimetypes
import os
import re
import shutil
import ssl
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
import math

import kalender as kal
import erechnung
import mailversand
import werkstatt
import material
import kundenimport
import adressen
import mahnwesen
import eingangsrechnung
import werkzeuge
import stuecklistenimport
import vorlagen
import geheim
import xmlansicht
import epruefung
import service
import tresor
import binascii
import gzip
import projektsicherung
import bank
import testdaten
import monatsbeleg
import arbeitsschutz_web
from monatsbeleg import monatsbeleg_hash, monatsbeleg_hash_v1, monatsbeleg_signaturen, monatsbeleg_unterschreiben, monatsbeleg_sig_bilder  # noqa: F401
from arbeitsschutz_web import zeichen_liste, arbeitsschutz_api, stempel_arbeitsschutz, as_druck_name, as_druck_html  # noqa: F401
from kern import ApiFehler, jetzt, zahl, jl, de, de_datum, h, plus_tage
from sepa import iban_normal, iban_ok, ibanFormat_py, sepa_xml
import liquiditaet
import preise
import wiedervorlage
import konten
import kalkulation
import benutzer
import personal
import montage
import reste
import protokoll
import export
import projekte
import bautagebuch
import korrespondenz
import arbeitsschutz
import unterschrift
import secrets

from kalkulation import (KALK_VORGABEN, TAETIGKEITEN_VORGABE, TAETIGKEITEN_KATALOG, TAETIGKEITEN_KATALOG_STAND, WERKSTOFF_TYPEN, LOHNGRUPPEN,
                         KATEGORIEN, position_rechnen, vorgaben_kopie, lohn_von, gk_von, f as fl)
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

BASIS = os.path.dirname(os.path.abspath(__file__))
DATEN = os.path.join(BASIS, "daten")
DB_PFAD = os.path.join(DATEN, "buero.db")
ANHANG_PFAD = os.path.join(DATEN, "anhaenge")
VORLAGEN_PFAD = os.path.join(DATEN, "vorlagen")
VORLAGEN_NAMEN = ("brief", "agb_verbraucher", "agb_unternehmen")
BACKUP_PFAD = os.path.join(DATEN, "backup")
STATIC = os.path.join(BASIS, "static")
PORT = int(os.environ.get("BUERO_PORT", "8765"))
MAX_ANFRAGE = 300 * 1024 * 1024   # größte angenommene Anfrage (Uploads als Base64)
VERSION = "2026.11.01-135"

SCHEMA = """
CREATE TABLE IF NOT EXISTS kunden (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer INTEGER UNIQUE NOT NULL,
    kurzname TEXT NOT NULL DEFAULT '',
    gruppe TEXT DEFAULT '',
    aktiv INTEGER DEFAULT 1,
    anschrift TEXT DEFAULT '',
    plz TEXT DEFAULT '',
    ort TEXT DEFAULT '',
    land TEXT DEFAULT 'Deutschland',
    anrede TEXT DEFAULT '',
    telefon TEXT DEFAULT '',
    email1 TEXT DEFAULT '', email2 TEXT DEFAULT '', email3 TEXT DEFAULT '', email4 TEXT DEFAULT '',
    telefax TEXT DEFAULT '',
    website TEXT DEFAULT '',
    bemerkungen TEXT DEFAULT '',
    merkmale TEXT DEFAULT '',
    waehrung TEXT DEFAULT 'EUR',
    ust REAL DEFAULT 19,
    ustid TEXT DEFAULT '',
    zahlungsziel INTEGER DEFAULT 14,
    skontotage INTEGER DEFAULT 0,
    skonto REAL DEFAULT 0,
    preise TEXT DEFAULT 'brutto',
    rabatt REAL DEFAULT 0,
    artikelpreise TEXT DEFAULT 'VK-Preis 1',
    rechnungsformat TEXT DEFAULT 'PDF',
    zahlungskonto TEXT DEFAULT '',
    lieferantennr TEXT DEFAULT '',
    leitweg_id TEXT DEFAULT '',
    lieferanschrift TEXT DEFAULT '',
    lieferort TEXT DEFAULT '',
    lieferland TEXT DEFAULT 'Deutschland',
    rechnungsanschrift TEXT DEFAULT '',
    rechnungsort TEXT DEFAULT '',
    rechnungsland TEXT DEFAULT 'Deutschland',
    angelegt TEXT,
    geaendert TEXT
);
CREATE TABLE IF NOT EXISTS auftraege (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer TEXT UNIQUE NOT NULL,
    kunde_id INTEGER NOT NULL REFERENCES kunden(id),
    bezeichnung TEXT DEFAULT '',
    gruppe TEXT DEFAULT '',
    status TEXT DEFAULT '',
    fertigung TEXT DEFAULT '',
    lieferung TEXT DEFAULT '',
    bemerkungen TEXT DEFAULT '',
    ordner TEXT DEFAULT '',
    angelegt TEXT,
    geaendert TEXT
);
CREATE TABLE IF NOT EXISTS anhaenge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kunde_id INTEGER REFERENCES kunden(id),
    auftrag_id INTEGER REFERENCES auftraege(id),
    dateiname TEXT NOT NULL,
    pfad TEXT NOT NULL,
    groesse INTEGER DEFAULT 0,
    angelegt TEXT
);
CREATE TABLE IF NOT EXISTS notizen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kunde_id INTEGER REFERENCES kunden(id),
    auftrag_id INTEGER REFERENCES auftraege(id),
    text TEXT NOT NULL,
    angelegt TEXT
);
CREATE TABLE IF NOT EXISTS offene_posten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer TEXT, art TEXT, kunde_id INTEGER, auftrag_id INTEGER,
    datum TEXT, betrag REAL, faellig TEXT, offen REAL, mahnstufe INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS briefe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer TEXT, kunde_id INTEGER, auftrag_id INTEGER, betreff TEXT, empfaenger TEXT,
    briefart TEXT, datum TEXT, status TEXT, termin TEXT, text TEXT
);
CREATE TABLE IF NOT EXISTS einstellungen (
    schluessel TEXT PRIMARY KEY,
    wert TEXT
);
CREATE TABLE IF NOT EXISTS lieferanten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer INTEGER UNIQUE NOT NULL,
    kurzname TEXT NOT NULL DEFAULT '',
    gruppe TEXT DEFAULT '',
    aktiv INTEGER DEFAULT 1,
    anschrift TEXT DEFAULT '',
    plz TEXT DEFAULT '',
    ort TEXT DEFAULT '',
    land TEXT DEFAULT 'Deutschland',
    anrede TEXT DEFAULT 'Sehr geehrte Damen und Herren,',
    telefon TEXT DEFAULT '',
    email1 TEXT DEFAULT '', email2 TEXT DEFAULT '', email3 TEXT DEFAULT '', email4 TEXT DEFAULT '',
    telefax TEXT DEFAULT '',
    website TEXT DEFAULT '',
    bemerkungen TEXT DEFAULT '',
    merkmale TEXT DEFAULT '',
    vorsteuer REAL DEFAULT 19,
    zahlungsziel INTEGER DEFAULT 30,
    skontotage INTEGER DEFAULT 0,
    skonto REAL DEFAULT 0,
    zahlkonto TEXT DEFAULT '',
    unsere_kundennr TEXT DEFAULT '',
    empfaenger TEXT DEFAULT '',
    info_zahlung TEXT DEFAULT '',
    iban TEXT DEFAULT '',
    bic TEXT DEFAULT '',
    bestell_kopf TEXT DEFAULT '',
    bestell_zeile TEXT DEFAULT '',
    angelegt TEXT,
    geaendert TEXT
);
CREATE TABLE IF NOT EXISTS zahlungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer TEXT UNIQUE NOT NULL,
    lieferant_id INTEGER NOT NULL REFERENCES lieferanten(id),
    auftrag_id INTEGER REFERENCES auftraege(id),
    belegnr TEXT DEFAULT '',
    belegdatum TEXT DEFAULT '',
    bemerkung TEXT DEFAULT '',
    empfaenger TEXT DEFAULT '',
    iban TEXT DEFAULT '',
    bic TEXT DEFAULT '',
    betrag REAL DEFAULT 0,
    vorsteuer REAL DEFAULT 19,
    skonto REAL DEFAULT 0,
    skonto_bis TEXT DEFAULT '',
    faellig TEXT DEFAULT '',
    bezahlt TEXT DEFAULT '',
    bezahlung TEXT DEFAULT 'Überweisung',
    angelegt TEXT,
    geaendert TEXT
);
CREATE TABLE IF NOT EXISTS positionen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auftrag_id INTEGER NOT NULL REFERENCES auftraege(id),
    parent_id INTEGER,
    titel INTEGER DEFAULT 0,
    sort REAL DEFAULT 0,
    gesperrt INTEGER DEFAULT 0,
    gruppe TEXT DEFAULT '',
    status TEXT DEFAULT '',
    menge REAL DEFAULT 1,
    einheit TEXT DEFAULT 'Stk.',
    text TEXT DEFAULT '',
    masse TEXT DEFAULT '{}',
    einzelpreis REAL DEFAULT 0,
    preis_manuell INTEGER DEFAULT 0,
    zeige TEXT DEFAULT '{"posnr":1,"anzahl":1,"ep":1,"gp":1}',
    unterdruck TEXT DEFAULT 'anzahl_text',
    stueckliste TEXT DEFAULT '[]',
    beschlaege TEXT DEFAULT '[]',
    zeiten TEXT DEFAULT '[]',
    zeitmodus TEXT DEFAULT 'taetigkeiten',
    extras TEXT DEFAULT '{}',
    angelegt TEXT,
    geaendert TEXT
);
CREATE TABLE IF NOT EXISTS belege (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auftrag_id INTEGER NOT NULL REFERENCES auftraege(id),
    kunde_id INTEGER, art TEXT NOT NULL, lfd INTEGER DEFAULT 0, nummer TEXT DEFAULT '', status TEXT DEFAULT 'entwurf',
    datum TEXT DEFAULT '', leistungsdatum TEXT DEFAULT '', betreff TEXT DEFAULT '', anschrift TEXT DEFAULT '',
    einleitung TEXT DEFAULT '', schluss TEXT DEFAULT '', daten TEXT DEFAULT '{}',
    netto REAL DEFAULT 0, ust_satz REAL DEFAULT 19, ust REAL DEFAULT 0, brutto REAL DEFAULT 0, zahlbetrag REAL DEFAULT 0,
    zahlungsziel INTEGER DEFAULT 14, faellig TEXT DEFAULT '', bezug_id INTEGER, pdf TEXT DEFAULT '',
    angelegt TEXT, geaendert TEXT
);
CREATE TABLE IF NOT EXISTS zahlungseingaenge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    op_id INTEGER NOT NULL, datum TEXT, betrag REAL DEFAULT 0, art TEXT DEFAULT '', bemerkung TEXT DEFAULT '', angelegt TEXT
);
CREATE TABLE IF NOT EXISTS termine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auftrag_id INTEGER REFERENCES auftraege(id),
    typ TEXT DEFAULT '', titel TEXT DEFAULT '', von TEXT NOT NULL, bis TEXT NOT NULL,
    zeit_von TEXT DEFAULT '', zeit_bis TEXT DEFAULT '', stunden REAL, notiz TEXT DEFAULT '', erledigt INTEGER DEFAULT 0,
    angelegt TEXT, geaendert TEXT
);
CREATE TABLE IF NOT EXISTS stunden (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auftrag_id INTEGER NOT NULL REFERENCES auftraege(id),
    datum TEXT, stunden REAL DEFAULT 0, kst TEXT DEFAULT '', gruppe TEXT DEFAULT '', taetigkeit TEXT DEFAULT '',
    angelegt TEXT
);
"""

# Spalten, die in bestehenden Datenbanken nachgerüstet werden
NACHRUESTEN = [
    ("belege", "artname", "TEXT DEFAULT ''"),   # Name einer eigenen Belegart (Variante), sonst leer
    ("auftraege", "leitstand", "TEXT DEFAULT ''"),
    ("auftraege", "projekt_id", "INTEGER"),
    ("kunden", "geburtstag", "TEXT DEFAULT ''"),
    ("briefe", "pdf", "TEXT DEFAULT ''"),
    ("briefe", "angelegt", "TEXT DEFAULT ''"),
    ("kunden", "newsletter_aus", "INTEGER DEFAULT 0"),
    ("stunden", "titel", "INTEGER DEFAULT 0"),
    ("zeiten", "titel", "INTEGER DEFAULT 0"),
    ("auftraege", "leitstand_sort", "REAL DEFAULT 0"),
    ("kunden", "anredeform", "TEXT DEFAULT ''"),
    ("kunden", "titel", "TEXT DEFAULT ''"),
    ("kunden", "vorname", "TEXT DEFAULT ''"),
    ("kunden", "nachname", "TEXT DEFAULT ''"),
    ("kunden", "firma", "TEXT DEFAULT ''"),
    ("kunden", "zusatz", "TEXT DEFAULT ''"),
    ("kunden", "strasse", "TEXT DEFAULT ''"),
    ("kunden", "hausnr", "TEXT DEFAULT ''"),
    ("lieferanten", "anredeform", "TEXT DEFAULT ''"),
    ("lieferanten", "titel", "TEXT DEFAULT ''"),
    ("lieferanten", "vorname", "TEXT DEFAULT ''"),
    ("lieferanten", "nachname", "TEXT DEFAULT ''"),
    ("lieferanten", "firma", "TEXT DEFAULT ''"),
    ("lieferanten", "zusatz", "TEXT DEFAULT ''"),
    ("lieferanten", "strasse", "TEXT DEFAULT ''"),
    ("lieferanten", "hausnr", "TEXT DEFAULT ''"),

    ("auftraege", "kunde_daten", "TEXT DEFAULT ''"),
    ("positionen", "bilder", "TEXT DEFAULT '[]'"),
    ("belege", "kompakt", "INTEGER DEFAULT 0"),
    ("belege", "versendet", "TEXT DEFAULT ''"),
    ("belege", "versendet_an", "TEXT DEFAULT ''"),
    ("anhaenge", "lieferant_id", "INTEGER"),
    ("notizen", "lieferant_id", "INTEGER"),
    ("briefe", "lieferant_id", "INTEGER"),
    ("briefe", "ihr_zeichen", "TEXT DEFAULT ''"),
    ("termine", "mitarbeiter", "TEXT DEFAULT '[]'"),
    ("notizen", "art", "TEXT DEFAULT ''"),
    ("notizen", "benutzer", "TEXT DEFAULT ''"),
    ("briefe", "unser_zeichen", "TEXT DEFAULT ''"),
    ("auftraege", "kalk", "TEXT DEFAULT ''"),
    ("auftraege", "titel", "TEXT DEFAULT '[]'"),
    ("auftraege", "titel_druck", "TEXT DEFAULT 'titel'"),
    ("offene_posten", "beleg_id", "INTEGER"),
    ("auftraege", "plan_von", "TEXT DEFAULT ''"),
    ("auftraege", "plan_bis", "TEXT DEFAULT ''"),
    ("lieferanten", "datev_konto", "TEXT DEFAULT ''"),
    ("stunden", "termin_id", "INTEGER"),
    ("auftraege", "nachgefasst", "TEXT DEFAULT ''"),
    ("offene_posten", "mahnkosten", "REAL DEFAULT 0"),
    ("positionen", "alternativ", "INTEGER DEFAULT 0"),
    ("belege", "druck", "TEXT DEFAULT '{}'"),
    ("lieferanten", "ustid", "TEXT DEFAULT ''"),
    ("zahlungen", "datei", "TEXT DEFAULT ''"),
    ("material", "ean", "TEXT DEFAULT ''"),
    ("werkzeuge", "nutzungsdauer", "REAL"),
    ("stunden", "zeit_id", "INTEGER"),
    ("material", "cad", "TEXT DEFAULT ''"),
    ("material", "plattenlaenge", "REAL DEFAULT 0"),
    ("kunden", "aufbewahren_bis", "TEXT DEFAULT ''"),
    ("material", "plattenbreite", "REAL DEFAULT 0"),
    ("stunden", "mitarbeiter_id", "INTEGER"),
    ("offene_posten", "mahnsperre", "INTEGER DEFAULT 0"),
    ("zahlungseingaenge", "auf_mahnkosten", "REAL DEFAULT 0"),
    ("mitarbeiter", "geburtsdatum", "TEXT DEFAULT ''"),
]

STANDARD_EINSTELLUNGEN = {
    "firma": "",
    "projektpfad": "",
    "ordnerschema": "{auftrag}_{projekt}_KD{kundennr}_{name}",
    "ordner_automatisch": True,
    "projekt_sammelordner": False,
    "zuschnitt_zugabe": dict(werkstatt.ZUSCHNITT_VORGABE),
    "lagerpreis_methode": "mittel",
    # Größe der Etiketten vom Etikettendrucker in mm (Teile- und Restetiketten im Zuschnittprogramm, QR-Etiketten für Material und Reste)
    "etikett_breite": 70, "etikett_hoehe": 74,
    "werkstatt_ordner": "50_Werkstatt",
    "konstruktion_ordner": "20_Konstruktion",   # Stücklisten-Export aus dem CAD für den Import in die Stückliste
    "bezug_eigen": [],
    "geburtstag_tage": 14,
    "posteingang_minuten": 15,
    "posteingang_ordner": ["Kundenkontakt"],
    "rechnung_ordner": ["Rechnungen"],   # Mailordner, in dem Lieferantenrechnungen liegen (wird zusätzlich zum Posteingang durchsucht)
    "zahlbest_vorschlagen": True,
    "zahlbest_betreff": "Zahlungseingang zu {belegart} {rechnung}",
    "zahlbest_text": "{anrede}\n\nvielen Dank für Ihre Zahlung über {betrag} €, die am {zahlungsdatum} bei uns eingegangen ist. "
                     "Damit ist unsere {belegart} {rechnung} vom {rechnungsdatum} zum Auftrag {auftrag} ({bezeichnung}) {status}.\n\n"
                     "{schlusssatz}\n\nMit freundlichen Grüßen",
    "zahlbest_schluss_rechnung": "Ich habe mich gefreut, für Sie arbeiten zu dürfen.",
    "zahlbest_schluss_abschlag": "Ich freue mich auf die weitere Arbeit an Ihrem Auftrag.",
    "geburtstag_betreff": "Herzlichen Glückwunsch zum Geburtstag",
    "geburtstag_text": "{anrede}\n\nzu Ihrem Geburtstag wünsche ich Ihnen von Herzen alles Gute, Gesundheit und ein schönes neues Lebensjahr.\n\nHerzliche Grüße",
    "taetigkeiten_katalog": [],
    "pos_vorlagen": [vorlagen.beispiel_system32(), vorlagen.beispiel_korpus()],   # variable Positionsvorlagen (Maße abfragen → Stückliste)
    "kundennr_start": 100000,
    "unterschrift_hoehe": 17,
    # Zahlungsplan in Angebot, Kostenvoranschlag und Auftragsbestätigung (Druckeinstellung „Konditionen: Zahlungsplan“)
    "zahlungsplan_text": "Individueller Zahlungsplan: {anzahlung} % Anzahlung, zahlbar nach Erhalt der Akonto-Rechnung. "
                         "Restzahlung {rest_tage} Tage nach Leistungserbringung.",
    "zahlungsplan_lieferung": "Lieferung ca. {lieferwochen} Wochen nach Eingang der Anzahlung.",
    "zahlungsplan_rest": 10,   # Höhe der eingescannten Unterschrift im Beleg und Brief (mm)
    "kundengruppen": ["Privatkunde", "Geschäftskunde", "Öffentlicher Auftraggeber"],
    "auftragsgruppen": ["Maßmöbel", "Innenausbau", "Objekteinrichtung", "Reparatur"],
    "auftragsstatus": ["Anfrage", "Angebot", "Auftrag", "Fertigung", "Montage", "Abgerechnet", "Erledigt", "Abgesagt"],
    "zahlungskonten": ["Hausbank"],
    "laender": ["Deutschland", "Österreich", "Schweiz", "Liechtenstein"],
    "lieferantennr_start": 700000,
    "lieferantengruppen": ["Plattenwerkstoffe", "Massivholz", "Beschläge", "Oberfläche", "Werkzeug & Maschinen",
                           "Dienstleister", "Versicherungen", "Finanzamt", "Sonstiges"],
    "bezahlarten": ["Überweisung", "Lastschrift", "Bar", "EC-Karte", "Kreditkarte", "PayPal"],
    "sepa_name": "",
    "sepa_iban": "",
    "sepa_bic": "",
    "unterordner": [],
    "kalk_vorgaben": {},
    "taetigkeiten": TAETIGKEITEN_VORGABE,
    "taetigkeit_listen": None,
    "girocode": True,
    "app_fenster": True,
    "netzwerk": False,
    # Angaben für den Auskunftsbrief nach Art. 15 DSGVO; betriebseigene Systeme ergänzt der Betrieb in den Einstellungen
    "auskunft_speicherorte": "Büroprogramm Jahresring auf dem Rechner des Betriebs, Projektordner des Betriebs, E-Mail-Postfach",
    "auskunft_empfaenger": "Finanzverwaltung (Steuererklärungen, Prüfungen), E-Mail-Anbieter für den Versand, Bank beim Zahlungsverkehr",
    "https": "aus",   # aus | zusaetzlich (http und https) | nur (andere Geräte werden auf https umgeleitet)
    "sicherung_ziel": "",
    # Projektordner auf das externe Sicherungsziel sichern: täglich ab der Uhrzeit, frühere Fassungen so viele Tage behalten (0 = immer)
    "projektsicherung": dict(projektsicherung.STANDARD),
    "zeit_gemeinkosten": ["Aufräumen", "Maschinenpflege", "Holz stapeln", "Besorgungen", "Büro", "Sonstiges"],
    "zeit_rundung": 0,
    "leitstand_schritte": ["Arbeitsvorbereitung", "Zuschnitt", "Hobeln", "Kanten", "Fräsen", "Bankraum", "Oberfläche", "Endkontrolle",
                           "Montage", "Nacharbeiten", "Fertig"],
    "leitstand_status_map": {},
    "leitstand_status": ["Auftrag", "Fertigung", "Montage"],
    "rechnungsnr_praefix": "",
    "zaehler": {},
    "material_gruppen": material.STANDARD_GRUPPEN,
    "lagerorte": ["Werkstatt", "Lager"],
    "zuschnitt_url": "",
    "zuschnitt_ordner": "40_Kalkulation",
    "verfahrensdoku": {},
    "datenschutzdoku": {},   # ausgefüllte Felder der Datenschutz-Dokumentation (hilfe/datenschutz.html)
    "mail": {},
    "mail_texte": {},
    "mahnwesen": mahnwesen.STANDARD,
    "zugferd": True,
    # Mengeneinheiten für Positionen, Kostenliste und Materialstamm (Einstellungen › Allgemein › Auswahllisten)
    "einheiten": ["lfm.", "m²", "m³", "Stk.", "Std.", "Pauschale", "Paar", "Satz", "Garnitur", "Dose", "Rolle", "Tube", "Packung", "Liter", "kg"],
    "positionsgruppen": ["Möbel", "Innenausbau", "Montage", "Material", "Sonstiges"],
    "positionsstatus": ["Angeboten", "Beauftragt", "In Arbeit", "Fertig", "Geliefert"],
    "textbausteine": [
        {"name": "Hinweis Möbeloberflächen", "text": "Hinweis zu Möbeloberflächen:\nGrundsätzlich sollen Verschmutzungen unmittelbar mit einem feuchten Tuch von der Oberfläche Ihrer Möbel entfernt werden. Folgende Mittel können die Oberfläche von Möbeln nachhaltig schädigen und dürfen deshalb nicht zur Reinigung verwendet werden:\n\n· Keine scheuernden oder abrasiven Mittel (z.B. Edelstahl Pads, Schwämme mit Schleifvlies, Reinigungsmilch, Reinigungspulver, etc.)\n\n· Keine stark konzentrierten Säuren und Laugen\n\n· Keine Reinigungsmittel wie Sanitärreiniger oder Chlorreiniger\n\n· Keine Poliermittel\n\nReinigungsmittel in jedem Fall sparsam, vorsichtig und nur im verschmutzten Bereich anwenden.\nAuf keinen Fall über längere Zeit einwirken lassen.\nDirektes Schneiden mit Messern auf Möbeloberflächen kann zu Schnittspuren führen. Verwenden Sie stets eine Unterlage.\nWischen Sie Wasser (Feuchtigkeit) im Fugenbereich stets weg."},
        {"name": "Inkl. Lieferung und Montage", "text": "Inkl. Lieferung und Montage"},
    ],
    "firma_inhaber": "",
    "firma_anschrift": "",
    "firma_telefon": "",
    "firma_email": "",
    "firma_web": "",
    "steuernummer": "",
    "ustid": "",
    "bank_name": "",
    "firma_zusatz": "",
    "absenderzeile": "",
    "beleg_texte": {},
    "hinweis_14b": True,
    "text_14b": "",
    "lohnanteil": "privat",   # Arbeitskosten nach § 35a EStG ausweisen: "privat", "alle", "nie"
    "lohnanteil_wg": True,    # Wagnis und Gewinn anteilig zum Arbeitspreis rechnen (sonst nur Lohn mit Gemeinkosten)
    "land_immer": False,      # Land auch bei Inlandsanschriften in die Briefanschrift
    "angebot_gueltig_tage": 7,   # Platzhalter {gueltig_bis} im Angebotstext = Belegdatum + Tage
    "text_lohnanteil": ("Im Rechnungsbetrag sind Arbeitskosten (Lohn-, Maschinen- und Fahrtkosten) in Höhe von {lohn_netto} € netto "
                        "zzgl. {lohn_ust} € Umsatzsteuer, zusammen {lohn_brutto} €, enthalten. Diese können Sie als Handwerkerleistung "
                        "nach § 35a EStG in Ihrer Steuererklärung angeben."),
    "rechnung_zusatz": "",
    "pdf_ordner": {"angebot": "Angebot", "kv": "Angebot", "ab": "Angebot", "lieferschein": "Liefer", "abnahme": "Liefer",
                   "abschlag": "Rechnung", "rechnung": "Rechnung", "storno": "Rechnung", "gutschrift": "Rechnung", "korrektur": "Rechnung"},
    "google_kalender": [],
    "termin_typen": [{"name": "Aufmaß", "farbe": "#7a8f9e"}, {"name": "Planung", "farbe": "#8e7cc3"},
                     {"name": "Fertigung", "farbe": "#b8834f"}, {"name": "Oberfläche", "farbe": "#c9a227"},
                     {"name": "Montage", "farbe": "#4d7a45"}, {"name": "Lieferung", "farbe": "#3d7ea6"},
                     {"name": "Sonstiges", "farbe": "#9a9087"}],
    "tagesstunden": 8,
    "nachfass_tage": 10,
    "briefvorlage_aktiv": True,
    "brief_layout": {"oben": 32, "unten": 40, "links": 26, "rechts": 18, "adresse_oben": 45, "info_links": 127,
                     "info_oben": 90, "inhalt_start": 105},
    "agb_bei": ["angebot"],
    "seitenzahlen": True, "seitenzahl_unten": 6, "seitenzahl_rechts": 18,
    "unten_buendig": True,   # Summen, Konditionen, Schlusstext und Gruß unten auf der letzten Seite
    "agb_verbraucher_gruppen": ["Privatkunde"],
    "anfrage_tage": 7,
    "ziel_stundensatz": 0,
    "typ_kst": {"Aufmaß": "AVORBER", "Planung": "AVORBER", "Fertigung": "BANKRAUM", "Oberfläche": "OBERFLÄ",
                "Montage": "MONTAGE", "Lieferung": "FAHRZEIT"},
    "status_angebot": ["Anfrage", "Angebot"],
    "status_ende": ["Abgerechnet", "Erledigt", "Abgesagt"],
    "umsatz_basis": "zahlung",
    "status_automatik": {
        "auftrag": {"angebot": "Angebot", "kv": "Angebot", "ab": "Auftrag", "lieferschein": "", "abnahme": "", "abschlag": "", "rechnung": "Abgerechnet",
                    # Datum im Auftrag eingetragen („Fertigung begonnen“ / „Geliefert am“); wirkt nur, wenn es den Status in der Liste gibt
                    "datum_fertigung": "Fertigung", "datum_lieferung": "Geliefert"},
        "position": {"angebot": "Angeboten", "kv": "Angeboten", "ab": "Beauftragt", "lieferschein": "Geliefert", "abnahme": "", "abschlag": "", "rechnung": ""}},
    "zeitraum_drucken": True,
    "beleg_varianten": [{"key": "v13b", "name": "Rechnung", "basis": "rechnung", "steuer": "13b",
                         "bemerkung": "§ 13b UStG: Bauleistungen an Unternehmer, ohne Umsatzsteuer", "einleitung": "", "schluss": ""}],
    "feiertage_wahl": {},      # {Schlüssel: True/False}, fehlt ein Schlüssel, gilt die Vorgabe (Baden-Württemberg)
    "frei_wahl": {},           # arbeitsfreie, nicht bezahlte Tage
    "tage_eigene": [],         # [{name, datum "TT.MM", art: feiertag|frei}]
    "sollplaene": [],          # Sollstundenpläne mit Zuschlägen (personal.zuschlaege)
    "wiedervorlage_regeln": wiedervorlage.REGELN,   # Wiedervorlagen nach dem Festschreiben einer Rechnung
    "datev": {},               # DATEV-Export: berater, mandant, skr ("03"/"04"), wj_beginn, sachkontenlaenge, konten {…}, ausgang, eingang
    "rohertrag_ohne_gruppen": ["Mitarbeiter", "Finanzamt", "Krankenkasse", "Krankenkassen", "Versicherungen", "Werkzeug & Maschinen"],
    "ist_kategorien": {"Plattenwerkstoffe": "werkstoffe", "Massivholz": "werkstoffe", "Beschläge": "beschlaege",
                       "Oberfläche": "oberflaeche", "Dienstleister": "fremdleistungen"},
}

LIEFERANT_FELDER = [
    "nummer", "kurzname", "gruppe", "aktiv", "anschrift", "plz", "ort", "land", "anrede",
    "telefon", "email1", "email2", "email3", "email4", "telefax", "website", "bemerkungen", "merkmale",
    "vorsteuer", "zahlungsziel", "skontotage", "skonto", "zahlkonto", "unsere_kundennr", "empfaenger",
    "info_zahlung", "iban", "bic", "bestell_kopf", "bestell_zeile", "ustid", "datev_konto",
] + adressen.FELDER
ZAHLUNG_FELDER = ["lieferant_id", "auftrag_id", "belegnr", "belegdatum", "bemerkung", "empfaenger", "iban", "bic",
                  "betrag", "vorsteuer", "skonto", "skonto_bis", "faellig", "bezahlt", "bezahlung"]

KUNDE_FELDER = [
    "nummer", "kurzname", "gruppe", "aktiv", "anschrift", "plz", "ort", "land", "anrede",
    "telefon", "email1", "email2", "email3", "email4", "telefax", "website", "bemerkungen",
    "merkmale", "waehrung", "ust", "ustid", "zahlungsziel", "skontotage", "skonto", "preise",
    "rabatt", "artikelpreise", "rechnungsformat", "zahlungskonto", "lieferantennr", "leitweg_id",
    "lieferanschrift", "lieferort", "lieferland", "rechnungsanschrift", "rechnungsort", "rechnungsland",
    "geburtstag", "newsletter_aus", "aufbewahren_bis",
] + adressen.FELDER
AUFTRAG_FELDER = ["kunde_id", "bezeichnung", "gruppe", "status", "fertigung", "lieferung", "bemerkungen", "ordner",
                  "plan_von", "plan_bis", "nachgefasst", "projekt_id"]

SUCHFELDER = {
    "alle": ["kurzname", "anschrift", "plz", "ort", "merkmale", "bemerkungen", "telefon",
             "email1", "email2", "email3", "email4", "CAST(nummer AS TEXT)"],
    "kurzname": ["kurzname"],
    "nummer": ["CAST(nummer AS TEXT)"],
    "anschrift": ["anschrift"],
    "ort": ["plz", "ort"],
    "telefon": ["telefon"],
    "email": ["email1", "email2", "email3", "email4"],
    "merkmale": ["merkmale"],
}


def verbindung():
    con = sqlite3.connect(DB_PFAD, timeout=30)   # Wartezeit auf die Schreibsperre bei gleichzeitigem Speichern
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA synchronous = NORMAL")   # im WAL-Modus sicher und deutlich schneller beim Speichern
    con.create_function("ulower", 1, lambda s: s.lower() if isinstance(s, str) else s)
    return con


def zeilen(rows):
    return [dict(r) for r in rows]


def vorlagen_einrichten():
    os.makedirs(VORLAGEN_PFAD, exist_ok=True)
    start = os.path.join(BASIS, "vorlagen_start")
    if not os.path.isdir(start):
        return
    for name in VORLAGEN_NAMEN:
        if not vorlage_dateien(name):
            for f in sorted(os.listdir(start)):
                if f.startswith(name + "-"):
                    shutil.copyfile(os.path.join(start, f), os.path.join(VORLAGEN_PFAD, f))
        # AGB: das Original-PDF dazulegen, solange noch die mitgelieferte AGB-Vorlage benutzt wird
        orig = os.path.join(start, name + ".pdf")
        if name.startswith("agb") and os.path.isfile(orig) and not os.path.isfile(os.path.join(VORLAGEN_PFAD, name + ".pdf")):
            gleich = True
            for f in vorlage_dateien(name):
                a, b = os.path.join(VORLAGEN_PFAD, f), os.path.join(start, f)
                if not os.path.isfile(b) or os.path.getsize(a) != os.path.getsize(b):
                    gleich = False
            if gleich and vorlage_dateien(name):
                shutil.copyfile(orig, os.path.join(VORLAGEN_PFAD, name + ".pdf"))


def agb_original(name):
    """Pfad des Original-PDFs einer AGB-Vorlage (wird unverändert ans Beleg-PDF gehängt) oder None."""
    p = os.path.join(VORLAGEN_PFAD, name + ".pdf") if name else None
    return p if p and os.path.isfile(p) else None


def vorlage_dateien(name):
    if not os.path.isdir(VORLAGEN_PFAD):
        return []
    fs = [f for f in os.listdir(VORLAGEN_PFAD) if re.fullmatch(re.escape(name) + r"-\d+\.(svg|png|jpg)", f)]
    return sorted(fs, key=lambda f: int(re.search(r"-(\d+)\.", f).group(1)))


def init_db():
    os.makedirs(DATEN, exist_ok=True)
    os.makedirs(ANHANG_PFAD, exist_ok=True)
    with verbindung() as con:
        con.executescript(SCHEMA)
        material.schema(con)
        con.executescript(mahnwesen.SCHEMA)
        werkzeuge.schema(con)
        benutzer.schema(con)
        personal.schema(con)
        montage.schema(con)
        reste.schema(con)
        projekte.schema(con)
        bautagebuch.schema(con)
        korrespondenz.schema(con)
        unterschrift.schema(con)
        arbeitsschutz.schema(con)
        bank.schema(con)
        wiedervorlage.schema(con)
        konten.schema(con)
        alt_v = con.execute("SELECT wert FROM einstellungen WHERE schluessel='programm_version'").fetchone()
        alt_v = json.loads(alt_v[0]) if alt_v else ""
        protokoll.einrichten(con, DATEN, VERSION)
        if alt_v != VERSION:
            protokoll.eintragen(con, "version", VERSION, f"Programmversion {alt_v or '(Erstinstallation)'} → {VERSION}",
                                {"von": alt_v, "nach": VERSION}, benutzer="Programm", version=VERSION)
        con.execute("INSERT OR REPLACE INTO einstellungen VALUES ('programm_version', ?)", (json.dumps(VERSION),))
        # Mail-Passwort unter Windows an das Benutzerkonto gebunden verschlüsseln (DPAPI), falls noch im Klartext
        mz = con.execute("SELECT wert FROM einstellungen WHERE schluessel='mail'").fetchone()
        if mz:
            m = json.loads(mz[0] or "{}")
            if m.get("passwort") and not str(m["passwort"]).startswith(geheim.PRAEFIX):
                vs = geheim.verschluesseln(m["passwort"])
                if vs != m["passwort"]:
                    m["passwort"] = vs
                    con.execute("UPDATE einstellungen SET wert=? WHERE schluessel='mail'", (json.dumps(m, ensure_ascii=False),))
        con.execute(CAD_SCHEMA)
        con.execute(RECHNUNGSPOST_SCHEMA)
        con.execute("CREATE TABLE IF NOT EXISTS zuordnungen (id INTEGER PRIMARY KEY AUTOINCREMENT, lieferant_id INTEGER, schluessel TEXT, "
                    "ziel TEXT, material_id INTEGER, kostenart TEXT DEFAULT '', angelegt TEXT, UNIQUE(lieferant_id, schluessel))")
        for tab, spalte, typ in NACHRUESTEN:
            vorhanden = [r["name"] for r in con.execute(f"PRAGMA table_info({tab})")]
            if spalte not in vorhanden:
                con.execute(f"ALTER TABLE {tab} ADD COLUMN {spalte} {typ}")
        for k, v in STANDARD_EINSTELLUNGEN.items():
            con.execute("INSERT OR IGNORE INTO einstellungen VALUES (?, ?)", (k, json.dumps(v, ensure_ascii=False)))
        eigene_dokumente_uebernehmen(bool(alt_v))
        # Echtbetrieb lief schon vor dieser Version: Altbestand einmalig sperren (Kunden, die bis zum Start angelegt waren)
        eb = protokoll.echtbetrieb(con)
        if eb and not con.execute("SELECT 1 FROM einstellungen WHERE schluessel='_altbestand_gesetzt'").fetchone():
            n_alt = altbestand_sperren(con, int(eb["seit"][:4]), eb["seit"])
            con.execute("INSERT INTO einstellungen VALUES ('_altbestand_gesetzt', 'true')")
            protokoll.eintragen(con, "aufbewahrung_geaendert", "", f"{n_alt} Kunden aus der Zeit vor dem Echtbetrieb als Altbestand bis "
                                f"{de_datum(altbestand_frist(int(eb['seit'][:4])))} gesperrt", {"anzahl": n_alt}, benutzer="Programm", version=VERSION)
        # Angebotstext: feste Gültigkeit „4 Wochen“ einmalig durch den Platzhalter {gueltig_bis} ersetzen
        bt = con.execute("SELECT wert FROM einstellungen WHERE schluessel='beleg_texte'").fetchone()
        if bt and "4 Wochen gültig" in bt[0]:
            con.execute("UPDATE einstellungen SET wert=? WHERE schluessel='beleg_texte'",
                        (bt[0].replace("Dieses Angebot ist 4 Wochen gültig.", "Dieses Angebot ist gültig bis {gueltig_bis}."),))
        alt_ls = con.execute("SELECT wert FROM einstellungen WHERE schluessel='leitstand_schritte'").fetchone()
        if alt_ls and json.loads(alt_ls[0]) == ["Arbeitsvorbereitung", "Zuschnitt", "Kanten / CNC", "Montage Werkstatt", "Oberfläche", "Montage beim Kunden", "Fertig"]:
            con.execute("UPDATE einstellungen SET wert=? WHERE schluessel='leitstand_schritte'",
                        (json.dumps(STANDARD_EINSTELLUNGEN["leitstand_schritte"], ensure_ascii=False),))
            ersatz = {"Kanten / CNC": "Kanten", "Montage Werkstatt": "Bankraum", "Montage beim Kunden": "Montage"}
            for alt_s, neu_s in ersatz.items():
                con.execute("UPDATE auftraege SET leitstand=? WHERE leitstand=?", (neu_s, alt_s))
        # Bestehende Kunden: Briefanschrift einmalig in Einzelfelder (Name, Straße, Hausnummer …) aufteilen
        for r in con.execute("SELECT id, anschrift FROM kunden WHERE IFNULL(anschrift,'')<>'' AND IFNULL(vorname,'')='' AND IFNULL(nachname,'')='' "
                             "AND IFNULL(firma,'')='' AND IFNULL(strasse,'')=''").fetchall():
            teile = adressen.zerlegen(r["anschrift"])
            con.execute(f"UPDATE kunden SET {','.join(f + '=?' for f in adressen.FELDER)} WHERE id=?",
                        [teile[f] for f in adressen.FELDER] + [r["id"]])
        # Bestehende Lieferanten ebenso (Anschrift in Einzelfelder wie bei den Kunden)
        for r in con.execute("SELECT id, anschrift FROM lieferanten WHERE IFNULL(anschrift,'')<>'' AND IFNULL(vorname,'')='' AND IFNULL(nachname,'')='' "
                             "AND IFNULL(firma,'')='' AND IFNULL(strasse,'')=''").fetchall():
            teile = adressen.zerlegen(r["anschrift"])
            con.execute(f"UPDATE lieferanten SET {','.join(f + '=?' for f in adressen.FELDER)} WHERE id=?",
                        [teile[f] for f in adressen.FELDER] + [r["id"]])
        # Einmalig: Positionsstatus erst mit dem Beleg setzen; Status bestehender Aufträge aus ihren Belegen nachziehen
        if not con.execute("SELECT 1 FROM einstellungen WHERE schluessel='_status_nachgezogen'").fetchone():
            erster = (einstellungen(con).get("positionsstatus") or [""])[0]
            con.execute("UPDATE positionen SET status='' WHERE status=? AND auftrag_id NOT IN "
                        "(SELECT auftrag_id FROM belege WHERE IFNULL(pdf,'')<>'' OR status IN ('fest','storniert'))", (erster,))
            for r in con.execute("SELECT id FROM belege WHERE IFNULL(pdf,'')<>'' OR status IN ('fest','storniert') ORDER BY datum, id").fetchall():
                try:
                    status_fortschreiben(con, beleg_laden(con, r["id"]))
                except Exception as f:  # noqa: BLE001
                    print("Status nicht nachgezogen:", f)
            con.execute("INSERT INTO einstellungen VALUES ('_status_nachgezogen', 'true')")
        # Einmalig: aus E-Rechnungen übernommene Einheitencodes („XUN“ = Einheit) lesbar machen
        if not con.execute("SELECT 1 FROM einstellungen WHERE schluessel='_einheit_xun'").fetchone():
            for tab in ("material", "auftragskosten"):
                con.execute(f"UPDATE {tab} SET einheit='Stk.' WHERE einheit IN ('XUN', 'H87', 'C62')")
            con.execute("INSERT INTO einstellungen VALUES ('_einheit_xun', 'true')")
        # Einmalig: Mengeneinheiten auf die neue Standardliste setzen; eigene Einträge bleiben hinten erhalten
        if not con.execute("SELECT 1 FROM einstellungen WHERE schluessel='_einheiten_neu'").fetchone():
            alt_liste = einstellungen(con).get("einheiten") or []
            frueher = ["Stk.", "Psch.", "m", "lfm", "m²", "m³", "h", "kg", "Satz", "Garnitur"]
            neu = STANDARD_EINSTELLUNGEN["einheiten"] + [x for x in alt_liste if x not in frueher and x not in STANDARD_EINSTELLUNGEN["einheiten"]]
            con.execute("INSERT OR REPLACE INTO einstellungen (schluessel, wert) VALUES ('einheiten', ?)", (json.dumps(neu, ensure_ascii=False),))
            con.execute("INSERT INTO einstellungen VALUES ('_einheiten_neu', 'true')")
            for r in con.execute("""SELECT id, extras FROM positionen WHERE extras LIKE '%"psch"%'""").fetchall():
                ex = json.loads(r["extras"] or "{}")
                for z in ex.get("kostenliste") or []:
                    if isinstance(z, dict) and z.get("einheit") == "psch":
                        z["einheit"] = "Pauschale"
                con.execute("UPDATE positionen SET extras=? WHERE id=?", (json.dumps(ex, ensure_ascii=False), r["id"]))
        # Einzelfelder Fremdleistungen/Zukauf in die freie Kostenliste übernehmen (Rechenergebnis bleibt gleich)
        # nur Positionen mit einem der alten Schlüssel ("fremdleistungen": …), nicht Kostenlisten-Zeilen ("art": "fremdleistungen")
        muster = [f'%"{k}":%' for a_ in kalkulation.KOSTENLISTE_ALT for k in (a_, a_ + "_text")]
        for r in con.execute("SELECT id, extras FROM positionen WHERE " + " OR ".join(["extras LIKE ?"] * len(muster)), muster).fetchall():
            try:
                ex = json.loads(r["extras"] or "{}")
            except ValueError:
                continue
            alt = [k for a in kalkulation.KOSTENLISTE_ALT for k in (a, a + "_text") if k in ex]
            if not alt:
                continue
            ex["kostenliste"] = kalkulation.kostenliste(ex)
            for k in alt:
                ex.pop(k, None)
            con.execute("UPDATE positionen SET extras=? WHERE id=?", (json.dumps(ex, ensure_ascii=False), r["id"]))
        # Bestehende Aufträge: Kundendaten und Kalkulationswerte einmalig in den Auftrag kopieren (einfrieren)
        for r in con.execute("SELECT id FROM auftraege WHERE IFNULL(kunde_daten,'')='' OR IFNULL(kalk,'')=''").fetchall():
            auftrag_kunde(con, r["id"])
            auftrag_kalk(con, r["id"])
        taet_katalog_ergaenzen(con)
        personal.tage_einstellen(einstellungen(con))
        indizes_anlegen(con)


# Zusätzliche Suchfelder für große Datenbestände: jede Verweisspalte (…_id) bekommt einen Index, dazu Datum/Status in
# den großen Tabellen. „CREATE INDEX IF NOT EXISTS“ ist beim Start ohne Wirkung, wenn die Indizes schon da sind.
INDEX_EXTRA = [("belege", "datum"), ("belege", "art, status"), ("zeiten", "datum"), ("stunden", "datum"), ("termine", "bis, von"),
               ("offene_posten", "offen"), ("zahlungen", "bezahlt"), ("zahlungseingaenge", "datum"), ("auftraege", "status"),
               ("lagerbewegungen", "datum"), ("auftragskosten", "datum")]


def indizes_anlegen(con):
    # WAL: Lesen läuft weiter, während ein anderes Gerät speichert (Einstellung bleibt in der Datei gespeichert)
    try:
        con.commit()   # der Modus lässt sich nur außerhalb einer Transaktion umstellen
        con.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error as f:
        print("WAL-Modus nicht möglich:", f)
    tabellen = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for t in tabellen:
        for sp in [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]:
            if sp.endswith("_id") and sp != "message_id":
                con.execute(f'CREATE INDEX IF NOT EXISTS "ix_{t}_{sp}" ON "{t}"({sp})')
    for t, sp in INDEX_EXTRA:
        if t in tabellen:
            con.execute(f'CREATE INDEX IF NOT EXISTS "ix_{t}_{sp.replace(", ", "_")}" ON "{t}"({sp})')
    # Statistik für die Abfrageplanung bei jedem Start auffrischen (mit Stichprobe, dauert auch bei großen Beständen nur Millisekunden)
    con.execute("PRAGMA analysis_limit=400")
    con.execute("ANALYZE")


SICHERUNG_PRUEFUNG = {"ok": True, "text": "", "zeit": ""}
SICHERUNG_EXTERN = {"text": ""}   # Fehler beim Kopieren der täglichen Sicherung auf das externe Sicherungsziel
SICHERUNG_LOCK = threading.Lock()
PROTOKOLL_PRUEFUNG = {"text": ""}


def protokoll_vollpruefung():
    """Beim Start im Hintergrund: ganze Hash-Kette prüfen. Danach prüft die Protokollseite nur noch neue Einträge."""
    try:
        with verbindung() as con:
            erg = protokoll.pruefen(con, voll=True)
            belege_pruefen(con)
        PROTOKOLL_PRUEFUNG["text"] = "" if erg["ok"] else ("Die Prüfung des Änderungsprotokolls hat Unstimmigkeiten gefunden. "
                                                            "Details unter Einstellungen › Service › Protokoll.")
    except Exception as f:  # noqa: BLE001
        print("Protokollprüfung:", f)


def db_optimieren(con):
    """Service › Datenbank optimieren: prüfen, Statistik auffrischen, Datei verdichten."""
    groesse = lambda: sum(os.path.getsize(DB_PFAD + x) for x in ("", "-wal") if os.path.exists(DB_PFAD + x))
    vorher = groesse()
    erg = [r[0] for r in con.execute("PRAGMA integrity_check").fetchall()]
    if erg != ["ok"]:
        raise ApiFehler("Die Datenbankprüfung hat Fehler gefunden: " + "; ".join(erg[:3])[:300]
                        + ". Bitte nicht optimieren, sondern die letzte gute Sicherung zurückspielen.", 409)
    con.commit()
    con.execute("PRAGMA analysis_limit=0")
    con.execute("ANALYZE")
    con.execute("VACUUM")
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    nachher = groesse()
    return {"ok": True, "vorher": vorher, "nachher": nachher}


def backup():
    """Tägliche Sicherung der Datenbank mit Prüfung (PRAGMA integrity_check). Behalten werden die letzten 30 Tage und
    zusätzlich die erste Sicherung jedes Monats für 12 Monate. Eine fehlerhafte Prüfung erscheint als Warnung auf der Startseite."""
    if not os.path.exists(DB_PFAD):
        return
    with SICHERUNG_LOCK:
        _backup()
        backup_extern()


EXTERN_STAND = {"tag": ""}   # Tag der letzten gelungenen Kopie aufs externe Ziel (in diesem Programmlauf)


def extern_zuletzt(neu=None):
    """Zeitpunkt der letzten gelungenen Kopie aufs externe Sicherungsziel (daten/extern.json) lesen bzw. setzen."""
    p = os.path.join(DATEN, "extern.json")
    if neu:
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"zuletzt": neu}, f)
        except OSError:
            pass
        return neu
    try:
        with open(p, encoding="utf-8") as f:
            return str(json.load(f).get("zuletzt") or "")
    except (OSError, ValueError):
        return ""


def backup_extern():
    """Die tägliche Datenbanksicherung zusätzlich auf das externe Sicherungsziel kopieren (Unterordner
    „Jahresring-Datenbank“, die letzten 30 bleiben), damit bei Festplattendefekt, Diebstahl oder Verschlüsselung
    höchstens ein Tag fehlt."""
    ziel_ordner = str(einstellungen_roh("sicherung_ziel", "") or "").strip()
    quelle = os.path.join(BACKUP_PFAD, f"buero_{date.today().isoformat()}.db")
    if not ziel_ordner or not os.path.exists(quelle):
        SICHERUNG_EXTERN["text"] = ""
        return
    try:
        ordner = os.path.join(ziel_ordner, "Jahresring-Datenbank")
        os.makedirs(ordner, exist_ok=True)
        ziel = os.path.join(ordner, os.path.basename(quelle))
        if not os.path.exists(ziel) and not os.path.exists(ziel + tresor.ENDUNG):
            # mit Sicherungskennwort verschlüsselt (.jrs), sonst unverändert
            service.extern_ablegen({"daten": DATEN}, quelle, ziel)
        alle = sorted(f for f in os.listdir(ordner) if f.startswith("buero_") and f.endswith((".db", ".db" + tresor.ENDUNG)))
        for alt in alle[:-30]:
            os.remove(os.path.join(ordner, alt))
        SICHERUNG_EXTERN["text"] = ""
        EXTERN_STAND["tag"] = date.today().isoformat()
        extern_zuletzt(jetzt())
    except tresor.Fehler as x:
        SICHERUNG_EXTERN["text"] = f"Die tägliche Datenbanksicherung wurde nicht auf das externe Sicherungsziel kopiert: {x}"
    except OSError as x:
        # Ein Ziel, das nur zeitweise angeschlossen ist (USB-Platte), ist kein Fehler: erst nach der eingestellten Zahl von Tagen warnen
        warn = projektsicherung.einstellung(einstellungen_roh("projektsicherung"))["warn_tage"]
        zuletzt = extern_zuletzt()
        try:
            tage = (datetime.now() - datetime.fromisoformat(zuletzt)).days if zuletzt else warn
        except ValueError:
            tage = warn
        SICHERUNG_EXTERN["text"] = "" if tage < warn else (
            f"Das externe Sicherungsziel ({ziel_ordner}) war seit {tage} Tagen nicht erreichbar ({x.strerror or x}); die täglichen Datenbanksicherungen "
            "liegen so lange nur auf diesem PC. Bitte das Laufwerk anschließen. Einstellungen › Service › Datensicherung.")


def laufendes_programm_fremd():
    """Läuft auf dem Port schon ein anderes Jahresring (andere Version oder anderer Ordner, z. B. eine alte Installation
    auf dem Desktop oder die Version vor dem Update), wäre dessen Fenster mit dessen Daten zu sehen. Dann Hinweis statt Fenster."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/version", timeout=3) as r:
            d = json.loads(r.read().decode("utf-8") or "{}")
    except Exception:  # noqa: BLE001
        return ""
    v, ordner = d.get("version") or "?", d.get("ordner") or ""
    if v == VERSION and (not ordner or os.path.normcase(ordner) == os.path.normcase(BASIS)):
        return ""
    wo = f" aus dem Ordner {ordner}" if ordner and os.path.normcase(ordner) != os.path.normcase(BASIS) else ""
    return (f"Auf diesem PC läuft bereits ein anderes Jahresring (Version {v}{wo}). Diese Version ({VERSION}, Ordner {BASIS}) "
            "kann deshalb nicht starten, sonst würde das Fenster die Daten des anderen Programms zeigen.\n\n"
            "Bitte das laufende Programm beenden (Symbol unten rechts in der Taskleiste › Rechtsklick › Beenden) und Jahresring "
            "danach neu starten." + ("\n\nLiegt in dem genannten Ordner eine alte Installation, sollte sie gelöscht oder umbenannt "
                                    "werden, damit sie nicht wieder automatisch startet." if wo else ""))


def meldung_fenster(text):
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, text, "Jahresring", 0x30)
            return
        except Exception:  # noqa: BLE001
            pass


def frage_fenster(text):
    """Ja/Nein-Frage beim Start (ohne Browser). Ohne Windows-Fenster entscheidet die Umgebungsvariable BUERO_NOTFALL=ja."""
    if os.name == "nt":
        try:
            import ctypes
            return ctypes.windll.user32.MessageBoxW(0, text, "Jahresring", 0x34) == 6   # Ja/Nein mit Warnsymbol
        except Exception:  # noqa: BLE001
            pass
    print(text)
    return os.environ.get("BUERO_NOTFALL", "").lower() == "ja"


def _db_in_ordnung(pfad):
    try:
        c = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True, timeout=30)
        try:
            return c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        finally:
            c.close()
    except sqlite3.Error:
        return False


NOTFALL = {"text": ""}


def datenbank_notfall(grund):
    """Die Datenbank lässt sich nicht lesen (z. B. Festplattenfehler, Stromausfall beim Schreiben auf ein defektes Laufwerk).
    Die beschädigte Datei wird aufbewahrt; auf Nachfrage wird die jüngste geprüfte Tagessicherung eingespielt."""
    stempel = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ablage = os.path.join(DATEN, "beschaedigt", stempel)
    os.makedirs(ablage, exist_ok=True)
    for x in ("", "-wal", "-shm"):
        if os.path.exists(DB_PFAD + x):
            shutil.copy2(DB_PFAD + x, ablage)
    gut = None
    try:
        tage = sorted((f for f in os.listdir(BACKUP_PFAD) if f.startswith("buero_") and f.endswith(".db")), reverse=True)
        st = os.path.join(BACKUP_PFAD, STUNDE_NAME)
        # die stündliche Zwischensicherung ist meist die jüngste – zuerst versuchen
        kandidaten = ([STUNDE_NAME] if os.path.exists(st) and (not tage or os.path.getmtime(st) > os.path.getmtime(os.path.join(BACKUP_PFAD, tage[0]))) else []) + tage
        for name in kandidaten:
            if _db_in_ordnung(os.path.join(BACKUP_PFAD, name)):
                gut = name
                break
    except OSError:
        pass
    print(f"Datenbank beschädigt ({grund}). Kopie unter {ablage}. Letzte gute Tagessicherung: {gut or 'keine'}")
    if not gut:
        meldung_fenster("Die Datenbank von Jahresring ist beschädigt und es wurde keine brauchbare Tagessicherung gefunden.\n\n"
                        f"Die beschädigte Datei liegt unverändert unter\n{ablage}\n\n"
                        "Bitte eine vollständige Sicherung (Sicherung_….zip) vom externen Sicherungsziel bereithalten und den Betreuer hinzuziehen. "
                        "Das Programm wird jetzt beendet.")
        sys.exit(1)
    tag = (datetime.fromtimestamp(os.path.getmtime(os.path.join(BACKUP_PFAD, gut))).strftime("%d.%m.%Y %H:%M Uhr") if gut == STUNDE_NAME
           else de_datum(gut[6:16]))
    if not frage_fenster("Die Datenbank von Jahresring ist beschädigt und kann nicht geöffnet werden.\n\n"
                         f"Die beschädigte Datei wurde unverändert aufbewahrt unter\n{ablage}\n\n"
                         f"Soll die letzte geprüfte Sicherung vom {tag} eingespielt werden?\n"
                         "Alles, was danach eingegeben wurde, fehlt dann und muss nachgetragen werden; Archiv-PDFs, Dateien und das "
                         "Änderungsprotokoll bleiben erhalten. Die Belegprüfung zeigt danach, welche Rechnungen fehlen.\n\n"
                         "Nein = Programm beenden, nichts verändern."):
        sys.exit(1)
    for x in ("-wal", "-shm"):
        if os.path.exists(DB_PFAD + x):
            os.remove(DB_PFAD + x)
    shutil.copy2(os.path.join(BACKUP_PFAD, gut), DB_PFAD)
    NOTFALL["text"] = (f"Die Datenbank war beschädigt und wurde beim Start aus der Sicherung vom {tag} wiederhergestellt. "
                       f"Die beschädigte Datei liegt unter {ablage}. Eingaben nach dem {tag} bitte nachtragen.")
    return gut, ablage


def datenbank_starten():
    """Datenbank öffnen und einrichten; bei einer beschädigten Datei den Notfallweg gehen statt kommentarlos abzustürzen."""
    try:
        init_db()
        return
    except sqlite3.DatabaseError as f:
        if "malformed" not in str(f) and "not a database" not in str(f) and "corrupt" not in str(f):
            raise
        grund = str(f)
    import gc
    gc.collect()   # die beim Fehler offen gebliebene Verbindung schließen, sonst bleibt die Datei gesperrt
    gut, ablage = datenbank_notfall(grund)
    init_db()
    with verbindung() as con:
        protokoll.eintragen(con, "ruecksicherung", gut, f"Datenbank beim Start beschädigt ({grund[:80]}); automatisch aus Tagessicherung {gut} "
                            f"wiederhergestellt. Beschädigte Datei aufbewahrt unter {ablage}.", {"sicherung": gut, "ablage": ablage}, benutzer="Programm", version=VERSION)
        con.commit()


def zwischenspeicher_vorwaermen():
    """Arbeitszeitkonten der Mitarbeiter (abgeschlossene Monate) gleich nach dem Start im Hintergrund berechnen,
    damit der erste Aufruf von Personal nicht wartet."""
    try:
        time.sleep(3)
        api("GET", ["mitarbeiter"], {"status": "aktiv"}, None)
    except Exception as x:  # noqa: BLE001
        print("Zwischenspeicher Personal:", x)


def projekt_cfg():
    return {"daten": DATEN, "projektpfad": str(einstellungen_roh("projektpfad", "") or ""), "ziel": str(einstellungen_roh("sicherung_ziel", "") or "").strip()}


def projekt_sichern(anlass="automatisch", wer="Programm"):
    """Ein Lauf der Projektordner-Sicherung samt Protokolleintrag (läuft im Hintergrund, nie innerhalb einer Anfrage)."""
    e = projektsicherung.einstellung(einstellungen_roh("projektsicherung"))
    erg = projektsicherung.sichern(projekt_cfg(), e["tage"])
    if erg["ok"] and (erg["neu"] or erg["geaendert"] or erg["entfernt"] or erg["umgestellt"] or erg["aufgeraeumt"] or anlass != "automatisch"):
        try:
            with verbindung() as con:
                protokoll.eintragen(con, "projektsicherung", "", f"Projektordner gesichert ({anlass}): {erg['neu']} neu, {erg['geaendert']} geändert, "
                                    f"{erg['entfernt']} im Projektordner gelöscht, {erg['fehler_anzahl']} nicht gesichert"
                                    + (f", {erg['aufgeraeumt']} frühere Stände nach Ablauf der Frist entfernt" if erg["aufgeraeumt"] else ""),
                                    {k: erg[k] for k in ("neu", "geaendert", "entfernt", "umgestellt", "bytes", "fehler_anzahl", "verschluesselt", "aufgeraeumt", "dauer")},
                                    benutzer=wer, version=VERSION)
        except Exception as x:  # noqa: BLE001
            print("Protokoll Projektsicherung:", x)
    return erg


def projekt_waechter():
    """Prüft jede Minute, ob die tägliche Sicherung des Projektordners fällig ist."""
    time.sleep(90)
    while True:
        try:
            e = projektsicherung.einstellung(einstellungen_roh("projektsicherung"))
            ziel = projekt_cfg()["ziel"]
            if ziel and projektsicherung.erreichbar(ziel):
                # Sicherungsziel ist (wieder) da, z. B. USB-Platte angesteckt: heutige Datenbanksicherung nachholen
                if EXTERN_STAND["tag"] != date.today().isoformat():
                    with SICHERUNG_LOCK:
                        backup_extern()
                if projektsicherung.faellig(DATEN, e, ziel=ziel):
                    projekt_sichern()
        except projektsicherung.Fehler:
            pass
        except Exception as x:  # noqa: BLE001
            print("Sicherung des Projektordners:", x)
        time.sleep(60)


def sicherungs_waechter():
    """Läuft das Programm über Nacht oder tagelang durch, entsteht die tägliche Sicherung trotzdem: stündlich prüfen."""
    while True:
        time.sleep(3600)
        try:
            backup()
        except Exception as x:  # noqa: BLE001
            print("Tägliche Sicherung im laufenden Betrieb:", x)
        try:
            stunden_sicherung()
        except Exception as x:  # noqa: BLE001
            print("Stündliche Zwischensicherung:", x)


STUNDE_NAME = "stunde_aktuell.db"


def stunden_sicherung():
    """Stündliche Zwischensicherung der Datenbank (eine Datei, wird jeweils ersetzt). Fällt die Datenbank aus, geht damit
    höchstens die letzte Stunde verloren statt des ganzen Tages. Ersetzt wird nur, wenn die neue Kopie die Prüfung besteht."""
    os.makedirs(BACKUP_PFAD, exist_ok=True)
    tmp = os.path.join(BACKUP_PFAD, STUNDE_NAME + ".part")
    if os.path.exists(tmp):
        os.remove(tmp)
    with SICHERUNG_LOCK:
        src = sqlite3.connect(DB_PFAD, timeout=30)
        dst = sqlite3.connect(tmp)
        try:
            with dst:
                src.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")
        finally:
            src.close()
            dst.close()
    if _db_in_ordnung(tmp):
        os.replace(tmp, os.path.join(BACKUP_PFAD, STUNDE_NAME))
    else:
        os.remove(tmp)
        print("Stündliche Zwischensicherung: Kopie hat die Prüfung nicht bestanden, alte Zwischensicherung bleibt.")


def sicherung_erinnerung(ziel=None):
    """Hinweis auf der Startseite (nur Inhaber): kein externes Sicherungsziel oder letzte vollständige Sicherung älter als 7 Tage."""
    try:
        voll = [f for f in os.listdir(BACKUP_PFAD) if f.startswith("Sicherung_") and f.endswith(".zip")]
    except OSError:
        voll = []
    teile = []
    if not str((einstellungen_roh("sicherung_ziel", "") if ziel is None else ziel) or "").strip():
        teile.append("Es ist kein externes Sicherungsziel eingerichtet (z. B. USB-Platte, NAS oder Cloud-Ordner). Ohne Kopie außerhalb dieses PCs "
                     "gehen bei Festplattendefekt oder Diebstahl alle Daten verloren.")
    if voll:
        letzte = max(os.path.getmtime(os.path.join(BACKUP_PFAD, f)) for f in voll)
        tage = (time.time() - letzte) / 86400
        if tage > 7:
            teile.append(f"Die letzte vollständige Sicherung (mit Anhängen und Bildern) ist {int(tage)} Tage alt.")
    elif os.path.exists(DB_PFAD):
        teile.append("Es gibt noch keine vollständige Sicherung mit Anhängen und Bildern.")
    if not teile:
        return ""
    return " ".join(teile) + " Einstellungen › Service › Datensicherung."


def _backup():
    os.makedirs(BACKUP_PFAD, exist_ok=True)
    ziel = os.path.join(BACKUP_PFAD, f"buero_{date.today().isoformat()}.db")
    if not os.path.exists(ziel):
        src = sqlite3.connect(DB_PFAD)
        dst = sqlite3.connect(ziel)
        with dst:
            src.backup(dst)
        dst.execute("PRAGMA journal_mode=DELETE")   # Sicherung als eine einzelne Datei (ohne -wal/-shm)
        src.close()
        dst.close()
        try:
            c = sqlite3.connect(f"file:{ziel}?mode=ro", uri=True)
            erg = [r[0] for r in c.execute("PRAGMA integrity_check").fetchall()]
            c.close()
        except sqlite3.Error as f:
            erg = [str(f)]
        ok = erg == ["ok"]
        SICHERUNG_PRUEFUNG.update(ok=ok, zeit=jetzt(), text="" if ok else
                                  "Die Prüfung der heutigen Datensicherung hat Fehler gefunden (" + "; ".join(erg[:3])[:200] + "). "
                                  "Bitte unter Einstellungen › Service den Relationencheck ausführen und ggf. die letzte gute Sicherung zurückspielen.")
        if not ok:
            os.replace(ziel, ziel + ".defekt")
    alle = sorted(f for f in os.listdir(BACKUP_PFAD) if f.startswith("buero_") and f.endswith(".db"))
    monate = {}
    for f in alle:
        monate.setdefault(f[6:13], f)   # erste Sicherung je Monat (buero_JJJJ-MM-TT.db)
    behalten = set(alle[-30:]) | set(sorted(monate.values())[-12:])
    for alt in alle:
        if alt not in behalten:
            os.remove(os.path.join(BACKUP_PFAD, alt))


def taet_listen(e):
    """Tätigkeitslisten (z. B. „Esstisch massiv, Stahlgestell“); alte Einzelliste wird zu „Standard“."""
    listen = e.get("taetigkeit_listen")
    if isinstance(listen, list) and listen:
        return listen
    return [{"name": "Standard", "modus": "taetigkeiten", "zeiten": e.get("taetigkeiten") or TAETIGKEITEN_VORGABE}]


TAET_FELDER = ("kst", "name", "gruppe", "minuten", "bezug", "ruest", "helfer", "stunden")


def taet_katalog(e):
    """Einzeln definierte Tätigkeiten. Ist der Katalog noch leer, wird er aus den vorhandenen Listen (und der Vorgabe) gebildet."""
    kat = e.get("taetigkeiten_katalog")
    if isinstance(kat, list) and kat:
        return kat
    kat, gesehen = [], set()
    quellen = [z for l in taet_listen(e) if (l.get("modus") or "taetigkeiten") != "stunden" for z in (l.get("zeiten") or [])] + list(TAETIGKEITEN_KATALOG)
    for z in quellen:
        schl = (z.get("kst") or "", re.sub(r"\s+", "", (z.get("name") or "").lower()))
        if not schl[1] or schl in gesehen:
            continue
        gesehen.add(schl)
        kat.append({"id": f"t{len(kat) + 1}", **{k: z.get(k, "" if k in ("kst", "name", "gruppe", "bezug") else 0) for k in TAET_FELDER if k != "stunden"}})
    return kat


def taet_katalog_ergaenzen(con):
    """Einmalig je Katalogstand: Tätigkeiten aus TAETIGKEITEN_KATALOG in den Katalog übernehmen. Gleiche Kostenstelle und
    Bezeichnung → Werte übernehmen (bei doppelter Bezeichnung zuerst die mit gleicher Bezugsgröße), sonst neu anlegen
    (Kennung vergibt das Programm). Andere vorhandene Tätigkeiten bleiben unverändert; kalkulierte Positionen haben ihre Kopie."""
    stand = con.execute("SELECT wert FROM einstellungen WHERE schluessel='_taet_katalog_stand'").fetchone()
    if stand and json.loads(stand[0]) == TAETIGKEITEN_KATALOG_STAND:
        return
    e = einstellungen(con)
    kat = [dict(t) for t in taet_katalog(e)]
    nr = max([int(re.sub(r"\D", "", str(t.get("id"))) or 0) for t in kat] + [0])
    benutzt, geaendert = set(), {}
    norm = lambda x: re.sub(r"\s+", "", (x or "").lower())   # „Lackieren 2x + Schleifen“ = „Lackieren 2x +Schleifen“
    zuordnung = {}
    # 1. Durchgang: gleiche Kostenstelle, Bezeichnung und Bezugsgröße; 2. Durchgang: nur Kostenstelle und Bezeichnung
    for genau in (True, False):
        for i, v in enumerate(TAETIGKEITEN_KATALOG):
            if i in zuordnung:
                continue
            t = next((t for t in kat if t.get("id") not in benutzt and t.get("kst") == v["kst"] and norm(t.get("name")) == norm(v["name"])
                      and (not genau or (t.get("bezug") or "") == v["bezug"])), None)
            if t:
                zuordnung[i] = t
                benutzt.add(t["id"])
    for i, v in enumerate(TAETIGKEITEN_KATALOG):
        werte = {"gruppe": "", "minuten": v["minuten"], "bezug": v["bezug"], "ruest": v["ruest"], "helfer": v["helfer"]}
        t = zuordnung.get(i)
        if t:
            t.update(werte)
            geaendert[t["id"]] = t
        else:
            nr += 1
            kat.append({"id": f"t{nr}", "kst": v["kst"], "name": v["name"], **werte})
    con.execute("INSERT OR REPLACE INTO einstellungen VALUES ('taetigkeiten_katalog', ?)", (json.dumps(kat, ensure_ascii=False),))
    listen = e.get("taetigkeit_listen")
    if isinstance(listen, list) and geaendert:   # Listenzeilen, die auf eine geänderte Tätigkeit verweisen, nachziehen
        for li in listen:
            for z in li.get("zeiten") or []:
                t = geaendert.get(z.get("tid"))
                if t:
                    z.update({k: t.get(k) for k in ("kst", "name", "gruppe", "minuten", "bezug", "ruest", "helfer")})
        con.execute("INSERT OR REPLACE INTO einstellungen VALUES ('taetigkeit_listen', ?)", (json.dumps(listen, ensure_ascii=False),))
    con.execute("INSERT OR REPLACE INTO einstellungen VALUES ('_taet_katalog_stand', ?)", (json.dumps(TAETIGKEITEN_KATALOG_STAND),))


def zeiten_fixieren(e, p, neu, bezug_da=None):
    """Tätigkeiten in der Position: Kostenstelle, Name und Bezugsgröße kommen aus dem Katalog (Einstellungen) bzw. bleiben
    wie bisher gespeichert. Änderbar sind Lohngruppe, Minuten, Rüstzeit und Helfer. Die Bezugsgröße einer vorhandenen Zeile
    lässt sich nur ersetzen, wenn es sie im Auftrag nicht mehr gibt (bezug_da = verfügbare Schlüssel; None = nicht prüfen)."""
    if (p.get("zeitmodus") or "taetigkeiten") == "stunden":
        return neu
    kat = {t.get("id"): t for t in taet_katalog(e) if t.get("id")}
    alt = {(z.get("tid"), z.get("kst"), z.get("name")) for z in p.get("zeiten") or []}
    alt_namen = {(z.get("kst"), z.get("name")) for z in p.get("zeiten") or []}
    aus = []
    for z in neu:
        if not isinstance(z, dict):
            continue
        t = kat.get(z.get("tid"))
        if t:
            z = {**z, "kst": t.get("kst") or "", "name": t.get("name") or ""}
        elif (z.get("kst"), z.get("name")) not in alt_namen and (z.get("tid"), z.get("kst"), z.get("name")) not in alt:
            # unbekannte Zeile: nur Tätigkeiten mit gleichem Namen aus dem Katalog zulassen
            t = next((x for x in kat.values() if (x.get("name") or "").strip().lower() == (z.get("name") or "").strip().lower()), None)
            if not t:
                continue
            z = {**z, "tid": t["id"], "kst": t.get("kst") or "", "name": t.get("name") or ""}
        aus.append(z)
    if bezug_da is None:
        return aus
    vorher = {}
    for z in p.get("zeiten") or []:
        vorher.setdefault((z.get("tid") or "", z.get("kst"), z.get("name")), []).append(z.get("bezug") or "")
    for z in aus:
        alt = vorher.get((z.get("tid") or "", z.get("kst"), z.get("name")))
        if alt:
            b = alt.pop(0)
            if b in bezug_da or not b:
                z["bezug"] = b
        elif (z.get("bezug") or "") not in bezug_da:   # neue Zeile (Katalog oder Tätigkeitsliste): unbekannte Bezugsgröße → wie im Katalog
            t = kat.get(z.get("tid"))
            z["bezug"] = (t.get("bezug") or "") if t else ""
    return aus


VERMERK = "Vermerk: "   # versendet_an bei von Hand vermerktem Versand (Post, persönlich, eigenes E-Mail-Programm)
EIGENE_DOKUMENTE = ("verfahrensdokumentation.html", "datenschutz.html")


def eigene_dokumente_uebernehmen(bestand):
    """Betriebseigene Fassungen der Verfahrens- und Datenschutzdokumentation liegen im Datenordner (daten/dokumente)
    und ersetzen dort die neutrale Vorlage aus static/hilfe. Ein Ordner „uebernahme“ im Programmordner wird beim
    Update einer bestehenden Installation einmalig dorthin übernommen (vorhandene Dateien bleiben) und danach entfernt."""
    quelle = os.path.join(BASIS, "uebernahme")
    if not os.path.isdir(quelle):
        return
    try:
        if bestand:
            ziel = os.path.join(DATEN, "dokumente")
            os.makedirs(ziel, exist_ok=True)
            for n in EIGENE_DOKUMENTE:
                if os.path.isfile(os.path.join(quelle, n)) and not os.path.exists(os.path.join(ziel, n)):
                    shutil.copy2(os.path.join(quelle, n), os.path.join(ziel, n))
        shutil.rmtree(quelle, ignore_errors=True)
    except OSError as x:
        print("Übernahme der eigenen Dokumente:", x)


def einstellungen(con):
    e = dict(STANDARD_EINSTELLUNGEN)
    for r in con.execute("SELECT schluessel, wert FROM einstellungen"):
        try:
            e[r["schluessel"]] = json.loads(r["wert"])
        except ValueError:
            pass
    LAND_EINST["immer"] = bool(e.get("land_immer"))
    m = e.get("mail")
    if isinstance(m, dict) and str(m.get("passwort") or "").startswith(geheim.PRAEFIX):
        e["mail"] = {**m, "passwort": geheim.entschluesseln(m["passwort"])}
    return e


def sauber(text):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(text or "")).strip()
    return text.rstrip(". ")


def ordner_name(e, auftrag, kunde):
    schema = e.get("ordnerschema") or STANDARD_EINSTELLUNGEN["ordnerschema"]
    name = schema.format(
        auftrag=sauber(auftrag["nummer"]),
        projekt=sauber(auftrag["bezeichnung"]) or "Projekt",
        kundennr=sauber(kunde["nummer"]),
        name=sauber(kunde["kurzname"]),
    )
    return sauber(name)


def ordner_anlegen(con, auftrag_id):
    e = einstellungen(con)
    basis = (e.get("projektpfad") or "").strip()
    if not basis:
        raise ApiFehler("In den Einstellungen ist noch kein Projektpfad hinterlegt.")
    if not os.path.isdir(basis):
        raise ApiFehler(f"Projektpfad nicht gefunden: {basis}")
    a = con.execute("SELECT * FROM auftraege WHERE id=?", (auftrag_id,)).fetchone()
    if not a:
        raise ApiFehler("Auftrag nicht gefunden", 404)
    if a["ordner"] and os.path.isdir(a["ordner"]):
        return a["ordner"]
    # Gehört der Auftrag zu einem Projekt und ist der Sammelordner eingeschaltet, liegt sein Ordner in „<Projektnr>_<Bezeichnung>“
    orte = [basis]
    if e.get("projekt_sammelordner") and a["projekt_id"]:
        pr = con.execute("SELECT nummer, bezeichnung FROM projekte WHERE id=?", (a["projekt_id"],)).fetchone()
        if pr:
            orte.insert(0, os.path.join(basis, sauber(f"{pr['nummer']}_{pr['bezeichnung']}" if pr["bezeichnung"] else pr["nummer"])))
    # Ordner verschoben oder umbenannt? Im Projektpfad (und im Projekt-Sammelordner) nach "<Auftragsnummer>_…" bzw. gleichem Namen suchen
    gefunden = None
    for ort in orte:
        if not os.path.isdir(ort):
            continue
        if a["ordner"] and os.path.isdir(os.path.join(ort, os.path.basename(a["ordner"]))):
            gefunden = os.path.join(ort, os.path.basename(a["ordner"]))
        else:
            for name in sorted(os.listdir(ort)):
                if (name == a["nummer"] or name.startswith(a["nummer"] + "_")) and os.path.isdir(os.path.join(ort, name)):
                    gefunden = os.path.join(ort, name)
                    break
        if gefunden:
            break
    if gefunden:
        pfad = gefunden
    else:
        k = auftrag_kunde(con, auftrag_id)
        pfad = os.path.join(orte[0], ordner_name(e, a, k))
        os.makedirs(pfad, exist_ok=True)
        for unter in list(e.get("unterordner") or []) + [werkstatt_unterordner(e)]:
            u = sauber(unter)
            if u:
                os.makedirs(os.path.join(pfad, u), exist_ok=True)
    con.execute("UPDATE auftraege SET ordner=?, geaendert=? WHERE id=?", (pfad, jetzt(), auftrag_id))
    return pfad


def im_ordner(basis, rel):
    """Löst einen relativen Pfad sicher innerhalb des Projektordners auf."""
    ziel = os.path.normpath(os.path.join(basis, rel or ""))
    b = os.path.normpath(basis)
    if os.path.normcase(ziel) != os.path.normcase(b) and not os.path.normcase(ziel).startswith(os.path.normcase(b) + os.sep):
        raise ApiFehler("Ungültiger Pfad.")
    return ziel


def nur_werkstatt():
    r = benutzer.aktuelle_rechte()
    return bool(r and not r.get("inhaber") and r.get("auftrag_reiter") == "werkstatt")


def werkstatt_unterordner(e):
    return sauber(e.get("werkstatt_ordner") or "50_Werkstatt") or "50_Werkstatt"


def sicht_ordner(con, aid, anlegen=True):
    """Projektordner aus Sicht des angemeldeten Benutzers: Werkstattbenutzer sehen nur den Unterordner 50_Werkstatt."""
    ordner, hinweis = projektordner(con, aid, anlegen)
    if ordner and nur_werkstatt():
        ordner = os.path.join(ordner, werkstatt_unterordner(einstellungen(con)))
        os.makedirs(ordner, exist_ok=True)
    return ordner, hinweis


def pos_vorlagen(e):
    liste = e.get("pos_vorlagen")
    return [v for v in liste if isinstance(v, dict)] if isinstance(liste, list) else []


def vorlage_finden(e, vid):
    v = next((x for x in pos_vorlagen(e) if str(x.get("id")) == str(vid)), None)
    if not v:
        raise ApiFehler("Positionsvorlage nicht gefunden.", 404)
    return v


def vorlagen_speichern(con, liste):
    gesehen = set()
    for v in liste:
        if not v.get("id") or v["id"] in gesehen:
            v["id"] = "v" + secrets.token_hex(4)
        gesehen.add(v["id"])
    con.execute("INSERT OR REPLACE INTO einstellungen VALUES (?, ?)", ("pos_vorlagen", json.dumps(liste, ensure_ascii=False)))
    return liste


def vorlage_vorschau(con, erg):
    """Materialnamen zu den gewählten Material-Parametern ergänzen (für Vorschau und Auswahl)."""
    namen = {}
    for k, mid in erg["materialien"].items():
        if mid:
            r = con.execute("SELECT nummer, bezeichnung, dicke FROM material WHERE id=?", (mid,)).fetchone()
            if r:
                namen[k] = f"{r['nummer']} {(r['bezeichnung'] or '').splitlines()[0] if r['bezeichnung'] else ''}".strip()
    erg["material_namen"] = namen
    return erg


def positionsvorlagen_api(con, methode, teile, d):
    e = einstellungen(con)
    if methode == "GET" and len(teile) == 1:
        return {"vorlagen": pos_vorlagen(e), "rollen": vorlagen.ROLLEN, "rolle_kats": vorlagen.ROLLE_KATS,
                "funktionen": sorted(vorlagen.FUNKTIONEN)}
    if methode == "PUT" and len(teile) == 1:
        if not isinstance(d.get("vorlagen"), list):
            raise ApiFehler("Keine Vorlagen übergeben.")
        return {"vorlagen": vorlagen_speichern(con, d["vorlagen"])}
    if methode == "POST" and teile[1:] == ["berechnen"]:
        v = d.get("vorlage") if isinstance(d.get("vorlage"), dict) else vorlage_finden(e, d.get("id"))
        return vorlage_vorschau(con, vorlagen.berechnen(v, d.get("werte") or {}))
    if methode == "POST" and teile[1:] == ["beispiel"]:
        bsp = vorlagen.beispiel_korpus() if d.get("art") == "korpus" else vorlagen.beispiel_system32()
        liste = pos_vorlagen(e) + [dict(bsp, id="")]
        return {"vorlagen": vorlagen_speichern(con, liste)}
    raise ApiFehler("Unbekannte Anfrage", 404)


def vorlage_anwenden(con, p, d):
    """Position aus einer Vorlage füllen (oder mit neuen Maßen neu berechnen): Stückliste und Beschläge werden ersetzt,
    Tätigkeiten nur gesetzt, wenn die Position noch keine hat; der Text nur, wenn er leer oder unverändert erzeugt ist."""
    e = einstellungen(con)
    v = vorlage_finden(e, d.get("id") or ((p.get("extras") or {}).get("vorlage") or {}).get("id"))
    erg = vorlagen.berechnen(v, d.get("werte") or {})
    if erg["fehler"]:
        raise ApiFehler("Die Vorlage lässt sich so nicht rechnen: " + "; ".join(erg["fehler"][:4]))
    kalk = auftrag_kalk(con, p["auftrag_id"])
    rollen = {x["k"]: x.get("rolle") or "platte" for x in v.get("parameter") or [] if x.get("typ") == "material"}
    kz = {}
    for k, mid in erg["materialien"].items():
        if mid:
            try:
                m = material.laden(con, mid)
            except material.Fehler:
                continue
            kz[k] = stuecklistenimport.auftrags_werkstoff(kalk, m, rollen.get(k, "platte"))
    con.execute("UPDATE auftraege SET kalk=? WHERE id=?", (json.dumps(kalk, ensure_ascii=False), p["auftrag_id"]))
    stueck = []
    for t in erg["teile"]:
        x = {"werkstoff": kz.get(t["werkstoff_param"], ""), "verwendung": t["verwendung"], "stueck": t.get("stueck", 0),
             "laenge": t.get("laenge", 0), "breite": t.get("breite", 0),
             "kanten": {s: kz[k] for s, k in t["kanten"].items() if kz.get(k)},
             "furnier": {s: kz[k] for s, k in t["furnier"].items() if kz.get(k)},
             "oberflaeche": {s: kz[k] for s, k in t["oberflaeche"].items() if kz.get(k)},
             "fraesen": t["fraesen"], "bemerkung": t["bemerkung"]}
        for f in ("bohren", "taschen", "tasche_l", "tasche_b", "tasche_t", "gehrung"):
            if t.get(f):
                x[f] = t[f]
        if t.get("verbinden"):
            x["verbinden"] = {"anzahl": t["verbinden"]}
        stueck.append(x)
    bs = [{"k": kz[b["material_param"]], "menge": b["menge"], "bemerkung": b["bemerkung"]} for b in erg["beschlaege"] if kz.get(b["material_param"])]
    ex = dict(p.get("extras") or {})
    alt = ex.get("vorlage") or {}
    werte = {"stueckliste": json.dumps(stueck, ensure_ascii=False), "beschlaege": json.dumps(bs, ensure_ascii=False), "geaendert": jetzt()}
    if not p.get("zeiten") and erg["zeiten"]:
        werte["zeiten"] = json.dumps(zeiten_fixieren(e, {"zeitmodus": "taetigkeiten", "zeiten": erg["zeiten"]}, erg["zeiten"]), ensure_ascii=False)
        werte["zeitmodus"] = "taetigkeiten"
    if klartext_leer(p.get("text")) or (alt.get("text") and klartext(p.get("text") or "").strip() == klartext(alt["text"]).strip()):
        werte["text"] = erg["text"]
    if len(erg["masse"]) > 1:
        werte["masse"] = json.dumps(erg["masse"])
    if d.get("neu"):
        werte["menge"] = erg["menge"]
        werte["einheit"] = v.get("einheit") or p.get("einheit") or "Stk."
    eingaben = {x["k"]: (erg["materialien"].get(x["k"]) if x.get("typ") == "material" else erg["werte"].get(x["k"]))
                for x in v.get("parameter") or [] if x.get("k")}
    ex["vorlage"] = {"id": v["id"], "name": v.get("name") or "", "werte": eingaben, "text": erg["text"], "am": jetzt()}
    werte["extras"] = json.dumps(ex, ensure_ascii=False)
    con.execute(f"UPDATE positionen SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [p["id"]])
    erg_pos = position_antwort(con, p["id"])
    erg_pos["vorlage"] = {"teile": len(stueck), "beschlaege": len(bs), "ohne_material": [k for k, mid in erg["materialien"].items() if not mid]}
    return erg_pos


def vorlage_aus_position(con, p, d):
    name = (d.get("name") or "").strip() or klartext(p.get("text") or "").split("\n")[0][:60] or "Neue Vorlage"
    kalk = auftrag_kalk(con, p["auftrag_id"])
    v = vorlagen.aus_position(p, kalk, name)
    # Material-Parameter mit dem Materialstamm verknüpfen (Vorgabe beim Anlegen)
    for x in v["parameter"]:
        if x.get("typ") == "material" and x.get("matnr"):
            r = con.execute("SELECT id FROM material WHERE nummer=?", (x["matnr"],)).fetchone()
            x["material_id"] = r["id"] if r else None
    liste = vorlagen_speichern(con, pos_vorlagen(einstellungen(con)) + [v])
    return liste[-1]


# ---------------------------------------------------------------- DSGVO: Auskunft und Anonymisierung
AUFBEWAHRUNG_JAHRE = 10   # sicherheitshalber 10 Jahre ab Ende des Jahres des letzten Belegs (§ 147 AO / § 257 HGB, teils 8 Jahre)


def altbestand_frist(jahr=None):
    return f"{(jahr or date.today().year) + AUFBEWAHRUNG_JAHRE}-12-31"


def altbestand_sperren(con, jahr=None, bis_angelegt=None):
    """Kunden, die beim Start des Echtbetriebs schon da sind, stammen aus früheren Programmen (anderes Branchenprogramm, Excel …).
    Deren Rechnungen und Briefe liegen dort und sind aufzubewahren – deshalb bis Ende des Jahres + 10 Jahre sperren
    (kein Löschen, kein Anonymisieren). Der Inhaber kann das Datum je Kunde anpassen, wenn er die letzte Rechnung kennt."""
    bis = altbestand_frist(jahr)
    sql, par = "UPDATE kunden SET aufbewahren_bis=? WHERE IFNULL(aufbewahren_bis,'')<?", [bis, bis]
    if bis_angelegt:
        sql += " AND IFNULL(angelegt,'')<=?"
        par.append(bis_angelegt)
    return con.execute(sql, par).rowcount


def kunde_auskunft(con, kid):
    """Alle zu einem Kunden gespeicherten Daten (Art. 15/20 DSGVO) als strukturierte Übersicht."""
    k = con.execute("SELECT * FROM kunden WHERE id=?", (kid,)).fetchone()
    if not k:
        raise ApiFehler("Kunde nicht gefunden", 404)
    auftr = zeilen(con.execute("SELECT id, nummer, bezeichnung, status, angelegt, ordner FROM auftraege WHERE kunde_id=?", (kid,)))
    ids = [a["id"] for a in auftr] or [0]
    ph = ",".join("?" * len(ids))
    erg = {
        "erstellt": jetzt(), "verantwortlicher": firma_daten(einstellungen(con)),
        "zweck": "Angebote, Auftragsabwicklung, Rechnungsstellung, Gewährleistung und gesetzliche Aufbewahrung (Art. 6 Abs. 1 b und c DSGVO)",
        "stammdaten": {x: v for x, v in dict(k).items() if v not in (None, "")},
        "auftraege": auftr,
        "belege": zeilen(con.execute(f"SELECT nummer, art, datum, status, netto, brutto FROM belege WHERE auftrag_id IN ({ph}) OR kunde_id=?", (*ids, kid))),
        "korrespondenz": zeilen(con.execute(f"SELECT datum, art, betreff, von, an FROM korrespondenz WHERE kunde_id=? OR auftrag_id IN ({ph}) ORDER BY datum", (kid, *ids))),
        "notizen": zeilen(con.execute(f"SELECT angelegt, text FROM notizen WHERE kunde_id=? OR auftrag_id IN ({ph})", (kid, *ids))),
        "briefe": zeilen(con.execute(f"SELECT nummer, datum, betreff, status FROM briefe WHERE kunde_id=? OR auftrag_id IN ({ph})", (kid, *ids))),
        "termine": zeilen(con.execute(f"SELECT von, bis, typ, titel FROM termine WHERE auftrag_id IN ({ph})", ids)),
        "anhaenge": [r["name"] if "name" in r.keys() else os.path.basename(r["pfad"]) for r in con.execute(f"SELECT * FROM anhaenge WHERE kunde_id=? OR auftrag_id IN ({ph})", (kid, *ids))],
        "rapporte": zeilen(con.execute(f"SELECT datum, status, kunde_name FROM montageberichte WHERE auftrag_id IN ({ph})", ids)),
        "hinweis": "Projektordner und E-Mails im Mailprogramm liegen außerhalb des Programms und sind dort zu prüfen.",
    }
    protokoll.eintragen(con, "datenauskunft", str(kid), f"Datenauskunft für Kunde {k['nummer']} erstellt", {},
                        benutzer=dict(benutzer.aktuell() or {}).get("login", ""), version=VERSION)
    return erg


FELD_NAMEN = {"nummer": "Kundennummer", "kurzname": "Kurzname", "anredeform": "Anrede", "titel": "Titel", "vorname": "Vorname",
              "nachname": "Nachname", "firma": "Firma", "strasse": "Straße", "hausnr": "Hausnummer", "zusatz": "Zusatz", "plz": "PLZ",
              "ort": "Ort", "land": "Land", "anschrift": "Briefanschrift", "anrede": "Briefanrede", "telefon": "Telefon", "mobil": "Mobil",
              "telefax": "Telefax", "email1": "E-Mail", "email2": "E-Mail 2", "email3": "E-Mail 3", "email4": "E-Mail 4", "website": "Website",
              "gruppe": "Kundengruppe", "ustid": "USt-IdNr.", "leitweg_id": "Leitweg-ID", "geburtstag": "Geburtstag",
              "lieferanschrift": "Lieferanschrift", "lieferort": "Lieferort", "rechnungsanschrift": "Rechnungsanschrift",
              "rechnungsort": "Rechnungsort", "bemerkungen": "Bemerkungen", "merkmale": "Merkmale", "newsletter_aus": "Keine Rundmails",
              "zahlungsziel": "Zahlungsziel (Tage)", "skonto": "Skonto %", "skontotage": "Skontotage", "rabatt": "Rabatt %"}


def auskunft_brief(con, kid):
    """Auskunft nach Art. 15 DSGVO als Brief (lesbar, auf dem Briefbogen, als PDF oder per E-Mail versendbar);
    der Versand steht dann als Nachweis in der Korrespondenz."""
    a = kunde_auskunft(con, kid)
    e = einstellungen(con)
    st = a["stammdaten"]

    def liste(titel, zeilen, leer="keine"):
        inhalt = "".join(f"<li>{z}</li>" for z in zeilen) if zeilen else f"<li>{leer}</li>"
        return f"<p><b>{h(titel)}</b></p><ul>{inhalt}</ul>"
    def wert(f):
        if f == "anrede":   # Briefanrede so, wie sie im Brief steht (Platzhalter wie {nachname} aufgelöst)
            return anrede_aufloesen(st)
        return ", ".join(z.strip() for z in str(st[f]).splitlines() if z.strip())
    stamm = [f"{h(FELD_NAMEN[f])}: {h(wert(f))}" for f in FELD_NAMEN if st.get(f) not in (None, "", 0) or f == "nummer"]
    teile = [
        "<p>auf Ihre Anfrage teile ich Ihnen nach Art. 15 DSGVO mit, welche personenbezogenen Daten ich über Sie gespeichert habe.</p>",
        liste("Verantwortlicher", [h(" · ".join(x for x in [a["verantwortlicher"].get("firma"), a["verantwortlicher"].get("firma_inhaber"),
                                                            (a["verantwortlicher"].get("firma_anschrift") or "").replace(chr(10), ", ")] if x))]),
        liste("Zwecke und Rechtsgrundlagen", [h(a["zweck"]), "Glückwunsch- und Rundmails nur mit Einwilligung bzw. als Bestandskunde mit Widerspruchsmöglichkeit (Art. 6 Abs. 1 a bzw. f DSGVO)"]),
        liste("Stammdaten", stamm),
        liste("Aufträge", [f"{h(x['nummer'])} {h(x['bezeichnung'])} (angelegt {de_datum((x['angelegt'] or '')[:10])}, Status {h(x['status'] or '')})" for x in a["auftraege"]]),
        liste("Belege", [f"{h(x['nummer'] or '(Entwurf)')} · {h(BELEGARTEN.get(x['art'], {}).get('name', x['art']))} vom {de_datum(x['datum'])}"
                         + (f" · {de(x['brutto'])} € brutto" if x.get("brutto") else "") for x in a["belege"]]),
        liste("Schriftverkehr (E-Mails, Anrufe, Briefe)", [f"{de_datum((x['datum'] or '')[:10])} · {h(korrespondenz.ARTEN.get(x['art'], x['art']))} · {h(x['betreff'] or '')}"
                                                           for x in a["korrespondenz"]] + [f"{de_datum(x['datum'])} · Brief {h(x['nummer'])} · {h(x['betreff'] or '')}" for x in a["briefe"]]),
        liste("Notizen", [f"{de_datum((x['angelegt'] or '')[:10])}: {h(x['text'])}" for x in a["notizen"]]),
        liste("Termine", [f"{de_datum(x['von'])}{' – ' + de_datum(x['bis']) if x.get('bis') and x['bis'] != x['von'] else ''} · {h(x['typ'] or '')} {h(x['titel'] or '')}" for x in a["termine"]]),
        liste("Dateien, Fotos, Rapporte", [h(x) for x in a["anhaenge"]] + [f"Rapport vom {de_datum(x['datum'])} ({h(x['status'])}), unterschrieben von {h(x['kunde_name'] or '')}" for x in a["rapporte"]]),
        liste("Speicherorte", [h(str(e.get("auskunft_speicherorte") or "").strip() or STANDARD_EINSTELLUNGEN["auskunft_speicherorte"])]),
        liste("Empfänger", [h(str(e.get("auskunft_empfaenger") or "").strip() or STANDARD_EINSTELLUNGEN["auskunft_empfaenger"])]),
        liste("Speicherdauer", ["Rechnungen 8 bzw. 10 Jahre, Angebote und Geschäftsbriefe 6 Jahre, jeweils ab Ende des Kalenderjahres (§ 147 AO, § 257 HGB); "
                                "danach werden Ihre Daten gelöscht bzw. anonymisiert"]),
        liste("Herkunft der Daten", ["von Ihnen selbst bei Anfrage und Auftrag"]),
        "<p>Sie haben das Recht auf Berichtigung, Löschung, Einschränkung der Verarbeitung, Widerspruch und Datenübertragbarkeit sowie auf Beschwerde "
        "bei einer Aufsichtsbehörde (in Baden-Württemberg: Der Landesbeauftragte für den Datenschutz und die Informationsfreiheit). "
        "Eine automatisierte Entscheidungsfindung findet nicht statt. Auf Wunsch erhalten Sie die Daten zusätzlich in einem maschinenlesbaren Format.</p>",
    ]
    b = brief_api(con, "POST", None, None, {}, {"kunde_id": kid, "betreff": "Auskunft über Ihre gespeicherten Daten (Art. 15 DSGVO)", "briefart": "Datenauskunft"})
    anrede = anrede_aufloesen(con.execute("SELECT * FROM kunden WHERE id=?", (kid,)).fetchone() and dict(con.execute("SELECT * FROM kunden WHERE id=?", (kid,)).fetchone()))
    text = f"<p>{h(anrede)}</p>" + "".join(teile) + "<p>Mit freundlichen Grüßen</p>"
    con.execute("UPDATE briefe SET text=? WHERE id=?", (bereinigen(text), b["id"]))
    return brief_laden(con, b["id"])


def _korrespondenz_loeschen(con, kid=None, auftrag_ids=()):
    bed, par = [], []
    if kid:
        bed.append("kunde_id=?")
        par.append(kid)
    if auftrag_ids:
        bed.append(f"auftrag_id IN ({','.join('?' * len(auftrag_ids))})")
        par += list(auftrag_ids)
    if not bed:
        return 0
    n = 0
    for r in con.execute(f"SELECT id, datei FROM korrespondenz WHERE {' OR '.join(bed)}", par).fetchall():
        if r["datei"]:
            p = os.path.normpath(os.path.join(DATEN, r["datei"]))
            if p.startswith(os.path.join(DATEN, "")) and os.path.isfile(p):
                os.remove(p)
        n += 1
    con.execute(f"DELETE FROM korrespondenz WHERE {' OR '.join(bed)}", par)
    return n


def kunde_anonymisieren(con, kid, ausfuehren=False):
    """Nach Ablauf der Aufbewahrungsfristen: Personenbezug eines Kunden entfernen (Art. 17 DSGVO).
    Zahlen (Beträge, Positionen, Stunden) bleiben für Statistik und Nachkalkulation erhalten."""
    k = con.execute("SELECT * FROM kunden WHERE id=?", (kid,)).fetchone()
    if not k:
        raise ApiFehler("Kunde nicht gefunden", 404)
    ids = [r["id"] for r in con.execute("SELECT id FROM auftraege WHERE kunde_id=?", (kid,))]
    ph = ",".join("?" * len(ids)) or "0"
    # Frist je Beleg: Rechnungen (Buchungsbelege) sicherheitshalber 10 Jahre, übrige Belege (Angebote, AB, Lieferscheine,
    # Handelsbriefe) 6 Jahre, jeweils ab Ende des Kalenderjahres; maßgeblich ist das späteste Fristende
    letzter, frist_ende = "", ""
    for b in con.execute(f"SELECT art, datum FROM belege WHERE (auftrag_id IN ({ph}) OR kunde_id=?) AND status<>'entwurf'", (*ids, kid)):
        d = b["datum"] or ""
        if not d[:4].isdigit():
            continue
        letzter = max(letzter, d)
        jahre = AUFBEWAHRUNG_JAHRE if BELEGARTEN.get(b["art"], {}).get("rechnung") else 6
        frist_ende = max(frist_ende, f"{int(d[:4]) + jahre}-12-31")
    for b in con.execute(f"SELECT datum FROM korrespondenz WHERE (kunde_id=? OR auftrag_id IN ({ph})) AND art LIKE 'mail%'", (kid, *ids)):
        d = b["datum"] or ""
        if d[:4].isdigit():
            frist_ende = max(frist_ende, f"{int(d[:4]) + 6}-12-31")   # geschäftliche E-Mails (Handelsbriefe)
    if (k["aufbewahren_bis"] or "") > frist_ende:   # Altbestand aus früheren Programmen oder von Hand gesetzt
        frist_ende = k["aufbewahren_bis"]
    offen = con.execute(f"SELECT COUNT(*) FROM offene_posten WHERE auftrag_id IN ({ph}) AND IFNULL(offen,0)>0.005", ids).fetchone()[0] if ids else 0
    erlaubt = (not frist_ende or frist_ende < date.today().isoformat()) and not offen
    info = {"offene_posten": offen, "kunde": k["kurzname"], "letzter_beleg": letzter, "frist_ende": frist_ende, "erlaubt": erlaubt, "auftraege": len(ids),
            "ordner": [r["ordner"] for r in con.execute(f"SELECT ordner FROM auftraege WHERE id IN ({ph}) AND IFNULL(ordner,'')<>''", ids)]}
    if not ausfuehren:
        return info
    if offen:
        raise ApiFehler("Es gibt noch offene Posten zu diesem Kunden.")
    if not erlaubt:
        raise ApiFehler(f"Die Aufbewahrungsfrist läuft noch bis {de_datum(frist_ende)}; vorher darf der Kunde nicht anonymisiert werden.")
    x = "anonymisiert"
    leer = {f: "" for f in ("vorname", "nachname", "titel", "firma", "strasse", "hausnr", "zusatz", "telefon", "mobil", "telefax", "email1",
                            "email2", "email3", "email4", "website", "bemerkungen", "merkmale", "ustid", "iban", "bic", "geburtstag",
                            "lieferanschrift", "lieferort", "rechnungsanschrift", "rechnungsort", "anrede")}
    spalten = {c[1] for c in con.execute("PRAGMA table_info(kunden)")}
    werte = {f: v for f, v in leer.items() if f in spalten}
    werte.update({"kurzname": f"{x} ({k['nummer']})", "anschrift": x, "aktiv": 0, "geaendert": jetzt()})
    con.execute(f"UPDATE kunden SET {','.join(f + '=?' for f in werte)} WHERE id=?", (*werte.values(), kid))
    if ids:
        con.execute(f"UPDATE auftraege SET kunde_daten=NULL WHERE id IN ({ph})", ids)
        for b in con.execute(f"SELECT id, daten, pdf FROM belege WHERE auftrag_id IN ({ph})", ids).fetchall():
            d = jl(b["daten"], {})
            d["kunde"] = {kk: (vv if kk in ("nummer", "gruppe", "land", "ust", "preise", "zahlungsziel", "skonto", "skontotage") else "")
                          for kk, vv in (d.get("kunde") or {}).items()}
            d.pop("unterschrift", None)
            con.execute("UPDATE belege SET anschrift=?, daten=?, pdf='' WHERE id=?", (x, json.dumps(d, ensure_ascii=False), b["id"]))
            if b["pdf"] and os.path.isfile(b["pdf"]) and os.path.commonpath([os.path.abspath(b["pdf"]), os.path.abspath(DATEN)]) == os.path.abspath(DATEN):
                os.remove(b["pdf"])
        for m in con.execute(f"SELECT id, unterschrift_kunde, unterschrift_monteur FROM montageberichte WHERE auftrag_id IN ({ph})", ids).fetchall():
            for datei in (m["unterschrift_kunde"], m["unterschrift_monteur"]):
                p = os.path.join(montage.ordner(), datei or "")
                if datei and os.path.isfile(p):
                    os.remove(p)
            con.execute("UPDATE montageberichte SET kunde_name=?, unterschrift_kunde='', unterschrift_monteur='', anmerkungen='' WHERE id=?", (x, m["id"]))
        con.execute(f"UPDATE briefe SET empfaenger=?, text='' WHERE auftrag_id IN ({ph})", (x, *ids))
        con.execute(f"DELETE FROM notizen WHERE auftrag_id IN ({ph})", ids)
    con.execute("UPDATE briefe SET empfaenger=?, text='' WHERE kunde_id=?", (x, kid))
    con.execute("DELETE FROM notizen WHERE kunde_id=?", (kid,))
    n_k = _korrespondenz_loeschen(con, kid, ids)
    for a in con.execute(f"SELECT pfad FROM anhaenge WHERE kunde_id=? OR auftrag_id IN ({ph})", (kid, *ids)).fetchall():
        if a["pfad"] and os.path.isfile(a["pfad"]) and os.path.commonpath([os.path.abspath(a["pfad"]), os.path.abspath(DATEN)]) == os.path.abspath(DATEN):
            os.remove(a["pfad"])
    con.execute(f"DELETE FROM anhaenge WHERE kunde_id=? OR auftrag_id IN ({ph})", (kid, *ids))
    con.execute(f"DELETE FROM wiedervorlagen WHERE kunde_id=? OR auftrag_id IN ({ph})", (kid, *ids))
    protokoll.eintragen(con, "kunde_anonymisiert", str(kid), f"Kunde {k['nummer']} nach Ablauf der Aufbewahrungsfrist anonymisiert", {"korrespondenz": n_k},
                        benutzer=dict(benutzer.aktuell() or {}).get("login", ""), version=VERSION)
    return {**info, "erledigt": True, "korrespondenz": n_k}


def konstruktion_dateien(con, aid, datei=None):
    """Stücklisten-Exporte (CSV/TXT, z. B. aus dem CAD) im Unterordner 20_Konstruktion des Projektordners.
    Ohne datei: Liste (neueste zuerst); mit datei (relativer Pfad): Inhalt als Text."""
    ordner, fehler = projektordner(con, aid, anlegen=False)
    if not ordner:
        raise ApiFehler(fehler or "Für diesen Auftrag gibt es keinen Projektordner.")
    stichwort = (einstellungen(con).get("konstruktion_ordner") or "20_Konstruktion").strip()
    nummer = stichwort.split("_")[0].lower()
    kandidaten = [os.path.join(ordner, n) for n in sorted(os.listdir(ordner)) if os.path.isdir(os.path.join(ordner, n))
                  and (n.lower() == stichwort.lower() or (nummer and n.lower().startswith(nummer + "_")) or "konstruktion" in n.lower())]
    genau = os.path.join(ordner, *[t for t in re.split(r"[\\/]", stichwort) if t not in ("", ".", "..")])   # auch Unterordner, z. B. 20_Konstruktion/Export
    if os.path.isdir(genau):
        kandidaten = [genau]
    if not kandidaten:
        raise ApiFehler(f"Im Projektordner gibt es keinen Ordner „{stichwort}“ (CAD-Ordner unter Einstellungen › Kunden & Aufträge).")
    basis = kandidaten[0]
    if datei:
        pfad = os.path.realpath(os.path.join(basis, datei))
        if not pfad.startswith(os.path.realpath(basis) + os.sep) or not os.path.isfile(pfad):
            raise ApiFehler("Datei nicht gefunden", 404)
        with open(pfad, "rb") as f:
            roh = f.read()
        for kod in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return {"name": os.path.basename(pfad), "text": roh.decode(kod)}
            except UnicodeDecodeError:
                continue
    liste = []
    for wurzel, _, files in os.walk(basis):
        for n in files:
            if n.lower().endswith((".csv", ".txt")) and not n.startswith("~"):
                pf = os.path.join(wurzel, n)
                liste.append({"datei": os.path.relpath(pf, basis).replace(os.sep, "/"), "groesse": os.path.getsize(pf),
                              "mtime": round(os.path.getmtime(pf), 1),
                              "geaendert": datetime.fromtimestamp(os.path.getmtime(pf)).isoformat(timespec="minutes")})
    liste.sort(key=lambda x: x["geaendert"], reverse=True)
    erledigt = {(r["datei"], r["mtime"]): r for r in con.execute("SELECT * FROM cad_importe WHERE auftrag_id=?", (aid,))}
    for x in liste:
        e_ = erledigt.get((x["datei"], x["mtime"]))
        x["status"] = e_["status"] if e_ else "neu"
        x["position_id"] = e_["position_id"] if e_ else None
    return {"ordner": os.path.basename(basis), "dateien": liste}


CAD_SCHEMA = """CREATE TABLE IF NOT EXISTS cad_importe (
    auftrag_id INTEGER NOT NULL, datei TEXT NOT NULL, mtime REAL NOT NULL, status TEXT DEFAULT 'importiert',
    position_id INTEGER, zeit TEXT, benutzer TEXT DEFAULT '', PRIMARY KEY (auftrag_id, datei, mtime))"""


def cad_vermerken(con, aid, datei, status, position_id=None):
    """Datei aus dem CAD-Ordner als übernommen bzw. ignoriert vermerken (mit Änderungszeit: eine neue Fassung gilt wieder als neu)."""
    try:
        info = next((x for x in konstruktion_dateien(con, aid)["dateien"] if x["datei"] == datei), None)
    except ApiFehler:
        info = None
    if not info:
        return
    con.execute("INSERT OR REPLACE INTO cad_importe (auftrag_id, datei, mtime, status, position_id, zeit, benutzer) VALUES (?,?,?,?,?,?,?)",
                (aid, datei, info["mtime"], status, position_id, jetzt(), dict(benutzer.aktuell() or {}).get("login", "")))


def cad_neu(con, aid=None):
    """Neue (noch nicht übernommene oder ignorierte) Stücklisten-Dateien in den CAD-Ordnern offener Aufträge."""
    sql = ("SELECT id, nummer, bezeichnung FROM auftraege WHERE IFNULL(ordner,'')<>'' AND IFNULL(status,'') NOT IN "
           "('Erledigt','Abgesagt','Abgerechnet')")
    par = []
    if aid:
        sql += " AND id=?"
        par.append(aid)
    aus = []
    for a in con.execute(sql, par).fetchall():
        try:
            dateien = konstruktion_dateien(con, a["id"])["dateien"]
        except ApiFehler:
            continue
        for x in dateien:
            if x["status"] == "neu":
                aus.append({"auftrag_id": a["id"], "nummer": a["nummer"], "bezeichnung": a["bezeichnung"], **x})
    return aus


def projektordner(con, aid, anlegen=True):
    """Liefert den Projektordner eines Auftrags und legt ihn bei Bedarf automatisch an."""
    a = auftrag_laden(con, aid)
    if a["ordner"] and os.path.isdir(a["ordner"]):
        return a["ordner"], None
    e = einstellungen(con)
    if not anlegen:
        return None, "Kein Projektordner vorhanden."
    if not (e.get("projektpfad") or "").strip():
        return None, "In den Einstellungen ist noch kein Projektpfad hinterlegt."
    try:
        return ordner_anlegen(con, aid), None
    except ApiFehler as f:
        return None, str(f)


def ordner_inhalt(basis, rel):
    pfad = im_ordner(basis, rel)
    if not os.path.isdir(pfad):
        raise ApiFehler("Unterordner nicht gefunden.", 404)
    eintraege = []
    for name in os.listdir(pfad):
        if name.startswith((".", "~$")) or name.lower() in ("desktop.ini", "thumbs.db"):
            continue
        voll = os.path.join(pfad, name)
        try:
            st = os.stat(voll)
        except OSError:
            continue
        ist_ordner = os.path.isdir(voll)
        anzahl = None
        if ist_ordner:
            try:
                anzahl = len([n for n in os.listdir(voll) if not n.startswith((".", "~$"))])
            except OSError:
                anzahl = 0
        eintraege.append({"name": name, "ordner": ist_ordner, "groesse": 0 if ist_ordner else st.st_size,
                          "anzahl": anzahl,
                          "geaendert": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes"),
                          "pfad": os.path.relpath(voll, basis).replace(os.sep, "/")})
    eintraege.sort(key=lambda x: (not x["ordner"], x["name"].lower()))
    return eintraege


ANFRAGE = threading.local()   # Angaben zur laufenden Anfrage (z. B. ob sie vom Büro-PC selbst kommt)
# Dateien, die beim „Öffnen“ ein Programm starten würden – nie aus dem Programm heraus öffnen
AUSFUEHRBAR = {".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".msi", ".msp", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
               ".hta", ".jar", ".lnk", ".url", ".reg", ".cpl", ".dll", ".application", ".appref-ms", ".scf", ".inf", ".gadget", ".msc", ".py", ".pyw", ".sh"}


def nur_am_pc(was):
    """Fenster auf dem Büro-PC öffnen darf nur, wer daran sitzt – nicht ein anderes Gerät im Netz."""
    if not getattr(ANFRAGE, "lokal", True):
        raise ApiFehler(f"{was} geht nur direkt am Büro-PC. Auf diesem Gerät die Datei bitte herunterladen.", 403)


def oeffnen(pfad):
    if os.path.isfile(pfad) and os.path.splitext(pfad)[1].lower() in AUSFUEHRBAR:
        raise ApiFehler("Programme und Skripte werden aus Sicherheitsgründen nicht aus Jahresring heraus gestartet. "
                        "Bitte „Im Explorer zeigen“ wählen und die Datei dort öffnen.")
    if sys.platform.startswith("win"):
        os.startfile(pfad)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", pfad])
    else:
        subprocess.Popen(["xdg-open", pfad])


def im_explorer_zeigen(pfad):
    """Öffnet den Explorer und markiert die Datei."""
    if sys.platform.startswith("win"):
        subprocess.Popen(f'explorer /select,"{pfad}"')
    else:
        oeffnen(os.path.dirname(pfad))


def in_papierkorb(pfad):
    """Verschiebt in den Windows-Papierkorb; sonst (oder wenn das scheitert) nach daten/papierkorb."""
    if sys.platform.startswith("win"):
        ps = ("Add-Type -AssemblyName Microsoft.VisualBasic; $p = $env:JR_PFAD; "
              "if (Test-Path -LiteralPath $p -PathType Container) "
              "{ [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p,'OnlyErrorDialogs','SendToRecycleBin') } "
              "else { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p,'OnlyErrorDialogs','SendToRecycleBin') }")
        try:
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                           env={**os.environ, "JR_PFAD": pfad}, capture_output=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.SubprocessError):
            pass
        if not os.path.exists(pfad):
            return "Papierkorb"
    korb = os.path.join(DATEN, "papierkorb")
    os.makedirs(korb, exist_ok=True)
    shutil.move(pfad, os.path.join(korb, datetime.now().strftime("%Y%m%d-%H%M%S_") + os.path.basename(pfad)))
    return korb


def dateifehler(f):
    if isinstance(f, PermissionError):
        return ApiFehler("Die Datei ist gerade in einem anderen Programm geöffnet oder schreibgeschützt.")
    return ApiFehler(f"Dateifehler: {f}")


def kunde_daten(daten):
    werte = {}
    for f in KUNDE_FELDER:
        if f in daten:
            v = daten[f]
            if f in ("ust", "skonto", "rabatt"):
                v = zahl(v, float)
            elif f in ("zahlungsziel", "skontotage", "nummer", "aktiv"):
                v = zahl(v, int)
            elif v is None:
                v = ""
            werte[f] = v
    return werte


def lieferant_daten(daten):
    werte = {}
    for f in LIEFERANT_FELDER:
        if f in daten:
            v = daten[f]
            if f in ("vorsteuer", "skonto"):
                v = zahl(v, float)
            elif f in ("zahlungsziel", "skontotage", "nummer", "aktiv"):
                v = zahl(v, int)
            elif f == "iban":
                v = iban_normal(v)
            elif f == "bic":
                v = re.sub(r"\s", "", str(v or "")).upper()
            elif v is None:
                v = ""
            werte[f] = v
    return werte


def lieferant_mit_zaehlern(con, lid):
    l = con.execute("SELECT * FROM lieferanten WHERE id=?", (lid,)).fetchone()
    if not l:
        raise ApiFehler("Lieferant nicht gefunden", 404)
    l = dict(l)
    l["anz_anhaenge"] = con.execute("SELECT COUNT(*) FROM anhaenge WHERE lieferant_id=?", (lid,)).fetchone()[0]
    l["anz_notizen"] = con.execute("SELECT COUNT(*) FROM notizen WHERE lieferant_id=?", (lid,)).fetchone()[0]
    l["anz_zahlungen"] = con.execute("SELECT COUNT(*) FROM zahlungen WHERE lieferant_id=?", (lid,)).fetchone()[0]
    l["offen_summe"] = con.execute(
        "SELECT COALESCE(SUM(betrag),0) FROM zahlungen WHERE lieferant_id=? AND bezahlt=''", (lid,)).fetchone()[0]
    l["iban_gueltig"] = iban_ok(l["iban"]) if l["iban"] else None
    return l


def naechste_zahlungsnummer(con):
    jahr = date.today().year
    r = con.execute("SELECT nummer FROM zahlungen WHERE nummer LIKE ? ORDER BY nummer DESC LIMIT 1",
                    (f"Z{jahr}-%",)).fetchone()
    lfd = int(r["nummer"].split("-")[1]) + 1 if r else 1
    return f"Z{jahr}-{lfd:04d}"


ZAHLUNG_FREI = ("bemerkung", "auftrag_id", "bezahlung")   # auch nach „bezahlt“ änderbar


def zahlung_daten(daten):
    werte = {}
    for f in ZAHLUNG_FELDER:
        if f in daten:
            v = daten[f]
            if f in ("betrag", "vorsteuer", "skonto"):
                v = zahl(v, float)
            elif f in ("lieferant_id", "auftrag_id"):
                v = int(v) if v not in (None, "", 0, "0") else None
            elif f == "iban":
                v = iban_normal(v)
            elif v is None:
                v = ""
            werte[f] = v
    if "lieferant_id" in werte and not werte["lieferant_id"]:
        raise ApiFehler("Bitte einen Lieferanten wählen.")
    return werte


def zahlung_laden(con, zid):
    z = con.execute(
        "SELECT z.*, l.kurzname AS lieferant, l.nummer AS lieferantennr, l.gruppe AS lieferantengruppe, "
        "a.nummer AS auftragsnr FROM zahlungen z JOIN lieferanten l ON l.id=z.lieferant_id "
        "LEFT JOIN auftraege a ON a.id=z.auftrag_id WHERE z.id=?", (zid,)).fetchone()
    if not z:
        raise ApiFehler("Zahlungsauftrag nicht gefunden", 404)
    return dict(z)


def kunde_mit_zaehlern(con, kid):
    k = con.execute("SELECT * FROM kunden WHERE id=?", (kid,)).fetchone()
    if not k:
        raise ApiFehler("Kunde nicht gefunden", 404)
    k = dict(k)
    k["anz_anhaenge"] = con.execute("SELECT COUNT(*) FROM anhaenge WHERE kunde_id=?", (kid,)).fetchone()[0]
    k["anz_notizen"] = con.execute("SELECT COUNT(*) FROM notizen WHERE kunde_id=?", (kid,)).fetchone()[0]
    k["anz_auftraege"] = con.execute("SELECT COUNT(*) FROM auftraege WHERE kunde_id=?", (kid,)).fetchone()[0]
    return k


def auftrag_laden(con, aid):
    a = con.execute(
        "SELECT a.*, k.kurzname AS kunde, k.nummer AS kundennr, k.ort AS kundenort "
        "FROM auftraege a JOIN kunden k ON k.id=a.kunde_id WHERE a.id=?", (aid,)).fetchone()
    if not a:
        raise ApiFehler("Auftrag nicht gefunden", 404)
    a = dict(a)
    kd = jl(a.get("kunde_daten"), None)
    if kd:
        a["kunde"] = kd.get("kurzname") or a["kunde"]
        a["kundenort"] = kd.get("ort") or a.get("kundenort")
    a.pop("kunde_daten", None)
    if a.get("projekt_id"):
        pr = con.execute("SELECT nummer, bezeichnung FROM projekte WHERE id=?", (a["projekt_id"],)).fetchone()
        if pr:
            a["projekt_nr"], a["projekt"] = pr["nummer"], pr["bezeichnung"]
    return a


# ---------- Nummernkreise ----------
# Gespeicherter Zählerstand (einstellungen „zaehler“) = zuletzt vergebene Nummer; er kann über die versteckten
# Nummernkreis-Einstellungen nur erhöht werden. Vergeben wird immer max(Zählerstand, höchste vorhandene) + 1.
def zaehler_stand(con, art, jahr=None):
    z = (einstellungen(con).get("zaehler") or {}).get(art) or {}
    return int(z.get(str(jahr), 0) if jahr is not None else z.get("_", 0) or 0)


def zaehler_setzen(con, art, wert, jahr=None):
    e = einstellungen(con)
    z = dict(e.get("zaehler") or {})
    a = dict(z.get(art) or {})
    a[str(jahr) if jahr is not None else "_"] = int(wert)
    z[art] = a
    con.execute("INSERT OR REPLACE INTO einstellungen VALUES (?, ?)", ("zaehler", json.dumps(z, ensure_ascii=False)))


def _hoechste_lfd(werte, praefix):
    hoch = 0
    for n in werte:
        if n and n.startswith(praefix):
            rest = n[len(praefix):]
            if rest.isdigit():
                hoch = max(hoch, int(rest))
    return hoch


def auftragsnummer_info(con, jahr=None):
    jahr = jahr or date.today().year
    vorhanden = _hoechste_lfd([r[0] for r in con.execute("SELECT nummer FROM auftraege WHERE nummer LIKE ?", (f"{jahr}-%",))], f"{jahr}-")
    letzte = max(vorhanden, zaehler_stand(con, "auftrag", jahr))
    return {"jahr": jahr, "vorhanden": vorhanden, "letzte": letzte, "naechste": f"{jahr}-{letzte + 1:04d}", "naechste_lfd": letzte + 1}


def naechste_auftragsnummer(con):
    return auftragsnummer_info(con)["naechste"]


def rechnungsnummer_praefix(con, jahr):
    return f"{(einstellungen(con).get('rechnungsnr_praefix') or '').strip()}{jahr}-"


def rechnungsnummer_info(con, jahr=None):
    jahr = jahr or date.today().year
    praefix = rechnungsnummer_praefix(con, jahr)
    vorhanden = _hoechste_lfd([r[0] for r in con.execute(
        "SELECT nummer FROM belege WHERE art IN ('rechnung','abschlag','storno','gutschrift','korrektur') AND nummer LIKE ?", (praefix + "%",))], praefix)
    letzte = max(vorhanden, zaehler_stand(con, "rechnung", jahr))
    # Nach einer Rücksicherung kennt die Datenbank später vergebene Nummern nicht mehr – das Protokoll schon.
    # Eine im Echtbetrieb vergebene Rechnungsnummer wird nie ein zweites Mal vergeben (GoBD, § 14 UStG).
    eb = protokoll.echtbetrieb(con)
    if eb:
        vergeben = [r[0] for r in con.execute("SELECT objekt FROM protokoll WHERE art='festschreiben' AND zeit>=? AND objekt LIKE ?", (eb["seit"], praefix + "%"))]
        for r in con.execute("SELECT daten FROM protokoll WHERE art='storno' AND zeit>=?", (eb["seit"],)):
            vergeben.append(str((jl(r[0], {}).get("storno") or {}).get("nummer") or ""))
        letzte = max(letzte, _hoechste_lfd([n for n in vergeben if n.startswith(praefix)], praefix))
    return {"jahr": jahr, "praefix": praefix, "vorhanden": vorhanden, "letzte": letzte,
            "naechste": f"{praefix}{letzte + 1:04d}", "naechste_lfd": letzte + 1}


def kundennummer_info(con):
    e = einstellungen(con)
    vorhanden = con.execute("SELECT MAX(nummer) FROM kunden").fetchone()[0] or 0
    start = int(e.get("kundennr_start") or 100000)
    letzte = max(vorhanden, start - 1, zaehler_stand(con, "kunde"))
    return {"vorhanden": vorhanden, "letzte": letzte, "naechste": letzte + 1}


def statistik(con, kid=None):
    """Kennzahlen je Kunde oder über alle Kunden: Aufträge, Umsatz je Jahr, Angebotsquote, Zahlungsdauer, Top-Kunden."""
    w, p = ("WHERE kunde_id=?", (kid,)) if kid else ("", ())
    erg = {
        "auftraege_status": zeilen(con.execute(
            f"SELECT status, COUNT(*) AS anzahl FROM auftraege {w} GROUP BY status ORDER BY anzahl DESC", p)),
        "auftraege_jahr": zeilen(con.execute(
            f"SELECT substr(nummer,1,4) AS jahr, COUNT(*) AS anzahl FROM auftraege {w} GROUP BY jahr ORDER BY jahr DESC", p)),
        "auftraege_gruppe": zeilen(con.execute(
            f"SELECT gruppe, COUNT(*) AS anzahl FROM auftraege {w} GROUP BY gruppe ORDER BY anzahl DESC", p)),
    }
    # Umsatz (festgeschriebene Rechnungen netto, Abschläge nicht doppelt) je Jahr und je Kunde
    umsatz_jahr, umsatz_kunde = {}, {}
    for b in con.execute("SELECT * FROM belege WHERE art IN ('rechnung','abschlag','storno','gutschrift','korrektur') AND status IN ('fest','storniert')"
                         + (" AND kunde_id=?" if kid else ""), p):
        u = beleg_umsatz(b)
        j = (b["datum"] or "")[:4]
        umsatz_jahr[j] = umsatz_jahr.get(j, 0) + u
        umsatz_kunde[b["kunde_id"]] = umsatz_kunde.get(b["kunde_id"], 0) + u
    erg["umsatz_jahr"] = [{"jahr": j, "umsatz": round(v, 2)} for j, v in sorted(umsatz_jahr.items(), reverse=True) if j]
    erg["umsatz_gesamt"] = round(sum(umsatz_jahr.values()), 2)
    # Angebotsquote: Aufträge mit Angebot/KV, davon beauftragt
    e = einstellungen(con)
    vor = set(e.get("status_angebot") or ["Anfrage", "Angebot"]) | {"Abgesagt"}
    mit_angebot = con.execute("SELECT a.id, a.status FROM auftraege a WHERE a.id IN (SELECT auftrag_id FROM belege WHERE art IN ('angebot','kv'))"
                              + (" AND a.kunde_id=?" if kid else ""), p).fetchall()
    erg["angebote"] = len(mit_angebot)
    erg["beauftragt"] = sum(1 for r in mit_angebot if (r["status"] or "") not in vor)
    erg["abgesagt"] = sum(1 for r in mit_angebot if (r["status"] or "") == "Abgesagt")
    abgerechnet = con.execute("SELECT COUNT(DISTINCT auftrag_id) FROM belege WHERE art='rechnung' AND status='fest'"
                              + (" AND kunde_id=?" if kid else ""), p).fetchone()[0]
    erg["durchschnitt_auftrag"] = round(erg["umsatz_gesamt"] / abgerechnet, 2) if abgerechnet else 0
    erg["offen"] = round(con.execute("SELECT COALESCE(SUM(offen),0) FROM offene_posten" + (" WHERE kunde_id=?" if kid else ""), p).fetchone()[0] or 0, 2)
    # Zahlungsdauer: Tage vom Rechnungsdatum bis zur letzten Zahlung bei bezahlten Posten
    tage = []
    for r in con.execute("SELECT o.datum, MAX(z.datum) AS bezahlt FROM offene_posten o JOIN zahlungseingaenge z ON z.op_id=o.id "
                         "WHERE IFNULL(o.offen,0) <= 0.005" + (" AND o.kunde_id=?" if kid else "") + " GROUP BY o.id", p):
        try:
            tage.append((date.fromisoformat(r["bezahlt"][:10]) - date.fromisoformat(r["datum"][:10])).days)
        except (TypeError, ValueError):
            pass
    erg["zahlungsdauer"] = round(sum(tage) / len(tage), 1) if tage else None
    if not kid:
        erg["kunden_gruppe"] = zeilen(con.execute(
            "SELECT gruppe, COUNT(*) AS anzahl FROM kunden WHERE aktiv=1 GROUP BY gruppe ORDER BY anzahl DESC"))
        erg["kunden_gesamt"] = con.execute("SELECT COUNT(*) FROM kunden WHERE aktiv=1").fetchone()[0]
        erg["neukunden_jahr"] = zeilen(con.execute(
            "SELECT substr(angelegt,1,4) AS jahr, COUNT(*) AS anzahl FROM kunden WHERE IFNULL(angelegt,'')<>'' GROUP BY jahr ORDER BY jahr DESC LIMIT 8"))
        namen = {r["id"]: (r["nummer"], r["kurzname"], r["gruppe"]) for r in con.execute("SELECT id, nummer, kurzname, gruppe FROM kunden")}
        top = sorted(umsatz_kunde.items(), key=lambda x: -x[1])[:10]
        erg["top_kunden"] = [{"id": k, "nummer": namen.get(k, ("", "", ""))[0], "kurzname": namen.get(k, ("", "?", ""))[1], "umsatz": round(v, 2),
                              "anteil": round(v / erg["umsatz_gesamt"] * 100, 1) if erg["umsatz_gesamt"] else 0} for k, v in top]
        ug = {}
        for k, v in umsatz_kunde.items():
            g = namen.get(k, ("", "", ""))[2] or "ohne Gruppe"
            ug[g] = ug.get(g, 0) + v
        erg["umsatz_gruppe"] = [{"gruppe": g, "umsatz": round(v, 2)} for g, v in sorted(ug.items(), key=lambda x: -x[1])]
    else:
        r = con.execute("SELECT MIN(angelegt) AS erster, MAX(angelegt) AS letzter FROM auftraege WHERE kunde_id=?",
                        (kid,)).fetchone()
        erg["erster"], erg["letzter"] = r["erster"], r["letzter"]
        kontakt = [r["letzter"] or ""]
        for sql in ("SELECT MAX(angelegt) FROM notizen WHERE kunde_id=?", "SELECT MAX(datum) FROM briefe WHERE kunde_id=?",
                    "SELECT MAX(datum) FROM korrespondenz WHERE kunde_id=?"):
            try:
                kontakt.append(con.execute(sql, (kid,)).fetchone()[0] or "")
            except sqlite3.Error:
                pass
        erg["letzter_kontakt"] = max(kontakt) or None
        erg["rang"] = statistik_rang(con).get(kid)
    return erg


# ====================== Briefe ======================
def brief_laden(con, bid):
    r = con.execute("SELECT b.*, k.kurzname AS kunde, k.nummer AS kundennr, l.kurzname AS lieferant, a.nummer AS auftragsnr, a.bezeichnung AS auftrag "
                    "FROM briefe b LEFT JOIN kunden k ON k.id=b.kunde_id LEFT JOIN lieferanten l ON l.id=b.lieferant_id "
                    "LEFT JOIN auftraege a ON a.id=b.auftrag_id WHERE b.id=?", (bid,)).fetchone()
    if not r:
        raise ApiFehler("Brief nicht gefunden", 404)
    return dict(r)


def briefe_als_korrespondenz(con, q):
    sql, par = "SELECT b.*, a.nummer AS auftragsnr FROM briefe b LEFT JOIN auftraege a ON a.id=b.auftrag_id WHERE 1=1", []
    for feld, spalte in (("kunde", "b.kunde_id"), ("lieferant", "b.lieferant_id"), ("auftrag", "b.auftrag_id")):
        if q.get(feld):
            sql += f" AND {spalte}=?"
            par.append(int(q[feld]))
    if q.get("art") and not "brief".startswith(q["art"]):
        return []
    return [{"id": f"b{r['id']}", "brief_id": r["id"], "art": "brief", "artname": "Brief", "datum": r["datum"] or "", "betreff": r["betreff"] or "",
             "kurz": f"{r['nummer'] or ''} · {r['status'] or 'Entwurf'}", "auftrag_id": r["auftrag_id"], "auftragsnr": r["auftragsnr"],
             "kunde_id": r["kunde_id"], "lieferant_id": r["lieferant_id"], "an": (r["empfaenger"] or "").split("\n")[0]} for r in con.execute(sql, par)]


def brief_api(con, methode, rid, unter, q, d):
    e = einstellungen(con)
    if methode == "POST" and rid is None:
        kid = int(d["kunde_id"]) if str(d.get("kunde_id") or "").isdigit() else None
        lid = int(d["lieferant_id"]) if str(d.get("lieferant_id") or "").isdigit() else None
        aid = int(d["auftrag_id"]) if str(d.get("auftrag_id") or "").isdigit() else None
        if aid and not kid:
            kid = con.execute("SELECT kunde_id FROM auftraege WHERE id=?", (aid,)).fetchone()["kunde_id"]
        if kid:
            k = auftrag_kunde(con, aid) if aid else dict(con.execute("SELECT * FROM kunden WHERE id=?", (kid,)).fetchone())
            anschrift, anrede = kunde_block(k), anrede_aufloesen(k, "")
        elif lid:
            l = dict(con.execute("SELECT * FROM lieferanten WHERE id=?", (lid,)).fetchone())
            anschrift = "\n".join(x for x in [l.get("anschrift") or l.get("kurzname") or "", f"{l.get('plz') or ''} {l.get('ort') or ''}".strip()] if x)
            anrede = l.get("anrede") or ""
        else:
            raise ApiFehler("Kunde oder Lieferant fehlt.")
        jahr = date.today().year
        n = con.execute("SELECT COUNT(*) FROM briefe WHERE nummer LIKE ?", (f"B{jahr}-%",)).fetchone()[0] + 1
        text = f"<p>{h(anrede or 'Sehr geehrte Damen und Herren,')}</p><p><br></p><p><br></p><p>Mit freundlichen Grüßen</p>"
        cur = con.execute("INSERT INTO briefe (nummer, kunde_id, lieferant_id, auftrag_id, betreff, empfaenger, briefart, datum, status, text, angelegt) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (f"B{jahr}-{n:03d}", kid, lid, aid, d.get("betreff") or "", anschrift, d.get("briefart") or "Brief",
                                                             date.today().isoformat(), "Entwurf", text, jetzt()))
        return brief_laden(con, cur.lastrowid)
    if not rid:
        raise ApiFehler("Unbekannte Anfrage", 404)
    b = brief_laden(con, rid)
    if methode == "GET" and unter is None:
        if b.get("kunde_id"):   # für die Auswahl der Briefanrede
            k = con.execute("SELECT anredeform, titel, vorname, nachname, anrede FROM kunden WHERE id=?", (b["kunde_id"],)).fetchone()
            b["anrede_kunde"] = {**dict(k), "anrede": anrede_aufloesen(dict(k))} if k else {}
        return b
    if methode == "PUT" and unter is None:
        # Der Status wird vom Programm gesetzt (Entwurf, erstellt, per E-Mail versendet) und ist nicht von Hand änderbar
        werte = {k: (bereinigen(d[k]) if k == "text" else d[k]) for k in ("betreff", "empfaenger", "datum", "briefart", "text", "auftrag_id", "ihr_zeichen", "unser_zeichen") if k in d}
        if werte:
            con.execute(f"UPDATE briefe SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [rid])
        return brief_laden(con, rid)
    if methode == "DELETE" and unter is None:
        con.execute("DELETE FROM briefe WHERE id=?", (rid,))
        return {"ok": True}
    if methode == "POST" and unter == "pdf":
        return brief_pdf(con, rid)
    if unter == "mail":
        cfg = e.get("mail") or {}
        if b["kunde_id"]:
            k = con.execute("SELECT * FROM kunden WHERE id=?", (b["kunde_id"],)).fetchone()
        else:
            k = con.execute("SELECT * FROM lieferanten WHERE id=?", (b["lieferant_id"],)).fetchone()
        adr = [k[f"email{i}"] for i in range(1, 5) if k and k[f"email{i}"]]
        name = sauber(f"{b['nummer']}_{b['betreff'] or 'Brief'}") + ".pdf"
        if methode == "GET":
            anrede = (anrede_aufloesen(dict(k)) if k and b["kunde_id"] else (k["anrede"] if k else "")) or "Sehr geehrte Damen und Herren,"
            return {"an": adr[0] if adr else "", "adressen": adr, "betreff": b["betreff"] or "Schreiben",
                    "text": f"{anrede}\n\nim Anhang erhalten Sie mein Schreiben.\n\nMit freundlichen Grüßen\n" + mail_signatur(e),
                    "anhaenge": [{"id": "brief", "name": name, "an": True}], "dateien": [], "eingerichtet": bool(cfg.get("smtp_server") and cfg.get("passwort")),
                    "kopie_an_mich": bool(cfg.get("kopie_an_mich")), "absender": cfg.get("adresse") or ""}
        if methode == "POST":
            pdf = brief_pdf(con, rid)
            anh = []
            if "brief" in (d.get("anhaenge") or ["brief"]):
                with open(pdf["archiv"], "rb") as f:
                    anh.append((name, f.read(), "application/pdf"))
            con.commit()
            try:
                r = mailversand.senden(cfg, d.get("an"), d.get("cc"), d.get("betreff") or "", d.get("text") or "", anh, kopie_an_mich=bool(d.get("kopie_an_mich")))
            except mailversand.MailFehler as f:
                raise ApiFehler(str(f))
            con.execute("UPDATE briefe SET status='per E-Mail versendet' WHERE id=?", (rid,))
            korrespondenz_eintragen(con, "mail_aus", kunde_id=b["kunde_id"], lieferant_id=b["lieferant_id"], auftrag_id=b["auftrag_id"],
                                    betreff=d.get("betreff") or "", text=d.get("text") or "", an=d.get("an") or "", message_id=r.get("message_id"),
                                    anhaenge=[x[0] for x in anh])
            return r
    raise ApiFehler("Unbekannte Anfrage", 404)


def brief_html(con, bid, als_pdf=False):
    b = brief_laden(con, bid)
    e = einstellungen(con)
    fi = firma_daten(e)
    info = [("Datum", de_datum(b["datum"])), ("Kunden-Nr.", b.get("kundennr")), ("Auftrag", b.get("auftragsnr")),
            ("Ihr Zeichen", (b.get("ihr_zeichen") or "").strip()), ("Unser Zeichen", (b.get("unser_zeichen") or "").strip() or b["nummer"])]
    info_html = "".join(f"<tr><td>{h(l)}</td><td>{h(v)}</td></tr>" for l, v in info if v)
    inhalt = (f'<div class="betreff" style="font-weight:700;margin-bottom:6mm">{h(b["betreff"])}</div>'
              f'<div class="rt">{rich_html(b["text"] or "")}</div>'
              + gruss_html(fi.get("firma_inhaber") or fi.get("firma"), hoehe=fi.get("unterschrift_hoehe")))
    return briefbogen_html(e, fi, f"Brief {b['nummer']}", h(b["empfaenger"] or "").replace("\n", "<br>"), info_html, inhalt, als_pdf)


def brief_pdf(con, bid):
    b = brief_laden(con, bid)
    con.commit()
    e = einstellungen(con)
    name = sauber(f"{b['nummer']}_{b['betreff'] or 'Brief'}") + ".pdf"
    archiv = os.path.join(DATEN, "briefe", (b["datum"] or "")[:4] or "ohne-datum")
    os.makedirs(archiv, exist_ok=True)
    pfad = os.path.join(archiv, name)
    pdf_url_rendern(f"http://127.0.0.1:{PORT}/druck/brief/{bid}?pdf=1", pfad)
    erg = {"archiv": pfad, "projekt": None}
    if b["auftrag_id"]:
        ordner, _ = projektordner(con, b["auftrag_id"])
        if ordner:
            ziel = os.path.join(pdf_unterordner(ordner, "brief", e), name)
            try:
                shutil.copyfile(pfad, ziel)
                erg["projekt"], erg["projekt_rel"] = ziel, os.path.relpath(ziel, ordner).replace(os.sep, "/")
            except OSError:
                pass
    con.execute("UPDATE briefe SET pdf=?, status=CASE WHEN status='Entwurf' THEN 'erstellt' ELSE status END WHERE id=?", (pfad, bid))
    return erg


# ====================== Newsletter ======================
def newsletter(con, methode, q, d):
    """Rundmail an Kunden: eine Mail an die eigene Adresse, alle Empfänger in BCC (in Paketen zu 40)."""
    e = einstellungen(con)
    cfg = e.get("mail") or {}

    def empfaenger(gruppen=None, nur_aktiv=True):
        sql = "SELECT id, nummer, kurzname, gruppe, email1 FROM kunden WHERE IFNULL(email1,'')<>'' AND IFNULL(newsletter_aus,0)=0"
        if nur_aktiv:
            sql += " AND aktiv=1"
        rows = [dict(r) for r in con.execute(sql + " ORDER BY kurzname")]
        return [r for r in rows if not gruppen or (r["gruppe"] or "") in gruppen]
    if methode == "GET":
        return {"empfaenger": empfaenger(None, q.get("alle") != "1"), "gruppen": e.get("kundengruppen") or [], "absender": cfg.get("adresse") or "",
                "eingerichtet": bool(cfg.get("smtp_server") and cfg.get("passwort")), "signatur": mail_signatur(e)}
    if methode == "POST":
        ids = {int(x) for x in d.get("ids") or []}
        liste = [r for r in empfaenger(None, False) if r["id"] in ids]
        if not liste:
            raise ApiFehler("Keine Empfänger ausgewählt.")
        if not (d.get("betreff") or "").strip() or not (d.get("text") or "").strip():
            raise ApiFehler("Betreff und Text fehlen.")
        anh = []
        for a in d.get("anhaenge") or []:
            try:
                anh.append((sauber(a.get("name") or "Anhang"), base64.b64decode(a.get("daten") or ""), None))
            except (ValueError, TypeError):
                raise ApiFehler("Anhang nicht lesbar.")
        if sum(len(x[1]) for x in anh) > 10 * 1024 * 1024:
            raise ApiFehler("Anhänge für Rundmails bitte unter 10 MB halten.")
        text = d["text"].rstrip() + "\n" + mail_signatur(e)
        gesendet = 0
        for i in range(0, len(liste), 40):
            paket = liste[i:i + 40]
            try:
                mailversand.senden(cfg, cfg.get("adresse"), "", d["betreff"], text, anh, bcc=[r["email1"] for r in paket])
            except mailversand.MailFehler as f:
                raise ApiFehler(f"Nach {gesendet} Empfängern abgebrochen: {f}")
            for r in paket:
                korrespondenz_eintragen(con, "mail_aus", kunde_id=r["id"], betreff="Rundmail: " + d["betreff"], text=d["text"], an=r["email1"])
            gesendet += len(paket)
            con.commit()
        return {"gesendet": gesendet}
    raise ApiFehler("Unbekannte Anfrage", 404)


# ====================== QR-Scan mit dem Handy ======================
def scan_api(con, methode, teile, q, d):
    """Mobile Scanseite (/scan): Material und Aufträge per QR-Code, Material auf Auftrag buchen (auch für die Werkstatt)."""
    wer = dict(benutzer.aktuell() or {})
    if methode == "GET" and teile[1:] == ["auftraege"]:
        return personal.offene_auftraege(con)
    if methode == "GET" and len(teile) == 3 and teile[1] == "material" and teile[2].isdigit():
        m = material.laden(con, int(teile[2]))
        return {k: m.get(k) for k in ("id", "nummer", "bezeichnung", "einheit", "bestand", "lager", "lagerort", "kategorie", "dicke", "mindestbestand")}
    if methode == "GET" and len(teile) == 3 and teile[1] == "auftrag" and teile[2].isdigit():
        a = auftrag_laden(con, int(teile[2]))
        tl = [t for t in jl(a.get("titel"), []) if t.get("nr") and not t.get("buchung_gesperrt")]
        return {"id": a["id"], "nummer": a["nummer"], "bezeichnung": a["bezeichnung"], "kunde": a["kunde"], "status": a["status"],
                "leitstand": a.get("leitstand") or "", "titel": tl,
                "kosten": [dict(r) for r in con.execute("SELECT datum, bezeichnung, menge, einheit FROM auftragskosten WHERE auftrag_id=? ORDER BY id DESC LIMIT 10", (a["id"],))]}
    if methode == "GET" and teile[1:] == ["suche"]:
        s = (q.get("q") or "").strip()
        if len(s) < 2:
            return []
        return [{k: m.get(k) for k in ("id", "nummer", "bezeichnung", "einheit", "bestand", "lager")} for m in material.liste(con, {"q": s, "status": "aktiv"})[:20]]
    if methode == "POST" and teile[1:] == ["buchen"]:
        mid, aid = int(d.get("material_id") or 0), int(d.get("auftrag_id") or 0)
        menge = fl(d.get("menge"))
        if menge <= 0:
            raise ApiFehler("Bitte eine Menge eingeben.")
        m = material.laden(con, mid)
        titel = titel_buchbar(con, aid, d.get("titel")) if d.get("titel") else 0
        try:
            ak = material.ak_buchen(con, {"auftrag_id": aid, "kostenart": material.KAT_KOSTENART.get(m["kategorie"], "werkstoffe"), "material_id": mid,
                                          "menge": menge, "lager_abgang": bool(m.get("lager")), "titel": titel,
                                          "bemerkung": f"per QR-Scan gebucht von {wer.get('name') or wer.get('login') or ''}".strip()})
        except material.Fehler as f:
            raise ApiFehler(str(f))
        return {"ok": True, "id": ak["id"], "bestand": material.laden(con, mid).get("bestand")}
    raise ApiFehler("Unbekannte Anfrage", 404)


def korrespondenz_eintragen(con, art, **kw):
    return korrespondenz.eintragen(con, art, benutzer=dict(benutzer.aktuell() or {}).get("login") or "", **kw)


def geburtstag_naechster(gb, heute_d):
    """Nächster Geburtstag (date) aus „JJJJ-MM-TT“ oder „MM-TT“, sonst None."""
    m = re.search(r"(\d{2})-(\d{2})$", str(gb or "").strip())
    if not m:
        return None
    mo, ta = int(m.group(1)), int(m.group(2))
    for j in (heute_d.year, heute_d.year + 1):
        try:
            d = date(j, mo, ta)
        except ValueError:
            d = date(j, 3, 1) if (mo, ta) == (2, 29) else None
        if d and d >= heute_d:
            return d
    return None


def geburtstage(con, tage=14):
    heute_d = date.today()
    aus = []
    for k in con.execute("SELECT id, nummer, kurzname, geburtstag, email1, anrede FROM kunden WHERE aktiv=1 AND IFNULL(geburtstag,'')<>''"):
        n = geburtstag_naechster(k["geburtstag"], heute_d)
        if n and (n - heute_d).days <= tage:
            alter = None
            if re.match(r"\d{4}-", k["geburtstag"] or ""):
                alter = n.year - int(k["geburtstag"][:4])
            gesendet = con.execute("SELECT 1 FROM notizen WHERE kunde_id=? AND text LIKE 'Geburtstagsmail%' AND angelegt>=?",
                                   (k["id"], n.replace(year=n.year).isoformat()[:4] + "-01-01")).fetchone() is not None
            aus.append({"id": k["id"], "nummer": k["nummer"], "kurzname": k["kurzname"], "datum": n.isoformat(), "in_tagen": (n - heute_d).days,
                        "alter": alter, "email": k["email1"] or "", "gesendet": gesendet})
    return sorted(aus, key=lambda x: x["datum"])


def kunde_mail(con, kid, methode, q, d):
    """Freie E-Mail an einen Kunden (z. B. Geburtstagsgruß); Signatur wird angehängt, Versand wird als Notiz vermerkt."""
    k = con.execute("SELECT * FROM kunden WHERE id=?", (kid,)).fetchone()
    if not k:
        raise ApiFehler("Kunde nicht gefunden", 404)
    e = einstellungen(con)
    cfg = e.get("mail") or {}
    adr = [k[f"email{i}"] for i in range(1, 5) if k[f"email{i}"]]
    auftrag = None
    if str(q.get("auftrag") or "").isdigit():
        auftrag = con.execute("SELECT id, nummer, bezeichnung FROM auftraege WHERE id=? AND kunde_id=?", (int(q["auftrag"]), kid)).fetchone()
    if methode == "GET":
        anrede = anrede_aufloesen(dict(k)).strip()
        betreff, text = "", anrede + "\n\n\n\nMit freundlichen Grüßen"
        if auftrag:   # Auftragsnummer in den Betreff: Antworten des Kunden landen so automatisch beim Auftrag
            betreff = f"{auftrag['nummer']} {auftrag['bezeichnung']}"
        if q.get("vorlage") == "geburtstag":
            betreff = e.get("geburtstag_betreff") or ""
            text = (e.get("geburtstag_text") or "").replace("{anrede}", anrede).replace("{vorname}", k["vorname"] or "").replace("{name}", k["kurzname"] or "")
        an = q.get("an") if q.get("an") in adr else (adr[0] if adr else "")
        return {"an": an, "adressen": adr, "betreff": betreff, "text": text.rstrip() + "\n" + mail_signatur(e),
                "anhaenge": [], "dateien": [], "eingerichtet": bool(cfg.get("smtp_server") and cfg.get("passwort")),
                "kopie_an_mich": bool(cfg.get("kopie_an_mich")), "absender": cfg.get("adresse") or ""}
    if methode == "POST":
        try:
            r = mailversand.senden(cfg, d.get("an"), d.get("cc"), d.get("betreff") or "", d.get("text") or "", [],
                                   kopie_an_mich=bool(d.get("kopie_an_mich")))
        except mailversand.MailFehler as f:
            raise ApiFehler(str(f))
        art = "Geburtstagsmail" if (d.get("betreff") or "") == (e.get("geburtstag_betreff") or "-") else "E-Mail"
        con.execute("INSERT INTO notizen (kunde_id, text, angelegt) VALUES (?,?,?)",
                    (kid, f"{art} gesendet an {d.get('an')}: {d.get('betreff')}", jetzt()))
        korrespondenz_eintragen(con, "mail_aus", kunde_id=kid, auftrag_id=auftrag["id"] if auftrag else None,
                                betreff=d.get("betreff") or "", text=d.get("text") or "", an=d.get("an") or "", message_id=r.get("message_id"))
        return r
    raise ApiFehler("Unbekannte Anfrage", 404)


def zahlbest_mail(con, opid, methode, q, d):
    """Zahlungsbestätigung per E-Mail zu einem offenen Posten (nur Mailtext, kein Dokument). Platzhalter siehe
    Einstellungen › E-Mail › Zahlungsbestätigung; Grundlage ist der zuletzt gebuchte Zahlungseingang."""
    op = con.execute("SELECT o.*, a.nummer AS auftragsnr, a.bezeichnung FROM offene_posten o LEFT JOIN auftraege a ON a.id=o.auftrag_id "
                     "WHERE o.id=?", (opid,)).fetchone()
    if not op:
        raise ApiFehler("Offener Posten nicht gefunden", 404)
    k = con.execute("SELECT * FROM kunden WHERE id=?", (op["kunde_id"],)).fetchone()
    if not k:
        raise ApiFehler("Kunde nicht gefunden", 404)
    e = einstellungen(con)
    cfg = e.get("mail") or {}
    if methode == "GET":
        z = con.execute("SELECT * FROM zahlungseingaenge WHERE op_id=? AND art<>'Skonto' ORDER BY id DESC LIMIT 1", (opid,)).fetchone()
        zd = z["datum"] if z else date.today().isoformat()
        skonto = con.execute("SELECT COALESCE(SUM(betrag),0) FROM zahlungseingaenge WHERE op_id=? AND art='Skonto' AND datum=?",
                             (opid, zd)).fetchone()[0]
        gesamt = con.execute("SELECT COALESCE(SUM(betrag),0) FROM zahlungseingaenge WHERE op_id=? AND art<>'Skonto'", (opid,)).fetchone()[0]
        offen = max(0.0, op["offen"] or 0)
        auftrag_bez = con.execute("SELECT COALESCE(SUM(z.betrag),0) FROM zahlungseingaenge z JOIN offene_posten o ON o.id=z.op_id "
                                  "WHERE o.auftrag_id=? AND z.art<>'Skonto'", (op["auftrag_id"],)).fetchone()[0] if op["auftrag_id"] else 0
        ist_abschlag = (op["art"] or "").lower().startswith("abschlag")
        werte = {"belegart": op["art"] or "Rechnung",
                 "schlusssatz": e.get("zahlbest_schluss_abschlag" if ist_abschlag else "zahlbest_schluss_rechnung") or "", "auftrag_bezahlt": de(auftrag_bez),
                 "anrede": anrede_aufloesen(dict(k)).strip(), "vorname": k["vorname"] or "", "name": k["kurzname"] or "",
                 "rechnung": op["nummer"] or "", "rechnungsdatum": de_datum(op["datum"] or ""), "rechnungsbetrag": de(op["betrag"] or 0),
                 "auftrag": op["auftragsnr"] or "", "bezeichnung": op["bezeichnung"] or "",
                 "betrag": de(z["betrag"] if z else 0), "zahlungsdatum": de_datum(zd), "zahlart": (z["art"] if z else "") or "",
                 "skonto": de(skonto), "bezahlt_gesamt": de(gesamt), "offen": de(offen),
                 "status": "vollständig bezahlt" if offen < 0.005 else f"bis auf {de(offen)} € bezahlt"}

        def ersetzen(s):
            return re.sub(r"\{(\w+)\}", lambda m: str(werte.get(m.group(1), m.group(0))), s or "")
        alt_text = (e.get("zahlbest_text") or "").replace("unsere Rechnung {rechnung}", "unsere {belegart} {rechnung}")
        alt_text = alt_text.replace("Ich habe mich gefreut, für Sie arbeiten zu dürfen.", "{schlusssatz}")
        text = re.sub(r"\n{3,}", "\n\n", ersetzen(alt_text))
        if not op["auftragsnr"]:   # ohne Auftrag den Satzteil „zum Auftrag  ()“ entfernen
            text = text.replace(" zum Auftrag  ()", "")
        adr = [k[f"email{i}"] for i in range(1, 5) if k[f"email{i}"]]
        return {"an": adr[0] if adr else "", "adressen": adr, "betreff": ersetzen((e.get("zahlbest_betreff") or "").replace("zu Rechnung {rechnung}", "zu {belegart} {rechnung}")),
                "text": text.rstrip() + "\n" + mail_signatur(e), "anhaenge": [], "dateien": [],
                "eingerichtet": bool(cfg.get("smtp_server") and cfg.get("passwort")),
                "kopie_an_mich": bool(cfg.get("kopie_an_mich")), "absender": cfg.get("adresse") or ""}
    if methode == "POST":
        try:
            r = mailversand.senden(cfg, d.get("an"), d.get("cc"), d.get("betreff") or "", d.get("text") or "", [],
                                   kopie_an_mich=bool(d.get("kopie_an_mich")))
        except mailversand.MailFehler as f:
            raise ApiFehler(str(f))
        korrespondenz_eintragen(con, "mail_aus", kunde_id=k["id"], auftrag_id=op["auftrag_id"],
                                betreff=d.get("betreff") or "", text=d.get("text") or "", an=d.get("an") or "", message_id=r.get("message_id"))
        return r
    raise ApiFehler("Unbekannte Anfrage", 404)


def lieferant_mail(con, lid, methode, q, d):
    """Freie E-Mail an einen Lieferanten aus Jahresring; Signatur wird angehängt, Versand steht in der Korrespondenz."""
    l = con.execute("SELECT * FROM lieferanten WHERE id=?", (lid,)).fetchone()
    if not l:
        raise ApiFehler("Lieferant nicht gefunden", 404)
    e = einstellungen(con)
    cfg = e.get("mail") or {}
    adr = []
    for i in range(1, 5):
        for a in re.split(r"[,;\s]+", l[f"email{i}"] or ""):
            if "@" in a and a not in adr:
                adr.append(a)
    auftrag = None
    if str(q.get("auftrag") or "").isdigit():
        auftrag = con.execute("SELECT id, nummer, bezeichnung FROM auftraege WHERE id=?", (int(q["auftrag"]),)).fetchone()
    if methode == "GET":
        anrede = (l["anrede"] or "").strip() or "Sehr geehrte Damen und Herren,"
        betreff = f"{auftrag['nummer']} {auftrag['bezeichnung']}" if auftrag else ""
        if l["unsere_kundennr"] and not betreff:
            betreff = f"Kunden-Nr. {l['unsere_kundennr']}: "
        an = q.get("an") if q.get("an") in adr else (adr[0] if adr else "")
        return {"an": an, "adressen": adr, "betreff": betreff, "text": anrede + "\n\n\n\nMit freundlichen Grüßen\n" + mail_signatur(e),
                "anhaenge": [], "dateien": [], "eingerichtet": bool(cfg.get("smtp_server") and cfg.get("passwort")),
                "kopie_an_mich": bool(cfg.get("kopie_an_mich")), "absender": cfg.get("adresse") or ""}
    if methode == "POST":
        try:
            r = mailversand.senden(cfg, d.get("an"), d.get("cc"), d.get("betreff") or "", d.get("text") or "", [],
                                   kopie_an_mich=bool(d.get("kopie_an_mich")))
        except mailversand.MailFehler as f:
            raise ApiFehler(str(f))
        con.execute("INSERT INTO notizen (lieferant_id, text, angelegt) VALUES (?,?,?)",
                    (lid, f"E-Mail gesendet an {d.get('an')}: {d.get('betreff')}", jetzt()))
        korrespondenz_eintragen(con, "mail_aus", lieferant_id=lid, auftrag_id=auftrag["id"] if auftrag else None,
                                betreff=d.get("betreff") or "", text=d.get("text") or "", an=d.get("an") or "", message_id=r.get("message_id"))
        return r
    raise ApiFehler("Unbekannte Anfrage", 404)


def statistik_rang(con):
    """Rang jedes Kunden nach Umsatz (1 = umsatzstärkster)."""
    u = {}
    for b in con.execute("SELECT * FROM belege WHERE art IN ('rechnung','abschlag','storno','gutschrift','korrektur') AND status IN ('fest','storniert')"):
        u[b["kunde_id"]] = u.get(b["kunde_id"], 0) + beleg_umsatz(b)
    return {k: i for i, (k, v) in enumerate(sorted(u.items(), key=lambda x: -x[1]), 1) if v > 0}


# ====================== Positionen & Kalkulation ======================
POS_JSON = ("masse", "zeige", "stueckliste", "beschlaege", "zeiten", "extras", "bilder")
POS_FELDER = ["parent_id", "titel", "sort", "gesperrt", "alternativ", "gruppe", "status", "menge", "einheit", "text", "masse",
              "einzelpreis", "preis_manuell", "zeige", "unterdruck", "stueckliste", "beschlaege", "zeiten",
              "zeitmodus", "extras", "bilder"]


def pos_dict(r):
    p = dict(r)
    for k in POS_JSON:
        p[k] = jl(p.get(k), {} if k in ("masse", "zeige", "extras") else [])
    z = {"posnr": 1, "anzahl": 1, "ep": 1, "gp": 1}
    z.update(p["zeige"] or {})
    p["zeige"] = z
    return p


def kunde_kopie(con, kid):
    """Kundendaten so, wie sie in einen Auftrag kopiert werden."""
    r = con.execute("SELECT * FROM kunden WHERE id=?", (kid,)).fetchone()
    if not r:
        return {}
    k = dict(r)
    kopie = {f: k.get(f) for f in KUNDE_FELDER}
    kopie["kopiert_am"] = jetzt()
    return kopie


def auftrag_kunde(con, aid):
    """Kundendaten des Auftrags (Kopie vom Anlegen). Ältere Aufträge bekommen die Kopie beim ersten Zugriff."""
    r = con.execute("SELECT kunde_id, kunde_daten FROM auftraege WHERE id=?", (aid,)).fetchone()
    if not r:
        raise ApiFehler("Auftrag nicht gefunden", 404)
    k = jl(r["kunde_daten"], None)
    if not k:
        k = kunde_kopie(con, r["kunde_id"])
        con.execute("UPDATE auftraege SET kunde_daten=? WHERE id=?", (json.dumps(k, ensure_ascii=False), aid))
    if not any(k.get(f) for f in adressen.FELDER) and k.get("anschrift"):
        k.update(adressen.zerlegen(k["anschrift"]))
        con.execute("UPDATE auftraege SET kunde_daten=? WHERE id=?", (json.dumps(k, ensure_ascii=False), aid))
    k = dict(k)
    k["id"] = r["kunde_id"]
    return k


def auftrag_kalk(con, aid):
    r = con.execute("SELECT kalk FROM auftraege WHERE id=?", (aid,)).fetchone()
    if not r:
        raise ApiFehler("Auftrag nicht gefunden", 404)
    k = jl(r["kalk"], None)
    if not k:
        k = vorgaben_kopie(einstellungen(con))
        con.execute("UPDATE auftraege SET kalk=? WHERE id=?", (json.dumps(k, ensure_ascii=False), aid))
    # fehlende Schlüssel aus Vorgaben ergänzen (ältere Aufträge)
    for key, v in KALK_VORGABEN.items():
        k.setdefault(key, v)
    # Eigene Bezugsgrößen sind wie alles andere eine Kopie im Auftrag: in den Einstellungen gelöschte oder geänderte
    # bleiben hier unverändert; neu angelegte kommen dazu, damit neue Tätigkeiten sie nutzen können.
    be = con.execute("SELECT wert FROM einstellungen WHERE schluessel='bezug_eigen'").fetchone()
    aktuell = (json.loads(be[0]) if be else STANDARD_EINSTELLUNGEN.get("bezug_eigen")) or []
    kopie = k.get("bezug_eigen")
    if not isinstance(kopie, list):
        kopie = []
    da = {str(b.get("k")) for b in kopie}
    neu = [dict(b) for b in aktuell if b.get("k") and b.get("name") and str(b.get("k")) not in da]
    if neu or not isinstance(k.get("bezug_eigen"), list):
        k["bezug_eigen"] = kopie + neu
        con.execute("UPDATE auftraege SET kalk=? WHERE id=?", (json.dumps(k, ensure_ascii=False), aid))
    # leere Platzhalter (früher P01–P04, K01 … als Standard) aufräumen, sofern nicht in einer Stückliste benutzt
    if any(kalkulation.leer_zeile(w) for w in k.get("werkstoffe", []) + k.get("beschlaege", [])):
        benutzt = set()
        for r2 in con.execute("SELECT stueckliste, beschlaege FROM positionen WHERE auftrag_id=?", (aid,)):
            for t in jl(r2["stueckliste"], []):
                benutzt.add(t.get("werkstoff"))
                for g in ("kanten", "furnier", "oberflaeche"):
                    benutzt.update((t.get(g) or {}).values())
            benutzt.update(b.get("k") for b in jl(r2["beschlaege"], []))
        kalkulation.leere_entfernen(k, benutzt)
    return k


def beschlag_mengen(con, aid):
    """Wie oft jeder Auftragsbeschlag im ganzen Auftrag gebraucht wird (Menge je Position × Positionsmenge, Unterpositionen × Menge der Hauptposition)."""
    pos = {r["id"]: r for r in con.execute("SELECT id, parent_id, menge, beschlaege FROM positionen WHERE auftrag_id=?", (aid,))}
    erg = {}
    for p in pos.values():
        faktor = kalkulation.f(p["menge"])
        if p["parent_id"] and p["parent_id"] in pos:
            faktor *= kalkulation.f(pos[p["parent_id"]]["menge"])
        for b in jl(p["beschlaege"], []):
            if b.get("k"):
                erg[b["k"]] = round(erg.get(b["k"], 0) + kalkulation.f(b.get("menge")) * faktor, 3)
    return erg


def klartext_leer(t):
    return not re.sub(r"<[^>]+>|&nbsp;|\s", "", t or "")


def auftrag_titel(con, aid):
    r = con.execute("SELECT titel, titel_druck FROM auftraege WHERE id=?", (aid,)).fetchone()
    return jl(r["titel"], []) if r else [], (r["titel_druck"] if r else "titel") or "titel"


def titel_buchbar(con, aid, nr):
    """Prüft, ob auf den Titel eines Auftrags gebucht werden darf; liefert die Titelnummer (0 = ohne Titel)."""
    try:
        nr = int(nr or 0)
    except (TypeError, ValueError):
        nr = 0
    if not nr:
        return 0
    t = next((x for x in auftrag_titel(con, aid)[0] if int(x.get("nr") or 0) == nr), None)
    if not t:
        raise ApiFehler("Diesen Titel gibt es im Auftrag nicht.")
    if t.get("buchung_gesperrt"):
        raise ApiFehler(f"Titel T{nr:02d} „{t.get('name') or ''}“ ist abgeschlossen, darauf kann nicht mehr gebucht werden.")
    return nr


def zaehlt(p, titel_gesperrt):
    return not p["gesperrt"] and not p.get("alternativ") and p["zeige"].get("gp", 1) and p["titel"] not in titel_gesperrt


def auftrag_rechnen(con, aid):
    """Rechnet alle Positionen eines Auftrags, nummeriert sie und bildet Summen."""
    kalk = dict(auftrag_kalk(con, aid))
    kalk["_bezug_eigen"] = kalk.get("bezug_eigen") or []   # Kopie im Auftrag (siehe auftrag_kalk)
    titel, titel_druck = auftrag_titel(con, aid)
    titel_reihe = {t["nr"]: i for i, t in enumerate(titel)}
    titel_gesperrt = {t["nr"] for t in titel if t.get("gesperrt")}
    alle = [pos_dict(r) for r in con.execute("SELECT * FROM positionen WHERE auftrag_id=?", (aid,))]
    kinder_von = {}
    for p in alle:
        kinder_von.setdefault(p["parent_id"], []).append(p)
    for liste in kinder_von.values():
        liste.sort(key=lambda p: (p["sort"], p["id"]))

    def rechne(p):
        kinder = kinder_von.get(p["id"], [])
        for i, k in enumerate(kinder, 1):
            k["posnr"] = f"{i:02d}"
            rechne(k)
        p["kinder"] = kinder
        c = position_rechnen(p, kalk, kinder)
        p["_calc"] = c
        p["_ep_gesamt"] = c["ep_gesamt"]
        p["_kosten_gesamt"] = c["kosten_gesamt"]
        return p

    haupt = sorted(kinder_von.get(None, []), key=lambda p: (titel_reihe.get(p["titel"], 999 if p["titel"] else -1), p["sort"], p["id"]))
    nr = 0
    for p in haupt:
        rechne(p)
        nr += 1
        p["posnr"] = f"{nr:02d}"

    soll = {k: 0.0 for k in KATEGORIEN}
    soll["stunden_kst"] = {}
    soll_titel = {}

    def summiere(p, faktor, ziel=None):
        c = p["_calc"]
        for z in (soll, ziel) if ziel is not None else (soll,):
            for k in KATEGORIEN:
                z[k] = z.get(k, 0.0) + c[k] * faktor
            z.setdefault("stunden_kst", {})
            for kst, h in c["stunden_kst"].items():
                z["stunden_kst"][kst] = z["stunden_kst"].get(kst, 0) + h * faktor
        for k in p["kinder"]:
            if not k.get("gesperrt"):
                summiere(k, faktor * fl(k["menge"]), ziel)

    def stunden_von(p, faktor):
        return p["_calc"]["stunden"] * faktor + sum(stunden_von(k, faktor * fl(k["menge"])) for k in p["kinder"] if not k.get("gesperrt"))

    netto = 0.0
    titel_summen, titel_stunden, titel_sk = {}, {}, {}
    for p in haupt:
        if zaehlt(p, titel_gesperrt):
            gp = p["_calc"]["gesamtpreis"]
            netto += gp
            titel_summen[p["titel"]] = titel_summen.get(p["titel"], 0) + gp
            titel_stunden[p["titel"]] = titel_stunden.get(p["titel"], 0) + stunden_von(p, fl(p["menge"]))
            titel_sk[p["titel"]] = titel_sk.get(p["titel"], 0) + p["_calc"]["kosten_gesamt"] * fl(p["menge"])
            st = soll_titel.setdefault(str(p["titel"] or 0), {k: 0.0 for k in KATEGORIEN})
            st["nettopreis"] = st.get("nettopreis", 0.0) + gp
            summiere(p, fl(p["menge"]), st)
    soll["nettopreis"] = round(netto, 2)
    return {"kalk": kalk, "titel": titel, "titel_druck": titel_druck, "positionen": haupt,
            "netto": round(netto, 2), "titel_summen": {str(k): round(v, 2) for k, v in titel_summen.items()},
            "titel_stunden": {str(k): round(v, 2) for k, v in titel_stunden.items()},
            "titel_selbstkosten": {str(k): round(v, 2) for k, v in titel_sk.items()},
            "soll": soll, "soll_titel": soll_titel}


def pos_ausgabe(p):
    """Bereitet eine gerechnete Position für die Oberfläche auf (ohne interne Felder)."""
    d = {k: v for k, v in p.items() if not k.startswith("_") and k != "kinder"}
    d["calc"] = p.get("_calc")
    d["kinder"] = [pos_ausgabe(k) for k in p.get("kinder", [])]
    return d


def finde_pos(haupt, pid, eltern=None):
    for p in haupt:
        if p["id"] == pid:
            return p, eltern
        r = finde_pos(p.get("kinder", []), pid, p)
        if r[0]:
            return r
    return None, None


def pos_werte(daten):
    werte = {}
    for k in POS_FELDER:
        if k in daten:
            v = daten[k]
            if k in POS_JSON:
                v = json.dumps(v if v is not None else ({} if k in ("masse", "zeige", "extras") else []), ensure_ascii=False)
            elif k in ("menge", "einzelpreis", "sort"):
                v = zahl(v, float)
            elif k == "text":
                v = bereinigen(v)
            elif k in ("titel", "gesperrt", "preis_manuell"):
                v = zahl(v, int)
            elif k == "parent_id":
                v = int(v) if v else None
            elif v is None:
                v = ""
            werte[k] = v
    return werte


def position_antwort(con, pid):
    r = con.execute("SELECT auftrag_id FROM positionen WHERE id=?", (pid,)).fetchone()
    if not r:
        raise ApiFehler("Position nicht gefunden", 404)
    erg = auftrag_rechnen(con, r["auftrag_id"])
    p, eltern = finde_pos(erg["positionen"], pid)
    liste = []
    for h in erg["positionen"]:
        liste.append({"id": h["id"], "posnr": h["posnr"], "titel": h["titel"], "text": klartext(h["text"]).split("\n")[0][:70],
                      "menge": h["menge"], "einheit": h["einheit"], "ebene": 0})
        for k in h["kinder"]:
            liste.append({"id": k["id"], "posnr": h["posnr"] + "." + k["posnr"], "titel": h["titel"],
                          "text": klartext(k["text"]).split("\n")[0][:70], "menge": k["menge"], "einheit": k["einheit"], "ebene": 1})
    return {"position": pos_ausgabe(p), "eltern": {"id": eltern["id"], "posnr": eltern["posnr"],
                                                     "text": klartext(eltern["text"]).split("\n")[0], "menge": eltern["menge"],
                                                     "einheit": eltern["einheit"], "masse": eltern["masse"], "titel": eltern["titel"],
                                                     "kinder": len(eltern.get("kinder") or [])} if eltern else None,
            "auftrag": auftrag_laden(con, r["auftrag_id"]), "kalk": erg["kalk"], "titel": erg["titel"],
            "liste": liste, "bezug": kalkulation.bezug_alle(erg["kalk"].get("bezug_eigen"))}


def neue_sortierung(con, aid, parent_id, titel):
    if parent_id:
        r = con.execute("SELECT MAX(sort) FROM positionen WHERE parent_id=?", (parent_id,)).fetchone()
    else:
        r = con.execute("SELECT MAX(sort) FROM positionen WHERE auftrag_id=? AND parent_id IS NULL AND titel=?",
                        (aid, titel)).fetchone()
    return (r[0] or 0) + 1


BILDER = os.path.join(DATEN, "bilder")


def bild_speichern(daten_b64, dateiname):
    """Speichert ein Bild (vom Browser bereits verkleinert) unter daten/bilder und liefert den Dateinamen."""
    os.makedirs(BILDER, exist_ok=True)
    roh = base64.b64decode(daten_b64)
    if len(roh) > 25 * 1024 * 1024:
        raise ApiFehler("Das Bild ist zu groß (über 25 MB).")
    if roh[:3] == b"\xff\xd8\xff":
        endung = ".jpg"
    elif roh[:8] == b"\x89PNG\r\n\x1a\n":
        endung = ".png"
    elif roh[:4] == b"RIFF" and roh[8:12] == b"WEBP":
        endung = ".webp"
    else:
        raise ApiFehler("Nur JPG-, PNG- oder WebP-Bilder werden unterstützt.")
    name = uuid.uuid4().hex[:16] + endung
    with open(os.path.join(BILDER, name), "wb") as f:
        f.write(roh)
    return name


# Druckfassungen der Positionsbilder: so groß, wie das Bild im Beleg gedruckt wird, bei 300 dpi.
# Chrome bettet JPEGs unverändert ins PDF ein – ohne Druckfassung landet das ganze Originalbild im PDF.
BILD_VARIANTEN = {"k": 900, "m": 1400, "g": 2000}   # Breite in Pixeln für klein (45 %), mittel (70 %), ganze Breite
BILD_MAX_HOEHE = 2540                                 # 215 mm bei 300 dpi
GROESSE_VARIANTE = {"klein": "k", "mittel": "m", "gross": "g"}


def bild_masse(pfad):
    """(Breite, Höhe) eines JPG/PNG ohne Zusatzpakete, sonst None."""
    try:
        with open(pfad, "rb") as f:
            kopf = f.read(26)
            if kopf[:8] == b"\x89PNG\r\n\x1a\n":
                return int.from_bytes(kopf[16:20], "big"), int.from_bytes(kopf[20:24], "big")
            if kopf[:2] != b"\xff\xd8":
                return None
            f.seek(2)
            while True:
                b = f.read(1)
                while b and b != b"\xff":
                    b = f.read(1)
                while b == b"\xff":
                    b = f.read(1)
                if not b:
                    return None
                marker = b[0]
                laenge = int.from_bytes(f.read(2), "big")
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    d = f.read(5)
                    return int.from_bytes(d[3:5], "big"), int.from_bytes(d[1:3], "big")
                f.seek(laenge - 2, 1)
    except (OSError, ValueError):
        return None


def variante_name(datei, art):
    stamm, endung = os.path.splitext(datei)
    return f"{stamm}_{art}.jpg"


def bild_fuer_druck(datei, groesse):
    """Liefert die passende Druckfassung, falls vorhanden, sonst das Original."""
    art = GROESSE_VARIANTE.get(groesse, "m")
    v = variante_name(datei, art)
    return v if os.path.isfile(os.path.join(BILDER, v)) else datei


def bild_varianten_noetig(datei):
    """Welche Druckfassungen fehlen für dieses Bild (nur wenn das Original größer ist)?"""
    masse = bild_masse(os.path.join(BILDER, datei))
    if not masse:
        return []
    w, hh = masse
    return [a for a, ziel in BILD_VARIANTEN.items()
            if min(ziel / w, BILD_MAX_HOEHE / hh) < 0.9 and not os.path.isfile(os.path.join(BILDER, variante_name(datei, a)))]


def bild_variante_speichern(datei, art, daten_b64):
    if art not in BILD_VARIANTEN or not re.fullmatch(r"[0-9a-f]{16}\.(jpg|png|webp)", datei or ""):
        raise ApiFehler("Ungültige Bildangabe")
    if not os.path.isfile(os.path.join(BILDER, datei)):
        raise ApiFehler("Bild nicht gefunden", 404)
    roh = base64.b64decode(daten_b64 or "")
    if roh[:3] != b"\xff\xd8\xff":
        raise ApiFehler("Druckfassung muss ein JPG sein")
    with open(os.path.join(BILDER, variante_name(datei, art)), "wb") as f:
        f.write(roh)


def bilder_ohne_varianten(con):
    benutzt = set()
    for r in con.execute("SELECT bilder FROM positionen WHERE IFNULL(bilder,'') NOT IN ('','[]')"):
        try:
            benutzt.update(b.get("datei") for b in json.loads(r["bilder"]) if isinstance(b, dict) and b.get("datei"))
        except ValueError:
            pass
    aus = []
    for d in sorted(benutzt):
        if re.fullmatch(r"[0-9a-f]{16}\.(jpg|png|webp)", d) and os.path.isfile(os.path.join(BILDER, d)):
            fehlt = bild_varianten_noetig(d)
            if fehlt:
                aus.append({"datei": d, "fehlt": fehlt})
    return aus


def position_kopieren(con, pid, parent_id=None, auftrag_id=None, sort=None):
    p = dict(con.execute("SELECT * FROM positionen WHERE id=?", (pid,)).fetchone())
    alt = p.pop("id")
    if auftrag_id:
        p["auftrag_id"] = auftrag_id
    if parent_id is not None:
        p["parent_id"] = parent_id
    p["sort"] = sort if sort is not None else p["sort"] + 0.5
    p["angelegt"] = p["geaendert"] = jetzt()
    cur = con.execute(f"INSERT INTO positionen ({','.join(p)}) VALUES ({','.join('?' * len(p))})", list(p.values()))
    neu = cur.lastrowid
    for k in con.execute("SELECT id, sort FROM positionen WHERE parent_id=?", (alt,)).fetchall():
        position_kopieren(con, k["id"], parent_id=neu, auftrag_id=p["auftrag_id"], sort=k["sort"])
    return neu


def neu_sortieren(con, aid, parent_id, titel):
    if parent_id:
        rows = con.execute("SELECT id FROM positionen WHERE parent_id=? ORDER BY sort, id", (parent_id,)).fetchall()
    else:
        rows = con.execute("SELECT id FROM positionen WHERE auftrag_id=? AND parent_id IS NULL AND titel=? ORDER BY sort, id",
                           (aid, titel)).fetchall()
    for i, r in enumerate(rows, 1):
        con.execute("UPDATE positionen SET sort=? WHERE id=?", (i, r["id"]))
    return [r["id"] for r in rows]


def position_einordnen(con, p, d):
    """Drag & Drop: Hauptposition in einen (anderen) Titel und vor eine bestimmte Position setzen (vor=None: ans Ende)."""
    if p["parent_id"]:
        # Unterposition: nur innerhalb derselben Hauptposition vor eine andere Unterposition setzen (vor=None: ans Ende)
        vor = zahl(d.get("vor"), int) or None
        ids = [r["id"] for r in con.execute("SELECT id FROM positionen WHERE parent_id=? AND id<>? ORDER BY sort, id", (p["parent_id"], p["id"]))]
        ids.insert(ids.index(vor) if vor in ids else len(ids), p["id"])
        for n, x in enumerate(ids, 1):
            con.execute("UPDATE positionen SET sort=? WHERE id=?", (n, x))
        return {"ok": True}
    aid = p["auftrag_id"]
    titel = zahl(d.get("titel"), int)
    vor = zahl(d.get("vor"), int) or None
    ids = [r["id"] for r in con.execute("SELECT id FROM positionen WHERE auftrag_id=? AND parent_id IS NULL AND titel=? "
                                         "AND id<>? ORDER BY sort, id", (aid, titel, p["id"]))]
    i = ids.index(vor) if vor in ids else len(ids)
    ids.insert(i, p["id"])
    alter_titel = p["titel"]
    con.execute("UPDATE positionen SET titel=?, geaendert=? WHERE id=?", (titel, jetzt(), p["id"]))
    # Unterpositionen wandern mit
    offen = [p["id"]]
    while offen:
        kinder = [r["id"] for r in con.execute("SELECT id FROM positionen WHERE parent_id=?", (offen.pop(),))]
        for k in kinder:
            con.execute("UPDATE positionen SET titel=? WHERE id=?", (titel, k))
        offen += kinder
    for n, x in enumerate(ids, 1):
        con.execute("UPDATE positionen SET sort=? WHERE id=?", (n, x))
    if alter_titel != titel:
        neu_sortieren(con, aid, None, alter_titel)
    return {"ok": True}


def positionen_suchen(con, q):
    """Positionen aus allen Aufträgen nach Text suchen (für „aus anderem Auftrag übernehmen“)."""
    wort = (q.get("q") or "").strip()
    sql = ("SELECT p.id, p.auftrag_id FROM positionen p JOIN auftraege a ON a.id=p.auftrag_id WHERE p.parent_id IS NULL "
           "AND IFNULL(p.text,'')<>''")
    par = []
    for w in wort.split():
        sql += " AND ulower(p.text) LIKE ?"
        par.append(f"%{w.lower()}%")
    if q.get("ausser"):
        sql += " AND p.auftrag_id<>?"
        par.append(int(q["ausser"]))
    treffer = con.execute(sql + " ORDER BY a.id DESC, p.sort LIMIT 60", par).fetchall()
    gefunden = {}
    for r in treffer:
        gefunden.setdefault(r["auftrag_id"], set()).add(r["id"])
    ergebnis = []
    for aid, pids in gefunden.items():
        a = con.execute("SELECT a.nummer, a.bezeichnung, a.angelegt, k.kurzname FROM auftraege a LEFT JOIN kunden k ON k.id=a.kunde_id "
                        "WHERE a.id=?", (aid,)).fetchone()
        erg = auftrag_rechnen(con, aid)
        for p in erg["positionen"]:
            if p["id"] in pids:
                ergebnis.append({"id": p["id"], "auftrag_id": aid, "auftrag": a["nummer"], "bezeichnung": a["bezeichnung"],
                                 "kunde": a["kurzname"] or "", "datum": (a["angelegt"] or "")[:10], "posnr": p["posnr"],
                                 "menge": p["menge"], "einheit": p["einheit"], "text": p["text"], "masse": p["masse"],
                                 "ep": p["_calc"]["ep_gesamt"], "unter": len(p["kinder"]), "gesperrt": p["gesperrt"],
                                 "preis_manuell": p["preis_manuell"]})
    return ergebnis


def position_uebernehmen(con, aid, d):
    """Kopiert eine Position (mit Unterpositionen, Stückliste, Beschlägen, Zeiten) aus einem anderen Auftrag."""
    auftrag_laden(con, aid)
    ids = d.get("ids") or ([d["id"]] if d.get("id") else [])
    if not ids:
        raise ApiFehler("Keine Position gewählt.")
    titel = zahl(d.get("titel"), int)
    neu = []
    for pid in ids:
        q = con.execute("SELECT parent_id FROM positionen WHERE id=?", (int(pid),)).fetchone()
        if not q:
            raise ApiFehler("Position nicht gefunden", 404)
        hoechste = con.execute("SELECT MAX(sort) FROM positionen WHERE auftrag_id=? AND parent_id IS NULL AND titel=?",
                               (aid, titel)).fetchone()[0] or 0
        nid = position_kopieren(con, int(pid), auftrag_id=aid, sort=hoechste + 1)
        status = ""
        con.execute("UPDATE positionen SET parent_id=NULL, titel=?, gesperrt=0, status=? WHERE id=?", (titel, status, nid))
        offen = [nid]
        while offen:
            kinder = [r["id"] for r in con.execute("SELECT id FROM positionen WHERE parent_id=?", (offen.pop(),))]
            for k in kinder:
                con.execute("UPDATE positionen SET titel=? WHERE id=?", (titel, k))
            offen += kinder
        neu.append(nid)
    neu_sortieren(con, aid, None, titel)
    return {"ids": neu}


def position_loeschen(con, pid):
    for k in con.execute("SELECT id FROM positionen WHERE parent_id=?", (pid,)).fetchall():
        position_loeschen(con, k["id"])
    con.execute("DELETE FROM positionen WHERE id=?", (pid,))


def soll_ist(con, aid, titel=None):
    """Soll/Ist wie im Branchenprogramm: Kalkulation gegen gebuchte Kosten und Stunden.
    titel=None → ganzer Auftrag; titel=Nr → nur dieser Titel (Ist: Stunden und Auftragskosten mit diesem Titel)."""
    erg = auftrag_rechnen(con, aid)
    kalk, soll = erg["kalk"], erg["soll"]
    nur_titel = titel is not None and str(titel) != ""
    if nur_titel:
        titel = int(titel)
        soll = {k: 0.0 for k in kalkulation.KATEGORIEN} | {"stunden_kst": {}, "nettopreis": 0.0}
        soll.update(erg.get("soll_titel", {}).get(str(titel)) or {})
    e = einstellungen(con)
    zuordnung = e.get("ist_kategorien") or {}
    ist = {k: 0.0 for k in ("werkstoffe", "beschlaege", "oberflaeche", "kleinmaterial", "fremdleistungen", "zukauf")}
    if not nur_titel:   # Lieferantenrechnungen sind dem Auftrag zugeordnet, nicht einem Titel
        for z in con.execute("SELECT z.betrag, z.vorsteuer, l.gruppe FROM zahlungen z JOIN lieferanten l ON l.id=z.lieferant_id "
                             "WHERE z.auftrag_id=?", (aid,)):
            netto = z["betrag"] / (1 + (z["vorsteuer"] or 0) / 100)
            ist[zuordnung.get(z["gruppe"] or "", "kleinmaterial")] += netto
    ak = material.ak_summen(con, aid, titel if nur_titel else None)
    for k, v in ak.items():
        if k in ist:
            ist[k] += v
    ist["material"] = sum(ist.values())
    ist["gk_material"] = ist["material"] * fl(kalk.get("gk_material")) / 100   # Material-GK auch auf Fremdleistungen und Zukauf
    ist["material_gk"] = ist["material"] + ist["gk_material"]
    stunden_kst, lohn, gk_lohn = {}, 0.0, 0.0
    # Stunden ohne (bekannte) Kostenstelle, z. B. Stempeluhr ohne Tätigkeit: mit dem durchschnittlichen GK-Satz des Auftrags
    # bewerten (gewichtet nach den Soll-Stunden der Kostenstellen), sonst hätten sie keinen Gemeinkostenzuschlag
    bekannte = {k["kst"] for k in kalk.get("kostenstellen", [])}
    sh = {k: v for k, v in (soll.get("stunden_kst") or {}).items() if k in bekannte and v}
    if sh:
        gk_schnitt = sum(v * gk_von(kalk, k) for k, v in sh.items()) / sum(sh.values())
    else:
        gks = [fl(k.get("gk")) for k in kalk.get("kostenstellen", [])]
        gk_schnitt = sum(gks) / len(gks) if gks else 0.0
    ohne_kst = 0.0
    for s in con.execute("SELECT * FROM stunden WHERE auftrag_id=?" + (" AND IFNULL(titel,0)=?" if nur_titel else ""),
                         (aid, titel) if nur_titel else (aid,)):
        h = s["stunden"] or 0
        kst = s["kst"] or ""
        stunden_kst[kst] = stunden_kst.get(kst, 0) + h
        l = h * lohn_von(kalk, s["gruppe"] or kalk.get("lohnbasis", "Durchschnitt"))
        lohn += l
        if kst in bekannte:
            gk_lohn += l * gk_von(kalk, kst) / 100
        else:
            ohne_kst += h
            gk_lohn += l * gk_schnitt / 100
    ist.update({"stunden": sum(stunden_kst.values()), "stunden_kst": stunden_kst, "lohn": lohn, "gk_lohn": gk_lohn,
                "lohn_gk": lohn + gk_lohn, "sonder_fertigung": ak.get("sonder_fertigung", 0.0), "sonder_vertrieb": ak.get("sonder_vertrieb", 0.0)})
    ist["selbstkosten"] = ist["material_gk"] + ist["lohn_gk"] + ist["sonder_fertigung"]
    # Ist-Erlös: festgeschriebene Rechnungen (netto, nach Rabatt); vorher die Kalkulationssumme abzüglich Kundenrabatt
    rab = fl(auftrag_kunde(con, aid).get("rabatt"))
    # Gutschriften und Rechnungskorrekturen ändern den Erlös mit (eine Berichtigung ohne Betrag hat netto 0)
    rg = con.execute("SELECT SUM(art='rechnung'), SUM(netto) FROM belege WHERE auftrag_id=? AND art IN ('rechnung','gutschrift','korrektur') "
                     "AND status='fest'", (aid,)).fetchone()
    if not nur_titel and rg[0]:
        ist["nettopreis"], erloes = round(rg[1] or 0, 2), f"berechnet laut {rg[0]} festgeschriebener Rechnung{'en' if rg[0] > 1 else ''}"
    else:
        basis = round(soll.get("nettopreis", 0), 2) if nur_titel else erg["netto"]
        ist["nettopreis"] = round(basis * (1 - rab / 100), 2)
        erloes = f"Kalkulationssumme abzüglich {de(rab, 2 if rab % 1 else 0)} % Kundenrabatt" if rab else "Kalkulationssumme (noch keine Schlussrechnung)"
    ist["wg"] = ist["nettopreis"] - ist["selbstkosten"] - ist["sonder_vertrieb"]
    for z in (soll, ist):
        z["wg_pz"] = round(z["wg"] / z["selbstkosten"] * 100, 2) if z.get("selbstkosten") else 0
    # Positionen mit Preis, aber ohne Kosten (keine Kalkulation): ihr ganzer Preis erscheint als Wagnis und Gewinn
    ohne_kalk = []

    def ohne_kosten(p, nr):
        for k in p["kinder"]:
            if not k.get("gesperrt"):
                ohne_kosten(k, nr + "." + str(k.get("posnr") or "").split(".")[-1])
        c = p["_calc"]
        if fl(c.get("einzelpreis")) > 0 and not c.get("hat_kalk"):
            ohne_kalk.append({"posnr": nr, "text": werkstatt.kurztext(p.get("text") or "")[:50], "betrag": round(fl(c["einzelpreis"]), 2)})
    for p in erg["positionen"]:
        if zaehlt(p, {t.get("nr") for t in erg["titel"] if t.get("gesperrt")}) and (not nur_titel or int(p["titel"] or 0) == titel):
            ohne_kosten(p, str(p.get("posnr") or ""))
    # je Titel: Soll-Stunden/Netto aus der Kalkulation, Ist-Stunden und gebuchte Auftragskosten
    je_titel = []
    ist_h = {r["titel"] or 0: r["h"] for r in con.execute("SELECT IFNULL(titel,0) AS titel, SUM(stunden) AS h FROM stunden WHERE auftrag_id=? GROUP BY IFNULL(titel,0)", (aid,))}
    ist_k = {r["titel"] or 0: r["b"] for r in con.execute("SELECT IFNULL(titel,0) AS titel, SUM(betrag) AS b FROM auftragskosten WHERE auftrag_id=? GROUP BY IFNULL(titel,0)", (aid,))}
    nummern = [0] + [int(t.get("nr") or 0) for t in erg["titel"] if t.get("nr")]
    for nr in nummern:
        t = next((x for x in erg["titel"] if int(x.get("nr") or 0) == nr), {})
        z = {"nr": nr, "name": t.get("name") or ("ohne Titel" if not nr else ""), "gesperrt": bool(t.get("gesperrt")),
             "buchung_gesperrt": bool(t.get("buchung_gesperrt")),
             "soll_stunden": erg["titel_stunden"].get(str(nr), 0), "ist_stunden": round(ist_h.get(nr, 0) or 0, 2),
             "netto": erg["titel_summen"].get(str(nr), 0), "ist_kosten": round(ist_k.get(nr, 0) or 0, 2)}
        if nr == 0 and not (z["soll_stunden"] or z["ist_stunden"] or z["ist_kosten"]):
            continue
        je_titel.append(z)
    return {"soll": soll, "ist": ist, "kostenstellen": [k["kst"] for k in kalk.get("kostenstellen", [])], "titel": je_titel,
            "ohne_kalk": sorted(ohne_kalk, key=lambda x: [int(t) if t.isdigit() else 0 for t in x["posnr"].split(".")]),
            "ohne_kst": {"stunden": round(ohne_kst, 2), "gk_pz": round(gk_schnitt, 1)} if ohne_kst else None, "erloes": erloes,
            "gewaehlt": titel if nur_titel else None,
            "titel_liste": [{"nr": int(t.get("nr") or 0), "name": t.get("name") or ""} for t in erg["titel"] if t.get("nr")]}


def historie_eintrag(con, aid, art, text):
    """Automatischer Eintrag in der Auftragshistorie (z. B. Statuswechsel, Datei abgelegt)."""
    try:
        name = benutzer.aktuell()["name"] if benutzer.aktuell() else ""
    except (KeyError, IndexError, TypeError):
        name = ""
    con.execute("INSERT INTO notizen (auftrag_id, text, angelegt, art, benutzer) VALUES (?,?,?,?,?)", (aid, text, jetzt(), art, name or ""))


def auftrag_historie(con, aid):
    """Alle Ereignisse eines Auftrags als Zeitleiste (neueste zuerst): Notizen, Statuswechsel, Belege, E-Mails, Briefe,
    Termine, Zahlungseingänge, gebuchte Stunden (je Tag), CAD-Importe und Dateien."""
    a = con.execute("SELECT * FROM auftraege WHERE id=?", (aid,)).fetchone()
    if not a:
        raise ApiFehler("Auftrag nicht gefunden", 404)
    ev = []

    def e(zeit, gruppe, art, titel, text="", **x):
        if zeit:
            ev.append({"nr": len(ev), "zeit": str(zeit)[:16].replace("T", " "), "gruppe": gruppe, "art": art, "titel": titel, "text": text, **x})
    e(a["angelegt"], "auftrag", "angelegt", "Auftrag angelegt", a["bezeichnung"] or "")
    for n in con.execute("SELECT * FROM notizen WHERE auftrag_id=?", (aid,)):
        art = n["art"] or "notiz"
        e(n["angelegt"], "auftrag" if art == "status" else "notiz", art,
          {"status": "Status geändert", "datei": "Datei abgelegt"}.get(art, "Notiz"), n["text"], id=n["id"], benutzer=n["benutzer"] or "",
          loeschbar=art == "notiz")
    for x in con.execute("SELECT * FROM anhaenge WHERE auftrag_id=?", (aid,)):
        e(x["angelegt"], "notiz", "anhang", "Datei", x["dateiname"], anhang_id=x["id"])
    for b in con.execute("SELECT id, art, artname, nummer, status, datum, angelegt, netto, brutto, versendet FROM belege WHERE auftrag_id=?", (aid,)):
        name = art_name(b)
        e(b["angelegt"], "beleg", "beleg", f"{name} erstellt", b["nummer"] or "Entwurf", beleg_id=b["id"])
        if b["status"] in ("fest", "storniert") and b["datum"]:
            e(b["datum"] + " 23:59", "beleg", "fest", f"{name} {b['nummer']} festgeschrieben",
              f"{de(b['brutto'] or 0)} € brutto" if BELEGARTEN.get(b["art"], {}).get("preise") else "", beleg_id=b["id"])
    for k in con.execute("SELECT id, art, datum, betreff, von, an FROM korrespondenz WHERE auftrag_id=? AND art<>'brief'", (aid,)):
        e(k["datum"], "korrespondenz", k["art"], korrespondenz.ARTEN.get(k["art"], k["art"]), k["betreff"] or "",
          wer=(k["an"] if k["art"].endswith("_aus") else k["von"]) or "", korr_id=k["id"])
    for b in con.execute("SELECT id, nummer, datum, betreff, status, angelegt FROM briefe WHERE auftrag_id=?", (aid,)):
        e(b["angelegt"], "korrespondenz", "brief", f"Brief {b['nummer'] or ''}".strip(), b["betreff"] or "", brief_id=b["id"])
    for t in con.execute("SELECT id, typ, titel, von, bis, erledigt FROM termine WHERE auftrag_id=?", (aid,)):
        e(t["von"] + " 00:00", "termin", "termin", (t["titel"] or f"Termin {t['typ'] or ''}").strip(),
          (f"{de_datum(t['von'])}–{de_datum(t['bis'])}" if t["bis"] != t["von"] else de_datum(t["von"])) + (" · erledigt" if t["erledigt"] else ""),
          termin_id=t["id"], erledigt=bool(t["erledigt"]))
    for z in con.execute("SELECT z.datum, z.betrag, z.art, b.nummer FROM zahlungseingaenge z JOIN offene_posten o ON o.id=z.op_id "
                         "JOIN belege b ON b.id=o.beleg_id WHERE b.auftrag_id=?", (aid,)):
        e(z["datum"] + " 12:00", "beleg", "zahlung", "Zahlung eingegangen" if (z["art"] or "") != "Skonto" else "Skonto",
          f"{de(z['betrag'] or 0)} € auf {z['nummer']}")
    for s in con.execute("SELECT datum, SUM(stunden) AS h, GROUP_CONCAT(DISTINCT NULLIF(taetigkeit,'')) AS t FROM stunden "
                         "WHERE auftrag_id=? GROUP BY datum", (aid,)):
        e((s["datum"] or "") + " 18:00", "werkstatt", "stunden", f"{de(s['h'] or 0)} h gebucht", s["t"] or "")
    con.execute(CAD_SCHEMA)
    for c in con.execute("SELECT datei, status, zeit FROM cad_importe WHERE auftrag_id=? AND status<>'ignoriert'", (aid,)):
        e(c["zeit"], "werkstatt", "cad", "CAD-Stückliste importiert", c["datei"])
    ev.sort(key=lambda x: (x["zeit"], x["nr"]), reverse=True)
    return {"ereignisse": ev}


def kapazitaet_daten(con, e, von, bis, termine, auftraege):
    """Kapazität für die Planung: je Mitarbeiter und Woche verfügbar/verplant sowie der Arbeitsvorrat der beauftragten
    Aufträge (kalkuliert − gebucht) gegen die freie Kapazität der nächsten 8 Wochen."""
    ts = fl(e.get("tagesstunden") or 8)
    kap = personal.kapazitaet(con, von, bis, termine, ts)
    heute = date.today().isoformat()
    bis8 = plus_tage(heute, 55)
    zuk = zeilen(con.execute("SELECT * FROM termine WHERE bis>=? AND von<=?", (heute, bis8)))
    k8 = personal.kapazitaet(con, heute, bis8, zuk, ts)
    verf8 = sum(w["verfuegbar"] for m in k8["mitarbeiter"] for w in m["wochen"].values())
    plan8 = sum(w["verplant"] for m in k8["mitarbeiter"] for w in m["wochen"].values()) + sum(k8["ohne_zuordnung"].values())
    ende = e.get("status_ende") or []
    vorrat = []
    for a in auftraege:
        if a.get("angebot") or a["status"] in ende or not a.get("soll_stunden"):
            continue
        rest = max(0.0, a["soll_stunden"] - (a.get("ist_stunden") or 0))
        if rest <= 0.05:
            continue
        verplant = 0.0   # Termin-Stunden ab heute
        for t in con.execute("SELECT von, bis, stunden FROM termine WHERE auftrag_id=? AND bis>=?", (a["id"], heute)):
            ges = t["stunden"] if t["stunden"] is not None else arbeitstage(t["von"], t["bis"]) * ts
            n = arbeitstage(t["von"], t["bis"]) or 1
            verplant += ges * arbeitstage(max(t["von"], heute), t["bis"]) / n
        vorrat.append({"id": a["id"], "nummer": a["nummer"], "kunde": a.get("kunde"), "bezeichnung": a["bezeichnung"],
                       "rest": round(rest, 1), "verplant": round(min(rest, verplant), 1), "offen": round(max(0.0, rest - verplant), 1)})
    rest_summe = sum(x["rest"] for x in vorrat)
    je_woche = verf8 / 8 if verf8 else 0
    return {**kap, "vorrat": sorted(vorrat, key=lambda x: -x["offen"]), "vorrat_rest": round(rest_summe, 1),
            "vorrat_offen": round(sum(x["offen"] for x in vorrat), 1), "frei_8w": round(verf8 - plan8, 1), "verfuegbar_8w": round(verf8, 1),
            "reichweite_wochen": round(rest_summe / je_woche, 1) if je_woche else None}


def arbeitstage(von, bis):
    v, b = date.fromisoformat(von), date.fromisoformat(bis)
    return sum(1 for i in range((b - v).days + 1) if (v + timedelta(days=i)).weekday() < 5)


# ====================== Kundenbelege (Angebot..Rechnung) ======================
BELEGARTEN = {
    "angebot": {"name": "Angebot", "kz": "A", "rechnung": False, "preise": True},
    "kv": {"name": "Kostenvoranschlag", "kz": "K", "rechnung": False, "preise": True},
    "ab": {"name": "Auftragsbestätigung", "kz": "AB", "rechnung": False, "preise": True},
    "lieferschein": {"name": "Lieferschein", "kz": "L", "rechnung": False, "preise": False},
    "abnahme": {"name": "Abnahmeprotokoll", "kz": "AP", "rechnung": False, "preise": False},
    "abschlag": {"name": "Abschlagsrechnung", "kz": "AR", "rechnung": True, "preise": True},
    "rechnung": {"name": "Rechnung", "kz": "R", "rechnung": True, "preise": True},
    "storno": {"name": "Stornorechnung", "kz": "S", "rechnung": True, "preise": True},
    "gutschrift": {"name": "Gutschrift", "kz": "G", "rechnung": True, "preise": True},
    "korrektur": {"name": "Rechnungskorrektur", "kz": "RK", "rechnung": True, "preise": True},
}
FREI_ARTEN = ("gutschrift", "korrektur")   # Zeilen frei eingegeben statt aus den Positionen
HINWEIS_13B = "Steuerschuldnerschaft des Leistungsempfängers (§ 13b UStG). Die Umsatzsteuer schuldet der Leistungsempfänger."

BELEG_TEXTE = {
    "angebot": {"einleitung": "{anrede}\n\nvielen Dank für Ihre Anfrage. Gerne biete ich Ihnen die folgenden Arbeiten an:",
                "schluss": "Ich würde mich freuen, den Auftrag für Sie ausführen zu dürfen. Dieses Angebot ist gültig bis {gueltig_bis}.\n\nMit freundlichen Grüßen"},
    "kv": {"einleitung": "{anrede}\n\ngerne erstelle ich Ihnen den folgenden Kostenvoranschlag:",
           "schluss": "Dieser Kostenvoranschlag ist unverbindlich. Die tatsächlichen Kosten können abweichen; eine wesentliche Überschreitung zeige ich Ihnen unverzüglich an.\n\nMit freundlichen Grüßen"},
    "ab": {"einleitung": "{anrede}\n\nvielen Dank für Ihren Auftrag, den ich hiermit wie folgt bestätige:",
           "schluss": "Mit freundlichen Grüßen"},
    "lieferschein": {"einleitung": "Ich liefere Ihnen heute:", "schluss": "Ware vollständig und in einwandfreiem Zustand erhalten."},
    "abnahme": {"einleitung": "Für den Auftrag „{auftrag}“ wurden die folgenden Leistungen gemeinsam besichtigt und geprüft:",
                "schluss": "Mit der Unterschrift erklärt der Auftraggeber die Abnahme der oben aufgeführten Leistungen. Ab der Abnahme beginnt die Gewährleistungsfrist; die Gefahr geht auf den Auftraggeber über. Aufgeführte Mängel und Restarbeiten werden in angemessener Frist erledigt."},
    "abschlag": {"einleitung": "{anrede}\n\nfür den Auftrag „{auftrag}“ berechne ich Ihnen vereinbarungsgemäß folgende Abschlagszahlung:",
                 "schluss": "Vielen Dank!\n\nMit freundlichen Grüßen"},
    "rechnung": {"einleitung": "{anrede}\n\nfür die ausgeführten Arbeiten erlaube ich mir, Ihnen Folgendes in Rechnung zu stellen:",
                 "schluss": "Vielen Dank für Ihren Auftrag!\n\nMit freundlichen Grüßen"},
    "storno": {"einleitung": "{anrede}\n\nhiermit storniere ich die Rechnung {bezug} vom {bezugdatum}.",
               "schluss": "Mit freundlichen Grüßen"},
    "gutschrift": {"einleitung": "{anrede}\n\nfür den Auftrag „{auftrag}“ schreibe ich Ihnen folgenden Betrag gut:",
                   "schluss": "Den Betrag verrechne ich mit offenen Forderungen oder überweise ihn auf Ihr Konto.\n\nMit freundlichen Grüßen"},
    "korrektur": {"einleitung": "{anrede}\n\nzur Rechnung {bezug} vom {bezugdatum} berichtige ich wie folgt:",
                  "schluss": "Mit freundlichen Grüßen"},
    "korrektur_berichtigen": {"einleitung": "{anrede}\n\ndiese Rechnungskorrektur ersetzt die Rechnung {bezug} vom {bezugdatum}. Berichtigt wurden die Angaben der Rechnung; der Rechnungsbetrag bleibt unverändert.",
                              "schluss": "Bereits geleistete Zahlungen sind berücksichtigt. Ein noch offener Betrag ist weiterhin unter der Rechnungsnummer {bezug} zu zahlen.\n\nMit freundlichen Grüßen"},
}

HINWEIS_14B = ("Hinweis für Privatkunden: Sie sind gesetzlich verpflichtet, diese Rechnung zwei Jahre lang "
               "aufzubewahren (§ 14b Abs. 1 Satz 5 UStG).")


def kunde_block(k):
    """Rechnungs-/Hauptanschrift eines Kunden als Zeilen."""
    if (k.get("rechnungsanschrift") or "").strip():
        zeilen = [z for z in k["rechnungsanschrift"].split("\n") if z.strip()]
        ort, land = k.get("rechnungsort") or "", k.get("rechnungsland") or ""
    else:
        zeilen = [z for z in (k.get("anschrift") or k.get("kurzname") or "").split("\n") if z.strip()]
        ort, land = " ".join(x for x in (k.get("plz"), k.get("ort")) if x), k.get("land") or ""
    if ort:
        zeilen.append(ort)
    # DIN 5008: Bestimmungsland in Großbuchstaben als letzte Zeile, bei Inlandsanschriften nur auf Wunsch
    heimat = (LAND_EINST.get("heimat") or "Deutschland").strip().lower()
    if land and (land.strip().lower() != heimat or LAND_EINST.get("immer")):
        zeilen.append(land.upper())
    return "\n".join(zeilen)


LAND_EINST = {"immer": False, "heimat": "Deutschland"}   # wird aus den Einstellungen gesetzt (land_immer)


def firma_daten(e):
    return {k: e.get(k) for k in ("firma", "firma_anschrift", "firma_inhaber", "firma_telefon", "firma_email",
                                  "firma_web", "steuernummer", "ustid", "bank_name", "sepa_iban", "sepa_bic",
                                  "firma_zusatz", "absenderzeile", "unterschrift_hoehe")}


def beleg_zeilen(erg, art, ust_satz):
    """Wandelt die gerechneten Positionen in druckfertige Zeilen um."""
    titel, td = erg["titel"], erg["titel_druck"]
    titel_gesperrt = {t["nr"] for t in titel if t.get("gesperrt")}
    zeilen = []
    letzter_titel = None
    for p in erg["positionen"]:
        if p["titel"] != letzter_titel:
            if td == "summen" and letzter_titel:
                zeilen.append({"typ": "titelsumme", "nr": letzter_titel, "name": titelName_py(titel, letzter_titel),
                               "summe": erg["titel_summen"].get(str(letzter_titel), 0)})
            letzter_titel = p["titel"]
            if p["titel"] and td != "nein":
                zeilen.append({"typ": "titel", "nr": p["titel"], "name": titelName_py(titel, p["titel"]),
                               "gesperrt": p["titel"] in titel_gesperrt})
        if p["gesperrt"]:
            continue
        c = p["_calc"]
        unter = []
        if p["kinder"] and p["unterdruck"] != "verdeckt":
            for k in p["kinder"]:
                if k.get("gesperrt"):   # gesperrte Unterpositionen werden nicht gedruckt
                    continue
                unter.append({"posnr": k["posnr"], "menge": k["menge"], "einheit": k["einheit"], "text": k["text"],
                              "bilder": [x for x in (k.get("bilder") or []) if x.get("drucken", True)],
                              "ep": k["_calc"]["ep_gesamt"], "gp": round(k["_calc"]["ep_gesamt"] * fl(k["menge"]), 2)})
        zeilen.append({"typ": "pos", "id": p["id"], "posnr": p["posnr"], "menge": p["menge"], "einheit": p["einheit"], "text": p["text"],
                       "ep": c["ep_gesamt"], "gp": c["gesamtpreis"], "zeige": p["zeige"],
                       "bilder": [x for x in (p.get("bilder") or []) if x.get("drucken", True)]
                                 + ([x for k in p["kinder"] if not k.get("gesperrt") for x in (k.get("bilder") or []) if x.get("drucken", True)]
                                    if p["kinder"] and p["unterdruck"] == "verdeckt" else []),
                       "zaehlt": bool(zaehlt(p, titel_gesperrt)), "titel_gesperrt": p["titel"] in titel_gesperrt,
                       "alternativ": bool(p.get("alternativ")),
                       "unter": unter, "unterdruck": p["unterdruck"]})
    if td == "summen" and letzter_titel:
        zeilen.append({"typ": "titelsumme", "nr": letzter_titel, "name": titelName_py(titel, letzter_titel),
                       "summe": erg["titel_summen"].get(str(letzter_titel), 0)})
    return zeilen


def titelName_py(titel, nr):
    for t in titel:
        if t["nr"] == nr:
            return t["name"]
    return ""


def summen_rechnen(netto, ust_satz, rabatt_pz=0.0):
    rabatt = round(netto * rabatt_pz / 100, 2)
    netto_r = round(netto - rabatt, 2)
    ust = round(netto_r * ust_satz / 100, 2)
    return {"netto_positionen": round(netto, 2), "rabatt_pz": rabatt_pz, "rabatt": rabatt, "netto": netto_r,
            "ust_satz": ust_satz, "ust": ust, "brutto": round(netto_r + ust, 2)}


def abschlaege_verrechnet(con, aid, ohne_beleg=None):
    """Nummern der Abschlagsrechnungen, die schon in einer festgeschriebenen Rechnung abgezogen sind."""
    n = set()
    for r in con.execute("SELECT id, daten FROM belege WHERE auftrag_id=? AND art='rechnung' AND status='fest'", (aid,)):
        if r["id"] != ohne_beleg:
            n.update(x.get("nummer") for x in (jl(r["daten"], {}) or {}).get("abzuege", []))
    return n


def anrede_aufloesen(k, leer="Sehr geehrte Damen und Herren,"):
    """Briefanrede des Kunden; Variablen wie {nachname}, {vorname}, {titel} werden mit den Stammdaten gefüllt."""
    k = k or {}
    t = (k.get("anrede") or "").strip()
    if not t:
        return leer
    for f in ("nachname", "vorname", "titel"):
        t = re.sub(r"\{\s*" + f + r"\s*\}", (k.get(f) or "").strip(), t, flags=re.I)
    t = re.sub(r"[ \u00a0]{2,}", " ", t).replace(" ,", ",")
    return t


def lohnanteil_rechnen(erg, summen, ust_satz, mit_wg=True):
    """Arbeitskosten der berechneten Positionen für § 35a EStG: der Teil des Preises, der auf die Arbeit entfällt
    (Lohn mit Gemeinkosten, mit_wg: zuzüglich anteiligem Wagnis und Gewinn). Material bleibt außen vor."""
    titel_gesperrt = {t["nr"] for t in erg["titel"] if t.get("gesperrt")}

    def arbeit_je_einheit(p):
        c = p.get("_calc") or {}
        eigen = fl(c.get("lohn_gk")) * ((1 + fl(c.get("wg_pz")) / 100) if mit_wg else 1)
        return eigen + sum(fl(k["menge"]) * arbeit_je_einheit(k) for k in p.get("kinder") or [] if not k.get("gesperrt"))
    roh = 0.0
    for p in erg["positionen"]:
        if not zaehlt(p, titel_gesperrt):
            continue
        c = p.get("_calc") or {}
        ep, gp = fl(c.get("ep_gesamt")), fl(c.get("gesamtpreis"))
        if ep > 0:   # Anteil der Arbeit am (gerundeten) Positionspreis
            anteil = gp * min(1.0, max(0.0, arbeit_je_einheit(p) / ep))
            roh += gp if mit_wg and gp - anteil < 0.01 * max(1.0, fl(p["menge"])) else anteil   # reine Arbeitsposition: ganzer Preis
    netto_vor = fl(erg["netto"])
    faktor = (fl(summen.get("netto")) / netto_vor) if netto_vor else 0   # Rabatt anteilig
    n = round(min(roh * faktor, fl(summen.get("netto"))), 2)
    u = round(n * fl(ust_satz) / 100, 2)
    return {"netto": n, "ust": u, "brutto": round(n + u, 2)}


def beleg_snapshot(con, aid, art, opts=None):
    """Friert Auftrag, Kunde, Positionen und Summen für einen Beleg ein."""
    opts = opts or {}
    e = einstellungen(con)
    a = auftrag_laden(con, aid)
    k = auftrag_kunde(con, aid)
    ust_satz = fl(k.get("ust") if k.get("ust") is not None else 19)
    variante = opts.get("variante") if isinstance(opts.get("variante"), dict) else None
    if variante and variante.get("steuer") == "13b":
        ust_satz = 0.0   # Steuerschuldnerschaft des Leistungsempfängers
    erg = auftrag_rechnen(con, aid)
    daten = {
        "art": art, "artname": (variante or {}).get("name") or BELEGARTEN[art]["name"],
        "firma": firma_daten(e),
        "kunde": {"nummer": k["nummer"], "kurzname": k["kurzname"], "gruppe": k["gruppe"], "ustid": k.get("ustid"),
                  "leitweg_id": k.get("leitweg_id"), "email": k.get("email1") or "", "plz": k.get("plz") or "",
                  "ort": k.get("ort") or "", "land": k.get("land") or "Deutschland", "rechnungsformat": k.get("rechnungsformat") or "",
                  "anrede": anrede_aufloesen(k),
                  "preise": k.get("preise") or "netto", "zahlungsziel": k.get("zahlungsziel") or 14,
                  "skonto": fl(k.get("skonto")), "skontotage": int(fl(k.get("skontotage"))),
                  "lieferanschrift": "\n".join(x for x in [k.get("lieferanschrift") or "", k.get("lieferort") or ""] if x.strip())},
        "auftrag": {"nummer": a["nummer"], "bezeichnung": a["bezeichnung"], "plan_von": a.get("plan_von") or "",
                    "plan_bis": a.get("plan_bis") or ""},
        "preise": BELEGARTEN[art]["preise"],
        "brutto_anzeige": (k.get("preise") == "brutto"),
        "abzuege": [],
    }
    if variante:
        daten["variante"] = {k_: variante.get(k_) for k_ in ("key", "name", "steuer", "basis")}
        if variante.get("steuer") == "13b":
            daten["steuer"] = "13b"
    if art == "korrektur" and opts.get("modus") == "berichtigen":
        # Angaben berichtigen, Betrag bleibt: Zeilen und Summen der ursprünglichen Rechnung, Positionstexte und
        # Kundendaten auf Wunsch neu aus dem Auftrag (nur wenn der Positionsbetrag gleich bleibt)
        bz = opts.get("bezug") or {}
        orig = con.execute("SELECT art, daten FROM belege WHERE id=?", (int(bz.get("id") or 0),)).fetchone()
        if not orig:
            raise ApiFehler("Die ursprüngliche Rechnung wurde nicht gefunden.")
        od = jl(orig["daten"], {}) or {}
        if opts.get("neu_aus_auftrag"):
            neu, _, _ = beleg_snapshot(con, aid, orig["art"], {**(od.get("abschlag") or {}), "druck": opts.get("druck") or {}, "variante": od.get("variante")})
            if abs(fl(neu["summen"].get("netto_positionen", neu["summen"]["netto"])) - fl(od["summen"].get("netto_positionen", od["summen"]["netto"]))) > 0.01:
                raise ApiFehler(f"Die Positionen im Auftrag ergeben {de(neu['summen'].get('netto_positionen', neu['summen']['netto']))} € netto, "
                                f"die Rechnung {de(od['summen'].get('netto_positionen', od['summen']['netto']))} €. Bei der Berichtigung muss der Betrag gleich bleiben; "
                                "für einen anderen Betrag eine Rechnungskorrektur mit Differenz oder ein Storno verwenden.")
            od["zeilen"], od["kunde"] = neu["zeilen"], neu["kunde"]
        elif isinstance(opts.get("eigen"), dict) and opts["eigen"].get("zeilen"):   # bisher übernommene Texte behalten
            od["zeilen"], od["kunde"] = opts["eigen"]["zeilen"], opts["eigen"].get("kunde", od.get("kunde"))
        for k_ in ("zeilen", "summen", "abzuege", "abschlaege", "abschlag", "kunde", "lohn", "brutto_anzeige"):
            if k_ in od:
                daten[k_] = od[k_]
        daten["modus"], daten["grundart"] = "berichtigen", orig["art"]
        daten["bezug"] = {"nummer": bz.get("nummer"), "datum": bz.get("datum") or "", "id": bz.get("id")}
        if od.get("steuer"):
            daten["steuer"] = od["steuer"]
        return daten, k, a
    if art in FREI_ARTEN:
        # Gutschrift / Rechnungskorrektur: Zeilen frei eingegeben (Gutschrift: Beträge positiv eingegeben, als Minus gebucht)
        vz = -1 if art == "gutschrift" else 1
        frei = [x for x in (opts.get("frei") or []) if isinstance(x, dict) and (str(x.get("text") or "").strip() or fl(x.get("betrag")))]
        if not frei:
            raise ApiFehler("Bitte mindestens eine Zeile mit Text und Betrag eingeben.")
        daten["frei"] = [{"text": str(x.get("text") or "").strip(), "betrag": round(fl(x.get("betrag")), 2)} for x in frei]
        daten["zeilen"] = [{"typ": "pos", "posnr": f"{i + 1:02d}", "menge": 1, "einheit": "Psch.", "text": x["text"],
                            "ep": round(vz * x["betrag"], 2), "gp": round(vz * x["betrag"], 2), "zeige": {"posnr": 1, "anzahl": 1, "ep": 1, "gp": 1},
                            "zaehlt": True, "unter": [], "unterdruck": "verdeckt"} for i, x in enumerate(daten["frei"])]
        if isinstance(opts.get("bezug"), dict) and opts["bezug"].get("nummer"):
            daten["bezug"] = {"nummer": opts["bezug"]["nummer"], "datum": opts["bezug"].get("datum") or "", "id": opts["bezug"].get("id")}
        daten["summen"] = summen_rechnen(round(sum(z["gp"] for z in daten["zeilen"]), 2), ust_satz, 0)
        s_ = daten["summen"]
        s_["abzug_brutto"], s_["zahlbetrag"] = 0.0, s_["brutto"]
        return daten, k, a
    if art == "abschlag":
        # Prozent-Abschläge vom Auftragsnetto nach Kundenrabatt (so viel wird später tatsächlich berechnet)
        rab = fl(k.get("rabatt"))
        netto_auftrag = round(erg["netto"] - round(erg["netto"] * rab / 100, 2), 2) if rab else erg["netto"]
        dr = opts.get("druck") or druck_standard("abschlag", e)
        mit_summe = dr.get("ab_summe", True)
        if opts.get("prozent"):
            betrag = round(netto_auftrag * fl(opts["prozent"]) / 100, 2)
            pz = f"{de(fl(opts['prozent']), 2 if fl(opts['prozent']) % 1 else 0)} %"
            zusatz = f"{pz} der Auftragssumme von {de(netto_auftrag)} € netto" if mit_summe else f"{pz} der Auftragssumme"
        else:
            betrag = round(fl(opts.get("betrag")), 2)
            zusatz = f"Auftragssumme {de(netto_auftrag)} € netto" if mit_summe else ""
        nr = con.execute("SELECT COUNT(*) FROM belege WHERE auftrag_id=? AND art='abschlag' AND status IN ('fest','storniert')",
                         (aid,)).fetchone()[0] + 1
        text = opts.get("text") or f"{nr}. Abschlagszahlung\nAuftrag {a['nummer']} „{a['bezeichnung']}“" + (f"\n{zusatz}" if zusatz else "")
        daten["zeilen"] = [{"typ": "pos", "posnr": "01", "menge": 1, "einheit": "Psch.", "text": text, "ep": betrag, "gp": betrag,
                            "zeige": {"posnr": 1, "anzahl": 1, "ep": 1, "gp": 1}, "zaehlt": True, "unter": [], "unterdruck": "verdeckt"}]
        daten["abschlag"] = {"prozent": opts.get("prozent"), "betrag": opts.get("betrag"), "text": opts.get("text")}
        # Auftragspositionen zur Information anhängen (zählen nicht, gehen nicht in die E-Rechnung)
        if dr.get("ab_positionen") in ("ja", "ohne"):
            info = [dict(z, info=True, zaehlt=False, zeige={**z.get("zeige", {}), "ep": z.get("zeige", {}).get("ep", 1) if dr["ab_positionen"] == "ja" else 0,
                                                             "gp": z.get("zeige", {}).get("gp", 1) if dr["ab_positionen"] == "ja" else 0})
                    for z in beleg_zeilen(erg, art, ust_satz) if z["typ"] in ("pos", "titel")]
            if info:
                daten["zeilen"].append({"typ": "titel", "nr": 0, "name": "Grundlage: Positionen des Auftrags", "info": True})
                daten["zeilen"] += info
        netto = betrag
    else:
        daten["zeilen"] = beleg_zeilen(erg, art, ust_satz)
        netto = erg["netto"]
    daten["summen"] = summen_rechnen(netto, ust_satz, fl(k.get("rabatt")) if art != "abschlag" else 0)
    if art == "rechnung":
        daten["lohnanteil"] = lohnanteil_rechnen(erg, daten["summen"], ust_satz, e.get("lohnanteil_wg", True) is not False)
        # Abschlagsrechnungen: per Häkchen wählbar, welche in dieser Schlussrechnung verrechnet werden
        aus = {int(x) for x in ((opts.get("druck") or {}).get("abschlaege_aus") or []) if str(x).isdigit()}
        schon = abschlaege_verrechnet(con, aid, ohne_beleg=opts.get("beleg_id"))
        daten["abschlaege"] = []
        for b in con.execute("SELECT * FROM belege WHERE auftrag_id=? AND art='abschlag' AND status='fest' ORDER BY datum, id", (aid,)):
            frei = b["nummer"] not in schon
            mit = frei and b["id"] not in aus
            daten["abschlaege"].append({"id": b["id"], "nummer": b["nummer"], "datum": b["datum"], "brutto": b["brutto"],
                                        "verrechnen": mit, "anderswo": not frei})
            if mit:
                daten["abzuege"].append({"id": b["id"], "nummer": b["nummer"], "datum": b["datum"], "netto": b["netto"], "ust": b["ust"], "brutto": b["brutto"]})
    s = daten["summen"]
    s["abzug_brutto"] = round(sum(x["brutto"] for x in daten["abzuege"]), 2)
    s["zahlbetrag"] = round(s["brutto"] - s["abzug_brutto"], 2)
    return daten, k, a


def text_einsetzen(vorlage, werte):
    """Ersetzt Platzhalter wie {anrede}. Tolerant gegenüber Formatierung mitten im Platzhalter
    (z. B. „{<b>anrede</b>}“), Groß-/Kleinschreibung und geschützten Leerzeichen."""
    out = vorlage or ""
    html = ist_html(out)
    tag = r"(?:<[^>]+>|&nbsp;|\s|\u00a0|\u200b)*"
    for k, v in werte.items():
        wert = _esc(str(v or ""), quote=False) if html else str(v or "")
        muster = r"(?:\{|&#123;|&lbrace;)" + tag + tag.join(re.escape(c) for c in k) + tag + r"(?:\}|&#125;|&rbrace;)"
        out = re.sub(muster, lambda m: wert, out, flags=re.I)
    return out


def beleg_platzhalter(b):
    d = b.get("daten") or {}
    return {"anrede": (d.get("kunde") or {}).get("anrede") or "Sehr geehrte Damen und Herren,",
            "auftrag": (d.get("auftrag") or {}).get("bezeichnung", ""), "betreff": b.get("betreff") or "",
            "nummer": b.get("nummer") or "", "bezug": (d.get("bezug") or {}).get("nummer", ""),
            "bezugdatum": de_datum((d.get("bezug") or {}).get("datum")) if (d.get("bezug") or {}).get("datum") else "",
            "gueltig_bis": gueltig_bis(b.get("datum"))}


def gueltig_bis(datum, tage=None):
    """Belegdatum + Gültigkeitsdauer (Einstellung angebot_gueltig_tage, Vorgabe 7) als TT.MM.JJJJ."""
    try:
        tage = int(einstellungen_roh("angebot_gueltig_tage", 7) if tage is None else tage)
        d = date.fromisoformat(str(datum or date.today().isoformat())[:10])
    except (TypeError, ValueError):
        return ""
    return de_datum((d + timedelta(days=tage)).isoformat())


UNTERSCHRIFT = "unterschrift.png"


def gruss_html(name, mit_unterschrift=True, hoehe=None):
    """Gruß mit Namen; darüber die eingescannte Unterschrift, als wäre sie mit dem Füller über den Namen geschrieben."""
    bild = ""
    if mit_unterschrift and os.path.exists(os.path.join(DATEN, UNTERSCHRIFT)):
        stand = int(os.path.getmtime(os.path.join(DATEN, UNTERSCHRIFT)))
        try:
            mm = min(35.0, max(6.0, float(str(hoehe).replace(",", ".")))) if hoehe not in (None, "") else 17.0
        except ValueError:
            mm = 17.0
        # Höhe einstellbar (Einstellungen › Firma); die Unterschrift sitzt weiter mit ihrem unteren Teil über dem Namen
        bild = f'<img class="unterschrift" src="/api/unterschrift?v={stand}" alt="" style="height:{mm:g}mm;top:{-mm * 7 / 17:.1f}mm">'
    return f'<div class="gruss{" mit-unterschrift" if bild else ""}">{h(name or "")}{bild}</div>'


def druck_standard(art, e=None):
    """Sinnvolle Vorgaben je Belegart; in den Einstellungen je Belegart überschreibbar (druck_vorgaben)."""
    rechnung = BELEGARTEN.get(art, {}).get("rechnung", False)
    preise = BELEGARTEN.get(art, {}).get("preise", True)
    std = {"nummer": "ja", "anrede": True, "preise": preise, "summen": "ja" if preise else "nein",
           "konditionen": rechnung and art not in ("storno", "gutschrift"), "qr": rechnung and art not in ("storno", "gutschrift"), "zusammen": True,
           "briefbogen": True, "unterschrift": True, "ab_positionen": "nein", "ab_summe": True,
           "bilder": art in ("angebot", "kv", "ab"),   # Positionsbilder standardmäßig nur in Angebot, KV und AB
           "unten_buendig": bool((e or {}).get("unten_buendig", True))}
    return {**std, **(((e or {}).get("druck_vorgaben") or {}).get(art) or {})}


def druck_einstellung(b, e=None):
    roh = jl(b.get("druck") if isinstance(b.get("druck"), str) else json.dumps(b.get("druck") or {}), {})
    d = {**druck_standard(b["art"], e), **roh}
    if b.get("status") in ("fest", "storniert") and "unten_buendig" not in roh:
        d["unten_buendig"] = False   # festgeschriebene Belege behalten ihr bisheriges Druckbild
    if BELEGARTEN.get(b["art"], {}).get("rechnung"):
        d["preise"], d["nummer"] = True, "ja"  # Rechnungen brauchen Preise, Summen und die volle Nummer
        if d["summen"] == "nein":
            d["summen"] = "ja"
    if b["art"] == "rechnung" and "lohnanteil" not in d:
        regel = (e or {}).get("lohnanteil", "privat")
        gruppe = ((jl(b["daten"], {}) if isinstance(b.get("daten"), str) else (b.get("daten") or {})).get("kunde") or {}).get("gruppe")
        d["lohnanteil"] = regel == "alle" or (regel == "privat" and gruppe == "Privatkunde")
    return d


def beleg_laden(con, bid):
    b = con.execute("SELECT * FROM belege WHERE id=?", (bid,)).fetchone()
    if not b:
        raise ApiFehler("Beleg nicht gefunden", 404)
    b = dict(b)
    b["daten"] = jl(b["daten"], {})
    b["artname"] = art_name(b)
    b["ist_rechnung"] = BELEGARTEN.get(b["art"], {}).get("rechnung", False)
    b["druck"] = druck_einstellung(b, einstellungen(con))
    op = con.execute("SELECT * FROM offene_posten WHERE beleg_id=?", (bid,)).fetchone()
    b["op"] = dict(op) if op else None
    return b


def art_name(b):
    """Anzeigename eines Belegs: eigene Belegart (Variante) oder die Grundart."""
    try:
        eigen = b["artname"] if "artname" in b.keys() else ""
    except AttributeError:
        eigen = b.get("artname", "")
    return eigen or BELEGARTEN.get(b["art"], {}).get("name", b["art"])


def beleg_titel(b):
    return f"{b['artname']} {b['nummer']}" if b.get("nummer") else f"{b['artname']} (Entwurf)"


def naechste_lfd(con, aid, art):
    r = con.execute("SELECT MAX(lfd) FROM belege WHERE auftrag_id=? AND art=? AND nummer<>''", (aid, art)).fetchone()
    return (r[0] or 0) + 1


def beleg_nummer(a_nummer, art, lfd):
    return f"{a_nummer}-{BELEGARTEN[art]['kz']}{lfd:02d}"


def beleg_variante(e, key):
    """Eigene Belegart (Einstellungen › Texte › Eigene Belegarten) nach Schlüssel."""
    return next((v for v in (e.get("beleg_varianten") or []) if key and v.get("key") == key), None)


def bezug_rechnung(con, aid, bid):
    """Festgeschriebene Rechnung desselben Auftrags, auf die sich Gutschrift oder Korrektur beziehen."""
    r = con.execute("SELECT id, nummer, datum, art, status FROM belege WHERE id=? AND auftrag_id=?", (int(bid or 0), aid)).fetchone()
    if not r or r["art"] not in ("rechnung", "abschlag", "korrektur") or r["status"] not in ("fest", "storniert"):
        raise ApiFehler("Bitte eine festgeschriebene Rechnung dieses Auftrags als Bezug wählen.")
    return {"id": r["id"], "nummer": r["nummer"], "datum": r["datum"]}


def beleg_anlegen(con, aid, d):
    art = d.get("art")
    e = einstellungen(con)
    v = beleg_variante(e, d.get("variante"))
    if v:
        art = v.get("basis") or art
    if art not in BELEGARTEN or art == "storno":
        raise ApiFehler("Unbekannte Belegart.")
    if art == "abschlag" and not (fl(d.get("prozent")) or fl(d.get("betrag"))):
        raise ApiFehler("Bitte Betrag oder Prozent für die Abschlagsrechnung angeben.")
    if art not in ("abschlag",) + FREI_ARTEN and not con.execute("SELECT 1 FROM positionen WHERE auftrag_id=?", (aid,)).fetchone():
        raise ApiFehler("Der Auftrag hat noch keine Positionen.")
    d = {**d, "druck": druck_standard(art, e), "variante": v}
    plan_uebernahme = {}
    if art in ("angebot", "kv", "ab"):
        # Zahlungsplan des letzten Angebots / der letzten AB übernehmen (z. B. Angebot → Auftragsbestätigung)
        for r in con.execute("SELECT druck FROM belege WHERE auftrag_id=? AND art IN ('angebot','kv','ab') ORDER BY datum DESC, id DESC", (aid,)):
            alt = jl(r["druck"], {})
            if alt.get("konditionen") == "plan":
                plan_uebernahme = {k: alt[k] for k in ("konditionen", "plan_anzahlung", "plan_rest", "plan_wochen") if k in alt}
                d["druck"] = {**d["druck"], **plan_uebernahme}
                break
    berichtigen = art == "korrektur" and d.get("modus") == "berichtigen"
    if berichtigen:   # Betrag bleibt: keine Zahlungsaufforderung, maßgeblich bleibt die ursprüngliche Rechnung
        d["druck"] = {**d["druck"], "konditionen": False, "qr": False}
    if art == "korrektur" or (art == "gutschrift" and d.get("bezug_id")):
        d["bezug"] = bezug_rechnung(con, aid, d.get("bezug_id"))
    daten, k, a = beleg_snapshot(con, aid, art, d)
    texte = dict((e.get("beleg_texte") or {}).get("korrektur_berichtigen" if berichtigen else art)
                 or BELEG_TEXTE["korrektur_berichtigen" if berichtigen else art])
    if v:
        texte.update({t_: v[t_] for t_ in ("einleitung", "schluss") if (v.get(t_) or "").strip()})
    werte = {"anrede": daten["kunde"]["anrede"], "auftrag": a["bezeichnung"], "betreff": a["bezeichnung"],
             "bezug": (daten.get("bezug") or {}).get("nummer", ""),
             "bezugdatum": de_datum((daten.get("bezug") or {}).get("datum")) if (daten.get("bezug") or {}).get("datum") else ""}
    datum = d.get("datum") or date.today().isoformat()
    ziel = int(fl(d.get("zahlungsziel") or k.get("zahlungsziel") or 14))
    rechnung = BELEGARTEN[art]["rechnung"]
    nummer, lfd = "", 0
    if not rechnung:
        lfd = naechste_lfd(con, aid, art)
        nummer = beleg_nummer(a["nummer"], art, lfd)
    schluss = text_einsetzen(texte.get("schluss"), werte)
    s = daten["summen"]
    werte_db = {
        "kompakt": 0 if e.get("platz_optimieren") is False else 1,   # „Platz optimieren“ ist Standard
        "auftrag_id": aid, "kunde_id": a["kunde_id"], "art": art, "lfd": lfd, "nummer": nummer,
        "status": "entwurf" if rechnung else "offen", "datum": datum,
        "leistungsdatum": d.get("leistungsdatum") or (a.get("lieferung") or "") if rechnung else "",
        "betreff": d.get("betreff") or a["bezeichnung"], "anschrift": kunde_block(k),
        "einleitung": text_einsetzen(texte.get("einleitung"), werte), "schluss": schluss,
        "daten": json.dumps(daten, ensure_ascii=False), "netto": s["netto"], "ust_satz": s["ust_satz"], "ust": s["ust"],
        "brutto": s["brutto"], "zahlbetrag": s["zahlbetrag"], "zahlungsziel": ziel,
        "faellig": plus_tage(datum, ziel) if rechnung else "", "angelegt": jetzt(), "geaendert": jetzt(),
        "artname": daten["artname"] if v else "", "bezug_id": (daten.get("bezug") or {}).get("id"),
    }
    if art == "gutschrift":
        werte_db["zahlungsziel"], werte_db["faellig"] = 0, ""
    if plan_uebernahme:
        werte_db["druck"] = json.dumps(plan_uebernahme, ensure_ascii=False)
    if berichtigen:   # ändert weder Umsatz noch offene Posten
        werte_db.update(netto=0, ust=0, brutto=0, zahlbetrag=0, zahlungsziel=0, faellig="",
                        druck=json.dumps({"konditionen": False, "qr": False}))
    cur = con.execute(f"INSERT INTO belege ({','.join(werte_db)}) VALUES ({','.join('?' * len(werte_db))})", list(werte_db.values()))
    if art == "lieferschein":
        geliefert_setzen(con, aid, werte_db.get("datum"))
    return cur.lastrowid


# Einstellungen, die Benutzer ohne volle Auftragsbearbeitung (Werkstatt, Mitarbeiter) erhalten: Listen und Schalter für
# Werkstatt-Reiter, Leitstand, Kalender, Lager, Stempeluhr – keine Firmendaten, Texte, Kalkulations- oder Zahlungsvorgaben
EINSTELLUNGEN_WERKSTATT = {
    "firma", "programm_version", "app_fenster", "etikett_breite", "etikett_hoehe", "https", "_https", "auftragsstatus", "auftragsgruppen", "positionsstatus", "positionsgruppen",
    "status_ende", "status_angebot", "status_automatik", "termin_typen", "einheiten", "lagerorte", "material_gruppen", "leitstand_schritte",
    "leitstand_status", "leitstand_status_map", "_leitstand_map", "taetigkeiten", "taetigkeit_listen", "taetigkeiten_katalog", "_taet_katalog_stand",
    "typ_kst", "ist_kategorien", "feiertage_wahl", "frei_wahl", "tage_eigene", "tagesstunden", "zeit_rundung", "zeit_gemeinkosten",
    "zuschnitt_url", "zuschnitt_zugabe", "laender", "land_immer", "_einheiten_neu", "_einheit_xun", "_status_nachgezogen", "sollplaene",
}
KUNDE_OHNE_KUNDENRECHT = ("id", "nummer", "kurzname", "gruppe", "aktiv", "anschrift", "plz", "ort", "land", "anrede", "telefon", "email1",
                          "lieferanschrift", "lieferort", "lieferland", "anredeform", "titel", "vorname", "nachname", "firma", "zusatz",
                          "strasse", "ansprechpartner", "mobil")
LIEFERANT_OHNE_RECHT = ("iban", "bic", "zahlkonto", "unsere_kundennr", "info_zahlung", "empfaenger", "vorsteuer", "zahlungsziel", "skonto",
                        "skontotage", "bemerkungen", "glaeubiger_id", "mandat", "steuernummer", "ustid", "datev_konto")


def sicht_einschraenken(teile, methode, erg, rechte):
    """Antworten für Benutzer mit eingeschränkten Rechten kürzen (Datensparsamkeit):
    Wer Kunden nur über den Auftrag erreicht (Werkstatt), bekommt vom Kunden Name, Anschrift und Erreichbarkeit, aber keine
    Konditionen, Bankdaten, Bemerkungen. Wer Lieferanten nur wegen des Materials sieht, bekommt keine Bank- und Zahlungsdaten;
    Lohn-Empfänger (Lieferantengruppe „Mitarbeiter“) sieht nur, wer Personal sehen darf."""
    if methode != "GET" or not teile:
        return erg
    b = rechte["bereiche"]
    if teile[0] == "kunden" and b.get("kunden", 0) < 1 and isinstance(erg, dict) and "kurzname" in erg:
        return {k: v for k, v in erg.items() if k in KUNDE_OHNE_KUNDENRECHT}
    if teile[0] == "lieferanten":
        def kuerzen(x):
            return {k: v for k, v in x.items() if k not in LIEFERANT_OHNE_RECHT} if isinstance(x, dict) and b.get("lieferanten", 0) < 1 else x
        if isinstance(erg, dict) and erg.get("gruppe") == "Mitarbeiter" and b.get("personal", 0) < 1:
            raise ApiFehler("Dafür fehlt die Berechtigung.", 403)
        return [kuerzen(x) for x in erg] if isinstance(erg, list) else kuerzen(erg)
    return erg


def etikett_mass(e):
    """Etikettengröße (Breite, Höhe) in mm aus den Einstellungen, auf 20–210 mm begrenzt; Vorgabe 70 × 74."""
    def m(k, std):
        try:
            v = round(float(str(e.get(k) or "").replace(",", ".")) * 10) / 10
        except ValueError:
            return std
        return v if 20 <= v <= 210 else std
    b, hh = m("etikett_breite", 70), m("etikett_hoehe", 74)
    return (int(b) if b == int(b) else b), (int(hh) if hh == int(hh) else hh)


def termin_konflikte(con, tid):
    """Hinweis, wenn ein zugeteilter Mitarbeiter an Tagen des Termins genehmigt abwesend ist oder schon einen anderen Termin hat.
    Der Termin wird trotzdem gespeichert – es ist nur ein Hinweis."""
    t = con.execute("SELECT * FROM termine WHERE id=?", (tid,)).fetchone()
    if not t:
        return ""
    try:
        zugeteilt = [int(x) for x in json.loads(t["mitarbeiter"] or "[]")]
    except (ValueError, TypeError):
        zugeteilt = []
    if not zugeteilt or t["erledigt"]:
        return ""
    namen = {m["id"]: f"{m['vorname']} {m['nachname']}".strip() for m in con.execute("SELECT id, vorname, nachname FROM mitarbeiter")}
    aus = []
    for mid in zugeteilt:
        for a in con.execute("SELECT von, bis FROM abwesenheiten WHERE mitarbeiter_id=? AND status='genehmigt' AND bis>=? AND von<=? ORDER BY von",
                             (mid, t["von"], t["bis"])):
            aus.append(f"{namen.get(mid, 'Mitarbeiter')} ist {'am ' + de_datum(a['von']) if a['von'] == a['bis'] else 'vom ' + de_datum(a['von']) + ' bis ' + de_datum(a['bis'])} abwesend")
        for o in con.execute("SELECT t.typ, t.von, t.bis, t.mitarbeiter, a.nummer FROM termine t LEFT JOIN auftraege a ON a.id=t.auftrag_id "
                             "WHERE t.id<>? AND t.erledigt=0 AND t.bis>=? AND t.von<=? AND t.mitarbeiter LIKE ?", (tid, t["von"], t["bis"], f"%{mid}%")):
            try:
                if mid not in json.loads(o["mitarbeiter"] or "[]"):
                    continue
            except ValueError:
                continue
            if t["zeit_von"] and t["zeit_bis"] and t["von"] == t["bis"]:
                continue   # stundengenaue Termine am selben Tag sind üblich (vormittags/nachmittags) – nicht melden
            aus.append(f"{namen.get(mid, 'Mitarbeiter')} hat {'am ' + de_datum(o['von']) if o['von'] == o['bis'] else 'vom ' + de_datum(o['von']) + ' bis ' + de_datum(o['bis'])} "
                       f"schon {o['typ'] or 'einen Termin'}{' (' + o['nummer'] + ')' if o['nummer'] else ''}")
    return "; ".join(dict.fromkeys(aus))[:400]


def termin_sichtbar(t, r=None):
    """Darf der angemeldete Benutzer diesen Termin im Kalender sehen? (Einstellung je Benutzer: Terminarten, nur eigene)"""
    r = r if r is not None else benutzer.aktuelle_rechte()
    if not r or r.get("inhaber"):
        return True
    k = r.get("kalender") or {}
    if k.get("typen") and (t["typ"] or "") not in k["typen"]:
        return False
    if k.get("nur_eigene"):
        mid = dict(benutzer.aktuell() or {}).get("mitarbeiter_id")
        try:
            zugeteilt = json.loads(t["mitarbeiter"] or "[]") if isinstance(t["mitarbeiter"], str) else (t["mitarbeiter"] or [])
        except ValueError:
            zugeteilt = []
        return bool(mid) and mid in zugeteilt
    return True


def kalender_sicht_anwenden(erg):
    """Kalenderdaten auf das kürzen, was der angemeldete Benutzer sehen darf. Der Inhaber sieht alles."""
    r = benutzer.aktuelle_rechte()
    if not r or r.get("inhaber"):
        return erg
    k = r.get("kalender") or {}
    if k.get("typen") or k.get("nur_eigene"):
        erg["termine"] = [t for t in erg["termine"] if termin_sichtbar(t, r)]
        sichtbar = {t["auftrag_id"] for t in erg["termine"]}
        erg["auftraege"] = [a for a in erg["auftraege"] if a["id"] in sichtbar]
    if not k.get("extern", True):
        erg["extern"], erg["fehler"] = [], ""
    if not k.get("abwesenheit", True):
        mid = dict(benutzer.aktuell() or {}).get("mitarbeiter_id")
        erg["abwesenheiten"] = [a for a in erg.get("abwesenheiten") or [] if mid and a["mitarbeiter_id"] == mid]
    if not r.get("preise", True):
        for a in erg["auftraege"]:
            a.pop("netto", None)
    return erg


def geliefert_setzen(con, aid, datum):
    """Lieferschein erstellt bzw. herausgegeben: Liefertag im Auftrag eintragen, falls noch leer."""
    if con.execute("UPDATE auftraege SET lieferung=? WHERE id=? AND IFNULL(lieferung,'')=''", (datum or date.today().isoformat(), aid)).rowcount:
        status_durch_datum(con, aid, "lieferung")


def status_durch_datum(con, aid, feld):
    """„Fertigung begonnen“ bzw. „Geliefert am“ wurde eingetragen: Auftragsstatus nach Einstellungen › Kunden & Aufträge
    nachziehen. Wie bei den Belegen nur vorwärts (Reihenfolge der Statusliste), nie zurück. Liefert den neuen Status oder ""."""
    e = einstellungen(con)
    ziel = status_automatik(e)["auftrag"].get("datum_" + feld) or ""
    liste = e.get("auftragsstatus") or []
    a = con.execute("SELECT status FROM auftraege WHERE id=?", (aid,)).fetchone()
    if not a or ziel not in liste or a["status"] == ziel:
        return ""
    if a["status"] in liste and liste.index(ziel) <= liste.index(a["status"]):
        return ""
    con.execute("UPDATE auftraege SET status=?, geaendert=? WHERE id=?", (ziel, jetzt(), aid))
    historie_eintrag(con, aid, "status", f"{a['status'] or '–'} → {ziel} (Datum „{'Fertigung begonnen' if feld == 'fertigung' else 'Geliefert am'}“ eingetragen)")
    return ziel


def beleg_aktualisieren(con, bid, neu_aus_auftrag=False):
    b = beleg_laden(con, bid)
    if b["status"] in ("fest", "storniert"):
        raise ApiFehler("Festgeschriebene Belege können nicht mehr geändert werden.")
    if b["daten"].get("unterschrift"):
        raise ApiFehler("Der Beleg ist vom Kunden unterschrieben und kann nicht mehr geändert werden. Für Änderungen bitte einen neuen Beleg erstellen.")
    opts = {**(b["daten"].get("abschlag") or {}), "druck": b["druck"], "beleg_id": bid,
            "variante": b["daten"].get("variante"), "frei": b["daten"].get("frei"), "bezug": b["daten"].get("bezug"),
            "modus": b["daten"].get("modus"), "neu_aus_auftrag": neu_aus_auftrag, "eigen": b["daten"]}
    daten, k, a = beleg_snapshot(con, b["auftrag_id"], b["art"], opts)
    if b["daten"].get("abnahme"):
        daten["abnahme"] = b["daten"]["abnahme"]
    s = dict(daten["summen"])
    if daten.get("modus") == "berichtigen":
        s.update(netto=0, ust=0, brutto=0, zahlbetrag=0)
    con.execute("UPDATE belege SET daten=?, netto=?, ust_satz=?, ust=?, brutto=?, zahlbetrag=?, geaendert=? WHERE id=?",
                (json.dumps(daten, ensure_ascii=False), s["netto"], s["ust_satz"], s["ust"], s["brutto"], s["zahlbetrag"], jetzt(), bid))


UNTERSCHREIBBAR = ("ab", "lieferschein", "abnahme")


def beleg_unterschreiben(con, bid, d, wer):
    """Kundenunterschrift auf dem Tablet für Auftragsbestätigung, Lieferschein oder Abnahmeprotokoll."""
    b = beleg_laden(con, bid)
    if b["art"] not in UNTERSCHREIBBAR:
        raise ApiFehler("Nur Auftragsbestätigung, Lieferschein und Abnahmeprotokoll werden digital unterschrieben.")
    if b["daten"].get("unterschrift"):
        raise ApiFehler("Der Beleg ist bereits unterschrieben.")
    bild = str(d.get("bild") or "")
    if not bild.startswith("data:image/png;base64,") or len(bild) > 3_000_000:
        raise ApiFehler("Die Unterschrift fehlt.")
    name = str(d.get("name") or "").strip()
    if not name:
        raise ApiFehler("Bitte den Namen der unterschreibenden Person eintragen.")
    daten = b["daten"]
    if b["art"] == "abnahme":
        daten["abnahme"] = {"vorbehalt": bool(d.get("vorbehalt")), "maengel": str(d.get("maengel") or "").strip(),
                            "restarbeiten": str(d.get("restarbeiten") or "").strip()}
    geo = d.get("geo") if isinstance(d.get("geo"), dict) else None
    bild_an = str(d.get("bild_an") or "")
    if bild_an and (not bild_an.startswith("data:image/png;base64,") or len(bild_an) > 3_000_000):
        bild_an = ""
    daten["unterschrift"] = {"bild": bild, "name": name, "ort": str(d.get("ort") or "").strip(), "zeit": jetzt(), "von": wer,
                             "geo": {k: geo.get(k) for k in ("lat", "lon", "genau") if k in geo} if geo else None,
                             "bild_an": bild_an, "name_an": str(d.get("name_an") or "").strip() if bild_an else ""}
    con.execute("UPDATE belege SET daten=?, geaendert=? WHERE id=?", (json.dumps(daten, ensure_ascii=False), jetzt(), bid))
    ort = daten["unterschrift"]["ort"]
    con.execute("INSERT INTO notizen (kunde_id, auftrag_id, text, angelegt) VALUES (?,?,?,?)",
                (b["kunde_id"], b["auftrag_id"], f"{b['artname']} {b['nummer']} digital unterschrieben von {name}{' in ' + ort if ort else ''}"
                 + (f" (Abnahme {'mit' if daten['abnahme']['vorbehalt'] else 'ohne'} Vorbehalt)" if b["art"] == "abnahme" else ""), jetzt()))
    if b["art"] == "lieferschein":
        geliefert_setzen(con, b["auftrag_id"], (daten["unterschrift"]["zeit"] or "")[:10])
    erg = {"beleg": beleg_laden(con, bid)}
    try:
        erg["pdf"] = beleg_pdf(con, bid)
    except Exception as f:  # noqa: BLE001
        erg["pdf_fehler"] = str(f)
    return erg


def unterschrift_html(b, teil="alles"):
    """Abnahmeangaben (teil="abnahme") und/oder digitale Kundenunterschrift (teil="signatur") im Beleg."""
    d = b["daten"]
    teile = []
    ab = d.get("abnahme")
    if b["art"] == "abnahme" and teil in ("alles", "abnahme"):
        ab = ab or {}
        teile.append('<div class="abn"><div class="abn-z"><b>Abnahme:</b> '
                     + ("☐ ohne Vorbehalt &nbsp; ☒ mit Vorbehalt wegen der unten aufgeführten Mängel" if ab.get("vorbehalt")
                        else ("☒ ohne Vorbehalt &nbsp; ☐ mit Vorbehalt" if d.get("unterschrift") else "☐ ohne Vorbehalt &nbsp; ☐ mit Vorbehalt"))
                     + "</div>"
                     + f'<div class="abn-z"><b>Mängel:</b> {h(ab.get("maengel")) if ab.get("maengel") else ("keine" if d.get("unterschrift") else "")}</div>'
                     + f'<div class="abn-z"><b>Restarbeiten:</b> {h(ab.get("restarbeiten")) if ab.get("restarbeiten") else ("keine" if d.get("unterschrift") else "")}</div></div>')
    u = d.get("unterschrift") if teil in ("alles", "signatur") else None
    if u:
        zeit = u.get("zeit") or ""
        wann = (f'{h(u.get("ort") + ", " if u.get("ort") else "")}{de_datum(zeit[:10])}, {zeit[11:16]} Uhr · digital unterschrieben'
                f'{" · Standort " + str(round(u["geo"]["lat"], 5)) + ", " + str(round(u["geo"]["lon"], 5)) if u.get("geo") and u["geo"].get("lat") is not None else ""}')
        rolle_k = {"lieferschein": "Empfänger", "ab": "Auftraggeber", "abnahme": "Auftraggeber"}.get(b["art"], "Auftraggeber")
        bild_an = u.get("bild_an") or ""
        links = (f'<div class="usig"><div class="usig-b"><img src="{bild_an}" alt="Unterschrift"></div>'
                 f'<div class="usig-l">{h(u.get("name_an") or "")}</div><div class="usig-k">Auftragnehmer</div></div>') if bild_an else ""
        rechts = (f'<div class="usig"><div class="usig-b"><img src="{u.get("bild")}" alt="Unterschrift"></div><div class="usig-l">{h(u.get("name"))}</div>'
                  f'<div class="usig-k">{rolle_k} · {wann}</div></div>')
        teile.append(f'<div class="usigs">{links}{rechts}</div>')
    if not teile:
        return ""
    return ('<style>.abn{margin-top:5mm;border:.4pt solid #999;padding:2mm 3mm}.abn-z{margin:1mm 0;white-space:pre-wrap}'
            '.usigs{display:flex;gap:10mm;margin-top:6mm;page-break-inside:avoid}.usig{width:78mm}.usig-b{height:23mm;display:flex;align-items:flex-end}'
            '.usig img{max-height:22mm;max-width:78mm;display:block}'
            '.usig-l{border-top:.5pt solid #000;padding-top:1mm;font-weight:600}.usig-k{font-size:7.5pt;color:#444}</style>' + "".join(teile))


def schluss_ohne_linie(b, text):
    """Ist ein Beleg digital unterschrieben, entfällt die Linie zum Unterschreiben von Hand („____ Datum, Unterschrift“)."""
    if not (b.get("daten") or {}).get("unterschrift") or not text:
        return text
    t = re.sub(r"(?:\n|<br\s*/?>|<div>|</div>|<p>|</p>|\s)*_{6,}(?:\s|<br\s*/?>|</?div>|</?p>)*Datum,?\s*Unterschrift[^<\n]*", "", text)
    return re.sub(r"(?:\s|<br\s*/?>)+$", "", t)


def op_zahlung_buchen(con, op_id, d):
    """Zahlungseingang zu einem offenen Posten buchen (von Hand oder aus dem Kontoauszug). Gibt die neuen IDs zurück."""
    op = con.execute("SELECT * FROM offene_posten WHERE id=?", (op_id,)).fetchone()
    if not op:
        raise ApiFehler("Offener Posten nicht gefunden", 404)
    betrag = round(zahl(d.get("betrag"), float), 2)
    if not betrag:
        raise ApiFehler("Bitte einen Betrag eingeben.")
    skonto = round(zahl(d.get("skonto"), float), 2)
    datum_ = d.get("datum") or date.today().isoformat()
    date.fromisoformat(datum_)
    # Was über den offenen Rechnungsbetrag hinausgeht, deckt zuerst die Mahnkosten
    auf_mk = 0.0
    if (op["mahnkosten"] or 0) > 0 and op["offen"] >= 0 and betrag + skonto > op["offen"] + 0.004:
        auf_mk = round(min(betrag + skonto - op["offen"], op["mahnkosten"]), 2)
    ids = [con.execute("INSERT INTO zahlungseingaenge (op_id, datum, betrag, art, bemerkung, angelegt, auf_mahnkosten) VALUES (?,?,?,?,?,?,?)",
                       (op_id, datum_, betrag, d.get("art") or "Überweisung",
                        d.get("bemerkung") or ("davon Mahnkosten " + de(auf_mk) + " €" if auf_mk else ""), jetzt(), auf_mk)).lastrowid]
    if skonto:
        ids.append(con.execute("INSERT INTO zahlungseingaenge (op_id, datum, betrag, art, bemerkung, angelegt) VALUES (?,?,?,?,?,?)",
                               (op_id, datum_, skonto, "Skonto", "Skontoabzug", jetzt())).lastrowid)
    con.execute("UPDATE offene_posten SET offen=ROUND(offen-?-?+?,2), mahnkosten=ROUND(IFNULL(mahnkosten,0)-?,2) WHERE id=?",
                (betrag, skonto, auf_mk, auf_mk, op_id))
    return ids


def zahlungseingang_loeschen(con, zid, aus_bank=False):
    z = con.execute("SELECT * FROM zahlungseingaenge WHERE id=?", (zid,)).fetchone()
    if not z:
        return
    mk = z["auf_mahnkosten"] or 0
    con.execute("UPDATE offene_posten SET offen=ROUND(offen+?-?,2), mahnkosten=ROUND(IFNULL(mahnkosten,0)+?,2) WHERE id=?",
                (z["betrag"], mk, mk, z["op_id"]))
    con.execute("DELETE FROM zahlungseingaenge WHERE id=?", (zid,))
    op = con.execute("SELECT nummer FROM offene_posten WHERE id=?", (z["op_id"],)).fetchone()
    prot(con, "zahlungseingang_geloescht", op["nummer"] if op else z["op_id"],
         f"Zahlungseingang {de(z['betrag'])} € vom {de_datum(z['datum'])} zu {op['nummer'] if op else 'OP ' + str(z['op_id'])} gelöscht"
         + (" (Zuordnung zum Kontoauszug gelöst)" if aus_bank else ""), dict(z))
    if not aus_bank:
        bank.eingang_entfernt(con, zid)


# ---------------------------------------------------------------- Kontoauszüge (bank.py)
def prot(con, art, objekt, text, daten=None):
    """Eintrag ins unveränderbare Protokoll (GoBD) mit angemeldetem Benutzer und Programmversion."""
    wer = dict(benutzer.aktuell() or {}).get("login") or "Programm"
    return protokoll.eintragen(con, art, objekt, text, daten, benutzer=wer, version=VERSION)


def beleg_kurz(b):
    return {"id": b["id"], "art": b["art"], "nummer": b["nummer"], "status": b["status"], "datum": b["datum"],
            "auftrag_id": b["auftrag_id"], "kunde": (b["daten"].get("kunde") or {}).get("kurzname", ""),
            "netto": b["netto"], "ust": b["ust"], "brutto": b["brutto"], "zahlbetrag": b["zahlbetrag"]}


def beleg_fingerabdruck(b):
    """SHA-256 über den steuerlich maßgeblichen Inhalt einer Rechnung (Nummer, Datum, Zeilen, Summen). Wird beim
    Festschreiben ins Protokoll geschrieben; die Belegprüfung erkennt daran jede spätere Änderung in der Datenbank."""
    d = b["daten"]
    kern = {"nummer": b["nummer"], "art": b["art"], "datum": b["datum"],
            "zeilen": [[str(z.get("posnr") or ""), str(z.get("text") or ""), round(fl(z.get("menge")), 4), str(z.get("einheit") or ""), round(fl(z.get("gp")), 2)]
                       for z in d.get("zeilen") or [] if z.get("typ") == "pos"],
            "frei": [[str(x.get("text") or ""), round(fl(x.get("betrag")), 2)] for x in d.get("frei") or []],
            "netto": round(fl(b["netto"]), 2), "ust": round(fl(b["ust"]), 2), "brutto": round(fl(b["brutto"]), 2), "zahlbetrag": round(fl(b["zahlbetrag"]), 2)}
    return hashlib.sha256(json.dumps(kern, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def datei_sha256(pfad):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


BELEG_PRUEFUNG = {"text": "", "zeit": "", "ergebnis": None}


def belege_pruefen(con):
    """GoBD-Belegprüfung: jede festgeschriebene Rechnung mit ihrem Protokolleintrag vergleichen (Nummer, Datum, Beträge,
    Inhalts-Fingerabdruck) und das Archiv-PDF mit dem dort festgehaltenen Hash. Meldet Abweichungen, ändert nichts."""
    fest, pdf, storno = {}, {}, {}
    for r in con.execute("SELECT art, daten FROM protokoll WHERE art IN ('festschreiben','archiv_pdf','storno') ORDER BY nr"):
        d = jl(r["daten"], {})
        if r["art"] == "festschreiben" and d.get("id"):
            fest[d["id"]] = d
        elif r["art"] == "archiv_pdf" and d.get("id"):
            pdf[d["id"]] = d
        elif r["art"] == "storno" and (d.get("storno") or {}).get("id"):
            storno[d["storno"]["id"]] = d["storno"]
    fehler, geprueft, mit_abdruck, pdf_ok, ohne = [], 0, 0, 0, 0
    eb = protokoll.echtbetrieb(con)
    if eb:   # im Echtbetrieb festgeschriebene Rechnungen dürfen nie verschwinden (z. B. nach einer Rücksicherung nachzutragen)
        da = {r[0] for r in con.execute("SELECT id FROM belege")}
        for r in con.execute("SELECT zeit, daten FROM protokoll WHERE art='festschreiben' AND zeit>=? ORDER BY nr", (eb["seit"],)):
            d = jl(r["daten"], {})
            if d.get("id") and d["id"] not in da:
                fehler.append(f"Rechnung {d.get('nummer')} vom {de_datum(d.get('datum'))} ({d.get('kunde')}, brutto {de(fl(d.get('brutto')))} €) "
                              "ist laut Protokoll festgeschrieben, fehlt aber in der Datenbank")
    rechnungsarten = [k for k, v in BELEGARTEN.items() if v.get("rechnung")]
    sql = (f"SELECT id, art, nummer, datum, netto, ust, brutto, zahlbetrag FROM belege WHERE status IN ('fest','storniert') "
           f"AND art IN ({','.join('?' * len(rechnungsarten))}) ORDER BY id")
    for row in con.execute(sql, rechnungsarten).fetchall():
        b = dict(row)
        b["artname"] = BELEGARTEN[b["art"]]["name"]
        p = fest.get(b["id"]) or storno.get(b["id"])
        a = pdf.get(b["id"])
        if (p and p.get("inhalt")) or a:   # den Beleginhalt nur laden, wenn er wirklich verglichen wird
            b["daten"] = jl(con.execute("SELECT daten FROM belege WHERE id=?", (b["id"],)).fetchone()[0], {})
        if not p:
            ohne += 1   # aus der Zeit vor dem Protokoll bzw. aus einer Datenübernahme
        else:
            geprueft += 1
            for k, name in (("nummer", "Nummer"), ("datum", "Datum")):
                if str(p.get(k) or "") != str(b[k] or ""):
                    fehler.append(f"{b['artname']} {p.get('nummer')}: {name} geändert (Protokoll {p.get(k)}, Datenbank {b[k]})")
            for k, name in (("netto", "Netto"), ("ust", "USt"), ("brutto", "Brutto")):
                if abs(fl(p.get(k)) - fl(b[k])) > 0.005:
                    fehler.append(f"{b['artname']} {b['nummer']}: {name} geändert (Protokoll {de(fl(p.get(k)))} €, Datenbank {de(fl(b[k]))} €)")
            if p.get("inhalt"):
                mit_abdruck += 1
                if p["inhalt"] != beleg_fingerabdruck(b):
                    fehler.append(f"{b['artname']} {b['nummer']}: Inhalt (Positionen oder Beträge) weicht vom festgeschriebenen Stand ab")
        if a and (b["daten"].get("kunde") or {}).get("kurzname") != "anonymisiert":
            pfad = os.path.join(DATEN, "belege", a.get("datei") or "")
            if not os.path.isfile(pfad):
                fehler.append(f"{b['artname']} {b['nummer']}: Archiv-PDF fehlt ({a.get('datei')})")
            elif datei_sha256(pfad) != a.get("sha256"):
                fehler.append(f"{b['artname']} {b['nummer']}: Archiv-PDF wurde nach der Erzeugung verändert ({a.get('datei')})")
            else:
                pdf_ok += 1
    for jahr in sorted({r[0] for r in con.execute("SELECT substr(datum,1,4) FROM belege WHERE status IN ('fest','storniert') AND lfd>0")}):
        lfd = sorted(r[0] for r in con.execute("SELECT lfd FROM belege WHERE status IN ('fest','storniert') AND lfd>0 AND substr(datum,1,4)=?", (jahr,)))
        doppelt = sorted({x for x in lfd if lfd.count(x) > 1})
        if doppelt:
            fehler.append(f"{jahr}: Rechnungsnummer doppelt vergeben (laufende Nr. {', '.join(map(str, doppelt[:5]))})")
    erg = {"ok": not fehler, "fehler": fehler[:30], "geprueft": geprueft, "mit_fingerabdruck": mit_abdruck, "pdf_geprueft": pdf_ok,
           "ohne_protokoll": ohne, "zeit": jetzt()}
    BELEG_PRUEFUNG.update(ergebnis=erg, zeit=erg["zeit"], text="" if erg["ok"] else
                          "Die Belegprüfung hat Abweichungen bei festgeschriebenen Rechnungen gefunden. Details unter Einstellungen › Service › Protokoll.")
    return erg


def beleg_festschreiben(con, bid):
    b = beleg_laden(con, bid)
    if not b["ist_rechnung"]:
        raise ApiFehler("Nur Rechnungen werden festgeschrieben.")
    if b["status"] != "entwurf":
        raise ApiFehler("Dieser Beleg ist bereits festgeschrieben.")
    beleg_aktualisieren(con, bid) if b["art"] != "storno" else None
    b = beleg_laden(con, bid)
    berichtigung = b["daten"].get("modus") == "berichtigen"
    if b["art"] != "storno" and abs(b["brutto"]) < 0.005 and not berichtigung:
        raise ApiFehler("Der Rechnungsbetrag ist 0 €.")
    datum = b["datum"] or date.today().isoformat()
    # Rechnungsnummer: Jahr-laufende Nummer (4-stellig), gemeinsamer Nummernkreis für Rechnung, Abschlag und Storno
    info = rechnungsnummer_info(con, int(datum[:4]))
    lfd, nummer = info["naechste_lfd"], info["naechste"]
    zaehler_setzen(con, "rechnung", lfd, int(datum[:4]))
    faellig = plus_tage(datum, b["zahlungsziel"])
    # Druckbild einfrieren: „unten bündig“ gilt für diese Rechnung so, wie es beim Festschreiben eingestellt war
    roh = jl(con.execute("SELECT druck FROM belege WHERE id=?", (bid,)).fetchone()["druck"], {}) or {}
    roh["unten_buendig"] = bool(b["druck"].get("unten_buendig"))
    con.execute("UPDATE belege SET druck=? WHERE id=?", (json.dumps(roh, ensure_ascii=False), bid))
    con.execute("UPDATE belege SET nummer=?, lfd=?, status='fest', datum=?, faellig=?, geaendert=? WHERE id=?",
                (nummer, lfd, datum, faellig, jetzt(), bid))
    betrag = b["zahlbetrag"]
    if b["art"] != "storno" and not berichtigung:
        con.execute("INSERT INTO offene_posten (nummer, art, kunde_id, auftrag_id, datum, betrag, faellig, offen, mahnstufe, beleg_id) "
                    "VALUES (?,?,?,?,?,?,?,?,0,?)", (nummer, b["artname"], b["kunde_id"], b["auftrag_id"], datum, betrag, faellig, betrag, bid))
    fb = beleg_laden(con, bid)
    prot(con, "festschreiben", fb["nummer"], f"{fb['artname']} {fb['nummer']} vom {de_datum(fb['datum'])} · {fb['daten'].get('kunde', {}).get('kurzname', '')} · brutto {de(fb['brutto'])} €",
         {**beleg_kurz(fb), "inhalt": beleg_fingerabdruck(fb)})
    try:
        wiedervorlage.nach_rechnung(con, fb, einstellungen(con), ich_login())
    except (sqlite3.Error, ValueError):
        traceback.print_exc()   # eine Wiedervorlage darf das Festschreiben nie verhindern
    return fb


def beleg_stornieren(con, bid):
    b = beleg_laden(con, bid)
    if b["status"] != "fest" or b["art"] not in ("rechnung", "abschlag", "gutschrift", "korrektur"):
        raise ApiFehler("Nur festgeschriebene Rechnungen können storniert werden.")
    if b["daten"].get("modus") == "berichtigen":
        raise ApiFehler("Eine Berichtigung ohne Betragsänderung kann nicht storniert werden. Bei erneutem Fehler eine weitere Berichtigung zur ursprünglichen Rechnung erstellen.")
    if b["art"] == "abschlag" and b["nummer"] in abschlaege_verrechnet(con, b["auftrag_id"]):
        raise ApiFehler("Diese Abschlagsrechnung ist bereits in einer Schlussrechnung verrechnet. Bitte zuerst die Schlussrechnung stornieren.")
    e = einstellungen(con)
    daten = json.loads(json.dumps(b["daten"]))
    daten["art"], daten["artname"] = "storno", BELEGARTEN["storno"]["name"]
    for z in daten.get("zeilen", []):
        for k in ("ep", "gp", "summe"):
            if k in z and isinstance(z[k], (int, float)):
                z[k] = -z[k]
        for u in z.get("unter", []):
            u["ep"], u["gp"] = -u["ep"], -u["gp"]
    s = daten["summen"]
    for k in ("netto_positionen", "rabatt", "netto", "ust", "brutto", "abzug_brutto", "zahlbetrag"):
        s[k] = -s.get(k, 0)
    for x in daten.get("abzuege", []):
        for k in ("netto", "ust", "brutto"):
            x[k] = -x[k]
    daten["bezug"] = {"nummer": b["nummer"], "datum": b["datum"]}
    texte = (e.get("beleg_texte") or {}).get("storno") or BELEG_TEXTE["storno"]
    werte = {"anrede": daten["kunde"]["anrede"], "bezug": b["nummer"], "bezugdatum": de_datum(b["datum"]),
             "auftrag": daten["auftrag"]["bezeichnung"]}
    heute_iso = date.today().isoformat()
    w = {"auftrag_id": b["auftrag_id"], "kunde_id": b["kunde_id"], "art": "storno", "lfd": 0, "nummer": "", "status": "entwurf",
         "datum": heute_iso, "leistungsdatum": b["leistungsdatum"], "betreff": f"Storno {b['artname']} {b['nummer']}",
         "anschrift": b["anschrift"], "einleitung": text_einsetzen(texte["einleitung"], werte),
         "schluss": text_einsetzen(texte["schluss"], werte), "daten": json.dumps(daten, ensure_ascii=False),
         "netto": s["netto"], "ust_satz": s["ust_satz"], "ust": s["ust"], "brutto": s["brutto"], "zahlbetrag": s["zahlbetrag"],
         "zahlungsziel": 0, "faellig": heute_iso, "bezug_id": bid, "angelegt": jetzt(), "geaendert": jetzt()}
    cur = con.execute(f"INSERT INTO belege ({','.join(w)}) VALUES ({','.join('?' * len(w))})", list(w.values()))
    sid = cur.lastrowid
    st = beleg_festschreiben(con, sid)
    con.execute("UPDATE belege SET status='storniert', geaendert=? WHERE id=?", (jetzt(), bid))
    wiedervorlage.nach_storno(con, bid)
    # Offenen Posten der Originalrechnung ausbuchen; bereits Gezahltes wird als Guthaben offen geführt
    op = con.execute("SELECT * FROM offene_posten WHERE beleg_id=?", (bid,)).fetchone()
    gezahlt = (op["betrag"] - op["offen"]) if op else 0
    if op:
        con.execute("UPDATE offene_posten SET offen=0 WHERE id=?", (op["id"],))
    con.execute("INSERT INTO offene_posten (nummer, art, kunde_id, auftrag_id, datum, betrag, faellig, offen, mahnstufe, beleg_id) "
                "VALUES (?,?,?,?,?,?,?,?,0,?)", (st["nummer"], st["artname"], st["kunde_id"], st["auftrag_id"], st["datum"],
                                               -round(gezahlt, 2), st["datum"], -round(gezahlt, 2), sid))
    prot(con, "storno", b["nummer"], f"{b['artname']} {b['nummer']} storniert durch Stornorechnung {st['nummer']}",
         {"original": beleg_kurz(b), "storno": {**beleg_kurz(st), "inhalt": beleg_fingerabdruck(st)}})
    return st


# ---------- PDF über Edge/Chrome (headless) ----------
def browser_finden():
    kandidaten = [os.environ.get("BUERO_BROWSER", "")]
    for var, rest in (("PROGRAMFILES(X86)", r"Microsoft\Edge\Application\msedge.exe"),
                      ("PROGRAMFILES", r"Microsoft\Edge\Application\msedge.exe"),
                      ("PROGRAMFILES", r"Google\Chrome\Application\chrome.exe"),
                      ("PROGRAMFILES(X86)", r"Google\Chrome\Application\chrome.exe"),
                      ("LOCALAPPDATA", r"Google\Chrome\Application\chrome.exe")):
        if os.environ.get(var):
            kandidaten.append(os.path.join(os.environ[var], rest))
    for name in ("msedge", "chrome", "chromium", "chromium-browser", "google-chrome"):
        w = shutil.which(name)
        if w:
            kandidaten.append(w)
    for k in kandidaten:
        if k and os.path.isfile(k):
            return k
    return None


HTTPS = {"aktiv": False, "modus": "aus", "port": 0, "stempel_port": 0, "meldung": ""}


class HttpsServer(ThreadingHTTPServer):
    """Zweiter Zugang über https (eigenes Zertifikat, siehe zert.py). Der TLS-Handshake läuft im Thread der jeweiligen
    Verbindung, damit ein hängendes Gerät nicht alle anderen aufhält."""
    allow_reuse_address = os.name != "nt"
    daemon_threads = True
    kontext = None

    def server_bind(self):
        import socket
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def get_request(self):
        sock, adresse = self.socket.accept()
        sock.settimeout(30)
        return self.kontext.wrap_socket(sock, server_side=True, do_handshake_on_connect=False), adresse

    def handle_error(self, request, client_address):
        pass   # abgebrochene Handshakes (z. B. Gerät ohne eingerichtetes Zertifikat) nicht ins Protokoll schreiben


HTTPS_SERVER = []


def zertifikat_am_pc(erneut=False):
    """Büro-CA im Windows-Zertifikatsspeicher des angemeldeten Benutzers eintragen. Ohne ausdrücklichen Wunsch (erneut) wird je CA
    nur einmal gefragt, damit ein „Nein“ nicht bei jedem Programmstart wieder zur Nachfrage führt."""
    import zert
    fp = zert.fingerabdruck(DATEN)
    merk = os.path.join(DATEN, "zertifikat", "windows.gefragt")
    stand = zert.windows_vertrauen(DATEN, eintragen=False)
    if stand == "fehlt":
        try:
            with open(merk, encoding="utf-8") as f:
                gefragt = f.read().strip() == fp
        except OSError:
            gefragt = False
        if erneut or not gefragt:
            with open(merk, "w", encoding="utf-8") as f:
                f.write(fp)
            stand = zert.windows_vertrauen(DATEN)
    HTTPS["am_pc"] = stand
    return stand


def zertifikat_neu():
    """Büro-CA und Server-Zertifikat neu ausstellen und sofort verwenden (ohne Neustart)."""
    import socket
    import zert
    adressen = {lokale_ip()}
    try:
        adressen |= {a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    except OSError:
        pass
    zert.ca_verwerfen(DATEN)
    cert, key, _ = zert.bereitstellen(DATEN, sorted(adressen), str(einstellungen_roh("firma", "") or ""))
    k = zert.kontext(cert, key)
    for srv in HTTPS_SERVER:
        srv.kontext = k
    HTTPS.update(meldung="Büro-CA und Zertifikat wurden neu angelegt.", eigen=False)
    return zertifikat_am_pc(erneut=True)


def https_starten():
    """https-Zugang starten, wenn Netzwerk und https eingeschaltet sind. Fehler lassen das Programm normal über http weiterlaufen."""
    modus = str(einstellungen_roh("https", "aus") or "aus")
    if modus not in ("zusaetzlich", "nur") or not NETZ["aktiv"]:
        return
    try:
        import socket
        import zert
        adressen = {lokale_ip()}
        try:
            adressen |= {a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
        except OSError:
            pass
        cert, key, meldung = zert.bereitstellen(DATEN, sorted(adressen), str(einstellungen_roh("firma", "") or ""))
        eigen = zert.eigenes(DATEN)   # eigenes Zertifikat des Betriebs hat Vorrang (daten/zertifikat/eigen.pem + eigen.key)
        if eigen:
            cert, key, meldung = eigen[0], eigen[1], "eigenes Zertifikat"
        port = int(os.environ.get("BUERO_HTTPS_PORT") or PORT + 1)
        srv = HttpsServer(("0.0.0.0", port), Handler)
        srv.kontext = zert.kontext(cert, key)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        HTTPS.update(aktiv=True, modus=modus, port=port, meldung=meldung, eigen=bool(eigen))
        HTTPS_SERVER.append(srv)
        if not eigen:   # an diesem PC selbst als vertrauenswürdig eintragen (Windows fragt einmal nach); je CA nur ein Versuch
            threading.Thread(target=zertifikat_am_pc, daemon=True).start()
        # Die Stempeluhr bekommt eine eigene Adresse (ein Port weiter). Für den Browser ist das eine eigene Seite – nur so
        # lässt sie sich auf einem Gerät zusätzlich zur Büro-App als zweite App installieren.
        try:
            srv2 = HttpsServer(("0.0.0.0", port + 1), Handler)
            srv2.kontext = srv.kontext
            HTTPS_SERVER.append(srv2)
            threading.Thread(target=srv2.serve_forever, daemon=True).start()
            HTTPS["stempel_port"] = port + 1
        except OSError as f:
            print(f"Eigene Adresse der Stempeluhr (Port {port + 1}) nicht verfügbar: {f}")
        print(f"https eingeschaltet: https://{lokale_ip()}:{port}  ({meldung or 'Zertifikat gültig'})")
    except Exception as f:  # noqa: BLE001
        HTTPS.update(aktiv=False, meldung=f"https konnte nicht gestartet werden: {f}")
        print(HTTPS["meldung"])


ZERT_SEITE = """<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jahresring – Zertifikat einrichten</title>
<style>body{font:16px/1.5 system-ui,Segoe UI,sans-serif;max-width:720px;margin:0 auto;padding:20px;color:#2b2622;background:#f6f3ee}
h1{font-size:1.4em}h2{font-size:1.1em;margin-top:1.6em}a.btn{display:inline-block;background:#5b4636;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none;margin:4px 8px 4px 0}
code{background:#eae4da;padding:2px 5px;border-radius:4px;word-break:break-all}li{margin:.35em 0}.h{color:#6b625a;font-size:.92em}</style>
<h1>Jahresring sicher verbinden (https)</h1>
<p>Damit dieses Gerät die verschlüsselte Adresse <b>__ADRESSE__</b> ohne Warnung öffnet und Jahresring als App installiert werden kann,
wird einmalig das Zertifikat des Büro-PCs als vertrauenswürdig eingerichtet. Es gilt nur für Jahresring im eigenen Netz (localhost, PC-Name, private Netzadressen).</p>
<p><a class="btn" href="/zertifikat/jahresring-ca.crt">Zertifikat herunterladen</a></p>
<p>Die <b>Stempeluhr</b> hat die eigene Adresse <b>__STEMPEL__</b>. Dort geöffnet, lässt sie sich als eigene App installieren – auch zusätzlich zur Büro-App auf demselben Gerät.</p>
<p class="h">Fingerabdruck (SHA-256) zum Vergleich mit der Anzeige unter Einstellungen › Benutzer &amp; Netzwerk am Büro-PC:<br><code>__FP__</code></p>
<h2>Android (Tablet, Handy)</h2><ol><li>Zertifikat herunterladen.</li><li>Einstellungen › Sicherheit (bzw. „Sicherheit &amp; Datenschutz“ › „Weitere Sicherheitseinstellungen“) ›
„Verschlüsselung &amp; Anmeldedaten“ › „Zertifikat installieren“ (bzw. „Von Gerätespeicher installieren“) › <b>CA-Zertifikat</b>.</li>
<li>Den Warnhinweis mit „Trotzdem installieren“ bestätigen und die Datei <code>jahresring-ca.crt</code> im Ordner Downloads wählen. Das Gerät braucht dafür eine Bildschirmsperre.</li>
<li>Chrome ganz schließen, neu öffnen und <b>__ADRESSE__</b> aufrufen. Im Menü ⋮ steht dann „App installieren“.</li></ol>
<h2>iPhone / iPad</h2><ol><li>Diese Seite in Safari öffnen, Zertifikat herunterladen und „Zulassen“ wählen.</li><li>Einstellungen › „Profil geladen“ › Installieren.</li>
<li>Einstellungen › Allgemein › Info › Zertifikatsvertrauenseinstellungen: „Jahresring Büro-CA …“ einschalten.</li><li><b>__ADRESSE__</b> in Safari öffnen, dann Teilen › „Zum Home-Bildschirm“.</li></ol>
<h2>Windows-PC</h2><p class="h">Am Büro-PC selbst richtet das Programm das Zertifikat ein (Nachfrage von Windows mit „Ja“ bestätigen). Für weitere PCs:</p><ol><li>Zertifikat herunterladen und doppelklicken › „Zertifikat installieren“ › „Lokaler Computer“ (oder „Aktueller Benutzer“).</li>
<li>„Alle Zertifikate in folgendem Speicher speichern“ › <b>Vertrauenswürdige Stammzertifizierungsstellen</b> › Fertig stellen.</li><li>Browser neu starten und <b>__ADRESSE__</b> öffnen.</li></ol>
<p class="h">Wird der Büro-PC neu aufgesetzt, entsteht ein neues Zertifikat; es ist dann auf den Geräten erneut einzurichten und das alte kann entfernt werden.</p></html>"""


class BueroServer(ThreadingHTTPServer):
    """Unter Windows darf SO_REUSEADDR denselben Port mehrfach belegen – dann laufen mehrere Programme
    nebeneinander und die Anfragen landen mal hier, mal dort. Daher exklusiv binden."""
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        import socket
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def service_cfg(con):
    e = einstellungen(con)
    return {"version": VERSION, "basis": BASIS, "daten": DATEN, "db": DB_PFAD, "backup": BACKUP_PFAD, "anhaenge": ANHANG_PFAD,
            "bilder": BILDER, "netz": NETZ["aktiv"], "ip": lokale_ip(), "port": PORT, "projektpfad": e.get("projektpfad") or "",
            "ziel": (e.get("sicherung_ziel") or "").strip()}


# ---------- Service: Testdaten löschen (vor dem Echtbetrieb) ----------
def _anzahl(con, sql, *a):
    try:
        return con.execute(sql, a).fetchone()[0] or 0
    except sqlite3.Error:
        return 0


def testdaten_vorschau(con):
    fest = _anzahl(con, "SELECT COUNT(*) FROM belege WHERE status IN ('fest', 'storniert')")
    z = {
        "auftraege": f"{_anzahl(con, 'SELECT COUNT(*) FROM auftraege')} Aufträge, {_anzahl(con, 'SELECT COUNT(*) FROM belege')} Belege "
                     f"(davon {fest} festgeschrieben/storniert), "
                     f"{_anzahl(con, 'SELECT COUNT(*) FROM offene_posten')} offene Posten",
        "zahlungen": f"{_anzahl(con, 'SELECT COUNT(*) FROM zahlungen')} Zahlungsaufträge",
        "personal": f"{_anzahl(con, 'SELECT COUNT(*) FROM zeiten')} Zeiten, {_anzahl(con, 'SELECT COUNT(*) FROM abwesenheiten')} Abwesenheiten, "
                    f"{_anzahl(con, 'SELECT COUNT(*) FROM lohn')} Lohnzahlungen",
        "kunden": f"{_anzahl(con, 'SELECT COUNT(*) FROM kunden')} Kunden",
        "lieferanten": f"{_anzahl(con, 'SELECT COUNT(*) FROM lieferanten')} Lieferanten",
        "termine": f"{_anzahl(con, 'SELECT COUNT(*) FROM termine WHERE auftrag_id IS NULL')} Termine",
        "arbeitsschutz": f"{_anzahl(con, 'SELECT COUNT(*) FROM as_unterweisungen')} Unterweisungen, {_anzahl(con, 'SELECT COUNT(*) FROM as_verbandbuch')} Verbandbuch-Einträge",
        "bank": f"{_anzahl(con, 'SELECT COUNT(*) FROM bank_auszuege')} Kontoauszüge mit {_anzahl(con, 'SELECT COUNT(*) FROM bank_umsaetze')} Umsätzen",
    }
    auftraege = zeilen(con.execute(
        "SELECT a.id, a.nummer, a.bezeichnung, a.status, k.kurzname AS kunde, (SELECT COUNT(*) FROM belege b WHERE b.auftrag_id=a.id) AS belege, "
        "(SELECT COUNT(*) FROM belege b WHERE b.auftrag_id=a.id AND b.status IN ('fest','storniert')) AS fest "
        "FROM auftraege a LEFT JOIN kunden k ON k.id=a.kunde_id ORDER BY a.nummer DESC LIMIT 500"))
    return {"echtbetrieb": protokoll.echtbetrieb(con), "auftraege": auftraege, "protokoll": _anzahl(con, "SELECT COUNT(*) FROM protokoll"), "fest": fest,
            "gruppen": [{"id": k, "text": t, "standard": std, "anzahl": z.get(k, "")} for k, (t, std) in testdaten.TESTDATEN_GRUPPEN.items()],
            "nummern": {"rechnung": rechnungsnummer_info(con)["naechste"], "auftrag": auftragsnummer_info(con)["naechste"],
                        "kunde": kundennummer_info(con)["naechste"]},
            "zaehler_gesetzt": bool(einstellungen(con).get("zaehler"))}


def _im_datenordner(pfad):
    try:
        return bool(pfad) and os.path.commonpath([os.path.abspath(pfad), os.path.abspath(DATEN)]) == os.path.abspath(DATEN)
    except ValueError:
        return False


def _datei_weg(pfad):
    if _im_datenordner(pfad) and os.path.isfile(pfad):
        try:
            os.remove(pfad)
        except OSError:
            pass


def auftrag_loeschen(con, aid):
    """Auftrag löschen. Gesperrt, sobald es Belege, Schriftverkehr oder unterschriebene Rapporte gibt (Aufbewahrung,
    GoBD); dann den Status auf „Abgesagt“ setzen. Daten, die nur zum Auftrag gehören (Positionen, Stunden, Termine,
    Auftragskosten, CAD-Vermerke, Historie), werden mit gelöscht; Verweise anderer Daten (Zeitbuchungen, Anhänge,
    Zahlungsaufträge, Lagerbewegungen …) werden gelöst, damit keine verwaisten Verknüpfungen bleiben."""
    a = con.execute("SELECT nummer FROM auftraege WHERE id=?", (aid,)).fetchone()
    if not a:
        raise ApiFehler("Auftrag nicht gefunden", 404)
    grund = []
    if con.execute("SELECT 1 FROM belege WHERE auftrag_id=? AND (status IN ('fest','storniert') OR IFNULL(versendet,'')<>'' "
                   "OR IFNULL(pdf,'')<>'') LIMIT 1", (aid,)).fetchone():
        grund.append("versendete, abgelegte oder festgeschriebene Belege")
    for tab, text in (("korrespondenz", "E-Mails oder Gesprächsnotizen"), ("briefe", "Briefe"), ("montageberichte", "Rapporte")):
        try:
            if con.execute(f"SELECT 1 FROM {tab} WHERE auftrag_id=? LIMIT 1", (aid,)).fetchone():
                grund.append(text)
        except sqlite3.OperationalError:
            pass
    if grund:
        raise ApiFehler(f"Auftrag {a['nummer']} hat {', '.join(grund)} und muss deshalb aufbewahrt werden. "
                        "Statt zu löschen den Status auf „Abgesagt“ setzen.")
    for r in con.execute("SELECT id FROM auftragskosten WHERE auftrag_id=?", (aid,)).fetchall():
        material.ak_loeschen(con, r["id"])   # bucht Lagerabgänge zurück
    for tab in ("belege", "positionen", "stunden", "termine", "cad_importe", "bautagebuch", "wiedervorlagen"):   # belege: nur noch Entwürfe
        try:
            con.execute(f"DELETE FROM {tab} WHERE auftrag_id=?", (aid,))
        except sqlite3.OperationalError:
            pass
    con.execute("DELETE FROM notizen WHERE auftrag_id=? AND art IN ('status','datei')", (aid,))   # automatische Historie
    for (tab,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        if tab == "auftraege":
            continue
        spalten = {r[1]: r[3] for r in con.execute(f'PRAGMA table_info("{tab}")')}
        if "auftrag_id" in spalten:
            if spalten["auftrag_id"]:
                con.execute(f"DELETE FROM {tab} WHERE auftrag_id=?", (aid,))
            else:
                con.execute(f"UPDATE {tab} SET auftrag_id=NULL WHERE auftrag_id=?", (aid,))
    con.execute("DELETE FROM auftraege WHERE id=?", (aid,))
    prot(con, "auftrag", a["nummer"], f"Auftrag {a['nummer']} gelöscht (nur Entwürfe, kein Schriftverkehr)")
    return {"ok": True}


def autostart_pfad():
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Jahresring.lnk")


def autostart_status():
    if os.name != "nt":
        return {"moeglich": False, "aktiv": False, "fenster": False}
    return {"moeglich": True, "aktiv": os.path.exists(autostart_pfad()), "fenster": einstellungen_roh("autostart_fenster", False) is True}


def autostart_setzen(con, aktiv, fenster):
    """Verknüpfung im Autostart-Ordner von Windows anlegen oder entfernen."""
    if os.name != "nt":
        raise ApiFehler("Autostart gibt es nur unter Windows.")
    pfad = autostart_pfad()
    con.execute("INSERT OR REPLACE INTO einstellungen VALUES ('autostart_fenster', ?)", (json.dumps(bool(fenster)),))
    if not aktiv:
        if os.path.exists(pfad):
            os.remove(pfad)
        return autostart_status()
    ziel = os.path.join(BASIS, "start.bat")
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:JR_LNK); $s.TargetPath=$env:JR_ZIEL; "
          "$s.Arguments=$env:JR_ARG; $s.WorkingDirectory=$env:JR_ORDNER; $s.WindowStyle=7; "
          "$s.IconLocation=$env:JR_ICON; $s.Description='Jahresring'; $s.Save()")
    umgebung = dict(os.environ, JR_LNK=pfad, JR_ZIEL=ziel, JR_ARG="" if fenster else "kein-browser", JR_ORDNER=BASIS,
                    JR_ICON=os.path.join(STATIC, "jahresring.ico"))
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], env=umgebung,
                       capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as f:
        raise ApiFehler(f"Autostart konnte nicht eingerichtet werden: {f}")
    if not os.path.exists(pfad):
        raise ApiFehler("Autostart konnte nicht eingerichtet werden (Verknüpfung wurde nicht angelegt).")
    return autostart_status()


def ort_warnung():
    """Programm- und Datenordner gehört nicht in einen von einem Cloud-Dienst synchronisierten Ordner: die Datenbank
    kann beim gleichzeitigen Synchronisieren beschädigt werden."""
    p = BASIS.lower()
    if any(w in p for w in ("onedrive", "dropbox", "google drive", "icloud", "nextcloud")):
        return (f"Der Programmordner liegt in einem synchronisierten Ordner ({BASIS}). Die Datenbank kann dort beschädigt werden. "
                "Bitte das Programm beenden und den ganzen Ordner nach C:\\Jahresring verschieben (siehe Installationsanleitung).")
    return ""


def autostart_nachziehen():
    """Wurde der Programmordner verschoben (z. B. vom Desktop nach C:\\Jahresring), zeigt die Autostart-Verknüpfung
    noch auf den alten Ort. Ist Autostart eingeschaltet, wird sie deshalb bei jedem Start im Hintergrund neu geschrieben."""
    if os.name != "nt" or not (os.path.exists(autostart_pfad())):
        return

    def lauf():
        try:
            with verbindung() as con:
                autostart_setzen(con, True, einstellungen_roh("autostart_fenster", False) is True)
                con.commit()
        except Exception as f:  # noqa: BLE001
            print("Autostart nachziehen:", f)
    threading.Thread(target=lauf, daemon=True).start()


def lokale_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.1.1", 9))  # es wird nichts gesendet
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def pc_adresse(netz=None):
    """Adresse, mit der das Programm am PC geöffnet wird: immer localhost. Chrome behandelt localhost als sichere
    Seite (Bluetooth für den Zebra-Drucker ohne Sonderfreigabe); Tablet, Handy und VPN nutzen weiter die
    Netzwerkadresse. Alle Fenster am PC nehmen dieselbe Adresse – die Anmeldung hängt daran."""
    return f"http://localhost:{PORT}"


# Einmaliger Umzug des PC-Fensters von der Netzwerkadresse auf localhost: Browserdaten (Einstellungen des
# Zuschnittprogramms, Ansichten) und die Anmeldung werden über den Server von der alten auf die neue Adresse übertragen.
UMZUG = {}


def umzug_erledigt_pfad():
    return os.path.join(DATEN, "umzug_localhost.erledigt")


def umzug_offen():
    return NETZ["aktiv"] and lokale_ip() not in ("127.0.0.1", "") and not os.path.exists(umzug_erledigt_pfad())


def app_fenster(url):
    """Öffnet das Büro als eigenes Programmfenster (Chrome/Edge im App-Modus: ohne Adressleiste und Lesezeichen).
    Geht das nicht, öffnet sich ein normaler Browser-Tab."""
    if umzug_offen() and url.startswith("http://localhost"):
        ziel = url[len(f"http://localhost:{PORT}"):] or "/"
        url = f"http://{lokale_ip()}:{PORT}/umzug.html?ziel={quote(ziel, safe='')}"
    if einstellungen_roh("app_fenster", True) is False:
        return webbrowser.open(url)
    exe = None
    if os.name == "nt":
        for var, rest in (("PROGRAMFILES", r"Google\Chrome\Application\chrome.exe"),
                          ("PROGRAMFILES(X86)", r"Google\Chrome\Application\chrome.exe"),
                          ("LOCALAPPDATA", r"Google\Chrome\Application\chrome.exe"),
                          ("PROGRAMFILES(X86)", r"Microsoft\Edge\Application\msedge.exe"),
                          ("PROGRAMFILES", r"Microsoft\Edge\Application\msedge.exe")):
            k = os.path.join(os.environ.get(var, ""), rest)
            if os.environ.get(var) and os.path.isfile(k):
                exe = k
                break
    if not exe:
        return webbrowser.open(url)
    try:
        subprocess.Popen([exe, f"--app={url}", "--start-maximized"], close_fds=True,   # immer bildschirmfüllend, damit alles sichtbar ist
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        webbrowser.open(url)


def einstellungen_roh(schluessel, standard=None):
    try:
        with verbindung() as con:
            r = con.execute("SELECT wert FROM einstellungen WHERE schluessel=?", (schluessel,)).fetchone()
            return json.loads(r["wert"]) if r else standard
    except Exception:  # noqa: BLE001
        return standard


# Unsichtbarer Messpunkt (weiße 1-px-Schrift ohne eigene Höhe) für „letzte Seite unten bündig“
UB_MARKE = '<div style="height:0;overflow:visible;font:1px/1px Arial,sans-serif;color:#fff;white-space:nowrap">{}</div>'


def _ub_marken_lesen(pdf_pfad):
    """Liefert {marke: (seite, y_mm von unten)} und die Seitenzahl aus einem Mess-PDF."""
    import logging
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    r = PdfReader(pdf_pfad)
    gefunden = {}
    for nr, seite in enumerate(r.pages):
        hoehe_pt = float(seite.mediabox.height)
        unten_pt = float(seite.mediabox.bottom)

        def besucher(text, cm, tm, *_):
            for m in ("JRUBANFANG", "JRUBENDE"):
                if m in (text or ""):
                    y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]   # Textmatrix mit der aktuellen Transformation verrechnen
                    gefunden[m] = (nr, (y - unten_pt) / 72 * 25.4, hoehe_pt / 72 * 25.4)
        try:
            seite.extract_text(visitor_text=besucher)
        except Exception:  # noqa: BLE001
            pass
    return gefunden, len(r.pages)


def unten_abstand(bid, e):
    """Misst, wie viel Platz unter dem Gruß auf der letzten Seite frei ist (mm), damit der Schlussblock
    (Summen, Konditionen, Schlusstext, Gruß) unten bündig steht. 0 = nichts zu verschieben."""
    tmp = os.path.join(DATEN, "tmp")
    os.makedirs(tmp, exist_ok=True)
    mess = os.path.join(tmp, f"messung-{bid}-{threading.get_ident()}.pdf")
    try:
        pdf_url_rendern(f"http://127.0.0.1:{PORT}/druck/{bid}?pdf=1&marken=1", mess)
        m, seiten = _ub_marken_lesen(mess)
    except Exception as f:  # noqa: BLE001
        print("Unten bündig: Messung nicht möglich:", f)
        return 0.0, 0
    finally:
        try:
            os.remove(mess)
        except OSError:
            pass
    if "JRUBANFANG" not in m or "JRUBENDE" not in m:
        return 0.0, seiten
    s_a, (s_e, y_e) = m["JRUBANFANG"][0], m["JRUBENDE"][:2]
    if s_a != s_e:
        return 0.0, seiten   # der Schlussblock geht schon über zwei Seiten – nichts verschieben
    if vorlage_dateien("brief") and e.get("briefvorlage_aktiv", True):
        L = {**STANDARD_EINSTELLUNGEN["brief_layout"], **(e.get("brief_layout") or {})}
        unten = float(L["unten"])
    else:
        unten = 10 + 22   # Seitenrand unten + Platz für die Fußzeile
    frei = y_e - unten - 3   # 3 mm Reserve gegen Rundung und Schriftunterlängen
    return (round(frei, 1) if frei >= 3 else 0.0), seiten


def pdf_rendern(bid, ziel):
    con = verbindung()
    try:
        b = beleg_laden(con, bid)
        e = einstellungen(con)
    finally:
        con.close()
    abstand, seiten = unten_abstand(bid, e) if b["druck"].get("unten_buendig") else (0.0, 0)
    pdf_url_rendern(f"http://127.0.0.1:{PORT}/druck/{bid}?pdf=1" + (f"&abstand={abstand}" if abstand else ""), ziel)
    if abstand and seiten:
        try:
            from pypdf import PdfReader
            if len(PdfReader(ziel).pages) != seiten:   # Seite übergelaufen: lieber ohne Verschieben
                pdf_url_rendern(f"http://127.0.0.1:{PORT}/druck/{bid}?pdf=1", ziel)
        except Exception as f:  # noqa: BLE001
            print("Unten bündig: Prüfung nicht möglich:", f)
    ku = b["daten"].get("kunde", {})
    agb_pdf = agb_original(beleg_agb_art(e, b, ku))
    # Seitenzahlen „Seite 1 von 2“ – AGB-Seiten zählen nicht mit
    if e.get("seitenzahlen", True):
        try:
            pdfseiten.nummerieren(ziel, ohne_letzte=0 if agb_pdf else len(beleg_agb_seiten(e, b, ku)),
                                  rechts_mm=float(e.get("seitenzahl_rechts") or 18), unten_mm=float(e.get("seitenzahl_unten") or 6))
        except Exception as f:  # noqa: BLE001
            print("Seitenzahlen nicht möglich:", f)
    if agb_pdf:
        try:
            agb_anhaengen(ziel, agb_pdf)
        except Exception as f:  # noqa: BLE001
            print("AGB-PDF konnte nicht angehängt werden:", f)
    return ziel


def agb_anhaengen(ziel, agb_pdf):
    import inspect
    import logging
    from pypdf import PdfReader, PdfWriter
    # harmlose Lesehinweise zu leicht unsauberen PDF-Dateien („Object count … exceeds defined trailer size“) nicht protokollieren
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    w = PdfWriter(clone_from=PdfReader(ziel))
    agb = PdfReader(agb_pdf)
    for seite in agb.pages:
        w.add_page(seite)
    if hasattr(w, "compress_identical_objects"):
        # Parameternamen je nach pypdf-Version (neu: remove_duplicates/remove_unreferenced, alt: remove_identicals/remove_orphans)
        par = inspect.signature(w.compress_identical_objects).parameters
        if "remove_duplicates" in par:
            w.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
        else:
            w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    tmp = ziel + ".agb.pdf"
    with open(tmp, "wb") as f:
        w.write(f)
    os.replace(tmp, ziel)


mimetypes.add_type("application/manifest+json", ".webmanifest")
# Windows liefert über die Registry teils falsche Typen (z. B. .js als text/plain) – Service Worker und Module brauchen die richtigen
for _typ, _end in (("text/javascript", ".js"), ("application/json", ".json"), ("text/css", ".css"), ("image/svg+xml", ".svg"), ("image/png", ".png"),
                   ("application/pdf", ".pdf"), ("image/jpeg", ".jpg"), ("image/jpeg", ".jpeg"), ("image/gif", ".gif"), ("image/webp", ".webp"),
                   ("text/plain", ".txt"), ("text/csv", ".csv")):
    mimetypes.add_type(_typ, _end)
NETZ = {"aktiv": False}
INTERN = secrets.token_urlsafe(24)  # erlaubt dem PDF-Browser auf diesem PC den Zugriff ohne Anmeldung


def pdf_url_rendern(url, ziel):
    url += ("&" if "?" in url else "?") + "intern=" + INTERN
    exe = browser_finden()
    if not exe:
        raise ApiFehler("Kein Edge/Chrome gefunden, um das PDF zu erzeugen. Bitte die Druckansicht öffnen und „Als PDF speichern“ wählen.")
    profil = os.path.join(DATEN, "browser-profil")
    os.makedirs(profil, exist_ok=True)
    tmp = ziel + ".tmp.pdf"
    if os.path.exists(tmp):
        os.remove(tmp)
    cmd = [exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
           "--disable-extensions", f"--user-data-dir={profil}", "--no-pdf-header-footer", "--print-to-pdf-no-header",
           f"--print-to-pdf={tmp}", url]
    if not sys.platform.startswith("win") and hasattr(os, "geteuid") and os.geteuid() == 0:
        cmd.insert(1, "--no-sandbox")
    try:
        subprocess.run(cmd, capture_output=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise ApiFehler("PDF-Erzeugung hat zu lange gedauert.")
    if not os.path.exists(tmp) or os.path.getsize(tmp) < 500:
        raise ApiFehler("PDF konnte nicht erzeugt werden. Bitte die Druckansicht öffnen und „Als PDF speichern“ wählen.")
    os.replace(tmp, ziel)
    return ziel


def pdf_unterordner(ordner, art, e):
    po = e.get("pdf_ordner") or {}
    stichwort = po[art] if art in po else STANDARD_EINSTELLUNGEN["pdf_ordner"].get(art, "")   # neue Belegarten auch bei älteren Einstellungen
    if stichwort:
        for name in sorted(os.listdir(ordner)):
            if stichwort.lower() in name.lower() and os.path.isdir(os.path.join(ordner, name)):
                return os.path.join(ordner, name)
    return ordner


def einstellungen_oeffentlich(con):
    e = einstellungen(con)
    e["_datenordner"] = DATEN
    m = dict(e.get("mail") or {})
    m["passwort_gesetzt"] = bool(m.pop("passwort", ""))
    e["mail"] = m
    e["_mail_texte_standard"] = MAIL_TEXTE
    e["_unterschrift"] = os.path.exists(os.path.join(DATEN, UNTERSCHRIFT))
    e["_text_14b_standard"] = HINWEIS_14B
    e["_pdf_ordner_standard"] = STANDARD_EINSTELLUNGEN["pdf_ordner"]
    e["_ort_warnung"] = " ".join(x for x in (NOTFALL["text"], ort_warnung(), SICHERUNG_PRUEFUNG["text"], SICHERUNG_EXTERN["text"], PROTOKOLL_PRUEFUNG["text"], BELEG_PRUEFUNG["text"],
                                                projektsicherung.warnung(DATEN, projektsicherung.einstellung(e.get("projektsicherung")))) if x)
    e["_sicherung_erinnerung"] = sicherung_erinnerung(e.get("sicherung_ziel") or "")
    e["_autostart"] = autostart_status()
    e["_echtbetrieb"] = bool(protokoll.echtbetrieb(con))
    e["_leitstand_map"] = {x: leitstand_status_fuer(e, x, i) for i, x in enumerate([y for y in (e.get("leitstand_schritte") or []) if y])}
    e["_netz"] = {"aktiv": NETZ["aktiv"], "ip": lokale_ip() if NETZ["aktiv"] else "", "port": PORT}
    e["_https"] = {**HTTPS, "fingerabdruck": __import__("zert").fingerabdruck(DATEN) if HTTPS["aktiv"] else "",
                   "namen": __import__("zert").namen(DATEN) if HTTPS["aktiv"] else [], "pc": __import__("socket").gethostname().split(".")[0]}
    return e


MAIL_TEXTE = {
    "angebot": {"betreff": "Angebot {nummer} – {betreff}",
                "text": "{anrede}\n\nvielen Dank für Ihre Anfrage. Im Anhang erhalten Sie mein Angebot {nummer} für „{betreff}“.\n\n"
                        "Bei Fragen melden Sie sich gern. Ich freue mich auf Ihre Rückmeldung.\n\nMit freundlichen Grüßen"},
    "kv": {"betreff": "Kostenvoranschlag {nummer} – {betreff}",
           "text": "{anrede}\n\nim Anhang erhalten Sie meinen Kostenvoranschlag {nummer} für „{betreff}“.\n\nMit freundlichen Grüßen"},
    "ab": {"betreff": "Auftragsbestätigung {nummer} – {betreff}",
           "text": "{anrede}\n\nvielen Dank für Ihren Auftrag. Im Anhang erhalten Sie die Auftragsbestätigung {nummer}.\n\nMit freundlichen Grüßen"},
    "abnahme": {"betreff": "Abnahmeprotokoll {nummer} – {betreff}",
                "text": "{anrede}\n\nim Anhang erhalten Sie das unterschriebene Abnahmeprotokoll {nummer} für „{betreff}“.\n\nVielen Dank für Ihr Vertrauen und mit freundlichen Grüßen"},
    "lieferschein": {"betreff": "Lieferschein {nummer} – {betreff}",
                     "text": "{anrede}\n\nim Anhang erhalten Sie den Lieferschein {nummer}.\n\nMit freundlichen Grüßen"},
    "abschlag": {"betreff": "Abschlagsrechnung {nummer} – {betreff}",
                 "text": "{anrede}\n\nim Anhang erhalten Sie die Abschlagsrechnung {nummer} über {betrag} €.\n"
                         "Bitte überweisen Sie den Betrag bis zum {faellig}. Am schnellsten geht es mit dem GiroCode auf der Rechnung.\n\n"
                         "Mit freundlichen Grüßen"},
    "rechnung": {"betreff": "Rechnung {nummer} – {betreff}",
                 "text": "{anrede}\n\nvielen Dank für Ihren Auftrag. Im Anhang erhalten Sie die Rechnung {nummer} über {betrag} €.\n"
                         "Bitte überweisen Sie den Betrag bis zum {faellig}. Am schnellsten geht es mit dem GiroCode auf der Rechnung.\n\n"
                         "Mit freundlichen Grüßen"},
    "storno": {"betreff": "Stornorechnung {nummer}",
               "text": "{anrede}\n\nim Anhang erhalten Sie die Stornorechnung {nummer} zur Rechnung {bezug}.\n\nMit freundlichen Grüßen"},
    "gutschrift": {"betreff": "Gutschrift {nummer} – {betreff}",
                   "text": "{anrede}\n\nim Anhang erhalten Sie die Gutschrift {nummer} über {betrag} €.\n\nMit freundlichen Grüßen"},
    "korrektur_berichtigen": {"betreff": "Rechnungskorrektur {nummer} zur Rechnung {bezug}",
                              "text": "{anrede}\n\nim Anhang erhalten Sie die Rechnungskorrektur {nummer}. Sie ersetzt die Rechnung {bezug}; der Betrag bleibt unverändert.\n\nMit freundlichen Grüßen"},
    "korrektur": {"betreff": "Rechnungskorrektur {nummer} zur Rechnung {bezug}",
                  "text": "{anrede}\n\nim Anhang erhalten Sie die Rechnungskorrektur {nummer} zur Rechnung {bezug} über {betrag} €.\n\nMit freundlichen Grüßen"},
}


HINWEIS_MAIL = ("Der Inhalt dieser E-Mail ist ausschließlich für den bezeichneten Adressaten oder dessen Vertreter bestimmt. "
                "Sofern diese E-Mail irrtümlich an einen falschen Empfänger versendet wurde, bitten wir diesen, sich mit dem Absender in Verbindung "
                "zu setzen und die E-Mail zu vernichten. Bitte beachten Sie, dass diese E-Mail vertraulich ist und gegebenenfalls rechtlich geschützte "
                "Informationen enthält, so dass jede Form der unerlaubten Kopie oder der unbefugten Weitergabe oder Veröffentlichung dieser E-Mail "
                "oder ihres Inhalts nicht gestattet ist.\nThis e-mail is solely intended for the addressee or his representative. If this e-mail by "
                "mistake is sent to the wrong recipient we kindly ask you to notify the sender immediately and to destroy this e-mail. Please note "
                "that this e-mail is confidential and may contain privileged information so that any kind of unauthorized copying or passing or "
                "publication of this e-mail or its content is strictly forbidden.")


def signatur_teile(e):
    """Signatur aus den Einstellungen; leere Felder werden aus den Firmendaten gebildet (wie die Signatur im Mailprogramm)."""
    m = e.get("mail") or {}
    name = m.get("signatur_name") if m.get("signatur_name") is not None else (e.get("firma_inhaber") or "")
    block = (m.get("signatur") or "").strip()
    if not block:
        tel = (e.get("firma_telefon") or "").strip()
        mobil = re.sub(r"\D", "", tel).startswith(("491", "01"))
        teile = [e.get("firma")] + (e.get("firma_anschrift") or "").split("\n")
        teile += [f"{'Mobil' if mobil else 'Tel.'}: {tel}" if tel else "", f"Mail: {e.get('firma_email') or m.get('adresse') or ''}" if (e.get("firma_email") or m.get("adresse")) else "",
                  f"Web: {e['firma_web']}" if e.get("firma_web") else ""]
        block = "\n".join(x.strip() for x in teile if x and x.strip())
        rechtl = [f"Inhaber: {e['firma_inhaber']}" if e.get("firma_inhaber") else "", f"Steuer-Nr.: {e['steuernummer']}" if e.get("steuernummer") else "",
                  f"USt-IdNr.: {e['ustid']}" if e.get("ustid") else ""]
        rechtl = [x for x in rechtl if x]
        if rechtl:
            block += "\n\n" + "\n".join(rechtl)
    hinweis = m.get("signatur_hinweis") if "signatur_hinweis" in m else HINWEIS_MAIL
    return {"name": name or "", "block": block, "hinweis": hinweis or ""}


def mail_signatur(e):
    """Die Signatur wird beim Senden angehängt (Text und HTML mit Logo), nicht mehr in den Mailtext geschrieben."""
    return ""


def _signatur_laden():
    with verbindung() as con:
        return signatur_teile(einstellungen(con))


def rechnungsadressen_vorn(adr):
    """Rechnungs-/Buchhaltungsadressen des Kunden (rechnung@, buchhaltung@ …) zuerst, damit sie als „An“ vorgeschlagen werden."""
    rg = [x for x in adr if re.match(r"(rechnung|rechnungen|invoice|invoices|buchhaltung|accounting|billing|finanzen)\b", x.split("@")[0], re.I)]
    return rg + [x for x in adr if x not in rg]


def mail_vorschlag(con, bid):
    b = beleg_laden(con, bid)
    e = einstellungen(con)
    k = auftrag_kunde(con, b["auftrag_id"])
    d = b["daten"]
    mk = "korrektur_berichtigen" if b["daten"].get("modus") == "berichtigen" else b["art"]
    vorlage = {**MAIL_TEXTE.get(mk, MAIL_TEXTE["angebot"]), **((e.get("mail_texte") or {}).get(mk) or {})}
    faellig = de_datum(b["faellig"]) if b.get("faellig") else (f"{b['zahlungsziel']} Tage nach Rechnungsdatum" if b.get("zahlungsziel") else "")
    werte = {"anrede": (d.get("kunde") or {}).get("anrede") or k.get("anrede") or "Sehr geehrte Damen und Herren,",
             "nummer": b["nummer"] or "(wird beim Festschreiben vergeben)", "betreff": b["betreff"] or (d.get("auftrag") or {}).get("bezeichnung", ""),
             "betrag": de(abs(b["zahlbetrag"]) if b["art"] == "gutschrift" else (b["zahlbetrag"] if b["ist_rechnung"] else b["brutto"])), "faellig": faellig,
             "belegart": b["artname"],
             "auftrag": (d.get("auftrag") or {}).get("bezeichnung", ""), "bezug": (d.get("bezug") or {}).get("nummer", ""),
             "firma": e.get("firma") or "", "inhaber": e.get("firma_inhaber") or "",
             "gueltig_bis": gueltig_bis(b.get("datum"), e.get("angebot_gueltig_tage", 7))}
    def fuellen(t):
        for kk, v in werte.items():
            t = t.replace("{" + kk + "}", str(v))
        return t
    text = fuellen(vorlage["text"]).rstrip() + "\n" + mail_signatur(e)
    kurz = (d.get('kunde') or {}).get('kurzname', '')
    pdf_name = sauber(f"{b['nummer']}_{b['artname']}_{kurz}" if b["nummer"] else f"{b['artname']}_{kurz}") + ".pdf"
    anh = [{"id": "beleg", "name": pdf_name, "an": True}]
    if b["ist_rechnung"] and xrechnung_gewuenscht(con, b):
        anh.append({"id": "xrechnung", "name": pdf_name[:-4] + "_XRechnung.xml", "an": True})
    dateien = []
    ordner, _ = projektordner(con, b["auftrag_id"])
    if ordner:
        for wurzel, dirs, files in os.walk(ordner):
            tiefe = os.path.relpath(wurzel, ordner).count(os.sep)
            if tiefe >= 2:
                dirs[:] = []
            dirs.sort()
            for f in sorted(files):
                pf = os.path.join(wurzel, f)
                if f.startswith((".", "~$")) or f == pdf_name:
                    continue
                try:
                    groesse = os.path.getsize(pf)
                except OSError:
                    continue
                if groesse <= 20 * 1024 * 1024:
                    dateien.append({"pfad": os.path.relpath(pf, ordner).replace(os.sep, "/"), "groesse": groesse})
            if len(dateien) > 150:
                break
    adr = [x for x in (k.get("email1"), k.get("email2"), k.get("email3"), k.get("email4")) if x]
    if b["ist_rechnung"]:
        adr = rechnungsadressen_vorn(adr)
    cfg = e.get("mail") or {}
    return {"an": adr[0] if adr else "", "adressen": adr, "betreff": fuellen(vorlage["betreff"]), "text": text,
            "anhaenge": anh, "dateien": dateien, "eingerichtet": bool(cfg.get("smtp_server") and cfg.get("passwort")),
            "absender": cfg.get("adresse") or "", "festschreiben": b["ist_rechnung"] and b["status"] == "entwurf",
            "versendet": b.get("versendet") or "", "versendet_an": b.get("versendet_an") or "",
            "kopie_an_mich": bool(cfg.get("kopie_an_mich"))}


def mail_senden(con, bid, d):
    e = einstellungen(con)
    cfg = e.get("mail") or {}
    if not (cfg.get("smtp_server") and cfg.get("passwort")):
        raise ApiFehler("Der E-Mail-Versand ist noch nicht eingerichtet (Einstellungen > E-Mail-Versand).")
    mailversand.adressen(d.get("an"))  # Adressen vor dem Festschreiben prüfen
    mailversand.adressen(d.get("cc"))
    b = beleg_laden(con, bid)
    if b["ist_rechnung"] and b["status"] == "entwurf":
        if not b["leistungsdatum"]:
            con.execute("UPDATE belege SET leistungsdatum=? WHERE id=?", (b["datum"] or date.today().isoformat(), bid))
        beleg_festschreiben(con, bid)
        d["betreff"] = (d.get("betreff") or "").replace("(wird beim Festschreiben vergeben)", beleg_laden(con, bid)["nummer"])
        d["text"] = (d.get("text") or "").replace("(wird beim Festschreiben vergeben)", beleg_laden(con, bid)["nummer"])
    pdf = beleg_pdf(con, bid)
    b = beleg_laden(con, bid)
    gewaehlt = set(d.get("anhaenge") or ["beleg"])
    anh = []
    if "beleg" in gewaehlt:
        with open(pdf["archiv"], "rb") as f:
            anh.append((os.path.basename(pdf["archiv"]), f.read(), "application/pdf"))
    if "xrechnung" in gewaehlt and pdf.get("xrechnung"):
        with open(pdf["xrechnung"], "rb") as f:
            anh.append((os.path.basename(pdf["xrechnung"]), f.read(), "application/xml"))
    if d.get("dateien"):
        ordner, hinweis = projektordner(con, b["auftrag_id"])
        if not ordner:
            raise ApiFehler(hinweis)
        for rel in d["dateien"]:
            pf = im_ordner(ordner, rel)
            if os.path.isfile(pf):
                with open(pf, "rb") as f:
                    anh.append((os.path.basename(pf), f.read(), None))
    if sum(len(x[1]) for x in anh) > 20 * 1024 * 1024:
        raise ApiFehler("Die Anhänge sind zusammen größer als 20 MB. Viele Mailserver nehmen das nicht an.")
    con.commit()  # Festschreibung bleibt erhalten, auch wenn der Versand scheitert
    try:
        r = mailversand.senden(cfg, d.get("an"), d.get("cc"), d.get("betreff") or b["betreff"], d.get("text") or "", anh,
                               kopie_an_mich=bool(d.get("kopie_an_mich")))
    except mailversand.MailFehler as f:
        raise ApiFehler(str(f))
    jetzt_txt = datetime.now().strftime("%d.%m.%Y %H:%M")
    con.execute("UPDATE belege SET versendet=?, versendet_an=? WHERE id=?", (datetime.now().isoformat(timespec="minutes"), d.get("an"), bid))
    if b["art"] in ("angebot", "kv"):
        status_fortschreiben(con, beleg_laden(con, bid))
    con.execute("INSERT INTO notizen (kunde_id, auftrag_id, text, angelegt) VALUES (?,?,?,?)",
                (b["kunde_id"], b["auftrag_id"], f"E-Mail gesendet an {d.get('an')}: {d.get('betreff')} "
                 f"({', '.join(x[0] for x in anh) or 'ohne Anhang'})", jetzt()))
    korrespondenz_eintragen(con, "mail_aus", kunde_id=b["kunde_id"], auftrag_id=b["auftrag_id"], betreff=d.get("betreff") or "",
                            text=d.get("text") or "", an=d.get("an") or "", message_id=r.get("message_id"), anhaenge=[x[0] for x in anh])
    r["beleg"] = beleg_laden(con, bid)
    r["zeit"] = jetzt_txt
    return r


def zeitbericht_daten(con, auftrag_ids, q):
    """Gebuchte Stunden der Aufträge mit Uhrzeit (aus der Zeiterfassung), Tätigkeit, Titel und Mitarbeiter."""
    if not auftrag_ids:
        return [], []
    wo, arg = [f"s.auftrag_id IN ({','.join('?' * len(auftrag_ids))})"], list(auftrag_ids)
    if q.get("von"):
        wo.append("s.datum>=?"); arg.append(q["von"])
    if q.get("bis"):
        wo.append("s.datum<=?"); arg.append(q["bis"])
    if (q.get("ma") or "").isdigit():
        wo.append("COALESCE(s.mitarbeiter_id, z.mitarbeiter_id)=?"); arg.append(int(q["ma"]))
    reihen = con.execute(
        "SELECT s.datum, s.stunden, s.kst, COALESCE(NULLIF(z.taetigkeit,''), s.taetigkeit) AS taetigkeit, s.zeit_id, s.titel, z.beginn, z.ende, z.notiz, a.nummer AS auftragsnr, a.bezeichnung AS auftrag, "
        "m.vorname, m.nachname, m.kuerzel, m.nummer FROM stunden s LEFT JOIN zeiten z ON z.id=s.zeit_id "
        "LEFT JOIN mitarbeiter m ON m.id=COALESCE(s.mitarbeiter_id, z.mitarbeiter_id) LEFT JOIN auftraege a ON a.id=s.auftrag_id "
        f"WHERE {' AND '.join(wo)} ORDER BY s.datum {'ASC' if q.get('sort') == 'auf' else 'DESC'}, "
        f"COALESCE(z.beginn,'') {'ASC' if q.get('sort') == 'auf' else 'DESC'}, s.id", arg).fetchall()
    zeilen = []
    for r in reihen:
        d = dict(r)
        d["mitarbeiter"] = personal.name(r) if r["vorname"] is not None or r["nachname"] is not None else "ohne Mitarbeiter"
        zeilen.append(d)
    ma = [{"id": m["id"], "name": personal.name(m)} for m in con.execute(
        "SELECT * FROM mitarbeiter WHERE id IN (SELECT COALESCE(s.mitarbeiter_id, z.mitarbeiter_id) FROM stunden s "
        f"LEFT JOIN zeiten z ON z.id=s.zeit_id WHERE s.auftrag_id IN ({','.join('?' * len(auftrag_ids))})) ORDER BY nachname, vorname",
        list(auftrag_ids))]
    return zeilen, ma


def projekt_zeitbericht_html(con, pid, q, pdf=False):
    try:
        p = projekte.laden(con, pid)
    except projekte.Fehler as f:
        raise ApiFehler(str(f), f.code)
    e = einstellungen(con)
    hilfe = {"h": h, "de": lambda z, n=2: de(fl(z), n), "de_datum": de_datum}
    zeilen, ma = zeitbericht_daten(con, [x["id"] for x in p["auftraege"]], q)
    inhalt = werkstatt.zeitbericht(zeilen, q, hilfe, mehrere_auftraege=True)
    titel = f"Zeitbericht Projekt {p['nummer']}"
    leiste = "" if pdf else (f'<div class="leiste"><b>{h(titel)}</b>{werkstatt.zeitbericht_filter(q, ma, h)}<span style="flex:1"></span>'
                             '<button onclick="window.print()">Drucken / PDF</button></div>')
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8"><title>{h(titel)}</title><style>{werkstatt.CSS}</style></head><body>{leiste}<div class="blatt">'
            f'{werkstatt.logo_zeile()}<div class="kopf"><div class="titelblock"><h1>ZEITBERICHT</h1><div class="k2">Projekt <b>{h(p["nummer"])} {h(p["bezeichnung"])}</b>'
            f'{"<br>Kunde <b>" + h(p.get("kundennr")) + " " + h(p.get("kunde")) + "</b>" if p.get("kunde") else ""}'
            f'<br>Aufträge: {h(", ".join(x["nummer"] for x in p["auftraege"]))}</div></div>'
            f'<div class="rechts"><table><tr><td>Nr.</td><td class="nr">{h(p["nummer"])}</td></tr><tr><td>Aufträge</td><td><b>{len(p["auftraege"])}</b></td></tr></table></div></div>'
            f'{inhalt}<div class="fuss">{h(e.get("firma_inhaber") or e.get("firma") or "")} · {datetime.now():%d.%m.%Y · %H:%M}</div></div></body></html>')


def papier_html(con, aid, art, q, pdf=False):
    """Werkstattpapiere und Auswertungen (siehe werkstatt.py)."""
    a = auftrag_laden(con, aid)
    k = auftrag_kunde(con, aid)
    e = einstellungen(con)
    erg = auftrag_rechnen(con, aid)
    opts = {x: q.get(x, "1") != "0" for x in ("anschrift", "telefon", "bemerkungen", "bilder", "preise")}
    opts["erklaerung"] = q.get("erklaerung") == "1"
    opts["handfelder"] = q.get("handfelder") == "1"
    opts["ausgabe"] = q.get("ausgabe", "titel")
    nur = {int(x) for x in q.get("pos", "").split(",") if x.strip().isdigit()} or None

    def qr(text):
        import segno
        buf = io.BytesIO()
        segno.make(text, error="m").save(buf, kind="svg", scale=1, border=0, xmldecl=False, omitsize=True)
        return buf.getvalue().decode()
    stamm = {r["nummer"]: dict(r) for r in con.execute(
        "SELECT m.nummer, m.bestellnr, l.kurzname AS lieferant FROM material m LEFT JOIN lieferanten l ON l.id=m.lieferant_id")}
    hilfe = {"h": h, "de": lambda z, n=2: de(fl(z), n), "de_datum": de_datum, "text_html": text_html, "qr": qr, "stamm": stamm,
             "ersteller": e.get("firma_inhaber") or e.get("firma") or "", "zuschnitt": e.get("zuschnitt_zugabe") or {}, "pdf": pdf}
    if art in ("materialsummen", "werkstattauftrag", "montageauftrag"):
        hilfe["as_links"] = arbeitsschutz.links_je_nummer(con)
        if art != "materialsummen":
            nummern, ids = auftrag_material_nummern(con, aid)
            hilfe["as_auftrag"] = arbeitsschutz.auftrag_materialien(con, nummern, ids)
    namen = {**werkstatt.WERKSTATT, **werkstatt.AUSWERTUNG}
    if art not in namen:
        raise ApiFehler("Unbekanntes Dokument", 404)
    if art == "werkstattauftrag":
        inhalt = werkstatt.werkstattauftrag(a, k, erg, opts, hilfe, nur)
    elif art == "stueckliste":
        inhalt = werkstatt.stueckliste(a, k, erg, opts, hilfe, nur)
    elif art == "materialsummen":
        inhalt = werkstatt.materialsummen_html(a, k, erg, opts, hilfe, nur)
    elif art == "montageauftrag":
        inhalt = werkstatt.montageauftrag(a, k, erg, opts, hilfe, nur)
    elif art == "stunden":
        inhalt = werkstatt.auswertung_stunden(a, k, erg, opts, hilfe)
    elif art == "kosten":
        inhalt = werkstatt.auswertung_kosten(a, k, erg, opts, hilfe)
    elif art == "sollist":
        inhalt = werkstatt.auswertung_sollist(a, k, erg, opts, hilfe, soll_ist(con, aid, q.get("titel")))
    elif art == "zeitbericht":
        zeilen, ma = zeitbericht_daten(con, [aid], q)
        return werkstatt.rahmen(namen[art], a, k, werkstatt.zeitbericht(zeilen, q, hilfe), hilfe, opts, pdf=pdf,
                                leiste_extra=werkstatt.zeitbericht_filter(q, ma, h))
    else:
        inhalt = werkstatt.auswertung_lohnmaterial(a, k, erg, opts, hilfe)
    return werkstatt.rahmen(namen[art], a, k, inhalt, hilfe, opts, pdf=pdf)


def papier_pdf(con, aid, art, q):
    a = auftrag_laden(con, aid)
    namen = {**werkstatt.WERKSTATT, **werkstatt.AUSWERTUNG}
    if art not in namen:
        raise ApiFehler("Unbekanntes Dokument", 404)
    con.commit()
    name = sauber(f"{a['nummer']}_{namen[art].replace('/', '-')}") + ".pdf"
    ordner, hinweis = projektordner(con, aid)
    e = einstellungen(con)
    if ordner:
        ziel_ordner = ordner
        wunsch = [(e.get("pdf_ordner") or {}).get("werkstatt")] + ["Werkstatt", "Fertigung", "Konstruktion", "Planung"]
        for stichwort in [w for w in wunsch if w]:
            treffer = [n for n in sorted(os.listdir(ordner)) if stichwort.lower() in n.lower() and os.path.isdir(os.path.join(ordner, n))]
            if treffer:
                ziel_ordner = os.path.join(ordner, treffer[0])
                break
    else:
        ziel_ordner = os.path.join(DATEN, "tmp")
        os.makedirs(ziel_ordner, exist_ok=True)
    ziel = os.path.join(ziel_ordner, name)
    query = "&".join(f"{k}={quote(str(v))}" for k, v in q.items() if k != "art")
    pdf_url_rendern(f"http://127.0.0.1:{PORT}/papier/{aid}/{art}?pdf=1&{query}", ziel)
    erg = {"pfad": ziel, "hinweis": None if ordner else hinweis}
    if ordner:
        erg["projekt_rel"] = os.path.relpath(ziel, ordner).replace(os.sep, "/")
    return erg


ZUSCHNITT_DATEI = os.path.join(DATEN, "zuschnitt.html")


def kunden_import(con, d):
    try:
        tab = kundenimport.tabelle_lesen(base64.b64decode(d.get("daten") or ""), d.get("dateiname"))
    except kundenimport.ImportFehler as f:
        raise ApiFehler(str(f))
    kopf, daten_zeilen = tab[0], tab[1:]
    e = einstellungen(con)
    gruppen = e.get("kundengruppen") or []
    zuordnung = d.get("zuordnung") or kundenimport.vorschlag(kopf)
    gruppe_std = d.get("gruppe") or (gruppen[0] if gruppen else "")
    if not d.get("ausfuehren"):
        vorschau = []
        for z in daten_zeilen[:6]:
            k = kundenimport.datensatz(z, zuordnung, gruppen, gruppe_std)
            if k:
                k["_doppelt"] = bool(kundenimport.doppelt(con, k))
                vorschau.append(k)
        return {"kopf": kopf, "beispiele": daten_zeilen[:5], "anzahl": len(daten_zeilen), "zuordnung": zuordnung,
                "felder": [[k, n] for k, n, _ in kundenimport.FELDER], "vorschau": vorschau,
                "doppelte": sum(1 for z in daten_zeilen if (lambda k: k and kundenimport.doppelt(con, k))(
                    kundenimport.datensatz(z, zuordnung, gruppen, gruppe_std)))}
    modus = d.get("doppelte") or "ueberspringen"
    neu = aktualisiert = uebersprungen = leer = 0
    maxnr = con.execute("SELECT MAX(nummer) FROM kunden").fetchone()[0]
    naechste = max(int(e.get("kundennr_start") or 100000), (maxnr or 0) + 1)
    for z in daten_zeilen:
        k = kundenimport.datensatz(z, zuordnung, gruppen, gruppe_std)
        if not k:
            leer += 1
            continue
        vorhanden = kundenimport.doppelt(con, k)
        werte = kunde_daten(k)
        if any(werte.get(f) for f in adressen.FELDER):
            werte = adressen.ableiten({}, werte)
            if k.get("anrede"):
                werte["anrede"] = k["anrede"]
            if k.get("kurzname"):
                werte["kurzname"] = k["kurzname"]
        if vorhanden:
            if modus == "aktualisieren":
                werte.pop("nummer", None)
                werte["geaendert"] = jetzt()
                con.execute(f"UPDATE kunden SET {','.join(f'{x}=?' for x in werte)} WHERE id=?", list(werte.values()) + [vorhanden])
                aktualisiert += 1
            else:
                uebersprungen += 1
            continue
        if not werte.get("nummer") or con.execute("SELECT 1 FROM kunden WHERE nummer=?", (werte["nummer"],)).fetchone():
            werte["nummer"] = naechste
        naechste = max(naechste, int(werte["nummer"]) + 1)
        werte.setdefault("zahlungskonto", (e.get("zahlungskonten") or [""])[0])
        werte["angelegt"] = werte["geaendert"] = jetzt()
        con.execute(f"INSERT INTO kunden ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})", list(werte.values()))
        neu += 1
    return {"neu": neu, "aktualisiert": aktualisiert, "uebersprungen": uebersprungen, "leer": leer}


def kunde_zeile(con, kid):
    r = con.execute("SELECT * FROM kunden WHERE id=?", (kid,)).fetchone()
    return dict(r) if r else {}


def xrechnung_gewuenscht(con, b):
    fmt = (b["daten"].get("kunde") or {}).get("rechnungsformat") or auftrag_kunde(con, b["auftrag_id"]).get("rechnungsformat")
    return (fmt or "").lower() == "xrechnung"


def status_automatik(e):
    std = STANDARD_EINSTELLUNGEN["status_automatik"]
    eigen = e.get("status_automatik") or {}
    return {k: {**std[k], **(eigen.get(k) or {})} for k in std}


def status_fortschreiben(con, b):
    """Setzt Auftrags- und Positionsstatus, wenn ein Beleg herausgeht (PDF gespeichert, gesendet, festgeschrieben).
    Der Status geht nur vorwärts (Reihenfolge der Auswahllisten), nie zurück."""
    if b["ist_rechnung"] and b["status"] not in ("fest", "storniert"):
        return []
    if b["art"] in ("angebot", "kv") and not b.get("versendet"):
        return []   # Angebot zählt erst, wenn es versendet ist (E-Mail aus dem Programm oder Vermerk „versendet“)
    e = einstellungen(con)
    auto = status_automatik(e)
    art = b["art"]
    meldung = []
    if art == "lieferschein":
        geliefert_setzen(con, b["auftrag_id"], b.get("datum"))
    a = con.execute("SELECT id, status FROM auftraege WHERE id=?", (b["auftrag_id"],)).fetchone()
    ziel = auto["auftrag"].get(art) or ""
    liste = e.get("auftragsstatus") or []
    if a and ziel in liste:
        alt = liste.index(a["status"]) if a["status"] in liste else -1
        if liste.index(ziel) > alt:
            con.execute("UPDATE auftraege SET status=?, geaendert=? WHERE id=?", (ziel, jetzt(), a["id"]))
            meldung.append(f"Auftrag: {ziel}")
    ziel_p = auto["position"].get(art) or ""
    pliste = e.get("positionsstatus") or []
    if ziel_p in pliste:
        ids = [z["id"] for z in (b["daten"].get("zeilen") or []) if z.get("typ") == "pos" and z.get("id")
               and not (z.get("alternativ") and art not in ("angebot", "kv"))]
        rows = con.execute("SELECT id, parent_id, status, gesperrt FROM positionen WHERE auftrag_id=?", (b["auftrag_id"],)).fetchall()
        haupt = {r["id"] for r in rows if not r["parent_id"]}
        auswahl = set(ids) & haupt if ids else {r["id"] for r in rows if not r["parent_id"] and (art in ("angebot", "kv") or not r["gesperrt"])}
        if art not in ("angebot", "kv"):
            auswahl -= {r["id"] for r in con.execute("SELECT id FROM positionen WHERE auftrag_id=? AND alternativ=1", (b["auftrag_id"],))}
        # Unterpositionen gehören dazu
        nach = True
        while nach:
            nach = False
            for r in rows:
                if r["parent_id"] in auswahl and r["id"] not in auswahl:
                    auswahl.add(r["id"])
                    nach = True
        n = 0
        for r in rows:
            if r["id"] in auswahl:
                alt = pliste.index(r["status"]) if r["status"] in pliste else -1
                if pliste.index(ziel_p) > alt:
                    con.execute("UPDATE positionen SET status=? WHERE id=?", (ziel_p, r["id"]))
                    n += 1
        if n:
            meldung.append(f"{n} Position{'en' if n > 1 else ''}: {ziel_p}")
    if meldung:
        con.execute("INSERT INTO notizen (kunde_id, auftrag_id, text, angelegt) VALUES (?,?,?,?)",
                    (b["kunde_id"], b["auftrag_id"], f"{b['artname']} {b['nummer'] or ''}: Status gesetzt ({'; '.join(meldung)})", jetzt()))
    return meldung


def beleg_pdf(con, bid):
    """Erzeugt das PDF: Archivkopie in daten/belege und Kopie im Projektordner."""
    b = beleg_laden(con, bid)
    con.commit()  # damit der Browser beim Abruf der Druckansicht den aktuellen Stand sieht
    e = einstellungen(con)
    name = sauber(f"{b['nummer'] or 'Entwurf-' + str(bid)}_{b['artname']}_{b['daten'].get('kunde', {}).get('kurzname', '')}") + ".pdf"
    archiv = os.path.join(DATEN, "belege", b["datum"][:4] if b["datum"] else "ohne-datum")
    os.makedirs(archiv, exist_ok=True)
    archiv_pfad = os.path.join(archiv, name)
    if b["status"] in ("fest", "storniert") and os.path.exists(archiv_pfad):
        pass  # festgeschriebene Rechnung: Archiv-PDF bleibt unverändert
    else:
        pdf_rendern(bid, archiv_pfad)
        if b["ist_rechnung"] and b["status"] in ("fest", "storniert") and e.get("zugferd", True):
            try:
                xml = erechnung.cii_xml(b, False, auftrag_kunde(con, b["auftrag_id"]))
                tmp = archiv_pfad + ".zf.pdf"
                erechnung.zugferd_pdf(archiv_pfad, xml, tmp, f"{b['artname']} {b['nummer']}", (b["daten"].get("firma") or {}).get("firma") or "")
                os.replace(tmp, archiv_pfad)
            except Exception as f:  # noqa: BLE001
                print("ZUGFeRD nicht möglich:", f)
                zf_hinweis = str(f)
        if b["ist_rechnung"] and b["status"] in ("fest", "storniert") and os.path.isfile(archiv_pfad):
            # Hash des Archiv-PDFs ins Protokoll: spätere Änderungen an der Datei fallen bei der Belegprüfung auf
            prot(con, "archiv_pdf", b["nummer"], f"Archiv-PDF zu {b['artname']} {b['nummer']} erzeugt: {name}",
                 {"id": b["id"], "nummer": b["nummer"], "datei": os.path.relpath(archiv_pfad, os.path.join(DATEN, "belege")).replace(os.sep, "/"),
                  "sha256": datei_sha256(archiv_pfad), "groesse": os.path.getsize(archiv_pfad)})
    ergebnis = {"archiv": archiv_pfad, "projekt": None}
    if "zf_hinweis" in locals():
        ergebnis["erechnung_hinweis"] = "Das PDF enthält keine ZUGFeRD-Daten: " + zf_hinweis
    xr_name = xr_pfad = None
    if b["ist_rechnung"] and b["status"] in ("fest", "storniert") and xrechnung_gewuenscht(con, b):
        try:
            xr_name = name[:-4] + "_XRechnung.xml"
            xr_pfad = os.path.join(archiv, xr_name)
            if not os.path.exists(xr_pfad) or os.path.getsize(xr_pfad) == 0:
                xml = erechnung.cii_xml(b, True, auftrag_kunde(con, b["auftrag_id"]))
                with open(xr_pfad, "wb") as f:
                    f.write(xml)
            ergebnis["xrechnung"] = xr_pfad
        except Exception as f:  # noqa: BLE001
            ergebnis["erechnung_hinweis"] = "XRechnung konnte nicht erzeugt werden: " + str(f)
            xr_pfad = None
    ordner, hinweis = projektordner(con, b["auftrag_id"])
    if ordner:
        ziel = os.path.join(pdf_unterordner(ordner, b["art"], e), name)
        shutil.copyfile(archiv_pfad, ziel)
        if xr_pfad:
            shutil.copyfile(xr_pfad, os.path.join(os.path.dirname(ziel), xr_name))
        ergebnis["projekt"] = ziel
        ergebnis["projekt_rel"] = os.path.relpath(ziel, ordner).replace(os.sep, "/")
    else:
        ergebnis["hinweis"] = hinweis
    con.execute("UPDATE belege SET pdf=? WHERE id=?", (ergebnis.get("projekt") or archiv_pfad, bid))
    ergebnis["status"] = status_fortschreiben(con, beleg_laden(con, bid))
    return ergebnis


# ---------- Formatierter Text (fett, kursiv, unterstrichen, Größe, Aufzählung) ----------
from html.parser import HTMLParser
from html import escape as _esc

RT_TAGS = {"b", "strong", "i", "em", "u", "br", "p", "div", "ul", "ol", "li", "span"}
RT_MUSTER = re.compile(r"<(b|strong|i|em|u|br|p|div|ul|ol|li|span)\b[^>]*>|&(lt|gt|amp|nbsp|quot);", re.I)


class _Bereiniger(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.stapel, self.ignorieren = [], [], 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("script", "style", "head", "title"):
            self.ignorieren += 1
            return
        if tag == "font":
            tag, groesse = "span", dict(attrs).get("size")
            stil = {"1": "7pt", "2": "8pt", "3": "", "4": "12pt", "5": "14pt", "6": "16pt", "7": "18pt"}.get(groesse or "", "")
            attrs = [("style", f"font-size:{stil}")] if stil else []
        if tag not in RT_TAGS:
            self.stapel.append(None)
            return
        if tag == "br":
            self.out.append("<br>")
            return
        attr = ""
        if tag == "span":
            m = re.search(r"font-size:\s*([\d.]+)(pt|px)", dict(attrs).get("style") or "")
            if m:
                pt = float(m.group(1)) * (0.75 if m.group(2) == "px" else 1)
                attr = f' style="font-size:{max(6, min(24, pt)):g}pt"'
            fett = re.search(r"font-weight:\s*(bold|[6-9]00)", dict(attrs).get("style") or "")
            if fett:
                attr = attr[:-1] + ';font-weight:bold"' if attr else ' style="font-weight:bold"'
        self.out.append(f"<{tag}{attr}>")
        self.stapel.append(tag)

    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style", "head", "title"):
            self.ignorieren = max(0, self.ignorieren - 1)
            return
        tag = "span" if tag.lower() == "font" else tag.lower()
        if tag == "br":
            return
        if tag in self.stapel:
            while self.stapel:
                t = self.stapel.pop()
                if t:
                    self.out.append(f"</{t}>")
                if t == tag:
                    break

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "br":
            self.out.append("<br>")

    def handle_data(self, data):
        if not self.ignorieren:
            self.out.append(_esc(data, quote=False))

    def ergebnis(self):
        while self.stapel:
            t = self.stapel.pop()
            if t:
                self.out.append(f"</{t}>")
        return "".join(self.out)


def ist_html(t):
    return bool(t) and bool(RT_MUSTER.search(t))


def bereinigen(t):
    """Lässt nur erlaubte Formatierungen stehen. Reiner Text bleibt unverändert."""
    if not ist_html(t):
        return t or ""
    b = _Bereiniger()
    b.feed(t)
    return b.ergebnis()


def rich_html(t):
    return bereinigen(t) if ist_html(t) else _esc(t or "", quote=False).replace("\n", "<br>")


def klartext(t):
    if not ist_html(t):
        return t or ""
    t = re.sub(r"<br\s*/?>|</?(div|p|li)\b[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    from html import unescape
    return re.sub(r"\n{3,}", "\n\n", unescape(t)).strip("\n")


def erste_zeile_fett(html):
    """Fettet die erste Zeile (Kurztext) einer Position."""
    m = re.search(r"<br>|<div|<p\b|<ul|<ol", html, re.I)
    kopf, rest = (html[:m.start()], html[m.start():]) if m else (html, "")
    if not kopf.strip():
        # Text beginnt mit einem Block: erste Zeile im ersten Block fetten
        m2 = re.match(r"(\s*<(div|p)>)(.*?)(</\2>|<br>)", html, re.S | re.I)
        if m2:
            return html[:m2.start(3)] + f"<b>{m2.group(3)}</b>" + html[m2.end(3):]
        return html
    return f"<b>{kopf}</b>{rest}"


# ---------- Druckansicht (HTML) ----------
def text_html(t, fett_erste=True):
    html = rich_html(t)
    return erste_zeile_fett(html) if fett_erste and html else html


BELEG_CSS = """
* { box-sizing: border-box; }
.rt ul, .rt ol, td ul, td ol { margin: 1mm 0 1mm 5mm; padding-left: 4mm; }
.rt p, td p { margin: 0 0 1.5mm; }
h1 { font-size: 14pt; margin: 4mm 0 1mm; }
.betreff { font-weight: 600; margin-bottom: 5mm; }
tr.bildzeile td { border-bottom: .3pt solid #ccc; padding: 1mm 1.5mm 3mm; }
tr.titel { page-break-after: avoid; break-after: avoid; }
tr.bildzeile, figure { page-break-inside: avoid; break-inside: avoid; }
table.pos tr.pos:has(+ tr.bildzeile) td { border-bottom: none; }
.pos-bilder { display: flex; flex-direction: column; align-items: center; gap: 3mm; }
.pos-bilder figure { margin: 0; text-align: center; }
.pos-bilder img { width: 100%; display: block; max-height: 215mm; object-fit: contain; object-position: center top; }
.pos-bilder figcaption { font-size: 8pt; color: #555; margin-top: 1mm; text-align: center; }
.zusammen { margin: 2mm 0 4mm auto; width: 60%; page-break-inside: avoid; }
.zusammen .zs-kopf { font-weight: 700; border-bottom: .8pt solid #333; padding: 1mm 1.5mm; font-size: 9pt; }
.zusammen table { width: 100%; border-collapse: collapse; }
.zusammen td { padding: 1.2mm 1.5mm; border-bottom: .3pt solid #ccc; }
.zusammen tr.zs-summe td { font-weight: 700; border-bottom: .8pt solid #333; }
.zahlung { display: flex; gap: 6mm; align-items: flex-start; page-break-inside: avoid; }
.zahlung .zahl-text { flex: 1; }
.girocode { flex: 0 0 26mm; text-align: center; font-size: 6.5pt; line-height: 1.25; color: #444; }
.girocode svg { margin-bottom: 1mm; }
.einl, .schluss { margin: 0 0 4mm; }
table.pos { width: 100%; border-collapse: collapse; margin: 2mm 0 4mm; }
table.pos.geteilt { margin-bottom: 0; } table.pos.pos-ende { margin-top: 0; }
table.pos th { text-align: left; font-size: 8.5pt; border-bottom: .8pt solid #333; padding: 1.2mm 1.5mm; }
table.pos td { padding: 2mm 1.5mm; vertical-align: top; border-bottom: .3pt solid #ccc; }
table.pos tr { page-break-inside: avoid; }
tr.titel td { font-weight: 700; padding-top: 4mm; border-bottom: .6pt solid #777; }
tr.tsum td { font-style: italic; border-bottom: .6pt solid #777; }
tr.unter td { font-size: 8.8pt; color: #333; padding-top: 1mm; }
table.pos tr.pos:has(+ tr.unter) td, table.pos tr.unter:has(+ tr.unter) td, table.pos tr.unter:has(+ tr.bildzeile) td,
table.pos tr.bildzeile:has(+ tr.unter) td { border-bottom: none; }
tr.textpos td { font-size: 9pt; }
.r { text-align: right; } .nw { white-space: nowrap; }
.alt { font-size: 7.5pt; font-weight: 700; letter-spacing: .3pt; color: #555; }
.klein, small { font-size: 8pt; color: #555; }
table.summen { margin-left: auto; border-collapse: collapse; min-width: 95mm; page-break-inside: avoid; }
table.summen td { padding: 1mm 1.5mm; } table.summen tr:last-child td { border-top: .8pt solid #333; }
.zahlung { margin: 5mm 0 3mm; }
.gruss { margin-top: 2mm; position: relative; }
.gruss.mit-unterschrift { margin-top: 5mm; margin-bottom: 8mm; }
.gruss img.unterschrift { position: absolute; left: -2mm; top: -7mm; height: 17mm; max-width: 70mm; z-index: 4; pointer-events: none; }
.ende { page-break-inside: avoid; margin-top: 6mm; }
.info { font-size: 9pt; border-collapse: collapse; } .info td { padding: 0 0 1mm 4mm; } .info td:first-child { color: #555; padding-left: 0; }
.wasser { position: fixed; top: 110mm; left: 30mm; font-size: 70pt; color: rgba(200,0,0,.12); transform: rotate(-30deg); font-weight: 700; z-index: 5; }
"""


def beleg_agb_art(e, b, ku):
    if b["art"] not in (e.get("agb_bei") or []):
        return None
    return "agb_verbraucher" if ku.get("gruppe") in (e.get("agb_verbraucher_gruppen") or ["Privatkunde"]) else "agb_unternehmen"


def beleg_agb_seiten(e, b, ku):
    art_agb = beleg_agb_art(e, b, ku)
    return [f"/api/vorlage/{f}" for f in vorlage_dateien(art_agb)] if art_agb else []


def zahlungsplan_text(e, dr, s):
    """Konditionen als Zahlungsplan: Anzahlung in % (je Beleg), Restzahlung in Tagen, optional Lieferzeit in Wochen."""
    pz = fl(dr.get("plan_anzahlung"))
    rest = int(fl(dr.get("plan_rest") if dr.get("plan_rest") not in (None, "") else e.get("zahlungsplan_rest") or 10))
    wochen = fl(dr.get("plan_wochen"))
    werte = {"anzahlung": de(pz, 0 if pz == int(pz) else 2), "anzahlung_betrag": de(round(fl(s.get("brutto")) * pz / 100, 2)),
             "rest_tage": str(rest), "lieferwochen": de(wochen, 0 if wochen == int(wochen) else 1)}

    def fuellen(t):
        if isinstance(t, list):   # ältere Speicherung als Zeilenliste
            t = " ".join(str(x) for x in t)
        for k, v in werte.items():
            t = t.replace("{" + k + "}", v)
        return t
    text = fuellen(e.get("zahlungsplan_text") or STANDARD_EINSTELLUNGEN["zahlungsplan_text"])
    if wochen > 0:
        text += " " + fuellen(e.get("zahlungsplan_lieferung") or STANDARD_EINSTELLUNGEN["zahlungsplan_lieferung"])
    return h(text.strip())


def druck_html(con, bid, als_pdf=False, abstand=0.0, marken=False):
    """abstand: Leerraum in mm vor dem Schlussblock (letzte Seite unten bündig), marken: unsichtbare Messpunkte für die Berechnung."""
    b = beleg_laden(con, bid)
    d = b["daten"]
    e = einstellungen(con)
    fi = d.get("firma") or firma_daten(e)
    ku = d.get("kunde", {})
    s = d.get("summen", {})
    dr = b["druck"]
    preise = bool(dr.get("preise", d.get("preise", True)))
    brutto = d.get("brutto_anzeige") and preise
    faktor = 1 + (s.get("ust_satz", 19) / 100) if brutto else 1
    rechnung = b["ist_rechnung"]

    def betrag(v, klammer=False):
        t = de(v * faktor)
        return f"({t})" if klammer else t

    def bilder_html(liste):
        if not liste:
            return ""
        breite = {"klein": "45%", "mittel": "70%", "gross": "100%"}
        teile = []
        for x in liste:
            datei = os.path.basename(x.get("datei") or "")
            if not datei or not os.path.exists(os.path.join(BILDER, datei)):
                continue
            teile.append(f'<figure style="width:{breite.get(x.get("groesse"), "58%")}"><img src="/api/bild/{h(bild_fuer_druck(datei, x.get("groesse")))}">'
                         + (f'<figcaption>{h(x["text"])}</figcaption>' if x.get("text") else "") + "</figure>")
        return f'<tr class="bildzeile"><td></td><td colspan="3"><div class="pos-bilder">{"".join(teile)}</div></td><td></td></tr>' if teile else ""

    rows, zusammen = [], []
    gruppen_start, titel_vorher = [], None
    for z in d.get("zeilen", []):
        if z["typ"] == "titel":
            titel_vorher = len(rows)
            rows.append(f'<tr class="titel"><td colspan="5">{h(z["name"])}{" <small>(nicht in der Summe)</small>" if z.get("gesperrt") else ""}</td></tr>')
        elif z["typ"] == "titelsumme":
            if preise:
                zusammen.append(z)
        elif z["typ"] == "pos":
            zg = z.get("zeige", {})
            ist_text = not zg.get("anzahl") and not zg.get("ep") and not zg.get("gp")
            menge = f'{de(z["menge"], 2 if z["menge"] % 1 else 0)} {h(z["einheit"])}' if zg.get("anzahl") else ""
            ep = betrag(z["ep"]) if preise and zg.get("ep") else ""
            gp = ""
            if preise and zg.get("gp", 1):
                gp = betrag(z["gp"], klammer=not z.get("zaehlt", True) and not z.get("info"))
            elif preise and not z.get("zaehlt", True) and zg.get("ep"):
                gp = "<small>Bedarfsposition</small>"
            hinweis = ("" if z.get("zaehlt", True) or z.get("info") or ist_text or not preise else
                       '<div class="klein">Alternativposition, nicht in der Summe enthalten</div>' if z.get("alternativ") else
                       '<div class="klein">Bedarfs-/Alternativposition, nicht in der Summe enthalten</div>')
            gruppen_start.append(titel_vorher if titel_vorher is not None else len(rows))
            titel_vorher = None
            rows.append(f'<tr class="pos{" textpos" if ist_text else ""}"><td>{h(z["posnr"]) if zg.get("posnr") else ""}{'<div class="alt">ALT</div>' if z.get("alternativ") else ""}</td><td class="r nw">{menge}</td>'
                        f'<td>{text_html(z["text"], not ist_text)}{hinweis}</td><td class="r nw">{ep}</td><td class="r nw">{gp}</td></tr>')
            pos_bilder = bilder_html(z.get("bilder")) if dr.get("bilder", True) else ""
            if z.get("unter") and z.get("unterdruck") != "verdeckt":
                for u in z["unter"]:
                    um = f'{de(u["menge"], 2 if u["menge"] % 1 else 0)} {h(u["einheit"])}' if z["unterdruck"] != "text" else ""
                    mit_preis = z["unterdruck"] == "beleg" and preise
                    rows.append(f'<tr class="unter"><td>{h(z["posnr"])}.{h(u["posnr"])}</td><td class="r nw">{um}</td><td>{text_html(u["text"])}</td>'
                                f'<td class="r nw">{"<small>" + betrag(u["ep"]) + "</small>" if mit_preis else ""}</td>'
                                f'<td class="r nw">{"<small>(" + betrag(u["gp"]) + ")</small>" if mit_preis else ""}</td></tr>')
                    rows.append(bilder_html(u.get("bilder")))
            rows.append(pos_bilder)
    zusammen_html = ""
    if zusammen:
        titel_namen = {str(z["nr"]): z for z in d.get("zeilen", []) if z["typ"] == "titel"}
        zz = "".join(f'<tr><td>{h(z["name"])}{" <small>(nicht in der Summe)</small>" if titel_namen.get(str(z["nr"]), {}).get("gesperrt") else ""}</td>'
                     f'<td class="r nw">{betrag(z["summe"], klammer=bool(titel_namen.get(str(z["nr"]), {}).get("gesperrt")))} €</td></tr>' for z in zusammen)
        zusammen_html = (f'<div class="zusammen"><div class="zs-kopf">Zusammenstellung</div><table>{zz}'
                         f'<tr class="zs-summe"><td>Summe {"brutto" if brutto else "netto"}</td><td class="r nw">{de(s.get("netto_positionen", 0) * faktor)} €</td></tr></table></div>')
    summe_html = ""
    if preise and dr.get("summen") == "netto":
        summe_html = f'<table class="summen"><tr><td><b>Summe netto</b></td><td class="r nw"><b>{de(s.get("netto", 0))} €</b></td></tr></table>'
    elif preise and dr.get("summen") != "nein":
        sz = []
        if brutto:
            if s.get("rabatt"):
                sz.append(("Summe Positionen brutto", de(s["netto_positionen"] * faktor)))
                sz.append((f"abzüglich {de(s['rabatt_pz'], 2 if s['rabatt_pz'] % 1 else 0)} % Rabatt", "-" + de(s["rabatt"] * faktor)))
            sz.append(("<b>Gesamtbetrag</b>", f"<b>{de(s['brutto'])} €</b>"))
            sz.append((f"darin enthalten {de(s['ust_satz'], 0)} % USt", f"{de(s['ust'])} €"))
            sz.append(("Nettobetrag", f"{de(s['netto'])} €"))
        else:
            if s.get("rabatt"):
                sz.append(("Summe Positionen", f"{de(s['netto_positionen'])} €"))
                sz.append((f"abzüglich {de(s['rabatt_pz'], 2 if s['rabatt_pz'] % 1 else 0)} % Rabatt", f"-{de(s['rabatt'])} €"))
            sz.append(("Nettobetrag", f"{de(s['netto'])} €"))
            if d.get("steuer") == "13b":
                sz.append(("Umsatzsteuer: Steuerschuldnerschaft des Leistungsempfängers (§ 13b UStG)", "–"))
            else:
                sz.append((f"zuzüglich {de(s['ust_satz'], 0)} % USt", f"{de(s['ust'])} €"))
            sz.append(("<b>Gesamtbetrag</b>", f"<b>{de(s['brutto'])} €</b>"))
        for x in d.get("abzuege", []):
            sz.append((f"abzüglich Abschlagsrechnung {h(x['nummer'])} vom {de_datum(x['datum'])}<br><small>netto {de(x['netto'])} € + USt {de(x['ust'])} €</small>",
                       f"-{de(x['brutto'])} €"))
        if d.get("abzuege"):
            sz.append(("<b>Verbleibender Zahlbetrag</b>", f"<b>{de(s['zahlbetrag'])} €</b>"))
        summe_html = '<table class="summen">' + "".join(f'<tr><td>{l}</td><td class="r nw">{v}</td></tr>' for l, v in sz) + "</table>"
    zahlung = ""
    if not rechnung and dr.get("konditionen") == "plan":
        zahlung = zahlungsplan_text(e, dr, s)
    elif not rechnung and dr.get("konditionen"):
        ziel = int(fl(ku.get("zahlungsziel") or 14))
        zahlung = f"Zahlungsbedingungen: zahlbar innerhalb von {ziel} Tagen nach Rechnungsdatum ohne Abzug"
        if ku.get("skonto") and ku.get("skontotage"):
            zahlung += f", bei Zahlung innerhalb von {ku['skontotage']} Tagen mit {de(ku['skonto'], 2 if ku['skonto'] % 1 else 0)} % Skonto"
        zahlung += "."
    if rechnung and b["art"] != "storno" and s.get("zahlbetrag", 0) > 0 and dr.get("konditionen", True):
        zb = s["zahlbetrag"]
        faellig = de_datum(b["faellig"]) if b["faellig"] else f"innerhalb von {b['zahlungsziel']} Tagen"
        zahlung = f"Bitte überweisen Sie den Betrag von {de(zb)} € bis zum {faellig} ohne Abzug"
        if ku.get("skonto") and ku.get("skontotage"):
            sk_bis = de_datum(plus_tage(b["datum"], ku["skontotage"])) if b["datum"] else f"{ku['skontotage']} Tage"
            zahlung += f" oder bis zum {sk_bis} abzüglich {de(ku['skonto'], 2 if ku['skonto'] % 1 else 0)} % Skonto ({de(zb * (1 - ku['skonto'] / 100))} €)"
        zahlung += f" unter Angabe der Rechnungsnummer {h(b['nummer'] or '…')}."
        if fi.get("sepa_iban"):
            zahlung += f"<br>Bankverbindung: {h(fi.get('bank_name') or '')} IBAN {h(ibanFormat_py(fi['sepa_iban']))}{' · BIC ' + h(fi['sepa_bic']) if fi.get('sepa_bic') else ''}"
            if e.get("girocode", True) and dr.get("qr", True):
                try:
                    qr = erechnung.girocode_svg(fi.get("firma"), fi["sepa_iban"], fi.get("sepa_bic"), zb,
                                                f"{b['artname']} {b['nummer'] or ''} Kd {ku.get('nummer') or ''}".strip())
                    zahlung = (f'<div class="zahl-text">{zahlung}</div><div class="girocode">{qr}'
                               f'<div>GiroCode<br>mit der Banking-App scannen</div></div>')
                except Exception as f:  # noqa: BLE001
                    print("GiroCode nicht möglich:", f)
    p14 = ""
    if rechnung and b["art"] not in ("storno", "gutschrift") and ku.get("gruppe") == "Privatkunde" and e.get("hinweis_14b", True):
        p14 = f'<p class="klein">{h(e.get("text_14b") or HINWEIS_14B)}</p>'
    if d.get("steuer") == "13b":   # Pflichtangabe nach § 14a Abs. 5 UStG
        p14 = f'<p class="hinweis13b" style="margin:3mm 0;font-weight:600">{h(HINWEIS_13B)}{" USt-IdNr. des Leistungsempfängers: " + h(ku["ustid"]) if ku.get("ustid") else ""}</p>' + p14
    zusatz = f'<p class="klein">{text_html(e.get("rechnung_zusatz"), False)}</p>' if rechnung and b["art"] not in ("storno", "gutschrift") and e.get("rechnung_zusatz") else ""
    # Arbeitskosten nach § 35a EStG als Satz unter dem Schlusstext (Rechnung/Schlussrechnung)
    lohn_satz = ""
    la = d.get("lohnanteil") or {}
    regel = e.get("lohnanteil", "privat")
    vorgabe_la = regel == "alle" or (regel == "privat" and ku.get("gruppe") == "Privatkunde")
    if b["art"] == "rechnung" and regel != "nie" and la.get("netto", 0) > 0.004 and dr.get("lohnanteil", vorgabe_la):
        t = (e.get("text_lohnanteil") or STANDARD_EINSTELLUNGEN["text_lohnanteil"])
        t = t.replace("{lohn_netto}", de(la["netto"])).replace("{lohn_ust}", de(la["ust"])).replace("{lohn_brutto}", de(la["brutto"]))
        lohn_satz = f'<p class="lohnanteil" style="margin:3mm 0">{h(t)}</p>'
    nr_druck = b["nummer"] or ""
    if dr.get("nummer") == "kurz":
        nr_druck = re.sub(r"^\d{4}-", "", nr_druck)
    elif dr.get("nummer") == "nein":
        nr_druck = ""
    info = [(f"{b['artname']}-Nr.", nr_druck or ("Entwurf" if rechnung else "")), ("Datum", de_datum(b["datum"])),
            ("Kunden-Nr.", ku.get("nummer")), ("Auftrag", d.get("auftrag", {}).get("nummer"))]
    if rechnung and b["leistungsdatum"]:
        info.append(("Leistungsdatum", de_datum(b["leistungsdatum"])))
    if ku.get("ustid"):
        info.append(("Ihre USt-IdNr.", ku["ustid"]))
    if ku.get("leitweg_id"):
        info.append(("Leitweg-ID", ku["leitweg_id"]))
    au = d.get("auftrag", {})
    if b["art"] in ("angebot", "kv", "ab") and au.get("plan_von") and e.get("zeitraum_drucken", True):
        kw_v, kw_b = date.fromisoformat(au["plan_von"]).isocalendar(), date.fromisoformat(au.get("plan_bis") or au["plan_von"]).isocalendar()
        kw_text = f"KW {kw_v[1]}" + (f"–{kw_b[1]}" if kw_b[1] != kw_v[1] or kw_b[0] != kw_v[0] else "") + f"/{kw_b[0]}"
        wochen = fl(dr.get("plan_wochen")) if dr.get("konditionen") == "plan" and fl(dr.get("plan_anzahlung")) else 0
        if wochen > 0:
            # Zahlungsplan mit Lieferzeit ab Anzahlung: der Termin gilt nur, wenn die Anzahlung rechtzeitig eingeht
            stichtag = date.fromisoformat(au["plan_von"]) - timedelta(days=round(wochen * 7))
            if not b.get("datum") or stichtag.isoformat() >= b["datum"]:
                info.append(("Ausführung ca.", kw_text))
                info.append(("bei Anzahlung bis", de_datum(stichtag.isoformat())))
            # liegt der Stichtag vor dem Belegdatum, ist der Termin nicht mehr zu halten: dann gilt nur die Lieferzeit ab Anzahlung
        else:
            info.append(("Ausführung ca.", kw_text))
    if d.get("bezug"):
        info.append(("zu Rechnung", d["bezug"]["nummer"]))
    entwurf = b["status"] == "entwurf" and rechnung
    info_html = "".join(f"<tr><td>{h(l)}</td><td>{h(v)}</td></tr>" for l, v in info if v)
    anschrift_html = h(b["anschrift"]).replace(chr(10), "<br>")
    colgroup = '<colgroup><col style="width:11mm"><col style="width:20mm"><col><col style="width:24mm"><col style="width:26mm"></colgroup>'
    # Letzte Position zusammen mit den Summen auf einer Seite halten
    ende_ab, ende_block_start, ende_block_ende = len(rows), "", ""
    if dr.get("zusammen", True) and gruppen_start and (summe_html or zusammen_html):
        ende_ab = gruppen_start[-1]
        ende_block_start = (f'<div style="break-inside: avoid; page-break-inside: avoid;"><table class="pos pos-ende">{colgroup}'
                            f'<tbody>{"".join(rows[ende_ab:])}</tbody></table>')
        ende_block_ende = "</div>"
    kopfzeile = (f'<thead><tr><th>Pos.</th><th class="r">Menge</th><th>Bezeichnung</th><th class="r">{"Einzelpreis" if preise else ""}</th>'
                 f'<th class="r">{"Gesamt " + ("brutto" if brutto else "netto") if preise else ""}</th></tr></thead>')
    if ende_block_start and ende_ab == 0:
        tabelle_oben = ""
        ende_block_start = ende_block_start.replace(f'{colgroup}<tbody>', f'{colgroup}{kopfzeile}<tbody>', 1)
    else:
        tabelle_oben = f'<table class="pos{" geteilt" if ende_block_start else ""}">{colgroup}{kopfzeile}<tbody>{"".join(rows[:ende_ab])}</tbody></table>'
    inhalt = f"""
<h1>{h(b["artname"])} {h(nr_druck)}</h1>
<div class="betreff">{h(b["betreff"])}</div>
{f'<div class="einl rt">{rich_html(text_einsetzen(b["einleitung"], beleg_platzhalter(b)))}</div>' if dr.get("anrede", True) else ""}
{tabelle_oben}
{ende_block_start}
{'<style>table.pos tr.pos, table.pos tr.unter { page-break-inside: auto !important; break-inside: auto !important; } table.pos td { padding-top: 1.4mm; padding-bottom: 1.4mm; }</style>' if b.get("kompakt") else ''}
{f'<div class="ub-abstand" style="height:{abstand:.2f}mm"></div>' if abstand > 0 else ''}{UB_MARKE.format("JRUBANFANG") if marken else ''}
{zusammen_html}
{summe_html}
{ende_block_ende}
{f'<div class="zahlung">{zahlung}</div>' if zahlung else ''}
{lohn_satz}
{p14}
{unterschrift_html(b, "abnahme") if b["art"] == "abnahme" else ""}
{f'''<div class="ende"><div class="schluss rt">{rich_html(schluss_ohne_linie(b, text_einsetzen(b["schluss"], beleg_platzhalter(b))))}</div>
{"" if b["daten"].get("unterschrift") else gruss_html(fi.get("firma_inhaber") or fi.get("firma"), dr.get("unterschrift", True), fi.get("unterschrift_hoehe") if b["status"] in ("fest", "storniert") else e.get("unterschrift_hoehe"))}</div>''' if dr.get("anrede", True) else ""}
{unterschrift_html(b, "signatur") if b["daten"].get("unterschrift") else ""}
{zusatz}
{UB_MARKE.format("JRUBENDE") if marken else ''}
{'<style>.bg-folge img, .bg-erste img, .kopf > *, .fuss {{ visibility: hidden; }}</style>' if not dr.get("briefbogen", True) else ''}"""
    # AGB anhängen?
    agb_seiten = beleg_agb_seiten(e, b, ku)
    if als_pdf and agb_original(beleg_agb_art(e, b, ku)):
        agb_seiten = []   # im PDF wird das Original-AGB-PDF angehängt (klein und gestochen scharf)
    agb_html = "".join(f'<div class="agb"><img class="voll" src="{u}"></div>' for u in agb_seiten)
    return briefbogen_html(e, fi, beleg_titel(b), anschrift_html, info_html, inhalt, als_pdf, entwurf=entwurf, agb_html=agb_html)


def briefbogen_html(e, fi, titel, anschrift_html, info_html, inhalt, als_pdf, entwurf=False, agb_html=""):
    """Seitenrahmen auf dem Briefbogen (Vorlage) oder mit einfachem Kopf/Fuß – für Belege, Mahnungen usw."""
    logo = os.path.exists(os.path.join(DATEN, "logo.png")) or os.path.exists(os.path.join(DATEN, "logo.jpg"))
    absender = fi.get("absenderzeile") or " · ".join(x for x in [fi.get("firma")] + (fi.get("firma_anschrift") or "").split("\n") if x)
    fuss = [
        "<br>".join(h(x) for x in [fi.get("firma"), fi.get("firma_inhaber")] + (fi.get("firma_anschrift") or "").split("\n") if x),
        "<br>".join(x for x in [f"Tel. {h(fi['firma_telefon'])}" if fi.get("firma_telefon") else "", h(fi.get("firma_email")), h(fi.get("firma_web"))] if x),
        "<br>".join(x for x in [h(fi.get("bank_name")), f"IBAN {h(ibanFormat_py(fi['sepa_iban']))}" if fi.get("sepa_iban") else "",
                                f"BIC {h(fi['sepa_bic'])}" if fi.get("sepa_bic") else ""] if x),
        "<br>".join(x for x in [f"Steuernummer {h(fi['steuernummer'])}" if fi.get("steuernummer") else "",
                                f"USt-IdNr. {h(fi['ustid'])}" if fi.get("ustid") else "", h(fi.get("firma_zusatz"))] if x),
    ]
    brief = vorlage_dateien("brief") if e.get("briefvorlage_aktiv", True) else []
    titel_html = f'<!doctype html><html lang="de"><head><meta charset="utf-8"><title>{h(titel)}</title>'
    druck_js = '' if als_pdf else '<script>if(location.search.includes("drucken"))window.print()</script>'

    if brief:
        L = {**STANDARD_EINSTELLUNGEN["brief_layout"], **(e.get("brief_layout") or {})}
        erste, folge = f"/api/vorlage/{brief[0]}", f"/api/vorlage/{brief[1] if len(brief) > 1 else brief[0]}"
        bildschirm = "" if als_pdf else """
html{background:#888} body{width:210mm;margin:10mm auto;background:#fff;box-shadow:0 2px 12px rgba(0,0,0,.3);position:relative}
.bg-folge{display:none} .agb{margin-top:10mm;box-shadow:0 2px 12px rgba(0,0,0,.3)}"""
        return f"""{titel_html}
<style>
@page {{ size: A4; margin: 0; }}
body {{ font: 10pt/1.38 Calibri, "Segoe UI", Arial, sans-serif; color: #222; margin: 0; }}
{BELEG_CSS}
.bg-folge {{ position: fixed; top: 0; left: 0; width: 210mm; height: 297mm; z-index: 0; }}
.bg-erste {{ position: absolute; top: 0; left: 0; width: 210mm; height: 297mm; background: #fff; z-index: 1; }}
img.voll {{ width: 100%; height: 100%; display: block; }}
table.seite {{ position: relative; z-index: 2; width: 100%; border-collapse: collapse; }}
table.seite > thead td {{ height: {L["oben"]}mm; padding: 0; }}
table.seite > tfoot td {{ height: {L["unten"]}mm; padding: 0; }}
table.seite > tbody > tr > td {{ padding: 0 {L["rechts"]}mm 0 {L["links"]}mm; }}
.bb-kopf {{ position: relative; height: {max(0, L["inhalt_start"] - L["oben"])}mm; }}
.bb-adresse {{ position: absolute; top: {L["adresse_oben"] - L["oben"]}mm; left: 0; width: 85mm; font-size: 10.5pt; line-height: 1.35; }}
.bb-info {{ position: absolute; top: {L["info_oben"] - L["oben"]}mm; left: {L["info_links"] - L["links"]}mm; }}
.agb {{ break-before: page; position: relative; z-index: 3; width: 210mm; height: 297mm; background: #fff; }}
{bildschirm}
</style></head><body>
{'<div class="wasser">ENTWURF</div>' if entwurf else ''}
<div class="bg-folge"><img class="voll" src="{folge}"></div>
<div class="bg-erste"><img class="voll" src="{erste}"></div>
<table class="seite"><thead><tr><td></td></tr></thead><tfoot><tr><td></td></tr></tfoot><tbody><tr><td>
<div class="bb-kopf"><div class="bb-adresse">{anschrift_html}</div><table class="info bb-info">{info_html}</table></div>
{inhalt}
</td></tr></tbody></table>
{agb_html}
{druck_js}
</body></html>"""

    return f"""{titel_html}
<style>
@page {{ size: A4; margin: 12mm 18mm 10mm 24mm; }}
@page agb {{ margin: 0; }}
body {{ font: 10pt/1.38 "Segoe UI", Arial, sans-serif; color: #222; margin: 0; }}
{BELEG_CSS}
{'' if als_pdf else 'html{background:#888} body{background:#fff;width:210mm;margin:10mm auto;padding:12mm 18mm 10mm 24mm;box-shadow:0 2px 12px rgba(0,0,0,.3)} .fuss{position:static!important;margin-top:20mm}'}
table.seite {{ width: 100%; border-collapse: collapse; }}
table.seite > thead td, table.seite > tfoot td {{ padding: 0; }}
.fussplatz {{ height: 22mm; }}
.fuss {{ position: fixed; bottom: 0; left: 0; right: 0; display: grid; grid-template-columns: repeat(4, 1fr); gap: 4mm; font-size: 7pt; color: #555; border-top: .3pt solid #999; padding-top: 2mm; }}
.kopf {{ display: flex; justify-content: space-between; align-items: flex-start; min-height: 30mm; }}
.kopf .logo img {{ max-height: 26mm; max-width: 70mm; }}
.kopf .firmenname {{ font-size: 15pt; font-weight: 600; letter-spacing: .3pt; text-align: right; }}
.adresse {{ display: flex; justify-content: space-between; align-items: flex-start; margin-top: 6mm; min-height: 45mm; }}
.empf {{ width: 85mm; }}
.absender {{ font-size: 7pt; color: #555; border-bottom: .3pt solid #999; padding-bottom: 1mm; margin-bottom: 3mm; white-space: nowrap; overflow: hidden; }}
.empf .anschrift {{ font-size: 10.5pt; line-height: 1.35; }}
.agb {{ page: agb; break-before: page; position: relative; z-index: 3; width: 210mm; height: 297mm; background: #fff; }}
img.voll {{ width: 100%; height: 100%; display: block; }}
</style></head><body>
{'<div class="wasser">ENTWURF</div>' if entwurf else ''}
<table class="seite"><tfoot><tr><td><div class="fussplatz"></div></td></tr></tfoot><tbody><tr><td>
<div class="kopf"><div></div>{'<div class="logo"><img src="/api/logo"></div>' if logo else f'<div class="firmenname">{h(fi.get("firma"))}</div>'}</div>
<div class="adresse">
  <div class="empf"><div class="absender">{h(absender)}</div><div class="anschrift">{anschrift_html}</div></div>
  <table class="info">{info_html}</table>
</div>
{inhalt}
</td></tr></tbody></table>
<div class="fuss">{"".join(f"<div>{x}</div>" for x in fuss)}</div>
{agb_html}
{druck_js}
</body></html>"""


def op_liste(con, q):
    sql = ("SELECT o.*, k.kurzname AS kunde, a.nummer AS auftragsnr, b.art AS belegart, b.status AS belegstatus, "
           "(SELECT s.nummer FROM belege s WHERE s.bezug_id=o.beleg_id AND s.art='storno' ORDER BY s.id DESC LIMIT 1) AS storno_nr, "
           "(SELECT r.nummer FROM belege r WHERE r.id=b.bezug_id) AS bezug_nr FROM offene_posten o "
           "LEFT JOIN kunden k ON k.id=o.kunde_id LEFT JOIN auftraege a ON a.id=o.auftrag_id "
           "LEFT JOIN belege b ON b.id=o.beleg_id WHERE 1=1")
    p = []
    if q.get("kunde"):
        sql += " AND o.kunde_id=?"
        p.append(int(q["kunde"]))
    if q.get("auftrag"):
        sql += " AND o.auftrag_id=?"
        p.append(int(q["auftrag"]))
    st = q.get("status", "offen")
    if st == "offen":
        sql += " AND (ABS(o.offen) >= 0.005 OR IFNULL(o.mahnkosten,0) >= 0.005)"
    elif st == "faellig":
        sql += " AND o.offen >= 0.005 AND o.faellig < ?"
        p.append(date.today().isoformat())
    elif st == "erledigt":
        sql += (" AND ABS(o.offen) < 0.005 AND IFNULL(o.mahnkosten,0) < 0.005 AND IFNULL(b.status,'')<>'storniert' "
                "AND IFNULL(b.art,'')<>'storno'")
    elif st == "storniert":
        sql += " AND (b.status='storniert' OR b.art='storno')"
    liste = zeilen(con.execute(sql + " ORDER BY o.faellig, o.id", p))
    mahn_ergaenzen(con, liste)
    return liste


def mahn_ergaenzen(con, liste):
    """Hängt an offene Posten die letzte Mahnung und den Mahnvorschlag (nächste Stufe, ab wann) an."""
    if not liste:
        return liste
    cfg = mahnwesen.einstellung(einstellungen(con))
    letzte = {}
    for m in con.execute("SELECT id, op_id, stufe, datum, frist, gesamt, versendet FROM mahnungen ORDER BY datum, id"):
        letzte[m["op_id"]] = dict(m)
    heute_d = date.today()
    for o in liste:
        lm = letzte.get(o["id"])
        if lm:
            lm["kz"] = cfg["stufen"][min(lm["stufe"], len(cfg["stufen"]) - 1)]["kz"]
            lm["name"] = cfg["stufen"][min(lm["stufe"], len(cfg["stufen"]) - 1)]["name"]
        o["letzte_mahnung"] = lm
        o["mahnvorschlag"] = mahnwesen.vorschlag(o, lm, cfg["stufen"], heute_d) if o.get("art") != "Storno" else None
        o["ueberfaellig_tage"] = (heute_d - date.fromisoformat(o["faellig"][:10])).days if o.get("faellig") and o["offen"] >= 0.005 else 0
    return liste



# ====================== Mahnwesen ======================
def op_laden(con, opid):
    op = con.execute("SELECT * FROM offene_posten WHERE id=?", (opid,)).fetchone()
    if not op:
        raise ApiFehler("Offener Posten nicht gefunden", 404)
    return dict(op)


def op_kunde(con, op):
    """Kundendaten zum offenen Posten: die Kopie im Auftrag, sonst der Kundenstamm."""
    if op.get("auftrag_id"):
        try:
            return auftrag_kunde(con, op["auftrag_id"])
        except ApiFehler:
            pass
    r = con.execute("SELECT * FROM kunden WHERE id=?", (op.get("kunde_id"),)).fetchone()
    return dict(r) if r else {}


def ist_unternehmer(e, k):
    return (k.get("gruppe") or "") not in (e.get("agb_verbraucher_gruppen") or ["Privatkunde"])


def mahn_bisher(con, opid):
    return zeilen(con.execute("SELECT * FROM mahnungen WHERE op_id=? ORDER BY datum, id", (opid,)))


def mahn_werte(op, k, betr, datum_iso, frist_iso, bisher, stufe_cfg, e, auftrag_bez=""):
    return {"anrede": anrede_aufloesen(k), "nummer": op.get("nummer") or "",
            "datum": de_datum(op.get("datum")), "faellig": de_datum(op.get("faellig")), "betrag": de(op.get("betrag") or 0),
            "offen": de(betr["offen"]), "zahlbetrag": de(betr["gesamt"]), "gebuehr": de(betr["gebuehr"]),
            "frist": de_datum(frist_iso), "heute": de_datum(datum_iso), "name": stufe_cfg["name"],
            "letzte_mahnung": de_datum(bisher[-1]["datum"]) if bisher else de_datum(op.get("faellig")),
            "auftrag": auftrag_bez, "firma": e.get("firma") or "", "inhaber": e.get("firma_inhaber") or ""}


def mahnung_vorschlag(con, opid, q):
    """Vorschlag für eine neue Mahnung (Stufe, Frist, Beträge, Texte) – für den Erstellen-Dialog."""
    op = op_laden(con, opid)
    mahn_ergaenzen(con, [op])
    e = einstellungen(con)
    cfg = mahnwesen.einstellung(e)
    bisher = mahn_bisher(con, opid)
    if q.get("stufe") not in (None, ""):
        stufe = max(0, min(int(q["stufe"]), len(cfg["stufen"]) - 1))
    else:
        vs = op.get("mahnvorschlag") or {}
        stufe = vs.get("stufe") if vs.get("stufe") is not None else min(len(bisher), len(cfg["stufen"]) - 1)
    sc = cfg["stufen"][stufe]
    datum_iso = q.get("datum") or date.today().isoformat()
    frist_iso = plus_tage(datum_iso, int(sc.get("frist") or 0))
    k = op_kunde(con, op)
    unternehmer = ist_unternehmer(e, k)
    ja = lambda x: None if x in (None, "") else x == "1"  # noqa: E731
    betr = mahnwesen.berechnen(op, bisher, sc, datum_iso, cfg, unternehmer, mit_zinsen=ja(q.get("zinsen")),
                               gebuehr=None if q.get("gebuehr") in (None, "") else zahl(q["gebuehr"], float),
                               mit_pauschale=ja(q.get("pauschale")))
    a = con.execute("SELECT bezeichnung FROM auftraege WHERE id=?", (op.get("auftrag_id"),)).fetchone()
    werte = mahn_werte(op, k, betr, datum_iso, frist_iso, bisher, sc, e, a["bezeichnung"] if a else "")
    return {"op": op, "stufe": stufe, "stufen": [{"kz": s["kz"], "name": s["name"]} for s in cfg["stufen"]],
            "datum": datum_iso, "frist": frist_iso, **betr, "betreff": text_einsetzen(sc["betreff"], werte),
            "text": text_einsetzen(sc["text"], werte), "schluss": text_einsetzen(sc.get("schluss") or "", werte),
            "mit_zinsen": betr["zinstage"] > 0 or (ja(q.get("zinsen")) if q.get("zinsen") not in (None, "") else bool(sc.get("zinsen"))),
            "mit_pauschale": betr["pauschale"] > 0, "unternehmer": unternehmer, "basiszins": cfg["basiszins"],
            "kunde": k.get("kurzname") or "", "bisher": [{"kz": cfg["stufen"][min(m["stufe"], 2)]["kz"], "datum": m["datum"]} for m in bisher]}


def mahnung_erstellen(con, opid, d):
    op = op_laden(con, opid)
    if (op["offen"] or 0) < 0.005:
        raise ApiFehler("Dieser Posten ist schon bezahlt.")
    e = einstellungen(con)
    cfg = mahnwesen.einstellung(e)
    stufe = max(0, min(int(zahl(d.get("stufe"), int) or 0), len(cfg["stufen"]) - 1))
    sc = cfg["stufen"][stufe]
    datum_iso = d.get("datum") or date.today().isoformat()
    frist_iso = d.get("frist") or plus_tage(datum_iso, int(sc.get("frist") or 0))
    if frist_iso < datum_iso:
        raise ApiFehler("Die Zahlungsfrist liegt vor dem Mahndatum.")
    bisher = mahn_bisher(con, opid)
    k = op_kunde(con, op)
    unternehmer = ist_unternehmer(e, k)
    betr = mahnwesen.berechnen(op, bisher, sc, datum_iso, cfg, unternehmer, mit_zinsen=bool(d.get("zinsen")),
                               gebuehr=zahl(d.get("gebuehr"), float), mit_pauschale=bool(d.get("pauschale")))
    a = con.execute("SELECT nummer, bezeichnung FROM auftraege WHERE id=?", (op.get("auftrag_id"),)).fetchone()
    nummer = f"{op['nummer']}-{sc['kz']}"
    n = 2
    while con.execute("SELECT 1 FROM mahnungen WHERE nummer=?", (nummer,)).fetchone():
        nummer = f"{op['nummer']}-{sc['kz']}-{n}"
        n += 1
    daten = {"stufenname": sc["name"], "kz": sc["kz"], "firma": firma_daten(e),
             "kunde": {x: k.get(x) for x in ("nummer", "kurzname", "anrede", "gruppe", "email1", "email2")},
             "rechnung": {x: op.get(x) for x in ("nummer", "datum", "betrag", "faellig", "beleg_id")},
             "auftrag": {"nummer": a["nummer"] if a else "", "bezeichnung": a["bezeichnung"] if a else ""},
             "vorherige": [{"name": cfg["stufen"][min(m["stufe"], 2)]["name"], "datum": m["datum"]} for m in bisher]}
    cur = con.execute(
        "INSERT INTO mahnungen (op_id, kunde_id, auftrag_id, stufe, nummer, datum, frist, offen, kosten_bisher, gebuehr, zinsen, zinstage, "
        "zinssatz, pauschale, gesamt, anschrift, betreff, text, schluss, daten, angelegt) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (opid, op["kunde_id"], op["auftrag_id"], stufe, nummer, datum_iso, frist_iso, betr["offen"], betr["kosten_bisher"], betr["gebuehr"],
         betr["zinsen"], betr["zinstage"], betr["zinssatz"], betr["pauschale"], betr["gesamt"], kunde_block(k),
         d.get("betreff") or sc["name"], d.get("text") or "", d.get("schluss") or "", json.dumps(daten, ensure_ascii=False), jetzt()))
    mid = cur.lastrowid
    neue_kosten = round(betr["gebuehr"] + betr["zinsen"] + betr["pauschale"], 2)
    con.execute("UPDATE offene_posten SET mahnstufe=?, mahnkosten=ROUND(IFNULL(mahnkosten,0)+?,2) WHERE id=?", (stufe + 1, neue_kosten, opid))
    con.execute("INSERT INTO notizen (kunde_id, auftrag_id, text, angelegt) VALUES (?,?,?,?)",
                (op["kunde_id"], op["auftrag_id"], f"{sc['name']} {nummer} zu Rechnung {op['nummer']} erstellt: "
                 f"{de(betr['gesamt'])} € bis {de_datum(frist_iso)}", jetzt()))
    ergebnis = {"id": mid, "nummer": nummer}
    try:
        pfad = mahnung_pdf(con, mid)
        ergebnis["pdf"] = os.path.basename(pfad)
        ergebnis["projekt"] = (mahnung_laden(con, mid)["daten"].get("projekt_rel") or "")
    except ApiFehler as f:
        ergebnis["hinweis"] = str(f)
    return ergebnis


def mahnung_laden(con, mid):
    m = con.execute("SELECT * FROM mahnungen WHERE id=?", (mid,)).fetchone()
    if not m:
        raise ApiFehler("Mahnung nicht gefunden", 404)
    m = dict(m)
    m["daten"] = jl(m["daten"], {})
    return m


def mahnungen_liste(con, q):
    cfg = mahnwesen.einstellung(einstellungen(con))
    sql = ("SELECT m.id, m.op_id, m.kunde_id, m.auftrag_id, m.stufe, m.nummer, m.datum, m.frist, m.gesamt, m.gebuehr, m.zinsen, "
           "m.pauschale, m.versendet, m.versendet_an, m.pdf, k.kurzname AS kunde, a.nummer AS auftragsnr, o.nummer AS rechnung, "
           "o.offen AS op_offen, o.beleg_id, (SELECT MAX(m2.id) FROM mahnungen m2 WHERE m2.op_id=m.op_id) AS letzte_id FROM mahnungen m "
           "LEFT JOIN kunden k ON k.id=m.kunde_id LEFT JOIN auftraege a ON a.id=m.auftrag_id LEFT JOIN offene_posten o ON o.id=m.op_id WHERE 1=1")
    p = []
    for feld, spalte in (("op", "m.op_id"), ("kunde", "m.kunde_id"), ("auftrag", "m.auftrag_id")):
        if q.get(feld):
            sql += f" AND {spalte}=?"
            p.append(int(q[feld]))
    sql += " ORDER BY m.datum DESC, m.id DESC"
    if q.get("limit"):
        sql += f" LIMIT {int(q['limit'])}"
    liste = zeilen(con.execute(sql, p))
    for m in liste:
        sc = cfg["stufen"][min(m["stufe"], len(cfg["stufen"]) - 1)]
        m["kz"], m["name"], m["letzte"] = sc["kz"], sc["name"], m["id"] == m["letzte_id"]
    return liste


def mahn_zahlung_html(e, fi, m, ku):
    if not fi.get("sepa_iban"):
        return f'<div class="zahlung">Bitte überweisen Sie {de(m["gesamt"])} € bis zum {de_datum(m["frist"])}.</div>'
    r = (m["daten"].get("rechnung") or {})
    text = (f"Bitte überweisen Sie {de(m['gesamt'])} € bis zum {de_datum(m['frist'])} unter Angabe der Rechnungsnummer "
            f"{h(r.get('nummer') or '')}.<br>Bankverbindung: {h(fi.get('bank_name') or '')} IBAN {h(ibanFormat_py(fi['sepa_iban']))}"
            f"{' · BIC ' + h(fi['sepa_bic']) if fi.get('sepa_bic') else ''}")
    if e.get("girocode", True) and m["gesamt"] > 0:
        try:
            qr = erechnung.girocode_svg(fi.get("firma"), fi["sepa_iban"], fi.get("sepa_bic"), m["gesamt"],
                                        f"Rechnung {r.get('nummer') or ''} Kd {ku.get('nummer') or ''}".strip())
            return (f'<div class="zahlung"><div class="zahl-text">{text}</div><div class="girocode">{qr}'
                    f'<div>GiroCode<br>mit der Banking-App scannen</div></div></div>')
        except Exception as f:  # noqa: BLE001
            print("GiroCode nicht möglich:", f)
    return f'<div class="zahlung">{text}</div>'


def mahnung_html(con, mid, als_pdf=False):
    m = mahnung_laden(con, mid)
    d = m["daten"]
    e = einstellungen(con)
    fi = d.get("firma") or firma_daten(e)
    ku = d.get("kunde") or {}
    r = d.get("rechnung") or {}
    info = [("Datum", de_datum(m["datum"])), ("Kunden-Nr.", ku.get("nummer")), ("Rechnung-Nr.", r.get("nummer")),
            ("Rechnungsdatum", de_datum(r.get("datum"))), ("Auftrag", (d.get("auftrag") or {}).get("nummer"))]
    info_html = "".join(f"<tr><td>{h(l)}</td><td>{h(v)}</td></tr>" for l, v in info if v)
    hilfe = {"h": h, "de": de, "de_datum": de_datum, "text_html": text_html, "gruss": fi.get("firma_inhaber") or fi.get("firma"),
             "gruss_html": gruss_html(fi.get("firma_inhaber") or fi.get("firma"), hoehe=fi.get("unterschrift_hoehe", e.get("unterschrift_hoehe"))),
             "zahlung": mahn_zahlung_html(e, fi, m, ku)}
    inhalt = mahnwesen.inhalt_html(m, d, hilfe)
    return briefbogen_html(e, fi, f"{d.get('stufenname', 'Mahnung')} {m['nummer']}", h(m["anschrift"]).replace("\n", "<br>"),
                           info_html, inhalt, als_pdf)


def mahnung_pdf(con, mid):
    """PDF der Mahnung: Archiv in daten/mahnungen/<Jahr>, Kopie im Projektordner (bei den Rechnungen)."""
    m = mahnung_laden(con, mid)
    if m["pdf"] and os.path.exists(m["pdf"]):
        return m["pdf"]
    con.commit()
    d = m["daten"]
    e = einstellungen(con)
    name = sauber(f"{m['nummer']}_{d.get('stufenname', 'Mahnung')}_{(d.get('kunde') or {}).get('kurzname', '')}") + ".pdf"
    archiv = os.path.join(DATEN, "mahnungen", (m["datum"] or "")[:4] or "ohne-datum")
    os.makedirs(archiv, exist_ok=True)
    pfad = os.path.join(archiv, name)
    pdf_url_rendern(f"http://127.0.0.1:{PORT}/druck/mahnung/{mid}?pdf=1", pfad)
    if m["auftrag_id"]:
        ordner, _ = projektordner(con, m["auftrag_id"])
        if ordner:
            art = "mahnung" if (e.get("pdf_ordner") or {}).get("mahnung") else "rechnung"
            ziel = os.path.join(pdf_unterordner(ordner, art, e), name)
            try:
                shutil.copyfile(pfad, ziel)
                d["projekt"] = ziel
                d["projekt_rel"] = os.path.relpath(ziel, ordner).replace(os.sep, "/")
            except OSError as f:
                print("Mahnung nicht in den Projektordner kopiert:", f)
    con.execute("UPDATE mahnungen SET pdf=?, daten=? WHERE id=?", (pfad, json.dumps(d, ensure_ascii=False), mid))
    return pfad


def mahnung_loeschen(con, mid):
    m = mahnung_laden(con, mid)
    juengste = con.execute("SELECT MAX(id) FROM mahnungen WHERE op_id=?", (m["op_id"],)).fetchone()[0]
    if juengste != mid:
        raise ApiFehler("Es kann nur die jeweils letzte Mahnung eines Postens gelöscht werden.")
    kosten = round((m["gebuehr"] or 0) + (m["zinsen"] or 0) + (m["pauschale"] or 0), 2)
    con.execute("DELETE FROM mahnungen WHERE id=?", (mid,))
    vorige = con.execute("SELECT stufe FROM mahnungen WHERE op_id=? ORDER BY id DESC LIMIT 1", (m["op_id"],)).fetchone()
    con.execute("UPDATE offene_posten SET mahnstufe=?, mahnkosten=MAX(0, ROUND(IFNULL(mahnkosten,0)-?,2)) WHERE id=?",
                (vorige["stufe"] + 1 if vorige else 0, kosten, m["op_id"]))
    for pf in (m["pdf"], m["daten"].get("projekt")):
        if pf and os.path.exists(pf):
            in_papierkorb(pf)
    con.execute("INSERT INTO notizen (kunde_id, auftrag_id, text, angelegt) VALUES (?,?,?,?)",
                (m["kunde_id"], m["auftrag_id"], f"{m['daten'].get('stufenname', 'Mahnung')} {m['nummer']} gelöscht", jetzt()))
    prot(con, "mahnung_geloescht", m["nummer"], f"{m['daten'].get('stufenname', 'Mahnung')} {m['nummer']} vom {de_datum(m['datum'])} gelöscht (PDF in den Papierkorb verschoben)",
         {k: m[k] for k in ("id", "op_id", "stufe", "datum", "gebuehr", "zinsen", "pauschale", "pdf") if k in m})
    return {"ok": True}


def mahnung_mail_vorschlag(con, mid):
    m = mahnung_laden(con, mid)
    d = m["daten"]
    e = einstellungen(con)
    cfg = mahnwesen.einstellung(e)
    sc = cfg["stufen"][min(m["stufe"], len(cfg["stufen"]) - 1)]
    op = con.execute("SELECT * FROM offene_posten WHERE id=?", (m["op_id"],)).fetchone()
    op = dict(op) if op else dict(d.get("rechnung") or {})
    k = op_kunde(con, op) if op.get("kunde_id") else dict(d.get("kunde") or {})
    betr = {x: m[x] for x in ("offen", "gesamt", "gebuehr")}
    bisher = [x for x in mahn_bisher(con, m["op_id"]) if x["id"] < mid]
    werte = mahn_werte(op, k, betr, m["datum"], m["frist"], bisher, sc, e, (d.get("auftrag") or {}).get("bezeichnung", ""))
    text = text_einsetzen(sc.get("mail_text") or "", werte).rstrip() + "\n" + mail_signatur(e)
    pdf_name = sauber(f"{m['nummer']}_{d.get('stufenname', 'Mahnung')}_{(d.get('kunde') or {}).get('kurzname', '')}") + ".pdf"
    anh = [{"id": "mahnung", "name": pdf_name, "an": True}]
    if (d.get("rechnung") or {}).get("beleg_id"):
        anh.append({"id": "rechnung", "name": f"Rechnung {(d.get('rechnung') or {}).get('nummer', '')} (PDF)", "an": m["stufe"] == 0})
    adr = [x for x in (k.get("email1"), k.get("email2"), k.get("email3"), k.get("email4")) if x]
    adr = rechnungsadressen_vorn(adr)   # Mahnungen bevorzugt an die Rechnungsadresse
    cfgm = e.get("mail") or {}
    return {"an": adr[0] if adr else "", "adressen": adr, "betreff": text_einsetzen(sc.get("mail_betreff") or sc["betreff"], werte),
            "text": text, "anhaenge": anh, "dateien": [], "eingerichtet": bool(cfgm.get("smtp_server") and cfgm.get("passwort")),
            "absender": cfgm.get("adresse") or "", "festschreiben": False, "versendet": m.get("versendet") or "",
            "versendet_an": m.get("versendet_an") or "", "kopie_an_mich": bool(cfgm.get("kopie_an_mich"))}


def mahnung_mail_senden(con, mid, d):
    e = einstellungen(con)
    cfg = e.get("mail") or {}
    if not (cfg.get("smtp_server") and cfg.get("passwort")):
        raise ApiFehler("Der E-Mail-Versand ist noch nicht eingerichtet (Einstellungen > E-Mail).")
    mailversand.adressen(d.get("an"))
    mailversand.adressen(d.get("cc"))
    m = mahnung_laden(con, mid)
    gewaehlt = set(d.get("anhaenge") or ["mahnung"])
    anh = []
    if "mahnung" in gewaehlt:
        pfad = mahnung_pdf(con, mid)
        with open(pfad, "rb") as f:
            anh.append((os.path.basename(pfad), f.read(), "application/pdf"))
    bid = (m["daten"].get("rechnung") or {}).get("beleg_id")
    if "rechnung" in gewaehlt and bid:
        pdf = beleg_pdf(con, bid)
        with open(pdf["archiv"], "rb") as f:
            anh.append((os.path.basename(pdf["archiv"]), f.read(), "application/pdf"))
    con.commit()
    try:
        r = mailversand.senden(cfg, d.get("an"), d.get("cc"), d.get("betreff") or m["betreff"], d.get("text") or "", anh,
                               kopie_an_mich=bool(d.get("kopie_an_mich")))
    except mailversand.MailFehler as f:
        raise ApiFehler(str(f))
    con.execute("UPDATE mahnungen SET versendet=?, versendet_an=? WHERE id=?", (datetime.now().isoformat(timespec="minutes"), d.get("an"), mid))
    korrespondenz_eintragen(con, "mail_aus", kunde_id=m["kunde_id"], auftrag_id=m["auftrag_id"], betreff=d.get("betreff") or "",
                            text=d.get("text") or "", an=d.get("an") or "", message_id=r.get("message_id"), anhaenge=[x[0] for x in anh])
    con.execute("INSERT INTO notizen (kunde_id, auftrag_id, text, angelegt) VALUES (?,?,?,?)",
                (m["kunde_id"], m["auftrag_id"], f"E-Mail gesendet an {d.get('an')}: {d.get('betreff')} "
                 f"({', '.join(x[0] for x in anh) or 'ohne Anhang'})", jetzt()))
    return r


# ====================== Eingangsrechnungen (E-Rechnung einlesen) ======================
EINGANG_PFAD = os.path.join(DATEN, "eingangsrechnungen")
GRUPPE_KAT = {"Plattenwerkstoffe": "holzwerkstoffe", "Massivholz": "massivholz", "Beschläge": "beschlaege", "Oberfläche": "beschichtung"}
GRUPPE_KOSTEN = {"Plattenwerkstoffe": "werkstoffe", "Massivholz": "werkstoffe", "Beschläge": "beschlaege", "Oberfläche": "oberflaeche",
                 "Dienstleister": "fremdleistungen"}
WERKZEUG_WORTE = ("säge", "saege", "fräse", "fraese", "schleifer", "schrauber", "bohrmaschine", "hobel", "kapex", "domino", "akku",
                  "maschine", "zwinge", "clamp", "license", "lizenz", "werkzeug", "maßstab", "wasserwaage", "untergestell")


def zuordnung_schluessel(z):
    return (z.get("artnr") or z.get("ean") or (z.get("bezeichnung") or "").split("\n")[0]).strip().lower()[:120]


def lieferant_finden(con, L):
    """Lieferant über USt-IdNr., IBAN oder Namen finden."""
    ust = eingangsrechnung.ustid_normal(L.get("ustid"))
    iban = eingangsrechnung.iban_normal(L.get("iban"))
    for r in con.execute("SELECT id, kurzname, gruppe, ustid, iban FROM lieferanten"):
        if ust and eingangsrechnung.ustid_normal(r["ustid"]) == ust:
            return dict(r)
        if iban and eingangsrechnung.iban_normal(r["iban"]) == iban:
            return dict(r)
    name = (L.get("name") or "").lower()
    wort = next((w for w in re.split(r"[\s,\-&.]+", name) if len(w) > 3 and w not in ("gmbh", "großhandel", "grosshandel", "franz")), "")
    if wort:
        r = con.execute("SELECT id, kurzname, gruppe, ustid, iban FROM lieferanten WHERE ulower(kurzname) LIKE ? ORDER BY aktiv DESC LIMIT 1",
                        (f"%{wort}%",)).fetchone()
        if r:
            return dict(r)
    return None


def auftrag_finden(con, texte):
    t = " ".join(x for x in texte if x)
    if not t:
        return None
    for a in con.execute("SELECT id, nummer, bezeichnung FROM auftraege ORDER BY id DESC"):
        if a["nummer"] and re.search(r"(?<![\w-])" + re.escape(a["nummer"]) + r"(?![\w-])", t):
            return dict(a)
    return None


def eingang_lesen(con, d):
    if not d.get("daten"):
        raise ApiFehler("Keine Datei übergeben.")
    roh = base64.b64decode(d["daten"])
    e = einstellungen(con)
    eigen = {"iban": [e.get("sepa_iban")], "ustid": [e.get("ustid")],
             "namen": [(e.get("firma") or "").lower(), (e.get("firma_inhaber") or "").lower()]}
    try:
        erg = eingangsrechnung.lesen(roh, d.get("dateiname") or "", eigen)
    except eingangsrechnung.LeseFehler as f:
        raise ApiFehler(str(f))
    # Datei zwischenspeichern, bis gebucht wird
    endung = ".xml" if not erg.get("pdf") else ".pdf"
    token = uuid.uuid4().hex
    tmp = os.path.join(DATEN, "tmp")
    os.makedirs(tmp, exist_ok=True)
    with open(os.path.join(tmp, f"eingang-{token}{endung}"), "wb") as f:
        f.write(roh)
    r, L = erg["rechnung"], erg["lieferant"]
    gef = lieferant_finden(con, L)
    erg["token"], erg["endung"], erg["dateiname"] = token, endung, d.get("dateiname") or ""
    erg["lieferant_id"] = gef["id"] if gef else None
    erg["lieferant_name"] = gef["kurzname"] if gef else ""
    gruppe = gef["gruppe"] if gef else ""
    if gef and r.get("nummer"):
        dop = con.execute("SELECT id, nummer FROM zahlungen WHERE lieferant_id=? AND belegnr=?", (gef["id"], r["nummer"])).fetchone()
        if dop:
            erg["doppelt"] = {"id": dop["id"], "nummer": dop["nummer"]}
    texte = erg["texte"] + [z.get("hinweis") or "" for z in erg["zeilen"]] + [z.get("bezeichnung") or "" for z in erg["zeilen"]] + [r.get("verwendungszweck") or ""]
    a = auftrag_finden(con, texte)
    erg["auftrag_id"] = a["id"] if a else None
    if a:
        erg["hinweise"].append(f"Auftrag {a['nummer']} ({a['bezeichnung']}) auf der Rechnung erkannt.")
    # Vorschläge je Zeile
    gelernt = {}
    if gef:
        for z in con.execute("SELECT * FROM zuordnungen WHERE lieferant_id=?", (gef["id"],)):
            gelernt[z["schluessel"]] = dict(z)
    for z in erg["zeilen"]:
        schl = zuordnung_schluessel(z)
        z["schluessel"] = schl
        g = gelernt.get(schl)
        m = None
        kandidaten = [x for x in (z.get("artnr"), z.get("ean")) if x]
        if g and g.get("material_id"):
            m = con.execute("SELECT id, nummer, bezeichnung, kategorie, einheit FROM material WHERE id=?", (g["material_id"],)).fetchone()
        if not m and kandidaten:
            ph = ",".join("?" * len(kandidaten))
            m = con.execute(f"SELECT id, nummer, bezeichnung, kategorie, einheit FROM material WHERE aktiv=1 AND "
                            f"(bestellnr IN ({ph}) OR IFNULL(ean,'') IN ({ph})) ORDER BY (lieferant_id=?) DESC LIMIT 1",
                            kandidaten + kandidaten + [gef["id"] if gef else 0]).fetchone()
        z["material_id"] = m["id"] if m else None
        z["material"] = f"{m['nummer']} · {m['bezeichnung'].splitlines()[0]}" if m else ""
        kat = (m["kategorie"] if m else None) or GRUPPE_KAT.get(gruppe, "artikel")
        z["kategorie"] = kat
        z["kostenart"] = (g or {}).get("kostenart") or (material.KAT_KOSTENART.get(m["kategorie"]) if m else GRUPPE_KOSTEN.get(gruppe, "kleinmaterial"))
        werkzeugig = gruppe == "Werkzeug & Maschinen" or any(w in (z.get("bezeichnung") or "").lower() for w in WERKZEUG_WORTE)
        if g:
            z["aktion"], z["gelernt"] = g["ziel"], True
        elif z.get("zuschlag"):
            z["aktion"] = "auftrag" if a else "kosten"
            z["kostenart"] = "fremdleistungen" if "fracht" in (z.get("bezeichnung") or "").lower() else z["kostenart"]
        elif m:
            z["aktion"] = "auftrag" if a else "lager"
        elif werkzeugig and abs(z.get("netto") or 0) >= 20:
            z["aktion"] = "werkzeug"
        else:
            z["aktion"] = "auftrag" if a else "kosten"
        if erg.get("gutschrift") and z["aktion"] in ("lager", "werkzeug"):
            z["aktion"] = "auftrag" if a else "kosten"   # Gutschrift: keine Lagerzugänge oder Werkzeuge anlegen
        z["merken"] = not z.get("zuschlag") and not erg.get("gutschrift")
    erg["kostenarten"] = material.KOSTENARTEN
    erg["kategorien"] = material.KATEGORIEN
    erg.pop("texte", None)
    return erg


def eingang_buchen(con, d):
    k = d.get("kopf") or {}
    token = re.sub(r"[^0-9a-f]", "", d.get("token") or "")
    tmp = os.path.join(DATEN, "tmp", f"eingang-{token}{'.xml' if d.get('endung') == '.xml' else '.pdf'}")
    # Lieferant
    lid = int(d.get("lieferant_id") or 0)
    if lid:
        l = con.execute("SELECT * FROM lieferanten WHERE id=?", (lid,)).fetchone()
        if not l:
            raise ApiFehler("Lieferant nicht gefunden.")
        # fehlende Stammdaten ergänzen
        neu = d.get("lieferant_neu") or {}
        for feld in ("ustid", "iban", "bic"):
            if neu.get(feld) and not (l[feld] or ""):
                con.execute(f"UPDATE lieferanten SET {feld}=? WHERE id=?", (neu[feld], lid))
    else:
        neu = d.get("lieferant_neu") or {}
        if not (neu.get("kurzname") or "").strip():
            raise ApiFehler("Bitte einen Lieferanten wählen oder einen Namen für den neuen Lieferanten eingeben.")
        e = einstellungen(con)
        maxnr = con.execute("SELECT MAX(nummer) FROM lieferanten").fetchone()[0]
        nr = max(int(e.get("lieferantennr_start") or 700000), (maxnr or 0) + 1)
        anschrift = "\n".join(x for x in [neu.get("name") or neu["kurzname"], neu.get("strasse")] if x)
        cur = con.execute("INSERT INTO lieferanten (nummer, kurzname, gruppe, anschrift, plz, ort, ustid, iban, bic, empfaenger, telefon, email1, "
                          "angelegt, geaendert) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (nr, neu["kurzname"].strip(), neu.get("gruppe") or "Sonstiges", anschrift, neu.get("plz") or "", neu.get("ort") or "",
                           neu.get("ustid") or "", neu.get("iban") or "", neu.get("bic") or "", neu.get("name") or neu["kurzname"],
                           neu.get("telefon") or "", neu.get("email") or "", jetzt(), jetzt()))
        lid = cur.lastrowid
        l = con.execute("SELECT * FROM lieferanten WHERE id=?", (lid,)).fetchone()
    belegnr = (k.get("belegnr") or "").strip()
    if belegnr and not d.get("trotzdem"):
        dop = con.execute("SELECT nummer FROM zahlungen WHERE lieferant_id=? AND belegnr=?", (lid, belegnr)).fetchone()
        if dop:
            raise ApiFehler(f"Die Rechnung {belegnr} von {l['kurzname']} ist schon als Zahlungsauftrag {dop['nummer']} erfasst.")
    belegdatum = k.get("belegdatum") or date.today().isoformat()
    # Datei ablegen
    datei = ""
    if token and os.path.exists(tmp):
        ordner = os.path.join(EINGANG_PFAD, belegdatum[:4])
        os.makedirs(ordner, exist_ok=True)
        datei = os.path.join(ordner, sauber(f"{belegdatum}_{l['kurzname']}_{belegnr or token[:8]}").replace(" ", "_") + os.path.splitext(tmp)[1])
        shutil.move(tmp, datei)
    # Zahlungsauftrag
    betrag = round(zahl(k.get("betrag"), float), 2)
    bezahlt = k.get("bezahlt") or ""
    werte = {"nummer": naechste_zahlungsnummer(con), "lieferant_id": lid, "auftrag_id": None, "belegnr": belegnr, "belegdatum": belegdatum,
             "bemerkung": k.get("bemerkung") or "", "empfaenger": l["empfaenger"] or l["kurzname"],
             "iban": eingangsrechnung.iban_normal(k.get("iban")) or l["iban"] or "", "bic": (k.get("bic") or l["bic"] or "").replace(" ", ""),
             "betrag": betrag, "vorsteuer": zahl(k.get("vorsteuer"), float) if k.get("vorsteuer") not in (None, "") else (l["vorsteuer"] or 19),
             "skonto": zahl(k.get("skonto"), float), "skonto_bis": k.get("skonto_bis") or "",
             "faellig": k.get("faellig") or plus_tage(belegdatum, l["zahlungsziel"] or 30), "bezahlt": bezahlt,
             "bezahlung": k.get("bezahlung") or "Überweisung", "datei": datei, "angelegt": jetzt(), "geaendert": jetzt()}
    cur = con.execute(f"INSERT INTO zahlungen ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})", list(werte.values()))
    zid = cur.lastrowid
    # Zeilen
    zaehler = {"lager": 0, "auftrag": 0, "werkzeug": 0, "kosten": 0, "neu_material": 0}
    hinweis = f"Rg. {belegnr} {l['kurzname']}".strip()
    for z in d.get("zeilen") or []:
        aktion = z.get("aktion") or "kosten"
        menge = zahl(z.get("menge"), float) or 1
        netto = round(zahl(z.get("netto"), float), 2)
        ep = round(netto / menge, 4) if menge else 0
        bez = (z.get("bezeichnung") or "").strip() or "(ohne Bezeichnung)"
        mid = int(z.get("material_id") or 0) or None
        try:
            if aktion in ("lager", "auftrag") and not mid and z.get("neu_anlegen"):
                kat = z.get("kategorie") if z.get("kategorie") in material.KATEGORIEN else "artikel"
                m = material.anlegen(con, {"kategorie": kat, "bezeichnung": bez, "einheit": z.get("einheit") or material.STANDARD_EINHEIT.get(kat, "Stk."),
                                           "ek_preis": ep, "lieferant_id": lid, "bestellnr": z.get("artnr") or "", "ean": z.get("ean") or "",
                                           "preis_vom": belegdatum, "gruppe": ""})
                mid = m["id"]
                zaehler["neu_material"] += 1
            if aktion == "lager":
                if not mid:
                    raise ApiFehler(f"Zeile „{bez.splitlines()[0]}“: bitte ein Material wählen oder „neu anlegen“ ankreuzen.")
                material.lager_buchen(con, {"material_id": mid, "menge": menge, "art": "zugang", "preis": ep, "datum": belegdatum,
                                            "bemerkung": hinweis})
                if z.get("preis_uebernehmen", True):
                    con.execute("UPDATE material SET ek_preis=?, preis_vom=?, geaendert=? WHERE id=?", (ep, belegdatum, jetzt(), mid))
            elif aktion == "auftrag":
                aid = int(z.get("auftrag_id") or k.get("auftrag_id") or 0)
                if not aid:
                    raise ApiFehler(f"Zeile „{bez.splitlines()[0]}“: bitte einen Auftrag wählen.")
                material.ak_buchen(con, {"auftrag_id": aid, "kostenart": z.get("kostenart") or "kleinmaterial", "material_id": mid or "",
                                         "bezeichnung": bez.splitlines()[0], "menge": menge, "einheit": z.get("einheit") or "",
                                         "einzelpreis": ep, "betrag": netto, "datum": belegdatum, "bemerkung": hinweis})
                if mid and z.get("preis_uebernehmen", True):
                    con.execute("UPDATE material SET ek_preis=?, preis_vom=?, geaendert=? WHERE id=?", (ep, belegdatum, jetzt(), mid))
            elif aktion == "werkzeug":
                werkzeuge.anlegen(con, {"bezeichnung": bez, "artikelnr": z.get("artnr") or "", "lieferant_id": lid, "zahlung_id": zid,
                                        "rechnung": belegnr, "kaufdatum": belegdatum, "preis": netto, "menge": menge,
                                        "art": z.get("werkzeug_art") or werkzeuge.art_raten(bez)})
        except (material.Fehler, werkzeuge.Fehler) as f:
            raise ApiFehler(f"Zeile „{bez.splitlines()[0]}“: {f}")
        zaehler[aktion if aktion in zaehler else "kosten"] += 1
        if z.get("merken") and z.get("schluessel"):
            con.execute("INSERT INTO zuordnungen (lieferant_id, schluessel, ziel, material_id, kostenart, angelegt) VALUES (?,?,?,?,?,?) "
                        "ON CONFLICT(lieferant_id, schluessel) DO UPDATE SET ziel=excluded.ziel, material_id=excluded.material_id, "
                        "kostenart=excluded.kostenart", (lid, z["schluessel"], aktion, mid, z.get("kostenart") or "", jetzt()))
    con.execute("INSERT INTO notizen (lieferant_id, text, angelegt) VALUES (?,?,?)",
                (lid, f"Eingangsrechnung {belegnr} eingelesen ({d.get('format') or 'Datei'}), Zahlungsauftrag {werte['nummer']}", jetzt()))
    if str(d.get("rechnungspost_id") or "").isdigit():
        # aus dem Postfach vorgeschlagen: als gebucht vermerken; die Datei liegt jetzt bei der Zahlung, die Kopie wird entfernt
        con.execute(RECHNUNGSPOST_SCHEMA)
        rp_ = con.execute("SELECT datei FROM rechnungspost WHERE id=?", (int(d["rechnungspost_id"]),)).fetchone()
        if rp_ and datei and rp_["datei"]:
            _datei_weg(os.path.normpath(os.path.join(DATEN, rp_["datei"])))
        con.execute("UPDATE rechnungspost SET status='gebucht', zahlung_id=?, lieferant_id=?, datei=CASE WHEN ? THEN '' ELSE datei END WHERE id=?",
                    (zid, lid, 1 if datei else 0, int(d["rechnungspost_id"])))
    return {"zahlung_id": zid, "zahlung": werte["nummer"], "lieferant_id": lid, **zaehler}


# ====================== Rechnungen aus dem Postfach (Lieferanten) ======================
RECHNUNGSPOST_PFAD = os.path.join(DATEN, "rechnungspost")
RECHNUNGSPOST_SCHEMA = """CREATE TABLE IF NOT EXISTS rechnungspost (
    id INTEGER PRIMARY KEY AUTOINCREMENT, hash TEXT UNIQUE, message_id TEXT, datei TEXT DEFAULT '', dateiname TEXT DEFAULT '',
    betreff TEXT DEFAULT '', von TEXT DEFAULT '', datum TEXT DEFAULT '', ordner TEXT DEFAULT '', lieferant_id INTEGER, auftrag_id INTEGER,
    belegnr TEXT DEFAULT '', belegdatum TEXT DEFAULT '', betrag REAL, format TEXT DEFAULT '', status TEXT DEFAULT 'neu',
    zahlung_id INTEGER, hinweis TEXT DEFAULT '', angelegt TEXT)"""
RG_WORTE = re.compile(r"(?i)rechnung|invoice|faktura|gutschrift|\bRE[-_ ]?\d|beleg")
FREEMAIL = {"gmail.com", "googlemail.com", "web.de", "gmx.de", "gmx.net", "t-online.de", "outlook.com", "outlook.de", "hotmail.com",
            "hotmail.de", "yahoo.de", "yahoo.com", "icloud.com", "me.com", "aol.com", "freenet.de", "posteo.de", "mailbox.org", "live.de"}


def _lieferant_per_mail(con, adressen):
    """Lieferant über die Absenderadresse finden: erst genaue Adresse (E-Mail 1–4), dann gleiche Domain (nicht bei Freemail)."""
    adressen = [a.lower() for a in adressen if "@" in a]
    domains = {a.split("@", 1)[1] for a in adressen} - FREEMAIL
    nach_domain = None
    for r in con.execute("SELECT id, email1, email2, email3, email4 FROM lieferanten ORDER BY aktiv DESC, id"):
        eigene = [x for i in range(1, 5) for x in re.split(r"[,;\s]+", (r[f"email{i}"] or "").lower()) if "@" in x]
        if any(a in eigene for a in adressen):
            return r["id"]
        if nach_domain is None and any(x.split("@", 1)[1] in domains for x in eigene):
            nach_domain = r["id"]
    return nach_domain


def rechnungspost_mail(con, msg, mid, absender, im_rg_ordner, lieferant_id=None):
    """Wird beim Lesen des Postfachs für jede eingehende Mail aufgerufen. Rechnungsanhänge (PDF, ZUGFeRD, XRechnung) von
    Lieferanten – erkannt an allen hinterlegten Mailadressen bzw. deren Domain – sowie alle PDF/XML-Anhänge aus dem
    Rechnungsordner werden abgelegt und zum Buchen vorgeschlagen. Nichts wird im Postfach verändert."""
    lid = lieferant_id or _lieferant_per_mail(con, absender)
    if not lid and not im_rg_ordner:
        return 0
    anhaenge = []
    for teil in msg.walk():
        if teil.is_multipart():
            continue
        name = teil.get_filename() or ""
        typ = teil.get_content_type()
        if not (name.lower().endswith((".pdf", ".xml")) or typ in ("application/pdf", "application/xml", "text/xml")):
            continue
        try:
            roh = teil.get_payload(decode=True) or b""
        except Exception:  # noqa: BLE001
            continue
        if 200 < len(roh) < 25 * 1024 * 1024:
            anhaenge.append((name or ("rechnung.pdf" if typ == "application/pdf" else "rechnung.xml"), roh))
    if not anhaenge:
        return 0
    con.execute(RECHNUNGSPOST_SCHEMA)
    import hashlib
    betreff = str(msg.get("Subject") or "")
    try:
        from email.utils import parsedate_to_datetime
        zeit = parsedate_to_datetime(str(msg.get("Date"))).astimezone().replace(tzinfo=None).isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001
        zeit = jetzt()
    text = ""
    try:
        text = korrespondenz._text_aus(msg)[0][:4000]
    except Exception:  # noqa: BLE001
        pass
    e = einstellungen(con)
    eigen = {"iban": [e.get("sepa_iban")], "ustid": [e.get("ustid")],
             "namen": [(e.get("firma") or "").lower(), (e.get("firma_inhaber") or "").lower()]}
    neu = 0
    for name, roh in anhaenge:
        hsh = hashlib.sha256(roh).hexdigest()
        if con.execute("SELECT 1 FROM rechnungspost WHERE hash=?", (hsh,)).fetchone():
            continue
        try:
            erg = eingangsrechnung.lesen(roh, name, eigen)
        except Exception:  # noqa: BLE001
            erg = None
        r = (erg or {}).get("rechnung") or {}
        e_rechnung = bool(erg) and erg.get("format") != "PDF ohne E-Rechnung"
        wahrscheinlich = e_rechnung or bool(RG_WORTE.search(name + " " + betreff)) or bool(r.get("nummer") and r.get("zahlbetrag"))
        if not wahrscheinlich and not im_rg_ordner:
            continue
        if erg is None and not im_rg_ordner:
            continue
        gef = lieferant_finden(con, erg.get("lieferant") or {}) if erg else None
        l_id = (gef or {}).get("id") or lid
        a = auftrag_finden(con, [betreff, text, name] + ((erg or {}).get("texte") or []) + [z.get("bezeichnung") or "" for z in (erg or {}).get("zeilen") or []])
        status, zid, hinweis = "neu", None, ""
        if l_id and r.get("nummer"):
            dop = con.execute("SELECT id, nummer FROM zahlungen WHERE lieferant_id=? AND belegnr=?", (l_id, r["nummer"])).fetchone()
            if dop:
                status, zid, hinweis = "erfasst", dop["id"], f"schon als Zahlungsauftrag {dop['nummer']} erfasst"
        if erg is None:
            hinweis = "Datei nicht lesbar – bitte von Hand prüfen"
        ordner = os.path.join(RECHNUNGSPOST_PFAD, zeit[:4])
        os.makedirs(ordner, exist_ok=True)
        datei = os.path.join(ordner, hsh[:16] + "_" + sauber(os.path.basename(name))[:80])
        with open(datei, "wb") as f:
            f.write(roh)
        betrag = r.get("zahlbetrag") or r.get("brutto")
        con.execute("INSERT INTO rechnungspost (hash, message_id, datei, dateiname, betreff, von, datum, ordner, lieferant_id, auftrag_id, belegnr, "
                    "belegdatum, betrag, format, status, zahlung_id, hinweis, angelegt) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (hsh, mid, os.path.relpath(datei, DATEN), name, betreff[:300], ", ".join(absender)[:200], zeit,
                     "Rechnungsordner" if im_rg_ordner else "Posteingang", l_id, (a or {}).get("id"), r.get("nummer") or "",
                     r.get("datum") or "", betrag, (erg or {}).get("format") or "", status, zid, hinweis, jetzt()))
        neu += 1
    return neu


def rechnungspost_api(con, methode, teile, q, d):
    con.execute(RECHNUNGSPOST_SCHEMA)
    rid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
    if methode == "GET" and rid is None:
        st = q.get("status", "neu")
        sql = ("SELECT r.*, l.kurzname AS lieferant, a.nummer AS auftragsnr, a.bezeichnung AS auftrag, z.nummer AS zahlung FROM rechnungspost r "
               "LEFT JOIN lieferanten l ON l.id=r.lieferant_id LEFT JOIN auftraege a ON a.id=r.auftrag_id LEFT JOIN zahlungen z ON z.id=r.zahlung_id")
        p = []
        if st:
            sql += " WHERE r.status=?"
            p.append(st)
        rows = [dict(x) for x in con.execute(sql + " ORDER BY r.datum DESC, r.id DESC LIMIT 500", p)]
        for x in rows:
            x.pop("hash", None)
        return rows
    if rid is None:
        raise ApiFehler("Unbekannte Anfrage", 404)
    r = con.execute("SELECT * FROM rechnungspost WHERE id=?", (rid,)).fetchone()
    if not r:
        raise ApiFehler("Eintrag nicht gefunden.", 404)
    pfad = os.path.normpath(os.path.join(DATEN, r["datei"] or ""))
    if methode == "POST" and teile[2:] == ["lesen"]:
        if not r["datei"] or not pfad.startswith(os.path.join(DATEN, "")) or not os.path.isfile(pfad):
            raise ApiFehler("Die Datei ist nicht mehr vorhanden.")
        with open(pfad, "rb") as f:
            roh = f.read()
        erg = eingang_lesen(con, {"daten": base64.b64encode(roh).decode("ascii"), "dateiname": r["dateiname"]})
        if not erg.get("lieferant_id") and r["lieferant_id"]:
            l = con.execute("SELECT id, kurzname FROM lieferanten WHERE id=?", (r["lieferant_id"],)).fetchone()
            if l:
                erg["lieferant_id"], erg["lieferant_name"] = l["id"], l["kurzname"]
                erg["hinweise"].append(f"Lieferant {l['kurzname']} an der Absenderadresse der Mail erkannt.")
        if not erg.get("auftrag_id") and r["auftrag_id"]:
            erg["auftrag_id"] = r["auftrag_id"]
            a = con.execute("SELECT nummer FROM auftraege WHERE id=?", (r["auftrag_id"],)).fetchone()
            if a:
                erg["hinweise"].append(f"Auftrag {a['nummer']} im Betreff oder Text der Mail erkannt.")
        erg["rechnungspost_id"] = rid
        erg["mail_von"] = r["von"] or ""
        erg["hinweise"].insert(0, f"Aus der Mail „{r['betreff']}“ vom {de_datum(r['datum'][:10])} ({r['von']}).")
        return erg
    if methode == "POST" and teile[2:] in (["ignorieren"], ["wieder"]):
        con.execute("UPDATE rechnungspost SET status=? WHERE id=?", ("ignoriert" if teile[2] == "ignorieren" else "neu", rid))
        return {"ok": True}
    raise ApiFehler("Unbekannte Anfrage", 404)


# ====================== XML-Ansicht (E-Rechnungen prüfen) ======================
def _datei_bytes(pfad):
    if not pfad or not os.path.isfile(pfad):
        raise ApiFehler("Die Datei ist nicht vorhanden.", 404)
    with open(pfad, "rb") as f:
        return f.read()


def xml_api(con, methode, teile, q, d):
    """XML-Datei oder ZUGFeRD-PDF anzeigen und prüfen. Quellen: hochgeladene Datei (POST), eingelesene Rechnung (Token),
    Zahlungsauftrag, Vorschlag aus dem Postfach, eigener Beleg, Datei im Projektordner."""
    r_ = benutzer.aktuelle_rechte()
    if r_ and not r_.get("inhaber") and not r_.get("preise"):
        raise ApiFehler("Für E-Rechnungen fehlt die Berechtigung (Preise).", 403)
    try:
        if methode == "POST" and len(teile) == 1:
            if not d.get("daten"):
                raise ApiFehler("Keine Datei übergeben.")
            return xmlansicht.anzeigen(base64.b64decode(d["daten"]), d.get("dateiname") or "")
        art = teile[1] if len(teile) > 1 else ""
        wert = teile[2] if len(teile) > 2 else ""
        if methode != "GET":
            raise ApiFehler("Unbekannte Anfrage", 404)
        if art == "eingang" and re.fullmatch(r"[0-9a-f]{32}", wert):
            for endung in (".pdf", ".xml"):
                p = os.path.join(DATEN, "tmp", f"eingang-{wert}{endung}")
                if os.path.isfile(p):
                    return xmlansicht.anzeigen(_datei_bytes(p), os.path.basename(p))
            raise ApiFehler("Die eingelesene Datei ist nicht mehr vorhanden.", 404)
        if art == "zahlung" and wert.isdigit():
            benutzer_darf("lieferanten")
            z = con.execute("SELECT datei FROM zahlungen WHERE id=?", (int(wert),)).fetchone()
            p = (z["datei"] if z else "") or ""
            p = p if os.path.isabs(p) else os.path.join(EINGANG_PFAD, p)
            return xmlansicht.anzeigen(_datei_bytes(p), os.path.basename(p))
        if art == "rechnungspost" and wert.isdigit():
            benutzer_darf("lieferanten")
            r = con.execute("SELECT datei, dateiname FROM rechnungspost WHERE id=?", (int(wert),)).fetchone()
            p = os.path.normpath(os.path.join(DATEN, (r["datei"] if r else "") or "-"))
            if not _im_datenordner(p):
                raise ApiFehler("Datei nicht gefunden.", 404)
            return xmlansicht.anzeigen(_datei_bytes(p), r["dateiname"] or "")
        if art == "beleg" and wert.isdigit():
            benutzer_darf("auftraege")
            b = beleg_laden(con, int(wert))
            if not b["ist_rechnung"]:
                raise ApiFehler("E-Rechnungen gibt es nur für Rechnungen.")
            if b["status"] in ("fest", "storniert"):
                # archiviertes Original: XRechnung-Datei oder die in der Archiv-PDF eingebettete XML
                if b.get("pdf") and os.path.isfile(b["pdf"]):
                    xr = b["pdf"][:-4] + "_XRechnung.xml"
                    if os.path.isfile(xr):
                        return xmlansicht.anzeigen(_datei_bytes(xr), os.path.basename(xr))
                    try:
                        return xmlansicht.anzeigen(_datei_bytes(b["pdf"]), os.path.basename(b["pdf"]))
                    except xmlansicht.Fehler:
                        pass
            xr = q.get("format") == "xrechnung" or xrechnung_gewuenscht(con, b)
            try:
                xml = erechnung.cii_xml(dict(b, nummer=b["nummer"] or "ENTWURF"), xr, auftrag_kunde(con, b["auftrag_id"]))
            except erechnung.ERechnungFehler as f:
                raise ApiFehler(f"Die E-Rechnung kann noch nicht erzeugt werden: {f}")
            erg = xmlansicht.pruefen(xml, "aus dem aktuellen Beleg erzeugt (Vorschau" + (", noch nicht festgeschrieben)" if b["status"] not in ("fest", "storniert") else ")"))
            erg["dateiname"] = f"{b['nummer'] or 'Entwurf'}{'_XRechnung' if xr else '_ZUGFeRD'}.xml"
            return erg
        if art == "projekt" and wert.isdigit():
            benutzer_darf("auftraege")
            ordner, hinweis = sicht_ordner(con, int(wert), anlegen=False)
            if not ordner:
                raise ApiFehler(hinweis or "Kein Projektordner.", 404)
            p = im_ordner(ordner, q.get("pfad", ""))
            return xmlansicht.anzeigen(_datei_bytes(p), os.path.basename(p))
    except xmlansicht.Fehler as f:
        raise ApiFehler(str(f))
    raise ApiFehler("Unbekannte Anfrage", 404)


def benutzer_darf(bereich):
    r = benutzer.aktuelle_rechte()
    if r and not r.get("inhaber") and not benutzer.darf(bereich, 1):
        raise ApiFehler("Dafür fehlt die Berechtigung.", 403)


# ====================== Listen als PDF (Werkzeuge, Lagerbestand) ======================
LISTEN = {"werkzeuge": "Werkzeug- und Maschinenliste", "lager": "Lagerbestand"}


def liste_html(con, art, q, pdf=False):
    e = einstellungen(con)
    heute_d = date.today()
    if art == "werkzeuge":
        daten = werkzeuge.liste(con, q)
        mit_rest = any(w["restwert"] is not None for w in daten)
        kopf = ["Nr.", "Bezeichnung", "Art", "Hersteller", "Seriennr.", "Standort", "Gekauft", "Status", "Preis netto"] + (["Restwert"] if mit_rest else [])
        zeilen_html, summe, gwg, je_art, rest, rest_n = [], 0.0, 0.0, {}, 0.0, 0
        for w in daten:
            p = w["preis"] or 0
            summe += p
            if w["restwert"] is not None:
                rest += w["restwert"]
                rest_n += 1
            gwg += p if w["gwg"] else 0
            je_art[w["art"] or "Sonstiges"] = je_art.get(w["art"] or "Sonstiges", 0) + p
            zeilen_html.append(
                f'<tr><td>{h(w["nummer"])}</td><td>{h((w["bezeichnung"] or "").splitlines()[0])}</td><td>{h(w["art"])}</td>'
                f'<td>{h(w["hersteller"])}</td><td>{h(w["seriennr"])}</td><td>{h(w["standort"])}</td><td class="nw">{de_datum(w["kaufdatum"])}</td>'
                f'<td>{h(w["status"])}</td><td class="r nw">{de(p)} €{" <small>GWG</small>" if w["gwg"] else ""}</td>'
                + (f'<td class="r nw">{de(w["restwert"]) + " €" if w["restwert"] is not None else ""}</td>' if mit_rest else "") + '</tr>')
        filter_txt = " · ".join(x for x in [
            {"aktiv": "alle aktiven", "faellig": "Prüfung/Wartung fällig", "": "alle einschließlich ausgemustert"}.get(q.get("status", "aktiv"), q.get("status")),
            q.get("art") or "", f"Suche „{q['q']}“" if q.get("q") else ""] if x)
        summen = "".join(f'<tr><td>{h(k)}</td><td class="r nw">{de(v)} €</td></tr>' for k, v in sorted(je_art.items(), key=lambda x: -x[1]))
        fuss = (f'<table class="summe"><tr><th colspan="2">Anschaffungswerte nach Art</th></tr>{summen}'
                f'<tr class="ges"><td>Gesamtanschaffungswert netto ({len(daten)} Stück)</td><td class="r nw">{de(summe)} €</td></tr>'
                f'<tr><td>davon geringwertige Wirtschaftsgüter (bis {de(werkzeuge.GWG_GRENZE, 0)} € netto je Stück)</td><td class="r nw">{de(gwg)} €</td></tr>'
                + (f'<tr class="ges"><td>Restbuchwert heute, linear ({rest_n} Stück mit Nutzungsdauer)</td><td class="r nw">{de(rest)} €</td></tr>' if rest_n else "")
                + '</table>' + ('<p class="klein">Restwert: lineare Abschreibung über die eingetragene Nutzungsdauer, monatsgenau ab dem Kaufmonat – ein Anhaltspunkt, maßgeblich ist das Anlagenverzeichnis der Buchhaltung.</p>' if rest_n else ""))
        breiten = ('<col style="width:13mm"><col><col style="width:30mm"><col style="width:22mm"><col style="width:24mm"><col style="width:22mm"><col style="width:19mm"><col style="width:20mm"><col style="width:26mm">'
                   + ('<col style="width:22mm">' if mit_rest else ""))
    elif art == "lager":
        stichtag = q.get("stichtag") or ""
        mats = [m for m in material.liste(con, {"lager": "1", "status": "alle"})]
        if stichtag:
            bis = {r["material_id"]: r["s"] for r in con.execute(
                "SELECT material_id, SUM(menge) AS s FROM lagerbewegungen WHERE datum<=? GROUP BY material_id", (stichtag,))}
            for m in mats:
                m["bestand"] = round(bis.get(m["id"], 0), 4)
        if q.get("lagerort"):
            mats = [m for m in mats if (m.get("lagerort") or "") == q["lagerort"]]
        mats = [m for m in mats if abs(m["bestand"] or 0) > 1e-9]
        mats.sort(key=lambda m: (list(material.KATEGORIEN).index(m["kategorie"]) if m["kategorie"] in material.KATEGORIEN else 99, m["nummer"]))
        kopf = ["Nr.", "Bezeichnung", "Lagerort", "Bestand", "Preis je Einheit", "Wert"]
        zeilen_html, summe, je_kat, letzte = [], 0.0, {}, None
        for m in mats:
            if m["kategorie"] != letzte:
                letzte = m["kategorie"]
                zeilen_html.append(f'<tr class="gr"><td colspan="6">{h(material.KATEGORIEN.get(letzte, letzte))}</td></tr>')
            preis = m["lagerpreis"] or m["ek_preis"] or 0   # Bestandswert immer zum Durchschnittspreis
            wert = round(max(m["bestand"] or 0, 0) * preis, 2)   # ein rechnerisch negativer Bestand (fehlender Zugang) ist kein negativer Wert
            summe += wert
            je_kat[letzte] = je_kat.get(letzte, 0) + wert
            zeilen_html.append(
                f'<tr><td>{h(m["nummer"])}</td><td>{h((m["bezeichnung"] or "").splitlines()[0])}</td><td>{h(m.get("lagerort") or "")}</td>'
                f'<td class="r nw">{de(m["bestand"], 3 if (m["bestand"] or 0) % 1 else 0)} {h(m["einheit"])}</td><td class="r nw">{de(preis)} €</td>'
                f'<td class="r nw">{de(wert)} €</td></tr>')
        filter_txt = " · ".join(x for x in [f"Stand {de_datum(stichtag)}" if stichtag else f"Stand {de_datum(heute_d.isoformat())}",
                                            f"Lagerort {q['lagerort']}" if q.get("lagerort") else "alle Lagerorte"] if x)
        summen = "".join(f'<tr><td>{h(material.KATEGORIEN.get(k, k))}</td><td class="r nw">{de(v)} €</td></tr>' for k, v in je_kat.items())
        fuss = (f'<table class="summe"><tr><th colspan="2">Lagerwert nach Materialart</th></tr>{summen}'
                f'<tr class="ges"><td>Gesamtwert Lager netto ({len(mats)} Artikel)</td><td class="r nw">{de(summe)} €</td></tr></table>'
                f'<p class="klein">Bewertet mit dem gleitenden Durchschnittspreis aus den Lagerzugängen (ohne Lagerbuchung: Einkaufspreis).'
                f'{" Bestände zum Stichtag aus den Lagerbewegungen, bewertet mit dem heutigen Durchschnittspreis." if stichtag else ""}</p>')
        breiten = '<col style="width:16mm"><col><col style="width:28mm"><col style="width:28mm"><col style="width:28mm"><col style="width:28mm">'
    else:
        raise ApiFehler("Unbekannte Liste", 404)
    titel = LISTEN[art]
    firma = " · ".join(x for x in [e.get("firma")] + (e.get("firma_anschrift") or "").split("\n") if x)
    quer = art == "werkzeuge"
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>{h(titel)}</title><style>
@page {{ size: A4 {"landscape" if quer else "portrait"}; margin: 12mm 12mm 14mm 14mm; }}
body {{ font: 9pt/1.35 Calibri, "Segoe UI", Arial, sans-serif; color: #222; margin: 0; }}
{"" if pdf else "html{background:#888} body{background:#fff;width:" + ("297mm" if quer else "210mm") + ";margin:10mm auto;padding:12mm 12mm 14mm 14mm;box-sizing:border-box;box-shadow:0 2px 12px rgba(0,0,0,.3)}"}
.kopf {{ display: flex; justify-content: space-between; align-items: flex-end; border-bottom: .8pt solid #333; padding-bottom: 2mm; margin-bottom: 3mm; }}
h1 {{ font-size: 15pt; margin: 0; }} .unter {{ color: #555; font-size: 9pt; }}
table.l {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
table.l th {{ text-align: left; font-size: 8pt; border-bottom: .8pt solid #333; padding: 1.2mm 1.5mm; }} table.l th.r {{ text-align: right; }}
table.l td {{ padding: 1.1mm 1.5mm; border-bottom: .3pt solid #ccc; vertical-align: top; overflow-wrap: anywhere; }}
table.l thead {{ display: table-header-group; }} table.l tr {{ page-break-inside: avoid; }}
tr.gr td {{ font-weight: 700; padding-top: 3mm; border-bottom: .6pt solid #777; }}
.r {{ text-align: right; }} .nw {{ white-space: nowrap; }} small, .klein {{ font-size: 7.5pt; color: #555; }}
table.summe {{ margin: 5mm 0 0 auto; border-collapse: collapse; min-width: 110mm; page-break-inside: avoid; }}
table.summe th {{ text-align: left; border-bottom: .8pt solid #333; padding: 1mm 1.5mm; font-size: 8.5pt; }}
table.summe td {{ padding: 1mm 1.5mm; border-bottom: .3pt solid #ccc; }}
table.summe tr.ges td {{ font-weight: 700; border-top: .8pt solid #333; border-bottom: .8pt solid #333; font-size: 10pt; }}
</style></head><body>
<div class="kopf"><div><h1>{h(titel)}</h1><div class="unter">{h(filter_txt)}</div></div><div class="unter" style="text-align:right">{h(firma)}<br>erstellt am {de_datum(heute_d.isoformat())}</div></div>
<table class="l"><colgroup>{breiten}</colgroup><thead><tr>{"".join(f'<th class="{"r" if k in ("Preis netto", "Restwert", "Bestand", "Preis je Einheit", "Wert") else ""}">{k}</th>' for k in kopf)}</tr></thead>
<tbody>{"".join(zeilen_html) or f'<tr><td colspan="{len(kopf)}">Keine Einträge.</td></tr>'}</tbody></table>
{fuss}
{'' if pdf else '<script>if(location.search.includes("drucken"))window.print()</script>'}
</body></html>"""


# ====================== Startseite / Controlling ======================
RECHNUNGSARTEN = ("abschlag", "rechnung", "storno", "gutschrift", "korrektur")


def beleg_umsatz(b):
    """Netto-Umsatz eines festgeschriebenen Rechnungsbelegs ohne doppelt gezählte Abschläge."""
    d = jl(b["daten"], {})
    return (b["netto"] or 0) - sum(x.get("netto", 0) for x in d.get("abzuege", []))


def start_daten(con, jahr):
    e = einstellungen(con)
    heute_d = date.today()
    heute_iso = heute_d.isoformat()
    vj = jahr - 1
    stichtag_vj = heute_d.replace(year=vj).isoformat() if jahr == heute_d.year else f"{vj}-12-31"
    # Umsatz je Monat
    monate = {jahr: [0.0] * 12, vj: [0.0] * 12}
    umsatz_vj_bis_stichtag = 0.0
    umsatz_auftrag = {}
    nach_zahlung = (e.get("umsatz_basis") or "zahlung") == "zahlung"

    umsatz_brutto = 0.0

    def buchen(datum_iso, u, brutto=None):
        nonlocal umsatz_vj_bis_stichtag, umsatz_brutto
        if not datum_iso:
            return
        y, m = int(datum_iso[:4]), int(datum_iso[5:7])
        if y == jahr:
            umsatz_brutto += u if brutto is None else brutto
        if y in monate:
            monate[y][m - 1] += u
        if y == vj and datum_iso <= stichtag_vj:
            umsatz_vj_bis_stichtag += u
    for b in con.execute("SELECT * FROM belege WHERE status IN ('fest','storniert') AND art IN ('abschlag','rechnung','storno','gutschrift','korrektur')"):
        u = beleg_umsatz(b)
        umsatz_auftrag[b["auftrag_id"]] = umsatz_auftrag.get(b["auftrag_id"], 0) + u
        if not nach_zahlung:
            buchen(b["datum"], u, u * (1 + (b["ust_satz"] or 0) / 100))
    if nach_zahlung:
        # Umsatz erst mit dem Zahlungseingang (Zufluss): bezahlter Betrag ohne Mahnkosten und ohne Skonto, netto
        # zum Steuersatz der Rechnung. Erstattungen (z. B. nach Storno) zählen negativ.
        for z in con.execute("SELECT z.datum, z.betrag, IFNULL(z.auf_mahnkosten,0) AS mk, z.art, b.ust_satz FROM zahlungseingaenge z "
                             "JOIN offene_posten o ON o.id=z.op_id LEFT JOIN belege b ON b.id=o.beleg_id"):
            if (z["art"] or "") == "Skonto":
                continue
            satz = z["ust_satz"] if z["ust_satz"] is not None else 19
            brutto = (z["betrag"] or 0) - z["mk"]
            buchen(z["datum"], brutto / (1 + satz / 100), brutto)
    umsatz = sum(monate[jahr])
    # Material/Wareneinsatz wie in der EÜR: alle Zahlungsaufträge an Lieferanten, netto, im Jahr der Bezahlung (bei Umsatz nach
    # Rechnungsdatum: im Jahr des Belegdatums); Skonto mindert den Betrag. Nicht dazu zählen Lieferantengruppen aus
    # „rohertrag_ohne_gruppen“ (Lohn, Finanzamt, Krankenkasse, Versicherungen, Maschinen) und die vom Lohn erzeugten Zahlungen.
    ohne_gruppen = {g.strip().lower() for g in (e.get("rohertrag_ohne_gruppen") or []) if g.strip()}
    material = 0.0
    kosten_gesamt = 0.0
    for z in con.execute("SELECT z.betrag, z.vorsteuer, z.auftrag_id, z.skonto, z.skonto_bis, z.bezahlt, z.belegdatum, z.belegnr, l.gruppe "
                         "FROM zahlungen z JOIN lieferanten l ON l.id=z.lieferant_id"):
        bez = (z["bezahlt"] or "")[:10]
        if nach_zahlung:
            if not (bez[:4].isdigit() and int(bez[:4]) == jahr):
                continue
            mit_skonto = bool(z["skonto"]) and bool(z["skonto_bis"]) and bez <= z["skonto_bis"]
            gezahlt = (z["betrag"] or 0) * (1 - (z["skonto"] or 0) / 100) if mit_skonto else (z["betrag"] or 0)
        else:
            if (z["belegdatum"] or "")[:4] != str(jahr):
                continue
            gezahlt = z["betrag"] or 0
        netto = gezahlt / (1 + (z["vorsteuer"] or 0) / 100)
        kosten_gesamt += netto
        lohn = re.match(r"^(Lohn|LStA|SV) \d\d/\d{4}$", z["belegnr"] or "")
        if z["auftrag_id"] or not (lohn or (z["gruppe"] or "").strip().lower() in ohne_gruppen):
            material += netto
    stunden = con.execute("SELECT COALESCE(SUM(stunden),0) FROM stunden WHERE substr(datum,1,4)=?", (str(jahr),)).fetchone()[0]
    # Forderungen / Verbindlichkeiten
    ford = con.execute("SELECT COALESCE(SUM(offen),0), COALESCE(SUM(CASE WHEN faellig<? THEN offen ELSE 0 END),0), "
                       "COUNT(CASE WHEN faellig<? AND offen>0.004 THEN 1 END) FROM offene_posten WHERE offen>0.004",
                       (heute_iso, heute_iso)).fetchone()
    verb = con.execute("SELECT COALESCE(SUM(betrag),0), COALESCE(SUM(CASE WHEN faellig>=? AND faellig<=? THEN betrag ELSE 0 END),0), "
                       "COALESCE(SUM(CASE WHEN faellig<>'' AND faellig<? THEN betrag ELSE 0 END),0), "
                       "COUNT(CASE WHEN faellig<>'' AND faellig<? THEN 1 END) FROM zahlungen WHERE bezahlt=''",
                       (heute_iso, plus_tage(heute_iso, 7), heute_iso, heute_iso)).fetchone()
    # Aufträge
    st_ang = e.get("status_angebot") or ["Anfrage", "Angebot"]
    st_ende = e.get("status_ende") or []
    anfragen, angebote, laufend = [], [], []
    angebotsvolumen = auftragsbestand = 0.0
    # Ein Angebot zählt erst, wenn es versendet ist; bis dahin bleibt der Auftrag bei den offenen Anfragen
    letzte_belege, entwuerfe = {}, {}
    for b in con.execute("SELECT id, auftrag_id, art, nummer, datum, netto, brutto, versendet FROM belege WHERE art IN ('angebot','kv') "
                         "ORDER BY datum, id"):
        (letzte_belege if b["versendet"] else entwuerfe)[b["auftrag_id"]] = dict(b)
    for a in con.execute("SELECT a.*, k.kurzname AS kunde, k.telefon, k.email1, k.id AS kid FROM auftraege a "
                         "JOIN kunden k ON k.id=a.kunde_id ORDER BY a.nummer"):
        a = dict(a)
        a["telefon"] = (a["telefon"] or "").split("\n")[0]
        if a["status"] in st_ende:
            continue
        try:
            erg = auftrag_rechnen(con, a["id"])
            a["netto"] = erg["netto"]
            a["soll_stunden"] = round(erg["soll"]["stunden"], 1)
        except ApiFehler:
            a["netto"], a["soll_stunden"] = 0, 0
        tage_alt = (heute_d - date.fromisoformat(a["angelegt"][:10])).days if a.get("angelegt") else 0
        ang = letzte_belege.get(a["id"])
        if a["status"] in st_ang and not ang and (a["status"] == st_ang[0] or a["id"] in entwuerfe):
            a["alter"] = tage_alt
            a["ueberfaellig"] = tage_alt >= int(e.get("anfrage_tage") or 7)
            a["entwurf"] = entwuerfe.get(a["id"])
            anfragen.append(a)
        elif a["status"] in st_ang:
            a["angebot"] = ang
            basis = max((x for x in [((ang or {}).get("versendet") or "")[:10], a.get("nachgefasst") or ""] if x), default=(a.get("angelegt") or "")[:10])
            a["seit"] = (heute_d - date.fromisoformat(basis)).days if basis else 0
            a["faellig"] = a["seit"] >= int(e.get("nachfass_tage") or 10)
            a["wert"] = (ang or {}).get("netto") or a["netto"]
            angebotsvolumen += a["wert"] or 0
            angebote.append(a)
        else:
            a["berechnet"] = round(umsatz_auftrag.get(a["id"], 0), 2)
            a["rest"] = round(max(0, a["netto"] - a["berechnet"]), 2)
            auftragsbestand += a["rest"]
            a["ist_stunden"] = round(con.execute("SELECT COALESCE(SUM(stunden),0) FROM stunden WHERE auftrag_id=?",
                                                 (a["id"],)).fetchone()[0], 1)
            t = con.execute("SELECT typ, von, bis FROM termine WHERE auftrag_id=? AND bis>=? AND erledigt=0 ORDER BY von LIMIT 1",
                            (a["id"], heute_iso)).fetchone()
            a["naechster_termin"] = dict(t) if t else None
            laufend.append(a)
    angebote.sort(key=lambda a: (not a["faellig"], -a["seit"]))
    anfragen.sort(key=lambda a: -a["alter"])
    # Angebotsquote im Jahr: Aufträge mit Angebot im Jahr, davon erteilt / abgesagt
    erteilt = abgesagt = offen_q = 0
    for a in con.execute("SELECT DISTINCT a.id, a.status FROM auftraege a JOIN belege b ON b.auftrag_id=a.id "
                         "WHERE b.art IN ('angebot','kv') AND IFNULL(b.versendet,'')<>'' AND substr(b.versendet,1,4)=?", (str(jahr),)):
        if a["status"] == "Abgesagt":
            abgesagt += 1
        elif a["status"] in st_ang:
            offen_q += 1
        else:
            erteilt += 1
    # Fällige Forderungen und Zahlungen
    ueberfaellig = zeilen(con.execute(
        "SELECT o.*, k.kurzname AS kunde FROM offene_posten o LEFT JOIN kunden k ON k.id=o.kunde_id "
        "WHERE o.offen>0.004 AND o.faellig<? ORDER BY o.faellig", (heute_iso,)))
    mahn_ergaenzen(con, ueberfaellig)
    zahlungen_faellig = zeilen(con.execute(
        "SELECT z.*, l.kurzname AS lieferant FROM zahlungen z JOIN lieferanten l ON l.id=z.lieferant_id WHERE z.bezahlt='' AND "
        "(z.faellig<=? OR (z.skonto>0 AND z.skonto_bis>=? AND z.skonto_bis<=?)) ORDER BY z.faellig",
        (plus_tage(heute_iso, 7), heute_iso, plus_tage(heute_iso, 7))))
    termine = zeilen(con.execute(
        "SELECT t.*, a.nummer AS auftragsnr, k.kurzname AS kunde FROM termine t LEFT JOIN auftraege a ON a.id=t.auftrag_id "
        "LEFT JOIN kunden k ON k.id=a.kunde_id WHERE t.bis>=? AND t.von<=? AND t.erledigt=0 ORDER BY t.von",
        (heute_iso, plus_tage(heute_iso, 13))))
    rohertrag = umsatz - material
    return {
        "jahr": jahr, "heute": heute_iso,
        "kennzahlen": {
            "umsatz": round(umsatz, 2), "umsatz_brutto": round(umsatz_brutto, 2), "umsatz_ust": round(umsatz_brutto - umsatz, 2), "umsatz_vj": round(umsatz_vj_bis_stichtag, 2), "umsatz_vj_gesamt": round(sum(monate[vj]), 2),
            "material": round(material, 2), "kosten_eingang": round(kosten_gesamt, 2), "rohertrag": round(rohertrag, 2),
            "rohertrag_pz": round(rohertrag / umsatz * 100, 1) if umsatz else 0,
            "stunden": round(stunden, 1), "ertrag_je_stunde": round(rohertrag / stunden, 2) if stunden else 0,
            "ziel_stundensatz": fl(e.get("ziel_stundensatz")),
            "forderungen": round(ford[0], 2), "forderungen_ueberfaellig": round(ford[1], 2), "anzahl_ueberfaellig": ford[2],
            "verbindlichkeiten": round(verb[0], 2), "verbindlichkeiten_7t": round(verb[1], 2),
            "verbindlichkeiten_ueberfaellig": round(verb[2], 2), "verbindlichkeiten_anzahl_ueberfaellig": verb[3],
            "material_basis": "Zahlung" if nach_zahlung else "Rechnungsdatum",
            "rechnungspost": con.execute("SELECT COUNT(*) FROM rechnungspost WHERE status='neu'").fetchone()[0],
            "angebotsvolumen": round(angebotsvolumen, 2), "auftragsbestand": round(auftragsbestand, 2),
            "quote_erteilt": erteilt, "quote_abgesagt": abgesagt, "quote_offen": offen_q,
        },
        "monate": {"aktuell": [round(x, 2) for x in monate[jahr]], "vorjahr": [round(x, 2) for x in monate[vj]]},
        "anfragen": anfragen, "angebote": angebote, "laufend": laufend,
        "ueberfaellig": ueberfaellig, "zahlungen_faellig": zahlungen_faellig, "termine": termine,
        "beschaffung": [x for x in reste.beschaffung(reste.laden(con)[0]) if x["zu_bestellen"] > 0],
        "geburtstage": geburtstage(con, int(e.get("geburtstag_tage") or 14)),
        "wiedervorlagen": wiedervorlage.liste(con, {"status": "offen", "bis": (heute_d + timedelta(7)).isoformat()}) if benutzer.darf("auftraege", 1) else [],
    }


def suche(con, q):
    q = (q or "").strip().lower()
    if len(q) < 2:
        return []
    like = f"%{q}%"
    erg = []
    for r in con.execute("SELECT id, nummer, kurzname, ort FROM kunden WHERE ulower(kurzname) LIKE ? OR CAST(nummer AS TEXT) LIKE ? "
                         "OR ulower(anschrift) LIKE ? OR ulower(ort) LIKE ? LIMIT 8", (like, like, like, like)):
        erg.append({"art": "Kunde", "titel": f"{r['nummer']} · {r['kurzname']}", "zusatz": r["ort"] or "", "link": f"#/kunde/{r['id']}"})
    for r in con.execute("SELECT a.id, a.nummer, a.bezeichnung, a.status, k.kurzname FROM auftraege a JOIN kunden k ON k.id=a.kunde_id "
                         "WHERE ulower(a.nummer) LIKE ? OR ulower(a.bezeichnung) LIKE ? OR ulower(k.kurzname) LIKE ? "
                         "ORDER BY a.nummer DESC LIMIT 8", (like, like, like)):
        erg.append({"art": "Auftrag", "titel": f"{r['nummer']} · {r['bezeichnung']}", "zusatz": f"{r['kurzname']} · {r['status']}",
                    "link": f"#/auftrag/{r['id']}"})
    for r in con.execute("SELECT id, nummer, bezeichnung, status FROM projekte WHERE ulower(nummer) LIKE ? OR ulower(bezeichnung) LIKE ? "
                         "ORDER BY nummer DESC LIMIT 5", (like, like)):
        erg.append({"art": "Projekt", "titel": f"{r['nummer']} · {r['bezeichnung']}", "zusatz": "laufend" if r["status"] == "aktiv" else "abgeschlossen",
                    "link": f"#/projekt/{r['id']}"})
    for r in con.execute("SELECT b.id, b.art, b.artname, b.nummer, b.datum, k.kurzname FROM belege b LEFT JOIN kunden k ON k.id=b.kunde_id "
                         "WHERE b.nummer<>'' AND ulower(b.nummer) LIKE ? ORDER BY b.datum DESC LIMIT 6", (like,)):
        erg.append({"art": art_name(r), "titel": r["nummer"],
                    "zusatz": f"{r['kurzname'] or ''} · {r['datum'][8:10]}.{r['datum'][5:7]}.{r['datum'][:4]}" if r["datum"] else "",
                    "link": f"#/beleg/{r['id']}"})
    for r in con.execute("SELECT id, nummer, kurzname, ort FROM lieferanten WHERE ulower(kurzname) LIKE ? OR CAST(nummer AS TEXT) LIKE ? LIMIT 5",
                         (like, like)):
        erg.append({"art": "Lieferant", "titel": f"{r['nummer']} · {r['kurzname']}", "zusatz": r["ort"] or "", "link": f"#/lieferant/{r['id']}"})
    return erg


# ---------------------------------------------------------------- Arbeitsschutz
def ich_name():
    b = dict(benutzer.aktuell() or {})
    return b.get("name") or b.get("login") or ""


def ich_login():
    return dict(benutzer.aktuell() or {}).get("login") or ""


def auftrag_material_nummern(con, aid):
    """Materialnummern und -IDs eines Auftrags: aus der Kalkulation (Werkstoffe, Beschläge) und aus den gebuchten Auftragskosten."""
    nummern = set()
    try:
        gruppen, bliste = werkstatt.materialsummen(auftrag_rechnen(con, aid))
        nummern = {x.get("matnr") for g in gruppen.values() for x in g if x.get("matnr")} | {x.get("matnr") for x in bliste if x.get("matnr")}
    except (ApiFehler, KeyError, TypeError, ValueError):
        pass
    ids = [r["material_id"] for r in con.execute("SELECT DISTINCT material_id FROM auftragskosten WHERE auftrag_id=? AND material_id IS NOT NULL", (aid,))]
    return nummern, ids


def api(methode, teile, q, daten):
    with verbindung() as con:
        res = teile[0] if teile else ""
        if methode != "GET" and res != "service":
            # Schreibende Anfragen holen sich die Schreibsperre gleich zu Beginn. Sonst kann eine Anfrage, die erst liest und
            # dann schreibt, bei gleichzeitigem Speichern eines anderen Nutzers sofort mit „database is locked“ scheitern
            # (veralteter Lesestand); so wartet sie stattdessen (bis 30 s) auf die andere Speicherung.
            con.execute("BEGIN IMMEDIATE")
        rid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
        unter = teile[2] if len(teile) > 2 else None

        if res == "stempel" and len(teile) >= 2 and teile[1] in ("unterschriften", "unterweisung", "monatsbeleg", "verbandbuch"):
            try:
                return stempel_arbeitsschutz(con, methode, teile, q, daten or {})
            except (arbeitsschutz.Fehler, unterschrift.Fehler, personal.Fehler) as f:
                raise ApiFehler(str(f), f.code)
        if res == "monatsbeleg" and rid and unter in ("unterschriften", "unterschreiben"):
            if methode == "GET":
                if not re.fullmatch(r"\d{4}-\d{2}", q.get("monat") or ""):
                    raise ApiFehler("Bitte den Monat angeben.")
                return monatsbeleg_signaturen(con, rid, q["monat"])
            if methode == "POST":
                d = daten or {}
                return monatsbeleg_unterschreiben(con, rid, str(d.get("monat") or ""), d.get("rolle") or "mitarbeiter", d, ich_login())
        if res in ("mitarbeiter", "zeiten", "abwesenheiten", "konten", "monatsbeleg", "lohn", "stempel"):
            return personal.api(con, methode, teile, q, daten)
        if res == "leitstand":
            if methode == "GET":
                return leitstand_daten(con)
            if methode == "PUT" and rid:
                return leitstand_setzen(con, rid, daten or {})
        if res == "reste":
            wer = dict(benutzer.aktuell() or {}).get("login") or "intern"
            try:
                if teile[1:] == ["lagerdatei"]:
                    if methode == "GET":
                        lager, rev = reste.stueck_abgleich(con, wer)   # Plattenformate und Stückzahl aus dem Materialstamm
                        return {"lager": lager, "rev": rev}
                    if methode == "PUT":
                        d = daten or {}
                        return {"rev": reste.speichern(con, d.get("lager"), d.get("basis"), wer)}
                if teile[1:] == ["import"] and methode == "POST":
                    try:
                        lager = json.loads((daten or {}).get("text") or "")
                    except ValueError:
                        raise ApiFehler("Die Datei ist kein gültiges JSON.")
                    reste.speichern(con, lager, None, wer)
                    return reste.uebersicht(con)
                if methode == "GET" and len(teile) == 1:
                    reste.stueck_abgleich(con, wer)
                    return reste.uebersicht(con)
                if methode == "POST" and len(teile) == 1:
                    return reste.rest_anlegen(con, daten or {}, wer)
                if methode == "PUT" and teile[1:] == ["bestellung"]:
                    reste.bestellung(con, daten or {}, wer)
                    return reste.uebersicht(con)
                if methode == "POST" and teile[1:] == ["wareneingang"]:
                    reste.wareneingang(con, daten or {}, wer)
                    return reste.uebersicht(con)
                if methode == "PUT" and len(teile) == 3 and teile[1] == "platte":
                    return reste.platte_menge(con, teile[2], daten or {}, wer)
                if methode == "PUT" and len(teile) == 2:
                    return reste.rest_aendern(con, teile[1], daten or {}, wer)
            except reste.Fehler as f:
                raise ApiFehler(str(f), f.code)
            raise ApiFehler("Unbekannte Anfrage", 404)
        if res == "scan":
            return scan_api(con, methode, teile, q, daten or {})
        if res == "korrespondenz":
            try:
                erg = korrespondenz.api(con, methode, teile, q, daten, dict(benutzer.aktuell() or {}).get("login") or "")
            except korrespondenz.Fehler as f:
                raise ApiFehler(str(f), f.code)
            if methode == "GET" and len(teile) == 1 and (q.get("kunde") or q.get("lieferant") or q.get("auftrag")):
                erg = sorted(erg + briefe_als_korrespondenz(con, q), key=lambda x: (x.get("datum") or ""), reverse=True)
            return erg
        if res == "newsletter":
            return newsletter(con, methode, q, daten or {})
        if res == "briefe" and not (methode == "GET" and rid is None):
            return brief_api(con, methode, rid, unter, q, daten or {})
        if res == "bautagebuch":
            try:
                return bautagebuch.api(con, methode, teile, q, daten, dict(benutzer.aktuell() or {}).get("login") or "")
            except bautagebuch.Fehler as f:
                raise ApiFehler(str(f), f.code)
        if res == "kundenunterschrift":
            # Unterschrift auf dem Tablet (auch für Benutzer „nur Werkstatt“): AB nur mit Preisrecht, Lieferschein/Abnahme immer
            r = benutzer.aktuelle_rechte() or {}
            darf_preise = r.get("inhaber") or r.get("preise", True)
            arten = UNTERSCHREIBBAR if darf_preise else ("lieferschein", "abnahme")
            if methode == "GET" and rid is None:
                aid = int(q.get("auftrag") or 0)
                return [{"id": x["id"], "art": x["art"], "artname": art_name(x), "nummer": x["nummer"], "datum": x["datum"],
                         "unterschrieben": (jl(x["daten"], {}).get("unterschrift") or {}).get("zeit"),
                         "name": (jl(x["daten"], {}).get("unterschrift") or {}).get("name")}
                        for x in con.execute(f"SELECT id, art, nummer, datum, daten FROM belege WHERE auftrag_id=? AND art IN ({','.join('?' * len(arten))}) "
                                             "ORDER BY datum DESC, id DESC", (aid, *arten))]
            if not rid:
                raise ApiFehler("Unbekannte Anfrage", 404)
            b = beleg_laden(con, rid)
            if b["art"] not in arten:
                raise ApiFehler("Dieser Beleg lässt sich hier nicht unterschreiben.", 403)
            if methode == "GET":
                k = auftrag_kunde(con, b["auftrag_id"])
                u = b["daten"].get("unterschrift") or {}
                return {"id": b["id"], "art": b["art"], "artname": b["artname"], "nummer": b["nummer"], "datum": b["datum"],
                        "auftrag_id": b["auftrag_id"], "auftrag": auftrag_laden(con, b["auftrag_id"]), "abnahme": b["daten"].get("abnahme") or {},
                        "kunde": {"name": k.get("name") or k.get("kurzname"), "ort": (k.get("lieferort") or k.get("ort") or "").strip(),
                                  "email": k.get("email") or ""},
                        "unterschrift": {x: u.get(x) for x in ("name", "ort", "zeit")} if u else None, "pdf": b.get("pdf")}
            if methode == "POST":
                erg = beleg_unterschreiben(con, rid, daten or {}, dict(benutzer.aktuell() or {}).get("login") or "")
                return {"ok": True, "pdf": erg.get("pdf"), "pdf_fehler": erg.get("pdf_fehler")}
            raise ApiFehler("Unbekannte Anfrage", 404)
        if res == "projekte":
            try:
                erg = projekte.api(con, methode, teile, q, daten)
            except projekte.Fehler as f:
                raise ApiFehler(str(f), f.code)
            return erg
        if res == "montage" and rid and unter == "mail":
            return montage_mail(con, methode, rid, daten or {})
        if res == "montage":
            ich = dict(benutzer.aktuell() or {})
            ma = con.execute("SELECT * FROM mitarbeiter WHERE id=?", (ich.get("mitarbeiter_id") or 0,)).fetchone()
            try:
                return montage.api(con, methode, teile, q, daten, ich.get("login") or "intern", dict(ma) if ma else None)
            except (montage.Fehler, material.Fehler) as f:
                raise ApiFehler(str(f), getattr(f, "code", 400))
        if res == "arbeitsschutz":
            try:
                return arbeitsschutz_api(con, methode, teile, q, daten)
            except (arbeitsschutz.Fehler, unterschrift.Fehler) as f:
                raise ApiFehler(str(f), f.code)
        if res == "werkzeuge":
            try:
                return werkzeuge.api(con, methode, teile, q, daten)
            except werkzeuge.Fehler as f:
                raise ApiFehler(str(f), f.code)
        if res == "xml":
            if teile[1:] == ["pruefung"] and methode == "GET":
                return epruefung.verfuegbar()
            if teile[1:] == ["einrichten"] and methode == "POST":
                if not benutzer.ist_inhaber():
                    raise ApiFehler("Die Einrichtung der Prüfung darf nur der Inhaber starten.", 403)
                return epruefung.einrichten_starten()
            erg = xml_api(con, methode, teile, q, daten or {})
            roh = erg.pop("_roh", None) if isinstance(erg, dict) else None
            if isinstance(erg, dict) and erg.get("xml"):
                try:
                    erg["ansicht_html"], erg["ansicht_grund"] = epruefung.ansicht_html(roh or erg["xml"].encode("utf-8"))
                except Exception as f:  # noqa: BLE001
                    erg["ansicht_html"], erg["ansicht_grund"] = None, str(f)
                try:
                    erg["offiziell"] = epruefung.pruefen(roh or erg["xml"].encode("utf-8"))
                except Exception as f:  # noqa: BLE001
                    erg["offiziell"] = {"moeglich": False, "grund": f"Prüfung nicht möglich: {f}"}
            return erg
        if res == "rechnungspost":
            return rechnungspost_api(con, methode, teile, q, daten or {})
        if res == "eingang" and len(teile) == 2 and methode == "POST":
            if teile[1] == "lesen":
                return eingang_lesen(con, daten or {})
            if teile[1] == "buchen":
                return eingang_buchen(con, daten or {})
        if res in ("material", "materialsets", "lager", "auftragskosten"):
            try:
                # Ins Protokoll kommen die Eingriffe in den Bestand, die keine gewöhnliche Bewegung sind: Inventur und gelöschte Buchung.
                # Zu- und Abgänge stehen fortlaufend in der Bewegungsliste des Lagers.
                if res == "lager" and methode == "POST" and (daten or {}).get("art") == "inventur":
                    vor = con.execute("SELECT nummer, bezeichnung, einheit, bestand, lagerpreis FROM material WHERE id=?", (int((daten or {}).get("material_id") or 0),)).fetchone()
                    erg_m = material.api(con, methode, teile, q, daten)
                    if vor:
                        prot(con, "lager_inventur", vor["nummer"], f"Inventur {vor['nummer']} {(vor['bezeichnung'] or '').splitlines()[0]}: Bestand {de(vor['bestand'] or 0, 3)} → "
                             f"{de(erg_m['bestand'] or 0, 3)} {vor['einheit']}" + (f" ({daten['bemerkung']})" if (daten or {}).get("bemerkung") else ""),
                             {"alt": vor["bestand"], "neu": erg_m["bestand"], "lagerpreis": vor["lagerpreis"]})
                    return erg_m
                if res == "auftragskosten" and methode == "DELETE" and len(teile) == 2 and teile[1].isdigit():
                    vor = con.execute("SELECT k.*, a.nummer AS auftrag FROM auftragskosten k LEFT JOIN auftraege a ON a.id=k.auftrag_id WHERE k.id=?", (int(teile[1]),)).fetchone()
                    erg_m = material.api(con, methode, teile, q, daten)
                    if vor and vor["lager_abgang"]:
                        prot(con, "lager_buchung_geloescht", vor["auftrag"] or "", f"Lagerabgang gelöscht und zurückgebucht: {de(vor['menge'], 3)} {vor['einheit']} {vor['bezeichnung']} "
                             f"vom {de_datum(vor['datum'])}, Auftrag {vor['auftrag'] or '–'}", dict(vor))
                    return erg_m
                return material.api(con, methode, teile, q, daten)
            except material.Fehler as f:
                raise ApiFehler(str(f), f.code)

        # ---------- Einstellungen ----------
        if res == "service":
            cfg = service_cfg(con)
            try:
                if methode == "GET" and teile[1:] == ["infos"]:
                    return service.infos(con, cfg)
                if methode == "GET" and teile[1:] == ["sicherungen"]:
                    return {"liste": service.sicherungen(cfg), "extern": service.externe_sicherungen(cfg) if q.get("extern") == "1" else [],
                            "ziel": cfg["ziel"], "pfad": cfg["backup"],
                            "kennwort": {"gesetzt": tresor.aktiv(DATEN), "lesbar": bool(tresor.laden(DATEN))}}
                if methode == "POST" and teile[1:] == ["kennwort"]:
                    # Sicherungskennwort setzen, ändern, prüfen oder entfernen (nur Inhaber; das bisherige Kennwort wird verlangt)
                    if not benutzer.ist_inhaber():
                        raise ApiFehler("Das Sicherungskennwort verwaltet nur der Inhaber.", 403)
                    d = daten or {}
                    try:
                        if d.get("pruefen"):
                            return {"stimmt": tresor.kennwort_stimmt(DATEN, str(d.get("kennwort") or ""))}
                        if tresor.laden(DATEN) and not tresor.kennwort_stimmt(DATEN, str(d.get("alt") or "")):
                            raise ApiFehler("Das bisherige Sicherungskennwort stimmt nicht.")
                        if d.get("entfernen"):
                            tresor.entfernen(DATEN)
                            prot(con, "sicherung_kennwort", "", "Sicherungskennwort entfernt – Sicherungen auf dem externen Ziel werden wieder unverschlüsselt abgelegt")
                            return {"gesetzt": False}
                        neu = str(d.get("kennwort") or "")
                        if neu != str(d.get("kennwort2") or ""):
                            raise ApiFehler("Die beiden Eingaben des Kennworts stimmen nicht überein.")
                        war = tresor.aktiv(DATEN)
                        tresor.setzen(DATEN, neu)
                        if not war:   # vorhandene lesbare Kopien auf dem externen Ziel im Hintergrund verschlüsseln
                            threading.Thread(target=lambda: print("Externe Sicherungen nachträglich verschlüsselt:", service.extern_nachverschluesseln(cfg)), daemon=True).start()
                        prot(con, "sicherung_kennwort", "", "Sicherungskennwort geändert" if war else
                             "Sicherungskennwort gesetzt – Sicherungen auf dem externen Ziel werden ab jetzt verschlüsselt abgelegt")
                        return {"gesetzt": True}
                    except tresor.Fehler as f:
                        raise ApiFehler(str(f))
                if len(teile) > 1 and teile[1] == "projektsicherung":
                    ps, pcfg = projektsicherung, {**cfg, "projektpfad": (cfg["projektpfad"] or "").strip()}
                    ein = ps.einstellung(einstellungen(con).get("projektsicherung"))
                    wer = dict(benutzer.aktuell() or {}).get("login") or "Programm"
                    d = daten or {}
                    try:
                        if methode == "GET" and len(teile) == 2:
                            try:
                                st = ps.staende(pcfg)
                            except ps.Fehler:
                                st = []
                            return {"einstellung": ein, "status": ps.status(DATEN), "lauf": {k: v for k, v in ps.LAUF.items()}, "staende": st,
                                    "projektpfad": pcfg["projektpfad"], "ziel": cfg["ziel"], "ordner": os.path.join(cfg["ziel"], ps.ORDNER) if cfg["ziel"] else "",
                                    "kennwort": {"gesetzt": tresor.aktiv(DATEN), "lesbar": bool(tresor.laden(DATEN))}}
                        if not benutzer.ist_inhaber():
                            raise ApiFehler("Die Sicherung des Projektordners verwaltet nur der Inhaber.", 403)
                        if methode == "GET" and teile[2:] == ["inhalt"]:
                            return ps.inhalt(pcfg, q.get("stand") or "", q.get("pfad") or "")
                        if methode == "POST" and teile[2:] == ["einstellung"]:
                            neu = ps.einstellung({**ein, **{k: d[k] for k in ("aktiv", "uhrzeit", "tage", "warn_tage") if k in d}})
                            if neu["aktiv"] and not ein["aktiv"]:
                                ps._pruefen(pcfg)   # noqa: SLF001 – Projektordner und Ziel müssen erreichbar sein
                                ps._status_schreiben(DATEN, eingeschaltet=jetzt())   # noqa: SLF001
                            con.execute("INSERT OR REPLACE INTO einstellungen (schluessel, wert) VALUES ('projektsicherung', ?)", (json.dumps(neu),))
                            if neu != ein:
                                prot(con, "projektsicherung", "", f"Sicherung des Projektordners: {'täglich ab ' + neu['uhrzeit'] + ' Uhr' if neu['aktiv'] else 'automatischer Lauf aus'}, "
                                     f"frühere Fassungen {'unbegrenzt' if not neu['tage'] else str(neu['tage']) + ' Tage'}", neu)
                            return neu
                        if methode == "POST" and teile[2:] == ["start"]:
                            ps._pruefen(pcfg)   # noqa: SLF001
                            if ps.LAUF["laeuft"]:
                                raise ApiFehler("Es läuft bereits eine Sicherung oder Wiederherstellung des Projektordners.")
                            threading.Thread(target=projekt_sichern, args=("von Hand gestartet", wer), daemon=True).start()
                            return {"ok": True}
                        if methode == "POST" and teile[2:] == ["abbrechen"]:
                            ps.LAUF["abbruch"] = True
                            return {"ok": True}
                        if methode == "POST" and teile[2:] == ["wiederherstellen"]:
                            stand, pfad, kw = str(d.get("stand") or ""), str(d.get("pfad") or ""), str(d.get("kennwort") or "")
                            if ps.LAUF["laeuft"]:
                                raise ApiFehler("Es läuft bereits eine Sicherung oder Wiederherstellung des Projektordners.")
                            try:
                                ps.kennwort_pruefen(pcfg, stand, pfad, kw or None)
                            except tresor.Fehler as f:
                                if str(f) == "KENNWORT_NOETIG":
                                    raise ApiFehler("Für diese Sicherung wird das Sicherungskennwort gebraucht.", 428)
                                raise ApiFehler(str(f))
                            prot(con, "projektsicherung", pfad, f"Aus der Sicherung des Projektordners zurückgeholt: {pfad or 'alles'} (Stand {stand}) "
                                 f"in den Unterordner {ps.WIEDER}", {"stand": stand, "pfad": pfad})
                            threading.Thread(target=lambda: ps.wiederherstellen(pcfg, stand, pfad, kw or None), daemon=True).start()
                            return {"ok": True}
                    except ps.Fehler as f:
                        raise ApiFehler(str(f))
                    except OSError as f:
                        raise ApiFehler(f"Nicht möglich: {f.strerror or f}")
                if methode == "POST" and teile[1:] == ["zertifikat"]:
                    # https-Zertifikat: an diesem PC als vertrauenswürdig eintragen bzw. neu ausstellen (nur Inhaber, nur am Büro-PC)
                    if not benutzer.ist_inhaber():
                        raise ApiFehler("Das Zertifikat verwaltet nur der Inhaber.", 403)
                    nur_am_pc("Das Zertifikat einrichten")
                    if not HTTPS["aktiv"]:
                        raise ApiFehler("https ist nicht eingeschaltet.")
                    if (daten or {}).get("neu"):
                        if HTTPS.get("eigen"):
                            raise ApiFehler("Es ist ein eigenes Zertifikat hinterlegt (daten/zertifikat/eigen.pem). Die Büro-CA wird dabei nicht benutzt.")
                        stand = zertifikat_neu()
                        prot(con, "zertifikat", "https", "https: Büro-CA und Server-Zertifikat neu ausgestellt – Geräte müssen das Zertifikat neu einrichten")
                    else:
                        stand = zertifikat_am_pc(erneut=True)
                    return {"am_pc": stand, "fingerabdruck": __import__("zert").fingerabdruck(DATEN)}
                if methode == "POST" and teile[1:] == ["sicherung"]:
                    erg = service.sicherung_erstellen(cfg)
                    prot(con, "sicherung", erg["name"], f"Vollständige Sicherung {erg['name']} ({erg['groesse']})" + (f", Kopie nach {erg['extern']}" if erg.get("extern") else ""), erg)
                    return erg
                if methode == "GET" and teile[1:] == ["exporte"]:
                    return {"liste": export.liste(), "luecken": export.nummern_luecken(con, f"{date.today().year}-01-01", date.today().isoformat())}
                if methode == "POST" and teile[1:] == ["datev"]:
                    d = daten or {}
                    con.commit()
                    erg = export.datev_export(con, d.get("von"), d.get("bis"), ich_login())
                    prot(con, "export", erg["datei"], f"DATEV-Buchungsstapel {de_datum(d.get('von'))} bis {de_datum(d.get('bis'))} erstellt: {erg['datei']} "
                         f"({erg['buchungen']} Buchungen)", {k: v for k, v in erg.items() if k != "groesse"})
                    return erg
                if methode == "GET" and teile[1:] == ["datev"]:
                    c = export.datev_cfg(einstellungen(con))
                    return {**c, "texte": export.DATEV_KONTEN_TEXT, "standard": export.DATEV_KONTEN[c["skr"]]}
                if methode == "POST" and teile[1:] in (["belegpaket"], ["pruefer"]):
                    d = daten or {}
                    wer = dict(benutzer.aktuell() or {}).get("login") or ""
                    con.commit()
                    try:
                        erg = (export.belegpaket if teile[1] == "belegpaket" else export.pruefer_export)(con, d.get("von"), d.get("bis"), wer)
                    except export.Fehler as f:
                        raise ApiFehler(str(f), f.code)
                    art = "Belegpaket" if teile[1] == "belegpaket" else "Datenträgerüberlassung (Beschreibungsstandard)"
                    prot(con, "export", erg["datei"], f"{art} {de_datum(d.get('von'))} bis {de_datum(d.get('bis'))} erstellt: {erg['datei']}",
                         {k: v for k, v in erg.items() if k != "groesse"})
                    return erg
                if methode == "GET" and teile[1:] == ["protokoll"]:
                    voll = q.get("voll") == "1"
                    pr = protokoll.pruefen(con, voll=voll)
                    if not pr["ok"]:
                        PROTOKOLL_PRUEFUNG["text"] = "Die Prüfung des Änderungsprotokolls hat Unstimmigkeiten gefunden. Details unter Einstellungen › Service › Protokoll."
                    elif voll:
                        PROTOKOLL_PRUEFUNG["text"] = ""
                    if voll or not BELEG_PRUEFUNG["ergebnis"]:
                        belege_pruefen(con)
                    return {"eintraege": protokoll.liste(con, q.get("art"), q.get("von"), q.get("bis"), q.get("q")),
                            "pruefung": pr, "belege": BELEG_PRUEFUNG["ergebnis"], "arten": protokoll.ARTEN, "echtbetrieb": protokoll.echtbetrieb(con)}
                if methode == "POST" and teile[1:] == ["echtbetrieb"]:
                    if not benutzer.ist_inhaber():
                        raise ApiFehler("Den Echtbetrieb startet nur der Inhaber.", 403)
                    if protokoll.echtbetrieb(con):
                        raise ApiFehler("Der Echtbetrieb läuft bereits.")
                    if ((daten or {}).get("bestaetigung") or "").strip().upper() != "ECHTBETRIEB":
                        raise ApiFehler("Bitte zur Bestätigung ECHTBETRIEB eintippen.")
                    testprot = ""
                    if (daten or {}).get("protokoll_neu"):
                        # Protokoll der Testphase abschließen: nur, wenn keine festgeschriebene Rechnung mehr da ist – deren Nachweis steht im Protokoll
                        if con.execute("SELECT 1 FROM belege WHERE status IN ('fest','storniert') LIMIT 1").fetchone():
                            raise ApiFehler("Es gibt noch festgeschriebene oder stornierte Rechnungen aus der Testphase. Ihr Nachweis steht im Protokoll; "
                                            "bitte zuerst die Testdaten löschen oder das Protokoll behalten.")
                        con.commit()
                        sich = service.sicherung_erstellen(cfg, "vor-Echtbetrieb")
                        n_p, datei_p = protokoll.neu_beginnen(con)
                        testprot = (f" Das Protokoll der Testphase ({n_p} Einträge) wurde abgeschlossen und liegt als {datei_p or '–'} im Ordner daten/protokoll "
                                    f"sowie in der Sicherung {sich['name']}; dieses Protokoll beginnt neu.")
                    nr = rechnungsnummer_info(con)
                    n_alt = altbestand_sperren(con)
                    prot(con, "echtbetrieb", "", f"Echtbetrieb begonnen. „Testdaten löschen“ ist ab jetzt dauerhaft gesperrt. Nächste Rechnungsnummer {nr['naechste']}. "
                         f"{n_alt} vorhandene Kunden als Altbestand bis {de_datum(altbestand_frist())} gesperrt." + testprot,
                         {"naechste_rechnung": nr["naechste"], "belege": con.execute("SELECT COUNT(*) FROM belege").fetchone()[0], "altbestand": n_alt})
                    return {"echtbetrieb": protokoll.echtbetrieb(con)}
                if methode == "POST" and teile[1:] == ["ruecksichern"]:
                    if not benutzer.ist_inhaber():
                        raise ApiFehler("Rücksichern darf nur der Inhaber.", 403)
                    grund = ((daten or {}).get("grund") or "").strip()
                    if protokoll.echtbetrieb(con) and len(grund) < 10:
                        raise ApiFehler("Im Echtbetrieb bitte den Grund der Rücksicherung angeben (mindestens 10 Zeichen) – er wird im Protokoll festgehalten.")
                    name = (daten or {}).get("name") or ""
                    ort, kennwort = str((daten or {}).get("ort") or ""), str((daten or {}).get("kennwort") or "")
                    try:   # vorab prüfen, damit ein falsches Kennwort keinen Protokolleintrag „gestartet“ hinterlässt
                        pf = service.sicherung_pfad(cfg, name, ort)
                        if name.endswith(tresor.ENDUNG) and not tresor.pruefen(pf, tresor.schluessel_fuer(pf, DATEN, kennwort or None)):
                            raise ApiFehler("Das Sicherungskennwort stimmt nicht oder die Sicherungsdatei ist beschädigt.")
                    except service.Fehler as f:
                        raise ApiFehler(str(f))
                    except tresor.Fehler as f:
                        if str(f) == "KENNWORT_NOETIG":
                            raise ApiFehler("Für diese Sicherung wird das Sicherungskennwort gebraucht.", 428)
                        raise ApiFehler(str(f))
                    prot(con, "ruecksicherung", name, f"Rücksicherung von {name} gestartet" + (f". Grund: {grund}" if grund else ""), {"sicherung": name, "grund": grund})
                    con.commit()
                    try:
                        erg = service.ruecksichern(cfg, name, init_db, kennwort or None, ort)
                    except service.Fehler as f:
                        raise ApiFehler(str(f))
                    with verbindung() as c2:
                        protokoll.einrichten(c2, DATEN, VERSION)   # Einträge nach dem Sicherungszeitpunkt aus dem Journal nachtragen
                        prot(c2, "ruecksicherung", name, f"Rücksicherung von {name} abgeschlossen; der Stand vorher liegt in {erg['vorher']}", erg)
                    return erg
                if methode == "GET" and teile[1:] == ["relationen"]:
                    return service.relationen(con, cfg)
                if methode == "POST" and teile[1:] == ["relationen", "loesen"]:
                    if not benutzer.ist_inhaber():
                        raise ApiFehler("Verweise lösen darf nur der Inhaber.", 403)
                    erg = service.verweise_loesen(con)
                    if erg:
                        prot(con, "relationen", "", "Relationencheck: verwaiste Verweise gelöst (Verknüpfung geleert, Datensätze bleiben)", erg)
                    return {"ok": True, "geloest": erg}
                if methode == "POST" and teile[1:] == ["optimieren"]:
                    if not benutzer.ist_inhaber():
                        raise ApiFehler("Die Datenbank optimiert nur der Inhaber.", 403)
                    erg = db_optimieren(con)
                    prot(con, "datenbank", "", f"Datenbank geprüft und optimiert ({erg['vorher'] / 1e6:.1f} MB → {erg['nachher'] / 1e6:.1f} MB)".replace(".", ","), erg)
                    return erg
                if methode == "GET" and teile[1:] == ["testdaten"]:
                    return testdaten_vorschau(con)
                if methode == "POST" and teile[1:] == ["testdaten"]:
                    if not benutzer.ist_inhaber():
                        raise ApiFehler("Testdaten löschen darf nur der Inhaber.", 403)
                    # Echtbetrieb-Sperre auch dann, wenn eine ältere Sicherung zurückgespielt wurde (Journaldatei)
                    d = daten or {}
                    if (d.get("bestaetigung") or "").strip().upper() != "LÖSCHEN":
                        raise ApiFehler("Bitte zur Bestätigung LÖSCHEN eintippen.")
                    eb = protokoll.echtbetrieb(con)
                    if eb:
                        raise ApiFehler(f"Gesperrt: Der Echtbetrieb läuft seit {de_datum(eb['seit'][:10])}. Im Echtbetrieb dürfen keine Daten gelöscht werden (GoBD).", 403)
                    vorher_nr = testdaten_vorschau(con)
                    con.commit()
                    sich = service.sicherung_erstellen(cfg, "vor-Testdaten-Loeschen")
                    erg = testdaten.testdaten_loeschen(con, d.get("gruppen") or [], bool(d.get("zaehler")), d.get("behalten") or [])
                    con.commit()
                    try:
                        con.execute("VACUUM")
                    except sqlite3.Error:
                        pass
                    erg["sicherung"] = sich["name"]
                    erg["nummern"] = testdaten_vorschau(con)["nummern"]
                    prot(con, "testdaten_geloescht", ", ".join(erg.get("gruppen") or []),
                         f"Testdaten gelöscht ({', '.join(erg.get('gruppen') or [])}). Sicherung vorher: {sich['name']}. "
                         f"Nächste Rechnungsnummer vorher {vorher_nr['nummern'].get('rechnung')}, jetzt {erg['nummern'].get('rechnung')}.",
                         {"gruppen": erg.get("gruppen"), "geloescht": erg.get("geloescht"), "sicherung": sich["name"],
                          "nummern_vorher": vorher_nr["nummern"], "nummern_nachher": erg["nummern"], "zaehler_zurueckgesetzt": bool(d.get("zaehler"))})
                    con.commit()
                    return erg
            except service.Fehler as f:
                raise ApiFehler(str(f))
            except OSError as f:
                raise ApiFehler(f"Datei-Fehler: {f}")
        if res == "bildvarianten" and methode == "GET":
            return {"varianten": BILD_VARIANTEN, "max_hoehe": BILD_MAX_HOEHE, "bilder": bilder_ohne_varianten(con)}
        if res == "bildvarianten" and methode == "POST":
            d = daten or {}
            bild_variante_speichern(d.get("datei"), d.get("art"), d.get("daten"))
            return {"ok": True}
        if res == "autostart" and methode == "POST":
            return autostart_setzen(con, bool((daten or {}).get("aktiv")), bool((daten or {}).get("fenster")))
        if res == "beenden" and methode == "POST":
            print("Beendet über die Oberfläche")
            def aus():
                try:
                    if os.name == "nt" and "tray" in sys.modules and sys.modules["tray"].beenden():
                        return
                except Exception:  # noqa: BLE001
                    pass
                os._exit(0)
            threading.Timer(0.4, aus).start()
            return {"ok": True}

        if res == "einstellungen":
            if methode == "GET":
                return einstellungen_oeffentlich(con)
            if methode == "PUT":
                if "sicherung_ziel" in daten:   # neues Sicherungsziel: heutige Datenbanksicherung gleich dorthin kopieren
                    threading.Thread(target=lambda: (time.sleep(2), backup()), daemon=True).start()
                if "rechnung_zusatz" in daten:
                    daten["rechnung_zusatz"] = bereinigen(daten["rechnung_zusatz"])
                if isinstance(daten.get("textbausteine"), list):
                    daten["textbausteine"] = [dict(t, text=bereinigen(t.get("text"))) for t in daten["textbausteine"]]
                if isinstance(daten.get("beleg_texte"), dict):
                    daten["beleg_texte"] = {a: {k: bereinigen(v) for k, v in (t or {}).items()} for a, t in daten["beleg_texte"].items()}
                if isinstance(daten.get("mail"), dict):
                    alt = einstellungen(con).get("mail") or {}
                    neu = {k: v for k, v in daten["mail"].items() if k != "passwort_gesetzt"}
                    if not neu.get("passwort"):
                        neu["passwort"] = alt.get("passwort", "")
                    neu["passwort"] = geheim.verschluesseln(neu["passwort"])   # Windows: DPAPI, nie im Klartext ablegen
                    daten["mail"] = neu
                if isinstance(daten.get("sollplaene"), list):
                    daten["sollplaene"] = personal.plaene_pruefen(daten["sollplaene"])
                for k, v in daten.items():
                    if k in STANDARD_EINSTELLUNGEN:
                        con.execute("INSERT OR REPLACE INTO einstellungen VALUES (?, ?)",
                                    (k, json.dumps(v, ensure_ascii=False)))
                if any(k in daten for k in ("feiertage_wahl", "frei_wahl", "tage_eigene", "sollplaene")):
                    personal.tage_einstellen(einstellungen(con))
                    if "sollplaene" in daten:
                        personal.plaene_uebertragen(con, daten["sollplaene"])
                return einstellungen_oeffentlich(con)
        if res == "zuschnitt" and methode == "POST":
            d = daten or {}
            if d.get("loeschen"):
                if os.path.exists(ZUSCHNITT_DATEI):
                    os.remove(ZUSCHNITT_DATEI)
                return {"vorhanden": False}
            roh = base64.b64decode(d.get("daten") or "")
            if b"<" not in roh[:2000]:
                raise ApiFehler("Das sieht nicht nach einer HTML-Datei aus.")
            with open(ZUSCHNITT_DATEI, "wb") as f:
                f.write(roh)
            return {"vorhanden": True, "name": d.get("dateiname")}
        if res == "zuschnitt" and methode == "GET":
            return {"vorhanden": os.path.exists(ZUSCHNITT_DATEI)}
        if res == "mail" and len(teile) == 2 and teile[1] == "signatur" and methode == "GET":
            e = einstellungen(con)
            lb = logo_bytes()
            src = f"data:{lb[1]};base64," + base64.b64encode(lb[0]).decode() if lb and (e.get("mail") or {}).get("logo_in_signatur", True) else None
            sig = signatur_teile(e)
            return {"html": mailversand.signatur_html(sig, src), "text": mailversand.signatur_text(sig), "teile": sig}
        if res == "mail" and unter is None and len(teile) == 2 and teile[1] == "test" and methode == "POST":
            cfg = dict((einstellungen(con).get("mail") or {}))
            for k, v in (daten or {}).items():
                if k != "passwort" or v:
                    cfg[k] = v
            r = mailversand.senden(cfg, cfg.get("adresse"), "", "Testmail aus Jahresring",
                                   "Diese Testmail zeigt, dass der E-Mail-Versand aus Jahresring funktioniert.", [])
            return r

        # ---------- Positionen, Titel, Auftragskalkulation ----------
        if res == "auftraege" and rid and unter in ("positionen", "kalk", "titel", "sollist") and len(teile) == 3:
            auftrag_laden(con, rid)
            if unter == "positionen" and methode == "GET":
                erg = auftrag_rechnen(con, rid)
                return {"positionen": [pos_ausgabe(p) for p in erg["positionen"]], "titel": erg["titel"],
                        "titel_druck": erg["titel_druck"], "netto": erg["netto"], "titel_summen": erg["titel_summen"],
                        "soll": erg["soll"]}
            if unter == "positionen" and methode == "POST":
                d = daten or {}
                parent = int(d["parent_id"]) if d.get("parent_id") else None
                titel = 0
                if parent:
                    pr = con.execute("SELECT auftrag_id, titel FROM positionen WHERE id=?", (parent,)).fetchone()
                    if not pr or pr["auftrag_id"] != rid:
                        raise ApiFehler("Übergeordnete Position nicht gefunden.")
                    titel = pr["titel"]
                else:
                    titel = zahl(d.get("titel"), int)
                e = einstellungen(con)
                werte = pos_werte(d)
                werte.update({"auftrag_id": rid, "parent_id": parent, "titel": titel,
                              "sort": neue_sortierung(con, rid, parent, titel)})
                if d.get("nach_id"):
                    nach = con.execute("SELECT sort FROM positionen WHERE id=?", (int(d["nach_id"]),)).fetchone()
                    if nach:
                        werte["sort"] = nach["sort"] + 0.5
                werte.setdefault("status", "")  # Status setzt sich mit Angebot, AB, Lieferschein
                werte.setdefault("gruppe", (e.get("positionsgruppen") or [""])[0])
                werte["angelegt"] = werte["geaendert"] = jetzt()
                cur = con.execute(f"INSERT INTO positionen ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})",
                                  list(werte.values()))
                neu_sortieren(con, rid, parent, titel)
                return {"id": cur.lastrowid}
            if unter == "kalk" and methode == "GET":
                k = auftrag_kalk(con, rid)
                return {"kalk": k, "typen": {t: list(v) for t, v in WERKSTOFF_TYPEN.items()}, "lohngruppen": LOHNGRUPPEN,
                        "beschlag_mengen": beschlag_mengen(con, rid),
                        "kostenstellen_vorgabe": vorgaben_kopie(einstellungen(con)).get("kostenstellen", [])}
            if unter == "kalk" and methode == "PUT":
                k = auftrag_kalk(con, rid)
                d = daten or {}
                if d.get("_zuruecksetzen"):
                    v = vorgaben_kopie(einstellungen(con))
                    for teil in d["_zuruecksetzen"]:
                        if teil in v and teil not in ("werkstoffe", "beschlaege"):
                            k[teil] = v[teil]
                if isinstance(d.get("kostenstellen"), list):
                    # Kostenstellen entstehen nur in den Einstellungen – im Auftrag nur Kopien davon
                    erlaubt = {x.get("kst") for x in vorgaben_kopie(einstellungen(con)).get("kostenstellen", [])} | {x.get("kst") for x in k.get("kostenstellen", [])}
                    fremd = [x.get("kst") for x in d["kostenstellen"] if isinstance(x, dict) and x.get("kst") not in erlaubt]
                    if fremd:
                        raise ApiFehler("Kostenstellen werden nur in den Einstellungen angelegt: " + ", ".join(map(str, fremd)))
                for key in KALK_VORGABEN:
                    if key in d:
                        k[key] = d[key]
                if isinstance(d.get("taetigkeit_listen"), list):   # auftragsspezifische Tätigkeitslisten
                    k["taetigkeit_listen"] = d["taetigkeit_listen"]
                con.execute("UPDATE auftraege SET kalk=?, geaendert=? WHERE id=?",
                            (json.dumps(k, ensure_ascii=False), jetzt(), rid))
                return {"kalk": k}
            if unter == "titel" and methode == "PUT":
                d = daten or {}
                if "titel" in d:
                    titel = [{"nr": int(t["nr"]), "name": str(t.get("name") or "").strip(), "gesperrt": bool(t.get("gesperrt")),
                              "buchung_gesperrt": bool(t.get("buchung_gesperrt"))} for t in d["titel"]]
                    con.execute("UPDATE auftraege SET titel=? WHERE id=?", (json.dumps(titel, ensure_ascii=False), rid))
                if "titel_druck" in d:
                    con.execute("UPDATE auftraege SET titel_druck=? WHERE id=?", (d["titel_druck"], rid))
                t, td = auftrag_titel(con, rid)
                return {"titel": t, "titel_druck": td}
            if unter == "sollist" and methode == "GET":
                return soll_ist(con, rid, q.get("titel"))

        if res == "positionen" and rid is None and len(teile) == 2 and teile[1] == "suche" and methode == "GET":
            return positionen_suchen(con, q)
        if res == "positionen" and rid:
            if not con.execute("SELECT 1 FROM positionen WHERE id=?", (rid,)).fetchone():
                raise ApiFehler("Position nicht gefunden", 404)
            p = pos_dict(con.execute("SELECT * FROM positionen WHERE id=?", (rid,)).fetchone())
            if methode == "GET" and unter is None:
                return position_antwort(con, rid)
            if methode == "PUT" and unter is None:
                if isinstance((daten or {}).get("zeiten"), list):
                    daten["zeiten"] = zeiten_fixieren(einstellungen(con), {**p, "zeitmodus": daten.get("zeitmodus", p.get("zeitmodus"))}, daten["zeiten"],
                                                      set(kalkulation.bezug_alle(auftrag_kalk(con, p["auftrag_id"]).get("bezug_eigen"))))
                werte = pos_werte(daten or {})
                werte.pop("parent_id", None)
                if werte:
                    werte["geaendert"] = jetzt()
                    con.execute(f"UPDATE positionen SET {','.join(f'{k}=?' for k in werte)} WHERE id=?",
                                list(werte.values()) + [rid])
                    if "titel" in werte and not p["parent_id"]:
                        con.execute("UPDATE positionen SET sort=? WHERE id=?",
                                    (neue_sortierung(con, p["auftrag_id"], None, werte["titel"]), rid))
                return position_antwort(con, rid)
            if methode == "DELETE" and unter is None:
                position_loeschen(con, rid)
                return {"ok": True, "auftrag_id": p["auftrag_id"], "parent_id": p["parent_id"]}
            if methode == "POST" and unter == "bild":
                d = daten or {}
                p = con.execute("SELECT bilder FROM positionen WHERE id=?", (rid,)).fetchone()
                if not p:
                    raise ApiFehler("Position nicht gefunden", 404)
                liste = jl(p["bilder"], [])
                datei = bild_speichern(d.get("daten") or "", d.get("dateiname") or "")
                for art, v in (d.get("varianten") or {}).items():
                    if v:
                        bild_variante_speichern(datei, art, v)
                liste.append({"datei": datei,
                              "name": os.path.basename(d.get("dateiname") or "Bild"), "groesse": d.get("groesse") or "mittel",
                              "text": "", "drucken": True})
                con.execute("UPDATE positionen SET bilder=?, geaendert=? WHERE id=?", (json.dumps(liste, ensure_ascii=False), jetzt(), rid))
                return position_antwort(con, rid)
            if methode == "POST" and unter == "vorlage":
                return vorlage_anwenden(con, p, daten or {})
            if methode == "POST" and unter == "als-vorlage":
                return vorlage_aus_position(con, p, daten or {})
            if methode == "GET" and unter == "konstruktion":
                return konstruktion_dateien(con, p["auftrag_id"], q.get("datei"))
            if methode == "POST" and unter == "stueckliste-import":
                d = daten or {}
                kalk = auftrag_kalk(con, p["auftrag_id"])
                erw = d.get("erweitert") if d.get("erweitert") in (True, False) else None
                try:
                    if not d.get("ausfuehren"):
                        return stuecklistenimport.vorschau(con, d.get("text") or "", erw)
                    stueck, bs, posz, angelegt, n_t, n_b = stuecklistenimport.importieren(
                        con, kalk, p, d.get("text") or "", d.get("zuordnung") or {}, erw, bool(d.get("ersetzen")))
                except stuecklistenimport.Fehler as f:
                    raise ApiFehler(str(f))
                except material.Fehler as f:
                    raise ApiFehler(str(f))
                con.execute("UPDATE auftraege SET kalk=? WHERE id=?", (json.dumps(kalk, ensure_ascii=False), p["auftrag_id"]))
                werte = {"stueckliste": json.dumps(stueck, ensure_ascii=False), "beschlaege": json.dumps(bs, ensure_ascii=False), "geaendert": jetzt()}
                if posz and d.get("position_uebernehmen"):
                    if not klartext_leer(p.get("text")) and not d.get("text_ersetzen"):
                        pass
                    else:
                        werte["text"] = posz["text"]
                    werte["menge"] = posz["menge"]
                    masse = dict(p.get("masse") or {})
                    masse.update({"h": posz["h"], "b": posz["b"], "t": posz["t"]})
                    masse.setdefault("art", "HBT")
                    werte["masse"] = json.dumps(masse)
                con.execute(f"UPDATE positionen SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [rid])
                if d.get("cad_datei"):
                    cad_vermerken(con, p["auftrag_id"], d["cad_datei"], "importiert", rid)
                erg = position_antwort(con, rid)
                erg["import"] = {"teile": n_t, "beschlaege": n_b, "angelegt": angelegt}
                return erg
            if methode == "POST" and unter == "kopieren":
                neu = position_kopieren(con, rid)
                neu_sortieren(con, p["auftrag_id"], p["parent_id"], p["titel"])
                return {"id": neu}
            if methode == "POST" and unter == "einordnen":
                return position_einordnen(con, p, daten or {})
            if methode == "POST" and unter == "verschieben":
                ids = neu_sortieren(con, p["auftrag_id"], p["parent_id"], p["titel"])
                i = ids.index(rid)
                j = i + (1 if (daten or {}).get("richtung", 1) > 0 else -1)
                if 0 <= j < len(ids):
                    ids[i], ids[j] = ids[j], ids[i]
                    for n, x in enumerate(ids, 1):
                        con.execute("UPDATE positionen SET sort=? WHERE id=?", (n, x))
                return {"ok": True}
            if methode == "POST" and unter == "taetigkeiten":
                d = daten or {}
                e = einstellungen(con)
                if d.get("katalog"):
                    # einzelne Tätigkeiten aus dem Katalog anhängen
                    kat = {t.get("id"): t for t in taet_katalog(e)}
                    neu = [dict({k: v for k, v in kat[i].items() if k != "id"}, tid=i, gruppe=kat[i].get("gruppe") or "") for i in d["katalog"] if i in kat]
                    con.execute("UPDATE positionen SET zeiten=?, zeitmodus='taetigkeiten', geaendert=? WHERE id=?",
                                (json.dumps(p["zeiten"] + neu, ensure_ascii=False), jetzt(), rid))
                    return position_antwort(con, rid)
                listen = (auftrag_kalk(con, p["auftrag_id"]).get("taetigkeit_listen") or []) if d.get("quelle") == "auftrag" else taet_listen(e)
                try:
                    liste = listen[int(d.get("liste") or 0)]
                except (ValueError, IndexError):
                    raise ApiFehler("Tätigkeitsliste nicht gefunden")
                neu = [dict(t, gruppe=t.get("gruppe") or "") for t in liste.get("zeiten") or []]
                if d.get("ersetzen"):
                    zeiten = neu
                else:
                    vorhanden = {(z.get("kst"), z.get("name")) for z in p["zeiten"]}
                    zeiten = p["zeiten"] + [t for t in neu if (t.get("kst"), t.get("name")) not in vorhanden]
                modus = liste.get("modus") or "taetigkeiten"
                con.execute("UPDATE positionen SET zeiten=?, zeitmodus=?, geaendert=? WHERE id=?",
                            (json.dumps(zeiten, ensure_ascii=False), modus, jetzt(), rid))
                return position_antwort(con, rid)
            if methode == "POST" and unter == "runden":
                a = position_antwort(con, rid)["position"]["calc"]
                modus = (daten or {}).get("modus", "auf")
                schritt = fl((daten or {}).get("schritt") or 1)
                # auf 6 Stellen runden, damit z. B. 100,00 nicht als 99,9999… auf 99 abgerundet wird
                ziel = (math.ceil if modus == "auf" else math.floor)(round(a["ep_gesamt"] / schritt, 6)) * schritt
                ep = round(ziel - a["unter_ep"], 2)
                con.execute("UPDATE positionen SET einzelpreis=?, preis_manuell=1, geaendert=? WHERE id=?", (ep, jetzt(), rid))
                return position_antwort(con, rid)
            if methode == "POST" and unter == "berechnen":
                con.execute("UPDATE positionen SET preis_manuell=0, geaendert=? WHERE id=?", (jetzt(), rid))
                return position_antwort(con, rid)

        # ---------- Stunden (Ist-Zeiten) ----------
        if res == "stunden":
            if methode == "GET":
                sql = ("SELECT s.*, t.typ AS termin_typ, t.titel AS termin_titel, t.von AS termin_von, t.bis AS termin_bis "
                       "FROM stunden s LEFT JOIN termine t ON t.id=s.termin_id WHERE ")
                if q.get("termin"):
                    return zeilen(con.execute(sql + "s.termin_id=? ORDER BY s.datum DESC, s.id DESC", (int(q["termin"]),)))
                return zeilen(con.execute(sql + "s.auftrag_id=? ORDER BY s.datum DESC, s.id DESC", (int(q.get("auftrag") or 0),)))
            if methode == "POST":
                d = daten or {}
                h = zahl(d.get("stunden"), float)
                if h <= 0:
                    raise ApiFehler("Bitte Stunden eingeben.")
                datum_b = d.get("datum") or date.today().isoformat()
                termin = None
                if d.get("termin_id"):
                    termin = con.execute("SELECT * FROM termine WHERE id=?", (int(d["termin_id"]),)).fetchone()
                    if not termin:
                        raise ApiFehler("Termin nicht gefunden.")
                    aid = termin["auftrag_id"] or (int(d["auftrag_id"]) if d.get("auftrag_id") else None)
                else:
                    aid = int(d["auftrag_id"])
                    if d.get("termin_id") != 0:  # 0 = bewusst ohne Termin
                        termin = con.execute("SELECT * FROM termine WHERE auftrag_id=? AND von<=? AND bis>=? "
                                             "ORDER BY erledigt, von LIMIT 1", (aid, datum_b, datum_b)).fetchone()
                if not aid:
                    raise ApiFehler("Stunden können nur auf Termine mit Auftrag gebucht werden.")
                e = einstellungen(con)
                kst = d.get("kst") or ((e.get("typ_kst") or {}).get(termin["typ"], "") if termin else "")
                gruppe = d.get("gruppe") or auftrag_kalk(con, aid).get("lohnbasis", "")
                titel_nr = titel_buchbar(con, aid, d.get("titel"))
                cur = con.execute("INSERT INTO stunden (auftrag_id, datum, stunden, kst, gruppe, taetigkeit, termin_id, titel, angelegt) "
                                  "VALUES (?,?,?,?,?,?,?,?,?)", (aid, datum_b, h, kst, gruppe, d.get("taetigkeit", ""),
                                                                termin["id"] if termin else None, titel_nr, jetzt()))
                return {"id": cur.lastrowid, "termin_id": termin["id"] if termin else None,
                        "termin": f"{termin['typ']} {termin['von']}" if termin else None}
            if methode == "PUT" and rid:
                d = daten or {}
                if "termin_id" in d:
                    con.execute("UPDATE stunden SET termin_id=? WHERE id=?", (int(d["termin_id"]) if d["termin_id"] else None, rid))
                if "titel" in d:
                    s_alt = con.execute("SELECT auftrag_id, zeit_id FROM stunden WHERE id=?", (rid,)).fetchone()
                    if s_alt:
                        nr = titel_buchbar(con, s_alt["auftrag_id"], d["titel"])
                        con.execute("UPDATE stunden SET titel=? WHERE id=?", (nr, rid))
                        if s_alt["zeit_id"]:
                            con.execute("UPDATE zeiten SET titel=? WHERE id=?", (nr, s_alt["zeit_id"]))
                return {"ok": True}
            if methode == "DELETE" and rid:
                con.execute("DELETE FROM stunden WHERE id=?", (rid,))
                return {"ok": True}

        if res == "cad":
            if methode == "GET" and teile[1:] == ["neu"]:
                return cad_neu(con, int(q["auftrag"]) if str(q.get("auftrag") or "").isdigit() else None)
            if methode == "POST" and teile[1:] == ["ignorieren"]:
                d = daten or {}
                cad_vermerken(con, int(d.get("auftrag_id") or 0), d.get("datei") or "", "ignoriert")
                return {"ok": True}
            raise ApiFehler("Unbekannte Anfrage", 404)
        if res == "positionsvorlagen":
            return positionsvorlagen_api(con, methode, teile, daten or {})
        if res == "kalkvorgaben" and methode == "GET":
            e = einstellungen(con)
            return {"vorgaben": vorgaben_kopie(e), "taetigkeiten": e.get("taetigkeiten") or TAETIGKEITEN_VORGABE,
                    "listen": taet_listen(e),
                    "typen": {t: list(v) for t, v in WERKSTOFF_TYPEN.items()}, "lohngruppen": LOHNGRUPPEN,
                    "bezug": kalkulation.bezug_alle(e.get("bezug_eigen")), "bezug_eigen": e.get("bezug_eigen") or [],
                    "katalog": taet_katalog(e)}

        if res == "vorlagen":
            if methode == "GET":
                return {n: vorlage_dateien(n) for n in VORLAGEN_NAMEN}
            if methode == "POST" and len(teile) == 2 and teile[1] in VORLAGEN_NAMEN:
                name = teile[1]
                seiten = (daten or {}).get("seiten") or []
                if not seiten:
                    raise ApiFehler("Keine Seiten übermittelt.")
                os.makedirs(VORLAGEN_PFAD, exist_ok=True)
                for f in vorlage_dateien(name):
                    os.remove(os.path.join(VORLAGEN_PFAD, f))
                for i, sd in enumerate(seiten, 1):
                    with open(os.path.join(VORLAGEN_PFAD, f"{name}-{i}.png"), "wb") as f:
                        f.write(base64.b64decode(sd))
                orig = os.path.join(VORLAGEN_PFAD, name + ".pdf")
                if os.path.isfile(orig):
                    os.remove(orig)
                if name.startswith("agb") and (daten or {}).get("pdf"):
                    roh = base64.b64decode(daten["pdf"])
                    if roh[:5] == b"%PDF-":
                        with open(orig, "wb") as f:
                            f.write(roh)
                return {"ok": True, "dateien": vorlage_dateien(name)}
            if methode == "DELETE" and len(teile) == 2 and teile[1] in VORLAGEN_NAMEN:
                for f in vorlage_dateien(teile[1]):
                    os.remove(os.path.join(VORLAGEN_PFAD, f))
                if agb_original(teile[1]):
                    os.remove(agb_original(teile[1]))
                return {"ok": True}
        if res == "start" and methode == "GET":
            return start_daten(con, int(q.get("jahr") or date.today().year))
        if res == "suche" and methode == "GET":
            return suche(con, q.get("q"))

        # ---------- Kalender & Termine ----------
        if res == "kalender" and methode == "GET" and len(teile) == 1:
            e = einstellungen(con)
            von = date.fromisoformat(q.get("von") or date.today().isoformat())
            bis = date.fromisoformat(q.get("bis") or plus_tage(von.isoformat(), 42))
            termine = zeilen(con.execute(
                "SELECT t.*, a.nummer AS auftragsnr, a.bezeichnung, a.status, k.kurzname AS kunde, "
                "(SELECT COALESCE(SUM(s.stunden),0) FROM stunden s WHERE s.termin_id=t.id) AS gebucht FROM termine t "
                "LEFT JOIN auftraege a ON a.id=t.auftrag_id LEFT JOIN kunden k ON k.id=a.kunde_id "
                "WHERE t.bis>=? AND t.von<=? ORDER BY t.von, t.zeit_von", (von.isoformat(), bis.isoformat())))
            for t in termine:
                t["geplant"] = round(t["stunden"] if t["stunden"] is not None else
                                     arbeitstage(t["von"], t["bis"]) * fl(e.get("tagesstunden") or 8), 1)
            ende = e.get("status_ende") or []
            auftraege = zeilen(con.execute(
                "SELECT a.id, a.nummer, a.bezeichnung, a.status, a.plan_von, a.plan_bis, a.fertigung, a.lieferung, "
                "k.kurzname AS kunde FROM auftraege a JOIN kunden k ON k.id=a.kunde_id ORDER BY a.nummer"))
            mit_termin = {t["auftrag_id"] for t in termine}
            zeilen_plan = []
            for a in auftraege:
                im_zeitraum = a["plan_von"] and a["plan_von"] <= bis.isoformat() and (a["plan_bis"] or a["plan_von"]) >= von.isoformat()
                if a["status"] in ende and not im_zeitraum and a["id"] not in mit_termin:
                    continue
                try:
                    erg = auftrag_rechnen(con, a["id"])
                    a["soll_stunden"] = round(erg["soll"]["stunden"], 1)
                    a["netto"] = erg["netto"]
                except ApiFehler:
                    a["soll_stunden"], a["netto"] = 0, 0
                r = con.execute("SELECT von, bis, stunden FROM termine WHERE auftrag_id=?", (a["id"],)).fetchall()
                a["geplant_stunden"] = round(sum(t["stunden"] if t["stunden"] is not None else
                                                 arbeitstage(t["von"], t["bis"]) * fl(e.get("tagesstunden") or 8) for t in r), 1)
                a["angebot"] = a["status"] in (e.get("status_angebot") or [])
                a["ist_stunden"] = round(con.execute("SELECT COALESCE(SUM(stunden),0) FROM stunden WHERE auftrag_id=?",
                                                     (a["id"],)).fetchone()[0], 1)
                zeilen_plan.append(a)
            extern, fehler = kal.externe_termine(e.get("google_kalender"), von, bis, neu=q.get("neu") == "1")
            kap = kapazitaet_daten(con, e, von.isoformat(), bis.isoformat(), termine, zeilen_plan)
            erg = {"von": von.isoformat(), "bis": bis.isoformat(), "termine": termine, "auftraege": zeilen_plan, "kapazitaet": kap,
                   "extern": extern, "fehler": fehler, **personal.kalender_eintraege(con, von.isoformat(), bis.isoformat(),
                                                                                      benutzer.darf("personal", 1))}
            return kalender_sicht_anwenden(erg)
        if res == "termine":
            felder = ("auftrag_id", "typ", "titel", "von", "bis", "zeit_von", "zeit_bis", "stunden", "notiz", "erledigt", "mitarbeiter")
            if methode in ("POST", "PUT"):
                d = daten or {}
                w = {k: d[k] for k in felder if k in d}
                if "stunden" in w:
                    w["stunden"] = None if w["stunden"] in (None, "") else zahl(w["stunden"], float)
                if "auftrag_id" in w:
                    w["auftrag_id"] = int(w["auftrag_id"]) if w["auftrag_id"] else None
                if "mitarbeiter" in w:
                    ma = w["mitarbeiter"]
                    if isinstance(ma, str):
                        try:
                            ma = json.loads(ma or "[]")
                        except ValueError:
                            ma = []
                    w["mitarbeiter"] = json.dumps(sorted({int(x) for x in ma or [] if str(x).isdigit()}))
                for k in ("von", "bis"):
                    if k in w:
                        date.fromisoformat(w[k])
                if w.get("von") and w.get("bis") and w["bis"] < w["von"]:
                    w["von"], w["bis"] = w["bis"], w["von"]
            if methode == "POST" and rid is None:
                if not w.get("von"):
                    raise ApiFehler("Bitte ein Datum angeben.")
                w.setdefault("bis", w["von"])
                w["angelegt"] = w["geaendert"] = jetzt()
                cur = con.execute(f"INSERT INTO termine ({','.join(w)}) VALUES ({','.join('?' * len(w))})", list(w.values()))
                return {**dict(con.execute("SELECT * FROM termine WHERE id=?", (cur.lastrowid,)).fetchone()), "warnung": termin_konflikte(con, cur.lastrowid)}
            if methode == "PUT" and rid:
                if w:
                    w["geaendert"] = jetzt()
                    con.execute(f"UPDATE termine SET {','.join(f'{k}=?' for k in w)} WHERE id=?", list(w.values()) + [rid])
                return {**dict(con.execute("SELECT * FROM termine WHERE id=?", (rid,)).fetchone()),
                        "warnung": termin_konflikte(con, rid) if any(k in w for k in ("von", "bis", "mitarbeiter")) else ""}
            if methode == "DELETE" and rid:
                con.execute("UPDATE stunden SET termin_id=NULL WHERE termin_id=?", (rid,))
                con.execute("DELETE FROM termine WHERE id=?", (rid,))
                return {"ok": True}
            if methode == "GET":
                e = einstellungen(con)
                rows = zeilen(con.execute("SELECT t.*, (SELECT COALESCE(SUM(s.stunden),0) FROM stunden s WHERE s.termin_id=t.id) "
                                          "AS gebucht FROM termine t WHERE auftrag_id=? ORDER BY von", (int(q.get("auftrag") or 0),)))
                for t in rows:
                    t["geplant"] = round(t["stunden"] if t["stunden"] is not None else
                                         arbeitstage(t["von"], t["bis"]) * fl(e.get("tagesstunden") or 8), 1)
                return rows
        if res == "kalendertest" and methode == "POST":
            try:
                text = kal.laden((daten or {}).get("url", ""), neu=True)
                heute_d = date.today()
                n = len(kal.ics_parsen(text, datetime.combine(heute_d - timedelta(days=30), datetime.min.time()),
                                       datetime.combine(heute_d + timedelta(days=90), datetime.max.time())))
                return {"ok": True, "anzahl": n}
            except Exception as f:  # noqa
                raise ApiFehler(f"Kalender nicht lesbar: {f}")

        # ---------- Kundenbelege ----------
        if res == "auftraege" and rid and unter == "uebernehmen" and methode == "POST":
            return position_uebernehmen(con, rid, daten or {})
        if res == "auftraege" and rid and unter == "belege" and len(teile) == 3:
            auftrag_laden(con, rid)
            if methode == "GET":
                rows = zeilen(con.execute("SELECT b.id, b.art, b.artname, b.nummer, b.status, b.datum, b.netto, b.brutto, b.zahlbetrag, b.faellig, "
                                          "b.bezug_id, b.pdf, o.offen, json_extract(b.daten, '$.variante.key') AS variante, "
                                          "json_extract(b.druck, '$.konditionen') AS konditionen, json_extract(b.druck, '$.plan_anzahlung') AS plan_anzahlung FROM belege b LEFT JOIN offene_posten o ON o.beleg_id=b.id "
                                          "WHERE b.auftrag_id=? ORDER BY b.datum, b.id", (rid,)))
                for r in rows:
                    r["artname"] = art_name(r)
                    r["ist_rechnung"] = BELEGARTEN.get(r["art"], {}).get("rechnung", False)
                return rows
            if methode == "POST":
                return {"id": beleg_anlegen(con, rid, daten or {})}

        if res == "belege" and rid is None and methode == "GET":
            sql = ("SELECT b.id, b.auftrag_id, b.art, b.artname, b.nummer, b.status, b.datum, b.netto, b.brutto, b.faellig, b.betreff, "
                   "k.kurzname AS kunde, b.kunde_id, a.nummer AS auftragsnr, a.bezeichnung, o.offen FROM belege b "
                   "LEFT JOIN kunden k ON k.id=b.kunde_id LEFT JOIN auftraege a ON a.id=b.auftrag_id "
                   "LEFT JOIN offene_posten o ON o.beleg_id=b.id WHERE 1=1")
            p = []
            if q.get("art"):
                sql += " AND b.art=?"
                p.append(q["art"])
            if q.get("jahr"):
                sql += " AND substr(b.datum,1,4)=?"
                p.append(q["jahr"])
            such = (q.get("q") or "").strip().lower()
            if such:
                sql += " AND (ulower(b.nummer) LIKE ? OR ulower(k.kurzname) LIKE ? OR ulower(b.betreff) LIKE ? OR ulower(a.nummer) LIKE ?)"
                p += [f"%{such}%"] * 4
            rows = zeilen(con.execute(sql + " ORDER BY b.datum DESC, b.id DESC", p))
            for r in rows:
                r["artname"] = art_name(r)
            return rows
        if res == "belege" and rid:
            b = beleg_laden(con, rid)
            if methode == "GET" and unter is None:
                b["auftrag"] = auftrag_laden(con, b["auftrag_id"])
                return b
            if methode == "POST" and unter == "unterschreiben":
                return beleg_unterschreiben(con, rid, daten or {}, dict(benutzer.aktuell() or {}).get("login") or "")
            if methode == "DELETE" and unter == "unterschrift":
                raise ApiFehler("Eine Kundenunterschrift kann nicht entfernt werden. Für Änderungen bitte einen neuen Beleg erstellen.", 403)
            if methode == "PUT" and unter is None:
                if b["status"] in ("fest", "storniert"):
                    raise ApiFehler("Festgeschriebene Belege können nicht mehr geändert werden (GoBD). Bitte stornieren und neu erstellen.")
                d = daten or {}
                plan_k = {"konditionen", "plan_anzahlung", "plan_rest", "plan_wochen"}
                if b["daten"].get("unterschrift") and (set(d) - {"druck"} or plan_k & set(d.get("druck") or {})):
                    raise ApiFehler("Der Beleg ist vom Kunden unterschrieben und kann nicht mehr geändert werden. Für Änderungen bitte einen neuen Beleg erstellen.")
                if b["art"] == "abnahme" and isinstance(d.get("abnahme"), dict):
                    dd = b["daten"]
                    dd["abnahme"] = {"vorbehalt": bool(d["abnahme"].get("vorbehalt")), "maengel": str(d["abnahme"].get("maengel") or ""),
                                     "restarbeiten": str(d["abnahme"].get("restarbeiten") or "")}
                    con.execute("UPDATE belege SET daten=?, geaendert=? WHERE id=?", (json.dumps(dd, ensure_ascii=False), jetzt(), rid))
                werte = {k: (bereinigen(d[k]) if k in ("einleitung", "schluss") else d[k])
                         for k in ("datum", "leistungsdatum", "betreff", "anschrift", "einleitung", "schluss") if k in d}
                if "zahlungsziel" in d:
                    werte["zahlungsziel"] = zahl(d["zahlungsziel"], int)
                if "kompakt" in d:
                    werte["kompakt"] = 1 if d["kompakt"] else 0
                if isinstance(d.get("druck"), dict):
                    alt = jl(con.execute("SELECT druck FROM belege WHERE id=?", (rid,)).fetchone()["druck"], {})
                    werte["druck"] = json.dumps({**alt, **d["druck"]}, ensure_ascii=False)
                if werte:
                    werte["geaendert"] = jetzt()
                    con.execute(f"UPDATE belege SET {','.join(f'{k}=?' for k in werte)} WHERE id=?", list(werte.values()) + [rid])
                    nb = beleg_laden(con, rid)
                    if nb["ist_rechnung"]:
                        con.execute("UPDATE belege SET faellig=? WHERE id=?", (plus_tage(nb["datum"], nb["zahlungsziel"]), rid))
                    if b["art"] == "abschlag" and any(k in d for k in ("prozent", "betrag", "text")):
                        pass
                if b["art"] == "abschlag" and any(k in (d.get("druck") or {}) for k in ("ab_positionen", "ab_summe")):
                    beleg_aktualisieren(con, rid)
                if b["art"] == "rechnung" and "abschlaege_aus" in (d.get("druck") or {}):
                    beleg_aktualisieren(con, rid)
                if b["art"] in FREI_ARTEN and isinstance(d.get("frei"), list):   # Zeilen von Gutschrift/Korrektur ändern
                    dd = beleg_laden(con, rid)["daten"]
                    dd["frei"] = [{"text": str(x.get("text") or "").strip(), "betrag": round(fl(x.get("betrag")), 2)}
                                  for x in d["frei"] if isinstance(x, dict) and (str(x.get("text") or "").strip() or fl(x.get("betrag")))]
                    if not dd["frei"]:
                        raise ApiFehler("Bitte mindestens eine Zeile mit Text und Betrag eingeben.")
                    con.execute("UPDATE belege SET daten=? WHERE id=?", (json.dumps(dd, ensure_ascii=False), rid))
                    beleg_aktualisieren(con, rid)
                if b["art"] == "abschlag" and any(k in d for k in ("prozent", "betrag", "text")):
                    dd = b["daten"]
                    dd["abschlag"] = {"prozent": d.get("prozent"), "betrag": d.get("betrag"), "text": d.get("text")}
                    con.execute("UPDATE belege SET daten=? WHERE id=?", (json.dumps(dd, ensure_ascii=False), rid))
                    beleg_aktualisieren(con, rid)
                return beleg_laden(con, rid)
            if methode == "DELETE" and unter is None:
                if b["daten"].get("unterschrift"):
                    raise ApiFehler("Vom Kunden unterschriebene Belege werden nicht gelöscht.", 403)
                if b["status"] in ("fest", "storniert"):
                    raise ApiFehler("Festgeschriebene Rechnungen dürfen nicht gelöscht werden (GoBD). Bitte stornieren.")
                con.execute("DELETE FROM belege WHERE id=?", (rid,))
                prot(con, "beleg_geloescht", b["nummer"] or f"Entwurf {rid}", f"{b['artname']} {b['nummer'] or '(Entwurf ohne Nummer)'} gelöscht", beleg_kurz(b))
                return {"ok": True, "auftrag_id": b["auftrag_id"]}
            if methode == "POST" and unter == "aktualisieren":
                beleg_aktualisieren(con, rid, neu_aus_auftrag=True)
                return beleg_laden(con, rid)
            if methode == "POST" and unter == "festschreiben":
                if not b["leistungsdatum"]:
                    con.execute("UPDATE belege SET leistungsdatum=? WHERE id=?", (b["datum"] or date.today().isoformat(), rid))
                nb = beleg_festschreiben(con, rid)
                pdf = {}
                try:
                    pdf = beleg_pdf(con, rid)
                except ApiFehler as f:
                    pdf = {"fehler": str(f)}
                return {"beleg": beleg_laden(con, rid), "pdf": pdf}
            if methode == "POST" and unter == "storno":
                st = beleg_stornieren(con, rid)
                pdf = {}
                try:
                    pdf = beleg_pdf(con, st["id"])
                except ApiFehler as f:
                    pdf = {"fehler": str(f)}
                return {"beleg": st, "pdf": pdf}
            if methode == "POST" and unter == "pdf":
                return beleg_pdf(con, rid)
            if unter == "versendet" and methode in ("POST", "DELETE"):
                # Versand außerhalb des Programms (Post, persönlich, eigenes E-Mail-Programm) vermerken oder den Vermerk zurücknehmen
                von_hand = (b.get("versendet_an") or "").startswith(VERMERK)
                if b.get("versendet") and not von_hand:
                    raise ApiFehler("Der Beleg wurde aus dem Programm per E-Mail gesendet; das bleibt so vermerkt.")
                if methode == "POST":
                    weg = str((daten or {}).get("weg") or "").strip()[:80] or "von Hand"
                    con.execute("UPDATE belege SET versendet=?, versendet_an=? WHERE id=?",
                                (datetime.now().isoformat(timespec="minutes"), VERMERK + weg, rid))
                    status_fortschreiben(con, beleg_laden(con, rid))
                else:
                    con.execute("UPDATE belege SET versendet='', versendet_an='' WHERE id=?", (rid,))
                return beleg_laden(con, rid)
            if methode == "GET" and unter == "mail":
                return mail_vorschlag(con, rid)
            if methode == "POST" and unter == "mail":
                return mail_senden(con, rid, daten or {})
            if methode == "GET" and unter == "erechnung":
                if not b["ist_rechnung"]:
                    raise ApiFehler("E-Rechnungen gibt es nur für Rechnungen.")
                xr = q.get("format") == "xrechnung"
                try:
                    erechnung.cii_xml(dict(b, nummer=b["nummer"] or "ENTWURF"), xr, auftrag_kunde(con, b["auftrag_id"]))
                    fehler = []
                except erechnung.ERechnungFehler as f:
                    fehler = [str(f)]
                return {"fehler": fehler, "fest": b["status"] in ("fest", "storniert")}

        # ---------- Offene Posten & Zahlungseingänge ----------
        if res == "offeneposten":
            if methode == "GET" and rid is None:
                return op_liste(con, q)
            if methode == "GET" and rid and unter == "zahlungen":
                return zeilen(con.execute("SELECT * FROM zahlungseingaenge WHERE op_id=? ORDER BY datum, id", (rid,)))
            if rid and unter == "mail":
                return zahlbest_mail(con, rid, methode, q, daten or {})
            if methode == "POST" and rid and unter == "zahlung":
                op_zahlung_buchen(con, rid, daten or {})
                return {"ok": True}
            if methode == "GET" and rid and unter == "mahnung":
                return mahnung_vorschlag(con, rid, q)
            if methode == "POST" and rid and unter == "mahnung":
                return mahnung_erstellen(con, rid, daten or {})
            if methode == "POST" and rid and unter == "mahnsperre":
                con.execute("UPDATE offene_posten SET mahnsperre=? WHERE id=?", (1 if (daten or {}).get("an") else 0, rid))
                return {"ok": True}
            if methode == "POST" and rid and unter == "mahnkosten_erlassen":
                op = con.execute("SELECT * FROM offene_posten WHERE id=?", (rid,)).fetchone()
                if op and (op["mahnkosten"] or 0) > 0:
                    con.execute("INSERT INTO notizen (kunde_id, auftrag_id, text, angelegt) VALUES (?,?,?,?)",
                                (op["kunde_id"], op["auftrag_id"], f"Mahnkosten {de(op['mahnkosten'])} € zu {op['nummer']} erlassen", jetzt()))
                    con.execute("UPDATE offene_posten SET mahnkosten=0 WHERE id=?", (rid,))
                return {"ok": True}
        if res == "bank":
            return bank.web_api(con, methode, teile, q, daten or {})
        if res == "liquiditaet":
            return liquiditaet.web_api(con, methode, teile, q, daten or {})
        if res == "sachkonten":
            c = export.datev_cfg(einstellungen(con))
            return konten.api(con, methode, teile, q, daten or {}, c["skr"], c["sachkontenlaenge"], benutzer.ist_inhaber())
        if res == "wiedervorlagen":
            return wiedervorlage.api(con, methode, teile, q, daten or {}, ich_login())
        if res == "preisimport" and methode == "POST" and teile[1:] in (["lesen"], ["uebernehmen"], ["neue"], ["anlegen"]):
            d = daten or {}
            lid = int(d["lieferant_id"]) if str(d.get("lieferant_id") or "").isdigit() else None
            if teile[1] == "lesen":
                if d.get("daten"):
                    roh = base64.b64decode(d["daten"])
                    erg = preise.lesen(roh, str(d.get("dateiname") or ""), d.get("zuordnung"))
                    schluessel = preise.merken(roh + json.dumps(d.get("zuordnung") or {}).encode(), erg)
                elif d.get("schluessel"):
                    erg, schluessel = preise.gemerkt(d["schluessel"]), d["schluessel"]
                else:
                    raise ApiFehler("Keine Datei übergeben.")
                ab = preise.abgleich(con, lid, erg["artikel"], zahl(d.get("rabatt") or 0, float), nur_lieferant=not d.get("alle"))
                return {**{k: v for k, v in erg.items() if k != "artikel"}, **ab, **preise.neue(con, erg["artikel"]), "schluessel": schluessel}
            if teile[1] == "neue":
                return preise.neue(con, preise.gemerkt(d.get("schluessel"))["artikel"], d.get("suche") or "", d.get("gruppe") or "")
            if teile[1] == "anlegen":
                erg = preise.anlegen(con, preise.gemerkt(d.get("schluessel"))["artikel"], d.get("auswahl"), d.get("kategorie"), lid,
                                     zahl(d.get("rabatt") or 0, float))
                if erg["angelegt"]:
                    l = con.execute("SELECT kurzname FROM lieferanten WHERE id=?", (lid,)).fetchone() if lid else None
                    prot(con, "preisimport", (l["kurzname"] if l else "")[:80], f"{erg['angelegt']} Materialien aus „{str(d.get('dateiname') or '')[:80]}“ angelegt"
                         + (f" (Lieferant {l['kurzname']})" if l else ""), {"angelegt": erg["liste"][:500]})
                return erg
            erg = preise.uebernehmen(con, d.get("posten"), date.today().isoformat())
            if erg["geaendert"]:
                l = con.execute("SELECT kurzname FROM lieferanten WHERE id=?", (lid,)).fetchone() if lid else None
                prot(con, "preisimport", (l["kurzname"] if l else "")[:80], f"{erg['geaendert']} Einkaufspreise aus „{str(d.get('dateiname') or '')[:80]}“ übernommen"
                     + (f" (Lieferant {l['kurzname']})" if l else ""), {"liste": erg["liste"][:500]})
            return erg
        if res == "zahlungseingaenge" and rid and methode == "DELETE":
            zahlungseingang_loeschen(con, rid)
            return {"ok": True}
        if res == "mahnungen":
            if methode == "GET" and rid is None:
                return mahnungen_liste(con, q)
            if methode == "GET" and rid and unter == "mail":
                return mahnung_mail_vorschlag(con, rid)
            if methode == "POST" and rid and unter == "mail":
                return mahnung_mail_senden(con, rid, daten or {})
            if methode == "DELETE" and rid:
                return mahnung_loeschen(con, rid)
        if res == "mahnwesen" and methode == "GET":
            liste = op_liste(con, {"status": "faellig"})
            return {"posten": liste, "mahnungen": mahnungen_liste(con, {"limit": "200"}),
                    "einstellung": mahnwesen.einstellung(einstellungen(con))}
        if res == "einstellungen" and len(teile) == 2 and teile[1] == "unterschrift" and methode == "POST":
            d = daten or {}
            pfad = os.path.join(DATEN, UNTERSCHRIFT)
            if d.get("daten"):
                roh = base64.b64decode(d["daten"])
                if not roh.startswith(b"\x89PNG"):
                    raise ApiFehler("Die Unterschrift muss als PNG ankommen.")
                with open(pfad, "wb") as f:
                    f.write(roh)
            elif os.path.exists(pfad):
                os.remove(pfad)
            return {"ok": True, "vorhanden": os.path.exists(pfad)}
        if res == "einstellungen" and unter is None and len(teile) == 2 and teile[1] == "logo" and methode == "POST":
            d = daten or {}
            endung = ".jpg" if (d.get("name") or "").lower().endswith((".jpg", ".jpeg")) else ".png"
            for alt in ("logo.png", "logo.jpg"):
                if os.path.exists(os.path.join(DATEN, alt)):
                    os.remove(os.path.join(DATEN, alt))
            if d.get("daten"):
                with open(os.path.join(DATEN, "logo" + endung), "wb") as f:
                    f.write(base64.b64decode(d["daten"]))
            return {"ok": True}

        # ---------- Kunden importieren ----------
        if res == "kunden" and len(teile) == 2 and teile[1] == "import" and methode == "POST":
            vorher = con.execute("SELECT IFNULL(MAX(id),0) FROM kunden").fetchone()[0]
            erg = kunden_import(con, daten or {})
            # importierte Kunden stammen aus einem früheren Programm: Altbestand sperren
            bis = f"{date.today().year + AUFBEWAHRUNG_JAHRE}-12-31"
            con.execute("UPDATE kunden SET aufbewahren_bis=? WHERE id>? AND IFNULL(aufbewahren_bis,'')<?", (bis, vorher, bis))
            return erg

        # ---------- Kunden ----------
        if res == "kunden":
            if methode == "GET" and rid is None:
                sql, p = "SELECT * FROM kunden WHERE 1=1", []
                such = (q.get("q") or "").strip().lower()
                if such:
                    felder = SUCHFELDER.get(q.get("feld", "alle"), SUCHFELDER["alle"])
                    sql += " AND (" + " OR ".join(f"ulower({f}) LIKE ?" for f in felder) + ")"
                    p += [f"%{such}%"] * len(felder)
                if q.get("gruppe"):
                    sql += " AND gruppe=?"
                    p.append(q["gruppe"])
                status = q.get("status", "aktiv")
                if status == "aktiv":
                    sql += " AND aktiv=1"
                elif status == "inaktiv":
                    sql += " AND aktiv=0"
                return zeilen(con.execute(sql + " ORDER BY nummer", p))
            if methode == "GET" and rid and unter == "statistik":
                return statistik(con, rid)
            if rid and unter == "mail":
                return kunde_mail(con, rid, methode, q, daten or {})
            if methode == "GET" and rid and unter == "auskunft":
                return kunde_auskunft(con, rid)
            if methode == "POST" and rid and unter == "auskunft":
                return auskunft_brief(con, rid)
            if rid and unter == "anonymisieren" and methode in ("GET", "POST"):
                if not benutzer.ist_inhaber():
                    raise ApiFehler("Anonymisieren darf nur der Inhaber.", 403)
                return kunde_anonymisieren(con, rid, ausfuehren=methode == "POST")
            if methode == "GET" and rid:
                return kunde_mit_zaehlern(con, rid)
            if methode == "POST" and rid is None:
                e = einstellungen(con)
                nr = kundennummer_info(con)["naechste"]
                werte = adressen.ableiten({}, kunde_daten(daten or {}))
                werte.setdefault("kurzname", "Neuer Kunde")
                werte.setdefault("gruppe", (e.get("kundengruppen") or [""])[0])
                werte.setdefault("zahlungskonto", (e.get("zahlungskonten") or [""])[0])
                werte["nummer"] = werte.get("nummer") or nr
                if con.execute("SELECT 1 FROM kunden WHERE nummer=?", (werte["nummer"],)).fetchone():
                    raise ApiFehler(f"Kundennummer {werte['nummer']} ist schon vergeben.")
                werte["angelegt"] = werte["geaendert"] = jetzt()
                cur = con.execute(
                    f"INSERT INTO kunden ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})",
                    list(werte.values()))
                return kunde_mit_zaehlern(con, cur.lastrowid)
            if methode == "PUT" and rid:
                alt = con.execute("SELECT * FROM kunden WHERE id=?", (rid,)).fetchone()
                if "aufbewahren_bis" in (daten or {}):
                    if not benutzer.ist_inhaber():
                        daten.pop("aufbewahren_bis")
                    elif alt and (alt["aufbewahren_bis"] or "") != (daten["aufbewahren_bis"] or ""):
                        prot(con, "aufbewahrung_geaendert", str(rid), f"Kunde {alt['nummer']}: Aufbewahren bis {de_datum(alt['aufbewahren_bis']) or '–'} → "
                             f"{de_datum(daten['aufbewahren_bis']) or '–'}", {"alt": alt["aufbewahren_bis"], "neu": daten["aufbewahren_bis"]})
                werte = adressen.ableiten(dict(alt) if alt else {}, kunde_daten(daten or {}))
                if "nummer" in werte:   # Kundennummer ist nach dem Anlegen fest (Belege, E-Rechnungen, Ordner verweisen darauf)
                    if alt and str(werte["nummer"]) != str(alt["nummer"]):
                        raise ApiFehler("Die Kundennummer ist nach dem Anlegen fest und kann nicht geändert werden.")
                    werte.pop("nummer")
                if "kurzname" in werte and not str(werte["kurzname"]).strip():
                    raise ApiFehler("Der Kurzname darf nicht leer sein.")
                if werte:
                    werte["geaendert"] = jetzt()
                    con.execute(f"UPDATE kunden SET {','.join(f'{k}=?' for k in werte)} WHERE id=?",
                                list(werte.values()) + [rid])
                return kunde_mit_zaehlern(con, rid)
            if methode == "DELETE" and rid:
                sperre = (con.execute("SELECT aufbewahren_bis FROM kunden WHERE id=?", (rid,)).fetchone() or {"aufbewahren_bis": ""})["aufbewahren_bis"] or ""
                if sperre > date.today().isoformat():
                    raise ApiFehler(f"Der Kunde ist bis {de_datum(sperre)} aufzubewahren (Altbestand aus früheren Programmen bzw. Frist). "
                                    "Er lässt sich stattdessen auf inaktiv setzen.")
                if con.execute("SELECT 1 FROM auftraege WHERE kunde_id=?", (rid,)).fetchone():
                    raise ApiFehler("Der Kunde hat Aufträge und kann nicht gelöscht werden. "
                                    "Er lässt sich auf inaktiv setzen und nach Ablauf der Fristen anonymisieren.")
                # Geschäftliche E-Mails und Briefe sind Handelsbriefe (6 Jahre ab Jahresende): solange nicht löschen
                frist = ""
                for (d,) in con.execute("SELECT datum FROM korrespondenz WHERE kunde_id=? AND art LIKE 'mail%' UNION ALL "
                                        "SELECT datum FROM briefe WHERE kunde_id=? AND IFNULL(status,'Entwurf')<>'Entwurf'", (rid, rid)):
                    if (d or "")[:4].isdigit():
                        frist = max(frist, f"{int(d[:4]) + 6}-12-31")
                if frist >= date.today().isoformat():
                    raise ApiFehler(f"Mit dem Kunden gibt es E-Mails oder Briefe (Handelsbriefe, aufzubewahren bis {de_datum(frist)}). "
                                    "Er kann deshalb nicht gelöscht werden. Bis dahin lässt er sich auf inaktiv setzen, danach anonymisieren.")
                for a in con.execute("SELECT pfad FROM anhaenge WHERE kunde_id=?", (rid,)):
                    if os.path.exists(a["pfad"]):
                        os.remove(a["pfad"])
                con.execute("DELETE FROM anhaenge WHERE kunde_id=?", (rid,))
                con.execute("DELETE FROM notizen WHERE kunde_id=?", (rid,))
                con.execute("DELETE FROM wiedervorlagen WHERE kunde_id=?", (rid,))
                _korrespondenz_loeschen(con, rid)
                con.execute("DELETE FROM kunden WHERE id=?", (rid,))
                protokoll.eintragen(con, "kunde_geloescht", str(rid), f"Kunde {rid} gelöscht (ohne Aufträge, mit Korrespondenz und Notizen)", {},
                                    benutzer=dict(benutzer.aktuell() or {}).get("login", ""), version=VERSION)
                return {"ok": True}

        # ---------- Aufträge ----------
        if res == "auftraege":
            if methode == "GET" and rid is None:
                sql = ("SELECT a.*, k.kurzname AS kunde, k.nummer AS kundennr, pr.nummer AS projekt_nr, pr.bezeichnung AS projekt FROM auftraege a "
                       "JOIN kunden k ON k.id=a.kunde_id LEFT JOIN projekte pr ON pr.id=a.projekt_id WHERE 1=1")
                p = []
                if q.get("projekt"):
                    if q["projekt"] == "ohne":
                        sql += " AND a.projekt_id IS NULL"
                    else:
                        sql += " AND a.projekt_id=?"
                        p.append(int(q["projekt"]))
                if q.get("kunde"):
                    sql += " AND a.kunde_id=?"
                    p.append(int(q["kunde"]))
                for f in ("gruppe", "status"):
                    if q.get(f):
                        sql += f" AND a.{f}=?"
                        p.append(q[f])
                such = (q.get("q") or "").strip().lower()
                if such:
                    sql += (" AND (ulower(a.nummer) LIKE ? OR ulower(a.bezeichnung) LIKE ? OR ulower(k.kurzname) LIKE ? OR ulower(a.bemerkungen) LIKE ?"
                            " OR ulower(IFNULL(pr.nummer,'')) LIKE ? OR ulower(IFNULL(pr.bezeichnung,'')) LIKE ?)")
                    p += [f"%{such}%"] * 6
                liste = zeilen(con.execute(sql + " ORDER BY a.nummer DESC", p))
                for a in liste:   # Kalkulationsvorgaben und Kundenkopie braucht keine Liste (je Auftrag rund 2 kB, bei Tausenden Aufträgen viele MB)
                    a.pop("kalk", None)
                    a.pop("kunde_daten", None)
                return liste
            if methode == "GET" and rid and unter is None:
                return auftrag_laden(con, rid)
            if methode == "GET" and rid and unter == "historie":
                return auftrag_historie(con, rid)
            if methode == "POST" and rid and unter == "ordner":
                ordner_anlegen(con, rid)
                return auftrag_laden(con, rid)
            if rid and unter == "kunde":
                kopie = auftrag_kunde(con, rid)
                if methode == "PUT":
                    neu = adressen.ableiten(kopie, {k: v for k, v in kunde_daten(daten or {}).items() if k != "nummer"})
                    kopie.update(neu)
                    kopie.pop("id", None)
                    con.execute("UPDATE auftraege SET kunde_daten=?, geaendert=? WHERE id=?", (json.dumps(kopie, ensure_ascii=False), jetzt(), rid))
                    kopie = auftrag_kunde(con, rid)
                elif methode == "POST":
                    k = kunde_kopie(con, kopie["id"])
                    con.execute("UPDATE auftraege SET kunde_daten=?, geaendert=? WHERE id=?", (json.dumps(k, ensure_ascii=False), jetzt(), rid))
                    kopie = auftrag_kunde(con, rid)
                stamm = kunde_zeile(con, kopie["id"])
                vergleich = ("kurzname", "anschrift", "plz", "ort", "land", "telefon", "email1", "anrede", "gruppe", "ustid",
                             "lieferanschrift", "lieferort", "rechnungsanschrift", "rechnungsort", "zahlungsziel", "skonto", "skontotage", "rabatt")
                return {"kopie": kopie, "stamm": stamm,
                        "unterschiede": [f for f in vergleich if str(stamm.get(f) or "") != str(kopie.get(f) or "")]}
            if methode == "POST" and rid and unter == "papier":
                d = daten or {}
                return papier_pdf(con, rid, d.get("art"), {k: v for k, v in (d.get("opts") or {}).items()})
            if methode == "GET" and rid and unter == "zuschnittplan":
                ordner, hinweis = projektordner(con, rid, anlegen=False)
                if not ordner:
                    raise ApiFehler(hinweis or "Für diesen Auftrag gibt es keinen Projektordner.")
                try:
                    name, plan, pfad = reste.plan_suchen(ordner, einstellungen(con).get("zuschnitt_ordner") or "40_Kalkulation")
                except reste.Fehler as f:
                    raise ApiFehler(str(f), f.code)
                return {"dateiname": name, "pfad": os.path.relpath(pfad, ordner).replace(os.sep, "/"), "plan": plan,
                        "auftrag_nr": auftrag_laden(con, rid)["nummer"]}
            if methode == "GET" and rid and unter == "zuschnitt":
                return {"auftrag": auftrag_laden(con, rid), "teile": werkstatt.zuschnitt_daten(auftrag_rechnen(con, rid))}
            if methode == "GET" and rid and unter == "bilddateien":
                ordner, hinweis = projektordner(con, rid)
                if not ordner:
                    return {"hinweis": hinweis, "dateien": []}
                liste = []
                for wurzel, dirs, files in os.walk(ordner):
                    if os.path.relpath(wurzel, ordner).count(os.sep) >= 3:
                        dirs[:] = []
                    for f in files:
                        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and not f.startswith((".", "~$")):
                            pf = os.path.join(wurzel, f)
                            try:
                                st = os.stat(pf)
                            except OSError:
                                continue
                            liste.append({"pfad": os.path.relpath(pf, ordner).replace(os.sep, "/"), "groesse": st.st_size,
                                          "geaendert": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes")})
                    if len(liste) > 300:
                        break
                liste.sort(key=lambda x: x["geaendert"], reverse=True)
                return {"dateien": liste}
            if methode == "GET" and rid and unter == "dateien":
                ordner, hinweis = sicht_ordner(con, rid)
                if not ordner:
                    return {"ordner": None, "hinweis": hinweis, "eintraege": []}
                rel = q.get("pfad", "")
                return {"ordner": ordner, "pfad": rel, "eintraege": ordner_inhalt(ordner, rel)}
            if methode == "POST" and rid and unter == "oeffnen":
                ordner, hinweis = sicht_ordner(con, rid)
                if not ordner:
                    raise ApiFehler(hinweis)
                ziel = im_ordner(ordner, (daten or {}).get("pfad", ""))
                if not os.path.exists(ziel):
                    raise ApiFehler("Datei oder Ordner nicht gefunden.")
                nur_am_pc("Öffnen")
                oeffnen(ziel)
                return {"ok": True}
            if methode == "POST" and rid and unter == "hochladen":
                ordner, hinweis = sicht_ordner(con, rid)
                if not ordner:
                    raise ApiFehler(hinweis)
                d = daten or {}
                zielordner = im_ordner(ordner, d.get("pfad", ""))
                name = sauber(os.path.basename(d.get("dateiname") or "")) or "datei"
                stamm, endung = os.path.splitext(name)
                ziel, i = os.path.join(zielordner, name), 1
                while os.path.exists(ziel):
                    ziel = os.path.join(zielordner, f"{stamm} ({i}){endung}")
                    i += 1
                with open(ziel, "wb") as f:
                    f.write(base64.b64decode(d.get("daten", "")))
                if d.get("historie"):
                    historie_eintrag(con, rid, "datei", os.path.relpath(ziel, ordner).replace(os.sep, "/"))
                return {"ok": True, "name": os.path.basename(ziel)}
            if methode == "POST" and rid and unter in ("umbenennen", "loeschen", "verschieben", "zeigen"):
                ordner, hinweis = sicht_ordner(con, rid)
                if not ordner:
                    raise ApiFehler(hinweis)
                d = daten or {}
                quelle = im_ordner(ordner, d.get("pfad", ""))
                if os.path.normcase(quelle) == os.path.normcase(os.path.normpath(ordner)) and unter != "zeigen":
                    raise ApiFehler("Der Projektordner selbst kann hier nicht verändert werden.")
                if not os.path.exists(quelle):
                    raise ApiFehler("Datei oder Ordner nicht gefunden. Liste neu laden.")
                try:
                    if unter == "zeigen":
                        nur_am_pc("Im Explorer zeigen")
                        im_explorer_zeigen(quelle)
                        return {"ok": True}
                    if unter == "umbenennen":
                        neu = sauber(d.get("neu"))
                        if not neu:
                            raise ApiFehler("Bitte einen gültigen Namen eingeben.")
                        ziel = os.path.join(os.path.dirname(quelle), neu)
                        if os.path.exists(ziel) and os.path.normcase(ziel) != os.path.normcase(quelle):
                            raise ApiFehler(f"„{neu}“ gibt es in diesem Ordner schon.")
                        os.rename(quelle, ziel)
                        return {"ok": True, "name": neu}
                    if unter == "loeschen":
                        wohin = in_papierkorb(quelle)
                        return {"ok": True, "wohin": wohin}
                    if unter == "verschieben":
                        zielordner = im_ordner(ordner, d.get("ziel", ""))
                        if not os.path.isdir(zielordner):
                            raise ApiFehler("Zielordner nicht gefunden.")
                        if os.path.normcase(zielordner) == os.path.normcase(quelle) or \
                                os.path.normcase(zielordner).startswith(os.path.normcase(quelle) + os.sep):
                            raise ApiFehler("Ein Ordner kann nicht in sich selbst verschoben werden.")
                        if os.path.normcase(os.path.dirname(quelle)) == os.path.normcase(zielordner):
                            return {"ok": True, "unveraendert": True}
                        ziel = os.path.join(zielordner, os.path.basename(quelle))
                        if os.path.exists(ziel):
                            raise ApiFehler(f"Im Zielordner gibt es „{os.path.basename(quelle)}“ schon.")
                        shutil.move(quelle, ziel)
                        return {"ok": True}
                except ApiFehler:
                    raise
                except OSError as f:
                    raise dateifehler(f)
            if methode == "POST" and rid and unter == "neuerordner":
                ordner, hinweis = sicht_ordner(con, rid)
                if not ordner:
                    raise ApiFehler(hinweis)
                d = daten or {}
                name = sauber(d.get("name"))
                if not name:
                    raise ApiFehler("Bitte einen Ordnernamen eingeben.")
                os.makedirs(os.path.join(im_ordner(ordner, d.get("pfad", "")), name), exist_ok=True)
                return {"ok": True}
            if methode == "POST" and rid is None:
                d = daten or {}
                if not d.get("kunde_id"):
                    raise ApiFehler("Bitte einen Kunden wählen.")
                if not con.execute("SELECT 1 FROM kunden WHERE id=?", (d["kunde_id"],)).fetchone():
                    raise ApiFehler("Kunde nicht gefunden.")
                e = einstellungen(con)
                werte = {f: d.get(f, "") for f in AUFTRAG_FELDER if f in d}
                if "projekt_id" in werte:
                    werte["projekt_id"] = int(werte["projekt_id"]) if str(werte["projekt_id"] or "").isdigit() else None
                werte.setdefault("status", (e.get("auftragsstatus") or [""])[0])
                eigene = str(d.get("nummer") or "").strip()
                if eigene:
                    if con.execute("SELECT 1 FROM auftraege WHERE nummer=?", (eigene,)).fetchone():
                        raise ApiFehler(f"Die Auftragsnummer {eigene} ist schon vergeben.")
                    werte["nummer"] = eigene
                else:
                    werte["nummer"] = naechste_auftragsnummer(con)
                werte["angelegt"] = werte["geaendert"] = jetzt()
                werte["kunde_daten"] = json.dumps(kunde_kopie(con, d["kunde_id"]), ensure_ascii=False)
                cur = con.execute(
                    f"INSERT INTO auftraege ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})",
                    list(werte.values()))
                aid = cur.lastrowid
                auftrag_kalk(con, aid)  # Kalkulationswerte (Werkstoffe, Beschläge, Löhne, Zuschläge) gleich einfrieren
                erg = auftrag_laden(con, aid)
                if e.get("ordner_automatisch") and (e.get("projektpfad") or "").strip():
                    try:
                        ordner_anlegen(con, aid)
                        erg = auftrag_laden(con, aid)
                    except ApiFehler as f:
                        erg["_hinweis"] = f"Auftrag angelegt, Ordner aber nicht: {f}"
                return erg
            if methode == "PUT" and rid:
                werte = {f: daten[f] for f in AUFTRAG_FELDER if f in (daten or {})}
                if "projekt_id" in werte:
                    werte["projekt_id"] = int(werte["projekt_id"]) if str(werte["projekt_id"] or "").isdigit() else None
                    if werte["projekt_id"] and not con.execute("SELECT 1 FROM projekte WHERE id=?", (werte["projekt_id"],)).fetchone():
                        raise ApiFehler("Projekt nicht gefunden.")
                alt = con.execute("SELECT kunde_id FROM auftraege WHERE id=?", (rid,)).fetchone()
                if "kunde_id" in werte and alt and int(werte["kunde_id"] or 0) != alt["kunde_id"]:
                    werte["kunde_daten"] = json.dumps(kunde_kopie(con, int(werte["kunde_id"])), ensure_ascii=False)
                # Status „Fertigung“ gesetzt: Beginn der Fertigung festhalten (falls noch leer)
                if werte.get("status") == "Fertigung" and "fertigung" not in werte:
                    if not (con.execute("SELECT fertigung FROM auftraege WHERE id=?", (rid,)).fetchone()["fertigung"] or ""):
                        werte["fertigung"] = date.today().isoformat()
                if werte.get("plan_von") and werte.get("plan_bis") and werte["plan_bis"] < werte["plan_von"]:
                    werte["plan_von"], werte["plan_bis"] = werte["plan_bis"], werte["plan_von"]
                vorher = con.execute("SELECT status, fertigung, lieferung FROM auftraege WHERE id=?", (rid,)).fetchone()
                alt_status = vorher["status"] if vorher else None
                if werte:
                    werte["geaendert"] = jetzt()
                    con.execute(f"UPDATE auftraege SET {','.join(f'{k}=?' for k in werte)} WHERE id=?",
                                list(werte.values()) + [rid])
                if "status" in werte and werte["status"] != alt_status:
                    historie_eintrag(con, rid, "status", f"{alt_status or '–'} → {werte['status']}")
                elif vorher:   # Datum eingetragen (und der Status nicht im selben Zug von Hand geändert): Status nachziehen
                    for feld in ("fertigung", "lieferung"):
                        if werte.get(feld) and werte[feld] != (vorher[feld] or ""):
                            status_durch_datum(con, rid, feld)
                return auftrag_laden(con, rid)
            if methode == "DELETE" and rid:
                return auftrag_loeschen(con, rid)

        # ---------- Lieferanten ----------
        if res == "lieferanten":
            if rid and unter == "mail":
                return lieferant_mail(con, rid, methode, q, daten or {})
            if methode == "GET" and rid is None:
                sql, p = "SELECT * FROM lieferanten WHERE 1=1", []
                such = (q.get("q") or "").strip().lower()
                if such:
                    felder = SUCHFELDER.get(q.get("feld", "alle"), SUCHFELDER["alle"])
                    sql += " AND (" + " OR ".join(f"ulower({f}) LIKE ?" for f in felder) + ")"
                    p += [f"%{such}%"] * len(felder)
                if q.get("gruppe"):
                    sql += " AND gruppe=?"
                    p.append(q["gruppe"])
                status = q.get("status", "aktiv")
                if status == "aktiv":
                    sql += " AND aktiv=1"
                elif status == "inaktiv":
                    sql += " AND aktiv=0"
                return zeilen(con.execute(sql + " ORDER BY nummer", p))
            if methode == "GET" and rid:
                return lieferant_mit_zaehlern(con, rid)
            if methode == "POST" and rid is None:
                e = einstellungen(con)
                maxnr = con.execute("SELECT MAX(nummer) FROM lieferanten").fetchone()[0]
                nr = max(int(e.get("lieferantennr_start") or 700000), (maxnr or 0) + 1)
                werte = adressen.ableiten({}, lieferant_daten(daten or {}))
                if werte.get("anschrift") and not any(werte.get(f) for f in adressen.FELDER):   # z. B. aus einer Eingangsrechnung
                    teile = adressen.zerlegen(werte["anschrift"])
                    werte.update({f: teile.get(f, "") for f in adressen.FELDER})
                    if not werte.get("kurzname"):
                        werte["kurzname"] = adressen.kurzname(werte) or werte["anschrift"].split("\n")[0][:60]
                werte.setdefault("kurzname", "Neuer Lieferant")
                werte["nummer"] = werte.get("nummer") or nr
                if con.execute("SELECT 1 FROM lieferanten WHERE nummer=?", (werte["nummer"],)).fetchone():
                    raise ApiFehler(f"Lieferantennummer {werte['nummer']} ist schon vergeben.")
                werte["angelegt"] = werte["geaendert"] = jetzt()
                cur = con.execute(
                    f"INSERT INTO lieferanten ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})",
                    list(werte.values()))
                return lieferant_mit_zaehlern(con, cur.lastrowid)
            if methode == "PUT" and rid:
                alt_l = con.execute("SELECT * FROM lieferanten WHERE id=?", (rid,)).fetchone()
                werte = adressen.ableiten(dict(alt_l) if alt_l else {}, lieferant_daten(daten or {}))
                if "nummer" in werte:   # Lieferantennummer ist nach dem Anlegen fest (Zahlungen, Belege, Exporte verweisen darauf)
                    alt = con.execute("SELECT nummer FROM lieferanten WHERE id=?", (rid,)).fetchone()
                    if alt and str(werte["nummer"]) != str(alt["nummer"]):
                        raise ApiFehler("Die Lieferantennummer ist nach dem Anlegen fest und kann nicht geändert werden.")
                    werte.pop("nummer")
                if "kurzname" in werte and not str(werte["kurzname"]).strip():
                    raise ApiFehler("Der Kurzname darf nicht leer sein.")
                if werte:
                    werte["geaendert"] = jetzt()
                    con.execute(f"UPDATE lieferanten SET {','.join(f'{k}=?' for k in werte)} WHERE id=?",
                                list(werte.values()) + [rid])
                return lieferant_mit_zaehlern(con, rid)
            if methode == "DELETE" and rid:
                if con.execute("SELECT 1 FROM zahlungen WHERE lieferant_id=?", (rid,)).fetchone():
                    raise ApiFehler("Zu diesem Lieferanten gibt es Zahlungsaufträge, er kann nicht gelöscht werden. "
                                    "Er lässt sich stattdessen auf inaktiv setzen.")
                for a in con.execute("SELECT pfad FROM anhaenge WHERE lieferant_id=?", (rid,)):
                    if os.path.exists(a["pfad"]):
                        os.remove(a["pfad"])
                con.execute("DELETE FROM anhaenge WHERE lieferant_id=?", (rid,))
                con.execute("DELETE FROM notizen WHERE lieferant_id=?", (rid,))
                con.execute("DELETE FROM lieferanten WHERE id=?", (rid,))
                return {"ok": True}

        # ---------- Zahlungsaufträge ----------
        if res == "zahlungen":
            if methode == "GET" and rid is None:
                sql = ("SELECT z.*, l.kurzname AS lieferant, l.nummer AS lieferantennr, a.nummer AS auftragsnr "
                       "FROM zahlungen z JOIN lieferanten l ON l.id=z.lieferant_id "
                       "LEFT JOIN auftraege a ON a.id=z.auftrag_id WHERE 1=1")
                p = []
                if q.get("lieferant"):
                    sql += " AND z.lieferant_id=?"
                    p.append(int(q["lieferant"]))
                st = q.get("status", "")
                heute = date.today().isoformat()
                if st == "offen":
                    sql += " AND z.bezahlt=''"
                elif st == "faellig":
                    sql += " AND z.bezahlt='' AND z.faellig<>'' AND z.faellig<=?"
                    p.append(heute)
                elif st == "skonto":
                    sql += " AND z.bezahlt='' AND z.skonto>0 AND z.skonto_bis>=?"
                    p.append(heute)
                elif st == "bezahlt":
                    sql += " AND z.bezahlt<>''"
                if q.get("bezahlung"):
                    sql += " AND z.bezahlung=?"
                    p.append(q["bezahlung"])
                such = (q.get("q") or "").strip().lower()
                if such:
                    sql += (" AND (ulower(z.nummer) LIKE ? OR ulower(z.bemerkung) LIKE ? OR ulower(z.empfaenger) LIKE ?"
                            " OR ulower(z.belegnr) LIKE ? OR ulower(l.kurzname) LIKE ?)")
                    p += [f"%{such}%"] * 5
                return zeilen(con.execute(sql + " ORDER BY z.nummer DESC", p))
            if methode == "GET" and rid:
                return zahlung_laden(con, rid)
            if methode == "POST" and rid is None and not teile[1:]:
                werte = zahlung_daten(daten or {})
                if not werte.get("lieferant_id"):
                    raise ApiFehler("Bitte einen Lieferanten wählen.")
                l = con.execute("SELECT * FROM lieferanten WHERE id=?", (werte["lieferant_id"],)).fetchone()
                if not l:
                    raise ApiFehler("Lieferant nicht gefunden.")
                for k, v in (("belegdatum", date.today().isoformat()), ("empfaenger", l["empfaenger"] or l["kurzname"]),
                             ("iban", l["iban"]), ("bic", l["bic"])):
                    if not werte.get(k):
                        werte[k] = v
                werte.setdefault("vorsteuer", l["vorsteuer"])
                werte.setdefault("skonto", l["skonto"])
                if not werte.get("faellig"):
                    werte["faellig"] = plus_tage(werte["belegdatum"], l["zahlungsziel"])
                if not werte.get("skonto_bis") and werte.get("skonto"):
                    werte["skonto_bis"] = plus_tage(werte["belegdatum"], l["skontotage"])
                werte.setdefault("bezahlung", "Überweisung")
                if (werte.get("belegnr") or "").strip() and not (daten or {}).get("trotzdem"):
                    dop = con.execute("SELECT nummer FROM zahlungen WHERE lieferant_id=? AND belegnr=?", (werte["lieferant_id"], werte["belegnr"].strip())).fetchone()
                    if dop:
                        raise ApiFehler(f"Die Rechnung {werte['belegnr']} von {l['kurzname']} ist schon als Zahlungsauftrag {dop['nummer']} erfasst.", 409)
                werte["nummer"] = naechste_zahlungsnummer(con)
                werte["angelegt"] = werte["geaendert"] = jetzt()
                cur = con.execute(
                    f"INSERT INTO zahlungen ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})",
                    list(werte.values()))
                return zahlung_laden(con, cur.lastrowid)
            if methode == "POST" and teile[1:] == ["bezahlt"]:
                d = daten or {}
                tag = d.get("datum") or date.today().isoformat()
                ids = [int(i) for i in d.get("ids") or []]
                date.fromisoformat(tag)
                nummern = []
                for i in ids:   # schon bezahlte bleiben, wie sie sind
                    z = con.execute("SELECT nummer, bezahlt FROM zahlungen WHERE id=?", (i,)).fetchone()
                    if z and not z["bezahlt"]:
                        con.execute("UPDATE zahlungen SET bezahlt=?, geaendert=? WHERE id=?", (tag, jetzt(), i))
                        nummern.append(z["nummer"])
                if nummern:
                    prot(con, "zahlungsauftrag_bezahlt", nummern[0], f"Als bezahlt am {de_datum(tag)} markiert (damit gesperrt): {', '.join(nummern)}", {"nummern": nummern, "bezahlt": tag})
                return {"ok": True, "anzahl": len(nummern)}
            if methode == "POST" and rid and unter == "oeffnen":
                # „bezahlt“ zurücknehmen: nur Inhaber, mit Protokolleintrag – danach ist der Zahlungsauftrag wieder änderbar
                if not benutzer.ist_inhaber():
                    raise ApiFehler("„Bezahlt“ zurücknehmen kann nur der Inhaber.", 403)
                z = zahlung_laden(con, rid)
                if z["bezahlt"]:
                    con.execute("UPDATE zahlungen SET bezahlt='', geaendert=? WHERE id=?", (jetzt(), rid))
                    prot(con, "zahlungsauftrag_geoeffnet", z["nummer"], f"Zahlungsauftrag {z['nummer']} (Beleg {z['belegnr']}): „bezahlt am {de_datum(z['bezahlt'])}“ zurückgenommen, "
                         "Sperre aufgehoben", {"bezahlt_alt": z["bezahlt"], "betrag": z["betrag"]})
                return zahlung_laden(con, rid)
            if methode == "POST" and teile[1:] == ["sepa"]:
                d = daten or {}
                ausf = d.get("ausfuehrung") or date.today().isoformat()
                ids = [int(i) for i in d.get("ids") or []]
                if not ids:
                    raise ApiFehler("Keine Zahlungsaufträge ausgewählt.")
                posten, fehler = [], []
                for i in ids:
                    z = zahlung_laden(con, i)
                    l = con.execute("SELECT unsere_kundennr FROM lieferanten WHERE id=?", (z["lieferant_id"],)).fetchone()
                    if z["bezahlt"]:
                        fehler.append(f"{z['nummer']} ist schon bezahlt")
                        continue
                    if not iban_ok(z["iban"]):
                        fehler.append(f"{z['nummer']} ({z['lieferant']}) hat keine gültige IBAN")
                        continue
                    if z["betrag"] <= 0:
                        fehler.append(f"{z['nummer']} hat keinen Betrag")
                        continue
                    mit_skonto = bool(z["skonto"]) and z["skonto_bis"] and z["skonto_bis"] >= ausf
                    zb = round(z["betrag"] * (1 - z["skonto"] / 100), 2) if mit_skonto else round(z["betrag"], 2)
                    teile_zweck = [z["belegnr"] and f"Rg. {z['belegnr']}",
                                   z["belegdatum"] and f"vom {z['belegdatum'][8:10]}.{z['belegdatum'][5:7]}.{z['belegdatum'][:4]}",
                                   l["unsere_kundennr"] and f"KdNr {l['unsere_kundennr']}",
                                   mit_skonto and ("abzgl. " + f"{z['skonto']:g}".replace(".", ",") + " Prozent Skonto"),
                                   not z["belegnr"] and z["bemerkung"]]
                    posten.append({"nummer": z["nummer"], "zahlbetrag": zb, "empfaenger": z["empfaenger"] or z["lieferant"],
                                   "iban": iban_normal(z["iban"]), "bic": z["bic"],
                                   "verwendungszweck": " ".join(t for t in teile_zweck if t)})
                if fehler:
                    raise ApiFehler("SEPA-Datei nicht erstellt: " + "; ".join(fehler))
                xml = sepa_xml(einstellungen(con), posten, ausf)
                return {"xml": xml, "dateiname": f"SEPA_{ausf}_{len(posten)}_Zahlungen.xml",
                        "summe": round(sum(p["zahlbetrag"] for p in posten), 2), "anzahl": len(posten)}
            if methode == "PUT" and rid:
                werte = zahlung_daten(daten or {})
                if werte:
                    alt_z = con.execute("SELECT * FROM zahlungen WHERE id=?", (rid,)).fetchone()
                    if alt_z and alt_z["bezahlt"]:
                        # bezahlt = gesperrt: nur noch Bemerkung, Auftragszuordnung und Zahlart
                        gesperrt = [k for k, v in werte.items() if k not in ZAHLUNG_FREI and k in alt_z.keys() and (alt_z[k] or "") != (v or "")
                                    and not (isinstance(v, float) and abs((alt_z[k] or 0) - v) < 0.005)]
                        if gesperrt:
                            raise ApiFehler(f"Der Zahlungsauftrag {alt_z['nummer']} ist bezahlt und damit gesperrt. Änderbar sind nur Bemerkung, Auftrag und Zahlart; "
                                            "für alles andere muss der Inhaber „bezahlt“ zuerst zurücknehmen.", 409)
                    if alt_z:
                        diff = {k: [alt_z[k], v] for k, v in werte.items() if k in alt_z.keys() and alt_z[k] != v}
                        if diff and (alt_z["bezahlt"] or any(k in diff for k in ("betrag", "belegnr", "belegdatum", "lieferant_id", "iban", "bezahlt", "vorsteuer", "skonto"))):
                            prot(con, "zahlungsauftrag_geaendert", alt_z["nummer"], f"Zahlungsauftrag {alt_z['nummer']} (Beleg {alt_z['belegnr']}) geändert: " + ", ".join(diff), diff)
                    werte["geaendert"] = jetzt()
                    con.execute(f"UPDATE zahlungen SET {','.join(f'{k}=?' for k in werte)} WHERE id=?",
                                list(werte.values()) + [rid])
                return zahlung_laden(con, rid)
            if methode == "DELETE" and rid:
                alt_z = con.execute("SELECT z.*, l.kurzname AS lieferant FROM zahlungen z LEFT JOIN lieferanten l ON l.id=z.lieferant_id WHERE z.id=?", (rid,)).fetchone()
                if alt_z and alt_z["bezahlt"]:
                    raise ApiFehler(f"Der Zahlungsauftrag {alt_z['nummer']} ist bezahlt und kann nicht gelöscht werden.", 409)
                con.execute("DELETE FROM zahlungen WHERE id=?", (rid,))
                if alt_z:
                    prot(con, "zahlungsauftrag_geloescht", alt_z["nummer"], f"Zahlungsauftrag {alt_z['nummer']} gelöscht: {alt_z['lieferant'] or ''}, Beleg {alt_z['belegnr']} vom {de_datum(alt_z['belegdatum'])}, {de(alt_z['betrag'] or 0)} €"
                         + (" (Originaldatei bleibt erhalten)" if alt_z["datei"] else ""), dict(alt_z))
                return {"ok": True}

        if res == "zahlungsstatistik" and methode == "GET":
            feld = "z.bezahlt" if q.get("datum") == "zahlung" else "z.belegdatum"
            sql = ("SELECT z.*, l.kurzname AS lieferant, l.nummer AS lieferantennr, l.gruppe AS gruppe "
                   f"FROM zahlungen z JOIN lieferanten l ON l.id=z.lieferant_id WHERE {feld}<>''")
            p = []
            if q.get("lieferant"):
                sql += " AND l.nummer=?"
                p.append(int(q["lieferant"]))
            if q.get("gruppe"):
                sql += " AND l.gruppe=?"
                p.append(q["gruppe"])
            if q.get("von"):
                sql += f" AND substr({feld},1,4)>=?"
                p.append(q["von"])
            if q.get("bis"):
                sql += f" AND substr({feld},1,4)<=?"
                p.append(q["bis"])
            if q.get("vst_von") not in (None, ""):
                sql += " AND z.vorsteuer>=?"
                p.append(float(q["vst_von"]))
            if q.get("vst_bis") not in (None, ""):
                sql += " AND z.vorsteuer<=?"
                p.append(float(q["vst_bis"]))
            nach = q.get("nach", "jahr")
            gruppen = {}
            for z in con.execute(sql, p):
                d = z["bezahlt"] if q.get("datum") == "zahlung" else z["belegdatum"]
                schl = {"jahr": d[:4], "monat": d[:7], "quartal": f"{d[:4]} Q{(int(d[5:7]) - 1) // 3 + 1}",
                        "lieferant": f"{z['lieferantennr']} {z['lieferant']}", "gruppe": z["gruppe"] or "ohne",
                        "vorsteuer": f"{z['vorsteuer']:g} %"}.get(nach, d[:4])
                g = gruppen.setdefault(schl, {"schluessel": schl, "anzahl": 0, "brutto": 0.0, "netto": 0.0, "vorsteuer": 0.0})
                netto = z["betrag"] / (1 + (z["vorsteuer"] or 0) / 100)
                g["anzahl"] += 1
                g["brutto"] += z["betrag"]
                g["netto"] += netto
                g["vorsteuer"] += z["betrag"] - netto
            erg = sorted(gruppen.values(), key=lambda g: g["schluessel"])
            for g in erg:
                for k in ("brutto", "netto", "vorsteuer"):
                    g[k] = round(g[k], 2)
            return erg

        if res == "naechste_zahlung" and methode == "GET":
            return {"nummer": naechste_zahlungsnummer(con)}

        # ---------- Anhänge ----------
        if res == "anhaenge":
            if methode == "GET" and rid is None:
                sql = ("SELECT h.*, a.nummer AS auftragsnr FROM anhaenge h "
                       "LEFT JOIN auftraege a ON a.id=h.auftrag_id WHERE 1=1")
                p = []
                if q.get("kunde"):
                    sql += " AND h.kunde_id=?"
                    p.append(int(q["kunde"]))
                if q.get("auftrag"):
                    sql += " AND h.auftrag_id=?"
                    p.append(int(q["auftrag"]))
                if q.get("lieferant"):
                    sql += " AND h.lieferant_id=?"
                    p.append(int(q["lieferant"]))
                return zeilen(con.execute(sql + " ORDER BY h.angelegt DESC", p))
            if methode == "POST" and rid is None:
                d = daten or {}
                kid = d.get("kunde_id")
                aid = d.get("auftrag_id")
                lid = d.get("lieferant_id")
                if lid:
                    l = con.execute("SELECT nummer FROM lieferanten WHERE id=?", (lid,)).fetchone()
                    if not l:
                        raise ApiFehler("Lieferant nicht gefunden.")
                    unterordner = "L" + str(l["nummer"])
                else:
                    if aid and not kid:
                        kid = con.execute("SELECT kunde_id FROM auftraege WHERE id=?", (aid,)).fetchone()[0]
                    k = con.execute("SELECT nummer FROM kunden WHERE id=?", (kid,)).fetchone()
                    if not k:
                        raise ApiFehler("Kunde nicht gefunden.")
                    unterordner = str(k["nummer"])
                name = sauber(d.get("dateiname")) or "datei"
                ordner = os.path.join(ANHANG_PFAD, unterordner)
                os.makedirs(ordner, exist_ok=True)
                stamm, endung = os.path.splitext(name)
                ziel, i = os.path.join(ordner, name), 1
                while os.path.exists(ziel):
                    ziel = os.path.join(ordner, f"{stamm}_{i}{endung}")
                    i += 1
                inhalt = base64.b64decode(d.get("daten", ""))
                with open(ziel, "wb") as f:
                    f.write(inhalt)
                cur = con.execute(
                    "INSERT INTO anhaenge (kunde_id, auftrag_id, lieferant_id, dateiname, pfad, groesse, angelegt) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (kid, aid, lid, os.path.basename(ziel), ziel, len(inhalt), jetzt()))
                return dict(con.execute("SELECT * FROM anhaenge WHERE id=?", (cur.lastrowid,)).fetchone())
            if methode == "DELETE" and rid:
                h = con.execute("SELECT * FROM anhaenge WHERE id=?", (rid,)).fetchone()
                if h and os.path.exists(h["pfad"]):
                    os.remove(h["pfad"])
                con.execute("DELETE FROM anhaenge WHERE id=?", (rid,))
                return {"ok": True}

        # ---------- Notizen ----------
        if res == "notizen":
            if methode == "GET":
                sql, p = "SELECT * FROM notizen WHERE 1=1", []
                if q.get("kunde"):
                    sql += " AND kunde_id=?"
                    p.append(int(q["kunde"]))
                if q.get("auftrag"):
                    sql += " AND auftrag_id=?"
                    p.append(int(q["auftrag"]))
                if q.get("lieferant"):
                    sql += " AND lieferant_id=?"
                    p.append(int(q["lieferant"]))
                return zeilen(con.execute(sql + " ORDER BY angelegt DESC", p))
            if methode == "POST":
                d = daten or {}
                if not (d.get("text") or "").strip():
                    raise ApiFehler("Notiz ist leer.")
                try:
                    wer = benutzer.aktuell()["name"] if benutzer.aktuell() else ""
                except (KeyError, IndexError, TypeError):
                    wer = ""
                cur = con.execute(
                    "INSERT INTO notizen (kunde_id, auftrag_id, lieferant_id, text, angelegt, benutzer) VALUES (?,?,?,?,?,?)",
                    (d.get("kunde_id"), d.get("auftrag_id"), d.get("lieferant_id"), d["text"].strip(), jetzt(), wer or ""))
                return dict(con.execute("SELECT * FROM notizen WHERE id=?", (cur.lastrowid,)).fetchone())
            if methode == "DELETE" and rid:
                con.execute("DELETE FROM notizen WHERE id=?", (rid,))
                return {"ok": True}

        # ---------- Offene Posten / Briefe (Belegmodul folgt) ----------
        if res in ("offeneposten", "briefe") and methode == "GET":
            tab = "offene_posten" if res == "offeneposten" else "briefe"
            sql = (f"SELECT t.*, k.kurzname AS kunde, a.nummer AS auftragsnr FROM {tab} t "
                   "LEFT JOIN kunden k ON k.id=t.kunde_id LEFT JOIN auftraege a ON a.id=t.auftrag_id WHERE 1=1")
            p = []
            if q.get("kunde"):
                sql += " AND t.kunde_id=?"
                p.append(int(q["kunde"]))
            if q.get("lieferant") and res == "briefe":
                sql += " AND t.lieferant_id=?"
                p.append(int(q["lieferant"]))
            return zeilen(con.execute(sql + " ORDER BY t.datum DESC", p))

        if res == "version":
            return {"version": VERSION, "ordner": BASIS}

        if res == "statistik" and methode == "GET":
            return statistik(con)

        if res == "naechste" and methode == "GET":
            return {"auftrag": naechste_auftragsnummer(con), "kunde": kundennummer_info(con)["naechste"],
                    "rechnung": rechnungsnummer_info(con)["naechste"]}
        if res == "fenster" and methode == "POST":
            ziel = "#" + str((daten or {}).get("hash") or "").lstrip("#")
            threading.Thread(target=app_fenster, args=(f"{pc_adresse()}/{ziel if ziel != '#' else ''}",), daemon=True).start()
            return {"ok": True, "app": os.name == "nt"}
        if res == "nummernkreise":
            if methode == "GET":
                return {"rechnung": rechnungsnummer_info(con), "auftrag": auftragsnummer_info(con), "kunde": kundennummer_info(con)}
            if methode == "PUT":
                d = daten or {}
                art, naechste = d.get("art"), int(fl(d.get("naechste")))
                info = {"rechnung": rechnungsnummer_info, "auftrag": auftragsnummer_info}.get(art)
                if art == "kunde":
                    akt = kundennummer_info(con)
                    if naechste < akt["naechste"]:
                        raise ApiFehler(f"Der Zähler kann nur erhöht werden. Nächste Kundennummer ist derzeit {akt['naechste']}.")
                    zaehler_setzen(con, "kunde", naechste - 1)
                    prot(con, "nummernkreis", "kunde", f"Nächste Kundennummer von {akt['naechste']} auf {naechste} gesetzt", {"von": akt["naechste"], "auf": naechste})
                elif info:
                    akt = info(con)
                    if naechste < akt["naechste_lfd"]:
                        raise ApiFehler(f"Der Zähler kann nur erhöht werden (sonst entstehen doppelte Nummern). Nächste Nummer ist derzeit {akt['naechste']}.")
                    zaehler_setzen(con, art, naechste - 1, akt["jahr"])
                    prot(con, "nummernkreis", art, f"Nummernkreis {art} {akt['jahr']}: nächste Nummer von {akt['naechste']} auf {akt['praefix'] if 'praefix' in akt else ''}{naechste:04d} gesetzt",
                         {"von": akt["naechste"], "auf_lfd": naechste, "jahr": akt["jahr"]})
                else:
                    raise ApiFehler("Unbekannter Nummernkreis.")
                return {"rechnung": rechnungsnummer_info(con), "auftrag": auftragsnummer_info(con), "kunde": kundennummer_info(con)}

    raise ApiFehler("Unbekannte Anfrage", 404)


class Handler(BaseHTTPRequestHandler):
    server_version, sys_version = "Jahresring", ""   # keine Python-Version nach außen melden

    def log_message(self, *args):
        pass

    # Dateitypen, die der Browser gefahrlos direkt anzeigen darf. Alles andere (HTML, SVG, XML …) könnte Skripte
    # enthalten, die mit der Anmeldung des Benutzers arbeiten – solche Dateien werden nur zum Herunterladen angeboten.
    SICHER_ANZEIGEN = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "text/plain", "text/csv"}

    PACKBAR = {"application/json", "text/html", "text/css", "text/javascript", "application/javascript", "text/plain", "image/svg+xml",
               "application/xml", "text/xml", "text/calendar", "application/manifest+json"}

    def senden(self, code, inhalt, typ, extra=None):
        csp = "frame-ancestors 'self'"
        if extra and str(extra.get("Content-Disposition", "")).startswith("inline") and typ.split(";")[0].strip().lower() not in self.SICHER_ANZEIGEN:
            extra = {**extra, "Content-Disposition": "attachment" + extra["Content-Disposition"][6:]}
            csp = "sandbox; default-src 'none'; frame-ancestors 'self'"
        # Über das Netz (Tablet, Handy, zweiter PC) werden Texte und Daten gepackt übertragen – Listen schrumpfen auf etwa ein Zehntel.
        # Am Büro-PC selbst lohnt das nicht (keine Leitung dazwischen).
        packen = (len(inhalt) > 1400 and typ.split(";")[0].strip() in self.PACKBAR and "gzip" in (self.headers.get("Accept-Encoding") or "")
                  and not self.lokal() and not (extra and "Content-Encoding" in extra))
        if packen:
            inhalt = gzip.compress(inhalt, 4)
        self.send_response(code)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(inhalt)))
        if packen:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Cache-Control", "no-store")
        # Grundschutz im Browser: keine Einbettung in fremde Seiten, kein MIME-Raten, keine Adresse an fremde Seiten
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Content-Security-Policy", csp)
        self.send_header("Referrer-Policy", "same-origin")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(inhalt)

    def json(self, obj, code=200, extra=None):
        self.senden(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", extra)

    def cookie(self):
        for teil in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = teil.strip().partition("=")
            if k == benutzer.COOKIE:
                return v
        return ""

    def lokal(self):
        """Anfrage direkt von diesem PC."""
        return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def umzug(self, methode, pfad):
        """Browserdaten und Anmeldung vom PC-Fenster unter der Netzwerkadresse auf localhost übertragen (nur am PC)."""
        if not (self.lokal() or self.ip() == lokale_ip()):
            return self.json({"fehler": "Nur am Büro-PC."}, 403)
        jetzt_ = datetime.now().timestamp()
        for k in [k for k, v in UMZUG.items() if v["zeit"] < jetzt_ - 300]:
            UMZUG.pop(k, None)
        if methode == "POST" and pfad == "/api/umzug":
            laenge = int(self.headers.get("Content-Length") or 0)
            if laenge > 5_000_000:
                return self.json({"fehler": "Zu groß."}, 413)
            try:
                daten = json.loads(self.rfile.read(laenge) or b"{}")
            except ValueError:
                daten = {}
            t = secrets.token_urlsafe(24)
            UMZUG[t] = {"zeit": jetzt_, "daten": daten.get("speicher") or {}, "token": self.token}
            return self.json({"t": t, "port": PORT})
        if methode == "POST" and pfad == "/api/umzug/fertig":
            if not self.lokal():
                return self.json({"fehler": "Nur über localhost."}, 403)
            with open(umzug_erledigt_pfad(), "w", encoding="utf-8") as f:
                f.write(jetzt())
            return self.json({"ok": True})
        m = re.fullmatch(r"/api/umzug/([\w-]+)", pfad)
        if methode == "GET" and m and self.lokal():
            e = UMZUG.pop(m.group(1), None)
            if not e:
                return self.json({"fehler": "Abgelaufen."}, 404)
            extra = None
            if e["token"]:
                with verbindung() as con:
                    gueltig = benutzer.sitzung_benutzer(con, e["token"])
                    con.commit()
                if gueltig:
                    extra = {"Set-Cookie": self.setze_cookie(e["token"])}
            return self.json({"speicher": e["daten"]}, extra=extra)
        return self.json({"fehler": "Unbekannte Anfrage"}, 404)

    def ip(self):
        return self.client_address[0]

    def verarbeiten(self, methode):
        """Anmeldung prüfen, dann die eigentliche Anfrage bearbeiten."""
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        pfad = u.path
        benutzer.setze_aktuell(None)
        ANFRAGE.lokal = self.lokal() or self.ip() == lokale_ip()   # am Büro-PC selbst (auch über dessen Netzwerkadresse)
        self.token = self.cookie()
        if HTTPS["stempel_port"] and methode == "GET" and pfad in ("", "/") and self.server.server_address[1] == HTTPS["stempel_port"]:
            return self.senden(302, b"", "text/plain", {"Location": "/stempel"})   # unter dieser Adresse läuft nur die Stempeluhr
        if HTTPS["aktiv"] or pfad.startswith("/zertifikat"):
            if methode == "GET" and pfad in ("/zertifikat", "/zertifikat/"):
                import zert
                seite = ZERT_SEITE.replace("__ADRESSE__", f"https://{lokale_ip()}:{HTTPS['port']}").replace("__FP__", zert.fingerabdruck(DATEN) or "–").replace(
                    "__STEMPEL__", f"https://{lokale_ip()}:{HTTPS['stempel_port'] or HTTPS['port']}/stempel")
                return self.senden(200 if HTTPS["aktiv"] else 404, (seite if HTTPS["aktiv"] else "https ist nicht eingeschaltet.").encode("utf-8"), "text/html; charset=utf-8")
            if methode == "GET" and pfad in ("/zertifikat/jahresring-ca.crt", "/zertifikat/jahresring-ca.pem"):
                datei = os.path.join(DATEN, "zertifikat", pfad.rsplit("/", 1)[1])
                if not os.path.isfile(datei):
                    return self.senden(404, b"", "text/plain")
                with open(datei, "rb") as f:
                    return self.senden(200, f.read(), "application/x-x509-ca-cert", {"Content-Disposition": f"attachment; filename={os.path.basename(datei)}"})
            if HTTPS["modus"] == "nur" and not self.ist_https() and not ANFRAGE.lokal:
                # andere Geräte nur noch verschlüsselt: Seiten umleiten, Datenanfragen ablehnen
                host = (self.headers.get("Host") or lokale_ip()).rsplit(":", 1)[0]
                if methode == "GET" and not pfad.startswith("/api/"):
                    zielport = HTTPS["stempel_port"] if pfad.startswith("/stempel") and HTTPS["stempel_port"] else HTTPS["port"]
                    return self.senden(307, b"", "text/plain", {"Location": f"https://{host}:{zielport}{self.path}"})
                return self.json({"fehler": f"Bitte die verschlüsselte Adresse verwenden: https://{host}:{HTTPS['port']}"}, 403)
        # Schutz gegen Anfragen fremder Webseiten (CSRF): ändernde Anfragen nur von der eigenen Adresse
        if methode not in ("GET", "HEAD"):
            herkunft = self.headers.get("Origin") or ""
            if herkunft and herkunft != "null" and urlparse(herkunft).netloc.lower() != (self.headers.get("Host") or "").lower():
                return self.json({"fehler": "Anfrage von fremder Seite abgelehnt."}, 403)
        try:
            # 1. öffentlich: Programmdateien, Logo, Version, Anmeldung
            if pfad.startswith("/api/anmeldung"):
                return self.anmeldung(methode, pfad)
            if pfad == "/api/umzug" or pfad.startswith("/api/umzug/"):
                return self.umzug(methode, pfad)
            if pfad in ("/api/version", "/api/logo"):
                return self._verarbeiten(methode)
            if not re.match(r"/(api|druck|papier|liste)(/|$)", pfad) and pfad not in ("/zuschnitt", "/zuschnitt.html", "/zuschnitt/"):
                return self._verarbeiten(methode)
            # 2. interner Aufruf (PDF-Erzeugung auf diesem PC)
            ref = self.headers.get("Referer") or ""
            if self.lokal() and (q.get("intern") == INTERN or f"intern={INTERN}" in ref):
                return self._verarbeiten(methode)
            # 3. angemeldeter Benutzer
            with verbindung() as con:
                b = benutzer.sitzung_benutzer(con, self.token)
                con.commit()
            if not b:
                if pfad.startswith("/api/"):
                    return self.json({"fehler": "Bitte anmelden.", "anmelden": True}, 401)
                return self.senden(302, b"", "text/plain", {"Location": "/#/anmelden"})
            benutzer.setze_aktuell(b)
            self.roh_recht(pfad)
            return self._verarbeiten(methode)
        except benutzer.Fehler as f:
            if pfad.startswith("/api/"):
                return self.json({"fehler": str(f)}, f.code)
            return self.senden(f.code, str(f).encode("utf-8"), "text/plain; charset=utf-8")
        finally:
            benutzer.setze_aktuell(None)

    def roh_recht(self, pfad):
        """Rechte für Seiten/Dateien außerhalb von /api/<ressource>."""
        if re.fullmatch(r"/druck/arbeitsschutz/(ba/\d+|notfall)(\.pdf)?", pfad) and (dict(benutzer.aktuell() or {}).get("mitarbeiter_id") or benutzer.darf("arbeitsschutz", 1)):
            return   # Betriebsanweisungen sehen alle Beschäftigten (auch in der Stempeluhr)
        if re.fullmatch(r"/druck/monatsbeleg/(\d+)/\d{4}-\d{2}(\.pdf)?", pfad) and not benutzer.darf("personal", 1):
            mm = re.fullmatch(r"/druck/monatsbeleg/(\d+)/", pfad[:pfad.rindex("/") + 1])
            if mm and int(mm.group(1)) == (dict(benutzer.aktuell() or {}).get("mitarbeiter_id") or -1):
                return   # den eigenen Monatsbeleg darf jeder Mitarbeiter ansehen
        regeln = [(r"/api/service/", ["einstellungen"]), (r"/druck/mahnung", ["op"]), (r"/druck/monatsbeleg", ["personal"]), (r"/druck/arbeitsschutz", ["arbeitsschutz"]), (r"/druck/", ["auftraege"]), (r"/papier/", ["auftraege"]),
                  (r"/liste/", ["material"]), (r"/zuschnitt", ["auftraege"]), (r"/api/mahnungen/", ["op"]),
                  (r"/api/zahlungen/", ["lieferanten"]), (r"/api/eingang/", ["lieferanten"]),
                  (r"/api/kalender/export", ["kalender"]), (r"/api/unterschrift", ["einstellungen", "auftraege"]),
                  (r"/api/korrespondenz/", ["kunden", "auftraege", "lieferanten"]), (r"/api/bautagebuch/foto/", ["auftraege"])]
        for muster, bereiche in regeln:
            if pfad.startswith(muster):
                if not any(benutzer.darf(x, 1) for x in bereiche):
                    raise benutzer.Fehler("Dafür fehlt die Berechtigung.", 403)
                r = benutzer.aktuelle_rechte()
                if muster == "/api/service/" and not benutzer.darf("einstellungen", 2):
                    raise benutzer.Fehler("Dafür fehlt die Berechtigung.", 403)
                if muster == "/druck/" and r and not r["inhaber"] and r["auftrag_reiter"] == "werkstatt":
                    # Werkstatt darf Lieferschein und Abnahmeprotokoll ansehen (zum Unterschreiben lassen), sonst nichts
                    mm = re.fullmatch(r"/druck/(\d+)(\.pdf)?", pfad)
                    if mm:
                        with verbindung() as con:
                            br = con.execute("SELECT art FROM belege WHERE id=?", (int(mm.group(1)),)).fetchone()
                        if br and br["art"] in ("lieferschein", "abnahme"):
                            return
                    raise benutzer.Fehler("Dafür fehlt die Berechtigung (nur Werkstatt).", 403)
                return

    def anmeldung(self, methode, pfad):
        teil = pfad[len("/api/anmeldung"):].strip("/")
        n = int(self.headers.get("Content-Length") or 0)
        if n > 64 * 1024:   # Anmeldung ohne Sitzung: nur kleine Anfragen annehmen
            return self.json({"fehler": "Anfrage zu groß."}, 413)
        d = json.loads(self.rfile.read(n).decode("utf-8")) if methode in ("POST", "PUT") and n else {}
        with verbindung() as con:
            if methode == "GET" and not teil:
                b = benutzer.sitzung_benutzer(con, self.token)
                con.commit()
                aus = {"eingerichtet": benutzer.anzahl(con) > 0, "benutzer": benutzer.oeffentlich(b), "firma": einstellungen(con).get("firma")}
                if b and b["mitarbeiter_id"]:
                    m = con.execute("SELECT id, vorname, nachname, kuerzel FROM mitarbeiter WHERE id=?", (b["mitarbeiter_id"],)).fetchone()
                    aus["mitarbeiter"] = dict(m) if m else None
                return self.json(aus)
            if methode == "POST" and teil == "einrichten":
                if benutzer.anzahl(con) > 0:
                    raise benutzer.Fehler("Es gibt schon Benutzer. Bitte anmelden.", 403)
                if not self.lokal():
                    raise benutzer.Fehler("Den ersten Zugang bitte direkt am Büro-PC anlegen.", 403)
                benutzer.api(con, "POST", ["benutzer"], {}, {"login": d.get("login"), "name": d.get("name"), "passwort": d.get("passwort"),
                                                            "rolle": "inhaber"})
                e0 = einstellungen(con)
                for k, v in (("firma", str(d.get("firma") or "").strip()), ("firma_inhaber", str(d.get("name") or "").strip())):
                    if v and not e0.get(k):
                        con.execute("INSERT OR REPLACE INTO einstellungen (schluessel, wert) VALUES (?, ?)", (k, json.dumps(v)))
                token, b = benutzer.anmelden(con, d.get("login"), d.get("passwort"), self.headers.get("User-Agent", ""), self.ip())
                con.commit()
                return self.json({"ok": True}, extra={"Set-Cookie": self.setze_cookie(token)})
            if methode == "POST" and teil == "anmelden":
                token, b = benutzer.anmelden(con, d.get("login"), d.get("passwort"), self.headers.get("User-Agent", ""), self.ip())
                con.commit()
                return self.json({"ok": True, "benutzer": benutzer.oeffentlich(b)}, extra={"Set-Cookie": self.setze_cookie(token)})
            if methode == "POST" and teil == "abmelden":
                benutzer.abmelden(con, self.token)
                con.commit()
                return self.json({"ok": True}, extra={"Set-Cookie": f"{benutzer.COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"})
            if methode == "POST" and teil == "vergessen":
                e = einstellungen(con)
                cfg = e.get("mail") or {}
                if not (cfg.get("smtp_server") and cfg.get("passwort")):
                    raise benutzer.Fehler("Der E-Mail-Versand ist in Jahresring noch nicht eingerichtet. Bitte den Inhaber bitten, das "
                                          "Passwort unter Einstellungen › Benutzer neu zu setzen (Inhaber: Notfallschlüssel verwenden).")
                b, code = benutzer.reset_code_anlegen(con, d.get("login"), self.ip())
                hinweis = ("Falls es den Benutzer gibt und eine E-Mail-Adresse hinterlegt ist, wurde ein Code gesendet. "
                           f"Er gilt {benutzer.CODE_MINUTEN} Minuten.")
                if b:
                    an = benutzer.reset_adresse(con, b, cfg.get("adresse") or e.get("email") or "")
                    if not an:
                        con.rollback()
                        prot(con, "passwort", b["login"], f"Passwort vergessen angefordert für {b['login']}, aber keine E-Mail-Adresse hinterlegt")
                        con.commit()
                        return self.json({"ok": True, "hinweis": hinweis})
                    text = (f"Hallo {b['name'] or b['login']},\n\nfür Ihren Zugang „{b['login']}“ in Jahresring wurde ein neues Passwort angefordert.\n\n"
                            f"Code: {code}\n\nDer Code gilt {benutzer.CODE_MINUTEN} Minuten und nur einmal. Geben Sie ihn auf der Anmeldeseite "
                            "unter „Passwort vergessen?“ zusammen mit dem neuen Passwort ein.\n\n"
                            "Wenn Sie das nicht selbst angefordert haben, können Sie diese Mail ignorieren; Ihr bisheriges Passwort bleibt gültig.\n\n"
                            f"{e.get('firma') or 'Jahresring'}")
                    try:
                        mailversand.senden(cfg, an, "", f"Jahresring: Code zum Zurücksetzen des Passworts ({code})", text, [], kopie_an_mich=False)
                    except mailversand.MailFehler as f:
                        con.rollback()
                        raise benutzer.Fehler(f"Die Mail mit dem Code konnte nicht gesendet werden: {f}")
                    prot(con, "passwort", b["login"], f"Code zum Zurücksetzen des Passworts an {benutzer.maskieren(an)} gesendet (von {self.ip()})")
                con.commit()
                return self.json({"ok": True, "hinweis": hinweis})
            if methode == "POST" and teil == "zuruecksetzen":
                b, art = benutzer.reset_ausfuehren(con, d.get("login"), d.get("code"), d.get("neu"), self.ip())
                prot(con, "passwort", b["login"], f"Passwort von {b['login']} zurückgesetzt mit " +
                     ("Code aus der E-Mail" if art == "mail" else "Notfallschlüssel (jetzt verbraucht)") + f" (von {self.ip()}); alle Geräte abgemeldet")
                con.commit()
                e = einstellungen(con)
                cfg = e.get("mail") or {}
                an = benutzer.reset_adresse(con, b, cfg.get("adresse") or e.get("email") or "")
                if an and cfg.get("smtp_server") and cfg.get("passwort"):
                    try:   # Hinweis an den Benutzer, damit ein fremdes Zurücksetzen auffällt
                        mailversand.senden(cfg, an, "", "Jahresring: Ihr Passwort wurde geändert",
                                           f"Hallo {b['name'] or b['login']},\n\ndas Passwort für Ihren Zugang „{b['login']}“ wurde soeben "
                                           f"{'mit dem Code aus der E-Mail' if art == 'mail' else 'mit dem Notfallschlüssel'} neu gesetzt. "
                                           "Alle Geräte wurden abgemeldet.\n\nWaren Sie das nicht, melden Sie sich bitte sofort beim Inhaber.\n\n"
                                           f"{e.get('firma') or 'Jahresring'}", [], kopie_an_mich=False)
                    except Exception:  # noqa: BLE001  Hinweis ist nicht entscheidend
                        pass
                token, b2 = benutzer.anmelden(con, b["login"], d.get("neu"), self.headers.get("User-Agent", ""), self.ip())
                con.commit()
                return self.json({"ok": True, "notfall_verbraucht": art == "notfall"}, extra={"Set-Cookie": self.setze_cookie(token)})
            if methode == "POST" and teil in ("email", "notfallschluessel"):
                b = benutzer.sitzung_benutzer(con, self.token)
                if not b:
                    raise benutzer.Fehler("Bitte anmelden.", 401)
                if teil == "email":
                    werte = benutzer._daten(con, {"email": d.get("email")}, b)
                    con.execute("UPDATE benutzer SET email=?, geaendert=? WHERE id=?", (werte["email"], jetzt(), b["id"]))
                    con.commit()
                    return self.json({"ok": True, "email": werte["email"]})
                if b["rolle"] != "inhaber":
                    raise benutzer.Fehler("Einen Notfallschlüssel gibt es nur für Inhaber-Zugänge.", 403)
                if not benutzer.pw_pruefen(d.get("passwort"), b["pw_hash"]):
                    raise benutzer.Fehler("Das Passwort stimmt nicht.")
                schl = benutzer.notfallschluessel_erzeugen(con, b["id"])
                prot(con, "passwort", b["login"], f"Neuer Notfallschlüssel für {b['login']} erzeugt (ein früherer ist damit ungültig)")
                con.commit()
                return self.json({"ok": True, "schluessel": schl})
            if methode == "POST" and teil == "passwort":
                b = benutzer.sitzung_benutzer(con, self.token)
                if not b:
                    raise benutzer.Fehler("Bitte anmelden.", 401)
                if not benutzer.pw_pruefen(d.get("alt"), b["pw_hash"]):
                    raise benutzer.Fehler("Das bisherige Passwort stimmt nicht.")
                benutzer.pw_regeln(d.get("neu"), b["rolle"])
                con.execute("UPDATE benutzer SET pw_hash=?, geaendert=? WHERE id=?", (benutzer.pw_hash(d["neu"]), jetzt(), b["id"]))
                con.execute("DELETE FROM sitzungen WHERE benutzer_id=? AND token<>?", (b["id"], benutzer.token_hash(self.token)))
                con.commit()
                return self.json({"ok": True})
        return self.json({"fehler": "Unbekannte Anfrage"}, 404)

    def ist_https(self):
        return isinstance(self.connection, ssl.SSLSocket)

    def setze_cookie(self, token):
        return (f"{benutzer.COOKIE}={token}; Path=/; Max-Age={benutzer.SITZUNG_TAGE * 86400}; HttpOnly; SameSite=Strict"
                + ("; Secure" if self.ist_https() else ""))   # über https angemeldet: Anmeldung nie unverschlüsselt mitschicken

    def do_GET(self):
        self.verarbeiten("GET")

    def do_POST(self):
        self.verarbeiten("POST")

    def do_PUT(self):
        self.verarbeiten("PUT")

    def do_DELETE(self):
        self.verarbeiten("DELETE")

    def _verarbeiten(self, methode):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if re.fullmatch(r"/druck/\d+\.pdf", u.path) and methode == "GET":
                bid = int(u.path.split("/")[2][:-4])
                tmp = os.path.join(DATEN, "tmp")
                os.makedirs(tmp, exist_ok=True)
                ziel = os.path.join(tmp, f"vorschau-{bid}.pdf")
                pdf_rendern(bid, ziel)
                with open(ziel, "rb") as f:
                    return self.senden(200, f.read(), "application/pdf", {"Content-Disposition": "inline; filename=vorschau.pdf"})
            if u.path.startswith("/api/vorlage/") and methode == "GET":
                name = u.path.split("/")[-1]
                pfad = os.path.join(VORLAGEN_PFAD, name)
                if not re.fullmatch(r"[a-z_]+-\d+\.(svg|png|jpg)", name) or not os.path.isfile(pfad):
                    return self.senden(404, b"", "text/plain")
                typ = {"svg": "image/svg+xml", "png": "image/png", "jpg": "image/jpeg"}[name.rsplit(".", 1)[1]]
                with open(pfad, "rb") as f:
                    return self.senden(200, f.read(), typ, {"Cache-Control": "max-age=60"})
            m = re.fullmatch(r"/api/belege/(\d+)/(xrechnung|zugferd)\.xml", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    b = beleg_laden(con, int(m.group(1)))
                    if b["status"] not in ("fest", "storniert"):
                        raise ApiFehler("Die E-Rechnung gibt es erst nach dem Festschreiben (dann steht die Rechnungsnummer fest).")
                    try:
                        xml = erechnung.cii_xml(b, m.group(2) == "xrechnung", auftrag_kunde(con, b["auftrag_id"]))
                    except erechnung.ERechnungFehler as f:
                        raise ApiFehler(str(f))
                name = sauber(f"{b['nummer']}_{'XRechnung' if m.group(2) == 'xrechnung' else 'ZUGFeRD'}") + ".xml"
                return self.senden(200, xml, "application/xml; charset=utf-8",
                                   {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
            m = re.fullmatch(r"/druck/brief/(\d+)", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    html_text = brief_html(con, int(m.group(1)), q.get("pdf") == "1")
                return self.senden(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
            m = re.fullmatch(r"/api/korrespondenz/(\d+)/eml", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    pf = korrespondenz.eml_pfad(con, int(m.group(1)))
                if not pf:
                    return self.json({"fehler": "Original nicht vorhanden"}, 404)
                with open(pf, "rb") as f:
                    return self.senden(200, f.read(), "message/rfc822", {"Content-Disposition": f"attachment; filename=mail_{m.group(1)}.eml"})
            m = re.fullmatch(r"/papier/bautagebuch/(\d+)", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    html_text = bautagebuch_html(con, int(m.group(1)), q)
                return self.senden(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
            m = re.fullmatch(r"/api/bautagebuch/foto/([\w.]+)", u.path)
            if m and methode == "GET":
                pf = bautagebuch.foto_pfad(m.group(1))
                if not pf:
                    return self.json({"fehler": "Foto nicht gefunden"}, 404)
                with open(pf, "rb") as f:
                    return self.senden(200, f.read(), mimetypes.guess_type(pf)[0] or "image/jpeg")
            m = re.fullmatch(r"/papier/projekt/(\d+)/zeitbericht", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    html_text = projekt_zeitbericht_html(con, int(m.group(1)), q, pdf=q.get("pdf") == "1")
                return self.senden(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
            m = re.fullmatch(r"/papier/projekt/(\d+)", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    html_text = projekt_html(con, int(m.group(1)))
                return self.senden(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
            m = re.fullmatch(r"/papier/montage/(\d+)", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    html_text = montage_html(con, int(m.group(1)), pdf=q.get("pdf") == "1")
                return self.senden(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
            m = re.fullmatch(r"/papier/(\d+)/zuschnitt\.csv", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    a = auftrag_laden(con, int(m.group(1)))
                    text = werkstatt.zuschnitt_csv(auftrag_rechnen(con, a["id"]), None, einstellungen(con).get("zuschnitt_zugabe") or {})
                return self.senden(200, text.encode("utf-8"), "text/csv; charset=utf-8",
                                   {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(a['nummer'] + '_Zuschnittliste.csv')}"})
            m = re.fullmatch(r"/papier/(\d+)/([a-z]+)", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    html_text = papier_html(con, int(m.group(1)), m.group(2), q, pdf=q.get("pdf") == "1")
                return self.senden(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
            if u.path in ("/zuschnitt", "/zuschnitt.html") and methode == "GET":
                return self.senden(302, b"", "text/plain", {"Location": "/zuschnitt/" + (("?" + u.query) if u.query else "")})
            if u.path in ("/zuschnitt/", "/zuschnitt/index.html") and methode == "GET":
                # eingebautes Zuschnittprogramm im Büro-Modus: Lager aus der Büro-Datenbank, Plan aus 40_Kalkulation
                with open(os.path.join(STATIC, "zuschnitt", "index.html"), "rb") as f:
                    roh = f.read()
                logo = "true" if any(os.path.exists(os.path.join(DATEN, n)) for n in ("logo.png", "logo.jpg")) else "false"
                with verbindung() as con_e:
                    ew, eh = etikett_mass(einstellungen(con_e))
                roh = roh.replace(b"<head>", ('<head><script>window.JAHRESRING={api:"/api/",logo:%s,etikett:{w:%s,h:%s}};</script>' % (logo, ew, eh)).encode(), 1)
                return self.senden(200, roh, "text/html; charset=utf-8", {"Cache-Control": "no-store"})
            if u.path == "/liste/etiketten" and methode == "GET":
                with verbindung() as con:
                    return self.senden(200, etiketten_seite(con, q).encode("utf-8"), "text/html; charset=utf-8")
            m = re.fullmatch(r"/druck/monatsbeleg/(\d+)/(\d{4}-\d{2})(\.pdf)?", u.path)
            if m and methode == "GET":
                if m.group(3):
                    tmp = os.path.join(DATEN, "tmp")
                    os.makedirs(tmp, exist_ok=True)
                    ziel = os.path.join(tmp, f"monatsbeleg-{m.group(1)}-{m.group(2)}.pdf")
                    pdf_url_rendern(f"http://127.0.0.1:{PORT}/druck/monatsbeleg/{m.group(1)}/{m.group(2)}?pdf=1", ziel)
                    with verbindung() as con:
                        ma = con.execute("SELECT nummer, nachname FROM mitarbeiter WHERE id=?", (int(m.group(1)),)).fetchone()
                    name = sauber(f"Monatsbeleg {ma['nummer'] if ma else ''} {ma['nachname'] if ma else ''} {m.group(2)}") + ".pdf"
                    with open(ziel, "rb") as f:
                        return self.senden(200, f.read(), "application/pdf", {"Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}"})
                with verbindung() as con:
                    html_text = personal.monatsbeleg_html(con, int(m.group(1)), m.group(2), einstellungen(con).get("firma", ""),
                                                          als_pdf=q.get("pdf") == "1", sig=monatsbeleg_sig_bilder(con, int(m.group(1)), m.group(2)))
                return self.senden(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
            m = re.fullmatch(r"/druck/arbeitsschutz/(gb|fassung|ba|unterweisung|gefahrstoffverzeichnis|notfall)(?:/(\d+))?(\.pdf)?", u.path)
            if m and methode == "GET":
                teil, nr = m.group(1), int(m.group(2) or 0)
                if m.group(3):
                    tmp = os.path.join(DATEN, "tmp")
                    os.makedirs(tmp, exist_ok=True)
                    ziel = os.path.join(tmp, f"as-{teil}-{nr}-{secrets.token_hex(4)}.pdf")
                    zusatz = "&entwurf=1" if q.get("entwurf") == "1" else ""
                    pdf_url_rendern(f"http://127.0.0.1:{PORT}/druck/arbeitsschutz/{teil}{'/' + str(nr) if nr else ''}?pdf=1{zusatz}", ziel)
                    with verbindung() as con:
                        name = sauber(as_druck_name(con, teil, nr)) + ".pdf"
                    try:
                        with open(ziel, "rb") as f:
                            return self.senden(200, f.read(), "application/pdf", {"Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}"})
                    finally:
                        try:
                            os.remove(ziel)
                        except OSError:
                            pass
                with verbindung() as con:
                    html_text = as_druck_html(con, teil, nr, q, q.get("pdf") == "1")
                return self.senden(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
            m = re.fullmatch(r"/druck/mahnung/(\d+)", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    html_text = mahnung_html(con, int(m.group(1)), als_pdf=q.get("pdf") == "1")
                return self.senden(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
            m = re.fullmatch(r"/api/mahnungen/(\d+)/pdf", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    pfad = mahnung_pdf(con, int(m.group(1)))
                    con.commit()
                with open(pfad, "rb") as f:
                    return self.senden(200, f.read(), "application/pdf",
                                       {"Content-Disposition": f"inline; filename*=UTF-8''{quote(os.path.basename(pfad))}"})
            if re.fullmatch(r"/druck/\d+", u.path) and methode == "GET":
                bid = int(u.path.split("/")[2])
                abstand = 0.0
                try:
                    abstand = max(0.0, min(250.0, float(q.get("abstand") or 0)))
                except ValueError:
                    pass
                if "drucken" in q and not abstand:
                    # Drucken aus dem Browser: Abstand für „letzte Seite unten bündig“ vorher messen
                    with verbindung() as con:
                        bd = beleg_laden(con, bid)
                        e = einstellungen(con)
                    if bd["druck"].get("unten_buendig"):
                        abstand = unten_abstand(bid, e)[0]
                with verbindung() as con:
                    html_text = druck_html(con, bid, als_pdf=q.get("pdf") == "1", abstand=abstand, marken=q.get("marken") == "1")
                return self.senden(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
            m = re.fullmatch(r"/api/service/export/([A-Za-z0-9_.\-]+\.zip)", u.path)
            if m and methode == "GET":
                pfad = os.path.join(export.ordner(), m.group(1))
                if not os.path.isfile(pfad):
                    return self.senden(404, b"", "text/plain")
                with open(pfad, "rb") as f:
                    return self.senden(200, f.read(), "application/zip", {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(m.group(1))}"})
            if u.path == "/api/service/protokoll.csv" and methode == "GET":
                with verbindung() as con:
                    text = protokoll.csv_text(con)
                return self.senden(200, text.encode("utf-8"), "text/csv; charset=utf-8",
                                   {"Content-Disposition": f"attachment; filename=Protokoll_Jahresring_{date.today().isoformat()}.csv"})
            if u.path == "/api/kalender/export.ics":
                with verbindung() as con:
                    ts = []
                    for t in con.execute("SELECT t.*, a.nummer, a.bezeichnung, k.kurzname FROM termine t LEFT JOIN auftraege a "
                                         "ON a.id=t.auftrag_id LEFT JOIN kunden k ON k.id=a.kunde_id"):
                        if not termin_sichtbar(t):
                            continue
                        titel = " · ".join(x for x in [t["typ"], t["titel"] or (f"{t['nummer']} {t['bezeichnung']}" if t["nummer"] else ""),
                                                       t["kurzname"]] if x)
                        ts.append({"art": "t", "id": t["id"], "von": t["von"], "bis": t["bis"], "zeit_von": t["zeit_von"],
                                   "zeit_bis": t["zeit_bis"], "titel": titel, "notiz": t["notiz"]})
                    kr = (benutzer.aktuelle_rechte() or {}).get("kalender") or {}
                    for a in con.execute("SELECT a.*, k.kurzname FROM auftraege a JOIN kunden k ON k.id=a.kunde_id WHERE a.plan_von<>''"):
                        if not benutzer.ist_inhaber() and (kr.get("typen") or kr.get("nur_eigene")):
                            break   # eingeschränkte Kalendersicht: keine Auftragsplanung
                        ts.append({"art": "plan", "id": a["id"], "von": a["plan_von"], "bis": a["plan_bis"] or a["plan_von"],
                                   "titel": f"(geplant) {a['nummer']} {a['bezeichnung']} · {a['kurzname']}", "vorlaeufig": True})
                return self.senden(200, kal.ics_export(ts).encode("utf-8"), "text/calendar; charset=utf-8",
                                   {"Content-Disposition": 'attachment; filename="Jahresring-Planung.ics"'})
            if u.path.startswith("/api/bild/") and methode == "GET":
                name = os.path.basename(u.path)
                pfad = os.path.join(BILDER, name)
                if not re.fullmatch(r"[0-9a-f]{16}(_[kmg])?\.(jpg|png|webp)", name) or not os.path.isfile(pfad):
                    return self.senden(404, b"", "text/plain")
                typ = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[name.rsplit(".", 1)[1]]
                with open(pfad, "rb") as f:
                    return self.senden(200, f.read(), typ, {"Cache-Control": "max-age=86400"})
            m = re.fullmatch(r"/liste/(werkzeuge|lager)(\.pdf)?", u.path)
            if m and methode == "GET":
                if m.group(2):
                    tmp = os.path.join(DATEN, "tmp")
                    os.makedirs(tmp, exist_ok=True)
                    ziel = os.path.join(tmp, f"liste-{m.group(1)}.pdf")
                    query = "&".join(f"{k}={quote(str(v))}" for k, v in q.items())
                    pdf_url_rendern(f"http://127.0.0.1:{PORT}/liste/{m.group(1)}?pdf=1&{query}", ziel)
                    name = f"{LISTEN[m.group(1)]} {date.today().isoformat()}.pdf"
                    with open(ziel, "rb") as f:
                        return self.senden(200, f.read(), "application/pdf", {"Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}"})
                with verbindung() as con:
                    html_text = liste_html(con, m.group(1), q, pdf=q.get("pdf") == "1")
                return self.senden(200, html_text.encode("utf-8"), "text/html; charset=utf-8")
            m = re.fullmatch(r"/api/eingang/datei/([0-9a-f]{32})", u.path)
            if m and methode == "GET":
                for endung, typ in ((".pdf", "application/pdf"), (".xml", "application/xml")):
                    pfad = os.path.join(DATEN, "tmp", f"eingang-{m.group(1)}{endung}")
                    if os.path.isfile(pfad):
                        with open(pfad, "rb") as f:
                            return self.senden(200, f.read(), typ, {"Content-Disposition": "inline"})
                return self.senden(404, b"", "text/plain")
            m = re.fullmatch(r"/api/zahlungen/(\d+)/datei", u.path)
            if m and methode == "GET":
                with verbindung() as con:
                    z = con.execute("SELECT datei FROM zahlungen WHERE id=?", (int(m.group(1)),)).fetchone()
                pfad = z["datei"] if z else ""
                if not pfad or not os.path.isfile(pfad):
                    return self.senden(404, "Keine Rechnungsdatei hinterlegt.".encode("utf-8"), "text/plain; charset=utf-8")
                typ = "application/pdf" if pfad.lower().endswith(".pdf") else "application/xml"
                with open(pfad, "rb") as f:
                    return self.senden(200, f.read(), typ, {"Content-Disposition": f"inline; filename*=UTF-8''{quote(os.path.basename(pfad))}"})
            m = re.fullmatch(r"/api/service/datei/([A-Za-z0-9_.\-]+)", u.path)
            if m and methode == "GET":
                pfad = os.path.join(BACKUP_PFAD, m.group(1))
                if not os.path.isfile(pfad):
                    return self.senden(404, "Sicherung nicht gefunden".encode("utf-8"), "text/plain; charset=utf-8")
                name = m.group(1)
                if tresor.aktiv(DATEN) and not name.endswith(tresor.ENDUNG):
                    # mit Sicherungskennwort: die heruntergeladene Kopie (z. B. für den USB-Stick) ist verschlüsselt
                    s = tresor.laden(DATEN)
                    if not s:
                        return self.senden(409, "Der Schlüssel des Sicherungskennworts ist auf diesem PC nicht lesbar. Bitte das Kennwort neu setzen.".encode("utf-8"), "text/plain; charset=utf-8")
                    tmp = os.path.join(DATEN, "tmp")
                    os.makedirs(tmp, exist_ok=True)
                    ziel = os.path.join(tmp, f"dl-{secrets.token_hex(6)}{tresor.ENDUNG}")
                    try:
                        tresor.verschluesseln(pfad, ziel, s[0], s[1])
                        with open(ziel, "rb") as f:
                            inhalt = f.read()
                    finally:
                        if os.path.exists(ziel):
                            os.remove(ziel)
                    return self.senden(200, inhalt, "application/octet-stream", {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name + tresor.ENDUNG)}"})
                with open(pfad, "rb") as f:
                    return self.senden(200, f.read(), "application/octet-stream", {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
            if u.path == "/api/unterschrift":
                pfad = os.path.join(DATEN, UNTERSCHRIFT)
                if not os.path.exists(pfad):
                    return self.senden(404, b"", "text/plain")
                with open(pfad, "rb") as f:
                    return self.senden(200, f.read(), "image/png", {"Cache-Control": "no-cache"})
            if u.path == "/api/logo":
                for n, typ in (("logo.png", "image/png"), ("logo.jpg", "image/jpeg")):
                    if os.path.exists(os.path.join(DATEN, n)):
                        with open(os.path.join(DATEN, n), "rb") as f:
                            return self.senden(200, f.read(), typ)
                return self.senden(404, b"", "text/plain")
            if not u.path.startswith("/api/"):
                return self.statisch(u.path)
            teile = [t for t in u.path[5:].split("/") if t]
            if methode not in ("POST", "PUT"):
                benutzer.pruefen(methode, teile, q)
            if methode == "GET" and len(teile) == 3 and teile[0] == "anhaenge" and teile[2] == "datei":
                return self.anhang(int(teile[1]))
            if methode == "GET" and len(teile) == 3 and teile[0] == "arbeitsschutz" and teile[1] == "datei" and teile[2].isdigit():
                return self.as_datei(int(teile[2]))
            if methode == "GET" and len(teile) == 3 and teile[0] == "auftraege" and teile[2] == "datei":
                return self.projektdatei(int(teile[1]), q.get("pfad", ""))
            daten = None
            if methode in ("POST", "PUT"):
                n = int(self.headers.get("Content-Length") or 0)
                if n > MAX_ANFRAGE:
                    raise ApiFehler(f"Die Datei bzw. Anfrage ist zu groß (höchstens {MAX_ANFRAGE // 1048576} MB).", 413)
                daten = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
                if not isinstance(daten, dict):
                    raise ApiFehler("Die Anfrage hat nicht den erwarteten Aufbau.")
                benutzer.pruefen(methode, teile, q, daten)
            if teile and teile[0] == "benutzer":
                with verbindung() as con:
                    erg = benutzer.api(con, methode, teile, q, daten, self.token)
                    con.commit()
                return self.json(erg)
            erg = api(methode, teile, q, daten)
            rechte = benutzer.aktuelle_rechte()
            if rechte and not rechte["inhaber"]:
                if teile[0] == "einstellungen" and methode == "GET" and isinstance(erg, dict) and rechte["bereiche"].get("auftraege", 0) < 1 or \
                        teile[0] == "einstellungen" and methode == "GET" and isinstance(erg, dict) and rechte.get("auftrag_reiter") == "werkstatt":
                    # Werkstatt und Mitarbeiter: nur die Auswahllisten und Schalter, die ihre Seiten brauchen
                    erg = {k: v for k, v in erg.items() if k in EINSTELLUNGEN_WERKSTATT}
                elif teile[0] == "einstellungen" and methode == "GET" and not benutzer.darf("einstellungen", 1):
                    erg = {k: v for k, v in erg.items() if not any(w in k.lower() for w in ("mail", "smtp", "iban", "bic", "bank", "caldav", "kalender_", "glaeubiger", "pfad", "ordner", "konten", "sicherung", "zaehler", "sepa", "mahn", "_netz", "netzwerk"))} if isinstance(erg, dict) else erg
                if not rechte["preise"]:
                    erg = benutzer.preise_entfernen(erg)
                erg = sicht_einschraenken(teile, methode, erg, rechte)
                if teile[0] in ("zahlungen", "lieferanten") and methode == "GET" and isinstance(erg, list) and not benutzer.darf("personal", 1):
                    with verbindung() as con:
                        lohn_ids = {x[0] for x in con.execute("SELECT id FROM lieferanten WHERE gruppe='Mitarbeiter'")}
                    erg = [x for x in erg if (x.get("lieferant_id") if teile[0] == "zahlungen" else x.get("id")) not in lohn_ids]
            self.json(erg)
        except ApiFehler as f:
            self.json({"fehler": str(f)}, f.code)
        except benutzer.Fehler as f:
            self.json({"fehler": str(f)}, f.code)
        except personal.Fehler as f:
            self.json({"fehler": str(f)}, f.code)
        except (mailversand.MailFehler, erechnung.ERechnungFehler) as f:
            self.json({"fehler": str(f)}, 400)
        except sqlite3.IntegrityError as f:
            self.json({"fehler": f"Datenbankkonflikt: {f}"}, 409)
        except ValueError as f:
            # falsch geschriebenes Datum oder eine Zahl, die keine ist: Eingabefehler, kein Programmfehler
            if any(x in str(f) for x in ("isoformat", "must be in", "out of range for month", "invalid literal for int", "could not convert string to float", "padding", "ASCII", "base64")):
                self.json({"fehler": "Die Eingabe ist ungültig (Datum oder Zahl bitte prüfen)."}, 400)
            else:
                traceback.print_exc()
                self.json({"fehler": f"Interner Fehler: {f}"}, 500)
        except (TypeError, AttributeError, sqlite3.InterfaceError, sqlite3.ProgrammingError, binascii.Error, OverflowError):
            # Fast immer ein Feld mit falschem Inhalt (Liste statt Text, Text statt Zahl): als Eingabefehler melden, im Log festhalten
            traceback.print_exc()
            self.json({"fehler": "Die Eingabe konnte nicht verarbeitet werden (ein Feld hat einen unerwarteten Inhalt)."}, 400)
        except Exception as f:  # noqa
            if type(f).__name__ == "Fehler" and isinstance(getattr(f, "code", None), int):
                self.json({"fehler": str(f)}, f.code)   # fachliche Meldung eines Programmteils (z. B. „Rapport nicht gefunden“)
                return
            traceback.print_exc()
            self.json({"fehler": f"Interner Fehler: {f}"}, 500)

    def anhang(self, aid):
        with verbindung() as con:
            h = con.execute("SELECT * FROM anhaenge WHERE id=?", (aid,)).fetchone()
        if not h or not os.path.exists(h["pfad"]):
            return self.json({"fehler": "Datei nicht gefunden"}, 404)
        with open(h["pfad"], "rb") as f:
            inhalt = f.read()
        typ = mimetypes.guess_type(h["dateiname"])[0] or "application/octet-stream"
        self.senden(200, inhalt, typ, {"Content-Disposition": f"inline; filename*=UTF-8''{quote(h['dateiname'])}"})

    def as_datei(self, fid):
        with verbindung() as con:
            try:
                r, pfad = arbeitsschutz.datei_pfad(con, DATEN, fid)
            except arbeitsschutz.Fehler as f:
                return self.json({"fehler": str(f)}, f.code)
            # Nachweise zu Personen (z. B. Ersthelfer-Bescheinigung) nur mit Arbeitsschutzrecht, Datenblätter für alle
            if r["qualifikation_id"] and not benutzer.darf("arbeitsschutz", 1):
                return self.json({"fehler": "Dafür fehlt die Berechtigung."}, 403)
        with open(pfad, "rb") as f:
            inhalt = f.read()
        typ = mimetypes.guess_type(r["dateiname"])[0] or "application/octet-stream"
        self.senden(200, inhalt, typ, {"Content-Disposition": f"inline; filename*=UTF-8''{quote(r['dateiname'])}"})

    def projektdatei(self, aid, rel):
        with verbindung() as con:
            ordner, hinweis = sicht_ordner(con, aid, anlegen=False)
        if not ordner:
            return self.json({"fehler": hinweis}, 404)
        voll = im_ordner(ordner, rel)
        if not os.path.isfile(voll):
            return self.json({"fehler": "Datei nicht gefunden"}, 404)
        with open(voll, "rb") as f:
            inhalt = f.read()
        name = os.path.basename(voll)
        typ = mimetypes.guess_type(name)[0] or "application/octet-stream"
        self.senden(200, inhalt, typ, {"Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}"})

    def statisch(self, pfad):
        if pfad in ("", "/"):
            pfad = "/index.html"
        if pfad in ("/stempel", "/stempel/"):
            pfad = "/stempel.html"
        if pfad in ("/scan", "/scan/"):
            pfad = "/scan.html"
        if pfad.startswith("/hilfe/") and pfad[7:] in EIGENE_DOKUMENTE and os.path.isfile(os.path.join(DATEN, "dokumente", pfad[7:])):
            voll = os.path.join(DATEN, "dokumente", pfad[7:])   # betriebseigene Fassung statt neutraler Vorlage
            with open(voll, "rb") as f:
                return self.senden(200, f.read(), "text/html; charset=utf-8")
        voll = os.path.normpath(os.path.join(STATIC, pfad.lstrip("/")))
        if not voll.startswith(os.path.join(STATIC, "")) or not os.path.isfile(voll):
            return self.senden(404, b"Nicht gefunden", "text/plain; charset=utf-8")
        with open(voll, "rb") as f:
            inhalt = f.read()
        typ = mimetypes.guess_type(voll)[0] or "application/octet-stream"
        if typ.startswith("text/") or typ.endswith("javascript"):
            typ += "; charset=utf-8"
        self.senden(200, inhalt, typ)


def im_hintergrund_neu_starten():
    """Unter Windows ohne Konsolenfenster weiterlaufen: pythonw.exe startet das Programm neu,
    dieses (sichtbare) Fenster schließt sich danach. Mit --konsole bleibt das Fenster."""
    if os.name != "nt" or "--konsole" in sys.argv or "--hintergrund" in sys.argv:
        return False
    if os.path.basename(sys.executable).lower() == "pythonw.exe":
        return False
    # Nie über die App-Aliase in ...\WindowsApps starten: so gestartete Programme sind abgeschirmt
    # und nehmen keine Verbindungen von Handys im WLAN an.
    kandidaten = []
    for exe in (getattr(sys, "_base_executable", None), sys.executable):
        if exe:
            for x in (exe, os.path.realpath(exe)):
                kandidaten.append(os.path.join(os.path.dirname(x), "pythonw.exe"))
    import glob
    kandidaten += sorted(glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Python", "pythoncore-*", "pythonw.exe")), reverse=True)
    kandidaten += sorted(glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python3*", "pythonw.exe")), reverse=True)
    kandidaten = [k for k in kandidaten if "windowsapps" not in k.lower()]
    pyw = next((k for k in kandidaten if os.path.isfile(k)), None) or shutil.which("pythonw") or shutil.which("pyw")
    if not pyw:
        print("Hinweis: pythonw.exe nicht gefunden, das Programm läuft mit Fenster.")
        return False
    try:
        subprocess.Popen([pyw, os.path.abspath(__file__), "--hintergrund"] + sys.argv[1:], cwd=BASIS,
                         creationflags=0x00000008 | 0x00000200, close_fds=True)  # DETACHED_PROCESS | NEW_PROCESS_GROUP
        return True
    except OSError as f:
        print("Hintergrundstart nicht möglich:", f)
        return False


def _kostenstellen(con):
    kv = einstellungen(con).get("kalk_vorgaben") or {}
    return [k.get("kst") for k in (kv.get("kostenstellen") or KALK_VORGABEN["kostenstellen"])]


def leitstand_status_fuer(e, schritt, index):
    """Auftragsstatus, der zu einem Leitstand-Schritt gehört ('' = Status nicht ändern). Einstellbar je Spalte."""
    karte = e.get("leitstand_status_map") or {}
    if schritt in karte:
        return karte[schritt] or ""
    s = schritt.lower()
    if index == 0 or s.startswith("fertig") or "abgeschlossen" in s:
        return ""
    if "montage" in s or "kunde" in s or "nacharbeit" in s or "einbau" in s:
        return "Montage"
    return "Fertigung"


def leitstand_daten(con):
    e = einstellungen(con)
    schritte = [x for x in (e.get("leitstand_schritte") or STANDARD_EINSTELLUNGEN["leitstand_schritte"]) if x]
    status = e.get("leitstand_status") or STANDARD_EINSTELLUNGEN["leitstand_status"]
    karten = []
    ph = ",".join("?" * len(status)) or "''"
    for r in con.execute(f"SELECT a.*, k.kurzname FROM auftraege a LEFT JOIN kunden k ON k.id=a.kunde_id WHERE a.status IN ({ph}) "
                         "ORDER BY a.leitstand_sort, a.nummer", list(status)):
        a = dict(r)
        try:
            erg = auftrag_rechnen(con, a["id"])
            soll_h = round(erg["soll"].get("stunden", 0), 1)
            npos = len(erg.get("positionen", []))
        except Exception:  # noqa: BLE001
            soll_h, npos = 0, 0
        ist_h = con.execute("SELECT IFNULL(SUM(stunden),0) FROM stunden WHERE auftrag_id=?", (a["id"],)).fetchone()[0]
        termin = con.execute("SELECT typ, von, bis FROM termine WHERE auftrag_id=? AND IFNULL(erledigt,0)=0 AND bis>=? ORDER BY von LIMIT 1",
                             (a["id"], date.today().isoformat())).fetchone()
        mb = con.execute("SELECT COUNT(*) FROM montageberichte WHERE auftrag_id=? AND status='unterschrieben'", (a["id"],)).fetchone()[0]
        karten.append({"id": a["id"], "nummer": a["nummer"], "bezeichnung": a["bezeichnung"], "kunde": a.get("kurzname") or "",
                       "status": a["status"], "schritt": a.get("leitstand") if a.get("leitstand") in schritte else schritte[0],
                       "sort": a.get("leitstand_sort") or 0, "plan_von": a.get("plan_von") or "", "plan_bis": a.get("plan_bis") or "",
                       "lieferung": a.get("lieferung") or "", "fertigung": a.get("fertigung") or "",
                       "soll_h": soll_h, "ist_h": round(ist_h, 1), "positionen": npos, "montageberichte": mb,
                       "termin": dict(termin) if termin else None})
    return {"schritte": schritte, "status": status, "karten": karten,
            "status_je_schritt": {x: leitstand_status_fuer(e, x, i) for i, x in enumerate(schritte)}}


def leitstand_setzen(con, aid, d):
    e = einstellungen(con)
    schritte = [x for x in (e.get("leitstand_schritte") or STANDARD_EINSTELLUNGEN["leitstand_schritte"]) if x]
    schritt = d.get("schritt")
    if schritt not in schritte:
        raise ApiFehler("Unbekannter Arbeitsschritt")
    a = auftrag_laden(con, aid)
    werte = {"leitstand": schritt, "leitstand_sort": fl(d.get("sort")), "geaendert": jetzt()}
    i = schritte.index(schritt)
    # Auftragsstatus mitziehen – nur wenn sich die kaufmännische Phase ändert und der Auftrag im Leitstand geführt wird
    stati = e.get("auftragsstatus") or []
    ziel = leitstand_status_fuer(e, schritt, i)
    im_leitstand = a["status"] in (e.get("leitstand_status") or STANDARD_EINSTELLUNGEN["leitstand_status"])
    if ziel and ziel in stati and ziel != a["status"] and im_leitstand:
        werte["status"] = ziel
    if (werte.get("status") or a["status"]) == "Fertigung" and not a.get("fertigung") and i > 0:
        werte["fertigung"] = date.today().isoformat()
    con.execute(f"UPDATE auftraege SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [aid])
    return {"ok": True, "status": werte.get("status", a["status"])}


def etiketten_seite(con, q):
    """Etiketten mit QR-Code: Material (öffnet die Materialseite) oder Reste (öffnet das Restelager)."""
    import segno

    def qr(text):
        buf = io.BytesIO()
        segno.make(text, error="m").save(buf, kind="svg", scale=1, border=0, xmldecl=False, omitsize=True)
        return buf.getvalue().decode()
    host = lokale_ip() if NETZ["aktiv"] else "localhost"
    basis = f"http://{host}:{PORT}/"
    eintraege = []
    if q.get("typ") == "rest":
        ids = set((q.get("ids") or "").split(","))
        for it in reste.uebersicht(con)["reste"]:
            if it.get("id") in ids:
                mm = lambda x: de(fl(x), 0)
                eintraege.append({"titel": it.get("no") or "", "zeilen": [it.get("material") or "", f"{mm(it.get('length'))} × {mm(it.get('width'))} mm · {de(fl(it.get('thickness')), 1)} mm",
                                                                          (it.get("location") or "") + (" · " + it["from"] if it.get("from") else "")],
                                  "qr_text": f"{basis}#/material/reste/{it.get('no')}",
                                  "klein": "Eingelagert " + de_datum((it.get("date") or "")[:10])})
    else:
        ids = [int(x) for x in (q.get("ids") or "").split(",") if x.strip().isdigit()]
        for mid in ids:
            r = con.execute("SELECT m.*, l.kurzname AS lief FROM material m LEFT JOIN lieferanten l ON l.id=m.lieferant_id WHERE m.id=?", (mid,)).fetchone()
            if not r:
                continue
            bez = (r["bezeichnung"] or "").split("\n")
            zeilen = [bez[0]] + ([bez[1]] if len(bez) > 1 and bez[1].strip() else [])
            if r["dicke"]:
                zeilen.append(f"{de(r['dicke'], 1)} mm")
            zeilen.append(" · ".join(x for x in [r["lagerort"] or "", r["lief"] or "", r["bestellnr"] or ""] if x))
            eintraege.append({"titel": r["nummer"], "zeilen": [z for z in zeilen if z], "qr_text": f"{basis}scan#m{mid}",
                              "klein": "Einheit " + (r["einheit"] or "")})
    if not eintraege:
        return "<p>Keine Etiketten ausgewählt.</p>"
    return reste.etiketten_html(eintraege, qr, h, "a4" if q.get("format") == "a4" else "70x74", etikett_mass(einstellungen(con)))


def _zuschnitt_buchen(con, aid, m, menge, text):
    if not con.execute("SELECT 1 FROM auftraege WHERE id=?", (aid,)).fetchone():
        return None
    ak = material.ak_buchen(con, {"auftrag_id": aid, "kostenart": material.KAT_KOSTENART.get(m["kategorie"], "werkstoffe"),
                                  "material_id": m["id"], "menge": menge, "lager_abgang": bool(m.get("lager")), "bemerkung": text})
    return ak["id"]


def _zuschnitt_stornieren(con, ak_id):
    try:
        material.ak_loeschen(con, ak_id)
    except material.Fehler:
        pass


reste.HILFE["lagerbuchung"] = lambda con, mid, menge, text: material.lager_buchen(
    con, {"material_id": mid, "menge": abs(menge), "art": "zugang" if menge > 0 else "abgang", "bemerkung": text})
material.BESTAND_GEAENDERT.append(lambda con, mid: reste.bestand_geaendert(con, mid))
reste.HILFE["abgleich"] = lambda con, alt, neu: reste.buchungen_abgleichen(con, alt, neu,
    lambda aid, m, menge, text: _zuschnitt_buchen(con, aid, m, menge, text), lambda ak: _zuschnitt_stornieren(con, ak))


def montage_mail(con, methode, mid, d):
    """Unterschriebenen Rapport per E-Mail an den Kunden (PDF im Anhang), Eintrag in der Korrespondenz."""
    b = montage.laden(con, mid)
    if b["status"] == "offen":
        raise ApiFehler("Den Rapport erst unterschreiben lassen, dann kann er versendet werden.")
    a = auftrag_laden(con, b["auftrag_id"])
    k = con.execute("SELECT * FROM kunden WHERE id=?", (a["kunde_id"],)).fetchone()
    k = dict(k) if k else {}
    e = einstellungen(con)
    cfg = e.get("mail") or {}
    adr = [k[f"email{i}"] for i in range(1, 5) if k.get(f"email{i}")]
    name = sauber(f"{a['nummer']}_Rapport_{b['datum']}_{mid}") + ".pdf"
    if methode == "GET":
        return {"an": adr[0] if adr else "", "adressen": adr, "betreff": f"Rapport vom {de_datum(b['datum'])} – {a['bezeichnung']}",
                "text": f"{anrede_aufloesen(k)}\n\nim Anhang erhalten Sie den unterschriebenen Rapport vom {de_datum(b['datum'])} "
                        f"für „{a['bezeichnung']}“.\n\nVielen Dank und mit freundlichen Grüßen",
                "anhaenge": [{"id": "rapport", "name": name, "an": True}], "dateien": [],
                "eingerichtet": bool(cfg.get("smtp_server") and cfg.get("passwort")),
                "kopie_an_mich": bool(cfg.get("kopie_an_mich")), "absender": cfg.get("adresse") or ""}
    if methode != "POST":
        raise ApiFehler("Unbekannte Anfrage", 404)
    pfad = b.get("pdf") if b.get("pdf") and os.path.exists(b["pdf"]) else None
    if not pfad:
        info = montage_pdf(con, mid)
        if info.get("fehler"):
            raise ApiFehler("PDF konnte nicht erzeugt werden: " + info["fehler"])
        pfad = info["pfad"]
    anh = []
    if "rapport" in (d.get("anhaenge") or ["rapport"]):
        with open(pfad, "rb") as f:
            anh.append((name, f.read(), "application/pdf"))
    con.commit()
    try:
        r = mailversand.senden(cfg, d.get("an"), d.get("cc"), d.get("betreff") or "", d.get("text") or "", anh, kopie_an_mich=bool(d.get("kopie_an_mich")))
    except mailversand.MailFehler as f:
        raise ApiFehler(str(f))
    korrespondenz_eintragen(con, "mail_aus", kunde_id=a["kunde_id"], auftrag_id=a["id"], betreff=d.get("betreff") or "",
                            text=d.get("text") or "", an=d.get("an") or "", message_id=r.get("message_id"), anhaenge=[x[0] for x in anh])
    return r


def montage_pdf(con, mid):
    """PDF des unterschriebenen Rapports in den Projektordner (Unterordner „Montage“ bzw. Werkstatt) und ins Archiv."""
    b = montage.laden(con, mid)
    a = auftrag_laden(con, b["auftrag_id"])
    con.commit()
    name = sauber(f"{a['nummer']}_Rapport_{b['datum']}_{mid}") + ".pdf"
    archiv = os.path.join(montage.ordner(), name)
    try:
        pdf_url_rendern(f"http://127.0.0.1:{PORT}/papier/montage/{mid}?pdf=1", archiv)
    except ApiFehler as f:
        return {"fehler": str(f)}
    ziel, rel = archiv, None
    ordner, _ = projektordner(con, b["auftrag_id"])
    if ordner:
        e = einstellungen(con)
        ziel_ordner = ordner
        for stichwort in [w for w in [(e.get("pdf_ordner") or {}).get("montage"), "Montage", (e.get("pdf_ordner") or {}).get("werkstatt"), "Werkstatt"] if w]:
            treffer = [n for n in sorted(os.listdir(ordner)) if stichwort.lower() in n.lower() and os.path.isdir(os.path.join(ordner, n))]
            if treffer:
                ziel_ordner = os.path.join(ordner, treffer[0])
                break
        ziel = os.path.join(ziel_ordner, name)
        try:
            shutil.copyfile(archiv, ziel)
            rel = os.path.relpath(ziel, ordner).replace(os.sep, "/")
        except OSError:
            ziel = archiv
    con.execute("UPDATE montageberichte SET pdf=? WHERE id=?", (ziel, mid))
    return {"pfad": ziel, "projekt_rel": rel}


def montage_html(con, mid, pdf=False):
    b = montage.laden(con, mid)
    a = auftrag_laden(con, b["auftrag_id"])
    k = auftrag_kunde(con, b["auftrag_id"])
    e = einstellungen(con)

    def qr(text):
        import segno
        buf = io.BytesIO()
        segno.make(text, error="m").save(buf, kind="svg", scale=1, border=0, xmldecl=False, omitsize=True)
        return buf.getvalue().decode()
    hilfe = {"h": h, "de": lambda z, n=2: de(fl(z), n), "de_datum": de_datum, "qr": qr, "ersteller": e.get("firma_inhaber") or e.get("firma") or ""}
    return werkstatt.rahmen("Rapport", a, k, montage.html_inhalt(con, b, hilfe), hilfe, {}, pdf=pdf)


def projekt_html(con, pid):
    try:
        p = projekte.laden(con, pid)
    except projekte.Fehler as f:
        raise ApiFehler(str(f), f.code)
    e = einstellungen(con)
    inhalt = projekte.html_inhalt(p, h, lambda z, n=2: de(fl(z), n), de_datum)
    titel = f"Projekt-Nachkalkulation {p['nummer']}"
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8"><title>{h(titel)}</title><style>{werkstatt.CSS} table.t th.r{{text-align:right}}</style></head><body>'
            f'<div class="leiste"><b>{h(titel)}</b><span style="flex:1"></span><button onclick="window.print()">Drucken / PDF</button></div><div class="blatt">'
            f'{werkstatt.logo_zeile()}<div class="kopf"><div class="titelblock"><h1>PROJEKT-NACHKALKULATION</h1><div class="k2">Projekt <b>{h(p["nummer"])} {h(p["bezeichnung"])}</b>'
            f'{"<br>Kunde <b>" + h(p.get("kundennr")) + " " + h(p.get("kunde")) + "</b>" if p.get("kunde") else ""}</div></div>'
            f'<div class="rechts"><table><tr><td>Nr.</td><td class="nr">{h(p["nummer"])}</td></tr><tr><td>Aufträge</td><td><b>{len(p["auftraege"])}</b></td></tr>'
            f'<tr><td>Status</td><td>{"laufend" if p["status"] == "aktiv" else h(p["status"])}</td></tr></table></div></div>{inhalt}'
            f'<div class="fuss">{h(e.get("firma_inhaber") or e.get("firma") or "")} · {datetime.now():%d.%m.%Y · %H:%M}</div></div></body></html>')


def bautagebuch_html(con, aid, q):
    a = auftrag_laden(con, aid)
    k = auftrag_kunde(con, aid)
    e = einstellungen(con)

    def qr(text):
        import segno
        buf = io.BytesIO()
        segno.make(text, error="m").save(buf, kind="svg", scale=1, border=0, xmldecl=False, omitsize=True)
        return buf.getvalue().decode()

    def foto_uri(name):
        pf = bautagebuch.foto_pfad(name)
        if not pf:
            return ""
        with open(pf, "rb") as f:
            return f"data:{mimetypes.guess_type(pf)[0] or 'image/jpeg'};base64," + base64.b64encode(f.read()).decode()
    hilfe = {"h": h, "de_datum": de_datum, "de": lambda z, n=2: de(fl(z), n), "qr": qr, "foto_uri": foto_uri, "ersteller": e.get("firma_inhaber") or e.get("firma") or ""}
    eintraege = bautagebuch.liste(con, aid)
    if q.get("von"):
        eintraege = [x for x in eintraege if x["datum"] >= q["von"]]
    if q.get("bis"):
        eintraege = [x for x in eintraege if x["datum"] <= q["bis"]]
    baustelle = " · ".join(x.strip() for x in ((k.get("lieferanschrift") or "") + "\n" + (k.get("lieferort") or "")).split("\n") if x.strip()) \
        or " · ".join(x.strip() for x in ((k.get("anschrift") or "").split("\n") + [f"{k.get('plz') or ''} {k.get('ort') or ''}".strip()]) if x.strip())
    deckblatt = None if q.get("deckblatt") == "0" else {"auftrag": a["bezeichnung"], "nummer": a["nummer"], "kunde": f"{k.get('nummer') or ''} {k.get('kurzname') or ''}".strip(),
                                                          "baustelle": baustelle, "firma": e.get("firma") or ""}
    return werkstatt.rahmen("Bautagebuch", a, k, bautagebuch.html_inhalt(eintraege, hilfe, q.get("fotos") != "0", deckblatt), hilfe, {}, pdf=q.get("pdf") == "1")


bautagebuch.HILFE.update({"daten": DATEN})
korrespondenz.HILFE.update({"daten": DATEN, "einstellungen": lambda con: einstellungen(con), "verbindung": lambda: verbindung(),
                            "rechnung": rechnungspost_mail})


def logo_datenuri():
    """Firmenlogo als data:-URI (für Werkstattpapiere, auch im PDF ohne Anmeldung)."""
    for n, typ in (("logo.png", "image/png"), ("logo.jpg", "image/jpeg")):
        pfad = os.path.join(DATEN, n)
        if os.path.exists(pfad):
            with open(pfad, "rb") as f:
                return f"data:{typ};base64," + base64.b64encode(f.read()).decode()
    return ""


werkstatt.LOGO["datenuri"] = logo_datenuri
werkstatt.LOGO["scan_basis"] = lambda: f"http://{lokale_ip() if NETZ['aktiv'] else 'localhost'}:{PORT}/"


def logo_bytes():
    for n, typ in (("logo.png", "image/png"), ("logo.jpg", "image/jpeg")):
        pfad = os.path.join(DATEN, n)
        if os.path.exists(pfad):
            with open(pfad, "rb") as f:
                return f.read(), typ
    return None


mailversand.LOGO["laden"] = logo_bytes
mailversand.SIGNATUR["laden"] = _signatur_laden
material.PREISREGEL["methode"] = lambda con: einstellungen(con).get("lagerpreis_methode") or "mittel"
projekte.HILFE.update({"soll_ist": lambda con, aid: soll_ist(con, aid), "beleg_umsatz": lambda b: beleg_umsatz(b)})
export.HILFE.update({"daten": DATEN, "basis": BASIS, "version": VERSION, "einstellungen": lambda con: einstellungen(con),
                     "archiv_pdf": lambda con, bid: beleg_pdf(con, bid), "klartext": lambda t: montage.klartext(t, 1000)})
bank.HILFE.update({"daten": DATEN, "prot": lambda *a, **k: prot(*a, **k), "ich_login": lambda: ich_login(),
                   "skr": lambda con: export.datev_cfg(einstellungen(con))["skr"],
                   "op_zahlung_buchen": lambda *a, **k: op_zahlung_buchen(*a, **k), "zahlungseingang_loeschen": lambda *a, **k: zahlungseingang_loeschen(*a, **k)})
liquiditaet.HILFE.update({"einstellungen": lambda con: einstellungen(con), "auftrag_rechnen": lambda con, aid: auftrag_rechnen(con, aid),
                          "beleg_umsatz": lambda b: beleg_umsatz(b)})
monatsbeleg.HILFE.update({"daten": DATEN, "prot": lambda *a, **k: prot(*a, **k), "ich_name": lambda: ich_name()})
arbeitsschutz_web.HILFE.update({"daten": DATEN, "static": STATIC, "prot": lambda *a, **k: prot(*a, **k), "ich_name": lambda: ich_name(), "ich_login": lambda: ich_login(),
                                "auftrag_material_nummern": lambda con, aid: auftrag_material_nummern(con, aid), "einstellungen": lambda con: einstellungen(con)})
testdaten.HILFE.update({"daten": DATEN, "bilder": BILDER, "eingang_pfad": EINGANG_PFAD, "datei_weg": lambda p: _datei_weg(p)})


montage.HILFE.update({"daten": DATEN, "auftrag_laden": lambda con, aid: auftrag_laden(con, aid),
                      "auftrag_kunde": lambda con, aid: auftrag_kunde(con, aid),
                      "auftrag_rechnen": lambda con, aid: auftrag_rechnen(con, aid),
                      "einstellungen": lambda con: einstellungen(con),
                      "kostenstellen": lambda con, aid: [x.get("kst") for x in auftrag_kalk(con, aid).get("kostenstellen", [])],
                      "nach_druck": lambda con, mid: montage_pdf(con, mid)})
personal.HILFE.update({"einstellungen": lambda con: einstellungen(con), "titel_buchbar": lambda con, aid, nr: titel_buchbar(con, aid, nr),
                       "lohnbasis": lambda con, aid: (auftrag_kalk(con, aid) or {}).get("lohnbasis", ""),
                       "zahlungsnummer": lambda con: naechste_zahlungsnummer(con),
                       "kostenstellen": _kostenstellen})


def main():
    if im_hintergrund_neu_starten():
        return
    if sys.stdout is None or sys.stderr is None:
        # ohne Konsolenfenster gestartet (pythonw): Ausgaben in daten/protokoll.txt
        os.makedirs(DATEN, exist_ok=True)
        log = open(os.path.join(DATEN, "protokoll.txt"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
        print(f"\n--- Start {datetime.now():%d.%m.%Y %H:%M} ---")
    datenbank_starten()
    vorlagen_einrichten()
    backup()
    threading.Thread(target=protokoll_vollpruefung, daemon=True).start()
    threading.Thread(target=sicherungs_waechter, daemon=True).start()
    threading.Thread(target=projekt_waechter, daemon=True).start()
    threading.Thread(target=zwischenspeicher_vorwaermen, daemon=True).start()
    autostart_nachziehen()
    try:
        netz = einstellungen_roh("netzwerk", False) is True
        NETZ["aktiv"] = netz
        server = BueroServer(("0.0.0.0" if netz else "127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Port {PORT} ist belegt – läuft das Programm schon? Adresse: {pc_adresse(netz)}")
        fremd = laufendes_programm_fremd()
        if fremd:
            print(fremd)
            meldung_fenster(fremd)
            return
        if "--kein-browser" not in sys.argv:
            app_fenster(pc_adresse(netz))
        return
    https_starten()
    url = pc_adresse(netz)   # alle Fenster am PC mit derselben Adresse
    print(f"Jahresring (Version {VERSION}) läuft auf {url}")
    print(f"Daten liegen in: {DATEN}")
    if netz:
        print(f"Im Netzwerk erreichbar: http://{lokale_ip()}:{PORT}  (Handy-Stempeluhr: http://{lokale_ip()}:{PORT}/stempel)")
    print("Beenden: Symbol unten rechts in der Taskleiste (Rechtsklick > Beenden) oder Ein/Aus-Knopf im Programm.")
    korrespondenz.hintergrund_starten()
    if "--kein-browser" not in sys.argv:
        threading.Timer(0.8, lambda: app_fenster(url)).start()
    if os.name == "nt" and "--konsole" not in sys.argv:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            symbol_starten(url)
            return
        except Exception as f:  # noqa: BLE001
            print("Taskleistensymbol nicht verfügbar:", f)
            threading.Event().wait()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def symbol_starten(url):
    """Symbol unten rechts im Infobereich (unter dem ^-Pfeil) mit Menü."""
    import tray

    def zeigen(pfad):
        if os.path.exists(pfad):
            os.startfile(pfad)

    tray.starten(
        f"Jahresring {VERSION}",
        os.path.join(STATIC, "jahresring.ico"),
        [("Jahresring öffnen", lambda: app_fenster(url)),
         ("Datenordner öffnen", lambda: zeigen(DATEN)),
         ("Protokoll anzeigen", lambda: zeigen(os.path.join(DATEN, "protokoll.txt"))),
         None,
         ("Beenden", tray.beenden)],
        beim_beenden=lambda: os._exit(0),
        linksklick=lambda: app_fenster(url),
        info=("Jahresring läuft", "Das Programm läuft im Hintergrund. Öffnen und Beenden über dieses Symbol unten rechts."),
    )


if __name__ == "__main__":
    main()
