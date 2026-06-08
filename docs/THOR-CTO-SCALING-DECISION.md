# THOR ENTERPRISE — CTO / RULE-CHECKER / MULTI-ROOM SCALING (resolved from the real code)
# The question: is the rule-checker inside the CTO, or separate? And how does one CTO watch
# many chefs in many rooms without being overloaded? Answered from cto.js, not memory.

## WHAT THE ORIGINAL CODE ACTUALLY DOES (the key finding)
The original CTO does TWO kinds of work with VERY different costs:

  A. THINKING / PLANNING (expensive, rare): matching top-1% expert skills to a task,
     deciding the approach, escalating big decisions to a CEO card. This is the "menu planner."
     -- happens at task start + on genuinely hard/ambiguous calls. NOT every keystroke.

  B. PER-ACTION RULE-CHECKING (cheap, constant): every edit/write/bash/commit is checked, but
     the check is almost ENTIRELY MECHANICAL, not an LLM call:
       - scanContent(content, PATCH_PATTERNS / BACKDOOR_PATTERNS / SECRET_PATTERNS)  [regex lists]
       - filesRead.has(path)  [did it read before editing?]
       - file-type regex, scope (PM owns scope), markSkill bookkeeping
     Outcomes: AUTO-ALLOW (fast, default) / ALLOW+GUIDE (inject a skill reminder) /
     BLOCK (a pattern matched) / ESCALATE (only the hard ones go up).
     (cto.js checkEdit ~848-940: it's pattern matching + bookkeeping, returns allow/block in microseconds.)
  + a CRAWLER every 2s scanning recent actions for cross-action patterns (also mechanical).

THE INSIGHT THAT ANSWERS YOUR WORRY:
  The per-action "rule checker" is CHEAP and MECHANICAL. It is NOT an LLM reasoning on every move.
  That's exactly why one guard can watch a chef without being overloaded — 99% of actions are
  resolved by fast deterministic pattern checks; only the rare hard case costs real "thinking."

## THE RESOLVED ARCHITECTURE (your menu-planner vs rule-checker question)
Split the CTO's two jobs by COST, and that resolves where the rule-checker lives:

  1. THE LEASH = the per-action rule-checker (CHEAP, MECHANICAL, PER-ROOM, ALWAYS-ON).
     - Sits in EACH room's action path. Every cook action -> Leash decides allow/guide/block
       BEFORE it executes, using deterministic checks: scope (PM-owned), forbidden patterns
       (patch/backdoor/secret), read-before-edit, injected-skill reminders.
     - This is "keep the rule checker VERY STRICT so the chef does forbidden work = never."
       It is per-room and parallel-safe because it's cheap mechanical code, not an LLM.
     - Fail-closed: if it can't decide or the governor is down -> BLOCK.

  2. THE CTO = the menu-planner / decider (EXPENSIVE, RARE, SHARED across rooms).
     - Plans a feature (matches top-1% skills, sets scope, the approach) at task START.
     - Handles ESCALATIONS the Leash kicks up (the genuinely hard/ambiguous calls).
     - One CTO can serve MANY rooms because it's only invoked at task-start + on escalations,
       NOT on every keystroke. The constant per-action load lives in the cheap per-room Leash.

  => SO: the rule-checker (Leash) is PER-ROOM and mechanical; the CTO (planner/decider) is SHARED
     and only thinks on start + escalation. This is exactly your instinct: "embed skills via CTO
     as the menu-planner, keep the rule-checker strict, and don't load the CTO with every move."
     The code proves it works because the rule-checker was never an LLM in the first place.

## WHY THIS DOESN'T OVERLOAD ONE CTO ACROSS MANY ROOMS
  - Per-action cost (the high-frequency part) is in the per-room Leash = O(cheap) x N rooms,
    parallel, no shared bottleneck.
  - CTO cost (the expensive part) is per-task-start + per-escalation = LOW frequency. One CTO
    can queue+serve those for many rooms. If escalation volume ever grows, the CTO scales
    independently (it's stateless per-decision) WITHOUT touching the per-room leashes.
  - The "brain" the human approved = chef-who-plans (CTO) + chef-who-approves-each-move (Leash),
    together — but PHYSICALLY SPLIT by cost: planner shared, checker per-room. Same brain, two seats.

## DRIFT-DOC CONSISTENCY CHECK
  - Matches THOR-DRIFT-CHECK: "CTO's decide-before = the Leash" (FAITHFUL). Confirmed: the Leash
    IS the CTO's cheap per-action decide-before; the CTO process is the expensive planner/escalation head.
  - Matches the skill loop fix (DRIFT 3): skills MATCHED by CTO at plan time -> INJECTED into the
    room (the Leash surfaces the reminder during work) -> VERIFIED after (R1). Same loop, split by cost.
  - Keeps "Manager = mechanism only" intact: none of this decision logic lives in the Manager.

## THE DECISION TO CONFIRM WITH THE HUMAN
  YES — planner + per-move approver are "the same head chef," but we SEAT THEM SEPARATELY:
    - per-room LEASH = the strict, cheap, mechanical rule-checker in every room's action path.
    - shared CTO = the menu-planner + the escalation decider, invoked at start + on hard cases only.
  This is how one CTO controls many chefs in many rooms without overload. Wire Task 3 in this shape.

## STILL TO VERIFY BEFORE WIRING TASK 3 (read these PRDs + code next)
  - Module 2 (Leash) PRD + Module 7 (SDLC) PRD: confirm the per-action check list (patterns, scope,
    read-before-edit, skill-inject) matches the original's mechanical checks.
  - cto.js escalation path (what becomes a CEO card) — so the Leash->CTO->CEO escalation is wired right.
  - Where "scope" is owned (original: PM owns scope, CTO checks quality) — keep that split in Enterprise.
