// =====================================================================
//  Rapport (Tablet): Stunden, Material, Anmerkungen, Kundenunterschrift
// =====================================================================

// Abschnitt im Auftrag › Werkstatt
async function montageAbschnitt(box, a) {
  let liste = [];
  try { liste = await api("montage?auftrag=" + a.id); } catch (e) { box.innerHTML = ""; return; }
  box.innerHTML = `
    <div class="sektion" style="margin-top:18px">Rapport mit Unterschrift</div>
    <div class="kachel">
      ${liste.length ? `<table class="liste"><tr><th>Datum</th><th>Status</th><th class="r">Stunden</th><th>Material</th><th>Kunde</th><th></th></tr>
        ${liste.map(m => `<tr class="klick" data-mb="${m.id}"><td><a href="#/montage/${m.id}">▸ ${datum(m.datum)}</a></td>
          <td>${m.status === "offen" ? `<span style="color:var(--akzent)">offen</span>` : `<span style="color:var(--gruen)">unterschrieben</span>`}</td>
          <td class="r">${n2(m.stunden_summe)} h</td><td>${m.material.filter(x => +x.menge > 0).length} Zeilen</td><td>${esc(m.kunde_name || "")}</td>
          <td>${m.status !== "offen" ? `<a href="/papier/montage/${m.id}" target="_blank">ansehen</a>` : ""}</td></tr>`).join("")}</table>` : `<p class="hinweis" style="margin-top:0">Noch kein Rapport.</p>`}
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px"><button class="btn prim" id="mbNeu">+ Neuer Rapport</button></div>
      <p class="hinweis" style="margin-bottom:0">Beim Kunden auf dem Tablet ausfüllen: Stunden, verwendetes Material und Anmerkungen eintragen und den Kunden direkt unterschreiben lassen. Danach landen die Stunden im Zeitkonto und in der Nachkalkulation, das Material in den Auftragskosten (Lagerartikel mit Lagerabgang), die Anmerkungen als Notiz – und das PDF im Projektordner.</p>
    </div>`;
  $$("[data-mb]", box).forEach(tr => tr.onclick = ev => { if (!ev.target.closest("a")) location.hash = "#/montage/" + tr.dataset.mb; });
  $("#mbNeu", box).onclick = async () => {
    try { const m = await api("montage", {method: "POST", body: {auftrag_id: a.id}}); location.hash = "#/montage/" + m.id; }
    catch (e) { toast(e.message, true); }
  };
}

const mbStd = z => {
  const m = t => { const x = String(t || "").replace(".", ":").split(":"); return x.length === 2 && x[0] !== "" ? (+x[0]) * 60 + (+x[1] || 0) : null; };
  const b = m(z.beginn), e = m(z.ende);
  if (b === null || e === null || e <= b) return 0;
  return Math.max(0, Math.round((e - b - (+z.pause || 0)) / 60 * 100) / 100);
};

// Unterseiten eines Auftrags (Rapport, Unterschrift, Bautagebuch): Auftragskopf mit Reitern und Projektordner bleiben stehen
async function auftragUnterseite(aid, titel, reiter = "werkstatt", a = null) {
  try { a = a || await api("auftraege/" + aid); }
  catch (e) { kopf({krumen: [["Aufträge", "#/auftraege"], [titel, ""]], zurueck: `#/auftrag/${aid}/${reiter}`}); return null; }
  auftragKopf(a, reiter, {zeile2: titel, zurueck: `#/auftrag/${aid}/${reiter}`});
  return a;
}

