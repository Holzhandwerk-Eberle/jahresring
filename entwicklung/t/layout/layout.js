// Layoutprüfung: alle Seiten in mehreren Fensterbreiten auf überlappende Felder/Beschriftungen und herausragende Elemente prüfen
const { chromium } = require('playwright');
const U='http://127.0.0.1:8799';
const BREITEN = (process.argv[2] || '1400,1100,820').split(',').map(Number);
const pruefe = () => {
  const wurzel = document.querySelector('#inhalt') || document.body, aus = [];
  const sichtbar = el => { if (el.closest('details:not([open])') && !el.closest('summary')) return null; const r = el.getBoundingClientRect(); if (r.width < 3 || r.height < 3) return null; const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return null;
    for (let p = el.parentElement; p; p = p.parentElement) { const c = getComputedStyle(p); if (c.display === 'none' || c.visibility === 'hidden') return null;
      if (/(auto|scroll|hidden)/.test(c.overflowX + c.overflowY)) { const pr = p.getBoundingClientRect(); if (r.right <= pr.left || r.left >= pr.right || r.bottom <= pr.top || r.top >= pr.bottom) return null; } }
    return r; };
  const name = el => { let s = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.name ? `[name=${el.name}]` : ''); const d = Object.keys(el.dataset || {})[0]; if (d) s += `[data-${d}=${el.dataset[d]}]`; const t = (el.innerText || el.value || el.placeholder || '').trim().slice(0, 25); return s + (t ? ` „${t}“` : ''); };
  const felder = [...wurzel.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]),select,textarea,button,a.btn')].map(el => ({el, r: sichtbar(el)})).filter(x => x.r);
  const schnitt = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  // 1. Felder überlappen einander
  for (let i = 0; i < felder.length; i++) for (let j = i + 1; j < felder.length; j++) { const a = felder[i], b = felder[j];
    if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
    if (schnitt(a.r, b.r) > 12) aus.push(`Felder überlappen: ${name(a.el)} / ${name(b.el)}`); }
  // 2. Text liegt unter/über einem Feld
  const tw = document.createTreeWalker(wurzel, NodeFilter.SHOW_TEXT); let n; const gesehen = new Set();
  while ((n = tw.nextNode())) { if (!n.nodeValue.trim() || !n.parentElement || /^(OPTION|SCRIPT|STYLE|TEXTAREA)$/.test(n.parentElement.tagName)) continue;
    if (!sichtbar(n.parentElement)) continue; const pcs = getComputedStyle(n.parentElement); if (pcs.position === 'absolute' || pcs.position === 'fixed') continue;
    const rg = document.createRange(); rg.selectNodeContents(n); const er = n.parentElement.getBoundingClientRect(), abgeschnitten = /(hidden|auto|scroll|clip)/.test(pcs.overflowX + pcs.overflowY);
    for (const tr of rg.getClientRects()) { if (tr.width < 2) continue; if (abgeschnitten && (tr.bottom <= er.top + 1 || tr.top >= er.bottom - 1 || er.height < 3)) continue;
      for (const f of felder) { if (f.el.contains(n)) continue; const fcs = getComputedStyle(f.el); if (fcs.position === 'absolute' || fcs.position === 'fixed') continue;
        if (schnitt(tr, f.r) > 20) { const k = name(f.el) + '|' + n.nodeValue.trim().slice(0, 20); if (!gesehen.has(k)) { gesehen.add(k); aus.push(`Text „${n.nodeValue.trim().slice(0, 30)}“ überlappt ${name(f.el)}`); } } } } }
  // 3. Feld ragt aus seiner Karte oder aus dem Fenster
  const breite = document.documentElement.clientWidth;
  const inScroll = el => { for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) { const c = getComputedStyle(p); if (/(auto|scroll)/.test(c.overflowX) && p.scrollWidth > p.clientWidth + 1 && p.getBoundingClientRect().right <= breite + 2) return true; } return false; };
  for (const f of felder) { if (f.r.right > breite + 2) { if (!inScroll(f.el)) aus.push(`ragt aus dem Fenster: ${name(f.el)}`); continue; }
    const z = f.el.closest('.zeile>div, td, .karte, .kachel, label'); if (z) { const zr = z.getBoundingClientRect(); const c = getComputedStyle(z); if (!/(auto|scroll)/.test(c.overflowX) && f.r.right > zr.right + 3 && zr.width > 20) aus.push(`ragt aus seinem Feldbereich (${Math.round(f.r.right - zr.right)} px): ${name(f.el)}`); } }
  if (document.documentElement.scrollWidth > breite + 4) aus.push(`Seite ist breiter als das Fenster (${document.documentElement.scrollWidth} > ${breite})`);
  return aus; };
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({viewport:{width:1400,height:950}, locale:'de-DE'}); const p = await ctx.newPage(); p.setDefaultTimeout(10000);
  p.on('dialog', d => d.dismiss());
  await p.goto(U+'/'); await p.waitForTimeout(800);
  if (await p.$('[name=passwort2]')) { await p.fill('[name=name]','Jonas'); await p.fill('[name=login]','jonas').catch(()=>{}); await p.fill('[name=passwort]','geheim123'); await p.fill('[name=passwort2]','geheim123'); }
  else { await p.fill('[name=login]','jonas'); await p.fill('[name=passwort]','geheim123'); }
  await p.click('button[type=submit]'); await p.waitForTimeout(1500);
  const api = pfad => p.evaluate(async pfad => { const r = await fetch('/api/'+pfad); return r.json().catch(()=>null); }, pfad);
  const ids = async (pfad) => { const j = await api(pfad); const l = Array.isArray(j) ? j : (j && (j.liste || j.eintraege || j.zeilen)) || []; return l.map(x => x.id).filter(Boolean); };
  const routen = ['#/start', '#/statistik', '#/kunden', '#/auftraege', '#/leitstand', '#/op', '#/op/mahnwesen', '#/belege', '#/lieferanten', '#/zahlungen', '#/kalender', '#/kalender/planung', '#/personal', '#/personal/zeiten', '#/personal/abwesenheit', '#/personal/beleg', '#/personal/lohn', '#/projekte', '#/briefe', '#/meine'];
  for (const r of ['', '/gb', '/gb/1', '/gb/2', '/ba', '/ba/1', '/ba/2', '/unterweisungen', '/unterweisungen/liste', '/unterweisungen/themen', '/unterweisung/1', '/thema/1', '/gefahrstoffe', '/notfall', '/nachweise']) routen.push('#/arbeitsschutz' + r);
  routen.push('#/mat/1/sicherheit');
  for (const m of ['holzwerkstoffe','massivholz','beschichtung','chemie','beschlaege','sets','artikel','reste','werkzeuge','auftrag','lager','statistik']) routen.push('#/material/' + m);
  const einst = await p.evaluate(() => ({tabs: (typeof EINST_TABS !== 'undefined' ? EINST_TABS : []).map(t => t[0]), unter: typeof EINST_UNTER !== 'undefined' ? EINST_UNTER : {}}));
  for (const t of einst.tabs) { routen.push('#/einstellungen/' + t); for (const [s] of (einst.unter[t] || [])) routen.push(`#/einstellungen/${t}/${s}`); }
  for (const k of (await ids('kunden?status=alle')).slice(0, 1)) for (const r of ['', '/konditionen', '/anhaenge', '/auftraege', '/op', '/briefe', '/statistik']) routen.push(`#/kunde/${k}${r}`);
  for (const a of (await ids('auftraege?status=')).slice(0, 1)) for (const r of ['', '/positionen', '/titel', '/kunde', '/belege', '/werkstatt', '/auswertung', '/stunden', '/sollist', '/op', '/korrespondenz', '/historie']) routen.push(`#/auftrag/${a}${r}`);
  for (const l of (await ids('lieferanten')).slice(0, 1)) for (const r of ['', '/konditionen', '/anhaenge', '/zahlungen', '/briefe', '/statistik']) routen.push(`#/lieferant/${l}${r}`);
  const belege = await api('belege'); const bl = (Array.isArray(belege) ? belege : (belege && belege.liste) || []); const arten = new Set();
  for (const x of bl) { if (!arten.has(x.art + x.status)) { arten.add(x.art + x.status); routen.push(`#/beleg/${x.id}`); } }
  const pos = await p.evaluate(async () => { const a = await (await fetch('/api/auftraege?status=')).json(); const l = Array.isArray(a) ? a : a.liste || []; for (const x of l) { const ps = await (await fetch(`/api/auftraege/${x.id}/positionen`)).json().catch(() => []); const pl = Array.isArray(ps) ? ps : ps.positionen || []; if (pl.length) return pl.slice(0, 1).map(y => y.id); } return []; });
  for (const id of pos) for (const r of ['', '/werkstoffe', '/beschlaege', '/zeiten', '/summen']) routen.push(`#/position/${id}${r}`);
  for (const m of (await ids('mitarbeiter')).slice(0, 1)) routen.push(`#/personal/ma/${m}`);
  let anzahl = 0; const funde = {};
  for (const w of BREITEN) { await p.setViewportSize({width: w, height: 950});
    for (const r of routen) { await p.evaluate(h => { location.hash = h; }, r); await p.waitForTimeout(550);
      // ganze Seite prüfen: nach unten blättern, damit nichts durch den Fensterrand abgeschnitten gewertet wird
      const f = await p.evaluate(pruefe); for (const x of f) { const k = `${r}: ${x}`; (funde[k] = funde[k] || []).push(w); anzahl++; } } }
  console.log(`Routen: ${routen.length} × Breiten ${BREITEN.join('/')}`);
  const schl = Object.keys(funde); console.log('Layoutfunde:', schl.length); schl.forEach(k => console.log(`  [${funde[k].join(',')}] ${k}`));
  await b.close(); })();
