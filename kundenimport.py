"""Import von Kundendaten aus CSV, Excel (.xlsx) oder vCard (.vcf, z. B. Outlook/Google-Kontakte)."""
import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET

# Zielfelder: (Schlüssel, Anzeige, Stichworte für die automatische Zuordnung)
FELDER = [
    ("nummer", "Kundennummer", ["kundennummer", "kundennr", "kd-nr", "kdnr", "kunden-nr", "nummer", "nr", "debitor", "debitorennummer", "id"]),
    ("kurzname", "Kurzname / Suchname", ["kurzname", "suchname", "matchcode", "anzeigename", "kurzbezeichnung"]),
    ("firma", "Firma", ["firma", "firmenname", "unternehmen", "company", "organisation", "name1", "name 1", "name"]),
    ("titel", "Anrede (Herr/Frau/Familie)", ["anrede", "salutation", "title", "geschlecht"]),
    ("akad", "Titel (Dr., Prof.)", ["titel", "akad. titel", "akademischer titel"]),
    ("vorname", "Vorname", ["vorname", "first name", "given name", "firstname"]),
    ("nachname", "Nachname", ["nachname", "familienname", "last name", "surname", "lastname", "name2", "name 2"]),
    ("zusatz", "Adresszusatz / z. Hd.", ["zusatz", "adresszusatz", "name3", "name 3", "abteilung", "z. hd.", "ansprechpartner"]),
    ("strasse", "Straße und Hausnummer", ["straße", "strasse", "str.", "anschrift", "adresse", "street", "straße/hausnummer"]),
    ("hausnr", "Hausnummer (separat)", ["hausnummer", "hausnr", "hnr"]),
    ("plz", "PLZ", ["plz", "postleitzahl", "zip", "postal code", "postcode"]),
    ("ort", "Ort", ["ort", "stadt", "city", "wohnort"]),
    ("land", "Land", ["land", "country", "staat"]),
    ("telefon", "Telefon", ["telefon", "tel", "tel.", "phone", "telefon geschäftlich", "telefon privat", "festnetz", "telefon 1"]),
    ("mobil", "Mobil", ["mobil", "handy", "mobile", "mobiltelefon", "mobilfunk", "telefon 2"]),
    ("email1", "E-Mail", ["e-mail", "email", "mail", "e-mail-adresse", "e-mail 1", "email1"]),
    ("email2", "E-Mail 2", ["e-mail 2", "email2", "e-mail2"]),
    ("website", "Website", ["website", "homepage", "internet", "web", "url"]),
    ("gruppe", "Kundengruppe", ["gruppe", "kundengruppe", "kategorie", "typ", "kundentyp"]),
    ("ustid", "USt-IdNr.", ["ust-idnr", "ustid", "ust-id", "umsatzsteuer-id", "vat"]),
    ("anrede", "Briefanrede", ["briefanrede", "briefanrede", "anrede brief"]),
    ("zahlungsziel", "Zahlungsziel (Tage)", ["zahlungsziel", "zahlungsfrist"]),
    ("bemerkungen", "Bemerkungen", ["bemerkung", "bemerkungen", "notiz", "notizen", "info", "kommentar", "notes"]),
    ("merkmale", "Merkmale", ["merkmale", "stichworte", "tags"]),
]
FELD_NAMEN = {k: n for k, n, _ in FELDER}


class ImportFehler(Exception):
    pass


