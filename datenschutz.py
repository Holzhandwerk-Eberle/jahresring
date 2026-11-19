"""Jahresring – Datenschutz: Personenbezug von Lieferanten und ausgeschiedenen Mitarbeitern nach Ablauf der
Aufbewahrungsfristen entfernen (Art. 17 DSGVO). Zahlen (Beträge, Stunden, Zeiten) bleiben für Buchhaltung und Statistik.

Ausgelöst nur vom Inhaber, je Datensatz, nach Rückfrage. Ohne „ausfuehren“ liefern die Funktionen nur die Auskunft,
ob und ab wann anonymisiert werden darf. Die Fristen sind bewusst großzügig (10 Jahre ab Jahresende des letzten Belegs
bzw. des Austritts), damit keine steuerliche oder sozialversicherungsrechtliche Aufbewahrungspflicht verletzt wird.
"""
import hashlib
import html as _html
import json
import os
import re
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


def _frist(jahr, jahre=None):
    return f"{int(jahr) + int(jahre or JAHRE)}-12-31"


# ---------------------------------------------------------------- Kunden
# Wörter, die in Firmen- und Straßennamen vorkommen, aber niemanden erkennbar machen – sie bleiben in den Texten stehen
ALLERWELT = {"gmbh", "mbh", "kg", "ohg", "gbr", "ag", "ug", "ek", "co", "und", "the", "von", "der", "die", "das", "den", "dem", "des", "für", "bei", "mit",
             "familie", "firma", "herr", "herrn", "frau", "eheleute", "ehepaar", "schreinerei", "tischlerei", "zimmerei", "holzbau", "bau", "küchen",
             "möbel", "praxis", "büro", "gemeinde", "stadt", "verein", "hotel", "gasthof", "gasthaus", "restaurant", "architekt", "architekten",
             "architekturbüro", "ingenieurbüro", "immobilien", "verwaltung", "hausverwaltung", "straße", "strasse", "weg", "platz", "gasse", "ring",
             "allee", "hof", "haus", "alte", "alter", "neue", "neuer", "obere", "untere", "sankt"}
_BUCHSTABE = "A-Za-zÄÖÜäöüßéèêáàâóòôúùûñç"


def namensteile(k):
    """Wörter, an denen der Kunde in freien Texten zu erkennen ist: Vor- und Nachname, Kurzname, Firma, Straße."""
    person, weitere = set(), set()
    for feld, ziel in (("nachname", person), ("vorname", person), ("kurzname", weitere), ("firma", weitere), ("strasse", weitere), ("zusatz", weitere)):
        for wort in re.findall(rf"[{_BUCHSTABE}][{_BUCHSTABE}\-]{{2,}}", str(k.get(feld) or "")):
            for t in {wort, *wort.split("-")}:
                if len(t) >= 3 and t.lower() not in ALLERWELT:
                    ziel.add(t)
    return person, (weitere - person)


def _muster(teile):
    """Ganze Wörter in der Schreibweise des Namens (so bleibt die Farbe „weiß“ stehen, wenn der Kunde Weiß heißt), auch mit Genitiv-s."""
    if not teile:
        return None
    alle = sorted({t for x in teile for t in (x, x.upper())}, key=len, reverse=True)
    return re.compile(rf"(?<![{_BUCHSTABE}])(?:{'|'.join(re.escape(t) for t in alle)})(?:s|S)?(?![{_BUCHSTABE}])")


def schwaerzen_kurz(text, k):
    """Für Bezeichnungen und Betreffzeilen („Küche Müller“): jedes Namenswort wird durch „…“ ersetzt."""
    person, weitere = namensteile(k)
    m = _muster(person | weitere)
    return re.sub(r"(…\s*)+…", "…", m.sub("…", str(text))) if text and m else text


