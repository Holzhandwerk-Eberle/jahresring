import json, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from uwh_daten import UWH
AS = "/tmp/claude-0/t/as/"
gbo = json.load(open(AS + "gbo_alle.json"))
grp = json.load(open(AS + "schreiner.json"))

def slug(s):
    s = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

datei_gruppe = {}
for g, liste in grp.items():
    for d in liste:
        datei_gruppe[d.replace(" ", "")] = g
ART = {"Stationäre Holzbearbeitungsmaschinen": "maschine", "Handmaschinen": "maschine"}
gb = []
for x in gbo:
    d = x["datei"].replace(" ", "")
    g = datei_gruppe.get(d)
    gef = [{"g": y["g"], "m": [m.strip() for m in y["m"] if m.strip()]} for y in x["gef"] if y["g"].strip()]
    gb.append({"id": slug(x["name"]), "name": x["name"], "gruppe": g or "Weitere Vorlagen (andere Branchen)",
               "art": ART.get(g, "taetigkeit" if g in ("Oberfläche und Gefahrstoffe", "Montage und Baustelle") else "bereich"),
               "schreiner": bool(g), "stand": x["stand"], "gef": gef, "mit": x.get("mit") or []})
fehlt = [d for d in datei_gruppe if not any(slug(z["name"]) == slug(d.replace("-", " ")) or z["name"] for z in gb)]
gb.sort(key=lambda z: (not z["schreiner"], list(grp).index(z["gruppe"]) if z["schreiner"] else 99, z["name"]))
print("GB-Vorlagen:", len(gb), "davon Schreiner:", sum(z["schreiner"] for z in gb))

# ---------------- Unterweisungsthemen
T = []
KURZ = {"UWH-011": "Tisch- und Formatkreissäge", "UWH-012": "Tischfräsmaschine", "UWH-013": "Tischbandsäge", "UWH-014": "Abrichthobelmaschine",
        "UWH-015": "Fräswerkzeuge", "UWH-016": "Fräswerkzeuge mit Hartmetall-Wechselschneiden", "UWH-017": "Kettensäge", "UWH-018": "Handmaschinen",
        "UWH-019": "Dickenhobelmaschine", "UWH-020": "Lärm und Gehörschutz", "UWH-021": "Flurförderzeuge (Stapler, Hubwagen)", "UWH-022": "Flurförderzeuge: besondere Einsätze",
        "UWH-023": "Arbeiten auf Leitern", "UWH-024": "Arbeiten in Spänesilos", "UWH-025": "Kantenanleimmaschine", "UWH-026": "Gattersägewerk"}
for u in UWH:
    T.append({"id": u["nr"].lower(), "titel": KURZ[u["nr"]],
              "volltitel": u["titel"], "gruppe": "Maschinen und Arbeitsmittel" if u["nr"] not in ("UWH-020", "UWH-024", "UWH-026") else ("Betrieb" if u["nr"] != "UWH-026" else "Weitere"),
              "quelle": f"BGHM Unterweisungshilfe {u['nr']}", "uwh": u["nr"], "gbo": u["gbo"],
              "abschnitte": [{"titel": a, "punkte": p} for a, p in u["abschnitte"]]})
