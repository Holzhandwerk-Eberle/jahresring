"""Prüfung der Einstellungen beim Speichern (E4, E5): Art und Wertebereich je Einstellung an einer Stelle.

Grundsatz: Jede Einstellung muss von derselben Art sein wie ihre Vorgabe (Text, Schalter, Zahl, Liste, Verzeichnis). Für Zahlen
gelten Grenzen (ZAHLEN), für Auswahlfelder die zulässigen Werte (AUSWAHL), für verschachtelte Einstellungen ein Muster (MUSTER oder die
Vorgabe selbst) und für einige zusätzlich eine eigene Regel (REGELN). Was nicht passt, wird mit einer Meldung abgelehnt, die das Feld
nennt; gespeichert wird dann nichts. Zahlen, die als Text ankommen („7“, „2,5“), werden in Zahlen gewandelt.

Beim Lesen prüft art_passt() nur die Art: Steht aus früherer Zeit ein unbrauchbarer Wert in der Datenbank, gilt die Vorgabe, statt
dass eine Seite ausfällt."""
import json
import math
import re
from datetime import date

import kalkulation
import mahnwesen
import nachweis
import personal
import rechtswerte


class Fehler(ValueError):
    pass


GROESSE_MAX = 6_000_000   # Zeichen je Einstellung in der Ablage (Textbausteine und Positionsvorlagen dürfen groß sein)
TEXT_MAX = 400_000        # Zeichen je einzelnem Text
TIEFE_MAX = 12

# Zahlen: Mindestwert, Höchstwert, nur ganze Zahlen
ZAHLEN = {
    "angebot_gueltig_tage": (0, 365, True), "nachfass_tage": (0, 365, True), "anfrage_tage": (0, 365, True),
    "geburtstag_tage": (0, 90, True), "posteingang_minuten": (0, 1440, True),   # 0 Minuten = Posteingang nicht selbsttätig prüfen
    "kundennr_start": (1, 99_999_999, True), "lieferantennr_start": (1, 99_999_999, True),
    "etikett_breite": (10, 300, False), "etikett_hoehe": (10, 300, False), "unterschrift_hoehe": (5, 60, False),
    "zahlungsplan_rest": (0, 365, True), "tagesstunden": (0, 24, False), "seitenzahl_unten": (0, 60, False), "seitenzahl_rechts": (0, 150, False),
    "sitzung_tage_buero": (1, 365, True), "sitzung_tage_mitarbeiter": (1, 365, True), "frist_rechnung_jahre": (8, 10, True),
    "ziel_stundensatz": (0, 1000, False),
}
ZAHL_ALLGEMEIN = (-1_000_000_000, 1_000_000_000)

AUSWAHL = {"lohnanteil": ("privat", "alle", "nie"), "https": ("aus", "zusaetzlich", "nur"), "umsatz_basis": ("zahlung", "rechnung"),
           "lagerpreis_methode": ("mittel", "hoechst", "letzter")}

# Muster für Einstellungen, deren Vorgabe leer ist. Listen: Das erste Element ist das Muster für jedes Element. Verzeichnisse mit dem
# Schlüssel "*": Muster für jeden Wert. None: beliebige einfache Angabe.
MUSTER = {
    "kalk_vorgaben": kalkulation.KALK_VORGABEN,
    "mahnwesen": {"basiszinsen": [{"ab": "", "satz": 0.0}], "stufen": mahnwesen.STUFEN},
    "typ_kst": {"*": ""}, "ist_kategorien": {"*": ""}, "pdf_ordner": {"*": ""}, "status_automatik": {"*": {"*": ""}}, "material_gruppen": {"*": [""]},
    "feiertage_wahl": {"*": True}, "frei_wahl": {"*": True},
    "leitstand_status_map": {"*": ""},
    "mail_texte": {"*": {"*": ""}}, "beleg_texte": {"*": {"*": ""}},
    "bezug_eigen": [{"k": "", "name": "", "einheit": "", "quelle": ""}],
    "unterordner": [""],
    "google_kalender": [{"name": "", "url": "", "farbe": "", "aktiv": True}],
    "tage_eigene": [{}],
    "sollplaene": [{}],
    "taetigkeiten_katalog": [{}],
    "taetigkeit_listen": [{}],
    "steuersaetze": [{"ab": "", "regel": 0.0, "ermaessigt": 0.0}],
    "mindestlohn": [{"ab": "", "satz": 0.0}],
    "mail": {"smtp_port": 0, "imap_port": 0},
    "datev": {"konten": {"*": 0}},
    "verfahrensdoku": {}, "datenschutzdoku": {},
}
# Vorgaben, deren Elemente nicht alle gleich aufgebaut sind oder die leer sein dürfen: nur die Art der Elemente prüfen
NUR_ELEMENTART = {"pos_vorlagen", "taetigkeiten", "textbausteine", "wiedervorlage_regeln", "beleg_varianten"}
# Einstellungen, die auch „nichts“ (null) sein dürfen
LEER_ERLAUBT = {"taetigkeit_listen"}
# Texte, die Zahlen enthalten dürfen, obwohl im Muster eine Zahl steht (und umgekehrt), gibt es nicht: Zahl bleibt Zahl.

