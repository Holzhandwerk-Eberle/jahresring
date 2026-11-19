// Version 152, Oberfläche (U9 bis U15, E5, Z12): Höhe der Schaltflächen und Felder, einheitliche Beschriftungen für Drucken und PDF,
// Hauptschaltflächen, Beschriftungen mit Feldbezug, Verweise der Rolle Werkstatt, Überstand auf Handy und Tablet, Seite „Gesetzliche Werte“.
// Aufruf: cd /tmp/claude-0/t/v25 && cp ../neu/ui152.js s/ && node s/ui152.js   (startet eine frische Instanz und füllt sie)
const { chromium } = require('playwright');
const { execSync } = require('child_process');
const U = 'http://127.0.0.1:8799';
const fehler = [];
const ok = (name, bed, info = '') => { console.log((bed ? 'ok   ' : 'FEHLER ') + name + (bed ? '' : '  → ' + String(typeof info === 'string' ? info : JSON.stringify(info)).slice(0, 1500))); if (!bed) fehler.push(name); };
(async () => {
  execSync('bash /tmp/claude-0/t/v25/neu.sh >/dev/null 2>&1; sleep 1; python3 /tmp/claude-0/t/neu/spur_seed.py > /tmp/claude-0/t/lauf/ui152_seed.txt 2>&1', { stdio: 'inherit', timeout: 300000 });
  const b = await chromium.launch();
  const jsFehler = [];
  const anmelden = async (ctx, login, pw) => { const p = await ctx.newPage(); p.setDefaultTimeout(15000);
    p.on('pageerror', e => jsFehler.push(`${login}: ${e.message}`)); p.on('dialog', d => d.dismiss().catch(() => {}));
    p.on('response', r => { if (r.url().includes('/api/') && r.status() >= 500) jsFehler.push(`${login}: HTTP ${r.status()} ${r.url().replace(U, '')}`); });
    await p.goto(U + '/'); await p.waitForSelector('[name=login]'); await p.fill('[name=login]', login); await p.fill('[name=passwort]', pw); await p.click('button[type=submit]'); await p.waitForTimeout(1800); return p; };
  const gehe = async (p, h, warte = 650) => { await p.evaluate(x => { location.hash = x; }, h); await p.waitForTimeout(warte); };
  const ctx = await b.newContext({ viewport: { width: 1400, height: 950 }, locale: 'de-DE' });
  const p = await anmelden(ctx, 'jonas', 'geheim12345');
  const api = pfad => p.evaluate(async x => { const r = await fetch('/api/' + x); return r.json().catch(() => null); }, pfad);
  const ids = async pfad => { const j = await api(pfad); const l = Array.isArray(j) ? j : (j && (j.liste || j.eintraege || j.zeilen)) || []; return l.map(x => x.id).filter(Boolean); };

  // ---------- Routen wie im Seitendurchlauf ----------
  const routen = ['#/start', '#/statistik', '#/kunden', '#/auftraege', '#/leitstand', '#/op', '#/op/mahnwesen', '#/belege', '#/lieferanten', '#/zahlungen', '#/kalender', '#/kalender/planung', '#/personal', '#/personal/zeiten', '#/personal/abwesenheit', '#/personal/beleg', '#/personal/lohn', '#/projekte', '#/briefe', '#/meine', '#/op/bank', '#/arbeitsschutz', '#/arbeitsschutz/gefahrstoffe', '#/arbeitsschutz/unterweisungen'];
  for (const m of ['holzwerkstoffe', 'massivholz', 'beschichtung', 'chemie', 'beschlaege', 'sets', 'artikel', 'reste', 'werkzeuge', 'auftrag', 'lager', 'statistik']) routen.push('#/material/' + m);
  const einst = await p.evaluate(() => ({ tabs: EINST_TABS.map(t => t[0]), unter: EINST_UNTER }));
  for (const t of einst.tabs) { routen.push('#/einstellungen/' + t); for (const [s] of (einst.unter[t] || [])) routen.push(`#/einstellungen/${t}/${s}`); }
  const kunden = (await ids('kunden?status=alle')).slice(0, 2), auftraege = (await ids('auftraege?status=')).slice(0, 2), lieferanten = (await ids('lieferanten')).slice(0, 2);
  for (const k of kunden) for (const r of ['', '/konditionen', '/anhaenge', '/auftraege', '/op', '/briefe', '/statistik']) routen.push(`#/kunde/${k}${r}`);
  for (const a of auftraege) for (const r of ['', '/positionen', '/titel', '/kunde', '/belege', '/werkstatt', '/auswertung', '/stunden', '/sollist', '/op', '/korrespondenz', '/historie']) routen.push(`#/auftrag/${a}${r}`);
  for (const l of lieferanten) for (const r of ['', '/konditionen', '/anhaenge', '/zahlungen', '/briefe', '/statistik']) routen.push(`#/lieferant/${l}${r}`);
  const belege = await api('belege'); for (const x of ((Array.isArray(belege) ? belege : (belege && belege.liste) || [])).slice(0, 6)) routen.push(`#/beleg/${x.id}`);
  const pos = await p.evaluate(async () => { const a = await (await fetch('/api/auftraege?status=')).json(); const l = Array.isArray(a) ? a : a.liste || []; for (const x of l) { const ps = await (await fetch(`/api/auftraege/${x.id}/positionen`)).json().catch(() => []); const pl = Array.isArray(ps) ? ps : ps.positionen || []; if (pl.length) return pl.slice(0, 1).map(y => y.id); } return []; });
  for (const id of pos) for (const r of ['', '/werkstoffe', '/beschlaege', '/zeiten', '/summen']) routen.push(`#/position/${id}${r}`);
  const mas = (await ids('mitarbeiter')).slice(0, 2); for (const m of mas) routen.push(`#/personal/ma/${m}`);
  console.log('Routen:', routen.length);

  // ---------- Messung am Schreibtisch: Schaltflächen, Felder, Beschriftungen ----------
  const messen = () => { const sichtbar = e => e.offsetParent && getComputedStyle(e).visibility !== 'hidden';
    const kn = [...document.querySelectorAll('#inhalt button.btn, #inhalt a.btn, #inhalt button:not([class])')].filter(sichtbar).filter(e => !e.closest('.rt-leiste')).map(e => ({ t: (e.innerText || e.title || '').trim().replace(/\s+/g, ' ').slice(0, 40), h: Math.round(e.getBoundingClientRect().height), f: getComputedStyle(e).fontSize, prim: e.classList.contains('prim') }));
    const felder = [...document.querySelectorAll('#inhalt input, #inhalt select, #inhalt textarea')].filter(sichtbar).filter(e => !['hidden', 'checkbox', 'radio', 'file', 'color', 'range', 'button', 'submit'].includes(e.type));
    const ohne = felder.filter(e => !(e.labels && e.labels.length) && !e.getAttribute('aria-label') && !e.getAttribute('aria-labelledby') && !e.title && !e.placeholder);
    const fh = felder.filter(e => e.tagName !== 'TEXTAREA' && !e.multiple).map(e => ({ n: e.name || e.dataset.f || e.id || e.dataset.k || '', h: Math.round(e.getBoundingClientRect().height) }));
    const th = [...document.querySelectorAll('#inhalt th')].filter(sichtbar).map(e => getComputedStyle(e).fontSize);
    return { kn, felder: felder.length, ohne: ohne.length, ohneBsp: ohne.slice(0, 4).map(e => (e.name || e.dataset.f || e.dataset.k || e.id || e.className || e.tagName) + ''), fh, th: [...new Set(th)] }; };
  let knoepfe = [], felder = 0, ohne = 0; const ohneWo = {}, hoch = [], feldhoch = [], thGross = {}, druckNamen = {};
  for (const r of routen) { await gehe(p, r); const m = await p.evaluate(messen);
    felder += m.felder; ohne += m.ohne; if (m.ohne) ohneWo[r] = `${m.ohne}: ${m.ohneBsp.join(', ')}`;
    for (const k of m.kn) { knoepfe.push(k); if (k.h > 34 || k.h < 28) hoch.push(`${r} „${k.t}“ ${k.h}px ${k.f}`); if (/druck|pdf/i.test(k.t)) (druckNamen[k.t] ||= new Set()).add(r.replace(/\d+/g, 'N')); }
    for (const f of m.fh) if (f.h < 29 || f.h > 40) feldhoch.push(`${r} ${f.n} ${f.h}px`);
    for (const t of m.th) (thGross[t] ||= []).push(r); }
  console.log(`Schaltflächen gemessen: ${knoepfe.length}, Felder: ${felder}, ohne Beschriftung: ${ohne}`);
  ok('U9/U10: Alle Schaltflächen sind zwischen 28 und 34 Pixel hoch', hoch.length === 0, [...new Set(hoch)].slice(0, 30).join(' | '));
  ok('U10: Eingabefelder sind einheitlich hoch (29 bis 40 Pixel)', feldhoch.length === 0, [...new Set(feldhoch)].slice(0, 30).join(' | '));
  console.log('   Schriftgrößen der Tabellenköpfe:', Object.entries(thGross).map(([g, l]) => `${g}: ${l.length} Seiten` + (l.length < 6 ? ' (' + l.join(', ') + ')' : '')).join(' · '));
  ok('U10: Tabellenköpfe haben überall dieselbe Schriftgröße', Object.keys(thGross).length <= 1, Object.entries(thGross).map(([g, l]) => `${g}: ${l.slice(0, 5).join(', ')}`).join(' | '));
  console.log('   Beschriftungen mit „Druck“ oder „PDF“:', Object.entries(druckNamen).map(([n, s]) => `„${n}“ ${[...s].slice(0, 3).join(', ')}`).join(' · '));
  const gemischt = Object.keys(druckNamen).filter(n => /ansehen \/ drucken|drucken \/ PDF|PDF ansehen|📄/i.test(n));
  ok('U11: Drucken, PDF und Ansehen heißen überall gleich (keine Mischformen wie „ansehen / drucken“, „PDF ansehen“, „📄 PDF“)', gemischt.length === 0 && 'Drucken' in druckNamen && 'PDF' in druckNamen, gemischt);
  await gehe(p, `#/kunde/${kunden[0]}`, 900);
  const kz = await p.evaluate(() => { const z = [...document.querySelectorAll('#inhalt .zeile')].filter(x => x.offsetParent && x.querySelector(':scope > label') && x.querySelector(':scope > label').textContent.trim() && x.querySelector(':scope > div input:not([type=checkbox]):not([type=radio]):not([type=hidden]), :scope > div select, :scope > div textarea'));
    const verbunden = z.filter(x => { const l = x.querySelector(':scope > label'); return l.htmlFor && document.getElementById(l.htmlFor); });
    const l0 = z[0] && z[0].querySelector(':scope > label'); if (l0) l0.click();
    return { zeilen: z.length, verbunden: verbunden.length, fokus: l0 ? document.activeElement && document.activeElement.id === l0.htmlFor : false, ohne: z.filter(x => !verbunden.includes(x)).slice(0, 5).map(x => x.querySelector(':scope > label').textContent.trim()) }; });
  ok('U13: Im Kundenstamm ist jede Formularzeile mit ihrem Feld verbunden; ein Klick auf die Beschriftung setzt ins Feld', kz.zeilen > 15 && kz.verbunden === kz.zeilen && kz.fokus, kz);
  ok('U13: Höchstens 3 Prozent der Eingabefelder ohne Beschriftung, die Vorlesehilfen finden', ohne <= felder * 0.03, `${ohne} von ${felder}: ` + Object.entries(ohneWo).slice(0, 25).map(([r, t]) => `${r} (${t})`).join(' | '));

  // ---------- Handy und Tablet: Überstand ----------
  for (const breite of [390, 820]) {
    // ohne Handy-Emulation: Dort wächst die gemeldete Fensterbreite mit dem Inhalt, und ein Überstand bliebe unbemerkt
    const c2 = await b.newContext({ viewport: { width: breite, height: 844 }, locale: 'de-DE', hasTouch: true });
    const q = await anmelden(c2, 'jonas', 'geheim12345'); const ueber = [];
    for (const r of routen) { await gehe(q, r, 550);
      const x = await q.evaluate(breite => { const de = document.documentElement, w = Math.min(window.innerWidth, breite); const u = de.scrollWidth - w;
        if (u <= 2) return null;
        // das breiteste Element außerhalb scrollbarer Behälter nennen
        let schuld = '';
        for (const e of document.querySelectorAll('#inhalt *, .kopf *, header *')) { const r = e.getBoundingClientRect(); if (r.right > w + 2 && r.width > 0) {
          let a = e.parentElement, innen = false; while (a && a !== document.body) { const s = getComputedStyle(a); if (/(auto|scroll|hidden)/.test(s.overflowX) && a.clientWidth < a.scrollWidth + 1 && a.getBoundingClientRect().right <= w + 2) { innen = true; break; } a = a.parentElement; }
          if (!innen) { schuld = `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}${e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).join('.') : ''} rechts ${Math.round(r.right)}`; break; } } }
        return { u, schuld }; }, breite);
      if (x) ueber.push(`${r} +${x.u}px [${x.schuld}]`); }
    ok(`U15: Bei ${breite} Pixel Breite ragt keine Seite waagrecht über den Rand`, ueber.length === 0, `${ueber.length} Seiten: ` + ueber.slice(0, 40).join(' | '));
    await c2.close(); }

  // ---------- U14: Rolle Werkstatt ----------
  const c3 = await b.newContext({ viewport: { width: 1400, height: 950 }, locale: 'de-DE' });
  const w = await anmelden(c3, 'werk', 'Pruefung#2026'); await gehe(w, '#/auftraege', 900);
  const wk = await w.evaluate(() => ({ zeilen: document.querySelectorAll('#inhalt table tr').length, kundenlinks: [...document.querySelectorAll('a[href^="#/kunde/"]')].length, name: /QX/.test(document.querySelector('#inhalt').innerText) }));
  ok('U14: In der Rolle Werkstatt führt in der Auftragsliste kein Verweis auf die Kundenseite; der Kundenname steht als Text da', wk.zeilen > 1 && wk.kundenlinks === 0 && wk.name, wk);
  const wa = await w.evaluate(async () => { const a = await (await fetch('/api/auftraege?status=')).json(); return (Array.isArray(a) ? a : a.liste || []).map(x => x.id)[0]; });
  await gehe(w, `#/auftrag/${wa}/werkstatt`, 1000);
  const wk2 = await w.evaluate(() => ({ kundenlinks: [...document.querySelectorAll('a[href^="#/kunde/"]')].map(a => a.outerHTML.slice(0, 80)), auftragslinks: document.querySelectorAll('a[href^="#/auftrag/"]').length,
    zurueck: document.querySelector('#kopf a.zurueck')?.getAttribute('href'), kopf: document.querySelector('#kopf .kontext')?.innerText || '', verboten: [...document.querySelectorAll('#inhalt a[href^="#/"], #kopf a[href^="#/"]')].map(a => a.getAttribute('href')).filter(h => { const b = ROUTE_BEREICH[h.slice(2).split(/[/?]/)[0]]; return b && !darf(b); }) }));
  ok('U14: Auch im Kopf des Auftrags gibt es für die Werkstatt keinen Verweis auf die Kundenseite (die übrigen Verweise bleiben)', wk2.kundenlinks.length === 0 && wk2.auftragslinks > 0, wk2);
  const wkName = await w.evaluate(async id => (await (await fetch('/api/auftraege/' + id)).json()).kunde, wa);
  ok('U14: Der Kundenname steht im Kopf weiter als Text, „Zurück“ führt auf eine erlaubte Seite, und kein Verweis der Seite zeigt in einen gesperrten Bereich', wkName && wk2.kopf.includes(wkName) && wk2.zurueck === '#/auftraege' && wk2.verboten.length === 0, { wkName, ...wk2 });
  await c3.close();

  // ---------- U12: Hauptschaltflächen ----------
  await gehe(p, '#/einstellungen/service/export', 900);
  const dv = await p.evaluate(() => [...document.querySelectorAll('#inhalt button')].filter(e => /DATEV-Einstellungen speichern/.test(e.innerText)).map(e => e.className));
  ok('U12: „DATEV-Einstellungen speichern“ ist eine Hauptschaltfläche', dv.length === 1 && /prim/.test(dv[0]), dv);

  // ---------- Z12/K10: Seite „Gesetzliche Werte“ ----------
  await gehe(p, '#/einstellungen/kalkulation/rechtswerte', 900);
  let rw = await p.evaluate(() => ({ titel: document.querySelector('#inhalt h2')?.innerText, tabellen: document.querySelectorAll('#inhalt table.stichtag').length, text: document.querySelector('#inhalt').innerText }));
  ok('Gesetzliche Werte: drei Tabellen mit den hinterlegten Sätzen (19 %, 1,52 %, 14,60 €)', rw.titel === 'Gesetzliche Werte' && rw.tabellen === 3 && /19,00 %/.test(rw.text) && /1,52 %/.test(rw.text) && /14,60 €/.test(rw.text) && /hinterlegt/.test(rw.text), rw.text.slice(0, 600));
  await p.fill('#rwLohn [data-neu="ab"]', '2028-01-01'); await p.fill('#rwLohn [data-neu="satz"]', '15,20'); await p.click('#rwLohn [data-neu="ok"]'); await p.waitForTimeout(900);
  rw = await p.evaluate(() => document.querySelector('#rwLohn').innerText);
  ok('Mindestlohn ab 01.01.2028 eingetragen: Zeile mit 15,20 € und Minijob-Grenze 659 €, als eigener Eintrag entfernbar', /01\.01\.2028/.test(rw) && /15,20 €/.test(rw) && /659,00 €/.test(rw) && /Entfernen/.test(rw), rw);
  await p.fill('#rwSteuer [data-neu="ab"]', '2028-01-01'); await p.fill('#rwSteuer [data-neu="regel"]', '20'); await p.fill('#rwSteuer [data-neu="ermaessigt"]', '7'); await p.click('#rwSteuer [data-neu="ok"]'); await p.waitForTimeout(900);
  rw = await p.evaluate(() => document.querySelector('#rwSteuer').innerText);
  ok('Umsatzsteuersatz ab 01.01.2028 eingetragen', /01\.01\.2028/.test(rw) && /20,00 %/.test(rw), rw);
  await p.fill('#rwSteuer [data-neu="ab"]', '2029-01-01'); await p.fill('#rwSteuer [data-neu="regel"]', '5'); await p.fill('#rwSteuer [data-neu="ermaessigt"]', '7'); await p.click('#rwSteuer [data-neu="ok"]'); await p.waitForTimeout(900);
  const meldung = await p.evaluate(() => document.querySelector('#toast').innerText);
  ok('Unsinniger Eintrag (ermäßigter Satz über dem Regelsatz) wird mit einer Meldung abgelehnt', /Regelsatz/.test(meldung), meldung);
  await p.selectOption('#rwZins [data-neu="ab"]', '2027-01-01'); await p.fill('#rwZins [data-neu="satz"]', '1,75'); await p.click('#rwZins [data-neu="ok"]'); await p.waitForTimeout(900);
  rw = await p.evaluate(() => document.querySelector('#rwZins').innerText);
  ok('Basiszinssatz ab 01.01.2027 eingetragen', /01\.01\.2027/.test(rw) && /1,75 %/.test(rw) && /Entfernen/.test(rw), rw);
  await gehe(p, '#/einstellungen/texte/mahnungen', 900);
  const mz = await p.evaluate(() => document.querySelector('#mzBasis')?.innerText || '');
  ok('Einstellungen der Mahnungen zeigen den Stand des Basiszinssatzes und den Weg zur Pflege', /1,52 %/.test(mz) && /Sätze pflegen/.test(mz), mz);

  // ---------- E5: Grenzen im Formular ----------
  await gehe(p, '#/einstellungen/auftraege', 900);
  const gr = await p.evaluate(() => ['nachfass_tage', 'anfrage_tage', 'kundennr_start'].map(n => { const e = document.querySelector(`[name=${n}]`); return e ? `${n}:${e.min}-${e.max}` : n + ':fehlt'; }));
  ok('E5: Zahlenfelder der Einstellungen tragen Mindest- und Höchstwert', gr.join(' ') === 'nachfass_tage:0-365 anfrage_tage:0-365 kundennr_start:1-99999999', gr);
  await p.fill('[name=nachfass_tage]', '-30'); await p.click('#sp'); await p.waitForTimeout(900);
  const m2 = await p.evaluate(() => document.querySelector('#toast').innerText);
  const nf = await api('einstellungen');
  ok('E5: „Nachfassen nach −30 Tagen“ wird beim Speichern mit einer Meldung abgelehnt, der alte Wert bleibt', /zwischen 0 und 365/.test(m2) && nf.nachfass_tage === 10, [m2, nf.nachfass_tage]);

  ok('Keine Skript- oder Serverfehler', jsFehler.length === 0, jsFehler.slice(0, 6));
  console.log('FEHLER: ' + JSON.stringify(fehler));
  await b.close();
})().catch(e => { console.log('ABBRUCH', e); console.log('FEHLER: ["Abbruch"]'); process.exit(1); });
