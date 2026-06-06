# THOR — CTO / Leash / Multi-Room Scaling (RESOLVED from the original `cto.js`)

> Resolves: is the rule-checker inside the CTO or separate, and how does one CTO watch many rooms
> without overload? Answered from a file:line read of the original `cto.js` (in `_reference/`), not
> memory. This is the locked shape for **Task 3 (CTO + Leash)**. Sits under `THOR-WIRING-MANUAL.md`.

## The key finding — the CTO does two jobs with very different costs
- **A. Thinking / planning (expensive, RARE):** match top-1% expert skills to a task, decide the
  approach, escalate big decisions to a CEO card. The "menu planner." Happens at task start + on
  genuinely hard/ambiguous calls — NOT every keystroke.
- **B. Per-action rule-checking (cheap, CONSTANT, mechanical — NOT an LLM):** every edit/write/bash/
  commit is checked by deterministic code: `scanContent(content, PATCH/BACKDOOR/SECRET_PATTERNS)`
  (regex lists), `filesRead.has(path)` (read-before-edit), file-type regex, scope (PM owns scope),
  `markSkill` bookkeeping. Outcomes: AUTO-ALLOW (default, fast) / ALLOW+GUIDE (inject a skill
  reminder) / BLOCK (a pattern matched) / ESCALATE (only the hard ones go up). Returns in
  microseconds. (`cto.js checkEdit ~848-940`.) Plus a crawler every ~2s scanning recent actions for
  cross-action patterns (also mechanical).

**The insight:** the per-action checker is cheap and mechanical, not an LLM on every move — which is
exactly why one guard can watch a chef without overload. ~99% of actions resolve by fast pattern
checks; only the rare hard case costs real "thinking."

## The resolved architecture (one brain, two seats, split by cost)
1. **THE LEASH = the per-action rule-checker** — CHEAP, MECHANICAL, **PER-ROOM**, ALWAYS-ON. Sits in
   each room's action path; every cook action → allow / guide / block BEFORE it executes, using
   deterministic checks (scope [PM-owned], forbidden patterns, read-before-edit, injected-skill
   reminders). Strict by design ("forbidden work = never"). Parallel-safe because it's cheap code,
   not an LLM. **Fail-closed:** can't decide / governor down → BLOCK.
2. **THE CTO = the planner / decider** — EXPENSIVE, RARE, **SHARED** across rooms. Plans a feature
   (matches top-1% skills, sets scope, the approach) at task START; handles ESCALATIONS the Leash
   kicks up. One CTO serves MANY rooms because it's only invoked at task-start + on escalations.

So: the **rule-checker (Leash) is per-room and mechanical**; the **CTO (planner/decider) is shared**
and only thinks on start + escalation. Same brain, two seats.

## Why one CTO doesn't overload across many rooms
- Per-action cost (high-frequency) lives in the per-room Leash = O(cheap) × N rooms, parallel, no
  shared bottleneck.
- CTO cost (expensive) = per-task-start + per-escalation = LOW frequency; one CTO queues+serves those
  for many rooms. If escalation volume grows, the CTO scales independently (stateless per-decision)
  WITHOUT touching the per-room leashes.

## Consistency
- Matches the drift doc: "CTO's decide-before = the Leash" — the Leash IS the CTO's cheap per-action
  decide-before; the CTO process is the expensive planner/escalation head.
- Matches DRIFT 3 (skill loop): skills MATCHED by the CTO at plan time → INJECTED into the room (the
  Leash surfaces the reminder during work) → VERIFIED after (R1). Same loop, split by cost.
- Keeps "Manager = mechanism only": none of this decision logic lives in the Manager.

## Confirmed decision
Planner + per-move approver are the same head chef, but **seated separately**: a per-room **Leash**
(strict, cheap, mechanical, in every room's action path) + a shared **CTO** (menu-planner + escalation
decider, invoked at start + on hard cases only). **Wire Task 3 in this shape.**

## Still to verify BEFORE wiring Task 3 (T3 entry criteria — read next when we reach T3)
- Module 2 (Leash) PRD + Module 7 (SDLC) PRD: confirm the per-action check list (patterns, scope,
  read-before-edit, skill-inject) matches the original's mechanical checks.
- `cto.js` escalation path: what becomes a CEO card — so Leash → CTO → CEO escalation is wired right.
- Where "scope" is owned (original: PM owns scope, CTO checks quality) — keep that split in Enterprise.
