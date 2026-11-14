"""Restelager (Holzwerkstoffe) und ganze Platten – gemeinsamer Bestand mit dem Zuschnittprogramm.
Das Lager wird als ein Dokument im Format der Zuschnitt-App („jahresring-lager“) gespeichert, damit das
Zuschnittprogramm unverändert damit rechnen kann. Das Büro bearbeitet es über eigene, kleine Funktionen."""
import json
import os
import secrets
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS zuschnitt_buchungen (
    schluessel TEXT PRIMARY KEY, auftrag_id INTEGER, material_id INTEGER, ak_id INTEGER, menge REAL, hinweis TEXT DEFAULT '', angelegt TEXT
);
CREATE TABLE IF NOT EXISTS reste_lager (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    daten TEXT NOT NULL, rev INTEGER DEFAULT 0, geaendert TEXT, geaendert_von TEXT DEFAULT ''
);
"""


HILFE = {"abgleich": None}   # von app.py gesetzt: Plattenbuchungen → Materialstamm/Auftragskosten


class Fehler(Exception):
    def __init__(self, text, code=400, daten=None):
        super().__init__(text)
        self.code = code
        self.daten = daten


def jetzt():
    return datetime.now().isoformat(timespec="seconds")


def leer():
    return {"format": FORMAT, "version": 1, "rev": 0, "updated": None, "nextRest": 1, "items": [], "bookings": {},
            "reservations": {}, "orders": {}, "log": []}


def schema(con):
    con.executescript(SCHEMA)


FORMAT = "jahresring-lager"


def laden(con):
    r = con.execute("SELECT * FROM reste_lager WHERE id=1").fetchone()
    if not r:
        return leer(), 0
    try:
        d = json.loads(r["daten"])
    except ValueError:
        d = leer()
    return {**leer(), **d, "format": FORMAT}, r["rev"]


def speichern(con, lager, basis, wer):
    if not isinstance(lager, dict) or lager.get("format") != FORMAT or not isinstance(lager.get("items"), list):
        raise Fehler("Das ist keine Lagerdatei der Zuschnitt-App.")
    lager["format"] = FORMAT
    _, rev = laden(con)
    if basis is not None and int(basis) != rev:
        raise Fehler("Das Lager wurde inzwischen geändert.", 409)
    lager = {k: v for k, v in lager.items() if k != "serverRev"}
    _IM_SPEICHERN[0] += 1
    try:
        if HILFE.get("abgleich"):
            alt, _ = laden(con)
            HILFE["abgleich"](con, alt, lager)
        if lager.get("stueckSync"):
            bestand_nachziehen(con, lager)
            stueck_aus_bestand(con, lager)
    finally:
        _IM_SPEICHERN[0] -= 1
    return _schreiben(con, lager, rev, wer)


def _schreiben(con, lager, rev, wer):
    neu = rev + 1
    con.execute("INSERT INTO reste_lager (id, daten, rev, geaendert, geaendert_von) VALUES (1,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET daten=excluded.daten, rev=excluded.rev, geaendert=excluded.geaendert, geaendert_von=excluded.geaendert_von",
                (json.dumps(lager, ensure_ascii=False), neu, jetzt(), wer))
    return neu


def _aendern(con, wer, fn, meldung):
    lager, rev = laden(con)
    erg = fn(lager)
    lager["rev"] = (lager.get("rev") or 0) + 1
    lager["updated"] = datetime.now().isoformat()
    lager["log"] = ([{"t": lager["updated"], "msg": meldung + " (Büro)"}] + (lager.get("log") or []))[:200]
    speichern(con, lager, rev, wer)
    return erg


def _zahl(x):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def rest_anlegen(con, d, wer):
    if not (d.get("material") or "").strip() or _zahl(d.get("laenge")) <= 0 or _zahl(d.get("breite")) <= 0:
        raise Fehler("Bitte Material, Länge und Breite angeben.")

    def fn(lager):
        no = "R-" + str(int(lager.get("nextRest") or 1)).zfill(4)
        lager["nextRest"] = int(lager.get("nextRest") or 1) + 1
        it = {"id": "r" + secrets.token_hex(5), "kind": "rest", "no": no, "material": d["material"].strip(),
              "thickness": _zahl(d.get("dicke")), "length": _zahl(d.get("laenge")), "width": _zahl(d.get("breite")),
              "location": (d.get("lagerort") or "").strip(), "date": datetime.now().isoformat(), "from": (d.get("herkunft") or "").strip()}
        lager["items"].append(it)
        return it
    return _aendern(con, wer, fn, f"Rest eingelagert: {d.get('material')} {d.get('laenge')} × {d.get('breite')}")


def rest_aendern(con, rid, d, wer):
    def fn(lager):
        it = next((i for i in lager["items"] if i.get("id") == rid), None)
        if not it:
            raise Fehler("Rest nicht gefunden", 404)
        aktion = d.get("aktion")
        if aktion == "verbraucht":
            it["used"] = datetime.now().isoformat()
            it["usedFor"] = d.get("fuer") or "Büro"
        elif aktion == "zurueck":
            it.pop("used", None)
            it.pop("usedFor", None)
        elif aktion == "loeschen":
            lager["items"] = [i for i in lager["items"] if i.get("id") != rid]
        else:
            for k_buero, k in (("material", "material"), ("lagerort", "location")):
                if k_buero in d:
                    it[k] = str(d[k_buero] or "").strip()
            for k_buero, k in (("dicke", "thickness"), ("laenge", "length"), ("breite", "width")):
                if k_buero in d:
                    it[k] = _zahl(d[k_buero])
        return it
    return _aendern(con, wer, fn, f"Rest {rid}: {d.get('aktion') or 'geändert'}")


def platte_menge(con, pid, d, wer):
    def fn(lager):
        it = next((i for i in lager["items"] if i.get("id") == pid and i.get("kind") == "platte"), None)
        if not it:
            raise Fehler("Platte nicht gefunden", 404)
        it["qty"] = max(0, int(_zahl(d.get("menge"))))
        return it
    return _aendern(con, wer, fn, f"Plattenbestand geändert: {pid} → {d.get('menge')}")


def uebersicht(con):
    lager, rev = laden(con)
    reste = [i for i in lager["items"] if i.get("kind") == "rest"]
    platten = [i for i in lager["items"] if i.get("kind") == "platte"]
    r = con.execute("SELECT geaendert, geaendert_von FROM reste_lager WHERE id=1").fetchone()
    return {"rev": rev, "reste": reste, "platten": platten, "log": (lager.get("log") or [])[:30], "beschaffung": beschaffung(lager),
            "geaendert": r["geaendert"] if r else None, "geaendert_von": r["geaendert_von"] if r else ""}


# ---------------------------------------------------------------- Zuschnittplan aus dem Projektordner
def plan_suchen(projektordner, unterordner="40_Kalkulation"):
    """Neueste JSON-Datei mit Zuschnittplan (CAD-Export) im Ordner 40_Kalkulation (oder einem Ordner, der so beginnt)."""
    if not projektordner or not os.path.isdir(projektordner):
        raise Fehler("Für diesen Auftrag ist kein Projektordner angelegt (Auftrag › Projekt).")
    kandidaten = []
    stichwort = unterordner.lower()
    nummer = stichwort.split("_")[0]
    for n in os.listdir(projektordner):
        p = os.path.join(projektordner, n)
        if os.path.isdir(p) and (n.lower() == stichwort or n.lower().startswith(nummer + "_") or "kalkulation" in n.lower()):
            kandidaten.append(p)
    if not kandidaten:
        raise Fehler(f"Im Projektordner gibt es keinen Ordner „{unterordner}“.")
    dateien = []
    for ordner in kandidaten:
        for wurzel, _, files in os.walk(ordner):
            for f in files:
                if f.lower().endswith(".json"):
                    dateien.append(os.path.join(wurzel, f))
    for pfad in sorted(dateien, key=os.path.getmtime, reverse=True):
        try:
            with open(pfad, "r", encoding="utf-8-sig") as fh:
                plan = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(plan, dict) and isinstance(plan.get("plates"), list) and plan["plates"]:
            return os.path.basename(pfad), plan, pfad
    raise Fehler(f"In „{os.path.basename(kandidaten[0])}“ liegt keine Zuschnitt-JSON aus dem CAD.")


# ---------------------------------------------------------------- Etiketten

def _svg_esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _passend(text, fs, breite, fett=False):
    """Schriftgröße so verkleinern, dass der Text in die Breite passt (Schätzung über die Zeichenzahl)."""
    if not text:
        return fs
    return max(fs * 0.55, min(fs, breite / (len(text) * (0.58 if fett else 0.53))))


def _umbrechen(text, fs, breite, fett=False):
    """Zu langen Text an der Wortgrenze in zwei möglichst gleich lange Zeilen teilen."""
    woerter = text.split()
    if len(woerter) < 2 or len(text) * fs * (0.58 if fett else 0.53) <= breite:
        return [text]
    best = min(range(1, len(woerter)), key=lambda i: max(len(" ".join(woerter[:i])), len(" ".join(woerter[i:]))))
    return [" ".join(woerter[:best]), " ".join(woerter[best:])]


def etikett_svg(e, qr, mass=(70, 74)):
    """Dasselbe Etikett als SVG (für den Zebra-Druck: Bild → 1-Bit → ZPL). Gezeichnet auf 70 × 74 mm; bei anderer
    Etikettengröße skaliert der Betrachter die Zeichnung als Ganzes und setzt sie mittig (viewBox)."""
    F = "Arial, Helvetica, sans-serif"
    teile = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{mass[0]}mm" height="{mass[1]}mm" viewBox="0 0 70 74">',
             '<rect width="70" height="74" fill="#fff"/>']

    def text(x, y, fs, t, fett=False):
        gewicht = ' font-weight="700"' if fett else ""
        teile.append(f'<text x="{x}" y="{y:.2f}" font-size="{fs:.2f}" font-family="{F}"{gewicht}>{_svg_esc(t)}</text>')
    titel = e.get("titel") or ""
    fs = _passend(titel, 7.0, 62, True)
    text(4, 4 + fs * 0.9, fs, titel, True)
    y = 4 + fs * 0.9 + 6.2
    for i, z in enumerate((e.get("zeilen") or [])[:5]):
        fett = i == 0
        for teil in (_umbrechen(z, 3.9, 62, True) if fett else [z]):
            if y > 38:
                break
            fs = _passend(teil, 3.9 if fett else 3.35, 62, fett)
            text(4, y, fs, teil, fett)
            y += fs + (0.5 if fett else 1.3)
        y += 1.0 if fett else 0
    klein = e.get("klein") or ""
    if klein:
        text(4, 69.5, _passend(klein, 2.5, 30), klein)
    q = qr(e["qr_text"]).replace("<svg ", '<svg x="36" y="40" width="30" height="30" shape-rendering="crispEdges" ', 1)
    teile.append(q)
    teile.append("</svg>")
    return "".join(teile)


ZEBRA_JS = r"""
(function () {
  var ZEBRA_SVC = "38eb4a80-c570-11e3-9507-0002a5d5c51b", ZEBRA_WRITE = "38eb4a82-c570-11e3-9507-0002a5d5c51b";
  var LBL = { w: (window.ETIKETT || {}).w || 70, h: (window.ETIKETT || {}).h || 74, dpmm: 8 }, st = { device: null, ch: null };
  var $ = function (id) { return document.getElementById(id); };
  var svgs = JSON.parse($("zsvgs").textContent);
  function status(t) { $("zst").textContent = t || ""; }
  function crc16(str) {
    var c = 0;
    for (var i = 0; i < str.length; i++) {
      c ^= str.charCodeAt(i) << 8;
      for (var b = 0; b < 8; b++) c = c & 0x8000 ? ((c << 1) ^ 0x1021) & 0xffff : (c << 1) & 0xffff;
    }
    return c.toString(16).toUpperCase().padStart(4, "0");
  }
  async function svgToBits(svg) {
    var wd = LBL.w * LBL.dpmm, ht = LBL.h * LBL.dpmm, img = new Image();
    var url = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svg)));
    await new Promise(function (res, rej) { img.onload = res; img.onerror = function () { rej(new Error("Etikett konnte nicht gezeichnet werden")); }; img.src = url; });
    var c = document.createElement("canvas"); c.width = wd; c.height = ht;
    var g = c.getContext("2d"); g.fillStyle = "#fff"; g.fillRect(0, 0, wd, ht); g.drawImage(img, 0, 0, wd, ht);
    var px = g.getImageData(0, 0, wd, ht).data, rowBytes = Math.ceil(wd / 8), bits = new Uint8Array(rowBytes * ht);
    for (var y = 0; y < ht; y++) for (var x = 0; x < wd; x++) {
      var i = (y * wd + x) * 4, lum = 0.3 * px[i] + 0.59 * px[i + 1] + 0.11 * px[i + 2];
      if (lum < 200) bits[y * rowBytes + (x >> 3)] |= 0x80 >> (x & 7);
    }
    return { bits: bits, rowBytes: rowBytes, wd: wd, ht: ht };
  }
  async function zplForSvg(svg) {
    var r = await svgToBits(svg), bits = r.bits, data;
    if (typeof CompressionStream === "function") {
      var z = new Uint8Array(await new Response(new Blob([bits]).stream().pipeThrough(new CompressionStream("deflate"))).arrayBuffer());
      var bin = ""; for (var i = 0; i < z.length; i++) bin += String.fromCharCode(z[i]);
      var b64 = btoa(bin); data = ":Z64:" + b64 + ":" + crc16(b64);
    } else {
      data = Array.from(bits, function (b) { return b.toString(16).toUpperCase().padStart(2, "0"); }).join("");
    }
    return "^XA^PW" + r.wd + "^LL" + r.ht + "^LH0,0^FO0,0^GFA," + bits.length + "," + bits.length + "," + r.rowBytes + "," + data + "^FS^PQ1^XZ";
  }
  window.zebraZpl = zplForSvg;
  function merk(name) { try { localStorage.setItem("etikett.zebra", name || ""); } catch (e) {} }
  function gemerkt() { try { return localStorage.getItem("etikett.zebra") || ""; } catch (e) { return ""; } }
  async function verbinden(neu) {
    if (!navigator.bluetooth) {
      throw new Error(window.isSecureContext === false
        ? "Bluetooth ist hier gesperrt, weil die Seite nicht über https oder localhost geöffnet ist. Bitte die verschlüsselte Adresse verwenden (Einstellungen › Benutzer & Netzwerk › Verschlüsselung)."
        : "Dieser Browser kann kein Bluetooth. Bitte Chrome verwenden (Tablet oder PC mit Bluetooth).");
    }
    if (!st.device && !neu && navigator.bluetooth.getDevices) {
      try {
        var name = gemerkt(), liste = await navigator.bluetooth.getDevices();
        st.device = liste.filter(function (d) { return name && d.name === name; })[0] || null;
      } catch (e) { st.device = null; }
    }
    if (!st.device || neu) {
      st.ch = null;
      st.device = await navigator.bluetooth.requestDevice({ acceptAllDevices: true, optionalServices: [ZEBRA_SVC] });
      st.device.addEventListener("gattserverdisconnected", function () { st.ch = null; status("Drucker getrennt"); });
      merk(st.device.name);
    }
    if (!st.ch) {
      status("verbinde mit " + (st.device.name || "Drucker") + " …");
      var srv = await st.device.gatt.connect(), svc = await srv.getPrimaryService(ZEBRA_SVC);
      st.ch = await svc.getCharacteristic(ZEBRA_WRITE);
    }
    $("zwahl").hidden = false;
    return st.ch;
  }
  async function senden(text) {
    var ch = await verbinden(false), bytes = new TextEncoder().encode(text);
    for (var i = 0; i < bytes.length; i += 160) {
      var part = bytes.slice(i, i + 160);
      if (ch.writeValueWithResponse) await ch.writeValueWithResponse(part); else await ch.writeValue(part);
    }
  }
  async function drucken() {
    var b = $("zdruck"); b.disabled = true;
    try {
      await verbinden(false);
      for (var i = 0; i < svgs.length; i++) {
        status("Etikett " + (i + 1) + " von " + svgs.length + " …");
        await senden(await zplForSvg(svgs[i]));
      }
      status(svgs.length + (svgs.length === 1 ? " Etikett" : " Etiketten") + " an " + (st.device && st.device.name || "Zebra") + " gesendet");
    } catch (e) {
      if (e && e.name === "NotFoundError") status("");
      else { status(""); alert("Etikett nicht gedruckt: " + (e.message || e)); }
    } finally { b.disabled = false; }
  }
  $("zdruck").addEventListener("click", drucken);
  $("zwahl").addEventListener("click", async function () {
    try { st.device = null; st.ch = null; await verbinden(true); status("verbunden: " + (st.device.name || "Drucker")); }
    catch (e) { if (!e || e.name !== "NotFoundError") alert("Keine Verbindung: " + (e.message || e)); }
  });
  if (gemerkt()) status("Drucker: " + gemerkt());
})();
"""


def etiketten_html(eintraege, qr, h, format_="70x74", mass=(70, 74)):
    """eintraege: [{titel, zeilen:[...], qr_text, klein}] → druckfertige Seite."""
    if format_ == "a4":
        css = ("@page{size:A4;margin:8mm 0 0 0}body{margin:0;font-family:Arial,Helvetica,sans-serif}"
               ".bogen{display:grid;grid-template-columns:repeat(3,70mm);grid-auto-rows:37mm;width:210mm}"
               ".et{box-sizing:border-box;padding:2.5mm 3mm;display:flex;gap:2mm;overflow:hidden;break-inside:avoid}"
               ".et .q svg{width:24mm;height:24mm}.et .t{font-size:8pt;line-height:1.25;min-width:0}.et .n{font-size:13pt;font-weight:700}"
               ".et .b{font-weight:600;font-size:8.5pt}")
        inhalt = '<div class="bogen">' + "".join(
            f'<div class="et"><div class="q">{qr(e["qr_text"])}</div><div class="t"><div class="n">{h(e["titel"])}</div>'
            + "".join(f'<div class="{"b" if i == 0 else ""}">{h(z)}</div>' for i, z in enumerate(e["zeilen"])) + "</div></div>"
            for e in eintraege) + "</div>"
    else:
        # Entwurf 70 × 74 mm; andere Etikettengrößen: Inhalt als Ganzes skalieren und mittig setzen
        bw, bh = mass
        k = min(bw / 70, bh / 74)
        css = (f"@page{{size:{bw}mm {bh}mm;margin:0}}body{{margin:0;font-family:Arial,Helvetica,sans-serif}}"
               f".rahmen{{width:{bw}mm;height:{bh}mm;position:relative;overflow:hidden;break-after:page}}.rahmen:last-child{{break-after:auto}}"
               f".et{{width:70mm;height:74mm;box-sizing:border-box;padding:4mm;display:flex;flex-direction:column;gap:2mm;overflow:hidden;"
               f"position:absolute;left:{round((bw - 70 * k) / 2, 2)}mm;top:{round((bh - 74 * k) / 2, 2)}mm;transform:scale({round(k, 4)});transform-origin:0 0}}"
               ".et .n{font-size:20pt;font-weight:700}.et .b{font-size:11pt;font-weight:600;line-height:1.2}"
               ".et .z{font-size:9.5pt}.et .q{margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end}"
               ".et .q svg{width:30mm;height:30mm}.et .k{font-size:7pt;color:#444;max-width:34mm}")
        inhalt = "".join(
            f'<div class="rahmen"><div class="et"><div class="n">{h(e["titel"])}</div>'
            + "".join(f'<div class="{"b" if i == 0 else "z"}">{h(z)}</div>' for i, z in enumerate(e["zeilen"]))
            + f'<div class="q"><div class="k">{h(e.get("klein") or "")}</div>{qr(e["qr_text"])}</div></div></div>' for e in eintraege)
    zebra = format_ != "a4"
    leiste = ('<div class="leiste" style="font:14px system-ui;background:#3b3530;color:#fff;padding:8px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">'
              f'<b>{len(eintraege)} Etikett{"en" if len(eintraege) != 1 else ""}</b><span id="zst" style="opacity:.85"></span><span style="flex:1"></span>'
              + ('<button id="zwahl" class="lb" style="background:#5a514a" hidden>Anderen Drucker wählen</button>'
                 '<button id="zdruck" class="lb">Auf Zebra drucken (Bluetooth)</button>' if zebra else "")
              + '<button onclick="window.print()" class="lb">Drucken</button></div>'
              '<style>.lb{font:inherit;padding:4px 12px;border:0;border-radius:5px;background:#b8834f;color:#fff;cursor:pointer}.lb:disabled{opacity:.5}'
              '@media print{.leiste{display:none}}@media screen{body{background:#999}.bogen .et,.rahmen{background:#fff;margin:6px auto;box-shadow:0 1px 6px rgba(0,0,0,.3)}.bogen{background:#fff;margin:6px auto}}</style>')
    if zebra:
        svgs = [etikett_svg(e, qr, mass) for e in eintraege]
        leiste += (f"<script>window.ETIKETT={{w:{mass[0]},h:{mass[1]}}};</script>" +'<script type="application/json" id="zsvgs">' + json.dumps(svgs).replace("</", "<\\/") + "</script>"
                   "<script>" + ZEBRA_JS + "</script>")
    return f'<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Etiketten</title><style>{css}</style></head><body>{leiste}{inhalt}</body></html>'


# ---------------------------------------------------------------- Beschaffung (wie im Zuschnittprogramm)
def mkey(material, dicke, laenge, breite):
    def z(x):
        x = _zahl(x)
        return int(x) if x == int(x) else x
    return "|".join([material or "ohne Material", str(z(dicke)), str(z(laenge)), str(z(breite))])


def beschaffung(lager):
    """Reservierte Platten, die im Lager fehlen: reserviert − Bestand − bestellt."""
    karte = {}
    for job, r in (lager.get("reservations") or {}).items():
        for k, n in (r.get("mats") or {}).items():
            if not (_zahl(n) > 0):
                continue
            e = karte.setdefault(k, {"key": k, "reserviert": 0, "auftraege": []})
            e["reserviert"] += int(_zahl(n))
            e["auftraege"].append({"projekt": r.get("project") or "", "nr": r.get("nr") or "", "auftrag_id": r.get("auftrag"), "anzahl": int(_zahl(n))})
    for k in (lager.get("orders") or {}):
        karte.setdefault(k, {"key": k, "reserviert": 0, "auftraege": []})
    aus = []
    for k, e in karte.items():
        teile = (k.split("|") + ["", "", "", ""])[:4]
        it = next((i for i in lager.get("items", []) if i.get("kind") == "platte"
                   and mkey(i.get("material"), i.get("thickness"), i.get("length"), i.get("width")) == k), None)
        bestellt = int(_zahl(((lager.get("orders") or {}).get(k) or {}).get("qty")))
        bestand = int(_zahl(it.get("qty"))) if it else 0
        fehlt = max(0, e["reserviert"] - bestand)
        aus.append({**e, "material": teile[0], "dicke": _zahl(teile[1]), "laenge": _zahl(teile[2]), "breite": _zahl(teile[3]),
                    "bestand": bestand, "bestellt": bestellt, "fehlt": fehlt, "zu_bestellen": max(0, fehlt - bestellt),
                    "bestellt_am": ((lager.get("orders") or {}).get(k) or {}).get("date")})
    return sorted([x for x in aus if x["fehlt"] > 0 or x["bestellt"] > 0], key=lambda x: (-x["zu_bestellen"], x["material"]))


def bestellung(con, d, wer):
    k, n = d.get("key") or "", max(0, int(_zahl(d.get("menge"))))

    def fn(lager):
        lager.setdefault("orders", {})
        if n > 0:
            lager["orders"][k] = {"qty": n, "date": datetime.now().isoformat()}
        else:
            lager["orders"].pop(k, None)
    return _aendern(con, wer, fn, f"{n} Platten {k.split('|')[0]} bestellt" if n else f"Bestellung {k.split('|')[0]} gelöscht")


def wareneingang(con, d, wer):
    k, n = d.get("key") or "", max(0, int(_zahl(d.get("menge"))))
    if not n:
        raise Fehler("Bitte die Anzahl angeben.")
    teile = (k.split("|") + ["", "", "", ""])[:4]

    def fn(lager):
        it = next((i for i in lager["items"] if i.get("kind") == "platte"
                   and mkey(i.get("material"), i.get("thickness"), i.get("length"), i.get("width")) == k), None)
        if not it:
            it = {"id": "p" + secrets.token_hex(5), "kind": "platte", "material": teile[0], "thickness": _zahl(teile[1]),
                  "length": _zahl(teile[2]), "width": _zahl(teile[3]), "qty": 0, "location": ""}
            lager["items"].append(it)
        it["qty"] = int(_zahl(it.get("qty"))) + n
        o = (lager.get("orders") or {}).get(k)
        if o:
            o["qty"] = int(_zahl(o.get("qty"))) - n
            if o["qty"] <= 0:
                lager["orders"].pop(k, None)
    return _aendern(con, wer, fn, f"Wareneingang: {n} Platten {teile[0]}")


# ---------------------------------------------------------------- Stückzahl ganzer Platten ↔ Lagerbestand (m²)
_IM_SPEICHERN = [0]


def ist_platte(m):
    """Nur Platten und Leimholz gehören ins Plattenlager des Zuschnitts (keine Kanten, Furniere, Sonstiges, keine lfm)."""
    if (m.get("kategorie") or "") != "holzwerkstoffe":
        return False
    if (m.get("gruppe") or "").strip().lower() not in ("", "platten", "platte", "leimholz"):
        return False
    return (m.get("einheit") or "").lower().replace(" ", "") not in ("lfm", "lfm.", "m", "rolle")


def platten_faktor(m):
    """Bestandsmenge je ganzer Platte: m² → Plattenfläche, Stück → 1; sonst None (nicht verknüpfbar)."""
    if not ist_platte(m):
        return None
    L, B = _zahl(m.get("plattenlaenge")), _zahl(m.get("plattenbreite"))
    if not (L > 0 and B > 0):
        return None
    e = (m.get("einheit") or "").lower().replace(" ", "")
    if e in ("m²", "m2", "qm"):
        return L * B / 1e6
    if e.startswith(("stk", "st.", "platte", "tafel")):
        return 1.0
    return None


def platten_im_bestand(bestand, faktor):
    return max(0, int(_zahl(bestand) / faktor + 1e-6)) if faktor else 0


def _gruppen(con, lager):
    """Ganze Platten im Zuschnittlager den Holzwerkstoffen im Materialstamm zuordnen: {material_id: (m, faktor, [items])}."""
    try:
        stamm = [dict(r) for r in con.execute(
            "SELECT * FROM material WHERE aktiv=1 AND kategorie='holzwerkstoffe' AND plattenlaenge>0 AND plattenbreite>0")]
    except Exception:
        return {}
    nach_nr = {(m.get("nummer") or "").lower(): m for m in stamm}
    gr = {}
    for it in lager.get("items", []):
        if it.get("kind") != "platte":
            continue
        m = nach_nr.get((it.get("materialNr") or "").lower()) if it.get("materialNr") else None
        if not m:
            m = material_finden(con, it.get("material"), it.get("thickness"), it.get("length"), it.get("width"))
        if not m:
            continue
        f = platten_faktor(m)
        if not f:
            continue
        ml, mb = sorted((_zahl(m.get("plattenlaenge")), _zahl(m.get("plattenbreite"))), reverse=True)
        il, ib = sorted((_zahl(it.get("length")), _zahl(it.get("width"))), reverse=True)
        if abs(ml - il) > 2 or abs(mb - ib) > 2:
            continue
        if m.get("dicke") and it.get("thickness") and abs(_zahl(m["dicke"]) - _zahl(it["thickness"])) > 0.6:
            continue
        gr.setdefault(m["id"], (m, f, []))[2].append(it)
    return gr


def stueck_aus_bestand(con, lager):
    """Stückzahl der ganzen Platten aus dem Lagerbestand des Materialstamms setzen. True, wenn sich etwas geändert hat."""
    geaendert = False
    for mid, (m, f, items) in _gruppen(con, lager).items():
        bestand = con.execute("SELECT bestand FROM material WHERE id=?", (mid,)).fetchone()["bestand"]
        soll = platten_im_bestand(bestand, f)
        ist = sum(int(_zahl(i.get("qty"))) for i in items)
        if soll == ist:
            continue
        rest = soll
        for i, it in enumerate(items):          # vorhandene Verteilung möglichst behalten, Differenz beim ersten Eintrag
            q = int(_zahl(it.get("qty")))
            q = min(q, rest) if i else q
            it["qty"] = q
            rest -= q
        items[0]["qty"] = int(_zahl(items[0].get("qty"))) + rest
        if items[0]["qty"] < 0:
            items[0]["qty"] = 0
        geaendert = True
    return geaendert


def bestand_nachziehen(con, lager, text="Abgleich mit dem Plattenlager des Zuschnitts"):
    """Stückzahl im Zuschnittlager weicht vom Bestand ab (z. B. +1/−1, Wareneingang, Platte ohne Auftrag entnommen):
    Differenz als Lagerzugang bzw. -abgang im Materialstamm buchen."""
    buchen = HILFE.get("lagerbuchung")
    if not buchen:
        return 0
    n = 0
    for mid, (m, f, items) in _gruppen(con, lager).items():
        bestand = con.execute("SELECT bestand FROM material WHERE id=?", (mid,)).fetchone()["bestand"]
        diff = sum(int(_zahl(i.get("qty"))) for i in items) - platten_im_bestand(bestand, f)
        if diff:
            buchen(con, mid, round(diff * f, 4), f"{text}: {'+' if diff > 0 else ''}{diff} Platte{'n' if abs(diff) != 1 else ''}")
            n += 1
    return n


def stueck_abgleich(con, wer):
    """Lager für das Zuschnittprogramm vorbereiten: Plattenformate ergänzen und Stückzahl aus dem Bestand setzen.
    Beim ersten Mal gilt eine im Zuschnitt gezählte Stückzahl (> 0) und der Bestand wird angeglichen."""
    lager, rev = laden(con)
    neu = formate_ergaenzen(con, lager)
    _IM_SPEICHERN[0] += 1
    try:
        erst = not lager.get("stueckSync")
        if erst:
            for mid, (m, f, items) in _gruppen(con, lager).items():
                if sum(int(_zahl(i.get("qty"))) for i in items) > 0:
                    bestand_nachziehen(con, {"items": items}, "Übernahme der Stückzahl aus dem Zuschnittlager")
            lager["stueckSync"] = True
        geaendert = stueck_aus_bestand(con, lager)
    finally:
        _IM_SPEICHERN[0] -= 1
    if erst or geaendert or neu:
        rev = _schreiben(con, lager, rev, wer)
    return lager, rev


def bestand_geaendert(con, mid, wer="Jahresring"):
    """Rückruf aus dem Materialstamm: Lagerbestand eines Holzwerkstoffs geändert → Stückzahl im Zuschnittlager nachführen."""
    if _IM_SPEICHERN[0]:
        return
    m = con.execute("SELECT * FROM material WHERE id=?", (mid,)).fetchone()
    if not m or not platten_faktor(dict(m)):
        return
    lager, rev = laden(con)
    if not lager.get("stueckSync"):
        return
    if stueck_aus_bestand(con, lager):
        lager["log"] = ([{"t": datetime.now().isoformat(), "msg": f"Bestand {m['nummer']} im Büro geändert"}] + (lager.get("log") or []))[:200]
        _schreiben(con, lager, rev, wer)


# ---------------------------------------------------------------- Ganze Platten → Materialstamm und Auftragskosten
def formate_ergaenzen(con, lager):
    """Holzwerkstoffe mit Plattenformat (Länge × Breite) aus dem Materialstamm als ganze Platten ins Lager des
    Zuschnittprogramms übernehmen, damit es passende Platten findet. Bestehende Einträge bleiben unverändert;
    der Bestand wird nur beim ersten Übernehmen aus dem Lagerbestand (Einheit Stück/Platte) vorbelegt."""
    try:
        stamm = [dict(r) for r in con.execute(
            "SELECT * FROM material WHERE aktiv=1 AND kategorie='holzwerkstoffe' AND plattenlaenge>0 AND plattenbreite>0")]
    except Exception:
        return 0
    neu = 0
    # Einträge zu Kanten, Furnieren u. ä., die früher übernommen wurden, wieder entfernen (nur unbenutzte mit 0 Stück)
    weg = {(m.get("nummer") or "").lower() for m in stamm if not ist_platte(m)}
    benutzt = {e.get("item") for e in (lager.get("bookings") or {}).values()}
    vorher = len(lager.get("items", []))
    lager["items"] = [i for i in lager.get("items", []) if not (
        i.get("kind") == "platte" and (i.get("materialNr") or "").lower() in weg and not int(_zahl(i.get("qty")))
        and i.get("id") not in benutzt)]
    neu += vorher - len(lager["items"])
    for m in stamm:
        if not ist_platte(m):
            continue
        name = (m.get("cad") or (m.get("bezeichnung") or "").split("\n")[0] or m.get("nummer") or "").strip()
        if not name:
            continue
        L, B, D = _zahl(m["plattenlaenge"]), _zahl(m["plattenbreite"]), _zahl(m.get("dicke"))
        k = mkey(name, D, L, B)
        if any(i.get("kind") == "platte" and mkey(i.get("material"), i.get("thickness"), i.get("length"), i.get("width")) == k
               for i in lager.get("items", [])):
            continue
        stueck = (m.get("einheit") or "").lower().startswith(("stk", "st.", "platte", "tafel"))
        lager["items"].append({"id": "p" + secrets.token_hex(5), "kind": "platte", "material": name, "thickness": D,
                               "length": L, "width": B, "qty": int(_zahl(m.get("bestand"))) if stueck and m.get("lager") else 0,
                               "location": m.get("lagerort") or "", "materialNr": m.get("nummer") or ""})
        neu += 1
    return neu


def material_finden(con, name, dicke, laenge=0, breite=0):
    """Materialstamm-Eintrag zum Plattenmaterial aus dem CAD: CAD-Kürzel, Nummer, Bezeichnung (passende Dicke bevorzugt)."""
    n = (name or "").strip().lower()
    if not n:
        return None
    kand = [dict(r) for r in con.execute(
        "SELECT * FROM material WHERE aktiv=1 AND kategorie IN ('holzwerkstoffe','massivholz') AND "
        "(ulower(IFNULL(cad,''))=? OR ulower(nummer)=? OR ulower(bezeichnung)=? OR ulower(bezeichnung) LIKE ?)", (n, n, n, n + "%"))]
    if not kand:
        return None
    d = _zahl(dicke)

    L, B = sorted((_zahl(laenge), _zahl(breite)), reverse=True)

    def format_passt(m):
        ml, mb = sorted((_zahl(m.get("plattenlaenge")), _zahl(m.get("plattenbreite"))), reverse=True)
        if not (L and ml):
            return 1        # unbekannt: zwischen passend und unpassend
        return 0 if abs(ml - L) <= 2 and abs(mb - B) <= 2 else 2

    def rang(m):
        return ((m.get("cad") or "").lower() != n, abs(_zahl(m.get("dicke")) - d) > 0.6 if d and m.get("dicke") else False,
                format_passt(m), (m.get("nummer") or "").lower() != n)
    return sorted(kand, key=rang)[0]


def buchungen_abgleichen(con, alt, neu, buchen, stornieren):
    """Neue Plattenbuchungen (ganze Platte aus dem Bestand, mit Auftrag) als Lagerabgang + Auftragskosten buchen,
    zurückgenommene wieder stornieren. buchen(auftrag_id, material, menge, text) → ak_id; stornieren(ak_id)."""
    erg = {"gebucht": 0, "storniert": 0, "ohne_material": []}
    alt_b, neu_b = (alt or {}).get("bookings") or {}, (neu or {}).get("bookings") or {}
    items = {i.get("id"): i for i in ((alt or {}).get("items") or []) + ((neu or {}).get("items") or [])}
    for k, e in neu_b.items():
        if k in alt_b or not e.get("item") or not e.get("auftrag"):
            continue
        if con.execute("SELECT 1 FROM zuschnitt_buchungen WHERE schluessel=?", (k,)).fetchone():
            continue
        it = items.get(e["item"]) or {}
        m = material_finden(con, it.get("material"), it.get("thickness"), it.get("length"), it.get("width"))
        flaeche = _zahl(it.get("length")) * _zahl(it.get("width")) / 1e6
        if not m:
            con.execute("INSERT INTO zuschnitt_buchungen (schluessel, auftrag_id, menge, hinweis, angelegt) VALUES (?,?,?,?,?)",
                        (k, int(e["auftrag"]), 1, f"kein Material „{it.get('material')}“ im Materialstamm", jetzt()))
            erg["ohne_material"].append(it.get("material") or "")
            continue
        einheit = (m.get("einheit") or "").lower()
        menge = round(flaeche, 4) if einheit.startswith("m²") or einheit == "m2" else (
            round(flaeche * _zahl(it.get("thickness")) / 1000, 5) if einheit.startswith("m³") else 1)
        text = f"Zuschnitt {e.get('project') or ''}: 1 Platte {_zahl(it.get('length')):.0f} × {_zahl(it.get('width')):.0f} mm"
        ak = buchen(int(e["auftrag"]), m, menge, text)
        con.execute("INSERT INTO zuschnitt_buchungen (schluessel, auftrag_id, material_id, ak_id, menge, angelegt) VALUES (?,?,?,?,?,?)",
                    (k, int(e["auftrag"]), m["id"], ak, menge, jetzt()))
        erg["gebucht"] += 1
    for k in alt_b:
        if k in neu_b:
            continue
        r = con.execute("SELECT * FROM zuschnitt_buchungen WHERE schluessel=?", (k,)).fetchone()
        if r:
            if r["ak_id"]:
                stornieren(r["ak_id"])
            con.execute("DELETE FROM zuschnitt_buchungen WHERE schluessel=?", (k,))
            erg["storniert"] += 1
    return erg
