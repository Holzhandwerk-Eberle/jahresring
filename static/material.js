// =====================================================================
//  Material: Stamm, Beschlägesets, Auftrag buchen, Lager buchen, Statistik
// =====================================================================
let MAT_META = null;
async function matMeta() { if (!MAT_META) MAT_META = await api("material/meta"); return MAT_META; }
const MAT_REITER = [["Holzwerkstoffe", "holzwerkstoffe"], ["Massivholz", "massivholz"], ["Oberflächenstoffe", "beschichtung"],
  ["Chemisch-technische Produkte", "chemie"], ["Beschläge", "beschlaege"], ["Beschlägesets", "sets"], ["Artikel", "artikel"], ["Reste & Platten", "reste"], ["Werkzeuge", "werkzeuge"],
  ["Auftrag buchen", "auftrag"], ["Lager buchen", "lager"], ["Preise einlesen", "preise"], ["Statistik", "statistik"]];
const matFilter = {};
let matSichtbar = [];
const mengeTxt = (v, e) => `${n2(v, Math.abs(v % 1) > 0.0001 ? 3 : 0)} ${esc(e || "")}`;
// Holzwerkstoffe mit Plattenformat und Einheit m²: Fläche je ganzer Platte (für die Stückzahl im Zuschnitt), sonst 0
const plattenFl = m => m && m.kategorie === "holzwerkstoffe" && ["", "platten", "platte", "leimholz"].includes((m.gruppe || "").trim().toLowerCase()) && +m.plattenlaenge > 0 && +m.plattenbreite > 0
  && ["m²", "m2", "qm"].includes((m.einheit || "").toLowerCase().replace(/ /g, "")) ? m.plattenlaenge * m.plattenbreite / 1e6 : 0;
const plattenTxt = (m, menge) => {
  const fl = plattenFl(m); if (!fl) return "";
  const v = menge ?? m.bestand, n = Math.max(0, Math.floor(v / fl + 1e-6)), rest = v - n * fl;
  return `${n} Platte${n === 1 ? "" : "n"}${n >= 0 && rest > 0.005 ? ` + ${n2(rest, 2)} m²` : ""}`;
};
const bestandTxt = m => mengeTxt(m.bestand, m.einheit) + (plattenFl(m) ? ` <span class="hinweis" style="white-space:nowrap">· ${plattenTxt(m)}</span>` : "");
const ersteZeile = t => esc(String(t || "").split("\n")[0]);
const weitereZeilen = t => esc(String(t || "").split("\n").slice(1).join(" ").trim());

function matKopf(aktiv, kontext = "", zurueck = null) {
  kopf({krumen: [["Lager", "#/material/holzwerkstoffe"]], kontext, zurueck,
    reiter: MAT_REITER.map(([l, s]) => [l, `#/material/${s}`, s === aktiv])});
}

async function ansichtMaterial(teil = "holzwerkstoffe", sub) {
  const meta = await matMeta();
  if (teil === "sets") return sub ? setDetail(+sub) : setsListe();
  if (teil === "auftrag") return auftragBuchen(sub);
  if (teil === "lager") return lagerBuchen();
  if (teil === "statistik") return materialStatistik();
  if (teil === "preise") return preisImport();
  if (teil === "reste") return restelager(sub);
  if (teil === "werkzeuge") return sub === "import" ? werkzeugImport() : werkzeugListe();
  if (!meta.kategorien[teil]) teil = "holzwerkstoffe";
  return materialListe(teil);
}

// ---------- Liste je Materialart ----------
async function materialListe(kat) {
  const meta = await matMeta();
  matKopf(kat);
  const f = matFilter[kat] || (matFilter[kat] = {q: "", gruppe: "", status: "aktiv"});
  const name = meta.kategorien[kat];
  const artikel = kat === "artikel", ohneV = artikel || kat === "beschlaege";
  const zeichnen = async () => {
    const liste = await api("material?" + new URLSearchParams({kat, q: f.q, gruppe: f.gruppe, status: f.status}));
    const t = tabelle("mat-" + kat, [
      {k: "nummer", t: "Nummer", f: z => `<a href="#/mat/${z.id}">${esc(z.nummer)}</a>`},
      {k: "bezeichnung", t: "Bezeichnung", f: z => `<b style="font-weight:500">${ersteZeile(z.bezeichnung)}</b>${weitereZeilen(z.bezeichnung) ? `<div class="hinweis">${weitereZeilen(z.bezeichnung).slice(0, 140)}</div>` : ""}`},
      ...(["holzwerkstoffe", "massivholz"].includes(kat) ? [{k: "dicke", t: "Dicke", r: 1, f: z => z.dicke ? n2(z.dicke, 1) : ""}, ...(kat === "holzwerkstoffe" ? [{k: "plattenlaenge", t: "Format", r: 1, f: z => z.plattenlaenge && z.plattenbreite ? `${n2(z.plattenlaenge, 0)} × ${n2(z.plattenbreite, 0)}` : ""}] : [])] : []),
      {k: "ek_preis", t: "EK-Preis", r: 1, f: z => eur(z.ek_preis)},
      {k: "einheit", t: "Einheit"},
      ...(artikel ? [{k: "vk_preis", t: "VK-Preis", r: 1, f: z => z.vk_preis ? eur(z.vk_preis) : ""}] : []),
      {k: "preis_vom", t: "Datum", f: z => datum(z.preis_vom)},
      ...(ohneV ? [] : [{k: "verschnitt", t: "Verschnitt", r: 1, f: z => n2(z.verschnitt, 0) + " %"}]),
      {k: "gruppe", t: "Gruppe"},
      {k: "lieferant", t: "Lieferant", f: z => esc(z.lieferant || "")},
      {k: "bestand", t: "Lager", r: 1, f: z => z.lager ? `<span class="${z.bestand < z.mindestbestand ? "rot" : ""}">${bestandTxt(z)}</span>` : ""},
    ], liste, {klick: z => location.hash = `#/mat/${z.id}`,
      leer: f.q ? "Kein Eintrag passt zur Suche." : `Noch keine ${name}. Über das Symbol rechts oben lässt sich der erste Eintrag anlegen.`});
    $("#liste").innerHTML = `<div class="hinweis" style="margin:0 0 6px">${liste.length} ${liste.length === 1 ? "Eintrag" : "Einträge"}</div>` + t.html;
    matSichtbar = liste.map(x => x.id);
    t.binden(zeichnen);
  };
  $("#inhalt").innerHTML = `
    <div class="titel"><h2>${esc(name)}</h2>
      <div class="such">
        <input id="mQ" placeholder="Nummer, Bezeichnung, Bestellnr., Lieferant …" value="${esc(f.q)}" style="width:300px">
        <select id="mGr">${opts((E.material_gruppen || meta.standard_gruppen)[kat] || [], f.gruppe, "Alle Gruppen")}</select>
        <select id="mSt">${[["aktiv", "Aktive"], ["alle", "Alle"], ["inaktiv", "Inaktive"]].map(([v, l]) => `<option value="${v}" ${f.status === v ? "selected" : ""}>${l}</option>`).join("")}</select>
      </div>
      <div class="rechts"><button class="btn" id="mEt" title="QR-Etiketten für alle angezeigten Einträge">🏷 Etiketten</button><button class="ib" id="mNeu" title="Neu">${ic("neu")}</button></div>
    </div><div id="liste"></div>`;
  let tm;
  $("#mEt").onclick = () => etikettenDialog("material", matSichtbar);
  $("#mQ").oninput = e => { f.q = e.target.value; clearTimeout(tm); tm = setTimeout(zeichnen, 250); };
  $("#mGr").onchange = e => { f.gruppe = e.target.value; zeichnen(); };
  $("#mSt").onchange = e => { f.status = e.target.value; zeichnen(); };
  $("#mNeu").onclick = async () => {
    const gruppen = (E.material_gruppen || meta.standard_gruppen)[kat] || [];
    const d = await modal(`Neu: ${name}`, `
      <div class="zeile"><label>Nummer</label><div><input name="nummer" placeholder="leer = automatisch, z. B. LHPCAB oder Art.-Nr."></div></div>
      <div class="zeile"><label>Bezeichnung</label><div><input name="bezeichnung"></div></div>
      <div class="zeile"><label>Gruppe</label><div><select name="gruppe">${opts(gruppen, f.gruppe || gruppen[0])}</select></div></div>`, "Anlegen");
    if (!d) return;
    try { const m = await api("material", {method: "POST", body: {...d, kategorie: kat}}); location.hash = `#/mat/${m.id}`; }
    catch (e) { toast(e.message, true); }
  };
  $("#mQ").focus();
  await zeichnen();
}

