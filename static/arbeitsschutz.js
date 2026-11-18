"use strict";
// =====================================================================
//  Jahresring – Arbeitsschutz: Gefährdungsbeurteilungen, Betriebsanweisungen, Unterweisungen,
//  Gefahrstoffe & Datenblätter, Erste Hilfe & Notfall, Beauftragte & Nachweise
// =====================================================================
let AS_V = null;
async function asVorlagen() { if (!AS_V) AS_V = await api("arbeitsschutz/vorlagen"); return AS_V; }
const AS_REITER = [["Übersicht", "uebersicht"], ["Gefährdungsbeurteilungen", "gb"], ["Betriebsanweisungen", "ba"], ["Unterweisungen", "unterweisungen"],
  ["Gefahrstoffe", "gefahrstoffe"], ["Erste Hilfe & Notfall", "notfall"], ["Beauftragte & Nachweise", "nachweise"]];
const asDarf = () => darf("arbeitsschutz", 2);
const asZeichen = (code, h = 26) => `<img src="/arbeitsschutz/zeichen/${esc(code)}.png" alt="${esc(code)}" title="${esc(code)}" style="height:${h}px;width:${h}px;vertical-align:middle">`;
const asStatus = s => `<span class="as-st as-st-${esc(s)}">${esc({entwurf: "Entwurf", gueltig: "gültig", ueberarbeitung: "in Überarbeitung", archiv: "archiviert", offen: "offen", abgeschlossen: "abgeschlossen"}[s] || s)}</span>`;
// Bildtafeln (PDF) im Programm zeigen – unabhängig davon, ob der Browser bzw. das App-Fenster PDFs selbst anzeigt.
// Strg-/Cmd-Klick öffnet die Datei wie gewohnt in einem eigenen Fenster.
document.addEventListener("click", e => {
  const a = e.target.closest && e.target.closest("a[data-tafel]");
  if (!a || e.ctrlKey || e.metaKey || e.shiftKey) return;
  e.preventDefault();
  asPdfZeigen(a.getAttribute("href"), a.dataset.tafel || "Bildtafel");
});
async function asPdfZeigen(url, titel) {
  const hg = document.createElement("div");
  hg.className = "modal-hg as-tafel-hg";
  hg.innerHTML = `<div class="modal as-tafel"><div class="as-tafel-kopf"><h3>${esc(titel)}</h3>
    <a class="btn" href="${esc(url)}" target="_blank">In eigenem Fenster</a><a class="btn" href="${esc(url)}" download>Herunterladen</a><button class="btn prim" data-zu>Schließen</button></div>
    <div class="as-tafel-inhalt"><div class="hinweis">Bildtafel wird geladen …</div></div></div>`;
  document.body.appendChild(hg);
  const zu = () => { hg.remove(); document.removeEventListener("keydown", taste); };
  const taste = ev => { if (ev.key === "Escape") zu(); };
  document.addEventListener("keydown", taste);
  hg.onclick = ev => { if (ev.target === hg || ev.target.closest("[data-zu]")) zu(); };
  const box = $(".as-tafel-inhalt", hg);
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`Die Bildtafel wurde nicht gefunden (${r.status}).`);
    const daten = new Uint8Array(await r.arrayBuffer());
    if (!window.pdfjsLib) {
      await skriptLaden("/pdfjs/pdf.min.js");
      window.pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdfjs/pdf.worker.min.js";
    }
    const doc = await window.pdfjsLib.getDocument({data: daten, isEvalSupported: false}).promise;
    const breite = Math.max(280, box.clientWidth - 8), dpr = window.devicePixelRatio || 1;
    const neu = [];
    for (let n = 1; n <= doc.numPages; n++) {
      const seite = await doc.getPage(n);
      const v0 = seite.getViewport({scale: 1}), sk = breite / v0.width, vp = seite.getViewport({scale: sk * dpr});
      const c = document.createElement("canvas");
      c.width = vp.width; c.height = vp.height;
      c.style.cssText = `display:block;width:${breite}px;height:${v0.height * sk}px;margin:0 auto 10px;background:#fff`;
      await seite.render({canvasContext: c.getContext("2d"), viewport: vp}).promise;
      neu.push(c);
    }
    if (document.body.contains(hg)) box.replaceChildren(...neu);
  } catch (err) {
    box.innerHTML = `<div class="hinweis">${esc(err.message || "Die Bildtafel konnte nicht angezeigt werden.")} Über „In eigenem Fenster“ oder „Herunterladen“ lässt sie sich trotzdem öffnen.</div>`;
  }
}
function asKopf(aktiv, kontext = "", zurueck = null, reiter2 = null) {
  kopf({krumen: [["Arbeitsschutz", "#/arbeitsschutz"]], kontext, zurueck, reiter2,
    reiter: AS_REITER.map(([l, s]) => [l, `#/arbeitsschutz/${s}`, s === aktiv])});
}
function asDebounce(fn, ms = 600) {
  let t = null, letzte = null;
  const f = (...a) => { clearTimeout(t); letzte = a; t = setTimeout(() => { t = null; letzte = null; fn(...a); }, ms); };
  f.jetzt = (...a) => { clearTimeout(t); t = null; letzte = null; return fn(...a); };
  // noch ausstehendes Speichern sofort ausführen (z. B. bevor eine Vorlage ergänzt oder die Seite verlassen wird)
  f.flush = async () => { if (t) { clearTimeout(t); t = null; const a = letzte; letzte = null; return fn(...a); } };
  return f;
}
function asSpeicherStatus(t, k = "") { const s = $(".speicher"); if (s) { s.textContent = t; s.className = "speicher " + k; } }
// dateiAlsBase64() steht in eingang.js (gemeinsam genutzt)

async function ansichtArbeitsschutz(teil = "uebersicht", id, sub) {
  if (teil === "gb") return id ? asGbDetail(+id) : asGbListe();
  if (teil === "ba") return id ? asBaDetail(+id) : asBaListe();
  if (teil === "unterweisungen") return asUnterweisungen(id || "faellig");
  if (teil === "unterweisung" && id) return asUnterweisungDetail(+id);
  if (teil === "thema" && id) return asThemaDetail(+id);
  if (teil === "gefahrstoffe") return asGefahrstoffe();
  if (teil === "notfall") return asNotfall();
  if (teil === "nachweise") return asNachweise();
  return asUebersicht();
}

// ---------------------------------------------------------------------
//  Unterschrift am Tablet (Finger oder Stift)
// ---------------------------------------------------------------------
function unterschriftDialog({titel = "Unterschreiben", text = "", name = "", nameFest = false, knopf = "Unterschreiben"} = {}) {
  return new Promise(res => {
    const hg = document.createElement("div");
    hg.className = "modal-hg";
    hg.innerHTML = `<div class="modal as-sig"><h3>${esc(titel)}</h3>${text ? `<div class="as-sig-text">${text}</div>` : ""}
      <label class="hinweis">Name</label><input id="sgName" value="${esc(name)}" ${nameFest ? "readonly" : ""} style="width:100%">
      <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-top:10px"><span class="hinweis">Hier mit dem Finger oder Stift unterschreiben</span><button class="btn" id="sgNeu">Löschen</button></div>
      <canvas class="mb-pad" id="sgPad"></canvas>
      <div class="knoepfe"><button class="btn" data-x="0">Abbrechen</button><button class="btn prim" data-x="1">✍ ${esc(knopf)}</button></div></div>`;
    document.body.appendChild(hg);
    const pad = unterschriftPad($("#sgPad", hg));
    $("#sgNeu", hg).onclick = () => pad.loeschen();
    const zu = ok => {
      if (ok) {
        const n = $("#sgName", hg).value.trim();
        if (!n) { toast("Bitte den Namen eintragen.", true); return; }
        if (pad.leer()) { toast("Bitte im Feld unterschreiben.", true); return; }
        const erg = {name: n, png: pad.png(), geraet: navigator.userAgent.slice(0, 180)};
        hg.remove(); res(erg); return;
      }
      hg.remove(); res(null);
    };
    $$("[data-x]", hg).forEach(b => b.onclick = () => zu(b.dataset.x === "1"));
  });
}

// ---------------------------------------------------------------------
//  Übersicht
// ---------------------------------------------------------------------
async function asUebersicht() {
  asKopf("uebersicht");
  const z = $("#inhalt");
  const d = await api("arbeitsschutz/uebersicht");
  const farbe = {rot: "var(--rot)", gelb: "#c9a227", info: "#7a8a99"};
  const symbol = ok => ok === true ? `<span style="color:var(--gruen);font-weight:700">✓</span>` : ok === false ? `<span style="color:var(--rot);font-weight:700">✗</span>` : `<span class="hinweis">–</span>`;
  z.innerHTML = `<div class="titel"><h2>Arbeitsschutz</h2><span class="hinweis">${d.bedarf.beschaeftigte} Beschäftigte</span></div>
    ${E.start_arbeitsschutz === false && darf("start") && darf("arbeitsschutz", 2) ? `<p class="hinweis" id="asStartAus" style="margin:0 0 10px">Die Erinnerungen auf der Startseite sind ausgeschaltet${ICH.rechte.inhaber ? ` (<a href="#/einstellungen/programm">Einstellungen › Programm</a>)` : ""}. Fällige Punkte stehen nur hier.</p>` : ""}
    <div class="as-zwei">
      <section class="kachel"><h4>Zu erledigen</h4>
        ${d.punkte.length ? `<ul class="as-punkte">${d.punkte.map(p => `<li><span class="as-dot" style="background:${farbe[p.stufe]}"></span><a href="${p.link}">${esc(p.text)}</a></li>`).join("")}</ul>`
          : `<p style="margin:0">Alles erledigt. Die nächsten Termine erscheinen hier rechtzeitig.</p>`}
        ${d.zahlen.maschinen_ohne_gb.length && asDarf() ? `<div style="margin-top:12px"><b>Maschinen ohne Gefährdungsbeurteilung</b>
          <div class="as-chips" style="margin-top:6px">${d.zahlen.maschinen_ohne_gb.map(m => `<button class="btn" data-gbneu="${m.id}">＋ ${esc(m.bezeichnung)}</button>`).join("")}</div>
          <p class="hinweis" style="margin:6px 0 0">Ein Klick legt die Gefährdungsbeurteilung mit der passenden Vorlage der Berufsgenossenschaft an.</p></div>` : ""}
      </section>
      <section class="kachel"><h4>Grundpflichten</h4>
        <table class="as-pfl">${d.pflichten.map(p => `<tr><td>${symbol(p.ok)}</td><td><a href="${p.link}">${esc(p.text)}</a>${p.hinweis ? `<div class="hinweis">${esc(p.hinweis)}</div>` : ""}</td></tr>`).join("")}</table>
      </section>
    </div>
    <details class="kachel" style="margin-top:14px"><summary><b>So läuft der Arbeitsschutz im Programm</b></summary>
      <p>Einmal einrichten: Unter „Beauftragte &amp; Nachweise“ die Betreuung, die Arbeitsbereiche und die Ersthelfer eintragen, unter „Erste Hilfe &amp; Notfall“ den Aushang ausfüllen. Danach für jeden Arbeitsbereich und jede Maschine eine Gefährdungsbeurteilung aus der Vorlage der Berufsgenossenschaft anlegen, jede Maßnahme als vorhanden, umzusetzen oder entfallend markieren und am Tablet freigeben. Die psychische Belastung wird mit der Checkliste der Berufsgenossenschaft beurteilt.</p>
      <p>Für Maschinen und Gefahrstoffe entstehen die Betriebsanweisungen aus den Vorlagen bzw. aus dem Sicherheitsdatenblatt; sie stehen der Werkstatt im Auftrag, bei den Materialsummen und in der Stempeluhr zur Verfügung. Die Unterweisung findet vor Aufnahme der Tätigkeit und danach mindestens jährlich statt (Jugendliche halbjährlich); alle Teilnehmer unterschreiben direkt am Tablet oder in der Stempeluhr. Diese Übersicht meldet, was fällig wird.</p>
    </details>`;
  $$("[data-gbneu]").forEach(b => b.onclick = async () => {
    const ws = await api("arbeitsschutz/werkzeuge"); const w = ws.find(x => x.id === +b.dataset.gbneu);
    try { const g = await api("arbeitsschutz/gb", {method: "POST", body: {art: "maschine", werkzeug_ids: [w.id], vorlage: w.vorschlag || "", titel: w.vorschlag ? "" : w.bezeichnung}}); location.hash = `#/arbeitsschutz/gb/${g.id}`; }
    catch (e) { toast(e.message, true); }
  });
}

// ---------------------------------------------------------------------
//  Gefährdungsbeurteilungen
// ---------------------------------------------------------------------
async function asGbListe() {
  asKopf("gb");
  const z = $("#inhalt");
  const liste = await api("arbeitsschutz/gb");
  const zeichnen = () => {
    const t = tabelle("asgb", [
      {k: "nummer", t: "Nr."}, {k: "titel", t: "Titel", f: x => `<b>${esc(x.titel)}</b>${x.werkzeuge.length ? `<div class="hinweis">${x.werkzeuge.map(w => esc(w.bezeichnung)).join(", ")}</div>` : ""}`},
      {k: "art_name", t: "Art"}, {k: "bereich", t: "Bereich"}, {k: "status", t: "Status", f: x => asStatus(x.status)},
      {k: "stand", t: "Stand", f: x => datum(x.stand)}, {k: "naechste", t: "Nächste Prüfung", f: x => x.naechste ? `<span style="${x.naechste < heute() ? "color:var(--rot);font-weight:600" : ""}">${datum(x.naechste)}</span>` : ""},
      {k: "offen", t: "Maßnahmen offen", r: 1, f: x => x.offen.umsetzen ? `<span style="${x.offen.ueberfaellig ? "color:var(--rot);font-weight:600" : ""}">${x.offen.umsetzen}</span>` : x.offen.ungeprueft ? `<span class="hinweis">${x.offen.ungeprueft} ungeprüft</span>` : "–"},
    ], liste, {klick: x => location.hash = `#/arbeitsschutz/gb/${x.id}`, leer: "Noch keine Gefährdungsbeurteilung. Mit „Neue Gefährdungsbeurteilung“ beginnen – am besten mit einem Arbeitsbereich oder einer Maschine."});
    z.innerHTML = `<div class="titel"><h2>Gefährdungsbeurteilungen</h2>
      <div class="rechts">${asDarf() ? `<button class="btn prim" id="gbNeu">＋ Neue Gefährdungsbeurteilung</button><button class="btn" id="gbPsych">＋ Psychische Belastung</button>` : ""}</div></div>
      <p class="hinweis" style="margin-top:0">Je Arbeitsbereich, Maschine oder Tätigkeit eine Beurteilung. Grundlage sind die Vorlagen der Berufsgenossenschaft; jede Maßnahme wird geprüft und als vorhanden, umzusetzen oder entfallend markiert. Nach der Freigabe mit Unterschrift bleibt die Fassung unverändert gespeichert.</p>
      ${t.html}`;
    t.binden(zeichnen);
    if ($("#gbNeu")) $("#gbNeu").onclick = () => asGbNeu();
    if ($("#gbPsych")) $("#gbPsych").onclick = async () => {
      if (!await frage("Gefährdungsbeurteilung psychische Belastung anlegen?\n\nGrundlage ist die Checkliste der Berufsgenossenschaft (Teil I) mit den Maßnahmenbeispielen aus Teil II. Jede Aussage wird mit „trifft zu“ oder „trifft nicht zu“ beantwortet; bei zutreffenden Punkten werden Maßnahmen festgelegt.", {ok: "Anlegen"})) return;
      const g = await api("arbeitsschutz/gb", {method: "POST", body: {art: "psychisch", titel: "Psychische Belastung – alle Beschäftigten"}}); location.hash = `#/arbeitsschutz/gb/${g.id}`;
    };
  };
  zeichnen();
}

