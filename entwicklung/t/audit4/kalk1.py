"""Rechenproben: Bruttoanzeige, Rundung im Beleg, unabhängige Nachrechnung einer Position."""
import json, re, sys, time, os
sys.path.insert(0, "/home/claude/eberle-buero")
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None):
    s, b, hd = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    return j
def text(bid):
    s, t, _ = rq(inh, "GET", f"/druck/{bid}"); t = re.sub(r"<(style|script).*?</\1>", "", t, flags=re.S); t = re.sub(r"<[^>]+>", " ", t); return re.sub(r"\s+", " ", t.replace("&nbsp;", " ").replace("\xa0", " "))
def beleg(kunde, pos, art="angebot", **kw):
    a = A("POST", "auftraege", {"kunde_id": kunde["id"], "bezeichnung": "Rechenprobe"})
    for txt, menge, ep in pos:
        po = A("POST", f"auftraege/{a['id']}/positionen", {"text": txt}); pid = po.get("id") or po["position"]["id"]; A("PUT", f"positionen/{pid}", {"einzelpreis": ep, "preis_manuell": 1, "menge": menge})
    b = A("POST", f"auftraege/{a['id']}/belege", {"art": art}); 
    if kw: A("PUT", f"belege/{b['id']}", kw)
    return A("GET", f"belege/{b['id']}")
print("== 1. Bruttoanzeige (Privatkunde): Summe der gedruckten Zeilen gegen gedruckte Endsumme")
kb = A("POST", "kunden", {"kurzname": "Brutto, Berta", "nachname": "Brutto", "plz": "88069", "ort": "Tettnang", "preise": "brutto"})
b = beleg(kb, [("Brett A", 1, 8.40), ("Brett B", 1, 8.40), ("Brett C", 1, 8.40)])
t = text(b["id"]); zahlen = re.findall(r"\d[\d.]*,\d\d", t)
print("  Summen laut Programm:", {k_: b["daten"]["summen"].get(k_) for k_ in ("netto_positionen", "netto", "ust", "brutto")}, "| brutto_anzeige:", b["daten"].get("brutto_anzeige"))
print("  gedruckte Beträge:", zahlen[:14])
print("  Ausschnitt:", t[t.find("Brett A") - 40: t.find("Brett A") + 420])
print("\n== 2. Rundung im Beleg")
kn = A("POST", "kunden", {"kurzname": "Netto GmbH", "firma": "Netto GmbH", "plz": "88069", "ort": "Tettnang"})
for pos, erwartet in (([("Arbeit", 0.5, 4764.83)], "0,5 × 4.764,83 = 2.382,415 → kaufmännisch 2.382,42"), ([("Kleinteil", 1, 2.50)], "USt auf 2,50 = 0,475 → kaufmännisch 0,48; brutto 2,98"), ([("Platte", 1.5, 231.69)], "1,5 × 231,69 = 347,535 → 347,54"), ([("Teil", 3, 0.335)], "EP 0,335 → ?")):
    b = beleg(kn, pos); s = b["daten"]["summen"]; z = [x for x in b["daten"]["zeilen"] if x.get("typ") == "pos"]
    print("  %-62s Programm: EP %s GP %s | netto %s USt %s brutto %s" % (erwartet, z[0].get("ep"), z[0].get("gp"), s["netto"], s["ust"], s["brutto"]))
print("\n== 3. Rabatt und Skonto")
b = beleg(kn, [("Schrank", 1, 1999.99), ("Montage", 3.25, 58.35)], rabatt_pz=7.5)
s = b["daten"]["summen"]; print("  Summen:", s); t = text(b["id"]); print("  Skonto/Zahlung im Druck:", re.findall(r"[^.]*Skonto[^.]*\.", t)[:2])
import kalkulation as K
print("\n== 4. Unabhängige Nachrechnung einer kalkulierten Position")
kalk = {"werkstoffe": [{"k": "P1", "name": "Eiche furniert 19", "preis": 40.0, "v": 20, "einheit": "m²", "art": "platte"}], "beschlaege": [{"k": "B1", "name": "Topfband", "preis": 3.5, "einheit": "Stk."}],
        "kleinmaterial": 3, "gk_material": 10, "wg": 15, "lohnbasis": "Geselle", "loehne": [{"gruppe": "Geselle", "lohn": 25.0}], "kostenstellen": [{"kst": "BANKRAUM", "gk": 120}]}
pos = {"menge": 2, "stueckliste": [{"werkstoff": "P1", "laenge": 2000, "breite": 600, "stueck": 1}], "beschlaege": [{"k": "B1", "menge": 4}], "zeitmodus": "stunden", "zeiten": [{"kst": "BANKRAUM", "stunden": 2, "gruppe": "Geselle"}], "extras": {}}
r = K.position_rechnen(pos, kalk)
soll = {"werkstoffe": 1.2 * 40 * 1.2, "beschlaege": 14.0}; soll["kleinmaterial"] = (soll["werkstoffe"] + 14) * 0.03; soll["material"] = soll["werkstoffe"] + 14 + soll["kleinmaterial"]; soll["gk_material"] = soll["material"] * 0.10
soll["lohn"] = 50.0; soll["gk_lohn"] = 60.0; soll["selbstkosten"] = soll["material"] + soll["gk_material"] + 110; soll["wg"] = soll["selbstkosten"] * 0.15; soll["einzelpreis"] = round(soll["selbstkosten"] * 1.15, 2); soll["gesamtpreis"] = round(soll["einzelpreis"] * 2, 2)
for k_ in soll: print("  %-14s Soll %10.4f  Programm %10.4f  %s" % (k_, soll[k_], r[k_], "ok" if abs(soll[k_] - r[k_]) < 0.005 else "ABWEICHUNG"))
print("  Warnungen:", r["warnungen"])
print("\n== 5. Zahlen als Text mit Komma in der Kalkulation (f() → 0?)")
for wert in ("12,5", "1.234,56", " 40 ", "40 €", "1e3", "inf", "nan", None, "", "-5"):
    k2 = json.loads(json.dumps(kalk)); k2["werkstoffe"][0]["preis"] = wert
    try: r2 = K.position_rechnen(pos, k2); print("  Werkstoffpreis %-10r → Werkstoffe %s, EP %s, Warnungen %s" % (wert, r2["werkstoffe"], r2["einzelpreis"], r2["warnungen"][:1]))
    except Exception as x: print("  Werkstoffpreis %-10r → FEHLER %s" % (wert, x))
