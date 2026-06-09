"""
Seam S12 — All modules → Manager EventLog (the single ledger).  Gap H6.

Static, fast, NO docker/DB: parses the product packages' ABSTRACT SYNTAX TREE and asserts NO module
writes the ledger directly via an `eventlog.append(...)` call — every governed record must route
through `Manager._record` (the fail-closed gate + projection). The Manager package owns `_record` and
the low-level `EventLogWriter.append`, so it is the sole legitimate writer and is excluded.

BUG-2 hardening: this used to be a string grep for the literal `.eventlog.append(`, which a reworded
bypass defeats (`self.eventlog .append(`, a line break before `.append`, extra spaces inside the
parens, etc.). The AST walk below matches the `eventlog.append(...)` CALL regardless of
whitespace/formatting/line-splitting, so those reword tricks no longer hide a bypass.

Honest scope: the AST catches `<x>.eventlog.append(...)` and a bare `eventlog.append(...)`. It does
NOT chase a value laundered through a local alias (`w = self.eventlog; w.append(...)`) — full alias
tracking is out of scope for a static seam test; that residual is covered by the live single-writer
ACs in `make prove`. This test GATES every run (not deferred).
"""
import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

# Every product package EXCEPT manager (the single writer). tools/ are dev smokes, tests/ are tests.
PRODUCT_PACKAGES = [
    "wall", "leash", "scheduler", "contract", "govengine",
    "sdlc", "sentinel", "selfaudit", "adapters", "mobile", "dashboard",
]


def _receiver_is_eventlog(node: ast.AST) -> bool:
    """True if `node` (the object `.append` is called on) refers to an eventlog: either an attribute
    access `<x>.eventlog` or a bare name `eventlog`."""
    if isinstance(node, ast.Attribute):
        return node.attr == "eventlog"
    if isinstance(node, ast.Name):
        return node.id == "eventlog"
    return False


def _bypass_calls(tree: ast.AST) -> list[int]:
    """Line numbers of any `<eventlog>.append(...)` call in this module."""
    hits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "append"
                and _receiver_is_eventlog(node.func.value)):
            hits.append(node.lineno)
    return hits


def test_seam_S12_no_bypass_writers():
    offenders = []
    for pkg in PRODUCT_PACKAGES:
        for py in (REPO / pkg).rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for line in _bypass_calls(tree):
                offenders.append(f"{py.relative_to(REPO)}:{line}")
    assert offenders == [], (
        "ledger bypass writers found — these must route through Manager._record (H6/S12): "
        + ", ".join(offenders)
    )
