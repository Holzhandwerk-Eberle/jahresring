import json, sys, threading, sqlite3, glob, os, time
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim123", "passwort2": "geheim123"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
rq(inh, "PUT", "/api/einstellungen", {"firma": "Muster", "firma_anschrift": "Hauptstr. 1\n88069 Tettnang", "steuernummer": "12/345/67890", "sepa_iban": "DE02120300000000202051"})
J = lambda t: json.loads(t)
k = J(rq(inh, "POST", "/api/kunden", {"kurzname": "Bau GmbH", "firma": "Bau GmbH", "strasse": "Weg 2", "plz": "88045", "ort": "FN"})[1])
def rechnung(preis=100):
    a = J(rq(inh, "POST", "/api/auftraege", {"kunde_id": k["id"], "bezeichnung": "T"})[1])
    p = J(rq(inh, "POST", f"/api/auftraege/{a['id']}/positionen", {"text": "Tisch"})[1]); pid = p.get("id") or p["position"]["id"]
    rq(inh, "PUT", f"/api/positionen/{pid}", {"einzelpreis": preis, "preis_manuell": 1})
    return a["id"], pid, J(rq(inh, "POST", f"/api/auftraege/{a['id']}/belege", {"art": "rechnung"})[1])["id"]
aid, pid, bid = rechnung()
s, b, _ = rq(inh, "POST", f"/api/belege/{bid}/festschreiben", {}); fb = J(b); print("fest", s, fb.get("nummer"), fb.get("brutto"))
print("ändern:", rq(inh, "PUT", f"/api/belege/{bid}", {"betreff": "x", "datum": "2020-01-01"})[1][:70])
print("löschen:", rq(inh, "DELETE", f"/api/belege/{bid}")[1][:90])
rq(inh, "PUT", f"/api/positionen/{pid}", {"einzelpreis": 999}); print("nach Positionsänderung brutto:", J(rq(inh, "GET", f"/api/belege/{bid}")[1])["brutto"])
print("Auftrag löschen:", rq(inh, "DELETE", f"/api/auftraege/{aid}")[1][:80]); print("Kunde löschen:", rq(inh, "DELETE", f"/api/kunden/{k['id']}")[1][:80])
print("nochmal fest:", rq(inh, "POST", f"/api/belege/{bid}/festschreiben", {})[1][:60])
# parallele Festschreibung
ids = [rechnung(50 + i)[2] for i in range(8)]; erg = []
def f(i): 
    o = cl(); rq(o, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}); s, b, _ = rq(o, "POST", f"/api/belege/{i}/festschreiben", {}); erg.append((s, J(b).get("nummer") or b[:60]))
th = [threading.Thread(target=f, args=(i,)) for i in ids]; [t.start() for t in th]; [t.join() for t in th]
print("parallel:", sorted(erg))
pr = J(rq(inh, "GET", "/api/service/protokoll?voll=1")[1]); print("Prüfung sauber:", pr["pruefung"]["ok"], pr["belege"])
# Manipulation direkt in der Datenbank und am PDF
db = glob.glob(D + "/*.db")[0]; c = sqlite3.connect(db)
r = c.execute("SELECT daten FROM belege WHERE id=?", (ids[0],)).fetchone(); d = json.loads(r[0])
for z in d["zeilen"]:
    if z.get("typ") == "pos": z["text"] = "manipuliert"
c.execute("UPDATE belege SET daten=? WHERE id=?", (json.dumps(d), ids[0])); c.execute("UPDATE belege SET brutto=brutto+100 WHERE id=?", (ids[1],)); c.commit()
try: c.execute("UPDATE protokoll SET text='x' WHERE nr=2"); print("Protokoll-Update ging durch!")
except Exception as e: print("Protokoll-Update gesperrt:", str(e)[:50])
c.close()
pdfs = sorted(glob.glob(D + "/belege/*/*.pdf")); print(len(pdfs), "Archiv-PDFs"); open(pdfs[0], "ab").write(b"\n%manipuliert"); os.remove(pdfs[1])
pr = J(rq(inh, "GET", "/api/service/protokoll?voll=1")[1]); print("nach Manipulation:", pr["belege"]["ok"]); [print("   ", x) for x in pr["belege"]["fehler"]]
print("Warnung in Einstellungen:", J(rq(inh, "GET", "/api/einstellungen")[1])["_ort_warnung"][:120])
