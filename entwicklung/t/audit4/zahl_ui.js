// Zahleneingabe im deutschen Format in der Oberfläche
const { chromium } = require('playwright');
const U = 'http://127.0.0.1:8799';
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1500, height: 950 }, locale: 'de-DE' }); const p = await ctx.newPage();
  const api = async (m, pf, d) => await p.evaluate(async ([m, pf, d]) => { const r = await fetch('/api/' + pf, { method: m, headers: { 'Content-Type': 'application/json' }, body: d ? JSON.stringify(d) : undefined }); return await r.json(); }, [m, pf, d]);
  await p.goto(U + '/'); await p.waitForTimeout(800); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1500);
  const k = await api('POST', 'kunden', { kurzname: 'Zahl, Zora', plz: '88069', ort: 'Tettnang' });
  const a = await api('POST', 'auftraege', { kunde_id: k.id, bezeichnung: 'Zahlentest' });
  const po = await api('POST', `auftraege/${a.id}/positionen`, { text: 'Tisch' }); const pid = po.id || po.position.id;
  await p.evaluate(h => { location.hash = h; }, `#/auftrag/${a.id}`); await p.waitForTimeout(1500);
  // alle Eingabefelder der Positionsliste auflisten
  const felder = await p.evaluate(() => [...document.querySelectorAll('#inhalt input')].map(i => ({ name: i.name || i.dataset.f || i.dataset.feld || i.className, type: i.type, mode: i.inputMode, val: i.value })).slice(0, 40));
  console.log('Felder in der Auftragsansicht:', JSON.stringify(felder).slice(0, 900));
  await p.screenshot({ path: '/tmp/claude-0/t/audit4/shots/zahl_auftrag.png' });
  await p.evaluate(h => { location.hash = h; }, `#/position/${pid}`); await p.waitForTimeout(1800);
  const felder2 = await p.evaluate(() => [...document.querySelectorAll('#inhalt input')].map(i => ({ name: i.name || i.id || i.dataset.f || i.dataset.feld || i.className, type: i.type, mode: i.inputMode, val: i.value })).slice(0, 60));
  console.log('Felder in der Position:', JSON.stringify(felder2).slice(0, 1800));
  await p.screenshot({ path: '/tmp/claude-0/t/audit4/shots/zahl_position.png', fullPage: true });
  await b.close();
})();
