p = "/home/claude/eberle-buero/static/hilfe/datenschutz.html"
s = open(p, encoding="utf-8").read()
n = 0
def ers(alt, neu):
    global s, n
    assert s.count(alt) == 1, (s.count(alt), alt[:90])
    s = s.replace(alt, neu); n += 1
def nach(anker, neu):
    ers(anker, anker + neu)

# 2 Überblick
ers("erreichbar am PC und – wenn eingeschaltet – im eigenen WLAN, nicht aus dem Internet.", "erreichbar am PC und – wenn eingeschaltet – im eigenen Netzwerk (Kabel und WLAN des eigenen Routers), nicht aus dem Internet.")
ers("Alle Daten in der Datenbank <i>daten\\buero.db</i> und im Datenordner (Belege, Anhänge, Bilder, E-Mail-Kopien, Unterschriften, Sicherungen).",
    "Alle Daten in der Datenbank <i>daten\\buero.db</i> und im Datenordner (Belege samt den versandten Fassungen, Anhänge, Bilder, E-Mail-Kopien und gesendete E-Mails, Kontoauszüge, Unterschriften, Sicherungen).")
# 3 Verzeichnis
ers("<td>bis zum Ende der Beschäftigung, danach mit der Anonymisierung des Mitarbeiters; nur Benutzer mit Bearbeitungsrecht im Arbeitsschutz</td></tr>",
    "<td>bis zum Ende der Beschäftigung, danach mit der Anonymisierung des Mitarbeiters; nur Benutzer mit Bearbeitungsrecht im Arbeitsschutz oder – mit dem Schalter unter Einstellungen › Benutzer &amp; Netzwerk – nur der Inhaber</td></tr>")
ers("<td>Login, Name, E-Mail-Adresse (für „Passwort vergessen“), Passwort-Hash, Rolle, Sitzungen (Gerät/Browser), Protokolleinträge mit Benutzer</td>",
    "<td>Login, Name, E-Mail-Adresse (für „Passwort vergessen“), Passwort-Hash, Rolle, Sitzungen (Gerät/Browser), Protokolleinträge mit Benutzer, darunter gelungene und fehlgeschlagene Anmeldungen sowie Änderungen an Benutzern und Rechten</td>")
# 5 TOM
ers("Passwörter mit mindestens 8 Zeichen, nur als Prüfwert gespeichert; Sperre nach Fehlversuchen; Anmeldung im Büro verfällt nach 30 Tagen ohne Benutzung;",
    "Passwörter mit mindestens 8 Zeichen (PIN der Stempeluhr mindestens 6), nur als Prüfwert gespeichert; Sperre nach Fehlversuchen; Anmeldung im Büro verfällt nach 30 Tagen ohne Benutzung, die der Stempeluhr nach 120 Tagen (beides einstellbar); „Passwort vergessen“ nur über die am Benutzer selbst hinterlegte E-Mail-Adresse;")
ers("Passwort als gesalzener Hash (PBKDF2-SHA256, 200 000 Runden)", "Passwort als gesalzener Hash (PBKDF2-SHA256, 600 000 Runden; ältere Hashes werden bei der nächsten Anmeldung erneuert)")
ers("Verbandbuch (Gesundheitsdaten) nur für den Inhaber lesbar, Nachweise zu Personen nur mit Arbeitsschutzrecht;",
    "Verbandbuch (Gesundheitsdaten) nur für den Inhaber lesbar, Vorsorgekartei und Expositionsverzeichnis auf Wunsch ebenfalls nur für den Inhaber, Nachweise zu Personen nur mit Arbeitsschutzrecht;")
ers("WLAN-Freigabe nur auf Wunsch, nur im privaten Netz (Firewallregel „Private Netzwerke“), kein Zugriff aus dem Internet, keine Portfreigabe im Router. Verbindung im WLAN verschlüsselt",
    "Freigabe im eigenen Netzwerk nur auf Wunsch, nur im privaten Netz (Firewallregel „Private Netzwerke“), kein Zugriff aus dem Internet, keine Portfreigabe im Router. Verbindung im Netzwerk verschlüsselt")
