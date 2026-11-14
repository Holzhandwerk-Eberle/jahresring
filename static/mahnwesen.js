// =====================================================================
//  Mahnwesen: Zahlungserinnerung (M0), Mahnung (M1), Letzte Mahnung (M2)
// =====================================================================
const OP_REITER = (aktiv, anzahl) => kopf({reiter: [["Offene Posten", "#/op", aktiv === "op"],
  [`Mahnwesen${anzahl ? ` (${anzahl})` : ""}`, "#/op/mahnwesen", aktiv === "mahn"], ["Kontoauszüge", "#/op/bank", aktiv === "bank"],
  ...(darf("op", 2) ? [["Liquidität", "#/op/liquiditaet", aktiv === "liq"]] : [])]});

// Kurze Anzeige des Mahnstands eines offenen Postens (für Listen)
function mahnStand(o) {
  const lm = o.letzte_mahnung, v = o.mahnvorschlag;
  const teile = [];
  if (lm) teile.push(`<span class="tag nw" title="${esc(lm.name)} vom ${datum(lm.datum)}, Frist bis ${datum(lm.frist)}">${esc(lm.kz)} · ${datum(lm.datum).slice(0, 6)}</span>`);
  if (o.mahnsperre) teile.push(`<span class="hinweis">Mahnsperre</span>`);
  else if (v && v.stufe != null && !v.jetzt) teile.push(`<span class="hinweis">${esc(v.kz)} ab ${datum(v.ab).slice(0, 6)}</span>`);
  else if (v && v.stufe == null) teile.push(`<span class="hinweis">${esc(v.name)}</span>`);
  return teile.join(" ");
}
function mahnKnopf(o) {
  const v = o.mahnvorschlag;
  if (!v || o.mahnsperre || o.offen < 0.005 || !o.faellig || o.faellig >= heute()) return "";  // erst wenn überfällig
  if (v.stufe == null) return "";
  return `<button class="btn nw${v.jetzt ? " prim" : ""}" data-mahnen="${o.id}" title="${esc(v.name)} erstellen${v.jetzt ? "" : " (planmäßig erst ab " + datum(v.ab) + ")"}">${esc(v.kz)} mahnen</button>`;
}

