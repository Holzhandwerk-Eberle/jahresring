"use strict";
// =====================================================================
//  Jahresring – Benutzer & Rechte, Mitarbeiter, Zeiten, Urlaub, Monatsbeleg, Lohn
// =====================================================================

let ICH = null;          // angemeldeter Benutzer {id, login, name, rechte:{bereiche, auftrag_reiter, preise, inhaber}, mitarbeiter_id}
let PMETA = null;        // Personal-Stammdaten (Lohnarten, Tätigkeiten, Aufträge …)
const optsKV = (paare, wert, leer) => (leer !== undefined ? `<option value="">${esc(leer)}</option>` : "") +
  paare.map(([v, l]) => `<option value="${esc(v)}" ${String(v) === String(wert ?? "") ? "selected" : ""}>${esc(l)}</option>`).join("");
const std = v => (v == null ? "" : zahlDE(v, 2));
const stdV = v => `<span style="color:${v < 0 ? "var(--rot)" : v > 0 ? "var(--gruen)" : "inherit"}">${v > 0 ? "+" : ""}${zahlDE(v || 0, 2)}</span>`;
const PMONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const monatName = m => `${PMONATE[+m.slice(5, 7) - 1]} ${m.slice(0, 4)}`;
const monatPlus = (m, n) => { const d = new Date(+m.slice(0, 4), +m.slice(5, 7) - 1 + n, 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; };
const isoTag = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const montagVon = iso => { const d = new Date(iso + "T12:00"); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); return isoTag(d); };
const tagPlus = (iso, n) => { const d = new Date(iso + "T12:00"); d.setDate(d.getDate() + n); return isoTag(d); };

// ---------------------------------------------------------------------
//  Rechte im Browser (der Server prüft zusätzlich jede Anfrage)
// ---------------------------------------------------------------------
const darf = (bereich, stufe = 1) => !ICH || ICH.rechte.inhaber || (ICH.rechte.bereiche[bereich] || 0) >= stufe;
const nurWerkstatt = () => ICH && !ICH.rechte.inhaber && ICH.rechte.auftrag_reiter === "werkstatt";
const ROUTE_BEREICH = {start: "start", statistik: "start", kunde: "kunden", kunden: "kunden", briefe: "kunden", auftraege: "auftraege",
  auftrag: "auftraege", position: "auftraege", beleg: "auftraege", belege: "auftraege", op: "op", lieferanten: "lieferanten",
  lieferant: "lieferanten", zahlungen: "lieferanten", zahlung: "lieferanten", material: "material", mat: "material",
  kalender: "kalender", personal: "personal", einstellungen: "einstellungen", vorgaben: "einstellungen", montage: "auftraege", unterschrift: "auftraege", bautagebuch: "auftraege", leitstand: "auftraege", projekte: "auftraege", projekt: "auftraege", arbeitsschutz: "arbeitsschutz"};
function startseiteFuer() {
  if (darf("start")) return "#/start";
  if (darf("auftraege")) return "#/auftraege";
  for (const [b, h] of [["kunden", "#/kunden"], ["kalender", "#/kalender"], ["material", "#/material/holzwerkstoffe"], ["personal", "#/personal"], ["arbeitsschutz", "#/arbeitsschutz"]])
    if (darf(b)) return h;
  return "#/meine";
}

// ---------------------------------------------------------------------
//  Anmeldung
// ---------------------------------------------------------------------
function anmeldeSeite(status) {
  const einrichten = !status.eingerichtet;
  document.body.classList.add("anmelde-body");
  document.body.innerHTML = `
    <div class="anm-box">
      <div class="anm-marke"><img src="jahresring.svg" alt=""><div><b>Jahresring</b>${status.firma ? `<small>${esc(status.firma)}</small>` : ""}</div></div>
      ${einrichten ? `<h2>Ersten Zugang anlegen</h2>
        <div id="anmFund">${status.uebernahme ? `<p class="hinweis anm-schon">Wurde bisher schon mit Jahresring gearbeitet? Dann keinen neuen Zugang anlegen, sondern die <a href="#" id="anmUebOben">Daten vom bisherigen PC übernehmen</a>.</p>` : ""}</div>
        <p class="hinweis">Zuerst den Inhaber-Zugang anlegen. Er darf alles, auch weitere Benutzer und Rechte verwalten. Angemeldet wird sich danach immer mit Benutzername und Passwort.</p>`
        : `<h2>Anmelden</h2>`}
      <form id="anmForm" autocomplete="on">
        ${einrichten ? `<label>Firmenname<input name="firma" value="${esc(status.firma || "")}" autocomplete="organization" placeholder="wie im Briefkopf"></label>` : ""}
        ${einrichten ? `<label>Name<input name="name" value="${esc(status.firma_inhaber || "")}" autocomplete="name" required></label>` : ""}
        <label>Benutzername<input name="login" autocomplete="username" autocapitalize="none" required></label>
        <label>Passwort${einrichten ? " <small>(mindestens 8 Zeichen)</small>" : ""}<input name="passwort" type="password" autocomplete="${einrichten ? "new-password" : "current-password"}" required></label>
        ${einrichten ? `<label>Passwort wiederholen<input name="passwort2" type="password" autocomplete="new-password" required></label>` : ""}
        <button class="btn prim" type="submit">${einrichten ? "Zugang anlegen und anmelden" : "Anmelden"}</button>
        <div id="anmFehler" class="anm-fehler"></div>
      </form>
      ${!einrichten ? `<p style="margin-top:18px"><a href="#" id="anmVergessen">Passwort vergessen?</a></p>` : ""}
      ${einrichten && status.uebernahme ? `<div class="anm-oder"><span>oder</span></div>
        <button class="btn" type="button" id="anmUeb">Daten vom bisherigen PC übernehmen …</button>
        <p class="hinweis" style="margin:8px 0 0">Für den Umzug auf einen neuen PC und für die Wiederherstellung aus einer Sicherung. Es gelten danach die bisherigen Benutzer und Passwörter.</p>` : ""}
    </div>`;
  const f = $("#anmForm");
  if ($("#anmVergessen")) $("#anmVergessen").onclick = e => { e.preventDefault(); passwortVergessen($(".anm-box"), f.login.value, () => anmeldeSeite(status)); };
  if ($("#anmUeb")) {
    let fund = null;
    $("#anmUeb").onclick = () => datenUebernahme(status, fund);
    $("#anmUebOben").onclick = e => { e.preventDefault(); datenUebernahme(status, fund); };
    // schon beim Öffnen nachsehen, ob der bisherige Bestand irgendwo bereitliegt (USB-Stick, Desktop, zu tief kopierter Ordner)
    fetch("/api/anmeldung/uebernahme").then(r => r.ok ? r.json() : null).then(j => {
      const k = j && (j.kandidaten || []).find(x => x.art === "ordner");
      if (!k || !$("#anmFund")) return;
      fund = j;
      $("#anmFund").innerHTML = `<div class="anm-fund"><b>Bisheriger Datenbestand gefunden${k.firma ? ": " + esc(k.firma) : ""}</b>
        <span class="ub-pfad">${esc(k.pfad)}</span><span class="hinweis">Wurde bisher schon mit Jahresring gearbeitet, keinen neuen Zugang anlegen, sondern diesen Bestand übernehmen.</span>
        <button class="btn prim" type="button" id="anmFundKnopf">Diesen Bestand übernehmen …</button></div>`;
      $("#anmFundKnopf").onclick = () => datenUebernahme(status, fund, k);
    }).catch(() => {});
  }
  f.login.focus();
  if (!einrichten && f.login.value === "") setTimeout(() => f.login.focus(), 50);
  f.onsubmit = async e => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(f));
    if (einrichten && d.passwort !== d.passwort2) { $("#anmFehler").textContent = "Die beiden Passwörter sind nicht gleich."; return; }
    try {
      const r = await fetch("/api/anmeldung/" + (einrichten ? "einrichten" : "anmelden"), {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(d)});
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.fehler || r.statusText);
      location.reload();
    } catch (x) { $("#anmFehler").textContent = x.message; f.passwort.select(); }
  };
}
// Seite „Ersten Zugang anlegen“: statt eines neuen Zugangs den Datenbestand vom bisherigen PC einspielen (Umzug auf einen
// neuen PC, Wiederherstellung aus einer Sicherung). Geht nur direkt am PC und nur, solange hier noch nichts erfasst ist.
function datenUebernahme(status, vorab = null, direkt = null) {
  const box = $(".anm-box");
  box.classList.add("anm-breit");
  const ruf = async body => {
    const r = await fetch("/api/anmeldung/uebernahme", body ? {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { const x = new Error(j.fehler || r.statusText); x.status = r.status; throw x; }
    return j;
  };
  const zeit = s => s ? datum(s) + (s.length > 10 ? `, ${s.slice(11, 16)} Uhr` : "") : "";
  const mz = (n, ein, mehr) => `${n} ${n === 1 ? ein : mehr}`;
  const titel = k => k.art === "ordner" ? (k.firma || "Datenbestand") : k.art === "sicherung" ? "Vollständige Sicherung" : "Datenbanksicherung (ohne Dateien)";
  const angaben = k => [k.art === "ordner" ? `Stand ${zeit(k.stand)}` : `vom ${zeit(k.stand)}`, k.art !== "ordner" && k.firma ? k.firma : "",
    k.benutzer ? `${k.benutzer} Benutzer` : "", k.benutzer ? mz(k.kunden, "Kunde", "Kunden") : "", k.benutzer ? mz(k.belege, "Beleg", "Belege") : "",
    k.groesse ? groesse(k.groesse) : "", k.rechner ? `PC ${k.rechner}` : "", k.version ? `Version ${k.version}` : "",
    k.verschluesselt ? "verschlüsselt" : ""].filter(Boolean).join(" · ");
  const karte = (k, knopf = "") => `<div class="ub-karte"><div><b>${esc(titel(k))}</b><span class="ub-pfad">${esc(k.pfad)}</span>
    <span class="hinweis">${esc(angaben(k))}</span></div>${knopf}</div>`;
  let funde = vorab ? vorab.kandidaten : null, dialog = !!(vorab && vorab.dialog), pfadEingabe = "";

  const auswahl = (meldung = "") => {
    box.innerHTML = `<h2>Daten vom bisherigen PC übernehmen</h2>
      <p class="hinweis">Auf diesem PC ist noch nichts erfasst. Hier lässt sich der bisherige Datenbestand einspielen: der Ordner „daten“ aus dem Jahresring-Ordner des bisherigen PCs (zum Beispiel auf einem USB-Stick) oder eine vollständige Sicherung (Datei Sicherung_….zip).</p>
      <div class="ub-titel">Gefundene Datenbestände <a href="#" id="ubSuchen">erneut suchen</a></div>
      <div id="ubListe">${funde === null ? `<p class="hinweis">Suche auf diesem PC und den angeschlossenen Datenträgern …</p>`
        : funde.length ? funde.map((k, i) => karte(k, `<button class="btn prim" type="button" data-i="${i}">Übernehmen …</button>`)).join("")
        : `<p class="hinweis">Nichts gefunden. Den Datenträger anstecken und „erneut suchen“ wählen oder den Ort unten angeben.</p>`}</div>
      <div class="ub-titel">Anderer Ort</div>
      <form id="ubForm" autocomplete="off">
        <label>Ordner „daten“ oder Sicherungsdatei<input name="pfad" value="${esc(pfadEingabe)}" placeholder="z. B. E:\\daten oder E:\\Sicherung_2026-11-17_18-00-00.zip" spellcheck="false" autocapitalize="none"></label>
        <div class="ub-knoepfe">${dialog ? `<button class="btn" type="button" id="ubOrdner">Ordner wählen …</button><button class="btn" type="button" id="ubDatei">Sicherungsdatei wählen …</button>` : ""}
          <button class="btn prim" type="submit">Prüfen</button></div>
      </form>
      <div class="anm-fehler" id="ubFehler">${esc(meldung)}</div>
      <p style="margin-top:6px"><a href="#" id="ubZu">Zurück: neuen Zugang anlegen</a></p>`;
    const f = $("#ubForm", box);
    $$("#ubListe button", box).forEach(b => b.onclick = () => bestaetigen(funde[+b.dataset.i]));
    $("#ubSuchen", box).onclick = e => { e.preventDefault(); funde = null; pfadEingabe = f.pfad.value; auswahl(); suchen(); };
    $("#ubZu", box).onclick = e => { e.preventDefault(); box.classList.remove("anm-breit"); anmeldeSeite(status); };
    const pruefen = async () => {
      pfadEingabe = f.pfad.value.trim();
      if (!pfadEingabe) { $("#ubFehler", box).textContent = "Bitte den Ordner oder die Sicherungsdatei angeben."; return; }
      try { bestaetigen(await ruf({pfad: pfadEingabe, nur_pruefen: true})); }
      catch (x) { $("#ubFehler", box).textContent = x.message; }
    };
    f.onsubmit = e => { e.preventDefault(); pruefen(); };
    for (const [id, art] of [["#ubOrdner", "ordner"], ["#ubDatei", "datei"]]) {
      if ($(id, box)) $(id, box).onclick = async () => {
        $("#ubFehler", box).textContent = "";
        try {
          const j = await ruf({waehlen: art});
          if (j.pfad) { f.pfad.value = j.pfad; pruefen(); }
          else if (j.dialog === false) $("#ubFehler", box).textContent = "Das Auswahlfenster ließ sich nicht öffnen. Bitte den Pfad eintippen oder im Explorer kopieren (Rechtsklick › „Als Pfad kopieren“).";
        } catch (x) { $("#ubFehler", box).textContent = x.message; }
      };
    }
  };
  const suchen = async () => {
    try { const j = await ruf(); funde = j.kandidaten || []; dialog = !!j.dialog; }
    catch (x) { funde = []; if ($("#ubListe", box)) return auswahl(x.message); }
    if ($("#ubListe", box)) auswahl();
  };

  const bestaetigen = (k, meldung = "") => {
    box.innerHTML = `<h2>Diesen Datenbestand übernehmen?</h2>
      ${karte(k)}
      ${k.verschluesselt ? `<label>Sicherungskennwort<input id="ubKw" type="password" autocomplete="off"></label>` : ""}
      <p class="hinweis">Der Bestand wird auf diesen PC kopiert; ${k.art === "ordner" ? "der Ordner" : "die Datei"} selbst bleibt unverändert. Je nach Umfang dauert das einige Minuten. Angemeldet wird sich danach mit den bisherigen Benutzernamen und Passwörtern.</p>
      ${k.art === "datenbank" ? `<p class="hinweis"><b>Nur die Datenbank:</b> Anhänge, archivierte Belege, Eingangsrechnungen und Bilder sind in dieser Sicherung nicht enthalten. Liegt der Ordner „daten“ vom bisherigen PC oder eine vollständige Sicherung vor, besser diese übernehmen.</p>` : ""}
      <div class="ub-knoepfe"><button class="btn" type="button" id="ubAb">Abbrechen</button><button class="btn prim" type="button" id="ubLos">Jetzt übernehmen</button></div>
      <div class="anm-fehler" id="ubFehler2">${esc(meldung)}</div>`;
    if ($("#ubKw", box)) $("#ubKw", box).focus();
    $("#ubAb", box).onclick = () => auswahl();
    $("#ubLos", box).onclick = async () => {
      const kennwort = $("#ubKw", box) ? $("#ubKw", box).value : "";
      if (k.verschluesselt && !kennwort) { $("#ubFehler2", box).textContent = "Bitte das Sicherungskennwort eingeben."; return; }
      box.innerHTML = `<h2>Die Daten werden übernommen …</h2>
        <p class="hinweis">Bitte dieses Fenster geöffnet lassen und den Datenträger nicht abziehen.</p>
        <div class="ub-balken"><i id="ubBalken"></i></div><p id="ubStand" class="hinweis">Der Datenbestand wird geprüft …</p>`;
      const uhr = setInterval(async () => {
        try {
          const st = await (await fetch("/api/anmeldung/uebernahme/stand")).json();
          if (!st.laeuft || !$("#ubStand", box)) return;
          $("#ubStand", box).textContent = st.schritt + (st.von ? ` … ${st.dateien} von ${st.von} Dateien (${groesse(st.bytes)} von ${groesse(st.von_bytes)})` : " …");
          $("#ubBalken", box).style.width = (st.von_bytes ? Math.round(st.bytes / st.von_bytes * 100) : 0) + "%";
        } catch (x) { /* nur Anzeige */ }
      }, 700);
      try { fertig(await ruf({pfad: k.pfad, kennwort})); }
      catch (x) { bestaetigen(k, x.message); }
      finally { clearInterval(uhr); }
    };
  };

  const fertig = r => {
    box.innerHTML = `<h2>Die Daten sind übernommen</h2>
      <p>${r.firma ? `<b>${esc(r.firma)}</b>: ` : ""}${r.benutzer} Benutzer, ${mz(r.kunden, "Kunde", "Kunden")}, ${mz(r.belege, "Beleg", "Belege")}${r.dateien ? `, ${mz(r.dateien, "Datei", "Dateien")} kopiert` : ""}.</p>
      <p>Angemeldet wird sich jetzt mit den bisherigen Benutzernamen und Passwörtern.</p>
      ${(r.hinweise || []).length > 1 ? `<div class="ub-titel">Noch zu beachten</div><ol class="ub-hinweise">${r.hinweise.map(h => `<li>${esc(h)}</li>`).join("")}</ol>`
        : (r.hinweise || []).length ? `<p class="ub-hinweise">${esc(r.hinweise[0])}</p>` : ""}
      <button class="btn prim" type="button" id="ubFertig">Zur Anmeldung</button>`;
    $("#ubFertig", box).onclick = () => location.reload();
    $("#ubFertig", box).focus();
  };

  if (direkt) bestaetigen(direkt); else auswahl();
  if (funde === null) suchen();
}
// „Passwort vergessen?“: Code per E-Mail anfordern, dann mit Code (oder als Inhaber mit dem Notfallschlüssel) neu setzen.
// Wird auch von der Stempeluhr benutzt (dort mit eigener Basisadresse).
function passwortVergessen(box, login = "", zurueck, basis = "") {
  const post = async (pfad, body) => {
    const r = await fetch(basis + "/api/anmeldung/" + pfad, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.fehler || r.statusText);
    return j;
  };
  const schritt1 = (meldung = "") => {
    box.innerHTML = `<h2>Passwort vergessen</h2>
      <p class="hinweis">Benutzername eingeben. Jahresring schickt einen Code an die E-Mail-Adresse, die für diesen Zugang hinterlegt ist (beim Inhaber notfalls an die Absenderadresse des Betriebs).</p>
      <form id="pvF1"><label>Benutzername<input name="login" value="${esc(login)}" autocomplete="username" autocapitalize="none" required></label>
        <button class="btn prim" type="submit">Code per E-Mail senden</button><div class="anm-fehler" id="pvFe">${esc(meldung)}</div></form>
      <p style="margin-top:14px;display:flex;gap:16px;flex-wrap:wrap"><a href="#" id="pvHabe">Ich habe schon einen Code</a><a href="#" id="pvNot">Notfallschlüssel (Inhaber)</a><a href="#" id="pvZu">Zurück zur Anmeldung</a></p>`;
    const f = $("#pvF1", box); f.login.focus();
    f.onsubmit = async e => {
      e.preventDefault(); login = f.login.value.trim();
      const knopf = $("button", f); knopf.disabled = true; knopf.textContent = "wird gesendet …";
      try { const j = await post("vergessen", {login}); schritt2(j.hinweis, false); }
      catch (x) { $("#pvFe", box).textContent = x.message; knopf.disabled = false; knopf.textContent = "Code per E-Mail senden"; }
    };
    $("#pvHabe", box).onclick = e => { e.preventDefault(); login = f.login.value.trim(); schritt2("", false); };
    $("#pvNot", box).onclick = e => { e.preventDefault(); login = f.login.value.trim(); schritt2("", true); };
    $("#pvZu", box).onclick = e => { e.preventDefault(); zurueck(); };
  };
  const schritt2 = (hinweis, notfall) => {
    box.innerHTML = `<h2>${notfall ? "Mit Notfallschlüssel" : "Neues Passwort setzen"}</h2>
      ${hinweis ? `<p class="hinweis">${esc(hinweis)} Auch im Spam-Ordner nachsehen.</p>` : ""}
      ${notfall ? `<p class="hinweis">Der Notfallschlüssel ist der ausgedruckte Schlüssel aus Einstellungen › Benutzer (nur Inhaber). Er gilt einmal; danach unter Einstellungen einen neuen erzeugen.</p>` : ""}
      <form id="pvF2" autocomplete="off"><label>Benutzername<input name="login" value="${esc(login)}" autocapitalize="none" required></label>
        <label>${notfall ? "Notfallschlüssel" : "Code aus der E-Mail"}<input name="code" ${notfall ? `placeholder="XXXX-XXXX-XXXX-XXXX"` : `inputmode="numeric" placeholder="6 Ziffern"`} autocomplete="one-time-code" required></label>
        <label>Neues Passwort<input name="neu" type="password" autocomplete="new-password" required></label>
        <label>Neues Passwort wiederholen<input name="neu2" type="password" autocomplete="new-password" required></label>
        <button class="btn prim" type="submit">Passwort setzen und anmelden</button><div class="anm-fehler" id="pvFe2"></div></form>
      <p style="margin-top:14px;display:flex;gap:16px;flex-wrap:wrap">${notfall ? "" : `<a href="#" id="pvNeu">Neuen Code anfordern</a>`}<a href="#" id="pvZu2">Zurück zur Anmeldung</a></p>`;
    const f = $("#pvF2", box); (login ? f.code : f.login).focus();
    f.onsubmit = async e => {
      e.preventDefault();
      if (f.neu.value !== f.neu2.value) { $("#pvFe2", box).textContent = "Die beiden Passwörter sind nicht gleich."; return; }
      try { await post("zuruecksetzen", {login: f.login.value.trim(), code: f.code.value.trim(), neu: f.neu.value}); location.reload(); }
      catch (x) { $("#pvFe2", box).textContent = x.message; }
    };
    if ($("#pvNeu", box)) $("#pvNeu", box).onclick = e => { e.preventDefault(); login = f.login.value.trim(); schritt1(); };
    $("#pvZu2", box).onclick = e => { e.preventDefault(); zurueck(); };
  };
  schritt1();
}
async function abmelden() {
  await fetch("/api/anmeldung/abmelden", {method: "POST"});
  location.hash = "";
  location.reload();
}
async function passwortAendern() {
  const d = await modal("Eigener Zugang", `<div class="form" style="grid-template-columns:1fr">
    ${zeile("E-Mail", `<input name="email" type="email" value="${esc(ICH.email || "")}" placeholder="für „Passwort vergessen?“">`)}
    ${zeile("Bisheriges Passwort", `<input type="password" name="alt" autocomplete="current-password" placeholder="zum Ändern von E-Mail oder Passwort">`)}
    ${zeile("Neues Passwort", `<input type="password" name="neu" autocomplete="new-password">`)}
    ${zeile("Wiederholen", `<input type="password" name="neu2" autocomplete="new-password">`)}</div>
    <p class="hinweis">An die E-Mail-Adresse schickt Jahresring bei „Passwort vergessen?“ einen Code – deshalb lässt sie sich nur mit dem bisherigen Passwort ändern. Nach einer Passwortänderung werden die anderen Geräte abgemeldet.</p>`, "Speichern");
  if (!d) return;
  if ((d.email || "") !== (ICH.email || "")) {
    if (!d.alt) return toast("Zum Ändern der E-Mail-Adresse bitte das bisherige Passwort eingeben.", true);
    try { const r = await fetch("/api/anmeldung/email", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({email: d.email, passwort: d.alt})});
      const j = await r.json(); if (!r.ok) throw new Error(j.fehler); ICH.email = j.email; toast("E-Mail gespeichert"); }
    catch (e) { return toast(e.message, true); }
  }
  if (!d.neu) return;
  if (d.neu !== d.neu2) return toast("Die neuen Passwörter sind nicht gleich.", true);
  try {
    const r = await fetch("/api/anmeldung/passwort", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(d)});
    const j = await r.json(); if (!r.ok) throw new Error(j.fehler);
    toast("Passwort geändert");
  } catch (e) { toast(e.message, true); }
}