async function ansichtMontage(id) {
  let b = await api("montage/" + id);
  const meta = await api("montage/meta?auftrag=" + b.auftrag_id);
  await auftragUnterseite(b.auftrag_id, `Rapport vom ${datum(b.datum)}`);
  const z = $("#inhalt");
  const offen = b.status === "offen";
  let timer;
  const speichern = (sofort) => {
    if (!offen) return;
    clearTimeout(timer);
    const s = $(".speicher"); if (s) { s.textContent = "…"; s.className = "speicher"; }
    timer = setTimeout(async () => {
      try {
        await api("montage/" + id, {method: "PUT", body: {datum: b.datum, positionen: b.positionen, zeiten: b.zeiten, material: b.material,
          anmerkungen: b.anmerkungen, abgeschlossen: b.abgeschlossen, kunde_name: b.kunde_name}});
        const s = $(".speicher"); if (s) { s.textContent = "gespeichert ✓"; s.className = "speicher ok"; }
      } catch (e) { toast(e.message, true); }
    }, sofort ? 20 : 700);
  };
  const dis = offen ? "" : "disabled";
  const summe = () => b.zeiten.reduce((s, x) => s + mbStd(x), 0);
  const zeichnen = () => {
    const adr = (meta.kunde.lieferanschrift || meta.kunde.anschrift || "").replace(/\n/g, " · ");
    z.innerHTML = `
      <div class="titel"><h2>Rapport</h2><span class="speicher"></span>
        <div class="rechts">${offen ? `<button class="btn rot" id="mbDel">Löschen</button>` : `<button class="btn" id="mbPdf" title="PDF neu erzeugen und im Projektordner ablegen">PDF neu ablegen</button><a class="btn" href="/papier/montage/${id}" target="_blank">Ansehen / Drucken</a><button class="btn prim" id="mbMail">✉ Per E-Mail senden</button>`}</div></div>
      ${offen ? "" : `<div class="kachel" style="margin-bottom:12px;border-left:4px solid var(--gruen)"><b>Unterschrieben</b> von ${esc(b.kunde_name)} am ${datum(b.unterschrieben.slice(0, 10))} um ${esc(b.unterschrieben.slice(11, 16))}.
        Übernommen: ${b.uebernahme.zeiten?.length || 0} Zeitabschnitte${b.uebernahme.stunden?.length ? ` + ${b.uebernahme.stunden.length} Stundenbuchungen` : ""}, ${b.uebernahme.auftragskosten?.length || 0} Materialbuchungen, Notiz im Auftrag.
        ${(b.uebernahme.hinweise || []).map(x => `<div style="color:var(--rot)">${esc(x)}</div>`).join("")}${b.pdf ? `<div class="hinweis">PDF: ${esc(b.pdf)}</div>` : ""}
        <div style="margin-top:8px"><button class="btn prim" id="mbMail2">✉ Rapport jetzt per E-Mail an den Kunden senden</button></div></div>`}
      <div class="mb">
        <div class="mb-kopf"><div><b>${esc(meta.auftrag.nummer)} · ${esc(meta.auftrag.bezeichnung)}</b><br>${esc(meta.kunde.name)}${adr ? " · " + esc(adr) : ""}${meta.kunde.telefon ? ` · <a href="tel:${esc(meta.kunde.telefon)}">${esc(meta.kunde.telefon)}</a>` : ""}</div>
          <label>Datum <input type="date" id="mbDatum" value="${esc(b.datum)}" ${dis}></label></div>

        ${b.positionen.length ? `<h3>Positionen</h3><div class="mb-pos">${b.positionen.map((p, i) => `<label class="mb-check"><input type="checkbox" data-pe="${i}" ${p.erledigt ? "checked" : ""} ${dis}>
          <span><b>${esc(p.posnr)}</b> ${esc(p.text)}</span></label>`).join("")}</div>` : ""}

        <h3>Geleistete Stunden</h3>
        <div class="mb-zeiten">${b.zeiten.map((x, i) => `<div class="mb-zeit">
          <select data-z="${i}" data-k="mitarbeiter_id" ${dis}><option value="">— andere Person —</option>${meta.mitarbeiter.map(m => `<option value="${m.id}" ${m.id === +x.mitarbeiter_id ? "selected" : ""}>${esc(m.name)}</option>`).join("")}</select>
          ${x.mitarbeiter_id ? "" : `<input data-z="${i}" data-k="name" value="${esc(x.name || "")}" placeholder="Name" ${dis}>`}
          <label>von <input type="time" data-z="${i}" data-k="beginn" value="${esc(x.beginn || "")}" ${dis}></label>
          <label>bis <input type="time" data-z="${i}" data-k="ende" value="${esc(x.ende || "")}" ${dis}></label>
          <label>Pause <input type="number" min="0" step="5" data-z="${i}" data-k="pause" value="${+x.pause || 0}" style="width:70px" ${dis}> min</label>
          <select data-z="${i}" data-k="kst" title="Kostenstelle" ${dis}>${meta.kostenstellen.map(k => `<option ${k === x.kst ? "selected" : ""}>${esc(k)}</option>`).join("")}</select>
          <input data-z="${i}" data-k="taetigkeit" value="${esc(x.taetigkeit || "")}" placeholder="Tätigkeit" ${dis}>
          <b class="mb-h" data-h="${i}">${n2(mbStd(x))} h</b>
          ${offen ? `<button class="btn rot" data-mbzdel="${i}" title="Zeile entfernen">✕</button>` : ""}</div>`).join("") || `<p class="hinweis">Noch keine Stunden.</p>`}</div>
        <div class="mb-zeile">${offen ? `<button class="btn" id="mbZeit">+ Person / Zeit</button>` : ""}<span style="margin-left:auto">Summe <b id="mbSumme">${n2(summe())} h</b></span></div>

        <h3>Verwendetes Material</h3>
        <div class="mb-mat">${b.material.map((m, i) => `<div class="mb-matz">
          <div class="mb-matname">${m.nummer ? `<b>${esc(m.nummer)}</b> ` : ""}${m.material_id ? esc(m.bezeichnung) : `<input data-m="${i}" data-k="bezeichnung" value="${esc(m.bezeichnung || "")}" placeholder="Bezeichnung (frei)" ${dis}>`}${m.lager ? ` <span class="hinweis">Lager</span>` : ""}</div>
          <input class="zahl" inputmode="decimal" data-m="${i}" data-k="menge" value="${m.menge ? mengeDE(m.menge) : ""}" placeholder="Menge" style="width:90px" ${dis}>
          ${m.material_id ? `<span>${esc(m.einheit || "")}</span>` : `<input data-m="${i}" data-k="einheit" value="${esc(m.einheit || "Stk.")}" style="width:70px" ${dis}>`}
          ${offen ? `<button class="btn rot" data-mdel="${i}">✕</button>` : ""}</div>`).join("") || `<p class="hinweis">Noch kein Material.</p>`}</div>
        ${offen ? `<div class="mb-suche"><input id="mbSuch" placeholder="Material suchen (Nummer, Bezeichnung, EAN) …" autocomplete="off"><div id="mbTreffer"></div></div>
          <div class="mb-zeile"><button class="btn" id="mbFrei">+ Material ohne Stamm (freie Zeile)</button></div>` : ""}

        <h3>Anmerkungen</h3>
        <textarea id="mbAnm" rows="4" placeholder="z. B. Restarbeiten, Mängel, Wünsche des Kunden" ${dis}>${esc(b.anmerkungen || "")}</textarea>
        <div class="mb-zeile"><span>Arbeiten abgeschlossen?</span>
          <label class="mb-check"><input type="radio" name="mbAbg" value="1" ${b.abgeschlossen ? "checked" : ""} ${dis}> ja</label>
          <label class="mb-check"><input type="radio" name="mbAbg" value="0" ${b.abgeschlossen ? "" : "checked"} ${dis}> nein</label></div>

        ${offen ? `<h3>Unterschriften</h3>
        <div class="mb-unterschriften">
          <div><div class="hinweis">Monteur (optional)</div><canvas class="mb-pad" id="padM"></canvas><button class="btn" data-leer="padM">löschen</button></div>
          <div><div class="hinweis">Kunde</div><canvas class="mb-pad" id="padK"></canvas><button class="btn" data-leer="padK">löschen</button>
            <input id="mbKunde" value="${esc(b.kunde_name || "")}" placeholder="Name des Kunden in Druckschrift" style="margin-top:6px;width:100%"></div>
        </div>
        <p class="hinweis">Mit der Unterschrift bestätigt der Kunde Arbeiten, Stunden und Material. Danach ist der Bericht gesperrt.</p>
        <button class="btn prim mb-gross" id="mbOk">Unterschreiben und in den Auftrag übernehmen</button>` : ""}
      </div>`;
    binden();
  };
  const pads = {};
  const pad = (cv) => {
    const g = cv.getContext("2d"); let malt = false, leer = true, last = null;
    const groesse = () => { const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1; cv.width = r.width * dpr; cv.height = r.height * dpr; g.scale(dpr, dpr); g.lineWidth = 2.2; g.lineCap = "round"; g.lineJoin = "round"; g.strokeStyle = "#111"; };
    groesse();
    const pt = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    cv.onpointerdown = e => { e.preventDefault(); cv.setPointerCapture(e.pointerId); malt = true; last = pt(e); g.beginPath(); g.arc(last[0], last[1], 1, 0, 7); g.fill(); leer = false; };
    cv.onpointermove = e => { if (!malt) return; e.preventDefault(); const p = pt(e); g.beginPath(); g.moveTo(last[0], last[1]); g.lineTo(p[0], p[1]); g.stroke(); last = p; };
    cv.onpointerup = cv.onpointercancel = () => { malt = false; };
    return {leer: () => leer, loeschen: () => { g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, cv.width, cv.height); groesse(); leer = true; },
      png: () => {
        // weißer Hintergrund statt transparent, damit es im PDF sauber aussieht
        const c = document.createElement("canvas"); c.width = cv.width; c.height = cv.height; const x = c.getContext("2d");
        x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height); x.drawImage(cv, 0, 0); return c.toDataURL("image/png");
      }};
  };
  const binden = () => {
    const pb = $("#mbPdf");
    if (pb) pb.onclick = async () => {
      pb.disabled = true; pb.textContent = "PDF wird erstellt …";
      try { const r = await api(`montage/${id}/pdf`, {method: "POST"}); if (r.fehler) throw new Error(r.fehler); toast("PDF abgelegt: " + (r.projekt_rel || r.pfad)); ansichtMontage(id); }
      catch (e) { toast(e.message, true); pb.disabled = false; pb.textContent = "PDF neu ablegen"; }
    };
    ["#mbMail", "#mbMail2"].forEach(s => { const mb = $(s); if (mb) mb.onclick = () => mailDialog(`montage/${id}`, "Rapport per E-Mail", () => ansichtMontage(id)); });
    if (!offen) return;
    $("#mbDatum").onchange = e => { b.datum = e.target.value; speichern(); };
    $$("[data-pe]", z).forEach(c => c.onchange = () => { b.positionen[+c.dataset.pe].erledigt = c.checked; speichern(); });
    $$("[data-z]", z).forEach(el => el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
      const x = b.zeiten[+el.dataset.z], k = el.dataset.k;
      x[k] = k === "pause" ? (+el.value || 0) : el.value;
      if (k === "mitarbeiter_id") { x.mitarbeiter_id = el.value ? +el.value : null; const m = meta.mitarbeiter.find(m => m.id === x.mitarbeiter_id); x.name = m ? m.name : ""; speichern(true); zeichnen(); return; }
      const hEl = $(`[data-h="${el.dataset.z}"]`, z); if (hEl) hEl.textContent = n2(mbStd(x)) + " h";
      $("#mbSumme").textContent = n2(summe()) + " h";
      speichern();
    }));
    $$("[data-mbzdel]", z).forEach(btn => btn.onclick = () => { b.zeiten.splice(+btn.dataset.mbzdel, 1); speichern(true); zeichnen(); });
    $("#mbZeit").onclick = () => {
      const vor = b.zeiten[b.zeiten.length - 1];
      b.zeiten.push({mitarbeiter_id: null, name: "", beginn: vor ? vor.beginn : "", ende: vor ? vor.ende : "", pause: vor ? vor.pause : 0, kst: vor ? vor.kst : meta.kst_vorgabe, taetigkeit: vor ? vor.taetigkeit : "Montage"});
      speichern(true); zeichnen();
    };
    $$("[data-m]", z).forEach(el => el.addEventListener("input", () => {
      const m = b.material[+el.dataset.m], k = el.dataset.k;
      m[k] = k === "menge" ? zahlEin(el.value) : el.value; speichern();
    }));
    $$("[data-mdel]", z).forEach(btn => btn.onclick = () => { b.material.splice(+btn.dataset.mdel, 1); speichern(true); zeichnen(); });
    $("#mbFrei").onclick = () => { b.material.push({material_id: null, nummer: "", bezeichnung: "", menge: 1, einheit: "Stk."}); speichern(true); zeichnen(); };
    let st;
    $("#mbSuch").oninput = e => {
      clearTimeout(st); const t = e.target.value.trim();
      if (t.length < 2) { $("#mbTreffer").innerHTML = ""; return; }
      st = setTimeout(async () => {
        const r = await api("montage/material?q=" + encodeURIComponent(t));
        $("#mbTreffer").innerHTML = r.length ? r.map((m, i) => `<button class="mb-treffer" data-t="${i}"><b>${esc(m.nummer)}</b> ${esc(m.bezeichnung)} <span class="hinweis">${esc(m.einheit || "")}${m.lager ? ` · Lager ${n2(m.bestand, m.bestand % 1 ? 2 : 0)}` : ""}</span></button>`).join("")
          : `<div class="hinweis" style="padding:6px">Nichts gefunden – „Material ohne Stamm“ nehmen.</div>`;
        $$("[data-t]", $("#mbTreffer")).forEach(btn => btn.onclick = () => {
          const m = r[+btn.dataset.t];
          b.material.push({material_id: m.id, nummer: m.nummer, bezeichnung: m.bezeichnung, einheit: m.einheit, lager: !!m.lager, menge: 1});
          speichern(true); zeichnen();
          setTimeout(() => { const f = $$("[data-k=menge]", z).pop(); if (f) { f.focus(); f.select(); } }, 30);
        });
      }, 250);
    };
    $("#mbAnm").oninput = e => { b.anmerkungen = e.target.value; speichern(); };
    $$("[name=mbAbg]", z).forEach(r => r.onchange = () => { b.abgeschlossen = r.value === "1"; speichern(); });
    $("#mbKunde").oninput = e => { b.kunde_name = e.target.value; speichern(); };
    pads.M = pad($("#padM")); pads.K = pad($("#padK"));
    $$("[data-leer]", z).forEach(btn => btn.onclick = () => pads[btn.dataset.leer === "padM" ? "M" : "K"].loeschen());
    $("#mbDel").onclick = async () => {
      if (!await frage("Rapport löschen?")) return;
      await api("montage/" + id, {method: "DELETE"}); location.hash = `#/auftrag/${b.auftrag_id}/werkstatt`;
    };
    $("#mbOk").onclick = async () => {
      if (!b.kunde_name.trim()) { toast("Bitte den Namen des Kunden eintragen.", true); $("#mbKunde").focus(); return; }
      if (pads.K.leer()) { toast("Bitte den Kunden unterschreiben lassen.", true); return; }
      const nMat = b.material.filter(m => +m.menge > 0).length;
      const leer = !summe() ? "\n\nAchtung: Es sind keine Stunden eingetragen (von/bis fehlt)." : "";
      if (!await frage(`Rapport abschließen?\n\n${n2(summe())} Stunden und ${nMat} Materialzeilen werden in den Auftrag übernommen. Danach ist der Bericht gesperrt.${leer}`, {ok: "Übernehmen"})) return;
      const btn = $("#mbOk"); btn.disabled = true; btn.textContent = "wird übernommen …";
      clearTimeout(timer);
      try {
        const r = await api(`montage/${id}/unterschreiben`, {method: "POST", body: {datum: b.datum, positionen: b.positionen, zeiten: b.zeiten, material: b.material,
          anmerkungen: b.anmerkungen, abgeschlossen: b.abgeschlossen, kunde_name: b.kunde_name,
          unterschrift_kunde: pads.K.png(), unterschrift_monteur: pads.M.leer() ? "" : pads.M.png()}});
        toast("Rapport unterschrieben und übernommen" + (r.pdf_info && r.pdf_info.projekt_rel ? " · PDF: " + r.pdf_info.projekt_rel : ""));
        if (r.pdf_info && r.pdf_info.fehler) setTimeout(() => toast("PDF: " + r.pdf_info.fehler, true), 2200);
        ansichtMontage(id);
      } catch (e) { toast(e.message, true); btn.disabled = false; btn.textContent = "Unterschreiben und in den Auftrag übernehmen"; }
    };
  };
  zeichnen();
}

