"""Variable Positionsvorlagen: Maße abfragen, Stückliste, Beschläge und Tätigkeiten über Formeln erzeugen.

Eine Vorlage (Einstellungen › Kalkulation › Positionsvorlagen) besteht aus
  parameter  [{k, name, typ: "zahl"|"material", wert, einheit, rolle (platte|kante|furnier|oberflaeche|beschlag), material_id}]
  hilfswerte [{k, name, formel}]                     – Zwischenwerte, z. B. Korpushöhe nach System 32
  teile      [{werkstoff: <Material-Parameter>, verwendung, stueck, laenge, breite, bedingung,
               kanten{oben,unten,links,rechts}, furnier{oben,unten}, oberflaeche{oben,unten}, fraesen{…: bool},
               verbinden, bohren, taschen, gehrung, bemerkung}]   – Zahlenfelder sind Formeln
  beschlaege [{material: <Material-Parameter>, menge, bemerkung, bedingung}]
  zeiten     [Tätigkeitszeilen wie in der Position (tid, kst, name, minuten, bezug, …)]
  text, einheit, masse {art, h, b, t}
Formeln: + − × / ( ), Vergleiche, Funktionen s32, s32auf, s32ab, ab, auf, runden, min, max, abs, wenn.
"""
import ast
import math
import re

TEIL_ZAHLEN = ("stueck", "laenge", "breite", "verbinden", "bohren", "taschen", "tasche_l", "tasche_b", "tasche_t", "gehrung")
SEITEN4 = ("oben", "unten", "links", "rechts")
ROLLEN = {"platte": "Platte / Massivholz", "kante": "Kante", "furnier": "Furnier", "oberflaeche": "Oberfläche", "beschlag": "Beschlag"}
ROLLE_KATS = {"platte": ["holzwerkstoffe", "massivholz", "artikel"], "kante": ["holzwerkstoffe"], "furnier": ["holzwerkstoffe"],
              "oberflaeche": ["beschichtung", "chemie"], "beschlag": ["beschlaege", "artikel", "chemie"]}


class Fehler(Exception):
    pass


def _raster(x, richtung):
    n = x / 32
    n = math.ceil(n - 1e-9) if richtung == "auf" else math.floor(n + 1e-9) if richtung == "ab" else math.floor(n + 0.5)
    return max(0, n) * 32


def s32(h, d=19, richtung="nah"):
    """Korpushöhe nach System 32: X + 2B mit X im 32-mm-Raster und B = halbe Plattenstärke (2B = d)."""
    return _raster(h - d, richtung) + d


def s32r(h, d=19, rundung=0):
    """Wie s32, Rundung als Zahl (für Auswahl-Parameter): 0 = nächstes Maß, 1 = aufrunden, −1 = abrunden."""
    return s32(h, d, "auf" if rundung > 0 else "ab" if rundung < 0 else "nah")


FUNKTIONEN = {
    "s32": s32,
    "s32r": s32r,
    "s32auf": lambda h, d=19: s32(h, d, "auf"),
    "s32ab": lambda h, d=19: s32(h, d, "ab"),
    "ab": lambda x, n=0: math.floor(x * 10 ** n + 1e-9) / 10 ** n,
    "auf": lambda x, n=0: math.ceil(x * 10 ** n - 1e-9) / 10 ** n,
    "runden": lambda x, n=0: math.floor(x * 10 ** n + 0.5) / 10 ** n,
    "min": min, "max": max, "abs": abs,
    "wenn": lambda b, x, y=0: x if b else y,
}

_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b if b else 0.0, ast.FloorDiv: lambda a, b: a // b if b else 0.0,
        ast.Mod: lambda a, b: a % b if b else 0.0, ast.Pow: lambda a, b: a ** b if abs(b) <= 4 else 0.0}
_CMP = {ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b, ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b,
        ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}


