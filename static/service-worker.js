/* KDP AdCopy Generator – Service Worker */

const CACHE_NAME = "kdp-adcopy-v1";
const STATIC_ASSETS = [
  "/",
  "/static/styles.css",
  "/static/app.js",
  "/static/manifest.json",
];

// Install: cache static assets
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Fetch: serve from cache, fallback to network (cache-first for static, network-first for API)
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Always go network-first for API and POST requests
  if (
    event.request.method !== "GET" ||
    url.pathname.startsWith("/generate") ||
    url.pathname.startsWith("/export") ||
    url.pathname.startsWith("/admin")
  ) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      return (
        cached ||
        fetch(event.request).then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
      );
    })
  );
});
