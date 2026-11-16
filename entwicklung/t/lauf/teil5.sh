export NODE_PATH=/opt/npm-tools/node_modules; O=/tmp/claude-0/t/lauf; N="bash /tmp/claude-0/t/v25/neu.sh"; rm -f $O/teil5.done
cd /tmp/claude-0/t/bank
$N >/dev/null 2>&1; timeout 600 python3 test.py > $O/bank.txt 2>&1
$N >/dev/null 2>&1; timeout 600 python3 datev.py > $O/datev.txt 2>&1
$N >/dev/null 2>&1; timeout 600 python3 preise.py > $O/preise.txt 2>&1
$N >/dev/null 2>&1; timeout 600 python3 wv.py > $O/wv.txt 2>&1
$N >/dev/null 2>&1; timeout 600 python3 test.py > /dev/null 2>&1; timeout 300 node ui.js > $O/bank_ui.txt 2>&1
cd /tmp/claude-0/t/gp && timeout 200 python3 mbhash.py > $O/mbhash.txt 2>&1; $N >/dev/null 2>&1; timeout 300 python3 inv.py > $O/inv.txt 2>&1
$N >/dev/null 2>&1; timeout 600 python3 /tmp/claude-0/t/neu/pruef.py > $O/neu_pruef.txt 2>&1; python3 /tmp/claude-0/t/neu/kalender_test.py > $O/neu_kalender.txt 2>&1; python3 /tmp/claude-0/t/neu/namen.py > $O/neu_namen.txt 2>&1
$N >/dev/null 2>&1; cd /tmp/claude-0/t/v25 && timeout 600 node s/t10.js > /dev/null 2>&1; cp /tmp/claude-0/t/neu/csp.js s/csp.js; timeout 300 node s/csp.js > $O/neu_csp.txt 2>&1
echo FERTIG > $O/teil5.done
