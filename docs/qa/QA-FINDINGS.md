# THOR QA Campaign — new findings register

New defects/observations surfaced by the verification campaign (separate from the four named bugs
BUG-1..4). Per the wiring rule "new problems → append to the register, don't fix inline." These are
candidates for triage; do NOT auto-fix working modules without sign-off.

| ID | Severity | Where | Finding | Status |
|----|----------|-------|---------|--------|
| FINDING-A | LOW–MED | `wall/provisioner.py:28` | `client = docker.from_env()` runs at **module import time**, so importing `ThorManager` (which imports `wall.provisioner`) **requires a live Docker daemon** — import fails with `DockerException` where no daemon/socket is reachable. Makes "docker-free" logic testing impossible for anything touching the Manager, and is a fragile import side-effect (a daemon hiccup breaks `import`). | Open — recorded Phase 1; consider lazy/deferred client init. |
| FINDING-B | **HIGH** | `sentinel/core.py:119-121` (`_destroy_rooms`) | `try: rooms = self.manager.state_summary()["rooms"] except Exception: return []`. If the Manager state is unreadable (e.g. Postgres down), a HALT enumerates **zero** rooms and physically destroys **nothing**, yet `halt()` records success (`rooms_halted=[]`). This **fails OPEN on the load-bearing C3 guarantee** ("a halt physically kills the rooms"): in exactly the degraded conditions that trigger a halt, the kill silently no-ops. Should fail closed — alarm/escalate, retry, or kill by Docker label rather than trusting DB state. | Open — Phase 3 audit; NOT fixed (working module; needs sign-off). |
| FINDING-C | **MED** | `sentinel/core.py:128-131` (`_destroy_rooms`) | `try: self.manager.destroy_room(rid) except Exception: pass  # already gone`. The bare swallow assumes "already gone", but it also catches a **genuine** destroy failure (Docker error, container wedged). A room that REFUSES to die during a halt is silently skipped — not in `killed`, **no alarm/escalation** — so a live, ungoverned room can survive a halt undetected. Should distinguish "already gone" from "failed to kill" and escalate the latter. | Open — Phase 3 audit; NOT fixed. |

## Phase 3 — exception-handling audit (governance path: manager/leash/govengine/sentinel)

Verdict per fail-closed-critical site (✓ = fails closed correctly; ✗ = fails open, see findings):

| Site | Behavior on error | Verdict |
|------|-------------------|---------|
| `manager/core.py:86` `_record` (eventlog write) | `raise FailClosed` — aborts the governed action | ✓ fail-closed |
| `manager/core.py:285` `health()` DB probe | reports `db_ok=False` / `eventlog_writable=False` | ✓ fail-closed (surfaces the fault) |
| `leash/proxy.py:44` governor `check_action` down | `Verdict("deny", governor_unavailable)` | ✓ fail-closed (deny) |
| `leash/proxy.py:50` recorder fails | returns `deny` (no unaudited action) | ✓ fail-closed |
| `govengine/fake_test.py:90` coverage tooling unavailable | `return True` (= treat test as HOLLOW → M1 fail → not_done) | ✓ fail-closed (conservative — never a false done) |
| `govengine/reality.py:27/34/41` git read errors | raise `RealityError` → panel escalates (FR-15/AC-8) | ✓ fail-closed (escalate) |
| `sentinel/core.py:121` `_destroy_rooms` state unreadable | `return []` — destroys nothing | ✗ **FINDING-B (fail-open)** |
| `sentinel/core.py:130` `destroy_room` fails | `pass` — room silently skipped, no alarm | ✗ **FINDING-C (fail-open)** |
| `sentinel/core.py:111/167` halt/alarm ledger record fails | `pass` — the physical halt/alarm still happens, only the ledger record is lost | ⚠ minor (unaudited halt possible; physical action proceeds) |
| `leash/gateway.py:77` network disconnect mid-teardown | `pass` — best-effort cleanup | ⚠ minor (teardown only) |

## Phase 3 — lint / standards

- `python -m compileall` (all product packages): **rc=0** (clean).
- `tools/arch_lint.py`: **OK** — no AGT/Gitea imports outside `adapters/`; audit + identity routed through their ports.
- `ruff check` (product packages): **4 × F401 unused imports** — `manager/core.py:20` (`_b64`), `sdlc/stages.py:22` (`gitea_adapter`), `contract/...messages` (`MessageError`), + 1 more. Style only, **not defects**; not auto-fixed (per campaign: report style, don't fix).

## Phase 3 — npm / front-end reality

- The Enterprise **dashboard is a Python API (`dashboard_api.py`/`service.py`) serving static HTML+CSS** (`cockpit.html`, `dashboard.css`). **There is NO npm/Node build surface** for the product — the only `package.json` files in the tree are under `_reference/`, a govengine smoke fixture (`.smoke/`), and the old `docs/thor2 - Copy/` JS project (a different repo). So `npm install`/`npm audit` is **not applicable** to the Enterprise product (front-end is server-rendered static, deferred per the PRD).