async function asGbNeu(vor = {}) {
  const [v, ws, org] = await Promise.all([asVorlagen(), api("arbeitsschutz/werkzeuge"), api("arbeitsschutz/organisation")]);
  const gruppen = v.gb_gruppen.map(g => `<optgroup label="${esc(g)}">${v.gb.filter(x => x.gruppe === g).map(x => `<option value="${esc(x.id)}">${esc(x.name)} (${x.anzahl})</option>`).join("")}</optgroup>`).join("");
  const erg = await modal("Neue Gefährdungsbeurteilung", `
    ${zeile("Art", `<select name="art">${Object.entries(v.gb_arten).filter(([k]) => k !== "psychisch").map(([k, l]) => `<option value="${k}" ${k === (vor.art || "bereich") ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`)}
    ${zeile("Maschine", `<select name="werkzeug"><option value="">–</option>${ws.map(w => `<option value="${w.id}" data-v="${esc(w.vorschlag)}">${esc(w.nummer)} ${esc(w.bezeichnung)}</option>`).join("")}</select>`)}
    ${zeile("Vorlage", `<select name="vorlage"><option value="">ohne Vorlage</option>${gruppen}</select>`)}
    ${zeile("Titel", `<input name="titel" placeholder="leer = Name der Vorlage">`)}
    ${zeile("Bereich", `<input name="bereich" list="asBereiche" value="${esc(vor.bereich || "")}"><datalist id="asBereiche">${org.organisation.bereiche.map(b => `<option>${esc(b)}</option>`).join("")}</datalist>`)}
    <p class="hinweis">Die Vorlagen „Alle Arbeitsplätze“ und „Arbeitsschutzorganisation“ decken die Grundlagen des Betriebs ab; je Maschine gibt es eine eigene Vorlage.</p>`, "Anlegen", hg => {
    const s = $("[name=werkzeug]", hg), vl = $("[name=vorlage]", hg), art = $("[name=art]", hg);
    s.onchange = () => { const o = s.selectedOptions[0]; if (o && o.dataset.v) vl.value = o.dataset.v; if (s.value) art.value = "maschine"; };
  });
  if (!erg) return;
  try {
    const g = await api("arbeitsschutz/gb", {method: "POST", body: {art: erg.art, titel: erg.titel, bereich: erg.bereich, vorlage: erg.vorlage, werkzeug_ids: erg.werkzeug ? [+erg.werkzeug] : []}});
    location.hash = `#/arbeitsschutz/gb/${g.id}`;
  } catch (e) { toast(e.message, true); }
}

const AS_MST = [["vorhanden", "✓", "vorhanden"], ["umsetzen", "!", "umsetzen"], ["entfaellt", "–", "entfällt"], ["offen", "?", "offen"]];
async function asGbDetail(id) {
  const [g0, v, ws] = await Promise.all([api("arbeitsschutz/gb/" + id), asVorlagen(), api("arbeitsschutz/werkzeuge")]);
  let g = g0;
  const ro = !asDarf() || g.status === "archiv";
  const psych = g.art === "psychisch";
  asKopf("gb", `Gefährdungsbeurteilung <b>${esc(g.nummer)}</b> · ${esc(g.titel)}`, "#/arbeitsschutz/gb");
  const z = $("#inhalt");
  const speichern = asDebounce(async body => {
    asSpeicherStatus("speichert …");
    try { const n = await api("arbeitsschutz/gb/" + id, {method: "PUT", body}); asSpeicherStatus("gespeichert ✓", "ok");
      const statusWar = g.status; g.status = n.status; g.pruefung = n.pruefung; g.offen = n.offen; kopfZeichnen(); if (statusWar !== n.status) toast("Geändert – die freigegebene Fassung gilt, bis die neue freigegeben ist."); }
    catch (e) { asSpeicherStatus("Fehler", "fehler"); toast(e.message, true); }
  }, 700);
  const zeilenSpeichern = () => speichern({zeilen: g.zeilen});
  const kopfZeichnen = () => {
    const k = $("#gbStatus"); if (!k) return;
    k.innerHTML = `${asStatus(g.status)}${g.stand ? ` · Stand ${datum(g.stand)}` : ""}${g.naechste ? ` · nächste Prüfung ${datum(g.naechste)}` : ""}`;
    const p = $("#gbPruef");
    if (p) p.innerHTML = g.status === "gueltig" ? "" : (g.pruefung || []).length
      ? `<div class="kachel as-hinweis"><b>Vor der Freigabe noch offen (${g.pruefung.length}):</b><ul>${g.pruefung.slice(0, 6).map(x => `<li>${esc(x)}</li>`).join("")}</ul>${g.pruefung.length > 6 ? `<span class="hinweis">… und ${g.pruefung.length - 6} weitere</span>` : ""}</div>`
      : `<div class="kachel as-hinweis ok">Alles bewertet – bereit zur Freigabe.</div>`;
  };
  const block = (zz, i) => {
    const ms = zz.m || [];
    const trifft = psych ? `<div class="as-jn"><button class="btn${zz.trifft === false ? " an" : ""}" data-tr="0" ${ro ? "disabled" : ""}>trifft nicht zu</button><button class="btn${zz.trifft === true ? " an rot" : ""}" data-tr="1" ${ro ? "disabled" : ""}>trifft zu</button>
      ${zz.auto ? `<span class="as-auto" title="Trifft die Beschreibung zu, besteht automatisch Handlungsbedarf">automatischer Handlungsbedarf</span>` : ""}</div>` : "";
    const zeigM = !psych || zz.trifft === true || ms.length;
    return `<div class="as-gbz" data-z="${i}">
      <div class="as-gbk">
        ${psych ? `<div class="as-psych-t">${esc(zz.g)}</div>${trifft}` : `<textarea data-g rows="1" ${ro ? "readonly" : ""}>${esc(zz.g)}</textarea>`}
        ${psych ? "" : `<select data-ri ${ro ? "disabled" : ""} title="Risiko ohne zusätzliche Maßnahmen">${optsKV([["", "Risiko"], ["gering", "gering"], ["mittel", "mittel"], ["hoch", "hoch"]], zz.risiko)}</select>`}
        ${ro || psych ? "" : `<button class="btn" data-alle title="Alle noch offenen Maßnahmen als vorhanden markieren">alle ✓</button><button class="aktion" data-zdel title="Gefährdung entfernen">${ic("loeschen")}</button>`}
      </div>
      ${zeigM ? `<table class="as-m">${ms.map((m, j) => `<tr data-m="${j}" class="as-m-${m.status}">
        <td><textarea data-t rows="1" ${ro ? "readonly" : ""}>${esc(m.t)}</textarea></td>
        <td><select data-a ${ro ? "disabled" : ""} title="technisch / organisatorisch / personenbezogen">${optsKV([["", "–"], ["T", "T"], ["O", "O"], ["P", "P"]], m.art)}</select></td>
        <td class="as-seg">${AS_MST.map(([s, sym, l]) => `<button class="${m.status === s ? "an " + s : ""}" data-s="${s}" title="${l}" ${ro ? "disabled" : ""}>${sym} ${l}</button>`).join("")}</td>
        <td>${ro ? "" : `<button class="aktion" data-mdel title="Maßnahme entfernen">${ic("loeschen")}</button>`}</td></tr>
        ${m.status === "umsetzen" || m.erledigt ? `<tr data-m="${j}" class="as-zus"><td colspan="4"><div class="as-wer">
          <label>wer <input data-w="wer" value="${esc(m.wer)}" ${ro ? "readonly" : ""}></label><label>bis <input type="date" data-w="bis" value="${esc(m.bis)}" ${ro ? "readonly" : ""}></label>
          <label>erledigt am <input type="date" data-w="erledigt" value="${esc(m.erledigt)}" ${ro ? "readonly" : ""}></label>
          <label title="Wirksamkeit der Maßnahme geprüft"><input type="checkbox" data-wk ${m.wirksam ? "checked" : ""} ${ro ? "disabled" : ""}> wirksam${m.wirksam && m.wirksam_am ? " (" + datum(m.wirksam_am) + ")" : ""}</label></div></td></tr>` : ""}`).join("")}</table>` : ""}
      ${ro || !zeigM ? "" : `<div class="as-mneu"><button class="btn" data-mneu>＋ Maßnahme</button>${psych && zz.hinweis ? `<button class="btn" data-hinw title="${esc(zz.hinweis)}">Maßnahmenbeispiel übernehmen</button><span class="hinweis as-beisp">${esc(zz.hinweis)}</span>` : ""}</div>`}
    </div>`;
  };
  const zeilenHtml = () => {
    let gr = null, out = "";
    g.zeilen.forEach((zz, i) => {
      if (psych && zz.gruppe !== gr) { gr = zz.gruppe; out += `<h3 class="as-gruppe">${esc(gr)}</h3>`; }
      out += block(zz, i);
    });
    return out || `<div class="leer">Noch keine Gefährdungen. Mit „Vorlage hinzufügen“ oder „Gefährdung hinzufügen“ beginnen.</div>`;
  };
  const zeichnen = () => {
    z.innerHTML = `<div class="titel"><h2>${esc(g.nummer)} ${esc(g.titel)}</h2><span class="speicher"></span>
      <div class="rechts"><a class="btn" href="/druck/arbeitsschutz/gb/${id}" target="_blank">Ansehen</a><a class="btn" href="/druck/arbeitsschutz/gb/${id}.pdf" target="_blank">📄 PDF</a>
        ${ICH.rechte.inhaber && g.status !== "archiv" ? `<button class="btn prim" id="gbFrei">✍ Freigeben</button>` : ""}
        ${asDarf() ? (g.status === "archiv" ? `<button class="btn" id="gbReakt">Wieder aufnehmen</button>` : g.fassungen.length ? `<button class="btn" id="gbArch">Archivieren</button>` : `<button class="btn pk rot" id="gbDel">${ic("loeschen")} Löschen</button>`) : ""}</div></div>
      <div id="gbStatus" class="hinweis" style="margin:-6px 0 10px"></div>
      <div class="form" id="gbF">
        ${zeile("Titel", `<input data-f="titel" value="${esc(g.titel)}" ${ro ? "readonly" : ""}>`)}
        ${zeile("Art", `<span style="padding-top:5px">${esc(g.art_name)}</span>`)}
        ${zeile("Arbeitsbereich", `<input data-f="bereich" value="${esc(g.bereich)}" ${ro ? "readonly" : ""}>`)}
        ${zeile("Prüfintervall", `<input data-f="intervall" value="${g.intervall}" style="flex:0 0 70px;text-align:right" ${ro ? "readonly" : ""}><span style="padding-top:5px">Monate</span>`)}
        ${zeile("Beteiligte", `<input data-f="beteiligte" value="${esc(g.beteiligte)}" placeholder="z. B. Inhaber, Mitarbeiter, Fachkraft für Arbeitssicherheit" ${ro ? "readonly" : ""}>`)}
        ${zeile("Mitgeltend", `<input data-f="mitgeltend" value="${esc(g.mitgeltend)}" placeholder="Betriebsanweisung, Bedienungsanleitung …" ${ro ? "readonly" : ""}>`)}
        ${psych ? "" : zeile("Maschinen", `<div class="as-chips" id="gbW">${ws.filter(w => w.art === "Stationäre Maschine" || g.werkzeug_ids.includes(w.id) || /maschine|säge|fräse|hobel|schleif|presse/i.test(w.bezeichnung)).map(w => `<label class="as-chip"><input type="checkbox" value="${w.id}" ${g.werkzeug_ids.includes(w.id) ? "checked" : ""} ${ro ? "disabled" : ""}> ${esc(w.bezeichnung)}</label>`).join("") || `<span class="hinweis">Keine Maschinen unter Lager › Werkzeuge</span>`}</div>`, true)}
        ${zeile("Bemerkung", `<textarea data-f="bemerkung" rows="2" ${ro ? "readonly" : ""}>${esc(g.bemerkung)}</textarea>`, true)}
      </div>
      <div id="gbPruef" style="margin-top:12px"></div>
      <div class="titel" style="margin-top:16px"><h3 style="margin:0">${psych ? "Checkliste psychische Belastung" : "Gefährdungen und Schutzmaßnahmen"}</h3>
        <div class="rechts">${ro || psych ? "" : `<select id="gbVorl" style="max-width:260px"><option value="">Vorlage hinzufügen …</option>${v.gb_gruppen.map(gr => `<optgroup label="${esc(gr)}">${v.gb.filter(x => x.gruppe === gr).map(x => `<option value="${esc(x.id)}">${esc(x.name)}</option>`).join("")}</optgroup>`).join("")}</select><button class="btn" id="gbZNeu">＋ Gefährdung</button>`}</div></div>
      ${psych ? `<p class="hinweis">Jede Aussage beschreibt eine kritische Ausprägung. „Trifft zu“ bedeutet: eine Gefährdung ist wahrscheinlich – dann Maßnahmen festlegen. Bei „automatischer Handlungsbedarf“ ist eine Maßnahme Pflicht.</p>` :
        `<p class="hinweis">Jede Maßnahme prüfen: ✓ vorhanden (umgesetzt), ! umsetzen (mit „wer“ und „bis wann“), – entfällt (trifft im Betrieb nicht zu). T/O/P: technisch, organisatorisch, personenbezogen.</p>`}
      <div id="gbZ">${zeilenHtml()}</div>
      ${g.fassungen.length ? `<div class="sektion" style="margin-top:18px">Freigegebene Fassungen</div><table class="liste"><tr><th>Fassung</th><th>Stand</th><th>Freigegeben</th><th></th></tr>
        ${g.fassungen.map(f => `<tr><td>${f.nr}</td><td>${datum(f.stand)}</td><td>${esc(f.unterschrift || f.freigegeben_von)}, ${datum(f.freigegeben_am)} ${String(f.freigegeben_am || "").slice(11, 16)}</td><td><a href="/druck/arbeitsschutz/fassung/${f.id}.pdf" target="_blank">PDF</a></td></tr>`).join("")}</table>` : ""}`;
    kopfZeichnen();
    if (!ro) autospeichern($("#gbF"), "arbeitsschutz/gb/" + id, r => { g.status = r.status; g.pruefung = r.pruefung; kopfZeichnen(); });
    if ($("#gbW")) $$("#gbW input").forEach(c => c.onchange = () => speichern.jetzt({werkzeug_ids: $$("#gbW input:checked").map(x => +x.value)}));
    binden();
    if ($("#gbVorl")) $("#gbVorl").onchange = async e => {
      if (!e.target.value) return;
      await speichern.flush();
      try { const n = await api("arbeitsschutz/gb/" + id, {method: "PUT", body: {vorlage: e.target.value}}); g = n; zeichnen(); toast("Vorlage hinzugefügt"); } catch (x) { toast(x.message, true); }
    };
    if ($("#gbZNeu")) $("#gbZNeu").onclick = () => { g.zeilen.push({id: "", g: "", risiko: "", m: []}); zeilenSpeichern(); $("#gbZ").innerHTML = zeilenHtml(); binden(); const t = $$("#gbZ [data-g]").pop(); t && t.focus(); };
    if ($("#gbFrei")) $("#gbFrei").onclick = async () => {
      await speichern.jetzt({zeilen: g.zeilen});
      const n = await api("arbeitsschutz/gb/" + id); g = n;
      if (n.pruefung.length) { kopfZeichnen(); toast("Noch nicht freigabebereit – siehe Hinweise oben.", true); $("#gbPruef").scrollIntoView({behavior: "smooth"}); return; }
      const s = await unterschriftDialog({titel: `${g.nummer} ${g.titel} freigeben`, name: ICH.name || "", knopf: "Freigeben",
        text: `<p>Mit der Unterschrift wird die Gefährdungsbeurteilung als gültige Fassung freigegeben. Die nächste Überprüfung ist in ${g.intervall} Monaten fällig.</p>`});
      if (!s) return;
      try { g = await api(`arbeitsschutz/gb/${id}/freigeben`, {method: "POST", body: s}); toast("Freigegeben"); zeichnen(); } catch (e) { toast(e.message, true); }
    };
    if ($("#gbArch")) $("#gbArch").onclick = async () => { await speichern.flush(); if (await frage("Gefährdungsbeurteilung archivieren?\n\nZum Beispiel, wenn die Maschine nicht mehr im Betrieb ist. Die freigegebenen Fassungen bleiben erhalten.", {ok: "Archivieren"})) { g = await api("arbeitsschutz/gb/" + id, {method: "PUT", body: {status: "archiv"}}); asGbDetail(id); } };
    if ($("#gbReakt")) $("#gbReakt").onclick = async () => { await api("arbeitsschutz/gb/" + id, {method: "PUT", body: {status: "entwurf"}}); asGbDetail(id); };
    if ($("#gbDel")) $("#gbDel").onclick = async () => { await speichern.flush(); if (await frage(`${g.nummer} löschen?`)) { await api("arbeitsschutz/gb/" + id, {method: "DELETE"}); location.hash = "#/arbeitsschutz/gb"; } };
  };
  const binden = () => {
    $$("#gbZ .as-gbz").forEach(el => {
      const i = +el.dataset.z, zz = g.zeilen[i];
      const neu = () => { el.outerHTML = block(zz, i); binden(); };
      const tg = $("[data-g]", el); if (tg && !tg.readOnly) tg.oninput = () => { zz.g = tg.value; zeilenSpeichern(); };
      const ri = $("[data-ri]", el); if (ri) ri.onchange = () => { zz.risiko = ri.value; zeilenSpeichern(); };
      $$("[data-tr]", el).forEach(b => b.onclick = () => { zz.trifft = b.dataset.tr === "1"; if (zz.trifft === false) zz.m = (zz.m || []).filter(m => m.t.trim()); zeilenSpeichern(); neu(); });
      const al = $("[data-alle]", el); if (al) al.onclick = () => { (zz.m || []).forEach(m => { if (m.status === "offen") m.status = "vorhanden"; }); zeilenSpeichern(); neu(); };
      const zd = $("[data-zdel]", el); if (zd) zd.onclick = async () => { if (!await frage("Diese Gefährdung mit allen Maßnahmen entfernen?", {ok: "Entfernen"})) return; g.zeilen.splice(i, 1); zeilenSpeichern(); $("#gbZ").innerHTML = zeilenHtml(); binden(); };
      const mn = $("[data-mneu]", el); if (mn) mn.onclick = () => { (zz.m = zz.m || []).push({id: "", t: "", art: "", status: psych ? "umsetzen" : "offen", wer: "", bis: "", erledigt: "", wirksam: 0}); zeilenSpeichern(); neu(); const t = $$(`[data-z="${i}"] [data-t]`).pop(); t && t.focus(); };
      const hw = $("[data-hinw]", el); if (hw) hw.onclick = () => { (zz.m = zz.m || []).push({id: "", t: zz.hinweis, art: "O", status: "umsetzen", wer: "", bis: "", erledigt: "", wirksam: 0}); zeilenSpeichern(); neu(); };
      $$("tr[data-m]", el).forEach(tr => {
        const m = zz.m[+tr.dataset.m];
        const t = $("[data-t]", tr); if (t && !t.readOnly) t.oninput = () => { m.t = t.value; zeilenSpeichern(); };
        const a = $("[data-a]", tr); if (a) a.onchange = e => { m.art = e.target.value; zeilenSpeichern(); };
        $$("[data-s]", tr).forEach(b => b.onclick = () => { m.status = b.dataset.s; zeilenSpeichern(); neu(); });
        $$("[data-w]", tr).forEach(inp => inp.oninput = inp.onchange = () => { m[inp.dataset.w] = inp.value; if (inp.dataset.w === "erledigt" && inp.value && m.status === "umsetzen") { m.status = "vorhanden"; zeilenSpeichern(); neu(); return; } zeilenSpeichern(); });
        const wk = $("[data-wk]", tr); if (wk) wk.onchange = () => { m.wirksam = wk.checked ? 1 : 0; m.wirksam_am = wk.checked ? heute() : ""; m.wirksam_wer = wk.checked ? (ICH.name || ICH.login) : ""; zeilenSpeichern(); };
        const md = $("[data-mdel]", tr); if (md) md.onclick = () => { zz.m.splice(+tr.dataset.m, 1); zeilenSpeichern(); neu(); };
      });
      $$("textarea", el).forEach(ta => { const auto = () => { ta.style.height = "auto"; ta.style.height = ta.scrollHeight + 2 + "px"; }; auto(); ta.addEventListener("input", auto); });
    });
  };
  zeichnen();
}

