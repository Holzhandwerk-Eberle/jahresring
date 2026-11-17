# Ausgaben der Gesamtprüfung mit dem Stand der Vorversion vergleichen (Zeitstempel, Nonces, Größen geglättet)
import re, os, sys, difflib
O = "/tmp/claude-0/t/lauf"; A = O + "/stand_148"
namen = "t10 crawl az_test az_beleg kalk er kalk_e2e sec gobd ausfall3 tresor https rechte fach sperre xss xssjs xss2 werkui stempel ps_test ps_e2e ps_status ps_kal zert export fuzz as_api as_perm as_xss as_fuzz as_ui tafel layout1400 layout1100 layout820 t30 bank datev preise wv bank_ui mbhash inv neu_pruef neu_kalender neu_namen neu_csp".split()
def glatt(t):
    t = re.sub(r"\d{4}-\d{2}-\d{2}[T _]\d{2}[:\-]\d{2}([:\-]\d{2})?", "<ZEIT>", t)
    t = re.sub(r"\b\d{2}:\d{2}(:\d{2})?\b", "<UHR>", t)
    t = re.sub(r"nonce-[A-Za-z0-9_\-]+", "nonce-<N>", t)
    t = re.sub(r"\b[0-9a-f]{12,64}\b", "<HEX>", t)
    t = re.sub(r"\b\d+(\.\d+)? ?(ms|s|Byte|KB|MB)\b", "<MASS>", t)
    t = re.sub(r"'Date': '[^']*'", "'Date': '<D>'", t)
    t = re.sub(r"2026\.11\.01-1[45]\d", "<VERSION>", t)
    return t
nur = sys.argv[1:] or namen
for n in nur:
    a, b = f"{A}/{n}.txt", f"{O}/{n}.txt"
    if not (os.path.exists(a) and os.path.exists(b)): print(f"== {n}: fehlt"); continue
    x, y = glatt(open(a, errors="replace").read()).splitlines(), glatt(open(b, errors="replace").read()).splitlines()
    d = [z for z in difflib.unified_diff(x, y, lineterm="", n=0) if not z.startswith(("---", "+++", "@@"))]
    if not d: continue
    print(f"== {n}: {len(d)} geänderte Zeilen")
    for z in d[: (40 if len(nur) < 4 else 6)]: print("   ", z[:300])
