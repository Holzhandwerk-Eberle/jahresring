import json, zipfile, io, csv, glob, os, sys
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
from lxml import etree
c = cl(); rq(c, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
s, b, _ = rq(c, "POST", "/api/service/pruefer", {"von": "2026-01-01", "bis": "2026-12-31"}); r = json.loads(b); print("Export:", s, {k: r.get(k) for k in ("datei", "tabellen", "belege", "fehler")})
D = "/tmp/claude-0/t/v25/eberle-buero/daten"; z = sorted(glob.glob(D + "/**/" + r["datei"], recursive=True))[0]; zf = zipfile.ZipFile(z)
namen = zf.namelist(); print(len(namen), "Dateien:", [n for n in namen if "/" not in n])
dtd = etree.DTD(io.BytesIO(zf.read("gdpdu-01-09-2004.dtd"))); doc = etree.fromstring(zf.read("index.xml"))
print("index.xml gültig gegen die DTD:", dtd.validate(doc), [str(e)[:120] for e in dtd.error_log][:3])
ok = True
for t in doc.iter("Table"):
    url = t.findtext("URL"); vl = t.find("VariableLength"); spalten = [x for x in vl if x.tag in ("VariablePrimaryKey", "VariableColumn")]
    trenn = vl.findtext("ColumnDelimiter") or ";"; zeilen = list(csv.reader(io.StringIO(zf.read(url).decode("utf-8-sig")), delimiter=trenn, quotechar=(vl.findtext("TextEncapsulator") or '"')))
    falsch = [i for i, zl in enumerate(zeilen) if len(zl) != len(spalten)]
    typfehler = 0
    for zl in zeilen:
        for sp, w in zip(spalten, zl):
            if sp.find("Numeric") is not None and w not in ("",):
                try: float(w.replace(".", "").replace(",", ".")) if "," in w else float(w)
                except ValueError: typfehler += 1
            if sp.find("Date") is not None and w and not (len(w) == 10 and w[2] == "." and w[5] == "."): typfehler += 1
    print(f"  {url:28} {len(spalten):2} Spalten, {len(zeilen):3} Zeilen, Zeilen mit falscher Spaltenzahl: {len(falsch)}, Typfehler: {typfehler}"); ok = ok and not falsch and not typfehler
print("Tabellen stimmig:", ok, "| Belegdateien im Paket:", len([n for n in namen if n.lower().endswith((".pdf", ".xml")) and "/" in n]))
