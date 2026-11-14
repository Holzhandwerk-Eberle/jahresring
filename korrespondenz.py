"""Korrespondenz je Kunde, Auftrag und Lieferant: E-Mails (Posteingang und Gesendet per IMAP), Anrufe, Briefe.

Der Posteingang wird nur gelesen (BODY.PEEK, nichts wird als gelesen markiert oder gelöscht). Zugeordnet werden nur Mails,
deren Absender bzw. Empfänger als E-Mail-Adresse bei einem Kunden oder Lieferanten hinterlegt ist."""
import email
import hashlib
import email.policy
import imaplib
import json
import os
import re
import ssl
import threading
import time
from datetime import date, datetime, timedelta
from email.utils import getaddresses, parsedate_to_datetime
from html import unescape

SCHEMA = """
CREATE TABLE IF NOT EXISTS korrespondenz (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    art TEXT NOT NULL, kunde_id INTEGER, lieferant_id INTEGER, auftrag_id INTEGER,
    datum TEXT, betreff TEXT DEFAULT '', text TEXT DEFAULT '', von TEXT DEFAULT '', an TEXT DEFAULT '',
    nummer TEXT DEFAULT '', dauer INTEGER DEFAULT 0, message_id TEXT, datei TEXT DEFAULT '', anhaenge TEXT DEFAULT '[]',
    benutzer TEXT DEFAULT '', angelegt TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS korrespondenz_mid ON korrespondenz(message_id) WHERE message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS korrespondenz_kunde ON korrespondenz(kunde_id, datum);
CREATE INDEX IF NOT EXISTS korrespondenz_auftrag ON korrespondenz(auftrag_id, datum);
"""
ARTEN = {"mail_ein": "E-Mail erhalten", "mail_aus": "E-Mail gesendet", "anruf_aus": "Anruf (ausgehend)",
         "anruf_ein": "Anruf (eingehend)", "brief": "Brief", "notiz": "Gesprächsnotiz"}
HILFE = {"daten": "", "einstellungen": None, "verbindung": None, "rechnung": None}
_lauf = {"aktiv": False, "letzter": None, "fehler": None, "neu": 0}
_sperre = threading.Lock()


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def schema(con):
    con.executescript(SCHEMA)


def eintragen(con, art, kunde_id=None, lieferant_id=None, auftrag_id=None, betreff="", text="", von="", an="",
              nummer="", dauer=0, message_id=None, datum=None, datei="", anhaenge=None, benutzer=""):
    try:
        cur = con.execute("INSERT INTO korrespondenz (art, kunde_id, lieferant_id, auftrag_id, datum, betreff, text, von, an, nummer, dauer, "
                          "message_id, datei, anhaenge, benutzer, angelegt) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (art, kunde_id, lieferant_id, auftrag_id, datum or jetzt(), betreff or "", (text or "")[:20000], von or "", an or "",
                           nummer or "", int(dauer or 0), message_id, datei or "", json.dumps(anhaenge or [], ensure_ascii=False), benutzer or "", jetzt()))
        return cur.lastrowid
    except Exception:  # noqa: BLE001  (doppelte Message-ID: schon erfasst)
        return None


def liste(con, q):
    sql = ("SELECT k.*, ku.kurzname AS kunde, l.kurzname AS lieferant, a.nummer AS auftragsnr FROM korrespondenz k "
           "LEFT JOIN kunden ku ON ku.id=k.kunde_id LEFT JOIN lieferanten l ON l.id=k.lieferant_id LEFT JOIN auftraege a ON a.id=k.auftrag_id WHERE 1=1")
    par = []
    for feld, spalte in (("kunde", "k.kunde_id"), ("lieferant", "k.lieferant_id"), ("auftrag", "k.auftrag_id")):
        if q.get(feld):
            sql += f" AND {spalte}=?"
            par.append(int(q[feld]))
    if q.get("ohne_auftrag"):
        sql += " AND k.auftrag_id IS NULL"
    if q.get("art"):
        sql += " AND k.art LIKE ?"
        par.append(q["art"] + "%")
    aus = []
    for r in con.execute(sql + " ORDER BY k.datum DESC, k.id DESC LIMIT 500", par):
        d = dict(r)
        d["artname"] = ARTEN.get(d["art"], d["art"])
        d["kurz"] = re.sub(r"\s+", " ", d.pop("text") or "")[:180]
        aus.append(d)
    return aus


