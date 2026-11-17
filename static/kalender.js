"use strict";
// =====================================================================
//  Jahresring – Kalender & Fertigungsplanung
// =====================================================================
const KAL = {ansicht: "planung", start: null, wochen: (() => { try { const w = +localStorage.getItem("kal_wochen"); return [1, 2, 4, 6, 8, 13, 26].includes(w) ? w : 8; } catch (e) { return 8; } })(), zeigeEnde: false, zeigeAngebote: true};
const TAG_MS = 864e5;
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const vonIso = s => { const [y, m, t] = s.split("-").map(Number); return new Date(y, m - 1, t); };
const plusTage = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const montag = d => plusTage(d, -((d.getDay() + 6) % 7));
const tageZwischen = (a, b) => Math.round((vonIso(b) - vonIso(a)) / TAG_MS);
const WT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const typFarbe = typ => ((E.termin_typen || []).find(t => t.name === typ) || {}).farbe || "#9a9087";
const arbeitstageJS = (v, b) => { let n = 0; for (let d = vonIso(v); d <= vonIso(b); d = plusTage(d, 1)) if ((d.getDay() + 6) % 7 < 5) n++; return n; };
const kwVon = d => kw(d);
const ABW_FARBE = {urlaub: "#6f9bcf", krank: "#cf7f6f", kind_krank: "#cf9a6f", schule: "#82b17f", sonder: "#a993cf", ueberstunden: "#c9ab4c", unbezahlt: "#a8a29a", abwesend: "#8f99a8"};
const abwText = a => `${a.kuerzel || a.name} ${a.art_name}${a.halbtag ? " ½" : ""}${a.beantragt ? " (beantragt)" : ""}`;
const abwTip = a => `${a.name}: ${a.art_name}${a.halbtag ? " (halbe Tage)" : ""} · ${datum(a.von)}${a.bis !== a.von ? " – " + datum(a.bis) : ""}${a.beantragt ? " · beantragt, noch nicht genehmigt" : ""}`;
const fsBalken = t => t.gebucht ? `<b class="kp-fs" style="width:${Math.min(100, t.gebucht / (t.geplant || 1) * 100)}%;${t.gebucht > t.geplant + 0.05 ? "background:#e05a4a" : ""}"></b>` : "";

function kalKopf(aktiv) {
  kopf({krumen: [["Kalender", "#/kalender"]],
    reiter: [["Planung", "planung"], ["Monat", "monat"], ["Woche", "woche"]].map(([l, s]) => [l, `#/kalender/${s}/${iso(KAL.start)}`, s === aktiv]),
    reiter2: darf("einstellungen", 2) ? [["Einstellungen", "#/einstellungen/kalender", false]] : []});
}

async function ansichtKalender(ansicht = "planung", datumStr) {
  KAL.ansicht = ansicht;
  const basis = datumStr ? vonIso(datumStr) : (KAL.start || new Date());
  if (ansicht === "monat") KAL.start = new Date(basis.getFullYear(), basis.getMonth(), 1);
  else KAL.start = montag(basis);
  kalKopf(ansicht);
  $(".wrap").classList.add("breit");
  const z = $("#inhalt");
  let von, bis;
  if (ansicht === "planung") { von = KAL.start; bis = plusTage(von, KAL.wochen * 7 - 1); }
  else if (ansicht === "monat") { von = montag(KAL.start); bis = plusTage(von, 41); }
  else { von = KAL.start; bis = plusTage(von, 6); }
  z.innerHTML = `<div class="leer">Kalender wird geladen …</div>`;
  const neu = KAL._neu; KAL._neu = false;
  const d = await api(`kalender?von=${iso(von)}&bis=${iso(bis)}${neu ? "&neu=1" : ""}`);
  KAL.daten = d;
  const titel = ansicht === "monat" ? `${MONATE[KAL.start.getMonth()]} ${KAL.start.getFullYear()}`
    : `KW ${kwVon(von)}${ansicht === "planung" ? "–" + kwVon(bis) : ""} · ${von.toLocaleDateString("de-DE")} – ${bis.toLocaleDateString("de-DE")}`;
  const schritt = ansicht === "monat" ? null : ansicht === "planung" ? 7 * Math.max(1, Math.floor(KAL.wochen / 2)) : 7;
  const vor = ansicht === "monat" ? iso(new Date(KAL.start.getFullYear(), KAL.start.getMonth() - 1, 1)) : iso(plusTage(KAL.start, -schritt));
  const nach = ansicht === "monat" ? iso(new Date(KAL.start.getFullYear(), KAL.start.getMonth() + 1, 1)) : iso(plusTage(KAL.start, schritt));
  z.innerHTML = `
    <div class="titel"><h2 style="min-width:0">${titel}</h2>
      <div class="such">
        <a class="btn" href="#/kalender/${ansicht}/${vor}" title="Zurück">◀</a><a class="btn" href="#/kalender/${ansicht}/${iso(new Date())}">Heute</a><a class="btn" href="#/kalender/${ansicht}/${nach}" title="Weiter">▶</a>
        ${ansicht === "planung" ? `<select id="kWochen">${[1, 2, 4, 6, 8, 13, 26].map(w => `<option value="${w}" ${w === KAL.wochen ? "selected" : ""}>${w} ${w === 1 ? "Woche" : "Wochen"}</option>`).join("")}</select>
          <label class="pchk"><input type="checkbox" id="kAng" ${KAL.zeigeAngebote ? "checked" : ""}> Angebote</label>
          <label class="pchk"><input type="checkbox" id="kEnde" ${KAL.zeigeEnde ? "checked" : ""}> Erledigte</label>` : ""}
      </div>
      <div class="rechts">
        ${termineAendern() ? `<button class="btn" id="kNeu">+ Termin</button>` : ""}
        <button class="btn" id="kAkt" title="Google Kalender neu laden">↻ Google</button>
        <a class="btn" href="/api/kalender/export.ics" title="Eigene Termine als Datei für den Import in Google Kalender">Export .ics</a>
      </div></div>
    ${d.fehler.length ? `<div class="kachel" style="margin-bottom:10px;color:var(--rot)">${d.fehler.map(esc).join("<br>")}</div>` : ""}
    ${(E.google_kalender || []).length ? "" : `<div class="hinweis" style="margin:-4px 0 10px">Tipp: Unter <a href="#/einstellungen/kalender">Kalender-Einstellungen</a> lässt sich ein Google Kalender einbinden.</div>`}
    <div id="kal"></div>`;
  $("#kAkt").onclick = () => { KAL._neu = true; ansichtKalender(ansicht, iso(KAL.start)); };
  if ($("#kNeu")) $("#kNeu").onclick = () => terminDialog({von: iso(new Date()), bis: iso(new Date())});
  if (ansicht === "planung") {
    $("#kWochen").onchange = e => { KAL.wochen = +e.target.value; try { localStorage.setItem("kal_wochen", KAL.wochen); } catch (x) {} ansichtKalender("planung", iso(KAL.start)); };
    $("#kAng").onchange = e => { KAL.zeigeAngebote = e.target.checked; planungZeichnen(von, bis); };
    $("#kEnde").onchange = e => { KAL.zeigeEnde = e.target.checked; planungZeichnen(von, bis); };
    planungZeichnen(von, bis);
  } else if (ansicht === "monat") monatZeichnen(von);
  else wocheZeichnen(von);
}

