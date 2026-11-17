"""Datenbestand vom bisherigen PC übernehmen, solange auf diesem PC noch nichts erfasst ist.

Auf der Seite „Ersten Zugang anlegen“ (noch kein Benutzer, direkt am PC) lässt sich statt eines neuen Zugangs der
Bestand des alten PCs einspielen: aus dem kopierten Ordner „daten“, aus einer vollständigen Sicherung (Sicherung_….zip)
oder – ohne Dateien – aus einer Datenbanksicherung (buero_….db); Sicherungen auch verschlüsselt (.jrs).
Übernommen werden Datenbank, Dateien und das Protokoll. Gehört das Journal dieses PCs zu einem anderen Protokoll (bei
einem frisch eingerichteten PC: die Einträge der Erstinstallation), wird es unter anderem Namen aufbewahrt und das
Journal des übernommenen Bestands tritt an seine Stelle.
Nicht kopiert wird, was nur am alten PC gilt: https-Zertifikat, Browser-Profil, Zwischendateien, Meldungen des Programms.

Außerdem hier: Anhänge und Eingangsrechnungen sind mit vollem Pfad gespeichert; pfade_anpassen stellt sie auf den
Datenordner dieses PCs um, wenn der Bestand von einem anderen Ort kommt.
"""
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile
from datetime import datetime
from urllib.request import pathname2url

import protokoll
import tresor

AUSLASSEN = {"tmp", "browser-profil", "browser-profil-ersatz", "zertifikat", "__pycache__"}   # Ordner: gelten nur am alten PC
AUSLASSEN_DATEIEN = {"protokoll.txt", "protokoll-alt.txt"}                                     # Meldungen des Programms am alten PC
DB_DATEIEN = {"buero.db", "buero.db-wal", "buero.db-shm", "buero.db-journal"}
LEER_TABELLEN = ("benutzer", "kunden", "auftraege", "belege", "lieferanten", "mitarbeiter")
JOURNAL = "protokoll/journal.jsonl"
EXTERN_DB = "Jahresring-Datenbank"     # Unterordner des externen Sicherungsziels mit den täglichen Datenbanksicherungen
SUCH_SEKUNDEN = 5.0
STAND = {"laeuft": False, "schritt": "", "dateien": 0, "von": 0, "bytes": 0, "von_bytes": 0}
_lauf = threading.Lock()


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def version_zahl(v):
    """„2026.11.01-149“ → (2026, 11, 1, 149); Unlesbares zählt als sehr alt."""
    aus = []
    for teil in str(v or "").replace("-", ".").split("."):
        if not teil.isdigit():
            return ()
        aus.append(int(teil))
    return tuple(aus)


def mz(n, ein, mehr):
    """Zahl mit Hauptwort in Einzahl oder Mehrzahl: 1 Kunde, 3 Kunden."""
    return f"{n} {ein if n == 1 else mehr}"


def _ort(p):
    return os.path.normcase(os.path.realpath(p))


def _gb(b):
    return f"{b / 1e9:.1f}".replace(".", ",") + " GB"


def _anzahl(con, tabelle):
    try:
        return con.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0] or 0
    except sqlite3.Error:
        return 0


def leer(con):
    """Auf diesem PC ist noch nichts erfasst: kein Benutzer, keine Kunden, Aufträge, Belege, Lieferanten, Mitarbeiter."""
    return all(_anzahl(con, t) == 0 for t in LEER_TABELLEN)


def _wert(con, schluessel):
    try:
        r = con.execute("SELECT wert FROM einstellungen WHERE schluessel=?", (schluessel,)).fetchone()
        return json.loads(r[0]) if r else ""
    except (sqlite3.Error, ValueError, TypeError):
        return ""


def _inhalt(con):
    return {"firma": str(_wert(con, "firma") or ""), "version": str(_wert(con, "programm_version") or ""),
            "benutzer": _anzahl(con, "benutzer"), "kunden": _anzahl(con, "kunden"), "auftraege": _anzahl(con, "auftraege"),
            "belege": _anzahl(con, "belege"), "protokoll": _anzahl(con, "protokoll")}


