"""Sicherung des Projektordners auf das externe Sicherungsziel – nur was sich geändert hat.

Der Projektordner (Zeichnungen, Fotos, CAD-Dateien …) kann sehr groß werden; ihn jedes Mal ganz zu kopieren, dauert
irgendwann Stunden. Hier wird deshalb verglichen und nur Neues und Geändertes übertragen:

    <Sicherungsziel>/Jahresring-Projekte/aktuell/…              Spiegel des Projektordners (gleiche Ordnerstruktur)
    <Sicherungsziel>/Jahresring-Projekte/frueher/<Zeitpunkt>/…  was bei diesem Lauf ersetzt oder im Projektordner gelöscht war

Eine ersetzte oder gelöschte Datei wird also nie überschrieben, sondern in „frueher“ verschoben und dort erst nach der
eingestellten Zahl von Tagen entfernt. Damit lässt sich auch ein Stand von vor einem Versehen oder vor einem
Verschlüsselungstrojaner zurückholen. Mit Sicherungskennwort wird jede Datei einzeln verschlüsselt (Endung .jrs, siehe
tresor.py); Datei- und Ordnernamen bleiben dabei lesbar.

Verglichen wird ohne eigene Liste, nur über Größe und Änderungszeit von Quelle und Ziel – eine beschädigte oder fehlende
Liste kann deshalb nichts durcheinanderbringen, und ein abgebrochener Lauf wird beim nächsten Mal einfach fortgesetzt.
"""
import json
import os
import shutil
import threading
import time
from datetime import datetime, timedelta

import tresor

ORDNER = "Jahresring-Projekte"
AKTUELL, FRUEHER = "aktuell", "frueher"
WIEDER = "_Wiederhergestellt"                      # Unterordner des Projektordners für zurückgeholte Dateien; wird nicht gesichert
STEMPEL = "%Y-%m-%d_%H%M%S"
ZUSATZ = tresor.KOPF + 32                           # so viel größer ist eine verschlüsselte Datei
STANDARD = {"aktiv": False, "uhrzeit": "12:00", "tage": 90, "warn_tage": 3}
AUSLASSEN_NAMEN = {"thumbs.db", "desktop.ini", ".ds_store", "$recycle.bin", "system volume information"}
LAUF = {"laeuft": False, "art": "", "phase": "", "gesamt": 0, "erledigt": 0, "bytes": 0, "datei": "", "abbruch": False}
_sperre = threading.Lock()


class Fehler(Exception):
    pass


def _lang(p):
    """Unter Windows auch Pfade über 260 Zeichen erlauben (tief verschachtelte Projektordner)."""
    if os.name != "nt":
        return p
    p = os.path.abspath(p)
    if p.startswith("\\\\?\\"):
        return p
    return "\\\\?\\UNC\\" + p[2:] if p.startswith("\\\\") else "\\\\?\\" + p


def _auslassen(name):
    n = name.lower()
    return n in AUSLASSEN_NAMEN or n.startswith(("~$", ".~lock.")) or n.endswith((".tmp", ".part", ".crdownload"))


