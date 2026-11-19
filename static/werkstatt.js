// =====================================================================
//  Auftrag > Werkstatt und Auftrag > Auswertung
// =====================================================================
const WS_DOKS = [
  ["werkstattauftrag", "Werkstattauftrag", "Anschrift, Vorgabezeiten je Kostenstelle, alle Positionen mit Text, Maßen und Bildern"],
  ["stueckliste", "Stückliste", "Teile je Position mit Fertigmaßen, Kanten, Furnier, Oberfläche, Bearbeitung und Beschlägen"],
  ["materialsummen", "Materialsummen", "Bestellliste: Platten, Massivholz, Kanten, Furnier, Oberfläche und Beschläge summiert, mit Verschnitt"],
];
const AW_DOKS = [
  ["stunden", "Auftragsstunden", "Kalkulierte Stunden je Position und Kostenstelle"],
  ["kosten", "Auftragskosten", "Material, Lohn, Gemeinkosten, Selbstkosten und Wagnis & Gewinn je Position"],
  ["sollist", "Soll/Ist-Vergleich", "Kalkulation gegen gebuchte Stunden und Lieferantenrechnungen"],
  ["lohnmaterial", "Lohn- und Materialkosten", "Lohnkosten je Kostenstelle und Materialkosten mit Materialsummen"],
  ["zeitbericht", "Zeitbericht", "Alle gebuchten Zeiten mit Datum, Uhrzeit, Tätigkeit und Mitarbeiter, mit Summen"],
];
const wsWahl = {art: "werkstattauftrag", opts: {anschrift: 1, telefon: 1, bemerkungen: 1, bilder: 1, preise: 1, erklaerung: 0}, pos: null};
const awWahl = {art: "stunden", ausgabe: "titel"};

function papierQuery(o) {
  return Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== "").map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");
}

