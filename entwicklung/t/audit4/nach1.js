const { chromium } = require('playwright');
const U = 'http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1400, height: 950 } }); const p = await ctx.newPage(); p.on('dialog', d => d.dismiss());
  await p.addInitScript(() => { window.print = () => { window.__gedruckt = (window.__gedruckt || 0) + 1; }; });
  await p.goto(U + '/'); await p.waitForTimeout(800); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1200);
  const api = async (m, pf, d) => await p.evaluate(async ([m, pf, d]) => { const r = await fetch('/api/' + pf, { method: m, headers: { 'Content-Type': 'application/json' }, body: d ? JSON.stringify(d) : undefined }); let j = null; try { j = await r.json(); } catch (e) {} return { s: r.status, j }; }, [m, pf, d]);
  // Brief über den Druckweg
  const kl = (await api('GET', 'kunden')).j; const kid = kl[0].id;
  const br = await api('POST', 'briefe', { kunde_id: kid, betreff: 'Terminbestätigung', text: 'Sehr geehrte Damen und Herren,\n\nhiermit bestätige ich den Termin.\n\nMit freundlichen Grüßen' });
  console.log('Brief', br.s, br.j && br.j.id);
  if (br.j && br.j.id) { await p.goto(U + `/druck/brief/${br.j.id}`); await p.waitForTimeout(2000); await p.pdf({ path: '/tmp/claude-0/t/audit4/ue/dw_brief.pdf', preferCSSPageSize: true, printBackground: false }); }
  // Werkstatt-Benutzer: was bietet der Reiter Werkstatt an?
  await p.goto(U + '/#/start'); await p.waitForTimeout(500);
  const m = await api('POST', 'mitarbeiter', { vorname: 'Max', nachname: 'Werk' });
  const u = await api('POST', 'benutzer', { name: 'werk', login: 'werk', passwort: 'Pruefung#2026', rolle: 'werkstatt', mitarbeiter_id: (m.j.id || (m.j.mitarbeiter || {}).id) }); console.log('Benutzer werk', u.s, u.j && u.j.fehler);
  const auf = (await api('GET', 'auftraege?status=')).j; const aid = auf[0].id;
  const ctx2 = await b.newContext({ viewport: { width: 1400, height: 950 } }); const q = await ctx2.newPage();
  await q.goto(U + '/'); await q.waitForTimeout(800); await q.fill('[name=login]', 'werk'); await q.fill('[name=passwort]', 'Pruefung#2026'); await q.click('button[type=submit]'); await q.waitForTimeout(1500);
  await q.evaluate(h => { location.hash = h; }, `#/auftrag/${aid}/werkstatt`); await q.waitForTimeout(1500);
  const karten = await q.evaluate(() => [...document.querySelectorAll('.ws-karte')].map(e => e.innerText.split('\n')[0]));
  const nav = await q.evaluate(() => [...document.querySelectorAll('nav a, .lb-nav a, header a')].map(e => e.innerText.trim()).filter(Boolean).slice(0, 20));
  console.log('Werkstatt-Benutzer sieht im Reiter Werkstatt die Papiere:', JSON.stringify(karten)); console.log('Navigation:', JSON.stringify(nav));
  await q.screenshot({ path: '/tmp/claude-0/t/audit4/shots/werk_werkstatt.png' });
  for (const pf of [`/papier/${aid}/kosten`, `/papier/${aid}/sollist`, '/liste/lager', '/liste/werkzeuge']) { const r = await q.goto(U + pf); const t = await q.evaluate(() => document.body.innerText); console.log('  ', pf, r.status(), /€/.test(t) ? 'mit €-Beträgen' : 'ohne Beträge', (t.match(/Selbstkosten|W&G|Lagerwert|Preis netto|Anschaffungswert/g) || []).slice(0, 4)); }
  await b.close(); })();
