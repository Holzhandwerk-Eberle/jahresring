# Befunde Prüfung -148 (Arbeitsnotizen, laufend)

## Sicherheit – Lauf 1 (sich1.py)
- Rohrouten: zugferd/xrechnung.xml liefern 400 für alle angemeldeten Rollen (Beleg 2 keine Rechnung?) → mit echter Rechnung als Mitarbeiter nachprüfen.
- /api/vorlage/brief-1.svg für alle Rollen lesbar (harmlos, Briefbogen).
- GET einstellungen als Rolle mitarbeiter 200 → Inhalt prüfen (Bankdaten? Mail?).
- eigen-Benutzer mit Einstellungen=2: kann keinen Inhaber anlegen, keine Rechte vergeben, die er nicht hat (403), Inhaber-Passwort nicht setzen. OFFEN: vordefinierte Rolle buero vergeben? eigene Rechte ändern (Liste kam leer)?
- Sitzungen enden bei Passwortwechsel und Sperre. OK.
- Kopfzeilen OK (CSP, nosniff, frame, referrer, no-store). Keine Permissions-Policy (gering).
- Feldlängen unbegrenzt: Kunde mit 200.000 Zeichen im Kurznamen wird angenommen.
- Herkunftsprüfung: fremde Origin 403, fremder Host 403. ABER Origin "null" wird angenommen, Content-Type wird nicht geprüft (text/plain geht). Cookie SameSite=Strict schützt; Härtung empfohlen.

## Sicherheit – bestätigt (sich2–sich6)
- S1 HOCH: Kontoübernahme. Benutzer mit eigenen Rechten "Personal=2" ändert die Mailadresse des Mitarbeiters, mit dem das Inhaber-Konto verknüpft ist (Inhaber ohne eigene Mailadresse) → "Passwort vergessen" schickt Code an diese Adresse → Passwort des Inhabers gesetzt, Anmeldung als Inhaber (nachgestellt). Gilt genauso für jedes andere verknüpfte Konto. Hinweis-Mail "Passwort geändert" geht ebenfalls an die gefälschte Adresse. benutzer.reset_adresse.
- S2 MITTEL: /api/belege/<id>/zugferd.xml (und xrechnung.xml) ohne Rechteregel in roh_recht: Rollen Mitarbeiter und Werkstatt (403 auf den Beleg selbst) erhalten 200 mit Kunde, Positionen, Beträgen; IDs fortlaufend.
- S3 MITTEL: Rolle Werkstatt ("ohne Preise") sieht Beträge: /papier/<aid>/kosten (Selbstkosten, W&G, Netto), /papier/<aid>/sollist, /liste/werkzeuge (Preis netto, Anschaffungswerte), /liste/lager (Preis je Einheit, Wert, Lagerwert). API /api/material filtert Preise korrekt.
- S4 GERING-MITTEL: nicht endliche Zahlen. PUT positionen {"einzelpreis": 1e999} wird gespeichert (inf); danach liefern /api/auftraege/<id>/positionen und /api/start ungültiges JSON ("netto": Infinity) → Startseite lädt für alle nicht mehr (nur per gezielter Anfrage, nicht über die Oberfläche).
- S5 GERING: keine Zeitbegrenzung für stumme HTTP-Verbindungen: 400 offene Verbindungen = 400 Threads, nach 40 s alle noch offen (https-Zugang hat 30 s). Im Netzbetrieb Lahmlegen möglich.
- S6 GERING: xlsx-Importe (Preise, Kunden) ohne Größengrenze beim Entpacken: 0,9 MB → 300 MB → Arbeitsspeicher 342 → 1178 MB. (ZIP mit Preislisten und Kontoauszüge haben Grenzen; XML-DTD im Kontoauszug wird sauber abgelehnt.)
- S7 GERING: angemeldeter Benutzer ohne Rechte (Mitarbeiter-PIN ab 4 Zeichen) kann 300-MB-Anfragen schicken; gelesen wird vor der Rechteprüfung.
- S8 GERING: Origin "null" wird angenommen, Content-Type nicht geprüft (SameSite=Strict schützt).
- S9 GERING: Kalenderadresse nimmt file:// und interne Adressen (nur Inhaber); Antwort ohne Größengrenze.
- S10 GERING: Code im Betreff der Reset-Mail; PBKDF2 200.000 Runden (Empfehlung OWASP 600.000); Mitarbeiter-PIN 4 Zeichen, Sitzung 120 Tage.
- S11 GERING: Fehlertexte: überlanger Dateiname → 500 mit Serverpfad; CRLF im Betreff → 500; ungültige Unicode-Zeichen → 500 bzw. Verbindung ohne Antwort geschlossen; Feldlängen unbegrenzt (200.000 Zeichen im Kurznamen).
- OK: SQL über Feldnamen/Typen (41 Ressourcen × 11 Varianten) keine Lücke; Pfadangaben alle 404; Uploads HTML/SVG/EXE nur als Download mit CSP sandbox; Mail-Kopfzeilen nicht einschleusbar; Sitzung endet bei Passwortwechsel/Sperre; eigen-Rolle bekommt nie Einstellungen; CA mit Name Constraints, Schlüssel DPAPI, nicht in Sicherung; Sicherungsverschlüsselung scrypt + SHAKE-256-Strom + HMAC (Eigenbau aus Standardbausteinen); Prüfwerkzeug-Installation mit festen Versionen und Prüfsummen; Update-Abfrage nur https, installiert nichts.
- xlsx_lesen: Zellen ohne r-Attribut → IndexError → HTTP 500 "list assignment index out of range" (Import-Robustheit).

