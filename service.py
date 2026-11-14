"""Service: Informationen, Datensicherung, Rücksicherung, Relationencheck."""
import json
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
import zipfile

import tresor
from datetime import datetime

AUSLASSEN = {"backup", "tmp", "browser-profil", "__pycache__", "zertifikat", "beschaedigt"}
EXTERN_DB = "Jahresring-Datenbank"   # Unterordner des externen Sicherungsziels für die täglichen Datenbanksicherungen
MAX_VOLL = 15          # vollständige Sicherungen, die behalten werden


class Fehler(Exception):
    pass


def groesse(pfad):
    if os.path.isfile(pfad):
        return os.path.getsize(pfad)
    summe = 0
    for wurzel, ordner, dateien in os.walk(pfad):
        ordner[:] = [o for o in ordner if o not in AUSLASSEN]
        for d in dateien:
            try:
                summe += os.path.getsize(os.path.join(wurzel, d))
            except OSError:
                pass
    return summe


def mb(b):
    return f"{b / 1048576:.2f}".replace(".", ",") + " MB"


# ---------------------------------------------------------------- Infos
def infos(con, cfg):
    zaehl = {}
    for tab, name in (("kunden", "Kunden"), ("auftraege", "Aufträge"), ("positionen", "Positionen"), ("belege", "Belege"),
                      ("offene_posten", "Offene Posten"), ("lieferanten", "Lieferanten"), ("zahlungen", "Zahlungsaufträge"),
                      ("material", "Materialien"), ("werkzeuge", "Werkzeuge"), ("mitarbeiter", "Mitarbeiter"), ("zeiten", "Zeitbuchungen"),
                      ("anhaenge", "Anhänge"), ("benutzer", "Benutzer")):
        try:
            zaehl[name] = con.execute(f"SELECT COUNT(*) FROM {tab}").fetchone()[0]
        except sqlite3.Error:
            pass
    try:
        platte = shutil.disk_usage(cfg["daten"])
    except OSError:
        platte = None
    letzte = next(iter(sicherungen(cfg, pruefen_=False)), None)
    return {
        "programm": {"Version": cfg["version"], "Programmordner": cfg["basis"], "Python": platform.python_version() + " (" + sys.executable + ")",
                     "Betriebssystem": f"{platform.system()} {platform.release()} ({platform.version()})"},
        "netzwerk": {"Im Netzwerk erreichbar": "ja" if cfg["netz"] else "nein (nur dieser PC)", "IP-Adresse": cfg["ip"], "Port": cfg["port"],
                     "Adresse am PC": f"http://localhost:{cfg['port']}",
                     "Stempeluhr": f"http://{cfg['ip']}:{cfg['port']}/stempel" if cfg["netz"] else "—"},
        "pfade": {"Daten-Verzeichnis": cfg["daten"], "Datenbank": cfg["db"], "Sicherungen": cfg["backup"],
                  "Projektordner": cfg.get("projektpfad") or "— (nicht eingerichtet)", "Externes Sicherungsziel": cfg.get("ziel") or "— (nicht eingerichtet)"},
        "platz": {"Datenbank": mb(os.path.getsize(cfg["db"])) if os.path.exists(cfg["db"]) else "—",
                  "Daten-Verzeichnis (ohne Sicherungen)": mb(groesse(cfg["daten"])),
                  "Sicherungen": mb(groesse_ordner(cfg["backup"])),
                  "Festplatte gesamt": f"{platte.total / 1e9:.0f} GB" if platte else "—",
                  "Festplatte frei": f"{platte.free / 1e9:.0f} GB ({platte.free / platte.total * 100:.1f} % frei)".replace(".", ",") if platte else "—"},
        "datensaetze": zaehl,
        "letzte_sicherung": letzte,
    }


def groesse_ordner(p):
    if not os.path.isdir(p):
        return 0
    return sum(os.path.getsize(os.path.join(p, f)) for f in os.listdir(p) if os.path.isfile(os.path.join(p, f)))


