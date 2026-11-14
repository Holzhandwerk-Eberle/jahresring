# -*- coding: utf-8 -*-
"""
Positionskalkulation für Jahresring.
Alle Beträge je Anzahl (= je Stück der Position), sofern nicht anders benannt.
"""
import copy

LOHNGRUPPEN = ["Meister", "Geselle", "Lehrling", "Hilfskraft", "Inhaber", "Durchschnitt"]

# Bezugsgrößen, die aus der Stückliste berechnet werden
# Bezugsgrößen wie im Branchenprogramm (Reihenfolge = Auswahlliste). „Platte“ = Teile aus Plattenwerkstoff,
# „Massiv“ = Teile aus Massivholz. Ältere Schlüssel (platte, platte2, kante, furnier, …) bleiben erhalten.
BEZUG = {
    "": ("---", ""),
    "platte_st": ("Platte - St.", "St."),
    "platte_lfm": ("Platte - lfm.", "lfm"),
    "platte_kanten": ("Platte - lfm. Kanten", "lfm"),
    "platte": ("Platte - m²", "m²"),
    "platte2": ("Platte - m² 2x", "m²"),
    "massiv_st": ("Massiv - St.", "St."),
    "massiv_lfm": ("Massiv - lfm.", "lfm"),
    "massiv_lfm2": ("Massiv - lfm. 2x", "lfm"),
    "massiv_kanten": ("Massiv - lfm. Kanten", "lfm"),
    "massiv": ("Massiv - m²", "m²"),
    "massiv2": ("Massiv - m² 2x", "m²"),
    "kante_st": ("Kante - St.", "St."),
    "kante": ("Kante - lfm.", "lfm"),
    "furnier_st": ("Furnier - St.", "St."),
    "furnier": ("Furnier - m²", "m²"),
    "oberflaeche_st": ("Oberfläche - St.", "St."),
    "oberflaeche": ("Oberfläche - m²", "m²"),
    "gehrung": ("Gehrung - St.", "St."),
    "fraesen": ("Fräsen - lfm.", "lfm"),
    "verbinden": ("Verbinden - St.", "St."),
    "bohren": ("Bohren - St.", "St."),
    "tasche": ("Tasche/Ausschnitt fräsen - St.", "St."),
    "tasche_lfm": ("Tasche/Ausschnitt fräsen - lfm. (Umfang)", "lfm"),
    "tasche_m2": ("Tasche/Ausschnitt fräsen - m² (Fläche)", "m²"),
    "zuschnitt": ("Schnittkanten - lfm.", "lfm"),
    "teile": ("Teile - St.", "St."),
    "beschlaege": ("Beschläge - St.", "St."),
}
LAGEN = ("oben", "unten", "vorn", "hinten", "mitte")   # Lage beim Verbinden/Bohren (nur Info für die Werkstatt)


def bezug_alle(eigene=None):
    """Alle Bezugsgrößen: fest eingebaute plus selbst festgelegte (Einstellungen › Tätigkeiten), Schlüssel „x_<k>“."""
    alle = {k: list(v) for k, v in BEZUG.items()}
    for b in eigene or []:
        if b.get("k") and b.get("name"):
            alle["x_" + str(b["k"])] = [b["name"], b.get("einheit") or "", b.get("quelle") or "teil"]
    return alle


def anzahl_verbinden(t):
    vb = t.get("verbinden") or {}
    if f(vb.get("anzahl")):
        return f(vb.get("anzahl"))
    return sum(1 for s in ("oben", "unten") if vb.get(s))   # ältere Stücklisten: je angehakter Seite 1

WERKSTOFF_TYPEN = {  # Kürzel-Präfix, Bezeichnung, Standardeinheit
    "platte": ("P", "Platten", "m²"),
    "massiv": ("M", "Massivholz", "m³"),
    "kante": ("K", "Kanten", "lfm"),
    "furnier": ("F", "Furnier", "m²"),
    "oberflaeche": ("O", "Oberfläche", "m²"),
    "sonstig": ("S", "Sonstiges", "Stk."),
}


def _leer_werkstoffe():
    zeilen = []
    for typ, (prae, _, einheit) in WERKSTOFF_TYPEN.items():
        anzahl = 4 if typ == "platte" else 2
        for i in range(1, anzahl + 1):
            zeilen.append({"k": f"{prae}{i:02d}", "typ": typ, "name": "", "einheit": einheit,
                           "dicke": 0, "v": 0, "preis": 0})
    return zeilen


