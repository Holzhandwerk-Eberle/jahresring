// =====================================================================
//  Korrespondenz (E-Mails, Anrufe, Briefe), Briefe, Rundmail, Geburtstage, Statistik
// =====================================================================
const KORR_SYMBOL = {mail_ein: "📥", mail_aus: "📤", anruf_aus: "📞", anruf_ein: "📲", notiz: "🗒", brief: "✉"};
const korrFilter = {art: ""};

// Liste für Kunde ({kunde}), Lieferant ({lieferant}) oder Auftrag ({auftrag, kunde})
async function korrespondenzListe(ziel, bezug) {
  const q = new URLSearchParams({...(bezug.auftrag ? {auftrag: bezug.auftrag.id} : bezug.kunde ? {kunde: bezug.kunde.id} : {lieferant: bezug.lieferant.id}), art: korrFilter.art});
  let liste = [], status = {};
  let offen = [];
  try { [liste, status, offen] = await Promise.all([api("korrespondenz?" + q), api("korrespondenz/status").catch(() => ({})),
    bezug.auftrag && bezug.auftrag.kunde_id ? api(`korrespondenz?kunde=${bezug.auftrag.kunde_id}&ohne_auftrag=1&art=${korrFilter.art}`).catch(() => []) : []]); }
  catch (e) { ziel.innerHTML = `<div class="leer">${esc(e.message)}</div>`; return; }
  const kid = bezug.kunde ? bezug.kunde.id : bezug.auftrag ? bezug.auftrag.kunde_id : null;
  const lid = bezug.lieferant ? bezug.lieferant.id : null;
  const filter = [["", "Alle"], ["mail", "E-Mails"], ["anruf", "Anrufe"], ["brief", "Briefe"], ["notiz", "Notizen"]];
  ziel.innerHTML = `<div class="titel"><h2>Korrespondenz</h2>
      <div class="such"><div class="radio">${filter.map(([v, l]) => `<label><input type="radio" name="kf" value="${v}" ${korrFilter.art === v ? "checked" : ""}> ${l}</label>`).join("")}</div></div>
      <div class="rechts" style="flex-wrap:wrap">
        ${kid || lid ? `<button class="btn prim" id="kMail">✉ E-Mail schreiben</button>` : ""}
        <button class="btn" id="kAnruf">📞 Anruf notieren</button>
        <button class="btn" id="kBrief">+ Brief</button>
        <button class="btn" id="kPruef" title="Posteingang und Gesendet jetzt auf neue Mails prüfen">↻ Posteingang</button></div></div>
    ${status.fehler ? `<div class="hinweis" style="color:var(--rot);margin:-4px 0 8px">Posteingang: ${esc(status.fehler)}</div>` : status.letzter ? `<div class="hinweis" style="margin:-4px 0 8px">Posteingang zuletzt geprüft ${datum(status.letzter.slice(0, 10))} ${status.letzter.slice(11, 16)}</div>` : ""}
    ${liste.length ? `<table class="liste korr"><tr><th style="width:150px">Datum</th><th style="width:150px">Art</th><th>Betreff</th>${bezug.auftrag ? "" : "<th>Auftrag</th>"}</tr>
      ${liste.map(x => `<tr class="klick" data-k="${x.id}"><td class="nw">${datum((x.datum || "").slice(0, 10))} ${(x.datum || "").slice(11, 16)}</td>
        <td class="nw">${KORR_SYMBOL[x.art] || ""} ${esc(x.artname)}</td>
        <td><b>${esc(x.betreff || "(ohne Betreff)")}</b><div class="hinweis">${esc(x.art === "mail_ein" ? "von " + (x.von || "") : x.an ? "an " + x.an : "")}${x.nummer ? " · " + esc(x.nummer) : ""}${x.dauer ? " · " + x.dauer + " min" : ""} ${esc(x.kurz || "")}</div></td>
        ${bezug.auftrag ? "" : `<td>${x.auftragsnr ? `<a href="#/auftrag/${x.auftrag_id}">${esc(x.auftragsnr)}</a>` : ""}</td>`}</tr>`).join("")}</table>`
      : `<div class="leer">Noch keine Korrespondenz zu diesem ${bezug.auftrag ? "Auftrag" : "Eintrag"}. E-Mails von und an die hinterlegten Adressen erscheinen automatisch, sobald der Posteingang eingerichtet ist (Einstellungen › E-Mail).</div>`}
    ${offen.length ? `<h3 style="margin:18px 0 4px">Beim Kunden, noch keinem Auftrag zugeordnet</h3>
      <p class="hinweis" style="margin:0 0 6px">Mails ohne Auftragsnummer im Betreff landen beim Kunden. Hat der Kunde nur einen offenen Auftrag, ordnet das Programm sie automatisch zu.</p>
      <table class="liste korr">${offen.map(x => `<tr class="klick" data-k2="${x.id}"><td class="nw" style="width:150px">${datum((x.datum || "").slice(0, 10))} ${(x.datum || "").slice(11, 16)}</td>
        <td class="nw" style="width:150px">${KORR_SYMBOL[x.art] || ""} ${esc(x.artname)}</td><td><b>${esc(x.betreff || "(ohne Betreff)")}</b><div class="hinweis">${esc(x.kurz || "")}</div></td>
        <td class="nw"><button class="btn" data-zuord="${x.id}">→ diesem Auftrag zuordnen</button></td></tr>`).join("")}</table>` : ""}`;
  $$("[data-zuord]", ziel).forEach(b => b.onclick = async ev => { ev.stopPropagation();
    try { await api("korrespondenz/" + b.dataset.zuord, {method: "PUT", body: {auftrag_id: bezug.auftrag.id}}); toast("Dem Auftrag zugeordnet"); korrespondenzListe(ziel, bezug); } catch (e) { toast(e.message, true); } });
  $$("[data-k2]", ziel).forEach(tr => tr.onclick = ev => { if (!ev.target.closest("button")) korrespondenzZeigen(+tr.dataset.k2, () => korrespondenzListe(ziel, bezug)); });
  const neu = () => korrespondenzListe(ziel, bezug);
  $$("[name=kf]", ziel).forEach(r => r.onchange = () => { korrFilter.art = r.value; neu(); });
  $$("[data-k]", ziel).forEach(tr => tr.onclick = ev => {
    if (ev.target.closest("a")) return;
    const x = liste.find(y => String(y.id) === tr.dataset.k);
    if (x.art === "brief") location.hash = "#/brief/" + x.brief_id; else korrespondenzZeigen(x.id, neu);
  });
  if ($("#kMail")) $("#kMail").onclick = () => kid ? mailDialog("kunden/" + kid, "E-Mail an den Kunden", () => neu(), bezug.auftrag ? `?auftrag=${bezug.auftrag.id}` : "")
    : mailDialog("lieferanten/" + lid, "E-Mail an den Lieferanten", () => neu());
  $("#kAnruf").onclick = () => anrufNotieren({kunde_id: kid, lieferant_id: lid, auftrag_id: bezug.auftrag ? bezug.auftrag.id : null}, "", neu);
  $("#kBrief").onclick = async () => {
    try { const b = await api("briefe", {method: "POST", body: {kunde_id: kid, lieferant_id: lid, auftrag_id: bezug.auftrag ? bezug.auftrag.id : null}}); location.hash = "#/brief/" + b.id; }
    catch (e) { toast(e.message, true); }
  };
  $("#kPruef").onclick = async () => {
    const b = $("#kPruef"); b.disabled = true; b.textContent = "prüft …";
    try { const r = await api("korrespondenz/pruefen", {method: "POST"}); toast(r.neu ? `${r.neu} neue Mail${r.neu > 1 ? "s" : ""} zugeordnet` : "Keine neuen Mails"); neu(); }
    catch (e) { toast(e.message, true); b.disabled = false; b.textContent = "↻ Posteingang"; }
  };
}

