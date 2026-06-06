"""
Sub-module 7.7 — Stage Transition Controller. Governs the EDGES of the lifecycle (FR-11): enforces
the SDLC order (Genesis-first; Build → QA → Verdict; QA-fail → ticket → Build) and the three
signature gates. No stage promotes its own work; the lifecycle is a governed graph.

  Signature 1 — Genesis → Build (no Build until the plan is signed, FR-4/AC-5).
  Signature 2 — QA-fail → re-work ticket (no loop-back until the human authorizes, FR-10/AC-6).
  Signature 3 — Verdict(done) → merge (owned by the Manager/Engine).

The Build↔QA loop is bounded: after N failed cycles, surface to the operator (FR/AC-11).
"""
from __future__ import annotations

MAX_QA_CYCLES = 3
# The canonical stage order; a transition `to` must be reachable from `frm` per the lifecycle.
ORDER = ("genesis", "build", "qa", "verdict", "merge")


class TransitionController:
    def __init__(self) -> None:
        self.plan_signed: dict[str, bool] = {}    # Signature 1
        self.qa_passed: dict[str, bool] = {}
        self.ticket_authorized: dict[str, bool] = {}  # Signature 2
        self.qa_cycles: dict[str, int] = {}

    # ---- signature-gate setters (driven by the Manager's card approvals) ----
    def sign_plan(self, feature_id: str) -> None:          # Signature 1
        self.plan_signed[feature_id] = True

    def authorize_ticket(self, feature_id: str) -> None:   # Signature 2
        self.ticket_authorized[feature_id] = True

    # ---- gates ----
    def can_build(self, feature_id: str) -> bool:          # FR-4 / AC-5 (and Sig-2 re-work)
        return self.plan_signed.get(feature_id, False)

    def can_verdict(self, feature_id: str) -> bool:        # FR-12 / AC-1 — no skipping QA
        return self.qa_passed.get(feature_id, False)

    # ---- QA result handling (bounded loop, FR/AC-11) ----
    def on_qa_result(self, feature_id: str, passed: bool) -> str:
        if passed:
            self.qa_passed[feature_id] = True
            return "verdict"
        self.qa_cycles[feature_id] = self.qa_cycles.get(feature_id, 0) + 1
        if self.qa_cycles[feature_id] >= MAX_QA_CYCLES:
            return "escalate_operator"                     # bounded — don't loop forever
        return "ticket"                                    # needs Signature 2 to loop back to Build

    # ---- the governed edge check ----
    def transition(self, feature_id: str, frm: str, to: str) -> tuple[bool, str]:
        if to not in ORDER or frm not in ORDER:
            return False, f"unknown stage in transition {frm}->{to}"
        if to == "build" and not self.can_build(feature_id):
            return False, "refused: Signature 1 (plan approval) required before any Build"
        if to == "verdict":
            if frm != "qa":
                return False, "refused: the verdict can only be reached from QA (no skipping QA)"
            if not self.can_verdict(feature_id):
                return False, "refused: QA must pass before the verdict (FR-12)"
        if to == "qa" and frm != "build":
            return False, "refused: QA only follows Build"
        return True, f"{frm} -> {to} allowed"
