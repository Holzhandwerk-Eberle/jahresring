// Jahresring: minimaler Service Worker, damit Browser (v. a. Chrome auf Android) die Seite als App installieren.
// Es wird nichts zwischengespeichert – alle Daten kommen immer frisch vom Büro-PC.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  if (e.request.mode !== "navigate") return;   // nur Seitenaufrufe, alles andere geht direkt an den Server
  e.respondWith(fetch(e.request).catch(() => new Response(
    '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><body style="font:16px sans-serif;padding:24px">' +
    '<h2>Jahresring ist nicht erreichbar</h2><p>Der Büro-PC ist aus, das Programm läuft nicht oder das Gerät ist nicht im selben WLAN.</p>' +
    '<p><button onclick="location.reload()">Erneut versuchen</button></p></body>',
    {status: 503, headers: {"Content-Type": "text/html; charset=utf-8"}})));
});
