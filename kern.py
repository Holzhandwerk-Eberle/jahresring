"""Jahresring – gemeinsame Grundfunktionen (Fehlerklasse der Schnittstelle, Datum, Zahlen, Text).
Ohne Abhängigkeit vom übrigen Programm, damit jedes Modul sie nutzen kann."""
import json
import secrets
import threading
from datetime import date, datetime


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


def zahl(wert, typ):
    if wert in (None, ""):
        return 0
    if isinstance(wert, str):
        wert = wert.replace(".", "").replace(",", ".") if "," in wert else wert
    try:
        return typ(float(wert))
    except ValueError:
        raise ApiFehler(f"Ungültige Zahl: {wert}")


def jl(s, standard):
    try:
        v = json.loads(s) if isinstance(s, str) and s else s
        return v if v is not None else standard
    except ValueError:
        return standard


def de(z, n=2):
    s = f"{abs(z):,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if z < 0 and round(abs(z), n) else "") + s


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