async function korrespondenzZeigen(id, danach) {
  const x = await api("korrespondenz/" + id);
  const manuell = ["anruf_aus", "anruf_ein", "notiz"].includes(x.art);
  let auftraege = [];
  if (x.kunde_id) try { auftraege = await api("auftraege?kunde=" + x.kunde_id); } catch (e) {}
  const ok = await modal(`${KORR_SYMBOL[x.art] || ""} ${x.artname}`, `
    <div class="hinweis">${datum((x.datum || "").slice(0, 10))} ${(x.datum || "").slice(11, 16)}${x.von ? " · von " + esc(x.von) : ""}${x.an ? " · an " + esc(x.an) : ""}${x.benutzer ? " · " + esc(x.benutzer) : ""}</div>
    ${manuell ? `<h3 style="margin:8px 0">${esc(x.betreff || "")}</h3>${x.nummer || x.dauer ? `<div class="hinweis">${esc(x.nummer || "")}${x.dauer ? " · " + x.dauer + " min" : ""}</div>` : ""}
      <div style="white-space:pre-wrap;background:var(--zeile);padding:10px;border-radius:6px;font-size:14px;margin-top:6px">${esc(x.text || "–")}</div>
      <p class="hinweis">Gespeicherte Notizen sind nicht mehr änderbar. Ergänzungen bitte als neue Notiz erfassen.</p>`
      : `<h3 style="margin:8px 0">${esc(x.betreff || "(ohne Betreff)")}</h3><div style="white-space:pre-wrap;max-height:50vh;overflow:auto;background:var(--zeile);padding:10px;border-radius:6px;font-size:14px">${esc(x.text || "")}</div>
      ${x.anhaenge.length ? `<div class="hinweis" style="margin-top:6px">Anhänge: ${x.anhaenge.map(esc).join(", ")}</div>` : ""}
      ${x.datei ? `<p><a class="btn" href="/api/korrespondenz/${x.id}/eml">Original-Mail öffnen (.eml)</a></p>` : ""}`}
    ${x.kunde_id ? `<div class="zeile"><label>Auftrag</label><div><select name="auftrag_id"><option value="">– keinem Auftrag zugeordnet –</option>${auftraege.map(a => `<option value="${a.id}" ${a.id === x.auftrag_id ? "selected" : ""}>${esc(a.nummer)} ${esc(a.bezeichnung)}</option>`).join("")}</select></div></div>` : ""}`,
    x.kunde_id ? "Zuordnung speichern" : "Schließen", hg => { $(".modal", hg).style.width = "min(760px,96vw)"; });
  if (!ok || !x.kunde_id) return;
  if (String(ok.auftrag_id || "") === String(x.auftrag_id || "")) return;
  try { await api("korrespondenz/" + id, {method: "PUT", body: {auftrag_id: ok.auftrag_id}}); toast("Auftrag zugeordnet"); danach && danach(); } catch (e) { toast(e.message, true); }
}

