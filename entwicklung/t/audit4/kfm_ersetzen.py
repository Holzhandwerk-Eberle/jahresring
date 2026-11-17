"""Ersetzt round(AUSDRUCK, 2) durch kfm(AUSDRUCK) (kaufmännisches Runden) in den Rechenteilen des Programms.
Unberührt bleiben: Fingerabdrücke und alles, was in eine Unterschrift eingeht (dort muss das Ergebnis bitgenau gleich bleiben)."""
import re, sys
def ersetze(text, ausnahme=lambda pos: False):
    aus, i, n = [], 0, 0
    for m in re.finditer(r"(?<![\w.])round\(", text):
        if m.start() < i or ausnahme(m.start()):
            continue
        j, tiefe, args, start, zeichen = m.end(), 1, [], m.end(), None
        while j < len(text) and tiefe:
            c = text[j]
            if zeichen:
                if c == "\\": j += 1
                elif c == zeichen: zeichen = None
            elif c in "\"'": zeichen = c
            elif c in "([{": tiefe += 1
            elif c in ")]}":
                tiefe -= 1
                if tiefe == 0: args.append(text[start:j])
            elif c == "," and tiefe == 1:
                args.append(text[start:j]); start = j + 1
            j += 1
        if tiefe or len(args) != 2 or args[1].strip() != "2":
            continue
        aus.append(text[i:m.start()] + "kfm(" + args[0].rstrip() + ")"); i = j; n += 1
    aus.append(text[i:])
    return "".join(aus), n
gesamt = 0
for datei in sys.argv[1:]:
    s = open(datei, encoding="utf-8").read()
    aus = lambda pos: False
    if datei.endswith("app.py"):
        a = s.index("def beleg_fingerabdruck(b):"); e = s.index("\ndef ", a + 10)
        aus = lambda pos, a=a, e=e: a <= pos < e
    neu, n = ersetze(s, aus)
    # (verschachtelte Fälle: round(x - round(y, 2), 2) → zweiter Durchgang)
    while True:
        neu2, n2 = ersetze(neu, (lambda pos: False) if not datei.endswith("app.py") else (lambda pos, t=neu: t.index("def beleg_fingerabdruck(b):") <= pos < t.index("\ndef ", t.index("def beleg_fingerabdruck(b):") + 10)))
        if not n2: break
        neu, n = neu2, n + n2
    if n:
        if not re.search(r"^from kern import .*\bkfm\b|^from kern import \(.*\bkfm\b", neu, re.M | re.S) and "kfm = " not in neu and "def kfm" not in neu:
            print("  !! kfm noch nicht eingebunden:", datei)
        open(datei, "w", encoding="utf-8").write(neu)
    print(f"{datei}: {n} ersetzt"); gesamt += n
print("gesamt", gesamt)
