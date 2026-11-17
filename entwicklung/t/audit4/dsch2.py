"""Rückstände nach dem Anonymisieren eines Kunden (Fristen per Datenbank zurückdatiert)."""
import json, re, sys, base64, time, os, sqlite3, subprocess, glob, io, zipfile
from datetime import date, datetime, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    return j
T = lambda x: "QX" + x + "QX"
k = A("POST", "kunden", {"kurzname": T("KURZ"), "vorname": T("VOR"), "nachname": T("NACH"), "firma": T("FIRMA"), "strasse": T("STR"), "hausnr": "7", "plz": "88099", "ort": T("ORT"), "telefon": "07542 " + T("TEL"), "email1": "qxmailqx@beispiel.de",
                         "bemerkungen": T("BEM"), "iban": "DE02120300000000202051", "lieferanschrift": T("LIEFERSTR") + " 3", "lieferort": "88099 " + T("LIEFERORT"), "geburtstag": "1970-02-03", "merkmale": T("MERK")})
print("Kunde", k["_s"], k.get("id"), k.get("nummer"), k.get("fehler", ""))
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Küche " + T("AUFTRAG"), "bemerkungen": T("AUFBEM")})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Schrank für Herrn " + T("POSTEXT")}); pid = po.get("id") or po["position"]["id"]
A("PUT", f"positionen/{pid}", {"einzelpreis": 500, "preis_manuell": 1, "menge": 1})
ids = {}
for art in ("angebot", "ab", "rechnung"):
    b = A("POST", f"auftraege/{a['id']}/belege", {"art": art}); ids[art] = b.get("id")
    r = A("PUT", f"belege/{b['id']}", {"einleitung": "Sehr geehrter Herr " + T("EINL" + art.upper()), "schluss": "Gruß an Frau " + T("SCHLUSS"), "betreff": "Küche " + T("BETREFF")})
    if art != "angebot":
        f = A("POST", f"belege/{b['id']}/festschreiben", {})
    s, t, _ = rq(inh, "GET", f"/druck/{b['id']}.pdf", roh=True)
print("Belege", ids)
A("POST", "termine", {"auftrag_id": a["id"], "typ": "Montage", "titel": "Montage bei " + T("TERMIN"), "von": "2026-11-20", "bis": "2026-11-20", "notiz": "Schlüssel bei Nachbar " + T("TERMINNOTIZ")})
A("POST", "termine", {"typ": "Aufmaß", "titel": "Aufmaß " + T("TERMINFREI"), "von": "2026-11-21", "bis": "2026-11-21"})
A("POST", "notizen", {"kunde_id": k["id"], "text": T("NOTIZK")}); A("POST", "notizen", {"auftrag_id": a["id"], "text": T("NOTIZA")})
br = A("POST", "briefe", {"kunde_id": k["id"], "betreff": "Brief " + T("BRIEFBETREFF"), "text": "Hallo " + T("BRIEFTEXT")}); print("Brief", br["_s"], br.get("id"), br.get("fehler", ""))
if br.get("id"): A("PUT", f"briefe/{br['id']}", {"betreff": "Brief " + T("BRIEFBETREFF"), "text": "Hallo " + T("BRIEFTEXT")})
wv = A("POST", "wiedervorlagen", {"kunde_id": k["id"], "text": T("WIEDERVORLAGE"), "datum": "2026-12-01", "faellig": "2026-12-01"}); print("Wiedervorlage", wv["_s"], wv.get("fehler", ""))
an = A("POST", "anhaenge", {"kunde_id": k["id"], "dateiname": "QXANHANGQX.txt", "daten": base64.b64encode(b"QXANHANGINHALTQX").decode()}); print("Anhang", an["_s"])
ops = A("GET", "offeneposten"); opl = ops.get("liste") or ops.get("posten") or []
op = [o for o in opl if o.get("kunde_id") == k["id"] or T("KURZ") in json.dumps(o)]
print("Offene Posten des Kunden:", len(op), sorted(op[0].keys())[:30] if op else "")
if op:
    z = A("POST", f"offeneposten/{op[0]['id']}/zahlung", {"datum": date.today().isoformat(), "betrag": op[0].get("offen") or op[0].get("betrag"), "art": "Überweisung", "bemerkung": "Zahler " + T("ZAHLTEXT"), "text": T("ZAHLTEXT2")}); print("Zahlung", z["_s"], z.get("fehler", ""))
