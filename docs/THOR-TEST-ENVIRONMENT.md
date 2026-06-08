# THOR ENTERPRISE — TEST ENVIRONMENT (so a green verdict is TRUSTWORTHY + reproducible)

WHY: "Claude Code says it passed" is only trustworthy if every test run starts from an IDENTICAL,
clean state and exercises the REAL wired system (live Postgres + real Docker rooms + the booted
control plane) — never in-process stand-ins. This spec defines that harness. It is the thing that
lets you (or CI) re-run any claim and get the same result.

## THE SHAPE (corrected — not "wire-container vs test-container")
THOR's control plane is ONE process (locked at T0 — one brain, not a mesh). It PROVISIONS room
containers as children — that is THOR working, not a test rig. So the separation we need is:

  A. THE SYSTEM        = one control-plane process + its child room containers + one Postgres.
  B. THE TEST HARNESS  = a reproducible, disposable wrapper that: boots a FRESH system from a known
                         clean state, runs the unified suite against it, captures real output, tears
                         everything down (no orphan rooms, no leftover ledger). Identical every run.

## THE TWO TEST LANES (fast feedback vs real proof — both must exist)
  LANE 1 — DEFAULT (fast, docker-free): `pytest`  → 145 deferred-deselected, the static + in-proc
    seam checks (e.g. S12 arch-lint). Runs in seconds. Gates every commit. No Docker, no Postgres.
  LANE 2 — DEFERRED PROVING (real, live): `pytest -m deferred` → boots the live plane + real Docker
    rooms + real Postgres; the module ACs + integration seam/flow tests run against REALITY.
    Slower (minutes). This is the lane whose green you TRUST for "it actually works."

## REPRODUCIBILITY REQUIREMENTS (what makes a verdict trustworthy)
  R1. FRESH STATE per deferred run: a throwaway Postgres (the existing thor-postgres bootstrap is
      fine, but the harness must DROP+recreate the schema, or use a uniquely-named test DB, so no
      run inherits another's ledger). Assert: ledger starts at the genesis event, not mid-history.
  R2. NO ORPHAN ROOMS: the harness reaps all `thor.room=1` containers before AND after the run.
      Assert `docker ps` shows zero THOR rooms at start and end (Task 1 already proved AC-12 no-orphans;
      the harness enforces it suite-wide).
  R3. REAL, NOT ASSERTED: every deferred test observes ground truth (docker inspect, host git log,
      a real HTTP call to the booted surface) — never a mocked return. (Rule 11.)
  R4. DETERMINISTIC TEARDOWN: pass or fail, the harness destroys rooms, stops the plane, drops the
      test DB. A failed run never poisons the next.
  R5. ONE COMMAND, SAME EVERYWHERE: `make test` (fast) and `make prove` (deferred/live) — identical
      for you, Claude Code, and CI. A claim is only "proven" if `make prove` is green from clean.
  R6. EVIDENCE CAPTURE: the deferred run writes a report (which ACs ran, real output snippets, docker
      ps before/after, replay-identical assertion) so a green is auditable, not just a word.

## WHO USES WHICH LANE
  - Claude Code, per task: wires the seam → runs LANE 2 for that module (`pytest -m deferred
    tests/<module>` + the new integration test) → shows real output → commits only if green.
  - You / trust check: run `make prove` yourself anytime to independently reproduce Claude Code's
    green. If it's green from clean on your machine, the verdict is trustworthy.
  - CI (later): runs LANE 1 on every push (fast gate) + LANE 2 nightly / pre-release (full proof).

## THE HARNESS PIECES TO BUILD (small, mechanical — OpenHands can do this)
  1. `tests/conftest.py` fixtures: `fresh_ledger` (drop+recreate test DB), `booted_plane` (start the
     control plane in-process or as a subprocess, yield its URLs, stop on teardown), `clean_docker`
     (reap THOR rooms before+after), `host_repo` (throwaway git repo for AC-1-style proofs).
  2. `Makefile`: `make test` (LANE 1), `make prove` (LANE 2 from clean), `make clean` (reap + drop DB).
  3. `tests/integration/` : the seam + golden-flow tests from Integration PRD §6 (built as we wire
     each task — test_flow_A, test_flow_B, test_seam_S5, test_edge_R1..R16, test_moat_adversarial).
  4. `docs/TEST-REPORT.md` (generated): the evidence capture from the last `make prove`.

## THE TRUST RULE (the point of all this)
A task is DONE only when `make prove` is green FROM CLEAN — fresh ledger, real Docker rooms, real
output, deterministic teardown — and you can reproduce that green yourself. Claude Code's word is
the start; a reproducible green from clean is the proof. That is what makes the verdict trustworthy.
