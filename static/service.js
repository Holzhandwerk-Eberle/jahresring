"use strict";
// =====================================================================
//  Einstellungen › Service: Infos, Datensicherung, Rücksicherung, Relationencheck
// =====================================================================
const zeitDE = iso => iso ? `${datum(iso)} ${iso.slice(11, 16)} Uhr` : "";
const wochentag = iso => ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"][new Date(iso).getDay()];
function sichZeile(s, link) {
  const text = `${s.art === "voll" ? "Vollständig" : "Datenbank (automatisch)"} vom ${wochentag(s.zeit)}, ${zeitDE(s.zeit)}${s.version ? " · Version " + esc(s.version) : ""} · ${esc(s.groesse)} · `
    + (s.ok ? `<span style="color:var(--gruen)">OK</span>` : s.ok === null || s.ok === undefined ? `<span class="hinweis">${s.kennwort ? "Kennwort nötig" : "wird beim Rücksichern geprüft"}</span>` : `<span style="color:var(--rot)">beschädigt</span>`)
    + (s.verschluesselt ? " · 🔒 verschlüsselt" : "") + (s.notiz ? ` · <i>${esc(s.notiz)}</i>` : "");
  return link && s.ok !== false ? `<a href="#" data-rueck="${esc(s.name)}" data-ort="${esc(s.ort || "")}" data-kennwort="${s.kennwort ? 1 : ""}">▸ ${text}</a>` : text;
}
async function serviceSeite(z, sub) {
  if (sub === "infos") {
    const d = await api("service/infos");
    const block = (titel, o) => `<div class="sektion">${titel}</div>` + Object.entries(o).map(([k, v]) => zeile(k, `<span style="padding-top:5px;word-break:break-all">${esc(String(v))}</span>`)).join("");
    z.innerHTML = `<div class="titel"><h2>Informationen</h2><div class="rechts"><a class="btn" href="/hilfe/handbuch.html" target="jahresring-hilfe">Benutzerhandbuch</a><a class="btn" href="/hilfe/verfahrensdokumentation.html" target="_blank">Verfahrensdokumentation (GoBD)</a><a class="btn" href="/hilfe/datenschutz.html" target="_blank">Datenschutz (DSGVO)</a><a class="btn" href="/hilfe/installation.html" target="_blank">Installation</a><a class="btn" href="/hilfe/kalkulation.html" target="_blank">Kalkulationslogik</a></div></div><div class="form" style="grid-template-columns:1fr">
      ${block("Programm", d.programm)}${block("Netzwerk", d.netzwerk)}${block("Pfade", d.pfade)}${block("Speicherplatz", d.platz)}
      ${block("Datensätze", d.datensaetze)}
      <div class="sektion">Letzte Sicherung</div>${zeile("", `<span style="padding-top:5px">${d.letzte_sicherung ? `${d.letzte_sicherung.art === "voll" ? "vollständig" : "Datenbank"} am ${zeitDE(d.letzte_sicherung.zeit)}` : "noch keine"}</span>`)}</div>`;
    return;
  }
  if (sub === "projekte") return projektSicherungSeite(z);
  if (sub === "sicherung" || sub === "ruecksicherung") {
    const rueck = sub === "ruecksicherung";
    const d = await api("service/sicherungen" + (rueck ? "?extern=1" : ""));
    const kw = d.kennwort || {};
    z.innerHTML = rueck ? `<div class="titel"><h2>Rücksicherung</h2></div>
      <p>Bitte Datenstand zum <b style="color:var(--rot)">Rücksichern</b> auswählen:</p>
      <div class="sich-liste">${d.liste.map(s => `<div>${sichZeile(s, true)}</div>`).join("") || `<div class="leer">Noch keine Sicherungen vorhanden.</div>`}</div>
      ${(d.extern || []).length ? `<p style="margin-top:14px">Auf dem externen Sicherungsziel <code>${esc(d.ziel)}</code>:</p>
      <div class="sich-liste">${d.extern.map(s => `<div>${sichZeile(s, true)}</div>`).join("")}</div>` : ""}
      <p class="hinweis">Vor jeder Rücksicherung sichert das Programm automatisch den aktuellen Stand („vor Rücksicherung“) – eine Rücksicherung lässt sich also rückgängig machen. Eine vollständige Sicherung stellt Datenbank und Dateien (Anhänge, Bilder, Vorlagen, Logo, Unterschrift, Eingangsrechnungen) wieder her, eine automatische Sicherung nur die Datenbank. Danach ist eine neue Anmeldung nötig.</p>`
      : `<div class="titel"><h2>Datensicherung</h2><div class="rechts"><button class="btn prim" id="sichStart">Datensicherung starten</button></div></div>
      <p>Vorhandene Sicherungen:</p>
      <div class="sich-liste">${d.liste.map(s => `<div class="sich-z"><span>${sichZeile(s, false)}</span><a class="btn" href="/api/service/datei/${encodeURIComponent(s.name)}" title="Herunterladen, z. B. auf einen USB-Stick">⬇</a></div>`).join("") || `<div class="leer">Noch keine Sicherungen vorhanden.</div>`}</div>
      <p style="margin-top:14px">Die Datensicherung erstellt eine Kopie der Daten im Verzeichnis <code>${esc(d.pfad)}</code> auf diesem PC und <span style="color:var(--rot)">schützt nicht vor Computer-/Festplattendefekten.</span>
      Einmal täglich wird automatisch die Datenbank gesichert, auch wenn das Programm durchläuft (30 Tage, dazu je Monat eine für 12 Monate). „Datensicherung starten“ sichert zusätzlich alle Dateien (die letzten 15 vollständigen Sicherungen bleiben).</p>
      <div class="form" style="grid-template-columns:1fr">
        ${zeile("Zusätzlich kopieren nach", `<input id="sichZiel" value="${esc(d.ziel)}" placeholder="z. B. D:\\Sicherung oder \\\\NAS\\Sicherung">`)}
        ${zeile("", `<span class="hinweis">Ein anderes Laufwerk, ein USB-Stick, ein Netzlaufwerk oder ein Cloud-Ordner (dann mit Sicherungskennwort). Jede vollständige Sicherung und zusätzlich die tägliche Datenbanksicherung (Unterordner „Jahresring-Datenbank“, die letzten 30) werden dorthin kopiert.</span>`)}
        ${zeile("Sicherungskennwort", `<div class="spalte"><span style="padding-top:5px">${kw.gesetzt ? (kw.lesbar ? `<b style="color:var(--gruen)">🔒 gesetzt</b> – Kopien auf dem externen Sicherungsziel und heruntergeladene Sicherungen sind verschlüsselt (Endung .jrs).`
            : `<b style="color:var(--rot)">gesetzt, aber auf diesem PC nicht lesbar</b> – bitte neu setzen, sonst werden keine externen Kopien abgelegt.`)
            : `nicht gesetzt – Kopien auf dem externen Sicherungsziel sind unverschlüsselt lesbar.`}</span>
          <span style="margin-top:6px"><button class="btn" id="kwSetzen">${kw.gesetzt ? "Kennwort ändern" : "Kennwort setzen"}</button>
          ${kw.gesetzt && kw.lesbar ? `<button class="btn" id="kwPruefen">Kennwort prüfen</button> <button class="btn" id="kwWeg">Verschlüsselung abschalten</button>` : ""}</span>
          <span class="hinweis" style="margin-top:6px"><b>Wichtig:</b> Ohne dieses Kennwort lässt sich eine verschlüsselte Sicherung auf einem anderen PC nicht mehr öffnen – auch nicht vom Hersteller. Das Kennwort bitte aufschreiben und getrennt vom PC und vom Sicherungsmedium aufbewahren. Die Sicherungen im Ordner auf diesem PC bleiben unverschlüsselt (sie liegen neben der Datenbank).</span></div>`)}
      </div>`;
    if (rueck) {
      $$("[data-rueck]", z).forEach(a => a.onclick = async e => {
        e.preventDefault();
        const name = a.dataset.rueck, ort = a.dataset.ort || "", brauchtKw = !!a.dataset.kennwort;
        const g = await modal("Datenstand zurücksichern", `<p style="margin-top:0">${esc(a.textContent.replace("▸ ", ""))}</p>
          ${brauchtKw ? `<div class="zeile voll"><label>Sicherungskennwort</label><div><input name="kennwort" type="password" autocomplete="off" style="width:100%"></div></div>
          <p class="hinweis">Diese Sicherung wurde auf einem anderen PC oder mit einem anderen Kennwort verschlüsselt.</p>` : ""}
          <p>Alle Änderungen seit dieser Sicherung gehen verloren (der jetzige Stand wird vorher automatisch gesichert). Das Protokoll bleibt vollständig erhalten.</p>
          <div class="zeile voll"><label>Grund</label><div><input name="grund" placeholder="z. B. Festplattendefekt, versehentlich gelöschte Daten" style="width:100%"></div></div>
          <p class="hinweis">Der Grund wird im unveränderbaren Protokoll festgehalten${E._echtbetrieb ? " und ist im Echtbetrieb Pflicht" : ""}.</p>`, "Zurücksichern");
        if (!g) return;
        a.textContent = "wird zurückgesichert …";
        try {
          const r = await api("service/ruecksichern", {method: "POST", body: {name, ort, grund: g.grund, kennwort: g.kennwort || ""}});
          await frage(`Rücksicherung abgeschlossen.${r.dateien ? `\n\n${r.dateien} Dateien wiederhergestellt.` : ""}\n\nDer vorherige Stand liegt als „${r.vorher}“ in den Sicherungen.`, {titel: "Fertig", ok: "Neu laden"});
          location.hash = "#/start"; location.reload();
        } catch (x) { toast(x.message, true); serviceSeite(z, sub); }
      });
    } else {
      $("#sichStart").onclick = async () => {
        const b = $("#sichStart"); b.disabled = true; b.textContent = "sichert …";
        try {
          const r = await api("service/sicherung", {method: "POST"});
          toast(`Sicherung erstellt (${r.groesse})` + (r.extern ? (r.extern.startsWith("FEHLER") ? ` · Kopie fehlgeschlagen: ${r.extern}` : ` · kopiert nach ${r.extern}`) : ""), r.extern.startsWith("FEHLER"));
        } catch (x) { toast(x.message, true); }
        try { E = await api("einstellungen"); } catch (x) { /* Hinweis auf der Startseite aktualisieren */ }
        serviceSeite(z, sub);
      };
      const kwDialog = async () => {
        const g = await modal(kw.gesetzt ? "Sicherungskennwort ändern" : "Sicherungskennwort setzen", `
          ${kw.gesetzt && kw.lesbar ? `<div class="zeile voll"><label>Bisheriges Kennwort</label><div><input name="alt" type="password" autocomplete="off" style="width:100%"></div></div>` : ""}
          <div class="zeile voll"><label>Neues Kennwort</label><div><input name="kennwort" type="password" autocomplete="new-password" style="width:100%"></div></div>
          <div class="zeile voll"><label>Wiederholen</label><div><input name="kennwort2" type="password" autocomplete="new-password" style="width:100%"></div></div>
          <p class="hinweis">Mindestens 10 Zeichen, am besten ein Satz aus mehreren Wörtern. Bitte aufschreiben und getrennt vom PC aufbewahren: Ohne das Kennwort ist eine verschlüsselte Sicherung auf einem anderen PC verloren. Ältere Sicherungen bleiben, wie sie sind (mit dem früheren Kennwort bzw. unverschlüsselt).</p>`, "Speichern");
        if (!g) return;
        try { await api("service/kennwort", {method: "POST", body: g}); toast("Sicherungskennwort gespeichert – externe Kopien werden ab jetzt verschlüsselt"); serviceSeite(z, sub); }
        catch (x) { toast(x.message, true); }
      };
      $("#kwSetzen").onclick = kwDialog;
      if ($("#kwPruefen")) $("#kwPruefen").onclick = async () => {
        const g = await modal("Sicherungskennwort prüfen", `<div class="zeile voll"><label>Kennwort</label><div><input name="kennwort" type="password" autocomplete="off" style="width:100%"></div></div>
          <p class="hinweis">Prüft, ob das notierte Kennwort zu den verschlüsselten Sicherungen passt.</p>`, "Prüfen");
        if (!g) return;
        try { const r = await api("service/kennwort", {method: "POST", body: {pruefen: true, kennwort: g.kennwort}}); toast(r.stimmt ? "✓ Das Kennwort stimmt." : "Das Kennwort stimmt nicht.", !r.stimmt); }
        catch (x) { toast(x.message, true); }
      };
      if ($("#kwWeg")) $("#kwWeg").onclick = async () => {
        const g = await modal("Verschlüsselung abschalten", `<div class="zeile voll"><label>Bisheriges Kennwort</label><div><input name="alt" type="password" autocomplete="off" style="width:100%"></div></div>
          <p class="hinweis">Neue Kopien auf dem externen Sicherungsziel werden danach wieder unverschlüsselt abgelegt. Bereits verschlüsselte Sicherungen bleiben verschlüsselt und brauchen weiterhin das Kennwort.</p>`, "Abschalten");
        if (!g) return;
        try { await api("service/kennwort", {method: "POST", body: {entfernen: true, alt: g.alt}}); toast("Verschlüsselung abgeschaltet"); serviceSeite(z, sub); }
        catch (x) { toast(x.message, true); }
      };
      $("#sichZiel").onchange = async e => { E = await api("einstellungen", {method: "PUT", body: {sicherung_ziel: e.target.value.trim()}}); toast("Gespeichert"); };
    }
    return;
  }
  if (sub === "loeschen") {
    // Jährliche Löschprüfung (Datenschutz): wer darf nach Ablauf der Aufbewahrungsfristen anonymisiert werden?
    z.innerHTML = `<div class="titel"><h2>Löschprüfung</h2></div>
      <p>Zeigt Kunden, Lieferanten und ausgeschiedene Mitarbeiter, deren Aufbewahrungsfristen abgelaufen sind, sowie Interessenten und Lieferanten ohne Belege, die seit drei Jahren unverändert sind. Gelöscht oder anonymisiert wird hier nichts – ein Klick öffnet den Datensatz, dort steht „Anonymisieren …“ bzw. „Löschen“.</p>
      <div id="lpErg"><div class="leer">wird geprüft …</div></div>`;
    try {
      const d = await api("datenschutz/faellig"), ka = d.kontoauszuege || {auszuege: 0, grenze: ""};
      const tab = (titel, liste, link, spalte) => `<div class="sektion" style="margin-top:14px">${titel} <span class="hinweis" style="font-weight:400">· ${liste.length}</span></div>` + (liste.length
        ? `<table class="liste"><tr><th style="width:110px">Nummer</th><th>Name</th><th style="width:150px">${spalte}</th><th style="width:170px">Frist abgelaufen am</th></tr>
          ${liste.map(x => `<tr class="klick" data-hash="${link(x)}"><td><a href="${link(x)}">${esc(String(x.nummer))}</a></td><td>${esc(x.name)}${x.ohne_belege ? ` <span class="hinweis">ohne Belege – kann gelöscht werden</span>` : ""}</td>
            <td>${datum(x.letzter)}</td><td>${x.frist_ende ? datum(x.frist_ende) : "–"}</td></tr>`).join("")}</table>`
        : `<div class="hinweis">Niemand fällig.</div>`);
      $("#lpErg").innerHTML = (d.anzahl ? "" : `<div class="kachel" style="border-left:4px solid var(--gruen)">Derzeit ist nichts zu löschen oder zu anonymisieren.</div>`)
        + tab("Kunden", d.kunden, x => `#/kunde/${x.id}`, "letzter Beleg") + tab("Lieferanten", d.lieferanten, x => `#/lieferant/${x.id}`, "letzter Beleg")
        + tab("Ausgeschiedene Mitarbeiter", d.mitarbeiter, x => `#/personal/ma/${x.id}`, "Austritt")
        + `<div class="sektion" style="margin-top:14px">Kontoauszüge</div>` + (ka.auszuege
          ? `<div class="kachel" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><div style="flex:1 1 320px">${ka.auszuege} ${ka.auszuege === 1 ? "eingelesener Kontoauszug" : "eingelesene Kontoauszüge"} bis ${datum(ka.bis)}${ka.umsaetze ? ` mit ${ka.umsaetze} Umsätzen, in denen noch Name oder Verwendungszweck stehen` : ""}: Die Aufbewahrungsfrist ist abgelaufen.
              <div class="hinweis">Gelöscht werden die abgelegten Auszugsdateien; in den Umsätzen werden Name, Verwendungszweck und Gegenkonto entfernt. Beträge, Buchungstage und die Zuordnung zu Rechnungen bleiben.</div></div>
              <button class="btn rot" id="lpKonto">Alte Kontoauszüge löschen …</button></div>`
          : `<div class="hinweis">Kein Kontoauszug, dessen Frist abgelaufen ist (Auszüge bis ${datum(ka.grenze)} wären es).</div>`)
        + `<p class="hinweis" style="margin-top:14px">Fristen: Rechnungen und Kontoauszüge ${d.frist_rechnung_jahre || 10} Jahre (einstellbar unter Einstellungen › Kunden &amp; Aufträge, zulässig sind 8 bis 10), Angebote und Geschäftsbriefe 6 Jahre, Lohn- und Zeitunterlagen 10 Jahre, jeweils ab Ende des Kalenderjahres; ein Expositionsverzeichnis 40 Jahre. Empfohlen: einmal im Jahr prüfen und in der Datenschutz-Dokumentation vermerken.</p>`;
      if ($("#lpKonto")) $("#lpKonto").onclick = async () => {
        if (!await frage(`${ka.auszuege} ${ka.auszuege === 1 ? "Kontoauszug" : "Kontoauszüge"} bis ${datum(ka.bis)} endgültig löschen? Die Auszugsdateien werden entfernt, in den Umsätzen verschwinden Name, Verwendungszweck und Gegenkonto. Das lässt sich nicht rückgängig machen; der Vorgang steht im Protokoll.`, {ok: "Löschen"})) return;
        try { const r = await api("datenschutz/kontoauszuege", {method: "POST", body: {}}); toast(`${r.dateien} Dateien gelöscht, ${r.umsaetze} Umsätze bereinigt`); serviceSeite(z, "loeschen"); }
        catch (x) { toast(x.message, true); }
      };
    } catch (e) { $("#lpErg").innerHTML = `<div class="leer">${esc(e.message)}</div>`; }
    return;
  }
  if (sub === "relationen") {
    z.innerHTML = `<div class="titel"><h2>Relationencheck</h2></div>
      <p>Check des Datenstands auf fehlende Relationen (verwaiste Datensätze/Dateien).</p>
      <p><a href="#" id="relStart">▸ Relationencheck starten</a></p><div id="relErg"></div>
      <div class="kachel" style="margin-top:18px"><b>Datenbank optimieren</b>
        <p style="margin:6px 0">Prüft die Datenbank (integrity_check), frischt die Statistik für die Suche auf und verdichtet die Datei. Lohnt sich vor allem nach großen Löschaktionen; die Daten selbst bleiben unverändert. Dauert bei großen Beständen einige Sekunden, andere Geräte warten so lange.</p>
        <button class="btn" id="dbOpt">Datenbank optimieren</button> <span id="dbOptErg" class="hinweis"></span></div>`;
    $("#dbOpt").onclick = async e => {
      e.target.disabled = true; $("#dbOptErg").textContent = "läuft …";
      try { const r = await api("service/optimieren", {method: "POST"}); $("#dbOptErg").textContent = `✓ geprüft und optimiert · ${n2(r.vorher / 1e6, 1)} MB → ${n2(r.nachher / 1e6, 1)} MB`; }
      catch (x) { $("#dbOptErg").textContent = ""; toast(x.message, true); }
      e.target.disabled = false;
    };
    $("#relStart").onclick = async e => {
      e.preventDefault();
      $("#relErg").innerHTML = `<div class="hinweis">prüft …</div>`;
      const d = await api("service/relationen");
      $("#relErg").innerHTML = `<div class="kachel" style="margin-bottom:10px;border-left:4px solid ${d.probleme ? "var(--rot)" : "var(--gruen)"}">
          ${d.probleme ? `<b>${d.probleme} Auffälligkeit${d.probleme > 1 ? "en" : ""} gefunden</b> – Details unten. Am Datenbestand wird nichts verändert.` : `<b>Alles in Ordnung</b> – keine verwaisten Datensätze oder Dateien.`}</div>
        <table class="liste"><tr><th>Prüfung</th><th class="r">Anzahl</th><th>Beispiele</th></tr>
        ${d.pruefungen.map(p => `<tr><td>${esc(p.text)}</td><td class="r">${p.anzahl == null ? "?" : p.anzahl ? `<b style="color:var(--rot)">${p.anzahl}</b>` : `<span style="color:var(--gruen)">0</span>`}</td>
          <td class="hinweis">${esc(p.fehler || p.beispiele.join(" · "))}</td></tr>`).join("")}</table>
        ${d.pruefungen.some(p => p.loesbar && p.anzahl) ? `<div class="kachel" style="margin-top:10px"><b>Verwaiste Verweise lösen</b>
          <p style="margin:6px 0">Bei ${d.pruefungen.filter(p => p.loesbar && p.anzahl).map(p => "„" + esc(p.text) + "“").join(", ")} zeigt ein Datensatz auf etwas, das es nicht mehr gibt. „Verweise lösen“ leert nur diese Verknüpfung; die Datensätze selbst (z. B. die Zeitbuchung) bleiben erhalten. Der Vorgang steht im Protokoll.</p>
          <button class="btn" id="relLoesen">Verweise lösen</button></div>` : ""}`;
      if ($("#relLoesen")) $("#relLoesen").onclick = async () => {
        try { const r = await api("service/relationen/loesen", {method: "POST"}); toast(Object.values(r.geloest).reduce((s, n) => s + n, 0) + " Verweis(e) gelöst"); $("#relStart").click(); }
        catch (x) { toast(x.message, true); }
      };
    };
  }
  if (sub === "export") {
    const d = await api("service/exporte");
    const dv = await api("service/datev");
    const h = new Date(), j = h.getFullYear(), m = h.getMonth();
    const iso = x => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
    const vormonat = [iso(new Date(j, m - 1, 1)), iso(new Date(j, m, 0))];
    const kb = n => n > 1048576 ? (n / 1048576).toFixed(1).replace(".", ",") + " MB" : Math.max(1, Math.round(n / 1024)) + " KB";
    z.innerHTML = `<div class="titel"><h2>Export für Buchführung und Betriebsprüfung</h2></div>
      ${d.luecken.length ? `<div class="kachel" style="border-left:4px solid var(--rot);margin-bottom:10px"><b>Lücken im Rechnungsnummernkreis ${j}:</b> ${d.luecken.map(esc).join(", ")}</div>` : ""}
      <div class="sektion">Zeitraum</div>
      <div class="form" style="grid-template-columns:1fr">
        ${zeile("Von / bis", `<input type="date" id="exVon" value="${vormonat[0]}"><input type="date" id="exBis" value="${vormonat[1]}">
          <span style="display:flex;gap:6px;flex-wrap:wrap;padding-top:2px"><button class="btn" data-zr="vm">Vormonat</button><button class="btn" data-zr="q">letztes Quartal</button><button class="btn" data-zr="vj">Vorjahr</button><button class="btn" data-zr="j">laufendes Jahr</button></span>`)}
      </div>
      <div class="ex-karten" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;margin-top:12px">
        <div class="kachel"><h3 style="margin-top:0">Belegpaket (Buchführung, Archiv, Steuerberater)</h3>
          <p>Alle festgeschriebenen Ausgangsrechnungen (PDF mit ZUGFeRD-Daten, ggf. XRechnung), alle Eingangsrechnungen im Originalformat und Listen als Excel-taugliche CSV:
          Rechnungsausgangsliste, Eingangsrechnungen, Zahlungseingänge. Dazu eine Prüfung, ob die Rechnungsnummern lückenlos sind.</p>
          <p class="hinweis">Zum Abgleich mit Dokumentenarchiv und Buchhaltung bzw. zur Weitergabe an die Steuerberatung.</p>
          <button class="btn prim" id="exBp">Belegpaket erstellen</button></div>
        <div class="kachel"><h3 style="margin-top:0">Datenträgerüberlassung für die Betriebsprüfung</h3>
          <p>Steuerlich relevante Daten nach § 147 Abs. 6 AO im „Beschreibungsstandard für die Datenträgerüberlassung“ (index.xml + CSV, lesbar mit der Prüfsoftware IDEA):
          Ausgangsrechnungen mit Positionen, Abschlagsverrechnung, offene Posten, Zahlungseingänge, Mahnungen, Eingangsrechnungen, Kunden, Lieferanten und das Protokoll – dazu alle Belegdateien.</p>
          <p class="hinweis">Nur auf Anforderung des Prüfers erstellen und nur den angeforderten Zeitraum übergeben.</p>
          <button class="btn prim" id="exPr">Datenträger erstellen</button></div>
        <div class="kachel"><h3 style="margin-top:0">DATEV-Buchungsstapel für die Steuerberatung</h3>
          <p>Ausgangs- und Eingangsrechnungen des Zeitraums als Buchungsstapel im DATEV-Format (zum Einlesen in DATEV Rechnungswesen), dazu die Belegdateien.
          Bankumsätze mit ihrer Zuordnung auf Wunsch (DATEV-Einstellungen), Löhne nicht.</p>
          <p class="hinweis">${dv.berater && dv.mandant ? `Berater ${esc(dv.berater)} · Mandant ${esc(dv.mandant)} · SKR ${esc(dv.skr)}` : "Zuerst unten Berater- und Mandantennummer eintragen."}</p>
          <button class="btn prim" id="exDv">DATEV-Stapel erstellen</button></div>
      </div>
      <details class="kachel" style="margin-top:12px" ${dv.berater && dv.mandant ? "" : "open"}><summary><b>DATEV-Einstellungen</b> <span class="hinweis">– mit der Steuerberatung abstimmen</span></summary>
        <div class="form" style="grid-template-columns:1fr;margin-top:8px">
          ${zeile("Beraternummer", `<input id="dvB" value="${esc(dv.berater)}" inputmode="numeric" style="max-width:140px"> Mandantennummer <input id="dvM" value="${esc(dv.mandant)}" inputmode="numeric" style="max-width:120px">`)}
          ${zeile("Kontenrahmen", `<select id="dvS"><option value="03" ${dv.skr === "03" ? "selected" : ""}>SKR 03</option><option value="04" ${dv.skr === "04" ? "selected" : ""}>SKR 04</option></select>
            Wirtschaftsjahr beginnt im Monat <input id="dvW" type="number" min="1" max="12" value="${dv.wj_beginn}" style="width:60px"> Sachkontenlänge <input id="dvL" type="number" min="4" max="8" value="${dv.sachkontenlaenge}" style="width:60px">`)}
          ${zeile("Enthalten", `<label><input type="checkbox" id="dvA" ${dv.ausgang ? "checked" : ""}> Ausgangsrechnungen</label> <label><input type="checkbox" id="dvE" ${dv.eingang ? "checked" : ""}> Eingangsrechnungen</label>
            <label title="Zugeordnete Kontoumsätze: Bank an Debitor/Kreditor bzw. an das Sachkonto. Nur, wenn die Kanzlei die Bankumsätze nicht selbst abruft."><input type="checkbox" id="dvK" ${dv.bankumsaetze ? "checked" : ""}> Bankumsätze</label>`)}
        </div>
        <table class="liste" style="margin-top:8px"><tr><th>Konto für</th><th>Kontonummer</th><th class="hinweis">Vorgabe SKR ${esc(dv.skr)}</th></tr>
          ${Object.keys(dv.texte).map(k => `<tr><td>${esc(dv.texte[k])}</td><td><input data-dvk="${k}" value="${dv.konten[k]}" inputmode="numeric" style="width:110px"></td><td class="hinweis">${dv.standard[k]}</td></tr>`).join("")}</table>
        <p class="hinweis">Abweichende Aufwandskonten für einzelne Lieferanten (z. B. Fremdleistungen, Werkzeuge, Bürobedarf) beim Lieferanten unter „DATEV-Aufwandskonto“ eintragen.
          Die Vorgaben sind übliche Automatikkonten; maßgeblich ist der Kontenplan der Kanzlei.</p>
        <button class="btn" id="dvSp">DATEV-Einstellungen speichern</button></details>
      <details class="kachel" style="margin-top:12px" id="kontenplan"><summary><b>Kontenplan (SKR ${esc(dv.skr)})</b> <span class="hinweis">– Sachkonten für Kontoumsätze und Lieferanten</span></summary>
        <div id="kpInhalt" style="margin-top:8px"></div></details>
      <div id="exErg" style="margin-top:12px"></div>
      <div class="sektion" style="margin-top:16px">Erstellte Exporte</div>
      ${d.liste.length ? `<table class="liste"><tr><th>Datei</th><th>erstellt</th><th class="r">Größe</th></tr>
        ${d.liste.map(x => `<tr><td><a href="/api/service/export/${encodeURIComponent(x.datei)}">⬇ ${esc(x.datei)}</a></td><td>${datum(x.zeit.slice(0, 10))} ${esc(x.zeit.slice(11, 16))}</td><td class="r">${kb(x.groesse)}</td></tr>`).join("")}</table>`
        : `<p class="hinweis">Noch keine Exporte. Sie liegen im Datenordner unter „exporte“.</p>`}`;
    $$("[data-zr]", z).forEach(b => b.onclick = () => {
      let v, bis;
      if (b.dataset.zr === "vm") [v, bis] = vormonat;
      if (b.dataset.zr === "q") { const q = Math.floor(m / 3) - 1, qj = q < 0 ? j - 1 : j, qq = (q + 4) % 4; v = iso(new Date(qj, qq * 3, 1)); bis = iso(new Date(qj, qq * 3 + 3, 0)); }
      if (b.dataset.zr === "vj") { v = `${j - 1}-01-01`; bis = `${j - 1}-12-31`; }
      if (b.dataset.zr === "j") { v = `${j}-01-01`; bis = iso(h); }
      $("#exVon").value = v; $("#exBis").value = bis;
    });
    const los = async (art, btn) => {
      const alt = btn.textContent; btn.disabled = true; btn.textContent = "wird erstellt …";
      try {
        const r = await api("service/" + art, {method: "POST", body: {von: $("#exVon").value, bis: $("#exBis").value}});
        const warn = art === "belegpaket" ? [r.luecken.length ? `Fehlende Rechnungsnummern: ${r.luecken.join(", ")}` : "",
          r.ohne_pdf.length ? `Ohne Archiv-PDF: ${r.ohne_pdf.join(", ")}` : "", r.ohne_datei.length ? `Zahlungsaufträge ohne Originaldatei (Papierbeleg?): ${r.ohne_datei.length}` : ""].filter(Boolean) : [];
        await serviceSeite(z, sub);
        $("#exErg").innerHTML = `<div class="kachel" style="border-left:4px solid var(--gruen)"><b>Erstellt:</b> <a href="/api/service/export/${encodeURIComponent(r.datei)}">⬇ ${esc(r.datei)}</a> (${kb(r.groesse)})<br>
          ${art === "belegpaket" ? `${r.rechnungen} Ausgangsrechnungen · ${r.eingangsrechnungen} Eingangsrechnungen · ${r.zahlungseingaenge} Zahlungseingänge`
            : Object.entries(r.tabellen).map(([k, n]) => `${esc(k)} ${n}`).join(" · ")}
          ${warn.map(w => `<div style="color:var(--rot)">${esc(w)}</div>`).join("")}</div>`;
      } catch (e) { toast(e.message, true); btn.disabled = false; btn.textContent = alt; }
    };
    $("#exBp").onclick = e => los("belegpaket", e.target);
    $("#exPr").onclick = e => los("pruefer", e.target);
    $("#exDv").onclick = async e => {
      const btn = e.target, alt = btn.textContent; btn.disabled = true; btn.textContent = "wird erstellt …";
      try {
        const r = await api("service/datev", {method: "POST", body: {von: $("#exVon").value, bis: $("#exBis").value}});
        await serviceSeite(z, sub);
        $("#exErg").innerHTML = `<div class="kachel" style="border-left:4px solid var(--gruen)"><b>Erstellt:</b> <a href="/api/service/export/${encodeURIComponent(r.datei)}">⬇ ${esc(r.datei)}</a> (${kb(r.groesse)})<br>
          ${r.buchungen} Buchungen · Ausgangsrechnungen ${eur(r.ausgang)} · Eingangsrechnungen ${eur(r.eingang)}${r.warnungen.map(w => `<div style="color:var(--rot)">${esc(w)}</div>`).join("")}</div>`;
      } catch (x) { toast(x.message, true); btn.disabled = false; btn.textContent = alt; }
    };
    const kpZeigen = async () => {
      const kp = await api("sachkonten?alle=1");
      const stOpt = v => Object.entries(kp.steuer).map(([k, t]) => `<option value="${k}" ${k === v ? "selected" : ""}>${esc(t)}</option>`).join("");
      const artOpt = v => Object.entries(kp.arten).map(([k, t]) => `<option value="${k}" ${k === v ? "selected" : ""}>${esc(t)}</option>`).join("");
      $("#kpInhalt").innerHTML = `<p class="hinweis" style="margin-top:0">Vorbelegt mit den üblichen Konten eines Handwerksbetriebs. Eigene Konten unten anlegen; Konten, die gebraucht wurden, werden beim Entfernen nur ausgeblendet.
          „Steuer“ bestimmt im DATEV-Export den BU-Schlüssel (Automatikkonten ohne). Mit der Kanzlei abstimmen.</p>
        <table class="liste"><tr><th>Nummer</th><th>Bezeichnung</th><th>Art</th><th>Steuer</th><th>aktiv</th><th></th></tr>
        ${kp.konten.map(k => `<tr style="${k.aktiv ? "" : "opacity:.5"}"><td><b>${String(k.nummer).padStart(4, "0")}</b></td><td><input data-kp="${k.id}" data-kk="bezeichnung" value="${esc(k.bezeichnung)}" style="width:100%;min-width:220px"></td>
          <td><select data-kp="${k.id}" data-kk="art">${artOpt(k.art)}</select></td><td><select data-kp="${k.id}" data-kk="steuer">${stOpt(k.steuer)}</select></td>
          <td><input type="checkbox" data-kp="${k.id}" data-kk="aktiv" ${k.aktiv ? "checked" : ""}></td><td>${k.eigen ? `<button class="btn" data-kpweg="${k.id}" title="Entfernen">✕</button>` : `<span class="hinweis">Vorgabe</span>`}</td></tr>`).join("")}
        <tr><td><input id="kpNr" placeholder="Nr." inputmode="numeric" style="width:80px"></td><td><input id="kpBez" placeholder="Bezeichnung des neuen Kontos" style="width:100%"></td>
          <td><select id="kpArt">${artOpt("aufwand")}</select></td><td><select id="kpSt">${stOpt("")}</select></td><td></td><td><button class="btn prim" id="kpNeu">＋ Anlegen</button></td></tr></table>`;
      $$("[data-kp]").forEach(el => el.onchange = async () => {
        try { await api("sachkonten/" + el.dataset.kp, {method: "PUT", body: {[el.dataset.kk]: el.type === "checkbox" ? el.checked : el.value}}); toast("Gespeichert"); if (el.type === "checkbox") kpZeigen(); }
        catch (x) { toast(x.message, true); }
      });
      $$("[data-kpweg]").forEach(b => b.onclick = async () => { const r = await api("sachkonten/" + b.dataset.kpweg, {method: "DELETE"}); toast(r.ausgeblendet ? "Konto wurde verwendet und ist jetzt ausgeblendet" : "Konto entfernt"); kpZeigen(); });
      $("#kpNeu").onclick = async () => {
        try { const k = await api("sachkonten", {method: "POST", body: {nummer: $("#kpNr").value, bezeichnung: $("#kpBez").value, art: $("#kpArt").value, steuer: $("#kpSt").value}}); toast(`Konto ${k.nummer} angelegt`); kpZeigen(); }
        catch (x) { toast(x.message, true); }
      };
    };
    $("#kontenplan").ontoggle = () => { if ($("#kontenplan").open && !$("#kpInhalt").innerHTML) kpZeigen(); };
    let kpOffen = false;
    try { kpOffen = !!sessionStorage.getItem("kpOffen"); sessionStorage.removeItem("kpOffen"); } catch (e) { /* ohne Speicher: zugeklappt */ }
    if (kpOffen) { $("#kontenplan").open = true; $("#kontenplan").scrollIntoView(); }
    $("#dvSp").onclick = async () => {
      const konten = {};
      $$("[data-dvk]").forEach(i => { konten[i.dataset.dvk] = i.value.trim(); });
      const skrNeu = $("#dvS").value !== dv.skr;
      await api("einstellungen", {method: "PUT", body: {datev: {berater: $("#dvB").value.trim(), mandant: $("#dvM").value.trim(), skr: $("#dvS").value,
        wj_beginn: +$("#dvW").value || 1, sachkontenlaenge: +$("#dvL").value || 4, ausgang: $("#dvA").checked, eingang: $("#dvE").checked, bankumsaetze: $("#dvK").checked,
        konten: skrNeu ? {} : Object.fromEntries(Object.entries(konten).filter(([k, v]) => String(v) !== String(dv.standard[k])))}}});
      toast(skrNeu ? "Gespeichert – Konten auf die Vorgaben des neuen Kontenrahmens gesetzt" : "DATEV-Einstellungen gespeichert"); serviceSeite(z, sub);
    };
    return;
  }
  if (sub === "protokoll") {
    const pf = serviceSeite.pf || (serviceSeite.pf = {art: "", q: "", von: "", bis: ""});
    const d = await api("service/protokoll?" + new URLSearchParams({...pf, ...(serviceSeite.pVoll ? {voll: "1"} : {})}));
    serviceSeite.pVoll = false;
    const p = d.pruefung;
    z.innerHTML = `<div class="titel"><h2>Protokoll</h2><div class="rechts"><a class="btn" href="/api/service/protokoll.csv">Export CSV</a></div></div>
      <div class="kachel" style="margin-bottom:12px;border-left:4px solid ${p.ok ? "var(--gruen)" : "var(--rot)"}">
        ${p.ok ? `<b>✓ Unverändert.</b> ${p.anzahl} Einträge, Hash-Kette in Datenbank und Journaldatei vollständig und übereinstimmend.`
               : `<b>Achtung – Unstimmigkeit im Protokoll:</b><br>${p.fehler.map(esc).join("<br>")}`}
        <div class="hinweis" style="margin-top:4px">${p.umfang === "neu" ? `Geprüft: die ${p.geprueft} neuen Einträge seit der vollständigen Prüfung vom ${datum(p.voll_zeit.slice(0, 10))} ${esc(p.voll_zeit.slice(11, 16))} (läuft bei jedem Programmstart im Hintergrund).` : "Vollständig geprüft (alle Einträge)."}
          <a href="#" id="prVoll">Jetzt vollständig prüfen</a></div>
        <div class="hinweis" style="margin-top:4px">Letzter Hash: <code>${esc(p.letzter_hash)}</code> · Journaldatei: ${esc(p.datei || "")}</div>
        ${d.belege ? `<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--linie)">${d.belege.ok
            ? `<b>✓ Festgeschriebene Rechnungen unverändert.</b> ${d.belege.geprueft} Rechnungen mit dem Protokoll verglichen (Nummer, Datum, Beträge${d.belege.mit_fingerabdruck ? `, davon ${d.belege.mit_fingerabdruck} auch im Inhalt` : ""}), ${d.belege.pdf_geprueft} Archiv-PDFs${d.belege.eingang_geprueft ? `, ${d.belege.eingang_geprueft} abgelegte Eingangsrechnungen` : ""}${d.belege.versandt_geprueft ? ` und ${d.belege.versandt_geprueft} versandte Fassungen von Angeboten und anderen Belegen` : ""} anhand ihres Hashs geprüft${d.belege.ohne_protokoll ? `, ${d.belege.ohne_protokoll} ältere ohne Protokolleintrag` : ""}.`
            : `<b style="color:var(--rot)">Achtung – Abweichung bei festgeschriebenen Rechnungen oder abgelegten Eingangsrechnungen:</b><br>${d.belege.fehler.map(esc).join("<br>")}`}
          <div class="hinweis">Stand ${datum(d.belege.zeit.slice(0, 10))} ${esc(d.belege.zeit.slice(11, 16))} · läuft bei jedem Programmstart und mit „Jetzt vollständig prüfen“</div></div>` : ""}
        <div class="hinweis">${d.echtbetrieb ? `Echtbetrieb seit ${datum(d.echtbetrieb.seit.slice(0, 10))} ${esc(d.echtbetrieb.seit.slice(11, 16))}` : "Echtbetrieb noch nicht gestartet (Service › Testdaten löschen)"}</div></div>
      <p class="hinweis" style="margin-top:0">Hier stehen alle GoBD-relevanten Vorgänge: Festschreiben und Stornieren von Rechnungen, versandte Fassungen von Angeboten und anderen Belegen, gelöschte Belege,
        geänderte oder gelöschte Zahlungsaufträge, gelöschte Zahlungseingänge und Mahnungen, Nummernkreis-Änderungen, Änderungen an Stammdaten (Kunden, Lieferanten, Mitarbeiter) und Einstellungen,
        Benutzer und Rechte, Anmeldungen, Sicherungen, Rücksicherungen, Testdatenlöschung, Echtbetrieb und Programmversionen. Bei Stammdaten stehen Zahlungsbedingungen mit altem und neuem Wert da,
        Bankverbindungen verkürzt, Namen und Anschriften nur als Tatsache. Einträge können nicht geändert oder gelöscht werden; jeder Eintrag ist über einen SHA-256-Hash mit dem vorigen verkettet.</p>
      <div class="such" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
        <select id="prArt"><option value="">Alle Vorgänge</option>${Object.entries(d.arten).map(([k, l]) => `<option value="${k}" ${k === pf.art ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>
        <input type="date" id="prVon" value="${esc(pf.von)}"><input type="date" id="prBis" value="${esc(pf.bis)}">
        <input id="prQ" placeholder="Suchen …" value="${esc(pf.q)}" style="width:220px"></div>
      <table class="liste"><tr><th>Nr.</th><th>Zeit</th><th>Benutzer</th><th>Vorgang</th><th>Beschreibung</th><th>Version</th></tr>
        ${d.eintraege.map(e => `<tr><td>${e.nr}</td><td class="nw">${datum(e.zeit.slice(0, 10))} ${esc(e.zeit.slice(11, 16))}</td><td>${esc(e.benutzer)}</td><td class="nw">${esc(e.art_name)}</td>
          <td>${esc(e.text)}<div class="hinweis" title="${esc(e.hash)}">#${esc(e.hash.slice(0, 12))}…</div></td><td class="hinweis nw">${esc(e.version)}</td></tr>`).join("") || `<tr><td colspan="6" class="hinweis">Keine Einträge.</td></tr>`}</table>`;
    const neu = () => { pf.art = $("#prArt").value; pf.von = $("#prVon").value; pf.bis = $("#prBis").value; pf.q = $("#prQ").value.trim(); serviceSeite(z, sub); };
    $("#prArt").onchange = neu; $("#prVon").onchange = neu; $("#prBis").onchange = neu;
    $("#prVoll").onclick = e => { e.preventDefault(); serviceSeite.pVoll = true; serviceSeite(z, sub); };
    let t; $("#prQ").oninput = () => { clearTimeout(t); t = setTimeout(neu, 400); };
    return;
  }
  if (sub === "testdaten") {
    const d = await api("service/testdaten");
    const inhaber = !ICH || ICH.rechte.inhaber;
    if (d.echtbetrieb) {
      z.innerHTML = `<div class="titel"><h2>Testdaten löschen</h2></div>
        <div class="kachel" style="border-left:4px solid var(--gruen)"><b>Gesperrt – Echtbetrieb seit ${datum(d.echtbetrieb.seit.slice(0, 10))} um ${esc(d.echtbetrieb.seit.slice(11, 16))}</b> (gestartet von ${esc(d.echtbetrieb.von || "")}).<br>
        Im Echtbetrieb können keine Daten mehr gelöscht werden. Festgeschriebene Rechnungen werden storniert, nicht gelöscht. Die Sperre lässt sich nicht aufheben, auch nicht durch eine Rücksicherung.
        <br><a href="#/einstellungen/service/protokoll">Zum Protokoll ›</a></div>`;
      return;
    }
    z.innerHTML = `<div class="titel"><h2>Testdaten löschen</h2></div>
      <div class="kachel" style="border-left:4px solid var(--rot);margin-bottom:12px">
        Für den Start in den Echtbetrieb: Hier werden die Daten gelöscht, die beim Ausprobieren entstanden sind – auch festgeschriebene Rechnungen.
        <b>Im Echtbetrieb niemals benutzen</b>: Festgeschriebene Rechnungen sind Buchungsbelege und müssen 8 Jahre aufbewahrt werden (§ 147 AO, § 14b UStG, GoBD).
        Vorher wird automatisch eine vollständige Sicherung angelegt, mit der sich alles über „Rücksicherung“ zurückholen lässt.</div>
      <p style="margin-top:0"><b>Was soll gelöscht werden?</b></p>
      <div class="spalte" style="gap:8px">${d.gruppen.map(g => `<label style="display:flex;gap:8px;align-items:flex-start"><input type="checkbox" data-tg="${g.id}" ${g.standard ? "checked" : ""} style="flex:0 0 auto;margin-top:3px">
        <span>${esc(g.text)}<br><span class="hinweis">derzeit ${esc(g.anzahl)}</span></span></label>`).join("")}</div>
      ${d.auftraege.length ? `<div class="sektion" style="margin-top:14px">Diese Aufträge behalten</div>
      <p style="margin:4px 0">Echte Aufträge oder Angebote, die schon in der Testphase entstanden sind, hier anhaken. Sie bleiben vollständig erhalten – mit Positionen, Kalkulation, Belegen, Terminen, Notizen und Anhängen, ebenso ihr Kunde und ihr Projekt – und behalten ihre Nummern; neue Aufträge zählen danach weiter.</p>
      <div class="sich-liste" style="max-height:260px;overflow:auto">${d.auftraege.map(a => `<label style="display:flex;gap:8px;padding:3px 0"><input type="checkbox" data-tb="${a.id}" style="flex:0 0 auto;margin-top:3px">
        <span><b>${esc(a.nummer)}</b> ${esc(a.bezeichnung || "")} · ${esc(a.kunde || "")} · ${esc(a.status || "")}${a.belege ? ` · ${a.belege} ${a.belege === 1 ? "Beleg" : "Belege"}` : ""}${a.fest ? ` · <span style="color:var(--rot)">${a.fest} festgeschrieben</span>` : ""}</span></label>`).join("")}</div>` : ""}
      <p class="hinweis">Bleiben immer erhalten: Einstellungen, Briefbogen/AGB, Textbausteine, Kalkulationswerte, Materialstamm samt Lagerbestand (Lagerabgänge auf gelöschte Aufträge werden zurückgebucht), Werkzeuge, Mitarbeiter-Stammdaten und Benutzer. Dateien in den Projektordnern werden nicht angerührt.</p>
      <div class="sektion" style="margin-top:14px">Nummernkreise</div>
      <p style="margin:4px 0">Nächste Nummern derzeit: Rechnung <b>${esc(d.nummern.rechnung)}</b> · Auftrag <b>${esc(d.nummern.auftrag)}</b> · Kunde <b>${esc(d.nummern.kunde)}</b>.
        Nach dem Löschen beginnen sie wieder vorn (bzw. bei der Startnummer aus den Einstellungen), wenn der Nummernzähler mit zurückgesetzt wird.</p>
      ${d.zaehler_gesetzt ? `<label style="display:flex;gap:8px"><input type="checkbox" id="tdZaehler" checked style="flex:0 0 auto;margin-top:3px"> <span>Nummernzähler zurücksetzen, damit Rechnungen, Aufträge und Kunden wieder vorn beginnen <span class="hinweis">(der Zähler merkt sich die höchste vergebene Rechnungsnummer, auch die der Testrechnungen; nur abwählen, wenn die Zähler bewusst an die Nummern eines Vorgängerprogramms angeschlossen wurden. Behaltene Aufträge und ihre Belege behalten ihre Nummern, neue zählen danach weiter.)</span></span></label>` : ""}
      <div class="sektion" style="margin-top:14px">Echtbetrieb starten</div>
      <p style="margin:4px 0">Sind die Testdaten gelöscht und beginnt die echte Arbeit, wird hier einmalig der <b>Echtbetrieb</b> gestartet. Ab dann ist „Testdaten löschen“ dauerhaft gesperrt –
        auch nach einer Rücksicherung, weil der Start im unveränderbaren Protokoll steht. Das ist der Nachweis, dass ab diesem Tag keine Rechnungen mehr gelöscht wurden (GoBD).</p>
      <label style="display:flex;gap:8px;margin:6px 0"><input type="checkbox" id="ebProt" ${d.fest ? "disabled" : "checked"} style="flex:0 0 auto;margin-top:3px">
        <span>Protokoll der Testphase abschließen und neu beginnen (derzeit ${d.protokoll} Einträge)<br><span class="hinweis">Die bisherigen Einträge werden nicht vernichtet: Vorher entsteht eine vollständige Sicherung, und die Protokolldatei der Testphase bleibt umbenannt im Datenordner liegen. Das neue Protokoll beginnt mit dem Eintrag „Echtbetrieb begonnen“.
        ${d.fest ? `<b style="color:var(--rot)">Nicht möglich, solange es festgeschriebene Rechnungen aus der Testphase gibt (${d.fest}) – erst Testdaten löschen.</b>` : ""}</span></span></label>
      ${inhaber ? `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0 4px">Zur Bestätigung <b>ECHTBETRIEB</b> eintippen: <input id="ebBest" style="width:150px" autocomplete="off">
        <button class="btn prim" id="ebGo" disabled>Echtbetrieb starten</button></div>` : ""}
      <div class="sektion" style="margin-top:14px">Testdaten löschen – Bestätigen</div>
      ${inhaber ? `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:6px">Zur Bestätigung <b>LÖSCHEN</b> eintippen: <input id="tdBest" style="width:130px" autocomplete="off">
        <button class="btn rot" id="tdGo" disabled>Ausgewählte Testdaten löschen</button></div><div id="tdErg" style="margin-top:12px"></div>`
        : `<p class="hinweis">Das darf nur der Inhaber.</p>`}`;
    if (!inhaber) return;
    const eb = $("#ebBest", z), ebGo = $("#ebGo", z);
    eb.oninput = () => { ebGo.disabled = eb.value.trim().toUpperCase() !== "ECHTBETRIEB"; };
    ebGo.onclick = async () => {
      if (!await frage("Echtbetrieb jetzt starten?\n\nDanach können keine Testdaten mehr gelöscht werden. Das lässt sich nicht rückgängig machen.", {ok: "Echtbetrieb starten"})) return;
      try { await api("service/echtbetrieb", {method: "POST", body: {bestaetigung: eb.value, protokoll_neu: !!($("#ebProt", z) || {}).checked}}); toast("Echtbetrieb gestartet"); E._echtbetrieb = true; serviceSeite(z, sub); }
      catch (x) { toast(x.message, true); }
    };
    const b = $("#tdBest", z), go = $("#tdGo", z);
    const sync = () => {
      const k = $$("[data-tg]", z);
      const kunden = k.find(x => x.dataset.tg === "kunden"), auft = k.find(x => x.dataset.tg === "auftraege");
      const lief = k.find(x => x.dataset.tg === "lieferanten"), zahl = k.find(x => x.dataset.tg === "zahlungen");
      if (kunden.checked) { auft.checked = true; } auft.disabled = kunden.checked;
      if (lief.checked) { zahl.checked = true; } zahl.disabled = lief.checked;
      go.disabled = b.value.trim().toUpperCase() !== "LÖSCHEN" || !k.some(x => x.checked);
    };
    $$("[data-tg]", z).forEach(x => x.onchange = sync); b.oninput = sync; sync();
    go.onclick = async () => {
      const gruppen = $$("[data-tg]", z).filter(x => x.checked).map(x => x.dataset.tg);
      const beh = $$("[data-tb]", z).filter(x => x.checked).length;
      if (!await frage(`Wirklich löschen? Vorher wird eine vollständige Sicherung angelegt.${beh ? `\n\n${beh} ${beh === 1 ? "Auftrag bleibt" : "Aufträge bleiben"} erhalten.` : ""}`)) return;
      go.disabled = true; go.textContent = "Sicherung und Löschen laufen …";
      try {
        const r = await api("service/testdaten", {method: "POST", body: {gruppen, bestaetigung: b.value, zaehler: !!($("#tdZaehler", z) || {}).checked, behalten: $$("[data-tb]", z).filter(x => x.checked).map(x => +x.dataset.tb)}});
        const n = Object.entries(r.geloescht).map(([t, a]) => `${t}: ${a}`).join(" · ");
        await serviceSeite(z, sub);
        $("#tdErg", z).innerHTML = `<div class="kachel" style="border-left:4px solid var(--gruen)"><b>Erledigt.</b> Gelöschte Datensätze: ${esc(n || "keine")}.${(r.behalten || []).length ? ` Behalten: ${esc(r.behalten.join(", "))}.` : ""}<br>
          Sicherung vorher: ${esc(r.sicherung)}<br>Nächste Nummern jetzt: Rechnung <b>${esc(r.nummern.rechnung)}</b> · Auftrag <b>${esc(r.nummern.auftrag)}</b> · Kunde <b>${esc(r.nummern.kunde)}</b></div>`;
        toast("Testdaten gelöscht");
      } catch (e) { toast(e.message, true); go.disabled = false; go.textContent = "Ausgewählte Testdaten löschen"; }
    };
  }
}

// ---------------------------------------------------------------- Projektordner sichern (nur Geändertes, mit früheren Fassungen)
const groesseText = b => b >= 1e9 ? n2(b / 1e9, 1) + " GB" : b >= 1e6 ? n2(b / 1e6, 1) + " MB" : b >= 1000 ? n2(b / 1e3, 0) + " kB" : b + " Byte";
let projektTakt = null;
async function projektSicherungSeite(z) {
  clearTimeout(projektTakt);
  const d = await api("service/projektsicherung");
  const e = d.einstellung, l = d.status.letzter, lauf = d.lauf, inhaber = !ICH || ICH.rechte.inhaber;
  const bereit = d.projektpfad && d.ziel;
  const letzterText = !l ? "noch kein Lauf" : `${zeitDE(l.zeit)} · ` + (l.ok ? `<span style="color:var(--gruen)">in Ordnung</span> · ${l.neu} neu, ${l.geaendert} geändert, ${l.entfernt} im Projektordner gelöscht, ${l.gleich} unverändert · ${groesseText(l.bytes)} übertragen in ${n2(l.dauer, 0)} s${l.verschluesselt ? " · 🔒 verschlüsselt" : ""}`
    : `<span style="color:var(--rot)">${l.abgebrochen ? "abgebrochen" : "nicht gesichert"}</span>`) + (l.hinweis ? `<br><span style="color:var(--rot)">${esc(l.hinweis)}</span>` : "")
    + (l.fehler_anzahl ? `<br><span style="color:var(--rot)">${l.fehler_anzahl} ${l.fehler_anzahl === 1 ? "Datei" : "Dateien"} nicht gesichert</span> (z. B. gerade in einem anderen Programm geöffnet; wird beim nächsten Lauf erneut versucht):<br><span class="hinweis">${l.fehler.slice(0, 8).map(esc).join("<br>")}${l.fehler_anzahl > 8 ? "<br>…" : ""}</span>` : "");
  z.innerHTML = `<div class="titel"><h2>Projektordner sichern</h2><div class="rechts">${lauf.laeuft ? `<button class="btn" id="psAbbruch">Abbrechen</button>` : `<button class="btn prim" id="psStart" ${bereit && inhaber ? "" : "disabled"}>Jetzt sichern</button>`}</div></div>
    <p>Sichert den Projektordner <code>${esc(d.projektpfad || "– nicht eingestellt –")}</code> auf das externe Sicherungsziel nach <code>${esc(d.ordner || "– kein Sicherungsziel eingestellt –")}</code>.
    Übertragen wird nur, was neu ist oder sich geändert hat; der erste Lauf dauert je nach Größe lange, alle weiteren meist nur Sekunden bis Minuten.</p>
    ${bereit ? "" : `<p style="color:var(--rot)">Dafür müssen der Projektordner (Einstellungen › Programm) und das externe Sicherungsziel (Service › Datensicherung) eingestellt sein.</p>`}
    ${lauf.laeuft ? `<div class="kachel"><b>${lauf.art === "wiederherstellen" ? "Wiederherstellung läuft" : "Sicherung läuft"}</b> – ${esc(lauf.phase)}${lauf.gesamt ? ` · ${lauf.erledigt} von ${lauf.gesamt} Dateien · ${groesseText(lauf.bytes)}` : ""}
      <div style="height:8px;background:var(--linie,#ddd);border-radius:4px;margin:8px 0;overflow:hidden"><div style="height:100%;width:${lauf.gesamt ? Math.round(100 * lauf.erledigt / lauf.gesamt) : 3}%;background:var(--akzent,#8a6a45)"></div></div>
      <span class="hinweis" style="word-break:break-all">${esc(lauf.datei || "")}</span></div>` : ""}
    <div class="form" style="grid-template-columns:1fr">
      ${zeile("Letzter Lauf", `<span style="padding-top:5px;line-height:1.5">${letzterText}</span>`)}
      ${zeile("Automatisch", `<label style="padding-top:5px"><input type="checkbox" id="psAktiv" ${e.aktiv ? "checked" : ""} ${inhaber ? "" : "disabled"}> täglich sichern, sobald das Programm nach
        <input type="time" id="psZeit" value="${esc(e.uhrzeit)}" style="width:110px" ${inhaber ? "" : "disabled"}> Uhr läuft</label>`)}
      ${zeile("Frühere Fassungen", `<span><input type="number" id="psTage" min="0" max="3650" value="${e.tage}" style="width:90px" ${inhaber ? "" : "disabled"}> Tage behalten (0 = nie entfernen)</span>`)}
      ${zeile("Warnen nach", `<span><input type="number" id="psWarn" min="1" max="365" value="${e.warn_tage}" style="width:90px" ${inhaber ? "" : "disabled"}> Tagen ohne Sicherung auf das externe Ziel (Hinweis auf der Startseite)</span>`)}
      ${zeile("", `<span class="hinweis">Für ein Ziel, das nur zeitweise angeschlossen wird (z. B. eine USB-Platte einmal in der Woche): Frist entsprechend höher setzen, etwa 8 Tage. Sobald das Laufwerk angesteckt ist, sichert das Programm innerhalb weniger Minuten von selbst, auch die Datenbanksicherung des Tages. Die Frist gilt ebenso für den Hinweis zur täglichen Datenbanksicherung.</span>`)}
      ${zeile("", `<span class="hinweis">Wird eine Datei geändert oder im Projektordner gelöscht, überschreibt die Sicherung nichts: Die bisherige Fassung wandert in den Unterordner „frueher“ und wird erst nach dieser Frist entfernt. So lässt sich auch der Stand von vor einem Versehen oder einem Verschlüsselungstrojaner zurückholen. Sind bei einem Lauf auffällig viele Dateien geändert, wird nichts entfernt und auf der Startseite gewarnt.<br>
        ${d.kennwort.gesetzt ? (d.kennwort.lesbar ? "🔒 Das Sicherungskennwort ist gesetzt: Jede Datei wird einzeln verschlüsselt abgelegt (Endung .jrs). Datei- und Ordnernamen bleiben auf dem Sicherungsziel lesbar." : `<b style="color:var(--rot)">Das Sicherungskennwort ist gesetzt, aber auf diesem PC nicht lesbar – es wird nicht gesichert, bis es unter Datensicherung neu gesetzt ist.</b>`)
          : "Ohne Sicherungskennwort (Service › Datensicherung) liegen die Dateien unverschlüsselt und direkt lesbar auf dem Sicherungsziel."}
        Nicht gesichert werden Zwischendateien geöffneter Programme (~$…, .tmp) und der Unterordner „_Wiederhergestellt“.</span>`)}
    </div>
    <div class="sektion" style="margin-top:18px">Dateien zurückholen</div>
    ${d.staende.length ? `<p class="hinweis">Stand wählen, zum gewünschten Ordner blättern und zurückholen. Die Dateien landen im Projektordner unter „_Wiederhergestellt“ – vorhandene Dateien werden nie überschrieben.</p>
      <div class="zeile"><label>Stand</label><div><select id="psStand" style="max-width:520px">${d.staende.map(s => `<option value="${esc(s.stand)}">${esc(s.text)}</option>`).join("")}</select></div></div>
      <div id="psInhalt" class="sich-liste" style="margin-top:8px"></div>` : `<p class="hinweis">Noch keine Sicherung des Projektordners vorhanden.</p>`}
    ${lauf.ergebnis && !lauf.laeuft ? `<p style="margin-top:10px">Zuletzt zurückgeholt: ${lauf.ergebnis.dateien} Dateien (${groesseText(lauf.ergebnis.bytes)}) nach <code>${esc(lauf.ergebnis.ordner || "")}</code>${lauf.ergebnis.fehler.length ? ` · <span style="color:var(--rot)">${lauf.ergebnis.fehler.length} Fehler: ${esc(lauf.ergebnis.fehler[0])}</span>` : ""}</p>` : ""}`;
  const neuLaden = () => { if (location.hash.includes("service/projekte")) projektSicherungSeite(z); };
  if (lauf.laeuft) projektTakt = setTimeout(neuLaden, 1500);
  const aktion = async (pfad, body, text) => { try { await api("service/projektsicherung/" + pfad, {method: "POST", body: body || {}}); if (text) toast(text); } catch (x) { toast(x.message, true); } neuLaden(); };
  if ($("#psStart")) $("#psStart").onclick = () => aktion("start", {}, "Sicherung gestartet – sie läuft im Hintergrund weiter");
  if ($("#psAbbruch")) $("#psAbbruch").onclick = () => aktion("abbrechen", {}, "wird abgebrochen …");
  const speichern = async () => {
    try { await api("service/projektsicherung/einstellung", {method: "POST", body: {aktiv: $("#psAktiv").checked, uhrzeit: $("#psZeit").value, tage: $("#psTage").value, warn_tage: $("#psWarn").value}}); toast("Gespeichert"); E = await api("einstellungen"); }
    catch (x) { toast(x.message, true); }
    neuLaden();
  };
  ["#psAktiv", "#psZeit", "#psTage", "#psWarn"].forEach(s => { if ($(s)) $(s).onchange = speichern; });
  if (!$("#psStand")) return;
  const zeigen = async pfad => {
    const stand = $("#psStand").value, box = $("#psInhalt");
    let i;
    try { i = await api(`service/projektsicherung/inhalt?stand=${encodeURIComponent(stand)}&pfad=${encodeURIComponent(pfad)}`); }
    catch (x) { box.innerHTML = `<div class="leer">${esc(x.message)}</div>`; return; }
    const teile = i.pfad ? i.pfad.split("/") : [];
    box.innerHTML = `<div><a href="#" data-p="">Projektordner</a>${teile.map((t, n) => ` › <a href="#" data-p="${esc(teile.slice(0, n + 1).join("/"))}">${esc(t)}</a>`).join("")}
        ${inhaber && !lauf.laeuft ? ` &nbsp; <button class="btn" data-hol="${esc(i.pfad)}">${i.pfad ? "Diesen Ordner zurückholen" : "Alles zurückholen"}</button>` : ""}</div>
      ${i.ordner.map(o => `<div>📁 <a href="#" data-p="${esc((i.pfad ? i.pfad + "/" : "") + o)}">${esc(o)}</a></div>`).join("")}
      ${i.dateien.slice(0, 300).map(f => `<div class="sich-z"><span>${esc(f.name)} · ${groesseText(f.groesse)} · ${zeitDE(f.zeit)}${f.verschluesselt ? " · 🔒" : ""}</span>${inhaber && !lauf.laeuft ? `<a class="btn" href="#" data-hol="${esc((i.pfad ? i.pfad + "/" : "") + f.name)}" title="Diese Datei zurückholen">↩</a>` : ""}</div>`).join("")}
      ${i.dateien.length > 300 ? `<div class="hinweis">… und ${i.dateien.length - 300} weitere Dateien</div>` : ""}
      ${!i.ordner.length && !i.dateien.length ? `<div class="leer">leer</div>` : ""}`;
    $$("[data-p]", box).forEach(a => a.onclick = ev => { ev.preventDefault(); zeigen(a.dataset.p); });
    $$("[data-hol]", box).forEach(a => a.onclick = async ev => {
      ev.preventDefault();
      const was = a.dataset.hol;
      const holen = async kennwort => {
        try { await api("service/projektsicherung/wiederherstellen", {method: "POST", body: {stand, pfad: was, kennwort}}); toast("Wird zurückgeholt …"); neuLaden(); }
        catch (x) {
          if (x.status !== 428 && !/Sicherungskennwort gebraucht/.test(x.message)) { toast(x.message, true); return; }
          const g = await modal("Sicherungskennwort", `<div class="zeile voll"><label>Kennwort</label><div><input name="kennwort" type="password" autocomplete="off" style="width:100%"></div></div>
            <p class="hinweis">Diese Sicherung wurde auf einem anderen PC oder mit einem anderen Kennwort verschlüsselt.</p>`, "Zurückholen");
          if (g) holen(g.kennwort);
        }
      };
      if (await frage(`„${was || "Alles"}“ aus dem gewählten Stand zurückholen?\n\nDie Dateien werden in den Projektordner unter „_Wiederhergestellt“ kopiert. Vorhandene Dateien bleiben unverändert.`, {ok: "Zurückholen"})) holen("");
    });
  };
  $("#psStand").onchange = () => zeigen("");
  zeigen("");
}