def _zeit(pfad):
    zeiten = [os.path.getmtime(p) for p in (pfad, pfad + "-wal") if os.path.exists(p)]
    return datetime.fromtimestamp(max(zeiten)).isoformat(timespec="minutes") if zeiten else ""


def db_beschreiben(pfad):
    """Kurzbeschreibung eines Datenbestands zum Wiedererkennen: Firma, Umfang, Stand, Programmversion. Am Quellort wird
    nichts angelegt oder geändert: Gelesen wird die Datei unverändert (immutable); liegt eine -wal-Datei daneben (Kopie bei
    laufendem Programm) oder nimmt SQLite den Pfad so nicht an (Netzwerkpfad), wird über eine Arbeitskopie gelesen."""
    def lesen(con):
        try:
            con.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
            return {**_inhalt(con), "stand": _zeit(pfad)}
        finally:
            con.close()
    if not (os.path.exists(pfad + "-wal") and os.path.getsize(pfad + "-wal") > 0):
        try:
            return lesen(sqlite3.connect("file:" + pathname2url(os.path.abspath(pfad)) + "?immutable=1", uri=True, timeout=3))
        except sqlite3.Error:
            pass
    tmp = tempfile.mkdtemp(prefix="jr-ueb-")
    try:
        for x in ("", "-wal"):
            if os.path.exists(pfad + x):
                shutil.copyfile(pfad + x, os.path.join(tmp, "buero.db" + x))
        return lesen(sqlite3.connect(os.path.join(tmp, "buero.db"), timeout=3))
    except (sqlite3.Error, OSError):
        raise Fehler("Die Datenbank lässt sich nicht lesen. Sie ist beschädigt oder keine Jahresring-Datenbank.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _datenordner(o):
    """Der Ordner selbst, sein Unterordner „daten“ oder „Jahresring/daten“ – wo eben buero.db liegt."""
    for k in (o, os.path.join(o, "daten"), os.path.join(o, "Jahresring", "daten")):
        if os.path.isfile(os.path.join(k, "buero.db")):
            return k
    return ""


def _kern(name):
    return name[:-len(tresor.ENDUNG)] if name.lower().endswith(tresor.ENDUNG) else name


def sicherungsart(name):
    """„sicherung“ für eine vollständige Sicherung (….zip), „datenbank“ für eine Datenbanksicherung (….db), sonst leer."""
    kern = _kern(os.path.basename(name)).lower()
    if kern.endswith(".zip"):
        return "sicherung"
    if kern.endswith(".db"):
        return "datenbank"
    return ""


def quelle_finden(pfad):
    """(Art, Pfad) zu einer Angabe des Benutzers: „ordner“ mit dem Ordner, in dem buero.db liegt, „sicherung“ oder
    „datenbank“ mit der Datei."""
    p = str(pfad or "").strip().strip('"').strip("'").strip()
    if not p:
        raise Fehler("Bitte den Ordner „daten“ vom bisherigen PC oder eine Sicherungsdatei angeben.")
    p = os.path.abspath(os.path.expanduser(p))
    if os.path.isfile(p):
        if os.path.basename(p).lower() == "buero.db":
            return "ordner", os.path.dirname(p)
        art = sicherungsart(p)
        if art:
            return art, p
        raise Fehler("Diese Datei ist weder eine vollständige Sicherung (Sicherung_….zip) noch eine Jahresring-Datenbank (….db).")
    if os.path.isdir(p):
        q = _datenordner(p)
        if q:
            return "ordner", q
        raise Fehler("In diesem Ordner liegen keine Jahresring-Daten: Die Datei buero.db fehlt. Gebraucht wird der Ordner „daten“ "
                     "aus dem Jahresring-Ordner des bisherigen PCs.")
    raise Fehler("Diesen Ordner oder diese Datei gibt es nicht. Ist der Datenträger angesteckt und der Pfad richtig geschrieben?")


def _eigener_ordner(q, daten):
    """Der angegebene Ordner ist der Datenordner dieses PCs oder enthält ihn – daraus lässt sich nichts übernehmen."""
    q_, d_ = _ort(q), _ort(daten)
    if q_ == d_:
        raise Fehler("Das ist der Datenordner dieses PCs. Gebraucht wird der Ordner „daten“ vom bisherigen PC.")
    if d_.startswith(os.path.join(q_, "")):
        raise Fehler("Dieser Ordner enthält den Datenordner dieses PCs. Bitte die Dateien des bisherigen Bestands (buero.db und die "
                     "Unterordner) in einen eigenen Ordner legen und diesen angeben.")


def _ohne_benutzer():
    return Fehler("Hier liegt ein leerer Datenbestand ohne Benutzer – vermutlich nicht der, mit dem bisher gearbeitet wurde. Am bisherigen PC "
                  "zeigt ein Rechtsklick auf das Jahresring-Symbol neben der Uhr › „Datenordner öffnen“ den richtigen Ordner.")


def _sicherung_beschreiben(art, pfad):
    aus = {"firma": "", "version": "", "rechner": "", "verschluesselt": pfad.lower().endswith(tresor.ENDUNG),
           "stand": datetime.fromtimestamp(os.path.getmtime(pfad)).isoformat(timespec="minutes"), "groesse": os.path.getsize(pfad)}
    if aus["verschluesselt"]:
        try:
            tresor.kopf_lesen(pfad)
        except (tresor.Fehler, OSError):
            raise Fehler("Diese Datei ist keine verschlüsselte Jahresring-Sicherung.")
    elif art == "sicherung":
        try:
            with zipfile.ZipFile(pfad) as z:
                if "buero.db" not in z.namelist():
                    raise Fehler("Diese ZIP-Datei ist keine vollständige Jahresring-Sicherung (buero.db fehlt darin).")
                if "sicherung.json" in z.namelist():
                    info = json.loads(z.read("sicherung.json"))
                    aus.update(version=str(info.get("version") or ""), rechner=str(info.get("rechner") or ""),
                               stand=str(info.get("zeit") or aus["stand"])[:16])
        except (zipfile.BadZipFile, OSError, ValueError):
            raise Fehler("Die Sicherungsdatei ist beschädigt oder keine ZIP-Datei.")
    else:
        aus.update(db_beschreiben(pfad), stand=aus["stand"])
        if not aus["benutzer"]:
            raise _ohne_benutzer()
    return aus


def beschreiben(pfad, eigene_daten=""):
    """Was liegt unter dieser Angabe? Für die Anzeige vor der Übernahme; ändert nichts."""
    art, q = quelle_finden(pfad)
    if art == "ordner":
        if eigene_daten:
            _eigener_ordner(q, eigene_daten)
        aus = db_beschreiben(os.path.join(q, "buero.db"))
        if not aus["benutzer"]:
            raise _ohne_benutzer()
    else:
        aus = _sicherung_beschreiben(art, q)
    return {"art": art, "pfad": q, **aus}


# ---------------------------------------------------------------- Suche nach Datenbeständen
def _laufwerke():
    """(wechselbare, feste) Laufwerke unter Windows – ohne Netz- und CD-Laufwerke, die beim Zugriff hängen können."""
    wechsel, fest = [], []
    if os.name != "nt":
        return wechsel, fest
    try:
        import ctypes
        maske = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if maske >> i & 1:
                w = f"{chr(65 + i)}:\\"
                art = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(w))
                if art == 2:
                    wechsel.append(w)
                elif art == 3:
                    fest.append(w)
    except Exception:  # noqa: BLE001
        pass
    return wechsel, fest


