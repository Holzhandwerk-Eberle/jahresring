"""Jahresring – gemeinsame Grundfunktionen (Fehlerklasse der Schnittstelle, Datum, Zahlen, Text).
Ohne Abhängigkeit vom übrigen Programm, damit jedes Modul sie nutzen kann."""
import json
import math
import re
import secrets
import threading
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP


class ApiFehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


class Rueckfrage(ApiFehler):
    """Die Anfrage ist ungewöhnlich und wird erst nach einer Bestätigung ausgeführt: Der Browser zeigt den Text als Frage
    und schickt die Anfrage bei „Ja“ mit dem Schlüssel im Kopf „X-Bestaetigt“ noch einmal (siehe api() in index.html)."""
    def __init__(self, schluessel, text, knopf="Trotzdem ausführen"):
        super().__init__(text, 409)
        self.schluessel, self.knopf = schluessel, knopf


# Inhaltsschutz im Browser (Content-Security-Policy): Skripte laufen nur aus Programmdateien oder mit einer Einmal-Kennung,
# die der Server je Antwort neu vergibt. In vom Programm erzeugten Seiten steht dafür dieser geheime Platzhalter; „senden“
# ersetzt ihn. Eingeschleuster Text kann ihn nicht kennen – ein eingeschleustes <script> läuft deshalb nicht.
NONCE = "JR" + secrets.token_hex(16)
DRUCKEN_JS = ('document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-drucken]");if(b)window.print()});'
              'if(location.search.includes("drucken"))window.print()')


def skript(js):
    """Skript für eine vom Programm erzeugte Seite (mit Einmal-Kennung)."""
    return f'<script nonce="{NONCE}">{js}</script>'


AKTUELL = threading.local()   # je Anfrage: kann der Aufrufer Rückfragen zeigen, und welche hat er bestätigt (von app.py gesetzt)


def rueckfrage(schluessel, text, knopf="Trotzdem ausführen"):
    """Löst eine Rückfrage aus, solange sie für diese Anfrage nicht bestätigt wurde. Nur wenn der Aufrufer Rückfragen
    anzeigen kann (Büro-Programm, Kopf „X-Rueckfrage“); Scan-Seite, Stempeluhr und Hintergrundläufe buchen ohne."""
    if getattr(AKTUELL, "fragen", False) and schluessel not in (getattr(AKTUELL, "bestaetigt", None) or ()):
        raise Rueckfrage(schluessel, text, knopf)


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def kfm(x, n=2):
    """Kaufmännisch runden: halbe Einheiten weg von null (2,675 → 2,68; −0,125 → −0,13). Pythons round() rundet Gleitkommazahlen
    je nach interner Darstellung auch ab (round(2.675, 2) = 2.67) – bei Geldbeträgen fehlt dann ein Cent. Gleitkomma-Reste aus
    vorangegangenen Rechnungen (347,53499999999997 statt 347,535) werden vorher bereinigt. Nicht endliche Werte ergeben 0."""
    try:
        x = float(x or 0)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(x):
        return 0.0
    if abs(x) >= 1e15:   # jenseits der Genauigkeit einer Gleitkommazahl gibt es keine Nachkommastellen mehr zu runden
        return x
    m = 10 ** n
    y = abs(x) * m
    g = math.floor(y)
    rest = y - g
    if abs(rest - 0.5) > 1e-6:   # kein Grenzfall: schnell und eindeutig
        v = (g + (1 if rest > 0.5 else 0)) / m
        return -v if x < 0 and v else v
    # Grenzfall „halbe Einheit“: über die Dezimaldarstellung entscheiden
    return float(Decimal(repr(round(x, n + 6))).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP))


_ZAHL_REST = re.compile(r"[\s\u00a0\u202f€]|EUR", re.I)


def zahl_lesen(wert):
    """Zahl aus einer Eingabe: 12,5 · 1.234,56 · 1,234.56 · 12.5 · „40 €“. Liefert None, wenn es keine (endliche) Zahl ist.
    Ein einzelner Punkt gilt wie bisher als Dezimalpunkt (so kommen Zahlen aus der Oberfläche und aus Dateien an)."""
    if isinstance(wert, bool):
        return None
    if isinstance(wert, (int, float)):
        return float(wert) if math.isfinite(wert) else None
    t = _ZAHL_REST.sub("", str(wert or ""))
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(",", "") if t.rfind(".") > t.rfind(",") else t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def zahl(wert, typ):
    if wert in (None, ""):
        return 0
    v = zahl_lesen(wert)
    if v is None:
        raise ApiFehler(f"Ungültige Zahl: {str(wert)[:40]}")
    return typ(v)


class JsonFehler(ValueError):
    pass


def _json_zahl(text):
    v = float(text)
    if not math.isfinite(v):
        raise JsonFehler("Die Anfrage enthält eine Zahl außerhalb des gültigen Bereichs.")
    return v


def _json_konstante(name):
    raise JsonFehler("Die Anfrage enthält eine Zahl außerhalb des gültigen Bereichs.")


def json_lesen(roh):
    """Anfragedaten lesen: unendliche Zahlen, NaN und unpaarige Unicode-Ersatzzeichen werden abgelehnt (JsonFehler) – sie
    ließen sich speichern, aber nicht mehr als gültiges JSON ausgeben, und die betroffene Seite lüde dann für niemanden."""
    if isinstance(roh, (bytes, bytearray)):
        try:
            text = bytes(roh).decode("utf-8")
        except UnicodeDecodeError:
            raise JsonFehler("Die Anfrage enthält ungültige Zeichen (kein UTF-8).")
    else:
        text = roh
    daten = json.loads(text, parse_float=_json_zahl, parse_constant=_json_konstante)
    if "\\ud" in text or "\\uD" in text:   # nur dann lohnt der genaue Blick
        try:
            json.dumps(daten, ensure_ascii=False).encode("utf-8")
        except UnicodeEncodeError:
            raise JsonFehler("Die Anfrage enthält ungültige Zeichen.")
    return daten


def _endlich(x):
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: _endlich(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_endlich(v) for v in x]
    return x


def json_text(obj):
    """Antwort als JSON-Text. Steht in den Daten doch einmal eine nicht endliche Zahl (Altbestand), wird sie als null
    ausgegeben, damit der Browser die Antwort lesen kann."""
    try:
        return json.dumps(obj, ensure_ascii=False, allow_nan=False)
    except ValueError:
        return json.dumps(_endlich(obj), ensure_ascii=False, allow_nan=False)


def jl(s, standard):
    try:
        v = json.loads(s) if isinstance(s, str) and s else s
        return v if v is not None else standard
    except ValueError:
        return standard


def de(z, n=2):
    z = kfm(z, n)   # Anzeige wie gerechnet: kaufmännisch gerundet
    s = f"{abs(z):,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if z < 0 else "") + s


def de_datum(iso):
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso and len(iso) >= 10 else ""


def h(s):
    from html import escape
    return escape(str(s or ""))


def plus_tage(iso, tage):
    try:
        return date.fromordinal(date.fromisoformat(iso[:10]).toordinal() + int(tage or 0)).isoformat()
    except (ValueError, TypeError):
        return ""