def schwaerzen_lang(text, k):
    """Für beschreibende Texte (Positionen, Bautagebuch): Ein Name wird dort entfernt, wo er als Name erkennbar ist – mit Anrede,
    mit Vornamen, oder als voller Vor- und Nachname. Ein Wort allein bleibt stehen: „Schrank“ beim Kunden Schrank ist die Ware.
    Solche einzeln stehenden Namensteile zeigt das Programm vor dem Anonymisieren und schwärzt sie auf Wunsch (fundstellen)."""
    if not text:
        return text
    person, _ = namensteile(k)
    t = str(text)
    nach = [x for x in re.findall(rf"[{_BUCHSTABE}][{_BUCHSTABE}\-]{{2,}}", str(k.get("nachname") or "")) if x.lower() not in ALLERWELT]
    vor = [x for x in re.findall(rf"[{_BUCHSTABE}][{_BUCHSTABE}\-]{{2,}}", str(k.get("vorname") or "")) if x.lower() not in ALLERWELT]
    if nach:
        n = "|".join(re.escape(x) for x in sorted(set(nach), key=len, reverse=True))
        v = "|".join(re.escape(x) for x in sorted(set(vor), key=len, reverse=True)) or "(?!)"
        anrede = r"(?:Herrn?|Frau|Familie|Fam\.|Eheleute|Ehepaar|Dr\.|Prof\.|Dipl\.-Ing\.)"
        t = re.sub(rf"{anrede}(?:\s+{anrede})*(?:\s+(?:{v}))?\s+(?:{n})(?:s|S)?(?![{_BUCHSTABE}])", "…", t)
        t = re.sub(rf"(?<![{_BUCHSTABE}])(?:{v})\s+(?:{n})(?:s|S)?(?![{_BUCHSTABE}])", "…", t)
        t = re.sub(rf"(?<![{_BUCHSTABE}])(?:{n}),?\s*(?:{v})(?![{_BUCHSTABE}])", "…", t)   # „Quittenbaum, Zacharias“ und „Quittenbaum Zacharias“
    for feld in ("email1", "email2", "email3", "email4", "telefon", "mobil", "telefax"):
        w = str(k.get(feld) or "").strip()
        if len(w) >= 6:
            t = t.replace(w, "…")
    strasse = " ".join(x for x in (str(k.get("strasse") or "").strip(), str(k.get("hausnr") or "").strip()) if x)
    if len(strasse) >= 6:
        t = t.replace(strasse, "…")
    return t


def _klartext(t):
    """Text ohne Formatierung in einer Zeile (zum Vergleichen und Zeigen)."""
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", " ", str(t or ""))
    return " ".join(_html.unescape(re.sub(r"<[^>]+>", "", t)).split())


def _fundstelle(text, kd, muster):
    """Bleibt nach der Regel für beschreibende Texte ein Namensteil als einzelnes Wort stehen („Sideboard Quittenbaum“, „Abholung
    durch Zacharias“)? → (Kennung des Textes, Klartext, gefundenes Wort) oder None. Gleiche Texte haben dieselbe Kennung –
    eine Position und ihre eingefrorene Zeile im Beleg sind damit eine Fundstelle."""
    if not text or not muster:
        return None
    klar = _klartext(schwaerzen_lang(text, kd))
    m = muster.search(klar)
    if not m:
        return None
    return hashlib.sha1(klar.encode("utf-8")).hexdigest()[:12], klar, m.group(0)


