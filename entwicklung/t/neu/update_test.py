"""Update-Hinweis und PDF-Erzeugung ohne Netz und ohne Browser prüfen (Programm als Modul aus der Prüfkopie geladen)."""
import sys, os, io, time
Q = sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/t/v25/eberle-buero"
sys.path.insert(0, Q); os.chdir(Q)
import app
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:300]))
    if not bed: fehler.append(name)
z = app._version_zahl
ok("Versionsvergleich", z("2026.11.01-141") > z("2026.11.01-99") and z("2026.12.01-1") > z("2026.11.30-500") and z("unsinn") == ())
gesehen = {}
class Antwort(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False
def falsch(inhalt, schl=""):
    app.einstellungen_roh = lambda k, s=None: {"adresse": "https://beispiel.invalid/v.txt", "schluessel": schl} if k == "update" else s
    class Oeffner:
        def open(self, anfrage, timeout=0):
            gesehen["kopf"] = dict(anfrage.header_items()); gesehen["url"] = anfrage.full_url
            if isinstance(inhalt, Exception): raise inhalt
            return Antwort(inhalt.encode())
    def bauen(*handler): gesehen["handler"] = handler; return Oeffner()
    app.urllib.request.build_opener = bauen
    return app.update_pruefen()
r = falsch("2099.01.01-7\n"); ok("neuere Version wird gemeldet", r["neu"] == "2099.01.01-7" and not r["fehler"] and r["geprueft"], r)
ok("ohne Schlüssel kein Authorization-Kopf", "Authorization" not in gesehen["kopf"], gesehen["kopf"])
r = falsch(app.VERSION); ok("gleiche Version: kein Hinweis", r["neu"] == "" and not r["fehler"], r)
r = falsch("2001.01.01-1"); ok("ältere Version: kein Hinweis", r["neu"] == "", r)
r = falsch('VERSION = "2099.02.02-3"\nalt 2020.01.01-1'); ok("höchste Versionsnummer im Text zählt", r["neu"] == "2099.02.02-3", r)
r = falsch("<html>Anmeldung</html>"); ok("Seite ohne Versionsnummer: Fehlertext", r["neu"] == "" and "keine Versionsnummer" in r["fehler"], r)
r = falsch("2099.01.01-7", "token123"); ok("mit Schlüssel: Authorization-Kopf und keine Umleitung", gesehen["kopf"].get("Authorization") == "Bearer token123" and app._KeineUmleitung in gesehen["handler"], gesehen)
import urllib.error
r = falsch(urllib.error.HTTPError("https://x", 404, "Not Found", {}, None)); ok("404: verständlicher Hinweis", "Zugangsschlüssel prüfen" in r["fehler"] and r["neu"] == "", r)
r = falsch(OSError("Netz nicht erreichbar")); ok("kein Netz: Fehlertext, kein Absturz", r["fehler"] and r["neu"] == "", r)
app.einstellungen_roh = lambda k, s=None: {"adresse": "http://unsicher/v.txt"} if k == "update" else s
gesehen.clear(); r = app.update_pruefen(); ok("http-Adresse wird nicht abgefragt", not gesehen and not r["geprueft"], (gesehen, r))

# --- PDF-Erzeugung: Ersatzprofil, wenn das gewohnte Browser-Profil blockiert ist
import tempfile, shutil
app.DATEN = tempfile.mkdtemp(); os.makedirs(os.path.join(app.DATEN, "tmp"))
app.browser_finden = lambda: "/bin/true"
laeufe = []
def lauf(gut):
    def _l(exe, profil, tmp, url, zeit):
        laeufe.append(os.path.basename(profil))
        if gut(os.path.basename(profil)):
            open(tmp, "wb").write(b"%PDF" + b"x" * 600); return ""
        return "keine Datei erzeugt"
    return _l
ziel = os.path.join(app.DATEN, "tmp", "a.pdf")
app._pdf_lauf = lauf(lambda p: True); app.pdf_url_rendern("http://127.0.0.1:1/druck/1", ziel)
ok("Normalfall: ein Lauf mit dem gewohnten Profil", laeufe == ["browser-profil"] and os.path.getsize(ziel) > 500, laeufe)
laeufe.clear(); app._pdf_lauf = lauf(lambda p: p != "browser-profil"); app.pdf_url_rendern("http://127.0.0.1:1/druck/1", ziel)
ok("blockiertes Profil: zweiter Lauf mit Ersatzprofil", laeufe == ["browser-profil", "browser-profil-ersatz"], laeufe)
laeufe.clear(); app.pdf_url_rendern("http://127.0.0.1:1/druck/1", ziel)
ok("danach zuerst das Ersatzprofil", laeufe == ["browser-profil-ersatz"], laeufe)
laeufe.clear(); app._pdf_lauf = lauf(lambda p: p.startswith("profil-")); app.pdf_url_rendern("http://127.0.0.1:1/druck/1", ziel)
ok("beide Profile blockiert: Einmal-Profil", len(laeufe) == 3 and laeufe[2].startswith("profil-"), laeufe)
ok("Einmal-Profil wird wieder entfernt", not [n for n in os.listdir(os.path.join(app.DATEN, "tmp")) if n.startswith("profil-")])
laeufe.clear(); app._pdf_lauf = lauf(lambda p: False)
try:
    app.pdf_url_rendern("http://127.0.0.1:1/druck/1", ziel); ok("alles blockiert: Fehlermeldung", False)
except app.ApiFehler as f:
    ok("alles blockiert: Fehlermeldung mit Grund", "keine Datei erzeugt" in str(f) and len(laeufe) == 3, f)
alt = os.path.join(app.DATEN, "tmp", "profil-alt"); os.makedirs(alt); os.utime(alt, (time.time() - 7200,) * 2)
app.tmp_aufraeumen(); ok("liegengebliebenes Einmal-Profil wird aufgeräumt", not os.path.exists(alt))
shutil.rmtree(app.DATEN, ignore_errors=True)
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
