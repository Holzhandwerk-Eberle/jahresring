#!/bin/bash
# Schnellprüfung vor jedem Bau (etwa zwei Minuten): Syntax, doppelte Namen, Kalkulation, Kalender, neue Prüfungen,
# Bedienoberfläche (Durchlauf, alle Seiten, Inhaltsschutz). Bricht mit Fehlercode ab, wenn etwas nicht stimmt.
Q=/home/claude/eberle-buero; O=/tmp/claude-0/t/lauf; T=/tmp/claude-0/t; rc=0
schritt() { name="$1"; shift; if "$@" > $O/tor_$name.txt 2>&1; then echo "ok     $name"; else echo "FEHLER $name  (siehe $O/tor_$name.txt)"; rc=1; fi; }
syntax() { for f in $Q/*.py; do python3 -c "import ast,sys; ast.parse(open(sys.argv[1], encoding='utf-8').read())" "$f" || return 1; done
           for f in $Q/static/*.js; do node --check "$f" || return 1; done; }
sauber() { ! grep -q "FEHLER \|Traceback\|Error:" "$1" && grep -q "$2" "$1"; }
schritt syntax syntax
schritt namen python3 $T/neu/namen.py
schritt kalkulation bash -c "python3 $T/audit/kalk_test.py | grep -q 'alles stimmt'"
schritt kalender python3 $T/neu/kalender_test.py
bash $T/v25/neu.sh >/dev/null 2>&1
schritt pruefungen python3 $T/neu/pruef.py
bash $T/v25/neu.sh >/dev/null 2>&1
schritt durchlauf bash -c "cd $T/v25 && timeout 600 node s/t10.js > $O/tor_t10.txt 2>&1; tail -1 $O/tor_t10.txt | grep -q 'fehler \[\]'"
schritt seiten bash -c "cd $T/v25 && timeout 600 node s/crawl.js > $O/tor_crawl.txt 2>&1; grep -q '^Fehler: 0' $O/tor_crawl.txt && grep -q '^Auffällige Texte: 0' $O/tor_crawl.txt"
schritt inhaltsschutz bash -c "cd $T/v25 && cp $T/neu/csp.js s/csp.js && timeout 300 node s/csp.js > $O/tor_csp.txt 2>&1; ! grep -q FEHLER $O/tor_csp.txt && grep -q 'keine Verstöße' $O/tor_csp.txt"
[ $rc = 0 ] && echo "Schnellprüfung bestanden" || echo "Schnellprüfung NICHT bestanden"
exit $rc
