# Lab-trust proof (Phase 0, step 4) — a KNOWN-FALSE assertion. Must go RED through `make qa`.
# If THIS cannot fail, the harness cannot be trusted (the one rule: a green is worthless unless it
# can go red). Filename is lab_*.py so the normal suite never collects it; run only by explicit path.


def test_known_false_fails():
    assert 1 + 1 == 3, "deliberate failure — proves the QA harness can actually report RED"
