"""Preisimport: Zeichensätze, Trennzeichen, Zahlenformate, Excel-Besonderheiten, kaputte und große Dateien."""
import json, re, sys, base64, time, io, zipfile
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None):
    z = time.time(); s, b, hd = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    j["_ms"] = int((time.time() - z) * 1000); return j
li = A("POST", "lieferanten", {"kurzname": "Beschlag Import AG"}); lid = li["id"]
def lesen(roh, name, zeig=True, **kw):
    x = A("POST", "preisimport/lesen", {"daten": base64.b64encode(roh).decode(), "dateiname": name, "lieferant_id": lid, **kw})
    if x["_s"] != 200: return f"HTTP {x['_s']} {x.get('fehler', '')[:150]}", x
    y = A("POST", "preisimport/neue", {"schluessel": x.get("schluessel"), "lieferant_id": lid})
    art = y.get("neue") or y.get("artikel") or []
    info = {k_: (v if not isinstance(v, (list, dict)) else len(v)) for k_, v in x.items() if not k_.startswith("_") and k_ not in ("schluessel",)}
    return (f"ok {x['_ms']} ms | {json.dumps(info, ensure_ascii=False)[:230]} | Beispiel: " + json.dumps([{k_: a.get(k_) for k_ in ('nummer', 'bezeichnung', 'preis', 'einheit', 'pe') if k_ in a} for a in art[:3]], ensure_ascii=False)[:330]), x
kopf = "Artikelnummer;Bezeichnung;Einheit;Preis\n"
zeilen = "4711;Topfband Größe 35 mm Türanschlag;Stk;3,45\n4712;Schubkastenführung „Tandem“ 500;Paar;18,90\n4713;Möbelgriff Edelstahl Ø 12;Stk;1.234,50\n"
print("== Zeichensätze und Trennzeichen")
for name, roh in (("cp1252, Semikolon", (kopf + zeilen).encode("cp1252", "replace")), ("UTF-8 mit BOM", ("﻿" + kopf + zeilen).encode("utf-8")), ("UTF-8 ohne BOM", (kopf + zeilen).encode("utf-8")),
                  ("UTF-16 (Excel „Unicode-Text“), Tab", (kopf + zeilen).replace(";", "\t").encode("utf-16")), ("Komma getrennt, englische Zahlen", 'Item No,Description,Unit,Price\n4711,"Hinge, soft close",pcs,3.45\n4713,"Handle 12",pcs,"1,234.50"\n'.encode("utf-8")),
                  ("Mac-Zeilenenden (CR)", (kopf + zeilen).replace("\n", "\r").encode("cp1252", "replace")), ("Leerzeilen und Titelzeile davor", ("Preisliste 2026 gültig ab 01.01.2026;;;\n\n" + kopf + zeilen).encode("cp1252", "replace"))):
    print("  %-40s %s" % (name, lesen(roh, "liste.csv")[0]))
print("== Zahlenformate")
for preis, soll in (("3,45", 3.45), ("1.234,50", 1234.5), ("1,234.50", 1234.5), ("1'234.50", 1234.5), ("1.234", "1234 oder 1,234?"), ("12.5", 12.5), ("3,45 €", 3.45), ("EUR 3,45", 3.45), ("-2,00", "negativ"), ("0", 0), ("", "leer"), ("auf Anfrage", "Text"), ("1,2E+02", 120)):
    t, x = lesen(("Artikelnummer;Bezeichnung;Einheit;Preis\nA1;Testartikel;Stk;" + preis + "\n").encode("utf-8"), "z.csv")
    m = re.search(r'"preis": ([^,}]+)', t); print("  Preis %-14r erwartet %-18s → gelesen %s %s" % (preis, soll, m.group(1) if m else "–", "" if m else t[:140]))
print("== Excel")
def xlsx(zellen_xml, shared=None):
    p = io.BytesIO()
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Preise" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        if shared is not None: z.writestr("xl/sharedStrings.xml", '<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' + "".join(f"<si><t>{s}</t></si>" for s in shared) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + zellen_xml + '</sheetData></worksheet>')
    return p.getvalue()
