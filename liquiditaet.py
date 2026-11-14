"""Jahresring – Liquiditätsvorschau: erwarteter Kontostand Woche für Woche.

Grundlage: letzter Kontostand aus einem eingelesenen Kontoauszug (oder von Hand eingetragen), offene Posten nach
Fälligkeit, offene Zahlungsaufträge (mit Skonto, wenn die Frist noch läuft), Löhne samt Steuer und Sozialversicherung
(geschätzt aus dem letzten erfassten Monat), regelmäßige Zahlungen aus den Einstellungen dieser Seite, auf Wunsch der
noch nicht berechnete Rest laufender Aufträge und eine geschätzte Umsatzsteuer-Zahllast (nach vereinnahmten Entgelten).
Alles Schätzwerte – die Seite ersetzt keine Finanzplanung, zeigt aber Engpässe früh.
"""
import calendar
import json
from datetime import date, timedelta

STANDARD = {"wochen": 12, "start_manuell": None, "regelmaessig": [], "auftraege": True, "ust": {"rhythmus": "quartal", "dauerfrist": False}, "loehne": True}
RHYTHMEN = {"monatlich": 1, "quartal": 3, "halbjahr": 6, "jaehrlich": 12}


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def einstellungen_laden(con):
    r = con.execute("SELECT wert FROM einstellungen WHERE schluessel='liquiditaet'").fetchone()
    cfg = json.loads(STANDARD_JSON)
    if r:
        try:
            cfg.update(json.loads(r["wert"]) or {})
        except ValueError:
            pass
    return cfg


STANDARD_JSON = json.dumps(STANDARD)


def _zahl(v):
    try:
        return round(float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) and "," in v else float(v or 0), 2)
    except (TypeError, ValueError):
        raise Fehler("Bitte einen gültigen Betrag eingeben.")


def einstellungen_speichern(con, d):
    cfg = einstellungen_laden(con)
    if "wochen" in d:
        cfg["wochen"] = max(4, min(52, int(d["wochen"] or 12)))
    if "auftraege" in d:
        cfg["auftraege"] = bool(d["auftraege"])
    if "loehne" in d:
        cfg["loehne"] = bool(d["loehne"])
    if "ust" in d and isinstance(d["ust"], dict):
        rh = d["ust"].get("rhythmus")
        cfg["ust"] = {"rhythmus": rh if rh in ("monat", "quartal", "keine") else "quartal", "dauerfrist": bool(d["ust"].get("dauerfrist"))}
    if "start_manuell" in d:
        s = d["start_manuell"]
        if s and str(s.get("betrag", "")).strip() != "":
            date.fromisoformat(s.get("datum") or date.today().isoformat())
            cfg["start_manuell"] = {"betrag": _zahl(s["betrag"]), "datum": s.get("datum") or date.today().isoformat()}
        else:
            cfg["start_manuell"] = None
    if "regelmaessig" in d:
        liste = []
        for x in d["regelmaessig"] or []:
            if not isinstance(x, dict) or not str(x.get("text") or "").strip():
                continue
            rh = x.get("rhythmus") if x.get("rhythmus") in RHYTHMEN else "monatlich"
            tag = max(1, min(31, int(x.get("tag") or 1)))
            ab = str(x.get("ab") or "")[:7]
            liste.append({"text": str(x["text"]).strip()[:80], "betrag": _zahl(x.get("betrag")), "rhythmus": rh, "tag": tag,
                          "ab": ab if len(ab) == 7 else date.today().isoformat()[:7], "ust": max(0.0, min(19.0, float(x.get("ust") or 0)))})
        cfg["regelmaessig"] = liste
    con.execute("INSERT OR REPLACE INTO einstellungen VALUES ('liquiditaet', ?)", (json.dumps(cfg, ensure_ascii=False),))
    return cfg


def _montag(d):
    return d - timedelta(d.weekday())


def _monate(von, bis):
    j, m = von.year, von.month
    while date(j, m, 1) <= bis:
        yield j, m
        m += 1
        if m > 12:
            j, m = j + 1, 1


