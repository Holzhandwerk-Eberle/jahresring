const { chromium } = require('playwright');
const U='http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const ctx = await b.newContext(); const p = await ctx.newPage(); const dlg=[]; p.on('dialog', d=>{dlg.push(d.message()); d.dismiss();});
  await p.goto(U+'/'); await p.waitForTimeout(600);
  await p.fill('[name=login]','jonas'); await p.fill('[name=passwort]','geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1500);
  for (const h of ['#/start','#/kunden','#/kunde/1','#/auftraege','#/auftrag/1','#/beleg/1','#/op','#/kalender','#/leitstand','#/protokoll','#/einstellungen/protokoll']) { await p.goto(U+'/'+h); await p.waitForTimeout(900); const x = await p.evaluate(()=>window.XSS); if (x) console.log('XSS in', h, x); }
  for (const u of ['/druck/1','/papier/1/laufzettel','/papier/1/materialliste']) { const r = await p.goto(U+u); await p.waitForTimeout(700); console.log(u, r.status(), 'XSS', await p.evaluate(()=>window.XSS), 'script-tags', await p.evaluate(()=>[...document.querySelectorAll('script')].filter(s=>/XSS/.test(s.textContent)).length), 'on*', await p.evaluate(()=>[...document.querySelectorAll('*')].filter(e=>[...e.attributes].some(a=>/^on/i.test(a.name)||/^javascript:/i.test(a.value))).map(e=>e.outerHTML.slice(0,80)))); }
  console.log('dialoge', dlg); await b.close(); })();
