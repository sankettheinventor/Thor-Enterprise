"""
Moat-LOGIC gate test (BUG-2 fix): the Panel Adjudicator (§7b "the panel adjudicator is correct — DO
NOT loosen"), exercised DIRECTLY and DOCKER-FREE so the cardinal rule (never a false `done`) is
guarded on EVERY commit. The live ACs (tests/govengine, deferred) prove it against real probe runs.
"""
from govengine.divergence import Divergence
from govengine.panel import adjudicate
from govengine.probes import ProbeResult

ALL = ("M1", "M2", "M3", "M4", "M5", "R1", "R2", "R3")


def _probes(failing=()):
    return [ProbeResult(n, n not in failing, "ok" if n not in failing else "fail") for n in ALL]


def test_all_pass_no_divergence_normal_stakes_is_done():
    v = adjudicate(_probes(), Divergence(found=False), "normal")
    assert v.verdict == "done"


def test_a_failed_probe_is_not_done():
    v = adjudicate(_probes(failing=("M4",)), Divergence(found=False), "normal")
    assert v.verdict == "not_done"


def test_divergence_escalates_even_if_probes_pass():
    v = adjudicate(_probes(), Divergence(found=True, signals=["claimed X but git shows Y"]), "normal")
    assert v.verdict == "escalate"


def test_errors_fail_closed_to_escalate():
    v = adjudicate(_probes(), Divergence(found=False), "normal", errors=["inputs unreadable"])
    assert v.verdict == "escalate"


def test_conflict_done_signals_but_diff_mismatch_escalates():
    # M1 (verifier) + M5 (contracts) say done, but M3 (diff matched cited files) fails → escalate
    v = adjudicate(_probes(failing=("M3",)), Divergence(found=False), "normal")
    assert v.verdict == "escalate"


def test_high_stakes_requires_signature_even_when_all_pass():
    v = adjudicate(_probes(), Divergence(found=False), "high")
    assert v.verdict == "escalate"