// Anruf: tel:-Link öffnen und danach Notiz erfassen
async function anrufNotieren(bezug, nummer = "", danach) {
  const d = await modal("📞 Anruf notieren", `
    <div class="zeile"><label>Richtung</label><div class="radio"><label><input type="radio" name="art" value="anruf_aus" checked> ausgehend</label><label><input type="radio" name="art" value="anruf_ein"> eingehend</label></div></div>
    <div class="zeile"><label>Nummer</label><div><input name="nummer" value="${esc(nummer)}"></div></div>
    <div class="zeile"><label>Betreff</label><div><input name="betreff" placeholder="z. B. Termin Aufmaß abgestimmt"></div></div>
    <div class="zeile"><label>Notiz</label><div><textarea name="text" rows="5" style="width:100%"></textarea></div></div>
    <div class="zeile"><label>Dauer</label><div><input name="dauer" type="number" min="0" style="width:90px"> min</div></div>
    <p class="hinweis">Nach dem Speichern ist die Notiz nicht mehr änderbar.</p>`, "Speichern", hg => setTimeout(() => $("[name=betreff]", hg).focus(), 50));
  if (!d) return;
  try { await api("korrespondenz", {method: "POST", body: {...bezug, ...d, dauer: +d.dauer || 0}}); toast("Anruf notiert"); danach && danach(); }
  catch (e) { toast(e.message, true); }
}
// Klick auf eine Telefonnummer mit data-anruf: Anruf starten und Notizfenster öffnen
document.addEventListener("click", ev => {
  const a = ev.target.closest("a[href^='tel:'][data-anruf]");
  if (!a) return;
  const bezug = JSON.parse(a.dataset.anruf || "{}");
  setTimeout(() => anrufNotieren(bezug, a.getAttribute("href").slice(4)), 400);
});