// =====================================================================
//  Digitale Kundenunterschrift für Auftragsbestätigung, Lieferschein und Abnahmeprotokoll
// =====================================================================
function unterschriftPad(cv) {
  const g = cv.getContext("2d"); let malt = false, leer = true, last = null;
  const groesse = () => { const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1; cv.width = r.width * dpr; cv.height = r.height * dpr; g.scale(dpr, dpr); g.lineWidth = 2.2; g.lineCap = "round"; g.lineJoin = "round"; g.strokeStyle = "#111"; };
  groesse();
  const pt = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  cv.onpointerdown = e => { e.preventDefault(); cv.setPointerCapture(e.pointerId); malt = true; last = pt(e); g.beginPath(); g.arc(last[0], last[1], 1, 0, 7); g.fill(); leer = false; };
  cv.onpointermove = e => { if (!malt) return; e.preventDefault(); const p = pt(e); g.beginPath(); g.moveTo(last[0], last[1]); g.lineTo(p[0], p[1]); g.stroke(); last = p; };
  cv.onpointerup = cv.onpointercancel = () => { malt = false; };
  return {leer: () => leer, loeschen: () => { g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, cv.width, cv.height); groesse(); leer = true; },
    png: () => { const c = document.createElement("canvas"); c.width = cv.width; c.height = cv.height; const x = c.getContext("2d");
      x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height); x.drawImage(cv, 0, 0); return c.toDataURL("image/png"); }};
}