async function ansichtMahnwesen(oeffnen) {
  const z = $("#inhalt");
  const r = await api("mahnwesen");
  const posten = r.posten.filter(o => o.offen >= 0.005);
  const jetzt = posten.filter(o => o.mahnvorschlag && o.mahnvorschlag.jetzt && !o.mahnsperre);
  OP_REITER("mahn", jetzt.length);
  sortierung.mahn ||= {k: "faellig", ab: false};
  const t = tabelle("mahn", [
    {k: "nummer", t: "Rechnung", f: o => `<span class="nw">${o.beleg_id ? `<a href="#/beleg/${o.beleg_id}">${esc(o.nummer)}</a>` : esc(o.nummer)}</span>`},
    {k: "kunde", t: "Kunde", f: o => `<a href="#/kunde/${o.kunde_id}">${esc(o.kunde || "")}</a>`},
    {k: "auftragsnr", t: "Auftrag", f: o => o.auftrag_id ? `<a class="nw" href="#/auftrag/${o.auftrag_id}/op">${esc(o.auftragsnr || "")}</a>` : ""},
    {k: "faellig", t: "Fällig", f: o => `<b style="color:var(--rot)">${datum(o.faellig)}</b>`},
    {k: "ueberfaellig_tage", t: "Tage", r: 1},
    {k: "offen", t: "Offen", r: 1, f: o => `<b class="nw">${eur(o.offen)}</b>`},
    {k: "mahnkosten", t: "Mahnkosten", r: 1, f: o => o.mahnkosten > 0.004 ? `<span class="nw">${eur(o.mahnkosten)}</span>` : ""},
    {k: "mahnstufe", t: "Stand", f: o => mahnStand(o) || `<span class="hinweis">noch nicht gemahnt</span>`},
    {k: "id", t: "", f: o => `<span style="display:flex;gap:4px;justify-content:flex-end">${mahnKnopf(o)}
      <button class="btn" data-sperre="${o.id}" title="${o.mahnsperre ? "Mahnsperre aufheben" : "Diesen Posten vorerst nicht mahnen (z. B. Ratenzahlung vereinbart)"}">${o.mahnsperre ? "Sperre aufheben" : "Sperre"}</button>
      <button class="btn" data-zahl="${o.id}">Zahlung</button></span>`},
  ], posten, {leer: "Keine überfälligen Rechnungen – es gibt nichts zu mahnen."});
  const ms = r.mahnungen;
  sortierung.mahnl ||= {k: "datum", ab: true};
  const tm = mahnungenTabelle("mahnl", ms, true);
  z.innerHTML = `<div class="titel"><h2>Mahnwesen</h2><div class="rechts"><a class="btn" href="#/einstellungen/texte/mahnungen" title="Mahnstufen, Fristen, Gebühren und Texte">Mahnstufen einstellen</a></div></div>
    <p class="hinweis" style="margin-top:-6px">Überfällige Rechnungen mit dem Vorschlag für die nächste Mahnstufe. Farbig hervorgehobene Knöpfe sind jetzt dran;
    die übrigen lassen sich auch früher mahnen. Zahlungseingänge werden hier oder unter „Offene Posten“ gebucht.</p>
    ${t.html}
    <h3 style="margin-top:22px">Erstellte Mahnungen</h3>${tm.html}`;
  const neu = () => ansichtMahnwesen();
  t.binden(neu); tm.binden(neu);
  $$("[data-mahnen]", z).forEach(b => b.onclick = () => mahnungErstellen(+b.dataset.mahnen, neu));
  $$("[data-sperre]", z).forEach(b => b.onclick = async () => {
    const o = posten.find(x => x.id === +b.dataset.sperre);
    await api(`offeneposten/${o.id}/mahnsperre`, {method: "POST", body: {an: !o.mahnsperre}});
    toast(o.mahnsperre ? "Mahnsperre aufgehoben" : "Mahnsperre gesetzt"); neu();
  });
  $$("[data-zahl]", z).forEach(b => b.onclick = () => zahlungBuchen(posten.find(x => x.id === +b.dataset.zahl), neu));
  mahnungenBinden(z, ms, neu);
  if (oeffnen && posten.some(o => o.id === +oeffnen)) mahnungErstellen(+oeffnen, () => { location.hash = "#/op/mahnwesen"; });
}

function mahnungenTabelle(id, ms, mitKunde) {
  return tabelle(id, [
    {k: "datum", t: "Datum", f: m => datum(m.datum)},
    {k: "nummer", t: "Mahnung", f: m => `<a href="/api/mahnungen/${m.id}/pdf" target="_blank" title="PDF öffnen">${esc(m.name)} ${esc(m.nummer)}</a>`},
    ...(mitKunde ? [{k: "kunde", t: "Kunde", f: m => `<a href="#/kunde/${m.kunde_id}">${esc(m.kunde || "")}</a>`}] : []),
    {k: "frist", t: "Frist bis", f: m => m.op_offen > 0.004 && m.frist < heute() && m.letzte ? `<b style="color:var(--rot)">${datum(m.frist)}</b>` : datum(m.frist)},
    {k: "gesamt", t: "Gefordert", r: 1, f: m => `<span class="nw">${eur(m.gesamt)}</span>`},
    {k: "versendet", t: "Versand", f: m => m.versendet ? `<span title="an ${esc(m.versendet_an)}">✉ ${datum(m.versendet.slice(0, 10)).slice(0, 6)}</span>` : ""},
    {k: "op_offen", t: "Status", f: m => m.op_offen < 0.005 ? `<span style="color:var(--gruen)">bezahlt</span>` : "offen"},
    {k: "id", t: "", f: m => `<span style="display:flex;gap:4px;justify-content:flex-end">
      <a class="btn" href="/api/mahnungen/${m.id}/pdf" target="_blank">PDF</a>
      <a class="btn" href="/druck/mahnung/${m.id}?drucken=1" target="_blank">Drucken</a>
      <button class="btn" data-mmail="${m.id}">E-Mail</button>
      ${m.letzte ? `<button class="btn rot" data-mdel="${m.id}" title="Mahnung löschen (nur die jeweils letzte eines Postens)">✕</button>` : ""}</span>`},
  ], ms, {leer: "Noch keine Mahnungen erstellt."});
}
function mahnungenBinden(z, ms, neu) {
  $$("[data-mmail]", z).forEach(b => b.onclick = () => mailDialog(`mahnungen/${b.dataset.mmail}`, "Mahnung per E-Mail senden", () => neu()));
  $$("[data-mdel]", z).forEach(b => b.onclick = async () => {
    const m = ms.find(x => x.id === +b.dataset.mdel);
    if (!await frage(`${m.name} ${m.nummer} löschen?\n\n` + (m.versendet ? "Sie wurde schon an den Kunden gesendet. " : "") +
      "Die Mahnkosten werden zurückgenommen, das PDF wandert in den Papierkorb.")) return;
    try { await api("mahnungen/" + m.id, {method: "DELETE"}); toast("Mahnung gelöscht"); neu(); } catch (e) { toast(e.message, true); }
  });
}

