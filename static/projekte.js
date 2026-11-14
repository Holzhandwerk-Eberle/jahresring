// =====================================================================
//  Projekte: Klammer über mehrere Aufträge mit gemeinsamer Auswertung
//  (Belege, Kalkulation und Leitstand bleiben je Auftrag)
// =====================================================================
function auftraegeReiter(aktiv) {
  kopf({reiter: [["Aufträge", "#/auftraege", aktiv === "auftraege"], ["Projekte", "#/projekte", aktiv === "projekte"]]});
}
async function ansichtProjekte() {
  auftraegeReiter("projekte");
  const z = $("#inhalt"), f = (filter.projekte ||= {q: "", status: "aktiv"});
  const zeichnen = async () => {
    const liste = await api("projekte?" + new URLSearchParams({q: f.q, status: f.status}));
    sortierung.proj ||= {k: "nummer", ab: true};
    const t = tabelle("proj", [
      {k: "nummer", t: "Projekt", f: p => `<a href="#/projekt/${p.id}">${esc(p.nummer)}</a>`},
      {k: "bezeichnung", t: "Bezeichnung", f: p => `<a href="#/projekt/${p.id}">${esc(p.bezeichnung)}</a>`},
      {k: "kunde", t: "Kunde", f: p => p.kunde ? esc(p.kunde) : `<span class="hinweis">verschiedene</span>`},
      {k: "anzahl", t: "Aufträge", r: 1},
      {k: "beauftragt", t: "Beauftragt", r: 1, f: p => eur(p.summe.beauftragt)},
      {k: "berechnet", t: "Berechnet", r: 1, f: p => eur(p.summe.berechnet)},
      {k: "offen", t: "Offen", r: 1, f: p => p.summe.offen ? `<b>${eur(p.summe.offen)}</b>` : eur(0)},
    ], liste.map(p => ({...p, beauftragt: p.summe.beauftragt, berechnet: p.summe.berechnet, offen: p.summe.offen})),
    {klick: p => location.hash = `#/projekt/${p.id}`, leer: f.status === "aktiv" ? "Keine laufenden Projekte. Ein Projekt fasst mehrere Aufträge zusammen, z. B. Bauabschnitte, Lose oder Nachträge." : "Keine Projekte gefunden."});
    $("#pl", z).innerHTML = t.html; t.binden(zeichnen);
  };
  z.innerHTML = `<div class="titel"><h2>Projekte</h2>
      <div class="such"><input id="pQ" placeholder="Nummer, Bezeichnung, Kunde …" value="${esc(f.q)}" style="width:240px">
        <select id="pSt">${[["aktiv", "laufende"], ["abgeschlossen", "abgeschlossene"], ["alle", "alle"]].map(([v, l]) => `<option value="${v}" ${f.status === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
      <div class="rechts">${darf("auftraege", 2) ? `<button class="ib" id="neuP" title="Neues Projekt">${ic("neu")}</button>` : ""}</div></div>
    <p class="hinweis" style="margin-top:-6px">Ein Projekt ist optional und fasst mehrere Aufträge zusammen. Angebote, Rechnungen, Kalkulation und Leitstand bleiben beim einzelnen Auftrag; das Projekt zeigt die Summen und die gemeinsame Nachkalkulation.</p>
    <div id="pl"></div>`;
  let t; $("#pQ").oninput = e => { f.q = e.target.value; clearTimeout(t); t = setTimeout(zeichnen, 250); };
  $("#pSt").onchange = e => { f.status = e.target.value; zeichnen(); };
  $("#neuP") && ($("#neuP").onclick = async () => { const p = await neuesProjekt(); if (p) location.hash = `#/projekt/${p.id}`; });
  await zeichnen();
}

// Neues Projekt anlegen (optional mit Kunde und gleich zugeordneten Aufträgen); gibt das Projekt zurück
async function neuesProjekt({kunde_id = null, auftraege = []} = {}) {
  const kunden = await api("kunden");
  const d = await modal("Neues Projekt", `
    <div class="zeile"><label>Bezeichnung</label><div><input name="bezeichnung" placeholder="z. B. Neubau Kindergarten"></div></div>
    <div class="zeile"><label>Kunde</label><div><select name="kunde_id"><option value="">– verschiedene / keiner –</option>${kunden.map(k => `<option value="${k.id}" ${k.id === kunde_id ? "selected" : ""}>${k.nummer} · ${esc(k.kurzname)}</option>`).join("")}</select></div></div>
    <p class="hinweis">Die Projektnummer wird automatisch vergeben (P${new Date().getFullYear()}-01, -02 …). Aufträge werden danach auf der Projektseite oder im Auftrag zugeordnet.</p>`, "Anlegen");
  if (!d) return null;
  try {
    const p = await api("projekte", {method: "POST", body: {...d, auftraege}});
    toast(`Projekt ${p.nummer} angelegt`);
    return p;
  } catch (e) { toast(e.message, true); return null; }
}

async function ansichtProjekt(id) {
  const z = $("#inhalt");
  let p;
  try { p = await api("projekte/" + id); } catch (e) { kopf({}); z.innerHTML = `<div class="leer">${esc(e.message)}</div>`; return; }
  const schreiben = darf("auftraege", 2);
  kopf({krumen: [["Aufträge", "#/auftraege"], ["Projekte", "#/projekte"]], zurueck: "#/projekte",
    kontext: `Projekt <b>${esc(p.nummer)}</b> · <b>${esc(p.bezeichnung)}</b>${p.kunde ? ` · <a href="#/kunde/${p.kunde_id}">${p.kundennr} ${esc(p.kunde)}</a>` : ""} · ${p.auftraege.length} Auftr${p.auftraege.length === 1 ? "ag" : "äge"}`});
  const kunden = await api("kunden");
  const s = p.summe;
  const kachel = (t, w, hin = "", rot = false) => `<div class="pj-k"><div class="hinweis">${t}</div><b style="${rot ? "color:var(--rot)" : ""}">${w}</b>${hin ? `<div class="hinweis">${hin}</div>` : ""}</div>`;
  const pz = (a, b) => b ? Math.round(a / b * 100) + " %" : "";
  const vz = x => (x > 0.004 ? "+" : "") + n2(x);
  const si = [["Werkstoffe", "werkstoffe"], ["Beschläge", "beschlaege"], ["Oberfläche", "oberflaeche"], ["Kleinmaterial", "kleinmaterial"], ["Fremdleistungen", "fremdleistungen"], ["Zukauf", "zukauf"],
    ["Material mit GK", "material_gk"], ["Stunden", "stunden", 1], ["Lohn mit GK", "lohn_gk"], ["Sonderkosten Fertigung", "sonder_fertigung"], ["Selbstkosten", "selbstkosten"]];
  z.innerHTML = `
    <div class="titel"><h2>Projekt ${esc(p.nummer)}</h2><span class="speicher"></span>
      <div class="rechts"><a class="btn" href="/papier/projekt/${p.id}" target="_blank" title="Projekt-Nachkalkulation drucken oder als PDF speichern">🖨 Nachkalkulation</a>
        <a class="btn" href="/papier/projekt/${p.id}/zeitbericht" target="_blank" title="Alle gebuchten Zeiten der Aufträge des Projekts mit Tätigkeit und Mitarbeiter">🕒 Zeitbericht</a>
      ${schreiben ? `<button class="ib" id="pLoe" title="Projekt auflösen">${ic("loeschen")}</button>` : ""}</div></div>
    <div class="form" id="pf">
      ${zeile("Bezeichnung", inp(p, "bezeichnung"), true)}
      ${zeile("Kunde", `<select data-f="kunde_id"><option value="">– verschiedene / keiner –</option>${kunden.map(k => `<option value="${k.id}" ${k.id === p.kunde_id ? "selected" : ""}>${k.nummer} · ${esc(k.kurzname)}</option>`).join("")}</select>`)}
      ${zeile("Status", `<select data-f="status">${[["aktiv", "laufend"], ["abgeschlossen", "abgeschlossen"]].map(([v, l]) => `<option value="${v}" ${p.status === v ? "selected" : ""}>${l}</option>`).join("")}</select>`)}
      ${zeile("Bemerkungen", ta(p, "bemerkungen", 3), true)}
    </div>
    <div class="pj-kacheln">
      ${kachel("Angeboten (netto)", eur(s.angeboten))}
      ${kachel("Beauftragt (netto)", eur(s.beauftragt))}
      ${kachel("Berechnet (netto)", eur(s.berechnet), s.beauftragt ? pz(s.berechnet, s.beauftragt) + " vom Auftragswert" : "")}
      ${kachel("Bezahlt (brutto)", eur(s.bezahlt))}
      ${kachel("Offen (brutto)", eur(s.offen), "", s.offen > 0.004)}
      ${kachel("Ergebnis", eur(p.ergebnis), "berechnet − Ist-Selbstkosten", p.ergebnis < -0.004)}
    </div>
    <div class="titel" style="margin-top:14px"><h3 style="margin:0">Aufträge im Projekt</h3>
      <div class="rechts">${schreiben ? `<button class="btn" id="pZu">+ Auftrag zuordnen</button><button class="btn" id="pNeuA">+ Neuer Auftrag</button>` : ""}</div></div>
    <div class="tab-scroll"><table class="liste"><thead><tr><th>Auftrag</th><th>Bezeichnung</th><th>Kunde</th><th>Status</th>
      <th class="r">Beauftragt</th><th class="r">Berechnet</th><th class="r">Offen</th><th class="r">Std. Soll / Ist</th><th class="r">SK Soll / Ist</th>${schreiben ? "<th></th>" : ""}</tr></thead>
      <tbody>${p.auftraege.map(a => {
        const x = a.sollist || {};
        const ueber = x.ist_selbstkosten > x.soll_selbstkosten + 0.004 && x.soll_selbstkosten;
        return `<tr class="klick" data-link="#/auftrag/${a.id}"><td><a href="#/auftrag/${a.id}">${esc(a.nummer)}</a></td><td>${esc(a.bezeichnung)}</td><td>${esc(a.kunde)}</td><td>${statusMitSchritt(a)}</td>
          <td class="r">${eur(a.zahlen.beauftragt)}</td><td class="r">${eur(a.zahlen.berechnet)}</td><td class="r">${a.zahlen.offen ? `<b>${eur(a.zahlen.offen)}</b>` : eur(0)}</td>
          <td class="r nw">${n2(x.soll_stunden || 0, 1)} / ${n2(x.ist_stunden || 0, 1)}</td><td class="r nw" style="${ueber ? "color:var(--rot)" : ""}">${n2(x.soll_selbstkosten || 0)} / ${n2(x.ist_selbstkosten || 0)}</td>
          ${schreiben ? `<td><button class="ib" data-loesen="${a.id}" title="Aus dem Projekt nehmen (Auftrag bleibt bestehen)">✕</button></td>` : ""}</tr>`;
      }).join("") || `<tr><td colspan="10" class="leer">Noch keine Aufträge zugeordnet.</td></tr>`}
      ${p.auftraege.length > 1 ? `<tr class="sum"><td colspan="4"><b>Summe</b></td><td class="r"><b>${eur(s.beauftragt)}</b></td><td class="r"><b>${eur(s.berechnet)}</b></td><td class="r"><b>${eur(s.offen)}</b></td>
        <td class="r nw"><b>${n2(p.soll.stunden, 1)} / ${n2(p.ist.stunden, 1)}</b></td><td class="r nw"><b>${n2(p.soll.selbstkosten)} / ${n2(p.ist.selbstkosten)}</b></td>${schreiben ? "<td></td>" : ""}</tr>` : ""}</tbody></table></div>
    <h3 style="margin:18px 0 6px">Soll/Ist über alle Aufträge</h3>
    <div class="tab-scroll"><table class="liste" style="max-width:640px"><thead><tr><th>Kosten</th><th class="r">Soll</th><th class="r">Ist</th><th class="r">Abweichung</th></tr></thead><tbody>
      ${si.map(([l, k, std]) => { const d = p.ist[k] - p.soll[k]; return `<tr${k === "selbstkosten" ? ` class="sum"` : ""}><td>${k === "selbstkosten" ? `<b>${l}</b>` : l}</td><td class="r">${n2(p.soll[k], std ? 1 : 2)}</td><td class="r">${n2(p.ist[k], std ? 1 : 2)}</td>
        <td class="r" style="${d > 0.004 ? "color:var(--rot)" : ""}">${std ? (d > 0.04 ? "+" : "") + n2(d, 1) : vz(d)}</td></tr>`; }).join("")}
    </tbody></table></div>
    <p class="hinweis">Soll = Kalkulation der Aufträge. Ist = gebuchte Stunden, Auftragskosten und zugeordnete Lieferantenrechnungen. Berechnet = festgeschriebene Rechnungen netto ohne doppelt gezählte Abschläge; bezahlt und offen brutto aus den offenen Posten.</p>`;
  $$("tr.klick", z).forEach(tr => tr.onclick = ev => { if (!ev.target.closest("a,button")) location.hash = tr.dataset.link; });
  if (!schreiben) { $$("#pf [data-f]").forEach(el => el.disabled = true); return; }
  autospeichern($("#pf"), "projekte/" + p.id, (r, d) => { if ("bezeichnung" in d || "kunde_id" in d) ansichtProjekt(id); });
  $$("[data-loesen]", z).forEach(b => b.onclick = async ev => {
    ev.stopPropagation();
    const a = p.auftraege.find(x => x.id === +b.dataset.loesen);
    if (!await frage(`Auftrag ${a.nummer} aus dem Projekt entfernen?\n\nDer Auftrag selbst bleibt mit allen Belegen bestehen, nur die Zuordnung zum Projekt entfällt.`)) return;
    try { await api("projekte/" + p.id, {method: "PUT", body: {loesen: a.id}}); toast("Auftrag aus dem Projekt genommen"); ansichtProjekt(id); }
    catch (e) { toast(e.message, true); }
  });
  $("#pZu").onclick = async () => {
    const frei = await api("auftraege?projekt=ohne");
    if (!frei.length) return toast("Alle Aufträge sind schon einem Projekt zugeordnet.", true);
    frei.sort((a, b) => (b.kunde_id === p.kunde_id) - (a.kunde_id === p.kunde_id) || String(b.nummer).localeCompare(String(a.nummer), "de", {numeric: true}));
    const d = await modal("Auftrag zuordnen", `<div class="zeile"><label>Auftrag</label><div><select name="aid" size="10" style="height:auto">${frei.map(a => `<option value="${a.id}">${esc(a.nummer)} · ${esc(kurz(a.bezeichnung, 40))} · ${esc(a.kunde)} · ${esc(a.status || "")}</option>`).join("")}</select></div></div>
      <p class="hinweis">Es erscheinen nur Aufträge, die noch zu keinem Projekt gehören${p.kunde_id ? "; Aufträge des Projektkunden stehen oben" : ""}.</p>`, "Zuordnen");
    if (!d || !d.aid) return;
    try { await api("projekte/" + p.id, {method: "PUT", body: {zuordnen: +d.aid}}); toast("Auftrag zugeordnet"); ansichtProjekt(id); }
    catch (e) { toast(e.message, true); }
  };
  $("#pNeuA").onclick = () => neuerAuftrag(p.kunde_id ? kunden.find(k => k.id === p.kunde_id) : null, p.id);
  $("#pLoe").onclick = async () => {
    if (!await frage(`Projekt ${p.nummer} auflösen?\n\nDie ${p.auftraege.length} Aufträge bleiben mit allen Belegen bestehen, nur die Klammer „Projekt“ wird entfernt. Ordner auf der Festplatte bleiben unverändert.`, {ok: "Auflösen"})) return;
    try { await api("projekte/" + p.id, {method: "DELETE"}); toast("Projekt aufgelöst"); location.hash = "#/projekte"; }
    catch (e) { toast(e.message, true); }
  };
}

// Auswahl „Projekt“ im Auftrag (mit „+ neues Projekt …“)
async function projektFeld(a, nachher) {
  const el = $("#projektWahl");
  if (!el) return;
  const liste = await api("projekte?status=alle");
  const fuellen = () => {
    el.innerHTML = `<option value="">– kein Projekt –</option>` + liste.filter(p => p.status === "aktiv" || p.id === a.projekt_id)
      .map(p => `<option value="${p.id}" ${p.id === a.projekt_id ? "selected" : ""}>${esc(p.nummer)} · ${esc(p.bezeichnung)}</option>`).join("")
      + (darf("auftraege", 2) ? `<option value="neu">+ neues Projekt …</option>` : "");
  };
  fuellen();
  el.onchange = async () => {
    let wert = el.value;
    if (wert === "neu") {
      const p = await neuesProjekt({kunde_id: a.kunde_id});
      if (!p) { fuellen(); return; }
      liste.push(p); wert = String(p.id);
    }
    try {
      const r = await api("auftraege/" + a.id, {method: "PUT", body: {projekt_id: wert ? +wert : null}});
      Object.assign(a, {projekt_id: r.projekt_id, projekt_nr: r.projekt_nr, projekt: r.projekt});
      fuellen(); toast(wert ? `Dem Projekt ${r.projekt_nr} zugeordnet` : "Projektzuordnung entfernt");
      const link = $("#projektLink"); if (link) link.href = a.projekt_id ? `#/projekt/${a.projekt_id}` : "#/projekte";
      nachher && nachher(r);
    } catch (e) { toast(e.message, true); fuellen(); }
  };
}
