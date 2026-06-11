# Security Policy — THOR Enterprise

THOR Enterprise is a governance product. A vulnerability in THOR is not just a bug —
it is a hole in the moat. We treat security reports as the highest-priority input
this project receives, and we hold ourselves to the same standard we hold agents to:
**no reproduction, no bug — and every confirmed hole becomes a permanent regression test.**

## How to report

**GitHub Security Advisories (preferred):** go to the repository **Security** tab and
create a private advisory.

**Email:** sankettoraskar.business@gmail.com with the subject line **[THOR SECURITY]**.

Please do **not** open a public issue for a suspected vulnerability.

## What to include

- A description of the vulnerability
- Steps to reproduce (a minimal proof of concept — ideally a failing test)
- The attack scenario it enables: who can exploit it, and what they gain
- The THOR Enterprise version / commit affected
- A suggested fix, if you have one

## What we consider a vulnerability

Anything that weakens one of the five guarantees:

- **Leash bypass** — any way for an in-room agent to write, execute, or reach the
  network without the action being judged by the policy engine first (a second pair
  of hands; a path around `InRoomProxy`)
- **Policy tampering** — any way for a room to read, modify, or influence its own
  FrozenPolicy, or to affect which policy is loaded
- **Verdict gaming** — any way to obtain a `done` verdict that diverges from reality:
  feeding the GovEngine actor-controlled inputs, defeating the divergence detector,
  fooling coverage-of-diff with hollow tests, or exploiting the freshness window
  between verdict and merge
- **Contract violations** — any way for a room to express or effect self-approval,
  exceed the six-message protocol, or impersonate the control plane
- **Signature forgery or replay** — any acceptance of a forged, replayed, or
  stale Ed25519 signature for Sig 1/2/3; any path to merge without a verified Sig 3
- **Ledger integrity** — any way to edit, reorder, or insert events without
  `verify_chain` failing; any second writer path around the Manager
- **Room escape** — container breakout, identity-token forgery that survives,
  privilege escalation inside a room, or persistence after room destruction
- **Egress bypass** — any network path out of a one-door room that does not pass
  the governed gateway (including DNS, redirects, IPv6); credential exposure
  inside a room
- **Fail-open behavior** — any failure of the Leash, Sentinel, or watchdog paths
  that allows work to continue ungoverned instead of halting
- **Sentinel blindness** — any way to make canary violations pass silently, or to
  prevent a justified halt from physically destroying rooms / blocking provisioning
- **Supply chain** — attacks via the npm package, PyPI dependencies, the room base
  image, or GitHub releases

## What we do NOT consider a vulnerability

- Attacks requiring the attacker to already have full write access to the host
  machine or the Postgres superuser (the host is the trust anchor; see THREAT-MODEL)
- False positives in policy pattern checks (open a regular issue instead)
- Social engineering of the human commander (a documented limitation — THOR governs
  agents, not the judgment of the person signing)
- Resource exhaustion requiring the commander's own signed approval of the workload
- Findings in third-party components (Docker, Postgres, Gitea, Ollama) without a
  THOR-specific exploitation path — report those upstream, though we appreciate a
  heads-up if THOR's defaults make them exploitable

## Disclosure timeline

| Stage | SLA |
|---|---|
| Acknowledgment | 48 hours |
| Preliminary assessment | 7 days |
| Fix for CRITICAL issues (moat-weakening) | 30 days |
| Public disclosure | After the fix is released, or 90 days — whichever comes first |

## Coordinated disclosure

We follow responsible disclosure. We will:

- Credit the reporter in the CHANGELOG and the Hall of Fame, unless anonymity is requested
- Coordinate disclosure timing with the reporter
- Never pursue legal action against good-faith security researchers
- Convert every confirmed vulnerability's proof of concept into a permanent test in
  the adversarial proving suite, so the same hole can never silently reopen

## Hall of fame

Researchers who have responsibly disclosed vulnerabilities to THOR Enterprise:

*(none yet — be the first)*
