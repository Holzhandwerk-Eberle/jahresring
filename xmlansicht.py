"""XML-Ansicht: XML-Dateien und die eingebettete XML einer ZUGFeRD-/Factur-X-PDF anzeigen und prüfen.

Die Prüfung ist eine Plausibilitätsprüfung der wichtigsten Pflichtangaben nach EN 16931 (Rechnungsnummer, Datum,
Verkäufer, Käufer, Summen, Steuer, Leitweg-ID bei XRechnung). Sie ersetzt nicht den offiziellen Validator
(KoSIT-Prüftool bzw. Schematron), zeigt aber die häufigsten Fehler sofort."""
import io
import xml.etree.ElementTree as ET

import eingangsrechnung as er

ln = er.ln


class Fehler(Exception):
    pass


def _alle(e, name):
    return [x for x in e.iter() if ln(x.tag) == name]


def _erst(e, *pfad):
    """Erstes Element entlang eines Pfades aus lokalen Namen, an beliebiger Tiefe beginnend."""
    kandidaten = _alle(e, pfad[0])
    for k in kandidaten:
        x = k
        for s in pfad[1:]:
            x = next((c for c in x if ln(c.tag) == s), None)
            if x is None:
                break
        if x is not None:
            return x
    return None


def _t(e):
    return (e.text or "").strip() if e is not None else ""


def _z(e):
    return er.zahl(_t(e)) if e is not None and _t(e) else None


def extrahieren(roh, dateiname=""):
    """→ (xml_bytes, quelle). PDF: eingebettete Rechnungs-XML; XML: die Datei selbst."""
    name = (dateiname or "").lower()
    if roh[:5] == b"%PDF-" or name.endswith(".pdf"):
        import pypdf
        try:
            r = pypdf.PdfReader(io.BytesIO(roh))
            anh = r.attachments or {}
        except Exception as f:  # noqa: BLE001
            raise Fehler(f"Die PDF-Datei ist nicht lesbar ({f}).")
        namen = sorted(anh, key=lambda n: (n.lower() not in er.XML_NAMEN, not n.lower().endswith(".xml")))
        for n in namen:
            if n.lower().endswith(".xml") and anh[n]:
                return anh[n][0], f"in der PDF eingebettete Datei „{n}“"
        if anh:
            raise Fehler("Die PDF hat Anhänge, aber keine XML-Datei (" + ", ".join(list(anh)[:5]) + ").")
        raise Fehler("Die PDF enthält keine eingebettete XML – sie ist keine ZUGFeRD-/Factur-X-Rechnung.")
    if roh.lstrip()[:1] != b"<":
        raise Fehler("Die Datei ist weder XML noch PDF.")
    return roh, "XML-Datei"


def _cii_pruefen(root, p):
    doc = _erst(root, "ExchangedDocument")
    if doc is None:
        doc = _erst(root, "HeaderExchangedDocument")
    p("Rechnungsnummer (BT-1)", _t(_erst(doc, "ID")) if doc is not None else "")
    dt = _t(_erst(root, "IssueDateTime", "DateTimeString"))
    p("Rechnungsdatum (BT-2)", f"{dt[6:8]}.{dt[4:6]}.{dt[:4]}" if len(dt) == 8 and dt.isdigit() else dt)
    p("Rechnungsart (BT-3)", _t(_erst(doc, "TypeCode")) if doc is not None else "", warnung=True)
    p("Verkäufer Name (BT-27)", _t(_erst(root, "SellerTradeParty", "Name")))
    sp = _erst(root, "SellerTradeParty")
    st = _alle(sp if sp is not None else root, "SpecifiedTaxRegistration")
    p("Verkäufer USt-IdNr. oder Steuernummer (BT-31/32)", ", ".join(_t(_erst(x, "ID")) for x in st))
    p("Käufer Name (BT-44)", _t(_erst(root, "BuyerTradeParty", "Name")))
    p("Währung (BT-5)", _t(_erst(root, "InvoiceCurrencyCode")))
    # Summen der Rechnung: ZUGFeRD 2 / Factur-X / XRechnung „...HeaderMonetarySummation“; ZUGFeRD 1.0 heißt das Element
    # „SpecifiedTradeSettlementMonetarySummation“ und steht direkt in der Kopf-Abrechnung (gleich heißt es auch in jeder Zeile)
    summen = _erst(root, "SpecifiedTradeSettlementHeaderMonetarySummation")
    if summen is None:
        kopf = _erst(root, "SpecifiedSupplyChainTradeTransaction", "ApplicableSupplyChainTradeSettlement")
        if kopf is not None:
            summen = next((c for c in kopf if ln(c.tag) == "SpecifiedTradeSettlementMonetarySummation"), None)
    return summen, [(_z(_erst(z, "LineTotalAmount")) or 0) for z in _alle(root, "IncludedSupplyChainTradeLineItem")], \
        _t(_erst(root, "BuyerReference")), _t(_erst(root, "GuidelineSpecifiedDocumentContextParameter", "ID"))