// ---------------------------------------------------------------------
//  Einstellungen › Benutzer & Netzwerk
// ---------------------------------------------------------------------
async function benutzerEinstellungen(z) {
  const [liste, meta, mas] = await Promise.all([api("benutzer"), api("benutzer/meta"), api("mitarbeiter?status=alle").catch(() => [])]);
  const netz = E._netz || {};
  const rolleText = Object.fromEntries(meta.rollen.map(r => [r.id, r]));
  z.innerHTML = `
    <div class="titel"><h2>Benutzer und Rechte</h2><div class="rechts"><button class="btn prim" id="bnNeu">+ Benutzer</button></div></div>
    <table class="liste"><tr><th>Benutzer</th><th>Name</th><th>Rolle</th><th>Mitarbeiter</th><th>Zuletzt angemeldet</th><th>Geräte</th><th></th></tr>
      ${liste.map(b => `<tr class="klick ${b.aktiv ? "" : "inaktiv"}" data-bn="${b.id}"><td><b>${esc(b.login)}</b>${b.id === ICH.id ? ` <span class="tag">angemeldet</span>` : ""}</td><td>${esc(b.name)}</td>
        <td>${esc(b.rolle_name)}${b.aktiv ? "" : ` <span class="tag">gesperrt</span>`}</td><td>${esc(b.mitarbeiter || "")}</td>
        <td>${b.letzter_login ? datum(b.letzter_login) + " " + b.letzter_login.slice(11, 16) : "<span class=hinweis>noch nie</span>"}</td>
        <td>${b.sitzungen || ""}</td><td class="r"><a href="#" data-bn="${b.id}">bearbeiten</a></td></tr>`).join("")}
    </table>
    ${ICH.rolle === "inhaber" ? `<div class="kachel" style="margin-top:14px">
      <b>Passwort vergessen</b>
      <p style="margin:6px 0">Auf der Anmeldeseite (auch auf der Stempeluhr) gibt es „Passwort vergessen?“. Jahresring schickt dann einen 6-stelligen Code an die E-Mail-Adresse, die am Benutzer selbst hinterlegt ist (Feld „E-Mail“; beim Inhaber ersatzweise die Absenderadresse des Betriebs). Die Adresse aus dem Mitarbeiterstamm zählt dafür nicht; wer keine eigene Adresse hat, lässt das Passwort vom Inhaber neu setzen. Der Code gilt 15 Minuten und einmal; danach sind alle Geräte des Benutzers abgemeldet, und er bekommt eine Hinweismail.
      Falls der Mailversand einmal nicht geht, hilft dem Inhaber ein <b>Notfallschlüssel</b> zum Ausdrucken: ${ICH.notfall_erstellt ? `erzeugt am ${datum(ICH.notfall_erstellt)}` : `<span style="color:var(--rot)">noch keiner erzeugt</span>`}.</p>
      <button class="btn" id="bnNotfall">${ICH.notfall_erstellt ? "Neuen Notfallschlüssel erzeugen" : "Notfallschlüssel erzeugen"}</button></div>` : ""}
    <div class="kachel" style="margin-top:14px">
      <b>Die Rollen</b>
      <table class="liste" style="margin-top:6px">${meta.rollen.filter(r => r.id !== "eigen").map(r => `<tr><td style="width:130px"><b>${esc(r.name)}</b></td><td>${esc(r.text)}</td></tr>`).join("")}
        <tr><td><b>Eigene Rechte</b></td><td>je Bereich „kein Zugriff“, „nur ansehen“ (Werkstattarbeiten wie Restelager, Scan, Leitstand und Bautagebuch bleiben möglich) oder „bearbeiten“, dazu Preise ein/aus und Aufträge nur mit Werkstatt-Reiter</td></tr></table>
    </div>

    ${ICH.rolle === "inhaber" ? `<div class="kachel" style="margin-top:14px">
      <b>Anmeldung und besondere Daten</b>
      <div class="form" style="grid-template-columns:1fr;margin-top:8px">
        ${zeile("Anmeldung gilt", `<div style="display:flex;gap:6px 10px;align-items:center;flex-wrap:wrap"><input id="bnTageB" class="zahl" style="width:64px" value="${esc(E.sitzung_tage_buero ?? 30)}"> Tage ohne Benutzung (Inhaber, Büro, Werkstatt)
          <span style="margin-left:14px"></span><input id="bnTageM" class="zahl" style="width:64px" value="${esc(E.sitzung_tage_mitarbeiter ?? 120)}"> Tage (Rolle Mitarbeiter, Stempeluhr am Handy)</div>`)}
        ${zeile("Vorsorge", `<div class="spalte"><label><input type="checkbox" id="bnVorsorge" ${E.vorsorge_nur_inhaber ? "checked" : ""}> Vorsorgekartei und Expositionsverzeichnis sieht nur der Inhaber</label>
          <span class="hinweis">Ohne Haken sieht sie auch, wer im Arbeitsschutz „bearbeiten“ darf (Rolle Büro). Das Verbandbuch liest ohnehin nur der Inhaber.</span></div>`)}
      </div></div>` : ""}

    <div class="titel" style="margin-top:22px"><h2>Netzwerk und Handys</h2></div>
    <div class="form" style="grid-template-columns:1fr">
      ${zeile("Im Netzwerk", `<label style="padding-top:5px"><input type="checkbox" id="nzAn" ${E.netzwerk ? "checked" : ""}> Programm im eigenen Netzwerk erreichbar machen (für Handys im WLAN und weitere PCs; der PC selbst kann per Kabel oder WLAN angeschlossen sein)</label>`)}
      ${zeile("Adresse", `<div style="padding-top:5px;line-height:1.6">${netz.aktiv
        ? `Stempeluhr fürs Handy: <b style="font-size:1.1em">http://${esc(netz.ip)}:${netz.port}/stempel</b><br>Büro von einem anderen PC: http://${esc(netz.ip)}:${netz.port}`
        : E.netzwerk ? `<span style="color:var(--rot)">Eingeschaltet – wirkt nach dem nächsten Neustart des Programms.</span> Danach steht hier die Adresse fürs Handy.`
        : `<span class="hinweis">ausgeschaltet – das Programm ist nur hier am PC erreichbar.</span>`}</div>`)}
      ${netz.aktiv && (E.https || "aus") === "aus" ? zeile("", `<div class="kachel" style="border-left:4px solid var(--rot);margin:0"><b>Die Verbindung im Netzwerk ist unverschlüsselt.</b> Anmeldung und Daten gehen im Klartext durchs Netz; wer im selben Netzwerk mitliest, kann sie sehen. Empfohlen: unten „https zusätzlich“ wählen, die Geräte einrichten und danach auf „nur https“ stellen.</div>`) : ""}
      ${zeile("Weitere Adressen", `<div class="spalte"><input id="nzHosts" value="${esc(E.netz_adressen || "")}" placeholder="z. B. buero.meinbetrieb.de" style="max-width:420px">
        <span class="hinweis" style="margin-top:4px">Nur nötig, wenn das Programm im eigenen Netz unter einem eigenen Namen mit Punkt aufgerufen wird. Ohne Eintrag gelten: localhost, die IP-Adresse, der Name dieses PCs und Namen wie „pc.fritz.box“ oder „pc.local“. Mehrere durch Komma trennen.</span></div>`)}
      ${zeile("Verschlüsselung (https)", `<div class="spalte"><select id="nzHttps" style="max-width:420px" ${E.netzwerk ? "" : "disabled"}>
          <option value="aus" ${(E.https || "aus") === "aus" ? "selected" : ""}>aus – nur http (unverschlüsselt im Netzwerk)</option>
          <option value="zusaetzlich" ${E.https === "zusaetzlich" ? "selected" : ""}>https zusätzlich – beide Adressen funktionieren (zum Einrichten der Geräte)</option>
          <option value="nur" ${E.https === "nur" ? "selected" : ""}>nur https – andere Geräte werden auf die verschlüsselte Adresse umgeleitet</option></select>
        ${(E._https || {}).aktiv ? `<span style="margin-top:6px;line-height:1.6">Verschlüsselte Adresse: <b>https://${esc(netz.ip)}:${E._https.port}</b> · Stempeluhr: <b>https://${esc(netz.ip)}:${E._https.stempel_port || E._https.port}/stempel</b><br>
          <span class="hinweis">Die Stempeluhr hat eine eigene Adresse (anderer Port), damit sie sich auf demselben Gerät zusätzlich zur Büro-App als eigene App installieren lässt.</span><br>
          Geräte einrichten: auf dem Tablet/Handy <b>http://${esc(netz.ip)}:${netz.port}/zertifikat</b> öffnen und der Anleitung folgen (einmalig je Gerät).<br>
          <span class="hinweis">Fingerabdruck des Zertifikats (SHA-256): <code style="word-break:break-all">${esc(E._https.fingerabdruck || "")}</code></span><br>
          <span class="hinweis">Das Zertifikat gilt für: ${(E._https.namen || []).map(esc).join(", ") || "–"}${E._https.eigen ? " (eigenes Zertifikat des Betriebs)" : ""}. Unter einer anderen Adresse zeigt der Browser „Nicht sicher“.</span><br>
          ${E._https.eigen ? "" : `An diesem PC: ${E._https.am_pc === "vorhanden" || E._https.am_pc === "eingetragen" ? `<b style="color:var(--gruen)">Zertifikat ist als vertrauenswürdig eingetragen</b> – Browser ggf. einmal schließen und neu öffnen.`
            : E._https.am_pc ? `<b style="color:var(--rot)">Zertifikat ist in Windows noch nicht als vertrauenswürdig eingetragen</b> – der Browser zeigt deshalb „Nicht sicher“.` : ""}
          <span style="margin-top:4px"><button class="btn" id="nzZertPc">An diesem PC einrichten</button> <button class="btn" id="nzZertNeu">Zertifikat neu ausstellen</button></span>`}</span>`
          : (E.https && E.https !== "aus") ? `<span style="margin-top:6px;color:var(--rot)">${esc((E._https || {}).meldung || "Eingeschaltet – wirkt nach dem nächsten Neustart des Programms.")}</span>` : ""}
        <span class="hinweis" style="margin-top:6px">Verschlüsselt Anmeldung und Daten im Netzwerk und ermöglicht die Installation als App. Das Zertifikat wird auf jedem Gerät einmal eingerichtet und gilt nur für diesen PC im eigenen Netz. Wirkt nach einem Neustart des Programms.</span></div>`)}
      ${zeile("", `<p class="hinweis" style="margin:0">Kommt ein Gerät nicht durch: im Programmordner <b>Handy-Freigabe.bat</b> doppelklicken (richtet die Firewall ein, zeigt Netzwerkprofil und Adressen). Android: Chrome braucht die Berechtigung „Geräte in der Nähe“; iPhone: unter Datenschutz &amp; Sicherheit › Lokales Netzwerk den Browser erlauben. Handys müssen im normalen WLAN des Routers sein, nicht im Gastzugang. Der PC sollte im Router eine feste IP-Adresse haben und unter Windows als „Privates Netzwerk“ eingestuft sein (Windows-Einstellungen › Netzwerk und Internet; ein neu angeschlossenes Kabelnetz gilt dort oft zunächst als öffentlich). Von außerhalb des eigenen Netzes ist das Programm nicht erreichbar; die Stempeluhr puffert Buchungen und überträgt sie, sobald das Handy wieder im WLAN ist.</p>`)}
    </div>

`;
  $$("[data-bn]", z).forEach(el => el.onclick = e => { e.preventDefault(); e.stopPropagation(); benutzerBearbeiten(liste.find(b => b.id === +el.dataset.bn), meta, mas, () => benutzerEinstellungen(z)); });
  $("#bnNeu").onclick = () => benutzerBearbeiten(null, meta, mas, () => benutzerEinstellungen(z));
  if ($("#bnNotfall", z)) $("#bnNotfall", z).onclick = async () => {
    const d = await modal("Notfallschlüssel erzeugen", `<p>Mit dem Notfallschlüssel lässt sich das Inhaber-Passwort auch ohne E-Mail neu setzen (Anmeldeseite › Passwort vergessen? › Notfallschlüssel). Er wird nur jetzt einmal angezeigt, gilt einmal, und ein früherer Schlüssel wird ungültig. Ausdrucken und an einem sicheren Ort aufbewahren, nicht am PC.</p>
      <div class="form" style="grid-template-columns:1fr">${zeile("Eigenes Passwort", `<input type="password" name="passwort" autocomplete="current-password">`)}</div>`, "Erzeugen");
    if (!d) return;
    try {
      const r = await fetch("/api/anmeldung/notfallschluessel", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(d)});
      const j = await r.json(); if (!r.ok) throw new Error(j.fehler);
      ICH.notfall_erstellt = new Date().toISOString().slice(0, 19);
      await modal("Notfallschlüssel", `<p>Notfallschlüssel für <b>${esc(ICH.login)}</b> (${esc(E.firma || "")}), erzeugt am ${datum(heute())}:</p>
        <p style="font:600 26px/1.4 ui-monospace,Consolas,monospace;letter-spacing:2px;text-align:center;padding:14px;border:2px dashed var(--linie);border-radius:8px">${esc(j.schluessel)}</p>
        <p class="hinweis">Jetzt ausdrucken oder abschreiben. Er wird nicht noch einmal angezeigt.</p>`, "Fertig", hg => {
          const b = document.createElement("button"); b.className = "btn"; b.type = "button"; b.textContent = "Drucken";
          b.onclick = () => { const w = window.open("", "_blank"); w.document.write(`<title>Notfallschlüssel Jahresring</title><body style="font:16px system-ui;padding:40px"><h2>Jahresring – Notfallschlüssel</h2><p>Zugang: <b>${esc(ICH.login)}</b><br>Erzeugt: ${datum(heute())}</p><p style="font:600 30px ui-monospace,Consolas,monospace;letter-spacing:3px;border:2px dashed #999;padding:16px;display:inline-block">${esc(j.schluessel)}</p><p>Verwendung: Anmeldeseite › Passwort vergessen? › Notfallschlüssel (Inhaber). Gilt einmal.</p></body>`); w.document.close(); w.print(); };
          $(".modal .knoepfe", hg).prepend(b);
        });
      benutzerEinstellungen(z);
    } catch (e) { toast(e.message, true); }
  };
  for (const [id, schluessel] of [["bnTageB", "sitzung_tage_buero"], ["bnTageM", "sitzung_tage_mitarbeiter"]]) if ($("#" + id, z)) $("#" + id, z).onchange = async e => {
    const n = Math.round(zahlEin(e.target.value));
    if (!(n >= 1 && n <= 365)) { toast("Bitte 1 bis 365 Tage angeben.", true); e.target.value = E[schluessel]; return; }
    E = await api("einstellungen", {method: "PUT", body: {[schluessel]: n}}); e.target.value = n; toast("Gespeichert – gilt für neue Anmeldungen");
  };
  if ($("#bnVorsorge", z)) $("#bnVorsorge", z).onchange = async e => { E = await api("einstellungen", {method: "PUT", body: {vorsorge_nur_inhaber: e.target.checked}}); toast("Gespeichert"); };
  $("#nzAn").onchange = async e => {
    if (e.target.checked && !await frage("Programm im Netzwerk erreichbar machen?\n\nDann können sich Handys und andere PCs im selben Netzwerk (WLAN oder Kabel) anmelden. Jeder braucht einen eigenen Benutzer. Dazu wird die verschlüsselte Adresse (https) eingeschaltet; die Geräte werden einmal eingerichtet. Die Änderung wirkt nach einem Neustart des Programms.", {ok: "Einschalten"})) { e.target.checked = false; return; }
    // beim Einschalten gleich die verschlüsselte Adresse dazu (http bleibt zum Einrichten der Geräte erreichbar)
    E = await api("einstellungen", {method: "PUT", body: {netzwerk: e.target.checked, ...(e.target.checked && (E.https || "aus") === "aus" ? {https: "zusaetzlich"} : {})}});
    toast("Gespeichert – bitte das Programm neu starten"); benutzerEinstellungen(z);
  };
  $("#nzHosts").onchange = async e => { E = await api("einstellungen", {method: "PUT", body: {netz_adressen: e.target.value.trim()}}); toast("Gespeichert"); };
  const zertAktion = async (body, text) => {
    try {
      const r = await api("service/zertifikat", {method: "POST", body});
      E = await api("einstellungen");
      toast(r.am_pc === "abgelehnt" ? "Windows hat das Zertifikat nicht eingetragen (Nachfrage abgelehnt?)" : r.am_pc ? text : "Erledigt", r.am_pc === "abgelehnt");
      benutzerEinstellungen(z);
    } catch (x) { toast(x.message, true); }
  };
  if ($("#nzZertPc")) $("#nzZertPc").onclick = () => zertAktion({}, "Zertifikat ist an diesem PC eingetragen – Browser bitte schließen und neu öffnen");
  if ($("#nzZertNeu")) $("#nzZertNeu").onclick = async () => {
    if (!await frage("Zertifikat neu ausstellen?\n\nEs entsteht ein neues Zertifikat mit dem heutigen PC-Namen und den heutigen Adressen. Auf allen Tablets und Handys muss das Zertifikat danach einmal neu eingerichtet werden (Seite /zertifikat); das bisherige kann dort entfernt werden.\n\nWindows fragt anschließend, ob das neue Zertifikat an diesem PC eingetragen werden soll – bitte mit „Ja“ bestätigen.", {ok: "Neu ausstellen"})) return;
    zertAktion({neu: true}, "Neues Zertifikat ausgestellt und an diesem PC eingetragen");
  };
  if ($("#nzHttps")) $("#nzHttps").onchange = async e => {
    E = await api("einstellungen", {method: "PUT", body: {https: e.target.value}});
    toast("Gespeichert – bitte das Programm neu starten"); benutzerEinstellungen(z);
  };
}

