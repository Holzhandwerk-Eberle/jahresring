"""Eigene Zertifikate für https im Büronetz – ohne Zusatzinstallation, nur mit der Python-Standardbibliothek.

Jahresring erzeugt einmalig eine eigene kleine Zertifizierungsstelle („Jahresring Büro-CA“) und stellt damit das
Server-Zertifikat für den Büro-PC aus (Name, localhost und Netzwerkadresse). Auf Tablets und Handys wird nur das
CA-Zertifikat einmal als vertrauenswürdig eingerichtet; ändert sich die Adresse des PCs oder läuft das Server-Zertifikat
ab, stellt das Programm selbst ein neues aus, ohne dass an den Geräten etwas zu tun ist.

Sicherheit: Die CA ist per „Name Constraints“ auf localhost, den PC-Namen und private Netzadressen (10.x, 172.16–31.x,
192.168.x, 127.x) beschränkt – sie kann also keine Zertifikate für fremde Webseiten ausstellen. Der CA-Schlüssel liegt
unter Windows an das Benutzerkonto gebunden (DPAPI) und wird nicht in Sicherungen aufgenommen.

Verfahren: RSA 2048 Bit, Signatur SHA-256 mit RSA (PKCS #1 v1.5), X.509 v3.
"""
import base64
import hashlib
import ipaddress
import os
import secrets
import socket
import ssl
from datetime import datetime, timedelta, timezone

import geheim

ORDNER = "zertifikat"
# Nur für diese Netze darf die Büro-CA Zertifikate ausstellen: private Netze (RFC 1918), der PC selbst, automatische
# Adressen ohne Router und der Bereich 100.64/10, den VPN-Dienste wie Tailscale benutzen.
NETZE = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16", "100.64.0.0/10")]
SERVER_TAGE = 397          # Apple und Chrome nehmen höchstens 398 Tage an
ERNEUERN_VOR_TAGEN = 30


