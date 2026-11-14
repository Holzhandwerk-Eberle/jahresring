"""Projekte: schlanke Klammer über mehrere Aufträge (z. B. Bauabschnitte, Lose, Nachträge, verschiedene Rechnungsempfänger).
Belege, Kalkulation und Leitstand bleiben je Auftrag; das Projekt fasst nur zusammen und wertet aus."""
from datetime import date, datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS projekte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer TEXT UNIQUE NOT NULL, bezeichnung TEXT DEFAULT '', kunde_id INTEGER,
    status TEXT DEFAULT 'aktiv', bemerkungen TEXT DEFAULT '', angelegt TEXT, geaendert TEXT
);
"""
FELDER = ("bezeichnung", "kunde_id", "status", "bemerkungen")
# Kostenarten des Soll/Ist, die über die Aufträge summiert werden
SI_KEYS = ("werkstoffe", "beschlaege", "oberflaeche", "kleinmaterial", "fremdleistungen", "zukauf", "material", "gk_material", "material_gk",
           "stunden", "lohn", "gk_lohn", "lohn_gk", "sonder_fertigung", "selbstkosten", "wg", "nettopreis")

HILFE = {"soll_ist": None, "beleg_umsatz": None}


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def schema(con):
    con.executescript(SCHEMA)


def naechste_nummer(con):
    jahr = date.today().year
    n = 0
    for (nr,) in con.execute("SELECT nummer FROM projekte WHERE nummer LIKE ?", (f"P{jahr}-%",)):
        try:
            n = max(n, int(nr.split("-")[1]))
        except (IndexError, ValueError):
            pass
    return f"P{jahr}-{n + 1:02d}"


def _f(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def auftrag_zahlen(con, a):
    """Geldwerte eines Auftrags: angeboten, beauftragt, berechnet, bezahlt, offen (alle netto außer bezahlt/offen = brutto)."""
    aid = a["id"]
    def letzter(arten):
        r = con.execute(f"SELECT netto FROM belege WHERE auftrag_id=? AND art IN ({','.join('?' * len(arten))}) ORDER BY datum DESC, id DESC LIMIT 1",
                        (aid, *arten)).fetchone()
        return _f(r["netto"]) if r else 0.0
    angeboten = letzter(("angebot", "kv"))
    beauftragt = letzter(("ab",)) or (angeboten if a["status"] not in ("Anfrage", "Angebot", "Abgesagt") else 0.0)
    berechnet = 0.0
    for b in con.execute("SELECT * FROM belege WHERE auftrag_id=? AND art IN ('rechnung','abschlag','storno','gutschrift','korrektur') AND status IN ('fest','storniert')", (aid,)):
        berechnet += HILFE["beleg_umsatz"](b)
    op = con.execute("SELECT COALESCE(SUM(betrag),0) AS betrag, COALESCE(SUM(offen),0) AS offen FROM offene_posten WHERE auftrag_id=?", (aid,)).fetchone()
    return {"angeboten": round(angeboten, 2), "beauftragt": round(beauftragt, 2), "berechnet": round(berechnet, 2),
            "bezahlt": round(_f(op["betrag"]) - _f(op["offen"]), 2), "offen": round(_f(op["offen"]), 2)}


def auftraege(con, pid):
    return [dict(r) for r in con.execute(
        "SELECT a.*, k.kurzname AS kunde, k.nummer AS kundennr FROM auftraege a JOIN kunden k ON k.id=a.kunde_id "
        "WHERE a.projekt_id=? ORDER BY a.nummer", (pid,))]


def laden(con, pid, mit_auswertung=True):
    r = con.execute("SELECT p.*, k.kurzname AS kunde, k.nummer AS kundennr FROM projekte p LEFT JOIN kunden k ON k.id=p.kunde_id WHERE p.id=?",
                    (pid,)).fetchone()
    if not r:
        raise Fehler("Projekt nicht gefunden", 404)
    p = dict(r)
    liste = auftraege(con, pid)
    summe = {k: 0.0 for k in ("angeboten", "beauftragt", "berechnet", "bezahlt", "offen")}
    soll = {k: 0.0 for k in SI_KEYS}
    ist = {k: 0.0 for k in SI_KEYS}
    for a in liste:
        a["zahlen"] = auftrag_zahlen(con, a)
        a.pop("kalk", None)
        a.pop("kunde_daten", None)
        for k in summe:
            summe[k] += a["zahlen"][k]
        if mit_auswertung:
            try:
                si = HILFE["soll_ist"](con, a["id"])
                for k in SI_KEYS:
                    soll[k] += _f(si["soll"].get(k))
                    ist[k] += _f(si["ist"].get(k))
                a["sollist"] = {"soll_selbstkosten": round(_f(si["soll"].get("selbstkosten")), 2), "ist_selbstkosten": round(_f(si["ist"].get("selbstkosten")), 2),
                                "soll_stunden": round(_f(si["soll"].get("stunden")), 1), "ist_stunden": round(_f(si["ist"].get("stunden")), 1)}
            except Exception:  # noqa: BLE001
                a["sollist"] = None
    p["auftraege"] = liste
    p["summe"] = {k: round(v, 2) for k, v in summe.items()}
    p["soll"] = {k: round(v, 2) for k, v in soll.items()}
    p["ist"] = {k: round(v, 2) for k, v in ist.items()}
    # Ergebnis auf Basis berechneter Umsätze (nachkalkulatorisch)
    p["ergebnis"] = round(p["summe"]["berechnet"] - p["ist"]["selbstkosten"], 2)
    return p


def liste(con, status=None, q=None):
    sql, par = "SELECT p.*, k.kurzname AS kunde FROM projekte p LEFT JOIN kunden k ON k.id=p.kunde_id WHERE 1=1", []
    if status and status != "alle":
        sql += " AND p.status=?"
        par.append(status)
    if q:
        sql += " AND (ulower(p.nummer) LIKE ? OR ulower(p.bezeichnung) LIKE ? OR ulower(IFNULL(k.kurzname,'')) LIKE ?)"
        par += [f"%{q.lower()}%"] * 3
    aus = []
    for r in con.execute(sql + " ORDER BY p.nummer DESC", par):
        p = dict(r)
        al = auftraege(con, p["id"])
        p["anzahl"] = len(al)
        s = {k: 0.0 for k in ("beauftragt", "berechnet", "offen")}
        for a in al:
            z = auftrag_zahlen(con, a)
            for k in s:
                s[k] += z[k]
        p["summe"] = {k: round(v, 2) for k, v in s.items()}
        aus.append(p)
    return aus


def anlegen(con, d):
    if not (d.get("bezeichnung") or "").strip():
        raise Fehler("Bitte eine Bezeichnung für das Projekt eingeben.")
    nr = naechste_nummer(con)
    cur = con.execute("INSERT INTO projekte (nummer, bezeichnung, kunde_id, status, bemerkungen, angelegt, geaendert) VALUES (?,?,?,?,?,?,?)",
                      (nr, d["bezeichnung"].strip(), int(d["kunde_id"]) if str(d.get("kunde_id") or "").isdigit() else None,
                       "aktiv", d.get("bemerkungen") or "", jetzt(), jetzt()))
    pid = cur.lastrowid
    for aid in d.get("auftraege") or []:
        con.execute("UPDATE auftraege SET projekt_id=? WHERE id=?", (pid, int(aid)))
    return laden(con, pid, False)


def speichern(con, pid, d):
    laden(con, pid, False)
    werte = {k: d[k] for k in FELDER if k in d}
    if "kunde_id" in werte:
        werte["kunde_id"] = int(werte["kunde_id"]) if str(werte["kunde_id"] or "").isdigit() else None
    if werte:
        werte["geaendert"] = jetzt()
        con.execute(f"UPDATE projekte SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [pid])
    if "zuordnen" in d:
        con.execute("UPDATE auftraege SET projekt_id=? WHERE id=?", (pid, int(d["zuordnen"])))
    if "loesen" in d:
        con.execute("UPDATE auftraege SET projekt_id=NULL WHERE id=? AND projekt_id=?", (int(d["loesen"]), pid))
    return laden(con, pid)


def loeschen(con, pid):
    laden(con, pid, False)
    con.execute("UPDATE auftraege SET projekt_id=NULL WHERE projekt_id=?", (pid,))
    con.execute("DELETE FROM projekte WHERE id=?", (pid,))
    return {"ok": True}


def api(con, methode, teile, q, d):
    d = d or {}
    pid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
    if methode == "GET" and pid is None:
        return liste(con, q.get("status") or "aktiv", (q.get("q") or "").strip())
    if methode == "GET" and pid:
        return laden(con, pid)
    if methode == "POST" and pid is None:
        return anlegen(con, d)
    if methode == "PUT" and pid:
        return speichern(con, pid, d)
    if methode == "DELETE" and pid:
        return loeschen(con, pid)
    raise Fehler("Unbekannte Anfrage", 404)


def html_inhalt(p, h, de, de_datum):
    """Projekt-Nachkalkulation zum Drucken."""
    zeilen = "".join(
        f'<tr><td class="nw">{h(a["nummer"])}</td><td>{h(a["bezeichnung"])}<div class="k">{h(a["kunde"])} · {h(a["status"] or "")}</div></td>'
        f'<td class="r nw">{de(a["zahlen"]["beauftragt"])}</td><td class="r nw">{de(a["zahlen"]["berechnet"])}</td><td class="r nw">{de(a["zahlen"]["offen"])}</td>'
        f'<td class="r nw">{de((a.get("sollist") or {}).get("soll_stunden", 0), 1)} / {de((a.get("sollist") or {}).get("ist_stunden", 0), 1)}</td>'
        f'<td class="r nw">{de((a.get("sollist") or {}).get("soll_selbstkosten", 0))}</td><td class="r nw">{de((a.get("sollist") or {}).get("ist_selbstkosten", 0))}</td></tr>'
        for a in p["auftraege"])
    s = p["summe"]
    namen = [("Werkstoffe", "werkstoffe"), ("Beschläge", "beschlaege"), ("Oberfläche", "oberflaeche"), ("Kleinmaterial", "kleinmaterial"),
             ("Fremdleistungen", "fremdleistungen"), ("Zukauf", "zukauf"), ("Material mit GK", "material_gk"), ("Stunden", "stunden"), ("Lohn mit GK", "lohn_gk"),
             ("Sonderkosten Fertigung", "sonder_fertigung"), ("Selbstkosten", "selbstkosten")]
    si = "".join(f'<tr{" class=sum" if k == "selbstkosten" else ""}><td>{n}</td><td class="r nw">{de(p["soll"][k], 1 if k == "stunden" else 2)}</td>'
                 f'<td class="r nw">{de(p["ist"][k], 1 if k == "stunden" else 2)}</td>'
                 f'<td class="r nw">{"+" if p["ist"][k] - p["soll"][k] > 0.004 else ""}{de(p["ist"][k] - p["soll"][k], 1 if k == "stunden" else 2)}</td></tr>' for n, k in namen)
    return (f'<div class="sek">Projekt</div><div><b>{h(p["nummer"])} {h(p["bezeichnung"])}</b>{" · " + h(p["kunde"]) if p.get("kunde") else ""} · Stand {de_datum(date.today().isoformat())}</div>'
            + (f'<div class="k" style="white-space:pre-wrap;margin-top:1mm">{h(p["bemerkungen"])}</div>' if p.get("bemerkungen") else "")
            + '<div class="sek">Aufträge</div><table class="t"><tr><th>Auftrag</th><th>Bezeichnung</th><th class="r">beauftragt</th><th class="r">berechnet</th>'
              '<th class="r">offen (brutto)</th><th class="r">Std. Soll/Ist</th><th class="r">SK Soll</th><th class="r">SK Ist</th></tr>' + zeilen
            + f'<tr class="sum"><td colspan="2">Summe</td><td class="r nw">{de(s["beauftragt"])}</td><td class="r nw">{de(s["berechnet"])}</td><td class="r nw">{de(s["offen"])}</td>'
              f'<td class="r nw">{de(p["soll"]["stunden"], 1)} / {de(p["ist"]["stunden"], 1)}</td><td class="r nw">{de(p["soll"]["selbstkosten"])}</td><td class="r nw">{de(p["ist"]["selbstkosten"])}</td></tr></table>'
            + '<div class="sek">Soll/Ist über alle Aufträge</div><table class="t"><tr><th>Kosten</th><th class="r">Soll</th><th class="r">Ist</th><th class="r">Abweichung</th></tr>' + si + '</table>'
            + f'<div class="sek">Ergebnis</div><table class="t"><tr><td>Berechneter Umsatz (netto)</td><td class="r nw">{de(s["berechnet"])} €</td></tr>'
              f'<tr><td>Ist-Selbstkosten</td><td class="r nw">{de(p["ist"]["selbstkosten"])} €</td></tr>'
              f'<tr class="sum"><td>Ergebnis (Wagnis und Gewinn)</td><td class="r nw">{"+" if p["ergebnis"] > 0 else ""}{de(p["ergebnis"])} €</td></tr></table>'
              '<p class="k">Soll = Kalkulation der Aufträge. Ist = gebuchte Stunden, Auftragskosten und zugeordnete Lieferantenrechnungen. '
              'Berechnet = festgeschriebene Rechnungen netto (Abschläge nicht doppelt). Offen/bezahlt brutto aus den offenen Posten.</p>')