// ---------- Brief ----------
async function ansichtBrief(id) {
  const z = $("#inhalt");
  let b;
  try { b = await api("briefe/" + id); } catch (e) { kopf({}); z.innerHTML = `<div class="leer">${esc(e.message)}</div>`; return; }
  const zurueck = b.auftrag_id ? `#/auftrag/${b.auftrag_id}/briefe` : b.kunde_id ? `#/kunde/${b.kunde_id}/briefe` : b.lieferant_id ? `#/lieferant/${b.lieferant_id}/briefe` : "#/briefe";
  if (b.auftrag_id) await auftragUnterseite(b.auftrag_id, `Brief ${esc(b.nummer)} an ${esc(b.kunde || b.lieferant || "")} · ${esc(b.status || "")}`, "briefe");
  else kopf({krumen: [["Briefe", "#/briefe"]], zurueck, kontext: `Brief <b>${esc(b.nummer)}</b> an ${esc(b.kunde || b.lieferant || "")}${b.auftragsnr ? ` · Auftrag <a href="#/auftrag/${b.auftrag_id}">${esc(b.auftragsnr)}</a>` : ""} · ${esc(b.status || "")}`});
  z.innerHTML = `<div class="titel"><h2>Brief ${esc(b.nummer)}</h2><span class="speicher"></span>
      <div class="rechts" style="flex-wrap:wrap"><button class="btn prim" id="brMail">✉ Per E-Mail senden</button><a class="btn" href="/druck/brief/${id}" target="_blank">Ansehen / Drucken</a>
        <button class="btn" id="brPdf">PDF ablegen</button><button class="ib" id="brDel" title="Brief löschen">${ic("loeschen")}</button></div></div>
    <div class="form" id="brF">
      ${zeile("Datum", `<input type="date" data-f="datum" value="${esc(b.datum || "")}">`)}
      ${zeile("Status", `<input value="${esc(b.status || "Entwurf")}" readonly disabled title="Der Status wird vom Programm gesetzt">`)}
      ${zeile("Empfänger", `<textarea data-f="empfaenger" rows="5">${esc(b.empfaenger || "")}</textarea>`)}
      ${zeile("Ihr Zeichen", `<input data-f="ihr_zeichen" value="${esc(b.ihr_zeichen || "")}" placeholder="Zeichen oder Aktenzeichen des Empfängers">`)}
      ${zeile("Unser Zeichen", `<input data-f="unser_zeichen" value="${esc(b.unser_zeichen || "")}" placeholder="leer = Briefnummer ${esc(b.nummer || "")}">`)}
      ${zeile("Betreff", `<input data-f="betreff" value="${esc(b.betreff || "")}">`, true)}
      ${b.kunde_id ? zeile("Anrede", `<select id="brAnrede"><option value="">– Anrede in die erste Zeile einsetzen –</option>${[...new Set([(b.anrede_kunde || {}).anrede, ...anredeVorlagen(b.anrede_kunde || {}).map(v => anredeEinsetzen(v, b.anrede_kunde || {}))].filter(Boolean))].map(v => `<option>${esc(v)}</option>`).join("")}</select>`) : ""}
      ${zeile("Text", rtEditor(b.text || "", `data-f="text"`), true)}
    </div>
    <p class="hinweis">Der Brief wird auf dem Briefbogen gedruckt (wie Angebote und Rechnungen). „PDF ablegen“ speichert ihn im Archiv (Datenordner › briefe › ${esc((b.datum || "").slice(0, 4))})${b.auftrag_id ? " und im Projektordner" : ""}.</p>`;
  autospeichern($("#brF"), "briefe/" + id);
  const brA = $("#brAnrede");
  if (brA) brA.onchange = () => {
    const v = brA.value; brA.value = ""; if (!v) return;
    const ed = $('#brF [data-f="text"]'); if (!ed) return;
    const erste = ed.querySelector("p, div");
    const istAnrede = el => el && /^\s*(sehr geehrte|liebe|hallo|guten tag|moin|servus|grüß)/i.test(el.textContent || "");
    if (istAnrede(erste)) erste.textContent = v;
    else if (/^\s*(sehr geehrte|liebe|hallo|guten tag)/i.test(ed.textContent || "") && !erste) ed.innerHTML = ed.innerHTML.replace(/^[^<]*?,/, esc(v));
    else ed.insertAdjacentHTML("afterbegin", `<p>${esc(v)}</p>`);
    ed.dispatchEvent(new Event("input", {bubbles: true}));
  };
  $("#brMail").onclick = () => mailDialog("briefe/" + id, "Brief per E-Mail", () => ansichtBrief(id));
  $("#brPdf").onclick = async () => { try { const r = await api(`briefe/${id}/pdf`, {method: "POST"}); toast("PDF abgelegt: " + (r.projekt_rel ? "Projektordner › " + r.projekt_rel + " und " : "") + "Archiv › " + r.archiv.split(/[\\/]/).slice(-3).join(" › ")); ansichtBrief(id); } catch (e) { toast(e.message, true); } };
  $("#brDel").onclick = async () => { if (!await frage(`Brief ${b.nummer} löschen?`)) return; await api("briefe/" + id, {method: "DELETE"}); location.hash = zurueck; };
}

