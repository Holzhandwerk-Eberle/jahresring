exec(open("/tmp/claude-0/t/sec/ausfall.py").read().split("inh = login(); db =")[0])
inh = login(); db = glob.glob(D + "/*.db")[0]
t0 = time.time(); s, b, _ = rq(inh, "POST", "/api/service/sicherung", {"notiz": "Test"}); print("Vollsicherung", s, b[:160], round(time.time() - t0, 1), "s")
name = J(b).get("name") or J(rq(inh, "GET", "/api/service/sicherungen")[1])["liste"][0]["name"]
n_vor = len(J(rq(inh, "GET", "/api/kunden")[1]))
for i in range(5): rq(inh, "POST", "/api/kunden", {"kurzname": f"Nach Sicherung {i}"})
pdfs = sorted(glob.glob(D + "/belege/*/*.pdf")); weg = pdfs[-1]; os.remove(weg)
t0 = time.time(); s, b, _ = rq(inh, "POST", "/api/service/ruecksichern", {"name": name, "grund": "Test der Rücksicherung"}); print("Rücksicherung", s, b[:200], round(time.time() - t0, 1), "s")
time.sleep(1); inh = login()
print("Kunden vorher/nachher:", n_vor, len(J(rq(inh, "GET", "/api/kunden")[1])), "| gelöschtes PDF wieder da:", os.path.exists(weg))
pr = J(rq(inh, "GET", "/api/service/protokoll?voll=1")[1]); print("Protokoll nach Rücksicherung:", pr["pruefung"]["ok"], [e["text"][:70] for e in pr["eintraege"][:2]])
# 3 beschädigte Datenbank
os.kill(pid(), signal.SIGTERM); time.sleep(1.5)
for x in ("-wal", "-shm"):
    if os.path.exists(db + x): os.remove(db + x)
g = os.path.getsize(db)
with open(db, "r+b") as f:
    f.seek(g // 3); f.write(os.urandom(60000))
print("DB beschädigt. Neustart:", start())
print(open(T + "/log.txt").read()[-700:])
o = cl(); s, b, _ = rq(o, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}); print("Anmeldung:", s, b[:200])
s, b, _ = rq(o, "GET", "/api/start"); print("Start:", s, b[:200]); s, b, _ = rq(o, "GET", "/api/auftraege"); print("Aufträge:", s, b[:160])
s, b, _ = rq(o, "GET", "/api/einstellungen"); print("Warnung:", s, (J(b).get("_ort_warnung") if s == 200 else b)[:300])