FARBE = re.compile(r"#[0-9a-fA-F]{3,8}")


def name(k):
    return nachweis.EINST_WERT.get(k) or nachweis.EINST_SCHALTER.get(k) or nachweis.EINST_FAKT.get(k) or nachweis.EINST_MASKE.get(k) or k


def _art(v):
    if isinstance(v, bool):
        return "schalter"
    if isinstance(v, (int, float)):
        return "zahl"
    if isinstance(v, str):
        return "text"
    if isinstance(v, list):
        return "liste"
    if isinstance(v, dict):
        return "verzeichnis"
    return "leer"


ART_NAME = {"schalter": "ein Schalter (ja/nein)", "zahl": "eine Zahl", "text": "ein Text", "liste": "eine Liste", "verzeichnis": "eine Gruppe von Angaben", "leer": "leer"}


def beim_lesen(k, wert, standard):
    """Prüfung beim Lesen aus der Datenbank → (brauchbar, Wert). Passt die Art des gespeicherten Werts nicht zur Vorgabe, gilt die
    Vorgabe. Eindeutiges wird übernommen: ein Zahlentext als Zahl, eine Zahl in einem Textfeld als Text."""
    muster = MUSTER.get(k, standard)
    if muster is None:
        return True, wert
    if wert is None:
        return k in LEER_ERLAUBT, wert
    a, b = _art(wert), _art(muster)
    if a == b:
        return not (a == "zahl" and isinstance(wert, float) and not math.isfinite(wert)), wert
    if b == "zahl" and a == "text":
        try:
            return True, _zahl(wert, k)
        except Fehler:
            return False, wert
    if b == "text" and a == "zahl":
        return True, str(wert)
    if b == "schalter" and a == "zahl" and wert in (0, 1):
        return True, bool(wert)
    return False, wert


def _zahl(wert, wo):
    """Zahl aus Zahl oder Zahlentext („7“, „2,5“); Schalter, leere Texte und Unendlich sind keine Zahlen."""
    if isinstance(wert, bool) or wert is None:
        raise Fehler(f"{wo}: Hier wird eine Zahl erwartet.")
    if isinstance(wert, str):
        t = wert.strip().replace(" ", "")
        if re.fullmatch(r"[+-]?\d{1,3}(\.\d{3})+(,\d+)?", t):
            t = t.replace(".", "")
        t = t.replace(",", ".")
        if not re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)", t):
            raise Fehler(f"{wo}: „{wert[:30]}“ ist keine Zahl.")
        wert = float(t)
        if wert == int(wert):
            wert = int(wert)
    if not isinstance(wert, (int, float)) or not math.isfinite(wert):
        raise Fehler(f"{wo}: Hier wird eine Zahl erwartet.")
    if not ZAHL_ALLGEMEIN[0] <= wert <= ZAHL_ALLGEMEIN[1]:
        raise Fehler(f"{wo}: Der Wert liegt außerhalb des sinnvollen Bereichs.")
    return wert