async function benutzerBearbeiten(b, meta, mas, danach) {
  const neu = !b;
  b = b || {login: "", name: "", rolle: "mitarbeiter", aktiv: 1, mitarbeiter_id: null, eigen: {}};
  const eigen = b.eigen && b.eigen.bereiche ? b.eigen : {bereiche: Object.fromEntries(meta.bereiche.map(([k]) => [k, 0])), auftrag_reiter: "alle", preise: true};
  const rechteTabelle = () => `<table class="liste" style="margin-top:4px">${meta.bereiche.filter(([k]) => k !== "einstellungen").map(([k, l]) => `<tr><td>${esc(l)}</td><td>
      <select data-rb="${k}" style="width:140px">${optsKV(Object.entries(meta.stufen), eigen.bereiche[k] || 0)}</select></td></tr>`).join("")}
      <tr><td>Aufträge</td><td><select id="bnReiter" style="width:220px">${optsKV([["alle", "alle Reiter"], ["werkstatt", "nur Reiter Werkstatt"]], eigen.auftrag_reiter)}</select></td></tr>
      <tr><td>Preise und Beträge</td><td><label><input type="checkbox" id="bnPreise" ${eigen.preise !== false ? "checked" : ""}> anzeigen</label></td></tr></table>
      <p class="hinweis" id="bnStufeHinweis" style="margin:4px 0 0">„Nur ansehen“ heißt: Stammdaten, Preise und Belege lassen sich nicht ändern. Die Arbeiten der Werkstatt bleiben damit möglich –
        bei Material: Restelager führen (Wareneingang, Bestellvermerk, Import) und Lagerbuchungen per Scan; bei Aufträgen: Leitstand, Bautagebuch, Montagebericht, Kundenunterschrift und Auftragsstatus.
        Wer auch das nicht dürfen soll, bekommt für den Bereich „kein Zugriff“. Ohne „Preise und Beträge“ sind Angebote, Rechnungen und ihre PDF gesperrt.</p>`;
  const kal = {typen: [], nur_eigene: false, extern: true, abwesenheit: true, ...((b.rechte || {}).kalender || {})};
  if (neu) kal.extern = false;
  const typNamen = (E.termin_typen || []).map(t => t.name);
  const kalenderBlock = () => `<div class="sektion" style="margin-top:6px">Kalender – was dieser Benutzer sieht</div>
      <div class="zeile voll"><label>Terminarten</label><div style="gap:4px 14px">${typNamen.map(n => `<label style="white-space:nowrap"><input type="checkbox" data-kt="${esc(n)}" ${!kal.typen.length || kal.typen.includes(n) ? "checked" : ""}> ${esc(n)}</label>`).join("")}</div></div>
      <div class="zeile voll"><label>Einschränkung</label><div class="spalte">
        <label><input type="checkbox" id="bnKalEigene" ${kal.nur_eigene ? "checked" : ""}> nur Termine, denen der oben gewählte Mitarbeiter zugeteilt ist</label>
        <label><input type="checkbox" id="bnKalExtern" ${kal.extern ? "checked" : ""}> Einträge aus dem verbundenen externen Kalender zeigen</label>
        <label><input type="checkbox" id="bnKalAbw" ${kal.abwesenheit ? "checked" : ""}> Abwesenheiten der Kollegen zeigen (ohne Grund; die eigenen immer)</label>
        <span class="hinweis">Gilt, wenn der Benutzer den Kalender überhaupt sehen darf. Sind Terminarten abgewählt oder „nur eigene“ gesetzt, entfällt auch die Auftragsplanung ohne sichtbaren Termin. Beträge sieht nur, wer Preise sehen darf.</span></div></div>`;
  const d = await modal(neu ? "Neuer Benutzer" : `Benutzer ${b.login}`, `<div class="form" style="grid-template-columns:1fr">
      ${zeile("Benutzername", `<input name="login" value="${esc(b.login)}" autocapitalize="none" placeholder="z. B. werkstatt oder max">`)}
      ${zeile("Name", `<input name="name" value="${esc(b.name)}">`)}
      ${zeile("E-Mail", `<input name="email" type="email" value="${esc(b.email || "")}" placeholder="für „Passwort vergessen?“ – nur an diese Adresse geht der Code">`)}
      ${zeile("Rolle", `<select name="rolle" id="bnRolle">${optsKV(meta.rollen.map(r => [r.id, r.name]), b.rolle)}</select>`)}
      <div id="bnRolleText" class="hinweis" style="margin:-4px 0 4px 0"></div>
      <div id="bnEigen"></div>
      <div id="bnKalender"></div>
      ${zeile("Mitarbeiter", `<select name="mitarbeiter_id">${optsKV(mas.map(m => [m.id, `${m.nummer} ${m.name}`]), b.mitarbeiter_id, "— keiner —")}</select><span class="hinweis" style="padding-top:5px">für die Stempeluhr und „Meine Zeiten“</span>`)}
      ${zeile(neu ? "Passwort / PIN" : "Neues Passwort", `<input name="passwort" type="text" autocomplete="off" placeholder="${neu ? "Rolle Mitarbeiter: mind. 6 Zeichen, sonst 8" : "leer = unverändert"}">`)}
      ${!neu ? zeile("Status", `<select name="aktiv">${optsKV([[1, "aktiv"], [0, "gesperrt (kann sich nicht anmelden)"]], b.aktiv)}</select>`) : ""}
    </div>
    ${!neu ? `<div style="display:flex;gap:8px;margin-top:8px">${b.sitzungen ? `<button class="btn" type="button" id="bnAb">Auf allen Geräten abmelden (${b.sitzungen})</button>` : ""}${b.id !== ICH.id ? `<button class="btn rot" type="button" id="bnDel">Benutzer löschen</button>` : ""}</div>` : ""}`,
    "Speichern", hg => {
      $(".modal", hg).style.width = "min(640px,96vw)";
      const rolleZeigen = () => {
        const r = meta.rollen.find(x => x.id === $("#bnRolle", hg).value);
        $("#bnRolleText", hg).textContent = r ? r.text : "";
        $("#bnEigen", hg).innerHTML = r && r.id === "eigen" ? rechteTabelle() : "";
        if (r && r.id !== "inhaber") {
          if (!$("#bnKalEigene", hg)) $("#bnKalender", hg).innerHTML = kalenderBlock();
          const lesen = () => { const an = $$("[data-kt]", hg).filter(c => c.checked).map(c => c.dataset.kt);
            kal.typen = an.length === typNamen.length ? [] : an.length ? an : ["(keine)"]; kal.nur_eigene = $("#bnKalEigene", hg).checked; kal.extern = $("#bnKalExtern", hg).checked; kal.abwesenheit = $("#bnKalAbw", hg).checked; };
          $$("#bnKalender input", hg).forEach(c => c.onchange = lesen);
        } else $("#bnKalender", hg).innerHTML = "";
        $$("[data-rb]", hg).forEach(s => s.onchange = () => eigen.bereiche[s.dataset.rb] = +s.value);
        if ($("#bnReiter", hg)) $("#bnReiter", hg).onchange = e => eigen.auftrag_reiter = e.target.value;
        if ($("#bnPreise", hg)) $("#bnPreise", hg).onchange = e => eigen.preise = e.target.checked;
      };
      $("#bnRolle", hg).onchange = rolleZeigen; rolleZeigen();
      // Mitarbeiter gewählt und noch keine Adresse am Zugang: dessen Adresse als Vorschlag eintragen (der Code für „Passwort vergessen?“
      // geht nur an die Adresse, die hier am Zugang steht – nicht mehr an die aus dem Mitarbeiterstamm)
      const maWahl = $("[name=mitarbeiter_id]", hg), mailFeld = $("[name=email]", hg);
      if (maWahl && mailFeld) maWahl.onchange = () => { const m = mas.find(x => String(x.id) === maWahl.value); if (m && m.email && !mailFeld.value.trim()) mailFeld.value = m.email; };
      if ($("#bnAb", hg)) $("#bnAb", hg).onclick = async () => { await api(`benutzer/${b.id}/abmelden`, {method: "POST"}); toast("Auf allen anderen Geräten abgemeldet"); };
      if ($("#bnDel", hg)) $("#bnDel", hg).onclick = async () => {
        if (!await frage(`Benutzer ${b.login} löschen?`)) return;
        try { await api("benutzer/" + b.id, {method: "DELETE"}); hg.remove(); toast("Gelöscht"); danach(); } catch (e) { toast(e.message, true); }
      };
    });
  if (!d) return;
  const body = {...d, mitarbeiter_id: d.mitarbeiter_id ? +d.mitarbeiter_id : null};
  if (d.aktiv !== undefined) body.aktiv = +d.aktiv;
  if (d.rolle === "eigen") body.eigen = eigen;
  if (d.rolle !== "inhaber") {
    body.kalender = kal;
  }
  if (!d.passwort) delete body.passwort;
  try { await api("benutzer" + (neu ? "" : "/" + b.id), {method: neu ? "POST" : "PUT", body}); toast("Gespeichert"); danach(); }
  catch (e) { toast(e.message, true); }
}

