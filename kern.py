"""Jahresring – gemeinsame Grundfunktionen (Fehlerklasse der Schnittstelle, Datum, Zahlen, Text).
Ohne Abhängigkeit vom übrigen Programm, damit jedes Modul sie nutzen kann."""
import json
from datetime import date, datetime


class ApiFehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


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