async function werkstattSeite(z, a) {
  const pl = await api(`auftraege/${a.id}/positionen`);
  const haupt = pl.positionen || [];
  let zs = {vorhanden: false};
  try { zs = await api("zuschnitt"); } catch (e) {}
  const zsUrl = (E.zuschnitt_url || "").trim();
  const radio = (k, l) => `<label><input type="radio" name="wo_${k}" value="1" ${wsWahl.opts[k] ? "checked" : ""}> Ja</label><label><input type="radio" name="wo_${k}" value="0" ${wsWahl.opts[k] ? "" : "checked"}> Nein</label>`;
  const optZeilen = {
    werkstattauftrag: [["anschrift", "Lieferanschrift"], ["telefon", "Telefon"], ["bemerkungen", "Vollständiger Positionstext"], ["bilder", "Bilder der Positionen"]],
    stueckliste: [["erklaerung", "Erläuterungen anhängen"]],
    materialsummen: [["preise", "EK-Preise und Beträge"]],
    montageauftrag: [["anschrift", "Anschrift"], ["telefon", "Telefon"], ["bemerkungen", "Positionsliste"]],
  };
  const zeichnen = () => {
    const doc = WS_DOKS.find(d => d[0] === wsWahl.art);
    z.innerHTML = `
      <div class="titel"><h2>Werkstatt</h2><span class="speicher"></span></div>
      <div class="form" id="wsA">
        ${zeile("Auftragsstatus", `<select data-f="status">${opts(E.auftragsstatus || [], a.status)}</select>`)}
        ${zeile("Fertigung begonnen", `<input type="date" data-f="fertigung" value="${esc(a.fertigung || "")}">`)}
        ${zeile("Geliefert am", `<input type="date" data-f="lieferung" value="${esc(a.lieferung || "")}">`)}
      </div>
      <div class="sektion" style="margin-top:14px">Werkstattpapiere</div>
      <div class="ws-karten">${WS_DOKS.map(([k, l, t]) => `<button class="ws-karte${k === wsWahl.art ? " aktiv" : ""}" data-art="${k}"><b>${l}</b><span>${t}</span></button>`).join("")}</div>
      <div class="form" style="grid-template-columns:1fr;margin-top:10px">
        ${optZeilen[wsWahl.art].map(([k, l]) => zeile(l, `<div class="radio">${radio(k, l)}</div>`)).join("")}
        ${zeile("Positionen", `<div class="spalte"><label><input type="radio" name="wsPos" value="alle" ${wsWahl.pos ? "" : "checked"}> Alle Positionen</label>
          <label><input type="radio" name="wsPos" value="wahl" ${wsWahl.pos ? "checked" : ""}> Nur ausgewählte</label>
          <div id="wsPosListe" style="${wsWahl.pos ? "" : "display:none"};padding-left:22px">${haupt.map(p => `<label><input type="checkbox" data-pid="${p.id}" ${wsWahl.pos && wsWahl.pos.has(p.id) ? "checked" : ""}> ${esc(p.posnr)} · ${esc(kurz(klartext(p.text), 70))}${p.gesperrt ? ` <span class="hinweis">(gesperrt)</span>` : p.alternativ ? ` <span class="hinweis">(Alternative)</span>` : ""}</label>`).join("") || `<span class="hinweis">Keine Positionen</span>`}</div></div>`)}
        ${zeile("Erstellen", `<a class="btn prim" id="wsAnsehen" target="_blank">${doc[1]} ansehen</a><button class="btn" id="wsPdf">PDF in Projektordner</button>`)}
      </div>

      <div class="sektion" style="margin-top:18px">Zuschnitt</div>
      <div class="kachel" id="wsZs">
        <div id="wsZsInfo" class="hinweis">Teile werden geladen …</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
          <button class="btn prim" id="zsOeffnen">Zuschnittprogramm öffnen</button>
          <button class="btn" id="zsKopieren" title="Teileliste in die Zwischenablage kopieren (Tabulator-getrennt, z. B. zum Einfügen in Excel oder ein Zuschnittprogramm)">Teile kopieren</button>
          <a class="btn" href="/papier/${a.id}/zuschnitt.csv">Zuschnittliste als CSV</a>
        </div>
      </div>
      <div id="wsAS"></div><div id="wsMontage"></div><div id="wsUnterschrift"></div><div id="wsBautagebuch"></div>`;
    asAuftragBox($("#wsAS"), a);
    montageAbschnitt($("#wsMontage"), a);
    if ($("#wsUnterschrift")) unterschriftAbschnitt($("#wsUnterschrift"), a);
    if ($("#wsBautagebuch")) bautagebuchAbschnitt($("#wsBautagebuch"), a);
    autospeichern($("#wsA"), "auftraege/" + a.id, (r, d) => {
      Object.assign(a, r);
      const f = $("#wsA [data-f=fertigung]");
      if ("status" in d && r.fertigung && f && !f.value) { f.value = r.fertigung; toast("Fertigungsbeginn eingetragen: " + datum(r.fertigung)); }
    });
    $$("[data-art]", z).forEach(b => b.onclick = () => { wsWahl.art = b.dataset.art; zeichnen(); });
    $$("[name^=wo_]", z).forEach(el => el.onchange = () => { wsWahl.opts[el.name.slice(3)] = +el.value; link(); });
    $$("[name=wsPos]", z).forEach(el => el.onchange = () => {
      // Vorauswahl: alles, was gefertigt wird (ohne gesperrte und Alternativpositionen)
      wsWahl.pos = el.value === "wahl" ? new Set(haupt.filter(p => !p.gesperrt && !p.alternativ).map(p => p.id)) : null;
      $("#wsPosListe").style.display = wsWahl.pos ? "" : "none";
      $$("[data-pid]", z).forEach(c => c.checked = !!wsWahl.pos && wsWahl.pos.has(+c.dataset.pid)); link();
    });
    $$("[data-pid]", z).forEach(c => c.onchange = () => { if (!wsWahl.pos) return; c.checked ? wsWahl.pos.add(+c.dataset.pid) : wsWahl.pos.delete(+c.dataset.pid); link(); });
    const query = () => ({...wsWahl.opts, pos: wsWahl.pos ? [...wsWahl.pos].join(",") : ""});
    const link = () => { $("#wsAnsehen").href = `/papier/${a.id}/${wsWahl.art}?${papierQuery(query())}`; };
    link();
    $("#wsPdf").onclick = async () => {
      const b = $("#wsPdf"); b.disabled = true; b.textContent = "PDF wird erstellt …";
      try {
        const r = await api(`auftraege/${a.id}/papier`, {method: "POST", body: {art: wsWahl.art, opts: query()}});
        toast(r.projekt_rel ? `PDF gespeichert: ${r.projekt_rel}` : `PDF erstellt (${r.hinweis || r.pfad})`);
        projektBrowser($("#seite"), a);
      } catch (e) { toast(e.message, true); }
      b.disabled = false; b.textContent = "PDF in Projektordner";
    };
    zuschnittBinden(a, zs, zsUrl);
  };
  zeichnen();
}

