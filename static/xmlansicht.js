// =====================================================================
//  XML-Ansicht: XML-Dateien und die XML in ZUGFeRD-/Factur-X-PDFs anzeigen und prüfen
// =====================================================================
// Bekannte Elemente der E-Rechnung (CII und UBL) mit deutscher Bezeichnung und Business-Term-Nummer
const XML_BT = {
  ExchangedDocument: "Rechnungskopf", "ExchangedDocument/ID": "Rechnungsnummer (BT-1)", IssueDateTime: "Rechnungsdatum (BT-2)",
  TypeCode: "Rechnungsart (BT-3)", IncludedNote: "Bemerkung (BG-1)", GuidelineSpecifiedDocumentContextParameter: "Profil (BT-24)",
  BuyerReference: "Käuferreferenz / Leitweg-ID (BT-10)", SellerTradeParty: "Verkäufer (BG-4)", BuyerTradeParty: "Käufer (BG-7)",
  PostalTradeAddress: "Anschrift", SpecifiedTaxRegistration: "Steuer-Registrierung (BT-31/32)", DefinedTradeContact: "Kontakt",
  BuyerOrderReferencedDocument: "Bestellreferenz (BT-13)", ApplicableHeaderTradeDelivery: "Lieferung", ActualDeliverySupplyChainEvent: "Lieferdatum (BT-72)",
  ApplicableHeaderTradeSettlement: "Zahlung und Summen", InvoiceCurrencyCode: "Währung (BT-5)", SpecifiedTradeSettlementPaymentMeans: "Zahlungsart (BG-16)",
  PayeePartyCreditorFinancialAccount: "Bankverbindung (BG-17)", IBANID: "IBAN (BT-84)", ApplicableTradeTax: "Steuer (BG-23)",
  SpecifiedTradePaymentTerms: "Zahlungsbedingungen (BT-20)", DueDateDateTime: "Fälligkeit (BT-9)",
  SpecifiedTradeSettlementHeaderMonetarySummation: "Summen (BG-22)", LineTotalAmount: "Summe Positionen (BT-106)",
  TaxBasisTotalAmount: "Nettobetrag (BT-109)", TaxTotalAmount: "Steuerbetrag (BT-110)", GrandTotalAmount: "Bruttobetrag (BT-112)",
  TotalPrepaidAmount: "Bereits gezahlt (BT-113)", AllowanceTotalAmount: "Abschläge (BT-107)", ChargeTotalAmount: "Zuschläge (BT-108)",
  SpecifiedTradeAllowanceCharge: "Ab-/Zuschlag (BG-20/21)", PaymentReference: "Verwendungszweck (BT-83)", SellerOrderReferencedDocument: "Auftragsreferenz (BT-14)", DuePayableAmount: "Zahlbetrag (BT-115)", IncludedSupplyChainTradeLineItem: "Rechnungszeile (BG-25)",
  SpecifiedTradeProduct: "Artikel", BilledQuantity: "Menge (BT-129)", NetPriceProductTradePrice: "Nettopreis (BT-146)",
  // UBL
  AccountingSupplierParty: "Verkäufer (BG-4)", AccountingCustomerParty: "Käufer (BG-7)", LegalMonetaryTotal: "Summen (BG-22)",
  InvoiceLine: "Rechnungszeile (BG-25)", CustomizationID: "Profil (BT-24)", DocumentCurrencyCode: "Währung (BT-5)", IssueDate: "Rechnungsdatum (BT-2)",
  DueDate: "Fälligkeit (BT-9)", PayableAmount: "Zahlbetrag (BT-115)", TaxInclusiveAmount: "Bruttobetrag (BT-112)", TaxExclusiveAmount: "Nettobetrag (BT-109)",
  LineExtensionAmount: "Nettobetrag Zeile/Positionen", PaymentMeans: "Zahlungsart (BG-16)",
};

function xmlLokal(n) { return (n.localName || n.nodeName); }