// ---------------------------------------------------------------------
//  Betriebsanweisungen
// ---------------------------------------------------------------------
async function asBaListe() {
  asKopf("ba");
  const z = $("#inhalt");
  const liste = await api("arbeitsschutz/ba");
  const zeichnen = () => {
    const t = tabelle("asba", [
      {k: "nummer", t: "Nr."}, {k: "titel", t: "Betriebsanweisung", f: x => `<b>${esc(x.titel)}</b>${x.werkzeuge.length ? `<div class="hinweis">${x.werkzeuge.map(w => esc(w.bezeichnung)).join(", ")}</div>` : ""}`},
      {k: "art_name", t: "Art"}, {k: "symbole", t: "Zeichen", f: x => x.symbole.slice(0, 6).map(s => asZeichen(s, 22)).join(" ")},
      {k: "status", t: "Status", f: x => asStatus(x.status)}, {k: "stand", t: "Stand", f: x => datum(x.stand)},
      {k: "id", t: "", f: x => `<a href="/druck/arbeitsschutz/ba/${x.id}.pdf" target="_blank">PDF</a>`},
    ], liste, {klick: x => location.hash = `#/arbeitsschutz/ba/${x.id}`, leer: "Noch keine Betriebsanweisung."});
    z.innerHTML = `<div class="titel"><h2>Betriebsanweisungen</h2><div class="rechts">${asDarf() ? `<button class="btn prim" id="baNeu">＋ Neue Betriebsanweisung</button>` : ""}</div></div>
      <p class="hinweis" style="margin-top:0">Betriebsanweisungen für Maschinen entstehen aus den Unterweisungshilfen der Berufsgenossenschaft, die für Gefahrstoffe aus den Angaben beim Material und dem Sicherheitsdatenblatt. Nach der Freigabe sind sie für alle Beschäftigten in der Werkstatt und in der Stempeluhr abrufbar.</p>${t.html}`;
    t.binden(zeichnen);
    if ($("#baNeu")) $("#baNeu").onclick = () => asBaNeu();
  };
  zeichnen();
}

async function asBaNeu(vor = {}) {
  const [v, ws, gs] = await Promise.all([asVorlagen(), api("arbeitsschutz/werkzeuge"), api("arbeitsschutz/gefahrstoffe")]);
  const themen = v.themen.filter(t => t.gruppe !== "Weitere");
  const erg = await modal("Neue Betriebsanweisung", `
    ${zeile("Art", `<select name="art">${Object.entries(v.ba_arten).map(([k, l]) => `<option value="${k}" ${k === (vor.art || "maschine") ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`)}
    <div data-fuer="maschine taetigkeit">${zeile("Maschine", `<select name="werkzeug"><option value="">–</option>${ws.map(w => `<option value="${w.id}">${esc(w.nummer)} ${esc(w.bezeichnung)}</option>`).join("")}</select>`)}
      ${zeile("Vorlage", `<select name="vorlage"><option value="">passend zur Maschine</option>${themen.map(t => `<option value="${esc(t.id)}">${esc(t.titel)}</option>`).join("")}</select>`)}</div>
    <div data-fuer="gefahrstoff">${zeile("Gefahrstoff", `<select name="material">${gs.map(x => `<option value="${x.material_id}" ${x.material_id === vor.material_id ? "selected" : ""}>${esc(x.name)}</option>`).join("") || `<option value="">Noch keine Gefahrstoffe erfasst</option>`}</select>`)}
      <p class="hinweis">Gefahrstoffe werden beim Material unter „Datenblätter &amp; Sicherheit“ gekennzeichnet.</p></div>
    ${zeile("Titel", `<input name="titel" placeholder="leer = Name der Maschine bzw. des Stoffs">`)}`, "Anlegen", hg => {
    const art = $("[name=art]", hg);
    const zeigen = () => $$("[data-fuer]", hg).forEach(d => d.style.display = d.dataset.fuer.split(" ").includes(art.value) ? "" : "none");
    art.onchange = zeigen; zeigen();
  });
  if (!erg) return;
  try {
    const b = await api("arbeitsschutz/ba", {method: "POST", body: {art: erg.art, titel: erg.titel, vorlage: erg.art !== "gefahrstoff" ? erg.vorlage : "",
      werkzeug_ids: erg.art !== "gefahrstoff" && erg.werkzeug ? [+erg.werkzeug] : [], material_id: erg.art === "gefahrstoff" ? +erg.material || null : null}});
    location.hash = `#/arbeitsschutz/ba/${b.id}`;
  } catch (e) { toast(e.message, true); }
}

