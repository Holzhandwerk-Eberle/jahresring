const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1250, height: 900 } })).newPage();
  await p.goto('http://127.0.0.1:8799/hilfe/handbuch.html'); await p.waitForTimeout(800);
  const h = await p.$('#fremdbausteine'); await h.scrollIntoViewIfNeeded(); await p.waitForTimeout(300);
  await p.screenshot({ path: '/tmp/claude-0/t/audit4/shots149/h_fremd.png' });
  console.log(await p.evaluate(() => ({ y: scrollY, kopf: getComputedStyle(document.querySelector('nav, aside, .inhalt, body > *')).position, anker: [...document.querySelectorAll('nav a, aside a')].filter(a => /Fremdbausteine/.test(a.textContent)).length })));
  await b.close(); })();
