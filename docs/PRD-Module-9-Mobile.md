# THOR Module 9 — Mobile / Remote + Legible Refusal

**Module PRD + FRD.** Read alongside the Bible (Pillar 4 Mobile/Remote, §16 legible refusal, the three signature points, HCD), the System Design & Flow doc (PhoneBridge, §5.5 the E2EE phone-approval sequence), and Module 8 (the PM Surface, whose data + signature model this shares).

> Saved from `THOR-Module9-Mobile-PRD.pdf` (v1.0) on 2026-06-06, transcribed faithfully. Build to this PRD; flag drift (Rule 9).

- **Module:** 9 — Mobile / Remote + Legible Refusal · **Pillar:** 4 (Mobile / Remote) · **Kind:** BUILD (extend the existing postman + Cloudflare E2EE bridge to N parallel rooms + the three signature points)
- **Build order:** Ninth — after the PM Surface; the phone is a remote head on the same truth.
- **One-line purpose:** Let the accountable human direct work and sign the decisions that matter from a phone, anywhere — securely, end-to-end-encrypted, with every block explained in plain language — so command is not chained to a desk.
- **Version:** 1.0

---

## 1. Overview
The PM Surface (M8) is the desktop cockpit. This module makes the *same command* available from a phone. The defining requirement: the phone is a **remote head on the same truth** (the Manager), not a separate system with its own state. A merge approved on the phone and one on the desktop are the same action against the same Manager.

THOR already has the hard part: a working phone bridge (postman + a Cloudflare worker) — an E2EE relay where the relay never sees plaintext. This module extends it from single-project to: (a) N parallel rooms/features, (b) the three signature points, (c) legible refusal on the small screen.

