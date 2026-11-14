// =====================================================================
//  Eingangsrechnungen einlesen (ZUGFeRD / XRechnung / PDF) und Werkzeugverwaltung
// =====================================================================
const EIN_ZIELE = [["lager", "Ins Lager"], ["auftrag", "Auf Auftrag"], ["werkzeug", "Werkzeug"], ["kosten", "Nur Kosten"]];

function dateiAlsBase64(f) {
  return f.arrayBuffer().then(buf => {
    const b = new Uint8Array(buf); let s = "";
    for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
    return btoa(s);
  });
}

async function eingangEinlesen(datei, danach) {
  if (datei.size > 25 * 1024 * 1024) return toast("Die Datei ist größer als 25 MB.", true);
  toast("Rechnung wird gelesen …");
  let v;
  try { v = await api("eingang/lesen", {method: "POST", body: {dateiname: datei.name, daten: await dateiAlsBase64(datei)}}); }
  catch (e) { return toast(e.message, true); }
  const [lieferanten, auftraege, materialien, wzMeta] = await Promise.all([
    api("lieferanten?status=alle").catch(() => []), api("auftraege").catch(() => []),
    api("material?status=aktiv").catch(() => []), api("werkzeuge/meta").catch(() => ({arten: []}))]);
  eingangDialog(v, {lieferanten, auftraege, materialien, wzMeta}, danach);
}

