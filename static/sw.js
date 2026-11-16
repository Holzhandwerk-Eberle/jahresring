// Jahresring: minimaler Service Worker, damit Browser (v. a. Chrome auf Android) die Seite als App installieren.
// Es wird nichts zwischengespeichert – alle Daten kommen immer frisch vom Büro-PC.
// Ist das Programm (noch) nicht erreichbar – z. B. weil Windows das Fenster beim Hochfahren wiederherstellt, bevor
// das Programm läuft –, erscheint eine Warteseite, die im Sekundentakt nachsieht und sich dann von selbst öffnet.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
const WARTESEITE = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Jahresring</title>' +
  '<body style="font:16px sans-serif;padding:24px;background:#f5f2ed;color:#2b2520">' +
  '<h2 id="t">Jahresring startet …</h2><p id="p">Einen Moment bitte, das Programm wird gerade gestartet. Die Seite öffnet sich von selbst.</p>' +
  '<p><button onclick="location.reload()">Erneut versuchen</button></p>' +
  '<script>let n=0;const pruefen=async()=>{try{const r=await fetch("/api/version?wartet=1",{cache:"no-store"});if(r.ok){location.reload();return;}}catch(e){}' +
  'if(++n===30){document.getElementById("t").textContent="Jahresring ist nicht erreichbar";' +
  'document.getElementById("p").textContent="Der Büro-PC ist aus, das Programm läuft nicht oder das Gerät ist nicht im selben WLAN. Die Seite öffnet sich von selbst, sobald das Programm wieder läuft.";}' +
  'setTimeout(pruefen,n<60?1000:5000);};setTimeout(pruefen,1000);</script></body>';
self.addEventListener("fetch", e => {
  if (e.request.mode !== "navigate") return;   // nur Seitenaufrufe, alles andere geht direkt an den Server
  e.respondWith(fetch(e.request).catch(() => new Response(WARTESEITE, {status: 503, headers: {"Content-Type": "text/html; charset=utf-8"}})));
});
