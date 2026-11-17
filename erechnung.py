"""E-Rechnung und GiroCode.

cii_xml()      – Rechnungsdaten als UN/CEFACT CII nach EN 16931 (für ZUGFeRD/Factur-X)
                 oder mit XRechnung-Kennung (für öffentliche Auftraggeber und B2B-Empfänger,
                 die ausdrücklich XRechnung verlangen).
zugferd_pdf()  – bettet die XML als factur-x.xml in das Rechnungs-PDF ein (PDF/A-3).
girocode_svg() – EPC-QR-Code („GiroCode“) zum Bezahlen mit der Banking-App.

Mitgelieferte Bibliotheken im Ordner lib: segno (QR-Code, BSD) und pypdf (PDF, BSD).
"""
import io
import os
import re
import sys
from datetime import date, datetime, timezone
from xml.sax.saxutils import escape
from kern import kfm

BASIS = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(BASIS, "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

PROFIL_EN16931 = "urn:cen.eu:en16931:2017"
PROFIL_XRECHNUNG = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
PEPPOL_PROZESS = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"

LAENDER = {"deutschland": "DE", "germany": "DE", "brd": "DE", "österreich": "AT", "oesterreich": "AT", "austria": "AT",
           "schweiz": "CH", "switzerland": "CH", "suisse": "CH", "liechtenstein": "LI", "frankreich": "FR", "france": "FR",
           "italien": "IT", "italy": "IT", "niederlande": "NL", "holland": "NL", "belgien": "BE", "luxemburg": "LU",
           "dänemark": "DK", "daenemark": "DK", "polen": "PL", "tschechien": "CZ", "tschechische republik": "CZ", "spanien": "ES",
           "portugal": "PT", "schweden": "SE", "norwegen": "NO", "finnland": "FI", "irland": "IE", "griechenland": "GR",
           "ungarn": "HU", "slowakei": "SK", "slowenien": "SI", "kroatien": "HR", "rumänien": "RO", "rumaenien": "RO",
           "bulgarien": "BG", "estland": "EE", "lettland": "LV", "litauen": "LT", "malta": "MT", "zypern": "CY",
           "großbritannien": "GB", "grossbritannien": "GB", "vereinigtes königreich": "GB", "england": "GB", "uk": "GB",
           "usa": "US", "vereinigte staaten": "US", "monaco": "MC", "island": "IS", "türkei": "TR", "tuerkei": "TR"}
# in XML 1.0 nicht erlaubte Zeichen (z. B. aus Word kopierte Steuerzeichen) – würden die Datei unlesbar machen
_UNGUELTIG = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")

# Einheiten nach UN/ECE Recommendation 20
EINHEITEN = [
    (r"^(stk|stück|st|x)\.?$", "H87"), (r"^(m²|m2|qm)$", "MTK"), (r"^(m³|m3|cbm)$", "MTQ"),
    (r"^(m|lfm|lfdm|meter)\.?$", "MTR"), (r"^(h|std|stunden?)\.?$", "HUR"), (r"^(min|minuten?)\.?$", "MIN"),
    (r"^(psch|pausch|pauschal|pauschale|ls)\.?$", "LS"), (r"^(kg)$", "KGM"), (r"^(l|ltr|liter)\.?$", "LTR"),
    (r"^(tag|tage|tg)\.?$", "DAY"), (r"^(satz|set|garnitur|garn)\.?$", "SET"), (r"^(paar|pr)\.?$", "PR"),
    (r"^(pck|pak|paket|pkg|packung|pckg)\.?$", "XPK"), (r"^(rolle|rl)\.?$", "XRO"), (r"^(dose|ds)\.?$", "XCA"), (r"^(tube|tb)\.?$", "XTU"),
]


class ERechnungFehler(Exception):
    pass


def einheit_code(einheit):
    e = (einheit or "").strip().lower()
    for muster, code in EINHEITEN:
        if re.match(muster, e):
            return code
    return "C62"  # „Einheit“


def betrag(x):
    return f"{kfm(float(x or 0) + 0.0):.2f}"


def menge_txt(x):
    s = f"{float(x or 0):.4f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def preis_txt(x):
    s = f"{float(x or 0):.4f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def t(x):
    return escape(_UNGUELTIG.sub("", str(x or "")).strip())


def datum102(iso):
    return (iso or date.today().isoformat())[:10].replace("-", "")


def land_code(land):
    land = (land or "").strip()
    if len(land) == 2 and land.isalpha():
        return land.upper()
    return LAENDER.get(land.lower(), "DE")


def anschrift_zerlegen(text, plz="", ort="", land="Deutschland"):
    """Briefanschrift (mehrzeilig) in Name, Straße, PLZ, Ort zerlegen."""
    zeilen = [z.strip() for z in (text or "").split("\n") if z.strip()]
    plz_ort = None
    for i in range(len(zeilen) - 1, -1, -1):
        m = re.match(r"^(?:[A-Z]{1,2}[- ])?(\d{4,5})\s+(.+)$", zeilen[i])
        if m:
            plz_ort = (m.group(1), m.group(2), i)
            break
    rest_land = None
    if plz_ort:
        plz, ort, i = plz_ort
        if i + 1 < len(zeilen):
            rest_land = zeilen[i + 1]
        zeilen = zeilen[:i]
    name = zeilen[0] if zeilen else ""
    strasse = zeilen[-1] if len(zeilen) > 1 else ""
    zusatz = zeilen[1:-1] if len(zeilen) > 2 else []
    return {"name": name, "zusatz": zusatz, "strasse": strasse, "plz": plz or "", "ort": ort or "",
            "land": land_code(rest_land or land)}


def adresse_xml(a):
    teile = [f"<ram:PostcodeCode>{t(a['plz'])}</ram:PostcodeCode>"] if a.get("plz") else []
    if a.get("strasse"):
        teile.append(f"<ram:LineOne>{t(a['strasse'])}</ram:LineOne>")
    if a.get("zusatz"):
        teile.append(f"<ram:LineTwo>{t(', '.join(a['zusatz']))}</ram:LineTwo>")
    if a.get("ort"):
        teile.append(f"<ram:CityName>{t(a['ort'])}</ram:CityName>")
    teile.append(f"<ram:CountryID>{a.get('land') or 'DE'}</ram:CountryID>")
    return "<ram:PostalTradeAddress>" + "".join(teile) + "</ram:PostalTradeAddress>"


def _klartext(html_oder_text):
    s = str(html_oder_text or "")
    if "<" in s:
        s = re.sub(r"(?i)<br\s*/?>|</(p|div|li)>", "\n", s)
        s = re.sub(r"(?i)<li[^>]*>", "• ", s)
        s = re.sub(r"<[^>]+>", "", s)
        from html import unescape
        s = unescape(s)
    return "\n".join(z.rstrip() for z in s.split("\n")).strip()


def pruefen(b, xrechnung):
    """Pflichtangaben prüfen; liefert eine Liste verständlicher Fehlermeldungen."""
    d = b["daten"]
    fi = d.get("firma") or {}
    fehler = []
    if not fi.get("firma"):
        fehler.append("Firmenname fehlt (Einstellungen).")
    a = anschrift_zerlegen(fi.get("firma_anschrift"))
    if not a["plz"] or not a["ort"]:
        fehler.append("Firmenanschrift mit PLZ und Ort fehlt (Einstellungen, z. B. „Musterstraße 1“ und darunter „12345 Musterstadt“).")
    if not fi.get("ustid") and not fi.get("steuernummer"):
        fehler.append("USt-IdNr. oder Steuernummer fehlt (Einstellungen).")
    if not fi.get("sepa_iban"):
        fehler.append("IBAN fehlt (Einstellungen).")
    if d.get("steuer") == "13b" and not (d.get("kunde") or {}).get("ustid"):
        fehler.append("Für eine E-Rechnung nach § 13b braucht der Kunde eine USt-IdNr. (Kundenstamm, Reiter Konditionen).")
    if xrechnung:
        if not fi.get("firma_email"):
            fehler.append("Für XRechnung ist eine Firmen-E-Mail nötig (Einstellungen).")
        if not fi.get("firma_telefon"):
            fehler.append("Für XRechnung ist eine Firmen-Telefonnummer nötig (Einstellungen).")
        if not (d.get("kunde") or {}).get("email"):
            fehler.append("Für XRechnung braucht der Kunde eine E-Mail-Adresse (Kundenstamm).")
    return fehler


def cii_xml(b, xrechnung=False, kunde_db=None):
    """b = Beleg wie aus beleg_laden() mit eingefrorenen Daten (b['daten']).
    kunde_db ergänzt Angaben, die ältere Belege noch nicht eingefroren haben (E-Mail, PLZ, Ort, Land)."""
    if kunde_db:
        ku = b["daten"].setdefault("kunde", {})
        for k, q in (("email", "email1"), ("plz", "plz"), ("ort", "ort"), ("land", "land")):
            if not ku.get(k) and kunde_db.get(q):
                ku[k] = kunde_db[q]
    fehler = pruefen(b, xrechnung)
    if fehler:
        raise ERechnungFehler(" ".join(fehler))
    d = b["daten"]
    fi, ku, s = d.get("firma") or {}, d.get("kunde") or {}, d["summen"]
    art = b["art"]
    # Storno und Gutschrift (und eine Korrektur mit Minusbetrag) gehen als Gutschrift (381) mit positiven Beträgen raus
    gutschrift = art in ("storno", "gutschrift") or (art == "korrektur" and float(s.get("brutto") or 0) < 0)
    vz = -1 if gutschrift else 1
    typ = "381" if gutschrift else {"rechnung": "380", "abschlag": "326", "korrektur": "384"}.get(art, "380")
    ust_satz = float(s.get("ust_satz") or 0)
    kat = "AE" if d.get("steuer") == "13b" else ("S" if ust_satz > 0 else "E")

    # --- Positionen ---
    zeilen, nr, summe_zeilen = [], 0, 0.0
    for z in d.get("zeilen", []):
        if z.get("typ") != "pos" or not z.get("zaehlt", True):
            continue
        nr += 1
        gp = kfm(vz * float(z.get("gp") or 0))
        menge = float(z.get("menge") or 0) or 1.0
        ep = gp / menge if menge else gp
        if ep < 0:   # BR-27: der Preis darf nicht negativ sein – ein Abzug wird als negative Menge übermittelt
            ep, menge = -ep, -menge
        text = _klartext(z.get("text"))
        name, _, beschr = text.partition("\n")
        unter = [f"{u.get('posnr', '')} {menge_txt(u.get('menge'))} {u.get('einheit', '')} {_klartext(u.get('text')).splitlines()[0] if _klartext(u.get('text')) else ''}".strip()
                 for u in z.get("unter", [])]
        if unter:
            beschr = (beschr + "\n" if beschr else "") + "enthält:\n" + "\n".join(unter)
        summe_zeilen += gp
        zeilen.append(f"""
    <ram:IncludedSupplyChainTradeLineItem>
      <ram:AssociatedDocumentLineDocument><ram:LineID>{nr}</ram:LineID></ram:AssociatedDocumentLineDocument>
      <ram:SpecifiedTradeProduct>
        {f"<ram:SellerAssignedID>{t(z.get('posnr'))}</ram:SellerAssignedID>" if t(z.get('posnr')) else ""}
        <ram:Name>{t(name[:200] or 'Position ' + str(nr))}</ram:Name>{f'''
        <ram:Description>{t(beschr)}</ram:Description>''' if beschr.strip() else ''}
      </ram:SpecifiedTradeProduct>
      <ram:SpecifiedLineTradeAgreement>
        <ram:NetPriceProductTradePrice><ram:ChargeAmount>{preis_txt(ep)}</ram:ChargeAmount></ram:NetPriceProductTradePrice>
      </ram:SpecifiedLineTradeAgreement>
      <ram:SpecifiedLineTradeDelivery>
        <ram:BilledQuantity unitCode="{einheit_code(z.get('einheit'))}">{menge_txt(menge)}</ram:BilledQuantity>
      </ram:SpecifiedLineTradeDelivery>
      <ram:SpecifiedLineTradeSettlement>
        <ram:ApplicableTradeTax><ram:TypeCode>VAT</ram:TypeCode><ram:CategoryCode>{kat}</ram:CategoryCode><ram:RateApplicablePercent>{menge_txt(ust_satz)}</ram:RateApplicablePercent></ram:ApplicableTradeTax>
        <ram:SpecifiedTradeSettlementLineMonetarySummation><ram:LineTotalAmount>{betrag(gp)}</ram:LineTotalAmount></ram:SpecifiedTradeSettlementLineMonetarySummation>
      </ram:SpecifiedLineTradeSettlement>
    </ram:IncludedSupplyChainTradeLineItem>""")
    if not zeilen:
        raise ERechnungFehler("Die Rechnung enthält keine abrechenbaren Positionen.")
    summe_zeilen = kfm(summe_zeilen)

    rabatt = kfm(vz * float(s.get("rabatt") or 0))
    netto = kfm(summe_zeilen - rabatt)
    ust = kfm(netto * ust_satz / 100)
    brutto = kfm(netto + ust)
    # Abweichungen zum gedruckten Beleg wären ein Fehler – lieber abbrechen als falsche Zahlen senden
    if abs(netto - vz * float(s.get("netto") or 0)) > 0.011 or abs(brutto - vz * float(s.get("brutto") or 0)) > 0.011:
        raise ERechnungFehler(f"Summen passen nicht zusammen (Positionen {netto:.2f} € netto, Beleg {vz * float(s.get('netto') or 0):.2f} €). "
                              "Bitte den Beleg mit „Aus Positionen aktualisieren“ neu berechnen.")
    netto, ust, brutto = kfm(vz * float(s["netto"])), kfm(vz * float(s["ust"])), kfm(vz * float(s["brutto"]))
    vorausbezahlt = kfm(vz * float(s.get("abzug_brutto") or 0))
    zahlbetrag = kfm(brutto - vorausbezahlt)

    # --- Parteien ---
    vk = anschrift_zerlegen(fi.get("firma_anschrift"))
    kd_adr = anschrift_zerlegen(b.get("anschrift") or "", ku.get("plz", ""), ku.get("ort", ""), ku.get("land") or "Deutschland")
    kaeufer_name = kd_adr["name"] or ku.get("kurzname") or "Kunde"
    # BT-44 ist der Name des Käufers, ohne Briefanrede („Herrn Tom Test“ → „Tom Test“; „Familie“/„Eheleute“ bleiben Teil des Namens)
    kaeufer_name = re.sub(r"^(Herrn?|Frau|Firma)\s+", "", kaeufer_name.strip()) or kaeufer_name
    if not kd_adr["plz"] and ku.get("plz"):
        kd_adr.update(plz=ku.get("plz"), ort=ku.get("ort"))
    steuer = ""
    if fi.get("ustid"):
        steuer += f'<ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">{t(fi["ustid"].replace(" ", ""))}</ram:ID></ram:SpecifiedTaxRegistration>'
    if fi.get("steuernummer"):
        steuer += f'<ram:SpecifiedTaxRegistration><ram:ID schemeID="FC">{t(fi["steuernummer"])}</ram:ID></ram:SpecifiedTaxRegistration>'
    # BR-CO-26: ohne USt-IdNr. braucht der Käufer eine andere Kennung des Verkäufers – dann die Steuernummer
    verkaeufer_id = "" if fi.get("ustid") else f"\n        <ram:ID>{t(fi.get('steuernummer'))}</ram:ID>"
    kontakt = ""
    if fi.get("firma_inhaber") or fi.get("firma_telefon") or fi.get("firma_email"):
        kontakt = ("<ram:DefinedTradeContact>"
                   + (f"<ram:PersonName>{t(fi.get('firma_inhaber') or fi.get('firma'))}</ram:PersonName>")
                   + (f"<ram:TelephoneUniversalCommunication><ram:CompleteNumber>{t(fi['firma_telefon'])}</ram:CompleteNumber></ram:TelephoneUniversalCommunication>" if fi.get("firma_telefon") else "")
                   + (f"<ram:EmailURIUniversalCommunication><ram:URIID>{t(fi['firma_email'])}</ram:URIID></ram:EmailURIUniversalCommunication>" if fi.get("firma_email") else "")
                   + "</ram:DefinedTradeContact>")
    vk_mail = f'<ram:URIUniversalCommunication><ram:URIID schemeID="EM">{t(fi["firma_email"])}</ram:URIID></ram:URIUniversalCommunication>' if fi.get("firma_email") else ""
    kd_mail = f'<ram:URIUniversalCommunication><ram:URIID schemeID="EM">{t(ku["email"])}</ram:URIID></ram:URIUniversalCommunication>' if ku.get("email") else ""
    kd_ustid = f'<ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">{t(ku["ustid"].replace(" ", ""))}</ram:ID></ram:SpecifiedTaxRegistration>' if ku.get("ustid") else ""
    kaeufer_ref = ku.get("leitweg_id") or (str(ku.get("nummer")) if ku.get("nummer") else "") or "keine Angabe"

    # --- Zahlung ---
    faellig = b.get("faellig") or b.get("datum")
    bedingung = []
    if zahlbetrag > 0 and not gutschrift:
        bedingung.append(f"Zahlbar ohne Abzug bis {faellig[8:10]}.{faellig[5:7]}.{faellig[:4]}"
                         + (f"; bei Zahlung innerhalb von {int(ku['skontotage'])} Tagen {menge_txt(ku['skonto'])} % Skonto" if ku.get("skonto") and ku.get("skontotage") else "")
                         + ".")
        if ku.get("skonto") and ku.get("skontotage"):
            # maschinenlesbare Skontozeile (XRechnung BR-DE-18): am Ende, mit Zeilenumbruch abgeschlossen
            bedingung.append(f"\n#SKONTO#TAGE={int(ku['skontotage'])}#PROZENT={float(ku['skonto']):.2f}#\n")
    elif gutschrift:
        bedingung.append("Storno, kein Zahlungsausgleich durch den Kunden." if art == "storno" else "Gutschrift zugunsten des Kunden.")
    else:
        bedingung.append("Bereits vollständig durch Abschlagszahlungen beglichen.")
    zahlungsmittel = ""
    if fi.get("sepa_iban"):
        zahlungsmittel = ("<ram:SpecifiedTradeSettlementPaymentMeans><ram:TypeCode>58</ram:TypeCode>"
                          "<ram:Information>SEPA-Überweisung</ram:Information>"
                          f"<ram:PayeePartyCreditorFinancialAccount><ram:IBANID>{t(fi['sepa_iban'].replace(' ', '').upper())}</ram:IBANID>"
                          + (f"<ram:AccountName>{t(fi.get('firma'))}</ram:AccountName>" if fi.get("firma") else "")
                          + "</ram:PayeePartyCreditorFinancialAccount>"
                          + (f"<ram:PayeeSpecifiedCreditorFinancialInstitution><ram:BICID>{t(fi['sepa_bic'].replace(' ', ''))}</ram:BICID></ram:PayeeSpecifiedCreditorFinancialInstitution>" if fi.get("sepa_bic") else "")
                          + "</ram:SpecifiedTradeSettlementPaymentMeans>")
    befreiung = ("" if kat == "S" else "<ram:ExemptionReason>Steuerschuldnerschaft des Leistungsempfängers (§ 13b UStG)</ram:ExemptionReason>"
                 if kat == "AE" else "<ram:ExemptionReason>Steuerfrei</ram:ExemptionReason>")
    befreiung_code = "<ram:ExemptionReasonCode>VATEX-EU-AE</ram:ExemptionReasonCode>" if kat == "AE" else ""
    rabatt_xml = ""
    if rabatt:
        rabatt_xml = (f"<ram:SpecifiedTradeAllowanceCharge><ram:ChargeIndicator><udt:Indicator>false</udt:Indicator></ram:ChargeIndicator>"
                      f"<ram:CalculationPercent>{menge_txt(s.get('rabatt_pz'))}</ram:CalculationPercent><ram:BasisAmount>{betrag(summe_zeilen)}</ram:BasisAmount>"
                      f"<ram:ActualAmount>{betrag(rabatt)}</ram:ActualAmount><ram:Reason>Rabatt</ram:Reason>"
                      f"<ram:CategoryTradeTax><ram:TypeCode>VAT</ram:TypeCode><ram:CategoryCode>{kat}</ram:CategoryCode><ram:RateApplicablePercent>{menge_txt(ust_satz)}</ram:RateApplicablePercent></ram:CategoryTradeTax>"
                      "</ram:SpecifiedTradeAllowanceCharge>")
    bezug = ""
    if (gutschrift or art == "korrektur") and d.get("bezug"):
        bezug = (f"<ram:InvoiceReferencedDocument><ram:IssuerAssignedID>{t(d['bezug']['nummer'])}</ram:IssuerAssignedID>"
                 f"<ram:FormattedIssueDateTime><qdt:DateTimeString format=\"102\">{datum102(d['bezug'].get('datum'))}</qdt:DateTimeString></ram:FormattedIssueDateTime>"
                 "</ram:InvoiceReferencedDocument>")
    elif d.get("abzuege"):
        bezug = "".join(f"<ram:InvoiceReferencedDocument><ram:IssuerAssignedID>{t(x['nummer'])}</ram:IssuerAssignedID>"
                        f"<ram:FormattedIssueDateTime><qdt:DateTimeString format=\"102\">{datum102(x.get('datum'))}</qdt:DateTimeString></ram:FormattedIssueDateTime>"
                        "</ram:InvoiceReferencedDocument>" for x in d["abzuege"][:1])
    notizen = []
    if b.get("betreff"):
        notizen.append(b["betreff"])
    for x in d.get("abzuege", []):
        notizen.append(f"Abzüglich Abschlagsrechnung {x['nummer']} vom {x['datum'][8:10]}.{x['datum'][5:7]}.{x['datum'][:4]}: "
                       f"netto {abs(x['netto']):.2f} EUR, USt {abs(x['ust']):.2f} EUR, brutto {abs(x['brutto']):.2f} EUR".replace(".", ","))
    notiz_xml = "".join(f"<ram:IncludedNote><ram:Content>{t(n)}</ram:Content></ram:IncludedNote>" for n in notizen)
    leistung = b.get("leistungsdatum") or b.get("datum")

    profil = PROFIL_XRECHNUNG if xrechnung else PROFIL_EN16931
    prozess = f"<ram:BusinessProcessSpecifiedDocumentContextParameter><ram:ID>{PEPPOL_PROZESS}</ram:ID></ram:BusinessProcessSpecifiedDocumentContextParameter>" if xrechnung else ""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100" xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100" xmlns:qdt="urn:un:unece:uncefact:data:standard:QualifiedDataType:100" xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>{prozess}<ram:GuidelineSpecifiedDocumentContextParameter><ram:ID>{profil}</ram:ID></ram:GuidelineSpecifiedDocumentContextParameter></rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>{t(b['nummer'])}</ram:ID>
    <ram:TypeCode>{typ}</ram:TypeCode>
    <ram:IssueDateTime><udt:DateTimeString format="102">{datum102(b.get('datum'))}</udt:DateTimeString></ram:IssueDateTime>{notiz_xml}
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>{''.join(zeilen)}
    <ram:ApplicableHeaderTradeAgreement>
      <ram:BuyerReference>{t(kaeufer_ref)}</ram:BuyerReference>
      <ram:SellerTradeParty>{verkaeufer_id}
        <ram:Name>{t(fi.get('firma'))}</ram:Name>{kontakt}
        {adresse_xml(vk)}{vk_mail}{steuer}
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        {f"<ram:ID>{t(ku.get('nummer'))}</ram:ID>" if t(ku.get('nummer')) else ""}
        <ram:Name>{t(kaeufer_name)}</ram:Name>
        {adresse_xml(kd_adr)}{kd_mail}{kd_ustid}
      </ram:BuyerTradeParty>
      {f"<ram:SellerOrderReferencedDocument><ram:IssuerAssignedID>{t((d.get('auftrag') or {}).get('nummer'))}</ram:IssuerAssignedID></ram:SellerOrderReferencedDocument>" if t((d.get('auftrag') or {}).get('nummer')) else ""}
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery>
      <ram:ActualDeliverySupplyChainEvent><ram:OccurrenceDateTime><udt:DateTimeString format="102">{datum102(leistung)}</udt:DateTimeString></ram:OccurrenceDateTime></ram:ActualDeliverySupplyChainEvent>
    </ram:ApplicableHeaderTradeDelivery>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:PaymentReference>{t(b['nummer'])}</ram:PaymentReference>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      {zahlungsmittel}
      <ram:ApplicableTradeTax>
        <ram:CalculatedAmount>{betrag(ust)}</ram:CalculatedAmount>
        <ram:TypeCode>VAT</ram:TypeCode>{befreiung}
        <ram:BasisAmount>{betrag(netto)}</ram:BasisAmount>
        <ram:CategoryCode>{kat}</ram:CategoryCode>{befreiung_code}
        <ram:RateApplicablePercent>{menge_txt(ust_satz)}</ram:RateApplicablePercent>
      </ram:ApplicableTradeTax>
      {rabatt_xml}
      <ram:SpecifiedTradePaymentTerms>
        <ram:Description>{escape(_UNGUELTIG.sub("", ''.join(bedingung)))}</ram:Description>{f'''
        <ram:DueDateDateTime><udt:DateTimeString format="102">{datum102(faellig)}</udt:DateTimeString></ram:DueDateDateTime>''' if zahlbetrag > 0 and not gutschrift else ''}
      </ram:SpecifiedTradePaymentTerms>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:LineTotalAmount>{betrag(summe_zeilen)}</ram:LineTotalAmount>{f'''
        <ram:AllowanceTotalAmount>{betrag(rabatt)}</ram:AllowanceTotalAmount>''' if rabatt else ''}
        <ram:TaxBasisTotalAmount>{betrag(netto)}</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">{betrag(ust)}</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>{betrag(brutto)}</ram:GrandTotalAmount>{f'''
        <ram:TotalPrepaidAmount>{betrag(vorausbezahlt)}</ram:TotalPrepaidAmount>''' if vorausbezahlt else ''}
        <ram:DuePayableAmount>{betrag(zahlbetrag)}</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
      {bezug}
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""
    return xml.encode("utf-8")


# ---------- ZUGFeRD / Factur-X: XML in PDF/A-3 einbetten ----------
ICC = os.path.join(BASIS, "lib", "sRGB.icc")


def _xmp(titel, autor, erstellt, profil_name):
    return f"""<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">
   <pdfaid:part>3</pdfaid:part>
   <pdfaid:conformance>B</pdfaid:conformance>
  </rdf:Description>
  <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
   <dc:format>application/pdf</dc:format>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{escape(titel)}</rdf:li></rdf:Alt></dc:title>
   <dc:creator><rdf:Seq><rdf:li>{escape(autor)}</rdf:li></rdf:Seq></dc:creator>
  </rdf:Description>
  <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">
   <xmp:CreatorTool>Jahresring</xmp:CreatorTool>
   <xmp:CreateDate>{erstellt}</xmp:CreateDate>
   <xmp:ModifyDate>{erstellt}</xmp:ModifyDate>
  </rdf:Description>
  <rdf:Description rdf:about="" xmlns:pdf="http://ns.adobe.com/pdf/1.3/">
   <pdf:Producer>Jahresring (pypdf)</pdf:Producer>
  </rdf:Description>
  <rdf:Description rdf:about="" xmlns:fx="urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#">
   <fx:DocumentType>INVOICE</fx:DocumentType>
   <fx:DocumentFileName>factur-x.xml</fx:DocumentFileName>
   <fx:Version>1.0</fx:Version>
   <fx:ConformanceLevel>{profil_name}</fx:ConformanceLevel>
  </rdf:Description>
  <rdf:Description rdf:about="" xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/" xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#" xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#">
   <pdfaExtension:schemas>
    <rdf:Bag>
     <rdf:li rdf:parseType="Resource">
      <pdfaSchema:schema>Factur-X PDFA Extension Schema</pdfaSchema:schema>
      <pdfaSchema:namespaceURI>urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#</pdfaSchema:namespaceURI>
      <pdfaSchema:prefix>fx</pdfaSchema:prefix>
      <pdfaSchema:property>
       <rdf:Seq>
        <rdf:li rdf:parseType="Resource"><pdfaProperty:name>DocumentFileName</pdfaProperty:name><pdfaProperty:valueType>Text</pdfaProperty:valueType><pdfaProperty:category>external</pdfaProperty:category><pdfaProperty:description>name of the embedded XML invoice file</pdfaProperty:description></rdf:li>
        <rdf:li rdf:parseType="Resource"><pdfaProperty:name>DocumentType</pdfaProperty:name><pdfaProperty:valueType>Text</pdfaProperty:valueType><pdfaProperty:category>external</pdfaProperty:category><pdfaProperty:description>INVOICE</pdfaProperty:description></rdf:li>
        <rdf:li rdf:parseType="Resource"><pdfaProperty:name>Version</pdfaProperty:name><pdfaProperty:valueType>Text</pdfaProperty:valueType><pdfaProperty:category>external</pdfaProperty:category><pdfaProperty:description>The actual version of the Factur-X XML schema</pdfaProperty:description></rdf:li>
        <rdf:li rdf:parseType="Resource"><pdfaProperty:name>ConformanceLevel</pdfaProperty:name><pdfaProperty:valueType>Text</pdfaProperty:valueType><pdfaProperty:category>external</pdfaProperty:category><pdfaProperty:description>The conformance level of the embedded Factur-X data</pdfaProperty:description></rdf:li>
       </rdf:Seq>
      </pdfaSchema:property>
     </rdf:li>
    </rdf:Bag>
   </pdfaExtension:schemas>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


def zugferd_pdf(pdf_in, xml_bytes, pdf_out, titel="Rechnung", autor="", xrechnung=False):
    """Macht aus dem gedruckten PDF eine ZUGFeRD-/Factur-X-Rechnung (PDF/A-3B mit factur-x.xml)."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject,
                               StreamObject, TextStringObject, create_string_object, ByteStringObject)
    import hashlib

    reader = PdfReader(pdf_in)
    writer = PdfWriter(clone_from=reader)
    jetzt = datetime.now(timezone.utc).astimezone()
    pdf_datum = jetzt.strftime("D:%Y%m%d%H%M%S") + jetzt.strftime("%z")[:3] + "'" + jetzt.strftime("%z")[3:] + "'"
    xmp_datum = jetzt.isoformat(timespec="seconds")

    # eingebettete XML-Datei
    ef = DecodedStreamObject()
    ef.set_data(xml_bytes)
    ef.update({NameObject("/Type"): NameObject("/EmbeddedFile"),
               NameObject("/Subtype"): NameObject("/text/xml"),   # pypdf schreibt das als /text#2Fxml (MIME-Typ text/xml)
               NameObject("/Params"): DictionaryObject({NameObject("/ModDate"): create_string_object(pdf_datum),
                                                        NameObject("/Size"): NumberObject(len(xml_bytes)),
                                                        NameObject("/CheckSum"): ByteStringObject(hashlib.md5(xml_bytes).digest())})})
    ef_ref = writer._add_object(ef)
    name = "xrechnung.xml" if xrechnung else "factur-x.xml"
    fs = DictionaryObject({NameObject("/Type"): NameObject("/Filespec"),
                           NameObject("/F"): create_string_object(name), NameObject("/UF"): create_string_object(name),
                           NameObject("/Desc"): create_string_object("Rechnungsdaten (EN 16931)"),
                           NameObject("/AFRelationship"): NameObject("/Alternative"),
                           NameObject("/EF"): DictionaryObject({NameObject("/F"): ef_ref, NameObject("/UF"): ef_ref})})
    fs_ref = writer._add_object(fs)
    root = writer._root_object
    root[NameObject("/Names")] = DictionaryObject({NameObject("/EmbeddedFiles"): DictionaryObject(
        {NameObject("/Names"): ArrayObject([create_string_object(name), fs_ref])})})
    root[NameObject("/AF")] = ArrayObject([fs_ref])

    # Farbprofil (OutputIntent) für PDF/A
    if os.path.exists(ICC):
        icc = DecodedStreamObject()
        icc.set_data(open(ICC, "rb").read())
        icc[NameObject("/N")] = NumberObject(3)
        icc_ref = writer._add_object(icc)
        root[NameObject("/OutputIntents")] = ArrayObject([writer._add_object(DictionaryObject({
            NameObject("/Type"): NameObject("/OutputIntent"), NameObject("/S"): NameObject("/GTS_PDFA1"),
            NameObject("/OutputConditionIdentifier"): create_string_object("sRGB IEC61966-2.1"),
            NameObject("/Info"): create_string_object("sRGB IEC61966-2.1"),
            NameObject("/DestOutputProfile"): icc_ref}))])

    # Metadaten (XMP und Info müssen übereinstimmen)
    xmp = DecodedStreamObject()
    xmp.set_data(_xmp(titel, autor, xmp_datum, "XRECHNUNG" if xrechnung else "EN 16931").encode("utf-8"))
    xmp.update({NameObject("/Type"): NameObject("/Metadata"), NameObject("/Subtype"): NameObject("/XML")})
    root[NameObject("/Metadata")] = writer._add_object(xmp)
    root[NameObject("/PageMode")] = NameObject("/UseAttachments")
    writer.add_metadata({"/Title": titel, "/Author": autor, "/Creator": "Jahresring",
                         "/Producer": "Jahresring (pypdf)", "/CreationDate": pdf_datum, "/ModDate": pdf_datum})
    # Links und andere Anmerkungen müssen für PDF/A als druckbar markiert sein
    for seite in writer.pages:
        for a in seite.get("/Annots") or []:
            o = a.get_object()
            o[NameObject("/F")] = NumberObject(4)
    writer.pdf_header = b"%PDF-1.7"   # eingebettete Dateien (/AF) gibt es ab PDF 1.7; PDF/A-3 beruht darauf
    if not writer._ID:
        writer.generate_file_identifiers()   # PDF/A verlangt eine Dateikennung (/ID) im Trailer
    with open(pdf_out, "wb") as f:
        writer.write(f)


# ---------- GiroCode (EPC-QR) ----------
def girocode_text(empfaenger, iban, bic, summe, verwendung):
    return "\n".join(["BCD", "002", "1", "SCT", (bic or "").replace(" ", ""), (empfaenger or "")[:70],
                      (iban or "").replace(" ", "").upper(), f"EUR{float(summe):.2f}", "", "", (verwendung or "")[:140]])


def girocode_svg(empfaenger, iban, bic, summe, verwendung, mm=26):
    import segno
    qr = segno.make(girocode_text(empfaenger, iban, bic, summe, verwendung), error="m", micro=False, encoding="utf-8")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=1, border=0, xmldecl=False, svgns=True, nl=False, dark="#000", omitsize=True)
    svg = buf.getvalue().decode("utf-8")
    return re.sub(r'<svg ', f'<svg style="width:{mm}mm;height:{mm}mm;display:block" preserveAspectRatio="xMidYMid meet" ', svg, count=1)