// ---------- Detail ----------
let LIEF_CACHE = null;
async function ansichtMaterialDetail(id, teil = "stamm") {
  const meta = await matMeta();
  const m = await api("material/" + id);
  const kat = m.kategorie;
  kopf({krumen: [["Lager", "#/material/holzwerkstoffe"], [meta.kategorien[kat], `#/material/${kat}`]],
    kontext: `${esc(meta.kategorien[kat])} <b>${esc(m.nummer)}</b> · ${ersteZeile(m.bezeichnung)}${m.lieferant ? " · " + esc(m.lieferant) : ""}`,
    zurueck: `#/material/${kat}`,
    reiter: [["Stammdaten", `#/mat/${id}`, teil === "stamm"], ["Statistik", `#/mat/${id}/statistik`, teil === "statistik"],
      ...(darf("arbeitsschutz") || darf("material", 2) ? [["Datenblätter & Sicherheit", `#/mat/${id}/sicherheit`, teil === "sicherheit"]] : [])]});
  if (teil === "statistik") return materialEinzelStatistik(m);
  if (teil === "sicherheit") return asMaterialSicherheit(m);
  if (!LIEF_CACHE) LIEF_CACHE = await api("lieferanten?status=alle");
  const gruppen = (E.material_gruppen || meta.standard_gruppen)[kat] || [];
  const artikel = kat === "artikel", holz = ["holzwerkstoffe", "massivholz"].includes(kat), beschlag = kat === "beschlaege";
  const zahl = (feld, nk = 2, extra = "") => `<input data-f="${feld}" value="${n2(m[feld] || 0, nk)}" style="width:110px;text-align:right" ${extra}>`;
  const kalkPreis = () => (+m.ek_preis || 0) * (1 + (+m.verschnitt || 0) / 100);
  const vkZeile = i => zeile(`VK-Preis${artikel ? " " + (i || 1) : ""}`, `${zahl("vk_preis" + i)} <span style="padding-top:5px">€ je ${esc(m.einheit)}</span><span class="hinweis" style="padding-top:5px" data-brutto="${i}"></span>
      <span style="padding-top:5px;margin-left:auto">Aufschlag</span>${zahl("aufschlag" + i, 2, 'style="width:80px;text-align:right"')} <span style="padding-top:5px">%</span>`, true);
  $("#inhalt").innerHTML = `
    <div class="titel"><h2>${esc(meta.kategorien[kat])}</h2><span class="speicher"></span>
      <div class="rechts"><a class="btn pk" href="/liste/etiketten?typ=material&ids=${m.id}" target="_blank">🏷 Etikett</a><button class="btn pk" id="mKopie">${ic("uebernehmen")} Kopieren</button><button class="btn pk rot" id="mDel">${ic("loeschen")} Löschen</button></div></div>
    <div class="form" id="f">
      ${zeile("Nummer", `<input value="${esc(m.nummer)}" readonly title="Die Nummer ist nach dem Anlegen fest" style="font-weight:600;background:var(--grau-h, #f3f0ec);max-width:220px"><span class="hinweis" style="padding-top:5px">fest vergeben, nicht änderbar</span>`)}
      ${zeile("Gruppe", `<select data-f="gruppe">${opts(gruppen.includes(m.gruppe) || !m.gruppe ? gruppen : [m.gruppe, ...gruppen], m.gruppe)}</select>
        <label style="display:flex;gap:5px;align-items:center;flex:0 0 auto;padding:4px 0"><input type="checkbox" data-f="aktiv" ${m.aktiv ? "checked" : ""}> aktiv</label>`)}
      ${zeile("Bezeichnung", `<textarea data-f="bezeichnung" rows="4" data-text="1">${esc(m.bezeichnung)}</textarea>`, true)}
      ${holz ? zeile("Dicke", `${zahl("dicke", 1, 'style="width:90px;text-align:right"')} <span style="padding-top:5px">mm</span>`) : ""}
      ${kat === "holzwerkstoffe" ? zeile("Plattenformat", `${zahl("plattenlaenge", 0, 'style="width:90px;text-align:right" placeholder="Länge"')} <span style="padding-top:5px">×</span> ${zahl("plattenbreite", 0, 'style="width:90px;text-align:right" placeholder="Breite"')} <span style="padding-top:5px">mm</span><span class="hinweis" style="padding-top:5px">Länge × Breite der ganzen Platte, z. B. 2800 × 2070 – damit das Zuschnittprogramm die richtige Platte aus dem Lager zieht</span>`) : ""}
      ${zeile("EK-Preis", `${zahl("ek_preis")} <span style="padding-top:5px">€ je</span><select data-f="einheit" style="flex:0 0 120px">${opts(meta.einheiten, m.einheit)}</select>`)}
      ${artikel || beschlag ? "" : zeile("Umrechnung", `<span style="padding-top:5px">1 Einheit =</span> ${zahl("umrechnung", 3, 'style="width:90px;text-align:right" placeholder="0"')} <span class="hinweis" style="padding-top:5px">nur nötig, wenn die Einheit nicht die Recheneinheit der Kalkulation ist: bei Kanten laufende Meter (1 Rolle = 50 lfm), bei Platten, Furnier und Oberflächen m² (1 Dose = 12 m², 1 Tafel = 5,796 m²), bei Massivholz m³. Leer oder 0 = der Preis gilt je Recheneinheit.</span>`, true)}
      ${zeile("Preis vom", `<input type="date" data-f="preis_vom" value="${esc(m.preis_vom || "")}" style="flex:0 0 170px">`)}
      ${artikel || beschlag ? "" : zeile("Verschnitt", `${zahl("verschnitt", 0, 'style="width:80px;text-align:right"')} <span style="padding-top:5px">%</span>`)}
      ${artikel ? "" : zeile(beschlag ? "Kosten je Einheit" : "Kalkulationspreis", `<span style="padding-top:5px" id="kpreis"></span>`)}
      ${vkZeile("")}${artikel ? vkZeile("2") + vkZeile("3") : ""}
      <div class="sektion">Lieferant / Bestellnummer</div>
      ${zeile("Lieferant", `<select data-f="lieferant_id"><option value="">—</option>${LIEF_CACHE.map(l => `<option value="${l.id}" ${l.id === m.lieferant_id ? "selected" : ""}>${l.nummer} ${esc(l.kurzname)}</option>`).join("")}</select>`)}
      ${zeile("Bestellnr.", `<input data-f="bestellnr" value="${esc(m.bestellnr)}">`)}
      ${zeile("CAD-Kürzel", `<input data-f="cad" value="${esc(m.cad || "")}" placeholder="z. B. FPYW19 – Werkstoffnummer aus dem CAD für den Stücklistenimport">`)}
      ${zeile("EAN", `<input data-f="ean" value="${esc(m.ean || "")}" placeholder="Strichcode-Nummer, wird beim Rechnungsimport erkannt">`)}
      ${zeile("Bemerkungen", `<textarea data-f="bemerkungen" rows="3" data-text="1">${esc(m.bemerkungen)}</textarea>`, true)}
      <div class="sektion">Lager</div>
      ${zeile("Lager führen", `<div class="radio"><label><input type="radio" name="lg" value="1" ${m.lager ? "checked" : ""}> Ja</label><label><input type="radio" name="lg" value="0" ${m.lager ? "" : "checked"}> Nein</label></div>`)}
      ${zeile("Lagerort", `<select data-f="lagerort">${opts(E.lagerorte || [], m.lagerort, "ohne")}</select>`)}
      ${zeile("Mindestbestand", `${zahl("mindestbestand", 2)} <span style="padding-top:5px">${esc(m.einheit)}</span>`)}
      ${zeile("Lagerbestand", `<span style="padding-top:5px"><b class="${m.lager && m.bestand < m.mindestbestand ? "rot" : ""}">${bestandTxt(m)}</b> · Lagerpreis ${eur(m.lagerpreis)} je ${esc(m.einheit)}${m.kalkpreis && Math.abs(m.kalkpreis - m.lagerpreis) > 0.004 ? ` · Kalkulationspreis ${eur(m.kalkpreis)}` : ""} · Wert ${eur(m.bestand * (m.lagerpreis || m.ek_preis || 0))}</span><a class="btn" href="#/material/lager" style="margin-left:auto">Lager buchen</a>`)}
    </div>`;
  const anzeigen = () => {
    const k = $("#kpreis"); if (k) k.innerHTML = beschlag
      ? `${eur(+m.ek_preis || 0)} je ${esc(m.einheit)} <span class="hinweis">(ohne Verschnitt – im Auftrag: Kosten je Einheit × Menge = Gesamtkosten)</span>`
      : `${eur(kalkPreis())} je ${esc(m.einheit)} <span class="hinweis">(EK + ${n2(m.verschnitt || 0, 0)} % Verschnitt, so wird im Auftrag gerechnet)</span>`;
    $$("[data-brutto]").forEach(el => { const v = +m["vk_preis" + el.dataset.brutto] || 0; el.textContent = v ? `(${eur(v * 1.19)} inkl. 19 % USt.)` : ""; });
  };
  anzeigen();
  autospeichern($("#f"), "material/" + id, r => {
    Object.assign(m, r);
    ["vk_preis", "vk_preis2", "vk_preis3", "aufschlag", "aufschlag2", "aufschlag3"].forEach(k => { const el = $(`[data-f=${k}]`); if (el && !el.matches(":focus")) el.value = n2(m[k] || 0); });
    anzeigen();
  });
  $$("[name=lg]").forEach(el => el.onchange = async () => { await api("material/" + id, {method: "PUT", body: {lager: +el.value}}); m.lager = +el.value; });
  $("#mKopie").onclick = async () => { const n = await api(`material/${id}/kopieren`, {method: "POST"}); toast("Kopie angelegt"); location.hash = `#/mat/${n.id}`; };
  $("#mDel").onclick = async () => {
    if (!await frage(`${m.nummer} löschen?`)) return;
    const r = await api("material/" + id, {method: "DELETE"});
    toast(r.inaktiv ? "Wurde schon gebucht und ist jetzt inaktiv gesetzt" : "Gelöscht"); location.hash = `#/material/${kat}`;
  };
}

async function materialEinzelStatistik(m) {
  const s = await api(`material/${m.id}/statistik`);
  const verbrauch = s.buchungen.reduce((a, b) => a + b.menge, 0), wert = s.buchungen.reduce((a, b) => a + b.betrag, 0);
  $("#inhalt").innerHTML = `
    <div class="titel"><h2>Statistik ${esc(m.nummer)}</h2></div>
    <div class="st-kacheln" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin-bottom:14px">
      <div class="kachel"><div class="hinweis">Auf Aufträge gebucht</div><b style="font-size:20px">${mengeTxt(verbrauch, m.einheit)}</b><div class="hinweis">${eur(wert)} in ${new Set(s.buchungen.map(b => b.auftrag_id)).size} Aufträgen</div></div>
      <div class="kachel"><div class="hinweis">Lagerbestand</div><b style="font-size:20px">${m.lager ? mengeTxt(m.bestand, m.einheit) : "kein Lagerartikel"}</b><div class="hinweis">${m.lager ? (plattenFl(m) ? plattenTxt(m) + " · " : "") + "Wert " + eur(m.bestand * (m.lagerpreis || m.ek_preis || 0)) : ""}</div></div>
      <div class="kachel"><div class="hinweis">In Beschlägesets</div><b style="font-size:20px">${s.sets.length}</b><div class="hinweis">${s.sets.map(x => esc(x.nummer)).join(", ")}</div></div>
    </div>
    <h3>Buchungen auf Aufträge</h3>
    ${s.buchungen.length ? `<table class="liste"><tr><th>Datum</th><th>Auftrag</th><th class="r">Menge</th><th class="r">Einzelpreis</th><th class="r">Betrag</th><th>Bemerkung</th></tr>
      ${s.buchungen.map(b => `<tr><td>${datum(b.datum)}</td><td><a href="#/auftrag/${b.auftrag_id}/sollist">${esc(b.auftrag)}</a> ${esc(b.auftrag_bez)}</td><td class="r">${mengeTxt(b.menge, b.einheit)}</td><td class="r">${eur(b.einzelpreis)}</td><td class="r">${eur(b.betrag)}</td><td>${esc(b.bemerkung)}</td></tr>`).join("")}</table>` : `<div class="leer">Noch nicht auf Aufträge gebucht.</div>`}
    <h3 style="margin-top:16px">Lagerbewegungen</h3>
    ${s.bewegungen.length ? `<table class="liste"><tr><th>Datum</th><th>Art</th><th class="r">Menge</th><th class="r">Preis</th><th>Auftrag</th><th>Bemerkung</th></tr>
      ${s.bewegungen.map(b => `<tr><td>${datum(b.datum)}</td><td>${{zugang: "Zugang", abgang: "Abgang", auftrag: "Auftrag", inventur: "Inventur", rueckbuchung: "Rückbuchung"}[b.art] || b.art}</td><td class="r ${b.menge < 0 ? "rot" : ""}">${mengeTxt(b.menge, b.einheit)}</td><td class="r">${eur(b.preis)}</td><td>${esc(b.auftrag || "")}</td><td>${esc(b.bemerkung)}</td></tr>`).join("")}</table>` : `<div class="leer">Keine Lagerbewegungen.</div>`}`;
}

