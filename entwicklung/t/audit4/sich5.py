import json, re, sys, base64, time, io, zipfile
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    return j
print("== Listen nach dem Fuzzing lesbar?")
for p in ("kunden", "auftraege", "lieferanten", "termine?von=2020-01-01&bis=2030-01-01", "material", "werkzeuge", "mitarbeiter", "projekte", "belege", "zahlungen", "start", "suche?q=a", "arbeitsschutz/uebersicht", "offeneposten", "wiedervorlagen", "benutzer", "korrespondenz", "lohn?monat=2026-11", "zeiten?monat=2026-11"):
    x = A("GET", p); print("  %-44s %s %s" % (p, x["_s"], x.get("fehler", "")[:120] if x["_s"] != 200 else len(x["_roh"])))
print("== NaN/Infinity: gespeicherte Werte")
k = A("POST", "kunden", {"kurzname": "NaN-Test2", "plz": "88069", "ort": "Tettnang"}); a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "NaN"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Pos"}); pid = po.get("id") or po["position"]["id"]
print("  Felder der Position:", [k_ for k_ in (po.get("position") or po) if any(w in k_ for w in ("preis", "ep", "gp", "menge", "netto", "summe"))])
for name, roh in (("Infinity", '{"einzelpreis": Infinity, "preis_manuell": 1, "menge": 1}'), ("NaN", '{"einzelpreis": NaN, "preis_manuell": 1, "menge": 1}'), ("1e999", '{"einzelpreis": 1e999, "preis_manuell": 1, "menge": 1}'), ("EP 1e300 × Menge 1e308", '{"einzelpreis": 1e300, "preis_manuell": 1, "menge": 1e308}'), ("EP 1e15 × 3", '{"einzelpreis": 1e15, "preis_manuell": 1, "menge": 3}'), ("EP -500", '{"einzelpreis": -500, "preis_manuell": 1, "menge": 1}'), ("Menge -2", '{"einzelpreis": 10, "preis_manuell": 1, "menge": -2}'), ("EP '12,50' als Text", '{"einzelpreis": "12,50", "preis_manuell": 1, "menge": "2,5"}'), ("EP '1.234,56' Text", '{"einzelpreis": "1.234,56", "preis_manuell": 1, "menge": "1"}'), ("EP '1.234' Text", '{"einzelpreis": "1.234", "preis_manuell": 1, "menge": "1"}'), ("EP '12.5' Text", '{"einzelpreis": "12.5", "preis_manuell": 1, "menge": "1"}')):
    r = urllib.request.Request(U + f"/api/positionen/{pid}", method="PUT", data=roh.encode(), headers={"Content-Type": "application/json"})
    try: x = inh.open(r); s, t = x.status, x.read().decode()
    except urllib.error.HTTPError as e: s, t = e.code, e.read().decode()
    p_ = J(t).get("position") or J(t)
    au = A("GET", f"auftraege/{a['id']}")
    print("  %-24s PUT %s → einzelpreis=%r menge=%r gesamt=%r | Auftrag netto=%r %s" % (name, s, p_.get("einzelpreis"), p_.get("menge"), p_.get("gesamtpreis", p_.get("gp")), au.get("netto", au.get("summe_netto", au.get("summen"))), p_.get("fehler", "")[:80]))
A("PUT", f"positionen/{pid}", {"einzelpreis": 1e15, "preis_manuell": 1, "menge": 3})
b = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"}); print("  Angebot über 3 Billiarden:", b["_s"], b.get("netto"), b.get("brutto"), b.get("fehler", ""))
s, t, _ = rq(inh, "GET", f"/druck/{b.get('id')}"); print("  Druckansicht:", s, re.findall(r"[\d.]{12,},\d\d", t)[:3])
