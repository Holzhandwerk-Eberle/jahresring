"use strict";
// =====================================================================
//  Jahresring – Startseite / Controlling
// =====================================================================
const START = {jahr: new Date().getFullYear()};
const FARBE_AKT = "#b8692a", FARBE_VJ = "#2f78a8";
const kEur = v => Math.abs(v) >= 10000 ? n2(v / 1000, 1) + " T€" : eur(v);
const tageText = n => n === 0 ? "heute" : n === 1 ? "seit 1 Tag" : `seit ${n} Tagen`;

function begruessung() {
  const h = new Date().getHours();
  const name = (E.firma_inhaber || "").split(" ")[0];
  return (h < 11 ? "Guten Morgen" : h < 18 ? "Hallo" : "Guten Abend") + (name ? ", " + name : "");
}

function kachel(titel, wert, unter = "", {ton = "", link = "", hilfe = "", rechts = ""} = {}) {
  let inner = `<div class="sk-t">${titel}${hilfe ? ` <span class="sk-hilfe" tabindex="0" data-hilfe="${esc(hilfe)}">ⓘ</span>` : ""}</div><div class="sk-w">${wert}</div><div class="sk-u ${ton}">${unter}</div>`;
  if (rechts) inner = `<div class="sk-zweig"><div class="sk-links">${inner}</div><div class="sk-r">${rechts}</div></div>`;
  return link ? `<a class="sk" href="${link}">${inner}</a>` : `<div class="sk">${inner}</div>`;
}

function umsatzDiagramm(akt, vj, jahr, breite = 760) {
  const W = Math.max(420, Math.round(breite)), H = 240, L = 52, R = 10, T = 12, B = 26;
  const max = Math.max(1, ...akt, ...vj);
  const schritt = [500, 1000, 2000, 2500, 5000, 10000, 20000, 25000, 50000, 100000].find(s => max / s <= 5) || 200000;
  const oben = Math.ceil(max / schritt) * schritt;
  const y = v => T + (H - T - B) * (1 - v / oben);
  const gw = (W - L - R) / 12, bw = Math.min(22, (gw - 10) / 2);
  const M = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
  let g = "";
  for (let v = 0; v <= oben + 0.1; v += schritt)
    g += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="dg-grid"/><text x="${L - 6}" y="${y(v) + 4}" class="dg-ax" text-anchor="end">${v >= 1000 ? n2(v / 1000, v % 1000 ? 1 : 0) + " T" : n2(v, 0)}</text>`;
  const balken = (x, v, f, tip) => v > 0
    ? `<path d="M${x},${y(0)} V${y(v) + 4} q0,-4 4,-4 h${bw - 8} q4,0 4,4 V${y(0)} Z" fill="${f}"/>` : "";
  for (let i = 0; i < 12; i++) {
    const x0 = L + i * gw + (gw - 2 * bw - 2) / 2;
    g += balken(x0, vj[i], FARBE_VJ, `${M[i]} ${jahr - 1}: ${eur(vj[i])}`);
    g += balken(x0 + bw + 2, akt[i], FARBE_AKT, `${M[i]} ${jahr}: ${eur(akt[i])}`);
    g += `<rect x="${L + i * gw}" y="${T}" width="${gw}" height="${H - T - B}" fill="transparent" data-tip="${esc(`${M[i]}: ${jahr} ${eur(akt[i])} · ${jahr - 1} ${eur(vj[i])}`)}"/>`;
    g += `<text x="${L + i * gw + gw / 2}" y="${H - 8}" class="dg-ax" text-anchor="middle">${M[i]}</text>`;
  }
  g += `<line x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}" class="dg-null"/>`;
  return `<div class="dg-legende"><span><i style="background:${FARBE_AKT}"></i>${jahr}</span><span><i style="background:${FARBE_VJ}"></i>${jahr - 1}</span></div>
    <div class="dg-box"><svg viewBox="0 0 ${W} ${H}" class="dg" role="img" aria-label="Umsatz netto je Monat ${jahr} und ${jahr - 1}">${g}</svg><div class="dg-tip"></div></div>
    <details class="dg-tabelle"><summary>Als Tabelle</summary><table class="liste"><tr><th>Monat</th><th class="r">${jahr}</th><th class="r">${jahr - 1}</th></tr>
      ${M.map((m, i) => `<tr><td>${m}</td><td class="r">${eur(akt[i])}</td><td class="r">${eur(vj[i])}</td></tr>`).join("")}</table></details>`;
}
function diagrammBinden(root) {
  const box = $(".dg-box", root); if (!box) return;
  const tip = $(".dg-tip", box);
  box.onmousemove = e => {
    const t = e.target.closest("[data-tip]");
    if (!t) { tip.style.display = "none"; return; }
    const r = box.getBoundingClientRect();
    tip.textContent = t.dataset.tip; tip.style.display = "block";
    tip.style.left = Math.min(r.width - 230, e.clientX - r.left + 12) + "px"; tip.style.top = (e.clientY - r.top - 34) + "px";
  };
  box.onmouseleave = () => tip.style.display = "none";
}

