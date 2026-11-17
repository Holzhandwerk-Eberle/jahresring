## Umsetzung in Version 2026.11.01-149

Stand 17.11.2026: Von den 51 Befunden sind 39 umgesetzt und geprüft, fünf teilweise umgesetzt und fünf bewusst offen; zwei brauchten keine Änderung. Die acht Abweichungen in der Gestaltung sind behoben. Die Version ist ausgeliefert; der Bericht darüber bleibt als Stand der Prüfung von Version 148 stehen.

| Bereich | Umgesetzt | Teilweise | Offen oder ohne Änderung |
| --- | --- | --- | --- |
| Cybersicherheit | S1 bis S9 | – | – |
| Datenschutz | D1 bis D5 | – | – |
| GoBD | G1 bis G5 | – | – |
| Funktionalität | F1, F2 | – | F3 offen |
| Einheitliche Bedienung | U1 bis U8 | – | – |
| Geschwindigkeit | P2, P3 | P1 | P4 ohne Änderung |
| Zukunftsfähigkeit | Z3, Z9 | Z2, Z4, Z6 | Z1, Z5, Z7, Z8 offen |
| Kalkulation und Rechnen | K1 bis K4 | – | – |
| Einstellungen | E2 | E3 | E1 ohne Änderung |
| Preis- und Kontoauszugsimport | I1 bis I5 | – | – |
| Mitarbeiter und Berechtigungen | M2 bis M5 (M1 verweist auf S1 bis S3) | – | – |

Was nicht oder nur zum Teil umgesetzt ist, und warum:

| Nr. | Stand | Begründung und nächster Schritt |
| --- | --- | --- |
| P1 | teilweise | Kunden- und Auftragsliste laden nur noch die angezeigten Spalten (im Großbestand 12,3 → 1,8 MB und 12,0 → 6,7 MB). Belege, offene Posten und Zahlungen bleiben: Die Belegliste ist schon schlank, „alle“ ist dort eine bewusste Auswahl, und im Netz wird gepackt übertragen. |
| Z2 | teilweise | Anonymisieren und Änderungsprotokoll liegen in eigenen Modulen (datenschutz.py, nachweis.py). app.py bleibt groß; weitere Auslagerung folgt schrittweise mit künftigen Änderungen. |
| Z4 | teilweise | start.bat nimmt nur Python ab 3.12 und lädt bei Bedarf 3.13.17. pdf.js bleibt bei 3.11.174: Neuere Fassungen laden anders und brauchen eine Probe auf Handy und in Edge. Python 3.13 bekommt seit Oktober 2026 keine Installationsprogramme für Windows mehr; der Umstieg auf 3.14 ist für 2027 vorzusehen. |
| Z6 | teilweise | Die Aufbewahrungsfrist ist einstellbar. Ein Umsatzsteuersatz mit Stichtag fehlt weiter: Der Satz steht je Kunde und wird im Beleg eingefroren; ein Stichtagsmodell lohnt erst bei einer angekündigten Satzänderung. |
| E3 | teilweise | Einstellbar sind jetzt Übertrag, Aufbewahrungsfrist und Dauer der Anmeldung. Die PIN-Länge ist fest (sechs Stellen), der Steuersatz mit Stichtag fehlt (siehe Z6). |
| F3 | offen | Die Ursache des PDF-Ausfalls am Büro-PC ließ sich nicht nachstellen. Neu ist der Ersatz: Fällt das PDF aus, druckt „Drucken“ die Bildschirmfassung und sagt das. |
| Z1 | offen | XRechnung 4.0 liegt nur als Vorabversion vor. Umstellung nach der endgültigen Fassung (erwartet Frühjahr 2027); die Prüfroutine führt den Termin. |
| Z5 | offen | Eine Signatur des Installationsprogramms braucht ein gekauftes Zertifikat; sinnvoll erst bei Weitergabe an weitere Betriebe. |
| Z7 | offen | Weitere Steuerfälle (Kleinunternehmer, EU-Lieferung, Ausfuhr) nur bei Bedarf; für den eigenen Betrieb ohne Belang. |
| Z8 | offen | Das Gegenlesen der eigenen Verschlüsselung kann nur ein fachkundiger Dritter leisten; nötig vor einer Weitergabe. |
| P4 | ohne Änderung | Kein Handlungsbedarf bei zwei bis fünf Benutzern. |
| E1 | ohne Änderung | Der Befund war unzutreffend (siehe unten). |

Drei Aussagen des Berichts haben sich bei der Umsetzung als ungenau erwiesen:

1. E1: Die Einstellung „Letzte Seite unten bündig“ gibt es unter Einstellungen › Belege & Briefbogen. Handbuch und Programm stimmten überein.
2. M5: Den Hinweis bei mehr als zehn Stunden Arbeitszeit gab es schon. Neu sind die Hinweise zu Ruhezeit, Mindestlohn und Minijob-Grenze.
3. G2: Einen Umsatzsteuersatz in den Einstellungen gibt es nicht. Der Satz steht beim Kunden; seine Änderung wird dort jetzt protokolliert.

Abweichend von der empfohlenen Abhilfe gelöst sind zwei Punkte. Bei G1 bekommt ein geändertes Angebot keine neue Nummer; stattdessen bleibt jede versandte Fassung als eigene Datei mit Prüfsumme erhalten. Bei P2 merkt sich das Programm keine Jahresstände; ein passender Index bringt die Mitarbeiterübersicht im Großbestand von 1,4 auf 0,19 Sekunden. Beim Anonymisieren (D1) bleiben Postleitzahl und Ort des Kunden für die Auswertung nach Gebieten stehen.

Geprüft wurde mit neun neuen Prüfskripten, die jetzt vor jedem Bau mitlaufen, darunter der Druckweg im echten Browser. Die Gesamtprüfung in sechs Teilen zeigt gegenüber Version 148 keinen Rückschritt. Nicht geprüft werden konnte weiterhin alles, was Windows braucht.

Am Büro-PC sollte deshalb einmal geprüft werden:

1. Ein mehrseitiger Beleg mit Briefbogen über „Drucken“ in Edge: Briefkopf, Seitenzahlen und Übertrag stehen auf den richtigen Seiten.
2. Der Programmstart nach dem Update, weil start.bat geändert ist.
3. Handy-Freigabe.bat am neuen PC: Netzwerkprofil „Private“, Adresse fürs Handy.
4. Die Aufbewahrungsfrist mit der Steuerberatung abstimmen und unter Einstellungen › Kunden & Aufträge eintragen.
5. In Verfahrens- und Datenschutz-Dokumentation die neuen gelben Felder zur Frist ausfüllen.