// ---------- Termin-Dialog ----------
const termineAendern = () => darf("kalender", 2) && !nurWerkstatt();
const maListe = () => (KAL.daten?.kapazitaet?.mitarbeiter || []);
function maVon(t) { try { return (typeof t.mitarbeiter === "string" ? JSON.parse(t.mitarbeiter || "[]") : t.mitarbeiter || []).map(Number); } catch (e) { return []; } }
const maKurz = t => maVon(t).map(id => (maListe().find(m => m.id === id) || {}).kuerzel).filter(Boolean).join(", ");
let gewMa = [];
async function terminDialog(t, {auftragFest = null} = {}) {
  if (!KAL.daten && termineAendern()) { try { KAL.daten = await api(`kalender?von=${iso(new Date())}&bis=${iso(new Date())}`); } catch (e) { /* ohne Mitarbeiterliste */ } }
  if (!termineAendern()) { if (t && t.id) terminAnsehen(t); else toast("Termine legt das Büro an. Sie lassen sich hier nur ansehen.", true); return false; }
  const auftraege = await api("auftraege");
  const neu = !t.id;
  const typen = (E.termin_typen || []).map(x => x.name);
  const stdAuto = t.von && t.bis ? arbeitstageJS(t.von, t.bis) * (+E.tagesstunden || 8) : 0;
  const r = await modal(neu ? "Neuer Termin" : "Termin bearbeiten", `
    <div class="zeile"><label>Auftrag</label><div><select name="auftrag_id" ${auftragFest ? "disabled" : ""}><option value="">— ohne Auftrag —</option>${auftraege.map(a => `<option value="${a.id}" ${a.id === (t.auftrag_id || auftragFest) ? "selected" : ""}>${esc(a.nummer)} · ${esc(a.kunde || "")} · ${esc(kurz(a.bezeichnung, 40))}</option>`).join("")}</select></div></div>
    <div class="zeile"><label>Art</label><div><select name="typ">${opts(typen, t.typ || "Fertigung")}</select></div></div>
    <div class="zeile"><label>Titel</label><div><input name="titel" value="${esc(t.titel || "")}" placeholder="optional, z. B. Korpusse"></div></div>
    <div class="zeile"><label>Von / bis</label><div><input type="date" name="von" value="${esc(t.von)}"><input type="date" name="bis" value="${esc(t.bis || t.von)}"></div></div>
    <div class="zeile"><label>Uhrzeit</label><div><input type="time" name="zeit_von" value="${esc(t.zeit_von || "")}"><input type="time" name="zeit_bis" value="${esc(t.zeit_bis || "")}"><span class="hinweis" style="padding-top:5px">leer = ganztägig</span></div></div>
    <div class="zeile"><label>Stunden</label><div><input name="stunden" class="zahl" style="width:90px" value="${t.stunden == null ? "" : n2(t.stunden, 1)}" placeholder="${n2(stdAuto, 0)}"><span class="hinweis" style="padding-top:5px">leer = Arbeitstage × ${n2(+E.tagesstunden || 8, 0)} h</span></div></div>
    ${maListe().length ? `<div class="zeile"><label>Mitarbeiter</label><div class="radio" id="tMa">${maListe().map(m => `<label><input type="checkbox" data-ma="${m.id}" ${maVon(t).includes(m.id) ? "checked" : ""}> ${esc(m.name)}</label>`).join("")}<span class="hinweis" style="width:100%">für die Kapazität: Stunden des Termins werden auf die gewählten Mitarbeiter verteilt; ohne Stunden sind sie an diesen Tagen voll verplant</span></div></div>` : ""}
    <div class="zeile"><label>Notiz</label><div><textarea name="notiz" rows="2">${esc(t.notiz || "")}</textarea></div></div>
    ${neu ? "" : `<div class="zeile"><label></label><div><label class="pchk"><input type="checkbox" id="tErl" ${t.erledigt ? "checked" : ""}> erledigt</label><button class="btn rot" id="tDel" type="button" style="margin-left:auto">Termin löschen</button></div></div>`}
    ${neu || !t.auftrag_id ? "" : `<div style="margin-top:12px;border-top:1px solid var(--linie);padding-top:10px">
      <b>Stunden auf diesen Termin</b> <span id="tbSum" class="hinweis"></span>
      <div id="tbListe" style="max-height:150px;overflow:auto;margin:6px 0"></div>
      <div data-enter="tbBuchen" style="display:flex;gap:6px;flex-wrap:wrap;align-items:center"><input type="date" id="tbDat" value="${esc(iso(new Date()) >= t.von && iso(new Date()) <= t.bis ? iso(new Date()) : t.von)}"><input id="tbStd" class="zahl" style="width:70px" placeholder="Std."><input id="tbTxt" placeholder="Tätigkeit" style="flex:1;min-width:120px"><button class="btn" id="tbBuchen" type="button">Buchen</button></div></div>`}`, neu ? "Anlegen" : "Speichern", hg => {
      gewMa = maVon(t);
      $$("[data-ma]", hg).forEach(c => c.onchange = () => { gewMa = $$("[data-ma]", hg).filter(x => x.checked).map(x => +x.dataset.ma); });
      if (!neu && t.auftrag_id) buchungenLaden(t);
    });
  if (!r) return false;
  const body = {...r, stunden: r.stunden ? zahlEin(r.stunden) : null, auftrag_id: auftragFest || (r.auftrag_id ? +r.auftrag_id : null), mitarbeiter: gewMa};
  if (!neu) body.erledigt = KAL._erl ? 1 : 0;
  try {
    const erg = neu ? await api("termine", {method: "POST", body}) : await api("termine/" + t.id, {method: "PUT", body});
    if (erg && erg.warnung) toast("Termin gespeichert – Hinweis: " + erg.warnung, true); else toast(neu ? "Termin angelegt" : "Termin gespeichert");
  } catch (e) { toast(e.message, true); return false; }
  neuLaden();
  return true;
}
document.addEventListener("change", e => { if (e.target.id === "tErl") KAL._erl = e.target.checked; });
document.addEventListener("click", async e => {
  if (e.target.id !== "tDel") return;
  const id = KAL._dialogId; if (!id || !await frage("Termin löschen?")) return;
  await api("termine/" + id, {method: "DELETE"});
  document.querySelector(".modal-hg")?.remove(); toast("Termin gelöscht"); neuLaden();
});
async function buchungenLaden(t) {
  const l = await api("stunden?termin=" + t.id);
  const sum = l.reduce((s, x) => s + x.stunden, 0);
  if (!$("#tbListe")) return;
  $("#tbSum").textContent = `· ${n2(sum, 1)} von ${n2(t.geplant ?? 0, 1)} h`;
  $("#tbListe").innerHTML = l.length ? `<table class="liste">${l.map(x => `<tr><td>${datum(x.datum)}</td><td class="r">${n2(x.stunden)} h</td><td>${esc(x.taetigkeit || "")}</td><td>${esc(x.kst || "")}</td></tr>`).join("")}</table>` : `<span class="hinweis">noch keine</span>`;
}
document.addEventListener("click", async e => {
  if (e.target.id !== "tbBuchen") return;
  const t = KAL._dialogTermin; if (!t) return;
  const h = zahlEin($("#tbStd").value); if (!h) return toast("Bitte Stunden eingeben.", true);
  try {
    await api("stunden", {method: "POST", body: {termin_id: t.id, auftrag_id: t.auftrag_id, datum: $("#tbDat").value, stunden: h, taetigkeit: $("#tbTxt").value}});
    $("#tbStd").value = ""; $("#tbTxt").value = ""; toast("Gebucht"); KAL._gebucht = true; buchungenLaden(t);
  } catch (er) { toast(er.message, true); }
});
function terminAnsehen(t) {
  modal(`${esc(t.typ || "Termin")} ${datum(t.von)}${t.bis && t.bis !== t.von ? " – " + datum(t.bis) : ""}`, `
    ${t.auftragsnr ? `<p><b>${esc(t.auftragsnr)}</b> ${esc(t.bezeichnung || "")}${t.kunde ? " · " + esc(t.kunde) : ""}</p>` : ""}
    ${t.zeit_von ? `<p>Uhrzeit ${esc(t.zeit_von)}${t.zeit_bis ? "–" + esc(t.zeit_bis) : ""}</p>` : ""}
    ${t.titel ? `<p>${esc(t.titel)}</p>` : ""}${t.notiz ? `<p style="white-space:pre-wrap">${esc(t.notiz)}</p>` : ""}
    <p class="hinweis">Nur ansehen: Termine legt das Büro an und ändert sie.</p>`, "Schließen");
}
function terminBearbeiten(t) { KAL._dialogTermin = t; KAL._gebucht = false; KAL._dialogId = t.id; KAL._erl = !!t.erledigt;
  return terminDialog(t).then(ok => { if (!ok && KAL._gebucht) neuLaden(); return ok; }); }
