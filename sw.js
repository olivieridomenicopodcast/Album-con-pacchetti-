const CACHE = 'raccoglitore-v4';
const ASSETS = ['./', './index.html', './buste.html', './manifest.json', './theme.js', './icon-192.png', './icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

function isHtmlRequest(req){
  return req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html');
}

self.addEventListener('fetch', e => {
  const req = e.request;

  // Pagine HTML: prova sempre la rete per prima, cosi' gli aggiornamenti
  // si vedono al primo caricamento invece che restare bloccati sulla
  // versione vecchia in cache. Cade sulla cache solo se offline.
  if (isHtmlRequest(req)) {
    e.respondWith(
      fetch(req).then(res => {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(req, clone));
        return res;
      }).catch(() => caches.match(req).then(cached => cached || caches.match('./index.html')))
    );
    return;
  }

  // Altri asset (css, immagini, icone): cache-first come prima.
  e.respondWith(
    caches.match(req).then(cached => {
      if (cached) return cached;
      return fetch(req).then(res => {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(req, clone));
        return res;
      }).catch(() => caches.match('./index.html'));
    })
  );
});
