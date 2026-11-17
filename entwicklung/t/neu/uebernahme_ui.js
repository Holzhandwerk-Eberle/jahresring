// Version 150, Bedienoberfläche: Seite „Ersten Zugang anlegen“ → Daten vom bisherigen PC übernehmen.
// Erwartet den alten Bestand aus uebernahme150.py (/tmp/claude-0/t/up150/alt und extern); baut sich den neuen PC selbst (Port 8797).
const { chromium } = require('playwright');
const { execSync } = require('child_process');
const fs = require('fs');
const Z = '/tmp/claude-0/t/up150', U = 'http://127.0.0.1:8797', BILD = Z + '/bild';
const fehler = [];
const ok = (name, bed, info) => { console.log((bed ? 'ok   ' : 'FEHLER ') + name + (bed ? '' : '  → ' + String(info === undefined ? '' : typeof info === 'string' ? info : JSON.stringify(info)).slice(0, 500))); if (!bed) fehler.push(name); };
(async () => {
  execSync(`bash ${Z}/neupc.sh 8797`, { stdio: 'ignore' });
  execSync(`cp -r "${Z}/alt/Jahresring" "${Z}/neupc/Jahresring alt" && mkdir -p ${Z}/neupc/Sicherung ${BILD} && cp ${Z}/extern/*.jrs ${Z}/neupc/Sicherung/`);
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, locale: 'de-DE' }); const p = await ctx.newPage();
  const stoerung = []; p.on('pageerror', e => stoerung.push('Skript: ' + String(e).slice(0, 160)));
  p.on('console', m => { if (m.type() === 'error' && !/401|403|400|428/.test(m.text())) stoerung.push('Konsole: ' + m.text().slice(0, 160)); });
  const text = async sel => (await p.textContent(sel)).replace(/\s+/g, ' ').trim();

  await p.goto(U + '/'); await p.waitForSelector('#anmForm');
  ok('Seite „Ersten Zugang anlegen“ mit dem Knopf zur Übernahme', (await text('.anm-box h2')) === 'Ersten Zugang anlegen' && (await text('#anmUeb')).startsWith('Daten vom bisherigen PC übernehmen'));
  await p.waitForSelector('.anm-fund', { timeout: 15000 });
  ok('gefundener Bestand wird gleich gemeldet (Firma und Ort)', /Bisheriger Datenbestand gefunden: Holzwerkstatt Alt/.test(await text('.anm-fund')) && /Jahresring alt/.test(await text('.anm-fund .ub-pfad')), await text('.anm-fund'));
  ok('die Meldung steht oben im Kasten, vor dem Formular, mit eigenem Knopf', await p.evaluate(() => { const f = document.querySelector('.anm-fund'), g = document.querySelector('#anmForm'); return !!document.querySelector('#anmFundKnopf') && f.getBoundingClientRect().bottom <= g.getBoundingClientRect().top && f.getBoundingClientRect().top < 400; }));
  await p.screenshot({ path: BILD + '/1_erster_zugang.png', fullPage: true });

  await p.click('#anmUeb'); await p.waitForSelector('#ubForm');
  ok('Auswahl: Überschrift und gefundene Bestände', (await text('.anm-box h2')) === 'Daten vom bisherigen PC übernehmen' && (await p.locator('#ubListe .ub-karte').count()) >= 2, await text('#ubListe'));
  const karten = await p.$$eval('#ubListe .ub-karte', l => l.map(k => k.textContent.replace(/\s+/g, ' ').trim()));
  ok('Karte des Ordners: Firma, Pfad, Stand, Umfang', /Holzwerkstatt Alt/.test(karten[0]) && /Stand \d\d\.\d\d\.\d{4}, \d\d:\d\d Uhr · 1 Benutzer · 1 Kunde · 1 Beleg · Version 2026/.test(karten[0]), karten[0]);
  ok('Karte der verschlüsselten Sicherung', karten.some(k => /Vollständige Sicherung/.test(k) && /verschlüsselt/.test(k) && /\.zip\.jrs/.test(k)), karten);
  ok('ohne Windows kein Auswahlfenster-Knopf', (await p.locator('#ubOrdner').count()) === 0);
  ok('Karten ragen nicht aus dem Kasten', await p.evaluate(() => { const k = document.querySelector('.anm-box').getBoundingClientRect(); return [...document.querySelectorAll('.ub-karte, .ub-karte .btn')].every(e => { const r = e.getBoundingClientRect(); return r.left >= k.left && r.right <= k.right + 0.5; }); }));
  await p.screenshot({ path: BILD + '/2_auswahl.png', fullPage: true });

  await p.fill('#ubForm [name=pfad]', '/gibt/es/nicht'); await p.click('#ubForm button[type=submit]'); await p.waitForFunction(() => document.querySelector('#ubFehler').textContent.length > 5);
  ok('falscher Ort: Meldung im Klartext, Eingabe bleibt stehen', /gibt es nicht/.test(await text('#ubFehler')) && (await p.inputValue('#ubForm [name=pfad]')) === '/gibt/es/nicht', await text('#ubFehler'));
  await p.click('#ubForm button[type=submit]', { clickCount: 1 }); await p.fill('#ubForm [name=pfad]', ''); await p.click('#ubForm button[type=submit]');
  ok('leere Eingabe: Hinweis', /angeben/.test(await text('#ubFehler')), await text('#ubFehler'));
  await p.click('#ubSuchen'); await p.waitForSelector('#ubListe .ub-karte');
  ok('„erneut suchen“ zeigt die Bestände wieder', (await p.locator('#ubListe .ub-karte').count()) >= 2);
  await p.click('#ubZu'); await p.waitForSelector('#anmForm');
  ok('zurück zum ersten Zugang: Kasten wieder schmal', (await text('.anm-box h2')) === 'Ersten Zugang anlegen' && await p.evaluate(() => !document.querySelector('.anm-box').classList.contains('anm-breit')));
  await p.waitForSelector('#anmFundKnopf', { timeout: 15000 }); await p.click('#anmFundKnopf'); await p.waitForSelector('#ubLos');
  ok('Knopf in der Meldung führt gleich zur Bestätigung dieses Bestands', (await text('.anm-box h2')) === 'Diesen Datenbestand übernehmen?' && /Jahresring alt/.test(await text('.ub-karte')));
  await p.click('#ubAb'); await p.waitForSelector('#ubListe .ub-karte');
  ok('„Abbrechen“ führt zur Auswahl mit allen Beständen', (await p.locator('#ubListe .ub-karte').count()) >= 2);

  // verschlüsselte Sicherung: Kennwort wird verlangt
  await p.locator('#ubListe .ub-karte', { hasText: '.zip.jrs' }).first().locator('button').click(); await p.waitForSelector('#ubLos');
  ok('verschlüsselte Sicherung: Kennwortfeld', (await p.locator('#ubKw').count()) === 1 && (await text('.anm-box h2')) === 'Diesen Datenbestand übernehmen?');
  await p.click('#ubLos'); ok('ohne Kennwort: Hinweis, nichts gestartet', /Sicherungskennwort eingeben/.test(await text('#ubFehler2')));
  await p.fill('#ubKw', 'falsch falsch'); await p.click('#ubLos'); await p.waitForSelector('#ubFehler2:not(:empty)', { timeout: 30000 });
  ok('falsches Kennwort: Meldung, Rückkehr zur Bestätigung', /stimmt nicht/.test(await text('#ubFehler2')) && (await p.locator('#ubKw').count()) === 1, await text('#ubFehler2'));
  await p.screenshot({ path: BILD + '/3_kennwort.png', fullPage: true });
  await p.click('#ubAb'); await p.waitForSelector('#ubListe .ub-karte');

  // Übernahme aus dem Ordner
  await p.locator('#ubListe .ub-karte', { hasText: 'Jahresring alt' }).locator('button').click(); await p.waitForSelector('#ubLos');
  ok('Bestätigung nennt Bestand und Folgen', /Holzwerkstatt Alt/.test(await text('.ub-karte')) && /bleibt unverändert/.test(await text('.anm-box')) && (await p.locator('#ubKw').count()) === 0, await text('.anm-box'));
  await p.screenshot({ path: BILD + '/4_bestaetigen.png', fullPage: true });
  await p.click('#ubLos'); await p.waitForSelector('#ubFertig', { timeout: 120000 });
  const fertig = await text('.anm-box');
  ok('Erfolg: Firma, Umfang, Anmeldehinweis', /Die Daten sind übernommen/.test(fertig) && /Holzwerkstatt Alt: 1 Benutzer, 1 Kunde, 1 Beleg, \d+ Dateien kopiert/.test(fertig) && /bisherigen Benutzernamen und Passwörtern/.test(fertig), fertig);
  ok('Hinweis zum bisherigen PC (ein einzelner Hinweis ohne Nummer)', (await p.locator('ol.ub-hinweise').count()) === 0 && /bisherigen PC/.test(await text('.ub-hinweise')), await text('.anm-box'));
  await p.screenshot({ path: BILD + '/5_fertig.png', fullPage: true });
  await p.click('#ubFertig'); await p.waitForSelector('#anmForm [name=login]');
  ok('danach: Anmeldung statt erstem Zugang, ohne Knopf zur Übernahme', (await text('.anm-box h2')) === 'Anmelden' && (await p.locator('#anmUeb').count()) === 0 && /Holzwerkstatt Alt/.test(await text('.anm-marke')));
  await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('#anmForm button[type=submit]'); await p.waitForSelector('#leiste', { timeout: 20000 });
  ok('Anmeldung mit dem bisherigen Zugang führt ins Programm', await p.evaluate(() => !!document.querySelector('#leiste') && !document.querySelector('.anm-box')));
  await p.goto(U + '/#/einstellungen/service/protokoll'); await p.waitForTimeout(2500);
  const prot = await text('#inhalt');
  ok('Protokollseite zeigt die Übernahme', /Datenbestand übernommen \(Umzug, Wiederherstellung\)/.test(prot) || /Datenbestand auf diesen PC übernommen/.test(prot), prot.slice(0, 300));
  await p.screenshot({ path: BILD + '/6_protokoll.png', fullPage: false });

  // schmales Fenster: nichts läuft aus dem Kasten
  await p.close();
  execSync(`bash ${Z}/neupc.sh 8797`, { stdio: 'ignore' });
  execSync(`cp -r "${Z}/alt/Jahresring" "${Z}/neupc/Jahresring alt" && mkdir -p ${Z}/neupc/Sicherung && cp ${Z}/extern/*.jrs ${Z}/neupc/Sicherung/`);
  const eng = await ctx.newPage(); await eng.setViewportSize({ width: 430, height: 900 });
  eng.on('pageerror', e => stoerung.push('Skript: ' + String(e).slice(0, 160)));
  await eng.goto(U + '/'); await eng.waitForSelector('.anm-fund', { timeout: 15000 }); await eng.click('#anmUeb'); await eng.waitForSelector('#ubListe .ub-karte');
  ok('schmales Fenster: kein waagerechtes Überlaufen', await eng.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
  await eng.screenshot({ path: BILD + '/7_schmal.png', fullPage: true });
  ok('keine Skriptfehler, keine Meldungen der Konsole', stoerung.length === 0, stoerung);
  await b.close();
  execSync(`for f in /proc/[0-9]*/environ; do grep -qa "BUERO_PORT=8797" $f 2>/dev/null && kill $(basename $(dirname $f)) 2>/dev/null; done; true`, { shell: '/bin/bash' });
  console.log('FEHLER: ' + JSON.stringify(fehler));
})().catch(e => { console.log('FEHLER Abbruch → ' + e.stack); console.log('FEHLER: ["Abbruch"]'); process.exit(1); });
