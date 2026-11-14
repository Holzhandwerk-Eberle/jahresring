"""Benutzer, Anmeldung, Sitzungen und Rechte."""
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from datetime import datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS benutzer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT UNIQUE NOT NULL,
    name TEXT DEFAULT '',
    pw_hash TEXT DEFAULT '',
    rolle TEXT DEFAULT 'mitarbeiter',
    rechte TEXT DEFAULT '{}',
    mitarbeiter_id INTEGER,
    aktiv INTEGER DEFAULT 1,
    angelegt TEXT, geaendert TEXT, letzter_login TEXT
);
CREATE TABLE IF NOT EXISTS sitzungen (
    token TEXT PRIMARY KEY,
    benutzer_id INTEGER NOT NULL,
    angelegt TEXT, zuletzt TEXT, ablauf TEXT, geraet TEXT DEFAULT ''
);
"""

BEREICHE = [
    ("start", "Startseite & Auswertungen"),
    ("kunden", "Kunden & Briefe"),
    ("auftraege", "Aufträge"),
    ("op", "Offene Posten & Mahnwesen"),
    ("lieferanten", "Lieferanten & Zahlungen"),
    ("material", "Material, Lager & Werkzeuge"),
    ("kalender", "Kalender"),
    ("personal", "Mitarbeiter, Zeiten & Lohn"),
    ("arbeitsschutz", "Arbeitsschutz"),
    ("einstellungen", "Einstellungen & Benutzer"),
]
STUFEN = {0: "kein Zugriff", 1: "nur ansehen", 2: "bearbeiten"}

ROLLEN = {
    "inhaber": {"name": "Inhaber", "text": "darf alles, auch Benutzer und Rechte verwalten",
                "rechte": {b: 2 for b, _ in BEREICHE}, "auftrag_reiter": "alle", "preise": True},
    "buero": {"name": "Büro", "text": "Kunden, Aufträge, Belege, Zahlungen, Material – ohne Personal und Einstellungen",
              "rechte": {"start": 2, "kunden": 2, "auftraege": 2, "op": 2, "lieferanten": 2, "material": 2, "kalender": 2,
                         "personal": 0, "arbeitsschutz": 2, "einstellungen": 0}, "auftrag_reiter": "alle", "preise": True},
    "werkstatt": {"name": "Werkstatt", "text": "nur Aufträge mit dem Reiter Werkstatt (Papiere, Zuschnitt, Dateien), Material und Kalender ansehen, ohne Preise",
                  "rechte": {"start": 0, "kunden": 0, "auftraege": 1, "op": 0, "lieferanten": 0, "material": 1, "kalender": 1,
                             "personal": 0, "arbeitsschutz": 1, "einstellungen": 0}, "auftrag_reiter": "werkstatt", "preise": False},
    "mitarbeiter": {"name": "Mitarbeiter", "text": "nur die eigene Zeiterfassung (Stempeluhr) und eigene Zeiten/Urlaub ansehen",
                    "rechte": {b: 0 for b, _ in BEREICHE}, "auftrag_reiter": "werkstatt", "preise": False},
    "eigen": {"name": "Eigene Rechte", "text": "Rechte je Bereich frei einstellen", "rechte": None, "auftrag_reiter": "alle", "preise": True},
}

# Was ein Benutzer im Kalender sieht (je Benutzer einstellbar, gilt für alle Rollen außer Inhaber):
#   typen = sichtbare Terminarten ([] = alle), nur_eigene = nur Termine, denen der eigene Mitarbeiter zugeteilt ist,
#   extern = Einträge aus dem verbundenen externen Kalender, abwesenheit = Abwesenheiten der Kollegen
KALENDER_STANDARD = {"typen": [], "nur_eigene": False, "extern": True, "abwesenheit": True}
KALENDER_ROLLE = {"werkstatt": {"extern": False}, "mitarbeiter": {"extern": False}}


def kalender_sicht(rolle, eigen):
    k = {**KALENDER_STANDARD, **KALENDER_ROLLE.get(rolle, {}), **((eigen or {}).get("kalender") or {})}
    return {"typen": [str(t) for t in k["typen"] or []], "nur_eigene": bool(k["nur_eigene"]), "extern": bool(k["extern"]), "abwesenheit": bool(k["abwesenheit"])}


SITZUNG_TAGE = 120
COOKIE = "jr_sitzung"

_fehlversuche = {}
_sperre = threading.Lock()
_lokal = threading.local()


class Fehler(Exception):
    def __init__(self, text, code=400):
        super().__init__(text)
        self.code = code


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def schema(con):
    con.executescript(SCHEMA)
    spalten = {r[1] for r in con.execute("PRAGMA table_info(benutzer)")}
    for sp, typ in (("email", "TEXT DEFAULT ''"), ("notfall_hash", "TEXT DEFAULT ''"), ("notfall_erstellt", "TEXT DEFAULT ''")):
        if sp not in spalten:
            con.execute(f"ALTER TABLE benutzer ADD COLUMN {sp} {typ}")
    # Einmalig: gespeicherte Sitzungs-Tokens durch ihren Hash ersetzen (bestehende Anmeldungen bleiben gültig)
    for r in con.execute("SELECT token FROM sitzungen WHERE token NOT LIKE 'h:%'").fetchall():
        con.execute("UPDATE OR REPLACE sitzungen SET token=? WHERE token=?", (token_hash(r[0]), r[0]))
    con.execute("CREATE TABLE IF NOT EXISTS pw_codes (benutzer_id INTEGER PRIMARY KEY, code_hash TEXT, ablauf TEXT, versuche INTEGER DEFAULT 0, "
                "angelegt TEXT)")


# ---------------------------------------------------------------- Passwort vergessen
CODE_MINUTEN = 15
CODE_VERSUCHE = 5


def _kurz_hash(s):
    return hashlib.sha256(("jahresring-reset|" + (s or "").strip().upper().replace("-", "").replace(" ", "")).encode("utf-8")).hexdigest()


def maskieren(adr):
    name, _, dom = (adr or "").partition("@")
    return (name[:1] + "•••" + (name[-1:] if len(name) > 2 else "") + "@" + dom) if dom else ""


def reset_adresse(con, b, firmen_adresse=""):
    """Mailadresse für „Passwort vergessen“: am Benutzer hinterlegt, sonst die des verknüpften Mitarbeiters,
    beim Inhaber zuletzt die Absenderadresse des Betriebs."""
    if (b["email"] or "").strip():
        return b["email"].strip()
    if b["mitarbeiter_id"]:
        m = con.execute("SELECT email FROM mitarbeiter WHERE id=?", (b["mitarbeiter_id"],)).fetchone()
        if m and (m["email"] or "").strip():
            return m["email"].strip()
    if b["rolle"] == "inhaber":
        return (firmen_adresse or "").strip()
    return ""


def reset_code_anlegen(con, login, ip=""):
    """Legt einen 6-stelligen Code an (15 Minuten gültig). Gibt (benutzer, code) zurück oder (None, None)."""
    login = (login or "").strip().lower()
    schluessel = f"reset|{ip}"
    if _gesperrt(schluessel) or _gesperrt(f"reset-login|{login}"):
        raise Fehler("Zu viele Anfragen. Bitte ein paar Minuten warten.", 429)
    _fehlversuch(schluessel)   # jede Anforderung zählt, damit niemand massenhaft Mails auslöst
    b = con.execute("SELECT * FROM benutzer WHERE lower(login)=? AND aktiv=1", (login,)).fetchone()
    if not b:
        time.sleep(0.4)
        return None, None
    alt = con.execute("SELECT angelegt FROM pw_codes WHERE benutzer_id=?", (b["id"],)).fetchone()
    if alt and (alt["angelegt"] or "") > (datetime.now() - timedelta(seconds=60)).isoformat(timespec="seconds"):
        raise Fehler("Es wurde gerade schon ein Code gesendet. Bitte eine Minute warten oder im Postfach nachsehen.", 429)
    code = f"{secrets.randbelow(1_000_000):06d}"
    con.execute("INSERT OR REPLACE INTO pw_codes (benutzer_id, code_hash, ablauf, versuche, angelegt) VALUES (?,?,?,0,?)",
                (b["id"], _kurz_hash(code), (datetime.now() + timedelta(minutes=CODE_MINUTEN)).isoformat(timespec="seconds"), jetzt()))
    return b, code


def reset_ausfuehren(con, login, code, neu, ip=""):
    """Setzt das Passwort mit Mail-Code oder (nur Inhaber) Notfallschlüssel neu. Gibt (benutzer, art) zurück."""
    login = (login or "").strip().lower()
    schluessel = f"reset-login|{login}"
    if _gesperrt(schluessel) or _gesperrt(f"reset-code|{ip}"):
        raise Fehler("Zu viele Fehlversuche. Bitte ein paar Minuten warten.", 429)
    b = con.execute("SELECT * FROM benutzer WHERE lower(login)=? AND aktiv=1", (login,)).fetchone()
    fehler = Fehler("Der Code stimmt nicht oder ist abgelaufen.")
    if not b:
        _fehlversuch(schluessel); _fehlversuch(f"reset-code|{ip}")
        time.sleep(0.4)
        raise fehler
    h = _kurz_hash(code)
    art = None
    r = con.execute("SELECT * FROM pw_codes WHERE benutzer_id=?", (b["id"],)).fetchone()
    if r and (r["ablauf"] or "") >= jetzt() and (r["versuche"] or 0) < CODE_VERSUCHE and hmac.compare_digest(r["code_hash"], h):
        art = "mail"
    elif b["rolle"] == "inhaber" and b["notfall_hash"] and hmac.compare_digest(b["notfall_hash"], h):
        art = "notfall"
    if not art:
        if r:
            con.execute("UPDATE pw_codes SET versuche=versuche+1 WHERE benutzer_id=?", (b["id"],))
            con.commit()   # Fehlversuch zählt auch, wenn die Anfrage danach mit Fehler endet
        _fehlversuch(schluessel); _fehlversuch(f"reset-code|{ip}")
        time.sleep(0.4)
        raise fehler
    pw_regeln(neu, b["rolle"])
    werte = {"pw_hash": pw_hash(neu), "geaendert": jetzt()}
    if art == "notfall":   # Notfallschlüssel gilt nur einmal
        werte.update({"notfall_hash": "", "notfall_erstellt": ""})
    con.execute(f"UPDATE benutzer SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [b["id"]])
    con.execute("DELETE FROM pw_codes WHERE benutzer_id=?", (b["id"],))
    con.execute("DELETE FROM sitzungen WHERE benutzer_id=?", (b["id"],))   # überall abmelden
    with _sperre:
        _fehlversuche.pop(schluessel, None)
    return b, art


def notfallschluessel_erzeugen(con, bid):
    roh = secrets.token_hex(8).upper()   # 16 Zeichen, in 4er-Gruppen angezeigt
    schl = "-".join(roh[i:i + 4] for i in range(0, 16, 4))
    con.execute("UPDATE benutzer SET notfall_hash=?, notfall_erstellt=? WHERE id=?", (_kurz_hash(schl), jetzt(), bid))
    return schl


# ---------------------------------------------------------------- Passwörter
def pw_hash(pw):
    salz = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salz), 200_000).hex()
    return f"pbkdf2${salz}${h}"


def pw_pruefen(pw, gespeichert):
    try:
        _, salz, h = gespeichert.split("$")
    except (ValueError, AttributeError):
        return False
    neu = hashlib.pbkdf2_hmac("sha256", (pw or "").encode("utf-8"), bytes.fromhex(salz), 200_000).hex()
    return hmac.compare_digest(neu, h)


def pw_regeln(pw, rolle):
    pw = pw or ""
    if rolle == "mitarbeiter":
        if len(pw) < 4:
            raise Fehler("Die PIN bzw. das Passwort muss mindestens 4 Zeichen haben.")
    elif len(pw) < 6:
        raise Fehler("Das Passwort muss mindestens 6 Zeichen haben.")


# ---------------------------------------------------------------- Rechte
def rechte_von(b):
    """Effektive Rechte eines Benutzers (dict) inkl. auftrag_reiter/preise."""
    rolle = b["rolle"] or "mitarbeiter"
    vorlage = ROLLEN.get(rolle, ROLLEN["mitarbeiter"])
    try:
        eigen = json.loads(b["rechte"] or "{}")
    except ValueError:
        eigen = {}
    if rolle == "inhaber":
        r = dict(vorlage["rechte"])
        return {"rolle": rolle, "bereiche": r, "auftrag_reiter": "alle", "preise": True, "inhaber": True, "kalender": dict(KALENDER_STANDARD)}
    if rolle == "eigen":
        r = {k: int((eigen.get("bereiche") or {}).get(k, 0)) for k, _ in BEREICHE}
        r["einstellungen"] = 0   # Einstellungen sind dem Inhaber vorbehalten
        return {"rolle": rolle, "bereiche": r, "auftrag_reiter": eigen.get("auftrag_reiter") or "alle",
                "preise": bool(eigen.get("preise", True)), "inhaber": False, "kalender": kalender_sicht(rolle, eigen)}
    return {"rolle": rolle, "bereiche": {**vorlage["rechte"], "einstellungen": 0}, "auftrag_reiter": vorlage["auftrag_reiter"],
            "preise": vorlage["preise"], "inhaber": False, "kalender": kalender_sicht(rolle, eigen)}


def oeffentlich(b):
    if not b:
        return None
    d = {k: b[k] for k in ("id", "login", "name", "rolle", "mitarbeiter_id", "aktiv", "letzter_login")}
    d["email"] = b["email"] if "email" in b.keys() else ""
    d["notfall_erstellt"] = b["notfall_erstellt"] if "notfall_erstellt" in b.keys() else ""
    d["rechte"] = rechte_von(b)
    d["rolle_name"] = ROLLEN.get(b["rolle"], {}).get("name", b["rolle"])
    try:
        d["eigen"] = json.loads(b["rechte"] or "{}")
    except ValueError:
        d["eigen"] = {}
    return d


# ---------------------------------------------------------------- aktueller Benutzer (je Anfrage-Thread)
def setze_aktuell(b):
    _lokal.benutzer = b
    _lokal.rechte = rechte_von(b) if b else None


def aktuell():
    return getattr(_lokal, "benutzer", None)


def aktuelle_rechte():
    return getattr(_lokal, "rechte", None)


def darf(bereich, stufe=1):
    r = aktuelle_rechte()
    if r is None:  # interne Aufrufe (PDF-Erzeugung, Hintergrund)
        return True
    if bereich == "einstellungen" and not r.get("inhaber"):
        return False   # Einstellungen sieht und ändert nur der Inhaber
    return r["bereiche"].get(bereich, 0) >= stufe


def ist_inhaber():
    r = aktuelle_rechte()
    return r is None or r.get("inhaber")


# ---------------------------------------------------------------- Sitzungen
def anzahl(con):
    return con.execute("SELECT COUNT(*) FROM benutzer").fetchone()[0]


def token_hash(token):
    """In der Datenbank steht nur der SHA-256 des Sitzungs-Tokens: Wer eine Sicherung oder die Datenbankdatei in die Hand
    bekommt, kann damit keine fremde Anmeldung übernehmen."""
    return "h:" + hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def sitzung_benutzer(con, token):
    if not token:
        return None
    token = token_hash(token)
    s = con.execute("SELECT * FROM sitzungen WHERE token=?", (token,)).fetchone()
    if not s or (s["ablauf"] or "") < jetzt():
        return None
    b = con.execute("SELECT * FROM benutzer WHERE id=? AND aktiv=1", (s["benutzer_id"],)).fetchone()
    if not b:
        return None
    # gleitend verlängern, höchstens einmal je Stunde schreiben
    if (s["zuletzt"] or "") < (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds"):
        con.execute("UPDATE sitzungen SET zuletzt=?, ablauf=? WHERE token=?",
                    (jetzt(), (datetime.now() + timedelta(days=SITZUNG_TAGE)).isoformat(timespec="seconds"), token))
    return b


def _gesperrt(schluessel):
    with _sperre:
        n, bis = _fehlversuche.get(schluessel, (0, 0))
        return bis > time.time()


def _fehlversuch(schluessel):
    with _sperre:
        n, bis = _fehlversuche.get(schluessel, (0, 0))
        n += 1
        _fehlversuche[schluessel] = (n, time.time() + min(300, 5 * 2 ** (n - 4)) if n >= 5 else 0)


def anmelden(con, login, pw, geraet="", ip=""):
    login = (login or "").strip().lower()
    schluessel = f"{login}|{ip}"
    if _gesperrt(schluessel):
        raise Fehler("Zu viele Fehlversuche. Bitte kurz warten und dann erneut versuchen.", 429)
    b = con.execute("SELECT * FROM benutzer WHERE lower(login)=? AND aktiv=1", (login,)).fetchone()
    if not b or not pw_pruefen(pw, b["pw_hash"]):
        _fehlversuch(schluessel)
        time.sleep(0.4)
        raise Fehler("Benutzername oder Passwort stimmt nicht.", 401)
    with _sperre:
        _fehlversuche.pop(schluessel, None)
    token = secrets.token_urlsafe(32)
    con.execute("INSERT INTO sitzungen (token, benutzer_id, angelegt, zuletzt, ablauf, geraet) VALUES (?,?,?,?,?,?)",
                (token_hash(token), b["id"], jetzt(), jetzt(), (datetime.now() + timedelta(days=SITZUNG_TAGE)).isoformat(timespec="seconds"),
                 (geraet or "")[:200]))
    con.execute("UPDATE benutzer SET letzter_login=? WHERE id=?", (jetzt(), b["id"]))
    con.execute("DELETE FROM sitzungen WHERE ablauf<?", (jetzt(),))
    return token, b


def abmelden(con, token):
    con.execute("DELETE FROM sitzungen WHERE token=?", (token_hash(token),))


# ---------------------------------------------------------------- Verwaltung
def _daten(con, d, alt=None):
    werte = {}
    if "login" in d:
        login = (d["login"] or "").strip().lower()
        if not login or any(c.isspace() for c in login):
            raise Fehler("Bitte einen Benutzernamen ohne Leerzeichen angeben.")
        r = con.execute("SELECT id FROM benutzer WHERE lower(login)=?", (login,)).fetchone()
        if r and (not alt or r["id"] != alt["id"]):
            raise Fehler(f"Den Benutzernamen „{login}“ gibt es schon.")
        werte["login"] = login
    if "name" in d:
        werte["name"] = (d["name"] or "").strip()
    if "email" in d:
        em = (d["email"] or "").strip()
        if em and ("@" not in em or " " in em):
            raise Fehler("Bitte eine gültige E-Mail-Adresse angeben.")
        werte["email"] = em
    if "rolle" in d:
        if d["rolle"] not in ROLLEN:
            raise Fehler("Unbekannte Rolle.")
        werte["rolle"] = d["rolle"]
    if "eigen" in d or "kalender" in d:
        try:
            bisher = json.loads((alt["rechte"] if alt else "") or "{}")
        except ValueError:
            bisher = {}
        if "eigen" in d:
            e = d["eigen"] or {}
            bisher.update({"bereiche": {k: max(0, min(2, int((e.get("bereiche") or {}).get(k, 0)))) for k, _ in BEREICHE},
                           "auftrag_reiter": "werkstatt" if e.get("auftrag_reiter") == "werkstatt" else "alle",
                           "preise": bool(e.get("preise", True))})
        if "kalender" in d:
            k = d["kalender"] or {}
            bisher["kalender"] = {"typen": [str(t)[:60] for t in (k.get("typen") or [])][:50], "nur_eigene": bool(k.get("nur_eigene")),
                                  "extern": bool(k.get("extern")), "abwesenheit": bool(k.get("abwesenheit"))}
        werte["rechte"] = json.dumps(bisher, ensure_ascii=False)
    if "mitarbeiter_id" in d:
        werte["mitarbeiter_id"] = int(d["mitarbeiter_id"]) if d["mitarbeiter_id"] else None
    if "aktiv" in d:
        werte["aktiv"] = 1 if d["aktiv"] else 0
    if d.get("passwort"):
        pw_regeln(d["passwort"], werte.get("rolle") or (alt["rolle"] if alt else "mitarbeiter"))
        werte["pw_hash"] = pw_hash(d["passwort"])
    return werte


def _inhaber_bleibt(con, ohne_id=None):
    n = con.execute("SELECT COUNT(*) FROM benutzer WHERE rolle='inhaber' AND aktiv=1 AND id<>?", (ohne_id or 0,)).fetchone()[0]
    if not n:
        raise Fehler("Es muss mindestens ein aktiver Benutzer mit der Rolle „Inhaber“ bleiben.")


def liste(con):
    aus = []
    for b in con.execute("SELECT b.*, m.vorname || ' ' || m.nachname AS mitarbeiter FROM benutzer b "
                         "LEFT JOIN mitarbeiter m ON m.id=b.mitarbeiter_id ORDER BY b.aktiv DESC, b.name, b.login"):
        d = oeffentlich(b)
        d["mitarbeiter"] = b["mitarbeiter"]
        d["sitzungen"] = con.execute("SELECT COUNT(*) FROM sitzungen WHERE benutzer_id=? AND ablauf>?", (b["id"], jetzt())).fetchone()[0]
        aus.append(d)
    return aus


def api(con, methode, teile, q, daten, token=None):
    d = daten or {}
    rid = int(teile[1]) if len(teile) > 1 and teile[1].isdigit() else None
    if methode == "GET" and len(teile) == 2 and teile[1] == "meta":
        return {"bereiche": BEREICHE, "stufen": STUFEN,
                "rollen": [{"id": k, "name": v["name"], "text": v["text"], "rechte": v["rechte"], "auftrag_reiter": v["auftrag_reiter"],
                            "preise": v["preise"]} for k, v in ROLLEN.items()]}
    if methode == "GET" and rid is None:
        return liste(con)
    if methode == "POST" and rid is None:
        if not d.get("passwort"):
            raise Fehler("Bitte ein Passwort bzw. eine PIN vergeben.")
        if d.get("rolle") == "inhaber" and not ist_inhaber():
            raise Fehler("Nur ein Inhaber kann weitere Inhaber anlegen.", 403)
        werte = _daten(con, {"rolle": "mitarbeiter", **d})
        if "login" not in werte:
            raise Fehler("Bitte einen Benutzernamen angeben.")
        werte["angelegt"] = werte["geaendert"] = jetzt()
        cur = con.execute(f"INSERT INTO benutzer ({','.join(werte)}) VALUES ({','.join('?' * len(werte))})", list(werte.values()))
        return oeffentlich(con.execute("SELECT * FROM benutzer WHERE id=?", (cur.lastrowid,)).fetchone())
    alt = con.execute("SELECT * FROM benutzer WHERE id=?", (rid,)).fetchone() if rid else None
    if rid and not alt:
        raise Fehler("Benutzer nicht gefunden.", 404)
    if methode == "PUT" and rid:
        if (alt["rolle"] == "inhaber" or d.get("rolle") == "inhaber") and not ist_inhaber():
            raise Fehler("Nur ein Inhaber kann Inhaber-Zugänge ändern.", 403)
        werte = _daten(con, d, alt)
        if alt["rolle"] == "inhaber" and (werte.get("rolle", "inhaber") != "inhaber" or werte.get("aktiv") == 0):
            _inhaber_bleibt(con, rid)
            if aktuell() and aktuell()["id"] == rid:
                # sich selbst die Inhaber-Rechte zu nehmen, wäre nicht rückgängig zu machen, sobald man die Seite verlässt
                raise Fehler("Die eigene Inhaber-Rolle lässt sich nicht selbst abgeben oder sperren. Das kann nur ein anderer Inhaber tun.")
        if werte:
            werte["geaendert"] = jetzt()
            con.execute(f"UPDATE benutzer SET {','.join(k + '=?' for k in werte)} WHERE id=?", list(werte.values()) + [rid])
        if "pw_hash" in werte or werte.get("aktiv") == 0:  # andere Geräte abmelden
            con.execute("DELETE FROM sitzungen WHERE benutzer_id=? AND token<>?", (rid, token_hash(token or "")))
        return oeffentlich(con.execute("SELECT * FROM benutzer WHERE id=?", (rid,)).fetchone())
    if methode == "POST" and rid and len(teile) == 3 and teile[2] == "abmelden":
        con.execute("DELETE FROM sitzungen WHERE benutzer_id=? AND token<>?", (rid, token_hash(token or "")))
        return {"ok": True}
    if methode == "DELETE" and rid:
        if alt["rolle"] == "inhaber":
            if not ist_inhaber():
                raise Fehler("Nur ein Inhaber kann Inhaber-Zugänge löschen.", 403)
            _inhaber_bleibt(con, rid)
        if aktuell() and aktuell()["id"] == rid:
            raise Fehler("Der eigene Zugang kann nicht gelöscht werden.")
        con.execute("DELETE FROM sitzungen WHERE benutzer_id=?", (rid,))
        con.execute("DELETE FROM benutzer WHERE id=?", (rid,))
        return {"ok": True}
    raise Fehler("Unbekannte Anfrage", 404)


# ---------------------------------------------------------------- Zuordnung API-Ressource → Bereich
# (Bereich, Mindeststufe für GET, Mindeststufe für Änderungen). Mehrere Bereiche = einer genügt.
RESSOURCEN = {
    "start": (["start"], 1, 2), "statistik": (["start"], 1, 2), "zahlungsstatistik": (["start", "lieferanten"], 1, 2),
    "kunden": (["kunden", "auftraege"], 1, 2), "briefe": (["kunden", "auftraege", "lieferanten"], 1, 2),
    "notizen": (["kunden", "auftraege", "lieferanten"], 1, 2), "anhaenge": (["kunden", "auftraege", "lieferanten"], 1, 2),
    "suche": (["kunden", "auftraege", "lieferanten", "material"], 1, 1),
    "auftraege": (["auftraege"], 1, 2), "positionen": (["auftraege"], 1, 2), "belege": (["auftraege"], 1, 2),
    "zuschnitt": (["auftraege"], 1, 2), "stunden": (["auftraege"], 1, 2), "naechste": (["auftraege", "kunden"], 1, 2),
    "kalkvorgaben": (["auftraege", "einstellungen"], 1, 2), "positionsvorlagen": (["auftraege", "einstellungen"], 1, 2), "cad": (["auftraege"], 1, 2), "mail": (["auftraege", "op", "kunden", "lieferanten"], 2, 2),
    "termine": (["kalender", "auftraege"], 1, 2), "wiedervorlagen": (["auftraege", "kunden"], 1, 2), "kalender": (["kalender"], 1, 2), "kalendertest": (["einstellungen"], 2, 2),
    "offeneposten": (["op", "auftraege"], 1, 2), "mahnwesen": (["op"], 1, 2), "mahnungen": (["op"], 1, 2),
    "zahlungseingaenge": (["op"], 1, 2), "bank": (["op"], 1, 2), "liquiditaet": (["op"], 2, 2),
    "lieferanten": (["lieferanten", "material"], 1, 2), "zahlungen": (["lieferanten"], 1, 2), "naechste_zahlung": (["lieferanten"], 1, 2),
    "eingang": (["lieferanten"], 2, 2), "rechnungspost": (["lieferanten"], 1, 2), "xml": (["lieferanten", "auftraege"], 1, 1),
    "material": (["material", "auftraege"], 1, 2), "materialsets": (["material", "auftraege"], 1, 2), "lager": (["material"], 1, 2),
    "auftragskosten": (["material", "auftraege"], 1, 2), "werkzeuge": (["material"], 1, 2), "preisimport": (["material"], 2, 2),
    "einstellungen": (None, 0, 2), "vorlagen": (None, 0, 2), "nummernkreise": (["einstellungen"], 1, 2),
    "version": (None, 0, 0), "fenster": (None, 0, 0),
    "benutzer": (["einstellungen"], 2, 2),
    "service": (["einstellungen"], 2, 2), "autostart": (["einstellungen"], 2, 2), "bildvarianten": (["auftraege"], 2, 2),
    "montage": (["auftraege"], 1, 1), "kundenunterschrift": (["auftraege"], 1, 1), "korrespondenz": (["kunden", "auftraege", "lieferanten"], 1, 2), "scan": (["auftraege", "material"], 1, 1), "newsletter": (["kunden"], 2, 2), "bautagebuch": (["auftraege"], 1, 1), "projekte": (["auftraege"], 1, 2), "leitstand": (["auftraege"], 1, 1), "reste": (["material", "auftraege"], 1, 1),
    "mitarbeiter": (["personal"], 1, 2), "zeiten": (["personal"], 1, 2), "abwesenheiten": (["personal"], 1, 2),
    "konten": (["personal"], 1, 2), "lohn": (["personal"], 1, 2), "monatsbeleg": (["personal"], 1, 2),
    "stempel": (None, 0, 0),  # eigene Zeiterfassung: prüft personal.py selbst
    "arbeitsschutz": (["arbeitsschutz"], 1, 2),
}
# Bei Auftragsrecht „nur Werkstatt“ erlaubte Auftrags-Unterseiten
WERKSTATT_UNTER = {None, "positionen", "papier", "zuschnitt", "zuschnittplan", "datei", "dateien", "projekt", "anhaenge", "notizen", "ordner"}


def pruefen(methode, teile, q, daten=None):
    """Wirft Fehler(403), wenn der aktuelle Benutzer das nicht darf."""
    r = aktuelle_rechte()
    if r is None or r.get("inhaber"):
        return
    res = teile[0] if teile else ""
    if res == "beenden":
        raise Fehler("Nur der Inhaber kann das Programm beenden.", 403)
    eintrag = RESSOURCEN.get(res)
    if eintrag is None:
        raise Fehler("Dafür fehlt die Berechtigung.", 403)
    bereiche, lesen, schreiben = eintrag
    stufe = lesen if methode == "GET" else schreiben
    # Werkstatt darf Status, Fertigungsbeginn und Lieferdatum eines Auftrags setzen
    werkstatt_status = (res == "auftraege" and methode == "PUT" and len(teile) == 2 and isinstance(daten, dict) and daten
                        and set(daten) <= {"status", "fertigung", "lieferung"} and r["bereiche"].get("auftraege", 0) >= 1)
    if werkstatt_status:
        return
    # Papiere erzeugen ist „lesen“
    if res == "auftraege" and methode == "POST" and len(teile) == 3 and teile[2] == "papier":
        stufe = 1
    if res in ("einstellungen", "vorlagen") and methode != "GET":
        raise Fehler("Einstellungen ändert nur der Inhaber.", 403)
    if res == "arbeitsschutz":
        unter = teile[1] if len(teile) > 1 else ""
        # Datenblätter und Herstellerunterlagen darf jeder Angemeldete öffnen (Zugang der Beschäftigten zum Sicherheitsdatenblatt)
        if methode == "GET" and unter == "datei":
            return
        # Unterschreiben bei einer Unterweisung und Eintragen ins Verbandbuch geht mit Leserecht (z. B. am Werkstatt-Tablet)
        if methode == "POST" and ((unter == "unterweisungen" and teile[-1] == "unterschreiben" and (daten or {}).get("rolle") != "unterweiser")
                                  or (unter == "verbandbuch" and len(teile) == 2)):
            stufe = 1
        # Material-Datenblätter und Gefahrstoffangaben pflegen auch Benutzer mit Recht „Material bearbeiten“
        if unter in ("dateien", "gefahrstoff", "ghs") and r["bereiche"].get("material", 0) >= (1 if methode == "GET" else 2):
            return
        # Das Verbandbuch ist vertraulich (§ 24 Abs. 6 DGUV Vorschrift 1): lesen und löschen nur der Inhaber
        if unter == "verbandbuch" and methode in ("GET", "DELETE"):
            raise Fehler("Das Verbandbuch sieht nur der Inhaber.", 403)
    if bereiche is not None and stufe > 0 and not any(r["bereiche"].get(b, 0) >= stufe for b in bereiche):
        raise Fehler("Dafür fehlt die Berechtigung.", 403)
    if res == "kunden" and r["bereiche"].get("kunden", 0) < 1 and not (len(teile) >= 2 and str(teile[1]).isdigit() and methode == "GET"):
        raise Fehler("Dafür fehlt die Berechtigung.", 403)  # Kundenliste nur mit Kundenrecht, einzelne Kunden über den Auftrag
    # Werkstatt (nur Reiter Werkstatt) legt keine Termine an und ändert keine
    if r.get("auftrag_reiter") == "werkstatt" and res == "termine" and methode != "GET":
        raise Fehler("Termine legt das Büro an (Werkstatt darf sie nur ansehen).", 403)
    if r.get("auftrag_reiter") == "werkstatt" and r["bereiche"].get("auftraege", 0) >= 1 and "auftraege" in (bereiche or []):
        # nur Werkstatt-Reiter: Belege, Positionsbearbeitung, OP usw. sperren
        if res in ("belege", "positionen", "stunden", "offeneposten", "mail", "kalkvorgaben", "positionsvorlagen", "cad", "naechste", "korrespondenz", "briefe", "projekte", "xml"):
            if not any(r["bereiche"].get(b, 0) >= 1 for b in bereiche if b != "auftraege"):
                raise Fehler("Dafür fehlt die Berechtigung (nur Werkstatt).", 403)
        if res == "auftraege" and len(teile) >= 3 and teile[2] not in WERKSTATT_UNTER:
            raise Fehler("Dafür fehlt die Berechtigung (nur Werkstatt).", 403)
        if res == "auftraege" and methode != "GET" and not (len(teile) == 3 and teile[2] == "papier"):
            raise Fehler("Dafür fehlt die Berechtigung (nur Werkstatt).", 403)


GELD = ("preis", "summe", "betrag", "netto", "brutto", "umsatz", "marge", "kosten", "lohn", "zuschlag", "rabatt", "ek_", "vk_",
        "stundensatz", "deckung", "gewinn", "skonto", "wert", "gk", "ust", "mwst", "verrechnung", "satz")


GELD_GENAU = {"ep", "gp", "wg", "ek", "vk", "db", "lnk", "offen", "saldo", "erloes", "ertrag", "bezahlt"}
GELD_TEIL = ("ep_", "_ep", "gp_", "_gp", "erloes", "ertrag", "_db", "db_")
KEIN_GELD = ("zeige",)   # Schalter „Preis anzeigen ja/nein“ sind keine Beträge


_BETRAG_IM_TEXT = re.compile(r"-?\d[\d.]*(?:,\d{1,2})?\s*€(?:\s*(?:brutto|netto))?")


def _ist_geld(schluessel):
    kl = str(schluessel).lower()
    return kl in GELD_GENAU or any(g in kl for g in GELD) or any(g in kl for g in GELD_TEIL)


def preise_entfernen(obj, geld=False):
    """Entfernt Geldbeträge aus einer API-Antwort (für Benutzer ohne Preis-Recht): Zahlen unter Schlüsseln, die nach Geld
    klingen, auch in darunter liegenden Listen/Verzeichnissen (z. B. Summen je Titel), und in eingebettetem JSON-Text
    (z. B. die Kalkulationsvorgaben eines Auftrags mit Löhnen und Stundensätzen)."""
    if isinstance(obj, dict):
        aus = {}
        for k, v in obj.items():
            if str(k).lower() in KEIN_GELD:
                aus[k] = v
                continue
            g = geld or _ist_geld(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and g:
                continue
            if isinstance(v, str) and "kalk" in str(k).lower() and v[:1] in "{[":
                try:
                    v = json.dumps(preise_entfernen(json.loads(v)), ensure_ascii=False)
                except ValueError:
                    pass
                aus[k] = v
                continue
            if k == "ereignisse" and isinstance(v, list):
                # vom Programm erzeugte Verlaufstexte (Historie) nennen Beträge im Text, z. B. „119,00 € brutto“ – dort ausblenden.
                # Frei eingegebene Texte bleiben unberührt, damit beim Bearbeiten nichts verloren geht.
                v = [{**x, "text": _BETRAG_IM_TEXT.sub("–", x["text"])} if isinstance(x, dict) and isinstance(x.get("text"), str) else x for x in v]
            aus[k] = preise_entfernen(v, g)
        return aus
    if isinstance(obj, list):
        return [x for x in (preise_entfernen(x, geld) for x in obj if not (geld and isinstance(x, (int, float)) and not isinstance(x, bool)))]
    return obj
