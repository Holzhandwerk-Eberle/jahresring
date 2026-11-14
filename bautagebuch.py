"""Bautagebuch: Tageseinträge je Auftrag (Wetter, Personal, Arbeiten, Behinderungen, Mängel, Fotos), auch auf dem Tablet."""
import base64
import json
import os
import re
import uuid
from datetime import date, datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS bautagebuch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auftrag_id INTEGER NOT NULL, datum TEXT NOT NULL, wetter TEXT DEFAULT '', temperatur TEXT DEFAULT '',
    personal TEXT DEFAULT '', arbeiten TEXT DEFAULT '', material TEXT DEFAULT '', behinderungen TEXT DEFAULT '',
    maengel TEXT DEFAULT '', besonderes TEXT DEFAULT '', fotos TEXT DEFAULT '[]',
    erstellt_von TEXT DEFAULT '', angelegt TEXT, geaendert TEXT
);
CREATE INDEX IF NOT EXISTS bautagebuch_auftrag ON bautagebuch(auftrag_id, datum);
"""
NACHRUESTEN = [("positionen", "TEXT DEFAULT '[]'")]
FELDER = ("datum", "wetter", "temperatur", "personal", "arbeiten", "material", "behinderungen", "maengel", "besonderes")
WETTER = ["sonnig", "heiter", "bewölkt", "Regen", "Gewitter", "Schnee", "Frost", "Wind/Sturm", "Nebel"]
HILFE = {"daten": "", "auftrag_laden": None, "auftrag_kunde": None, "einstellungen": None}


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def schema(con):
    con.executescript(SCHEMA)
    spalten = {c[1] for c in con.execute("PRAGMA table_info(bautagebuch)")}
    for sp, typ in NACHRUESTEN:
        if sp not in spalten:
            con.execute(f"ALTER TABLE bautagebuch ADD COLUMN {sp} {typ}")


def stunden_am_tag(con, aid, tag):
    """Gebuchte Stunden des Auftrags an diesem Tag (Zeiterfassung, Stempeluhr, Rapport, Büro)."""
    aus = []
    for r in con.execute("SELECT s.stunden, s.kst, s.taetigkeit, s.titel, m.vorname, m.nachname, m.kuerzel FROM stunden s "
                         "LEFT JOIN mitarbeiter m ON m.id=s.mitarbeiter_id WHERE s.auftrag_id=? AND s.datum=? ORDER BY s.id", (aid, tag)):
        name = " ".join(x for x in [r["vorname"], r["nachname"]] if x) or r["kuerzel"] or ""
        aus.append({"name": name, "stunden": round(r["stunden"] or 0, 2), "kst": r["kst"] or "", "taetigkeit": r["taetigkeit"] or "", "titel": r["titel"] or 0})
    return aus


def ordner():
    p = os.path.join(HILFE["daten"], "bautagebuch")
    os.makedirs(p, exist_ok=True)
    return p


def laden(con, eid):
    r = con.execute("SELECT * FROM bautagebuch WHERE id=?", (eid,)).fetchone()
    if not r:
        raise Fehler("Eintrag nicht gefunden", 404)
    d = dict(r)
    for k in ("fotos", "positionen"):
        try:
            d[k] = json.loads(d.get(k) or "[]")
        except ValueError:
            d[k] = []
    try:
        d["stunden"] = stunden_am_tag(con, d["auftrag_id"], d["datum"])
    except Exception:  # noqa: BLE001
        d["stunden"] = []
    d["stunden_summe"] = round(sum(x["stunden"] for x in d["stunden"]), 2)
    return d


def liste(con, aid):
    return [laden(con, r["id"]) for r in con.execute("SELECT id FROM bautagebuch WHERE auftrag_id=? ORDER BY datum DESC, id DESC", (aid,))]


def personal_vorschlag(con, aid, tag):
    """Wer war an dem Tag auf dem Auftrag (aus Zeiterfassung und Stunden)?"""
    namen = {}
    try:
        for r in con.execute("SELECT m.vorname, m.nachname, m.kuerzel, z.beginn, z.ende FROM zeiten z JOIN mitarbeiter m ON m.id=z.mitarbeiter_id "
                             "WHERE z.auftrag_id=? AND z.datum=?", (aid, tag)):
            n = " ".join(x for x in [r["vorname"], r["nachname"]] if x) or r["kuerzel"]
            namen.setdefault(n, []).append(f"{r['beginn']}–{r['ende'] or '…'}")
    except Exception:  # noqa: BLE001  (ohne Personalmodul)
        pass
    return "\n".join(f"{n} ({', '.join(z)})" for n, z in namen.items())


def anlegen(con, aid, d, wer):
    if not con.execute("SELECT 1 FROM auftraege WHERE id=?", (aid,)).fetchone():
        raise Fehler("Auftrag nicht gefunden", 404)
    tag = d.get("datum") or date.today().isoformat()
    vorhanden = con.execute("SELECT id FROM bautagebuch WHERE auftrag_id=? AND datum=?", (aid, tag)).fetchone()
    if vorhanden:
        return laden(con, vorhanden["id"])   # je Tag ein Eintrag
    cur = con.execute("INSERT INTO bautagebuch (auftrag_id, datum, personal, erstellt_von, angelegt, geaendert) VALUES (?,?,?,?,?,?)",
                      (aid, tag, personal_vorschlag(con, aid, tag), wer, jetzt(), jetzt()))
    return laden(con, cur.lastrowid)


def speichern(con, eid, d):
    laden(con, eid)
    werte = {k: str(d[k] or "") for k in FELDER if k in d}
    if isinstance(d.get("positionen"), list):
        werte["positionen"] = json.dumps([{"id": int(x.get("id") or 0), "posnr": str(x.get("posnr") or ""), "text": str(x.get("text") or "")[:120]}
                                          for x in d["positionen"] if isinstance(x, dict)], ensure_ascii=False)
    if "datum" in werte and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", werte["datum"]):
        raise Fehler("Ungültiges Datum.")
    if werte:
        werte["geaendert"] = jetzt()
        con.execute(f"UPDATE bautagebuch SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [eid])
    return laden(con, eid)


def foto_hinzu(con, eid, d):
    e = laden(con, eid)
    roh = str(d.get("daten") or "")
    m = re.match(r"data:image/(jpeg|png|webp);base64,", roh)
    if not m:
        raise Fehler("Bitte ein Foto (JPG/PNG) wählen.")
    inhalt = base64.b64decode(roh[m.end():])
    if len(inhalt) > 8_000_000:
        raise Fehler("Das Foto ist zu groß.")
    name = f"btb_{eid}_{uuid.uuid4().hex[:8]}.{m.group(1).replace('jpeg', 'jpg')}"
    with open(os.path.join(ordner(), name), "wb") as f:
        f.write(inhalt)
    e["fotos"].append({"datei": name, "text": str(d.get("text") or "")[:200], "zeit": jetzt()})
    con.execute("UPDATE bautagebuch SET fotos=?, geaendert=? WHERE id=?", (json.dumps(e["fotos"], ensure_ascii=False), jetzt(), eid))
    return laden(con, eid)


def foto_weg(con, eid, datei):
    e = laden(con, eid)
    e["fotos"] = [x for x in e["fotos"] if x.get("datei") != datei]
    con.execute("UPDATE bautagebuch SET fotos=?, geaendert=? WHERE id=?", (json.dumps(e["fotos"], ensure_ascii=False), jetzt(), eid))
    pfad = os.path.join(ordner(), os.path.basename(datei))
    if os.path.exists(pfad):
        os.remove(pfad)
    return laden(con, eid)


def foto_pfad(name):
    name = os.path.basename(name or "")
    if not re.fullmatch(r"btb_\d+_[0-9a-f]{8}\.(jpg|png|webp)", name):
        return None
    p = os.path.join(ordner(), name)
    return p if os.path.isfile(p) else None


def api(con, methode, teile, q, d, wer):
    d = d or {}
    eid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
    if methode == "GET" and eid is None:
        return {"eintraege": liste(con, int(q.get("auftrag") or 0)), "wetter": WETTER}
    if methode == "POST" and eid is None:
        return anlegen(con, int(d.get("auftrag_id") or 0), d, wer)
    if eid and len(teile) == 2:
        if methode == "GET":
            return {**laden(con, eid), "wetter_liste": WETTER}
        if methode == "PUT":
            return speichern(con, eid, d)
        if methode == "DELETE":
            raise Fehler("Einträge im Bautagebuch werden nicht gelöscht. Korrekturen bitte im Eintrag ergänzen.", 403)
    if eid and teile[2:] == ["foto"]:
        if methode == "POST":
            return foto_hinzu(con, eid, d)
        if methode == "DELETE":
            return foto_weg(con, eid, q.get("datei") or d.get("datei"))
    raise Fehler("Unbekannte Anfrage", 404)


def html_inhalt(eintraege, hilfe, mit_fotos=True, deckblatt=None):
    """Druck: Deckblatt mit Übersicht, danach jeder Tag auf einer eigenen Seite."""
    h, ddat = hilfe["h"], hilfe["de_datum"]
    wt = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    reihe = sorted(eintraege, key=lambda x: (x["datum"], x["id"]))

    def tag_name(e):
        try:
            return wt[date.fromisoformat(e["datum"]).weekday()]
        except ValueError:
            return ""
    teile = []
    if deckblatt is not None:
        db = deckblatt
        summe = sum(e.get("stunden_summe") or 0 for e in reihe)
        zeitraum = f"{ddat(reihe[0]['datum'])} – {ddat(reihe[-1]['datum'])}" if reihe else "–"
        uebersicht = "".join(f'<tr><td class="nw">{tag_name(e)[:2]} {ddat(e["datum"])}</td><td class="nw">{h(e.get("wetter") or "")}{" · " + h(e["temperatur"]) + " °C" if e.get("temperatur") else ""}</td>'
                             f'<td>{h((e.get("arbeiten") or "").splitlines()[0] if e.get("arbeiten") else "")}</td><td class="r nw">{hilfe["de"](e.get("stunden_summe") or 0)} h</td>'
                             f'<td class="r">{len(e.get("fotos") or []) or ""}</td></tr>' for e in reihe)
        teile.append(f'''<div style="margin:14mm 0 8mm"><div style="font-size:26pt;font-weight:700;letter-spacing:.5px">BAUTAGEBUCH</div>
<div style="font-size:14pt;margin-top:3mm">{h(db.get("auftrag"))}</div></div>
<table class="t" style="width:auto;min-width:120mm"><tr><td class="k" style="width:38mm">Auftrag</td><td><b>{h(db.get("nummer"))}</b></td></tr>
<tr><td class="k">Auftraggeber</td><td>{h(db.get("kunde"))}</td></tr>
<tr><td class="k">Baustelle</td><td>{h(db.get("baustelle")) or "–"}</td></tr>
<tr><td class="k">Auftragnehmer</td><td>{h(db.get("firma"))}</td></tr>
<tr><td class="k">Zeitraum</td><td>{zeitraum}</td></tr>
<tr><td class="k">Einträge</td><td>{len(reihe)} Tage · {hilfe["de"](summe)} gebuchte Stunden</td></tr></table>
<div class="sek" style="margin-top:8mm">Übersicht</div><table class="t"><tr><th>Tag</th><th>Wetter</th><th>Arbeiten</th><th class="r">Stunden</th><th class="r">Fotos</th></tr>{uebersicht or "<tr><td colspan=5>–</td></tr>"}</table>''')
    for e in reihe:
        zeilen = "".join(f'<tr><td class="k" style="width:30mm">{n}</td><td style="white-space:pre-wrap">{h(e[k])}</td></tr>'
                         for n, k in (("Personal", "personal"), ("Ausgeführte Arbeiten", "arbeiten"), ("Material / Lieferungen", "material"),
                                      ("Behinderungen", "behinderungen"), ("Mängel", "maengel"), ("Besonderes", "besonderes")) if (e.get(k) or "").strip())
        pos = ", ".join(f'{h(p.get("posnr"))} {h(p.get("text"))}' for p in e.get("positionen") or [])
        if pos:
            zeilen = f'<tr><td class="k">Positionen</td><td>{pos}</td></tr>' + zeilen
        std = ""
        if e.get("stunden"):
            std = ('<div class="sek">Gebuchte Stunden</div><table class="t"><tr><th>Mitarbeiter</th><th>Kostenstelle</th><th>Tätigkeit</th><th class="r">Stunden</th></tr>'
                   + "".join(f'<tr><td>{h(x["name"]) or "–"}</td><td>{h(x["kst"])}</td><td>{h(x["taetigkeit"])}</td><td class="r nw">{hilfe["de"](x["stunden"])} h</td></tr>' for x in e["stunden"])
                   + f'<tr class="sum"><td colspan="3">Summe</td><td class="r nw">{hilfe["de"](e["stunden_summe"])} h</td></tr></table>')
        fotos = ""
        if mit_fotos and e["fotos"]:
            fotos = '<div class="sek">Fotos</div><div class="bilder">' + "".join(f'<img src="{hilfe["foto_uri"](x["datei"])}">' for x in e["fotos"]) + "</div>"
        teile.append(('<div class="neue-seite"></div>' if teile else "") + f'<div class="sek" style="font-size:11pt;margin-top:0">{tag_name(e)}, {ddat(e["datum"])}'
                     f'{" · " + h(e["wetter"]) if e.get("wetter") else ""}{" · " + h(e["temperatur"]) + " °C" if e.get("temperatur") else ""}</div>'
                     f'<table class="t">{zeilen or "<tr><td>–</td></tr>"}</table>{std}{fotos}')
    if not reihe:
        teile.append("<p>Noch keine Einträge im Bautagebuch.</p>")
    return "".join(teile)