def _eigene_ordner():
    """Desktop, Downloads und Dokumente des Windows-Benutzers – auch wenn Windows sie an einen anderen Ort verlegt hat."""
    heim = os.path.expanduser("~")
    aus = [os.path.join(heim, x) for x in ("Desktop", "Downloads", "Documents", "Dokumente")]
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                for name in ("Desktop", "Personal", "{374DE290-123F-4565-9164-39C4925E467B}"):
                    try:
                        aus.append(os.path.expandvars(str(winreg.QueryValueEx(k, name)[0])))
                    except OSError:
                        pass
        except Exception:  # noqa: BLE001
            pass
    return aus


def _unterordner(o, grenze=200):
    aus = []
    try:
        with os.scandir(o) as it:
            for e in it:
                if len(aus) >= grenze:
                    break
                try:
                    if e.is_dir(follow_symlinks=False) and not e.name.startswith(("$", ".")):
                        aus.append(e.path)
                except OSError:
                    continue
    except OSError:
        pass
    return aus


def _sicherungen_in(o, grenze=3000):
    """Sicherungsdateien direkt in diesem Ordner: Sicherung_….zip und buero_….db, auch verschlüsselt."""
    aus = []
    try:
        with os.scandir(o) as it:
            for i, e in enumerate(it):
                if i >= grenze:
                    break
                kern = _kern(e.name)
                if (kern.startswith("Sicherung_") and kern.endswith(".zip")) or (kern.startswith("buero_") and kern.endswith(".db")):
                    try:
                        if e.is_file():
                            aus.append(e.path)
                    except OSError:
                        continue
    except OSError:
        pass
    return aus


