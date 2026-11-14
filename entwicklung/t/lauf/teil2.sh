O=/tmp/claude-0/t/lauf; N="bash /tmp/claude-0/t/v25/neu.sh"; rm -f $O/teil2.done
$N >/dev/null 2>&1; cd /tmp/claude-0/t/sec && timeout 600 python3 sec.py > $O/sec.txt 2>&1
$N >/dev/null 2>&1; cd /tmp/claude-0/t/sec && timeout 600 python3 gobd.py > $O/gobd.txt 2>&1; timeout 600 python3 ausfall3.py > $O/ausfall3.txt 2>&1; timeout 600 python3 tresor_test.py > $O/tresor.txt 2>&1; timeout 600 python3 https_test.py > $O/https.txt 2>&1
$N >/dev/null 2>&1; cd /tmp/claude-0/t/sec && timeout 600 python3 gobd.py >/dev/null 2>&1; cd /tmp/claude-0/t/audit2 && timeout 600 python3 rechte.py > $O/rechte.txt 2>&1; timeout 600 python3 fach.py > $O/fach.txt 2>&1; timeout 600 python3 sperre.py > $O/sperre.txt 2>&1
$N >/dev/null 2>&1; cd /tmp/claude-0/t/sec && timeout 600 python3 gobd.py >/dev/null 2>&1; cd /tmp/claude-0/t/audit2 && timeout 600 python3 xss.py > $O/xss.txt 2>&1; timeout 600 node xss.js > $O/xssjs.txt 2>&1; timeout 600 node xss2.js > $O/xss2.txt 2>&1; timeout 600 node werkui.js > $O/werkui.txt 2>&1; timeout 600 node stempel.js > $O/stempel.txt 2>&1
echo FERTIG > $O/teil2.done
