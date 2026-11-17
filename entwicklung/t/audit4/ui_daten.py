# Zusatzdaten für die Vermessung der Oberfläche (nach neu.sh + t10.js): Lieferant, zweiter Auftrag, Kontoauszug mit Hinweis, Zahlungsauftrag
import sys, json, base64
sys.path.insert(0, "/tmp/claude-0/t/bank"); import camt
import urllib.request, http.cookiejar
U = "http://127.0.0.1:8799"
o = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def A(m, p, d=None):
    r = urllib.request.Request(U + "/api/" + p, method=m, data=json.dumps(d).encode() if d is not None else None, headers={"Content-Type": "application/json", "Origin": U})
    try:
        return json.loads(o.open(r, timeout=120).read().decode())
    except urllib.error.HTTPError as e:
        print("FEHLER", m, p, e.code, e.read().decode()[:200]); return {}
print("anmelden", A("POST", "anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}).get("ok"))
k = A("GET", "kunden?status=alle")[0]
l = A("POST", "lieferanten", {"kurzname": "Holz Müller", "firma": "Holz Müller GmbH", "strasse": "Sägeweg 2", "plz": "88069", "ort": "Tettnang", "iban": "DE44500105175407324931"})
print("lieferant", l.get("id"))
a2 = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Einbauschrank Flur"})
p = A("POST", f"auftraege/{a2['id']}/positionen", {"text": "Einbauschrank, Eiche furniert"})
pid = p.get("id") or p["position"]["id"]; A("PUT", f"positionen/{pid}", {"einzelpreis": 2400, "preis_manuell": 1})
b = A("POST", f"auftraege/{a2['id']}/belege", {"art": "angebot"}); print("beleg", b.get("id"))
z = A("POST", "zahlungen", {"lieferant_id": l.get("id"), "belegnr": "R-4711", "betrag": 357.0, "vorsteuer": 19, "faellig": "2026-11-30"}); print("zahlung", z.get("id"))
ein = [camt.ntry(119.0, "CRDT", "Erika Muster", "DE89370400440532013000", "Rechnung 2026-0001", ref="R1", datum="2026-11-10"),
       camt.ntry(357.0, "DBIT", "Holz Müller GmbH", "DE44500105175407324931", "R-4711", ref="R2", datum="2026-11-11"),
       camt.ntry(42.5, "DBIT", "Stadtwerke", "DE12500105170648489890", "Abschlag Strom", ref="R3", datum="2026-11-12")]
r = A("POST", "bank/einlesen", {"daten": base64.b64encode(camt.datei(ein, anfang=1000.0, ende=999.0)).decode(), "dateiname": "auszug_11.xml"})
print("auszug", {x: r.get(x) for x in ("neu", "hinweise")})
