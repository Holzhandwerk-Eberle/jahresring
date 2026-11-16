"""Prüft die Skripte der Oberfläche auf doppelte globale Namen (alle Skripte teilen sich einen Namensraum) und auf
Kennungen (id="…"), die innerhalb derselben Funktion mehrfach vergeben werden. Bekannte, unschädliche Doppelungen stehen
in ids_basis.txt; nur neue Funde gelten als Fehler."""
import re, glob, collections, os, sys
S = next((a for a in sys.argv[1:] if not a.startswith("--")), "/home/claude/eberle-buero") + "/static"
HIER = os.path.dirname(os.path.abspath(__file__))
fehler = []
namen = collections.defaultdict(list)
dateien = sorted(glob.glob(S + "/*.js")) + [S + "/index.html"]
for f in dateien:
    if f.endswith("sw.js"): continue
    for i, z in enumerate(open(f, encoding="utf-8").read().split("\n"), 1):
        m = re.match(r"(?:async\s+)?(?:function\*?|const|let|var|class)\s+([A-Za-z_$][\w$]*)", z)
        if m: namen[m.group(1)].append(f"{os.path.basename(f)}:{i}")
for k, v in sorted(namen.items()):
    if len(v) > 1: fehler.append(f"globaler Name doppelt: {k} ({', '.join(v)})")
# Kennungen je oberster Funktion
funde = set()
for f in dateien:
    text = open(f, encoding="utf-8").read().split("\n")
    fn, ids = "(oben)", collections.Counter()
    def schluss():
        for k, n in ids.items():
            if n > 1: funde.add(f"{os.path.basename(f)} {fn} #{k}")
    for z in text:
        m = re.match(r"(?:async\s+)?function\*?\s+([A-Za-z_$][\w$]*)", z)
        if m:
            schluss(); fn, ids = m.group(1), collections.Counter()
        for k in re.findall(r'\bid="([A-Za-z][\w-]*)"', z): ids[k] += 1
    schluss()
basis_datei = os.path.join(HIER, "ids_basis.txt")
if "--basis" in sys.argv:
    open(basis_datei, "w", encoding="utf-8").write("\n".join(sorted(funde)) + "\n"); print("Basis geschrieben:", len(funde))
basis = set(open(basis_datei, encoding="utf-8").read().split("\n")) if os.path.exists(basis_datei) else set()
for x in sorted(funde - basis): fehler.append("Kennung in einer Funktion mehrfach: " + x)
print(len(namen), "globale Namen,", len(funde), "bekannte Mehrfach-Kennungen (Basis", len(basis - {''}), ")")
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
