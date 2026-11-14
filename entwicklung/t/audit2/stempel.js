const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({viewport:{width:420,height:800}})).newPage(); const f=[]; p.on('pageerror',e=>f.push(e.message));
  await p.goto('http://127.0.0.1:8799/stempel'); await p.waitForTimeout(600); await p.fill('input[type=text], input:not([type])','mita').catch(()=>{}); const ins = await p.$$('input'); await ins[0].fill('mita'); await ins[1].fill('geheim456'); await p.click('button'); await p.waitForTimeout(1500);
  console.log('Stempeluhr:', (await p.evaluate(() => document.body.innerText)).replace(/\s+/g,' ').slice(0,160), '| fehler', f); await b.close(); })();