function neuLaden() {
  const h = location.hash;
  if (h.startsWith("#/kalender")) ansichtKalender(KAL.ansicht, iso(KAL.start)); else render();
}

// ---------- Planung (Balkenansicht) ----------
function lanes(items) {
  const reihen = [];
  items.sort((a, b) => a.von.localeCompare(b.von));
  for (const it of items) {
    let i = reihen.findIndex(r => r.every(x => x.bis < it.von || x.von > it.bis));
    if (i < 0) { reihen.push([]); i = reihen.length - 1; }
    reihen[i].push(it); it.lane = i;
  }
  return Math.max(1, reihen.length);
}

function planungZeichnen(von, bis) {
  const d = KAL.daten;
  if (!KAL.zu) { try { KAL.zu = new Set(JSON.parse(localStorage.getItem("kal_zu") || "[]")); } catch (e) { KAL.zu = new Set(); } }
  const ziel = $("#kal");
  const tage = tageZwischen(iso(von), iso(bis)) + 1;
  const breite = Math.max(600, ziel.clientWidth - 250);
  const tw = Math.max(14, Math.floor(breite / tage));
  const heuteIso = iso(new Date());
  const x = s => Math.max(0, tageZwischen(iso(von), s)) * tw;
  const w = (a, b) => (Math.min(tageZwischen(iso(von), b), tage - 1) - Math.max(0, tageZwischen(iso(von), a)) + 1) * tw;
  const sichtbar = (a, b) => b >= iso(von) && a <= iso(bis);
  const ende = E.status_ende || [];
  let auftraege = d.auftraege.filter(a => (KAL.zeigeEnde || !ende.includes(a.status)) && (KAL.zeigeAngebote || !a.angebot));
  const termineVon = id => d.termine.filter(t => t.auftrag_id === id);
  const beauftragt = auftraege.filter(a => !a.angebot), angebote = auftraege.filter(a => a.angebot);
  const ohne = d.termine.filter(t => !t.auftrag_id);

  // Kopfzeilen
  let kopfM = "", kopfK = "", kopfT = "", raster = "";
  // Feiertage: farbiger Streifen über die ganze Spalte (in jeder Zeile), der Name steht beim Überfahren und im Kopf
  const ftName = Object.fromEntries((d.feiertage || []).map(f => [f.datum, f.name]));
  for (let i = 0; i < tage; i++) {
    const t = plusTage(von, i), wt = (t.getDay() + 6) % 7, s = iso(t);
    if (i === 0 || t.getDate() === 1) kopfM += `<div class="kp-m" style="left:${i * tw}px">${MONATE[t.getMonth()]} ${t.getFullYear()}</div>`;
    if (wt === 0 || i === 0) kopfK += `<div class="kp-k" style="left:${i * tw}px;width:${tw * (7 - wt)}px">KW ${kw(t)}</div>`;
    kopfT += `<div class="kp-t${wt > 4 ? " we" : ""}${ftName[s] ? " ft" : ""}${s === heuteIso ? " heute" : ""}" style="left:${i * tw}px;width:${tw}px"${ftName[s] ? ` title="Feiertag: ${esc(ftName[s])}"` : ""}>${tw >= 22 ? WT[wt] + "<br>" : ""}${t.getDate()}</div>`;
    if (ftName[s]) raster += `<div class="kp-ftag" style="left:${i * tw}px;width:${tw}px" title="Feiertag: ${esc(ftName[s])}"></div>`;
    else if (wt > 4) raster += `<div class="kp-we" style="left:${i * tw}px;width:${tw}px"></div>`;
    if (wt === 0) raster += `<div class="kp-wl" style="left:${i * tw}px"></div>`;
  }
  const heuteX = sichtbar(heuteIso, heuteIso) ? `<div class="kp-heute" style="left:${x(heuteIso) + tw / 2}px"></div>` : "";

  const balken = (it, cls, inhalt, attrs, oben = 4) => `<div class="kp-b ${cls}" ${attrs} style="left:${x(it.von)}px;width:${w(it.von, it.bis) - 2}px;top:${oben + it.lane * 26}px;${it.farbe ? `--f:${it.farbe}` : ""}" title="${esc(it.tip || "")}">
      ${it.von >= iso(von) ? `<i class="kp-h l"></i>` : ""}<span>${inhalt}</span>${it.bis <= iso(bis) ? `<i class="kp-h r"></i>` : ""}</div>`;

  const zeile = (a) => {
    const items = [], zu = KAL.zu.has(a.id);
    if (a.plan_von && sichtbar(a.plan_von, a.plan_bis || a.plan_von))
      items.push({von: a.plan_von, bis: a.plan_bis || a.plan_von, art: "plan", id: a.id, tip: `${a.angebot ? "Vorgemerkter (reservierter) Ausführungszeitraum aus dem Angebot" : "Geplanter Ausführungszeitraum"} ${datum(a.plan_von)} – ${datum(a.plan_bis || a.plan_von)}`});
    const ts = termineVon(a.id).filter(t => sichtbar(t.von, t.bis));
    if (zu && !items.length && ts.length) {   // zugeklappt ohne geplanten Zeitraum: ein Sammelbalken über alle Termine
      const v = ts.reduce((m, t) => t.von < m ? t.von : m, ts[0].von), b = ts.reduce((m, t) => t.bis > m ? t.bis : m, ts[0].bis);
      items.push({von: v < iso(von) ? iso(von) : v, bis: b, art: "sum", tip: ts.map(t => `${t.typ}${t.titel ? ": " + t.titel : ""} ${datum(t.von)}${t.bis !== t.von ? "–" + datum(t.bis) : ""}`).join("\n")});
    }
    if (!zu) for (const t of ts)
      items.push({von: t.von, bis: t.bis, art: "termin", t, farbe: typFarbe(t.typ), tip: `${t.typ}${t.titel ? ": " + t.titel : ""} · gebucht ${n2(t.gebucht || 0, 1)} von ${n2(t.geplant || 0, 1)} h · ${datum(t.von)}${t.bis !== t.von ? " – " + datum(t.bis) : ""}${t.zeit_von ? " " + t.zeit_von + "–" + (t.zeit_bis || "") : ""}${t.notiz ? "\n" + t.notiz : ""}`});
    const n = lanes(items);
    const voll = a.soll_stunden && a.geplant_stunden >= a.soll_stunden - 0.05;
    return `<div class="kp-zeile${zu ? " kp-zu" : ""}" data-a="${a.id}">
      <div class="kp-label"><button class="kp-auf" data-zu="${a.id}" title="${zu ? "Termine aufklappen" : "Termine zuklappen (nur geplanter Zeitraum)"}">${zu ? "▸" : "▾"}</button><a href="#/auftrag/${a.id}"><b>${esc(a.nummer)}</b> ${esc(a.kunde || "")}</a><div class="kp-bez">${esc(kurz(a.bezeichnung, 34))}</div>
        <div class="kp-std"><span class="kp-st">${esc(a.status || "")}</span>
          <span title="Ist (gebucht) / geplant (Termine) / Soll (Kalkulation)"> · Ist ${n2(a.ist_stunden || 0, 0)} · Plan <span style="color:${voll ? "var(--gruen)" : "inherit"}">${n2(a.geplant_stunden, 0)}</span>${a.soll_stunden ? ` · Soll ${n2(a.soll_stunden, 0)}` : ""} h</span></div></div>
      <div class="kp-flaeche" style="height:${n * 26 + 8}px;width:${tage * tw}px">${raster}${heuteX}
        ${items.map(it => it.art === "sum" ? balken(it, "sum", `${ts.length} Termin${ts.length > 1 ? "e" : ""}`, `data-zu="${a.id}"`) : it.art === "plan"
          ? balken(it, a.angebot ? "plan" : "plan fest", a.angebot ? "vorgemerkt" : "geplant", `data-plan="${a.id}"`)
          : balken(it, "termin" + (it.t.erledigt ? " erl" : ""), `${esc(it.t.typ)}${it.t.titel ? " · " + esc(it.t.titel) : ""}${maKurz(it.t) ? ` <small>· ${esc(maKurz(it.t))}</small>` : ""}${it.t.gebucht ? ` <small>${n2(it.t.gebucht, 1)}/${n2(it.t.geplant, 0)} h</small>` : ""}${fsBalken(it.t)}`, `data-t="${it.t.id}"`)).join("")}
      </div></div>`;
  };
  const ext = d.extern.map(e => ({...e, tip: `${e.quelle}: ${e.titel}${e.zeit_von ? " " + e.zeit_von + "–" + e.zeit_bis : ""}${e.ort ? " · " + e.ort : ""}`}));
  const extN = lanes(ext);
  const abwItems = [...(d.abwesenheiten || []).map(a => ({...a, titel: abwText(a), tip: abwTip(a), farbe: ABW_FARBE[a.art] || "#8f99a8"}))]
    .map(e => ({...e, von: e.von < iso(von) ? iso(von) : e.von, bis: e.bis > iso(plusTage(von, tage - 1)) ? iso(plusTage(von, tage - 1)) : e.bis}));
  const abwN = lanes(abwItems);
  const ohneItems = ohne.filter(t => sichtbar(t.von, t.bis)).map(t => ({von: t.von, bis: t.bis, t, farbe: typFarbe(t.typ), tip: `${t.typ}${t.titel ? ": " + t.titel : ""}`}));
  const ohneN = lanes(ohneItems);
  ziel.innerHTML = `<div class="kp" style="--tw:${tw}px">
    <div class="kp-kopf"><div class="kp-label kp-ecke"></div><div class="kp-skala" style="width:${tage * tw}px">${kopfM}${kopfK}${kopfT}</div></div>
    ${d.extern.length || (E.google_kalender || []).length ? `<div class="kp-zeile kp-ext"><div class="kp-label"><b>Google Kalender</b><div class="kp-bez">${esc((E.google_kalender || []).map(k => k.name).join(", "))}</div></div>
      <div class="kp-flaeche" style="height:${extN * 26 + 8}px;width:${tage * tw}px">${raster}${heuteX}${ext.map(e => `<div class="kp-b ext" style="left:${x(e.von)}px;width:${w(e.von, e.bis) - 2}px;top:${4 + e.lane * 26}px;--f:${e.farbe}" title="${esc(e.tip)}"><span>${e.zeit_von && w(e.von, e.bis) > 70 ? e.zeit_von + " " : ""}${esc(e.titel)}</span></div>`).join("")}</div></div>` : ""}
    ${abwItems.length ? `<div class="kp-zeile kp-ext kp-abw"><div class="kp-label"><b>Abwesend</b><div class="kp-bez">Urlaub, Krank, Schule …</div></div>
      <div class="kp-flaeche" style="height:${abwN * 26 + 8}px;width:${tage * tw}px">${raster}${heuteX}${abwItems.map(e => `<div class="kp-b ext${e.beantragt ? " beantr" : ""}${e.ft ? " ft" : ""}" ${e.id ? `data-abw="${e.id}"` : ""} style="left:${x(e.von)}px;width:${w(e.von, e.bis) - 2}px;top:${4 + e.lane * 26}px;--f:${e.farbe}" title="${esc(e.tip)}"><span>${esc(e.titel)}</span></div>`).join("")}</div></div>` : ""}
    ${kapazitaetHtml(d.kapazitaet, {von, tage, tw, raster, heuteX, balken, sichtbar, termine: d.termine})}
    <div class="kp-zeile kp-ohne" data-a=""><div class="kp-label"><b>Allgemein</b><div class="kp-bez">Termine ohne Auftrag</div></div>
      <div class="kp-flaeche" style="height:${ohneN * 26 + 8}px;width:${tage * tw}px">${raster}${heuteX}${ohneItems.map(it => balken(it, "termin" + (it.t.erledigt ? " erl" : ""), `${esc(it.t.typ)}${it.t.titel ? " · " + esc(it.t.titel) : ""}`, `data-t="${it.t.id}"`)).join("")}</div></div>
    ${beauftragt.length ? `<div class="kp-gruppe">Beauftragt · Fertigungsplanung <button class="btn klein" data-zualle="${beauftragt.every(a => KAL.zu.has(a.id)) ? "auf" : "zu"}">${beauftragt.every(a => KAL.zu.has(a.id)) ? "▾ alle aufklappen" : "▸ alle zuklappen"}</button></div>${beauftragt.map(zeile).join("")}` : ""}
    ${angebote.length ? `<div class="kp-gruppe">Angebote / Anfragen · geplante Ausführung</div>${angebote.map(zeile).join("")}` : ""}
    ${auftraege.length ? "" : `<div class="leer">Keine offenen Aufträge.</div>`}
  </div>
  <p class="hinweis">Ziehen in einer leeren Zeile legt einen Termin an. Balken verschieben oder an den Enden in der Länge ändern. Klick öffnet den Termin. Schraffiert = vorgemerkter (reservierter) Ausführungszeitraum eines Angebots; sobald der Auftrag erteilt ist, wird er voll als „geplant“ gezeigt. Unter dem Auftrag: Ist = gebuchte Stunden, Plan = Stunden der Termine, Soll = kalkulierte Stunden. Der helle Strich im Balken zeigt, wie viel vom Termin schon gebucht ist.</p>`;
  planungBinden(ziel, von, tw, tage);
  const neu = () => { try { localStorage.setItem("kal_zu", JSON.stringify([...KAL.zu])); } catch (e) {} planungZeichnen(von, bis); };
  $$("[data-zu]", ziel).forEach(b => b.onclick = ev => { ev.stopPropagation(); const id = +b.dataset.zu; KAL.zu.has(id) ? KAL.zu.delete(id) : KAL.zu.add(id); neu(); });
  $$("[data-zualle]", ziel).forEach(b => b.onclick = () => { beauftragt.forEach(a => b.dataset.zualle === "zu" ? KAL.zu.add(a.id) : KAL.zu.delete(a.id)); neu(); });
}