def _vorbereiten(formel):
    t = str(formel if formel is not None else "").strip()
    if not t:
        return "0"
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})*(,\d+)?|-?\d+(,\d+)?", t):   # deutsche Zahl, z. B. 2.400 oder 18,5
        return t.replace(".", "").replace(",", ".")
    t = t.replace("×", "*").replace("·", "*").replace("−", "-").replace(";", ",")
    t = re.sub(r"(?<=\d),(?=\d)", ".", t) if "(" not in t else t   # 0,5 ohne Funktionsaufruf als Dezimalzahl
    t = re.sub(r"\bund\b", " and ", t)
    t = re.sub(r"\boder\b", " or ", t)
    return t


def auswerten(formel, werte):
    """Rechnet eine Formel sicher aus (nur Zahlen, Namen aus werte, erlaubte Funktionen)."""
    if isinstance(formel, (int, float)):
        return float(formel)
    try:
        baum = ast.parse(_vorbereiten(formel), mode="eval")
    except SyntaxError:
        raise Fehler(f"Formel nicht lesbar: {formel}")

    def r(n):
        if isinstance(n, ast.Expression):
            return r(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float, str)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.Name):
            for k in (n.id, n.id.upper(), n.id.lower()):
                if k in werte:
                    return werte[k]
            raise Fehler(f"Unbekannter Wert „{n.id}“")
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            return _BIN[type(n.op)](float(r(n.left)), float(r(n.right)))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd, ast.Not)):
            v = r(n.operand)
            return -v if isinstance(n.op, ast.USub) else (+v if isinstance(n.op, ast.UAdd) else (0.0 if v else 1.0))
        if isinstance(n, ast.Compare):
            links = r(n.left)
            for op, rechts_n in zip(n.ops, n.comparators):
                rechts = r(rechts_n)
                if type(op) not in _CMP or not _CMP[type(op)](links, rechts):
                    return 0.0
                links = rechts
            return 1.0
        if isinstance(n, ast.BoolOp):
            werte_ = [r(x) for x in n.values]
            return 1.0 if (all(werte_) if isinstance(n.op, ast.And) else any(werte_)) else 0.0
        if isinstance(n, ast.IfExp):
            return r(n.body) if r(n.test) else r(n.orelse)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id.lower() in FUNKTIONEN and not n.keywords:
            try:
                return FUNKTIONEN[n.func.id.lower()](*[r(a) for a in n.args])
            except TypeError:
                raise Fehler(f"Falsche Angaben in {n.func.id}(…)")
        raise Fehler(f"In Formeln nicht erlaubt: {formel}")
    v = r(baum)
    if isinstance(v, str):
        raise Fehler(f"Formel ergibt keine Zahl: {formel}")
    return float(v)


def zahl_text(v):
    v = round(float(v or 0), 1)
    t = f"{v:.1f}".replace(".", ",")   # Maße ohne Tausenderpunkt (2400 mm)
    return t[:-2] if t.endswith(",0") else t


def optionen(p):
    """Auswahl-Parameter: „0=ohne; 1=Passleiste; 2=Blende“ → [(0.0, "ohne"), …]"""
    aus = []
    for teil in re.split(r"[;\n]", str(p.get("optionen") or "")):
        if "=" in teil:
            w, t = teil.split("=", 1)
            try:
                aus.append((float(w.strip().replace(",", ".")), t.strip()))
            except ValueError:
                continue
    return aus


