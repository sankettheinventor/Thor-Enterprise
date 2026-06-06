"""
THOR Module 9 — Mobile / Remote + Legible Refusal.

The phone is a REMOTE HEAD on the same Manager truth (M3) — not a second system with its own state.
A merge approved on the phone and one on the desktop (M8) are the same action against the same
Manager. Security is strict (the phone is the most-exposed surface): E2EE through a zero-knowledge
relay, Ed25519 signed approvals, a command allowlist, no inbound port (outbound tunnel), device-key
custody + revocation, and stale-safety on flaky connections.

Files → PRD §2 sub-modules:
    crypto.py        9.2 E2EE — X25519 + ChaCha20-Poly1305 sealed boxes (cryptography lib)
    relay.py         9.2 the Cloudflare relay model — a dumb, zero-knowledge pipe (ciphertext only)
    bridge.py        9.1 PhoneBridge (control-plane side) + 9.5 Command Allowlist + revocation
    allowlist.py     9.5 the bounded command set the phone may issue
    phone_client.py  9.3/9.4/9.7/9.8 — the device-side stand-in (signing, legible refusal, offline)

Bootstrap notes (flagged Rule 9): the postman/Cloudflare bridge is rebuilt CLEAN (Rule 10 — _reference
is read-only); the mobile UI per PRD §4 is deferred — the E2EE channel + signing + allowlist (the
security-critical substance) is what's built and proven.
"""