def _einfach(wert, wo, tiefe=0):
    """Beliebige einfache Angabe ohne Muster: nur Texte, endliche Zahlen, Schalter, Listen und Verzeichnisse in begrenzter Tiefe."""
    if tiefe > TIEFE_MAX:
        raise Fehler(f"{wo}: Die Angabe ist zu tief verschachtelt.")
    if wert is None or isinstance(wert, bool):
        return wert
    if isinstance(wert, (int, float)):
        if not math.isfinite(wert):
            raise Fehler(f"{wo}: Hier steht keine gültige Zahl.")
        return wert
    if isinstance(wert, str):
        if len(wert) > TEXT_MAX:
            raise Fehler(f"{wo}: Der Text ist zu lang (höchstens {TEXT_MAX} Zeichen).")
        return wert
    if isinstance(wert, list):
        return [_einfach(x, wo, tiefe + 1) for x in wert]
    if isinstance(wert, dict):
        if any(not isinstance(s, str) for s in wert):
            raise Fehler(f"{wo}: Die Angabe ist nicht lesbar.")
        return {s: _einfach(x, wo, tiefe + 1) for s, x in wert.items()}
    raise Fehler(f"{wo}: Die Angabe ist nicht lesbar.")


def _nach_muster(wert, muster, wo, tiefe=0, nur_art=False):
    """Wert gegen ein Muster prüfen und bereinigt zurückgeben (siehe Kopf des Moduls)."""
    if tiefe > TIEFE_MAX:
        raise Fehler(f"{wo}: Die Angabe ist zu tief verschachtelt.")
    if muster is None:
        return _einfach(wert, wo, tiefe)
    soll = _art(muster)
    if wert is None and tiefe and soll in ("liste", "verzeichnis", "zahl"):
        return [] if soll == "liste" else {} if soll == "verzeichnis" else None   # „nicht gesetzt“ innerhalb einer Liste oder Gruppe
    if soll == "schalter":
        if not isinstance(wert, bool):   # streng: 0, "" oder "false" schalten nichts aus – sie werden abgelehnt
            raise Fehler(f"{wo}: Hier wird ein Schalter (ja/nein) erwartet.")
        return wert
    if soll == "zahl":
        if wert == "" and tiefe:     # leeres Zahlenfeld innerhalb einer Liste: 0
            return 0
        return _zahl(wert, wo)
    if soll == "text":
        if wert is None:
            return ""
        if isinstance(wert, (int, float)) and not isinstance(wert, bool) and math.isfinite(wert) and tiefe:
            return str(wert)     # Zahl in einem Textfeld einer Liste (z. B. eine Nummer): als Text übernehmen
        if not isinstance(wert, str):
            raise Fehler(f"{wo}: Hier wird ein Text erwartet.")
        if len(wert) > TEXT_MAX:
            raise Fehler(f"{wo}: Der Text ist zu lang (höchstens {TEXT_MAX} Zeichen).")
        return wert
    if soll == "liste":
        if not isinstance(wert, list):
            raise Fehler(f"{wo}: Hier wird eine Liste erwartet.")
        if len(wert) > 5000:
            raise Fehler(f"{wo}: Die Liste ist zu lang.")
        if not muster:
            return [_einfach(x, wo, tiefe + 1) for x in wert]
        el = muster[0]
        if nur_art or (isinstance(el, dict) and not el):
            art = _art(el)
            for i, x in enumerate(wert):
                if _art(x) != art:
                    raise Fehler(f"{wo}: Der {i + 1}. Eintrag ist nicht lesbar.")
            return [_einfach(x, wo, tiefe + 1) for x in wert]
        return [_nach_muster(x, el, f"{wo}, {i + 1}. Eintrag", tiefe + 1) for i, x in enumerate(wert)]
    if soll == "verzeichnis":
        if not isinstance(wert, dict) or any(not isinstance(s, str) for s in wert):
            raise Fehler(f"{wo}: Die Angabe ist nicht lesbar.")
        if len(wert) > 20000:
            raise Fehler(f"{wo}: Zu viele Einträge.")
        aus = {}
        for s, x in wert.items():
            if s in muster:
                aus[s] = _nach_muster(x, muster[s], f"{wo} ({s})", tiefe + 1)
            elif "*" in muster:
                aus[s] = _nach_muster(x, muster["*"], f"{wo} ({s[:40]})", tiefe + 1)
            else:
                aus[s] = _einfach(x, wo, tiefe + 1)
        return aus
    return _einfach(wert, wo, tiefe)


