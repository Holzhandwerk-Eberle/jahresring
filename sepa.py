"""Jahresring – SEPA-Überweisungsdatei (pain.001.001.09), IBAN-Prüfung und SEPA-Zeichensatz."""
import re
from datetime import datetime

from kern import ApiFehler


SEPA_UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss", "&": "+"}


def iban_normal(iban):
    return re.sub(r"\s", "", str(iban or "")).upper()


def iban_ok(iban):
    i = iban_normal(iban)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", i):
        return False
    ziffern = "".join(str(int(c, 36)) for c in i[4:] + i[:4])
    return int(ziffern) % 97 == 1


def ibanFormat_py(i):
    i = iban_normal(i)
    return " ".join(i[n:n + 4] for n in range(0, len(i), 4))


def sepa_text(s, laenge):
    s = "".join(SEPA_UMLAUTE.get(c, c) for c in str(s or ""))
    s = re.sub(r"[^A-Za-z0-9/\-?:().,'+ ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()[:laenge]


def sepa_xml(e, posten, ausfuehrung):
    """Erzeugt eine SEPA-Überweisungsdatei (pain.001.001.09) für das Onlinebanking."""
    from xml.sax.saxutils import escape as x
    name = sepa_text(e.get("sepa_name") or e.get("firma"), 70)
    iban = iban_normal(e.get("sepa_iban"))
    bic = re.sub(r"\s", "", e.get("sepa_bic") or "").upper()
    if bic and not re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", bic):
        bic = ""
    if not name or not iban_ok(iban):
        raise ApiFehler("Für die SEPA-Datei fehlen in den Einstellungen Kontoinhaber oder eine gültige eigene IBAN.")
    summe = sum(round(p["zahlbetrag"], 2) for p in posten)
    msg = "JR" + datetime.now().strftime("%Y%m%d%H%M%S%f")   # eindeutig auch bei zwei Dateien in derselben Sekunde
    tx = []
    for p in posten:
        bic_n = re.sub(r"\s", "", p.get("bic") or "").upper()
        # BIC ist im SEPA-Raum freiwillig; eine unvollständige BIC würde die ganze Datei ungültig machen
        bic_p = f"<CdtrAgt><FinInstnId><BICFI>{x(bic_n)}</BICFI></FinInstnId></CdtrAgt>" if re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", bic_n) else ""
        zweck = sepa_text(p["verwendungszweck"], 140)
        tx.append(
            f"<CdtTrfTxInf><PmtId><EndToEndId>{x(sepa_text(p['nummer'], 35))}</EndToEndId></PmtId>"
            f"<Amt><InstdAmt Ccy=\"EUR\">{p['zahlbetrag']:.2f}</InstdAmt></Amt>{bic_p}"
            f"<Cdtr><Nm>{x(sepa_text(p['empfaenger'], 70))}</Nm></Cdtr>"
            f"<CdtrAcct><Id><IBAN>{x(p['iban'])}</IBAN></Id></CdtrAcct>"
            f"<RmtInf><Ustrd>{x(zweck)}</Ustrd></RmtInf></CdtTrfTxInf>")
    dbtr_agt = f"<FinInstnId><BICFI>{x(bic)}</BICFI></FinInstnId>" if bic else "<FinInstnId><Othr><Id>NOTPROVIDED</Id></Othr></FinInstnId>"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09">'
        f"<CstmrCdtTrfInitn><GrpHdr><MsgId>{msg}</MsgId><CreDtTm>{datetime.now().isoformat(timespec='seconds')}</CreDtTm>"
        f"<NbOfTxs>{len(posten)}</NbOfTxs><CtrlSum>{summe:.2f}</CtrlSum><InitgPty><Nm>{x(name)}</Nm></InitgPty></GrpHdr>"
        f"<PmtInf><PmtInfId>{msg}-1</PmtInfId><PmtMtd>TRF</PmtMtd><BtchBookg>true</BtchBookg>"
        f"<NbOfTxs>{len(posten)}</NbOfTxs><CtrlSum>{summe:.2f}</CtrlSum>"
        "<PmtTpInf><SvcLvl><Cd>SEPA</Cd></SvcLvl></PmtTpInf>"
        f"<ReqdExctnDt><Dt>{ausfuehrung}</Dt></ReqdExctnDt>"
        f"<Dbtr><Nm>{x(name)}</Nm></Dbtr><DbtrAcct><Id><IBAN>{iban}</IBAN></Id></DbtrAcct>"
        f"<DbtrAgt>{dbtr_agt}</DbtrAgt><ChrgBr>SLEV</ChrgBr>"
        + "".join(tx) + "</PmtInf></CstmrCdtTrfInitn></Document>\n"
    )