// Abschnitt im Auftrag › Werkstatt: Belege zum Unterschreiben
async function unterschriftAbschnitt(box, a) {
  let liste = [];
  try { liste = await api("kundenunterschrift?auftrag=" + a.id); } catch (e) { box.innerHTML = ""; return; }
  box.innerHTML = `<div class="sektion" style="margin-top:18px">Belege unterschreiben lassen</div>
    <div class="kachel">${liste.length ? `<table class="liste"><tr><th>Beleg</th><th>Datum</th><th>Unterschrift</th><th></th></tr>
      ${liste.map(b => `<tr><td>${esc(b.artname)} ${esc(b.nummer || "")}</td><td>${datum(b.datum)}</td>
        <td>${b.unterschrieben ? `<span style="color:var(--gruen)">✓ ${esc(b.name || "")}, ${datum(b.unterschrieben.slice(0, 10))}</span>` : `<span class="hinweis">offen</span>`}</td>
        <td>${b.unterschrieben ? `<a href="/druck/${b.id}.pdf" target="_blank">PDF</a>` : `<a class="btn prim" href="#/unterschrift/${b.id}">✍ Unterschreiben lassen</a>`}</td></tr>`).join("")}</table>`
      : `<p class="hinweis" style="margin:0">Noch keine Auftragsbestätigung, kein Lieferschein und kein Abnahmeprotokoll. Diese Belege legt das Büro unter Belege an; hier werden sie dann beim Kunden auf dem Tablet unterschrieben.</p>`}</div>`;
}

