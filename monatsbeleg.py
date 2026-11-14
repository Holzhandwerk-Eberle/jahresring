"""Jahresring – Unterschriften unter dem Monatsbeleg (Arbeitszeitnachweis): Fingerabdruck, Prüfung, Unterschreiben."""
import os
import re
from datetime import date

import benutzer
import personal
import unterschrift
from kern import ApiFehler

# von app.py gesetzt: daten, prot, ich_name
HILFE = {}


def monatsbeleg_hash(con, mid, monat):
    """Fingerabdruck dessen, was unterschrieben wird: die einzelnen Zeitbuchungen (Beginn, Ende, Auftrag, Tätigkeit),
    Abwesenheiten, Kontokorrekturen und die daraus gerechneten Tageswerte und Summen. Ändert sich davon etwas, gilt
    eine vorhandene Unterschrift als „Zeiten danach geändert“."""
    d = personal.monat_daten(con, mid, monat)
    von, bis = f"{monat}-01", f"{monat}-31"
    zeiten = [list(r) for r in con.execute("SELECT datum, beginn, IFNULL(ende,''), IFNULL(auftrag_id,0), kst, taetigkeit FROM zeiten "
                                           "WHERE mitarbeiter_id=? AND datum BETWEEN ? AND ? ORDER BY datum, beginn, id", (mid, von, bis))]
    abw = [list(r) for r in con.execute("SELECT art, von, bis, halbtag, status FROM abwesenheiten WHERE mitarbeiter_id=? AND bis>=? AND von<=? "
                                        "ORDER BY von, id", (mid, von, bis))]
    korr = [list(r) for r in con.execute("SELECT datum, konto, wert FROM kontobuchungen WHERE mitarbeiter_id=? AND datum BETWEEN ? AND ? "
                                         "ORDER BY datum, id", (mid, von, bis))]
    return unterschrift.inhalt_hash({"zeiten": zeiten, "abwesenheiten": abw, "korrekturen": korr,
                                     "tage": [{k: t.get(k) for k in ("datum", "ist", "soll", "pause", "abw", "urlaubstage", "saldo")} for t in d["tage"]],
                                     "summe": d["summe"]})


def monatsbeleg_hash_v1(con, mid, monat):
    """Fingerabdruck der Programmversionen bis 2026.11.01-129 (nur Tageswerte). Unterschriften aus dieser Zeit
    werden damit weiter geprüft, damit sie nach dem Update nicht fälschlich als „geändert“ gelten."""
    d = personal.monat_daten(con, mid, monat)
    return unterschrift.inhalt_hash({"tage": [{k: t.get(k) for k in ("datum", "beginn", "ende", "pause", "ist", "soll", "abw", "urlaubstage")} for t in d["tage"]],
                                     "summe": d["summe"], "korrekturen": [{k: x.get(k) for k in ("datum", "konto", "wert")} for x in d["korrekturen"]]})


def monatsbeleg_signaturen(con, mid, monat):
    """Letzte Unterschrift von Mitarbeiter und Arbeitgeber zu einem Monatsbeleg, mit Hinweis, ob sich die Zeiten seither geändert haben."""
    aktuell = monatsbeleg_hash(con, mid, monat)
    alt = None
    aus = {}
    for rolle in ("mitarbeiter", "arbeitgeber"):
        sig = unterschrift.letzte(con, "monatsbeleg", f"{mid}:{monat}", rolle)
        if not sig:
            aus[rolle] = None
            continue
        geaendert = sig["inhalt_sha256"] != aktuell
        if geaendert:   # Unterschrift aus einer älteren Version: mit deren Fingerabdruck prüfen (ein neuer kann damit nie übereinstimmen)
            alt = alt or monatsbeleg_hash_v1(con, mid, monat)
            geaendert = sig["inhalt_sha256"] != alt
        aus[rolle] = dict(unterschrift.oeffentlich(sig), geaendert=geaendert)
    return aus


def monatsbeleg_unterschreiben(con, mid, monat, rolle, d, wer, eigener=False):
    if not re.fullmatch(r"\d{4}-\d{2}", monat or ""):
        raise ApiFehler("Bitte den Monat angeben.")
    if monat > date.today().isoformat()[:7]:
        raise ApiFehler("Ein Monat in der Zukunft kann nicht unterschrieben werden.")
    m = con.execute("SELECT * FROM mitarbeiter WHERE id=?", (mid,)).fetchone()
    if not m:
        raise ApiFehler("Mitarbeiter nicht gefunden.", 404)
    if rolle not in ("mitarbeiter", "arbeitgeber"):
        raise ApiFehler("Unbekannte Rolle.")
    if rolle == "arbeitgeber" and (eigener or not benutzer.darf("personal", 2)):
        raise ApiFehler("Als Arbeitgeber unterschreibt der Inhaber bzw. wer Mitarbeiter bearbeiten darf.", 403)
    name = (d.get("name") or (f"{m['vorname']} {m['nachname']}".strip() if rolle == "mitarbeiter" else HILFE["ich_name"]())).strip()
    try:
        sig = unterschrift.speichern(con, os.path.join(HILFE["daten"], "unterschriften"), "monatsbeleg", f"{mid}:{monat}", rolle, name, d.get("png"), wer,
                                     mitarbeiter_id=mid if rolle == "mitarbeiter" else None, inhalt_sha=monatsbeleg_hash(con, mid, monat), geraet=d.get("geraet"))
    except unterschrift.Fehler as f:
        raise ApiFehler(str(f), f.code)
    HILFE["prot"](con, "unterschrift_monatsbeleg", f"{m['nummer']}:{monat}", f"Monatsbeleg {monat} von {m['vorname']} {m['nachname']} unterschrieben "
         f"({'Mitarbeiter' if rolle == 'mitarbeiter' else 'Arbeitgeber'}: {name})", {"signatur": sig["id"], "inhalt": sig["inhalt_sha256"]})
    return monatsbeleg_signaturen(con, mid, monat)


def monatsbeleg_sig_bilder(con, mid, monat):
    aus = {}
    sig = monatsbeleg_signaturen(con, mid, monat)
    for rolle in ("mitarbeiter", "arbeitgeber"):
        x = unterschrift.letzte(con, "monatsbeleg", f"{mid}:{monat}", rolle)
        if x:
            aus[rolle] = {"name": x["name"], "zeit": x["zeit"], "bild": unterschrift.bild_url(os.path.join(HILFE["daten"], "unterschriften"), x),
                          "geaendert": sig[rolle]["geaendert"]}
    return aus