## Datenschutz / Mitarbeiter (dsch1–3)
- D1 MITTEL: Stempeluhr vertraut der Uhrzeit des Geräts: Rolle Mitarbeiter kann per Anfrage Beginn 05:00 vor 6 Tagen und Ende 19:30 stempeln (14,5 h), sogar Zeiten im Jahr 2019; Eintrag erscheint mit Quelle "stempel" wie live gestempelt, kein Hinweis fürs Büro (stempel_ereignisse speichert Eingangszeit, wird aber nirgends ausgewertet). Kein Monatsabschluss; unterschriebener Monatsbeleg zeigt spätere Änderung an (geaendert), verhindert sie nicht. Keine Warnung >10 h, Ruhezeit; Pausenhinweis 6/9 h vorhanden. Kein Mindestlohn-/Minijob-Grenzwert.
- OK: Kalender zeigt Kollegen nur "abwesend" (kein Grund, keine Notiz) für Werkstatt/Büro; Mitarbeiter-Rolle kein Kalender. Lohn/Stammdaten/Zeiten anderer: 403 für Büro/Werkstatt/Mitarbeiter. Verbandbuch nur Inhaber lesbar, Eintragen für alle.
- D2 HINWEIS: Rolle Büro (Arbeitsschutz=2) liest arbeitsmedizinische Vorsorge (Art, Datum, Arzt) und Expositionsverzeichnis aller Mitarbeiter; Werkstatt nicht.
- D3 MITTEL: Anonymisieren lässt Personenbezug stehen: belege.einleitung ("Sehr geehrter Herr …"), belege.schluss, belege.betreff, belege.daten (Positionstexte, Bezeichnung), auftraege.bezeichnung/bemerkungen, positionen.text, termine.titel/notiz, briefe.betreff, zahlungseingaenge.bemerkung, kunden.ort, bank_umsaetze.name/zweck + Kontoauszugsdatei, protokoll (Kurzname; unveränderbar), Vorschau-PDFs in daten/tmp (bis 3 Tage). Entfernt: Name, Anschrift, Telefon, Mail, IBAN, Notizen, Brieftext, Anhänge, Wiedervorlagen, Unterschrift, Archiv-PDF.
- D4 MITTEL (Zusammenspiel): Nach dem Anonymisieren meldet die Belegprüfung dauerhaft "Archiv-PDF fehlt" für die Rechnungen des Kunden (auch nach erneutem PDF-Abruf).
- D5 HINWEIS: Frist einheitlich 10 Jahre für Rechnungen ("sicherheitshalber"); gesetzlich seit 2025 8 Jahre für Buchungsbelege. Anonymisieren vor Fristende sauber gesperrt (400).
- Mitarbeiter-Stammdaten: keine Steuer-ID/SV-Nummer/Konfession gespeichert (Datensparsamkeit).