The security model is strict (the phone is the most-exposed surface): **E2EE** (the relay is a dumb pipe that never decrypts), **signed approvals** (every signature is Ed25519, the operator's identity), **allowlisted commands** (a bounded set — direct, observe, sign — never arbitrary control), and **no open inbound port** (an outbound tunnel, so nothing listens on the control plane). Legible refusal lives here too — on a phone, a non-technical operator needs the *why* in one clear sentence, not a trace.

## 2. Sub-modules
- **9.1 PhoneBridge (extended postman)** — the control-plane relay endpoint; pushes Manager events E2EE to the phone; receives signed responses. Extends postman to N rooms.
- **9.2 E2EE Channel (Cloudflare relay)** — the encrypted transport; relays ciphertext only, never holds keys or sees plaintext (zero-knowledge).
- **9.3 Mobile App / Client** — the phone-side condensed cockpit (approval queue, room glances, kanban essentials); shares M8's data + signature model.
- **9.4 Mobile Signature Pad** — phone-side Ed25519 signing for the three signature points + escalations; the operator's signing identity on-device.
- **9.5 Command Allowlist** — the bounded set the phone may perform (approve/reject, mark-ready, add/prioritize, view); anything else rejected.
- **9.6 Push & Notify** — alerts the operator when a card needs them, so round-the-clock work doesn't stall at a desk.
- **9.7 Legible Refusal (mobile)** — the plain-language renderer tuned for the small screen (one-sentence why + expandable detail); shared with M8.
- **9.8 Offline/Reconnect Handler** — intermittent connectivity: clear stale/disconnected state; never old-as-live; never signs against stale; resumes cleanly.

## 3. Functional Requirements (FR)
- **FR-1** The phone is a remote head on the same Manager truth — no separate authoritative state; the same card resolved on phone or desktop is one action.
- **FR-2** All phone↔control-plane traffic is end-to-end encrypted; the relay never sees plaintext or holds keys.
- **FR-3** Every approval/rejection from the phone carries an Ed25519 signature bound to card + payload, verified by the Manager (P6).
- **FR-4** The phone only performs allowlisted commands; arbitrary/non-allowlisted commands are rejected.
- **FR-5** The bridge uses an outbound tunnel with NO open inbound port on the control plane.
- **FR-6** The phone surfaces the three signature points (plan, ticket, merge) + critical escalations as actionable cards.
- **FR-7** Every block/escalation on the phone includes a plain-language reason, tuned for the small screen.
- **FR-8** The phone push-notifies the operator when a card needs them.
- **FR-9** The phone shows live (or clearly-marked-stale) room/stage states and cost; never stale-as-live.
- **FR-10** On disconnect, the phone shows a clear disconnected state + disables signing; resumes cleanly on reconnect.
- **FR-11** The phone cannot reach into a room or bypass governance; it directs/observes/signs through governed channels only.
- **FR-12** Every phone action is recorded as an event via the Manager (audited identically to desktop).
- **FR-13** The phone shares M8's data + signature model, so desktop and mobile are consistent and a decision is never double-counted.
- **FR-14** The signing identity on the device is protected (keystore/secure enclave); a compromised relay cannot forge a signature.
- **FR-15** The phone handles concurrent resolution gracefully: if a card is resolved on desktop first, the phone shows "already decided".
- **FR-16** Usable by a non-technical operator: glanceable states, one-tap signing, plain-language cards.

## 4. Technical Requirements
- **Existing foundation:** the working postman (control-plane) + Cloudflare worker (relay) E2EE bridge — extend, don't rebuild.
- **Language:** the bridge + mobile client stay in JS/TS; native wrapper (Capacitor) or a mobile-optimized PWA over the same DashboardAPI model.
- **Encryption:** E2EE — keys only on device + control plane; the relay transports ciphertext (zero-knowledge). Established crypto (NaCl/libsodium-style sealed boxes).
- **Signatures:** Ed25519; key in the device keystore/secure enclave; bound to card-id + payload-hash + nonce; Manager-verified (same model as M8).
- **Transport:** outbound tunnel (the control plane dials out) — no inbound port. Push via APNs/FCM (wake/summary only, no sensitive plaintext).
- **Data:** all reads are Manager projections relayed E2EE; no authoritative local store; cache for responsiveness only.
- **Consistency:** shares M8's API + signature model; same card schema, same verification path.

## 5. The Logic
- **5.1 A remote head, not a second system** — same Manager, same cards, same signatures, same single truth. No "mobile state" that could diverge. A merge card appears on both; whichever signs first resolves it; the other shows "already decided." The phone adds reach, not a new source of truth.
- **5.2 The E2EE relay is a dumb pipe** — the relay bridges two endpoints that can't otherwise reach each other; it relays ciphertext and nothing else. Even a fully-compromised relay learns nothing and forges nothing — at most it drops/delays (a liveness issue). The most-exposed surface can still be trusted because security doesn't depend on the relay being honest.
- **5.3 No open inbound port** — the control plane dials OUT through the relay (an outbound tunnel). Nothing listens for inbound connections. The phone capability adds zero new inbound attack surface — critical when the control plane holds the keys to a codebase.
- **5.4 Allowlisted commands: reach without risk** — the phone may approve/reject, mark-ready, add/prioritize, and view; nothing else. The most-likely-lost device is scoped to accountable-operator actions; rules are changed only host-side (the amend path), never from the pocket.
- **5.5 Signing from the pocket (HCD, mobile)** — the three signature points work identically: a plain-language card → tap approve → an Ed25519 signature from the device's protected key, sent E2EE, verified by the Manager. Bound to card + payload + nonce (no replay). A phone approval is exactly as authoritative (and audited) as a desktop one.
- **5.6 Legible refusal on a small screen** — the card leads with one plain sentence + expandable detail. A non-technical operator can decide a governance question in seconds from their pocket.
- **5.7 Stale-safety on flaky connections** — on disconnect, show "disconnected", disable signing, and re-validate any pending action against the Manager's current state at submit. The phone never lets the operator sign against a stale view.

## 6. API Strategy
The phone communicates only through the E2EE bridge; it shares M8's card + signature schema. All payloads are encrypted end-to-end; the relay sees ciphertext.
### 6.1 The bridge channel (E2EE, PhoneBridge ↔ Cloudflare relay ↔ phone)
```
# control plane -> phone (push, ciphertext)
card.push   E2EE{ card_id, type, feature_id, summary, legible_reason }
state.push  E2EE{ rooms_glance[], feature_states, cost }
notify      (APNs/FCM wake — summary only, no sensitive plaintext)
# phone -> control plane (signed, ciphertext)
approve     E2EE{ card_id, signature(Ed25519) }  -> Manager verifies + acts
reject      E2EE{ card_id, signature, reason }   -> Manager verifies + acts
mark_ready  E2EE{ feature_id, signature? }       -> Scheduler
add_feature E2EE{ title, context, priority }     -> catalog (Kind C)
view_request E2EE{ scope }                       -> state.push reply
```
### 6.2 Allowlist (the only commands the phone may issue)
```
ALLOWED:  approve, reject, mark_ready, add_feature, prioritize, view
REJECTED: anything else — reach-into-room, change-rules, bypass-governance, arbitrary-command
```
### 6.3 Security properties
| Property | Mechanism |
|---|---|
| E2EE | keys on device + control plane only; relay sees ciphertext (FR-2) |
| No inbound port | control plane dials out via the relay (FR-5) |
| Signed approvals | Ed25519 bound to card+payload+nonce, Manager-verified (FR-3) |
| Bounded power | command allowlist (FR-4) |
| Key protection | device keystore / secure enclave (FR-14) |
| Audited | every phone action → Manager event (FR-12) |
### 6.4 Consistency with Module 8
Same card schema, same signature model, same Manager verification. Desktop and phone are two heads; the Manager dedupes resolution (FR-15).

## 7. Diagrams (described)
- **Figure 1** — The E2EE bridge: the control plane dials out through the Cloudflare relay (a dumb, zero-knowledge pipe) to the phone; the relay transports ciphertext only and can forge nothing; no inbound port is opened.
- **Figure 2** — A remote head on one truth: phone and desktop are twin windows onto the same Manager; the same card resolves once, whichever signs first; no divergent mobile state.
- **Figure 3** — Bounded power: the phone may only direct, observe, and sign (allowlisted); it cannot reach into a room, change rules, or bypass governance — so the most-exposed device carries the least catastrophic risk.

## 8. Flows
- **8.1 Sign a merge from the phone** — verdict passes → Manager raises a merge card → PhoneBridge pushes it E2EE + notifies → operator taps approve → Mobile Signature Pad produces an Ed25519 signature (device key) → sent E2EE → Manager verifies → directs Gitea to merge → the card clears on both surfaces.
- **8.2 Review a legible block** — escalation card → phone shows "Blocked: edited billing/ outside F47's area. Allow once / reject?" → operator rejects → signed, relayed, recorded.
- **8.3 Concurrent resolution** — a card open on both; operator signs on desktop first; the phone shows "already decided" (Manager dedupes).
- **8.4 Disconnect mid-review** — phone loses connectivity → "disconnected", signing disabled → on reconnect the state is re-fetched and re-validated at submit.
- **8.5 Relay compromise** — assume the relay is fully compromised → it sees only ciphertext, no keys, no forgeable signatures → worst case it drops/delays (liveness). It cannot approve/reject/fabricate. Security holds.

## 9. Use Cases / User Stories (story points)
- **US-1 (13)** sign the three decisions from a phone, anywhere — command not chained to a desk. *(The core value.)*
- **US-2 (13)** E2EE through a zero-knowledge relay — a compromised relay learns and forges nothing. *(The core security property.)*
- **US-3 (8)** the control plane opens no inbound port — zero new attack surface.
- **US-4 (8)** the phone can only do allowlisted things — least catastrophic risk on the most-exposed device.
- **US-5 (8)** blocks explained in one plain sentence on the small screen.
- **US-6 (8)** a remote head on the same truth — a decision is never double-counted.
- **US-7 (5)** push-notified when a card needs me.
- **US-8 (5)** device-protected signing key + Manager verification — a phone approval is unforgeable.
- **US-9 (5)** on a flaky connection, shown disconnected; can't sign against stale state.
- **US-10 (5)** every phone action audited identically to desktop.
- **US-11 (3)** glanceable + one-tap — command from a pocket without a terminal.

**Total: ~81 points for Module 9.**

## 10. Error & Edge Cases
| Case | Trigger | Handling |
|---|---|---|
| Relay compromised | hostile relay | E2EE: ciphertext only; can't forge/decrypt; at worst drops messages |
| Phone lost/stolen | device compromise | Allowlist bounds damage; revoke the device's signing identity; rules host-only |
| Stale view on the phone | flaky connection | Disconnected state; signing disabled; re-validate on reconnect |
| Concurrent resolve | both surfaces open | Manager dedupes; second shows "already decided" |
| Signature replay attempt | captured ciphertext | Signature bound to card+payload+nonce; Manager rejects replays |
| Push notification delayed | platform push lag | Card still appears on next sync; nothing depends on the push |
| Non-allowlisted command | malicious/buggy client | Rejected at the bridge; logged as a security event |
| Inbound connection attempt | scan/attack | No inbound port exists; nothing to connect to |
| Key unavailable on device | keystore issue | Signing blocked with a clear error; never fake a signature |
| Approve on stale card | edge timing | Submit re-validates; if changed, rejected with "state changed, review again" |
| Relay outage | Cloudflare down | Phone shows disconnected; desktop still works; resume when relay returns |
| Large state push | many rooms | Glanceable summaries; detail on demand; don't flood the device |

## 11. Easy vs Difficult Parts
- **Easy:** extending postman to relay N rooms' cards/states; the mobile card UI (mirrors M8); push notifications.
- **Moderate:** sharing M8's card + signature schema across surfaces; offline/reconnect + stale-safety; glanceable summaries.
- **Difficult / real risk:** (1) **E2EE done correctly** — real key management, the relay truly zero-knowledge, no subtle leak. (2) **Device-side signing key protection** — usable for signing but not extractable, revocable if lost. (3) **Stale-safety on mobile** — intermittent connectivity makes "never sign against stale state" harder than on desktop.

## 12. Technical Difficulties
- **D1 — Airtight E2EE.** Established libraries (libsodium/NaCl sealed boxes); keys never leave device/control-plane; the relay handles only ciphertext; adversarial review + a "compromised relay" test asserting it learns/forges nothing.
- **D2 — Signing-key custody.** Device keystore/secure enclave; signature bound to card+payload+nonce (no reuse); per-device identity revocable at the Manager; a lost device's key is revoked, not catastrophic.
- **D3 — Stale-safety.** Disable signing when disconnected; re-validate every action against the Manager's current state at submit; clear stale banners; never cached-as-live.
- **D4 — No-inbound-port tunnel.** The control plane dials the relay; verified to add no listening surface; the relay only matches the two encrypted endpoints.
- **D5 — Cross-surface consistency.** One Manager truth; shared card+signature schema; Manager dedupes; both surfaces re-validate at submit.

## 13. What Needs To Be Built (checklist)
- [ ] PhoneBridge — extend postman from one project to N rooms (cards + states out, signed actions in)
- [ ] E2EE channel hardening (keys on device + control plane; relay zero-knowledge)
- [ ] Mobile client (condensed cockpit)
- [ ] Mobile Signature Pad (Ed25519; device keystore/enclave; bound signatures)
- [ ] Command Allowlist (enforce the bounded set; reject the rest)
- [ ] Push & Notify (APNs/FCM wake; summary only)
- [ ] Legible Refusal (mobile) — one-sentence why + expandable detail
- [ ] Offline/Reconnect Handler (disconnected state; disable signing; re-validate)
- [ ] Device identity revocation (lost-device path at the Manager)
- [ ] Cross-surface dedupe (consistency with Module 8)
- [ ] "Compromised relay" + "replay" security test suite

## 14. Dependencies & Sequencing
**Depends on:** Module 8 (PM Surface) — shares its card + signature model + DashboardAPI data; the phone is its remote twin (hard dep). Module 3 (Manager) — the single truth the phone reads from and signs against; verifies signatures; dedupes. The existing postman + Cloudflare bridge — the proven E2EE foundation.

**Blocks / depended on by:** Completes Pillar 4 (Mobile/Remote). Nothing downstream strictly depends on mobile; it's a reach extension.

**Build-order note:** Build after the PM Surface so the card + signature model exists to share. Extend the existing bridge rather than rebuild. **Milestone:** an operator receives a merge card on their phone, signs it with a device-protected key over an E2EE channel, the Manager verifies it and merges, and a "compromised relay" test confirms the relay could neither read the card nor forge the signature.

## 15. Test / Acceptance Criteria (evidence-based)
- **AC-1** A merge approved on the phone produces a Manager-verified Ed25519 signature and triggers the merge exactly as a desktop approval would.
- **AC-2** With the relay treated as fully compromised, it can read no card contents, no keys, and forge no signature (zero-knowledge — the relay only ever holds ciphertext).
- **AC-3** The control plane opens no inbound port for the phone capability (port scan — nothing listening).
- **AC-4** A non-allowlisted command from the phone is rejected and logged.
- **AC-5** A block shown on the phone includes a one-sentence plain-language reason.
- **AC-6** A card resolved on desktop shows "already decided" on the phone (no double-resolution).
- **AC-7** On disconnect, the phone disables signing and shows a clear stale/disconnected state; never cached-as-live.
- **AC-8** A captured/replayed approval is rejected (signature bound to card+payload+nonce).
- **AC-9** A lost device's signing identity can be revoked; after which its signatures are rejected.
- **AC-10** Every phone action is recorded as an event identically to desktop.
- **AC-11** The phone cannot reach into a room or change rules (no such path exists).
- **AC-12** Phone and desktop render the same card from the same Manager state consistently.

**Headline milestone:** AC-1 + AC-2 + AC-3 together — a real merge signed from a phone over an end-to-end-encrypted channel, where the relay can neither read nor forge anything and the control plane exposes no inbound port. That proves command-from-anywhere without weakening THOR's security.

---

*End of THOR Module 9 — Mobile / Remote + Legible Refusal PRD v1.0. Pillar 4 is now specified, completing the human-command layer (desktop + mobile). Next module: 10 — The Sentinel (meta-governance: the layer that verifies THOR itself is alive, loaded, connected, untampered, and still catching — and can halt).*