function xmlBaumHtml(el, tiefe = 0, eltern = "") {
  const name = xmlLokal(el);
  const praefix = el.prefix ? `<span class="xv-p">${esc(el.prefix)}:</span>` : "";
  const bt = XML_BT[eltern + "/" + name] || XML_BT[name];
  const attr = [...el.attributes].filter(a => !a.name.startsWith("xmlns")).map(a => ` <span class="xv-a">${esc(a.name)}</span>=<span class="xv-v">"${esc(a.value)}"</span>`).join("");
  const kinder = [...el.children];
  const text = kinder.length ? "" : (el.textContent || "").trim();
  const kopf = `<span class="xv-t">&lt;${praefix}${esc(name)}</span>${attr}<span class="xv-t">&gt;</span>${bt ? ` <span class="xv-bt">${esc(bt)}</span>` : ""}`;
  if (!kinder.length) return `<div class="xv-z" data-such="${esc((name + " " + text + " " + (bt || "")).toLowerCase())}">${kopf}<span class="xv-x">${esc(text)}</span></div>`;
  return `<details class="xv-d" ${tiefe < 3 ? "open" : ""}><summary data-such="${esc((name + " " + (bt || "")).toLowerCase())}">${kopf} <span class="xv-n">${kinder.length}</span></summary>
    <div class="xv-k">${kinder.map(k => xmlBaumHtml(k, tiefe + 1, name)).join("")}</div></details>`;
}

function xmlHuebsch(xml) {
  // einfache Formatierung mit Einrückung (für die Quelltextansicht und den Download)
  try {
    const doc = new DOMParser().parseFromString(xml, "application/xml");
    if (doc.querySelector("parsererror")) return xml;
    const aus = [];
    const rek = (n, e) => {
      if (n.nodeType === 3) { const t = n.textContent.trim(); if (t) aus.push("  ".repeat(e) + t); return; }
      if (n.nodeType === 8) { aus.push("  ".repeat(e) + `<!--${n.textContent}-->`); return; }
      if (n.nodeType !== 1) return;
      const attr = [...n.attributes].map(a => ` ${a.name}="${a.value.replace(/"/g, "&quot;")}"`).join("");
      const k = [...n.childNodes].filter(c => c.nodeType === 1 || (c.nodeType === 3 && c.textContent.trim()) || c.nodeType === 8);
      if (!k.length) aus.push("  ".repeat(e) + `<${n.nodeName}${attr}/>`);
      else if (k.length === 1 && k[0].nodeType === 3) aus.push("  ".repeat(e) + `<${n.nodeName}${attr}>${k[0].textContent.trim().replace(/&/g, "&amp;").replace(/</g, "&lt;")}</${n.nodeName}>`);
      else { aus.push("  ".repeat(e) + `<${n.nodeName}${attr}>`); k.forEach(c => rek(c, e + 1)); aus.push("  ".repeat(e) + `</${n.nodeName}>`); }
    };
    rek(doc.documentElement, 0);
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + aus.join("\n");
  } catch (e) { return xml; }
}

function xmlFarbig(text) {
  return esc(text).replace(/(&lt;\/?)([\w:.-]+)/g, '$1<span class="xv-t">$2</span>')
    .replace(/([\w:.-]+)=(&quot;|")(.*?)(&quot;|")/g, '<span class="xv-a">$1</span>=<span class="xv-v">"$3"</span>');
}

