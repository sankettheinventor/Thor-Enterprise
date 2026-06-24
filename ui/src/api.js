// Same-origin client for the Manager DashboardAPI. No secrets here — reads are public; the SIGN path
// (sign.js) holds the operator key in the browser only.
// Normally same-origin (the PWA is served by the plane at :7080/app/). Fall back to the local plane if the
// origin isn't http(s) (e.g. opened from a non-served context) so the app still reaches the API.
const base = (typeof location !== 'undefined' && /^https?:/.test(location.origin || '')) ? location.origin : 'http://localhost:7080'

export async function get(path) {
  const r = await fetch(base + path, { cache: 'no-store' })
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

export async function post(path, body) {
  const r = await fetch(base + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  })
  return r.json()
}

export async function del(path) {
  const r = await fetch(base + path, { method: 'DELETE' })
  return r.json()
}
