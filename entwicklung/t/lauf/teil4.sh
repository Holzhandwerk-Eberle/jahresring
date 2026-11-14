O=/tmp/claude-0/t/lauf; N="bash /tmp/claude-0/t/v25/neu.sh"; rm -f $O/teil4.done
$N >/dev/null 2>&1; cd /tmp/claude-0/t/as/test && timeout 600 python3 api.py > $O/as_api.txt 2>&1; timeout 600 python3 perm.py > $O/as_perm.txt 2>&1; timeout 600 python3 xss_as.py > $O/as_xss.txt 2>&1; timeout 900 python3 fuzz_as.py > $O/as_fuzz.txt 2>&1; timeout 600 python3 ui.py > $O/as_ui.txt 2>&1; timeout 300 python3 /tmp/claude-0/t/gp/tafel.py > $O/tafel.txt 2>&1
cd /tmp/claude-0/t/layout && for b in 1400 1100 820; do timeout 900 node layout.js $b > $O/layout$b.txt 2>&1; done
cd /tmp/claude-0/t/v25 && timeout 900 node s/t30.js > $O/t30.txt 2>&1
echo FERTIG > $O/teil4.done
