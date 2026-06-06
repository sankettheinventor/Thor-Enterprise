"""
Sub-module 12.6 — Catalog Bridge (FR-10 / AC of single-source).

The feature catalog (Kind C, M8) and Gitea issues are the SAME thing surfaced two ways: the operator
sees a kanban, the system sees issues. The bridge keeps them consistent — one source, two faces — so
there is never a competing feature list.
"""
from __future__ import annotations


def issue_to_feature(issue: dict) -> dict:
    """Map a Gitea issue → a catalog feature (Kind C)."""
    return {"feature_id": issue["number"], "title": issue["title"],
            "context": issue.get("body", ""), "status": "ready" if issue.get("open", True) else "done"}


def feature_to_issue(feature: dict) -> dict:
    """Map a catalog feature → a Gitea issue."""
    return {"number": feature["feature_id"], "title": feature["title"],
            "body": feature.get("context", ""), "open": feature.get("status") != "done"}


def reconcile(features: list[dict], issues: list[dict]) -> dict:
    """One source of truth: surface drift between the kanban and the issue tracker."""
    feat_ids = {f["feature_id"] for f in features}
    issue_ids = {i["number"] for i in issues}
    return {"only_in_catalog": sorted(feat_ids - issue_ids),
            "only_in_issues": sorted(issue_ids - feat_ids),
            "consistent": feat_ids == issue_ids}
