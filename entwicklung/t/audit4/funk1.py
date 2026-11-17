"""Übertrag in Schlussrechnung (mit Abschlägen) und in Belegen mit Titeln; Druckweg über den Browser."""
import json, re, sys, base64, time, os, io, subprocess
sys.path.insert(0, "/home/claude/eberle-buero/lib")
from pypdf import PdfReader
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
AUS = "/tmp/claude-0/t/audit4/ue"
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None):
    s, b, hd = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    return j
de = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
k = A("POST", "kunden", {"kurzname": "Übertrag, Ulla", "nachname": "Übertrag", "vorname": "Ulla", "strasse": "Weg", "hausnr": "3", "plz": "88069", "ort": "Tettnang"})
def auftrag(n, titel=False):
    a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Ausbau"})
    if titel: print("  Titel setzen:", A("PUT", f"auftraege/{a['id']}/titel", {"titel": [{"nr": 1, "name": "Küche"}, {"nr": 2, "name": "Bad"}, {"nr": 3, "name": "Flur"}]})["_s"])
    for i in range(1, n + 1):
        po = A("POST", f"auftraege/{a['id']}/positionen", {"text": f"Schrank {i}", **({"titel": 1 + (i - 1) * 3 // n} if titel else {})}); pid = po.get("id") or po["position"]["id"]
        A("PUT", f"positionen/{pid}", {"einzelpreis": 100 * i, "preis_manuell": 1, "menge": 1, "text": f"<b>Schrank {i}</b><br>Korpus Dekorspan weiß<br>Front Eiche furniert<br>Beschläge Blum", **({"titel": 1 + (i - 1) * 3 // n} if titel else {})})
    return a
def seiten(bid, name):
    st, daten, _ = rq(inh, "GET", f"/druck/{bid}.pdf", roh=True); open(f"{AUS}/{name}.pdf", "wb").write(daten)
    return [re.sub(r"\s+", " ", (p.extract_text() or "").replace("\xa0", " ")) for p in PdfReader(io.BytesIO(daten)).pages]
print("== Schlussrechnung mit zwei Abschlägen")
a = auftrag(26)
for pz in (30, 30):
    ab = A("POST", f"auftraege/{a['id']}/belege", {"art": "abschlag", "prozent": pz}); f = A("POST", f"belege/{ab['id']}/festschreiben", {}); print("  Abschlag", pz, "%:", ab["_s"], (f.get("beleg") or f).get("nummer"), (f.get("beleg") or f).get("brutto"), f.get("fehler", ""))
sr = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); b = A("GET", f"belege/{sr['id']}"); s = b["daten"]["summen"]
print("  Schlussrechnung Summen:", {k_: s.get(k_) for k_ in ("netto_positionen", "netto", "ust", "brutto", "abzug_brutto", "zahlbetrag")}, "| Abzüge:", [(x.get("nummer"), x.get("brutto")) for x in b["daten"].get("abzuege", [])])
soll_netto = sum(100 * i for i in range(1, 27)); print("  Nachrechnung: netto %.2f, USt %.2f, brutto %.2f, abzüglich 2 × 30 %% = %.2f → Rest %.2f" % (soll_netto, soll_netto * .19, soll_netto * 1.19, 2 * round(round(soll_netto * .3, 2) * 1.19, 2), soll_netto * 1.19 - 2 * round(round(soll_netto * .3, 2) * 1.19, 2)))
sn = seiten(sr["id"], "schluss")
lauf = 0
for i, t in enumerate(sn):
    nummern = sorted({int(m) for m in re.findall(r"Schrank (\d+)", t)}); u = re.findall(r"Übertrag\s*([\d.]+,\d\d)", t)
    print("  Seite %d: Positionen %s–%s | Übertrag: %s | Abzüge auf der Seite: %s | Zahlbetrag: %s" % (i + 1, nummern[:1], nummern[-1:], u, len(re.findall(r"Abschlagsrechnung", t)), re.findall(r"(?:Zahlbetrag|Restbetrag|zu zahlen)[^0-9]{0,30}([\d.]+,\d\d)", t)[:2]))
print("== Angebot mit Titeln")
a2 = auftrag(27, titel=True); an = A("POST", f"auftraege/{a2['id']}/belege", {"art": "angebot"}); bb = A("GET", f"belege/{an['id']}")
print("  Zeilentypen:", [z.get("typ") for z in bb["daten"]["zeilen"]][:12], "| uebertrag:", bb["druck"].get("uebertrag"))
for i, t in enumerate(seiten(an["id"], "titel")):
    nummern = sorted({int(m) for m in re.findall(r"Schrank (\d+)", t)}); u = re.findall(r"Übertrag\s*([\d.]+,\d\d)", t)
    print("  Seite %d: Positionen %s–%s | Übertrag: %s | Titelsummen: %s" % (i + 1, nummern[:1], nummern[-1:], u, re.findall(r"Summe (?:Titel )?[^0-9]{0,22}([\d.]+,\d\d)", t)[:4]))
for n in ("schluss", "titel"):
    subprocess.run(["pdftoppm", "-r", "45", "-png", f"{AUS}/{n}.pdf", f"{AUS}/{n}"], check=False)
print(sorted(os.listdir(AUS)))
print("IDS", sr["id"], an["id"])
