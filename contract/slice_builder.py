"""
Sub-module 5.2 — Feature-Slice Builder.

Extracts ONE feature's slice from the catalog (Kind C) + its policy slice (Kind B) and packages a
FeatureSlice. It takes a single feature dict (never the catalog), and emits only a WHITELISTED set
of fields — so it structurally cannot leak the roadmap, another feature, or credentials (FR-4/5/14,
D5). The output is validated against the FeatureSlice schema.
"""
from __future__ import annotations

from .messages import FeatureSlice

# The only fields a slice may carry (D5 slice minimality).
_WHITELIST = ("feature_id", "task_type", "context", "goals", "non_goals",
              "contract", "scope", "capability_tags")


def build_slice(feature: dict, policy: dict | None = None) -> FeatureSlice:
    """
    `feature` is ONE feature's record (not the catalog). `policy` is its Kind-B scope slice.
    Returns a validated FeatureSlice — extra/unknown fields are dropped, never forwarded.
    """
    policy = policy or {}
    return FeatureSlice(
        feature_id=feature["feature_id"],
        task_type=feature.get("task_type", "build"),
        context=feature.get("context", ""),
        goals=list(feature.get("goals", [])),
        non_goals=list(feature.get("non_goals", [])),
        # the spec the Verdict Coordinator reads from trusted state: criteria + the test files (C4).
        contract={"acceptance_criteria": list(feature.get("acceptance_criteria", [])),
                  "test_file": feature.get("planned_test") or feature.get("test_file"),
                  "regression_file": feature.get("regression_file")},
        scope={"files": list(policy.get("scope_files", feature.get("scope_files", [])))},
        capability_tags=list(feature.get("capability_tags", [])),
    )


def leaks_catalog(slice_obj: FeatureSlice, other_feature_ids: set[str]) -> bool:
    """True if the slice mentions any OTHER feature id (a leak). Used to prove minimality (AC-2)."""
    blob = slice_obj.model_dump_json()
    return any(fid in blob for fid in other_feature_ids if fid != slice_obj.feature_id)
