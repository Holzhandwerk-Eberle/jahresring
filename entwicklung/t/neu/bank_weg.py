"""Eingelesenen Kontoauszug wieder entfernen: nur ohne gebuchte Umsätze, nur Inhaber, Überschneidungen bleiben erhalten, Protokoll."""
import json, base64, sys, os
sys.path.insert(0, "/tmp/claude-0/t/bank")
from camt import ntry, datei
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
if len(sys.argv) > 1: U = sys.argv[1]
DATEN = sys.argv[2] if len(sys.argv) > 2 else "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:400]))
    if not bed: fehler.append(name)
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, c=None):
    s, b, _ = rq(c or inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    return j
A("PUT", "einstellungen", {"firma": "Muster", "sepa_iban": "DE02120300000000202051"})
def lesen(name, eintraege, ende, **kw):
    return A("POST", "bank/einlesen", {"dateiname": name, "daten": base64.b64encode(datei(eintraege, 1000, ende, **kw)).decode()})
e_a = [ntry(100, "CRDT", "Anna", "DE44500105175407324931", "Zahlung A", ref="A1", datum="2026-11-03"), ntry(20, "DBIT", "Bank", "", "Entgelt", ref="A2", datum="2026-11-04"),
       ntry(55, "DBIT", "Strom AG", "", "Abschlag", ref="A3", datum="2026-11-05")]
e_b = e_a[1:] + [ntry(70, "CRDT", "Bert", "", "Zahlung B", ref="B1", datum="2026-11-08")]   # überschneidet sich mit A in zwei Umsätzen
ra = lesen("woche1.xml", e_a, 1025, von="2026-11-01", bis="2026-11-05")
rb = lesen("woche2.xml", e_b, 1095, von="2026-11-04", bis="2026-11-09")
ok("zwei Dateien eingelesen (zweite: 1 neu, 2 schon vorhanden)", ra.get("neu") == 3 and rb.get("neu") == 1 and rb.get("doppelt") == 2, (ra, rb))
d = A("GET", "bank?status=alle"); fs = d.get("dateien", [])
ok("Liste der eingelesenen Dateien mit Umsatzzahl", len(fs) == 2 and fs[0]["datei"] == "woche2.xml" and fs[0]["umsaetze"] == 1 and fs[1]["umsaetze"] == 3 and fs[1]["gebucht"] == 0, fs)
ablage_a = [f for f in os.listdir(os.path.join(DATEN, "bank", str(__import__("datetime").date.today().year))) if "woche1" in f]
ok("Originaldatei liegt in der Ablage", len(ablage_a) == 1, ablage_a)
# gebuchter Umsatz sperrt
u_strom = [u for u in d["umsaetze"] if u["name"] == "Strom AG"][0]
sk = A("GET", "sachkonten"); sk = sk if isinstance(sk, list) else sk.get("konten", [])
r = A("POST", f"bank/{u_strom['id']}/konto", {"konto": str(sk[0].get("nummer") or sk[0].get("konto")), "notiz": "Strom"}); ok("Umsatz auf Konto gebucht", r["_s"] == 200, r)
fa = [f for f in A("GET", "bank?status=alle")["dateien"] if f["datei"] == "woche1.xml"][0]
ok("Datei zeigt 1 gebuchten Umsatz", fa["gebucht"] == 1, fa)
r = A("DELETE", f"bank/auszuege/{fa['id']}"); ok("Entfernen gesperrt, solange ein Umsatz gebucht ist", r["_s"] == 409 and "Zurückholen" in r.get("fehler", ""), r)
ok("nichts gelöscht", len(A("GET", "bank?status=alle")["umsaetze"]) == 4)
A("POST", f"bank/{u_strom['id']}/loesen", {})
# Rechte
b = A("POST", "benutzer", {"name": "Büro", "login": "buero", "passwort": "buerobuero991", "rolle": "buero"}); w = cl(); rq(w, "POST", "/api/anmeldung/anmelden", {"login": "buero", "passwort": "buerobuero991"})
r = A("DELETE", f"bank/auszuege/{fa['id']}", c=w); ok("Entfernen nur durch den Inhaber", r["_s"] == 403, r)
r = A("DELETE", "bank/auszuege/99999"); ok("unbekannte Datei: 404", r["_s"] == 404, r)
# Entfernen der ersten Datei: ihre drei Umsätze weg, die zwei auch in Datei 2 enthaltenen bleiben erhalten
r = A("DELETE", f"bank/auszuege/{fa['id']}"); ok("Datei 1 entfernt", r["_s"] == 200 and r.get("umsaetze") == 3 and r.get("wieder_angelegt") == 2, r)
d = A("GET", "bank?status=alle"); namen = sorted(u["name"] for u in d["umsaetze"])
ok("übrig: Umsätze der Datei 2 vollständig (Bank, Strom AG, Bert), Anna weg", namen == ["Bank", "Bert", "Strom AG"], namen)
ok("Datei 2 zählt jetzt 3 Umsätze, nichts mehr doppelt", len(d["dateien"]) == 1 and d["dateien"][0]["umsaetze"] == 3 and d["dateien"][0]["doppelt"] == 0, d["dateien"])
ok("Kontostand kommt aus der verbliebenen Datei", d["kontostand"] and abs(d["kontostand"]["saldo_ende"] - 1095) < 0.01, d["kontostand"])
ok("Originaldatei aus der Ablage entfernt", not [f for f in os.listdir(os.path.join(DATEN, "bank", str(__import__("datetime").date.today().year))) if "woche1" in f])
pr = A("GET", "service/protokoll"); ein = [x for x in pr.get("eintraege", []) if x["art"] == "bank_entfernt"]
ok("Entfernen steht im Protokoll", len(ein) == 1 and "woche1.xml" in ein[0]["text"] and "3 Umsätze" in ein[0]["text"], ein)
# erneut einlesen geht, danach ganz entfernen
ra2 = lesen("woche1.xml", e_a, 1025, von="2026-11-01", bis="2026-11-05"); ok("Datei 1 lässt sich erneut einlesen (1 neu, 2 schon vorhanden)", ra2.get("neu") == 1 and ra2.get("doppelt") == 2, ra2)
for f in A("GET", "bank?status=alle")["dateien"]:
    A("DELETE", f"bank/auszuege/{f['id']}")
d = A("GET", "bank?status=alle"); ok("alle Dateien entfernt: keine Umsätze, kein Kontostand", d["umsaetze"] == [] and d["dateien"] == [] and not d["kontostand"], d)
print("FEHLER:", fehler); sys.exit(1 if fehler else 0)