u = A("POST", f"belege/{ids['ab']}/unterschreiben", {"name": T("UNTERSCHRIFTNAME"), "bild": "data:image/png;base64," + base64.b64encode(open("/home/claude/eberle-buero/static/jahresring-192.png", "rb").read()).decode()}); print("Unterschrift AB:", u["_s"], u.get("fehler", "")[:100])
bt = A("POST", "bautagebuch", {"auftrag_id": a["id"], "datum": date.today().isoformat(), "text": "Kunde " + T("BAUTAGEBUCH") + " anwesend", "wetter": "trocken"}); print("Bautagebuch", bt["_s"], bt.get("fehler", "")[:80])
ko = A("POST", "korrespondenz", {"kunde_id": k["id"], "art": "telefon", "betreff": T("KORRBETREFF"), "text": T("KORRTEXT"), "datum": date.today().isoformat()}); print("Korrespondenz", ko["_s"], ko.get("fehler", "")[:80])
# Kontoauszug mit Zahlung des Kunden
camt = f'''<?xml version="1.0" encoding="UTF-8"?><Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><Stmt><Id>QX1</Id><CreDtTm>2026-11-17T08:00:00</CreDtTm><Acct><Id><IBAN>DE02120300000000202051</IBAN></Id></Acct>
<Bal><Tp><CdOrPrtry><Cd>PRCD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">0.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2026-11-16</Dt></Dt></Bal><Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">77.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2026-11-17</Dt></Dt></Bal>
<Ntry><Amt Ccy="EUR">77.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><BookgDt><Dt>2026-11-17</Dt></BookgDt><ValDt><Dt>2026-11-17</Dt></ValDt><NtryDtls><TxDtls><RltdPties><Dbtr><Nm>QXBANKNAMEQX</Nm></Dbtr><DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct></RltdPties><RmtInf><Ustrd>Anzahlung QXBANKZWECKQX</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry></Stmt></BkToCstmrStmt></Document>'''
bk = A("POST", "bank/einlesen", {"daten": base64.b64encode(camt.encode()).decode(), "dateiname": "QX-auszug.xml"}); print("Kontoauszug", bk["_s"], bk.get("neu"), bk.get("fehler", ""))
con = sqlite3.connect(D + "/buero.db", timeout=20); con.row_factory = sqlite3.Row
tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
def scan(was):
    funde = {}
    for t in tabs:
        try:
            for r in con.execute(f'SELECT * FROM "{t}"'):
                for sp in r.keys():
                    v = r[sp]
                    if isinstance(v, bytes): v = v.decode("utf-8", "replace")
                    if isinstance(v, str):
                        for m in re.findall(r"QX[A-ZÄÖÜa-z0-9]+QX|qxmailqx", v):
                            funde.setdefault(m, set()).add(f"{t}.{sp}")
        except sqlite3.Error as f: pass
    return funde
