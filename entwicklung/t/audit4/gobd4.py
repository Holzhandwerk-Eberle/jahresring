import json, re, sys, base64, time, os, sqlite3, glob, hashlib, io
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
sys.path.insert(0, "/home/claude/eberle-buero/lib")
from pypdf import PdfReader
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
D = "/tmp/claude-0/t/v25/eberle-buero/daten"
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None):
    s, b, hd = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s
    return j
e0 = A("GET", "einstellungen"); print("Betrieb vorher:", e0.get("firma"), "|", e0.get("sepa_iban"), "| Fußzeile-Schlüssel:", [k for k in e0 if "fuss" in k or "bank" in k][:8])
A("PUT", "einstellungen", {"firma": "Altfirma Schreinerei", "sepa_iban": "DE02120300000000202051", "bank_name": "Altbank"})
k = A("POST", "kunden", {"kurzname": "Original, Otto", "nachname": "Original", "plz": "88069", "ort": "Tettnang"})
a = A("POST", "auftraege", {"kunde_id": k["id"], "bezeichnung": "Regal"})
po = A("POST", f"auftraege/{a['id']}/positionen", {"text": "Regal"}); pid = po.get("id") or po["position"]["id"]; A("PUT", f"positionen/{pid}", {"einzelpreis": 400, "preis_manuell": 1, "menge": 1})
b = A("POST", f"auftraege/{a['id']}/belege", {"art": "rechnung"}); f = A("POST", f"belege/{b['id']}/festschreiben", {}); nr = (f.get("beleg") or f).get("nummer")
txt = lambda roh: re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(roh)).pages))
archiv = glob.glob(D + f"/belege/*/{nr}.pdf")[0]; t_archiv = txt(open(archiv, "rb").read())
v1 = txt(rq(inh, "GET", f"/druck/{b['id']}.pdf", roh=True)[1])
A("PUT", "einstellungen", {"firma": "Neufirma Holzbau GmbH", "sepa_iban": "DE89370400440532013000", "bank_name": "Neubank", "firma_anschrift": "Neue Gasse 9\n88000 Neustadt", "steuernummer": "99/999/99999"})
v2 = txt(rq(inh, "GET", f"/druck/{b['id']}.pdf", roh=True)[1])
t_archiv2 = txt(open(archiv, "rb").read())
woerter = lambda t: {w for w in ("Altfirma", "Neufirma", "DE02 1203", "DE021203", "DE89 3704", "DE893704", "Altbank", "Neubank", "Neue Gasse", "99/999/99999") if w in t}
print("Rechnung", nr)
print("  Archiv-PDF enthält:            ", sorted(woerter(t_archiv)), "| unverändert nach Einstellungswechsel:", t_archiv == t_archiv2)
print("  „PDF ansehen“ vor der Änderung: ", sorted(woerter(v1)))
print("  „PDF ansehen“ nach der Änderung:", sorted(woerter(v2)))
s, h, _ = rq(inh, "GET", f"/druck/{b['id']}"); print("  Druckansicht (HTML) nach der Änderung:", sorted(woerter(re.sub(r"<[^>]+>", " ", h))))
m = A("GET", f"belege/{b['id']}/mail"); print("  Mail-Anhang käme aus:", [x.get("name") for x in (m.get("anhaenge") or [])])
A("PUT", "einstellungen", {"firma": e0.get("firma"), "sepa_iban": e0.get("sepa_iban") or "", "bank_name": e0.get("bank_name") or "", "firma_anschrift": e0.get("firma_anschrift") or "", "steuernummer": e0.get("steuernummer") or ""})
