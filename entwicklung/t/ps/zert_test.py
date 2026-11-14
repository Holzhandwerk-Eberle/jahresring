import sys, os, socket, ssl, tempfile, threading, http.server, shutil
sys.path.insert(0, "/home/claude/eberle-buero")
import zert
def ok(b, t): print(("ok   " if b else "FEHLER ") + t); assert b, t
D = tempfile.mkdtemp()
socket.gethostname = lambda: "Magda_Schupp"
cert, key, m = zert.bereitstellen(D, ["192.168.178.26"], "Holzhandwerk Eberle")
n = zert.namen(D); print(n)
ok("magda_schupp" in n and "192.168.178.26" in n and "localhost" in n, "Unterstrich-Name und IP im Zertifikat")
# echte TLS-Prüfung gegen die CA, mit Name und IP
srv = http.server.HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler); srv.socket = zert.kontext(cert, key).wrap_socket(srv.socket, server_side=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
ctx = ssl.create_default_context(cafile=os.path.join(D, "zertifikat", "jahresring-ca.pem"))
for host in ("magda_schupp", "localhost", "magda_schupp.fritz.box"):
    try:
        with ctx.wrap_socket(socket.create_connection(("127.0.0.1", srv.server_address[1])), server_hostname=host) as s: ok(True, f"TLS gültig für {host}")
    except ssl.SSLError as x: ok(False, f"{host}: {x}")
# CA ohne den Namen (alter Stand / PC umbenannt): Name wird weggelassen, Zertifikat bleibt gültig
socket.gethostname = lambda: "Neuer_Name"
cert, key, m = zert.bereitstellen(D, ["192.168.178.26", "192.168.178.40"], "x"); n = zert.namen(D)
ok("neuer_name" not in n and "192.168.178.40" in n, f"umbenannter PC: Name nicht im Zertifikat, neue IP nachgetragen {n}")
srv.socket = None
srv2 = http.server.HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler); srv2.socket = zert.kontext(cert, key).wrap_socket(srv2.socket, server_side=True)
threading.Thread(target=srv2.serve_forever, daemon=True).start()
with ctx.wrap_socket(socket.create_connection(("127.0.0.1", srv2.server_address[1])), server_hostname="localhost") as s: ok(True, "weiter gültig mit alter CA")
fp = zert.fingerabdruck(D); zert.ca_verwerfen(D); cert, key, m = zert.bereitstellen(D, ["192.168.178.26"], "x")
ok(zert.fingerabdruck(D) != fp and "neuer_name" in zert.namen(D) and any(f.startswith("alt-") for f in os.listdir(os.path.join(D, "zertifikat"))), "neu ausgestellt: neue CA mit neuem Namen, alte Dateien aufbewahrt")
ok(zert.eigenes(D) is None, "kein eigenes Zertifikat")
shutil.copy(cert, os.path.join(D, "zertifikat", "eigen.pem")); shutil.copy(key, os.path.join(D, "zertifikat", "eigen.key"))
ok(zert.eigenes(D) is not None, "eigenes Zertifikat erkannt")
open(os.path.join(D, "zertifikat", "eigen.key"), "w").write("kaputt"); ok(zert.eigenes(D) is None, "kaputtes eigenes Zertifikat wird nicht benutzt")
ok(zert.windows_vertrauen(D) == "", "kein Windows: nichts zu tun")
print("ALLES IN ORDNUNG")