def _tag(wert, wo):
    try:
        return date.fromisoformat(str(wert or "")[:10])
    except ValueError:
        raise Fehler(f"{wo}: „{str(wert)[:20]}“ ist kein gültiges Datum.") from None


def _in(x, lo, hi):
    """Liegt die Zahl im Bereich? Eine fehlende Angabe gilt als in Ordnung."""
    return x is None or (isinstance(x, (int, float)) and not isinstance(x, bool) and lo <= x <= hi)


def _regel_mahnwesen(m, wo):
    m = mahnwesen.umstellen(m)
    if len(m.get("stufen") or []) > len(mahnwesen.STUFEN):
        raise Fehler(f"{wo}: Es gibt höchstens {len(mahnwesen.STUFEN)} Mahnstufen.")
    for i, s in enumerate(m.get("stufen") or []):
        for feld, (lo, hi) in {"tage": (0, 365), "frist": (0, 365), "gebuehr": (0, 1000)}.items():
            if not _in(s.get(feld), lo, hi):
                raise Fehler(f"{wo}, {i + 1}. Stufe: {feld.capitalize()} muss zwischen {lo} und {hi} liegen.")
    roh = m.get("basiszinsen") or []
    for x in roh:
        t = _tag(x.get("ab"), f"{wo}, Basiszinssatz")
        if (t.month, t.day) not in ((1, 1), (7, 1)):
            raise Fehler(f"{wo}: Der Basiszinssatz ändert sich nur zum 1. Januar und zum 1. Juli; {t:%d.%m.%Y} ist kein solcher Stichtag.")
        if x.get("satz") is None or not _in(x.get("satz"), -5, 30):
            raise Fehler(f"{wo}: Der Basiszinssatz ab {t:%d.%m.%Y} muss zwischen −5 und 30 Prozent liegen.")
    m["basiszinsen"] = mahnwesen.eigene_saetze(roh)
    return m


def _regel_steuersaetze(liste, wo):
    for x in liste:
        t = _tag(x.get("ab"), wo)
        regel, erm = x.get("regel") or 0, x.get("ermaessigt") or 0
        if t.year < 2007 or not 0 < erm <= regel <= 40:
            raise Fehler(f"{wo}: Eintrag ab {t:%d.%m.%Y}: Der Regelsatz muss größer als 0 und höchstens 40 Prozent sein, der ermäßigte Satz "
                         "größer als 0 und höchstens so hoch wie der Regelsatz.")
    return rechtswerte.steuer_eigene(liste)


def _regel_mindestlohn(liste, wo):
    for x in liste:
        t = _tag(x.get("ab"), wo)
        if t.year < 2015 or not 5 <= (x.get("satz") or 0) <= 100:
            raise Fehler(f"{wo}: Eintrag ab {t:%d.%m.%Y}: Der Mindestlohn muss zwischen 5 und 100 € je Stunde liegen.")
    return personal.mindestlohn_eigene(liste)


def _regel_brief_layout(d, wo):
    for s, x in d.items():
        if isinstance(x, (int, float)) and not isinstance(x, bool) and not -50 <= x <= 400:
            raise Fehler(f"{wo}: Die Maße liegen zwischen −50 und 400 Millimetern.")
    return d


def _regel_zuschnitt_zugabe(d, wo):
    for s, x in d.items():
        if isinstance(x, (int, float)) and not isinstance(x, bool) and not 0 <= x <= 1000:
            raise Fehler(f"{wo}: Die Zugaben liegen zwischen 0 und 1000 Millimetern.")
    return d


def _regel_termin_typen(liste, wo):
    for t in liste:
        if t.get("farbe") and not FARBE.fullmatch(str(t["farbe"])):
            raise Fehler(f"{wo}: „{str(t['farbe'])[:20]}“ ist keine Farbe (erwartet wird zum Beispiel #7a8f9e).")
    return liste