async function zahlungBuchen(o, danach) {
  let best = E.zahlbest_vorschlagen !== false;
  const mk = o.mahnkosten > 0.004 ? o.mahnkosten : 0;
  const d = await modal(`Zahlungseingang ${o.nummer}`, `
    <div class="zeile"><label>Datum</label><div><input type="date" name="datum" value="${heute()}"></div></div>
    <div class="zeile"><label>Betrag</label><div><input name="betrag" class="zahl" value="${n2(o.offen + mk)}" style="width:120px"> €</div></div>
    ${mk ? `<div class="zeile"><label></label><div class="hinweis">offen ${eur(o.offen)} + Mahnkosten ${eur(mk)}. Was über den Rechnungsbetrag hinausgeht, wird auf die Mahnkosten gebucht.</div></div>` : ""}
    <div class="zeile"><label>Skontoabzug</label><div><input name="skonto" class="zahl" value="" placeholder="0,00" style="width:120px"> €</div></div>
    <div class="zeile"><label>Zahlart</label><div><select name="art">${opts(E.bezahlarten, "Überweisung")}</select></div></div>
    <div class="zeile"><label>Bemerkung</label><div><input name="bemerkung"></div></div>
    <div class="zeile"><label></label><div><label style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="zbBest" ${E.zahlbest_vorschlagen !== false ? "checked" : ""} style="flex:0 0 auto"> danach Zahlungsbestätigung per E-Mail an den Kunden</label></div></div>`, "Buchen",
    hg => { $("#zbBest", hg).onchange = e => { best = e.target.checked; }; });
  if (!d) return;
  try { await api(`offeneposten/${o.id}/zahlung`, {method: "POST", body: {...d, betrag: zahlEin(d.betrag), skonto: zahlEin(d.skonto)}}); toast("Zahlung gebucht"); danach(); }
  catch (e) { return toast(e.message, true); }
  if (best) mailDialog(`offeneposten/${o.id}`, `Zahlungsbestätigung ${o.nummer}`);
}

