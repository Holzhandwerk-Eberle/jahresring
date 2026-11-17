import json, collections, re
d = json.load(open("/tmp/claude-0/t/audit4/ui_stil.json"))
C = collections.Counter
kn = [x for x in d if x["art"] == "knopf" and not x["imKopf"]]
print("Schaltflächen im Inhaltsbereich:", len(kn), "auf", len({x["route"] for x in kn}), "Seiten")
def sig(x): return (x["h"], x["fs"], x["fw"], x["rad"], x["ff"])
print("\n== nach Klasse: Anzahl und gemessene Varianten (Höhe, Schrift, Gewicht, Radius)")
nach = collections.defaultdict(list)
for x in kn: nach[x["kl"] or "(ohne Klasse)"].append(x)
for kl, l in sorted(nach.items(), key=lambda t: -len(t[1]))[:40]:
    var = C((x["h"], x["fs"], x["rad"]) for x in l)
    print("  %-34s %4d × | Varianten: %s | z. B. %s" % (kl[:34], len(l), dict(var.most_common(4)), sorted({x["text"] or x["titel"] for x in l})[:4]))
print("\n== Höhen aller Schaltflächen:", dict(C(x["h"] for x in kn).most_common(12)))
print("== Schriftgrößen:", dict(C(x["fs"] for x in kn).most_common(8)), "| Radien:", dict(C(x["rad"] for x in kn).most_common(6)), "| Schriftarten:", dict(C(x["ff"] for x in kn).most_common(4)))
ohne = [x for x in kn if "btn" not in x["kl"].split()]
print("\n== Schaltflächen ohne Klasse „btn“:", len(ohne), "von", len(kn))
for (kl, h, fs), n in C((x["kl"], x["h"], x["fs"]) for x in ohne).most_common(30):
    bsp = [x for x in ohne if (x["kl"], x["h"], x["fs"]) == (kl, h, fs)]
    print("  %-30s h=%s fs=%s  %3d × | %s | Seiten: %s" % (kl[:30] or "(keine)", h, fs, n, sorted({(x["text"] or x["titel"])[:22] for x in bsp})[:4], sorted({x["route"].split("/")[1] for x in bsp})[:4]))
inl = [x for x in kn if re.search(r"font-size|padding|height|background|border-radius", x["inline"])]
print("\n== Schaltflächen mit eigener Formatierung im style-Attribut:", len(inl))
for (st,), n in C((x["inline"][:70],) for x in inl).most_common(14): print("  %3d × %s | %s" % (n, st, sorted({x["text"][:18] for x in inl if x["inline"][:70] == st})[:3]))
print("\n== Beschriftungen für gleiche Handlungen")
texte = C(x["text"] for x in kn if x["text"])
gruppen = {"Speichern": r"^(Speichern|Sichern|Übernehmen|OK|Ok|Anwenden|Fertig|Änderungen speichern|Speichern und schließen)$", "Abbrechen": r"^(Abbrechen|Schließen|Zurück|Verwerfen)$", "Löschen": r"(Löschen|löschen|Entfernen|entfernen|✕|×|🗑|✖)", "Neu": r"^(\+|＋|Neu|Hinzufügen|Anlegen|\+ .*|Neue[rs]? .*)$", "Drucken/PDF": r"(Druck|PDF)", "Bearbeiten": r"(Bearbeiten|Ändern|✎|✏)"}
for g, m in gruppen.items():
    print("  %-12s %s" % (g, {t: n for t, n in texte.most_common() if re.search(m, t)} if True else ""))
nur_symbol = [x for x in kn if x["text"] and len(x["text"]) <= 2 and not re.search(r"[A-Za-z0-9]", x["text"])]
print("\n== reine Symbolschaltflächen:", len(nur_symbol), "| ohne Erklärung (title/aria-label):", len([x for x in nur_symbol if not x["titel"]]), sorted(C(x["text"] for x in nur_symbol if not x["titel"]).items(), key=lambda t: -t[1])[:12])
leer = [x for x in kn if not x["text"] and not x["titel"]]
print("== Schaltflächen ganz ohne Text und Erklärung:", len(leer), C((x["kl"], x["route"].split("/")[1]) for x in leer).most_common(6))
fe = [x for x in d if x["art"] in ("feld", "auswahl") and not x["imKopf"]]
print("\n== Eingabefelder:", len(fe), "| Höhen:", dict(C(x["h"] for x in fe).most_common(10)), "| Schrift:", dict(C(x["fs"] for x in fe).most_common(6)), "| Radius:", dict(C(x["rad"] for x in fe).most_common(5)))
for h in [h for h, n in C(x["h"] for x in fe).most_common() if n < 40][:8]:
    b = [x for x in fe if x["h"] == h]; print("   Höhe %s: %d × | Klassen %s | Seiten %s" % (h, len(b), sorted({x["kl"][:20] for x in b})[:4], sorted({x["route"] for x in b})[:3]))
for tag in ("h1", "h2", "h3", "th"):
    l = [x for x in d if x["tag"] == tag]; print("== %s: %d | Schriftgrößen %s | Gewicht %s" % (tag, len(l), dict(C(x["fs"] for x in l).most_common(6)), dict(C(x["fw"] for x in l).most_common(3))))
kopf = [x for x in d if x["art"] == "knopf" and x["imKopf"]]; print("== Kopfbereich:", len(kopf), dict(C((x["kl"][:20], x["h"]) for x in kopf).most_common(8)))