async function zuschnittBinden(a, zs, zsUrl) {
  let d;
  try { d = await api(`auftraege/${a.id}/zuschnitt`); } catch (e) { $("#wsZsInfo").textContent = e.message; return; }
  const proWk = {};
  d.teile.forEach(t => { const k = t.werkstoff || "ohne Werkstoff"; proWk[k] = proWk[k] || {name: t.werkstoff_name, stueck: 0, m2: 0}; proWk[k].stueck += t.stueck; proWk[k].m2 += t.stueck * t.laenge * t.breite / 1e6; });
  $("#wsZsInfo").innerHTML = d.teile.length
    ? `<b>${d.teile.reduce((s, t) => s + t.stueck, 0)} Teile</b> aus ${d.teile.length} Stücklistenzeilen: ` + Object.entries(proWk).map(([k, v]) => `${esc(k)}${v.name ? " " + esc(v.name) : ""} – ${v.stueck} St., ${n2(v.m2, 2)} m²`).join(" · ")
    : "In den Positionen ist noch keine Stückliste erfasst.";
  const tsv = () => [["Position", "Nr", "Verwendung", "Werkstoff", "Bezeichnung", "Stück", "Länge", "Breite", "Dicke", "Kante oben", "Kante unten", "Kante links", "Kante rechts", "Bemerkung"].join("\t")]
    .concat(d.teile.map(t => [t.position, t.nr, t.verwendung, t.werkstoff, t.werkstoff_name, t.stueck, n2(t.laenge, 1), n2(t.breite, 1), n2(t.dicke, 1),
      t.kanten.oben || "", t.kanten.unten || "", t.kanten.links || "", t.kanten.rechts || "", t.bemerkung].join("\t"))).join("\n");
  $("#zsKopieren").onclick = async () => {
    try { await navigator.clipboard.writeText(tsv()); toast(`${d.teile.length} Zeilen kopiert`); } catch (e) { toast("Kopieren nicht möglich: " + e.message, true); }
  };
  const ob = $("#zsOeffnen");
  if (ob) ob.onclick = async () => {
    // Das eingebaute Zuschnittprogramm lädt die CAD-Verschnittberechnung (JSON) selbst aus dem Ordner 40_Kalkulation
    try { const p = await api(`auftraege/${a.id}/zuschnittplan`); toast(`Zuschnitt: ${p.pfad}`); }
    catch (e) { toast(e.message + " – das Zuschnittprogramm öffnet trotzdem, dort lässt sich eine Datei wählen.", true); }
    window.open(`/zuschnitt/?auftrag=${a.id}`, "_blank");
  };
}