def berechnen(v, eingaben=None):
    """→ {werte, hilfswerte, materialien {k: material_id}, teile, beschlaege, zeiten, text, masse, menge, fehler[], hinweise[]}"""
    eingaben = eingaben or {}
    werte, mats, fehler = {}, {}, []
    for p in v.get("parameter") or []:
        k = (p.get("k") or "").strip()
        if not k:
            continue
        if (p.get("typ") or "zahl") == "material":
            mid = eingaben.get(k, p.get("material_id"))
            mats[k] = int(mid) if str(mid or "").isdigit() else None
            continue
        try:
            werte[k] = auswerten(eingaben[k] if k in eingaben and eingaben[k] not in ("", None) else (p.get("wert") or 0), werte)
        except Fehler as f:
            fehler.append(f"{p.get('name') or k}: {f}")
            werte[k] = 0.0
    hilfs = []
    for hw in v.get("hilfswerte") or []:
        k = (hw.get("k") or "").strip()
        if not k:
            continue
        try:
            werte[k] = auswerten(hw.get("formel"), werte)
        except Fehler as f:
            fehler.append(f"{hw.get('name') or k}: {f}")
            werte[k] = 0.0
        hilfs.append({"k": k, "name": hw.get("name") or k, "wert": round(werte[k], 2), "verdeckt": bool(hw.get("verdeckt"))})

    def zahl(feld, formel, wo):
        try:
            return round(auswerten(formel, werte), 1)
        except Fehler as f:
            fehler.append(f"{wo}, {feld}: {f}")
            return 0.0

    def gilt(x, wo):
        b = (x.get("bedingung") or "").strip()
        return True if not b else zahl("Bedingung", b, wo) > 0

    teile = []
    for i, t in enumerate(v.get("teile") or [], 1):
        wo = f"Teil {i} ({t.get('verwendung') or '–'})"
        if not gilt(t, wo):
            continue
        z = {f: zahl(f, t.get(f), wo) for f in TEIL_ZAHLEN if str(t.get(f) or "").strip()}
        if z.get("stueck", 0) <= 0:
            continue
        teile.append({"werkstoff_param": t.get("werkstoff") or "", "verwendung": t.get("verwendung") or "", **z,
                      "kanten": {s: t["kanten"][s] for s in SEITEN4 if (t.get("kanten") or {}).get(s)},
                      "furnier": {s: t["furnier"][s] for s in ("oben", "unten") if (t.get("furnier") or {}).get(s)},
                      "oberflaeche": {s: t["oberflaeche"][s] for s in ("oben", "unten") if (t.get("oberflaeche") or {}).get(s)},
                      "fraesen": {s: True for s in SEITEN4 if (t.get("fraesen") or {}).get(s)},
                      "bemerkung": t.get("bemerkung") or ""})
    hinweise = []
    for pr in v.get("pruefungen") or []:
        if str(pr.get("bedingung") or "").strip() and zahl("Prüfung", pr["bedingung"], "Prüfung") > 0:
            t = pr.get("text") or pr["bedingung"]
            for k, w in sorted(werte.items(), key=lambda x: -len(x[0])):
                t = re.sub(r"\{\s*" + re.escape(k) + r"\s*\}", zahl_text(w), t)
            hinweise.append(t)
    beschlaege = []
    for i, b in enumerate(v.get("beschlaege") or [], 1):
        wo = f"Beschlag {i}"
        if not gilt(b, wo):
            continue
        m = zahl("Menge", b.get("menge"), wo)
        if m > 0:
            beschlaege.append({"material_param": b.get("material") or "", "menge": m, "bemerkung": b.get("bemerkung") or ""})
    text = v.get("text") or ""
    for p in v.get("parameter") or []:   # {K:text} setzt bei Auswahl-Parametern den Text der gewählten Möglichkeit ein
        if p.get("typ") == "auswahl" and p.get("k"):
            text = re.sub(r"\{\s*" + re.escape(p["k"]) + r"\s*:\s*text\s*\}", dict(optionen(p)).get(werte.get(p["k"], 0), ""), text)
    for k, w in sorted(werte.items(), key=lambda x: -len(x[0])):
        text = re.sub(r"\{\s*" + re.escape(k) + r"\s*\}", zahl_text(w), text)
    ma = v.get("masse") or {}
    masse = {"art": ma.get("art") or "HBT"}
    for x in ("h", "b", "t"):
        if str(ma.get(x) or "").strip():
            masse[x] = zahl(f"Maß {x.upper()}", ma[x], "Maße")
    menge = zahl("Menge", v.get("menge") or 1, "Position") if str(v.get("menge") or "").strip() else 1.0
    return {"werte": {k: round(x, 2) for k, x in werte.items()}, "hilfswerte": hilfs, "materialien": mats, "teile": teile,
            "beschlaege": beschlaege, "zeiten": [dict(z) for z in v.get("zeiten") or []], "text": text, "masse": masse,
            "menge": menge, "fehler": fehler, "hinweise": hinweise,
            "auswahl_texte": {p["k"]: dict(optionen(p)).get(werte.get(p["k"], 0), "") for p in v.get("parameter") or []
                              if p.get("typ") == "auswahl" and p.get("k")}}