// ---------------------------------------------------------------------
//  Mitarbeiter-Bereich
// ---------------------------------------------------------------------
const PERS_REITER = [["Mitarbeiter", ""], ["Zeiten", "zeiten"], ["Urlaub & Abwesenheit", "abwesenheit"], ["Monatsbeleg", "beleg"], ["Lohnzahlung", "lohn"]];
function persKopf(aktiv, kontext = "") {
  kopf({krumen: [["Mitarbeiter", "#/personal"]], kontext,
    reiter: PERS_REITER.map(([l, s]) => [l, `#/personal${s ? "/" + s : ""}`, s === aktiv])});
}
const persAuswahl = {mid: null, woche: null, monat: null, jahr: new Date().getFullYear()};

async function ansichtPersonal(b, c, d) {
  PMETA = PMETA || await api("mitarbeiter/meta");
  if (b === "ma" && c) return mitarbeiterSeite(+c);
  if (b === "zeiten") return zeitenSeitePersonal(c ? +c : null);
  if (b === "abwesenheit") return abwesenheitSeite();
  if (b === "beleg") return monatsbelegSeite(c ? +c : null, d);
  if (b === "lohn") return lohnSeite(c);
  return mitarbeiterListe();
}

async function mitarbeiterListe() {
  persKopf("");
  const z = $("#inhalt");
  let status = "aktiv";
  const zeichnen = async () => {
    const l = await api("mitarbeiter?status=" + status);
    const t = tabelle("ma", [
      {k: "nummer", t: "Nr.", f: m => `<a href="#/personal/ma/${m.id}">${m.nummer}</a>`},
      {k: "name", t: "Name", f: m => `<a href="#/personal/ma/${m.id}">${esc(m.name)}</a>${m.kuerzel ? ` <span class="hinweis">${esc(m.kuerzel)}</span>` : ""}${m.aktiv ? "" : ` <span class="tag">ausgetreten</span>`}`},
      {k: "lohnart_name", t: "Lohnart"},
      {k: "wochenstunden", t: "Std./Woche", r: 1, f: m => zahlDE(m.wochenstunden, m.wochenstunden % 1 ? 2 : 0)},
      {k: "ueberstunden", t: "Überstunden", r: 1, f: m => m.ueberstunden == null ? "" : stdV(m.ueberstunden) + " h"},
      {k: "resturlaub", t: "Resturlaub", r: 1, f: m => m.resturlaub == null ? "" : zahlDE(m.resturlaub, 1) + " T."},
      {k: "laeuft", t: "Gerade", f: m => m.laeuft ? `<span style="color:var(--gruen)">● seit ${m.laeuft.beginn}</span> ${esc(m.laeuft.auftragsnr || m.laeuft.taetigkeit || "")}` : ""},
      {k: "benutzer", t: "Anmeldung", f: m => m.benutzer.length ? esc(m.benutzer.join(", ")) : `<span class="hinweis">kein Benutzer</span>`},
    ], l, {klick: m => location.hash = `#/personal/ma/${m.id}`, leer: "Noch keine Mitarbeiter. Inhaber und Mitarbeiter werden mit „+ Mitarbeiter“ angelegt."});
    $("#maL").innerHTML = t.html; t.binden(zeichnen);
  };
  z.innerHTML = `<div class="titel"><h2>Mitarbeiter</h2>
      <div class="such"><select id="maS"><option value="aktiv">Aktive</option><option value="alle">Alle, auch ausgetreten</option></select></div>
      <div class="rechts"><button class="btn prim" id="maNeu">+ Mitarbeiter</button></div></div>
    <div id="maL"></div>
    <p class="hinweis">Jeder Mitarbeiter bekommt für die Stempeluhr einen eigenen Benutzer (Rolle „Mitarbeiter“). Die Stunden mit Auftrag fließen automatisch in die Nachkalkulation des Auftrags (Reiter Stunden und Soll/Ist).</p>`;
  $("#maS").onchange = e => { status = e.target.value; zeichnen(); };
  $("#maNeu").onclick = async () => {
    const d = await modal("Neuer Mitarbeiter", `<div class="form" style="grid-template-columns:1fr">
      ${zeile("Vorname", `<input name="vorname">`)}${zeile("Nachname", `<input name="nachname">`)}
      ${zeile("Kürzel", `<input name="kuerzel" style="width:80px;flex:0 0 80px" placeholder="MM">`)}
      ${zeile("Personalnummer", `<input name="nummer" value="${PMETA.naechste_nr}" style="width:100px;flex:0 0 100px">`)}
      ${zeile("Eintritt", `<input name="eintritt" type="date">`)}
      ${zeile("Lohnart", `<select name="lohnart">${optsKV(Object.entries(PMETA.lohnarten), "stunde")}</select>`)}</div>`, "Anlegen");
    if (!d) return;
    try { const m = await api("mitarbeiter", {method: "POST", body: d}); PMETA = null; location.hash = `#/personal/ma/${m.id}`; } catch (e) { toast(e.message, true); }
  };
  await zeichnen();
}

