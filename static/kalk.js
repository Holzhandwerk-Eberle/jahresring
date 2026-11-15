"use strict";
// =====================================================================
//  Jahresring – Auftrag, Positionen, Kalkulation (Stufe 3a)
// =====================================================================

const n2 = (v, n = 2) => zahlDE(v, n);
// Benutzer ohne Preisrecht bekommen keine Beträge übertragen – dann einen Strich zeigen statt „0,00 €“
const eur = v => (typeof ICH !== "undefined" && ICH && ICH.rechte && ICH.rechte.preise === false) ? "–" : zahlDE(v) + " €";
const kurz = (t, n = 70) => { const z = klartext(String(t || "")).split("\n")[0]; return z.length > n ? z.slice(0, n - 1) + "…" : z; };
// Freie Kostenliste einer Position; ältere Einzelfelder (fremdleistungen/zukauf mit *_text) werden als Zeile gelesen
const klAusExtras = ex => {
  ex = ex || {};
  const z = (ex.kostenliste || []).filter(x => x && typeof x === "object");
  for (const art of KL_ALT) if (+ex[art] || String(ex[art + "_text"] || "").trim()) z.push({art, text: ex[art + "_text"] || "", menge: 1, einheit: "Pauschale", preis: +ex[art] || 0});
  return z;
};
const KL_ALT = ["fremdleistungen", "zukauf", "sonder_fertigung", "sonder_vertrieb"];
const klBetrag = x => (x.menge === "" || x.menge == null ? 1 : +x.menge || 0) * (+x.preis || 0);
const numInp = (wert, attr = "", n = 2) => `<input class="zahl" value="${wert === "" || wert == null ? "" : n2(wert, n)}" ${attr}>`;

// Kleiner Speicher-Helfer: sammelt Änderungen und schickt sie verzögert
function speicherer(pfad, nachher, methode = "PUT") {
  let offen = {}, timer;
  const anzeige = () => $(".speicher");
  const status = (t, k = "") => { const a = anzeige(); if (a) { a.textContent = t; a.className = "speicher " + k; } };
  const senden = async () => {
    clearTimeout(timer);
    const d = offen; offen = {};
    if (!Object.keys(d).length) return;
    status("speichert …");
    try { const r = await api(pfad, {method: methode, body: d}); status("gespeichert ✓", "ok"); nachher && nachher(r, d); }
    catch (e) { status("Fehler", "fehler"); toast(e.message, true); }
  };
  window.onbeforeunload = () => { if (Object.keys(offen).length) { senden(); return "Ungespeicherte Änderungen"; } };
  return {
    setze(k, v, sofort = false) { offen[k] = v; status("…"); clearTimeout(timer); timer = setTimeout(senden, sofort ? 30 : 600); },
    offen: () => Object.keys(offen).length > 0,   // noch nicht gesendete Änderungen vorhanden
    senden,
  };
}

// ---------------------------------------------------------------------
//  Kopf für alle Auftragsseiten
// ---------------------------------------------------------------------
function auftragKopf(a, aktiv, {zeile2 = "", werte = null, zurueck = null} = {}) {
  const r = [["Auftrag",""],["Positionen","positionen"],["Titel","titel"],["Kunde","kunde"],
    ["Belege","belege"],["Werkstatt","werkstatt"],["Auswertung","auswertung"],["Stunden","stunden"],["Soll/Ist","sollist"],["Offene Posten","op"],["Korrespondenz","briefe"],["Historie","historie"]]
    .filter(([l, s]) => !nurWerkstatt() || ["werkstatt", "historie"].includes(s))
    .map(([l, s]) => [l, s === null ? `#/kunde/${a.kunde_id}` : `#/auftrag/${a.id}${s ? "/" + s : ""}`, s !== null && s === aktiv]);
  // Auftragswerte-Reiter nur in der Position (dort in ansichtPosition); hier nur, falls die Seite direkt aufgerufen wurde
  const r2 = nurWerkstatt() || !werte ? [] : [["Werkstoffe","werkstoffe"],["Beschläge","beschlaege"],["Löhne","loehne"],["Zuschläge","zuschlaege"]]
    .map(([l, s]) => [l, `#/auftrag/${a.id}/werte/${s}`, werte === s]);
  kopf({krumen: [["Aufträge","#/auftraege"]], zurueck: zurueck || `#/kunde/${a.kunde_id}/auftraege`,
    kontext: `Auftrag <a href="#/auftrag/${a.id}" title="Zum Auftrag (Stammdaten)"><b>${esc(a.nummer)}</b></a> · <a href="#/auftrag/${a.id}"><b>${esc(a.bezeichnung)}</b></a> · <a href="#/kunde/${a.kunde_id}">${a.kundennr} ${esc(a.kunde)}</a>${a.projekt_nr ? ` · Projekt <a href="#/projekt/${a.projekt_id}">${esc(a.projekt_nr)}</a>` : ""}${a.status ? ` · ${statusMitSchritt(a)}${werkstattSchritt(a) ? ` <a href="#/leitstand" title="Im Leitstand ansehen">▸</a>` : ""}` : ""}`
      + (zeile2 ? `<br><span style="padding-left:18px">${zeile2}</span>` : ""),
    reiter: r, reiter2: r2});
  $(".wrap").classList.add("mit-seite");
  projektBrowser($("#seite"), a);
}

async function ansichtAuftrag(id, reiter = "auftrag", sub) {
  const a = await api("auftraege/" + id);
  if (reiter === "anhaenge") reiter = "historie";   // früherer Reiter „Anhänge“
  if (nurWerkstatt() && !["werkstatt", "historie"].includes(reiter)) reiter = "werkstatt";
  if (reiter === "werte") { auftragKopf(a, null, {werte: sub || "werkstoffe"}); return auftragsWerte($("#inhalt"), {auftrag: a, teil: sub || "werkstoffe"}); }
  auftragKopf(a, reiter === "auftrag" ? "" : reiter);
  const z = $("#inhalt");
  switch (reiter) {
    case "positionen": return positionsListe(z, a);
    case "titel": return titelSeite(z, a);
    case "historie": return historieSeite(z, a);
    case "kunde": return auftragKundendaten(z, a);
    case "belege": return belegeListe(z, a);
    case "werkstatt": return werkstattSeite(z, a);
    case "auswertung": return auswertungSeite(z, a);
    case "stunden": return stundenSeite(z, a);
    case "sollist": return sollIstSeite(z, a);
    case "op": return opListeNeu(z, {auftrag: a});
    case "briefe": return korrespondenzListe(z, {auftrag: a});
    default: return auftragStamm(z, a);
  }
}

// ---------------------------------------------------------------------
//  Reiter „Auftrag“
// ---------------------------------------------------------------------
async function auftragStamm(z, a) {
  const [kunden, pos, belege] = await Promise.all([api("kunden?status=alle"), api(`auftraege/${a.id}/positionen`), api(`auftraege/${a.id}/belege`)]);
  const kOpt = k => `${k.nummer} · ${k.kurzname}${k.ort ? " · " + k.ort : ""}`;
  const vorschau = pos.positionen.slice(0, 8).map(p => `<div><a href="#/position/${p.id}">${p.posnr}</a> &nbsp;${p.zeige.anzahl ? n2(p.menge, p.menge % 1 ? 2 : 0) + " " + esc(p.einheit) + " " : ""}${esc(kurz(p.text, 90))}</div>`).join("")
    + (pos.positionen.length > 8 ? `<div class="hinweis">… und ${pos.positionen.length - 8} weitere</div>` : "");
  z.innerHTML = `
    <div class="titel"><h2>Auftrag ${esc(a.nummer)}</h2><span class="speicher"></span>
      <div class="rechts"><button class="ib" id="loeschen" title="Auftrag löschen">${ic("loeschen")}</button></div></div>
    <div class="form" id="f">
      ${zeile("Bezeichnung", inp(a, "bezeichnung"), true)}
      ${zeile("Kunde", `<input id="kundeWahl" list="kundenListe" value="${esc(kOpt(kunden.find(k => k.id === a.kunde_id) || {nummer: a.kundennr, kurzname: a.kunde}))}"><datalist id="kundenListe">${kunden.map(k => `<option value="${esc(kOpt(k))}">`).join("")}</datalist><a class="aktion" href="#/kunde/${a.kunde_id}" title="Kunde öffnen">${ic("uebernehmen")}</a>`)}
      ${zeile("Gruppe", sel(a, "gruppe", E.auftragsgruppen))}
      ${zeile("Status", sel(a, "status", E.auftragsstatus))}
      ${zeile("Projekt", `<select id="projektWahl"><option value="">– kein Projekt –</option></select><a class="aktion" id="projektLink" href="${a.projekt_id ? "#/projekt/" + a.projekt_id : "#/projekte"}" title="Projekt öffnen">${ic("uebernehmen")}</a>`)}
      ${zeile("Fertigung begonnen", `<input type="date" data-f="fertigung" value="${esc(a.fertigung)}" title="Wird beim Status „Fertigung“ automatisch eingetragen, wenn leer">`)}
      ${zeile("Geliefert am", `<input type="date" data-f="lieferung" value="${esc(a.lieferung)}" title="Wird mit dem Lieferschein automatisch eingetragen, wenn leer; Vorschlag für das Leistungsdatum der Rechnung">`)}
      <div class="sektion">Planung</div>
      <div id="planung" style="grid-column:1/-1;display:grid;gap:3px"></div>
      <div class="sektion">Positionen / Kundenbelege</div>
      <div class="zeile voll"><label><a href="#/auftrag/${a.id}/positionen">▸ Positionen</a></label><div style="display:block;padding:7px 10px">
        ${vorschau || `<span class="hinweis">Noch keine Positionen. <a href="#/auftrag/${a.id}/positionen">Jetzt erfassen</a></span>`}
        ${pos.positionen.length ? `<div style="margin-top:6px"><b>Nettosumme ${eur(pos.netto)}</b></div>` : ""}</div></div>
      <div class="zeile voll"><label><a href="#/auftrag/${a.id}/belege">▸ Kundenbelege</a></label><div style="display:block;padding:7px 10px">${belege.map(b => `<div><a href="#/beleg/${b.id}">${esc(belegName(b))}</a> vom ${datum(b.datum)} über ${eur(b.brutto)}${b.status === "storniert" ? " <span class='hinweis'>(storniert)</span>" : ""}</div>`).join("") || `<span class="hinweis">Noch keine. <a href="#/auftrag/${a.id}/belege">Angebot oder Rechnung erstellen</a></span>`}</div></div>
      <div class="sektion">Bemerkungen</div>
      ${zeile("Bemerkungen", ta(a, "bemerkungen", 6), true)}
      <div id="wvBox"></div>
    </div>`;
  auftragWiedervorlagen($("#wvBox"), a);
  auftragPlanung($("#planung"), a);
  const kopfNeu = r => { Object.assign(a, r); auftragKopf(a, ""); };
  projektFeld(a, kopfNeu);
  autospeichern($("#f"), "auftraege/" + a.id, (r, d) => {
    if ("bezeichnung" in d) kopfNeu(r);
    if ("status" in d && r.fertigung && !$("[data-f=fertigung]").value) { $("[data-f=fertigung]").value = r.fertigung; toast("Fertigungsbeginn eingetragen: " + datum(r.fertigung)); }
    if (("fertigung" in d || "lieferung" in d) && !("status" in d) && r.status !== $("[data-f=status]").value) { $("[data-f=status]").value = r.status; a.status = r.status; kopfNeu(r); toast("Status: " + r.status); }
  });
  $("#kundeWahl").onchange = async e => {
    const k = kunden.find(k => kOpt(k) === e.target.value);
    if (!k) return toast("Bitte einen Kunden aus der Liste wählen.", true);
    if (k.id === a.kunde_id) return;
    try { kopfNeu(await api("auftraege/" + a.id, {method: "PUT", body: {kunde_id: k.id}})); toast("Kunde geändert · Kundendaten neu übernommen"); }
    catch (er) { toast(er.message, true); }
  };
  $("#loeschen").onclick = async () => {
    if (!await frage(`Auftrag ${a.nummer} mit allen Positionen löschen? Der Projektordner auf der Festplatte bleibt erhalten.`)) return;
    try { await api("auftraege/" + a.id, {method: "DELETE"}); toast("Auftrag gelöscht"); location.hash = `#/kunde/${a.kunde_id}/auftraege`; }
    catch (x) { toast(x.message, true); }
  };
}

// ---------------------------------------------------------------------
//  Reiter „Positionen“
// ---------------------------------------------------------------------
const titelName = (titel, nr) => { const t = titel.find(t => t.nr === nr); return t ? t.name : ""; };
async function neuePosition(a, {titel = 0, parent_id = null, text = "", zeige = null, oeffnen = true} = {}) {
  const body = {titel, parent_id, text};
  if (zeige) body.zeige = zeige;
  const r = await api(`auftraege/${a.id}/positionen`, {method: "POST", body});
  if (oeffnen) location.hash = `#/position/${r.id}`;
  return r.id;
}

async function textbausteinWaehlen() {
  const tb = E.textbausteine || [];
  if (!tb.length) { toast("Noch keine Textbausteine. Sie lassen sich in den Einstellungen anlegen.", true); return null; }
  const d = await modal("Textbaustein einfügen", `
    <div class="zeile"><label>Baustein</label><div><select name="i">${tb.map((t, i) => `<option value="${i}">${esc(t.name)}</option>`).join("")}</select></div></div>
    <div id="tbVorschau" class="hinweis rt-vorschau" style="max-height:220px;overflow:auto;margin-top:8px;padding:8px;background:var(--zeile);border-radius:5px">${textHtml(tb[0].text)}</div>`, "Einfügen");
  return d ? tb[+d.i] : null;
}
document.addEventListener("change", e => { if (e.target.matches(".modal [name=i]") && $("#tbVorschau")) $("#tbVorschau").innerHTML = textHtml((E.textbausteine || [])[+e.target.value]?.text || ""); });

// Ansicht der Positionsliste: "text" (aufgeklappt, voller Text) oder "kalk" (zugeklappt mit Kalkulationsspalten)
const plAnsicht = {get() { try { return localStorage.getItem("plAnsicht") || "text"; } catch (e) { return plAnsicht._w || "text"; } },
  set(v) { plAnsicht._w = v; try { localStorage.setItem("plAnsicht", v); } catch (e) {} }};

// Kalkulationswerte einer Position je Stück inkl. Unterpositionen
function plWerte(p) {
  const c = p.calc || {};
  const w = {werk: c.material_gk || 0, lohn: c.lohn_gk || 0, std: c.stunden || 0,
    skf: c.sonder_fertigung || 0, sk: c.selbstkosten || 0, skv: c.sonder_vertrieb || 0};
  for (const kd of p.kinder || []) {
    const u = plWerte(kd), m = +kd.menge || 0;
    for (const x of ["werk", "lohn", "std", "skf", "sk", "skv"]) w[x] += u[x] * m;
  }
  return w;
}
const MASS_ARTEN = {HBT: "hbt", BHT: "bht", LBD: "lbd"};  // H*B*T, B*H*T, L*B*D
const masseText = m => { m = m || {}; const t = [...(MASS_ARTEN[m.art] || "hbt")].map(x => [x.toUpperCase(), m[x]]).filter(([, v]) => v).map(([l, v]) => `${l} ${zahlDE(v, 0)}`); return t.join(" * "); };

async function positionsListe(z, a) {
  const d = await api(`auftraege/${a.id}/positionen`);
  const ansicht = plAnsicht.get();
  const kalk = ansicht === "kalk";
  $(".wrap").classList.toggle("seite-unten", kalk);  // breite Kalkulationstabelle: Projektordner unter die Liste
  const gruppen = [];
  const titelReihe = [{nr: 0, name: ""}, ...d.titel];
  for (const t of titelReihe) {
    const ps = d.positionen.filter(p => p.titel === t.nr);
    if (ps.length || t.nr) gruppen.push({t, ps});
  }
  const bekannt = new Set(titelReihe.map(t => t.nr));
  const rest = d.positionen.filter(p => !bekannt.has(p.titel));
  if (rest.length) gruppen.push({t: {nr: -1, name: "Titel fehlt"}, ps: rest});
  const titelGesperrt = new Set(d.titel.filter(t => t.gesperrt).map(t => t.nr));
  const klammer = (an, s) => an ? s : `{${s}}`;
  const spalten = kalk ? 11 : 6;
  const summe = {werk: 0, lohn: 0, std: 0, skf: 0, sk: 0, wg: 0, skv: 0};
  const nrZelle = p => `<td class="pl-nr"><span class="pl-griff" title="Ziehen zum Verschieben">⋮⋮</span><button class="pl-sperre" data-sperre="${p.id}" title="${p.gesperrt ? "Gesperrt (wird nicht gedruckt, nicht in der Summe). Klick: entsperren" : "Klick: Position sperren (wird nicht gedruckt, nicht in der Summe)"}">${klammer(p.zeige.posnr, p.posnr)}${p.alternativ ? "<small>ALT</small>" : ""}</button>${(p.calc?.warnungen || []).length ? `<span title="${esc(p.calc.warnungen.join("\n"))}" style="color:#b8860b;cursor:help">⚠</span>` : ""}</td>`;
  const akt = `<div class="pl-akt"><button data-a="hoch" title="nach oben">▲</button><button data-a="runter" title="nach unten">▼</button><button data-a="kopie" title="kopieren">⧉</button><button data-a="del" title="löschen">✕</button></div>`;
  const posZeile = p => {
    const c = p.calc, zaehlt = p.zeige.gp && !p.gesperrt && !p.alternativ && !titelGesperrt.has(p.titel);
    const gp = zaehlt ? eur(c.gesamtpreis) : (c.gesamtpreis ? `{${eur(c.gesamtpreis)}}` : "");
    if (kalk) {
      const w = plWerte(p), m = +p.menge || 0, wg = c.gesamtpreis - (w.sk + w.skv) * m;
      if (zaehlt) { summe.werk += w.werk * m; summe.lohn += w.lohn * m; summe.std += w.std * m; summe.skf += w.skf * m; summe.sk += w.sk * m; summe.skv += w.skv * m; summe.wg += wg; }
      const zahl = v => zahlDE(v);
      const marken = [(p.stueckliste || []).length ? `<span class="pl-marke" title="Stückliste">S</span>` : "", (p.beschlaege || []).length ? `<span class="pl-marke" title="Beschläge">B</span>` : ""].join("");
      const mt = masseText(p.masse);
      return `<tr class="pl-pos pl-kalk${p.gesperrt ? " gesperrt" : ""}" data-id="${p.id}" data-titel="${p.titel}" draggable="true">
        ${nrZelle(p)}
        <td class="r">${klammer(p.zeige.anzahl, n2(p.menge, p.menge % 1 ? 2 : 0))}</td>
        <td class="pl-text"><div class="pl-kurz">${p.zeige.anzahl ? esc(p.einheit) + " " : ""}${esc(kurz(p.text, 110)) || "<span class='hinweis'>(ohne Text)</span>"}</div>${mt ? `<div class="hinweis">${mt}</div>` : ""}${p.kinder.length ? `<div class="hinweis">+ ${p.kinder.length} Unterposition${p.kinder.length > 1 ? "en" : ""}</div>` : ""}</td>
        <td class="r nw">${zahl(w.werk * m)}${marken ? `<div>${marken}</div>` : ""}</td>
        <td class="r nw">${zahl(w.lohn * m)}${(p.zeiten || []).length ? `<div><span class="pl-marke" title="Tätigkeiten">T</span></div>` : ""}</td>
        <td class="r nw">${zahlDE(w.std * m)}h</td>
        <td class="r nw">${zahl(w.skf * m)}</td>
        <td class="r nw">${zahl(w.sk * m)}</td>
        <td class="r nw">${wg >= 0 ? "+" : ""}${zahl(wg)}<div class="hinweis">${w.sk ? zahlDE(wg / (w.sk * m || 1) * 100, 0) + "%" : ""}</div></td>
        <td class="r nw">${zahl(w.skv * m)}</td>
        <td class="r nw">${zaehlt ? zahl(c.gesamtpreis) : `{${zahl(c.gesamtpreis)}}`}${akt}</td></tr>`;
    }
    // Unterpositionen: Text, Einzelpreis und Gesamtpreis je Unterposition in den Spalten der Liste
    const kl = v => p.unterdruck === "verdeckt" || p.unterdruck === "text" ? "{" + eur(v) + "}" : eur(v);
    const unter = p.kinder.length ? `<tr class="pl-unter" data-zu="${p.id}"><td></td><td></td><td></td>
        <td><div class="pl-uz"><a href="#/position/${p.id}/unterpositionen">▸ ${p.kinder.length} Unterposition${p.kinder.length > 1 ? "en" : ""}</a></div>
        ${p.kinder.map(k => `<div class="pl-uz">${n2(k.menge, k.menge % 1 ? 2 : 0)} ${esc(k.einheit)} ${esc(kurz(k.text, 60))}</div>`).join("")}</td>
        <td class="r"><div class="pl-uz">&nbsp;</div>${p.kinder.map(k => `<div class="pl-uz">${kl(k.calc.ep_gesamt)}</div>`).join("")}</td>
        <td class="r"><div class="pl-uz">&nbsp;</div>${p.kinder.map(k => `<div class="pl-uz">${kl(k.calc.gesamtpreis)}</div>`).join("")}</td></tr>` : "";
    return `<tr class="pl-pos${p.gesperrt ? " gesperrt" : ""}" data-id="${p.id}" data-titel="${p.titel}" draggable="true">
      ${nrZelle(p)}
      <td class="hinweis">${esc(p.status || "")}</td>
      <td class="r">${klammer(p.zeige.anzahl, n2(p.menge, p.menge % 1 ? 2 : 0))}</td>
      <td class="pl-text"><div>${p.zeige.anzahl ? esc(p.einheit) + " " : ""}${p.text ? textHtml(p.text) : "<span class='hinweis'>(ohne Text)</span>"}</div></td>
      <td class="r">${p.zeige.ep ? eur(c.ep_gesamt) : ""}${c.hat_kalk && !p.preis_manuell ? `<div class="hinweis" title="berechnet">kalk.</div>` : ""}</td>
      <td class="r">${gp}${akt}</td>
    </tr>${unter}`;
  };
  const kopfZeile = kalk
    ? `<tr><th style="width:62px">Pos.</th><th class="r" style="width:54px">Anzahl</th><th>Bezeichnung</th><th class="r">Werkstoffe</th><th class="r">Lohnkosten</th><th class="r">Sollstd</th><th class="r" title="Sonderkosten der Fertigung">SK-Fert</th><th class="r">Selbstkosten</th><th class="r" title="Wagnis und Gewinn">WuG</th><th class="r" title="Sonderkosten des Vertriebs">SK-Vertr</th><th class="r" style="width:110px">Gesamtpreis</th></tr>`
    : `<tr><th style="width:62px">Pos.</th><th style="width:70px">Status</th><th class="r" style="width:60px">Anzahl</th><th>Text</th><th class="r" style="width:120px">Einzelpreis</th><th class="r" style="width:150px">Gesamtpreis</th></tr>`;
  const koerper = gruppen.map(({t, ps}) => `
        ${t.nr ? `<tr class="pl-titel" data-titelnr="${t.nr}"><td colspan="${spalten - 1}"><span class="hinweis">T${String(t.nr).padStart(2, "0")}</span>&nbsp; <b>${esc(t.name || "(ohne Namen)")}</b>${t.gesperrt ? " <span class='hinweis'>(gesperrt)</span>" : ""}</td><td class="r"><button class="btn" data-neu-titel="${t.nr}">+ Position</button></td></tr>` : ""}
        ${ps.map(posZeile).join("")}
        ${t.nr && d.titel_druck === "summen" && ps.length ? `<tr class="pl-tsum"><td colspan="${spalten - 1}" class="r">Summe T${String(t.nr).padStart(2, "0")}</td><td class="r">${eur(d.titel_summen[t.nr] || 0)}</td></tr>` : ""}
      `).join("");
  const fuss = kalk
    ? `<tr class="pl-summe"><td colspan="3"><b>Nettosummen</b></td><td class="r">${zahlDE(summe.werk)}</td><td class="r">${zahlDE(summe.lohn)}</td><td class="r nw">${zahlDE(summe.std)}h</td><td class="r">${zahlDE(summe.skf)}</td><td class="r">${zahlDE(summe.sk)}</td><td class="r nw">${summe.wg >= 0 ? "+" : ""}${zahlDE(summe.wg)}<div class="hinweis">${summe.sk ? zahlDE(summe.wg / summe.sk * 100, 0) + "%" : ""}</div></td><td class="r">${zahlDE(summe.skv)}</td><td class="r"><b>${zahlDE(d.netto)}</b></td></tr>`
    : `<tr class="pl-summe"><td colspan="5"><b>Nettosumme</b></td><td class="r"><b>${eur(d.netto)}</b></td></tr>`;
  z.innerHTML = `
    <div class="titel"><h2>Positionen</h2>
      <div class="rechts">
        <button class="btn" id="plAnsicht" title="${kalk ? "Positionen mit vollem Text zeigen" : "Positionen zuklappen und Kalkulationswerte zeigen"}">${kalk ? "▾ Aufklappen" : "▸ Zuklappen"}</button>
        <button class="btn" id="neuBaustein">+ aus Textbaustein</button>
        <button class="btn" id="neuAusAuftrag" title="Position aus einem anderen Auftrag kopieren">+ aus anderem Auftrag</button>
        <button class="btn" id="neuVorlage" title="Position aus einer Vorlage: Maße eingeben, Stückliste wird erzeugt">+ aus Vorlage</button>
        <button class="btn prim" id="neuPos">+ Neue Position</button>
      </div></div>
    <table class="liste pl${kalk ? " pl-zu" : ""}">
      ${kopfZeile}
      ${koerper}
      ${fuss}
    </table>
    ${d.positionen.length ? "" : `<div class="leer" style="margin-top:8px">Noch keine Positionen. ${d.titel.length ? "" : "Tipp: Unter „Titel“ lassen sich Positionen gruppieren, z. B. „Bad“ und „Gäste-WC“."}</div>`}
    <p class="hinweis">Werte in {Klammern} werden nicht gedruckt bzw. nicht in die Summe gerechnet (Alternativ-/Bedarfsposition oder Hinweis). Klick auf die Positionsnummer sperrt bzw. entsperrt die Position,
    Klick auf die übrige Zeile öffnet Text und Kalkulation. Positionen lassen sich mit der Maus an eine andere Stelle oder in einen anderen Titel ziehen.</p>`;
  const neuLaden = () => positionsListe(z, a);
  const ersterTitel = d.titel[0]?.nr || 0;
  $("#plAnsicht").onclick = () => { plAnsicht.set(kalk ? "text" : "kalk"); neuLaden(); };
  $("#neuPos").onclick = () => neuePosition(a, {titel: ersterTitel});
  $("#neuBaustein").onclick = async () => {
    const tb = await textbausteinWaehlen(); if (!tb) return;
    await neuePosition(a, {titel: d.titel.at(-1)?.nr || 0, text: tb.text, zeige: {posnr: 0, anzahl: 0, ep: 0, gp: 0}, oeffnen: false});
    toast("Textbaustein eingefügt"); neuLaden();
  };
  $("#neuAusAuftrag").onclick = () => positionAusAuftrag(a, d.titel, neuLaden);
  $("#neuVorlage").onclick = () => vorlageDialog({a, titel: d.titel.at(-1)?.nr || 0});
  cadHinweis(z, a, d);
  $$("[data-neu-titel]", z).forEach(b => b.onclick = () => neuePosition(a, {titel: +b.dataset.neuTitel}));
  $$("[data-sperre]", z).forEach(b => b.onclick = async ev => {
    ev.stopPropagation();
    const p = d.positionen.find(x => x.id === +b.dataset.sperre);
    try { await api(`positionen/${p.id}`, {method: "PUT", body: {gesperrt: p.gesperrt ? 0 : 1}}); toast(p.gesperrt ? `Position ${p.posnr} entsperrt` : `Position ${p.posnr} gesperrt (nicht in der Summe)`); neuLaden(); }
    catch (e) { toast(e.message, true); }
  });
  $$("tr.pl-pos", z).forEach(tr => {
    const id = +tr.dataset.id;
    tr.onclick = async ev => {
      const b = ev.target.closest("button[data-a]");
      if (!b) { if (!ev.target.closest("a,button")) location.hash = `#/position/${id}`; return; }
      ev.stopPropagation();
      try {
        if (b.dataset.a === "hoch" || b.dataset.a === "runter") await api(`positionen/${id}/verschieben`, {method: "POST", body: {richtung: b.dataset.a === "hoch" ? -1 : 1}});
        if (b.dataset.a === "kopie") { await api(`positionen/${id}/kopieren`, {method: "POST"}); toast("Position kopiert"); }
        if (b.dataset.a === "del") { if (!await frage("Position mit Kalkulation und Unterpositionen löschen?")) return; await api(`positionen/${id}`, {method: "DELETE"}); toast("Position gelöscht"); }
        neuLaden();
      } catch (e) { toast(e.message, true); }
    };
  });
  positionenZiehen(z, d, neuLaden);
}

// ---------- Drag & Drop der Positionen (auch in andere Titel) ----------
function positionenZiehen(z, d, neuLaden) {
  const tab = $("table.pl", z); if (!tab) return;
  let zieh = null;
  const weg = () => $$(".drop-vor,.drop-nach", tab).forEach(x => x.classList.remove("drop-vor", "drop-nach"));
  // Ziel aus der Zeile unter der Maus bestimmen: {titel, vor, zeile, unten}
  const ziel = ev => {
    let tr = ev.target.closest("tr"); if (!tr || !tab.contains(tr)) return null;
    if (tr.classList.contains("pl-unter")) tr = tab.querySelector(`tr.pl-pos[data-id="${tr.dataset.zu}"]`);
    if (tr.classList.contains("pl-titel")) {
      const nr = +tr.dataset.titelnr;
      const erste = d.positionen.find(p => p.titel === nr);
      return {titel: nr, vor: erste ? erste.id : null, zeile: tr, unten: true};
    }
    if (!tr.classList.contains("pl-pos")) return null;
    const id = +tr.dataset.id, titel = +tr.dataset.titel;
    const r = tr.getBoundingClientRect(), unten = ev.clientY > r.top + r.height / 2;
    const imTitel = d.positionen.filter(p => p.titel === titel);
    const i = imTitel.findIndex(p => p.id === id);
    const vor = unten ? (imTitel[i + 1] ? imTitel[i + 1].id : null) : id;
    const zeile = unten ? (tr.nextElementSibling && tr.nextElementSibling.classList.contains("pl-unter") ? tr.nextElementSibling : tr) : tr;
    return {titel, vor, zeile, unten};
  };
  $$("tr.pl-pos", tab).forEach(tr => {
    tr.addEventListener("dragstart", ev => {
      zieh = +tr.dataset.id; tr.classList.add("zieht");
      ev.dataTransfer.effectAllowed = "move"; ev.dataTransfer.setData("text/plain", String(zieh));
    });
    tr.addEventListener("dragend", () => { tr.classList.remove("zieht"); weg(); zieh = null; });
  });
  tab.addEventListener("dragover", ev => {
    if (zieh == null) return;
    const zl = ziel(ev); if (!zl) return;
    ev.preventDefault(); ev.dataTransfer.dropEffect = "move";
    weg(); zl.zeile.classList.add(zl.unten ? "drop-nach" : "drop-vor");
  });
  tab.addEventListener("dragleave", ev => { if (!tab.contains(ev.relatedTarget)) weg(); });
  tab.addEventListener("drop", async ev => {
    if (zieh == null) return;
    ev.preventDefault();
    const zl = ziel(ev); weg();
    const id = zieh; zieh = null;
    if (!zl || zl.vor === id) return;
    const p = d.positionen.find(x => x.id === id);
    const imTitel = d.positionen.filter(x => x.titel === zl.titel);
    const nachfolger = imTitel[imTitel.findIndex(x => x.id === id) + 1];
    if (p.titel === zl.titel && ((nachfolger && zl.vor === nachfolger.id) || (!nachfolger && zl.vor === null))) return; // gleiche Stelle
    try { await api(`positionen/${id}/einordnen`, {method: "POST", body: {titel: zl.titel, vor: zl.vor}}); neuLaden(); }
    catch (e) { toast(e.message, true); }
  });
}

// ---------- Position aus einem anderen Auftrag übernehmen ----------
async function positionAusAuftrag(a, titel, danach) {
  const gewaehlt = new Set();
  let liste = [], laeuft = 0;
  const inhalt = `
    <div class="zeile"><label>Suchen</label><div><input id="paSuche" placeholder="z. B. Esstisch, Garderobe, Eiche …" autocomplete="off" data-enter="paLos"></div></div>
    ${titel.length ? `<div class="zeile"><label>In Titel</label><div><select name="titel">${[{nr: 0, name: "(ohne Titel)"}, ...titel].map(t => `<option value="${t.nr}" ${t.nr === titel[0].nr ? "selected" : ""}>${t.nr ? "T" + String(t.nr).padStart(2, "0") + " " : ""}${esc(t.name || "")}</option>`).join("")}</select></div></div>` : ""}
    <div id="paListe" style="max-height:52vh;overflow:auto;margin-top:8px"></div>
    <p class="hinweis" style="margin-bottom:0">Kopiert werden Text, Maße, Stückliste, Beschläge, Tätigkeiten, Bilder und Unterpositionen. Berechnete Preise ergeben sich neu aus den Kalkulationswerten dieses Auftrags; ein fest eingetragener Einzelpreis bleibt.</p>
    <button id="paLos" type="button" hidden></button>`;
  const zeichnen = hg => {
    const box = $("#paListe", hg);
    if (!liste.length) { box.innerHTML = `<div class="leer">${$("#paSuche", hg).value.trim() ? "Nichts gefunden." : "Suchbegriff eingeben – gesucht wird im Positionstext aller Aufträge."}</div>`; return; }
    box.innerHTML = `<table class="liste">${liste.map(p => `<tr class="klick" data-pa="${p.id}">
      <td style="width:28px"><input type="checkbox" data-pa-cb="${p.id}" ${gewaehlt.has(p.id) ? "checked" : ""}></td>
      <td><b>${esc(kurz(p.text, 90))}</b>${masseText(p.masse) ? ` <span class="hinweis">${masseText(p.masse)}</span>` : ""}${p.unter ? ` <span class="hinweis">· ${p.unter} Unterpos.</span>` : ""}
        <div class="hinweis">Auftrag ${esc(p.auftrag)} · ${esc(p.bezeichnung || "")} · ${esc(p.kunde)} · Pos. ${esc(p.posnr)}${p.datum ? " · " + datum(p.datum) : ""}</div>
        <details class="pa-text" style="margin-top:2px"><summary class="hinweis" style="cursor:pointer">ganzer Text</summary><div class="rt-vorschau" style="padding:6px 0">${textHtml(p.text)}</div></details></td>
      <td class="r nw">${n2(p.menge, p.menge % 1 ? 2 : 0)} ${esc(p.einheit || "")}</td><td class="r nw">${eur(p.ep)}</td></tr>`).join("")}</table>`;
    $$("[data-pa]", box).forEach(tr => tr.onclick = ev => {
      if (ev.target.closest("details")) return;
      const id = +tr.dataset.pa, cb = $("input", tr);
      if (ev.target !== cb) cb.checked = !cb.checked;
      cb.checked ? gewaehlt.add(id) : gewaehlt.delete(id);
      knopf(hg);
    });
  };
  const knopf = hg => { const b = $("[data-x='1']", hg); b.disabled = !gewaehlt.size; b.textContent = gewaehlt.size > 1 ? `${gewaehlt.size} Positionen übernehmen` : "Übernehmen"; };
  const suchen = async hg => {
    const nr = ++laeuft, wort = $("#paSuche", hg).value.trim();
    if (!wort) { liste = []; return zeichnen(hg); }
    try { const r = await api("positionen/suche?" + new URLSearchParams({q: wort, ausser: a.id})); if (nr === laeuft) { liste = r; zeichnen(hg); } }
    catch (e) { toast(e.message, true); }
  };
  let timer;
  const d = await modal("Position aus anderem Auftrag übernehmen", inhalt, "Übernehmen", hg => {
    $(".modal", hg).style.width = "min(900px,96vw)";
    zeichnen(hg); knopf(hg);
    $("#paSuche", hg).oninput = () => { clearTimeout(timer); timer = setTimeout(() => suchen(hg), 250); };
    $("#paLos", hg).onclick = () => suchen(hg);
    $("#paSuche", hg).focus();
  });
  if (!d || !gewaehlt.size) return;
  try {
    const r = await api(`auftraege/${a.id}/uebernehmen`, {method: "POST", body: {ids: [...gewaehlt], titel: +(d.titel || 0)}});
    toast(r.ids.length > 1 ? `${r.ids.length} Positionen übernommen` : "Position übernommen");
    danach();
  } catch (e) { toast(e.message, true); }
}

