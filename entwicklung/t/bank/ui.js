const { chromium } = require('playwright'); const U='http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const c = await b.newContext({viewport:{width:1400,height:900}}); await c.request.post(U+'/api/anmeldung/anmelden', {data:{login:'jonas', passwort:'geheim123'}}); const p = await c.newPage(); const f = [];
  p.on('pageerror', e => f.push(e.message)); p.on('console', m => { if (m.type()==='error') f.push(m.text()); });
  for (const [r, n] of [['#/op/bank', 'bank1'], ['#/op/liquiditaet', 'liq1']]) { await p.goto(U+'/'+r); await p.waitForTimeout(1200); await p.screenshot({path: `/tmp/claude-0/t/bank/${n}.png`, fullPage: true}); }
  await p.goto(U+'/#/op/bank'); await p.waitForTimeout(1000);
  const btn = await p.$('[data-zu]'); if (btn) { await btn.click(); await p.waitForTimeout(900); await p.screenshot({path: '/tmp/claude-0/t/bank/dlg.png'}); 
    const cb = await p.$$('.modal input[name=bzw]'); console.log('kandidaten', cb.length); if (cb.length) { await cb[0].check(); await p.waitForTimeout(200); console.log(await p.innerText('#bzSumme').catch(()=>'')); }
    await p.click('.modal [data-x="1"]'); await p.waitForTimeout(1000); }
  console.log((await p.innerText('#inhalt')).slice(0, 600).replace(/\n+/g, ' | '));
  await p.goto(U+'/#/op/liquiditaet'); await p.waitForTimeout(1000); await p.click('.lq-w'); await p.waitForTimeout(300);
  await p.click('#lqNeu'); await p.waitForTimeout(1000);
  console.log('regel', await p.$$eval('#lqRegel tr[data-i]', t => t.length));
  console.log('fehler', f); await b.close(); })();
