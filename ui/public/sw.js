// THOR cockpit service worker — makes the app installable + loads instantly, WITHOUT ever caching live
// governance data. It caches ONLY the static app shell (under /app/). Every API + the SSE /stream pass
// straight to the network, so the phone never shows a stale ledger, verdict, or card (no stale truth).
// Bump on every shell change so the activate handler purges the previous cache — otherwise a redeploy with
// new hashed asset names keeps serving the OLD cached index and the app renders a blank screen.
const CACHE = 'thor-cockpit-v3'
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
  if (e.request.method !== 'GET' || !url.pathname.startsWith('/app/') || url.pathname === '/app/stream') {
    return  // API / stream / non-GET -> straight to network (live truth, never cached)
  }
  // The HTML SHELL is NETWORK-FIRST: always fetch the latest index so it references the CURRENT hashed
  // assets after a redeploy (this is what prevents the stale-shell blank screen); fall back to cache only
  // when offline. Content-hashed assets are immutable -> cache-first for instant loads.
  const isShell = e.request.mode === 'navigate' || url.pathname === '/app/' || url.pathname === '/app/index.html'
  if (isShell) {
    e.respondWith(
      fetch(e.request).then((resp) => {
        const copy = resp.clone()
        caches.open(CACHE).then((c) => c.put('/app/index.html', copy))
        return resp
      }).catch(() => caches.match('/app/index.html').then((h) => h || caches.match('/app/')))
    )
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
