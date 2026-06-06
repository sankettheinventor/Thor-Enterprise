# Module 9 — Mobile / Remote + Legible Refusal

The phone as a **remote head on the same Manager truth** — command from anywhere, securely. E2EE
through a **zero-knowledge relay**, **Ed25519 signed approvals**, a **command allowlist**, **no inbound
port** (outbound tunnel), **device-key revocation**, and **stale-safety** on flaky connections. Shares
Module 8's card + signature model (two heads, one truth). Spec:
[`../docs/PRD-Module-9-Mobile.md`](../docs/PRD-Module-9-Mobile.md).

**Decisions (flagged Rule 9):** the postman/Cloudflare bridge is rebuilt **clean** (`_reference` is
read-only, Rule 10); the mobile **app UI** per PRD §4 is deferred (no Node; a SPA isn't smoke-testable).
What's built + proven is the **security-critical substance**: real E2EE, the relay, allowlist, signing,
replay/dedup, revocation, offline.

## Files (→ PRD §2 sub-modules)
| File | Sub-module | Role |
|---|---|---|
| `crypto.py` | 9.2 E2EE | X25519 + ChaCha20-Poly1305 sealed boxes (`cryptography`) |
| `relay.py` | 9.2 Relay | dumb, zero-knowledge pipe (ciphertext only; no inbound port) |
| `bridge.py` | 9.1 PhoneBridge + 9.5 | seal/push, open/verify, allowlist, device registry + revocation |
| `allowlist.py` | 9.5 | the bounded command set the phone may issue |
| `phone_client.py` | 9.3/9.4/9.7/9.8 | device-side: signing, legible refusal, offline stale-safety |

## Milestone (smoke `tools/smoke_mobile.py`)
**AC-1 + AC-2 + AC-3** — a real merge signed from a phone over an E2EE channel, where the relay can
neither read nor forge anything and the control plane exposes no inbound port. Command-from-anywhere
without weakening security.

## Smoke (NOT run until asked)
```bash
python tools/smoke_mobile.py   # Postgres + Manager + DashboardService + E2EE bridge + phone stand-in
```
`tests/mobile/` holds AC-1..AC-12 as deferred/skipped specs (never a false green).
