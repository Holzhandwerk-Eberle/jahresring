import json, re, sys, base64, time, os, sqlite3, glob, hashlib, shutil
from datetime import date, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    return j
def prot_letzte(n=6):
    pr = A("GET", "service/protokoll"); return [(e.get("art"), e.get("text", "")[:150]) for e in (pr.get("eintraege") or [])[-n:]]
def pruefung():
    pr = A("GET", "service/protokoll?voll=1"); return pr.get("pruefung", {}), [f for f in (pr.get("belege", {}).get("fehler") or []) if "2026-0051" not in f and "2026-0052" not in f]
con = sqlite3.connect(D + "/buero.db", timeout=20); con.row_factory = sqlite3.Row
trig = [(r[0], r[1]) for r in con.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'")]; print("Trigger:", [t[0] for t in trig])
pr, bf = pruefung(); print("Ausgangslage:", pr.get("ok"), {k_: v for k_, v in pr.items() if k_ != "ok"}, bf[:2])
mitte = con.execute("SELECT * FROM protokoll WHERE art='festschreiben' ORDER BY nr DESC LIMIT 1").fetchone(); letzte = con.execute("SELECT * FROM protokoll ORDER BY nr DESC LIMIT 1").fetchone()
for n_, _ in trig: con.execute(f"DROP TRIGGER {n_}")
con.commit()
con.execute("UPDATE protokoll SET text=replace(text, 'brutto', 'BRUTTO') WHERE nr=?", (mitte["nr"],)); con.commit(); pr, bf = pruefung(); print("c) Schutz-Trigger entfernt, Protokolltext geändert →", pr.get("ok"), str({k_: v for k_, v in pr.items() if k_ != "ok"})[:260])
con.execute("UPDATE protokoll SET text=? WHERE nr=?", (mitte["text"], mitte["nr"])); con.commit()
pcols = [r[1] for r in con.execute("PRAGMA table_info(protokoll)")]
kopie = [tuple(r) for r in con.execute("SELECT * FROM protokoll WHERE nr>=?", (letzte["nr"] - 1,))]
con.execute("DELETE FROM protokoll WHERE nr>=?", (letzte["nr"] - 1,)); con.commit(); pr, bf = pruefung(); print("d) die letzten zwei Protokollzeilen gelöscht →", pr.get("ok"), str({k_: v for k_, v in pr.items() if k_ != "ok"})[:300])
con.executemany(f"INSERT INTO protokoll VALUES ({','.join('?' * len(pcols))})", kopie); con.commit()
for _, sql in trig: con.execute(sql)
con.commit(); pr, bf = pruefung(); print("wiederhergestellt:", pr.get("ok"), bf[:2], "| Trigger:", [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'")])
print("Journal-Datei:", [(os.path.basename(f), os.path.getsize(f)) for f in glob.glob(D + "/protokoll/*")])
print("\n== 4. Zahlungseingang löschen, Stammdaten ändern: Spur im Protokoll?")
rid = con.execute("SELECT id FROM belege WHERE art='rechnung' AND status='fest' ORDER BY id DESC LIMIT 1").fetchone()[0]
ops = A("GET", "offeneposten"); op = [o for o in (ops.get("liste") or ops.get("posten") or []) if o.get("beleg_id") == rid][0]
z = A("POST", f"offeneposten/{op['id']}/zahlung", {"datum": date.today().isoformat(), "betrag": 500, "art": "Bar"}); zl = A("GET", f"offeneposten/{op['id']}/zahlungen")["liste"]; print("  Zahlung gebucht:", z["_s"], z.get("fehler", ""), [(x.get("betrag"), x.get("art"), x.get("datum")) for x in zl])
if zl:
    r = A("DELETE", f"zahlungseingaenge/{zl[0]['id']}"); print("  Zahlung gelöscht:", r["_s"], r.get("fehler", "")[:80], "| Protokoll:", [p for p in prot_letzte(4) if "ahlung" in p[1]][-2:])
def n(): return len(A("GET", "service/protokoll?limit=5000").get("eintraege") or [])
n0 = con.execute("SELECT MAX(nr) FROM protokoll").fetchone()[0]
li = A("POST", "lieferanten", {"kurzname": "Holz AG Test", "iban": "DE02120300000000202051"}); r = A("PUT", f"lieferanten/{li['id']}", {"iban": "DE89370400440532013000"}); print("  IBAN Lieferant geändert:", r["_s"])
A("PUT", "einstellungen", {"sepa_iban": "DE89370400440532013000"}); A("PUT", "einstellungen", {"sepa_iban": "DE02120300000000202051"}); A("PUT", "einstellungen", {"ust": 16}); A("PUT", "einstellungen", {"ust": 19})
k = con.execute("SELECT id FROM kunden ORDER BY id DESC LIMIT 1").fetchone()[0]; A("PUT", f"kunden/{k}", {"ust": 7, "strasse": "Anders"}); A("PUT", f"kunden/{k}", {"ust": 19})
con.close(); con = sqlite3.connect(D + "/buero.db", timeout=20); con.row_factory = sqlite3.Row
print("  neue Protokollzeilen:", [(r["art"], r["text"][:110]) for r in con.execute("SELECT art, text FROM protokoll WHERE nr>?", (n0,))] or "KEINE")
print("  Arten im Protokoll insgesamt:", sorted({r[0] for r in con.execute("SELECT DISTINCT art FROM protokoll")}))
print("\n== 5. Datumslogik beim Festschreiben")
a = con.execute("SELECT auftrag_id FROM belege WHERE id=?", (rid,)).fetchone()[0]
for dat, was in (((date.today() - timedelta(days=400)).isoformat(), "Vorjahr"), ((date.today() + timedelta(days=60)).isoformat(), "in 60 Tagen")):
    x = A("POST", f"auftraege/{a}/belege", {"art": "rechnung"}); r1 = A("PUT", f"belege/{x['id']}", {"datum": dat}); f = A("POST", f"belege/{x['id']}/festschreiben", {}, h={"X-Rueckfrage": "1"})
    print("  Rechnungsdatum %s (%s): setzen %s, festschreiben %s %s %s" % (dat, was, r1["_s"], f["_s"], (f.get("beleg") or f).get("nummer", ""), json.dumps({k_: v for k_, v in f.items() if k_ in ("fehler", "frage", "rueckfrage", "fragen", "hinweis")}, ensure_ascii=False)[:230]))
    if f["_s"] != 200: print("     löschen:", A("DELETE", f"belege/{x['id']}")["_s"])
print("\n== 6. Versandtes Angebot ändern")
bid = con.execute("SELECT id FROM belege WHERE art='angebot' AND IFNULL(versendet,'')<>'' ORDER BY id DESC LIMIT 1").fetchone()
if bid:
    bid = bid[0]; b0 = A("GET", f"belege/{bid}"); pdf = con.execute("SELECT pdf FROM belege WHERE id=?", (bid,)).fetchone()[0]; h0 = hashlib.sha256(open(pdf, "rb").read()).hexdigest()[:12] if pdf and os.path.isfile(pdf) else None
    r = A("PUT", f"belege/{bid}", {"einleitung": "Nachträglich geänderter Text"}); print("  Einleitung des versandten Angebots ändern:", r["_s"], r.get("fehler", "")[:140])
    r2 = A("POST", f"belege/{bid}/aktualisieren", {}); print("  Positionen neu übernehmen:", r2["_s"], r2.get("fehler", "")[:140])
    rq(inh, "GET", f"/druck/{bid}.pdf", roh=True); h1 = hashlib.sha256(open(pdf, "rb").read()).hexdigest()[:12] if pdf and os.path.isfile(pdf) else None
    b1 = A("GET", f"belege/{bid}"); print("  netto vorher/nachher:", b0.get("netto"), b1.get("netto"), "| Archiv-PDF vorher/nachher:", h0, h1, "→", "ÜBERSCHRIEBEN" if h0 != h1 else "unverändert", "| Dateien:", [os.path.basename(x) for x in glob.glob(os.path.dirname(pdf) + "/" + b0["nummer"] + "*")])
    r3 = A("DELETE", f"belege/{bid}"); print("  Versandtes Angebot löschen:", r3["_s"], r3.get("fehler", "")[:140])
src = open("/home/claude/eberle-buero/app.py", encoding="utf-8").read()
print("\n== 7. Zahlarten:", sorted(set(re.findall(r'"(Bar|Überweisung|EC|Karte|Scheck|Lastschrift|PayPal|Barzahlung|bar)"', src))), "| Kassenbuch:", "kassenbuch" in src.lower())