// ---------- Auswahl-Dialog (für Sets, Buchungen, Auftragswerte) ----------
async function materialWaehlen(kategorien = null, titel = "Material wählen") {
  const meta = await matMeta();
  let wahl = null, liste = [];
  const ok = await modal(titel, `
    <div style="display:flex;gap:6px;margin-bottom:8px"><input id="mwQ" placeholder="Suchen …" style="flex:1"><select id="mwK"><option value="">${kategorien ? "passende Arten" : "alle Arten"}</option>${Object.entries(meta.kategorien).map(([k, l]) => `<option value="${k}">${l}</option>`).join("")}</select></div>
    <div id="mwL" style="max-height:55vh;overflow:auto"></div>`, "Übernehmen", hg => {
    $(".modal", hg).style.width = "min(820px,96vw)";
    let t;
    const laden = async () => {
      const k = $("#mwK", hg).value;
      const q = $("#mwQ", hg).value;
      const ks = k ? [k] : (kategorien || [""]);
      liste = (await Promise.all(ks.map(x => api("material?" + new URLSearchParams({kat: x, q}))))).flat();
      $("#mwL", hg).innerHTML = liste.length ? `<table class="liste">${liste.slice(0, 300).map((m, i) => `<tr class="klick" data-mw="${i}"><td><b>${esc(m.nummer)}</b></td><td>${ersteZeile(m.bezeichnung)}${m.dicke ? ` <span class="hinweis">${n2(m.dicke, 1)} mm</span>` : ""}</td><td class="r nw">${eur(m.ek_preis)} / ${esc(m.einheit)}</td><td class="hinweis">${esc(m.lieferant || "")}</td></tr>`).join("")}</table>`
        : `<div class="leer">Nichts gefunden. <a href="#/material/${kategorien ? kategorien[0] : "holzwerkstoffe"}" data-schl>Material anlegen</a></div>`;
      $$("[data-mw]", hg).forEach(tr => {
        tr.onclick = () => { $$("[data-mw]", hg).forEach(x => x.classList.remove("gewaehlt")); tr.classList.add("gewaehlt"); wahl = liste[+tr.dataset.mw]; };
        tr.ondblclick = () => { wahl = liste[+tr.dataset.mw]; $("[data-x='1']", hg).click(); };
      });
      $$("[data-schl]", hg).forEach(a => a.onclick = () => hg.remove());
    };
    $("#mwQ", hg).oninput = () => { clearTimeout(t); t = setTimeout(laden, 200); };
    $("#mwQ", hg).addEventListener("keydown", e => { if (e.key === "Enter" && liste.length === 1) wahl = liste[0]; });
    $("#mwK", hg).onchange = laden;
    laden(); setTimeout(() => $("#mwQ", hg).focus(), 30);
  });
  return ok ? wahl : null;
}

// ---------- Beschlägesets ----------
async function setsListe() {
  matKopf("sets");
  const liste = await api("materialsets");
  const t = tabelle("sets", [
    {k: "nummer", t: "Nummer", f: z => `<a href="#/material/sets/${z.id}">${esc(z.nummer)}</a>`},
    {k: "bezeichnung", t: "Bezeichnung"}, {k: "anzahl", t: "Teile", r: 1}, {k: "summe", t: "EK gesamt", r: 1, f: z => eur(z.summe)},
  ], liste, {klick: z => location.hash = `#/material/sets/${z.id}`, leer: "Noch keine Beschlägesets. Ein Set fasst mehrere Beschläge zusammen, z. B. „Schubkasten komplett“."});
  $("#inhalt").innerHTML = `<div class="titel"><h2>Beschlägesets</h2><div class="rechts"><button class="ib" id="sNeu" title="Neues Set">${ic("neu")}</button></div></div>${t.html}`;
  t.binden(setsListe);
  $("#sNeu").onclick = async () => {
    const d = await modal("Neues Beschlägeset", `<div class="zeile"><label>Nummer</label><div><input name="nummer" placeholder="leer = automatisch"></div></div>
      <div class="zeile"><label>Bezeichnung</label><div><input name="bezeichnung" placeholder="z. B. Schubkasten Movento 500 komplett"></div></div>`, "Anlegen");
    if (!d) return;
    try { const s = await api("materialsets", {method: "POST", body: d}); location.hash = `#/material/sets/${s.id}`; } catch (e) { toast(e.message, true); }
  };
}

async function setDetail(id) {
  matKopf("sets");
  const s = await api("materialsets/" + id);
  const pos = s.positionen.map(p => ({...p}));
  const speichern = async () => { const r = await api("materialsets/" + id, {method: "PUT", body: {positionen: pos}}); s.summe = r.summe; $("#sSum").textContent = eur(r.summe); };
  const zeichnen = () => {
    $("#inhalt").innerHTML = `
      <div class="titel"><h2>Beschlägeset</h2><span class="speicher"></span><div class="rechts"><button class="btn pk rot" id="sDel">${ic("loeschen")} Löschen</button></div></div>
      <div class="form" id="f">${zeile("Nummer", `<input data-f="nummer" value="${esc(s.nummer)}">`)}${zeile("Bezeichnung", `<input data-f="bezeichnung" value="${esc(s.bezeichnung)}">`)}
        ${zeile("Bemerkungen", `<textarea data-f="bemerkungen" rows="2" data-text="1">${esc(s.bemerkungen)}</textarea>`, true)}</div>
      <table class="liste" style="margin-top:12px"><tr><th>Nummer</th><th>Bezeichnung</th><th class="r">Menge</th><th>Einheit</th><th class="r">EK</th><th class="r">Gesamt</th><th></th></tr>
        ${pos.map((p, i) => `<tr><td><a href="#/mat/${p.material_id}">${esc(p.nummer)}</a></td><td>${ersteZeile(p.bezeichnung)}</td>
          <td class="r">${numInp(p.menge, `data-pm="${i}" style="width:80px"`)}</td><td>${esc(p.einheit)}</td><td class="r">${eur(p.ek_preis)}</td>
          <td class="r">${eur(p.menge * p.ek_preis * (1 + (p.verschnitt || 0) / 100))}</td><td><button class="btn rot" data-px="${i}">✕</button></td></tr>`).join("")}
        <tr class="zw"><td colspan="5"><b>Summe EK</b></td><td class="r"><b id="sSum">${eur(s.summe)}</b></td><td></td></tr></table>
      <button class="btn" id="sPlus" style="margin-top:8px">+ Beschlag hinzufügen</button>
      <p class="hinweis">Ein Set lässt sich unter „Auftrag buchen“ komplett auf einen Auftrag buchen.</p>`;
    autospeichern($("#f"), "materialsets/" + id, r => Object.assign(s, r));
    $$("[data-pm]").forEach(el => el.onchange = async () => { pos[+el.dataset.pm].menge = zahlEin(el.value); await speichern(); zeichnen(); });
    $$("[data-px]").forEach(b => b.onclick = async () => { pos.splice(+b.dataset.px, 1); await speichern(); zeichnen(); });
    $("#sPlus").onclick = async () => {
      const m = await materialWaehlen(["beschlaege", "artikel", "chemie"], "Beschlag wählen"); if (!m) return;
      pos.push({material_id: m.id, menge: 1, nummer: m.nummer, bezeichnung: m.bezeichnung, einheit: m.einheit, ek_preis: m.ek_preis, verschnitt: m.verschnitt});
      await speichern(); zeichnen();
    };
    $("#sDel").onclick = async () => { if (!await frage("Set löschen?")) return; await api("materialsets/" + id, {method: "DELETE"}); location.hash = "#/material/sets"; };
  };
  zeichnen();
}

