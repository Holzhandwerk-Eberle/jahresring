"""Version 149, Preis- und Tabellenimport: Zeichensätze und Zeilenenden, Zahlenformate mit Hinweisen, Excel-Sonderfälle,
Größengrenze beim Entpacken, kaputte Dateien ohne internen Fehler. Erwartet eine frische Prüfinstanz."""
import json, re, sys, base64, time, io, zipfile, resource
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:500]))
    if not bed: fehler.append(name)
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None):
    s, b, hd = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
lid = A("POST", "lieferanten", {"kurzname": "Beschlag Import AG"})["id"]
def lesen(roh, name):
    x = A("POST", "preisimport/lesen", {"daten": base64.b64encode(roh).decode(), "dateiname": name, "lieferant_id": lid})
    art = []
    if x["_s"] == 200 and x.get("schluessel"):
        y = A("POST", "preisimport/neue", {"schluessel": x["schluessel"], "lieferant_id": lid}); art = y.get("neu") or []
    return x, {a.get("artnr"): a.get("preis") for a in art}, art
kopf = "Artikelnummer;Bezeichnung;Einheit;Preis\n"
zeilen = "4711;Topfband Größe 35 mm;Stk;3,45\n4712;Schubkastenführung „Tandem“;Paar;18,90\n4713;Möbelgriff Ø 12;Stk;1.234,50\n"
soll = {"4711": 3.45, "4712": 18.9, "4713": 1234.5}

print("== I4: Zeichensätze, Zeilenenden")
for name, roh in (("cp1252", (kopf + zeilen).encode("cp1252", "replace")), ("UTF-8 mit BOM", ("﻿" + kopf + zeilen).encode("utf-8")), ("UTF-8", (kopf + zeilen).encode("utf-8")),
                  ("UTF-16 mit Kennung (Excel „Unicode-Text“), Tabulator", (kopf + zeilen).replace(";", "\t").encode("utf-16")),
                  ("UTF-16 ohne Kennung", (kopf + zeilen).replace(";", "\t").encode("utf-16-le")),
                  ("alte Mac-Zeilenenden (nur CR)", (kopf + zeilen).replace("\n", "\r").encode("cp1252", "replace")), ("Windows-Zeilenenden", (kopf + zeilen).replace("\n", "\r\n").encode("utf-8"))):
    x, preise, art = lesen(roh, "liste.csv")
    ok(f"{name}: drei Artikel mit richtigen Preisen", x["_s"] == 200 and preise == soll and ("UTF-16" not in name or any("Größe" in (a.get("text") or "") for a in art)), (x["_s"], x.get("fehler"), preise))

print("== I5: Zahlenformate")
def spalte(werte):
    x, preise, _ = lesen((kopf + "".join(f"A{i};Artikel {i};Stk;{w}\n" for i, w in enumerate(werte))).encode("utf-8"), "z.csv")
    return x, [preise.get(f"A{i}") for i in range(len(werte))]
x, p = spalte(["3,45", "1.234,50", "1.250", "EUR 3,45", "3,45 €", "12,5"])
ok("deutsche Spalte: 3,45 · 1.234,50 · „1.250“ = 1250 · „EUR 3,45“ · „3,45 €“ · 12,5", p == [3.45, 1234.5, 1250.0, 3.45, 3.45, 12.5], p)
ok("… mit dem Hinweis, wie „1.250“ gelesen wurde", "„1.250“" in (x.get("hinweis") or "") and "1.250,00 €" in x["hinweis"] and "Komma als Dezimalzeichen" in x["hinweis"], x.get("hinweis"))
x, p = spalte(["3.45", "1,234.50", "1.250", "12.5", "1'234.50"])
ok("englische Spalte: 3.45 · 1,234.50 · „1.250“ = 1,25 · 12.5 · 1'234.50, ohne Hinweis", p == [3.45, 1234.5, 1.25, 12.5, 1234.5] and not x.get("hinweis"), (p, x.get("hinweis")))
x, p = spalte(["1.250", "2.500", "17"])
ok("Spalte nur mit „1.250“, „2.500“ und „17“: gelesen als 1,25 und 2,50 – mit dem Hinweis, dass das mehrdeutig ist", p == [1.25, 2.5, 17.0] and "mehrdeutig" in (x.get("hinweis") or "") and "2 Preise" in x["hinweis"], (p, x.get("hinweis")))
x, p = spalte(["3,45", "auf Anfrage", "-2,00", "", "1.2.3", "7,00"])
h = x.get("hinweis") or ""
ok("nicht lesbare, negative und fehlende Preise werden übersprungen und gezählt", p == [3.45, None, None, None, None, 7.0] and "2 Zeilen mit nicht lesbarem Preis" in h and "auf Anfrage" in h and "1 Zeile mit negativem Preis" in h and "1 Zeile ohne Preis" in h, (p, h))
x, p = spalte(["2.000.000,00", "1.234.567", "0,5"])
ok("mehrere Tausenderpunkte: 2.000.000,00 und 1.234.567", p == [2000000.0, 1234567.0, 0.5], p)

print("== I4: Excel")
def xlsx(zellen_xml, shared=None, extra=None):
    p = io.BytesIO()
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Preise" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        if shared is not None: z.writestr("xl/sharedStrings.xml", '<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' + "".join(f"<si><t>{s}</t></si>" for s in shared) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", extra if extra is not None else '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + zellen_xml + '</sheetData></worksheet>')
    return p.getvalue()
