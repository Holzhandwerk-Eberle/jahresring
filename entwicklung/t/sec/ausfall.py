import json, sys, threading, sqlite3, glob, os, time, subprocess, signal
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
T = "/tmp/claude-0/t/v25"; D = T + "/eberle-buero/daten"; J = json.loads
def pid():
    for f in glob.glob("/proc/[0-9]*/environ"):
        try:
            if b"BUERO_PORT=8799" in open(f, "rb").read() and b"app.py" in open(os.path.dirname(f) + "/cmdline", "rb").read(): return int(f.split("/")[2])
        except OSError: pass
def start():
    subprocess.Popen("cd %s/eberle-buero && BUERO_PORT=8799 BUERO_BROWSER=/tmp/claude-0/t/fake/chrome nohup python3 app.py kein-browser >> %s/log.txt 2>&1 &" % (T, T), shell=True)
    for _ in range(40):
        time.sleep(0.5)
        try:
            if rq(cl(), "GET", "/api/version")[0] == 200: return True
        except Exception: pass
    return False
def login():
    o = cl(); rq(o, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}); return o
inh = login(); db = glob.glob(D + "/*.db")[0]
k = J(rq(inh, "GET", "/api/kunden")[1])[0]["id"]
# 1 Absturz mitten im Schreiben
stop = []; ok = [0]
def schreiben(n):
    o = login()
    while not stop:
        try:
            s, b, _ = rq(o, "POST", "/api/auftraege", {"kunde_id": k, "bezeichnung": f"Last {n}"})
            if s == 200: ok[0] += 1; letzte[n] = J(b)["id"]
        except Exception: return
letzte = {}
th = [threading.Thread(target=schreiben, args=(i,), daemon=True) for i in range(6)]; [t.start() for t in th]; time.sleep(4)
p = pid(); os.kill(p, signal.SIGKILL); stop.append(1); time.sleep(1)
print("Absturz nach", ok[0], "bestätigten Aufträgen; WAL-Datei:", os.path.exists(db + "-wal") and os.path.getsize(db + "-wal"))
t0 = time.time(); print("Neustart ok:", start(), round(time.time() - t0, 1), "s")
c = sqlite3.connect(db); print("integrity:", c.execute("PRAGMA integrity_check").fetchone()[0], "| Aufträge in DB:", c.execute("SELECT COUNT(*) FROM auftraege WHERE bezeichnung LIKE 'Last%'").fetchone()[0], "bestätigt:", ok[0],
      "| alle bestätigten da:", all(c.execute("SELECT 1 FROM auftraege WHERE id=?", (i,)).fetchone() for i in letzte.values())); c.close()
inh = login(); pr = J(rq(inh, "GET", "/api/service/protokoll?voll=1")[1]); print("Protokoll nach Absturz:", pr["pruefung"]["ok"], "Belege:", pr["belege"]["ok"] if pr["belege"] else None)
# 2 Sicherung und Rücksicherung
s, b, _ = rq(inh, "GET", "/api/service/sicherungen"); print("sicherungen", s, b[:200])