function auswertungSeite(z, a) {
  const zeichnen = () => {
    const doc = AW_DOKS.find(d => d[0] === awWahl.art);
    z.innerHTML = `
      <div class="titel"><h2>Auswertung</h2></div>
      <div class="ws-karten">${AW_DOKS.map(([k, l, t]) => `<button class="ws-karte${k === awWahl.art ? " aktiv" : ""}" data-art="${k}"><b>${l}</b><span>${t}</span></button>`).join("")}</div>
      <div class="form" style="grid-template-columns:1fr;margin-top:10px">
        ${["stunden", "kosten"].includes(awWahl.art) ? zeile("Ausgabe", `<div class="radio">${[["auftrag", "Auftrag"], ["titel", "Auftrag unterteilt nach Titel"], ["seite", "Neue Seite je Titel"]].map(([v, l]) => `<label><input type="radio" name="awA" value="${v}" ${awWahl.ausgabe === v ? "checked" : ""}> ${l}</label>`).join("")}</div>`) : ""}
        ${awWahl.art === "zeitbericht" ? zeile("Zeitraum", `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><input type="date" id="zbVon"> bis <input type="date" id="zbBis">
          <select id="zbSort"><option value="ab">neueste zuerst</option><option value="auf">älteste zuerst</option></select>
          <span class="hinweis">leer = alle Zeiten; Mitarbeiter lassen sich im Bericht oben wählen</span></div>`) : ""}
        ${zeile("Auswertung erstellen", `<a class="btn prim" id="awAnsehen" target="_blank">${doc[1]} ansehen</a><button class="btn" id="awPdf">PDF in Projektordner</button>${awWahl.art === "sollist" ? `<a class="btn" href="#/auftrag/${a.id}/sollist">Soll/Ist am Bildschirm</a>` : ""}`)}
      </div>`;
    $$("[data-art]", z).forEach(b => b.onclick = () => { awWahl.art = b.dataset.art; zeichnen(); });
    $$("[name=awA]", z).forEach(el => el.onchange = () => { awWahl.ausgabe = el.value; link(); });
    const zbQ = () => awWahl.art === "zeitbericht" ? {von: $("#zbVon")?.value, bis: $("#zbBis")?.value, sort: $("#zbSort")?.value} : {ausgabe: awWahl.ausgabe};
    const link = () => { $("#awAnsehen").href = `/papier/${a.id}/${awWahl.art}?${papierQuery(zbQ())}`; };
    $$("#zbVon,#zbBis,#zbSort", z).forEach(el => el.onchange = link);
    link();
    $("#awPdf").onclick = async () => {
      const b = $("#awPdf"); b.disabled = true; b.textContent = "PDF wird erstellt …";
      try {
        const r = await api(`auftraege/${a.id}/papier`, {method: "POST", body: {art: awWahl.art, opts: zbQ()}});
        toast(r.projekt_rel ? `PDF gespeichert: ${r.projekt_rel}` : `PDF erstellt (${r.hinweis || r.pfad})`);
        projektBrowser($("#seite"), a);
      } catch (e) { toast(e.message, true); }
      b.disabled = false; b.textContent = "PDF in Projektordner";
    };
  };
  zeichnen();
}