def kandidaten(basis, daten, weitere=()):
    """Datenbestände, die sich für die Übernahme anbieten: auf USB-Sticks und Festplatten, auf dem Desktop, unter Downloads
    und Dokumente sowie im Programmordner selbst (ein versehentlich eine Ebene zu tief kopierter Ordner). Gesucht wird nur
    in der obersten Ebene und eine darunter, höchstens einige Sekunden; alles andere gibt der Benutzer als Pfad an."""
    ende = time.time() + SUCH_SEKUNDEN
    fehlermodus = None
    if os.name == "nt":
        try:   # kein Windows-Fenster „Kein Datenträger im Laufwerk“, wenn ein leerer Kartenleser abgefragt wird
            import ctypes
            fehlermodus = ctypes.windll.kernel32.SetErrorMode(0x8001)   # SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX
        except Exception:  # noqa: BLE001
            pass
    try:
        return _kandidaten(basis, daten, weitere, ende)
    finally:
        if fehlermodus is not None:
            try:
                ctypes.windll.kernel32.SetErrorMode(fehlermodus)
            except Exception:  # noqa: BLE001
                pass


def _kandidaten(basis, daten, weitere, ende):
    wechsel, fest = _laufwerke()
    wurzeln = list(weitere) + wechsel + [daten, basis, os.path.dirname(os.path.abspath(basis))] + _eigene_ordner() + fest
    eigene = _ort(daten)
    eigene_sicherungen = _ort(os.path.join(daten, "backup"))
    ordner, dateien, gesehen = [], [], set()

    def merken(o):
        q = _datenordner(o)
        r = _ort(q) if q else ""
        if q and r != eigene and r not in gesehen and not eigene.startswith(os.path.join(r, "")):
            gesehen.add(r)
            ordner.append(q)

    def sicherungen(o):
        for x in (o, os.path.join(o, EXTERN_DB)):
            if _ort(x) != eigene_sicherungen and os.path.isdir(x):
                dateien.extend(_sicherungen_in(x))

    for w in dict.fromkeys(os.path.abspath(x) for x in wurzeln if x):
        if time.time() > ende:
            break
        if not os.path.isdir(w):
            continue
        merken(w)
        sicherungen(w)
        for u in _unterordner(w):
            if time.time() > ende:
                break
            merken(u)
            sicherungen(u)
    aus = []
    for q in ordner:
        try:
            b = db_beschreiben(os.path.join(q, "buero.db"))
        except (Fehler, OSError):
            continue
        if b["benutzer"]:
            aus.append({"art": "ordner", "pfad": q, **b})
    aus.sort(key=lambda x: x["stand"], reverse=True)
    voll, nur_db = [], []
    for f in dict.fromkeys(dateien):
        try:
            (voll if sicherungsart(f) == "sicherung" else nur_db).append(
                {"art": sicherungsart(f), "pfad": f, "firma": "", "version": "", "rechner": "", "verschluesselt": f.lower().endswith(tresor.ENDUNG),
                 "groesse": os.path.getsize(f), "stand": datetime.fromtimestamp(os.path.getmtime(f)).isoformat(timespec="minutes")})
        except OSError:
            continue
    for liste, n in ((voll, 4), (nur_db, 2)):
        liste.sort(key=lambda x: x["stand"], reverse=True)
        for e in liste[:n]:
            if not e["verschluesselt"]:
                try:   # nur die angezeigten genauer ansehen (Version, PC bzw. Inhalt)
                    e.update(_sicherung_beschreiben(e["art"], e["pfad"]))
                except (Fehler, OSError):
                    continue
            aus.append(e)
    return aus[:14]


