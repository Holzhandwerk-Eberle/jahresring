// Beschlägesets im Auftrag: „+ Beschlägeset“ bei den Auftragsbeschlägen und in der Beschlägeliste der Position; leere Beschlagzeile zählt nicht
const { chromium } = require('playwright');
const U = process.argv[2] || 'http://127.0.0.1:8799', S = '/tmp/claude-0/-home-claude/ec87b02e-c197-5135-8518-1f390bf90317/scratchpad/';
const fehler = []; const ok = (n, b, i) => { console.log((b ? 'ok   ' : 'FEHLER ') + n + (b ? '' : '  → ' + JSON.stringify(i).slice(0, 300))); if (!b) fehler.push(n); };
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({viewport: {width: 1400, height: 1000}, locale: 'de-DE'})).newPage(); p.setDefaultTimeout(8000);
  p.on('pageerror', e => { console.log('FEHLER Seite', e.message); fehler.push('Seitenfehler'); });
  await p.goto(U + '/'); await p.waitForTimeout(800);
  const neu = await p.evaluate(async () => (await (await fetch('/api/anmeldung/stand')).json()));
  await p.evaluate(async () => { await fetch('/api/anmeldung/einrichten', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: 'Jonas', login: 'jonas', passwort: 'geheim12345', passwort2: 'geheim12345', firma: 'Muster'})}); });
  await p.goto(U + '/'); await p.waitForTimeout(800);
  if (await p.$('[name=login]')) { await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim12345'); await p.click('button[type=submit]'); await p.waitForTimeout(1500); }
  const d = await p.evaluate(async () => {
    const api = async (m, pfad, body) => { const r = await fetch('/api/' + pfad, {method: m, headers: {'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined}); const j = await r.json(); if (!r.ok) throw new Error(pfad + ': ' + JSON.stringify(j)); return j; };
    const m1 = await api('POST', 'material', {kategorie: 'beschlaege', bezeichnung: 'Topfscharnier 110°', ek_preis: 5, einheit: 'Stk.'});
    const m2 = await api('POST', 'material', {kategorie: 'beschlaege', bezeichnung: 'Montageplatte', ek_preis: 0.5, einheit: 'Stk.'});
    const m3 = await api('POST', 'material', {kategorie: 'beschlaege', bezeichnung: 'Griff', ek_preis: 8, einheit: 'Stk.'});
    const s = await api('POST', 'materialsets', {bezeichnung: 'Tür komplett'});
    await api('PUT', 'materialsets/' + s.id, {positionen: [{material_id: m1.id, menge: 2}, {material_id: m2.id, menge: 2}, {material_id: m3.id, menge: 1}]});
    await api('POST', 'materialsets', {bezeichnung: 'leeres Set'});
    const k = await api('POST', 'kunden', {kurzname: 'Muster, Max'});
    const a = await api('POST', 'auftraege', {kunde_id: k.id, bezeichnung: 'Schrank'});
    const po = await api('POST', 'auftraege/' + a.id + '/positionen', {text: 'Schrank'}); const pid = po.id || po.position.id;
    await api('PUT', 'positionen/' + pid, {zeitmodus: 'taetigkeiten', zeiten: [{kst: 'BANKRAUM', name: 'Beschläge einlassen', minuten: 6, bezug: 'beschlaege', ruest: 12, helfer: 0}], beschlaege: [{k: '', menge: 23, bemerkung: ''}]});
    const pp = await api('GET', 'positionen/' + pid);
    return {aid: a.id, pid, set: s, stunden: pp.position.calc.zeit_summen.gesamt_pos}; });
  ok('leere Beschlagzeile (Menge 23) rechnet keine Arbeitszeit', Math.abs(d.stunden) < 0.001, d.stunden);
  // Position › Beschläge: Set mit Anzahl 3
  await p.goto(U + '/#/position/' + d.pid + '/beschlaege'); await p.waitForTimeout(1500);
  ok('Knopf „+ Beschlägeset …“ in der Beschlägeliste', !!(await p.$('#bSet')));
  await p.click('#bSet'); await p.waitForTimeout(600);
  const opt = await p.$$eval('.modal select[name=set] option', o => o.map(x => x.textContent));
  ok('Auswahl zeigt nur Sets mit Beschlägen, mit Anzahl und Summe', opt.length === 1 && /3 Beschläge/.test(opt[0]) && /19,00/.test(opt[0]), opt);
  await p.fill('.modal [name=anzahl]', '3'); await p.screenshot({path: S + 'v_set1.png'});
  await p.click(".modal [data-x='1']"); await p.waitForTimeout(1800);
  const st = await p.evaluate(async (pid) => { const j = await (await fetch('/api/positionen/' + pid)).json(); return {b: j.position.beschlaege, c: j.position.calc.beschlaege, h: j.position.calc.zeit_summen.gesamt_pos, kalk: j.kalk.beschlaege.map(x => [x.k, x.name, x.preis])}; }, d.pid);
  ok('drei Zeilen aus dem Set mit Menge × 3', st.b.length === 4 && JSON.stringify(st.b.slice(1).map(x => x.menge)) === '[6,6,3]' && st.b.slice(1).every(x => x.k && /Set SET/.test(x.bemerkung)), st.b);
  ok('fehlende Beschläge in die Auftragsbeschläge übernommen', st.kalk.filter(x => x[1]).length === 3, st.kalk);
  ok('Kosten: 6×5 + 6×0,5 + 3×8 = 57', Math.abs(st.c - 57) < 0.01, st.c);
  ok('Arbeitszeit zählt 15 Beschläge (leere Zeile nicht): 15×6 min + 12 min Rüstzeit', Math.abs(st.h - (15 * 6 + 12) / 60) < 0.01, st.h);
  await p.screenshot({path: S + 'v_set2.png'});
  // noch einmal dasselbe Set: Auftragsbeschläge bleiben drei, Zeilen kommen dazu
  await p.click('#bSet'); await p.waitForTimeout(500); await p.click(".modal [data-x='1']"); await p.waitForTimeout(1500);
  const st2 = await p.evaluate(async (pid) => { const j = await (await fetch('/api/positionen/' + pid)).json(); return {n: j.position.beschlaege.length, kalk: j.kalk.beschlaege.filter(x => x.name).length}; }, d.pid);
  ok('zweites Mal: keine doppelten Auftragsbeschläge', st2.n === 7 && st2.kalk === 3, st2);
  // Auftragsbeschläge eines zweiten Auftrags: Set übernimmt alle Beschläge
  const a2 = await p.evaluate(async () => { const api = async (m, pfad, body) => (await (await fetch('/api/' + pfad, {method: m, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})).json());
    const k = await api('POST', 'kunden', {kurzname: 'Zwei, Kunde'}); const a = await api('POST', 'auftraege', {kunde_id: k.id, bezeichnung: 'Regal'}); const po = await api('POST', 'auftraege/' + a.id + '/positionen', {text: 'Regal'}); return {aid: a.id, pid: po.id || po.position.id}; });
  await p.goto(U + '/#/position/' + a2.pid + '/werte/beschlaege'); await p.waitForTimeout(1500);
  ok('Knopf „+ Beschlägeset“ bei den Auftragsbeschlägen', !!(await p.$('[data-plus=set]')));
  await p.click('[data-plus=set]'); await p.waitForTimeout(500); await p.click(".modal [data-x='1']"); await p.waitForTimeout(1500);
  const k2 = await p.evaluate(async (pid) => (await (await fetch('/api/positionen/' + pid)).json()).kalk.beschlaege.filter(x => x.name).map(x => x.name), a2.pid);
  ok('Auftragsbeschläge: alle drei Beschläge des Sets übernommen', k2.length === 3 && k2.includes('Griff'), k2);
  await p.screenshot({path: S + 'v_set3.png'});
  console.log('FEHLER:', JSON.stringify(fehler)); await b.close(); process.exit(fehler.length ? 1 : 0); })();
