"""Jahresring – Schnittstelle des Arbeitsschutzes (Büro und Stempeluhr) und Druckseiten. Fachlogik in arbeitsschutz.py."""
import json
import os
import re
from datetime import date, timedelta

import arbeitsschutz
import benutzer
import personal
import unterschrift
from kern import ApiFehler, de_datum, h, jl
from monatsbeleg import monatsbeleg_signaturen, monatsbeleg_unterschreiben

# von app.py gesetzt: daten, static, prot, ich_name, ich_login, auftrag_material_nummern, einstellungen
HILFE = {}


def zeichen_liste():
    try:
        with open(os.path.join(HILFE["static"], "arbeitsschutz", "zeichen", "zeichen.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def arbeitsschutz_api(con, methode, teile, q, daten):
    d = daten or {}
    u = teile[1] if len(teile) > 1 else ""
    rid = int(teile[2]) if len(teile) > 2 and teile[2].isdigit() else None
    akt = teile[3] if len(teile) > 3 else ""
    A = arbeitsschutz
    wer, inhaber = HILFE["ich_login"](), benutzer.ist_inhaber()
    schreiben = benutzer.darf("arbeitsschutz", 2)
    # Vorsorgekartei und Expositionsverzeichnis: mit Bearbeitungsrecht – oder, wenn so eingestellt, nur für den Inhaber
    vorsorge_sicht = schreiben and (inhaber or not HILFE["einstellungen"](con).get("vorsorge_nur_inhaber"))
    if u == "uebersicht" and methode == "GET":
        return A.uebersicht(con, inhaber, vorsorge_sicht)
    if u == "vorlagen" and methode == "GET":
        v = A.vorlagen()
        if len(teile) == 4 and teile[2] == "gb":
            x = next((g for g in v["gb"] if g["id"] == teile[3]), None)
            if not x:
                raise ApiFehler("Vorlage nicht gefunden.", 404)
            return x
        return {"gb": [{k: g[k] for k in ("id", "name", "gruppe", "art", "schreiner")} | {"anzahl": len(g["gef"])} for g in v["gb"]], "gb_gruppen": v["gb_gruppen"],
                "themen": v["themen"], "psych": v["psych"], "h_saetze": v["h_saetze"], "anlaesse": v["anlaesse"], "notfall": v["notfall"], "stand": v["stand"],
                "quali": A.QUALI, "datei_arten": A.DATEI_ARTEN, "lagerklassen": A.LAGERKLASSEN, "wgk": A.WGK, "gb_arten": A.GB_ARTEN, "ba_arten": A.BA_ARTEN,
                "ba_abschnitte": A.BA_ABSCHNITTE, "zeichen": zeichen_liste()}
    if u == "organisation":
        if methode == "GET":
            return {"organisation": A.organisation(con), "notfall": A.notfall(con), "bedarf": A.bedarf(len(A.mitarbeiter_liste(con)))}
        if methode == "PUT":
            if "organisation" in d:
                o = A.organisation(con)
                for k in A.ORG_STANDARD:
                    if k in d["organisation"]:
                        wert = d["organisation"][k]
                        if k == "bereiche":
                            liste = wert if isinstance(wert, list) else str(wert or "").splitlines()
                            o[k] = [str(x).strip()[:120] for x in liste if str(x).strip()][:50]
                        else:
                            o[k] = str(wert or "")[:1000]
                A.daten_schreiben(con, "organisation", o)
            if "notfall" in d:
                n = A.notfall(con)
                n.update({k: str(d["notfall"].get(k) or "")[:300] for k, _ in A.vorlagen()["notfall"] if k in d["notfall"]})
                A.daten_schreiben(con, "notfall", n)
            return {"organisation": A.organisation(con), "notfall": A.notfall(con)}
    if u == "mitarbeiter" and methode == "GET":
        return [{k: m[k] for k in ("id", "name", "kuerzel", "eintritt", "jugendlich", "inhaber")} for m in A.mitarbeiter_liste(con)]
    if u == "werkzeuge" and methode == "GET":
        return [dict(r, vorschlag=A.vorschlag_vorlage(r["bezeichnung"])) for r in con.execute(
            "SELECT id, nummer, bezeichnung, art, standort, status FROM werkzeuge WHERE IFNULL(status,'')<>'ausgemustert' ORDER BY art<>'Stationäre Maschine', nummer")]
    if u == "werkzeug" and rid and methode == "GET":
        gbs = [{"id": g["id"], "nummer": g["nummer"], "titel": g["titel"], "status_name": g["status_name"], "naechste": g["naechste"]} for g in A.gb_liste(con) if rid in g["werkzeug_ids"]]
        bas = [{"id": b["id"], "nummer": b["nummer"], "titel": b["titel"], "status_name": b["status_name"]} for b in A.ba_liste(con) if rid in b["werkzeug_ids"]]
        th = [{"id": t["id"], "titel": t["titel"]} for t in A.themen(con) if rid in t["werkzeug_ids"]]
        w = con.execute("SELECT bezeichnung FROM werkzeuge WHERE id=?", (rid,)).fetchone()
        return {"gb": gbs, "ba": bas, "themen": th, "dateien": A.dateien(con, {"werkzeug": rid}), "vorschlag": A.vorschlag_vorlage(w["bezeichnung"]) if w else ""}
    # ---- Gefährdungsbeurteilungen
    if u == "gb":
        if methode == "GET" and not rid:
            return A.gb_liste(con)
        if methode == "GET" and rid and not akt:
            g = A.gb_laden(con, rid)
            g["pruefung"] = A.gb_pruefen(g)
            return g
        if methode == "POST" and not rid:
            return A.gb_anlegen(con, d)
        if methode == "PUT" and rid:
            g = A.gb_aendern(con, rid, d)
            g["pruefung"] = A.gb_pruefen(g)
            return g
        if methode == "POST" and rid and akt == "freigeben":
            if not inhaber:
                raise ApiFehler("Gefährdungsbeurteilungen gibt der Inhaber (Unternehmer) frei.", 403)
            g, nr = A.gb_freigeben(con, HILFE["daten"], rid, d, wer)
            HILFE["prot"](con, "as_gb_freigabe", g["nummer"], f"Gefährdungsbeurteilung {g['nummer']} {g['titel']} freigegeben (Fassung {nr}, Stand {de_datum(g['stand'])})",
                 {"fassung": g["fassungen"][0]["id"], "sha256": g["fassungen"][0]["sha256"]})
            g["pruefung"] = []
            return g
        if methode == "DELETE" and rid:
            A.gb_loeschen(con, rid)
            return {"ok": True}
    # ---- Betriebsanweisungen
    if u == "ba":
        if methode == "GET" and not rid:
            return A.ba_liste(con)
        if methode == "GET" and rid:
            return A.ba_laden(con, rid)
        if methode == "POST" and not rid:
            return A.ba_anlegen(con, d)
        if methode == "PUT" and rid:
            return A.ba_aendern(con, rid, d)
        if methode == "POST" and rid and akt == "freigeben":
            if not inhaber:
                raise ApiFehler("Betriebsanweisungen gibt der Inhaber (Unternehmer) frei.", 403)
            b, nr = A.ba_freigeben(con, HILFE["daten"], rid, d, wer)
            HILFE["prot"](con, "as_ba_freigabe", b["nummer"], f"Betriebsanweisung {b['nummer']} {b['titel']} freigegeben (Fassung {nr})", {"fassung": b["fassungen"][0]["id"]})
            return b
        if methode == "DELETE" and rid:
            A.ba_loeschen(con, rid)
            return {"ok": True}
    # ---- Unterweisungen
    if u == "themen":
        if methode == "GET":
            return A.themen(con, q.get("alle") == "1")
        if methode == "POST" and not rid:
            return A.thema_anlegen(con, d)
        if methode == "PUT" and rid:
            return A.thema_aendern(con, rid, d)
        if methode == "DELETE" and rid:
            return A.thema_loeschen(con, rid)
    if u == "matrix" and methode == "GET":
        return A.matrix(con)
    if u == "unterweisungen":
        if methode == "GET" and not rid:
            return A.unterweisungen(con)
        if methode == "GET" and rid:
            return A.unterweisung_laden(con, rid)
        if methode == "POST" and not rid:
            return A.unterweisung_anlegen(con, d, wer, HILFE["ich_name"]())
        if methode == "PUT" and rid:
            return A.unterweisung_aendern(con, rid, d)
        if methode == "POST" and rid and akt == "unterschreiben":
            try:
                return A.unterweisung_unterschreiben(con, HILFE["daten"], rid, d, wer)
            except unterschrift.Fehler as f:
                raise ApiFehler(str(f), f.code)
        if methode == "POST" and rid and akt == "abschliessen":
            uw, entfernt = A.unterweisung_abschliessen(con, rid)
            HILFE["prot"](con, "as_unterweisung", uw["nummer"], f"Unterweisung {uw['nummer']} „{uw['titel']}“ vom {de_datum(uw['datum'])} abgeschlossen: "
                 + ", ".join(t["name"] for t in uw["teilnehmer"]), {"inhalt": uw["inhalt_hash"], "teilnehmer": [t["name"] for t in uw["teilnehmer"]]})
            uw["entfernt"] = entfernt
            return uw
        if methode == "DELETE" and rid:
            A.unterweisung_loeschen(con, rid)
            return {"ok": True}
    # ---- Gefahrstoffe und Dateien
    if u == "gefahrstoffe" and methode == "GET":
        return A.verzeichnis(con)
    if u == "gefahrstoff" and rid:
        if methode == "GET":
            erg = A.material_sicherheit(con, rid)
            return erg
        if methode == "PUT":
            return A.gefahrstoff_speichern(con, rid, d)
    if u == "ghs" and methode == "GET":
        return {"ghs": A.ghs_vorschlag(q.get("h", "")), "codes": A.h_codes(q.get("h", ""))}
    if u == "dateien":
        if methode == "GET":
            return A.dateien(con, q)
        if methode == "POST" and not rid:
            if d.get("qualifikation_id") and not schreiben:
                raise ApiFehler("Dafür fehlt die Berechtigung.", 403)
            return A.datei_hochladen(con, HILFE["daten"], d, wer)
        if methode == "PUT" and rid:
            r, _ = A.datei_pfad(con, HILFE["daten"], rid)
            w = {}
            if "titel" in d:
                w["titel"] = str(d["titel"] or "")[:200]
            if "ausgabe" in d:
                w["ausgabe"] = A.datum_ok(d["ausgabe"])
            if "art" in d and d["art"] in A.DATEI_ARTEN:
                w["art"] = d["art"]
            if "aktuell" in d:
                w["aktuell"] = 1 if d["aktuell"] else 0
            if w:
                con.execute(f"UPDATE as_dateien SET {','.join(k + '=?' for k in w)} WHERE id=?", list(w.values()) + [rid])
            return A.datei_info(con.execute("SELECT * FROM as_dateien WHERE id=?", (rid,)).fetchone())
        if methode == "DELETE" and rid:
            r, pfad = A.datei_pfad(con, HILFE["daten"], rid)
            con.execute("DELETE FROM as_dateien WHERE id=?", (rid,))
            if not con.execute("SELECT 1 FROM as_dateien WHERE pfad=?", (r["pfad"],)).fetchone():
                try:
                    os.remove(pfad)
                except OSError:
                    pass
            return {"ok": True}
    if u == "auftrag" and rid and methode == "GET":
        nummern, ids = HILFE["auftrag_material_nummern"](con, rid)
        return A.auftrag_materialien(con, nummern, ids)
    # ---- Nachweise, Verbandbuch
    if u == "qualifikationen":
        if methode == "GET":
            return A.qualifikationen(con)
        if methode == "POST" and not rid:
            return A.quali_speichern(con, None, d)
        if methode == "PUT" and rid:
            return A.quali_speichern(con, rid, d)
        if methode == "DELETE" and rid:
            for f in con.execute("SELECT id FROM as_dateien WHERE qualifikation_id=?", (rid,)).fetchall():
                arbeitsschutz_api(con, "DELETE", ["arbeitsschutz", "dateien", str(f["id"])], {}, {})
            con.execute("DELETE FROM as_qualifikationen WHERE id=?", (rid,))
            return {"ok": True}
    if u == "verbandbuch":
        if methode == "GET":
            return A.verbandbuch(con)
        if methode == "POST" and not rid:
            return A.verbandbuch_eintragen(con, d, wer)
        if methode == "PUT" and rid:
            if not inhaber:
                raise ApiFehler("Das Verbandbuch sieht und ergänzt nur der Inhaber.", 403)
            return A.verbandbuch_nachtrag(con, rid, d)
        if methode == "DELETE" and rid:
            A.verbandbuch_loeschen(con, rid)
            return {"ok": True}
    # ---- Vorsorgekartei und Expositionsverzeichnis: vertraulich, nur mit Bearbeitungsrecht im Arbeitsschutz
    if u in ("vorsorge", "exposition"):
        if not vorsorge_sicht:
            raise ApiFehler("Vorsorgekartei und Expositionsverzeichnis sind vertraulich (nur für den Inhaber)." if schreiben else
                            "Vorsorgekartei und Expositionsverzeichnis sind vertraulich (nur mit Bearbeitungsrecht im Arbeitsschutz).", 403)
        if u == "vorsorge":
            if methode == "GET":
                return {"eintraege": A.vorsorge(con), "arten": A.VORSORGE_ARTEN, "status": A.VORSORGE_STATUS, "anlaesse": A.VORSORGE_ANLAESSE}
            if methode == "POST" and not rid:
                return A.vorsorge_speichern(con, None, d, wer)
            if methode == "PUT" and rid:
                return A.vorsorge_speichern(con, rid, d, wer)
            if methode == "DELETE" and rid:
                con.execute("DELETE FROM as_vorsorge WHERE id=?", (rid,))
                return {"ok": True}
        else:
            if methode == "GET":
                return {"eintraege": A.exposition(con), "stoffe": A.EXPO_STOFFE, "jahre": A.EXPO_JAHRE}
            if methode == "POST" and not rid:
                return A.exposition_speichern(con, None, d, wer)
            if methode == "PUT" and rid:
                return A.exposition_speichern(con, rid, d, wer)
            if methode == "DELETE" and rid:
                A.exposition_loeschen(con, rid)
                return {"ok": True}
    raise ApiFehler("Unbekannte Anfrage", 404)


def stempel_arbeitsschutz(con, methode, teile, q, d):
    """Stempeluhr: offene Unterschriften (Unterweisungen, Monatsbelege), Betriebsanweisungen, Gefahrstoffe, Verbandbuch."""
    m = personal.eigener_mitarbeiter(con)
    wer = HILFE["ich_login"]()
    if teile[1] == "unterschriften" and methode == "GET":
        erg = arbeitsschutz.fuer_mitarbeiter(con, m["id"])
        heute_m = date.today().isoformat()[:7]
        monate = []
        for i in range(1, 4):
            mo = (date.today().replace(day=1) - timedelta(days=1 + 31 * (i - 1))).isoformat()[:7]
            if m["eintritt"] and mo < m["eintritt"][:7]:
                continue
            s = monatsbeleg_signaturen(con, m["id"], mo)
            if not s["mitarbeiter"] or s["mitarbeiter"]["geaendert"]:
                monate.append({"monat": mo, "erneut": bool(s["mitarbeiter"])})
        erg["monatsbelege"] = sorted({x["monat"]: x for x in monate}.values(), key=lambda x: x["monat"])
        erg["heute_monat"] = heute_m
        return erg
    if teile[1] == "unterweisung" and len(teile) >= 3 and teile[2].isdigit():
        uid = int(teile[2])
        uw = arbeitsschutz.unterweisung_laden(con, uid)
        if not any(t["mitarbeiter_id"] == m["id"] for t in uw["teilnehmer"]):
            raise ApiFehler("Diese Unterweisung betrifft dich nicht.", 403)
        if methode == "GET":
            return {k: uw[k] for k in ("id", "nummer", "datum", "titel", "anlass", "unterweiser", "inhalt", "ergaenzung", "status")} | \
                {"unterschrieben": next((t["unterschrieben"] for t in uw["teilnehmer"] if t["mitarbeiter_id"] == m["id"]), "")}
        if methode == "POST":
            try:
                arbeitsschutz.unterweisung_unterschreiben(con, HILFE["daten"], uid, {**d, "rolle": "teilnehmer", "name": f"{m['vorname']} {m['nachname']}".strip()}, wer,
                                                         eigener_mitarbeiter=m["id"])
            except unterschrift.Fehler as f:
                raise ApiFehler(str(f), f.code)
            return {"ok": True}
    if teile[1] == "monatsbeleg" and methode == "POST":
        return monatsbeleg_unterschreiben(con, m["id"], str(d.get("monat") or ""), "mitarbeiter", {**d, "name": f"{m['vorname']} {m['nachname']}".strip()}, wer, eigener=True)
    if teile[1] == "monatsbeleg" and methode == "GET":
        mo = q.get("monat") or ""
        return {"signaturen": monatsbeleg_signaturen(con, m["id"], mo)} if re.fullmatch(r"\d{4}-\d{2}", mo) else {}
    if teile[1] == "verbandbuch" and methode == "POST":
        return arbeitsschutz.verbandbuch_eintragen(con, {**d, "name": d.get("name") or f"{m['vorname']} {m['nachname']}".strip()}, wer)
    raise ApiFehler("Unbekannte Anfrage", 404)


def as_druck_name(con, teil, nr):
    if teil == "gb":
        r = con.execute("SELECT nummer, titel FROM as_gb WHERE id=?", (nr,)).fetchone()
        return f"Gefährdungsbeurteilung {r['nummer']} {r['titel']}" if r else "Gefährdungsbeurteilung"
    if teil == "ba":
        r = con.execute("SELECT nummer, titel FROM as_ba WHERE id=?", (nr,)).fetchone()
        return f"Betriebsanweisung {r['nummer']} {r['titel']}" if r else "Betriebsanweisung"
    if teil == "unterweisung":
        r = con.execute("SELECT nummer, titel FROM as_unterweisungen WHERE id=?", (nr,)).fetchone()
        return f"Unterweisung {r['nummer']} {r['titel']}" if r else "Unterweisung"
    if teil == "fassung":
        r = con.execute("SELECT art, nr, inhalt FROM as_fassungen WHERE id=?", (nr,)).fetchone()
        i = jl(r["inhalt"], {}) if r else {}
        return f"{'Gefährdungsbeurteilung' if r and r['art'] == 'gb' else 'Betriebsanweisung'} {i.get('nummer', '')} Fassung {r['nr'] if r else ''}"
    return {"gefahrstoffverzeichnis": "Gefahrstoffverzeichnis", "notfall": "Notfall-Aushang"}.get(teil, "Arbeitsschutz")


def as_druck_html(con, teil, nr, q, als_pdf):
    A = arbeitsschutz
    firma = HILFE["einstellungen"](con).get("firma", "")
    try:
        if teil == "gb":
            return A.gb_html(con, HILFE["daten"], A.gb_laden(con, nr), firma, als_pdf)
        if teil == "fassung":
            f = A.fassung(con, nr)
            if f["art"] == "gb":
                return A.gb_html(con, HILFE["daten"], f["inhalt"], firma, als_pdf, fassung_info=f)
            return A.ba_html(con, HILFE["daten"], f["inhalt"], firma, als_pdf, fassung_info=f)
        if teil == "ba":
            b = A.ba_laden(con, nr)
            f = None if q.get("entwurf") == "1" else A.letzte_fassung(con, "ba", nr)
            if not f and not benutzer.darf("arbeitsschutz", 1):
                raise A.Fehler("Diese Betriebsanweisung ist noch nicht freigegeben.", 403)
            return A.ba_html(con, HILFE["daten"], f["inhalt"], firma, als_pdf, fassung_info=f) if f else A.ba_html(con, HILFE["daten"], b, firma, als_pdf)
        if teil == "unterweisung":
            return A.unterweisung_html(con, HILFE["daten"], A.unterweisung_laden(con, nr), firma, als_pdf)
        if teil == "gefahrstoffverzeichnis":
            return A.verzeichnis_html(con, firma, als_pdf)
        if teil == "notfall":
            return A.notfall_html(con, firma, als_pdf)
    except A.Fehler as f:
        return f"<!doctype html><meta charset=utf-8><p style='font:16px sans-serif;margin:40px'>{h(str(f))}</p>"
    return "<!doctype html><meta charset=utf-8><p>Unbekannte Seite</p>"
