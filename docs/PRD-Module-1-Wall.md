# THOR Module 1 — The Wall (Isolation Layer)

**Module PRD + FRD.** Part of the THOR Enterprise PRD suite. Read alongside the Bible (principles, modules) and the System Design & Flow doc (topology, ports, contracts).

> Saved from the user-provided `THOR-Module1-Wall-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully so it survives independently of chat context. This is the source-of-truth spec the Wall is built against (Rule 9: build to the PRD, flag drift).

- **Module:** 1 — The Wall · **Pillar:** 1 (Isolation) · **Kind:** ADOPT (Docker) + thin BUILD (provisioning wrapper)
- **Build order:** FIRST — net-new, load-bearing; everything sits on it.
- **One-line purpose:** Give each task a sealed, disposable container the agent cannot escape, with exactly one governed network exit, so isolation is a physical fact (P4), not a convention.
- **Version:** 1.0

---

## 1. Overview

The Wall is the sealed environment where one cook (any coding agent) does one task. It is the foundation of THOR's entire trust model: every other guarantee — the leash, the verdict, the audit — assumes the agent physically cannot escape, cannot see the host, cannot reach other rooms, and cannot reach the network except through THOR's one door.

The Wall is deliberately **dumb about governance**. It knows nothing about scope, contracts, or "done." Its only intelligence is structural: enforce isolation, force all traffic through the chokepoint, and make the leash untouchable. All judgment lives above it (Pillar 2). This separation (P8) is why the Wall stays small and reliable while governance evolves.

In Bible terms: the Wall is the OS-enforced boundary (P4). In SDLC terms: the Wall is the container that every typed stage (genesis/checker/build/qa) runs inside — one image, many task-types. In System-Design terms: the Wall is the Room, reachable by ThorManager on `:8000`, with its single exit on `:8001`.

**Why this is built first:** Per the build-order law (Bible §15): prove one cook does real work in a real sealed container and produces a clean branch + manifest, with the gate stubbed as "always approve." Nothing else can stand without it, and it's the one piece no existing system gives us in exactly the shape we need (Docker gives the primitive; the THOR-specific provisioning, one-door enforcement, and lifecycle are ours).

## 2. Sub-modules

The Wall decomposes into six internal parts:

- **1.1 Image Builder** — produces the room OCI image(s): base OS, the cook runtime, the in-room Leash proxy, the skill-loading mechanism. ARM (free tier) and x86 (paid) variants.
- **1.2 Provisioner** — on instruction from ThorManager, creates a container instance: applies network lock, mounts (worktree read-write, `/task/feature.json` read-only, rules read-only), resource limits, and the task-type config.
- **1.3 Network Enforcer** — applies the iptables/namespace rules that make `:8001` the only outbound route. The heart of P4.
- **1.4 Mount Manager** — manages what's mounted and with what permissions (the read-only guarantees are here).
- **1.5 Lifecycle Controller** — create / health-check / pause / destroy. Tracks container state, reports to ThorManager.
- **1.6 Identity Stamper** — stamps each room with a verifiable identity token so ThorManager can confirm a room belongs to this THOR instance (defends against stale/sibling rooms — the original THOR's F103 lesson).

## 3. Functional Requirements (FR)

- **FR-1** The Wall SHALL create a container per task on instruction from ThorManager, never autonomously.
- **FR-2** Each container SHALL run exactly one cook and own exactly one git worktree/branch.
- **FR-3** The container SHALL have no inbound network access except ThorManager → agent-server (`:8000`).
- **FR-4** The container SHALL have exactly one outbound route: the in-room Leash proxy (`:8001`). All model and tool calls exit only through it. (P4)
- **FR-5** Outbound attempts that bypass `:8001` SHALL be dropped at the network layer (not merely discouraged).
- **FR-6** The feature-slice SHALL be mounted read-only at `/task/feature.json`. The cook cannot modify its own task/scope. (P1)
- **FR-7** The governance rules slice SHALL be mounted read-only; editable only host-side. (P1, P8.7)
- **FR-8** The worktree SHALL be mounted read-write (the cook needs to build).
- **FR-9** For `checker` task-type, the codebase SHALL be mounted READ-ONLY (the Project Checker changes nothing — the trust guarantee).
- **FR-10** Each container SHALL carry a verifiable identity token; ThorManager SHALL verify it before trusting the room.
- **FR-11** The container SHALL enforce CPU/RAM/disk limits supplied at provision time.
- **FR-12** The container SHALL be destroyable on command, fully removing the container and its ephemeral state (worktree branch persists in Gitea; container does not).
- **FR-13** The container SHALL NOT be able to see, reach, or enumerate other rooms. (room-to-room isolation)
- **FR-14** The container SHALL NOT be able to read the host filesystem outside its explicit mounts.
- **FR-15** The Wall SHALL support a `task_type` parameter (`genesis | checker | build | qa`) that selects mounts, permissions, and which skills load — one image, four behaviors.
- **FR-16** The Lifecycle Controller SHALL report container health (alive AND responsive) to the Sentinel on request.
- **FR-17** On container crash, ephemeral compute is lost but the worktree (in Gitea) and execution state (Kind A, persisted outside) SHALL survive for resume.
- **FR-18** The Wall SHALL run identically on Docker Compose (local/free) and Kubernetes (paid), via the same OCI image.

## 4. Technical Requirements

- **Runtime:** Docker (OCI containers). Same image runs under Docker Compose (free tier) and Kubernetes (paid).
- **Image architecture:** ARM (Oracle free-tier Ampere) + x86 (paid). Multi-arch build.
- **Base image:** minimal Linux (e.g. slim Debian/Alpine variant) + the cook runtime + the in-room Leash proxy binary + skill-loader.
- **Network enforcement:** iptables rules / network namespaces (Docker custom network with egress locked to the proxy); under K8s, NetworkPolicy + egress controls.
- **Provisioning language:** Python (the THOR control-plane backend; matches AGT ecosystem) calling the Docker SDK / K8s API.
- **Mounts:** Docker volumes/binds with explicit `:ro` / `:rw` flags; tmpfs for ephemeral scratch.
- **Identity:** a signed token (Ed25519, reusing AGT/Mesh identity primitives) injected at provision, verified by ThorManager.
- **Resource control:** Docker `--cpus`, `--memory`, `--storage-opt`; K8s resource requests/limits.
- **No privileged containers:** the cook runs unprivileged; the Wall's enforcement is from the host/orchestrator side, not from inside the container (the container cannot weaken its own jail).

## 5. The Logic (how it actually works)

### 5.1 The one-door enforcement (the core)
The defining mechanism. A naive sandbox lets the agent talk to the network and *asks* it to use a proxy. THOR does the opposite:
1. The container is attached to a custom Docker network with no default route to the internet.
2. The only reachable outbound address is the in-room Leash proxy (`:8001`), which itself routes to the AGT adapter on the control plane.
3. iptables rules (applied host-side at provision) DROP any outbound packet not destined for `:8001`.
4. The cook has no credentials for the LLM API, Gitea, or anything else — those live in the AGT adapter and are injected only for approved destinations after a policy check.

**Result:** even a malicious or confused cook cannot reach the internet, the model API, or another room. Not because it's asked not to — because there is no route and no key. This is P4 made physical, and it is the reason THOR's other guarantees hold.

### 5.2 Provisioning sequence (internal)
On `provision(room_id, task_type, skills[], scope, repo, base_branch, limits)`:
1. Mount Manager prepares mounts: worktree (rw), `/task/feature.json` (ro), rules (ro), and for `checker` the codebase (ro).
2. Image Builder selects the arch-appropriate image; skill-loader is told which skills to load.
3. Network Enforcer creates/attaches the locked network; installs the `:8001`-only egress rule.
4. Identity Stamper injects the signed room token.
5. Lifecycle Controller starts the container, waits for the agent-server (`:8000`) and Leash proxy (`:8001`) to report ready.
6. Reports `{room_id, address, status:"ready"}` to ThorManager, which verifies identity before trusting it.

### 5.3 Task-type as configuration, not separate code
One image; `task_type` selects behavior (FR-15):
- **genesis** — mounts planning workspace; loads PM+CTO+UX skills; no source repo yet.
- **checker** — mounts the existing codebase READ-ONLY; loads analysis skills; emits findings only.
- **build** — mounts a fresh worktree rw; loads task-type build skills; normal governed build.
- **qa** — mounts the build branch + read access to code; loads QA skills; adversarial test.

This keeps the Wall uniform (one thing to build and harden) while serving all SDLC stages.

### 5.4 Disposability + recovery
The container is cattle, not a pet. Its compute state is ephemeral; the durable outputs (the git branch, the execution state Kind A persisted outside) survive destruction or crash. To recover: provision a new container, re-attach the worktree, reload execution state, resume. The Wall never holds anything that can't be reconstructed.

## 6. API Strategy

The Wall exposes a small control interface to ThorManager and reports to the Sentinel. It does not expose anything to the cook (the cook only sees its mounts and its one door). All control-plane calls are HTTP/REST/JSON.

### 6.1 Endpoints the Wall EXPOSES (consumed by ThorManager)
```
POST /wall/provision
  req: { room_id, task_type, skills[], scope{}, repo, base_branch, limits{cpu,mem,disk}, arch }
  res: { room_id, address, agent_port:8000, status:"ready"|"error", identity_token }

