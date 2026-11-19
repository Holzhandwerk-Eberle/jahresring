// =====================================================================
//  Kunden importieren (CSV, Excel .xlsx, vCard .vcf)
// =====================================================================
async function ansichtKundenImport(inEinstellungen) {
  if (!inEinstellungen) kopf({krumen: [["Kunden", "#/kunden"]], zurueck: "#/kunden"});
  const z = $("#inhalt");
  let datei = null, info = null;
  const opt = {doppelte: "ueberspringen", gruppe: (E.kundengruppen || [])[0] || "", altbestand: null, plz: false, bestaetigt: null};
  z.innerHTML = `
    <div class="titel"><h2>Kunden importieren</h2></div>
    <div class="kachel">
      <p style="margin-top:0">Bitte eine Datei mit den Kundendaten wählen. Die erste Zeile muss die Spaltenüberschriften enthalten.
      Möglich sind <b>CSV</b> (z. B. Export aus einem anderen Programm oder Excel „CSV UTF-8“ bzw. „CSV (Trennzeichen-getrennt)“),
      <b>Excel (.xlsx)</b> und <b>vCard (.vcf)</b> aus Outlook oder Google-Kontakte.</p>
      <div class="pb-drop" id="kiDrop">Datei hierher ziehen oder <a href="#" id="kiWahl">Datei wählen</a><input type="file" id="kiDatei" accept=".csv,.txt,.xlsx,.vcf" hidden></div>
    </div>
    <div id="kiSchritt2"></div>`;
  const lesen = async f => {
    const buf = new Uint8Array(await f.arrayBuffer());
    let bin = ""; for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
    datei = {daten: btoa(bin), dateiname: f.name};
    info = null;
    await pruefen();
  };
  const pruefen = async () => {
    try {
      info = await api("kunden/import", {method: "POST", body: {...datei, zuordnung: info ? info.zuordnung : null, gruppe: opt.gruppe, plz_auffuellen: opt.plz}});
      opt.bestaetigt = new Set(info.dubletten.filter(x => x.sicher).map(x => x.zeile));   // vorausgewählt nur, wo der Name übereinstimmt
      zeichnen();
    } catch (e) { toast(e.message, true); }
  };
  const zeichnen = () => {
    const felder = info.felder;
    const zuord = info.zuordnung;
    const beispiel = i => info.beispiele.map(r => r[i]).filter(Boolean).slice(0, 3).map(x => esc(String(x).slice(0, 40))).join(" · ");
    $("#kiSchritt2").innerHTML = `
      <h3 style="margin-top:16px">1. Spalten zuordnen <span class="hinweis" style="font-weight:400">· ${esc(datei.dateiname)} · ${info.anzahl} Datenzeilen</span></h3>
      <table class="liste"><tr><th>Spalte in der Datei</th><th>Beispiele</th><th style="width:260px">wird übernommen als</th></tr>
        ${info.kopf.map((h, i) => `<tr><td><b>${esc(h || "(ohne Überschrift)")}</b></td><td class="hinweis">${beispiel(i)}</td>
          <td><select data-ki="${i}" style="width:100%"><option value="">— nicht übernehmen —</option>${felder.map(([k, n]) => `<option value="${k}" ${zuord[i] === k ? "selected" : ""}>${n}</option>`).join("")}</select></td></tr>`).join("")}
      </table>
      <p class="hinweis">Aus Firma, Anrede, Vor- und Nachname, Zusatz und Straße baut das Programm die Briefanschrift. Die Briefanrede („Sehr geehrte Frau …“) entsteht aus Anrede und Nachname, sofern es keine eigene Spalte dafür gibt. Ohne Spalte „Kundengruppe“ werden Einträge mit Firma Gewerbe-, die übrigen Privatkunden.</p>
      <h3 style="margin-top:16px">2. Vorschau der ersten Kunden</h3>
      ${info.vorschau.length ? `<table class="liste"><tr><th>Nr.</th><th>Kurzname</th><th>Anschrift</th><th>PLZ / Ort</th><th>Telefon</th><th>E-Mail</th><th>Gruppe</th><th>Briefanrede</th><th></th></tr>
        ${info.vorschau.map(k => `<tr><td>${k.nummer || "<span class=hinweis>neu</span>"}</td><td><b>${esc(k.kurzname)}</b></td><td style="white-space:pre-line">${esc(k.anschrift)}</td>
          <td>${esc(k.plz || "")} ${esc(k.ort || "")}</td><td>${esc(k.telefon || "")}</td><td>${esc(k.email1 || "")}</td><td>${esc(k.gruppe || "")}</td><td class="hinweis">${esc(k.anrede)}</td>
          <td>${k._doppelt ? `<span class="tag" title="Diesen Kunden gibt es schon">schon vorhanden</span>` : ""}</td></tr>`).join("")}</table>`
        : `<div class="leer">Mit dieser Zuordnung entsteht kein Kunde. Bitte mindestens Firma, Nachname oder Kurzname zuordnen.</div>`}
      <h3 style="margin-top:16px">3. Importieren</h3>
      <div class="form" style="grid-template-columns:1fr">
        ${zeile("Die Datei enthält", `<div class="radio"><label><input type="radio" name="kiAlt" value="1" ${opt.altbestand === true ? "checked" : ""}> Kunden aus dem bisherigen Programm, zu denen es Rechnungen gibt</label>
          <label><input type="radio" name="kiAlt" value="0" ${opt.altbestand === false ? "checked" : ""}> reine Kontakte ohne Belege</label>
          <span class="hinweis" style="padding-top:4px">Kunden mit Rechnungen bekommen die Aufbewahrungsfrist und lassen sich bis dahin weder löschen noch anonymisieren. Kontakte bleiben löschbar.</span></div>`)}
        ${info.plz_vier.anzahl ? zeile("Postleitzahlen", `<div class="spalte"><label><input type="checkbox" id="kiPlz" ${opt.plz ? "checked" : ""}> vierstellige Postleitzahlen mit führender Null ergänzen (deutsche Anschriften)</label>
          <span class="hinweis" style="color:var(--rot)">${info.plz_vier.anzahl} ${info.plz_vier.anzahl === 1 ? "Postleitzahl hat" : "Postleitzahlen haben"} vier Stellen und keine Landesangabe, z. B. ${esc(info.plz_vier.beispiele.join(" · "))}.
          Excel speichert Postleitzahlen oft als Zahl, dann fehlt die führende Null. Anschriften in Österreich oder der Schweiz bleiben vierstellig: dann nicht ergänzen oder eine Spalte „Land“ zuordnen.</span></div>`) : ""}
        ${info.tel_ohne_null.anzahl ? zeile("Telefonnummern", `<span class="hinweis" style="color:var(--rot)" id="kiTel">${info.tel_ohne_null.anzahl} ${info.tel_ohne_null.anzahl === 1 ? "Telefonnummer beginnt" : "Telefonnummern beginnen"} nicht mit 0 oder +, z. B. ${esc(info.tel_ohne_null.beispiele.join(" · "))}.
          Vermutlich fehlt die führende Null (in Excel als Zahl gespeichert). Das Programm ergänzt sie nicht: bitte in der Datei als Text formatieren oder nach dem Import berichtigen.</span>`) : ""}
        ${zeile("Schon vorhandene Kunden", `<div class="radio"><label><input type="radio" name="kiD" value="ueberspringen" ${opt.doppelte === "ueberspringen" ? "checked" : ""}> überspringen</label><label><input type="radio" name="kiD" value="aktualisieren" ${opt.doppelte === "aktualisieren" ? "checked" : ""}> mit den Daten aus der Datei aktualisieren</label>
          <span class="hinweis" style="padding-top:4px">${info.doppelte} von ${info.anzahl} sind schon vorhanden (gleiche Kundennummer, E-Mail oder Name + PLZ)</span></div>`)}
        ${opt.doppelte === "aktualisieren" && info.dubletten.length ? `<div id="kiDub" style="grid-column:1/-1">
          <p class="hinweis" style="margin:4px 0">Aktualisiert werden nur die angehakten Kunden und nur die Felder, die in der Datei stehen; Konditionen, Gruppe und Briefanrede bleiben, wenn die Datei sie nicht enthält.
          Nicht vorausgewählt sind Treffer, bei denen der Name abweicht – dieselbe E-Mail-Adresse oder Kundennummer kann zu einem anderen Menschen gehören.</p>
          <table class="liste"><tr><th><input type="checkbox" id="kiDubAlle" title="alle an- oder abwählen"></th><th>Zeile</th><th>in der Datei</th><th>vorhandener Kunde</th><th>gleich über</th><th>Änderungen</th></tr>
          ${info.dubletten.map(x => `<tr><td><input type="checkbox" data-dub="${x.zeile}" ${opt.bestaetigt.has(x.zeile) ? "checked" : ""}></td><td>${x.zeile}</td>
            <td><b>${esc(x.datei.kurzname)}</b><div class="hinweis">${esc(x.datei.plz)} ${esc(x.datei.ort)}</div></td>
            <td><a href="#/kunde/${x.bestand.id}" target="_blank">${esc(String(x.bestand.nummer || ""))}</a> ${esc(x.bestand.kurzname || "")}<div class="hinweis">${esc(x.bestand.plz || "")} ${esc(x.bestand.ort || "")}</div></td>
            <td>${esc(x.grund)}${x.sicher ? "" : `<div style="color:var(--rot)">Name weicht ab</div>`}</td>
            <td class="hinweis">${x.aenderungen.length ? x.aenderungen.map(([f, a, n]) => `${esc(f)}: ${esc(a || "–")} → <b>${esc(n || "–")}</b>`).join("<br>") : "keine"}</td></tr>`).join("")}</table>
          ${info.doppelte > info.dubletten.length ? `<p class="hinweis">Gezeigt werden die ersten ${info.dubletten.length} von ${info.doppelte}; die übrigen bleiben unverändert.</p>` : ""}</div>` : ""}
        ${zeile("Gruppe, wenn unklar", `<select id="kiG">${opts(E.kundengruppen || [], opt.gruppe)}</select>`)}
        ${zeile("", `<button class="btn prim" id="kiOk">${info.anzahl} Zeilen importieren</button><a class="btn" href="${inEinstellungen ? "#/einstellungen/import/kunden" : "#/kunden"}">Abbrechen</a>`)}
      </div>`;
    $$("[data-ki]").forEach(s => s.onchange = () => {
      const i = s.dataset.ki;
      if (s.value) Object.keys(info.zuordnung).forEach(k => { if (info.zuordnung[k] === s.value && k !== i && !["bemerkungen", "merkmale"].includes(s.value)) info.zuordnung[k] = ""; });
      info.zuordnung[i] = s.value; pruefen();
    });
    $$("[name=kiD]").forEach(r => r.onchange = () => { opt.doppelte = r.value; zeichnen(); });
    $$("[name=kiAlt]").forEach(r => r.onchange = () => { opt.altbestand = r.value === "1"; });
    if ($("#kiPlz")) $("#kiPlz").onchange = e => { opt.plz = e.target.checked; pruefen(); };
    $$("[data-dub]").forEach(c => c.onchange = () => { c.checked ? opt.bestaetigt.add(+c.dataset.dub) : opt.bestaetigt.delete(+c.dataset.dub); });
    if ($("#kiDubAlle")) $("#kiDubAlle").onchange = e => $$("[data-dub]").forEach(c => { c.checked = e.target.checked; c.onchange(); });
    $("#kiG").onchange = e => { opt.gruppe = e.target.value; pruefen(); };
    $("#kiOk").onclick = async () => {
      if (opt.altbestand === null) return toast("Bitte oben wählen, ob die Datei Kunden mit Rechnungen oder reine Kontakte enthält.", true);
      const b = $("#kiOk"); b.disabled = true; b.textContent = "Wird importiert …";
      try {
        const r = await api("kunden/import", {method: "POST", body: {...datei, zuordnung: info.zuordnung, gruppe: opt.gruppe, doppelte: opt.doppelte, ausfuehren: true,
          altbestand: opt.altbestand, plz_auffuellen: opt.plz, bestaetigt: [...opt.bestaetigt]}});
        const unveraendert = (r.uebersprungen || 0) + (r.unbestaetigt || 0);
        toast(`${r.neu} Kunden neu angelegt` + (r.aktualisiert ? `, ${r.aktualisiert} aktualisiert` : "") + (unveraendert ? `, ${unveraendert} vorhandene unverändert` : ""));
        location.hash = "#/kunden";
      } catch (e) { toast(e.message, true); b.disabled = false; b.textContent = "Erneut versuchen"; }
    };
  };
  $("#kiWahl").onclick = e => { e.preventDefault(); $("#kiDatei").click(); };
  $("#kiDatei").onchange = e => e.target.files[0] && lesen(e.target.files[0]);
  const drop = $("#kiDrop");
  drop.ondragover = e => { e.preventDefault(); drop.classList.add("ueber"); };
  drop.ondragleave = () => drop.classList.remove("ueber");
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove("ueber"); if (e.dataTransfer.files[0]) lesen(e.dataTransfer.files[0]); };
}
