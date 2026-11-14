const { chromium } = require('playwright'); const U='http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({viewport:{width:1300,height:900}})).newPage();
  p.on('pageerror', e => console.log('ERR', p.url(), e.stack.split('\n').slice(0,5).join(' | ')));
  await p.goto(U+'/'); await p.waitForTimeout(600); await p.fill('[name=login]', 'werk'); await p.fill('[name=passwort]','geheim456'); await p.click('button[type=submit]'); await p.waitForTimeout(1500);
  for (const r of ['#/start', '#/auftraege']) { await p.evaluate(h => { location.hash = h; }, r); await p.waitForTimeout(800); }
  console.log(await p.evaluate(() => document.body.innerText.slice(0,300)));console.log(await p.evaluate(() => document.querySelector('#leiste') ? document.querySelector('#leiste').outerHTML.slice(0, 600) : 'kein leiste'));
  await b.close(); })();
