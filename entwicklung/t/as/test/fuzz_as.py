import json, itertools
exec(open("/tmp/claude-0/t/sec/sec.py").read().split("inh = cl()")[0])
inh = cl(); rq(inh, "POST", "/api/anmeldung/anmelden", {"login": "jonas", "passwort": "geheim123"})
WERTE = [None, 1, -1, 1.5, "", "x" * 3000, [], [1, "a"], {}, {"a": 1}, True, "2026-13-45", "<b>"]
FELDER = ["titel", "art", "bereich", "werkzeug_ids", "vorlage", "vorlagen", "zeilen", "intervall", "status", "beteiligte", "mitgeltend", "abschnitte", "symbole", "material_id",
          "thema_ids", "mitarbeiter_ids", "datum", "anlass", "ergaenzung", "text", "alle", "aktiv", "ba_ids", "gefahrstoff", "ghs", "h_saetze", "signalwort", "name", "png", "rolle",
          "teilnehmer_id", "monat", "dateiname", "daten", "qualifikation_id", "gueltig_bis", "organisation", "notfall", "zeit", "verletzung", "ausgabe", "mitarbeiter_id"]
PFADE = [("POST", "arbeitsschutz/gb"), ("PUT", "arbeitsschutz/gb/1"), ("POST", "arbeitsschutz/gb/1/freigeben"), ("POST", "arbeitsschutz/ba"), ("PUT", "arbeitsschutz/ba/1"),
         ("POST", "arbeitsschutz/ba/2/freigeben"), ("POST", "arbeitsschutz/themen"), ("PUT", "arbeitsschutz/themen/1"), ("POST", "arbeitsschutz/unterweisungen"),
         ("PUT", "arbeitsschutz/unterweisungen/2"), ("POST", "arbeitsschutz/unterweisungen/2/unterschreiben"), ("PUT", "arbeitsschutz/gefahrstoff/1"), ("POST", "arbeitsschutz/dateien"),
         ("PUT", "arbeitsschutz/dateien/1"), ("POST", "arbeitsschutz/qualifikationen"), ("PUT", "arbeitsschutz/qualifikationen/1"), ("PUT", "arbeitsschutz/organisation"),
         ("POST", "arbeitsschutz/verbandbuch"), ("POST", "monatsbeleg/1/unterschreiben"), ("GET", "arbeitsschutz/ghs?h=H225,EUH066,H999X"), ("GET", "arbeitsschutz/vorlagen/gb/x")]
st = {}
s5 = []
for m, p in PFADE:
    for f in FELDER:
        for w in WERTE:
            s, b, _ = rq(inh, m, "/api/" + p, {f: w} if m != "GET" else None)
            st[s] = st.get(s, 0) + 1
            if s >= 500: s5.append((m, p, f, repr(w)[:30], b[:120]))
print(st); print("5xx:", len(s5)); [print(x) for x in s5[:20]]