ers("unveränderbares Protokoll mit Hash-Kette für Festschreibungen, Löschungen, Rücksicherungen, Datenauskünfte, Anonymisierungen und Passwort-Zurücksetzungen; Zugriffsprotokoll des Archivs",
    "unveränderbares Protokoll mit Hash-Kette für Festschreibungen, Löschungen, Rücksicherungen, Datenauskünfte, Anonymisierungen, Passwort-Zurücksetzungen, Anmeldungen und Fehlversuche, Änderungen an Benutzern und Rechten, an Stammdaten und Einstellungen sowie den Versand von Belegen. Weil das Protokoll nicht gelöscht werden kann, nennt es bei Stammdatenänderungen die Person nur mit ihrer Nummer, Bankverbindungen verkürzt und bei Namen, Anschriften, Kontaktdaten und Lohnangaben nur die Tatsache der Änderung; Empfängeradressen und Passwörter stehen nicht darin. Zugriffsprotokoll des Archivs")
# 6 Löschkonzept
ers("<td>Rechnungen: 10 Jahre nach Ende des Belegjahres (sicherer Wert; Buchungsbelege 8 Jahre, Aufzeichnungen 10 Jahre); nur Angebote, AB, Lieferscheine, E-Mails: 6 Jahre. Maßgeblich ist das späteste Fristende.</td><td>„Anonymisieren …“ beim Kunden (nur Inhaber): prüft Frist und offene Posten, entfernt Name, Anschrift, Kontakt, Notizen, Korrespondenz, Anhänge, Unterschriften und archivierte Beleg-PDFs; Zahlen bleiben. Projektordner manuell löschen (Pfad wird angezeigt).</td></tr>",
    "<td>Rechnungen: nach der im Programm eingestellten Frist von 8 bis 10 Jahren nach Ende des Belegjahres (Vorgabe 10 Jahre als sicherer Wert; Buchungsbelege 8 Jahre, Aufzeichnungen 10 Jahre), im Betrieb eingestellt: <span class=\"ein\" data-f=\"d32\">[… Jahre]</span>; nur Angebote, AB, Lieferscheine, E-Mails: 6 Jahre. Maßgeblich ist das späteste Fristende.</td><td>„Anonymisieren …“ beim Kunden (nur Inhaber): prüft Frist und offene Posten. Geleert werden Name, Firma, Straße, Kontakt, Bankverbindung, Geburtstag, Bemerkungen und Merkmale, in den Belegen Kundendaten, Anschrift, Einleitung, Schlusstext und Unterschrift, außerdem Bemerkungen von Aufträgen und Zahlungen, Notizen, Wiedervorlagen und die Korrespondenz. Gelöscht werden die Dateien: archivierte Beleg-PDFs, E-Rechnungs-Dateien, versandte Fassungen, gespeicherte E-Mails, Mahnungen, Briefe, Rapporte mit Unterschriften, Fotos des Bautagebuchs, Anhänge. In Betreff, Auftrags- und Projektbezeichnung und Terminen werden die Namensbestandteile entfernt, in Positionstexten und im Bautagebuch nur erkennbare Namen (mit Anrede oder Vornamen). Bei zugeordneten Kontoumsätzen werden Name, Gegenkonto und Verwendungszweck geleert. Es bleiben Kundennummer, Gruppe, Postleitzahl und Ort (Auswertung nach Gebieten; ohne Name und Straße kein Personenbezug mehr), Positionen, Beträge, Zahlungen und Stunden. Frei formulierte Texte nach dem Anonymisieren stichprobenweise prüfen; Projektordner manuell löschen (Pfad wird angezeigt).</td></tr>"
    "\n<tr><td>Versandte Fassungen von Belegen, gesendete E-Mails als Datei</td><td>6 Jahre (Handels- und Geschäftsbriefe), bei Rechnungen wie oben</td><td>liegen im Datenordner unter „belege/Jahr/versandt“ und „mails/Jahr“; werden mit der Anonymisierung des Kunden gelöscht (Protokolleintrag mit Dateiliste)</td></tr>")
ers("<td>Originaldateien liegen im Datenordner unter „bank/Jahr“; nach Fristablauf dort löschen. Umsätze ohne Bezug zum Betrieb (privat) nicht einlesen bzw. „ohne Zuordnung“ setzen.</td></tr>",
    "<td>Originaldateien liegen im Datenordner unter „bank/Jahr“. Nach Ablauf der eingestellten Frist zeigt die Löschprüfung die betroffenen Auszüge; „Abgelaufene Kontoauszüge löschen“ (nur Inhaber) löscht die Dateien und leert Name, Gegenkonto und Verwendungszweck der Umsätze, Datum, Betrag und Zuordnung bleiben (Protokolleintrag). Umsätze ohne Bezug zum Betrieb (privat) nicht einlesen bzw. „ohne Zuordnung“ setzen.</td></tr>")
