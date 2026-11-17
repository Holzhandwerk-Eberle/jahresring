# Nach dem Bau von 150: zweiter Prüfteil (Sicherheit, GoBD, Ausfall, Sicherungskennwort, Rechte) und Probe des Updates von 148 mit Daten
O=/tmp/claude-0/t/lauf; T=/tmp/claude-0/t; rm -f $O/nachlauf150.done
bash $O/teil2.sh
bash $T/up148/neu148.sh >/dev/null 2>&1
cd $T/v25 && timeout 600 node s/t10.js > $T/up148/t10.txt 2>&1
python3 $T/up148/daten148.py > $O/up148_daten.txt 2>&1
bash $T/v25/nachziehen.sh > $O/up148_nachziehen.txt 2>&1
python3 $T/up148/nach149.py > $O/up148_nach.txt 2>&1
cd $T/v25 && timeout 600 node s/crawl.js > $O/up148_crawl.txt 2>&1
touch $O/nachlauf150.done
