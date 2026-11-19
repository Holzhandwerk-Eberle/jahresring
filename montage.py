"""Rapport: auf dem Tablet beim Kunden ausfüllen und unterschreiben lassen.
Nach der Unterschrift werden Stunden (Zeitkonto + Nachkalkulation), Material (Auftragskosten, ggf. Lagerabgang)
und Anmerkungen (Notiz) in den Auftrag übernommen und ein PDF abgelegt."""
import base64
import html as html_mod
import json
import os
import re
from datetime import date, datetime

import material
import personal
from kern import de_menge

SCHEMA = """
CREATE TABLE IF NOT EXISTS montageberichte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auftrag_id INTEGER NOT NULL,
    datum TEXT, status TEXT DEFAULT 'offen',
    positionen TEXT DEFAULT '[]', zeiten TEXT DEFAULT '[]', material TEXT DEFAULT '[]',
    anmerkungen TEXT DEFAULT '', abgeschlossen INTEGER DEFAULT 1,
    kunde_name TEXT DEFAULT '', unterschrift_kunde TEXT DEFAULT '', unterschrift_monteur TEXT DEFAULT '',
    unterschrieben TEXT DEFAULT '', uebernahme TEXT DEFAULT '{}', pdf TEXT DEFAULT '',
    angelegt TEXT, geaendert TEXT, angelegt_von TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_montage_auftrag ON montageberichte(auftrag_id);
"""
JSON_FELDER = ("positionen", "zeiten", "material", "uebernahme")

# wird von app.py befüllt
HILFE = {"daten": "", "auftrag_laden": None, "auftrag_kunde": None, "auftrag_rechnen": None, "einstellungen": None,
         "kostenstellen": None, "nach_druck": None}


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def klartext(t, laenge=220):
    """Positionstext aus dem Texteditor (HTML) als einfacher Text: Aufzählungen mit „·“, Absätze mit „ – “."""
    t = str(t or "")
    if "<" in t:
        t = re.sub(r"(?i)<li[^>]*>", "\n", t)
        t = re.sub(r"(?i)<br\s*/?>|</(p|div|li|ul|ol|h\d)>", "\n", t)
        t = re.sub(r"<[^>]+>", "", t)
    t = html_mod.unescape(t)
    zeilen = [re.sub(r"\s+", " ", z).strip(" ·") for z in t.split("\n")]
    zeilen = [z for z in zeilen if z]
    if not zeilen:
        return ""
    text = zeilen[0] + (" – " + " · ".join(zeilen[1:]) if len(zeilen) > 1 else "")
    return text if len(text) <= laenge else text[:laenge - 1].rstrip() + "…"


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def schema(con):
    con.executescript(SCHEMA)


def ordner():
    p = os.path.join(HILFE["daten"], "montage")
    os.makedirs(p, exist_ok=True)
    return p


def laden(con, mid):
    r = con.execute("SELECT * FROM montageberichte WHERE id=?", (mid,)).fetchone()
    if not r:
        raise Fehler("Rapport nicht gefunden", 404)
    b = dict(r)
    for k in JSON_FELDER:
        try:
            b[k] = json.loads(b[k] or ("{}" if k == "uebernahme" else "[]"))
        except ValueError:
            b[k] = {} if k == "uebernahme" else []
    for p in b["positionen"]:
        if isinstance(p, dict) and "<" in str(p.get("text") or ""):
            p["text"] = klartext(p["text"])   # ältere Berichte: HTML aus dem Texteditor
    b["stunden_summe"] = round(sum(zeile_stunden(z) for z in b["zeiten"]), 2)
    return b


def minuten(t):
    try:
        h, m = (t or "").replace(".", ":").split(":")
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def zeile_stunden(z):
    b, e = minuten(z.get("beginn")), minuten(z.get("ende"))
    if b is None or e is None or e <= b:
        return 0.0
    return round((e - b - int(float(z.get("pause") or 0))) / 60, 2)