function planungBinden(ziel, von, tw, tage) {
  const d = KAL.daten;
  $$(".kp-b[data-abw]", ziel).forEach(el => el.onclick = () => { if (darf("personal")) location.hash = "#/personal/abwesenheit"; });
  const tagAus = (flaeche, clientX) => Math.max(0, Math.min(tage - 1, Math.floor((clientX - flaeche.getBoundingClientRect().left) / tw)));
  // Neue Termine aufziehen
  $$(".kp-zeile:not(.kp-ext) .kp-flaeche", ziel).forEach(fl => {
    fl.onpointerdown = ev => {
      if (ev.target.closest(".kp-b") || ev.button !== 0 || !termineAendern()) return;
      ev.preventDefault();
      const zeileEl = fl.closest(".kp-zeile"), aid = zeileEl.dataset.a ? +zeileEl.dataset.a : null;
      const start = tagAus(fl, ev.clientX);
      const sel = document.createElement("div"); sel.className = "kp-sel"; fl.appendChild(sel);
      const zeig = e2 => { const t = tagAus(fl, e2.clientX), a = Math.min(start, t), b = Math.max(start, t); sel.style.left = a * tw + "px"; sel.style.width = (b - a + 1) * tw + "px"; return [a, b]; };
      let ber = zeig(ev);
      const move = e2 => { ber = zeig(e2); };
      const up = async () => {
        window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up);
        const [a, b] = ber; const vonS = iso(plusTage(von, a)), bisS = iso(plusTage(von, b));
        const auf = aid ? d.auftraege.find(x => x.id === aid) : null;
        if (auf && auf.angebot) {
          const wahl = await modal(`${auf.nummer} · ${auf.bezeichnung}`, `<p>Der Auftrag ist noch im Status „${esc(auf.status)}“. Was soll für ${datum(vonS)} – ${datum(bisS)} eingetragen werden?</p>
            <div class="zeile"><label>Eintrag</label><div><select name="w"><option value="plan">Geplanter Ausführungszeitraum (für das Angebot)</option><option value="termin">Termin (z. B. Aufmaß)</option></select></div></div>`, "Weiter");
          if (!wahl) { sel.remove(); return; }
          if (wahl.w === "plan") { await api("auftraege/" + aid, {method: "PUT", body: {plan_von: vonS, plan_bis: bisS}}); toast("Zeitraum eingetragen"); return neuLaden(); }
        }
        const ok = await terminDialog({von: vonS, bis: bisS, auftrag_id: aid, typ: auf && !auf.angebot ? "Fertigung" : (aid ? "Aufmaß" : "Sonstiges")});
        if (!ok) sel.remove();
      };
      window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
    };
  });
  // Balken verschieben / Länge ändern
  $$(".kp-b[data-t], .kp-b[data-plan]", ziel).forEach(b => {
    b.onpointerdown = ev => {
      if (ev.button !== 0) return;
      ev.preventDefault(); ev.stopPropagation();
      if (!termineAendern()) { const tt = b.dataset.t ? d.termine.find(x => x.id === +b.dataset.t) : null; if (tt) terminAnsehen(tt); return; }
      const modus = ev.target.classList.contains("l") ? "l" : ev.target.classList.contains("r") ? "r" : "m";
      const t = b.dataset.t ? d.termine.find(x => x.id === +b.dataset.t) : null;
      const a = b.dataset.plan ? d.auftraege.find(x => x.id === +b.dataset.plan) : null;
      const orig = t ? {von: t.von, bis: t.bis} : {von: a.plan_von, bis: a.plan_bis || a.plan_von};
      const x0 = ev.clientX, l0 = b.offsetLeft, w0 = b.offsetWidth;
      let delta = 0, bewegt = false;
      b.classList.add("zieht");
      const move = e2 => {
        delta = Math.round((e2.clientX - x0) / tw);
        if (Math.abs(e2.clientX - x0) > 3) bewegt = true;
        if (modus === "m") b.style.left = l0 + delta * tw + "px";
        if (modus === "r") b.style.width = Math.max(tw - 2, w0 + delta * tw) + "px";
        if (modus === "l") { const dl = Math.min(delta, Math.round(w0 / tw) - 1); b.style.left = l0 + dl * tw + "px"; b.style.width = w0 - dl * tw + "px"; }
      };
      const up = async () => {
        window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up);
        b.classList.remove("zieht");
        if (!bewegt || !delta) {
          if (!bewegt) { if (t) terminBearbeiten(t); else location.hash = `#/auftrag/${a.id}`; }
          else neuLaden();
          return;
        }
        let nv = orig.von, nb = orig.bis;
        const s = n => iso(plusTage(vonIso(n), delta));
        if (modus === "m") { nv = s(orig.von); nb = s(orig.bis); }
        if (modus === "r") { nb = s(orig.bis); if (nb < nv) nb = nv; }
        if (modus === "l") { nv = s(orig.von); if (nv > nb) nv = nb; }
        try {
          if (t) { const erg = await api("termine/" + t.id, {method: "PUT", body: {von: nv, bis: nb}}); if (erg && erg.warnung) toast("Hinweis: " + erg.warnung, true); }
          else await api("auftraege/" + a.id, {method: "PUT", body: {plan_von: nv, plan_bis: nb}});
          toast(`${datum(nv)}${nb !== nv ? " – " + datum(nb) : ""}`);
        } catch (e) { toast(e.message, true); }
        neuLaden();
      };
      window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
    };
  });
}

