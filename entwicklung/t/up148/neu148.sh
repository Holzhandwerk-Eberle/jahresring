# Vorher: mkdir -p /tmp/claude-0/t/up148/src && git archive a66ffb2 | tar -x -C /tmp/claude-0/t/up148/src  (Programmstand 148). Ablauf: neu148.sh, node s/t10.js, daten148.py, v25/nachziehen.sh, nach149.py, node s/crawl.js
# Prüfinstanz mit dem Programmstand 148 frisch aufsetzen (für die Probe des Updates auf 149)
for f in /proc/[0-9]*/environ; do grep -qa "BUERO_PORT=8799" $f 2>/dev/null && kill $(basename $(dirname $f)) 2>/dev/null; done; sleep 1
T=/tmp/claude-0/t/v25; rm -rf $T/eberle-buero $T/projekte; mkdir -p $T/projekte; cp -r /tmp/claude-0/t/up148/src $T/eberle-buero && rm -rf $T/eberle-buero/daten $T/eberle-buero/entwicklung
cd $T/eberle-buero && (BUERO_PORT=8799 BUERO_BROWSER=/tmp/claude-0/t/fake/chrome nohup python3 app.py kein-browser > $T/log.txt 2>&1 &) ; sleep 2
