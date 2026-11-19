"""Spurprüfung (ab Version 152): Prüfinstanz (frisch, Port 8799) mit einem breiten Bestand füllen. Auffällige Werte dienen als Spuren:
Preise 7131.31 (EK Material), 9292.92 (Einzelpreis), 8181.81 (Werkzeug), 4646.46 (Zahlungsauftrag); Löhne 37.73 und 41.17;
Personenbezug QX…QX (Kunde), X…-Wörter (Mitarbeiter, Arbeitsschutz)."""
import json, base64, sys, sqlite3
from datetime import date, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas Inhaber", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Holzwerkstatt Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, c=None, h=None):
    s, b, hd = rq(c or inh, m, "/api/" + p, d, h); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    if s >= 400: print("   !!", m, p, s, (j.get("fehler") or b)[:160])
    return j
heute = date.today(); H = heute.isoformat(); T = lambda x: "QX" + x + "QX"
ident = lambda d: d.get("id") or (d.get("mitarbeiter") or {}).get("id") or (d.get("position") or {}).get("id")
PW = "Pruefung#2026"
A("PUT", "einstellungen", {"firma": "Holzwerkstatt Muster", "firma_inhaber": "Jonas Inhaber", "firma_anschrift": "Musterweg 1\n88069 Tettnang", "steuernummer": "61/123/45678",
                           "sepa_iban": "DE02120300000000202051", "sepa_bic": "BYLADEM1001", "email": "buero@muster.example", "telefon": "07542 1234"})
# Mitarbeiter und Benutzer
m1 = ident(A("POST", "mitarbeiter", {"vorname": "Max", "nachname": "Werk", "lohnart": "stunde", "stundenlohn": 37.73, "eintritt": "2024-01-01"}))
m2 = ident(A("POST", "mitarbeiter", {"vorname": "Eva", "nachname": "Zwei", "lohnart": "minijob", "stundenlohn": 41.17, "eintritt": "2025-03-01"}))
A("PUT", f"mitarbeiter/{m1}", {"geburtsdatum": "1990-05-05", "strasse": "XSTRASSE 5", "plz": "88069", "ort": "Tettnang", "telefon": "0171 XTELEFON", "email": "max@muster.example"})
ben = {}
for lg, rolle, extra in (("buero", "buero", {}), ("werk", "werkstatt", {"mitarbeiter_id": m1}), ("mita", "mitarbeiter", {"mitarbeiter_id": m2}), ("mita1", "mitarbeiter", {"mitarbeiter_id": m1}),
                         ("epers", "eigen", {"eigen": {"bereiche": {"personal": 2}}}), ("emat", "eigen", {"eigen": {"bereiche": {"material": 1}, "preise": False}}),
                         ("eauf", "eigen", {"eigen": {"bereiche": {"auftraege": 1}, "preise": False}}), ("ekal", "eigen", {"eigen": {"bereiche": {"kalender": 1}}}),
                         ("eop", "eigen", {"eigen": {"bereiche": {"op": 1}}}), ("eas", "eigen", {"eigen": {"bereiche": {"arbeitsschutz": 1}}}),
                         ("elief", "eigen", {"eigen": {"bereiche": {"lieferanten": 1}}}), ("ekun", "eigen", {"eigen": {"bereiche": {"kunden": 1}}}), ("estart", "eigen", {"eigen": {"bereiche": {"start": 1}}})):
    r = A("POST", "benutzer", {"name": lg.capitalize(), "login": lg, "passwort": "246813" if rolle == "mitarbeiter" else PW, "rolle": rolle, **extra}); ben[lg] = r.get("id")
print("Benutzer", ben)
# Kunden
k1 = A("POST", "kunden", {"kurzname": T("KUNDE") + ", Gustav", "vorname": "Gustav", "nachname": T("NACH"), "strasse": "Kundenweg", "hausnr": "7", "plz": "88099", "ort": "Neukirch", "telefon": "07528 " + T("TEL"),
                          "email1": "gustav@beispiel.example", "bemerkungen": T("BEM"), "geburtstag": "1970-02-03", "iban": "DE89370400440532013000"})