function eingangDialog(v, {lieferanten, auftraege, materialien, wzMeta}, danach) {
  const r = v.rechnung || {}, L = v.lieferant || {};
  const matText = m => `${m.nummer} · ${String(m.bezeichnung || "").split("\n")[0]}`;
  const matNachText = new Map(materialien.map(m => [matText(m), m]));
  const offeneAuftraege = auftraege.filter(a => !["Erledigt", "Abgesagt"].includes(a.status) || a.id === v.auftrag_id);
  const aOpt = (wert, leer = "– kein Auftrag –") => `<option value="">${leer}</option>` + offeneAuftraege.map(a => `<option value="${a.id}" ${+wert === a.id ? "selected" : ""}>${esc(a.nummer)} · ${esc(a.bezeichnung || "")}${a.kunde ? " · " + esc(a.kunde) : ""}</option>`).join("");
  const kopf = {belegnr: r.nummer || "", belegdatum: r.datum || heute(), faellig: r.faellig || "", skonto: r.skonto || 0, skonto_bis: r.skonto_bis || "",
    betrag: r.zahlbetrag || r.brutto || 0, vorsteuer: r.ust_satz ?? 19, iban: L.iban || "", bic: L.bic || "", auftrag_id: v.auftrag_id || "",
    bemerkung: "", bezahlt: r.bereits_bezahlt ? (r.datum || heute()) : "", bezahlung: r.bereits_bezahlt ? (r.bezahlart && (E.bezahlarten || []).includes(r.bezahlart) ? r.bezahlart : (E.bezahlarten || []).includes("PayPal") && /paypal/i.test(r.zahlungsbedingung || "") ? "PayPal" : "Überweisung") : (r.lastschrift ? "Lastschrift" : "Überweisung")};
  let lid = v.lieferant_id || "";
  const neuL = {kurzname: (L.name || "").replace(/\s+(GmbH|KG|AG|SE|eG)\b.*$/i, "").trim() || L.name || "", name: L.name || "", gruppe: "",
    strasse: L.strasse || "", plz: L.plz || "", ort: L.ort || "", ustid: L.ustid || "", iban: L.iban || "", bic: L.bic || "", telefon: L.telefon || "", email: L.email || ""};
  const zeilen = (v.zeilen || []).map(z => ({...z, preis_uebernehmen: true, neu_anlegen: !z.material_id && z.aktion === "lager", auftrag_id: ""}));
  const kostenOpt = w => Object.entries(v.kostenarten || {}).map(([k, l]) => `<option value="${k}" ${k === w ? "selected" : ""}>${esc(l)}</option>`).join("");
  const katOpt = w => Object.entries(v.kategorien || {}).map(([k, l]) => `<option value="${k}" ${k === w ? "selected" : ""}>${esc(l)}</option>`).join("");

  const hg = document.createElement("div");
  hg.className = "modal-hg";
  hg.innerHTML = `<div class="modal" style="width:min(1250px,97vw);max-height:95vh;overflow:auto">
    <h3 style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap">Rechnung einlesen <span class="hinweis" style="font-weight:400">${esc(v.dateiname)} · ${esc(v.format)}</span>
      <a class="btn" href="/api/eingang/datei/${v.token}" target="_blank" style="margin-left:auto">📄 Original ansehen</a>${v.format !== "PDF ohne E-Rechnung" ? `<button class="btn" type="button" id="eXml">🔍 XML</button>` : ""}</h3>
    ${v.doppelt ? `<div class="kachel" style="border-left:4px solid var(--rot);margin-bottom:8px">Diese Rechnung ist schon als Zahlungsauftrag <a href="#/zahlung/${v.doppelt.id}">${esc(v.doppelt.nummer)}</a> erfasst.</div>` : ""}
    ${(v.hinweise || []).map(h => `<div class="hinweis" style="margin-bottom:4px">ℹ ${esc(h)}</div>`).join("")}
    <div class="ein-kopf form" style="grid-template-columns:1fr 1fr">
      <div>
        ${zeile("Lieferant", `<select id="eLief"><option value="">– noch nicht angelegt –</option>${lieferanten.map(l => `<option value="${l.id}" ${l.id === lid ? "selected" : ""}>${esc(l.kurzname)} (${l.nummer})</option>`).join("")}</select>`)}
        <div id="eNeuL"></div>
        ${zeile("Erkannt", `<span class="hinweis" style="padding-top:5px">${esc(L.name || "–")}${L.ustid ? " · " + esc(L.ustid) : ""}${L.ort ? " · " + esc(L.plz || "") + " " + esc(L.ort) : ""}</span>`)}
        ${zeile("IBAN / BIC", `<input data-k="iban" value="${esc(ibanFormat(kopf.iban))}" style="font-family:monospace;flex:2"><input data-k="bic" value="${esc(kopf.bic)}" style="font-family:monospace;flex:1" placeholder="BIC">`)}
        ${zeile("Auftrag", `<select data-k="auftrag_id">${aOpt(kopf.auftrag_id)}</select>`)}
        ${zeile("Bemerkung", `<input data-k="bemerkung" value="" placeholder="optional, erscheint im Zahlungsauftrag">`)}
      </div>
      <div>
        ${zeile("Rechnungsnr.", `<input data-k="belegnr" value="${esc(kopf.belegnr)}">`)}
        ${zeile("Datum", `<input type="date" data-k="belegdatum" value="${esc(kopf.belegdatum)}">`)}
        ${zeile("Zu zahlen", `<input data-k="betrag" class="zahl" value="${n2(kopf.betrag)}" style="width:110px;flex:0 0 110px"> € brutto · USt <select data-k="vorsteuer" style="flex:0 0 70px">${[19, 7, 0].map(x => `<option value="${x}" ${+kopf.vorsteuer === x ? "selected" : ""}>${x} %</option>`).join("")}</select>`)}
        ${zeile("Fällig", `<input type="date" data-k="faellig" value="${esc(kopf.faellig)}">${r.zahlungsbedingung ? `<span class="hinweis" style="padding-top:5px">${esc(r.zahlungsbedingung)}</span>` : ""}`)}
        ${zeile("Skonto", `<input data-k="skonto" class="zahl" value="${n2(kopf.skonto)}" style="width:60px;flex:0 0 60px"> % bis <input type="date" data-k="skonto_bis" value="${esc(kopf.skonto_bis)}">`)}
        ${zeile("Bereits bezahlt", `<input type="date" data-k="bezahlt" value="${esc(kopf.bezahlt)}" title="leer = noch zu überweisen"><select data-k="bezahlung" style="flex:0 0 140px">${opts(E.bezahlarten || ["Überweisung"], kopf.bezahlung)}</select>`)}
      </div>
    </div>
    <h4 style="margin:12px 0 6px">Rechnungszeilen <span class="hinweis" style="font-weight:400">· jede Zeile prüfen und zuordnen; ✓ „merken“ schlägt das beim nächsten Mal für diesen Artikel wieder vor</span></h4>
    <datalist id="eMat">${materialien.map(m => `<option value="${esc(matText(m))}">`).join("")}</datalist>
    <div style="max-height:52vh;overflow:auto;border:1px solid var(--linie);border-radius:6px"><table class="ein-tab"><thead><tr>
      <th style="width:90px">Art.-Nr.</th><th>Bezeichnung</th><th style="width:120px">Menge</th><th style="width:95px;text-align:right">Netto €</th><th style="width:120px">Ziel</th><th>Zuordnung</th><th style="width:60px">merken</th><th style="width:30px"></th></tr></thead>
      <tbody id="eZeilen"></tbody></table></div>
    <div style="display:flex;gap:10px;align-items:center;margin-top:8px;flex-wrap:wrap">
      <button class="btn" id="eZeileNeu" type="button">+ Zeile</button>
      <span style="flex:1"></span>
      <span id="eSumme" class="hinweis"></span>
    </div>
    <div class="knoepfe"><button class="btn" data-x="0">Abbrechen</button><button class="btn prim" data-x="1">Zahlungsauftrag anlegen und buchen</button></div>
  </div>`;
  document.body.appendChild(hg);
  const neuLZeichnen = () => {
    $("#eNeuL", hg).innerHTML = lid ? "" : `${zeile("", `<span style="color:var(--rot);padding-top:5px">Lieferant „${esc(L.name || neuL.kurzname || "unbekannt")}“ ist noch nicht angelegt.</span><button class="btn" type="button" id="eNeuLief" style="flex:0 0 auto">Lieferant anlegen …</button>`)}`;
    if (!lid) $("#eNeuLief", hg).onclick = () => anlegen();
  };
  const selZeichnen = () => { $("#eLief", hg).innerHTML = `<option value="">– noch nicht angelegt –</option>` + lieferanten.map(l => `<option value="${l.id}" ${l.id === lid ? "selected" : ""}>${esc(l.kurzname)} (${l.nummer})</option>`).join(""); };
  // Lieferant noch nicht angelegt: nachfragen, ob er mit den erkannten Daten angelegt werden soll
  const anlegen = async () => {
    const l = await lieferantNeuDialog(L, neuL, v.mail_von);
    if (!l) return false;
    lieferanten.push(l); lid = l.id; selZeichnen(); neuLZeichnen();
    toast(`Lieferant ${l.kurzname} (${l.nummer}) angelegt`);
    return true;
  };
  neuLZeichnen();
  $("#eLief", hg).onchange = e => { lid = +e.target.value || ""; neuLZeichnen(); };
  const xb = $("#eXml", hg); if (xb) xb.onclick = () => xmlAnsicht(`xml/eingang/${v.token}`, "Eingangsrechnung");
  if (!lid) setTimeout(() => anlegen(), 50);
  $$("[data-k]", hg).forEach(el => el.addEventListener(el.tagName === "SELECT" || el.type === "date" ? "change" : "input", () => {
    kopf[el.dataset.k] = el.value;
    if (el.dataset.k === "auftrag_id") zeilenZeichnen();
    if (el.dataset.k === "betrag" || el.dataset.k === "vorsteuer") summeZeigen();
  }));

  const zielZelle = (z, i) => {
    if (z.aktion === "kosten") return `<span class="hinweis">nur im Zahlungsauftrag, keine Buchung</span>`;
    if (z.aktion === "werkzeug") return `<div class="ein-ziel"><div class="zl">in die Werkzeugverwaltung als <select data-z="werkzeug_art" data-i="${i}">${opts(wzMeta.arten || [], z.werkzeug_art || "")}</select></div>
      <span class="hinweis">Seriennummer, Standort und Prüftermin lassen sich dort nachtragen.</span></div>`;
    const matFeld = `<input list="eMat" data-z="material" data-i="${i}" value="${esc(z.material || "")}" placeholder="Material suchen …" style="flex:1;min-width:180px">`;
    const neuFeld = !z.material_id ? `<label class="zl" style="gap:4px"><input type="checkbox" data-z="neu_anlegen" data-i="${i}" ${z.neu_anlegen ? "checked" : ""}> neu anlegen als <select data-z="kategorie" data-i="${i}">${katOpt(z.kategorie)}</select></label>` : "";
    const preis = z.material_id || z.neu_anlegen ? `<label class="zl hinweis" style="gap:4px"><input type="checkbox" data-z="preis_uebernehmen" data-i="${i}" ${z.preis_uebernehmen ? "checked" : ""}> EK-Preis ${z.menge ? n2(z.netto / z.menge, 2) : ""} € übernehmen</label>` : "";
    if (z.aktion === "lager") return `<div class="ein-ziel"><div class="zl">${matFeld}</div>${neuFeld}${preis}</div>`;
    return `<div class="ein-ziel"><div class="zl"><select data-z="auftrag_id" data-i="${i}" style="flex:1">${aOpt(z.auftrag_id || kopf.auftrag_id, "– Auftrag wählen –")}</select>
      <select data-z="kostenart" data-i="${i}" style="flex:0 0 130px">${kostenOpt(z.kostenart)}</select></div>
      <div class="zl">${matFeld}</div><span class="hinweis">Material optional – nur für die Statistik</span></div>`;
  };
  const zeilenZeichnen = () => {
    $("#eZeilen", hg).innerHTML = zeilen.map((z, i) => `<tr class="e-${z.aktion}">
      <td><input data-z="artnr" data-i="${i}" value="${esc(z.artnr || "")}" style="width:84px">${z.ean ? `<div class="hinweis" title="EAN">${esc(z.ean)}</div>` : ""}</td>
      <td><textarea data-z="bezeichnung" data-i="${i}" rows="${Math.min(4, String(z.bezeichnung || "").split("\n").length + 1)}">${esc(z.bezeichnung || "")}</textarea>${z.hinweis ? `<div class="hinweis">${esc(z.hinweis)}</div>` : ""}</td>
      <td><div class="zl" style="display:flex;gap:3px"><input data-z="menge" data-i="${i}" class="zahl" value="${n2(z.menge, z.menge % 1 ? 3 : 0)}" style="width:58px"><input data-z="einheit" data-i="${i}" value="${esc(z.einheit || "")}" style="width:52px"></div></td>
      <td><input data-z="netto" data-i="${i}" class="zahl" value="${n2(z.netto)}" style="width:86px;text-align:right">${z.menge && z.netto ? `<div class="hinweis" style="text-align:right">${n2(z.netto / z.menge, 2)} €/${esc(z.einheit || "St.")}</div>` : ""}</td>
      <td><select data-z="aktion" data-i="${i}">${EIN_ZIELE.map(([k, l]) => `<option value="${k}" ${k === z.aktion ? "selected" : ""}>${l}</option>`).join("")}</select>${z.gelernt ? `<div class="ein-gelernt">✓ gemerkt</div>` : ""}</td>
      <td>${zielZelle(z, i)}</td>
      <td style="text-align:center"><input type="checkbox" data-z="merken" data-i="${i}" ${z.merken ? "checked" : ""} title="Zuordnung für diesen Artikel dieses Lieferanten merken"></td>
      <td><button class="btn rot" data-weg="${i}" type="button" title="Zeile entfernen" style="padding:2px 7px">✕</button></td></tr>`).join("")
      || `<tr><td colspan="8" class="hinweis" style="padding:14px">Keine Rechnungszeilen gelesen. Für eine reine Zahlung reicht das; Material oder Werkzeug lässt sich mit „+ Zeile“ selbst eintragen.</td></tr>`;
    $$("[data-z]", hg).forEach(el => el.addEventListener(el.type === "checkbox" || el.tagName === "SELECT" ? "change" : "input", () => {
      const z = zeilen[+el.dataset.i], k = el.dataset.z;
      if (el.type === "checkbox") z[k] = el.checked;
      else if (["menge", "netto"].includes(k)) z[k] = zahlEin(el.value);
      else if (k === "material") {
        const m = matNachText.get(el.value);
        z.material = el.value; z.material_id = m ? m.id : null;
        if (m) { z.neu_anlegen = false; z.kategorie = m.kategorie; }
        if ((m && !el.dataset.hatte) || (!m && el.dataset.hatte)) { el.dataset.hatte = m ? "1" : ""; return zeilenZeichnenBehalten(el); }
        return;
      } else z[k] = el.value;
      if (k === "aktion") { z.neu_anlegen = z.aktion === "lager" && !z.material_id; zeilenZeichnen(); }
      if (["menge", "netto"].includes(k)) summeZeigen();
    }));
    $$("[data-weg]", hg).forEach(b => b.onclick = () => { zeilen.splice(+b.dataset.weg, 1); zeilenZeichnen(); });
    summeZeigen();
  };
  // nach Materialwahl neu zeichnen, Fokus auf das nächste sinnvolle Feld
  const zeilenZeichnenBehalten = el => { const i = el.dataset.i; zeilenZeichnen(); const f = $(`[data-z=material][data-i="${i}"]`, hg); if (f) { f.dataset.hatte = zeilen[i].material_id ? "1" : ""; } };
  const summeZeigen = () => {
    const netto = zeilen.reduce((s, z) => s + (+z.netto || 0), 0);
    const brutto = zahlEin(kopf.betrag) || 0;
    const erw = r.netto || (brutto / (1 + (+kopf.vorsteuer || 0) / 100));
    const diff = Math.abs(netto - erw) > 0.05 && zeilen.length;
    $("#eSumme", hg).innerHTML = `Zeilen netto <b>${eur(netto)}</b> · Rechnung netto ${eur(erw)}${diff ? ` <span style="color:var(--rot)">· Abweichung ${eur(netto - erw)}</span>` : zeilen.length ? ` <span style="color:var(--gruen)">✓</span>` : ""}`;
  };
  zeilenZeichnen();
  $("#eZeileNeu", hg).onclick = () => { zeilen.push({artnr: "", bezeichnung: "", menge: 1, einheit: "Stk.", netto: 0, aktion: "werkzeug", merken: false, kostenart: "kleinmaterial", kategorie: "artikel"}); zeilenZeichnen(); };
  const zu = () => hg.remove();
  hg.addEventListener("keydown", e => { if (e.key === "Escape") zu(); });
  $("[data-x='0']", hg).onclick = zu;
  $("[data-x='1']", hg).onclick = async () => {
    const knopf = $("[data-x='1']", hg);
    if (!lid && !await anlegen()) return toast("Bitte einen vorhandenen Lieferanten wählen oder den neuen anlegen.", true);
    const body = {token: v.token, endung: v.endung, format: v.format, lieferant_id: lid || null, trotzdem: !!v.doppelt, rechnungspost_id: v.rechnungspost_id || null,
      lieferant_neu: {...neuL, kurzname: neuL.kurzname}, kopf: {...kopf, betrag: zahlEin(kopf.betrag), skonto: zahlEin(kopf.skonto)},
      zeilen: zeilen.map(z => ({...z, material: undefined}))};
    if (v.doppelt && !await frage(`Diese Rechnung ist schon als ${v.doppelt.nummer} erfasst.\n\nTrotzdem noch einmal anlegen?`, {ok: "Trotzdem anlegen"})) return;
    knopf.disabled = true; knopf.textContent = "wird gebucht …";
    try {
      const e = await api("eingang/buchen", {method: "POST", body});
      zu();
      const teile = [e.lager && `${e.lager}× Lager`, e.auftrag && `${e.auftrag}× Auftrag`, e.werkzeug && `${e.werkzeug}× Werkzeug`, e.neu_material && `${e.neu_material} Material neu`].filter(Boolean);
      toast(`Zahlungsauftrag ${e.zahlung} angelegt${teile.length ? " · " + teile.join(" · ") : ""}`);
      danach && danach(e);
    } catch (err) { toast(err.message, true); knopf.disabled = false; knopf.textContent = "Zahlungsauftrag anlegen und buchen"; }
  };
}

