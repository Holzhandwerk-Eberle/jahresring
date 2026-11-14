const { chromium } = require('playwright'); const fs = require('fs');
const U='http://127.0.0.1:8799', S='/tmp/claude-0/t/v25/';
(async () => { const b = await chromium.launch(); const ctx = await b.newContext({viewport:{width:1300,height:900}, locale:'de-DE'}); const p = await ctx.newPage();
  const f=[]; p.on('pageerror',e=>f.push(e.message));
  await p.goto(U+'/'); await p.waitForTimeout(600);
  await p.fill('[name=name]','Jonas'); await p.fill('[name=login]','jonas'); await p.fill('[name=passwort]','geheim123'); await p.fill('[name=passwort2]','geheim123'); await p.click('button[type=submit]'); await p.waitForTimeout(1500);
  const api = (m, pfad, body) => p.evaluate(async ([m,pfad,body]) => { const r = await fetch('/api/'+pfad,{method:m,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined}); const j = await r.json().catch(()=>({})); if(!r.ok) return {FEHLER:j.fehler, code:r.status}; return j; }, [m,pfad,body]);
  await api('PUT','einstellungen',{firma:'Holzhandwerk Eberle', steuernummer:'12/345/67890', firma_anschrift:'Teststr. 1\n88069 Tettnang'});
  const k = await api('POST','kunden',{kurzname:'Test, Kunde'}); const a = await api('POST','auftraege',{kunde_id:k.id,bezeichnung:'Tisch'});
  const pos = await api('POST','auftraege/'+a.id+'/positionen',{text:'Tisch'}); await api('PUT','positionen/'+(pos.id||pos.position.id),{einzelpreis:1000, preis_manuell:1});
  const r1 = await api('POST','auftraege/'+a.id+'/belege',{art:'rechnung'}); const fr = await api('POST','belege/'+r1.id+'/festschreiben'); console.log('fest', fr.beleg ? fr.beleg.nummer : JSON.stringify(fr).slice(0,200));
  const st = await api('POST','belege/'+r1.id+'/storno'); console.log('storno', st.beleg ? st.beleg.nummer : JSON.stringify(st));
  const ang = await api('POST','auftraege/'+a.id+'/belege',{art:'angebot'}); await api('DELETE','belege/'+ang.id);
  await api('PUT','nummernkreise',{art:'rechnung', naechste: 50});
  const sich = await api('POST','service/sicherung'); console.log('sicherung', sich.name);
  // Testdaten löschen vor Echtbetrieb
  const td = await api('POST','service/testdaten',{gruppen:['auftraege'], bestaetigung:'LÖSCHEN'}); console.log('testdaten', td.FEHLER || 'ok');
  // Echtbetrieb
  console.log('echtbetrieb falsch', (await api('POST','service/echtbetrieb',{bestaetigung:'x'})).FEHLER);
  console.log('echtbetrieb', JSON.stringify(await api('POST','service/echtbetrieb',{bestaetigung:'echtbetrieb'})));
  console.log('testdaten danach', (await api('POST','service/testdaten',{gruppen:['auftraege'], bestaetigung:'LÖSCHEN'})).FEHLER);
  // Rücksicherung auf Stand vor Echtbetrieb ohne Grund / mit Grund
  console.log('rueck ohne grund', (await api('POST','service/ruecksichern',{name:sich.name})).FEHLER);
  const rs = await api('POST','service/ruecksichern',{name:sich.name, grund:'Test der Rücksicherung im Echtbetrieb'}); console.log('rueck', rs.FEHLER || rs.vorher);
  console.log('testdaten nach rück', (await api('POST','service/testdaten',{gruppen:['auftraege'], bestaetigung:'LÖSCHEN'})).FEHLER);
  const pr = await api('GET','service/protokoll'); console.log('pruefung', JSON.stringify(pr.pruefung.ok), pr.pruefung.anzahl, pr.pruefung.fehler);
  console.log(pr.eintraege.map(e=>`${e.nr} ${e.art}: ${e.text}`).reverse().join('\n'));
  await p.goto(U+'/#/einstellungen/service/protokoll'); await p.waitForTimeout(1200); await p.screenshot({path:S+'pr1.png'});
  await p.goto(U+'/#/einstellungen/service/testdaten'); await p.waitForTimeout(900); await p.screenshot({path:S+'pr2.png', clip:{x:0,y:0,width:1300,height:400}});
  console.log('fehler', f); await b.close(); })();
