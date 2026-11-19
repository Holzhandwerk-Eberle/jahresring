"""Version 152, Widerrufsbelehrung: Schalter „außerhalb der Geschäftsräume geschlossen“ an Angebot und Auftragsbestätigung, Hinweis und
eigenes Blatt im Druck, Fristende, Sperre im Kalender, Rückfrage bei Terminen in der Frist. Erwartet eine frische Prüfinstanz."""
import json, sys, re, sqlite3
from datetime import date, timedelta
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
sys.path.insert(0, "/home/claude/eberle-buero")
import widerruf
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
fehler = []
def ok(name, bed, info=""):
    print(("ok   " if bed else "FEHLER ") + name + ("" if bed else "  → " + str(info)[:700]))
    if not bed: fehler.append(name)
H = date.today().isoformat(); tag = lambda n: (date.today() + timedelta(days=n)).isoformat()

print("== Fristende")
ft = {"2026-12-25": "1. Weihnachtstag", "2026-12-26": "2. Weihnachtstag", "2027-01-01": "Neujahr", "2027-01-06": "Heilige Drei Könige"}.get
ok("Vertrag am Montag 02.11.2026: Frist endet am Montag 16.11.2026", widerruf.frist_ende("2026-11-02", ft) == "2026-11-16", widerruf.frist_ende("2026-11-02", ft))
ok("Ende fiele auf Samstag 21.11.: Frist endet am Montag 23.11.", widerruf.frist_ende("2026-11-07", ft) == "2026-11-23", widerruf.frist_ende("2026-11-07", ft))
ok("Ende fiele auf Sonntag: nächster Werktag", widerruf.frist_ende("2026-11-08", ft) == "2026-11-23", widerruf.frist_ende("2026-11-08", ft))
ok("Ende fiele auf den 1. Weihnachtstag (Freitag): Frist endet am Montag 28.12.", widerruf.frist_ende("2026-12-11", ft) == "2026-12-28", widerruf.frist_ende("2026-12-11", ft))
ok("Ende fiele auf Neujahr (Freitag): Frist endet am Montag 04.01.2027", widerruf.frist_ende("2026-12-18", ft) == "2027-01-04", widerruf.frist_ende("2026-12-18", ft))
ok("ohne oder mit unsinnigem Datum: keine Frist", widerruf.frist_ende("") == "" and widerruf.frist_ende("morgen") == "" and widerruf.frist_ende(None) == "")

print("== Mustertexte")
B = widerruf.BELEHRUNG
ok("Belehrung enthält die Sätze des gesetzlichen Musters für Dienstleistungen",
   all(s in B for s in ("Sie haben das Recht, binnen vierzehn Tagen ohne Angabe von Gründen diesen Vertrag zu widerrufen.",
                         "Die Widerrufsfrist beträgt vierzehn Tage ab dem Tag des Vertragsabschlusses.",
                         "mittels einer eindeutigen Erklärung (z. B. ein mit der Post versandter Brief oder eine E-Mail) über Ihren Entschluss, diesen Vertrag zu widerrufen, informieren.",
                         "Sie können dafür das beigefügte Muster-Widerrufsformular verwenden, das jedoch nicht vorgeschrieben ist.",
                         "Zur Wahrung der Widerrufsfrist reicht es aus, dass Sie die Mitteilung über die Ausübung des Widerrufsrechts vor Ablauf der Widerrufsfrist absenden.",
                         "unverzüglich und spätestens binnen vierzehn Tagen ab dem Tag zurückzuzahlen, an dem die Mitteilung über Ihren Widerruf dieses Vertrags bei uns eingegangen ist.",
                         "in keinem Fall werden Ihnen wegen dieser Rückzahlung Entgelte berechnet.",
                         "so haben Sie uns einen angemessenen Betrag zu zahlen, der dem Anteil der bis zu dem Zeitpunkt, zu dem Sie uns von der Ausübung des Widerrufsrechts hinsichtlich dieses Vertrags unterrichten, bereits erbrachten Dienstleistungen im Vergleich zum Gesamtumfang der im Vertrag vorgesehenen Dienstleistungen entspricht.")))
