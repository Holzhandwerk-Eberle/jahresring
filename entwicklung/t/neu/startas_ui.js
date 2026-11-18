// Version 151, Bedienoberfläche: Schalter „Erinnerungen des Arbeitsschutzes auf der Startseite“ (Einstellungen › Programm).
// Nur diese Erinnerung verschwindet; alle anderen Hinweise und Kästen der Startseite bleiben. Sind Mitarbeiter angelegt,
// steht für den Inhaber der Hinweis, sie wieder einzuschalten. Baut sich die Prüfinstanz selbst frisch auf (Port 8799).
const { chromium } = require('playwright');
const { execSync } = require('child_process');
const U = 'http://127.0.0.1:8799', BILD = '/tmp/claude-0/t/lauf/bild151';
const fehler = [];
const ok = (name, bed, info) => { console.log((bed ? 'ok   ' : 'FEHLER ') + name + (bed ? '' : '  → ' + String(info === undefined ? '' : typeof info === 'string' ? info : JSON.stringify(info)).slice(0, 500))); if (!bed) fehler.push(name); };
(async () => {
  execSync('bash /tmp/claude-0/t/v25/neu.sh', { stdio: 'ignore' }); execSync('mkdir -p ' + BILD);
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1400, height: 950 }, locale: 'de-DE' }); const p = await ctx.newPage();
  const stoerung = []; p.on('pageerror', e => stoerung.push('Skript: ' + String(e).slice(0, 160)));
  // Fehlgeschlagene Abrufe: Logo und Unterschrift fehlen in der frischen Instanz (404 beim Öffnen der Einstellungen), alles andere zählt
  const erlaubt = /\/api\/(logo|unterschrift)\b/;
  p.on('response', r => { if (r.status() >= 400 && !erlaubt.test(r.url())) stoerung.push(`Abruf ${r.status()}: ${r.url().replace(U, '')}`); });
  p.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) stoerung.push('Konsole: ' + m.text().slice(0, 160)); });
  const ruf = async (seite, m, pf, d) => await seite.evaluate(async ([m, pf, d]) => { const r = await fetch('/api/' + pf, { method: m, headers: { 'Content-Type': 'application/json' }, body: d ? JSON.stringify(d) : undefined }); return await r.json(); }, [m, pf, d]);
  const text = async (seite, sel) => ((await seite.textContent(sel)) || '').replace(/\s+/g, ' ').trim();
  // Startseite frisch aufbauen: über eine andere Seite, die jede Rolle öffnen darf, und erst weiter, wenn sie steht
  const start = async seite => { await seite.goto(U + '/#/kunden'); await seite.waitForSelector('#inhalt .titel'); await seite.waitForTimeout(400); await seite.goto(U + '/#/start'); await seite.waitForSelector('#stJahr'); await seite.waitForTimeout(900); };
  const kaesten = async seite => await seite.$$eval('.st-box h3', l => l.map(x => x.childNodes[0].textContent.trim()));

  await p.goto(U + '/'); await p.waitForSelector('#anmForm');
  await ruf(p, 'POST', 'anmeldung/einrichten', { name: 'Jonas', login: 'jonas', passwort: 'geheim12345', passwort2: 'geheim12345', firma: 'Muster' });
  await p.goto(U + '/'); await p.waitForSelector('#leiste', { timeout: 20000 });   // der erste Zugang ist nach dem Anlegen gleich angemeldet
  await ruf(p, 'POST', 'werkzeuge', { bezeichnung: 'Formatkreissäge', art: 'Stationäre Maschine' });
  await ruf(p, 'POST', 'benutzer', { name: 'Berta Büro', login: 'berta', passwort: 'Pruefung#2026', rolle: 'buero' });
  await ruf(p, 'POST', 'benutzer', { name: 'Willi Werkstatt', login: 'willi', passwort: 'Pruefung#2026', rolle: 'werkstatt' });
  const k = await ruf(p, 'POST', 'kunden', { kurzname: 'Muster', nachname: 'Muster', strasse: 'Weg 1', plz: '88069', ort: 'Tettnang' });
  await ruf(p, 'POST', 'auftraege', { kunde_id: k.id, bezeichnung: 'Tisch' });

  // ---------- eingeschaltet (Vorgabe) ----------
  await start(p);
  ok('Vorgabe: die Erinnerung des Arbeitsschutzes steht auf der Startseite', (await p.locator('#stASHinweis').count()) === 1 && /Arbeitsschutz: .*Maschine\(n\) ohne Gefährdungsbeurteilung.*Zur Übersicht/.test(await text(p, '#stASHinweis')), await text(p, '#stAS'));
  const sicherung = () => p.locator('#inhalt .kachel', { hasText: 'Zur Datensicherung' }).count();
  ok('daneben steht die Erinnerung an die Datensicherung', (await sicherung()) === 1);
  const kaestenVorher = await kaesten(p), kennzahlenVorher = await p.locator('.sk-raster > *').count();
  ok('Startseite vollständig (Kennzahlen und Kästen)', kennzahlenVorher === 8 && kaestenVorher.length >= 6, [kennzahlenVorher, kaestenVorher]);
  await p.screenshot({ path: BILD + '/1_start_an.png' });

  // ---------- Schalter in den Einstellungen ----------
  await p.goto(U + '/#/einstellungen/programm'); await p.waitForSelector('#startAS');
  const zeile = p.locator('.einst-pane[data-pane=programm] .zeile', { has: p.locator('#startAS') });
  ok('Einstellungen › Programm: Abschnitt „Startseite“ mit dem Schalter, eingeschaltet', (await p.isChecked('#startAS')) && (await p.locator('.einst-pane[data-pane=programm] .sektion', { hasText: 'Startseite' }).count()) === 1
     && /Erinnerungen des Arbeitsschutzes auf der Startseite anzeigen/.test(await zeile.textContent()));
  ok('Hinweis am Schalter: was gemeint ist, was bleibt, und bei Mitarbeitern einschalten', /Arbeitsschutz › Übersicht vollständig sichtbar/.test(await zeile.textContent()) && /Der Schalter wirkt nur auf diese Erinnerungen, alle anderen Hinweise der Startseite bleiben/.test(await zeile.textContent())
     && /Sobald Mitarbeiter beschäftigt werden, wieder einschalten/.test(await zeile.textContent()), await zeile.textContent());
  await p.uncheck('#startAS'); await p.waitForTimeout(500);
  ok('ohne Mitarbeiter keine Warnung am Schalter, auch nicht beim Ausschalten', !(await p.isVisible('#startASWarn')) && (await text(p, '#startASWarn')) === '');
  await p.check('#startAS');
  ok('es gibt auf der Seite nur diesen einen Schalter für Hinweise der Startseite', (await p.locator('.einst-pane[data-pane=programm] input[name^=start_]').count()) === 1);
  await p.uncheck('#startAS'); await p.screenshot({ path: BILD + '/2_schalter.png' });
  await p.click('#sp'); await p.waitForTimeout(700);
  ok('gespeichert: Einstellung ist aus', (await ruf(p, 'GET', 'einstellungen')).start_arbeitsschutz === false);

  // ---------- ausgeschaltet, keine Mitarbeiter ----------
  await start(p);
  ok('ausgeschaltet: keine Erinnerung des Arbeitsschutzes und (ohne Mitarbeiter) kein Hinweis', (await p.locator('#stASHinweis').count()) === 0 && (await p.locator('#stASAus').count()) === 0 && (await text(p, '#stAS')) === '', await text(p, '#stAS'));
  ok('die Erinnerung an die Datensicherung bleibt', (await sicherung()) === 1);
  ok('Kennzahlen und Kästen der Startseite unverändert', (await p.locator('.sk-raster > *').count()) === kennzahlenVorher && JSON.stringify(await kaesten(p)) === JSON.stringify(kaestenVorher), await kaesten(p));
  await p.screenshot({ path: BILD + '/3_start_aus.png' });
  await p.goto(U + '/#/arbeitsschutz'); await p.waitForSelector('.as-zwei');
  ok('Arbeitsschutz › Übersicht: Punkte weiter sichtbar, Vermerk über die ausgeschaltete Erinnerung mit Weg zur Einstellung', (await p.locator('.as-punkte li').count()) >= 1 && /Die Erinnerungen auf der Startseite sind ausgeschaltet/.test(await text(p, '#asStartAus'))
     && (await p.locator('#asStartAus a[href="#/einstellungen/programm"]').count()) === 1, await text(p, '#inhalt'));

  // ---------- ausgeschaltet, Mitarbeiter angelegt ----------
  await ruf(p, 'POST', 'mitarbeiter', { vorname: 'Max', nachname: 'Werk', lohnart: 'minijob', stundenlohn: 14, eintritt: '2026-01-01' });
  await start(p);
  ok('mit einem Mitarbeiter: Hinweis für den Inhaber, die Erinnerungen einzuschalten', (await p.locator('#stASAus').count()) === 1 && /ausgeschaltet, es ist aber 1 Mitarbeiter angelegt/.test(await text(p, '#stASAus'))
     && /Gefährdungsbeurteilung und Unterweisungen/.test(await text(p, '#stASAus')) && (await p.locator('#stASHinweis').count()) === 0, await text(p, '#stAS'));
  await p.screenshot({ path: BILD + '/4_start_hinweis.png' });
  await p.click('#stASAus a'); await p.waitForSelector('#startAS'); await p.waitForSelector('#startASWarn', { state: 'visible', timeout: 8000 });
  ok('der Hinweis führt zum Schalter; dort steht die Warnung mit der Zahl der Mitarbeiter', (await p.isVisible('#startAS')) && !(await p.isChecked('#startAS')) && (await p.isVisible('#startASWarn')) && /Es ist 1 Mitarbeiter angelegt: Die Erinnerungen sollten eingeschaltet sein/.test(await text(p, '#startASWarn')), await text(p, '#startASWarn'));
  await p.screenshot({ path: BILD + '/5_schalter_warnung.png' });
  await p.check('#startAS'); ok('eingeschaltet verschwindet die Warnung sofort', !(await p.isVisible('#startASWarn')));
  await p.uncheck('#startAS'); ok('… und kommt beim Ausschalten wieder', await p.isVisible('#startASWarn'));
  await ruf(p, 'POST', 'mitarbeiter', { vorname: 'Nina', nachname: 'Neu', lohnart: 'stunde', stundenlohn: 18, eintritt: '2026-01-01' });
  await start(p); ok('Mehrzahl: „es sind aber 2 Mitarbeiter angelegt“', /es sind aber 2 Mitarbeiter angelegt/.test(await text(p, '#stASAus')), await text(p, '#stAS'));

  // ---------- andere Benutzer, solange ausgeschaltet ----------
  const ctx2 = await b.newContext({ viewport: { width: 1400, height: 950 }, locale: 'de-DE' }); const q = await ctx2.newPage(); q.on('pageerror', e => stoerung.push('Skript (Büro): ' + String(e).slice(0, 160)));
  await q.goto(U + '/'); await q.waitForSelector('[name=login]'); await q.fill('[name=login]', 'berta'); await q.fill('[name=passwort]', 'Pruefung#2026'); await q.click('#anmForm button[type=submit]'); await q.waitForSelector('#leiste', { timeout: 20000 });
  await start(q);
  ok('Begrüßung nennt den angemeldeten Benutzer, nicht den Inhaber', /, Berta$/.test(await text(q, '#inhalt .titel h2')) && /, Jonas$/.test(await (async () => { await start(p); return text(p, '#inhalt .titel h2'); })()), await text(q, '#inhalt .titel h2'));
  ok('Büro: weder Erinnerung noch Hinweis (einschalten kann nur der Inhaber)', (await q.locator('#stASHinweis').count()) === 0 && (await q.locator('#stASAus').count()) === 0, await text(q, '#stAS'));
  await q.goto(U + '/#/arbeitsschutz'); await q.waitForSelector('.as-zwei');
  ok('Büro sieht in der Übersicht den Vermerk, ohne Verweis auf die Einstellungen', /ausgeschaltet/.test(await text(q, '#asStartAus')) && (await q.locator('#asStartAus a').count()) === 0, await text(q, '#asStartAus'));

  // Werkstatt hat keine Startseite und bekam die Erinnerung nie: dort steht auch kein Vermerk
  const ctx3 = await b.newContext({ viewport: { width: 1400, height: 950 }, locale: 'de-DE' }); const w = await ctx3.newPage(); w.on('pageerror', e => stoerung.push('Skript (Werkstatt): ' + String(e).slice(0, 160)));
  await w.goto(U + '/'); await w.waitForSelector('[name=login]'); await w.fill('[name=login]', 'willi'); await w.fill('[name=passwort]', 'Pruefung#2026'); await w.click('#anmForm button[type=submit]');
  await w.waitForFunction(() => typeof ICH === 'object' && ICH && ICH.login === 'willi' && location.hash.length > 2, null, { timeout: 20000 }); await w.waitForSelector('#inhalt .titel'); await w.waitForTimeout(400);
  await w.goto(U + '/#/arbeitsschutz'); await w.waitForSelector('.as-zwei');
  ok('Werkstatt (ohne Startseite): Übersicht mit den Punkten, aber ohne Vermerk zur Startseite', (await w.locator('.as-punkte li').count()) >= 1 && (await w.locator('#asStartAus').count()) === 0, await text(w, '#inhalt'));
  await ctx3.close();

  // ---------- wieder einschalten ----------
  await p.goto(U + '/#/einstellungen/programm'); await p.waitForSelector('#startAS'); await p.check('#startAS'); await p.click('#sp'); await p.waitForTimeout(700);
  await start(p);
  ok('eingeschaltet: Erinnerung wieder da, Hinweis weg', (await p.locator('#stASHinweis').count()) === 1 && (await p.locator('#stASAus').count()) === 0, await text(p, '#stAS'));
  await start(q);
  ok('Büro bekommt die Erinnerung ohne Neuanmeldung wieder (Stand der Startseite zählt, nicht die geladenen Einstellungen)', (await q.locator('#stASHinweis').count()) === 1, await text(q, '#stAS'));
  await p.goto(U + '/#/arbeitsschutz'); await p.waitForSelector('.as-zwei'); ok('Übersicht ohne Vermerk', (await p.locator('#asStartAus').count()) === 0);
  await p.goto(U + '/#/einstellungen/service/protokoll'); await p.waitForTimeout(1800);
  const prot = await text(p, '#inhalt');
  ok('Protokoll: aus- und eingeschaltet festgehalten', /Erinnerungen des Arbeitsschutzes auf der Startseite ausgeschaltet/.test(prot) && /Erinnerungen des Arbeitsschutzes auf der Startseite eingeschaltet/.test(prot), prot.slice(0, 400));

  // ---------- schmales Fenster ----------
  await ruf(p, 'PUT', 'einstellungen', { start_arbeitsschutz: false });
  await p.setViewportSize({ width: 430, height: 900 }); await p.goto(U + '/'); await p.waitForSelector('#stJahr'); await start(p);
  ok('schmales Fenster: Hinweis ohne waagerechtes Überlaufen', (await p.locator('#stASAus').count()) === 1 && await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
  await p.screenshot({ path: BILD + '/6_schmal.png' });
  await p.goto(U + '/#/einstellungen/programm'); await p.waitForSelector('#startAS');
  ok('schmales Fenster: Schalter und Hinweistext ohne Überlaufen', await p.evaluate(() => { const z = document.querySelector('#startAS').closest('.zeile').getBoundingClientRect(); return z.right <= window.innerWidth + 1 && document.documentElement.scrollWidth <= window.innerWidth + 1; }));
  ok('keine Skriptfehler, keine Meldungen der Konsole', stoerung.length === 0, stoerung);
  await b.close();
  console.log('FEHLER: ' + JSON.stringify(fehler));
})().catch(e => { console.log('FEHLER Abbruch → ' + e.stack); console.log('FEHLER: ["Abbruch"]'); process.exit(1); });