async function asBaDetail(id) {
  const [b0, v] = await Promise.all([api("arbeitsschutz/ba/" + id), asVorlagen()]);
  let b = b0;
  const ro = !asDarf() || b.status === "archiv";
  asKopf("ba", `Betriebsanweisung <b>${esc(b.nummer)}</b> · ${esc(b.titel)}`, "#/arbeitsschutz/ba");
  const z = $("#inhalt");
  const speichern = asDebounce(async body => {
    asSpeicherStatus("speichert …");
    try { const n = await api("arbeitsschutz/ba/" + id, {method: "PUT", body}); asSpeicherStatus("gespeichert ✓", "ok"); if (n.status !== b.status) { b.status = n.status; $("#baSt").innerHTML = asStatus(b.status); } }
    catch (e) { asSpeicherStatus("Fehler", "fehler"); toast(e.message, true); }
  }, 700);
  const gruppen = {};
  v.zeichen.forEach(x => (gruppen[x.gruppe] = gruppen[x.gruppe] || []).push(x));
  const reihenfolge = b.art === "gefahrstoff" ? ["GHS-Gefahrenpiktogramme", "Gebotszeichen", "Warnzeichen", "Verbotszeichen", "Rettungszeichen", "Brandschutzzeichen"]
    : ["Gebotszeichen", "Warnzeichen", "Verbotszeichen", "GHS-Gefahrenpiktogramme", "Rettungszeichen", "Brandschutzzeichen", "Leiter-Piktogramme"];
  z.innerHTML = `<div class="titel"><h2>${esc(b.nummer)} ${esc(b.titel)}</h2><span class="speicher"></span>
      <div class="rechts"><a class="btn" href="/druck/arbeitsschutz/ba/${id}?entwurf=1" target="_blank">Vorschau</a><a class="btn" href="/druck/arbeitsschutz/ba/${id}.pdf" target="_blank">📄 PDF (freigegeben)</a>
        ${ICH.rechte.inhaber && b.status !== "archiv" ? `<button class="btn prim" id="baFrei">✍ Freigeben</button>` : ""}
        ${asDarf() ? (b.status === "archiv" ? `<button class="btn" id="baReakt">Wieder aufnehmen</button>` : b.fassungen.length ? `<button class="btn" id="baArch">Archivieren</button>` : `<button class="btn pk rot" id="baDel">${ic("loeschen")} Löschen</button>`) : ""}</div></div>
    <div class="hinweis" style="margin:-6px 0 10px"><span id="baSt">${asStatus(b.status)}</span> · ${esc(b.art_name)}${b.stand ? ` · Stand ${datum(b.stand)}` : ""}${b.material ? ` · <a href="#/mat/${b.material.id}/sicherheit">${esc(b.material.nummer)} ${esc(b.material.name)}</a>` : ""}${b.werkzeuge.length ? " · " + b.werkzeuge.map(w => esc(w.bezeichnung)).join(", ") : ""}</div>
    ${Object.values(b.abschnitte).some(t => String(t).includes("[aus SDB")) ? `<div class="kachel as-hinweis" style="margin-bottom:10px">Die Stellen mit „[aus SDB …]“ bitte mit den Angaben aus dem Sicherheitsdatenblatt ersetzen (die Abschnittsnummer steht dabei). Erst dann ist die Freigabe möglich.</div>` : ""}
    <div class="form" id="baF">
      ${zeile("Titel", `<input data-f="titel" value="${esc(b.titel)}" ${ro ? "readonly" : ""}>`)}
      ${zeile("Arbeitsbereich", `<input data-f="bereich" value="${esc(b.bereich)}" ${ro ? "readonly" : ""}>`)}
    </div>
    <p class="hinweis">Jede Zeile wird in der Betriebsanweisung ein Aufzählungspunkt.</p>
    <div id="baAb">${b.gliederung.map(([k, t]) => `<div class="as-ab"><div class="as-abk ${b.art === "gefahrstoff" ? "gs" : ""}">${esc(t)}</div>
      <textarea data-ab="${k}" rows="3" ${ro ? "readonly" : ""}>${esc(b.abschnitte[k] || "")}</textarea></div>`).join("")}</div>
    <div class="sektion" style="margin-top:14px">Zeichen <span class="hinweis" style="font-weight:400">– GHS-Piktogramme erscheinen bei „Gefahren“, alle anderen bei „Schutzmaßnahmen“</span></div>
    <div id="baZ">${reihenfolge.filter(g => gruppen[g]).map(g => `<details ${g === reihenfolge[0] || gruppen[g].some(x => b.symbole.includes(x.code)) ? "open" : ""}><summary>${esc(g)}</summary>
      <div class="as-zeichen">${gruppen[g].map(x => `<button class="${b.symbole.includes(x.code) ? "an" : ""}" data-z="${esc(x.code)}" title="${esc(x.code)} ${esc(x.name)}" ${ro ? "disabled" : ""}>${asZeichen(x.code, 44)}<span>${esc(x.name)}</span></button>`).join("")}</div></details>`).join("")}</div>
    ${b.fassungen.length ? `<div class="sektion" style="margin-top:18px">Freigegebene Fassungen</div><table class="liste"><tr><th>Fassung</th><th>Stand</th><th>Freigegeben</th><th></th></tr>
      ${b.fassungen.map(f => `<tr><td>${f.nr}</td><td>${datum(f.stand)}</td><td>${esc(f.freigegeben_von)}, ${datum(f.freigegeben_am)}</td><td><a href="/druck/arbeitsschutz/fassung/${f.id}.pdf" target="_blank">PDF</a></td></tr>`).join("")}</table>` : ""}`;
  if (!ro) autospeichern($("#baF"), "arbeitsschutz/ba/" + id, r => { b.status = r.status; $("#baSt").innerHTML = asStatus(b.status); });
  $$("[data-ab]").forEach(ta => { const auto = () => { ta.style.height = "auto"; ta.style.height = ta.scrollHeight + 2 + "px"; }; auto();
    ta.oninput = () => { auto(); b.abschnitte[ta.dataset.ab] = ta.value; speichern({abschnitte: b.abschnitte}); }; });
  $$("[data-z]").forEach(btn => btn.onclick = () => {
    const c = btn.dataset.z; b.symbole = b.symbole.includes(c) ? b.symbole.filter(x => x !== c) : [...b.symbole, c];
    btn.classList.toggle("an", b.symbole.includes(c)); speichern.jetzt({symbole: b.symbole});
  });
  if ($("#baFrei")) $("#baFrei").onclick = async () => {
    await speichern.jetzt({abschnitte: b.abschnitte});
    const s = await unterschriftDialog({titel: `Betriebsanweisung ${b.nummer} freigeben`, name: ICH.name || "", knopf: "Freigeben",
      text: `<p>Mit der Unterschrift wird die Betriebsanweisung freigegeben. Sie steht danach allen Beschäftigten zur Verfügung und gehört in die nächste Unterweisung.</p>`});
    if (!s) return;
    try { await api(`arbeitsschutz/ba/${id}/freigeben`, {method: "POST", body: s}); toast("Freigegeben"); asBaDetail(id); } catch (e) { toast(e.message, true); }
  };
  if ($("#baArch")) $("#baArch").onclick = async () => { if (await frage("Betriebsanweisung archivieren?", {ok: "Archivieren"})) { await api("arbeitsschutz/ba/" + id, {method: "PUT", body: {status: "archiv"}}); asBaDetail(id); } };
  if ($("#baReakt")) $("#baReakt").onclick = async () => { await api("arbeitsschutz/ba/" + id, {method: "PUT", body: {status: "entwurf"}}); asBaDetail(id); };
  if ($("#baDel")) $("#baDel").onclick = async () => { if (await frage(`${b.nummer} löschen?`)) { await api("arbeitsschutz/ba/" + id, {method: "DELETE"}); location.hash = "#/arbeitsschutz/ba"; } };
}

// ---------------------------------------------------------------------
//  Unterweisungen
// ---------------------------------------------------------------------
function asUwKopf(aktiv) {
  asKopf("unterweisungen", "", null, [["Fälligkeiten", "#/arbeitsschutz/unterweisungen", aktiv === "faellig"], ["Durchgeführt", "#/arbeitsschutz/unterweisungen/liste", aktiv === "liste"],
    ["Themen", "#/arbeitsschutz/unterweisungen/themen", aktiv === "themen"]]);
}
async function asUnterweisungen(teil) {
  if (teil === "liste") return asUwListe();
  if (teil === "themen") return asThemen();
  asUwKopf("faellig");
  const z = $("#inhalt");
  const m = await api("arbeitsschutz/matrix");
  if (!m.themen.length) return asThemenStart();
  const farbe = {fehlt: "as-c-rot", ueberfaellig: "as-c-rot", bald: "as-c-gelb", ok: "as-c-gruen"};
  const faellig = [];
  m.zeilen.forEach(r => Object.entries(r.themen).forEach(([tid, f]) => { if (f.status !== "ok") faellig.push([r.mitarbeiter.id, +tid]); }));
  z.innerHTML = `<div class="titel"><h2>Unterweisungen – Fälligkeiten</h2><div class="rechts">${asDarf() ? `<button class="btn prim" id="uwPlan">＋ Unterweisung durchführen</button>` : ""}</div></div>
    <p class="hinweis" style="margin-top:0">Erstunterweisung vor Aufnahme der Tätigkeit, danach mindestens jährlich – Jugendliche halbjährlich (§ 29 JArbSchG; das Geburtsdatum steht beim Mitarbeiter). Grün: aktuell, gelb: in den nächsten 30 Tagen fällig, rot: fällig oder noch nie unterwiesen.</p>
    ${m.zeilen.length ? `<div class="tab-scroll"><table class="liste as-matrix"><tr><th>Mitarbeiter</th>${m.themen.map(t => `<th title="${esc(t.titel)} – alle ${t.intervall} Monate" data-th="${t.id}">${esc(t.titel)}</th>`).join("")}</tr>
      ${m.zeilen.map(r => `<tr><td><b>${esc(r.mitarbeiter.name)}</b>${r.mitarbeiter.jugendlich ? ` <span class="as-jug" title="unter 18: halbjährliche Unterweisung">J</span>` : ""}</td>
        ${m.themen.map(t => { const f = r.themen[t.id]; return f ? `<td class="${farbe[f.status]}" title="${f.letzte ? "zuletzt " + datum(f.letzte) + " · " : ""}fällig ${datum(f.faellig)}">${f.status === "fehlt" ? "noch nie" : datum(f.faellig)}</td>` : `<td class="hinweis">–</td>`; }).join("")}</tr>`).join("")}</table></div>`
      : `<div class="leer">Keine Beschäftigten. Mitarbeiter werden unter „Mitarbeiter“ angelegt (ohne Lohnart „Inhaber“).</div>`}`;
  const erst = m.zeilen.some(r => Object.values(r.themen).some(f => f.status === "fehlt"));
  const neu = (tids, mids) => asUwNeu({thema_ids: tids, mitarbeiter_ids: mids, anlass: erst ? "" : "Wiederholungsunterweisung (mindestens jährlich)"});
  if ($("#uwPlan")) $("#uwPlan").onclick = () => neu([...new Set(faellig.map(x => x[1]))], [...new Set(faellig.map(x => x[0]))]);
  $$("[data-th]").forEach(th => th.onclick = () => asDarf() && neu([+th.dataset.th], [...new Set(faellig.filter(x => x[1] === +th.dataset.th).map(x => x[0]))]));
}

async function asThemenStart() {
  const v = await asVorlagen();
  const z = $("#inhalt");
  const vor = new Set(["allgemein", "brandschutz", "erste-hilfe", "uwh-020", "gefahrstoffe", "uwh-018", "leitern", "montage-baustelle"]);
  const gruppen = [...new Set(v.themen.map(t => t.gruppe))];
  z.innerHTML = `<div class="titel"><h2>Unterweisungsthemen einrichten</h2></div>
    <p>Noch keine Themen angelegt. Hier die Themen auswählen, zu denen im Betrieb unterwiesen wird – die Inhalte stammen aus den Unterweisungshilfen und -nachweisen der Berufsgenossenschaft und lassen sich danach anpassen. Für jede Maschine mit Gefährdung das passende Maschinenthema wählen.</p>
    ${gruppen.map(g => `<div class="sektion">${esc(g)}</div><div class="as-chips">${v.themen.filter(t => t.gruppe === g).map(t => `<label class="as-chip"><input type="checkbox" value="${esc(t.id)}" ${vor.has(t.id) ? "checked" : ""}> ${esc(t.titel)}</label>`).join("")}</div>`).join("")}
    ${asDarf() ? `<button class="btn prim" id="thAnl" style="margin-top:16px">Ausgewählte Themen übernehmen</button>` : ""}`;
  if ($("#thAnl")) $("#thAnl").onclick = async () => {
    for (const c of $$(".as-chip input:checked")) await api("arbeitsschutz/themen", {method: "POST", body: {vorlage: c.value}});
    toast("Themen übernommen"); asUnterweisungen("faellig");
  };
}

async function asUwNeu(vor = {}) {
  const [v, th, mas] = await Promise.all([asVorlagen(), api("arbeitsschutz/themen"), api("arbeitsschutz/mitarbeiter")]);
  const tids = new Set(vor.thema_ids || []), mids = new Set(vor.mitarbeiter_ids || []);
  let fenster = null;
  const erg = await modal("Unterweisung durchführen", `
    ${zeile("Datum", `<input type="date" name="datum" value="${heute()}">`)}
    ${zeile("Anlass", `<select name="anlass">${v.anlaesse.map(a => `<option ${a === (vor.anlass || v.anlaesse[0]) ? "selected" : ""}>${esc(a)}</option>`).join("")}</select>`)}
    ${zeile("Unterweist", `<input name="unterweiser" value="${esc(ICH.name || ICH.login)}">`)}
    ${zeile("Ort", `<input name="ort" placeholder="z. B. Werkstatt, an der Maschine">`)}
    <div class="sektion">Themen</div><div class="as-wahl" id="uwT">${th.map(t => `<label><input type="checkbox" value="${t.id}" ${tids.has(t.id) ? "checked" : ""}> ${esc(t.titel)}</label>`).join("")}</div>
    <div class="sektion">Teilnehmer</div><div class="as-wahl" id="uwM">${mas.filter(m => !m.inhaber).map(m => `<label><input type="checkbox" value="${m.id}" ${mids.has(m.id) ? "checked" : ""}> ${esc(m.name)}${m.jugendlich ? " (J)" : ""}</label>`).join("")}</div>`,
    "Weiter zur Durchführung", hg => { fenster = hg; $(".modal", hg).style.width = "min(640px,96vw)"; });
  if (!erg) return;
  // das Fenster ist schon geschlossen, die Auswahl steht aber noch in seinen Elementen
  const body = {...erg, thema_ids: $$("#uwT input:checked", fenster).map(x => +x.value), mitarbeiter_ids: $$("#uwM input:checked", fenster).map(x => +x.value)};
  try { const u = await api("arbeitsschutz/unterweisungen", {method: "POST", body}); location.hash = `#/arbeitsschutz/unterweisung/${u.id}`; }
  catch (e) { toast(e.message, true); }
}

async function asUwListe() {
  asUwKopf("liste");
  const z = $("#inhalt");
  const liste = await api("arbeitsschutz/unterweisungen");
  const zeichnen = () => {
    const t = tabelle("asuw", [
      {k: "datum", t: "Datum", f: x => datum(x.datum)}, {k: "nummer", t: "Nr."}, {k: "titel", t: "Thema", f: x => `<b>${esc(x.titel)}</b><div class="hinweis">${esc(x.anlass)}</div>`},
      {k: "namen", t: "Teilnehmer", f: x => esc(x.namen.join(", "))}, {k: "unterschrieben", t: "Unterschriften", r: 1, f: x => `${x.unterschrieben} / ${x.teilnehmer}`},
      {k: "status", t: "Status", f: x => asStatus(x.status)}, {k: "id", t: "", f: x => `<a href="/druck/arbeitsschutz/unterweisung/${x.id}.pdf" target="_blank">PDF</a>`},
    ], liste, {klick: x => location.hash = `#/arbeitsschutz/unterweisung/${x.id}`, leer: "Noch keine Unterweisung durchgeführt."});
    z.innerHTML = `<div class="titel"><h2>Durchgeführte Unterweisungen</h2><div class="rechts">${asDarf() ? `<button class="btn prim" id="uwNeu">＋ Unterweisung durchführen</button>` : ""}</div></div>${t.html}`;
    t.binden(zeichnen);
    if ($("#uwNeu")) $("#uwNeu").onclick = () => asUwNeu();
  };
  zeichnen();
}

