// =====================================================================
//  Variable Positionsvorlagen: Maße abfragen → Stückliste, Beschläge, Tätigkeiten
// =====================================================================
const VL_ROLLEN = {platte: "Platte / Massivholz", kante: "Kante", furnier: "Furnier", oberflaeche: "Oberfläche", beschlag: "Beschlag"};
const VL_KATS = {platte: ["holzwerkstoffe", "massivholz", "artikel"], kante: ["holzwerkstoffe"], furnier: ["holzwerkstoffe"], oberflaeche: ["beschichtung", "chemie"], beschlag: ["beschlaege", "artikel", "chemie"]};
// Maße ohne Tausenderpunkt (2400 statt 2.400), Komma als Dezimalzeichen
// Auswahl-Parameter: „0=ohne; 1=Passleiste“ → [[0, "ohne"], [1, "Passleiste"]]
const vlOptionen = p => String(p.optionen || "").split(/[;\n]/).map(t => t.split("=")).filter(x => x.length > 1 && x[0].trim() !== "").map(([w, ...t]) => [+w.trim().replace(",", "."), t.join("=").trim()]);
const vlZahl = v => { const n = +v; return v !== "" && v != null && Number.isFinite(n) ? String(Math.round(n * 10) / 10).replace(".", ",") : String(v ?? ""); };