async function mitarbeiterSeite(id) {
  PMETA = PMETA || await api("mitarbeiter/meta");
  const m = await api("mitarbeiter/" + id);
  persKopf("", `Mitarbeiter <b>${m.nummer}</b> · <b>${esc(m.name)}</b>`);
  const z = $("#inhalt");
  const f = (k, l, attr = "") => zeile(l, `<input data-f="${k}" value="${esc(m[k] ?? "")}" ${attr}>`);
  const geld = (k, l, einheit = "€") => zeile(l, `<input data-f="${k}" class="zahl" value="${m[k] ? n2(m[k]) : ""}" style="width:110px;flex:0 0 110px"> <span style="padding-top:6px">${einheit}</span>`);
  const k = m.konten;
  z.innerHTML = `
    <div class="titel"><h2>${esc(m.name)}</h2><span class="speicher"></span>
      <div class="rechts"><a class="btn" href="#/personal/zeiten/${id}">Zeiten</a><a class="btn" href="#/personal/beleg/${id}">Monatsbeleg</a></div></div>
    <div class="ma-raster">
    <div>
      <div class="form" id="maF" style="grid-template-columns:1fr">
        <div class="sektion">Person</div>
        ${f("vorname", "Vorname")}${f("nachname", "Nachname")}${f("kuerzel", "Kürzel", `style="width:90px;flex:0 0 90px"`)}${f("nummer", "Personalnummer", `style="width:100px;flex:0 0 100px"`)}
        ${f("strasse", "Straße")}${zeile("PLZ / Ort", `<input data-f="plz" value="${esc(m.plz)}" style="width:80px;flex:0 0 80px"><input data-f="ort" value="${esc(m.ort)}">`)}
        ${f("telefon", "Telefon")}${f("email", "E-Mail")}
        ${zeile("Eintritt / Austritt", `<input data-f="eintritt" type="date" value="${esc(m.eintritt)}"><input data-f="austritt" type="date" value="${esc(m.austritt)}">`)}
        ${zeile("Geburtsdatum", `<input data-f="geburtsdatum" type="date" value="${esc(m.geburtsdatum || "")}" style="flex:0 0 170px"><span class="hinweis" style="padding-top:5px">nur für den Jugendarbeitsschutz: unter 18 halbjährliche Unterweisung</span>`)}
        ${zeile("Status", `<select data-f="aktiv">${optsKV([[1, "aktiv"], [0, "ausgetreten / inaktiv"]], m.aktiv)}</select>`)}
        <div class="sektion">Lohn</div>
        ${zeile("Lohnart", `<select data-f="lohnart">${optsKV(Object.entries(PMETA.lohnarten), m.lohnart)}</select>`)}
        ${geld("stundenlohn", "Stundenlohn brutto", "€/h")}${geld("gehalt", "Monatsgehalt brutto")}
        ${geld("kostensatz", "Kostensatz intern", "€/h")}
        ${zeile("", `<span class="hinweis">Kostensatz = was eine Stunde den Betrieb wirklich kostet (Lohn + Lohnnebenkosten). Für die Nachkalkulation zählt weiterhin die Lohngruppe aus der Kalkulation.</span>`)}
        ${zeile("IBAN", `<input data-f="iban" value="${esc(ibanFormat(m.iban))}" style="font-family:monospace"><span id="maIban" style="padding-top:5px;flex:0 0 auto"></span>`)}
        ${f("bic", "BIC")}
        ${zeile("Krankenkasse", `<select data-f="kasse_id">${optsKV(PMETA.kassen.map(l => [l.id, l.kurzname + (l.gruppe ? " · " + l.gruppe : "")]), m.kasse_id, "— Lieferant wählen —")}</select>`)}
        ${zeile("", `<span class="hinweis">Krankenkasse und Finanzamt werden als Lieferanten mit IBAN angelegt. Für die Lohnüberweisung legt das Programm den Mitarbeiter automatisch als Zahlungsempfänger an (Lieferantengruppe „Mitarbeiter“).</span>`)}
        ${zeile("Bemerkungen", `<textarea data-f="bemerkungen" rows="3">${esc(m.bemerkungen)}</textarea>`)}
      </div>
    </div>
    <div>
      <div class="sektion" style="margin-top:0">Arbeitszeit und Urlaub</div>
      <div id="maMod"></div>
      <div class="sektion">Konten</div>
      <div class="form" id="maK" style="grid-template-columns:1fr">
        ${zeile("Konten ab", `<input data-f="konten_ab" type="date" value="${esc(m.konten_ab)}"><span class="hinweis" style="padding-top:5px">ab hier zählen Überstunden und Urlaub</span>`)}
        ${zeile("Überstunden am Start", `<input data-f="ueberstunden_start" class="zahl" value="${n2(m.ueberstunden_start)}" style="width:90px;flex:0 0 90px"> <span style="padding-top:6px">h</span>`)}
        ${zeile("Resturlaub am Start", `<input data-f="urlaub_start" class="zahl" value="${n2(m.urlaub_start, 1)}" style="width:90px;flex:0 0 90px"> <span style="padding-top:6px">Tage</span><span class="hinweis" style="padding-top:5px">Start am 1.1.: Übertrag aus dem Vorjahr (der Jahresanspruch kommt automatisch dazu). Start mitten im Jahr: noch offener Urlaub an diesem Tag. Bei Eintritt leer lassen.</span>`)}
      </div>
      ${m.lohnart === "inhaber" ? `<p class="hinweis" style="margin:6px 0 0">Lohnart Inhaber: Es gibt kein Soll, gezählt werden nur die Iststunden. Das Überstundenkonto spielt dann keine Rolle.</p>` : ""}
      ${m.lohnart !== "inhaber" && m.konten_ab && m.konten_ab < `${new Date().getFullYear()}-01-01` ? `<p class="hinweis" style="margin:6px 0 0;color:var(--rot)">Die Konten laufen seit ${datum(m.konten_ab)}. Alle Arbeitstage seitdem ohne erfasste Zeit zählen als Minusstunden, und für jedes Jahr kommt Urlaubsanspruch dazu. Beginnt die Zeiterfassung erst jetzt, „Konten ab“ auf heute bzw. den 1.1. setzen und Überstunden und Resturlaub zu diesem Tag eintragen.</p>` : ""}
      <div class="kachel" style="margin-top:10px">
        <div style="display:flex;gap:28px;flex-wrap:wrap">
          <div><div class="hinweis">Überstunden heute</div><div style="font-size:1.5em">${stdV(k.ueberstunden)} h</div></div>
          <div><div class="hinweis">Resturlaub ${new Date().getFullYear()}</div><div style="font-size:1.5em">${zahlDE(k.urlaub_rest, 1)} Tage</div>${k.urlaub_geplant ? `<div class="hinweis">davon ${zahlDE(k.urlaub_geplant, 1)} schon eingetragen</div>` : ""}</div>
        </div>
        <table class="liste" style="margin-top:10px"><tr><th>Urlaub</th><th class="r">Übertrag</th><th class="r">Anspruch</th><th class="r">Korrektur</th><th class="r">genommen</th><th class="r">Rest</th></tr>
          ${k.urlaub_jahre.map(j => `<tr><td>${j.jahr}</td><td class="r">${zahlDE(j.uebertrag, 1)}</td><td class="r">${zahlDE(j.anspruch, 1)}</td><td class="r">${j.korrektur ? zahlDE(j.korrektur, 1) : ""}</td><td class="r">${zahlDE(j.genommen, 1)}</td><td class="r"><b>${zahlDE(j.rest, 1)}</b></td></tr>`).join("")}</table>
        <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap"><button class="btn" id="maKorr">Korrektur buchen …</button><span class="hinweis" style="padding-top:6px">z. B. „20 h Überstunden ausbezahlt“ (−20) oder „Resturlaub verfallen“</span></div>
        <div id="maBuch"></div>
      </div>
      <div class="sektion">Anmeldung</div>
      <div>${m.benutzer.length ? m.benutzer.map(b => `<span class="tag">${esc(b.login)}</span> `).join("") + ` <a href="#/einstellungen/benutzer">verwalten</a>`
        : `<button class="btn" id="maBen">Benutzer für die Stempeluhr anlegen …</button>`}</div>
      <div style="margin-top:20px"><button class="btn rot" id="maDel">Mitarbeiter löschen</button>${ICH.rechte.inhaber ? ` <button class="btn" id="maAnon" title="Für ausgeschiedene Mitarbeiter nach Ablauf der Aufbewahrungsfristen: Name, Anschrift, Geburtsdatum, Bankverbindung, Unterschriften und Qualifikationsnachweise entfernen; Zeiten und Lohnsummen bleiben">Anonymisieren …</button>` : ""}</div>
    </div></div>`;
  autospeichern($("#maF"), "mitarbeiter/" + id);
  autospeichern($("#maK"), "mitarbeiter/" + id, () => mitarbeiterSeite(id));
  const iban = $("[data-f=iban]");
  const ibanZeigen = () => { const v = iban.value.trim(); $("#maIban").innerHTML = !v ? "" : ibanOk(v) ? `<span style="color:var(--gruen)">✓ gültig</span>` : `<span style="color:var(--rot)">ungültig</span>`; };
  iban.addEventListener("input", ibanZeigen); ibanZeigen();
  // Arbeitszeitmodelle
  const mods = m.modelle.map(x => ({...x, tage: [...x.tage]}));
  const modZeichnen = () => {
    const PL = E.sollplaene || [];
    $("#maMod").innerHTML = `<table class="liste ma-mod"><tr><th>gültig ab</th><th>Sollstundenplan</th>${PMETA.wochentage.map(t => `<th class="r">${t}</th>`).join("")}<th class="r">Woche</th><th class="r">Urlaub/Jahr</th><th></th></tr>
      ${mods.map((x, i) => `<tr><td><input type="date" data-mi="${i}" data-mk="ab" value="${esc(x.ab)}" style="width:130px"></td>
        <td><select data-mi="${i}" data-mk="plan"><option value="">individuell</option>${PL.map(p => `<option value="${esc(p.id)}" ${p.id === x.plan ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></td>
        ${x.tage.map((t, j) => `<td class="r"><input class="zahl" data-mi="${i}" data-mt="${j}" value="${t ? n2(t, t % 1 ? 2 : 0) : ""}" style="width:46px" ${x.plan ? "disabled title=\"kommt aus dem Sollstundenplan\"" : ""}></td>`).join("")}
        <td class="r"><b>${zahlDE(x.tage.reduce((s, t) => s + (+t || 0), 0), 2)}</b></td>
        <td class="r"><input class="zahl" data-mi="${i}" data-mk="urlaub" value="${n2(x.urlaub, x.urlaub % 1 ? 1 : 0)}" style="width:50px"></td>
        <td>${mods.length > 1 ? `<a href="#" data-mdel="${i}" title="entfernen">✕</a>` : ""}</td></tr>`).join("")}</table>
      <div style="margin-top:6px"><a href="#" id="maModNeu">+ geänderte Arbeitszeit ab einem Datum</a> <span class="hinweis">· Stunden je Wochentag (Soll), Urlaubstage je Jahr bei voller Beschäftigung. Mit einem Sollstundenplan (Einstellungen › Arbeitszeit) kommen Sollstunden und Zuschläge aus dem Plan.</span></div>`;
    const sp = async () => { try { await api("mitarbeiter/" + id, {method: "PUT", body: {modelle: mods}}); $(".speicher").textContent = "gespeichert ✓"; } catch (e) { toast(e.message, true); } };
    $$("[data-mi]").forEach(el => el.onchange = () => {
      const x = mods[+el.dataset.mi];
      if (el.dataset.mt !== undefined) x.tage[+el.dataset.mt] = zahlEin(el.value);
      else if (el.dataset.mk === "ab") x.ab = el.value;
      else if (el.dataset.mk === "plan") { x.plan = el.value; const p = PL.find(p => p.id === x.plan); if (p) x.tage = [...p.tage]; }
      else x.urlaub = zahlEin(el.value);
      sp(); modZeichnen();
    });
    $$("[data-mdel]").forEach(a => a.onclick = e => { e.preventDefault(); mods.splice(+a.dataset.mdel, 1); sp(); modZeichnen(); });
    $("#maModNeu").onclick = e => { e.preventDefault(); mods.push({ab: heute(), tage: [...mods[mods.length - 1].tage], urlaub: mods[mods.length - 1].urlaub, plan: mods[mods.length - 1].plan || ""}); modZeichnen(); };
  };
  modZeichnen();
  const buchungen = async () => {
    const kk = await api("konten/" + id);
    $("#maBuch").innerHTML = kk.buchungen.length ? `<table class="liste" style="margin-top:8px">${kk.buchungen.map(b => `<tr><td>${datum(b.datum)}</td><td>${b.konto === "urlaub" ? "Urlaub" : "Überstunden"}</td>
      <td class="r">${zahlDE(b.wert, b.konto === "urlaub" ? 1 : 2)} ${b.konto === "urlaub" ? "T." : "h"}</td><td>${esc(b.text)}</td><td><a href="#" data-kb="${b.id}">✕</a></td></tr>`).join("")}</table>` : "";
    $$("[data-kb]").forEach(a => a.onclick = async e => { e.preventDefault(); if (!await frage("Korrekturbuchung löschen?")) return; await api("konten/buchung/" + a.dataset.kb, {method: "DELETE"}); mitarbeiterSeite(id); });
  };
  buchungen();
  $("#maKorr").onclick = async () => {
    const d = await modal("Korrektur buchen", `<div class="form" style="grid-template-columns:1fr">
      ${zeile("Konto", `<select name="konto"><option value="ueberstunden">Überstunden (Stunden)</option><option value="urlaub">Urlaub (Tage)</option></select>`)}
      ${zeile("Datum", `<input type="date" name="datum" value="${heute()}">`)}
      ${zeile("Wert", `<input name="wert" class="zahl" style="width:100px;flex:0 0 100px" placeholder="-20"><span class="hinweis" style="padding-top:5px">negativ = abziehen</span>`)}
      ${zeile("Text", `<input name="text" placeholder="z. B. 20 Überstunden mit Novemberlohn ausbezahlt">`)}</div>`, "Buchen");
    if (!d) return;
    try { await api("konten/" + id, {method: "POST", body: {...d, wert: zahlEin(d.wert)}}); mitarbeiterSeite(id); } catch (e) { toast(e.message, true); }
  };
  if ($("#maBen")) $("#maBen").onclick = async () => {
    const vorschlag = (m.vorname || m.kuerzel || "").toLowerCase().replace(/[^a-z0-9äöüß]/g, "");
    const d = await modal("Benutzer für die Stempeluhr", `<div class="form" style="grid-template-columns:1fr">
      ${zeile("Benutzername", `<input name="login" value="${esc(vorschlag)}" autocapitalize="none">`)}
      ${zeile("PIN / Passwort", `<input name="passwort" placeholder="mind. 6 Zeichen">`)}
      ${zeile("Rolle", `<select name="rolle"><option value="mitarbeiter">Mitarbeiter – nur Stempeluhr und eigene Zeiten</option><option value="werkstatt">Werkstatt – zusätzlich Werkstattpapiere der Aufträge</option></select>`)}</div>`, "Anlegen");
    if (!d) return;
    try { await api("benutzer", {method: "POST", body: {...d, name: m.name, mitarbeiter_id: id}}); toast("Benutzer angelegt"); mitarbeiterSeite(id); } catch (e) { toast(e.message, true); }
  };
  if ($("#maAnon")) $("#maAnon").onclick = async () => {
    try {
      const i = await api(`mitarbeiter/${id}/anonymisieren`);
      if (!i.erlaubt) return frage(!i.austritt ? "Anonymisiert werden nur ausgeschiedene Mitarbeiter. Bitte zuerst das Austrittsdatum eintragen." : `Noch nicht möglich.\n\nLetzter Eintrag ${datum(i.letzter_eintrag)} – Lohn- und Zeitunterlagen werden 10 Jahre ab Jahresende aufbewahrt, also bis ${datum(i.frist_ende)}.`, {titel: "Anonymisieren", ok: "OK", abbrechen: "Schließen"});
      if (!await frage(`${m.name} anonymisieren?\n\nName, Anschrift, Geburtsdatum, Kontaktdaten, Bankverbindung, Bemerkungen, Unterschriften, Qualifikationsnachweise und der Zugang zur Stempeluhr werden endgültig entfernt; Zeiten, Abwesenheiten und Lohnsummen bleiben ohne Namen erhalten.`, {ok: "Endgültig anonymisieren"})) return;
      await api(`mitarbeiter/${id}/anonymisieren`, {method: "POST"}); PMETA = null; toast("Mitarbeiter anonymisiert"); location.hash = "#/personal";
    } catch (e) { toast(e.message, true); }
  };
  $("#maDel").onclick = async () => {
    if (!await frage(`${m.name} löschen?\n\nGeht nur, solange es keine Zeiten oder Lohndaten gibt. Sonst bitte Austrittsdatum eintragen und auf „ausgetreten“ stellen.`)) return;
    try { await api("mitarbeiter/" + id, {method: "DELETE"}); PMETA = null; location.hash = "#/personal"; } catch (e) { toast(e.message, true); }
  };
}

// ---------- Zeiten (Wochenansicht, bearbeiten, nachtragen) ----------
async function maWahl(aktuell, alle = false) {
  const l = await api("mitarbeiter?status=" + (alle ? "alle" : "aktiv"));
  if (!aktuell && l.length) aktuell = l[0].id;
  return {liste: l, id: aktuell, html: `<select id="persMa">${optsKV(l.map(m => [m.id, `${m.nummer} ${m.name}`]), aktuell)}</select>`};
}
// Auftrag und optional Titel in einer Auswahl: Wert "id" oder "id:titelnr"
function auftragOpts(wert, titel = 0) {
  const w = titel ? `${wert}:${titel}` : String(wert || "");
  return `<option value="">— ohne Auftrag —</option>` + PMETA.auftraege.map(a => `<option value="${a.id}" ${String(a.id) === w ? "selected" : ""}>${esc(a.nummer)} ${esc(a.bezeichnung)} · ${esc(a.kunde)}</option>`
    + (a.titel || []).map(t => `<option value="${a.id}:${t.nr}" ${`${a.id}:${t.nr}` === w ? "selected" : ""}>&nbsp;&nbsp;&nbsp;› ${esc(a.nummer)} ${esc(a.bezeichnung)} › T${String(t.nr).padStart(2, "0")} ${esc(t.name)}</option>`).join("")).join("");
}
const auftragWert = v => { const [a, t] = String(v || "").split(":"); return {auftrag_id: a ? +a : null, titel: t ? +t : 0}; };
function taetigkeitOpts(auftrag, kst, taet) {
  const t = PMETA.taetigkeiten;
  if (auftrag) return `<option value="">—</option>` + t.produktiv.map(x => `<option value="k:${esc(x.kst)}" ${x.kst === kst ? "selected" : ""}>${esc(x.name)}</option>`).join("");
  return `<option value="">—</option>` + [...new Set([...t.gemein, ...(taet && !t.gemein.includes(taet) ? [taet] : [])])].map(x => `<option value="t:${esc(x)}" ${x === taet ? "selected" : ""}>${esc(x)}</option>`).join("");
}
async function zeitenSeitePersonal(mid) {
  PMETA = PMETA || await api("mitarbeiter/meta");
  persKopf("zeiten");
  const w = await maWahl(mid || persAuswahl.mid);
  persAuswahl.mid = w.id;
  persAuswahl.woche = persAuswahl.woche || montagVon(heute());
  const z = $("#inhalt");
  if (!w.id) { z.innerHTML = `<div class="leer">Noch keine Mitarbeiter angelegt.</div>`; return; }
  const von = persAuswahl.woche, bis = tagPlus(von, 6);
  const [zeiten, monat1, monat2] = await Promise.all([api(`zeiten?mitarbeiter=${w.id}&von=${von}&bis=${bis}`),
    api(`monatsbeleg/${w.id}?monat=${von.slice(0, 7)}`), bis.slice(0, 7) !== von.slice(0, 7) ? api(`monatsbeleg/${w.id}?monat=${bis.slice(0, 7)}`) : null]);
  const tageInfo = Object.fromEntries([...monat1.tage, ...(monat2 ? monat2.tage : [])].map(t => [t.datum, t]));
  const d0 = new Date(von + "T12:00");
  const kwNr = kw(d0);
  let html = "";
  for (let i = 0; i < 7; i++) {
    const tag = tagPlus(von, i), t = tageInfo[tag] || {}, zs = zeiten.filter(x => x.datum === tag);
    html += `<tr class="zt-tag ${t.feiertag || i > 4 ? "we" : ""}"><td colspan="2"><b>${t.wt} ${datum(tag).slice(0, 6)}</b> ${esc(t.feiertag || (t.abw ? PMETA.abwesenheit[t.abw] : ""))}${t.hinweis ? ` <span style="color:var(--rot)">· ${esc(t.hinweis)}</span>` : ""}</td>
      <td class="r hinweis">Pause ${std(t.pause)}</td><td class="r">Soll ${std(t.soll)}</td><td class="r">Ist <b>${std(t.ist)}</b></td><td class="r">${t.zukunft ? "" : stdV(t.saldo)}</td>
      <td class="r"><a href="#" data-zneu="${tag}">+ Zeit</a></td></tr>`;
    for (const x of zs) html += `<tr data-zid="${x.id}" class="zt-zeile"><td class="nw"><input class="zt-u" data-k="beginn" value="${x.beginn}"> – <input class="zt-u" data-k="ende" value="${x.ende || ""}" placeholder="läuft"></td>
      <td><select data-k="auftrag_id" style="max-width:300px">${auftragOpts(x.auftrag_id, x.titel)}</select></td>
      <td><select data-k="taet">${taetigkeitOpts(x.auftrag_id, x.kst, x.taetigkeit)}</select></td>
      <td colspan="2"><input data-k="notiz" value="${esc(x.notiz)}" placeholder="Notiz" style="width:100%"></td>
      <td class="r">${std(x.stunden)} h</td><td class="r nw">${x.spaet ? `<span class="hinweis" style="font-size:12px;color:#8a5a00" title="Die Stempelung kam nicht im Augenblick des Stempelns beim Programm an (Handy ohne Netz – oder die Zeit wurde später eingegeben). Eingegangen am ${datum((x.eingang || "").slice(0, 10))} um ${esc((x.eingang || "").slice(11, 16))} Uhr, ${x.spaet >= 120 ? Math.round(x.spaet / 60) + " Stunden" : x.spaet + " Minuten"} nach der gestempelten Zeit.">⏱ nachträglich</span> ` : ""}<span class="hinweis" style="font-size:12px">${{stempel: "Stempeluhr", nachtrag: "Nachtrag", pc: "Büro"}[x.quelle] || ""}</span> <a href="#" data-zdel="${x.id}" title="Zeit löschen">✕</a></td></tr>`;
  }
  const summe = Object.values(tageInfo).filter(t => t.datum >= von && t.datum <= bis);
  z.innerHTML = `<div class="titel"><h2>Zeiten</h2><div class="such">${w.html}
      <button class="btn" id="ztZur" title="Vorige Woche">‹</button><b style="padding:6px 4px">KW ${kwNr} · ${datum(von).slice(0, 6)}–${datum(bis)}</b><button class="btn" id="ztVor" title="Nächste Woche">›</button><button class="btn" id="ztHeute">heute</button></div>
      <span class="speicher"></span></div>
    <table class="liste zt">${html}
      <tr class="sum"><td colspan="3">Woche</td><td class="r">Soll ${std(summe.reduce((s, t) => s + t.soll, 0))}</td><td class="r">Ist ${std(summe.reduce((s, t) => s + t.ist, 0))}</td>
      <td class="r">${stdV(summe.reduce((s, t) => s + t.saldo, 0))}</td><td></td></tr></table>
    <p class="hinweis">Herkunft: Stempeluhr, Nachtrag (vom Mitarbeiter nachgetragen) oder Büro. Änderungen speichern sofort und landen auch in den Auftragsstunden. Urlaub und Krankheit unter „Urlaub & Abwesenheit“.</p>`;
  $("#persMa").onchange = e => { persAuswahl.mid = +e.target.value; zeitenSeitePersonal(persAuswahl.mid); };
  $("#ztZur").onclick = () => { persAuswahl.woche = tagPlus(von, -7); zeitenSeitePersonal(w.id); };
  $("#ztVor").onclick = () => { persAuswahl.woche = tagPlus(von, 7); zeitenSeitePersonal(w.id); };
  $("#ztHeute").onclick = () => { persAuswahl.woche = montagVon(heute()); zeitenSeitePersonal(w.id); };
  const neuLaden = () => zeitenSeitePersonal(w.id);
  $$("tr[data-zid]").forEach(tr => {
    const zid = tr.dataset.zid;
    $$("[data-k]", tr).forEach(el => el.onchange = async () => {
      const body = {};
      if (el.dataset.k === "taet") {
        const v = el.value;
        body.kst = v.startsWith("k:") ? v.slice(2) : ""; body.taetigkeit = v.startsWith("t:") ? v.slice(2) : "";
      } else if (el.dataset.k === "auftrag_id") {
        const alt = zeiten.find(x => String(x.id) === String(zid)) || {};
        Object.assign(body, auftragWert(el.value));
        if (body.auftrag_id !== alt.auftrag_id) { body.kst = ""; body.taetigkeit = ""; }
      }
      else body[el.dataset.k] = el.value;
      try { await api("zeiten/" + zid, {method: "PUT", body}); toast("Gespeichert"); neuLaden(); } catch (e) { toast(e.message, true); neuLaden(); }
    });
  });
  $$("[data-zdel]").forEach(a => a.onclick = async e => { e.preventDefault(); if (!await frage("Zeiteintrag löschen?")) return; await api("zeiten/" + a.dataset.zdel, {method: "DELETE"}); neuLaden(); });
  $$("[data-zneu]").forEach(a => a.onclick = async e => {
    e.preventDefault();
    const tag = a.dataset.zneu;
    const d = await modal(`Zeit nachtragen · ${datum(tag)}`, `<div class="form" style="grid-template-columns:1fr">
      ${zeile("Von – bis", `<input name="beginn" placeholder="7:00" style="width:80px;flex:0 0 80px"> – <input name="ende" placeholder="12:00" style="width:80px;flex:0 0 80px">`)}
      ${zeile("Auftrag", `<select name="auftrag_id" id="znA">${auftragOpts("")}</select>`)}
      ${zeile("Tätigkeit", `<select name="taet" id="znT">${taetigkeitOpts(null)}</select>`)}
      ${zeile("Notiz", `<input name="notiz">`)}</div>`, "Speichern", hg => {
        $(".modal", hg).style.width = "min(620px,96vw)";
        $("#znA", hg).onchange = e => $("#znT", hg).innerHTML = taetigkeitOpts(auftragWert(e.target.value).auftrag_id);
      });
    if (!d) return;
    try {
      await api("zeiten", {method: "POST", body: {mitarbeiter_id: w.id, datum: tag, beginn: d.beginn, ende: d.ende, ...auftragWert(d.auftrag_id),
        kst: d.taet.startsWith("k:") ? d.taet.slice(2) : "", taetigkeit: d.taet.startsWith("t:") ? d.taet.slice(2) : "", notiz: d.notiz}});
      neuLaden();
    } catch (x) { toast(x.message, true); }
  });
}

// ---------- Urlaub & Abwesenheit ----------
async function abwesenheitSeite() {
  PMETA = PMETA || await api("mitarbeiter/meta");
  persKopf("abwesenheit");
  const z = $("#inhalt");
  const j = persAuswahl.jahr;
  const [l, mas] = await Promise.all([api(`abwesenheiten?von=${j}-01-01&bis=${j}-12-31`), api("mitarbeiter")]);
  const offen = l.filter(a => a.status === "beantragt");
  z.innerHTML = `<div class="titel"><h2>Urlaub und Abwesenheit</h2><div class="such"><button class="btn" id="abZur" title="Voriges Jahr">‹</button><b style="padding:6px">${j}</b><button class="btn" id="abVor" title="Nächstes Jahr">›</button></div>
      <div class="rechts"><button class="btn prim" id="abNeu">+ eintragen</button></div></div>
    ${offen.length ? `<div class="kachel" style="border-left:4px solid var(--akzent);margin-bottom:12px"><b>Urlaubsanträge</b>
      <table class="liste" style="margin-top:6px">${offen.map(a => `<tr><td>${esc(a.vorname)} ${esc(a.nachname)}</td><td>${datum(a.von)}${a.bis !== a.von ? " – " + datum(a.bis) : ""}${a.halbtag ? " (halber Tag)" : ""}</td>
        <td class="r">${zahlDE(a.arbeitstage, 1)} Tage</td><td>${esc(a.notiz)}</td><td class="r"><button class="btn prim" data-gen="${a.id}">genehmigen</button> <button class="btn" data-abl="${a.id}">ablehnen</button></td></tr>`).join("")}</table></div>` : ""}
    <div class="ab-kal" id="abKal"></div>
    <table class="liste" style="margin-top:14px"><tr><th>Mitarbeiter</th><th>Art</th><th>Zeitraum</th><th class="r">Arbeitstage</th><th>Status</th><th>Notiz</th><th></th></tr>
      ${l.map(a => `<tr><td>${esc(a.vorname)} ${esc(a.nachname)}</td><td>${esc(a.art_name)}</td><td>${datum(a.von)}${a.bis !== a.von ? " – " + datum(a.bis) : ""}${a.halbtag ? " (½)" : ""}</td>
        <td class="r">${zahlDE(a.arbeitstage, 1)}</td><td>${a.status === "genehmigt" ? "" : `<span class="tag">${esc(a.status)}</span>`}</td><td>${esc(a.notiz)}</td>
        <td class="r nw"><a href="#" data-abe="${a.id}">bearbeiten</a> · <a href="#" data-abd="${a.id}">✕</a></td></tr>`).join("") || `<tr><td colspan="7" class="leer">Keine Einträge in ${j}.</td></tr>`}</table>
    <p class="hinweis">Urlaub, Krankheit, Berufsschule und Sonderurlaub zählen als Ist-Zeit (Soll des Tages wird gutgeschrieben). „Überstunden frei“ baut das Überstundenkonto ab, „Unbezahlt frei“ senkt das Soll. Feiertage in Baden-Württemberg trägt das Programm selbst ein.</p>`;
  // Jahreskalender: je Mitarbeiter eine Zeile, Monate als Spalten mit Tagen
  const farbe = {urlaub: "#7aa6d6", krank: "#d98b7a", kind_krank: "#d9a37a", schule: "#9cc59a", sonder: "#b8a4d6", ueberstunden: "#e0c46c", unbezahlt: "#bbb"};
  let kal = `<div class="ab-leg">${Object.entries(PMETA.abwesenheit).map(([k, n]) => `<span><i style="background:${farbe[k]}"></i>${esc(n)}</span>`).join("")}<span><i style="background:#e9e4dc"></i>Wochenende</span></div>`;
  for (let mo = 0; mo < 12; mo++) {
    const tageImMonat = new Date(j, mo + 1, 0).getDate();
    kal += `<div class="ab-mon"><div class="ab-mn">${PMONATE[mo].slice(0, 3)}</div>`;
    for (const m of mas) {
      kal += `<div class="ab-z"><span class="ab-name">${esc(m.kuerzel || m.name)}</span>`;
      for (let t = 1; t <= tageImMonat; t++) {
        const iso = `${j}-${String(mo + 1).padStart(2, "0")}-${String(t).padStart(2, "0")}`;
        const wt = new Date(j, mo, t).getDay();
        const a = l.find(x => x.mitarbeiter_id === m.id && x.von <= iso && x.bis >= iso);
        kal += `<i title="${datum(iso)}${a ? " · " + esc(a.art_name) + (a.status !== "genehmigt" ? " (" + a.status + ")" : "") : ""}" style="${a ? `background:${farbe[a.art]};${a.status !== "genehmigt" ? "opacity:.45" : ""}` : wt === 0 || wt === 6 ? "background:#e9e4dc" : ""}"></i>`;
      }
      kal += `</div>`;
    }
    kal += `</div>`;
  }
  $("#abKal").innerHTML = mas.length ? kal : "";
  $("#abZur").onclick = () => { persAuswahl.jahr--; abwesenheitSeite(); };
  $("#abVor").onclick = () => { persAuswahl.jahr++; abwesenheitSeite(); };
  const dialog = async a => {
    a = a || {mitarbeiter_id: persAuswahl.mid || (mas[0] || {}).id, art: "urlaub", von: heute(), bis: heute(), halbtag: 0, status: "genehmigt", notiz: ""};
    const d = await modal(a.id ? "Abwesenheit bearbeiten" : "Abwesenheit eintragen", `<div class="form" style="grid-template-columns:1fr">
      ${zeile("Mitarbeiter", `<select name="mitarbeiter_id">${optsKV(mas.map(m => [m.id, m.name]), a.mitarbeiter_id)}</select>`)}
      ${zeile("Art", `<select name="art">${optsKV(Object.entries(PMETA.abwesenheit), a.art)}</select>`)}
      ${zeile("Von – bis", `<input type="date" name="von" value="${a.von}"> <input type="date" name="bis" value="${a.bis}">`)}
      ${zeile("Umfang", `<select name="halbtag">${optsKV([[0, "ganze Tage"], [1, "halbe Tage"]], a.halbtag)}</select>`)}
      ${zeile("Status", `<select name="status">${optsKV([["genehmigt", "genehmigt / eingetragen"], ["beantragt", "beantragt"], ["abgelehnt", "abgelehnt"]], a.status)}</select>`)}
      ${zeile("Notiz", `<input name="notiz" value="${esc(a.notiz)}">`)}</div>`, "Speichern");
    if (!d) return;
    if (d.bis < d.von) d.bis = d.von;
    try { await api("abwesenheiten" + (a.id ? "/" + a.id : ""), {method: a.id ? "PUT" : "POST", body: {...d, mitarbeiter_id: +d.mitarbeiter_id, halbtag: +d.halbtag}}); abwesenheitSeite(); }
    catch (e) { toast(e.message, true); }
  };
  $("#abNeu").onclick = () => dialog();
  $$("[data-abe]").forEach(x => x.onclick = e => { e.preventDefault(); dialog(l.find(a => a.id === +x.dataset.abe)); });
  $$("[data-abd]").forEach(x => x.onclick = async e => { e.preventDefault(); if (!await frage("Eintrag löschen?")) return; await api("abwesenheiten/" + x.dataset.abd, {method: "DELETE"}); abwesenheitSeite(); });
  $$("[data-gen]").forEach(b => b.onclick = async () => { await api("abwesenheiten/" + b.dataset.gen, {method: "PUT", body: {status: "genehmigt"}}); toast("Genehmigt"); abwesenheitSeite(); });
  $$("[data-abl]").forEach(b => b.onclick = async () => { await api("abwesenheiten/" + b.dataset.abl, {method: "PUT", body: {status: "abgelehnt"}}); abwesenheitSeite(); });
}