// ---------- Monat & Woche ----------
function eintraegeAm(s) {
  const d = KAL.daten, out = [];
  for (const e of d.extern) if (e.von <= s && e.bis >= s) out.push({art: "ext", sort: e.ganztags ? "0" : "1" + e.zeit_von, html: `<div class="km-e ext" style="--f:${e.farbe}" title="${esc(e.quelle + ": " + e.titel + (e.ort ? " · " + e.ort : ""))}">${e.zeit_von ? `<b>${e.zeit_von}</b> ` : ""}${esc(e.titel)}</div>`});
  for (const f of d.feiertage || []) if (f.datum === s) out.push({art: "ft", sort: "00", html: `<div class="km-e ext ft" style="--f:#b5ab9e" title="Feiertag">${esc(f.name)}</div>`});
  for (const a of d.abwesenheiten || []) if (a.von <= s && a.bis >= s) out.push({art: "abw", sort: "01" + a.kuerzel, html: `<div class="km-e ext${a.beantragt ? " beantr" : ""}" ${a.id ? `data-abw="${a.id}"` : ""} style="--f:${ABW_FARBE[a.art] || "#8f99a8"}" title="${esc(abwTip(a))}">${esc(abwText(a))}</div>`});
  for (const t of d.termine) if (t.von <= s && t.bis >= s) out.push({art: "t", sort: (t.zeit_von ? "1" + t.zeit_von : "0") + t.typ, html: `<div class="km-e${t.erledigt ? " erl" : ""}" data-t="${t.id}" style="--f:${typFarbe(t.typ)}" title="${esc((t.auftragsnr ? t.auftragsnr + " " + (t.bezeichnung || "") + "\n" : "") + (t.notiz || ""))}">${t.zeit_von ? `<b>${t.zeit_von}</b> ` : ""}${esc(t.typ)}${t.kunde ? " · " + esc(t.kunde) : ""}${t.titel ? " · " + esc(t.titel) : ""}</div>`});
  for (const a of d.auftraege) if (a.plan_von && a.plan_von <= s && (a.plan_bis || a.plan_von) >= s && (KAL.zeigeAngebote || !a.angebot))
    out.push({art: "p", sort: "2", html: `<div class="km-e plan${a.angebot ? "" : " fest"}" data-a="${a.id}" title="${a.angebot ? "Vorgemerkter Ausführungszeitraum (Angebot)" : "Geplanter Ausführungszeitraum (beauftragt)"}">${esc(a.nummer)} ${esc(a.kunde || "")} (${a.angebot ? "vorgemerkt" : "geplant"})</div>`});
  return out.sort((a, b) => a.sort.localeCompare(b.sort)).map(x => x.html).join("");
}
function kalBinden(ziel) {
  $$("[data-t]", ziel).forEach(el => el.onclick = ev => { ev.stopPropagation(); terminBearbeiten(KAL.daten.termine.find(t => t.id === +el.dataset.t)); });
  $$("[data-a]", ziel).forEach(el => el.onclick = ev => { ev.stopPropagation(); location.hash = `#/auftrag/${el.dataset.a}`; });
  $$("[data-abw]", ziel).forEach(el => el.onclick = ev => { ev.stopPropagation(); if (darf("personal")) location.hash = "#/personal/abwesenheit"; });
  $$("[data-tag]", ziel).forEach(el => el.ondblclick = () => terminDialog({von: el.dataset.tag, bis: el.dataset.tag}));
}
function monatZeichnen(von) {
  const heuteIso = iso(new Date()), m = KAL.start.getMonth();
  let html = `<div class="km">${WT.map(t => `<div class="km-k">${t}</div>`).join("")}`;
  for (let i = 0; i < 42; i++) {
    const t = plusTage(von, i), s = iso(t);
    html += `<div class="km-tag${t.getMonth() !== m ? " fremd" : ""}${(t.getDay() + 6) % 7 > 4 ? " we" : ""}${s === heuteIso ? " heute" : ""}" data-tag="${s}">
      <div class="km-n">${t.getDate()}${(t.getDay() + 6) % 7 === 0 ? `<span>KW ${kw(t)}</span>` : ""}</div>${eintraegeAm(s)}</div>`;
  }
  $("#kal").innerHTML = html + `</div>${termineAendern() ? `<p class="hinweis">Doppelklick auf einen Tag legt einen Termin an.</p>` : ""}`;
  kalBinden($("#kal"));
}
function wocheZeichnen(von) {
  const heuteIso = iso(new Date());
  $("#kal").innerHTML = `<div class="kw7">${Array.from({length: 7}, (_, i) => { const t = plusTage(von, i), s = iso(t);
    return `<div class="kw-tag${s === heuteIso ? " heute" : ""}${i > 4 ? " we" : ""}" data-tag="${s}"><div class="km-n">${WT[i]} ${t.getDate()}.${t.getMonth() + 1}.</div>${eintraegeAm(s) || `<div class="hinweis">frei</div>`}</div>`; }).join("")}</div>
    ${termineAendern() ? `<p class="hinweis">Doppelklick auf einen Tag legt einen Termin an.</p>` : ""}`;
  kalBinden($("#kal"));
}

