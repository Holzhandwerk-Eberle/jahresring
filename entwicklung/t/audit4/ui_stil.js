// Einheitlichkeit der Bedienelemente: alle Seiten abgehen und Schaltflächen/Felder vermessen
const { chromium } = require('playwright'); const fs = require('fs');
const U = 'http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1400, height: 950 } })).newPage(); p.setDefaultTimeout(10000);
  const fehler = []; let route = '';
  p.on('pageerror', e => fehler.push(`[JS] ${route}: ${e.message}`)); p.on('dialog', d => d.dismiss());
  p.on('response', r => { if (r.url().includes('/api/') && r.status() >= 500) fehler.push(`[HTTP ${r.status()}] ${route}: ${r.url().replace(U, '')}`); });
  await p.goto(U + '/'); await p.waitForTimeout(800); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1500);
  const api = pfad => p.evaluate(async pfad => { const r = await fetch('/api/' + pfad); return r.json().catch(() => null); }, pfad);
  const ids = async (pfad) => { const j = await api(pfad); const l = Array.isArray(j) ? j : (j && (j.liste || j.eintraege || j.zeilen)) || []; return l.map(x => x.id).filter(Boolean); };
  const routen = ['#/start', '#/statistik', '#/kunden', '#/auftraege', '#/leitstand', '#/op', '#/op/mahnwesen', '#/op/bank', '#/belege', '#/lieferanten', '#/zahlungen', '#/kalender', '#/kalender/planung', '#/personal', '#/personal/zeiten', '#/personal/abwesenheit', '#/personal/beleg', '#/personal/lohn', '#/projekte', '#/briefe', '#/meine', '#/arbeitsschutz'];
  for (const m of ['holzwerkstoffe', 'massivholz', 'beschichtung', 'chemie', 'beschlaege', 'sets', 'artikel', 'reste', 'werkzeuge', 'auftrag', 'lager', 'statistik']) routen.push('#/material/' + m);
  const einst = await p.evaluate(() => ({ tabs: (typeof EINST_TABS !== 'undefined' ? EINST_TABS : []).map(t => t[0]), unter: typeof EINST_UNTER !== 'undefined' ? EINST_UNTER : {} }));
  for (const t of einst.tabs) { routen.push('#/einstellungen/' + t); for (const [s] of (einst.unter[t] || [])) routen.push(`#/einstellungen/${t}/${s}`); }
  for (const k of (await ids('kunden?status=alle')).slice(0, 1)) for (const r of ['', '/konditionen', '/anhaenge', '/auftraege', '/op', '/briefe', '/statistik']) routen.push(`#/kunde/${k}${r}`);
  for (const a of (await ids('auftraege?status=')).slice(0, 2)) for (const r of ['', '/positionen', '/titel', '/kunde', '/belege', '/werkstatt', '/auswertung', '/stunden', '/sollist', '/op', '/korrespondenz', '/historie']) routen.push(`#/auftrag/${a}${r}`);
  for (const l of (await ids('lieferanten')).slice(0, 1)) for (const r of ['', '/konditionen', '/anhaenge', '/zahlungen', '/briefe', '/statistik']) routen.push(`#/lieferant/${l}${r}`);
  const belege = await api('belege'); for (const x of ((Array.isArray(belege) ? belege : (belege && belege.liste) || [])).slice(0, 4)) routen.push(`#/beleg/${x.id}`);
  const pos = await p.evaluate(async () => { const a = await (await fetch('/api/auftraege?status=')).json(); const l = Array.isArray(a) ? a : a.liste || []; for (const x of l) { const ps = await (await fetch(`/api/auftraege/${x.id}/positionen`)).json().catch(() => []); const pl = Array.isArray(ps) ? ps : ps.positionen || []; if (pl.length) return pl.slice(0, 1).map(y => y.id); } return []; });
  for (const id of pos) for (const r of ['', '/werkstoffe', '/beschlaege', '/zeiten', '/summen']) routen.push(`#/position/${id}${r}`);
  for (const m of (await ids('mitarbeiter')).slice(0, 1)) routen.push(`#/personal/ma/${m}`);
  const alle = [];
  for (const r of routen) {
    route = r; await p.evaluate(h => { location.hash = h; }, r); await p.waitForTimeout(650);
    const el = await p.evaluate(() => {
      const sichtbar = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 2 && r.height > 2 && s.visibility !== 'hidden' && s.display !== 'none'; };
      const aus = [];
      for (const e of document.querySelectorAll('button, a.btn, input[type=submit], input[type=button], select, input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]), textarea, h1, h2, h3, th')) {
        if (!sichtbar(e)) continue; const s = getComputedStyle(e), r = e.getBoundingClientRect();
        const art = e.matches('button, a.btn, input[type=submit], input[type=button]') ? 'knopf' : e.matches('select') ? 'auswahl' : e.matches('textarea') ? 'textfeld' : e.matches('input') ? 'feld' : e.tagName.toLowerCase();
        aus.push({ art, tag: e.tagName.toLowerCase(), kl: [...e.classList].sort().join(' '), text: (e.innerText || e.value || '').trim().replace(/\s+/g, ' ').slice(0, 40), titel: e.title || e.getAttribute('aria-label') || '', h: Math.round(r.height), b: Math.round(r.width), fs: s.fontSize, ff: s.fontFamily.split(',')[0].replace(/"/g, ''), fw: s.fontWeight, rad: s.borderTopLeftRadius, bg: s.backgroundColor, fg: s.color, rand: s.borderTopWidth + ' ' + s.borderTopColor, inline: e.getAttribute('style') || '', imKopf: !!e.closest('header, nav, .lb-nav, #kopf'), typ: e.type || '' });
      }
      return aus;
    });
    el.forEach(x => { x.route = r; alle.push(x); });
  }
  fs.writeFileSync('/tmp/claude-0/t/audit4/ui_stil.json', JSON.stringify(alle));
  console.log('Routen:', routen.length, '| Elemente:', alle.length, '| Fehler:', fehler.length, fehler.slice(0, 5));
  await b.close(); })();