// ---------- Rundmail (Newsletter, alle Empfänger in BCC) ----------
async function rundmailDialog() {
  const v = await api("newsletter");
  if (!v.eingerichtet) return toast("Der E-Mail-Versand ist noch nicht eingerichtet (Einstellungen › E-Mail).", true);
  const gew = new Set(v.empfaenger.map(e => e.id));
  let anh = [];
  const d = await modal("Rundmail an Kunden", `
    <p class="hinweis" style="margin-top:0">Die Mail geht an die eigene Adresse (${esc(v.absender)}), alle Kunden stehen in BCC und sehen sich gegenseitig nicht. Kunden mit „keine Rundmails“ und ohne E-Mail-Adresse sind nicht in der Liste. Werbliche Mails nur an Kunden, die eingewilligt haben oder bei denen die Ausnahme für Bestandskunden greift (ähnliche Leistungen, Hinweis auf Widerspruch) – im Zweifel im Text auf die Abmeldemöglichkeit hinweisen.</p>
    <div class="zeile"><label>Gruppen</label><div class="radio">${["", ...v.gruppen].map(g => `<label><input type="checkbox" data-gr="${esc(g)}" checked> ${esc(g || "ohne Gruppe")}</label>`).join("")}</div></div>
    <div class="zeile"><label>Empfänger</label><div class="spalte"><div class="kat-liste" style="max-height:180px" id="rmListe">${v.empfaenger.map(e => `<label data-gruppe="${esc(e.gruppe || "")}"><input type="checkbox" data-id="${e.id}" checked> ${esc(e.kurzname)} <small>${esc(e.email1)}</small></label>`).join("")}</div><span class="hinweis" id="rmAnz"></span></div></div>
    <div class="zeile"><label>Betreff</label><div><input name="betreff" placeholder="z. B. Frohe Weihnachten aus der Werkstatt"></div></div>
    <div class="zeile"><label>Text</label><div><textarea name="text" rows="9" style="width:100%">Liebe Kundinnen und Kunden,\n\n\n\nHerzliche Grüße</textarea></div></div>
    <div class="zeile"><label>Anhang</label><div><input type="file" id="rmAnh" multiple><span class="hinweis">z. B. Weihnachtskarte als PDF oder Bild (zusammen unter 10 MB)</span></div></div>
    <p class="hinweis">Die Signatur wird automatisch angehängt.</p>`, "Senden", hg => {
      $(".modal", hg).style.width = "min(780px,96vw)"; $(".modal", hg).style.maxHeight = "94vh"; $(".modal", hg).style.overflow = "auto";
      const anz = () => { $("#rmAnz", hg).textContent = `${gew.size} Empfänger`; };
      $$("[data-id]", hg).forEach(c => c.onchange = () => { c.checked ? gew.add(+c.dataset.id) : gew.delete(+c.dataset.id); anz(); });
      $$("[data-gr]", hg).forEach(c => c.onchange = () => { $$(`#rmListe label[data-gruppe="${CSS.escape(c.dataset.gr)}"] input`, hg).forEach(x => { x.checked = c.checked; c.checked ? gew.add(+x.dataset.id) : gew.delete(+x.dataset.id); }); anz(); });
      $("#rmAnh", hg).onchange = async e => { anh = []; for (const f of e.target.files) anh.push({name: f.name, daten: await new Promise(ok => { const r = new FileReader(); r.onload = () => ok(r.result.split(",")[1]); r.readAsDataURL(f); })}); };
      $("[name=text]", hg).addEventListener("keydown", e => e.stopPropagation());
      anz();
    });
  if (!d) return;
  if (!await frage(`Rundmail „${d.betreff}“ jetzt an ${gew.size} Empfänger senden?`, {ok: "Senden"})) return;
  toast("Rundmail wird gesendet …");
  try { const r = await api("newsletter", {method: "POST", body: {ids: [...gew], betreff: d.betreff, text: d.text, anhaenge: anh}}); toast(`Rundmail an ${r.gesendet} Empfänger gesendet`); }
  catch (e) { toast(e.message, true); }
}

