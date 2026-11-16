"""Jahresring – Datenschutz: Personenbezug von Lieferanten und ausgeschiedenen Mitarbeitern nach Ablauf der
Aufbewahrungsfristen entfernen (Art. 17 DSGVO). Zahlen (Beträge, Stunden, Zeiten) bleiben für Buchhaltung und Statistik.

Ausgelöst nur vom Inhaber, je Datensatz, nach Rückfrage. Ohne „ausfuehren“ liefern die Funktionen nur die Auskunft,
ob und ab wann anonymisiert werden darf. Die Fristen sind bewusst großzügig (10 Jahre ab Jahresende des letzten Belegs
bzw. des Austritts), damit keine steuerliche oder sozialversicherungsrechtliche Aufbewahrungspflicht verletzt wird.
"""
import os
import secrets
from datetime import date, datetime

import protokoll
from kern import ApiFehler, de_datum

JAHRE = 10
X = "anonymisiert"


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def _spalten(con, tabelle):
    return {r[1] for r in con.execute(f"PRAGMA table_info({tabelle})")}


def _tabelle_da(con, tabelle):
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabelle,)).fetchone())


def _weg(daten, pfad):
    """Datei löschen, aber nur innerhalb des Datenordners. Gibt den Pfad relativ zum Datenordner zurück (oder leer)."""
    if not pfad:
        return ""
    voll = os.path.normpath(pfad if os.path.isabs(pfad) else os.path.join(daten, pfad))
    basis = os.path.join(os.path.abspath(daten), "")
    if os.path.abspath(voll).startswith(basis) and os.path.isfile(voll):
        try:
            os.remove(voll)
        except OSError:
            return ""
        return os.path.relpath(voll, daten).replace(os.sep, "/")
    return ""


def _frist(jahr):
    return f"{int(jahr) + JAHRE}-12-31"


# ---------------------------------------------------------------- Lieferanten
def lieferant(con, lid, daten, ausfuehren=False, wer="", version=""):
    l = con.execute("SELECT * FROM lieferanten WHERE id=?", (lid,)).fetchone()
    if not l:
        raise ApiFehler("Lieferant nicht gefunden", 404)
    if (l["gruppe"] or "") == "Mitarbeiter":
        raise ApiFehler("Dieser Eintrag gehört zu einem Mitarbeiter (Lohnzahlungen) und wird zusammen mit dem Mitarbeiter anonymisiert.")
    letzter, frist_ende = "", ""
    for r in con.execute("SELECT belegdatum, bezahlt FROM zahlungen WHERE lieferant_id=?", (lid,)):
        for d in (r["belegdatum"] or "", r["bezahlt"] or ""):
            if d[:4].isdigit():
                letzter = max(letzter, d[:10])
                frist_ende = max(frist_ende, _frist(d[:4]))
    for tab, spalte, jahre in (("korrespondenz", "datum", 6), ("briefe", "datum", 6)):
        if "lieferant_id" in _spalten(con, tab):
            for r in con.execute(f"SELECT {spalte} AS d FROM {tab} WHERE lieferant_id=?", (lid,)):
                d = r["d"] or ""
                if d[:4].isdigit():
                    frist_ende = max(frist_ende, f"{int(d[:4]) + jahre}-12-31")
    offen = con.execute("SELECT COUNT(*) FROM zahlungen WHERE lieferant_id=? AND IFNULL(bezahlt,'')=''", (lid,)).fetchone()[0]
    material = con.execute("SELECT COUNT(*) FROM material WHERE lieferant_id=? AND aktiv=1", (lid,)).fetchone()[0]
    erlaubt = (not frist_ende or frist_ende < date.today().isoformat()) and not offen
    info = {"name": l["kurzname"], "letzter_beleg": letzter, "frist_ende": frist_ende, "offen": offen, "material": material, "erlaubt": erlaubt}
    if not ausfuehren:
        return info
    if offen:
        raise ApiFehler(f"Es gibt noch {offen} unbezahlte Zahlungsaufträge zu diesem Lieferanten.")
    if not erlaubt:
        raise ApiFehler(f"Die Aufbewahrungsfrist läuft noch bis {de_datum(frist_ende)}; vorher darf der Lieferant nicht anonymisiert werden.")
    sp = _spalten(con, "lieferanten")
    leer = [f for f in ("anschrift", "plz", "ort", "anrede", "telefon", "email1", "email2", "email3", "email4", "telefax", "website", "bemerkungen",
                        "merkmale", "unsere_kundennr", "info_zahlung", "iban", "bic", "anredeform", "titel", "vorname", "nachname", "firma", "zusatz",
                        "strasse", "hausnr", "ustid") if f in sp]
    werte = {**{f: "" for f in leer}, "kurzname": f"{X} ({l['nummer']})", "empfaenger": X, "aktiv": 0, "geaendert": jetzt()}
    con.execute(f"UPDATE lieferanten SET {','.join(f + '=?' for f in werte)} WHERE id=?", (*werte.values(), lid))
    dateien = []
    for z in con.execute("SELECT id, datei FROM zahlungen WHERE lieferant_id=?", (lid,)).fetchall():
        rel = _weg(daten, z["datei"])
        if rel:
            dateien.append(rel)
    con.execute("UPDATE zahlungen SET empfaenger=?, iban='', bic='', bemerkung='', datei='' WHERE lieferant_id=?", (X, lid))
    n = 0
    for r in con.execute("SELECT id, datei FROM korrespondenz WHERE lieferant_id=?", (lid,)).fetchall():
        _weg(daten, r["datei"])
        n += 1
    con.execute("DELETE FROM korrespondenz WHERE lieferant_id=?", (lid,))
    con.execute("UPDATE briefe SET empfaenger=?, text='' WHERE lieferant_id=?", (X, lid))
    con.execute("DELETE FROM notizen WHERE lieferant_id=?", (lid,))
    for a in con.execute("SELECT pfad FROM anhaenge WHERE lieferant_id=?", (lid,)).fetchall():
        _weg(daten, a["pfad"])
    con.execute("DELETE FROM anhaenge WHERE lieferant_id=?", (lid,))
    if _tabelle_da(con, "rechnungspost"):
        for r in con.execute("SELECT datei FROM rechnungspost WHERE lieferant_id=?", (lid,)).fetchall():
            _weg(daten, r["datei"])
        con.execute("DELETE FROM rechnungspost WHERE lieferant_id=?", (lid,))
    if _tabelle_da(con, "wiedervorlagen") and "lieferant_id" in _spalten(con, "wiedervorlagen"):
        con.execute("DELETE FROM wiedervorlagen WHERE lieferant_id=?", (lid,))
    protokoll.eintragen(con, "anonymisiert", f"Lieferant {l['nummer']}", f"Lieferant {l['nummer']} nach Ablauf der Aufbewahrungsfrist anonymisiert "
                        f"({len(dateien)} abgelegte Rechnungsdateien entfernt)", {"art": "lieferant", "id": lid, "dateien": dateien, "korrespondenz": n},
                        benutzer=wer, version=version)
    return {**info, "erledigt": True, "dateien": len(dateien), "korrespondenz": n}


