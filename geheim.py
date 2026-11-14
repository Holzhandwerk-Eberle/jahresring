"""Schutz von Zugangsdaten (Mail-Passwort) in der Datenbank.

Unter Windows wird das Passwort mit der Windows-Datenschutz-API (DPAPI, CryptProtectData) an das
Windows-Benutzerkonto gebunden verschlüsselt: Wer nur die Datenbankdatei oder eine Sicherung kopiert,
kann es nicht lesen. Auf anderen Systemen (Entwicklung, Test) bleibt der Wert unverändert.
Nach einer Rücksicherung auf einem anderen PC/Benutzerkonto muss das Passwort neu eingegeben werden.
"""
import base64
import os

PRAEFIX = "dpapi:"
_ENTROPIE = b"Jahresring-Zugangsdaten"


def _dpapi():
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    return ctypes, BLOB


def _blob(ctypes, BLOB, daten):
    puffer = ctypes.create_string_buffer(daten, len(daten))
    return BLOB(len(daten), ctypes.cast(puffer, ctypes.POINTER(ctypes.c_char))), puffer


def verschluesseln(text):
    if not text or str(text).startswith(PRAEFIX):
        return text
    api = _dpapi()
    if not api:
        return text
    ctypes, BLOB = api
    ein, p1 = _blob(ctypes, BLOB, str(text).encode("utf-8"))
    ent, p2 = _blob(ctypes, BLOB, _ENTROPIE)
    aus = BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(ein), "Jahresring", ctypes.byref(ent), None, None, 0x1, ctypes.byref(aus)):
        return text
    try:
        roh = ctypes.string_at(aus.pbData, aus.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(aus.pbData)
    return PRAEFIX + base64.b64encode(roh).decode("ascii")


def entschluesseln(wert):
    """Liefert den Klartext; bei nicht lesbarem Wert (anderer PC/Benutzer) einen leeren Text."""
    if not wert or not str(wert).startswith(PRAEFIX):
        return wert
    api = _dpapi()
    if not api:
        return ""
    ctypes, BLOB = api
    try:
        roh = base64.b64decode(str(wert)[len(PRAEFIX):])
    except ValueError:
        return ""
    ein, p1 = _blob(ctypes, BLOB, roh)
    ent, p2 = _blob(ctypes, BLOB, _ENTROPIE)
    aus = BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(ein), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(aus)):
        return ""
    try:
        return ctypes.string_at(aus.pbData, aus.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(aus.pbData)