// ---------- Statistik ----------
function statKachel(t, w, hin = "") { return `<div class="kachel"><h4>${t}</h4><div class="gross">${w}</div>${hin ? `<div class="hinweis">${hin}</div>` : ""}</div>`; }
function umsatzBalken(titel, liste, schl) {
  const max = Math.max(1, ...liste.map(x => x.umsatz));
  return `<div class="kachel"><h4>${titel}</h4>${liste.length ? liste.map(x => `<div class="balken"><span>${esc(x[schl] || "–")}</span><i style="width:${x.umsatz / max * 100}%"></i><b class="nw">${n2(x.umsatz, 0)} €</b></div>`).join("") : `<span class="hinweis">noch keine Rechnungen</span>`}</div>`;
}
async function kundeStatistik(k) {
  const s = await api(`kunden/${k.id}/statistik`);
  const quote = s.angebote ? Math.round(s.beauftragt / s.angebote * 100) + " %" : "–";
  $("#inhalt").innerHTML = `<div class="titel"><h2>Statistik</h2></div><div class="raster">
    ${statKachel("Umsatz gesamt", eur(s.umsatz_gesamt), s.rang ? `Rang ${s.rang} unter allen Kunden` : "")}
    ${statKachel("Aufträge", k.anz_auftraege, s.erster ? `erster ${datum(s.erster)} · letzter ${datum(s.letzter)}` : "noch keine")}
    ${statKachel("Angebotsquote", quote, `${s.beauftragt} von ${s.angebote} Angeboten beauftragt${s.abgesagt ? ` · ${s.abgesagt} abgesagt` : ""}`)}
    ${statKachel("Ø Auftragswert", s.durchschnitt_auftrag ? eur(s.durchschnitt_auftrag) : "–", "berechnet je abgerechnetem Auftrag")}
    ${statKachel("Zahlungsdauer", s.zahlungsdauer != null ? n2(s.zahlungsdauer, 0) + " Tage" : "–", "Ø vom Rechnungsdatum bis zum Zahlungseingang")}
    ${statKachel("Offen", eur(s.offen), s.letzter_kontakt ? "letzter Kontakt " + datum(s.letzter_kontakt.slice(0, 10)) : "")}
    ${umsatzBalken("Umsatz je Jahr (netto)", s.umsatz_jahr, "jahr")}
    ${balken("Aufträge nach Status", s.auftraege_status, "status")}${balken("Aufträge nach Jahr", s.auftraege_jahr, "jahr")}${balken("Aufträge nach Gruppe", s.auftraege_gruppe, "gruppe")}
    </div><p class="hinweis">Umsatz = festgeschriebene Rechnungen netto, Abschläge nicht doppelt gezählt.</p>`;
}
async function ansichtStatistik() {
  kopf({});
  const s = await api("statistik");
  const quote = s.angebote ? Math.round(s.beauftragt / s.angebote * 100) + " %" : "–";
  $("#inhalt").innerHTML = `<div class="titel"><h2>Statistik</h2></div><div class="raster">
    ${statKachel("Aktive Kunden", s.kunden_gesamt)}
    ${statKachel("Umsatz gesamt", eur(s.umsatz_gesamt), "festgeschriebene Rechnungen netto")}
    ${statKachel("Angebotsquote", quote, `${s.beauftragt} von ${s.angebote} Angeboten beauftragt`)}
    ${statKachel("Ø Auftragswert", s.durchschnitt_auftrag ? eur(s.durchschnitt_auftrag) : "–")}
    ${statKachel("Zahlungsdauer", s.zahlungsdauer != null ? n2(s.zahlungsdauer, 0) + " Tage" : "–", "Ø vom Rechnungsdatum bis zur Zahlung")}
    ${statKachel("Offene Forderungen", eur(s.offen))}
    <div class="kachel" style="grid-column:span 2"><h4>Top-Kunden nach Umsatz</h4>${s.top_kunden.length ? `<table class="liste"><tr><th>Kunde</th><th class="r">Umsatz</th><th class="r">Anteil</th></tr>
      ${s.top_kunden.map(t => `<tr class="klick" data-hash="#/kunde/${t.id}/statistik"><td>${esc(t.nummer)} ${esc(t.kurzname)}</td><td class="r">${eur(t.umsatz)}</td><td class="r">${n2(t.anteil, 1)} %</td></tr>`).join("")}</table>` : `<span class="hinweis">noch keine Rechnungen</span>`}</div>
    ${umsatzBalken("Umsatz je Jahr (netto)", s.umsatz_jahr, "jahr")}${umsatzBalken("Umsatz nach Kundengruppe", s.umsatz_gruppe, "gruppe")}
    ${balken("Kunden nach Gruppe", s.kunden_gruppe, "gruppe")}${balken("Neukunden je Jahr", s.neukunden_jahr, "jahr")}
    ${balken("Aufträge nach Status", s.auftraege_status, "status")}${balken("Aufträge nach Jahr", s.auftraege_jahr, "jahr")}</div>
    <div id="zstat" style="margin-top:26px"></div>`;
  await zahlungsStatistik($("#zstat"), null);
}
