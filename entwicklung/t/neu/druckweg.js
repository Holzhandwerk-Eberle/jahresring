// Druckweg: Die Schaltfläche „Drucken“ muss dasselbe Blatt liefern wie das PDF des Programms.
// Geprüft wird mit einem echten Chrome (unter Xvfb), der ohne Rückfrage „als PDF speichert“ (--kiosk-printing): So läuft der
// Druck wirklich über das Druckfenster des Browsers – nicht nur über die PDF-Erzeugung des Programms.
// Aufruf: xvfb-run -a node druckweg.js   (frische Prüfinstanz, danach s/t10.js für Benutzer und Stammdaten)
const { chromium } = require('playwright'); const fs = require('fs'), path = require('path'), cp = require('child_process');
const U = 'http://127.0.0.1:8799', T = '/tmp/claude-0/t/drucktest', AUS = T + '/aus', PROFIL = T + '/profil', ABL = T + '/ablage';
const DATEN = '/tmp/claude-0/t/v25/eberle-buero/daten', FAKE = '/tmp/claude-0/t/fake/chrome';
const fehler = [];
const ok = (name, bed, info) => { console.log((bed ? 'ok   ' : 'FEHLER ') + name + (bed ? '' : '  → ' + String(info === undefined ? '' : typeof info === 'string' ? info : JSON.stringify(info)).slice(0, 400))); if (!bed) fehler.push(name); };
const warte = ms => new Promise(r => setTimeout(r, ms));
const texte = pdf => cp.execFileSync('pdftotext', ['-layout', pdf, '-'], { maxBuffer: 1 << 26 }).toString().split('\f').slice(0, -1).map(t => t.replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim());
const seiten = pdf => texte(pdf).length;
function bild(pdf, nr) {   // Seite als Graustufenbild (30 dpi) – genug, um Lage und Schwärzung zu vergleichen
  const pre = path.join(T, 'b' + Math.random().toString(36).slice(2));
  cp.execFileSync('pdftoppm', ['-r', '30', '-gray', '-f', String(nr), '-l', String(nr), pdf, pre]);
  const datei = fs.readdirSync(T).filter(f => f.startsWith(path.basename(pre))).map(f => path.join(T, f))[0];
  const roh = fs.readFileSync(datei); fs.unlinkSync(datei);
  const kopf = roh.subarray(0, 40).toString('latin1').match(/^P5\s+(\d+)\s+(\d+)\s+(\d+)\s/);
  return { w: +kopf[1], h: +kopf[2], d: roh.subarray(kopf[0].length) };
}
function abweichung(a, na, b, nb) {   // mittlere Abweichung zweier Seiten in Prozent der Schwärzung (0 = gleich)
  const x = bild(a, na), y = bild(b, nb);
  if (Math.abs(x.w - y.w) > 2 || Math.abs(x.h - y.h) > 2) return 100;   // (angehängte PDF-Seiten können um einen Bildpunkt abweichen)
  const w = Math.min(x.w, y.w), hh = Math.min(x.h, y.h); let s = 0;
  for (let r = 0; r < hh; r++) for (let c = 0; c < w; c++) s += Math.abs(x.d[r * x.w + c] - y.d[r * y.w + c]);
  return s / (w * hh) / 255 * 100;
}
const gleich = (a, b) => JSON.stringify(a) === JSON.stringify(b);

