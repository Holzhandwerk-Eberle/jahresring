import json, collections, re
d = json.load(open("/tmp/claude-0/t/audit4/ui_stil.json")); C = collections.Counter
kn = [x for x in d if x["art"] == "knopf" and not x["imKopf"]]
print("btn mit 32 px:", C((x["text"][:26], x["route"]) for x in kn if x["kl"] == "btn" and x["h"] == 32).most_common(6))
print("btn prim 49 px:", [(x["text"], x["route"], x["b"]) for x in kn if x["kl"] == "btn prim" and x["h"] == 49])
print("× statt ✕:", [(x["route"], x["kl"], x["titel"][:30]) for x in kn if x["text"] == "×"])
print("✕ ohne Erklärung nach Seite:", C(x["route"].split("/")[1] + ("/" + x["route"].split("/")[2] if len(x["route"].split("/")) > 2 and not x["route"].split("/")[2].isdigit() else "") for x in kn if x["text"] == "✕" and not x["titel"]).most_common(10))
print("✕ mit Erklärung, Beispiele:", sorted({x["titel"][:40] for x in kn if x["text"] == "✕" and x["titel"]})[:10])
fe = [x for x in d if x["art"] in ("feld", "auswahl") and not x["imKopf"]]
print("Felder nach Art und Höhe:", C((x["tag"], x["typ"], x["h"]) for x in fe).most_common(16))
h3 = [x for x in d if x["tag"] == "h3"]
for fs in ("17px", "16.38px", "16px"): print("h3", fs, sorted({x["route"].split("/")[1] for x in h3 if x["fs"] == fs})[:8], sorted({x["text"][:24] for x in h3 if x["fs"] == fs})[:4])
print("th 13px:", [(x["route"], x["text"]) for x in d if x["tag"] == "th" and x["fs"] == "13px"])
print("Farben btn prim:", C((x["bg"], x["fg"]) for x in kn if "prim" in x["kl"]).most_common(3), "| btn rot:", C((x["bg"], x["fg"], x["rand"]) for x in kn if "rot" in x["kl"].split()).most_common(3), "| btn:", C((x["bg"], x["fg"]) for x in kn if x["kl"] == "btn").most_common(4))
print("Speichern-Schaltflächen: Klasse", C((x["kl"], x["text"]) for x in kn if x["text"] in ("Speichern", "Übernehmen")).most_common(5))
print("Hauptschaltfläche je Seite (btn prim) – Seiten mit mehr als 2:", [(r, n) for r, n in C(x["route"] for x in kn if "prim" in x["kl"]).most_common(6)])
print("Seiten ohne jede btn-prim:", len({x["route"] for x in kn} - {x["route"] for x in kn if "prim" in x["kl"]}), "von", len({x["route"] for x in kn}))