// ---------- Position aus Vorlage anlegen bzw. Maße ändern ----------
// a: Auftrag (zum Anlegen), pid: vorhandene Position (Maße ändern), vorlageId/werte: Vorbelegung
async function vorlageDialog({a = null, titel = 0, pid = null, vorlageId = null, werte = null, nachher = null} = {}) {
  let liste;
  try { liste = (await api("positionsvorlagen")).vorlagen; } catch (e) { return toast(e.message, true); }
  if (!liste.length) {
    if (await frage("Noch keine Positionsvorlagen angelegt.\n\nJetzt in den Einstellungen anlegen?")) location.hash = "#/einstellungen/kalkulation/vorlagen";
    return;
  }
  let v = liste.find(x => x.id === vorlageId) || liste[0];
  let ein = {}, namen = {}, erg = null, timer;
  const vorbelegen = () => {
    ein = {}; namen = {};
    for (const p of v.parameter || []) ein[p.k] = p.typ === "material" ? (p.material_id || null) : p.wert;
    if (werte && v.id === vorlageId) Object.assign(ein, werte);
  };
  vorbelegen();
  const hg = document.createElement("div");
  hg.className = "modal-hg";
  hg.innerHTML = `<div class="modal" style="width:min(1050px,96vw);max-height:94vh;overflow:auto"><h3>${pid ? "Maße ändern" : "Position aus Vorlage"}</h3><div id="vlInhalt"></div>
    <div class="knoepfe"><button class="btn" id="vlAbbr">Abbrechen</button><button class="btn prim" id="vlOk">${pid ? "Stückliste neu berechnen" : "Position anlegen"}</button></div></div>`;
  document.body.appendChild(hg);
  const zu = () => { hg.remove(); window.removeEventListener("hashchange", zu); document.removeEventListener("keydown", esc_); };
  const esc_ = e => { if (e.key === "Escape" && document.body.lastElementChild === hg) zu(); };
  window.addEventListener("hashchange", zu); document.addEventListener("keydown", esc_);
  $("#vlAbbr", hg).onclick = zu;
  const rechnen = async () => {
    try { erg = await api("positionsvorlagen/berechnen", {method: "POST", body: {id: v.id, werte: ein}}); namen = {...namen, ...(erg.material_namen || {})}; }
    catch (e) { erg = {fehler: [e.message], teile: [], beschlaege: [], hilfswerte: []}; }
    vorschau();
  };
  const spaeter = () => { clearTimeout(timer); timer = setTimeout(rechnen, 350); };
  const pname = k => ((v.parameter || []).find(p => p.k === k) || {}).name || k;
  const vorschau = () => {
    $$("[data-vm]", hg).forEach(b => { if (ein[b.dataset.vm] && namen[b.dataset.vm]) b.textContent = namen[b.dataset.vm]; });
    const ziel = $("#vlVorschau", hg); if (!ziel || !erg) return;
    const kn = t => Object.values(t.kanten || {}).length ? `<span class="tag">K ${Object.keys(t.kanten).map(s => s[0].toUpperCase()).join("")}</span>` : "";
    ziel.innerHTML = `${erg.fehler.length ? `<div class="kachel" style="border-left:4px solid var(--rot);margin-bottom:8px">${erg.fehler.map(esc).join("<br>")}</div>` : ""}
      ${(erg.hinweise || []).length ? `<div class="kachel" style="border-left:4px solid var(--akzent);margin-bottom:8px">${erg.hinweise.map(esc).join("<br>")}</div>` : ""}
      ${erg.hilfswerte.length ? `<div class="hinweis" style="margin-bottom:6px">${erg.hilfswerte.filter(h => !h.verdeckt).map(h => `${esc(h.name)} <b>${vlZahl(h.wert)}</b>`).join(" · ")}</div>` : ""}
      <table class="liste"><tr><th>Teil</th><th>Werkstoff</th><th class="r">Stück</th><th class="r">Länge</th><th class="r">Breite</th><th>Bearbeitung</th></tr>
        ${erg.teile.map(t => `<tr><td>${esc(t.verwendung)}</td><td>${t.werkstoff_param ? (namen[t.werkstoff_param] ? esc(namen[t.werkstoff_param]) : `<span style="color:var(--akzent)">${esc(pname(t.werkstoff_param))}: noch wählen</span>`) : "–"}</td>
          <td class="r">${vlZahl(t.stueck)}</td><td class="r">${vlZahl(t.laenge)}</td><td class="r">${vlZahl(t.breite)}</td>
          <td>${kn(t)}${t.gehrung ? `<span class="tag">G ${vlZahl(t.gehrung)}×</span>` : ""}${t.bohren ? `<span class="tag">B ${vlZahl(t.bohren)}×</span>` : ""}${t.verbinden ? `<span class="tag">V ${vlZahl(t.verbinden)}×</span>` : ""}${t.bemerkung ? ` <span class="hinweis">${esc(t.bemerkung)}</span>` : ""}</td></tr>`).join("")}
        ${erg.beschlaege.map(b => `<tr><td colspan="2">${namen[b.material_param] ? esc(namen[b.material_param]) : `<span style="color:var(--akzent)">${esc(pname(b.material_param))}: noch wählen</span>`}</td><td class="r">${vlZahl(b.menge)}</td><td colspan="3" class="hinweis">Beschlag${b.bemerkung ? " · " + esc(b.bemerkung) : ""}</td></tr>`).join("")}
      </table>
      ${erg.text ? `<div class="hinweis" style="margin-top:6px;white-space:pre-line">${esc(erg.text)}</div>` : ""}`;
  };
  const zeichnen = () => {
    const zahlen = (v.parameter || []).filter(p => (p.typ || "zahl") !== "material");
    const mats = (v.parameter || []).filter(p => p.typ === "material");
    $("#vlInhalt", hg).innerHTML = `
      ${pid ? `<p class="hinweis" style="margin-top:0">Vorlage <b>${esc(v.name)}</b>. Stückliste und Beschläge der Position werden neu berechnet und ersetzt; Tätigkeiten und eigene Änderungen am Text bleiben.</p>`
        : `<div class="zeile"><label>Vorlage</label><div><select id="vlWahl">${liste.map(x => `<option value="${esc(x.id)}" ${x.id === v.id ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></div></div>`}
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px 12px;margin:8px 0">
        ${zahlen.map(p => `<label style="display:flex;flex-direction:column;gap:3px;font-size:13px"><span>${esc(p.name || p.k)} <span class="hinweis">${esc(p.k)}${p.einheit && p.typ !== "auswahl" ? ", " + esc(p.einheit) : ""}</span></span>
          ${p.typ === "auswahl" ? `<select data-vs="${esc(p.k)}">${vlOptionen(p).map(([w, t]) => `<option value="${w}" ${+ein[p.k] === w ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>`
            : `<input class="zahl" data-vp="${esc(p.k)}" value="${esc(vlZahl(ein[p.k]))}">`}</label>`).join("")}</div>
      ${mats.length ? `<div class="sektion" style="font-size:13px">Material</div><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:6px 12px;margin-bottom:8px">
        ${mats.map(p => `<div style="display:flex;gap:6px;align-items:center"><span style="flex:0 0 120px;font-size:13px">${esc(p.name || p.k)}</span>
          <button class="btn" data-vm="${esc(p.k)}" style="flex:1;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${ein[p.k] ? esc(namen[p.k] || "gewählt") : "wählen …"}</button>
          ${ein[p.k] ? `<button class="ib" data-vmx="${esc(p.k)}" title="ohne Material">✕</button>` : ""}</div>`).join("")}</div>` : ""}
      <div class="sektion" style="font-size:13px">Ergebnis</div><div id="vlVorschau"><span class="hinweis">rechnet …</span></div>`;
    const w = $("#vlWahl", hg);
    if (w) w.onchange = () => { v = liste.find(x => x.id === w.value); vorbelegen(); zeichnen(); rechnen(); };
    $$("[data-vs]", hg).forEach(el => el.onchange = () => { ein[el.dataset.vs] = +el.value; rechnen(); });
    $$("[data-vp]", hg).forEach(el => el.oninput = () => { const n = /^[\d.,\s-]+$/.test(el.value) ? zahlLesen(el.value) : null; ein[el.dataset.vp] = el.value.trim() === "" ? "" : (n ? n.wert : el.value); spaeter(); });
    $$("[data-vm]", hg).forEach(b => b.onclick = async () => {
      const p = v.parameter.find(x => x.k === b.dataset.vm);
      const m = await materialWaehlen(VL_KATS[p.rolle || "platte"], `${p.name || p.k} wählen`);
      if (!m) return;
      ein[p.k] = m.id; namen[p.k] = `${m.nummer} ${(m.bezeichnung || "").split("\n")[0]}`; zeichnen(); rechnen();
    });
    $$("[data-vmx]", hg).forEach(b => b.onclick = () => { ein[b.dataset.vmx] = null; delete namen[b.dataset.vmx]; zeichnen(); rechnen(); });
    vorschau();
  };
  $("#vlOk", hg).onclick = async () => {
    if (erg && erg.fehler.length) return toast("Bitte erst die Fehler in den Eingaben beheben.", true);
    if (erg && (erg.hinweise || []).length && !await frage(`Trotz Hinweis fortfahren?\n\n${erg.hinweise.join("\n")}`, {ok: "Trotzdem anlegen"})) return;
    const btn = $("#vlOk", hg); btn.disabled = true;
    try {
      let ziel = pid;
      if (!ziel) ziel = await neuePosition(a, {titel, oeffnen: false});
      const r = await api(`positionen/${ziel}/vorlage`, {method: "POST", body: {id: v.id, werte: ein, neu: !pid}});
      zu();
      const ohne = (r.vorlage.ohne_material || []).map(pname);
      toast(`${r.vorlage.teile} Teile und ${r.vorlage.beschlaege} Beschläge berechnet` + (ohne.length ? ` · ohne Material: ${ohne.join(", ")}` : ""), !!ohne.length);
      if (nachher) nachher(r); else location.hash = `#/position/${ziel}/werkstoffe`;
    } catch (e) { toast(e.message, true); btn.disabled = false; }
  };
  zeichnen(); rechnen();
}

async function alsVorlageSpeichern(pid, text) {
  const d = await modal("Als Positionsvorlage speichern", `
    <div class="zeile"><label>Name</label><div><input name="name" value="${esc(klartext(text || "").split("\n")[0].slice(0, 60))}"></div></div>
    <p class="hinweis">Stückliste, Beschläge und Tätigkeiten dieser Position werden zur Vorlage. Die Werkstoffe werden zu Material-Parametern, Höhe, Breite und Tiefe zu Maß-Parametern. Danach werden in den Einstellungen die festen Maße durch Formeln ersetzt (z. B. Länge „H − 2*D“).</p>`, "Speichern");
  if (!d) return;
  try { const v = await api(`positionen/${pid}/als-vorlage`, {method: "POST", body: {name: d.name}}); toast(`Vorlage „${v.name}“ gespeichert`); location.hash = `#/einstellungen/kalkulation/vorlagen/${v.id}`; }
  catch (e) { toast(e.message, true); }
}

// ---------- Einstellungen › Kalkulation › Positionsvorlagen ----------
async function positionsvorlagenVorgabe(z, gewaehlt) {
  const [q, kv] = await Promise.all([api("positionsvorlagen"), api("kalkvorgaben")]);
  const V = q.vorlagen;
  const bezug = kv.bezug || {}, K = kv.katalog || [];
  let akt = V.find(v => v.id === gewaehlt) || V[0] || null, offen = null, erg = null, matNamen = {}, timer;
  const sp = speicherer("positionsvorlagen", r => { /* IDs bleiben stabil */ });
  const speichern = (sofort) => { sp.setze("vorlagen", V, sofort); clearTimeout(timer); timer = setTimeout(probe, 400); };
  const probe = async () => {
    if (!akt) return;
    try { erg = await api("positionsvorlagen/berechnen", {method: "POST", body: {vorlage: akt}}); matNamen = erg.material_namen || {}; }
    catch (e) { erg = {fehler: [e.message], teile: [], beschlaege: [], hilfswerte: [], werte: {}}; }
    probeZeigen();
  };
  const probeZeigen = () => {
    $$("[data-pmat]").forEach(b => { const p = akt && akt.parameter[+b.dataset.pmat]; if (p && p.material_id && matNamen[p.k]) b.textContent = matNamen[p.k]; });
    const el = $("#vgProbe"); if (!el || !erg) return;
    el.innerHTML = `${erg.fehler.length ? `<div style="color:var(--rot)">${erg.fehler.map(esc).join("<br>")}</div>` : `<span style="color:var(--gruen)">✓ rechnet ohne Fehler</span>`}${(erg.hinweise || []).length ? `<div style="color:var(--akzent)">Hinweise mit den Vorgaben: ${erg.hinweise.map(esc).join(" · ")}</div>` : ""}
      · ${erg.teile.length} Teile, ${erg.beschlaege.length} Beschläge mit den Vorgabewerten`;
    $$("[data-hw-wert]").forEach(s => { const h = erg.hilfswerte.find(x => x.k === s.dataset.hwWert); s.textContent = h ? "= " + vlZahl(h.wert) : ""; });
    $$("[data-t-erg]").forEach(s => {
      const t = akt.teile[+s.dataset.tErg]; const r = erg.teile.find(x => x.verwendung === t.verwendung && x.werkstoff_param === (t.werkstoff || ""));
      s.textContent = r ? `${vlZahl(r.stueck)} × ${vlZahl(r.laenge)} × ${vlZahl(r.breite)}` : "entfällt";
    });
  };
  const matParams = rollen => (akt.parameter || []).filter(p => p.typ === "material" && (!rollen || rollen.includes(p.rolle || "platte")));
  const pSel = (attr, wert, rollen) => `<select ${attr}><option value="">–</option>${matParams(rollen).map(p => `<option value="${esc(p.k)}" ${p.k === wert ? "selected" : ""}>${esc(p.name || p.k)}</option>`).join("")}</select>`;
  const inp = (attr, wert, breite = 90, ph = "") => `<input ${attr} value="${esc(wert ?? "")}" style="width:${breite}px" placeholder="${esc(ph)}">`;
  const zeichnen = () => {
    z.innerHTML = `<div class="titel"><h2>Positionsvorlagen</h2><span class="speicher"></span>
        <div class="rechts"><select id="vgWahl" style="min-width:220px">${V.map(v => `<option value="${esc(v.id)}" ${akt && v.id === akt.id ? "selected" : ""}>${esc(v.name || "(ohne Name)")}</option>`).join("")}</select>
          <button class="btn" id="vgNeu">+ Neu</button><button class="btn" id="vgBsp" title="Beispiel nach dem System-32-Konfigurator: Nische aufteilen mit Passleisten/Blenden">+ Beispiel Nische</button><button class="btn" id="vgBspK" title="Beispiel nach dem System-32-Konfigurator: Korpusmaß">+ Beispiel Korpus</button>
          ${akt ? `<button class="btn" id="vgKopie">Kopieren</button><button class="btn rot" id="vgDel">Löschen</button>` : ""}</div></div>
      <p class="hinweis" style="margin-top:0">Eine Vorlage fragt beim Anlegen einer Position Maße und Material ab und erzeugt daraus Stückliste, Beschläge und Tätigkeiten. In allen Zahlenfeldern stehen Formeln mit den Kürzeln der Parameter und Hilfswerte, z. B. <code>H - S</code>, <code>2*A</code>, <code>KB - 2*D</code>.
        Funktionen: <code>s32(h; d)</code> Korpushöhe nach System 32 (X + 2B im 32-mm-Raster, auch <code>s32ab</code>, <code>s32auf</code>), <code>ab(x)</code>, <code>auf(x)</code>, <code>runden(x; n)</code>, <code>min</code>, <code>max</code>, <code>wenn(Bedingung; dann; sonst)</code>. Eine Bedingung (z. B. <code>FB</code> oder <code>S &gt; 0</code>) lässt ein Teil weg, wenn sie 0 ergibt. Tipp: eine fertig kalkulierte Position mit „Als Vorlage speichern“ übernehmen und dann die Maße durch Formeln ersetzen.</p>
      ${akt ? editor() : `<div class="leer">Noch keine Vorlage. „+ Neu“ oder „+ Beispiel System 32“.</div>`}`;
    binden();
    probeZeigen();
  };
  const editor = () => {
    const v = akt;
    v.parameter = v.parameter || []; v.hilfswerte = v.hilfswerte || []; v.teile = v.teile || []; v.beschlaege = v.beschlaege || []; v.zeiten = v.zeiten || []; v.masse = v.masse || {art: "HBT"};
    return `<div class="form">
        ${zeile("Name", inp('data-v="name"', v.name, 360))}${zeile("Einheit", inp('data-v="einheit"', v.einheit || "Stk.", 90))}
        ${zeile("Positionstext", `<div class="spalte"><textarea data-v="text" rows="3">${esc(v.text || "")}</textarea><span class="hinweis">Werte in geschweiften Klammern werden eingesetzt, z. B. {N}, {KH}.</span></div>`, true)}
        ${zeile("Maße der Position", `<span style="padding-top:5px">H</span>${inp('data-vm="h"', v.masse.h, 110)}<span style="padding-top:5px">B</span>${inp('data-vm="b"', v.masse.b, 110)}<span style="padding-top:5px">T</span>${inp('data-vm="t"', v.masse.t, 110)}`, true)}
      </div>
      <div class="sektion">Parameter <span class="hinweis" style="font-weight:400">· werden beim Anlegen abgefragt</span></div>
      <table class="liste"><tr><th>Kürzel</th><th>Bezeichnung</th><th>Art</th><th>Vorgabe</th><th>Einheit bzw. Möglichkeiten</th><th></th></tr>
        ${v.parameter.map((p, i) => `<tr><td>${inp(`data-p="${i}" data-k="k"`, p.k, 90)}</td><td>${inp(`data-p="${i}" data-k="name"`, p.name, 230)}</td>
          <td><select data-p="${i}" data-k="typ"><option value="zahl" ${(p.typ || "zahl") === "zahl" ? "selected" : ""}>Zahl</option><option value="auswahl" ${p.typ === "auswahl" ? "selected" : ""}>Auswahl</option>${Object.entries(VL_ROLLEN).map(([r, l]) => `<option value="m:${r}" ${p.typ === "material" && (p.rolle || "platte") === r ? "selected" : ""}>Material: ${l}</option>`).join("")}</select></td>
          <td>${p.typ === "material" ? `<button class="btn" data-pmat="${i}" style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.material_id ? esc(matNamen[p.k] || "gewählt") : "beim Anlegen wählen"}</button>${p.material_id ? `<button class="ib" data-pmatx="${i}" title="keine Vorgabe">✕</button>` : ""}` : inp(`data-p="${i}" data-k="wert"`, vlZahl(p.wert), 90)}</td>
          <td>${p.typ === "material" ? "" : p.typ === "auswahl" ? inp(`data-p="${i}" data-k="optionen" title="Möglichkeiten: Zahl=Text, getrennt mit Semikolon. In Formeln zählt die Zahl, im Positionstext setzt {${esc(p.k)}:text} den Text ein."`, p.optionen, 300, "0=ohne; 1=Passleiste; 2=Blende") : inp(`data-p="${i}" data-k="einheit"`, p.einheit, 60)}</td><td><button class="btn rot" data-pdel="${i}">✕</button></td></tr>`).join("")}
      </table><button class="btn" id="vgPNeu" style="margin-top:6px">+ Parameter</button>
      <div class="sektion">Hilfswerte <span class="hinweis" style="font-weight:400">· Zwischenergebnisse, der Reihe nach gerechnet</span></div>
      <table class="liste"><tr><th>Kürzel</th><th>Bezeichnung</th><th>Formel</th><th>Wert mit Vorgaben</th><th title="Im Fenster „Position aus Vorlage“ anzeigen">zeigen</th><th></th></tr>
        ${v.hilfswerte.map((h, i) => `<tr><td>${inp(`data-h="${i}" data-k="k"`, h.k, 90)}</td><td>${inp(`data-h="${i}" data-k="name"`, h.name, 260)}</td><td>${inp(`data-h="${i}" data-k="formel"`, h.formel, 260)}</td>
          <td class="hinweis" data-hw-wert="${esc(h.k)}"></td><td><input type="checkbox" data-hzeig="${i}" ${h.verdeckt ? "" : "checked"}></td><td><button class="btn rot" data-hdel="${i}">✕</button></td></tr>`).join("")}
      </table><button class="btn" id="vgHNeu" style="margin-top:6px">+ Hilfswert</button>
      <div class="sektion">Prüfungen <span class="hinweis" style="font-weight:400">· Hinweis beim Anlegen, wenn die Bedingung zutrifft, z. B. <code>PLSL &lt; PLL</code></span></div>
      <table class="liste"><tr><th>Bedingung</th><th>Hinweistext (Werte mit {Kürzel})</th><th></th></tr>
        ${(v.pruefungen = v.pruefungen || []).map((x, i) => `<tr><td>${inp(`data-q="${i}" data-k="bedingung"`, x.bedingung, 260)}</td><td>${inp(`data-q="${i}" data-k="text"`, x.text, 420)}</td><td><button class="btn rot" data-qdel="${i}">✕</button></td></tr>`).join("")}
      </table><button class="btn" id="vgQNeu" style="margin-top:6px">+ Prüfung</button>
      <div class="sektion">Teile</div>
      <div style="overflow-x:auto"><table class="liste"><tr><th>Werkstoff</th><th>Verwendung</th><th>Stück</th><th>Länge</th><th>Breite</th><th>Kante o / u / l / r</th><th>Bedingung</th><th>Ergebnis</th><th></th></tr>
        ${v.teile.map((t, i) => `<tr><td>${pSel(`data-t="${i}" data-k="werkstoff"`, t.werkstoff, ["platte"])}</td><td>${inp(`data-t="${i}" data-k="verwendung"`, t.verwendung, 150)}</td>
          <td>${inp(`data-t="${i}" data-k="stueck"`, t.stueck, 70)}</td><td>${inp(`data-t="${i}" data-k="laenge"`, t.laenge, 120)}</td><td>${inp(`data-t="${i}" data-k="breite"`, t.breite, 120)}</td>
          <td class="nw">${["oben", "unten", "links", "rechts"].map(s => pSel(`data-t="${i}" data-g="kanten" data-s="${s}" style="max-width:90px" title="Kante ${s}"`, (t.kanten || {})[s], ["kante"])).join("")}</td>
          <td>${inp(`data-t="${i}" data-k="bedingung"`, t.bedingung, 80)}</td><td class="hinweis nw" data-t-erg="${i}"></td>
          <td class="nw"><button class="btn" data-tmehr="${i}" title="Furnier, Oberfläche, Bearbeitung">${offen === i ? "▴" : "⋯"}</button><button class="btn" data-tkop="${i}" title="kopieren">⧉</button><button class="btn rot" data-tdel="${i}">✕</button></td></tr>
          ${offen === i ? `<tr><td colspan="9"><div class="form" style="grid-template-columns:1fr 1fr">
            ${zeile("Furnier oben/unten", pSel(`data-t="${i}" data-g="furnier" data-s="oben"`, (t.furnier || {}).oben, ["furnier"]) + pSel(`data-t="${i}" data-g="furnier" data-s="unten"`, (t.furnier || {}).unten, ["furnier"]))}
            ${zeile("Oberfläche oben/unten", pSel(`data-t="${i}" data-g="oberflaeche" data-s="oben"`, (t.oberflaeche || {}).oben, ["oberflaeche"]) + pSel(`data-t="${i}" data-g="oberflaeche" data-s="unten"`, (t.oberflaeche || {}).unten, ["oberflaeche"]))}
            ${zeile("Fräsen", `<div class="radio">${["oben", "unten", "links", "rechts"].map(s => `<label><input type="checkbox" data-t="${i}" data-fr="${s}" ${(t.fraesen || {})[s] ? "checked" : ""}> ${s}</label>`).join("")}</div>`)}
            ${zeile("Verbinden / Bohren", `${inp(`data-t="${i}" data-k="verbinden"`, t.verbinden, 90, "Anzahl")} ${inp(`data-t="${i}" data-k="bohren"`, t.bohren, 90, "Anzahl")}`)}
            ${zeile("Tasche", `${inp(`data-t="${i}" data-k="taschen"`, t.taschen, 70, "Anzahl")} ${inp(`data-t="${i}" data-k="tasche_l"`, t.tasche_l, 110, "Länge mm")} ${inp(`data-t="${i}" data-k="tasche_b"`, t.tasche_b, 110, "Breite mm")} ${inp(`data-t="${i}" data-k="tasche_t"`, t.tasche_t, 90, "Tiefe")}`)}
            ${zeile("Gehrung", inp(`data-t="${i}" data-k="gehrung"`, t.gehrung, 90, "Anzahl"))}
            ${zeile("Bemerkung", inp(`data-t="${i}" data-k="bemerkung"`, t.bemerkung, 300))}</div></td></tr>` : ""}`).join("")}
      </table></div><button class="btn" id="vgTNeu" style="margin-top:6px">+ Teil</button>
      <div class="sektion">Beschläge</div>
      <table class="liste"><tr><th>Beschlag</th><th>Menge</th><th>Bedingung</th><th>Bemerkung</th><th></th></tr>
        ${v.beschlaege.map((b, i) => `<tr><td>${pSel(`data-b="${i}" data-k="material"`, b.material, ["beschlag"])}</td><td>${inp(`data-b="${i}" data-k="menge"`, b.menge, 140)}</td>
          <td>${inp(`data-b="${i}" data-k="bedingung"`, b.bedingung, 90)}</td><td>${inp(`data-b="${i}" data-k="bemerkung"`, b.bemerkung, 220)}</td><td><button class="btn rot" data-bdel="${i}">✕</button></td></tr>`).join("")}
      </table><button class="btn" id="vgBNeu" style="margin-top:6px">+ Beschlag</button>
      <div class="sektion">Tätigkeiten <span class="hinweis" style="font-weight:400">· aus dem Katalog; Bezugsgrößen rechnen mit der erzeugten Stückliste</span></div>
      <table class="liste"><tr><th>Kostenstelle</th><th>Tätigkeit</th><th class="r">Minuten</th><th>Bezugsgröße</th><th class="r">Rüstzeit</th><th class="r">Helfer</th><th></th></tr>
        ${v.zeiten.map((x, i) => `<tr><td><b>${esc(x.kst || "")}</b></td><td>${esc(x.name || "")}</td><td class="r">${numInp(x.minuten, `data-z="${i}" data-k="minuten" style="width:70px"`)}</td>
          <td><select data-z="${i}" data-k="bezug">${Object.entries(bezug).map(([k, [l, e]]) => `<option value="${k}" ${k === (x.bezug || "") ? "selected" : ""}>${esc(l)}</option>`).join("")}</select></td>
          <td class="r">${numInp(x.ruest, `data-z="${i}" data-k="ruest" style="width:60px"`)}</td><td class="r">${numInp(x.helfer, `data-z="${i}" data-k="helfer" style="width:50px"`, 1)}</td><td><button class="btn rot" data-zdelv="${i}">✕</button></td></tr>`).join("")}
      </table><button class="btn" id="vgZNeu" style="margin-top:6px">+ Tätigkeit …</button>
      <div class="kachel" id="vgProbe" style="margin-top:14px"></div>`;
  };
  const binden = () => {
    $("#vgWahl").onchange = e => { akt = V.find(v => v.id === e.target.value); offen = null; location.hash = `#/einstellungen/kalkulation/vorlagen/${akt.id}`; };
    $("#vgNeu").onclick = () => { akt = {id: "", name: "Neue Vorlage", einheit: "Stk.", text: "", parameter: [{k: "H", name: "Höhe", typ: "zahl", wert: 720, einheit: "mm"}, {k: "B", name: "Breite", typ: "zahl", wert: 600, einheit: "mm"}, {k: "T", name: "Tiefe", typ: "zahl", wert: 560, einheit: "mm"}, {k: "D", name: "Plattenstärke", typ: "zahl", wert: 19, einheit: "mm"}], hilfswerte: [], teile: [], beschlaege: [], zeiten: [], masse: {art: "HBT", h: "H", b: "B", t: "T"}}; V.push(akt); sofortSpeichern(); };
    const beispiel = async art => { try { const r = await api("positionsvorlagen/beispiel", {method: "POST", body: {art}}); V.splice(0, V.length, ...r.vorlagen); akt = V.at(-1); zeichnen(); probe(); toast("Beispielvorlage angelegt"); } catch (e) { toast(e.message, true); } };
    $("#vgBsp").onclick = () => beispiel("nische"); $("#vgBspK").onclick = () => beispiel("korpus");
    if (!akt) return;
    $("#vgKopie").onclick = () => { const k = JSON.parse(JSON.stringify(akt)); k.id = ""; k.name += " (Kopie)"; V.push(k); akt = k; sofortSpeichern(); };
    $("#vgDel").onclick = async () => { if (!await frage(`Vorlage „${akt.name}“ löschen?`)) return; V.splice(V.indexOf(akt), 1); akt = V[0] || null; sofortSpeichern(); };
    $$("[data-v]", z).forEach(el => el.oninput = () => { akt[el.dataset.v] = el.value; speichern(); });
    $$("[data-vm]", z).forEach(el => el.oninput = () => { akt.masse[el.dataset.vm] = el.value; speichern(); });
    const feld = (liste, attr) => $$(`[${attr}]`, z).forEach(el => {
      if (el.dataset.fr || el.dataset.g || attr === "data-z" && !el.dataset.k) return;
      el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
        const o = liste()[+el.getAttribute(attr)], k = el.dataset.k; if (!o || !k) return;
        if (k === "typ") { if (el.value === "zahl" || el.value === "auswahl") { o.typ = el.value; delete o.rolle; delete o.material_id; if (el.value === "auswahl" && !o.optionen) o.optionen = "0=nein; 1=ja"; } else { o.typ = "material"; o.rolle = el.value.slice(2); o.material_id = o.material_id || null; } speichern(true); return zeichnen(); }
        o[k] = attr === "data-z" && ["minuten", "ruest", "helfer"].includes(k) ? zahlEin(el.value) : el.value;
        speichern(el.tagName === "SELECT");
        if (attr === "data-p" && k === "k" || el.tagName === "SELECT" && attr !== "data-z") { /* Auswahllisten aktualisieren */ }
      });
    });
    feld(() => akt.parameter, "data-p"); feld(() => akt.pruefungen, "data-q"); feld(() => akt.hilfswerte, "data-h"); feld(() => akt.teile, "data-t"); feld(() => akt.beschlaege, "data-b"); feld(() => akt.zeiten, "data-z");
    $$("[data-p][data-k=k]", z).forEach(el => el.addEventListener("change", () => zeichnen()));
    $$("[data-p][data-k=wert]", z).forEach(el => el.addEventListener("input", () => { const n = /^[\d.,\s-]+$/.test(el.value) ? zahlLesen(el.value) : null; akt.parameter[+el.dataset.p].wert = n ? n.wert : el.value; speichern(); }));
    $$("[data-g]", z).forEach(el => el.onchange = () => { const t = akt.teile[+el.dataset.t], g = el.dataset.g; t[g] = t[g] || {}; if (el.value) t[g][el.dataset.s] = el.value; else delete t[g][el.dataset.s]; speichern(true); });
    $$("[data-hzeig]", z).forEach(el => el.onchange = () => { akt.hilfswerte[+el.dataset.hzeig].verdeckt = !el.checked; speichern(true); });
    $$("[data-fr]", z).forEach(el => el.onchange = () => { const t = akt.teile[+el.dataset.t]; t.fraesen = t.fraesen || {}; if (el.checked) t.fraesen[el.dataset.fr] = true; else delete t.fraesen[el.dataset.fr]; speichern(true); });
    $$("[data-pmat]", z).forEach(b => b.onclick = async () => {
      const p = akt.parameter[+b.dataset.pmat]; const m = await materialWaehlen(VL_KATS[p.rolle || "platte"], `Vorgabe für ${p.name || p.k}`);
      if (m) { p.material_id = m.id; matNamen[p.k] = `${m.nummer} ${(m.bezeichnung || "").split("\n")[0]}`; sofortSpeichern(); }
    });
    $$("[data-pmatx]", z).forEach(b => b.onclick = () => { akt.parameter[+b.dataset.pmatx].material_id = null; sofortSpeichern(); });
    const loesch = (attr, liste) => $$(`[${attr}]`, z).forEach(b => b.onclick = () => { liste().splice(+b.getAttribute(attr), 1); sofortSpeichern(); });
    loesch("data-pdel", () => akt.parameter); loesch("data-qdel", () => akt.pruefungen); loesch("data-hdel", () => akt.hilfswerte); loesch("data-tdel", () => akt.teile); loesch("data-bdel", () => akt.beschlaege); loesch("data-zdelv", () => akt.zeiten);
    $$("[data-tmehr]", z).forEach(b => b.onclick = () => { offen = offen === +b.dataset.tmehr ? null : +b.dataset.tmehr; zeichnen(); });
    $$("[data-tkop]", z).forEach(b => b.onclick = () => { const i = +b.dataset.tkop; akt.teile.splice(i + 1, 0, JSON.parse(JSON.stringify(akt.teile[i]))); sofortSpeichern(); });
    $("#vgPNeu").onclick = () => { akt.parameter.push({k: "", name: "", typ: "zahl", wert: 0, einheit: "mm"}); sofortSpeichern(); };
    $("#vgQNeu").onclick = () => { akt.pruefungen.push({bedingung: "", text: ""}); sofortSpeichern(); };
    $("#vgHNeu").onclick = () => { akt.hilfswerte.push({k: "", name: "", formel: ""}); sofortSpeichern(); };
    $("#vgTNeu").onclick = () => { akt.teile.push({werkstoff: (matParams(["platte"])[0] || {}).k || "", verwendung: "", stueck: "1", laenge: "", breite: "", kanten: {}}); sofortSpeichern(); };
    $("#vgBNeu").onclick = () => { akt.beschlaege.push({material: (matParams(["beschlag"])[0] || {}).k || "", menge: "1"}); sofortSpeichern(); };
    $("#vgZNeu").onclick = async () => {
      if (!K.length) return toast("Noch keine Tätigkeiten im Katalog (Kalkulation › Tätigkeiten).", true);
      const gew = new Set();
      const d = await modal("Tätigkeiten hinzufügen", `<div class="kat-liste">${K.map(t => `<label><input type="checkbox" data-kt="${esc(t.id)}"> <span><b>${esc(t.name)}</b> <span class="hinweis">${esc(t.kst)}</span></span></label>`).join("")}</div>`, "Hinzufügen",
        hg => $$("[data-kt]", hg).forEach(c => c.onchange = () => c.checked ? gew.add(c.dataset.kt) : gew.delete(c.dataset.kt)));
      if (!d) return;
      for (const t of K) if (gew.has(t.id)) { const {id, ...rest} = t; akt.zeiten.push({...rest, tid: id, gruppe: rest.gruppe || ""}); }
      sofortSpeichern();
    };
  };
  const sofortSpeichern = async () => {
    try { const r = await api("positionsvorlagen", {method: "PUT", body: {vorlagen: V}}); r.vorlagen.forEach((v, i) => { V[i].id = v.id; }); }
    catch (e) { toast(e.message, true); }
    zeichnen(); probe();
  };
  zeichnen(); probe();
}
