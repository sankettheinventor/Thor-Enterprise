# THOR Module 12 — The Foundation Adapters (Audit Trail / Identity / Gitea)

**Module PRD + FRD.** Read alongside the Bible (§17 adoption decisions, §14.2 audit/compliance, §9.5 authority model, the Strangler-fig strategy, modules 4/5/6 in the map), the System Design & Flow doc (§7 integration seams, §6.2 the EventLog), and all prior modules — these adapters are the substrate they all sit on.

> Saved from `THOR-Module12-Adapters-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully. Build to this PRD; flag drift (Rule 9).

- **Module:** 12 — The Foundation Adapters · **Pillar:** Foundation (the adopted substrate, behind THOR-owned seams) · **Kind:** ADOPT (Microsoft AGT for audit + identity; Gitea for git/PR/CI) — each behind a THOR-owned adapter, Strangler-ready
- **Build order:** Twelfth — but the adapters are interfaced early (stubbed) and filled in here; they underpin Modules 3, 6, 9, 10.
- **One-line purpose:** Provide the three adopted substrates — a tamper-evident signed audit trail, cryptographic identity, and the git/PR/CI backbone — each wrapped in a thin THOR-owned adapter so the substrate is fully used yet fully swappable.
- **Version:** 1.0

---

## 1. Overview
THOR builds the moat (governance, verdict, SDLC, human command) and **adopts** the commodity substrate beneath it. This module is that substrate, expressed as three adapters:
1. **Audit Trail adapter** — a tamper-evident, signed, hash-chained record of every governance decision, verdict, signature, and lifecycle event. ADOPT Microsoft AGT (Merkle/HMAC chaining, Hypervisor receipts) + compliance mapping (EU AI Act, HIPAA, SOC2, NIST, OWASP).
2. **Identity adapter** — cryptographic identity (Ed25519/DID) for rooms, decisions, and human signatures. ADOPT AGT Agent Mesh. (System-trust only, not per-agent trust-scoring — Bible §11.4.)
3. **Gitea adapter** — the git/PR/CI backbone: repos, branches, PRs, issues (= the feature catalog), CI (Gitea Actions). ADOPT Gitea via its REST API.

The unifying principle (Bible §17, the Strangler-fig strategy): **adopt deeply, but always behind a thin THOR-owned adapter.** Each adapter is the only code that imports its external; everything else in THOR speaks THOR's vocabulary. This buys: (a) the external's churn (AGT is "Public Preview") touches one file; (b) the external can be replaced piece-by-piece later by rewriting one adapter, not the system; and (c) the moat is never welded to a commodity dependency. The interesting THOR work is not the substrates — it's the **seams** that keep THOR free.

## 2. Sub-modules
- **12.1 Audit Trail Adapter** — wraps AGT's tamper-evident chain (Merkle/HMAC + Hypervisor receipts); exposes THOR vocabulary (`append_event`, `verify_chain`, `export_compliance`); the only writer-path the Manager's EventLog Writer uses underneath.
- **12.2 Compliance Mapper** — maps THOR's audit events to regulatory frameworks (EU AI Act, HIPAA, SOC2, NIST, OWASP) and generates compliance evidence/reports. ADOPT from AGT.
- **12.3 Identity Adapter** — wraps AGT Agent Mesh (Ed25519/DID); exposes `mint_room_identity`, `verify_identity`, `verify_signature`; backs room identity stamping (M1) and human signatures (M3/8/9).
- **12.4 Signature Verifier** — the shared Ed25519 verification for the three signature points + room tokens; bound to payload+nonce (anti-replay).
- **12.5 Gitea Adapter** — wraps the Gitea REST API; exposes THOR vocabulary (`create_worktree`, `open_pr`, `merge`, `ci_result`, `list_issues`, `git_log`, `git_diff`); the peer-handshake executor THOR directs.
- **12.6 Catalog Bridge** — maps Gitea issues ↔ the feature catalog (Kind C), so the kanban and the issue tracker are one source surfaced two ways.
- **12.7 Adapter Contract & Versioning** — the formal THOR-vocabulary interface each adapter implements; versioned; the seam the Strangler strategy depends on; each adapter has its own test suite.
- **12.8 Substitution Harness** — proves swappability: a test/scaffold demonstrating an adapter's external can be replaced (e.g. Gitea→GitHub stub) by changing only the adapter, with THOR unchanged.

## 3. Functional Requirements (FR)
- **FR-1** Each adapter is the ONLY component that imports its external (AGT or Gitea); all other THOR code calls the adapter's THOR-vocabulary interface. (Strangler seam)
- **FR-2** The Audit Trail adapter provides a tamper-evident, signed, hash-chained append: altering any past event breaks verification detectably.
- **FR-3** The Audit Trail is the durable substrate beneath the Manager's EventLog (M3 is the sole writer; this adapter provides tamper-evidence + chaining underneath).
- **FR-4** The Compliance Mapper maps audit events to named frameworks and exports compliance evidence on demand.
- **FR-5** The Identity adapter mints verifiable room identities (Ed25519/DID) and verifies them; the Manager uses it to trust a room.
- **FR-6** The Signature Verifier verifies human signatures (Ed25519) for the three signature points, bound to card+payload+nonce, rejecting replays/forgeries. (P6)
- **FR-7** Identity is used for system-trust and verification only — NOT for per-agent trust-scoring (Bible §11.4).
- **FR-8** The Gitea adapter exposes git/PR/CI operations in THOR vocabulary; THOR owns the merge authority (decide), Gitea executes (merge + CI) — the peer handshake.
- **FR-9** Swapping Gitea for another git host (e.g. GitHub) requires changing only the Gitea adapter, never THOR's authority or other modules.
- **FR-10** The Catalog Bridge keeps Gitea issues and the feature catalog (Kind C) consistent — one source, surfaced as both issues and kanban.
- **FR-11** Each adapter is versioned and has its own test suite asserting the THOR vocabulary holds across external upgrades.
- **FR-12** AGT being "Public Preview" does NOT propagate breaking changes into THOR: an AGT API change is absorbed by the adapter alone.
- **FR-13** The adapters fail-closed: if the audit substrate can't record, governed actions don't proceed; if identity can't verify, the room/signature isn't trusted; if Gitea is unreachable, no merge is reported as done.
- **FR-14** The Substitution Harness demonstrates (in test) that an external can be replaced by rewriting only its adapter.
- **FR-15** Credentials/tokens for the externals live in the adapters/control plane, never in rooms (consistent with the leash's credential isolation, M2).
- **FR-16** Compliance evidence is exportable in standard formats (CSV/JSON/report) for auditors, derived from the tamper-evident chain (not re-constructed).

## 4. Technical Requirements
- **Language:** Python (control plane; AGT full stack is Python-native; Gitea via REST).
- **Audit substrate:** AGT Merkle/HMAC chaining + Hypervisor receipts (each event signed Ed25519, prev_hash → hash chained). Stored as the EventLog (Postgres append table).
- **Compliance:** AGT Agent Compliance — framework mappings + evidence generation.
- **Identity:** AGT Agent Mesh — Ed25519 keys / DIDs for rooms, decisions, signatures; secure key custody.
- **Gitea:** Gitea REST API (repos, branches, PRs, issues, Actions CI); THOR holds a Gitea service token (in the adapter, not in rooms).
- **Adapter pattern:** each adapter = a stable THOR interface (the vocabulary) + an implementation that calls the external; pinned external versions; adapter-level test suites.
- **Ports:** AGT adapter `:7160`, Gitea adapter `:7170`. Audit + Identity functions are exposed via the AGT adapter surface.
- **Swappability:** the Substitution Harness uses a stub alternate (a minimal GitHub or local-git adapter) to prove only-the-adapter-changes.

## 5. The Logic
- **5.1 Adopt deeply, behind a thin seam** — THOR adopts the substrates but never welds to them. Everywhere it calls `audit.append_event(...)`, `identity.verify(...)`, `git.merge(...)` — THOR's vocabulary — and never sees an AGT or Gitea type. The seam buys churn-isolation, replaceability, and moat-protection.
- **5.2 The Audit Trail: tamper-evidence as the foundation of trust** — each event carries prev_hash → hash + a signature, so altering any past entry visibly breaks the chain. A ledger, not a diary. Every claim (verdict evidence, signatures, divergence records, compliance reports) is only as trustworthy as the chain it lives in. The Manager is the sole writer; this adapter provides the tamper-evidence beneath that write.
- **5.3 Compliance: the audit trail in regulators' language** — the Compliance Mapper translates already-generated audit events into evidence mapped to frameworks, so "here is the SOC2 report" is a derived export, not extra work. Cheap because THOR already produces the underlying evidence.
- **5.4 Identity: trusting rooms and signatures** — answers "is this room really mine?" (room identity) and "did the human really sign this?" (the three signature points), bound to card+payload+nonce (anti-replay). Identity is for verification + system-trust, never per-agent trust-scoring.
- **5.5 Gitea: the executor THOR commands (the peer handshake)** — THOR decides ("approved, merge"), Gitea executes (merges, runs CI). THOR is not a check inside Gitea's branch-protection — it's a peer authority Gitea obeys. Swapping Gitea for GitHub changes only this adapter; the verdict (the moat) always lives in THOR.
- **5.6 The Catalog Bridge: one source, two faces** — the feature catalog (Kind C) and Gitea issues are the same thing surfaced two ways; the bridge keeps them consistent, avoiding two competing feature lists.
- **5.7 Fail-closed, consistently** — if the audit chain can't record, governed actions don't proceed; if identity can't verify, it isn't trusted; if Gitea is unreachable, no feature is reported merged. The substrate failing degrades into "stop, safely," never "proceed anyway."
- **5.8 Proving swappability** — the Strangler strategy is only real if demonstrated. The Substitution Harness proves a stub alternate (a minimal GitHub/local-git adapter) runs THOR unchanged by changing only the adapter — validating the seam is genuinely clean.

## 6. API Strategy
### 6.1 Audit Trail adapter (THOR vocabulary; backs the EventLog)
```
append_event(event)        -> { seq, prev_hash, hash, signature }   # only via Manager's writer
verify_chain(range?)       -> { intact:bool, broken_at? }
export_compliance(framework) -> evidence report (EU AI Act|HIPAA|SOC2|NIST|OWASP)
```
### 6.2 Identity adapter (THOR vocabulary)
```
mint_room_identity(room_id)        -> { identity_token (Ed25519/DID) }
verify_identity(token)             -> { valid:bool, room_id }
verify_signature(sig, payload, nonce) -> { valid:bool, signer }   # the three signature points
revoke_identity(device|room)       -> { revoked:bool }            # e.g. lost mobile (M9)
```
### 6.3 Gitea adapter (THOR vocabulary; the executor THOR commands)
```
create_worktree(repo, base, branch) -> { worktree }
open_pr(branch, meta)               -> { pr_id }
ci_result(branch)                   -> { passed:bool, runs[] }    # feeds verdict M1/M4
git_log(grep) / git_diff(branch)    -> reality (feeds verdict M2/M3)
merge(pr_id, signature_ref)         -> { merged:bool }            # only after Signature 3
list_issues() <-> catalog           -> features (Catalog Bridge)
```
### 6.4 The seam discipline
THOR code calls only these THOR-vocabulary methods. No AGT type, no Gitea type ever appears outside its adapter. Ports: AGT adapter `:7160`, Gitea adapter `:7170`. Credentials live in the adapters, never in rooms (FR-15). Each adapter has its own version + test suite (FR-11).

## 7. Diagrams (described)
- **Figure 1** — The adapter seam: THOR speaks one vocabulary to three adapters; each adapter is the ONLY importer of its external (AGT audit, AGT identity, Gitea). Churn or replacement touches one file.
- **Figure 2** — The tamper-evident audit chain: each event signed + prev_hash→hash chained, so altering any past entry breaks verification — the ledger (not a diary) that every THOR claim rests on, and the source of compliance evidence.
- **Figure 3** — The peer handshake: THOR owns the verdict/authority portably; Gitea executes (merge + CI). Swapping Gitea for GitHub changes only the adapter — the moat never moves.

## 8. Flows
- **8.1 Append a governance event** — Manager's EventLog Writer → Audit adapter `append_event` → adapter signs (Ed25519), chains (prev_hash → hash), persists → returns the sealed entry; the chain is extended and verifiable.
- **8.2 Verify a room's identity** — Wall stamps a room with a minted identity → Manager `verify_identity(token)` before trusting/routing → a forged/stale token fails → room refused (M3 AC-8).
- **8.3 The merge (peer handshake)** — Verdict done + human Signature 3 (verified via Identity adapter) → Manager `merge(pr_id, signature_ref)` → Gitea executes the merge + its no-conflict guarantee → reports back. THOR decided; Gitea executed.
- **8.4 Compliance export** — Auditor needs SOC2 evidence → `export_compliance("SOC2")` derives the report from the tamper-evident chain → exported CSV/JSON/report (evidence, not reconstruction).
- **8.5 Substitution** — Goal: run THOR on GitHub → implement a GitHub adapter exposing the same THOR vocabulary → swap the adapter; THOR's authority + all other modules unchanged (harness verifies).
- **8.6 AGT breaking change** — AGT renames an API → only the AGT adapter's implementation changes; its test suite catches the break and confirms the THOR vocabulary still holds → the rest of THOR is untouched.

## 9. Use Cases / User Stories (story points)
- **US-1 (13)** each external lives behind one adapter that is its only importer — churn/replacement touches one file. *(The core Strangler seam.)*
- **US-2 (8)** every event signed + hash-chained so tampering is detectable.
- **US-3 (8)** audit events map to frameworks + export as evidence (sales-unlocking).
- **US-4 (8)** room identities + human signatures cryptographically verifiable (anti-replay).
- **US-5 (8)** swapping Gitea for GitHub changes only the Gitea adapter.
- **US-6 (5)** the merge is a peer handshake (THOR decides, Gitea executes).
- **US-7 (5)** an AGT breaking change is absorbed by the adapter alone.
- **US-8 (5)** identity is for verification + system-trust only, never per-agent scoring.
- **US-9 (5)** the catalog and Gitea issues stay consistent (one source, two faces).
- **US-10 (5)** substrate failures fail-closed.
- **US-11 (3)** a substitution harness proves swappability in test.
- **US-12 (3)** external credentials live in adapters, never in rooms.

**Total: ~76 points for Module 12.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| AGT API breaking change | Public Preview update | Absorbed by the adapter; its tests catch it; THOR unchanged |
| Audit chain can't record | store down | Fail-closed: governed actions don't proceed (no unaudited actions) |
| Chain tamper detected | hash mismatch | Verification fails; Sentinel alarms + halts (M10 AC-4) |
| Forged/stale room identity | attack/stale room | verify_identity fails → room refused/quarantined |
| Replayed signature | captured ciphertext | bound to card+payload+nonce → rejected |
| Gitea unreachable | network/down | No merge reported done; verdict can't read CI → escalate (M6); retry/queue |
| Gitea token leaked | misconfig | Token in adapter only (not rooms); rotate; never mounted into a room |
| Catalog/issue divergence | sync gap | Catalog Bridge reconciles; one source of truth restored; conflicts surfaced |
| Compliance framework changes | regulation update | Compliance Mapper updated; evidence regenerated from the chain |
| Substitution leaks an external type | crack in the seam | Substitution Harness fails → the leak is found and sealed |
| AGT identity service down | dep failure | Can't mint/verify → fail-closed; alarm |
| Merge succeeds but report lost | network blip | Idempotent merge check; reconcile PR state; don't double-merge |

## 11. Easy vs Difficult Parts
- **Easy:** calling Gitea's REST API; using AGT's audit/identity primitives via pip; mapping issues ↔ catalog.
- **Moderate:** the compliance evidence export; anti-replay signature binding; fail-closed at each substrate boundary.
- **Difficult / real risk:** (1) **Clean seams with zero leakage** — the entire Strangler value depends on no external type ever leaking past its adapter. (2) **Tamper-evidence done correctly** — chaining + signing + idempotent append, performant under many rooms, with verification that genuinely catches tampering. (3) **Authority portability in practice** — truly keeping the merge authority in THOR so a GitHub swap is genuinely one-adapter.

## 12. Technical Difficulties
- **D1 — Seam airtightness.** The adapter exposes only THOR-vocabulary types; lint/architecture tests forbid importing AGT/Gitea outside the adapter; the Substitution Harness proves swappability (a leak makes it fail).
- **D2 — Tamper-evident performance.** Serialized single-writer append (M3), batch-friendly, idempotent; verification on read + by the Sentinel; AGT's optimized chain underneath.
- **D3 — Authority portability.** THOR vocabulary is git-host-neutral; the merge decision lives in THOR, Gitea only executes; the harness includes a non-Gitea stub to keep the interface honest.
- **D4 — AGT preview churn.** Pin versions; the adapter's test suite is the early-warning system; upgrades are an adapter-local task.
- **D5 — Compliance accuracy.** Rely on AGT's maintained mappings; evidence is derived from the tamper-evident chain (not asserted); auditors get the raw chain + the mapping.

## 13. What Needs To Be Built (checklist)
- [ ] Audit Trail adapter (AGT Merkle/HMAC + Hypervisor; THOR-vocabulary append/verify)
- [ ] Compliance Mapper (framework mappings + evidence export) — ADOPT from AGT
- [ ] Identity adapter (AGT Mesh; mint/verify room identity; Ed25519/DID)
- [ ] Signature Verifier (three signature points; bound to card+payload+nonce; anti-replay)
- [ ] Gitea adapter (REST: worktree/PR/CI/issues/log/diff/merge; THOR vocabulary)
- [ ] Catalog Bridge (Gitea issues ↔ catalog Kind C consistency)
- [ ] Adapter Contract & Versioning (the THOR-vocabulary interfaces; per-adapter test suites)
- [ ] Substitution Harness (prove swappability: a non-Gitea / alternate stub)
- [ ] Fail-closed boundaries (can't record/verify/reach → stop safely)
- [ ] Credential custody (external tokens in adapters, never in rooms)
- [ ] Architecture lint (forbid AGT/Gitea imports outside their adapters)

## 14. Dependencies & Sequencing
**Depends on:** AGT (audit, compliance, identity) + Gitea (git/PR/CI) — the adopted externals. Module 3 (Manager) — the sole EventLog writer that uses the Audit adapter; the authority that directs the Gitea adapter.

**Blocks / depended on by:** Module 6 (Verdict Engine) — reads git/CI (Gitea adapter) + the audit window (Audit adapter). Module 1 (Wall) — room identity stamping (Identity adapter). Modules 8 & 9 (PM Surface, Mobile) — signature verification (Identity adapter). Module 10 (Sentinel) — chain integrity verification (Audit adapter). Effectively the substrate beneath the moat — interfaced (stubbed) early, filled in here.

**Build-order note:** The adapters are interfaced early (stubbed: a local-git stand-in, an always-allow audit log, a minimal signer) so Modules 1–11 can be built and tested, then filled in with the real AGT + Gitea here. **Milestone:** every governance event lands in a tamper-evident signed chain that detects a forced tamper; a room identity + human signature verify (and forgeries are rejected); a real merge runs through the Gitea adapter as a peer handshake; and the Substitution Harness proves an external can be swapped by changing only its adapter.

## 15. Test / Acceptance Criteria (evidence-based)
- **AC-1** No AGT or Gitea type appears in THOR code outside its adapter (architecture lint).
- **AC-2** Every governance event is signed + hash-chained; a forced edit to a past event is detected on verification.
- **AC-3** Compliance evidence for a named framework (e.g. SOC2) is exported and traces to the tamper-evident chain.
- **AC-4** A room identity verifies; a forged/stale identity is rejected.
- **AC-5** A human signature for each of the three signature points verifies; a replayed/forged signature is rejected.
- **AC-6** A real merge runs through the Gitea adapter only after a verified Signature 3, as a peer handshake.
- **AC-7** Swapping the Gitea adapter for an alternate (GitHub/local stub) leaves THOR's authority + other modules unchanged.
- **AC-8** An AGT version bump is absorbed by the adapter alone; THOR-vocabulary callers are unchanged.
- **AC-9** When the audit substrate can't record, governed actions don't proceed (fail-closed).
- **AC-10** When identity can't verify, the room/signature isn't trusted (fail-closed).
- **AC-11** External credentials are never present in a room (verified by inspecting room env/FS).
- **AC-12** Identity is used only for verification/system-trust; no per-agent trust score is computed anywhere.

**Headline milestone:** AC-1 + AC-2 + AC-7 together — no external type leaks past its adapter, the audit chain detects tampering, and an external can be swapped by changing only its adapter. That proves the Strangler foundation: the substrate is fully used yet fully swappable, and the moat stands on it without being welded to it.

---

*End of THOR Module 12 — The Foundation Adapters PRD v1.0. All 17 modules are now specified (the 12 PRD documents cover the 17 modules — several modules are grouped here as the foundation substrate). The complete THOR Enterprise PRD suite — Bible + System Design & Flow + 12 module PRDs — is complete.*