// ---------- Monatsbeleg ----------
function monatsTabelle(d, {kurz = false} = {}) {
  const s = d.summe;
  const zeilen = d.tage.map(t => `<tr class="${t.feiertag || t.wt === "Sa" || t.wt === "So" ? "we" : ""}"><td class="nw">${t.wt} ${datum(t.datum).slice(0, 6)}</td>
    <td>${esc(t.feiertag || (t.abw ? d.abw_namen[t.abw] : ""))}${t.urlaubstage === 0.5 ? " ½" : ""}</td>
    <td class="nw">${t.beginn}${t.ende ? "–" + t.ende : t.laeuft ? "–…" : ""}</td>
    ${kurz ? "" : `<td class="r">${t.pause ? std(t.pause) : ""}</td><td class="r">${t.produktiv ? std(t.produktiv) : ""}</td><td class="r">${t.gemein ? std(t.gemein) : ""}</td><td class="r">${t.abw_std ? std(t.abw_std) : ""}</td>`}
    <td class="r">${t.soll ? std(t.soll) : ""}</td><td class="r">${t.ist ? std(t.ist) : ""}</td><td class="r">${t.zukunft || !(t.soll || t.ist) ? "" : stdV(t.saldo)}</td>
    ${kurz ? "" : `<td style="color:var(--rot);font-size:.9em">${esc(t.hinweis)}</td>`}</tr>`).join("");
  return `<table class="liste mb">
    <tr><th>Datum</th><th>Feiertag / Abwesenheit</th><th>Zeit</th>${kurz ? "" : `<th class="r">Pause</th><th class="r">Produktiv</th><th class="r">Nicht direkt</th><th class="r">Abwes.</th>`}<th class="r">Soll</th><th class="r">Ist</th><th class="r">Saldo</th>${kurz ? "" : "<th></th>"}</tr>
    ${zeilen}
    <tr class="sum"><td colspan="3">Summe</td>${kurz ? "" : `<td class="r">${std(s.pause)}</td><td class="r">${std(s.produktiv)}</td><td class="r">${std(s.gemein)}</td><td class="r">${std(Object.values(d.abwesenheit).reduce((a, b) => a + b, 0))}</td>`}
      <td class="r">${std(s.soll)}</td><td class="r">${std(s.ist)}</td><td class="r">${stdV(s.saldo)}</td>${kurz ? "" : "<td></td>"}</tr></table>`;
}
function kontenKachel(d) {
  const kv = d.konten_vormonat, k = d.konten;
  return `<div class="kachel mb-konten"><div><span class="hinweis">Überstunden Vormonat</span><b>${stdV(kv.ueberstunden)} h</b></div>
    <div><span class="hinweis">Saldo ${monatName(d.monat)}</span><b>${stdV(d.summe.saldo)} h</b></div>
    ${d.korrekturen.length ? `<div><span class="hinweis">Korrekturen</span><b>${d.korrekturen.map(x => zahlDE(x.wert, 2) + (x.konto === "urlaub" ? " T." : " h")).join(", ")}</b></div>` : ""}
    <div><span class="hinweis">Überstunden aktuell</span><b>${stdV(k.ueberstunden)} h</b></div>
    <div><span class="hinweis">Urlaub im Monat</span><b>${zahlDE(d.summe.urlaubstage, 1)} T.</b></div>
    <div><span class="hinweis">Resturlaub</span><b>${zahlDE(k.urlaub_rest, 1)} T.</b></div>
    ${(d.zuschlaege || []).map(x => `<div><span class="hinweis">${esc(x.name)} ${zahlDE(x.prozent, 0)} %</span><b>${zahlDE(x.stunden, 2)} h</b></div>`).join("")}</div>`;
}
async function monatsbelegSeite(mid, monat) {
  persKopf("beleg");
  const w = await maWahl(mid || persAuswahl.mid, true);
  persAuswahl.mid = w.id;
  monat = monat || persAuswahl.monat || heute().slice(0, 7);
  persAuswahl.monat = monat;
  const z = $("#inhalt");
  if (!w.id) { z.innerHTML = `<div class="leer">Noch keine Mitarbeiter angelegt.</div>`; return; }
  const d = await api(`monatsbeleg/${w.id}?monat=${monat}`);
  const kst = Object.entries(d.kostenstellen).sort((a, b) => b[1] - a[1]);
  z.innerHTML = `<div class="titel"><h2>Monatsbeleg</h2><div class="such">${w.html}<button class="btn" id="mbZur" title="Voriger Monat">‹</button><b style="padding:6px 4px">${monatName(monat)}</b><button class="btn" id="mbVor" title="Nächster Monat">›</button></div>
      <div class="rechts"><a class="btn" href="/druck/monatsbeleg/${w.id}/${monat}.pdf" target="_blank">📄 PDF</a></div></div>
    <div id="mbSig"></div>
    ${kontenKachel(d)}
    ${monatsTabelle(d)}
    ${kst.length ? `<div class="kachel" style="margin-top:12px"><b>Stunden nach Tätigkeit</b><div class="mb-kst">${kst.map(([k, v]) => `<span>${esc(d.kst_namen[k] || k)} <b>${std(v)} h</b></span>`).join("")}</div></div>` : ""}`;
  $("#persMa").onchange = e => monatsbelegSeite(+e.target.value, monat);
  monatsbelegUnterschriften($("#mbSig"), w, monat);
  $("#mbZur").onclick = () => monatsbelegSeite(w.id, monatPlus(monat, -1));
  $("#mbVor").onclick = () => monatsbelegSeite(w.id, monatPlus(monat, 1));
}

