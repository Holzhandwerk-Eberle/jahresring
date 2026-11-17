const { chromium } = require('playwright'); const fs = require('fs');
const U = 'http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1400, height: 950 } }); const p = await ctx.newPage(); p.on('dialog', d => d.dismiss());
  await p.addInitScript(() => { window.print = () => { window.__gedruckt = (window.__gedruckt || 0) + 1; }; });
  await p.goto(U + '/'); await p.waitForTimeout(800); await p.fill('[name=login]', 'jonas'); await p.fill('[name=passwort]', 'geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1200);
  for (const [id, name] of [[19, 'titel'], [18, 'schluss']]) {
    await p.goto(U + `/druck/${id}?drucken=1`); await p.waitForTimeout(2500);
    const info = await p.evaluate(() => ({ gedruckt: window.__gedruckt || 0, ue: [...document.querySelectorAll('.ue')].map(e => ({ t: e.innerText.replace(/\s+/g, ' ').slice(0, 30), top: Math.round(e.getBoundingClientRect().top + scrollY), pos: getComputedStyle(e).position })).slice(0, 8), hoehe: document.documentElement.scrollHeight, url: location.href.slice(-40) }));
    console.log(name, JSON.stringify(info).slice(0, 700));
    await p.emulateMedia({ media: 'print' });
    await p.pdf({ path: `/tmp/claude-0/t/audit4/ue/druckweg_${name}.pdf`, preferCSSPageSize: true, printBackground: true });
    await p.emulateMedia({ media: 'screen' }); await p.screenshot({ path: `/tmp/claude-0/t/audit4/ue/bildschirm_${name}.png`, fullPage: false });
  }
  await b.close(); })();
