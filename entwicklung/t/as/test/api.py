import json, sys, base64, io
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas Inhaber", "login": "jonas", "passwort": "geheim123", "passwort2": "geheim123", "firma": "Testbetrieb"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
fehler = []
def P(pfad, d=None, m="POST", erwartet=200, o=None):
    s, b, _ = rq(o or inh, m, "/api/" + pfad, d)
    if s != erwartet:
        fehler.append((m, pfad, s, b[:200])); print("  !!", m, pfad, s, b[:200])
    return J(b)
from PIL import Image
buf = io.BytesIO(); im = Image.new("RGB", (300, 100), "white")
from PIL import ImageDraw; ImageDraw.Draw(im).line((10, 50, 290, 60), fill="black", width=4); im.save(buf, "PNG")
PNG = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
m1 = P("mitarbeiter", {"vorname": "Max", "nachname": "Werk", "eintritt": "2025-01-01"}); m2 = P("mitarbeiter", {"vorname": "Azubi", "nachname": "Jung", "eintritt": "2026-08-01", "geburtsdatum": "2010-05-01"})
w1 = P("werkzeuge", {"bezeichnung": "Formatkreissäge Altendorf F45", "art": "Stationäre Maschine", "standort": "Maschinenraum"})
w2 = P("werkzeuge", {"bezeichnung": "Abrichthobelmaschine", "art": "Stationäre Maschine"})
print("werkzeuge", w1.get("id"), w2.get("id"))
v = P("arbeitsschutz/vorlagen", m="GET"); print("vorlagen", len(v["gb"]), len(v["themen"]), len(v["zeichen"]))
ws = P("arbeitsschutz/werkzeuge", m="GET"); print("vorschlag", [(x["bezeichnung"], x["vorschlag"]) for x in ws])
g = P("arbeitsschutz/gb", {"art": "maschine", "werkzeug_ids": [w1["id"]], "vorlage": ws[0]["vorschlag"], "bereich": "Maschinenraum"})
print("GB", g["nummer"], g["titel"], len(g["zeilen"]), g["offen"])
# Freigabe ohne Bewertung → 409
P(f"arbeitsschutz/gb/{g['id']}/freigeben", {"name": "Jonas", "png": PNG}, erwartet=409)
z = g["zeilen"]
for zz in z:
    zz["risiko"] = "mittel"
    for i, m in enumerate(zz["m"]):
        m["status"] = "vorhanden" if i else "umsetzen"
        if i == 0: m["wer"] = "Jonas"; m["bis"] = "2026-12-01"