// ---------- Planung im Auftrag ----------
async function auftragPlanung(ziel, a) {
  const termine = await api("termine?auftrag=" + a.id);
  ziel.innerHTML = `
    <div class="zeile"><label>Ausführung geplant</label><div><input type="date" id="plV" value="${esc(a.plan_von || "")}"><span style="padding-top:5px">bis</span><input type="date" id="plB" value="${esc(a.plan_bis || "")}"><a class="btn" href="#/kalender/planung/${a.plan_von || iso(new Date())}" style="flex:0 0 auto">In Planung zeigen</a></div></div>
    <div class="zeile"><label>Termine</label><div style="display:block;padding:6px 10px">
      ${termine.map(t => `<div class="km-e" data-tid="${t.id}" style="--f:${typFarbe(t.typ)};display:inline-block;margin:0 6px 4px 0;cursor:pointer">${esc(t.typ)} ${datum(t.von)}${t.bis !== t.von ? "–" + datum(t.bis) : ""}${t.titel ? " · " + esc(t.titel) : ""} · ${n2(t.gebucht, 1)}/${n2(t.geplant, 0)} h${t.erledigt ? " ✓" : ""}</div>`).join("") || `<span class="hinweis">noch keine</span>`}
      ${termineAendern() ? `<button class="btn" id="tNeuA" type="button">+ Termin</button>` : ""}</div></div>`;
  const sp = () => api("auftraege/" + a.id, {method: "PUT", body: {plan_von: $("#plV").value, plan_bis: $("#plB").value || $("#plV").value}}).then(r => { Object.assign(a, r); toast("Zeitraum gespeichert"); });
  $("#plV").onchange = () => { if (!$("#plB").value || $("#plB").value < $("#plV").value) $("#plB").value = $("#plV").value; sp(); };
  $("#plB").onchange = sp;
  if ($("#tNeuA")) $("#tNeuA").onclick = () => terminDialog({von: a.plan_von || iso(new Date()), bis: a.plan_bis || a.plan_von || iso(new Date()), auftrag_id: a.id, typ: "Fertigung"});
  $$("[data-tid]", ziel).forEach(el => el.onclick = () => terminBearbeiten(termine.find(t => t.id === +el.dataset.tid)));
}

