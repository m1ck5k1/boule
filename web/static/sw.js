/* Boule service worker — S6.

   Two jobs, and no third:
     1. make the app installable (a PWA cannot exist without one);
     2. at install, ask for a device key. The install IS the identity mechanism, which
        is why S6 was load-bearing rather than cosmetic.

   Caching is deliberately thin. Pages are NETWORK FIRST and never cached, because the
   tally must not be served out of a cache and presented as current — a stale number is
   the one thing this project cannot ship. Only the static shell is cached, and it can
   go stale without changing a figure. Boule therefore does NOT work offline, and the
   worker does not pretend it does: voting needs the network by definition.
*/
const SHELL = 'boule-shell-v2';
const SHELL_ASSETS = ['/static/boule.css', '/static/icon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL);
    await cache.addAll(SHELL_ASSETS);
    // Idempotent: the server mints a key only when this device has none, so a
    // reinstall neither forks the identity nor adds a row.
    try {
      await fetch('/api/device', { method: 'POST', credentials: 'same-origin' });
    } catch (_) { /* the page calls it too; never block install on it */ }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (key !== SHELL) await caches.delete(key);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(caches.match(req).then((hit) => hit || fetch(req)));
    return;
  }
  // Everything else — every page, every tally: go to the network. No cache, no lie.
  event.respondWith(fetch(req));
});
