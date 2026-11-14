exec(open("/tmp/claude-0/t/sec/ausfall.py").read().split("inh = login(); db =")[0])
inh = login(); aid = J(rq(inh, "GET", "/api/auftraege")[1])[0]["id"]
bid = J(rq(inh, "POST", f"/api/auftraege/{aid}/belege", {"art": "rechnung"})[1])["id"]; s, b, _ = rq(inh, "POST", f"/api/belege/{bid}/festschreiben", {}); fb = J(b); print("nächste Nummer nach Wiederherstellung:", s, (fb.get("beleg") or fb).get("nummer") or b[:200])