// ---------- Werkzeugverwaltung (Reiter unter Material) ----------
const wzFilter = {q: "", status: "aktiv", art: ""};
async function werkzeugListe() {
  matKopf("werkzeuge");
  const meta = await api("werkzeuge/meta");
  const z = $("#inhalt");
  const zeichnen = async () => {
    const liste = await api("werkzeuge?" + new URLSearchParams(wzFilter));
    sortierung.wz ||= {k: "nummer", ab: false};
    const heuteIso = heute();
    const termin = (d, faellig) => d ? `<span style="${faellig ? "color:var(--rot);font-weight:600" : ""}">${datum(d)}</span>` : "";
    const t = tabelle("wz", [
      {k: "nummer", t: "Nr.", f: w => `<a href="#" data-wz="${w.id}">${esc(w.nummer)}</a>`},
      {k: "bezeichnung", t: "Bezeichnung", f: w => `<b style="font-weight:500">${esc(String(w.bezeichnung || "").split("\n")[0])}</b>${w.seriennr ? `<div class="hinweis">SN ${esc(w.seriennr)}</div>` : ""}`},
      {k: "art", t: "Art"},
      {k: "hersteller", t: "Hersteller"},
      {k: "kaufdatum", t: "Gekauft", f: w => datum(w.kaufdatum)},
      {k: "preis", t: "Preis netto", r: 1, f: w => w.preis ? `<span class="nw">${eur(w.preis)}</span>${w.gwg ? `<div class="hinweis" title="Geringwertiges Wirtschaftsgut (bis ${zahlDE(meta.gwg_grenze, 0)} € netto je Stück)">GWG</div>` : ""}` : ""},
      ...(liste.some(w => w.restwert != null) ? [{k: "restwert", t: "Restwert", r: 1, f: w => w.restwert != null ? `<span class="nw" title="Linear über ${zahlDE(w.nutzungsdauer, w.nutzungsdauer % 1 ? 1 : 0)} Jahre abgeschrieben">${eur(w.restwert)}</span>` : ""}] : []),
      {k: "lieferant", t: "Lieferant", f: w => w.lieferant ? `${esc(w.lieferant)}${w.zahlung_id ? `<div class="hinweis nw"><a href="#/zahlung/${w.zahlung_id}">${esc(w.zahlungsnr || "Rechnung")}</a></div>` : ""}` : ""},
      {k: "standort", t: "Standort"},
      {k: "pruefung_bis", t: "Prüfung", f: w => termin(w.pruefung_bis, w.pruefung_faellig)},
      {k: "wartung_bis", t: "Wartung", f: w => termin(w.wartung_bis, w.wartung_faellig)},
      {k: "garantie_bis", t: "Garantie", f: w => w.garantie_bis ? `<span class="${w.garantie_bis < heuteIso ? "hinweis" : ""}">${datum(w.garantie_bis)}</span>` : ""},
      {k: "status", t: "Status", f: w => w.status === "in Betrieb" ? `<span class="hinweis nw">in Betrieb</span>` : `<b>${esc(w.status)}</b>`},
    ], liste, {klick: w => werkzeugBearbeiten(w.id, meta, zeichnen), leer: "Noch keine Werkzeuge. Sie entstehen automatisch beim Einlesen einer Rechnung (Ziel „Werkzeug“) oder mit „+ Werkzeug“."});
    const summe = liste.reduce((s, w) => s + (w.preis || 0), 0);
    const mitRest = liste.filter(w => w.restwert != null);
    const rest = mitRest.reduce((s, w) => s + w.restwert, 0);
    $("#wzL").innerHTML = t.html + (liste.length ? `<div class="hinweis" style="text-align:right;margin-top:6px">${liste.length} Werkzeuge · Anschaffungswert ${eur(summe)} netto${mitRest.length ? ` · Restwert ${eur(rest)} (${mitRest.length} mit Nutzungsdauer)` : ""}</div>` : "");
    t.binden(zeichnen);
    $$("[data-wz]").forEach(a => a.onclick = e => { e.preventDefault(); werkzeugBearbeiten(+a.dataset.wz, meta, zeichnen); });
  };
  z.innerHTML = `<div class="titel"><h2>Werkzeuge & Maschinen</h2>
      <div class="such"><input id="wzQ" placeholder="Bezeichnung, Nr., Seriennr., Standort …" value="${esc(wzFilter.q)}" style="width:260px">
        <select id="wzS">${[["aktiv", "Alle aktiven"], ["faellig", "Prüfung/Wartung fällig"], ...meta.status.map(s => [s, s]), ["", "Alle"]].map(([v, l]) => `<option value="${v}" ${v === wzFilter.status ? "selected" : ""}>${l}</option>`).join("")}</select>
        <select id="wzA">${opts(meta.arten, wzFilter.art, "Alle Arten")}</select></div>
      <div class="rechts"><button class="btn" id="wzPdf" title="Liste mit den aktuellen Filtern als PDF, mit Gesamtanschaffungswert">📄 PDF</button><button class="btn prim" id="wzNeu">+ Werkzeug</button></div></div>
    <div id="wzL"></div>
    <p class="hinweis">Elektrische Geräte brauchen eine regelmäßige Prüfung (DGUV Vorschrift 3, in Werkstätten meist jährlich). Fällige Prüf- und Wartungstermine erscheinen rot.
    GWG = geringwertiges Wirtschaftsgut bis ${zahlDE(meta.gwg_grenze, 0)} € netto, kann sofort abgeschrieben werden – das entscheidet die Buchhaltung.</p>`;
  let tm; $("#wzQ").oninput = e => { wzFilter.q = e.target.value; clearTimeout(tm); tm = setTimeout(zeichnen, 250); };
  $("#wzS").onchange = e => { wzFilter.status = e.target.value; zeichnen(); };
  $("#wzA").onchange = e => { wzFilter.art = e.target.value; zeichnen(); };
  $("#wzPdf").onclick = () => window.open("/liste/werkzeuge.pdf?" + new URLSearchParams(wzFilter), "_blank");
  $("#wzNeu").onclick = async () => { const w = await api("werkzeuge", {method: "POST", body: {bezeichnung: "Neues Werkzeug", art: "Elektrowerkzeug"}}); werkzeugBearbeiten(w.id, meta, zeichnen, true); };
  await zeichnen();
}