// Monatsbeleg unterschreiben: Mitarbeiter am Tablet (oder in der Stempeluhr), Arbeitgeber hier
async function monatsbelegUnterschriften(box, w, monat) {
  if (!box) return;
  if (monat > heute().slice(0, 7)) { box.innerHTML = ""; return; }
  let s;
  try { s = await api(`monatsbeleg/${w.id}/unterschriften?monat=${monat}`); } catch (e) { box.innerHTML = ""; return; }
  const name = ((w.liste || []).find(m => m.id === w.id) || {}).name || "";
  const feld = (x, rolle, text) => x ? `<span style="color:${x.geaendert ? "var(--rot)" : "var(--gruen)"}">${x.geaendert ? "⚠" : "✓"} ${esc(text)}: ${esc(x.name)}, ${datum(x.zeit)} ${x.zeit.slice(11, 16)}${x.geaendert ? " – Zeiten seither geändert, bitte neu unterschreiben" : ""}</span>`
    : `<span class="hinweis">${esc(text)}: noch nicht unterschrieben</span>`;
  box.innerHTML = `<div class="kachel" style="margin-bottom:12px;display:flex;gap:18px;align-items:center;flex-wrap:wrap">
    <b>Unterschriften</b>${feld(s.mitarbeiter, "mitarbeiter", "Mitarbeiter")}${feld(s.arbeitgeber, "arbeitgeber", "Arbeitgeber")}
    <span style="margin-left:auto;display:flex;gap:6px;flex-wrap:wrap">${darf("personal", 2) ? `${!s.mitarbeiter || s.mitarbeiter.geaendert ? `<button class="btn" id="mbSigM">✍ Mitarbeiter unterschreibt</button>` : ""}
      ${!s.arbeitgeber || s.arbeitgeber.geaendert ? `<button class="btn prim" id="mbSigA">✍ Als Arbeitgeber unterschreiben</button>` : ""}` : ""}</span></div>`;
  const sig = async (rolle, vorName, fest) => {
    const r = await unterschriftDialog({titel: `Monatsbeleg ${monatName(monat)} – ${rolle === "mitarbeiter" ? "Mitarbeiter" : "Arbeitgeber"}`, name: vorName, nameFest: fest,
      text: `<p>${rolle === "mitarbeiter" ? "Ich bestätige die Arbeitszeiten, Abwesenheiten und Konten" : "Bestätigt: Arbeitszeiten, Abwesenheiten und Konten"} von <b>${esc(name)}</b> für ${monatName(monat)} laut Monatsbeleg.</p>`});
    if (!r) return;
    try { await api(`monatsbeleg/${w.id}/unterschreiben`, {method: "POST", body: {...r, monat, rolle}}); toast("Unterschrift gespeichert"); monatsbelegUnterschriften(box, w, monat); }
    catch (e) { toast(e.message, true); }
  };
  if ($("#mbSigM")) $("#mbSigM").onclick = () => sig("mitarbeiter", name, true);
  if ($("#mbSigA")) $("#mbSigA").onclick = () => sig("arbeitgeber", ICH.name || ICH.login, false);
}

// ---------- Lohnzahlung ----------
async function lohnSeite(monat) {
  persKopf("lohn");
  monat = monat || persAuswahl.lohnmonat || monatPlus(heute().slice(0, 7), new Date().getDate() < 15 ? -1 : 0);
  persAuswahl.lohnmonat = monat;
  const z = $("#inhalt");
  const d = await api("lohn?monat=" + monat);
  const zst = x => !x ? "" : x.bezahlt ? `<span style="color:var(--gruen)" title="bezahlt am ${datum(x.bezahlt)}">✓</span> <a href="#/zahlung/${x.id}">${esc(x.nummer)}</a>`
    : `<a href="#/zahlung/${x.id}">${esc(x.nummer)}</a>`;
  const summe = k => d.zeilen.reduce((s, r) => s + ((r.lohn || {})[k] || 0), 0);
  z.innerHTML = `<div class="titel"><h2>Lohnzahlung</h2><div class="such"><button class="btn" id="lzZur" title="Voriger Monat">‹</button><b style="padding:6px 4px">${monatName(monat)}</b><button class="btn" id="lzVor" title="Nächster Monat">›</button></div><span class="speicher"></span></div>
    <p class="hinweis" style="margin-top:0">So läuft es: Zum Monatsende gehen die Monatsbelege (Stunden, Urlaub, Krankheit) an den Steuerberater. Aus der Lohnabrechnung werden hier Brutto, Auszahlung (netto), Lohnsteuer (inkl. Soli/Kirchensteuer) und der Gesamtsozialversicherungsbeitrag eingetragen. „Überweisungen erzeugen“ legt die Zahlungsaufträge an – sie erscheinen unter Lieferanten › Zahlungen und gehen mit der SEPA-Datei an die Bank.</p>
    <table class="liste lz"><tr><th>Mitarbeiter</th><th class="r">Stunden</th><th class="r">Urlaub</th><th class="r">Krank</th><th class="r" title="Stundenlohn × Ist-Stunden bzw. Gehalt">Richtwert</th>
      <th class="r">Brutto</th><th class="r">Auszahlung</th><th class="r">Lohnsteuer</th><th class="r">SV gesamt</th><th>Überweisungen</th><th></th></tr>
      ${d.zeilen.map(r => { const l = r.lohn || {}; const m = r.mitarbeiter; const inp = k => `<input class="zahl" data-lm="${m.id}" data-lk="${k}" value="${l[k] ? n2(l[k]) : ""}" style="width:90px">`;
        return `<tr><td><a href="#/personal/ma/${m.id}">${esc(m.name)}</a><div class="hinweis">${esc(m.lohnart_name)}</div>${(r.hinweise || []).map(t => `<div class="hinweis" style="color:#8a5a00;max-width:330px;white-space:normal">⚠ ${esc(t)}</div>`).join("")}</td>
        <td class="r">${std(r.ist)}<div class="hinweis">Soll ${std(r.soll)}</div></td><td class="r">${r.urlaub ? zahlDE(r.urlaub, 1) + " T." : ""}</td><td class="r">${r.krank ? r.krank + " T." : ""}</td>
        <td class="r hinweis">${r.schaetzung ? eur(r.schaetzung) : ""}</td>
        <td class="r">${inp("brutto")}</td><td class="r">${inp("netto")}</td><td class="r">${inp("steuer")}</td><td class="r">${inp("sv")}</td>
        <td class="nw" style="font-size:.9em">${["netto", "steuer", "sv"].map(k => r.zahlungen[k] ? `<div>${{netto: "Lohn", steuer: "LSt", sv: "SV"}[k]}: ${zst(r.zahlungen[k])}</div>` : "").join("")}</td>
        <td><a href="/druck/monatsbeleg/${m.id}/${monat}.pdf" target="_blank" title="Monatsbeleg als PDF">📄</a></td></tr>`; }).join("") || `<tr><td colspan="11" class="leer">Keine Mitarbeiter mit Lohn in diesem Monat (Lohnart „Inhaber“ erscheint hier nicht).</td></tr>`}
      <tr class="sum"><td colspan="5">Summe</td><td class="r">${eur(summe("brutto"))}</td><td class="r">${eur(summe("netto"))}</td><td class="r">${eur(summe("steuer"))}</td><td class="r">${eur(summe("sv"))}</td><td colspan="2"></td></tr></table>
    <div class="form" style="grid-template-columns:1fr;margin-top:14px">
      ${zeile("Finanzamt", `<select id="lzFa">${optsKV(d.empfaenger.map(l => [l.id, l.kurzname + (l.gruppe ? " · " + l.gruppe : "")]), d.finanzamt_id, "— Lieferant wählen —")}</select><span class="hinweis" style="padding-top:5px">Empfänger der Lohnsteuer</span>`)}
      ${zeile("Fälligkeiten", `<span style="padding-top:5px">Lohn ${datum(d.faellig.netto)} · Sozialversicherung ${datum(d.faellig.sv)} (drittletzter Bankarbeitstag) · Lohnsteuer ${datum(d.faellig.steuer)}</span>`)}
      ${zeile("", `<button class="btn prim" id="lzZahl">Überweisungen erzeugen</button><span class="hinweis" style="padding-top:6px">schon erzeugte werden nicht doppelt angelegt</span>`)}
    </div>`;
  $("#lzZur").onclick = () => lohnSeite(monatPlus(monat, -1));
  $("#lzVor").onclick = () => lohnSeite(monatPlus(monat, 1));
  $$("[data-lm]").forEach(el => el.onchange = async () => {
    try { await api(`lohn/${el.dataset.lm}?monat=${monat}`, {method: "PUT", body: {[el.dataset.lk]: zahlEin(el.value)}}); $(".speicher").textContent = "gespeichert ✓"; el.value = el.value ? n2(zahlEin(el.value)) : ""; }
    catch (e) { toast(e.message, true); }
  });
  $("#lzZahl").onclick = async () => {
    try {
      const r = await api("lohn/zahlungen", {method: "POST", body: {monat, finanzamt_id: $("#lzFa").value ? +$("#lzFa").value : null}});
      if (r.fehlt.length) await frage(`${r.neu.length ? r.neu.length + " Überweisung(en) angelegt." : "Keine Überweisung angelegt."}\n\nNoch offen:\n${r.fehlt.join("\n")}`, {titel: "Überweisungen", ok: "OK"});
      else toast(r.neu.length ? `${r.neu.length} Überweisung(en) angelegt: ${r.neu.join(", ")}` : "Nichts Neues zu überweisen");
      lohnSeite(monat);
    } catch (e) { toast(e.message, true); }
  };
}

