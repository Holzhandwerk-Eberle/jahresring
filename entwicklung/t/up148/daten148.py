# Daten im Programmstand 148 anlegen (nach neu148.sh + t10.js): danach wird auf 149 aktualisiert und geprüft
import sys, json, base64, urllib.request, http.cookiejar
from datetime import datetime, timedelta
sys.path.insert(0, "/tmp/claude-0/t/bank"); import camt
U = "http://127.0.0.1:8799"
def sitzung():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def A(o, m, p, d=None):
    r = urllib.request.Request(U + "/api/" + p, method=m, data=json.dumps(d).encode() if d is not None else None, headers={"Content-Type": "application/json", "Origin": U})
    try:
        t = o.open(r, timeout=120).read().decode(); return json.loads(t) if t else {}
    except urllib.error.HTTPError as e:
        print("FEHLER", m, p, e.code, e.read().decode()[:200]); return {}
o = sitzung(); print("anmelden", A(o, "POST", "anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}).get("ok"))
print("version", A(o, "GET", "version").get("version"))
k = A(o, "GET", "kunden?status=alle")[0]
A(o, "PUT", "einstellungen", {"sepa_iban": "DE02120300000000202051", "firma": "Holzhandwerk Muster", "firma_anschrift": "Weg 1\n88069 Tettnang", "steuernummer": "12/345/67890"})
l = A(o, "POST", "lieferanten", {"kurzname": "Holz Müller", "firma": "Holz Müller GmbH", "strasse": "Sägeweg 2", "plz": "88069", "ort": "Tettnang", "iban": "DE44500105175407324931"})
a2 = A(o, "POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Einbauschrank Flur"})
p = A(o, "POST", f"auftraege/{a2['id']}/positionen", {"text": "Einbauschrank, Eiche furniert"}); pid = p.get("id") or p["position"]["id"]
A(o, "PUT", f"positionen/{pid}", {"einzelpreis": 2400, "preis_manuell": 1, "menge": 0.5})
an = A(o, "POST", f"auftraege/{a2['id']}/belege", {"art": "angebot"}); print("angebot", an.get("id"), A(o, "POST", f"belege/{an['id']}/versendet", {"weg": "Post"}).get("ok"))
re = A(o, "POST", f"auftraege/{a2['id']}/belege", {"art": "rechnung"}); f = A(o, "POST", f"belege/{re['id']}/festschreiben", {}); b = A(o, "GET", f"belege/{re['id']}")
print("rechnung", re.get("id"), b.get("nummer"), b.get("status"), b.get("brutto"))
z = A(o, "POST", "zahlungen", {"lieferant_id": l.get("id"), "belegnr": "R-4711", "betrag": 357.0, "vorsteuer": 19, "faellig": "2026-11-30"})
ein = [camt.ntry(float(b.get("brutto") or 1428.0), "CRDT", "Kunde Test", "DE89370400440532013000", f"Rechnung {b.get('nummer')}", ref="R1", datum="2026-11-10"),
       camt.ntry(357.0, "DBIT", "Holz Müller GmbH", "DE44500105175407324931", "R-4711", ref="NONREF", datum="2026-11-11"),
       camt.ntry(42.5, "DBIT", "Stadtwerke", "DE12500105170648489890", "Abschlag Strom", ref="R3", datum="2026-11-12")]
roh = camt.datei(ein, anfang=1000.0, ende=1000.0 + float(b.get("brutto") or 1428.0) - 357.0 - 42.5)
open("/tmp/claude-0/t/up148/auszug.xml", "wb").write(roh)
r = A(o, "POST", "bank/einlesen", {"daten": base64.b64encode(roh).decode(), "dateiname": "auszug_11.xml"}); print("auszug", r.get("neu"), r.get("doppelt"))
ma = A(o, "POST", "mitarbeiter", {"vorname": "Max", "nachname": "Werk", "lohnart": "stunde", "stundenlohn": 15.0, "eintritt": "2026-01-01"}); mid = ma.get("id") or ma.get("mitarbeiter", {}).get("id")
print("benutzer", A(o, "POST", "benutzer", {"name": "Max", "login": "max", "passwort": "1234", "rolle": "mitarbeiter", "mitarbeiter_id": mid}).get("id"))
m = sitzung(); print("max anmelden", A(m, "POST", "anmeldung/anmelden", {"login": "max", "passwort": "1234"}).get("ok"))
jetzt = datetime.now(); iso = lambda t: t.strftime("%Y-%m-%dT%H:%M")
print("stempel", A(m, "POST", "stempel", {"aktion": "start", "zeit": iso(jetzt - timedelta(hours=2)), "client_id": "u1"}).get("ok"), A(m, "POST", "stempel", {"aktion": "ende", "zeit": iso(jetzt - timedelta(minutes=30)), "client_id": "u2"}).get("ok"))
pr = A(o, "GET", "service/protokoll?voll=1"); print("protokoll", pr.get("pruefung", {}).get("ok"), {x: pr.get("belege", {}).get(x) for x in ("ok", "geprueft", "fehler", "ohne_protokoll")})
