"""Eingangsrechnungen lesen: ZUGFeRD 1.0 / 2.x / Factur-X (CII), XRechnung (CII und UBL) und – als Notlösung –
Kopfdaten aus dem Text einer normalen PDF. Ergebnis ist ein einheitliches Wörterbuch; die Zuordnung zu Lieferant,
Material, Auftrag und Werkzeug macht app.py."""
import io
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from kern import kfm

EINHEITEN = {"H87": "Stk.", "C62": "Stk.", "PCE": "Stk.", "EA": "Stk.", "NAR": "Stk.", "ST": "Stk.", "XPP": "Stk.",
             "XUN": "Stk.", "NPR": "Paar", "XCT": "Karton", "CT": "Karton",
             "XPX": "Palette", "XPF": "Palette", "XBG": "Beutel", "XSA": "Sack", "XBO": "Flasche", "XJR": "Glas",
             "GRM": "g", "MLT": "ml", "CMT": "cm", "MMT": "mm", "DMT": "dm",
             "MIN": "Min.", "WEE": "Woche", "MON": "Monat", "ANN": "Jahr", "KWH": "kWh", "TU": "Tube", "BX": "Packung", "PK": "Packung",
             "MTK": "m²", "MTR": "lfm.", "LM": "lfm.", "MTQ": "m³", "LTR": "Liter", "KGM": "kg", "SET": "Satz",
             "PR": "Paar", "HUR": "Std.", "LS": "Pauschale", "XRO": "Rolle", "RO": "Rolle", "XPK": "Packung", "PA": "Packung",
             "XBX": "Packung", "XTU": "Tube", "XCA": "Dose", "TNE": "t", "DAY": "Tag", "KMT": "km"}


class LeseFehler(Exception):
    pass


DTD_HINWEIS = ("Die XML-Datei enthält eine DTD bzw. Entity-Deklaration (<!DOCTYPE …>). E-Rechnungen enthalten so etwas nicht; "
               "aus Sicherheitsgründen wird die Datei nicht gelesen.")


def dtd_pruefen(daten):
    """Schutz vor präparierten XML-Dateien (Entity-Expansion, Zugriff auf lokale Dateien über externe Entities):
    E-Rechnungen haben nie eine DTD, also wird jede Datei mit <!DOCTYPE oder <!ENTITY abgelehnt."""
    roh = daten if isinstance(daten, (bytes, bytearray)) else str(daten or "").encode("utf-8", "ignore")
    if re.search(rb"<!\s*(DOCTYPE|ENTITY)", bytes(roh).replace(b"\x00", b""), re.I):
        raise LeseFehler(DTD_HINWEIS)


def ln(tag):
    return tag.split("}")[-1] if isinstance(tag, str) else ""


def kind(e, *namen):
    """Erstes direktes Kind mit einem der Namen."""
    if e is None:
        return None
    for c in e:
        if ln(c.tag) in namen:
            return c
    return None


def kinder(e, *namen):
    return [c for c in e if ln(c.tag) in namen] if e is not None else []


def pfad(e, *schritte):
    """Folgt einem Pfad aus lokalen Namen; jeder Schritt darf mehrere Namen mit | enthalten."""
    for s in schritte:
        e = kind(e, *s.split("|"))
        if e is None:
            return None
    return e


def tiefe(e, name):
    """Erster Nachfahre mit diesem Namen."""
    if e is None:
        return None
    for x in e.iter():
        if ln(x.tag) == name:
            return x
    return None


def text(e):
    return (e.text or "").strip() if e is not None else ""


def zahl(s):
    s = (s or "").strip().replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def datum_cii(e):
    """DateTimeString im Format 102 (JJJJMMTT) oder ISO."""
    s = text(tiefe(e, "DateTimeString") if e is not None and ln(e.tag) != "DateTimeString" else e)
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    return ""


