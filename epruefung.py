"""Offizielle Prüfung von E-Rechnungen mit den Regelwerken, die auch der KoSIT-Validator verwendet.

Schritte (wie im Prüftool der KoSIT):
  1. Schema (XSD): CII D16B nach EN 16931 (nur CII; mit lxml)
  2. EN 16931: Schematron-Regeln der CEN (ConnectingEurope „validation-1.3.17“, als XSLT)
  3. XRechnung: Schematron-Regeln der KoSIT 2.6.0 inkl. eingebundener Peppol-Regeln (nur bei XRechnung-Profil)

Die Regeln liegen im Ordner „pruefregeln“ des Programms. Ausgeführt werden sie mit Saxon-HE (Python-Paket „saxonche“),
das Schema mit „lxml“. Beides wird bei Bedarf einmalig mit pip nachinstalliert (Einstellungen › Service bzw. Knopf in der
XML-Ansicht); ohne die Pakete bleibt die einfache Prüfung in xmlansicht.py.
"""
import importlib
import os
import site
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET

REGELN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pruefregeln")
VERSIONEN = {"en16931": "CEN EN 16931 Validierungsartefakte 1.3.17", "xrechnung": "KoSIT XRechnung-Schematron 2.6.0 (mit Peppol BIS 3.0.21)"}
PAKETE = ["saxonche", "lxml"]
ANFORDERUNGEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pruefregeln", "anforderungen.txt")
_sperre = threading.Lock()
_cache = {}
EINRICHTUNG = {"laeuft": False, "fertig": False, "fehler": "", "ausgabe": ""}


def _user_site():
    try:
        p = site.getusersitepackages()
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.append(p)
    except Exception:  # noqa: BLE001
        pass


def verfuegbar():
    _user_site()
    importlib.invalidate_caches()
    try:
        import saxonche  # noqa: F401
        sx = True
    except ImportError:
        sx = False
    try:
        import lxml.etree  # noqa: F401
        lx = True
    except ImportError:
        lx = False
    return {"saxon": sx, "lxml": lx, "regeln": os.path.isfile(os.path.join(REGELN, "EN16931-CII-validation.xslt")),
            "einrichtung": dict(EINRICHTUNG), "versionen": VERSIONEN}


def einrichten_starten():
    """Installiert Saxon-HE und lxml im Hintergrund für das aktuelle Windows-Benutzerkonto (pip --user)."""
    if EINRICHTUNG["laeuft"]:
        return dict(EINRICHTUNG)

    def lauf():
        EINRICHTUNG.update(laeuft=True, fertig=False, fehler="", ausgabe="")
        try:
            # nur die geprüften Fassungen: feste Versionen, Prüfsumme jeder Datei muss stimmen (pruefregeln/anforderungen.txt)
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--disable-pip-version-check", "--no-input",
                                "--only-binary=:all:", "--no-deps", "--require-hashes", "-r", ANFORDERUNGEN],
                               capture_output=True, text=True, timeout=900,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            EINRICHTUNG["ausgabe"] = (r.stdout or "")[-2000:] + (r.stderr or "")[-2000:]
            if r.returncode != 0:
                aus = (r.stderr or "") + (r.stdout or "")
                if "hash" in aus.lower() or "No matching distribution" in aus or "from versions: none" in aus:
                    EINRICHTUNG["fehler"] = (f"Für dieses Python ({sys.version_info.major}.{sys.version_info.minor}) liegen keine geprüften Pakete vor "
                                             "(vorgesehen: Windows 64 Bit mit Python 3.12 bis 3.14). Es wurde nichts installiert. " + aus.strip()[-200:])
                else:
                    EINRICHTUNG["fehler"] = "Die Installation ist fehlgeschlagen (Internetverbindung?). " + (r.stderr or "").strip()[-300:]
        except Exception as f:  # noqa: BLE001
            EINRICHTUNG["fehler"] = f"Die Installation ist fehlgeschlagen: {f}"
        finally:
            EINRICHTUNG.update(laeuft=False, fertig=not EINRICHTUNG["fehler"])
    threading.Thread(target=lauf, daemon=True).start()
    return dict(EINRICHTUNG, laeuft=True)


def _ln(tag):
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def _xslt(name):
    """Kompiliertes Regelwerk (einmal je Programmlauf, danach aus dem Speicher)."""
    if name not in _cache:
        from saxonche import PySaxonProcessor
        if "_proc" not in _cache:
            _cache["_proc"] = PySaxonProcessor(license=False)
            _cache["_xp"] = _cache["_proc"].new_xslt30_processor()
        _cache[name] = _cache["_xp"].compile_stylesheet(stylesheet_file=os.path.join(REGELN, name))
    return _cache[name]


