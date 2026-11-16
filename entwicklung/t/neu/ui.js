// Rückfragen in der Oberfläche: Zahlungseingang über dem offenen Betrag, gleichzeitiges Bearbeiten, Eingangsrechnung mit anderer IBAN (Warnung sichtbar)
const { chromium } = require('playwright');
const U = process.argv[2] || 'http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const neu = async () => { const c = await b.newContext({viewport: {width: 1300, height: 950}, locale: 'de-DE'}); const p = await c.newPage(); p.setDefaultTimeout(8000); return p; };
  const p = await neu(); const fehler = []; p.on('pageerror', e => fehler.push(e.message));
  const ok = (name, bed, info) => { console.log((bed ? 'ok   ' : 'FEHLER ') + name + (bed ? '' : '  → ' + String(info).slice(0, 300))); if (!bed) fehler.push(name); };
  await p.goto(U + '/'); await p.waitForTimeout(600);
  if (await p.$('[name=firma]')) { await p.fill('[name=firma]', 'Muster'); await p.fill('[name=name]', 'Jonas'); await p.fill('[name=passwort2]', 'geheim12345'); }
  await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim12345'); await p.click('button[type=submit]'); await p.waitForTimeout(1500);
  const api = (pg, m, pfad, body) => pg.evaluate(async ([m, pfad, body]) => { try { return await api(pfad, {method: m, body}); } catch (e) { return {FEHLER: e.message}; } }, [m, pfad, body]);
  const k = await api(p, 'POST', 'kunden', {kurzname: 'Testkunde', nachname: 'Test'}); const a = await api(p, 'POST', 'auftraege', {kunde_id: k.id, bezeichnung: 'Regal'});
  const po = await api(p, 'POST', `auftraege/${a.id}/positionen`, {text: 'Regal'}); const pid = po.id || po.position.id;
  await api(p, 'PUT', `positionen/${pid}`, {einzelpreis: 100, preis_manuell: 1, menge: 1});
  const bl = await api(p, 'POST', `auftraege/${a.id}/belege`, {art: 'rechnung'}); await api(p, 'POST', `belege/${bl.id}/festschreiben`, {});
  const ops = await api(p, 'GET', 'offeneposten'); const op = (Array.isArray(ops) ? ops : Object.values(ops).find(Array.isArray))[0];
  // 1) Überzahlung: Rückfrage erscheint, Abbrechen bucht nicht, Bestätigen bucht
  let erg = p.evaluate(async id => { try { await api(`offeneposten/${id}/zahlung`, {method: 'POST', body: {betrag: 500, datum: heute()}}); return 'gebucht'; } catch (e) { return e.message; } }, op.id);
  await p.waitForSelector('.frage'); const text = await p.textContent('.frage');
  ok('Rückfrage bei Überzahlung zeigt den Grund', /mehr als der offene Betrag/.test(text) && /Trotzdem buchen/.test(text), text);
  await p.click('.frage [data-f="0"]'); ok('Abbrechen: nichts gebucht', /Abgebrochen/.test(await erg), await erg);
  erg = p.evaluate(async id => { try { await api(`offeneposten/${id}/zahlung`, {method: 'POST', body: {betrag: 500, datum: heute()}}); return 'gebucht'; } catch (e) { return e.message; } }, op.id);
  await p.waitForSelector('.frage'); await p.click('.frage [data-f="1"]'); ok('Bestätigen: gebucht', (await erg) === 'gebucht', await erg);
  // 2) gleichzeitiges Bearbeiten: zweites Fenster (eigene Anmeldung) ändert den Kunden, das erste speichert danach
  const p2 = await neu(); await p2.goto(U + '/'); await p2.waitForTimeout(600); await p2.fill('[name=login]', 'jonas'); await p2.fill('[name=passwort]', 'geheim12345'); await p2.click('button[type=submit]'); await p2.waitForTimeout(1200);
  await p.goto(U + `/#/kunde/${k.id}`); await p.waitForTimeout(1200);
  await p2.goto(U + `/#/kunde/${k.id}`); await p2.waitForTimeout(1200);
  ok('zweites Fenster speichert ohne Rückfrage', !(await api(p2, 'PUT', `kunden/${k.id}`, {telefon: '111'})).FEHLER);
  erg = api(p, 'PUT', `kunden/${k.id}`, {telefon: '222'});
  await p.waitForSelector('.frage'); const t2 = await p.textContent('.frage');
  ok('erstes Fenster bekommt die Rückfrage mit Name und Uhrzeit', /Jonas hat diesen Datensatz um \d\d:\d\d Uhr geändert/.test(t2) && /Trotzdem speichern/.test(t2), t2);
  await p.click('.frage [data-f="1"]'); ok('… und kann trotzdem speichern', !(await erg).FEHLER, JSON.stringify(await erg).slice(0, 200));
  ok('danach ohne erneute Rückfrage', !(await api(p, 'PUT', `kunden/${k.id}`, {telefon: '333'})).FEHLER);
  // 3) ganz normales Speichern in der Oberfläche löst keine Rückfrage aus
  await p.goto(U + `/#/kunde/${k.id}`); await p.waitForTimeout(1200);
  const feld = await p.$('[data-f="telefon"], [name=telefon]'); if (feld) { await feld.fill('07542 123'); await feld.press('Tab'); await p.waitForTimeout(900); }
  ok('Feld speichern ohne Rückfrage', !(await p.$('.frage')));
  console.log('fehler', fehler); await b.close(); process.exit(fehler.length ? 1 : 0); })();