def _freitexte(con, kid, ids):
    """Alle freien Texte zu einem Kunden, in denen sein Name stehen kann: (Ort der Fundstelle, Text). Dieselbe Aufzählung dient der
    Vorschau (fundstellen) und entspricht den Stellen, die kunde() beim Ausführen bearbeitet."""
    ph = ",".join("?" * len(ids)) or "0"
    nr = {r["id"]: r["nummer"] for r in con.execute(f"SELECT id, nummer FROM auftraege WHERE id IN ({ph})", ids)}
    for p in con.execute(f"SELECT auftrag_id, text FROM positionen WHERE auftrag_id IN ({ph})", ids):
        yield f"Position in Auftrag {nr.get(p['auftrag_id'], '')}", p["text"]
    for b in con.execute(f"SELECT nummer, art, daten FROM belege WHERE auftrag_id IN ({ph}) OR kunde_id=?", (*ids, kid)):
        try:
            d = json.loads(b["daten"] or "{}")
        except ValueError:
            continue
        wo = f"Beleg {b['nummer'] or '(Entwurf)'}"
        for z in d.get("zeilen") or []:
            if isinstance(z, dict):
                yield wo, z.get("text")
                for u in z.get("unter") or []:
                    if isinstance(u, dict):
                        yield wo, u.get("text")
        for x in d.get("frei") or []:
            if isinstance(x, dict):
                yield wo, x.get("text")
        for vv in (d.get("abnahme") or {}).values() if isinstance(d.get("abnahme"), dict) else []:
            if isinstance(vv, str):
                yield wo + " (Abnahme)", vv
    if ids and _tabelle_da(con, "auftragskosten"):
        for r in con.execute(f"SELECT auftrag_id, bezeichnung, bemerkung FROM auftragskosten WHERE auftrag_id IN ({ph})", ids):
            yield f"Auftragskosten in Auftrag {nr.get(r['auftrag_id'], '')}", r["bezeichnung"]
            yield f"Auftragskosten in Auftrag {nr.get(r['auftrag_id'], '')}", r["bemerkung"]
    if ids:
        for r in con.execute(f"SELECT auftrag_id, taetigkeit FROM stunden WHERE auftrag_id IN ({ph}) AND IFNULL(taetigkeit,'')<>''", ids):
            yield f"Stundenbuchung in Auftrag {nr.get(r['auftrag_id'], '')}", r["taetigkeit"]
    if ids and _tabelle_da(con, "bautagebuch"):
        for e in con.execute(f"SELECT * FROM bautagebuch WHERE auftrag_id IN ({ph})", ids):
            for f in ("personal", "arbeiten", "material", "behinderungen", "maengel", "besonderes"):
                yield f"Bautagebuch vom {de_datum(e['datum'])}", e[f]
    for t in con.execute("SELECT von, titel, notiz FROM termine WHERE auftrag_id IS NULL AND (IFNULL(titel,'')<>'' OR IFNULL(notiz,'')<>'')"):
        yield f"Termin ohne Auftrag am {de_datum(t['von'])}", t["titel"]
        yield f"Termin ohne Auftrag am {de_datum(t['von'])}", t["notiz"]


def fundstellen(con, kid, kd, ids, hoechstens=300):
    """Vorschau zum Anonymisieren: Stellen, an denen ein Namensteil stehen bliebe. → [{id, text, wort, wo: [...]}]"""
    person, weitere = namensteile(kd)
    muster = _muster(person | weitere)
    funde = {}
    for wo, text in _freitexte(con, kid, ids):
        f = _fundstelle(text, kd, muster)
        if not f:
            continue
        e = funde.setdefault(f[0], {"id": f[0], "text": f[1][:220], "wort": f[2], "wo": []})
        if wo not in e["wo"] and len(e["wo"]) < 6:
            e["wo"].append(wo)
    return list(funde.values())[:hoechstens]


