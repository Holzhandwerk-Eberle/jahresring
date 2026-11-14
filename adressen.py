"""Anschrift aus Einzelfeldern (Anrede, Titel, Vor-/Nachname, Firma, Zusatz, Straße, Hausnummer) und umgekehrt."""
import re

FELDER = ["anredeform", "titel", "vorname", "nachname", "firma", "zusatz", "strasse", "hausnr"]
ANREDEN = ["", "Herr", "Frau", "Familie", "Eheleute", "Firma"]
FIRMA_WORTE = re.compile(r"\b(gmbh|ag|kg|ohg|gbr|ug|e\.\s?k\.|e\.\s?v\.|mbh|co\.|gemeinde|stadt|landratsamt|amt|verwaltung|schule|kirche|"
                         r"architekt|büro|buero|praxis|kanzlei|hotel|gasthof|restaurant|bäckerei|metzgerei|schreinerei|bau|immobilien|"
                         r"genossenschaft|verein|stiftung|werk|handel|service|gruppe|zentrum|institut)\b", re.I)


def person_zeile(k):
    form = (k.get("anredeform") or "").strip()
    wort = {"Herr": "Herrn", "Frau": "Frau", "Familie": "Familie", "Eheleute": "Eheleute"}.get(form, "")
    teile = [wort, (k.get("titel") or "").strip(), (k.get("vorname") or "").strip(), (k.get("nachname") or "").strip()]
    if form == "Familie":
        teile = [wort, (k.get("nachname") or "").strip()]
    return " ".join(t for t in teile if t)


def anschrift(k):
    zeilen = []
    if (k.get("firma") or "").strip():
        zeilen.append(k["firma"].strip())
    p = person_zeile(k)
    if p and p not in ("Herrn", "Frau", "Familie", "Eheleute"):
        zeilen.append(p)
    if (k.get("zusatz") or "").strip():
        zeilen.append(k["zusatz"].strip())
    strasse = " ".join(x for x in [(k.get("strasse") or "").strip(), (k.get("hausnr") or "").strip()] if x)
    if strasse:
        zeilen.append(strasse)
    return "\n".join(zeilen)


def briefanrede(k):
    form = (k.get("anredeform") or "").strip()
    name = (k.get("nachname") or "").strip()
    titel = ((k.get("titel") or "").strip() + " ") if (k.get("titel") or "").strip() else ""
    if form == "Herr" and name:
        return f"Sehr geehrter Herr {titel}{name},"
    if form == "Frau" and name:
        return f"Sehr geehrte Frau {titel}{name},"
    if form == "Familie" and name:
        return f"Sehr geehrte Familie {name},"
    if form == "Eheleute" and name:
        return f"Sehr geehrte Eheleute {name},"
    return "Sehr geehrte Damen und Herren,"


def kurzname(k):
    if (k.get("firma") or "").strip():
        return k["firma"].strip()
    n, v = (k.get("nachname") or "").strip(), (k.get("vorname") or "").strip()
    return ", ".join(x for x in [n, v] if x)


def strasse_teilen(s):
    s = (s or "").strip()
    m = re.match(r"^(.*?\D)\s*(\d+\s*[a-zA-Z]?(?:\s*[-/]\s*\d*\s*[a-zA-Z]?)?)$", s)
    if m and m.group(1).strip():
        return m.group(1).strip().rstrip(","), m.group(2).replace(" ", "")
    return s, ""


def zerlegen(text):
    """Versucht, eine mehrzeilige Briefanschrift in Einzelfelder aufzuteilen (für bestehende Kunden)."""
    zeilen = [z.strip() for z in (text or "").split("\n") if z.strip()]
    k = {f: "" for f in FELDER}
    if not zeilen:
        return k
    # letzte Zeile mit Hausnummer = Straße
    if re.search(r"\d", zeilen[-1]) and not re.match(r"^\d{4,5}\s", zeilen[-1]):
        k["strasse"], k["hausnr"] = strasse_teilen(zeilen.pop())
    elif re.match(r"^(postfach|pf\.?)\b", zeilen[-1], re.I):
        k["strasse"] = zeilen.pop()
    person_i = None
    for i, z in enumerate(zeilen):
        z2 = re.sub(r"^(z\.\s*hd\.?|zu händen|c/o)\s*", "", z, flags=re.I)
        m = re.match(r"^(Herrn?|Frau|Familie|Fam\.|Eheleute)\s+(.*)$", z2, re.I)
        if m:
            person_i = i
            form = m.group(1).lower()
            k["anredeform"] = "Herr" if form.startswith("herr") else "Frau" if form == "frau" else "Eheleute" if form == "eheleute" else "Familie"
            rest = m.group(2).strip()
            t = re.match(r"^((?:Prof\.\s*)?(?:Dr\.(?:\s*[\w.-]+\.)?\s*)?(?:Dipl\.-[\w.]+\s*)?)(.*)$", rest)
            if t and t.group(1).strip():
                k["titel"], rest = t.group(1).strip(), t.group(2).strip()
            namen = rest.split()
            if k["anredeform"] in ("Familie", "Eheleute") and len(namen) == 1:
                k["nachname"] = namen[0]
            elif namen:
                k["nachname"] = namen[-1]
                k["vorname"] = " ".join(namen[:-1])
            break
    andere = [z for i, z in enumerate(zeilen) if i != person_i]
    if person_i is not None:
        if andere and person_i > 0:
            k["firma"] = andere.pop(0)
        k["zusatz"] = ", ".join(andere)
    elif andere:
        erste = andere.pop(0)
        worte = erste.split()
        if FIRMA_WORTE.search(erste) or len(worte) > 3 or len(worte) == 1:
            k["firma"] = erste
            if k["firma"] and len(worte) == 1 and not FIRMA_WORTE.search(erste):
                k["firma"], k["nachname"] = "", erste
        else:
            k["vorname"], k["nachname"] = " ".join(worte[:-1]), worte[-1]
        k["zusatz"] = ", ".join(andere)
    return k


def ableiten(alt, neu):
    """alt = gespeicherter Datensatz, neu = geänderte Felder. Setzt Anschrift, Briefanrede und Kurzname neu, wenn
    Einzelfelder geändert wurden. Briefanrede und Kurzname nur, solange sie nicht von Hand abweichend eingetragen sind."""
    if not any(f in neu for f in FELDER):
        return neu
    vorher = {f: (alt or {}).get(f) or "" for f in FELDER}
    nachher = {**vorher, **{f: neu[f] for f in FELDER if f in neu}}
    neu = dict(neu)
    neu["anschrift"] = anschrift(nachher)
    if "anrede" not in neu and ((alt or {}).get("anrede") or "") in ("", briefanrede(vorher), "Sehr geehrte Damen und Herren,"):
        neu["anrede"] = briefanrede(nachher)
    if "kurzname" not in neu and ((alt or {}).get("kurzname") or "") in ("", kurzname(vorher), "Neuer Kunde", "Neuer Lieferant"):
        kn = kurzname(nachher)
        if kn:
            neu["kurzname"] = kn
    return neu
