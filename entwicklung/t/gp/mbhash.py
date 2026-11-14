import sys, os, shutil
P = "/tmp/claude-0/t/gp/app3"
shutil.rmtree(P, ignore_errors=True)
shutil.copytree("/home/claude/eberle-buero", P, ignore=shutil.ignore_patterns("daten", "__pycache__"))
sys.path.insert(0, P); os.chdir(P)
import app, unterschrift
app.init_db()
with app.verbindung() as con:
    m = app.api("POST", ["mitarbeiter"], {}, {"vorname": "Max", "nachname": "Test", "eintritt": "2026-01-01"})
    mid = m["id"]
    con.execute("INSERT INTO zeiten (mitarbeiter_id, datum, beginn, ende, kst, taetigkeit) VALUES (?,?,?,?,?,?)", (mid, "2026-10-05", "07:00", "16:00", "", ""))
    con.commit()
    alt = app.monatsbeleg_hash_v1(con, mid, "2026-10")
    con.execute("INSERT INTO signaturen (art, bezug, rolle, name, inhalt_sha256, zeit) VALUES ('monatsbeleg', ?, 'mitarbeiter', 'Max', ?, '2026-11-01T10:00:00')", (f"{mid}:2026-10", alt))
    con.commit()
    print("alte Unterschrift geändert?", app.monatsbeleg_signaturen(con, mid, "2026-10")["mitarbeiter"]["geaendert"])
    con.execute("UPDATE zeiten SET beginn='07:30', ende='16:30' WHERE mitarbeiter_id=?", (mid,)); con.commit()
    print("nach Verschieben (alte Formel sieht es):", app.monatsbeleg_signaturen(con, mid, "2026-10")["mitarbeiter"]["geaendert"])
    neu = app.monatsbeleg_hash(con, mid, "2026-10")
    con.execute("INSERT INTO signaturen (art, bezug, rolle, name, inhalt_sha256, zeit) VALUES ('monatsbeleg', ?, 'arbeitgeber', 'Chef', ?, '2026-11-14T10:00:00')", (f"{mid}:2026-10", neu)); con.commit()
    print("neue Unterschrift geändert?", app.monatsbeleg_signaturen(con, mid, "2026-10")["arbeitgeber"]["geaendert"])
