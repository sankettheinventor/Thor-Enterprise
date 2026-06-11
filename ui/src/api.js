// Same-origin client for the Manager DashboardAPI. No secrets here — reads are public; the SIGN path
// (sign.js) holds the operator key in the browser only.
const base = typeof location !== 'undefined' ? location.origin : ''

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