# ---------------------------------------------------------------- Mitarbeiter
def mitarbeiter(con, mid, daten, ausfuehren=False, wer="", version="", sig_ordner=()):
    m = con.execute("SELECT * FROM mitarbeiter WHERE id=?", (mid,)).fetchone()
    if not m:
        raise ApiFehler("Mitarbeiter nicht gefunden", 404)
    austritt = (m["austritt"] or "")[:10]
    letzter = austritt
    for sql in ("SELECT MAX(datum) FROM zeiten WHERE mitarbeiter_id=?", "SELECT MAX(monat) || '-28' FROM lohn WHERE mitarbeiter_id=?",
                "SELECT MAX(bis) FROM abwesenheiten WHERE mitarbeiter_id=?"):
        d = con.execute(sql, (mid,)).fetchone()[0] or ""
        if d[:4].isdigit():
            letzter = max(letzter, d[:10])
    frist_ende = _frist(letzter[:4]) if letzter[:4].isdigit() else ""
    expo = ""
    if _tabelle_da(con, "as_exposition"):
        # Expositionsverzeichnis (krebserzeugende Stoffe): 40 Jahre nach Ende der Exposition aufzubewahren – mit Namen
        for r in con.execute("SELECT bis FROM as_exposition WHERE mitarbeiter_id=?", (mid,)):
            ende = (r["bis"] or austritt or date.today().isoformat())[:10]
            expo = max(expo, f"{int(ende[:4]) + 40}-12-31")
        frist_ende = max(frist_ende, expo)
    erlaubt = bool(austritt) and austritt < date.today().isoformat() and (not frist_ende or frist_ende < date.today().isoformat())
    name = " ".join(x for x in (m["vorname"], m["nachname"]) if x)
    info = {"name": name, "austritt": austritt, "letzter_eintrag": letzter, "frist_ende": frist_ende, "erlaubt": erlaubt, "exposition": bool(expo)}
    if not ausfuehren:
        return info
    if not austritt:
        raise ApiFehler("Anonymisiert werden nur ausgeschiedene Mitarbeiter. Bitte zuerst das Austrittsdatum eintragen.")
    if not erlaubt:
        raise ApiFehler(f"Die Aufbewahrungsfrist (Lohn- und Zeitunterlagen{', Expositionsverzeichnis 40 Jahre' if expo else ''}) läuft noch bis {de_datum(frist_ende)}; vorher darf der Mitarbeiter nicht anonymisiert werden.")
    sp = _spalten(con, "mitarbeiter")
    leer = [f for f in ("vorname", "kuerzel", "strasse", "plz", "ort", "telefon", "email", "iban", "bic", "bemerkungen", "geburtsdatum") if f in sp]
    werte = {**{f: "" for f in leer}, "nachname": f"{X} ({m['nummer']})", "aktiv": 0, "geaendert": jetzt()}
    con.execute(f"UPDATE mitarbeiter SET {','.join(f + '=?' for f in werte)} WHERE id=?", (*werte.values(), mid))
    con.execute("UPDATE abwesenheiten SET notiz='' WHERE mitarbeiter_id=?", (mid,))
    con.execute("UPDATE zeiten SET notiz='' WHERE mitarbeiter_id=?", (mid,))
    con.execute("UPDATE lohn SET notiz='' WHERE mitarbeiter_id=?", (mid,))
    if _tabelle_da(con, "kontobuchungen"):
        con.execute("UPDATE kontobuchungen SET text='' WHERE mitarbeiter_id=?", (mid,))
    if _tabelle_da(con, "stempel_ereignisse"):
        con.execute("DELETE FROM stempel_ereignisse WHERE mitarbeiter_id=?", (mid,))
    # Zugang zur Stempeluhr
    for b in con.execute("SELECT id FROM benutzer WHERE mitarbeiter_id=?", (mid,)).fetchall():
        con.execute("DELETE FROM sitzungen WHERE benutzer_id=?", (b["id"],))
        con.execute("UPDATE benutzer SET aktiv=0, name=?, login=?, email='', pw_hash=?, notfall_hash='' WHERE id=?",
                    (X, f"anonym-{b['id']}", "gesperrt$" + secrets.token_hex(8), b["id"]))
    # Unterschriften (Monatsbelege, Unterweisungen): Bild löschen, Name entfernen – der Vorgang selbst bleibt nachweisbar
    bilder = 0
    for s in con.execute("SELECT id, datei FROM signaturen WHERE mitarbeiter_id=?", (mid,)).fetchall():
        for o in sig_ordner:
            if s["datei"] and _weg(daten, os.path.join(o, os.path.basename(s["datei"]))):
                bilder += 1
        con.execute("UPDATE signaturen SET name=?, geraet='' WHERE id=?", (X, s["id"]))
    # Arbeitsschutz: Teilnahme an Unterweisungen ohne Namen, Qualifikationen und deren Nachweise entfernen
    if _tabelle_da(con, "as_vorsorge"):   # Vorsorgekartei: nach Ende der Beschäftigung zu löschen (ArbMedVV)
        con.execute("DELETE FROM as_vorsorge WHERE mitarbeiter_id=?", (mid,))
    if _tabelle_da(con, "as_exposition"):
        con.execute("DELETE FROM as_exposition WHERE mitarbeiter_id=?", (mid,))
    if _tabelle_da(con, "as_teilnehmer"):
        con.execute("UPDATE as_teilnehmer SET name=? WHERE mitarbeiter_id=?", (X, mid))
    if _tabelle_da(con, "as_qualifikationen"):
        qids = [r[0] for r in con.execute("SELECT id FROM as_qualifikationen WHERE mitarbeiter_id=?", (mid,))]
        if qids and _tabelle_da(con, "as_dateien"):
            ph = ",".join("?" * len(qids))
            for d in con.execute(f"SELECT pfad FROM as_dateien WHERE qualifikation_id IN ({ph})", qids).fetchall():
                _weg(daten, d["pfad"])
            con.execute(f"DELETE FROM as_dateien WHERE qualifikation_id IN ({ph})", qids)
        con.execute("DELETE FROM as_qualifikationen WHERE mitarbeiter_id=?", (mid,))
    if _tabelle_da(con, "as_verbandbuch") and m["nachname"] and m["vorname"]:
        con.execute("UPDATE as_verbandbuch SET name=? WHERE name LIKE ? AND name LIKE ?", (X, f"%{m['nachname']}%", f"%{m['vorname']}%"))
    # Lohnzahlungen laufen über einen Lieferanten-Eintrag der Gruppe „Mitarbeiter“
    lid = m["lieferant_id"] if "lieferant_id" in sp else None
    if lid and con.execute("SELECT 1 FROM lieferanten WHERE id=? AND gruppe='Mitarbeiter'", (lid,)).fetchone():
        lsp = _spalten(con, "lieferanten")
        lw = {f: "" for f in ("anschrift", "plz", "ort", "telefon", "email1", "iban", "bic", "bemerkungen", "vorname", "nachname", "strasse", "hausnr") if f in lsp}
        lw.update({"kurzname": f"{X} (Mitarbeiter {m['nummer']})", "empfaenger": X, "aktiv": 0, "geaendert": jetzt()})
        con.execute(f"UPDATE lieferanten SET {','.join(f + '=?' for f in lw)} WHERE id=?", (*lw.values(), lid))
        con.execute("UPDATE zahlungen SET empfaenger=?, iban='', bic='', bemerkung='' WHERE lieferant_id=?", (X, lid))
    protokoll.eintragen(con, "anonymisiert", f"Mitarbeiter {m['nummer']}", f"Mitarbeiter {m['nummer']} nach Ablauf der Aufbewahrungsfrist anonymisiert",
                        {"art": "mitarbeiter", "id": mid, "unterschriften": bilder}, benutzer=wer, version=version)
    return {**info, "erledigt": True}


