// Version 152: Seitenwechsel, während die vorige Seite noch Daten holt. Die späte Antwort einer verlassenen Seite darf die verlangte
// nicht verdrängen (Abrufe künstlich verzögert). Baut sich die Prüfinstanz selbst auf. Aufruf: cd /tmp/claude-0/t/v25 && cp ../neu/seitenwechsel.js s/ && node s/seitenwechsel.js
const { chromium } = require('playwright'); const { execSync } = require('child_process');
const U = 'http://127.0.0.1:8799'; const fehler = [];
(async () => {
  if (!process.env.OHNE_NEU) execSync('bash /tmp/claude-0/t/v25/neu.sh >/dev/null 2>&1; sleep 1; python3 /tmp/claude-0/t/neu/spur_seed.py > /dev/null 2>&1', { timeout: 300000 });
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1400, height: 950 }, locale: 'de-DE' }); const p = await ctx.newPage();
  await p.goto(U + '/'); await p.waitForSelector('[name=login]'); await p.waitForTimeout(300); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim12345'); await p.click('button[type=submit]'); await p.waitForSelector('#leiste');
  await p.waitForTimeout(800);
  const kid = await p.evaluate(async () => (await (await fetch('/api/kunden?status=alle')).json())[0].id);
  for (const [name, langsam, erst, dann, erwartet] of [
    ['Kunde (langsam) → Aufträge', `**/api/kunden/${kid}`, `#/kunde/${kid}`, '#/auftraege', /Aufträge/],
    ['Aufträge (langsam) → Kunden', '**/api/auftraege*', '#/auftraege', '#/kunden', /Kunden/],
    ['Statistik (langsam) → Lieferanten', '**/api/statistik*', '#/statistik', '#/lieferanten', /Lieferanten/]]) {
    await p.route(langsam, async r => { await new Promise(x => setTimeout(x, 1500)); await r.continue(); });
    await p.evaluate(h => { location.hash = h; }, erst); await p.waitForTimeout(150);
    await p.evaluate(h => { location.hash = h; }, dann);
    // 2,6 Sekunden lang alle 60 ms den Titel lesen: Die verlangte Seite muss erscheinen und darf nicht mehr von der alten verdrängt werden
    const gesehen = []; for (let i = 0; i < 43; i++) { await p.waitForTimeout(60); const tt = await p.evaluate(() => (document.querySelector('#inhalt .titel h2') || {}).innerText || ''); if (gesehen[gesehen.length - 1] !== tt) gesehen.push(tt); }
    const x = await p.evaluate(() => ({ hash: location.hash, titel: (document.querySelector('#inhalt .titel h2') || {}).innerText || '' }));
    const erste = gesehen.findIndex(tt => erwartet.test(tt)), danachAnders = erste >= 0 && gesehen.slice(erste).some(tt => !erwartet.test(tt));
    const gut = erwartet.test(x.titel) && !danachAnders;
    if (!gut) fehler.push(name);
    console.log((gut ? 'ok   ' : 'FEHLER ') + name + ': Adresse ' + x.hash + ', Seite zeigt „' + x.titel + '“; Abfolge der Titel: ' + gesehen.map(tt => '„' + tt + '“').join(' → '));
    await p.unroute(langsam); await p.evaluate(() => { location.hash = '#/start'; }); await p.waitForTimeout(700); }
  // Zweiter Fall: Der erste Abruf der alten Seite kommt rechtzeitig, erst ein späterer trifft nach dem Wechsel ein. Dann darf die alte
  // Seite kurz aufscheinen, am Ende muss die verlangte stehen.
  for (const [name, erst, dann, erwartet] of [['Kunde, Reiter Aufträge (zweiter Abruf langsam) → Lieferanten', `#/kunde/${kid}/auftraege`, '#/lieferanten', /Lieferanten/],
                                              ['Kunde, Reiter Offene Posten (zweiter Abruf langsam) → Aufträge', `#/kunde/${kid}/op`, '#/auftraege', /Aufträge/]]) {
    let n = 0, scharf = true;
    await p.route('**/api/**', async r => { if (scharf && r.request().method() === 'GET' && ++n > 1) await new Promise(x => setTimeout(x, 1500)); await r.continue(); });
    await p.evaluate(h => { location.hash = h; }, erst); await p.waitForTimeout(400); scharf = false;
    await p.evaluate(h => { location.hash = h; }, dann);
    const gesehen = []; for (let i = 0; i < 50; i++) { await p.waitForTimeout(60); const tt = await p.evaluate(() => (document.querySelector('#inhalt .titel h2') || {}).innerText || ''); if (gesehen[gesehen.length - 1] !== tt) gesehen.push(tt); }
    const x = await p.evaluate(() => ({ hash: location.hash, titel: (document.querySelector('#inhalt .titel h2') || {}).innerText || '' }));
    const gut = erwartet.test(x.titel); if (!gut) fehler.push(name);
    console.log((gut ? 'ok   ' : 'FEHLER ') + name + ': Adresse ' + x.hash + ', Seite zeigt am Ende „' + x.titel + '“; Abfolge der Titel: ' + gesehen.map(tt => '„' + tt + '“').join(' → ') + ` (${n} Abrufe der alten Seite)`);
    await p.unroute('**/api/**'); await p.evaluate(() => { location.hash = '#/start'; }); await p.waitForTimeout(700); }
  // Dritter Fall: Seitenwechsel, während das Programm noch startet (Einstellungen kommen verzögert). Bis Version 151 scheiterte dann der
  // Aufbau der Kopfleiste, und jede Seite zeigte nur noch eine Fehlermeldung.
  { const c2 = await b.newContext({ viewport: { width: 1400, height: 950 }, locale: 'de-DE' }); const q = await c2.newPage(); const skript = [];
    q.on('pageerror', e => skript.push(String(e).slice(0, 160)));
    await q.goto(U + '/'); await q.waitForSelector('[name=login]'); await q.fill('[name=login]', 'jonas'); await q.fill('[name=passwort]', 'geheim12345');
    await q.route('**/api/einstellungen', async r => { await new Promise(x => setTimeout(x, 900)); await r.continue(); });
    await q.click('button[type=submit]'); await q.waitForSelector('#leiste'); await q.waitForTimeout(250);
    const vorher = await q.evaluate(() => ({ leiste: !!document.querySelector('#lbIch'), gestartet: typeof gestartet !== 'undefined' && gestartet }));
    await q.evaluate(() => { location.hash = '#/kunden'; }); await q.waitForTimeout(2500);
    const x = await q.evaluate(() => ({ hash: location.hash, titel: (document.querySelector('#inhalt .titel h2') || {}).innerText || '', inhalt: (document.querySelector('#inhalt') || {}).innerText.slice(0, 80), leiste: !!document.querySelector('#lbIch') }));
    const gut = !vorher.gestartet && /Kunden/.test(x.titel) && x.leiste && !/Fehler/.test(x.inhalt) && skript.length === 0; if (!gut) fehler.push('Seitenwechsel während des Programmstarts');
    console.log((gut ? 'ok   ' : 'FEHLER ') + 'Seitenwechsel während des Programmstarts: die verlangte Seite steht, die Kopfleiste ist aufgebaut, keine Fehlermeldung ' + JSON.stringify({ vorher, ...x, skript }));
    await c2.close(); }
  // Gegenprobe: ohne Verzögerung wechselt die Seite wie gewohnt, auch zweimal dieselbe Adresse und schnelles Hin und Her
  for (const h of ['#/kunden', '#/auftraege', '#/kunden', '#/lieferanten', '#/start']) { await p.evaluate(x => { location.hash = x; }, h); await p.waitForTimeout(40); }
  await p.waitForTimeout(1200);
  const ende = await p.evaluate(() => ({ hash: location.hash, da: !!document.querySelector('#stJahr') }));
  if (!ende.da) fehler.push('schnelles Hin und Her');
  console.log((ende.da ? 'ok   ' : 'FEHLER ') + 'schnelles Hin und Her über fünf Seiten endet auf der Startseite: ' + JSON.stringify(ende));
  console.log('FEHLER:', JSON.stringify(fehler)); await b.close(); })();
