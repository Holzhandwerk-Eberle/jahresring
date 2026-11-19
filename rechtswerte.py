"""Gesetzliche Werte mit Stichtag (Z12, K10): Umsatzsteuersätze hier, der Basiszinssatz in mahnwesen.py, der Mindestlohn in personal.py.

Hinterlegt ist jeweils der Stand bei Auslieferung der Version. Ändert der Gesetzgeber einen Wert, trägt der Betrieb ihn in den
Einstellungen mit dem Tag ein, ab dem er gilt; ein späteres Update bringt ihn ebenfalls mit. Eigene Einträge stehen in den
Einstellungen „steuersaetze“, „mindestlohn“ und „mahnwesen.basiszinsen“; bei gleichem Stichtag zählt der eigene Eintrag."""
from datetime import date

# Umsatzsteuersätze (§ 12 UStG): gültig ab, Regelsatz, ermäßigter Satz. Zweites Halbjahr 2020: befristete Senkung.
STEUERSAETZE = [("2007-01-01", 19.0, 7.0), ("2020-07-01", 16.0, 5.0), ("2021-01-01", 19.0, 7.0)]


def _tag(wert):
    try:
        return date.fromisoformat(str(wert or "")[:10])
    except ValueError:
        return None


def de_tag(iso):
    t = _tag(iso)
    return f"{t:%d.%m.%Y}" if t else str(iso or "")


def de_zahl(x, stellen=2):
    return f"{float(x):.{stellen}f}".replace(".", ",")


def steuer_eigene(liste):
    """Eigene Einträge der Einstellung „steuersaetze“, geprüft und nach Stichtag sortiert: [{ab, regel, ermaessigt}]."""
    aus = {}
    for x in liste if isinstance(liste, list) else []:
        if not isinstance(x, dict):
            continue
        t = _tag(x.get("ab"))
        try:
            regel, erm = round(float(x.get("regel")), 2), round(float(x.get("ermaessigt")), 2)
        except (TypeError, ValueError):
            continue
        if t and t.year >= 2007 and 0 < erm <= regel <= 40:
            aus[t.isoformat()] = (regel, erm)
    return [{"ab": ab, "regel": r, "ermaessigt": e} for ab, (r, e) in sorted(aus.items())]


def steuerliste(eigene=None):
    """Hinterlegte und eigene Sätze, aufsteigend nach Stichtag: [(ab, Regelsatz, ermäßigter Satz)]."""
    d = {ab: (r, e) for ab, r, e in STEUERSAETZE}
    for x in steuer_eigene(eigene):
        d[x["ab"]] = (x["regel"], x["ermaessigt"])
    return [(ab, r, e) for ab, (r, e) in sorted(d.items())]


def steuersatz_am(eigene, satz, tag_iso):
    """Beim Kunden steht ein Steuersatz (Vorgabe 19). Ist das der Regelsatz oder der ermäßigte Satz irgendeines Zeitraums, zählt
    der Satz dieser Art, der am genannten Tag gilt. Andere Sätze (0 Prozent, Sonderfälle) bleiben, wie sie sind."""
    try:
        satz = float(satz)
    except (TypeError, ValueError):
        return satz
    liste = steuerliste(eigene)
    art = 1 if any(abs(satz - x[1]) < 0.005 for x in liste) else 2 if any(abs(satz - x[2]) < 0.005 for x in liste) else 0
    if not art or satz <= 0:
        return satz
    tag = str(tag_iso or "")[:10]
    if not _tag(tag):
        tag = date.today().isoformat()
    return next((x for x in reversed(liste) if x[0] <= tag), liste[0])[art]


def hinweise(e, zinsen_genutzt, lohn_genutzt, heute=None):
    """Erinnerungen für die Startseite des Inhabers: Werte, die zu einem Stichtag nachzutragen sind. Gemeldet wird nur, was der
    Betrieb benutzt (Verzugszinsen im Mahnwesen, Mitarbeiter mit Lohn)."""
    import mahnwesen
    import personal
    heute = heute or date.today()
    aus = []
    cfg = mahnwesen.einstellung(e, heute)
    if zinsen_genutzt and cfg["offen"]:
        aus.append({"art": "basiszins", "link": "#/einstellungen/kalkulation/rechtswerte",
                    "text": (f"Seit dem {de_tag(cfg['offen'])} läuft ein neues Halbjahr für den Basiszinssatz (§ 247 BGB). Bitte den Satz der "
                             "Deutschen Bundesbank eintragen, auch wenn er gleich geblieben ist." if len(cfg["fehlend"]) == 1 else
                             f"Für {len(cfg['fehlend'])} Halbjahre seit dem {de_tag(cfg['offen'])} ist kein Basiszinssatz (§ 247 BGB) eingetragen. "
                             "Bitte die Sätze der Deutschen Bundesbank nachtragen, auch wenn sie gleich geblieben sind.")
                            + f" Bis dahin rechnet das Mahnwesen mit {de_zahl(cfg['basiszins'])} %."})
    ml = personal.mindestlohn_liste(e.get("mindestlohn"))
    if lohn_genutzt and int(ml[-1][0][:4]) < heute.year:
        aus.append({"art": "mindestlohn", "link": "#/einstellungen/kalkulation/rechtswerte",
                    "text": f"Für {heute.year} ist kein gesetzlicher Mindestlohn eingetragen. Die Lohnhinweise rechnen weiter mit "
                            f"{de_zahl(ml[-1][1])} € je Stunde (Stand {de_tag(ml[-1][0])}). Bitte den Satz für {heute.year} eintragen, "
                            "auch wenn er gleich geblieben ist."})
    return aus
