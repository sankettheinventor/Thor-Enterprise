// THOR cockpit service worker — makes the app installable + loads instantly, WITHOUT ever caching live
// governance data. It caches ONLY the static app shell (under /app/). Every API + the SSE /stream pass
// straight to the network, so the phone never shows a stale ledger, verdict, or card (no stale truth).
const CACHE = 'thor-cockpit-v1'
const SHELL = ['/app/', '/app/index.html', '/app/manifest.webmanifest', '/app/icon.svg']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)
  // Only the static shell is cached. API/stream/anything else -> network only (live truth, never stale).
  if (e.request.method !== 'GET' || !url.pathname.startsWith('/app/') || url.pathname === '/app/stream') {
    return
  }
  e.respondWith(
    caches.match(e.request).then((hit) =>
      hit || fetch(e.request).then((resp) => {
        const copy = resp.clone()
        caches.open(CACHE).then((c) => c.put(e.request, copy))
        return resp
      })
    )
  )
})
