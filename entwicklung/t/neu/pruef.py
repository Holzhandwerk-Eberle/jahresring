"""Prüfungen zu Version -140: Rückfragen, Eingangsrechnung (IBAN, Summen, Fingerabdruck), Rechnungsdatum, Zahlungen, Lager, Termine, gleichzeitiges Bearbeiten."""
import json, base64, sys, os
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
if len(sys.argv) > 1: U = sys.argv[1]
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
FR = {"X-Rueckfrage": "1"}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:300]))
    if not bed: fehler.append(name)
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
s, _, _ = rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"}); ok("Anmeldung", s == 200, s)
def A(m, p, d=None, h=None):
    s, b, hd = rq(inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_h"] = hd
    return j
A("PUT", "einstellungen", {"firma": "Holz Lieferant GmbH", "firma_anschrift": "Weg 1\n88069 Tettnang", "firma_email": "a@b.de", "firma_telefon": "07542 1", "ustid": "DE123456789", "sepa_iban": "DE02120300000000202051"})
k = A("POST", "kunden", {"kurzname": "Kunde", "nachname": "Kunde", "strasse": "Str 2", "plz": "88069", "ort": "Tettnang", "email": "k@x.de"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Tisch"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Tisch"}); pid = po.get("id") or po["position"]["id"]
A("PUT", f"positionen/{pid}", {"einzelpreis": 100, "preis_manuell": 1, "menge": 1})
def rechnung(datum=None, h=None):
    b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"})
    if datum: A("PUT", f"belege/{b['id']}", {"datum": datum})
    return b["id"], A("POST", f"belege/{b['id']}/festschreiben", {}, h)
from datetime import date, timedelta
heute = date.today()
# --- Rechnungsdatum
bid, r = rechnung(None, FR); ok("Rechnung heute ohne Rückfrage", r["_s"] == 200, r)
b2, r = rechnung((heute + timedelta(days=5 * 365)).isoformat(), FR); ok("Datum in 5 Jahren abgelehnt", r["_s"] == 400 and "Tippfehler" in r.get("fehler", ""), r)
b3, r = rechnung((heute - timedelta(days=45)).isoformat(), FR); ok("45 Tage zurück: Rückfrage", r["_s"] == 409 and r.get("rueckfrage") == "rechnungsdatum", r)
r = A("POST", f"belege/{b3}/festschreiben", {}, {**FR, "X-Bestaetigt": "rechnungsdatum"}); ok("… bestätigt: festgeschrieben", r["_s"] == 200, r)
b4, r = rechnung((heute - timedelta(days=50)).isoformat(), {**FR, "X-Bestaetigt": "rechnungsdatum"}); ok("ohne Rückfrage-Kopf wie bisher möglich (hier bestätigt)", r["_s"] == 200, r)
b5, r = rechnung((heute - timedelta(days=3)).isoformat()); ok("Aufrufer ohne Rückfrage-Fähigkeit: keine Rückfrage", r["_s"] == 200, r)
# --- Zahlungseingang
ops = A("GET", "offeneposten"); liste = ops if isinstance(ops, list) else [v for v in ops.values() if isinstance(v, list)][0]
op = [o for o in liste if abs(o["offen"] - 119) < 0.01][0]
z = lambda d, h=FR: A("POST", f"offeneposten/{op['id']}/zahlung", d, h)
r = z({"betrag": 500, "datum": heute.isoformat()}); ok("Überzahlung: Rückfrage", r["_s"] == 409 and r.get("rueckfrage") == "zahlung", r)
r = z({"betrag": -5, "datum": heute.isoformat()}); ok("negativ: Rückfrage", r["_s"] == 409, r)
r = z({"betrag": 10, "datum": (heute + timedelta(days=9)).isoformat()}); ok("Zukunft: Rückfrage", r["_s"] == 409, r)
r = z({"betrag": 19, "datum": heute.isoformat()}); ok("normale Teilzahlung ohne Rückfrage", r["_s"] == 200, r)
r = z({"betrag": 500, "datum": heute.isoformat()}, {**FR, "X-Bestaetigt": "zahlung"}); ok("Überzahlung bestätigt gebucht", r["_s"] == 200, r)
# --- Eingangsrechnung
s, xml, _ = rq(inh, "GET", f"/api/belege/{bid}/zugferd.xml"); ok("eigene E-Rechnung als Muster", s == 200, xml[:200])
A("PUT", "einstellungen", {"firma": "Muster Schreiner", "ustid": "DE999999999", "sepa_iban": "DE89370400440532013000"})
lf = A("POST", "lieferanten", {"kurzname": "Holz Lieferant", "firma": "Holz Lieferant GmbH", "ustid": "DE123456789", "iban": "DE89370400440532013000"})
lesen = lambda x: A("POST", "eingang/lesen", {"daten": base64.b64encode(x.encode()).decode(), "dateiname": "r.xml"})
e = lesen(xml); ok("abweichende IBAN: Warnung beim Lesen", any("IBAN weicht" in w for w in e.get("warnungen", [])), e.get("warnungen"))
x2 = xml.replace("<ram:GrandTotalAmount>119.00", "<ram:GrandTotalAmount>219.00").replace("<ram:DuePayableAmount>119.00", "<ram:DuePayableAmount>219.00")
e2 = lesen(x2); ok("manipulierte Summe: Warnung", any("Rechnerisch" in w for w in e2.get("warnungen", [])) and x2 != xml, e2.get("warnungen"))
ok("stimmige Rechnung: keine Rechen-Warnung", not any("Rechnerisch" in w for w in e.get("warnungen", [])), e.get("warnungen"))
kopf = {"belegnr": e["rechnung"]["nummer"], "belegdatum": e["rechnung"]["datum"], "betrag": e["rechnung"]["zahlbetrag"], "iban": e["lieferant"]["iban"]}
body = {"token": e["token"], "endung": e["endung"], "lieferant_id": lf["id"], "kopf": kopf, "zeilen": []}
r = A("POST", "eingang/buchen", body, FR); ok("Buchen mit anderer IBAN: Rückfrage", r["_s"] == 409 and r.get("rueckfrage") == "iban", r)
r = A("POST", "eingang/buchen", body, {**FR, "X-Bestaetigt": "iban"}); ok("… bestätigt: gebucht", r["_s"] == 200 and r.get("zahlung"), r)
pr = A("GET", "service/protokoll"); ein = [x for x in pr.get("eintraege", []) if x["art"] == "eingangsrechnung"]
ok("Fingerabdruck der Originaldatei im Protokoll", len(ein) == 1 and len(ein[0]["daten"].get("sha256", "")) == 64, ein)
bel = A("GET", "service/protokoll?voll=1").get("belege") or {}
ok("Belegprüfung zählt die Eingangsrechnung", bel.get("eingang_geprueft") == 1, bel)
r = A("POST", "zahlungen", {"lieferant_id": lf["id"], "betrag": 50, "belegnr": "X1", "iban": "DE02120300000000202051"}, FR); ok("Zahlungsauftrag von Hand mit anderer IBAN: Rückfrage", r["_s"] == 409 and r.get("rueckfrage") == "iban", r)
r = A("POST", "zahlungen", {"lieferant_id": lf["id"], "betrag": 50, "belegnr": "X2"}, FR); ok("Zahlungsauftrag mit Stamm-IBAN ohne Rückfrage", r["_s"] == 200, r)
# --- Lager
m = A("POST", "material", {"kategorie": "holzwerkstoffe", "bezeichnung": "MDF 19", "ek_preis": 12.0, "einheit": "m²"}); mid = m["id"]
r = A("POST", "lager", {"material_id": mid, "art": "inventur", "menge": 10}); ok("Inventur als Erstbestand: Lagerpreis = EK", abs((r.get("lagerpreis") or 0) - 12) < 0.001, r.get("lagerpreis"))
st = A("GET", "material/statistik"); ok("Lagerwert 120 €", abs(st["lagerwert"][0]["wert"] - 120) < 0.01, st["lagerwert"])
r = A("POST", "lager", {"material_id": mid, "art": "abgang", "menge": 25}, FR); ok("Abgang über Bestand: Rückfrage", r["_s"] == 409 and r.get("rueckfrage") == "lager_negativ", r)
r = A("POST", "lager", {"material_id": mid, "art": "zugang", "menge": -5}, FR); ok("Zugang mit negativer Menge abgelehnt", r["_s"] == 400, r)
r = A("POST", "lager", {"material_id": mid, "art": "abgang", "menge": 4}, FR); ok("normaler Abgang", r["_s"] == 200 and abs(r["bestand"] - 6) < 0.001, r)
r = A("POST", "auftragskosten", {"auftrag_id": a["id"], "material_id": mid, "menge": 50, "lager_abgang": 1}, FR); ok("Auftragsentnahme über Bestand: Rückfrage", r["_s"] == 409, r)
r = A("POST", "auftragskosten", {"auftrag_id": a["id"], "material_id": mid, "menge": 50, "lager_abgang": 1}); ok("Scan/Stempeluhr (ohne Rückfrage-Kopf) bucht wie bisher", r["_s"] == 200, r)
# --- Termine
r = A("POST", "termine", {"auftrag_id": a["id"], "typ": "Montage", "von": "2026-12-14", "bis": "2026-12-14", "zeit_von": "14:00", "zeit_bis": "09:00"}); ok("Uhrzeit bis vor von abgelehnt", r["_s"] == 400, r)
r = A("POST", "termine", {"auftrag_id": 99999, "typ": "Montage", "von": "2026-12-14", "bis": "2026-12-14"}); ok("Termin zu unbekanntem Auftrag: verständliche Meldung", r["_s"] in (400, 404, 409) and "FOREIGN" not in r.get("fehler", ""), r)
r = A("POST", "termine", {"auftrag_id": a["id"], "typ": "Montage", "von": "2026-12-24", "bis": "2026-12-28"}); kal = A("GET", "kalender?von=2026-12-21&bis=2026-12-31")
t = [x for x in kal["termine"] if x["id"] == r["id"]][0]; ok("Termin 24.–28.12.: nur 2 Arbeitstage geplant (16 h)", abs(t["geplant"] - 16) < 0.01, t.get("geplant"))
# --- gleichzeitiges Bearbeiten
b2c = cl(); A("POST", "benutzer", {"name": "Büro Zwei", "login": "buero", "passwort": "geheim45678", "rolle": "buero"})
rq(b2c, "POST", "/api/anmeldung/anmelden", {"login": "buero", "passwort": "geheim45678"})
g = A("GET", f"kunden/{k['id']}"); stand = g["_h"].get("X-Zeit"); ok("Server gibt Stand mit", bool(stand), g["_h"])
s, t_, _ = rq(b2c, "PUT", f"/api/kunden/{k['id']}", {"telefon": "111"}, FR); ok("zweiter Benutzer ändert den Kunden", s == 200, t_)
r = A("PUT", f"kunden/{k['id']}", {"telefon": "222"}, {**FR, "X-Stand": stand}); ok("erster speichert mit altem Stand: Rückfrage", r["_s"] == 409 and r.get("rueckfrage") == "stand" and "Büro Zwei" in r.get("fehler", ""), r)
r = A("PUT", f"kunden/{k['id']}", {"telefon": "222"}, {**FR, "X-Stand": stand, "X-Bestaetigt": "stand"}); ok("… bestätigt: gespeichert", r["_s"] == 200, r)
r2 = A("PUT", f"kunden/{k['id']}", {"telefon": "333"}, {**FR, "X-Stand": r["_h"].get("X-Zeit")}); ok("eigener neuer Stand: keine Rückfrage", r2["_s"] == 200, r2)
# --- Datenschutz: Anonymisieren
r = A("GET", f"lieferanten/{lf['id']}/anonymisieren"); ok("Lieferant mit frischen Belegen: noch nicht erlaubt", r.get("erlaubt") is False and r.get("frist_ende", "") > heute.isoformat(), r)
r = A("POST", f"lieferanten/{lf['id']}/anonymisieren", {}); ok("… Ausführen abgelehnt", r["_s"] == 400, r)
alt = A("POST", "lieferanten", {"kurzname": "Alt & Söhne", "firma": "Alt GmbH", "strasse": "Gasse 3", "plz": "88069", "ort": "Tettnang", "telefon": "07542 99", "iban": "DE89370400440532013000"})
za = A("POST", "zahlungen", {"lieferant_id": alt["id"], "betrag": 77, "belegnr": "A1", "belegdatum": "2012-03-01"}); A("POST", "zahlungen/bezahlt", {"ids": [za["id"]], "datum": "2012-03-10"})
r = A("GET", f"lieferanten/{alt['id']}/anonymisieren"); ok("Lieferant mit Belegen von 2012: erlaubt", r.get("erlaubt") is True, r)
s2, t2, _ = rq(b2c, "POST", f"/api/lieferanten/{alt['id']}/anonymisieren", {}); ok("Anonymisieren nur durch den Inhaber", s2 == 403, t2)
r = A("POST", f"lieferanten/{alt['id']}/anonymisieren", {}); l2 = A("GET", f"lieferanten/{alt['id']}"); z2 = A("GET", f"zahlungen/{za['id']}")
ok("Lieferant anonymisiert: Name, IBAN, Telefon weg, Betrag bleibt", r.get("erledigt") and "anonymisiert" in l2["kurzname"] and not l2["iban"] and not l2["telefon"] and abs(z2["betrag"] - 77) < 0.01 and not z2["iban"], (l2, z2))
ma = A("POST", "mitarbeiter", {"vorname": "Max", "nachname": "Früher", "strasse": "Weg 9", "telefon": "0171 5", "iban": "DE89370400440532013000", "geburtsdatum": "1970-01-01", "eintritt": "2005-01-01", "austritt": "2012-06-30"}); mid_ = ma.get("id") or ma.get("mitarbeiter", {}).get("id")
ma2 = A("POST", "mitarbeiter", {"vorname": "Eva", "nachname": "Aktiv", "eintritt": "2020-01-01"}); mid2_ = ma2.get("id") or ma2.get("mitarbeiter", {}).get("id")
r = A("GET", f"mitarbeiter/{mid2_}/anonymisieren"); ok("aktiver Mitarbeiter: nicht erlaubt", r.get("erlaubt") is False, r)
r = A("POST", f"mitarbeiter/{mid_}/anonymisieren", {}); m3 = A("GET", f"mitarbeiter/{mid_}"); m3 = m3.get("mitarbeiter", m3)
ok("ausgeschiedener Mitarbeiter (2012) anonymisiert", r.get("erledigt") and "anonymisiert" in (m3.get("nachname") or "") and not m3.get("vorname") and not m3.get("iban") and not m3.get("geburtsdatum"), (r, m3))
pr = A("GET", "service/protokoll"); ok("Anonymisierung im Protokoll", sum(1 for x in pr.get("eintraege", []) if x["art"] == "anonymisiert") == 2)
# --- Sicherheit
import http.client, urllib.parse
def roh(pfad, host):
    u = urllib.parse.urlparse(U); c = http.client.HTTPConnection(u.hostname, u.port, timeout=20); c.putrequest("GET", pfad, skip_host=True); c.putheader("Host", host); c.endheaders(); r = c.getresponse(); return r.status, r.read()[:200]
ok("fremder Hostname abgelehnt", roh("/api/anmeldung", "evil.example.com")[0] == 403, roh("/api/anmeldung", "evil.example.com"))
ok("Rechnername, IP, fritz.box, localhost erlaubt", all(roh("/api/anmeldung", h_)[0] == 200 for h_ in ("buero-pc:8765", "192.168.178.20:8765", "buero-pc.fritz.box:8765", "localhost:8765", "[::1]:8765")))
A("PUT", "einstellungen", {"netz_adressen": "buero.meinbetrieb.de"}); import time as _t; _t.sleep(0.1)
r = A("POST", "benutzer", {"name": "Kurz", "login": "kurz", "passwort": "abc123", "rolle": "buero"}); ok("Passwort mit 6 Zeichen abgelehnt", r["_s"] == 400 and "8 Zeichen" in r.get("fehler", ""), r)
r = A("POST", "benutzer", {"name": "Leicht", "login": "leicht", "passwort": "passwort", "rolle": "buero"}); ok("leicht zu erratendes Passwort abgelehnt", r["_s"] == 400, r)
r = A("POST", "benutzer", {"name": "Pin", "login": "pin", "passwort": "1234", "rolle": "mitarbeiter", "mitarbeiter_id": mid2_}); ok("Stempeluhr-PIN mit 4 Zeichen weiter möglich", r["_s"] == 200, r)
s3, t3, h3 = rq(inh, "GET", "/"); csp = h3.get("Content-Security-Policy", ""); ok("Inhaltsschutz mit Einmal-Kennung", "script-src 'self' 'nonce-" in csp and "connect-src 'self'" in csp and "JR" + "x" not in t3 and 'nonce="' in t3, csp)
import re as _re; ok("Platzhalter der Kennung wird ersetzt", not _re.search(r'nonce="JR[0-9a-f]{32}"', t3))
v = A("GET", "version"); ok("Version meldet den Ordner nur am Büro-PC", "version" in v)
print("\nFEHLER:", fehler)
sys.exit(1 if fehler else 0)
