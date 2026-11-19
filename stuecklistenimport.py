"""Stücklisten-Import im üblichen CSV-Stücklistenformat (22 Felder), wahlweise mit zusätzlichem Feld 2
„Werkstoffbezeichnung“ (23 Felder). Unbekannte Werkstoffe werden im Materialstamm mit fortlaufender Nummer angelegt.

Teilezeile (Standard):  1 Werkstoffnr; 2 Verwendung; 3 Anzahl; 4 Länge; 5 Breite; 6-9 Kante links/rechts/oben/unten; 10 Kantenverlauf;
                  11/12 Furnier oben/unten; 13/14 Oberfläche oben/unten; 15 Bemerkung; 16-19 Fräsen l/r/o/u; 20/21 Verbinden o/u; 22 Bohren;
                  23 Taschen/Ausschnitte fräsen (optional, Erweiterung von Jahresring): „Anzahl“ oder „Anzahl x Länge x Breite [x Tiefe]“ in mm
Beschlagzeile:    1 Beschlagnr; 2 Verwendung/Bemerkung; 3 Anzahl (keine Maße)
Positionszeile:   1 leer; 2 Bezeichnung; 3 Anzahl; 4 Höhe; 5 Breite; 6 Tiefe
Erweitert:        nach Feld 1 steht bei Teile- und Beschlagzeilen zusätzlich die Werkstoff-/Beschlagbezeichnung.
"""
import re

import material

ROLLEN = {"platte": "Werkstoff", "kante": "Kante", "furnier": "Furnier/Schichtstoff", "oberflaeche": "Oberfläche", "beschlag": "Beschlag"}
# neue Materialien: Kategorie, Gruppe, Auftrags-Werkstofftyp
NEU_VORGABE = {"platte": ("holzwerkstoffe", "Platten"), "kante": ("holzwerkstoffe", "Kanten"), "furnier": ("holzwerkstoffe", "Furnier"),
               "oberflaeche": ("beschichtung", "Lack"), "beschlag": ("beschlaege", "Sonstiges")}
TYP_PRAEFIX = {"platte": "P", "massiv": "M", "kante": "K", "furnier": "F", "oberflaeche": "O", "sonstig": "S"}
TYP_EINHEIT = {"platte": "m²", "massiv": "m³", "kante": "lfm", "furnier": "m²", "oberflaeche": "m²", "sonstig": "Stk."}


class Fehler(Exception):
    pass


def zahl(s):
    s = (s or "").strip()
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def dicke_raten(*texte):
    for t in texte:
        m = re.search(r"(\d{1,2}(?:[.,]\d)?)\s*mm", t or "")
        if m:
            return zahl(m.group(1))
    for t in texte:
        m = re.search(r"(?<![\d,.])(\d{1,2}(?:[.,]\d)?)$", (t or "").strip())
        if m and 2 <= zahl(m.group(1)) <= 60:
            return zahl(m.group(1))
    return 0.0


def tasche_lesen(feld):
    """Feld „Taschen“: „2“ oder „2x560x490“ bzw. „2x560x490x12“ (Anzahl × Länge × Breite [× Tiefe] in mm; x, X, × oder *)."""
    teile = [x for x in re.split(r"\s*[xX×*]\s*", (feld or "").strip()) if x != ""]
    if not teile or not re.fullmatch(r"\d+", teile[0]):
        return {"taschen": 0}
    erg = {"taschen": int(teile[0])}
    for k, w in zip(("tasche_l", "tasche_b", "tasche_t"), teile[1:4]):
        if zahl(w):
            erg[k] = zahl(w)
    return erg


def zahl_lesen(s, stil=None):
    """Liest eine Zahl der Stückliste streng → (Wert, Zustand). Zustand: "" (Feld leer), "ok", "mehrdeutig" (1.250 ohne
    weiteren Anhalt als 1250 gelesen) oder "unlesbar". stil: "komma" (die Datei schreibt Dezimalkommas, der Punkt trennt Tausender),
    "punkt" (die Datei schreibt Dezimalpunkte) oder None (kein Anhalt)."""
    s = (s or "").strip().replace(" ", "").replace(" ", "")
    if not s:
        return 0.0, ""
    if re.fullmatch(r"-?\d+", s):
        return float(s), "ok"
    if re.fullmatch(r"-?(\d{1,3}(\.\d{3})+|\d+),\d+", s):
        return float(s.replace(".", "").replace(",", ".")), "ok"
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        if stil == "punkt":
            return float(s), "ok"
        return float(s.replace(".", "")), "ok" if stil == "komma" else "mehrdeutig"
    if re.fullmatch(r"-?\d+\.\d+", s) and stil != "komma":
        return float(s), "ok"
    return 0.0, "unlesbar"


