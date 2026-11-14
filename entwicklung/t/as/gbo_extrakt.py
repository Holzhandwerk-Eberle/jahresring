import zipfile, glob, re, json, os, sys
from xml.etree import ElementTree as ET
aus = []; fehl = []
for f in sorted(glob.glob("/tmp/claude-0/t/as/roh/gbo/*.docx")):
    z = zipfile.ZipFile(f); teil = None
    for n in z.namelist():
        if n.lower().startswith("customxml/item") and not n.lower().startswith("customxml/itemprops"):
            b = z.read(n)
            if b"ArbeitsblattContext" in b: teil = b; break
    if not teil: fehl.append(os.path.basename(f)); continue
    root = ET.fromstring(teil.decode("utf-8-sig").encode())
    loc = lambda e: e.tag.split("}")[-1]
    name = datum = mag = ""
    gef = []
    for e in root:
        if loc(e) == "Arbeitsblatt_Name": name = (e.text or "").strip()
        elif loc(e) == "Arbeitsblatt_Datum": datum = (e.text or "").strip()
        elif loc(e) == "Arbeitsblatt_MAG": mag = (e.text or "").strip()
        elif loc(e) == "Arbeitsblatt_Tabelle":
            for ctx in e:
                g = ""; m = []
                for c in ctx:
                    if loc(c) == "Arbeitsblatt_Tabelle_Gefaehrdung": g = (c.text or "").strip()
                    elif loc(c) == "Arbeitsblatt_Tabelle_Schutzziele":
                        for t in c:
                            for x in t:
                                v = (x.text or "").strip()
                                if v and not re.fullmatch(r"[.\s…]+", v): m.append(v)
                if g and not re.fullmatch(r"[.\s…]+", g): gef.append({"g": g, "m": m})
    # Mitgeltende Unterlagen aus dem Dokument
    doc = next((z.read(n).decode("utf-8", "ignore") for n in z.namelist() if re.match(r"word/document\d*\.xml$", n)), "")
    txt = re.sub(r"<[^>]+>", " ", doc)
    mit = [x for x in ("Betriebsanweisung", "Bedienungsanleitung", "Betriebsanleitung", "Sicherheitsdatenblatt", "Gefahrstoffverzeichnis", "Prüfbuch", "Unterweisungsnachweis") if x in txt]
    aus.append({"datei": os.path.basename(f)[4:-5], "name": name, "stand": datum, "gef": gef, "mit": mit})
print(len(aus), "ausgelesen,", len(fehl), "ohne Daten:", fehl[:10])
print(sum(len(a["gef"]) for a in aus), "Gefährdungen,", sum(len(g["m"]) for a in aus for g in a["gef"]), "Maßnahmen")
json.dump(aus, open("/tmp/claude-0/t/as/gbo_alle.json", "w"), ensure_ascii=False, indent=1)
for a in aus[:3]: print(a["name"], a["stand"], [g["g"] for g in a["gef"]], a["mit"])
