"""Werkstattpapiere und Auswertungen eines Auftrags als druckfertige HTML-Seiten.

Werkstatt:  Werkstattauftrag, Stückliste, Materialsummen, Zuschnittliste (CSV)
Auswertung: Auftragsstunden, Auftragskosten, Soll/Ist-Vergleich, Lohn- und Materialkosten
"""
import kern
from kern import zahl_lesen, de_menge
import csv
from kalkulation import fertigdicke, anzahl_verbinden, kostenliste
import io
import re
from datetime import datetime

MASS_ARTEN = {"HBT": "hbt", "BHT": "bht", "LBD": "lbd"}  # Reihenfolge der Maße je Maßart

WERKSTATT = {"werkstattauftrag": "Werkstattauftrag", "stueckliste": "Stückliste", "materialsummen": "Materialsummen"}
AUSWERTUNG = {"stunden": "Auftragsstunden", "kosten": "Auftragskosten", "sollist": "Soll/Ist-Vergleich",
              "lohnmaterial": "Lohn- und Materialkosten", "zeitbericht": "Zeitbericht"}
SEITEN = {"oben": "O", "unten": "U", "links": "L", "rechts": "R"}
LAGE_KZ = {"oben": "O", "unten": "U", "vorn": "V", "hinten": "H", "mitte": "M"}


def f(x):
    """Zahl aus einem gespeicherten Wert; Texte in deutscher Schreibweise werden gelesen, Unlesbares zählt als 0."""
    if isinstance(x, (int, float)):
        return float(x) if x == x and abs(x) != float("inf") else 0.0
    return (zahl_lesen(x) or 0.0) if x else 0.0


def klar(t):
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li)>", "\n", str(t or ""))
    s = re.sub(r"<[^>]+>", "", s)
    from html import unescape
    return unescape(s).strip()


def kurztext(t):
    return (klar(t).split("\n") or [""])[0]


# ---------------------------------------------------------------- Daten aufbereiten
def stk(t):
    """Stückzahl eines Stücklistenteils; leer = 1 Stück (wie in der Kalkulation)."""
    return 1.0 if t.get("stueck") in (None, "") else f(t.get("stueck"))


def alle_positionen(erg, nur=None):
    """Haupt- und Unterpositionen in Druckreihenfolge mit Gesamtfaktor (Menge Hauptposition × Menge Unterposition).
    Gesperrte Positionen, Alternativpositionen und Positionen gesperrter Titel werden nicht gefertigt und fehlen,
    außer sie wurden ausdrücklich ausgewählt (nur)."""
    titel_name = {t["nr"]: t["name"] for t in erg["titel"]}
    titel_gesperrt = {t["nr"] for t in erg["titel"] if t.get("gesperrt")}
    liste = []
    for p in erg["positionen"]:
        if nur and p["id"] not in nur:
            continue
        if not nur and (p.get("gesperrt") or p.get("alternativ") or p["titel"] in titel_gesperrt):
            continue
        m = f(p["menge"])
        liste.append({"p": p, "nr": p["posnr"], "faktor": m, "ebene": 0, "titel": p["titel"],
                      "titelname": titel_name.get(p["titel"], "")})
        for k in p["kinder"]:
            if k.get("gesperrt"):
                continue
            liste.append({"p": k, "nr": f"{p['posnr']}.{k['posnr']}", "faktor": m * f(k["menge"]), "ebene": 1,
                          "titel": p["titel"], "titelname": titel_name.get(p["titel"], "")})
    return liste


def werkstoff_index(kalk):
    return {w["k"]: w for w in kalk.get("werkstoffe", []) if w.get("k")}


def beschlag_index(kalk):
    return {b["k"]: b for b in kalk.get("beschlaege", []) if b.get("k")}


def materialsummen(erg, nur=None):
    """Summiert Platten, Massivholz, Kanten, Furnier, Oberfläche und Beschläge je Werkstoffkürzel."""
    wks, bss = werkstoff_index(erg["kalk"]), beschlag_index(erg["kalk"])
    summen = {}

    def add(kz, menge, stueck=0, flaechen=0):
        if not kz:
            return
        s = summen.setdefault(kz, {"menge": 0.0, "stueck": 0, "flaechen": 0})
        s["menge"] += menge
        s["stueck"] += stueck
        s["flaechen"] += flaechen

    beschlaege = {}
    for e in alle_positionen(erg, nur):
        p, fak = e["p"], e["faktor"]
        for t in p.get("stueckliste") or []:
            n = stk(t) * fak
            l, b = f(t.get("laenge")) / 1000, f(t.get("breite")) / 1000
            w = wks.get(t.get("werkstoff") or "")
            dicke = f(w.get("dicke")) if w and f(w.get("dicke")) else f(t.get("dicke"))   # Rohdicke für das Volumen
            fdicke = fertigdicke(t, w)
            if w:   # Mengen wie in der Kalkulation (kalkulation.teil_rechnen)
                ein = w.get("einheit") or ""
                if w.get("typ") == "massiv" and ein not in ("m²", "m2", "lfm", "lfm.", "Stk.", "St.", "Stk"):
                    add(w["k"], l * b * dicke / 1000 * n, n)
                elif ein in ("lfm", "lfm."):
                    add(w["k"], l * n, n)
                elif ein in ("Stk.", "St.", "Stk"):
                    add(w["k"], n, n)
                else:
                    add(w["k"], l * b * n, n)
            kanten = t.get("kanten") or {}
            for seite, laenge in (("oben", l), ("unten", l), ("links", b), ("rechts", b)):
                add(kanten.get(seite), laenge * n)
            for s in ("oben", "unten"):
                add((t.get("furnier") or {}).get(s), l * b * n)
            ofl = t.get("oberflaeche") or {}
            seiten = [s for s in ("oben", "unten") if ofl.get(s)]
            # Schmalflächen wie in der Kalkulation: ganzer Umfang × Fertigdicke, einmal je Teil
            for i, s in enumerate(seiten):
                add(ofl[s], (l * b + (2 * (l + b) * fdicke / 1000 if i == 0 else 0)) * n, 0, int(round(n)))
        for bz in p.get("beschlaege") or []:
            if bz.get("k"):
                beschlaege[bz["k"]] = beschlaege.get(bz["k"], 0) + f(bz.get("menge")) * fak
    gruppen = {"platte": [], "massiv": [], "kante": [], "furnier": [], "oberflaeche": [], "sonstig": []}
    for kz, s in summen.items():
        w = wks.get(kz)
        if not w:
            continue
        v = f(w.get("v"))
        brutto = s["menge"] * (1 + v / 100)
        gruppen.setdefault(w.get("typ") or "sonstig", []).append({
            "k": kz, "name": w.get("name") or "", "einheit": w.get("einheit") or "", "dicke": f(w.get("dicke")),
            "stueck": s["stueck"], "flaechen": s["flaechen"], "netto": s["menge"], "v": v, "brutto": brutto,
            "preis": f(w.get("preis")), "betrag": brutto * f(w.get("preis")), "matnr": w.get("matnr") or "",
            "lieferant": w.get("lieferant") or "", "bestellnr": w.get("bestellnr") or ""})
    bliste = []
    for kz, m in beschlaege.items():
        b = bss.get(kz) or {}
        v = 0.0   # Beschläge haben keinen Verschnitt
        bliste.append({"k": kz, "artnr": b.get("artnr") or "", "matnr": b.get("matnr") or b.get("artnr") or "",
                       "lieferant": b.get("lieferant") or "", "bestellnr": b.get("bestellnr") or "", "name": b.get("name") or "", "einheit": b.get("einheit") or "",
                       "menge": m, "v": v, "preis": f(b.get("preis")), "betrag": m * f(b.get("preis")) * (1 + v / 100)})
    for g in gruppen.values():
        g.sort(key=lambda x: x["k"])
    bliste.sort(key=lambda x: x["k"])
    return gruppen, bliste


