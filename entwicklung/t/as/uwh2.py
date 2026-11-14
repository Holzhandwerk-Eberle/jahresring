import pdfplumber, glob, re, json
A = "/mnt/user-data/attachments/ec87b02e-c197-5135-8518-1f390bf90317/"
KOPF = {"Allgemeines", "Werkzeuge", "Werkzeug", "Einstellen", "Betreiben", "Einrichten", "Einsatzbedingungen", "Wartung und Pflege", "Umgang und Pflege",
        "Schneidenwechsel", "Schutzkleidung", "Verkehrsregelung", "Fahrweise", "Besondere Einsatzbedingungen", "Vorbereitung", "Arbeiten in Silos",
        "Beseitigen von Stauungen", "Vertikalsägegatter", "Vorkappsägen", "Fördereinrichtungen", "Einsatz mit Arbeitsbühne", "Verfahren von Rundholz",
        "Einsteigen ohne diese Einrichtungen", "Persönliche Schutzausrüstung", "Gehörschutz", "Lärmbereiche"}
aus = {}
for f in sorted(glob.glob(A + "*UWH-0*.pdf")):
    nr = "UWH-" + re.search(r"UWH-(\d+)", f).group(1)
    if nr in aus: continue
    p = pdfplumber.open(f).pages[0]
    words = p.extract_words(keep_blank_chars=False, use_text_flow=False, extra_attrs=["size"])
    bul = [w for w in words if w["text"].startswith("•")]
    xs = sorted({round(w["x0"] / 8) * 8 for w in bul})
    # Spaltengrenzen aus den Bullet-x-Positionen
    spalten = []
    for x in xs:
        if not spalten or x - spalten[-1][-1] > 40: spalten.append([x])
        else: spalten[-1].append(x)
    starts = [min(s) - 12 for s in spalten]
    top = min(w["top"] for w in bul) - 40 if bul else 0
    texte = []
    for i, s in enumerate(starts):
        e = starts[i + 1] - 2 if i + 1 < len(starts) else p.width
        texte.append(p.crop((max(0, s), top, e, p.height)).extract_text() or "")
    titel = " ".join((p.crop((0, 0, p.width, 140)).extract_text() or "").split("\n")[:4])
    m = re.search(r"(Sicher\w* (?:Arbeiten|Betrieb)[^\d]*)", titel.replace("\n", " "))
    titel = re.sub(r"\s+", " ", m.group(1)).strip() if m else titel
    sek, akt, pkt = [], None, None
    def fertig():
        global pkt
        if pkt and akt is not None: akt["punkte"].append(re.sub(r"\s+", " ", pkt).strip())
        pkt = None
    for t in texte:
        for z in t.split("\n"):
            z = z.strip()
            if not z: continue
            if z.startswith(("Weitere Informa", "Bestell-Nr", "www.bghm", "Bilder:", "in „Holz")): fertig(); akt = None; continue
            if z in KOPF:
                fertig(); akt = {"titel": z, "punkte": []}; sek.append(akt); continue
            if z.startswith("•"):
                fertig()
                if akt is None:
                    akt = {"titel": "Hinweise", "punkte": []}; sek.append(akt)
                pkt = z.lstrip("• ").strip(); continue
            if pkt is not None:
                pkt = pkt[:-1] + z if pkt.endswith("-") and z[:1].islower() else pkt + " " + z
    fertig()
    sek = [s for s in sek if s["punkte"]]
    aus[nr] = {"nr": nr, "titel": titel, "abschnitte": sek, "datei": f}
for k, v in sorted(aus.items()):
    print("\n##", k, v["titel"])
    for s in v["abschnitte"]: print("  [" + s["titel"] + "]", " | ".join(s["punkte"]))
json.dump(aus, open("uwh.json", "w"), ensure_ascii=False, indent=1)