DIALOG_PS = ("Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.Form -Property @{TopMost = $true}; $p = ''; "
             "if ($env:JR_ART -eq 'datei') { $d = New-Object System.Windows.Forms.OpenFileDialog; $d.Title = $env:JR_TITEL; $d.Filter = $env:JR_FILTER; "
             "if ($d.ShowDialog($f) -eq 'OK') { $p = $d.FileName } } "
             "else { $d = New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description = $env:JR_TITEL; $d.ShowNewFolderButton = $false; "
             "if ($d.ShowDialog($f) -eq 'OK') { $p = $d.SelectedPath } } "
             "Write-Output ('JR:' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($p)))")


def dialog_moeglich():
    return os.name == "nt"


def auswahl_dialog(art):
    """Auswahlfenster von Windows am PC selbst: Ordner (art „ordner“) oder Sicherungsdatei („datei“). Liefert den gewählten
    Pfad, einen leeren Text bei Abbruch und None, wenn sich das Fenster nicht öffnen ließ (dann bleibt die Eingabe des Pfads)."""
    if not dialog_moeglich():
        return None
    import base64
    import subprocess
    umgebung = dict(os.environ, JR_ART="datei" if art == "datei" else "ordner",
                    JR_TITEL=("Sicherungsdatei wählen" if art == "datei"
                              else "Den Ordner „daten“ vom bisherigen PC wählen (darin liegt die Datei buero.db)."),
                    JR_FILTER="Jahresring-Sicherungen (*.zip;*.jrs;*.db)|*.zip;*.jrs;*.db|Alle Dateien (*.*)|*.*")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", DIALOG_PS], env=umgebung,
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for zeile in r.stdout.decode("ascii", "ignore").splitlines():
            if zeile.strip().startswith("JR:"):
                return base64.b64decode(zeile.strip()[3:]).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001  kein PowerShell, Zeitüberschreitung, gesperrt
        pass
    return None


# ---------------------------------------------------------------- Dateipfade nach einem Ortswechsel
PFADSPALTEN = (("anhaenge", "pfad", "anhaenge", "groesse"), ("zahlungen", "datei", "eingangsrechnungen", ""))   # Tabelle, Spalte, Ordner, Spalte der Größe


def _umgesetzt(pfad, daten, ordnername):
    """Neuer Ort einer Datei, die unter <früherer Datenordner>/<ordnername>/… lag: derselbe Platz im Datenordner dieses PCs."""
    teile = [t for t in re.split(r"[\\/]+", str(pfad or "")) if t]
    klein = [t.lower() for t in teile]
    if ordnername not in klein:
        return ""
    rest = teile[len(klein) - klein[::-1].index(ordnername):]
    if not rest or any(t in (".", "..") for t in rest):
        return ""
    return os.path.join(daten, ordnername, *rest)


def pfade_anpassen(con, daten):
    """Stellt die mit vollem Pfad gespeicherten Dateien (Anhänge, Eingangsrechnungen) auf den Datenordner dieses PCs um, wenn
    der Bestand von einem anderen Ort kommt. Umgestellt wird nur, wenn die Datei im Datenordner dieses PCs liegt und dieselbe
    ist: Am gespeicherten Ort fehlt sie oder ist gleich groß, und eine gespeicherte Größe stimmt. Liefert {Tabelle: Anzahl}."""
    aus = {}
    for tabelle, spalte, ordnername, groesse in PFADSPALTEN:
        hier = os.path.normcase(os.path.join(os.path.abspath(daten), ordnername, ""))
        try:
            zeilen = con.execute(f"SELECT id, {spalte}, {groesse or '0'} FROM {tabelle} WHERE IFNULL({spalte},'')<>''").fetchall()
        except sqlite3.Error:
            continue
        n = 0
        for r in zeilen:
            alt = str(r[1])
            if not re.match(r"([A-Za-z]:)?[\\/]", alt) or os.path.normcase(os.path.abspath(alt)).startswith(hier):
                continue
            neu = _umgesetzt(alt, daten, ordnername)
            try:
                if not neu or not os.path.isfile(neu):
                    continue
                gr = os.path.getsize(neu)
                if (os.path.isfile(alt) and os.path.getsize(alt) != gr) or (r[2] and int(r[2]) != gr):
                    continue
            except (OSError, ValueError, TypeError):
                continue
            con.execute(f"UPDATE {tabelle} SET {spalte}=? WHERE id=?", (neu, r[0]))
            n += 1
        if n:
            aus[tabelle] = n
    return aus


