/* The only script Boule loads, and it exists for two things the platform requires:
   a PWA cannot install without a service worker, and a service worker cannot be
   registered without script. Everything else here is server-rendered.

   This is also where the device key is requested on the page's own behalf: the call is
   idempotent server-side, so it mints a key only when this device has none. It is
   repeated here as well as in the worker because a worker's fetch cannot be relied on
   to have stored the cookie in every browser. */
(function () {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
  }
  try {
    fetch('/api/device', { method: 'POST', credentials: 'same-origin' }).catch(function () {});
  } catch (_) {}
})();
