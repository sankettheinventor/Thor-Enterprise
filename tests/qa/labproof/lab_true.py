# Lab-trust proof (Phase 0, step 4) — a KNOWN-TRUE assertion. Must go GREEN through `make qa`.
# Filename is lab_*.py (NOT test_*.py) so the normal suite never auto-collects it; it is run only
# by explicit path during the deliberate harness red/green demonstration.


def test_known_true_passes():
    assert 1 + 1 == 2