# ---------------------------------------------------------------- DER
def _tlv(tag, inhalt):
    n = len(inhalt)
    if n < 0x80:
        laenge = bytes([n])
    else:
        b = n.to_bytes((n.bit_length() + 7) // 8, "big")
        laenge = bytes([0x80 | len(b)]) + b
    return bytes([tag]) + laenge + inhalt


def _seq(*teile):
    return _tlv(0x30, b"".join(teile))


def _int(x):
    b = x.to_bytes(max(1, (x.bit_length() + 8) // 8), "big")   # führendes Nullbyte, wenn das oberste Bit gesetzt wäre
    return _tlv(0x02, b)


def _oid(text):
    t = [int(x) for x in text.split(".")]
    aus = bytes([40 * t[0] + t[1]])
    for x in t[2:]:
        teil = [x & 0x7F]
        x >>= 7
        while x:
            teil.append(0x80 | (x & 0x7F))
            x >>= 7
        aus += bytes(reversed(teil))
    return _tlv(0x06, aus)


def _name(cn, org="Jahresring"):
    def rdn(oid, wert):
        return _tlv(0x31, _seq(_oid(oid), _tlv(0x0C, wert.encode("utf-8"))))
    return _seq(rdn("2.5.4.10", org), rdn("2.5.4.3", cn))


def _zeit(t):
    return _tlv(0x17, t.strftime("%y%m%d%H%M%SZ").encode("ascii"))


def _ext(oid, wert, kritisch=False):
    return _seq(_oid(oid), *( [_tlv(0x01, b"\xff")] if kritisch else [] ), _tlv(0x04, wert))


SIG_ALG = _seq(_oid("1.2.840.113549.1.1.11"), _tlv(0x05, b""))   # sha256WithRSAEncryption
DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


# ---------------------------------------------------------------- RSA
_KLEINE = [p for p in range(3, 2000, 2) if all(p % q for q in range(3, int(p ** 0.5) + 1, 2))]


def _ist_prim(n, runden=24):
    if n < 2 or n % 2 == 0:
        return n == 2
    for p in _KLEINE:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(runden):   # Miller-Rabin mit zufälligen Basen
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _primzahl(bits, e):
    while True:
        p = secrets.randbits(bits) | (3 << (bits - 2)) | 1   # die beiden obersten Bits gesetzt, ungerade
        if (p - 1) % e and _ist_prim(p):
            return p


def rsa_schluessel(bits=2048):
    e = 65537
    while True:
        p, q = _primzahl(bits // 2, e), _primzahl(bits // 2, e)
        if p != q and abs(p - q).bit_length() > bits // 2 - 100:
            break
    n, phi = p * q, (p - 1) * (q - 1)
    d = pow(e, -1, phi)
    return {"n": n, "e": e, "d": d, "p": p, "q": q}


def _schluessel_pem(k):
    der = _seq(_int(0), _int(k["n"]), _int(k["e"]), _int(k["d"]), _int(k["p"]), _int(k["q"]),
               _int(k["d"] % (k["p"] - 1)), _int(k["d"] % (k["q"] - 1)), _int(pow(k["q"], -1, k["p"])))
    return _pem(der, "RSA PRIVATE KEY")


def _schluessel_aus_pem(text):
    der = base64.b64decode("".join(z for z in text.strip().splitlines() if not z.startswith("-----")))
    werte, pos = [], 0
    assert der[0] == 0x30
    pos = 2 + (der[1] & 0x7F if der[1] & 0x80 else 0)
    while pos < len(der):
        assert der[pos] == 0x02
        n = der[pos + 1]
        pos += 2
        if n & 0x80:
            m = n & 0x7F
            n = int.from_bytes(der[pos:pos + m], "big")
            pos += m
        werte.append(int.from_bytes(der[pos:pos + n], "big"))
        pos += n
    return {"n": werte[1], "e": werte[2], "d": werte[3], "p": werte[4], "q": werte[5]}


def _pem(der, art):
    b = base64.b64encode(der).decode("ascii")
    return f"-----BEGIN {art}-----\n" + "\n".join(b[i:i + 64] for i in range(0, len(b), 64)) + f"\n-----END {art}-----\n"


def _pub_bits(k):
    return _seq(_int(k["n"]), _int(k["e"]))


def _spki(k):
    return _seq(_seq(_oid("1.2.840.113549.1.1.1"), _tlv(0x05, b"")), _tlv(0x03, b"\x00" + _pub_bits(k)))


def _ski(k):
    return hashlib.sha1(_pub_bits(k)).digest()   # nur Kennung des Schlüssels (RFC 5280), keine Sicherheitsfunktion


def _signieren(tbs, k):
    laenge = (k["n"].bit_length() + 7) // 8
    t = DIGEST_INFO + hashlib.sha256(tbs).digest()
    em = b"\x00\x01" + b"\xff" * (laenge - len(t) - 3) + b"\x00" + t
    # CRT wäre schneller; hier zählt Einfachheit – signiert wird nur beim Ausstellen
    return pow(int.from_bytes(em, "big"), k["d"], k["n"]).to_bytes(laenge, "big")


def _zertifikat(subjekt, aussteller, pub, sig_schluessel, von, bis, erweiterungen):
    tbs = _seq(_tlv(0xA0, _int(2)), _int(int.from_bytes(secrets.token_bytes(16), "big") | 1 << 126), SIG_ALG, aussteller,
               _seq(_zeit(von), _zeit(bis)), subjekt, _spki(pub), _tlv(0xA3, _seq(*erweiterungen)))
    return _seq(tbs, SIG_ALG, _tlv(0x03, b"\x00" + _signieren(tbs, sig_schluessel)))


def _dns(name):
    return _tlv(0x82, name.encode("ascii"))


def ca_erzeugen(pc_name, firma=""):
    k = rsa_schluessel()
    name = _name(f"Jahresring Büro-CA {pc_name}"[:60], (firma or "Jahresring")[:60])
    jetzt = datetime.now(timezone.utc) - timedelta(hours=1)
    erlaubt = [_seq(_dns("localhost"))]
    for n in {pc_name.lower(), "fritz.box"}:
        if _name_ok(n):
            erlaubt.append(_seq(_dns(n)))
    for n in NETZE:
        erlaubt.append(_seq(_tlv(0x87, n.network_address.packed + n.netmask.packed)))
    ext = [_ext("2.5.29.19", _seq(_tlv(0x01, b"\xff"), _int(0)), True),          # CA, darf keine Unter-CAs ausstellen
           _ext("2.5.29.15", _tlv(0x03, b"\x01\x06"), True),                      # nur Zertifikate (und Sperrlisten) signieren
           _ext("2.5.29.30", _seq(_tlv(0xA0, b"".join(erlaubt))), True),          # nur lokale Namen und private Adressen
           _ext("2.5.29.14", _tlv(0x04, _ski(k)))]
    der = _zertifikat(name, name, k, k, jetzt, jetzt + timedelta(days=3650), ext)
    return k, der, name


def _name_ok(n):
    """PC-Namen dürfen unter Windows auch einen Unterstrich enthalten (z. B. BUERO_PC); Browser akzeptieren ihn im Zertifikat."""
    return bool(n) and n.isascii() and all(c.isalnum() or c in "-._" for c in n)


def pc_name_erlaubt(ca_der, pc_name):
    """Steht der PC-Name unter den erlaubten Namen der CA? Sonst würde ein Server-Zertifikat mit diesem Namen als Ganzes ungültig."""
    n = (pc_name or "").lower()
    return _name_ok(n) and _seq(_dns(n)) in ca_der


def server_erzeugen(ca_k, ca_name, pc_name, adressen, mit_name=True):
    k = rsa_schluessel()
    jetzt = datetime.now(timezone.utc) - timedelta(hours=1)
    san = [_dns("localhost")]
    n = pc_name.lower()
    if mit_name and _name_ok(n) and n != "localhost":
        san += [_dns(n)] + ([_dns(n + ".fritz.box")] if "." not in n else [])
    for a in sorted({"127.0.0.1", *adressen}):
        try:
            ip = ipaddress.ip_address(a)
        except ValueError:
            continue
        if ip.version == 4 and any(ip in n for n in NETZE):
            san.append(_tlv(0x87, ip.packed))
    ext = [_ext("2.5.29.19", _seq(), True),
           _ext("2.5.29.15", _tlv(0x03, b"\x05\xa0"), True),                      # Signatur + Schlüsselaustausch
           _ext("2.5.29.37", _seq(_oid("1.3.6.1.5.5.7.3.1"))),                    # nur als Webserver
           _ext("2.5.29.17", _seq(*san)),
           _ext("2.5.29.14", _tlv(0x04, _ski(k))),
           _ext("2.5.29.35", _seq(_tlv(0x80, _ski(ca_k))))]
    der = _zertifikat(_name(pc_name[:60] or "Jahresring"), ca_name, k, ca_k, jetzt, jetzt + timedelta(days=SERVER_TAGE), ext)
    return k, der


# ---------------------------------------------------------------- Ablage und Erneuerung
def _p(daten, name):
    return os.path.join(daten, ORDNER, name)


def _lesen(pfad, binaer=False):
    try:
        with open(pfad, "rb" if binaer else "r", **({} if binaer else {"encoding": "utf-8"})) as f:
            return f.read()
    except OSError:
        return None


def _schreiben(pfad, inhalt):
    with open(pfad + ".part", "wb" if isinstance(inhalt, bytes) else "w", **({} if isinstance(inhalt, bytes) else {"encoding": "utf-8"})) as f:
        f.write(inhalt)
    os.replace(pfad + ".part", pfad)
    try:
        os.chmod(pfad, 0o600)
    except OSError:
        pass


def _cert_info(pem_pfad):
    """Ablaufdatum und Namen eines Zertifikats (über die ssl-Bibliothek gelesen)."""
    try:
        d = ssl._ssl._test_decode_cert(pem_pfad)   # noqa: SLF001 – einzige Möglichkeit der Standardbibliothek, eine Datei zu lesen
        bis = datetime.fromtimestamp(ssl.cert_time_to_seconds(d["notAfter"]), timezone.utc)
        return bis, {v for art, v in d.get("subjectAltName", ())}
    except Exception:  # noqa: BLE001
        return None, set()


def fingerabdruck(daten):
    der = _lesen(_p(daten, "jahresring-ca.crt"), True)
    if not der:
        return ""
    h = hashlib.sha256(der).hexdigest().upper()
    return ":".join(h[i:i + 2] for i in range(0, len(h), 2))


def bereitstellen(daten, adressen, firma=""):
    """Sorgt für CA und gültiges Server-Zertifikat (legt an bzw. erneuert bei Bedarf). Liefert (cert.pem, key.pem, Meldung)."""
    os.makedirs(os.path.join(daten, ORDNER), exist_ok=True)
    pc = socket.gethostname().split(".")[0] or "Buero-PC"
    meldung = ""
    ca_roh, ca_der = _lesen(_p(daten, "ca.schluessel")), _lesen(_p(daten, "jahresring-ca.crt"), True)
    ca_k = None
    if ca_roh and ca_der:
        try:
            ca_k = _schluessel_aus_pem(geheim.entschluesseln(ca_roh) or "")
        except Exception:  # noqa: BLE001
            ca_k = None
    if not ca_k:
        if ca_der:
            meldung = ("Der Schlüssel der Büro-CA war auf diesem PC nicht lesbar (anderes Windows-Konto oder anderer PC). Es wurde eine neue "
                       "CA angelegt – das Zertifikat muss auf den Geräten neu eingerichtet werden.")
        ca_k, ca_der, _ = ca_erzeugen(pc, firma)
        _schreiben(_p(daten, "ca.schluessel"), geheim.verschluesseln(_schluessel_pem(ca_k)))
        _schreiben(_p(daten, "jahresring-ca.crt"), ca_der)
        _schreiben(_p(daten, "jahresring-ca.pem"), _pem(ca_der, "CERTIFICATE"))
        for alt in ("server.pem", "server.key"):
            if os.path.exists(_p(daten, alt)):
                os.remove(_p(daten, alt))
        meldung = meldung or "Büro-CA und Zertifikat wurden neu angelegt."
    cert, key = _p(daten, "server.pem"), _p(daten, "server.key")
    bis, namen = _cert_info(cert) if os.path.exists(cert) and os.path.exists(key) else (None, set())
    mit_name = pc_name_erlaubt(ca_der, pc)
    soll = {a for a in adressen if a and _im_netz(a)} | {"127.0.0.1", "localhost"} | ({pc.lower()} if mit_name and pc.lower() != "localhost" else set())
    if not bis or bis - datetime.now(timezone.utc) < timedelta(days=ERNEUERN_VOR_TAGEN) or not soll <= namen:
        # Aussteller-Name aus dem CA-Zertifikat übernehmen (Subject = 6. Element der TBS-Struktur)
        ca_name = _subjekt(ca_der)
        k, der = server_erzeugen(ca_k, ca_name, pc, [a for a in adressen if a], mit_name)
        _schreiben(key, _schluessel_pem(k))
        _schreiben(cert, _pem(der, "CERTIFICATE") + _pem(ca_der, "CERTIFICATE"))
        meldung = meldung or "Server-Zertifikat neu ausgestellt (neue Adresse oder Ablauf)."
    return cert, key, meldung


def namen(daten):
    """Namen und Adressen, für die das Server-Zertifikat gilt (zur Anzeige)."""
    eigen = eigenes(daten)
    _, n = _cert_info(eigen[0] if eigen else _p(daten, "server.pem"))
    return sorted(n, key=lambda x: (x[:1].isdigit(), x))


def eigenes(daten):
    """Eigenes Zertifikat des Betriebs (z. B. von einer öffentlichen Zertifizierungsstelle für eine eigene Domain):
    daten/zertifikat/eigen.pem (Zertifikat samt Zwischenzertifikaten) und eigen.key (privater Schlüssel, ohne Kennwort).
    Liefert (cert, key), wenn beide Dateien da sind, zueinander passen und das Zertifikat noch gilt, sonst None."""
    cert, key = _p(daten, "eigen.pem"), _p(daten, "eigen.key")
    if not (os.path.isfile(cert) and os.path.isfile(key)):
        return None
    try:
        kontext(cert, key)
    except (ssl.SSLError, OSError, ValueError):
        return None
    bis, _ = _cert_info(cert)
    return (cert, key) if bis and bis > datetime.now(timezone.utc) else None


def ca_verwerfen(daten):
    """Büro-CA und Server-Zertifikat verwerfen; bereitstellen() legt danach beides neu an (Geräte müssen neu eingerichtet werden).
    Die alten Dateien bleiben umbenannt liegen."""
    stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    for n in ("ca.schluessel", "jahresring-ca.crt", "jahresring-ca.pem", "server.pem", "server.key"):
        if os.path.exists(_p(daten, n)):
            os.replace(_p(daten, n), _p(daten, f"alt-{stempel}-{n}"))


def windows_vertrauen(daten, eintragen=True):
    """Die Büro-CA im Zertifikatsspeicher des angemeldeten Windows-Benutzers als vertrauenswürdig eintragen, damit der
    Browser an diesem PC die https-Adresse ohne Warnung öffnet. Windows fragt dabei einmal nach (Sicherheitswarnung mit
    Fingerabdruck). Liefert "vorhanden", "eingetragen", "abgelehnt" oder "" (kein Windows / nicht möglich)."""
    crt = _p(daten, "jahresring-ca.crt")
    der = _lesen(crt, True)
    if os.name != "nt" or not der:
        return ""
    import subprocess
    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    sha1 = hashlib.sha1(der).hexdigest()   # Windows benennt Zertifikate im Speicher über diesen Fingerabdruck
    try:
        if subprocess.run(["certutil", "-user", "-verifystore", "Root", sha1], capture_output=True, timeout=30, creationflags=flag).returncode == 0:
            return "vorhanden"
        if not eintragen:
            return "fehlt"
        r = subprocess.run(["certutil", "-user", "-addstore", "Root", crt], capture_output=True, timeout=300, creationflags=flag)
        return "eingetragen" if r.returncode == 0 else "abgelehnt"
    except (OSError, subprocess.SubprocessError):
        return ""


def _im_netz(a):
    try:
        ip = ipaddress.ip_address(a)
        return ip.version == 4 and any(ip in n for n in NETZE)
    except ValueError:
        return False


def _teile(der):
    """Zerlegt den Inhalt einer DER-Struktur in ihre Elemente (jeweils vollständig mit Kennung und Länge)."""
    aus, pos = [], 0
    while pos < len(der):
        n, kopf = der[pos + 1], 2
        if n & 0x80:
            m = n & 0x7F
            n, kopf = int.from_bytes(der[pos + 2:pos + 2 + m], "big"), 2 + m
        aus.append(der[pos:pos + kopf + n])
        pos += kopf + n
    return aus


def _inhalt(elem):
    n = elem[1]
    return elem[2 + (n & 0x7F):] if n & 0x80 else elem[2:]


def _subjekt(cert_der):
    tbs = _teile(_inhalt(cert_der))[0]
    return _teile(_inhalt(tbs))[5]


def kontext(cert, key):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cert, key)
    return ctx