k2 = A("POST", "kunden", {"kurzname": "Bau GmbH", "firma": "Bau GmbH", "strasse": "Industriestr.", "hausnr": "2", "plz": "88045", "ort": "Friedrichshafen", "email1": "einkauf@bau.example", "ustid": "DE123456789"})
# Lieferant, Material, Lager, Werkzeug
lf = A("POST", "lieferanten", {"kurzname": "Holz AG", "firma": "Holz AG", "strasse": "Sägeweg 2", "plz": "88069", "ort": "Tettnang", "iban": "DE44500105175407324931", "zahlungsziel": 30, "vorsteuer": 19})
mat = A("POST", "material", {"kategorie": "holzwerkstoffe", "bezeichnung": "Spanplatte 19 mm weiß", "einheit": "m²", "ek_preis": 7131.31, "lieferant_id": lf.get("id")})
mat2 = A("POST", "material", {"kategorie": "beschlaege", "bezeichnung": "Topfband 110°", "einheit": "Stk", "ek_preis": 2.35})
A("POST", "lager", {"material_id": mat.get("id"), "art": "zugang", "menge": 10, "preis": 7131.31})
wz = A("POST", "werkzeuge", {"bezeichnung": "Formatkreissäge", "art": "Stationäre Maschine", "hersteller": "Altendorf", "seriennr": "SN-1", "preis": 8181.81})
# Aufträge, Positionen, Belege
a1 = A("POST", "auftraege", {"kunde_id": k1["id"], "bezeichnung": "Einbauschrank Flur", "bemerkungen": T("AUFBEM")})
p1 = ident(A("POST", f"auftraege/{a1['id']}/positionen", {"text": "Einbauschrank, Eiche furniert"})); A("PUT", f"positionen/{p1}", {"einzelpreis": 9292.92, "preis_manuell": 1, "menge": 1})
p2 = ident(A("POST", f"auftraege/{a1['id']}/positionen", {"text": "Montage vor Ort"})); A("PUT", f"positionen/{p2}", {"einzelpreis": 480, "preis_manuell": 1, "menge": 1})
p3 = ident(A("POST", f"auftraege/{a1['id']}/positionen", {"text": "Regal kalkuliert"}))
bel = {}
for art in ("angebot", "ab", "abschlag", "rechnung"):
    b = A("POST", f"auftraege/{a1['id']}/belege", {"art": art, **({"betrag": 3000} if art == "abschlag" else {})}); bel[art] = b.get("id")
A("POST", f"belege/{bel['angebot']}/versendet", {"weg": "Post"})
for art in ("abschlag", "rechnung"):
    if bel.get(art): f = A("POST", f"belege/{bel[art]}/festschreiben", {}); print("fest", art, f.get("_s"), f.get("nummer") or f.get("fehler", "")[:80])
a2 = A("POST", "auftraege", {"kunde_id": k2["id"], "bezeichnung": "Ladentheke"})
p4 = ident(A("POST", f"auftraege/{a2['id']}/positionen", {"text": "Theke"})); A("PUT", f"positionen/{p4}", {"einzelpreis": 5000, "preis_manuell": 1, "menge": 2})
b2 = A("POST", f"auftraege/{a2['id']}/belege", {"art": "rechnung"}); A("POST", f"belege/{b2['id']}/festschreiben", {})
A("POST", "auftragskosten", {"auftrag_id": a1["id"], "material_id": mat.get("id"), "menge": 3, "lager_abgang": 1})
A("POST", "stunden", {"auftrag_id": a1["id"], "datum": H, "stunden": 2.5, "taetigkeit": "Montage", "mitarbeiter": "Max Werk"})
# Zahlung, Mahnung, Termine, Notizen, Briefe, Anhänge
ops = A("GET", "offeneposten"); opl = ops.get("liste") or ops.get("posten") or []
print("offene Posten:", len(opl))
if opl:
    A("POST", f"offeneposten/{opl[0]['id']}/zahlung", {"datum": H, "betrag": 100, "art": "Überweisung", "bemerkung": T("ZAHLTEXT")})
    A("POST", f"offeneposten/{opl[-1]['id']}/mahnung", {"stufe": 0, "text": "Bitte zahlen Sie."})