def datum_de(s):
    m = re.match(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", s or "")
    if not m:
        return ""
    t, mo, j = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if j < 100:
        j += 2000
    try:
        return date(j, mo, t).isoformat()
    except ValueError:
        return ""


def plus(iso, tage):
    try:
        return (date.fromisoformat(iso) + timedelta(days=int(tage))).isoformat()
    except (ValueError, TypeError):
        return ""


def iban_normal(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def ustid_normal(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def zahlungsbedingung(texte, datum_iso):
    """Skonto und Fälligkeit aus Freitext: „10T2%-N30“, „#SKONTO#TAGE=14#PROZENT=2.00#“, „2 % Skonto bei Zahlung
    innerhalb 10 Tagen“, „Bei Zahlung bis 18.10.2026 - Skonto: 2,00%“, „30 Tage netto“, „zahlbar bis 23.07.2026“."""
    erg = {}
    for t in texte:
        t = t or ""
        m = re.search(r"#SKONTO#TAGE=(\d+)#PROZENT=([\d.,]+)#", t)
        if m:
            erg.setdefault("skonto", zahl(m.group(2)))
            erg.setdefault("skonto_bis", plus(datum_iso, m.group(1)))
        m = re.search(r"(\d+)\s*T(?:age)?\s*([\d.,]+)\s*%\s*-?\s*N(?:etto)?\s*(\d+)", t, re.I)
        if m:
            erg.setdefault("skonto", zahl(m.group(2)))
            erg.setdefault("skonto_bis", plus(datum_iso, m.group(1)))
            erg.setdefault("faellig", plus(datum_iso, m.group(3)))
        m = re.search(r"([\d.,]+)\s*%\s*Skonto[^.\n]*?(\d+)\s*Tag", t, re.I) or re.search(r"(\d+)\s*Tag\w*[^.\n]*?([\d.,]+)\s*%\s*Skonto", t, re.I)
        if m:
            a, b = m.group(1), m.group(2)
            pz, tg = (a, b) if "%" in t[m.start():m.start() + len(a) + 3] else (b, a)
            erg.setdefault("skonto", zahl(pz))
            erg.setdefault("skonto_bis", plus(datum_iso, tg))
        m = re.search(r"bis\s*(\d{1,2}\.\d{1,2}\.\d{2,4})[^%\n]{0,30}?Skonto[^\d\n]{0,5}([\d.,]+)\s*%", t, re.I)
        if m:
            erg.setdefault("skonto", zahl(m.group(2)))
            erg.setdefault("skonto_bis", datum_de(m.group(1)))
        m = re.search(r"(?:netto|ohne Abzug)[^\n]{0,25}?bis\s*(?:zum\s*)?(\d{1,2}\.\d{1,2}\.\d{2,4})", t, re.I) or \
            re.search(r"zahlbar\s*bis\s*(?:zum\s*)?(\d{1,2}\.\d{1,2}\.\d{2,4})", t, re.I)
        if m:
            erg.setdefault("faellig", datum_de(m.group(1)))
        m = re.search(r"(\d+)\s*Tage?n?\s*(?:nach\s*Rechnungsdatum\s*)?(?:netto|ohne\s*Abzug)", t, re.I) or \
            re.search(r"innerhalb\s*(?:von\s*)?(\d+)\s*Tage?n?[^\n]{0,30}ohne\s*Abzug", t, re.I) or \
            re.search(r"netto\s*(\d+)\s*Tage", t, re.I)
        if m and datum_iso:
            erg.setdefault("faellig", plus(datum_iso, m.group(1)))
    return erg


def leer_ergebnis(fmt):
    return {"format": fmt, "rechnung": {}, "lieferant": {}, "zeilen": [], "hinweise": [], "texte": []}


# ------------------------------------------------------------------ CII (ZUGFeRD 1/2, Factur-X, XRechnung CII)
def lies_cii(root):
    zf1 = ln(root.tag) == "CrossIndustryDocument"
    erg = leer_ergebnis("ZUGFeRD 1.0" if zf1 else "ZUGFeRD/XRechnung")
    kontext = tiefe(root, "GuidelineSpecifiedDocumentContextParameter")
    profil = text(kind(kontext, "ID"))
    if "xrechnung" in profil.lower():
        erg["format"] = "XRechnung (CII)"
    elif "factur-x" in profil.lower() or "zugferd" in profil.lower() or "en16931" in profil.lower():
        erg["format"] = "ZUGFeRD/Factur-X"
    doc = kind(root, "ExchangedDocument", "HeaderExchangedDocument")
    tx = kind(root, "SupplyChainTradeTransaction", "SpecifiedSupplyChainTradeTransaction")
    if doc is None or tx is None:
        raise LeseFehler("Die XML-Datei ist keine vollständige ZUGFeRD-/XRechnung.")
    agr = kind(tx, "ApplicableHeaderTradeAgreement", "ApplicableSupplyChainTradeAgreement")
    lief = kind(tx, "ApplicableHeaderTradeDelivery", "ApplicableSupplyChainTradeDelivery")
    sett = kind(tx, "ApplicableHeaderTradeSettlement", "ApplicableSupplyChainTradeSettlement")
    r = erg["rechnung"]
    r["nummer"] = text(kind(doc, "ID"))
    r["typ"] = text(kind(doc, "TypeCode"))
    r["datum"] = datum_cii(kind(doc, "IssueDateTime"))
    r["lieferdatum"] = datum_cii(tiefe(lief, "OccurrenceDateTime")) if lief is not None else ""
    for n in kinder(doc, "IncludedNote"):
        erg["texte"].append(text(kind(n, "Content")))
    # Verkäufer
    s = kind(agr, "SellerTradeParty")
    adr = kind(s, "PostalTradeAddress")
    L = erg["lieferant"]
    L["name"] = text(kind(s, "Name"))
    L["strasse"] = text(kind(adr, "LineOne"))
    L["plz"] = text(kind(adr, "PostcodeCode"))
    L["ort"] = text(kind(adr, "CityName"))
    L["land"] = text(kind(adr, "CountryID"))
    for reg in kinder(s, "SpecifiedTaxRegistration"):
        idt = kind(reg, "ID")
        if idt is not None and idt.attrib.get("schemeID") == "VA":
            L["ustid"] = ustid_normal(text(idt))
        elif idt is not None and idt.attrib.get("schemeID") == "FC":
            L["steuernr"] = text(idt)
    kontakt = kind(s, "DefinedTradeContact")
    L["email"] = text(tiefe(kontakt, "URIID")) if kontakt is not None else ""
    L["telefon"] = text(tiefe(kontakt, "CompleteNumber")) if kontakt is not None else ""
    # Referenzen (Bestellung/Kommission) – zum Erkennen einer Auftragsnummer
    for name in ("BuyerReference",):
        if text(kind(agr, name)):
            erg["texte"].append(text(kind(agr, name)))
    for d in kinder(agr, "BuyerOrderReferencedDocument"):
        erg["texte"].append(text(kind(d, "IssuerAssignedID", "ID")))
    # Zahlung
    r["waehrung"] = text(kind(sett, "InvoiceCurrencyCode")) or "EUR"
    r["verwendungszweck"] = text(kind(sett, "PaymentReference"))
    for pm in kinder(sett, "SpecifiedTradeSettlementPaymentMeans"):
        konto = kind(pm, "PayeePartyCreditorFinancialAccount")
        iban = iban_normal(text(kind(konto, "IBANID")))
        if not iban:
            m = re.search(r"\b([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?)", text(kind(konto, "ProprietaryID")))
            iban = iban_normal(m.group(1)) if m else ""
        bic = text(tiefe(kind(pm, "PayeeSpecifiedCreditorFinancialInstitution"), "BICID"))
        if not bic:
            m = re.search(r"BIC:?\s*([A-Z0-9 ]{8,14})", text(kind(konto, "ProprietaryID")))
            bic = m.group(1).replace(" ", "") if m else ""
        if iban and not L.get("iban"):
            L["iban"], L["bic"] = iban, bic
        code = text(kind(pm, "TypeCode"))
        if code in ("59",):
            r["lastschrift"] = True
    # Steuer
    steuern = []
    for t in kinder(sett, "ApplicableTradeTax"):
        steuern.append({"satz": zahl(text(kind(t, "RateApplicablePercent", "ApplicablePercent"))),
                        "basis": zahl(text(kind(t, "BasisAmount"))), "betrag": zahl(text(kind(t, "CalculatedAmount")))})
    if steuern:
        r["ust_satz"] = max(steuern, key=lambda x: x["basis"])["satz"]
    # Zahlungsbedingungen
    texte_zb, faellig = [], []
    for pt in kinder(sett, "SpecifiedTradePaymentTerms"):
        texte_zb.append(text(kind(pt, "Description")))
        fd = datum_cii(kind(pt, "DueDateDateTime"))
        if fd:
            faellig.append(fd)
        dt = kind(pt, "ApplicableTradePaymentDiscountTerms")
        if dt is not None and zahl(text(kind(dt, "CalculationPercent"))):
            r["skonto"] = zahl(text(kind(dt, "CalculationPercent")))
            tage = text(kind(dt, "BasisPeriodMeasure"))
            if fd:
                r["skonto_bis"] = fd
            elif tage:
                r["skonto_bis"] = plus(r["datum"], int(zahl(tage)))
    r["zahlungsbedingung"] = " · ".join(t for t in texte_zb if t)
    if faellig:
        r["faellig"] = max(faellig)
        if r.get("skonto") and not r.get("skonto_bis") and len(faellig) > 1:
            r["skonto_bis"] = min(faellig)
    for k, v in zahlungsbedingung(texte_zb, r["datum"]).items():
        r.setdefault(k, v)
    # Summen
    summen = kind(sett, "SpecifiedTradeSettlementHeaderMonetarySummation", "SpecifiedTradeSettlementMonetarySummation")
    r["netto"] = zahl(text(kind(summen, "TaxBasisTotalAmount")))
    # Steuerbetrag in der Rechnungswährung (daneben kann einer in einer abweichenden Steuerwährung stehen)
    steuern = kinder(summen, "TaxTotalAmount")
    st = next((x for x in steuern if (x.get("currencyID") or r.get("waehrung")) == r.get("waehrung")), steuern[0] if steuern else None)
    r["ust"] = zahl(text(st))
    r["brutto"] = zahl(text(kind(summen, "GrandTotalAmount")))
    r["vorausbezahlt"] = zahl(text(kind(summen, "TotalPrepaidAmount")))
    zb = kind(summen, "DuePayableAmount")
    r["zahlbetrag"] = zahl(text(zb)) if zb is not None else r["brutto"]
    if r["brutto"] and r["zahlbetrag"] < 0.005 and r["vorausbezahlt"]:
        r["bereits_bezahlt"] = True
    # Zeilen
    for li in kinder(tx, "IncludedSupplyChainTradeLineItem"):
        prod = kind(li, "SpecifiedTradeProduct")
        a = kind(li, "SpecifiedLineTradeAgreement", "SpecifiedSupplyChainTradeAgreement")
        dl = kind(li, "SpecifiedLineTradeDelivery", "SpecifiedSupplyChainTradeDelivery")
        st = kind(li, "SpecifiedLineTradeSettlement", "SpecifiedSupplyChainTradeSettlement")
        menge_e = kind(dl, "BilledQuantity")
        menge = zahl(text(menge_e))
        code = (menge_e.attrib.get("unitCode") if menge_e is not None else "") or ""
        preis = kind(a, "NetPriceProductTradePrice")
        basis = zahl(text(kind(preis, "BasisQuantity"))) or 1
        ep = zahl(text(kind(preis, "ChargeAmount"))) / basis
        summe = zahl(text(tiefe(st, "LineTotalAmount")))
        steuer = kind(st, "ApplicableTradeTax")
        satz_e = tiefe(steuer, "RateApplicablePercent")
        if satz_e is None:
            satz_e = tiefe(steuer, "ApplicablePercent")
        satz = zahl(text(satz_e)) if satz_e is not None else r.get("ust_satz", 19)
        name = text(kind(prod, "Name"))
        beschr = text(kind(prod, "Description"))
        notiz = " ".join(text(kind(n, "Content")) for n in kinder(kind(li, "AssociatedDocumentLineDocument"), "IncludedNote"))
        ref = text(tiefe(kind(a, "BuyerOrderReferencedDocument"), "IssuerAssignedID"))
        erg["zeilen"].append({
            "artnr": text(kind(prod, "SellerAssignedID")), "ean": text(kind(prod, "GlobalID")),
            "bezeichnung": name + (("\n" + beschr) if beschr and beschr != name else ""),
            "menge": menge, "einheit": EINHEITEN.get(code.upper(), code), "einheit_code": code,
            "ep": round(summe / menge, 4) if menge else round(ep, 4), "listenpreis": round(ep, 4), "netto": kfm(summe),
            "ust_satz": satz, "hinweis": " ".join(x for x in (notiz, ref) if x)})
        if ref:
            erg["texte"].append(ref)
    # Kopf-Zu-/Abschläge (Fracht, Logistikpauschale …) als eigene Zeilen
    for ac in kinder(sett, "SpecifiedTradeAllowanceCharge"):
        zuschlag = text(tiefe(ac, "Indicator")).lower() == "true"
        betrag = zahl(text(kind(ac, "ActualAmount")))
        if not betrag:
            continue
        grund = text(kind(ac, "Reason")) or {"FC": "Fracht", "ABL": "Verpackung", "AAJ": "Mindermengenzuschlag"}.get(
            text(kind(ac, "ReasonCode")), "Zuschlag" if zuschlag else "Abzug")
        erg["zeilen"].append({"artnr": "", "ean": "", "bezeichnung": grund, "menge": 1, "einheit": "Pauschale", "einheit_code": "",
                              "ep": betrag if zuschlag else -betrag, "listenpreis": 0, "netto": betrag if zuschlag else -betrag,
                              "ust_satz": r.get("ust_satz", 19), "hinweis": "", "zuschlag": True})
    if r["typ"] in ("381", "261"):
        erg["hinweise"].append("Das ist eine Gutschrift bzw. Rechnungskorrektur.")
    return erg


# ------------------------------------------------------------------ UBL (XRechnung UBL)
def lies_ubl(root):
    erg = leer_ergebnis("XRechnung (UBL)")
    gutschrift = ln(root.tag) == "CreditNote"
    r, L = erg["rechnung"], erg["lieferant"]
    r["nummer"] = text(kind(root, "ID"))
    r["datum"] = text(kind(root, "IssueDate"))[:10]
    r["faellig"] = text(kind(root, "DueDate"))[:10]
    r["typ"] = "381" if gutschrift else text(kind(root, "InvoiceTypeCode"))
    for n in kinder(root, "Note"):
        erg["texte"].append(text(n))
    if text(kind(root, "BuyerReference")):
        erg["texte"].append(text(kind(root, "BuyerReference")))
    erg["texte"].append(text(pfad(root, "OrderReference", "ID")))
    party = pfad(root, "AccountingSupplierParty", "Party")
    L["name"] = text(pfad(party, "PartyLegalEntity", "RegistrationName")) or text(pfad(party, "PartyName", "Name"))
    adr = kind(party, "PostalAddress")
    L["strasse"] = text(kind(adr, "StreetName"))
    L["plz"] = text(kind(adr, "PostalZone"))
    L["ort"] = text(kind(adr, "CityName"))
    L["land"] = text(pfad(adr, "Country", "IdentificationCode"))
    for pts in kinder(party, "PartyTaxScheme"):
        cid = text(kind(pts, "CompanyID"))
        if re.match(r"[A-Z]{2}", cid):
            L["ustid"] = ustid_normal(cid)
        elif cid:
            L["steuernr"] = cid
    L["email"] = text(pfad(party, "Contact", "ElectronicMail"))
    L["telefon"] = text(pfad(party, "Contact", "Telephone"))
    r["lieferdatum"] = text(pfad(root, "Delivery", "ActualDeliveryDate"))[:10]
    for pm in kinder(root, "PaymentMeans"):
        konto = kind(pm, "PayeeFinancialAccount")
        if konto is not None and not L.get("iban"):
            L["iban"] = iban_normal(text(kind(konto, "ID")))
            L["bic"] = text(pfad(konto, "FinancialInstitutionBranch", "ID"))
        r["verwendungszweck"] = r.get("verwendungszweck") or text(kind(pm, "PaymentID"))
    texte_zb = [text(kind(pt, "Note")) for pt in kinder(root, "PaymentTerms")]
    r["zahlungsbedingung"] = " · ".join(t for t in texte_zb if t)
    for k, v in zahlungsbedingung(texte_zb, r["datum"]).items():
        r.setdefault(k, v)
    sub = [kind(t, "TaxCategory") for t in kinder(kind(root, "TaxTotal"), "TaxSubtotal")]
    saetze = [zahl(text(kind(c, "Percent"))) for c in sub if c is not None]
    if saetze:
        r["ust_satz"] = max(saetze)
    tot = kind(root, "LegalMonetaryTotal")
    r["netto"] = zahl(text(kind(tot, "TaxExclusiveAmount")))
    r["brutto"] = zahl(text(kind(tot, "TaxInclusiveAmount")))
    r["ust"] = kfm(r["brutto"] - r["netto"])
    r["vorausbezahlt"] = zahl(text(kind(tot, "PrepaidAmount")))
    r["zahlbetrag"] = zahl(text(kind(tot, "PayableAmount")))
    if r["brutto"] and r["zahlbetrag"] < 0.005 and r["vorausbezahlt"]:
        r["bereits_bezahlt"] = True
    for li in kinder(root, "InvoiceLine", "CreditNoteLine"):
        item = kind(li, "Item")
        q = kind(li, "InvoicedQuantity", "CreditedQuantity")
        menge = zahl(text(q))
        code = (q.attrib.get("unitCode") if q is not None else "") or ""
        summe = zahl(text(kind(li, "LineExtensionAmount")))
        basis = zahl(text(pfad(li, "Price", "BaseQuantity"))) or 1
        ep = zahl(text(pfad(li, "Price", "PriceAmount"))) / basis
        erg["zeilen"].append({
            "artnr": text(pfad(item, "SellersItemIdentification", "ID")), "ean": text(pfad(item, "StandardItemIdentification", "ID")),
            "bezeichnung": text(kind(item, "Name")) + (("\n" + text(kind(item, "Description"))) if text(kind(item, "Description")) else ""),
            "menge": menge, "einheit": EINHEITEN.get(code.upper(), code), "einheit_code": code,
            "ep": round(summe / menge, 4) if menge else round(ep, 4), "listenpreis": round(ep, 4), "netto": kfm(summe),
            "ust_satz": zahl(text(pfad(item, "ClassifiedTaxCategory", "Percent"))),
            "hinweis": text(kind(li, "Note"))})
    # Kopf-Zu-/Abschläge (Fracht, Verpackung, Rabatt …) als eigene Zeilen – wie bei CII
    for ac in kinder(root, "AllowanceCharge"):
        zuschlag = text(kind(ac, "ChargeIndicator")).lower() == "true"
        betrag = zahl(text(kind(ac, "Amount")))
        if not betrag:
            continue
        grund = text(kind(ac, "AllowanceChargeReason")) or {"FC": "Fracht", "ABL": "Verpackung", "AAJ": "Mindermengenzuschlag"}.get(
            text(kind(ac, "AllowanceChargeReasonCode")), "Zuschlag" if zuschlag else "Abzug")
        erg["zeilen"].append({"artnr": "", "ean": "", "bezeichnung": grund, "menge": 1, "einheit": "Pauschale", "einheit_code": "",
                              "ep": betrag if zuschlag else -betrag, "listenpreis": 0, "netto": betrag if zuschlag else -betrag,
                              "ust_satz": zahl(text(pfad(ac, "TaxCategory", "Percent"))) or r.get("ust_satz", 19), "hinweis": "", "zuschlag": True})
    if gutschrift:
        erg["_creditnote"] = True
        erg["hinweise"].append("Das ist eine Gutschrift.")
    return erg


def lies_xml(daten):
    dtd_pruefen(daten)
    try:
        root = ET.fromstring(daten)
    except ET.ParseError as f:
        raise LeseFehler(f"Die XML-Datei ist nicht lesbar ({f}).")
    name = ln(root.tag)
    if name in ("CrossIndustryInvoice", "CrossIndustryDocument"):
        return lies_cii(root)
    if name in ("Invoice", "CreditNote"):
        return lies_ubl(root)
    raise LeseFehler("Die XML-Datei ist keine E-Rechnung (weder ZUGFeRD/XRechnung CII noch UBL).")


# ------------------------------------------------------------------ PDF
XML_NAMEN = ("factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml", "zugferd.xml")


def pdf_anhang(daten):
    """Liefert die eingebettete E-Rechnungs-XML einer PDF (oder None)."""
    import pypdf
    try:
        r = pypdf.PdfReader(io.BytesIO(daten))
        anh = r.attachments or {}
    except Exception as f:  # noqa: BLE001
        raise LeseFehler(f"Die PDF-Datei ist nicht lesbar ({f}).")
    for name, inhalte in anh.items():
        if name.lower() in XML_NAMEN and inhalte:
            return inhalte[0]
    for name, inhalte in anh.items():
        if name.lower().endswith(".xml") and inhalte:
            return inhalte[0]
    return None


def pdf_text(daten):
    import pypdf
    try:
        r = pypdf.PdfReader(io.BytesIO(daten))
        return "\n".join((p.extract_text() or "") for p in r.pages)
    except Exception:  # noqa: BLE001
        return ""


BETRAG = r"(-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2}|-?\d+\.\d{2})"


def lies_text(t, eigen):
    """Notlösung für PDF ohne E-Rechnung: nur Kopfdaten, alle als Vorschlag zum Prüfen."""
    erg = leer_ergebnis("PDF ohne E-Rechnung")
    r, L = erg["rechnung"], erg["lieferant"]
    erg["hinweise"].append("Diese PDF enthält keine E-Rechnung. Die Kopfdaten sind aus dem Text geraten – bitte prüfen. "
                           "Rechnungszeilen bei Bedarf selbst eintragen.")
    eigene_iban = {iban_normal(x) for x in eigen.get("iban", []) if x}
    eigene_ust = {ustid_normal(x) for x in eigen.get("ustid", []) if x}
    zeilen = [z.strip() for z in t.splitlines()]
    # Kopfzeile mit Spalten („Kunden-Nr Rechnung-Nr Datum“) und Werten in der Zeile darunter
    for i, z in enumerate(zeilen[:-1]):
        koepfe = z.split()
        werte = zeilen[i + 1].split()
        if len(koepfe) == len(werte) and len(koepfe) > 1:
            for k, w in zip(koepfe, werte):
                if re.match(r"Rechnung(s)?-?(Nr|nummer)", k, re.I) and re.match(r"[A-Z0-9][A-Z0-9/\-_.]{3,}$", w, re.I):
                    r["nummer"] = w
                if re.match(r"(Rechnungs)?datum$", k, re.I) and datum_de(w):
                    r["datum"] = datum_de(w)
    m = None if r.get("nummer") else (re.search(r"Rechnung(?:s)?[- ]?(?:Nr\.?|nummer|-Nr\.?)\s*[:.]?\s*(?:Datum\s*)?(?:\d{1,2}[./]\d{1,2}[./]\d{4})?\s*([A-Z0-9][A-Z0-9/\-_.]{3,})", t, re.I)
         or re.search(r"Beleg(?:nummer|-Nr\.?)\s*[:.]?\s*([A-Z0-9][A-Z0-9/\-_.]{3,})", t, re.I)
         or re.search(r"Rechnung-Nr\s+Datum\s*\n\s*\S+\s+(\S+)\s+\d", t))
    if m:
        r["nummer"] = m.group(1).strip(".")
    m = None if r.get("datum") else re.search(r"(?:Rechnungs|Beleg)?datum\s*[:.]?\s*(\d{1,2}[./]\d{1,2}[./]\d{4})", t, re.I) or \
        re.search(r"Datum\s*\n?\s*(?:\S+\s+){0,2}(\d{1,2}[./]\d{1,2}[./]\d{4})", t, re.I) or \
        re.search(r"(\d{1,2}[./]\d{1,2}[./]\d{4})", t)
    if m:
        r["datum"] = datum_de(m.group(1))
    for muster in (r"(?:Endbetrag|Rechnungssumme|Rechnungsbetrag|Gesamtsumme|Gesamtbetrag|Bruttobetrag|Zahlbetrag|zu zahlen|Summe brutto)[^\n\d-]{0,25}" + BETRAG,
                   r"Brutto-?\s*Betrag:?[^\n]*?" + BETRAG + r"\s*$"):
        treffer = re.findall(muster, t, re.I | re.M)
        if treffer:
            r["zahlbetrag"] = r["brutto"] = zahl(treffer[-1])
            break
    m = re.search(r"Netto(?:summe|betrag)?[^\n\d-]{0,15}" + BETRAG, t, re.I)
    if m:
        r["netto"] = zahl(m.group(1))
    m = re.search(r"\+?\s*(\d{1,2}(?:,\d)?)\s*%\s*(?:MwSt|Mehrwertsteuer|USt)", t, re.I) or re.search(r"(?:MwSt|USt)\.?\s*(\d{1,2})\s*%", t, re.I)
    r["ust_satz"] = zahl(m.group(1)) if m else 19.0
    for m in re.finditer(r"\b(DE\d{2}(?:\s?\d{2,4}){4,6})", t):
        iban = iban_normal(m.group(1))
        if len(iban) == 22 and iban not in eigene_iban:
            L["iban"] = iban
            b = re.search(r"BIC:?\s*([A-Z]{4}\s?[A-Z]{2}\s?[A-Z0-9]{2}(?:\s?[A-Z0-9]{3})?)", t[max(0, m.start() - 80):m.end() + 60])
            if b:
                L["bic"] = b.group(1).replace(" ", "")
            break
    for m in re.finditer(r"\b(DE\s?\d{3}\s?\d{3}\s?\d{3})\b", t):
        u = ustid_normal(m.group(1))
        if u not in eigene_ust:
            L["ustid"] = u
            break
    for k, v in zahlungsbedingung([t], r.get("datum", "")).items():
        r.setdefault(k, v)
    m = re.search(r"Zahlungsbedingung(?:en)?\s*:\s*([^\n]{3,80})", t, re.I) or re.search(r"Zahlungskonditionen\s*([^\n]{3,80})", t, re.I)
    if m:
        r["zahlungsbedingung"] = m.group(1).strip()
    if re.search(r"Zahlungsbedingung\w*\s*:?\s*(PayPal|Kreditkarte|bereits bezahlt|Vorkasse|Lastschrift)", t, re.I):
        r["bereits_bezahlt"] = True
        r["bezahlart"] = re.search(r"(PayPal|Kreditkarte|Vorkasse|Lastschrift)", t, re.I).group(1) if re.search(r"(PayPal|Kreditkarte|Vorkasse|Lastschrift)", t, re.I) else ""
    # Lieferantenname: erste Zeile mit Rechtsform, die nicht die eigene Firma ist
    eigene_namen = [x.lower() for x in eigen.get("namen", []) if x]
    for z in zeilen:
        m = re.match(r"([A-ZÄÖÜ][\wÄÖÜäöüß&.'\- ]{1,60}?\b(?:GmbH(?:\s*&\s*Co\.?\s*KG)?|SE\s*&\s*Co\.?\s*KG|KG|AG|SE|e\.\s?K\.|OHG|UG|GbR|eG))(?=$|[\s,])", z)
        if m and not any(n and n in m.group(1).lower() for n in eigene_namen):
            L["name"] = m.group(1).strip()
            break
    erg["texte"].append(t[:6000])
    return erg


def gutschrift_vorzeichen(erg):
    """Gutschrift/Rechnungskorrektur des Lieferanten (CII 381/261, UBL CreditNote): die Beträge stehen in der E-Rechnung
    positiv, bedeuten aber Geld zurück. Sie werden als Minusbeträge übernommen, damit kein Zahlungsauftrag über den
    Betrag entsteht und Kosten gemindert statt erhöht werden."""
    r = erg["rechnung"]
    if not (r.get("typ") in ("381", "261") or erg.get("format") == "XRechnung (UBL)" and erg.get("_creditnote")):
        return erg
    erg["gutschrift"] = True
    if (r.get("brutto") or 0) > 0 or (r.get("zahlbetrag") or 0) > 0:
        for k in ("netto", "ust", "brutto", "zahlbetrag", "vorausbezahlt"):
            if r.get(k):
                r[k] = -abs(r[k])
        for z in erg["zeilen"]:
            z["netto"] = -z.get("netto", 0)
            z["ep"] = -z.get("ep", 0)
    erg["hinweise"] = [h for h in erg["hinweise"] if "Gutschrift" not in h]
    erg["hinweise"].append("Das ist eine Gutschrift bzw. Rechnungskorrektur des Lieferanten. Die Beträge sind als Minusbeträge "
                           "übernommen (Geld zurück); Lagerzugänge werden dafür nicht gebucht.")
    return erg


def lesen(daten, dateiname, eigen):
    """Einstieg: Bytes + Dateiname → einheitliches Ergebnis. eigen = eigene IBANs/USt-IdNr./Namen zum Ausschließen."""
    name = (dateiname or "").lower()
    if name.endswith(".xml") or daten[:200].lstrip().startswith(b"<"):
        erg = gutschrift_vorzeichen(lies_xml(daten))
        erg["pdf"] = False
        return erg
    if not daten.startswith(b"%PDF"):
        raise LeseFehler("Bitte eine PDF- oder XML-Datei wählen.")
    xml = pdf_anhang(daten)
    if xml:
        erg = gutschrift_vorzeichen(lies_xml(xml))
        erg["pdf"] = True
        return erg
    erg = lies_text(pdf_text(daten), eigen)
    erg["pdf"] = True
    return erg
