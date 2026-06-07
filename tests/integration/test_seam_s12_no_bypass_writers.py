"""
Seam S12 — All modules → Manager EventLog (the single ledger).  Gap H6.

Static, fast, NO docker/DB: scans the product packages and asserts NO module writes the ledger
directly via `.eventlog.append(` — every governed record must route through `Manager._record`
(the fail-closed gate + projection). The Manager package is the sole legitimate writer (it owns
`_record` and the low-level `EventLogWriter.append`), so it is excluded.

This test GATES every run (not deferred): if anyone reintroduces a bypass writer, it goes red here.
"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

# Every product package EXCEPT manager (the single writer). tools/ are dev smokes, tests/ are tests.
PRODUCT_PACKAGES = [
    "wall", "leash", "scheduler", "contract", "govengine",
    "sdlc", "sentinel", "selfaudit", "adapters", "mobile", "dashboard",
]


def test_seam_S12_no_bypass_writers():
    offenders = []
    for pkg in PRODUCT_PACKAGES:
        for py in (REPO / pkg).rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                if ".eventlog.append(" in line:
                    offenders.append(f"{py.relative_to(REPO)}:{i}")
    assert offenders == [], (
        "ledger bypass writers found — these must route through Manager._record (H6/S12): "
        + ", ".join(offenders)
    )
