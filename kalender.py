# -*- coding: utf-8 -*-
"""
Kalender: Einlesen externer Kalender (Google über die private iCal-Adresse) und Export eigener Termine als .ics
Nur Standardbibliothek.
"""
import re
import ssl
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

_cache = {}  # url -> (zeitpunkt, ereignisse)
CACHE_SEKUNDEN = 600


def _entfalten(text):
    return re.sub(r"\r?\n[ \t]", "", text).replace("\r\n", "\n").split("\n")


def _unescape(s):
    return s.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _zeit(wert, params):
    """Liefert (datetime naiv in lokaler Zeit, ganztags?)."""
    wert = wert.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", wert):
        return datetime.strptime(wert[:8], "%Y%m%d"), True
    if wert.endswith("Z"):
        utc = datetime.strptime(wert[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        return utc.astimezone().replace(tzinfo=None), False
    dt = datetime.strptime(wert[:15], "%Y%m%dT%H%M%S")
    tzid = params.get("TZID")
    if tzid:
        try:
            from zoneinfo import ZoneInfo
            return dt.replace(tzinfo=ZoneInfo(tzid)).astimezone().replace(tzinfo=None), False
        except Exception:  # noqa – ohne Zeitzonendaten (Windows) als Ortszeit nehmen
            pass
    return dt, False


def _zeile(z):
    if ":" not in z:
        return None, {}, ""
    kopf, wert = z.split(":", 1)
    teile = kopf.split(";")
    params = {}
    for p in teile[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.upper()] = v.strip('"')
    return teile[0].upper(), params, wert


def _dauer(s):
    m = re.fullmatch(r"([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", s.strip())
    if not m:
        return timedelta(0)
    w, d, h, mi, se = (int(x or 0) for x in m.groups()[1:])
    return timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=se)


WTAGE = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def _monatstage(jahr, monat, tage_regel, monatstage, setpos, vorgabe_tag):
    """Tage eines Monats laut BYDAY (auch „2TU“, „-1FR“), BYMONTHDAY (auch negativ) und BYSETPOS; sonst der Tag des Serienbeginns."""
    import calendar
    letzter = calendar.monthrange(jahr, monat)[1]
    tage = None
    if tage_regel:
        tage = set()
        for nr, wt in tage_regel:
            treffer = [t for t in range(1, letzter + 1) if date(jahr, monat, t).weekday() == wt]
            if nr:
                if -len(treffer) <= nr <= len(treffer) and nr != 0:
                    tage.add(treffer[nr - 1 if nr > 0 else nr])
            else:
                tage.update(treffer)
    if monatstage:
        mt = {t if t > 0 else letzter + 1 + t for t in monatstage}
        mt = {t for t in mt if 1 <= t <= letzter}
        tage = mt if tage is None else tage & mt
    if tage is None:
        tage = {vorgabe_tag} if vorgabe_tag <= letzter else set()
    tage = sorted(tage)
    if setpos:
        tage = sorted({tage[p - 1 if p > 0 else p] for p in setpos if p != 0 and -len(tage) <= p <= len(tage)})
    return tage


def _wiederholungen(start, regel, von, bis, max_n=20000, lokal=None):
    """RRULE-Auswertung: DAILY/WEEKLY/MONTHLY/YEARLY mit INTERVAL, COUNT, UNTIL, BYDAY (auch „jeden 2. Dienstag“, „letzter Freitag“),
    BYMONTHDAY (auch −1 = Monatsletzter), BYMONTH und BYSETPOS. „lokal“ rechnet einen Serientermin in Ortszeit um
    (Serien, deren Beginn in Weltzeit angegeben ist, wandern mit der Sommerzeit)."""
    r = dict(p.split("=", 1) for p in regel.split(";") if "=" in p)
    freq = r.get("FREQ", "")
    lokal = lokal or (lambda x: x)
    try:
        intervall = max(1, int(r.get("INTERVAL", "1") or 1))
        anzahl = int(r["COUNT"]) if "COUNT" in r else None
        tage_regel = []
        for x in r.get("BYDAY", "").split(","):
            m = re.fullmatch(r"([+-]?\d+)?(MO|TU|WE|TH|FR|SA|SU)", x.strip())
            if m:
                tage_regel.append((int(m.group(1) or 0), WTAGE.index(m.group(2))))
        zahlen = lambda k: [int(x) for x in r.get(k, "").split(",") if re.fullmatch(r"[+-]?\d+", x.strip())]
        monatstage, monate, setpos = zahlen("BYMONTHDAY"), [m for m in zahlen("BYMONTH") if 1 <= m <= 12], zahlen("BYSETPOS")
    except ValueError:
        return [start]
    bis_regel = None
    if "UNTIL" in r:
        try:
            bis_regel = _zeit(r["UNTIL"], {})[0]
            if len(r["UNTIL"].strip()) == 8:   # nur Datum: der ganze Tag zählt noch
                bis_regel = bis_regel.replace(hour=23, minute=59, second=59)
        except ValueError:
            bis_regel = None
    if freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        return [start]
    zeit = lambda d: datetime(d.year, d.month, d.day, start.hour, start.minute, start.second)
    wochentage = sorted({wt for _, wt in tage_regel})
    # Ohne COUNT gleich in die Nähe des gesuchten Zeitraums springen (alte Serien liefen sonst ins Leere)
    i = 0
    if anzahl is None:
        ab = von - timedelta(days=70)
        if ab > start:
            tage_ = (ab - start).days
            i = {"DAILY": tage_ // intervall, "WEEKLY": tage_ // (7 * intervall), "MONTHLY": (tage_ // 31) // intervall, "YEARLY": (tage_ // 366) // intervall}[freq]
            i = max(0, i - 1)
    erg, n, schritte = [], 0, 0
    while schritte < max_n:
        schritte += 1
        if freq == "DAILY":
            k = start + timedelta(days=i * intervall)
            kandidaten = [k] if (not wochentage or k.weekday() in wochentage) and (not monate or k.month in monate) else []
        elif freq == "WEEKLY":
            woche = start - timedelta(days=start.weekday()) + timedelta(weeks=i * intervall)
            kandidaten = [zeit(woche + timedelta(days=t)) for t in wochentage] if wochentage else [start + timedelta(weeks=i * intervall)]
        elif freq == "MONTHLY":
            m = start.month - 1 + i * intervall
            j, mo = start.year + m // 12, m % 12 + 1
            kandidaten = [zeit(date(j, mo, t)) for t in _monatstage(j, mo, tage_regel, monatstage, setpos, start.day)]
        else:
            j = start.year + i * intervall
            if j > 9998:
                return erg
            kandidaten = []
            for mo in (sorted(set(monate)) or [start.month]):
                kandidaten += [zeit(date(j, mo, t)) for t in _monatstage(j, mo, tage_regel, monatstage, setpos, start.day)]
        for k in kandidaten:
            if k < start:
                continue
            kl = lokal(k)
            if bis_regel and kl > bis_regel:
                return erg
            if anzahl is not None and n >= anzahl:
                return erg
            n += 1
            if kl > bis:
                return erg
            if kl >= von - timedelta(days=60):
                erg.append(kl)
        i += 1
    return erg


def ics_parsen(text, von, bis):
    """Liefert Ereignisse im Zeitraum [von, bis] (datetime)."""
    ereignisse, overrides, aktuell = [], {}, None
    for z in _entfalten(text):
        if z == "BEGIN:VEVENT":
            aktuell = {"exdate": []}
            continue
        if z == "END:VEVENT":
            if aktuell and "start" in aktuell:
                ereignisse.append(aktuell)
            aktuell = None
            continue
        if aktuell is None:
            continue
        name, params, wert = _zeile(z)
        try:
            if name == "SUMMARY":
                aktuell["titel"] = _unescape(wert)
            elif name == "LOCATION":
                aktuell["ort"] = _unescape(wert)
            elif name == "DTSTART":
                aktuell["start"], aktuell["ganztags"] = _zeit(wert, params)
                if wert.strip().endswith("Z") and not aktuell["ganztags"]:
                    aktuell["start_utc"] = datetime.strptime(wert.strip()[:15], "%Y%m%dT%H%M%S")
            elif name == "DTEND":
                aktuell["ende"] = _zeit(wert, params)[0]
            elif name == "DURATION":
                aktuell["dauer"] = _dauer(wert)
            elif name == "RRULE":
                aktuell["rrule"] = wert
            elif name == "EXDATE":
                aktuell["exdate"] += [_zeit(w, params)[0] for w in wert.split(",")]
            elif name == "UID":
                aktuell["uid"] = wert
            elif name == "RECURRENCE-ID":
                aktuell["recid"] = _zeit(wert, params)[0]
            elif name == "STATUS":
                aktuell["status"] = wert
        except ValueError:
            continue
    for e in ereignisse:
        if e.get("recid") and e.get("uid"):
            overrides.setdefault(e["uid"], set()).add(e["recid"])
    erg = []
    for e in ereignisse:
        if e.get("status") == "CANCELLED":
            continue
        start = e["start"]
        dauer = (e["ende"] - start) if "ende" in e else e.get("dauer") or (timedelta(days=1) if e.get("ganztags") else timedelta(hours=1))
        if e.get("rrule") and not e.get("recid"):
            if e.get("start_utc"):   # Serie in Weltzeit: je Termin in Ortszeit umrechnen (Sommer-/Winterzeit)
                starts = _wiederholungen(e["start_utc"], e["rrule"], von, bis, lokal=lambda x: x.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None))
            else:
                starts = _wiederholungen(start, e["rrule"], von, bis)
        else:
            starts = [start]
        ausnahmen = set(e["exdate"]) | (overrides.get(e.get("uid"), set()) if e.get("rrule") else set())
        for s in starts:
            if s in ausnahmen:
                continue
            ende = s + dauer
            if ende <= von or s > bis:
                continue
            if e.get("ganztags"):
                letzter = (ende - timedelta(days=1)).date() if ende.date() > s.date() else s.date()
                erg.append({"titel": e.get("titel", ""), "ort": e.get("ort", ""), "ganztags": True,
                            "von": s.date().isoformat(), "bis": letzter.isoformat()})
            else:
                erg.append({"titel": e.get("titel", ""), "ort": e.get("ort", ""), "ganztags": False,
                            "von": s.date().isoformat(), "bis": (ende - timedelta(seconds=1)).date().isoformat(),
                            "zeit_von": s.strftime("%H:%M"), "zeit_bis": ende.strftime("%H:%M")})
    erg.sort(key=lambda x: (x["von"], x.get("zeit_von", "")))
    return erg


MAX_KALENDER = 20 * 1024 * 1024   # größter Kalender, der aus dem Netz gelesen wird


def laden(url, neu=False):
    url = url.strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    jetzt = time.time()
    if not neu and url in _cache and jetzt - _cache[url][0] < CACHE_SEKUNDEN:
        return _cache[url][1]
    if not re.match(r"https?://", url, re.I):   # keine Datei- oder sonstigen Adressen: hier wird nur ein Kalender aus dem Netz gelesen
        raise ValueError("Die Kalenderadresse muss mit https:// (oder webcal://) beginnen.")
    req = urllib.request.Request(url, headers={"User-Agent": "Jahresring/1.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
        roh = r.read(MAX_KALENDER + 1)
    if len(roh) > MAX_KALENDER:
        raise ValueError(f"Der Kalender ist zu groß (mehr als {MAX_KALENDER // 1048576} MB).")
    text = roh.decode("utf-8", errors="replace")
    if "BEGIN:VCALENDAR" not in text:
        raise ValueError("Unter dieser Adresse liegt kein Kalender (iCal). Bitte die „Privatadresse im iCal-Format“ verwenden.")
    _cache[url] = (jetzt, text)
    return text


def externe_termine(kalender, von, bis, neu=False):
    """kalender: Liste von {name, url, farbe, aktiv}. Liefert (termine, fehler)."""
    von_dt = datetime.combine(von, datetime.min.time())
    bis_dt = datetime.combine(bis, datetime.max.time())
    termine, fehler = [], []
    for i, k in enumerate(kalender or []):
        if not k.get("url") or k.get("aktiv") is False:
            continue
        try:
            for t in ics_parsen(laden(k["url"], neu), von_dt, bis_dt):
                t.update({"quelle": k.get("name") or f"Kalender {i + 1}", "farbe": k.get("farbe") or "#4f7cba", "extern": True})
                termine.append(t)
        except Exception as f:  # noqa
            fehler.append(f"{k.get('name') or 'Kalender'}: {f}")
    return termine, fehler


def _esc(s):
    return str(s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_export(termine):
    """Eigene Termine als .ics (zum Import in Google Kalender)."""
    jetzt = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    z = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Jahresring//DE", "CALSCALE:GREGORIAN",
         "X-WR-CALNAME:Jahresring Planung"]
    for t in termine:
        z += ["BEGIN:VEVENT", f"UID:jahresring-{t['art']}-{t['id']}@jahresring", f"DTSTAMP:{jetzt}"]
        v, b = date.fromisoformat(t["von"]), date.fromisoformat(t["bis"])
        if t.get("zeit_von"):
            z.append(f"DTSTART:{v.strftime('%Y%m%d')}T{t['zeit_von'].replace(':', '')}00")
            ende = t.get("zeit_bis") or ""
            if not ende or (v == b and ende <= t["zeit_von"]):   # ohne (gültiges) Ende: eine Stunde
                h_, m_ = (int(x) for x in t["zeit_von"].split(":")[:2])
                ende = f"{min(h_ + 1, 23):02d}:{m_ if h_ < 23 else 59:02d}"
            z.append(f"DTEND:{b.strftime('%Y%m%d')}T{ende.replace(':', '')}00")
        else:
            z.append(f"DTSTART;VALUE=DATE:{v.strftime('%Y%m%d')}")
            z.append(f"DTEND;VALUE=DATE:{(b + timedelta(days=1)).strftime('%Y%m%d')}")
        z.append(f"SUMMARY:{_esc(t['titel'])}")
        if t.get("notiz"):
            z.append(f"DESCRIPTION:{_esc(t['notiz'])}")
        if t.get("vorlaeufig"):
            z.append("STATUS:TENTATIVE")
        z.append("END:VEVENT")
    z.append("END:VCALENDAR")
    return "\r\n".join(z) + "\r\n"