// Dialog „Mahnung erstellen“
async function mahnungErstellen(opid, danach) {
  let v;
  try { v = await api(`offeneposten/${opid}/mahnung`); } catch (e) { return toast(e.message, true); }
  const st = {stufe: v.stufe, datum: v.datum, frist: v.frist, gebuehr: v.gebuehr, zinsen: v.mit_zinsen, pauschale: v.mit_pauschale, textGeaendert: false};
  const o = v.op;
  const betraege = w => `<table class="liste" style="margin:0">
      <tr><td>offener Rechnungsbetrag</td><td class="r">${eur(w.offen)}</td></tr>
      ${w.kosten_bisher ? `<tr><td>Mahnkosten aus vorherigen Mahnungen</td><td class="r">${eur(w.kosten_bisher)}</td></tr>` : ""}
      ${w.gebuehr ? `<tr><td>Mahngebühr</td><td class="r">${eur(w.gebuehr)}</td></tr>` : ""}
      ${w.zinsen ? `<tr><td>Verzugszinsen ${zahlDE(w.zinssatz)} % für ${w.zinstage} Tage</td><td class="r">${eur(w.zinsen)}</td></tr>` : ""}
      ${w.pauschale ? `<tr><td>Verzugspauschale § 288 Abs. 5 BGB</td><td class="r">${eur(w.pauschale)}</td></tr>` : ""}
      <tr><td><b>Gesamt</b></td><td class="r"><b>${eur(w.gesamt)}</b></td></tr></table>`;
  const inhalt = `
    <p class="hinweis" style="margin-top:0">Rechnung <b>${esc(o.nummer)}</b> vom ${datum(o.datum)} · ${esc(v.kunde)} · fällig seit ${datum(o.faellig)}
      ${v.bisher.length ? ` · bisher: ${v.bisher.map(b => `${esc(b.kz)} vom ${datum(b.datum)}`).join(", ")}` : " · noch nicht gemahnt"}</p>
    <div class="zeile"><label>Mahnstufe</label><div><select id="mStufe">${v.stufen.map((s, i) => `<option value="${i}" ${i === v.stufe ? "selected" : ""}>${esc(s.kz)} · ${esc(s.name)}</option>`).join("")}</select></div></div>
    <div class="zeile"><label>Datum</label><div><input type="date" id="mDatum" value="${v.datum}" style="width:160px">
      <span style="padding:6px 6px 0 14px">zahlbar bis</span><input type="date" id="mFrist" value="${v.frist}" style="width:160px"></div></div>
    <div class="zeile"><label>Mahngebühr</label><div><input id="mGeb" class="zahl" value="${n2(v.gebuehr)}" style="width:100px"> €</div></div>
    <div class="zeile"><label></label><div class="spalte">
      <label><input type="checkbox" id="mZins" ${st.zinsen ? "checked" : ""}> Verzugszinsen berechnen (${zahlDE(v.basiszins)} % Basiszins + ${v.unternehmer ? "9" : "5"} Prozentpunkte, ${v.unternehmer ? "Geschäftskunde" : "Verbraucher"})</label>
      ${v.unternehmer ? `<label><input type="checkbox" id="mPausch" ${st.pauschale ? "checked" : ""}> Verzugspauschale 40 € (§ 288 Abs. 5 BGB, nur einmal je Rechnung)</label>` : ""}
    </div></div>
    <div class="zeile"><label>Beträge</label><div id="mBetr" style="display:block">${betraege(v)}</div></div>
    <div class="zeile"><label>Betreff</label><div><input name="betreff" id="mBetreff" value="${esc(v.betreff)}"></div></div>
    <div class="zeile"><label>Text</label><div><textarea name="text" id="mText" rows="9" style="width:100%;font:inherit">${esc(v.text)}</textarea></div></div>
    <div class="zeile"><label>Schluss</label><div><textarea name="schluss" id="mSchluss" rows="2" style="width:100%;font:inherit">${esc(v.schluss)}</textarea></div></div>`;
  const d = await modal("Mahnung erstellen", inhalt, "Mahnung erstellen", hg => {
    $(".modal", hg).style.width = "min(760px,96vw)";
    $(".modal", hg).style.maxHeight = "94vh"; $(".modal", hg).style.overflow = "auto";
    ["#mText", "#mBetreff", "#mSchluss"].forEach(s => $(s, hg).addEventListener("input", () => st.textGeaendert = true));
    $("#mText", hg).addEventListener("keydown", e => e.stopPropagation());
    const neuLaden = async stufeGewechselt => {
      const q = new URLSearchParams({stufe: st.stufe, datum: st.datum, zinsen: st.zinsen ? "1" : "0", pauschale: st.pauschale ? "1" : "0",
        ...(stufeGewechselt ? {} : {gebuehr: st.gebuehr})});
      const w = await api(`offeneposten/${opid}/mahnung?` + q);
      if (stufeGewechselt) {
        st.gebuehr = w.gebuehr; $("#mGeb", hg).value = n2(w.gebuehr);
        st.frist = w.frist; $("#mFrist", hg).value = w.frist;
        if (!st.textGeaendert || await frage("Die Texte der neuen Mahnstufe übernehmen? Änderungen am Text gehen dabei verloren.", {ok: "Übernehmen"})) {
          $("#mBetreff", hg).value = w.betreff; $("#mText", hg).value = w.text; $("#mSchluss", hg).value = w.schluss; st.textGeaendert = false;
        }
      } else if (!st.textGeaendert) {
        $("#mBetreff", hg).value = w.betreff; $("#mText", hg).value = w.text; $("#mSchluss", hg).value = w.schluss;
      }
      $("#mBetr", hg).innerHTML = betraege(w);
    };
    $("#mStufe", hg).onchange = e => { st.stufe = +e.target.value; neuLaden(true); };
    $("#mDatum", hg).onchange = e => {
      const alt = st.datum; st.datum = e.target.value || heute();
      const tage = Math.round((new Date(st.frist) - new Date(alt)) / 864e5);
      const f = new Date(st.datum); f.setDate(f.getDate() + tage); st.frist = f.toISOString().slice(0, 10); $("#mFrist", hg).value = st.frist;
      neuLaden(false);
    };
    $("#mFrist", hg).onchange = e => { st.frist = e.target.value; if (!st.textGeaendert) neuLaden(false); };
    $("#mGeb", hg).onchange = e => { st.gebuehr = zahlEin(e.target.value); neuLaden(false); };
    $("#mZins", hg).onchange = e => { st.zinsen = e.target.checked; neuLaden(false); };
    const p = $("#mPausch", hg); if (p) p.onchange = e => { st.pauschale = e.target.checked; neuLaden(false); };
  });
  if (!d) return;
  toast("Mahnung wird erstellt …");
  let r;
  try {
    r = await api(`offeneposten/${opid}/mahnung`, {method: "POST", body: {stufe: st.stufe, datum: st.datum, frist: st.frist, gebuehr: st.gebuehr,
      zinsen: st.zinsen, pauschale: st.pauschale, betreff: d.betreff, text: d.text, schluss: d.schluss}});
  } catch (e) { return toast(e.message, true); }
  if (r.hinweis) toast(r.hinweis, true);
  const weiter = await auswahl(`${v.stufen[st.stufe].name} ${r.nummer} erstellt`,
    `<p style="margin-top:0">Das PDF liegt im Archiv${r.projekt ? ` und im Projektordner unter <b>${esc(r.projekt)}</b>` : ""}. Wie soll sie zum Kunden?</p>`,
    [["mail", "Per E-Mail senden"], ["druck", "Drucken"], ["pdf", "PDF ansehen"], ["", "Fertig"]]);
  if (weiter === "mail") await mailDialog(`mahnungen/${r.id}`, "Mahnung per E-Mail senden", () => danach && danach());
  else if (weiter === "druck") window.open(`/druck/mahnung/${r.id}?drucken=1`, "_blank");
  else if (weiter === "pdf") window.open(`/api/mahnungen/${r.id}/pdf`, "_blank");
  if (weiter !== "mail") danach && danach();
}

