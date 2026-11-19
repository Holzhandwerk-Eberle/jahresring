"""Übertrag in mehrseitigen Belegen: Zwischensumme unten auf der Seite und oben auf der Folgeseite; einseitige Belege unverändert."""
import json, sys, os, re, io
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
if len(sys.argv) > 1: U = sys.argv[1]
AUS = sys.argv[2] if len(sys.argv) > 2 else "/tmp/claude-0/-home-claude/ec87b02e-c197-5135-8518-1f390bf90317/scratchpad/ue"
os.makedirs(AUS, exist_ok=True)
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:500]))
    if not bed: fehler.append(name)
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None):
    s, b, _ = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    return j
sys.path.insert(0, "/home/claude/eberle-buero/lib")   # pypdf aus dem Programm, nicht aus dem System
from pypdf import PdfReader
def seiten(bid, name):
    st, daten, _ = rq(inh, "GET", f"/druck/{bid}.pdf", roh=True)
    assert st == 200, (st, daten[:200])
    open(os.path.join(AUS, name), "wb").write(daten)
    aus = []
    for p in PdfReader(io.BytesIO(daten)).pages:
        funde = []
        def v(t, cm, tm, *_):
            if (t or "").strip(): funde.append((round((float(p.mediabox.height) - (tm[4] * cm[1] + tm[5] * cm[3] + cm[5])) / 72 * 25.4, 1), t.strip()))
        text = p.extract_text(visitor_text=v)
        aus.append({"text": text, "funde": funde})
    return aus
k = A("POST", "kunden", {"kurzname": "Muster, Max", "nachname": "Muster", "strasse": "Weg 2", "plz": "88099", "ort": "Neukirch"})
def auftrag(n, lang=True):
    a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": f"Küche {n}"})
    for i in range(1, n + 1):
        po = A("POST", f"auftraege/{a['id']}/positionen", {"text": f"Schrank {i}"}); pid = po.get("id") or po["position"]["id"]
        A("PUT", f"positionen/{pid}", {"einzelpreis": 100 * i, "preis_manuell": 1, "menge": 1, "langtext": "<p>Korpus Dekorspan weiß</p><p>Front Eiche furniert</p><p>Beschläge Blum</p>" if lang else ""})
    return a
a = auftrag(24)
b = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"}); bid = b["id"]
bb = A("GET", f"belege/{bid}"); ok("neuer Beleg: Übertrag ist Vorgabe", bb["druck"].get("uebertrag") is True, bb["druck"])
s = seiten(bid, "angebot_lang.pdf"); n = len(s)
ok("langer Beleg hat mehrere Seiten", n >= 3, n)
de = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
def pruefen(s, preis, anzahl, was):
    """Je Seite: Übertrag unten = Summe der bis dahin begonnenen Positionen, Übertrag oben = Wert vom Ende der Vorseite.
    Solange noch Positionen folgen, muss unten ein Übertrag stehen (preis(i) = gedruckter Betrag der Position i)."""
    lauf, gut, letzte_pos, unten_vor = 0.0, True, 0, None
    for i in range(len(s)):
        t = s[i]["text"].replace("\xa0", " ")
        nummern = sorted({int(m) for m in re.findall(r"Schrank (\d+)", t)})
        u = re.findall(r"Übertrag\s*([\d.]+,\d\d)", t)
        lauf += sum(preis(x) for x in nummern if x > letzte_pos)
        letzte_pos = max(nummern + [letzte_pos])
        oben = u.pop(0) if unten_vor is not None and u else None
        unten = u.pop(0) if u else None
        if nummern or oben or unten:
            print("   Seite", i + 1, "Positionen", nummern[:1], "…", nummern[-1:], "oben", oben, "unten", unten)
        gut &= not u and oben == unten_vor and (unten is None or unten == de(lauf)) and (unten is not None or letzte_pos >= anzahl or not lauf)
        unten_vor = unten
    ok(was, gut and letzte_pos == anzahl and unten_vor is None)