async function asUnterweisungDetail(id) {
  let u = await api("arbeitsschutz/unterweisungen/" + id);
  const v = await asVorlagen();
  asKopf("unterweisungen", `Unterweisung <b>${esc(u.nummer)}</b> · ${esc(u.titel)}`, "#/arbeitsschutz/unterweisungen/liste");
  const z = $("#inhalt");
  const zeichnen = () => {
    const offen = u.status === "offen";
    const gesperrt = !offen || u.unterweiser_signatur || u.teilnehmer.some(t => t.unterschrieben);
    const ro = !darf("arbeitsschutz", 2);
    z.innerHTML = `<div class="titel"><h2>${esc(u.titel)}</h2><span class="speicher"></span>
        <div class="rechts"><a class="btn" href="/druck/arbeitsschutz/unterweisung/${id}" target="_blank">Nachweis ansehen</a><a class="btn" href="/druck/arbeitsschutz/unterweisung/${id}.pdf" target="_blank">📄 PDF</a>
          ${offen && !gesperrt && asDarf() ? `<button class="btn pk rot" id="uwDel">${ic("loeschen")} Löschen</button>` : ""}</div></div>
      <div class="hinweis" style="margin:-6px 0 10px">${asStatus(u.status)} · Nr. ${esc(u.nummer)}${u.abgeschlossen ? " · abgeschlossen am " + datum(u.abgeschlossen) : ""}</div>
      <div class="form" id="uwF">
        ${zeile("Datum", `<input type="date" data-f="datum" value="${esc(u.datum)}" ${gesperrt || ro ? "readonly" : ""}>`)}
        ${zeile("Anlass", `<select data-f="anlass" ${gesperrt || ro ? "disabled" : ""}>${opts(v.anlaesse, u.anlass)}</select>`)}
        ${zeile("Unterweist", `<input data-f="unterweiser" value="${esc(u.unterweiser)}" ${!offen || ro ? "readonly" : ""}>`)}
        ${zeile("Ort / Dauer", `<input data-f="ort" value="${esc(u.ort)}" placeholder="Ort" ${!offen || ro ? "readonly" : ""}><input data-f="dauer" value="${esc(u.dauer)}" placeholder="z. B. 30 Minuten" style="flex:0 0 140px" ${!offen || ro ? "readonly" : ""}>`)}
      </div>
      <div class="as-uw-inhalt">${u.inhalt.map(t => `<section><h3>${esc(t.titel)}</h3>
        ${t.uwh ? `<p><a class="btn" href="/arbeitsschutz/uwh/${esc(t.uwh)}.pdf" target="_blank" data-tafel="${esc(t.titel)}">🖼 Bildtafel der Berufsgenossenschaft zeigen (${esc(t.uwh)})</a></p>` : ""}
        ${(t.abschnitte || []).map(a => `${a.titel ? `<h4>${esc(a.titel)}</h4>` : ""}<ul>${(a.punkte || []).map(p => `<li>${esc(p)}</li>`).join("")}</ul>`).join("")}
        ${t.ba.length ? `<p>Betriebsanweisungen: ${t.ba.map(b => `<a href="/druck/arbeitsschutz/ba/${b.id}" target="_blank">${esc(b.nummer)} ${esc(b.titel)}</a>`).join(", ")}</p>` : ""}</section>`).join("")}</div>
      <div class="form" id="uwF2" style="margin-top:10px">
        ${zeile("Ergänzungen", `<textarea data-f="ergaenzung" rows="2" placeholder="Was zusätzlich besprochen wurde, z. B. ein Beinaheunfall" ${gesperrt || ro ? "readonly" : ""}>${esc(u.ergaenzung)}</textarea>`, true)}
        ${zeile("Verständnis geprüft", `<input data-f="verstaendnis" value="${esc(u.verstaendnis)}" list="uwVerst" placeholder="Wie wurde geprüft, ob alles verstanden ist?" ${!offen || ro ? "readonly" : ""}>
          <datalist id="uwVerst"><option>Rückfragen gestellt und beantwortet</option><option>Arbeitsschritte an der Maschine vorgeführt und nachmachen lassen</option><option>Kurzes Gespräch mit Fragen zu den Inhalten</option><option>Fragebogen ausgefüllt</option></datalist>`, true)}
      </div>
      <div class="sektion" style="margin-top:16px">Unterschriften</div>
      <p class="hinweis" style="margin-top:0">Jede Person bestätigt am Tablet: „Ich habe an der Unterweisung teilgenommen und den Inhalt verstanden.“ Wer nicht vor Ort unterschreibt, kann das in der Stempeluhr unter „Offene Unterschriften“ nachholen, solange die Unterweisung nicht abgeschlossen ist.</p>
      <div class="as-tn">${u.teilnehmer.map(t => `<div class="as-tn-z"><b>${esc(t.name)}</b>${t.unterschrieben ? `<span style="color:var(--gruen)">✓ unterschrieben ${datum(t.unterschrieben)} ${t.unterschrieben.slice(11, 16)}</span>`
          : offen ? `<button class="btn prim" data-sig="${t.id}">✍ Unterschreiben</button>` : `<span class="hinweis">nicht unterschrieben</span>`}</div>`).join("")}
        <div class="as-tn-z as-tn-uw"><b>${esc(u.unterweiser)}</b> <span class="hinweis">(unterweist)</span>${u.unterweiser_signatur ? `<span style="color:var(--gruen)">✓ unterschrieben ${datum(u.unterweiser_signatur.zeit)}</span>`
          : offen && !ro ? `<button class="btn" id="uwSigU">✍ Unterschreiben</button>` : ""}</div></div>
      ${offen && asDarf() ? `<div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap">${ro ? "" : `<button class="btn" id="uwTn">Teilnehmer ändern</button>`}<button class="btn prim" id="uwAbschl">Unterweisung abschließen</button></div>
        <p class="hinweis">Beim Abschließen werden Teilnehmer ohne Unterschrift von der Liste genommen (sie waren nicht dabei); danach ist der Nachweis unveränderlich.</p>` : ""}`;
    if (!ro) {
      const nach = r => { u = r; };
      if (offen) { autospeichern($("#uwF"), "arbeitsschutz/unterweisungen/" + id, nach); autospeichern($("#uwF2"), "arbeitsschutz/unterweisungen/" + id, nach); }
    }
    const inhaltText = `<p>Mit meiner Unterschrift bestätige ich, dass ich an der Unterweisung <b>${esc(u.titel)}</b> vom ${datum(u.datum)} teilgenommen und den Inhalt verstanden habe.</p>`;
    $$("[data-sig]").forEach(b => b.onclick = async () => {
      const t = u.teilnehmer.find(x => x.id === +b.dataset.sig);
      const s = await unterschriftDialog({titel: "Unterweisung bestätigen", text: inhaltText, name: t.name, nameFest: true, knopf: "Bestätigen"});
      if (!s) return;
      try { u = await api(`arbeitsschutz/unterweisungen/${id}/unterschreiben`, {method: "POST", body: {...s, teilnehmer_id: t.id}}); toast("Unterschrift gespeichert"); zeichnen(); } catch (e) { toast(e.message, true); }
    });
    if ($("#uwSigU")) $("#uwSigU").onclick = async () => {
      const s = await unterschriftDialog({titel: "Unterweisung durchgeführt", text: `<p>Die Unterweisung <b>${esc(u.titel)}</b> wurde wie beschrieben durchgeführt.</p>`, name: u.unterweiser, knopf: "Unterschreiben"});
      if (!s) return;
      try { u = await api(`arbeitsschutz/unterweisungen/${id}/unterschreiben`, {method: "POST", body: {...s, rolle: "unterweiser"}}); toast("Unterschrift gespeichert"); zeichnen(); } catch (e) { toast(e.message, true); }
    };
    if ($("#uwAbschl")) $("#uwAbschl").onclick = async () => {
      const ohne = u.teilnehmer.filter(t => !t.unterschrieben).map(t => t.name);
      if (!await frage(`Unterweisung abschließen?${ohne.length ? "\n\nOhne Unterschrift (werden von der Liste genommen): " + ohne.join(", ") : ""}`, {ok: "Abschließen"})) return;
      try { u = await api(`arbeitsschutz/unterweisungen/${id}/abschliessen`, {method: "POST", body: {}}); toast("Abgeschlossen"); zeichnen(); } catch (e) { toast(e.message, true); }
    };
    if ($("#uwTn")) $("#uwTn").onclick = async () => {
      const mas = await api("arbeitsschutz/mitarbeiter");
      const da = new Set(u.teilnehmer.map(t => t.mitarbeiter_id));
      let fenster = null;
      const erg = await modal("Teilnehmer", `<div class="as-wahl">${mas.filter(m => !m.inhaber).map(m => `<label><input type="checkbox" value="${m.id}" ${da.has(m.id) ? "checked" : ""}> ${esc(m.name)}</label>`).join("")}</div>`, "Übernehmen", hg => { fenster = hg; });
      if (!erg) return;
      const ids = $$(".as-wahl input:checked", fenster).map(x => +x.value);
      try { u = await api("arbeitsschutz/unterweisungen/" + id, {method: "PUT", body: {mitarbeiter_ids: ids}}); zeichnen(); } catch (e) { toast(e.message, true); }
    };
    if ($("#uwDel")) $("#uwDel").onclick = async () => { if (await frage("Diese Unterweisung löschen?")) { await api("arbeitsschutz/unterweisungen/" + id, {method: "DELETE"}); location.hash = "#/arbeitsschutz/unterweisungen/liste"; } };
  };
  zeichnen();
}
async function asThemen() {
  asUwKopf("themen");
  const z = $("#inhalt");
  const [th, v] = await Promise.all([api("arbeitsschutz/themen?alle=1"), asVorlagen()]);
  const da = new Set(th.map(t => t.vorlage).filter(Boolean));
  z.innerHTML = `<div class="titel"><h2>Unterweisungsthemen</h2><div class="rechts">${asDarf() ? `<select id="thVorl"><option value="">＋ Thema aus Vorlage …</option>${[...new Set(v.themen.map(t => t.gruppe))].map(g => `<optgroup label="${esc(g)}">${v.themen.filter(t => t.gruppe === g && !da.has(t.id)).map(t => `<option value="${esc(t.id)}">${esc(t.titel)}</option>`).join("")}</optgroup>`).join("")}</select><button class="btn" id="thNeu">＋ Eigenes Thema</button>` : ""}</div></div>
    <table class="liste"><tr><th>Thema</th><th>Gruppe</th><th class="r">Intervall</th><th>Gilt für</th><th>Betriebsanweisungen</th></tr>
    ${th.map(t => `<tr class="klick" data-t="${t.id}"><td><b>${esc(t.titel)}</b>${t.aktiv ? "" : ` <span class="hinweis">(inaktiv)</span>`}</td><td>${esc(t.gruppe)}</td><td class="r">${t.intervall} Monate</td><td>${t.alle ? "alle" : t.mitarbeiter_ids.length + " Mitarbeiter"}</td><td>${t.ba.map(b => esc(b.nummer)).join(", ")}</td></tr>`).join("") || `<tr><td colspan="5" class="leer">Noch keine Themen.</td></tr>`}</table>`;
  $$("[data-t]").forEach(tr => tr.onclick = () => location.hash = `#/arbeitsschutz/thema/${tr.dataset.t}`);
  if ($("#thVorl")) $("#thVorl").onchange = async e => { if (!e.target.value) return; const t = await api("arbeitsschutz/themen", {method: "POST", body: {vorlage: e.target.value}}); location.hash = `#/arbeitsschutz/thema/${t.id}`; };
  if ($("#thNeu")) $("#thNeu").onclick = async () => { const e = await modal("Eigenes Thema", zeile("Titel", `<input name="titel">`), "Anlegen"); if (!e) return;
    try { const t = await api("arbeitsschutz/themen", {method: "POST", body: {titel: e.titel, text: "## Inhalte\n"}}); location.hash = `#/arbeitsschutz/thema/${t.id}`; } catch (x) { toast(x.message, true); } };
}

async function asThemaDetail(id) {
  const [t, mas, ws, bas] = await Promise.all([api("arbeitsschutz/themen?alle=1").then(l => l.find(x => x.id === id)), api("arbeitsschutz/mitarbeiter"), api("arbeitsschutz/werkzeuge"), api("arbeitsschutz/ba")]);
  if (!t) { asUwKopf("themen"); $("#inhalt").innerHTML = `<div class="leer">Thema nicht gefunden.</div>`; return; }
  asKopf("unterweisungen", `Unterweisungsthema <b>${esc(t.titel)}</b>`, "#/arbeitsschutz/unterweisungen/themen");
  const ro = !asDarf();
  const z = $("#inhalt");
  z.innerHTML = `<div class="titel"><h2>${esc(t.titel)}</h2><span class="speicher"></span><div class="rechts">${t.uwh ? `<a class="btn" href="/arbeitsschutz/uwh/${esc(t.uwh)}.pdf" target="_blank" data-tafel="${esc(t.titel)}">🖼 Bildtafel ${esc(t.uwh)}</a>` : ""}${ro ? "" : `<button class="btn pk rot" id="thDel">${ic("loeschen")} Entfernen</button>`}</div></div>
    <div class="form" id="thF">
      ${zeile("Titel", `<input data-f="titel" value="${esc(t.titel)}" ${ro ? "readonly" : ""}>`)}
      ${zeile("Gruppe", `<input data-f="gruppe" value="${esc(t.gruppe)}" ${ro ? "readonly" : ""}>`)}
      ${zeile("Intervall", `<input data-f="intervall" value="${t.intervall}" style="flex:0 0 70px;text-align:right" ${ro ? "readonly" : ""}><span style="padding-top:5px">Monate (Jugendliche höchstens 6)</span>`)}
      ${zeile("Aktiv", `<label style="padding-top:5px"><input type="checkbox" data-f="aktiv" ${t.aktiv ? "checked" : ""} ${ro ? "disabled" : ""}> wird in den Fälligkeiten geführt</label>`)}
      ${zeile("Gilt für", `<div class="spalte"><label><input type="radio" name="thAlle" value="1" ${t.alle ? "checked" : ""} ${ro ? "disabled" : ""}> alle Beschäftigten</label><label><input type="radio" name="thAlle" value="0" ${t.alle ? "" : "checked"} ${ro ? "disabled" : ""}> nur ausgewählte</label>
        <div class="as-chips" id="thM" style="${t.alle ? "display:none" : ""}">${mas.filter(m => !m.inhaber).map(m => `<label class="as-chip"><input type="checkbox" value="${m.id}" ${t.mitarbeiter_ids.includes(m.id) ? "checked" : ""} ${ro ? "disabled" : ""}> ${esc(m.name)}</label>`).join("")}</div></div>`, true)}
      ${zeile("Inhalt", `<textarea data-f="text" rows="14" ${ro ? "readonly" : ""} style="font-family:inherit">${esc(t.text)}</textarea>`, true)}
    </div>
    <p class="hinweis">Zeilen mit „## “ am Anfang sind Zwischenüberschriften, jede andere Zeile ist ein Punkt der Unterweisung.</p>
    <div class="sektion">Maschinen</div><div class="as-chips" id="thW">${ws.filter(w => w.art === "Stationäre Maschine" || t.werkzeug_ids.includes(w.id)).map(w => `<label class="as-chip"><input type="checkbox" value="${w.id}" ${t.werkzeug_ids.includes(w.id) ? "checked" : ""} ${ro ? "disabled" : ""}> ${esc(w.bezeichnung)}</label>`).join("") || `<span class="hinweis">keine</span>`}</div>
    <div class="sektion">Betriebsanweisungen zum Thema</div><div class="as-chips" id="thB">${bas.filter(b => b.status !== "archiv").map(b => `<label class="as-chip"><input type="checkbox" value="${b.id}" ${t.ba_ids.includes(b.id) ? "checked" : ""} ${ro ? "disabled" : ""}> ${esc(b.nummer)} ${esc(b.titel)}</label>`).join("") || `<span class="hinweis">noch keine</span>`}</div>`;
  if (ro) return;
  autospeichern($("#thF"), "arbeitsschutz/themen/" + id);
  const put = body => api("arbeitsschutz/themen/" + id, {method: "PUT", body}).then(() => asSpeicherStatus("gespeichert ✓", "ok")).catch(e => toast(e.message, true));
  $$("[name=thAlle]").forEach(r => r.onchange = () => { $("#thM").style.display = r.value === "1" ? "none" : ""; put({alle: +r.value}); });
  $$("#thM input").forEach(c => c.onchange = () => put({mitarbeiter_ids: $$("#thM input:checked").map(x => +x.value)}));
  $$("#thW input").forEach(c => c.onchange = () => put({werkzeug_ids: $$("#thW input:checked").map(x => +x.value)}));
  $$("#thB input").forEach(c => c.onchange = () => put({ba_ids: $$("#thB input:checked").map(x => +x.value)}));
  $("#thDel").onclick = async () => { if (!await frage(`Thema „${t.titel}“ entfernen?\n\nWurde schon dazu unterwiesen, bleibt es als inaktiv erhalten.`, {ok: "Entfernen"})) return;
    const r = await api("arbeitsschutz/themen/" + id, {method: "DELETE"}); toast(r.inaktiv ? "Auf inaktiv gesetzt" : "Entfernt"); location.hash = "#/arbeitsschutz/unterweisungen/themen"; };
}

