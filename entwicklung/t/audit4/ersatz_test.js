const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1200, height: 900 } })).newPage();
  await p.goto('http://127.0.0.1:8799/'); await p.waitForTimeout(600); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1200);
  await p.addInitScript(() => { window.print = () => { window.__gedruckt = (window.__gedruckt || 0) + 1; }; });
  await p.goto('http://127.0.0.1:8799/druck/4?drucken=html'); await p.waitForTimeout(800);
  console.log('Hinweis:', await p.$eval('.ersatzhinweis', e => e.textContent), '| gedruckt:', await p.evaluate(() => window.__gedruckt));
  await p.screenshot({ path: '/tmp/claude-0/t/audit4/shots149/ersatz.png' });
  await p.emulateMedia({ media: 'print' }); console.log('im Druck sichtbar:', await p.$eval('.ersatzhinweis', e => getComputedStyle(e).display));
  await b.close(); })();
