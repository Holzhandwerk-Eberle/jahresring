"""E-Mail-Versand über das eigene Postfach (SMTP) mit Ablage im Ordner „Gesendet“ (IMAP)."""
import imaplib
import mimetypes
import os
import re
import smtplib
import socket
import ssl
import time
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, formatdate

# Voreinstellungen bekannter Anbieter
ANBIETER = {
    "t-online.de": ("securemail.t-online.de", 465, "ssl", "secureimap.t-online.de"),
    "magenta.de": ("securemail.t-online.de", 465, "ssl", "secureimap.t-online.de"),
    "gmx.de": ("mail.gmx.net", 587, "starttls", "imap.gmx.net"),
    "gmx.net": ("mail.gmx.net", 587, "starttls", "imap.gmx.net"),
    "web.de": ("smtp.web.de", 587, "starttls", "imap.web.de"),
    "gmail.com": ("smtp.gmail.com", 465, "ssl", "imap.gmail.com"),
    "googlemail.com": ("smtp.gmail.com", 465, "ssl", "imap.gmail.com"),
    "ionos.de": ("smtp.ionos.de", 465, "ssl", "imap.ionos.de"),
    "strato.de": ("smtp.strato.de", 465, "ssl", "imap.strato.de"),
    "posteo.de": ("posteo.de", 465, "ssl", "posteo.de"),
    "mailbox.org": ("smtp.mailbox.org", 465, "ssl", "imap.mailbox.org"),
}


class MailFehler(Exception):
    pass


# liefert (bytes, mime-typ) des Firmenlogos oder None; wird von app.py gesetzt
LOGO = {"laden": lambda: None}


# Signatur {name, block, hinweis}; wird von app.py aus den Einstellungen geliefert und beim Senden angehängt
SIGNATUR = {"laden": lambda: None}


def _html_zeilen(t):
    from html import escape
    t = escape(t or "")
    t = re.sub(r"(https?://[^\s<]+|www\.[^\s<]+)", lambda m: f'<a href="{m.group(1) if m.group(1).startswith("http") else "https://" + m.group(1)}" style="color:#1a5fb4">{m.group(1)}</a>', t)
    t = re.sub(r"([\w.+-]+@[\w-]+\.[\w.-]+)", r'<a href="mailto:\1" style="color:#1a5fb4">\1</a>', t)
    return t.replace("\n", "<br>\n")


def signatur_text(sig):
    if not sig:
        return ""
    teile = [x for x in [(sig.get("name") or "").strip(), (sig.get("block") or "").strip(), (sig.get("hinweis") or "").strip()] if x]
    return "\n\n".join(teile)


def signatur_html(sig, logo_src=None):
    """Signatur wie aus dem Mailprogramm: Name, Logo, Firmenblock, Hinweistext (kleiner)."""
    if not sig:
        return ""
    aus = []
    if (sig.get("name") or "").strip():
        aus.append(f'<div style="font-size:14px;margin:0 0 10px">{_html_zeilen(sig["name"].strip())}</div>')
    if logo_src:
        aus.append(f'<div style="margin:0 0 12px"><img src="{logo_src}" alt="Logo" style="height:48px;width:auto;display:block"></div>')
    if (sig.get("block") or "").strip():
        aus.append(f'<div style="font-size:13px;line-height:1.3;margin:0 0 14px">{_html_zeilen(sig["block"].strip())}</div>')
    if (sig.get("hinweis") or "").strip():
        aus.append(f'<div style="font-size:12px;line-height:1.3;color:#222">{_html_zeilen(sig["hinweis"].strip())}</div>')
    return "".join(aus)


def html_aus_text(text, logo_cid=None, sig=None):
    """HTML-Fassung der Mail: Text mit Zeilenumbrüchen und anklickbaren Adressen, darunter die Signatur mit Logo."""
    logo_src = f"cid:{logo_cid[1:-1]}" if logo_cid else None
    sig_html = signatur_html(sig, logo_src) if sig else (f'<p style="margin-top:12px"><img src="{logo_src}" alt="Logo" style="height:48px"></p>' if logo_src else "")
    return ('<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.45;color:#222">'
            f'<div style="margin-bottom:10px">{_html_zeilen(text)}</div>{sig_html}</body></html>')


def server_bereinigen(name):
    """Tippfehler abfangen: Leerzeichen, „smtp://“, angehängter Port, Punkt am Ende."""
    n = (name or "").strip().lower()
    n = re.sub(r"^[a-z]+://", "", n)
    n = n.split("/")[0].split(":")[0].strip().strip(".")
    return n.replace(" ", "")