# ---------------------------------------------------------------- Sicherungen
def _db_pruefen(pfad):
    try:
        c = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
        ok = c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        try:
            v = json.loads(c.execute("SELECT wert FROM einstellungen WHERE schluessel='programm_version'").fetchone()[0])
        except Exception:  # noqa: BLE001
            v = ""
        c.close()
        return ok, v
    except sqlite3.Error:
        return False, ""


def _zip_pruefen(pfad):
    try:
        with zipfile.ZipFile(pfad) as z:
            if "buero.db" not in z.namelist() or z.testzip() is not None:
                return False, ""
            info = json.loads(z.read("sicherung.json")) if "sicherung.json" in z.namelist() else {}
            return True, info.get("version", "")
    except (zipfile.BadZipFile, OSError, ValueError):
        return False, ""


def _pruef_cache(p, neu=None):
    """Prüfergebnisse je Sicherungsdatei (Name, Größe, Änderungszeit) in backup/pruefung.json, damit jede Datei nur
    einmal geprüft wird. Sicherungen ändern sich nach dem Anlegen nicht; ändert sich eine doch, wird sie neu geprüft."""
    datei = os.path.join(p, "pruefung.json")
    if neu is None:
        try:
            with open(datei, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}
    try:
        with open(datei + ".part", "w", encoding="utf-8") as f:
            json.dump(neu, f, ensure_ascii=False)
        os.replace(datei + ".part", datei)
    except OSError:
        pass


def sicherungen(cfg, pruefen_=True):
    """Neueste zuerst. art: voll (Daten + Dateien) oder auto (tägliche Datenbanksicherung beim Start)."""
    p = cfg["backup"]
    if not os.path.isdir(p):
        return []
    aus = []
    cache = _pruef_cache(p) if pruefen_ else {}
    cache_neu = {}
    for f in os.listdir(p):
        voll = os.path.join(p, f)
        art = _art(f)
        if not art:
            continue
        jrs = f.endswith(tresor.ENDUNG)
        zeit = datetime.fromtimestamp(os.path.getmtime(voll))
        e = {"name": f, "art": art, "zeit": zeit.isoformat(timespec="minutes"), "groesse": mb(os.path.getsize(voll)),
             "notiz": "vor Rücksicherung" if "vor-Ruecksicherung" in f else ""}
        if pruefen_:
            stempel = [os.path.getsize(voll), int(os.path.getmtime(voll))]
            c = cache.get(f)
            if c and c.get("stempel") == stempel:
                ok, v = c["ok"], c["version"]
            else:
                if jrs:   # verschlüsselt: mit dem Schlüssel dieses PCs auf Unverfälschtheit prüfen, sonst offen lassen
                    s = tresor.laden(cfg["daten"])
                    ok, v = (tresor.pruefen(voll, s[0]) if s and not _kennwort_noetig(cfg, voll) else None), ""
                else:
                    ok, v = _zip_pruefen(voll) if art == "voll" else _db_pruefen(voll)
            if ok is not None:
                cache_neu[f] = {"stempel": stempel, "ok": ok, "version": v}
            e.update({"ok": ok, "version": v})
        if jrs:
            e.update({"verschluesselt": True, "kennwort": _kennwort_noetig(cfg, voll)})
        aus.append(e)
    if pruefen_ and cache_neu != cache:
        _pruef_cache(p, cache_neu)
    return sorted(aus, key=lambda x: x["zeit"], reverse=True)