def aus_position(p, kalk, name):
    """Neue Vorlage aus einer fertigen Position: Werkstoffe werden zu Material-Parametern, Maße bleiben feste Zahlen
    (danach in den Einstellungen durch Formeln ersetzen)."""
    wks = {w["k"]: w for w in kalk.get("werkstoffe") or [] if w.get("k")}
    bss = {b["k"]: b for b in kalk.get("beschlaege") or [] if b.get("k")}
    params, nach_k = [], {}
    m = p.get("masse") or {}
    for k, nm in (("H", "Höhe"), ("B", "Breite"), ("T", "Tiefe")):
        params.append({"k": k, "name": nm, "typ": "zahl", "wert": float(m.get(k.lower()) or 0), "einheit": "mm"})

    def param(kuerzel, rolle, quelle):
        if not kuerzel:
            return ""
        if (rolle, kuerzel) in nach_k:
            return nach_k[(rolle, kuerzel)]
        w = quelle.get(kuerzel) or {}
        k = re.sub(r"[^A-Z0-9]", "", (w.get("matnr") or kuerzel).upper())[:6] or kuerzel
        k = "M_" + k
        while any(x["k"] == k for x in params):
            k += "X"
        params.append({"k": k, "name": w.get("name") or kuerzel, "typ": "material", "rolle": rolle, "matnr": w.get("matnr") or w.get("artnr") or ""})
        nach_k[(rolle, kuerzel)] = k
        return k
    teile = []
    for t in p.get("stueckliste") or []:
        typ = (wks.get(t.get("werkstoff")) or {}).get("typ")
        teile.append({"werkstoff": param(t.get("werkstoff"), "platte", wks), "verwendung": t.get("verwendung") or "",
                      "stueck": str(zahl_text(t.get("stueck") or 0)), "laenge": zahl_text(t.get("laenge")), "breite": zahl_text(t.get("breite")),
                      "kanten": {s: param(k, "kante", wks) for s, k in (t.get("kanten") or {}).items() if k},
                      "furnier": {s: param(k, "furnier", wks) for s, k in (t.get("furnier") or {}).items() if k},
                      "oberflaeche": {s: param(k, "oberflaeche", wks) for s, k in (t.get("oberflaeche") or {}).items() if k},
                      "fraesen": {s: True for s, x in (t.get("fraesen") or {}).items() if x},
                      "verbinden": zahl_text((t.get("verbinden") or {}).get("anzahl") or 0) if (t.get("verbinden") or {}).get("anzahl") else "",
                      "bohren": zahl_text(t["bohren"]) if t.get("bohren") else "", "taschen": zahl_text(t["taschen"]) if t.get("taschen") else "",
                      **{k: zahl_text(t[k]) for k in ("tasche_l", "tasche_b", "tasche_t") if t.get(k)},
                      "gehrung": zahl_text(t["gehrung"]) if t.get("gehrung") else "", "bemerkung": t.get("bemerkung") or "",
                      "_typ": typ})
    for t in teile:
        t.pop("_typ", None)
    besch = [{"material": param(b.get("k"), "beschlag", bss), "menge": zahl_text(b.get("menge") or 0), "bemerkung": b.get("bemerkung") or ""}
             for b in p.get("beschlaege") or [] if b.get("k")]
    return {"name": name, "text": p.get("text") or "", "einheit": p.get("einheit") or "Stk.", "parameter": params, "hilfswerte": [],
            "teile": teile, "beschlaege": besch, "zeiten": [dict(z) for z in p.get("zeiten") or []],
            "masse": {"art": m.get("art") or "HBT", "h": "H", "b": "B", "t": "T"}}


