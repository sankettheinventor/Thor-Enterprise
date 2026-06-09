# THOR QA Campaign — new findings register

New defects/observations surfaced by the verification campaign (separate from the four named bugs
BUG-1..4). Per the wiring rule "new problems → append to the register, don't fix inline." These are
candidates for triage; do NOT auto-fix working modules without sign-off.

| ID | Severity | Where | Finding | Status |
|----|----------|-------|---------|--------|
| FINDING-A | LOW–MED | `wall/provisioner.py:28` | `client = docker.from_env()` runs at **module import time**, so importing `ThorManager` (which imports `wall.provisioner`) **requires a live Docker daemon** — import fails with `DockerException` where no daemon/socket is reachable. Makes "docker-free" logic testing impossible for anything touching the Manager, and is a fragile import side-effect (a daemon hiccup breaks `import`). | Open — recorded Phase 1; consider lazy/deferred client init. |

(Phases 3–4 will append more as they are found.)
