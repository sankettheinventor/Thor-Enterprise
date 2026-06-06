# THOR Enterprise — Windows Dev Setup + Project Skeleton + Starter Code

This doc preserves the user-provided setup runbook, the project skeleton, and the Module 1 (Wall)
starter code verbatim, so it survives a reboot independently of chat context.

---

## A. Windows Dev Setup (do this once)

Goal: a friction-free Linux-like dev environment on Windows, because THOR's rooms are Linux
containers and the whole stack assumes a Unix shell.

### 1. WSL2 + Ubuntu (admin PowerShell)
    wsl --install
    # reboot when prompted; create your Ubuntu username + password

### 2. Docker Desktop
    - Install Docker Desktop for Windows
    - Settings -> General: "Use the WSL 2 based engine" (on)
    - Settings -> Resources -> WSL Integration: enable your Ubuntu distro
    - Verify (in the Ubuntu shell):   docker run hello-world

### 3. VS Code + WSL
    - Install VS Code (Windows)
    - Install the "WSL" extension (Microsoft)
    - From the Ubuntu shell, in your project folder:   code .

### 4. Toolchain (inside Ubuntu/WSL shell)
    python3 --version        # 3.11+ ideally
    git --version
    sudo apt update && sudo apt install -y python3-venv python3-pip

### 5. Make the project
    mkdir -p ~/thor-enterprise && cd ~/thor-enterprise
    git init
    python3 -m venv .venv && source .venv/bin/activate
    code .

### Commands you live in
    docker ...   # build/run/inspect rooms
    git ...      # the cook commits land here
    python ...   # control-plane code
    + the VS Code integrated terminal + Claude Code in it.

### What you do NOT do yet
    - No Kubernetes (premature).
    - No cloud (local Docker proves the Wall).
    - No governance on THIS build (P7 — build ungoverned first).

---

## B. Project Skeleton (build order mirrors the module map)

Everything is ORDINARY SOFTWARE — no governance on THOR's own build (P7).

    thor-enterprise/
    ├── README.md
    ├── docker-compose.yml          # local control plane (filled in as modules land)
    ├── pyproject.toml              # Python control-plane deps
    ├── .env.example                # config (never commit real secrets)
    │
    ├── wall/                       # Module 1 — the sealed container (BUILD FIRST)
    │   ├── image/Dockerfile        # the room OCI image (Dockerfile, cook runtime, skill-loader)
    │   ├── provisioner.py          # create container: mounts, limits, task_type
    │   ├── network_enforcer.py     # the one-door egress lock (iptables/namespace)
    │   ├── mount_manager.py        # ro/rw mounts (incl. checker read-only)
    │   ├── lifecycle.py            # create / health / destroy
    │   └── identity_stamper.py     # Ed25519 room token
    │
    ├── leash/                      # Module 2 — pre-action interception (AGT adapter lives here)
    ├── manager/                    # Module 3 — the single brain + EventLog writer + registry
    ├── scheduler/                  # Module 4 — deterministic task-graph executor
    ├── contract/                   # Module 5 — the frozen six-message interface + slice
    ├── govengine/                  # Module 6 — the 8-probe verdict (THE MOAT)
    ├── sdlc/                       # Module 7 — typed stages (genesis/checker/build/qa)
    ├── pmsurface/                  # Module 8 — kanban/cards/audit (JS/TS web UI)
    ├── mobile/                     # Module 9 — phone bridge (extend postman + Cloudflare)
    ├── sentinel/                   # Module 10 — meta-governance health
    ├── selfaudit/                  # Module 11 — the zero-cost Qwen inspector
    ├── adapters/                   # Module 12 — audit / identity / gitea (behind THOR vocab)
    │   ├── agt_adapter.py          # the ONLY file importing AGT
    │   └── gitea_adapter.py        # the ONLY file importing Gitea
    │
    └── tests/                      # the PROVING suite — written alongside, RUN at the end
        ├── wall/                   # AC-1..AC-12 for the Wall (deferred proving)
        └── ...