KALK_VORGABEN = {
    "loehne": [{"gruppe": g, "lohn": 27.0 if g in ("Inhaber", "Durchschnitt") else 0.0, "lnk": 90.0}
               for g in LOHNGRUPPEN],
    "kostenstellen": [
        {"kst": "AVORBER", "gk": 110}, {"kst": "ZUSCHNIT", "gk": 140}, {"kst": "KANTENMA", "gk": 180},
        {"kst": "SONST-MA", "gk": 140}, {"kst": "BANKRAUM", "gk": 140}, {"kst": "OBERFLÄ", "gk": 160},
        {"kst": "MONTAGE", "gk": 130}, {"kst": "REPARAT", "gk": 140}, {"kst": "FAHRZEIT", "gk": 110},
        {"kst": "HELFER", "gk": 110},
    ],
    "lohnbasis": "Durchschnitt",
    "gk_material": 30.0,
    "kleinmaterial": 15.0,
    "wg": 15.0,
    "helfer_gruppe": "Hilfskraft",
    "helfer_kst": "HELFER",
    "werkstoffe": [],   # je Auftrag aus dem Materialstamm oder dem Stücklistenimport (keine Vorgabe in den Einstellungen)
    "beschlaege": [],
}

TAETIGKEITEN_VORGABE = [
    {"kst": "AVORBER", "name": "Fertigungsunterlagen", "minuten": 60, "bezug": "", "ruest": 0, "helfer": 0},
    {"kst": "ZUSCHNIT", "name": "Grobzuschnitt Platte", "minuten": 6, "bezug": "platte", "ruest": 0, "helfer": 0.2},
    {"kst": "ZUSCHNIT", "name": "Formatsägen", "minuten": 2, "bezug": "zuschnitt", "ruest": 0, "helfer": 0.2},
    {"kst": "KANTENMA", "name": "Kante anleimen masch.", "minuten": 3, "bezug": "kante", "ruest": 10, "helfer": 1},
    {"kst": "SONST-MA", "name": "Kante bündig fräsen", "minuten": 1, "bezug": "kante", "ruest": 5, "helfer": 0},
    {"kst": "SONST-MA", "name": "Furnier richten masch.", "minuten": 20, "bezug": "furnier", "ruest": 5, "helfer": 0},
    {"kst": "SONST-MA", "name": "Kalibrieren Platte", "minuten": 4, "bezug": "platte2", "ruest": 5, "helfer": 1},
    {"kst": "SONST-MA", "name": "Furnierpresse", "minuten": 12, "bezug": "furnier", "ruest": 5, "helfer": 1},
    {"kst": "SONST-MA", "name": "Fräsen-Fälzen-Nuten", "minuten": 4, "bezug": "fraesen", "ruest": 10, "helfer": 0},
    {"kst": "SONST-MA", "name": "Dübel/Lamello Verbindung", "minuten": 5, "bezug": "verbinden", "ruest": 5, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Kante schleifen v. Hand", "minuten": 3.5, "bezug": "kante", "ruest": 0, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Schleifen Lack", "minuten": 8, "bezug": "oberflaeche", "ruest": 2, "helfer": 0},
    {"kst": "OBERFLÄ", "name": "Lackieren 2x + Schleifen", "minuten": 30, "bezug": "oberflaeche", "ruest": 20, "helfer": 0.2},
    {"kst": "BANKRAUM", "name": "Verleimen", "minuten": 5, "bezug": "verbinden", "ruest": 5, "helfer": 0.5},
    {"kst": "BANKRAUM", "name": "Handling", "minuten": 10, "bezug": "platte", "ruest": 0, "helfer": 0},
    {"kst": "MONTAGE", "name": "Montage", "minuten": 120, "bezug": "", "ruest": 0, "helfer": 0},
]