// quelle: API-Pfad (z. B. "xml/zahlung/12") oder {daten, dateiname}
async function xmlAnsicht(quelle, titel) {
  toast("XML wird gelesen …");
  let d;
  try { d = typeof quelle === "string" ? await api(quelle) : await api("xml", {method: "POST", body: quelle}); }
  catch (e) { return toast(e.message, true); }
  const huebsch = xmlHuebsch(d.xml || "");
  const st = {ok: ["✓", "var(--gruen)"], warnung: ["!", "#b8860b"], fehler: ["✕", "var(--rot)"], hinweis: ["ℹ", "var(--leise)"]};
  const off = d.offiziell || {};
  const offFehler = (off.schritte || []).reduce((n, s) => n + s.meldungen.filter(m => m.stufe === "fehler").length + (s.status === "fehler" && !s.meldungen.length ? 1 : 0), 0);
  const fehler = off.moeglich && off.gueltig !== null && off.gueltig !== undefined ? offFehler : (d.pruefungen || []).filter(p => p.stufe === "fehler").length, warn = (d.pruefungen || []).filter(p => p.stufe === "warnung").length;
  const u = d.uebersicht, r = u?.rechnung || {}, v = u?.verkaeufer || {};
  const hg = document.createElement("div");
  hg.className = "modal-hg";
  hg.innerHTML = `<div class="modal" style="width:min(1150px,97vw);max-height:88vh;display:flex;flex-direction:column;overflow:hidden">
    <h3 style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap">${esc(titel || "XML-Ansicht")} <span class="hinweis" style="font-weight:400">${esc(d.dateiname || "")} · ${esc(d.quelle || "")}</span></h3>
    <div class="reiter-zeile" style="display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap">
      <button class="btn prim" data-xr="pruef">Prüfung ${fehler ? `<span style="color:#fff;background:var(--rot);border-radius:8px;padding:0 6px">${fehler}</span>` : warn ? `<span>(${warn} Hinweise)</span>` : d.art ? "✓" : ""}</button>
      <button class="btn" data-xr="ansicht">Übersicht</button><button class="btn" data-xr="baum">Baum</button><button class="btn" data-xr="text">Quelltext</button>
      <span style="flex:1"></span>
      <input id="xvSuche" placeholder="Suchen (Element, Wert, BT-Nummer) …" style="width:260px">
      <button class="btn" id="xvKopie">Kopieren</button><button class="btn" id="xvLaden">Herunterladen</button>
    </div>
    <div style="flex:1;overflow:auto;min-height:300px;border:1px solid var(--linie);border-radius:6px;padding:10px;background:#fff">
      <div data-xs="pruef">
        <div id="xvOff">${xmlOffiziellHtml(d.offiziell)}</div>
        <h4 style="margin:14px 0 6px">Schnellprüfung</h4>
        <p style="margin-top:0"><b>${esc(d.art || "XML")}</b>${d.profil ? ` · Profil <code>${esc(d.profil)}</code>` : ""}${d.wohlgeformt === false ? ` · <b style="color:var(--rot)">nicht wohlgeformt</b>` : ""}</p>
        <table class="liste" style="max-width:900px">${(d.pruefungen || []).map(p => `<tr><td style="width:24px;text-align:center;font-weight:700;color:${st[p.stufe]?.[1] || "inherit"}">${st[p.stufe]?.[0] || ""}</td><td>${esc(p.text)}</td></tr>`).join("")}</table>
      </div>
      <div data-xs="ansicht" style="display:none;height:100%"></div>
      <div data-xs="baum" style="display:none;font:12.5px/1.55 Consolas,Menlo,monospace" id="xvBaum"></div>
      <pre data-xs="text" style="display:none;margin:0;font:12.5px/1.5 Consolas,Menlo,monospace;white-space:pre-wrap;word-break:break-all" id="xvText"></pre>
    </div>
    <div class="knoepfe"><button class="btn prim" data-x="0">Schließen</button></div></div>`;
  document.body.appendChild(hg);
  let baumFertig = false;
  const zeige = k => {
    $$("[data-xr]", hg).forEach(b => b.classList.toggle("prim", b.dataset.xr === k));
    $$("[data-xs]", hg).forEach(s => s.style.display = s.dataset.xs === k ? "" : "none");
    if (k === "baum" && !baumFertig) {
      const doc = new DOMParser().parseFromString(d.xml || "", "application/xml");
      $("#xvBaum", hg).innerHTML = doc.querySelector("parsererror") ? `<p style="color:var(--rot)">${esc(doc.querySelector("parsererror").textContent)}</p>` : xmlBaumHtml(doc.documentElement);
      baumFertig = true;
    }
    if (k === "ansicht" && !$("[data-xs=ansicht]", hg).innerHTML) xmlAnsichtZeigen($("[data-xs=ansicht]", hg), d);
    if (k === "text" && !$("#xvText", hg).innerHTML) $("#xvText", hg).innerHTML = xmlFarbig(huebsch);
    suchen();
  };
  const suchen = () => {
    const w = ($("#xvSuche", hg).value || "").trim().toLowerCase();
    $$("#xvBaum [data-such]", hg).forEach(el => el.classList.toggle("xv-treffer", !!w && el.dataset.such.includes(w)));
    if (w) $$("#xvBaum .xv-treffer", hg).forEach(el => { let p = el.parentElement; while (p && p !== hg) { if (p.tagName === "DETAILS") p.open = true; p = p.parentElement; } });
    const pre = $("#xvText", hg);
    if (pre.innerHTML) {
      pre.innerHTML = xmlFarbig(huebsch);
      if (w) {
        const re = new RegExp("(" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")(?![^<]*>)", "gi");
        pre.innerHTML = pre.innerHTML.replace(re, '<mark>$1</mark>');
      }
    }
    const erster = $(".xv-treffer, #xvText mark", hg);
    if (erster && w) { const box = erster.closest("[data-xs]").parentElement; box.scrollTop += erster.getBoundingClientRect().top - box.getBoundingClientRect().top - box.clientHeight / 2; }
  };
  $$("[data-xr]", hg).forEach(b => b.onclick = () => zeige(b.dataset.xr));
  const ein = $("#xvEinrichten", hg);
  if (ein) ein.onclick = async () => {
    ein.disabled = true; ein.textContent = "wird eingerichtet … (1–3 Minuten)";
    try { await api("xml/einrichten", {method: "POST"}); } catch (e) { ein.disabled = false; ein.textContent = "Jetzt einrichten"; return toast(e.message, true); }
    const warte = async () => {
      if (!document.body.contains(hg)) return;
      const s = await api("xml/pruefung").catch(() => null);
      const st = s && s.einrichtung;
      if (st && st.laeuft) return setTimeout(warte, 3000);
      if (st && st.fehler) { ein.disabled = false; ein.textContent = "Erneut versuchen"; return toast(st.fehler, true); }
      toast("Offizielle Prüfung eingerichtet");
      hg.remove(); xmlAnsicht(quelle, titel);
    };
    setTimeout(warte, 3000);
  };
  let zs; $("#xvSuche", hg).oninput = () => { clearTimeout(zs); zs = setTimeout(suchen, 200); };
  $("#xvKopie", hg).onclick = async () => { try { await navigator.clipboard.writeText(huebsch); toast("XML kopiert"); } catch (e) { toast("Kopieren nicht möglich", true); } };
  $("#xvLaden", hg).onclick = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([d.xml || ""], {type: "application/xml"}));
    a.download = (d.dateiname || "rechnung").replace(/\.(pdf|xml)$/i, "") + ".xml"; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  };
  const zu = () => hg.remove();
  $("[data-x='0']", hg).onclick = zu;
  hg.onclick = e => { if (e.target === hg) zu(); };
  hg.addEventListener("keydown", e => { if (e.key === "Escape") zu(); });
  window.addEventListener("hashchange", zu, {once: true});
}