// ---------------------------------------------------------------------
//  Meine Zeiten (für jeden Benutzer mit Mitarbeiter)
// ---------------------------------------------------------------------
async function ansichtMeine(monat) {
  kopf({krumen: [["Meine Zeiten", "#/meine"]]});
  const z = $("#inhalt");
  if (!ICH.mitarbeiter_id) { z.innerHTML = `<div class="leer">Dieser Benutzer ist keinem Mitarbeiter zugeordnet.</div>`; return; }
  monat = monat || heute().slice(0, 7);
  const [d, st, abw] = await Promise.all([api("stempel/monat?monat=" + monat), api("stempel"), api("stempel/abwesenheiten")]);
  z.innerHTML = `<div class="titel"><h2>Meine Zeiten</h2><div class="such"><button class="btn" id="mzZur" title="Voriger Monat">‹</button><b style="padding:6px 4px">${monatName(monat)}</b><button class="btn" id="mzVor" title="Nächster Monat">›</button></div>
      <div class="rechts"><a class="btn prim" href="/stempel" target="_blank">⏱ Stempeluhr öffnen</a></div></div>
    ${st.laeuft ? `<div class="kachel" style="border-left:4px solid var(--gruen);margin-bottom:10px">Gestempelt seit <b>${st.laeuft.beginn}</b> ${esc(st.laeuft.auftragsnr || "")} ${esc(st.laeuft.auftrag || st.laeuft.taetigkeit || "")}</div>` : ""}
    ${kontenKachel(d)}
    ${monatsTabelle(d, {kurz: true})}
    <h3 style="margin-top:18px">Urlaub und Abwesenheiten</h3>
    <table class="liste">${abw.map(a => `<tr><td>${esc(a.art_name)}</td><td>${datum(a.von)}${a.bis !== a.von ? " – " + datum(a.bis) : ""}${a.halbtag ? " (½)" : ""}</td><td>${a.status === "genehmigt" ? "✓ genehmigt" : esc(a.status)}</td><td>${esc(a.notiz)}</td></tr>`).join("") || `<tr><td class="leer">keine</td></tr>`}</table>`;
  $("#mzZur").onclick = () => ansichtMeine(monatPlus(monat, -1));
  $("#mzVor").onclick = () => ansichtMeine(monatPlus(monat, 1));
}

// Einstellungen › Kalkulation › Unproduktive Tätigkeiten (Zeiten ohne Auftrag, z. B. Aufräumen, Maschinenpflege)
function unproduktivVorgabe(z) {
  z.innerHTML = `<div class="titel"><h2>Unproduktive Tätigkeiten</h2><span class="speicher"></span></div>
    <p class="hinweis" style="margin-top:-6px">Zeiten, die keinem Auftrag zugeordnet werden – sie stecken in den Gemeinkosten. Auf der Stempeluhr erscheinen sie unter „Ohne Auftrag“, in der Zeiterfassung im Bereich Mitarbeiter ebenso. Die Tätigkeiten auf Aufträgen sind die Kostenstellen (Reiter Zuschläge).</p>
    <div class="form" style="grid-template-columns:1fr">
      ${zeile("Tätigkeiten", `<textarea id="zgk" rows="10" style="max-width:420px">${esc((E.zeit_gemeinkosten || []).join("\n"))}</textarea><span class="hinweis" style="padding-top:5px">eine je Zeile</span>`)}
    </div>`;
  $("#zgk").onchange = async e => {
    try { E = await api("einstellungen", {method: "PUT", body: {zeit_gemeinkosten: e.target.value.split("\n").map(s => s.trim()).filter(Boolean)}}); toast("Gespeichert"); }
    catch (x) { toast(x.message, true); }
  };
}

// Einstellungen › Arbeitszeit: Feiertage, arbeitsfreie Tage, Sollstundenpläne mit Zuschlägen
async function arbeitszeitVorgabe(z, sub) {
  const jahr = arbeitszeitVorgabe.jahr || new Date().getFullYear();
  const d = await api("mitarbeiter/arbeitszeit?jahr=" + jahr);
  const speichern = async (body, neu = true) => {
    try { E = await api("einstellungen", {method: "PUT", body}); $(".speicher", z) && ($(".speicher", z).textContent = "gespeichert ✓"); if (neu) arbeitszeitVorgabe(z, sub); }
    catch (x) { toast(x.message, true); }
  };
  const wtag = iso => ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"][new Date(iso + "T12:00").getDay()];
  const katTabelle = (liste, schl, spalte) => `<table class="liste"><tr><th>Tag</th><th>${jahr}</th><th style="width:90px">${spalte}</th><th>Hinweis</th></tr>
    ${liste.map(x => `<tr><td>${esc(x.name)}</td><td class="nw">${wtag(x.datum)} ${datum(x.datum).slice(0, 6)}</td><td><input type="checkbox" data-kat="${schl}" value="${x.k}" ${x.an ? "checked" : ""}></td><td class="hinweis">${esc(x.hinweis)}</td></tr>`).join("")}</table>`;
  const jahrWahl = `<select id="azJahr" style="flex:0 0 auto">${[-1, 0, 1, 2].map(i => new Date().getFullYear() + i).map(y => `<option ${y === jahr ? "selected" : ""}>${y}</option>`).join("")}</select>`;
  if (sub === "feiertage" || sub === "frei") {
    const ft = sub === "feiertage";
    const eigene = (E.tage_eigene || []).map(x => ({...x}));
    z.innerHTML = `<div class="titel"><h2>${ft ? "Feiertage" : "Arbeitsfreie Tage"}</h2><span class="speicher"></span><div class="rechts">${jahrWahl}</div></div>
      <p class="hinweis" style="margin-top:-6px">${ft ? "Angehakte Feiertage haben kein Soll; die ausfallenden Stunden gelten als bezahlt (im Monatsbeleg „Feiertage bezahlt“). Wer an einem Feiertag arbeitet, bekommt den Feiertagszuschlag aus dem Sollstundenplan. Ohne Änderung gelten die Feiertage in Baden-Württemberg."
        : "Arbeitsfreie Tage sind Betriebsruhetage ohne Bezahlung: kein Soll, also kein Minus im Arbeitszeitkonto, aber auch keine bezahlten Stunden. Ist derselbe Tag auch als bezahlter Feiertag angehakt, gilt der Feiertag."}
      Die Einstellung gilt für alle Tage, auch rückwirkend; sie ändert deshalb auch die Überstundenkonten vergangener Monate.</p>
      ${katTabelle(ft ? d.feiertage : d.frei, ft ? "feiertage_wahl" : "frei_wahl", ft ? "Feiertag" : "arbeitsfrei")}
      <h3 style="margin-top:18px">Weitere Feiertage und arbeitsfreie Tage</h3>
      <table class="liste" id="azEig"><tr><th>Bezeichnung</th><th>Datum (TT.MM)</th><th>Art</th><th></th></tr>
        ${eigene.map((x, i) => `<tr><td><input data-ei="${i}" data-ek="name" value="${esc(x.name || "")}" style="width:100%;min-width:200px"></td>
          <td><input data-ei="${i}" data-ek="datum" value="${esc(x.datum || "")}" placeholder="z. B. 15.08" style="width:90px"></td>
          <td><select data-ei="${i}" data-ek="art"><option value="feiertag">Feiertag (bezahlt)</option><option value="frei" ${x.art === "frei" ? "selected" : ""}>arbeitsfrei (unbezahlt)</option></select></td>
          <td><button class="btn rot" data-edel="${i}">✕</button></td></tr>`).join("")}</table>
      <button class="btn" id="azEigNeu" style="margin-top:6px">+ Tag</button>
      <h3 style="margin-top:18px">Ergebnis ${jahr}</h3>
      <div class="hinweis">${d.vorschau.map(v => `${wtag(v.datum)} ${datum(v.datum).slice(0, 6)} ${esc(v.name)}${v.art === "frei" ? " (arbeitsfrei)" : ""}`).join(" · ") || "keine"}</div>`;
    $$("[data-kat]", z).forEach(c => c.onchange = () => {
      const wahl = Object.fromEntries($$(`[data-kat="${c.dataset.kat}"]`, z).map(x => [x.value, x.checked]));
      speichern({[c.dataset.kat]: wahl});
    });
    $$("[data-ei]", z).forEach(el => el.onchange = () => { eigene[+el.dataset.ei][el.dataset.ek] = el.value.trim(); speichern({tage_eigene: eigene}); });
    $$("[data-edel]", z).forEach(b => b.onclick = () => { eigene.splice(+b.dataset.edel, 1); speichern({tage_eigene: eigene}); });
    $("#azEigNeu").onclick = () => { eigene.push({name: "", datum: "", art: "feiertag"}); speichern({tage_eigene: eigene}); };
    $("#azJahr").onchange = e => { arbeitszeitVorgabe.jahr = +e.target.value; arbeitszeitVorgabe(z, sub); };
    return;
  }
  // Sollstundenpläne
  const P = (E.sollplaene || []).map(p => JSON.parse(JSON.stringify(p)));
  const ZA = d.zuschlag_arten, WT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
  let aktiv = Math.min(arbeitszeitVorgabe.plan || 0, Math.max(0, P.length - 1));
  const zeichnen = () => {
    const p = P[aktiv];
    z.innerHTML = `<div class="titel"><h2>Sollstundenpläne</h2><span class="speicher"></span></div>
      <p class="hinweis" style="margin-top:-6px">Ein Plan legt die Sollstunden je Wochentag und die Zuschläge fest. Im Mitarbeiter wird er im Arbeitszeitmodell gewählt; ändert sich der Plan, übernehmen alle Mitarbeiter mit diesem Plan die neuen Sollstunden. Der Monatsbeleg weist die zuschlagspflichtigen Stunden je Art aus.</p>
      <div style="display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap">
      <div class="kachel" style="min-width:220px;flex:0 0 auto">${P.map((x, i) => `<div><a href="#" data-pl="${i}" style="${i === aktiv ? "font-weight:700" : ""}">${esc(x.name)}</a> <span class="hinweis">${zahlDE(x.tage.reduce((s, t) => s + t, 0), 2)} h · ${x.regelung}</span></div>`).join("") || `<div class="hinweis">Noch kein Plan.</div>`}
        <button class="btn prim" id="plNeu" style="margin-top:8px">+ Sollstundenplan</button></div>
      ${p ? `<div style="flex:1;min-width:420px"><div class="form" style="grid-template-columns:1fr">
        ${zeile("Bezeichnung", `<input data-pf="name" value="${esc(p.name)}">`)}
        ${zeile("Arbeitszeitregelung", `<div class="radio"><label><input type="radio" name="plR" value="fix" ${p.regelung === "fix" ? "checked" : ""}> Fix</label><label><input type="radio" name="plR" value="flexibel" ${p.regelung !== "fix" ? "checked" : ""}> Flexibel</label></div>
          <span class="hinweis" style="padding-top:5px">${p.regelung === "fix" ? "Jede Stunde über dem Wochensoll ist eine Überstunde mit Zuschlag (wird ausgezahlt)." : "Mehrstunden gehen ins Arbeitszeitkonto; Überstunden mit Zuschlag erst über der Höchstarbeitszeit."}</span>`)}
        ${zeile("Sollstunden", `<table class="liste" style="width:auto"><tr>${WT.map(t => `<th class="r">${t}</th>`).join("")}<th class="r">Woche</th></tr>
          <tr>${p.tage.map((t, j) => `<td><input class="zahl" data-pt="${j}" value="${t ? n2(t, t % 1 ? 2 : 0) : ""}" style="width:50px"></td>`).join("")}<td class="r"><b>${zahlDE(p.tage.reduce((s, t) => s + t, 0), 2)} h</b></td></tr></table>`)}
        ${zeile("Höchstarbeitszeit Woche", `<input class="zahl klein" data-pf="max_woche" value="${p.max_woche ? n2(p.max_woche, 2) : ""}"> Std. <span class="hinweis" style="padding-top:5px">nur bei flexibel; leer = keine Überstunden aus der Woche</span>`)}
        ${zeile("Höchstarbeitszeit Tag", `<input class="zahl klein" data-pf="max_tag" value="${p.max_tag ? n2(p.max_tag, 2) : ""}"> Std. <span class="hinweis" style="padding-top:5px">nur bei flexibel; leer = nein</span>`)}
        <div class="sektion">Zuschläge</div>
        ${ZA.map(a => zeile(a.name, `<input class="zahl klein" data-pz="${a.k}" value="${n2(p.zuschlaege[a.k] ?? a.vorgabe, 0)}"> %`)).join("")}
      </div>
      <p class="hinweis">Jede Stunde fällt in höchstens eine Zuschlagsart: Feiertag vor Sonntag vor 24.12.; Überstunden zählen nur an den übrigen Tagen. „Feiertag ist arbeitsfreier Tag“ = Feiertag an einem Wochentag ohne Sollstunden (z. B. Samstag).</p>
      <button class="btn rot" id="plDel">Plan löschen</button></div>` : ""}</div>`;
    const sp = () => speichern({sollplaene: P}, false).then(() => { if (!P.every(x => x.id)) arbeitszeitVorgabe(z, sub); });
    $$("[data-pl]", z).forEach(a => a.onclick = e => { e.preventDefault(); aktiv = arbeitszeitVorgabe.plan = +a.dataset.pl; zeichnen(); });
    $("#plNeu").onclick = () => { P.push({name: "Neuer Plan", regelung: "flexibel", tage: [8, 8, 8, 8, 8, 0, 0], max_woche: 0, max_tag: 0, zuschlaege: Object.fromEntries(ZA.map(a => [a.k, a.vorgabe]))}); aktiv = arbeitszeitVorgabe.plan = P.length - 1; speichern({sollplaene: P}); };
    if (!p) return;
    $$("[data-pf]", z).forEach(el => el.onchange = () => { p[el.dataset.pf] = el.dataset.pf === "name" ? el.value : zahlEin(el.value); sp(); zeichnen(); });
    $$("[name=plR]", z).forEach(r => r.onchange = () => { p.regelung = r.value; sp(); zeichnen(); });
    $$("[data-pt]", z).forEach(el => el.onchange = () => { p.tage[+el.dataset.pt] = zahlEin(el.value); sp(); zeichnen(); });
    $$("[data-pz]", z).forEach(el => el.onchange = () => { p.zuschlaege[el.dataset.pz] = zahlEin(el.value); sp(); });
    $("#plDel").onclick = async () => { if (!await frage(`Sollstundenplan „${p.name}“ löschen? Mitarbeiter mit diesem Plan behalten ihre Sollstunden, aber ohne Zuschläge.`)) return; P.splice(aktiv, 1); aktiv = arbeitszeitVorgabe.plan = 0; speichern({sollplaene: P}); };
  };
  zeichnen();
}
