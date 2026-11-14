O=/tmp/claude-0/t/lauf; N="bash /tmp/claude-0/t/v25/neu.sh"; rm -f $O/teil3.done
$N >/dev/null 2>&1; cd /tmp/claude-0/t/ps && timeout 600 python3 test.py > $O/ps_test.txt 2>&1; timeout 600 node e2e.js > $O/ps_e2e.txt 2>&1
$N >/dev/null 2>&1; cd /tmp/claude-0/t/ps && timeout 600 node status.js > $O/ps_status.txt 2>&1
$N >/dev/null 2>&1; cd /tmp/claude-0/t/ps && timeout 600 node kal.js > $O/ps_kal.txt 2>&1; timeout 600 python3 zert_test.py > $O/zert.txt 2>&1
$N >/dev/null 2>&1; cd /tmp/claude-0/t/sec && timeout 600 python3 gobd.py >/dev/null 2>&1; cd /tmp/claude-0/t/audit3 && timeout 900 python3 export.py > $O/export.txt 2>&1; timeout 900 python3 fuzz.py > $O/fuzz.txt 2>&1
echo FERTIG > $O/teil3.done
