import sys, os, time, cProfile, pstats, io
os.chdir("/tmp/claude-0/t/perf152/eberle-buero"); sys.path.insert(0, "."); sys.argv = ["app.py"]
os.environ["BUERO_PORT"] = "8794"
t0 = time.perf_counter(); import app; print(f"Import {time.perf_counter() - t0:.2f} s")
t0 = time.perf_counter(); app.datenbank_starten(); print(f"Datenbank starten (einrichten, nachrüsten) {time.perf_counter() - t0:.2f} s")
for name, teile, q in [("start", ["start"], {}), ("start (2.)", ["start"], {}), ("einstellungen", ["einstellungen"], {}), ("mitarbeiter", ["mitarbeiter"], {"status": "aktiv"}), ("start (3.)", ["start"], {})]:
    pr = cProfile.Profile(); t0 = time.perf_counter(); pr.enable()
    try: erg = app.api("GET", teile, q, None)
    except Exception as f: erg = f
    pr.disable(); t = time.perf_counter() - t0
    print(f"== {name}: {t:.2f} s  ({type(erg).__name__})")
    if t > 0.5:
        s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(28); print("\n".join(l[:190] for l in s.getvalue().splitlines()[4:44]))