def kunde(con, kid, daten, ausfuehren=False, wer="", version="", hilfe=None, schwaerzen=None, mit_fundstellen=False):
    """Nach Ablauf der Aufbewahrungsfristen: Personenbezug eines Kunden entfernen (Art. 17 DSGVO).
    Zahlen (Beträge, Positionen, Stunden) bleiben für Statistik und Nachkalkulation erhalten; Postleitzahl und Ort bleiben für
    die Auswertung nach Gebieten stehen. hilfe: jahre_rechnung, rechnungsarten, beleg_dateien(beleg_id) → Pfade,
    montage_ordner(), bautagebuch_ordner(), korrespondenz_loeschen(con, kid, auftrag_ids).
    schwaerzen: Kennungen der Fundstellen (siehe fundstellen), an denen auch ein einzeln stehender Namensteil ersetzt wird."""
    hilfe = hilfe or {}
    k = con.execute("SELECT * FROM kunden WHERE id=?", (kid,)).fetchone()
    if not k:
        raise ApiFehler("Kunde nicht gefunden", 404)
    kd = dict(k)
    ids = [r["id"] for r in con.execute("SELECT id FROM auftraege WHERE kunde_id=?", (kid,))]
    ph = ",".join("?" * len(ids)) or "0"
    jahre_rechnung = int(hilfe.get("jahre_rechnung") or JAHRE)
    # Frist je Beleg: Rechnungen (Buchungsbelege) nach der eingestellten Frist, übrige Belege (Angebote, AB, Lieferscheine,
    # Handelsbriefe) 6 Jahre, jeweils ab Ende des Kalenderjahres; maßgeblich ist das späteste Fristende
    letzter, frist_ende = "", ""
    for b in con.execute(f"SELECT art, datum FROM belege WHERE (auftrag_id IN ({ph}) OR kunde_id=?) AND status<>'entwurf'", (*ids, kid)):
        d = b["datum"] or ""
        if not d[:4].isdigit():
            continue
        letzter = max(letzter, d)
        jahre = jahre_rechnung if b["art"] in (hilfe.get("rechnungsarten") or ()) else 6
        frist_ende = max(frist_ende, f"{int(d[:4]) + jahre}-12-31")
    for b in con.execute(f"SELECT datum FROM korrespondenz WHERE (kunde_id=? OR auftrag_id IN ({ph})) AND art LIKE 'mail%'", (kid, *ids)):
        d = b["datum"] or ""
        if d[:4].isdigit():
            frist_ende = max(frist_ende, f"{int(d[:4]) + 6}-12-31")   # geschäftliche E-Mails (Handelsbriefe)
    if (k["aufbewahren_bis"] or "") > frist_ende:   # Altbestand aus früheren Programmen oder von Hand gesetzt
        frist_ende = k["aufbewahren_bis"]
    offen = con.execute(f"SELECT COUNT(*) FROM offene_posten WHERE auftrag_id IN ({ph}) AND IFNULL(offen,0)>0.005", ids).fetchone()[0] if ids else 0
    erlaubt = (not frist_ende or frist_ende < date.today().isoformat()) and not offen
    info = {"offene_posten": offen, "kunde": k["kurzname"], "letzter_beleg": letzter, "frist_ende": frist_ende, "erlaubt": erlaubt, "auftraege": len(ids),
            "ordner": [r["ordner"] for r in con.execute(f"SELECT ordner FROM auftraege WHERE id IN ({ph}) AND IFNULL(ordner,'')<>''", ids)]}
    if not ausfuehren:
        if erlaubt and mit_fundstellen:   # was die Regeln stehen ließen: zur Entscheidung zeigen
            info["fundstellen"] = fundstellen(con, kid, kd, ids)
        return info
    if offen:
        raise ApiFehler("Es gibt noch offene Posten zu diesem Kunden.")
    if not erlaubt:
        raise ApiFehler(f"Die Aufbewahrungsfrist läuft noch bis {de_datum(frist_ende)}; vorher darf der Kunde nicht anonymisiert werden.")

    dateien = []

    def weg(pfad):
        rel = _weg(daten, pfad)
        if rel:
            dateien.append(rel)

    kurz = lambda t: schwaerzen_kurz(t, kd)   # noqa: E731
    wahl = {str(x) for x in schwaerzen or []}
    muster_alle = _muster(set().union(*namensteile(kd)))
    geschwaerzt = set()

    def lang(t):
        """Regel für beschreibende Texte. Bleibt danach ein Namensteil stehen und ist die Stelle zum Schwärzen ausgewählt, wird auch
        er ersetzt (jedes Namenswort durch „…“)."""
        neu = schwaerzen_lang(t, kd)
        f = _fundstelle(t, kd, muster_alle) if wahl else None
        if f and f[0] in wahl:
            geschwaerzt.add(f[0])
            return schwaerzen_kurz(neu, kd)
        return neu
    leer = {f: "" for f in ("vorname", "nachname", "titel", "firma", "strasse", "hausnr", "zusatz", "telefon", "mobil", "telefax", "email1",
                            "email2", "email3", "email4", "website", "bemerkungen", "merkmale", "ustid", "iban", "bic", "geburtstag",
                            "lieferanschrift", "lieferort", "rechnungsanschrift", "rechnungsort", "anrede", "leitweg_id", "lieferantennr")}
    spalten = _spalten(con, "kunden")
    werte = {f: v for f, v in leer.items() if f in spalten}
    werte.update({"kurzname": f"{X} ({k['nummer']})", "anschrift": X, "aktiv": 0, "geaendert": jetzt()})
    con.execute(f"UPDATE kunden SET {','.join(f + '=?' for f in werte)} WHERE id=?", (*werte.values(), kid))

    # Belege: Kundendaten, Anrede- und Schlusstext, Unterschrift; Namen in Betreff und Positionstexten; abgelegte Dateien
    behalten = ("nummer", "gruppe", "land", "ust", "preise", "zahlungsziel", "skonto", "skontotage")
    for b in con.execute(f"SELECT id, betreff, daten, pdf FROM belege WHERE auftrag_id IN ({ph}) OR kunde_id=?", (*ids, kid)).fetchall():
        for pfad in (hilfe["beleg_dateien"](b["id"]) if hilfe.get("beleg_dateien") else []) + [b["pdf"]]:
            weg(pfad)
        try:
            d = json.loads(b["daten"] or "{}")
        except ValueError:
            d = {}
        d["kunde"] = {**{kk: (vv if kk in behalten else "") for kk, vv in (d.get("kunde") or {}).items()}, "kurzname": X}
        d.pop("unterschrift", None)
        for z in d.get("zeilen") or []:
            if isinstance(z, dict):
                z["text"] = lang(z.get("text"))
                for u in z.get("unter") or []:
                    if isinstance(u, dict):
                        u["text"] = lang(u.get("text"))
        for x in d.get("frei") or []:
            if isinstance(x, dict):
                x["text"] = lang(x.get("text"))
        if isinstance(d.get("auftrag"), dict):
            d["auftrag"]["bezeichnung"] = kurz(d["auftrag"].get("bezeichnung"))
        if isinstance(d.get("abnahme"), dict):
            d["abnahme"] = {kk: (lang(vv) if isinstance(vv, str) else vv) for kk, vv in d["abnahme"].items()}
        con.execute("UPDATE belege SET anschrift=?, betreff=?, einleitung='', schluss='', versendet_an=CASE WHEN IFNULL(versendet_an,'')='' THEN '' ELSE ? END, daten=?, pdf='' WHERE id=?",
                    (X, kurz(b["betreff"]), X, json.dumps(d, ensure_ascii=False), b["id"]))
        if _tabelle_da(con, "beleg_versand"):
            con.execute("UPDATE beleg_versand SET an='', datei='' WHERE beleg_id=?", (b["id"],))
    if ids:
        for a in con.execute(f"SELECT id, bezeichnung FROM auftraege WHERE id IN ({ph})", ids).fetchall():
            con.execute("UPDATE auftraege SET kunde_daten=NULL, bezeichnung=?, bemerkungen='' WHERE id=?", (kurz(a["bezeichnung"]), a["id"]))
        for p in con.execute(f"SELECT id, text FROM positionen WHERE auftrag_id IN ({ph})", ids).fetchall():
            neu = lang(p["text"])
            if neu != p["text"]:
                con.execute("UPDATE positionen SET text=? WHERE id=?", (neu, p["id"]))
        for t in con.execute(f"SELECT id, titel FROM termine WHERE auftrag_id IN ({ph})", ids).fetchall():
            con.execute("UPDATE termine SET titel=?, notiz='' WHERE id=?", (kurz(t["titel"]), t["id"]))
        if "notiz" in _spalten(con, "zeiten"):
            con.execute(f"UPDATE zeiten SET notiz='' WHERE auftrag_id IN ({ph}) AND IFNULL(notiz,'')<>''", ids)
        if _tabelle_da(con, "auftragskosten"):
            for r in con.execute(f"SELECT id, bezeichnung, bemerkung FROM auftragskosten WHERE auftrag_id IN ({ph})", ids).fetchall():
                neu_b, neu_m = lang(r["bezeichnung"]), lang(r["bemerkung"])
                if (neu_b, neu_m) != (r["bezeichnung"], r["bemerkung"]):
                    con.execute("UPDATE auftragskosten SET bezeichnung=?, bemerkung=? WHERE id=?", (neu_b, neu_m, r["id"]))
        for r in con.execute(f"SELECT id, taetigkeit FROM stunden WHERE auftrag_id IN ({ph}) AND IFNULL(taetigkeit,'')<>''", ids).fetchall():
            neu = lang(r["taetigkeit"])
            if neu != r["taetigkeit"]:
                con.execute("UPDATE stunden SET taetigkeit=? WHERE id=?", (neu, r["id"]))
        for m in con.execute(f"SELECT id, unterschrift_kunde, unterschrift_monteur, pdf FROM montageberichte WHERE auftrag_id IN ({ph})", ids).fetchall():
            for datei in (m["unterschrift_kunde"], m["unterschrift_monteur"]):
                if datei and hilfe.get("montage_ordner"):
                    weg(os.path.join(hilfe["montage_ordner"](), datei))
            weg(m["pdf"])
            con.execute("UPDATE montageberichte SET kunde_name=?, unterschrift_kunde='', unterschrift_monteur='', anmerkungen='', pdf='' WHERE id=?", (X, m["id"]))
        if _tabelle_da(con, "bautagebuch"):
            for e in con.execute(f"SELECT * FROM bautagebuch WHERE auftrag_id IN ({ph})", ids).fetchall():
                try:
                    fotos = json.loads(e["fotos"] or "[]")
                except ValueError:
                    fotos = []
                for f in fotos:   # Fotos zeigen oft Wohnräume: Sie werden entfernt, der Text des Eintrags bleibt ohne Namen stehen
                    name = os.path.basename(str((f.get("datei") if isinstance(f, dict) else f) or ""))
                    if name and hilfe.get("bautagebuch_ordner"):
                        weg(os.path.join(hilfe["bautagebuch_ordner"](), name))
                con.execute("UPDATE bautagebuch SET personal=?, arbeiten=?, material=?, behinderungen=?, maengel=?, besonderes=?, fotos='[]' WHERE id=?",
                            (*(lang(e[f]) for f in ("personal", "arbeiten", "material", "behinderungen", "maengel", "besonderes")), e["id"]))
        con.execute(f"UPDATE briefe SET empfaenger=?, text='' WHERE auftrag_id IN ({ph})", (X, *ids))
        con.execute(f"DELETE FROM notizen WHERE auftrag_id IN ({ph})", ids)
    for b in con.execute(f"SELECT id, betreff, pdf FROM briefe WHERE kunde_id=? OR auftrag_id IN ({ph})", (kid, *ids)).fetchall():
        weg(b["pdf"])
        con.execute("UPDATE briefe SET empfaenger=?, text='', betreff=?, pdf='' WHERE id=?", (X, kurz(b["betreff"]), b["id"]))
    con.execute("DELETE FROM notizen WHERE kunde_id=?", (kid,))
    if wahl:   # Termine ohne Auftrag, in denen der Name steht: nur die ausgewählten
        for t in con.execute("SELECT id, titel, notiz FROM termine WHERE auftrag_id IS NULL AND (IFNULL(titel,'')<>'' OR IFNULL(notiz,'')<>'')").fetchall():
            neu_t, neu_n = lang(t["titel"]), lang(t["notiz"])
            if (neu_t, neu_n) != (t["titel"], t["notiz"]):
                con.execute("UPDATE termine SET titel=?, notiz=? WHERE id=?", (neu_t, neu_n, t["id"]))
    if _tabelle_da(con, "bank_kundenkonten"):   # gemerkte Zahlerkonten (IBAN, von der der Kunde schon bezahlt hat)
        con.execute("DELETE FROM bank_kundenkonten WHERE kunde_id=?", (kid,))
    if _tabelle_da(con, "projekte") and "kunde_id" in _spalten(con, "projekte"):
        for p in con.execute("SELECT id, bezeichnung FROM projekte WHERE kunde_id=?", (kid,)).fetchall():
            con.execute("UPDATE projekte SET bezeichnung=?, bemerkungen='' WHERE id=?", (kurz(p["bezeichnung"]), p["id"]))
    # Offene Posten, Zahlungseingänge, Mahnungen, zugeordnete Kontoumsätze
    ops = [r["id"] for r in con.execute(f"SELECT id FROM offene_posten WHERE kunde_id=? OR auftrag_id IN ({ph})", (kid, *ids))]
    if ops:
        op_ph = ",".join("?" * len(ops))
        con.execute(f"UPDATE zahlungseingaenge SET bemerkung='' WHERE op_id IN ({op_ph})", ops)
        if _tabelle_da(con, "mahnungen"):
            for m in con.execute(f"SELECT id, betreff, daten, pdf FROM mahnungen WHERE op_id IN ({op_ph})", ops).fetchall():
                weg(m["pdf"])
                try:
                    md = json.loads(m["daten"] or "{}")
                except ValueError:
                    md = {}
                md["kunde"] = {"nummer": (md.get("kunde") or {}).get("nummer"), "gruppe": (md.get("kunde") or {}).get("gruppe"), "kurzname": X}
                if isinstance(md.get("auftrag"), dict):
                    md["auftrag"]["bezeichnung"] = kurz(md["auftrag"].get("bezeichnung"))
                md.pop("projekt", None)
                md.pop("projekt_rel", None)
                con.execute("UPDATE mahnungen SET anschrift=?, betreff=?, text='', schluss='', daten=?, pdf='', versendet_an='' WHERE id=?",
                            (X, kurz(m["betreff"]), json.dumps(md, ensure_ascii=False), m["id"]))
        if _tabelle_da(con, "bank_umsaetze"):
            n_bank = 0
            for u in con.execute("SELECT id, ziel FROM bank_umsaetze WHERE ziel LIKE '%\"op\"%'").fetchall():
                try:
                    ziele = json.loads(u["ziel"] or "[]")
                except ValueError:
                    continue
                if any(isinstance(z, dict) and z.get("art") == "op" and z.get("id") in ops for z in ziele):
                    for z in ziele:
                        if isinstance(z, dict) and "text" in z:
                            z["text"] = kurz(z["text"])
                    con.execute("UPDATE bank_umsaetze SET name=?, zweck='', gegen_iban='', e2e='', notiz='', ziel=? WHERE id=?", (X, json.dumps(ziele, ensure_ascii=False), u["id"]))
                    n_bank += 1
            info["kontoumsaetze"] = n_bank
    n_k = hilfe["korrespondenz_loeschen"](con, kid, ids) if hilfe.get("korrespondenz_loeschen") else 0
    for a in con.execute(f"SELECT pfad FROM anhaenge WHERE kunde_id=? OR auftrag_id IN ({ph})", (kid, *ids)).fetchall():
        _weg(daten, a["pfad"])
    con.execute(f"DELETE FROM anhaenge WHERE kunde_id=? OR auftrag_id IN ({ph})", (kid, *ids))
    con.execute(f"DELETE FROM wiedervorlagen WHERE kunde_id=? OR auftrag_id IN ({ph})", (kid, *ids))
    bleibt = [f for f in fundstellen(con, kid, kd, ids)]   # was nach dem Ausführen noch stehen bleibt (nicht ausgewählte Stellen)
    protokoll.eintragen(con, "kunde_anonymisiert", f"Kunde {k['nummer']}", f"Kunde {k['nummer']} nach Ablauf der Aufbewahrungsfrist anonymisiert "
                        f"({len(dateien)} abgelegte Dateien entfernt"
                        + (f", {len(geschwaerzt)} Textstellen mit einzeln stehendem Namen geschwärzt" if geschwaerzt else "")
                        + (f", {len(bleibt)} auf Entscheidung des Benutzers belassen" if bleibt else "") + ")",
                        {"id": kid, "korrespondenz": n_k, "dateien": dateien, "geschwaerzt": len(geschwaerzt), "belassen": len(bleibt)}, benutzer=wer, version=version)
    return {**info, "erledigt": True, "korrespondenz": n_k, "dateien": len(dateien), "geschwaerzt": len(geschwaerzt), "belassen": len(bleibt)}