## GoBD (gobd1–3)
- OK: Festgeschriebene Rechnung: alle 8 Änderungsversuche + Löschen abgelehnt; spätere Änderung an Auftragsposition/Kunde wirkt nicht auf die Rechnung; Eingriff in DB (Brutto) erkannt, verändertes Archiv-PDF erkannt, Protokoll per DB-Trigger gegen UPDATE/DELETE gesperrt, nach Entfernen der Trigger erkennt Hash-Kette Änderung, Abschneiden wird über Journaldatei erkannt. Ungewöhnliches Rechnungsdatum (Vorjahr, Zukunft) → Rückfrage 409. Zahlungseingang löschen wird protokolliert (Art zahlungseingang_geloescht).
- G1 MITTEL: Versandte Angebote/Auftragsbestätigungen nicht festgehalten: nach Mailversand (800 €) geändert (650 €), erneut unter derselben Nummer 2026-0011-A01 versandt → Archiv-PDF überschrieben, erste Fassung weg (Schriftverkehr nennt nur Dateinamen, keine .eml). Versandtes Angebot und versandte AB lassen sich löschen (Protokoll "beleg_geloescht", Datei bleibt liegen, Datensatz weg). Auftrag selbst danach nicht löschbar (gut).
- G2 MITTEL: Stammdaten- und Einstellungsänderungen ohne Protokoll: IBAN Lieferant, IBAN Betrieb, USt-Satz (Einstellung und Kunde), Anschrift Kunde → keine Zeile im Protokoll.
- G3 HINWEIS: Zahlart "Bar" buchbar, kein Kassenbuch.
- G4 MITTEL: Benutzer-/Rechteänderungen und Anmeldungen nicht im Protokoll (nur Passwort-Reset). 
- G5 GERING: "PDF ansehen"/Vorschau rendert festgeschriebene Rechnungen jedes Mal neu (/druck/N.pdf → tmp/vorschau-N.pdf) statt das Archiv-Original zu zeigen; Inhalt kommt aus dem eingefrorenen Stand (Bank, IBAN stabil – getestet), Briefbogen/Layout aus dem aktuellen Programm. Mailversand und Projektordner nehmen das Archiv-Original.

## Geschwindigkeit (Großbestand 628 MB: 12.001 Kunden, 24.001 Aufträge, 360.016 Positionen, 72.002 Belege, 450.000 Zeiten, 120.000 Schriftverkehr, 60.000 Termine, 36.000 Zahlungen, 9.000 Material)
- Programmstart 0,7 s (erste Indexanlage einmalig 16 s auf erzeugten Daten). Server-RSS 220 MB.
- Browser: Anmeldung bis Startseite 1,8 s; Kunden 0,46 s (11,7 MB JSON, 32 Zeilen im DOM); Aufträge 0,56 s (11,4 MB); OP/Zahlungen/Lieferanten/Material/Projekte/Leitstand < 0,05 s; Kalender 0,86 s; Personal 1,5 s; Startseite 1,5 s (3,2 MB); Einstellungen 0,9 s; Auftrag öffnen 0,9 s.
- API warm: start 1471 ms; belege (alle) 1296 ms / 24 MB; offeneposten alle 750 ms / 19 MB; zahlungen alle 523 ms / 16 MB; mitarbeiter 1396 ms (kalt 4437 ms: Konten über alle Zeiten); kalender 908 ms; protokoll voll (Belegprüfung 72.000 Belege) 3,0 s; Suche 170–260 ms.
- Schreiben: Position anlegen+bepreisen 8–12 ms auch bei 120 Positionen; Festschreiben 6,2 s bei 120 Positionen (davon praktisch alles PDF-Erzeugung; ohne Browser 0,08 s); PDF 120 Positionen: ohne Übertrag 3,3 s, mit Übertrag 5,7 s; "PDF ansehen" einer festgeschriebenen Rechnung jedes Mal 5,8 s (Neuberechnung).
- Sicherung 9,4 s → 63,7 MB.
- Listen ohne Seitenweise-Laden: Kunden/Aufträge/Belege/OP alle/Zahlungen alle liefern alles in einer Antwort (12–24 MB).

