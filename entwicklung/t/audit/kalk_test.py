import sys, copy, math
sys.path.insert(0, "/home/claude/eberle-buero")
import kalkulation as K
f = K.f
fehler = []
def gleich(name, ist, soll, tol=0.005):
    if abs((ist or 0) - soll) > tol:
        fehler.append(f"{name}: ist {ist} soll {soll}")
kalk = copy.deepcopy(K.KALK_VORGABEN)
kalk["werkstoffe"] = [
    {"k": "SPAN19", "name": "Span 19", "typ": "platte", "einheit": "m²", "preis": 10.0, "v": 20, "dicke": 19},
    {"k": "EI-M", "name": "Eiche massiv", "typ": "massiv", "einheit": "m³", "preis": 2000.0, "v": 50, "dicke": 30},
    {"k": "KANTE", "name": "Kante", "typ": "kante", "einheit": "lfm", "preis": 1.0, "v": 10},
    {"k": "LACK", "name": "Lack", "typ": "oberflaeche", "einheit": "m²", "preis": 5.0, "v": 0},
]
kalk["beschlaege"] = [{"k": "SCHARN", "name": "Scharnier", "preis": 3.5, "einheit": "Stk."}]
kalk["kleinmaterial"], kalk["gk_material"], kalk["wg"] = 15.0, 30.0, 15.0
kalk["loehne"] = [{"gruppe": "Durchschnitt", "lohn": 27.0}, {"gruppe": "Meister", "lohn": 40.0}]
kalk["lohnbasis"] = "Durchschnitt"
gkk = {k["kst"]: f(k["gk"]) for k in kalk["kostenstellen"]}
kst1, kst2 = list(gkk)[:2]

# 1) Stückliste Platte mit Kante und Lack
pos = {"menge": 2, "stueckliste": [{"werkstoff": "SPAN19", "laenge": 1000, "breite": 500, "stueck": 2,
        "kanten": {"oben": "KANTE"}, "oberflaeche": {"oben": "LACK"}}], "beschlaege": [{"k": "SCHARN", "menge": 4}],
       "zeitmodus": "stunden", "zeiten": [{"kst": kst1, "stunden": 2}, {"kst": kst2, "stunden": 1, "gruppe": "Meister"}],
       "extras": {"kostenliste": [{"art": "werkstoffe", "menge": 2, "preis": 10}, {"art": "fremdleistungen", "menge": 1, "preis": 100},
                                  {"art": "zukauf", "menge": "", "preis": 200}, {"art": "sonder_fertigung", "menge": 1, "preis": 30},
                                  {"art": "sonder_vertrieb", "menge": 1, "preis": 20}]}}
c = K.position_rechnen(pos, kalk)
platte = 0.5 * 10 * 1.2 * 2          # 1 m × 0,5 m, +20 % Verschnitt, 2 Stück
kante = 1.0 * 1.0 * 1.1 * 2
lack_f = 0.5 * 5 * 2
schmal = 2 * (1 + 0.5) * 19 / 1000 * 5 * 2
werk = platte + kante + 20          # Kante zählt als Werkstoff? prüfen unten
print("Werkstoffe", c["werkstoffe"], "Oberfläche", c["oberflaeche"], "Beschläge", c["beschlaege"])
gleich("Beschläge", c["beschlaege"], 14)
gleich("Oberfläche", c["oberflaeche"], lack_f + schmal)
gleich("Werkstoffe", c["werkstoffe"], platte + kante + 20)
klein = (c["werkstoffe"] + c["beschlaege"] + c["oberflaeche"]) * 0.15
gleich("Kleinmaterial", c["kleinmaterial"], klein)
mat = c["werkstoffe"] + c["beschlaege"] + c["oberflaeche"] + klein + 100 + 200
gleich("Material", c["material"], mat)
gleich("GK Material", c["gk_material"], mat * 0.30)
lohn = 2 * 27 + 1 * 40
gleich("Lohn", c["lohn"], lohn)
gk_l = 2 * 27 * gkk[kst1] / 100 + 40 * gkk[kst2] / 100
gleich("GK Lohn", c["gk_lohn"], gk_l)
sk = mat * 1.3 + lohn + gk_l + 30
gleich("Selbstkosten", c["selbstkosten"], sk)
gleich("Einzelpreis", c["einzelpreis"], round(sk * 1.15 + 20, 2))
gleich("Gesamtpreis", c["gesamtpreis"], round(round(sk * 1.15 + 20, 2) * 2, 2))
gleich("SoKo V", c["sonder_vertrieb"], 20)
# 2) fester Preis
p2 = copy.deepcopy(pos); p2["preis_manuell"] = 1; p2["einzelpreis"] = 2000
c2 = K.position_rechnen(p2, kalk)
gleich("fest EP", c2["einzelpreis"], 2000); gleich("fest WG", c2["wg"], 2000 - sk - 20); gleich("fest WG%", c2["wg_pz"], (2000 - sk - 20) / sk * 100)
# 3) eigener W+G
p3 = copy.deepcopy(pos); p3["extras"]["wg"] = 25
gleich("WG 25 EP", K.position_rechnen(p3, kalk)["einzelpreis"], round(sk * 1.25 + 20, 2))
# 4) Unterpositionen
k1 = {"menge": 2, "extras": {"kostenliste": [{"art": "zukauf", "menge": 1, "preis": 100}]}}
k2 = {"menge": 1, "einzelpreis": 50, "preis_manuell": 1}
k3 = {"menge": 1, "gesperrt": 1, "extras": {"kostenliste": [{"art": "zukauf", "menge": 1, "preis": 999}]}}
kinder = []
for k in (k1, k2, k3):
    ck = K.position_rechnen(k, kalk); k["_calc"] = ck; k["_ep_gesamt"] = ck["ep_gesamt"]; k["_kosten_gesamt"] = ck["kosten_gesamt"]; kinder.append(k)