def beispiel_system32():
    """Beispielvorlage nach dem System-32-Konfigurator „Nische aufteilen“: alle Wahlmöglichkeiten des Konfigurators
    (Ausführung der Passleiste, Luft, Fugen, Rundung der Höhe) und links/rechts wahlweise Passleiste, Blende oder nichts."""
    P = lambda k, n, w, e="mm": {"k": k, "name": n, "typ": "zahl", "wert": w, "einheit": e}  # noqa: E731
    A = lambda k, n, w, o: {"k": k, "name": n, "typ": "auswahl", "wert": w, "optionen": o}  # noqa: E731
    M = lambda k, n, r: {"k": k, "name": n, "typ": "material", "rolle": r, "material_id": None}  # noqa: E731
    vorn = {"oben": "KANTE"}
    abschluss = "0=ohne (Korpus an der Wand); 1=Passleiste; 2=Blende"
    return {
        "id": "system32", "name": "Einbauschrank System 32 (Nische)", "einheit": "Stk.",
        "text": "Einbauschrank nach Maß in Nische {N} × {H} mm, Tiefe {T} mm\n{A} Korpusse nach System 32: Korpushöhe {KH} mm, "
                "Korpusbreite {KB} mm, je {FB} Fachböden\nAbschluss links: {AL:text}, rechts: {AR:text}; Passleisten {PT:text}\n"
                "Sockel {S} mm, Passleiste oben {PLO} mm",
        "parameter": [P("N", "Nischenbreite (lichte Weite)", 2400), P("H", "Nischenhöhe", 2500), P("T", "Korpustiefe", 600),
                      P("A", "Anzahl Korpusse", 3, "Stk."), P("S", "Sockelhöhe", 100), P("D", "Plattenstärke Korpus", 19),
                      A("RH", "Rundung der Korpushöhe", -1, "0=nächstes Maß; 1=aufrunden; -1=abrunden"),
                      P("PO", "Passleiste oben min.", 20),
                      A("AL", "Abschluss links", 1, abschluss), P("PLL", "Passleiste links min.", 20), P("BL", "Blende links Breite", 50),
                      A("AR", "Abschluss rechts", 1, abschluss), P("PLR", "Passleiste rechts min.", 20), P("BR", "Blende rechts Breite", 50),
                      A("PT", "Ausführung Passleiste", 0, "0=mit Schattenfuge; 1=flächenbündig (Luft an den äußeren Korpussen)"),
                      P("LU", "Luft je Außenseite (flächenbündig)", 2), P("FG", "Fuge zwischen Korpussen", 0),
                      P("ZG", "Zugabe Passleisten zum Anpassen", 10), P("FB", "Fachböden je Korpus", 4, "Stk."), P("FU", "Fuge Front", 3),
                      M("KORPUS", "Korpusmaterial", "platte"), M("FRONT", "Frontmaterial", "platte"), M("RW", "Rückwand", "platte"),
                      M("KANTE", "Kante Korpus", "kante"), M("KANTEF", "Kante Front", "kante"),
                      M("BAND", "Topfband", "beschlag"), M("BT", "Bodenträger", "beschlag")],
        "hilfswerte": [
            {"k": "PL_L", "verdeckt": True, "name": "Passleiste links ja (1)", "formel": "AL == 1"},
            {"k": "PL_R", "verdeckt": True, "name": "Passleiste rechts ja (1)", "formel": "AR == 1"},
            {"k": "FIX", "verdeckt": True, "name": "Blenden zusammen", "formel": "wenn(AL == 2, BL) + wenn(AR == 2, BR)"},
            {"k": "MINP", "verdeckt": True, "name": "Passleisten mindestens", "formel": "PL_L*PLL + PL_R*PLR"},
            {"k": "LUFT", "verdeckt": True, "name": "Luft flächenbündig", "formel": "wenn(PT == 1, LU * (PL_L + PL_R))"},
            {"k": "FUGEN", "verdeckt": True, "name": "Fugen zwischen Korpussen", "formel": "FG * (A - 1)"},
            {"k": "KB", "name": "Korpusbreite", "formel": "ab((N - FIX - MINP - LUFT - FUGEN) / A)"},
            {"k": "REST", "verdeckt": True, "name": "Rest für die Passleisten", "formel": "N - FIX - A*KB - LUFT - FUGEN"},
            {"k": "PLSL", "name": "Passleiste links", "formel": "wenn(PL_L, wenn(PL_R, ab(REST/2), REST))"},
            {"k": "PLSR", "name": "Passleiste rechts", "formel": "wenn(PL_R, REST - PLSL)"},
            {"k": "KH", "name": "Korpushöhe (X + 2B im 32er-Raster)", "formel": "s32r(H - S - PO, D, RH)"},
            {"k": "PLO", "name": "Passleiste oben", "formel": "H - S - KH"},
            {"k": "IB", "verdeckt": True, "name": "Innenbreite", "formel": "KB - 2*D"},
            {"k": "Y", "verdeckt": True, "name": "Abstand Lochreihen (T − 2 × 37)", "formel": "T - 74"},
            {"k": "BAENDER", "name": "Bänder je Tür", "formel": "wenn(KH > 1600, 4, wenn(KH > 900, 3, 2))"}],
        "pruefungen": [
            {"bedingung": "KB < 150", "text": "Nische zu klein: Korpusbreite nur {KB} mm."},
            {"bedingung": "PL_L and PLSL < PLL", "text": "Passleiste links {PLSL} mm liegt unter dem Minimum {PLL} mm."},
            {"bedingung": "PL_R and PLSR < PLR", "text": "Passleiste rechts {PLSR} mm liegt unter dem Minimum {PLR} mm."},
            {"bedingung": "PL_L == 0 and PL_R == 0 and REST > 0", "text": "Ohne Passleisten bleiben {REST} mm Rest – Korpusbreite oder Blenden anpassen."},
            {"bedingung": "PLO < PO", "text": "Passleiste oben {PLO} mm liegt unter dem Minimum {PO} mm."}],
        "teile": [
            {"werkstoff": "KORPUS", "verwendung": "Seite", "stueck": "2*A", "laenge": "KH", "breite": "T", "kanten": vorn, "bohren": "BAENDER*2"},
            {"werkstoff": "KORPUS", "verwendung": "Boden/Deckel", "stueck": "2*A", "laenge": "IB", "breite": "T", "kanten": vorn, "verbinden": "4"},
            {"werkstoff": "KORPUS", "verwendung": "Fachboden", "stueck": "FB*A", "laenge": "IB - 2", "breite": "T - 20", "kanten": vorn, "bedingung": "FB"},
            {"werkstoff": "RW", "verwendung": "Rückwand (genutet)", "stueck": "A", "laenge": "KH - 2*D + 16", "breite": "IB + 16"},
            {"werkstoff": "FRONT", "verwendung": "Tür", "stueck": "A", "laenge": "KH - FU", "breite": "KB - FU",
             "kanten": {"oben": "KANTEF", "unten": "KANTEF", "links": "KANTEF", "rechts": "KANTEF"}},
            {"werkstoff": "FRONT", "verwendung": "Sockelblende", "stueck": "1", "laenge": "N", "breite": "S", "kanten": {"oben": "KANTEF"}, "bedingung": "S"},
            {"werkstoff": "FRONT", "verwendung": "Passleiste links", "stueck": "1", "laenge": "H - S", "breite": "PLSL + ZG",
             "kanten": {"oben": "KANTEF"}, "bedingung": "PL_L", "bemerkung": "mit Zugabe zum Anpassen"},
            {"werkstoff": "FRONT", "verwendung": "Passleiste rechts", "stueck": "1", "laenge": "H - S", "breite": "PLSR + ZG",
             "kanten": {"oben": "KANTEF"}, "bedingung": "PL_R", "bemerkung": "mit Zugabe zum Anpassen"},
            {"werkstoff": "FRONT", "verwendung": "Blende links", "stueck": "1", "laenge": "H", "breite": "BL",
             "kanten": {"oben": "KANTEF"}, "bedingung": "AL == 2"},
            {"werkstoff": "FRONT", "verwendung": "Blende rechts", "stueck": "1", "laenge": "H", "breite": "BR",
             "kanten": {"oben": "KANTEF"}, "bedingung": "AR == 2"},
            {"werkstoff": "FRONT", "verwendung": "Passleiste oben", "stueck": "1", "laenge": "N - FIX", "breite": "PLO + ZG",
             "kanten": {"oben": "KANTEF"}, "bedingung": "PLO > 0", "bemerkung": "mit Zugabe zum Anpassen"}],
        "beschlaege": [{"material": "BAND", "menge": "A * BAENDER"}, {"material": "BT", "menge": "4 * FB * A", "bedingung": "FB"}],
        "zeiten": [], "masse": {"art": "HBT", "h": "H", "b": "N", "t": "T"},
    }


