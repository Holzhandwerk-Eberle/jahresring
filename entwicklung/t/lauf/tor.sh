#!/bin/bash
# Schnellprüfung vor jedem Bau (etwa 25 Minuten): Syntax, doppelte Namen, Kalkulation, Kalender, neue Prüfungen,
# Bedienoberfläche (Durchlauf, alle Seiten, Inhaltsschutz). Bricht mit Fehlercode ab, wenn etwas nicht stimmt.
Q=/home/claude/eberle-buero; O=/tmp/claude-0/t/lauf; T=/tmp/claude-0/t; rc=0
schritt() { name="$1"; shift; if "$@" > $O/tor_$name.txt 2>&1; then echo "ok     $name"; else echo "FEHLER $name  (siehe $O/tor_$name.txt)"; rc=1; fi; }
syntax() { for f in $Q/*.py; do python3 -c "import ast,sys; ast.parse(open(sys.argv[1], encoding='utf-8').read())" "$f" || return 1; done
           for f in $Q/static/*.js; do node --check "$f" || return 1; done; }
sauber() { ! grep -q "FEHLER \|Traceback\|Error:" "$1" && grep -q "$2" "$1"; }
schritt syntax syntax
schritt namen python3 $T/neu/namen.py
schritt kalkulation bash -c "python3 $T/audit/kalk_test.py | grep -q 'alles stimmt'"
schritt kalender python3 $T/neu/kalender_test.py
bash $T/v25/neu.sh >/dev/null 2>&1
schritt pruefungen python3 $T/neu/pruef.py
bash $T/v25/neu.sh >/dev/null 2>&1
schritt pruefungen141 python3 $T/neu/pruef141.py
schritt update_pdf python3 $T/neu/update_test.py
bash $T/v25/neu.sh >/dev/null 2>&1
schritt kontoauszug_entfernen python3 $T/neu/bank_weg.py
bash $T/v25/neu.sh >/dev/null 2>&1
schritt zahlungsplan python3 $T/neu/plan_wochen.py
bash $T/v25/neu.sh >/dev/null 2>&1
schritt dateiname python3 $T/neu/dateiname.py
bash $T/v25/neu.sh >/dev/null 2>&1
schritt uebertrag bash -c "python3 $T/neu/uebertrag.py > $O/tor_uebertrag.txt 2>&1"
schritt preisimport bash -c "bash $T/v25/neu.sh >/dev/null 2>&1; python3 $T/bank/preise.py | grep -q 'FEHLER: \[\]'"
# Prüfungen zur Umsetzung des Prüfberichts (Version 149): Sicherheit, Rechnen, Bank, Importe, Nachvollziehbarkeit, Datenschutz, Personal
for n in sicher149 rechnen149 bank149 import149 nachweis149 datenschutz149 personal149; do
  bash $T/v25/neu.sh >/dev/null 2>&1
  schritt $n bash -c "python3 $T/neu/$n.py > $O/tor_aus_$n.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_aus_$n.txt"
done
# Version 150: Datenbestand vom bisherigen PC übernehmen (eigene Instanzen auf den Ports 8796 bis 8798), danach dieselben Seiten im Browser
schritt uebernahme150 bash -c "timeout 900 python3 $T/neu/uebernahme150.py > $O/tor_aus_uebernahme150.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_aus_uebernahme150.txt"
schritt uebernahme_ui bash -c "cd $T/v25 && cp $T/neu/uebernahme_ui.js s/uebernahme_ui.js && timeout 400 node s/uebernahme_ui.js > $O/tor_aus_uebernahme_ui.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_aus_uebernahme_ui.txt"
# Version 151: Erinnerungen des Arbeitsschutzes auf der Startseite abschaltbar (nur diese), an der Schnittstelle und im Browser
bash $T/v25/neu.sh >/dev/null 2>&1
schritt startas151 bash -c "python3 $T/neu/startas151.py > $O/tor_aus_startas151.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_aus_startas151.txt"
schritt startas_ui bash -c "cd $T/v25 && cp $T/neu/startas_ui.js s/startas_ui.js && timeout 400 node s/startas_ui.js > $O/tor_aus_startas_ui.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_aus_startas_ui.txt"
# Version 152 (Umsetzung des zweiten Prüfberichts): Bank und Skonto, Rechnen, Importe, Widerruf, Zugriff, Spurprüfung, Pflege der gesetzlichen Werte
for n in bank152 rechnen152 import152 widerruf152 sicher152 spur152 pflege152; do
  bash $T/v25/neu.sh >/dev/null 2>&1
  schritt $n bash -c "timeout 900 python3 $T/neu/$n.py > $O/tor_aus_$n.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_aus_$n.txt"
done
# dazu im Browser (beide bauen sich ihre Instanz selbst auf): Widerruf mit Sperre im Kalender, einheitliche Oberfläche und Seite „Gesetzliche Werte“
schritt widerruf_ui bash -c "cd $T/v25 && cp $T/neu/widerruf_ui.js s/widerruf_ui.js && timeout 600 node s/widerruf_ui.js > $O/tor_aus_widerruf_ui.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_aus_widerruf_ui.txt"
schritt ui152 bash -c "cd $T/v25 && cp $T/neu/ui152.js s/ui152.js && timeout 900 node s/ui152.js > $O/tor_aus_ui152.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_aus_ui152.txt"
schritt seitenwechsel bash -c "cd $T/v25 && cp $T/neu/seitenwechsel.js s/seitenwechsel.js && timeout 400 node s/seitenwechsel.js > $O/tor_aus_seitenwechsel.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_aus_seitenwechsel.txt"
bash $T/v25/neu.sh >/dev/null 2>&1
schritt durchlauf bash -c "cd $T/v25 && timeout 600 node s/t10.js > $O/tor_t10.txt 2>&1; tail -1 $O/tor_t10.txt | grep -q 'fehler \[\]'"
schritt seiten bash -c "cd $T/v25 && timeout 600 node s/crawl.js > $O/tor_crawl.txt 2>&1; grep -q '^Fehler: 0' $O/tor_crawl.txt && grep -q '^Auffällige Texte: 0' $O/tor_crawl.txt"
schritt inhaltsschutz bash -c "cd $T/v25 && cp $T/neu/csp.js s/csp.js && timeout 300 node s/csp.js > $O/tor_csp.txt 2>&1; ! grep -q FEHLER $O/tor_csp.txt && grep -q 'keine Verstöße' $O/tor_csp.txt"
# Druckweg (echter Browser unter Xvfb: gedruckt wird das PDF des Programms) und Zahleneingabe, beide auf den Daten des Durchlaufs
schritt druckweg bash -c "cd $T/v25 && cp $T/neu/druckweg.js s/druckweg.js && timeout 400 xvfb-run -a node s/druckweg.js > $O/tor_aus_druckweg.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_aus_druckweg.txt"
schritt zahleneingabe bash -c "cd $T/v25 && cp $T/neu/zahlen.js s/zahlen.js && timeout 400 node s/zahlen.js > $O/tor_aus_zahlen.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_aus_zahlen.txt"
bash $T/v25/neu.sh >/dev/null 2>&1
schritt beschlagsets bash -c "cd $T/v25 && cp $T/neu/sets.js s/sets.js && timeout 300 node s/sets.js > $O/tor_sets.txt 2>&1; grep -q 'FEHLER: \[\]' $O/tor_sets.txt"
[ $rc = 0 ] && echo "Schnellprüfung bestanden" || echo "Schnellprüfung NICHT bestanden"
exit $rc