ers("<tr><td>Protokoll (Journal)</td><td>10 Jahre</td><td>unveränderbar; enthält nur Kundennummer und Vorgang, keine Inhalte</td></tr>",
    "<tr><td>Protokoll (Journal)</td><td>10 Jahre</td><td>unveränderbar (GoBD), deshalb von Löschung und Anonymisierung ausgenommen (Art. 17 Abs. 3 b DSGVO). Einträge zu Rechnungen und Zahlungen nennen Nummer, Datum, Betrag und den Kurznamen des Kunden; Einträge zu Stammdatenänderungen und Anonymisierungen nur die Kundennummer. Der Kurzname in älteren Einträgen bleibt bis zum Ablauf der Frist bestehen.</td></tr>"
    "\n<tr><td>Vorschau-Dateien, Zwischendateien</td><td>3 Tage</td><td>löscht das Programm selbst (Vorschau-PDFs, gelesene, aber nicht gebuchte Eingangsrechnungen)</td></tr>")
ers("Das Programm setzt bei ihnen „Aufbewahren bis“ auf das Jahresende + 10 Jahre; bis dahin sind Löschen und Anonymisieren gesperrt. Ist die letzte Rechnung im alten Programm bekannt, trägt der Inhaber beim Kunden das passende Datum ein (Jahr der Rechnung + 10, 31.12.;",
    "Das Programm setzt bei ihnen „Aufbewahren bis“ auf das Jahresende plus die eingestellte Aufbewahrungsfrist (Vorgabe 10 Jahre); bis dahin sind Löschen und Anonymisieren gesperrt. Ist die letzte Rechnung im alten Programm bekannt, trägt der Inhaber beim Kunden das passende Datum ein (Jahr der Rechnung plus Frist, 31.12.;")
ers("die Liste der fälligen Kunden, Lieferanten und ausgeschiedenen Mitarbeiter durchgehen (das Programm zeigt nur an, gelöscht wird je Datensatz von Hand)",
    "die Liste der fälligen Kunden, Lieferanten und ausgeschiedenen Mitarbeiter durchgehen (das Programm zeigt nur an, gelöscht wird je Datensatz von Hand), abgelaufene Kontoauszüge dort löschen")
ers("Lieferanten 10 Jahre nach Ende des Jahres der letzten Rechnung, Beschäftigte 10 Jahre nach Ende des Jahres des Austritts.",
    "Lieferanten nach der eingestellten Aufbewahrungsfrist (Vorgabe 10 Jahre) ab Ende des Jahres der letzten Rechnung, Beschäftigte 10 Jahre nach Ende des Jahres des Austritts.")
# 7 Rechte
ers("erstellt einen Brief mit allen gespeicherten Daten (Stammdaten, Aufträge, Belege, Schriftverkehr, Notizen, Termine, Dateien, Rapporte)",
    "erstellt einen Brief mit allen gespeicherten Daten (Stammdaten, Aufträge, Belege und ihre versandten Fassungen, Zahlungen, Mahnungen, zugeordnete Kontoumsätze, Schriftverkehr, Notizen, Termine, Dateien, Rapporte)")
# 11 Beschäftigte
ers("Die Stempeluhr erfasst Beginn, Ende, Pausen, Auftrag und Tätigkeit.",
    "Die Stempeluhr erfasst Beginn, Ende, Pausen, Auftrag und Tätigkeit sowie den Zeitpunkt, zu dem eine Stempelung am Büro-PC eingeht; weicht er um mehr als 15 Minuten von der gestempelten Uhrzeit ab, ist die Zeit im Büro als nachträglich gekennzeichnet. Das dient der Richtigkeit der Arbeitszeitaufzeichnung, nicht der Leistungs- oder Verhaltenskontrolle. Anmeldungen und Fehlversuche der Benutzer stehen aus Gründen der Sicherheit im Protokoll. Hinweise des Programms zu Pausen, Höchstarbeitszeit, Ruhezeit, Mindestlohn und Minijob-Grenze sieht nur, wer das Personalrecht hat.")
open(p, "w", encoding="utf-8").write(s)
print("Ersetzungen:", n)