def vorschlag(adresse):
    dom = (adresse or "").split("@")[-1].lower().strip()
    return ANBIETER.get(dom)


def _verstaendlich(f):
    t = str(f)
    if isinstance(f, smtplib.SMTPAuthenticationError) or "authentication" in t.lower() or "535" in t:
        return ("Anmeldung beim Mailserver fehlgeschlagen. Benutzername oder Passwort stimmen nicht. "
                "Bei T-Online wird ein eigenes E-Mail-Passwort gebraucht (im Kundencenter unter E-Mail-Passwort), "
                "bei Gmail ein App-Passwort.")
    if isinstance(f, (socket.gaierror, ConnectionRefusedError)):
        return f"Mailserver nicht erreichbar ({t}). Servername und Port prüfen, Internetverbindung prüfen."
    if isinstance(f, (socket.timeout, TimeoutError)):
        return "Der Mailserver antwortet nicht (Zeitüberschreitung)."
    if isinstance(f, smtplib.SMTPRecipientsRefused):
        return "Der Mailserver lehnt die Empfängeradresse ab: " + ", ".join(f.recipients)
    if isinstance(f, ssl.SSLError):
        return f"Verschlüsselte Verbindung fehlgeschlagen ({t}). Passt der Port zur Verschlüsselung (465 = SSL, 587 = STARTTLS)?"
    return t


def nachricht_bauen(cfg, an, cc, betreff, text, anhaenge, bcc=None):
    absender = cfg.get("adresse") or cfg.get("benutzer")
    if not absender:
        raise MailFehler("In den Einstellungen ist keine Absenderadresse für E-Mails eingetragen.")
    m = EmailMessage()
    m["From"] = formataddr((cfg.get("name") or "", absender))
    m["To"] = ", ".join(an)
    if cc:
        m["Cc"] = ", ".join(cc)
    m["Subject"] = " ".join(str(betreff or "").split())   # Zeilenumbrüche im Betreff (z. B. aus eingefügtem Text) wären ein Fehler des Mailformats
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=absender.split("@")[-1])
    sig = None if cfg.get("_ohne_signatur") else SIGNATUR["laden"]()
    text = (text or "").rstrip()
    m.set_content(text + ("\n" + signatur_text(sig) if sig else "") + "\n")
    if cfg.get("html", True):
        logo = LOGO["laden"]() if cfg.get("logo_in_signatur", True) else None
        cid = make_msgid(domain="jahresring") if logo else None
        m.add_alternative(html_aus_text(text, cid, sig), subtype="html")
        if logo:
            haupt, _, unter = logo[1].partition("/")
            m.get_payload()[1].add_related(logo[0], maintype=haupt, subtype=unter, cid=cid, filename="logo." + unter.replace("jpeg", "jpg"))
    if bcc:
        m["Bcc"] = ", ".join(bcc)
    for name, daten, typ in anhaenge:
        typ = typ or mimetypes.guess_type(name)[0] or "application/octet-stream"
        haupt, _, unter = typ.partition("/")
        m.add_attachment(daten, maintype=haupt, subtype=unter, filename=name)
    return m


def adressen(text):
    teile = [x.strip() for x in re.split(r"[,;\s]+", text or "") if x.strip()]
    for x in teile:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", x):
            raise MailFehler(f"„{x}“ ist keine gültige E-Mail-Adresse.")
    return teile


def _ohne_bcc(roh):
    """Kopfzeile „Bcc“ entfernen: In der abgelegten Mail sollen die verdeckten Empfänger (Rundmail) nicht stehen."""
    kopf, trenner, rest = roh.partition(b"\r\n\r\n") if b"\r\n\r\n" in roh[:200000] else roh.partition(b"\n\n")
    return re.sub(rb"(?im)^Bcc:.*(?:\r?\n[ \t].*)*\r?\n?", b"", kopf + (b"\r\n" if b"\r\n" in trenner else b"\n")).rstrip(b"\r\n") + trenner + rest