def _regel_google_kalender(liste, wo):
    for k in liste:
        if k.get("farbe") and not FARBE.fullmatch(str(k["farbe"])):
            raise Fehler(f"{wo}: „{str(k['farbe'])[:20]}“ ist keine Farbe (erwartet wird zum Beispiel #4f7cba).")
        # Die Adresse wird beim Tippen gespeichert und deshalb erst beim Abruf geprüft (kalender.laden nimmt nur https und webcal)
    return liste


def _regel_kalk(d, wo):
    for feld in ("gk_material", "kleinmaterial", "wg"):
        if not _in(d.get(feld), -100, 1000):
            raise Fehler(f"{wo}: Zuschläge liegen zwischen −100 und 1000 Prozent.")
    for l in d.get("loehne") or []:
        if not _in(l.get("lohn"), 0, 1000) or not _in(l.get("lnk"), 0, 1000):
            raise Fehler(f"{wo}: Löhne und Lohnnebenkosten liegen zwischen 0 und 1000.")
    for k in d.get("kostenstellen") or []:
        if not _in(k.get("gk"), -100, 10000):
            raise Fehler(f"{wo}: Gemeinkostensätze der Kostenstellen liegen zwischen −100 und 10000 Prozent.")
    return d


def _regel_mail(d, wo):
    for feld in ("smtp_port", "imap_port"):
        if d.get(feld) not in (None, "", 0) and not _in(d[feld], 1, 65535):
            raise Fehler(f"{wo}: Der Port liegt zwischen 1 und 65535.")
    return d


REGELN = {"mahnwesen": _regel_mahnwesen, "steuersaetze": _regel_steuersaetze, "mindestlohn": _regel_mindestlohn, "brief_layout": _regel_brief_layout,
          "zuschnitt_zugabe": _regel_zuschnitt_zugabe, "termin_typen": _regel_termin_typen, "google_kalender": _regel_google_kalender,
          "kalk_vorgaben": _regel_kalk, "mail": _regel_mail}

# Schreibt nur das Programm selbst fort: Die Zählerstände der Nummernkreise haben einen eigenen Weg (dort lassen sie sich nur erhöhen)
# und werden über das Speichern der Einstellungen nie verändert.
NICHT_HIER = ("zaehler",)


def wert_pruefen(k, wert, standard):
    """Eine Einstellung prüfen und bereinigt zurückgeben; wirft Fehler mit einer Meldung, die das Feld nennt."""
    wo = name(k)
    muster = MUSTER.get(k, standard)
    if wert is None and (k in LEER_ERLAUBT or standard is None and k not in MUSTER):
        return None
    if k in ZAHLEN:
        lo, hi, ganz = ZAHLEN[k]
        z = _zahl(wert, wo)
        if ganz and z != int(z):
            raise Fehler(f"{wo}: Hier wird eine ganze Zahl erwartet.")
        if not lo <= z <= hi:
            raise Fehler(f"{wo}: Der Wert muss zwischen {lo} und {hi} liegen.")
        return int(z) if ganz else z
    if k in AUSWAHL:
        if wert not in AUSWAHL[k]:
            raise Fehler(f"{wo}: „{str(wert)[:30]}“ steht nicht zur Auswahl.")
        return wert
    neu = _nach_muster(wert, muster, wo, nur_art=k in NUR_ELEMENTART)
    if k in REGELN:
        neu = REGELN[k](neu, wo)
    if len(json.dumps(neu, ensure_ascii=False)) > GROESSE_MAX:
        raise Fehler(f"{wo}: Die Angabe ist zu groß.")
    return neu


def pruefen(daten, standards):
    """Alle bekannten Einstellungen aus daten prüfen → bereinigtes Verzeichnis. Unbekannte Schlüssel bleiben unverändert stehen
    (sie werden ohnehin nicht gespeichert); was nur das Programm fortschreibt (NICHT_HIER), fällt heraus."""
    if not isinstance(daten, dict):
        raise Fehler("Die Einstellungen sind nicht lesbar.")
    aus = {k: v for k, v in daten.items() if k not in NICHT_HIER}
    for k, v in aus.items():
        if k in standards:
            aus[k] = wert_pruefen(k, v, standards[k])
    return aus