D = [
 ("allgemein", "Allgemeine Unterweisung (Betrieb, Notfall, PSA)", "Betrieb", [
   ("Allgemeine Unterweisungen", ["Erläuterung betrieblicher Abläufe", "Verhalten in Notfällen", "Verhalten im Brandfall",
                                   "Allgemeine Schutzmaßnahmen an Maschinen und betrieblichen Einrichtungen", "Persönliche Schutzausrüstungen"]),
   ("Arbeitsplatzbezogen", ["Störungen und Gefährdungen vermeiden, auch durch andere Mitarbeiter", "Sicherheitsgerechtes Arbeiten vorführen und gemeinsam üben"])]),
 ("brandschutz", "Brandschutz / Brandbekämpfung", "Betrieb", [
   ("Vor Beginn feuergefährlicher Arbeiten", ["Brennbare Stoffe entfernen", "Kollegen informieren", "Brennbare Stoffe sicher aufbewahren"]),
   ("In brandgefährdeten Bereichen", ["Rauchverbot beachten", "Zündquellen vermeiden", "Feuerschutztüren nicht blockieren"]),
   ("Bei Entstehungsbrand: Handfeuerlöscher einsetzen", ["Sicherheitssplint ziehen", "In Windrichtung löschen", "Von vorne nach hinten löschen",
                                                       "Wenn möglich, mehrere Feuerlöscher gleichzeitig einsetzen", "Elektrobrand mit CO2 löschen", "Feuerlöscher freihalten"]),
   ("Bei größeren Bränden", ["Feuerwehr alarmieren", "Fluchtwege freihalten", "Gefährdete Mitarbeiter informieren", "Aufzüge in keinem Fall benutzen",
                             "Nach Verlassen der Gebäude Sammelpunkt aufsuchen", "Feuerwehr einweisen"])]),
 ("erste-hilfe", "Erste Hilfe", "Betrieb", [
   ("Kleine Verletzungen", ["Selbst versorgen (z. B. Pflaster)", "Ins Verbandbuch eintragen", "Vorgesetzten informieren"]),
   ("Beispiele", ["Leichte Verbrennungen mit Wasser kühlen", "Brennende Kleidung durch Abdecken löschen", "Fremdkörper im Auge mit fließendem Wasser oder Augendusche ausspülen",
                  "Mit ätzenden Stoffen benetzte Kleidung ausziehen und benetzte Körperstellen mit Wasser abspülen", "Verstauchungen kühlen", "Gegebenenfalls anschließend Durchgangsarzt aufsuchen"]),
   ("Schwere Verletzungen", ["Erstversorgung durchführen", "Ersthelfer herbeiholen", "Rettungsdienst informieren: Wo? Was? Wie viele Verletzte? Welche Verletzungen? Warten auf Rückfragen",
                             "Vorgesetzten informieren", "Rettungsfahrzeuge einweisen", "Rettungsarbeiten nicht behindern", "Ins Verbandbuch eintragen"])]),
 ("gefahrstoffe", "Tätigkeiten mit Gefahrstoffen (§ 14 GefStoffV)", "Gefahrstoffe und Oberfläche", [
   ("Inhalte", ["Betriebsanweisungen der verwendeten Gefahrstoffe besprechen", "Gefahren für Mensch und Umwelt (Kennzeichnung, Piktogramme, H- und P-Sätze)",
                "Schutzmaßnahmen und Verhaltensregeln, persönliche Schutzausrüstung, Hautschutz", "Verhalten im Gefahrfall und Erste Hilfe", "Sachgerechte Entsorgung",
                "Allgemeine arbeitsmedizinisch-toxikologische Beratung", "Wo das Gefahrstoffverzeichnis und die Sicherheitsdatenblätter zu finden sind"])]),
 ("lackieren", "Lackieren und vorbereitende Arbeiten", "Gefahrstoffe und Oberfläche", [
   ("Brandgefahr", ["Rauchverbot beachten", "Zündquellen vermeiden", "Zur Verringerung der Brandlast Abdeckpapiere mindestens einmal am Tag aus dem Arbeitsbereich entfernen"]),
   ("Gefahrstoffe", ["Bei Freisetzung gefahrstoffhaltiger Dämpfe technische Lüftung in Betrieb nehmen; reicht diese nicht aus, Atemschutz verwenden",
                     "Schleifstäube an der Schleifmaschine absaugen; falls nicht ausreichend, Feinstaubmaske verwenden",
                     "Behälter zum Umfüllen von Gefahrstoffen wie Lösemittel oder Verdünnung kennzeichnen (Name, Gefahrenkennzeichnung)"]),
   ("Mischraum", ["Lüftungs- bzw. Absaugeinrichtungen nicht verstellen", "Feuerschutztüren nicht festsetzen"]),
   ("Lackieren", ["Lackieren nur in den dafür zugelassenen Räumen oder Bereichen mit wirksamer Absaugung", "Vor dem Lackieren Türen von Lackierkabinen schließen",
                  "Gegebenenfalls Atemschutz verwenden", "Filtermatten regelmäßig reinigen"])]),
 ("schleifen", "Schleifen", "Gefahrstoffe und Oberfläche", [
   ("Schleifen", ["Augenschutz benutzen", "Brennbare Stoffe aus dem Arbeitsbereich entfernen", "Gefährdungen von Kollegen durch Funkenflug vermeiden", "Gehörschutz verwenden",
                  "Schleifmaschinen sicher halten, ggf. zweiten Griff benutzen", "Schruppen und Trennen nur mit Schutzhaube", "Werkstücke sicher befestigen",
                  "Nach Beendigung der Arbeiten Maschine möglichst in geeigneter Halterung ablegen", "Nur elektrisch geprüfte Maschinen einsetzen",
                  "Keine Maschinen mit offensichtlichen Mängeln benutzen", "Geeignete Scheiben verwenden", "Schleifstäube absaugen, ggf. Atemschutz benutzen",
                  "Leichtmetallstäube immer absaugen (Explosionsgefahr)",
                  "Bei Ständerschleifmaschinen Werkstückauflage und Schutzhaube entsprechend dem Scheibenverschleiß nachstellen",
                  "Bei Bandschleifern darf die Schleifbandkante nicht überstehen (Schnittgefahr)"])]),
 ("instandhaltung", "Instandhaltung", "Maschinen und Arbeitsmittel", [
   ("Instandhaltungsarbeiten", ["Gegenseitige Gefährdungen vermeiden", "Mit Instandhaltungsarbeiten erst nach Übergabe der Maschine beginnen",
                                "Vor Kontakt mit hautgefährdenden Stoffen geeigneten Hautschutz verwenden", "Vor Beginn der Arbeiten notwendige Informationen einholen",
                                "Höher gelegene Arbeiten nur von geeigneten Aufstiegen aus durchführen (z. B. Leitern, Tritte)",
                                "Arbeiten an spannungsführenden Teilen nur von einer Elektrofachkraft durchführen lassen",
                                "Für Spannungsfreiheit der Maschine sorgen, z. B. Netzstecker ziehen bzw. Hauptschalter in AUS-Position mit Sicherung gegen Wiedereinschalten",
                                "Auf gespeicherte Energien achten, z. B. Druckbehälter, Hydraulikanlagen, herabfallende Teile",
                                "Vor Freigabe Probelauf durchführen, danach Maschine freigeben"])]),
 ("leitern", "Leitern und Kleingerüste", "Montage und Baustelle", [
   ("Absturz von der Leiter droht", ["Bei losem und rutschigem Untergrund", "Bei einseitigem Anlegen", "Wenn der Anstellwinkel zu flach oder zu steil ist (richtig: 65°–75°)",
                                     "Durch defekte Leitern – bei schadhaften Leitern Vorgesetzte informieren", "Bei zu schmalem Leiterfuß",
                                     "Durch fehlende Haltemöglichkeiten beim Transport sperriger Lasten", "Beim Übersteigen von der Leiter aus – Leiterüberstand mindestens 1 m, wenn andere Haltemöglichkeiten fehlen",
                                     "Bei rutschigen Leitersprossen", "Bei abgetragenen (profillosen) Schuhsohlen"]),
   ("Auswahl geeigneter Leitern und Tritte", ["Bei länger andauernden Arbeiten möglichst Stehleitern mit großformatigen Aufstandsflächen benutzen",
                                              "Zum Aufstieg ungeeignet sind Stühle (insbesondere Rollenstühle), umgedrehte Eimer und Getränkekisten"]),
   ("Kleingerüste", ["Vollständig nach Gebrauchsanleitung des Herstellers aufbauen", "Handlauf, Knieleiste und Bordbrett an allen Absturzkanten anbringen",
                     "Gegen Wegrollen durch Arretieren der Räder sichern", "Nur verfahren, wenn sich keine Personen darauf befinden", "Gegen Einsinken auf losem Untergrund sichern",
                     "Auf Verkehrswegen gegen An- und Umfahren durch Fahrzeuge sichern"])]),
 ("montage-baustelle", "Montagearbeiten auf Baustellen", "Montage und Baustelle", [
   ("Fahrt zur Baustelle", ["Transportgut wie Gasflaschen, Werkzeuge oder Bauteile im Fahrzeug sicher befestigen", "Dachlasten wie Leitern sicher befestigen",
                            "Warnweste im Fahrerbereich mitführen", "Bei Unfall oder Panne vor dem Verlassen des Fahrzeugs Warnweste überziehen"]),
   ("Montageanweisung", ["Sicherheitshinweise in Montageanweisungen beachten"]),
   ("Persönliche Schutzausrüstung", ["Auf Baustellen grundsätzlich Schutzhelm und Schutzschuhe mit durchtrittsicherer Sohle benutzen"]),
   ("Elektrische Gefährdung", ["Elektrische Maschinen nur am Baustromverteiler anschließen", "Nur Geräte und Leitungen verwenden, die für den Betrieb auf Baustellen geeignet sind"]),
   ("Baustellenkoordinator", ["Weisungen des Baustellenkoordinators zur Vermeidung gegenseitiger Gefährdungen in jedem Fall beachten",
                              "Keine Arbeiten durchführen, die andere gefährden können"])]),
 ("absturz", "Absturzsicherung", "Montage und Baustelle", [
   ("Begehen von Dächern", ["Festgelegte Aufstiege benutzen", "Ausreichende Tragfähigkeit der Dachfläche und von Einbauteilen (z. B. Lichtkuppeln, Lichtbänder) prüfen",
                            "Mindestens 2 m Abstand zu absturzgefährdeten Stellen einhalten, feste Absperrung (Kette, Seil) erforderlich", "Gekennzeichnete Verkehrswege benutzen"]),
   ("Gerüste", ["Nur gekennzeichnete und freigegebene Gerüste betreten", "Lose aufgelegte oder kippelnde Gerüstbeläge nicht betreten",
                "Gerüstebenen nur betreten, wenn der Seitenschutz (Handlauf, Knieleiste, Bordbrett) vollständig ist", "Durchstiegsklappen nach dem Durchstieg schließen"]),
   ("Laufstege und Gitterroste", ["Nur befestigte Gitterroste betreten", "Lose verlegte Gitterroste den Vorgesetzten melden", "Bei Rutschgefahr (z. B. Vereisung) Laufstege nicht betreten"]),
   ("PSA gegen Absturz", ["Benutzung nur nach Unterweisung mit praktischen Übungen", "Vorgegebene Anschlageinrichtungen benutzen", "Keine Veränderungen an der PSA gegen Absturz vornehmen",
                          "PSA gegen Absturz nur zur Sicherung von Personen benutzen", "Vor Benutzung über das Rettungskonzept informieren"])]),
 ("hubarbeitsbuehne", "Einsatz von Hubarbeitsbühnen", "Montage und Baustelle", [
   ("Betrieb allgemein", ["Betriebsanleitung und Nachweise der regelmäßigen Prüfungen", "Kennzeichnung und Hinweise an der Maschine", "Einsatzgrenzen (z. B. Wind, Neigung, Reichweite, zulässige Last)",
                          "Sicherheitseinrichtungen, Reichweiten", "Arbeitstägliche Sicht- und Funktionsprüfung", "Lastverteilung und Kräfte an der Maschine, Gesamtgewicht",
                          "Bestimmungsgemäße Benutzung (z. B. kein Übersteigen, kein Kranbetrieb), Peitscheneffekt"]),
   ("Übernahme und Transport", ["Führerscheinklasse bezüglich der Gewichtsklassen im Straßenverkehr", "Eignung von Zugfahrzeug bzw. Transportmittel, Ladungssicherung",
                                "Höchstgeschwindigkeiten, Durchfahrtshöhen und -breiten"]),
   ("Aufstellung am Arbeitsort", ["Belastbarkeit von Böden und Bodenabdeckungen", "Belastbarkeit von Decken, Fußböden und Bauteilen in Gebäuden", "Aufstellung, Abstützfolge der Stützen im Gefälle",
                                  "Lastverteilung, notwendige Fläche der Unterbauung", "Gefahr durch Lastübernahme", "Gefahren anderer Gewerke, Krananlagen",
                                  "Verdeckte Gefahren, z. B. Kanäle, mangelhafte Abdeckungen"]),
   ("Sondereinsatz", ["Arbeiten im öffentlichen Verkehrsraum", "Arbeiten unter Spannung, Abstände zu Freileitungen"])]),
 ("bildschirm", "Bildschirmarbeitsplätze", "Büro", [
   ("Bildschirmarbeitsplätze", ["Arbeitsplatz so einrichten, dass die Sehentfernung zum Bildschirm ca. 70 cm beträgt", "Zur Vermeidung ständiger Kopfbewegungen Konzepthalter verwenden",
                                "Bürostuhl so einstellen, dass man aufrecht sitzt, Arme und Beine einen Winkel von ca. 90 Grad bilden und die Füße auf dem Boden stehen (ggf. Fußstütze)",
                                "Schreibtischfläche möglichst frei halten", "Bildschirm so aufstellen, dass das Licht hauptsächlich von der Seite einfällt",
                                "Bei starkem Lichteinfall Jalousien so einstellen, dass Blendung vermieden wird"])]),
]
for i, tit, g, ab in D:
    T.append({"id": i, "titel": tit, "volltitel": tit, "gruppe": g, "quelle": "BGHM Unterweisungsnachweis", "uwh": "", "gbo": [],
              "abschnitte": [{"titel": a, "punkte": p} for a, p in ab]})
