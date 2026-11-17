import json, re, sys, base64, time, io, zipfile
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None):
    s, b, hd = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    return j
lid = [l for l in A("GET", "lieferanten?status=alle") if isinstance(l, dict)] if False else None
ll = rq(inh, "GET", "/api/lieferanten")[1]; lid = [l["id"] for l in json.loads(ll) if l["kurzname"] == "Beschlag Import AG"][0]
def lesen(roh, name):
    x = A("POST", "preisimport/lesen", {"daten": base64.b64encode(roh).decode(), "dateiname": name, "lieferant_id": lid}); return x
x = lesen("Artikelnummer;Bezeichnung;Einheit;Preis\nA1;Testartikel;Stk;3,45\n".encode(), "z.csv")
print({k: (v if not isinstance(v, list) else v[:2]) for k, v in x.items() if k != "schluessel"})
for preis in ("3,45", "1.234,50", "1,234.50", "1'234.50", "1.234", "12.5", "3,45 €", "EUR 3,45", "-2,00", "0", "1,2E+02", "1.250"):
    x = lesen(("Artikelnummer;Bezeichnung;Einheit;Preis\nA1;Testartikel;Stk;" + preis + "\n").encode("utf-8"), "z.csv")
    n = x.get("neu") or []
    print("  Preis %-12r → %s" % (preis, [(a.get("preis"), a.get("listenpreis"), a.get("netto")) for a in n][:1] or ("nichts gelesen, Hinweis: %r" % x.get("hinweis"))))
x = lesen(("Artikelnummer;Bezeichnung;Einheit;Preis\n4711;Topfband Größe;Stk;3,45\n").replace(";", "\t").encode("utf-16"), "u.txt"); print("UTF-16:", x.get("kopf"), x.get("zuordnung"), x.get("hinweis"))
x = lesen(("Artikelnummer;Bezeichnung;Einheit;Preis\n4711;Topfband Größe 35;Stk;3,45\n").encode("cp1252"), "c.csv"); print("cp1252 Umlaute:", [(a.get("bezeichnung")) for a in (x.get("neu") or [])])
x = lesen(("Artikelnummer;Bezeichnung;Einheit;Preis\n4711;Topfband Größe 35;Stk;3,45\n").encode("utf-8"), "c.csv"); print("utf-8 Umlaute:", [(a.get("bezeichnung")) for a in (x.get("neu") or [])])
