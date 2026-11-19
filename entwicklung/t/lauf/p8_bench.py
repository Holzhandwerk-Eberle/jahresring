"""P8: große Importe messen (Preisliste mit 21.000 Zeilen gegen 21.000 Materialien; Kundenimport mit 5.000 Zeilen)."""
import json, time, base64, sys
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
inh = cl()
rq(inh, "POST", "/api/anmeldung/einrichten", {"name": "Jonas", "login": "jonas", "passwort": "geheim12345", "passwort2": "geheim12345", "firma": "Muster"})
rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim12345"})
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
def A(m, p, d=None):
    t0 = time.time(); s, b, h = rq(inh, m, "/api/" + p, d, {"X-Rueckfrage": "1", "X-Bestaetigt": "fremdwaehrung"}); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_t"] = time.time() - t0
    return j
N = int(sys.argv[1]) if len(sys.argv) > 1 else 21000
lf = A("POST", "lieferanten", {"kurzname": "Großhandel", "firma": "Großhandel KG"})
zeilen = ["Artikelnummer;Bezeichnung;Einheit;Preis;EAN"] + [f"A{i:06d};Artikel {i} Beschlag verzinkt;Stk.;{1 + i % 97},{i % 100:02d};{4000000000000 + i}" for i in range(N)]
roh = base64.b64encode("\n".join(zeilen).encode("utf-8")).decode()
r = A("POST", "preisimport/lesen", {"daten": roh, "dateiname": "gross.csv", "lieferant_id": lf["id"]})
print(f"Lesen ({N} Zeilen, leerer Stamm): {r['_t']:.1f} s, Status {r['_s']}, Artikel {r.get('artikel')}, neu {r.get('neu_anzahl', r.get('anzahl'))}", {k: (v if not isinstance(v, (list, dict)) else f'<{len(v)}>') for k, v in r.items() if k not in ('treffer',)})
kat = sys.argv[2] if len(sys.argv) > 2 else "beschlag"
t0 = time.time(); n = 0
for i in range(0, N, 2000):
    x = A("POST", "preisimport/anlegen", {"schluessel": r["schluessel"], "auswahl": [f"A{k:06d}" for k in range(i, min(N, i + 2000))], "kategorie": kat, "lieferant_id": lf["id"], "dateiname": "gross.csv"})
    if x["_s"] != 200: print("Anlegen:", x); break
    n += x.get("angelegt", 0)
    if i == 0: print(f"  erste 2.000 angelegt in {x['_t']:.1f} s")
print(f"Anlegen von {n} Materialien in Paketen zu 2.000: {time.time() - t0:.1f} s (letztes Paket {x['_t']:.1f} s)")
zeilen2 = ["Artikelnummer;Bezeichnung;Einheit;Preis;EAN"] + [f"A{i:06d};Artikel {i} Beschlag verzinkt;Stk.;{2 + i % 97},{i % 100:02d};{4000000000000 + i}" for i in range(N)]
roh2 = base64.b64encode("\n".join(zeilen2).encode("utf-8")).decode()
r2 = A("POST", "preisimport/lesen", {"daten": roh2, "dateiname": "gross2.csv", "lieferant_id": lf["id"]})
print(f"Abgleich {N} Zeilen gegen {r2.get('materialien')} Materialien: {r2['_t']:.1f} s, Treffer {len(r2.get('treffer') or [])}, Antwort {len(json.dumps(r2)) / 1e6:.1f} MB")
posten = [{"material_id": t["material_id"], "neu": t["neu"]} for t in r2["treffer"] if t.get("vorschlag")]
u = A("POST", "preisimport/uebernehmen", {"posten": posten, "dateiname": "gross2.csv", "lieferant_id": lf["id"]})
print(f"Übernehmen von {len(posten)} Preisen: {u['_t']:.1f} s, geändert {u.get('geaendert')}, Status {u['_s']}", u.get("fehler") or "")
r3 = A("POST", "preisimport/lesen", {"schluessel": r2["schluessel"], "lieferant_id": lf["id"]})
print(f"erneuter Abgleich (alles gleich): {r3['_t']:.1f} s")