// ---------------------------------------------------------------------
//  Reiter „Titel“
// ---------------------------------------------------------------------
async function titelSeite(z, a) {
  const d = await api(`auftraege/${a.id}/positionen`);
  let titel = d.titel.map(t => ({...t}));
  const anzahl = nr => d.positionen.filter(p => p.titel === nr).length;
  const zeichnen = () => {
    z.innerHTML = `
      <div class="titel"><h2>Positionstitel</h2><span class="speicher"></span></div>
      <div class="form">
        ${zeile("Druck in Belegen", `<div class="radio">${[["titel","Titel"],["summen","Titel mit Zusammenstellung der Titelsummen am Ende"],["nein","Nein"]].map(([v, l]) => `<label><input type="radio" name="td" value="${v}" ${d.titel_druck === v ? "checked" : ""}> ${l}</label>`).join("")}</div>`, true)}
      </div>
      <table class="liste" style="margin-top:10px">
        <tr><th style="width:60px">Nr</th><th>Titel</th><th style="width:110px" class="r">Positionen</th><th style="width:220px">Positionen des Titels sind</th><th style="width:150px">Zeitbuchung</th><th style="width:40px"></th></tr>
        ${titel.map((t, i) => `<tr>
          <td>T${String(t.nr).padStart(2, "0")}</td>
          <td><input data-i="${i}" data-k="name" value="${esc(t.name)}" style="width:100%"></td>
          <td class="r">${anzahl(t.nr)}</td>
          <td><label><input type="radio" name="g${i}" data-i="${i}" data-k="gesperrt" value="0" ${t.gesperrt ? "" : "checked"}> Normal</label> &nbsp;
              <label><input type="radio" name="g${i}" data-i="${i}" data-k="gesperrt" value="1" ${t.gesperrt ? "checked" : ""}> Gesperrt</label></td>
          <td><label title="Abgeschlossene Titel bieten Stempeluhr, Zeiterfassung und Stundenbuchung nicht mehr an"><input type="checkbox" data-i="${i}" data-k="buchung_gesperrt" ${t.buchung_gesperrt ? "checked" : ""}> abgeschlossen</label></td>
          <td>${anzahl(t.nr) ? "" : `<button class="btn rot" data-del="${i}" title="Titel entfernen">✕</button>`}</td></tr>`).join("")}
      </table>
      <div style="margin-top:10px"><button class="btn" id="tNeu">+ Titel hinzufügen</button></div>
      <p class="hinweis">Gesperrte Titel werden nicht in die Nettosumme gerechnet, z. B. für Varianten im Angebot. Stunden lassen sich auf Titel buchen (Reiter Stunden, Zeiterfassung, Stempeluhr); ein als „abgeschlossen“ markierter Titel wird dort nicht mehr angeboten, darauf kann nicht mehr gebucht werden.</p>`;
    const sp = speicherer(`auftraege/${a.id}/titel`);
    $$("[data-k]", z).forEach(el => el.addEventListener(el.type === "radio" || el.type === "checkbox" ? "change" : "input", () => {
      const t = titel[+el.dataset.i];
      if (el.dataset.k === "name") t.name = el.value;
      else if (el.dataset.k === "buchung_gesperrt") t.buchung_gesperrt = el.checked;
      else t.gesperrt = el.value === "1";
      sp.setze("titel", titel, el.type === "checkbox");
    }));
    $$("[name=td]", z).forEach(el => el.onchange = () => { d.titel_druck = el.value; sp.setze("titel_druck", el.value, true); });
    $("#tNeu").onclick = () => { titel.push({nr: Math.max(0, ...titel.map(t => t.nr)) + 1, name: "", gesperrt: false}); sp.setze("titel", titel, true); zeichnen(); $$("[data-k=name]", z).at(-1).focus(); };
    $$("[data-del]", z).forEach(b => b.onclick = () => { titel.splice(+b.dataset.del, 1); sp.setze("titel", titel, true); zeichnen(); });
  };
  zeichnen();
}

// ---------------------------------------------------------------------
//  Position (mit Unterreitern)
// ---------------------------------------------------------------------
async function ansichtPosition(pid, reiter = "position", sub) {
  const d = await api("positionen/" + pid);
  const p = d.position, a = d.auftrag;
  const el = d.eltern;
  const mz = (x, ein) => `${n2(x, x % 1 ? 2 : 0)} ${esc(ein)}`;
  auftragKopf(a, "positionen", {zeile2: el
    ? `<a href="#/position/${el.id}">Position ${el.posnr} · ${mz(el.menge, el.einheit)} ${esc(kurz(el.text, 60))}</a><br><span style="padding-left:18px">Unterposition ${p.posnr} · ${mz(p.menge, p.einheit)} ${esc(kurz(p.text, 60))}</span>`
    : `Position ${p.posnr} · ${mz(p.menge, p.einheit)} ${esc(kurz(p.text, 60))}`});
  // Positions-Reiter ersetzen die Auftragsreiter; eine Unterposition hat keine eigenen Unterpositionen
  const reiterPos = el ? [["Unterposition","position"],["Stückliste","werkstoffe"],["Beschläge","beschlaege"],["Zeiten","zeiten"],["Summen","summen"]]
    : [["Position","position"],["Stückliste","werkstoffe"],["Beschläge","beschlaege"],["Zeiten","zeiten"],["Summen","summen"],["Unterpositionen","unterpositionen"]];
  if (el && reiter === "unterpositionen") reiter = "position";
  $(".reiter").innerHTML = `<a class="zurueck" href="${d.eltern ? `#/position/${d.eltern.id}/unterpositionen` : `#/auftrag/${a.id}/positionen`}">← Zurück</a>`
    + reiterPos.map(([l, s]) => `<a href="#/position/${pid}/${s}" class="${s === reiter ? "aktiv" : ""}">${l}${s === "unterpositionen" && p.kinder.length ? ` (${p.kinder.length})` : ""}${s === "werkstoffe" && p.stueckliste.length ? ` (${p.stueckliste.length})` : ""}</a>`).join("")
    + (nurWerkstatt() ? "" : `<div class="r2">` + [["Werkstoffe","werkstoffe"],["Beschläge","beschlaege"],["Löhne","loehne"],["Zuschläge","zuschlaege"]].map(([l, s]) =>
      `<a class="grau${reiter === "werte" && (sub || "werkstoffe") === s ? " aktiv" : ""}" href="#/position/${pid}/werte/${s}" title="Auftragswerte (gelten für alle Positionen des Auftrags)">${l}</a>`).join("") + `</div>`);
  const z = $("#inhalt");
  // Bei Unterpositionen nur die Unterpositionen derselben Hauptposition zur Auswahl
  const wahlListe = el ? d.liste.filter(x => x.ebene && String(x.posnr).startsWith(el.posnr + ".")) : d.liste;
  const posWahl = `<select id="posWahl" style="max-width:520px">${wahlListe.map(x => `<option value="${x.id}" ${x.id === pid ? "selected" : ""}>${el ? "Unterposition " + String(x.posnr).split(".").pop() : `${x.ebene ? "   └ " : ""}${x.titel ? "T" + String(x.titel).padStart(2, "0") + " " : ""}Pos. ${x.posnr}`} · ${n2(x.menge, x.menge % 1 ? 2 : 0)} ${esc(x.einheit)} ${esc(x.text)}</option>`).join("")}</select>`;
  const ctx = {d, p, a, pid, z, posWahl, neu: () => ansichtPosition(pid, reiter, sub)};
  if (reiter === "werte") return auftragsWerte(z, {auftrag: a, teil: sub || "werkstoffe"});
  ({position: posSeite, werkstoffe: stuecklisteSeite, beschlaege: beschlagSeite, zeiten: zeitenSeite, summen: summenSeite, unterpositionen: unterSeite}[reiter] || posSeite)(ctx);
  $("#posWahl")?.addEventListener("change", e => location.hash = `#/position/${e.target.value}/${reiter}`);
}

function posKopfzeile(ctx, titel, extraKnoepfe = "", nurUnter = false) {
  const el = ctx.d.eltern, w = el ? "Unterposition" : "Position";
  // Bei Unterpositionen: Zeile mit der Hauptposition darüber
  const haupt = el ? `<a class="up-haupt" href="#/position/${el.id}/unterpositionen" title="Zur Hauptposition">
      <span class="up-nr">${esc(el.posnr)}</span><span class="r">${n2(el.menge, el.menge % 1 ? 2 : 0)}</span><span>${esc(el.einheit)}</span>
      <span class="up-text">${esc(kurz(el.text, 80))}</span><span class="hinweis">${masseText(el.masse) || ""}</span>
      <span class="hinweis">Hauptposition · ${el.kinder} Unterposition${el.kinder > 1 ? "en" : ""}</span></a>` : "";
  return `${haupt}<div class="titel"><h2>${titel}</h2>${ctx.posWahl}<span class="speicher"></span>
    <div class="rechts">${extraKnoepfe}
      ${nurUnter ? "" : `<button class="btn pk" id="pNeu" title="Neue ${w} nach dieser anlegen">${ic("neu")} Neue ${w}</button>
      <button class="btn pk" id="pKopie" title="${w} kopieren">${ic("uebernehmen")} ${w} kopieren</button>
      <button class="btn pk rot" id="pDel" title="${w} mit Kalkulation löschen">${ic("loeschen")} ${w} löschen</button>`}</div></div>`;
}
function posKopfBinden(ctx) {
  const {p, a, pid, d} = ctx;
  if (!$("#pNeu")) return;   // Reiter „Unterpositionen“: Knöpfe gelten dort den Unterpositionen
  $("#pNeu").onclick = async () => {
    const r = await api(`auftraege/${a.id}/positionen`, {method: "POST", body: {titel: p.titel, parent_id: d.eltern?.id || null, nach_id: pid}});
    location.hash = `#/position/${r.id}`;
  };
  $("#pKopie").onclick = async () => { const r = await api(`positionen/${pid}/kopieren`, {method: "POST"}); toast("Kopie angelegt"); location.hash = `#/position/${r.id}`; };
  $("#pDel").onclick = async () => {
    if (!await frage(d.eltern ? "Diese Unterposition mit Kalkulation löschen?" : "Diese Position mit Kalkulation und Unterpositionen löschen?")) return;
    await api(`positionen/${pid}`, {method: "DELETE"}); toast("Gelöscht");
    location.hash = d.eltern ? `#/position/${d.eltern.id}/unterpositionen` : `#/auftrag/${a.id}/positionen`;
  };
}

// --- Unterreiter „Position“ ---
function posSeite(ctx) {
  const {p, d, z, pid} = ctx;
  const c = p.calc;
  const chk = (k, l) => `<label class="pchk"><input type="checkbox" data-zeige="${k}" ${p.zeige[k] ? "checked" : ""}> ${l}</label>`;
  z.innerHTML = posKopfzeile(ctx, d.eltern ? "Unterposition" : "Position") + `
    <div class="form" id="f">
      ${d.eltern ? "" : zeile("Titel", `<select data-p="titel"><option value="0">(ohne Titel)</option>${d.titel.map(t => `<option value="${t.nr}" ${t.nr === p.titel ? "selected" : ""}>T${String(t.nr).padStart(2, "0")} · ${esc(t.name)}</option>`).join("")}</select>`, true)}
      ${zeile("Position ist", `<div class="radio" style="flex-wrap:wrap"><label><input type="radio" name="gesp" value="0" ${p.gesperrt ? "" : "checked"}> Normal</label><label title="Wird nicht gedruckt und nicht gerechnet"><input type="radio" name="gesp" value="1" ${p.gesperrt ? "checked" : ""}> Gesperrt</label>
        ${d.eltern ? "" : `<label title="Wird im Beleg als Alternativposition gedruckt, der Preis steht in Klammern und zählt nicht zur Summe"><input type="checkbox" id="pAlt" ${p.alternativ ? "checked" : ""}> Alternative</label>`}</div>`)}
      ${zeile("Gruppe / Status", `<select data-p="gruppe">${opts(E.positionsgruppen, p.gruppe)}</select><select data-p="status">${opts(E.positionsstatus, p.status, "– noch kein Status –")}</select>`)}
      ${zeile("Drucken", `<div class="radio" style="flex-wrap:wrap">${chk("posnr", "Posnr")}${chk("anzahl", "Anzahl")}${chk("ep", "Einzelpreis")}${chk("gp", "Gesamtpreis (zählt zur Summe)")}</div>`, true)}
      ${zeile("Anzahl / Einheit", `${numInp(p.menge, 'data-p="menge" style="width:90px;text-align:right"', p.menge % 1 ? 2 : 0)}<select data-p="einheit" style="flex:0 0 120px">${opts(E.einheiten, p.einheit)}</select>`)}
      ${zeile("Maße (mm)", `<select id="mArt" style="flex:0 0 86px" title="Maßangabe">${Object.keys(MASS_ARTEN).map(x => `<option value="${x}" ${x === (p.masse.art || "HBT") ? "selected" : ""}>${x.split("").join("*")}</option>`).join("")}</select>
        ${[...(MASS_ARTEN[p.masse.art] || "hbt")].map(x => `<span class="hinweis" style="padding-top:5px">${x.toUpperCase()}</span>${numInp(p.masse[x] || "", `data-m="${x}" style="width:72px"`, 0)}`).join("")}`)}
      <div class="zeile voll"><label>Text<br><span class="hinweis" style="font-weight:400">1. Zeile = Kurztext</span></label><div>
        ${rtEditor(p.text, 'data-p="text"', "gross")}
        <div style="display:flex;flex-direction:column;gap:4px"><button class="btn" id="tbEin" title="Textbaustein einfügen">Baustein</button><button class="btn" id="tbSp" title="Diesen Text als Baustein speichern">Speichern</button></div>
      </div></div>
      <div class="zeile voll"><label>Bilder<br><span class="hinweis" style="font-weight:400">z. B. Rendering aus dem CAD</span></label><div id="pBilder" style="display:block"></div></div>
      <div class="zeile voll"><label>Werkstattinfo<br><span class="hinweis" style="font-weight:400">nur auf dem Werkstattauftrag, nicht für den Kunden</span></label><div><textarea id="pWi" rows="3" placeholder="z. B. Front mit eingefrästem Griff, Maserung durchlaufend, Kanten vorher anfasen" style="width:100%">${esc((p.extras || {}).werkstattinfo || "")}</textarea></div></div>
      <div class="sektion">Preis</div>
      <div class="sektion" style="margin-top:4px">Kostenliste <span class="hinweis" style="font-weight:400">frei, ohne Stückliste · Beträge je Anzahl</span></div>
      <div id="klBox" style="grid-column:1/-1;width:100%;margin-bottom:8px"></div>
      <div class="zeile voll"><label>Einzelpreis</label><div style="align-items:center">
        <span class="hinweis">Kosten/Anz.${p.kinder && p.kinder.length ? " inkl. Unterpos." : ""}</span> <a href="#/position/${pid}/summen" id="vKosten">${n2(p.kinder && p.kinder.length ? c.kosten_gesamt : c.selbstkosten)}</a>
        <span style="width:16px"></span>
        ${numInp(p.preis_manuell || !c.hat_kalk ? p.einzelpreis : c.einzelpreis, 'id="ep" style="width:120px;text-align:right"')} €
        <button class="btn" id="rAb" title="Gesamten Einzelpreis auf volle Euro abrunden">,00 ↓</button>
        <button class="btn" id="rAuf" title="Gesamten Einzelpreis auf volle Euro aufrunden">,00 ↑</button>
        <span id="epArt" class="hinweis"></span>
        ${p.preis_manuell && c.hat_kalk ? `<button class="btn" id="neuBer">Preis wieder berechnen</button>` : ""}
      </div></div>
      ${p.kinder.length ? zeile("Unterpositionen", `<div class="radio" style="flex-wrap:wrap">${[["beleg","Auf Beleg (mit Preisen)"],["anzahl_text","Anzahl + Text"],["text","Nur Text"],["verdeckt","Verdeckt"]].map(([v, l]) => `<label><input type="radio" name="ud" value="${v}" ${p.unterdruck === v ? "checked" : ""}> ${l}</label>`).join("")}</div>`, true) : ""}
    </div>
    <table class="liste" id="psum" style="margin-top:14px"></table>`;
  // Übersicht mit eigenem Wagnis-und-Gewinn-Zuschlag dieser Position (bleibt beim Tippen stehen, nur die Zahlen werden neu geschrieben)
  const zeigeSumme = c => {
    const wgEingabe = $("#wgE");
    const fokus = wgEingabe && wgEingabe.matches(":focus");
    if (!fokus) $("#psum").innerHTML = `
      <tr><th>Übersicht</th><th class="r">je Anzahl</th><th class="r">Gesamt (× ${n2(p.menge, p.menge % 1 ? 2 : 0)})</th></tr>
      ${c.unter_ep ? `<tr><td>Eigener Preis / Unterpositionen</td><td class="r" id="sEig"></td><td></td></tr>` : ""}
      <tr><td>Selbstkosten${c.unter_kosten ? " inkl. Unterpositionen" : ""}</td><td class="r" id="sSk"></td><td class="r" id="sSkG"></td></tr>
      <tr><td><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">Wagnis und Gewinn
        <span style="display:inline-flex;align-items:center;gap:4px">${numInp(c.wg_pz, `id="wgE" style="width:80px;text-align:right" ${c.hat_kalk || +p.einzelpreis ? "" : 'disabled title="Erst Kosten kalkulieren (Stückliste, Beschläge, Zeiten), dann lässt sich ein Zuschlag rechnen"'}`)} %</span>
        <span class="hinweis" id="sWgInfo"></span></div></td><td class="r" id="sWg"></td><td class="r" id="sWgG"></td></tr>
      <tr><td><b>Nettopreis</b></td><td class="r"><b id="sNp"></b></td><td class="r"><b id="sNpG"></b></td></tr>`;
    const setz = (id, t) => { const el = $("#" + id); if (el) el.textContent = t; };
    setz("sEig", `${n2(c.einzelpreis)} + ${n2(c.unter_ep)}`);
    setz("sSk", n2(c.kosten_gesamt)); setz("sSkG", eur(c.kosten_gesamt * p.menge));
    setz("sWg", n2(c.ep_gesamt - c.kosten_gesamt)); setz("sWgG", eur((c.ep_gesamt - c.kosten_gesamt) * p.menge));
    setz("sNp", n2(c.ep_gesamt)); setz("sNpG", eur(c.gesamtpreis));
    setz("sWgInfo", !c.hat_kalk ? (+p.einzelpreis ? "Eingabe übernimmt den Einzelpreis als Zukauf und rechnet den Zuschlag darauf" : "ohne Kalkulation nicht möglich") : (p.preis_manuell ? "ergibt sich aus dem festen Preis · Eingabe rechnet den Preis neu" : (p.extras && p.extras.wg != null && p.extras.wg !== "" ? "eigener Zuschlag dieser Position" : `Standard des Auftrags`))
      + (c.unter_ep && c.hat_kalk ? ` · mit Unterpositionen ${n2(c.wg_gesamt_pz)} %` : ""));
    if (!fokus) { const w = $("#wgE"); if (w) w.oninput = () => {
      p.extras = p.extras || {};
      // Ohne Kalkulation: der eingetragene Einzelpreis wird einmalig zum Zukauf, W+G kommt darauf
      if (!p.calc.hat_kalk && !klZeilen().length && +p.einzelpreis) { klSetze([{art: "zukauf", text: "", menge: 1, einheit: "Stk.", preis: +p.einzelpreis}], false); klZeichnen(); }
      p.extras.wg = zahlEin(w.value); p.preis_manuell = 0;
      sp.setze("extras", p.extras); sp.setze("preis_manuell", 0);
    }; }
    $("#vKosten").textContent = n2(p.kinder && p.kinder.length ? c.kosten_gesamt : c.selbstkosten);
    $("#epArt").textContent = p.preis_manuell || !c.hat_kalk ? (c.hat_kalk ? "fester Preis" : "") : "berechnet";
  };
  // Freie Kostenliste (wie die Werkstoffliste): Kostenart, Beschreibung, Menge, Einheit, Preis je Einheit
  const KL_ARTEN = [["werkstoffe", "Werkstoffe"], ["fremdleistungen", "Fremdleistung"], ["zukauf", "Zukauf"], ["sonder_fertigung", "Soko Fertigung"], ["sonder_vertrieb", "Soko Vertrieb"]];
  const KL_BSP = {werkstoffe: "z. B. Arbeitsplatte Eiche 40 mm", fremdleistungen: "z. B. Pulverbeschichtung, Glaszuschnitt, Elektriker", zukauf: "z. B. Hochschrank Fa. …, Kühlschrank",
    sonder_fertigung: "z. B. Kranmiete, Container, Auslösung, Km-Geld", sonder_vertrieb: "z. B. Provision, Verpackung, Versand"};
  const klZeilen = () => klAusExtras(p.extras);
  const klSetze = (zeilen, preisNeu = true) => {
    const ex = {...(p.extras || {}), kostenliste: zeilen};
    KL_ALT.forEach(k => { delete ex[k]; delete ex[k + "_text"]; });
    p.extras = ex; sp.setze("extras", ex);
    if (preisNeu) { p.preis_manuell = 0; sp.setze("preis_manuell", 0); }
  };
  const klZeichnen = () => {
    const zl = klZeilen();
    const summe = zl.reduce((a, x) => a + klBetrag(x), 0);
    $("#klBox").innerHTML = (zl.length ? `<table class="liste kl" style="margin:0 0 6px;width:100%"><tr><th style="width:160px">Kostenart</th><th>Beschreibung</th><th class="r" style="width:84px">Menge</th><th style="width:106px">Einheit</th><th class="r" style="width:104px">Preis/Einh.</th><th class="r nw" style="width:100px">Betrag</th><th style="width:34px"></th></tr>
      ${zl.map((x, i) => `<tr><td><select data-kl="art" data-i="${i}">${KL_ARTEN.map(([k, l]) => `<option value="${k}" ${k === (x.art || "werkstoffe") ? "selected" : ""}>${l}</option>`).join("")}</select></td>
        <td><input data-kl="text" data-i="${i}" value="${esc(x.text || "")}" placeholder="${KL_BSP[x.art] || KL_BSP.werkstoffe}" style="width:100%"></td>
        <td class="r">${numInp(x.menge == null || x.menge === "" ? 1 : x.menge, `data-kl="menge" data-i="${i}" style="width:74px;text-align:right"`, Math.round((+x.menge || 0) * 100) === (+x.menge || 0) * 100 ? 2 : 3)}</td>
        <td><select data-kl="einheit" data-i="${i}" style="width:100px">${opts(E.einheiten, x.einheit || "", "(keine)")}</select></td>
        <td class="r">${numInp(x.preis || 0, `data-kl="preis" data-i="${i}" style="width:90px;text-align:right"`)}</td>
        <td class="r nw" data-klb="${i}">${n2(klBetrag(x))}</td><td><button class="btn klein" data-klweg="${i}" title="Zeile entfernen">✕</button></td></tr>`).join("")}
      <tr><td colspan="5" class="r"><b>Summe</b></td><td class="r nw"><b id="klSum">${n2(summe)}</b></td><td></td></tr></table>` : "")
      + `<button class="btn" id="klNeu">+ Kostenzeile</button> <span class="hinweis">Werkstoffe mit Kleinmaterial und Material-GK, Fremdleistungen und Zukauf mit Material-GK, Sonderkosten Fertigung ohne GK; auf diese kommt Wagnis und Gewinn. Sonderkosten Vertrieb kommen nach Wagnis und Gewinn dazu.</span>`;
    $("#klNeu").onclick = () => { klSetze([...zl, {art: "zukauf", text: "", menge: 1, einheit: "Stk.", preis: 0}], false); klZeichnen(); $(`[data-kl="text"][data-i="${zl.length}"]`)?.focus(); };
    $$("[data-klweg]", $("#klBox")).forEach(b => b.onclick = () => { const n = klZeilen(); n.splice(+b.dataset.klweg, 1); klSetze(n); klZeichnen(); });
    $$("[data-kl]", $("#klBox")).forEach(el => el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
      const n = klZeilen().map(x => ({...x})), i = +el.dataset.i, k = el.dataset.kl;
      n[i][k] = ["menge", "preis"].includes(k) ? zahlEin(el.value) : el.value;
      const zahl = ["menge", "preis", "art"].includes(k);
      klSetze(n, zahl);
      if (zahl) { $(`[data-klb="${i}"]`).textContent = n2(klBetrag(n[i])); $("#klSum").textContent = n2(n.reduce((a, x) => a + klBetrag(x), 0)); }
      if (k === "art") { const t = $(`[data-kl="text"][data-i="${i}"]`); t.placeholder = KL_BSP[n[i].art] || KL_BSP.werkstoffe; }
    }));
    $$("[data-kl=text]", $("#klBox")).forEach(el => el.addEventListener("keydown", e => e.stopPropagation()));
  };
  let sp;
  zeigeSumme(c);
  sp = speicherer("positionen/" + pid, r => { if (sp.offen()) { p.calc = r.position.calc; zeigeSumme(p.calc); return; } Object.assign(p, r.position); zeigeSumme(r.position.calc); if (!$("#ep").matches(":focus")) $("#ep").value = n2(p.preis_manuell || !p.calc.hat_kalk ? p.einzelpreis : p.calc.einzelpreis); });
  $$("[data-p]", z).forEach(el => el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
    let v = el.isContentEditable ? el.innerHTML : el.value;
    if (el.dataset.p === "menge") v = zahlEin(v);
    if (el.dataset.p === "titel") v = +v;
    p[el.dataset.p] = v; sp.setze(el.dataset.p, v, el.tagName === "SELECT");
  }));
  $$("[data-zeige]", z).forEach(el => el.onchange = () => { p.zeige[el.dataset.zeige] = el.checked ? 1 : 0; sp.setze("zeige", p.zeige, true); });
  $$("[data-m]", z).forEach(el => el.oninput = () => { p.masse[el.dataset.m] = zahlEin(el.value); sp.setze("masse", p.masse); });
  $$("[name=gesp]", z).forEach(el => el.onchange = () => sp.setze("gesperrt", +el.value, true));
  $("#pWi").addEventListener("input", e => { p.extras = {...(p.extras || {}), werkstattinfo: e.target.value}; sp.setze("extras", p.extras); });
  $("#pWi").addEventListener("keydown", e => e.stopPropagation());
  const alt = $("#pAlt"); if (alt) alt.onchange = () => { p.alternativ = alt.checked ? 1 : 0; sp.setze("alternativ", p.alternativ, true); };
  // Maßart wechseln: die eingegebenen Werte bleiben an ihrer Stelle (1. Feld bleibt 1. Feld)
  $("#mArt").onchange = async e => {
    const alt = [...(MASS_ARTEN[p.masse.art] || "hbt")], neu = [...MASS_ARTEN[e.target.value]];
    const m = {art: e.target.value}; neu.forEach((x, i) => { if (p.masse[alt[i]]) m[x] = p.masse[alt[i]]; });
    p.masse = m; sp.setze("masse", m, true); await sp.senden(); posSeite(ctx);
  };
  $$("[name=ud]", z).forEach(el => el.onchange = () => sp.setze("unterdruck", el.value, true));
  bilderBereich(ctx, sp);
  klZeichnen();
  $("#ep").oninput = e => { p.preis_manuell = 1; p.einzelpreis = zahlEin(e.target.value) - (p.calc.unter_ep || 0) * 0; sp.setze("einzelpreis", zahlEin(e.target.value)); sp.setze("preis_manuell", 1); };
  const runden = async modus => { await sp.senden(); const r = await api(`positionen/${pid}/runden`, {method: "POST", body: {modus}}); Object.assign(p, r.position); posSeite(Object.assign(ctx, {p: r.position})); };
  $("#rAb").onclick = () => runden("ab"); $("#rAuf").onclick = () => runden("auf");
  const nb = $("#neuBer"); if (nb) nb.onclick = async () => { const r = await api(`positionen/${pid}/berechnen`, {method: "POST"}); posSeite(Object.assign(ctx, {p: r.position})); };
  $("#tbEin").onclick = async () => {
    const tb = await textbausteinWaehlen(); if (!tb) return;
    const t = $("[data-p=text]");
    t.focus();
    if (rtAuswahl && t.contains(rtAuswahl.commonAncestorContainer)) { const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(rtAuswahl); }
    else { const r = document.createRange(); r.selectNodeContents(t); r.collapse(false); const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r); }
    document.execCommand("insertHTML", false, (t.textContent.trim() ? "<br>" : "") + textHtml(tb.text));
    t.dispatchEvent(new Event("input", {bubbles: true}));
  };
  $("#tbSp").onclick = async () => {
    const r = await modal("Als Textbaustein speichern", `<div class="zeile"><label>Name</label><div><input name="name" value="${esc(kurz(p.text, 40))}"></div></div>`, "Speichern");
    if (!r || !r.name.trim()) return;
    const tb = [...(E.textbausteine || []).filter(t => t.name !== r.name.trim()), {name: r.name.trim(), text: $("[data-p=text]").innerHTML}];
    E = {...E, ...(await api("einstellungen", {method: "PUT", body: {textbausteine: tb}}))};
    toast("Textbaustein gespeichert");
  };
  posKopfBinden(ctx);
}

// --- Unterreiter „Werkstoffe“ (Stückliste) ---
function stuecklisteSeite(ctx) {
  const {p, d, z, pid} = ctx;
  const wks = d.kalk.werkstoffe;
  const nach = typ => wks.filter(w => typ.includes(w.typ));
  const wOpt = (liste, wert, leer = "—") => `<option value="">${leer}</option>` + liste.map(w => `<option value="${w.k}" ${w.k === wert ? "selected" : ""}>${w.k} ${esc(w.name || "")}${(w.fdicke || w.dicke) ? " " + n2(w.fdicke || w.dicke, 1) : ""}</option>`).join("")
    + `<option value="__neu">+ aus dem Materialstamm …</option>`;
  let offen = null;
  const teile = p.stueckliste;
  const eigeneTeil = Object.entries(d.bezug || {}).filter(([k, v]) => k.startsWith("x_") && (v[2] || "teil") === "teil").map(([k, v]) => [k, v[0], v[1]]);
  const sp = speicherer("positionen/" + pid, r => { p.calc = r.position.calc; zeichneKosten(); });
  const merk = (o, k) => o && o[k];
  const kantenAnz = t => ["oben", "unten", "links", "rechts"].filter(s => merk(t.kanten, s));
  const symbol = t => {
    const k = kantenAnz(t), fu = ["oben", "unten"].filter(s => merk(t.furnier, s)).length, of = ["oben", "unten"].filter(s => merk(t.oberflaeche, s)).length;
    const fr = ["oben", "unten", "links", "rechts"].filter(s => merk(t.fraesen, s)).length;
    const vb = +((t.verbinden || {}).anzahl) || ["oben", "unten"].filter(s => merk(t.verbinden, s)).length;
    return [k.length ? `<span class="tag">K ${k.length === 4 ? "rundum" : k.map(s => s[0].toUpperCase()).join("")}</span>` : "",
      fu ? `<span class="tag">F ${fu}×</span>` : "", of ? `<span class="tag">O ${of}×</span>` : "",
      fr ? `<span class="tag">Fr ${fr}</span>` : "", vb ? `<span class="tag">V ${vb}×</span>` : "", +t.bohren ? `<span class="tag">B ${t.bohren}×</span>` : "",
      +t.taschen ? `<span class="tag">T ${t.taschen}×${+t.tasche_l && +t.tasche_b ? ` ${n2(t.tasche_l, 0)}×${n2(t.tasche_b, 0)}${+t.tasche_t ? "×" + n2(t.tasche_t, 1).replace(/,0$/, "") : ""}` : ""}</span>` : "", +t.gehrung ? `<span class="tag">G ${t.gehrung}×</span>` : ""].join("");
  };
  const zeichneKosten = () => {
    $$("[data-kost]", z).forEach(el => { const t = p.calc.teile[+el.dataset.kost]; el.textContent = t ? n2(t.kosten) : ""; });
    const c = p.calc;
    $("#slSum").innerHTML = `Werkstoffe <b>${eur(c.werkstoffe)}</b> · Oberfläche <b>${eur(c.oberflaeche)}</b> je Anzahl · Platte ${n2(c.bezug.platte, 2)} m²${c.massiv_m3 ? ` · Massivholz ${n2(c.massiv_m3, 3)} m³ (Rohdicke)` : ""} · Kante ${n2(c.bezug.kante, 2)} lfm · Furnier ${n2(c.bezug.furnier, 2)} m² · Oberfläche ${n2(c.bezug.oberflaeche, 2)} m²`;
  };
  const speichern = (sofort) => sp.setze("stueckliste", teile, sofort);
  const editor = (t, i) => {
    const kSel = s => `<select data-t="kanten.${s}">${wOpt(nach(["kante"]), merk(t.kanten, s))}</select>`;
    const sSel = (gruppe, s, typ) => `<select data-t="${gruppe}.${s}">${wOpt(nach([typ]), merk(t[gruppe], s))}</select>`;
    const cb = (gruppe, s, l) => `<label><input type="checkbox" data-c="${gruppe}.${s}" ${merk(t[gruppe], s) ? "checked" : ""}> ${l}</label>`;
    return `<tr class="sl-edit"><td colspan="10"><div class="form" style="grid-template-columns:1fr 1fr">
      ${zeile("Werkstoff", `<select data-t="werkstoff">${wOpt(nach(["platte", "massiv", "sonstig"]), t.werkstoff, "— wählen —")}</select>`)}
      ${zeile("Verwendung", `<input data-t="verwendung" value="${esc(t.verwendung || "")}">`)}
      ${zeile("Stück", numInp(t.stueck, 'data-t="stueck" style="width:90px"', 0))}
      ${zeile("Länge × Breite", `${numInp(t.laenge, 'data-t="laenge" style="width:110px"', 1)} × ${numInp(t.breite, 'data-t="breite" style="width:110px"', 1)} mm`)}
      ${zeile("Kante oben", kSel("oben"))}${zeile("Kante unten", kSel("unten"))}
      ${zeile("Kante links", kSel("links"))}${zeile("Kante rechts", kSel("rechts"))}
      ${zeile("Furnier oben", sSel("furnier", "oben", "furnier"))}${zeile("Furnier unten", sSel("furnier", "unten", "furnier"))}
      ${zeile("Oberfl. oben", sSel("oberflaeche", "oben", "oberflaeche"))}${zeile("Oberfl. unten", sSel("oberflaeche", "unten", "oberflaeche"))}
      ${zeile("Fräsen", `<div class="radio">${cb("fraesen", "links", "links")}${cb("fraesen", "rechts", "rechts")}${cb("fraesen", "oben", "oben")}${cb("fraesen", "unten", "unten")}</div>`)}
      ${zeile("Verbinden", `<div class="spalte"><label style="display:flex;gap:6px;align-items:center">Anzahl ${numInp((t.verbinden || {}).anzahl || "", 'data-n="verbinden.anzahl" style="width:70px"', 0)}</label>
        <div class="radio">${LAGEN.map(([s, l]) => cb("verbinden", s, l)).join("")}</div></div>`)}
      ${zeile("Bohren", `<div class="spalte"><label style="display:flex;gap:6px;align-items:center">Anzahl ${numInp(t.bohren || "", 'data-n="bohren" style="width:70px"', 0)}</label>
        <div class="radio">${LAGEN.map(([s, l]) => cb("bohren_lage", s, l)).join("")}</div></div>`)}
      ${zeile("Tasche fräsen", `<div class="spalte"><label style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">Anzahl ${numInp(t.taschen || "", 'data-n="taschen" style="width:60px"', 0)}
        Größe ${numInp(t.tasche_l || "", 'data-n="tasche_l" style="width:70px" placeholder="Länge"', 0)} × ${numInp(t.tasche_b || "", 'data-n="tasche_b" style="width:70px" placeholder="Breite"', 0)} mm,
        Tiefe ${numInp(t.tasche_t || "", 'data-n="tasche_t" style="width:60px" placeholder="durch"', 1)} mm</label>
        <span class="hinweis">Taschen und Ausschnitte (Spüle, Kochfeld, Griffmulde …), Größe je Tasche; Tiefe leer = durchgehender Ausschnitt. Bezugsgrößen: St., lfm Umfang, m² Fläche.</span></div>`)}
      ${zeile("Gehrung", `<label style="display:flex;gap:6px;align-items:center">Anzahl ${numInp(t.gehrung || "", 'data-n="gehrung" style="width:70px"', 0)}<span class="hinweis">Gehrungsschnitte am Teil</span></label>`)}
      ${eigeneTeil.map(([k, l, e]) => zeile(esc(l), `<label style="display:flex;gap:6px;align-items:center">${numInp(((t.bezug_eigen || {})[k.slice(2)]) || "", `data-n="bezug_eigen.${k.slice(2)}" style="width:80px"`, 2)} ${esc(e)}</label>`)).join("")}
      ${zeile("Bemerkung", `<input data-t="bemerkung" value="${esc(t.bemerkung || "")}">`)}
      <div class="zeile voll"><label></label><div><button class="btn" data-alle="${i}">Kanten/Furnier/Oberfläche wie Teil davor</button><button class="btn" data-zu="1">Schließen</button></div></div>
    </div><p class="hinweis" style="margin:4px 0 0">Kante oben/unten läuft entlang der Länge, links/rechts entlang der Breite.</p></td></tr>`;
  };
  const zeichnen = () => {
    z.innerHTML = posKopfzeile(ctx, "Stückliste") + `
      ${wks.some(w => w.name || w.preis) ? "" : `<div class="leer" style="margin-bottom:10px">Für diesen Auftrag sind noch keine Werkstoffe hinterlegt. <a href="#/position/${ctx.pid}/werte/werkstoffe">Auftragswerkstoffe eintragen</a> (Platten, Kanten, Furnier, Oberfläche mit Preis und Verschnitt).</div>`}
      <table class="liste sl">
        <tr><th>Nr</th><th>Werkstoff</th><th>Verwendung</th><th class="r">Stück</th><th class="r">Länge</th><th class="r">Breite</th><th class="r">Dicke</th><th>Bearbeitung</th><th class="r">Kosten/St</th><th></th></tr>
        ${teile.map((t, i) => `<tr class="klick sl-z${offen === i ? " gew" : ""}" data-i="${i}">
          <td>${String(i + 1).padStart(3, "0")}</td><td>${esc(t.werkstoff || "—")}</td><td>${esc(t.verwendung || "")}</td>
          <td class="r">${n2(t.stueck, 0)}</td><td class="r">${n2(t.laenge, 1)}</td><td class="r">${n2(t.breite, 1)}</td>
          <td class="r">${n2(p.calc.teile[i]?.dicke || 0, 1)}</td><td>${symbol(t)}</td><td class="r" data-kost="${i}"></td>
          <td class="r" style="white-space:nowrap"><button class="btn" data-kop="${i}" title="Teil kopieren">⧉</button><button class="btn rot" data-del="${i}" title="Teil löschen">✕</button></td></tr>
          ${offen === i ? editor(t, i) : ""}`).join("")}
      </table>
      ${teile.length ? "" : `<div class="leer">Noch keine Teile.</div>`}
      <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap"><button class="btn prim" id="tNeu">+ Teil</button>${(p.extras || {}).vorlage ? `<button class="btn prim" id="tVorlage" title="Maße der Vorlage ändern und Stückliste neu berechnen">Maße ändern (${esc(p.extras.vorlage.name || "Vorlage")}) …</button>` : `<button class="btn" id="tVorlage" title="Stückliste aus einer Positionsvorlage berechnen">Aus Vorlage …</button>`}<button class="btn" id="tAlsVorlage" title="Diese Position als variable Vorlage speichern">Als Vorlage speichern …</button><button class="btn" id="tCsv" title="Stückliste aus dem CAD übernehmen: neueste Datei im CAD-Ordner des Projekts, eine andere Datei oder Zwischenablage">CAD-Import …</button></div>
      <div class="hinweis" id="slSum" style="margin-top:10px"></div>`;
    zeichneKosten();
    $$(".sl-z", z).forEach(tr => tr.onclick = ev => {
      if (ev.target.closest("button")) return;
      offen = offen === +tr.dataset.i ? null : +tr.dataset.i; zeichnen();
    });
    $$("[data-del]", z).forEach(b => b.onclick = () => { teile.splice(+b.dataset.del, 1); offen = null; speichern(true); zeichnen(); });
    $$("[data-kop]", z).forEach(b => b.onclick = () => { const i = +b.dataset.kop; teile.splice(i + 1, 0, JSON.parse(JSON.stringify(teile[i]))); offen = i + 1; speichern(true); zeichnen(); });
    $("#tNeu").onclick = () => {
      const v = teile.at(-1);
      teile.push(v ? {...JSON.parse(JSON.stringify(v)), verwendung: "", stueck: 1, laenge: 0, breite: 0, bemerkung: ""} : {werkstoff: nach(["platte"])[0]?.k || "", verwendung: "", stueck: 1, laenge: 0, breite: 0});
      offen = teile.length - 1; speichern(true); zeichnen(); $("[data-t=verwendung]", z)?.focus();
    };
    $("#tCsv").onclick = () => stuecklistenImport(ctx, {konstruktion: true});
    $("#tVorlage").onclick = () => { const vl = (p.extras || {}).vorlage; vorlageDialog({pid: ctx.pid, vorlageId: vl && vl.id, werte: vl && vl.werte, nachher: () => ansichtPosition(ctx.pid, "werkstoffe")}); };
    $("#tAlsVorlage").onclick = () => alsVorlageSpeichern(ctx.pid, p.text);
    if (offen !== null) {
      const t = teile[offen], ed = $(".sl-edit", z);
      const setze = (pfad, v) => { const [g, s] = pfad.split("."); if (s) { t[g] = {...(t[g] || {})}; t[g][s] = v; } else t[g] = v; speichern(); };
      $$("[data-t]", ed).forEach(el => el.addEventListener(el.tagName === "SELECT" ? "change" : "input", async () => {
        if (el.value === "__neu") {
          const feld = el.dataset.t.split(".")[0];
          const kats = {werkstoff: ["holzwerkstoffe", "massivholz", "artikel"], kanten: ["holzwerkstoffe"], furnier: ["holzwerkstoffe"], oberflaeche: ["beschichtung", "chemie"]}[feld];
          const m = await materialWaehlen(kats, "Material für den Auftrag wählen");
          if (!m) { el.value = ""; return; }
          const r = materialInKalk(d.kalk, m, {kanten: "kante", furnier: "furnier", oberflaeche: "oberflaeche"}[feld] || null);
          try { await api(`auftraege/${ctx.a.id}/kalk`, {method: "PUT", body: {werkstoffe: d.kalk.werkstoffe}}); } catch (x) { toast(x.message, true); return; }
          setze(el.dataset.t, r.k); speichern(true); zeichnen(); toast(`${m.nummer} als ${r.k} in den Auftrag übernommen`);
          return;
        }
        const k = el.dataset.t; setze(k, ["stueck", "laenge", "breite"].includes(k) ? zahlEin(el.value) : el.value);
        if (el.tagName === "SELECT" || k === "verwendung") { const zl = $(`.sl-z[data-i="${offen}"]`, z); zl.children[1].textContent = t.werkstoff || "—"; zl.children[2].textContent = t.verwendung || ""; zl.children[7].innerHTML = symbol(t); }
        else { const zl = $(`.sl-z[data-i="${offen}"]`, z); zl.children[3].textContent = n2(t.stueck, 0); zl.children[4].textContent = n2(t.laenge, 1); zl.children[5].textContent = n2(t.breite, 1); }
      }));
      $$("[data-c]", ed).forEach(el => el.onchange = () => { setze(el.dataset.c, el.checked ? 1 : 0); $(`.sl-z[data-i="${offen}"]`, z).children[7].innerHTML = symbol(t); });
      $$("[data-n]", ed).forEach(el => el.addEventListener("input", () => { setze(el.dataset.n, zahlEin(el.value)); $(`.sl-z[data-i="${offen}"]`, z).children[7].innerHTML = symbol(t); }));
      $("[data-zu]", ed).onclick = () => { offen = null; zeichnen(); };
      $("[data-alle]", ed).onclick = () => {
        const v = teile[offen - 1]; if (!v) return toast("Kein Teil davor.", true);
        for (const g of ["kanten", "furnier", "oberflaeche", "fraesen", "verbinden", "bohren_lage"]) t[g] = JSON.parse(JSON.stringify(v[g] || {}));
        t.werkstoff = v.werkstoff; speichern(true); zeichnen();
      };
    }
    posKopfBinden(ctx);
  };
  zeichnen();
}