async function ansichtUnterschrift(bid) {
  const z = $("#inhalt");
  let b;
  try { b = await api("kundenunterschrift/" + bid); } catch (e) { kopf({}); z.innerHTML = `<div class="leer">${esc(e.message)}</div>`; return; }
  const a = b.auftrag;
  await auftragUnterseite(a.id, `${b.artname} ${b.nummer || ""} unterschreiben`);
  const ab = b.abnahme || {};
  if (b.unterschrift) {
    z.innerHTML = `<div class="titel"><h2>${esc(b.artname)} ${esc(b.nummer || "")}</h2></div>
      <div class="kachel" style="margin-bottom:12px">✓ Unterschrieben von <b>${esc(b.unterschrift.name)}</b>${b.unterschrift.ort ? " in " + esc(b.unterschrift.ort) : ""} am ${datum(b.unterschrift.zeit.slice(0, 10))} um ${b.unterschrift.zeit.slice(11, 16)} Uhr.</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="btn prim" href="/druck/${bid}.pdf" target="_blank">PDF</a>
        ${darf("mail", 2) || darf("auftraege", 2) ? `<button class="btn" id="usMail">✉ Per E-Mail an den Kunden</button>` : ""}<a class="btn" href="#/auftrag/${a.id}/werkstatt">Zurück zum Auftrag</a></div>`;
    if ($("#usMail")) $("#usMail").onclick = () => belegMailen(bid);
    return;
  }
  z.innerHTML = `<div class="titel"><h2>${esc(b.artname)} ${esc(b.nummer || "")}</h2><div class="rechts"><a class="btn" href="/druck/${bid}.pdf" target="_blank">PDF</a></div></div>
    <div style="position:relative"><div id="vsInfo" class="hinweis" style="position:absolute;top:8px;right:12px;background:#fff;padding:2px 8px;border-radius:4px"></div>
    <div id="vorschau" style="width:100%;max-height:55vh;overflow:auto;border:1px solid var(--linie);border-radius:6px;background:#8a8a8a;padding:14px 0"></div></div>
    ${b.art === "abnahme" ? `<div class="form" style="grid-template-columns:1fr;margin-top:12px">
      ${zeile("Abnahme", `<div class="radio"><label><input type="radio" name="usVb" value="0" ${ab.vorbehalt ? "" : "checked"}> ohne Vorbehalt</label><label><input type="radio" name="usVb" value="1" ${ab.vorbehalt ? "checked" : ""}> mit Vorbehalt (Mängel)</label></div>`)}
      ${zeile("Mängel", `<textarea id="usMaengel" rows="3" placeholder="keine">${esc(ab.maengel || "")}</textarea>`)}
      ${zeile("Restarbeiten", `<textarea id="usRest" rows="2" placeholder="keine">${esc(ab.restarbeiten || "")}</textarea>`)}</div>` : ""}
    <div class="form" style="grid-template-columns:1fr;margin-top:12px">
      ${zeile(b.art === "lieferschein" ? "Name Empfänger" : "Name Auftraggeber", `<input id="usName" value="${esc(b.kunde.name || "")}" placeholder="Vor- und Nachname">`)}
      ${zeile("Ort", `<input id="usOrt" value="${esc(b.kunde.ort || "")}" placeholder="Ort der Unterschrift"><button class="btn" id="usGps" type="button" title="Standort des Tablets mit ablegen (wenn der Browser es erlaubt)">📍</button>`)}
    </div>
    <div class="mb-pads" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(280px,100%),1fr));gap:14px;margin-top:10px">
      <div><div class="hinweis">Auftragnehmer (optional)</div><input id="usNameAn" value="${esc((ICH && ICH.name) || E.firma_inhaber || "")}" placeholder="Name" style="margin:4px 0">
        <canvas class="mb-pad" id="usPadAn"></canvas><button class="btn" id="usLeerAn">löschen</button></div>
      <div><div class="hinweis">${b.art === "abnahme" ? "Auftraggeber (Abnahme)" : b.art === "lieferschein" ? "Empfänger (Ware erhalten)" : "Auftraggeber (Auftrag bestätigt)"}</div><div style="height:38px"></div>
        <canvas class="mb-pad" id="usPad"></canvas><button class="btn" id="usLeer">löschen</button></div>
    </div>
    <button class="btn prim mb-gross" id="usOk">Unterschreiben</button>`;
  vorschauZeichnen(bid, 1, () => 1);   // echte PDF-Seiten (wie gedruckt), auch auf dem Tablet
  const pad = unterschriftPad($("#usPad")), padAn = unterschriftPad($("#usPadAn"));
  $("#usLeerAn").onclick = () => padAn.loeschen();
  let geo = null;
  $("#usLeer").onclick = () => pad.loeschen();
  $("#usGps").onclick = () => {
    if (!navigator.geolocation) return toast("Der Browser liefert keinen Standort.", true);
    navigator.geolocation.getCurrentPosition(p => { geo = {lat: p.coords.latitude, lon: p.coords.longitude, genau: Math.round(p.coords.accuracy)}; toast(`Standort übernommen (± ${geo.genau} m)`); },
      () => toast("Standort nicht verfügbar (der Browser erlaubt ihn im Netzwerk ohne https meist nicht). Der Ort reicht.", true), {enableHighAccuracy: true, timeout: 8000});
  };
  $("#usOk").onclick = async () => {
    if (pad.leer()) return toast("Bitte unterschreiben lassen.", true);
    const name = $("#usName").value.trim(); if (!name) return toast("Bitte den Namen eintragen.", true);
    const body = {bild: pad.png(), name, ort: $("#usOrt").value.trim(), geo, ...(padAn.leer() ? {} : {bild_an: padAn.png(), name_an: $("#usNameAn").value.trim()})};
    if (b.art === "abnahme") Object.assign(body, {vorbehalt: ($$("[name=usVb]").find(x => x.checked) || {}).value === "1", maengel: $("#usMaengel").value, restarbeiten: $("#usRest").value});
    const k = $("#usOk"); k.disabled = true; k.textContent = "wird gespeichert …";
    try { const r = await api("kundenunterschrift/" + bid, {method: "POST", body}); toast(r.pdf_fehler ? "Unterschrieben (PDF: " + r.pdf_fehler + ")" : "Unterschrieben, PDF abgelegt"); ansichtUnterschrift(bid); }
    catch (e) { toast(e.message, true); k.disabled = false; k.textContent = "Unterschreiben"; }
  };
}

