// =====================================================================
//  Fertigungsleitstand (Kanban): Spalten = Arbeitsschritte, Karten = Aufträge
// =====================================================================
async function ansichtLeitstand() {
  kopf({krumen: [["Leitstand", "#/leitstand"]]});
  $(".wrap").classList.add("breit");
  const z = $("#inhalt");
  let d;
  const laden = async () => { d = await api("leitstand"); zeichnen(); };
  const heuteIso = heute();
  const karteHtml = k => {
    const ende = k.lieferung || k.plan_bis;
    const ueberfaellig = ende && ende < heuteIso && !k.lieferung;
    const pz = k.soll_h ? Math.min(100, k.ist_h / k.soll_h * 100) : 0, ueber = k.soll_h && k.ist_h > k.soll_h + 0.05;
    const i = d.schritte.indexOf(k.schritt);
    return `<div class="ls-karte" data-k="${k.id}">
      <div class="ls-kz"><a href="#/auftrag/${k.id}/werkstatt" class="ls-nr">${esc(k.nummer)}</a><span class="ls-status">${esc(k.status)}</span></div>
      <div class="ls-bez">${esc(k.bezeichnung)}</div>
      <div class="hinweis">${esc(k.kunde)}${k.positionen ? ` · ${k.positionen} Pos.` : ""}</div>
      ${k.soll_h || k.ist_h ? `<div class="ls-fs" title="Ist / Soll Stunden"><i style="width:${pz}%;${ueber ? "background:var(--rot)" : ""}"></i></div><div class="hinweis">${n2(k.ist_h, 1)} / ${n2(k.soll_h, 1)} h</div>` : ""}
      ${k.termin ? `<div class="hinweis">📅 ${esc(k.termin.typ)} ${datum(k.termin.von).slice(0, 6)}${k.termin.bis !== k.termin.von ? "–" + datum(k.termin.bis).slice(0, 6) : ""}</div>` : ""}
      ${ende ? `<div class="hinweis" style="${ueberfaellig ? "color:var(--rot);font-weight:600" : ""}">${k.lieferung ? "geliefert" : "fertig bis"} ${datum(ende)}</div>` : ""}
      ${k.montageberichte ? `<div class="hinweis">✍ ${k.montageberichte} Rapport${k.montageberichte > 1 ? "e" : ""}</div>` : ""}
      <div class="ls-pfeile"><button class="btn" data-zu="${i - 1}" ${i <= 0 ? "disabled" : ""} title="Schritt zurück">◀</button>
        <button class="btn" data-zu="${i + 1}" ${i >= d.schritte.length - 1 ? "disabled" : ""} title="Nächster Schritt">▶</button></div>
    </div>`;
  };
  const zeichnen = () => {
    z.innerHTML = `<div class="titel"><h2>Fertigungsleitstand</h2>
      <div class="rechts">${darf("einstellungen", 2) ? `<a class="btn" href="#/einstellungen/werkstatt">Arbeitsschritte ändern</a>` : ""}<button class="btn" id="lsNeu" title="Neu laden">↻</button></div></div>
      <p class="hinweis" style="margin-top:-6px">Aufträge mit Status ${d.status.map(esc).join(", ")}. Karten mit der Maus oder dem Finger in eine andere Spalte ziehen – oder mit ◀ ▶ weiterschieben.</p>
      <div class="ls-brett" style="--n:${d.schritte.length}">${d.schritte.map(s => {
        const ks = d.karten.filter(k => k.schritt === s);
        const st = (d.status_je_schritt || {})[s];
        return `<div class="ls-spalte" data-s="${esc(s)}"><div class="ls-kopf"><div>${esc(s)}${st ? `<div class="ls-st">→ ${esc(st)}</div>` : ""}</div><span>${ks.length}</span></div><div class="ls-liste">${ks.map(karteHtml).join("")}</div></div>`;
      }).join("")}</div>
      ${d.karten.length ? "" : `<div class="leer">Keine Aufträge in Arbeit. Aufträge erscheinen hier, sobald sie den Status ${d.status.map(esc).join(" / ")} haben.</div>`}`;
    $("#lsNeu").onclick = laden;
    $$("[data-zu]", z).forEach(b => b.onclick = ev => { ev.stopPropagation(); const k = d.karten.find(x => x.id === +b.closest(".ls-karte").dataset.k); verschieben(k, d.schritte[+b.dataset.zu], 9e9); });
    $$(".ls-karte", z).forEach(el => ziehbar(el));
  };
  const verschieben = async (k, schritt, sort) => {
    if (!k || !schritt) return;
    const liste = d.karten.filter(x => x.schritt === schritt && x.id !== k.id).sort((a, b) => a.sort - b.sort);
    // neue Sortierung: ans Ende oder vor die Karte, über der losgelassen wurde
    let pos = liste.findIndex(x => x.sort >= sort); if (pos < 0) pos = liste.length;
    liste.splice(pos, 0, k);
    k.schritt = schritt;
    liste.forEach((x, i) => x.sort = i + 1);
    zeichnen();
    try {
      for (const x of liste) await api("leitstand/" + x.id, {method: "PUT", body: {schritt, sort: x.sort}});
      const r = d.karten.find(x => x.id === k.id);
      const neu = await api("leitstand"); d = neu; zeichnen();
      if (r && neu.karten.find(x => x.id === k.id)?.status !== r.status) toast("Auftragsstatus: " + neu.karten.find(x => x.id === k.id).status);
    } catch (e) { toast(e.message, true); laden(); }
  };
  // Ziehen mit Maus und Finger (Pointer Events statt HTML-Drag&Drop, damit es auch auf dem Tablet geht)
  const ziehbar = el => {
    let start = null, geist = null, ziel = null;
    el.addEventListener("pointerdown", e => {
      if (e.target.closest("a,button") || e.button > 0) return;
      start = {x: e.clientX, y: e.clientY, id: e.pointerId};
    });
    el.addEventListener("pointermove", e => {
      if (!start) return;
      if (!geist) {
        if (Math.hypot(e.clientX - start.x, e.clientY - start.y) < 8) return;
        el.setPointerCapture(start.id);
        const r = el.getBoundingClientRect();
        geist = el.cloneNode(true); geist.classList.add("ls-geist"); geist.style.width = r.width + "px";
        geist.dataset.dx = start.x - r.left; geist.dataset.dy = start.y - r.top;
        document.body.appendChild(geist); el.classList.add("ls-weg");
      }
      e.preventDefault();
      geist.style.left = (e.clientX - geist.dataset.dx) + "px"; geist.style.top = (e.clientY - geist.dataset.dy) + "px";
      geist.style.display = "none"; const unter = document.elementFromPoint(e.clientX, e.clientY); geist.style.display = "";
      const sp = unter && unter.closest(".ls-spalte");
      $$(".ls-spalte.drop").forEach(x => x !== sp && x.classList.remove("drop"));
      if (sp) sp.classList.add("drop");
      ziel = sp ? {schritt: sp.dataset.s, vor: unter.closest(".ls-karte")} : null;
    });
    const ende = () => {
      if (geist) {
        geist.remove(); el.classList.remove("ls-weg"); $$(".ls-spalte.drop").forEach(x => x.classList.remove("drop"));
        if (ziel) {
          const k = d.karten.find(x => x.id === +el.dataset.k);
          const vor = ziel.vor && ziel.vor !== el ? d.karten.find(x => x.id === +ziel.vor.dataset.k) : null;
          verschieben(k, ziel.schritt, vor ? vor.sort - 0.5 : 9e9);
        }
      }
      start = geist = ziel = null;
    };
    el.addEventListener("pointerup", ende); el.addEventListener("pointercancel", ende);
  };
  await laden();
}