// Kleiner Dialog mit mehreren Knöpfen; liefert den Schlüssel des gewählten Knopfs
function auswahl(titel, text, knoepfe) {
  return new Promise(res => {
    const hg = document.createElement("div");
    hg.className = "modal-hg";
    hg.innerHTML = `<div class="modal frage"><h3>${esc(titel)}</h3>${text}<div class="knoepfe">
      ${knoepfe.map(([k, l], i) => `<button class="btn${i === 0 ? " prim" : ""}" data-w="${k}">${esc(l)}</button>`).join("")}</div></div>`;
    document.body.appendChild(hg);
    const zu = w => { hg.remove(); res(w); };
    $$("[data-w]", hg).forEach(b => b.onclick = () => zu(b.dataset.w));
    hg.addEventListener("keydown", e => { if (e.key === "Escape") zu(""); });
    $("[data-w]", hg).focus();
  });
}

// ---------- Einstellungen > Texte > Mahnungen ----------
function mahnEinstellungen(z) {
  const std = E.mahnwesen || {};
  const cfg = {basiszins: std.basiszins ?? 1.52, stufen: JSON.parse(JSON.stringify(std.stufen || []))};
  const sp = speicherer("einstellungen", r => { E = {...E, ...r}; });
  const speichern = () => sp.setze("mahnwesen", cfg);
  z.innerHTML = `<div class="titel"><h2>Mahnungen</h2><span class="speicher"></span></div>
    <p class="hinweis" style="margin-top:-6px">Drei Mahnstufen. „Mahnen ab“ zählt bei der Zahlungserinnerung ab dem Fälligkeitsdatum der Rechnung,
    bei den weiteren Stufen ab dem Ablauf der Zahlungsfrist der vorigen Mahnung. Platzhalter: {anrede}, {nummer} (Rechnungsnummer), {datum} (Rechnungsdatum),
    {betrag} (Rechnungsbetrag), {offen}, {faellig}, {zahlbetrag} (Gesamtforderung inkl. Kosten), {gebuehr}, {frist}, {letzte_mahnung}, {auftrag}.
    Die Signatur wird an E-Mails automatisch angehängt.</p>
    <div class="kachel" style="margin-bottom:10px"><div class="form" style="grid-template-columns:1fr">
      ${zeile("Basiszinssatz", `<input id="mzBasis" class="zahl" value="${zahlDE(cfg.basiszins)}" style="flex:0 0 90px;width:90px"> % <span class="hinweis" style="padding:6px 0 0 8px">nach § 247 BGB, ändert sich zum 1. Januar und 1. Juli (Deutsche Bundesbank). Seit 1. Juli 2026: 1,52 %.</span>`)}
    </div></div>
    ${cfg.stufen.map((s, i) => `<div class="kachel" style="margin-bottom:10px"><h4>${esc(s.kz)} · ${esc(s.name)}</h4>
      <div class="form" style="grid-template-columns:1fr">
        ${zeile("Bezeichnung", `<input data-ms="${i}" data-feld="name" value="${esc(s.name)}">`)}
        ${zeile("Mahnen ab", `<input data-ms="${i}" data-feld="tage" data-zahl="1" value="${s.tage}" style="flex:0 0 70px;width:70px"><span style="padding:6px 0 0 6px">Tage ${i ? "nach Ablauf der vorigen Frist" : "nach Fälligkeit"}</span>`)}
        ${zeile("Zahlungsfrist", `<input data-ms="${i}" data-feld="frist" data-zahl="1" value="${s.frist}" style="flex:0 0 70px;width:70px"><span style="padding:6px 0 0 6px">Tage ab Mahndatum</span>`)}
        ${zeile("Mahngebühr", `<input data-ms="${i}" data-feld="gebuehr" data-zahl="1" value="${n2(s.gebuehr)}" style="flex:0 0 90px;width:90px"><span style="padding:6px 0 0 6px">€</span>`)}
        ${zeile("", `<div class="spalte"><label><input type="checkbox" data-ms="${i}" data-feld="zinsen" ${s.zinsen ? "checked" : ""}> Verzugszinsen vorschlagen</label>
          <label><input type="checkbox" data-ms="${i}" data-feld="pauschale" ${s.pauschale ? "checked" : ""}> Verzugspauschale 40 € bei Geschäftskunden vorschlagen</label></div>`)}
        ${zeile("Betreff", `<input data-ms="${i}" data-feld="betreff" value="${esc(s.betreff)}">`)}
        ${zeile("Text", `<textarea data-ms="${i}" data-feld="text" rows="7" style="width:100%;font:inherit">${esc(s.text)}</textarea>`)}
        ${zeile("Schluss", `<textarea data-ms="${i}" data-feld="schluss" rows="2" style="width:100%;font:inherit">${esc(s.schluss)}</textarea>`)}
        ${zeile("E-Mail-Betreff", `<input data-ms="${i}" data-feld="mail_betreff" value="${esc(s.mail_betreff)}">`)}
        ${zeile("E-Mail-Text", `<textarea data-ms="${i}" data-feld="mail_text" rows="6" style="width:100%;font:inherit">${esc(s.mail_text)}</textarea>`)}
      </div></div>`).join("")}
    <p class="hinweis">Rechtlicher Hinweis: Eine Mahngebühr darf nur die tatsächlichen Kosten (Porto, Papier) abdecken; Gerichte akzeptieren meist 1 bis 5 €.
    Für die Zahlungserinnerung, die den Verzug erst auslöst, sollte keine Gebühr anfallen. Verbraucher kommen ohne Mahnung erst 30 Tage nach Zugang der Rechnung in Verzug,
    wenn die Rechnung darauf hinweist.</p>`;
  $("#mzBasis", z).oninput = e => { cfg.basiszins = zahlEin(e.target.value); speichern(); };
  $$("[data-ms]", z).forEach(el => {
    const ev = el.type === "checkbox" ? "onchange" : "oninput";
    el[ev] = () => {
      const s = cfg.stufen[+el.dataset.ms];
      s[el.dataset.feld] = el.type === "checkbox" ? el.checked : el.dataset.zahl ? zahlEin(el.value) : el.value;
      speichern();
    };
  });
}
