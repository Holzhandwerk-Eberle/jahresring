import sys, os, shutil, json, random
P = "/tmp/claude-0/t/er/app2"; shutil.rmtree(P, ignore_errors=True)
shutil.copytree("/home/claude/eberle-buero", P, ignore=shutil.ignore_patterns("daten", "__pycache__")); sys.path.insert(0, P); os.chdir(P)
import app
app.init_db(); random.seed(7); A = app.api; F = []
def chk(name, ist, soll, tol=0.011):
    if abs(ist - soll) > tol: F.append(f"{name}: ist {ist} soll {soll}")
with app.verbindung() as con:
    A("PUT", ["einstellungen"], {}, {"firma": "M", "firma_anschrift": "A 1\n88069 T", "steuernummer": "1", "sepa_iban": "DE02120300000000202051"})
    n_auftraege = 0
    for lauf in range(40):
        kd = {"kurzname": f"K{lauf}", "strasse": "W", "plz": "88045", "ort": "FN"}
        rab = random.choice([0, 0, 3, 5.5]); brutto = random.random() < 0.3
        if rab: kd["rabatt"] = rab
        if brutto: kd["preise"] = "brutto"
        kid = A("POST", ["kunden"], {}, kd)["id"]; aid = A("POST", ["auftraege"], {}, {"kunde_id": kid, "bezeichnung": "T"})["id"]
        k = json.loads(con.execute("SELECT kalk FROM auftraege WHERE id=?", (aid,)).fetchone()[0] or "{}")
        wk = [w["k"] for w in k.get("werkstoffe", []) if w.get("typ") in ("platte", "massiv")][:5]; kst = [x["kst"] for x in k.get("kostenstellen", [])][:4]
        soll_netto = 0
        for i in range(random.randint(1, 7)):
            p = A("POST", ["auftraege", str(aid), "positionen"], {}, {"text": f"P{i}"}); pid = p.get("id") or p["position"]["id"]
            d = {"menge": random.choice([1, 2, 3, 0.5, 2.75, 12])}
            art = random.choice(["manuell", "kalk", "kalk", "mix"])
            if art == "manuell": d.update(einzelpreis=round(random.uniform(5, 3000), 2), preis_manuell=1)
            else:
                d.update(stueckliste=[{"werkstoff": random.choice(wk), "laenge": random.randint(200, 2400), "breite": random.randint(100, 900), "stueck": random.randint(1, 6)} for _ in range(random.randint(0, 8))] if wk else [],
                         zeitmodus="stunden", zeiten=[{"kst": c, "stunden": round(random.uniform(0.25, 12), 2)} for c in kst[:random.randint(0, 4)]],
                         extras={"kostenliste": [{"art": random.choice(["werkstoffe", "fremdleistungen", "zukauf", "sonder_fertigung", "sonder_vertrieb"]), "menge": random.choice([1, 2, ""]), "preis": round(random.uniform(1, 400), 2)} for _ in range(random.randint(0, 3))]})
            if random.random() < 0.15: d["gesperrt"] = 1
            if random.random() < 0.1: d["alternativ"] = 1
            A("PUT", ["positionen", str(pid)], {}, d)
            for u in range(random.choice([0, 0, 1, 3])):
                c = A("POST", ["auftraege", str(aid), "positionen"], {}, {"text": "U", "parent_id": pid}); cid = c.get("id") or c["position"]["id"]
                A("PUT", ["positionen", str(cid)], {}, {"menge": random.choice([1, 2, 4]), "einzelpreis": round(random.uniform(5, 500), 2), "preis_manuell": 1, **({"gesperrt": 1} if random.random() < 0.15 else {})})
        con.commit()
        erg = A("GET", ["auftraege", str(aid), "positionen"], {}, None); ps = erg["positionen"]
        for p in ps:
            c = p["calc"]; kinder = [x for x in (p.get("kinder") or []) if not x.get("gesperrt")]
            unter = sum(float(x["menge"] or 0) * x["calc"]["ep_gesamt"] for x in kinder)
            chk(f"A{aid} P{p['id']} unter_ep", c.get("unter_ep", 0), unter, 0.02)
            if not p.get("preis_manuell"):
                chk(f"A{aid} P{p['id']} ep_gesamt = ep + unter", c["ep_gesamt"], c.get("ep", c["ep_gesamt"] - unter) + unter, 0.02)
            if not p["gesperrt"] and not p.get("alternativ"): soll_netto += round(float(p["menge"] or 0) * c["ep_gesamt"], 2)
        s = erg.get("summen") or {}
        bid = A("POST", ["auftraege", str(aid), "belege"], {}, {"art": "rechnung"})["id"]; con.commit(); b = app.beleg_laden(con, bid); sm = b["daten"]["summen"]
        zs = sum(z["gp"] for z in b["daten"]["zeilen"] if z.get("typ") == "pos" and z.get("zaehlt", True))
        if brutto:
            chk(f"A{aid} Bruttokunde Zeilen netto", zs, soll_netto, 0.011 * max(1, len(ps)))
        else:
            chk(f"A{aid} Zeilensumme = Positionen", zs, soll_netto, 0.011 * max(1, len(ps)))
            chk(f"A{aid} Netto = Zeilen − Rabatt", sm["netto"], round(zs - (sm.get("rabatt") or 0), 2))
            if rab: chk(f"A{aid} Rabatt {rab} %", sm.get("rabatt") or 0, round(zs * rab / 100, 2))
        chk(f"A{aid} USt", sm["ust"], round(sm["netto"] * 0.19, 2), 0.011 if not brutto else 0.02); chk(f"A{aid} Brutto", sm["brutto"], round(sm["netto"] + sm["ust"], 2))
        chk(f"A{aid} Spalten", b["brutto"], sm["brutto"]); chk(f"A{aid} Zahlbetrag", b["zahlbetrag"], sm["brutto"])
        try:
            si = A("GET", ["auftraege", str(aid), "sollist"], {}, None)
            erl = (si.get("soll") or {}).get("erloes") if isinstance(si.get("soll"), dict) else None
            if erl is not None and not brutto: chk(f"A{aid} Soll/Ist Erlös = Netto vor Rabatt", erl, zs, 0.02 * max(1, len(ps)))
        except Exception as f: F.append(f"A{aid} sollist: {f}")
        n_auftraege += 1
    print(n_auftraege, "Zufallsaufträge geprüft;", len(F), "Abweichungen"); [print("  ", x) for x in F[:15]]
