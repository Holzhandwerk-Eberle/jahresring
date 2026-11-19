// Überstand bei schmalen Breiten messen (ohne Handy-Emulation, wie in der Prüfung). Aufruf: node s/u15.js [Breite …] – nutzt die laufende Instanz
const { chromium } = require('playwright');
const U = 'http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1400, height: 950 }, locale: 'de-DE' }); const p = await ctx.newPage(); p.setDefaultTimeout(15000);
  p.on('dialog', d => d.dismiss().catch(() => {}));
  await p.goto(U + '/'); await p.waitForSelector('[name=login]'); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim12345'); await p.click('button[type=submit]'); await p.waitForTimeout(1800);
  const api = pfad => p.evaluate(async x => { const r = await fetch('/api/' + x); return r.json().catch(() => null); }, pfad);
  const ids = async pfad => { const j = await api(pfad); const l = Array.isArray(j) ? j : (j && (j.liste || j.eintraege || j.zeilen)) || []; return l.map(x => x.id).filter(Boolean); };
  let routen = ['#/start', '#/statistik', '#/kunden', '#/auftraege', '#/leitstand', '#/op', '#/op/mahnwesen', '#/op/bank', '#/op/liquiditaet', '#/belege', '#/lieferanten', '#/zahlungen', '#/kalender', '#/kalender/planung', '#/kalender/woche', '#/personal', '#/personal/zeiten', '#/personal/abwesenheit', '#/personal/beleg', '#/personal/lohn', '#/projekte', '#/briefe', '#/meine', '#/arbeitsschutz', '#/arbeitsschutz/gb', '#/arbeitsschutz/ba', '#/arbeitsschutz/unterweisungen', '#/arbeitsschutz/gefahrstoffe', '#/arbeitsschutz/notfall', '#/arbeitsschutz/nachweise'];
  for (const m of ['holzwerkstoffe', 'massivholz', 'beschichtung', 'chemie', 'beschlaege', 'sets', 'artikel', 'reste', 'werkzeuge', 'auftrag', 'lager', 'statistik']) routen.push('#/material/' + m);
  const einst = await p.evaluate(() => ({ tabs: EINST_TABS.map(t => t[0]), unter: EINST_UNTER }));
  for (const t of einst.tabs) { routen.push('#/einstellungen/' + t); for (const [s] of (einst.unter[t] || [])) routen.push(`#/einstellungen/${t}/${s}`); }
  const kunden = (await ids('kunden?status=alle')).slice(0, 2), auftraege = (await ids('auftraege?status=')).slice(0, 2), lieferanten = (await ids('lieferanten')).slice(0, 2);
  for (const k of kunden) for (const r of ['', '/konditionen', '/anhaenge', '/auftraege', '/op', '/briefe', '/statistik']) routen.push(`#/kunde/${k}${r}`);
  for (const a of auftraege) for (const r of ['', '/positionen', '/titel', '/kunde', '/belege', '/werkstatt', '/auswertung', '/stunden', '/sollist', '/op', '/briefe', '/historie']) routen.push(`#/auftrag/${a}${r}`);
  for (const l of lieferanten) for (const r of ['', '/konditionen', '/anhaenge', '/zahlungen', '/briefe', '/statistik']) routen.push(`#/lieferant/${l}${r}`);
  const belege = await api('belege'); for (const x of ((Array.isArray(belege) ? belege : (belege && belege.liste) || [])).slice(0, 6)) routen.push(`#/beleg/${x.id}`);
  const pos = await p.evaluate(async () => { const a = await (await fetch('/api/auftraege?status=')).json(); const l = Array.isArray(a) ? a : a.liste || []; const aus = []; for (const x of l.slice(0, 6)) { const ps = await (await fetch(`/api/auftraege/${x.id}/positionen`)).json().catch(() => []); const pl = Array.isArray(ps) ? ps : ps.positionen || []; if (pl.length) { aus.push(pl[0].id); break; } } return aus; });
  for (const id of pos) for (const r of ['', '/werkstoffe', '/beschlaege', '/zeiten', '/summen']) routen.push(`#/position/${id}${r}`);
  const mas = (await ids('mitarbeiter')).slice(0, 2); for (const m of mas) routen.push(`#/personal/ma/${m}`);
  if (process.env.NUR) routen = routen.filter(r => new RegExp(process.env.NUR).test(r));
  for (const w of (process.argv.slice(2).length ? process.argv.slice(2).map(Number) : [390, 820])) {
    await p.setViewportSize({ width: w, height: 900 }); const breit = [];
    for (const r of routen) { await p.evaluate(h => { location.hash = h; }, r); await p.waitForTimeout(450);
      const x = await p.evaluate(() => { const de = document.documentElement, w = window.innerWidth, u = de.scrollWidth - w; if (u <= 2) return null; const schuld = [];
        for (const e of document.querySelectorAll('body *')) { const q = e.getBoundingClientRect(); if (q.right > w + 2 && q.width > 0 && q.height > 0) {
          let a = e.parentElement, innen = false; while (a && a !== document.body) { const s = getComputedStyle(a); if (/(auto|scroll|hidden)/.test(s.overflowX)) { innen = true; break; } a = a.parentElement; }
          if (!innen) { const kette = []; let v = e; for (let i = 0; i < 4 && v && v !== document.body; i++) { kette.push(v.tagName.toLowerCase() + (v.id ? '#' + v.id : '') + (typeof v.className === 'string' && v.className ? '.' + v.className.trim().split(/\s+/).join('.') : '')); v = v.parentElement; }
            schuld.push(`${kette.join(' < ')} [B ${Math.round(q.width)}, rechts ${Math.round(q.right)}] „${(e.innerText || '').trim().slice(0, 40).replace(/\s+/g, ' ')}“`); if (schuld.length >= 3) break; } } }
        return { u, schuld }; });
      if (x) breit.push(`${r} +${x.u}px\n      ` + x.schuld.join('\n      ')); }
    console.log(`Breite ${w}: ${breit.length} von ${routen.length} Seiten mit Überstand`); breit.forEach(z => console.log('   ' + z)); }
  await b.close(); })();