def montage_kst(con, aid):
    e = HILFE["einstellungen"](con)
    ksts = HILFE["kostenstellen"](con, aid)
    wunsch = (e.get("typ_kst") or {}).get("Montage") or ""
    if wunsch in ksts:
        return wunsch
    return next((k for k in ksts if "MONT" in k.upper()), ksts[0] if ksts else "")


def meta(con, aid):
    a = HILFE["auftrag_laden"](con, aid)
    k = HILFE["auftrag_kunde"](con, aid)
    erg = HILFE["auftrag_rechnen"](con, aid)
    pos = [{"posnr": p.get("posnr"), "text": klartext(p.get("text")), "menge": p.get("menge"), "einheit": p.get("einheit")}
           for p in erg.get("positionen", []) if not p.get("parent_id")]
    mas = [{"id": m["id"], "name": f"{m['vorname'] or ''} {m['nachname'] or ''}".strip(), "kuerzel": m["kuerzel"] or ""}
           for m in con.execute("SELECT * FROM mitarbeiter WHERE aktiv=1 ORDER BY nachname, vorname")]
    name_worte = set(re.findall(r"\w+", (k.get("kurzname") or "").lower()))

    def ohne_namen(t):
        # Zeilen, die nur den Kundennamen wiederholen (z. B. „Arno Straub“ bei „Straub, Arno“), weglassen
        return "\n".join(z for z in (t or "").split("\n") if z.strip() and not (set(re.findall(r"\w+", z.lower())) <= name_worte))
    return {"auftrag": {"id": a["id"], "nummer": a["nummer"], "bezeichnung": a["bezeichnung"]},
            "kunde": {"name": k.get("kurzname") or "", "anschrift": ohne_namen(k.get("anschrift")), "lieferanschrift": ohne_namen(k.get("lieferanschrift")),
                      "telefon": k.get("telefon") or k.get("mobil") or ""},
            "positionen": pos, "mitarbeiter": mas, "kostenstellen": HILFE["kostenstellen"](con, aid), "kst_vorgabe": montage_kst(con, aid)}


def material_suchen(con, text):
    text = (text or "").strip()
    sql = "SELECT id, nummer, bezeichnung, einheit, lager, bestand, kategorie FROM material WHERE aktiv=1"
    par = []
    for w in text.split()[:5]:
        sql += " AND (ulower(nummer) LIKE ? OR ulower(bezeichnung) LIKE ? OR ulower(IFNULL(bestellnr,'')) LIKE ? OR ulower(IFNULL(ean,'')) LIKE ?)"
        par += [f"%{w.lower()}%"] * 4
    sql += " ORDER BY lager DESC, nummer LIMIT 40"
    return [{**dict(r), "bezeichnung": (r["bezeichnung"] or "").split("\n")[0]} for r in con.execute(sql, par)]


def anlegen(con, aid, wer, eigener_mitarbeiter=None):
    m = meta(con, aid)
    zeiten = []
    if eigener_mitarbeiter:
        zeiten.append({"mitarbeiter_id": eigener_mitarbeiter["id"], "name": f"{eigener_mitarbeiter['vorname']} {eigener_mitarbeiter['nachname']}".strip(),
                       "beginn": "", "ende": "", "pause": 0, "kst": m["kst_vorgabe"], "taetigkeit": "Montage"})
    pos = [{**p, "erledigt": False} for p in m["positionen"]]
    cur = con.execute("INSERT INTO montageberichte (auftrag_id, datum, positionen, zeiten, angelegt, geaendert, angelegt_von) VALUES (?,?,?,?,?,?,?)",
                      (aid, date.today().isoformat(), json.dumps(pos, ensure_ascii=False), json.dumps(zeiten, ensure_ascii=False), jetzt(), jetzt(), wer))
    return laden(con, cur.lastrowid)


