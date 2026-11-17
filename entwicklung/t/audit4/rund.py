"""Rundung: Programm (round auf float) gegen kaufmännische Rundung (Decimal, halb aufwärts)."""
import sys
from decimal import Decimal, ROUND_HALF_UP
sys.path.insert(0, "/home/claude/eberle-buero")
import importlib, types
def kfm(x, n=2): return Decimal(str(x)).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP)
def summen_rechnen(netto, ust_satz, rabatt_pz=0.0):   # wortgleich aus app.py
    rabatt = round(netto * rabatt_pz / 100, 2)
    netto_r = round(netto - rabatt, 2)
    ust = round(netto_r * ust_satz / 100, 2)
    return {"netto_positionen": round(netto, 2), "rabatt_pz": rabatt_pz, "rabatt": rabatt, "netto": netto_r, "ust_satz": ust_satz, "ust": ust, "brutto": round(netto_r + ust, 2)}
for satz in (19, 7):
    ab = []; halbe = 0
    for cent in range(1, 3_000_001):   # 0,01 € bis 30.000,00 €
        netto = cent / 100
        soll = (Decimal(cent) * satz / Decimal(10000)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ist = summen_rechnen(netto, satz)["ust"]
        if (cent * satz) % 100 == 50: halbe += 1
        if Decimal(str(ist)) != soll: ab.append((netto, ist, float(soll)))
    print(f"USt {satz} %: Nettobeträge 0,01–30.000,00 €: {halbe} Fälle genau auf halbem Cent, davon {len(ab)} anders als kaufmännisch gerundet ({len(ab) / 3_000_000 * 100:.3f} % aller Beträge)")
    print("   Beispiele (netto, Programm, kaufmännisch):", ab[:6], "…", ab[-2:])
    print("   Richtung:", sum(1 for a in ab if a[1] < a[2]), "zu niedrig,", sum(1 for a in ab if a[1] > a[2]), "zu hoch")
# Rabatt
ab = []
for cent in range(1, 500_001, 7):
    for pz in (2, 3, 5, 7.5, 10, 12.5, 15):
        netto = cent / 100; soll = (Decimal(cent) * Decimal(str(pz)) / Decimal(10000)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ist = summen_rechnen(netto, 19, pz)["rabatt"]
        if Decimal(str(ist)) != soll: ab.append((netto, pz, ist, float(soll)))
print("Rabatt: Abweichungen", len(ab), ab[:5])
# Positionssumme: Menge × EP
ab = []; n = 0
import random; random.seed(3)
for _ in range(400000):
    menge = random.choice([0.5, 1.5, 2.5, 0.25, 0.75, 1.25, 3.35, 2.45, 7.15, 12.345, 0.125, 1.005, 33.3]); ep = random.randint(1, 500000) / 100
    soll = (Decimal(str(menge)) * Decimal(str(ep))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP); ist = round(ep * menge, 2); n += 1
    if Decimal(str(ist)) != soll: ab.append((menge, ep, ist, float(soll)))
print(f"Gesamtpreis = round(EP × Menge, 2): {len(ab)} von {n} Zufallsfällen weichen um 1 Cent ab ({len(ab) / n * 100:.2f} %)", ab[:5])
print("Python-Beispiele: round(2.675,2) =", round(2.675, 2), "| round(1.005,2) =", round(1.005, 2), "| round(0.125,2) =", round(0.125, 2), "| round(0.375,2) =", round(0.375, 2), "| round(2.5*0.19,2) =", round(2.5 * 0.19, 2), "| round(102.5*19/100,2) =", round(102.5 * 19 / 100, 2))