(async () => {
  for (const d of [AUS, PROFIL, ABL]) { fs.rmSync(d, { recursive: true, force: true }); fs.mkdirSync(d, { recursive: true }); }
  fs.mkdirSync(PROFIL + '/Default', { recursive: true });
  const zustand = JSON.stringify({ version: 2, recentDestinations: [{ id: 'Save as PDF', origin: 'local', account: '' }], selectedDestinationId: 'Save as PDF', isHeaderFooterEnabled: false, isCssBackgroundEnabled: true });
  fs.writeFileSync(PROFIL + '/Default/Preferences', JSON.stringify({ printing: { print_preview_sticky_settings: { appState: zustand } }, savefile: { default_directory: AUS }, download: { default_directory: AUS, prompt_for_download: false } }));
  const ctx = await chromium.launchPersistentContext(PROFIL, { headless: false, executablePath: chromium.executablePath(), args: ['--kiosk-printing', '--no-sandbox', '--disable-gpu'], viewport: { width: 1300, height: 900 } });
  const p = ctx.pages()[0] || await ctx.newPage();
  p.on('pageerror', e => ok('kein Skriptfehler (' + String(e).slice(0, 80) + ')', false));
  await p.goto(U + '/'); await p.waitForSelector('[name=login]'); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1200);
  const api = async (m, pf, d) => await p.evaluate(async ([m, pf, d]) => { const r = await fetch('/api/' + pf, { method: m, headers: { 'Content-Type': 'application/json' }, body: d ? JSON.stringify(d) : undefined }); const j = await r.json().catch(() => ({})); j._s = r.status; return j; }, [m, pf, d]);
  const holen = async (pfad, name) => { const r = await ctx.request.get(U + pfad); const z = path.join(ABL, name); fs.writeFileSync(z, await r.body()); return { status: r.status(), datei: z, typ: r.headers()['content-type'] || '' }; };
  let nr = 0;
  async function drucke(adresse, selbst) {   // Seite öffnen, auf die vom Browser „gedruckte“ PDF-Datei warten
    for (const f of fs.readdirSync(AUS)) fs.unlinkSync(path.join(AUS, f));
    await p.goto(U + adresse); if (selbst) { await p.waitForTimeout(1500); await p.evaluate(() => window.print()); }
    for (let i = 0; i < 120; i++) {
      await warte(250); const fs_ = fs.readdirSync(AUS).filter(f => f.endsWith('.pdf'));
      if (fs_.length) { const q = path.join(AUS, fs_[0]); const g = fs.statSync(q).size; await warte(400); if (g > 500 && fs.statSync(q).size === g) { const z = path.join(ABL, `druck${++nr}.pdf`); fs.copyFileSync(q, z); return z; } }
    }
    return null;
  }
  async function vergleich(name, gedruckt, programm, grenze = 0.35) {
    if (!gedruckt) return ok(name + ': der Browser hat gedruckt', false, 'keine Datei');
    const a = texte(gedruckt), b = texte(programm);
    ok(`${name}: gleiche Seitenzahl wie das PDF des Programms (${b.length})`, a.length === b.length, [a.length, b.length]);
    ok(`${name}: gleicher Text auf jeder Seite`, gleich(a, b), a.map((t, i) => t === b[i] ? '' : `Seite ${i + 1}: ${t.slice(0, 60)} | ${(b[i] || '').slice(0, 60)}`).filter(Boolean));
    const ab = []; for (let i = 1; i <= Math.min(a.length, b.length); i++) ab.push(+abweichung(gedruckt, i, programm, i).toFixed(3));
    ok(`${name}: jedes Blatt deckungsgleich (größte Abweichung ${Math.max(...ab)} %)`, Math.max(...ab) < grenze, ab);
  }

  // ---------- Daten ----------
  const k = await api('POST', 'kunden', { kurzname: 'Druck, Dora', nachname: 'Druck', vorname: 'Dora', strasse: 'Am Hang 3', plz: '88069', ort: 'Tettnang' });
  const kb = await api('POST', 'kunden', { kurzname: 'Brutto, Bernd', nachname: 'Brutto', plz: '88069', ort: 'Tettnang', gruppe: 'Privatkunde', preise: 'brutto' });
  async function auftrag(kid, bez, pos) {
    const a = await api('POST', 'auftraege', { kunde_id: kid, bezeichnung: bez });
    for (const [text, preis, menge] of pos) { const po = await api('POST', `auftraege/${a.id}/positionen`, { text }); await api('PUT', `positionen/${po.id || po.position.id}`, { einzelpreis: preis, preis_manuell: 1, menge: menge || 1 }); }
    return a;
  }
  const a1 = await auftrag(k.id, 'Regal', [['Regal Eiche\nmassiv, geölt', 480]]);
  const viele = []; for (let i = 1; i <= 24; i++) viele.push([`Schrank ${i}\nKorpus Dekorspan weiß\nFront Eiche furniert\nBeschläge Blum`, 100 + 119 * i]);
  const a2 = await auftrag(k.id, 'Ausbau', viele);
  const a3 = await auftrag(kb.id, 'Brett', [['Brett A', 8.40], ['Brett B', 8.40], ['Brett C', 8.40]]);
  const ein = await api('POST', `auftraege/${a1.id}/belege`, { art: 'angebot' });
  const mehr = await api('POST', `auftraege/${a2.id}/belege`, { art: 'angebot' });
  const bru = await api('POST', `auftraege/${a3.id}/belege`, { art: 'angebot' });
  const re = await api('POST', `auftraege/${a1.id}/belege`, { art: 'rechnung' }); const fest = await api('POST', `belege/${re.id}/festschreiben`, {});
  ok('Vorbereitung: Belege angelegt, Rechnung festgeschrieben', ein.id && mehr.id && bru.id && fest._s === 200, [ein._s, mehr._s, bru._s, fest._s, fest.fehler]);

  // ---------- 1. „Drucken“ = das PDF des Programms ----------
  const pEin = await holen(`/druck/${ein.id}.pdf`, 'ein.pdf'), pMehr = await holen(`/druck/${mehr.id}.pdf`, 'mehr.pdf');
  ok('PDF des Programms: einseitiges Angebot und mehrseitiges Angebot erzeugt', pEin.status === 200 && pMehr.status === 200 && seiten(pMehr.datei) >= 4, [pEin.status, pMehr.status]);
  await vergleich('Drucken, einseitiges Angebot', await drucke(`/druck/${ein.id}?drucken=1`), pEin.datei);
  const dMehr = await drucke(`/druck/${mehr.id}?drucken=1`);
  await vergleich('Drucken, mehrseitiges Angebot', dMehr, pMehr.datei);
  const tm = dMehr ? texte(dMehr) : [];
  // die Seitenzahlen („Seite 1 von 5“) sind im PDF gezeichnet, kein Text: Sie stecken im Bildvergleich oben; hier zusätzlich: unten rechts steht etwas
  const ecke = (pdf, n) => { const b = bild(pdf, n); let dunkel = 0; for (let y = Math.round(b.h * 0.965); y < Math.round(b.h * 0.99); y++) for (let x = Math.round(b.w * 0.75); x < Math.round(b.w * 0.93); x++) if (b.d[y * b.w + x] < 200) dunkel++; return dunkel; };
  ok('der Ausdruck trägt den Übertrag und unten rechts die Seitenzahl des PDFs', tm.length > 1 && /Übertrag/.test(tm[0]) && /Übertrag/.test(tm[1]) && ecke(dMehr, 1) > 0 && ecke(dMehr, 2) > 0, [tm.length, dMehr && ecke(dMehr, 1), dMehr && ecke(dMehr, 2)]);
  ok('die Druckansicht zeigt eine Leiste mit dem Namen des Belegs und der Schaltfläche „Drucken“', await p.locator('.leiste #dr').isEnabled() && /Angebot/.test(await p.locator('.leiste b').innerText()), await p.locator('.leiste').innerText().catch(e => String(e)));

  // ---------- 2. festgeschriebene Rechnung: gezeigt und gedruckt wird die abgelegte Datei ----------
  const jahr = String(new Date().getFullYear());
  const reNr = (await api('GET', `belege/${re.id}`)).nummer;
  const archivDatei = fs.readdirSync(path.join(DATEN, 'belege', jahr)).filter(f => reNr && f.includes(reNr) && f.endsWith('.pdf'))[0] || 'fehlt.pdf';
  const archiv = fs.existsSync(path.join(DATEN, 'belege', jahr, archivDatei)) ? fs.readFileSync(path.join(DATEN, 'belege', jahr, archivDatei)) : Buffer.alloc(0);
  const pFest = await holen(`/druck/${re.id}.pdf`, 'fest.pdf'), pFest2 = await holen(`/druck/${re.id}.pdf`, 'fest2.pdf');
  ok('„PDF“ einer festgeschriebenen Rechnung liefert Byte für Byte die Datei aus dem Archiv', archiv.length > 500 && archiv.equals(fs.readFileSync(pFest.datei)) && archiv.equals(fs.readFileSync(pFest2.datei)), [archiv.length, fs.statSync(pFest.datei).size]);
  ok('das Archiv-PDF bleibt dabei unverändert', archiv.length > 500 && archiv.equals(fs.readFileSync(path.join(DATEN, 'belege', jahr, archivDatei))));
  await vergleich('Drucken, festgeschriebene Rechnung', await drucke(`/druck/${re.id}?drucken=1`), pFest.datei);

  // ---------- 3. Mahnung ----------
  const ops = await api('GET', 'offeneposten'); const op = (ops.liste || ops.posten || ops).find ? (ops.liste || ops.posten || ops).find(o => o.beleg_id === re.id) : null;
  const mahn = op ? await api('POST', `offeneposten/${op.id}/mahnung`, { stufe: 0 }) : { _s: 0 };
  ok('Vorbereitung: Mahnung erstellt', mahn._s === 200 && mahn.id, [mahn._s, mahn.fehler, Object.keys(ops).slice(0, 6)]);
  if (mahn.id) { const pM = await holen(`/api/mahnungen/${mahn.id}/pdf`, 'mahnung.pdf'); await vergleich('Drucken, Mahnung', await drucke(`/druck/mahnung/${mahn.id}?drucken=1`), pM.datei); }

  // ---------- 4. Ansichten, die der Browser selbst druckt (Brief, Listen): Bildschirmregeln dürfen im Druck nicht gelten ----------
  const br = await api('POST', 'briefe', { kunde_id: k.id, betreff: 'Terminbestätigung', text: 'Sehr geehrte Frau Druck,\n\nwir kommen am Montag.' });
  if (br.id) {
    const bp = await api('POST', `briefe/${br.id}/pdf`, {}); const quelle = bp.archiv || (bp.pdf && bp.pdf.archiv);
    ok('Vorbereitung: Brief angelegt, PDF erzeugt', !!quelle && fs.existsSync(quelle), [br._s, bp._s, Object.keys(bp)]);
    if (quelle && fs.existsSync(quelle)) await vergleich('Brief aus der Ansicht gedruckt', await drucke(`/druck/brief/${br.id}`, true), quelle, 0.6);
  } else ok('Vorbereitung: Brief angelegt', false, [br._s, br.fehler]);
  const pL = await holen('/liste/lager.pdf', 'lager.pdf');
  if (pL.status === 200) await vergleich('Lagerliste aus der Ansicht gedruckt', await drucke('/liste/lager', true), pL.datei, 0.6);
  else ok('Vorbereitung: Lagerliste als PDF', false, pL.status);

  // ---------- 5. kurze Positionen bleiben zusammen, Rundungszeile bei Bruttoanzeige ----------
  const geteilt = texte(pMehr.datei).slice(1).map((t, i) => { const z = t.split('\n'); const kopf = z.findIndex(x => /Pos\.\s+Menge/.test(x)); return kopf >= 0 && z[kopf + 1] && !/^\s*\d\d\s/.test(z[kopf + 1]) ? `Seite ${i + 2}: ${z[kopf + 1].trim()}` : ''; }).filter(Boolean);
  ok('mehrseitiges Angebot (Platz optimieren): keine vierzeilige Position wird am Seitenende geteilt', geteilt.length === 0, geteilt);
  const pBru = await holen(`/druck/${bru.id}.pdf`, 'brutto.pdf'), tb = texte(pBru.datei).join('\n');
  ok('Bruttoanzeige: 3 × 10,00 € ergeben 29,99 € – die Differenz steht als eigene Zeile da', /Summe der Einzelbeträge 30,00 €/.test(tb) && /Rundungsdifferenz[^\n]*-0,01 €/.test(tb) && /Gesamtbetrag 29,99 €/.test(tb), tb.slice(tb.indexOf('Brett C'), tb.indexOf('Brett C') + 400));
  ok('ohne Differenz erscheint keine Rundungszeile', !/Rundungsdifferenz/.test(texte(pEin.datei).join('\n')) && !/Rundungsdifferenz/.test(texte(pMehr.datei).join('\n')));

  // ---------- 6. Lässt sich kein PDF erzeugen, druckt „Drucken“ ersatzweise die Bildschirmfassung – auf dem Briefbogen wie das PDF ----------
  // (ohne „unten bündig“: Diesen Abstand misst das Programm mit dem PDF-Browser – ohne ihn steht der Schluss direkt unter den Summen)
  await api('PUT', `belege/${ein.id}`, { druck: { unten_buendig: false } });
  const pEin2 = await holen(`/druck/${ein.id}.pdf`, 'ein2.pdf');
  fs.renameSync(FAKE, FAKE + '.weg');
  try {
    const ers = await drucke(`/druck/${ein.id}?drucken=1`);
    ok('ohne PDF-Erzeugung: „Drucken“ weicht auf die Bildschirmfassung aus und druckt', !!ers && /drucken=html/.test(p.url()), p.url());
    if (ers) {
      const a = texte(ers), b = texte(pEin2.datei);
      ok('Ersatzdruck: gleiche Seitenzahl wie das PDF, gleicher Text auf dem Belegblatt (die AGB-Seite ist hier ein Bild)', a.length === b.length && a[0] === b[0], [a.length, b.length, a[0].slice(0, 80), b[0].slice(0, 80)]);
      const ab = +abweichung(ers, 1, pEin2.datei, 1).toFixed(3);
      ok(`Ersatzdruck: Belegblatt deckungsgleich mit dem PDF (Abweichung ${ab} %) – der Inhalt sitzt richtig auf dem Briefbogen`, ab < 0.35, ab);
      // (die AGB-Seite wird hier nicht verglichen: Im PDF hängt die hinterlegte AGB-Datei an, im Ersatzdruck deren Seitenbild)
    }
  } finally { fs.renameSync(FAKE + '.weg', FAKE); }

  console.log('FEHLER: ' + JSON.stringify(fehler));
  await ctx.close(); process.exit(fehler.length ? 1 : 0);
})().catch(e => { try { if (fs.existsSync(FAKE + '.weg')) fs.renameSync(FAKE + '.weg', FAKE); } catch (x) { /* nichts */ } console.log('FEHLER: Abbruch ' + (e && e.stack || e)); process.exit(1); });