ok("Angaben des Betriebs: Name, Anschrift, Telefon, E-Mail; im Formular ohne Telefon",
   widerruf.unternehmer({"firma": "Muster Schreinerei", "firma_inhaber": "Jonas Muster", "firma_anschrift": "Weg 1\n88069 Tettnang", "firma_telefon": "07542 1", "firma_email": "a@b.example"})
   == "Muster Schreinerei, Jonas Muster, Weg 1, 88069 Tettnang, Telefon 07542 1, E-Mail a@b.example"
   and "Telefon" not in widerruf.unternehmer({"firma": "M", "firma_telefon": "1", "firma_email": "a@b.example"}, mit_telefon=False))
ok("fehlende Angaben werden benannt", widerruf.fehlende_angaben({"firma": "M", "firma_anschrift": "Weg"}) == ["Telefon", "E-Mail"])

inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
def A(m, p, d=None, h=None):
    s, b, hd = rq(inh, m, "/api/" + p, d, {"X-Rueckfrage": "1", **(h or {})}); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    else: j = {"_s": s, "liste": j}
    return j
seite = lambda p: rq(inh, "GET", p)[1]
A("PUT", "einstellungen", {"firma": "Muster Schreinerei", "firma_anschrift": "Weg 1\n88069 Tettnang", "firma_inhaber": "Jonas Muster", "steuernummer": "12/345/67890"})
con = sqlite3.connect(D + "/buero.db", timeout=30); con.row_factory = sqlite3.Row
k = A("POST", "kunden", {"kurzname": "Haus, Hanna", "nachname": "Haus", "vorname": "Hanna", "anredeform": "Frau", "strasse": "Gartenweg", "hausnr": "4", "plz": "88069", "ort": "Tettnang", "gruppe": "Privatkunde"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Einbauschrank"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Einbauschrank"}); pid = po.get("id") or po["position"]["id"]
A("PUT", f"positionen/{pid}", {"einzelpreis": 4200, "preis_manuell": 1, "menge": 1})
ang = A("POST", f"auftraege/{a['id']}/belege", {"art": "angebot"})

print("== Schalter am Angebot")
b = A("GET", f"belege/{ang['id']}")
ok("neues Angebot: Schalter steht auf Nein, kein Blatt im Druck", not b.get("agv") and "Widerrufsbelehrung" not in seite(f"/druck/{ang['id']}"), b.get("agv"))
e = A("GET", "einstellungen")
ok("Einstellungen melden, dass Telefon und E-Mail des Betriebs fehlen", e["_widerruf_standard"]["fehlt"] == ["Telefon", "E-Mail"], e.get("_widerruf_standard", {}).get("fehlt"))
A("PUT", "einstellungen", {"firma_telefon": "07542 12345", "firma_email": "info@muster.example"})
x = A("PUT", f"belege/{ang['id']}", {"agv": True}); b = A("GET", f"belege/{ang['id']}")
ok("auf Ja gestellt: Tag des Vertragsschlusses ist mit dem Belegdatum vorbelegt, Fristende berechnet",
   x["_s"] == 200 and b["agv"] == 1 and b["vertrag_am"] == b["datum"] and b["widerruf_bis"] == widerruf.frist_ende(b["datum"], lambda i: __import__("personal").feiertag(i)), (x, b.get("vertrag_am"), b.get("widerruf_bis")))
html = seite(f"/druck/{ang['id']}")
ok("Angebot druckt den Hinweis auf das Widerrufsrecht", "außerhalb von Geschäftsräumen geschlossen" in html and "Muster-Widerrufsformular sind beigefügt" in html)
ok("angehängt: Widerrufsbelehrung mit den Angaben des Betriebs in Klammern",
   "<h2>Widerrufsbelehrung</h2>" in html and "müssen Sie uns (Muster Schreinerei, Jonas Muster, Weg 1, 88069 Tettnang, Telefon 07542 12345, E-Mail info@muster.example) mittels" in html, re.findall(r"müssen Sie uns \([^)]*\)", html))
ok("angehängt: Muster-Widerrufsformular mit Name, Anschrift und E-Mail des Betriebs (ohne Telefon) und allen Zeilen des Musters",
   "Muster-Widerrufsformular</h2>" in html and "An Muster Schreinerei, Jonas Muster, Weg 1, 88069 Tettnang, E-Mail info@muster.example:" in html
   and all(t in html for t in ("Hiermit widerrufe(n) ich/wir (*) den von mir/uns (*) abgeschlossenen Vertrag über den Kauf der folgenden Waren (*)/die Erbringung der folgenden Dienstleistung (*)",
                               "Bestellt am (*)/erhalten am (*)", "Name des/der Verbraucher(s)", "Anschrift des/der Verbraucher(s)",
                               "Unterschrift des/der Verbraucher(s) (nur bei Mitteilung auf Papier)", "(*) Unzutreffendes streichen.")))