// --- Unterreiter „Beschläge“ ---
function beschlagSeite(ctx) {
  const {p, d, z, pid} = ctx;
  const bss = d.kalk.beschlaege;
  const zeilen = p.beschlaege;
  const sp = speicherer("positionen/" + pid, r => { p.calc = r.position.calc; kosten(); });
  const kosten = () => {
    p.calc.beschlagzeilen.forEach((b, i) => { const zl = $(`[data-bz="${i}"]`, z); if (zl) { zl.children[3].textContent = b.einheit || ""; zl.children[4].textContent = n2(b.kosten_me); zl.children[5].textContent = n2(b.gesamt); } });
    $("#bsSum").textContent = eur(p.calc.beschlaege);
  };
  const zeichnen = () => {
    z.innerHTML = posKopfzeile(ctx, "Beschlägeliste") + `
      ${bss.some(b => b.name || b.preis) ? "" : `<div class="leer" style="margin-bottom:10px">Noch keine Auftragsbeschläge hinterlegt. <a href="#/position/${ctx.pid}/werte/beschlaege">Auftragsbeschläge eintragen</a></div>`}
      <table class="liste">
        <tr><th style="width:44px">Nr</th><th>Beschlag</th><th>Bemerkung</th><th>Me</th><th class="r">Kosten/Me</th><th class="r">Gesamt</th><th style="width:110px" class="r">Menge</th><th></th></tr>
        ${zeilen.map((b, i) => `<tr data-bz="${i}"><td>${String(i + 1).padStart(3, "0")}</td>
          <td><select data-b="k" data-i="${i}" style="width:100%"><option value="">— wählen —</option>${bss.map(s => `<option value="${s.k}" ${s.k === b.k ? "selected" : ""}>${s.k} ${esc(s.artnr || "")} ${esc(s.name || "")}</option>`).join("")}</select></td>
          <td><input data-b="bemerkung" data-i="${i}" value="${esc(b.bemerkung || "")}" style="width:100%"></td>
          <td></td><td class="r"></td><td class="r"></td>
          <td class="r">${numInp(b.menge, `data-b="menge" data-i="${i}" style="width:90px;text-align:right"`)}</td>
          <td><button class="btn rot" data-del="${i}">✕</button></td></tr>`).join("")}
        <tr><td colspan="5"><b>Summe Beschläge je Anzahl</b></td><td class="r"><b id="bsSum"></b></td><td colspan="2"></td></tr>
      </table>
      <div style="margin-top:10px"><button class="btn prim" id="bNeu">+ Beschlag</button></div>`;
    kosten();
    $$("[data-b]", z).forEach(el => el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
      const b = zeilen[+el.dataset.i]; b[el.dataset.b] = el.dataset.b === "menge" ? zahlEin(el.value) : el.value; sp.setze("beschlaege", zeilen, el.tagName === "SELECT");
    }));
    $$("[data-del]", z).forEach(b => b.onclick = () => { zeilen.splice(+b.dataset.del, 1); sp.setze("beschlaege", zeilen, true); zeichnen(); });
    $("#bNeu").onclick = () => { zeilen.push({k: "", menge: 1, bemerkung: ""}); sp.setze("beschlaege", zeilen, true); zeichnen(); };
    posKopfBinden(ctx);
  };
  zeichnen();
}

const LAGEN = [["oben", "oben"], ["unten", "unten"], ["vorn", "vorn"], ["hinten", "hinten"], ["mitte", "Mitte"]];

// --- Unterreiter „Zeiten“ ---
function zeitenSeite(ctx) {
  const {p, d, z, pid} = ctx;
  const ksts = d.kalk.kostenstellen.map(k => k.kst);
  const gruppen = d.kalk.loehne.map(l => l.gruppe);
  const zeilen = p.zeiten;
  const sp = speicherer("positionen/" + pid, r => { p.calc = r.position.calc; werte(); });
  const bezugOpt = w => Object.entries(d.bezug).map(([k, [l, e]]) => `<option value="${k}" ${k === (w || "") ? "selected" : ""}>${l}${e && !l.includes(" - ") ? " (" + e + ")" : ""}</option>`).join("");
  const zeileH = (tr, i) => { const c = tr && tr.cells[4]; if (c && p.zeitmodus === "stunden") { c.className = "r zpos"; c.textContent = n2((+zeilen[i].stunden || 0) * (+p.menge || 0)) + " h"; } };
  const werte = () => {
    const c = p.calc;
    c.zeitzeilen.forEach((x, i) => { const zl = $(`[data-zz="${i}"]`, z); if (!zl) return; const m = $(".zmenge", zl), ma = $(".zmin", zl), h = $(".zh", zl), hp = $(".zhp", zl);
      if (hp) { hp.innerHTML = `<b>${n2(x.h_pos)}</b>`; hp.title = `Bearbeitung ${n2(x.h_anz * (+p.menge || 0))} h + Rüstzeit ${n2(x.ruest_h)} h + Helfer ${n2(x.helfer_h)} h`; }
      if (m) m.textContent = x.menge == null ? "" : n2(x.menge); if (ma) ma.textContent = n2(x.min_anz); if (h) h.textContent = n2(x.h_anz);
      zl.style.background = x.bezug_fehlt ? "#fde8e4" : ""; zl.title = x.bezug_fehlt ? "Diese Bezugsgröße gibt es nicht mehr – bitte eine andere wählen" : ""; });
    if ($("#zWarn", z)) $("#zWarn", z).innerHTML = kalkWarnHtml(c);
    const s = c.zeit_summen;
    $("#zSum").innerHTML = p.zeitmodus === "stunden"
      ? `<tr><th>Summe</th><th class="r">Stunden/Anzahl</th><th class="r">Stunden Position</th></tr><tr><td></td><td class="r">${n2(s.bearbeitung)} h</td><td class="r">${n2(s.bearbeitung * p.menge)} h</td></tr>`
      : `<tr><th>Summen</th><th class="r">Bearbeitungszeit</th><th class="r">Rüstzeit</th><th class="r">Helferzeit</th><th class="r">Gesamtzeit</th></tr>
         <tr><td>Stunden/Anzahl</td><td class="r">${n2(s.bearbeitung)} h</td><td class="r">${n2(p.menge ? s.ruest / p.menge : 0)} h</td><td class="r">${n2(s.helfer)} h</td><td class="r">${n2(s.bearbeitung + s.helfer + (p.menge ? s.ruest / p.menge : 0))} h</td></tr>
         <tr><td>Stunden Position</td><td class="r">${n2(s.bearbeitung * p.menge)} h</td><td class="r">${n2(s.ruest)} h</td><td class="r">${n2(s.helfer * p.menge)} h</td><td class="r"><b>${n2(s.gesamt_pos)} h</b></td></tr>`;
  };
  // Stunden direkt: immer alle Kostenstellen des Auftrags als Zeilen zeigen.
  // Leere Kostenstellen sind nur Platzhalter und werden erst gespeichert, wenn Stunden eingetragen sind.
  const gruppeSel = (attr, wert) => `<select ${attr}><option value="">Standard</option>${gruppen.map(g => `<option ${g === wert ? "selected" : ""}>${g}</option>`).join("")}</select>`;
  const stundenZeilen = () => {
    const reihen = [];
    const alle = [...ksts, ...[...new Set(zeilen.map(x => x.kst))].filter(x => !ksts.includes(x))];
    for (const kst of alle) {
      const echte = zeilen.map((x, i) => [x, i]).filter(([x]) => x.kst === kst);
      if (!echte.length) {
        reihen.push(`<tr class="zt-leer"><td><b>${esc(kst)}</b></td><td><input data-v="${esc(kst)}" data-vz="name" style="width:100%;min-width:140px"></td>
          <td>${gruppeSel(`data-v="${esc(kst)}" data-vz="gruppe"`, "")}</td>
          <td class="r">${numInp(0, `data-v="${esc(kst)}" data-vz="stunden" style="width:80px"`)}</td><td class="r hinweis">0,00 h</td><td></td></tr>`);
        continue;
      }
      echte.forEach(([x, i], n) => reihen.push(`<tr data-zz="${i}"><td>${n ? "" : `<b>${esc(kst)}</b>`}${ksts.includes(kst) ? "" : ` <span class="hinweis">(nicht in den Auftragswerten)</span>`}</td>
        <td><input data-z="name" data-i="${i}" value="${esc(x.name || "")}" style="width:100%;min-width:140px"></td>
        <td>${gruppeSel(`data-z="gruppe" data-i="${i}"`, x.gruppe)}</td>
        <td class="r">${numInp(x.stunden, `data-z="stunden" data-i="${i}" style="width:80px"`)}</td>
        <td class="r zpos">${n2((+x.stunden || 0) * (+p.menge || 0))} h</td>
        <td class="nw">${n ? "" : `<button class="btn" data-plus="${esc(kst)}" title="Weitere Zeile für ${esc(kst)}, z. B. andere Lohngruppe">+</button>`}${echte.length > 1 || x.name || x.gruppe ? `<button class="btn rot" data-del="${i}" title="Zeile entfernen">✕</button>` : ""}</td></tr>`));
    }
    return reihen.join("");
  };
  const zeichnen = () => {
    const std = p.zeitmodus === "stunden";
    const posBezug = Object.entries(d.bezug || {}).filter(([k, v]) => k.startsWith("x_") && v[2] === "position");
    z.innerHTML = posKopfzeile(ctx, "Zeiten") + `
      ${!std && posBezug.length ? `<div class="form" style="margin-bottom:10px">${posBezug.map(([k, v]) => zeile(esc(v[0]), `<label style="display:flex;gap:6px;align-items:center">${numInp(((p.extras || {}).bezug_eigen || {})[k.slice(2)] || "", `data-pb="${k.slice(2)}" style="width:90px"`, 2)} ${esc(v[1] || "")} je Anzahl</label>`)).join("")}</div>` : ""}
      <div class="radio" style="margin-bottom:10px"><label><input type="radio" name="zm" value="stunden" ${std ? "checked" : ""}> <b>Stunden</b> direkt eingeben</label><label><input type="radio" name="zm" value="taetigkeiten" ${std ? "" : "checked"}> <b>Tätigkeiten</b> mit Bezugsgrößen aus der Stückliste</label></div>
      <div style="overflow-x:auto"><table class="liste zt">
        ${std ? `<tr><th>Kostenstelle</th><th>Tätigkeit / Notiz</th><th>Lohngruppe</th><th class="r">Stunden/Anz.</th><th class="r">Stunden Position</th><th></th></tr>`
              : `<tr><th>Nr</th><th>Kostenstelle</th><th>Tätigkeit</th><th>Lohngruppe</th><th class="r">Minuten</th><th>Bezugsgröße</th><th class="r">Menge</th>
                 <th class="r nw"><label title="Rüstzeiten aller Zeilen ein-/ausschalten"><input type="checkbox" id="zAlleR" ${zeilen.some(x => !x.ruest_aus) ? "checked" : ""}> Rüstzeit</label></th>
                 <th class="r nw"><label title="Helfer aller Zeilen ein-/ausschalten"><input type="checkbox" id="zAlleH" ${zeilen.some(x => !x.helfer_aus) ? "checked" : ""}> Helfer</label></th><th class="r">Min/Anz</th><th class="r">h/Anz</th><th class="r" title="Bearbeitung × Anzahl + Rüstzeit + Helfer">h Pos.</th><th></th></tr>`}
        ${std ? stundenZeilen() : zeilen.map((x, i) => `<tr data-zz="${i}"><td>${String(i + 1).padStart(3, "0")}</td>
          <td><b>${esc(x.kst || "")}</b>${x.kst && !ksts.includes(x.kst) ? ` <span class="hinweis">(nicht in den Auftragswerten)</span>` : ""}</td>
          <td title="Tätigkeiten werden in den Einstellungen festgelegt">${esc(x.name || "")}</td>
          <td><select data-z="gruppe" data-i="${i}"><option value="">Standard</option>${gruppen.map(g => `<option ${g === x.gruppe ? "selected" : ""}>${g}</option>`).join("")}</select></td>
          ${std ? `<td class="r">${numInp(x.stunden, `data-z="stunden" data-i="${i}" style="width:80px"`)}</td>`
                : `<td class="r">${numInp(x.minuten, `data-z="minuten" data-i="${i}" style="width:70px"`)}</td>
                   <td>${x.bezug && !d.bezug[x.bezug] ? `<select data-z="bezug" data-i="${i}" title="Diese Bezugsgröße gibt es nicht mehr – bitte eine andere wählen">${bezugOpt(x.bezug)}</select>`
                     : `<span title="Bezugsgröße aus den Einstellungen (Kalkulation › Tätigkeiten)">${esc((d.bezug[x.bezug] || ["–"])[0] === "---" ? "–" : (d.bezug[x.bezug] || ["–"])[0])}</span>`}</td><td class="r zmenge"></td>
                   <td class="r nw${x.ruest_aus ? " z-aus" : ""}"><input type="checkbox" data-za="ruest_aus" data-i="${i}" ${x.ruest_aus ? "" : "checked"} title="Rüstzeit ein/aus"> ${numInp(x.ruest, `data-z="ruest" data-i="${i}" style="width:60px"`)}</td>
                   <td class="r nw${x.helfer_aus ? " z-aus" : ""}"><input type="checkbox" data-za="helfer_aus" data-i="${i}" ${x.helfer_aus ? "" : "checked"} title="Helfer ein/aus"> ${numInp(x.helfer, `data-z="helfer" data-i="${i}" style="width:50px"`, 1)}</td>
                   <td class="r zmin"></td><td class="r zh"></td><td class="r zhp"></td>`}
          <td><button class="btn rot" data-del="${i}">✕</button></td></tr>`).join("")}
      </table></div>
      ${zeilen.length || std ? "" : `<div class="leer">Noch keine Zeiten.</div>`}
      <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">${std ? "" : `<button class="btn prim" id="zKat">+ Tätigkeit …</button>`}<button class="btn" id="zStd">Liste laden …</button>${zeilen.length ? `<button class="btn" id="zAlsListe">Als Liste speichern …</button><button class="btn rot" id="zLeeren" style="margin-left:auto">Alle Zeiten entfernen</button>` : ""}</div>
      ${std ? `<p class="hinweis">Alle Kostenstellen des Auftrags stehen als Zeile da; einfach die geschätzten Stunden je Anzahl eintragen. Mit + bekommt eine Kostenstelle eine weitere Zeile, z. B. für eine andere Lohngruppe. Kostenstellen werden unter Löhne und Zuschläge gepflegt.</p>` : ""}
      <table class="liste" id="zSum" style="margin-top:14px"></table><div id="zWarn"></div>
      ${std ? "" : `<p class="hinweis">Minuten gelten je Einheit der Bezugsgröße (z. B. je m² Platte). Rüstzeit fällt einmal je Position an, Helfer = Anteil einer Helferkraft während der Bearbeitung (0,5 = halbe Zeit; auf die Rüstzeit kein Helfer). Ist die Menge 0, entfällt die Zeile samt Rüstzeit. „h Pos.“ zeigt alles zusammen für die Position. Tätigkeit, Kostenstelle und Bezugsgröße kommen aus den Einstellungen (Kalkulation › Tätigkeiten) und sind hier fest; änderbar sind Lohngruppe, Minuten, Rüstzeit und Helfer.</p>`}`;
    werte();
    $$("[data-z]", z).forEach(el => el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
      const k = el.dataset.z; zeilen[+el.dataset.i][k] = ["minuten", "ruest", "helfer", "stunden"].includes(k) ? zahlEin(el.value) : el.value;
      sp.setze("zeiten", zeilen, el.tagName === "SELECT");
    }));
    $$("[data-del]", z).forEach(b => b.onclick = () => { zeilen.splice(+b.dataset.del, 1); sp.setze("zeiten", zeilen, true); zeichnen(); });
    $$("[data-za]", z).forEach(el => el.onchange = () => { zeilen[+el.dataset.i][el.dataset.za] = !el.checked; el.closest("td").classList.toggle("z-aus", !el.checked); sp.setze("zeiten", zeilen, true); });
    [["#zAlleR", "ruest_aus"], ["#zAlleH", "helfer_aus"]].forEach(([id, k]) => { const el = $(id, z); if (el) el.onchange = () => { zeilen.forEach(x => x[k] = !el.checked); sp.setze("zeiten", zeilen, true); zeichnen(); }; });
    $$("[data-pb]", z).forEach(el => el.addEventListener("input", () => { p.extras = {...(p.extras || {})}; p.extras.bezug_eigen = {...(p.extras.bezug_eigen || {}), [el.dataset.pb]: zahlEin(el.value)}; sp.setze("extras", p.extras); }));
    if ($("#zKat")) $("#zKat").onclick = () => katalogWaehlen(ctx, sp);
    // Platzhalterzeile einer Kostenstelle: beim ersten Eintrag wird daraus eine echte Zeile
    $$("[data-v]", z).forEach(el => el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
      const kst = el.dataset.v, tr = el.closest("tr");
      const neu = {kst, name: $("[data-vz=name]", tr).value, gruppe: $("[data-vz=gruppe]", tr).value, stunden: zahlEin($("[data-vz=stunden]", tr).value)};
      zeilen.push(neu);
      const i = zeilen.length - 1;
      tr.classList.remove("zt-leer"); tr.dataset.zz = i;
      $$("[data-v]", tr).forEach(f => { f.dataset.z = f.dataset.vz; f.dataset.i = i; delete f.dataset.v; delete f.dataset.vz;
        f.addEventListener(f.tagName === "SELECT" ? "change" : "input", () => { const kk = f.dataset.z; zeilen[i][kk] = kk === "stunden" ? zahlEin(f.value) : f.value; sp.setze("zeiten", zeilen, f.tagName === "SELECT"); zeileH(tr, i); }); });
      sp.setze("zeiten", zeilen, el.tagName === "SELECT"); zeileH(tr, i);
    }, {once: true}));
    $$("[data-z=stunden]", z).forEach(el => el.addEventListener("input", () => zeileH(el.closest("tr"), +el.dataset.i)));
    $$("[name=zm]", z).forEach(el => el.onchange = () => { p.zeitmodus = el.value; sp.setze("zeitmodus", el.value, true); zeichnen(); });
    $$("[data-plus]", z).forEach(b => b.onclick = () => {
      const kst = b.dataset.plus, letzte = zeilen.map((x, i) => x.kst === kst ? i : -1).filter(i => i >= 0).pop();
      zeilen.splice(letzte + 1, 0, {kst, name: "", gruppe: "", stunden: 0}); sp.setze("zeiten", zeilen, true); zeichnen();
    });
    if ($("#zNeu")) $("#zNeu").onclick = () => { zeilen.push(std ? {kst: ksts[0], name: "", gruppe: "", stunden: 0} : {kst: ksts[0], name: "", gruppe: "", minuten: 0, bezug: "", ruest: 0, helfer: 0}); sp.setze("zeiten", zeilen, true); zeichnen(); };
    $("#zStd").onclick = () => taetigkeitenLaden(ctx, sp);
    const al = $("#zAlsListe"); if (al) al.onclick = () => alsListeSpeichern(p);
    const zl = $("#zLeeren"); if (zl) zl.onclick = async () => { if (!await frage(`Alle ${zeilen.length} Zeilen aus den Zeiten dieser Position entfernen? Die Position selbst bleibt erhalten.`)) return; zeilen.splice(0); sp.setze("zeiten", zeilen, true); zeichnen(); };
    posKopfBinden(ctx);
  };
  zeichnen();
}

// Einzelne Tätigkeiten aus dem Katalog (Einstellungen › Tätigkeiten) in die Position übernehmen
async function katalogWaehlen(ctx, sp) {
  const {pid} = ctx;
  await sp.senden();
  const q = await api("kalkvorgaben");
  const K = nachKst([...(q.katalog || [])], ((q.vorgaben || {}).kostenstellen || []).map(k => k.kst));
  if (!K.length) return toast("Noch keine Tätigkeiten definiert (Einstellungen › Kalkulation › Tätigkeiten).", true);
  const bz = q.bezug || {};
  const zeile_ = t => `<label data-such="${esc((t.kst + " " + t.name).toLowerCase())}"><input type="checkbox" value="${esc(t.id)}"> <span><b>${esc(t.name)}</b> <span class="hinweis">${esc(t.kst)}</span></span>
    <small>${n2(t.minuten || 0, 1)} min${t.bezug ? " je " + esc((bz[t.bezug] || [t.bezug])[0]) : ""}</small></label>`;
  const gew = new Set();
  const ok = await modal("Tätigkeiten hinzufügen", `<input id="katQ" placeholder="Suchen …" style="width:100%;margin-bottom:8px">
    <div class="kat-liste">${K.map(zeile_).join("")}</div>
    <p class="hinweis">Mehrere ankreuzen. Die Werte werden in die Position kopiert und können dort angepasst werden.</p>`, "Hinzufügen", hg => {
      $(".modal", hg).style.width = "min(640px,96vw)";
      $("#katQ", hg).oninput = e => { const s = e.target.value.toLowerCase(); $$(".kat-liste label", hg).forEach(l => l.style.display = l.dataset.such.includes(s) ? "" : "none"); };
      $$(".kat-liste input", hg).forEach(c => c.onchange = () => c.checked ? gew.add(c.value) : gew.delete(c.value));
      setTimeout(() => $("#katQ", hg).focus(), 50);
    });
  if (!ok || !gew.size) return;
  const r = await api(`positionen/${pid}/taetigkeiten`, {method: "POST", body: {katalog: [...gew]}});
  toast(`${gew.size} Tätigkeit${gew.size > 1 ? "en" : ""} hinzugefügt`);
  zeitenSeite(Object.assign(ctx, {p: r.position}));
}

// Tätigkeitsliste auswählen und in die Position laden (gespeicherte Listen oder Listen dieses Auftrags)
async function taetigkeitenLaden(ctx, sp) {
  const {p, pid} = ctx;
  await sp.senden();
  const [q, kk] = await Promise.all([api("kalkvorgaben"), api(`auftraege/${ctx.a.id}/kalk`)]);
  const AL = (kk.kalk.taetigkeit_listen || []).map((l, i) => ({...l, _q: "auftrag", _i: i}));
  const L = [...AL, ...q.listen.map((l, i) => ({...l, _q: "", _i: i}))];
  // Vorschlag: Liste, deren Name am besten zum Positionstext passt
  const txt = klartext(p.text || "").toLowerCase();
  let vor = 0, best = 0;
  L.forEach((l, i) => { const w = (l.name || "").toLowerCase().split(/[\s,;/]+/).filter(x => x.length > 2); const tr = w.filter(x => txt.includes(x)).length; if (tr > best) { best = tr; vor = i; } });
  const hat = p.zeiten.length;
  const wahl = {liste: vor, ersetzen: false};
  const gruppe = l => l._q === "auftrag" ? "nur dieser Auftrag" : "";
  const ok = await modal("Tätigkeiten laden", `
    <p class="hinweis" style="margin-top:0">Welche Liste soll in diese Position geladen werden?</p>
    <div class="tl-wahl">${L.map((l, i) => `<label><input type="radio" name="tlw" value="${i}" ${i === vor ? "checked" : ""}> <span><b>${esc(l.name || "(ohne Namen)")}</b>${gruppe(l) ? ` <span class="tag">${gruppe(l)}</span>` : ""}<small>${(l.zeiten || []).length} Tätigkeiten${l.modus === "stunden" ? " · Stunden direkt" : ""} · ${esc((l.zeiten || []).slice(0, 4).map(x => x.name).join(", "))}${(l.zeiten || []).length > 4 ? " …" : ""}</small></span></label>`).join("")}</div>
    ${hat ? `<div class="radio" style="margin-top:12px"><label><input type="radio" name="tlm" value="0" checked> zu den vorhandenen ${hat} Zeilen ergänzen</label><label><input type="radio" name="tlm" value="1"> vorhandene Zeilen ersetzen</label></div>` : ""}
    <p class="hinweis"><a href="#/einstellungen/kalkulation/taetigkeiten" data-schliessen>Listen bearbeiten</a></p>`,
    "Laden", hg => {
      $$("[name=tlw]", hg).forEach(el => el.onchange = () => { wahl.liste = +el.value; });
      $$("[name=tlm]", hg).forEach(el => el.onchange = () => { wahl.ersetzen = el.value === "1"; });
      $$("[data-schliessen]", hg).forEach(a => a.onclick = () => hg.remove());
    });
  if (!ok) return;
  const gl = L[wahl.liste];
  const r = await api(`positionen/${pid}/taetigkeiten`, {method: "POST", body: {liste: gl._i, quelle: gl._q, ersetzen: wahl.ersetzen}});
  toast(`„${L[wahl.liste].name}“ geladen`);
  zeitenSeite(Object.assign(ctx, {p: r.position}));
}

// Zeiten der Position als neue Tätigkeitsliste ablegen
async function alsListeSpeichern(p) {
  const q = await api("kalkvorgaben");
  const L = JSON.parse(JSON.stringify(q.listen));
  const d = await modal("Als Tätigkeitsliste speichern", `
    <div class="zeile"><label>Speichern für</label><div class="radio"><label><input type="radio" name="alWo" value="alle" checked> alle Aufträge (Einstellungen)</label><label><input type="radio" name="alWo" value="auftrag"> nur diesen Auftrag</label></div></div>
    <div class="zeile"><label>Name</label><div><input id="alName" name="alName" value="${esc(klartext(p.text || "").split("\n")[0].slice(0, 60))}"></div></div>
    ${L.length ? `<div class="zeile"><label>oder ersetzen</label><div><select id="alErs" name="alErs"><option value="">— neue Liste —</option>${L.map((l, i) => `<option value="${i}">${esc(l.name)}</option>`).join("")}</select></div></div>` : ""}
    <p class="hinweis">Übernommen werden alle ${p.zeiten.length} Zeilen mit Minuten, Bezugsgrößen, Rüst- und Helferzeiten.</p>`,
    "Speichern", hg => $("#alName", hg).select());
  if (!d) return;
  if (d.alWo === "auftrag") {
    const name = (d.alName || "").trim(); if (!name) return toast("Bitte einen Namen eingeben", true);
    const kk = await api(`auftraege/${p.auftrag_id}/kalk`);
    const AL = kk.kalk.taetigkeit_listen || [];
    AL.push({name, modus: p.zeitmodus === "stunden" ? "stunden" : "taetigkeiten", zeiten: JSON.parse(JSON.stringify(p.zeiten))});
    await api(`auftraege/${p.auftrag_id}/kalk`, {method: "PUT", body: {taetigkeit_listen: AL}});
    return toast(`Liste „${name}“ für diesen Auftrag gespeichert`);
  }
  const name = (d.alName || "").trim(), ers = d.alErs || "";
  if (!name && ers === "") return toast("Bitte einen Namen eingeben", true);
  const eintrag = {name: ers === "" ? name : L[+ers].name, modus: p.zeitmodus === "stunden" ? "stunden" : "taetigkeiten", zeiten: JSON.parse(JSON.stringify(p.zeiten))};
  if (ers === "") L.push(eintrag); else L[+ers] = eintrag;
  await api("einstellungen", {method: "PUT", body: {taetigkeit_listen: L}});
  toast(`Liste „${eintrag.name}“ gespeichert`);
}

