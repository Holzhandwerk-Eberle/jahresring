#!/bin/bash
# Prüfungen zur Version 149 (Umsetzung des Prüfberichts), jede auf frischer Instanz; Ausgabe: je Prüfung eine Zeile mit Dauer
T=/tmp/claude-0/t; O=$T/lauf; rc=0
lauf() { name=$1; shift; bash $T/v25/neu.sh >/dev/null 2>&1; a=$(date +%s); "$@" > $O/neu149_$name.txt 2>&1; e=$(date +%s)
         if grep -q 'FEHLER: \[\]' $O/neu149_$name.txt && ! grep -q 'Traceback' $O/neu149_$name.txt; then echo "ok     $name ($((e-a)) s)"; else echo "FEHLER $name ($((e-a)) s, siehe $O/neu149_$name.txt)"; rc=1; fi; }
for n in ${@:-sicher149 rechnen149 bank149 import149 nachweis149 datenschutz149 personal149}; do lauf $n python3 $T/neu/$n.py; done
exit $rc