// ---------- Auftrag buchen ----------
const akWahl = {auftrag: null, kostenart: "werkstoffe", titel: 0};
async function auftragBuchen(vorgabe) {
  const meta = await matMeta();
  matKopf("auftrag");
  const auftraege = await api("auftraege");
  if (vorgabe) akWahl.auftrag = +vorgabe;
  const offen = auftraege.filter(a => !["Erledigt", "Abgesagt", "Archiv", "Bezahlt"].includes(a.status));
  if (!akWahl.auftrag && offen.length) akWahl.auftrag = offen[0].id;
  let mat = null;
  $("#inhalt").innerHTML = `
    <div class="titel"><h2>Auftragskosten buchen</h2></div>
    <div class="form" style="grid-template-columns:1fr 1fr">
      ${zeile("Auftrag", `<select id="akA" style="width:100%">${auftraege.map(a => `<option value="${a.id}" ${a.id === akWahl.auftrag ? "selected" : ""}>${esc(a.nummer)} ${esc(a.kunde)} · ${esc(a.bezeichnung)}${a.status ? " (" + esc(a.status) + ")" : ""}</option>`).join("")}</select>`, true)}
      ${zeile("Titel", `<select id="akT"><option value="0">(ohne Titel)</option></select>`)}
      ${zeile("Kostenart", `<select id="akK">${Object.entries(meta.kostenarten).map(([k, l]) => `<option value="${k}" ${k === akWahl.kostenart ? "selected" : ""}>${l}</option>`).join("")}</select>`)}
      ${zeile("Material", `<input id="akMat" readonly placeholder="optional – aus dem Materialstamm wählen" style="cursor:pointer"><button class="btn" id="akMatW" title="Material aus dem Materialstamm wählen">🔍</button><button class="btn" id="akSet" title="Ein Beschlägeset komplett buchen">Set</button>`, true)}
      ${zeile("Bezeichnung", `<input id="akB" placeholder="z. B. Lieferschein-Nr. oder freier Text">`, true)}
      ${zeile("Menge", `<input id="akM" style="width:110px;text-align:right"> <span id="akE" style="padding-top:5px"></span>`)}
      ${zeile("Einzelpreis", `<input id="akP" style="width:110px;text-align:right"> <span style="padding-top:5px">€</span> <span class="hinweis" id="akG" style="padding-top:5px"></span>`)}
      ${zeile("Lager", `<div class="radio"><label><input type="radio" name="akL" value="0" checked> ohne Lager</label><label><input type="radio" name="akL" value="1" disabled> Lagerabgang</label></div>`)}
      ${zeile("Datum", `<input type="date" id="akD" value="${heute()}" style="flex:0 0 170px">`)}
      ${zeile("Bemerkung", `<input id="akBem">`, true)}
      <div class="zeile voll"><label></label><div><button class="btn prim" id="akOk">Buchen</button></div></div>
    </div>
    <div id="akListe" style="margin-top:16px"></div>`;
  const gesamt = () => { const g = zahlEin($("#akM").value) * zahlEin($("#akP").value); $("#akG").textContent = g ? "= " + eur(g) : ""; };
  $("#akM").oninput = gesamt; $("#akP").oninput = gesamt;
  const matSetzen = m => {
    mat = m;
    $("#akMat").value = m ? `${m.nummer} · ${m.bezeichnung.split("\n")[0]}` : "";
    $("#akB").value = m ? m.bezeichnung.split("\n")[0] : $("#akB").value;
    $("#akE").textContent = m ? m.einheit : "";
    $("#akP").value = m ? n2(m.kalkpreis ?? (m.lager && m.lagerpreis ? m.lagerpreis : m.ek_preis)) : "";
    const l = $("[name=akL][value='1']"); l.disabled = !(m && m.lager); if (l.disabled) $("[name=akL][value='0']").checked = true; else l.checked = true;
    if (m) { $("#akK").value = meta.kat_kostenart[m.kategorie] || "werkstoffe"; akWahl.kostenart = $("#akK").value; }
    $("[name=akL][value='1']").parentElement.title = m && m.lager ? `Bestand ${m.bestand} ${m.einheit}` : "nur für Lagerartikel";
    gesamt(); $("#akM").focus();
  };
  $("#akMat").onclick = $("#akMatW").onclick = async () => { const m = await materialWaehlen(null); if (m) matSetzen(m); };
  $("#akK").onchange = e => akWahl.kostenart = e.target.value;
  $("#akT").onchange = e => akWahl.titel = +e.target.value;
  const listeZeigen = async () => {
    const aid = +$("#akA").value; akWahl.auftrag = aid;
    const [ks, si, pl] = await Promise.all([api("auftragskosten?auftrag_id=" + aid), api(`auftraege/${aid}/sollist`), api(`auftraege/${aid}/positionen`)]);
    $("#akT").innerHTML = `<option value="0">(ohne Titel)</option>` + (pl.titel || []).map(t => `<option value="${t.nr}" ${t.nr === akWahl.titel ? "selected" : ""}>T${String(t.nr).padStart(2, "0")} ${esc(t.name)}</option>`).join("");
    const arten = Object.entries(meta.kostenarten);
    const ist = {}; ks.forEach(k => ist[k.kostenart] = (ist[k.kostenart] || 0) + k.betrag);
    $("#akListe").innerHTML = `
      <h3>Soll/Ist dieses Auftrags</h3>
      <table class="liste"><tr><th>Kostenart</th><th class="r">Soll (Kalkulation)</th><th class="r">Ist gesamt</th><th class="r">davon hier gebucht</th><th class="r">Abweichung</th></tr>
        ${arten.map(([k, l]) => { const s = si.soll[k] || 0, i = si.ist[k] || 0; return `<tr><td>${l}</td><td class="r">${eur(s)}</td><td class="r">${eur(i)}</td><td class="r">${ist[k] ? eur(ist[k]) : ""}</td><td class="r ${i > s ? "rot" : ""}">${i - s > 0.004 ? "+" : ""}${eur(i - s)}</td></tr>`; }).join("")}</table>
      <p class="hinweis">Ist = hier gebuchte Auftragskosten plus Lieferantenrechnungen (Zahlungen), die dem Auftrag zugeordnet sind.</p>
      <h3 style="margin-top:14px">Gebuchte Auftragskosten</h3>
      ${ks.length ? `<table class="liste"><tr><th>Datum</th><th>Kostenart</th><th>Material</th><th>Bezeichnung</th><th class="r">Menge</th><th class="r">Einzelpreis</th><th class="r">Betrag</th><th>Lager</th><th></th></tr>
        ${ks.map(k => `<tr><td>${datum(k.datum)}</td><td>${meta.kostenarten[k.kostenart] || k.kostenart}${k.titel ? ` <span class="hinweis">T${String(k.titel).padStart(2, "0")}</span>` : ""}</td><td>${k.material_id ? `<a href="#/mat/${k.material_id}">${esc(k.matnr)}</a>` : ""}</td>
          <td>${esc(k.bezeichnung)}${k.bemerkung ? `<div class="hinweis">${esc(k.bemerkung)}</div>` : ""}</td><td class="r">${mengeTxt(k.menge, k.einheit)}</td><td class="r">${eur(k.einzelpreis)}</td><td class="r">${eur(k.betrag)}</td>
          <td>${k.lager_abgang ? "Abgang" : ""}</td><td><button class="btn rot" data-akx="${k.id}" title="Buchung löschen">✕</button></td></tr>`).join("")}
        <tr class="zw"><td colspan="6"><b>Summe</b></td><td class="r"><b>${eur(ks.reduce((a, b) => a + b.betrag, 0))}</b></td><td colspan="2"></td></tr></table>` : `<div class="leer">Auf diesen Auftrag ist noch nichts gebucht.</div>`}`;
    $$("[data-akx]").forEach(b => b.onclick = async () => { if (!await frage("Buchung löschen? Ein Lagerabgang wird zurückgebucht.")) return; const r = await api("auftragskosten/" + b.dataset.akx, {method: "DELETE"}); if (r && r.hinweis) toast(r.hinweis); listeZeigen(); });
  };
  $("#akA").onchange = () => { akWahl.titel = 0; listeZeigen(); };
  const buchen = async (body) => api("auftragskosten", {method: "POST", body: {auftrag_id: +$("#akA").value, titel: +$("#akT").value, datum: $("#akD").value, ...body}});
  $("#akOk").onclick = async () => {
    try {
      await buchen({kostenart: $("#akK").value, material_id: mat ? mat.id : null, bezeichnung: $("#akB").value, menge: $("#akM").value,
        einzelpreis: $("#akP").value, einheit: mat ? mat.einheit : "", lager_abgang: $("[name=akL]:checked").value === "1", bemerkung: $("#akBem").value});
      toast("Gebucht"); matSetzen(null); $("#akB").value = ""; $("#akM").value = ""; $("#akBem").value = ""; $("#akMat").focus(); listeZeigen();
    } catch (e) { toast(e.message, true); }
  };
  $("#akSet").onclick = async () => {
    const sets = await api("materialsets");
    if (!sets.length) return toast("Noch keine Beschlägesets angelegt.", true);
    const d = await modal("Beschlägeset buchen", `<div class="zeile"><label>Set</label><div><select name="set">${sets.map(s => `<option value="${s.id}">${esc(s.nummer)} · ${esc(s.bezeichnung)} (${eur(s.summe)})</option>`).join("")}</select></div></div>
      <div class="zeile"><label>Anzahl</label><div><input name="anzahl" value="1" style="width:90px"></div></div>
      <p class="hinweis">Jeder Beschlag des Sets wird einzeln als Kostenart „Beschläge“ gebucht, Lagerartikel als Lagerabgang.</p>`, "Buchen");
    if (!d) return;
    const s = await api("materialsets/" + d.set);
    const n = zahlEin(d.anzahl) || 1;
    try {
      for (const p of s.positionen) {
        const m = await api("material/" + p.material_id);
        await buchen({kostenart: "beschlaege", material_id: m.id, menge: p.menge * n, lager_abgang: !!m.lager, bemerkung: `Set ${s.nummer}`});
      }
      toast(`Set ${s.nummer} gebucht`); listeZeigen();
    } catch (e) { toast(e.message, true); listeZeigen(); }
  };
  if (auftraege.length) listeZeigen(); else $("#akListe").innerHTML = `<div class="leer">Noch keine Aufträge vorhanden.</div>`;
}

