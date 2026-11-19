import sys, time, random
sys.path.insert(0, "/home/claude/eberle-buero")
import bank
random.seed(7)
namen = ["Müller", "Schmid", "Maier", "Huber", "Wagner", "Bauer", "Fischer", "Weber", "Schwarz", "Keller", "Vogel", "Frank", "Lang", "Roth", "Beck", "Jung"]
ops = []
for i in range(2016):
    n = random.choice(namen) + str(i % 97)
    betrag = round(random.uniform(80, 9000), 2)
    ops.append({"id": i + 1, "nummer": f"RE-2026-{i + 1:04d}", "art": "Rechnung", "offen": betrag, "betrag": betrag, "datum": "2026-10-01", "faellig": "2026-10-15", "mahnkosten": 0.0,
                "kunde_id": i + 1, "beleg_id": i + 1, "skonto": 2.0 if i % 5 == 0 else 0, "skonto_bis": "2026-10-10" if i % 5 == 0 else "", "kurzname": n + ", Hans", "name": n, "firma": "", "vorname": "Hans"})
us = []
for j in range(1000):
    o = random.choice(ops)
    art = j % 5
    if art == 0: zweck, betrag = f"Rechnung {o['nummer']} vielen Dank", o["offen"]
    elif art == 1: zweck, betrag = f"RE {o['nummer'].replace('-', '')}", o["offen"]
    elif art == 2: zweck, betrag = "Danke fuer die Arbeit", o["offen"]
    elif art == 3: zweck, betrag = f"Miete {j} Kd 4711 Vertrag 99887766", round(random.uniform(50, 800), 2)
    else: zweck, betrag = f"Lastschrift Strom {j}", -round(random.uniform(30, 500), 2)
    us.append({"id": j + 1, "zweck": zweck, "e2e": "", "betrag": betrag, "name": o["name"] + " Hans", "gegen_iban": "DE02120300000000202051", "buchung": "2026-10-09", "status": "offen" if j % 5 < 3 or j % 10 == 3 or j % 10 == 4 else "zugeordnet", "rueck": 0})
offen = [u for u in us if u["status"] == "offen"]
print("offene Umsätze:", len(offen), "offene Posten:", len(ops))
zas = [{"id": i, "nummer": f"ZA-{i:05d}", "belegnr": f"LS-{i}", "betrag": round(random.uniform(20, 3000), 2), "skonto": 0, "skonto_bis": "", "faellig": "2026-10-20", "bezahlt": "", "iban": "", "lieferant": "L", "lief_iban": ""} for i in range(300)]
for runde in range(2):
    t0 = time.perf_counter()
    if hasattr(bank, "posten_vorbereiten"): bank.posten_vorbereiten(ops)
    erg = [bank.vorschlag(u, ops, zas, None, set(), []) for u in offen]
    t = time.perf_counter() - t0
    print(f"Lauf {runde + 1}: {t:.2f} s, Vorschläge: {sum(1 for e in erg if e)}, sicher: {sum(1 for e in erg if e and e['sicher'])}")
import json, hashlib
print("Fingerabdruck der Vorschläge:", hashlib.sha256(json.dumps(erg, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16])
