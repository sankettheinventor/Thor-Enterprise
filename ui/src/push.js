// Native push subscription (Web Push / VAPID). Asks the OS for permission, subscribes with the server's
// application key, and registers the device so THOR can alert it when a card needs a signature — even
// with the app closed. The private VAPID key never leaves the server.
import { get, post } from './api.js'

function b64ToU8(b64) {
  const s = atob(b64.replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from([...s].map((c) => c.charCodeAt(0)))
}

export function pushSupported() {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

export async function enablePush() {
  if (!pushSupported()) return { ok: false, reason: 'push not supported on this device/browser' }
  const perm = await Notification.requestPermission()
  if (perm !== 'granted') return { ok: false, reason: 'notifications permission denied' }
  const reg = await navigator.serviceWorker.ready
  const { key } = await get('/push/vapid')
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: b64ToU8(key),
  })
  await post('/push/subscribe', sub.toJSON())
  return { ok: true }
}