ok("zweites Blatt: Empfangsbestätigung und Erklärung zum Beginn vor Fristende, mit Beleg und Kunde",
   "Erklärungen des Kunden" in html and "auf Papier erhalten" in html and "vor Ablauf der Widerrufsfrist beginnt" in html and "Hanna Haus, Gartenweg 4, 88069 Tettnang" in html and b["nummer"] in html)
ok("Reihenfolge: erst der Beleg, dann die Blätter", html.index("Sehr geehrte") < html.index("<h2>Widerrufsbelehrung</h2>") < html.index("Erklärungen des Kunden"))
x = A("PUT", f"belege/{ang['id']}", {"vertrag_am": "morgen"})
ok("unsinniges Datum wird abgelehnt", x["_s"] == 400, x)
x = A("PUT", f"belege/{ang['id']}", {"vertrag_am": "2026-11-07"}); b = A("GET", f"belege/{ang['id']}")
ok("Vertrag am Samstag 07.11.2026 → Frist bis Montag 23.11.2026", b["vertrag_am"] == "2026-11-07" and b["widerruf_bis"] == "2026-11-23", (b["vertrag_am"], b["widerruf_bis"]))
x = A("PUT", f"belege/{ang['id']}", {"vertrag_am": H})
A("PUT", "einstellungen", {"widerruf_hinweis": "Eigener Hinweis zum Widerruf.", "widerruf_belehrung": "## Eigene Überschrift\nEigener Text an {unternehmer}."})
html = seite(f"/druck/{ang['id']}")
ok("eigene Texte aus den Einstellungen werden gedruckt, {unternehmer} ersetzt, „## “ wird Überschrift",
   "Eigener Hinweis zum Widerruf." in html and "<h3>Eigene Überschrift</h3>" in html and "Eigener Text an Muster Schreinerei, Jonas Muster" in html and "binnen vierzehn Tagen" not in html)
A("PUT", "einstellungen", {"widerruf_hinweis": "", "widerruf_belehrung": ""})
ok("leer = wieder das gesetzliche Muster", "binnen vierzehn Tagen ohne Angabe von Gründen" in seite(f"/druck/{ang['id']}"))
re_ = A("POST", f"auftraege/{a['id']}/belege", {"art": "lieferschein"})
x = A("PUT", f"belege/{re_['id']}", {"agv": True})
ok("am Lieferschein gibt es den Schalter nicht", x["_s"] == 400, x)

print("== Auftragsbestätigung erbt, Unterschrift setzt den Vertragstag")
ab = A("POST", f"auftraege/{a['id']}/belege", {"art": "ab"}); b2 = A("GET", f"belege/{ab['id']}")
ok("Auftragsbestätigung übernimmt Schalter und Vertragstag vom Angebot", b2["agv"] == 1 and b2["vertrag_am"] == H and "<h2>Widerrufsbelehrung</h2>" in seite(f"/druck/{ab['id']}"), (b2.get("agv"), b2.get("vertrag_am")))
A("PUT", f"belege/{ab['id']}", {"vertrag_am": tag(-3)})
png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
u = A("POST", f"belege/{ab['id']}/unterschreiben", {"bild": png, "name": "Hanna Haus", "ort": "Tettnang"})
b2 = A("GET", f"belege/{ab['id']}")
ok("Kunde unterschreibt auf dem Tablet: Vertragstag = Tag der Unterschrift", u["_s"] == 200 and b2["vertrag_am"] == H, (u.get("fehler"), b2.get("vertrag_am")))
x = A("PUT", f"belege/{ab['id']}", {"agv": False})
ok("nach der Unterschrift lässt sich der Schalter nicht mehr umstellen", x["_s"] == 400 and A("GET", f"belege/{ab['id']}")["agv"] == 1, x)
x = A("PUT", f"belege/{ab['id']}", {"agv_beginn": True})
ok("„Beginn vor Fristende verlangt“ lässt sich auch nach der Unterschrift vermerken", x["_s"] == 200 and A("GET", f"belege/{ab['id']}")["agv_beginn"] == 1, x)
A("PUT", f"belege/{ab['id']}", {"agv_beginn": False})

