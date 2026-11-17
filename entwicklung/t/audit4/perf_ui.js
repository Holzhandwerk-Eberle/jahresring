// Ladezeiten der Hauptseiten im Browser bei sehr großer Datenbank (wartet auf offene Anfragen und ruhiges DOM)
const { chromium } = require('playwright');
const U = process.argv[2] || 'http://127.0.0.1:8797';
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1500, height: 950 } }); const p = await ctx.newPage();
  await p.addInitScript(() => { window.__offen = 0; window.__letzte = performance.now(); const f = window.fetch; window.fetch = function () { window.__offen++; return f.apply(this, arguments).then(async r => { const k = r.clone(); try { await k.arrayBuffer(); } catch (e) {} window.__offen--; window.__letzte = performance.now(); return r; }, e => { window.__offen--; window.__letzte = performance.now(); throw e; }); }; });
  const fehler = []; p.on('pageerror', e => fehler.push(String(e).slice(0, 200)));
  let anfragen = []; p.on('response', async r => { const u = r.url(); if (u.includes('/api/')) { try { const body = await r.body(); anfragen.push([u.replace(U, ''), body.length]); } catch (e) {} } });
  const ruhig = async (max = 90000) => { await p.waitForTimeout(250); await p.evaluate(max => new Promise(ok => { const t0 = performance.now(); let dom = performance.now(); const o = new MutationObserver(() => { dom = performance.now(); }); o.observe(document.body, { childList: true, subtree: true }); const i = setInterval(() => { const n = performance.now(); if ((window.__offen === 0 && n - window.__letzte > 500 && n - dom > 500) || n - t0 > max) { clearInterval(i); o.disconnect(); ok(); } }, 50); }), max); };
  await p.goto(U + '/'); await p.waitForTimeout(800); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); const ta = Date.now(); await p.click('button[type=submit]'); await ruhig(); console.log('Anmeldung bis Startseite fertig:', Date.now() - ta - 750, 'ms');
  const routen = ['#/kunden', '#/auftraege', '#/op', '#/zahlungen', '#/lieferanten', '#/material', '#/kalender', '#/personal', '#/projekte', '#/leitstand', '#/arbeitsschutz', '#/start', '#/einstellungen'];
  for (const r of routen) {
    anfragen = []; const t0 = Date.now();
    await p.evaluate(h => { location.hash = h; }, r); await ruhig();
    const dauer = Date.now() - t0 - 750;
    const m = await p.evaluate(() => ({ knoten: document.querySelectorAll('*').length, zeilen: document.querySelectorAll('tr').length, heap: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : 0 }));
    const sum = anfragen.reduce((a, x) => a + x[1], 0);
    const gross = anfragen.sort((a, b) => b[1] - a[1]).slice(0, 2).map(a => `${a[0].slice(0, 40)} ${(a[1] / 1048576).toFixed(1)} MB`);
    console.log(`${r.padEnd(16)} ${String(dauer).padStart(6)} ms | ${anfragen.length} Anfragen ${(sum / 1048576).toFixed(1)} MB | DOM ${String(m.knoten).padStart(6)} Knoten ${String(m.zeilen).padStart(5)} Zeilen | Speicher ${m.heap} MB | ${gross.join(' ; ')}`);
    await p.screenshot({ path: `/tmp/claude-0/t/audit4/shots/perf_${r.replace(/[#/]/g, '') || 'start'}.png` });
  }
  await p.evaluate(() => { location.hash = '#/kunden'; }); await ruhig();
  const such = await p.$('main input[type=search], main input[placeholder*="uche"], #inhalt input[type=search], input[type=search]');
  if (such) { const t0 = Date.now(); await such.type('Wolf, Karin', { delay: 40 }); await ruhig(); console.log('Kundensuche „Wolf, Karin“ (11 Zeichen):', Date.now() - t0 - 750 - 11 * 40, 'ms nach dem Tippen; Zeilen:', await p.evaluate(() => document.querySelectorAll('tr').length)); }
  let t1 = Date.now(); await p.evaluate(() => { location.hash = '#/auftrag/21'; }); await ruhig(); console.log('Auftrag öffnen:', Date.now() - t1 - 750, 'ms');
  t1 = Date.now(); await p.evaluate(() => { location.hash = '#/kunde/39'; }); await ruhig(); console.log('Kunde öffnen:', Date.now() - t1 - 750, 'ms');
  console.log('Fehler im Browser:', fehler.length, fehler.slice(0, 5));
  await b.close();
})();
