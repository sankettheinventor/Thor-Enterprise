# THOR Module 8 — The PM Surface (Kanban, Approval Cards, Audit, Signatures)

**Module PRD + FRD.** Read alongside the Bible (Pillar 3, the three signature points, §16 legible refusal, HCD), the System Design & Flow doc (DashboardAPI :7080, §10 who-writes-what), and Modules 1–7 — especially Module 3 (Manager, which this reads from and signs through) and Module 7 (SDLC stages, whose states this surfaces).

> Saved from `THOR-Module8-PMSurface-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully. Build to this PRD; flag drift (Rule 9).

- **Module:** 8 — The PM Surface · **Pillar:** 3 (Project Management — the human direction layer) · **Kind:** BUILD — the moat (the human-accountability experience; evolve the existing CEO dashboard from one project to N parallel rooms)
- **Build order:** Eighth — after the engine + stages; this is the human face over the working system.
- **One-line purpose:** Give the accountable human one screen to direct features, watch parallel agentic work, and sign the three decisions that matter — a project-management tool *over* agentic AI, where the human stays in command.
- **Version:** 1.0

---

## 1. Overview
Where THOR becomes a *product a person uses*, not just an engine. Everything below it is machinery; the PM Surface is the cockpit the operator sits in. It is half of THOR's moat: the industry races to *remove* the human ("while you sleep"); THOR's bet is the opposite — a human in command, accountable, with the tools to direct and sign.

It does four things: **Direct** (a kanban of features — the catalog, Kind C, backed by Gitea issues), **Watch** (live parallel rooms/stages, read-only logs, cost), **Decide** (the approval queue — the three signature points + critical escalations, each cryptographically signed), **Audit** (the activity feed + audit log from the EventLog, exportable).

Critically, the PM Surface is a **read-and-sign face over the Manager** — it holds no competing truth. It reads the Manager's projections and writes back only signatures + direction. It also carries **legible refusal**: when THOR denies/escalates, the operator sees *why* in plain language — not a stack trace.

## 2. Sub-modules
- **8.1 Kanban Board** — the catalog as columns (Backlog → Ready → Building → In QA → Awaiting Signature → Done).
- **8.2 Room/Stage Live View** — real-time active rooms: feature, stage, status, elapsed, cost-so-far, read-only logs.
- **8.3 Approval Queue** — the cards needing a human: the three signature points + critical escalations.
- **8.4 Signature Pad** — the cryptographic signing component: Ed25519 signature bound to card + payload; verified by the Manager.
- **8.5 Audit Feed & Log** — the activity stream from the EventLog; filterable; exportable (CSV/JSON).
- **8.6 Legible Refusal Renderer** — translates governance denials/escalations into plain-language explanations.
- **8.7 Cost & Budget Panel** — per-feature and total spend, budget caps, estimates, alerts approaching caps.
- **8.8 Project Checker Findings View** — surfaces the read-only Project Checker output (the install "aha moment").
- **8.9 DashboardAPI Client** — the read/write client to the Manager's DashboardAPI (:7080); holds no authoritative state.

## 3. Functional Requirements (FR)
- **FR-1** Present the catalog as a kanban with stage-based columns, reflecting live Manager feature states.
- **FR-2** The operator can add/edit/prioritize/mark-ready features; changes written back to the catalog (Kind C) via the Manager.
- **FR-3** Show all active rooms with feature, stage, status, elapsed time, cost-so-far, near-real-time.
- **FR-4** Room logs are READ-ONLY; the operator cannot reach into a room from the dashboard.
- **FR-5** The Approval Queue presents every card requiring a human: Sig 1 (plan), Sig 2 (ticket), Sig 3 (merge), + critical escalations.
- **FR-6** Each card displays context + a plain-language reason (legible refusal), not raw codes/traces.
- **FR-7** Approving/rejecting requires an Ed25519 signature bound to card + payload, verified by the Manager (P6).
- **FR-8** The PM Surface holds NO authoritative state; it reads projections and writes back only signatures + direction.
- **FR-9** The audit feed shows every decision/verdict/signature/lifecycle event; filterable and exportable (CSV/JSON).
- **FR-10** Show per-feature and total cost/spend + active budget caps; alert when a cap is approached/exceeded.
- **FR-11** Surface Project Checker findings as a dedicated view (the onboarding "aha moment").
- **FR-12** Support dry-run/cost-preview before a wave runs (from the Scheduler).
- **FR-13** Clearly indicate when something is held pending human action (a card never auto-resolves).
- **FR-14** Usable by a non-technical operator: plain language, clear states, no required container/port/git knowledge.
- **FR-15** All operator actions (sign, reject, mark-ready, add-feature) recorded as events via the Manager.
- **FR-16** Degrade safely: if the Manager is unreachable, show a clear "disconnected" state; never fabricate or cache-as-truth.
- **FR-17** Share the same data + signature model as the Mobile surface (Module 16) — desktop and phone consistent.
- **FR-18** Show the meta-trust / system-health indicators (Sentinel + Self-Audit) so the operator can see THOR's own health.

## 4. Technical Requirements
- **Frontend:** web UI — JS/TS (React or similar; evolve the existing ceo.html / cockpit assets).
- **Backend-for-frontend:** the Manager's DashboardAPI on `:7080` (HTTPS, TLS) — the only externally-exposed read/sign surface.
- **Realtime:** push updates (WebSocket/SSE) for room/stage states and the approval queue.
- **Signatures:** Ed25519 in the browser/client; bound to card-id + payload-hash + nonce; secure key handling.
- **Data model:** all reads are projections from the Manager; no local authoritative store. Local cache for responsiveness only, never truth when disconnected (FR-16).
- **Export:** CSV/JSON of the audit log. **Accessibility:** plain-language, clear-state UI (FR-14). **Consistency with mobile:** shares the API + signature model with Module 16.

## 5. The Logic
- **5.1 A window, not a brain** — reads everything from the Manager (the one brain); writes back only direction + signatures. Never computes a verdict, never decides "done," never holds a competing list. Disconnected → it says so; never stale-as-live.
- **5.2 Direct → Watch → Decide → Audit** — four interlocking loops: shape the catalog (feeds the Scheduler); see parallel work live (read-only); sign the three points + escalations (in command); review what happened (exportable).
- **5.3 The three signature points** — Sig 1 (plan: "approve to begin building?"), Sig 2 (re-work ticket: "authorize a re-work?"), Sig 3 (merge: "approve the merge to main?"). Each a real Ed25519 signature bound to the card, verified by the Manager. A card never auto-resolves; the held-pending-you state is unmistakable — silence is never consent.
- **5.4 Legible refusal** — the Legible Refusal Renderer translates the Leash/Engine reason codes into human explanations; a genuine differentiator (every competitor builds for developers who read traces; THOR explains itself to the accountable human).
- **5.5 Watching without touching** — the operator sees everything read-only; there is no "reach into the room and fix it" button. Influence is exercised through governed channels (mark-ready, sign, ticket), never around them.
- **5.6 Cost visibility first-class** — per-feature spend, total, caps, estimates before a wave, alerts approaching a cap. The accountable human is accountable for spend too.
- **5.7 Showing THOR's own health** — the operator sees the Sentinel's status + the Self-Audit meta-trust signal; a governed system that hides its own health asks for blind trust.

## 6. API Strategy
The PM Surface is a client of the Manager's DashboardAPI (`:7080`). It reads projections and writes direction + signatures; it exposes no authoritative API of its own.
### 6.1 Endpoints the PM Surface CONSUMES (DashboardAPI :7080 → Manager)
```
GET /state/summary -> { features[], rooms[], open_cards[], health }
GET /kanban        -> { columns:{ backlog, ready, building, in_qa, awaiting_signature, done } }
GET /rooms/live    -> { active:[ {room_id, feature_id, stage, status, elapsed, cost_so_far } ] }  (WS/SSE)
GET /rooms/{id}/logs -> { log_lines[] }   # READ-ONLY
GET /cards         -> { cards:[ {card_id, type, feature_id, context, legible_reason, held_since } ] }
GET /audit/feed?filter&range -> { events[] }
GET /audit/export?fmt=csv|json -> file
GET /cost          -> { per_feature[], total, caps, estimates }
GET /findings      -> { checker_findings[] }
GET /health/system -> { sentinel, self_audit_meta_trust }
```
### 6.2 Endpoints the PM Surface WRITES (direction + signatures only)
```
POST  /features        { title, context, priority } -> add to catalog (Kind C)
PATCH /features/{id}    { priority?, ready?:bool }   -> direct the Scheduler
POST  /approve          { card_id, signature }       -> Manager verifies (Ed25519) + acts
POST  /reject           { card_id, signature, reason } -> Manager verifies + acts
POST  /schedule/dry_run { }                          -> cost+wave preview (no provisioning)
```
### 6.3 The discipline
Every read is a projection from the Manager (no local truth). Every write is direction or a signature — and every write is recorded as an event (FR-15). Disconnected → "disconnected", never stale-as-live (FR-16). Signing always re-validates against the Manager's current state.

## 7. Diagrams (described)
- **Figure 1** — The cockpit layout: kanban (Direct), live room/stage view (Watch), approval queue with the three signatures (Decide), audit feed (Audit) — all reading from the one Manager.
- **Figure 2** — The four operator loops: Direct → Watch → Decide → Audit — the whole job of an accountable operator.
- **Figure 3** — A window, not a brain: the PM Surface reads projections and writes back only direction + signatures; holds no competing truth; shows "disconnected" rather than stale-as-live.

## 8. Flows
- **8.1 Direct** — add a feature on the kanban → POST /features → Manager writes the catalog + Gitea issue → mark ready → the Scheduler picks it up.
- **8.2 Watch** — Live View streams active rooms; the operator opens read-only logs, sees the cook working, cannot intervene.
- **8.3 Decide — sign the merge (Sig 3)** — F47 passes the verdict → Manager raises a merge card → the card shows a plain-language summary → operator signs (Ed25519 bound to the card) → POST /approve → Manager verifies → directs Gitea to merge → card clears; event logged.
- **8.4 Decide — legible refusal** — a build action tried to edit billing outside F47's scope → escalated → the card shows "Blocked: tried to edit billing/ which isn't in F47's approved area. Allow once, or reject?" → operator rejects → recorded.
- **8.5 Audit + export** — filter the audit feed; export CSV/JSON for compliance.
- **8.6 Disconnected** — the Manager becomes unreachable → "disconnected — data may be out of date" banner; signing disabled; resumes when reconnected.

## 9. Use Cases / User Stories (story points)
- **US-1 (13)** direct/watch/decide/audit agentic work from one cockpit. *(The core product experience.)*
- **US-2 (13)** sign the three decisions cryptographically — genuinely accountable. *(HCD as product.)*
- **US-3 (8)** blocks/escalations explained in plain language. *(Legible refusal — differentiator.)*
- **US-4 (8)** see all parallel rooms/stages live with cost-so-far.
- **US-5 (8)** the cockpit holds no authoritative state — one source of truth.
- **US-6 (5)** watch logs read-only; influence only through governed channels.
- **US-7 (5)** see per-feature/total cost + caps with alerts.
- **US-8 (5)** on install, see the truth about the codebase (Checker findings).
- **US-9 (5)** filter + export the full audit log.
- **US-10 (5)** a card held pending action is unmistakably waiting; never auto-resolves.
- **US-11 (5)** desktop and phone show the same truth + signing model.
- **US-12 (3)** if disconnected, told clearly; never shown stale data as live.
- **US-13 (3)** see THOR's own health (Sentinel + meta-trust).

**Total: ~86 points for Module 8.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| Manager unreachable | network/crash | "Disconnected" banner; disable signing; no stale-as-live (FR-16) |
| Signature fails verification | forged/expired/wrong card | Manager rejects; card stays open; UI shows the failure |
| Two operators act on one card | concurrent | Manager resolves once (idempotent); the second sees "already decided" |
| Stale view vs live state | lag | WS/SSE push reconciles; signing re-validates against current state |
| Operator tries to edit a room | no such path | Logs are read-only; no intervene control exists (by design) |
| Cost cap hit mid-wave | spend accrues | Alert + Scheduler halts dispatch; operator decides |
| Card never actioned | operator absent | Held indefinitely; clearly pending; no auto-resolve |
| Huge audit export | large log | Paginated/streamed; bounded; background job for very large ranges |
| Legible reason missing | new reason code | Safe generic explanation + raw code for support; never show nothing |
| Non-technical operator confused | unclear context | Plain-language-first; "what does this mean?" help |
| Kanban edit conflicts with running work | edit a building feature | Edits constrained; scope changes go through amend/signature, not silent kanban edits |
| Browser signing-key issue | key unavailable | Block signing with a clear error; never fake a signature |

## 11. Easy vs Difficult Parts
- **Easy:** the kanban + feature CRUD; the audit feed + export; read-only log viewing.
- **Moderate:** realtime room/stage/cost streaming at scale; the approval-queue UX with clear held-pending states; the cost panel wired to the Scheduler.
- **Difficult / real risk:** (1) **Legible refusal that's genuinely clear** — translating arbitrary reason codes into explanations a non-technical operator understands. (2) **Secure in-browser signing** — handling the signing identity securely, binding signatures correctly, without leaks or mis-binding. (3) **Never showing stale-as-live** — getting disconnect/stale handling exactly right and disabling signing when uncertain.

## 12. Technical Difficulties
- **D1 — Legible refusal coverage.** A reason-code → explanation mapping maintained alongside the Leash/Engine; safe generic fallback + raw code for unmapped; legibility a first-class, growing asset.
- **D2 — Signature security.** Ed25519; bound to card-id + payload-hash + nonce; verified server-side; secure client key handling; replayed/forged rejected.
- **D3 — Stale-vs-live correctness.** Push-based live updates; signing re-validates at submit time; on disconnect, explicit banner + disabled signing; cache for responsiveness only.
- **D4 — Realtime at scale.** WS/SSE with efficient diffs; the Manager's projections drive the stream; backpressure for high room counts.
- **D5 — Non-technical usability.** Plain-language-first; human-named states (Building, Testing, Awaiting your signature); hide internals; the cockpit teaches the model by its layout.

## 13. What Needs To Be Built (checklist)
- [ ] Kanban Board (catalog columns; add/edit/prioritize/mark-ready; Gitea-issue-backed)
- [ ] Room/Stage Live View (WS/SSE; feature, stage, status, elapsed, cost; read-only logs)
- [ ] Approval Queue (the three signatures + escalations; held-pending states)
- [ ] Signature Pad (Ed25519, bound to card+payload+nonce; secure client signing)
- [ ] Audit Feed & Log (EventLog projection; filter; CSV/JSON export)
- [ ] Legible Refusal Renderer (reason-code → plain language; safe fallback)
- [ ] Cost & Budget Panel (per-feature + total spend; caps; estimates; alerts; dry-run)
- [ ] Project Checker Findings View (the aha-moment screen)
- [ ] System Health view (Sentinel + Self-Audit meta-trust)
- [ ] DashboardAPI Client (read projections; write direction + signatures only)
- [ ] Disconnected-state handling (banner; disable signing; no stale-as-live)
- [ ] Desktop/mobile shared API + signature model (with Module 16)

## 14. Dependencies & Sequencing
**Depends on:** Module 3 (Manager) — the source of all data (projections) + the verifier of all signatures (hard dep; the PM Surface is its window). Module 7 (SDLC Stages) — whose stage states + Checker findings + QA cards the surface displays. Module 4 (Scheduler) — for cost estimates, dry-run, budget caps. Module 6 (Engine) — whose verdicts produce the merge cards. The EventLog — for the audit feed.

**Blocks / depended on by:** Module 16 (Mobile) — shares this surface's API + signature model (two heads, one truth). The product's usability — without the PM Surface, THOR has no human face.

**Build-order note:** Build after the engine + stages exist. Evolve the existing ceo.html / cockpit assets from one project to N parallel rooms. **Milestone:** an operator drives a feature on the kanban, watches it build + QA live with cost, signs the merge with a verified signature, and exports the audit trail — all as read-and-sign over the one Manager.

## 15. Test / Acceptance Criteria (evidence-based)
- **AC-1** The kanban reflects live Manager feature states; marking a feature ready causes the Scheduler to pick it up.
- **AC-2** Approving a merge card produces a valid Ed25519 signature the Manager verifies, and the merge proceeds only then (forged rejected).
- **AC-3** A governance block is shown to the operator in plain language (not a raw code/trace).
- **AC-4** Room logs are viewable read-only; there is no control to modify a room from the dashboard.
- **AC-5** The PM Surface holds no authoritative state: closed/reopened, all state comes from the Manager unchanged.
- **AC-6** When the Manager is unreachable, the UI shows "disconnected", disables signing, and never presents stale data as live.
- **AC-7** Per-feature and total cost + caps are shown; approaching a cap raises an alert; a dry-run shows cost with zero provisioning.
- **AC-8** All three signature points appear as cards and require a verified signature to proceed; none auto-resolves.
- **AC-9** The audit feed shows every decision/verdict/signature and exports to CSV/JSON.
- **AC-10** Project Checker findings render as a dedicated view and match what the Checker wrote to the DB.
- **AC-11** Every operator action (sign, reject, mark-ready, add-feature) is recorded as an event.
- **AC-12** Desktop and mobile show the same card and resolve it consistently (one decision, not two).

**Headline milestone:** AC-2 + AC-3 + AC-6 together — a verified human signature drives a real merge, blocks are explained in plain language, and the cockpit never lets the operator sign against a stale picture. That proves the human-command experience is real, legible, and safe.

---

*End of THOR Module 8 — The PM Surface PRD v1.0. Pillar 3 (the human direction layer) is now specified. Next module: 9 — Mobile / Remote + Legible Refusal (the phone-as-remote-control surface — E2EE signed approvals — sharing this module's data and signature model).*
