p = "/home/claude/eberle-buero/static/hilfe/installation.html"
s = open(p, encoding="utf-8").read()
n = 0
def ers(alt, neu):
    global s, n
    assert s.count(alt) == 1, (s.count(alt), alt[:90])
    s = s.replace(alt, neu); n += 1
ers("<tr><td>Python</td><td>Python 3.10 oder neuer. Fehlt Python, richtet das Programm es beim ersten Start selbst ein (Internetverbindung nötig). Weitere Pakete sind nicht nötig.</td></tr>",
    "<tr><td>Python</td><td>Python 3.12 oder neuer (geprüft mit 3.13 und 3.14). Fehlt Python oder ist nur eine ältere Version vorhanden, richtet das Programm es beim ersten Start selbst ein (Internetverbindung nötig). Weitere Pakete sind nicht nötig.</td></tr>")
ers("<li>Firewall: Hat das Setup sie nicht freigegeben, im Programmordner <b>Handy-Freigabe.bat</b> doppelklicken. Sie gibt die Ports frei, zeigt das Netzwerkprofil (muss „Privat“ sein) und die Adressen.</li>",
    "<li>Firewall: Hat das Setup sie nicht freigegeben, im Programmordner <b>Handy-Freigabe.bat</b> doppelklicken. Sie gibt die Ports frei, zeigt das Netzwerkprofil (muss „Privat“ sein) und die Adressen. Führt Windows das Netzwerk als öffentlich – bei einem neu angeschlossenen Netzwerkkabel ist das die übliche Voreinstellung –, bietet sie an, es auf „Privat“ zu stellen; von Hand geht das unter Windows-Einstellungen › Netzwerk und Internet.</li>"
    "\n<li>Der PC kann per Netzwerkkabel oder per WLAN am Router hängen: Beides gehört zum selben Netz, ein Handy im WLAN erreicht auch einen PC am Kabel. Handys und Tablets müssen im normalen WLAN des Routers sein, nicht im Gastzugang.</li>")
ers("<li>Der neue PC hat eine andere Netzwerkadresse und stellt ein neues https-Zertifikat aus. Auf Tablets und Handys das Zertifikat erneut einrichten (Abschnitt 4) und die Apps unter der neuen Adresse installieren. Autostart am neuen PC einschalten.</li>",
    "<li>Der neue PC hat eine andere Netzwerkadresse und stellt ein neues https-Zertifikat aus. Auf Tablets und Handys das Zertifikat erneut einrichten (Abschnitt 4) und die Apps unter der neuen Adresse installieren. Autostart am neuen PC einschalten. Im Router dem neuen PC eine feste IP-Adresse geben und unter Windows prüfen, dass das Netzwerk als „Privat“ geführt wird (Handy-Freigabe.bat zeigt es an).</li>")
ers("Netzwerk eingeschaltet, Handy-Freigabe.bat ausführen, Netzwerkprofil „Privat“, PC und Gerät im selben WLAN;",
    "Netzwerk eingeschaltet, Handy-Freigabe.bat ausführen, Netzwerkprofil „Privat“, PC und Gerät am selben Router (PC per Kabel oder WLAN, Handy im WLAN, nicht im Gastzugang);")
ers("<tr><td>☐</td><td>Beleg als PDF speichern und öffnen; PDF im Projektordner vorhanden; Rechnung festschreiben, Archiv-PDF unter daten\\belege vorhanden</td></tr>",
    "<tr><td>☐</td><td>Beleg als PDF speichern und öffnen; PDF im Projektordner vorhanden; Rechnung festschreiben, Archiv-PDF unter daten\\belege vorhanden</td></tr>"
    "\n<tr><td>☐</td><td>Mehrseitigen Beleg mit Briefbogen über „Drucken“ auf Papier ausgeben: Die Druckansicht zeigt das PDF, der Ausdruck hat Briefkopf, Fußzeile und Seitenzahlen auf den richtigen Seiten (im Druckfenster „Tatsächliche Größe“)</td></tr>")
ers("<tr><td>☐</td><td>https einschalten, Zertifikat am PC bestätigen; Stempeluhr am Handy über https öffnen und als App installieren</td></tr>",
    "<tr><td>☐</td><td>Handy-Freigabe.bat ausführen: Programm „im Netzwerk erreichbar“, Netzwerkprofil „Private“, Adresse fürs Handy wird angezeigt</td></tr>"
    "\n<tr><td>☐</td><td>https einschalten, Zertifikat am PC bestätigen; Stempeluhr am Handy über https öffnen und als App installieren; eine Stempelung erscheint im Büro unter Mitarbeiter › Zeiten</td></tr>"
    "\n<tr><td>☐</td><td>„Passwort vergessen?“ auf der Anmeldeseite: Der Code kommt an der Adresse an, die am Benutzer hinterlegt ist</td></tr>")
open(p, "w", encoding="utf-8").write(s)
print("Ersetzungen:", n)
