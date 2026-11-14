import json, ssl, socket, http.client, os, time, subprocess, glob, signal, sys
exec(open("/tmp/claude-0/t/sec/ausfall.py").read().split("inh = login(); db =")[0])
inh = login(); print("Einstellung:", rq(inh, "PUT", "/api/einstellungen", {"netzwerk": True, "https": "nur"})[0])
os.kill(pid(), signal.SIGTERM); time.sleep(1.5); os.environ["BUERO_HTTPS_PORT"] = "8796"; print("Neustart:", start()); print(open(T + "/log.txt").read().strip().splitlines()[-4:])
ca = D + "/zertifikat/jahresring-ca.pem"; ctx = ssl.create_default_context(cafile=ca)
PORT_T = 8796
def anfrage(tls, methode, pfad, body=None, quelle="127.0.0.1", cookie=None, kontext=None):
    c = (http.client.HTTPSConnection("127.0.0.1", PORT_T, context=kontext or ctx, source_address=(quelle, 0), timeout=20) if tls
         else http.client.HTTPConnection("127.0.0.1", 8799, source_address=(quelle, 0), timeout=20))
    c.request(methode, pfad, body=json.dumps(body) if body is not None else None, headers={"Content-Type": "application/json", **({"Cookie": cookie} if cookie else {})})
    r = c.getresponse(); b = r.read(); return r.status, dict(r.getheaders()), b
s, h, b = anfrage(True, "GET", "/"); print("https Startseite:", s, len(b), "Bytes")
s, h, b = anfrage(True, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}, quelle="127.0.0.2"); ck = h.get("Set-Cookie", ""); print("https Anmeldung:", s, "| Cookie-Attribute:", ";".join(ck.split(";")[1:]))
s, h, b = anfrage(True, "GET", "/api/kunden", cookie=ck.split(";")[0], quelle="127.0.0.2"); print("https Daten mit Anmeldung (fremdes Gerät):", s, len(json.loads(b)), "Kunden")
s, h, b = anfrage(False, "GET", "/stempel", quelle="127.0.0.2"); print("http von fremdem Gerät (nur https):", s, h.get("Location"))
s, h, b = anfrage(False, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"}, quelle="127.0.0.2"); print("http Anmeldung von fremdem Gerät:", s, b.decode()[:90])
s, h, b = anfrage(False, "GET", "/zertifikat", quelle="127.0.0.2"); print("http /zertifikat:", s, "Fingerabdruck auf Seite:", "SHA-256" in b.decode(), "| Adresse:", "https://" in b.decode())
s, h, b = anfrage(False, "GET", "/zertifikat/jahresring-ca.crt", quelle="127.0.0.2"); print("CA-Download:", s, h.get("Content-Type"), len(b), "Bytes", b[:1] == b"\x30")
s, h, b = anfrage(False, "GET", "/api/version"); print("http am PC selbst:", s)
try: anfrage(True, "GET", "/", kontext=ssl.create_default_context()); print("FEHLER: ohne CA vertraut")
except ssl.SSLError as e: print("Gerät ohne eingerichtetes Zertifikat:", str(e)[:60])
# hängendes Gerät blockiert niemanden
sk = socket.create_connection(("127.0.0.1", 8796)); t0 = time.time(); s, h, b = anfrage(True, "GET", "/api/version"); print(f"Anfrage trotz hängender Verbindung: {s} in {(time.time()-t0)*1000:.0f} ms"); sk.close()
print("Server-Schlüssel/CA in Vollsicherung:", end=" "); n = json.loads(rq(login(), "POST", "/api/service/sicherung", {})[1])["name"]
import zipfile; print([x for x in zipfile.ZipFile(D + "/backup/" + n).namelist() if "zertifikat" in x or "schluessel" in x] or "nein")
e = json.loads(rq(login(), "GET", "/api/einstellungen")[1]); print("_https:", {k: (v[:20] if isinstance(v, str) else v) for k, v in e["_https"].items()})

PORT_T = 8797
s, h, b = anfrage(True, "GET", "/"); print("Stempel-Adresse /:", s, h.get("Location"))
s, h, b = anfrage(True, "GET", "/stempel"); print("Stempel-Adresse /stempel:", s, b"stempel.webmanifest" in b)
s, h, b = anfrage(True, "GET", "/stempel.webmanifest"); print("Manifest:", s, json.loads(b)["id"], json.loads(b)["scope"])
s, h, b = anfrage(True, "GET", "/api/stempel", cookie=ck.split(";")[0]); print("Stempel-API mit der Anmeldung der Büro-Adresse:", s)
s, h, b = anfrage(False, "GET", "/stempel", quelle="127.0.0.2"); print("http /stempel von fremdem Gerät →", h.get("Location"))
