exec(open("/tmp/claude-0/t/sec/ausfall.py").read().split("inh = login(); db =")[0])
inh = login(); db = glob.glob(D + "/*.db")[0]
aid = J(rq(inh, "GET", "/api/auftraege")[1])[0]["id"]
print("Echtbetrieb:", rq(inh, "POST", "/api/service/echtbetrieb", {"bestaetigung": "ECHTBETRIEB"})[0])
subprocess.run(["python3", "-c", "import app; app.stunden_sicherung(); print('Zwischensicherung erstellt')"], cwd=T + "/eberle-buero")
# nach der Zwischensicherung noch eine Rechnung festschreiben – die geht beim Ausfall verloren
bid = J(rq(inh, "POST", f"/api/auftraege/{aid}/belege", {"art": "rechnung"})[1])["id"]; fb = J(rq(inh, "POST", f"/api/belege/{bid}/festschreiben", {})[1]); print("fest nach Sicherung:", (fb.get("beleg") or fb).get("nummer"))
os.kill(pid(), signal.SIGTERM); time.sleep(1.5)
for x in ("-wal", "-shm"):
    if os.path.exists(db + x): os.remove(db + x)
with open(db, "r+b") as f:
    f.seek(os.path.getsize(db) // 3); f.write(os.urandom(60000))
os.environ["BUERO_NOTFALL"] = "nein"; print("Neustart ohne Zustimmung:", start()); print("  ", open(T + "/log.txt").read()[-330:].replace("\n", " | "))
os.environ["BUERO_NOTFALL"] = "ja"; print("Neustart mit Zustimmung:", start())
o = login(); e = J(rq(o, "GET", "/api/einstellungen")[1]); print("Hinweis:", e["_ort_warnung"][:330])
pr = J(rq(o, "GET", "/api/service/protokoll?voll=1")[1]); print("Protokoll ok:", pr["pruefung"]["ok"], "| Belegprüfung:"); [print("   ", x) for x in pr["belege"]["fehler"][:6]]
print(os.listdir(D + "/beschaedigt"))