// =====================================================================
//  Bautagebuch (je Auftrag, Tageseinträge mit Fotos)
// =====================================================================
async function bautagebuchAbschnitt(box, a) {
  let d;
  try { d = await api("bautagebuch?auftrag=" + a.id); } catch (e) { box.innerHTML = ""; return; }
  const L = d.eintraege;
  box.innerHTML = `<div class="sektion" style="margin-top:18px">Bautagebuch</div>
    <div class="kachel">${L.length ? `<table class="liste"><tr><th>Datum</th><th>Wetter</th><th>Arbeiten</th><th class="r">Fotos</th></tr>
      ${L.map(e => `<tr class="klick" data-bt="${e.id}"><td><a href="#/bautagebuch/${e.id}">▸ ${datum(e.datum)}</a></td><td>${esc(e.wetter || "")}${e.temperatur ? " · " + esc(e.temperatur) + " °C" : ""}</td>
        <td>${esc(kurz(e.arbeiten || "", 70))}</td><td class="r">${e.fotos.length || ""}</td></tr>`).join("")}</table>` : `<p class="hinweis" style="margin-top:0">Noch keine Einträge.</p>`}
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px"><button class="btn prim" id="btHeute">+ Eintrag für heute</button>
        ${L.length ? `<a class="btn" href="/papier/bautagebuch/${a.id}" target="_blank">Bautagebuch ansehen</a>` : ""}</div>
      <p class="hinweis" style="margin-bottom:0">Je Tag ein Eintrag mit Wetter, Personal (aus der Zeiterfassung vorgeschlagen), ausgeführten Arbeiten, Lieferungen, Behinderungen, Mängeln und Fotos.</p></div>`;
  $$("[data-bt]", box).forEach(tr => tr.onclick = ev => { if (!ev.target.closest("a")) location.hash = "#/bautagebuch/" + tr.dataset.bt; });
  $("#btHeute", box).onclick = async () => {
    try { const e = await api("bautagebuch", {method: "POST", body: {auftrag_id: a.id}}); location.hash = "#/bautagebuch/" + e.id; } catch (x) { toast(x.message, true); }
  };
}

