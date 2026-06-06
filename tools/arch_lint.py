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
    if violations:
        print("ARCH-LINT FAIL — AGT/Gitea imported outside adapters/ (Rule 4):")
        print("\n".join(violations))
        return 1
    print("arch-lint OK: no AGT/Gitea imports outside adapters/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
