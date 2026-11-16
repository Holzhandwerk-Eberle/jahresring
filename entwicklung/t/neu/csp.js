// Inhaltsschutz: Seiten laufen ohne Verstöße, eingeschleuste Skripte laufen nicht. Erwartet Daten aus v25/s/t10.js (Benutzer jonas).
const { chromium } = require('playwright');
const U = process.argv[2] || 'http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({viewport: {width: 1300, height: 900}, locale: 'de-DE'}); const p = await ctx.newPage(); p.setDefaultTimeout(8000);
  let wo = ''; const funde = [];
  p.on('console', m => { if (/Content Security Policy|Refused to/i.test(m.text())) funde.push(wo + ': ' + m.text().slice(0, 220)); });
  p.on('pageerror', e => funde.push(wo + ' [JS]: ' + e.message.slice(0, 160)));
  await p.goto(U + '/'); await p.waitForTimeout(600);
  await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1500);
  const r = await p.request.get(U + '/'); const csp = r.headers()['content-security-policy'] || '';
  console.log((/script-src 'self' 'nonce-/.test(csp) && !/unsafe-inline'; img/.test(csp.split('style-src')[0])) ? 'ok   ' : 'FEHLER', 'Kopfzeile:', csp.slice(0, 90));
  const api = pfad => p.evaluate(async pfad => (await fetch('/api/' + pfad)).json(), pfad);
  const belege = await api('belege').catch(() => []), auftraege = await api('auftraege').catch(() => []);
  const bid = (Array.isArray(belege) && belege[0] || {}).id, aid = (Array.isArray(auftraege) && auftraege[0] || {}).id;
  const seiten = ['/hilfe/handbuch.html', '/hilfe/datenschutz.html', '/hilfe/verfahrensdokumentation.html', '/hilfe/installation.html', '/hilfe/kalkulation.html', '/stempel', '/scan', '/zuschnitt',
    '/druck/1', '/druck/2', '/papier/1/laufzettel', aid && `/papier/${aid}/laufzettel`, '/liste/lager', '/liste/etiketten?ids=1', '/zertifikat', '/#/start', '/#/einstellungen/programm', '/#/korrespondenz/statistik'].filter(Boolean);
  for (const s of seiten) { wo = s; const x = await p.goto(U + s).catch(e => null); await p.waitForTimeout(900); if (x && x.status() >= 500) funde.push(s + ' Status ' + x.status()); }
  // Druckknopf vorhanden und verdrahtet?
  wo = 'Druckknopf'; await p.goto(U + '/hilfe/kalkulation.html'); await p.waitForTimeout(500);
  await p.evaluate(() => { window.__gedruckt = 0; window.print = () => { window.__gedruckt++; }; }); await p.click('[data-drucken]');
  console.log((await p.evaluate(() => window.__gedruckt)) === 1 ? 'ok   ' : 'FEHLER', 'Druckknopf der Hilfeseite löst Drucken aus');
  { await p.goto(U + '/druck/1'); await p.waitForTimeout(500); const kn = await p.$('[data-drucken]');
    if (kn) { await p.evaluate(() => { window.__gedruckt = 0; window.print = () => { window.__gedruckt++; }; }); await kn.click(); console.log((await p.evaluate(() => window.__gedruckt)) === 1 ? 'ok   ' : 'FEHLER', 'Druckknopf der Belegansicht'); } }
  console.log(funde.length ? 'FEHLER' : 'ok   ', 'keine Verstöße auf', seiten.length, 'Seiten', funde.slice(0, 12));
  // eingeschleustes Skript darf nicht laufen
  await p.goto(U + '/#/start'); await p.waitForTimeout(800); wo = 'Einschleusung (erwartet)'; const n = funde.length;
  const lief = await p.evaluate(async () => { const d = document.createElement('div'); d.innerHTML = '<img src=x onerror="window.__inj=1">'; document.body.appendChild(d);
    const s = document.createElement('script'); s.textContent = 'window.__inj2=1'; document.body.appendChild(s); await new Promise(r => setTimeout(r, 400)); return [window.__inj, window.__inj2]; });
  console.log(!lief[0] && !lief[1] ? 'ok   ' : 'FEHLER', 'eingeschleustes onerror und <script> laufen nicht', lief, '(gemeldete Verstöße:', funde.length - n + ')');
  const fremd = await p.evaluate(async () => { try { await fetch('https://example.com/', {mode: 'no-cors'}); return 'gesendet'; } catch (e) { return 'blockiert'; } });
  console.log(fremd === 'blockiert' ? 'ok   ' : 'FEHLER', 'Verbindung zu fremder Adresse blockiert:', fremd);
  await b.close(); })();
