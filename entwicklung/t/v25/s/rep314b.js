// Nach der Anmeldung sofort auf eine andere Seite wechseln (wie startas_ui) und festhalten, was die Seite zeigt, wenn der Titel ausbleibt
const { chromium } = require('playwright'); const { execSync } = require('child_process');
const U = 'http://127.0.0.1:8799';
(async () => {
  execSync('bash /tmp/claude-0/t/v25/neu.sh', { stdio: 'ignore' });
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1400, height: 950 }, locale: 'de-DE' }); const p = await ctx.newPage();
  const t0 = Date.now(); const z = () => ((Date.now() - t0) / 1000).toFixed(1).padStart(5) + ' s';
  await p.goto(U + '/'); await p.waitForSelector('#anmForm');
  await p.evaluate(async () => { await fetch('/api/anmeldung/einrichten', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'Jonas', login: 'jonas', passwort: 'geheim12345', passwort2: 'geheim12345', firma: 'Muster' }) }); });
  await p.goto(U + '/'); await p.waitForSelector('#leiste', { timeout: 20000 });
  await p.evaluate(async () => { await fetch('/api/benutzer', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'Berta Büro', login: 'berta', passwort: 'Pruefung#2026', rolle: 'buero' }) }); });
  let haenger = 0;
  for (let i = 1; i <= +(process.argv[2] || 12); i++) {
    const c = await b.newContext({ viewport: { width: 1400, height: 950 }, locale: 'de-DE' }); const q = await c.newPage(); const netz = [];
    q.on('request', r => { if (r.url().includes('/api/')) netz.push(`→ ${r.method()} ${r.url().replace(U, '')}`); });
    q.on('response', r => { if (r.url().includes('/api/')) netz.push(`${r.status()} ${r.url().replace(U, '')}`); });
    q.on('pageerror', e => netz.push('SKRIPTFEHLER: ' + String(e).slice(0, 300)));
    q.on('console', m => { if (m.type() === 'error') netz.push('KONSOLE: ' + m.text().slice(0, 200)); });
    q.on('framenavigated', f => { if (f === q.mainFrame()) netz.push('NAVIGATION ' + f.url().replace(U, '')); });
    await q.goto(U + '/'); await q.waitForSelector('[name=login]'); await q.fill('[name=login]', 'berta'); await q.fill('[name=passwort]', 'Pruefung#2026');
    await q.click('#anmForm button[type=submit]'); await q.waitForSelector('#leiste', { timeout: 20000 });
    netz.push('--- #leiste da, Wechsel auf #/kunden');
    await q.goto(U + '/#/kunden');
    try { await q.waitForSelector('#inhalt .titel', { timeout: 8000 }); }
    catch (e) { haenger++; console.log(z(), `Runde ${i}: KEIN TITEL nach 8 s`);
      console.log('   Zustand:', JSON.stringify(await q.evaluate(() => ({ hash: location.hash, inhalt: (document.querySelector('#inhalt') || {}).innerText?.slice(0, 200), koerper: document.body.innerText.slice(0, 120).replace(/\s+/g, ' '), ich: typeof ICH === 'undefined' ? 'undefiniert' : (ICH && ICH.login), E: typeof E === 'undefined' ? 'undefiniert' : Object.keys(E || {}).length, lauf: typeof seitenLauf === 'undefined' ? null : [seitenLauf, seitenFertig, API_LAUF], wrap: !!document.querySelector('.wrap') }))));
      console.log('   Ablauf:', netz.slice(-28).join(' | ')); if (haenger >= 2) break; }
    await c.close(); }
  console.log(haenger ? `${haenger} Hänger` : 'kein Hänger'); await b.close(); })();
