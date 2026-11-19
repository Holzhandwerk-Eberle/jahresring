# -*- coding: utf-8 -*-
"""
Positionskalkulation für Jahresring.
Alle Beträge je Anzahl (= je Stück der Position), sofern nicht anders benannt.
"""
import copy
import math
import threading
from kern import kfm, zahl_lesen

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


_UNLESBAR = threading.local()   # je Rechenlauf: Werte, die keine Zahl sind (werden als Warnung an der Position gemeldet)


def f(x):
    """Zahl aus einem Kalkulationswert. Texte in deutscher Schreibweise („12,5“, „40 €“) werden gelesen. Was keine endliche
    Zahl ist („abc“, unendlich), zählt als 0 und wird gemerkt, damit die Position darauf hinweisen kann."""
    if isinstance(x, (int, float)):
        try:
            if math.isfinite(x):
                return float(x)
        except OverflowError:
            pass
    elif not x:
        return 0.0
    else:
        v = zahl_lesen(x)
        if v is not None:
            return v
    liste = getattr(_UNLESBAR, "liste", None)
    if liste is not None and len(liste) < 20:
        liste.append(str(x)[:30])
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
    """Kosten je Einheit inkl. Verschnitt. Ein Verschnitt unter −100 % ergäbe negative Kosten: gerechnet wird dann mit 0."""
    return f(w.get("preis")) * max(0.0, 1 + f(w.get("v")) / 100) if w else 0.0


# Womit die Kalkulation rechnet: Kanten je laufendem Meter, Platten, Furnier und Oberflächen je m², Massivholz je m³.
# Steht am Werkstoff eine dieser Schreibweisen (oder nichts), ist der Preis schon der Preis je Recheneinheit.
EINHEIT_GLEICH = {"lfm": {"lfm", "lfm.", "m", "lm", "lfdm"}, "m²": {"m²", "m2", "qm"}, "m³": {"m³", "m3", "cbm"}}


def preis_bezug(w, soll, warnungen=None, was="Werkstoff"):
    """Kosten je Recheneinheit (lfm, m² oder m³) inkl. Verschnitt. Hat der Werkstoff eine andere Einheit (Rolle, Dose, Liter, kg,
    Tafel …), wird über „um“ umgerechnet: 1 Einheit = um Recheneinheiten. Fehlt die Umrechnung, bleibt es beim bisherigen Rechenweg
    (Preis × Recheneinheit) – dann aber mit Warnung, weil der Preis so fast immer falsch ist."""
    if not w:
        return 0.0
    k = wk_kosten(w)
    e = str(w.get("einheit") or "").strip()
    if not e or e in EINHEIT_GLEICH[soll]:
        return k
    um = f(w.get("um"))
    if um > 0:
        return k / um
    if warnungen is not None and k:
        warnungen.add(f"{was} „{w.get('name') or w.get('k')}“ hat die Einheit „{e}“, gerechnet wird je {soll}. Bitte bei den Werkstoffen des Auftrags "
                      f"die Umrechnung eintragen (1 {e} = … {soll}) oder den Preis je {soll} angeben.")
    return k


def ohne_preis(w, was, warnungen):
    """Warnung, wenn ein verwendeter Werkstoff keinen Preis hat (z. B. nach einem Stücklistenimport neu angelegt)."""
    if warnungen is not None and w and f(w.get("preis")) <= 0:
        warnungen.add(f"{was} „{w.get('name') or w.get('k')}“ hat keinen Preis – gerechnet wird mit 0 €")
    if warnungen is not None and w and f(w.get("v")) < -100:
        warnungen.add(f"{was} „{w.get('name') or w.get('k')}“: Verschnitt unter −100 % – gerechnet wird mit 0 €")


def bs_index(kalk):
    return {b["k"]: b for b in kalk.get("beschlaege", []) if b.get("k")}


def fertigdicke(t, w):
    """Maßgebliche Fertigdicke eines Teils: Fertigdicke des Werkstoffs, sonst Dicke am Teil, sonst (Roh-)Dicke des Werkstoffs."""
    w = w or {}
    return f(w.get("fdicke")) or f(t.get("dicke")) or f(w.get("dicke"))