// ---------- Kalender-Einstellungen ----------
function kalenderVorgabe(z) {
  const gk = (E.google_kalender || []).map(k => ({...k}));
  const typen = (E.termin_typen || []).map(t => ({...t}));
  const sp = speicherer("einstellungen", r => { E = {...E, ...r}; });
  const zeichnen = () => {
    z.innerHTML = `<div class="titel"><h2>Kalender</h2><span class="speicher"></span></div>
      <div class="kachel" style="margin-bottom:12px"><h4>Google Kalender einbinden</h4>
        <p class="hinweis" style="margin-top:0">In Google Kalender am PC: Zahnrad › Einstellungen › links den eigenen Kalender anklicken › ganz unten <b>„Privatadresse im iCal-Format“</b> kopieren und hier einfügen. Die Adresse ist geheim, sie gibt Lesezugriff auf den Kalender. Die Termine werden nur angezeigt, nicht verändert.</p>
        <table class="liste"><tr><th>Name</th><th>Privatadresse (iCal)</th><th>Farbe</th><th>aktiv</th><th></th></tr>
        ${gk.map((k, i) => `<tr><td><input data-g="${i}" data-k="name" value="${esc(k.name)}" style="width:140px"></td>
          <td><input data-g="${i}" data-k="url" value="${esc(k.url)}" style="width:100%;min-width:300px" placeholder="https://calendar.google.com/calendar/ical/…/private-…/basic.ics"></td>
          <td><input type="color" data-g="${i}" data-k="farbe" value="${esc(k.farbe || "#4f7cba")}"></td>
          <td><input type="checkbox" data-g="${i}" data-k="aktiv" ${k.aktiv !== false ? "checked" : ""}></td>
          <td style="white-space:nowrap"><button class="btn" data-test="${i}">Testen</button><button class="btn rot" data-gdel="${i}" title="Kalender entfernen">✕</button></td></tr>`).join("")}</table>
        <button class="btn" id="gPlus" style="margin-top:6px">+ Kalender</button></div>
      <div class="kachel" style="margin-bottom:12px"><h4>Terminarten</h4>
        <table class="liste"><tr><th>Name</th><th>Farbe</th><th></th></tr>
        ${typen.map((t, i) => `<tr><td><input data-ty="${i}" data-k="name" value="${esc(t.name)}"></td><td><input type="color" data-ty="${i}" data-k="farbe" value="${esc(t.farbe)}"></td><td><button class="btn rot" data-tdel="${i}">✕</button></td></tr>`).join("")}</table>
        <button class="btn" id="tyPlus" style="margin-top:6px">+ Terminart</button></div>
      <div class="form">
        ${zeile("Stunden je Arbeitstag", `<input id="tStd" class="zahl" style="width:70px" value="${n2(+E.tagesstunden || 8, 1)}"> h <span class="hinweis" style="padding-top:5px">für verplante Stunden, wenn im Termin keine eingetragen sind</span>`, true)}
        ${zeile("Angebot", `<label class="pchk"><input type="checkbox" id="zDr" ${E.zeitraum_drucken !== false ? "checked" : ""}> geplanten Ausführungszeitraum als KW auf Angebot, KV und Auftragsbestätigung drucken</label>`, true)}
        ${zeile("Status „Angebot“", `<input id="stAng" value="${esc((E.status_angebot || []).join(", "))}"><span class="hinweis" style="padding-top:5px">Aufträge mit diesem Status gelten als noch nicht erteilt</span>`, true)}
        ${zeile("Status „Ende“", `<input id="stEnde" value="${esc((E.status_ende || []).join(", "))}"><span class="hinweis" style="padding-top:5px">werden in der Planung ausgeblendet</span>`, true)}
      </div>`;
    $$("[data-g]", z).forEach(el => el.addEventListener(el.type === "checkbox" || el.type === "color" ? "change" : "input", () => { gk[+el.dataset.g][el.dataset.k] = el.type === "checkbox" ? el.checked : el.value.trim(); sp.setze("google_kalender", gk); }));
    $$("[data-gdel]", z).forEach(b => b.onclick = () => { gk.splice(+b.dataset.gdel, 1); sp.setze("google_kalender", gk, true); zeichnen(); });
    $("#gPlus").onclick = () => { gk.push({name: gk.length ? "Kalender " + (gk.length + 1) : "Google", url: "", farbe: "#4f7cba", aktiv: true}); sp.setze("google_kalender", gk, true); zeichnen(); };
    $$("[data-test]", z).forEach(b => b.onclick = async () => {
      b.textContent = "…";
      try { const r = await api("kalendertest", {method: "POST", body: {url: gk[+b.dataset.test].url}}); toast(`Kalender gelesen: ${r.anzahl} Termine in den nächsten Wochen`); }
      catch (e) { toast(e.message, true); }
      b.textContent = "Testen";
    });
    $$("[data-ty]", z).forEach(el => el.addEventListener(el.type === "color" ? "change" : "input", () => { typen[+el.dataset.ty][el.dataset.k] = el.value; sp.setze("termin_typen", typen); }));
    $$("[data-tdel]", z).forEach(b => b.onclick = () => { typen.splice(+b.dataset.tdel, 1); sp.setze("termin_typen", typen, true); zeichnen(); });
    $("#tyPlus").onclick = () => { typen.push({name: "Neu", farbe: "#888888"}); sp.setze("termin_typen", typen, true); zeichnen(); };
    $("#tStd").oninput = e => sp.setze("tagesstunden", zahlEin(e.target.value));
    $("#zDr").onchange = e => sp.setze("zeitraum_drucken", e.target.checked, true);
    $("#stAng").oninput = e => sp.setze("status_angebot", e.target.value.split(",").map(s => s.trim()).filter(Boolean));
    $("#stEnde").oninput = e => sp.setze("status_ende", e.target.value.split(",").map(s => s.trim()).filter(Boolean));
  };
  zeichnen();
}