def sicherung_erstellen(cfg, zusatz=""):
    """Vollständige Sicherung: Datenbank (konsistente Kopie) + alle Dateien des Daten-Verzeichnisses als ZIP."""
    os.makedirs(cfg["backup"], exist_ok=True)
    name = f"Sicherung_{datetime.now():%Y-%m-%d_%H-%M-%S}{'_' + zusatz if zusatz else ''}.zip"
    ziel = os.path.join(cfg["backup"], name)
    tmp = tempfile.mkdtemp(prefix="jr-sich-")
    try:
        kopie = os.path.join(tmp, "buero.db")
        src = sqlite3.connect(cfg["db"])
        dst = sqlite3.connect(kopie)
        with dst:
            src.backup(dst)
        dst.execute("PRAGMA journal_mode=DELETE")   # Sicherung als eine einzelne Datei (ohne -wal/-shm)
        src.close()
        dst.close()
        with zipfile.ZipFile(ziel + ".part", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.write(kopie, "buero.db")
            z.writestr("sicherung.json", json.dumps({"version": cfg["version"], "zeit": datetime.now().isoformat(timespec="seconds"),
                                                     "rechner": platform.node()}, ensure_ascii=False))
            for wurzel, ordner, dateien in os.walk(cfg["daten"]):
                ordner[:] = [o for o in ordner if o not in AUSLASSEN]
                for d in dateien:
                    voll = os.path.join(wurzel, d)
                    rel = os.path.relpath(voll, cfg["daten"]).replace("\\", "/")
                    if rel in ("buero.db", "buero.db-journal", "buero.db-wal", "buero.db-shm", "sicherung.schluessel") or rel.startswith(("backup/", "tmp/")):
                        continue
                    try:
                        z.write(voll, "dateien/" + rel)
                    except OSError:
                        pass
        os.replace(ziel + ".part", ziel)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # alte vollständige Sicherungen aufräumen (Sicherungen „vor Rücksicherung“ zählen mit)
    alle = sorted(f for f in os.listdir(cfg["backup"]) if f.startswith("Sicherung_") and f.endswith(".zip"))
    for alt in alle[:-MAX_VOLL]:
        try:
            os.remove(os.path.join(cfg["backup"], alt))
        except OSError:
            pass
    extern, verschluesselt = "", False
    if cfg.get("ziel"):
        try:
            os.makedirs(cfg["ziel"], exist_ok=True)
            verschluesselt = extern_ablegen(cfg, ziel, os.path.join(cfg["ziel"], name))
            extern = cfg["ziel"]
        except (OSError, tresor.Fehler) as f:
            extern = f"FEHLER: {f}"
    return {"name": name, "groesse": mb(os.path.getsize(ziel)), "extern": extern, "verschluesselt": verschluesselt}


def extern_ablegen(cfg, quelle, ziel):
    """Kopie aufs externe Sicherungsziel: mit Sicherungskennwort verschlüsselt (Endung .jrs), sonst unverändert.
    Ist ein Kennwort gesetzt, der Schlüssel aber nicht lesbar, wird NICHT unverschlüsselt kopiert."""
    if tresor.aktiv(cfg["daten"]):
        s = tresor.laden(cfg["daten"])
        if not s:
            raise tresor.Fehler("Der Schlüssel des Sicherungskennworts ist auf diesem PC nicht lesbar (anderes Windows-Konto?). "
                                "Bitte das Sicherungskennwort unter Service › Datensicherung neu setzen.")
        tresor.verschluesseln(quelle, ziel + tresor.ENDUNG, s[0], s[1])
        return True
    shutil.copy2(quelle, ziel + ".tmp")
    os.replace(ziel + ".tmp", ziel)
    return False


def extern_nachverschluesseln(cfg):
    """Nach dem Setzen des Kennworts: bereits vorhandene unverschlüsselte Kopien auf dem externen Sicherungsziel verschlüsseln
    (die lesbare Datei wird erst entfernt, wenn die verschlüsselte geprüft ist). Liefert die Anzahl."""
    s = tresor.laden(cfg["daten"])
    if not s or not cfg.get("ziel"):
        return 0
    n = 0
    for ordner in (cfg["ziel"], os.path.join(cfg["ziel"], EXTERN_DB)):
        try:
            namen = os.listdir(ordner)
        except OSError:
            continue
        for f in namen:
            voll = os.path.join(ordner, f)
            if f.endswith(tresor.ENDUNG) or not _art(f) or not os.path.isfile(voll):
                continue
            try:
                tresor.verschluesseln(voll, voll + tresor.ENDUNG, s[0], s[1])
                if tresor.pruefen(voll + tresor.ENDUNG, s[0]):
                    os.remove(voll)
                    n += 1
            except OSError as x:
                print("Nachträgliches Verschlüsseln:", f, x)
    return n


def _art(f):
    """voll / auto für Sicherungsdateien (auch verschlüsselt), sonst None."""
    kern = f[:-len(tresor.ENDUNG)] if f.endswith(tresor.ENDUNG) else f
    if kern.startswith("Sicherung_") and kern.endswith(".zip"):
        return "voll"
    if kern.startswith("buero_") and kern.endswith(".db"):
        return "auto"
    return None


def sicherung_pfad(cfg, name, ort=""):
    """Pfad einer Sicherung: im Sicherungsordner dieses PCs oder (ort = extern/extern-db) auf dem externen Sicherungsziel."""
    if os.path.basename(name) != name or not _art(name):
        raise Fehler("Ungültiger Dateiname.")
    basis = {"": cfg["backup"], "extern": cfg.get("ziel") or "", "extern-db": os.path.join(cfg.get("ziel") or "", EXTERN_DB)}.get(ort or "")
    if not basis or (ort and not cfg.get("ziel")):
        raise Fehler("Sicherung nicht gefunden.")
    pfad = os.path.join(basis, name)
    if not os.path.isfile(pfad):
        raise Fehler("Sicherung nicht gefunden.")
    return pfad


def externe_sicherungen(cfg):
    """Sicherungen auf dem externen Sicherungsziel (ohne Inhaltsprüfung – die erfolgt beim Rücksichern)."""
    aus = []
    for ort, ordner in (("extern", cfg.get("ziel") or ""), ("extern-db", os.path.join(cfg.get("ziel") or "", EXTERN_DB))):
        if not cfg.get("ziel") or not os.path.isdir(ordner):
            continue
        try:
            namen = os.listdir(ordner)
        except OSError:
            continue
        for f in namen:
            art = _art(f)
            voll = os.path.join(ordner, f)
            if not art or not os.path.isfile(voll):
                continue
            aus.append({"name": f, "art": art, "ort": ort, "zeit": datetime.fromtimestamp(os.path.getmtime(voll)).isoformat(timespec="minutes"),
                        "groesse": mb(os.path.getsize(voll)), "notiz": "extern", "ok": None, "version": "",
                        "verschluesselt": f.endswith(tresor.ENDUNG), "kennwort": _kennwort_noetig(cfg, voll)})
    return sorted(aus, key=lambda x: x["zeit"], reverse=True)[:60]


def _kennwort_noetig(cfg, pfad):
    if not pfad.endswith(tresor.ENDUNG):
        return False
    try:
        salz, _ = tresor.kopf_lesen(pfad)
    except (tresor.Fehler, OSError):
        return False
    s = tresor.laden(cfg["daten"])
    return not (s and s[1] == salz)


def ruecksichern(cfg, name, nach_db, kennwort=None, ort=""):
    """Stellt eine Sicherung wieder her. Vorher wird der aktuelle Stand als „vor Rücksicherung“ gesichert.
    Verschlüsselte Sicherungen (.jrs) werden mit dem Schlüssel dieses PCs oder dem angegebenen Kennwort entschlüsselt."""
    pfad = sicherung_pfad(cfg, name, ort)
    tmp = tempfile.mkdtemp(prefix="jr-rueck-")
    dateien = 0
    try:
        if name.endswith(tresor.ENDUNG):
            try:
                schluessel = tresor.schluessel_fuer(pfad, cfg["daten"], kennwort)
                name = name[:-len(tresor.ENDUNG)]
                klar = os.path.join(tmp, name)
                tresor.entschluesseln(pfad, klar, schluessel)
            except tresor.Fehler as f:
                raise Fehler(str(f))
            pfad = klar
        ok, _ = _zip_pruefen(pfad) if name.endswith(".zip") else _db_pruefen(pfad)
        if not ok:
            raise Fehler("Diese Sicherung ist beschädigt und kann nicht zurückgesichert werden.")
        vorher = sicherung_erstellen({**cfg, "ziel": ""}, "vor-Ruecksicherung")
        if name.endswith(".zip"):
            with zipfile.ZipFile(pfad) as z:
                z.extract("buero.db", tmp)
                quelle = os.path.join(tmp, "buero.db")
                for m in z.namelist():
                    if not m.startswith("dateien/") or m.endswith("/"):
                        continue
                    rel = m[len("dateien/"):]
                    if rel.startswith("protokoll/"):
                        continue   # das Journal wird nie zurückgesetzt (GoBD)
                    ziel = os.path.normpath(os.path.join(cfg["daten"], rel))
                    if not ziel.startswith(os.path.normpath(cfg["daten"]) + os.sep):
                        continue
                    os.makedirs(os.path.dirname(ziel), exist_ok=True)
                    with z.open(m) as q, open(ziel, "wb") as w:
                        shutil.copyfileobj(q, w)
                    dateien += 1
        else:
            quelle = pfad
        src = sqlite3.connect(quelle)
        dst = sqlite3.connect(cfg["db"], timeout=30)
        with dst:
            src.backup(dst)   # ersetzt den Inhalt der laufenden Datenbank
        src.close()
        dst.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    nach_db()  # Datenbank auf die aktuelle Programmversion bringen
    return {"ok": True, "vorher": vorher["name"], "dateien": dateien}


# ---------------------------------------------------------------- Relationencheck
PRUEFUNGEN = [
    ("Positionen ohne Auftrag", "SELECT id, text AS info FROM positionen WHERE auftrag_id NOT IN (SELECT id FROM auftraege)"),
    ("Unterpositionen ohne Hauptposition", "SELECT id, text AS info FROM positionen WHERE parent_id IS NOT NULL AND parent_id NOT IN (SELECT id FROM positionen)"),
    ("Aufträge ohne Kunde", "SELECT id, nummer AS info FROM auftraege WHERE kunde_id NOT IN (SELECT id FROM kunden)"),
    ("Aufträge mit gelöschtem Projekt", "SELECT id, nummer AS info FROM auftraege WHERE projekt_id IS NOT NULL AND projekt_id NOT IN (SELECT id FROM projekte)"),
    ("Belege ohne Auftrag", "SELECT id, nummer AS info FROM belege WHERE auftrag_id IS NOT NULL AND auftrag_id NOT IN (SELECT id FROM auftraege)"),
    ("Offene Posten ohne Beleg", "SELECT id, beleg_id AS info FROM offene_posten WHERE beleg_id IS NOT NULL AND beleg_id NOT IN (SELECT id FROM belege)"),
    ("Zahlungseingänge ohne offenen Posten", "SELECT id, op_id AS info FROM zahlungseingaenge WHERE op_id NOT IN (SELECT id FROM offene_posten)"),
    ("Mahnungen ohne offenen Posten", "SELECT id, op_id AS info FROM mahnungen WHERE op_id NOT IN (SELECT id FROM offene_posten)"),
    ("Zahlungsaufträge ohne Lieferant", "SELECT id, nummer AS info FROM zahlungen WHERE lieferant_id NOT IN (SELECT id FROM lieferanten)"),
    ("Termine mit gelöschtem Auftrag", "SELECT id, titel AS info FROM termine WHERE auftrag_id IS NOT NULL AND auftrag_id NOT IN (SELECT id FROM auftraege)"),
    ("Auftragsstunden ohne Auftrag", "SELECT id, datum AS info FROM stunden WHERE auftrag_id NOT IN (SELECT id FROM auftraege)"),
    ("Auftragsstunden mit gelöschter Zeitbuchung", "SELECT id, datum AS info FROM stunden WHERE zeit_id IS NOT NULL AND zeit_id NOT IN (SELECT id FROM zeiten)"),
    ("Auftragskosten ohne Auftrag", "SELECT id, bezeichnung AS info FROM auftragskosten WHERE auftrag_id NOT IN (SELECT id FROM auftraege)"),
    ("Lagerbewegungen ohne Material", "SELECT id, datum AS info FROM lagerbewegungen WHERE material_id NOT IN (SELECT id FROM material)"),
    ("Set-Bestandteile ohne Material oder Set", "SELECT id, set_id AS info FROM material_set_pos WHERE material_id NOT IN (SELECT id FROM material) OR set_id NOT IN (SELECT id FROM material_sets)"),
    ("Zeitbuchungen ohne Mitarbeiter", "SELECT id, datum AS info FROM zeiten WHERE mitarbeiter_id NOT IN (SELECT id FROM mitarbeiter)"),
    ("Zeitbuchungen mit gelöschtem Auftrag", "SELECT id, datum AS info FROM zeiten WHERE auftrag_id IS NOT NULL AND auftrag_id NOT IN (SELECT id FROM auftraege)"),
    ("Abwesenheiten ohne Mitarbeiter", "SELECT id, von AS info FROM abwesenheiten WHERE mitarbeiter_id NOT IN (SELECT id FROM mitarbeiter)"),
    ("Lohndaten ohne Mitarbeiter", "SELECT id, monat AS info FROM lohn WHERE mitarbeiter_id NOT IN (SELECT id FROM mitarbeiter)"),
    ("Benutzer mit gelöschtem Mitarbeiter", "SELECT id, login AS info FROM benutzer WHERE mitarbeiter_id IS NOT NULL AND mitarbeiter_id NOT IN (SELECT id FROM mitarbeiter)"),
    ("Anhänge ohne Kunde/Auftrag/Lieferant", "SELECT id, dateiname AS info FROM anhaenge WHERE (kunde_id IS NOT NULL AND kunde_id NOT IN (SELECT id FROM kunden)) "
     "OR (auftrag_id IS NOT NULL AND auftrag_id NOT IN (SELECT id FROM auftraege)) OR (lieferant_id IS NOT NULL AND lieferant_id NOT IN (SELECT id FROM lieferanten))"),
    ("Notizen ohne Kunde/Auftrag/Lieferant", "SELECT id, substr(text,1,40) AS info FROM notizen WHERE (kunde_id IS NOT NULL AND kunde_id NOT IN (SELECT id FROM kunden)) "
     "OR (auftrag_id IS NOT NULL AND auftrag_id NOT IN (SELECT id FROM auftraege)) OR (lieferant_id IS NOT NULL AND lieferant_id NOT IN (SELECT id FROM lieferanten))"),
    ("Werkzeuge mit gelöschtem Lieferanten/Zahlungsauftrag", "SELECT id, nummer AS info FROM werkzeuge WHERE (lieferant_id IS NOT NULL AND lieferant_id NOT IN (SELECT id FROM lieferanten)) "
     "OR (zahlung_id IS NOT NULL AND zahlung_id NOT IN (SELECT id FROM zahlungen))"),
]


# Verwaiste Verweise, die sich gefahrlos lösen lassen (Spalte darf leer sein, der Datensatz bleibt erhalten)
LOESBAR = {
    "Aufträge mit gelöschtem Projekt": [("auftraege", "projekt_id", "projekte")],
    "Termine mit gelöschtem Auftrag": [("termine", "auftrag_id", "auftraege")],
    "Auftragsstunden mit gelöschter Zeitbuchung": [("stunden", "zeit_id", "zeiten")],
    "Zeitbuchungen mit gelöschtem Auftrag": [("zeiten", "auftrag_id", "auftraege")],
    "Benutzer mit gelöschtem Mitarbeiter": [("benutzer", "mitarbeiter_id", "mitarbeiter")],
    "Anhänge ohne Kunde/Auftrag/Lieferant": [("anhaenge", "kunde_id", "kunden"), ("anhaenge", "auftrag_id", "auftraege"), ("anhaenge", "lieferant_id", "lieferanten")],
    "Notizen ohne Kunde/Auftrag/Lieferant": [("notizen", "kunde_id", "kunden"), ("notizen", "auftrag_id", "auftraege"), ("notizen", "lieferant_id", "lieferanten")],
    "Werkzeuge mit gelöschtem Lieferanten/Zahlungsauftrag": [("werkzeuge", "lieferant_id", "lieferanten"), ("werkzeuge", "zahlung_id", "zahlungen")],
}


def verweise_loesen(con):
    """Löst verwaiste Verweise aus LOESBAR (setzt die Spalte leer). Gibt {Prüfung: Anzahl} zurück."""
    erg = {}
    for text, ziele in LOESBAR.items():
        n = 0
        for tab, spalte, ziel in ziele:
            try:
                n += con.execute(f"UPDATE {tab} SET {spalte}=NULL WHERE {spalte} IS NOT NULL AND {spalte} NOT IN (SELECT id FROM {ziel})").rowcount
            except sqlite3.Error:
                pass
        if n:
            erg[text] = n
    return erg


def relationen(con, cfg):
    ergebnis = []
    for text, sql in PRUEFUNGEN:
        try:
            zeilen = con.execute(sql).fetchall()
        except sqlite3.Error as f:
            ergebnis.append({"text": text, "anzahl": None, "fehler": str(f), "beispiele": []})
            continue
        ergebnis.append({"text": text, "anzahl": len(zeilen), "loesbar": text in LOESBAR, "beispiele": [f"#{r['id']} {r['info'] or ''}".strip() for r in zeilen[:5]]})
    # Dateien
    fehlend = [dict(r) for r in con.execute("SELECT id, dateiname, pfad FROM anhaenge") if not os.path.isfile(r["pfad"] or "")]
    ergebnis.append({"text": "Anhänge, deren Datei fehlt", "anzahl": len(fehlend), "beispiele": [f"#{x['id']} {x['dateiname']}" for x in fehlend[:5]]})
    bekannt = {os.path.normcase(os.path.abspath(r["pfad"])) for r in con.execute("SELECT pfad FROM anhaenge") if r["pfad"]}
    verwaist = []
    if os.path.isdir(cfg["anhaenge"]):
        for wurzel, _, dateien in os.walk(cfg["anhaenge"]):
            for d in dateien:
                p = os.path.normcase(os.path.abspath(os.path.join(wurzel, d)))
                if p not in bekannt:
                    verwaist.append(os.path.relpath(p, cfg["anhaenge"]))
    ergebnis.append({"text": "Verwaiste Dateien im Anhang-Ordner (ohne Datensatz)", "anzahl": len(verwaist), "beispiele": verwaist[:5]})
    benutzte_bilder = set()
    for r in con.execute("SELECT bilder FROM positionen WHERE IFNULL(bilder,'') NOT IN ('','[]')"):
        try:
            benutzte_bilder.update(b.get("datei") for b in json.loads(r["bilder"]) if isinstance(b, dict))
        except ValueError:
            pass
    fehl_b = [b for b in benutzte_bilder if b and not os.path.isfile(os.path.join(cfg["bilder"], b))]
    ergebnis.append({"text": "Positionsbilder, deren Datei fehlt", "anzahl": len(fehl_b), "beispiele": fehl_b[:5]})
    # Unveränderbares Protokoll (Hash-Kette)
    try:
        import protokoll
        pr = protokoll.pruefen(con)
        ergebnis.append({"text": "Protokoll/Journal: Hash-Kette und Abgleich Datenbank ↔ Journaldatei", "anzahl": 0 if pr["ok"] else len(pr["fehler"]),
                         "beispiele": pr["fehler"][:5]})
    except Exception as f:  # noqa: BLE001
        ergebnis.append({"text": "Protokoll/Journal prüfen", "anzahl": 1, "beispiele": [str(f)]})
    # Datenbank selbst
    integ = con.execute("PRAGMA integrity_check").fetchone()[0]
    ergebnis.insert(0, {"text": "Datenbank-Integrität (PRAGMA integrity_check)", "anzahl": 0 if integ == "ok" else 1,
                        "beispiele": [] if integ == "ok" else [integ]})
    return {"zeit": datetime.now().isoformat(timespec="seconds"), "pruefungen": ergebnis,
            "probleme": sum(1 for e in ergebnis if e["anzahl"])}
