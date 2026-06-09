# Dashboard / Cockpit — UX backlog (POST-correctness, separate track)

**This is NOT a correctness defect and NOT part of the verification campaign.** THOR's job is
governance, and the governance works (see `VERIFICATION-REPORT.md`). The cockpit must be *legible*,
but it is a UI polish pass to be scheduled AFTER correctness — do not let it touch governance code.

Scope reviewed: `dashboard/cockpit.html` (965 lines) — 5 top nav tabs (Home · Decide · Work · Watch ·
Security), ~12 buttons, ~20+ distinct panels.

## The problem (your words: "too many options / cluttered")

The cockpit shows **everything at once**, and several panels are near-duplicates of the same signal,
so the eye has nowhere to rest and the ONE thing that needs a human — *a card to sign* — competes with
~20 always-on widgets.

Observed overlap / redundancy:
- **Trust score shown 3×:** `Meta-trust`, `System meta-trust`, `Project health` overlap.
- **Health shown 2–3×:** `System health`, `Brain Status`, `Sentinel`/`Self-Audit` status tiles.
- **CTO split into 4 panels:** `CTO Decisions`, `CTO Details`, `CTO Violations`, `Guarding files`.
- **Two activity streams:** `Activity feed` and `Activity logbook`.
- **Two pulse/health framings:** `Project health` and `Project pulse`.
- **Decision surfaced twice:** `Decisions waiting` and `Decisions waiting for you` + the `Decide` tab.

## Smallest cuts (progressive disclosure first — remove little, hide a lot)

Priority order; each is independent and low-risk:

1. **Make "sign" the hero.** When a card needs a signature, the *Decisions waiting for you* panel +
   `Sign` button should dominate the Home view; everything else dims. When nothing waits, show one calm
   "Nothing waiting" line. (This is the single highest-value change.)
2. **Collapse the 3 trust readouts into one `Meta-trust` number** with a tooltip/expand for the
   contributing signals. Remove `System meta-trust` + the duplicate in `Project health`.
3. **One `System health` strip** (Manager · Leash · Sentinel · Self-Audit dots). Fold `Brain Status`
   into it. Remove the standalone duplicate tiles.
4. **One CTO panel** with tabs/disclosure for Decisions / Violations / Guarded files; drop `CTO Details`
   as a separate always-on panel (open on click).
5. **One activity stream.** Keep `Activity feed` (live); move `Activity logbook` behind a "history"
   toggle.
6. **Merge `Project health` + `Project pulse`** into a single feature-status strip
   (Queued · Planning · Building · In progress · Done) — the kanban counts already cover this.
7. **Move `Token spend`, `Open risks`, `Tests`, `Triggers`, benchmark/retro controls** behind the
   `Watch` tab (progressive disclosure) — they are monitoring, not the primary CEO action.

## What to KEEP front-and-centre (the CEO's actual job)
- The signature queue (sign / reject, with the legible one-sentence "why").
- `Lies caught` (the honesty meter) and `Last merge` — proof the moat is working.
- A single health strip and a single trust number.

## Guardrails
- UI only. No change to `dashboard/service.py` / `dashboard_api.py` semantics, the verify/record path,
  or any governance module. The cockpit is a *projection*; it must stay read-only and never become a
  second source of authoritative state (manager `state_summary` remains the truth).
- Re-run `make qa` after any change to confirm the gate stays green.