# ---------------------------------------------------------------- Übernahme
def _dateiliste(q):
    """Alle Dateien des alten Datenordners, die mitkommen: (Quelle, Pfad relativ zum Datenordner mit „/“, Größe).
    Die alten Sicherungen (Ordner backup) kommen zuletzt."""
    aus = []
    for wurzel, ordner, dateien in os.walk(q):
        oben = _ort(wurzel) == _ort(q)
        ordner[:] = sorted(o for o in ordner if o != "__pycache__" and not (oben and o in AUSLASSEN))
        for d in sorted(dateien):
            voll = os.path.join(wurzel, d)
            rel = os.path.relpath(voll, q).replace(os.sep, "/")
            if rel in DB_DATEIEN or rel in AUSLASSEN_DATEIEN or os.path.islink(voll):
                continue
            try:
                aus.append((voll, rel, os.path.getsize(voll)))
            except OSError as f:
                raise Fehler(f"Die Datei {rel} lässt sich nicht lesen ({f.strerror or f}). Es wurde nichts übernommen.")
    aus.sort(key=lambda x: x[1].startswith("backup/"))
    return aus


def _platz_pruefen(ziel, bytes_):
    try:
        frei = shutil.disk_usage(ziel).free
    except OSError:
        return
    if bytes_ + 200 * 1024 * 1024 > frei:
        raise Fehler(f"Auf diesem PC ist zu wenig Platz: gebraucht werden etwa {_gb(bytes_)}, frei sind {_gb(frei)}.")


def _db_pruefen(pfad, eigene_version):
    """Die zu übernehmende Datenbank (Arbeitskopie): unbeschädigt, mit Benutzern, nicht aus einer neueren Programmversion.
    Liefert (Inhalt, fremd): fremd = das Journal dieses PCs gehört zu einem anderen Protokoll als dieser Bestand."""
    kaputt = Fehler("Die Datenbank dieses Bestands ist beschädigt oder unvollständig kopiert. Bitte am bisherigen PC Jahresring beenden "
                    "(Symbol neben der Uhr › Beenden) und den Ordner „daten“ noch einmal kopieren, oder eine Sicherung verwenden.")
    try:
        con = sqlite3.connect(pfad, timeout=10)
        ok = con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except sqlite3.Error:
        raise kaputt
    try:
        if not ok:
            raise kaputt
        inhalt = _inhalt(con)
        if not inhalt["benutzer"]:
            raise _ohne_benutzer()
        if version_zahl(inhalt["version"]) > version_zahl(eigene_version):
            raise Fehler(f"Dieser Datenbestand stammt aus der neueren Programmversion {inhalt['version']}. Bitte auf diesem PC zuerst "
                         "dieselbe oder eine neuere Version von Jahresring installieren.")
        return inhalt, protokoll.fremd(con)
    finally:
        con.close()


def _echtbetrieb_hier(cfg):
    con = sqlite3.connect(cfg["db"], timeout=30)
    con.row_factory = sqlite3.Row
    try:
        return protokoll.echtbetrieb(con)
    except sqlite3.Error:
        return None
    finally:
        con.close()


def _journal_frage(cfg, fremd):
    """Tritt das Journal des übernommenen Bestands an die Stelle des Journals dieses PCs? Ja, wenn dieses zu einem anderen
    Protokoll gehört (frischer PC) oder fehlt. Gehört es zum selben Protokoll (derselbe PC nach einem Datenbankschaden),
    bleibt es – es kann jüngere Einträge enthalten als die Sicherung."""
    if fremd and _echtbetrieb_hier(cfg):
        raise Fehler("Auf diesem PC liegt das Protokoll eines Datenbestands im Echtbetrieb, und der gewählte Bestand gehört nicht dazu. "
                     "Er wird deshalb nicht übernommen. Gehört der gewählte Bestand wirklich auf diesen PC, bitte den Betreuer hinzuziehen.", 409)
    return fremd or not protokoll.datei_lesen()


