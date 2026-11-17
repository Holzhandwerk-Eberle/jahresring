const { chromium } = require('playwright'); const fs = require('fs');
const U = 'http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1400, height: 950 } }); const p = await ctx.newPage(); p.on('dialog', d => d.dismiss());
  await p.addInitScript(() => { window.print = () => { window.__gedruckt = (window.__gedruckt || 0) + 1; }; });
  await p.goto(U + '/'); await p.waitForTimeout(800); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1200);
  const api = async (m, pf, d) => await p.evaluate(async ([m, pf, d]) => { const r = await fetch('/api/' + pf, { method: m, headers: { 'Content-Type': 'application/json' }, body: d ? JSON.stringify(d) : undefined }); return await r.json(); }, [m, pf, d]);
  for (const ue of [false, true]) {
    await p.goto(U + '/#/start'); await p.waitForTimeout(400);
    const r = await api('PUT', 'belege/18', { druck: { uebertrag: ue } });
    await p.goto(U + `/druck/18?drucken=1`); await p.waitForTimeout(2500);
    const info = await p.evaluate(() => ({ gedruckt: window.__gedruckt || 0, klassen: document.documentElement.className, body: document.body.className, medien: [...document.styleSheets].length }));
    await p.emulateMedia({ media: 'print' });
    await p.pdf({ path: `/tmp/claude-0/t/audit4/ue/dw2_${ue ? 'mit' : 'ohne'}.pdf`, preferCSSPageSize: true, printBackground: true });
    await p.emulateMedia({ media: 'screen' });
    console.log('Übertrag', ue, JSON.stringify(info));
  }
  await b.close(); })();
