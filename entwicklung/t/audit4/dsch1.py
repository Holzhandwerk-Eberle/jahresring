"""Datenschutz und Mitarbeiterverwaltung: Stempeln, Sicht auf Kollegen, Arbeitsschutzdaten, Rückstände nach dem Anonymisieren."""
import json, re, sys, base64, time, os, sqlite3, subprocess, glob
from datetime import date, datetime, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    return j
def anmelden(login, pw):
    c = cl(); s, b, _ = rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": pw}); return c, s
PW = "Pruefung#2026"
werk, _ = anmelden("werk", PW); mita, _ = anmelden("mita", PW); buero, _ = anmelden("buero", "Neu#Passwort77")
ml = A("GET", "mitarbeiter")["liste"]; m1 = [m for m in ml if m["nachname"] == "Werk"][0]["id"]; m2 = [m for m in ml if m["nachname"] == "Zwei"][0]["id"]
heute = date.today().isoformat()
print("== A. Stempeln mit frei gewählter Uhrzeit (Rolle Mitarbeiter)")
vor = (date.today() - timedelta(days=6)).isoformat()
r = A("POST", "stempel", {"aktion": "start", "zeit": f"{vor}T05:00"}, c=mita); print("  Beginn vor 6 Tagen um 05:00:", r["_s"], r.get("ergebnisse", r.get("fehler")))
r = A("POST", "stempel", {"aktion": "ende", "zeit": f"{vor}T19:30"}, c=mita); print("  Ende am selben Tag 19:30:", r["_s"], r.get("ergebnisse", r.get("fehler")))
r = A("POST", "stempel", {"aktion": "start", "zeit": "2019-03-04T07:00"}, c=mita); r2 = A("POST", "stempel", {"aktion": "ende", "zeit": "2019-03-04T16:00"}, c=mita); print("  Zeiten im Jahr 2019:", r["_s"], r2["_s"])
z = A("GET", f"zeiten?mitarbeiter_id={m2}&von=2019-01-01&bis={heute}")
zl = z.get("liste") or z.get("zeiten") or []
print("  Im Büro sichtbar:", [(x.get("datum"), x.get("beginn"), x.get("ende"), x.get("quelle"), x.get("stunden")) for x in zl][:6])
print("  Felder eines Zeiteintrags:", sorted(zl[0].keys()) if zl else z["_roh"][:200])
print("\n== B. Sicht auf Kollegen (Abwesenheiten mit Grund)")
r = A("POST", "abwesenheiten", {"mitarbeiter_id": m2, "art": "krank", "von": heute, "bis": heute, "notiz": "Bandscheibe XGESUND"}); print("  Krankmeldung für Eva angelegt:", r["_s"], r.get("fehler", ""))
r = A("POST", "abwesenheiten", {"mitarbeiter_id": m2, "art": "urlaub", "von": (date.today() + timedelta(days=3)).isoformat(), "bis": (date.today() + timedelta(days=5)).isoformat(), "notiz": "XURLAUBNOTIZ"})
von, bis = (date.today() - timedelta(days=3)).isoformat(), (date.today() + timedelta(days=10)).isoformat()
for lg, c in (("werk", werk), ("buero", buero), ("mita", mita)):
    k = A("GET", f"kalender?von={von}&bis={bis}", c=c); t = k["_roh"]
    ab = k.get("abwesenheiten") or [x for x in (k.get("termine") or []) if x.get("art") or x.get("abwesenheit")]
    print("  %-6s Kalender %s | Abwesenheiten: %s | 'krank' im Text: %s | Notiz sichtbar: %s" % (lg, k["_s"], json.dumps(ab, ensure_ascii=False)[:230], "krank" in t.lower(), "XGESUND" in t or "XURLAUBNOTIZ" in t))
s, t, _ = rq(werk, "GET", "/api/kalender/export.ics"); print("  werk Kalender-Export enthält 'krank':", "krank" in t.lower(), "| Notiz:", "XGESUND" in t)
s, t, _ = rq(werk, "GET", "/api/leitstand"); print("  werk Leitstand:", s, "| krank:", "krank" in t.lower())
print("\n== C. Arbeitsschutz: personenbezogene Nachweise für Büro (2) und Werkstatt (1)")
r = A("POST", "arbeitsschutz/vorsorge", {"mitarbeiter_id": m1, "art": "G 44 Hartholzstäube", "anlass": "Pflichtvorsorge", "datum": heute, "naechste": "2028-11-01", "ergebnis": "XVORSORGE keine Bedenken", "arzt": "Dr. XARZT"}); print("  Vorsorge angelegt:", r["_s"], r.get("fehler", ""), [k_ for k_ in r if not k_.startswith("_")][:14])
r = A("POST", "arbeitsschutz/exposition", {"mitarbeiter_id": m1, "stoff": "Buchenholzstaub XEXPO", "taetigkeit": "Schleifen", "von": "2026-01-01", "bis": heute, "hoehe": "1,2 mg/m³"}); print("  Exposition angelegt:", r["_s"], r.get("fehler", ""))
r = A("POST", "arbeitsschutz/verbandbuch", {"datum": heute, "name": "Max Werk", "verletzung": "Schnitt Daumen XVERBAND", "hergang": "Stemmeisen", "ersthelfer": "Eva"}); print("  Verbandbuch-Eintrag:", r["_s"], r.get("fehler", ""))
for lg, c in (("buero", buero), ("werk", werk), ("mita", mita)):
    aus = []
    for p in ("arbeitsschutz/vorsorge", "arbeitsschutz/exposition", "arbeitsschutz/verbandbuch", "arbeitsschutz/qualifikationen", "arbeitsschutz/uebersicht", "arbeitsschutz/unterweisungen", f"arbeitsschutz/mitarbeiter/{m1}"):
        x = A("GET", p, c=c); aus.append(f"{p.split('/', 1)[1]}:{x['_s']}" + ("!" if any(w in x["_roh"] for w in ("XVORSORGE", "XEXPO", "XVERBAND", "XARZT")) else ""))
    print("  %-6s %s   (! = Inhalt des Nachweises lesbar)" % (lg, " ".join(aus)))
print("\n== D. Lohn- und Stammdaten: wer sieht was")
A("PUT", f"mitarbeiter/{m1}", {"iban": "DE02120300000000202051", "geburtsdatum": "1990-05-05", "steuer_id": "12345678901", "sv_nummer": "12 050590 W 123", "krankenkasse": "AOK XKASSE", "konfession": "rk", "strasse": "XSTRASSE 5"})
mm = A("GET", f"mitarbeiter/{m1}"); print("  Felder Mitarbeiter (Inhaber):", sorted(k_ for k_ in mm if not k_.startswith("_"))[:60])
for lg, c in (("buero", buero), ("werk", werk), ("mita", mita)):
    aus = {p: A("GET", p, c=c) for p in ("mitarbeiter", f"mitarbeiter/{m1}", "lohn?monat=2026-11", f"zeiten?mitarbeiter_id={m1}&von=2026-11-01&bis=2026-11-30", "anmeldung", "stempel?mit=listen", "start", "suche?q=Werk", "suche?q=XSTRASSE")}
    print("  %-6s" % lg, {p.split("?")[0]: (x["_s"], "IBAN!" if "DE0212030000" in x["_roh"] else "", "Lohn!" if '"stundenlohn": 23.5' in x["_roh"] else "", "Straße!" if "XSTRASSE" in x["_roh"] else "") for p, x in aus.items()})