def senden(cfg, an, cc, betreff, text, anhaenge, kopie_an_mich=False, bcc=None, ablage=None):
    """Schickt die Mail ab. Liefert {'gesendet': True, 'abgelegt': Ordner oder None, 'hinweis': ...}.
    ablage: Ordner, in dem die verschickte Mail vollständig (mit Anhängen) als .eml-Datei festgehalten wird; der Pfad steht
    dann in 'datei'. So lässt sich später genau das zeigen, was der Empfänger bekommen hat."""
    an, cc = adressen(an), adressen(cc)
    bcc = adressen(", ".join(bcc)) if isinstance(bcc, list) else adressen(bcc)
    if not an:
        raise MailFehler("Bitte eine Empfängeradresse angeben.")
    if not cfg.get("smtp_server") or not cfg.get("passwort"):
        raise MailFehler("Der E-Mail-Versand ist noch nicht eingerichtet (Einstellungen > E-Mail-Versand).")
    cfg = dict(cfg)
    for k in ("smtp_server", "imap_server"):
        cfg[k] = server_bereinigen(cfg.get(k))
    m = nachricht_bauen(cfg, an, cc, betreff, text, anhaenge, bcc)
    empfaenger = an + cc + bcc + ([cfg.get("adresse")] if kopie_an_mich and cfg.get("adresse") else [])
    port = int(cfg.get("smtp_port") or 465)
    modus = cfg.get("smtp_modus") or ("ssl" if port == 465 else "starttls")
    kontext = ssl.create_default_context()
    try:
        if modus == "ssl":
            s = smtplib.SMTP_SSL(cfg["smtp_server"], port, timeout=40, context=kontext)
        else:
            s = smtplib.SMTP(cfg["smtp_server"], port, timeout=40)
            s.ehlo()
            if modus == "starttls":
                s.starttls(context=kontext)
                s.ehlo()
        with s:
            s.login(cfg.get("benutzer") or cfg.get("adresse"), cfg["passwort"])
            s.send_message(m, to_addrs=empfaenger)
    except MailFehler:
        raise
    except socket.gaierror:
        raise MailFehler(f"Der Postausgangsserver „{cfg['smtp_server']}“ wurde nicht gefunden. Bitte den Servernamen prüfen "
                         f"(T-Online: securemail.t-online.de, GMX: mail.gmx.net, Web.de: smtp.web.de). "
                         f"Wenn er stimmt: Internetverbindung, VPN oder Virenscanner prüfen.")
    except Exception as f:  # noqa: BLE001
        raise MailFehler(_verstaendlich(f))
    ergebnis = {"gesendet": True, "abgelegt": None, "message_id": m["Message-ID"]}
    if ablage:
        try:
            jahr = os.path.join(ablage, datetime.now().strftime("%Y"))
            os.makedirs(jahr, exist_ok=True)
            pfad = os.path.join(jahr, f"aus_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{os.urandom(4).hex()}.eml")
            with open(pfad, "wb") as f:
                f.write(_ohne_bcc(m.as_bytes()))
            ergebnis["datei"] = pfad
        except OSError as f:
            ergebnis["hinweis"] = "Die Mail wurde verschickt, ließ sich aber nicht im Programm ablegen: " + str(f)[:120]
    if cfg.get("gesendet_ablegen", True) and cfg.get("imap_server"):
        try:
            ergebnis["abgelegt"] = in_gesendet_ablegen(cfg, m)
        except Exception as f:  # noqa: BLE001
            ergebnis["hinweis"] = "Die Mail wurde verschickt, aber nicht im Ordner „Gesendet“ abgelegt: " + _verstaendlich(f)
    return ergebnis


def _gesendet_ordner(imap):
    typ, daten = imap.list()
    namen = []
    for zeile in daten or []:
        z = zeile.decode("utf-8", "replace") if isinstance(zeile, bytes) else str(zeile)
        m = re.match(r'\((?P<flags>[^)]*)\)\s+(?:"[^"]*"|NIL)\s+(?P<name>.+)$', z)
        if not m:
            continue
        name = m.group("name").strip()
        if "\\sent" in m.group("flags").lower():
            return name
        namen.append(name)
    for wunsch in ('"Gesendet"', "Gesendet", '"INBOX.Gesendet"', '"Sent"', "Sent", '"Gesendete Objekte"',
                   '"Sent Items"', '"INBOX.Sent"', '"[Gmail]/Gesendet"', '"[Gmail]/Sent Mail"'):
        if wunsch in namen:
            return wunsch
    for n in namen:
        if "gesendet" in n.lower() or "sent" in n.lower():
            return n
    return None


def in_gesendet_ablegen(cfg, m):
    imap = imaplib.IMAP4_SSL(cfg["imap_server"], int(cfg.get("imap_port") or 993),
                             ssl_context=ssl.create_default_context(), timeout=30)
    try:
        imap.login(cfg.get("benutzer") or cfg.get("adresse"), cfg["passwort"])
        ordner = _gesendet_ordner(imap)
        if not ordner:
            raise MailFehler("Ordner „Gesendet“ im Postfach nicht gefunden.")
        typ, _ = imap.append(ordner, "\\Seen", imaplib.Time2Internaldate(time.time()), m.as_bytes())
        if typ != "OK":
            raise MailFehler("Der Server hat die Ablage abgelehnt.")
        return ordner.strip('"')
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass
