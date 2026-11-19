// Version 152, Bedienoberfläche zum Widerrufsrecht: Schalter im Angebot („Vertrag außerhalb der Geschäftsräume geschlossen?“),
// Datum und Fristende, Hinweise, Sperre im Kalender (Planung und Monat), Rückfrage beim Termin in der Frist, Blätter im PDF.
// Baut sich die Prüfinstanz selbst frisch auf (Port 8799).
const { chromium } = require('playwright');
const { execSync } = require('child_process');
const fs = require('fs');
const U = 'http://127.0.0.1:8799', BILD = '/tmp/claude-0/t/lauf/bild152';
const fehler = [];
const ok = (name, bed, info) => { console.log((bed ? 'ok   ' : 'FEHLER ') + name + (bed ? '' : '  → ' + String(info === undefined ? '' : typeof info === 'string' ? info : JSON.stringify(info)).slice(0, 500))); if (!bed) fehler.push(name); };
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const tag = n => { const d = new Date(); d.setDate(d.getDate() + n); return iso(d); };
(async () => {
  execSync('bash /tmp/claude-0/t/v25/neu.sh', { stdio: 'ignore' }); execSync('mkdir -p ' + BILD);
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1400, height: 1000 }, locale: 'de-DE' }); const p = await ctx.newPage();
  const stoerung = []; p.on('pageerror', e => stoerung.push('Skript: ' + String(e).slice(0, 160)));
  const erlaubt = /\/api\/(logo|unterschrift)\b/;
  p.on('response', r => { if (r.status() >= 400 && r.status() !== 409 && !erlaubt.test(r.url())) stoerung.push(`Abruf ${r.status()}: ${r.url().replace(U, '')}`); });
  p.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) stoerung.push('Konsole: ' + m.text().slice(0, 160)); });
  const ruf = async (m, pf, d) => await p.evaluate(async ([m, pf, d]) => { const r = await fetch('/api/' + pf, { method: m, headers: { 'Content-Type': 'application/json' }, body: d ? JSON.stringify(d) : undefined }); return await r.json(); }, [m, pf, d]);
  const text = async sel => ((await p.textContent(sel)) || '').replace(/\s+/g, ' ').trim();

  await p.goto(U + '/'); await p.waitForSelector('#anmForm');
  await ruf('POST', 'anmeldung/einrichten', { name: 'Jonas', login: 'jonas', passwort: 'geheim12345', passwort2: 'geheim12345', firma: 'Muster Schreinerei' });
  await p.goto(U + '/'); await p.waitForSelector('#leiste', { timeout: 20000 });
  await ruf('PUT', 'einstellungen', { firma: 'Muster Schreinerei', firma_inhaber: 'Jonas Muster', firma_anschrift: 'Weg 1\n88069 Tettnang', steuernummer: '12/345/67890' });
  const k = await ruf('POST', 'kunden', { kurzname: 'Haus, Hanna', nachname: 'Haus', vorname: 'Hanna', anredeform: 'Frau', strasse: 'Gartenweg', hausnr: '4', plz: '88069', ort: 'Tettnang', gruppe: 'Privatkunde' });
  const a = await ruf('POST', 'auftraege', { kunde_id: k.id, bezeichnung: 'Einbauschrank Flur' });
  const po = await ruf('POST', `auftraege/${a.id}/positionen`, { text: 'Einbauschrank nach Aufmaß' }); const pid = po.id || po.position.id;
  await ruf('PUT', `positionen/${pid}`, { einzelpreis: 4200, preis_manuell: 1, menge: 1 });
  const ang = await ruf('POST', `auftraege/${a.id}/belege`, { art: 'angebot' });
  await p.goto(U + '/#/kunden'); await p.waitForSelector('#inhalt .titel'); await p.goto(U + `/#/beleg/${ang.id}`); await p.waitForSelector('[name=agv]');

  // ---------- Schalter ----------
  ok('Angebot zeigt den Abschnitt „Widerrufsrecht“ mit der Frage, Vorgabe Nein', /Vertrag außerhalb der Geschäftsräume geschlossen\?/.test(await text('#f')) && await p.isChecked('[name=agv][value="0"]'));
  ok('ohne „Ja“ gibt es weder Datum noch Hinweise', (await p.locator('#agvD').count()) === 0 && (await p.locator('#agvHinweise').count()) === 0);
  await p.check('[name=agv][value="1"]'); await p.waitForSelector('#agvD');
  ok('nach „Ja“: Datum des Vertragsschlusses ist mit dem Belegdatum vorbelegt, das Fristende steht daneben', (await p.inputValue('#agvD')) === iso(new Date()) && /Widerrufsfrist bis \d\d\.\d\d\.\d{4}/.test(await text('#agvBis')), await text('#agvBis'));
  const hin = await text('#agvHinweise');
  ok('Hinweis: auf Papier übergeben', /auf Papier übergeben/.test(hin), hin);
  ok('Hinweis: Telefon und E-Mail des Betriebs fehlen noch', /fehlt noch: .*Telefon, E-Mail/.test(hin), hin);
  await p.screenshot({ path: BILD + '/1_angebot_schalter.png', fullPage: true });
  await ruf('PUT', 'einstellungen', { firma_telefon: '07542 12345', firma_email: 'info@muster.example' });
  await p.reload(); await p.waitForSelector('#agvD');
  ok('nach dem Eintragen in den Einstellungen ist der Hinweis weg', !/fehlt noch/.test(await text('#agvHinweise')), await text('#agvHinweise'));
  // Vorschau zeigt den Beleg mit den angehängten Blättern (eine Zeichenfläche je Seite)
  await p.waitForFunction(() => document.querySelectorAll('#vorschau canvas').length >= 3, null, { timeout: 30000 }).catch(() => {});
  const flaechen = await p.locator('#vorschau canvas').count();
  ok('Vorschau des Angebots zeigt die zusätzlichen Seiten', flaechen >= 3, flaechen);
  // Datum ändern
  await p.fill('#agvD', tag(-2)); await p.dispatchEvent('#agvD', 'change'); await p.waitForTimeout(700); await p.waitForSelector('#agvD');
  ok('Datum geändert: gespeichert', (await ruf('GET', `belege/${ang.id}`)).vertrag_am === tag(-2));
  await p.fill('#agvD', iso(new Date())); await p.dispatchEvent('#agvD', 'change'); await p.waitForTimeout(700);

  // ---------- PDF ----------
  const pdf = await p.evaluate(async id => { const r = await fetch(`/druck/${id}.pdf`); const buf = new Uint8Array(await r.arrayBuffer()); return { status: r.status, typ: r.headers.get('content-type'), bytes: Array.from(buf) }; }, ang.id);
  fs.writeFileSync(BILD + '/angebot.pdf', Buffer.from(pdf.bytes));
  ok('PDF des Angebots wird erzeugt', pdf.status === 200 && /pdf/.test(pdf.typ) && pdf.bytes.length > 20000, [pdf.status, pdf.typ, pdf.bytes.length]);
  const seiten = execSync(`pdftotext -layout ${BILD}/angebot.pdf -`).toString().split('\f').map(s => s.replace(/\s+/g, ' '));
  ok('PDF: Seite 1 Angebot mit Hinweis, Seite 2 Belehrung und Formular, Seite 3 Erklärungen des Kunden (danach die AGB)',
    seiten.length >= 3 && /Angebot/.test(seiten[0]) && /außerhalb von Geschäftsräumen geschlossen/.test(seiten[0]) && /Widerrufsbelehrung/.test(seiten[1]) && /Muster-Widerrufsformular/.test(seiten[1])
    && /Unzutreffendes streichen/.test(seiten[1]) && /Erklärungen des Kunden/.test(seiten[2]) && /Empfangsbestätigung/.test(seiten[2]) && !/Widerrufsbelehrung Widerrufsrecht/.test(seiten[2]), seiten.map(s => s.slice(0, 60)));
  ok('PDF: die Belehrung nennt Telefon und E-Mail des Betriebs', /Telefon 07542 12345, E-Mail info@muster\.example\)/.test(seiten[1]), (seiten[1] || '').slice(200, 500));
  execSync(`cd ${BILD} && pdftoppm -r 60 -png angebot.pdf seite`);

  // ---------- Kalender ----------
  await p.goto(U + `/#/kalender/planung/${tag(-3)}`); await p.waitForSelector('.kp-b.wdr', { timeout: 15000 });
  const balken = await text('.kp-b.wdr');
  ok('Planung: Sperre „Widerrufsfrist bis …“ in der Zeile des Auftrags', /Widerrufsfrist bis \d\d\.\d\d\./.test(balken), balken);
  const breite = await p.evaluate(() => { const b = document.querySelector('.kp-b.wdr'), z = b.closest('.kp-zeile'); const tw = parseFloat(getComputedStyle(document.querySelector('.kp')).getPropertyValue('--tw')); return { tage: Math.round((b.offsetWidth + 2) / tw), auftrag: z.querySelector('.kp-label a').textContent }; });
  ok('die Sperre reicht vom Vertragstag bis zum Fristende (15 bis 18 Tage) und steht beim richtigen Auftrag', breite.tage >= 15 && breite.tage <= 18 && /Haus/.test(breite.auftrag), breite);
  await p.screenshot({ path: BILD + '/2_kalender_planung.png', fullPage: false });
  await p.goto(U + `/#/kalender/monat/${tag(0)}`); await p.waitForSelector('.km-e.wdr', { timeout: 15000 });
  const mon = await p.$$eval('.km-e.wdr', l => l.map(x => x.textContent.trim()));
  ok('Monat: an jedem Tag der Frist steht „Widerrufsfrist“, am letzten „Ende Widerrufsfrist“', mon.length >= 10 && mon.some(x => /^Ende Widerrufsfrist/.test(x)) && mon.every(x => /Haus/.test(x)), mon.slice(0, 3));
  await p.screenshot({ path: BILD + '/3_kalender_monat.png', fullPage: false });
  // Termin in der Frist anlegen → Rückfrage
  await p.goto(U + `/#/kalender/planung/${tag(-3)}`); await p.waitForSelector('.kp-b.wdr');
  await p.click('#kNeu'); await p.waitForSelector('.modal [name=auftrag_id]');
  await p.selectOption('.modal [name=auftrag_id]', String(a.id)); await p.fill('.modal [name=von]', tag(3)); await p.fill('.modal [name=bis]', tag(3));
  await p.click('.modal .btn.prim'); await p.waitForFunction(() => /Widerrufsfrist/.test(document.body.innerText) && document.querySelectorAll('.modal').length >= 1, null, { timeout: 8000 });
  const frage = await p.evaluate(() => Array.from(document.querySelectorAll('.modal')).map(m => m.innerText).join(' | '));
  ok('Termin in der Frist: Rückfrage nennt Vertragstag, Fristende und die Erklärung des Kunden', /liegt in der Widerrufsfrist/.test(frage) && /ausdrücklich verlangt/.test(frage) && /Trotzdem eintragen/.test(frage), frage.slice(0, 300));
  await p.screenshot({ path: BILD + '/4_rueckfrage.png' });
  await p.getByRole('button', { name: 'Abbrechen' }).last().click(); await p.waitForTimeout(500);
  ok('abgebrochen: kein Termin angelegt', (await ruf('GET', `termine?auftrag=${a.id}`)).length === 0);
  // Beginn verlangt → heller Hinweis
  await ruf('PUT', `belege/${ang.id}`, { agv_beginn: true });
  await p.goto(U + `/#/kalender/monat/${tag(0)}`); await p.waitForSelector('.km-e.wdr.frei', { timeout: 15000 });
  ok('Kunde hat den Beginn verlangt: Sperre nur noch als heller Hinweis', (await p.locator('.km-e.wdr.frei').count()) >= 10);
  // Klick auf die Sperre führt zum Beleg
  await p.click('.km-e.wdr'); await p.waitForSelector('[name=agv]');
  ok('Klick auf die Sperre öffnet den Beleg', new RegExp(`#/beleg/${ang.id}$`).test(p.url()) && await p.isChecked('#agvB'));
  // Rechnung hat den Abschnitt nicht
  const re = await ruf('POST', `auftraege/${a.id}/belege`, { art: 'rechnung' });
  // erst weiter, wenn wirklich die Rechnung dasteht (vorher zeigt die Seite noch das Angebot, das auch ein Formular #f hat)
  await p.goto(U + `/#/beleg/${re.id}`); await p.waitForFunction(() => /Rechnung/.test((document.querySelector('#inhalt .titel h2') || {}).innerText || ''), null, { timeout: 15000 }); await p.waitForSelector('#f');
  ok('Rechnung: kein Abschnitt „Widerrufsrecht“', (await p.locator('[name=agv]').count()) === 0);
  // Einstellungen: Texte
  await p.goto(U + '/#/einstellungen/belege'); await p.waitForSelector('[name=widerruf_belehrung]', { timeout: 15000 });
  const ph = await p.getAttribute('[name=widerruf_belehrung]', 'placeholder');
  ok('Einstellungen › Belege: drei Textfelder, das gesetzliche Muster steht grau als Vorgabe', /binnen vierzehn Tagen/.test(ph) && (await p.locator('[name=widerruf_hinweis]').count()) === 1 && (await p.locator('[name=widerruf_erklaerung]').count()) === 1, (ph || '').slice(0, 80));
  await p.locator('[name=widerruf_belehrung]').scrollIntoViewIfNeeded(); await p.screenshot({ path: BILD + '/5_einstellungen.png' });
  ok('keine Skriptfehler und keine fehlgeschlagenen Abrufe', stoerung.length === 0, stoerung);
  await b.close();
  console.log('FEHLER: ' + JSON.stringify(fehler));
})().catch(e => { console.log('FEHLER Abbruch: ' + e); console.log('FEHLER: ["Abbruch"]'); process.exit(1); });
