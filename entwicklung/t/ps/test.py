import os, sys, shutil, time, tempfile, json
sys.path.insert(0, "/home/claude/eberle-buero")
import projektsicherung as ps, tresor
T = tempfile.mkdtemp(prefix="ps-"); Q, Z, D = (os.path.join(T, x) for x in ("projekte", "ziel", "daten"))
for x in (Q, Z, D): os.makedirs(x)
cfg = {"projektpfad": Q, "ziel": Z, "daten": D}
def w(rel, inhalt, alt=0):
    p = os.path.join(Q, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(inhalt)
    if alt: os.utime(p, (time.time() - alt, time.time() - alt))
def ok(b, t): print(("ok   " if b else "FEHLER ") + t); assert b, t
A = os.path.join(Z, ps.ORDNER, "aktuell")
# leer + keine Sicherung: läuft (nichts zu tun)
w("2026-001 Müller/Zeichnung.dwg", b"a" * 3000, 100); w("2026-001 Müller/Fotos/bild1.jpg", os.urandom(2_500_000), 100)
w("2026-002 Maier/Angebot.pdf", b"pdf", 100); w("2026-002 Maier/~$offen.docx", b"x"); w("Thumbs.db", b"x")
os.makedirs(os.path.join(Q, "leer"))
r = ps.sichern(cfg); ok(r["ok"] and r["neu"] == 3 and not r["fehler"], f"erster Lauf: 3 neu {r['neu']}")
ok(open(os.path.join(A, "2026-002 Maier/Angebot.pdf"), "rb").read() == b"pdf", "Klartextkopie lesbar")
r = ps.sichern(cfg); ok(r["ok"] and r["neu"] == 0 and r["gleich"] == 3 and r["geaendert"] == 0, "zweiter Lauf: nichts zu tun")
ok(not os.path.exists(os.path.join(Z, ps.ORDNER, "frueher")) or not os.listdir(os.path.join(Z, ps.ORDNER, "frueher")), "kein frueher-Ordner ohne Änderung")
# ändern + löschen
time.sleep(1.1)
w("2026-002 Maier/Angebot.pdf", b"pdf neu"); os.remove(os.path.join(Q, "2026-001 Müller/Zeichnung.dwg")); w("neu.txt", b"n")
r = ps.sichern(cfg); ok(r["geaendert"] == 1 and r["entfernt"] == 1 and r["neu"] == 1, f"geändert/gelöscht/neu {r}")
st = ps.staende(cfg); ok(len(st) == 2 and st[0]["stand"] == "aktuell", "zwei Stände")
f1 = st[1]["stand"]; F = os.path.join(Z, ps.ORDNER, "frueher", f1)
ok(open(os.path.join(F, "2026-002 Maier/Angebot.pdf"), "rb").read() == b"pdf", "alte Fassung in frueher")
ok(os.path.exists(os.path.join(F, "2026-001 Müller/Zeichnung.dwg")) and not os.path.exists(os.path.join(A, "2026-001 Müller/Zeichnung.dwg")), "gelöschte Datei in frueher")
# Kennwort setzen -> umstellen ohne frueher
tresor.setzen(D, "ein langes kennwort"); time.sleep(1.1)
r = ps.sichern(cfg); ok(r["verschluesselt"] and r["umgestellt"] == 3 and r["geaendert"] == 0, f"auf verschlüsselt umgestellt {r}")
namen = sorted(os.listdir(os.path.join(A, "2026-001 Müller/Fotos")))
ok(namen == ["bild1.jpg.jrs"], f"nur verschlüsselte Datei im Ziel {namen}")
ok(b"pdf neu" not in open(os.path.join(A, "2026-002 Maier/Angebot.pdf.jrs"), "rb").read(), "Inhalt nicht lesbar")
r = ps.sichern(cfg); ok(r["gleich"] == 3 and r["neu"] == 0 and r["umgestellt"] == 0, f"verschlüsselt: zweiter Lauf nichts zu tun {r}")
time.sleep(1.1); w("2026-002 Maier/Angebot.pdf", b"pdf drei")
r = ps.sichern(cfg); ok(r["geaendert"] == 1, "verschlüsselt geändert")
# Wiederherstellen aktuell (verschlüsselt, Schlüssel am PC) – ganzer Ordner
ok(ps.kennwort_pruefen(cfg, "aktuell", "2026-002 Maier") is True, "Kennwortprüfung mit PC-Schlüssel")
e = ps.wiederherstellen(cfg, "aktuell", "2026-002 Maier"); ok(e["dateien"] == 1 and not e["fehler"], f"zurückgeholt {e}")
ok(open(os.path.join(e["ordner"], "2026-002 Maier/Angebot.pdf"), "rb").read() == b"pdf drei", "Inhalt stimmt")
# einzelne Datei aus früherem Stand (Klartext)
e = ps.wiederherstellen(cfg, f1, "2026-001 Müller/Zeichnung.dwg"); ok(e["dateien"] == 1 and open(os.path.join(e["ordner"], "2026-001 Müller/Zeichnung.dwg"), "rb").read() == b"a" * 3000, "einzelne Datei aus frueher")
# einzelne verschlüsselte Datei
e = ps.wiederherstellen(cfg, "aktuell", "2026-001 Müller/Fotos/bild1.jpg"); ok(e["dateien"] == 1 and os.path.getsize(os.path.join(e["ordner"], "2026-001 Müller/Fotos/bild1.jpg")) == 2_500_000, "einzelne verschlüsselte Datei")
# _Wiederhergestellt wird nicht gesichert
r = ps.sichern(cfg); ok(r["neu"] == 0 and not os.path.exists(os.path.join(A, ps.WIEDER)), f"_Wiederhergestellt nicht gesichert {r}")
# anderer PC: Schlüssel weg -> Kennwort nötig
os.rename(os.path.join(D, "sicherung.schluessel"), os.path.join(D, "x"))
try: ps.kennwort_pruefen(cfg, "aktuell", ""); ok(False, "Kennwort nötig")
except tresor.Fehler as x: ok(str(x) == "KENNWORT_NOETIG", "ohne Schlüssel: Kennwort nötig")
try: ps.kennwort_pruefen(cfg, "aktuell", "", "falsch falsch"); ok(False, "falsches Kennwort")
except ps.Fehler: ok(True, "falsches Kennwort abgelehnt")
ok(ps.kennwort_pruefen(cfg, "aktuell", "", "ein langes kennwort"), "richtiges Kennwort")
e = ps.wiederherstellen(cfg, "aktuell", "", "ein langes kennwort"); ok(e["dateien"] == 3 and not e["fehler"], f"alles mit Kennwort zurück {e['dateien']}")
os.rename(os.path.join(D, "x"), os.path.join(D, "sicherung.schluessel"))
# Schlüssel unlesbar, Kennwort aktiv -> kein Klartext
open(os.path.join(D, "sicherung.schluessel"), "w").write("{}")
r = ps.sichern(cfg); ok(not r["ok"] and "nicht lesbar" in r["hinweis"], "Schlüssel unlesbar: keine Klartextsicherung")
tresor.entfernen(D)
# leerer Projektordner -> Abbruch ohne Änderung
shutil.move(Q, Q + "_weg"); os.makedirs(Q)
r = ps.sichern(cfg); ok(not r["ok"] and "leer" in r["hinweis"] and os.path.exists(os.path.join(A, "neu.txt.jrs")), "leerer Projektordner: nichts verändert")
os.rmdir(Q); r = ps.sichern(cfg); ok(not r["ok"] and "nicht erreichbar" in r["hinweis"], "fehlender Projektordner")
shutil.move(Q + "_weg", Q)
# Ziel fehlt
r = ps.sichern({**cfg, "ziel": os.path.join(T, "gibtsnicht")}); ok(not r["ok"] and "Sicherungsziel" in r["hinweis"], "Ziel nicht erreichbar")
r = ps.sichern({**cfg, "ziel": os.path.join(Q, "unter")}); ok(not r["ok"], "Ziel im Projektordner abgelehnt")
# Aufräumen nach Frist
alt = os.path.join(Z, ps.ORDNER, "frueher", "2026-01-05_120000"); os.makedirs(alt); open(os.path.join(alt, "a"), "w").write("x")
fremd = os.path.join(Z, ps.ORDNER, "frueher", "eigener Ordner"); os.makedirs(fremd)
r = ps.sichern(cfg, tage=90); ok(r["ok"] and r["aufgeraeumt"] == 1 and not os.path.exists(alt) and os.path.exists(fremd) and os.path.exists(F), f"Aufräumen: nur abgelaufene eigene Stände {r['aufgeraeumt']}")
ok(r["umgestellt"] == 3, "zurück auf unverschlüsselt umgestellt")
# Massenänderung (Trojaner): Aufräumen ausgesetzt
for i in range(300): w(f"viele/d{i}.txt", b"x" * 10, 50)
r = ps.sichern(cfg); ok(r["neu"] == 300 and not r["hinweis"], "300 neue Dateien sind unauffällig")
time.sleep(1.1)
for i in range(300): w(f"viele/d{i}.txt", os.urandom(12))
os.makedirs(alt); r = ps.sichern(cfg, tage=90)
ok(r["ok"] and r["geaendert"] == 300 and "Auffällig" in r["hinweis"] and os.path.exists(alt), "Massenänderung: Hinweis, Aufräumen ausgesetzt")
ok(len(os.listdir(os.path.join(Z, ps.ORDNER, "frueher", ps.staende(cfg)[1]["stand"], "viele"))) == 300, "alle 300 alten Fassungen erhalten")
# unlesbarer Ordner gilt nicht als gelöscht
if os.geteuid() != 0:
    os.chmod(os.path.join(Q, "viele"), 0); r = ps.sichern(cfg); os.chmod(os.path.join(Q, "viele"), 0o755)
    ok(r["entfernt"] == 0 and r["fehler_anzahl"] == 1, "unlesbarer Ordner")
# Inhalt, Pfadprüfung
i = ps.inhalt(cfg, "aktuell", ""); ok("2026-002 Maier" in i["ordner"] and any(d["name"] == "neu.txt" for d in i["dateien"]), "Inhalt blättern")
for boese in ("../..", "a/../../b", "C:/Windows"):
    try: ps.inhalt(cfg, "aktuell", boese); ok(False, "Pfad " + boese)
    except ps.Fehler: pass
try: ps.inhalt(cfg, "../../etc", ""); ok(False, "Stand")
except ps.Fehler: ok(True, "Pfad- und Standprüfung")
# Zeitplan
from datetime import datetime, timedelta
e = ps.einstellung({"aktiv": True, "uhrzeit": "12:00"}); j = datetime.now().replace(hour=13, minute=0)
ok(not ps.faellig(D, e, j), "heute schon gesichert: nicht fällig")
ps._status_schreiben(D, letzter_erfolg=(j - timedelta(days=1)).isoformat(), versuch=(j - timedelta(days=1)).isoformat())
ok(ps.faellig(D, e, j) and not ps.faellig(D, e, j.replace(hour=11)), "fällig ab Uhrzeit")
ps._status_schreiben(D, versuch=(j - timedelta(minutes=20)).isoformat(), letzter={"ok": False, "hinweis": "Ziel fehlt"})
ok(not ps.faellig(D, e, j) and ps.faellig(D, e, j + timedelta(minutes=50)), "nach Fehlschlag stündlich")
ps._status_schreiben(D, letzter_erfolg=(j - timedelta(days=4)).isoformat())
ok("seit 4 Tagen" in ps.warnung(D, e, j) and ps.warnung(D, ps.einstellung({"aktiv": True, "warn_tage": 8}), j) == "" and not ps.faellig(D, e, j + timedelta(hours=3), ziel="/gibt/es/nicht") and ps.faellig(D, e, j + timedelta(hours=3), ziel=D) and ps.warnung(D, ps.einstellung({}), j) == "", "Warnung nach 3 Tagen")
ok(ps.einstellung({"uhrzeit": "99:99", "tage": "x"}) == {"aktiv": False, "uhrzeit": "23:59", "tage": 90, "warn_tage": 3}, "Einstellung bereinigt")
shutil.rmtree(T); print("ALLES IN ORDNUNG")
