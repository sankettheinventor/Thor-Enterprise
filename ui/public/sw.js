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

// Native push — a THOR-styled OS notification arrives even with the app closed. The payload is the
// server's encrypted alert (title/body/url); the push service only relayed ciphertext.
self.addEventListener('push', (e) => {
  let d = {}
  try { d = e.data ? e.data.json() : {} } catch (_) { d = { body: e.data && e.data.text() } }
  e.waitUntil(self.registration.showNotification(d.title || 'THOR', {
    body: d.body || 'A card needs your attention.',
    icon: d.icon || '/app/icon.svg',
    badge: '/app/icon.svg',
    tag: d.tag || 'thor',
    data: { url: d.url || '/app/' },
    requireInteraction: true,            // a signature decision shouldn't vanish on its own
    vibrate: [80, 40, 80],
  }))
})

self.addEventListener('notificationclick', (e) => {
  e.notification.close()
  const url = (e.notification.data && e.notification.data.url) || '/app/'
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cs) => {
      for (const c of cs) { if (c.url.includes('/app') && 'focus' in c) return c.focus() }
      return self.clients.openWindow(url)
    })
  )
})