// --- Unterreiter „Summen“ ---
function summenSeite(ctx) {
  const {p, z, pid, d} = ctx;
  const sp = speicherer("positionen/" + pid, r => { Object.assign(p, r.position); tabelleZeichnen(); });
  const ex = p.extras;
  const tabelleZeichnen = () => {
    const c = p.calc, m = p.menge || 0;
    // Spalten: diese Position | Unterpositionen | zusammen (nur mit Unterpositionen) | Gesamt × Menge (nur wenn Menge ≠ 1) | Anteil
    const uk = c.unter_kat || {}, mitU = (p.kinder || []).length > 0, mitG = Math.abs(m - 1) > 1e-9;
    const sk = mitU ? (c.kosten_gesamt || 0) : (c.selbstkosten || 0);
    const svU = (+c.sonder_vertrieb || 0) + (+uk.sonder_vertrieb || 0);
    const wgZ = mitU ? (c.ep_gesamt || 0) - sk - svU : (c.wg || 0);
    const vz = v => (v >= 0 ? "+" : "") + n2(v);
    const ant = v => sk ? n2(v / sk * 100) + " %" : "";
    // Zeile: Bezeichnung, Zuschlag, eigener Wert, Wert der Unterpositionen, Darstellung (n2 / Stunden / Vorzeichen), Anteil?, fett?
    const zeile = (l, pz, eig, unt, art = "", mitAnteil = false, fett = false, opt = {}) => {
      const fmt = v => art === "h" ? n2(v) + " h" : art === "vz" ? vz(v) : n2(v);
      const b = s => fett ? `<b>${s}</b>` : s;
      const zus = opt.zus ?? (eig + unt);
      const ges = opt.ges ?? zus * m;
      let h = `<tr class="${fett ? "zw" : ""}"><td>${l}</td><td class="r nw">${pz}</td><td class="r nw">${opt.eigHtml ?? b(fmt(eig))}</td>`;
      if (mitU) h += `<td class="r nw">${opt.untHtml ?? fmt(unt)}</td><td class="r nw">${opt.zusHtml ?? b(fmt(zus))}</td>`;
      if (mitG) h += `<td class="r nw">${opt.gesHtml ?? b(art === "h" ? fmt(ges) : (art === "vz" ? vz(ges) : n2(ges)))}</td>`;
      return h + `<td class="r nw">${mitAnteil ? ant(zus) : ""}</td></tr>`;
    };
    const u = k => +uk[k] || 0;
    const np = numInp(c.ep_gesamt, 'id="np" style="width:110px;text-align:right;font-weight:600"');
    if ($("#sWarn")) $("#sWarn").innerHTML = kalkWarnHtml(c);
    $("#sTab").innerHTML = `
      <tr><th>Kalkulation</th><th class="r" style="width:120px">Zuschlag %</th><th class="r">${mitU ? "diese Position" : "je Anzahl"}</th>${mitU ? `<th class="r" title="Unterpositionen je Anzahl der Hauptposition"><a href="#/position/${pid}/unterpositionen" style="color:inherit">Unterpositionen</a></th><th class="r" title="diese Position plus Unterpositionen, je Anzahl">zusammen</th>` : ""}${mitG ? `<th class="r">Gesamt (×&nbsp;${n2(m, m % 1 ? 2 : 0)})</th>` : ""}<th class="r">Anteil</th></tr>
      ${zeile(`<a href="#/position/${pid}/werkstoffe">▸ Werkstoffe</a> <span class="hinweis">Stückliste ${p.stueckliste.length} Zeilen${c.kostenliste_werkstoffe ? ` · davon Kostenliste ${n2(c.kostenliste_werkstoffe)}` : ""}</span>`, "", c.werkstoffe, u("werkstoffe"))}
      ${zeile(`<a href="#/position/${pid}/beschlaege">▸ Beschläge</a> <span class="hinweis">${p.beschlaege.length} Zeilen</span>`, "", c.beschlaege, u("beschlaege"))}
      ${zeile("Oberfläche", "", c.oberflaeche, u("oberflaeche"))}
      ${zeile("Kleinmaterial", numInp(c.kleinmaterial_pz, 'data-x="kleinmaterial" style="width:70px"') + " %", c.kleinmaterial, u("kleinmaterial"))}
      ${zeile(`<a href="#/position/${pid}">▸ Fremdleistungen</a> <span class="hinweis">Kostenliste</span>`, "", c.fremdleistungen, u("fremdleistungen"))}
      ${zeile(`<a href="#/position/${pid}">▸ Zukauf</a> <span class="hinweis">Kostenliste, Handelsware</span>`, "", c.zukauf, u("zukauf"))}
      ${zeile("Summe Material", "", c.material, u("material"), "", true)}
      ${zeile("Gemeinkosten Material", n2(c.gk_material_pz) + " %", c.gk_material, u("gk_material"))}
      ${zeile("Material mit GK", "", c.material_gk, u("material_gk"), "", true, true)}
      ${zeile(`<a href="#/position/${pid}/zeiten">▸ Fertigungsstunden</a>`, "", c.stunden, u("stunden"), "h", false, false, {ges: (c.zeit_summen.gesamt_pos || 0) + u("stunden") * m})}
      ${zeile("Lohnkosten", "", c.lohn, u("lohn"), "", true)}
      ${zeile("Gemeinkosten Lohn", n2(c.gk_lohn_pz) + " %", c.gk_lohn, u("gk_lohn"))}
      ${zeile("Lohnkosten mit GK", "", c.lohn_gk, u("lohn_gk"), "", true, true)}
      ${zeile(`<a href="#/position/${pid}">▸ Sonderkosten Fertigung</a> <span class="hinweis">Kostenliste</span>`, "", c.sonder_fertigung, u("sonder_fertigung"), "", true)}
      ${zeile("Selbstkosten", "", c.selbstkosten, u("selbstkosten"), "", true, true, {zus: sk})}
      ${zeile("Wagnis und Gewinn", c.hat_kalk ? numInp(c.wg_pz, 'data-x="wg" style="width:70px"') + " %" : n2(c.wg_pz) + " %", c.wg, u("wg"), "vz", true, false, {zus: wgZ})}
      ${zeile(`<a href="#/position/${pid}">▸ Sonderkosten Vertrieb</a> <span class="hinweis">Kostenliste</span>`, "", c.sonder_vertrieb, u("sonder_vertrieb"))}
      ${zeile("Nettopreis", `<button class="btn" data-r="ab" title="abrunden">,00↓</button><button class="btn" data-r="auf" title="aufrunden">,00↑</button>`, c.einzelpreis, c.unter_ep || 0, "", false, true,
        {zus: c.ep_gesamt || 0, eigHtml: mitU ? `<b>${n2(c.einzelpreis)}</b>` : np, zusHtml: np, gesHtml: `<b>${n2(c.gesamtpreis)}</b>`})
        .replace(/<td class="r nw"><\/td><\/tr>$/, `<td class="r nw">${p.preis_manuell && c.hat_kalk ? `<button class="btn" id="neuBer">berechnen</button>` : ""}</td></tr>`)}`;
    $$("[data-x]", z).forEach(el => el.onchange = () => { ex[el.dataset.x] = zahlEin(el.value); sp.setze("extras", ex, true); if (el.dataset.x === "wg" && p.preis_manuell) sp.setze("preis_manuell", 0, true); });
    $$("[data-r]", z).forEach(b => b.onclick = async () => { await sp.senden(); const r = await api(`positionen/${pid}/runden`, {method: "POST", body: {modus: b.dataset.r}}); Object.assign(p, r.position); tabelleZeichnen(); });
    $("#np").onchange = () => { const v = zahlEin($("#np").value) - (p.calc.unter_ep || 0); sp.setze("einzelpreis", v, true); sp.setze("preis_manuell", 1, true); };
    const nb = $("#neuBer"); if (nb) nb.onclick = async () => { const r = await api(`positionen/${pid}/berechnen`, {method: "POST"}); Object.assign(p, r.position); tabelleZeichnen(); };
  };
  z.innerHTML = posKopfzeile(ctx, "Summen") + `<div id="sWarn"></div><table class="liste st" id="sTab"></table>
    <p class="hinweis">Wird der Nettopreis selbst eingegeben, gilt er als fester Preis und Wagnis und Gewinn ergibt sich daraus. Wird Wagnis und Gewinn eingegeben, berechnet sich der Preis wieder daraus.</p>`;
  tabelleZeichnen();
  posKopfBinden(ctx);
}

// --- Unterreiter „Unterpositionen“ ---
function unterSeite(ctx) {
  const {p, z, a, pid, d} = ctx;
  if (d.eltern) {
    z.innerHTML = posKopfzeile(ctx, "Unterpositionen") + `<div class="leer">Unterpositionen gibt es nur eine Ebene tief. Dies ist bereits eine Unterposition von <a href="#/position/${d.eltern.id}">Position ${d.eltern.posnr}</a>.</div>`;
    return posKopfBinden(ctx);
  }
  // Knöpfe oben gelten hier den Unterpositionen; Hauptposition kopieren/löschen auf den anderen Reitern
  z.innerHTML = posKopfzeile(ctx, "Unterpositionen zu", `<button class="btn prim pk" id="uNeu" title="Neue Unterposition zu dieser Position anlegen">${ic("neu")} Neue Unterposition</button>`, true) + `
    <table class="liste unterliste">
      <tr><th>Unterpos.</th><th class="r">Anzahl</th><th>Text</th><th class="r">Einzelpreis</th><th class="r">Gesamtpreis</th><th></th></tr>
      ${p.kinder.map(k => `<tr class="klick" data-id="${k.id}" draggable="true" title="Ziehen zum Verschieben"><td><span class="hinweis" style="cursor:grab;margin-right:6px">⠿</span><a href="#/position/${k.id}">${k.posnr}</a></td><td class="r">${n2(k.menge, k.menge % 1 ? 2 : 0)}</td>
        <td class="pl-text">${esc(k.einheit)} ${textHtml(k.text)}</td><td class="r">${eur(k.calc.ep_gesamt)}</td><td class="r">${eur(k.calc.gesamtpreis)}</td>
        <td class="r" style="white-space:nowrap"><button class="btn pk" data-a="kopie" title="Unterposition kopieren">${ic("uebernehmen")}</button><button class="btn" data-a="hoch" title="nach oben">▲</button><button class="btn" data-a="runter" title="nach unten">▼</button><button class="btn rot" data-a="del" title="Unterposition löschen">✕</button></td></tr>`).join("")}
      ${p.kinder.length ? `<tr><td colspan="4"><b>Summe Unterpositionen je Anzahl der Hauptposition</b></td><td class="r"><b>${eur(p.calc.unter_ep)}</b></td><td></td></tr>` : ""}
    </table>
    ${p.kinder.length ? "" : `<div class="leer">Noch keine Unterpositionen. Sie eignen sich z. B. für Schubkästen oder Zubehör, die zum Preis der Hauptposition dazugerechnet werden und eine eigene Kalkulation haben können. Neu anlegen mit „Neue Unterposition“ oben rechts.</div>`}`;
  $("#uNeu").onclick = () => neuePosition(a, {parent_id: pid});
  $$("tr.klick", z).forEach(tr => tr.onclick = async ev => {
    const b = ev.target.closest("button"), id = +tr.dataset.id;
    if (!b) { if (!ev.target.closest("a")) location.hash = `#/position/${id}`; return; }
    if (b.dataset.a === "del") { if (!await frage("Unterposition löschen?")) return; await api(`positionen/${id}`, {method: "DELETE"}); }
    else if (b.dataset.a === "kopie") { await api(`positionen/${id}/kopieren`, {method: "POST"}); toast("Kopie der Unterposition angelegt"); }
    else await api(`positionen/${id}/verschieben`, {method: "POST", body: {richtung: b.dataset.a === "hoch" ? -1 : 1}});
    ctx.neu();
  });
  // Drag & Drop: Unterposition innerhalb der Hauptposition verschieben (obere Zeilenhälfte = davor, untere = danach)
  const tab = $("table.liste", z), zeilen = $$("tr.klick", z);
  let zieh = null;
  const weg = () => zeilen.forEach(t => t.classList.remove("drop-vor", "drop-nach"));
  const ziel = ev => {
    const tr = ev.target.closest("tr.klick"); if (!tr) return null;
    const r = tr.getBoundingClientRect(), unten = ev.clientY > r.top + r.height / 2;
    const i = zeilen.indexOf(tr);
    return {zeile: tr, unten, vor: unten ? (zeilen[i + 1] ? +zeilen[i + 1].dataset.id : null) : +tr.dataset.id};
  };
  zeilen.forEach(tr => {
    tr.addEventListener("dragstart", ev => { zieh = +tr.dataset.id; tr.classList.add("zieht"); ev.dataTransfer.effectAllowed = "move"; ev.dataTransfer.setData("text/plain", String(zieh)); });
    tr.addEventListener("dragend", () => { tr.classList.remove("zieht"); weg(); zieh = null; });
  });
  tab.addEventListener("dragover", ev => {
    if (zieh == null) return;
    const zl = ziel(ev); if (!zl) return;
    ev.preventDefault(); ev.dataTransfer.dropEffect = "move";
    weg(); zl.zeile.classList.add(zl.unten ? "drop-nach" : "drop-vor");
  });
  tab.addEventListener("dragleave", ev => { if (!tab.contains(ev.relatedTarget)) weg(); });
  tab.addEventListener("drop", async ev => {
    if (zieh == null) return;
    ev.preventDefault();
    const zl = ziel(ev); weg();
    const id = zieh; zieh = null;
    if (!zl || zl.vor === id) return;
    const i = zeilen.findIndex(t => +t.dataset.id === id), nach = zeilen[i + 1];
    if ((nach && zl.vor === +nach.dataset.id) || (!nach && zl.vor === null)) return;   // gleiche Stelle
    try { await api(`positionen/${id}/einordnen`, {method: "POST", body: {vor: zl.vor}}); ctx.neu(); }
    catch (e) { toast(e.message, true); }
  });
  posKopfBinden(ctx);
}

// ---------------------------------------------------------------------
//  Auftragswerte / Standardwerte: Werkstoffe, Beschläge, Löhne, Zuschläge
// ---------------------------------------------------------------------
async function auftragsWerte(z, {auftrag = null, teil}) {
  const vorgabe = !auftrag;
  const quelle = vorgabe ? await api("kalkvorgaben") : await api(`auftraege/${auftrag.id}/kalk`);
  const k = vorgabe ? quelle.vorgaben : quelle.kalk;
  const typen = quelle.typen, lohngruppen = quelle.lohngruppen;
  const titel = {werkstoffe: "Werkstoffe", beschlaege: "Beschläge", loehne: "Löhne", zuschlaege: "Zuschläge"}[teil];
  const speichernNach = async (body) => {
    if (vorgabe) {
      const v = {...(E.kalk_vorgaben || {}), ...body};
      E = {...E, ...(await api("einstellungen", {method: "PUT", body: {kalk_vorgaben: v}}))};
      return;
    }
    await api(`auftraege/${auftrag.id}/kalk`, {method: "PUT", body});
  };
  let timer, offen = {};
  const setze = (key, sofort) => {
    offen[key] = k[key]; const s = $(".speicher"); if (s) { s.textContent = "…"; s.className = "speicher"; }
    clearTimeout(timer); timer = setTimeout(async () => {
      const d = offen; offen = {};
      try { await speichernNach(d); const s = $(".speicher"); if (s) { s.textContent = "gespeichert ✓"; s.className = "speicher ok"; } }
      catch (e) { toast(e.message, true); }
    }, sofort ? 30 : 600);
  };
  const kostenVon = w => (+w.preis || 0) * (1 + (+w.v || 0) / 100);
  const bMengen = quelle.beschlag_mengen || {};
  const kstVorgabe = quelle.kostenstellen_vorgabe || [];
  // Im Auftrag wird nur mit einer Kopie gearbeitet: Änderungen gehen nie zurück in die Einstellungen oder den Materialstamm
  const knoepfe = vorgabe || !["loehne", "zuschlaege"].includes(teil) ? "" : `<button class="btn" id="zurueck" title="Die Kopie in diesem Auftrag durch die aktuellen Werte aus den Einstellungen ersetzen">↻ Aus Einstellungen neu laden</button>`;
  const kopfHtml = `<div class="titel"><h2>${vorgabe ? "Standard-" + titel : "Auftrags" + titel.toLowerCase()}</h2><span class="speicher"></span><div class="rechts">${knoepfe}</div></div>
    ${vorgabe ? `<p class="hinweis" style="margin-top:-6px">Diese Werte übernimmt jeder neue Auftrag als Kopie. Bestehende Aufträge behalten ihre eigenen Werte.</p>`
      : `<p class="hinweis" style="margin-top:-6px">Kopie für diesen Auftrag. Änderungen hier gelten nur für diesen Auftrag, ${["werkstoffe", "beschlaege"].includes(teil) ? "der Materialstamm" : "die Einstellungen"} bleiben unverändert.</p>`}`;
  const binden = () => {
    $$("[data-w]", z).forEach(el => el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => {
      const [liste, i, f] = el.dataset.w.split(".");
      const ziel = i === "_" ? k : k[liste][+i];
      const feld = i === "_" ? f : f;
      ziel[feld] = el.dataset.num ? zahlEin(el.value) : el.value;
      const kz = el.closest("tr")?.querySelector(".wkost");
      if (kz && i !== "_") kz.textContent = n2(kostenVon(k[liste][+i]));
      const bg = el.closest("tr")?.querySelector(".bges");
      if (bg && i !== "_") { const b = k[liste][+i]; bg.textContent = n2((+b.preis || 0) * (bMengen[b.k] || 0)); const su = $("#bGesamt", z); if (su) su.textContent = eur(k.beschlaege.reduce((a, x) => a + (+x.preis || 0) * (bMengen[x.k] || 0), 0)); }
      const ml = el.closest("tr")?.querySelector(".ml2");
      if (ml) { const g = k.loehne[+i]; ml.textContent = eur(g.lohn * (1 + g.lnk / 100)); }
      const skh = el.closest("tr")?.querySelector(".skh");
      if (skh) skh.textContent = eur(lohnBasis() * (1 + (+k.kostenstellen[+i].gk || 0) / 100));
      setze(i === "_" ? feld : liste, el.tagName === "SELECT");
    }));
    $$("[data-weg]", z).forEach(b => b.onclick = () => { const [liste, i] = b.dataset.weg.split("."); k[liste].splice(+i, 1); setze(liste, true); zeichnen(); });
    const zr = $("#zurueck"); if (zr) zr.onclick = async () => {
      if (!await frage(`${titel} dieses Auftrags durch die aktuellen Werte aus den Einstellungen ersetzen? Positionen werden danach mit den neuen Werten gerechnet.`)) return;
      const teile = {werkstoffe: ["werkstoffe"], beschlaege: ["beschlaege"], loehne: ["loehne", "lohnbasis"], zuschlaege: ["kostenstellen", "gk_material", "kleinmaterial", "wg", "helfer_gruppe", "helfer_kst"]}[teil];
      await api(`auftraege/${auftrag.id}/kalk`, {method: "PUT", body: {_zuruecksetzen: teile}}); toast("Aus den Einstellungen neu geladen"); auftragsWerte(z, {auftrag, teil});
    };
  };
  const lohnBasis = () => (k.loehne.find(l => l.gruppe === k.lohnbasis) || {lohn: 0}).lohn;
  const zeichnen = () => {
    let html = kopfHtml;
    if (teil === "werkstoffe") {
      html += Object.entries(typen).map(([typ, [prae, name, einheit]]) => {
        const rows = k.werkstoffe.map((w, i) => [w, i]).filter(([w]) => w.typ === typ);
        if (!rows.length) return "";
        return `<h3 style="margin:14px 0 6px">${name}</h3><table class="liste">
          <tr><th style="width:50px">Kürzel</th><th style="min-width:220px">Bezeichnung</th><th style="width:76px">Einheit</th>${typ === "massiv" ? `<th class="r" style="width:72px" title="Rohdicke – damit wird das Volumen und der Preis gerechnet">Roh-<br>dicke</th><th class="r" style="width:72px" title="Fertigdicke – erscheint in Stückliste, Zuschnitt und Werkstattpapieren">Fertig-<br>dicke</th>` : typ === "oberflaeche" ? "" : `<th class="r" style="width:72px">Dicke mm</th>`}<th class="r" style="width:60px">V %</th><th class="r" style="width:96px">Preis/Einh.</th><th class="r" style="width:86px">Kosten</th><th style="width:40px"></th></tr>
          ${rows.map(([w, i]) => `<tr><td><b>${esc(w.k)}</b></td><td><div style="display:flex;gap:4px"><input data-w="werkstoffe.${i}.name" value="${esc(w.name)}" style="width:100%" placeholder="z. B. Egger H3303 / Span P3"><button class="btn" data-such="werkstoffe.${i}" title="Aus dem Materialstamm übernehmen">🔍</button></div>${w.matnr ? `<div class="hinweis">Material ${esc(w.matnr)}${w.lieferant ? " · " + esc(w.lieferant) : ""}${w.preis_vom ? " · Preis vom " + datum(w.preis_vom) : ""}${stammAbw(w)}</div>` : ""}</td>
            <td><select data-w="werkstoffe.${i}.einheit" style="width:68px">${opts(["m²", "lfm", "m³", "Stk.", "kg", "l"], w.einheit)}</select></td>
            ${typ === "oberflaeche" ? "" : `<td class="r">${numInp(w.dicke, `data-w="werkstoffe.${i}.dicke" data-num="1" style="width:60px"`, 1)}</td>`}
            ${typ === "massiv" ? `<td class="r">${numInp(w.fdicke || "", `data-w="werkstoffe.${i}.fdicke" data-num="1" style="width:60px" placeholder="${n2(w.dicke, 1)}"`, 1)}</td>` : ""}
            <td class="r">${numInp(w.v, `data-w="werkstoffe.${i}.v" data-num="1" style="width:50px"`, 0)}</td>
            <td class="r">${numInp(w.preis, `data-w="werkstoffe.${i}.preis" data-num="1" style="width:84px"`)}</td>
            <td class="r wkost">${n2(kostenVon(w))}</td><td><button class="btn rot" data-weg="werkstoffe.${i}" title="Zeile entfernen">✕</button></td></tr>`).join("")}
        </table>`;
      }).join("") + (k.werkstoffe.length ? `<p class="hinweis" style="margin-bottom:0">Verschnitt und Preis gelten nur für diesen ${vorgabe ? "Standard" : "Auftrag"} – der Materialstamm bleibt unverändert. Weicht etwas vom Stamm ab, steht der Stammwert darunter.</p>` : `<div class="leer" style="margin-top:10px">Noch keine Werkstoffe in diesem ${vorgabe ? "Standard" : "Auftrag"}. Mit „+ Material“ aus dem Materialstamm hinzufügen – beim CSV-Stücklistenimport kommen die Werkstoffe automatisch dazu.</div>`)
        + `<button class="btn prim" data-plus="material" style="margin-top:10px">+ Material</button><p class="hinweis">Kosten = Preis je Einheit × (1 + Verschnitt %). Kanten in lfm, Platten/Furnier/Oberfläche in m², Massivholz in m³ – gerechnet mit der Rohdicke, in Stückliste und Werkstattpapieren steht die Fertigdicke.</p>`;
    }
    if (teil === "beschlaege") {
      const mitMenge = !vorgabe;
      const summe = k.beschlaege.reduce((a, x) => a + (+x.preis || 0) * (bMengen[x.k] || 0), 0);
      html += `<table class="liste"><tr><th style="width:56px">Kürzel</th><th style="width:130px">Art.-Nr.</th><th style="width:110px">Einheit</th><th>Bezeichnung</th><th class="r" style="width:120px">Kosten je Einheit</th>${mitMenge ? `<th class="r" style="width:90px" title="Summe über alle Positionen dieses Auftrags">Menge im Auftrag</th><th class="r" style="width:110px">Gesamtkosten</th>` : ""}<th style="width:40px"></th></tr>
        ${k.beschlaege.map((b, i) => `<tr><td><b>${esc(b.k)}</b></td><td><input data-w="beschlaege.${i}.artnr" value="${esc(b.artnr)}" style="width:100%"></td>
          <td><select data-w="beschlaege.${i}.einheit">${opts(["Stk.", "Garnitur", "Paar", "Satz", "m", "Pkg."], b.einheit)}</select></td>
          <td><div style="display:flex;gap:4px"><input data-w="beschlaege.${i}.name" value="${esc(b.name)}" style="width:100%"><button class="btn" data-such="beschlaege.${i}" title="Aus dem Materialstamm übernehmen">🔍</button></div>${b.matnr || stammAbwPreis(b) ? `<div class="hinweis">${b.matnr ? "Material " + esc(b.matnr) + (b.lieferant ? " · " + esc(b.lieferant) : "") : ""}${stammAbwPreis(b)}</div>` : ""}</td>
          <td class="r">${numInp(b.preis, `data-w="beschlaege.${i}.preis" data-num="1" style="width:96px"`)}</td>
          ${mitMenge ? `<td class="r">${n2(bMengen[b.k] || 0, (bMengen[b.k] || 0) % 1 ? 2 : 0)}</td><td class="r bges">${n2((+b.preis || 0) * (bMengen[b.k] || 0))}</td>` : ""}
          <td><button class="btn rot" data-weg="beschlaege.${i}">✕</button></td></tr>`).join("")}
        ${mitMenge && k.beschlaege.length ? `<tr><td colspan="6" class="r"><b>Beschläge gesamt</b></td><td class="r"><b id="bGesamt">${eur(summe)}</b></td><td></td></tr>` : ""}
        </table>${k.beschlaege.length ? "" : `<div class="leer" style="margin-top:10px">Noch keine Beschläge. Mit „+ Beschlag“ aus dem Materialstamm hinzufügen.</div>`}<button class="btn prim" data-plus="beschlag" style="margin-top:10px">+ Beschlag</button>
        <p class="hinweis">Beschläge werden ohne Verschnitt gerechnet: Kosten je Einheit × Menge.${mitMenge ? " Die Menge ist die Summe aller Positionen (× Positionsmenge)." : ""}</p>`;
    }
    if (teil === "loehne") {
      html += `<table class="liste"><tr><th>Gruppe</th><th>Mittellohn I</th><th>Lohnnebenkosten</th><th class="r">Mittellohn II</th></tr>
        ${k.loehne.map((g, i) => `<tr><td><b>${esc(g.gruppe)}</b></td><td>${numInp(g.lohn, `data-w="loehne.${i}.lohn" data-num="1" style="width:90px"`)} €/h</td>
          <td>${numInp(g.lnk, `data-w="loehne.${i}.lnk" data-num="1" style="width:70px"`)} %</td><td class="r ml2">${eur(g.lohn * (1 + g.lnk / 100))}</td></tr>`).join("")}
      </table>
      <div class="form" style="margin-top:12px">${zeile("Lohnbasis", `<select data-w="x._.lohnbasis">${opts(lohngruppen, k.lohnbasis)}</select><span class="hinweis" style="padding-top:5px">gilt für Zeiten ohne eigene Lohngruppe</span>`, true)}</div>
      <p class="hinweis">Kalkuliert wird mit Mittellohn I. Lohnnebenkosten und Betriebskosten stecken in den Gemeinkosten-Zuschlägen der Kostenstellen.</p>`;
    }
    if (teil === "zuschlaege") {
      html += `<div class="hinweis" style="margin-bottom:8px">Lohnbasis für GK-Zuschläge: Mittellohn I ${esc(k.lohnbasis)} (${eur(lohnBasis())})</div>
      <table class="liste"><tr><th>Kostenstelle</th><th>Gemeinkosten-Zuschlag</th><th class="r">Selbstkosten je Stunde</th><th style="width:40px"></th></tr>
        ${k.kostenstellen.map((s, i) => `<tr><td>${vorgabe ? `<input data-w="kostenstellen.${i}.kst" value="${esc(s.kst)}" style="width:140px">` : `<b>${esc(s.kst)}</b>${(() => { const st = kstVorgabe.find(x => x.kst === s.kst); return st && Math.abs((+st.gk || 0) - (+s.gk || 0)) > 0.0049 ? `<div class="hinweis" style="color:var(--akzent)">in den Einstellungen: ${n2(st.gk, 0)} %</div>` : ""; })()}`}</td><td>${numInp(s.gk, `data-w="kostenstellen.${i}.gk" data-num="1" style="width:80px"`)} %</td>
          <td class="r skh">${eur(lohnBasis() * (1 + (+s.gk || 0) / 100))}</td><td><button class="btn rot" data-weg="kostenstellen.${i}" title="${vorgabe ? "Kostenstelle löschen" : "Aus diesem Auftrag entfernen (bleibt in den Einstellungen)"}">✕</button></td></tr>`).join("")}
      </table>${vorgabe ? `<button class="btn" data-plus="kst" style="margin-top:6px">+ Kostenstelle</button>`
        : kstVorgabe.some(v => !k.kostenstellen.find(x => x.kst === v.kst)) ? `<button class="btn" data-plus="kstkopie" style="margin-top:6px">+ Kostenstelle aus den Einstellungen</button>` : ""}
      ${vorgabe ? "" : `<p class="hinweis">Kostenstellen werden nur in den Einstellungen (Kalkulation › Zuschläge) angelegt. Der Auftrag arbeitet mit einer Kopie: Zuschlag ändern, Kostenstelle entfernen oder mit „+ Kostenstelle aus den Einstellungen“ wieder laden – die Einstellungen bleiben unverändert.</p>`}
      <div class="form" style="margin-top:14px">
        <div class="sektion">Material und Gewinn</div>
        ${zeile("GK-Zuschlag Material", numInp(k.gk_material, 'data-w="x._.gk_material" data-num="1" style="width:80px"') + " %")}
        ${zeile("Kleinmaterial", numInp(k.kleinmaterial, 'data-w="x._.kleinmaterial" data-num="1" style="width:80px"') + " % auf Werkstoffe, Beschläge, Oberfläche")}
        ${zeile("Wagnis und Gewinn", numInp(k.wg, 'data-w="x._.wg" data-num="1" style="width:80px"') + " % Standard")}
        <div class="sektion">Umlage Helferzeiten</div>
        ${zeile("auf Lohngruppe", `<select data-w="x._.helfer_gruppe">${opts(lohngruppen, k.helfer_gruppe)}</select>`)}
        ${zeile("auf Kostenstelle", `<select data-w="x._.helfer_kst">${opts(k.kostenstellen.map(s => s.kst), k.helfer_kst)}</select>`)}
      </div>`;
    }
    z.innerHTML = html;
    $$("[data-such]", z).forEach(b => b.onclick = async () => {
      const [liste, i] = b.dataset.such.split(".");
      const zeile_ = k[liste][+i];
      const kats = liste === "beschlaege" ? ["beschlaege", "artikel"] : ({platte: ["holzwerkstoffe"], kante: ["holzwerkstoffe"], furnier: ["holzwerkstoffe"], massiv: ["massivholz"], oberflaeche: ["beschichtung"]}[zeile_.typ] || null);
      const m = await materialWaehlen(kats); if (!m) return;
      const einh = {"lfm.": "lfm", "Liter": "l"}[m.einheit] || m.einheit;
      Object.assign(zeile_, {name: m.bezeichnung.split("\n")[0], preis: m.kalkpreis ?? m.ek_preis, v: m.verschnitt, stamm_preis: (m.kalkpreis ?? m.ek_preis) || 0, stamm_v: m.verschnitt || 0, matnr: m.nummer, lieferant: m.lieferant || "", bestellnr: m.bestellnr || "", preis_vom: m.preis_vom || ""});
      if (liste === "beschlaege") Object.assign(zeile_, {artnr: m.nummer, einheit: einh, v: 0, stamm_v: 0});
      else { zeile_.einheit = einh; if (m.dicke) zeile_.dicke = m.dicke; }
      setze(liste, true); zeichnen(); toast(`${m.nummer} übernommen`);
    });
    $$("[data-plus]", z).forEach(b => b.onclick = async () => {
      const t = b.dataset.plus;
      if (t === "kst") { k.kostenstellen.push({kst: "NEU", gk: 140}); setze("kostenstellen", true); zeichnen(); return; }
      if (t === "kstkopie") {
        const frei = kstVorgabe.filter(v => !k.kostenstellen.find(x => x.kst === v.kst));
        const d = await modal("Kostenstelle aus den Einstellungen", zeile("Kostenstelle", `<select name="kst">${frei.map(v => `<option value="${esc(v.kst)}">${esc(v.kst)} (${n2(v.gk, 0)} %)</option>`).join("")}</select>`), "Übernehmen");
        if (!d) return;
        const v = frei.find(x => x.kst === d.kst); if (!v) return;
        k.kostenstellen.push({...v}); setze("kostenstellen", true); zeichnen(); return;
      }
      const m = await materialWaehlen(t === "beschlag" ? ["beschlaege", "artikel", "chemie"] : ["holzwerkstoffe", "massivholz", "beschichtung", "chemie", "artikel"],
        t === "beschlag" ? "Beschlag hinzufügen" : "Material hinzufügen");
      if (!m) return;
      const r = materialInKalk(k, m, t === "beschlag" ? "beschlag" : null);
      setze(t === "beschlag" ? "beschlaege" : "werkstoffe", true); zeichnen();
      toast(r.neu ? `${m.nummer} als ${r.k} hinzugefügt` : `${m.nummer} ist schon als ${r.k} im ${vorgabe ? "Standard" : "Auftrag"}`);
    });
    binden();
  };
  zeichnen();
}

async function ansichtVorgaben(teil) {
  // alte Adressen #/vorgaben/… führen in die Einstellungen
  const tab = ["belegtexte", "textbausteine"].includes(teil) ? "texte" : teil === "kalender" ? "kalender" : "kalkulation";
  location.replace(`#/einstellungen/${tab}${tab === "kalender" ? "" : "/" + teil}`);
}

