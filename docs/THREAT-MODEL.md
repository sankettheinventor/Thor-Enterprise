# THOR Enterprise — Threat Model & Detection

THOR's job is to let an **untrusted** AI cook build software without being able to harm the host, exfiltrate
data, escape its scope, or lie its way to a merge. This document states the threat model (STRIDE), the
layered controls that block each threat, and — the part most systems skip — **how THOR KNOWS an attack is
happening** (the Threat Detector). It follows the security invariants THOR governs by (defense-in-depth,
least privilege, default-deny, never-trust-always-verify, positive input validation, audit-for-incident).

## Trust boundaries
1. **Cook ↔ room** — the cook is fully untrusted code running inside a sealed container.
2. **Room ↔ host** — the control plane; holds the ledger, signing material, and operator credentials.
3. **Room ↔ network** — egress only through the one-door gateway.
4. **Operator ↔ plane** — the human authority; the only mint of a merge.
5. **Plane ↔ verification** — the verdict runs cook-authored test code (now sealed).

## STRIDE → control (defense in depth)
| Threat (STRIDE) | Attack | Primary control | Backstop |
|---|---|---|---|
| **Spoofing** | forge an operator signature / replay an approval | Ed25519 over `card-id\|payload-hash\|nonce`, one-time nonce, registered keys only | co-signed operator registration; `signature.rejected` detected |
| **Tampering** | edit the audit ledger; fabricate a claim/test | SHA-256 hash-chain (Ed25519-signed rows); verdict-from-reality | `verify_chain` on every boot/replay (fail-closed) + ledger-tamper detection |
| **Repudiation** | "I didn't approve that" | append-only signed ledger; every security action recorded with context | crash-replay rebuilds exact state |
| **Information Disclosure** | exfiltrate data / steal the model/plane secret | one-door egress allowlist (IP-pinned, :443, SSRF-guarded); **verification sandbox** (no net, minimal env) | egress denials → exfiltration detection |
| **Denial of Service** | fork-bomb, resource exhaust, fill the ledger | per-room mem/cpu/**pids** limits; bounded API inputs | governor-alarm detection |
| **Elevation of Privilege** | write outside scope; escape the container | read-only root, cap_drop ALL, no-new-privileges, non-root, traversal guards; in-room hook + verdict scope-containment | out-of-scope denials → scope-probing detection |

## The verification boundary (the cage's own blind spot, now closed)
The verdict runs the **cook-authored** verifier/regression test. That code is untrusted. It now executes in a
**sealed ephemeral container** (network-disabled, read-only root, non-root, caps dropped, pids/mem limits,
**minimal env** — no API token / DB creds / signing material — against a repo COPY) whenever a real cook is
in play (`THOR_COOK` set). Proven: `tools/qa/prove_verify_sandbox.py` (secret/host-write/network all blocked).

## Host-side git (another untrusted-input-execution boundary, closed)
The cook writes `/work` including its `.git`, and THOR runs host-side git (`add`/`commit`/`checkout`/`push`)
on that repo. A planted `.git/hooks/*` or a `core.fsmonitor`/`core.sshCommand` config would execute on the
plane — RCE. Every host-side git invocation now runs with those neutralised via `-c` flags that override the
repo's local config (`core.hooksPath=/dev/null`, `core.fsmonitor=`, `core.sshCommand=`,
`protocol.ext.allow=never`). Proven: `tools/qa/prove_git_hook_safety.py`.

## How we KNOW an attack is happening — the Threat Detector
`sentinel/threat_detector.py` reads the tamper-evident ledger + the egress decision log over a sliding window
and turns the cage's stream of denials into **named, scored, STRIDE-tagged** signals. The Sentinel runs it
periodically (throttled); a crossed threshold records `threat.detected` (incident-response audit) and a
**CRITICAL** signal escalates to a halt. The cockpit shows them live at `GET /threats`.

| Signature | STRIDE | Source events | Threshold / window | Action |
|---|---|---|---|---|
| `scope-probing` | Elevation of Privilege | `action.decided` (deny) | ≥5 / 300s | record |
| `exfiltration-attempt` | Information Disclosure | gateway egress denials | ≥5 / 300s | record |
| `signature-forgery` | Spoofing | `signature.rejected` | ≥3 / 300s | record |
| `dishonest-cook` | Tampering | `dishonesty.caught` | ≥1 | record |
| `governor-alarm` | Denial of Service | `security.alarm` / `sentinel.kill` | ≥1 | record |
| `ledger-tamper` | Tampering | `verify_chain` = false | 1 | **HALT** |

Detection is **defense-in-depth, never the enforcement** — the attack is already blocked by the time it is
counted. Signatures are an **allow-list of known shapes**; new shapes are added explicitly. Proven:
`tools/qa/prove_threat_detection.py` (four staged attacks → named/scored/ledgered; tamper → halt).

## Invariants (how THOR satisfies each)
1. **Secrets never in source/logs** — credentials come from env; gateway `UPSTREAM_CRED` is env-only; the cook carries its own model token (never injected by THOR).
2. **AuthN ≠ AuthZ** — the API bearer token is transport-only; *authority* to merge is a separate Ed25519 operator signature a token cannot mint.
3. **Untrusted input is hostile** — positive (allow-list) validation at the API edge (`feature_id`/`command` patterns, bounded bodies); the cook's output is judged from reality, never trusted.
4. **Crypto from libraries** — Ed25519 / SHA-256 / X25519-ChaCha20 from `cryptography`; constant-time token compare.
5. **Default deny** — the Leash denies undeclared scope; egress denies non-allowlisted; the verdict escalates the unverifiable.
6. **Bounded blast radius** — one-time nonces, scoped rooms, per-room limits; no god-mode token (it can't sign).
7. **Tamper-evident audit** — the signed hash-chain, verified on boot/replay; every security action recorded for incident reconstruction.
8. **Documented threat model** — this file.

## Egress isolation (defense in depth, kernel + userspace)
The room sits on a **per-cook** `thor-room-net-<id>` created **`internal=True`** — Docker installs the kernel
iptables rules that give it **no route to the internet at all**; only that cook's own dual-homed gateway
(`thor-leash-gateway-<id>`) bridges it to the shared `thor-egress-net`. So the **L3 backstop is the network
topology** (the cook cannot reach the internet even if the proxy were bypassed), and the gateway's IP-pinned,
:443-only, SSRF-guarded allowlist is the **L7** layer on top.

## Parallel cooks (per-room isolation, no shared singleton)
Every request already carries a `room_id`/`feature_id`, so each one-door cook gets its OWN gateway on its OWN
internal room-net keyed by that id. Two real cooks therefore run **truly in parallel**, each behind its own
door enforcing **exactly its own allowlist** — there is no shared gateway to swap allowlists out from under a
peer, and **no global serialization lock**. Inter-room lateral movement stays architecturally prevented: a
cook's room-net is private to that cook (the shared egress-net is outside-facing only, and each gateway is the
sole bridge for its own room-net). The resolver retries transient DNS failures so a cold-start hiccup never
turns an allowlisted host into a spurious egress deny (which would also wrongly inflate exfiltration
detection) — an unresolvable allowlisted host is an operational 502, distinct from a security deny. Proven:
`tools/qa/prove_parallel_cooks.py` (two concurrent cooks, each reaches only its own host, blocked from the
peer's, both gateways alive simultaneously).

## RBAC — multiple users on one host (authN ≠ authZ, two layers)
Three rank-ordered roles — **viewer** (read-only) < **operator** (run the SDLC flow: queue/stop features, run
commands) < **commander** (the authority surface: approve/reject cards, register users). Each user carries a
**per-user API token** AND a **per-user Ed25519 key**, and the two never blur:
- **Transport (authN + coarse authZ)** — the token proves *who* is calling and gates the mutating surface by
  role at the HTTP edge (`thor_http_auth.require_role`): a Viewer's token can't mutate (403), an Operator's
  can't reach `/approve` (403), only a Commander's reaches the authority surface. A bad/absent token is 401.
- **Authority (the real authZ)** — a merge is minted ONLY by an Ed25519 signature, and now ONLY a
  **commander's** registered key may sign one (`Manager.authorized_signers` holds commander keys only;
  registering a key as operator/viewer *removes* it from the signer set). A token — any token, even a
  Commander's — can NEVER mint a merge; that takes the offline signing key.

Config is env-driven like the rest (`THOR_USERS` = JSON `[{id, role, token, pubkey}]`); when unset the legacy
single-token/open posture applies, so `make qa`/`make prove` (no token) pass unchanged. Proven:
`tests/test_rbac.py` (fast lane) + `tools/qa/prove_rbac.py` (both layers, three roles).

RBAC is enforced on **every served surface**, not just the dashboard: the Manager API (:7100,
provision/destroy = operator, raw `events/append` = commander) and the Self-Audit API (:7150, benchmark =
operator) carry the same role gates, and `require_token`/`require_role` are **RBAC-aware** — when `THOR_USERS`
is set a valid per-user token is required even if the legacy `THOR_API_TOKEN` is unset (they no longer fall
open on an RBAC-only deployment — AUD-rbac-failopen). Sensitive **reads** (audit feed, caught lies, threats,
cost, the board) require a **viewer** token when RBAC is on, so the audit/threat feed is not world-readable
and the viewer role is meaningful; liveness (`/health/system`), the SSE `/stream` (an `EventSource` cannot
send an auth header; it emits only ledger seq numbers), the public VAPID key, and the static shell stay open.

**By design (least authority):** only the highest-authority action — minting a merge — requires an Ed25519
*signature*; operator/viewer actions are gated by token + role, not a signature. So a commander's per-user key
is exercised (it signs merges) while operator/viewer keys are **registered identities** (the authority anchor
for co-signing a new commander, or for elevation) that no current action challenges. This is intentional, not
an omission: the cockpit never has to hold an operator signing key in the browser to run the build flow.

## Hardening added this pass
- **Secret files** owner-only (`0600`/`0700`): the Ed25519 signing key and the VAPID key.
- **Rate limit** (sliding window, per client) on the mutating surface — bounds brute-force / abuse (429); tune via `THOR_RL_MAX`/`THOR_RL_WINDOW`.
- **Threat thresholds** are per-deployment tunable (`THOR_THREAT_SCOPE`/`_EGRESS`/`_FORGERY`).

## Honest residuals (tracked in `GAP-AND-RISK-REGISTER.md`)
Single-host (no k8s fleet — RBAC for multiple users on one host is now CLOSED, see below); non-Python work escalates to a human (no mechanical coverage); detection is **static-threshold rules** (tunable), not a learned baseline (no ML anomaly model yet); the during-build `/work` disk cap needs an FS-level quota at deploy (the verification sandbox is already capped). Inter-room lateral movement is **architecturally prevented** today: sealed rooms have NO network, and one-door rooms now sit on **per-cook internal nets** (each cook's own gateway is the sole bridge — rooms cannot see each other), so parallel cooks are isolated without serialization. None are silent — each is a register row.
