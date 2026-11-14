const { chromium } = require('playwright');
const U='http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({viewport:{width:1400,height:950}})).newPage(); p.setDefaultTimeout(10000);
  const fehler = []; let route = '';
  p.on('pageerror', e => fehler.push(`[JS] ${route}: ${e.message}`));
  p.on('console', m => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) fehler.push(`[Konsole] ${route}: ${m.text().slice(0,200)}`); });
  p.on('response', r => { if (r.url().includes('/api/') && r.status() >= 500) fehler.push(`[HTTP ${r.status()}] ${route}: ${r.url().replace(U,'')}`); });
  p.on('dialog', d => d.dismiss());
  await p.goto(U+'/'); await p.waitForTimeout(800);
  if (await p.$('[name=passwort2]')) { await p.fill('[name=name]','Jonas'); await p.fill('[name=login]','jonas').catch(()=>{}); await p.fill('[name=passwort]','geheim123'); await p.fill('[name=passwort2]','geheim123'); }
  else { await p.fill('[name=login]','jonas'); await p.fill('[name=passwort]','geheim123'); }
  await p.click('button[type=submit]'); await p.waitForTimeout(1500);
  const api = pfad => p.evaluate(async pfad => { const r = await fetch('/api/'+pfad); return r.json().catch(()=>null); }, pfad);
  const ids = async (pfad) => { const j = await api(pfad); const l = Array.isArray(j) ? j : (j && (j.liste || j.eintraege || j.zeilen)) || []; return l.map(x => x.id).filter(Boolean); };
  const routen = ['#/start', '#/statistik', '#/kunden', '#/auftraege', '#/leitstand', '#/op', '#/op/mahnwesen', '#/belege', '#/lieferanten', '#/zahlungen', '#/kalender', '#/kalender/planung', '#/personal', '#/personal/zeiten', '#/personal/abwesenheit', '#/personal/beleg', '#/personal/lohn', '#/projekte', '#/briefe', '#/meine'];
  for (const m of ['holzwerkstoffe','massivholz','beschichtung','chemie','beschlaege','sets','artikel','reste','werkzeuge','auftrag','lager','statistik']) routen.push('#/material/' + m);
  const einst = await p.evaluate(() => ({tabs: (typeof EINST_TABS !== 'undefined' ? EINST_TABS : []).map(t => t[0]), unter: typeof EINST_UNTER !== 'undefined' ? EINST_UNTER : {}}));
  for (const t of einst.tabs) { routen.push('#/einstellungen/' + t); for (const [s] of (einst.unter[t] || [])) routen.push(`#/einstellungen/${t}/${s}`); }
  for (const k of (await ids('kunden?status=alle')).slice(0, 3)) for (const r of ['', '/konditionen', '/anhaenge', '/auftraege', '/op', '/briefe', '/statistik']) routen.push(`#/kunde/${k}${r}`);
  for (const a of (await ids('auftraege?status=')).slice(0, 4)) for (const r of ['', '/positionen', '/titel', '/kunde', '/belege', '/werkstatt', '/auswertung', '/stunden', '/sollist', '/op', '/korrespondenz', '/historie']) routen.push(`#/auftrag/${a}${r}`);
  for (const l of (await ids('lieferanten')).slice(0, 3)) for (const r of ['', '/konditionen', '/anhaenge', '/zahlungen', '/briefe', '/statistik']) routen.push(`#/lieferant/${l}${r}`);
  const belege = await api('belege'); for (const x of ((Array.isArray(belege) ? belege : (belege && belege.liste) || [])).slice(0, 12)) routen.push(`#/beleg/${x.id}`);
  const pos = await p.evaluate(async () => { const a = await (await fetch('/api/auftraege?status=')).json(); const l = Array.isArray(a) ? a : a.liste || []; for (const x of l) { const ps = await (await fetch(`/api/auftraege/${x.id}/positionen`)).json().catch(() => []); const pl = Array.isArray(ps) ? ps : ps.positionen || []; if (pl.length) return pl.slice(0, 2).map(y => y.id); } return []; });
  for (const id of pos) for (const r of ['', '/werkstoffe', '/beschlaege', '/zeiten', '/summen']) routen.push(`#/position/${id}${r}`);
  for (const m of (await ids('mitarbeiter')).slice(0, 2)) routen.push(`#/personal/ma/${m}`);
  const komisch = [];
  for (const r of routen) {
    route = r;
    await p.evaluate(h => { location.hash = h; }, r); await p.waitForTimeout(700);
    const t = await p.evaluate(() => (document.querySelector('#inhalt') || document.body).innerText);
    const m = t.match(/(undefined|NaN|\[object Object\]|null €|Infinity)/);
    if (m) { const i = t.indexOf(m[1]); komisch.push(`${r}: „${t.slice(Math.max(0, i - 40), i + 30).replace(/\s+/g, ' ')}“`); }
  }
  console.log('Routen geprüft:', routen.length, ['#/kunde/','#/auftrag/','#/lieferant/','#/beleg/','#/position/','#/personal/ma/','#/einstellungen/'].map(x => x + routen.filter(r => r.startsWith(x)).length).join(' '));
  console.log('Fehler:', fehler.length); fehler.forEach(x => console.log('  ' + x));
  console.log('Auffällige Texte:', komisch.length); komisch.forEach(x => console.log('  ' + x));
  await b.close(); })();