async function ansichtStart(wieder) {
  kopf({});
  const z = $("#inhalt");
  const d = wieder === true && START._d ? START._d : (START._d = await api("start?jahr=" + START.jahr));
  // Lange Listen zeigen zuerst nur die ersten 20 Einträge; „alle anzeigen“ blendet den Rest ein (ohne neu zu laden)
  const ALLE = START.alle || (START.alle = {}), GRENZE = 20;
  const erste = (key, liste) => ALLE[key] ? liste : liste.slice(0, GRENZE);
  const alle = (key, liste) => liste.length <= GRENZE ? "" : `<div style="margin-top:6px"><a href="#" data-alle="${key}">${ALLE[key] ? "nur die ersten " + GRENZE + " anzeigen" : `alle ${liste.length} anzeigen ›`}</a></div>`;
  const k = d.kennzahlen, j = d.jahr;
  const diff = k.umsatz_vj ? (k.umsatz - k.umsatz_vj) / Math.abs(k.umsatz_vj) * 100 : null;
  const quoteBasis = k.quote_erteilt + k.quote_abgesagt;
  const quote = quoteBasis ? Math.round(k.quote_erteilt / quoteBasis * 100) : null;
  const nachfassen = d.angebote.filter(a => a.faellig).length;
  const statusAuftrag = (E.auftragsstatus || []).find(s => !(E.status_angebot || []).includes(s) && !(E.status_ende || []).includes(s)) || "Auftrag";
  const kontakt = a => [a.telefon ? `<a href="tel:${esc(a.telefon.replace(/[^\d+]/g, ""))}" title="${esc(a.telefon)}">☎</a>` : "", a.email1 ? `<a href="mailto:${esc(a.email1)}" title="${esc(a.email1)}">✉</a>` : ""].join(" ");

  z.innerHTML = `
    <div class="titel"><h2>${begruessung()}</h2><span class="hinweis">${new Date().toLocaleDateString("de-DE", {weekday: "long", day: "numeric", month: "long"})} · KW ${kw(new Date())}</span>
      <div class="rechts"><select id="stJahr">${[0, 1, 2, 3].map(i => new Date().getFullYear() - i).map(y => `<option ${y === j ? "selected" : ""}>${y}</option>`).join("")}</select></div></div>
    ${E._ort_warnung && ICH.rechte.inhaber ? `<div class="kachel" style="border-left:4px solid var(--rot);margin-bottom:12px">${esc(E._ort_warnung)}</div>` : ""}
    ${E._sicherung_erinnerung && ICH.rechte.inhaber ? `<div class="kachel" style="border-left:4px solid #c9a227;margin-bottom:12px">⚠ ${esc(E._sicherung_erinnerung)} <a href="#/einstellungen/service/sicherung">Zur Datensicherung ›</a></div>` : ""}
    <div id="stAS"></div>

    <div class="sk-raster">
      ${kachel(`Umsatz netto ${j}`, eur(k.umsatz), diff == null ? `Vorjahr gesamt ${eur(k.umsatz_vj_gesamt)}` : `${diff >= 0 ? "▲" : "▼"} ${n2(Math.abs(diff), 0)} % zum Vorjahr (${kEur(k.umsatz_vj)})`, {ton: diff == null ? "" : diff >= 0 ? "gut" : "schlecht", link: "#/belege",
        rechts: `<div><span>brutto</span><b>${eur(k.umsatz_brutto || 0)}</b></div><div><span>USt.</span><b>${eur(k.umsatz_ust || 0)}</b></div>`, hilfe: (E.umsatz_basis || "zahlung") === "zahlung"
        ? "Zahlungseingänge (netto, ohne Mahnkosten, Skonto mindert) nach Zahlungsdatum – eine Rechnung zählt erst, wenn sie bezahlt ist; bis dahin steht sie bei den offenen Forderungen. Erstattungen nach einem Storno zählen negativ. Vergleich mit dem Vorjahr bis zum gleichen Tag."
        : "Festgeschriebene Rechnungen, Abschläge und Stornos (netto) nach Rechnungsdatum. Vergleich mit dem Vorjahr bis zum gleichen Tag."})}
      ${kachel("Rohertrag", eur(k.rohertrag), (k.umsatz ? `${n2(k.rohertrag_pz, 0)} % vom Umsatz · ` : "noch kein Umsatz · ") + `Material bezahlt ${kEur(k.material)}`, {hilfe: k.material_basis === "Zahlung" ? "Wie in der EÜR: Umsatz (Zahlungseingänge, netto) minus Einkauf (alle bezahlten Zahlungsaufträge an Lieferanten, netto, abzüglich Skonto; ohne Lohn und ohne die Lieferantengruppen unter Einstellungen › Kunden & Aufträge › „Nicht im Rohertrag“), jeweils nach Zahlungsdatum. Rechnungen ohne Zahlungsdatum („bezahlt“) zählen noch nicht." : "Umsatz nach Rechnungsdatum minus gekauftes Material nach Belegdatum (netto)."})}
      ${kachel("Ertrag je Stunde", k.stunden ? eur(k.ertrag_je_stunde) : "–", k.stunden ? `${n2(k.stunden, 0)} h gebucht${k.ziel_stundensatz ? ` · Ziel ${eur(k.ziel_stundensatz)}` : ""}` : "noch keine Stunden gebucht", {ton: k.ziel_stundensatz && k.stunden ? (k.ertrag_je_stunde >= k.ziel_stundensatz ? "gut" : "schlecht") : "", hilfe: "Rohertrag geteilt durch gebuchte Ist-Stunden im Jahr. Das ist, was jede Werkstattstunde nach Material tatsächlich eingebracht hat. Ziel unter Einstellungen > Kalender."})}
      ${kachel("Auftragsbestand", eur(k.auftragsbestand), `${d.laufend.length} laufende Aufträge, noch abzurechnen`, {link: "#/kalender/planung", hilfe: "Summe der beauftragten Positionen minus bereits gestellte Rechnungen."})}
      ${kachel("Offene Angebote", eur(k.angebotsvolumen), `${d.angebote.length} Angebote${nachfassen ? ` · <b>${nachfassen} nachfassen</b>` : ""}`, {ton: nachfassen ? "achtung" : ""})}
      ${kachel(`Angebotsquote ${j}`, quote == null ? "–" : quote + " %", `${k.quote_erteilt} erteilt · ${k.quote_abgesagt} abgesagt · ${k.quote_offen} offen`, {hilfe: "Anteil der erteilten Aufträge an allen entschiedenen Angeboten des Jahres."})}
      ${kachel("Offene Forderungen", eur(k.forderungen), k.forderungen_ueberfaellig ? `davon überfällig ${eur(k.forderungen_ueberfaellig)} (${k.anzahl_ueberfaellig})` : "nichts überfällig", {ton: k.forderungen_ueberfaellig ? "schlecht" : "gut", link: "#/op"})}
      ${kachel("Offene Lieferantenrechnungen", eur(k.verbindlichkeiten), (k.verbindlichkeiten_ueberfaellig ? `<span class="rot-t">überfällig ${eur(k.verbindlichkeiten_ueberfaellig)} (${k.verbindlichkeiten_anzahl_ueberfaellig})</span><br>` : "") + (k.verbindlichkeiten_7t ? `fällig in 7 Tagen: ${eur(k.verbindlichkeiten_7t)}` : "nichts fällig in 7 Tagen") + (k.rechnungspost ? ` · <b>${k.rechnungspost} neu im Postfach</b>` : ""), {ton: k.verbindlichkeiten_7t || k.rechnungspost ? "achtung" : "", link: "#/zahlungen"})}
    </div>

    <div class="st-raster">
      <section class="st-box st-breit"><h3>Laufende Aufträge <span class="st-anz">${d.laufend.length}</span></h3>
        ${d.laufend.length ? `<table class="liste"><tr><th>Auftrag</th><th>Kunde</th><th>Status</th><th class="r">Auftragswert</th><th class="r">berechnet</th><th style="width:200px">Stunden Ist / Soll</th><th>Nächster Termin</th></tr>
          ${erste("laufend", d.laufend).map(a => `<tr class="klick" data-link="#/auftrag/${a.id}"><td><a href="#/auftrag/${a.id}">${esc(a.nummer)}</a> ${esc(kurz(a.bezeichnung, 30))}</td><td>${esc(a.kunde)}</td><td>${statusMitSchritt(a)}</td>
            <td class="r">${eur(a.netto)}</td><td class="r">${a.berechnet ? eur(a.berechnet) : "–"}</td>
            <td class="fs-zelle">${a.soll_stunden ? fortschritt(a.ist_stunden, a.soll_stunden) : `${n2(a.ist_stunden, 1)} h`}</td>
            <td>${a.naechster_termin ? `<span class="km-e" style="--f:${typFarbe(a.naechster_termin.typ)};display:inline-block">${esc(a.naechster_termin.typ)}</span> ${datum(a.naechster_termin.von)}` : a.lieferung ? `geliefert ${datum(a.lieferung)}` : `<span class="hinweis">nicht geplant</span>`}</td></tr>`).join("")}</table>${alle("laufend", d.laufend)}`
          : `<div class="hinweis">Keine laufenden Aufträge.</div>`}</section>

      <section class="st-box"><h3>Termine nächste 2 Wochen</h3>
        ${d.termine.length ? `<div class="st-liste">${d.termine.map(t => `<div class="st-z"><div class="st-h"><span><span class="km-e" style="--f:${typFarbe(t.typ)};display:inline-block">${esc(t.typ)}</span> ${t.auftragsnr ? `<a href="#/auftrag/${t.auftrag_id}">${esc(t.auftragsnr)} ${esc(t.kunde || "")}</a>` : esc(t.titel || "")}</span>
          <span class="hinweis">${datum(t.von).slice(0, 6)}${t.bis !== t.von ? "–" + datum(t.bis).slice(0, 6) : ""}</span></div></div>`).join("")}</div>`
          : `<div class="hinweis">Keine Termine geplant.</div>`}
        <a class="btn" href="#/kalender/planung" style="margin-top:8px;display:inline-block">Zur Planung</a></section>

      <section class="st-box"><h3>Geld</h3>
        <h4>Überfällige Kundenrechnungen</h4>
        ${d.ueberfaellig.length ? erste("ueberfaellig", d.ueberfaellig).map(o => `<div class="st-z faellig"><div class="st-h"><a href="#/beleg/${o.beleg_id}">${esc(o.nummer)} · ${esc(o.kunde || "")}</a><span class="st-betrag">${eur(o.offen)}</span></div><div class="st-u"><span class="rot-t">fällig seit ${datum(o.faellig)}</span>${o.letzte_mahnung ? ` · ${esc(o.letzte_mahnung.name)} vom ${datum(o.letzte_mahnung.datum)}` : ""}${o.mahnsperre ? " · Mahnsperre" : o.mahnvorschlag && o.mahnvorschlag.stufe != null ? (o.mahnvorschlag.jetzt ? ` · <a href="#/op/mahnwesen/${o.id}">${esc(o.mahnvorschlag.name)} erstellen ›</a>` : ` · ${esc(o.mahnvorschlag.name)} ab ${datum(o.mahnvorschlag.ab)}`) : ""}</div></div>`).join("") + alle("ueberfaellig", d.ueberfaellig) : `<div class="hinweis">Keine.</div>`}
        <h4 style="margin-top:12px">Zahlungen an Lieferanten (überfällig, 7 Tage, Skonto)</h4>
        ${d.zahlungen_faellig.length ? erste("zahlungen", d.zahlungen_faellig).map(zg => `<div class="st-z${zg.faellig && zg.faellig < d.heute ? " faellig" : ""}"><div class="st-h"><a href="#/zahlung/${zg.id}">${esc(zg.lieferant)}${zg.belegnr ? " · Rg. " + esc(zg.belegnr) : ""}</a><span class="st-betrag">${eur(zg.betrag)}</span></div>
          <div class="st-u">${zg.skonto > 0 && zg.skonto_bis >= d.heute ? `<span style="color:var(--gruen)">Skonto bis ${datum(zg.skonto_bis)}</span> · ` : ""}${zg.faellig && zg.faellig < d.heute ? `<span class="rot-t">überfällig seit ${datum(zg.faellig)}</span> · schon bezahlt? Im Zahlungsauftrag „bezahlt“ eintragen` : `fällig ${datum(zg.faellig)}`}</div></div>`).join("") + alle("zahlungen", d.zahlungen_faellig) : `<div class="hinweis">Nichts fällig.</div>`}
      </section>

      <section class="st-box"><h3>Angebote nachfassen <span class="st-anz">${d.angebote.length}</span></h3>
        ${d.angebote.length ? `<div class="st-liste">${erste("angebote", d.angebote).map(a => `<div class="st-z${a.faellig ? " faellig" : ""}" data-a="${a.id}">
          <div class="st-h"><a href="#/auftrag/${a.id}"><b>${esc(a.kunde)}</b> · ${esc(kurz(a.bezeichnung, 38))}</a><span class="st-betrag">${eur(a.wert || 0)}</span></div>
          <div class="st-u">${a.angebot ? `<a href="#/auftrag/${a.id}/belege">${esc(a.angebot.nummer)}</a> vom ${datum(a.angebot.datum)}` : "noch kein Angebot erstellt"}${a.nachgefasst ? ` · nachgefasst ${datum(a.nachgefasst)}` : ""} · <span class="${a.faellig ? "rot-t" : ""}">${tageText(a.seit)}</span> ${kontakt(a)}
            <span class="st-akt"><button class="btn" data-nf="${a.id}" title="Heute nachgefasst">nachgefasst</button><button class="btn" data-st="${a.id}" data-wert="${esc(statusAuftrag)}">erteilt</button><button class="btn rot" data-st="${a.id}" data-wert="Abgesagt">abgesagt</button></span></div></div>`).join("")}</div>${alle("angebote", d.angebote)}`
          : `<div class="hinweis">Keine offenen Angebote.</div>`}
        <p class="hinweis">Nachfassen nach ${E.nachfass_tage || 10} Tagen ohne Rückmeldung.</p></section>

      <section class="st-box"><h3>Offene Anfragen <span class="st-anz">${d.anfragen.length}</span></h3>
        ${d.anfragen.length ? `<div class="st-liste">${erste("anfragen", d.anfragen).map(a => `<div class="st-z${a.ueberfaellig ? " faellig" : ""}">
          <div class="st-h"><a href="#/auftrag/${a.id}"><b>${esc(a.kunde)}</b> · ${esc(kurz(a.bezeichnung, 40))}</a></div>
          <div class="st-u"><span class="${a.ueberfaellig ? "rot-t" : ""}">${tageText(a.alter)}</span> ${kontakt(a)} · ${a.entwurf ? `<a href="#/beleg/${a.entwurf.id}" title="Erstellt, aber noch nicht versendet">${esc(a.entwurf.nummer || "Angebot")} noch nicht versendet ›</a>` : `<a href="#/auftrag/${a.id}/positionen">Angebot erstellen ›</a>`}</div></div>`).join("")}</div>${alle("anfragen", d.anfragen)}`
          : `<div class="hinweis">Keine offenen Anfragen.</div>`}
        <button class="btn" id="stNeuAnfrage" style="margin-top:8px">+ Neue Anfrage</button></section>

      ${(d.geburtstage || []).length ? `<section class="st-box"><h3>Geburtstage <span class="st-anz">${d.geburtstage.length}</span></h3>
        <div class="st-liste">${d.geburtstage.map(g => `<div class="st-z${g.in_tagen === 0 ? " faellig" : ""}"><div class="st-h"><a href="#/kunde/${g.id}">🎂 ${esc(g.kurzname)}</a>
          <span class="hinweis">${g.in_tagen === 0 ? "<b>heute</b>" : g.in_tagen === 1 ? "morgen" : datum(g.datum).slice(0, 6)}${g.alter ? ` · wird ${g.alter}` : ""}</span></div>
          <div class="st-u">${g.gesendet ? "✓ Glückwunsch gesendet" : g.email ? `<a href="#" data-gb="${g.id}">Glückwunsch-Mail schreiben ›</a>` : "keine E-Mail-Adresse"}</div></div>`).join("")}</div></section>` : ""}

      ${(d.beschaffung || []).length ? `<section class="st-box"><h3>Platten beschaffen <span class="st-anz">${d.beschaffung.length}</span></h3>
        <div class="st-liste">${erste("beschaffung", d.beschaffung).map(x => `<div class="st-z faellig"><div class="st-h"><b>${x.zu_bestellen} × ${esc(x.material)}</b><span class="hinweis">${n2(x.dicke, x.dicke % 1 ? 1 : 0)} mm · ${n2(x.laenge, 0)} × ${n2(x.breite, 0)}</span></div>
          <div class="st-u">für ${x.auftraege.map(a => a.auftrag_id ? `<a href="#/auftrag/${a.auftrag_id}/werkstatt">${esc(a.nr || a.projekt)}</a>` : esc(a.projekt)).join(", ") || "–"}${x.bestellt ? ` · ${x.bestellt} schon bestellt` : ""}</div></div>`).join("")}</div>${alle("beschaffung", d.beschaffung)}
        <a class="btn" href="#/material/reste" style="margin-top:8px;display:inline-block">Bestellen / Wareneingang ›</a></section>` : ""}

      <section class="st-box st-breit" id="dgBox"><h3>Umsatz je Monat</h3><div id="dgInhalt"></div></section>
    </div>`;
  const na = $("#stNeuAnfrage"); if (na) na.onclick = () => neuerAuftrag(null, null, {titel: "Neue Anfrage", status: (E.status_angebot || ["Anfrage"])[0] || "Anfrage"});
  const dgZeichnen = () => { const b = $("#dgInhalt"); if (!b) return; b.innerHTML = umsatzDiagramm(d.monate.aktuell, d.monate.vorjahr, j, b.clientWidth); diagrammBinden(b); };
  dgZeichnen();
  window.onresize = () => { clearTimeout(START._rs); START._rs = setTimeout(dgZeichnen, 150); };
  $("#stJahr").onchange = e => { START.jahr = +e.target.value; ansichtStart(); };
  asStartHinweis($("#stAS"));
  if (darf("auftraege", 2)) api("cad/neu").then(neu => {
    if (!neu.length || !$("#stJahr")) return;
    const k = document.createElement("div"); k.className = "kachel"; k.style.cssText = "border-left:4px solid var(--akzent);margin-bottom:12px";
    k.innerHTML = `<b>Neue Stücklisten aus dem CAD</b> <span class="hinweis">· in der Positionsliste des Auftrags übernehmen</span>` +
      neu.slice(0, 8).map(x => `<div><a href="#/auftrag/${x.auftrag_id}/positionen">${esc(x.nummer)} ${esc(x.bezeichnung)}</a> · ${esc(x.datei)} <span class="hinweis">${datum(x.geaendert.slice(0, 10))} ${x.geaendert.slice(11, 16)}</span></div>`).join("");
    $(".titel", $("#inhalt")).after(k);
  }).catch(() => {});
  $$("[data-alle]", z).forEach(a => a.onclick = ev => { ev.preventDefault(); const y = scrollY; ALLE[a.dataset.alle] = !ALLE[a.dataset.alle]; ansichtStart(true).then(() => scrollTo(0, y)); });
  $$("tr[data-link]", z).forEach(tr => tr.onclick = ev => { if (!ev.target.closest("a")) location.hash = tr.dataset.link; });
  $$("[data-gb]", z).forEach(x => x.onclick = ev => { ev.preventDefault(); mailDialog("kunden/" + x.dataset.gb, "Glückwunsch zum Geburtstag", ok => ok && ansichtStart(), "?vorlage=geburtstag"); });
  $$("[data-nf]", z).forEach(b => b.onclick = async () => { await api("auftraege/" + b.dataset.nf, {method: "PUT", body: {nachgefasst: heute()}}); toast("Als nachgefasst vermerkt"); ansichtStart(); });
  $$("[data-st]", z).forEach(b => b.onclick = async () => {
    if (b.dataset.wert === "Abgesagt" && !await frage("Angebot als abgesagt markieren?")) return;
    await api("auftraege/" + b.dataset.st, {method: "PUT", body: {status: b.dataset.wert}});
    toast(b.dataset.wert === "Abgesagt" ? "Als abgesagt markiert" : "Auftrag erteilt – jetzt im Kalender einplanen"); ansichtStart();
  });
}