# ---------------------------------------------------------------- Lieferanten
def lieferant(con, lid, daten, ausfuehren=False, wer="", version="", jahre=None):
    """jahre: Aufbewahrungsfrist für Eingangsrechnungen (Buchungsbelege) laut Einstellung, sonst 10 Jahre."""
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
                frist_ende = max(frist_ende, _frist(d[:4], jahre))
    for tab, spalte, jahre_brief in (("korrespondenz", "datum", 6), ("briefe", "datum", 6)):
        if "lieferant_id" in _spalten(con, tab):
            for r in con.execute(f"SELECT {spalte} AS d FROM {tab} WHERE lieferant_id=?", (lid,)):
                d = r["d"] or ""
                if d[:4].isdigit():
                    frist_ende = max(frist_ende, f"{int(d[:4]) + jahre_brief}-12-31")
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
def faellig(con, kunde_info, jahre=None):
    """Wer darf jetzt anonymisiert (bzw. als Interessent gelöscht) werden? Für die jährliche Löschprüfung.
    kunde_info(con, id) liefert die Auskunft des Kunden (Frist, erlaubt) wie beim Knopf „Anonymisieren“."""
    heute = date.today()
    alt = heute.replace(year=heute.year - 3).isoformat()   # ohne Belege: 3 Jahre nach der letzten Änderung
    aus = {"kunden": [], "lieferanten": [], "mitarbeiter": []}
    # Kandidaten zuerst mit einer Abfrage eingrenzen: Wer in den letzten sechs Jahren einen Beleg bekommen hat oder noch eine
    # Aufbewahrungsfrist trägt, kann nicht fällig sein – für ihn braucht es die ausführliche Auskunft nicht (bei Tausenden Kunden
    # dauerte die Liste sonst über zehn Sekunden). Die ausführliche Prüfung entscheidet weiterhin für alle übrigen.
    grenze = f"{heute.year - 6}-01-01"
    for k in con.execute("SELECT k.id, k.nummer, k.kurzname, k.angelegt, k.geaendert FROM kunden k WHERE k.kurzname NOT LIKE ? "
                         "AND IFNULL(k.aufbewahren_bis,'')<? "
                         "AND NOT EXISTS (SELECT 1 FROM belege b WHERE b.kunde_id=k.id AND b.status<>'entwurf' AND b.datum>=?) "
                         "AND NOT EXISTS (SELECT 1 FROM belege b JOIN auftraege a ON a.id=b.auftrag_id WHERE a.kunde_id=k.id AND b.status<>'entwurf' AND b.datum>=?) "
                         "ORDER BY k.nummer", (X + "%", heute.isoformat(), grenze, grenze)).fetchall():
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
            i = lieferant(con, l["id"], "", jahre=jahre)
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
