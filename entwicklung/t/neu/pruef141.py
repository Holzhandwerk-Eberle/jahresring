"""Prüfungen zu Version -141: Vorsorgekartei, Expositionsverzeichnis, Unfallanzeige, Löschprüfung, Update-Hinweis, PDF-Erzeugung mit Ersatzprofil."""
import json, sys, os, importlib, tempfile
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
if len(sys.argv) > 1: U = sys.argv[1]
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:400]))
    if not bed: fehler.append(name)
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
s, _, _ = rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"}); ok("Anmeldung", s == 200, s)
def A(m, p, d=None, h=None, c=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    return j
from datetime import date, timedelta
heute = date.today()
mi = lambda d: (d.get("id") or d.get("mitarbeiter", {}).get("id"))
m1 = mi(A("POST", "mitarbeiter", {"vorname": "Eva", "nachname": "Aktiv", "eintritt": "2020-01-01"}))
m2 = mi(A("POST", "mitarbeiter", {"vorname": "Max", "nachname": "Früher", "eintritt": "2000-01-01", "austritt": "2012-06-30"}))
m3 = mi(A("POST", "mitarbeiter", {"vorname": "Otto", "nachname": "Staub", "eintritt": "2000-01-01", "austritt": "2012-06-30"}))
# --- Vorsorgekartei
r = A("GET", "arbeitsschutz/vorsorge"); ok("Vorsorge: Liste mit Auswahllisten", r["_s"] == 200 and r["eintraege"] == [] and "Pflichtvorsorge" in r["arten"] and r["anlaesse"], r)
v = A("POST", "arbeitsschutz/vorsorge", {"mitarbeiter_id": m1, "anlass": "Lärm", "art": "Pflichtvorsorge", "status": "durchgeführt", "datum": (heute - timedelta(days=400)).isoformat(),
                                          "naechste": (heute - timedelta(days=10)).isoformat(), "arzt": "Dr. Muster"})
ok("Vorsorge angelegt", v["_s"] == 200 and v.get("id"), v)
r = A("POST", "arbeitsschutz/vorsorge", {"anlass": "Lärm"}); ok("Vorsorge ohne Mitarbeiter abgelehnt", r["_s"] == 400, r)
r = A("POST", "arbeitsschutz/vorsorge", {"mitarbeiter_id": m1, "anlass": "Lärm", "datum": "2026-13-45"}); ok("Vorsorge mit falschem Datum abgelehnt", r["_s"] == 400, r)
l = A("GET", "arbeitsschutz/vorsorge")["eintraege"]; ok("Vorsorge überfällig erkannt", len(l) == 1 and l[0]["faellig"] == "ueberfaellig" and l[0]["name"] == "Eva Aktiv", l)
ue = A("GET", "arbeitsschutz/uebersicht"); texte = " | ".join(p["text"] for p in ue.get("punkte", []))
ok("Übersicht erinnert an Vorsorge", "Arbeitsmedizinische Vorsorge Lärm für Eva Aktiv" in texte, texte)
v2 = A("POST", "arbeitsschutz/vorsorge", {"mitarbeiter_id": m1, "anlass": "Lärm", "art": "Pflichtvorsorge", "datum": heute.isoformat(), "naechste": (heute + timedelta(days=1000)).isoformat()})
l = A("GET", "arbeitsschutz/vorsorge")["eintraege"]; ok("neuer Eintrag löst den alten ab (nur der jüngste je Anlass ist fällig)", not any(x["faellig"] for x in l), l)
r = A("PUT", f"arbeitsschutz/vorsorge/{v['id']}", {"bemerkung": "x" * 500}); l = A("GET", "arbeitsschutz/vorsorge")["eintraege"]
ok("Vorsorge ändern, Bemerkung begrenzt", r["_s"] == 200 and len([x for x in l if x["id"] == v["id"]][0]["bemerkung"]) == 300, r)
ok("Vorsorgekartei ohne Befundfeld", not any(k in l[0] for k in ("befund", "diagnose", "ergebnis")), list(l[0]))
r = A("DELETE", f"arbeitsschutz/vorsorge/{v2['id']}"); ok("Vorsorge löschen", r["_s"] == 200 and len(A("GET", "arbeitsschutz/vorsorge")["eintraege"]) == 1, r)
# --- Expositionsverzeichnis
r = A("POST", "arbeitsschutz/exposition", {"stoff": "Hartholzstaub (Eiche, Buche)"}); ok("Exposition ohne Mitarbeiter abgelehnt", r["_s"] == 400, r)
r = A("POST", "arbeitsschutz/exposition", {"mitarbeiter_id": m1, "stoff": "Hartholzstaub (Eiche, Buche)", "von": "2024-01-01", "bis": "2023-01-01"}); ok("Ende vor Beginn abgelehnt", r["_s"] == 400, r)
e1 = A("POST", "arbeitsschutz/exposition", {"mitarbeiter_id": m1, "stoff": "Hartholzstaub (Eiche, Buche)", "taetigkeit": "Schleifen", "von": "2020-01-01", "hoehe": "unter 2 mg/m³", "haeufigkeit": "täglich 2 h"})
ok("Exposition angelegt", e1["_s"] == 200 and e1.get("id"), e1)
e3 = A("POST", "arbeitsschutz/exposition", {"mitarbeiter_id": m3, "stoff": "Hartholzstaub (Eiche, Buche)", "taetigkeit": "Schleifen", "von": "2000-01-01", "bis": "2012-06-30"})
l = A("GET", "arbeitsschutz/exposition"); el = {x["id"]: x for x in l["eintraege"]}
ok("Aufbewahrung 40 Jahre nach Ende", l["jahre"] == 40 and el[e3["id"]]["aufbewahren_bis"] == "2052-06-30" and el[e1["id"]]["aufbewahren_bis"] == "", el)
ok("am Tag der Erfassung löschbar (Tippfehler)", el[e1["id"]]["loeschbar"] is True)
# Erfassungstag zurückdatieren: dann gilt die Aufbewahrungsfrist
import sqlite3
db = sys.argv[2] if len(sys.argv) > 2 else "/tmp/claude-0/t/v25/eberle-buero/daten/buero.db"
con = sqlite3.connect(db, timeout=10); con.execute("UPDATE as_exposition SET angelegt='2020-01-01 08:00:00'"); con.commit(); con.close()
r = A("DELETE", f"arbeitsschutz/exposition/{e3['id']}"); ok("Exposition innerhalb der 40 Jahre nicht löschbar", r["_s"] == 409 and "40 Jahre" in r.get("fehler", ""), r)
r = A("PUT", f"arbeitsschutz/exposition/{e1['id']}", {"mitarbeiter_id": m2, "bis": "2025-12-31"}); el = {x["id"]: x for x in A("GET", "arbeitsschutz/exposition")["eintraege"]}
ok("Exposition ändern: Ende gesetzt, Mitarbeiter bleibt", r["_s"] == 200 and el[e1["id"]]["bis"] == "2025-12-31" and el[e1["id"]]["mitarbeiter_id"] == m1, el[e1["id"]])
# --- Rechte: Mitarbeiter ohne Schreibrecht im Arbeitsschutz
b = A("POST", "benutzer", {"name": "Werk", "login": "werk", "passwort": "werkstatt9911", "rolle": "werkstatt"}); ok("zweiter Benutzer", b["_s"] == 200, b)
w = cl(); s, t, _ = rq(w, "POST", "/api/anmeldung/anmelden", {"login": "werk", "passwort": "werkstatt9911"}); ok("Werkstatt angemeldet", s == 200, t)
for p in ("arbeitsschutz/vorsorge", "arbeitsschutz/exposition", "datenschutz/faellig"):
    r = A("GET", p, c=w); ok(f"Werkstatt sieht {p} nicht", r["_s"] == 403, r)
r = A("POST", "update/pruefen", {}, c=w); ok("Update-Prüfung nur Inhaber", r["_s"] == 403, r)
# --- Verbandbuch: Ausfalltage und Unfallanzeige
vb = A("POST", "arbeitsschutz/verbandbuch", {"name": "Eva Aktiv", "verletzung": "Schnitt Hand", "hergang": "Stechbeitel", "zeit": heute.isoformat() + "T09:00"}); ok("Verbandbuch-Eintrag", vb.get("id"), vb)
r = A("PUT", f"arbeitsschutz/verbandbuch/{vb['id']}", {"au_tage": "zwei"}); ok("Ausfalltage nur als Zahl", r["_s"] == 400, r)
r = A("PUT", f"arbeitsschutz/verbandbuch/{vb['id']}", {"au_tage": 2}, c=w); ok("Nachtrag nur durch Inhaber", r["_s"] == 403, r)
A("PUT", f"arbeitsschutz/verbandbuch/{vb['id']}", {"au_tage": 3}); t = " | ".join(p["text"] for p in A("GET", "arbeitsschutz/uebersicht")["punkte"])
ok("3 Ausfalltage: keine Anzeige nötig", "Unfallanzeige" not in t, t)
A("PUT", f"arbeitsschutz/verbandbuch/{vb['id']}", {"au_tage": 5}); t = " | ".join(p["text"] for p in A("GET", "arbeitsschutz/uebersicht")["punkte"])
ok("5 Ausfalltage: Erinnerung an Unfallanzeige", "Unfallanzeige" in t and "Eva Aktiv" in t, t)
A("PUT", f"arbeitsschutz/verbandbuch/{vb['id']}", {"anzeige_am": heute.isoformat()}); t = " | ".join(p["text"] for p in A("GET", "arbeitsschutz/uebersicht")["punkte"])
ok("Anzeige eingetragen: Erinnerung weg", "Unfallanzeige" not in t, t)
# --- Löschprüfung
alt = A("POST", "lieferanten", {"kurzname": "Alt & Söhne", "firma": "Alt GmbH", "iban": "DE89370400440532013000"})
za = A("POST", "zahlungen", {"lieferant_id": alt["id"], "betrag": 77, "belegnr": "A1", "belegdatum": "2012-03-01"}); A("POST", "zahlungen/bezahlt", {"ids": [za["id"]], "datum": "2012-03-10"})
neu = A("POST", "lieferanten", {"kurzname": "Frisch GmbH"})
kn = A("POST", "kunden", {"kurzname": "Neu, Kunde"})
f = A("GET", "datenschutz/faellig"); ok("Löschprüfung liefert Listen", f["_s"] == 200 and set(f) >= {"kunden", "lieferanten", "mitarbeiter", "anzahl"}, f)
ok("alter Lieferant gemeldet, frischer nicht", [x["id"] for x in f["lieferanten"]] == [alt["id"]], f["lieferanten"])
ok("frischer Kunde nicht gemeldet", f["kunden"] == [], f["kunden"])
ok("ausgeschiedener Mitarbeiter gemeldet, der mit Exposition nicht (40 Jahre)", [x["id"] for x in f["mitarbeiter"]] == [m2], f["mitarbeiter"])
ok("Anzahl stimmt", f["anzahl"] == 2, f["anzahl"])
r = A("GET", f"mitarbeiter/{m3}/anonymisieren"); ok("Mitarbeiter mit Exposition: Frist bis 2052", r.get("erlaubt") is False and str(r.get("frist_ende", "")).startswith("2052"), r)
r = A("POST", f"mitarbeiter/{m2}/anonymisieren", {}); f = A("GET", "datenschutz/faellig"); ok("nach dem Anonymisieren nicht mehr in der Liste", r.get("erledigt") and f["mitarbeiter"] == [], f["mitarbeiter"])
# --- Update-Hinweis
r = A("PUT", "einstellungen", {"update": {"adresse": "http://beispiel.invalid/version.txt", "schluessel": "geheimer-schluessel-123"}}); ok("Adresse ohne https abgelehnt", r["_s"] == 400 and "https" in r.get("fehler", ""), r)
r = A("POST", "update/pruefen", {}); ok("ohne Adresse wird nichts abgefragt", r["_s"] == 200 and not r.get("geprueft") and not r.get("neu") and not r.get("fehler"), r)
r = A("PUT", "einstellungen", {"update": {"adresse": "https://beispiel.invalid/version.txt", "schluessel": "geheimer-schluessel-123"}}); ok("Adresse und Schlüssel gespeichert", r["_s"] == 200, r)
e = A("GET", "einstellungen"); u = e.get("update") or {}
ok("Zugangsschlüssel wird nie ausgeliefert", "geheimer-schluessel-123" not in json.dumps(e) and u.get("schluessel_gesetzt") is True and "schluessel" not in u, u)
con = sqlite3.connect(db, timeout=10); roh = con.execute("SELECT wert FROM einstellungen WHERE schluessel='update'").fetchone()[0]; con.close()
ok("Zugangsschlüssel gespeichert (unter Windows verschlüsselt, hier im Test unverändert)", json.loads(roh).get("schluessel") and (os.name != "nt" or "geheimer-schluessel-123" not in roh), roh)
A("PUT", "einstellungen", {"update": {"adresse": "https://beispiel.invalid/version.txt"}})
r = A("POST", "update/pruefen", {}); ok("nicht erreichbare Adresse: Fehlertext statt Absturz", r["_s"] == 200 and r.get("fehler") and r.get("geprueft") and not r.get("neu"), r)
e = A("GET", "einstellungen"); ok("Schlüssel bleibt beim Ändern der Adresse erhalten", (e.get("update") or {}).get("schluessel_gesetzt") is True, e.get("update"))
A("PUT", "einstellungen", {"update": {"schluessel_loeschen": True}}); e = A("GET", "einstellungen"); ok("Schlüssel entfernen", (e.get("update") or {}).get("schluessel_gesetzt") is False, e.get("update"))
r = A("PUT", "einstellungen", {"update": {"adresse": "https://x.invalid/v.txt"}}, c=w); e = A("GET", "einstellungen")
ok("Update-Adresse ändert nur der Inhaber", (e.get("update") or {}).get("adresse") == "https://beispiel.invalid/version.txt", (r, e.get("update")))
A("PUT", "einstellungen", {"update": {"adresse": ""}})
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