// ---------- Lager buchen ----------
async function lagerBuchen() {
  matKopf("lager");
  let mat = null;
  const ort = matFilter._lagerort || "";
  $("#inhalt").innerHTML = `
    <div class="titel"><h2>Lager buchen</h2><div class="such"><select id="lO">${opts(E.lagerorte || [], ort, "alle Lagerorte")}</select></div>
      <div class="rechts"><button class="btn" id="lPdf" title="Lagerbestand mit Werten als PDF, z. B. für die Inventur zum Jahresende">📄 Lagerbestand als PDF</button></div></div>
    <div class="form" style="grid-template-columns:1fr 1fr">
      ${zeile("Material", `<input id="lMat" readonly placeholder="Material wählen …" style="cursor:pointer"><button class="btn" id="lMatW" title="Material aus dem Materialstamm wählen">🔍</button>`, true)}
      ${zeile("Buchung", `<div class="radio"><label><input type="radio" name="lA" value="zugang" checked> Lagerzugang</label><label><input type="radio" name="lA" value="abgang"> Lagerabgang</label><label><input type="radio" name="lA" value="inventur"> Inventur (Bestand setzen)</label></div>`, true)}
      ${zeile("Menge", `<input id="lM" style="width:110px;text-align:right"> <span id="lE" style="padding-top:5px"></span><span id="lStk" hidden style="padding-top:5px;margin-left:10px">= <input id="lS" style="width:60px;text-align:right"> Platten</span>`)}
      ${zeile("Einzelpreis", `<input id="lP" style="width:110px;text-align:right"> <span style="padding-top:5px">€</span>`)}
      ${zeile("Datum", `<input type="date" id="lD" value="${heute()}" style="flex:0 0 170px">`)}
      ${zeile("Bemerkung", `<input id="lB" placeholder="z. B. Lieferschein, Inventur">`)}
      <div class="zeile voll"><label></label><div><button class="btn prim" id="lOk">Buchen</button><span class="hinweis" id="lInfo" style="padding-top:6px"></span></div></div>
    </div>
    <div id="lListe" style="margin-top:16px"></div>`;
  const setzen = m => {
    mat = m; $("#lMat").value = m ? `${m.nummer} · ${m.bezeichnung.split("\n")[0]}` : ""; $("#lE").textContent = m ? m.einheit : "";
    $("#lP").value = m ? n2(m.ek_preis) : "";
    $("#lInfo").textContent = m ? `Bestand ${n2(m.bestand, 3)} ${m.einheit}${plattenFl(m) ? " (" + plattenTxt(m) + ")" : ""}${m.lager ? "" : " · wird mit der ersten Buchung zum Lagerartikel"}` : "";
    $("#lStk").hidden = !plattenFl(m); $("#lS").value = "";
    $("#lM").focus();
  };
  $("#lS").oninput = () => { const fl = plattenFl(mat), n = zahlEin($("#lS").value); $("#lM").value = fl && n ? String(Math.round(n * fl * 10000) / 10000).replace(".", ",") : ""; };
  $("#lM").oninput = () => { const fl = plattenFl(mat), v = zahlEin($("#lM").value); $("#lS").value = fl && v ? String(Math.round(v / fl * 100) / 100).replace(".", ",") : ""; };
  $("#lMat").onclick = $("#lMatW").onclick = async () => { const m = await materialWaehlen(null); if (m) setzen(m); };
  $("#lO").onchange = e => { matFilter._lagerort = e.target.value; zeigen(); };
  $("#lPdf").onclick = async () => {
    const jahrEnde = `${new Date().getFullYear() - (new Date().getMonth() < 2 ? 1 : 0)}-12-31`;
    const d = await modal("Lagerbestand als PDF", `
      <div class="zeile"><label>Stand</label><div><select name="art" style="flex:0 0 150px"><option value="heute">heute</option><option value="tag">zum Stichtag</option></select>
        <input type="date" name="stichtag" value="${jahrEnde <= heute() ? jahrEnde : heute()}" style="flex:0 0 170px;visibility:hidden"></div></div>
      <div class="zeile"><label>Lagerort</label><div><select name="lagerort">${opts(E.lagerorte || [], $("#lO").value, "alle Lagerorte")}</select></div></div>
      <p class="hinweis">Zum Stichtag (z. B. 31.12. für die Inventur) rechnet das Programm die Bestände aus den Lagerbewegungen bis zu diesem Tag zurück.</p>`, "PDF öffnen", hg => {
        $("[name=art]", hg).onchange = e => { $("[name=stichtag]", hg).style.visibility = e.target.value === "tag" ? "visible" : "hidden"; };
      });
    if (!d) return;
    const q = {lagerort: d.lagerort || ""};
    if (d.art === "tag" && d.stichtag) q.stichtag = d.stichtag;
    window.open("/liste/lager.pdf?" + new URLSearchParams(q), "_blank");
  };
  const zeigen = async () => {
    const [bestand, bew] = await Promise.all([api("material?" + new URLSearchParams({lager: "1", status: "aktiv"})), api("lager")]);
    const o = $("#lO").value;
    const b = bestand.filter(m => !o || m.lagerort === o);
    $("#lListe").innerHTML = `
      <h3>Lagerbestand${o ? " " + esc(o) : ""} · Wert ${eur(b.reduce((a, m) => a + Math.max(0, m.bestand) * m.lagerpreis, 0))}</h3>
      ${b.length ? `<table class="liste"><tr><th>Nummer</th><th>Bezeichnung</th><th>Lagerort</th><th class="r">Bestand</th><th class="r">Mindestbestand</th><th class="r">Lagerpreis</th><th class="r">Wert</th></tr>
        ${b.map(m => `<tr class="klick" data-lm="${m.id}"><td><a href="#/mat/${m.id}">${esc(m.nummer)}</a></td><td>${ersteZeile(m.bezeichnung)}</td><td>${esc(m.lagerort)}</td>
          <td class="r ${m.bestand < m.mindestbestand ? "rot" : ""}"><b>${mengeTxt(m.bestand, m.einheit)}</b>${plattenFl(m) ? `<div class="hinweis">${plattenTxt(m)}</div>` : ""}</td><td class="r">${m.mindestbestand ? mengeTxt(m.mindestbestand, m.einheit) : ""}</td>
          <td class="r">${eur(m.lagerpreis || m.ek_preis)}</td><td class="r">${eur(Math.max(0, m.bestand) * (m.lagerpreis || m.ek_preis || 0))}</td></tr>`).join("")}</table>` : `<div class="leer">Noch keine Lagerartikel. Bei einem Material „Lager führen: Ja“ wählen oder hier einen Zugang buchen.</div>`}
      <h3 style="margin-top:14px">Letzte Lagerbewegungen</h3>
      ${bew.length ? `<table class="liste"><tr><th>Datum</th><th>Material</th><th>Art</th><th class="r">Menge</th><th class="r">Preis</th><th>Auftrag</th><th>Bemerkung</th></tr>
        ${bew.slice(0, 60).map(x => `<tr><td>${datum(x.datum)}</td><td><a href="#/mat/${x.material_id}">${esc(x.nummer)}</a> ${ersteZeile(x.bezeichnung)}</td><td>${{zugang: "Zugang", abgang: "Abgang", auftrag: "Auftrag", inventur: "Inventur", rueckbuchung: "Rückbuchung"}[x.art] || x.art}</td>
          <td class="r ${x.menge < 0 ? "rot" : ""}">${mengeTxt(x.menge, x.einheit)}</td><td class="r">${eur(x.preis)}</td><td>${esc(x.auftrag || "")}</td><td>${esc(x.bemerkung)}</td></tr>`).join("")}</table>` : `<div class="leer">Noch keine Lagerbewegungen.</div>`}`;
    $$("[data-lm]").forEach(tr => tr.onclick = async ev => { if (ev.target.closest("a")) return; setzen(await api("material/" + tr.dataset.lm)); window.scrollTo({top: 0, behavior: "smooth"}); });
  };
  $("#lOk").onclick = async () => {
    if (!mat) return toast("Bitte zuerst ein Material wählen.", true);
    try {
      const art = $("[name=lA]:checked").value;
      const m = await api("lager", {method: "POST", body: {material_id: mat.id, art, menge: $("#lM").value, preis: $("#lP").value, datum: $("#lD").value, bemerkung: $("#lB").value, lagerort: $("#lO").value}});
      toast(`Gebucht · neuer Bestand ${n2(m.bestand, 3)} ${m.einheit}`); setzen(m); $("#lM").value = ""; $("#lS").value = ""; $("#lB").value = ""; zeigen();
    } catch (e) { toast(e.message, true); }
  };
  zeigen();
}
const MAT_KATEGORIEN_NAMEN = {holzwerkstoffe: "Holzwerkstoffe", massivholz: "Massivholz", beschichtung: "Oberflächenstoffe", chemie: "Chemisch-technische Produkte", beschlaege: "Beschläge", artikel: "Artikel"};

// ---------- Statistik ----------
async function materialStatistik() {
  const meta = await matMeta();
  matKopf("statistik");
  const s = await api("material/statistik");
  const wert = s.lagerwert.reduce((a, x) => a + (x.wert || 0), 0);
  $("#inhalt").innerHTML = `
    <div class="titel"><h2>Material-Statistik ${s.jahr}</h2></div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;margin-bottom:14px">
      <div class="kachel"><div class="hinweis">Lagerwert</div><b style="font-size:22px">${eur(wert)}</b></div>
      <div class="kachel"><div class="hinweis">Unter Mindestbestand</div><b style="font-size:22px" class="${s.knapp.length ? "rot" : ""}">${s.knapp.length}</b></div>
      <div class="kachel"><div class="hinweis">Auf Aufträge gebucht ${s.jahr}</div><b style="font-size:22px">${eur(s.kostenarten.reduce((a, x) => a + x.betrag, 0))}</b></div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px">
      <div><h3>Bestand je Materialart</h3><table class="liste"><tr><th>Art</th><th class="r">Einträge</th><th class="r">im Lager</th><th class="r">Lagerwert</th></tr>
        ${s.lagerwert.map(x => `<tr><td><a href="#/material/${x.kategorie}">${meta.kategorien[x.kategorie] || x.kategorie}</a></td><td class="r">${x.artikel}</td><td class="r">${x.gelagert}</td><td class="r">${eur(x.wert || 0)}</td></tr>`).join("") || `<tr><td colspan="4" class="hinweis">Noch kein Material angelegt.</td></tr>`}</table></div>
      <div><h3>Nachbestellen (unter Mindestbestand)</h3>${s.knapp.length ? `<table class="liste"><tr><th>Nummer</th><th>Bezeichnung</th><th class="r">Bestand</th><th class="r">Mindest</th></tr>
        ${s.knapp.map(x => `<tr><td><a href="#/mat/${x.id}">${esc(x.nummer)}</a></td><td>${ersteZeile(x.bezeichnung)}</td><td class="r rot">${mengeTxt(x.bestand, x.einheit)}</td><td class="r">${mengeTxt(x.mindestbestand, x.einheit)}</td></tr>`).join("")}</table>` : `<div class="leer">Alles ausreichend auf Lager.</div>`}</div>
      <div><h3>Meistgebuchtes Material ${s.jahr}</h3>${s.verbrauch.length ? `<table class="liste"><tr><th>Nummer</th><th>Bezeichnung</th><th class="r">Menge</th><th class="r">Betrag</th><th class="r">Aufträge</th></tr>
        ${s.verbrauch.map(x => `<tr><td><a href="#/mat/${x.id}">${esc(x.nummer)}</a></td><td>${ersteZeile(x.bezeichnung)}</td><td class="r">${mengeTxt(x.menge, x.einheit)}</td><td class="r">${eur(x.betrag)}</td><td class="r">${x.auftraege}</td></tr>`).join("")}</table>` : `<div class="leer">Noch keine Auftragsbuchungen in ${s.jahr}.</div>`}</div>
      <div><h3>Gebucht nach Kostenart ${s.jahr}</h3>${s.kostenarten.length ? `<table class="liste">${s.kostenarten.map(x => `<tr><td>${meta.kostenarten[x.kostenart] || x.kostenart}</td><td class="r">${eur(x.betrag)}</td></tr>`).join("")}</table>` : `<div class="leer">–</div>`}
        <h3 style="margin-top:14px">Preise älter als ein Jahr</h3>${s.alte_preise.length ? `<table class="liste">${s.alte_preise.map(x => `<tr><td><a href="#/mat/${x.id}">${esc(x.nummer)}</a></td><td>${ersteZeile(x.bezeichnung)}</td><td>${datum(x.preis_vom)}</td></tr>`).join("")}</table>` : `<div class="leer">Alle Preise sind aktuell.</div>`}</div>
    </div>`;
}


// ---------- QR-Etiketten ----------
async function etikettenDialog(typ, ids) {
  if (!ids.length) return toast("Keine Einträge ausgewählt", true);
  const d = await modal("QR-Etiketten drucken", `
    <p style="margin-top:0">${ids.length} Etikett${ids.length > 1 ? "en" : ""}. Der QR-Code öffnet mit der Handy-Kamera direkt ${typ === "rest" ? "das Restelager" : "die Materialseite"} im Büro (im WLAN, wenn das Netzwerk eingeschaltet ist).</p>
    <div class="zeile"><label>Format</label><div class="spalte">
      <label><input type="radio" name="format" value="70x74" checked> ${zahlDE(E.etikett_breite ?? 70, 0)} × ${zahlDE(E.etikett_hoehe ?? 74, 0)} mm – ein Etikett je Seite (Etikettendrucker, z. B. Zebra; Größe unter Einstellungen › Werkstatt &amp; Material)</label>
      <label><input type="radio" name="format" value="a4"> A4-Bogen 3 × 8 (70 × 37 mm, z. B. Avery/Herma)</label></div></div>`, "Etiketten öffnen");
  if (!d) return;
  window.open(`/liste/etiketten?typ=${typ}&format=${d.format}&ids=${ids.join(",")}`, "_blank");
}