function fotoVerkleinern(datei, max = 1800) {
  return new Promise((ok, fehler) => {
    const url = URL.createObjectURL(datei), img = new Image();
    img.onload = () => { const f = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight)); const c = document.createElement("canvas");
      c.width = Math.round(img.naturalWidth * f); c.height = Math.round(img.naturalHeight * f); c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url); ok(c.toDataURL("image/jpeg", 0.85)); };
    img.onerror = () => { URL.revokeObjectURL(url); fehler(new Error("Bild nicht lesbar")); };
    img.src = url;
  });
}

async function ansichtBautagebuch(eid) {
  const z = $("#inhalt");
  let e;
  try { e = await api("bautagebuch/" + eid); } catch (x) { kopf({}); z.innerHTML = `<div class="leer">${esc(x.message)}</div>`; return; }
  const [a, pl] = await Promise.all([api("auftraege/" + e.auftrag_id), api(`auftraege/${e.auftrag_id}/positionen`).catch(() => ({positionen: []}))]);
  const haupt = pl.positionen || [];
  await auftragUnterseite(a.id, `Bautagebuch ${datum(e.datum)}`, "werkstatt", a);
  const ta = (k, l, rows = 3, ph = "") => zeile(l, `<textarea data-f="${k}" rows="${rows}" placeholder="${ph}">${esc(e[k] || "")}</textarea>`, true);
  const zeichnen = () => {
    z.innerHTML = `<div class="titel"><h2>Bautagebuch ${datum(e.datum)}</h2><span class="speicher"></span>
      <div class="rechts"><a class="btn" href="/papier/bautagebuch/${a.id}" target="_blank">Bautagebuch ansehen</a></div></div>
      <div class="form" id="btF">
        ${zeile("Datum", `<input type="date" data-f="datum" value="${esc(e.datum)}">`)}
        ${zeile("Wetter", `<select data-f="wetter"><option value="">–</option>${e.wetter_liste.map(w => `<option ${w === e.wetter ? "selected" : ""}>${esc(w)}</option>`).join("")}</select><input data-f="temperatur" value="${esc(e.temperatur || "")}" placeholder="°C" style="width:70px;flex:0 0 70px">`)}
        ${haupt.length ? zeile("Positionen", `<div class="spalte">${haupt.map(p => `<label><input type="checkbox" data-pos="${p.id}" ${(e.positionen || []).some(x => x.id === p.id) ? "checked" : ""}> ${esc(p.posnr)} ${esc(kurz(klartext(p.text || ""), 70))}</label>`).join("")}<span class="hinweis">An welchen Positionen wurde an diesem Tag gearbeitet?</span></div>`, true) : ""}
        ${ta("personal", "Personal", 3, "Wer war vor Ort, von–bis")}
        ${zeile("Gebuchte Stunden", e.stunden.length ? `<div class="spalte" style="width:100%"><table class="liste"><tr><th>Mitarbeiter</th><th>Kostenstelle</th><th>Tätigkeit</th><th class="r">Stunden</th></tr>
          ${e.stunden.map(x => `<tr><td>${esc(x.name || "–")}</td><td>${esc(x.kst)}</td><td>${esc(x.taetigkeit)}</td><td class="r">${n2(x.stunden)} h</td></tr>`).join("")}
          <tr class="sum"><td colspan="3">Summe</td><td class="r">${n2(e.stunden_summe)} h</td></tr></table><span class="hinweis">aus Stempeluhr, Zeiterfassung, Rapport und Stundenbuchung dieses Tages</span></div>`
          : `<span class="hinweis" style="padding-top:5px">Für diesen Tag sind auf dem Auftrag noch keine Stunden gebucht.</span>`, true)}
        ${ta("arbeiten", "Ausgeführte Arbeiten", 4)}
        ${ta("material", "Material / Lieferungen", 2)}
        ${ta("behinderungen", "Behinderungen", 2, "z. B. Vorgewerk nicht fertig, Zugang gesperrt, Wetter")}
        ${ta("maengel", "Mängel", 2)}
        ${ta("besonderes", "Besonderes / Absprachen", 2)}
      </div>
      <div class="sektion" style="margin-top:14px">Fotos</div>
      <div class="bt-fotos">${e.fotos.map(f => `<figure><a href="/api/bautagebuch/foto/${esc(f.datei)}" target="_blank"><img src="/api/bautagebuch/foto/${esc(f.datei)}"></a><button class="bt-weg" data-fweg="${esc(f.datei)}" title="Foto entfernen">✕</button></figure>`).join("")}
        <label class="bt-plus">📷 Foto aufnehmen / wählen<input type="file" id="btFoto" accept="image/*" capture="environment" multiple hidden></label></div>`;
    autospeichern($("#btF"), "bautagebuch/" + eid, r => { Object.assign(e, r); });
    $("#btFoto").onchange = async ev => {
      for (const f of ev.target.files) {
        try { const daten = await fotoVerkleinern(f); const r = await api(`bautagebuch/${eid}/foto`, {method: "POST", body: {daten}}); e.fotos = r.fotos; }
        catch (x) { toast(x.message, true); }
      }
      zeichnen(); toast("Foto gespeichert");
    };
    $$("[data-fweg]", z).forEach(b => b.onclick = async () => { if (!await frage("Foto entfernen?")) return; const r = await api(`bautagebuch/${eid}/foto?datei=${encodeURIComponent(b.dataset.fweg)}`, {method: "DELETE"}); e.fotos = r.fotos; zeichnen(); });
    $$("[data-pos]", z).forEach(c => c.onchange = async () => {
      const gew = haupt.filter(p => $(`[data-pos="${p.id}"]`, z).checked).map(p => ({id: p.id, posnr: p.posnr, text: kurz(klartext(p.text || ""), 100)}));
      try { const r = await api("bautagebuch/" + eid, {method: "PUT", body: {positionen: gew}}); e.positionen = r.positionen; } catch (x) { toast(x.message, true); }
    });
  };
  e.wetter_liste = e.wetter_liste || (await api("bautagebuch?auftrag=0")).wetter;
  zeichnen();
}
