# Contributing to THOR Enterprise

Thank you — sincerely. THOR exists to make AI development that doesn't increase human
work, but removes the repetitive parts while keeping the work **commanded by you and
me: the human.** If that's a future you want to help build, you're welcome here, and
your contribution will be honored.

## The culture

THOR's contribution culture mirrors its product philosophy: **claims are testimony;
tests are truth.** The same standards THOR applies to AI agents apply to all of us,
maintainer included.

## The six rules

1. **Read the actual code first.** Documentation drifts; source doesn't.
2. **One gap per PR.** Name the gap (a Gap Register row or an issue number) in the
   commit message. No drive-by refactors of working modules.
3. **Prove over the live plane.** A green unit test is testimony. Your PR must keep
   `make prove` green from clean — real rooms, real Postgres, real attacks.
4. **Never weaken the moat.** Any change that makes the policy engine more permissive,
   the verdict more forgiving, or the worker more trusted will be rejected regardless
   of what else it improves. The moat gets harder, never easier.
5. **Adversarial proof for boundary changes.** If your PR touches the worker, the
   policy engine, or the network boundary, it ships with the attack that fails against it.
6. **Update the register.** Found a gap you're not fixing? Add the row with file:line.
   Honest open gaps outrank silent ones.

## Reporting a bug

THOR applies its own standard to itself: **no reproduction, no bug.**

1. Open a GitHub issue using the bug template.
2. Include a minimal reproduction — ideally a failing test, otherwise exact steps,
   your platform (Linux/WSL2 version, Docker, Postgres), and the THOR commit.
3. A confirmed bug's reproduction becomes a permanent regression test, so the same
   bug can never silently return. By reporting well, you make THOR stricter forever.

**Security issues are different:** never open a public issue. See [SECURITY.md](SECURITY.md).

### Bug response targets

| Severity | Meaning | First response | Fix target |
|---|---|---|---|
| **S1 — Moat** | A governance guarantee weakened (treat as security) | 48 h (via SECURITY.md) | 30 days |
| **S2 — Critical** | THOR unusable; ledger or state corruption | 72 h | 14 days |
| **S3 — Major** | A feature broken; workaround exists | 72 h | Next release |
| **S4 — Minor** | Cosmetic, docs, small annoyances | 7 days | Best effort |

These are honest targets from a solo maintainer, not a paid SLA. If a target slips,
the issue will say so and why — the same radical honesty as the Gap Register.

## Suggesting ideas

Have a way to make THOR better — a new feature, a sharper check, a whole new
direction? Open a GitHub Discussion (or an issue tagged `idea`). The bar for ideas is
generous; the bar for merging is the six rules. The best ideas come with a sketch of
how they'd be **proven**, not just built.

## Community

Join the THOR Discord to discuss governance, share what you're building, and help
shape the roadmap: **[invite link — placeholder, server being set up]**.

## Contributor rights and project ownership

THOR Enterprise — its name, code, and the Human Command Development (HCD)
framework — is created and owned by **Sanket Toraskar**, and all rights are reserved
to him (see [LICENSE](LICENSE)).

By submitting a contribution, you agree that:

- The contribution is your original work, or you have the right to submit it.
- You **retain copyright** in your contribution.
- You grant Sanket Toraskar a **perpetual, worldwide, irrevocable, royalty-free,
  transferable license** to use, modify, distribute, sublicense, and **relicense**
  your contribution as part of THOR Enterprise — including under commercial licenses
  granted per the LICENSE.

This is what lets the project stay free for personal use while commercial use is
licensed centrally: one steward must hold the rights to grant. Your name stays on
your work — contributors are credited in the CHANGELOG.

Thank you in advance. We will honor it.

— Sanket Toraskar, founder
