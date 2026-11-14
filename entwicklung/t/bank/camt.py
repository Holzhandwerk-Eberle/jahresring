"""Erzeugt CAMT-Testdateien."""
def ntry(betrag, cd, name, iban, zweck, e2e="NOTPROVIDED", ref="", datum="2026-11-10", sts08=True, txs=None):
    sts = "<Sts><Cd>BOOK</Cd></Sts>" if sts08 else "<Sts>BOOK</Sts>"
    rolle, konto = ("Dbtr", "DbtrAcct") if cd == "CRDT" else ("Cdtr", "CdtrAcct")
    def tx(b, n, i, z, e):
        nm = f"<Pty><Nm>{n}</Nm></Pty>" if sts08 else f"<Nm>{n}</Nm>"
        return (f"<TxDtls><Refs><EndToEndId>{e}</EndToEndId></Refs><AmtDtls><TxAmt><Amt Ccy=\"EUR\">{b:.2f}</Amt></TxAmt></AmtDtls>"
                f"<RltdPties><{rolle}>{nm}</{rolle}><{konto}><Id><IBAN>{i}</IBAN></Id></{konto}></RltdPties><RmtInf><Ustrd>{z}</Ustrd></RmtInf></TxDtls>")
    details = "".join(tx(*t) for t in txs) if txs else tx(betrag, name, iban, zweck, e2e)
    r = f"<AcctSvcrRef>{ref}</AcctSvcrRef>" if ref else ""
    return (f"<Ntry><Amt Ccy=\"EUR\">{betrag:.2f}</Amt><CdtDbtInd>{cd}</CdtDbtInd>{sts}<BookgDt><Dt>{datum}</Dt></BookgDt><ValDt><Dt>{datum}</Dt></ValDt>{r}"
            f"<BkTxCd/><NtryDtls>{details}</NtryDtls></Ntry>")

def datei(eintraege, anfang=1000.0, ende=None, ns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08", iban="DE02120300000000202051", von="2026-11-01", bis="2026-11-13"):
    return (f'<?xml version="1.0" encoding="UTF-8"?><Document xmlns="{ns}"><BkToCstmrStmt><GrpHdr><MsgId>T1</MsgId><CreDtTm>2026-11-13T10:00:00</CreDtTm></GrpHdr>'
            f'<Stmt><Id>S1</Id><CreDtTm>2026-11-13T10:00:00</CreDtTm><FrToDt><FrDtTm>{von}T00:00:00</FrDtTm><ToDtTm>{bis}T23:59:59</ToDtTm></FrToDt>'
            f'<Acct><Id><IBAN>{iban}</IBAN></Id></Acct>'
            f'<Bal><Tp><CdOrPrtry><Cd>PRCD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">{anfang:.2f}</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>{von}</Dt></Dt></Bal>'
            + (f'<Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">{abs(ende):.2f}</Amt><CdtDbtInd>{"CRDT" if ende >= 0 else "DBIT"}</CdtDbtInd><Dt><Dt>{bis}</Dt></Dt></Bal>' if ende is not None else "")
            + "".join(eintraege) + "</Stmt></BkToCstmrStmt></Document>").encode("utf-8")