def laden(con, kid):
    r = con.execute("SELECT * FROM korrespondenz WHERE id=?", (kid,)).fetchone()
    if not r:
        raise Fehler("Eintrag nicht gefunden", 404)
    d = dict(r)
    d["artname"] = ARTEN.get(d["art"], d["art"])
    try:
        d["anhaenge"] = json.loads(d["anhaenge"] or "[]")
    except ValueError:
        d["anhaenge"] = []
    return d


# ---------------------------------------------------------------- Posteingang (IMAP)
def _text_aus(msg):
    """Lesbarer Text einer Mail (text/plain bevorzugt, sonst HTML ohne Tags) und Namen der Anhänge."""
    text, html_text, anh = "", "", []
    for teil in msg.walk():
        if teil.is_multipart():
            continue
        dispo = (teil.get_content_disposition() or "")
        name = teil.get_filename()
        if dispo == "attachment" or (name and dispo != "inline"):
            if name:
                anh.append(name)
            continue
        typ = teil.get_content_type()
        try:
            inhalt = teil.get_content()
        except Exception:  # noqa: BLE001
            continue
        if typ == "text/plain" and not text:
            text = str(inhalt)
        elif typ == "text/html" and not html_text:
            html_text = str(inhalt)
    if not text and html_text:
        t = re.sub(r"(?is)<(script|style).*?</\1>", "", html_text)
        t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", t)
        text = unescape(re.sub(r"<[^>]+>", "", t))
    text = re.sub(r"\n{3,}", "\n\n", text.replace("\r", "")).strip()
    return text, anh


def _adressbuch(con):
    """E-Mail-Adresse (klein) → (kunde_id, lieferant_id)."""
    buch = {}
    for r in con.execute("SELECT id, email1, email2, email3, email4 FROM kunden"):
        for i in range(1, 5):
            a = (r[f"email{i}"] or "").strip().lower()
            if a:
                buch.setdefault(a, (r["id"], None))
    try:
        spalten = {c[1] for c in con.execute("PRAGMA table_info(lieferanten)")}
        felder = [f for f in ("email", "email1", "email2", "email3", "email4") if f in spalten]
        if felder:
            for r in con.execute(f"SELECT id, {', '.join(felder)} FROM lieferanten"):
                for f in felder:
                    for a in re.split(r"[,;\s]+", (r[f] or "").lower()):
                        if "@" in a:
                            buch.setdefault(a, (None, r["id"]))
    except Exception:  # noqa: BLE001
        pass
    return buch


ERLEDIGT = ("Erledigt", "Abgesagt", "Abgerechnet")


def _auftrag_finden(con, betreff, text, kunde_id):
    """Auftrag aus Betreff/Text (Auftragsnummer JJJJ-NNNN oder Belegnummer); sonst der einzige noch offene Auftrag
    des Kunden; sonst None (dann steht die Mail nur beim Kunden und lässt sich dort einem Auftrag zuordnen)."""
    for nr in re.findall(r"\b(20\d{2}-\d{4})(?:-[A-Z]{1,2}\d{2})?\b", (betreff or "") + " " + (text or "")[:3000]):
        r = con.execute("SELECT id FROM auftraege WHERE nummer=?" + (" AND kunde_id=?" if kunde_id else ""),
                        (nr, kunde_id) if kunde_id else (nr,)).fetchone()
        if r:
            return r["id"]
    if kunde_id:
        offen = con.execute(f"SELECT id FROM auftraege WHERE kunde_id=? AND IFNULL(status,'') NOT IN ({','.join('?' * len(ERLEDIGT))})",
                            (kunde_id, *ERLEDIGT)).fetchall()
        if len(offen) == 1:
            return offen[0]["id"]
    return None


def _zustand_datei():
    return os.path.join(HILFE["daten"], "posteingang.json")