g = P(f"arbeitsschutz/gb/{g['id']}", {"zeilen": z, "beteiligte": "Jonas, Max"}, "PUT"); print("pruefung", g["pruefung"], g["offen"])
g = P(f"arbeitsschutz/gb/{g['id']}/freigeben", {"name": "Jonas", "png": PNG}); print("freigegeben", g["status"], g["stand"], g["naechste"], len(g["fassungen"]))
g2 = P(f"arbeitsschutz/gb/{g['id']}", {"bemerkung": "neu"}, "PUT"); print("nach Änderung", g2["status"])
P(f"arbeitsschutz/gb/{g['id']}", m="DELETE", erwartet=409)
gp = P("arbeitsschutz/gb", {"art": "psychisch"}); print("psych", len(gp["zeilen"]), gp["intervall"])
# BA
ba = P("arbeitsschutz/ba", {"art": "maschine", "werkzeug_ids": [w1["id"]]}); print("BA", ba["nummer"], ba["titel"], ba["vorlage"], ba["symbole"], ba["abschnitte"]["schutz"][:80])
ba = P(f"arbeitsschutz/ba/{ba['id']}/freigeben", {"name": "Jonas", "png": PNG}); print("BA frei", ba["status"])
# Material + Gefahrstoff
mat = P("material", {"kategorie": "beschichtung", "bezeichnung": "Klarlack seidenmatt\nLösemittelhaltig"}); print("mat", mat.get("id"), mat.get("nummer"))
gs = P(f"arbeitsschutz/gefahrstoff/{mat['id']}", {"gefahrstoff": 1, "h_saetze": "H226, H336, EUH066, H412", "signalwort": "Achtung", "lagerklasse": "3", "psa": "Schutzhandschuhe Nitril, Schutzbrille"}, "PUT")
print("GHS-Vorschlag", P("arbeitsschutz/ghs?h=H226,H336,EUH066,H412", m="GET"))
gs = P(f"arbeitsschutz/gefahrstoff/{mat['id']}", {"ghs": ["GHS02", "GHS07"]}, "PUT")
pdf = base64.b64encode(b"%PDF-1.4\n%test\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF").decode()
d1 = P("arbeitsschutz/dateien", {"art": "sdb", "material_id": mat["id"], "dateiname": "SDB Klarlack.pdf", "daten": pdf, "ausgabe": "2025-03-01"})
d2 = P("arbeitsschutz/dateien", {"art": "sdb", "material_id": mat["id"], "dateiname": "SDB Klarlack 2026.pdf", "daten": pdf, "ausgabe": "2026-03-01"})
print("dateien", [(x["titel"], x["aktuell"]) for x in P(f"arbeitsschutz/dateien?material={mat['id']}", m="GET")])
s, b, hd = rq(inh, "GET", f"/api/arbeitsschutz/datei/{d2['id']}", roh=True); print("datei", s, hd.get("Content-Type"), b[:8])
bag = P("arbeitsschutz/ba", {"art": "gefahrstoff", "material_id": mat["id"]}); print("BA Gefahrstoff", bag["abschnitte"]["gefahren"])
P(f"arbeitsschutz/ba/{bag['id']}/freigeben", {"name": "Jonas", "png": PNG}, erwartet=409)
print("verzeichnis", [(x["name"], x["ghs"], bool(x["sdb"]), x["ba"]) for x in P("arbeitsschutz/gefahrstoffe", m="GET")])
# Themen + Unterweisung
t1 = P("arbeitsschutz/themen", {"vorlage": "uwh-011"}); t2 = P("arbeitsschutz/themen", {"vorlage": "gefahrstoffe"}); t3 = P("arbeitsschutz/themen", {"vorlage": "erste-hilfe"})
P(f"arbeitsschutz/themen/{t1['id']}", {"ba_ids": [ba["id"]], "werkzeug_ids": [w1["id"]]}, "PUT")
mx = P("arbeitsschutz/matrix", m="GET"); print("matrix", [(z["mitarbeiter"]["name"], {k: v["status"] for k, v in z["themen"].items()}) for z in mx["zeilen"]])
uw = P("arbeitsschutz/unterweisungen", {"thema_ids": [t1["id"], t2["id"]], "mitarbeiter_ids": [m1["id"], m2["id"]], "anlass": "Erstunterweisung vor Aufnahme der Tätigkeit"})
print("UW", uw["nummer"], uw["titel"], [t["name"] for t in uw["teilnehmer"]], [ (i["titel"], len(i["ba"])) for i in uw["inhalt"]])
P(f"arbeitsschutz/unterweisungen/{uw['id']}/abschliessen", {}, erwartet=409)
tn = uw["teilnehmer"][0]
uw = P(f"arbeitsschutz/unterweisungen/{uw['id']}/unterschreiben", {"teilnehmer_id": tn["id"], "png": PNG, "name": tn["name"]})
P(f"arbeitsschutz/unterweisungen/{uw['id']}", {"ergaenzung": "nachträglich"}, "PUT", erwartet=409)
uw = P(f"arbeitsschutz/unterweisungen/{uw['id']}/unterschreiben", {"rolle": "unterweiser", "png": PNG, "name": "Jonas Inhaber"})
uw = P(f"arbeitsschutz/unterweisungen/{uw['id']}/abschliessen", {}); print("abgeschlossen", uw["status"], uw["entfernt"], [t["name"] for t in uw["teilnehmer"]])
mx = P("arbeitsschutz/matrix", m="GET"); print("matrix", [(z["mitarbeiter"]["name"], z["mitarbeiter"]["jugendlich"], {k: (v["status"], v["faellig"]) for k, v in z["themen"].items()}) for z in mx["zeilen"]])
# Verbandbuch, Qualifikationen, Organisation
P("arbeitsschutz/verbandbuch", {"name": "Max Werk", "verletzung": "Schnitt Daumen", "hergang": "Stecheisen", "massnahmen": "Pflaster", "helfer": "Jonas"})
print("verbandbuch", len(P("arbeitsschutz/verbandbuch", m="GET")))
q = P("arbeitsschutz/qualifikationen", {"mitarbeiter_id": m1["id"], "art": "Ersthelfer", "datum": "2025-02-01"}); print("quali", q["gueltig_bis"], q["gueltig"])
P("arbeitsschutz/organisation", {"organisation": {"betreuung": "Unternehmermodell (alternative bedarfsorientierte Betreuung)", "bereiche": ["Maschinenraum", "Bankraum", "Lackierraum"]}, "notfall": {"unfall": "Jonas 0170 1", "rettung": "112"}}, "PUT")
ue = P("arbeitsschutz/uebersicht", m="GET"); print("Übersicht"); [print("  ", p["stufe"], p["text"]) for p in ue["punkte"]]; [print("  ", "✓" if x["ok"] else "–" if x["ok"] is None else "✗", x["text"], "|", x["hinweis"]) for x in ue["pflichten"]]
print("werkzeug", P(f"arbeitsschutz/werkzeug/{w1['id']}", m="GET"))
# Druckseiten
for pf in (f"/druck/arbeitsschutz/gb/{g['id']}", f"/druck/arbeitsschutz/fassung/{g['fassungen'][0]['id']}", f"/druck/arbeitsschutz/ba/{ba['id']}", f"/druck/arbeitsschutz/ba/{bag['id']}",
           f"/druck/arbeitsschutz/unterweisung/{uw['id']}", "/druck/arbeitsschutz/gefahrstoffverzeichnis", "/druck/arbeitsschutz/notfall", f"/druck/arbeitsschutz/gb/{gp['id']}"):
    s, b, _ = rq(inh, "GET", pf); print("druck", pf, s, len(b), "Fehler" if "Traceback" in b or "Interner" in b else "")
    open("/tmp/claude-0/t/as/test/" + pf.strip("/").replace("/", "_") + ".html", "w").write(b)
# Monatsbeleg
print("mb sig", P(f"monatsbeleg/{m1['id']}/unterschriften?monat=2026-10", m="GET"))
print("mb unterschreiben", P(f"monatsbeleg/{m1['id']}/unterschreiben", {"monat": "2026-10", "rolle": "mitarbeiter", "png": PNG}))
print("mb arbeitgeber", P(f"monatsbeleg/{m1['id']}/unterschreiben", {"monat": "2026-10", "rolle": "arbeitgeber", "png": PNG}))
s, b, _ = rq(inh, "GET", f"/druck/monatsbeleg/{m1['id']}/2026-10"); print("mb druck", s, "data:image/png" in b, "Zeiten danach" in b)
P("zeiten", {"mitarbeiter_id": m1["id"], "datum": "2026-10-05", "beginn": "07:00", "ende": "12:00"})
s, b, _ = rq(inh, "GET", f"/druck/monatsbeleg/{m1['id']}/2026-10"); print("mb nach Änderung", "Zeiten danach geändert" in b)
print("FEHLER:", fehler)