def _tag_im_monat(j, m, tag):
    return date(j, m, min(tag, calendar.monthrange(j, m)[1]))


def berechnen(con, hilfe, cfg=None):
    """hilfe: {"lohn_faelligkeiten": fn(monat), "auftraege_rest": fn(con) -> [{id, nummer, kunde, rest_netto, ust_satz, termin}],
    "kontostand": fn(con) -> {saldo_ende, saldo_datum} | None, "darf_loehne": bool}"""
    cfg = cfg or einstellungen_laden(con)
    heute = date.today()
    start_woche = _montag(heute)
    wochen = int(cfg.get("wochen") or 12)
    ende = start_woche + timedelta(7 * wochen - 1)
    posten = []   # {datum, betrag (+ ein / − aus), art, text, link, ust}
    hinweise = []

    # Startwert: Kontoauszug oder von Hand
    ks = hilfe["kontostand"](con)
    sm = cfg.get("start_manuell")
    start = None
    if ks and (not sm or ks["saldo_datum"] >= sm["datum"]):
        start = {"betrag": round(ks["saldo_ende"], 2), "datum": ks["saldo_datum"], "quelle": "kontoauszug"}
    elif sm:
        start = {"betrag": sm["betrag"], "datum": sm["datum"], "quelle": "manuell"}
    if not start:
        hinweise.append("Noch kein Kontostand: einen Kontoauszug einlesen oder den Kontostand unten von Hand eintragen. Bis dahin beginnt die Rechnung bei 0 €.")
        start = {"betrag": 0.0, "datum": heute.isoformat(), "quelle": "keiner"}
    elif (heute - date.fromisoformat(start["datum"])).days > 7:
        hinweise.append(f"Der Kontostand ist vom {date.fromisoformat(start['datum']).strftime('%d.%m.%Y')} – für eine genaue Vorschau den aktuellen Kontoauszug einlesen.")

    def dazu(d, betrag, art, text, link="", ust=0.0, ueberfaellig=False):
        if abs(betrag) < 0.005:
            return
        posten.append({"datum": d.isoformat(), "betrag": round(betrag, 2), "art": art, "text": text, "link": link, "ust": round(ust, 2), "ueberfaellig": ueberfaellig})

    # offene Posten (Kundenrechnungen)
    for o in con.execute("SELECT o.id, o.nummer, o.art, o.offen, o.faellig, o.beleg_id, IFNULL(b.ust_satz,19) AS ust_satz, k.kurzname "
                         "FROM offene_posten o LEFT JOIN belege b ON b.id=o.beleg_id LEFT JOIN kunden k ON k.id=o.kunde_id WHERE o.offen > 0.004"):
        f = date.fromisoformat(o["faellig"][:10]) if o["faellig"] else heute
        ueber = f < heute
        d = max(f, heute)
        if d > ende:
            continue
        satz = o["ust_satz"] or 0
        dazu(d, o["offen"], "op", f"{o['art']} {o['nummer']} · {o['kurzname'] or ''}" + (" (überfällig)" if ueber else ""),
             f"#/beleg/{o['beleg_id']}" if o["beleg_id"] else "#/op", o["offen"] * satz / (100 + satz), ueber)

    # offene Zahlungsaufträge (Lieferanten, Löhne, Steuern …)
    for z in con.execute("SELECT z.id, z.nummer, z.betrag, z.skonto, z.skonto_bis, z.faellig, z.vorsteuer, z.belegnr, l.kurzname, l.gruppe "
                         "FROM zahlungen z LEFT JOIN lieferanten l ON l.id=z.lieferant_id WHERE IFNULL(z.bezahlt,'')=''"):
        betrag = z["betrag"] or 0
        f = z["faellig"] or heute.isoformat()
        if z["skonto"] and z["skonto_bis"] and z["skonto_bis"] >= heute.isoformat():
            betrag -= z["skonto"]
            f = z["skonto_bis"]
        f = date.fromisoformat(f[:10])
        ueber = f < heute
        d = max(f, heute)
        if d > ende:
            continue
        vst = z["vorsteuer"] or 0
        lohn = (z["gruppe"] or "") in ("Mitarbeiter", "Finanzamt", "Krankenkasse")
        dazu(d, -betrag, "zahlung", (f"{z['nummer']} · " + ("Löhne und Abgaben" if lohn and not hilfe.get("darf_loehne") else f"{z['kurzname'] or ''} {z['belegnr'] or ''}")).strip(),
             f"#/zahlung/{z['id']}", -betrag * vst / (100 + vst), ueber)

    # Löhne: Monate ohne erfasste Lohnzahlungen aus dem letzten erfassten Monat schätzen
    if cfg.get("loehne", True):
        letzter = con.execute("SELECT monat FROM lohn WHERE IFNULL(netto,0)+IFNULL(steuer,0)+IFNULL(sv,0) > 0 ORDER BY monat DESC LIMIT 1").fetchone()
        if letzter:
            basis = con.execute("SELECT SUM(IFNULL(netto,0)) AS netto, SUM(IFNULL(steuer,0)) AS steuer, SUM(IFNULL(sv,0)) AS sv FROM lohn WHERE monat=?",
                                (letzter["monat"],)).fetchone()
            for j, m in _monate(heute.replace(day=1), ende):
                monat = f"{j}-{m:02d}"
                if monat <= letzter["monat"]:
                    continue
                fae = hilfe["lohn_faelligkeiten"](monat)
                for teil, text in (("netto", "Nettolöhne"), ("sv", "Sozialversicherung"), ("steuer", "Lohnsteuer")):
                    d = date.fromisoformat(fae[teil])
                    if heute <= d <= ende and basis[teil]:
                        dazu(d, -basis[teil], "lohn", f"{text} {m:02d}/{j} (geschätzt nach {letzter['monat'][5:]}/{letzter['monat'][:4]})")

    # regelmäßige Zahlungen (Miete, Versicherungen, Leasing …)
    for x in cfg.get("regelmaessig") or []:
        schritt = RHYTHMEN.get(x["rhythmus"], 1)
        aj, am = int(x["ab"][:4]), int(x["ab"][5:7])
        for j, m in _monate(heute.replace(day=1), ende):
            if ((j - aj) * 12 + (m - am)) % schritt or (j, m) < (aj, am):
                continue
            d = _tag_im_monat(j, m, x["tag"])
            if heute <= d <= ende:
                satz = x.get("ust") or 0
                dazu(d, x["betrag"], "regel", x["text"], "", x["betrag"] * satz / (100 + satz))

    # noch nicht berechneter Rest laufender Aufträge (nach geplantem Fertigstellungstermin + 14 Tage Zahlungsziel)
    ohne_termin = 0.0
    if cfg.get("auftraege", True):
        for a in hilfe["auftraege_rest"](con):
            if a["rest_netto"] < 1:
                continue
            brutto = a["rest_netto"] * (1 + a["ust_satz"] / 100)
            if not a["termin"]:
                ohne_termin += brutto
                continue
            d = max(date.fromisoformat(a["termin"][:10]) + timedelta(14), heute)
            if d <= ende:
                dazu(d, brutto, "auftrag", f"Auftrag {a['nummer']} · {a['kunde'] or ''} (Rest, geplant)", f"#/auftrag/{a['id']}", brutto - a["rest_netto"])
        if ohne_termin >= 1:
            hinweise.append(f"Laufende Aufträge ohne geplanten Termin mit zusammen {ohne_termin:,.2f} € noch nicht berechnet – nicht eingerechnet.".replace(",", "X").replace(".", ",").replace("X", "."))

    # Umsatzsteuer-Zahllast (Ist-Versteuerung: vereinnahmte Umsatzsteuer minus bezahlte Vorsteuer je Zeitraum)
    ust = cfg.get("ust") or {}
    if ust.get("rhythmus") in ("monat", "quartal"):
        n = 1 if ust["rhythmus"] == "monat" else 3
        j, m = heute.year, heute.month
        m0 = ((m - 1) // n) * n + 1
        perioden = []
        pj, pm = j, m0
        for _ in range(4):   # zwei Zeiträume zurück, laufender, nächster
            pm -= n
            if pm < 1:
                pm += 12
                pj -= 1
        for _ in range(6):
            perioden.append((pj, pm))
            pm += n
            if pm > 12:
                pm -= 12
                pj += 1
        for pj, pm in perioden:
            p_von = date(pj, pm, 1)
            ej, em = (pj, pm + n - 1) if pm + n - 1 <= 12 else (pj + 1, pm + n - 13)
            p_bis = date(ej, em, calendar.monthrange(ej, em)[1])
            fj, fm = (ej, em + 1) if em < 12 else (ej + 1, 1)
            if ust.get("dauerfrist"):
                fj, fm = (fj, fm + 1) if fm < 12 else (fj + 1, 1)
            faellig = date(fj, fm, 10)
            if not (heute <= faellig <= ende):
                continue
            ist_ust = con.execute("SELECT COALESCE(SUM(z.betrag * IFNULL(b.ust_satz,0) / (100 + IFNULL(b.ust_satz,0))),0) FROM zahlungseingaenge z "
                                  "JOIN offene_posten o ON o.id=z.op_id LEFT JOIN belege b ON b.id=o.beleg_id WHERE z.datum BETWEEN ? AND ? AND z.art<>'Skonto'",
                                  (p_von.isoformat(), min(p_bis, heute).isoformat())).fetchone()[0] or 0
            ist_vst = con.execute("SELECT COALESCE(SUM((betrag - IFNULL(skonto,0)) * IFNULL(vorsteuer,0) / (100 + IFNULL(vorsteuer,0))),0) FROM zahlungen "
                                  "WHERE substr(bezahlt,1,10) BETWEEN ? AND ?", (p_von.isoformat(), min(p_bis, heute).isoformat())).fetchone()[0] or 0
            plan = sum(p["ust"] for p in posten if p_von.isoformat() <= p["datum"] <= p_bis.isoformat())
            zahllast = round(ist_ust - ist_vst + plan, 2)
            name = f"{pm:02d}/{pj}" if n == 1 else f"{(pm - 1) // 3 + 1}. Quartal {pj}"
            if abs(zahllast) >= 1:
                dazu(faellig, -zahllast, "ust", f"Umsatzsteuer {name} (geschätzt)")

    # Wochen bilden
    posten.sort(key=lambda p: (p["datum"], -p["betrag"]))
    saldo = start["betrag"]
    aus = []
    for i in range(wochen):
        von = start_woche + timedelta(7 * i)
        bis = von + timedelta(6)
        ps = [p for p in posten if von.isoformat() <= p["datum"] <= bis.isoformat()]
        ein = round(sum(p["betrag"] for p in ps if p["betrag"] > 0), 2)
        ab = round(-sum(p["betrag"] for p in ps if p["betrag"] < 0), 2)
        saldo = round(saldo + ein - ab, 2)
        aus.append({"von": von.isoformat(), "bis": bis.isoformat(), "kw": von.isocalendar()[1], "ein": ein, "aus": ab, "saldo": saldo, "posten": ps})
    tiefst = min(aus, key=lambda w: w["saldo"]) if aus else None
    ueber = {"ein": round(sum(p["betrag"] for p in posten if p["ueberfaellig"] and p["betrag"] > 0), 2),
             "aus": round(-sum(p["betrag"] for p in posten if p["ueberfaellig"] and p["betrag"] < 0), 2)}
    return {"start": start, "wochen": aus, "tiefst": tiefst and {"saldo": tiefst["saldo"], "von": tiefst["von"]}, "ueberfaellig": ueber,
            "hinweise": hinweise, "einstellungen": cfg}
