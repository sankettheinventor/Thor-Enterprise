"""
Sub-module 7.9 — the SDLC → merge driver (Integration PRD seams S8/S9).

Drives the existing §7b bridge + Manager from a LIVE verdict: a `done` verdict raises the merge
card; once the human's Signature 3 is VERIFIED and the verdict is still FRESH (R9), the Manager
merges through the Gitea adapter and the room is destroyed. THOR decides; Gitea executes. This
DRIVES the bridge/transitions — it never rewrites them.
"""
from __future__ import annotations

from .bridge import FindingsTicketBridge


class MergeDriver:
    def __init__(self, manager, engine=None) -> None:
        self.manager = manager
        self.bridge = FindingsTicketBridge(manager)
        self.engine = engine          # GovernanceEngine — for the R9 freshness check before merge

    def on_verdict(self, verdict_result: dict) -> str | None:
        """A live verdict drives the card: `done` → a merge card (Signature 3 pending). Returns its id."""
        if verdict_result.get("verdict") == "done":
            return self.bridge.raise_merge_card(verdict_result["feature_id"])
        return None   # not_done/escalate are handled by the qa-fail / escalation paths

    def merge_if_authorized(self, card_id: str, repo: str, branch: str,
                            verdict_result: dict, ctx=None) -> dict:
        """Merge ONLY on a verified Signature 3 AND a fresh verdict (R9). Else refuse — card stays open."""
        if not self.manager.is_card_approved(card_id):
            return {"merged": False, "reason": "no verified Signature 3 — the merge card is not approved"}
        if self.engine is not None and ctx is not None and not self.engine.is_fresh(verdict_result, ctx):
            return {"merged": False, "reason": "verdict is stale (branch HEAD moved) — re-run before merge (R9)"}
        fid = verdict_result["feature_id"]
        res = self.manager.direct_merge(repo, branch, fid, signature_ref=card_id)   # card_id = the Sig-3 ref
        if res.get("merged") and verdict_result.get("room_id"):
            try:
                self.manager.destroy_room(verdict_result["room_id"])
            except Exception:  # noqa: BLE001 — room already gone; the branch (the work) persists
                pass
        return res