def zahlen_stil(felder):
    """Schreibweise der Zahlen in den Maß- und Mengenfeldern einer Datei: "komma", "punkt" oder None."""
    komma = punkt = False
    for f in felder:
        for x in f[1:7]:
            x = (x or "").strip()
            if re.fullmatch(r"-?[\d.]+,\d+", x):
                komma = True
            elif re.fullmatch(r"-?\d+\.\d+", x) and not re.fullmatch(r"-?\d{1,3}(\.\d{3})+", x):
                punkt = True
    return "komma" if komma else ("punkt" if punkt else None)


def zeilen_lesen(text, erweitert=None):
    """→ (position, teile, beschlaege, erweitert, hinweise). Was sich nicht eindeutig lesen lässt, wird nicht umgedeutet, sondern
    ausgelassen und in hinweise gemeldet: [{zeile, art: "fehler" (Zeile ausgelassen) | "hinweis" (gelesen, bitte prüfen), text}]."""
    roh = [(nr, z) for nr, z in enumerate((text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1) if z.strip()]
    felder = [[f.strip() for f in z.split(";")] for _, z in roh]
    if erweitert is None:
        # Standard: Feld 3 = Anzahl (Zahl). Erweitert: Feld 3 = Verwendung (Text), Feld 4 = Anzahl
        ist_zahl = lambda x: bool(re.fullmatch(r"-?[\d.]+(,\d+)?", (x or "").strip()))  # noqa: E731
        std = erw = 0
        for f in felder:
            if not f or not f[0] or len(f) < 4:
                continue
            if ist_zahl(f[2]):
                std += 1
            elif ist_zahl(f[3]):
                erw += 1
        erweitert = erw > std
    stil = zahlen_stil(felder)
    position, teile, beschlaege, hinweise = None, [], [], []

    def melde(nr, text_, art="fehler"):
        hinweise.append({"zeile": nr, "art": art, "text": text_})

    for i, f in enumerate(felder):
        nr_zeile = roh[i][0]
        n_felder = len(f)
        f = f + [""] * (26 - len(f))
        if not f[0]:
            if i == 0 and f[1]:
                werte = {}
                for name, feld, x in (("Anzahl", "menge", f[2]), ("Höhe", "h", f[3]), ("Breite", "b", f[4]), ("Tiefe", "t", f[5])):
                    w, zustand = zahl_lesen(x, stil)
                    if zustand == "unlesbar" or w < 0:
                        melde(nr_zeile, f"{name} der Position „{x}“ ist keine brauchbare Zahl und wird nicht übernommen.", "hinweis")
                        w = 0.0
                    elif zustand == "mehrdeutig":
                        melde(nr_zeile, f"{name} der Position „{x}“ wurde als {w:.0f} gelesen (Punkt als Tausenderzeichen).", "hinweis")
                    werte[feld] = w
                position = {"text": f[1], "menge": werte["menge"] or 1, "h": werte["h"], "b": werte["b"], "t": werte["t"]}
            elif f[1] and any(x.strip() for x in f[2:6]):
                melde(nr_zeile, f"weitere Positionszeile „{f[1][:40]}“: Alle Teile dieser Daten kommen in die eine, geöffnete Position.", "hinweis")
            continue
        nr = f[0]
        bez = f[1] if erweitert else ""
        g = f[2:] if erweitert else f[1:]   # g[0] = Verwendung, g[1] = Anzahl, g[2] = Länge …
        was = f"„{nr}“" + (f" ({g[0][:30]})" if g[0] else "")
        if n_felder < (4 if erweitert else 3):
            melde(nr_zeile, f"{was}: zu wenige Felder, die Anzahl fehlt. Zeile nicht übernommen.")
            continue
        anzahl, z_a = zahl_lesen(g[1], stil)
        laenge, z_l = zahl_lesen(g[2], stil)
        breite, z_b = zahl_lesen(g[3], stil)
        unlesbar = [f"{n} „{x}“" for n, x, z in (("Anzahl", g[1], z_a), ("Länge", g[2], z_l), ("Breite", g[3], z_b)) if z == "unlesbar"]
        if unlesbar:
            melde(nr_zeile, f"{was}: {' und '.join(unlesbar)} {'ist keine Zahl' if len(unlesbar) == 1 else 'sind keine Zahlen'}. Zeile nicht übernommen.")
            continue
        if anzahl < 0 or laenge < 0 or breite < 0:
            melde(nr_zeile, f"{was}: negative Anzahl oder negatives Maß. Zeile nicht übernommen.")
            continue
        if z_a and not anzahl:
            melde(nr_zeile, f"{was}: Anzahl 0. Zeile nicht übernommen.")
            continue
        if not z_a:
            melde(nr_zeile, f"{was}: Anzahl fehlt, 1 angenommen.", "hinweis")
            anzahl = 1.0
        if bool(laenge) != bool(breite):
            melde(nr_zeile, f"{was}: {'Breite' if laenge else 'Länge'} fehlt. Ein Teil braucht Länge und Breite, ein Beschlag keines von beiden. Zeile nicht übernommen.")
            continue
        for n, x, w, z in (("Anzahl", g[1], anzahl, z_a), ("Länge", g[2], laenge, z_l), ("Breite", g[3], breite, z_b)):
            if z == "mehrdeutig":
                melde(nr_zeile, f"{was}: {n} „{x}“ wurde als {w:.0f} gelesen (Punkt als Tausenderzeichen). Bitte prüfen.", "hinweis")
        if not laenge:
            beschlaege.append({"nr": nr, "bez": bez, "verwendung": g[0], "menge": anzahl})
            continue
        if anzahl != int(anzahl):
            melde(nr_zeile, f"{was}: Stückzahl „{g[1]}“ ist keine ganze Zahl. Zeile nicht übernommen.")
            continue
        kanten = {"links": g[4], "rechts": g[5], "oben": g[6], "unten": g[7]}
        teile.append({"nr": nr, "bez": bez, "verwendung": g[0][:40], "stueck": int(anzahl), "laenge": laenge, "breite": breite,
                      "kanten": kanten, "verlauf": g[8].upper()[:1], "furnier": {"oben": g[9], "unten": g[10]},
                      "oberflaeche": {"oben": g[11], "unten": g[12]}, "bemerkung": g[13],
                      "fraesen": {s: 1 if g[14 + j] == "1" else 0 for j, s in enumerate(("links", "rechts", "oben", "unten"))},
                      "verbinden": {"oben": 1 if g[18] == "1" else 0, "unten": 1 if g[19] == "1" else 0},
                      "bohren": int(zahl(g[20])) if g[20].strip().isdigit() else 0,
                      **tasche_lesen(g[21])})
    return position, teile, beschlaege, erweitert, hinweise


def schon_enthalten(con, kalk, pos, teile, beschlaege):
    """Wie viele der gelesenen Teile und Beschläge stehen schon in der Position? Teile gelten als gleich bei gleicher Verwendung,
    Stückzahl, Länge und Breite; Beschläge bei gleichem Material und gleicher Menge. → (teile_doppelt, beschlaege_doppelt)"""
    def f(x):
        try:
            return round(float(x or 0), 1)
        except (TypeError, ValueError):
            return 0.0
    vorh = {}
    for t in (pos or {}).get("stueckliste") or []:
        k = (str(t.get("verwendung") or "")[:40], f(t.get("stueck")), f(t.get("laenge")), f(t.get("breite")))
        vorh[k] = vorh.get(k, 0) + 1
    n_t = 0
    for t in teile:
        k = (t["verwendung"], f(t["stueck"]), f(t["laenge"]), f(t["breite"]))
        if vorh.get(k, 0) > 0:
            vorh[k] -= 1
            n_t += 1
    kuerzel = {}   # Materialnummer → Kürzel in den Auftragswerten
    for b in (kalk or {}).get("beschlaege") or []:
        for nr in (b.get("artnr"), b.get("matnr")):
            if nr:
                kuerzel[nr] = b.get("k")
    vorh_b = {}
    for b in (pos or {}).get("beschlaege") or []:
        k = (b.get("k"), f(b.get("menge")))
        vorh_b[k] = vorh_b.get(k, 0) + 1
    n_b = 0
    for b in beschlaege:
        m = material_suchen(con, b["nr"], b["bez"], ROLLE_KATS["beschlag"])
        k = (kuerzel.get(m["nummer"]) if m else None, f(b["menge"]))
        if k[0] and vorh_b.get(k, 0) > 0:
            vorh_b[k] -= 1
            n_b += 1
    return n_t, n_b


def material_suchen(con, code, bez, kats):
    """Treffer im Materialstamm: CAD-Kürzel, Nummer, Bestellnummer, dann exakte Bezeichnung."""
    platz = ",".join("?" * len(kats))
    for feld in ("cad", "nummer", "bestellnr"):
        r = con.execute(f"SELECT * FROM material WHERE lower({feld})=lower(?) AND kategorie IN ({platz}) ORDER BY aktiv DESC LIMIT 1",
                        [code] + list(kats)).fetchone()
        if r:
            return dict(r)
    if bez:
        r = con.execute(f"SELECT * FROM material WHERE lower(bezeichnung)=lower(?) AND kategorie IN ({platz}) ORDER BY aktiv DESC LIMIT 1",
                        [bez] + list(kats)).fetchone()
        if r:
            return dict(r)
    return None


ROLLE_KATS = {"platte": ("holzwerkstoffe", "massivholz", "artikel"), "kante": ("holzwerkstoffe",), "furnier": ("holzwerkstoffe",),
              "oberflaeche": ("beschichtung", "chemie"), "beschlag": ("beschlaege", "artikel", "chemie")}


def benoetigte_materialien(teile, beschlaege):
    """{(rolle, code): {bez, anzahl}} – „G“ an der Kante bedeutet Gehrung, kein Werkstoff."""
    bedarf = {}

    def merke(rolle, code, bez="", n=1):
        code = (code or "").strip()
        if not code or (rolle == "kante" and code.upper() == "G"):
            return
        e = bedarf.setdefault((rolle, code), {"bez": "", "anzahl": 0})
        e["bez"] = e["bez"] or bez
        e["anzahl"] += n
    for t in teile:
        merke("platte", t["nr"], t["bez"], t["stueck"])
        for s in ("links", "rechts", "oben", "unten"):
            merke("kante", t["kanten"][s], "", t["stueck"])
        for s in ("oben", "unten"):
            merke("furnier", t["furnier"][s], "", t["stueck"])
            merke("oberflaeche", t["oberflaeche"][s], "", t["stueck"])
    for b in beschlaege:
        merke("beschlag", b["nr"], b["bez"], b["menge"])
    return bedarf


def hinweis_text(hinweise, hoechstens=3):
    return " ".join(f"Zeile {h['zeile']}: {h['text']}" for h in hinweise[:hoechstens])


def vorschau(con, text, erweitert=None, kalk=None, pos=None):
    position, teile, beschlaege, erw, hinweise = zeilen_lesen(text, erweitert)
    if not teile and not beschlaege:
        fehler = [h for h in hinweise if h["art"] == "fehler"]
        raise Fehler("In den Daten wurden keine Teile oder Beschläge gefunden. Erwartet wird das CSV-Stücklistenformat mit 22 Feldern "
                     "(Semikolon getrennt, eine Zeile je Teil)." + (" " + hinweis_text(fehler) if fehler else ""))
    doppelt_t, doppelt_b = schon_enthalten(con, kalk, pos, teile, beschlaege)
    mats = []
    naechste = {}
    for (rolle, code), e in sorted(benoetigte_materialien(teile, beschlaege).items(), key=lambda x: (list(ROLLEN).index(x[0][0]), x[0][1])):
        treffer = material_suchen(con, code, e["bez"], ROLLE_KATS[rolle])
        kat, gruppe = NEU_VORGABE[rolle]
        if kat not in naechste:
            naechste[kat] = material.naechste_nummer(con, kat)
        mats.append({"rolle": rolle, "rolle_name": ROLLEN[rolle], "code": code, "bez": e["bez"], "anzahl": e["anzahl"],
                     "treffer": {k: treffer[k] for k in ("id", "nummer", "bezeichnung", "kategorie", "gruppe", "dicke", "ek_preis", "einheit")}
                     if treffer else None,
                     "neu": {"kategorie": kat, "gruppe": gruppe, "bezeichnung": e["bez"] or code,
                             "dicke": dicke_raten(e["bez"], code) if rolle == "platte" else (dicke_raten(code) if rolle == "kante" else 0)}})
    return {"position": position, "teile": len(teile), "beschlaege": len(beschlaege), "erweitert": erw, "materialien": mats,
            "hinweise": hinweise, "ausgelassen": sum(1 for h in hinweise if h["art"] == "fehler"),
            "doppelt": {"teile": doppelt_t, "beschlaege": doppelt_b, "alles": doppelt_t == len(teile) and doppelt_b == len(beschlaege)},
            "beispiele": [{"nr": t["nr"], "verwendung": t["verwendung"], "stueck": t["stueck"], "laenge": t["laenge"], "breite": t["breite"]}
                          for t in teile[:6]],
            "naechste": naechste, "kategorien": material.KATEGORIEN, "gruppen": material.STANDARD_GRUPPEN}


def auftrags_werkstoff(kalk, m, rolle):
    """Sucht/erzeugt in den Auftragswerten den Eintrag zum Stamm-Material, liefert dessen Kürzel (P01, K02 …)."""
    if rolle == "beschlag":
        for b in kalk.setdefault("beschlaege", []):
            if b.get("artnr") == m["nummer"] or b.get("matnr") == m["nummer"]:
                return b["k"]
        for b in kalk["beschlaege"]:  # leere Zeile wiederverwenden
            if not (b.get("artnr") or b.get("name") or b.get("preis")):
                ziel = b
                break
        else:
            ziel = {"k": "B" + str(max([int(b["k"][1:]) for b in kalk["beschlaege"] if b.get("k", "B")[1:].isdigit()] + [0]) + 1).zfill(2)}
            kalk["beschlaege"].append(ziel)
        ziel.update({"artnr": m["nummer"], "matnr": m["nummer"], "name": (m["bezeichnung"] or "").split("\n")[0], "einheit": m["einheit"] or "Stk.",
                     "preis": (m.get("kalkpreis") if m.get("kalkpreis") is not None else m["ek_preis"]) or 0, "v": 0, "stamm_preis": (m.get("kalkpreis") if m.get("kalkpreis") is not None else m["ek_preis"]) or 0, "stamm_v": 0,
                     "lieferant": m.get("lieferant") or "", "bestellnr": m.get("bestellnr") or "", "preis_vom": m.get("preis_vom") or ""})
        return ziel["k"]
    typ = material.kalk_typ(m) if rolle == "platte" else {"kante": "kante", "furnier": "furnier", "oberflaeche": "oberflaeche"}[rolle]
    wks = kalk.setdefault("werkstoffe", [])
    for w in wks:
        if w.get("matnr") == m["nummer"] and w.get("typ") == typ:
            return w["k"]
    ziel = next((w for w in wks if w.get("typ") == typ and not (w.get("name") or w.get("preis") or w.get("matnr"))), None)
    if not ziel:
        p = TYP_PRAEFIX[typ]
        nrn = [int(w["k"][1:]) for w in wks if w.get("k", "").startswith(p) and w["k"][1:].isdigit()]
        ziel = {"k": f"{p}{max(nrn + [0]) + 1:02d}", "typ": typ}
        wks.append(ziel)
    einheit = {"lfm.": "lfm", "Liter": "l"}.get(m["einheit"], m["einheit"]) or TYP_EINHEIT[typ]
    ziel.update({"name": (m["bezeichnung"] or "").split("\n")[0], "preis": (m.get("kalkpreis") if m.get("kalkpreis") is not None else m["ek_preis"]) or 0, "v": m.get("verschnitt") or 0,
                 "stamm_preis": (m.get("kalkpreis") if m.get("kalkpreis") is not None else m["ek_preis"]) or 0, "stamm_v": m.get("verschnitt") or 0, "einheit": einheit, "um": m.get("umrechnung") or 0, "matnr": m["nummer"], "lieferant": m.get("lieferant") or "", "bestellnr": m.get("bestellnr") or "",
                 "preis_vom": m.get("preis_vom") or ""})
    if m.get("dicke"):
        ziel["dicke"] = m["dicke"]
    return ziel["k"]


def importieren(con, kalk, pos, text, zuordnung, erweitert=None, ersetzen=False):
    """zuordnung: {"rolle|code": {"material_id": n} | {"neu": {kategorie, gruppe, bezeichnung, dicke}} | {"weglassen": True}}
    → (stueckliste, beschlaege, position, angelegt[])"""
    position, teile, beschlaege, _, _hinweise = zeilen_lesen(text, erweitert)
    bedarf = benoetigte_materialien(teile, beschlaege)
    codes = {}   # (rolle, code) → Kürzel in den Auftragswerten
    angelegt = []
    for (rolle, code), e in bedarf.items():
        z = (zuordnung or {}).get(f"{rolle}|{code}") or {}
        if z.get("weglassen"):
            continue
        m = None
        if z.get("material_id"):
            m = material.laden(con, int(z["material_id"]))
        elif z.get("neu") is not None or not z:
            vorh = material_suchen(con, code, e["bez"], ROLLE_KATS[rolle]) if not z else None
            if vorh:
                m = material.laden(con, vorh["id"])
            else:
                neu = z.get("neu") or {}
                kat = neu.get("kategorie") or NEU_VORGABE[rolle][0]
                d = {"kategorie": kat, "gruppe": neu.get("gruppe") or NEU_VORGABE[rolle][1],
                     "bezeichnung": (neu.get("bezeichnung") or e["bez"] or code).strip(), "dicke": zahl(str(neu.get("dicke") or 0)),
                     "cad": code, "bemerkungen": f"Automatisch angelegt beim Stücklisten-Import (CAD-Kürzel {code})"}
                if kat == "holzwerkstoffe" and d["gruppe"] == "Kanten":
                    d["einheit"] = "lfm."
                m = material.anlegen(con, d)
                angelegt.append(f"{m['nummer']} {m['bezeichnung']}")
        if m:
            if not (m.get("cad") or "").strip():
                con.execute("UPDATE material SET cad=? WHERE id=?", (code, m["id"]))  # Zuordnung für das nächste Mal merken
            codes[(rolle, code)] = auftrags_werkstoff(kalk, m, rolle)
    k = lambda rolle, code: codes.get((rolle, (code or "").strip()), "")  # noqa: E731
    neu_teile = []
    for t in teile:
        bem = [t["bemerkung"]] if t["bemerkung"] else []
        gehrung = [s for s in ("links", "rechts", "oben", "unten") if (t["kanten"][s] or "").upper() == "G"]
        if gehrung:
            bem.append("Gehrung " + "/".join(gehrung))
        if t["verlauf"] in ("L", "Q", "G"):
            bem.append({"L": "Kanten längs durchgehend", "Q": "Kanten quer durchgehend", "G": "Kanten auf Gehrung"}[t["verlauf"]])
        neu_teile.append({"werkstoff": k("platte", t["nr"]), "verwendung": t["verwendung"], "stueck": t["stueck"], "laenge": t["laenge"],
                          "breite": t["breite"], "kanten": {s: k("kante", v) for s, v in t["kanten"].items() if k("kante", v)},
                          "furnier": {s: k("furnier", v) for s, v in t["furnier"].items() if k("furnier", v)},
                          "oberflaeche": {s: k("oberflaeche", v) for s, v in t["oberflaeche"].items() if k("oberflaeche", v)},
                          "fraesen": {s: v for s, v in t["fraesen"].items() if v}, "verbinden": {s: v for s, v in t["verbinden"].items() if v},
                          "bohren": t["bohren"], "taschen": t["taschen"], **{k: t[k] for k in ("tasche_l", "tasche_b", "tasche_t") if t.get(k)},
                          "gehrung": len(gehrung), "bemerkung": "; ".join(bem)})
    neu_bs = [{"k": k("beschlag", b["nr"]), "menge": b["menge"], "bemerkung": b["verwendung"]} for b in beschlaege if k("beschlag", b["nr"])]
    stueck = neu_teile if ersetzen else (pos.get("stueckliste") or []) + neu_teile
    bs = neu_bs if ersetzen else (pos.get("beschlaege") or []) + neu_bs
    return stueck, bs, position, angelegt, len(neu_teile), len(neu_bs)