let taetListeAktiv = 0, taetAnsicht = "katalog";
// Tätigkeiten nach Kostenstelle (Reihenfolge wie in den Einstellungen), innerhalb der Kostenstelle nach Name
function nachKst(liste, ksts) {
  const pos = k => { const i = ksts.indexOf(k); return i < 0 ? 9999 : i; };
  return liste.sort((a, b) => pos(a.kst) - pos(b.kst) || String(a.kst || "").localeCompare(String(b.kst || ""), "de") || String(a.name || "").localeCompare(String(b.name || ""), "de"));
}
async function taetigkeitenVorgabe(z) {
  const q = await api("kalkvorgaben");
  const L = JSON.parse(JSON.stringify(q.listen));
  const B = JSON.parse(JSON.stringify(q.bezug_eigen || []));
  const ksts = q.vorgaben.kostenstellen.map(k => k.kst);
  const K = nachKst(JSON.parse(JSON.stringify(q.katalog || [])), ksts);
  const gruppen = q.vorgaben.loehne.map(l => l.gruppe);
  const sp = speicherer("einstellungen", r => { E = {...E, ...r}; });
  const FELDER = ["kst", "name", "gruppe", "minuten", "bezug", "ruest", "helfer"];
  // vorhandene Listenzeilen dem Katalog zuordnen (gleiche Kostenstelle + Name)
  let verknuepft = false;
  for (const l of L) for (const x of l.zeiten || []) if (!x.tid && (l.modus || "taetigkeiten") !== "stunden") {
    const k = K.find(k => k.kst === x.kst && (k.name || "").trim() === (x.name || "").trim()); if (k) { x.tid = k.id; verknuepft = true; }
  }
  const bezugAlle = () => ({...Object.fromEntries(Object.entries(q.bezug).filter(([k]) => !k.startsWith("x_"))), ...Object.fromEntries(B.filter(b => b.k && b.name).map(b => ["x_" + b.k, [b.name, b.einheit || "", b.quelle || "teil"]]))});
  const bezugOpt = w => Object.entries(bezugAlle()).map(([k, [l, e]]) => `<option value="${k}" ${k === (w || "") ? "selected" : ""}>${esc(l)}${e && !l.includes(" - ") ? " (" + esc(e) + ")" : ""}</option>`).join("");
  const speichernK = (sofort) => { sp.setze("taetigkeiten_katalog", K, sofort); };
  const speichernL = (sofort) => sp.setze("taetigkeit_listen", L, sofort);
  const speichernB = (sofort) => sp.setze("bezug_eigen", B, sofort);
  if (verknuepft) speichernL(true);
  // Katalogänderung an alle Listenzeilen weitergeben, die auf die Tätigkeit verweisen
  const weitergeben = t => { for (const l of L) for (const x of l.zeiten || []) if (x.tid === t.id) FELDER.forEach(f => x[f] = t[f]); speichernL(); };
  const nachKatalog = id => K.find(k => k.id === id);
  const reiterHtml = () => `<div class="radio" style="margin:-4px 0 12px">${[["katalog", "Tätigkeiten"], ["listen", "Tätigkeitslisten"], ["bezug", "Bezugsgrößen"]].map(([v, l]) => `<label><input type="radio" name="tAns" value="${v}" ${taetAnsicht === v ? "checked" : ""}> <b>${l}</b></label>`).join("")}</div>`;
  const katalogHtml = () => `
    <p class="hinweis" style="margin-top:-6px">Jede Tätigkeit wird hier einmal festgelegt. In der Position kommen einzelne mit „+ Tätigkeit …“ hinzu, oder es wird eine Liste geladen. Änderungen hier gelten für alle Listen, die die Tätigkeit enthalten; bereits kalkulierte Positionen behalten ihre Werte (Kopie).</p>
    <input id="kQ" placeholder="Tätigkeit suchen …" style="width:260px;margin-bottom:8px">
    <table class="liste"><tr><th>Kostenstelle</th><th>Tätigkeit</th><th>Lohngruppe</th><th class="r">Minuten</th><th>Bezugsgröße</th><th class="r">Rüstzeit</th><th class="r">Helfer</th><th class="r">in Listen</th><th></th></tr>
    ${K.map((x, i) => `<tr data-ks="${esc((x.kst + " " + x.name).toLowerCase())}"><td><select data-ki="${i}" data-k="kst">${opts(ksts, x.kst)}</select></td><td><input data-ki="${i}" data-k="name" value="${esc(x.name || "")}" style="width:100%;min-width:170px"></td>
      <td><select data-ki="${i}" data-k="gruppe"><option value="">Standard</option>${gruppen.map(g => `<option ${g === x.gruppe ? "selected" : ""}>${esc(g)}</option>`).join("")}</select></td>
      <td class="r">${numInp(x.minuten, `data-ki="${i}" data-k="minuten" data-num="1" style="width:70px"`)}</td><td><select data-ki="${i}" data-k="bezug">${bezugOpt(x.bezug)}</select></td>
      <td class="r">${numInp(x.ruest, `data-ki="${i}" data-k="ruest" data-num="1" style="width:60px"`)}</td><td class="r">${numInp(x.helfer, `data-ki="${i}" data-k="helfer" data-num="1" style="width:50px"`, 1)}</td>
      <td class="r">${L.filter(l => (l.zeiten || []).some(z => z.tid === x.id)).length || ""}</td><td><button class="btn rot" data-kdel="${i}" title="Tätigkeit löschen">✕</button></td></tr>`).join("")}</table>
    ${K.length ? "" : `<div class="leer">Noch keine Tätigkeiten.</div>`}
    <button class="btn prim" id="kPlus" style="margin-top:8px">+ Tätigkeit</button>`;
  const listenHtml = () => {
    if (taetListeAktiv >= L.length) taetListeAktiv = 0;
    const li = L[taetListeAktiv] || {name: "", zeiten: []}, t = li.zeiten || [], std = li.modus === "stunden";
    return `<p class="hinweis" style="margin-top:-6px">Eine Liste fasst Tätigkeiten aus dem Katalog zusammen, z. B. „Esstisch massiv, Stahlgestell“. In der Position werden sie mit „Liste laden …“ geladen. Listen nur für einen Auftrag werden in der Position gespeichert mit „Als Liste speichern … nur diesen Auftrag“.</p>
      <div class="tl-rahmen">
        <div class="tl-listen">
          ${L.map((x, i) => `<button class="tl-eintrag${i === taetListeAktiv ? " aktiv" : ""}" data-li="${i}"><span>${esc(x.name || "(ohne Namen)")}</span><small>${(x.zeiten || []).length}</small></button>`).join("")}
          <button class="btn" id="lNeu" style="margin-top:8px;width:100%">+ Neue Liste</button>
        </div>
        <div class="tl-inhalt">${L.length ? `
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px">
            <input id="lName" value="${esc(li.name || "")}" placeholder="Name der Liste" style="flex:1;min-width:220px;font-weight:600">
            <button class="btn" id="lHoch" ${taetListeAktiv ? "" : "disabled"} title="nach oben">↑</button>
            <button class="btn" id="lKopie">Kopieren</button>
            <button class="btn rot" id="lWeg" ${L.length > 1 ? "" : "disabled"}>Löschen</button>
          </div>
          <div class="radio" style="margin-bottom:8px"><label><input type="radio" name="lm" value="taetigkeiten" ${std ? "" : "checked"}> Tätigkeiten mit Bezugsgrößen</label><label><input type="radio" name="lm" value="stunden" ${std ? "checked" : ""}> Stunden direkt</label></div>
          <table class="liste"><tr><th>Kostenstelle</th><th>Tätigkeit</th><th>Lohngruppe</th>${std ? `<th class="r">Stunden/Anz.</th>` : `<th class="r">Minuten</th><th>Bezugsgröße</th><th class="r">Rüstzeit</th><th class="r">Helfer</th>`}<th></th></tr>
          ${t.map((x, i) => { const kat = !std && x.tid && nachKatalog(x.tid);
            if (kat) return `<tr title="aus dem Katalog – dort ändern"><td>${esc(kat.kst)}</td><td>${esc(kat.name)} <span class="tag">Katalog</span></td><td>${esc(kat.gruppe || "Standard")}</td><td class="r">${n2(kat.minuten || 0, 1)}</td><td>${esc((bezugAlle()[kat.bezug] || ["—"])[0])}</td><td class="r">${n2(kat.ruest || 0, 0)}</td><td class="r">${n2(kat.helfer || 0, 1)}</td>
              <td style="white-space:nowrap"><button class="btn" data-auf="${i}" ${i ? "" : "disabled"} title="nach oben">↑</button> <button class="btn rot" data-del="${i}">✕</button></td></tr>`;
            return `<tr><td><select data-i="${i}" data-k="kst">${opts(ksts, x.kst)}</select></td><td><input data-i="${i}" data-k="name" value="${esc(x.name || "")}" style="width:100%;min-width:160px"></td>
            <td><select data-i="${i}" data-k="gruppe"><option value="">Standard</option>${gruppen.map(g => `<option ${g === x.gruppe ? "selected" : ""}>${esc(g)}</option>`).join("")}</select></td>
            ${std ? `<td class="r">${numInp(x.stunden, `data-i="${i}" data-k="stunden" data-num="1" style="width:80px"`)}</td>`
              : `<td class="r">${numInp(x.minuten, `data-i="${i}" data-k="minuten" data-num="1" style="width:70px"`)}</td>
            <td><select data-i="${i}" data-k="bezug">${bezugOpt(x.bezug)}</select></td>
            <td class="r">${numInp(x.ruest, `data-i="${i}" data-k="ruest" data-num="1" style="width:60px"`)}</td>
            <td class="r">${numInp(x.helfer, `data-i="${i}" data-k="helfer" data-num="1" style="width:50px"`, 1)}</td>`}
            <td style="white-space:nowrap"><button class="btn" data-auf="${i}" ${i ? "" : "disabled"} title="nach oben">↑</button> <button class="btn rot" data-del="${i}">✕</button></td></tr>`; }).join("")}</table>
          ${t.length ? "" : `<div class="leer">Noch keine Tätigkeiten in dieser Liste.</div>`}
          <div style="display:flex;gap:8px;margin-top:8px">${std ? `<button class="btn" id="tPlus">+ Zeile</button>` : `<button class="btn prim" id="tKat">+ aus dem Katalog …</button>`}</div>` : `<div class="leer">Noch keine Liste.</div>`}
        </div>
      </div>`;
  };
  const bezugHtml = () => `<p class="hinweis" style="margin-top:-6px">Fest eingebaut sind ${Object.values(q.bezug).filter(v => v[0] !== "---").map(v => esc(v[0])).join(", ")}. Hier werden eigene Bezugsgrößen festgelegt. „je Teil“ erscheint als Eingabefeld im Teil der Stückliste und wird mit der Stückzahl summiert, „je Position“ wird in der Position unter Zeiten eingetragen.</p>
    <table class="liste" style="max-width:720px"><tr><th>Bezeichnung</th><th>Einheit</th><th>erfasst</th><th></th></tr>
    ${B.map((b, i) => `<tr><td><input data-bi="${i}" data-k="name" value="${esc(b.name || "")}" placeholder="z. B. Griffe montieren" style="width:100%"></td><td><input data-bi="${i}" data-k="einheit" value="${esc(b.einheit || "")}" placeholder="St." style="width:80px"></td>
      <td><select data-bi="${i}" data-k="quelle"><option value="teil" ${(b.quelle || "teil") === "teil" ? "selected" : ""}>je Teil (Stückliste)</option><option value="position" ${b.quelle === "position" ? "selected" : ""}>je Position</option></select></td>
      <td><button class="btn rot" data-bdel="${i}">✕</button></td></tr>`).join("")}</table>
    ${B.length ? "" : `<div class="leer" style="max-width:720px">Noch keine eigenen Bezugsgrößen.</div>`}
    <button class="btn" id="bPlus" style="margin-top:8px">+ Bezugsgröße</button>`;
  const zeichnen = () => {
    z.innerHTML = `<div class="titel"><h2>Tätigkeiten</h2><span class="speicher"></span></div>${reiterHtml()}
      ${taetAnsicht === "katalog" ? katalogHtml() : taetAnsicht === "listen" ? listenHtml() : bezugHtml()}`;
    $$("[name=tAns]", z).forEach(el => el.onchange = () => { taetAnsicht = el.value; zeichnen(); });
    if (taetAnsicht === "katalog") {
      $("#kQ").oninput = e => { const s2 = e.target.value.toLowerCase(); $$("[data-ks]", z).forEach(tr => tr.style.display = tr.dataset.ks.includes(s2) ? "" : "none"); };
      $$("[data-ki]", z).forEach(el => el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => { const t = K[+el.dataset.ki]; t[el.dataset.k] = el.dataset.num ? zahlEin(el.value) : el.value; speichernK(); weitergeben(t); }));
      $$("[data-kdel]", z).forEach(b => b.onclick = async () => {
        const t = K[+b.dataset.kdel], n = L.filter(l => (l.zeiten || []).some(x => x.tid === t.id)).length;
        if (!await frage(`Tätigkeit „${t.name}“ löschen?${n ? `\n\nSie steht in ${n} Liste(n); dort bleibt sie als eigene Zeile erhalten.` : ""}`)) return;
        for (const l of L) for (const x of l.zeiten || []) if (x.tid === t.id) delete x.tid;
        K.splice(+b.dataset.kdel, 1); speichernK(true); speichernL(true); zeichnen();
      });
      $("#kPlus").onclick = () => { const id = "t" + (Math.max(0, ...K.map(k => +String(k.id).replace(/\D/g, "") || 0)) + 1); K.push({id, kst: ksts[0], name: "", gruppe: "", minuten: 0, bezug: "", ruest: 0, helfer: 0}); speichernK(true); zeichnen(); $$("[data-k=name]", z).at(-1).focus(); };
    } else if (taetAnsicht === "listen") {
      const li = L[taetListeAktiv], t = li ? li.zeiten : [];
      $$("[data-li]", z).forEach(b => b.onclick = () => { taetListeAktiv = +b.dataset.li; zeichnen(); });
      $("#lNeu").onclick = () => { L.push({name: "Neue Liste", modus: "taetigkeiten", zeiten: []}); taetListeAktiv = L.length - 1; speichernL(true); zeichnen(); $("#lName").select(); };
      if (!li) return;
      $("#lName").oninput = e => { li.name = e.target.value; const b = $(`[data-li="${taetListeAktiv}"] span`, z); if (b) b.textContent = li.name || "(ohne Namen)"; speichernL(); };
      $("#lKopie").onclick = () => { L.splice(taetListeAktiv + 1, 0, JSON.parse(JSON.stringify({...li, name: li.name + " (Kopie)"}))); taetListeAktiv++; speichernL(true); zeichnen(); $("#lName").select(); };
      $("#lWeg").onclick = async () => { if (!await frage(`Liste „${li.name}“ löschen?`)) return; L.splice(taetListeAktiv, 1); taetListeAktiv = Math.max(0, taetListeAktiv - 1); speichernL(true); zeichnen(); };
      $("#lHoch").onclick = () => { const i = taetListeAktiv; [L[i - 1], L[i]] = [L[i], L[i - 1]]; taetListeAktiv--; speichernL(true); zeichnen(); };
      $$("[name=lm]", z).forEach(el => el.onchange = () => { li.modus = el.value; speichernL(true); zeichnen(); });
      $$("[data-k]", z).forEach(el => el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => { t[+el.dataset.i][el.dataset.k] = el.dataset.num ? zahlEin(el.value) : el.value; speichernL(); }));
      $$("[data-del]", z).forEach(b => b.onclick = () => { t.splice(+b.dataset.del, 1); speichernL(true); zeichnen(); });
      $$("[data-auf]", z).forEach(b => b.onclick = () => { const i = +b.dataset.auf; [t[i - 1], t[i]] = [t[i], t[i - 1]]; speichernL(true); zeichnen(); });
      if ($("#tPlus")) $("#tPlus").onclick = () => { t.push({kst: ksts[0], name: "", gruppe: "", stunden: 1}); speichernL(true); zeichnen(); };
      if ($("#tKat")) $("#tKat").onclick = async () => {
        const gew = new Set();
        const ok = await modal("Tätigkeiten aus dem Katalog", `<div class="kat-liste">${K.map(k => `<label><input type="checkbox" value="${esc(k.id)}" ${t.some(x => x.tid === k.id) ? "disabled" : ""}> <span><b>${esc(k.name)}</b> <span class="hinweis">${esc(k.kst)}</span></span><small>${n2(k.minuten || 0, 1)} min</small></label>`).join("")}</div>`, "Hinzufügen",
          hg => $$(".kat-liste input", hg).forEach(c => c.onchange = () => c.checked ? gew.add(c.value) : gew.delete(c.value)));
        if (!ok || !gew.size) return;
        for (const id of gew) { const k = nachKatalog(id); if (k) t.push({tid: k.id, ...Object.fromEntries(FELDER.map(f => [f, k[f]]))}); }
        speichernL(true); zeichnen();
      };
    } else {
      $$("[data-bi]", z).forEach(el => el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => { B[+el.dataset.bi][el.dataset.k] = el.value; speichernB(); }));
      $$("[data-bdel]", z).forEach(b => b.onclick = async () => { if (!await frage(`Bezugsgröße „${B[+b.dataset.bdel].name}“ löschen? Tätigkeiten, die sie nutzen, rechnen dann ohne Menge.`)) return; B.splice(+b.dataset.bdel, 1); speichernB(true); zeichnen(); });
      $("#bPlus").onclick = () => { const k = "b" + (Math.max(0, ...B.map(b => +String(b.k).replace(/\D/g, "") || 0)) + 1); B.push({k, name: "", einheit: "St.", quelle: "teil"}); speichernB(true); zeichnen(); $$("[data-k=name]", z).at(-1).focus(); };
    }
  };
  if (!(q.katalog_gespeichert) && K.length && !(E.taetigkeiten_katalog || []).length) speichernK(true);
  zeichnen();
}

function textbausteineVorgabe(z) {
  const tb = (E.textbausteine || []).map(x => ({...x}));
  const sp = speicherer("einstellungen", r => { E = {...E, ...r}; });
  const zeichnen = () => {
    z.innerHTML = `<div class="titel"><h2>Textbausteine</h2><span class="speicher"></span></div>
      ${tb.map((t, i) => `<div class="kachel" style="margin-bottom:10px"><div style="display:flex;gap:8px;margin-bottom:6px"><input data-i="${i}" data-k="name" value="${esc(t.name)}" style="flex:1;font-weight:600"><button class="btn rot" data-del="${i}">Löschen</button></div>
        ${rtEditor(t.text, `data-i="${i}" data-k="text"`)}</div>`).join("")}
      <button class="btn" id="tbPlus">+ Textbaustein</button>`;
    $$("[data-k]", z).forEach(el => el.oninput = () => { tb[+el.dataset.i][el.dataset.k] = el.isContentEditable ? el.innerHTML : el.value; sp.setze("textbausteine", tb); });
    $$("[data-del]", z).forEach(b => b.onclick = async () => { if (!await frage("Textbaustein löschen?")) return; tb.splice(+b.dataset.del, 1); sp.setze("textbausteine", tb, true); zeichnen(); });
    $("#tbPlus").onclick = () => { tb.push({name: "Neuer Baustein", text: ""}); sp.setze("textbausteine", tb, true); zeichnen(); };
  };
  zeichnen();
}

// ---------------------------------------------------------------------
//  Reiter „Stunden“ (Ist-Zeiten) und „Soll/Ist“
// ---------------------------------------------------------------------
const terminText = t => `${t.typ}${t.titel ? " · " + t.titel : ""} ${datum(t.von).slice(0, 6)}${t.bis !== t.von ? "–" + datum(t.bis).slice(0, 6) : ""}`;
function fortschritt(g, p) {
  const pz = p ? Math.min(100, g / p * 100) : 0, ueber = p && g > p + 0.05;
  return `<div class="fs"><i style="width:${pz}%;${ueber ? "background:var(--rot)" : ""}"></i></div><span class="${ueber ? "rot-t" : ""}">${n2(g, 1)} / ${n2(p, 1)} h</span>`;
}
async function stundenSeite(z, a) {
  const [liste, k, termine, si] = await Promise.all([api("stunden?auftrag=" + a.id), api(`auftraege/${a.id}/kalk`), api("termine?auftrag=" + a.id), api(`auftraege/${a.id}/sollist`).catch(() => ({titel: []}))]);
  let tl = []; try { tl = JSON.parse(a.titel || "[]"); } catch (e) {}
  const tName = nr => { const t = tl.find(x => +x.nr === +nr); return t ? `T${String(t.nr).padStart(2, "0")} ${t.name || ""}` : ""; };
  const titelOpts = (wert, nurOffen) => `<option value="0">— ohne Titel —</option>` + tl.filter(t => !nurOffen || !t.buchung_gesperrt || +t.nr === +wert)
    .map(t => `<option value="${t.nr}" ${+t.nr === +wert ? "selected" : ""}>${esc(tName(t.nr))}${t.buchung_gesperrt ? " (abgeschlossen)" : ""}</option>`).join("");
  const ksts = k.kalk.kostenstellen.map(s => s.kst), gruppen = k.kalk.loehne.map(l => l.gruppe);
  const summe = liste.reduce((s, x) => s + x.stunden, 0);
  const ohne = liste.filter(s => !s.termin_id).reduce((s, x) => s + x.stunden, 0);
  const typKst = E.typ_kst || {};
  const passend = d => termine.find(t => t.von <= d && t.bis >= d && !t.erledigt) || termine.find(t => t.von <= d && t.bis >= d);
  z.innerHTML = `<div class="titel"><h2>Stunden (Ist)</h2></div>
    <div class="form" id="sf">
      ${zeile("Datum", `<input type="date" name="datum" value="${heute()}">`)}
      ${zeile("Stunden", `<input name="stunden" class="zahl" style="width:90px" placeholder="0,00"> h`)}
      ${zeile("Termin", `<select name="termin_id"><option value="">automatisch nach Datum</option>${termine.map(t => `<option value="${t.id}">${esc(terminText(t))}${t.erledigt ? " ✓" : ""}</option>`).join("")}<option value="0">ohne Termin</option></select><span class="hinweis" id="sAuto" style="padding-top:5px"></span>`, true)}
      ${tl.length ? zeile("Titel", `<select name="titel">${titelOpts(0, true)}</select>`) : ""}
      ${zeile("Kostenstelle", `<select name="kst"><option value="">passend zum Termin</option>${opts(ksts, "")}</select>`)}
      ${zeile("Lohngruppe", `<select name="gruppe">${opts(gruppen, k.kalk.lohnbasis)}</select>`)}
      ${zeile("Tätigkeit", `<input name="taetigkeit" placeholder="z. B. Korpus verleimen">`, true)}
      <div class="zeile voll"><label></label><div><button class="btn prim" id="sNeu">Buchen</button></div></div>
    </div>
    ${termine.length ? `<h3 style="margin:18px 0 6px">Termine: geplant und gebucht</h3>
    <table class="liste"><tr><th>Termin</th><th>Zeitraum</th><th style="width:300px">gebucht / geplant</th><th></th></tr>
      ${termine.map(t => `<tr><td><span class="km-e" style="--f:${typFarbe(t.typ)};display:inline-block">${esc(t.typ)}</span> ${esc(t.titel || "")}${t.erledigt ? " <span class='hinweis'>erledigt</span>" : ""}</td>
        <td>${datum(t.von)}${t.bis !== t.von ? " – " + datum(t.bis) : ""}</td><td class="fs-zelle">${fortschritt(t.gebucht, t.geplant)}</td>
        <td><a href="#/kalender/planung/${t.von}">im Kalender</a></td></tr>`).join("")}
      ${ohne ? `<tr><td colspan="2" class="hinweis">ohne Termin gebucht</td><td>${n2(ohne, 1)} h</td><td></td></tr>` : ""}
    </table>` : `<p class="hinweis">Noch keine Termine. Sind im Kalender oder im Reiter Auftrag Termine angelegt, werden die Stunden automatisch zugeordnet.</p>`}
    ${tl.length && (si.titel || []).length ? `<h3 style="margin:18px 0 6px">Stunden je Titel</h3>
    <table class="liste"><tr><th>Titel</th><th style="width:300px">gebucht / kalkuliert</th><th></th></tr>
      ${si.titel.map(t => `<tr><td>${t.nr ? esc(tName(t.nr)) : "<span class='hinweis'>ohne Titel</span>"}${t.gesperrt ? " <span class='hinweis'>(nicht in der Summe)</span>" : ""}</td>
        <td class="fs-zelle">${fortschritt(t.ist_stunden, t.soll_stunden)}</td><td>${t.buchung_gesperrt ? "<span class='hinweis'>abgeschlossen</span>" : ""}</td></tr>`).join("")}</table>` : ""}
    <h3 style="margin:18px 0 6px">Buchungen</h3>
    <table class="liste"><tr><th>Datum</th><th class="r">Stunden</th><th>Termin</th>${tl.length ? "<th>Titel</th>" : ""}<th>Kostenstelle</th><th>Lohngruppe</th><th>Tätigkeit</th><th></th></tr>
      ${liste.map(s => `<tr><td>${datum(s.datum)}</td><td class="r">${n2(s.stunden)}</td>
        <td><select data-tz="${s.id}" style="max-width:220px"><option value="">— ohne —</option>${termine.map(t => `<option value="${t.id}" ${t.id === s.termin_id ? "selected" : ""}>${esc(terminText(t))}</option>`).join("")}</select></td>
        ${tl.length ? `<td><select data-ttl="${s.id}" style="max-width:220px">${titelOpts(s.titel || 0, true)}</select></td>` : ""}
        <td>${esc(s.kst)}</td><td>${esc(s.gruppe)}</td><td>${esc(s.taetigkeit)}</td><td><button class="btn rot" data-del="${s.id}">✕</button></td></tr>`).join("")}
      <tr><td><b>Summe</b></td><td class="r"><b>${n2(summe)} h</b></td><td colspan="6"></td></tr></table>`;
  const auto = () => {
    const sel = $("[name=termin_id]", z), d = $("[name=datum]", z).value;
    if (sel.value === "") { const t = passend(d); $("#sAuto").textContent = t ? "→ " + terminText(t) : "→ kein Termin an diesem Tag"; }
    else $("#sAuto").textContent = "";
    const t = sel.value && sel.value !== "0" ? termine.find(x => x.id === +sel.value) : sel.value === "" ? passend(d) : null;
    $("[name=kst]", z).options[0].textContent = t && typKst[t.typ] ? `passend zum Termin (${typKst[t.typ]})` : "passend zum Termin";
  };
  $("[name=datum]", z).onchange = auto; $("[name=termin_id]", z).onchange = auto; auto();
  $("#sNeu").onclick = async () => {
    const d = {auftrag_id: a.id}; $$("[name]", $("#sf")).forEach(el => d[el.name] = el.name === "stunden" ? zahlEin(el.value) : el.value);
    d.termin_id = d.termin_id === "" ? null : +d.termin_id;
    if (!d.kst) d.kst = "";
    try { const r = await api("stunden", {method: "POST", body: d}); toast(r.termin ? `Gebucht auf ${r.termin}` : "Gebucht (ohne Termin)"); stundenSeite(z, a); } catch (e) { toast(e.message, true); }
  };
  $$("[data-ttl]", z).forEach(sel => sel.onchange = async () => { try { await api("stunden/" + sel.dataset.ttl, {method: "PUT", body: {titel: +sel.value}}); toast("Titel geändert"); } catch (e) { toast(e.message, true); } stundenSeite(z, a); });
  $$("[data-tz]", z).forEach(sel => sel.onchange = async () => { await api("stunden/" + sel.dataset.tz, {method: "PUT", body: {termin_id: sel.value ? +sel.value : null}}); toast("Zuordnung geändert"); stundenSeite(z, a); });
  $$("[data-del]", z).forEach(b => b.onclick = async () => { if (!await frage("Buchung löschen?")) return; await api("stunden/" + b.dataset.del, {method: "DELETE"}); stundenSeite(z, a); });
}

async function sollIstSeite(z, a, titel = "") {
  const d = await api(`auftraege/${a.id}/sollist${titel !== "" ? "?titel=" + titel : ""}`);
  const s = d.soll, i = d.ist;
  // Zeilen wie im Branchenprogramm; Anteil bezogen auf die Selbstkosten (= 100 %)
  const ZEILEN = [["Werkstoffe", "werkstoffe"], ["Beschläge", "beschlaege"], ["Oberfläche", "oberflaeche"], ["Kleinmaterial", "kleinmaterial"], ["Fremdleistungen", "fremdleistungen"], ["Zukauf (Handelsware)", "zukauf"],
    ["Summe Material", "material", "zw"], ["Gemeinkosten Material", "gk_material"], ["Material mit GK", "material_gk", "anteil"],
    [`<a href="#/auftrag/${a.id}/stunden">▸ Fertigungsstunden</a>`, "stunden", "h"], ["Lohnkosten", "lohn"], ["Gemeinkosten Lohn", "gk_lohn"], ["Lohnkosten mit GK", "lohn_gk", "anteil"],
    ["Sonderkosten Fertigung", "sonder_fertigung"], ["Selbstkosten (100 %)", "selbstkosten", "anteil"], ["Wagnis und Gewinn", "wg", "ertrag"],
    ["Sonderkosten Vertrieb", "sonder_vertrieb"], ["Nettopreis", "nettopreis", "ertrag"]];
  // Zuschlagssatz hinter den Gemeinkosten-Zeilen (Soll; weicht das Ist ab, zusätzlich Ist)
  const gkSatz = k => {
    const basis = {gk_material: "material", gk_lohn: "lohn"}[k]; if (!basis) return "";
    const pz = [s, i].map(x => +x[basis] ? (+x[k] || 0) / +x[basis] * 100 : null);
    if (pz[0] == null && pz[1] == null) return "";
    return ` <span class="hinweis">${n2(pz[0] ?? pz[1])} %${pz[0] != null && pz[1] != null && Math.abs(pz[0] - pz[1]) >= 0.005 ? ` (Ist ${n2(pz[1])} %)` : ""}</span>`;
  };
  const rot = (v, e) => { const r = Math.round((+v || 0) * 100) / 100; return `<span${r < 0 ? ' style="color:var(--rot)"' : ""}>${n2(r)}${e}</span>`; };
  // Anteil an den Selbstkosten; auch für Material und Lohn ohne Gemeinkosten
  const anteil = (x, k, art) => (art === "anteil" || art === "ertrag" || k === "material" || k === "lohn") && k !== "nettopreis" && x.selbstkosten ? rot(x[k] / x.selbstkosten * 100, " %") : "";
  // Abweichung: bei Kosten Soll − Ist (mehr gebucht als kalkuliert → negativ), bei Ertrag Ist − Soll
  const abw = (k, art) => art === "ertrag" ? (+i[k] || 0) - (+s[k] || 0) : (+s[k] || 0) - (+i[k] || 0);
  const tl = d.titel_liste || [];
  z.innerHTML = `<div class="titel"><h2>Soll/Ist-Vergleich</h2>
      <div class="rechts">${tl.length ? `<select id="siTitel"><option value="">Ganzer Auftrag</option>${tl.map(t => `<option value="${t.nr}" ${String(d.gewaehlt) === String(t.nr) ? "selected" : ""}>Titel ${String(t.nr).padStart(2, "0")} ${esc(t.name)}</option>`).join("")}</select>` : ""}
        <a class="btn" target="_blank" href="/papier/${a.id}/sollist${titel !== "" ? "?titel=" + titel : ""}">Drucken</a></div></div>
    ${(d.ohne_kalk || []).length ? `<div class="kachel" style="border-left:4px solid #c9a227;margin:0 0 12px">⚠ <b>${d.ohne_kalk.length === 1 ? "1 Position hat" : d.ohne_kalk.length + " Positionen haben"} einen Preis, aber keine Kosten.</b>
      Ohne Kalkulation (Stückliste, Beschläge, Zeiten oder Kostenliste) zählt ihr ganzer Preis als Wagnis und Gewinn, Selbstkosten und Zuschlag sind dadurch zu niedrig bzw. zu hoch:
      ${d.ohne_kalk.map(x => `Pos. ${esc(x.posnr)}${x.text ? " " + esc(x.text) : ""} (${eur(x.betrag)})`).join(", ")}.
      Abhilfe: in der Position die Kosten in die Kostenliste eintragen (z. B. als Zukauf) oder Zeiten planen.</div>` : ""}
    <table class="liste st">
      <tr><th>Kosten</th><th class="r">Soll</th><th class="r">Anteil</th><th class="r">Ist</th><th class="r">Anteil</th><th class="r">Abweichung</th></tr>
      ${ZEILEN.map(([l, k, art = ""]) => { const e = art === "h" ? " h" : " €";
        return `<tr class="${["zw", "anteil", "ertrag"].includes(art) ? "zw" : ""}"><td>${["zw", "anteil", "ertrag"].includes(art) ? `<b>${l}</b>` : l}${gkSatz(k)}</td><td class="r">${rot(s[k], e)}</td><td class="r">${anteil(s, k, art)}</td>
          <td class="r">${rot(i[k], e)}</td><td class="r">${anteil(i, k, art)}</td><td class="r"><b>${rot(abw(k, art), e)}</b></td></tr>`; }).join("")}
    </table>
    ${d.erloes ? `<p class="hinweis">Ist-Nettopreis: ${esc(d.erloes)}. Die Kosten im Ist sind die gebuchten Stunden und Materialien.</p>` : ""}
    ${d.ohne_kst ? `<p class="hinweis">${n2(d.ohne_kst.stunden)} h wurden ohne Kostenstelle gebucht (z. B. Stempeluhr ohne Tätigkeit); sie sind mit dem durchschnittlichen Gemeinkostenzuschlag des Auftrags von ${n2(d.ohne_kst.gk_pz, 1)} % bewertet.</p>` : ""}
    ${!d.gewaehlt && (d.titel || []).filter(t => t.nr).length ? `<h3 style="margin:18px 0 6px">Je Titel</h3><table class="liste st">
      <tr><th>Titel</th><th class="r">Netto</th><th class="r">Stunden Soll</th><th class="r">Stunden Ist</th><th class="r">Abweichung</th><th class="r">gebuchte Auftragskosten</th></tr>
      ${d.titel.map(t => `<tr${t.nr ? ` class="klick" data-titel="${t.nr}"` : ""}><td>${t.nr ? "T" + String(t.nr).padStart(2, "0") + " " + esc(t.name) : "<span class='hinweis'>ohne Titel</span>"}${t.buchung_gesperrt ? " <span class='hinweis'>(abgeschlossen)</span>" : ""}</td>
        <td class="r">${n2(t.netto)} €</td><td class="r">${n2(t.soll_stunden)} h</td><td class="r">${n2(t.ist_stunden)} h</td><td class="r">${rot(t.soll_stunden - t.ist_stunden, " h")}</td><td class="r">${n2(t.ist_kosten)} €</td></tr>`).join("")}
    </table>` : ""}
    <p class="hinweis">Abweichung = Soll − Ist; bei Wagnis und Gewinn und beim Nettopreis Ist − Soll. Negativ (rot) heißt: schlechter als kalkuliert. Ist-Material kommt aus den Auftragskosten (Lager, Zuschnitt) und den Zahlungsaufträgen, die diesem Auftrag zugeordnet sind (netto, nach Lieferantengruppe)${d.gewaehlt ? "; bei einem einzelnen Titel zählen nur Stunden und Auftragskosten mit diesem Titel, Lieferantenrechnungen nur beim ganzen Auftrag" : ""}. Ist-Stunden kommen aus dem Reiter Stunden. Ist-Nettopreis ist die Auftragssumme.</p>`;
  const w = $("#siTitel"); if (w) w.onchange = () => sollIstSeite(z, a, w.value);
  $$("tr[data-titel]", z).forEach(tr => tr.onclick = () => sollIstSeite(z, a, tr.dataset.titel));
}

// =====================================================================
//  Stufe 3b: Kundenbelege (Angebot..Rechnung), Offene Posten
// =====================================================================
const BELEGARTEN_UI = [["angebot","Angebot"],["kv","Kostenvoranschlag"],["ab","Auftragsbestätigung"],["lieferschein","Lieferschein"],["abnahme","Abnahmeprotokoll"],["abschlag","Abschlagsrechnung"],["rechnung","Rechnung / Schlussrechnung"],["gutschrift","Gutschrift"],["korrektur","Rechnungskorrektur"]];
const FREI_ARTEN = ["gutschrift", "korrektur"];
// Eigene Belegarten (Einstellungen › Texte › Eigene Belegarten) als Auswahl „v:Schlüssel“
const belegArtWahl = vorgabe => BELEGARTEN_UI.map(([v, l]) => `<option value="${v}" ${v === vorgabe ? "selected" : ""}>${l}</option>`).join("")
  + ((E.beleg_varianten || []).length ? `<optgroup label="Eigene Belegarten">${E.beleg_varianten.map(x => `<option value="v:${esc(x.key)}" data-basis="${esc(x.basis)}">${esc(x.name)}${x.bemerkung ? " – " + esc(x.bemerkung) : ""}</option>`).join("")}</optgroup>` : "");
const belegBasis = v => v && v.startsWith("v:") ? ((E.beleg_varianten || []).find(x => "v:" + x.key === v) || {}).basis || "" : v;
const freiZeilenHtml = (zeilen, dis = "") => `<table class="liste" style="width:100%"><tr><th>Text</th><th class="r" style="width:130px">Betrag netto</th><th style="width:30px"></th></tr>
  ${zeilen.map((x, i) => `<tr><td><textarea data-fz="${i}" data-fk="text" rows="2" style="width:100%" ${dis}>${esc(x.text || "")}</textarea></td>
    <td class="r"><input class="zahl" data-fz="${i}" data-fk="betrag" value="${x.betrag ? n2(x.betrag) : ""}" style="width:110px" ${dis}></td>
    <td>${dis || zeilen.length < 2 ? "" : `<a href="#" data-fzdel="${i}">✕</a>`}</td></tr>`).join("")}</table>
  ${dis ? "" : `<a href="#" class="fz-neu">+ Zeile</a>`}`;
const belegStatus = b => b.status === "entwurf" ? `<span style="color:var(--akzent)">Entwurf</span>`
  : b.status === "storniert" ? `<span style="color:var(--rot)">storniert</span>`
  : b.status === "fest" ? `<span style="color:var(--gruen)">festgeschrieben</span>` : b.versendet ? "versendet" : "erstellt";
const belegName = b => `${b.artname} ${b.nummer || "(Entwurf)"}`;

async function belegeListe(z, a) {
  const liste = await api(`auftraege/${a.id}/belege`);
  z.innerHTML = `<div class="titel"><h2>Belege</h2><div class="rechts"><button class="btn prim" id="bNeu">+ Neuer Beleg</button></div></div>
    <table class="liste">
      <tr><th>Kundenbeleg</th><th>Datum</th><th>Status</th><th class="r">Netto</th><th class="r">Brutto</th><th class="r">Rest offen</th><th>PDF</th></tr>
      ${liste.map(b => `<tr class="klick" data-id="${b.id}"><td><a href="#/beleg/${b.id}">▸ ${esc(belegName(b))}</a></td><td>${datum(b.datum)}</td><td>${belegStatus(b)}</td>
        <td class="r">${eur(b.netto)}</td><td class="r">${eur(b.brutto)}</td><td class="r">${b.offen == null ? "" : eur(b.offen)}</td>
        <td>${b.pdf ? `<span title="${esc(b.pdf)}">✓</span>` : ""}</td></tr>`).join("")}
    </table>
    ${liste.length ? "" : `<div class="leer">Noch keine Belege. Ein Beleg übernimmt die aktuellen Positionen des Auftrags und friert sie ein.</div>`}
    <p class="hinweis">Angebote, Kostenvoranschläge und Auftragsbestätigungen bekommen sofort ihre Nummer und können jederzeit aus den Positionen aktualisiert werden. Rechnungen sind zunächst Entwurf und bekommen erst beim Festschreiben ihre fortlaufende Nummer; danach sind sie unveränderbar und werden bei Bedarf storniert.</p>`;
  $$("tr.klick", z).forEach(tr => tr.onclick = ev => { if (!ev.target.closest("a")) location.hash = `#/beleg/${tr.dataset.id}`; });
  $("#bNeu").onclick = () => neuerBeleg(a);
}

