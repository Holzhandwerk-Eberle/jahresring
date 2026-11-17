# Nach dem Update auf den aktuellen Stand (zuerst 149) mit dem Datenbestand aus 148: läuft alles, stimmt die Prüfung, greifen die neuen Regeln ohne Fehlalarm?
import sys, json, base64, sqlite3, urllib.request, http.cookiejar
from datetime import datetime, timedelta
U = "http://127.0.0.1:8799"; fehler = []
def ok(text, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + text + ("" if bed else f"  → {str(info)[:300]}"))
    if not bed: fehler.append(text)
def sitzung(): return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def A(o, m, p, d=None, h=None):
    r = urllib.request.Request(U + "/api/" + p, method=m, data=json.dumps(d).encode() if d is not None else None, headers={"Content-Type": "application/json", "Origin": U, **(h or {})})
    try:
        t = o.open(r, timeout=120).read().decode(); e = json.loads(t) if t else {}
        if isinstance(e, dict): e["_s"] = 200
        return e
    except urllib.error.HTTPError as e:
        try: d = json.loads(e.read().decode())
        except Exception: d = {}
        d["_s"] = e.code; return d
o = sitzung(); r = A(o, "POST", "anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}); ok("Inhaber meldet sich mit dem bisherigen Passwort an", r.get("ok"), r)
import re
NEU = re.search(r'^VERSION = "([^"]+)"', open("/home/claude/eberle-buero/app.py", encoding="utf-8").read(), re.M).group(1)   # der aktuelle Programmstand
ok(f"Version {NEU} läuft", A(o, "GET", "version").get("version") == NEU)
con = sqlite3.connect("/tmp/claude-0/t/v25/eberle-buero/daten/buero.db"); con.row_factory = sqlite3.Row
ph = con.execute("SELECT pw_hash FROM benutzer WHERE login='jonas'").fetchone()[0]
ok("Passwort-Prüfwert beim Anmelden auf 600.000 Runden erneuert", ph.startswith("pbkdf2$600000$"), ph[:40])
sp = {r[1] for r in con.execute("PRAGMA table_info(zeiten)")}; ok("Tabelle zeiten hat die neuen Spalten", {"eingang", "spaet"} <= sp, sp)
ok("Tabelle beleg_versand angelegt", con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='beleg_versand'").fetchone()[0] == 1)
idx = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='zeiten'")}; ok("Indizes der Zeiten umgestellt", {"zeiten_ma_zeit", "zeiten_offen"} <= idx and "zeiten_ma" not in idx, idx)
z = [dict(r) for r in con.execute("SELECT * FROM zeiten")]; ok("gestempelte Zeiten aus 148 vorhanden, ohne Kennzeichen „nachträglich“", len(z) >= 1 and all(not x["spaet"] for x in z), z[:2])
pr = A(o, "GET", "service/protokoll?voll=1"); b = pr.get("belege", {})
ok("Protokoll unverändert (Hash-Kette in Ordnung)", pr.get("pruefung", {}).get("ok") is True, pr.get("pruefung"))
ok("Belegprüfung ohne Fehlalarm (Rechnungen aus 148, auch im Echtbetrieb festgeschriebene)", b.get("ok") is True and not b.get("fehler"), b)
arten = [e["art"] for e in pr.get("eintraege", [])][:12]; alle = A(o, "GET", "service/protokoll?limit=200")
texte = [e.get("text", "") for e in (alle.get("eintraege") or pr.get("eintraege") or [])]
ok("Versionswechsel von 148 auf den aktuellen Stand steht im Protokoll", any(f"2026.11.01-148 → {NEU}" in t for t in texte), texte[:5])
bel = A(o, "GET", "belege"); ang = [x for x in bel if x["art"] == "angebot"]; rech = [x for x in bel if x["nummer"] == "2026-0050"]
ok("Belege aus 148 vorhanden (Angebot, Rechnung 2026-0050)", ang and rech, [(x["art"], x["nummer"], x["status"]) for x in bel])
bd = A(o, "GET", f"belege/{ang[0]['id']}"); ok("in 148 versandtes Angebot: öffnet, ohne festgehaltene Fassung (die gab es noch nicht)", bd["_s"] == 200 and bd.get("versand") == [], (bd.get("_s"), bd.get("versand")))
r = A(o, "DELETE", f"belege/{ang[0]['id']}"); ok("in 148 versandtes Angebot lässt sich nicht löschen", r["_s"] == 409, r)
import urllib.error
s = o.open(U + f"/druck/{rech[0]['id']}.pdf", timeout=120); roh = s.read(); ok("PDF der Rechnung aus 148 kommt aus dem Archiv", s.status == 200 and roh[:4] == b"%PDF", (s.status, roh[:20]))
s = o.open(U + f"/druck/{rech[0]['id']}?drucken=1", timeout=60); t = s.read().decode(); ok("Druckansicht der Rechnung aus 148", "iframe" in t and f"/druck/{rech[0]['id']}.pdf" in t, t[:200])
roh = open("/tmp/claude-0/t/up148/auszug.xml", "rb").read()
r = A(o, "POST", "bank/einlesen", {"daten": base64.b64encode(roh).decode(), "dateiname": "auszug_11.xml"})
ok("derselbe Kontoauszug noch einmal: alle drei Umsätze als schon vorhanden erkannt (auch der mit Platzhalter-Referenz)", r.get("neu") == 0 and r.get("doppelt") == 3, {k: r.get(k) for k in ("neu", "doppelt", "fehler", "_s")})
m = sitzung(); r = A(m, "POST", "anmeldung/anmelden", {"login": "max", "passwort": "1234"}); ok("Mitarbeiter mit vierstelliger PIN aus 148 kann sich weiter anmelden", r.get("ok"), r)
jetzt = datetime.now(); iso = lambda t: t.strftime("%Y-%m-%dT%H:%M")
r = A(m, "POST", "stempel", {"aktion": "start", "zeit": iso(jetzt), "client_id": "n1"}); ok("Stempeln nach dem Update", r["_s"] == 200 and not (r.get("ergebnisse") or [{}])[0].get("abgelehnt"), r)
A(m, "POST", "stempel", {"aktion": "ende", "zeit": iso(jetzt + timedelta(minutes=1)), "client_id": "n2"})
r = A(o, "PUT", f"benutzer/{[x for x in A(o, 'GET', 'benutzer') if x['login'] == 'max'][0]['id']}", {"passwort": "9876"}); ok("neue vierstellige PIN wird abgelehnt", r["_s"] == 400, r)
e = A(o, "GET", "einstellungen"); ok("neue Einstellungen mit Vorgaben vorhanden", e.get("uebertrag") is True and e.get("frist_rechnung_jahre") == 10 and e.get("sitzung_tage_buero") == 30,
                                     {k: e.get(k) for k in ("uebertrag", "frist_rechnung_jahre", "sitzung_tage_buero", "zeit_rundung")})
for p in ("kunden?felder=liste", "auftraege?felder=liste", "start", "offeneposten", "zahlungen", "bank?status=alle", "bank/regeln", "zeiten", "lohn?monat=2026-11", "datenschutz/faellig", "mitarbeiter"):
    r = A(o, "GET", p); ok(f"GET {p}", (r.get("_s") if isinstance(r, dict) else 200) == 200, r if isinstance(r, dict) else "")
print("FEHLER:", fehler)