// ---------- Kapazität: je Mitarbeiter und Woche verfügbar / verplant, Arbeitsvorrat ----------
function kapazitaetHtml(k, {von, tage, tw, raster, heuteX, balken, sichtbar, termine}) {
  if (!k || !(k.mitarbeiter || []).length) return "";
  const wochen = [], start = von;
  for (let i = 0; i < tage; ) {
    const t = plusTage(start, i), wt = (t.getDay() + 6) % 7, n = Math.min(7 - wt, tage - i);
    wochen.push({mo: iso(plusTage(t, -wt)), left: i * tw, w: n * tw}); i += n;
  }
  const zelle = (w, v, p) => {
    if (!v && !p) return `<div class="kk-z" style="left:${w.left}px;width:${w.w - 2}px"></div>`;
    const q = v ? p / v : 2, farbe = q > 1.0001 ? "var(--rot)" : q >= 0.8 ? "#c9a227" : "var(--gruen)";
    return `<div class="kk-z" style="left:${w.left}px;width:${w.w - 2}px" title="verfügbar ${n2(v, 1)} h · verplant ${n2(p, 1)} h · frei ${n2(v - p, 1)} h">
      <i style="width:${Math.min(100, v ? p / v * 100 : 100)}%;background:${farbe}"></i><span>${w.w >= 60 ? `${n2(p, 0)}/${n2(v, 0)} h` : n2(v - p, 0)}</span></div>`;
  };
  const sicht = termine.filter(t => sichtbar(t.von, t.bis) && (KAL.zeigeEnde || !t.erledigt));
  const inhalt = t => `${t.auftragsnr ? `<b>${esc(t.auftragsnr)}</b> ${esc(t.kunde || "")} · ` : ""}${esc(t.typ)}${t.titel ? " · " + esc(t.titel) : ""}`;
  const tip = t => `${t.auftragsnr ? t.auftragsnr + " " + (t.kunde || "") + " · " + (t.bezeichnung || "") + "\n" : ""}${t.typ}${t.titel ? ": " + t.titel : ""} · ${datum(t.von)}${t.bis !== t.von ? " – " + datum(t.bis) : ""}${t.zeit_von ? " " + t.zeit_von + "–" + (t.zeit_bis || "") : ""} · ${n2(t.geplant || 0, 1)} h${maKurz(t) ? " · " + maKurz(t) : ""}${t.notiz ? "\n" + t.notiz : ""}`;
  const reihe = (label, bez, streifen, ts, cls = "") => {
    const items = ts.map(t => ({von: t.von, bis: t.bis, t, farbe: typFarbe(t.typ), tip: tip(t)}));
    const n = items.length ? lanes(items) : 0;
    return `<div class="kp-zeile kp-ext kk ${cls}"><div class="kp-label">${label}<div class="kp-bez">${bez}</div></div>
      <div class="kp-flaeche" style="height:${30 + n * 26 + (n ? 4 : 0)}px;width:${tage * tw}px">${raster}${heuteX}${streifen}
        ${items.map(it => balken(it, "termin" + (it.t.erledigt ? " erl" : ""), inhalt(it.t), `data-t="${it.t.id}"`, 30)).join("")}</div></div>`;
  };
  const zeilen = k.mitarbeiter.map(m => reihe(`<b>${esc(m.name)}</b>`, "Einsatz · verplant/verfügbar je Woche",
    wochen.map(w => { const x = m.wochen[w.mo] || {}; return zelle(w, x.verfuegbar || 0, x.verplant || 0); }).join(""),
    sicht.filter(t => maVon(t).includes(m.id)))).join("");
  const ohneT = sicht.filter(t => !maVon(t).some(id => k.mitarbeiter.some(m => m.id === id)));
  const oz = k.ohne_zuordnung || {};
  const ohne = ohneT.length || Object.values(oz).some(v => v > 0) ? reihe(`<b title="Termin anklicken und im Dialog Mitarbeiter zuordnen">Nicht zugeordnet</b>`, "Termine ohne Mitarbeiter",
    wochen.map(w => { const h = oz[w.mo] || 0; return h ? `<div class="kk-z kk-oz" style="left:${w.left}px;width:${w.w - 2}px" title="${n2(h, 1)} h in Terminen ohne Mitarbeiter. Diese Stunden sind keinem Mitarbeiter zugerechnet und fehlen in dessen Auslastung."><span>${n2(h, 0)} h offen</span></div>` : ""; }).join(""),
    ohneT, "kk-ohne") : "";
  const vr = k.vorrat || [];
  const kopf = `<div class="kp-gruppe kk-kopf"><details><summary>Kapazität · Arbeitsvorrat ${n2(k.vorrat_rest || 0, 0)} h${k.reichweite_wochen != null ? ` ≈ ${n2(k.reichweite_wochen, 1)} Wochen` : ""} · davon unverplant ${n2(k.vorrat_offen || 0, 0)} h · frei in den nächsten 8 Wochen ${n2(k.frei_8w || 0, 0)} h</summary>
    ${vr.length ? `<table class="liste" style="margin:6px 0;max-width:760px"><tr><th>Auftrag</th><th class="r">Rest h</th><th class="r">in Terminen</th><th class="r">unverplant</th></tr>
      ${vr.map(a => `<tr><td><a href="#/auftrag/${a.id}">${esc(a.nummer)}</a> ${esc(a.kunde || "")} · ${esc(kurz(a.bezeichnung || "", 40))}</td><td class="r">${n2(a.rest, 1)}</td><td class="r">${n2(a.verplant, 1)}</td><td class="r"><b style="color:${a.offen > 0.05 ? "var(--rot)" : "inherit"}">${n2(a.offen, 1)}</b></td></tr>`).join("")}</table>` : `<div class="hinweis" style="margin:6px 0">Kein Arbeitsvorrat aus beauftragten Aufträgen.</div>`}
    <div class="hinweis" style="font-weight:400">Rest = kalkulierte minus gebuchte Stunden der beauftragten Aufträge; in Terminen = Stunden der Termine ab heute; Reichweite = Rest / verfügbare Stunden je Woche (Durchschnitt der nächsten 8 Wochen). Verfügbar = Arbeitszeitmodell der Mitarbeiter ohne Feiertage und Abwesenheiten.</div></details></div>`;
  return kopf + zeilen + ohne;
}
