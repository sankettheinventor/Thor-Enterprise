"""
THOR Module 8 — the PM Surface (kanban, approval cards, audit, signatures).

The cockpit the accountable human sits in: Direct (kanban) → Watch (live rooms/cost, read-only) →
Decide (the three signature points) → Audit (event feed + export), plus legible refusal in plain
language. It is a WINDOW, NOT A BRAIN (FR-8): it reads projections from the Manager (M3) and writes
back only direction + signatures; it holds no competing truth and shows "disconnected" rather than
stale-as-live (FR-16).

Files → PRD §2 sub-modules:
    legible.py       8.6 Legible Refusal Renderer (reason-code → plain language)
    kanban.py        8.1 Kanban projection (features → stage columns)
    cost.py          8.7 Cost & Budget Panel
    audit.py         8.5 Audit Feed & Log (+ CSV/JSON export)
    service.py       8.9 DashboardAPI Client logic + 8.2/8.3/8.4/8.8 (the read-and-sign service)
    dashboard_api.py the DashboardAPI (:7080) FastAPI wrapper over the service
    cockpit.html     a minimal static cockpit (evolves ceo.html); the full React UI is deferred

Bootstrap note (flagged Rule 9): the substantive build is the Python DashboardAPI + logic (testable);
the React presentation layer per PRD §4 is deferred — this env has no Node and a SPA isn't smoke-testable.
"""
