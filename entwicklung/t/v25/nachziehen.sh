# Geänderte Programmdateien in die laufende Prüfinstanz übernehmen (Daten bleiben) und den Server neu starten
T=/tmp/claude-0/t/v25
for f in /proc/[0-9]*/environ; do grep -qa "BUERO_PORT=8799" $f 2>/dev/null && kill $(basename $(dirname $f)) 2>/dev/null; done; sleep 1
cp /home/claude/eberle-buero/*.py $T/eberle-buero/ && cp -r /home/claude/eberle-buero/static/. $T/eberle-buero/static/
cd $T/eberle-buero && (BUERO_PORT=8799 BUERO_BROWSER=/tmp/claude-0/t/fake/chrome nohup ${BUERO_PY:-python3} app.py kein-browser >> $T/log.txt 2>&1 &) ; sleep 2
curl -s -o /dev/null -w "Instanz: %{http_code}\n" http://127.0.0.1:8799/