async function werkzeugBearbeiten(id, meta, danach, neu = false) {
  const w = await api("werkzeuge/" + id);
  const f = (k, l, typ = "text", extra = "") => zeile(l, `<input name="${k}" type="${typ}" value="${esc(w[k] ?? "")}" ${extra}>`);
  const d = await modal(`${w.nummer} · Werkzeug`, `<div class="form" style="grid-template-columns:1fr 1fr">
      ${zeile("Bezeichnung", `<textarea name="bezeichnung" rows="2" style="width:100%">${esc(w.bezeichnung)}</textarea>`, true)}
      ${zeile("Art", `<select name="art">${opts(meta.arten, w.art)}</select>`)}${zeile("Status", `<select name="status">${opts(meta.status, w.status)}</select>`)}
      ${f("hersteller", "Hersteller")}${f("artikelnr", "Modell / Art.-Nr.")}
      ${f("seriennr", "Seriennummer")}${zeile("Standort", `<input name="standort" value="${esc(w.standort)}" list="wzOrte"><datalist id="wzOrte">${(meta.standorte || []).map(s => `<option value="${esc(s)}">`).join("")}</datalist>`)}
      ${f("kaufdatum", "Gekauft am", "date")}${zeile("Preis netto", `<input name="preis" class="zahl" value="${n2(w.preis)}" style="width:110px;flex:0 0 110px"> € · Menge <input name="menge" class="zahl" value="${n2(w.menge, w.menge % 1 ? 2 : 0)}" style="width:60px;flex:0 0 60px">`)}
      ${zeile("Nutzungsdauer", `<input name="nutzungsdauer" class="zahl" value="${w.nutzungsdauer ? n2(w.nutzungsdauer, w.nutzungsdauer % 1 ? 1 : 0) : ""}" style="width:60px;flex:0 0 60px"> Jahre
        <span class="hinweis" style="padding-top:6px">${w.restwert != null ? "Restwert heute " + eur(w.restwert) : "für die lineare Abschreibung"}</span>`)}${zeile("", "")}
      ${f("pruefung_bis", "Nächste Prüfung", "date")}${f("wartung_bis", "Nächste Wartung", "date")}
      ${f("garantie_bis", "Garantie bis", "date")}${zeile("Rechnung", w.zahlung_id ? `<a href="#/zahlung/${w.zahlung_id}" style="padding-top:6px">${esc(w.zahlungsnr || "")} ${esc(w.rechnung || "")}${w.lieferant ? " · " + esc(w.lieferant) : ""}</a>` : `<input name="rechnung" value="${esc(w.rechnung)}">`)}
      ${zeile("Bemerkungen", `<textarea name="bemerkungen" rows="2" style="width:100%">${esc(w.bemerkungen)}</textarea>`, true)}
    </div>
    <div id="wzAS" style="margin-top:6px"></div>
    <div style="margin-top:8px"><button class="btn rot" id="wzDel" type="button">Werkzeug löschen</button></div>`, "Speichern", hg => {
      $(".modal", hg).style.width = "min(860px,96vw)";
      if (typeof asWerkzeugInfo === "function") asWerkzeugInfo($("#wzAS", hg), id);
      $$("textarea", hg).forEach(t => t.addEventListener("keydown", e => e.stopPropagation()));
      $("#wzDel", hg).onclick = async () => {
        if (!await frage(`${w.nummer} löschen?\n\nTipp: Verkaufte oder kaputte Geräte besser auf „ausgemustert“ setzen, dann bleibt die Historie erhalten.`)) return;
        await api("werkzeuge/" + id, {method: "DELETE"}); hg.remove(); toast("Werkzeug gelöscht"); danach && danach();
      };
    });
  if (!d) { if (neu) danach && danach(); return; }
  try { await api("werkzeuge/" + id, {method: "PUT", body: {...d, preis: zahlEin(d.preis), menge: zahlEin(d.menge), nutzungsdauer: zahlEin(d.nutzungsdauer)}}); toast("Gespeichert"); }
  catch (e) { toast(e.message, true); }
  danach && danach();
}