def _lesen(wurzel, ziel=False, unlesbar=None, oben_auslassen=()):
    """Alle Dateien unter wurzel: {Schlüssel: (relativer Pfad, Größe, Änderungszeit, verschlüsselt)}. Der Schlüssel ist der
    relative Pfad in einheitlicher Schreibweise (Windows unterscheidet Groß/Klein nicht), im Ziel ohne die Endung .jrs."""
    aus, leer = {}, []
    stapel = [""]
    while stapel:
        if LAUF["abbruch"]:
            raise Fehler("abgebrochen")
        rel = stapel.pop()
        try:
            with os.scandir(_lang(os.path.join(wurzel, rel)) if rel else _lang(wurzel)) as it:
                eintraege = list(it)
        except OSError as x:
            if not rel:
                raise
            if unlesbar is not None:
                unlesbar.append((rel, x.strerror or str(x)))
            continue
        if not eintraege and rel:
            leer.append(rel)
        for e in eintraege:
            r = os.path.join(rel, e.name) if rel else e.name
            try:
                if e.is_symlink() or getattr(e, "is_junction", lambda: False)():
                    continue                                        # Verknüpfungen nicht verfolgen (Schleifen, fremde Laufwerke)
                if e.is_dir(follow_symlinks=False):
                    if not rel and e.name in oben_auslassen or e.name.lower() in AUSLASSEN_NAMEN:
                        continue
                    stapel.append(r)
                    continue
                if not e.is_file(follow_symlinks=False):
                    continue
                st = e.stat(follow_symlinks=False)
            except OSError as x:
                if unlesbar is not None:
                    unlesbar.append((r, x.strerror or str(x)))
                continue
            if ziel:
                if e.name.endswith(".part"):
                    aus["\0teil\0" + r] = (r, 0, 0, False)             # Rest eines abgebrochenen Laufs
                    continue
                verschl = e.name.endswith(tresor.ENDUNG)
                kern = r[:-len(tresor.ENDUNG)] if verschl else r
                aus[os.path.normcase(kern)] = (r, st.st_size - (ZUSATZ if verschl else 0), st.st_mtime, verschl)
            else:
                if _auslassen(e.name) or e.name.endswith(tresor.ENDUNG):
                    continue                                        # .jrs im Projektordner sind bereits Sicherungsdateien
                aus[os.path.normcase(r)] = (r, st.st_size, st.st_mtime, False)
    aus["\0leer\0"] = leer
    return aus


def _gleich(q, z, verschluesseln):
    return z[3] == verschluesseln and q[1] == z[1] and abs(q[2] - z[2]) <= 2.0


def _verschieben(von, nach):
    os.makedirs(_lang(os.path.dirname(nach)), exist_ok=True)
    os.replace(_lang(von), _lang(nach))


def _leere_ordner_entfernen(wurzel, leer):
    """Leer gewordene Ordner im Spiegel entfernen (nur wirklich leere; rmdir scheitert sonst)."""
    for rel in sorted(leer, key=len, reverse=True):
        p = os.path.join(wurzel, rel)
        while len(p) > len(wurzel):
            try:
                os.rmdir(_lang(p))
            except OSError:
                break
            p = os.path.dirname(p)


def _status_datei(daten):
    return os.path.join(daten, "projektsicherung.json")