Day-one focus: wall/ — get a cook into a sealed container that makes a real commit.
Proving (the tests/ battery) is written but run as a pass LATER, when THOR is whole.

---

## C. Starter code (provided by user — reproduce when scaffolding the Wall)

### wall/provisioner.py
```python
"""
THOR Module 1 — the Wall: minimal provisioner (built ungoverned, iterate with Claude Code).

This is the day-one artifact: create a sealed room, mount a task slice read-only,
mount a worktree read-write, apply a one-door network lock, and start a cook.
Smoke-check ("does it run") as you go; the full AC-1..AC-12 PROVING is deferred.

Requires: pip install docker
"""
import docker, json, os, tempfile, uuid

client = docker.from_env()
ROOM_IMAGE = "thor-room:dev"

def build_image():
    """Build the room OCI image from wall/image/Dockerfile."""
    img, _ = client.images.build(path="wall/image", tag=ROOM_IMAGE, rm=True)
    return img

def provision_room(task_type="build", feature_slice=None, worktree_host_path=None,
                   cpu=1.0, mem="1g"):
    """
    Create ONE sealed room. The big idea: NO default network (one-door rule comes next),
    task slice mounted READ-ONLY, worktree READ-WRITE, unprivileged, resource-capped.
    """
    room_id = f"room-{uuid.uuid4().hex[:8]}"

    # write the feature slice to a temp file, mounted read-only at /task/feature.json
    mounts = []
    if feature_slice is not None:
        slice_dir = tempfile.mkdtemp(prefix=f"{room_id}-task-")
        with open(os.path.join(slice_dir, "feature.json"), "w") as f:
            json.dump(feature_slice, f)
        mounts.append(docker.types.Mount("/task", slice_dir, type="bind", read_only=True))

    if worktree_host_path:
        mounts.append(docker.types.Mount("/work", worktree_host_path, type="bind", read_only=False))

    container = client.containers.run(
        ROOM_IMAGE,
        command="sleep infinity",          # placeholder; the cook entrypoint replaces this
        name=room_id,
        detach=True,
        mounts=mounts,
        network_disabled=True,             # START with NO network; the one-door proxy is added next
        mem_limit=mem,
        nano_cpus=int(cpu * 1e9),
        user="cook",
        cap_drop=["ALL"],                  # drop Linux capabilities (hardening)
        security_opt=["no-new-privileges"],
        labels={"thor.room": "1", "thor.task_type": task_type, "thor.room_id": room_id},
    )
    return {"room_id": room_id, "container": container.id, "task_type": task_type}

def destroy_room(room_id):
    """Tear down the container; the branch (in git) persists, the container does not."""
    for c in client.containers.list(all=True, filters={"label": f"thor.room_id={room_id}"}):
        c.remove(force=True)
    return {"room_id": room_id, "status": "destroyed"}

if __name__ == "__main__":
    # day-one smoke check: build, provision, confirm it runs, destroy
    build_image()
    room = provision_room(task_type="build", feature_slice={"feature_id": "F001", "goals": ["hello"]})
    print("provisioned:", room)
    print("destroyed:", destroy_room(room["room_id"]))
```

### wall/image/Dockerfile
```dockerfile
# THOR Room image (Module 1, the Wall) — one image, four task_types.
# Minimal Linux + a cook runtime + git. Built ungoverned; hardened later.
FROM python:3.11-slim

# git so the cook can commit; the worktree is mounted in at runtime
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# unprivileged user — the container cannot weaken its own jail from inside
RUN useradd -m -u 1000 cook
USER cook
WORKDIR /work

# task slice is mounted read-only at /task/feature.json by the Mount Manager
# the cook's agent-server / entrypoint goes here as it's built
ENTRYPOINT ["/bin/bash"]
```

---

## D. Reference source note
The original THOR codebase is at `C:\dev\thor2 - Copy`. It is **read-only study material**:
mine proven doctrine (e.g. done-check.js for the 8-probe verdict), then REIMPLEMENT clean in the
new module structure. NEVER import it, NEVER extend it, NEVER copy files wholesale. It will be
copied into `~/thor-enterprise/_reference/` post-reboot.
