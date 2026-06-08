"""
Sub-module 7.8 — Findings & Ticket Bridge.

Routes QA findings as structured bugs to the DB via the Manager (FR-9), and QA failures as CEO
cards that — when signed (Signature 2) — become re-work tickets fed back to the Scheduler (FR-10).
Also routes Checker findings to the DB (shown on the Dashboard later).

Keeps findings in the DB, never agent memory (AC-4) — so the system stays light and findings become
queryable data.
"""
from __future__ import annotations


class FindingsTicketBridge:
    def __init__(self, manager) -> None:
        self.manager = manager

    def emit_qa_bugs(self, feature_id: str, bugs: list[str]) -> list[str]:
        """Persist QA findings as structured bugs (FR-9 / AC-4)."""
        return [self.manager.append_bug(feature_id, "high", b, source="qa") for b in bugs]

    def raise_qa_fail_card(self, feature_id: str, bugs: list[str]) -> str:
        """QA failure → a CEO card; becomes a re-work ticket only on Signature 2 (FR-10 / AC-6)."""
        return self.manager.raise_card("qa_fail", feature_id, {"bugs": bugs}, held=True)

    def raise_capability_gap_card(self, feature_id: str, missing_tag: str) -> str:
        """Mid-build discovery of a needed capability → a card, never a silent skill add (FR-18/AC-10)."""
        return self.manager.raise_card("capability_gap", feature_id,
                                       {"missing_tag": missing_tag}, held=True)

    def raise_merge_card(self, feature_id: str, repo: str | None = None, branch: str | None = None,
                         snapshot_sha: str | None = None) -> str:
        """Verdict done → a merge card; merge only on Signature 3 (FR-15). Carries the merge context
        (repo/branch) + the verdict snapshot so the dashboard's Sign can drive the real, FRESH merge."""
        return self.manager.raise_card("merge", feature_id, {
            "feature_id": feature_id, "repo": repo, "branch": branch, "snapshot_sha": snapshot_sha})
