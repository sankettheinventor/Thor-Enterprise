# THOR — WIRING PHASE RULES (the working agreement)

We are NOT building new modules. We are ASSEMBLING the 17 built parts into one running,
enforcing system, then turning the ~144 acceptance tests into real gated tests.
Per the Gap & Risk Register. Follow these rules without exception.

## The 10 wiring rules

1. **WIRE, DON'T REDESIGN.** Connect the parts exactly as the PRDs + System Design doc specify.
   Do not improve, refactor, or add features while wiring. If you spot a new problem, append it
   to `docs/GAP-AND-RISK-REGISTER.md` and keep going — do NOT fix it inline.

2. **ONE GAP AT A TIME.** Fix exactly one register item per change, in the agreed order. Each change
   closes a specific numbered gap (C1, C2, ...). Name the gap in the commit. No bundling.

3. **WIRE THEN PROVE, PER MODULE.** For each module: (a) wire it into the real running system,
   (b) THEN un-skip its acceptance tests and make them real gated tests that pass against the
   wired thing. A test only counts if it runs against the wired path, not a smoke stand-in.

4. **BOTTOM-UP ORDER, NO JUMPING.** Wall → Manager → Leash → Contract/Scheduler → GovEngine
   → SDLC → Dashboard/Mobile → Sentinel → Self-Audit → Adapters. Don't touch a higher
   module until the one below it is wired + its tests pass.

5. **THE MOAT GETS HARDER, NEVER EASIER.** When wiring the Verdict Coordinator (C4), the engine must
   derive claim/contract/commit_window from trusted Manager/Contract state — NEVER accept them
   from the actor. No wiring shortcut may make a false "done" easier. If wiring would weaken the
   moat, STOP and ask.

6. **REAL EVIDENCE ONLY (still Rule 11).** Show real output. Never fake, assume, or hand-wave a pass.
   If something doesn't work, show the real error. A wired test that passes must pass for real.

7. **NO NEW STUBS; REMOVE OR PROMOTE THEM.** Wiring means replacing in-process stand-ins with real
   connections. Don't add new stubs. When you wire a seam, the old smoke-only path is replaced,
   not left beside the real one (no two ways to do the same thing).

8. **SINGLE SOURCE OF TRUTH, ENFORCED.** While wiring, make "Manager is the only EventLog writer"
   actually true (fix H6/H7): route every record through the Manager; remove direct `eventlog.append`
   bypasses; unify the Leash's separate chain into the Manager's. No competing ledgers.

9. **SHOW THE PLAN BEFORE THE CODE, ON ANYTHING STRUCTURAL.** For each gap that changes how modules
   connect (the run target, the Leash interceptor, the Verdict Coordinator, real halt), show the
   design in plain words FIRST. Owner approves, then code. Small/obvious wirings can proceed.

10. **STILL UNGOVERNED, STILL WSL, STILL ASK WHEN UNSURE.** THOR does not govern its own build (P7).
    WSL2/Linux paths only. Ambiguous or architectural fork not in the spec → stop and ask, never guess.

## Definition of "wired correctly" (the bar each gap must clear)
- The real product path does the thing (not a smoke script).
- Its acceptance tests run against that real path and pass for real.
- No stub remains for that seam; no second way to do it.
- The change is committed naming the gap it closed.
- The register row is updated: status → CLOSED, with the file:line of the wiring.

## Push discipline
- Commit per gap closed (small, named commits).
- Push to GitHub after each module is fully wired + its tests pass (a clean, working checkpoint).
- Do NOT push a half-wired module. A pushed checkpoint must run.
