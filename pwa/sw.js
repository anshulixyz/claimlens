/* Minimal service worker — caches the app shell for offline use. */
const CACHE = "claimlens-v13";
const SHELL = ["./", "index.html",
  "ui-base.js", "ui-messenger.js", "ui-landing.js", "app.js",
  "styles.css", "manifest.json",
  "icon.svg", "icon-192.png", "icon-512.png",
  "vendor/react.production.min.js", "vendor/react-dom.production.min.js", "vendor/htm.umd.js"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).catch(() => hit))
  );
});