def _kopieren(von, nach):
    os.makedirs(os.path.dirname(nach), exist_ok=True)
    shutil.copyfile(von, nach)
    try:
        shutil.copystat(von, nach)
    except OSError:
        pass


def _entschluesselt(pfad, daten, kennwort, tmp):
    """Pfad der lesbaren Fassung einer Sicherung (verschlüsselte werden in den Arbeitsordner entschlüsselt)."""
    if not pfad.lower().endswith(tresor.ENDUNG):
        return pfad
    try:
        schluessel = tresor.schluessel_fuer(pfad, daten, kennwort or None)
        klar = os.path.join(tmp, "klar-" + _kern(os.path.basename(pfad)))
        STAND.update(schritt="Die Sicherung wird entschlüsselt")
        tresor.entschluesseln(pfad, klar, schluessel)
        return klar
    except tresor.Fehler as f:
        if str(f) == "KENNWORT_NOETIG":
            raise Fehler("Diese Sicherung ist verschlüsselt. Bitte das Sicherungskennwort eingeben.", 428)
        raise Fehler(str(f))
    except OSError as f:
        raise Fehler(f"Die Sicherung ließ sich nicht lesen ({f.strerror or f}).")


def uebernehmen(cfg, pfad, nach_db, kennwort=None):
    """Spielt den Datenbestand vom bisherigen PC ein. Der Aufrufer hat geprüft, dass auf diesem PC noch nichts erfasst ist.
    Reihenfolge: erst alles prüfen, dann die Dateien kopieren, zuletzt Datenbank und Journal tauschen – bricht das Kopieren ab
    (Datenträger abgezogen), sind die Daten dieses PCs unverändert und die Übernahme lässt sich wiederholen."""
    if not _lauf.acquire(blocking=False):
        raise Fehler("Die Übernahme läuft bereits.", 409)
    try:
        STAND.update(laeuft=True, schritt="Der Datenbestand wird geprüft", dateien=0, von=0, bytes=0, von_bytes=0)
        return _uebernehmen(cfg, pfad, nach_db, kennwort)
    finally:
        STAND.update(laeuft=False)
        _lauf.release()