vorher = scan("vor")
print("\nMarken in der Datenbank vorher:", len(vorher))
dat_vor = subprocess.run(f"grep -rlaE 'QX[A-Z]+QX|qxmailqx' {D} --exclude=buero.db* 2>/dev/null | head -50", shell=True, capture_output=True, text=True).stdout.split()
print("Dateien mit Marken vorher:", [d.replace(D, "") for d in dat_vor][:30])
# zurückdatieren: alles 12 Jahre alt
for t, sp in (("belege", "datum"), ("auftraege", "angelegt"), ("auftraege", "geaendert"), ("offene_posten", "datum"), ("offene_posten", "faellig"), ("zahlungseingaenge", "datum"), ("korrespondenz", "datum"), ("termine", "von"), ("termine", "bis"), ("briefe", "datum")):
    try:
        wo = {"belege": "auftrag_id=?", "auftraege": "id=?", "offene_posten": "auftrag_id=?", "termine": "auftrag_id=?", "briefe": "kunde_id=?", "korrespondenz": "kunde_id=?", "zahlungseingaenge": "op_id IN (SELECT id FROM offene_posten WHERE auftrag_id=?)"}[t]
        n = con.execute(f"UPDATE {t} SET {sp}='2013-03-0' || (1 + abs(random()) % 8) WHERE {wo}", (k["id"] if "kunde_id" in wo else a["id"],)).rowcount
    except sqlite3.Error as f: print("  ", t, sp, f)
con.execute("UPDATE kunden SET angelegt='2013-01-01', geaendert='2013-01-01' WHERE id=?", (k["id"],)); con.commit()
info = A("GET", f"kunden/{k['id']}/anonymisieren"); print("\nVorschau:", info["_s"], {x: info.get(x) for x in info if not x.startswith("_")})
erg = A("POST", f"kunden/{k['id']}/anonymisieren", {"bestaetigung": "ANONYMISIEREN"}, h={"X-Bestaetigt": "anonymisieren"}); print("Ausgeführt:", erg["_s"], erg.get("fehler", ""), {x: erg.get(x) for x in ("erledigt", "korrespondenz")})
con.close(); con = sqlite3.connect(D + "/buero.db", timeout=20); con.row_factory = sqlite3.Row
nach = scan("nach")
print("\n== Marken, die NACH dem Anonymisieren noch in der Datenbank stehen:")
for m in sorted(nach): print("  %-26s %s" % (m, sorted(nach[m])))
print("== entfernt:", sorted(set(vorher) - set(nach)))
dat_nach = subprocess.run(f"grep -rlaE 'QX[A-Z]+QX|qxmailqx' {D} --exclude=buero.db* 2>/dev/null | head -50", shell=True, capture_output=True, text=True).stdout.split()
print("== Dateien mit Marken danach:", [d.replace(D, "") for d in dat_nach][:30])
print("== Dateien zum Kunden/zur Rechnung, die noch liegen:")
rn = con.execute("SELECT nummer, art, pdf, status FROM belege WHERE auftrag_id=?", (a["id"],)).fetchall(); print("  Belege:", [dict(r) for r in rn])
for r in rn:
    for f in glob.glob(D + f"/**/*{r['nummer']}*", recursive=True) if r["nummer"] else []: print("   noch da:", f.replace(D, ""), os.path.getsize(f))
print("  Unterschriften-Dateien:", [f.replace(D, "") for f in glob.glob(D + "/unterschriften/*")][:8], "| Signaturen-Zeilen:", [dict(r) for r in con.execute("SELECT id, name, datei, bezug FROM signaturen")][:4] if "signaturen" in tabs else "-")
print("  Bank-Ablage:", [f.replace(D, "") for f in glob.glob(D + "/bank/*")][:5])
# PDF-Texte prüfen
try:
    from pypdf import PdfReader
    for f in glob.glob(D + "/**/*.pdf", recursive=True):
        try:
            t = " ".join((p.extract_text() or "") for p in PdfReader(f).pages)
            if "QX" in t: print("   PDF mit Kundendaten:", f.replace(D, ""), re.findall(r"QX[A-ZÄÖÜ]+QX", t)[:5])
        except Exception as x: pass
except ImportError: print("pypdf fehlt")
pr = A("GET", "service/protokoll?voll=1"); print("Protokoll danach in Ordnung:", pr.get("pruefung", {}).get("ok"), "| Belegprüfung:", pr.get("belege", {}).get("ok"), str(pr.get("belege", {}).get("fehler"))[:300])