def speichern(con, mid, d):
    b = laden(con, mid)
    if b["status"] != "offen":
        raise Fehler("Der Rapport ist unterschrieben und kann nicht mehr geändert werden.")
    werte = {}
    for k in ("datum", "anmerkungen", "kunde_name"):
        if k in d:
            werte[k] = str(d[k] or "")
    if "abgeschlossen" in d:
        werte["abgeschlossen"] = 1 if d["abgeschlossen"] else 0
    for k in ("positionen", "zeiten", "material"):
        if isinstance(d.get(k), list):
            werte[k] = json.dumps(d[k], ensure_ascii=False)
    if werte:
        werte["geaendert"] = jetzt()
        con.execute(f"UPDATE montageberichte SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [mid])
    return laden(con, mid)


def _png_speichern(b64, name):
    roh = base64.b64decode((b64 or "").split(",")[-1])
    if roh[:8] != b"\x89PNG\r\n\x1a\n" or len(roh) < 200:
        return ""
    with open(os.path.join(ordner(), name), "wb") as f:
        f.write(roh)
    return name


def unterschreiben(con, mid, d, wer):
    b = laden(con, mid)
    if b["status"] != "offen":
        raise Fehler("Der Rapport ist bereits unterschrieben.")
    if d:
        b = speichern(con, mid, d)
    if not (d.get("kunde_name") or b["kunde_name"]).strip():
        raise Fehler("Bitte den Namen des Kunden eintragen.")
    for z in b["zeiten"]:
        if (z.get("beginn") or z.get("ende")) and zeile_stunden(z) <= 0:
            raise Fehler(f"Zeit von {z.get('name') or 'Mitarbeiter'}: bitte Beginn und Ende prüfen.")
    uk = _png_speichern(d.get("unterschrift_kunde"), f"mb{mid}_kunde.png")
    if not uk:
        raise Fehler("Bitte den Kunden unterschreiben lassen.")
    um = _png_speichern(d.get("unterschrift_monteur"), f"mb{mid}_monteur.png")
    aid = b["auftrag_id"]
    datum = b["datum"] or date.today().isoformat()
    ueb = {"zeiten": [], "stunden": [], "auftragskosten": [], "notiz": None, "hinweise": []}
    # Stunden: Mitarbeiter mit Stammsatz → Zeitkonto (das bucht automatisch auch die Auftragsstunden), sonst nur Auftragsstunden
    for z in b["zeiten"]:
        std = zeile_stunden(z)
        if std <= 0:
            continue
        text = z.get("taetigkeit") or "Montage"
        pause = int(float(z.get("pause") or 0))
        if z.get("mitarbeiter_id"):
            try:
                if pause:
                    # Pause in die Mitte legen: zwei Abschnitte, damit das Zeitkonto stimmt
                    bm, em = minuten(z["beginn"]), minuten(z["ende"])
                    mitte = bm + ((em - bm - pause) // 2) // 5 * 5
                    abschnitte = [(z["beginn"], f"{mitte // 60:02d}:{mitte % 60:02d}"),
                                  (f"{(mitte + pause) // 60:02d}:{(mitte + pause) % 60:02d}", z["ende"])]
                else:
                    abschnitte = [(z["beginn"], z["ende"])]
                for von, bis in abschnitte:
                    zid = personal.zeit_speichern(con, {"mitarbeiter_id": z["mitarbeiter_id"], "datum": datum, "beginn": von, "ende": bis,
                                                        "auftrag_id": aid, "kst": z.get("kst") or "", "taetigkeit": text,
                                                        "notiz": f"Rapport {mid}", "quelle": "montage"}, von=wer)
                    ueb["zeiten"].append(zid)
            except personal.Fehler as f:
                ueb["hinweise"].append(f"{z.get('name')}: {f} – Zeit nicht übernommen (vermutlich schon gestempelt).")
        else:
            cur = con.execute("INSERT INTO stunden (auftrag_id, datum, stunden, kst, gruppe, taetigkeit, angelegt) VALUES (?,?,?,?,?,?,?)",
                              (aid, datum, std, z.get("kst") or "", "", f"{z.get('name') or ''} · {text} (Rapport)".strip(" ·"), jetzt()))
            ueb["stunden"].append(cur.lastrowid)
    # Material → Auftragskosten (Lagerartikel mit Lagerabgang)
    for m in b["material"]:
        menge = float(m.get("menge") or 0)
        if menge <= 0:
            continue
        mat = None
        if m.get("material_id"):
            r = con.execute("SELECT * FROM material WHERE id=?", (m["material_id"],)).fetchone()
            mat = dict(r) if r else None
        art = material.KAT_KOSTENART.get(mat["kategorie"], "werkstoffe") if mat else "kleinmaterial"
        ak = material.ak_buchen(con, {"auftrag_id": aid, "datum": datum, "kostenart": art, "material_id": mat["id"] if mat else None,
                                      "bezeichnung": m.get("bezeichnung") or "", "einheit": m.get("einheit") or "", "menge": menge,
                                      "lager_abgang": bool(mat and mat.get("lager")), "bemerkung": f"Rapport {mid} vom {_de(datum)}"})
        ueb["auftragskosten"].append(ak["id"])
    # Anmerkungen → Notiz im Auftrag
    teile = []
    erledigt = [p for p in b["positionen"] if p.get("erledigt")]
    if erledigt:
        teile.append("Erledigt: " + ", ".join(f"Pos. {p.get('posnr')}" for p in erledigt))
    if b["anmerkungen"].strip():
        teile.append(b["anmerkungen"].strip())
    teile.append("Arbeiten abgeschlossen: " + ("ja" if b["abgeschlossen"] else "nein"))
    cur = con.execute("INSERT INTO notizen (auftrag_id, text, angelegt) VALUES (?,?,?)",
                      (aid, f"Rapport vom {_de(datum)} (unterschrieben von {d.get('kunde_name') or b['kunde_name']}):\n" + "\n".join(teile), jetzt()))
    ueb["notiz"] = cur.lastrowid
    con.execute("UPDATE montageberichte SET status='unterschrieben', unterschrift_kunde=?, unterschrift_monteur=?, unterschrieben=?, "
                "uebernahme=?, geaendert=? WHERE id=?", (uk, um, jetzt(), json.dumps(ueb, ensure_ascii=False), jetzt(), mid))
    return laden(con, mid)


def _de(iso):
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso or ""


def loeschen(con, mid):
    b = laden(con, mid)
    if b["status"] != "offen":
        raise Fehler("Unterschriebene Rapporte werden nicht gelöscht.")
    con.execute("DELETE FROM montageberichte WHERE id=?", (mid,))
    return {"ok": True, "auftrag_id": b["auftrag_id"]}


def bild_b64(name):
    p = os.path.join(ordner(), os.path.basename(name or ""))
    if not name or not os.path.isfile(p):
        return ""
    with open(p, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def html_inhalt(con, b, hilfe):
    """Inhalt für den Werkstatt-Rahmen (werkstatt.rahmen)."""
    h, de = hilfe["h"], hilfe["de"]
    m = meta(con, b["auftrag_id"])
    k = m["kunde"]
    adr = (k["lieferanschrift"] or k["anschrift"] or "").replace("\n", " · ")
    pos = "".join(f'<tr><td class="nw" style="width:6mm">{"☑" if p.get("erledigt") else "☐"}</td><td class="nw" style="width:12mm">{h(p.get("posnr"))}</td><td>{h(p.get("text"))}</td></tr>'
                  for p in b["positionen"])
    zeiten = "".join(f'<tr><td>{h(z.get("name"))}</td><td class="nw">{h(z.get("beginn"))}–{h(z.get("ende"))}</td>'
                     f'<td class="r nw">{int(float(z.get("pause") or 0))} min</td><td class="r nw">{de(zeile_stunden(z))} h</td><td>{h(z.get("taetigkeit"))}</td></tr>'
                     for z in b["zeiten"] if zeile_stunden(z) > 0)
    mat = "".join(f'<tr><td class="r nw">{de_menge(x.get("menge"))} {h(x.get("einheit"))}</td>'
                  f'<td>{h(x.get("nummer") or "")}</td><td>{h(x.get("bezeichnung"))}</td></tr>' for x in b["material"] if float(x.get("menge") or 0) > 0)
    uk, um = bild_b64(b["unterschrift_kunde"]), bild_b64(b["unterschrift_monteur"])
    unterschrift = (f'<table class="t" style="margin-top:4mm"><tr>'
                    f'<td style="width:50%;height:26mm;vertical-align:bottom">{f"<img src={chr(34)}{um}{chr(34)} style={chr(34)}max-height:24mm;max-width:80mm{chr(34)}>" if um else ""}</td>'
                    f'<td style="vertical-align:bottom">{f"<img src={chr(34)}{uk}{chr(34)} style={chr(34)}max-height:24mm;max-width:80mm{chr(34)}>" if uk else ""}</td></tr>'
                    f'<tr><td class="k">Auftragnehmer</td><td class="k">Auftraggeber: {h(b["kunde_name"])}'
                    f'{" · unterschrieben am " + h(_de(b["unterschrieben"])) + " um " + h(b["unterschrieben"][11:16]) if b["unterschrieben"] else ""}</td></tr></table>')
    return (f'<div class="sek">Einsatz</div><div>Datum <b>{h(_de(b["datum"]))}</b> · Kunde <b>{h(k["name"])}</b>{" · " + h(adr) if adr else ""}</div>'
            + (f'<div class="sek">Positionen</div><table class="t">{pos}</table>' if pos else "")
            + f'<div class="sek">Geleistete Stunden</div><table class="t"><tr><th>Mitarbeiter</th><th>Von–Bis</th><th class="r">Pause</th><th class="r">Stunden</th><th>Tätigkeit</th></tr>{zeiten or "<tr><td colspan=5>–</td></tr>"}'
            + f'<tr class="sum"><td colspan="3">Summe</td><td class="r nw">{de(b["stunden_summe"])} h</td><td></td></tr></table>'
            + f'<div class="sek">Verwendetes Material</div><table class="t"><tr><th class="r" style="width:18%">Menge</th><th style="width:16%">Nr.</th><th>Bezeichnung</th></tr>{mat or "<tr><td colspan=3>–</td></tr>"}</table>'
            + f'<div class="sek">Anmerkungen</div><div style="white-space:pre-wrap;min-height:10mm">{h(b["anmerkungen"]) or "–"}</div>'
            + f'<div class="sek">Abnahme</div><div>Arbeiten abgeschlossen: <b>{"ja" if b["abgeschlossen"] else "nein"}</b>. '
              'Der Auftraggeber bestätigt die oben aufgeführten Arbeiten, Stunden und das verwendete Material.</div>'
            + unterschrift)


def api(con, methode, teile, q, d, wer, eigener_mitarbeiter=None):
    d = d or {}
    rid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
    if methode == "GET" and teile[1:] == ["meta"]:
        return meta(con, int(q.get("auftrag") or 0))
    if methode == "GET" and teile[1:] == ["material"]:
        return material_suchen(con, q.get("q"))
    if methode == "GET" and len(teile) == 1:
        sql = "SELECT id FROM montageberichte"
        par = []
        if q.get("auftrag"):
            sql += " WHERE auftrag_id=?"
            par.append(int(q["auftrag"]))
        sql += " ORDER BY datum DESC, id DESC LIMIT 200"
        return [laden(con, r["id"]) for r in con.execute(sql, par)]
    if methode == "POST" and len(teile) == 1:
        return anlegen(con, int(d.get("auftrag_id") or 0), wer, eigener_mitarbeiter)
    if rid and len(teile) == 2:
        if methode == "GET":
            return laden(con, rid)
        if methode == "PUT":
            return speichern(con, rid, d)
        if methode == "DELETE":
            return loeschen(con, rid)
    if rid and methode == "POST" and teile[2:] == ["pdf"]:
        if laden(con, rid)["status"] == "offen":
            raise Fehler("Erst nach der Unterschrift gibt es ein PDF.")
        return HILFE["nach_druck"](con, rid)
    if rid and methode == "POST" and teile[2:] == ["unterschreiben"]:
        b = unterschreiben(con, rid, d, wer)
        if HILFE.get("nach_druck"):
            b["pdf_info"] = HILFE["nach_druck"](con, rid)
            b = {**laden(con, rid), "pdf_info": b["pdf_info"]}
        return b
    raise Fehler("Unbekannte Anfrage", 404)