// ---------- Reste & Platten (gemeinsam mit dem Zuschnittprogramm) ----------
const restFilter = {q: "", verbraucht: false};
async function restelager(markiert) {
  matKopf("reste");
  const z = $("#inhalt");
  const mm = v => n2(+v || 0, (+v || 0) % 1 ? 1 : 0);
  let d, gewaehlt = new Set();
  const zeichnen = () => {
    const q = restFilter.q.toLowerCase();
    const reste = d.reste.filter(r => (restFilter.verbraucht || !r.used) && (!q || [r.no, r.material, r.location, r.from, `${r.length}x${r.width}`, r.thickness].join(" ").toLowerCase().includes(q)))
      .sort((a, b) => (a.material || "").localeCompare(b.material || "") || (b.length * b.width) - (a.length * a.width));
    const flaeche = reste.filter(r => !r.used).reduce((s, r) => s + r.length * r.width / 1e6, 0);
    z.innerHTML = `
      <div class="titel"><h2>Reste & Platten</h2><span class="speicher"></span>
        <div class="rechts"><a class="btn" href="/zuschnitt/" target="_blank">Zuschnittprogramm öffnen</a>
          <label class="btn" title="Lagerdatei der Zuschnitt-App (JSON) einmalig übernehmen">Lagerdatei übernehmen …<input type="file" id="rlImp" accept=".json,application/json" hidden></label></div></div>
      <p class="hinweis" style="margin-top:-6px">Gemeinsamer Bestand mit dem Zuschnittprogramm: Reste, die an der Säge eingelagert oder verbraucht werden, erscheinen hier sofort – und umgekehrt.${d.geaendert ? ` Zuletzt geändert ${datum(d.geaendert.slice(0, 10))} ${esc(d.geaendert.slice(11, 16))}${d.geaendert_von ? " von " + esc(d.geaendert_von) : ""}.` : ""}</p>
      ${d.beschaffung.length ? `<h3 style="margin:14px 0 6px">Zu beschaffen <span class="hinweis" style="font-weight:400">– im Zuschnittprogramm reserviert, aber nicht im Lager</span></h3>
        <table class="liste"><tr><th>Material</th><th class="r">Stärke</th><th class="r">Format</th><th>für</th><th class="r">reserviert</th><th class="r">im Lager</th><th class="r">bestellt</th><th class="r">zu bestellen</th><th></th></tr>
        ${d.beschaffung.map((x, i) => `<tr><td><b>${esc(x.material)}</b></td><td class="r">${mm(x.dicke)}</td><td class="r">${mm(x.laenge)} × ${mm(x.breite)}</td>
          <td>${x.auftraege.map(a => a.auftrag_id ? `<a href="#/auftrag/${a.auftrag_id}/werkstatt">${esc(a.nr || a.projekt)}</a> (${a.anzahl})` : `${esc(a.projekt)} (${a.anzahl})`).join(", ")}</td>
          <td class="r">${x.reserviert}</td><td class="r">${x.bestand}</td><td class="r">${x.bestellt || ""}${x.bestellt_am ? `<div class="hinweis">${datum(x.bestellt_am.slice(0, 10))}</div>` : ""}</td>
          <td class="r"><b class="${x.zu_bestellen ? "rot" : ""}">${x.zu_bestellen || "–"}</b></td>
          <td class="nw"><button class="btn" data-bs="${i}" data-n="${x.zu_bestellen + x.bestellt || 1}">bestellt …</button>${x.bestellt ? `<button class="btn" data-we="${i}" data-n="${x.bestellt}">eingetroffen …</button>` : ""}</td></tr>`).join("")}</table>
        <p class="hinweis">Die Liste entsteht im Zuschnittprogramm durch „reservieren“ im Projekt. Bei „eingetroffen“ werden die Platten als ganze Platten eingelagert.</p>` : ""}
      <h3 style="margin:14px 0 6px">Restplatten</h3>
      <div class="such" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px">
        <input id="rlQ" placeholder="Suchen: Nummer, Material, Maß, Lagerort …" value="${esc(restFilter.q)}" style="width:300px">
        <label style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="rlV" ${restFilter.verbraucht ? "checked" : ""}> auch verbrauchte</label>
        <span class="hinweis">${reste.filter(r => !r.used).length} Reste · ${n2(flaeche)} m²</span>
        <span style="margin-left:auto"></span><button class="btn" id="rlEt">🏷 Etiketten (${gewaehlt.size || "alle angezeigten"})</button>
      </div>
      <table class="liste"><tr><th style="width:30px"><input type="checkbox" id="rlAlle"></th><th>Nr.</th><th>Material</th><th class="r">Stärke</th><th class="r">Länge × Breite</th><th class="r">m²</th><th>Lagerort</th><th>Eingelagert</th><th>Herkunft</th><th></th></tr>
        ${reste.map(r => `<tr class="${r.no === markiert ? "markiert" : ""}" style="${r.used ? "opacity:.5" : ""}"><td><input type="checkbox" data-rw="${esc(r.id)}" ${gewaehlt.has(r.id) ? "checked" : ""}></td>
          <td><b>${esc(r.no)}</b></td><td>${esc(r.material)}</td><td class="r">${mm(r.thickness)}</td><td class="r"><b>${mm(r.length)} × ${mm(r.width)}</b></td>
          <td class="r">${n2(r.length * r.width / 1e6)}</td><td>${esc(r.location || "")}</td><td>${r.date ? datum(r.date.slice(0, 10)) : ""}</td>
          <td class="hinweis">${esc(r.from || "")}${r.used ? `<br>verbraucht ${datum(r.used.slice(0, 10))}${r.usedFor ? " · " + esc(r.usedFor) : ""}` : ""}${r.reservedFor ? `<br><b>vorgemerkt ${esc(r.reservedFor.nr || r.reservedFor.project || "")}</b>` : ""}</td>
          <td class="nw">${r.used ? `<button class="btn" data-ra="zurueck" data-id="${esc(r.id)}">zurück ins Lager</button>`
            : `<a class="btn" href="/liste/etiketten?typ=rest&ids=${encodeURIComponent(r.id)}" target="_blank" title="Etikett">🏷</a><button class="btn" data-ra="verbraucht" data-id="${esc(r.id)}">verbraucht</button>`}
            <button class="btn rot" data-ra="loeschen" data-id="${esc(r.id)}" title="Löschen">✕</button></td></tr>`).join("") || `<tr><td colspan="10" class="hinweis">Keine Reste${q ? " passend zur Suche" : ""}.</td></tr>`}
      </table>
      <div class="form" id="rlNeu" style="margin-top:10px;grid-template-columns:1fr">
        ${zeile("Rest einlagern", `<input name="material" list="rlMat" placeholder="Material" style="flex:2 1 180px"><input name="dicke" class="zahl" placeholder="Stärke mm" style="width:90px;flex:0 0 90px">
          <input name="laenge" class="zahl" placeholder="Länge (Faser)" style="width:110px;flex:0 0 110px"><input name="breite" class="zahl" placeholder="Breite" style="width:100px;flex:0 0 100px">
          <input name="lagerort" placeholder="Lagerort" style="width:120px;flex:0 0 120px"><button class="btn prim" id="rlAdd">Einlagern</button>`)}
      </div>
      <datalist id="rlMat">${[...new Set([...d.reste, ...d.platten].map(r => r.material).filter(Boolean))].map(m => `<option value="${esc(m)}">`).join("")}</datalist>
      <h3 style="margin:18px 0 6px">Ganze Platten</h3>
      ${d.platten.length ? `<table class="liste"><tr><th>Material</th><th class="r">Stärke</th><th class="r">Format</th><th>Lagerort</th><th class="r">Bestand</th></tr>
        ${d.platten.map(p => `<tr><td>${esc(p.material)}</td><td class="r">${mm(p.thickness)}</td><td class="r">${mm(p.length)} × ${mm(p.width)}</td><td>${esc(p.location || "")}</td>
          <td class="r"><input class="zahl" data-pq="${esc(p.id)}" value="${p.qty}" style="width:70px"> Stk.</td></tr>`).join("")}</table>` : `<p class="hinweis">Ganze Platten werden im Zuschnittprogramm (Lager) eingetragen und beim Zuschnitt automatisch abgebucht.</p>`}
      ${d.log.length ? `<h3 style="margin:18px 0 6px">Letzte Buchungen</h3><div class="hinweis" style="line-height:1.7">${d.log.slice(0, 12).map(l => `${new Date(l.t).toLocaleString("de-DE", {dateStyle: "short", timeStyle: "short"})} · ${esc(l.msg)}`).join("<br>")}</div>` : ""}`;
    let tq;
    $("#rlQ").oninput = e => { restFilter.q = e.target.value; clearTimeout(tq); tq = setTimeout(() => { zeichnen(); const f = $("#rlQ"); f.focus(); f.setSelectionRange(f.value.length, f.value.length); }, 300); };
    $("#rlV").onchange = e => { restFilter.verbraucht = e.target.checked; zeichnen(); };
    $("#rlAlle").onchange = e => { reste.forEach(r => e.target.checked ? gewaehlt.add(r.id) : gewaehlt.delete(r.id)); zeichnen(); };
    $$("[data-rw]", z).forEach(c => c.onchange = () => { c.checked ? gewaehlt.add(c.dataset.rw) : gewaehlt.delete(c.dataset.rw); $("#rlEt").textContent = `🏷 Etiketten (${gewaehlt.size || "alle angezeigten"})`; });
    $("#rlEt").onclick = () => etikettenDialog("rest", gewaehlt.size ? [...gewaehlt] : reste.filter(r => !r.used).map(r => r.id));
    $$("[data-ra]", z).forEach(b => b.onclick = async () => {
      const a = b.dataset.ra;
      if (a === "loeschen" && !await frage("Rest endgültig löschen? (Für verarbeitete Reste besser „verbraucht“.)")) return;
      try { await api("reste/" + encodeURIComponent(b.dataset.id), {method: "PUT", body: {aktion: a}}); await laden(); } catch (e) { toast(e.message, true); }
    });
    $$("[data-pq]", z).forEach(el => el.onchange = async () => {
      try { await api("reste/platte/" + encodeURIComponent(el.dataset.pq), {method: "PUT", body: {menge: zahlEin(el.value)}}); toast("Bestand gespeichert"); await laden(); } catch (e) { toast(e.message, true); }
    });
    const anzahl = async (titel, vorgabe) => { const r = await modal(titel, zeile("Anzahl Platten", `<input name="n" type="number" min="0" value="${vorgabe}" style="width:100px">`), "OK"); return r ? +r.n : null; };
    $$("[data-bs]", z).forEach(b => b.onclick = async () => {
      const x = d.beschaffung[+b.dataset.bs]; const n = await anzahl(`Bestellt: ${x.material} (0 = Bestellung löschen)`, b.dataset.n); if (n === null) return;
      try { d = await api("reste/bestellung", {method: "PUT", body: {key: x.key, menge: n}}); zeichnen(); toast(n ? `${n} Platten als bestellt vermerkt` : "Bestellung gelöscht"); } catch (e) { toast(e.message, true); }
    });
    $$("[data-we]", z).forEach(b => b.onclick = async () => {
      const x = d.beschaffung[+b.dataset.we]; const n = await anzahl(`Eingetroffen: ${x.material}`, b.dataset.n); if (!n) return;
      try { d = await api("reste/wareneingang", {method: "POST", body: {key: x.key, menge: n}}); zeichnen(); toast(`${n} Platten eingelagert`); } catch (e) { toast(e.message, true); }
    });
    $("#rlAdd").onclick = async () => {
      const f = {}; $$("#rlNeu [name]").forEach(el => f[el.name] = el.classList.contains("zahl") ? zahlEin(el.value) : el.value);
      try {
        const it = await api("reste", {method: "POST", body: f}); toast(`Rest ${it.no} eingelagert`);
        await laden();
        if (await frage(`Etikett für ${it.no} drucken?`, {ok: "Etikett"})) window.open(`/liste/etiketten?typ=rest&ids=${encodeURIComponent(it.id)}`, "_blank");
      } catch (e) { toast(e.message, true); }
    };
    $("#rlImp").onchange = async e => {
      const datei = e.target.files[0]; if (!datei) return;
      if (d.reste.length + d.platten.length && !await frage("Das Lager im Büro durch den Inhalt dieser Datei ersetzen?")) return;
      try { d = await api("reste/import", {method: "POST", body: {text: await datei.text()}}); toast(`Übernommen: ${d.reste.filter(r => !r.used).length} Reste, ${d.platten.length} Plattenformate`); zeichnen(); }
      catch (x) { toast(x.message, true); }
    };
    const mk = $("tr.markiert", z); if (mk) mk.scrollIntoView({block: "center"});
  };
  const laden = async () => { d = await api("reste"); zeichnen(); };
  await laden();
}


