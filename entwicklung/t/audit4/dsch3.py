import json, re, sys, base64, time, os, sqlite3
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    return j
def pruefung(text):
    pr = A("GET", "service/protokoll?voll=1"); print(f"  {text}: Protokoll {pr.get('pruefung', {}).get('ok')} | Belege ok={pr.get('belege', {}).get('ok')}"); 
    for f in (pr.get("belege", {}).get("fehler") or []): 
        if "2026-0051" not in f: print("      ", f[:200])
k = A("POST", "kunden", {"kurzname": "Zweittest, Anna", "nachname": "Zweittest", "plz": "88099", "ort": "Neukirch"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Regal"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Regal"}); pid = po.get("id") or po["position"]["id"]; A("PUT", f"positionen/{pid}", {"einzelpreis": 300, "preis_manuell": 1, "menge": 1})
b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); f = A("POST", f"belege/{b['id']}/festschreiben", {}); nr = (f.get("beleg") or f).get("nummer"); print("Rechnung", nr)
rq(inh, "GET", f"/druck/{b['id']}.pdf", roh=True)
ops = A("GET", "offeneposten"); op = [o for o in (ops.get("liste") or ops.get("posten") or []) if o.get("kunde_id") == k["id"]][0]
A("POST", f"offeneposten/{op['id']}/zahlung", {"datum": "2026-11-17", "betrag": op["offen"], "art": "Überweisung"})
pruefung("A nach dem Anlegen")
# nur die Frist verkürzen: Aufbewahren-bis gibt es am Kunden; hier stattdessen den Kunden als Inhaber prüfen lassen, ohne Belegdaten anzufassen
info = A("GET", f"kunden/{k['id']}/anonymisieren"); print("  Vorschau ohne Zurückdatieren:", {x: info.get(x) for x in ("frist_ende", "erlaubt", "offene_posten")})
erg = A("POST", f"kunden/{k['id']}/anonymisieren", {}); print("  Anonymisieren vor Fristablauf:", erg["_s"], erg.get("fehler", "")[:120])
# Frist umgehen wie es nach 10 Jahren wäre: Systemzeit lässt sich nicht stellen, daher nur das Belegdatum in der DB ändern und danach zurückstellen
con = sqlite3.connect(D + "/buero.db", timeout=20)
alt = con.execute("SELECT datum FROM belege WHERE id=?", (b["id"],)).fetchone()[0]
con.execute("UPDATE belege SET datum='2013-03-05' WHERE id=?", (b["id"],)); con.commit()
erg = A("POST", f"kunden/{k['id']}/anonymisieren", {}); print("  Anonymisieren (Datum kurz zurückgestellt):", erg["_s"], erg.get("fehler", "")[:120], erg.get("erledigt"))
con.execute("UPDATE belege SET datum=? WHERE id=?", (alt, b["id"])); con.commit(); con.close()
pruefung("B nach dem Anonymisieren (Belegdatum wieder original)")
bb = A("GET", f"belege/{b['id']}"); print("  Beleg danach: status", bb.get("status"), "| anschrift:", repr(bb.get("anschrift"))[:60], "| PDF-Abruf:", rq(inh, "GET", f"/druck/{b['id']}.pdf", roh=True)[0])
pruefung("C nach erneutem PDF-Abruf")