// ---------------------------------------------------------------------
//  Gefahrstoffe & Datenblätter
// ---------------------------------------------------------------------
async function asGefahrstoffe() {
  asKopf("gefahrstoffe");
  const z = $("#inhalt");
  const liste = await api("arbeitsschutz/gefahrstoffe");
  const kann = asDarf() || darf("material", 2);
  z.innerHTML = `<div class="titel"><h2>Gefahrstoffverzeichnis</h2><div class="rechts"><a class="btn" href="/druck/arbeitsschutz/gefahrstoffverzeichnis.pdf" target="_blank">📄 PDF</a>${kann ? `<button class="btn prim" id="gsNeu">＋ Gefahrstoff kennzeichnen</button>` : ""}</div></div>
    <p class="hinweis" style="margin-top:0">Alle Materialien, die als Gefahrstoff gekennzeichnet sind (Lacke, Beizen, Öle, Klebstoffe, Verdünnungen …). Sicherheitsdatenblatt und technisches Merkblatt liegen beim Material unter „Datenblätter &amp; Sicherheit“ und sind in der Werkstatt bei den Materialsummen anklickbar.</p>
    <table class="liste"><tr><th>Gefahrstoff</th><th>Piktogramme</th><th>Signalwort</th><th>H-Sätze</th><th>Arbeitsbereich</th><th>Sicherheitsdatenblatt</th><th>Betriebsanweisung</th></tr>
    ${liste.map(x => `<tr class="klick" data-m="${x.material_id}"><td><b>${esc(x.name)}</b><div class="hinweis">${esc(x.nummer)}${x.lieferant ? " · " + esc(x.lieferant) : ""}</div></td>
      <td>${x.ghs.map(g => asZeichen(g, 28)).join(" ")}</td><td>${esc(x.signalwort)}</td><td>${esc(x.h_saetze)}</td><td>${esc(x.bereich)}</td>
      <td>${x.sdb ? `<a href="/api/arbeitsschutz/datei/${x.sdb.id}" target="_blank">öffnen</a> <span class="hinweis">${datum(x.sdb.ausgabe || x.sdb.angelegt)}</span>` : `<span class="rot-t">fehlt</span>`}</td>
      <td>${x.ba ? `<a href="#/arbeitsschutz/ba/${x.ba.id}">${esc(x.ba.nummer)}</a> ${x.ba.status === "gueltig" ? "" : asStatus(x.ba.status)}` : asDarf() ? `<button class="btn" data-ba="${x.material_id}">anlegen</button>` : "–"}</td></tr>`).join("")
      || `<tr><td colspan="7" class="leer">Noch keine Gefahrstoffe gekennzeichnet.</td></tr>`}</table>`;
  $$("tr[data-m]").forEach(tr => tr.onclick = e => { if (e.target.closest("a,button")) return; location.hash = `#/mat/${tr.dataset.m}/sicherheit`; });
  $$("[data-ba]").forEach(b => b.onclick = async () => { try { const n = await api("arbeitsschutz/ba", {method: "POST", body: {art: "gefahrstoff", material_id: +b.dataset.ba}}); location.hash = `#/arbeitsschutz/ba/${n.id}`; } catch (e) { toast(e.message, true); } });
  if ($("#gsNeu")) $("#gsNeu").onclick = async () => { const m = await materialWaehlen(["beschichtung", "chemie"], "Material als Gefahrstoff kennzeichnen"); if (m) location.hash = `#/mat/${m.id}/sicherheit`; };
}

// Material › Datenblätter & Sicherheit
async function asMaterialSicherheit(m) {
  const z = $("#inhalt");
  let d;
  try { d = await api("arbeitsschutz/gefahrstoff/" + m.id); } catch (e) { z.innerHTML = `<div class="leer">${esc(e.message)}</div>`; return; }
  const kann = asDarf() || darf("material", 2);
  const g = d.gefahrstoff;
  const zeichnen = () => {
    const akt = d.dateien.filter(x => x.aktuell), alt = d.dateien.filter(x => !x.aktuell);
    const dz = x => `<tr><td>${esc(x.art_name)}</td><td><a href="/api/arbeitsschutz/datei/${x.id}" target="_blank">${esc(x.titel)}</a><div class="hinweis">${esc(x.dateiname)} · ${groesse(x.groesse)}</div></td>
      <td>${kann ? `<input type="date" data-aus="${x.id}" value="${esc(x.ausgabe)}" title="Ausgabedatum laut Datenblatt">` : datum(x.ausgabe)}</td><td class="hinweis">${datum(x.angelegt)}</td>
      <td>${kann ? `<button class="aktion" data-del="${x.id}" title="Datei löschen">${ic("loeschen")}</button>` : ""}</td></tr>`;
    z.innerHTML = `<div class="titel"><h2>Datenblätter &amp; Sicherheit</h2><span class="speicher"></span></div>
      <div class="sektion">Datenblätter</div>
      ${akt.length ? `<table class="liste"><tr><th>Art</th><th>Datei</th><th>Ausgabe vom</th><th>hochgeladen</th><th></th></tr>${akt.map(dz).join("")}</table>` : `<p class="hinweis">Noch kein Datenblatt hinterlegt.</p>`}
      ${kann ? `<div class="ablage" id="asAbl" style="margin-top:8px">Sicherheitsdatenblatt oder technisches Merkblatt (PDF) hierher ziehen oder <label style="text-decoration:underline;cursor:pointer">auswählen<input type="file" id="asDatei" accept=".pdf,image/*" hidden></label>
        <div style="margin-top:6px"><select id="asArt">${Object.entries(d.auswahl.datei_arten).filter(([k]) => ["sdb", "tdb", "ba", "sonst"].includes(k)).map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join("")}</select>
        <span class="hinweis">Ein neues Sicherheitsdatenblatt ersetzt das bisherige; das alte bleibt als frühere Fassung erhalten.</span></div></div>` : ""}
      ${alt.length ? `<details style="margin-top:8px"><summary class="hinweis">Frühere Fassungen (${alt.length})</summary><table class="liste">${alt.map(dz).join("")}</table></details>` : ""}
      <div class="sektion" style="margin-top:16px">Gefahrstoff</div>
      <div class="form" id="asG">
        ${zeile("Gefahrstoff", `<label style="padding-top:5px"><input type="checkbox" data-f="gefahrstoff" ${g.gefahrstoff ? "checked" : ""} ${kann ? "" : "disabled"}> kennzeichnungspflichtig (Gefahrenpiktogramm oder H-Sätze im Sicherheitsdatenblatt) – erscheint im Gefahrstoffverzeichnis</label>`, true)}
        <div class="as-gs" style="display:${g.gefahrstoff ? "contents" : "none"}">
        ${zeile("H-Sätze", `<input data-f="h_saetze" value="${esc(g.h_saetze)}" placeholder="z. B. H226, H336, EUH066 (Abschnitt 2 des Sicherheitsdatenblatts)" ${kann ? "" : "readonly"}>${kann ? `<button class="btn" id="asGhsV" title="Piktogramme aus den H-Sätzen vorschlagen">Piktogramme vorschlagen</button>` : ""}`, true)}
        ${zeile("Piktogramme", `<div class="as-ghs">${["GHS01", "GHS02", "GHS03", "GHS04", "GHS05", "GHS06", "GHS07", "GHS08", "GHS09"].map(c => `<button class="${g.ghs.includes(c) ? "an" : ""}" data-ghs="${c}" ${kann ? "" : "disabled"}>${asZeichen(c, 40)}</button>`).join("")}</div>`, true)}
        ${zeile("Signalwort", `<select data-f="signalwort" ${kann ? "" : "disabled"}>${optsKV([["", "–"], ["Achtung", "Achtung"], ["Gefahr", "Gefahr"]], g.signalwort)}</select>`)}
        ${zeile("P-Sätze", `<input data-f="p_saetze" value="${esc(g.p_saetze)}" placeholder="Sicherheitshinweise, z. B. P210, P280" ${kann ? "" : "readonly"}>`)}
        ${zeile("Lagerklasse", `<select data-f="lagerklasse" ${kann ? "" : "disabled"}>${opts(d.auswahl.lagerklassen, g.lagerklasse, "–")}</select>`)}
        ${zeile("Wassergefährdung", `<select data-f="wgk" ${kann ? "" : "disabled"}>${opts(d.auswahl.wgk, g.wgk, "–")}</select>`)}
        ${zeile("Menge", `<input data-f="menge" value="${esc(g.menge)}" placeholder="Mengenbereich im Betrieb, z. B. bis 50 l/Jahr" ${kann ? "" : "readonly"}>`)}
        ${zeile("Arbeitsbereich", `<input data-f="bereich" value="${esc(g.bereich)}" placeholder="wo damit gearbeitet wird, z. B. Lackierraum" ${kann ? "" : "readonly"}>`)}
        ${zeile("Schutzausrüstung", `<input data-f="psa" value="${esc(g.psa)}" placeholder="laut Abschnitt 8, z. B. Nitrilhandschuhe, Schutzbrille, Atemschutz A2" ${kann ? "" : "readonly"}>`, true)}
        ${zeile("Ersatzstoffprüfung", `<textarea data-f="ersatz" rows="2" placeholder="Gibt es ein weniger gefährliches Produkt oder Verfahren? Ergebnis kurz festhalten." ${kann ? "" : "readonly"}>${esc(g.ersatz)}</textarea>`, true)}
        ${zeile("Betriebsanweisung", d.ba ? `<a href="#/arbeitsschutz/ba/${d.ba.id}" style="padding-top:5px">${esc(d.ba.nummer)} ${esc(d.ba.titel)}</a> ${asStatus(d.ba.status)}` : asDarf() ? `<button class="btn" id="asBaNeu">Betriebsanweisung anlegen</button>` : `<span class="hinweis" style="padding-top:5px">noch keine</span>`, true)}
        </div>
      </div>`;
    if (!kann) return;
    autospeichern($("#asG"), "arbeitsschutz/gefahrstoff/" + m.id, (r, x) => { Object.assign(g, r); if ("gefahrstoff" in x) $(".as-gs").style.display = r.gefahrstoff ? "contents" : "none"; });
    $$("[data-ghs]").forEach(b => b.onclick = async () => {
      const c = b.dataset.ghs; g.ghs = g.ghs.includes(c) ? g.ghs.filter(x => x !== c) : [...g.ghs, c].sort();
      b.classList.toggle("an", g.ghs.includes(c)); await api("arbeitsschutz/gefahrstoff/" + m.id, {method: "PUT", body: {ghs: g.ghs}}); asSpeicherStatus("gespeichert ✓", "ok");
    });
    if ($("#asGhsV")) $("#asGhsV").onclick = async () => {
      const r = await api("arbeitsschutz/ghs?h=" + encodeURIComponent($("[data-f=h_saetze]").value));
      if (!r.ghs.length) return toast("Aus diesen H-Sätzen ergibt sich kein Piktogramm.");
      g.ghs = r.ghs; await api("arbeitsschutz/gefahrstoff/" + m.id, {method: "PUT", body: {ghs: g.ghs}}); zeichnen(); toast("Vorschlag übernommen – bitte mit Abschnitt 2 des Sicherheitsdatenblatts abgleichen.");
    };
    if ($("#asBaNeu")) $("#asBaNeu").onclick = async () => { try { const n = await api("arbeitsschutz/ba", {method: "POST", body: {art: "gefahrstoff", material_id: m.id}}); location.hash = `#/arbeitsschutz/ba/${n.id}`; } catch (e) { toast(e.message, true); } };
    const hoch = async files => {
      for (const f of files) {
        try { d.dateien.unshift(await api("arbeitsschutz/dateien", {method: "POST", body: {material_id: m.id, art: $("#asArt").value, dateiname: f.name, titel: f.name.replace(/\.[^.]+$/, ""), daten: await dateiAlsBase64(f)}})); }
        catch (e) { toast(e.message, true); }
      }
      d.dateien = await api("arbeitsschutz/dateien?material=" + m.id); toast("Gespeichert"); zeichnen();
    };
    $("#asDatei").onchange = e => hoch([...e.target.files]);
    const ab = $("#asAbl");
    ab.ondragover = e => { e.preventDefault(); ab.classList.add("drueber"); };
    ab.ondragleave = () => ab.classList.remove("drueber");
    ab.ondrop = e => { e.preventDefault(); ab.classList.remove("drueber"); hoch([...e.dataTransfer.files]); };
    $$("[data-aus]").forEach(i => i.onchange = () => api("arbeitsschutz/dateien/" + i.dataset.aus, {method: "PUT", body: {ausgabe: i.value}}).then(() => asSpeicherStatus("gespeichert ✓", "ok")));
    $$("[data-del]").forEach(b => b.onclick = async () => { if (!await frage("Datei löschen?")) return; await api("arbeitsschutz/dateien/" + b.dataset.del, {method: "DELETE"}); d.dateien = await api("arbeitsschutz/dateien?material=" + m.id); zeichnen(); });
  };
  zeichnen();
}

