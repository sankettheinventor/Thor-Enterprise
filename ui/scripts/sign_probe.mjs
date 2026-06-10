// Sign a material string with the SAME @noble/ed25519 + b64url encoding the React cockpit uses
// (src/sign.js), so a test can prove the BROWSER-produced signature is accepted by the Python Manager.
// Usage: node scripts/sign_probe.mjs <privHex> <material>   ->   {"pub": "...", "sig": "..."}
import * as ed from '@noble/ed25519'
import { sha512 } from '@noble/hashes/sha512'

ed.etc.sha512Sync = (...m) => sha512(ed.etc.concatBytes(...m))
const b64url = (b) => Buffer.from(b).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')

const [, , privHex, material] = process.argv
const priv = Uint8Array.from(privHex.match(/../g).map((h) => parseInt(h, 16)))
process.stdout.write(JSON.stringify({
  pub: b64url(ed.getPublicKey(priv)),
  sig: b64url(ed.sign(new TextEncoder().encode(material), priv)),
}))