// Einstellungen: Zuschnittprogramm hinterlegen
function zuschnittEinstellungen() {
  return `<div class="sektion">Werkstatt / Zuschnitt</div>
    ${zeile("Zuschnittprogramm", `<div class="spalte"><span style="padding-top:5px">Eingebaut – <a href="/zuschnitt/" target="_blank">öffnen</a>. Am Tablet: <b>http://${esc((E._netz || {}).ip || "PC-Adresse")}:${esc((E._netz || {}).port || 8765)}/zuschnitt/</b></span>
      <span class="hinweis">Im Auftrag unter Werkstatt öffnet „Zuschnittprogramm öffnen“ direkt die Verschnittberechnung (JSON aus dem CAD) aus dem Projektordner. Das Lager (Reste und Platten) liegt im Büro unter Lager › Reste & Platten.</span></div>`, true)}
    ${zeile("JSON-Ordner", `<input name="zuschnitt_ordner" value="${esc(E.zuschnitt_ordner || "40_Kalkulation")}" style="max-width:260px"><span class="hinweis" style="padding-top:5px">Unterordner im Projektordner, in dem die Zuschnitt-JSON liegt (die neueste wird genommen)</span>`)}
    ${(() => { const z = {aktiv: false, platte_l: 0, platte_b: 0, massiv_l: 50, massiv_b: 10, kanten_abziehen: false, ...(E.zuschnitt_zugabe || {})};
      const n = (k, t) => `<label style="display:flex;gap:6px;align-items:center">${t}<input data-zs="${k}" type="number" step="0.5" value="${z[k]}" style="width:70px"> mm</label>`;
      return zeile("Zuschnittmaß", `<div class="spalte"><label><input type="checkbox" data-zs="aktiv" ${z.aktiv ? "checked" : ""}> Zuschnittmaß in der Stückliste ausweisen (zusätzliche Spalte, auch in der Zuschnitt-CSV)</label>
        <label><input type="checkbox" data-zs="kanten_abziehen" ${z.kanten_abziehen ? "checked" : ""}> Kantenstärken vom Fertigmaß abziehen</label>
        <div style="display:flex;gap:14px;flex-wrap:wrap">${n("platte_l", "Platten Länge +")}${n("platte_b", "Breite +")}</div>
        <div style="display:flex;gap:14px;flex-wrap:wrap">${n("massiv_l", "Massivholz Länge +")}${n("massiv_b", "Breite +")}</div>
        <span class="hinweis">Zuschnittmaß = Fertigmaß (ggf. minus Kanten) plus Zugabe, z. B. Übermaß zum Bündigfräsen oder Abrichten/Hobeln.</span></div>`, true); })()}
    ${zeile("Etikettengröße", `<div class="spalte"><span><input name="etikett_breite" type="number" min="20" max="210" step="0.5" value="${esc(E.etikett_breite ?? 70)}" style="width:90px"> ×
        <input name="etikett_hoehe" type="number" min="20" max="210" step="0.5" value="${esc(E.etikett_hoehe ?? 74)}" style="width:90px"> mm (Breite × Höhe)</span>
        <span class="hinweis">Größe der Etiketten im Etikettendrucker, 20 bis 210 mm. Gilt für die Teile- und Restetiketten des Zuschnittprogramms und für die QR-Etiketten von Material und Resten auf allen Geräten. Die Etiketten sind für 70 × 74 mm gezeichnet; bei einer anderen Größe wird der Inhalt als Ganzes passend skaliert und mittig gesetzt. Im Druckdialog dieselbe Papiergröße wählen.</span></div>`, true)}
    <div class="sektion">Material</div>
    ${zeile("Lagerpreis", `<div class="spalte"><select name="lagerpreis_methode" style="max-width:min(360px,100%)">${[["mittel", "Mittelpreis (gleitender Durchschnitt)"], ["hoechst", "Höchster Einkaufspreis (letzte 12 Monate)"]].map(([v, l]) => `<option value="${v}" ${(E.lagerpreis_methode || "mittel") === v ? "selected" : ""}>${l}</option>`).join("")}</select><span class="hinweis">Preis, mit dem Lagerartikel in die Kalkulation übernommen und als Auftragskosten gebucht werden. Der Lagerwert wird immer zum Durchschnittspreis gerechnet.</span></div>`, true)}
    ${zeile("Lagerorte", `<textarea name="lagerorte" rows="3" placeholder="ein Lagerort je Zeile">${esc((E.lagerorte || []).join("\n"))}</textarea>`)}`;
}

