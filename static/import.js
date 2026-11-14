// =====================================================================
//  Kunden importieren (CSV, Excel .xlsx, vCard .vcf)
// =====================================================================
async function ansichtKundenImport(inEinstellungen) {
  if (!inEinstellungen) kopf({krumen: [["Kunden", "#/kunden"]], zurueck: "#/kunden"});
  const z = $("#inhalt");
  let datei = null, info = null;
  const opt = {doppelte: "ueberspringen", gruppe: (E.kundengruppen || [])[0] || ""};
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
      info = await api("kunden/import", {method: "POST", body: {...datei, zuordnung: info ? info.zuordnung : null, gruppe: opt.gruppe}});
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
        ${zeile("Schon vorhandene Kunden", `<div class="radio"><label><input type="radio" name="kiD" value="ueberspringen" ${opt.doppelte === "ueberspringen" ? "checked" : ""}> überspringen</label><label><input type="radio" name="kiD" value="aktualisieren" ${opt.doppelte === "aktualisieren" ? "checked" : ""}> mit den Daten aus der Datei aktualisieren</label>
          <span class="hinweis" style="padding-top:4px">${info.doppelte} von ${info.anzahl} sind schon vorhanden (gleiche Kundennummer, E-Mail oder Name + PLZ)</span></div>`)}
        ${zeile("Gruppe, wenn unklar", `<select id="kiG">${opts(E.kundengruppen || [], opt.gruppe)}</select>`)}
        ${zeile("", `<button class="btn prim" id="kiOk">${info.anzahl} Zeilen importieren</button><a class="btn" href="${inEinstellungen ? "#/einstellungen/import/kunden" : "#/kunden"}">Abbrechen</a>`)}
      </div>`;
    $$("[data-ki]").forEach(s => s.onchange = () => {
      const i = s.dataset.ki;
      if (s.value) Object.keys(info.zuordnung).forEach(k => { if (info.zuordnung[k] === s.value && k !== i && !["bemerkungen", "merkmale"].includes(s.value)) info.zuordnung[k] = ""; });
      info.zuordnung[i] = s.value; pruefen();
    });
    $$("[name=kiD]").forEach(r => r.onchange = () => opt.doppelte = r.value);
    $("#kiG").onchange = e => { opt.gruppe = e.target.value; pruefen(); };
    $("#kiOk").onclick = async () => {
      const b = $("#kiOk"); b.disabled = true; b.textContent = "Wird importiert …";
      try {
        const r = await api("kunden/import", {method: "POST", body: {...datei, zuordnung: info.zuordnung, gruppe: opt.gruppe, doppelte: opt.doppelte, ausfuehren: true}});
        toast(`${r.neu} Kunden neu angelegt` + (r.aktualisiert ? `, ${r.aktualisiert} aktualisiert` : "") + (r.uebersprungen ? `, ${r.uebersprungen} übersprungen` : ""));
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
