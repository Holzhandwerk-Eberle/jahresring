const { chromium } = require('playwright');
const U = 'http://127.0.0.1:8799';
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1500, height: 950 }, locale: 'de-DE' }); const p = await ctx.newPage();
  const api = async (m, pf, d) => await p.evaluate(async ([m, pf, d]) => { const r = await fetch('/api/' + pf, { method: m, headers: { 'Content-Type': 'application/json' }, body: d ? JSON.stringify(d) : undefined }); return await r.json(); }, [m, pf, d]);
  await p.goto(U + '/'); await p.waitForTimeout(800); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1500);
  const k = await api('POST', 'kunden', { kurzname: 'Zahl2, Zora', plz: '88069', ort: 'Tettnang' });
  const a = await api('POST', 'auftraege', { kunde_id: k.id, bezeichnung: 'Zahlentest2' });
  const po = await api('POST', `auftraege/${a.id}/positionen`, { text: 'Tisch' }); const pid = po.id || po.position.id;
  for (const eingabe of ['1.500', '1.234,56', '12,5', '1500', '1.5', '2.000.000', '1 500', '1.500,00 €', '=1+1', '']) {
    await p.evaluate(h => { location.hash = h; }, `#/position/${pid}`); await p.waitForTimeout(900);
    const ep = await p.$('#ep'); if (!ep) { console.log('kein #ep'); break; }
    await ep.click({ clickCount: 3 }); await p.keyboard.press('Control+A'); await p.keyboard.type(eingabe); await p.keyboard.press('Tab'); await p.waitForTimeout(700);
    const anzeige = await p.evaluate(() => document.querySelector('#ep') ? document.querySelector('#ep').value : null);
    const toast = await p.evaluate(() => [...document.querySelectorAll('.toast, #toast, .meldung')].map(x => x.textContent.trim()).filter(Boolean).join(' | ').slice(0, 120));
    const pos = await api('GET', `auftraege/${a.id}/positionen`); const z = (pos.positionen || pos)[0];
    console.log(`Eingabe Einzelpreis „${eingabe}“ → Feld zeigt „${anzeige}“, gespeichert einzelpreis=${z.einzelpreis} ${toast ? '| Meldung: ' + toast : ''}`);
  }
  // Mengenfeld
  for (const eingabe of ['2,5', '1.000', '0,5']) {
    await p.evaluate(h => { location.hash = h; }, `#/position/${pid}`); await p.waitForTimeout(900);
    const m = (await p.$$('#inhalt input.zahl'))[0]; await m.click({ clickCount: 3 }); await p.keyboard.press('Control+A'); await p.keyboard.type(eingabe); await p.keyboard.press('Tab'); await p.waitForTimeout(700);
    const pos = await api('GET', `auftraege/${a.id}/positionen`); const z = (pos.positionen || pos)[0];
    console.log(`Eingabe Menge „${eingabe}“ → gespeichert menge=${z.menge}`);
  }
  await b.close();
})();