S = ["Artikelnummer", "Bezeichnung", "Einheit", "Preis", "Topfband", "Stk", "Griff"]
kopfz = '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c></row>'
for name, rows in (("Zahlzellen 3.45 / 1234.5", '<row r="2"><c r="A2"><v>4711</v></c><c r="B2" t="s"><v>4</v></c><c r="C2" t="s"><v>5</v></c><c r="D2"><v>3.45</v></c></row><row r="3"><c r="A3"><v>4713</v></c><c r="B3" t="s"><v>6</v></c><c r="C3" t="s"><v>5</v></c><c r="D3"><v>1234.5</v></c></row>'),
                   ("Zahlzelle 1.234 (ein Euro 23,4 Cent)", '<row r="2"><c r="A2"><v>4711</v></c><c r="B2" t="s"><v>4</v></c><c r="C2" t="s"><v>5</v></c><c r="D2"><v>1.234</v></c></row>'),
                   ("Gleitkommarest 12.340000000000002", '<row r="2"><c r="A2"><v>4711</v></c><c r="B2" t="s"><v>4</v></c><c r="C2" t="s"><v>5</v></c><c r="D2"><v>12.340000000000002</v></c></row>'),
                   ("Exponent 1.2E-2", '<row r="2"><c r="A2"><v>4711</v></c><c r="B2" t="s"><v>4</v></c><c r="C2" t="s"><v>5</v></c><c r="D2"><v>1.2E-2</v></c></row>'),
                   ("Artikelnummer 0004711 als Zahl 4711.0", '<row r="2"><c r="A2"><v>4711.0</v></c><c r="B2" t="s"><v>4</v></c><c r="C2" t="s"><v>5</v></c><c r="D2"><v>3.5</v></c></row>'),
                   ("lange Nummer 4006381333931 als 4.006381333931E12", '<row r="2"><c r="A2"><v>4.006381333931E12</v></c><c r="B2" t="s"><v>4</v></c><c r="C2" t="s"><v>5</v></c><c r="D2"><v>3.5</v></c></row>'),
                   ("Formelzelle mit Ergebnis", '<row r="2"><c r="A2"><v>4711</v></c><c r="B2" t="s"><v>4</v></c><c r="C2" t="s"><v>5</v></c><c r="D2"><f>3*1.15</f><v>3.4499999999999997</v></c></row>'),
                   ("Zellen ohne Zellbezug (r fehlt)", '<row><c><v>4711</v></c><c t="s"><v>4</v></c><c t="s"><v>5</v></c><c><v>3.45</v></c></row>')):
    kz = kopfz if "ohne Zellbezug" not in name else '<row><c t="s"><v>0</v></c><c t="s"><v>1</v></c><c t="s"><v>2</v></c><c t="s"><v>3</v></c></row>'
    print("  %-48s %s" % (name, lesen(xlsx(kz + rows, S), "liste.xlsx")[0][:330]))
print("== kaputte Dateien")
for name, roh, dn in (("leere Datei", b"", "leer.csv"), ("nur Kopfzeile", kopf.encode(), "kopf.csv"), ("PDF als .csv", b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj", "liste.csv"), ("Zufallsbytes", bytes(range(256)) * 20, "x.csv"),
                      ("altes Excel .xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 600, "liste.xls"), ("kaputtes ZIP als .xlsx", b"PK\x03\x04kaputt", "liste.xlsx"), ("eine Spalte", b"Preis\n3,45\n", "s.csv"), ("JSON", b'{"a": 1}', "x.json")):
    print("  %-22s %s" % (name, lesen(roh, dn)[0][:200]))
print("== große Datei")
gross = (kopf + "".join(f"G{i:06d};Artikel {i} Beschlag verzinkt;Stk;{1 + i % 500},{i % 100:02d}\n" for i in range(120000))).encode("cp1252")
t, x = lesen(gross, "gross.csv"); print("  120.000 Zeilen (%.1f MB): %s" % (len(gross) / 1048576, t[:200]))
z = time.time(); y = A("POST", "preisimport/lesen", {"schluessel": x.get("schluessel"), "lieferant_id": lid}); print("  erneutes Öffnen aus dem Zwischenspeicher: %d ms" % y["_ms"])
dop = (kopf + "D1;Erster;Stk;1,00\nD1;Zweiter mit gleicher Nummer;Stk;2,00\nd1;Dritter klein geschrieben;Stk;3,00\n").encode()
print("  doppelte Artikelnummern in einer Datei:", lesen(dop, "d.csv")[0][:300])