## Kalkulation (rund.py, kalk1.py, zahl_ui2.js)
- K1 MITTEL: Rundung nicht kaufmännisch (round() auf Gleitkommazahlen). USt: bei 0,5 % aller Nettobeträge (jeder zweite Halb-Cent-Fall, z. B. netto 2,50 → USt 0,47 statt 0,48; 29.997,50 → 5.699,52 statt ,53), immer 1 Cent zu niedrig, nie zu hoch (3 Mio. Beträge durchgerechnet, 19 % und 7 %). Gesamtpreis = EP × Menge: bei gebrochenen Mengen 10 % der Zufallsfälle 1 Cent daneben (0,5 × 4.764,83 → 2.382,41 statt ,42; 1,5 × 231,69 → 347,53 statt ,54). Rabatt ebenso. Im echten Beleg nachgestellt.
- K2 MITTEL: Zahleneingabe: "1.500" im Feld Einzelpreis wird als 1,50 € gespeichert (Feld zeigt selbst "1.500,00" an); "2.000.000", "1 500", "1.500,00 €" werden ohne Meldung zu 0,00; Menge "1.000" → 1. (zahlEin in index.html)
- K3 GERING-MITTEL: Bruttoanzeige (Privatkunde): 3 × 8,40 netto → gedruckt 10,00 + 10,00 + 10,00, Gesamtbetrag 29,99 €.
- K4 GERING: Kalkulationswerte als Text ("12,5", "40 €") rechnen still mit 0 € (kalkulation.f); "inf"/"nan" werden angenommen. Über die Oberfläche kommen Zahlen, über Importe/Schnittstelle möglich.
- OK: unabhängige Nachrechnung Zuschlagskalkulation (Werkstoff mit Verschnitt, Beschläge, Kleinmaterial, Material-GK, Lohn, Lohn-GK, W&G, EP, GP) stimmt auf den Cent; vorhandener Kalkulationstest "alles stimmt"; Warnungen bei fehlenden Werkstoffen/Lohngruppen/Kostenstellen vorhanden; § 13b, § 35a vorhanden; Verzugszinsen taggenau/365.
- Basiszins-Vorgabe 1,52 % fest im Code (Einstellung vorhanden) → Stand prüfen.

## Importe (imp1, imp1b, imp2, imp3)
- I1 MITTEL: "Alle sicheren Vorschläge übernehmen" bucht alle Vorschläge aus einem Schnappschuss, ohne nach jeder Buchung neu zu prüfen: Rechnung 2026-0051 (1.190 €) erhielt drei Zahlungen (offen −2.380 €), 2026-0052 zwei. Vorschlag "Betrag und Name passen" gilt als sicher, auch wenn ein anderer Umsatz derselben Datei dieselbe Rechnung per Nummer begleicht (V11: Zweck "Rechnung 2026-00511").
- I2 MITTEL-GERING: Doppelt-Erkennung mit Bankreferenz ohne Datum/Zahler: zwei verschiedene Umsätze (anderer Tag, anderer Zahler) mit Referenz "NONREF" und gleichem Betrag → zweiter als "schon vorhanden" verworfen.
- I3 GERING: keine Vollständigkeitsprüfung: fehlender Auszug (Endsaldo 1.010 → Anfangssaldo 5.000), Summe passt nicht zum Endsaldo, Auszug eines fremden Kontos, Umsatz in USD (als Euro übernommen) – alles ohne Hinweis.
- OK Bank: camt.052/053/054 in .02/.08/.13; gleiche Datei zweimal; gleiche Umsätze ohne Referenz in einer Datei; Tages-/Monatsauszug; vorgemerkte Umsätze ausgelassen; Rückbuchung; Nummern mit Leerzeichen/ohne Bindestrich; Sammelzahlung zweier Rechnungen; Skontoabzug als unsicher; 5.000 Umsätze in 0,3 s; MT940/CSV/PDF klare Absage; DTD abgelehnt.
- I4 GERING: Preisimport: Mac-Zeilenenden (nur CR) und Binärmüll → HTTP 500 (csv-Fehler); xlsx ohne Zellbezug → HTTP 500; UTF-16 ("Unicode-Text" aus Excel) nicht erkannt (Spaltennamen verstümmelt); Preis "1.234"/"1.250" ohne Komma wird als 1,234/1,25 gelesen; "EUR 3,45" → Zeile fällt ohne Hinweis weg (kein Zähler übersprungener Zeilen); negative Preise angenommen.
- OK Preise: cp1252/UTF-8 (mit/ohne BOM), Semikolon/Komma, deutsch/englisch/Schweiz, Exponent, Gleitkommarest, Formelzellen, lange EAN in Exponentialschreibweise, Titelzeile → Zuordnung von Hand, alte .xls/kaputtes ZIP/leer klare Meldung, 120.000 Zeilen in 0,7 s; Datanorm 4/5, ZIP, Rabattgruppen, Preiseinheit (vorhandener Test).
- Eingangsrechnung: CII und UBL, DTD-Prüfung vorhanden.
- D4-Ursache: belege_pruefen überspringt Archivprüfung nur bei daten.kunde.kurzname == "anonymisiert"; kunde_anonymisieren setzt kurzname im Belegstand auf "" → Bedingung greift nie.
- Protokollprüfung 20.055 Einträge 0,44 s (linear, 100.000 ≈ 2,2 s); Journal 8,5 MB je 20.000.