A("POST", "termine", {"auftrag_id": a1["id"], "typ": "Montage", "titel": "Montage " + T("TERMIN"), "von": H, "bis": H, "notiz": T("TERMINNOTIZ")})
A("POST", "notizen", {"kunde_id": k1["id"], "text": T("NOTIZK")}); A("POST", "notizen", {"auftrag_id": a1["id"], "text": T("NOTIZA")})
br = A("POST", "briefe", {"kunde_id": k1["id"], "betreff": "Brief " + T("BRIEF"), "text": "Hallo " + T("BRIEFTEXT")})
A("POST", "wiedervorlagen", {"kunde_id": k1["id"], "text": T("WV"), "datum": H, "faellig": H})
A("POST", "anhaenge", {"kunde_id": k1["id"], "dateiname": "QXANHANGQX.txt", "daten": base64.b64encode(b"QXANHANGINHALTQX").decode()})
A("POST", "korrespondenz", {"kunde_id": k1["id"], "art": "anruf_ein", "betreff": T("KORR"), "text": T("KORRTEXT"), "datum": H})
bt_ = A("POST", "bautagebuch", {"auftrag_id": a1["id"], "datum": H}); A("PUT", f"bautagebuch/{bt_.get('id')}", {"arbeiten": "Baustelle " + T("BTB"), "wetter": "trocken"})
A("POST", "notizen", {"lieferant_id": lf.get("id"), "text": "LXNOTIZLX"}); A("POST", "briefe", {"lieferant_id": lf.get("id"), "betreff": "Brief LXBRIEFLX"})
A("POST", "korrespondenz", {"lieferant_id": lf.get("id"), "art": "anruf_aus", "betreff": "LXKORRLX", "text": "LXKORRTEXTLX"})
pj = A("POST", "projekte", {"bezeichnung": "Projekt " + T("PROJEKT"), "kunde_id": k1["id"]})
# Lieferantenrechnung, Zahlungsauftrag
z = A("POST", "zahlungen", {"lieferant_id": lf.get("id"), "belegnr": "R-4711", "betrag": 4646.46, "vorsteuer": 19, "belegdatum": H, "faellig": (heute + timedelta(days=14)).isoformat()})
# Personal
for i in range(1, 4):
    A("POST", "zeiten", {"mitarbeiter_id": m1, "datum": (heute - timedelta(days=i)).isoformat(), "beginn": "07:00", "ende": "16:00", "pause": 45, "bemerkung": "XZEIT1"})
    A("POST", "zeiten", {"mitarbeiter_id": m2, "datum": (heute - timedelta(days=i)).isoformat(), "beginn": "08:00", "ende": "12:00", "bemerkung": "XZEIT2"})
A("POST", "abwesenheiten", {"mitarbeiter_id": m2, "art": "krank", "von": (heute + timedelta(days=3)).isoformat(), "bis": (heute + timedelta(days=5)).isoformat(), "notiz": "XKRANKNOTIZ", "status": "genehmigt"})
A("POST", "abwesenheiten", {"mitarbeiter_id": m1, "art": "urlaub", "von": (heute + timedelta(days=10)).isoformat(), "bis": (heute + timedelta(days=12)).isoformat(), "notiz": "XURLAUBNOTIZ", "status": "genehmigt"})
# Arbeitsschutz
A("POST", "arbeitsschutz/vorsorge", {"mitarbeiter_id": m1, "art": "G 44 Hartholzstäube", "anlass": "Pflichtvorsorge", "datum": H, "naechste": "2028-11-01", "ergebnis": "XVORSORGE keine Bedenken", "arzt": "Dr. XARZT"})
A("POST", "arbeitsschutz/exposition", {"mitarbeiter_id": m1, "stoff": "Buchenholzstaub XEXPO", "taetigkeit": "Schleifen", "von": "2026-01-01", "bis": H, "hoehe": "1,2 mg/m³"})
A("POST", "arbeitsschutz/verbandbuch", {"datum": H, "name": "Max Werk", "verletzung": "Schnitt Daumen XVERBAND", "hergang": "Stemmeisen", "ersthelfer": "Eva"})
# Kontoauszug
sys.path.insert(0, "/tmp/claude-0/t/bank"); import camt
ein = [camt.ntry(1500.0, "CRDT", T("BANKNAME"), "DE89370400440532013000", "Abschlag Einbauschrank " + T("BANKZWECK"), ref="R1", datum=H),
       camt.ntry(4646.46, "DBIT", "Holz AG", "DE44500105175407324931", "R-4711", ref="R2", datum=H),
       camt.ntry(42.5, "DBIT", "Stadtwerke", "DE12500105170648489890", "Abschlag Strom", ref="R3", datum=H)]
roh = camt.datei(ein, anfang=1000.0, ende=1000.0 + 1500.0 - 4646.46 - 42.5)
bk = A("POST", "bank/einlesen", {"daten": base64.b64encode(roh).decode(), "dateiname": "auszug.xml"}); print("Kontoauszug", bk.get("_s"), bk.get("neu"))
json.dump({"m1": m1, "m2": m2, "k1": k1.get("id"), "k2": k2.get("id"), "lf": lf.get("id"), "mat": mat.get("id"), "a1": a1.get("id"), "a2": a2.get("id"), "bel": bel, "b2": b2.get("id"), "pos": [p1, p2, p3, p4],
           "ben": ben, "wz": wz.get("id"), "z": z.get("id"), "pj": pj.get("id"), "brief": br.get("id")}, open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/t/lauf/spur_ids.json", "w"))
print("fertig")