GET  /wall/rooms/{room_id}/health
  res: { room_id, alive:bool, responsive:bool, agent_server:bool, leash_proxy:bool }

POST /wall/rooms/{room_id}/pause
  res: { room_id, status:"paused" }

POST /wall/rooms/{room_id}/destroy
  res: { room_id, status:"destroyed", branch_preserved:bool }

GET  /wall/rooms
  res: { rooms:[ {room_id, task_type, status, address} ] }   # registry view
```

### 6.2 Endpoints the Wall CONSUMES
- → Docker SDK / K8s API (create/start/stop/remove containers, networks, volumes)
- → Gitea adapter (`:7170`) `POST /git/worktree` (create worktree+branch before provision)
- → (rooms route outward only via the in-room Leash proxy `:8001` → AGT adapter `:7160`)

### 6.3 In-room interface (ThorManager → the cook's agent-server, NOT the Wall itself)
The Wall sets up `:8000` and `:8001` but does not mediate task content. Per the frozen contract (Bible D8 / System Design §7.4): ThorManager → Room `:8000` carries `assign_task`, `status`, `claim_done`, `result_decision`. The Wall's job ends once the container is ready and locked.

### 6.4 Port summary (from System Design §3)
| Endpoint | Port | Reachable by |
|---|---|---|
| Wall provisioning API | (control-plane, via ThorManager) | ThorManager |
| Room agent-server | `:8000` (per container) | ThorManager only (inbound) |
| Room Leash proxy | `:8001` (per container) | the ONLY outbound route |

## 7. Diagrams (described)
- **Figure 1** — The Wall's six sub-modules and how a provision request flows through them (ThorManager → Provisioner → Image Builder / Identity Stamper / Network Enforcer / Mount Manager / Lifecycle Ctrl) to a locked, ready Room (`cook :8000 · door :8001`).
- **Figure 2** — The one-door network model: the Cook (has task + skills, NO creds) → Leash proxy `:8001` (the ONLY exit) → AGT adapter (holds creds, injects per-destination). Internet and other rooms are DROPPED (no route). Host-side iptables drops anything not bound for `:8001`. Cook cannot leak: no path AND no keys.
- **Figure 3** — One OCI image, `task_type` selects: genesis (planning ws · PM+CTO+UX) / checker (codebase RO · analysis) / build (worktree rw · build skills) / qa (branch+ro · QA skills). Same wall, same hardening — four behaviors.

## 8. Flows

### 8.1 Happy path — provision a build room
1. ThorManager → Gitea adapter: create worktree + branch.
2. ThorManager → Wall: `POST /wall/provision {task_type:"build", skills, scope, limits, arch}`.
3. Mount Manager prepares mounts (worktree rw, /task ro, rules ro).
4. Network Enforcer creates the locked network + `:8001`-only egress rule.
5. Identity Stamper injects the signed token.
6. Lifecycle Controller starts the container; waits for `:8000` and `:8001` ready.
7. Wall → ThorManager: `{room_id, address, status:"ready", identity_token}`.
8. ThorManager verifies the identity token, then proceeds to `assign_task`.

### 8.2 Happy path — destroy after merge
1. ThorManager → Wall: `POST /wall/rooms/{id}/destroy`.
2. Lifecycle Controller stops the container, removes it, tears down the network/volumes.
3. Confirms the branch is preserved in Gitea; ephemeral state gone.
4. Wall → ThorManager: `{status:"destroyed", branch_preserved:true}`.

### 8.3 Recovery — container crash mid-work
1. Sentinel health probe fails (room unresponsive).
2. ThorManager marks room crashed; instructs Wall to destroy the dead container.
3. ThorManager provisions a new container, re-attaches the worktree, reloads execution state (Kind A).
4. Cook resumes from persisted state. No governance truth lost (it's in the EventLog).

## 9. Use Cases / User Stories (story points: Fibonacci)

- **US-1 (8)** As ThorManager, I can provision a sealed build container with one command, so an agent can start work in isolation. (Core provisioning.)
- **US-2 (13)** As the platform, I guarantee the cook cannot reach the network except via `:8001`, so isolation is physical. (The one-door enforcement — hardest, highest-value.)
- **US-3 (5)** As ThorManager, I can destroy a room and be sure the branch survives but the container is gone, so rooms are safely disposable.
- **US-4 (5)** As the Sentinel, I can query whether a room is alive AND responsive, so I can detect hung containers.
- **US-5 (8)** As the platform, I can run the same image on Docker Compose and Kubernetes, so free and paid tiers share one build.
- **US-6 (5)** As the Project Checker, I get the codebase mounted read-only, so I provably change nothing.
- **US-7 (3)** As ThorManager, I can verify a room's identity token, so a stale/sibling room can't be mistaken for a live one.
- **US-8 (8)** As the platform, I can recover a crashed room by re-attaching its worktree and reloading state, so a crash never loses work.
- **US-9 (5)** As ThorManager, I select `task_type` and the right mounts/skills load automatically, so one image serves all four SDLC stages.
- **US-10 (3)** As the operator, resource limits are enforced per room, so one runaway room can't starve the host.

**Total: ~63 points for Module 1.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| Provision fails (no capacity) | Docker/K8s can't allocate | Return error; ThorManager queues or bursts to paid (per D3) |
| Image pull fails | Registry unreachable / wrong arch | Fail provision with clear arch error; don't start a half-room |
| Network lock fails to apply | iptables/namespace error | **Fail-closed: do NOT start the container** (a room without the lock is forbidden) |
| Cook tries to reach internet directly | Bypass attempt | Packet dropped at host network layer; logged as security event |
| Cook tries to write `/task/feature.json` | Self-modify scope | Write denied (read-only mount); attempt logged |
| Checker tries to write the codebase | Should be impossible | Denied (read-only mount); if it somehow attempts, flagged as critical |
| Container hangs (alive but unresponsive) | Cook stuck/infinite loop | Health probe distinguishes alive-vs-responsive; ThorManager times out → mark failed |
| Identity token mismatch | Stale/sibling room | ThorManager refuses to trust; room quarantined/destroyed |
| Destroy fails (container stuck) | Docker daemon issue | Retry with force; escalate to Sentinel if it persists; never leave an unlocked zombie |
| Worktree mount conflict | Two rooms, same branch | Provisioner refuses; one branch = one room (enforced) |
| Resource limit exceeded | Cook over-consumes | Container throttled/killed per limit; ThorManager notified |
| Disk fills (ephemeral) | Large build artifacts | tmpfs/quota caps; build fails cleanly rather than crashing host |

## 11. Easy vs Difficult Parts (honest build assessment)
- **Easy / well-trodden:** basic container create/start/stop/destroy (Docker SDK); mounts with ro/rw flags; resource limits (`--cpus`/`--memory`); task-type as a config parameter.
- **Moderate:** multi-arch image build (ARM + x86 — fiddly, CI matrix needed); health that distinguishes alive-vs-responsive; identity stamping + verification; Docker-Compose-and-K8s parity.
- **Difficult / the real risk:** the **one-door network enforcement (US-2)** — getting egress lockdown truly airtight is the hardest and most important part. Subtle holes (DNS, IPv6, link-local, container escape via misconfig) defeat the entire trust model. Needs careful iptables/namespace work, IPv6 disabled or locked, DNS routed through the proxy, and adversarial testing. Plus **crash recovery with worktree re-attach** — finicky to do without corruption.

## 12. Technical Difficulties (the genuinely hard problems)
- **D1 — Airtight egress.** Many ways to leak (raw IP, DNS exfil, IPv6, ICMP). Approach: default-deny network; allow only `:8001`; disable IPv6 in the container; route DNS through the proxy; adversarially test with the Sentinel canary firing escape attempts that MUST be dropped.
- **D2 — Container escape surface.** A malicious cook + a Docker misconfig could break out to the host. Approach: unprivileged containers, no `--privileged`, drop capabilities, read-only root FS where possible, seccomp/AppArmor profiles, enforcement always host-side.
- **D3 — Credential isolation.** If creds leak into the container, the one-door model collapses. Approach: the cook never holds creds; the AGT adapter injects them only outbound, per approved destination; nothing sensitive mounted or env-injected.
- **D4 — ARM/x86 parity.** A dependency that's x86-only breaks the free tier. Approach: multi-arch images; CI builds + tests both; flag x86-only deps early.
- **D5 — Clean teardown at scale.** Orphaned containers/networks/volumes accumulate. Approach: Lifecycle Controller owns teardown; Sentinel periodically reconciles the registry vs actual containers and reaps orphans.

## 13. What Needs To Be Built (checklist)
- [ ] Multi-arch room OCI image (base + cook runtime + in-room Leash proxy + skill-loader)
- [ ] Provisioner service (Python, Docker SDK + K8s API)
- [ ] Network Enforcer (iptables/namespace egress lock; K8s NetworkPolicy variant)
- [ ] Mount Manager (ro/rw mount logic incl. checker read-only codebase)
- [ ] Lifecycle Controller (create/health/pause/destroy + state tracking)
- [ ] Identity Stamper (Ed25519 token inject + ThorManager-side verify)
- [ ] Wall provisioning REST API (§6.1)
- [ ] Health probe (alive AND responsive)
- [ ] Task-type config system (genesis/checker/build/qa → mounts+skills)
- [ ] Crash-recovery path (worktree re-attach + state reload)
- [ ] Orphan reaper (registry vs actual reconciliation)
- [ ] Adversarial egress test suite (the escape attempts that must be dropped)

## 14. Dependencies & Sequencing
**Depends on (must exist or be stubbed first):**
- Docker/K8s runtime available on the host. *(✅ Docker Engine 29.1.3 installed in WSL Ubuntu.)*
- Gitea adapter (for worktree creation) — can be stubbed initially with a local git worktree.
- AGT adapter (for the in-room Leash proxy's upstream) — for Module-1-alone testing, the proxy can run in "always-allow + log" stub mode (gate stubbed, per build-order law).
- Identity primitive (Ed25519) — reuse from AGT/Mesh, or a minimal local signer for v1.

**Blocks (cannot start without the Wall):** Module 2 (Leash) — needs a room to live in. All SDLC stages — need a container to run in. Effectively everything; this is the foundation.

**Build-order note:** Per P7, build the Wall with the gate stubbed "always approve." Prove a real cook does real work in a real sealed container and produces a clean branch + manifest, BEFORE wiring real governance. This is the milestone that de-risks the whole project.

## 15. Test / Acceptance Criteria (evidence-based, THOR-style)
The Wall is "done" only when ALL of these are demonstrably true (not self-reported):

- **AC-1** A provisioned container runs a cook that creates a real commit on its branch (verified via git, not the cook's word).
- **AC-2** From inside the container, an attempt to reach any internet address other than `:8001` is dropped (verified by adversarial test: curl/dig/raw-socket attempts all fail).
- **AC-3** The cook cannot read the host FS outside its mounts (verified by attempted reads failing).
- **AC-4** The cook cannot reach another running room (verified by attempted connection failing).
- **AC-5** Writing to `/task/feature.json` fails (read-only verified).
- **AC-6** A `checker` room cannot modify the mounted codebase (read-only verified).
- **AC-7** Destroying a room removes the container but the branch persists in Gitea (verified both ways).
- **AC-8** A crashed container is recovered by re-attaching the worktree and reloading state; work resumes (verified end-to-end).
- **AC-9** The same image runs on Docker Compose and on Kubernetes (verified on both).
- **AC-10** Identity verification rejects a forged/stale token (verified by negative test).
- **AC-11** Resource limits hold: a room cannot exceed its CPU/RAM/disk caps (verified by stress test).
- **AC-12** No orphaned containers/networks/volumes remain after a destroy cycle (verified by reconciliation).

**The headline milestone (build-order gate):** AC-1 + AC-2 together — a real agent doing real work that physically cannot escape. That is the moment the Wall is proven and the rest of THOR can be built on it.

---

*End of THOR Module 1 — The Wall PRD v1.0. Next module: 2 — The Leash (cook-agnostic pre-action interception), which lives inside the door this module builds.*