S = ["Artikelnummer", "Bezeichnung", "Einheit", "Preis", "Topfband", "Stk"]
kz = '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c></row>'
x, p, _ = lesen(xlsx(kz + '<row r="2"><c r="A2"><v>4711</v></c><c r="B2" t="s"><v>4</v></c><c r="C2" t="s"><v>5</v></c><c r="D2"><v>3.45</v></c></row>', S), "liste.xlsx")
ok("gewöhnliche Excel-Datei", x["_s"] == 200 and p == {"4711": 3.45}, (x["_s"], x.get("fehler"), p))
ohne = '<row><c t="s"><v>0</v></c><c t="s"><v>1</v></c><c t="s"><v>2</v></c><c t="s"><v>3</v></c></row><row><c><v>4711</v></c><c t="s"><v>4</v></c><c t="s"><v>5</v></c><c><v>3.45</v></c></row>'
x, p, _ = lesen(xlsx(ohne, S), "liste.xlsx")
ok("Excel-Datei ohne Zellbezüge (r fehlt): wird gelesen (bisher interner Fehler)", x["_s"] == 200 and p == {"4711": 3.45}, (x["_s"], x.get("fehler"), p))
x, p, _ = lesen(xlsx(kz + '<row r="2"><c r="A2"><v>4711</v></c><c r="B2" t="s"><v>99</v></c><c r="C2" t="s"><v>abc</v></c><c r="D2"><v>3.45</v></c></row>', S), "liste.xlsx")
ok("Verweis auf einen Text, den es nicht gibt: Zelle bleibt leer, kein Fehler", x["_s"] == 200 and p == {"4711": 3.45}, (x["_s"], x.get("fehler"), p))
x, p, _ = lesen(xlsx("", S, extra='<?xml version="1.0"?><worksheet><sheetData><row><c><v>1</v></c></row>'), "liste.xlsx")
ok("beschädigtes Tabellenblatt: verständliche Absage", x["_s"] == 400 and "beschädigt" in x.get("fehler", ""), (x["_s"], x.get("fehler")))
x, p, _ = lesen(xlsx("", S, extra='<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>&lol2;</t></is></c></row></sheetData></worksheet>'), "liste.xlsx")
ok("Excel-Datei mit Entity-Deklaration: abgelehnt", x["_s"] == 400 and "Sicherheitsgründen" in x.get("fehler", ""), (x["_s"], x.get("fehler")))

print("== S6: Größe beim Entpacken")
riesig = '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + ('<row><c t="inlineStr"><is><t>' + "A" * 1000 + '</t></is></c></row>') * 1 + " " * (200 * 1024 * 1024) + '</sheetData></worksheet>'
bombe = xlsx("", S, extra=riesig); del riesig
def speicher():
    if not __import__("os").path.isdir("/proc"): return 0   # unter Windows ohne Messung des Arbeitsspeichers
    for f in __import__("os").listdir("/proc"):
        if f.isdigit():
            try:
                if b"BUERO_PORT=8799" in open(f"/proc/{f}/environ", "rb").read(): return int(re.search(r"VmRSS:\s+(\d+)", open(f"/proc/{f}/status").read()).group(1)) // 1024
            except OSError: pass
    return 0
vor = speicher(); z = time.time(); x, p, _ = lesen(bombe, "gross.xlsx"); dauer = time.time() - z; nach = speicher()
ok(f"Excel-Datei mit {len(bombe) // 1024} KB, die ausgepackt 200 MB hätte: abgelehnt, ohne sie auszupacken ({dauer:.1f} s, Arbeitsspeicher {vor} → {nach} MB)", x["_s"] == 400 and "zu groß" in x.get("fehler", "") and nach - vor < 80, (x["_s"], x.get("fehler"), vor, nach))
x2 = A("POST", "kunden/import", {"daten": base64.b64encode(bombe).decode(), "dateiname": "kunden.xlsx", "vorschau": True})
ok("dieselbe Grenze gilt beim Kundenimport", x2["_s"] == 400 and "zu groß" in x2.get("fehler", ""), (x2["_s"], x2.get("fehler"), str(x2)[:200]))

print("== kaputte Dateien")
for name, roh, dn in (("leere Datei", b"", "leer.csv"), ("nur Kopfzeile", kopf.encode(), "kopf.csv"), ("PDF als .csv", b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj", "liste.csv"), ("Zufallsbytes", bytes(range(256)) * 20, "x.csv"),
                      ("altes Excel .xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 600, "liste.xls"), ("kaputtes ZIP als .xlsx", b"PK\x03\x04kaputt", "liste.xlsx"), ("eine Spalte", b"Preis\n3,45\n", "s.csv"),
                      ("Anführungszeichen ohne Ende", (kopf + '4711;"Topfband;Stk;3,45\n' + "x" * 200000).encode(), "q.csv"), ("Nullbytes mitten im Text", (kopf + zeilen).encode() + b"\x00\x00\x00" + zeilen.encode(), "n.csv")):
    x, p, _ = lesen(roh, dn)
    ok(f"{name}: Antwort ohne internen Fehler ({x['_s']}{' – ' + x['fehler'][:70] if x.get('fehler') else ''})", x["_s"] in (200, 400), (x["_s"], str(x)[:200]))
print("FEHLER:", fehler)
sys.exit(1 if fehler else 0)