def teil_rechnen(t, wks, warnungen=None):
    """Rechnet ein Stücklistenteil: Kosten je Teil und Bezugsgrößen je Teil. „warnungen“ (Menge) sammelt Stellen,
    an denen sonst still mit 0 € gerechnet würde."""
    l, b = f(t.get("laenge")) / 1000, f(t.get("breite")) / 1000
    p = wks.get(t.get("werkstoff") or "")
    # bei Massivholz: Rohdicke des Werkstoffs (für das Volumen); fehlt sie dort, die Dicke des Teils
    dicke = (f(p.get("dicke")) or f(t.get("dicke"))) if p else f(t.get("dicke"))
    if warnungen is not None:
        if t.get("werkstoff") and not p:
            warnungen.add(f"Werkstoff „{t.get('werkstoff')}“ aus der Stückliste fehlt in den Werkstoffen des Auftrags – das Material kostet 0 €")
        ohne_preis(p, "Werkstoff", warnungen)
        for wo, kz in [("Kante", k_) for k_ in (t.get("kanten") or {}).values()] + [("Furnier", k_) for k_ in (t.get("furnier") or {}).values()] + \
                [("Oberfläche", k_) for k_ in (t.get("oberflaeche") or {}).values()]:
            if kz and isinstance(kz, str) and kz not in wks:
                warnungen.add(f"{wo} „{kz}“ aus der Stückliste fehlt in den Werkstoffen des Auftrags – sie kostet 0 €")
            elif kz and isinstance(kz, str):
                ohne_preis(wks.get(kz), wo, warnungen)
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
            kosten_platte = volumen * preis_bezug(p, "m³", warnungen, "Massivholz")
            if warnungen is not None and not dicke and flaeche:
                warnungen.add(f"Massivholz „{p.get('name') or p.get('k')}“: weder Rohdicke am Werkstoff noch Dicke am Teil – das Material kostet 0 €")
        elif einheit in ("lfm", "lfm."):
            kosten_platte = l * wk_kosten(p)
        elif einheit in ("Stk.", "St.", "Stk"):
            kosten_platte = wk_kosten(p)
        else:
            kosten_platte = flaeche * preis_bezug(p, "m²", warnungen, "Werkstoff")
    kanten = t.get("kanten") or {}
    kante_lfm, kosten_kante = 0.0, 0.0
    for seite, laenge in (("oben", l), ("unten", l), ("links", b), ("rechts", b)):
        k = kanten.get(seite)
        if k:
            kante_lfm += laenge
            kosten_kante += laenge * preis_bezug(wks.get(k), "lfm", warnungen, "Kante")
    furn = t.get("furnier") or {}
    furnier_m2 = sum(flaeche for s in ("oben", "unten") if furn.get(s))
    kosten_furnier = sum(flaeche * preis_bezug(wks.get(furn[s]), "m²", warnungen, "Furnier") for s in ("oben", "unten") if furn.get(s))
    ofl = t.get("oberflaeche") or {}
    ofl_seiten = [s for s in ("oben", "unten") if ofl.get(s)]
    # Schmalflächen: ist eine Seite behandelt, werden alle vier Schmalflächen mitbehandelt (Umfang × Fertigdicke),
    # unabhängig davon, ob sie bekantet sind (Massivholz, lackierte MDF-Kanten, Anleimer …)
    schmal_m2 = 2 * (l + b) * fertig / 1000 if ofl_seiten else 0.0
    ofl_m2 = flaeche * len(ofl_seiten) + schmal_m2
    kosten_ofl = sum(flaeche * preis_bezug(wks.get(ofl[s]), "m²", warnungen, "Oberfläche") for s in ofl_seiten)
    if ofl_seiten:
        kosten_ofl += schmal_m2 * preis_bezug(wks.get(ofl[ofl_seiten[0]]), "m²", warnungen, "Oberfläche")
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
    aussen = getattr(_UNLESBAR, "liste", None)
    _UNLESBAR.liste = []
    try:
        erg = _position_rechnen(pos, kalk, kinder)
        for t in sorted(set(_UNLESBAR.liste)):
            erg["warnungen"].append(f"Der Wert „{t}“ ist keine Zahl – gerechnet wurde mit 0. Bitte die Eingaben der Position prüfen.")
        return erg
    finally:
        _UNLESBAR.liste = aussen


