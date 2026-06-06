"""
Sub-module 8.6 — Legible Refusal Renderer (FR-6 / AC-3, the differentiator).

Translates the Leash/Engine reason codes into plain-language explanations a non-technical operator
understands — not "GovernanceDenied: scope_violation E0042" but "This change was blocked because it
tried to edit files outside feature F47's approved area." Unmapped codes fall back to a SAFE generic
explanation plus the raw code for support — never nothing (D1).
"""
from __future__ import annotations

# (substring in the reason code) -> (plain-language explanation). First match wins; order by specificity.
_RULES: list[tuple[str, str]] = [
    ("forbidden", "This was blocked because it touched a forbidden area (for example secrets or infrastructure files)."),
    ("scope", "This change was blocked because it tried to edit files outside this feature's approved area."),
    ("governor_unavailable", "This was paused because the safety governor was briefly unreachable — to stay safe, nothing was allowed through."),
    ("dependency-manifest", "This needs your approval because it changes the project's dependencies."),
    ("no policy", "This was blocked because this room has no approved rules loaded yet."),
    ("high-stakes", "This needs your signature because it touches sensitive, high-stakes files."),
    ("divergence", "This was flagged because what the agent said it did doesn't match what actually changed in the code."),
    ("conflict", "This needs your decision because the automated checks disagree with each other."),
    ("unaudited", "This was blocked because the action couldn't be recorded — THOR won't allow anything it can't audit."),
    ("malicious", "This was stopped because a tool or file looked malicious; the room was shut down to keep you safe."),
]

_FALLBACK = "This action needs your attention."


def render(reason: str, feature_id: str | None = None) -> str:
    text = _FALLBACK
    raw_needed = True
    for key, explanation in _RULES:
        if key in (reason or "").lower():
            text = explanation
            raw_needed = False
            break
    if feature_id:
        text = text.replace("this feature's", f"feature {feature_id}'s")
    # safe fallback keeps the raw code for support; mapped codes hide it entirely (clean for the operator)
    return f"{text} (details: {reason})" if raw_needed else text
