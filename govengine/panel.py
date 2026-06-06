"""
Sub-module 6.8 — Panel Adjudicator. Trusts no single mechanism (FR-7).

Combines the 8 probes + divergence + stakes into a verdict:
  done     — all 8 pass, no divergence, no conflict, stakes normal.
  not_done — one or more probes failed (the contract/reality agree it's incomplete); blockers named.
  escalate — cannot compute reliably (fail-closed), OR divergence (a possible lie), OR a CONFLICT
             (the done-signals M1+M5 say done but reality M3 contradicts), OR a high-stakes change.

The cardinal rule (D3): never a false `done`. When unsure, escalate (the safe side).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Verdict:
    verdict: str                      # "done" | "not_done" | "escalate"
    blockers: list = field(default_factory=list)
    divergence: object | None = None
    stakes: str = "normal"
    reason: str = ""


def _p(probes, name):
    return next(x for x in probes if x.name == name)


def adjudicate(probes, divergence, stakes: str, errors: list[str] | None = None) -> Verdict:
    v = _decide(probes, divergence, stakes, errors)
    v.stakes = stakes                                       # always report the true stakes level
    return v


def _decide(probes, divergence, stakes: str, errors: list[str] | None) -> Verdict:
    if errors:                                              # FR-15 / AC-8 — fail-closed
        return Verdict("escalate", blockers=errors, reason="cannot compute reliably (fail-closed)")

    failed = [(x.name, x.evidence) for x in probes if not x.passed]

    if divergence is not None and divergence.found:        # AC-2 — the lie-detector
        return Verdict("escalate", blockers=failed, divergence=divergence,
                       reason="claim-vs-reality divergence (possible dishonesty)")

    # CONFLICT: the signals that would say "done" (verifier M1 + contracts M5) pass, but git reality
    # (M3 diff) contradicts them → the mechanisms disagree → escalate, never guess (FR-8 / AC-4).
    done_signals = _p(probes, "M1").passed and _p(probes, "M5").passed
    if done_signals and not _p(probes, "M3").passed:
        return Verdict("escalate", blockers=failed,
                       reason="conflict: verifier+contracts say done but the diff doesn't match")

    if failed:                                             # AC-1 — incomplete, specific blockers
        return Verdict("not_done", blockers=failed, reason="probes failed")

    if stakes == "high":                                   # FR-9 / AC-10 — human signature required
        return Verdict("escalate", stakes="high",
                       reason="high-stakes change requires a human signature even with all probes passing")

    return Verdict("done", reason="all 8 probes pass, no divergence, within policy")
