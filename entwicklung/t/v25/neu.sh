for f in /proc/[0-9]*/environ; do grep -qa "BUERO_PORT=8799" $f 2>/dev/null && kill $(basename $(dirname $f)) 2>/dev/null; done; sleep 1
T=/tmp/claude-0/t/v25; rm -rf $T/eberle-buero $T/projekte; mkdir -p $T/projekte; cp -r /home/claude/eberle-buero $T/ && rm -rf $T/eberle-buero/daten
cd $T/eberle-buero && (BUERO_PORT=8799 BUERO_BROWSER=/tmp/claude-0/t/fake/chrome nohup python3 app.py kein-browser > $T/log.txt 2>&1 &) ; sleep 2
