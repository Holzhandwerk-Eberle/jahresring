# Ergebnis der Gesamtprüfung auf einen Blick: je Ausgabedatei Schlusszeile und Zahl der Fehlerzeilen
import re, sys, os, glob
O = "/tmp/claude-0/t/lauf"
namen = "t10 crawl az_test az_beleg kalk er kalk_e2e sec gobd ausfall3 tresor https rechte fach sperre xss xssjs xss2 werkui stempel ps_test ps_e2e ps_status ps_kal zert export fuzz as_api as_perm as_xss as_fuzz as_ui tafel layout1400 layout1100 layout820 t30 bank datev preise wv bank_ui mbhash inv neu_pruef neu_kalender neu_namen neu_csp".split()
namen += [os.path.basename(p)[:-4] for p in sorted(glob.glob(O + "/neu149_*.txt")) + sorted(glob.glob(O + "/teil6_*.txt"))]
for n in namen:
    p = f"{O}/{n}.txt"
    if not os.path.exists(p): print(f"{n:22} FEHLT"); continue
    t = open(p, encoding="utf-8", errors="replace").read(); z = [x for x in t.splitlines() if x.strip()]
    schlecht = [x for x in z if re.search(r"^\s*(FEHLER|FAIL|✗|NICHT ok|!!)|Traceback|Error:|^falsch ", x) and not re.search(r"FEHLER: \[\]|fehler \[\]|^Fehler: 0", x)]
    print(f"{n:22} {len(z):5} Zeilen  {len(schlecht):3} auffällig  | {(z[-1] if z else '(leer)')[:150]}")
    for x in schlecht[:4]: print("        >", x[:200])