async function neuerBeleg(a, artVorgabe = "angebot") {
  const alle = await api(`auftraege/${a.id}/belege`).catch(() => []);
  const rechnungen = alle.filter(x => ["rechnung", "abschlag", "korrektur"].includes(x.art) && ["fest", "storniert"].includes(x.status));
  // Anzahlung aus dem Zahlungsplan des letzten Angebots / der letzten Auftragsbestätigung (nur solange noch kein Abschlag erstellt ist)
  const planBeleg = [...alle].reverse().find(x => ["angebot", "kv", "ab"].includes(x.art) && x.konditionen === "plan" && +x.plan_anzahlung);
  const planPz = planBeleg && !alle.some(x => x.art === "abschlag" && x.status !== "storniert") ? +planBeleg.plan_anzahlung : 0;
  const frei = [{text: "", betrag: 0}];
  const freiBinden = hg => {
    const box = $("#nbFrei", hg); if (!box) return;
    box.innerHTML = freiZeilenHtml(frei);
    $$("[data-fz]", box).forEach(el => el.onchange = () => { frei[+el.dataset.fz][el.dataset.fk] = el.dataset.fk === "betrag" ? zahlEin(el.value) : el.value; });
    $$("[data-fzdel]", box).forEach(x => x.onclick = ev => { ev.preventDefault(); frei.splice(+x.dataset.fzdel, 1); freiBinden(hg); });
    $(".fz-neu", box).onclick = ev => { ev.preventDefault(); frei.push({text: "", betrag: 0}); freiBinden(hg); };
  };
  const d = await modal("Neuer Kundenbeleg", `
    <div class="zeile"><label>Belegart</label><div><select name="art" id="nbArt">${belegArtWahl(artVorgabe)}</select></div></div>
    <div class="zeile nb-bezug" style="display:none"><label>Bezug</label><div><select name="bezug_id"><option value="">– ohne –</option>${rechnungen.map(x => `<option value="${x.id}">${esc(x.artname)} ${esc(x.nummer)} vom ${datum(x.datum)} · ${eur(x.brutto)}</option>`).join("")}</select></div></div>
    <div class="zeile nb-modus" style="display:none"><label>Korrektur</label><div class="radio" style="flex-direction:column;align-items:flex-start">
      <label><input type="radio" name="modus" value="differenz" checked> Betrag ändern: nur die Differenz eingeben</label>
      <label><input type="radio" name="modus" value="berichtigen"> Angaben berichtigen, Betrag bleibt (Text, Anschrift, Leistungsdatum …)</label></div></div>
    <div class="zeile voll nb-frei" style="display:none"><label>Zeilen</label><div id="nbFrei" style="display:block"></div></div>
    <p class="hinweis nb-frei" style="display:none" id="nbFreiHin"></p>
    <div class="zeile"><label>Datum</label><div><input type="date" name="datum" value="${heute()}"></div></div>
    <div class="zeile nb-ab" style="display:none"><label>Abschlag</label><div><input name="prozent" class="zahl" style="width:70px" placeholder="30" value="${planPz ? n2(planPz, planPz % 1 ? 2 : 0) : ""}">${planPz ? ` <span class="hinweis">aus dem Zahlungsplan</span>` : ""} % oder <input name="betrag" class="zahl" style="width:100px" placeholder="0,00"> € netto</div></div>
    <div class="zeile nb-plan"><label>Ausführung geplant</label><div><input type="date" name="plan_von" value="${esc(a.plan_von || "")}"><span style="padding-top:5px">bis</span><input type="date" name="plan_bis" value="${esc(a.plan_bis || "")}"></div></div>
    <div class="zeile nb-re" style="display:none"><label>Leistungsdatum</label><div><input type="date" name="leistungsdatum" value="${esc(a.lieferung || "")}"></div></div>
    <p class="hinweis">In der Schlussrechnung wird per Häkchen gewählt, welche festgeschriebenen Abschlagsrechnungen abgezogen werden (vorausgewählt: alle noch nicht verrechneten).</p>`, "Erstellen",
    hg => { freiBinden(hg); $("#nbArt", hg).dispatchEvent(new Event("change", {bubbles: true})); });
  if (!d) return;
  if (d.art.startsWith("v:")) { d.variante = d.art.slice(2); d.art = belegBasis("v:" + d.variante); }
  if (FREI_ARTEN.includes(d.art) && !(d.art === "korrektur" && d.modus === "berichtigen")) d.frei = frei;
  if (d.art !== "korrektur") delete d.modus;
  if (d.art === "korrektur" && !d.bezug_id) return toast("Bitte die Rechnung wählen, die korrigiert wird.", true);
  try {
    if (["angebot", "kv", "ab"].includes(d.art) && d.plan_von && (d.plan_von !== a.plan_von || d.plan_bis !== a.plan_bis))
      await api("auftraege/" + a.id, {method: "PUT", body: {plan_von: d.plan_von, plan_bis: d.plan_bis && d.plan_bis >= d.plan_von ? d.plan_bis : d.plan_von}});
    const r = await api(`auftraege/${a.id}/belege`, {method: "POST", body: {...d, prozent: zahlEin(d.prozent) || null, betrag: zahlEin(d.betrag) || null}});
    location.hash = `#/beleg/${r.id}`;
  } catch (e) { toast(e.message, true); }
}
document.addEventListener("change", e => {
  if (e.target.id !== "nbArt") return;
  const v = belegBasis(e.target.value);
  const berichtigen = v === "korrektur" && ($("[name=modus]:checked") || {}).value === "berichtigen";
  $$(".nb-frei").forEach(x => x.style.display = FREI_ARTEN.includes(v) && !berichtigen ? "" : "none");
  $$(".nb-modus").forEach(x => x.style.display = v === "korrektur" ? "" : "none");
  $$(".nb-bezug").forEach(x => x.style.display = FREI_ARTEN.includes(v) ? "" : "none");
  if ($("#nbFreiHin")) $("#nbFreiHin").textContent = v === "gutschrift" ? "Beträge positiv eingeben; die Gutschrift wird als Minusbetrag gebucht und mit offenen Forderungen des Kunden verrechnet oder ausgezahlt."
    : v === "korrektur" ? "Nur die Differenz zur ursprünglichen Rechnung eingeben: mehr berechnet = positiver Betrag, weniger berechnet = Minusbetrag." : "";
  if (!e.target.dataset.modusGebunden) { e.target.dataset.modusGebunden = 1; $$("[name=modus]").forEach(r => r.onchange = () => e.target.dispatchEvent(new Event("change", {bubbles: true}))); }
  $$(".nb-ab").forEach(x => x.style.display = v === "abschlag" ? "" : "none");
  $$(".nb-re").forEach(x => x.style.display = ["abschlag", "rechnung"].includes(v) ? "" : "none");
  $$(".nb-plan").forEach(x => x.style.display = ["angebot", "kv", "ab"].includes(v) ? "" : "none");
});

// ---------- Druckeinstellungen eines Belegs ----------
function druckEinstellungen(b, dis) {
  const dr = b.druck || {}, art = b.art, re = b.ist_rechnung;
  const JN = [[true, "Ja"], [false, "Nein"]];
  const rg = (k, opts, extra = "") => `<div class="radio" style="flex-wrap:wrap">${opts.map(([v, l]) => `<label><input type="radio" name="dr_${k}" data-dr="${k}" value="${v}" ${String(dr[k]) === String(v) ? "checked" : ""} ${dis}> ${l}</label>`).join("")}${extra}</div>`;
  return `<div class="sektion">Druckeinstellungen <span class="hinweis" style="font-weight:400">· gelten für Vorschau, PDF und E-Mail dieses Belegs</span></div>
    ${re ? "" : zeile("Belegnummer", rg("nummer", [["ja", "Ja"], ["kurz", "Kurze Nr. ohne Jahreszahl"], ["nein", "Nein"]]))}
    ${zeile("Anrede/Gruß", rg("anrede", JN, `<span class="hinweis" style="padding-top:2px">Einleitung, Schlusstext und Gruß</span>`))}
    ${re ? "" : zeile("Positionspreise", rg("preise", JN))}
    ${re ? "" : zeile("Belegsummen", rg("summen", [["ja", "Ja"], ["netto", "Nur Nettosumme"], ["nein", "Nein"]]))}
    ${art === "storno" ? "" : zeile("Konditionen", rg("konditionen", re ? JN : [[true, "Ja"], ["plan", "Zahlungsplan"], [false, "Nein"]], `<span class="hinweis" style="padding-top:2px">${re ? "Zahlungsziel, Skonto, Bankverbindung" : dr.konditionen === "plan" ? "Anzahlung und Restzahlung, Text unter Einstellungen › Belege & Briefbogen" : "Zahlungsbedingungen aus dem Kunden"}</span>`))}
    ${!re && dr.konditionen === "plan" ? zeile("Zahlungsplan", `<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">Anzahlung ${numInp(dr.plan_anzahlung ?? "", `data-drz="plan_anzahlung" style="width:70px;text-align:right" placeholder="40" ${dis}`, 0)} %
      <span style="margin-left:10px">Restzahlung</span> ${numInp(dr.plan_rest ?? (E.zahlungsplan_rest ?? 10), `data-drz="plan_rest" style="width:60px;text-align:right" ${dis}`, 0)} Tage nach Leistung
      <span style="margin-left:10px">Lieferung</span> ${numInp(dr.plan_wochen ?? "", `data-drz="plan_wochen" style="width:60px;text-align:right" placeholder="–" ${dis}`, 0)} Wochen nach Anzahlung <span class="hinweis">(leer = ohne Satz)</span>
      ${+dr.plan_anzahlung ? "" : `<span style="color:var(--rot)">Bitte Anzahlung in % eintragen.</span>`}</div>
      ${(() => { const pv = ((b.daten || {}).auftrag || {}).plan_von; if (!pv || !(+dr.plan_wochen > 0) || !+dr.plan_anzahlung) return "";
        const st = new Date(pv + "T12:00:00"); st.setDate(st.getDate() - Math.round(+dr.plan_wochen * 7)); const sti = st.toISOString().slice(0, 10);
        return sti >= (b.datum || "") ? `<div class="hinweis">Im Kopf steht der geplante Ausführungszeitraum mit „bei Anzahlung bis ${datum(sti)}“.</div>`
          : `<div class="hinweis" style="color:var(--rot)">Der geplante Ausführungszeitraum ist mit ${n2(+dr.plan_wochen, 0)} Wochen ab Anzahlung nicht mehr zu halten (Anzahlung wäre bis ${datum(sti)} nötig gewesen) und wird nicht gedruckt.</div>`; })()}`) : ""}
    ${re && art !== "storno" ? zeile("QR-Code", rg("qr", JN, E.sepa_iban ? `<span class="hinweis" style="padding-top:2px">GiroCode zum Bezahlen mit der Banking-App</span>` : `<span class="hinweis" style="padding-top:2px">erst IBAN unter Einstellungen > Firma eintragen</span>`)) : ""}
    ${art === "rechnung" && E.lohnanteil !== "nie" ? zeile("Arbeitskosten § 35a", rg("lohnanteil", JN, `<span class="hinweis" style="padding-top:2px">Satz mit dem Lohnanteil${b.daten && b.daten.lohnanteil ? " (" + eur(b.daten.lohnanteil.brutto) + " brutto)" : ""} für die Steuererklärung des Kunden</span>`)) : ""}
    ${art === "abschlag" ? zeile("Positionen", rg("ab_positionen", [["ja", "Ja"], ["ohne", "Ohne Preise"], ["nein", "Nein"]], `<span class="hinweis" style="padding-top:2px">Positionen des Auftrags als Grundlage zeigen</span>`)) + zeile("Druck Auftragssumme", rg("ab_summe", JN)) : ""}
    <div class="sektion" style="font-size:13px">Gestaltung</div>
    ${zeile("Platz optimieren", `<div class="radio" style="flex-wrap:wrap"><label><input type="radio" name="dr_kompakt" value="1" ${b.kompakt ? "checked" : ""} ${dis}> Ja</label><label><input type="radio" name="dr_kompakt" value="0" ${b.kompakt ? "" : "checked"} ${dis}> Nein</label><span class="hinweis" style="padding-top:2px">lange Positionen dürfen auf zwei Seiten aufgeteilt werden</span></div>`)}
    ${zeile("Bilder der Positionen", rg("bilder", JN, `<span class="hinweis" style="padding-top:2px">Vorgabe: nur in Angebot, Kostenvoranschlag und Auftragsbestätigung</span>`))}
    ${zeile("Letzte Position + Summen auf einer Seite", rg("zusammen", JN))}
    ${zeile("Letzte Seite unten bündig", rg("unten_buendig", JN, `<span class="hinweis" style="padding-top:2px">Summen, Konditionen, Schlusstext und Gruß stehen unten auf der letzten Seite (PDF und Drucken)</span>`))}
    ${zeile("Briefbogen", rg("briefbogen", [[true, "Mit Briefbogen"], [false, "Ohne Briefbogen"]], `<span class="hinweis" style="padding-top:2px">ohne: für vorgedrucktes Papier</span>`))}
    ${zeile("Unterschrift", rg("unterschrift", JN, `<span class="hinweis" style="padding-top:2px">${E._unterschrift ? "über dem Namen unter dem Gruß" : "noch keine hinterlegt (Einstellungen > Belege & Briefbogen)"}</span>`))}`;
}
function druckBinden(b, bid, neuVorschau) {
  $$("[data-dr]").forEach(el => el.onchange = async () => {
    const k = el.dataset.dr, v = el.value === "true" ? true : el.value === "false" ? false : el.value;
    try {
      await api("belege/" + bid, {method: "PUT", body: {druck: {[k]: v}}});
      b.druck[k] = v;
      if (k === "konditionen") return ansichtBeleg(bid);   // Felder für den Zahlungsplan ein- oder ausblenden
      if (b.art === "abschlag" && k.startsWith("ab_")) return ansichtBeleg(bid);
      neuVorschau(true);
    } catch (e) { toast(e.message, true); }
  });
  $$("[data-drz]").forEach(el => el.onchange = async () => {
    const k = el.dataset.drz, v = el.value.trim() === "" ? "" : zahlEin(el.value);
    try { await api("belege/" + bid, {method: "PUT", body: {druck: {[k]: v}}}); b.druck[k] = v; if (k === "plan_anzahlung") return ansichtBeleg(bid); neuVorschau(true); }
    catch (e) { toast(e.message, true); }
  });
  $$("[name=dr_kompakt]").forEach(el => el.onchange = async () => { await api("belege/" + bid, {method: "PUT", body: {kompakt: el.value === "1"}}); neuVorschau(true); });
}

async function ansichtBeleg(bid) {
  const b = await api("belege/" + bid);
  const a = b.auftrag;
  auftragKopf(a, "belege", {zeile2: `${esc(belegName(b))} · ${datum(b.datum)} · ${belegStatus(b)}`});
  const z = $("#inhalt");
  const fest = b.status === "fest" || b.status === "storniert";
  const gesperrt = fest || !!b.daten.unterschrift;
  const dis = gesperrt ? "disabled" : "";
  const knoepfe = [
    b.status !== "storniert" || b.art === "storno" ? `<button class="btn prim" id="bMail" title="Beleg als PDF per E-Mail an den Kunden senden">✉ Per E-Mail senden</button>` : "",
    `<a class="btn" href="/druck/${bid}.pdf" target="_blank">PDF ansehen</a>`,
    `<a class="btn" href="/druck/${bid}?drucken=1" target="_blank">Drucken</a>`,
    `<button class="btn" id="bPdf">PDF in Projektordner</button>`,
    ["angebot", "kv"].includes(b.art) && !b.versendet ? `<button class="btn" id="bVers" title="Das Angebot wurde auf anderem Weg übergeben (Post, persönlich, eigenes E-Mail-Programm). Erst dann zählt es auf der Startseite als offenes Angebot.">✓ Als versendet vermerken</button>` : "",
    !fest && !b.daten.unterschrift && (!FREI_ARTEN.includes(b.art) || b.daten.modus === "berichtigen") ? `<button class="btn" id="bAkt" title="${b.daten.modus === "berichtigen" ? "Positionstexte und Kundendaten neu aus dem Auftrag; der Betrag muss gleich bleiben" : "Positionen und Summen neu aus dem Auftrag übernehmen"}">Aus Positionen aktualisieren</button>` : "",
    ["ab", "lieferschein", "abnahme"].includes(b.art) && !b.daten.unterschrift ? `<a class="btn" href="#/unterschrift/${bid}" title="Auf dem Tablet vom Kunden unterschreiben lassen">✍ Unterschreiben lassen</a>` : "",
    b.ist_rechnung && b.status === "entwurf" ? `<button class="btn prim" id="bFest">Festschreiben</button>` : "",
    b.ist_rechnung && fest ? `<a class="btn" href="/api/belege/${bid}/xrechnung.xml" title="E-Rechnung im XRechnung-Format, z. B. für öffentliche Auftraggeber oder Firmen, die XRechnung verlangen">XRechnung</a>` : "",
    b.status === "fest" && ["rechnung", "abschlag", "gutschrift", "korrektur"].includes(b.art) && b.daten.modus !== "berichtigen" ? `<button class="btn rot" id="bStorno">Stornieren</button>` : "",
    !fest && !b.daten.unterschrift ? `<button class="ib" id="bDel" title="Beleg löschen">${ic("loeschen")}</button>` : "",
  ].join("");
  const s = b.daten.summen || {};
  const op = b.op;
  z.innerHTML = `
    <div class="titel"><h2>${esc(belegName(b))}</h2><span class="speicher"></span><div class="rechts" style="flex-wrap:wrap">${knoepfe}</div></div>
    ${b.versendet ? (b.versendet_an || "").startsWith("Vermerk: ")
      ? `<div class="hinweis" style="margin:-4px 0 8px">✓ Als versendet vermerkt (${esc(b.versendet_an.slice(9))}) am ${datum(b.versendet.slice(0, 10))} um ${b.versendet.slice(11, 16)} Uhr · <a href="#" id="bVersZur">Vermerk zurücknehmen</a></div>`
      : `<div class="hinweis" style="margin:-4px 0 8px">✉ Per E-Mail gesendet am ${datum(b.versendet.slice(0, 10))} um ${b.versendet.slice(11, 16)} Uhr an ${esc(b.versendet_an)}</div>`
      : ["angebot", "kv"].includes(b.art) ? `<div class="hinweis" style="margin:-4px 0 8px">Noch nicht versendet. Auf der Startseite zählt der Beleg erst nach dem Versand (per E-Mail aus dem Programm oder „Als versendet vermerken“).</div>` : ""}
    ${b.ist_rechnung ? `<div id="erInfo"></div>` : ""}
    ${b.daten.unterschrift ? `<div class="kachel" style="margin-bottom:10px">✍ Digital unterschrieben von <b>${esc(b.daten.unterschrift.name)}</b>${b.daten.unterschrift.ort ? " in " + esc(b.daten.unterschrift.ort) : ""} am ${datum(b.daten.unterschrift.zeit.slice(0, 10))} um ${b.daten.unterschrift.zeit.slice(11, 16)} Uhr. Der Beleg ist damit endgültig gesperrt und kann nicht gelöscht werden; für Änderungen einen neuen Beleg erstellen.</div>` : ""}
    ${b.art === "abnahme" && !b.daten.unterschrift ? `<div class="form" id="fAbn" style="margin-bottom:10px">
      ${zeile("Abnahme", `<div class="radio"><label><input type="radio" name="abVb" value="0" ${(b.daten.abnahme || {}).vorbehalt ? "" : "checked"}> ohne Vorbehalt</label><label><input type="radio" name="abVb" value="1" ${(b.daten.abnahme || {}).vorbehalt ? "checked" : ""}> mit Vorbehalt</label></div>`)}
      ${zeile("Mängel", `<textarea id="abM" rows="2">${esc((b.daten.abnahme || {}).maengel || "")}</textarea>`, true)}
      ${zeile("Restarbeiten", `<textarea id="abR" rows="2">${esc((b.daten.abnahme || {}).restarbeiten || "")}</textarea>`, true)}</div>` : ""}
    ${fest ? `<div class="kachel" style="margin-bottom:10px">Dieser Beleg ist ${b.status === "storniert" ? "<b>storniert</b>" : "<b>festgeschrieben</b>"} und kann nicht mehr geändert werden.${b.bezug_id && b.art === "storno" ? ` Storno zu <a href="#/beleg/${b.bezug_id}">Rechnung</a>.` : ""}</div>` : ""}
    ${b.daten.bezug && b.art !== "storno" ? `<div class="hinweis" style="margin:-4px 0 8px">Bezug: <a href="#/beleg/${b.daten.bezug.id || b.bezug_id}">Rechnung ${esc(b.daten.bezug.nummer)} vom ${datum(b.daten.bezug.datum)}</a></div>` : ""}
    ${b.daten.modus === "berichtigen" ? `<div class="hinweis" style="margin:-4px 0 8px">Berichtigung ohne Betragsänderung: ersetzt die Rechnung mit allen Positionen und Summen, ändert aber weder Umsatz noch offene Posten. Anschrift, Datum, Leistungsdatum, Betreff und Texte hier ändern; Positionstexte im Auftrag ändern und dann „Aus Positionen aktualisieren“.</div>` : ""}
    ${b.daten.steuer === "13b" ? `<div class="hinweis" style="margin:-4px 0 8px">§ 13b UStG: ohne Umsatzsteuer, mit Hinweis auf die Steuerschuldnerschaft des Leistungsempfängers.</div>` : ""}
    <div class="form" id="f">
      ${zeile("Datum", `<input type="date" data-f="datum" value="${esc(b.datum)}" ${dis}>`)}
      ${b.ist_rechnung ? zeile("Leistungsdatum", `<input type="date" data-f="leistungsdatum" value="${esc(b.leistungsdatum)}" ${dis}>`) : zeile("Auftrag", `<a href="#/auftrag/${a.id}/positionen" style="padding-top:5px">${esc(a.nummer)} · Positionen bearbeiten</a>`)}
      ${["angebot", "kv", "ab"].includes(b.art) ? zeile("Ausführung geplant", `<input type="date" id="bPlV" value="${esc(a.plan_von || "")}"><span style="padding-top:5px">bis</span><input type="date" id="bPlB" value="${esc(a.plan_bis || "")}"><span class="hinweis" style="padding-top:5px">erscheint im Kalender${E.zeitraum_drucken !== false ? " und als KW auf dem Beleg" : ""}</span>`, true) : ""}
      ${zeile("Betreff", `<input data-f="betreff" value="${esc(b.betreff)}" ${dis}>`, true)}
      ${zeile("Anschrift", `<textarea data-f="anschrift" rows="4" ${dis}>${esc(b.anschrift)}</textarea>`)}
      ${b.ist_rechnung ? zeile("Zahlungsziel", `<input data-f="zahlungsziel" type="number" value="${b.zahlungsziel}" style="width:80px;flex:0 0 auto" ${dis}> Tage${b.faellig ? ` · fällig ${datum(b.faellig)}` : ""}`) : zeile("", "")}
      ${b.art === "abschlag" && !fest ? zeile("Abschlag", `<input id="abPz" class="zahl" style="width:70px" value="${b.daten.abschlag?.prozent ? n2(b.daten.abschlag.prozent) : ""}"> % oder <input id="abBt" class="zahl" style="width:100px" value="${b.daten.abschlag?.betrag ? n2(b.daten.abschlag.betrag) : ""}"> € netto`, true) : ""}
      ${FREI_ARTEN.includes(b.art) && b.daten.modus !== "berichtigen" ? `<div class="zeile voll"><label>Zeilen</label><div id="bFrei" style="display:block"></div></div>` : ""}
      ${zeile("Einleitung", rtEditor(b.einleitung, `data-f="einleitung"${gesperrt ? ' contenteditable="false"' : ""}`), true)}
      ${zeile("Schlusstext", rtEditor(b.schluss, `data-f="schluss"${gesperrt ? ' contenteditable="false"' : ""}`), true)}
      ${b.art === "rechnung" && (b.daten.abschlaege || []).length ? `<div class="sektion">Abschlagsrechnungen verrechnen</div>
        ${zeile("Abziehen", `<div class="spalte">${b.daten.abschlaege.map(x => `<label style="display:flex;gap:8px;align-items:center"><input type="checkbox" data-abz="${x.id}" ${x.verrechnen ? "checked" : ""} ${dis || x.anderswo ? "disabled" : ""} style="flex:0 0 auto">
          Abschlagsrechnung ${esc(x.nummer)} vom ${datum(x.datum)} · ${eur(x.brutto)} brutto${x.anderswo ? ` <span class="hinweis">(schon in einer anderen Rechnung verrechnet)</span>` : ""}</label>`).join("")}
          <span class="hinweis">Angehakte Abschläge werden in dieser Rechnung abgezogen. Haken weg, wenn ein Abschlag erst in einer späteren Rechnung verrechnet werden soll.</span></div>`, true)}` : ""}
      ${druckEinstellungen(b, dis)}
      <div class="sektion">Summen</div>
      <div class="zeile voll"><label></label><div style="display:block;padding:8px 10px">
        Netto <b>${eur(s.netto || 0)}</b> · ${n2(s.ust_satz || 0, 0)} % USt <b>${eur(s.ust || 0)}</b> · Brutto <b>${eur(s.brutto || 0)}</b>
        ${(b.daten.abzuege || []).length ? ` · abzüglich Abschläge ${eur(s.abzug_brutto)} · <b>Zahlbetrag ${eur(s.zahlbetrag)}</b>` : ""}
        ${op ? `<br>Offener Posten: noch offen <b>${eur(op.offen)}</b> · <a href="#/auftrag/${a.id}/op">Zahlung erfassen</a>` : ""}
        ${b.pdf ? `<br><span class="hinweis">PDF: ${esc(b.pdf)}</span>` : ""}
      </div></div>
    </div>
    <div style="position:relative;margin-top:14px"><div id="vsInfo" class="hinweis" style="position:absolute;top:8px;right:12px;background:#fff;padding:2px 8px;border-radius:4px"></div>
    <div id="vorschau" style="width:100%;min-height:400px;max-height:1150px;overflow:auto;border:1px solid var(--linie);border-radius:6px;background:#8a8a8a;padding:14px 0"></div></div>`;
  let vsTimer, vsLauf = 0;
  const neuVorschau = (sofort) => {
    clearTimeout(vsTimer);
    vsTimer = setTimeout(() => vorschauZeichnen(bid, ++vsLauf, () => vsLauf), sofort ? 0 : 1200);
  };
  neuVorschau(true);
  if (!gesperrt) {
    autospeichern($("#f"), "belege/" + bid, () => neuVorschau());
    const ab = () => api("belege/" + bid, {method: "PUT", body: {prozent: zahlEin($("#abPz").value) || null, betrag: zahlEin($("#abBt").value) || null}}).then(() => ansichtBeleg(bid)).catch(e => toast(e.message, true));
    $("#abPz")?.addEventListener("change", ab); $("#abBt")?.addEventListener("change", ab);
  }
  druckBinden(b, bid, neuVorschau);
  if ($("#bFrei")) {   // Zeilen von Gutschrift / Rechnungskorrektur
    const fz = (b.daten.frei || []).map(x => ({...x}));
    const fzZeichnen = () => {
      const box = $("#bFrei"); box.innerHTML = freiZeilenHtml(fz, dis);
      if (dis) return;
      const sp = () => api("belege/" + bid, {method: "PUT", body: {frei: fz}}).then(() => ansichtBeleg(bid)).catch(e => toast(e.message, true));
      $$("[data-fz]", box).forEach(el => el.onchange = () => { fz[+el.dataset.fz][el.dataset.fk] = el.dataset.fk === "betrag" ? zahlEin(el.value) : el.value; sp(); });
      $$("[data-fzdel]", box).forEach(x => x.onclick = ev => { ev.preventDefault(); fz.splice(+x.dataset.fzdel, 1); sp(); });
      $(".fz-neu", box).onclick = ev => { ev.preventDefault(); fz.push({text: "", betrag: 0}); fzZeichnen(); };
    };
    fzZeichnen();
  }

  if ($("#fAbn")) { let t; const sp = () => { clearTimeout(t); t = setTimeout(async () => { try { await api("belege/" + bid, {method: "PUT", body: {abnahme: {vorbehalt: ($$("[name=abVb]").find(x => x.checked) || {}).value === "1", maengel: $("#abM").value, restarbeiten: $("#abR").value}}}); neuVorschau(); } catch (e) { toast(e.message, true); } }, 600); };
    $$("[name=abVb]").forEach(x => x.onchange = sp); $("#abM").oninput = sp; $("#abR").oninput = sp; }
  $$("[data-abz]").forEach(c => c.onchange = async () => {
    const aus = $$("[data-abz]").filter(x => !x.checked && !x.disabled).map(x => +x.dataset.abz);
    try { await api("belege/" + bid, {method: "PUT", body: {druck: {abschlaege_aus: aus}}}); toast("Verrechnung geändert"); ansichtBeleg(bid); }
    catch (e) { toast(e.message, true); }
  });
  const plSp = async () => {
    const v = $("#bPlV").value, bb = $("#bPlB").value && $("#bPlB").value >= v ? $("#bPlB").value : v;
    if ($("#bPlB").value !== bb) $("#bPlB").value = bb;
    await api("auftraege/" + a.id, {method: "PUT", body: {plan_von: v, plan_bis: v ? bb : ""}});
    await api(`belege/${bid}/aktualisieren`, {method: "POST"}); toast("Zeitraum gespeichert"); neuVorschau();
  };
  $("#bPlV")?.addEventListener("change", plSp); $("#bPlB")?.addEventListener("change", plSp);
  if (b.ist_rechnung) api(`belege/${bid}/erechnung?format=${(b.daten.kunde || {}).rechnungsformat === "XRechnung" ? "xrechnung" : "zugferd"}`).then(r => {
    const el = $("#erInfo"); if (!el) return;
    const xr = (b.daten.kunde || {}).rechnungsformat === "XRechnung";
    el.innerHTML = r.fehler.length
      ? `<div class="kachel" style="margin-bottom:10px;border-left:4px solid var(--rot)"><b>E-Rechnung noch nicht möglich:</b> ${esc(r.fehler.join(" "))}</div>`
      : `<div class="hinweis" style="margin:-4px 0 10px">✓ E-Rechnung: ${fest ? "Das PDF enthält die ZUGFeRD-Daten" : "Beim Festschreiben bekommt das PDF die ZUGFeRD-Daten"}${xr ? ", zusätzlich wird eine XRechnung-Datei abgelegt" : ""}. <a href="#" id="erXml">XML ansehen und prüfen ›</a></div>`;
    const ex = $("#erXml"); if (ex) ex.onclick = ev => { ev.preventDefault(); xmlAnsicht(`xml/beleg/${bid}${xr ? "?format=xrechnung" : ""}`, `E-Rechnung ${b.nummer || "(Entwurf)"}`); };
  }).catch(() => {});
  const pdfMeldung = r => {
    if (r.fehler) return toast(r.fehler, true);
    toast((r.projekt_rel ? `PDF gespeichert: ${r.projekt_rel}` : `PDF gespeichert (${r.hinweis || "nur im Archiv"})`) + (r.xrechnung ? " · XRechnung-Datei liegt daneben" : ""));
    if (r.status && r.status.length) setTimeout(() => toast("Status gesetzt · " + r.status.join(" · ")), 1800);
    if (r.erechnung_hinweis) setTimeout(() => toast(r.erechnung_hinweis, true), 2500);
    pbRel[a.id] = r.projekt_rel && r.projekt_rel.includes("/") ? r.projekt_rel.slice(0, r.projekt_rel.lastIndexOf("/")) : (pbRel[a.id] || "");
  };
  const bm = $("#bMail"); if (bm) bm.onclick = () => belegMailen(bid, b);
  $("#bPdf").onclick = async () => {
    const btn = $("#bPdf"); btn.disabled = true; btn.textContent = "PDF wird erstellt …";
    try { pdfMeldung(await api(`belege/${bid}/pdf`, {method: "POST"})); ansichtBeleg(bid); }
    catch (e) { toast(e.message, true); btn.disabled = false; btn.textContent = "PDF in Projektordner"; }
  };
  $("#bVers")?.addEventListener("click", async () => {
    const wege = ["per Post", "persönlich übergeben", "eigenes E-Mail-Programm", "sonstiger Weg"];
    const r = await modal("Als versendet vermerken", `<div class="zeile"><label>Weg</label><div><select name="weg">${wege.map(w => `<option>${w}</option>`).join("")}</select></div></div>
      <p class="hinweis">Danach zählt der Beleg auf der Startseite als offenes Angebot und der Auftragsstatus wird nachgezogen.</p>`, "Vermerken");
    if (!r) return;
    await api(`belege/${bid}/versendet`, {method: "POST", body: {weg: r.weg}}); toast("Als versendet vermerkt"); ansichtBeleg(bid);
  });
  $("#bVersZur")?.addEventListener("click", async e => {
    e.preventDefault();
    await api(`belege/${bid}/versendet`, {method: "DELETE"}); toast("Vermerk zurückgenommen"); ansichtBeleg(bid);
  });
  $("#bAkt")?.addEventListener("click", async () => { await api(`belege/${bid}/aktualisieren`, {method: "POST"}); toast("Aus Positionen aktualisiert"); ansichtBeleg(bid); });
  $("#bFest")?.addEventListener("click", async () => {
    if (!await frage(`Rechnung jetzt festschreiben?\n\nSie bekommt ihre endgültige Nummer, wird als PDF archiviert und kann danach nicht mehr geändert werden (nur noch stornieren).`)) return;
    const btn = $("#bFest"); btn.disabled = true; btn.textContent = "wird festgeschrieben …";
    try { const r = await api(`belege/${bid}/festschreiben`, {method: "POST"}); toast(`${r.beleg.artname} ${r.beleg.nummer} festgeschrieben`); if (r.pdf) pdfMeldung(r.pdf); ansichtBeleg(bid); }
    catch (e) { toast(e.message, true); btn.disabled = false; btn.textContent = "Festschreiben"; }
  });
  $("#bStorno")?.addEventListener("click", async () => {
    if (!await frage(`${belegName(b)} stornieren?\n\nEs wird eine Stornorechnung mit eigener Nummer erstellt und der offene Posten ausgebucht.`)) return;
    try { const r = await api(`belege/${bid}/storno`, {method: "POST"}); toast(`Stornorechnung ${r.beleg.nummer} erstellt`); if (r.pdf) pdfMeldung(r.pdf); location.hash = `#/beleg/${r.beleg.id}`; }
    catch (e) { toast(e.message, true); }
  });
  $("#bDel")?.addEventListener("click", async () => {
    if (!await frage(`${belegName(b)} löschen?`)) return;
    try { await api("belege/" + bid, {method: "DELETE"}); toast("Beleg gelöscht"); location.hash = `#/auftrag/${a.id}/belege`; }
    catch (e) { toast(e.message, true); }
  });
}

// ---------- Offene Posten (ersetzt die einfache Liste) ----------
const opFilter = {status: "offen"};
async function opListeNeu(ziel, {kunde = null, auftrag = null} = {}) {
  const q = new URLSearchParams({status: opFilter.status, ...(kunde ? {kunde: kunde.id} : {}), ...(auftrag ? {auftrag: auftrag.id} : {})});
  const liste = await api("offeneposten?" + q);
  sortierung.op2 ||= {k: "faellig", ab: false};
  const t = tabelle("op2", [
    {k: "nummer", t: "Nummer", f: o => `<span class="nw">${o.beleg_id ? `<a href="#/beleg/${o.beleg_id}">${esc(o.nummer)}</a>` : esc(o.nummer)}</span>`},
    {k: "art", t: "Art"},
    ...(kunde || auftrag ? [] : [{k: "kunde", t: "Kunde", f: o => `<a href="#/kunde/${o.kunde_id}">${esc(o.kunde || "")}</a>`}]),
    ...(auftrag ? [] : [{k: "auftragsnr", t: "Auftrag", f: o => o.auftrag_id ? `<a class="nw" href="#/auftrag/${o.auftrag_id}">${esc(o.auftragsnr || "")}</a>` : ""}]),
    {k: "datum", t: "Datum", f: o => datum(o.datum)},
    {k: "betrag", t: "Betrag", r: 1, f: o => `<span class="nw">${eur(o.betrag)}</span>`},
    {k: "faellig", t: "Fällig", f: o => o.offen > 0.004 && o.faellig && o.faellig < heute() ? `<b style="color:var(--rot)">${datum(o.faellig)}</b>` : datum(o.faellig)},
    {k: "offen", t: "Offen", r: 1, f: o => o.belegstatus === "storniert" ? `<span class="hinweis" title="${o.storno_nr ? "storniert durch " + esc(o.storno_nr) : "storniert"}">storniert${o.storno_nr ? "<br>" + esc(o.storno_nr) : ""}</span>`
      : o.belegart === "storno" && Math.abs(o.offen) < 0.005 ? `<span class="hinweis">Storno${o.bezug_nr ? `<br><span class="nw">zu ${esc(o.bezug_nr)}</span>` : ""}</span>`
      : Math.abs(o.offen) < 0.005 ? (o.mahnkosten > 0.004 ? `<span title="Rechnung bezahlt, Mahnkosten offen">${eur(o.mahnkosten)} Mahnk.</span>` : `<span style="color:var(--gruen)">bezahlt</span>`) : `<b class="nw">${eur(o.offen)}</b>${o.mahnkosten > 0.004 ? `<div class="hinweis nw">+ ${eur(o.mahnkosten)} Mahnk.</div>` : ""}`},
    {k: "mahnstufe", t: "Mahnung", f: o => mahnStand(o)},
    {k: "id", t: "", f: o => `<span style="display:flex;gap:4px;justify-content:flex-end">${mahnKnopf(o)}` + (Math.abs(o.offen) >= 0.005 || o.mahnkosten > 0.004 ? `<button class="btn" data-zahl="${o.id}">${o.offen < 0 ? "Erstattung" : "Zahlung"}</button>` : "")
      + (Math.abs(o.offen) < 0.005 && o.mahnkosten > 0.004 ? `<button class="btn" data-erlass="${o.id}" title="Mahnkosten nicht mehr einfordern">erlassen</button>` : "")
      + (Math.abs(o.offen) < 0.005 && !(o.mahnkosten > 0.004) ? `<button class="btn" data-hist="${o.id}">Zahlungen</button>` : "")
      + (o.betrag - o.offen > 0.004 && o.betrag > 0 && o.belegstatus !== "storniert" ? `<button class="btn" data-zbest="${o.id}" title="Zahlungsbestätigung per E-Mail an den Kunden (zur letzten gebuchten Zahlung)">✉</button>` : "") + `</span>`},
  ], liste, {leer: opFilter.status === "offen" ? "Keine offenen Posten." : "Keine Einträge."});
  const summe = liste.reduce((s, o) => s + o.offen, 0);
  const bezahltSumme = liste.filter(o => o.belegstatus !== "storniert" && o.belegart !== "storno").reduce((s, o) => s + (o.betrag - o.offen), 0);
  ziel.innerHTML = `<div class="titel"><h2>Offene Posten</h2>
      <div class="such"><select id="opSt">${[["offen","Offene"],["faellig","Überfällige"],["erledigt","Bezahlte"],["storniert","Stornierte"],["alle","Alle"]].map(([v, l]) => `<option value="${v}" ${v === opFilter.status ? "selected" : ""}>${l}</option>`).join("")}</select></div></div>
    ${t.html}${liste.length ? `<div class="hinweis" style="text-align:right;margin-top:6px">${liste.length} Posten · ${opFilter.status === "erledigt" ? `bezahlt gesamt <b>${eur(bezahltSumme)}</b> brutto` : opFilter.status === "storniert" ? "stornierte Rechnungen zählen nicht zum Umsatz" : `offen gesamt <b>${eur(summe)}</b>`}</div>` : ""}
    <div id="opMahn"></div>`;
  const neu = () => opListeNeu(ziel, {kunde, auftrag});
  t.binden(neu);
  $$("[data-mahnen]", ziel).forEach(b => b.onclick = () => mahnungErstellen(+b.dataset.mahnen, neu));
  $$("[data-erlass]", ziel).forEach(b => b.onclick = async () => {
    if (!await frage("Mahnkosten erlassen?\n\nDie offenen Mahnkosten dieses Postens werden auf 0 gesetzt und nicht mehr eingefordert.", {ok: "Erlassen"})) return;
    await api(`offeneposten/${b.dataset.erlass}/mahnkosten_erlassen`, {method: "POST", body: {}}); toast("Mahnkosten erlassen"); neu();
  });
  if (kunde || auftrag) {
    const ms = await api("mahnungen?" + new URLSearchParams(kunde ? {kunde: kunde.id} : {auftrag: auftrag.id}));
    if (ms.length) {
      sortierung.mahnk ||= {k: "datum", ab: true};
      const tm = mahnungenTabelle("mahnk", ms, false);
      $("#opMahn", ziel).innerHTML = `<h3 style="margin-top:22px">Mahnungen</h3>${tm.html}`;
      tm.binden(neu); mahnungenBinden(ziel, ms, neu);
    }
  }
  $("#opSt").onchange = e => { opFilter.status = e.target.value; opListeNeu(ziel, {kunde, auftrag}); };
  $$("[data-zahl]", ziel).forEach(b => b.onclick = () => zahlungBuchen(liste.find(x => x.id === +b.dataset.zahl), neu));
  $$("[data-zbest]", ziel).forEach(b => b.onclick = () => { const o = liste.find(x => x.id === +b.dataset.zbest); mailDialog(`offeneposten/${o.id}`, `Zahlungsbestätigung ${o.nummer}`); });
  $$("[data-hist]", ziel).forEach(b => b.onclick = async () => {
    const z = await api(`offeneposten/${b.dataset.hist}/zahlungen`);
    await modal("Zahlungen", z.length ? `<table class="liste">${z.map(x => `<tr><td>${datum(x.datum)}</td><td>${esc(x.art)}</td><td class="r">${eur(x.betrag)}</td><td>${esc(x.bemerkung)}</td><td><button class="btn rot" data-zedel="${x.id}" type="button">✕</button></td></tr>`).join("")}</table>` : `<div class="hinweis">Keine Zahlungen gebucht (ausgeglichen durch Storno/Verrechnung).</div>`, "Schließen");
    opListeNeu(ziel, {kunde, auftrag});
  });
}
document.addEventListener("click", async e => {
  // nur die Löschknöpfe im Fenster „Zahlungen“ (eigener Attributname, damit andere Listen nicht betroffen sind)
  const b = e.target.closest(".modal [data-zedel]"); if (!b) return;
  if (!await frage("Zahlung löschen? Der Betrag ist danach wieder offen.")) return;
  await api("zahlungseingaenge/" + b.dataset.zedel, {method: "DELETE"}); b.closest("tr").remove(); toast("Zahlung gelöscht");
});