def _schematron(name, xml_text):
    exe = _xslt(name)
    proc = _cache["_proc"]
    knoten = proc.parse_xml(xml_text=xml_text)
    svrl = exe.transform_to_string(xdm_node=knoten)
    meldungen = []
    for e in ET.fromstring(svrl.encode("utf-8")).iter():
        art = _ln(e.tag)
        if art not in ("failed-assert", "successful-report"):
            continue
        text = " ".join(" ".join("".join(t.itertext()).split()) for t in e if _ln(t.tag) == "text")
        flag = (e.attrib.get("flag") or ("fatal" if art == "failed-assert" else "warning")).lower()
        meldungen.append({"regel": e.attrib.get("id", ""), "stufe": "fehler" if flag in ("fatal", "error") else "warnung",
                          "text": text, "ort": e.attrib.get("location", "")})
    return meldungen


def _schema_cii(xml_bytes):
    from lxml import etree
    if "xsd_cii" not in _cache:
        pfad = os.path.join(REGELN, "cii-schema", "CII", "uncefact", "data", "standard", "CrossIndustryInvoice_100pD16B.xsd")
        _cache["xsd_cii"] = etree.XMLSchema(etree.parse(pfad))
    s = _cache["xsd_cii"]
    doc = etree.fromstring(xml_bytes, etree.XMLParser(resolve_entities=False, no_network=True))
    if s.validate(doc):
        return []
    return [{"regel": "XSD", "stufe": "fehler", "text": f"Zeile {f.line}: {f.message}", "ort": ""} for f in list(s.error_log)[:50]]


def pruefen(xml_bytes):
    """→ {"moeglich", "gueltig", "schritte": [{"name", "status" ok|fehler|warnung|uebersprungen, "hinweis", "meldungen"}]}"""
    v = verfuegbar()
    if not v["saxon"] or not v["regeln"]:
        return {"moeglich": False, "grund": "nicht eingerichtet", "verfuegbar": v}
    import eingangsrechnung
    try:
        eingangsrechnung.dtd_pruefen(xml_bytes)
    except eingangsrechnung.LeseFehler as f:
        return {"moeglich": True, "gueltig": False, "schritte": [{"name": "Sicherheit", "status": "fehler", "meldungen": [
            {"regel": "XML", "stufe": "fehler", "text": str(f), "ort": ""}]}]}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as f:
        return {"moeglich": True, "gueltig": False, "schritte": [{"name": "Wohlgeformtheit", "status": "fehler", "meldungen": [
            {"regel": "XML", "stufe": "fehler", "text": str(f), "ort": ""}]}]}
    name = _ln(root.tag)
    profil = ""
    for e in root.iter():
        if _ln(e.tag) in ("GuidelineSpecifiedDocumentContextParameter",):
            profil = "".join(x.text or "" for x in e if _ln(x.tag) == "ID").strip()
            break
        if _ln(e.tag) == "CustomizationID":
            profil = (e.text or "").strip()
            break
    pl = profil.lower()
    xr = "xrechnung" in pl
    import re as _re
    import xmlansicht
    text = xmlansicht._als_text(xml_bytes)
    text = _re.sub(r"^\s*<\?xml[^>]*\?>", "", text, count=1)   # Saxon liest den Text; die Kodierungsangabe gilt hier nicht mehr
    schritte = []
    with _sperre:
        if name == "CrossIndustryInvoice":
            if "extended" in pl or "minimum" in pl or "basicwl" in pl:
                schritte.append({"name": "Schema (XSD)", "status": "uebersprungen", "meldungen": [],
                                 "hinweis": "Das Profil hat ein eigenes Factur-X-Schema; geprüft werden die EN-16931-Regeln."})
            elif v["lxml"]:
                m = _schema_cii(xml_bytes)
                schritte.append({"name": "Schema (XSD) CII D16B", "status": "fehler" if m else "ok", "meldungen": m})
            else:
                schritte.append({"name": "Schema (XSD)", "status": "uebersprungen", "meldungen": [], "hinweis": "lxml fehlt"})
            regeln = ("EN16931-CII-validation.xslt", "XRechnung-CII-validation.xsl")
        elif name in ("Invoice", "CreditNote"):
            schritte.append({"name": "Schema (XSD)", "status": "uebersprungen", "meldungen": [],
                             "hinweis": "Für UBL ist das Schema nicht enthalten; geprüft werden die Geschäftsregeln."})
            regeln = ("EN16931-UBL-validation.xslt", "XRechnung-UBL-validation.xsl")
        elif name == "CrossIndustryDocument":
            return {"moeglich": True, "gueltig": None, "schritte": [{"name": "EN 16931", "status": "uebersprungen", "meldungen": [],
                    "hinweis": "ZUGFeRD 1.0 ist kein Format nach EN 16931; dafür gibt es keine offizielle Prüfung."}]}
        else:
            return {"moeglich": True, "gueltig": None, "schritte": [{"name": "E-Rechnung", "status": "uebersprungen", "meldungen": [],
                    "hinweis": "Keine E-Rechnung (weder CII noch UBL)."}]}
        try:
            m = _schematron(regeln[0], text)
            schritte.append({"name": f"EN 16931 ({VERSIONEN['en16931']})", "meldungen": m,
                             "status": "fehler" if any(x["stufe"] == "fehler" for x in m) else "warnung" if m else "ok"})
            if xr:
                m = _schematron(regeln[1], text)
                schritte.append({"name": f"XRechnung ({VERSIONEN['xrechnung']})", "meldungen": m,
                                 "status": "fehler" if any(x["stufe"] == "fehler" for x in m) else "warnung" if m else "ok"})
            else:
                schritte.append({"name": "XRechnung", "status": "uebersprungen", "meldungen": [],
                                 "hinweis": "Kein XRechnung-Profil; die deutschen Zusatzregeln gelten nur für XRechnungen."})
        except Exception as f:  # noqa: BLE001
            schritte.append({"name": "Regelprüfung", "status": "fehler", "meldungen": [
                {"regel": "", "stufe": "fehler", "text": f"Die Prüfung konnte nicht ausgeführt werden: {f}", "ort": ""}]})
    gueltig = not any(s["status"] == "fehler" for s in schritte)
    return {"moeglich": True, "gueltig": gueltig, "profil": profil, "schritte": schritte}