def _uebernehmen(cfg, pfad, nach_db, kennwort):
    art, q = quelle_finden(pfad)
    daten = cfg["daten"]
    tmp = tempfile.mkdtemp(prefix="jr-ueb-")
    journal_neu = os.path.join(daten, "protokoll", "journal.jsonl.uebernahme")
    n = 0
    try:
        arbeits_db = os.path.join(tmp, "buero.db")
        if art == "ordner":
            _eigener_ordner(q, daten)
            # Datenbank mit -wal in einen Arbeitsordner: lief das alte Programm beim Kopieren noch, wird das Mitgeschriebene hier eingearbeitet
            for x in ("buero.db", "buero.db-wal", "buero.db-journal"):
                if os.path.exists(os.path.join(q, x)):
                    shutil.copyfile(os.path.join(q, x), os.path.join(tmp, x))
            inhalt, fremd = _db_pruefen(arbeits_db, cfg["version"])
            tauschen = _journal_frage(cfg, fremd)
            dateien = _dateiliste(q)
            _platz_pruefen(daten, sum(x[2] for x in dateien))
            STAND.update(schritt="Dateien werden kopiert", von=len(dateien), von_bytes=sum(x[2] for x in dateien))
            for voll, rel, groesse in dateien:
                ziel = os.path.join(daten, *rel.split("/"))
                if rel == JOURNAL:
                    ziel = journal_neu if tauschen else ""
                try:
                    if ziel:
                        _kopieren(voll, ziel)
                except OSError as f:
                    raise Fehler(f"Die Datei {rel} konnte nicht kopiert werden ({f.strerror or f}). Die Daten dieses PCs sind unverändert; "
                                 "die Übernahme lässt sich wiederholen.")
                n += 1
                STAND["dateien"], STAND["bytes"] = n, STAND["bytes"] + groesse
        elif art == "sicherung":
            klar = _entschluesselt(q, daten, kennwort, tmp)
            STAND.update(schritt="Die Sicherung wird geprüft")
            try:
                with zipfile.ZipFile(klar) as z:
                    if "buero.db" not in z.namelist() or z.testzip() is not None:
                        raise Fehler("Diese Sicherung ist beschädigt oder keine vollständige Jahresring-Sicherung.")
                    z.extract("buero.db", tmp)
                    inhalt, fremd = _db_pruefen(arbeits_db, cfg["version"])
                    tauschen = _journal_frage(cfg, fremd)
                    glieder = []
                    for m in z.infolist():
                        if not m.filename.startswith("dateien/") or m.is_dir():
                            continue
                        rel = m.filename[len("dateien/"):]
                        ziel = os.path.normpath(os.path.join(daten, *rel.split("/")))
                        if rel.split("/")[0] in AUSLASSEN or rel in DB_DATEIEN | AUSLASSEN_DATEIEN or not ziel.startswith(os.path.normpath(daten) + os.sep):
                            continue
                        glieder.append((m, journal_neu if rel == JOURNAL else ziel, rel))
                    _platz_pruefen(daten, sum(m.file_size for m, _, _ in glieder))
                    STAND.update(schritt="Dateien werden kopiert", von=len(glieder), von_bytes=sum(m.file_size for m, _, _ in glieder))
                    for m, ziel, rel in glieder:
                        if rel != JOURNAL or tauschen:
                            os.makedirs(os.path.dirname(ziel), exist_ok=True)
                            with z.open(m) as quelle, open(ziel, "wb") as w:
                                shutil.copyfileobj(quelle, w)
                        n += 1
                        STAND["dateien"], STAND["bytes"] = n, STAND["bytes"] + m.file_size
            except (zipfile.BadZipFile, OSError) as f:
                raise Fehler(f"Die Sicherung ließ sich nicht vollständig lesen ({getattr(f, 'strerror', None) or f}). "
                             "Die Daten dieses PCs sind unverändert; die Übernahme lässt sich wiederholen.")
        else:   # nur die Datenbank (tägliche Datenbanksicherung)
            klar = _entschluesselt(q, daten, kennwort, tmp)
            try:
                shutil.copyfile(klar, arbeits_db)
            except OSError as f:
                raise Fehler(f"Die Datenbanksicherung ließ sich nicht lesen ({f.strerror or f}).")
            inhalt, fremd = _db_pruefen(arbeits_db, cfg["version"])
            tauschen = _journal_frage(cfg, fremd)
        # ab hier wird dieser PC umgestellt: das Journal tauschen, dann den Datenbankinhalt ersetzen
        STAND.update(schritt="Die Datenbank wird eingerichtet")
        journal_alt, n_alt = "", 0
        try:
            if tauschen:
                journal_alt, n_alt = protokoll.journal_ersetzen(journal_neu if os.path.exists(journal_neu) else None, "vor_uebernahme")
        except OSError as f:
            raise Fehler(f"Das Protokoll dieses PCs ließ sich nicht beiseitelegen ({f.strerror or f}). Die Daten dieses PCs sind unverändert; "
                         "bitte die Übernahme wiederholen.")
        src = sqlite3.connect(arbeits_db)
        dst = sqlite3.connect(cfg["db"], timeout=30)
        try:
            with dst:
                src.backup(dst)
        except sqlite3.Error as f:
            if tauschen:
                protokoll.journal_zurueck(journal_alt)
            raise Fehler(f"Die Datenbank dieses PCs ließ sich nicht ersetzen ({f}). Die Daten dieses PCs sind unverändert; "
                         "bitte die Übernahme wiederholen.")
        finally:
            src.close()
            dst.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            os.remove(journal_neu)
        except OSError:
            pass
    nach_db()   # Datenbank auf die Programmversion dieses PCs bringen, Protokoll und Journal abgleichen, Dateipfade umstellen
    return {"ok": True, "art": art, "quelle": q, "dateien": n, "journal_alt": journal_alt, "journal_alt_eintraege": n_alt,
            "innen": art == "ordner" and _ort(q).startswith(os.path.join(_ort(daten), "")),
            "verschluesselt": q.lower().endswith(tresor.ENDUNG), **inhalt}