// Eigene Datei wählen (XML oder PDF) und anzeigen
function xmlDateiWaehlen() {
  const i = document.createElement("input");
  i.type = "file"; i.accept = ".xml,.pdf,application/xml,text/xml,application/pdf";
  i.onchange = async () => {
    const f = i.files[0]; if (!f) return;
    if (f.size > 25 * 1024 * 1024) return toast("Die Datei ist größer als 25 MB.", true);
    xmlAnsicht({dateiname: f.name, daten: await dateiAlsBase64(f)}, "XML-Ansicht");
  };
  i.click();
}

function xmlOffiziellHtml(o) {
  if (!o) return "";
  if (!o.moeglich) {
    const v = o.verfuegbar || {};
    return `<div class="kachel" style="border-left:4px solid var(--akzent);margin-bottom:6px"><b>Offizielle Prüfung (Regeln der KoSIT und der CEN)</b>
      <p style="margin:6px 0">Sie braucht einmalig zwei Zusatzpakete für Python: Saxon-HE (führt die Prüfregeln aus) und lxml (Schemaprüfung), zusammen etwa 45 MB, Internetverbindung nötig. Die Regelwerke selbst sind im Programm enthalten.${o.grund && o.grund !== "nicht eingerichtet" ? `<br><span style="color:var(--rot)">${esc(o.grund)}</span>` : ""}</p>
      ${ICH.rechte.inhaber ? `<button class="btn prim" id="xvEinrichten">Jetzt einrichten</button>` : `<span class="hinweis">Einrichten kann der Inhaber.</span>`}</div>`;
  }
  const st = {ok: ["✓", "var(--gruen)", "bestanden"], fehler: ["✕", "var(--rot)", "Fehler"], warnung: ["!", "#b8860b", "Hinweise"], uebersprungen: ["–", "var(--leise)", "nicht anwendbar"]};
  const kopf = o.gueltig === true ? `<div style="font-size:16px;font-weight:700;color:var(--gruen)">✓ Gültige E-Rechnung</div>`
    : o.gueltig === false ? `<div style="font-size:16px;font-weight:700;color:var(--rot)">✕ Nicht gültig</div>`
    : `<div style="font-size:16px;font-weight:700;color:var(--leise)">Keine offizielle Prüfung möglich</div>`;
  return `<div class="kachel" style="border-left:4px solid ${o.gueltig === true ? "var(--gruen)" : o.gueltig === false ? "var(--rot)" : "var(--linie)"};margin-bottom:6px">
    <div style="display:flex;gap:12px;align-items:baseline;flex-wrap:wrap">${kopf}<span class="hinweis">Offizielle Prüfung mit den Regeln, die auch der KoSIT-Validator verwendet</span></div>
    <table class="liste" style="margin-top:6px">${(o.schritte || []).map(s => `<tr><td style="width:24px;text-align:center;font-weight:700;color:${st[s.status][1]}">${st[s.status][0]}</td>
      <td><b>${esc(s.name)}</b> <span class="hinweis">${st[s.status][2]}${s.hinweis ? " · " + esc(s.hinweis) : ""}</span>
      ${s.meldungen.length ? `<div style="margin-top:4px">${s.meldungen.map(m => `<div style="margin:3px 0"><span style="font-weight:600;color:${m.stufe === "fehler" ? "var(--rot)" : "#b8860b"}">${esc(m.regel || (m.stufe === "fehler" ? "Fehler" : "Hinweis"))}</span> ${esc(m.text.replace(/^\[[^\]]+\]\s*-?\s*/, ""))}${m.ort ? `<div class="hinweis" style="font-family:monospace;font-size:11px;word-break:break-all">${esc(m.ort.replace(/\{[^}]*\}/g, "").replace(/\[namespace-uri\(\)='[^']*'\]/g, ""))}</div>` : ""}</div>`).join("")}</div>` : ""}</td></tr>`).join("")}</table></div>`;
}

// Reiter „Übersicht“: offizielle XRechnung-Visualisierung der KoSIT (wie in DMS-Programmen), sonst vereinfachte Darstellung
function xmlAnsichtZeigen(ziel, d) {
  if (d.ansicht_html) {
    ziel.innerHTML = `<div style="display:flex;gap:8px;align-items:center;margin:-4px 0 6px"><span class="hinweis" style="flex:1">Darstellung mit der XRechnung-Visualisierung der KoSIT · Felder ohne Inhalt werden nicht angezeigt · Reiter im Fenster: Übersicht, Details, Zusätze, Anlagen, Laufzettel</span>
      <button class="btn" type="button" id="xvDruck">Drucken / PDF</button><button class="btn" type="button" id="xvNeu">In neuem Fenster</button></div>
      <iframe id="xvRahmen" sandbox="allow-scripts allow-downloads allow-modals" style="width:100%;height:calc(88vh - 215px);min-height:380px;border:1px solid var(--linie);border-radius:6px;background:#fff"></iframe>`;
    $("#xvRahmen", ziel).srcdoc = d.ansicht_html;
    const fenster = drucken => {
      const url = URL.createObjectURL(new Blob([d.ansicht_html], {type: "text/html"}));
      const w = window.open(url, "_blank");
      if (!w) return toast("Das Fenster wurde vom Browser blockiert.", true);
      if (drucken) w.addEventListener("load", () => setTimeout(() => w.print(), 300));
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    };
    $("#xvDruck", ziel).onclick = () => fenster(true);
    $("#xvNeu", ziel).onclick = () => fenster(false);
    return;
  }
  const u = d.uebersicht, r = u?.rechnung || {}, v = u?.verkaeufer || {};
  const grund = d.ansicht_grund === "nicht eingerichtet" ? "Die offizielle Ansicht steht nach dem einmaligen Einrichten der Prüfung zur Verfügung (Reiter Prüfung › „Jetzt einrichten“)."
    : d.ansicht_grund ? `Offizielle Ansicht nicht verfügbar: ${d.ansicht_grund}.` : "";
  if (!u) { ziel.innerHTML = `<p class="hinweis">${esc(grund || "Keine Rechnungsdaten erkannt.")}</p>`; return; }
  const box = (titel, zeilen) => `<div class="kachel" style="margin-bottom:10px"><h4 style="margin:0 0 6px;color:var(--akzent)">${titel}</h4><table class="liste">${zeilen.filter(z => z[1] !== "" && z[1] != null).map(([l, w]) => `<tr><td style="width:38%;color:var(--leise)">${esc(l)}</td><td>${w}</td></tr>`).join("")}</table></div>`;
  ziel.innerHTML = `${grund ? `<p class="hinweis" style="margin-top:0">${esc(grund)} Vereinfachte Darstellung:</p>` : ""}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:1000px">
      ${box("Verkäufer", [["Name", esc(v.name || "")], ["Anschrift", esc([v.strasse, [v.plz, v.ort].filter(Boolean).join(" "), v.land].filter(Boolean).join(", "))], ["USt-IdNr.", esc(v.ustid || "")], ["Steuernummer", esc(v.steuernr || "")], ["E-Mail", esc(v.email || "")], ["Telefon", esc(v.telefon || "")]])}
      ${box("Rechnungsdaten", [["Rechnungsnummer", esc(r.nummer || "")], ["Rechnungsdatum", r.datum ? datum(r.datum) : ""], ["Rechnungsart", esc(r.typ || "")], ["Leistungsdatum", r.lieferdatum ? datum(r.lieferdatum) : ""], ["Währung", esc(r.waehrung || "")], ["Verwendungszweck", esc(r.verwendungszweck || "")]])}
      ${box("Gesamtbeträge", [["Summe netto", eur(r.netto || 0)], ["Umsatzsteuer", r.ust != null ? `${eur(r.ust)}${r.ust_satz != null ? ` (${n2(r.ust_satz, 0)} %)` : ""}` : ""], ["Gesamtsumme brutto", eur(r.brutto || 0)], ["Bereits gezahlt", r.vorausbezahlt ? eur(r.vorausbezahlt) : ""], ["Fälliger Betrag", `<b>${eur(r.zahlbetrag || 0)}</b>`]])}
      ${box("Zahlungsdaten", [["Fällig", r.faellig ? datum(r.faellig) : ""], ["Skonto", r.skonto ? `${n2(r.skonto, 1)} % bis ${datum(r.skonto_bis)}` : ""], ["Zahlungsbedingungen", esc(r.zahlungsbedingung || "").replace(/\n/g, "<br>")], ["IBAN", esc(v.iban || "")], ["BIC", esc(v.bic || "")]])}
    </div>
    ${(u.zeilen || []).length ? `<div class="kachel" style="max-width:1000px"><h4 style="margin:0 0 6px;color:var(--akzent)">Positionen</h4><table class="liste"><tr><th>Art.-Nr.</th><th>Bezeichnung</th><th class="r">Menge</th><th class="r">Einzelpreis</th><th class="r">Netto</th></tr>
      ${u.zeilen.map(z => `<tr><td>${esc(z.artnr || "")}</td><td>${esc(z.bezeichnung || "").replace(/\n/g, "<br>")}</td><td class="r">${n2(z.menge || 0, (z.menge || 0) % 1 ? 3 : 0)} ${esc(z.einheit || "")}</td><td class="r">${z.menge ? eur((z.netto || 0) / z.menge) : ""}</td><td class="r">${eur(z.netto || 0)}</td></tr>`).join("")}</table></div>` : ""}`;
}
