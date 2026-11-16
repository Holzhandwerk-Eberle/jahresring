set -e
# Vor jedem Bau läuft die Schnellprüfung; schlägt sie fehl, wird nichts gebaut (zum Umgehen: OHNE_TOR=1 bash bauen.sh)
if [ -z "$OHNE_TOR" ]; then bash /tmp/claude-0/t/lauf/tor.sh || { echo 'Bau abgebrochen: Schnellprüfung nicht bestanden.'; exit 1; }; fi
# Versionsnummer als eigene Datei (für den Update-Hinweis des Programms)
grep -m1 '^VERSION = ' /home/claude/eberle-buero/app.py | grep -oE '[0-9]{4}\.[0-9]{2}\.[0-9]{2}-[0-9]+' > /home/claude/eberle-buero/version.txt
rm -rf /tmp/claude-0/t/stage && mkdir -p /tmp/claude-0/t/stage && cp -r /home/claude/eberle-buero /tmp/claude-0/t/stage/Jahresring && cd /tmp/claude-0/t/stage && rm -rf Jahresring/daten Jahresring/entwicklung Jahresring/.git Jahresring/.gitignore && find Jahresring -name __pycache__ -type d -exec rm -rf {} +
rm -f /home/claude/Jahresring.zip && zip -qr /home/claude/Jahresring.zip Jahresring
cd /tmp/claude-0/t/inst/setup && cp /home/claude/Jahresring.zip payload.zip && grep -o '2026\.[0-9.]*-[0-9]*' /home/claude/eberle-buero/app.py | head -1 > version.txt
python3 /tmp/claude-0/t/inst/syso.py /home/claude/eberle-buero/static/jahresring.ico rsrc_windows_amd64.syso "$(cat version.txt)" "Holzhandwerk Eberle"
GOOS=windows GOARCH=amd64 go build -trimpath -ldflags "-H windowsgui -s -w" -o /home/claude/Jahresring-Setup.exe .
ls -la /home/claude/Jahresring.zip /home/claude/Jahresring-Setup.exe; cat version.txt