def beispiel_korpus():
    """Beispielvorlage nach dem System-32-Konfigurator „Korpusmaß“: ein Korpus, Höhe im 32er-Raster."""
    P = lambda k, n, w, e="mm": {"k": k, "name": n, "typ": "zahl", "wert": w, "einheit": e}  # noqa: E731
    M = lambda k, n, r: {"k": k, "name": n, "typ": "material", "rolle": r, "material_id": None}  # noqa: E731
    vorn = {"oben": "KANTE"}
    return {
        "id": "korpus32", "name": "Korpus System 32 (Korpusmaß)", "einheit": "Stk.",
        "text": "Korpus nach System 32, {B} × {HG} × {T} mm (B × H × T), Korpushöhe {KH} mm, {FB} Fachböden",
        "parameter": [P("H", "Gesamthöhe inkl. Sockel", 720), P("B", "Breite", 600), P("T", "Tiefe", 560), P("D", "Plattenstärke", 19),
                      P("S", "Sockelhöhe", 0), {"k": "RH", "name": "Rundung der Höhe", "typ": "auswahl", "wert": 0,
                                                 "optionen": "0=nächstes Maß; 1=aufrunden; -1=abrunden"},
                      P("FB", "Fachböden", 1, "Stk."), P("FU", "Fuge Front", 3),
                      M("KORPUS", "Korpusmaterial", "platte"), M("FRONT", "Frontmaterial", "platte"), M("RW", "Rückwand", "platte"),
                      M("KANTE", "Kante", "kante"), M("BAND", "Topfband", "beschlag"), M("BT", "Bodenträger", "beschlag")],
        "hilfswerte": [{"k": "KH", "name": "Korpushöhe (X + 2B)", "formel": "s32r(H - S, D, RH)"},
                       {"k": "HG", "name": "Gesamthöhe gerundet", "formel": "KH + S"},
                       {"k": "DH", "verdeckt": True, "name": "Abweichung zur Eingabe", "formel": "HG - H"},
                       {"k": "Y", "verdeckt": True, "name": "Abstand Lochreihen (T − 2 × 37)", "formel": "T - 74"},
                       {"k": "IB", "verdeckt": True, "name": "Innenbreite", "formel": "B - 2*D"},
                       {"k": "BAENDER", "name": "Bänder", "formel": "wenn(KH > 1600, 4, wenn(KH > 900, 3, 2))"}],
        "pruefungen": [{"bedingung": "DH != 0", "text": "Gesamthöhe auf {HG} mm angepasst (Abweichung {DH} mm)."}],
        "teile": [
            {"werkstoff": "KORPUS", "verwendung": "Seite", "stueck": "2", "laenge": "KH", "breite": "T", "kanten": vorn, "bohren": "BAENDER*2"},
            {"werkstoff": "KORPUS", "verwendung": "Boden/Deckel", "stueck": "2", "laenge": "IB", "breite": "T", "kanten": vorn, "verbinden": "4"},
            {"werkstoff": "KORPUS", "verwendung": "Fachboden", "stueck": "FB", "laenge": "IB - 2", "breite": "T - 20", "kanten": vorn, "bedingung": "FB"},
            {"werkstoff": "RW", "verwendung": "Rückwand (genutet)", "stueck": "1", "laenge": "KH - 2*D + 16", "breite": "IB + 16"},
            {"werkstoff": "FRONT", "verwendung": "Tür", "stueck": "1", "laenge": "KH - FU", "breite": "B - FU",
             "kanten": {"oben": "KANTE", "unten": "KANTE", "links": "KANTE", "rechts": "KANTE"}}],
        "beschlaege": [{"material": "BAND", "menge": "BAENDER"}, {"material": "BT", "menge": "4 * FB", "bedingung": "FB"}],
        "zeiten": [], "masse": {"art": "HBT", "h": "HG", "b": "B", "t": "T"},
    }