def _zustand():
    try:
        with open(_zustand_datei(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _zustand_speichern(z):
    with open(_zustand_datei(), "w", encoding="utf-8") as f:
        json.dump(z, f)


def _ordner_liste(imap):
    namen = []
    typ, daten = imap.list()
    for zeile in daten or []:
        z = zeile.decode("utf-8", "replace") if isinstance(zeile, bytes) else str(zeile)
        m = re.match(r'\((?P<flags>[^)]*)\) "?(?P<trenner>[^"]*)"? (?P<name>.+)$', z)
        if m:
            namen.append((m.group("flags").lower(), m.group("name").strip()))
    return namen


def _gesendet(imap):
    namen = _ordner_liste(imap)
    for flags, n in namen:
        if "\\sent" in flags:
            return n
    for flags, n in namen:
        if "gesendet" in n.lower() or "sent" in n.lower():
            return n
    return None


def pruefen(con, cfg, tage_erstlauf=30, weitere=("Kundenkontakt",), nachlauf_tage=60, rechnung_ordner=()):
    """Liest neue Mails aus Posteingang und Gesendet und ordnet sie Kunden/Lieferanten/Aufträgen zu. Liefert Anzahl neuer Einträge.

    Eingehende Mails (Posteingang, weitere Ordner und die Rechnungsordner) gehen zusätzlich an HILFE["rechnung"]: Dort werden
    Rechnungsanhänge von Lieferanten (bzw. alle PDF/XML-Anhänge im Rechnungsordner) zum Buchen vorgemerkt."""
    if not cfg.get("imap_server") or not cfg.get("passwort"):
        raise Fehler("Für den Posteingang fehlt der IMAP-Server oder das Passwort (Einstellungen › E-Mail).")
    buch = _adressbuch(con)
    eigene = {(cfg.get("adresse") or "").lower(), (cfg.get("benutzer") or "").lower()}
    zustand = _zustand()
    neu = 0
    # Hashes der bekannten Adressen (keine Adressen im Klartext in der Zustandsdatei)
    bekannte = {hashlib.sha256(a.encode()).hexdigest()[:16]: a for a in buch}
    vorher = set(zustand.get("_adressen") or [])
    # beim ersten Lauf nach dem Update (Zustand vorhanden, aber noch ohne Adressliste) einmal alle Adressen nachsuchen
    neue_adressen = {a for h_, a in bekannte.items() if h_ not in vorher} if (vorher or any(k != "_adressen" for k in zustand)) else set()
    ablage = os.path.join(HILFE["daten"], "mails")
    os.makedirs(ablage, exist_ok=True)
    imap = imaplib.IMAP4_SSL(cfg["imap_server"].strip(), int(cfg.get("imap_port") or 993), ssl_context=ssl.create_default_context(), timeout=40)
    try:
        imap.login(cfg.get("benutzer") or cfg.get("adresse"), cfg["passwort"])
        # Posteingang, zusätzliche Ordner (z. B. „Kundenkontakt“, wohin Mails verschoben werden) und Gesendet.
        # Verschobene Mails behalten ihre Message-ID und werden deshalb nicht doppelt erfasst.
        namen = [n for _, n in _ordner_liste(imap)]

        def finden(wuensche):
            gef = []
            for w in wuensche or ():
                w = (w or "").strip().strip('"').lower()
                for n in namen:
                    kurz = re.split(r"[./]", n.strip('"'))[-1].lower()
                    if w and (kurz == w or n.strip('"').lower() == w) and n not in gef:
                        gef.append(n)
            return gef
        extra = finden(weitere)
        rg = [n for n in finden(rechnung_ordner) if n not in extra and n.upper() != "INBOX"]
        rg_alle = set(finden(rechnung_ordner))
        for ordner, richtung in [("INBOX", "ein")] + [(n, "ein") for n in extra + rg] + [(_gesendet(imap), "aus")]:
            if not ordner:
                continue
            im_rg = ordner in rg_alle
            typ, _ = imap.select(ordner, readonly=True)
            if typ != "OK":
                continue
            uv = (imap.response("UIDVALIDITY")[1] or [b""])[0]
            uv = uv.decode() if isinstance(uv, bytes) else str(uv or "")
            z = zustand.get(ordner) or {}
            if z.get("uidvalidity") != uv:
                z = {"uidvalidity": uv, "letzte": 0}
            if z["letzte"]:
                typ, daten = imap.uid("SEARCH", None, f"UID {int(z['letzte']) + 1}:*")
            else:
                seit = (date.today() - timedelta(days=tage_erstlauf)).strftime("%d-%b-%Y")
                typ, daten = imap.uid("SEARCH", None, "SINCE", seit)
            uids = [int(x) for x in (daten[0].split() if daten and daten[0] else []) if int(x) > int(z["letzte"] or 0)]
            # Adressen, die seit dem letzten Lauf neu bei Kunden/Lieferanten eingetragen wurden: deren Mails der letzten
            # Tage nachträglich suchen (sonst fehlen Mails, die vor dem Eintragen der Adresse kamen oder gesendet wurden)
            nach = set()
            # Einmalig nach Einführung der Rechnungserkennung: Mails der Lieferanten aus den letzten 30 Tagen nachlesen
            if z["letzte"] and richtung == "ein" and HILFE.get("rechnung") and not zustand.get("_rg_nachlauf"):
                seit = (date.today() - timedelta(days=tage_erstlauf)).strftime("%d-%b-%Y")
                for adr in sorted(a for a, (k_, l_) in buch.items() if l_)[:300]:
                    typ, d3 = imap.uid("SEARCH", None, "SINCE", seit, "FROM", f'"{adr}"')
                    if typ == "OK" and d3 and d3[0]:
                        nach.update(int(x) for x in d3[0].split() if int(x) <= int(z["letzte"]))
            if z["letzte"] and neue_adressen:
                seit = (date.today() - timedelta(days=nachlauf_tage)).strftime("%d-%b-%Y")
                for adr in sorted(neue_adressen)[:300]:
                    for feld in ("FROM", "TO", "CC"):
                        typ, d3 = imap.uid("SEARCH", None, "SINCE", seit, feld, f'"{adr}"')
                        if typ == "OK" and d3 and d3[0]:
                            nach.update(int(x) for x in d3[0].split() if int(x) <= int(z["letzte"]))
            for uid in sorted(nach) + uids[-500:]:
                neuer_uid = uid > int(z["letzte"] or 0)
                typ, d2 = imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
                roh = next((t[1] for t in d2 or [] if isinstance(t, tuple)), None)
                if neuer_uid:
                    z["letzte"] = max(int(z["letzte"] or 0), uid)
                if not roh:
                    continue
                msg = email.message_from_bytes(roh, policy=email.policy.default)
                absender = [a.lower() for _, a in getaddresses([str(msg.get("From") or "")]) if a]
                empf = [a.lower() for _, a in getaddresses([str(msg.get("To") or ""), str(msg.get("Cc") or "")]) if a]
                partner = empf if richtung == "aus" else absender
                treffer = next((buch[a] for a in partner if a in buch and a not in eigene), None)
                mid = str(msg.get("Message-ID") or "").strip() or f"<{ordner}-{uv}-{uid}@jahresring>"
                if richtung == "ein" and HILFE.get("rechnung"):
                    try:
                        HILFE["rechnung"](con, msg, mid, [a for a in absender if a not in eigene], im_rg, (treffer or (None, None))[1])
                    except Exception as f:  # noqa: BLE001
                        print("Rechnungsanhang nicht vorgemerkt:", f)
                if not treffer:
                    continue
                if con.execute("SELECT 1 FROM korrespondenz WHERE message_id=?", (mid,)).fetchone():
                    continue
                text, anh = _text_aus(msg)
                try:
                    zeit = parsedate_to_datetime(str(msg.get("Date"))).astimezone().replace(tzinfo=None).isoformat(timespec="seconds")
                except Exception:  # noqa: BLE001
                    zeit = jetzt()
                betreff = str(msg.get("Subject") or "")
                jahr = os.path.join(ablage, zeit[:4])
                os.makedirs(jahr, exist_ok=True)
                datei = os.path.join(jahr, f"{richtung}_{uv}_{uid}.eml")
                with open(datei, "wb") as f:
                    f.write(roh)
                kid, lid = treffer
                if eintragen(con, "mail_" + richtung, kunde_id=kid, lieferant_id=lid, auftrag_id=_auftrag_finden(con, betreff, text, kid),
                             betreff=betreff, text=text, von=", ".join(absender), an=", ".join(empf), message_id=mid, datum=zeit,
                             datei=os.path.relpath(datei, HILFE["daten"]), anhaenge=anh):
                    neu += 1
            zustand[ordner] = z
            con.commit()
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass
        zustand["_adressen"] = sorted(bekannte)
        if HILFE.get("rechnung"):
            zustand["_rg_nachlauf"] = True
        _zustand_speichern(zustand)
    return neu


def hintergrund_starten():
    """Prüft den Posteingang regelmäßig im Hintergrund (Intervall in den Einstellungen, 0 = aus)."""
    def schleife():
        time.sleep(60)
        while True:
            minuten = 15
            try:
                with HILFE["verbindung"]() as con:
                    e = HILFE["einstellungen"](con)
                    minuten = int(e.get("posteingang_minuten") or 0)
                    cfg = e.get("mail") or {}
                    if minuten > 0 and cfg.get("imap_server") and cfg.get("passwort"):
                        with _sperre:
                            _lauf["neu"] = pruefen(con, cfg, weitere=e.get("posteingang_ordner") or ["Kundenkontakt"],
                                                  rechnung_ordner=e.get("rechnung_ordner") or [])
                            _lauf["letzter"], _lauf["fehler"] = jetzt(), None
            except Exception as f:  # noqa: BLE001
                _lauf["letzter"], _lauf["fehler"] = jetzt(), str(f)
            time.sleep(max(5, minuten or 15) * 60)
    if not _lauf["aktiv"]:
        _lauf["aktiv"] = True
        threading.Thread(target=schleife, daemon=True).start()


def api(con, methode, teile, q, d, wer):
    d = d or {}
    kid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
    if methode == "GET" and teile[1:] == ["status"]:
        return dict(_lauf)
    if methode == "POST" and teile[1:] == ["pruefen"]:
        e = HILFE["einstellungen"](con)
        with _sperre:
            try:
                n = pruefen(con, e.get("mail") or {}, weitere=e.get("posteingang_ordner") or ["Kundenkontakt"],
                            rechnung_ordner=e.get("rechnung_ordner") or [])
            except (imaplib.IMAP4.error, OSError, ssl.SSLError) as f:
                raise Fehler(f"Posteingang konnte nicht gelesen werden: {f}")
            _lauf["letzter"], _lauf["fehler"], _lauf["neu"] = jetzt(), None, n
        return {"neu": n}
    if methode == "GET" and kid is None:
        return liste(con, q)
    if methode == "GET" and kid and len(teile) == 2:
        return laden(con, kid)
    if methode == "POST" and kid is None:
        art = d.get("art") or "notiz"
        if art not in ("anruf_aus", "anruf_ein", "notiz"):
            raise Fehler("Unbekannte Art.")
        if not (d.get("kunde_id") or d.get("lieferant_id")):
            raise Fehler("Kunde oder Lieferant fehlt.")
        nid = eintragen(con, art, kunde_id=d.get("kunde_id"), lieferant_id=d.get("lieferant_id"), auftrag_id=d.get("auftrag_id") or None,
                        betreff=d.get("betreff") or ARTEN[art], text=d.get("text") or "", nummer=d.get("nummer") or "",
                        dauer=d.get("dauer") or 0, benutzer=wer)
        return laden(con, nid)
    if methode == "PUT" and kid:
        e = laden(con, kid)
        werte = {}
        if "auftrag_id" in d:
            werte["auftrag_id"] = int(d["auftrag_id"]) if str(d["auftrag_id"] or "").isdigit() else None
        if werte:
            con.execute(f"UPDATE korrespondenz SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [kid])
        return laden(con, kid)
    if methode == "DELETE" and kid:
        raise Fehler("Einträge der Korrespondenz werden nicht gelöscht oder geändert (nur der Auftrag lässt sich zuordnen).")
    raise Fehler("Unbekannte Anfrage", 404)


def eml_pfad(con, kid):
    e = laden(con, kid)
    if not e["datei"]:
        return None
    p = os.path.normpath(os.path.join(HILFE["daten"], e["datei"]))
    if not p.startswith(os.path.normpath(HILFE["daten"])) or not os.path.isfile(p):
        return None
    return p
