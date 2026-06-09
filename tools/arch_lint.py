"""
Architecture lint (Bible Rule 4 / Adapter discipline).

FAILS (exit 1) if AGT or Gitea is imported anywhere OUTSIDE the adapters/ package. Everything
else must speak THOR vocabulary; only adapters/agt_adapter.py and adapters/gitea_adapter.py may
touch the externals. Run as part of CI as modules land:

    python tools/arch_lint.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Match only REAL import statements of the external modules (anchored at statement start),
# so prose/comments mentioning "AGT" and this file's own regex string are not false positives.
FORBIDDEN = re.compile(r"^\s*(?:import|from)\s+(agt|gitea)\b")
EXEMPT_DIRS = {"adapters", "_reference", ".venv", "tests", "docs"}


def main() -> int:
    violations: list[str] = []
    for py in ROOT.rglob("*.py"):
        rel = py.relative_to(ROOT)
        if rel.parts and rel.parts[0] in EXEMPT_DIRS:
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if FORBIDDEN.search(line):
                violations.append(f"{rel}:{i}: {line.strip()}")
    violations += _strangler_wired()
    if violations:
        print("ARCH-LINT FAIL — adapter discipline (Rule 4 imports + Strangler-wired):")
        print("\n".join(violations))
        return 1
    print("arch-lint OK: no AGT/Gitea imports outside adapters/; audit + identity routed through their ports")
    return 0


def _strangler_wired() -> list[str]:
    """M8 (T10) — beyond import-strings: the audit + identity PORTS must be CONSUMED by a product module
    (the Manager), so a vendor swap is a one-file change. Catches a regression back to decorative adapters
    (the exact H5 failure: ports defined but bypassed by the modules they claim to back)."""
    miss: list[str] = []
    core = (ROOT / "manager" / "core.py").read_text(encoding="utf-8")
    if "ChainAudit" not in core or "self.eventlog = audit or" not in core:
        miss.append("manager/core.py: audit NOT routed through the AuditPort (ChainAudit) — decorative (H5)")
    if "MeshIdentity" not in core or "self.identity.verify_identity" not in core:
        miss.append("manager/core.py: identity NOT routed through the IdentityPort — decorative (H5)")
    return miss


if __name__ == "__main__":
    sys.exit(main())
