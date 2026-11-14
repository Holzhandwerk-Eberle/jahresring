import zipfile, glob, os, re, sys
def text(xml):
    xml = re.sub(r"</w:p>", "\n", xml); xml = re.sub(r"</w:tc>", " | ", xml); xml = re.sub(r"<w:tab/>", "\t", xml)
    t = re.sub(r"<[^>]+>", "", xml)
    import html; t = html.unescape(t)
    return "\n".join(l.strip() for l in t.splitlines() if l.strip(" |\t"))
A = "/mnt/user-data/attachments/ec87b02e-c197-5135-8518-1f390bf90317/"
fs = [f for f in glob.glob(A + "*.docx") if not os.path.basename(f).split("-", 1)[1].startswith(("AGB", "GBO"))]
for f in sorted(fs, key=lambda x: os.path.basename(x).split("-", 1)[1]):
    z = zipfile.ZipFile(f); print("\n\n########", os.path.basename(f).split("-", 1)[1])
    for n in sorted(z.namelist()):
        if re.match(r"word/(document\d*|header\d*|footer\d*)\.xml$", n):
            t = text(z.read(n).decode("utf-8", "ignore"))
            if t.strip(): print(f"--- {n}\n{t[:6000]}")
        if n.lower().startswith("customxml/item") and "props" not in n.lower():
            b = z.read(n).decode("utf-8-sig", "ignore")
            if "Context" in b or "Arbeitsblatt" in b:
                vals = [v.strip() for v in re.findall(r">([^<>]+)<", b) if v.strip() and not re.fullmatch(r"[.\s]+|[JKL]", v.strip())]
                print(f"--- {n} (Daten, {len(vals)} Werte)\n  " + "\n  ".join(vals[:150]))