## Funktionalität / Bedienung (funk1, druckweg*, ui_stil)
- F1 HOCH (Funktion): Schaltfläche "Drucken" (Belegansicht → /druck/<id>?drucken=1, Druck über den Browser) liefert mit Briefbogen ein kaputtes Druckbild: einseitiges Angebot → 4 Seiten (Seite 1 Inhalt ohne Briefkopf/Fuß, 10 mm nach unten versetzt; Seite 2 Briefkopf mit überlagertem Schlusstext; Seite 3 leer; Seite 4 AGB). Mehrseitig: Briefkopf der ersten Seite auf Seite 2 über der Tabelle, Folgeseiten ohne Briefbogen, Übertrag passt nicht zum Seiteninhalt (Seite 1 zeigt Übertrag 1.190,00 bei Positionen 1–3 = 714,00). Ursache: Bildschirm-Regeln in briefbogen_html (html{background}, body{width:210mm;margin:10mm auto}, .bg-folge{display:none}, .agb{margin-top}) stehen nicht in @media screen und gelten auch im Druck; seit dem Ausgangsstand -130 so. Nachgestellt mit Chromium 153 (page.pdf = Druckweg des Browsers). Programm-PDF ("PDF ansehen", Mail, Projektordner) ist in Ordnung. Gilt auch für Mahnung/Brief (gleicher Seitenrahmen) – nicht einzeln nachgestellt.
- OK: Übertrag in Schlussrechnung mit zwei Abschlägen (Summen unabhängig nachgerechnet: 41.769,00 − 25.061,40 = 16.707,60) und in Angebot mit Titeln stimmt auf jeder Seite; Bruttoanzeige im Übertrag folgerichtig.
- F2 GERING: Positionen werden am Seitenende geteilt (Position 13: zwei Zeilen unten, zwei oben auf der Folgeseite).
- UI gemessen (118 Seiten, 3.098 Schaltflächen): 2.442 mit 30 px/14 px/Radius 4 px, Farben einheitlich (normal, Haupt, rot). Abweichungen: 12 Schaltflächen mit Symbol vorn 32 px (✉ Rundmail, 🔍 XML prüfen, 🏷 Etiketten); "Hinzufügen" 49 px hoch (Kunde/Lieferant › Anhänge); Löschzeichen ✕ 139 × gegen × 3 × (Kunde › Anhänge, Auftrag › Historie) und Wörter; 67 ✕ ohne Erklärtext (Einstellungen › Kalkulation 60, Kalender 7); "Speichern" 7 × Hauptschaltfläche, 1 × normal; Listen-Symbolknöpfe ib 32 px/Radius 6, aktion 28 px/Radius 5; Felder: Text 30 px, Auswahl 29 px, Datum 32 px, Uhrzeit 26 px; h3 in drei Größen (17/16,38/16 px). Keine Browser-Dialoge (confirm/alert), einheitliche Rückfrage. Layoutprüfung 1400/1100/820 px ohne Fund; XSS-Durchlauf 114 Seiten ohne Fund; 0 JS-Fehler.

## Stand
Bericht fertig im Dokument "Prüfbericht Jahresring 2026.11.01-148" (https://claude.ai/artifact/2wxs1FJxy2K6JRtY2Myqcw), 51 Befunde + 8 UI-Abweichungen; Kennungen im Bericht: S1–S9, D1–D5, G1–G5, F1–F3, U1–U8, P1–P4, Z1–Z9, K1–K4 (K1 = Zahleneingabe, K2 = Rundung), E1–E3, I1–I5, M1–M5. Programm unverändert (-148, a66ffb2). Prüfskripte in /tmp/claude-0/t/audit4 (nicht im Repo: enthalten Nachweise zu noch offenen Lücken).