// ---------- Einkaufspreise von Lieferanten einlesen (Datanorm, CSV, Excel) ----------
const PREIS_IMPORT = {lieferant_id: "", rabatt: "", alle: false, datei: null, zuordnung: null, erg: null, schluessel: "", wahl: new Set(), suche: "", gruppe: "", kat: "beschlaege", rabatte: {}};
async function preisImport() {
  matKopf("preise");
  const lieferanten = (await api("lieferanten?status=aktiv")).filter(l => !["Mitarbeiter", "Finanzamt", "Krankenkasse"].includes(l.gruppe || ""));
  const P = PREIS_IMPORT, kann = darf("material", 2);
  const rabattZahl = () => parseFloat(String(P.rabatt || "").replace(",", ".")) || 0;
  const zeigen = () => {
    const r = P.erg;
    const pzt = v => v == null ? "–" : `${v > 0 ? "+" : ""}${zahlDE(v, 1)} %`;
    $("#inhalt").innerHTML = `<div class="titel"><h2>Einkaufspreise einlesen</h2></div>
      <p class="hinweis" style="margin-top:-6px">Preisdatei des Lieferanten (Datanorm 4 oder 5 – auch als ZIP und als reine Preisänderungsdatei –, CSV oder Excel) einlesen. Abgeglichen wird über die <b>Bestellnummer</b> im Materialstamm, sonst über die EAN.
        Übernommen werden nur die Preise, die unten angehakt sind – Verkaufspreise mit Aufschlag werden dabei nachgeführt.</p>
      <div class="form" style="grid-template-columns:1fr">
        ${zeile("Lieferant", `<select id="piL"><option value="">– alle Lieferanten –</option>${lieferanten.map(l => `<option value="${l.id}" ${String(l.id) === String(P.lieferant_id) ? "selected" : ""}>${esc(l.kurzname)}</option>`).join("")}</select>
          <label><input type="checkbox" id="piA" ${P.alle ? "checked" : ""}> auch Material anderer Lieferanten abgleichen</label>`)}
        ${zeile("Rabatt auf Listenpreise", `<input id="piR" value="${esc(P.rabatt)}" style="width:80px"> % <span class="hinweis">nur für Bruttopreise (Datanorm-Preiskennzeichen 1); Tabellen gelten als Nettopreise</span>`)}
        ${zeile("Datei", `<label class="btn prim">📄 Preisdatei wählen<input type="file" id="piD" hidden></label> <span class="hinweis">${P.datei ? esc(P.datei.name) : ""}</span>${P.datei ? ` <button class="btn" id="piZu" title="Preisdatei schließen; im Materialstamm bleibt alles, wie es ist">✕ Datei schließen</button>` : ""}`)}
      </div>
      <div id="piErg">${!r ? "" : `
        <div class="kachel" style="margin:12px 0">${esc(r.format)}: <b>${r.artikel}</b> Artikel in der Datei · <b>${r.treffer.length}</b> Treffer im Materialstamm (von ${r.materialien} geprüften) ·
          davon ${r.treffer.filter(t => !t.gleich).length} mit neuem Preis${r.hinweis ? `<div class="hinweis" style="color:var(--rot)">${esc(r.hinweis)}</div>` : ""}</div>
        ${r.brutto ? `<div class="kachel" style="margin:0 0 12px;border-left:4px solid var(--akzent)"><b>${r.brutto} Artikel haben Listenpreise (brutto), keinen Einkaufspreis.</b>
          Der Einkaufspreis ergibt sich erst mit dem Rabatt${r.rabattgruppen.length ? " der jeweiligen Rabattgruppe" : ""}. ${!r.rabattgruppen.length && !rabattZahl() ? `<span style="color:var(--rot)">Oben ist kein Rabatt eingetragen – ohne Rabatt würde der Listenpreis als Einkaufspreis übernommen.</span>` : ""}
          ${r.rabattgruppen.length ? `<table class="liste" style="margin-top:8px;max-width:560px"><tr><th>Rabattgruppe</th><th class="r">Artikel</th><th class="r" style="width:120px">Rabatt %</th><th>Herkunft</th></tr>
            ${r.rabattgruppen.map(g => `<tr><td><b>${esc(g.gruppe)}</b></td><td class="r">${g.anzahl}</td>
              <td class="r"><input data-rg="${esc(g.gruppe)}" value="${g.rabatt == null ? "" : zahlDE(g.rabatt, g.rabatt % 1 ? 2 : 0)}" placeholder="${esc(String(P.rabatt || "0"))}" style="width:80px;text-align:right"></td>
              <td class="hinweis">${g.rabatt == null ? (rabattZahl() ? "allgemeiner Rabatt von oben" : `<span style="color:var(--rot)">kein Rabatt</span>`) : esc(g.quelle)}</td></tr>`).join("")}</table>
            <div class="hinweis" style="margin-top:6px">Leeres Feld = allgemeiner Rabatt von oben. ${P.lieferant_id ? "Eingetragene Rabatte werden bei diesem Lieferanten gespeichert und beim nächsten Einlesen wieder verwendet." : "Mit gewähltem Lieferanten werden die Rabatte bei ihm gespeichert."}</div>` : ""}</div>` : ""}
        ${r.kopf && r.kopf.length ? `<details ${r.treffer.length ? "" : "open"} style="margin-bottom:10px"><summary>Spalten der Tabelle zuordnen</summary><div class="form" style="grid-template-columns:1fr;margin-top:6px">
          ${[["artnr", "Artikel-/Bestellnummer"], ["ean", "EAN"], ["text", "Bezeichnung"], ["preis", "Preis (netto)"], ["einheit", "Einheit"], ["pe", "Preiseinheit (je …)"]].map(([k, t]) =>
            zeile(t, `<select data-pz="${k}"><option value="-1">–</option>${r.kopf.map((h, i) => `<option value="${i}" ${r.zuordnung[k] === i ? "selected" : ""}>${esc(h || "Spalte " + (i + 1))}</option>`).join("")}</select>`)).join("")}
          </div><button class="btn" id="piNeu">Neu abgleichen</button></details>` : ""}
        ${r.treffer.length ? `<table class="liste"><tr><th><input type="checkbox" id="piAlle"></th><th>Material</th><th>Bestellnr.</th><th class="r">bisher</th><th class="r">neu</th><th class="r">Änderung</th><th>Einheit</th><th>Hinweis</th></tr>
          ${r.treffer.map((t, i) => `<tr class="${t.gleich ? "hinweis" : ""}"><td>${t.gleich ? "" : `<input type="checkbox" data-pi="${i}" ${t.vorschlag ? "checked" : ""}>`}</td>
            <td><a href="#/mat/${t.material_id}">${esc(t.nummer)}</a> ${esc(t.bezeichnung)}${t.text_datei ? `<div class="hinweis">${esc(t.text_datei)}</div>` : ""}</td>
            <td class="nw">${esc(t.bestellnr || "")} <span class="hinweis">${t.ueber === "EAN" ? "(EAN)" : ""}</span></td>
            <td class="r nw">${eur(t.alt)}<div class="hinweis">${datum(t.preis_vom)}</div></td><td class="r nw"><b>${eur(t.neu)}</b></td>
            <td class="r nw" style="color:${t.diff > 0 ? "var(--rot)" : t.diff < 0 ? "var(--gruen)" : "inherit"}">${t.gleich ? "gleich" : pzt(t.diff)}</td>
            <td class="nw">${esc(t.einheit)}${t.einheit_ok ? "" : ` <span style="color:var(--rot)">≠ ${esc(t.einheit_datei)}</span>`}</td>
            <td class="hinweis">${[t.waehrung ? `<span style="color:var(--rot)">Preis in ${esc(t.waehrung)} – nicht umgerechnet</span>` : "", t.pe_hinweis, t.brutto ? `Listenpreis${t.rabattgruppe ? " " + esc(t.rabattgruppe) : ""} abzgl. Rabatt` : "", !t.gleich && !t.vorschlag ? (t.einheit_ok ? "große Änderung – bitte prüfen" : "Einheit weicht ab – Preis bezieht sich evtl. auf eine andere Menge") : ""].filter(Boolean).join(" · ")}</td></tr>`).join("")}</table>
          ${kann ? `<button class="btn prim" id="piOk" style="margin-top:10px">Angehakte Preise übernehmen</button>` : ""}` : `<div class="leer">Keine Treffer im Materialstamm. Neue Artikel lassen sich unten aus der Datei anlegen.</div>`}
        <div id="piNeuBox"></div>`}
      </div>`;
    $("#piL").onchange = e => { P.lieferant_id = e.target.value; P.rabatte = {}; if (P.datei) lesen(); };
    $$("[data-rg]").forEach(el => el.onchange = async () => {
      const gr = el.dataset.rg, v = el.value.trim();
      const rn = zahlLesen(v);
      if (v && (!rn || rn.wert < 0 || rn.wert >= 100)) { toast("Ein Rabatt liegt zwischen 0 und 100 %.", true); return; }
      try {
        if (P.lieferant_id && kann) { await api("preisimport/rabatte", {method: "POST", body: {lieferant_id: P.lieferant_id, rabatte: {[gr]: v === "" ? null : zahlEin(v)}}}); delete P.rabatte[gr]; }
        else if (v === "") delete P.rabatte[gr]; else P.rabatte[gr] = zahlEin(v);
      } catch (x) { toast(x.message, true); }
      lesen();
    });
    $("#piA").onchange = e => { P.alle = e.target.checked; if (P.datei) lesen(); };
    $("#piR").onchange = e => { P.rabatt = e.target.value; if (P.datei) lesen(); };
    $("#piD").onchange = e => { P.datei = e.target.files[0]; P.zuordnung = null; P.schluessel = ""; P.wahl = new Set(); P.suche = P.gruppe = ""; P.einheiten = {}; lesen(); };
    if ($("#piZu")) $("#piZu").onclick = () => { Object.assign(P, {datei: null, erg: null, schluessel: "", zuordnung: null, wahl: new Set(), suche: "", gruppe: "", rabatte: {}}); zeigen(); };
    if ($("#piNeu")) $("#piNeu").onclick = () => { P.zuordnung = Object.fromEntries($$("[data-pz]").map(s => [s.dataset.pz, +s.value])); P.schluessel = ""; lesen(); };
    if (r && $("#piNeuBox")) neueZeigen(r);
    if ($("#piAlle")) $("#piAlle").onchange = e => $$("[data-pi]").forEach(c => { c.checked = e.target.checked; });
    if ($("#piOk")) $("#piOk").onclick = async () => {
      const posten = $$("[data-pi]:checked").map(c => r.treffer[+c.dataset.pi]);
      if (!posten.length) return toast("Nichts angehakt.", true);
      if (!await frage(`${posten.length} Einkaufspreise übernehmen?`, {ok: "Übernehmen"})) return;
      const x = await api("preisimport/uebernehmen", {method: "POST", body: {lieferant_id: P.lieferant_id, dateiname: P.datei ? P.datei.name : "", posten}});
      toast(`${x.geaendert} Preise übernommen`); lesen();
    };
  };
  const lesen = async () => {
    if (!P.datei) return zeigen();
    try {
      const basis = {dateiname: P.datei.name, lieferant_id: P.lieferant_id, rabatt: P.rabatt, alle: P.alle, zuordnung: P.zuordnung, rabatte: P.rabatte};
      try { if (!P.schluessel) throw new Error(); P.erg = await api("preisimport/lesen", {method: "POST", body: {...basis, schluessel: P.schluessel}}); }
      catch (x) { P.erg = await api("preisimport/lesen", {method: "POST", body: {...basis, daten: await dateiAlsBase64(P.datei)}}); }
      P.schluessel = P.erg.schluessel;
    } catch (x) { P.erg = null; toast(x.message, true); }
    zeigen();
  };
  // neue Artikel aus der Datei: suchen, anhaken, anlegen
  const neueZeigen = r => {
    const box = $("#piNeuBox");
    if (!box) return;
    const liste = r.neu || [];
    const schl = a => a.artnr || a.ean || "";
    box.innerHTML = `<h3 style="margin-top:22px">Neue Artikel aus der Datei <span class="hinweis" style="font-weight:400">· ${r.neu_gesamt} noch nicht im Materialstamm</span></h3>
      ${!r.neu_gesamt ? `<div class="leer">Alle Artikel der Datei sind schon angelegt.</div>` : `
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
        <input id="piSu" placeholder="Bezeichnung, Artikelnummer oder EAN …" value="${esc(P.suche)}" style="flex:1 1 240px;max-width:380px">
        ${r.gruppen.length ? `<select id="piGr"><option value="">alle Warengruppen</option>${r.gruppen.map(([g, n]) => `<option value="${esc(g)}" ${g === P.gruppe ? "selected" : ""}>${esc(g)} (${n})</option>`).join("")}</select>` : ""}
      </div>
      ${liste.length ? `<table class="liste"><tr><th></th><th>Artikelnr.</th><th>Bezeichnung</th><th>Warengruppe</th><th>Einheit</th><th class="r">EK ${r.brutto ? "(nach Rabatt)" : ""}</th></tr>
        ${liste.map((a, i) => { const rg = (r.rabattgruppen || []).find(g => g.gruppe === (a.rabattgruppe || "")), pz = rg && rg.rabatt != null ? rg.rabatt : rabattZahl();
          const ek = a.netto === false ? a.preis * (1 - pz / 100) : a.preis;
          return `<tr><td><input type="checkbox" data-pn="${i}" ${P.wahl.has(schl(a)) ? "checked" : ""}></td><td class="nw">${esc(a.artnr || "")}${a.ean ? `<div class="hinweis">${esc(a.ean)}</div>` : ""}</td>
          <td>${esc(a.text)}</td><td class="hinweis">${esc(a.warengruppe || "")}</td>
          <td class="nw">${esc(a.einheit || "")}${a.einheit_unbekannt ? ` <span style="color:var(--rot)" title="Diese Einheit kennt das Programm nicht. Beim Anlegen wird gefragt, als welche Einheit der Artikel geführt wird.">${a.einheit ? "?" : "fehlt"}</span>` : ""}</td>
          <td class="r nw">${eur(ek)}${a.waehrung ? `<div class="hinweis" style="color:var(--rot)">Preis in ${esc(a.waehrung)}</div>` : ""}</td></tr>`; }).join("")}</table>
        ${r.neu_treffer > liste.length ? `<p class="hinweis">${r.neu_treffer} passende Artikel, die ersten ${liste.length} werden gezeigt – Suche eingrenzen.</p>` : ""}`
        : `<div class="leer">Keine passenden Artikel.</div>`}
      ${kann ? `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px">
        <span><b id="piAnz">${P.wahl.size}</b> angehakt · anlegen als</span>
        <select id="piKat">${Object.entries(MAT_KATEGORIEN_NAMEN).map(([k, t]) => `<option value="${k}" ${k === P.kat ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>
        <button class="btn prim" id="piAnl">Angehakte anlegen</button>${P.wahl.size ? `<button class="btn" id="piWeg">Auswahl leeren</button>` : ""}</div>
        <p class="hinweis">Angelegt wird mit Bezeichnung, Bestellnummer, EAN, Einheit, Einkaufspreis${P.lieferant_id ? ", Lieferant" : ""} und Warengruppe; die Materialnummer vergibt das Programm.
        ${P.lieferant_id ? "" : "<b>Tipp:</b> oben den Lieferanten wählen, damit er beim Material eingetragen wird."}</p>` : ""}`}`;
    let t;
    const suchen = async () => {
      try { Object.assign(P.erg, await api("preisimport/neue", {method: "POST", body: {schluessel: P.schluessel, suche: P.suche, gruppe: P.gruppe}})); }
      catch (x) { toast(x.message, true); if (x.status === 410) { P.schluessel = ""; return lesen(); } }
      neueZeigen(P.erg);
      const su = $("#piSu"); if (su && document.activeElement !== su && P.suche) { su.focus(); su.setSelectionRange(su.value.length, su.value.length); }
    };
    if ($("#piSu")) $("#piSu").oninput = e => { clearTimeout(t); t = setTimeout(() => { P.suche = e.target.value.trim(); suchen(); }, 350); };
    if ($("#piGr")) $("#piGr").onchange = e => { P.gruppe = e.target.value; suchen(); };
    $$("[data-pn]", box).forEach(c => c.onchange = () => { const k = schl(liste[+c.dataset.pn]); c.checked ? P.wahl.add(k) : P.wahl.delete(k); $("#piAnz").textContent = P.wahl.size; });
    if ($("#piKat")) $("#piKat").onchange = e => { P.kat = e.target.value; };
    if ($("#piWeg")) $("#piWeg").onclick = () => { P.wahl = new Set(); neueZeigen(r); };
    if ($("#piAnl")) $("#piAnl").onclick = async () => {
      if (!P.wahl.size) return toast("Bitte Artikel anhaken.", true);
      if (!await frage(`${P.wahl.size} Artikel als „${MAT_KATEGORIEN_NAMEN[P.kat]}“ anlegen?`, {ok: "Anlegen"})) return;
      try {
        const anfrage = einheiten => api("preisimport/anlegen", {method: "POST", body: {schluessel: P.schluessel, auswahl: [...P.wahl], kategorie: P.kat,
          lieferant_id: P.lieferant_id, rabatt: P.rabatt, rabatte: P.rabatte, dateiname: P.datei ? P.datei.name : "", einheiten}});
        let x = await anfrage(P.einheiten || {});
        if (x.einheiten_fehlen) {
          // Einheiten, die das Programm nicht kennt: nachfragen statt eine Einheit zu unterstellen
          const zu = await modal("Einheiten zuordnen", `<p class="hinweis" style="margin-top:0">Diese Einheiten der Preisdatei kennt das Programm nicht. Der Preis der Datei gilt je dieser Einheit.
            Wird zum Beispiel eine Tafel, ein Blatt oder ein Kanister als „Stk.“ oder „Packung“ geführt, lässt sich im Material anschließend die <b>Umrechnung</b> eintragen (1 Einheit = … m², lfm oder m³), damit die Kalkulation richtig rechnet.</p>
            <div class="form" style="grid-template-columns:1fr">${x.einheiten_fehlen.map((u, i) => zeile(u.einheit ? `„${u.einheit}“` : "ohne Einheit",
              `<select name="e${i}"><option value="">– bitte wählen –</option>${x.einheiten.map(e => `<option>${esc(e)}</option>`).join("")}</select>
               <span class="hinweis">${u.anzahl} Artikel, z. B. ${esc(u.beispiel)}</span>`)).join("")}</div>`, "Anlegen");
          if (!zu) return;
          const wahl = {...(P.einheiten || {})};
          x.einheiten_fehlen.forEach((u, i) => { if (zu["e" + i]) wahl[u.einheit] = zu["e" + i]; });
          if (x.einheiten_fehlen.some(u => !wahl[u.einheit])) return toast("Bitte für jede Einheit eine Zuordnung wählen.", true);
          P.einheiten = wahl;
          x = await anfrage(wahl);
          if (x.einheiten_fehlen) return toast("Die Einheiten konnten nicht zugeordnet werden.", true);
        }
        toast(`${x.angelegt} Materialien angelegt${x.uebersprungen ? `, ${x.uebersprungen} gab es schon` : ""}`);
        P.wahl = new Set(); lesen();
      } catch (x) { toast(x.message, true); if (x.status === 410) { P.schluessel = ""; lesen(); } }
    };
  };
  zeigen();
}