def vorgabezeiten(erg, nur=None):
    """Stunden je Kostenstelle (Gesamtauftrag oder ausgewählte Positionen)."""
    kst = {}
    for e in alle_positionen(erg, nur):
        for k, h in (e["p"]["_calc"].get("stunden_kst") or {}).items():
            kst[k] = kst.get(k, 0) + h * e["faktor"]
    return kst


def zuschnitt_csv(erg, nur=None, zs=None):
    wks = werkstoff_index(erg["kalk"])
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Position", "Nr", "Verwendung", "Werkstoff", "Werkstoff-Bezeichnung", "Stück", "Länge", "Breite", "Dicke",
                "Kante oben", "Kante unten", "Kante links", "Kante rechts", "Bemerkung", "Zuschnitt Länge", "Zuschnitt Breite"])
    for e in alle_positionen(erg, nur):
        for i, t in enumerate(e["p"].get("stueckliste") or [], 1):
            wk = wks.get(t.get("werkstoff") or "") or {}
            ka = t.get("kanten") or {}
            dicke = fertigdicke(t, wk)
            w.writerow([e["nr"], f"{i:03d}", t.get("verwendung") or "", t.get("werkstoff") or "", wk.get("name") or "",
                        _zahl(stk(t) * e["faktor"], 0), _zahl(t.get("laenge"), 1), _zahl(t.get("breite"), 1),
                        _zahl(dicke, 1), ka.get("oben") or "", ka.get("unten") or "", ka.get("links") or "",
                        ka.get("rechts") or "", t.get("bemerkung") or ""]
                       + [_zahl(x, 1) for x in zuschnitt_mass(t, wk, wks, zs if (zs or {}).get("aktiv") else {"platte_l": 0, "platte_b": 0, "massiv_l": 0, "massiv_b": 0})])
    return "﻿" + buf.getvalue()


def zuschnitt_daten(erg, nur=None):
    """Teile als JSON für ein Zuschnittprogramm."""
    wks = werkstoff_index(erg["kalk"])
    teile = []
    for e in alle_positionen(erg, nur):
        for i, t in enumerate(e["p"].get("stueckliste") or [], 1):
            wk = wks.get(t.get("werkstoff") or "") or {}
            teile.append({"position": e["nr"], "nr": i, "verwendung": t.get("verwendung") or "", "werkstoff": t.get("werkstoff") or "",
                          "werkstoff_name": wk.get("name") or "", "dicke": fertigdicke(t, wk),
                          "stueck": round(stk(t) * e["faktor"]), "laenge": f(t.get("laenge")),
                          "breite": f(t.get("breite")), "kanten": t.get("kanten") or {}, "bemerkung": t.get("bemerkung") or ""})
    return teile


def _zahl(x, n=2):
    return f"{f(x):.{n}f}".replace(".", ",")


# ---------------------------------------------------------------- HTML-Rahmen
LOGO = {"datenuri": lambda: ""}   # wird von app.py gesetzt (Logo aus den Einstellungen als data:-URI)

CSS = """
@page { size: A4; margin: 14mm 12mm 14mm 16mm; }
.as { margin-top: .6mm; font-size: 8pt; color: #8a3a12; } .as a { color: #1f5aa6; } .as img.ghs { height: 4.6mm; vertical-align: middle; margin-left: .8mm; }
.gsbox { border: .8pt solid #c8501e; padding: 1.5mm 2.5mm; margin-top: 1mm; } .gsbox .z { margin: .8mm 0; }
@media print { html, body { background: #fff; } .blatt { padding: 0; margin: 0; max-width: none; box-shadow: none; } .kopf { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
.sek, table.t tr.sum td, .fuss { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.kopf .logo { flex: 0 0 auto; align-self: center; } .kopf .logo img { max-height: 15mm; max-width: 42mm; display: block; }
.logozeile { display: flex; justify-content: flex-end; margin: 0 0 2.5mm; } .logozeile img { max-height: 17mm; max-width: 55mm; display: block; }
.kopf .titelblock { flex: 1 1 auto; }
* { box-sizing: border-box; }
body { font: 9pt/1.35 Arial, Helvetica, sans-serif; color: #111; margin: 0; }
.leiste { position: sticky; top: 0; background: #3b3530; color: #fff; padding: 8px 14px; display: flex; gap: 10px; align-items: center; font: 14px system-ui; z-index: 5; }
.leiste button { font: inherit; padding: 4px 12px; border-radius: 5px; border: 0; background: #b8834f; color: #fff; cursor: pointer; }
.blatt { max-width: 190mm; margin: 0 auto; }
@media screen { body { background: #888; } .blatt { background: #fff; padding: 12mm 12mm 14mm 16mm; margin: 14px auto; max-width: 210mm; box-shadow: 0 2px 12px rgba(0,0,0,.3); } }
@media print { .leiste { display: none; } }
.kopf { background: #e8e8e8; padding: 2.5mm 3mm; display: flex; justify-content: space-between; gap: 4mm; align-items: flex-start; }
.kopf h1 { font-size: 15pt; margin: 0 0 3mm; letter-spacing: .3px; }
.kopf .k2 { font-size: 8pt; }
.kopf .k2 b { font-size: 9pt; }
.kopf .rechts { display: flex; gap: 3mm; align-items: flex-start; font-size: 7.5pt; }
.kopf .rechts table td { padding: 0 1mm; }
.kopf .rechts .nr { font-size: 13pt; font-weight: 700; }
.kopf svg { width: 16mm; height: 16mm; }
h2 { font-size: 12pt; margin: 6mm 0 1.5mm; }
.sek { background: #e8e8e8; font-weight: 700; padding: 1mm 2mm; margin: 4mm 0 1.5mm; }
table.t { width: 100%; border-collapse: collapse; }
table.t th { text-align: left; font-size: 7.5pt; border-bottom: .8pt solid #000; padding: .8mm 1mm; }
table.t td { padding: 1mm; vertical-align: top; border-bottom: .3pt solid #bbb; }
table.t tr { page-break-inside: avoid; }
table.t tr.sum td { font-weight: 700; border-top: .8pt solid #000; border-bottom: none; }
table.t tr.tit td { font-weight: 700; background: #f2f2f2; }
.r { text-align: right; } .nw { white-space: nowrap; } .k { font-size: 7.5pt; color: #444; }
.code { border: .6pt solid #000; font-size: 6.5pt; padding: 0 .8mm; margin-right: .6mm; display: inline-block; line-height: 1.3; }
.code.dunkel { background: #000; color: #fff; }
.postext { white-space: normal; }
.postext p, .postext div { margin: 0 0 1mm; }
.postext ul { margin: .5mm 0 1mm 4mm; padding-left: 3mm; }
.bilder img { max-width: 70mm; max-height: 55mm; margin: 1mm 2mm 1mm 0; border: .3pt solid #ccc; }
.linie td { height: 8mm; border-bottom: .5pt solid #000 !important; }
.fuss { text-align: center; font-size: 7.5pt; color: #444; background: #e8e8e8; padding: 1mm; margin-top: 8mm; }
.neue-seite { page-break-before: always; }
.wi { margin: 1.5mm 0 1mm; border-left: 1.2mm solid #b8834f; background: #f5efe7; padding: 1mm 2.5mm; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.wi b { font-size: 7.5pt; letter-spacing: .4px; } .wi div { white-space: pre-wrap; font-weight: 600; }
.zwei { display: grid; grid-template-columns: 1fr 1fr; gap: 0 5mm; }
.vzs { display: flex; flex-wrap: wrap; gap: 1.5mm; }
.vz { border: .4pt solid #999; border-radius: 1mm; padding: 1mm 2.5mm; min-width: 20mm; }
.vz span { display: block; font-size: 7pt; color: #444; } .vz b { font-size: 10pt; }
.vz.summe { background: #e8e8e8; border-color: #e8e8e8; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.legende td { padding: .6mm 1mm; font-size: 8pt; vertical-align: top; }
"""