def status(daten):
    try:
        with open(_status_datei(daten), encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _status_schreiben(daten, **neu):
    d = {**status(daten), **neu}
    p = _status_datei(daten)
    with open(p + ".part", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(p + ".part", p)
    return d


def einstellung(wert):
    e = {**STANDARD, **(wert if isinstance(wert, dict) else {})}
    try:
        h, m = str(e["uhrzeit"]).split(":")
        e["uhrzeit"] = f"{min(23, max(0, int(h))):02d}:{min(59, max(0, int(m))):02d}"
    except ValueError:
        e["uhrzeit"] = STANDARD["uhrzeit"]
    try:
        e["tage"] = min(3650, max(0, int(e["tage"])))
    except (TypeError, ValueError):
        e["tage"] = STANDARD["tage"]
    try:
        e["warn_tage"] = min(365, max(1, int(e["warn_tage"])))
    except (TypeError, ValueError):
        e["warn_tage"] = STANDARD["warn_tage"]
    e["aktiv"] = bool(e["aktiv"])
    return e


def _pruefen(cfg):
    quelle, ziel = (cfg.get("projektpfad") or "").strip(), (cfg.get("ziel") or "").strip()
    if not quelle:
        raise Fehler("Es ist kein Projektordner eingestellt (Einstellungen › Programm).")
    if not ziel:
        raise Fehler("Es ist kein externes Sicherungsziel eingestellt (Einstellungen › Service › Datensicherung).")
    if not os.path.isdir(_lang(quelle)):
        raise Fehler(f"Der Projektordner {quelle} ist nicht erreichbar.")
    if not os.path.isdir(_lang(ziel)):
        raise Fehler(f"Das Sicherungsziel {ziel} ist nicht erreichbar. Ist das Laufwerk angeschlossen bzw. das Netzlaufwerk eingeschaltet?")
    a, b = os.path.normcase(os.path.abspath(quelle)), os.path.normcase(os.path.abspath(ziel))
    if a == b or b.startswith(a + os.sep) or a.startswith(b + os.sep):
        raise Fehler("Projektordner und Sicherungsziel dürfen nicht ineinander liegen.")
    return quelle, os.path.join(ziel, ORDNER)


def sichern(cfg, tage=90):
    """Ein Sicherungslauf. Liefert das Ergebnis (auch in daten/projektsicherung.json). Wirft Fehler, wenn gar nicht gesichert werden konnte."""
    if not _sperre.acquire(blocking=False):
        raise Fehler("Es läuft bereits eine Sicherung oder Wiederherstellung des Projektordners.")
    beginn = time.time()
    LAUF.update(laeuft=True, art="sichern", phase="Projektordner wird gelesen", gesamt=0, erledigt=0, bytes=0, datei="", abbruch=False)
    erg = {"zeit": datetime.now().isoformat(timespec="seconds"), "ok": False, "abgebrochen": False, "neu": 0, "geaendert": 0, "entfernt": 0,
           "gleich": 0, "umgestellt": 0, "bytes": 0, "fehler": [], "fehler_anzahl": 0, "verschluesselt": False, "hinweis": "", "aufgeraeumt": 0}

    def fehler(rel, text):
        erg["fehler_anzahl"] += 1
        if len(erg["fehler"]) < 50:
            erg["fehler"].append(f"{rel}: {text}")

    try:
        quelle, basis = _pruefen(cfg)
        schluessel = None
        if tresor.aktiv(cfg["daten"]):
            schluessel = tresor.laden(cfg["daten"])
            if not schluessel:   # nie unverschlüsselt ablegen, wenn ein Kennwort gesetzt ist
                raise Fehler("Der Schlüssel des Sicherungskennworts ist auf diesem PC nicht lesbar. Bitte das Sicherungskennwort unter "
                             "Service › Datensicherung neu setzen.")
        erg["verschluesselt"] = bool(schluessel)
        unlesbar = []
        q = _lesen(quelle, unlesbar=unlesbar, oben_auslassen=(WIEDER,))
        q.pop("\0leer\0")
        for rel, text in unlesbar:
            fehler(rel, f"nicht lesbar ({text})")
        aktuell = os.path.join(basis, AKTUELL)
        os.makedirs(_lang(aktuell), exist_ok=True)
        LAUF["phase"] = "Sicherungsziel wird gelesen"
        z = _lesen(aktuell, ziel=True)
        leer = z.pop("\0leer\0")
        for k in [k for k in z if k.startswith("\0teil\0")]:
            try:
                os.remove(_lang(os.path.join(aktuell, z.pop(k)[0])))
            except OSError:
                pass
        if not q and z:
            # Ein leerer Projektordner bei vorhandener Sicherung ist fast immer ein nicht verbundenes Laufwerk oder ein Unglück –
            # dann nichts als „gelöscht“ behandeln.
            raise Fehler(f"Der Projektordner {quelle} ist leer, die Sicherung enthält aber {len(z)} Dateien. Es wurde nichts verändert.")
        frueher = os.path.join(basis, FRUEHER, datetime.now().strftime(STEMPEL))
        # Was im Projektordner gerade nicht lesbar ist (gesperrter Ordner, Datei ohne Zugriff), gilt nicht als gelöscht
        gesperrt = tuple(os.path.normcase(rel) + os.sep for rel, _ in unlesbar)
        genau = {os.path.normcase(rel) for rel, _ in unlesbar}
        zu_kopieren = [(k, v) for k, v in q.items() if k not in z or not _gleich(v, z[k], bool(schluessel))]
        erg["gleich"] = len(q) - len(zu_kopieren)
        weg = [(k, v) for k, v in z.items() if k not in q and k not in genau and not (gesperrt and k.startswith(gesperrt))]
        LAUF.update(phase="Dateien werden gesichert", gesamt=len(zu_kopieren) + len(weg))
        # 1. Im Projektordner Gelöschtes aus dem Spiegel nach „frueher“ verschieben
        for k, v in weg:
            if LAUF["abbruch"]:
                raise Fehler("abgebrochen")
            try:
                _verschieben(os.path.join(aktuell, v[0]), os.path.join(frueher, v[0]))
                erg["entfernt"] += 1
                leer.append(os.path.dirname(v[0]))
            except OSError as x:
                fehler(v[0], f"konnte nicht nach „frueher“ verschoben werden ({x.strerror or x})")
            LAUF["erledigt"] += 1
        # 2. Neues und Geändertes übertragen; die bisherige Fassung wandert vorher nach „frueher“
        for k, v in sorted(zu_kopieren):
            if LAUF["abbruch"]:
                raise Fehler("abgebrochen")
            rel, groesse, mzeit, _ = v
            LAUF["datei"] = rel
            von = os.path.join(quelle, rel)
            nach = os.path.join(aktuell, rel) + (tresor.ENDUNG if schluessel else "")
            alt = z.get(k)
            try:
                os.makedirs(_lang(os.path.dirname(nach)), exist_ok=True)
                teil = nach + ".part"
                if schluessel:
                    tresor.verschluesseln(_lang(von), _lang(teil), schluessel[0], schluessel[1])
                else:
                    shutil.copyfile(_lang(von), _lang(teil))
                st = os.stat(_lang(von))
                if st.st_size != groesse or abs(st.st_mtime - mzeit) > 2.0:
                    os.remove(_lang(teil))
                    fehler(rel, "wurde während des Kopierens verändert – wird beim nächsten Lauf gesichert")
                    continue
                os.utime(_lang(teil), (mzeit, mzeit))
                if alt and alt[3] != bool(schluessel) and alt[1] == groesse and abs(alt[2] - mzeit) <= 2.0:
                    # gleicher Inhalt, nur die Form wechselt (Kennwort neu gesetzt oder abgeschaltet): erst die neue Datei, dann die alte weg
                    os.replace(_lang(teil), _lang(nach))
                    os.remove(_lang(os.path.join(aktuell, alt[0])))
                    erg["umgestellt"] += 1
                elif alt:
                    _verschieben(os.path.join(aktuell, alt[0]), os.path.join(frueher, alt[0]))
                    os.replace(_lang(teil), _lang(nach))
                    erg["geaendert"] += 1
                else:
                    os.replace(_lang(teil), _lang(nach))
                    erg["neu"] += 1
                erg["bytes"] += groesse
                LAUF["bytes"] = erg["bytes"]
            except (OSError, tresor.Fehler) as x:
                fehler(rel, getattr(x, "strerror", None) or str(x))
                try:
                    os.remove(_lang(nach + ".part"))
                except OSError:
                    pass
                if isinstance(x, OSError) and not os.path.isdir(_lang(aktuell)):
                    raise Fehler("Das Sicherungsziel ist während der Sicherung nicht mehr erreichbar.")
            LAUF["erledigt"] += 1
        _leere_ordner_entfernen(aktuell, leer)
        # 3. Frühere Fassungen nach Ablauf der Frist entfernen – aber nicht, wenn dieser Lauf auffällig viel ersetzt hat
        vorher = len(z)
        betroffen = erg["geaendert"] + erg["entfernt"]
        if vorher >= 50 and betroffen > max(200, vorher * 0.3):
            erg["hinweis"] = (f"Auffällig viele Dateien waren geändert oder gelöscht ({betroffen} von {vorher}). Die früheren Fassungen liegen im "
                              "Ordner „frueher“; das automatische Aufräumen ist ausgesetzt, bis ein Lauf wieder unauffällig ist. Bitte prüfen, "
                              "ob die Änderungen gewollt waren (Umräumen) oder ein Schaden vorliegt.")
        elif tage > 0:
            erg["aufgeraeumt"] = aufraeumen(basis, tage)
        erg["ok"] = True
    except Fehler as x:
        if str(x) == "abgebrochen":
            erg["abgebrochen"] = True
            erg["hinweis"] = "Die Sicherung wurde abgebrochen; der nächste Lauf macht dort weiter."
        else:
            erg["hinweis"] = str(x)
    except OSError as x:
        erg["hinweis"] = f"Sicherung nicht möglich: {x.strerror or x}"
    finally:
        erg["dauer"] = round(time.time() - beginn, 1)
        alt = status(cfg["daten"])
        neu = {"letzter": erg, "versuch": erg["zeit"]}
        if erg["ok"]:
            neu["letzter_erfolg"] = erg["zeit"]
            neu["fehler_folge"] = (alt.get("fehler_folge") or 0) + 1 if erg["fehler_anzahl"] else 0
        try:
            _status_schreiben(cfg["daten"], **neu)
        except OSError:
            pass
        LAUF.update(laeuft=False, phase="", datei="")
        _sperre.release()
    return erg


def aufraeumen(basis, tage):
    """Stände in „frueher“ entfernen, die älter als die eingestellte Zahl von Tagen sind. Liefert die Anzahl."""
    grenze = datetime.now() - timedelta(days=tage)
    n = 0
    try:
        namen = os.listdir(_lang(os.path.join(basis, FRUEHER)))
    except OSError:
        return 0
    for name in namen:
        try:
            zeit = datetime.strptime(name, STEMPEL)
        except ValueError:
            continue                                                # nur eigene Ordner anfassen
        if zeit < grenze:
            shutil.rmtree(_lang(os.path.join(basis, FRUEHER, name)), ignore_errors=True)
            n += 1
    return n


# ---------------------------------------------------------------- Zurückholen
def _basis(cfg):
    ziel = (cfg.get("ziel") or "").strip()
    if not ziel:
        raise Fehler("Es ist kein externes Sicherungsziel eingestellt.")
    return os.path.join(ziel, ORDNER)


def staende(cfg):
    """Vorhandene Stände: der aktuelle Spiegel und die früheren Fassungen (neueste zuerst)."""
    basis = _basis(cfg)
    aus = []
    if os.path.isdir(_lang(os.path.join(basis, AKTUELL))):
        aus.append({"stand": AKTUELL, "text": "Aktueller Stand der Sicherung"})
    try:
        namen = sorted(os.listdir(_lang(os.path.join(basis, FRUEHER))), reverse=True)
    except OSError:
        namen = []
    for n in namen:
        try:
            t = datetime.strptime(n, STEMPEL)
        except ValueError:
            continue
        aus.append({"stand": n, "text": f"Ersetzt oder gelöscht am {t:%d.%m.%Y} um {t:%H:%M} Uhr"})
    return aus


def _stand_pfad(cfg, stand, pfad=""):
    basis = _basis(cfg)
    if stand != AKTUELL:
        try:
            datetime.strptime(stand or "", STEMPEL)
        except ValueError:
            raise Fehler("Unbekannter Stand.")
    wurzel = os.path.join(basis, AKTUELL) if stand == AKTUELL else os.path.join(basis, FRUEHER, stand)
    teile = [t for t in str(pfad or "").replace("\\", "/").split("/") if t not in ("", ".")]
    if any(t == ".." or ":" in t for t in teile):
        raise Fehler("Ungültiger Pfad.")
    voll = os.path.join(wurzel, *teile) if teile else wurzel
    if not os.path.exists(_lang(voll)):
        raise Fehler("Diesen Ordner gibt es in dem gewählten Stand nicht.")
    return wurzel, voll, os.path.join(*teile) if teile else ""


def inhalt(cfg, stand, pfad=""):
    """Eine Ebene eines Stands zum Durchblättern: Unterordner und Dateien (Namen ohne .jrs)."""
    _, voll, rel = _stand_pfad(cfg, stand, pfad)
    ordner, dateien = [], []
    with os.scandir(_lang(voll)) as it:
        for e in it:
            if e.is_dir(follow_symlinks=False):
                ordner.append(e.name)
            elif e.is_file(follow_symlinks=False) and not e.name.endswith(".part"):
                v = e.name.endswith(tresor.ENDUNG)
                st = e.stat()
                dateien.append({"name": e.name[:-len(tresor.ENDUNG)] if v else e.name, "groesse": max(0, st.st_size - (ZUSATZ if v else 0)),
                                "zeit": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes"), "verschluesselt": v})
    return {"stand": stand, "pfad": rel.replace("\\", "/"), "ordner": sorted(ordner, key=str.lower), "dateien": sorted(dateien, key=lambda d: d["name"].lower())}


def _finden(cfg, stand, pfad):
    """Ordner oder Datei eines Stands; eine einzelne Datei kann verschlüsselt (mit .jrs) abgelegt sein."""
    try:
        wurzel, voll, _ = _stand_pfad(cfg, stand, pfad)
    except Fehler:
        if not pfad:
            raise
        wurzel, voll, _ = _stand_pfad(cfg, stand, str(pfad) + tresor.ENDUNG)
    return wurzel, voll


def _dateien_unter(voll):
    if os.path.isfile(_lang(voll)):
        return [_lang(voll)]
    aus = []
    for ordner, _, namen in os.walk(_lang(voll)):
        aus += [os.path.join(ordner, n) for n in namen if not n.endswith(".part")]
    return aus


def kennwort_pruefen(cfg, stand, pfad, kennwort=None):
    """Vor dem Zurückholen: Wird ein Kennwort gebraucht und stimmt es? Wirft tresor.Fehler("KENNWORT_NOETIG") bzw. Fehler."""
    _, voll = _finden(cfg, stand, pfad)
    for d in _dateien_unter(voll):
        if d.endswith(tresor.ENDUNG):
            k = tresor.schluessel_fuer(d, cfg["daten"], kennwort or None)
            if not tresor.pruefen(d, k):
                raise Fehler("Das Sicherungskennwort stimmt nicht oder die Datei ist beschädigt.")
            return True
    return False


def wiederherstellen(cfg, stand, pfad="", kennwort=None):
    """Einen Ordner (oder eine Datei) eines Stands in den Projektordner zurückholen – immer in einen neuen Unterordner
    „_Wiederhergestellt/<Zeitpunkt>/…“, damit nichts Vorhandenes überschrieben wird."""
    quelle = (cfg.get("projektpfad") or "").strip()
    if not quelle or not os.path.isdir(_lang(quelle)):
        raise Fehler("Der Projektordner ist nicht erreichbar.")
    wurzel, voll = _finden(cfg, stand, pfad)
    if not _sperre.acquire(blocking=False):
        raise Fehler("Es läuft bereits eine Sicherung oder Wiederherstellung des Projektordners.")
    erg = {"dateien": 0, "bytes": 0, "fehler": [], "abgebrochen": False}
    try:
        LAUF.update(laeuft=True, art="wiederherstellen", phase="Dateien werden gesucht", gesamt=0, erledigt=0, bytes=0, datei="", abbruch=False)
        dateien = _dateien_unter(voll)
        ziel_wurzel = os.path.join(quelle, WIEDER, f"{datetime.now():%Y-%m-%d_%H%M%S}_Stand_{stand}")
        erg["ordner"] = ziel_wurzel
        LAUF.update(phase="Dateien werden zurückgeholt", gesamt=len(dateien))
        lw = _lang(wurzel)
        for d in dateien:
            if LAUF["abbruch"]:
                erg["abgebrochen"] = True
                break
            rel = os.path.relpath(d, lw)
            v = rel.endswith(tresor.ENDUNG)
            nach = os.path.join(ziel_wurzel, rel[:-len(tresor.ENDUNG)] if v else rel)
            LAUF["datei"] = rel
            try:
                os.makedirs(_lang(os.path.dirname(nach)), exist_ok=True)
                mzeit = os.stat(d).st_mtime
                if v:
                    tresor.entschluesseln(d, _lang(nach), tresor.schluessel_fuer(d, cfg["daten"], kennwort or None))
                else:
                    shutil.copyfile(d, _lang(nach))
                os.utime(_lang(nach), (mzeit, mzeit))
                erg["dateien"] += 1
                erg["bytes"] += os.path.getsize(_lang(nach))
            except (OSError, tresor.Fehler) as x:
                try:
                    os.remove(_lang(nach))
                except OSError:
                    pass
                if len(erg["fehler"]) < 50:
                    erg["fehler"].append(f"{rel}: {'Sicherungskennwort nötig' if str(x) == 'KENNWORT_NOETIG' else getattr(x, 'strerror', None) or x}")
            LAUF["erledigt"] += 1
            LAUF["bytes"] = erg["bytes"]
    finally:
        LAUF.update(laeuft=False, phase="", datei="")
        LAUF["ergebnis"] = erg
        _sperre.release()
    return erg


# ---------------------------------------------------------------- Zeitplan und Warnung
def erreichbar(ziel):
    """Ist das Sicherungsziel gerade da (USB-Platte angesteckt, Netzlaufwerk verbunden)?"""
    try:
        return bool(ziel) and os.path.isdir(_lang(ziel))
    except OSError:
        return False


def faellig(daten, e, jetzt=None, ziel=None):
    """Soll jetzt automatisch gesichert werden? Einmal täglich ab der eingestellten Uhrzeit. Ist das Sicherungsziel nicht
    angeschlossen, wird still gewartet und gesichert, sobald es da ist; scheitert ein Lauf aus anderem Grund, stündlich neu."""
    if not e["aktiv"] or LAUF["laeuft"]:
        return False
    if ziel is not None and not erreichbar(ziel):
        return False
    jetzt = jetzt or datetime.now()
    if jetzt.strftime("%H:%M") < e["uhrzeit"]:
        return False
    s = status(daten)
    heute = jetzt.date().isoformat()
    if (s.get("letzter_erfolg") or "")[:10] == heute:
        return False
    versuch = s.get("versuch") or ""
    if versuch[:10] == heute and (s.get("letzter") or {}).get("abgebrochen"):
        return False                                                # von Hand abgebrochen: heute nicht von selbst neu beginnen
    try:
        return not versuch or jetzt - datetime.fromisoformat(versuch) >= timedelta(minutes=60)
    except ValueError:
        return True


def warnung(daten, e, jetzt=None):
    """Text für die Startseite, wenn die automatische Sicherung des Projektordners nicht läuft."""
    if not e["aktiv"]:
        return ""
    s = status(daten)
    jetzt = jetzt or datetime.now()
    seit = s.get("letzter_erfolg") or s.get("eingeschaltet") or ""
    try:
        tage = (jetzt - datetime.fromisoformat(seit)).days if seit else 0
    except ValueError:
        tage = 0
    letzter = s.get("letzter") or {}
    if tage >= e["warn_tage"]:
        grund = letzter.get("hinweis") or ""
        return (f"Der Projektordner wurde seit {tage} Tagen nicht auf das externe Sicherungsziel gesichert." + (f" {grund}" if grund else "")
                + " Einstellungen › Service › Projektordner sichern.")
    if letzter.get("ok") and letzter.get("hinweis"):
        return "Sicherung des Projektordners: " + letzter["hinweis"]
    if (s.get("fehler_folge") or 0) >= 3:
        return (f"Bei der Sicherung des Projektordners konnten wiederholt Dateien nicht gesichert werden ({letzter.get('fehler_anzahl', 0)} beim letzten Lauf). "
                "Einstellungen › Service › Projektordner sichern.")
    return ""