// Auftrag › Werkstatt: Gefahrstoffe und Datenblätter der Materialien
async function asAuftragBox(box, a) {
  if (!box || !darf("arbeitsschutz")) return;
  let l = [];
  try { l = await api("arbeitsschutz/auftrag/" + a.id); } catch (e) { return; }
  if (!l.length) { box.innerHTML = ""; return; }
  box.innerHTML = `<div class="sektion" style="margin-top:18px">Gefahrstoffe und Datenblätter</div>
    <div class="kachel as-auftrag">${l.map(x => `<div class="as-az"><div><b>${esc(x.name)}</b> <span class="hinweis">${esc(x.nummer)}</span>${x.gefahrstoff ? ` <span class="rot-t">Gefahrstoff</span>` : ""}
      ${x.ghs.map(g => asZeichen(g, 26)).join(" ")}${x.psa ? `<div class="hinweis">Schutzausrüstung: ${esc(x.psa)}</div>` : ""}</div>
      <div class="as-az-l">${x.dateien.map(dd => `<a class="btn" href="/api/arbeitsschutz/datei/${dd.id}" target="_blank">${dd.art === "sdb" ? "Sicherheitsdatenblatt" : dd.art === "tdb" ? "Technisches Merkblatt" : esc(dd.art_name)}</a>`).join("")}
        ${x.ba ? `<a class="btn" href="/druck/arbeitsschutz/ba/${x.ba.id}" target="_blank">Betriebsanweisung</a>` : ""}</div></div>`).join("")}</div>`;
}

// Werkzeug-Dialog: Gefährdungsbeurteilung, Betriebsanweisung, Unterweisung zur Maschine
async function asWerkzeugInfo(box, wid) {
  if (!box || !darf("arbeitsschutz")) return;
  let d;
  try { d = await api("arbeitsschutz/werkzeug/" + wid); } catch (e) { return; }
  const teile = [...d.gb.map(g => `<a href="#/arbeitsschutz/gb/${g.id}">${esc(g.nummer)} Gefährdungsbeurteilung</a> <span class="hinweis">${esc(g.status_name)}</span>`),
    ...d.ba.map(b => `<a href="/druck/arbeitsschutz/ba/${b.id}" target="_blank">${esc(b.nummer)} Betriebsanweisung</a> <span class="hinweis">${esc(b.status_name)}</span>`),
    ...d.themen.map(t => `<a href="#/arbeitsschutz/thema/${t.id}">Unterweisung: ${esc(t.titel)}</a>`)];
  box.innerHTML = `<div class="sektion">Arbeitsschutz</div><div class="hinweis" style="line-height:1.8">${teile.join("<br>") || "Noch keine Gefährdungsbeurteilung zu diesem Arbeitsmittel."}
    ${!d.gb.length && asDarf() ? ` <a href="#" id="wzGb">Jetzt anlegen</a>` : ""}</div>`;
  const a = $("#wzGb", box);
  if (a) a.onclick = async e => { e.preventDefault(); $$(".modal-hg").forEach(x => x.remove());
    const g = await api("arbeitsschutz/gb", {method: "POST", body: {art: "maschine", werkzeug_ids: [wid], vorlage: d.vorschlag}}).catch(x => { toast(x.message, true); });
    if (g) location.hash = `#/arbeitsschutz/gb/${g.id}`; };
}

// ---------------------------------------------------------------------
//  Erste Hilfe & Notfall
// ---------------------------------------------------------------------
async function asNotfall() {
  asKopf("notfall");
  const z = $("#inhalt");
  const [o, v, qs] = await Promise.all([api("arbeitsschutz/organisation"), asVorlagen(), api("arbeitsschutz/qualifikationen")]);
  const eh = qs.filter(q => q.art === "Ersthelfer" && q.gueltig).map(q => q.name);
  let vb = [];
  if (ICH.rechte.inhaber) vb = await api("arbeitsschutz/verbandbuch");
  const ro = !asDarf();
  z.innerHTML = `<div class="titel"><h2>Erste Hilfe &amp; Notfall</h2><span class="speicher"></span><div class="rechts"><a class="btn" href="/druck/arbeitsschutz/notfall" target="_blank">Aushang ansehen</a><a class="btn" href="/druck/arbeitsschutz/notfall.pdf" target="_blank">📄 PDF</a></div></div>
    <div class="sektion">Notfall-Aushang</div>
    <p class="hinweis" style="margin-top:0">Rufnummern und Ansprechpartner für den Aushang neben dem Erste-Hilfe-Material.${eh.length ? ` Ersthelfer laut Nachweisen: ${esc(eh.join(", "))} – erscheinen im Aushang, solange hier keine eingetragen sind.` : ""}</p>
    <div class="form" id="nfF">${v.notfall.map(([k, l]) => zeile(esc(l), `<input data-nf="${k}" value="${esc(o.notfall[k] || "")}" ${ro ? "readonly" : ""}>`)).join("")}</div>
    <div class="sektion" style="margin-top:18px">Verbandbuch</div>
    <p class="hinweis" style="margin-top:0">Jede Erste-Hilfe-Leistung wird dokumentiert und fünf Jahre aufbewahrt. Die Einträge sind vertraulich und nur für den Inhaber sichtbar. Mitarbeiter können auch in der Stempeluhr eintragen.</p>
    <button class="btn prim" id="vbNeu">＋ Erste-Hilfe-Leistung eintragen</button>
    ${ICH.rechte.inhaber ? `<table class="liste" style="margin-top:10px"><tr><th>Wann</th><th>Wer</th><th>Verletzung</th><th>Hergang</th><th>Maßnahmen</th><th>Ersthelfer</th><th>Ausfall / Unfallanzeige</th><th></th></tr>
      ${vb.map(x => `<tr><td class="nw">${datum(x.zeit)} ${String(x.zeit).slice(11, 16)}</td><td>${esc(x.name)}</td><td>${esc(x.verletzung)}</td><td>${esc(x.hergang)}${x.ort ? `<div class="hinweis">${esc(x.ort)}</div>` : ""}${x.zeugen ? `<div class="hinweis">Zeugen: ${esc(x.zeugen)}</div>` : ""}</td>
        <td>${esc(x.massnahmen)}</td><td>${esc(x.helfer)}</td>
        <td>${x.au_tage == null ? `<span class="hinweis">nicht erfasst</span>` : `${x.au_tage} Tag${x.au_tage === 1 ? "" : "e"} arbeitsunfähig`}${x.au_tage > 3 ? (x.anzeige_am ? `<div class="hinweis">Unfallanzeige am ${datum(x.anzeige_am)}</div>` : `<div style="color:var(--rot);font-weight:600">Unfallanzeige fällig</div>`) : ""}
          <div><a href="#" data-vau="${x.id}" class="hinweis">eintragen</a></div></td><td>${x.abgelaufen ? `<button class="aktion" data-vdel="${x.id}" title="älter als fünf Jahre – löschen">${ic("loeschen")}</button>` : ""}</td></tr>`).join("") || `<tr><td colspan="8" class="leer">Keine Einträge.</td></tr>`}</table>
      <p class="hinweis">Fällt die verletzte Person <b>mehr als drei Tage</b> aus (der Unfalltag zählt nicht mit) oder verläuft der Unfall tödlich, ist er der Berufsgenossenschaft binnen drei Tagen anzuzeigen (§ 193 SGB VII). Dafür hier die Ausfalltage nachtragen – die Übersicht erinnert, bis das Datum der Unfallanzeige eingetragen ist.</p>` : ""}`;
  if (!ro) {
    const sp = asDebounce(async (k, val) => { try { await api("arbeitsschutz/organisation", {method: "PUT", body: {notfall: {[k]: val}}}); asSpeicherStatus("gespeichert ✓", "ok"); } catch (e) { toast(e.message, true); } }, 500);
    $$("[data-nf]").forEach(i => i.oninput = () => { asSpeicherStatus("…"); sp(i.dataset.nf, i.value); });
  }
  $("#vbNeu").onclick = () => asVerbandbuchEintrag();
  $$("[data-vau]").forEach(a => a.onclick = async ev => {
    ev.preventDefault();
    const x = vb.find(y => y.id === +a.dataset.vau);
    const e = await modal("Ausfall und Unfallanzeige", `
      ${zeile("Arbeitsunfähig", `<input name="au_tage" value="${x.au_tage == null ? "" : x.au_tage}" style="max-width:90px"> <span class="hinweis" style="padding-top:5px">Tage (0 = weitergearbeitet; der Unfalltag zählt nicht mit)</span>`)}
      ${zeile("Unfallanzeige am", `<input type="date" name="anzeige_am" value="${esc(x.anzeige_am || "")}"><span class="hinweis">Datum, an dem die Anzeige an die Berufsgenossenschaft ging</span>`)}`, "Speichern");
    if (!e) return;
    try { await api("arbeitsschutz/verbandbuch/" + x.id, {method: "PUT", body: e}); asNotfall(); } catch (f) { toast(f.message, true); }
  });
  $$("[data-vdel]").forEach(b => b.onclick = async () => { if (await frage("Eintrag löschen? (älter als fünf Jahre)")) { await api("arbeitsschutz/verbandbuch/" + b.dataset.vdel, {method: "DELETE"}); asNotfall(); } });
}
async function asVerbandbuchEintrag() {
  const jetzt = new Date(); const iso = `${heute()}T${String(jetzt.getHours()).padStart(2, "0")}:${String(jetzt.getMinutes()).padStart(2, "0")}`;
  const e = await modal("Erste-Hilfe-Leistung eintragen", `
    ${zeile("Wann", `<input type="datetime-local" name="zeit" value="${iso}">`)}${zeile("Wo", `<input name="ort" placeholder="Ort, Arbeitsbereich">`)}
    ${zeile("Wer", `<input name="name" placeholder="Name der verletzten Person">`)}${zeile("Hergang", `<textarea name="hergang" rows="2"></textarea>`)}
    ${zeile("Verletzung", `<input name="verletzung" placeholder="Art und Umfang">`)}${zeile("Zeugen", `<input name="zeugen">`)}
    ${zeile("Erste Hilfe", `<input type="datetime-local" name="hilfe_zeit" value="${iso}">`)}${zeile("Maßnahmen", `<input name="massnahmen" placeholder="z. B. Wunde versorgt, Pflaster">`)}
    ${zeile("Ersthelfer", `<input name="helfer" value="${esc(ICH.name || "")}">`)}`, "Eintragen");
  if (!e) return;
  try { await api("arbeitsschutz/verbandbuch", {method: "POST", body: e}); toast("Eingetragen"); if (location.hash.includes("notfall")) asNotfall(); } catch (x) { toast(x.message, true); }
}

