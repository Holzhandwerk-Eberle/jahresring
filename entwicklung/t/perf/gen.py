import sqlite3, random, json, sys
from datetime import date, timedelta
random.seed(1)
c = sqlite3.connect(sys.argv[1]); c.row_factory = sqlite3.Row
F = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
N = lambda n: int(n * F)
tb = dict(c.execute("select * from belege where art='rechnung' limit 1").fetchone())
tp = dict(c.execute("select * from positionen limit 1").fetchone())
start = date(2012, 1, 1); tage = (date(2026, 11, 1) - start).days
d = lambda: (start + timedelta(days=random.randrange(tage))).isoformat()
vn = "Anna Bernd Clara Dieter Eva Frank Gerda Hans Ina Jörg Karin Lukas Maria Nils Olga Peter".split()
nn = "Müller Schmid Weber Wagner Becker Hoffmann Schäfer Koch Bauer Richter Klein Wolf Schröder Neumann".split()
orte = "Tettnang Friedrichshafen Ravensburg Meckenbeuren Kressbronn Lindau Wangen Neukirch Langenargen".split()
def ins(t, rows):
    if not rows: return
    k = list(rows[0]); c.executemany(f'insert into "{t}" ({",".join(k)}) values ({",".join("?"*len(k))})', [tuple(r[x] for x in k) for r in rows])
mx = lambda t, col="nummer": c.execute(f"select coalesce(max(cast({col} as integer)),0) from {t}").fetchone()[0]
k0 = mx("kunden")
ins("kunden", [dict(nummer=k0+i+1, kurzname=f"{random.choice(nn)}, {random.choice(vn)}", vorname=random.choice(vn), nachname=random.choice(nn),
    anschrift=f"Hauptstr. {i%200}", strasse="Hauptstr.", hausnr=str(i%200), plz="88069", ort=random.choice(orte), telefon=f"07542 {100000+i}", email1=f"k{i}@example.de",
    angelegt=d()+"T10:00:00", geaendert=d()+"T10:00:00") for i in range(N(4000))])
kids = [r[0] for r in c.execute("select id from kunden")]
l0 = mx("lieferanten")
ins("lieferanten", [dict(nummer=l0+i+1, kurzname=f"Lieferant {i}", ort=random.choice(orte), angelegt=d()) for i in range(N(400))])
lids = [r[0] for r in c.execute("select id from lieferanten")]
ins("mitarbeiter", [dict(nummer=900+i, kuerzel=f"M{i}", vorname=random.choice(vn), nachname=random.choice(nn), aktiv=1, eintritt="2012-01-01", stundenlohn=20, kostensatz=45, modelle="[]", angelegt=d()) for i in range(6)])
mids = [r[0] for r in c.execute("select id from mitarbeiter")]
ins("projekte", [dict(nummer=f"P{i:05d}", bezeichnung=f"Projekt {i}", kunde_id=random.choice(kids), angelegt=d()) for i in range(N(600))])
pids = [r[0] for r in c.execute("select id from projekte")]
st = ["Abgerechnet"] * 800 + ["Erledigt"] * 80 + ["Abgesagt"] * 80 + ["Angebot"] * 25 + ["Anfrage"] * 5 + ["Auftrag"] * 10
au = []
for i in range(N(8000)):
    dt = d(); au.append(dict(nummer=f"{dt[:4]}-9{i:05d}", kunde_id=random.choice(kids), bezeichnung=random.choice(["Küche", "Schrank", "Tisch", "Bad", "Treppe", "Tür"]) + f" {i}",
        status=random.choice(st), projekt_id=random.choice(pids) if random.random() < .1 else None, angelegt=dt + "T09:00:00", geaendert=dt + "T09:00:00",
        kalk=tb.get("kalk", "") if False else "", titel="[]"))
ins("auftraege", au)
aids = [r[0] for r in c.execute("select id from auftraege")]
pos = []
for a in aids:
    for j in range(15):
        r = dict(tp); r.pop("id"); r.update(auftrag_id=a, sort=j + 1, text=f"Position {j} Korpus Eiche geölt, mit Schubkästen und Blum Tandembox", einzelpreis=random.randint(50, 3000))
        pos.append(r)
