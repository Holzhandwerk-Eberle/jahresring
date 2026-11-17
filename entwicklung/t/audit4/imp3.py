import json, re, sys, base64, time
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
J = lambda t: json.loads(t) if t and t[:1] in "[{" else {}
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
def A(m, p, d=None):
    s, b, hd = rq(inh, m, "/api/" + p, d); j = J(b)
    if isinstance(j, dict): j["_s"] = s; j["_roh"] = b
    else: j = {"_s": s, "liste": j, "_roh": b}
    return j
def ops():
    x = A("GET", "offeneposten?status=alle"); l = x.get("liste") or x.get("posten") or []
    return {o["nummer"]: (o["betrag"], o["offen"]) for o in l if o["nummer"] in ("2026-0051", "2026-0052", "2026-0053", "2026-0054", "2026-0055")}
print("vorher:", ops())
bk = A("GET", "bank"); sicher = [(u["referenz"], u["betrag"], [(z["text"][:18], z["betrag"]) for z in u["vorschlag"]["ziele"]]) for u in bk["umsaetze"] if u.get("vorschlag") and u["vorschlag"]["sicher"] and u["status"] == "offen"]
print("sichere Vorschläge:", len(sicher)); [print("   ", s) for s in sicher]
r = A("POST", "bank/sichere", {}); print("alle sicheren übernehmen:", r["_s"], {k: v for k, v in r.items() if not k.startswith("_")})
print("nachher:", ops())
bk = A("GET", "bank?status=alle"); print("Umsätze V*:", [(u["referenz"], u["status"]) for u in bk["umsaetze"] if (u.get("referenz") or "").startswith("V")])
x = A("GET", "offeneposten?status=alle"); l = x.get("liste") or x.get("posten") or []
print("Guthaben/Überzahlung:", [(o["nummer"], o["art"], o["betrag"], o["offen"]) for o in l if o["offen"] < -0.004 or "uthaben" in str(o.get("art"))][:6])
