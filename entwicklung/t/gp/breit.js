const { chromium } = require('playwright'); const U='http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const c = await b.newContext({viewport:{width:1400,height:900}}); await c.request.post(U+'/api/anmeldung/anmelden', {data:{login:'jonas', passwort:'geheim123'}}); const p = await c.newPage();
  for (const r of ['#/arbeitsschutz', '#/arbeitsschutz/thema/1']) {
    await p.goto(U+'/'+r); await p.waitForTimeout(1200);
    const x = await p.evaluate(() => { const W = document.documentElement.clientWidth; const out = []; document.querySelectorAll('body *').forEach(e => { const rc = e.getBoundingClientRect(); if (rc.right > W + 2 && rc.width > 0) out.push(e.tagName + '.' + e.className + ' ' + Math.round(rc.left) + '-' + Math.round(rc.right) + ' ' + (e.innerText||'').slice(0,40).replace(/\n/g,' ')); }); return [document.documentElement.scrollWidth, out.slice(0, 8)]; });
    console.log(r, JSON.stringify(x, null, 1));
  }
  await b.close(); })();
