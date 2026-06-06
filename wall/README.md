# Module 1 — The Wall

The sealed, disposable container where one cook does one task. Foundation of THOR's trust model
(Pillar 1 / P4). **Built ungoverned (P7); gate stubbed; smoke-checked, not formally proven (Rule 2).**
Spec: [`../docs/PRD-Module-1-Wall.md`](../docs/PRD-Module-1-Wall.md).

## Files (map to PRD §2 sub-modules)
| File | Sub-module | Role |
|---|---|---|
| `image/Dockerfile` | 1.1 Image Builder | room OCI image (python:3.11-slim + git + unprivileged `cook`) |
| `provisioner.py` | 1.2 Provisioner | composes the others; creates one sealed room |
| `network_enforcer.py` | 1.3 Network Enforcer | day-one: `network_disabled=True`; `:8001` one-door at M2 |
| `mount_manager.py` | 1.4 Mount Manager | ro/rw mounts (FR-6..FR-9) |
| `lifecycle.py` | 1.5 Lifecycle Controller | create/health/pause/destroy + registry view |
| `identity_stamper.py` | 1.6 Identity Stamper | Ed25519 local signer (FR-10, AC-10) |
| `api.py` | — | Wall REST API (PRD §6.1) |
| `config.py` | — | task-type table (FR-15) + constants |

Adapters are stubbed in [`../adapters/`](../adapters/) (Rule 5): local git for Gitea, always-allow+log for AGT.

## Day-one milestone
**AC-1 + AC-2** — a real cook makes a real commit on its branch, inside a box it physically cannot
escape. That is the moment the Wall is proven and the rest of THOR can stand on it (PRD §15).

## How it will be smoke-checked (NOT run until asked)
```bash
# inside the WSL venv, from ~/thor-enterprise
pip install -r requirements.txt
python -m wall.provisioner          # build image -> provision sealed room -> destroy
# or run the API:  uvicorn wall.api:app --host 127.0.0.1 --port 7180
```
The `tests/wall/` AC suite is written but **deferred** — it stays skipped (never a false green).
