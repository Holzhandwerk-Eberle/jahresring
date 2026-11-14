const { chromium } = require('playwright'); const U='http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({viewport:{width:1300,height:900}})).newPage();
  await p.goto(U+'/'); await p.waitForTimeout(600); await p.fill('[name=login]','jonas'); await p.fill('[name=passwort]','geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1200);
  for (const r of ['#/auftrag/10', '#/auftrag/10/positionen', '#/kunde/2', '#/kunden', '#/kalender', '#/lieferant/1', '#/zahlungen', '#/material/holzwerkstoffe', '#/personal', '#/einstellungen/benutzer', '#/start', '#/leitstand', '#/projekte']) {
    await p.evaluate(h => { location.hash = h; }, r); await p.waitForTimeout(900);
    const x = await p.evaluate(() => ({sichtbar: (document.body.innerText.match(/onerror=/g) || []).length, img: document.querySelectorAll('img[src="x"]').length, xss: window.__xss || 0}));
    console.log(r.padEnd(28), JSON.stringify(x)); }
  // Druckansichten und Suche (serverseitig erzeugtes HTML)
  for (const u of ['/api/belege/10/druck', '/api/belege/11/druck', '/api/suche?q=img', '/api/kalender/export.ics', '/zertifikat', '/stempel']) {
    const t = await p.evaluate(async u => { const r = await fetch(u); return r.status + ' ' + (await r.text()); }, u);
    console.log(u.padEnd(28), t.slice(0, 3), 'roh <img src=x:', (t.match(/<img src=x onerror/g) || []).length, 'maskiert:', (t.match(/&lt;img src=x/g) || []).length); }
  const bl = await p.evaluate(async () => (await (await fetch('/api/belege')).json()).slice(0, 4).map(x => x.id));
  for (const id of bl) { const pg = await (await b.newContext()).newPage(); await pg.context().addCookies(await p.context().cookies()); await pg.goto(U + '/druck/' + id).catch(() => {}); await pg.waitForTimeout(800); console.log('Druckseite', id, pg.url().slice(-12), await pg.evaluate(() => ({xss: window.__xss || 0, img: document.querySelectorAll('img[src="x"]').length, len: document.body.innerText.length}))); }
  await b.close(); })();