def _position_rechnen(pos, kalk, kinder=()):
    menge = f(pos.get("menge")) or 0.0
    wks, bss = wk_index(kalk), bs_index(kalk)
    stueck = pos.get("stueckliste") or []
    eigene = kalk.get("_bezug_eigen") or []
    bezug = {k: 0.0 for k in BEZUG if k}
    bezug.update({"x_" + str(b["k"]): 0.0 for b in eigene if b.get("k")})
    werkstoffe = oberflaeche = massiv_m3 = 0.0
    teile = []
    warnungen = set()
    for i, t in enumerate(stueck, 1):
        # Negative Stückzahlen und Maße gibt es nicht; sie würden den Preis still mindern. Das Teil zählt dann nicht und wird gemeldet.
        negativ = [n for n, k in (("Stückzahl", "stueck"), ("Länge", "laenge"), ("Breite", "breite")) if f(t.get(k)) < 0]
        if negativ:
            warnungen.add(f"Stückliste Zeile {i}{' (' + str(t.get('verwendung')) + ')' if t.get('verwendung') else ''}: {' und '.join(negativ)} negativ – "
                          "das Teil wird nicht gerechnet")
            t = {**t, "stueck": 0, "laenge": max(0.0, f(t.get("laenge"))), "breite": max(0.0, f(t.get("breite")))}
        r = teil_rechnen(t, wks, warnungen)
        n = 1.0 if t.get("stueck") in (None, "") else f(t.get("stueck"))   # leere Stückzahl = 1 Stück
        werkstoffe += r["kosten_werkstoff"] * n
        oberflaeche += r["kosten_oberflaeche"] * n
        massiv_m3 += r["volumen"] * n
        for k, v in r["bezug"].items():
            if k in bezug:
                bezug[k] += v * n
        teile.append({"kosten": kfm(r["kosten"]), "dicke": r["dicke"]})
    # Bezugsgrößen, die je Position eingetragen werden (eigene mit Quelle „Position“), und Anzahl Beschläge
    pb = (pos.get("extras") or {}).get("bezug_eigen") or {}
    for b in eigene:
        if b.get("k") and (b.get("quelle") or "teil") == "position":
            bezug["x_" + str(b["k"])] = f(pb.get(str(b["k"])))
    # Anzahl Beschläge: leere Zeilen (kein Beschlag gewählt und keine Bemerkung) zählen nicht – sonst rechnet eine versehentlich
    # angelegte oder noch nicht ausgefüllte Zeile Arbeitszeit. Eine Zeile nur mit Bemerkung zählt (z. B. bauseits gestellte Beschläge).
    bs_liste = []
    for i, b in enumerate(pos.get("beschlaege") or [], 1):
        if f(b.get("menge")) < 0:
            warnungen.add(f"Beschläge Zeile {i}: Menge negativ – die Zeile wird nicht gerechnet")
            b = {**b, "menge": 0}
        bs_liste.append(b)
    bezug["beschlaege"] = sum(f(b.get("menge")) for b in bs_liste if b.get("k") or str(b.get("bemerkung") or "").strip())
    beschlaege = 0.0
    bzeilen = []
    for b in bs_liste:
        stamm = bss.get(b.get("k") or "")
        k = f(stamm.get("preis")) if stamm else 0.0   # Beschläge: Kosten je Stück/Einheit, kein Verschnitt
        if b.get("k") and not stamm and f(b.get("menge")):
            warnungen.add(f"Beschlag „{b.get('k')}“ fehlt in den Beschlägen des Auftrags – er kostet 0 €")
        elif stamm and k <= 0 and f(b.get("menge")):
            warnungen.add(f"Beschlag „{stamm.get('name') or b.get('k')}“ hat keinen Preis – gerechnet wird mit 0 €")
        beschlaege += k * f(b.get("menge"))
        bzeilen.append({"kosten_me": kfm(k), "gesamt": kfm(k * f(b.get("menge"))),
                        "einheit": stamm.get("einheit") if stamm else "", "name": stamm.get("name") if stamm else ""})
    ex = pos.get("extras") or {}
    # freie Kostenliste: Werkstoffe (mit Kleinmaterial und Material-GK), Fremdleistungen und Zukauf (mit Material-GK)
    kl = {k: 0.0 for k in KOSTENLISTE_ARTEN}
    for z in kostenliste(ex):
        kl[z.get("art") if z.get("art") in kl else "werkstoffe"] += kl_betrag(z)
    werkstoffe += kl["werkstoffe"]
    klein_pz = f(ex.get("kleinmaterial")) if ex.get("kleinmaterial") not in (None, "") else f(kalk.get("kleinmaterial"))
    if klein_pz < -100 or f(kalk.get("gk_material")) < -100:
        warnungen.add("Zuschlag unter −100 % (Kleinmaterial oder Material-Gemeinkosten) – gerechnet wird mit −100 %")
        klein_pz = max(-100.0, klein_pz)
    kleinmaterial = (werkstoffe + beschlaege + oberflaeche) * klein_pz / 100
    fremd = kl["fremdleistungen"]
    # Zukauf (Handelsware, z. B. fertig gekaufter Schrank): zählt zum Material, mit Material-GK
    zukauf = kl["zukauf"]
    material = werkstoffe + beschlaege + oberflaeche + kleinmaterial + fremd + zukauf
    gk_mat = material * max(-100.0, f(kalk.get("gk_material"))) / 100   # Material-GK auch auf Fremdleistungen und Zukauf

    # Zeiten
    lohn_kst, stunden_kst = {}, {}
    zzeilen = []
    helfer_gr, helfer_kst = kalk.get("helfer_gruppe", "Hilfskraft"), kalk.get("helfer_kst", "HELFER")
    sum_bearb = sum_ruest = sum_helfer = 0.0

    roh = {}  # (Kostenstelle, Lohngruppe) → Stunden
    # Arbeit im Haushalt des Kunden (§ 35a EStG): Stunden der dafür gewählten Kostenstellen (Montage, Reparatur, Fahrzeit …).
    # Helferstunden zählen nach der Kostenstelle der Zeile, bei der geholfen wird, auch wenn sie auf der Helfer-Kostenstelle stehen.
    haus_kst = set(kalk.get("_haushalt_kst") or [])
    roh_haus = {}

    def buche(kst, gruppe, h, zeile_kst=None):
        roh[(kst, gruppe)] = roh.get((kst, gruppe), 0) + h
        if (kst if zeile_kst is None else zeile_kst) in haus_kst:
            roh_haus[(kst, gruppe)] = roh_haus.get((kst, gruppe), 0) + h

    modus = pos.get("zeitmodus") or "taetigkeiten"
    for i, z in enumerate(pos.get("zeiten") or [], 1):
        negativ = [k for k in ("stunden", "minuten", "ruest", "helfer") if f(z.get(k)) < 0]
        if negativ:   # negative Zeiten würden den Preis still mindern
            warnungen.add(f"Zeiten Zeile {i}{' (' + str(z.get('name') or z.get('kst')) + ')' if z.get('name') or z.get('kst') else ''}: negative Zeit – "
                          "gerechnet wird mit 0")
            z = {**z, **{k: 0 for k in negativ}}
        gruppe = z.get("gruppe") or kalk.get("lohnbasis", "Durchschnitt")
        if modus == "stunden":
            h = f(z.get("stunden"))
            buche(z.get("kst"), gruppe, h)
            sum_bearb += h
            zzeilen.append({"min_anz": kfm(h * 60), "h_anz": kfm(h), "menge": None})
            continue
        q = bezug.get(z.get("bezug") or "", 0.0)
        faktor = q if z.get("bezug") else 1.0
        bez_fehlt = bool(z.get("bezug")) and z.get("bezug") not in bezug
        if bez_fehlt:
            warnungen.add(f"Tätigkeit „{z.get('name') or z.get('kst') or ''}“: Bezugsgröße „{z.get('bezug')}“ gibt es nicht mehr – sie wird mit 0 gerechnet")
        min_anz = f(z.get("minuten")) * faktor
        # Rüstzeit/Helfer je Zeile abschaltbar; ist die Bezugsgröße in dieser Position 0 (z. B. keine Beschläge),
        # entfällt die Tätigkeit ganz – auch die Rüstzeit. Tätigkeiten ohne Bezugsgröße (Fahrzeit …) zählen immer.
        leer = bool(z.get("bezug")) and abs(q) < 1e-9
        ruest = 0.0 if z.get("ruest_aus") or leer else f(z.get("ruest"))
        ruest_anz = ruest / menge if menge else 0
        # Helfer = Anteil einer Helferkraft während der Bearbeitung (1,0 = ein Helfer die ganze Bearbeitungszeit); Rüstzeit ohne Helfer
        helfer_anz = 0.0 if z.get("helfer_aus") else min_anz * f(z.get("helfer"))
        buche(z.get("kst"), gruppe, (min_anz + ruest_anz) / 60)
        if helfer_anz:
            # Helferstunden auf die Helfer-Kostenstelle/-Lohngruppe; fehlen diese in den Auftragswerten,
            # auf die Kostenstelle der Zeile und die Lohnbasis (sonst würden sie mit 0 € gerechnet)
            hk = helfer_kst if any(k.get("kst") == helfer_kst for k in kalk.get("kostenstellen", [])) else z.get("kst")
            hg = helfer_gr if any(g.get("gruppe") == helfer_gr for g in kalk.get("loehne", [])) else kalk.get("lohnbasis", "Durchschnitt")
            buche(hk, hg, helfer_anz / 60, z.get("kst"))
        sum_bearb += min_anz / 60
        sum_ruest += ruest / 60
        sum_helfer += helfer_anz / 60
        zzeilen.append({"bezug_fehlt": bez_fehlt, "menge": kfm(q) if z.get("bezug") else None, "min_anz": kfm(min_anz),
                        "h_anz": kfm(min_anz / 60), "ruest_h": kfm(ruest / 60), "helfer_h": kfm(helfer_anz * menge / 60),
                        "h_pos": kfm((min_anz * menge + ruest + helfer_anz * menge) / 60)})
    # Stunden je Anzahl nicht auf 1/100 h runden: bei großen Mengen gingen sonst Zeiten verloren oder würden aufgebläht
    # (0,004 h × 200 Stück). Gerundet wird nur in der Anzeige.
    ksts = {k.get("kst") for k in kalk.get("kostenstellen", [])}
    for (kst, gruppe), h in roh.items():
        h = round(h, 6)
        if h and kst not in ksts:
            warnungen.add(f"Kostenstelle „{kst or '(leer)'}“ fehlt in den Zuschlägen des Auftrags – ihre Stunden werden ohne Gemeinkosten gerechnet")
        stunden_kst[kst] = round(stunden_kst.get(kst, 0) + h, 6)
        lohn_kst[kst] = lohn_kst.get(kst, 0) + h * lohn_von(kalk, gruppe, warnungen)
    lohn = sum(lohn_kst.values())
    if any(gk_von(kalk, k) < -100 for k in lohn_kst):
        warnungen.add("Gemeinkostenzuschlag einer Kostenstelle unter −100 % – gerechnet wird mit −100 %")
    gk_lohn = sum(v * max(-100.0, gk_von(kalk, k)) / 100 for k, v in lohn_kst.items())
    lohn_gk_haushalt = sum(round(h, 6) * lohn_von(kalk, gruppe) * (1 + max(-100.0, gk_von(kalk, kst)) / 100) for (kst, gruppe), h in roh_haus.items())
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
        if wg_pz < -100:
            warnungen.add("Wagnis und Gewinn unter −100 % – gerechnet wird mit −100 %")
            wg_pz = -100.0
        wg = selbstkosten * wg_pz / 100
        ep = kfm(selbstkosten + wg + sonder_vertr)

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
    ep_gesamt = kfm(ep + unter_ep)
    kosten_gesamt = selbstkosten + unter_kosten
    return {
        "werkstoffe": werkstoffe, "beschlaege": beschlaege, "oberflaeche": oberflaeche,
        "kleinmaterial_pz": klein_pz, "kleinmaterial": kleinmaterial, "fremdleistungen": fremd, "zukauf": zukauf, "kostenliste_werkstoffe": kl["werkstoffe"],

        "material": material, "gk_material_pz": f(kalk.get("gk_material")), "gk_material": gk_mat,
        "material_gk": material + gk_mat,
        "stunden": stunden, "stunden_kst": stunden_kst, "lohn": lohn,
        "gk_lohn_pz": (gk_lohn / lohn * 100) if lohn else 0, "gk_lohn": gk_lohn, "lohn_gk": lohn + gk_lohn,
        "lohn_gk_haushalt": lohn_gk_haushalt,
        "sonder_fertigung": sonder_fert, "selbstkosten": selbstkosten,
        "wg_pz": wg_pz, "wg": wg, "sonder_vertrieb": sonder_vertr, "einzelpreis": kfm(ep),
        "unter_ep": kfm(unter_ep), "unter_kosten": unter_kosten, "unter_kat": unter_kat,
        "ep_gesamt": ep_gesamt, "kosten_gesamt": kosten_gesamt,
        "wg_gesamt_pz": ((ep_gesamt - kosten_gesamt) / kosten_gesamt * 100) if kosten_gesamt else 0,
        "gesamtpreis": kfm(ep_gesamt * menge),
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