# ---------------------------------------------------------------- Ansicht (KoSIT XRechnung-Visualisierung)
VIS = os.path.join(REGELN, "visualisierung")
VIS_STIL = """<style>
/* Jahresring: Farben des Programms, etwas kompakter (Inhalt und Aufbau bleiben die der KoSIT) */
body{background-color:#f4efe8!important;font-family:"Segoe UI",system-ui,sans-serif!important}
.menue{background-color:#3b3530!important}
.btnAktiv,.btnInaktiv,.tab{font-family:"Segoe UI",system-ui,sans-serif!important;font-size:17px!important}
.btnAktiv{color:#e0b07a!important}.btnAktiv:after{border-top-color:#3b3530!important}
.boxtitel{background-color:#9a6a3a!important}.boxtitelSub{background-color:#efe6da!important}
.wert{background-color:#faf7f2!important}
.boxzeile:has(> .wert:empty){display:none}   /* Felder ohne Inhalt ausblenden (wie in der PDF-Fassung der KoSIT) */.box,.boxtabelle{border-color:#ddd6cc!important}
</style>"""


def ansicht_html(xml_bytes):
    """HTML-Ansicht der Rechnung mit der offiziellen XRechnung-Visualisierung der KoSIT (Übersicht, Details, Zusätze,
    Anlagen, Laufzettel). → (html, None) oder (None, Grund)."""
    v = verfuegbar()
    if not v["saxon"]:
        return None, "nicht eingerichtet"
    if not os.path.isfile(os.path.join(VIS, "xrechnung-html.xsl")):
        return None, "Visualisierung fehlt im Programmordner"
    import eingangsrechnung
    try:
        eingangsrechnung.dtd_pruefen(xml_bytes)
        root = ET.fromstring(xml_bytes)
    except eingangsrechnung.LeseFehler:
        return None, "XML mit DTD wird aus Sicherheitsgründen nicht angezeigt"
    except ET.ParseError:
        return None, "XML nicht lesbar"
    name = _ln(root.tag)
    xsl = {"CrossIndustryInvoice": "cii-xr.xsl", "Invoice": "ubl-invoice-xr.xsl", "CreditNote": "ubl-creditnote-xr.xsl"}.get(name)
    if not xsl:
        return None, ("ZUGFeRD 1.0 kann die offizielle Ansicht nicht darstellen" if name == "CrossIndustryDocument"
                      else "keine E-Rechnung")
    import re as _re
    import xmlansicht
    text = _re.sub(r"^\s*<\?xml[^>]*\?>", "", xmlansicht._als_text(xml_bytes), count=1)
    with _sperre:
        try:
            _xslt("visualisierung/" + xsl)
            _xslt("visualisierung/xrechnung-html.xsl")
            proc = _cache["_proc"]
            xr = _cache["visualisierung/" + xsl].transform_to_string(xdm_node=proc.parse_xml(xml_text=text))
            html = _cache["visualisierung/xrechnung-html.xsl"].transform_to_string(xdm_node=proc.parse_xml(xml_text=_re.sub(r"^\s*<\?xml[^>]*\?>", "", xr, count=1)))
        except Exception as f:  # noqa: BLE001
            return None, f"Ansicht nicht möglich: {f}"
    if not html:
        return None, "Ansicht leer"
    html = html.replace("</head>", VIS_STIL + "</head>", 1)
    return html, None