// ---------- Werkzeuge importieren (CSV / Excel) ----------
async function werkzeugImport(inEinstellungen) {
  if (!inEinstellungen) matKopf("werkzeuge");
  const z = $("#inhalt");
  let datei = null, info = null;
  const opt = {doppelte: "ueberspringen", blatt: null, gelbe_ueberspringen: true};
  z.innerHTML = `
    <div class="titel"><h2>Werkzeuge importieren</h2><div class="rechts"><a class="btn" href="#/material/werkzeuge">← Zur Werkzeugliste</a></div></div>
    <div class="kachel">
      <p style="margin-top:0">Bitte die Werkzeugliste als <b>Excel (.xlsx)</b> oder <b>CSV</b> wählen. Die erste Zeile muss die Spaltenüberschriften enthalten, z. B. „Bezeichnung“, „Hersteller“,
      „Seriennummer“, „Kaufdatum“, „Preis“. Danach wird jede Spalte einem Feld zugeordnet; vor dem Import erscheint eine Vorschau.</p>
      <div class="pb-drop" id="wiDrop">Datei hierher ziehen oder <a href="#" id="wiWahl">Datei wählen</a><input type="file" id="wiDatei" accept=".csv,.txt,.xlsx" hidden></div>
    </div>
    <div id="wiSchritt2"></div>`;
  const pruefen = async () => {
    try { info = await api("werkzeuge/import", {method: "POST", body: {...datei, zuordnung: info ? info.zuordnung : null, blatt: opt.blatt, gelbe_ueberspringen: opt.gelbe_ueberspringen}}); opt.blatt = info.blatt || null; zeichnen(); }
    catch (e) { toast(e.message, true); }
  };
  const lesen = async f => { datei = {daten: await dateiAlsBase64(f), dateiname: f.name}; info = null; opt.blatt = null; await pruefen(); };
  const zeichnen = () => {
    const beispiel = i => info.beispiele.map(r => r[i]).filter(Boolean).slice(0, 3).map(x => esc(String(x).slice(0, 40))).join(" · ");
    const blattWahl = info.blaetter && info.blaetter.length > 1
      ? `<div class="kachel" style="margin-top:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap"><b>Tabellenblatt</b>
          <select id="wiBlatt" style="flex:0 0 220px">${opts(info.blaetter, info.blatt)}</select>
          <span class="hinweis">Die Arbeitsmappe hat ${info.blaetter.length} Blätter – importiert wird nur das gewählte.</span></div>` : "";
    const gelbInfo = info.excel
      ? (info.gelb ? `<div class="kachel" style="margin-top:12px;border-left:4px solid #f2c200">
          <label style="display:flex;gap:8px;align-items:flex-start"><input type="checkbox" id="wiGelb" ${opt.gelbe_ueberspringen ? "checked" : ""} style="margin-top:3px">
          <span><b>${info.gelb} gelb markierte Zeile${info.gelb === 1 ? "" : "n"} nicht übernehmen</b> (${eur(info.gelb_summe)})<br>
          <span class="hinweis">z. B. ${info.gelb_beispiele.map(esc).join(", ")}${info.gelb > info.gelb_beispiele.length ? " …" : ""}</span></span></label></div>`
          : `<p class="hinweis" style="margin-top:12px">Im Blatt sind keine gelb markierten Zeilen.</p>`)
      : `<p class="hinweis" style="margin-top:12px">Hinweis: Eine CSV-Datei enthält keine Farben. Sind in Excel Zeilen farbig markiert (z. B. gelb = noch nicht gekauft), lade bitte die <b>.xlsx</b>-Datei hoch – dann kann das Programm diese Zeilen erkennen und weglassen.</p>`;
    $("#wiSchritt2").innerHTML = `${blattWahl}${gelbInfo}
      <h3 style="margin-top:16px">1. Spalten zuordnen <span class="hinweis" style="font-weight:400">· ${esc(datei.dateiname)}${info.blatt ? " · Blatt „" + esc(info.blatt) + "“" : ""} · ${info.anzahl} Werkzeuge in ${info.zeilen} Zeilen</span></h3>
      <table class="liste"><tr><th>Spalte in der Datei</th><th>Beispiele</th><th style="width:260px">wird übernommen als</th></tr>
        ${info.kopf.map((hd, i) => `<tr><td><b>${esc(hd || "(ohne Überschrift)")}</b></td><td class="hinweis">${beispiel(i)}</td>
          <td><select data-wi="${i}" style="width:100%"><option value="">— nicht übernehmen —</option>${info.felder.map(([k, n]) => `<option value="${k}" ${info.zuordnung[i] === k ? "selected" : ""}>${n}</option>`).join("")}</select></td></tr>`).join("")}
      </table>
      <p class="hinweis">Datumsangaben dürfen als 12.03.2019, 2019-03-12, 03/2019, nur Jahr oder Excel-Datum vorliegen. Preise mit oder ohne €-Zeichen. Unbekannte Arten ordnet das Programm nach der Bezeichnung ein (z. B. „Säge“ → Elektrowerkzeug), ein bekannter Lieferant wird verknüpft, sonst landet er in den Bemerkungen.</p>
      <h3 style="margin-top:16px">2. Vorschau</h3>
      ${info.vorschau.length ? `<table class="liste"><tr><th>Nr.</th><th>Bezeichnung</th><th>Art</th><th>Hersteller</th><th>Seriennr.</th><th>Standort</th><th>Gekauft</th><th class="r">Preis</th><th>Status</th><th></th></tr>
        ${info.vorschau.map(w => `<tr><td>${esc(w.nummer || "") || "<span class=hinweis>neu</span>"}</td><td><b>${esc(w.bezeichnung)}</b>${w.bemerkungen ? `<div class="hinweis">${esc(w.bemerkungen).slice(0, 80)}</div>` : ""}</td><td>${esc(w.art)}</td><td>${esc(w.hersteller || "")}</td>
          <td>${esc(w.seriennr || "")}</td><td>${esc(w.standort || "")}</td><td>${datum(w.kaufdatum)}</td><td class="r nw">${w.preis ? eur(w.preis) : ""}</td><td>${esc(w.status)}</td>
          <td>${w._doppelt ? `<span class="tag">schon vorhanden</span>` : ""}</td></tr>`).join("")}</table>
        <div class="hinweis" style="text-align:right;margin-top:6px">${info.vorschau.length < info.anzahl ? `Vorschau der ersten ${info.vorschau.length} von ${info.anzahl} · ` : ""}Anschaffungswert laut Datei: <b>${eur(info.summe)}</b></div>`
        : `<div class="leer">Mit dieser Zuordnung entsteht kein Werkzeug. Bitte mindestens die Bezeichnung zuordnen.</div>`}
      ${info.doppelte_nummern && info.doppelte_nummern.length ? `<p class="hinweis" style="color:var(--rot)">In der Datei sind Inventarnummern doppelt vergeben: ${info.doppelte_nummern.map(esc).join(", ")}. Beide Stücke werden übernommen, das zweite bekommt eine neue Nummer (W…) – die alte Nummer steht dann in den Bemerkungen.</p>` : ""}
      <h3 style="margin-top:16px">3. Importieren</h3>
      <div class="form" style="grid-template-columns:1fr">
        ${zeile("Schon vorhandene", `<div class="radio" style="flex-wrap:wrap"><label><input type="radio" name="wiD" value="ueberspringen" ${opt.doppelte === "ueberspringen" ? "checked" : ""}> überspringen</label><label><input type="radio" name="wiD" value="aktualisieren" ${opt.doppelte === "aktualisieren" ? "checked" : ""}> mit den Daten aus der Datei aktualisieren</label>
          <span class="hinweis" style="padding-top:4px">${info.doppelte} schon vorhanden (gleiche Seriennummer, Inventarnummer oder Bezeichnung + Kaufdatum)</span></div>`)}
        ${zeile("", `<button class="btn prim" id="wiOk" ${info.vorschau.length ? "" : "disabled"}>${info.anzahl} Werkzeuge importieren</button><a class="btn" href="${inEinstellungen ? "#/einstellungen/import/werkzeuge" : "#/material/werkzeuge"}">Abbrechen</a>`)}
      </div>`;
    $$("[data-wi]").forEach(s => s.onchange = () => {
      const i = s.dataset.wi;
      if (s.value && s.value !== "bemerkungen") Object.keys(info.zuordnung).forEach(k => { if (info.zuordnung[k] === s.value && k !== i) info.zuordnung[k] = ""; });
      info.zuordnung[i] = s.value; pruefen();
    });
    $$("[name=wiD]").forEach(r => r.onchange = () => opt.doppelte = r.value);
    if ($("#wiBlatt")) $("#wiBlatt").onchange = e => { opt.blatt = e.target.value; info.zuordnung = null; info = null; pruefen(); };
    if ($("#wiGelb")) $("#wiGelb").onchange = e => { opt.gelbe_ueberspringen = e.target.checked; pruefen(); };
    $("#wiOk").onclick = async () => {
      const b = $("#wiOk"); b.disabled = true; b.textContent = "Wird importiert …";
      try {
        const r = await api("werkzeuge/import", {method: "POST", body: {...datei, zuordnung: info.zuordnung, doppelte: opt.doppelte, blatt: opt.blatt, gelbe_ueberspringen: opt.gelbe_ueberspringen, ausfuehren: true}});
        toast(`${r.neu} Werkzeuge neu` + (r.aktualisiert ? `, ${r.aktualisiert} aktualisiert` : "") + (r.uebersprungen ? `, ${r.uebersprungen} übersprungen` : "")
          + (r.umnummeriert && r.umnummeriert.length ? ` · neu nummeriert: ${r.umnummeriert.join("; ")}` : ""));
        location.hash = "#/material/werkzeuge";
      } catch (e) { toast(e.message, true); b.disabled = false; b.textContent = "Erneut versuchen"; }
    };
  };
  $("#wiWahl").onclick = e => { e.preventDefault(); $("#wiDatei").click(); };
  $("#wiDatei").onchange = e => e.target.files[0] && lesen(e.target.files[0]);
  const drop = $("#wiDrop");
  drop.ondragover = e => { e.preventDefault(); drop.classList.add("ueber"); };
  drop.ondragleave = () => drop.classList.remove("ueber");
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove("ueber"); if (e.dataTransfer.files[0]) lesen(e.dataTransfer.files[0]); };
}

// ---------- Rechnungen aus dem Postfach (Vorschläge zum Buchen) ----------
async function rechnungspostBox(ziel, danach) {
  if (!ziel) return;
  let zeigeAlle = false;
  const zeichnen = async () => {
    let liste = [];
    try { liste = await api("rechnungspost?status=" + (zeigeAlle ? "" : "neu")); } catch (e) { ziel.innerHTML = ""; return; }
    const neu = liste.filter(r => r.status === "neu").length;
    const stTxt = {neu: "", erfasst: "schon erfasst", gebucht: "gebucht", ignoriert: "ignoriert"};
    ziel.innerHTML = `<div class="kachel" style="margin:0 0 12px">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><h4 style="margin:0;flex:1">📨 Rechnungen aus dem Postfach ${neu ? `<span class="st-anz">${neu}</span>` : ""}</h4>
        <label class="hinweis"><input type="checkbox" id="rpAlle" ${zeigeAlle ? "checked" : ""}> auch erledigte zeigen</label>
        <button class="btn" id="rpSuchen" title="Posteingang und Rechnungsordner jetzt lesen">Postfach jetzt prüfen</button></div>
      ${liste.length ? `<table class="liste" style="margin-top:8px"><tr><th>Eingang</th><th>Lieferant</th><th>Rechnung</th><th class="r">Betrag</th><th>Auftrag</th><th>Datei</th><th></th></tr>
        ${liste.map(r => `<tr><td>${datum((r.datum || "").slice(0, 10))}<div class="hinweis">${esc(kurz(r.betreff || "", 40))}</div></td>
          <td>${r.lieferant ? `<a href="#/lieferant/${r.lieferant_id}">${esc(r.lieferant)}</a>` : `<span class="hinweis">${esc(r.von || "unbekannt")}</span>`}</td>
          <td>${esc(r.belegnr || "–")}${r.belegdatum ? ` <span class="hinweis">vom ${datum(r.belegdatum)}</span>` : ""}<div class="hinweis">${esc(r.format || "")}${r.hinweis ? " · " + esc(r.hinweis) : ""}</div></td>
          <td class="r">${r.betrag != null ? eur(r.betrag) : ""}</td>
          <td>${r.auftragsnr ? `<a href="#/auftrag/${r.auftrag_id}">${esc(r.auftragsnr)}</a>` : ""}</td>
          <td class="hinweis">${esc(kurz(r.dateiname || "", 28))}${r.datei && r.format && r.format !== "PDF ohne E-Rechnung" ? ` <a href="#" data-rpx="${r.id}" title="XML ansehen und prüfen">XML</a>` : ""}</td>
          <td style="white-space:nowrap">${r.status === "neu" ? `<button class="btn prim" data-rpl="${r.id}">Prüfen und buchen …</button> <button class="btn" data-rpi="${r.id}" title="Kein Rechnungsbeleg oder schon anders erfasst">ignorieren</button>`
            : `${r.zahlung ? `<a href="#/zahlung/${r.zahlung_id}">${esc(r.zahlung)}</a> ` : ""}<span class="hinweis">${stTxt[r.status] || esc(r.status)}</span>${r.status === "ignoriert" ? ` <button class="btn" data-rpw="${r.id}">wieder vorschlagen</button>` : ""}`}</td></tr>`).join("")}</table>`
        : `<p class="hinweis" style="margin:6px 0 0">Keine neuen Rechnungen im Postfach. Gelesen werden der Posteingang (Mails von den hinterlegten Mailadressen der Lieferanten) und der Rechnungsordner aus Einstellungen › E-Mail.</p>`}</div>`;
    $("#rpAlle", ziel).onchange = e => { zeigeAlle = e.target.checked; zeichnen(); };
    $("#rpSuchen", ziel).onclick = async ev => {
      ev.target.disabled = true; ev.target.textContent = "wird gelesen …";
      try { await api("korrespondenz/pruefen", {method: "POST"}); } catch (e) { toast(e.message, true); }
      zeichnen();
    };
    $$("[data-rpx]", ziel).forEach(b => b.onclick = ev => { ev.preventDefault(); xmlAnsicht(`xml/rechnungspost/${b.dataset.rpx}`, "Rechnung aus dem Postfach"); });
    $$("[data-rpi]", ziel).forEach(b => b.onclick = async () => { await api(`rechnungspost/${b.dataset.rpi}/ignorieren`, {method: "POST"}); zeichnen(); });
    $$("[data-rpw]", ziel).forEach(b => b.onclick = async () => { await api(`rechnungspost/${b.dataset.rpw}/wieder`, {method: "POST"}); zeichnen(); });
    $$("[data-rpl]", ziel).forEach(b => b.onclick = async () => {
      toast("Rechnung wird gelesen …");
      let v;
      try { v = await api(`rechnungspost/${b.dataset.rpl}/lesen`, {method: "POST"}); } catch (e) { return toast(e.message, true); }
      const [lieferanten, auftraege, materialien, wzMeta] = await Promise.all([
        api("lieferanten?status=alle").catch(() => []), api("auftraege").catch(() => []),
        api("material?status=aktiv").catch(() => []), api("werkzeuge/meta").catch(() => ({arten: []}))]);
      eingangDialog(v, {lieferanten, auftraege, materialien, wzMeta}, e => { zeichnen(); danach && danach(e); });
    });
  };
  zeichnen();
}

// Neuen Lieferanten aus den erkannten Rechnungsdaten anlegen (mit Rückfrage)
async function lieferantNeuDialog(L, neuL, mailVon) {
  const email = L.email || (String(mailVon || "").match(/[\w.+-]+@[\w.-]+/) || [""])[0];
  const d = await modal("Lieferant anlegen?", `
    <p style="margin-top:0">Der Lieferant dieser Rechnung ist noch nicht angelegt. Soll er mit den erkannten Daten angelegt werden? Die Angaben lassen sich hier noch korrigieren.</p>
    <div class="zeile"><label>Kurzname</label><div><input name="kurzname" value="${esc(neuL.kurzname || L.name || "")}"></div></div>
    <div class="zeile"><label>Firmenname</label><div><input name="empfaenger" value="${esc(L.name || "")}" placeholder="vollständiger Name laut Rechnung"></div></div>
    <div class="zeile"><label>Gruppe</label><div><select name="gruppe">${opts(E.lieferantengruppen || [], neuL.gruppe || "", "Gruppe …")}</select></div></div>
    <div class="zeile"><label>Straße</label><div><input name="strasse" value="${esc(L.strasse || "")}"></div></div>
    <div class="zeile"><label>PLZ / Ort</label><div><input name="plz" value="${esc(L.plz || "")}" style="flex:0 0 80px"><input name="ort" value="${esc(L.ort || "")}"></div></div>
    <div class="zeile"><label>E-Mail</label><div><input name="email1" value="${esc(email)}"></div></div>
    <div class="zeile"><label>Telefon</label><div><input name="telefon" value="${esc(L.telefon || "")}"></div></div>
    <div class="zeile"><label>USt-IdNr.</label><div><input name="ustid" value="${esc(L.ustid || "")}"></div></div>
    <div class="zeile"><label>IBAN / BIC</label><div><input name="iban" value="${esc(ibanFormat(L.iban || ""))}" style="font-family:monospace;flex:2"><input name="bic" value="${esc(L.bic || "")}" style="font-family:monospace;flex:1"></div></div>
    <p class="hinweis">„Abbrechen“ lässt den Lieferanten offen; dann kann im Dialog ein vorhandener Lieferant gewählt werden.</p>`, "Lieferant anlegen");
  if (!d) return null;
  if (!d.kurzname.trim()) { toast("Bitte einen Kurznamen eingeben.", true); return null; }
  try {
    return await api("lieferanten", {method: "POST", body: {kurzname: d.kurzname.trim(), empfaenger: d.empfaenger.trim() || d.kurzname.trim(),
      gruppe: d.gruppe || "Sonstiges", anschrift: [d.empfaenger.trim() || d.kurzname.trim(), d.strasse.trim()].filter(Boolean).join("\n"),
      plz: d.plz.trim(), ort: d.ort.trim(), email1: d.email1.trim(), telefon: d.telefon.trim(), ustid: d.ustid.replace(/\s/g, ""),
      iban: d.iban.replace(/\s/g, "").toUpperCase(), bic: d.bic.replace(/\s/g, "").toUpperCase()}});
  } catch (e) { toast(e.message, true); return null; }
}