def dekodieren(roh):
    # „Unicode-Text“ aus Excel ist UTF-16: am Anfangszeichen zu erkennen – oder daran, dass jedes zweite Byte 0 ist
    if roh[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return roh.decode("utf-16")
        except UnicodeDecodeError:
            pass
    probe = roh[:4000]
    if len(probe) >= 8 and probe.count(b"\x00") > len(probe) // 3:
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                text = roh.decode(enc)
            except UnicodeDecodeError:
                continue
            if text[:200].count("\x00") == 0 and sum(1 for c in text[:200] if c.isprintable() or c in "\r\n\t") > len(text[:200]) * 0.9:
                return text
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return roh.decode(enc)
        except UnicodeDecodeError:
            continue
    return roh.decode("utf-8", "replace")


def csv_lesen(roh):
    text = dekodieren(roh)
    if "\x00" in text[:20000]:
        raise ImportFehler("Die Datei ist keine lesbare Tabelle. Bitte als .csv oder .xlsx speichern.")
    text = text.replace("\r\n", "\n").replace("\r", "\n")   # auch Dateien mit alten Mac-Zeilenenden (nur CR)
    probe = text[:5000]
    try:
        dialekt = csv.Sniffer().sniff(probe, delimiters=";,\t|")
        trenner = dialekt.delimiter
    except csv.Error:
        trenner = max(";,\t", key=probe.count)
    try:
        zeilen = [z for z in csv.reader(io.StringIO(text), delimiter=trenner) if any(x.strip() for x in z)]
    except csv.Error:
        raise ImportFehler("Die Datei ließ sich nicht als Tabelle lesen (CSV). Bitte in der Tabellenkalkulation neu als .csv oder .xlsx speichern.")
    return zeilen


# Excel-Dateien sind gepackt: Eine kleine Datei kann ausgepackt sehr groß werden. Mehr als diese Menge liest das Programm nicht
# in den Arbeitsspeicher (eine Preisliste mit 200.000 Zeilen bleibt weit darunter).
MAX_XLSX_ENTPACKT = 150 * 1024 * 1024


def _xlsx_teil(z, name):
    """Ein Teil der Excel-Datei als XML-Baum – mit Größenprüfung und ohne DTD/Entity-Deklarationen."""
    try:
        info = z.getinfo(name)
    except KeyError:
        raise ImportFehler("Die Excel-Datei ist unvollständig. Bitte neu als .xlsx speichern.")
    if info.file_size > MAX_XLSX_ENTPACKT:
        raise ImportFehler("Die Excel-Datei ist zu groß (mehr als 150 MB Tabelleninhalt).")
    try:
        roh = z.read(name)
    except Exception:   # noqa: BLE001 – beschädigtes Archiv
        raise ImportFehler("Die Excel-Datei ist beschädigt. Bitte neu als .xlsx speichern.")
    if re.search(rb"<!\s*(DOCTYPE|ENTITY)", roh[:4096], re.I):
        raise ImportFehler("Die Excel-Datei enthält eine DTD bzw. Entity-Deklaration und wird aus Sicherheitsgründen nicht gelesen.")
    try:
        return ET.fromstring(roh)
    except ET.ParseError:
        raise ImportFehler("Die Excel-Datei ist beschädigt. Bitte neu als .xlsx speichern.")


def _xlsx_oeffnen(roh):
    try:
        z = zipfile.ZipFile(io.BytesIO(roh))
    except zipfile.BadZipFile:
        raise ImportFehler("Die Excel-Datei ließ sich nicht öffnen. Bitte als .xlsx oder .csv speichern.")
    if sum(i.file_size for i in z.infolist() if i.filename.startswith("xl/") and i.filename.endswith(".xml")) > MAX_XLSX_ENTPACKT:
        raise ImportFehler("Die Excel-Datei ist zu groß (mehr als 150 MB Tabelleninhalt).")
    return z


def _farbe_rgb(el, theme):
    """<fgColor rgb=.. | theme=.. tint=.. | indexed=..> → (r, g, b) oder None."""
    if el is None:
        return None
    hexwert = None
    if el.get("rgb"):
        hexwert = el.get("rgb")[-6:]
    elif el.get("theme") is not None and theme:
        try:
            hexwert = theme[int(el.get("theme"))]
        except (IndexError, ValueError):
            return None
    elif el.get("indexed") is not None:
        hexwert = {"5": "FFFF00", "13": "FFFF00", "34": "FFFF99", "43": "FFFF99", "51": "FFCC00", "26": "FFFF00",
                   "22": "C0C0C0", "9": "FFFFFF", "64": None}.get(el.get("indexed"))
    if not hexwert or len(hexwert) != 6:
        return None
    try:
        r, g, b = (int(hexwert[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None
    tint = float(el.get("tint") or 0)
    if tint:
        f = (lambda c: c + (255 - c) * tint) if tint > 0 else (lambda c: c * (1 + tint))
        r, g, b = (int(round(f(c))) for c in (r, g, b))
    return r, g, b


def ist_gelb(rgb):
    if not rgb:
        return False
    r, g, b = rgb
    return r >= 200 and g >= 170 and g - b >= 35 and r - b >= 40 and abs(r - g) <= 70


def _xlsx_farben(z, ns):
    """Style-Index → True, wenn die Zellfüllung gelblich ist."""
    theme = []
    for n in z.namelist():
        if n.startswith("xl/theme/") and n.endswith(".xml"):
            try:
                t = ET.fromstring(z.read(n))
                a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
                cs = next(t.iter(a + "clrScheme"), None)
                if cs is not None:
                    werte = []
                    for kind in cs:
                        srgb = kind.find(a + "srgbClr")
                        sys_ = kind.find(a + "sysClr")
                        werte.append(srgb.get("val") if srgb is not None else (sys_.get("lastClr") if sys_ is not None else "000000"))
                    # Excel-Reihenfolge der Theme-Indizes: lt1, dk1, lt2, dk2, accent1…6
                    if len(werte) >= 4:
                        werte[0], werte[1], werte[2], werte[3] = werte[1], werte[0], werte[3], werte[2]
                    theme = werte
            except ET.ParseError:
                pass
            break
    if "xl/styles.xml" not in z.namelist():
        return {}
    try:
        st = ET.fromstring(z.read("xl/styles.xml"))
    except Exception:   # noqa: BLE001 – Formatvorlagen nicht lesbar: dann eben ohne Farberkennung
        return {}
    fills = []
    fl = st.find("m:fills", ns)
    for f in (fl.findall("m:fill", ns) if fl is not None else []):
        pf = f.find("m:patternFill", ns)
        gelb = False
        if pf is not None and (pf.get("patternType") or "none") != "none":
            gelb = ist_gelb(_farbe_rgb(pf.find("m:fgColor", ns), theme) or _farbe_rgb(pf.find("m:bgColor", ns), theme))
        fills.append(gelb)
    xf = st.find("m:cellXfs", ns)
    ergebnis = {}
    for i, x in enumerate(xf.findall("m:xf", ns) if xf is not None else []):
        try:
            ergebnis[i] = fills[int(x.get("fillId") or 0)]
        except (IndexError, ValueError):
            ergebnis[i] = False
    return ergebnis


def xlsx_blaetter(z, ns):
    """[(Name, Pfad)] in der Reihenfolge der Arbeitsmappe."""
    try:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    except (KeyError, ET.ParseError):
        return []
    ziele = {r.get("Id"): r.get("Target") for r in rels}
    rid = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    aus = []
    for sh in wb.iter("{%s}sheet" % ns["m"]):
        ziel = (ziele.get(sh.get(rid)) or "").lstrip("/")
        if ziel and not ziel.startswith("xl/"):
            ziel = "xl/" + ziel
        if ziel in z.namelist():
            aus.append((sh.get("name") or "", ziel))
    return aus


def xlsx_blattnamen(roh):
    try:
        z = _xlsx_oeffnen(roh)
    except ImportFehler:
        return []
    return [b[0] for b in xlsx_blaetter(z, {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"})]


def xlsx_lesen(roh, blatt=None, info=None):
    """Liest ein Tabellenblatt. blatt = Name (oder None = erstes / passendes Blatt).
    info (dict) bekommt: blaetter (Namen), blatt (gelesenes Blatt), gelb (Zeilenindizes mit gelber Füllung)."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    z = _xlsx_oeffnen(roh)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in _xlsx_teil(z, "xl/sharedStrings.xml").findall("m:si", ns):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
    blaetter = xlsx_blaetter(z, ns)
    pfad, name = None, ""
    if blaetter:
        wahl = None
        if blatt:
            wahl = next((b for b in blaetter if b[0].strip().lower() == str(blatt).strip().lower()), None)
        name, pfad = wahl or blaetter[0]
    if not pfad:
        pfad = "xl/worksheets/sheet1.xml"
        if pfad not in z.namelist():
            kandidaten = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
            if not kandidaten:
                raise ImportFehler("In der Excel-Datei wurde kein Tabellenblatt gefunden.")
            pfad = kandidaten[0]
    farben = _xlsx_farben(z, ns) if info is not None else {}
    zeilen, gelb = [], []
    def ganz(t):
        try:
            return int(t or 0)
        except ValueError:
            return 0
    for row in _xlsx_teil(z, pfad).iter("{%s}row" % ns["m"]):
        werte, gelbe_zellen = {}, 0
        zeile_gelb = row.get("customFormat") == "1" and farben.get(ganz(row.get("s")), False)
        vorige = 0
        for c in row.findall("m:c", ns):
            ref = c.get("r") or ""
            spalte = 0
            for ch in re.match(r"[A-Z]*", ref.upper()).group(0):
                spalte = spalte * 26 + ord(ch) - 64
            if not spalte:   # Zelle ohne Bezug (manche Programme lassen ihn weg): Sie folgt auf die vorige
                spalte = vorige + 1
            vorige = spalte
            typ = c.get("t")
            v = c.find("m:v", ns)
            if typ == "s" and v is not None:
                nr = ganz(v.text) if (v.text or "").strip().isdigit() else -1
                wert = shared[nr] if 0 <= nr < len(shared) else ""
            elif typ == "inlineStr":
                wert = "".join(t.text or "" for t in c.iter("{%s}t" % ns["m"]))
            else:
                wert = v.text if v is not None else ""
                if wert and re.fullmatch(r"-?\d+\.0+", wert):
                    wert = wert.split(".")[0]
            wert = (wert or "").strip()
            if wert and farben.get(ganz(c.get("s")), False):
                gelbe_zellen += 1
            if wert or spalte - 1 in werte:
                werte[spalte - 1] = wert
        if werte and any(werte.values()):
            zeile = [""] * (max(werte) + 1)
            for i, w in werte.items():
                zeile[i] = w
            gefuellt = sum(1 for w in zeile if w)
            if zeile_gelb or (gefuellt and gelbe_zellen * 2 >= gefuellt):
                gelb.append(len(zeilen))
            zeilen.append(zeile)
    if info is not None:
        info.update({"blaetter": [b[0] for b in blaetter], "blatt": name, "gelb": gelb})
    return zeilen


def vcf_lesen(roh):
    text = dekodieren(roh).replace("\r\n ", "").replace("\n ", "")
    kopf = ["Firma", "Anrede", "Vorname", "Nachname", "Straße", "PLZ", "Ort", "Land", "Telefon", "Mobil", "E-Mail", "E-Mail 2", "Website", "Bemerkung"]
    zeilen = [kopf]
    for karte in re.findall(r"BEGIN:VCARD(.*?)END:VCARD", text, re.S | re.I):
        d = {k: "" for k in kopf}
        mails = []
        for zeile in karte.strip().splitlines():
            if ":" not in zeile:
                continue
            schluessel, wert = zeile.split(":", 1)
            name = schluessel.split(";")[0].upper().split(".")[-1]
            par = schluessel.upper()
            wert = wert.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").strip()
            if name == "N":
                t = (wert.split(";") + [""] * 5)[:5]
                d["Nachname"], d["Vorname"] = t[0], t[1]
                d["Anrede"] = t[3]
            elif name == "ORG":
                d["Firma"] = wert.split(";")[0]
            elif name == "ADR" and not d["Ort"]:
                t = (wert.split(";") + [""] * 7)[:7]
                d["Straße"], d["Ort"], d["PLZ"], d["Land"] = t[2], t[3], t[5], t[6]
            elif name == "TEL":
                if "CELL" in par and not d["Mobil"]:
                    d["Mobil"] = wert
                elif not d["Telefon"]:
                    d["Telefon"] = wert
            elif name == "EMAIL":
                mails.append(wert)
            elif name == "URL" and not d["Website"]:
                d["Website"] = wert
            elif name == "NOTE":
                d["Bemerkung"] = wert
        d["E-Mail"], d["E-Mail 2"] = (mails + ["", ""])[:2]
        if any(d.values()):
            zeilen.append([d[k] for k in kopf])
    if len(zeilen) == 1:
        raise ImportFehler("In der vCard-Datei wurden keine Kontakte gefunden.")
    return zeilen


def tabelle_lesen(roh, dateiname, blatt=None, info=None):
    n = (dateiname or "").lower()
    if n.endswith(".xlsx") or roh[:2] == b"PK":
        z = xlsx_lesen(roh, blatt, info)
    elif n.endswith(".vcf") or b"BEGIN:VCARD" in roh[:2000].upper():
        z = vcf_lesen(roh)
    elif n.endswith(".xls"):
        raise ImportFehler("Alte Excel-Dateien (.xls) bitte in Excel als .xlsx oder .csv speichern.")
    else:
        z = csv_lesen(roh)
    if len(z) < 2:
        raise ImportFehler("Die Datei enthält keine Datenzeilen (erste Zeile = Spaltenüberschriften).")
    breite = max(len(r) for r in z)
    return [r + [""] * (breite - len(r)) for r in z]


def _norm(s):
    return re.sub(r"[\s_]+", " ", (s or "").strip().lower())


def vorschlag(kopf):
    """Ordnet Spaltenüberschriften automatisch den Zielfeldern zu."""
    zuordnung, vergeben = {}, set()
    # erst exakte Treffer, dann Teiltreffer
    for exakt in (True, False):
        for i, h in enumerate(kopf):
            if str(i) in zuordnung:
                continue
            hn = _norm(h)
            for k, _, worte in FELDER:
                if k in vergeben:
                    continue
                if (exakt and hn in worte) or (not exakt and any(w in hn for w in worte if len(w) > 3)):
                    zuordnung[str(i)] = k
                    vergeben.add(k)
                    break
    # „Name“ neben „Vorname“ ist der Nachname einer Person, keine Firma
    werte = set(zuordnung.values())
    if "vorname" in werte and "nachname" not in werte:
        for i, k in list(zuordnung.items()):
            if k == "firma" and _norm(kopf[int(i)]) in ("name", "name1", "name 1"):
                zuordnung[i] = "nachname"
    return zuordnung


def _anschrift(r):
    zeilen = []
    if r.get("firma"):
        zeilen.append(r["firma"])
    person = " ".join(x for x in [r.get("titel") if r.get("titel", "").lower() in ("herr", "herrn", "frau", "familie", "fam.") else "",
                                    r.get("akad"), r.get("vorname"), r.get("nachname")] if x)
    if person.lower().startswith("herr "):
        person = "Herrn " + person[5:]
    if person:
        zeilen.append(("z. Hd. " + person) if r.get("firma") and not person.lower().startswith(("herrn", "frau", "familie")) else person)
    if r.get("zusatz"):
        zeilen.append(r["zusatz"])
    strasse = " ".join(x for x in [r.get("strasse"), r.get("hausnr")] if x)
    if strasse:
        zeilen.append(strasse)
    return "\n".join(zeilen)


def _briefanrede(r):
    if r.get("anrede"):
        return r["anrede"]
    t = (r.get("titel") or "").lower()
    name = r.get("nachname") or ""
    akad = (r.get("akad") + " ") if r.get("akad") else ""
    if t.startswith("frau") and name:
        return f"Sehr geehrte Frau {akad}{name},"
    if t.startswith("herr") and name:
        return f"Sehr geehrter Herr {akad}{name},"
    if t.startswith("fam") and name:
        return f"Sehr geehrte Familie {name},"
    return "Sehr geehrte Damen und Herren,"


def datensatz(zeile, zuordnung, gruppen, gruppe_standard):
    r = {}
    for i, feld in zuordnung.items():
        if feld and int(i) < len(zeile):
            w = (zeile[int(i)] or "").strip()
            if w:
                r[feld] = (r[feld] + " " + w) if feld in r and feld in ("bemerkungen", "merkmale") else w
    if not any(r.get(k) for k in ("firma", "nachname", "vorname", "kurzname")):
        return None
    k = {}
    form = (r.get("titel") or "").strip().lower()
    k["anredeform"] = "Herr" if form.startswith("herr") else "Frau" if form.startswith("frau") else "Familie" if form.startswith("fam") \
        else "Eheleute" if form.startswith("eheleute") else "Firma" if form.startswith("firma") else ""
    k["titel"] = r.get("akad") or ""
    for a, b in (("vorname", "vorname"), ("nachname", "nachname"), ("firma", "firma"), ("zusatz", "zusatz")):
        k[a] = r.get(b) or ""
    if r.get("hausnr"):
        k["strasse"], k["hausnr"] = r.get("strasse") or "", r["hausnr"]
    else:
        import adressen
        k["strasse"], k["hausnr"] = adressen.strasse_teilen(r.get("strasse") or "")
    k["kurzname"] = r.get("kurzname") or r.get("firma") or ", ".join(x for x in [r.get("nachname"), r.get("vorname")] if x)
    k["anschrift"] = _anschrift(r)
    k["anrede"] = _briefanrede(r)
    for f in ("plz", "ort", "land", "telefon", "email1", "email2", "website", "ustid", "bemerkungen", "merkmale"):
        if r.get(f):
            k[f] = r[f]
    if r.get("mobil"):
        k["telefon"] = (k["telefon"] + " · " + r["mobil"]) if k.get("telefon") else r["mobil"]
    if r.get("land") and r["land"].upper() in ("D", "DE", "DEU", "GERMANY"):
        k["land"] = "Deutschland"
    if r.get("zahlungsziel") and r["zahlungsziel"].isdigit():
        k["zahlungsziel"] = int(r["zahlungsziel"])
    if r.get("nummer"):
        nr = re.sub(r"\D", "", r["nummer"])
        if nr:
            k["nummer"] = int(nr)
    g = r.get("gruppe")
    if g:
        treffer = next((x for x in gruppen if x.lower() == g.lower() or g.lower() in x.lower()), None)
        k["gruppe"] = treffer or g
    else:
        privat = next((x for x in gruppen if "privat" in x.lower()), None)
        gewerbe = next((x for x in gruppen if any(w in x.lower() for w in ("gewerb", "geschäft", "geschaeft", "firm", "unternehm"))), None)
        k["gruppe"] = (gewerbe if r.get("firma") else privat) or gruppe_standard
    return k


def doppelt(con, k):
    if k.get("nummer"):
        r = con.execute("SELECT id FROM kunden WHERE nummer=?", (k["nummer"],)).fetchone()
        if r:
            return r["id"]
    if k.get("email1"):
        r = con.execute("SELECT id FROM kunden WHERE lower(email1)=lower(?)", (k["email1"],)).fetchone()
        if r:
            return r["id"]
    r = con.execute("SELECT id FROM kunden WHERE lower(kurzname)=lower(?) AND IFNULL(plz,'')=?", (k["kurzname"], k.get("plz", ""))).fetchone()
    return r["id"] if r else None
