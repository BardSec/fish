/* Fishing Atlas service worker.
 *
 * Strategy
 *   - App shell + core pages: precached on install; navigations are
 *     network-first, falling back to cache, then to the /offline page.
 *   - Static assets (css/js/icons/vendor): cache-first, refreshed in background.
 *   - Map tiles (OpenStreetMap): runtime cache-first, so areas you've already
 *     viewed keep working with no signal.
 *   - /api/*: always network. Data durability is handled by IndexedDB + the
 *     sync queue, not by caching API responses.
 */
const VERSION = 'v1';
const SHELL_CACHE = `fa-shell-${VERSION}`;
const STATIC_CACHE = `fa-static-${VERSION}`;
const TILE_CACHE = 'fa-tiles';
const TILE_MAX = 600; // cap cached tiles so storage doesn't grow unbounded

const CORE_PAGES = ['/', '/trips', '/trips/new', '/catches', '/map', '/pins', '/settings', '/offline'];
const CORE_ASSETS = [
  '/static/css/styles.css',
  '/static/js/db.js', '/static/js/api.js', '/static/js/sync.js', '/static/js/app.js',
  '/static/js/dashboard.js', '/static/js/trips.js', '/static/js/trip_form.js',
  '/static/js/trip_detail.js', '/static/js/catches.js', '/static/js/map.js',
  '/static/js/pins.js', '/static/js/settings.js',
  '/static/vendor/leaflet/leaflet.css', '/static/vendor/leaflet/leaflet.js',
  '/static/vendor/leaflet/images/marker-icon.png',
  '/static/vendor/leaflet/images/marker-icon-2x.png',
  '/static/vendor/leaflet/images/marker-shadow.png',
  '/manifest.webmanifest',
  '/static/icons/icon-192.png', '/static/icons/icon-512.png',
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const shell = await caches.open(SHELL_CACHE);
    // Tolerate individual misses (e.g. an icon not generated yet).
    await Promise.allSettled(CORE_PAGES.map(u => shell.add(new Request(u, { cache: 'reload' }))));
    const stat = await caches.open(STATIC_CACHE);
    await Promise.allSettled(CORE_ASSETS.map(u => stat.add(new Request(u, { cache: 'reload' }))));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keep = new Set([SHELL_CACHE, STATIC_CACHE, TILE_CACHE]);
    for (const k of await caches.keys()) if (!keep.has(k)) await caches.delete(k);
    await self.clients.claim();
  })());
});

function isTile(url) {
  return /tile\.openstreetmap\.org/.test(url.host) || /\.tile\./.test(url.host);
}

async function trimCache(name, max) {
  const cache = await caches.open(name);
  const keys = await cache.keys();
  if (keys.length > max) for (const k of keys.slice(0, keys.length - max)) await cache.delete(k);
}

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  // API: straight to network (offline handled by the app's local store).
  if (url.pathname.startsWith('/api/')) return;

  // Map tiles: cache-first runtime cache.
  if (isTile(url)) {
    event.respondWith((async () => {
      const cache = await caches.open(TILE_CACHE);
      const hit = await cache.match(request);
      if (hit) return hit;
      try {
        const res = await fetch(request);
        if (res.ok) { cache.put(request, res.clone()); trimCache(TILE_CACHE, TILE_MAX); }
        return res;
      } catch (e) { return hit || Response.error(); }
    })());
    return;
  }

  // Page navigations: network-first, fall back to cache, then offline page.
  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const res = await fetch(request);
        const shell = await caches.open(SHELL_CACHE);
        shell.put(request, res.clone());
        return res;
      } catch (e) {
        const cached = await caches.match(request);
        return cached || (await caches.match('/offline')) || Response.error();
      }
    })());
    return;
  }

  // Same-origin static assets: cache-first with background refresh.
  if (url.origin === self.location.origin) {
    event.respondWith((async () => {
      const cached = await caches.match(request);
      const network = fetch(request).then(res => {
        if (res.ok) caches.open(STATIC_CACHE).then(c => c.put(request, res.clone()));
        return res;
      }).catch(() => cached);
      return cached || network;
    })());
  }
});