# Tätigkeitskatalog (Einstellungen › Kalkulation › Tätigkeiten): Vorgabe für neue Installationen und einmalige
# Übernahme in bestehende Kataloge (siehe app.taet_katalog_ergaenzen). Lohngruppe leer = Standard (Lohnbasis).
TAETIGKEITEN_KATALOG_STAND = "2026-11-08"
TAETIGKEITEN_KATALOG = [
    {"kst": "AVORBER", "name": "Angebotserstellung", "minuten": 0, "bezug": "", "ruest": 0, "helfer": 0},
    {"kst": "AVORBER", "name": "Aufmaß inkl. An- und Abfahrt", "minuten": 0, "bezug": "", "ruest": 0, "helfer": 0},
    {"kst": "AVORBER", "name": "Fertigungsunterlagen", "minuten": 0, "bezug": "", "ruest": 0, "helfer": 0},
    {"kst": "AVORBER", "name": "Materialbeschaffung", "minuten": 0, "bezug": "", "ruest": 0, "helfer": 0},
    {"kst": "ZUSCHNIT", "name": "Grobzuschnitt Platte", "minuten": 4, "bezug": "platte", "ruest": 0, "helfer": 0.2},
    {"kst": "ZUSCHNIT", "name": "Formatsägen", "minuten": 1, "bezug": "platte_kanten", "ruest": 0, "helfer": 0.2},
    {"kst": "ZUSCHNIT", "name": "Ablängen", "minuten": 1, "bezug": "massiv_st", "ruest": 0, "helfer": 0},
    {"kst": "ZUSCHNIT", "name": "Abrichten", "minuten": 1, "bezug": "massiv_lfm2", "ruest": 0, "helfer": 0.2},
    {"kst": "ZUSCHNIT", "name": "Besäumen", "minuten": 1, "bezug": "massiv_lfm2", "ruest": 5, "helfer": 0.2},
    {"kst": "ZUSCHNIT", "name": "Dickenhobeln", "minuten": 1, "bezug": "massiv_lfm2", "ruest": 2, "helfer": 1},
    {"kst": "ZUSCHNIT", "name": "Zuschnitt Massivholz", "minuten": 1, "bezug": "massiv_kanten", "ruest": 2, "helfer": 0.2},
    {"kst": "ZUSCHNIT", "name": "Gehrungsschnitte", "minuten": 1, "bezug": "gehrung", "ruest": 3, "helfer": 0.2},
    {"kst": "KANTENMA", "name": "Kante anleimen masch.", "minuten": 1, "bezug": "kante", "ruest": 10, "helfer": 1},
    {"kst": "SONST-MA", "name": "Kalibrieren Platte", "minuten": 1, "bezug": "platte2", "ruest": 5, "helfer": 1},
    {"kst": "SONST-MA", "name": "Schichtstoff Verpressen", "minuten": 5, "bezug": "platte2", "ruest": 5, "helfer": 0},
    {"kst": "SONST-MA", "name": "Kalibrieren Massivholz", "minuten": 1, "bezug": "massiv_lfm2", "ruest": 5, "helfer": 1},
    {"kst": "SONST-MA", "name": "Kante schleifen Massivholz", "minuten": 1, "bezug": "massiv_kanten", "ruest": 0, "helfer": 0},
    {"kst": "SONST-MA", "name": "Kante bündig fräsen", "minuten": 1, "bezug": "kante", "ruest": 5, "helfer": 0},
    {"kst": "SONST-MA", "name": "Kante schleifen", "minuten": 1, "bezug": "kante", "ruest": 0, "helfer": 0},
    {"kst": "SONST-MA", "name": "Furnier richten masch.", "minuten": 5, "bezug": "furnier", "ruest": 5, "helfer": 0},
    {"kst": "SONST-MA", "name": "Furnier schleifen/kalib", "minuten": 1, "bezug": "furnier", "ruest": 5, "helfer": 1},
    {"kst": "SONST-MA", "name": "Furnierpresse", "minuten": 5, "bezug": "furnier", "ruest": 5, "helfer": 1},
    {"kst": "SONST-MA", "name": "Fräsen-Fälzen-Nuten", "minuten": 1, "bezug": "fraesen", "ruest": 10, "helfer": 0},
    {"kst": "SONST-MA", "name": "Dübel/Lamello Verbindung", "minuten": 3, "bezug": "verbinden", "ruest": 5, "helfer": 0},
    {"kst": "SONST-MA", "name": "Zinken fräsen", "minuten": 8, "bezug": "verbinden", "ruest": 10, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Beschläge einlassen", "minuten": 0, "bezug": "", "ruest": 0, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Demontieren", "minuten": 0, "bezug": "", "ruest": 10, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Zusammenbauen", "minuten": 0, "bezug": "", "ruest": 10, "helfer": 0.5},
    {"kst": "BANKRAUM", "name": "Handling", "minuten": 3, "bezug": "platte", "ruest": 0, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Kante bündig fräsen", "minuten": 1, "bezug": "platte_lfm", "ruest": 5, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Kante brechen Massivholz", "minuten": 1, "bezug": "massiv_lfm2", "ruest": 0, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Verleimen", "minuten": 5, "bezug": "massiv", "ruest": 15, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Schleifen Exzenter massiv", "minuten": 10, "bezug": "massiv2", "ruest": 2, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Kante anleimen v. Hand", "minuten": 5, "bezug": "kante", "ruest": 10, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Kante brechen", "minuten": 1, "bezug": "kante", "ruest": 0, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Kante schleifen v. Hand", "minuten": 5, "bezug": "kante", "ruest": 0, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Kante Verputzen", "minuten": 2, "bezug": "kante", "ruest": 0, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Furnieren v. Hand", "minuten": 15, "bezug": "furnier", "ruest": 0, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Schleifen Lack", "minuten": 6, "bezug": "oberflaeche", "ruest": 2, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Bohren (auch Lochreihe)", "minuten": 2, "bezug": "bohren", "ruest": 5, "helfer": 0},
    {"kst": "BANKRAUM", "name": "Verleimen", "minuten": 5, "bezug": "verbinden", "ruest": 5, "helfer": 0.5},
    {"kst": "OBERFLÄ", "name": "Beizen inkl. Wässern", "minuten": 15, "bezug": "oberflaeche", "ruest": 5, "helfer": 0},
    {"kst": "OBERFLÄ", "name": "Füllern 2x +Schleifen", "minuten": 60, "bezug": "oberflaeche", "ruest": 20, "helfer": 0.2},
    {"kst": "OBERFLÄ", "name": "Lackieren 2x +Schleifen", "minuten": 60, "bezug": "oberflaeche", "ruest": 20, "helfer": 0.2},
    {"kst": "OBERFLÄ", "name": "Wachsen", "minuten": 10, "bezug": "oberflaeche", "ruest": 5, "helfer": 0},
    {"kst": "OBERFLÄ", "name": "Ölen 2x + Schleifen", "minuten": 18, "bezug": "oberflaeche", "ruest": 3, "helfer": 0},
    {"kst": "MONTAGE", "name": "Montage", "minuten": 0, "bezug": "", "ruest": 0, "helfer": 0},
    {"kst": "MONTAGE", "name": "Auf-/Abladen Platte", "minuten": 2, "bezug": "platte", "ruest": 0, "helfer": 0},
    {"kst": "MONTAGE", "name": "Auf-/Abladen Massiv", "minuten": 2, "bezug": "massiv", "ruest": 0, "helfer": 0},
    {"kst": "FAHRZEIT", "name": "An- und Abfahrt", "minuten": 0, "bezug": "", "ruest": 0, "helfer": 0},
]


def f(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def leer_zeile(w):
    return not (w.get("name") or w.get("matnr") or w.get("artnr") or float(w.get("preis") or 0))


def leere_entfernen(k, benutzt=()):
    """Leere Platzhalterzeilen (P01 … ohne Bezeichnung und Preis) entfernen, sofern keine Stückliste sie verwendet."""
    for liste in ("werkstoffe", "beschlaege"):
        if isinstance(k.get(liste), list):
            k[liste] = [w for w in k[liste] if not leer_zeile(w) or w.get("k") in benutzt]
    return k


def vorgaben_kopie(e):
    v = copy.deepcopy(KALK_VORGABEN)
    v.update(copy.deepcopy(e.get("kalk_vorgaben") or {}))
    # Werkstoffe und Beschläge gibt es nicht als Vorgabe: Ein Auftrag bekommt sie aus dem Materialstamm oder dem Stücklistenimport
    v["werkstoffe"], v["beschlaege"] = [], []
    return leere_entfernen(v)


KOSTENLISTE_ARTEN = {"werkstoffe": "Werkstoffe", "fremdleistungen": "Fremdleistung", "zukauf": "Zukauf",
                     "sonder_fertigung": "Sonderkosten Fertigung", "sonder_vertrieb": "Sonderkosten Vertrieb"}
KOSTENLISTE_ALT = ("fremdleistungen", "zukauf", "sonder_fertigung", "sonder_vertrieb")   # frühere Einzelfelder in extras


def kostenliste(ex):
    """Freie Kostenliste einer Position (extras.kostenliste): Zeilen mit Kostenart, Text, Menge, Einheit, Preis je Einheit.
    Ältere Einzelfelder (extras.fremdleistungen, .zukauf, .sonder_fertigung, .sonder_vertrieb, ggf. mit *_text) werden als Zeile gelesen."""
    ex = ex or {}
    zeilen = [z for z in (ex.get("kostenliste") or []) if isinstance(z, dict)]
    for art in KOSTENLISTE_ALT:
        if f(ex.get(art)) or str(ex.get(art + "_text") or "").strip():
            zeilen.append({"art": art, "text": str(ex.get(art + "_text") or ""), "menge": 1, "einheit": "Pauschale", "preis": f(ex.get(art))})
    return zeilen


def kl_betrag(z):
    m = z.get("menge")
    return (1.0 if m in (None, "") else f(m)) * f(z.get("preis"))


def wk_index(kalk):
    return {w["k"]: w for w in kalk.get("werkstoffe", []) if w.get("k")}


def wk_kosten(w):
    """Kosten je Einheit inkl. Verschnitt."""
    return f(w.get("preis")) * (1 + f(w.get("v")) / 100) if w else 0.0


def bs_index(kalk):
    return {b["k"]: b for b in kalk.get("beschlaege", []) if b.get("k")}


def fertigdicke(t, w):
    """Maßgebliche Fertigdicke eines Teils: Fertigdicke des Werkstoffs, sonst Dicke am Teil, sonst (Roh-)Dicke des Werkstoffs."""
    w = w or {}
    return f(w.get("fdicke")) or f(t.get("dicke")) or f(w.get("dicke"))


def teil_rechnen(t, wks):
    """Rechnet ein Stücklistenteil: Kosten je Teil und Bezugsgrößen je Teil."""
    l, b = f(t.get("laenge")) / 1000, f(t.get("breite")) / 1000
    p = wks.get(t.get("werkstoff") or "")
    dicke = f(p.get("dicke")) if p else f(t.get("dicke"))   # bei Massivholz: Rohdicke (für das Volumen)
    # Fertigdicke: aus dem Werkstoff (Massivholz), sonst die Dicke des Teils (z. B. aus dem Stücklistenimport), sonst die Werkstoffdicke
    fertig = fertigdicke(t, p)
    flaeche = l * b
    kosten_platte = 0.0
    volumen = 0.0
    einheit = (p or {}).get("einheit") or ""
    if p:
        if p.get("typ") == "massiv" and einheit not in ("m²", "m2", "lfm", "lfm.", "Stk.", "St.", "Stk"):
            # Massivholz: Kubikmeter aus Länge × Breite × Rohdicke, Preis je m³ inkl. Verschnitt
            volumen = flaeche * dicke / 1000
            kosten_platte = volumen * wk_kosten(p)
        elif einheit in ("lfm", "lfm."):
            kosten_platte = l * wk_kosten(p)
        elif einheit in ("Stk.", "St.", "Stk"):
            kosten_platte = wk_kosten(p)
        else:
            kosten_platte = flaeche * wk_kosten(p)
    kanten = t.get("kanten") or {}
    kante_lfm, kosten_kante = 0.0, 0.0
    for seite, laenge in (("oben", l), ("unten", l), ("links", b), ("rechts", b)):
        k = kanten.get(seite)
        if k:
            kante_lfm += laenge
            kosten_kante += laenge * wk_kosten(wks.get(k))
    furn = t.get("furnier") or {}
    furnier_m2 = sum(flaeche for s in ("oben", "unten") if furn.get(s))
    kosten_furnier = sum(flaeche * wk_kosten(wks.get(furn[s])) for s in ("oben", "unten") if furn.get(s))
    ofl = t.get("oberflaeche") or {}
    ofl_seiten = [s for s in ("oben", "unten") if ofl.get(s)]
    # Schmalflächen: ist eine Seite behandelt, werden alle vier Schmalflächen mitbehandelt (Umfang × Fertigdicke),
    # unabhängig davon, ob sie bekantet sind (Massivholz, lackierte MDF-Kanten, Anleimer …)
    schmal_m2 = 2 * (l + b) * fertig / 1000 if ofl_seiten else 0.0
    ofl_m2 = flaeche * len(ofl_seiten) + schmal_m2
    kosten_ofl = sum(flaeche * wk_kosten(wks.get(ofl[s])) for s in ofl_seiten)
    if ofl_seiten:
        kosten_ofl += schmal_m2 * wk_kosten(wks.get(ofl[ofl_seiten[0]]))
    fr = t.get("fraesen") or {}
    fraesen_lfm = sum(laenge for s, laenge in (("oben", l), ("unten", l), ("links", b), ("rechts", b)) if fr.get(s))
    massiv = bool(p) and p.get("typ") == "massiv"
    kanten_st = sum(1 for s in ("oben", "unten", "links", "rechts") if kanten.get(s))
    # lfm. Kanten: bei Platten die bekanteten Seiten, bei Massivholz die bearbeiteten (bekantet oder gefräst), sonst der Umfang
    kanten_massiv = kante_lfm or fraesen_lfm or 2 * (l + b)
    pl = 0.0 if massiv else 1.0
    ms = 1.0 if massiv else 0.0
    return {
        "dicke": fertig, "rohdicke": dicke, "volumen": volumen,
        "kosten_werkstoff": kosten_platte + kosten_kante + kosten_furnier,
        "kosten_oberflaeche": kosten_ofl,
        "kosten": kosten_platte + kosten_kante + kosten_furnier + kosten_ofl,
        "bezug": {
            "platte_st": pl, "platte_lfm": pl * l, "platte_kanten": pl * kante_lfm,
            "platte": pl * flaeche, "platte2": pl * 2 * flaeche,
            "massiv_st": ms, "massiv_lfm": ms * l, "massiv_lfm2": ms * 2 * l, "massiv_kanten": ms * kanten_massiv,
            "massiv": ms * flaeche, "massiv2": ms * 2 * flaeche,
            "kante_st": kanten_st, "furnier_st": sum(1 for s in ("oben", "unten") if furn.get(s)),
            "oberflaeche_st": 1.0 if ofl_seiten else 0.0, "gehrung": f(t.get("gehrung")),
            "zuschnitt": 2 * (l + b), "kante": kante_lfm,
            "furnier": furnier_m2, "oberflaeche": ofl_m2, "fraesen": fraesen_lfm,
            "verbinden": anzahl_verbinden(t), "bohren": f(t.get("bohren")), "tasche": f(t.get("taschen")),
            # Taschengröße (mm): Fräsweg = Umfang, Fläche = L × B, je Tasche
            "tasche_lfm": f(t.get("taschen")) * 2 * (f(t.get("tasche_l")) + f(t.get("tasche_b"))) / 1000,
            "tasche_m2": f(t.get("taschen")) * f(t.get("tasche_l")) * f(t.get("tasche_b")) / 1e6, "teile": 1,
            **{"x_" + str(k): f(v) for k, v in (t.get("bezug_eigen") or {}).items()},
        },
    }


def lohn_von(kalk, gruppe, warnungen=None):
    """Mittellohn I einer Lohngruppe. Fehlt die Gruppe oder steht sie auf 0 €/h, gilt der Lohn der Lohnbasis
    (sonst würden Stunden ohne Kosten gerechnet); das wird in „warnungen“ vermerkt."""
    lohn = next((f(g.get("lohn")) for g in kalk.get("loehne", []) if g.get("gruppe") == gruppe), 0.0)
    basis = kalk.get("lohnbasis", "Durchschnitt")
    if lohn <= 0 and gruppe != basis:
        ersatz = next((f(g.get("lohn")) for g in kalk.get("loehne", []) if g.get("gruppe") == basis), 0.0)
        if warnungen is not None and ersatz > 0:
            warnungen.add(f"Lohngruppe „{gruppe}“ hat keinen Lohn hinterlegt; gerechnet mit der Lohnbasis {basis} ({ersatz:.2f} €/h)".replace(".", ","))
        return ersatz
    if lohn <= 0 and warnungen is not None:
        warnungen.add(f"Lohngruppe „{gruppe}“ hat keinen Lohn hinterlegt – die Stunden kosten 0 €")
    return lohn


def gk_von(kalk, kst):
    for k in kalk.get("kostenstellen", []):
        if k["kst"] == kst:
            return f(k.get("gk"))
    return 0.0


def position_rechnen(pos, kalk, kinder=()):
    """Liefert die komplette Kalkulation einer Position (je Anzahl) inkl. Unterpositionen."""
    menge = f(pos.get("menge")) or 0.0
    wks, bss = wk_index(kalk), bs_index(kalk)
    stueck = pos.get("stueckliste") or []
    eigene = kalk.get("_bezug_eigen") or []
    bezug = {k: 0.0 for k in BEZUG if k}
    bezug.update({"x_" + str(b["k"]): 0.0 for b in eigene if b.get("k")})
    werkstoffe = oberflaeche = massiv_m3 = 0.0
    teile = []
    for t in stueck:
        r = teil_rechnen(t, wks)
        n = 1.0 if t.get("stueck") in (None, "") else f(t.get("stueck"))   # leere Stückzahl = 1 Stück
        werkstoffe += r["kosten_werkstoff"] * n
        oberflaeche += r["kosten_oberflaeche"] * n
        massiv_m3 += r["volumen"] * n
        for k, v in r["bezug"].items():
            if k in bezug:
                bezug[k] += v * n
        teile.append({"kosten": round(r["kosten"], 2), "dicke": r["dicke"]})
    # Bezugsgrößen, die je Position eingetragen werden (eigene mit Quelle „Position“), und Anzahl Beschläge
    pb = (pos.get("extras") or {}).get("bezug_eigen") or {}
    for b in eigene:
        if b.get("k") and (b.get("quelle") or "teil") == "position":
            bezug["x_" + str(b["k"])] = f(pb.get(str(b["k"])))
    bezug["beschlaege"] = sum(f(b.get("menge")) for b in pos.get("beschlaege") or [])
    beschlaege = 0.0
    bzeilen = []
    for b in pos.get("beschlaege") or []:
        stamm = bss.get(b.get("k") or "")
        k = f(stamm.get("preis")) if stamm else 0.0   # Beschläge: Kosten je Stück/Einheit, kein Verschnitt
        beschlaege += k * f(b.get("menge"))
        bzeilen.append({"kosten_me": round(k, 2), "gesamt": round(k * f(b.get("menge")), 2),
                        "einheit": stamm.get("einheit") if stamm else "", "name": stamm.get("name") if stamm else ""})
    ex = pos.get("extras") or {}
    # freie Kostenliste: Werkstoffe (mit Kleinmaterial und Material-GK), Fremdleistungen und Zukauf (mit Material-GK)
    kl = {k: 0.0 for k in KOSTENLISTE_ARTEN}
    for z in kostenliste(ex):
        kl[z.get("art") if z.get("art") in kl else "werkstoffe"] += kl_betrag(z)
    werkstoffe += kl["werkstoffe"]
    klein_pz = f(ex.get("kleinmaterial")) if ex.get("kleinmaterial") not in (None, "") else f(kalk.get("kleinmaterial"))
    kleinmaterial = (werkstoffe + beschlaege + oberflaeche) * klein_pz / 100
    fremd = kl["fremdleistungen"]
    # Zukauf (Handelsware, z. B. fertig gekaufter Schrank): zählt zum Material, mit Material-GK
    zukauf = kl["zukauf"]
    material = werkstoffe + beschlaege + oberflaeche + kleinmaterial + fremd + zukauf
    gk_mat = material * f(kalk.get("gk_material")) / 100   # Material-GK auch auf Fremdleistungen und Zukauf

    # Zeiten
    lohn_kst, stunden_kst = {}, {}
    zzeilen = []
    warnungen = set()
    helfer_gr, helfer_kst = kalk.get("helfer_gruppe", "Hilfskraft"), kalk.get("helfer_kst", "HELFER")
    sum_bearb = sum_ruest = sum_helfer = 0.0

    roh = {}  # (Kostenstelle, Lohngruppe) → Stunden

    def buche(kst, gruppe, h):
        roh[(kst, gruppe)] = roh.get((kst, gruppe), 0) + h

    modus = pos.get("zeitmodus") or "taetigkeiten"
    for z in pos.get("zeiten") or []:
        gruppe = z.get("gruppe") or kalk.get("lohnbasis", "Durchschnitt")
        if modus == "stunden":
            h = f(z.get("stunden"))
            buche(z.get("kst"), gruppe, h)
            sum_bearb += h
            zzeilen.append({"min_anz": round(h * 60, 2), "h_anz": round(h, 2), "menge": None})
            continue
        q = bezug.get(z.get("bezug") or "", 0.0)
        faktor = q if z.get("bezug") else 1.0
        bez_fehlt = bool(z.get("bezug")) and z.get("bezug") not in bezug
        if bez_fehlt:
            warnungen.add(f"Tätigkeit „{z.get('name') or z.get('kst') or ''}“: Bezugsgröße „{z.get('bezug')}“ gibt es nicht mehr – sie wird mit 0 gerechnet")
        min_anz = f(z.get("minuten")) * faktor
        ruest = 0.0 if z.get("ruest_aus") else f(z.get("ruest"))      # Rüstzeit/Helfer je Zeile abschaltbar
        ruest_anz = ruest / menge if menge else 0
        # Helfer = Anteil einer Helferkraft während Bearbeitung und Rüsten (1,0 = ein Helfer die ganze Zeit)
        helfer_anz = 0.0 if z.get("helfer_aus") else (min_anz + ruest_anz) * f(z.get("helfer"))
        buche(z.get("kst"), gruppe, (min_anz + ruest_anz) / 60)
        if helfer_anz:
            # Helferstunden auf die Helfer-Kostenstelle/-Lohngruppe; fehlen diese in den Auftragswerten,
            # auf die Kostenstelle der Zeile und die Lohnbasis (sonst würden sie mit 0 € gerechnet)
            hk = helfer_kst if any(k.get("kst") == helfer_kst for k in kalk.get("kostenstellen", [])) else z.get("kst")
            hg = helfer_gr if any(g.get("gruppe") == helfer_gr for g in kalk.get("loehne", [])) else kalk.get("lohnbasis", "Durchschnitt")
            buche(hk, hg, helfer_anz / 60)
        sum_bearb += min_anz / 60
        sum_ruest += ruest / 60
        sum_helfer += helfer_anz / 60
        zzeilen.append({"bezug_fehlt": bez_fehlt, "menge": round(q, 2) if z.get("bezug") else None, "min_anz": round(min_anz, 2),
                        "h_anz": round(min_anz / 60, 2), "ruest_h": round(ruest / 60, 2), "helfer_h": round(helfer_anz * menge / 60, 2),
                        "h_pos": round((min_anz * menge + ruest + helfer_anz * menge) / 60, 2)})
    # Stunden je Anzahl nicht auf 1/100 h runden: bei großen Mengen gingen sonst Zeiten verloren oder würden aufgebläht
    # (0,004 h × 200 Stück). Gerundet wird nur in der Anzeige.
    for (kst, gruppe), h in roh.items():
        h = round(h, 6)
        stunden_kst[kst] = round(stunden_kst.get(kst, 0) + h, 6)
        lohn_kst[kst] = lohn_kst.get(kst, 0) + h * lohn_von(kalk, gruppe, warnungen)
    lohn = sum(lohn_kst.values())
    gk_lohn = sum(v * gk_von(kalk, k) / 100 for k, v in lohn_kst.items())
    stunden = sum(stunden_kst.values())
    sonder_fert = kl["sonder_fertigung"]   # Sonderkosten aus der Kostenliste: Fertigung mit W+G, Vertrieb ohne
    sonder_vertr = kl["sonder_vertrieb"]
    selbstkosten = material + gk_mat + lohn + gk_lohn + sonder_fert

    hat_kalk = selbstkosten > 0
    if pos.get("preis_manuell") or not hat_kalk:
        ep = f(pos.get("einzelpreis"))
        wg = ep - selbstkosten - sonder_vertr
        wg_pz = (wg / selbstkosten * 100) if selbstkosten else 0
    else:
        wg_pz = f(ex.get("wg")) if ex.get("wg") not in (None, "") else f(kalk.get("wg"))
        wg = selbstkosten * wg_pz / 100
        ep = round(selbstkosten + wg + sonder_vertr, 2)

    # Unterpositionen (je Anzahl der Hauptposition)
    unter_ep = unter_kosten = 0.0
    unter_kat = {}   # Kostenarten der Unterpositionen (je Anzahl der Hauptposition), für die Summenansicht
    for k in kinder:
        if k.get("gesperrt"):   # gesperrte Unterpositionen zählen nicht
            continue
        unter_ep += f(k["menge"]) * k["_ep_gesamt"]
        unter_kosten += f(k["menge"]) * k["_kosten_gesamt"]
        kc = k.get("_calc") or {}
        for key in KATEGORIEN:
            unter_kat[key] = unter_kat.get(key, 0.0) + f(k["menge"]) * (f(kc.get(key)) + f((kc.get("unter_kat") or {}).get(key)))
    ep_gesamt = round(ep + unter_ep, 2)
    kosten_gesamt = selbstkosten + unter_kosten
    return {
        "werkstoffe": werkstoffe, "beschlaege": beschlaege, "oberflaeche": oberflaeche,
        "kleinmaterial_pz": klein_pz, "kleinmaterial": kleinmaterial, "fremdleistungen": fremd, "zukauf": zukauf, "kostenliste_werkstoffe": kl["werkstoffe"],

        "material": material, "gk_material_pz": f(kalk.get("gk_material")), "gk_material": gk_mat,
        "material_gk": material + gk_mat,
        "stunden": stunden, "stunden_kst": stunden_kst, "lohn": lohn,
        "gk_lohn_pz": (gk_lohn / lohn * 100) if lohn else 0, "gk_lohn": gk_lohn, "lohn_gk": lohn + gk_lohn,
        "sonder_fertigung": sonder_fert, "selbstkosten": selbstkosten,
        "wg_pz": wg_pz, "wg": wg, "sonder_vertrieb": sonder_vertr, "einzelpreis": round(ep, 2),
        "unter_ep": round(unter_ep, 2), "unter_kosten": unter_kosten, "unter_kat": unter_kat,
        "ep_gesamt": ep_gesamt, "kosten_gesamt": kosten_gesamt,
        "wg_gesamt_pz": ((ep_gesamt - kosten_gesamt) / kosten_gesamt * 100) if kosten_gesamt else 0,
        "gesamtpreis": round(ep_gesamt * menge, 2),
        "bezug": {k: round(v, 3) for k, v in bezug.items()},
        "teile": teile, "beschlagzeilen": bzeilen, "zeitzeilen": zzeilen, "massiv_m3": round(massiv_m3, 4),
        "zeit_summen": {"bearbeitung": sum_bearb, "ruest": sum_ruest, "helfer": sum_helfer,
                        "gesamt_anz": sum_bearb + sum_helfer,
                        "gesamt_pos": (sum_bearb + sum_helfer) * menge + sum_ruest},
        "hat_kalk": hat_kalk,
        "warnungen": sorted(warnungen),
    }


KATEGORIEN = ["werkstoffe", "beschlaege", "oberflaeche", "kleinmaterial", "fremdleistungen", "zukauf", "material",
              "gk_material", "material_gk", "stunden", "lohn", "gk_lohn", "lohn_gk", "sonder_fertigung",
              "selbstkosten", "wg", "sonder_vertrieb"]