// ---------- Belegtexte (Einstellungen) ----------
function belegtexteVorgabe(z) {
  const STANDARD = {
    angebot: ["{anrede}\n\nvielen Dank für Ihre Anfrage. Gerne biete ich Ihnen die folgenden Arbeiten an:", "Ich würde mich freuen, den Auftrag für Sie ausführen zu dürfen. Dieses Angebot ist gültig bis {gueltig_bis}.\n\nMit freundlichen Grüßen"],
    kv: ["{anrede}\n\ngerne erstelle ich Ihnen den folgenden Kostenvoranschlag:", "Dieser Kostenvoranschlag ist unverbindlich. Die tatsächlichen Kosten können abweichen; eine wesentliche Überschreitung zeige ich Ihnen unverzüglich an.\n\nMit freundlichen Grüßen"],
    ab: ["{anrede}\n\nvielen Dank für Ihren Auftrag, den ich hiermit wie folgt bestätige:", "Mit freundlichen Grüßen"],
    lieferschein: ["Ich liefere Ihnen heute:", "Ware vollständig und in einwandfreiem Zustand erhalten:\n\n\n______________________________\nDatum, Unterschrift"],
    abnahme: ["Für den Auftrag „{auftrag}“ wurden die folgenden Leistungen gemeinsam besichtigt und geprüft:", "Mit der Unterschrift erklärt der Auftraggeber die Abnahme der oben aufgeführten Leistungen. Ab der Abnahme beginnt die Gewährleistungsfrist; die Gefahr geht auf den Auftraggeber über. Aufgeführte Mängel und Restarbeiten werden in angemessener Frist erledigt."],
    abschlag: ["{anrede}\n\nfür den Auftrag „{auftrag}“ berechne ich Ihnen vereinbarungsgemäß folgende Abschlagszahlung:", "Vielen Dank!\n\nMit freundlichen Grüßen"],
    rechnung: ["{anrede}\n\nfür die ausgeführten Arbeiten erlaube ich mir, Ihnen Folgendes in Rechnung zu stellen:", "Vielen Dank für Ihren Auftrag!\n\nMit freundlichen Grüßen"],
    storno: ["{anrede}\n\nhiermit storniere ich die Rechnung {bezug} vom {bezugdatum}.", "Mit freundlichen Grüßen"],
    gutschrift: ["{anrede}\n\nfür den Auftrag „{auftrag}“ schreibe ich Ihnen folgenden Betrag gut:", "Den Betrag verrechne ich mit offenen Forderungen oder überweise ihn auf Ihr Konto.\n\nMit freundlichen Grüßen"],
    korrektur: ["{anrede}\n\nzur Rechnung {bezug} vom {bezugdatum} berichtige ich wie folgt:", "Mit freundlichen Grüßen"],
    korrektur_berichtigen: ["{anrede}\n\ndiese Rechnungskorrektur ersetzt die Rechnung {bezug} vom {bezugdatum}. Berichtigt wurden die Angaben der Rechnung; der Rechnungsbetrag bleibt unverändert.", "Bereits geleistete Zahlungen sind berücksichtigt. Ein noch offener Betrag ist weiterhin unter der Rechnungsnummer {bezug} zu zahlen.\n\nMit freundlichen Grüßen"],
  };
  const namen = {angebot: "Angebot", kv: "Kostenvoranschlag", ab: "Auftragsbestätigung", lieferschein: "Lieferschein", abnahme: "Abnahmeprotokoll", abschlag: "Abschlagsrechnung", rechnung: "Rechnung", storno: "Stornorechnung", gutschrift: "Gutschrift", korrektur: "Rechnungskorrektur", korrektur_berichtigen: "Rechnungskorrektur (Angaben berichtigen)"};
  const t = JSON.parse(JSON.stringify(E.beleg_texte || {}));
  for (const k in STANDARD) t[k] ||= {einleitung: STANDARD[k][0], schluss: STANDARD[k][1]};
  const sp = speicherer("einstellungen", r => { E = {...E, ...r}; });
  const mstd = E._mail_texte_standard || {};
  const mt = {}; for (const k in STANDARD) mt[k] = {...(mstd[k] || {betreff: "", text: ""}), ...((E.mail_texte || {})[k] || {})};
  z.innerHTML = `<div class="titel"><h2>Belegtexte</h2><span class="speicher"></span></div>
    <p class="hinweis" style="margin-top:-6px">Platzhalter siehe <a href="#/einstellungen/texte/variablen">Belegvariablen</a>, z. B. {anrede}, {auftrag}, {gueltig_bis}, {bezug}. Die Signatur wird an E-Mails automatisch angehängt. Die Texte gelten für neu erstellte Belege und lassen sich im einzelnen Beleg noch anpassen. Eigene Belegarten mit eigenen Texten: <a href="#/einstellungen/texte/belegarten">Eigene Belegarten</a>.</p>
    <div class="form" style="max-width:520px;margin-bottom:10px">${zeile("Angebote gültig", `<span><input type="number" min="0" max="365" id="btGueltig" value="${esc(E.angebot_gueltig_tage ?? 7)}" style="width:80px"> Tage ab Belegdatum <span class="hinweis">({gueltig_bis})</span></span>`)}</div>
    ${Object.keys(STANDARD).map(k => `<div class="kachel" style="margin-bottom:10px"><h4>${namen[k]}</h4>
      <div class="form" style="grid-template-columns:1fr">${zeile("Einleitung", rtEditor(t[k].einleitung, `data-k="${k}" data-t="einleitung"`, "klein"))}${zeile("Schlusstext", rtEditor(t[k].schluss, `data-k="${k}" data-t="schluss"`, "klein"))}${zeile("E-Mail-Betreff", `<input data-mk="${k}" data-mt="betreff" value="${esc(mt[k].betreff)}">`)}${zeile("E-Mail-Text", `<textarea data-mk="${k}" data-mt="text" rows="6" style="width:100%;font:inherit">${esc(mt[k].text)}</textarea>`)}</div></div>`).join("")}`;
  $$("[data-k]", z).forEach(el => el.oninput = () => { t[el.dataset.k][el.dataset.t] = el.innerHTML; sp.setze("beleg_texte", t); });
  $$("[data-mk]", z).forEach(el => el.oninput = () => { mt[el.dataset.mk][el.dataset.mt] = el.value; sp.setze("mail_texte", mt); });
  $("#btGueltig", z).oninput = e => sp.setze("angebot_gueltig_tage", Math.max(0, parseInt(e.target.value, 10) || 0));
}

// ---------- Eigene Belegarten (Varianten der Grundarten) ----------
function belegartenVorgabe(z) {
  const V = (E.beleg_varianten || []).map(x => ({...x}));
  const GRUND = BELEGARTEN_UI.map(([k, l]) => [k, l.replace(" / Schlussrechnung", "")]);
  const preise = k => !["lieferschein", "abnahme"].includes(k);
  const speichern = async neu => { try { E = await api("einstellungen", {method: "PUT", body: {beleg_varianten: V}}); $(".speicher", z).textContent = "gespeichert ✓"; if (neu) belegartenVorgabe(z); } catch (e) { toast(e.message, true); } };
  z.innerHTML = `<div class="titel"><h2>Eigene Belegarten</h2><span class="speicher"></span></div>
    <p class="hinweis" style="margin-top:-6px">Eine eigene Belegart beruht auf einer Grundart und übernimmt deren Verhalten (Nummernkreis, Festschreiben, offene Posten, E-Rechnung). Sie hat eine eigene Bezeichnung, die als Überschrift auf dem Beleg steht, eine Bemerkung für die Auswahlliste und auf Wunsch eigene Texte (leer = Texte der Grundart). Mit „§ 13b UStG“ wird ohne Umsatzsteuer gerechnet und der Pflichthinweis zur Steuerschuldnerschaft des Leistungsempfängers gedruckt. Erstellt wird sie im Auftrag unter Belege › + Neuer Beleg.</p>
    ${V.map((x, i) => `<div class="kachel" style="margin-bottom:10px"><div class="form" style="grid-template-columns:1fr">
      ${zeile("Bezeichnung", `<input data-v="${i}" data-vk="name" value="${esc(x.name || "")}" placeholder="z. B. Kostenvoranschlag, Schlussrechnung">`)}
      ${zeile("Grundart", `<select data-v="${i}" data-vk="basis">${GRUND.map(([k, l]) => `<option value="${k}" ${k === x.basis ? "selected" : ""}>${l}</option>`).join("")}</select>`)}
      ${zeile("Bemerkung", `<input data-v="${i}" data-vk="bemerkung" value="${esc(x.bemerkung || "")}" placeholder="erscheint nur in der Auswahl, z. B. „für Bauleistungen“">`)}
      ${preise(x.basis) ? zeile("Umsatzsteuer", `<div class="radio"><label><input type="radio" name="vst${i}" data-v="${i}" data-vk="steuer" value="" ${x.steuer !== "13b" ? "checked" : ""}> normal (Steuersatz des Kunden)</label><label><input type="radio" name="vst${i}" data-v="${i}" data-vk="steuer" value="13b" ${x.steuer === "13b" ? "checked" : ""}> § 13b UStG (Steuerschuldnerschaft des Leistungsempfängers)</label></div>`) : ""}
      ${zeile("Einleitung", rtEditor(x.einleitung || "", `data-v="${i}" data-vk="einleitung" data-rt="1"`, "klein"))}
      ${zeile("Schlusstext", rtEditor(x.schluss || "", `data-v="${i}" data-vk="schluss" data-rt="1"`, "klein"))}
      <div><button class="btn rot" data-vdel="${i}">Belegart löschen</button></div></div></div>`).join("") || `<div class="leer">Noch keine eigenen Belegarten.</div>`}
    <button class="btn prim" id="vNeu">+ Eigene Belegart</button>`;
  $$("[data-v]", z).forEach(el => {
    const set = () => { const x = V[+el.dataset.v]; x[el.dataset.vk] = el.dataset.rt ? el.innerHTML : el.value; };
    if (el.dataset.rt) { let t; el.oninput = () => { set(); clearTimeout(t); t = setTimeout(() => speichern(false), 700); }; }
    else el.onchange = () => { set(); speichern(el.dataset.vk === "basis"); };
  });
  $$("[data-vdel]", z).forEach(b => b.onclick = async () => { if (!await frage(`Belegart „${V[+b.dataset.vdel].name}“ löschen? Bereits erstellte Belege bleiben unverändert.`)) return; V.splice(+b.dataset.vdel, 1); speichern(true); });
  $("#vNeu").onclick = () => { const n = Math.max(0, ...V.map(x => +String(x.key || "").replace(/\D/g, "") || 0)) + 1; V.push({key: "v" + n, name: "", basis: "angebot", bemerkung: "", steuer: "", einleitung: "", schluss: ""}); speichern(true); };
}

// ---------- Übersicht der Belegvariablen (Platzhalter) ----------
const BELEGVARIABLEN = [
  ["Belegtexte (Einleitung und Schlusstext)", "Einstellungen › Texte › Belegtexte, eigene Belegarten und jeder einzelne Beleg", [
    ["{anrede}", "Briefanrede aus dem Kunden, z. B. „Sehr geehrte Frau Müller,“"], ["{auftrag}", "Bezeichnung des Auftrags"],
    ["{betreff}", "Betreff des Belegs"], ["{nummer}", "Belegnummer (bei Rechnungen erst nach dem Festschreiben)"],
    ["{gueltig_bis}", "Belegdatum plus Gültigkeitsdauer der Angebote (Einstellung „Angebote gültig“)"],
    ["{bezug}", "Nummer der Rechnung, auf die sich Storno, Gutschrift oder Rechnungskorrektur beziehen"], ["{bezugdatum}", "Datum dieser Rechnung"]]],
  ["E-Mail zum Beleg (Betreff und Text)", "Einstellungen › Texte › Belegtexte", [
    ["{anrede}, {auftrag}, {betreff}, {nummer}, {bezug}, {gueltig_bis}", "wie in den Belegtexten"], ["{betrag}", "Zahlbetrag bei Rechnungen (Gutschrift: Betrag ohne Minus), sonst Bruttobetrag"],
    ["{faellig}", "Fälligkeitsdatum der Rechnung"], ["{belegart}", "Bezeichnung des Belegs, z. B. Rechnung, Kostenvoranschlag"],
    ["{firma}", "Firmenname"], ["{inhaber}", "Inhaber"]]],
  ["Arbeitskosten nach § 35a EStG", "Einstellungen › Belege & Briefbogen", [
    ["{lohn_netto}", "Arbeitskosten netto"], ["{lohn_ust}", "darauf entfallende Umsatzsteuer"], ["{lohn_brutto}", "Arbeitskosten brutto"]]],
  ["Mahnungen", "Einstellungen › Texte › Mahnungen", [
    ["{anrede}", "Briefanrede"], ["{nummer}", "Rechnungsnummer"], ["{datum}", "Rechnungsdatum"], ["{betrag}", "Rechnungsbetrag"], ["{offen}", "noch offener Betrag"],
    ["{faellig}", "Fälligkeit der Rechnung"], ["{zahlbetrag}", "Gesamtforderung inkl. Mahnkosten"], ["{gebuehr}", "Mahngebühr dieser Stufe"], ["{frist}", "neue Zahlungsfrist"],
    ["{letzte_mahnung}", "Datum der vorigen Mahnung"], ["{auftrag}", "Auftragsbezeichnung"]]],
  ["Zahlungsbestätigung per E-Mail", "Einstellungen › E-Mail", [
    ["{anrede}, {vorname}, {name}", "aus dem Kunden"], ["{belegart}", "Rechnung, Abschlagsrechnung …"], ["{rechnung}, {rechnungsdatum}, {rechnungsbetrag}", "bezahlte Rechnung"],
    ["{auftrag}, {bezeichnung}", "Auftragsnummer und -bezeichnung"], ["{betrag}, {zahlungsdatum}, {zahlart}, {skonto}", "diese Zahlung"],
    ["{bezahlt_gesamt}, {offen}", "Stand der Rechnung"], ["{auftrag_bezahlt}", "alle Zahlungen zum Auftrag"], ["{status}", "„vollständig bezahlt“ bzw. „bis auf … € bezahlt“"], ["{schlusssatz}", "Schlusssatz je nach Belegart"]]],
  ["Geburtstags- und Rundmails", "Einstellungen › E-Mail", [["{anrede}", "Briefanrede"], ["{vorname}", "Vorname"], ["{name}", "Nachname"]]],
  ["Projektordner", "Einstellungen › Kunden & Aufträge › Ordnerschema", [["{auftrag}", "Auftragsnummer"], ["{projekt}", "Auftragsbezeichnung"], ["{kundennr}", "Kundennummer"], ["{name}", "Kundenname"]]],
  ["Bestelldatei für Lieferanten", "Lieferant › Bestelldatei", [["#bestellnummer#, #bezeichnung#, #anzahl#, #einheit#", "Material"], ["#auftrag#, #liefertermin#, #kundennr#", "Bestellung"]]],
];
function belegvariablenVorgabe(z) {
  z.innerHTML = `<div class="titel"><h2>Belegvariablen</h2></div>
    <p class="hinweis" style="margin-top:-6px">Platzhalter in geschweiften Klammern werden beim Erstellen eines Belegs, einer E-Mail oder Mahnung durch die Werte ersetzt. Groß- und Kleinschreibung ist egal; eine Formatierung mitten im Platzhalter (z. B. fett) stört nicht.</p>
    ${BELEGVARIABLEN.map(([titel, wo, liste]) => `<div class="kachel" style="margin-bottom:10px"><h4 style="margin:0 0 2px">${esc(titel)}</h4><div class="hinweis" style="margin-bottom:6px">${esc(wo)}</div>
      <table class="liste">${liste.map(([k, t]) => `<tr><td style="width:38%"><code>${esc(k)}</code></td><td>${esc(t)}</td></tr>`).join("")}</table></div>`).join("")}`;
}

// ---------- Übersicht aller Belege ----------
const belegFilter = {q: "", art: "", jahr: ""};
async function alleBelege(z) {
  const f = belegFilter;
  const zeichnen = async () => {
    const liste = await api("belege?" + new URLSearchParams(f));
    sortierung.alleb ||= {k: "datum", ab: true};
    const t = tabelle("alleb", [
      {k: "nummer", t: "Beleg", f: b => `<a href="#/beleg/${b.id}">${esc(b.artname)} ${esc(b.nummer || "(Entwurf)")}</a>`},
      {k: "datum", t: "Datum", f: b => datum(b.datum)},
      {k: "kunde", t: "Kunde", f: b => `<a href="#/kunde/${b.kunde_id}">${esc(b.kunde || "")}</a>`},
      {k: "auftragsnr", t: "Auftrag", f: b => `<a href="#/auftrag/${b.auftrag_id}/belege">${esc(b.auftragsnr || "")}</a> <span class="hinweis">${esc(kurz(b.bezeichnung, 40))}</span>`},
      {k: "status", t: "Status", f: b => belegStatus(b)},
      {k: "brutto", t: "Brutto", r: 1, f: b => eur(b.brutto)},
      {k: "offen", t: "Offen", r: 1, f: b => b.offen == null ? "" : Math.abs(b.offen) < 0.005 ? `<span style="color:var(--gruen)">bezahlt</span>` : eur(b.offen)},
    ], liste, {klick: b => location.hash = `#/beleg/${b.id}`,
      leer: "Noch keine Belege. Angebote und Rechnungen entstehen im jeweiligen Auftrag unter „Belege“."});
    $("#bl").innerHTML = t.html; t.binden(zeichnen);
  };
  const j = new Date().getFullYear();
  z.innerHTML = `<div class="titel"><h2>Angebote &amp; Rechnungen</h2>
      <div class="such">
        <input id="blQ" placeholder="Nummer, Kunde, Betreff …" value="${esc(f.q)}" style="width:240px">
        <select id="blArt"><option value="">Alle Belegarten</option>${BELEGARTEN_UI.map(([v, l]) => `<option value="${v}" ${v === f.art ? "selected" : ""}>${l}</option>`).join("")}<option value="storno" ${f.art === "storno" ? "selected" : ""}>Stornorechnung</option></select>
        <select id="blJahr"><option value="">Alle Jahre</option>${[j, j - 1, j - 2, j - 3].map(y => `<option ${String(y) === f.jahr ? "selected" : ""}>${y}</option>`).join("")}</select>
      </div>
      <div class="rechts"><button class="btn prim" id="blNeu">+ Neuer Beleg</button></div></div>
    <div id="bl"></div>`;
  let tm; $("#blQ").oninput = e => { f.q = e.target.value; clearTimeout(tm); tm = setTimeout(zeichnen, 250); };
  $("#blArt").onchange = e => { f.art = e.target.value; zeichnen(); };
  $("#blJahr").onchange = e => { f.jahr = e.target.value; zeichnen(); };
  $("#blNeu").onclick = async () => {
    const auftraege = await api("auftraege");
    if (!auftraege.length) return toast("Bitte zuerst einen Auftrag anlegen (Belege gehören immer zu einem Auftrag).", true);
    const d = await modal("Neuer Beleg zu welchem Auftrag?", `<div class="zeile"><label>Auftrag</label><div><select name="a">${auftraege.map(a => `<option value="${a.id}">${esc(a.nummer)} · ${esc(a.bezeichnung)} · ${esc(a.kunde)}</option>`).join("")}</select></div></div>`, "Weiter");
    if (!d) return;
    neuerBeleg(auftraege.find(a => a.id === +d.a));
  };
  await zeichnen();
}


// PDF-Vorschau als Seitenbilder (unabhängig vom PDF-Betrachter des Browsers)
async function vorschauZeichnen(bid, lauf, aktuell) {
  const box = $("#vorschau"), info = $("#vsInfo"); if (!box) return;
  info.textContent = "Vorschau wird erstellt …";
  try {
    const r = await fetch(`/druck/${bid}.pdf?t=${Date.now()}`);
    if (!r.ok) throw new Error("PDF");
    const daten = new Uint8Array(await r.arrayBuffer());
    const basis = "/pdfjs/";
    if (!window.pdfjsLib) {
      await skriptLaden(basis + "pdf.min.js");
      window.pdfjsLib.GlobalWorkerOptions.workerSrc = basis + "pdf.worker.min.js";
    }
    const doc = await window.pdfjsLib.getDocument({data: daten}).promise;
    if (lauf !== aktuell()) return;
    const breite = Math.min(box.clientWidth - 28, 900), dpr = window.devicePixelRatio || 1;
    const neu = document.createElement("div");
    for (let n = 1; n <= doc.numPages; n++) {
      const seite = await doc.getPage(n);
      const v0 = seite.getViewport({scale: 1}), sk = breite / v0.width;
      const vp = seite.getViewport({scale: sk * dpr});
      const c = document.createElement("canvas");
      c.width = vp.width; c.height = vp.height;
      c.style.cssText = `display:block;width:${breite}px;height:${v0.height * sk}px;margin:0 auto 14px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.35)`;
      await seite.render({canvasContext: c.getContext("2d"), viewport: vp}).promise;
      neu.appendChild(c);
    }
    if (lauf !== aktuell() || !document.body.contains(box)) return;
    const pos = box.scrollTop;
    box.replaceChildren(...neu.children); box.scrollTop = pos;
    info.textContent = doc.numPages + (doc.numPages === 1 ? " Seite" : " Seiten");
  } catch (e) {
    if (lauf !== aktuell()) return;
    box.innerHTML = `<iframe src="/druck/${bid}?t=${Date.now()}" style="width:100%;height:1100px;border:0;background:#fff"></iframe>`;
    info.textContent = "HTML-Vorschau (PDF-Vorschau nicht verfügbar)";
  }
}


// ---------- Beleg per E-Mail senden ----------
async function belegMailen(bid) {
  return mailDialog(`belege/${bid}`, "Beleg per E-Mail senden", () => ansichtBeleg(bid));
}
// Gemeinsamer E-Mail-Dialog für Belege und Mahnungen: pfad + "/mail" liefert den Vorschlag (GET) und sendet (POST)
async function mailDialog(pfad, titel, danach, abfrage = "") {
  let v;
  try { v = await api(`${pfad}/mail${abfrage}`); } catch (e) { return toast(e.message, true); }
  if (!v.eingerichtet) {
    if (await frage("Der E-Mail-Versand ist noch nicht eingerichtet. Jetzt in den Einstellungen einrichten?")) location.hash = "#/einstellungen";
    return;
  }
  const gew = new Set(v.anhaenge.filter(x => x.an).map(x => x.id)), dat = new Set();
  const kb = n => n > 1048576 ? (n / 1048576).toFixed(1).replace(".", ",") + " MB" : Math.max(1, Math.round(n / 1024)) + " KB";
  const inhalt = `
    ${v.festschreiben ? `<div class="kachel" style="margin-bottom:10px;border-left:4px solid var(--akzent)">Die Rechnung ist noch ein Entwurf. Beim Senden wird sie <b>festgeschrieben</b> und bekommt ihre Nummer, danach ist sie nicht mehr änderbar.</div>` : ""}
    ${v.versendet ? `<p class="hinweis" style="margin-top:0">Schon einmal gesendet am ${datum(v.versendet.slice(0, 10))} an ${esc(v.versendet_an)}.</p>` : ""}
    <div class="zeile"><label>An</label><div class="spalte" style="gap:4px"><input name="an" value="${esc(v.an)}" list="mAdressen" placeholder="kunde@beispiel.de, mehrere mit Komma"><datalist id="mAdressen">${(v.adressen || []).map(a => `<option value="${esc(a)}">`).join("")}</datalist>
      ${(v.adressen || []).length > 1 ? `<div style="display:flex;gap:6px;flex-wrap:wrap" id="mChips">${v.adressen.map(a => `<button type="button" class="btn" data-adr="${esc(a)}" style="padding:2px 8px;font-size:12.5px"></button>`).join("")}</div>
        <span class="hinweis">Klick schaltet eine Adresse in „An“ ein oder aus; mit Umschalt-Klick kommt sie in „Cc“.</span>` : ""}</div></div>
    <div class="zeile"><label>Cc</label><div><input name="cc" value="" placeholder="optional, mehrere mit Komma"></div></div>
    <div class="zeile"><label>Betreff</label><div><input name="betreff" value="${esc(v.betreff)}"></div></div>
    <div class="zeile"><label>Text</label><div class="spalte" style="width:100%"><textarea name="text" rows="12" style="width:100%;font:inherit">${esc(v.text)}</textarea><span class="hinweis">Darunter wird beim Senden die Signatur mit Logo angehängt (Einstellungen › E-Mail › Signatur).</span></div></div>
    <div class="zeile"><label>Anhänge</label><div class="spalte">
      ${v.anhaenge.map(a => `<label><input type="checkbox" data-anh="${a.id}" ${a.an ? "checked" : ""}> 📄 ${esc(a.name)}</label>`).join("")}
      ${v.dateien.length ? `<details style="margin-top:4px"><summary style="cursor:pointer">Weitere Dateien aus dem Projektordner …</summary>
        <div class="spalte" style="max-height:200px;overflow:auto;margin-top:6px">${v.dateien.map((f, i) => `<label><input type="checkbox" data-dat="${i}"> ${esc(f.pfad)} <span class="hinweis">${kb(f.groesse)}</span></label>`).join("")}</div></details>` : ""}
    </div></div>
    <div class="zeile"><label></label><div><label style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="mBcc" ${v.kopie_an_mich ? "checked" : ""} style="flex:0 0 auto"> Kopie an mich (${esc(v.absender)})</label></div></div>`;
  let bcc = v.kopie_an_mich;
  const d = await modal(titel, inhalt, v.festschreiben ? "Festschreiben und senden" : "Senden", hg => {
    $(".modal", hg).style.width = "min(780px,96vw)";
    $(".modal", hg).style.maxHeight = "94vh"; $(".modal", hg).style.overflow = "auto";
    // hinterlegte Adressen als Schalter: An bzw. (Umschalt) Cc
    const liste = el => el.value.split(/[,;]\s*/).map(s => s.trim()).filter(Boolean);
    const chips = () => $$("[data-adr]", hg).forEach(c => {
      const a = c.dataset.adr.toLowerCase(), an = liste($("[name=an]", hg)).some(x => x.toLowerCase() === a), cc = liste($("[name=cc]", hg)).some(x => x.toLowerCase() === a);
      c.classList.toggle("prim", an); c.textContent = (an ? "✓ " : cc ? "Cc ✓ " : "+ ") + c.dataset.adr;
    });
    $$("[data-adr]", hg).forEach(c => c.onclick = ev => {
      const a = c.dataset.adr, gleich = x => x.toLowerCase() === a.toLowerCase();
      const feld = $(ev.shiftKey ? "[name=cc]" : "[name=an]", hg), anderes = $(ev.shiftKey ? "[name=an]" : "[name=cc]", hg);
      anderes.value = liste(anderes).filter(x => !gleich(x)).join(", ");   // eine Adresse steht nur in An oder in Cc
      const l = liste(feld), i = l.findIndex(gleich);
      if (i >= 0) l.splice(i, 1); else l.push(a);
      feld.value = l.join(", "); chips();
    });
    $("[name=an]", hg).addEventListener("input", chips); $("[name=cc]", hg).addEventListener("input", chips); chips();
    $$("[data-anh]", hg).forEach(x => x.onchange = () => x.checked ? gew.add(x.dataset.anh) : gew.delete(x.dataset.anh));
    $$("[data-dat]", hg).forEach(x => x.onchange = () => x.checked ? dat.add(v.dateien[+x.dataset.dat].pfad) : dat.delete(v.dateien[+x.dataset.dat].pfad));
    $("#mBcc", hg).onchange = e => { bcc = e.target.checked; };
    $("[name=text]", hg).addEventListener("keydown", e => e.stopPropagation());
  });
  if (!d) return;
  const warten = toast("E-Mail wird gesendet …");
  try {
    const r = await api(`${pfad}/mail${abfrage}`, {method: "POST", body: {an: d.an, cc: d.cc, betreff: d.betreff, text: d.text, anhaenge: [...gew], dateien: [...dat], kopie_an_mich: bcc}});
    toast(`E-Mail an ${d.an} gesendet` + (r.abgelegt ? ` · Kopie in „${r.abgelegt}“` : ""));
    if (r.hinweis) setTimeout(() => toast(r.hinweis, true), 2500);
    danach && danach(true);
  } catch (e) { toast(e.message, true); danach && danach(false); }
}


// ---------- Bilder in Positionen (Renderings, Fotos) ----------
// Das Original wird mit max. 2400 px gespeichert (zum Ansehen/Vergrößern). Zusätzlich entstehen Druckfassungen
// in genau der Größe, in der das Bild im Beleg gedruckt wird (300 dpi) – nur die landen im PDF.
const BILD_VARIANTEN = {k: 900, m: 1400, g: 2000}, BILD_MAX_H = 2540;
function bildLaden(quelle) {
  return new Promise((ok, fehler) => {
    const url = typeof quelle === "string" ? quelle : URL.createObjectURL(quelle), img = new Image();
    const frei = () => { if (typeof quelle !== "string") URL.revokeObjectURL(url); };
    img.onload = () => { frei(); ok(img); };
    img.onerror = () => { frei(); fehler(new Error("Das Bild konnte nicht gelesen werden (nur JPG, PNG oder WebP).")); };
    img.src = url;
  });
}
function bildSkalieren(img, maxB, maxH, q = 0.9) {
  const f = Math.min(1, maxB / img.naturalWidth, maxH / img.naturalHeight);
  const c = document.createElement("canvas"); c.width = Math.round(img.naturalWidth * f); c.height = Math.round(img.naturalHeight * f);
  const g = c.getContext("2d"); g.imageSmoothingEnabled = true; g.imageSmoothingQuality = "high";
  g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", q).split(",")[1];
}
function bildVariantenNoetig(img) {
  return Object.entries(BILD_VARIANTEN).filter(([, b]) => Math.min(b / img.naturalWidth, BILD_MAX_H / img.naturalHeight) < 0.9);
}
async function bildVerkleinern(blob, max = 2400) {
  const img = await bildLaden(blob);
  const varianten = {};
  for (const [art, b] of bildVariantenNoetig(img)) varianten[art] = bildSkalieren(img, b, BILD_MAX_H, 0.9);
  return {daten: bildSkalieren(img, max, max, 0.88), varianten};
}
// Ältere Bilder einmalig nachrüsten (läuft still im Hintergrund)
async function bildVariantenNachruesten() {
  let r;
  try { r = await api("bildvarianten"); } catch (e) { return; }
  for (const x of r.bilder || []) {
    try {
      const img = await bildLaden(`/api/bild/${x.datei}`);
      for (const art of x.fehlt) {
        const b = (r.varianten || BILD_VARIANTEN)[art]; if (!b) continue;
        await api("bildvarianten", {method: "POST", body: {datei: x.datei, art, daten: bildSkalieren(img, b, r.max_hoehe || BILD_MAX_H, 0.9)}});
      }
    } catch (e) { /* einzelnes Bild überspringen */ }
  }
}
function bilderBereich(ctx, sp) {
  const {p, pid, d} = ctx;
  const box = $("#pBilder"); if (!box) return;
  p.bilder = p.bilder || [];
  const GR = [["klein", "klein"], ["mittel", "mittel"], ["gross", "ganze Breite"]];
  const speichern = () => sp.setze("bilder", p.bilder, true);
  const hochladen = async (blob, name) => {
    toast("Bild wird eingefügt …");
    try {
      const {daten, varianten} = await bildVerkleinern(blob);
      const r = await api(`positionen/${pid}/bild`, {method: "POST", body: {daten, varianten, dateiname: name || "Bild.jpg", groesse: "mittel"}});
      p.bilder = r.position.bilder; zeichnen(); toast("Bild eingefügt");
    } catch (e) { toast(e.message, true); }
  };
  const zeichnen = () => {
    box.innerHTML = `
      <div class="pb-liste">${p.bilder.map((b, i) => `<div class="pb-karte${b.drucken === false ? " aus" : ""}">
        <img src="/api/bild/${esc(b.datei)}" alt="">
        <div class="pb-feld"><input data-bt="${i}" value="${esc(b.text || "")}" placeholder="Bildunterschrift (optional)"></div>
        <div class="pb-feld"><select data-bg="${i}">${GR.map(([v, l]) => `<option value="${v}" ${(b.groesse || "mittel") === v ? "selected" : ""}>${l}</option>`).join("")}</select>
          <label title="Im Beleg drucken"><input type="checkbox" data-bd="${i}" ${b.drucken === false ? "" : "checked"}> drucken</label></div>
        <div class="pb-feld"><button class="btn" data-bl="${i}" ${i ? "" : "disabled"} title="nach vorn">←</button><button class="btn rot" data-bx="${i}" title="Bild entfernen">✕</button></div>
      </div>`).join("")}</div>
      <div class="pb-drop" id="pbDrop">Bild hierher ziehen oder mit Strg+V einfügen ·
        <a href="#" id="pbWahl">Datei wählen</a> · <a href="#" id="pbProj">aus dem Projektordner</a>
        <input type="file" id="pbDatei" accept="image/jpeg,image/png,image/webp" multiple hidden></div>`;
    $$("[data-bt]", box).forEach(el => el.oninput = () => { p.bilder[+el.dataset.bt].text = el.value; sp.setze("bilder", p.bilder); });
    $$("[data-bg]", box).forEach(el => el.onchange = () => { p.bilder[+el.dataset.bg].groesse = el.value; speichern(); });
    $$("[data-bd]", box).forEach(el => el.onchange = () => { p.bilder[+el.dataset.bd].drucken = el.checked; speichern(); zeichnen(); });
    $$("[data-bl]", box).forEach(el => el.onclick = () => { const i = +el.dataset.bl; [p.bilder[i - 1], p.bilder[i]] = [p.bilder[i], p.bilder[i - 1]]; speichern(); zeichnen(); });
    $$("[data-bx]", box).forEach(el => el.onclick = async () => { if (!await frage("Bild aus dieser Position entfernen?")) return; p.bilder.splice(+el.dataset.bx, 1); speichern(); zeichnen(); });
    $("#pbWahl").onclick = e => { e.preventDefault(); $("#pbDatei").click(); };
    $("#pbDatei").onchange = async e => { for (const f of e.target.files) await hochladen(f, f.name); };
    const drop = $("#pbDrop");
    drop.ondragover = e => { e.preventDefault(); drop.classList.add("ueber"); };
    drop.ondragleave = () => drop.classList.remove("ueber");
    drop.ondrop = async e => { e.preventDefault(); drop.classList.remove("ueber"); for (const f of e.dataTransfer.files) if (f.type.startsWith("image/")) await hochladen(f, f.name); };
    $("#pbProj").onclick = async e => {
      e.preventDefault();
      const r = await api(`auftraege/${d.auftrag.id}/bilddateien`);
      if (!r.dateien.length) return toast(r.hinweis || "Im Projektordner sind keine Bilder (JPG, PNG, WebP).", true);
      let wahl = null;
      const ok = await modal("Bild aus dem Projektordner", `<p class="hinweis" style="margin-top:0">Neueste zuerst. Ein Klick wählt das Bild aus.</p>
        <div class="pb-proj">${r.dateien.map((f, i) => `<button type="button" data-pf="${i}"><img loading="lazy" src="/api/auftraege/${d.auftrag.id}/datei?pfad=${encodeURIComponent(f.pfad)}"><span>${esc(f.pfad)}</span></button>`).join("")}</div>`,
        "Einfügen", hg => {
          $(".modal", hg).style.width = "min(860px,96vw)";
          $$("[data-pf]", hg).forEach(b => b.onclick = () => { $$("[data-pf]", hg).forEach(x => x.classList.remove("gewaehlt")); b.classList.add("gewaehlt"); wahl = r.dateien[+b.dataset.pf]; });
          $$("[data-pf]", hg).forEach(b => b.ondblclick = () => $("[data-x='1']", hg).click());
        });
      if (!ok || !wahl) return;
      const blob = await (await fetch(`/api/auftraege/${d.auftrag.id}/datei?pfad=${encodeURIComponent(wahl.pfad)}`)).blob();
      await hochladen(blob, wahl.pfad.split("/").pop());
    };
  };
  zeichnen();
  // Einfügen aus der Zwischenablage (z. B. Screenshot oder kopiertes Rendering)
  if (!window._pbPaste) {
    window._pbPaste = true;
    document.addEventListener("paste", e => {
      const ziel = window._pbZiel; if (!ziel || !document.body.contains($("#pBilder"))) return;
      if (e.target.closest && e.target.closest("[contenteditable=true],input,textarea")) return;
      const f = [...(e.clipboardData?.files || [])].find(x => x.type.startsWith("image/"));
      if (f) { e.preventDefault(); ziel(f, "Eingefügt.png"); }
    });
  }
  window._pbZiel = hochladen;
}


