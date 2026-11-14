"use strict";
// =====================================================================
//  Jahresring – Kontoauszüge (CAMT) und Liquiditätsvorschau
// =====================================================================
const BANK_FILTER = {status: "offen", q: ""};

async function ansichtBank() {
  OP_REITER("bank");
  const z = $("#inhalt");
  const d = await api("bank?" + new URLSearchParams(BANK_FILTER));
  const n = d.anzahl || {};
  const sicher = d.umsaetze.filter(u => u.status === "offen" && u.vorschlag && u.vorschlag.sicher);
  const ks = d.kontostand;
  const kann = darf("op", 2);
  const zielText = u => (u.ziel || []).map(t => `<div>${t.art === "op" ? "Zahlungseingang" : "Zahlungsauftrag"} <b>${esc(t.nummer || "")}</b> ${eur(Math.abs(t.betrag))}${t.art === "zahlung" && !t.gesetzt ? ` <span class="hinweis">(war schon bezahlt)</span>` : ""}</div>`).join("");
  const vorschlagText = v => !v ? `<span class="hinweis">kein Vorschlag</span>`
    : `<div class="bk-vs ${v.sicher ? "sicher" : "pruefen"}"><span class="tag">${v.sicher ? "sicher" : "prüfen"}</span> ${v.ziele.map(t => `${esc(t.text)}${v.ziele.length > 1 ? ` (${eur(t.betrag)})` : ""}`).join("<br>")}<div class="hinweis">${esc(v.grund)}</div></div>`;
  const zeilen = d.umsaetze.map(u => `<tr data-u="${u.id}">
      <td class="nw">${datum(u.buchung)}</td>
      <td><b>${esc(u.name || "–")}</b><div class="hinweis bk-zweck">${esc(u.zweck)}</div></td>
      <td class="r nw"><b style="color:${u.betrag < 0 ? "var(--rot)" : "var(--gruen)"}">${eur(u.betrag)}</b></td>
      <td>${u.status === "offen" ? vorschlagText(u.vorschlag) : u.status === "zugeordnet" ? zielText(u) : `<span class="hinweis">ignoriert${u.notiz ? ": " + esc(u.notiz) : ""}</span>`}</td>
      <td class="r">${!kann ? "" : u.status === "offen" ? `<span class="bk-kn">${u.vorschlag ? `<button class="btn${u.vorschlag.sicher ? " prim" : ""}" data-ok="${u.id}">Übernehmen</button>` : ""}<button class="btn" data-zu="${u.id}">Zuordnen …</button><button class="btn" data-ign="${u.id}" title="Kein Kunden- oder Lieferantenbezug, z. B. Kontoführung, Privatentnahme">Ohne Zuordnung</button></span>`
        : `<button class="btn" data-los="${u.id}">${u.status === "zugeordnet" ? "Zuordnung lösen" : "Zurückholen"}</button>`}</td></tr>`).join("");
  z.innerHTML = `<div class="titel"><h2>Kontoauszüge</h2><div class="rechts">
      ${kann ? `<label class="btn prim" title="CAMT-Datei (camt.053 oder camt.052, auch als ZIP) aus dem Onlinebanking">📥 Kontoauszug einlesen<input type="file" id="bkDatei" accept=".xml,.zip,application/xml,text/xml,application/zip" hidden multiple></label>` : ""}</div></div>
    <p class="hinweis" style="margin-top:-6px">Im Onlinebanking den Kontoauszug als <b>CAMT-Datei</b> (camt.053, bei manchen Banken „XML“ oder „ISO 20022“) herunterladen und hier einlesen.
      Gutschriften werden offenen Rechnungen zugeordnet, Abbuchungen den Zahlungsaufträgen. Schon eingelesene Umsätze erkennt das Programm und legt sie nicht doppelt an.</p>
    <div class="kachel" style="margin-bottom:12px">${ks ? `Kontostand laut Auszug vom <b>${datum(ks.saldo_datum)}</b>: <b style="font-size:17px">${eur(ks.saldo_ende)}</b> <span class="hinweis">${esc(ks.iban || "")}</span>` : `<span class="hinweis">Noch kein Kontoauszug mit Kontostand eingelesen.</span>`}
      · <a href="#/op/liquiditaet">Liquiditätsvorschau ›</a></div>
    ${sicher.length && kann && BANK_FILTER.status === "offen" ? `<div class="kachel" style="border-left:4px solid var(--gruen);margin-bottom:12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <span><b>${sicher.length}</b> ${sicher.length === 1 ? "Umsatz passt" : "Umsätze passen"} eindeutig zu Rechnung bzw. Zahlungsauftrag.</span><button class="btn prim" id="bkAlle">Alle sicheren übernehmen</button></div>` : ""}
    <div class="filterleiste" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
      ${[["offen", `Offen (${n.offen || 0})`], ["zugeordnet", `Zugeordnet (${n.zugeordnet || 0})`], ["ignoriert", `Ohne Zuordnung (${n.ignoriert || 0})`], ["alle", "Alle"]]
        .map(([k, t]) => `<button class="btn${BANK_FILTER.status === k ? " prim" : ""}" data-st="${k}">${t}</button>`).join("")}
      <input id="bkSuche" placeholder="Name, Verwendungszweck, Betrag …" value="${esc(BANK_FILTER.q)}" style="flex:1 1 200px;max-width:320px">
    </div>
    ${d.umsaetze.length ? `<table class="liste bk-liste"><tr><th>Buchung</th><th>Auftraggeber / Empfänger · Verwendungszweck</th><th class="r">Betrag</th><th>Zuordnung</th><th></th></tr>${zeilen}</table>`
      : `<div class="leer">${BANK_FILTER.status === "offen" ? "Keine offenen Umsätze." : "Keine Umsätze."}</div>`}
    ${d.auszuege.length ? `<h3 style="margin-top:22px">Eingelesene Dateien</h3><table class="liste"><tr><th>eingelesen</th><th>Datei</th><th>Zeitraum</th><th class="r">neu</th><th class="r">schon vorhanden</th><th class="r">Kontostand</th></tr>
      ${d.auszuege.map(a => `<tr><td class="nw">${datum(a.importiert)} ${esc((a.importiert || "").slice(11, 16))}</td><td>${esc(a.datei)} <span class="hinweis">${esc(a.format)}</span></td><td class="nw">${datum(a.von)} – ${datum(a.bis)}</td>
        <td class="r">${a.neu}</td><td class="r">${a.doppelt}</td><td class="r nw">${a.saldo_ende != null ? eur(a.saldo_ende) : ""}</td></tr>`).join("")}</table>` : ""}`;
  const neu = () => ansichtBank();
  $$("[data-st]", z).forEach(b => b.onclick = () => { BANK_FILTER.status = b.dataset.st; neu(); });
  const s = $("#bkSuche"); let t; s.oninput = () => { clearTimeout(t); t = setTimeout(() => { BANK_FILTER.q = s.value.trim(); neu().then(() => { const x = $("#bkSuche"); if (x) { x.focus(); x.setSelectionRange(x.value.length, x.value.length); } }); }, 350); };
  if ($("#bkDatei")) $("#bkDatei").onchange = async e => {
    const dateien = [...e.target.files]; let neuN = 0, dopp = 0;
    for (const f of dateien) {
      try { const r = await api("bank/einlesen", {method: "POST", body: {dateiname: f.name, daten: await dateiAlsBase64(f)}}); neuN += r.neu; dopp += r.doppelt; }
      catch (x) { toast(`${f.name}: ${x.message}`, true); }
    }
    toast(`${neuN} neue Umsätze eingelesen${dopp ? `, ${dopp} waren schon vorhanden` : ""}`);
    BANK_FILTER.status = "offen"; neu();
  };
  if ($("#bkAlle")) $("#bkAlle").onclick = async () => {
    if (!await frage(`${sicher.length} Umsätze wie vorgeschlagen zuordnen? Kundenzahlungen werden als Zahlungseingang gebucht, Zahlungsaufträge als bezahlt markiert.`, {ok: "Zuordnen"})) return;
    const r = await api("bank/sichere", {method: "POST", body: {}});
    toast(`${r.zugeordnet} Umsätze zugeordnet`); if (r.fehler.length) toast(r.fehler.join(" · "), true); neu();
  };
  $$("[data-ok]", z).forEach(b => b.onclick = async () => {
    const u = d.umsaetze.find(x => x.id === +b.dataset.ok);
    try { await api(`bank/${u.id}/zuordnen`, {method: "POST", body: {ziele: u.vorschlag.ziele}}); toast("Zugeordnet"); neu(); } catch (x) { toast(x.message, true); }
  });
  $$("[data-zu]", z).forEach(b => b.onclick = () => bankZuordnen(d.umsaetze.find(x => x.id === +b.dataset.zu), neu));
  $$("[data-ign]", z).forEach(b => b.onclick = async () => {
    const r = await modal("Ohne Zuordnung", `<p class="hinweis">Für Umsätze ohne Rechnung oder Zahlungsauftrag, z. B. Kontoführungsgebühren, Privatentnahmen oder Umbuchungen.</p>
      <div class="zeile"><label>Notiz</label><div><input name="notiz" placeholder="z. B. Kontoführung"></div></div>`, "Speichern");
    if (!r) return;
    await api(`bank/${b.dataset.ign}/ignorieren`, {method: "POST", body: {notiz: r.notiz}}); neu();
  });
  $$("[data-los]", z).forEach(b => b.onclick = async () => {
    const u = d.umsaetze.find(x => x.id === +b.dataset.los);
    if (u.status === "zugeordnet" && !await frage("Zuordnung lösen? Die daraus gebuchten Zahlungseingänge werden wieder entfernt (mit Protokolleintrag), ein dadurch als bezahlt markierter Zahlungsauftrag wird wieder offen.", {ok: "Lösen"})) return;
    try { await api(`bank/${u.id}/loesen`, {method: "POST", body: {}}); neu(); } catch (x) { toast(x.message, true); }
  });
}

async function bankZuordnen(u, fertig) {
  const k = await api("bank/kandidaten");
  const gutschrift = u.betrag > 0;
  const liste = gutschrift ? k.op : k.zahlung;
  const vorgabe = new Set(((u.vorschlag || {}).ziele || []).map(t => t.id));
  let fenster = null;
  const r = await modal(gutschrift ? "Gutschrift zuordnen" : "Abbuchung zuordnen", `
    <p><b>${esc(u.name || "")}</b> · ${datum(u.buchung)} · <b>${eur(u.betrag)}</b><br><span class="hinweis">${esc(u.zweck)}</span></p>
    <input id="bzSuche" placeholder="${gutschrift ? "Rechnungsnummer, Kunde …" : "Zahlungsauftrag, Lieferant, Rechnungsnummer …"}" style="width:100%;margin-bottom:6px">
    <div class="bz-liste" style="max-height:46vh;overflow:auto;border:1px solid var(--linie);border-radius:6px">
      ${liste.map(x => `<label class="bz-z" data-t="${esc((x.text || "").toLowerCase())} ${String(x.offen).replace(".", ",")}" style="display:flex;gap:8px;align-items:center;padding:6px 8px;border-bottom:1px solid var(--zeile2);cursor:pointer">
        <input type="${gutschrift ? "checkbox" : "radio"}" name="bzw" value="${x.id}" ${vorgabe.has(x.id) ? "checked" : ""}>
        <span style="flex:1">${esc(x.text)}<span class="hinweis"> · fällig ${datum(x.faellig)}</span></span><span class="nw">${eur(x.offen)}</span>
        ${gutschrift ? `<input class="bz-b" data-b="${x.id}" style="width:90px;text-align:right" placeholder="Betrag">` : ""}</label>`).join("") || `<div class="leer">Nichts Offenes vorhanden.</div>`}
    </div>
    ${gutschrift ? `<p class="hinweis" id="bzSumme"></p>` : ""}`, "Zuordnen", hg => {
    fenster = hg;
    $(".modal", hg).style.width = "min(760px,96vw)";
    const sum = () => {
      if (!gutschrift) return;
      const gew = $$("input[name=bzw]:checked", hg);
      if (gew.length === 1) { const b = $(`[data-b="${gew[0].value}"]`, hg); if (!b.value) b.value = zahlDE(u.betrag); }
      const s = gew.reduce((a, c) => a + (parseFloat(($(`[data-b="${c.value}"]`, hg).value || "0").replace(/\./g, "").replace(",", ".")) || 0), 0);
      $("#bzSumme", hg).innerHTML = `Aufgeteilt: <b>${eur(s)}</b> von ${eur(u.betrag)}${Math.abs(s - u.betrag) > 0.009 ? ` <span style="color:var(--rot)">– Rest ${eur(u.betrag - s)}</span>` : " ✓"}`;
    };
    $$("input[name=bzw]", hg).forEach(c => c.onchange = () => {
      if (gutschrift && !c.checked) $(`[data-b="${c.value}"]`, hg).value = "";
      if (gutschrift && c.checked) { const x = liste.find(y => y.id === +c.value); const rest = u.betrag - $$("input[name=bzw]:checked", hg).filter(o => o !== c).reduce((a, o) => a + (parseFloat(($(`[data-b="${o.value}"]`, hg).value || "0").replace(/\./g, "").replace(",", ".")) || 0), 0); $(`[data-b="${c.value}"]`, hg).value = zahlDE(Math.max(0, Math.min(x.offen, rest))); }
      sum();
    });
    $$(".bz-b", hg).forEach(i => i.oninput = () => { const c = $(`input[name=bzw][value="${i.dataset.b}"]`, hg); c.checked = !!i.value; sum(); });
    $("#bzSuche", hg).oninput = e => { const q = e.target.value.toLowerCase().trim(); $$(".bz-z", hg).forEach(l => l.style.display = !q || l.dataset.t.includes(q) ? "" : "none"); };
    if (gutschrift) { $$("input[name=bzw]:checked", hg).forEach(c => { const v = (u.vorschlag.ziele.find(t => t.id === +c.value) || {}).betrag; $(`[data-b="${c.value}"]`, hg).value = zahlDE(v); }); sum(); }
  });
  if (!r || !fenster) return;
  const zahlLesen = t => parseFloat(String(t || "0").replace(/\./g, "").replace(",", ".")) || 0;
  const ziele = $$("input[name=bzw]:checked", fenster).map(c => ({art: gutschrift ? "op" : "zahlung", id: +c.value,
    betrag: gutschrift ? zahlLesen($(`[data-b="${c.value}"]`, fenster).value) : -u.betrag}));
  if (!ziele.length) return toast("Bitte etwas auswählen.", true);
  try { await api(`bank/${u.id}/zuordnen`, {method: "POST", body: {ziele}}); toast("Zugeordnet"); fertig(); } catch (x) { toast(x.message, true); }
}

// ---------------------------------------------------------------- Liquiditätsvorschau
async function ansichtLiquiditaet() {
  OP_REITER("liq");
  const z = $("#inhalt");
  const d = await api("liquiditaet");
  const w = d.wochen, cfg = d.einstellungen;
  const werte = [d.start.betrag, ...w.map(x => x.saldo)];
  const max = Math.max(0, ...werte, ...w.map(x => x.ein)), min = Math.min(0, ...werte, ...w.map(x => -x.aus));
  const B = 900, H = 260, L = 70, R = 12, O = 14, U = 34, sp = (B - L - R) / Math.max(1, w.length);
  const y = v => O + (max - v) / ((max - min) || 1) * (H - O - U);
  const stufe = (() => { const r = (max - min) / 4 || 1, p = Math.pow(10, Math.floor(Math.log10(r))); return [1, 2, 2.5, 5, 10].map(f => f * p).find(f => f >= r); })();
  let raster = "";
  for (let v = Math.ceil(min / stufe) * stufe; v <= max + 1e-6; v += stufe)
    raster += `<line x1="${L}" x2="${B - R}" y1="${y(v)}" y2="${y(v)}" class="lq-r${Math.abs(v) < 1e-6 ? " null" : ""}"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end" class="lq-t">${zahlDE(v / 1000, Math.abs(v % 1000) > 1e-6 ? 1 : 0)} T€</text>`;
  const balken = w.map((x, i) => {
    const xm = L + sp * i + sp / 2, bw = Math.min(16, sp / 3);
    return `<rect x="${xm - bw - 1}" y="${y(x.ein)}" width="${bw}" height="${Math.max(0, y(0) - y(x.ein))}" class="lq-ein"><title>Eingänge KW ${x.kw}: ${eur(x.ein)}</title></rect>
      <rect x="${xm + 1}" y="${y(0)}" width="${bw}" height="${Math.max(0, y(-x.aus) - y(0))}" class="lq-aus"><title>Ausgänge KW ${x.kw}: ${eur(x.aus)}</title></rect>
      <text x="${xm}" y="${H - 12}" text-anchor="middle" class="lq-t">KW ${x.kw}</text>`;
  }).join("");
  const punkte = w.map((x, i) => `${L + sp * i + sp / 2},${y(x.saldo)}`).join(" ");
  const kreise = w.map((x, i) => `<circle cx="${L + sp * i + sp / 2}" cy="${y(x.saldo)}" r="4" class="lq-p${x.saldo < 0 ? " neg" : ""}"><title>Kontostand Ende KW ${x.kw}: ${eur(x.saldo)}</title></circle>`).join("");
  const svg = `<svg viewBox="0 0 ${B} ${H}" class="lq-svg" role="img" aria-label="Kontostand je Woche">${raster}${balken}<polyline points="${L},${y(d.start.betrag)} ${punkte}" class="lq-l"/>${kreise}</svg>`;
  const tief = d.tiefst;
  const artName = {op: "Rechnung", zahlung: "Zahlungsauftrag", lohn: "Löhne", regel: "regelmäßig", auftrag: "Auftrag (geplant)", ust: "Umsatzsteuer"};
  z.innerHTML = `<div class="titel"><h2>Liquiditätsvorschau</h2><div class="rechts"><label class="hinweis">Wochen <select id="lqW">${[8, 12, 16, 26].map(n => `<option ${n === cfg.wochen ? "selected" : ""}>${n}</option>`).join("")}</select></label></div></div>
    ${d.hinweise.map(h => `<div class="kachel" style="border-left:4px solid var(--orange,#c80);margin-bottom:8px">${esc(h)}</div>`).join("")}
    <div class="lq-kacheln">
      <div class="kachel"><div class="hinweis">Kontostand ${d.start.quelle === "kontoauszug" ? "laut Auszug" : d.start.quelle === "manuell" ? "von Hand" : ""} vom ${datum(d.start.datum)}</div><div class="lq-zahl">${eur(d.start.betrag)}</div></div>
      <div class="kachel"><div class="hinweis">Tiefster Stand (Woche ab ${tief ? datum(tief.von) : "–"})</div><div class="lq-zahl" style="color:${tief && tief.saldo < 0 ? "var(--rot)" : "inherit"}">${tief ? eur(tief.saldo) : "–"}</div></div>
      <div class="kachel"><div class="hinweis">Am Ende des Zeitraums</div><div class="lq-zahl">${w.length ? eur(w[w.length - 1].saldo) : "–"}</div></div>
      <div class="kachel"><div class="hinweis">Darin überfällig</div><div>Forderungen <b>${eur(d.ueberfaellig.ein)}</b><br>Zahlungsaufträge <b>${eur(d.ueberfaellig.aus)}</b></div></div>
    </div>
    <div class="kachel" style="margin:12px 0;overflow-x:auto">${svg}<div class="hinweis lq-leg"><span class="lq-sw ein"></span> Eingänge <span class="lq-sw aus"></span> Ausgänge <span class="lq-sw l"></span> Kontostand am Wochenende</div></div>
    <table class="liste lq-tab"><tr><th>Woche</th><th class="r">Eingänge</th><th class="r">Ausgänge</th><th class="r">Kontostand</th><th></th></tr>
      ${w.map((x, i) => `<tr class="lq-w" data-w="${i}" style="cursor:pointer"><td class="nw">KW ${x.kw} · ${datum(x.von).slice(0, 6)} – ${datum(x.bis).slice(0, 6)}</td><td class="r nw">${x.ein ? eur(x.ein) : ""}</td>
        <td class="r nw">${x.aus ? eur(-x.aus) : ""}</td><td class="r nw"><b style="color:${x.saldo < 0 ? "var(--rot)" : "inherit"}">${eur(x.saldo)}</b></td><td class="hinweis">${x.posten.length ? x.posten.length + " Posten ▾" : ""}</td></tr>
        <tr class="lq-d" data-d="${i}" hidden><td colspan="5"><table class="lq-pt">${x.posten.map(p => `<tr><td class="nw">${datum(p.datum)}</td><td>${p.link ? `<a href="${esc(p.link)}">${esc(p.text)}</a>` : esc(p.text)}</td>
          <td class="hinweis">${esc(artName[p.art] || p.art)}</td><td class="r nw" style="color:${p.betrag < 0 ? "var(--rot)" : "var(--gruen)"}">${eur(p.betrag)}</td></tr>`).join("")}</table></td></tr>`).join("")}</table>
    <h3 style="margin-top:22px">Annahmen</h3>
    <div class="form" style="grid-template-columns:1fr">
      ${zeile("Einrechnen", `<label><input type="checkbox" id="lqAuf" ${cfg.auftraege ? "checked" : ""}> Rest laufender Aufträge (geplanter Termin + 14 Tage)</label>
        <label><input type="checkbox" id="lqLohn" ${cfg.loehne ? "checked" : ""}> Löhne künftiger Monate wie im zuletzt erfassten Monat</label>`)}
      ${zeile("Umsatzsteuer", `<select id="lqUst">${[["quartal", "vierteljährliche Voranmeldung"], ["monat", "monatliche Voranmeldung"], ["keine", "nicht einrechnen"]].map(([k, t]) => `<option value="${k}" ${cfg.ust.rhythmus === k ? "selected" : ""}>${t}</option>`).join("")}</select>
        <label><input type="checkbox" id="lqDf" ${cfg.ust.dauerfrist ? "checked" : ""}> Dauerfristverlängerung</label>`)}
      ${zeile("Kontostand von Hand", `<input id="lqSb" placeholder="Betrag" value="${cfg.start_manuell ? zahlDE(cfg.start_manuell.betrag) : ""}" style="max-width:140px"> am <input type="date" id="lqSd" value="${cfg.start_manuell ? cfg.start_manuell.datum : heute()}" style="max-width:160px">
        <span class="hinweis">nur nötig, solange kein neuerer Kontoauszug eingelesen ist</span>`)}
    </div>
    <h3 style="margin-top:16px">Regelmäßige Zahlungen</h3>
    <p class="hinweis">Miete, Versicherungen, Leasing, Kfz-Steuer, Beiträge … Ausgaben mit Minus eintragen (z. B. -850), regelmäßige Einnahmen ohne.</p>
    <table class="liste" id="lqRegel"><tr><th>Bezeichnung</th><th class="r">Betrag</th><th>Rhythmus</th><th>am Tag</th><th>ab Monat</th><th>darin USt %</th><th></th></tr>
      ${cfg.regelmaessig.map((x, i) => `<tr data-i="${i}"><td><input data-k="text" value="${esc(x.text)}"></td><td><input data-k="betrag" value="${zahlDE(x.betrag)}" style="width:100px;text-align:right"></td>
        <td><select data-k="rhythmus">${[["monatlich", "monatlich"], ["quartal", "vierteljährlich"], ["halbjahr", "halbjährlich"], ["jaehrlich", "jährlich"]].map(([k, t]) => `<option value="${k}" ${x.rhythmus === k ? "selected" : ""}>${t}</option>`).join("")}</select></td>
        <td><input data-k="tag" type="number" min="1" max="31" value="${x.tag}" style="width:60px"></td><td><input data-k="ab" type="month" value="${x.ab}"></td>
        <td><select data-k="ust">${[0, 7, 19].map(v => `<option ${+x.ust === v ? "selected" : ""}>${v}</option>`).join("")}</select></td><td><button class="btn" data-weg="${i}">✕</button></td></tr>`).join("")}
    </table><button class="btn" id="lqNeu" style="margin-top:6px">＋ Regelmäßige Zahlung</button>
    <p class="hinweis" style="margin-top:14px">Alle Werte sind Schätzungen aus den Daten im Programm. Umsatzsteuer nach vereinnahmten Entgelten (Ist-Versteuerung), Lohnkosten nach dem letzten erfassten Monat. Zahlungen, die nicht im Programm stehen (z. B. Einkommensteuer-Vorauszahlung, Privatentnahmen), als regelmäßige Zahlung eintragen.</p>`;
  const speichern = async teil => { await api("liquiditaet/einstellungen", {method: "PUT", body: teil}); ansichtLiquiditaet(); };
  $("#lqW").onchange = e => speichern({wochen: +e.target.value});
  $("#lqAuf").onchange = e => speichern({auftraege: e.target.checked});
  $("#lqLohn").onchange = e => speichern({loehne: e.target.checked});
  $("#lqUst").onchange = $("#lqDf").onchange = () => speichern({ust: {rhythmus: $("#lqUst").value, dauerfrist: $("#lqDf").checked}});
  $("#lqSb").onchange = $("#lqSd").onchange = () => speichern({start_manuell: $("#lqSb").value.trim() ? {betrag: $("#lqSb").value, datum: $("#lqSd").value} : null});
  const regel = () => $$("#lqRegel tr[data-i]").map(tr => Object.fromEntries($$("[data-k]", tr).map(el => [el.dataset.k, el.value])));
  $$("#lqRegel [data-k]").forEach(el => el.onchange = () => speichern({regelmaessig: regel()}));
  $$("[data-weg]").forEach(b => b.onclick = () => speichern({regelmaessig: regel().filter((_, i) => i !== +b.dataset.weg)}));
  $("#lqNeu").onclick = () => speichern({regelmaessig: [...regel(), {text: "Neue Zahlung", betrag: -100, rhythmus: "monatlich", tag: 1, ab: heute().slice(0, 7), ust: 0}]});
  $$(".lq-w").forEach(tr => tr.onclick = () => { const d2 = $(`[data-d="${tr.dataset.w}"]`); d2.hidden = !d2.hidden; });
}