ordnung = ["Betrieb", "Maschinen und Arbeitsmittel", "Gefahrstoffe und Oberfläche", "Montage und Baustelle", "Büro", "Weitere"]
T.sort(key=lambda t: (ordnung.index(t["gruppe"]), t["titel"]))
print("Unterweisungsthemen:", len(T))

# ---------------- Psychische Belastung (FI 0052 / FI 0053)
P = [
 ("Arbeitsinhalt und Arbeitsaufgabe", [
  ("Vollständigkeit der Arbeitsaufgabe", [("Die Tätigkeit ist unvollständig oder kleinteilig, also nur vorbereitend, nur ausführend oder nur kontrollierend (z. B. ausschließlich Maschinen bedienen oder nur Sichtprüfung zur Qualitätskontrolle).", 0)],
   "Arbeitsaufgaben neu verteilen: Planen, Bearbeiten und Kontrollieren eines Auftrags durch eine Person ermöglichen oder verschiedenartige Aufgaben übertragen; Maschinenbedienung im Wechsel mit Programmierung oder Verwaltung; in festgelegten Grenzen Arbeitsmittel, Verfahren, Abläufe und Pensum selbst bestimmen lassen; Tätigkeitswechsel und Rotation über Bereiche fördern."),
  ("Variabilität (Abwechslungsreichtum)", [("Die Anforderungen der Tätigkeit sind in der Regel gleich bzw. abwechslungsarm (wenige, ähnliche Arbeitsgegenstände und Arbeitsmittel).", 0),
   ("Die Arbeitsschritte wiederholen sich häufig in kurzen Abständen (gleichartige Handlungen in kurzen Takten unter 31 Sekunden).", 0),
   ("Mehrere Tätigkeiten gleicher Priorität müssen zur gleichen Zeit mit derselben Aufmerksamkeit durchgeführt werden (Multitasking).", 0)],
   "Rotation einfordern und fördern; durch systematische Weiterbildung befähigen, möglichst viele Tätigkeiten mit verschiedenen Anforderungen auszuführen."),
  ("Handlungsspielraum", [("Beschäftigte haben keinen Einfluss auf den Inhalt der zu verrichtenden Arbeit.", 0),
   ("Beschäftigte haben keinen Einfluss auf Arbeitsumfang, -menge und -ziele pro Arbeitstag.", 0),
   ("Beschäftigte haben keinen Einfluss auf die Auswahl der Methoden, Verfahren und Arbeitsmittel.", 0),
   ("Beschäftigte haben keinen Einfluss auf die Reihenfolge der Arbeitsschritte.", 0),
   ("Die Arbeitstätigkeiten sind eng an einen hohen Takt gebunden (z. B. Fließbandarbeit ohne ausreichenden Puffer).", 0)],
   "Autonome Arbeitsorganisation: Beschäftigte bestimmen in festgelegten Grenzen Arbeitsmittel, Arbeitsverfahren, Arbeitsabläufe und Arbeitspensum."),
  ("Information/Informationsangebot", [("Für die Tätigkeit stehen regelmäßig zu viele Informationen zur Verfügung (ungeklärte Priorität, Reizüberflutung).", 0),
   ("Die benötigten Informationen sind ungünstig dargeboten (z. B. sprachlich oder optisch).", 0),
   ("Die benötigten Informationen sind unvollständig (lückenhaft, nicht aktuell, unklare Ziele, unklare Quelle).", 0)],
   "Informationen auf Nützlichkeit prüfen und nach Bedarf ordnen (am Arbeitsplatz notwendig, für das Umfeld interessant, privat); Aktualitätsregeln festlegen, z. B. Aushänge monatlich ausmisten, gezielte statt gestreute Information, Regelungen für E-Mails bei Abwesenheit."),
  ("Qualifikation", [("Die Qualifikation entspricht regelmäßig nicht den Anforderungen oder Veränderungen der Arbeitsaufgaben; es folgt keine Kompetenzanpassung (Über- oder Unterforderung).", 0),
   ("Beschäftigte erhalten bei neuen Aufgaben keine ausreichende Einweisung bzw. Gelegenheit zur Einarbeitung.", 0)],
   "Systematische und gezielte Fort- und Weiterbildung: Qualifikationsmatrix, feste Einarbeitungspläne, jährliche Besprechung des Weiterbildungs- und Einweisungsbedarfs."),
  ("Emotionale Inanspruchnahme", [("Bei der Tätigkeit ist es wahrscheinlich, dass emotional traumatisierende Ereignisse miterlebt werden (schwere Unfälle, Krankheit, Tod).", 0),
   ("Die Tätigkeit erfordert, regelmäßig auf Bedürfnisse und Gefühle anderer Menschen einzugehen.", 0),
   ("Die Tätigkeit erfordert ständig bestimmte Verhaltensweisen unabhängig von den eigenen Empfindungen (z. B. immer gleichbleibend freundlich).", 0),
   ("Die Tätigkeit erfordert den Umgang mit Übergriffen, Bedrohungen, Aggressionen oder Gewalt durch andere Personen.", 1)],
   "Gezielte Weiterbildung zum Umgang mit Bedrohungssituationen; betriebliche Notfallplanung um psychologische Angebote erweitern (z. B. Psychologische Notfallversorgung der Berufsgenossenschaft).")]),
 ("Arbeitsorganisation", [
  ("Arbeitsintensität", [("Es besteht regelmäßig ein Ungleichgewicht von Arbeitsmenge, Aufgabenvielfalt, Komplexität und verfügbarer Zeit; Zeitdruck und/oder Überstunden sind die Folge.", 1)],
   "Störungs- und unterbrechungsfreie Zeiten einräumen; Zeitansätze mit den Beschäftigten besprechen und anpassen, auch Kleinaufträge nebenbei berücksichtigen; feste Ansprechpersonen und verlässliche Abläufe bei Störungen und Fehlern."),
  ("Störungen/Unterbrechungen", [("Die Ausführung der Arbeitsaufgaben wird häufig oder lang andauernd gestört bzw. muss ungeplant unterbrochen werden.", 0),
   ("Die Arbeitsabläufe sind regelmäßig nicht nachvollziehbar.", 0)], "Störungsursachen erfassen und abstellen; ungestörte Zeiten planen; Abläufe festlegen und erklären."),
  ("Kommunikation/Kooperation", [("Es bestehen nur unzureichende Möglichkeiten zum fachlichen Austausch, zur Zusammenarbeit, Abstimmung und gegenseitigen Unterstützung.", 1)],
   "Isolierte Einzelarbeit vermeiden, z. B. Montagekräfte melden sich zweimal am Tag zurück; Sicht- oder Telefonkontakt einmal täglich mit allen Beschäftigten."),
  ("Zuständigkeit/Kompetenzen", [("Die Grenzen der Verantwortung und der Zuständigkeiten sind nicht eindeutig (Schnittstellen, Befugnisse, Rollen).", 1),
   ("Es bestehen regelmäßig widersprüchliche Arbeitsanforderungen.", 1), ("Notwendige Berechtigungen und Befugnisse fehlen oder sind zu eng begrenzt.", 1)],
   "Zuständigkeiten, Vertretungen und Befugnisse schriftlich festlegen und bekannt machen; Prioritäten bei widersprüchlichen Anforderungen durch die Führung klären.")]),
 ("Arbeitszeit", [
  ("Dauer", [("Die Arbeitszeit übersteigt regelmäßig 10 Stunden pro Tag oder 48 Stunden pro 6-Tage-Woche oder 8 Stunden pro Tag bei Arbeit mit Gefahrstoffen mit Grenzwerten, Lärm, hohen Konzentrationsanforderungen, hoher Taktbindung, starker körperlicher Anstrengung oder hoher sozialer Interaktionsdichte.", 1)],
   "Arbeitszeitgesetz einhalten und das Unplanbare planen: Zeitpuffer bei Auftragsannahme und Tagesplanung, verlässliche Notfall- und Vertretungspläne, Pausen sicherstellen, vereinbarte Arbeitszeiten einhalten, Überstunden durch Freizeit ausgleichen."),
  ("Lage/Schichtarbeit", [("Arbeiten an Sonn- und Feiertagen, Nachtarbeit oder ungünstige Schicht- bzw. Dienstpläne (z. B. geteilte Schichten).", 1)], "Schichtsysteme gesundheitsgerecht gestalten; Sonn- und Feiertagsarbeit auf das Notwendige begrenzen."),
  ("Planbarkeit/Vorhersehbarkeit", [("Die Arbeitszeit ist nicht verlässlich planbar; es bestehen nur unzureichende Einflussmöglichkeiten auf Dauer, Lage und Flexibilität.", 0)],
   "Einsatzplanung frühzeitig bekannt geben; Einflussmöglichkeiten der Beschäftigten auf Arbeitszeiten schaffen."),
  ("Erholungszeiten/Pausen", [("Geplante Ruhe- und Pausenzeiten können regelmäßig nicht oder nur verkürzt eingehalten werden oder eine erweiterte berufsbezogene Erreichbarkeit (z. B. Rufbereitschaft) ist erforderlich.", 0)],
   "Pausen und Ruhezeiten verbindlich einplanen und einhalten; Erreichbarkeit außerhalb der Arbeitszeit klar regeln.")]),
 ("Soziale Beziehungen", [
  ("Kollegen/Kolleginnen", [("Es bestehen nur unzureichende Möglichkeiten des sozialen Austauschs (z. B. Alleinarbeit) oder ein Übermaß an sozialer Ablenkung.", 0),
   ("Häufige Streitigkeiten oder Aggressionen der Beschäftigten untereinander behindern die Arbeit und/oder schwächen das Betriebsklima; gegenseitige Unterstützung ist nicht spürbar.", 1),
   ("Destruktives Verhalten der Beschäftigten untereinander (Herabwürdigung, Bloßstellen, Ausgrenzung, Beschimpfungen, Diskriminierung, Belästigung) tritt regelmäßig auf bzw. wird toleriert.", 1)],
   "Gemeinschaft fördern: Mobbing und Gewalt haben unmittelbare Konsequenzen; gemeinsame Unternehmungen unterstützen; Raum für Gespräche während der Arbeitszeit; Kontaktpersonen für Konflikte benennen."),
  ("Führungskräfte/Vorgesetzte", [("Feedback und Anerkennung für erbrachte Leistungen sind nicht ausreichend bzw. nicht gerecht.", 1),
   ("Möglichkeiten der Unterstützung und des sozialen Austauschs zwischen Führungskräften und Beschäftigten sind unzureichend.", 1),
   ("Häufige Streitigkeiten oder aggressive Auseinandersetzungen mit Führungskräften behindern die Arbeit und/oder schwächen das Betriebsklima.", 1),
   ("Destruktives Führungsverhalten (Herabwürdigung, Bloßstellen, Ausgrenzung, Beschimpfungen, Diskriminierung, Belästigung) wird regelmäßig zugelassen bzw. toleriert.", 1)],
   "Führungszeit ist Arbeitszeit: Zeit für Führung einplanen; mindestens einmal im Jahr Feedbackgespräche nach bekannten Kriterien; Führungskräfte zu gesundheitsgerechtem Führen qualifizieren.")]),
 ("Arbeitsmittel", [
  ("Arbeitsmittel", [("Wichtige Signale, Informationen und Hinweise sind schlecht wahrnehmbar (z. B. Warnsignale an Maschinen fehlen, sind verdeckt oder gehen unter).", 0),
   ("Regelmäßig fehlen die erforderlichen Werkzeuge bzw. Arbeitsmittel oder sie sind ungeeignet gestaltet bzw. ausgestattet.", 0),
   ("Die benötigten Arbeitsmittel (Maschinen, Werkzeuge, Hard- und Software) sind schlecht einzurichten oder zu bedienen.", 0),
   ("Die Mensch-Maschine-Interaktion (z. B. CNC-Maschinen) ist so gestaltet, dass Fehlbedienungen mit gravierenden Folgen möglich sind.", 0),
   ("Bedienelemente, Signale und Hinweise der Arbeitsmittel und Schutzeinrichtungen sind nicht zu verstehen.", 0)],
   "Technische, ergonomische und organisatorische Probleme vorrangig abstellen: Werkzeuge, die die Arbeit erleichtern; Software-Ergonomie beachten; arbeitsmedizinische Vorsorge bei körperlich beanspruchenden Tätigkeiten ermöglichen."),
  ("Persönliche Schutzausrüstung (PSA)", [("Durch die zu verwendende PSA entstehen zusätzliche Beeinträchtigungen.", 0)], "PSA gemeinsam mit den Beschäftigten auswählen und anprobieren lassen; Tragezeiten begrenzen; technische Lösungen bevorzugen.")]),
 ("Arbeitsumgebung", [
  ("Physikalische, chemische und biologische Faktoren", [("Geräuschpegel (über 55 bzw. 70 dB(A)), störende Hintergrundgeräusche und/oder Vibrationen beeinträchtigen Wahrnehmung und Konzentration.", 0),
   ("Ungeeignete Beleuchtung (z. B. kein Tageslicht, unter 500 Lux).", 0), ("Gerüche beeinträchtigen Konzentration und Aufmerksamkeit.", 0),
   ("Mit gefährlichen Stoffen (Dämpfe, Gase, Chemikalien, Erreger) muss umgegangen werden.", 0),
   ("Die Umgebungsbedingungen sind ungünstig und/oder können nur unzureichend selbst beeinflusst werden (Lärm, Raumklima, Beleuchtung, Luftqualität).", 0)],
   "Gesundheitsschädigende und konzentrationsstörende Bedingungen (Dauergeräusche, Vibrationen, Gerüche) möglichst vollständig beseitigen."),
  ("Ergonomische Faktoren", [("Beschäftigte verrichten schwere körperliche Arbeit.", 0),
   ("Räumliche Bedingungen (z. B. Enge) führen zu unnatürlichen Bewegungen, Zwangshaltungen und Verdrehungen.", 0)],
   "Hebehilfen und Transportmittel bereitstellen; Arbeitsplätze ergonomisch gestalten; Eignung für körperlich beanspruchende Tätigkeiten betriebsärztlich begleiten.")]),
]
psych = [{"bereich": b, "merkmale": [{"merkmal": m, "punkte": [{"text": t, "auto": bool(a)} for t, a in pkt], "massnahmen": mass} for m, pkt, mass in ml]} for b, ml in P]
print("Psych-Punkte:", sum(len(m["punkte"]) for b in psych for m in b["merkmale"]))