# ---------------------------------------------------------------- Löschliste
def faellig(con, kunde_info):
    """Wer darf jetzt anonymisiert (bzw. als Interessent gelöscht) werden? Für die jährliche Löschprüfung.
    kunde_info(con, id) liefert die Auskunft des Kunden (Frist, erlaubt) wie beim Knopf „Anonymisieren“."""
    heute = date.today()
    alt = heute.replace(year=heute.year - 3).isoformat()   # ohne Belege: 3 Jahre nach der letzten Änderung
    aus = {"kunden": [], "lieferanten": [], "mitarbeiter": []}
    for k in con.execute("SELECT id, nummer, kurzname, angelegt, geaendert FROM kunden WHERE kurzname NOT LIKE ? ORDER BY nummer", (X + "%",)).fetchall():
        try:
            i = kunde_info(con, k["id"])
        except ApiFehler:
            continue
        if not i.get("erlaubt"):
            continue
        ohne = not i.get("frist_ende")
        if ohne and (k["geaendert"] or k["angelegt"] or "9999")[:10] > alt:
            continue   # Interessent ohne Belege, aber noch frisch
        aus["kunden"].append({"id": k["id"], "nummer": k["nummer"], "name": k["kurzname"], "frist_ende": i.get("frist_ende") or "",
                              "letzter": i.get("letzter_beleg") or (k["geaendert"] or k["angelegt"] or "")[:10], "ohne_belege": ohne, "auftraege": i.get("auftraege", 0)})
    for l in con.execute("SELECT id, nummer, kurzname, gruppe, angelegt, geaendert FROM lieferanten WHERE kurzname NOT LIKE ? "
                         "AND IFNULL(gruppe,'') NOT IN ('Mitarbeiter','Finanzamt','Krankenkasse') ORDER BY nummer", (X + "%",)).fetchall():
        try:
            i = lieferant(con, l["id"], "")
        except ApiFehler:
            continue
        if not i["erlaubt"]:
            continue
        ohne = not i["frist_ende"]
        if ohne and ((l["geaendert"] or l["angelegt"] or "9999")[:10] > alt or i["material"]):
            continue   # ohne Rechnungen: nur melden, wenn seit drei Jahren unverändert und kein Material mehr daran hängt
        aus["lieferanten"].append({"id": l["id"], "nummer": l["nummer"], "name": l["kurzname"], "frist_ende": i["frist_ende"],
                                   "letzter": i["letzter_beleg"] or (l["geaendert"] or l["angelegt"] or "")[:10], "ohne_belege": ohne})
    for m in con.execute("SELECT id, nummer, vorname, nachname FROM mitarbeiter WHERE IFNULL(austritt,'')<>'' AND nachname NOT LIKE ? ORDER BY nummer", (X + "%",)).fetchall():
        i = mitarbeiter(con, m["id"], "")
        if i["erlaubt"]:
            aus["mitarbeiter"].append({"id": m["id"], "nummer": m["nummer"], "name": i["name"], "frist_ende": i["frist_ende"], "letzter": i["austritt"]})
    aus["anzahl"] = sum(len(v) for v in aus.values())
    return aus
