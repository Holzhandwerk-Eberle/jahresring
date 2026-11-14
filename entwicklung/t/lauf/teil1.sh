O=/tmp/claude-0/t/lauf; cd /tmp/claude-0/t/v25
bash neu.sh >/dev/null 2>&1
timeout 900 node s/t10.js > $O/t10.txt 2>&1
timeout 900 node s/crawl.js > $O/crawl.txt 2>&1
cd /tmp/claude-0/t/az && timeout 600 python3 test.py > $O/az_test.txt 2>&1; timeout 600 python3 beleg.py > $O/az_beleg.txt 2>&1
cd /tmp/claude-0/t/audit && timeout 600 python3 kalk_test.py > $O/kalk.txt 2>&1
cd /tmp/claude-0/t/er && timeout 600 python3 audit.py > $O/er.txt 2>&1; timeout 600 python3 kalk_e2e.py > $O/kalk_e2e.txt 2>&1
cp /tmp/claude-0/t/v25/eberle-buero/daten/buero.db $O/teil1.db 2>/dev/null
echo FERTIG > $O/teil1.done
