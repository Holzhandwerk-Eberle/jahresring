const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1250, height: 900 } })).newPage();
  const fehler = []; p.on('pageerror', e => fehler.push(e.message));
  await p.goto('http://127.0.0.1:8799/api/anmeldung/status').catch(() => {});
  await p.evaluate(async () => { await fetch('/api/anmeldung/einrichten', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'Jonas', login: 'jonas', passwort: 'geheim12345', passwort2: 'geheim12345', firma: 'Muster' }) }); });
  for (const [seite, anker, name] of [['handbuch.html', '#fremdbausteine', 'h_fremd'], ['handbuch.html', '#anonymisieren', 'h_anon'], ['handbuch.html', '#drucken', 'h_druck'], ['installation.html', '', 'inst']]) {
    const r = await p.goto('http://127.0.0.1:8799/hilfe/' + seite + anker); await p.waitForTimeout(700);
    console.log(seite, anker, r && r.status(), await p.title());
    if (anker) await p.evaluate(a => { const e = document.querySelector(a); if (e) e.scrollIntoView(); }, anker);
    await p.waitForTimeout(300); await p.screenshot({ path: '/tmp/claude-0/t/audit4/shots149/' + name + '.png' });
  }
  console.log('Fehler', fehler); await b.close(); })();