function programmFensterZeilen() {
  return `
    <div class="sektion">Programmfenster</div>
    ${zeile("Fenster", `<div class="spalte"><label><input type="checkbox" name="app_fenster" ${E.app_fenster !== false ? "checked" : ""}> Beim Start als eigenes Programmfenster öffnen (ohne Adressleiste und Lesezeichen)</label><span class="hinweis">Gilt ab dem nächsten Start. Ausgeschaltet öffnet sich ein normaler Browser-Tab.</span></div>`)}
    ${(E._autostart || {}).moeglich ? zeile("Autostart", `<div class="spalte">
      <label><input type="checkbox" id="asAn" ${E._autostart.aktiv ? "checked" : ""}> Beim Anmelden an Windows automatisch starten</label>
      <label style="margin-left:22px"><input type="checkbox" id="asFenster" ${E._autostart.fenster ? "checked" : ""} ${E._autostart.aktiv ? "" : "disabled"}> dabei auch das Programmfenster öffnen</label>
      <span class="hinweis">Ohne Fenster läuft Jahresring still im Hintergrund (Symbol unten rechts in der Taskleiste) – praktisch, damit die Stempeluhr auf den Handys immer erreichbar ist. Öffnen dann über „Jahresring“ auf dem Desktop oder das Taskleistensymbol.</span></div>`) : ""}
    ${ICH.rechte.inhaber ? `<div class="sektion">Update-Hinweis</div>
    ${zeile("Adresse", `<div class="spalte"><input id="upAdr" value="${esc((E.update || {}).adresse || "")}" placeholder="https://… (Datei mit der neuesten Versionsnummer, z. B. version.txt)">
      <span class="hinweis">Leer = ausgeschaltet. Ist eine Adresse eingetragen, fragt das Programm sie einmal am Tag ab und meldet auf der Startseite, wenn dort eine neuere Version steht. Installiert wird nichts von selbst; übertragen wird nur die Abfrage.</span></div>`)}
    ${zeile("Zugangsschlüssel", `<div class="spalte"><input id="upSchl" type="password" autocomplete="new-password" placeholder="${(E.update || {}).schluessel_gesetzt ? "gespeichert – zum Ändern neu eingeben" : "nur bei geschützter Ablage (Lesezugriff)"}" style="max-width:420px">
      <span class="hinweis">Wird verschlüsselt auf diesem PC gespeichert und nie angezeigt.${(E.update || {}).schluessel_gesetzt ? ` <a href="#" id="upSchlWeg">Schlüssel entfernen</a>` : ""}</span></div>`)}
    ${zeile("Stand", `<div><button class="btn" type="button" id="upJetzt">Jetzt prüfen</button> <span class="hinweis" id="upStand">${updateStandText(E._update)}</span></div>`)}` : ""}`;
}
function updateStandText(u) {
  u = u || {};
  if (u.fehler) return `<span style="color:var(--rot)">Prüfung nicht möglich: ${esc(u.fehler)}</span>`;
  if (u.neu) return `<b style="color:var(--akzent)">Neuere Version verfügbar: ${esc(u.neu)}</b> (installiert: ${esc(VERSION)})`;
  return u.geprueft ? `Stand ${datum(u.geprueft.slice(0, 10))} ${esc(u.geprueft.slice(11, 16))}: Das Programm ist aktuell (${esc(VERSION)}).` : "noch nicht geprüft";
}
document.addEventListener("change", async e => {
  if (e.target.id !== "upAdr" && e.target.id !== "upSchl") return;
  try { E = await api("einstellungen", {method: "PUT", body: {update: e.target.id === "upAdr" ? {adresse: e.target.value.trim()} : {schluessel: e.target.value.trim()}}}); toast("Gespeichert"); if (e.target.id === "upSchl") e.target.value = ""; }
  catch (x) { toast(x.message, true); }
});
document.addEventListener("click", async e => {
  const el = e.target.closest && e.target.closest("#upJetzt, #upSchlWeg"); if (!el) return;
  e.preventDefault();
  try {
    if (el.id === "upSchlWeg") { E = await api("einstellungen", {method: "PUT", body: {update: {schluessel_loeschen: true}}}); toast("Schlüssel entfernt"); el.remove(); return; }
    $("#upStand").textContent = "wird geprüft …";
    const u = await api("update/pruefen", {method: "POST"}); E._update = u; $("#upStand").innerHTML = updateStandText(u);
  } catch (x) { toast(x.message, true); }
});
async function autostartSetzen() {
  const an = $("#asAn").checked, fe = $("#asFenster");
  fe.disabled = !an;
  try {
    E._autostart = await api("autostart", {method: "POST", body: {aktiv: an, fenster: an && fe.checked}});
    toast(an ? "Autostart eingerichtet" : "Autostart ausgeschaltet");
  } catch (e) { toast(e.message, true); $("#asAn").checked = !an; }
}