pruefen(s, lambda x: 119.0 * x, 24, "Übertrag unten = Summe bis Seitenende, oben = derselbe Wert auf der Folgeseite (Bruttoanzeige)")
ok("Gesamtbetrag stimmt", de(35700) in s[-2]["text"].replace("\xa0", " ") or de(35700) in s[-1]["text"].replace("\xa0", " "))
ok("keine Messmarken im fertigen PDF", not any("JRP" in x["text"] or "JRTAB" in x["text"] or "JRUB" in x["text"] for x in s))
# abschalten
A("PUT", f"belege/{bid}", {"druck": {"uebertrag": False}}); s2 = seiten(bid, "angebot_ohne.pdf")
ok("Übertrag abgeschaltet: keine Zeile", not any("Übertrag" in x["text"] for x in s2), [x["text"][:80] for x in s2])
# einseitiger Beleg unverändert
a1 = auftrag(3, lang=False); b1 = A("POST", f"auftraege/{a1['id']}/belege", {"art": "angebot"}); s1 = seiten(b1["id"], "angebot_kurz.pdf")
ok("einseitiger Beleg: kein Übertrag", not any("Übertrag" in x["text"] for x in s1), len(s1))
A("PUT", f"belege/{b1['id']}", {"druck": {"uebertrag": False}}); s1o = seiten(b1["id"], "angebot_kurz_ohne.pdf")
pos = lambda x, w: [y for y, t in x[0]["funde"] if w in t][:1]
ok("einseitiger Beleg: Druckbild mit und ohne Einstellung gleich", len(s1) == len(s1o) and [f for f in s1[0]["funde"]] == [f for f in s1o[0]["funde"]], (len(s1), len(s1o)))
# sehr langer Beleg mit langen Texten (Zeilen werden über den Seitenwechsel geteilt), Alternativposition und Rabatt, Nettoanzeige beim Geschäftskunden
kg = A("POST", "kunden", {"kurzname": "Firma GmbH", "firma": "Firma GmbH", "art": "geschaeft", "strasse": "Weg 2", "plz": "88099", "ort": "Neukirch"})
a3 = A("POST", "auftraege", {"kunde_id": kg["id"], "bezeichnung": "Ausbau"})
for i in range(1, 31):
    po = A("POST", f"auftraege/{a3['id']}/positionen", {"text": f"Schrank {i}"}); pid = po.get("id") or po["position"]["id"]
    A("PUT", f"positionen/{pid}", {"einzelpreis": 100 * i, "preis_manuell": 1, "menge": 1, "alternativ": 1 if i == 7 else 0,
                                   "text": f"<p><b>Schrank {i}</b></p>" + "".join(f"<p>Zeile {z} der Beschreibung mit etwas Text, damit die Position lang wird.</p>" for z in range(1, (22 if i % 5 == 0 else 3)))})
b3 = A("POST", f"auftraege/{a3['id']}/belege", {"art": "angebot"}); A("PUT", f"belege/{b3['id']}", {"rabatt_pz": 3})
s3 = seiten(b3["id"], "angebot_netto.pdf"); netto = "Gesamt netto" in s3[0]["text"]
pruefen(s3, lambda x: 0.0 if x == 7 else (100.0 if netto else 119.0) * x, 30, "langer Beleg mit geteilten Zeilen, Alternativposition und Rabatt: jeder Übertrag stimmt")
ok("mehr als drei Seiten mit Übertrag", sum(1 for x in s3 if "Übertrag" in x["text"]) >= 4, [("Übertrag" in x["text"]) for x in s3])
# ohne Briefbogen-Vorlage (einfacher Kopf und Fuß): derselbe Beleg
A("PUT", "einstellungen", {"briefvorlage_aktiv": False}); s4 = seiten(b3["id"], "angebot_ohne_vorlage.pdf")
pruefen(s4, lambda x: 0.0 if x == 7 else (100.0 if netto else 119.0) * x, 30, "ohne Briefbogen-Vorlage: jeder Übertrag stimmt")
A("PUT", "einstellungen", {"briefvorlage_aktiv": True})
# festgeschriebene Rechnung ohne gespeicherte Einstellung behält ihr Druckbild
import sqlite3
re_ = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); A("POST", f"belege/{re_['id']}/festschreiben", {})
sr = seiten(re_["id"], "rechnung_neu.pdf"); ok("neue Rechnung nach dem Festschreiben: mit Übertrag", any("Übertrag" in x["text"] for x in sr))
DB = sys.argv[3] if len(sys.argv) > 3 else "/tmp/claude-0/t/v25/eberle-buero/daten/buero.db"
con = sqlite3.connect(DB, timeout=10); roh = json.loads(con.execute("SELECT druck FROM belege WHERE id=?", (re_["id"],)).fetchone()[0] or "{}")
ok("Einstellung wird beim Festschreiben eingefroren", roh.get("uebertrag") is True, roh)
roh.pop("uebertrag"); con.execute("UPDATE belege SET druck=? WHERE id=?", (json.dumps(roh), re_["id"])); con.commit(); con.close()
ok("früher festgeschriebene Rechnung (ohne gespeicherte Einstellung): Einstellung gilt als aus", A("GET", f"belege/{re_['id']}")["druck"].get("uebertrag") is False)
print("FEHLER:", fehler); sys.exit(1 if fehler else 0)
