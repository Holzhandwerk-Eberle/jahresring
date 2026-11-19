export NODE_PATH=/opt/npm-tools/node_modules; O=/tmp/claude-0/t/lauf; T=/tmp/claude-0/t; N="bash /tmp/claude-0/t/v25/neu.sh"; rm -f $O/teil6.done
# Prüfungen zur Version 149 (Umsetzung des Prüfberichts), jede auf frischer Instanz
for n in sicher149 rechnen149 bank149 import149 nachweis149 datenschutz149 personal149; do $N >/dev/null 2>&1; timeout 600 python3 $T/neu/$n.py > $O/teil6_$n.txt 2>&1; done
$N >/dev/null 2>&1; cd $T/v25 && timeout 600 node s/t10.js > /dev/null 2>&1; cp $T/neu/druckweg.js $T/neu/zahlen.js s/
timeout 400 xvfb-run -a node s/druckweg.js > $O/teil6_druckweg.txt 2>&1; timeout 400 node s/zahlen.js > $O/teil6_zahlen.txt 2>&1
# Version 150: Datenbestand vom bisherigen PC übernehmen (eigene Instanzen, eigene Ports), danach die Seiten im Browser
timeout 900 python3 $T/neu/uebernahme150.py > $O/teil6_uebernahme150.txt 2>&1
cd $T/v25 && cp $T/neu/uebernahme_ui.js s/ && timeout 400 node s/uebernahme_ui.js > $O/teil6_uebernahme_ui.txt 2>&1
# Version 151: Erinnerungen des Arbeitsschutzes auf der Startseite abschaltbar (nur diese), an der Schnittstelle und im Browser
$N >/dev/null 2>&1; timeout 600 python3 $T/neu/startas151.py > $O/teil6_startas151.txt 2>&1
cd $T/v25 && cp $T/neu/startas_ui.js s/ && timeout 400 node s/startas_ui.js > $O/teil6_startas_ui.txt 2>&1
# Version 152 (Umsetzung des zweiten Prüfberichts), jede Prüfung auf frischer Instanz; die beiden Browserprüfungen bauen sich ihre selbst auf
for n in bank152 rechnen152 import152 widerruf152 sicher152 spur152 pflege152; do $N >/dev/null 2>&1; timeout 900 python3 $T/neu/$n.py > $O/teil6_$n.txt 2>&1; done
cd $T/v25 && cp $T/neu/widerruf_ui.js $T/neu/ui152.js s/ && timeout 600 node s/widerruf_ui.js > $O/teil6_widerruf_ui.txt 2>&1; timeout 900 node s/ui152.js > $O/teil6_ui152.txt 2>&1
cp $T/neu/seitenwechsel.js s/ && timeout 400 node s/seitenwechsel.js > $O/teil6_seitenwechsel.txt 2>&1
echo FERTIG > $O/teil6.done