ins("positionen", pos); del pos
bel = []
arten = ["angebot", "auftragsbestaetigung", "rechnung", "rechnung", "abschlagsrechnung"]
for i in range(N(24000)):
    r = dict(tb); r.pop("id"); a = random.choice(aids); dt = d(); n = random.randint(200, 20000)
    r.update(auftrag_id=a, kunde_id=random.choice(kids), art=random.choice(arten), lfd=i + 10, nummer=f"{dt[:4]}-8{i:05d}", status="fest", datum=dt, leistungsdatum=dt,
             netto=n, ust=n * .19, brutto=n * 1.19, zahlbetrag=n * 1.19, faellig=dt, pdf="", angelegt=dt + "T10:00:00", geaendert=dt + "T10:00:00")
    bel.append(r)
ins("belege", bel)
bl = [dict(r) for r in c.execute("select id, nummer, kunde_id, auftrag_id, datum, brutto from belege where art like '%rechnung' and nummer like '%-8%'")]
ins("offene_posten", [dict(nummer=b["nummer"], art="Rechnung", kunde_id=b["kunde_id"], auftrag_id=b["auftrag_id"], datum=b["datum"], betrag=b["brutto"], faellig=b["datum"],
    offen=0 if random.random() < .97 else b["brutto"], mahnstufe=0, beleg_id=b["id"], mahnkosten=0, mahnsperre=0) for b in bl])
z = []
for i in range(N(150000)):
    dt = d(); h = random.randint(7, 15)
    z.append(dict(mitarbeiter_id=random.choice(mids), datum=dt, beginn=f"{h:02d}:00", ende=f"{h+2:02d}:30", auftrag_id=random.choice(aids), kst="Bank", taetigkeit="Korpus verleimt", quelle="stempel", angelegt=dt))
ins("zeiten", z); del z
ins("stunden", [dict(auftrag_id=random.choice(aids), datum=d(), stunden=random.randint(1, 8), kst="Bank", taetigkeit="Montage", mitarbeiter_id=random.choice(mids), angelegt=d()) for i in range(N(30000))])
ins("termine", [dict(auftrag_id=random.choice(aids), typ="montage", titel="Montage", von=(x := d()), bis=x, stunden=8, mitarbeiter=json.dumps([random.choice(mids)]), angelegt=x) for i in range(N(20000))])
ins("korrespondenz", [dict(art=random.choice(["mail_ein", "mail_aus", "telefon", "notiz"]), kunde_id=random.choice(kids), auftrag_id=random.choice(aids), datum=d() + "T10:00:00",
    betreff=f"Betreff {i}", text="Sehr geehrter Herr Jonas Eberle, vielen Dank für das Angebot. " * 20, von="kunde@example.de", an="info@example.de", angelegt=d()) for i in range(N(40000))])
m0 = c.execute("select count(*) from material").fetchone()[0]
kat = ["holzwerkstoffe", "massivholz", "beschlaege", "beschichtung", "chemie", "artikel"]
ins("material", [dict(kategorie=random.choice(kat), nummer=f"X{i:05d}", bezeichnung=f"Material {i} Eiche", einheit="Stk.", ek_preis=random.randint(1, 80), lieferant_id=random.choice(lids), lager=1 if i % 3 == 0 else 0, bestand=random.randint(0, 50), angelegt=d()) for i in range(N(3000))])
matids = [r[0] for r in c.execute("select id from material")]
ins("auftragskosten", [dict(datum=d(), auftrag_id=random.choice(aids), kostenart="material", material_id=random.choice(matids), bezeichnung="Material", menge=2, einzelpreis=10, betrag=20, lager_abgang=0, angelegt=d()) for i in range(N(30000))])
ins("lagerbewegungen", [dict(datum=d(), material_id=random.choice(matids), menge=random.choice([-2, 5]), preis=10, art="zugang", angelegt=d()) for i in range(N(30000))])
ins("zahlungen", [dict(nummer=f"Z{i:06d}", lieferant_id=random.choice(lids), auftrag_id=random.choice(aids) if random.random() < .5 else None, belegnr=f"R{i}", belegdatum=(x := d()), betrag=random.randint(20, 5000), faellig=x, bezahlt=x if random.random() < .98 else "", angelegt=x) for i in range(N(12000))])
c.commit()
for t in ["kunden", "auftraege", "positionen", "belege", "offene_posten", "zeiten", "stunden", "termine", "korrespondenz", "material", "auftragskosten", "lagerbewegungen", "zahlungen"]:
    print(t, c.execute(f"select count(*) from {t}").fetchone()[0])
