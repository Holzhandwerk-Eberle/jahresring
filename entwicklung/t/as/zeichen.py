import os, re, json, glob
from PIL import Image
Q = "/tmp/claude-0/t/as/pikto"; Z = "/home/claude/eberle-buero/static/arbeitsschutz/zeichen"
GRUPPE = {"Gefahrstoffe": "GHS-Gefahrenpiktogramme", "Leitern": "Leiter-Piktogramme", "Warnzeichen": "Warnzeichen", "Rettungszeichen": "Rettungszeichen",
          "Gebotszeichen": "Gebotszeichen", "Verbotszeichen": "Verbotszeichen", "Brandschutz": "Brandschutzzeichen"}
GHS = {"01": "Explodierende Bombe", "02": "Flamme", "03": "Flamme über einem Kreis", "04": "Gasflasche", "05": "Ätzwirkung",
       "06": "Totenkopf mit gekreuzten Knochen", "07": "Ausrufezeichen", "08": "Gesundheitsgefahr", "09": "Umwelt"}
aus = []
for d in sorted(os.listdir(Q)):
    g = next(v for k, v in GRUPPE.items() if k in d)
    for f in sorted(os.listdir(os.path.join(Q, d))):
        if re.match(r"(Beispiel|Reichtungspfeil|Richtungspfeil|Rettungsweg-Notausgang-E002|w0)", f): continue
        stamm = os.path.splitext(f)[0].replace("#U00e4", "ä")
        m = re.match(r"GHS_(\d\d)", stamm)
        if m:
            code, name = "GHS" + m.group(1), GHS[m.group(1)]
        else:
            m = re.match(r"((?:D-|WS)?[A-Z]{1,2}\d{3})[ _-]+(.*)", stamm)
            code, name = m.group(1), m.group(2)
            name = re.sub(r"[_-]+", " ", name).replace("ue", "ü").replace("oe", "ö").replace("ae", "ä").replace("UE", "Ü")
            for a, b in (("Feür", "Feuer"), ("feür", "feuer"), ("Qütsch", "Quetsch"), ("Fraün", "Frauen"), ("Fuss", "Fuß"), ("heisser", "heißer"),
                         ("Oeffentliche", "Öffentliche"), ("Uebergang", "Übergang"), ("feuergefährlichen", "feuergefährlichen Stoffen"),
                         ("Temperatur Frost", "Temperatur/Frost"), ("Rettungsweg Notausgang", "Rettungsweg/Notausgang"), ("1m", "1 m")):
                name = name.replace(a, b)
            name = name.strip()
            name = name[0].upper() + name[1:]
        im = Image.open(os.path.join(Q, d, f)); im.info.pop("icc_profile", None); im = im.convert("RGBA"); _w = Image.new("RGBA", im.size, (255, 255, 255, 255)); _w.alpha_composite(im); im = _w
        # weißen Rand abschneiden
        hg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        from PIL import ImageChops
        diff = ImageChops.difference(im.convert("RGB"), hg.convert("RGB")).convert("L").point(lambda p: 255 if p > 18 else 0)
        box = diff.getbbox()
        if box: im = im.crop(box)
        im.thumbnail((180, 180), Image.LANCZOS)
        im.convert("RGB").quantize(colors=48, method=Image.MEDIANCUT, dither=Image.NONE).save(os.path.join(Z, code + ".png"), optimize=True, icc_profile=None)
        aus.append({"code": code, "name": name, "gruppe": g})
json.dump(aus, open(os.path.join(Z, "zeichen.json"), "w"), ensure_ascii=False, indent=0)
for a in aus: print(a["code"], "|", a["name"])
