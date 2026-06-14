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
The room sits on `thor-room-net` created **`internal=True`** — Docker installs the kernel iptables rules that
give it **no route to the internet at all**; only the dual-homed gateway bridges to `thor-egress-net`. So the
**L3 backstop is the network topology** (the cook cannot reach the internet even if the proxy were bypassed),
and the gateway's IP-pinned, :443-only, SSRF-guarded allowlist is the **L7** layer on top.

## Hardening added this pass
- **Secret files** owner-only (`0600`/`0700`): the Ed25519 signing key and the VAPID key.
- **Rate limit** (sliding window, per client) on the mutating surface — bounds brute-force / abuse (429); tune via `THOR_RL_MAX`/`THOR_RL_WINDOW`.
- **Threat thresholds** are per-deployment tunable (`THOR_THREAT_SCOPE`/`_EGRESS`/`_FORGERY`).

## Honest residuals (tracked in `GAP-AND-RISK-REGISTER.md`)
Single-host / single-commander (no RBAC, no k8s fleet); non-Python work escalates to a human (no mechanical coverage); detection is **static-threshold rules** (tunable), not a learned baseline (no ML anomaly model yet); the during-build `/work` disk cap needs an FS-level quota at deploy (the verification sandbox is already capped). Inter-room lateral movement is **architecturally prevented** today (sealed rooms have NO network; one-door rooms share `thor-room-net` but are serialized one-at-a-time) — per-room networks remain the k8s-era hardening. None are silent — each is a register row.