H = {"H220": "Extrem entzündbares Gas.", "H222": "Extrem entzündbares Aerosol.", "H223": "Entzündbares Aerosol.", "H224": "Flüssigkeit und Dampf extrem entzündbar.",
     "H225": "Flüssigkeit und Dampf leicht entzündbar.", "H226": "Flüssigkeit und Dampf entzündbar.", "H229": "Behälter steht unter Druck: Kann bei Erwärmung bersten.",
     "H280": "Enthält Gas unter Druck; kann bei Erwärmung explodieren.", "H290": "Kann gegenüber Metallen korrosiv sein.",
     "H302": "Gesundheitsschädlich bei Verschlucken.", "H304": "Kann bei Verschlucken und Eindringen in die Atemwege tödlich sein.",
     "H312": "Gesundheitsschädlich bei Hautkontakt.", "H314": "Verursacht schwere Verätzungen der Haut und schwere Augenschäden.", "H315": "Verursacht Hautreizungen.",
     "H317": "Kann allergische Hautreaktionen verursachen.", "H318": "Verursacht schwere Augenschäden.", "H319": "Verursacht schwere Augenreizung.",
     "H332": "Gesundheitsschädlich bei Einatmen.", "H334": "Kann bei Einatmen Allergie, asthmaartige Symptome oder Atembeschwerden verursachen.",
     "H335": "Kann die Atemwege reizen.", "H336": "Kann Schläfrigkeit und Benommenheit verursachen.", "H350": "Kann Krebs erzeugen.", "H351": "Kann vermutlich Krebs erzeugen.",
     "H360": "Kann die Fruchtbarkeit beeinträchtigen oder das Kind im Mutterleib schädigen.", "H361": "Kann vermutlich die Fruchtbarkeit beeinträchtigen oder das Kind im Mutterleib schädigen.",
     "H373": "Kann die Organe schädigen bei längerer oder wiederholter Exposition.", "H400": "Sehr giftig für Wasserorganismen.",
     "H410": "Sehr giftig für Wasserorganismen mit langfristiger Wirkung.", "H411": "Giftig für Wasserorganismen, mit langfristiger Wirkung.",
     "H412": "Schädlich für Wasserorganismen, mit langfristiger Wirkung.", "H413": "Kann für Wasserorganismen schädlich sein, mit langfristiger Wirkung.",
     "EUH066": "Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.", "EUH204": "Enthält Isocyanate. Kann allergische Reaktionen hervorrufen.",
     "EUH208": "Enthält einen sensibilisierenden Stoff. Kann allergische Reaktionen hervorrufen.", "EUH210": "Sicherheitsdatenblatt auf Anfrage erhältlich.",
     "EUH211": "Achtung! Beim Sprühen können gefährliche lungengängige Tröpfchen entstehen. Aerosol oder Nebel nicht einatmen.",
     "EUH212": "Achtung! Bei der Verwendung kann gefährlicher lungengängiger Staub entstehen. Staub nicht einatmen."}

