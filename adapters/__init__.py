"""
Module 12 — Adapters. The ONLY place external systems (AGT, Gitea) are imported (Rule 4).

Everything else speaks THOR vocabulary; these adapters translate. On day one (Modules 1–11)
both are STUBS (Rule 5): local-git stand-in for Gitea, always-allow+log for the AGT leash.
Real wiring is Module 12. An architecture-lint (tools/arch_lint.py) FAILS the build if AGT or
Gitea is imported anywhere outside this package.
"""
