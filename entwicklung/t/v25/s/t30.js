const { chromium } = require('playwright');
const U='http://127.0.0.1:8799';
(async () => { const b = await chromium.launch(); const p = await (await b.newContext()).newPage();
  for (const [d, n] of [['datenschutz','Datenschutz-Dokumentation_Jahresring'],['installation','Installationsanleitung_Jahresring'],['verfahrensdokumentation','Verfahrensdokumentation_GoBD_Jahresring'],['kalkulation','Kalkulationslogik_Jahresring']]) {
    await p.goto(U+'/hilfe/'+d+'.html'); await p.waitForTimeout(800); await p.emulateMedia({media:'print'});
    await p.pdf({path:'/home/claude/'+n+'.pdf', format:'A4', preferCSSPageSize:true, printBackground:false}); }
  await b.close(); })();