print("== Kalender")
ende = widerruf.frist_ende(H, __import__("personal").feiertag)
kal = A("GET", f"kalender?von={tag(-7)}&bis={tag(30)}")
w = [x for x in kal.get("widerruf", []) if x["auftrag_id"] == a["id"]]
ok("Kalender liefert die Sperre: eine je Auftrag, vom Vertragstag bis zum Fristende", len(w) == 1 and w[0]["von"] == H and w[0]["bis"] == ende and w[0]["beginn"] is False and w[0]["beleg_id"] == ab["id"], kal.get("widerruf"))
kal2 = A("GET", f"kalender?von={tag(40)}&bis={tag(70)}")
ok("außerhalb der Frist: keine Sperre", not kal2.get("widerruf"), kal2.get("widerruf"))
t1 = A("POST", "termine", {"auftrag_id": a["id"], "typ": "Montage", "von": tag(3), "bis": tag(4)})
ok("Termin in der Widerrufsfrist: Rückfrage mit Vertragstag und Fristende", t1["_s"] == 409 and t1.get("rueckfrage") == "widerrufsfrist" and f"{ende[8:10]}.{ende[5:7]}.{ende[:4]}" in t1["fehler"], t1)
ok("nichts eingetragen", not con.execute("select 1 from termine where auftrag_id=?", (a["id"],)).fetchone())
t2 = A("POST", "termine", {"auftrag_id": a["id"], "typ": "Montage", "von": tag(3), "bis": tag(4)}, {"X-Bestaetigt": "widerrufsfrist"})
ok("bestätigt: Termin steht", t2["_s"] == 200 and t2.get("id"), t2)
nach = (date.fromisoformat(ende) + timedelta(days=3)).isoformat()
t3 = A("POST", "termine", {"auftrag_id": a["id"], "typ": "Montage", "von": nach, "bis": nach})
ok("Termin nach Fristende: ohne Rückfrage", t3["_s"] == 200, t3)
t4 = A("PUT", f"termine/{t3['id']}", {"von": tag(5), "bis": tag(5)})
ok("Termin in die Frist verschieben: Rückfrage", t4["_s"] == 409 and t4.get("rueckfrage") == "widerrufsfrist", t4)
t5 = A("POST", "termine", {"typ": "Sonstiges", "von": tag(3), "bis": tag(3), "titel": "Zahnarzt"})
ok("Termin ohne Auftrag: keine Rückfrage", t5["_s"] == 200, t5)
x = A("PUT", f"auftraege/{a['id']}", {"plan_von": tag(2), "plan_bis": tag(6)})
ok("geplanter Ausführungszeitraum in der Frist: Rückfrage", x["_s"] == 409 and x.get("rueckfrage") == "widerrufsfrist", x)
A("PUT", f"belege/{ab['id']}", {"agv_beginn": True})
t6 = A("POST", "termine", {"auftrag_id": a["id"], "typ": "Montage", "von": tag(6), "bis": tag(6)})
kal = A("GET", f"kalender?von={tag(-7)}&bis={tag(30)}"); w = [x for x in kal.get("widerruf", []) if x["auftrag_id"] == a["id"]]
ok("Kunde hat den Beginn verlangt: Termin ohne Rückfrage, Sperre nur noch als Hinweis gekennzeichnet", t6["_s"] == 200 and w and w[0]["beginn"] is True, (t6, w))
# zweiter Auftrag ohne Schalter bleibt unberührt
a2 = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Tisch"}); t7 = A("POST", "termine", {"auftrag_id": a2["id"], "typ": "Fertigung", "von": tag(2), "bis": tag(2)})
ok("Auftrag ohne Schalter: Termine wie bisher", t7["_s"] == 200 and not [x for x in kal.get("widerruf", []) if x["auftrag_id"] == a2["id"]], t7)
A("PUT", f"auftraege/{a['id']}", {"status": "Abgesagt"})
kal = A("GET", f"kalender?von={tag(-7)}&bis={tag(30)}")
endstatus = (A("GET", "einstellungen").get("status_ende") or [])
ok("abgesagter Auftrag: keine Sperre mehr", "Abgesagt" not in endstatus or not [x for x in kal.get("widerruf", []) if x["auftrag_id"] == a["id"]], (endstatus, kal.get("widerruf")))
print("FEHLER:", fehler)
