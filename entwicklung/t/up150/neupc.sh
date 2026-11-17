# „Neuer PC“: frische Instanz in einem anderen Ordner als der alte Bestand (Port 8797), ohne Daten
P=${1:-8797}
for f in /proc/[0-9]*/environ; do grep -qa "BUERO_PORT=$P" $f 2>/dev/null && kill $(basename $(dirname $f)) 2>/dev/null; done; sleep 1
T=/tmp/claude-0/t/up150/neupc; rm -rf $T; mkdir -p $T/Jahresring
cd /home/claude/eberle-buero && for x in *; do case "$x" in daten|entwicklung|__pycache__) ;; *) cp -r "$x" $T/Jahresring/ ;; esac; done
cd $T/Jahresring && (BUERO_PORT=$P BUERO_BROWSER=/tmp/claude-0/t/fake/chrome nohup ${BUERO_PY:-python3} app.py kein-browser > $T/log.txt 2>&1 &) ; sleep 2
curl -s -o /dev/null -w "neuer PC: %{http_code}\n" http://127.0.0.1:$P/
