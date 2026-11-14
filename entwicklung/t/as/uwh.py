import pypdfium2 as pdfium, glob, re, json, os
A = "/mnt/user-data/attachments/ec87b02e-c197-5135-8518-1f390bf90317/"
aus = {}
for f in sorted(glob.glob(A + "*UWH-0*.pdf")):
    nr = re.search(r"UWH-(\d+)", f).group(1)
    if "UWH-" + nr in aus: continue
    d = pdfium.PdfDocument(f); t = d[0].get_textpage().get_text_range().replace("￾", "").replace("\r", "")
    zeilen = [z.strip() for z in t.split("\n") if z.strip()]
    # Titel: Zeilen nach "Quelle: BGHM" bis zur ersten Ziffernzeile
    titel = []
    try:
        i = next(i for i, z in enumerate(zeilen) if z.startswith("Sicheres") or z.startswith("Sicherer") or z.startswith("Sichere"))
        for z in zeilen[i:]:
            if re.fullmatch(r"[\d ]+", z): break
            titel.append(z)
    except StopIteration: pass
    titel = " ".join(titel)
    sek, aktuell, punkt, ende = [], None, None, False
    for z in zeilen:
        if z.startswith("Weitere Informa") or z.startswith("Bestell-Nr"): 
            if punkt: aktuell["punkte"].append(punkt); punkt = None
            aktuell = None; continue
        if z.startswith("•"):
            if aktuell is None:
                if not sek: continue
                aktuell = sek[-1]
            if punkt: aktuell["punkte"].append(punkt)
            punkt = z.lstrip("• ").strip(); continue
        if punkt is not None:
            if not re.search(r"[.!:]$", punkt):
                punkt = (punkt + " " + z) if not punkt.endswith("-") else punkt[:-1] + z
                continue
            aktuell["punkte"].append(punkt); punkt = None
            # nach Punkt mit Satzende: neue Überschrift?
        if re.fullmatch(r"[A-ZÄÖÜ][A-Za-zäöüßÄÖÜ /,-]{2,40}", z) and len(z.split()) <= 4 and not z.endswith("."):
            aktuell = {"titel": z, "punkte": []}; sek.append(aktuell); continue
        aktuell = None
    if punkt and aktuell: aktuell["punkte"].append(punkt)
    sek = [s for s in sek if s["punkte"]]
    aus["UWH-" + nr] = {"nr": "UWH-" + nr, "titel": titel, "abschnitte": sek, "datei": f}
for k, v in aus.items():
    print("\n##", k, v["titel"]); 
    for s in v["abschnitte"]: print("  [" + s["titel"] + "]", len(s["punkte"]), "|", " / ".join(p[:60] for p in s["punkte"])[:400])
json.dump(aus, open("uwh.json", "w"), ensure_ascii=False, indent=1)
