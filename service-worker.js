// App shell only; NEVER cache authenticated API responses or secret results.
const CACHE = 'wichtelzauber-static-v1';
const FILES = ['/static/styles.css','/static/app.js','/static/icon.svg'];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || !url.pathname.startsWith('/static/')) return;
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
});
