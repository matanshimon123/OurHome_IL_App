// OurHome IL service worker — network first, cache as fallback, a friendly offline page for pages that can't load.
const CACHE_NAME = 'ourhome-pop-2';
const OFFLINE_URL = '/static/offline.html';
const ASSETS_TO_CACHE = [
  OFFLINE_URL,
  '/static/css/style.css?v=pop2',
  '/static/js/pop.js?v=pop2',
  '/static/js/expense-sheet.js?v=pop2',
  '/static/icons/favicon.png',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

// Install - cache the design system + the offline page
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS_TO_CACHE).catch(err => {
      console.log('Cache addAll error (non-critical):', err);
    }))
  );
  self.skipWaiting();
});

// Activate - clean old caches (including the pre-redesign Bootstrap / Font Awesome / Chart.js cache)
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
  );
  self.clients.claim();
});

// Fetch - network first, fallback to cache; pages with nothing cached get the offline page
self.addEventListener('fetch', event => {
  const req = event.request;
  // Skip non-GET and API requests (never serve stale family data)
  if (req.method !== 'GET' || req.url.includes('/api/')) return;

  event.respondWith(
    fetch(req)
      .then(response => {
        if (response.status === 200 && new URL(req.url).origin === self.location.origin) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(req, copy));
        }
        return response;
      })
      .catch(() => caches.match(req).then(hit => {
        if (hit) return hit;
        if (req.mode === 'navigate') return caches.match(OFFLINE_URL);
        return Response.error();
      }))
  );
});
