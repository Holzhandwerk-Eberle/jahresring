const { chromium } = require('playwright');
const U = 'http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1400, height: 950 } }); const p = await ctx.newPage(); p.on('dialog', d => d.dismiss());
  await p.addInitScript(() => { window.print = () => { window.__gedruckt = (window.__gedruckt || 0) + 1; }; });
  await p.goto(U + '/'); await p.waitForTimeout(800); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1200);
  const api = async (m, pf, d) => await p.evaluate(async ([m, pf, d]) => { const r = await fetch('/api/' + pf, { method: m, headers: { 'Content-Type': 'application/json' }, body: d ? JSON.stringify(d) : undefined }); return await r.json(); }, [m, pf, d]);
  const k = await api('POST', 'kunden', { kurzname: 'Einseitig, Erna', nachname: 'Einseitig', plz: '88069', ort: 'Tettnang' });
  const a = await api('POST', 'auftraege', { kunde_id: k.id, bezeichnung: 'Regal' });
  const po = await api('POST', `auftraege/${a.id}/positionen`, { text: 'Regal Eiche' }); await api('PUT', `positionen/${po.id || po.position.id}`, { einzelpreis: 480, preis_manuell: 1, menge: 1 });
  const an = await api('POST', `auftraege/${a.id}/belege`, { art: 'angebot' });
  await p.goto(U + `/druck/${an.id}?drucken=1`); await p.waitForTimeout(2500);
  await p.pdf({ path: '/tmp/claude-0/t/audit4/ue/dw3_einseitig.pdf', preferCSSPageSize: true, printBackground: false });
  // Mahnung / Brief / Werkstattpapier ebenfalls über den Druckweg?
  console.log('Angebot', an.id);
  await b.close(); })();