def _als_text(b):
    """XML-Bytes als Text für die Anzeige; berücksichtigt eine abweichende Kodierung in der XML-Deklaration."""
    import re
    if b[:3] == b"\xef\xbb\xbf":
        b = b[3:]
    m = re.match(rb'<\?xml[^>]*encoding=["\']([A-Za-z0-9_.-]+)', b[:200])
    try:
        return b.decode(m.group(1).decode() if m else "utf-8")
    except (LookupError, UnicodeDecodeError):
        return b.decode("utf-8", "replace")


def pruefen(xml_bytes, quelle=""):
    try:
        er.dtd_pruefen(xml_bytes)
    except er.LeseFehler as f:
        return {"xml": _als_text(xml_bytes), "_roh": xml_bytes, "quelle": quelle, "wohlgeformt": False,
                "pruefungen": [{"stufe": "fehler", "text": str(f)}], "art": "", "profil": ""}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as f:
        return {"xml": _als_text(xml_bytes), "_roh": xml_bytes, "quelle": quelle, "wohlgeformt": False,
                "pruefungen": [{"stufe": "fehler", "text": f"XML nicht wohlgeformt: {f}"}], "art": "", "profil": ""}
    erg = {"xml": _als_text(xml_bytes), "_roh": xml_bytes, "quelle": quelle, "wohlgeformt": True, "pruefungen": [], "profil": "",
           "wurzel": ln(root.tag), "art": "", "uebersicht": None}

    def p(titel, wert, warnung=False):
        if wert:
            erg["pruefungen"].append({"stufe": "ok", "text": f"{titel}: {wert}"})
        else:
            erg["pruefungen"].append({"stufe": "warnung" if warnung else "fehler", "text": f"{titel} fehlt"})

    name = ln(root.tag)
    if name in ("CrossIndustryInvoice", "CrossIndustryDocument"):
        erg["art"] = "CII (ZUGFeRD / Factur-X / XRechnung)"
        summen, zeilen, leitweg, profil = _cii_pruefen(root, p)
        netto = _z(_erst(summen, "LineTotalAmount")) if summen is not None else None
        basis = _z(_erst(summen, "TaxBasisTotalAmount")) if summen is not None else None
        steuer = _z(_erst(summen, "TaxTotalAmount")) if summen is not None else None
        brutto = _z(_erst(summen, "GrandTotalAmount")) if summen is not None else None
        zahl = _z(_erst(summen, "DuePayableAmount")) if summen is not None else None
        iban = _t(_erst(root, "PayeePartyCreditorFinancialAccount", "IBANID"))
    elif name in ("Invoice", "CreditNote"):
        erg["art"] = "UBL (XRechnung)"
        p("Rechnungsnummer (BT-1)", _t(next((c for c in root if ln(c.tag) == "ID"), None)))
        p("Rechnungsdatum (BT-2)", _t(_erst(root, "IssueDate")))
        p("Verkäufer Name (BT-27)", _t(_erst(root, "AccountingSupplierParty", "Party", "PartyLegalEntity", "RegistrationName"))
          or _t(_erst(root, "AccountingSupplierParty", "Party", "PartyName", "Name")))
        p("Käufer Name (BT-44)", _t(_erst(root, "AccountingCustomerParty", "Party", "PartyLegalEntity", "RegistrationName"))
          or _t(_erst(root, "AccountingCustomerParty", "Party", "PartyName", "Name")))
        p("Währung (BT-5)", _t(_erst(root, "DocumentCurrencyCode")))
        lm = _erst(root, "LegalMonetaryTotal")
        netto = _z(_erst(lm, "LineExtensionAmount")) if lm is not None else None
        basis = _z(_erst(lm, "TaxExclusiveAmount")) if lm is not None else None
        brutto = _z(_erst(lm, "TaxInclusiveAmount")) if lm is not None else None
        zahl = _z(_erst(lm, "PayableAmount")) if lm is not None else None
        steuer = _z(_erst(root, "TaxTotal", "TaxAmount"))
        zeilen = [(_z(_erst(z, "LineExtensionAmount")) or 0) for z in _alle(root, "InvoiceLine") + _alle(root, "CreditNoteLine")]
        leitweg = _t(_erst(root, "BuyerReference"))
        profil = _t(_erst(root, "CustomizationID"))
        iban = _t(_erst(root, "PayeeFinancialAccount", "ID"))
    else:
        erg["art"] = "sonstiges XML"
        erg["pruefungen"].append({"stufe": "hinweis", "text": f"Wurzelelement „{name}“: keine E-Rechnung, nur Anzeige."})
        return erg
    erg["profil"] = profil
    if name == "CrossIndustryDocument" or "urn:ferd:" in profil.lower():
        erg["art"] = "CII ZUGFeRD 1.0"
        erg["pruefungen"].append({"stufe": "hinweis", "text": "ZUGFeRD 1.0 ist das Vorgängerformat und entspricht nicht der EN 16931. Es gilt deshalb nicht als "
                                  "E-Rechnung im Sinne von § 14 UStG, sondern als sonstige Rechnung (in der Übergangszeit weiter zulässig). "
                                  "Die Daten lassen sich trotzdem lesen und buchen."})
    p("Profil / Spezifikation (BT-24)", profil)
    ist_xr = "xrechnung" in profil.lower()
    if ist_xr:
        p("Leitweg-ID / Käuferreferenz (BT-10, Pflicht bei XRechnung)", leitweg)
    elif leitweg:
        erg["pruefungen"].append({"stufe": "ok", "text": f"Käuferreferenz (BT-10): {leitweg}"})
    if "minimum" in profil.lower() or "basicwl" in profil.lower():
        erg["pruefungen"].append({"stufe": "warnung", "text": "Profil MINIMUM/BASIC WL: keine Rechnungszeilen, gilt in Deutschland nicht als E-Rechnung."})
    p("Summe der Positionen (BT-106)", f"{netto:.2f}" if netto is not None else "")
    p("Gesamtbetrag brutto (BT-112)", f"{brutto:.2f}" if brutto is not None else "")
    p("Zahlbetrag (BT-115)", f"{zahl:.2f}" if zahl is not None else "")
    if zeilen and netto is not None:
        s = round(sum(zeilen), 2)
        erg["pruefungen"].append({"stufe": "ok" if abs(s - netto) < 0.015 else "fehler",
                                  "text": f"{len(zeilen)} Rechnungszeilen, Summe {s:.2f} " + ("= Positionssumme" if abs(s - netto) < 0.015 else f"≠ Positionssumme {netto:.2f}")})
    elif not zeilen:
        erg["pruefungen"].append({"stufe": "warnung", "text": "Keine Rechnungszeilen enthalten."})
    if basis is not None and steuer is not None and brutto is not None:
        ok = abs(basis + steuer - brutto) < 0.015
        erg["pruefungen"].append({"stufe": "ok" if ok else "fehler",
                                  "text": f"Netto {basis:.2f} + Steuer {steuer:.2f} " + ("= Brutto" if ok else f"≠ Brutto {brutto:.2f}")})
    if brutto is not None and abs(brutto) < 0.005:
        erg["pruefungen"].append({"stufe": "warnung", "text": "Der Rechnungsbetrag ist 0,00."})
    if iban:
        erg["pruefungen"].append({"stufe": "ok", "text": f"IBAN Zahlungsempfänger (BT-84): {iban}"})
    try:
        les = er.lies_xml(xml_bytes)
        erg["uebersicht"] = {"rechnung": les.get("rechnung"), "verkaeufer": les.get("lieferant"), "zeilen": les.get("zeilen")[:200],
                             "format": les.get("format")}
    except er.LeseFehler as f:
        erg["pruefungen"].append({"stufe": "warnung", "text": str(f)})
    return erg


def anzeigen(roh, dateiname=""):
    xml, quelle = extrahieren(roh, dateiname)
    erg = pruefen(xml, quelle)
    erg["dateiname"] = dateiname
    return erg