// Kundendaten des Auftrags: beim Anlegen aus dem Kundenstamm kopiert, danach unabhängig davon
async function auftragKundendaten(box, a) {
  const r = await api(`auftraege/${a.id}/kunde`);
  const k = r.kopie;
  const namen = {kurzname: "Kurzname", anschrift: "Briefanschrift", plz: "PLZ", ort: "Ort", land: "Land", telefon: "Telefon", email1: "E-Mail", anrede: "Briefanrede",
    gruppe: "Gruppe", ustid: "USt-IdNr.", lieferanschrift: "Lieferanschrift", lieferort: "Lieferort", rechnungsanschrift: "Rechnungsanschrift", rechnungsort: "Rechnungsort",
    zahlungsziel: "Zahlungsziel", skonto: "Skonto", skontotage: "Skontotage", rabatt: "Rabatt"};
  const f = (feld, attr = "") => `<input data-f="${feld}" value="${esc(k[feld] ?? "")}" ${attr}>`;
  const t = (feld, rows = 3) => `<textarea data-f="${feld}" rows="${rows}" data-text="1">${esc(k[feld] || "")}</textarea>`;
  box.innerHTML = `
    <div class="titel"><h2>Kunde im Auftrag ${esc(a.nummer)}</h2><span class="speicher"></span>
      <div class="rechts"><a class="btn" href="#/kunde/${k.id}">Kundenstamm öffnen</a><button class="btn" id="kdNeu" title="Kundendaten erneut aus dem Kundenstamm übernehmen">Aus Kundenstamm aktualisieren</button></div></div>
    <p class="hinweis" style="margin:0 0 8px">Beim Anlegen des Auftrags aus dem Kundenstamm kopiert${k.kopiert_am ? " am " + datum(k.kopiert_am.slice(0, 10)) : ""}. Änderungen im Kundenstamm wirken sich auf diesen Auftrag und seine Belege nicht aus; Änderungen hier nicht auf den Kundenstamm.</p>
    ${r.unterschiede.length ? `<div class="kachel" style="margin-bottom:8px;border-left:4px solid var(--akzent)">Im Kundenstamm steht inzwischen etwas anderes bei: <b>${r.unterschiede.map(x => namen[x] || x).join(", ")}</b>.
      ${r.unterschiede.slice(0, 4).map(x => `<div class="hinweis">${namen[x] || x}: Auftrag „${esc(String(k[x] ?? "").replace(/\n/g, ", "))}“ · Kundenstamm „${esc(String(r.stamm[x] ?? "").replace(/\n/g, ", "))}“</div>`).join("")}</div>` : ""}
    <div class="form" id="fk">
      ${zeile("Kurzname", f("kurzname"))}
      ${zeile("Gruppe", `<select data-f="gruppe">${opts(E.kundengruppen || [], k.gruppe)}</select>`)}
      ${adressFelder(k)}
      ${zeile("Briefanschrift", `<div class="briefanschrift" id="bfAnschrift">${esc(k.anschrift || "")}</div>`)}
      ${zeile("Telefon", f("telefon"))}
      ${zeile("E-Mail", f("email1"))}
      ${zeile("Briefanrede", f("anrede"))}
      ${zeile("USt-IdNr.", f("ustid"))}
      ${zeile("Lieferanschrift", t("lieferanschrift", 3))}
      ${zeile("Lieferort", f("lieferort"))}
      ${zeile("Zahlungsziel", `${f("zahlungsziel", 'style="flex:0 0 80px"')}<span style="padding-top:5px">Tage · Skonto</span>${f("skonto", 'style="flex:0 0 60px"')}<span style="padding-top:5px">% in</span>${f("skontotage", 'style="flex:0 0 60px"')}<span style="padding-top:5px">Tagen</span>`)}
      ${zeile("Rabatt", `${f("rabatt", 'style="flex:0 0 80px"')}<span style="padding-top:5px">%</span>`)}
    </div>`;
  autospeichern($("#fk"), `auftraege/${a.id}/kunde`, res => { if (!res || !res.kopie) return; Object.assign(k, res.kopie); adressAktualisieren(k); if (res.kopie.kurzname !== a.kunde) { a.kunde = res.kopie.kurzname; auftragKopf(a, "kunde"); } });
  $("#kdNeu").onclick = async () => {
    if (!await frage("Kundendaten dieses Auftrags durch die aktuellen Daten aus dem Kundenstamm ersetzen? Bereits erstellte Belege bleiben unverändert.")) return;
    await api(`auftraege/${a.id}/kunde`, {method: "POST"}); toast("Kundendaten aktualisiert"); auftragKundendaten(box, a);
  };
}


// ---------------------------------------------------------------------
//  CSV-Stücklistenimport (CSV-Format mit 22 Feldern, optional mit Werkstoffbezeichnung)
// ---------------------------------------------------------------------
async function textAusDatei(f) {
  const buf = await f.arrayBuffer();
  try { return new TextDecoder("utf-8", {fatal: true}).decode(buf); }
  catch (e) { return new TextDecoder("windows-1252").decode(buf); }
}
function stuecklistenImport(ctx, {konstruktion = false, datei = ""} = {}) {
  const {pid} = ctx;
  let text = "", info = null, format = "auto", posUebernehmen = true, ersetzen = false, kDateien = null, kOrdner = "", kGewaehlt = "";
  const wahl = {};  // "rolle|code" → {material_id, anzeige} | {neu:{…}} | {weglassen:true}
  const hg = document.createElement("div");
  hg.className = "modal-hg";
  hg.innerHTML = `<div class="modal" style="width:min(1100px,96vw);max-height:92vh;overflow:auto"><h3>CAD-Import</h3><div id="siInhalt"></div>
    <div class="knoepfe"><button class="btn" id="siAbbr">Abbrechen</button><button class="btn prim" id="siOk" disabled>Importieren</button></div></div>`;
  document.body.appendChild(hg);
  const zu = () => hg.remove();
  $("#siAbbr", hg).onclick = zu;
  const body = () => ({text, erweitert: format === "auto" ? null : format === "erw"});
  const pruefen = async () => {
    try { info = await api(`positionen/${pid}/stueckliste-import`, {method: "POST", body: body()}); }
    catch (e) { info = null; toast(e.message, true); }
    for (const m of info ? info.materialien : []) {
      const key = `${m.rolle}|${m.code}`;
      if (!wahl[key]) wahl[key] = m.treffer ? {material_id: m.treffer.id, anzeige: `${m.treffer.nummer} ${m.treffer.bezeichnung}`} : {neu: {...m.neu}};
    }
    zeichnen();
  };
  const neueNummern = () => {
    const zaehler = {}, aus = {};
    for (const m of info.materialien) {
      const w = wahl[`${m.rolle}|${m.code}`];
      if (!w || !w.neu) continue;
      const kat = w.neu.kategorie, basis = info.naechste[kat];
      if (!basis) { aus[`${m.rolle}|${m.code}`] = "neu"; continue; }
      const prae = basis.replace(/\d+$/, ""), start = +basis.slice(prae.length);
      zaehler[kat] = (zaehler[kat] ?? -1) + 1;
      aus[`${m.rolle}|${m.code}`] = prae + String(start + zaehler[kat]).padStart(basis.length - prae.length, "0");
    }
    return aus;
  };
  const zeichnen = () => {
    const ziel = $("#siInhalt", hg);
    const eingabe = `
      <p class="hinweis" style="margin-top:0">Übliches CSV-Stücklistenformat mit 22 Feldern, optional Feld 23 Taschen: eine Zeile je Teil (Werkstoff; Verwendung; Anzahl; Länge; Breite; Kanten l/r/o/u; Kantenverlauf; Furnier o/u; Oberfläche o/u; Bemerkung; Fräsen l/r/o/u; Verbinden o/u; Bohren; Taschen), Beschläge ohne Maße, optional als erste Zeile die Position. Alle Felder: <a href="/hilfe/handbuch.html#importformat" target="jahresring-hilfe">Handbuch › Importformat</a>.
      <b>Erweitert:</b> nach der Werkstoffnummer zusätzlich die <b>Werkstoffbezeichnung</b> – damit legt das Programm unbekannte Werkstoffe mit fortlaufender Nummer im Materialstamm an.</p>
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:6px">
        <label class="btn">CSV-Datei wählen<input type="file" id="siDatei" accept=".csv,.txt" hidden></label>
        <button class="btn" id="siKons" type="button">Aus dem CAD-Ordner (${esc(kOrdner || E.konstruktion_ordner || "20_Konstruktion")})</button>
        <span class="hinweis">oder Daten aus der Zwischenablage einfügen:</span></div>
      ${kDateien ? (kDateien.length ? `<div class="kat-liste" style="max-height:150px;margin-bottom:6px">${kDateien.map(d => `<label><input type="radio" name="siK" value="${esc(d.datei)}" ${d.datei === kGewaehlt ? "checked" : ""}> <span><b>${esc(d.datei)}</b>${d.status === "importiert" ? ` <span class="hinweis">· schon übernommen</span>` : d.status === "ignoriert" ? ` <span class="hinweis">· ignoriert</span>` : ` <span style="color:var(--gruen)">· neu</span>`}</span><small>${datum(d.geaendert.slice(0, 10))} ${d.geaendert.slice(11, 16)} · ${Math.max(1, Math.round(d.groesse / 1024))} KB</small></label>`).join("")}</div>`
        : `<p class="hinweis" style="color:var(--rot)">Im Ordner ${esc(kOrdner)} liegt noch keine CSV- oder TXT-Datei. Im CAD die Stückliste im CSV-Stücklistenformat (22 Felder) dorthin exportieren.</p>`) : ""}
      <textarea id="siText" rows="${info ? 4 : 10}" style="width:100%;font-family:monospace;font-size:12px" placeholder=";Wäscheschrank;1;2.000,0;800,0;600,0;;;;;;;;;;;;;;;;&#10;FPYW19;Spanplatte weiß 19 mm;Seite;2;2.000,0;600,0;KDKUW1,5;;KDKUW1,5;KDKUW1,5;L;;;;;Falz Rückwand;1;;;;;2">${esc(text)}</textarea>
      <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:6px">
        <span>Format: <select id="siFormat">${optsPaare([["auto", "automatisch erkennen"], ["std", "Standard (22 Felder, ohne Bezeichnung)"], ["erw", "mit Werkstoffbezeichnung (Feld 2)"]], format)}</select></span>
        <button class="btn" id="siPruef">Daten prüfen</button></div>`;
    if (!info) { ziel.innerHTML = eingabe; binden(); $("#siOk", hg).disabled = true; return; }
    const nr = neueNummern();
    const katOpt = (kat) => Object.entries(info.kategorien).map(([k, n]) => `<option value="${k}" ${k === kat ? "selected" : ""}>${esc(n)}</option>`).join("");
    const grOpt = (kat, gr) => (info.gruppen[kat] || []).map(g => `<option ${g === gr ? "selected" : ""}>${esc(g)}</option>`).join("");
    const zeilen = info.materialien.map((m, i) => {
      const key = `${m.rolle}|${m.code}`, w = wahl[key];
      const modus = w.weglassen ? "weg" : w.neu ? "neu" : "vorh";
      return `<tr data-mi="${i}"><td>${esc(m.rolle_name)}</td><td><b>${esc(m.code)}</b>${m.bez ? `<div class="hinweis">${esc(m.bez)}</div>` : ""}</td><td class="r">${m.anzahl}</td>
        <td><select data-modus>${optsPaare([["vorh", w.material_id ? "→ " + w.anzeige : "vorhandenes Material wählen …"], ["neu", "neu anlegen als " + (nr[key] || "…")], ["weg", "nicht übernehmen"]], modus)}</select>
        ${modus === "vorh" ? ` <button class="btn" data-anders>anderes …</button>` : ""}
        ${modus === "neu" ? `<div style="display:flex;gap:4px;margin-top:4px;flex-wrap:wrap">
            <input data-n="bezeichnung" value="${esc(w.neu.bezeichnung)}" style="flex:1 1 220px" placeholder="Bezeichnung">
            <select data-n="kategorie">${katOpt(w.neu.kategorie)}</select><select data-n="gruppe">${grOpt(w.neu.kategorie, w.neu.gruppe)}</select>
            ${["platte", "kante"].includes(m.rolle) ? `<input data-n="dicke" class="zahl" value="${w.neu.dicke ? n2(w.neu.dicke, w.neu.dicke % 1 ? 1 : 0) : ""}" style="width:60px" placeholder="Dicke"> mm` : ""}</div>` : ""}</td></tr>`;
    }).join("");
    const anzNeu = Object.values(wahl).filter(w => w.neu).length;
    ziel.innerHTML = eingabe + `
      <h4 style="margin:14px 0 4px">Gefunden: ${info.teile} Teile, ${info.beschlaege} Beschläge ${info.erweitert ? "· Format mit Werkstoffbezeichnung" : "· Standardformat (22 Felder)"}</h4>
      ${info.beispiele.length ? `<div class="hinweis">${info.beispiele.map(t => `${esc(t.verwendung || t.nr)} ${t.stueck}× ${n2(t.laenge, 0)}×${n2(t.breite, 0)}`).join(" · ")}${info.teile > info.beispiele.length ? " …" : ""}</div>` : ""}
      <table class="liste" style="margin-top:8px"><tr><th>Art</th><th>Kürzel aus der CAD</th><th class="r">Anz.</th><th>Materialstamm</th></tr>${zeilen}</table>
      <p class="hinweis">Gefundene Zuordnungen merkt sich das Programm im Material (Feld „CAD-Kürzel“) – beim nächsten Import ist alles schon richtig zugeordnet. Die Werkstoffe kommen mit Preis und Verschnitt aus dem Materialstamm in die Auftragswerte.</p>
      <div class="form" style="grid-template-columns:1fr">
        ${info.position ? zeile("Position", `<label><input type="checkbox" id="siPos" ${posUebernehmen ? "checked" : ""}> Anzahl und Maße aus der Positionszeile übernehmen (${esc(info.position.text)}, ${n2(info.position.menge, 0)} Stk., ${n2(info.position.h, 0)} × ${n2(info.position.b, 0)} × ${n2(info.position.t, 0)}); leerer Positionstext wird gefüllt</label>`) : ""}
        ${zeile("Vorhandene Teile", `<select id="siErs">${optsPaare([["0", "behalten, neue Teile anhängen"], ["1", "ersetzen durch die importierten"]], ersetzen ? "1" : "0")}</select>`)}
      </div>`;
    $("#siOk", hg).disabled = false;
    $("#siOk", hg).textContent = anzNeu ? `Importieren und ${anzNeu} Material${anzNeu > 1 ? "ien" : ""} anlegen` : "Importieren";
    binden();
    $$("tr[data-mi]", ziel).forEach(tr => {
      const m = info.materialien[+tr.dataset.mi], key = `${m.rolle}|${m.code}`;
      const anders = async () => {
        const kats = {platte: ["holzwerkstoffe", "massivholz", "artikel"], kante: ["holzwerkstoffe"], furnier: ["holzwerkstoffe"], oberflaeche: ["beschichtung", "chemie"], beschlag: ["beschlaege", "artikel", "chemie"]}[m.rolle];
        const x = await materialWaehlen(kats, `${m.rolle_name} für ${m.code} wählen`);
        if (x) wahl[key] = {material_id: x.id, anzeige: `${x.nummer} ${x.bezeichnung}`};
        zeichnen();
      };
      $("[data-modus]", tr).onchange = e => {
        const v = e.target.value;
        if (v === "weg") wahl[key] = {weglassen: true};
        else if (v === "neu") wahl[key] = {neu: {...m.neu}};
        else if (m.treffer) wahl[key] = {material_id: m.treffer.id, anzeige: `${m.treffer.nummer} ${m.treffer.bezeichnung}`};
        else return anders();
        zeichnen();
      };
      const b = $("[data-anders]", tr); if (b) b.onclick = anders;
      $$("[data-n]", tr).forEach(el => el.onchange = () => {
        const n = wahl[key].neu;
        n[el.dataset.n] = el.dataset.n === "dicke" ? zahlEin(el.value) : el.value;
        if (el.dataset.n === "kategorie") { n.gruppe = (info.gruppen[n.kategorie] || [""])[0]; zeichnen(); }
      });
    });
    if ($("#siPos", hg)) $("#siPos", hg).onchange = e => posUebernehmen = e.target.checked;
    $("#siErs", hg).onchange = e => ersetzen = e.target.value === "1";
  };
  const binden = () => {
    $("#siDatei", hg).onchange = async e => { const f = e.target.files[0]; if (!f) return; text = await textAusDatei(f); pruefen(); };
    $("#siText", hg).oninput = e => { text = e.target.value; };
    $("#siPruef", hg).onclick = () => { text = $("#siText", hg).value; pruefen(); };
    $("#siFormat", hg).onchange = e => { format = e.target.value; if (text) pruefen(); };
    $("#siKons", hg).onclick = () => konstruktionLaden();
    $$("[name=siK]", hg).forEach(r => r.onchange = () => dateiLaden(r.value));
  };
  const dateiLaden = async rel => {
    try { const r = await api(`positionen/${pid}/konstruktion?datei=${encodeURIComponent(rel)}`); kGewaehlt = rel; text = r.text; pruefen(); }
    catch (e) { toast(e.message, true); }
  };
  const konstruktionLaden = async () => {
    try { const r = await api(`positionen/${pid}/konstruktion`); kDateien = r.dateien; kOrdner = r.ordner; }
    catch (e) { toast(e.message, true); return; }
    if (datei && kDateien.some(x => x.datei === datei)) return dateiLaden(datei);
    if (kDateien.length) return dateiLaden(kDateien[0].datei);   // neueste Datei gleich laden
    zeichnen();
  };
  $("#siOk", hg).onclick = async () => {
    const b = $("#siOk", hg); b.disabled = true; b.textContent = "importiert …";
    try {
      const r = await api(`positionen/${pid}/stueckliste-import`, {method: "POST", body: {...body(), ausfuehren: true, zuordnung: wahl, cad_datei: kGewaehlt || "",
        position_uebernehmen: posUebernehmen, ersetzen}});
      zu();
      const im = r.import;
      toast(`${im.teile} Teile und ${im.beschlaege} Beschläge übernommen` + (im.angelegt.length ? ` · neu im Materialstamm: ${im.angelegt.join(", ")}` : ""));
      ansichtPosition(pid, "werkstoffe");
    } catch (e) { toast(e.message, true); b.disabled = false; b.textContent = "Importieren"; }
  };
  zeichnen();
  if (konstruktion) konstruktionLaden();
}
const optsPaare = (paare, wert) => paare.map(([v, l]) => `<option value="${esc(v)}" ${String(v) === String(wert) ? "selected" : ""}>${esc(l)}</option>`).join("");


// Material aus dem Stamm in die Auftrags-/Standardwerte übernehmen → {k, neu}
function kalkTyp(m) {
  const gr = (m.gruppe || "").toLowerCase();
  if (m.kategorie === "holzwerkstoffe") return gr.includes("kant") ? "kante" : gr.includes("furnier") ? "furnier" : "platte";
  return {massivholz: "massiv", beschichtung: "oberflaeche"}[m.kategorie] || "sonstig";
}
function materialInKalk(k, m, rolle) {
  const einh = {"lfm.": "lfm", "Liter": "l"}[m.einheit] || m.einheit;
  const daten = {name: (m.bezeichnung || "").split("\n")[0], preis: (m.kalkpreis ?? m.ek_preis) || 0, v: m.verschnitt || 0, stamm_preis: (m.kalkpreis ?? m.ek_preis) || 0, stamm_v: m.verschnitt || 0, matnr: m.nummer, lieferant: m.lieferant || "",
    bestellnr: m.bestellnr || "", preis_vom: m.preis_vom || ""};
  if (rolle === "beschlag") {
    k.beschlaege = k.beschlaege || [];
    const da = k.beschlaege.find(b => b.matnr === m.nummer || b.artnr === m.nummer);
    if (da) return {k: da.k, neu: false};
    const nrn = k.beschlaege.map(b => +String(b.k).slice(1) || 0);
    const neu = {k: "B" + String(Math.max(0, ...nrn) + 1).padStart(2, "0"), artnr: m.nummer, einheit: einh || "Stk.", ...daten, v: 0, stamm_v: 0};
    k.beschlaege.push(neu);
    return {k: neu.k, neu: true};
  }
  const typ = rolle || kalkTyp(m);
  k.werkstoffe = k.werkstoffe || [];
  const da = k.werkstoffe.find(w => w.matnr === m.nummer && w.typ === typ);
  if (da) return {k: da.k, neu: false};
  const prae = {platte: "P", massiv: "M", kante: "K", furnier: "F", oberflaeche: "O", sonstig: "S"}[typ];
  const nrn = k.werkstoffe.filter(w => String(w.k).startsWith(prae)).map(w => +String(w.k).slice(1) || 0);
  const neu = {k: prae + String(Math.max(0, ...nrn) + 1).padStart(2, "0"), typ, einheit: einh || {kante: "lfm", massiv: "m³", sonstig: "Stk."}[typ] || "m²", dicke: m.dicke || 0, ...daten};
  k.werkstoffe.push(neu);
  return {k: neu.k, neu: true};
}

const stammAbwPreis = w => w.stamm_preis != null && Math.abs((+w.preis || 0) - (+w.stamm_preis || 0)) > 0.0049
  ? ` · <span style="color:var(--akzent)">im Stamm: ${n2(w.stamm_preis)}</span>` : "";
const stammAbw = w => {
  if (w.stamm_preis == null) return "";
  const t = [];
  if (Math.abs((+w.preis || 0) - (+w.stamm_preis || 0)) > 0.0049) t.push("Preis " + n2(w.stamm_preis));
  if (Math.abs((+w.v || 0) - (+w.stamm_v || 0)) > 0.0049) t.push("V " + n2(w.stamm_v, 0) + " %");
  return t.length ? ` · <span style="color:var(--akzent)">im Stamm: ${t.join(", ")}</span>` : "";
};


// Neue Stücklisten aus dem CAD im CAD-Ordner des Projekts: Hinweis über der Positionsliste
async function cadHinweis(z, a, d) {
  let neu = [];
  try { neu = await api("cad/neu?auftrag=" + a.id); } catch (e) { return; }
  if (!neu.length || !document.body.contains(z)) return;
  const box = document.createElement("div");
  box.className = "kachel"; box.style.cssText = "border-left:4px solid var(--akzent);margin:0 0 12px";
  const pos = (d.positionen || []).filter(p => !p.parent_id);
  box.innerHTML = `<b>Neue Stückliste${neu.length > 1 ? "n" : ""} aus dem CAD</b> <span class="hinweis">im Ordner ${esc(E.konstruktion_ordner || "20_Konstruktion")}</span>
    ${neu.map((x, i) => `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:6px"><span style="flex:1 1 240px"><b>${esc(x.datei)}</b> <span class="hinweis">${datum(x.geaendert.slice(0, 10))} ${x.geaendert.slice(11, 16)}</span></span>
      <button class="btn prim" data-cneu="${i}">Als neue Position übernehmen</button>
      ${pos.length ? `<select data-cpos="${i}"><option value="">In Position übernehmen …</option>${pos.map(p => `<option value="${p.id}">${esc(p.posnr)} ${esc(kurz(p.text, 40))}</option>`).join("")}</select>` : ""}
      <button class="btn" data-cign="${i}" title="Diese Fassung der Datei nicht mehr anzeigen">Ignorieren</button></div>`).join("")}`;
  z.prepend(box);
  $$("[data-cneu]", box).forEach(b => b.onclick = async () => {
    const x = neu[+b.dataset.cneu];
    const pid = await neuePosition(a, {titel: d.titel.at(-1)?.nr || 0, oeffnen: false});
    location.hash = `#/position/${pid}/werkstoffe`;
    setTimeout(() => stuecklistenImport({pid}, {konstruktion: true, datei: x.datei}), 900);
  });
  $$("[data-cpos]", box).forEach(s => s.onchange = () => {
    if (!s.value) return; const x = neu[+s.dataset.cpos], pid = +s.value;
    location.hash = `#/position/${pid}/werkstoffe`;
    setTimeout(() => stuecklistenImport({pid}, {konstruktion: true, datei: x.datei}), 900);
  });
  $$("[data-cign]", box).forEach(b => b.onclick = async () => {
    const x = neu[+b.dataset.cign];
    try { await api("cad/ignorieren", {method: "POST", body: {auftrag_id: a.id, datei: x.datei}}); b.closest("div").remove(); if (!$("[data-cign]", box)) box.remove(); } catch (e) { toast(e.message, true); }
  });
}

// Hinweise der Kalkulation (Lohngruppe ohne Lohn, fehlende Bezugsgröße …)
function kalkWarnHtml(c) {
  const w = (c && c.warnungen) || [];
  return w.length ? `<div class="kachel" style="border-left:4px solid #c9a227;margin:10px 0">${w.map(x => `<div>⚠ ${esc(x)}</div>`).join("")}</div>` : "";
}

// ---------------------------------------------------------------------
//  Auftragshistorie: Zeitleiste mit Notizen und allen Ereignissen des Auftrags
// ---------------------------------------------------------------------
const HIST_ICON = {notiz: "📝", status: "🔄", datei: "📎", anhang: "📎", beleg: "📄", fest: "✅", zahlung: "💶", mail_ein: "📥", mail_aus: "📤",
  anruf_ein: "📞", anruf_aus: "📞", notiz_k: "🗒", brief: "📮", termin: "📅", stunden: "⏱", cad: "📐", angelegt: "✳️"};
const HIST_FILTER = [["", "Alle"], ["notiz", "Notizen & Dateien"], ["korrespondenz", "Korrespondenz"], ["beleg", "Belege & Zahlungen"], ["termin", "Termine"], ["werkstatt", "Werkstatt"], ["auftrag", "Status"]];
async function historieSeite(z, a) {
  let filter = "";
  const [ordner] = await Promise.all([api(`auftraege/${a.id}/dateien`).catch(() => ({}))]);
  const mitOrdner = !!(ordner && ordner.ordner);
  z.innerHTML = `<div class="titel"><h2>Auftragshistorie</h2></div>
    <div class="kachel" style="margin-bottom:12px">
      <div style="display:flex;gap:8px"><textarea id="hNotiz" rows="2" placeholder="Notiz, z. B. Telefonat: Kunde wünscht Eiche geölt statt lackiert" style="flex:1"></textarea>
        <button class="btn prim" id="hNeu" style="align-self:flex-start">Notiz speichern</button></div>
      <div class="ablage" id="hAblage" style="margin-top:8px">Dateien hierher ziehen oder <label style="text-decoration:underline;cursor:pointer">auswählen<input type="file" id="hDatei" multiple hidden></label>
        <span class="hinweis">– ${mitOrdner ? "sie werden im Projektordner abgelegt" : "sie werden in Jahresring gespeichert (kein Projektordner eingerichtet)"}</span></div>
    </div>
    <div id="hFilter" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">${HIST_FILTER.map(([k, l]) => `<button class="btn${k === filter ? " prim" : ""}" data-hf="${k}">${l}</button>`).join("")}</div>
    <div id="hListe"></div>`;
  const zeichnen = async () => {
    let d;
    try { d = await api(`auftraege/${a.id}/historie`); } catch (e) { $("#hListe").innerHTML = `<p class="hinweis">${esc(e.message)}</p>`; return; }
    const ev = d.ereignisse.filter(x => !filter || x.gruppe === filter);
    let tag = "";
    const link = x => x.beleg_id ? `#/beleg/${x.beleg_id}` : x.brief_id ? `#/brief/${x.brief_id}` : x.korr_id ? `#/auftrag/${a.id}/briefe` : x.termin_id ? `#/kalender/planung/${x.zeit.slice(0, 10)}` : "";
    $("#hListe").innerHTML = ev.length ? ev.map(x => {
      const t = x.zeit.slice(0, 10), kopf = t !== tag ? `<div class="h-tag">${wochentagDatum(t)}</div>` : ""; tag = t;
      const ziel = link(x);
      const titel = ziel ? `<a href="${ziel}">${esc(x.titel)}</a>` : x.anhang_id ? `<a href="/api/anhaenge/${x.anhang_id}/datei" target="_blank">${esc(x.titel)}</a>` : esc(x.titel);
      return `${kopf}<div class="h-e h-${x.gruppe}${x.art === "notiz" ? " h-notiz" : ""}"><span class="h-i">${HIST_ICON[x.art] || "•"}</span>
        <div class="h-b"><div><b>${titel}</b> <span class="hinweis">${x.zeit.slice(11, 16) !== "00:00" && x.zeit.slice(11, 16) !== "23:59" && x.zeit.slice(11, 16) !== "12:00" && x.zeit.slice(11, 16) !== "18:00" ? x.zeit.slice(11, 16) : ""}${x.benutzer ? " · " + esc(x.benutzer) : ""}${x.wer ? " · " + esc(x.wer) : ""}</span></div>
        ${x.text ? `<div class="h-t">${esc(x.text).replace(/\n/g, "<br>")}</div>` : ""}</div>
        ${x.loeschbar ? `<button class="btn rot" data-hdel="${x.id}" title="Notiz löschen">×</button>` : ""}</div>`;
    }).join("") : `<p class="hinweis">Noch keine Einträge.</p>`;
    $$("[data-hdel]").forEach(b => b.onclick = async () => { if (await frage("Notiz löschen?")) { await api("notizen/" + b.dataset.hdel, {method: "DELETE"}); zeichnen(); } });
  };
  $$("[data-hf]").forEach(b => b.onclick = () => { filter = b.dataset.hf; $$("[data-hf]").forEach(x => x.classList.toggle("prim", x === b)); zeichnen(); });
  $("#hNeu").onclick = async () => {
    const text = $("#hNotiz").value.trim(); if (!text) return toast("Die Notiz ist leer.", true);
    try { await api("notizen", {method: "POST", body: {kunde_id: a.kunde_id, auftrag_id: a.id, text}}); $("#hNotiz").value = ""; zeichnen(); } catch (e) { toast(e.message, true); }
  };
  $("#hNotiz").onkeydown = e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("#hNeu").click(); };
  const hoch = async files => {
    for (const f of files) {
      const b64 = await new Promise((ok, err) => { const r = new FileReader(); r.onload = () => ok(r.result.split(",")[1]); r.onerror = err; r.readAsDataURL(f); });
      try {
        if (mitOrdner) await api(`auftraege/${a.id}/hochladen`, {method: "POST", body: {pfad: "", dateiname: f.name, daten: b64, historie: true}});
        else await api("anhaenge", {method: "POST", body: {kunde_id: a.kunde_id, auftrag_id: a.id, dateiname: f.name, daten: b64}});
      } catch (e) { toast(e.message, true); }
    }
    toast(files.length + " Datei(en) abgelegt"); zeichnen();
    if (mitOrdner && $("#seite")) projektBrowser($("#seite"), a);
  };
  $("#hDatei").onchange = e => hoch([...e.target.files]);
  const ab = $("#hAblage");
  ab.ondragover = e => { e.preventDefault(); ab.classList.add("drueber"); };
  ab.ondragleave = () => ab.classList.remove("drueber");
  ab.ondrop = e => { e.preventDefault(); ab.classList.remove("drueber"); hoch([...e.dataTransfer.files]); };
  zeichnen();
}
function wochentagDatum(iso) {
  const d = new Date(iso + "T12:00:00");
  return isNaN(d) ? iso : d.toLocaleDateString("de-DE", {weekday: "long", day: "2-digit", month: "2-digit", year: "numeric"});
}


// Wiedervorlagen eines Auftrags (Nachfrage, Pflege, Gewährleistung, eigene)
async function auftragWiedervorlagen(box, a) {
  if (!box || !darf("auftraege", 1)) return;
  const liste = await api("wiedervorlagen?" + new URLSearchParams({auftrag_id: a.id, status: "alle"})).catch(() => []);
  const kann = darf("auftraege", 2);
  box.innerHTML = `<div class="sektion">Wiedervorlagen</div>
    <div class="zeile voll"><div style="display:block;padding:7px 10px;width:100%">
      ${liste.length ? liste.map(w => `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:3px 0;${w.erledigt ? "opacity:.55" : ""}">
        <span class="nw" style="min-width:86px">${datum(w.datum)}</span><span class="tag">${esc(w.art_name)}</span><span style="flex:1 1 240px">${esc(w.text)}</span>
        ${w.erledigt ? `<span class="hinweis">erledigt ${datum(w.erledigt)}</span>` : kann ? `<button class="btn" data-wve="${w.id}">erledigt</button>` : ""}
        ${kann ? `<button class="btn" data-wvd="${w.id}" title="Löschen">✕</button>` : ""}</div>`).join("") : `<span class="hinweis">Keine. Sie entstehen beim Festschreiben der Rechnung (Einstellungen › Aufträge).</span>`}
      ${kann ? `<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap"><input type="date" id="wvD" style="max-width:160px"><input id="wvT" placeholder="Neue Wiedervorlage, z. B. Nachfrage Fronten" style="flex:1 1 240px"><button class="btn" id="wvN">＋</button></div>` : ""}
    </div></div>`;
  const neu = () => auftragWiedervorlagen(box, a);
  $$("[data-wve]", box).forEach(b => b.onclick = async () => { await api("wiedervorlagen/" + b.dataset.wve, {method: "PUT", body: {erledigt: true}}); neu(); });
  $$("[data-wvd]", box).forEach(b => b.onclick = async () => { await api("wiedervorlagen/" + b.dataset.wvd, {method: "DELETE"}); neu(); });
  if ($("#wvN", box)) $("#wvN", box).onclick = async () => {
    if (!$("#wvD", box).value || !$("#wvT", box).value.trim()) return toast("Bitte Datum und Text eingeben.", true);
    try { await api("wiedervorlagen", {method: "POST", body: {auftrag_id: a.id, kunde_id: a.kunde_id, datum: $("#wvD", box).value, text: $("#wvT", box).value}}); neu(); } catch (x) { toast(x.message, true); }
  };
}
