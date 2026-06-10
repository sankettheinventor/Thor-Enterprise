// T7 — the human-signs authority, ported byte-for-byte from the proven cockpit.html so the Manager
// verifies identical material. The operator's Ed25519 private key is generated once and stored in THIS
// browser's localStorage; it NEVER leaves the device. We sign the Manager's one-time challenge material
// (card-id|payload-hash|nonce); the nonce is consumed on use → replayed/forged signatures are rejected.
import * as ed from '@noble/ed25519'
import { sha512 } from '@noble/hashes/sha512'
import { get, post } from './api.js'

ed.etc.sha512Sync = (...m) => sha512(ed.etc.concatBytes(...m)) // ed25519 needs a sync sha512

const b64url = (b) =>
  btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')

export function operatorKey() {
  let hex = localStorage.getItem('thor_op_key')
  if (!hex) {
    hex = [...ed.utils.randomPrivateKey()].map((x) => x.toString(16).padStart(2, '0')).join('')
    localStorage.setItem('thor_op_key', hex) // generated once; in prod this is the CEO's provisioned key
  }
  return Uint8Array.from(hex.match(/../g).map((h) => parseInt(h, 16)))
}

async function registered() {
  const priv = operatorKey()
  const pub = b64url(ed.getPublicKey(priv))
  await post('/operator/register', { signer_pub: pub })
  return { priv, pub }
}

// Sign a card. Returns the Manager's verdict ({verified} or {verified:false, reason}).
export async function signCard(cardId) {
  const { priv, pub } = await registered()
  const ch = await get('/cards/' + cardId + '/challenge')
  if (ch.error) return { verified: false, reason: ch.error }
  const sig = b64url(ed.sign(new TextEncoder().encode(ch.material), priv)) // signed locally with YOUR key
  return post('/approve', { card_id: cardId, signature: sig, signer_pub: pub, nonce: ch.nonce })
}