aus = {"stand": "BGHM-Vorlagen, Stand der Unterlagen 11/2025 (GBO), 06/2026 (FI 0052), 12/2022 (FI 0053)",
       "gb": gb, "gb_gruppen": list(grp) + ["Weitere Vorlagen (andere Branchen)"], "themen": T, "psych": psych, "h_saetze": H,
       "anlaesse": ["Erstunterweisung vor Aufnahme der Tätigkeit", "Wiederholungsunterweisung (mindestens jährlich)", "Änderung der Tätigkeit oder Funktion",
                    "Änderung an Maschinen, Verfahren oder Arbeitsstoffen", "Besonderer Anlass (Unfall, Beinaheunfall, Störung)", "Fehlverhalten (z. B. Schutzeinrichtung umgangen, PSA nicht benutzt)",
                    "Unterweisung Jugendlicher (§ 29 JArbSchG, mindestens halbjährlich)", "Sonstiger Anlass"],
       "notfall": [["unfall", "Unfall melden an"], ["ersthelfer1", "Ersthelfer"], ["ersthelfer2", "Ersthelfer"], ["sanitaet", "Erste-Hilfe-Material / Sanitätsraum (Ort)"],
                   ["rettung", "Rettungsdienst / Feuerwehr"], ["arzt", "Arzt"], ["darzt", "Durchgangsarzt"], ["krankenhaus", "Krankenhaus"], ["gift", "Giftnotruf"],
                   ["sibe", "Sicherheitsbeauftragter"], ["fasi", "Fachkraft für Arbeitssicherheit"], ["betriebsarzt", "Betriebsarzt"], ["praevention", "Präventionsdienst der Berufsgenossenschaft"]]}
open("/home/claude/eberle-buero/arbeitsschutz_vorlagen.json", "w").write(json.dumps(aus, ensure_ascii=False, separators=(",", ":")))
print(os.path.getsize("/home/claude/eberle-buero/arbeitsschutz_vorlagen.json") // 1024, "KB")
