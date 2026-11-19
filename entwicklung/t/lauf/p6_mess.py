import sys, os, time
os.chdir("/tmp/claude-0/t/perf152/eberle-buero"); sys.path.insert(0, "."); sys.argv = ["app.py"]
os.environ["BUERO_PORT"] = "8794"
import app
app.datenbank_starten()
for name, teile, q in [("Löschliste", ["datenschutz", "faellig"], {}), ("Löschliste (2.)", ["datenschutz", "faellig"], {}), ("Kontoauszüge", ["bank"], {}), ("Startseite", ["start"], {}), ("Startseite (2.)", ["start"], {})]:
    t0 = time.perf_counter()
    try: erg = app.api("GET", teile, q, None)
    except Exception as f: erg = f
    print(f"{name}: {time.perf_counter() - t0:.2f} s ({type(erg).__name__}{'' if not isinstance(erg, dict) else ' ' + str({k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in list(erg.items())[:6]})})")
