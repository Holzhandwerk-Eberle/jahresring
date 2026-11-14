import json, glob, os
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {"_roh": t[:200]}
c = cl(); rq(c, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None):
    s, b, _ = rq(c, m, "/api/" + p, d); j = J(b)
    return {"FEHLER": j.get("fehler", b[:100]), "code": s} if s >= 400 and isinstance(j, dict) else j
def ok(b, t): print(("ok   " if b else "FEHLER ") + t)
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
k1 = A("POST", "kunden", {"kurzname": "Kölbl echt"}); k2 = A("POST", "kunden", {"kurzname": "Testkunde"})
def auftrag(k, bez, art="angebot"):
    a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": bez}); po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Tisch"}); pid = po.get("id") or po["position"]["id"]
    A("PUT", f"positionen/{pid}", {"einzelpreis": 1144.73, "preis_manuell": 1}); b = A("POST", f"auftraege/{a['id']}/belege", {"art": art})
    A("POST", "termine", {"auftrag_id": a["id"], "typ": "Montage", "von": "2027-02-15", "bis": "2027-02-16"}); A("POST", "notizen", {"auftrag_id": a["id"], "text": "Notiz " + bez})
    return a, pid, b
echt, pe, be = auftrag(k1, "Tischplatte echt"); test, pt, bt = auftrag(k2, "Testauftrag")
vor = A("GET", "service/testdaten"); ok(len(vor["auftraege"]) >= 2 and vor["fest"] >= 1, f"Vorschau: {len(vor['auftraege'])} Aufträge, {vor['fest']} festgeschriebene Belege, Protokoll {vor['protokoll']}")
ok(A("POST", "service/echtbetrieb", {"bestaetigung": "ECHTBETRIEB", "protokoll_neu": True}).get("code") == 400, "Protokoll neu beginnen bei vorhandenen Testrechnungen abgelehnt")
r = A("POST", "service/testdaten", {"gruppen": ["auftraege", "zahlungen", "personal", "kunden", "termine"], "bestaetigung": "LÖSCHEN", "behalten": [echt["id"], 99999, "x"]})
print("     ", json.dumps(r, ensure_ascii=False)[:300])
ok(r.get("behalten") == [echt["nummer"]], "Rückmeldung nennt den behaltenen Auftrag")
al = A("GET", "auftraege"); ok([a["id"] for a in al] == [echt["id"]], f"nur der behaltene Auftrag ist noch da ({[a['nummer'] for a in al]})")
pos = A("GET", f"auftraege/{echt['id']}/positionen"); ok(len(pos["positionen"]) == 1 and abs(pos["netto"] - 1144.73) < 0.01, "Positionen und Kalkulation erhalten")
bl = A("GET", f"auftraege/{echt['id']}/belege"); ok(len(bl) == 1 and bl[0]["id"] == be["id"], "Angebot erhalten")
kl = A("GET", "kunden?status=alle"); ok([x["kurzname"] for x in kl] == ["Kölbl echt"], f"nur der Kunde des behaltenen Auftrags bleibt ({[x['kurzname'] for x in kl]})")
kal = A("GET", "kalender?von=2027-02-01&bis=2027-02-28"); ok(len(kal["termine"]) == 1 and kal["termine"][0]["auftrag_id"] == echt["id"], "Termin des behaltenen Auftrags erhalten, der andere weg")
h = A("GET", f"auftraege/{echt['id']}/historie"); ok("Notiz Tischplatte echt" in json.dumps(h, ensure_ascii=False), "Notiz erhalten")
ok(A("GET", "belege") and all(b["auftrag_id"] == echt["id"] for b in A("GET", "belege")), "keine fremden Belege mehr")
neu = A("POST", "auftraege", {"kunde_id": k1["id"], "bezeichnung": "danach"}); ok(neu["nummer"] > echt["nummer"], f"neue Auftragsnummer zählt weiter: {echt['nummer']} → {neu['nummer']}")
vor = A("GET", "service/testdaten"); ok(vor["fest"] == 0, "keine festgeschriebenen Rechnungen mehr")
n_alt = vor["protokoll"]
r = A("POST", "service/echtbetrieb", {"bestaetigung": "ECHTBETRIEB", "protokoll_neu": True}); ok("echtbetrieb" in r and r["echtbetrieb"], "Echtbetrieb gestartet")
pr = A("GET", "service/protokoll"); print("     ", pr["eintraege"][-1]["text"][:330] if pr["eintraege"] else "")
ok(len(pr["eintraege"]) <= 3 and any(e["art"] == "echtbetrieb" for e in pr["eintraege"]) and pr["pruefung"]["ok"], f"Protokoll neu begonnen ({n_alt} → {len(pr['eintraege'])} Einträge), Kette in Ordnung")
ok(len(glob.glob(D + "/protokoll/journal_testphase_*.jsonl")) == 1 and os.path.getsize(glob.glob(D + "/protokoll/journal_testphase_*.jsonl")[0]) > 100, "Protokolldatei der Testphase liegt umbenannt im Datenordner")
ok(A("POST", "service/testdaten", {"gruppen": ["auftraege"], "bestaetigung": "LÖSCHEN"}).get("code") == 403, "danach ist Testdaten löschen gesperrt")
a2, p2, b2 = auftrag(k1, "Echte Rechnung", "rechnung"); f = A("POST", f"belege/{b2['id']}/festschreiben", {}); ok(bool(f.get("beleg", {}).get("nummer")), "erste echte Rechnung: " + str(f.get("beleg", {}).get("nummer")))
pr = A("GET", "service/protokoll?voll=1"); ok(pr["pruefung"]["ok"] and pr["belege"]["ok"], "Protokoll- und Belegprüfung nach dem Neubeginn in Ordnung")