// ---------------------------------------------------------------------
//  Beauftragte & Nachweise
// ---------------------------------------------------------------------
async function asNachweise() {
  asKopf("nachweise");
  const z = $("#inhalt");
  const [o, qs, mas, v] = await Promise.all([api("arbeitsschutz/organisation"), api("arbeitsschutz/qualifikationen"), api("arbeitsschutz/mitarbeiter"), asVorlagen()]);
  const org = o.organisation, b = o.bedarf, ro = !asDarf();
  const BETR = ["Regelbetreuung (Fachkraft für Arbeitssicherheit und Betriebsarzt mit festen Einsatzzeiten)", "Unternehmermodell (alternative bedarfsorientierte Betreuung)"];
  z.innerHTML = `<div class="titel"><h2>Beauftragte &amp; Nachweise</h2><span class="speicher"></span></div>
    <div class="sektion">Organisation</div>
    <div class="form" id="orgF">
      ${zeile("Betreuung", `<select data-o="betreuung" ${ro ? "disabled" : ""}>${opts(BETR, org.betreuung, "bitte wählen")}</select>`, true)}
      ${zeile("Seit / Schulung", `<input data-o="betreuung_seit" value="${esc(org.betreuung_seit)}" placeholder="z. B. Unternehmerschulung vom …" ${ro ? "readonly" : ""}>`)}
      ${zeile("Berufsgenossenschaft", `<input data-o="bg" value="${esc(org.bg)}" placeholder="z. B. BGHM" ${ro ? "readonly" : ""}><input data-o="bg_nr" value="${esc(org.bg_nr)}" placeholder="Mitgliedsnummer" style="flex:0 0 150px" ${ro ? "readonly" : ""}>`)}
      ${zeile("Fachkraft für Arbeitssicherheit", `<input data-o="fasi" value="${esc(org.fasi)}" placeholder="Name, Firma, Telefon" ${ro ? "readonly" : ""}>`)}
      ${zeile("Betriebsarzt", `<input data-o="betriebsarzt" value="${esc(org.betriebsarzt)}" placeholder="Name, Praxis, Telefon" ${ro ? "readonly" : ""}>`)}
      ${zeile("Arbeitsbereiche", `<textarea data-o="bereiche" rows="3" placeholder="je Zeile ein Bereich, z. B. Maschinenraum, Bankraum, Lackierraum, Lager, Montage, Büro" ${ro ? "readonly" : ""}>${esc(org.bereiche.join("\n"))}</textarea>`, true)}
      ${zeile("Arbeitsmed. Vorsorge", `<input data-o="vorsorge" value="${esc(org.vorsorge)}" placeholder="z. B. Angebotsvorsorge Holzstaub, Lärm – wer, wann" ${ro ? "readonly" : ""}>`, true)}
      ${zeile("Prüfung elektr. Geräte", `<input data-o="pruefung_elektro" value="${esc(org.pruefung_elektro)}" placeholder="wer prüft, letzte Prüfung" ${ro ? "readonly" : ""}>`, true)}
    </div>
    <p class="hinweis">Bei ${b.beschaeftigte} Beschäftigten: mindestens ${b.ersthelfer} Ersthelfer, ${b.brandschutzhelfer} Brandschutzhelfer${b.sibe ? ", ein Sicherheitsbeauftragter" : ""}.</p>
    <div class="titel" style="margin-top:16px"><h3 style="margin:0">Beauftragte, Schulungen und Berechtigungen</h3><div class="rechts">${ro ? "" : `<button class="btn prim" id="qNeu">＋ Nachweis</button>`}</div></div>
    <table class="liste"><tr><th>Person</th><th>Art</th><th>Datum</th><th>gültig bis</th><th>Nachweis</th><th></th></tr>
      ${qs.map(q => `<tr><td>${esc(q.name)}</td><td>${esc(q.art)}${q.bemerkung ? `<div class="hinweis">${esc(q.bemerkung)}</div>` : ""}</td><td>${datum(q.datum)}</td>
        <td>${q.gueltig_bis ? `<span style="${q.gueltig ? "" : "color:var(--rot);font-weight:600"}">${datum(q.gueltig_bis)}</span>` : "–"}</td>
        <td>${q.dateien.map(dd => `<a href="/api/arbeitsschutz/datei/${dd.id}" target="_blank">${esc(dd.titel)}</a>`).join(", ")}${ro ? "" : ` <label class="hinweis" style="cursor:pointer;text-decoration:underline">hochladen<input type="file" data-qd="${q.id}" hidden></label>`}</td>
        <td>${ro ? "" : `<button class="aktion" data-qe="${q.id}" title="Bearbeiten">${ic("anrede")}</button> <button class="aktion" data-qdel="${q.id}" title="Löschen">${ic("loeschen")}</button>`}</td></tr>`).join("") || `<tr><td colspan="6" class="leer">Noch keine Nachweise – zum Beispiel die Ersthelfer mit Datum der letzten Aus- oder Fortbildung.</td></tr>`}</table><div id="asVors"></div><div id="asExpo"></div>`;
  if (ro) return;
  const sp = asDebounce(async (k, val) => { try { await api("arbeitsschutz/organisation", {method: "PUT", body: {organisation: {[k]: val}}}); asSpeicherStatus("gespeichert ✓", "ok"); } catch (e) { toast(e.message, true); } }, 600);
  $$("[data-o]").forEach(i => i.oninput = i.onchange = () => { asSpeicherStatus("…"); sp(i.dataset.o, i.dataset.o === "bereiche" ? i.value.split("\n").map(x => x.trim()).filter(Boolean) : i.value); });
  const dialog = async q => {
    const e = await modal(q ? "Nachweis bearbeiten" : "Neuer Nachweis", `
      ${zeile("Person", `<select name="mitarbeiter_id"><option value="">andere Person …</option>${mas.map(m => `<option value="${m.id}" ${q && q.mitarbeiter_id === m.id ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select>`)}
      ${zeile("Name", `<input name="name" value="${esc(q && !q.mitarbeiter_id ? q.name : "")}" placeholder="nur bei anderer Person">`)}
      ${zeile("Art", `<select name="art">${opts(Object.keys(v.quali), q ? q.art : "Ersthelfer")}</select>`)}
      ${zeile("Datum", `<input type="date" name="datum" value="${esc(q ? q.datum : "")}">`)}
      ${zeile("gültig bis", `<input type="date" name="gueltig_bis" value="${esc(q ? q.gueltig_bis : "")}"><span class="hinweis">leer = automatisch (Ersthelfer 2 Jahre, Brandschutzhelfer 3 Jahre)</span>`)}
      ${zeile("Bemerkung", `<input name="bemerkung" value="${esc(q ? q.bemerkung : "")}">`)}`, q ? "Speichern" : "Anlegen");
    if (!e) return;
    try { await api("arbeitsschutz/qualifikationen" + (q ? "/" + q.id : ""), {method: q ? "PUT" : "POST", body: e}); asNachweise(); } catch (x) { toast(x.message, true); }
  };
  $("#qNeu").onclick = () => dialog(null);
  $$("[data-qe]").forEach(b => b.onclick = () => dialog(qs.find(q => q.id === +b.dataset.qe)));
  $$("[data-qdel]").forEach(b => b.onclick = async () => { if (await frage("Nachweis löschen?")) { await api("arbeitsschutz/qualifikationen/" + b.dataset.qdel, {method: "DELETE"}); asNachweise(); } });
  $$("[data-qd]").forEach(i => i.onchange = async () => {
    const f = i.files[0]; if (!f) return;
    try { await api("arbeitsschutz/dateien", {method: "POST", body: {qualifikation_id: +i.dataset.qd, art: "nachweis", dateiname: f.name, titel: f.name.replace(/\.[^.]+$/, ""), daten: await dateiAlsBase64(f)}}); asNachweise(); }
    catch (e) { toast(e.message, true); }
  });
  asVorsorge(mas); asExposition(mas);
}

// Vorsorgekartei (arbeitsmedizinische Vorsorge): wer, wann, aus welchem Anlass – keine Befunde
async function asVorsorge(mas) {
  const box = $("#asVors"); if (!box) return;
  let d; try { d = await api("arbeitsschutz/vorsorge"); } catch (e) { return; }
  const l = d.eintraege;
  box.innerHTML = `<div class="titel" style="margin-top:22px"><h3 style="margin:0">Vorsorgekartei (arbeitsmedizinische Vorsorge)</h3><div class="rechts"><button class="btn prim" id="voNeu">＋ Vorsorge</button></div></div>
    <p class="hinweis" style="margin-top:0">Festgehalten wird, dass, wann und aus welchem Anlass eine Vorsorge stattgefunden hat oder angeboten wurde – <b>keine Befunde oder Diagnosen</b>. Welche Vorsorge Pflicht ist oder angeboten werden muss, ergibt die Gefährdungsbeurteilung zusammen mit dem Betriebsarzt. Die Kartei wird bis zum Ende der Beschäftigung geführt; beim Ausscheiden erhält der Mitarbeiter eine Kopie.</p>
    <table class="liste"><tr><th>Mitarbeiter</th><th>Anlass</th><th>Art</th><th>Datum</th><th>Stand</th><th>nächste</th><th>Arzt</th><th></th></tr>
      ${l.map(x => `<tr><td>${esc(x.name)}${x.ausgeschieden ? ` <span class="hinweis">(ausgeschieden)</span>` : ""}</td><td>${esc(x.anlass)}${x.bemerkung ? `<div class="hinweis">${esc(x.bemerkung)}</div>` : ""}</td><td>${esc(x.art)}</td>
        <td class="nw">${datum(x.datum)}</td><td>${esc(x.status)}</td><td class="nw">${x.naechste ? `<span style="${x.faellig === "ueberfaellig" ? "color:var(--rot);font-weight:600" : x.faellig === "bald" ? "color:#9a7400;font-weight:600" : ""}">${datum(x.naechste)}</span>` : "–"}</td>
        <td>${esc(x.arzt)}</td><td class="nw"><button class="aktion" data-voe="${x.id}" title="Bearbeiten">${ic("anrede")}</button> <button class="aktion" data-vodel="${x.id}" title="Löschen">${ic("loeschen")}</button></td></tr>`).join("") || `<tr><td colspan="8" class="leer">Noch keine Einträge.</td></tr>`}</table>`;
  const dialog = async x => {
    const e = await modal(x ? "Vorsorge bearbeiten" : "Vorsorge eintragen", `
      ${zeile("Mitarbeiter", `<select name="mitarbeiter_id" ${x ? "disabled" : ""}><option value="">bitte wählen</option>${mas.map(m => `<option value="${m.id}" ${x && x.mitarbeiter_id === m.id ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select>`)}
      ${zeile("Anlass", `<input name="anlass" list="voAnl" value="${esc(x ? x.anlass : "")}" placeholder="z. B. Lärm"><datalist id="voAnl">${d.anlaesse.map(a => `<option value="${esc(a)}">`).join("")}</datalist>`)}
      ${zeile("Art", `<select name="art">${opts(d.arten, x ? x.art : "Angebotsvorsorge")}</select>`)}
      ${zeile("Stand", `<select name="status">${opts(d.status, x ? x.status : "durchgeführt")}</select>`)}
      ${zeile("Datum", `<input type="date" name="datum" value="${esc(x ? x.datum : heute())}">`)}
      ${zeile("nächste Vorsorge", `<input type="date" name="naechste" value="${esc(x ? x.naechste : "")}"><span class="hinweis">laut Bescheinigung des Arztes; erscheint rechtzeitig in der Übersicht</span>`)}
      ${zeile("Arzt", `<input name="arzt" value="${esc(x ? x.arzt : "")}" placeholder="Betriebsarzt, Praxis">`)}
      ${zeile("Bemerkung", `<input name="bemerkung" value="${esc(x ? x.bemerkung : "")}" placeholder="keine Befunde eintragen">`)}`, x ? "Speichern" : "Eintragen");
    if (!e) return;
    try { await api("arbeitsschutz/vorsorge" + (x ? "/" + x.id : ""), {method: x ? "PUT" : "POST", body: e}); asVorsorge(mas); } catch (f) { toast(f.message, true); }
  };
  $("#voNeu").onclick = () => dialog(null);
  $$("[data-voe]", box).forEach(b => b.onclick = () => dialog(l.find(x => x.id === +b.dataset.voe)));
  $$("[data-vodel]", box).forEach(b => b.onclick = async () => { if (await frage("Eintrag der Vorsorgekartei löschen?")) { await api("arbeitsschutz/vorsorge/" + b.dataset.vodel, {method: "DELETE"}); asVorsorge(mas); } });
}

// Expositionsverzeichnis: Tätigkeiten mit krebserzeugenden Stoffen (z. B. Eichen- und Buchenholzstaub), 40 Jahre aufzubewahren
async function asExposition(mas) {
  const box = $("#asExpo"); if (!box) return;
  let d; try { d = await api("arbeitsschutz/exposition"); } catch (e) { return; }
  const l = d.eintraege;
  box.innerHTML = `<div class="titel" style="margin-top:22px"><h3 style="margin:0">Expositionsverzeichnis (krebserzeugende Stoffe)</h3><div class="rechts"><button class="btn prim" id="exNeu">＋ Exposition</button></div></div>
    <p class="hinweis" style="margin-top:0">Für Beschäftigte, die bei ihrer Tätigkeit krebserzeugenden Stoffen ausgesetzt sind – im Holzhandwerk vor allem Staub von Eiche und Buche –, verlangt die Gefahrstoffverordnung (§ 10a) ein Verzeichnis mit Höhe und Dauer der Exposition. Ob es im Betrieb nötig ist, ergibt die Gefährdungsbeurteilung (Auskunft: Berufsgenossenschaft, Fachkraft für Arbeitssicherheit). Die Einträge werden ${d.jahre} Jahre nach Ende der Exposition aufbewahrt; beim Ausscheiden erhält der Mitarbeiter einen Auszug.</p>
    <table class="liste"><tr><th>Mitarbeiter</th><th>Stoff</th><th>Tätigkeit</th><th>von</th><th>bis</th><th>Höhe</th><th>Häufigkeit / Dauer</th><th></th></tr>
      ${l.map(x => `<tr><td>${esc(x.name)}</td><td>${esc(x.stoff)}${x.bemerkung ? `<div class="hinweis">${esc(x.bemerkung)}</div>` : ""}</td><td>${esc(x.taetigkeit)}</td><td class="nw">${datum(x.von)}</td>
        <td class="nw">${x.bis ? datum(x.bis) + `<div class="hinweis">aufbewahren bis ${datum(x.aufbewahren_bis)}</div>` : "läuft"}</td><td>${esc(x.hoehe)}</td><td>${esc(x.haeufigkeit)}</td>
        <td class="nw"><button class="aktion" data-exe="${x.id}" title="Bearbeiten">${ic("anrede")}</button>${x.loeschbar ? ` <button class="aktion" data-exdel="${x.id}" title="Löschen">${ic("loeschen")}</button>` : ""}</td></tr>`).join("") || `<tr><td colspan="8" class="leer">Keine Einträge.</td></tr>`}</table>`;
  const dialog = async x => {
    const e = await modal(x ? "Exposition bearbeiten" : "Exposition eintragen", `
      ${zeile("Mitarbeiter", `<select name="mitarbeiter_id" ${x ? "disabled" : ""}><option value="">bitte wählen</option>${mas.map(m => `<option value="${m.id}" ${x && x.mitarbeiter_id === m.id ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select>`)}
      ${zeile("Stoff", `<input name="stoff" list="exSt" value="${esc(x ? x.stoff : "")}" placeholder="z. B. Hartholzstaub (Eiche, Buche)"><datalist id="exSt">${d.stoffe.map(a => `<option value="${esc(a)}">`).join("")}</datalist>`)}
      ${zeile("Tätigkeit", `<input name="taetigkeit" value="${esc(x ? x.taetigkeit : "")}" placeholder="z. B. Schleifen von Eiche, Maschinenraum">`)}
      ${zeile("von", `<input type="date" name="von" value="${esc(x ? x.von : "")}">`)}
      ${zeile("bis", `<input type="date" name="bis" value="${esc(x ? x.bis : "")}"><span class="hinweis">leer = dauert an</span>`)}
      ${zeile("Höhe", `<input name="hoehe" value="${esc(x ? x.hoehe : "")}" placeholder="z. B. Messwert in mg/m³ oder „Grenzwert eingehalten laut Messung vom …“">`)}
      ${zeile("Häufigkeit / Dauer", `<input name="haeufigkeit" value="${esc(x ? x.haeufigkeit : "")}" placeholder="z. B. etwa 6 Stunden je Woche">`)}
      ${zeile("Bemerkung", `<input name="bemerkung" value="${esc(x ? x.bemerkung : "")}">`)}`, x ? "Speichern" : "Eintragen");
    if (!e) return;
    try { await api("arbeitsschutz/exposition" + (x ? "/" + x.id : ""), {method: x ? "PUT" : "POST", body: e}); asExposition(mas); } catch (f) { toast(f.message, true); }
  };
  $("#exNeu").onclick = () => dialog(null);
  $$("[data-exe]", box).forEach(b => b.onclick = () => dialog(l.find(x => x.id === +b.dataset.exe)));
  $$("[data-exdel]", box).forEach(b => b.onclick = async () => { if (await frage("Eintrag im Expositionsverzeichnis löschen?")) { try { await api("arbeitsschutz/exposition/" + b.dataset.exdel, {method: "DELETE"}); asExposition(mas); } catch (f) { toast(f.message, true); } } });
}

// Startseite: Erinnerung an fällige und bald fällige Punkte. Sie lässt sich unter Einstellungen › Programm ausschalten (nur sie).
// Ist sie aus und sind Mitarbeiter angelegt, steht für den Inhaber stattdessen der Hinweis, sie wieder einzuschalten.
async function asStartHinweis(box, st) {
  if (!box) return;
  if (st ? st.anzeigen === false : E.start_arbeitsschutz === false) {   // der Stand der Startseite ist frischer als die geladenen Einstellungen
    if (st && st.mitarbeiter && ICH.rechte.inhaber) box.innerHTML = `<div class="kachel" id="stASAus" style="border-left:4px solid #c9a227;margin-bottom:12px">Arbeitsschutz: Die Erinnerungen auf der Startseite sind ausgeschaltet, ${st.mitarbeiter === 1 ? "es ist aber 1 Mitarbeiter angelegt" : `es sind aber ${st.mitarbeiter} Mitarbeiter angelegt`}. Mit Beschäftigten gehören Gefährdungsbeurteilung und Unterweisungen zu den Pflichten des Arbeitgebers; bitte wieder einschalten. <a href="#/einstellungen/programm">Einstellungen › Programm ›</a></div>`;
    return;
  }
  if (!darf("arbeitsschutz", 2)) return;
  try {
    const d = await api("arbeitsschutz/uebersicht");
    const rot = d.punkte.filter(p => p.stufe === "rot").length, gelb = d.punkte.filter(p => p.stufe === "gelb").length;
    if (!rot && !gelb) return;
    box.innerHTML = `<div class="kachel" id="stASHinweis" style="border-left:4px solid ${rot ? "var(--rot)" : "#c9a227"};margin-bottom:12px">Arbeitsschutz: ${rot ? `${rot} Punkt(e) fällig` : ""}${rot && gelb ? ", " : ""}${gelb ? `${gelb} bald fällig bzw. offen` : ""} – ${esc(d.punkte[0].text)} <a href="#/arbeitsschutz">Zur Übersicht ›</a></div>`;
  } catch (e) {}
}