def rahmen(titel, a, k, inhalt, hilfe, opts=None, pdf=False, leiste_extra=""):
    h, ddat = hilfe["h"], hilfe["de_datum"]
    basis = LOGO.get("scan_basis", lambda: "")()
    qr = hilfe["qr"](f"{basis}scan#a{a['id']}" if basis and a.get("id") else f"{a['nummer']} {a['bezeichnung']}")
    leiste = "" if pdf else ('<div class="leiste"><b>' + h(titel) + '</b> · Auftrag ' + h(a["nummer"]) + leiste_extra
                             + '<span style="flex:1"></span><button data-drucken>Drucken</button></div>')
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>{h(titel)} {h(a['nummer'])}</title>
<style>{CSS}</style></head><body>{leiste}<div class="blatt">
{logo_zeile()}<div class="kopf"><div class="titelblock"><h1>{h(titel.upper())}</h1>
<div class="k2">Auftrag <b>{h(a['nummer'])} {h(a['bezeichnung'])}</b><br>Kunde <b>{h(k.get('nummer'))} {h(k.get('kurzname'))}</b></div></div>
<div class="rechts">{qr}<table><tr><td>Nr.</td><td class="nr">{h(a['nummer'])}</td></tr>
<tr><td>Fertigung</td><td><b>{h(_datum(a.get('fertigung') or a.get('plan_von'), ddat))}</b></td></tr>
<tr><td>Lieferung</td><td><b>{h(_datum(a.get('lieferung') or (a.get('plan_bis') if a.get('plan_bis') != a.get('plan_von') else ''), ddat))}</b></td></tr>
<tr><td>Status</td><td>{h(a.get('status') or '')}</td></tr></table></div></div>
{inhalt}
<div class="fuss">{h(hilfe['ersteller'])} · {datetime.now():%d.%m.%Y · %H:%M}</div>
</div></body></html>"""


def _logo():
    uri = LOGO["datenuri"]()
    return f'<div class="logo"><img src="{uri}" alt=""></div>' if uri else ""


def logo_zeile():
    """Firmenlogo oben rechts über dem grauen Kopf – wie auf Angeboten und Rechnungen."""
    l = _logo()
    return f'<div class="logozeile">{l}</div>' if l else ""


def _datum(x, ddat):
    x = (x or "").strip()
    return ddat(x) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x) else x


def anschrift_block(k, opts, hilfe, titel="Lieferanschrift"):
    h = hilfe["h"]
    teile = []
    if opts.get("anschrift", True):
        adr = (k.get("lieferanschrift") or "").strip()
        if adr:
            zeile = " · ".join(x.strip() for x in (adr + "\n" + (k.get("lieferort") or "")).split("\n") if x.strip())
        else:
            zeile = " · ".join(x.strip() for x in ((k.get("anschrift") or "").split("\n") + [f"{k.get('plz') or ''} {k.get('ort') or ''}".strip()]) if x.strip())
        teile.append(f'<div><div class="sek">{titel}</div><div>{h(zeile) or "–"}</div></div>')
    if opts.get("telefon", True):
        tel = " · ".join(x for x in [k.get("telefon"), k.get("mobil") if k.get("mobil") else ""] if x)
        teile.append(f'<div><div class="sek">Telefon</div><div>{h(tel) or "–"}</div></div>')
    return f'<div class="zwei">{"".join(teile)}</div>' if teile else ""


# ---------------------------------------------------------------- Werkstattpapiere
def werkstattauftrag(a, k, erg, opts, hilfe, nur=None):
    h, de = hilfe["h"], hilfe["de"]
    kst = vorgabezeiten(erg, nur)
    reihen = [x["kst"] for x in erg["kalk"].get("kostenstellen", [])]
    reihen += [x for x in kst if x not in reihen]
    reihen = [x for x in reihen if f(kst.get(x)) > 0.004]   # nur Kostenstellen mit Vorgabezeit
    if reihen:
        kacheln = "".join(f'<div class="vz"><span>{h(x.title())}</span><b>{de(kst.get(x, 0), 1)} h</b></div>' for x in reihen)
        zeiten = (f'<div class="sek">Vorgabezeiten</div><div class="vzs">{kacheln}'
                  f'<div class="vz summe"><span>Summe</span><b>{de(sum(kst.values()), 1)} h</b></div></div>')
    else:
        zeiten = '<div class="sek">Vorgabezeiten</div><div class="k">Für diesen Auftrag sind keine Stunden kalkuliert.</div>'
    zeilen = []
    letzter = None
    for e in alle_positionen(erg, nur):
        p = e["p"]
        if e["titel"] != letzter and e["titelname"] and e["ebene"] == 0:
            zeilen.append(f'<tr class="tit"><td colspan="3">{h(e["titelname"])}</td></tr>')
        letzter = e["titel"]
        text = hilfe["text_html"](p["text"]) if opts.get("bemerkungen", True) else h(kurztext(p["text"]))
        masse = p.get("masse") or {}
        mtxt = " × ".join(f"{k.upper()} {de(masse[k], 0)}" for k in MASS_ARTEN.get(masse.get("art"), "hbt") if f(masse.get(k)))
        bilder = ""
        if opts.get("bilder", True):
            bilder = "".join(f'<img src="/api/bild/{h(x["datei"])}">' for x in (p.get("bilder") or []) if x.get("datei"))
        wi = ((p.get("extras") or {}).get("werkstattinfo") or "").strip()
        wi_html = f'<div class="wi"><b>FERTIGUNG</b><div>{h(wi)}</div></div>' if wi else ""
        # freie Kostenliste: was zugekauft oder außer Haus gemacht wird, mit Menge
        extern = []
        for z in kostenliste(p.get("extras")):
            if z.get("art") == "sonder_vertrieb":   # Provision, Versand usw. gehören nicht in die Werkstatt
                continue
            art = {"fremdleistungen": "Fremdleistung", "zukauf": "Zukauf", "sonder_fertigung": "Sonderkosten"}.get(z.get("art"), "Material")
            m = 1.0 if z.get("menge") in (None, "") else f(z.get("menge"))
            ein = (z.get("einheit") or "").strip()
            menge = "" if m == 1 and ein in ("", "psch", "Pauschale", "(keine)") else (f"{de(m, 0 if m == int(m) else 2 if round(m, 2) == m else 3)} {ein}".strip() + " ")
            extern.append(f"{art}: {menge}{(z.get('text') or '').strip() or 'ohne Beschreibung'}")
        if extern:
            wi_html += '<div class="k">' + " · ".join(h(x) for x in extern) + '</div>'
        zeilen.append(f'<tr><td class="nw">{h(e["nr"])}</td><td class="r nw">{de_menge(p["menge"])} {h(p["einheit"])}</td>'
                      f'<td class="postext">{text}{f"<div class=k>Maße: {mtxt} mm</div>" if mtxt else ""}{wi_html}'
                      f'{f"<div class=bilder>{bilder}</div>" if bilder else ""}</td></tr>')
    pos = f'<div class="sek">Positionen</div><table class="t"><tr><th style="width:14mm">Pos.</th><th class="r" style="width:20mm">Menge</th><th>Beschreibung</th></tr>{"".join(zeilen)}</table>'
    return anschrift_block(k, opts, hilfe) + zeiten + pos + gefahrstoff_block(hilfe)


def as_links_html(l, hilfe):
    """Hinweis „Gefahrstoff“ mit Piktogrammen und Links auf Sicherheitsdatenblatt, Merkblatt und Betriebsanweisung."""
    if not l:
        return ""
    h, pdf = hilfe["h"], hilfe.get("pdf")
    teile = []
    if l.get("gefahrstoff"):
        ghs = l["gefahrstoff"] if isinstance(l["gefahrstoff"], list) else []
        teile.append("⚠ Gefahrstoff" + "".join(f'<img class="ghs" src="/arbeitsschutz/zeichen/{h(g)}.png" alt="{h(g)}">' for g in ghs))
    for key, text, url in (("sdb", "Sicherheitsdatenblatt", "/api/arbeitsschutz/datei/{}"), ("tdb", "Technisches Merkblatt", "/api/arbeitsschutz/datei/{}"),
                           ("ba", "Betriebsanweisung", "/druck/arbeitsschutz/ba/{}")):
        if l.get(key):
            teile.append(h(text) if pdf else f'<a href="{url.format(int(l[key]))}" target="_blank">{h(text)}</a>')
    if not teile:
        return ""
    zusatz = ' <span style="color:#666">(im Programm hinterlegt)</span>' if pdf and any(l.get(x) for x in ("sdb", "tdb", "ba")) else ""
    return '<div class="as">' + " · ".join(teile) + zusatz + "</div>"


def gefahrstoff_block(hilfe):
    """Werkstattauftrag: Gefahrstoffe und Datenblätter der Materialien dieses Auftrags."""
    liste = hilfe.get("as_auftrag") or []
    if not liste:
        return ""
    h = hilfe["h"]
    z = []
    for x in liste:
        links = {"gefahrstoff": x["ghs"] or x["gefahrstoff"], "sdb": next((d["id"] for d in x["dateien"] if d["art"] == "sdb"), None),
                 "tdb": next((d["id"] for d in x["dateien"] if d["art"] == "tdb"), None), "ba": (x.get("ba") or {}).get("id")}
        psa = f'<div class="k">Schutzausrüstung: {h(x["psa"])}</div>' if x.get("psa") else ""
        z.append(f'<div class="z"><b>{h(x["name"])}</b> <span class="k">{h(x["nummer"])}</span>{as_links_html(links, hilfe)}{psa}</div>')
    return '<div class="sek">Gefahrstoffe und Datenblätter in diesem Auftrag</div><div class="gsbox">' + "".join(z) + "</div>"


def _codes(t, wks):
    """Bearbeitungscodes: Kanten, Fräsen, Verbinden, Furnier, Oberfläche."""
    ka = t.get("kanten") or {}
    kanten = " ".join(f'{SEITEN[s]} {ka[s]}' for s in ("links", "rechts", "oben", "unten") if ka.get(s))
    fr = [SEITEN[s] for s in ("links", "rechts", "oben", "unten") if (t.get("fraesen") or {}).get(s)]
    vb = [LAGE_KZ[s] for s in LAGE_KZ if (t.get("verbinden") or {}).get(s)]
    fu = t.get("furnier") or {}
    of = t.get("oberflaeche") or {}
    return kanten, fr, vb, fu, of


ZUSCHNITT_VORGABE = {"aktiv": False, "platte_l": 0, "platte_b": 0, "massiv_l": 50, "massiv_b": 10, "kanten_abziehen": False}


def zuschnitt_mass(t, w, wks, z):
    """Zuschnittmaß (Länge, Breite) aus dem Fertigmaß: optional Kantenstärken abziehen, dann Zugabe je Werkstoffart."""
    z = {**ZUSCHNITT_VORGABE, **(z or {})}
    l, b = f(t.get("laenge")), f(t.get("breite"))
    if z.get("kanten_abziehen"):
        ka = t.get("kanten") or {}
        # Kanten oben/unten laufen entlang der Länge und verkürzen die Breite, links/rechts verkürzen die Länge
        b -= sum(f((wks.get(ka.get(s) or "") or {}).get("dicke")) for s in ("oben", "unten") if ka.get(s))
        l -= sum(f((wks.get(ka.get(s) or "") or {}).get("dicke")) for s in ("links", "rechts") if ka.get(s))
    art = "massiv" if (w or {}).get("typ") == "massiv" else "platte"
    return round(l + f(z.get(art + "_l")), 1), round(b + f(z.get(art + "_b")), 1)


def stueckliste(a, k, erg, opts, hilfe, nur=None):
    h, de = hilfe["h"], hilfe["de"]
    wks, bss = werkstoff_index(erg["kalk"]), beschlag_index(erg["kalk"])
    zs = hilfe.get("zuschnitt") or {}
    mit_zs = bool(zs.get("aktiv"))
    teile = []
    for e in alle_positionen(erg, nur):
        p = e["p"]
        sl, bs = p.get("stueckliste") or [], p.get("beschlaege") or []
        if not sl and not bs:
            continue
        benutzt = set()
        z = []
        for i, t in enumerate(sl, 1):
            w = wks.get(t.get("werkstoff") or "") or {}
            dicke = fertigdicke(t, w)
            kanten, fr, vb, fu, of = _codes(t, wks)
            for kz in list((t.get("kanten") or {}).values()) + list(fu.values()) + list(of.values()):
                if kz:
                    benutzt.add(kz)
            n_vb = anzahl_verbinden(t)
            bl = [LAGE_KZ[s] for s in LAGE_KZ if (t.get("bohren_lage") or {}).get(s)]
            bearb = (f'<span class="code">FR {" ".join(fr)}</span>' if fr else "") \
                + (f'<span class="code">VB {de(n_vb, 0)}×{" " + " ".join(vb) if vb else ""}</span>' if n_vb else "") \
                + (f'<span class="code">Bohren {de(f(t.get("bohren")), 0)}×{" " + " ".join(bl) if bl else ""}</span>' if f(t.get("bohren")) else "") \
                + (f'<span class="code">Tasche {de(f(t.get("taschen")), 0)}×'
                   + (f' {de(f(t.get("tasche_l")), 0)}×{de(f(t.get("tasche_b")), 0)}' if f(t.get("tasche_l")) and f(t.get("tasche_b")) else "")
                   + (f' T{de(f(t.get("tasche_t")), 1).replace(",0", "")}' if f(t.get("tasche_t")) else (" durch" if f(t.get("tasche_l")) else ""))
                   + '</span>' if f(t.get("taschen")) else "") \
                + (f'<span class="code">Gehrung {de(f(t.get("gehrung")), 0)}×</span>' if f(t.get("gehrung")) else "")
            fo = "<br>".join(x for x in [f'V {h(fu.get("oben"))}' if fu.get("oben") else "", f'R {h(fu.get("unten"))}' if fu.get("unten") else ""] if x)
            oo = "<br>".join(x for x in [f'<span class="code dunkel">V {h(of.get("oben"))}</span>' if of.get("oben") else "",
                                         f'<span class="code dunkel">R {h(of.get("unten"))}</span>' if of.get("unten") else ""] if x)
            z.append(f'<tr><td>{i:03d}</td><td>{h(t.get("verwendung") or "")}{"<div class=k>" + h(t["bemerkung"]) + "</div>" if t.get("bemerkung") else ""}'
                     f'{"<div>" + bearb + "</div>" if bearb else ""}</td><td><b>{h(t.get("werkstoff") or "")}</b><div class="k">{h(w.get("name") or "")}</div></td>'
                     f'<td class="r">{de(stk(t) * e["faktor"], 0)}</td><td class="r nw">{de(t.get("laenge"), 1)}</td>'
                     f'<td class="r nw">{de(t.get("breite"), 1)}</td><td class="r nw">{de(dicke, 1)}</td>'
                     + (lambda m: f'<td class="r nw zs">{de(m[0], 1)} × {de(m[1], 1)}</td>' if mit_zs else "")(zuschnitt_mass(t, w, wks, zs))
                     + f'<td class="nw">{h(kanten)}</td><td class="nw">{fo}</td><td class="nw">{oo}</td></tr>')
        legende = " · ".join(f"{kz}={h(wks[kz].get('name') or '')}{(' ' + de(wks[kz].get('dicke'), 1)) if f(wks[kz].get('dicke')) else ''}"
                             for kz in sorted(benutzt) if kz in wks)
        block = (f'<div style="page-break-inside:avoid"><h2>Position {h(e["nr"])} &nbsp; {de_menge(p["menge"])} {h(p["einheit"])} {h(kurztext(p["text"]))}</h2>')
        if sl:
            block += ('<div class="sek">Hauptwerkstoffe</div><table class="t"><tr><th>Nr</th><th>Verwendung</th><th>Werkstoff</th><th class="r">Stück</th>'
                      '<th class="r">Länge</th><th class="r">Breite</th><th class="r">Dicke</th>' + ('<th class="r">Zuschnitt L × B</th>' if mit_zs else "")
                      + '<th>Kanten</th><th>Furnier</th><th>Oberfl.</th></tr>'
                      + "".join(z) + "</table>" + (f'<div class="k" style="margin-top:1mm">{legende}</div>' if legende else ""))
        if bs:
            bz = []
            for i, b in enumerate(bs, 1):
                st = bss.get(b.get("k") or "") or {}
                bz.append(f'<tr><td>{i:03d}</td><td><b>{h(st.get("artnr") or b.get("k") or "")}</b></td><td class="r nw">{de(f(b.get("menge")) * e["faktor"])} </td>'
                          f'<td>{h(st.get("einheit") or "")}</td><td>{h(st.get("name") or "")}{" · " + h(b["bemerkung"]) if b.get("bemerkung") else ""}</td></tr>')
            block += ('<div class="sek">Beschläge</div><table class="t"><tr><th>Nr</th><th>Beschlag</th><th class="r">Anzahl</th><th>Me</th>'
                      '<th>Bezeichnung/Bemerkung</th></tr>' + "".join(bz) + "</table>")
        teile.append(block + "</div>")
    if not teile:
        teile.append('<p>Für diesen Auftrag ist noch keine Stückliste erfasst.</p>')
    erkl = ('<div class="neue-seite"></div><h2>Erläuterungen zur Stückliste</h2><table class="legende">'
            '<tr><td><b>Stück</b></td><td>Gesamtstückzahl für die Position (Stück je Möbel × Anzahl der Position).</td></tr>'
            '<tr><td><b>Länge/Breite/Dicke</b></td><td>Fertigmaße in mm. Die Länge entspricht der Laufrichtung von Furnier bzw. Maserung.</td></tr>'
            + ('<tr><td><b>Zuschnitt</b></td><td>Zuschnittmaß in mm: ' + ("Fertigmaß abzüglich Kantenstärken, " if zs.get("kanten_abziehen") else "Fertigmaß ")
               + f'zuzüglich Zugabe (Platten L +{de(zs.get("platte_l"), 0)} / B +{de(zs.get("platte_b"), 0)}, Massivholz L +{de(zs.get("massiv_l"), 0)} / B +{de(zs.get("massiv_b"), 0)}).</td></tr>' if mit_zs else "")
            + '<tr><td><b>Kanten</b></td><td>L/R/O/U = links, rechts, oben, unten, bezogen auf die Laufrichtung, mit Werkstoffkürzel (z. B. O K01).</td></tr>'
            '<tr><td><b>Furnier / Oberfläche</b></td><td>V = Vorderseite, R = Rückseite, mit Werkstoffkürzel.</td></tr>'
            '<tr><td><b>FR / VB / Bohren</b></td><td>Fräsen an den genannten Kanten; Verbinden und Bohren mit Anzahl und Lage (O oben, U unten, V vorn, H hinten, M Mitte); Tasche = Taschen/Ausschnitte fräsen.</td></tr></table>') if opts.get("erklaerung") else ""
    return "".join(teile) + erkl


def materialsummen_html(a, k, erg, opts, hilfe, nur=None):
    h, de = hilfe["h"], hilfe["de"]
    gruppen, bliste = materialsummen(erg, nur)
    namen = {"platte": ("Platten", "Stück", "m²"), "massiv": ("Massivholz", "Stück", "m³"), "kante": ("Kanten", "", "lfm"),
             "furnier": ("Furnier", "", "m²"), "oberflaeche": ("Oberfläche", "Flächen", "m²"), "sonstig": ("Sonstiges", "Stück", "")}
    teile, gesamt = [], 0.0
    preise = opts.get("preise", True)
    stamm = hilfe.get("stamm") or {}

    def bezug(x):
        # zuerst die beim Übernehmen in den Auftrag kopierten Angaben, sonst der Materialstamm
        st = {"lieferant": x.get("lieferant"), "bestellnr": x.get("bestellnr")} if (x.get("lieferant") or x.get("bestellnr")) \
            else stamm.get(x.get("matnr") or "") or {}
        t = " · ".join(v for v in [st.get("lieferant") or "", ("Best.-Nr. " + st["bestellnr"]) if st.get("bestellnr") else ""] if v)
        return (f'<div class="k">{h(t)}</div>' if t else "") + as_links_html((hilfe.get("as_links") or {}).get(x.get("matnr") or ""), hilfe)
    for typ, liste in gruppen.items():
        if not liste:
            continue
        titel, spalte, einheit = namen.get(typ, (typ, "", ""))
        z = []
        for x in liste:
            gesamt += x["betrag"]
            nachk = 3 if typ == "massiv" else 2
            e_txt = x["einheit"] or einheit
            z.append(f'<tr><td><b>{h(x["name"] or x["k"])}</b>{" " + de(x["dicke"], 1) + " mm" if x["dicke"] and typ in ("platte", "kante") else ""}{bezug(x)}</td>'
                     f'<td><b>{h(x["k"])}</b>{"<div class=k>+ " + de(x["v"], 0) + " % Verschnitt</div>" if x["v"] else ""}</td>'
                     f'<td class="r">{(de(x["flaechen"] if typ == "oberflaeche" else x["stueck"], 0)) if spalte else ""}</td>'
                     f'<td class="r nw">{de(x["netto"], nachk)} {h(e_txt)}{"<div><b>" + de(x["brutto"], nachk) + " " + h(e_txt) + "</b></div>" if x["v"] else ""}</td>'
                     + (f'<td class="r nw k">{de(x["preis"])} €/{h(e_txt)}</td><td class="r nw"><b>{de(x["betrag"])} €</b></td>' if preise else "") + "</tr>")
        teile.append(f'<h2>{h(titel.upper())}</h2><table class="t"><tr><th>Bezeichnung</th><th>Werkstoff</th><th class="r">{spalte}</th>'
                     f'<th class="r">Menge</th>{"<th class=r>EK-Preis</th><th class=r>Betrag</th>" if preise else ""}</tr>{"".join(z)}</table>')
    if bliste:
        z = []
        for x in bliste:
            gesamt += x["betrag"]
            z.append(f'<tr><td><b>{h(x["name"] or x["k"])}</b>{bezug(x)}</td><td><b>{h(x["artnr"] or x["k"])}</b></td><td class="r nw">{de(x["menge"])} {h(x["einheit"])}</td>'
                     + (f'<td class="r nw k">{de(x["preis"])} €/{h(x["einheit"])}</td><td class="r nw"><b>{de(x["betrag"])} €</b></td>' if preise else "") + "</tr>")
        teile.append(f'<h2>BESCHLÄGE</h2><table class="t"><tr><th>Bezeichnung</th><th>Beschlag</th><th class="r">Menge</th>'
                     f'{"<th class=r>EK-Preis</th><th class=r>Betrag</th>" if preise else ""}</tr>{"".join(z)}</table>')
    # Kostenliste der Positionen (Werkstoffe, Zukauf, Fremdleistungen) mit Menge × Auftragsmenge
    kl = {}
    for e in alle_positionen(erg, nur):
        for z_ in kostenliste(e["p"].get("extras")):
            art = z_.get("art") or "werkstoffe"
            if art not in ("werkstoffe", "zukauf", "fremdleistungen"):
                continue
            m = (1.0 if z_.get("menge") in (None, "") else f(z_.get("menge"))) * e["faktor"]
            key = (art, (z_.get("text") or "").strip(), z_.get("einheit") or "", f(z_.get("preis")))
            kl[key] = kl.get(key, 0.0) + m
    if kl:
        z = []
        artname = {"werkstoffe": "Werkstoff", "zukauf": "Zukauf", "fremdleistungen": "Fremdleistung"}
        for (art, text, ein, preis), m in sorted(kl.items(), key=lambda x: (x[0][0], x[0][1])):
            gesamt += m * preis
            z.append(f'<tr><td><b>{h(text or "ohne Beschreibung")}</b></td><td>{artname[art]}</td><td class="r nw">{de(m)} {h(ein)}</td>'
                     + (f'<td class="r nw k">{de(preis)} €{"/" + h(ein) if ein else ""}</td><td class="r nw"><b>{de(m * preis)} €</b></td>' if preise else "") + "</tr>")
        teile.append(f'<h2>KOSTENLISTE (ZUKAUF, FREMDLEISTUNGEN)</h2><table class="t"><tr><th>Bezeichnung</th><th>Art</th><th class="r">Menge</th>'
                     f'{"<th class=r>Preis</th><th class=r>Betrag</th>" if preise else ""}</tr>{"".join(z)}</table>')
    if not teile:
        return '<p>Für diesen Auftrag sind noch keine Stücklisten oder Beschläge erfasst.</p>'
    if preise:
        teile.append(f'<table class="t" style="margin-top:4mm"><tr class="sum"><td>Material gesamt (EK inkl. Verschnitt, netto)</td><td class="r">{de(gesamt)} €</td></tr></table>')
    return "".join(teile)


def montageauftrag(a, k, erg, opts, hilfe, nur=None):
    h, de = hilfe["h"], hilfe["de"]
    linien = lambda n, spalten: "".join("<tr class='linie'>" + "<td></td>" * spalten + "</tr>" for _ in range(n))
    pos = ""
    if opts.get("bemerkungen", True):
        z = "".join(f'<tr><td class="nw">{h(e["nr"])}</td><td class="r nw">{de_menge(e["p"]["menge"])} {h(e["p"]["einheit"])}</td>'
                    f'<td>{h(kurztext(e["p"]["text"]))}</td></tr>' for e in alle_positionen(erg, nur) if e["ebene"] == 0)
        pos = f'<div class="sek">Positionen</div><table class="t">{z}</table>'
    if not opts.get("handfelder"):
        return (anschrift_block(k, opts, hilfe, "Anschrift") + pos
                + '<div class="sek">Rapport</div><div>Arbeitszeiten, verbautes Material, Anmerkungen und die Unterschrift des Kunden werden digital im '
                  'Rapport erfasst (Auftrag › Werkstatt › Montage, am Tablet oder Handy).</div>' + gefahrstoff_block(hilfe))
    return (anschrift_block(k, opts, hilfe, "Anschrift") + pos
            + '<div class="sek">Verwendetes Material</div><table class="t"><tr><th style="width:15%">Anzahl</th><th style="width:35%">Bezeichnung</th>'
              '<th style="width:15%">Anzahl</th><th>Bezeichnung</th></tr>' + linien(5, 4) + "</table>"
            + '<div class="sek">Geleistete Stunden</div><table class="t"><tr><th style="width:15%">Datum</th><th style="width:15%">Von..Bis</th>'
              '<th style="width:20%">Mitarbeiter</th><th style="width:10%">Stunden</th><th>Beschreibung</th></tr>' + linien(5, 5) + "</table>"
            + '<div class="sek">Anmerkungen zu den geleisteten Arbeiten</div><table class="t">' + linien(4, 1) + "</table>"
            + '<div class="sek">Arbeiten abgeschlossen / Datum und Unterschriften</div>'
              '<table class="t" style="margin-top:8mm"><tr class="linie"><td style="width:18%"></td><td style="width:4%;border:0!important"></td><td style="width:20%"></td>'
              '<td style="width:4%;border:0!important"></td><td></td><td style="width:4%;border:0!important"></td><td></td></tr>'
              '<tr><td class="k">Ja/Nein</td><td></td><td class="k">Datum</td><td></td><td class="k">Unterschrift Auftragnehmer</td><td></td>'
              '<td class="k">Unterschrift Auftraggeber</td></tr></table>')


# ---------------------------------------------------------------- Auswertungen
def _gruppiert(erg, ausgabe, zeile, kopf, summe, hilfe, nur=None):
    """Baut eine Tabelle über alle Hauptpositionen; je nach Ausgabe mit Titel-Zwischensummen oder neuer Seite je Titel."""
    h = hilfe["h"]
    pos = [e for e in alle_positionen(erg, nur) if e["ebene"] == 0]
    if ausgabe == "auftrag" or not any(e["titelname"] for e in pos):
        return f'<table class="t">{kopf}{"".join(zeile(e) for e in pos)}{summe(pos, "Summe Auftrag")}</table>'
    teile, gruppen = [], []
    for e in pos:
        if not gruppen or gruppen[-1][0] != e["titel"]:
            gruppen.append((e["titel"], e["titelname"] or "ohne Titel", []))
        gruppen[-1][2].append(e)
    for i, (_, name, liste) in enumerate(gruppen):
        neu = ' class="neue-seite"' if ausgabe == "seite" and i else ""
        teile.append(f'<div{neu}><h2>{h(name)}</h2><table class="t">{kopf}{"".join(zeile(e) for e in liste)}{summe(liste, "Summe " + name)}</table></div>')
    teile.append(f'<h2>Gesamt</h2><table class="t">{kopf}{summe(pos, "Summe Auftrag")}</table>')
    return "".join(teile)


def auswertung_stunden(a, k, erg, opts, hilfe):
    h, de = hilfe["h"], hilfe["de"]
    reihen = [x["kst"] for x in erg["kalk"].get("kostenstellen", [])]
    benutzt = [r for r in reihen if any((e["p"]["_calc"].get("stunden_kst") or {}).get(r) for e in alle_positionen(erg))]
    benutzt = benutzt or reihen[:6]

    def std(e):
        kst = {}
        for x in [e] + [x for x in alle_positionen(erg) if x["ebene"] == 1 and x["nr"].startswith(e["nr"] + ".")]:
            for kk, v in (x["p"]["_calc"].get("stunden_kst") or {}).items():
                kst[kk] = kst.get(kk, 0) + v * x["faktor"]
        return kst
    kopf = ("<tr><th>Pos.</th><th>Bezeichnung</th>" + "".join(f'<th class="r">{h(x.title())}</th>' for x in benutzt)
            + '<th class="r">Summe</th></tr>')

    def zeile(e):
        s = std(e)
        text = h(kurztext(e["p"]["text"])) + (f'<div class="k">{de_menge(e["p"]["menge"])} {h(e["p"]["einheit"])}</div>')
        return (f'<tr><td>{h(e["nr"])}</td><td>{text}</td>' + "".join(f'<td class="r nw">{de(s.get(x, 0)) if s.get(x) else ""}</td>' for x in benutzt)
                + f'<td class="r nw"><b>{de(sum(s.values()))}</b></td></tr>')

    def summe(liste, label):
        ges = {}
        for e in liste:
            for kk, v in std(e).items():
                ges[kk] = ges.get(kk, 0) + v
        return (f'<tr class="sum"><td></td><td>{h(label)}</td>' + "".join(f'<td class="r nw">{de(ges.get(x, 0))}</td>' for x in benutzt)
                + f'<td class="r nw">{de(sum(ges.values()))} h</td></tr>')
    return '<p class="k">Kalkulierte Stunden (Vorgabezeiten) je Position und Kostenstelle, inkl. Rüst- und Helferzeiten.</p>' + \
        _gruppiert(erg, opts.get("ausgabe", "titel"), zeile, kopf, summe, hilfe)


KOSTEN_SPALTEN = [("material", "Material"), ("gk_material", "GK Mat."), ("lohn", "Lohn"), ("gk_lohn", "GK Lohn"),
                  ("sonder_fertigung", "Sonderk."), ("selbstkosten", "Selbstkosten"), ("wg", "W&G")]


def auswertung_kosten(a, k, erg, opts, hilfe):
    h, de = hilfe["h"], hilfe["de"]

    def werte(e):
        c, m = e["p"]["_calc"], e["faktor"]
        w = {kk: c.get(kk, 0) * m for kk, _ in KOSTEN_SPALTEN}
        for x in [x for x in alle_positionen(erg) if x["ebene"] == 1 and x["nr"].startswith(e["nr"] + ".")]:
            for kk, _ in KOSTEN_SPALTEN:
                w[kk] += x["p"]["_calc"].get(kk, 0) * x["faktor"]
        w["netto"] = c["gesamtpreis"]
        sv = c.get("sonder_vertrieb", 0) * m + sum(x["p"]["_calc"].get("sonder_vertrieb", 0) * x["faktor"]
                                                   for x in alle_positionen(erg) if x["ebene"] == 1 and x["nr"].startswith(e["nr"] + "."))
        w["wg"] = w["netto"] - w["selbstkosten"] - sv   # Sonderkosten Vertrieb sind kein Gewinn
        return w
    kopf = ("<tr><th>Pos.</th><th>Bezeichnung</th>" + "".join(f'<th class="r">{h(l)}</th>' for _, l in KOSTEN_SPALTEN)
            + '<th class="r">Netto</th></tr>')

    def zeile(e):
        w = werte(e)
        return (f'<tr><td>{h(e["nr"])}</td><td>{h(kurztext(e["p"]["text"]))}</td>'
                + "".join(f'<td class="r nw">{de(w[kk])}</td>' for kk, _ in KOSTEN_SPALTEN) + f'<td class="r nw"><b>{de(w["netto"])}</b></td></tr>')

    def summe(liste, label):
        g = {kk: 0.0 for kk, _ in KOSTEN_SPALTEN}
        g["netto"] = 0.0
        for e in liste:
            for kk, v in werte(e).items():
                g[kk] += v
        pz = f' <span class="k">({de(g["wg"] / g["selbstkosten"] * 100, 1)} % W&G)</span>' if g["selbstkosten"] else ""
        return (f'<tr class="sum"><td></td><td>{h(label)}{pz}</td>' + "".join(f'<td class="r nw">{de(g[kk])}</td>' for kk, _ in KOSTEN_SPALTEN)
                + f'<td class="r nw">{de(g["netto"])} €</td></tr>')
    return '<p class="k">Kalkulierte Kosten je Position in Euro (Gesamtmenge der Position). Bedarfs- und Alternativpositionen sind enthalten, sofern sie im Auftrag stehen.</p>' + \
        _gruppiert(erg, opts.get("ausgabe", "titel"), zeile, kopf, summe, hilfe)


SOLLIST_ZEILEN = [("Werkstoffe", "werkstoffe", ""), ("Beschläge", "beschlaege", ""), ("Oberfläche", "oberflaeche", ""),
                  ("Kleinmaterial", "kleinmaterial", ""), ("Fremdleistungen", "fremdleistungen", ""), ("Zukauf (Handelsware)", "zukauf", ""), ("Summe Material", "material", "zw"),
                  ("Gemeinkosten Material", "gk_material", ""), ("Material mit GK", "material_gk", "anteil"),
                  ("Fertigungsstunden", "stunden", "h"), ("Lohnkosten", "lohn", ""), ("Gemeinkosten Lohn", "gk_lohn", ""),
                  ("Lohnkosten mit GK", "lohn_gk", "anteil"), ("Sonderkosten Fertigung", "sonder_fertigung", ""),
                  ("Selbstkosten (100 %)", "selbstkosten", "anteil"), ("Wagnis und Gewinn", "wg", "ertrag"),
                  ("Sonderkosten Vertrieb", "sonder_vertrieb", ""), ("Nettopreis", "nettopreis", "ertrag")]


def sollist_abweichung(kk, art, sv, iv):
    """Abweichung wie im Branchenprogramm: bei Kosten Soll − Ist (mehr gebucht als kalkuliert → negativ),
    bei Wagnis und Gewinn und Nettopreis Ist − Soll (weniger Ertrag → negativ)."""
    return (iv - sv) if art == "ertrag" else (sv - iv)


def auswertung_sollist(a, k, erg, opts, hilfe, si):
    h, de = hilfe["h"], hilfe["de"]
    s, i = si["soll"], si["ist"]

    def anteil(z, kk, art):
        if (art not in ("anteil", "ertrag") and kk not in ("material", "lohn")) or kk == "nettopreis" or not f(z.get("selbstkosten")):
            return ""
        return de(f(z.get(kk)) / f(z["selbstkosten"]) * 100) + " %"

    def zahl(v, einheit=""):
        v = round(f(v), 2)
        return f'<span style="color:#c00">{de(v)}{einheit}</span>' if v < 0 else f"{de(v)}{einheit}"
    def gk_satz(kk):
        """Zuschlagssatz hinter den Gemeinkosten-Zeilen: Soll, bei abweichendem Ist zusätzlich Ist."""
        basis = {"gk_material": "material", "gk_lohn": "lohn"}.get(kk)
        if not basis:
            return ""
        pz = [f(z_.get(kk)) / f(z_.get(basis)) * 100 if f(z_.get(basis)) else None for z_ in (s, i)]
        if pz[0] is None and pz[1] is None:
            return ""
        t = de(pz[0] if pz[0] is not None else pz[1]) + " %"
        if pz[0] is not None and pz[1] is not None and abs(pz[0] - pz[1]) >= 0.005:
            t += f" (Ist {de(pz[1])} %)"
        return f' <span class="k">{t}</span>'
    z = []
    for l, kk, art in SOLLIST_ZEILEN:
        sv, iv = f(s.get(kk)), f(i.get(kk))
        einheit = " h" if art == "h" else ""
        fett = art in ("anteil", "ertrag", "zw")
        z.append(f'<tr{" class=tit" if fett else ""}><td>{l}{gk_satz(kk)}</td><td class="r nw">{zahl(sv, einheit)}</td><td class="r nw">{anteil(s, kk, art)}</td>'
                 f'<td class="r nw">{zahl(iv, einheit)}</td><td class="r nw">{anteil(i, kk, art)}</td>'
                 f'<td class="r nw">{zahl(sollist_abweichung(kk, art, sv, iv), einheit)}</td></tr>')
    kst = si["kostenstellen"]
    zk = "".join(f'<tr><td>{h(x)}</td><td class="r nw">{de((s.get("stunden_kst") or {}).get(x, 0))} h</td><td class="r nw">{de((i.get("stunden_kst") or {}).get(x, 0))} h</td>'
                 f'<td class="r nw">{zahl((s.get("stunden_kst") or {}).get(x, 0) - (i.get("stunden_kst") or {}).get(x, 0), " h")}</td></tr>'
                 for x in kst if (s.get("stunden_kst") or {}).get(x) or (i.get("stunden_kst") or {}).get(x))
    tname = next((f"Titel {t['nr']:02d} {t['name']}" for t in si.get("titel_liste") or [] if t["nr"] == si.get("gewaehlt")), "")
    return (f'<p class="k">{h(tname + " · ") if tname else ""}Soll = Kalkulation, Ist = gebuchte Stunden, Auftragskosten und Lieferantenrechnungen. '
            'Abweichung = Soll − Ist (bei Wagnis und Gewinn und Nettopreis Ist − Soll); negativ heißt: schlechter als kalkuliert.</p>'
            '<table class="t"><tr><th>Kosten</th><th class="r">Soll</th><th class="r">Anteil</th><th class="r">Ist</th><th class="r">Anteil</th><th class="r">Abweichung</th></tr>'
            + "".join(z) + "</table>" + (f'<h2>Stunden je Kostenstelle</h2><table class="t"><tr><th>Kostenstelle</th><th class="r">Soll</th><th class="r">Ist</th><th class="r">Abweichung</th></tr>{zk}</table>' if zk else ""))


def auswertung_lohnmaterial(a, k, erg, opts, hilfe):
    h, de = hilfe["h"], hilfe["de"]
    kalk = erg["kalk"]
    soll = erg["soll"]
    lohnbasis = kalk.get("lohnbasis", "Durchschnitt")
    lohn_h = next((f(x.get("lohn")) for x in kalk.get("loehne", []) if x.get("gruppe") == lohnbasis), 0)
    z = []
    ges_h = ges_l = ges_gk = 0.0
    for x in kalk.get("kostenstellen", []):
        st = (soll.get("stunden_kst") or {}).get(x["kst"], 0)
        if not st:
            continue
        lohn = st * lohn_h
        gk = lohn * f(x.get("gk")) / 100
        ges_h, ges_l, ges_gk = ges_h + st, ges_l + lohn, ges_gk + gk
        z.append(f'<tr><td>{h(x["kst"])}</td><td class="r nw">{de(st)} h</td><td class="r nw">{de(lohn)}</td><td class="r nw">{de(f(x.get("gk")), 0)} %</td>'
                 f'<td class="r nw">{de(gk)}</td><td class="r nw"><b>{de(lohn + gk)}</b></td></tr>')
    lohn_tab = (f'<h2>Lohnkosten je Kostenstelle</h2><p class="k">Gerechnet mit dem Stundenlohn der Lohnbasis „{h(lohnbasis)}“ ({de(lohn_h)} €/h). '
                f'Abweichende Lohngruppen einzelner Tätigkeiten sind in der Auftragskalkulation berücksichtigt (Summe dort: {de(soll.get("lohn", 0))} €).</p>'
                '<table class="t"><tr><th>Kostenstelle</th><th class="r">Stunden</th><th class="r">Lohn</th><th class="r">GK-Satz</th><th class="r">GK</th><th class="r">Summe</th></tr>'
                + "".join(z) + f'<tr class="sum"><td>Summe</td><td class="r">{de(ges_h)} h</td><td class="r">{de(ges_l)}</td><td></td><td class="r">{de(ges_gk)}</td>'
                f'<td class="r">{de(ges_l + ges_gk)} €</td></tr></table>')
    mat = [("Werkstoffe", "werkstoffe"), ("Beschläge", "beschlaege"), ("Oberfläche", "oberflaeche"), ("Kleinmaterial", "kleinmaterial"),
           ("Fremdleistungen", "fremdleistungen"), ("Zukauf (Handelsware)", "zukauf")]
    zm = "".join(f'<tr><td>{l}</td><td class="r nw">{de(soll.get(kk, 0))}</td></tr>' for l, kk in mat)
    mat_tab = (f'<h2>Materialkosten</h2><table class="t"><tr><th>Kategorie</th><th class="r">Betrag</th></tr>{zm}'
               f'<tr><td>Gemeinkosten Material ({de(f(kalk.get("gk_material")), 0)} %)</td><td class="r">{de(soll.get("gk_material", 0))}</td></tr>'
               f'<tr class="sum"><td>Material mit Gemeinkosten</td><td class="r">{de(soll.get("material_gk", 0))} €</td></tr></table>')
    return lohn_tab + mat_tab + materialsummen_html(a, k, erg, {"preise": True}, hilfe)


# ---------------------------------------------------------------- Zeitbericht
def zeitbericht_filter(q, mitarbeiter, h):
    """Bedienleiste (nicht gedruckt): Zeitraum, Mitarbeiter, Reihenfolge, Zusammenfassung – lädt die Seite mit neuen Parametern."""
    ma = "".join(f'<option value="{m["id"]}"{" selected" if str(m["id"]) == q.get("ma", "") else ""}>{h(m["name"])}</option>' for m in mitarbeiter)
    sel = lambda k, v: " selected" if q.get(k, "") == v else ""
    return (f'<form class="zbf" method="get" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-left:14px">'
            f'<label>von <input type="date" name="von" value="{h(q.get("von", ""))}"></label>'
            f'<label>bis <input type="date" name="bis" value="{h(q.get("bis", ""))}"></label>'
            f'<select name="ma"><option value="">alle Mitarbeiter</option>{ma}</select>'
            f'<select name="sort"><option value="ab"{sel("sort", "ab")}>neueste zuerst</option><option value="auf"{sel("sort", "auf")}>älteste zuerst</option></select>'
            f'<select name="summen"><option value="1">mit Zusammenfassung</option><option value="0"{sel("summen", "0")}>ohne Zusammenfassung</option></select>'
            '<button type="submit">Anzeigen</button></form>'
            '<style>.zbf input,.zbf select{font:13px system-ui;padding:2px 4px;border-radius:4px;border:0}.zbf label{display:flex;gap:4px;align-items:center}</style>')


def zeitbericht(zeilen, q, hilfe, mehrere_auftraege=False):
    """Detaillierter Bericht aller gebuchten Zeiten: Datum, Tätigkeit, Auftrag/Titel, Dauer mit Uhrzeit, Mitarbeiter."""
    h, de, ddat = hilfe["h"], hilfe["de"], hilfe["de_datum"]
    ges = sum(f(z["stunden"]) for z in zeilen)
    zr = (f'{ddat(q["von"]) if q.get("von") else "Beginn"} – {ddat(q["bis"]) if q.get("bis") else "heute"}'
          if q.get("von") or q.get("bis") else "gesamter Zeitraum")
    if zeilen:
        dmin, dmax = min(z["datum"] for z in zeilen), max(z["datum"] for z in zeilen)
        zr += f" · gebucht {ddat(dmin)}" + (f" bis {ddat(dmax)}" if dmax != dmin else "")
    kopf = (f'<div style="display:flex;gap:30px;align-items:baseline;margin:2mm 0 4mm"><div class="k">Zeitraum: {h(zr)}'
            + (f'<br>Mitarbeiter: {h(zeilen[0]["mitarbeiter"])}' if q.get("ma") and zeilen else "")
            + f'</div><div style="font-size:13pt">Gesamt: <b>{de(ges)} h</b></div></div>')
    if not zeilen:
        return kopf + '<p>Keine gebuchten Zeiten im gewählten Zeitraum.</p>'
    z = []
    for r in zeilen:
        unter = " · ".join(x for x in [
            f'{r["auftragsnr"]} {r["auftrag"]}' if mehrere_auftraege else "",
            f'Titel {r["titel"]}' if r.get("titel") else "",
            (r.get("kst") or "").title() if r.get("kst") and r.get("taetigkeit") and (r.get("kst") or "").lower() != (r.get("taetigkeit") or "").lower() else "",
            r.get("notiz") or ""] if x)
        uhr = f'{r["beginn"][:5]} – {r["ende"][:5]}' if r.get("beginn") and r.get("ende") else ""
        z.append(f'<tr><td class="nw">{ddat(r["datum"])}</td><td><b>{h(r["taetigkeit"] or (r.get("kst") or "").title() or "Arbeitszeit")}</b>'
                 f'{f"<div class=k>{h(unter)}</div>" if unter else ""}</td>'
                 f'<td class="r nw"><b>{de(r["stunden"])}</b>{f"<div class=k>{h(uhr)}</div>" if uhr else ""}</td>'
                 f'<td>{h(r["mitarbeiter"])}</td></tr>')
    html = (kopf + '<table class="t"><tr><th style="width:15%">Datum</th><th>Beschreibung</th><th class="r" style="width:18%">Dauer (h)</th>'
            '<th style="width:20%">Mitarbeiter</th></tr>' + "".join(z)
            + f'<tr class="sum"><td></td><td>Gesamt</td><td class="r nw">{de(ges)} h</td><td></td></tr></table>')
    if q.get("summen", "1") != "0":
        def summe(titel, schluessel):
            s = {}
            for r in zeilen:
                k = schluessel(r)
                s[k] = s.get(k, 0) + f(r["stunden"])
            if len(s) < 2 and titel != "Tätigkeit":
                return ""
            zz = "".join(f'<tr><td>{h(k)}</td><td class="r nw">{de(v)} h</td><td class="r nw">{de(v / ges * 100 if ges else 0, 0)} %</td></tr>'
                         for k, v in sorted(s.items(), key=lambda x: -x[1]))
            return (f'<div style="break-inside:avoid"><h2>Je {titel}</h2><table class="t" style="width:70%"><tr><th>{titel}</th><th class="r">Stunden</th>'
                    f'<th class="r">Anteil</th></tr>{zz}</table></div>')
        html += summe("Tätigkeit", lambda r: r["taetigkeit"] or (r.get("kst") or "").title() or "Arbeitszeit")
        html += summe("Mitarbeiter", lambda r: r["mitarbeiter"])
        if mehrere_auftraege:
            html += summe("Auftrag", lambda r: f'{r["auftragsnr"]} {r["auftrag"]}')
        html += summe("Titel", lambda r: f'Titel {r["titel"]}' if r.get("titel") else "ohne Titel")
    return html