h = {"menge": 3, "extras": {"kostenliste": [{"art": "werkstoffe", "menge": 1, "preis": 10}]}}
ch = K.position_rechnen(h, kalk, kinder)
ep_k1 = round(100 * 1.3 * 1.15, 2)
gleich("Unter EP", ch["unter_ep"], 2 * ep_k1 + 50)
own = round(10 * 1.15 * 1.3 * 1.15, 2)
gleich("Haupt EP gesamt", ch["ep_gesamt"], round(own + 2 * ep_k1 + 50, 2))
gleich("Haupt Gesamtpreis", ch["gesamtpreis"], round(round(own + 2 * ep_k1 + 50, 2) * 3, 2))
gleich("unter_kat zukauf", ch["unter_kat"]["zukauf"], 200)
gleich("kosten_gesamt", ch["kosten_gesamt"], 10 * 1.15 * 1.3 + 2 * 130)
# 5) Massivholz
p5 = {"menge": 1, "stueckliste": [{"werkstoff": "EI-M", "laenge": 2000, "breite": 100, "stueck": 1}]}
gleich("Massiv", K.position_rechnen(p5, kalk)["werkstoffe"], 2 * 0.1 * 30 / 1000 * 2000 * 1.5)
# 6) leere Stückzahl = 1, Menge 0
p6 = {"menge": 0, "stueckliste": [{"werkstoff": "SPAN19", "laenge": 1000, "breite": 1000, "stueck": ""}]}
c6 = K.position_rechnen(p6, kalk); gleich("Stk leer", c6["werkstoffe"], 12); gleich("Menge 0 Gesamt", c6["gesamtpreis"], 0)
# 7) Altfelder
p7 = {"menge": 1, "extras": {"zukauf": 100, "fremdleistungen": 50, "sonder_fertigung": 10, "sonder_vertrieb": 5}}
c7 = K.position_rechnen(p7, kalk)
gleich("Alt SK", c7["selbstkosten"], 150 * 1.3 + 10); gleich("Alt EP", c7["einzelpreis"], round((150 * 1.3 + 10) * 1.15 + 5, 2))
# 8) Tätigkeiten mit Rüstzeit und Helfer
p8 = {"menge": 4, "zeitmodus": "taetigkeiten", "zeiten": [{"kst": kst1, "minuten": 30, "ruest": 60, "helfer": 0.5}]}
c8 = K.position_rechnen(p8, kalk)
h_anz = (30 + 60 / 4) / 60
print("T8 stunden je Anz", c8["stunden"], "Helfer", c8["zeit_summen"])
gleich("Tätigkeit Bearb.+Rüst h", c8["zeit_summen"]["gesamt_pos"], 30 * 4 / 60 + 1 + 30 * 0.5 * 4 / 60)   # Helfer nur auf Bearbeitung
# Menge 0 bei Bezugsgröße: Zeile entfällt samt Rüstzeit und Helfer; ohne Bezugsgröße zählt sie
p9 = {"menge": 2, "zeitmodus": "taetigkeiten", "zeiten": [{"kst": kst1, "minuten": 5, "bezug": "beschlaege", "ruest": 10, "helfer": 1},
                                                          {"kst": kst1, "minuten": 45, "bezug": "", "ruest": 6, "helfer": 0}]}
c9 = K.position_rechnen(p9, kalk)
print("T9", c9["zeit_summen"])
gleich("Menge 0 ohne Rüstzeit", c9["zeit_summen"]["gesamt_pos"], 45 * 2 / 60 + 6 / 60)
# Beschlägeliste: leere Zeile (kein Beschlag, keine Bemerkung) zählt nicht für die Bezugsgröße „Beschläge – St.“
zt = [{"kst": kst1, "minuten": 6, "bezug": "beschlaege", "ruest": 12, "helfer": 0}]
c10 = K.position_rechnen({"menge": 1, "zeitmodus": "taetigkeiten", "zeiten": zt, "beschlaege": [{"k": "", "menge": 23, "bemerkung": ""}]}, kalk)
gleich("leere Beschlagzeile: keine Arbeitszeit", c10["zeit_summen"]["gesamt_pos"], 0)
c11 = K.position_rechnen({"menge": 1, "zeitmodus": "taetigkeiten", "zeiten": zt, "beschlaege": [{"k": "", "menge": 23, "bemerkung": ""}, {"k": "SCHARN", "menge": 4}, {"k": "", "menge": 2, "bemerkung": "bauseits"}]}, kalk)
gleich("Beschlag gewählt oder Bemerkung: zählt", c11["zeit_summen"]["gesamt_pos"], 6 * 6 / 60 + 12 / 60)
gleich("Beschlagkosten unverändert", c11["beschlaege"], 4 * 3.5)
print("FEHLER:" if fehler else "alles stimmt", fehler if fehler else "")
