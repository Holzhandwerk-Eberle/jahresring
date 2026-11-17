// Zahlen in der Oberfläche: Eingaben lesen (deutsche Schreibweise), Unlesbares melden statt 0 speichern, kaufmännisch runden.
// Aufruf: node zahlen.js   (frische Prüfinstanz, danach s/t10.js für Benutzer und Stammdaten)
const { chromium } = require('playwright');
const U = 'http://127.0.0.1:8799';
const fehler = [];
const ok = (name, bed, info) => { console.log((bed ? 'ok   ' : 'FEHLER ') + name + (bed ? '' : '  → ' + String(info === undefined ? '' : typeof info === 'string' ? info : JSON.stringify(info)).slice(0, 400))); if (!bed) fehler.push(name); };
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1500, height: 950 }, locale: 'de-DE' }); const p = await ctx.newPage();
  const skriptfehler = []; p.on('pageerror', e => skriptfehler.push(String(e).slice(0, 120)));
  const api = async (m, pf, d) => await p.evaluate(async ([m, pf, d]) => { const r = await fetch('/api/' + pf, { method: m, headers: { 'Content-Type': 'application/json' }, body: d ? JSON.stringify(d) : undefined }); return await r.json(); }, [m, pf, d]);
  await p.goto(U + '/'); await p.waitForSelector('[name=login]'); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1500);

  // ---------- 1. Lesen ----------
  const lesbar = { '': 0, '12': 12, '12,5': 12.5, '1.234,56': 1234.56, '1234,56': 1234.56, '1 500': 1500, '2.000.000': 2000000, '1.500': 1500, '100.000': 100000, '1.5': 1.5, '0.125': 0.125, '12.50': 12.5, '1.5000': 1.5,
    '1.500,00 €': 1500, '480 €': 480, '€ 480': 480, '12 %': 12, '1,234.56': 1234.56, '1,234,567': 1234567, '-3,5': -3.5, '−3,5': -3.5, '+7': 7, ',5': 0.5, '5,': 5, '-': 0, ',': 0, ' 42 ': 42, "1'500,50": 1500.5, '0': 0, '-0': 0 };
  const erg = await p.evaluate(l => Object.fromEntries(Object.keys(l).map(k => { const r = zahlLesen(k); return [k, r ? r.wert : null]; })), lesbar);
  const falsch = Object.keys(lesbar).filter(k => !(erg[k] === lesbar[k] || (Object.is(erg[k], -0) && lesbar[k] === 0)) || Object.is(erg[k], -0)).map(k => `„${k}“ → ${erg[k]} (erwartet ${lesbar[k]})`);
  ok(`${Object.keys(lesbar).length} Schreibweisen werden richtig gelesen (1.234,56 · 1 500 · 2.000.000 · 1.500 = 1500 · 1.5 = 1,5 · 480 € …)`, falsch.length === 0, falsch);
  const unlesbar = ['abc', '12x', '1.2.3', '1,2,3', '5-', '1e5', '1.500.00', '--5', '=1+1', '1,5,0', '1.23,4.5', 'NaN', 'Infinity'];
  const erg2 = await p.evaluate(l => l.filter(k => zahlLesen(k) !== null), unlesbar);
  ok(`${unlesbar.length} Eingaben, die keine Zahl sind, werden als solche erkannt`, erg2.length === 0, erg2);
  ok('nur „1.500“ und „100.000“ gelten als mehrdeutig (Hinweis beim Verlassen des Feldes)', await p.evaluate(() => zahlLesen('1.500').tausender && zahlLesen('100.000').tausender && !zahlLesen('1.5').tausender && !zahlLesen('2.000.000').tausender && !zahlLesen('1.500,00').tausender));

  // ---------- 2. kaufmännisch runden in der Anzeige ----------
  const r = await p.evaluate(() => ({ a: kfm(2.675), b: kfm(1.005), c: kfm(0.285), d: kfm(2.5, 0), e: kfm(-2.675), f: kfm(1.115), g: kfm(8.345), h: kfm(1000000000.005), i: kfm(0.5, 0), j: kfm(-0.004), k: zahlDE(2.675), l: zahlDE(1234.5), m: zahlDE(-0.004), n: zahlDE(1.005, 2), o: kfm(NaN), q: kfm(1.0049999) }));
  ok('Grenzfälle: 2,675 → 2,68 · 1,005 → 1,01 · 0,285 → 0,29 · −2,675 → −2,68 · 1.000.000.000,005 → …,01', r.a === 2.68 && r.b === 1.01 && r.c === 0.29 && r.d === 3 && r.e === -2.68 && r.f === 1.12 && r.g === 8.35 && r.h === 1000000000.01 && r.i === 1 && Object.is(r.j, 0) && r.o === 0 && r.q === 1, r);
  ok('Anzeige: 2,68 · 1.234,50 · 0,00 (kein „−0,00“) · 1,01', r.k === '2,68' && r.l === '1.234,50' && r.m === '0,00' && r.n === '1,01', [r.k, r.l, r.m, r.n]);
  const abw = await p.evaluate(() => { const f = []; for (let i = 0; i < 400000; i++) { const x = i / 1000, soll = Math.floor((i + 5) / 10) / 100; if (kfm(x) !== soll || kfm(-x) !== (soll ? -soll : 0)) f.push(x); if (f.length > 5) break; } return f; });
  ok('400.000 Beträge mit drei Nachkommastellen (0,000 bis 399,999): jede Rundung stimmt mit der genauen Rechnung überein', abw.length === 0, abw);
  const abw2 = await p.evaluate(() => { const f = []; let s = 12345; for (let i = 0; i < 200000; i++) { s = (s * 1103515245 + 12345) % 2147483648; const cent = s % 5000000, pz = [19, 7, 3, 2.5][i % 4]; const x = cent / 100 * pz / 100;
    const soll = Number((BigInt(cent) * BigInt(pz * 10) + 500n) / 1000n) / 100; if (kfm(x) !== soll) f.push([cent / 100, pz, kfm(x), soll]); if (f.length > 5) break; } return f; });
  ok('200.000 Steuer- und Skontobeträge (19 %, 7 %, 3 %, 2,5 % aus Beträgen bis 50.000 €) auf den Cent wie von Hand gerechnet', abw2.length === 0, abw2);

  // ---------- 3. Eingabefelder ----------
  const k = await api('POST', 'kunden', { kurzname: 'Zahl, Zora', plz: '88069', ort: 'Tettnang' });
  const a = await api('POST', 'auftraege', { kunde_id: k.id, bezeichnung: 'Zahlentest' });
  const po = await api('POST', `auftraege/${a.id}/positionen`, { text: 'Tisch' }); const pid = po.id || po.position.id;
  const gespeichert = async () => { const pos = await api('GET', `auftraege/${a.id}/positionen`); return (pos.positionen || pos)[0]; };
  const toast = () => p.evaluate(() => { const t = document.querySelector('#toast'); return t && t.className.includes('zeigen') ? t.textContent.trim() : ''; });
  async function tippe(sel, eingabe, verlassen = true, unter = '') {
    await p.evaluate(h => { if (location.hash !== h) location.hash = h; }, `#/position/${pid}${unter}`); await p.waitForSelector(sel); await p.waitForTimeout(300);
    await p.click(sel, { clickCount: 3 }); await p.keyboard.press('Control+A'); await p.keyboard.press('Delete'); await p.keyboard.type(eingabe); if (verlassen) await p.keyboard.press('Tab'); await p.waitForTimeout(900);
  }
  await tippe('#ep', '1.500');
  let z = await gespeichert(), t = await toast();
  ok('Einzelpreis „1.500“ wird als 1.500,00 € gespeichert (bisher 1,50 €)', z.einzelpreis === 1500, z.einzelpreis);
  ok('dazu erscheint der Hinweis, wie die Eingabe gelesen wurde', /als 1\.500 gelesen/.test(t) && /Komma/.test(t), t);
  for (const [eingabe, soll] of [['1.234,56', 1234.56], ['12,5', 12.5], ['1.5', 1.5], ['2.000.000', 2000000], ['1 500', 1500], ['1.500,00 €', 1500], ['480', 480]]) {
    await tippe('#ep', eingabe); z = await gespeichert();
    ok(`Einzelpreis „${eingabe}“ → ${soll}`, z.einzelpreis === soll, z.einzelpreis);
  }
  await tippe('#ep', '12x', false);
  ok('„12x“ im Einzelpreis: das Feld wird schon beim Tippen markiert', await p.evaluate(() => document.querySelector('#ep').classList.contains('zahl-fehler')));
  await p.keyboard.press('Tab'); await p.waitForTimeout(900); z = await gespeichert(); t = await toast();
  ok('… gespeichert bleibt der letzte lesbare Stand der Eingabe (12), „12x“ wird nicht zu 0', z.einzelpreis === 12, z.einzelpreis);
  ok('… beim Verlassen kommt die Meldung „ist keine Zahl“', /„12x“ ist keine Zahl/.test(t), t);
  await tippe('#ep', '520'); z = await gespeichert();
  ok('nach der Korrektur verschwindet die Markierung und der Wert wird gespeichert', z.einzelpreis === 520 && await p.evaluate(() => !document.querySelector('#ep').classList.contains('zahl-fehler')), z.einzelpreis);
  // Menge
  const mengeSel = '#inhalt input.zahl';
  await tippe(mengeSel, '1.000'); z = await gespeichert();
  ok('Menge „1.000“ wird als 1000 gespeichert (bisher 1)', z.menge === 1000, z.menge);
  await tippe(mengeSel, '2,5'); z = await gespeichert();
  ok('Menge „2,5“ → 2,5', z.menge === 2.5, z.menge);
  await tippe(mengeSel, 'zwei'); t = await toast();
  ok('Menge „zwei“: Feld markiert, Meldung erscheint', /„zwei“ ist keine Zahl/.test(t) && await p.evaluate(s => document.querySelector(s).classList.contains('zahl-fehler'), mengeSel), t);
  await tippe(mengeSel, '1');
  // Feld, das erst beim Verlassen speichert (Kleinmaterial in der Kalkulation): Unlesbares lässt den gespeicherten Wert unberührt
  const km = '[data-x=kleinmaterial]';
  await p.evaluate(h => { location.hash = h; }, `#/position/${pid}/summen`); await p.waitForTimeout(900);
  if (await p.locator(km).count()) {
    await tippe(km, '7,5', true, '/summen'); z = await gespeichert(); const vorher = (z.extras || {}).kleinmaterial;
    await tippe(km, '7.5.1', true, '/summen'); z = await gespeichert(); t = await toast();
    ok('Kleinmaterial „7.5.1“: der gespeicherte Wert (7,5 %) bleibt, Meldung erscheint', vorher === 7.5 && (z.extras || {}).kleinmaterial === 7.5 && /„7\.5\.1“ ist keine Zahl/.test(t), [vorher, (z.extras || {}).kleinmaterial, t]);
    await tippe(km, '8', true, '/summen'); z = await gespeichert();
    ok('nach der Korrektur wird gespeichert (8 %)', (z.extras || {}).kleinmaterial === 8, (z.extras || {}).kleinmaterial);
  } else ok('Feld Kleinmaterial gefunden', false);
  // Dialog (Zahlung zu einem offenen Posten): Unlesbares bricht das Speichern ab
  ok('keine unbehandelten Skriptfehler (Zahlfehler werden als Meldung gezeigt)', skriptfehler.length === 0, skriptfehler);
  console.log('FEHLER: ' + JSON.stringify(fehler));
  await b.close(); process.exit(fehler.length ? 1 : 0);
})().catch(e => { console.log('FEHLER: Abbruch ' + (e && e.stack || e)); process.exit(1); });
