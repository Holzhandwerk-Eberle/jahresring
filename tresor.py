"""Verschlüsselung der Datensicherungen mit einem Sicherungskennwort.

Es werden nur Bausteine der Python-Standardbibliothek benutzt (keine Zusatzinstallation):
  * Schlüsselableitung aus dem Kennwort: scrypt (N=2^15, r=8, p=1), 64 Byte → 32 Byte Verschlüsselungs- und 32 Byte Prüfschlüssel
  * Verschlüsselung: Stromchiffre aus SHAKE-256 (SHA-3-Familie); der Schlüsselstrom für Block i ist
        SHAKE256(Verschlüsselungsschlüssel ‖ Nonce ‖ i als 8 Byte big-endian), Blockgröße 1 MiB, XOR mit dem Klartext
  * Unverfälschtheit: HMAC-SHA-256 über Kopf und Chiffrat (Encrypt-then-MAC), 32 Byte am Dateiende

Dateiaufbau (.jrs):  "JRSICH1\\0" (8) | KDF-Kennung (1, 1 = scrypt) | Salz (16) | Nonce (16) | Chiffrat | HMAC (32)

Der abgeleitete Schlüssel liegt auf diesem PC in daten/sicherung.schluessel, unter Windows an das Windows-Benutzerkonto
gebunden (DPAPI), damit die automatischen Sicherungen ohne Nachfrage verschlüsselt werden können. Auf einem anderen PC
wird das Kennwort gebraucht. Ohne Kennwort ist eine verschlüsselte Sicherung nicht lesbar – auch nicht für den Hersteller.
"""
import hashlib
import hmac
import json
import os
import secrets

import geheim

MAGIC = b"JRSICH1\0"
ENDUNG = ".jrs"
BLOCK = 1 << 20
KOPF = len(MAGIC) + 1 + 16 + 16
_cache = {}


class Fehler(Exception):
    pass


def ableiten(kennwort, salz):
    """Kennwort + Salz → 64 Byte Schlüsselmaterial (dauert absichtlich etwa eine Zehntelsekunde)."""
    k = (bytes(salz), kennwort)
    if k not in _cache:
        _cache.clear()
        _cache[k] = hashlib.scrypt(kennwort.encode("utf-8"), salt=bytes(salz), n=1 << 15, r=8, p=1, dklen=64, maxmem=1 << 27)
    return _cache[k]


def _xor(daten, strom):
    return (int.from_bytes(daten, "big") ^ int.from_bytes(strom, "big")).to_bytes(len(daten), "big")


def _strom(enc, nonce, i, n):
    return hashlib.shake_256(enc + nonce + i.to_bytes(8, "big")).digest(n)


def verschluesseln(quelle, ziel, schluessel, salz):
    """Datei quelle verschlüsselt nach ziel schreiben (erst .part, dann umbenennen)."""
    enc, mac = schluessel[:32], schluessel[32:]
    nonce = secrets.token_bytes(16)
    kopf = MAGIC + b"\x01" + bytes(salz) + nonce
    h = hmac.new(mac, kopf, hashlib.sha256)
    with open(quelle, "rb") as q, open(ziel + ".part", "wb") as z:
        z.write(kopf)
        i = 0
        while True:
            block = q.read(BLOCK)
            if not block:
                break
            c = _xor(block, _strom(enc, nonce, i, len(block)))
            h.update(c)
            z.write(c)
            i += 1
        z.write(h.digest())
        z.flush()
        os.fsync(z.fileno())
    os.replace(ziel + ".part", ziel)


def kopf_lesen(pfad):
    """Liefert (Salz, Nonce) oder wirft Fehler, wenn es keine Jahresring-Sicherung ist."""
    with open(pfad, "rb") as f:
        k = f.read(KOPF)
    if len(k) < KOPF or k[:8] != MAGIC or k[8] != 1:
        raise Fehler("Das ist keine verschlüsselte Jahresring-Sicherung.")
    return k[9:25], k[25:41]


def pruefen(pfad, schluessel):
    """True, wenn Schlüssel passt und die Datei unverändert ist."""
    try:
        groesse = os.path.getsize(pfad)
        if groesse < KOPF + 32:
            return False
        h = hmac.new(schluessel[32:], digestmod=hashlib.sha256)
        with open(pfad, "rb") as f:
            rest = groesse - 32
            while rest:
                b = f.read(min(BLOCK, rest))
                if not b:
                    return False
                h.update(b)
                rest -= len(b)
            return hmac.compare_digest(h.digest(), f.read(32))
    except OSError:
        return False


def entschluesseln(pfad, ziel, schluessel):
    """Erst die Unverfälschtheit prüfen, dann nach ziel entschlüsseln."""
    _, nonce = kopf_lesen(pfad)
    if not pruefen(pfad, schluessel):
        raise Fehler("Das Sicherungskennwort stimmt nicht oder die Sicherungsdatei ist beschädigt.")
    enc = schluessel[:32]
    rest = os.path.getsize(pfad) - KOPF - 32
    with open(pfad, "rb") as q, open(ziel, "wb") as z:
        q.seek(KOPF)
        i = 0
        while rest:
            c = q.read(min(BLOCK, rest))
            z.write(_xor(c, _strom(enc, nonce, i, len(c))))
            rest -= len(c)
            i += 1


# ---------------------------------------------------------------- Schlüssel auf diesem PC
def _datei(daten_ordner):
    return os.path.join(daten_ordner, "sicherung.schluessel")


def laden(daten_ordner):
    """(Schlüssel, Salz) dieses PCs oder None, wenn kein Kennwort gesetzt ist bzw. der Schlüssel hier nicht lesbar ist."""
    try:
        with open(_datei(daten_ordner), encoding="utf-8") as f:
            d = json.load(f)
        k = bytes.fromhex(geheim.entschluesseln(d["schluessel"]) or "")
        return (k, bytes.fromhex(d["salz"])) if len(k) == 64 else None
    except (OSError, ValueError, KeyError):
        return None


def aktiv(daten_ordner):
    return os.path.exists(_datei(daten_ordner))


def setzen(daten_ordner, kennwort):
    if len(kennwort or "") < 10:
        raise Fehler("Das Sicherungskennwort braucht mindestens 10 Zeichen.")
    salz = secrets.token_bytes(16)
    k = ableiten(kennwort, salz)
    p = _datei(daten_ordner)
    with open(p + ".part", "w", encoding="utf-8") as f:
        json.dump({"salz": salz.hex(), "schluessel": geheim.verschluesseln(k.hex()), "hinweis": "Schlüssel der verschlüsselten Datensicherungen – nicht löschen"}, f)
    os.replace(p + ".part", p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return k, salz


def kennwort_stimmt(daten_ordner, kennwort):
    s = laden(daten_ordner)
    if not s:
        return False
    return hmac.compare_digest(ableiten(kennwort or "", s[1]), s[0])


def entfernen(daten_ordner):
    try:
        os.remove(_datei(daten_ordner))
    except OSError:
        pass


def schluessel_fuer(pfad, daten_ordner, kennwort=None):
    """Passenden Schlüssel für eine .jrs-Datei: der gespeicherte dieses PCs (wenn das Salz passt) oder aus dem Kennwort."""
    salz, _ = kopf_lesen(pfad)
    s = laden(daten_ordner)
    if s and s[1] == salz:
        return s[0]
    if not kennwort:
        raise Fehler("KENNWORT_NOETIG")
    return ableiten(kennwort, salz)
