"""
THOR Module 7 — the SDLC Stages (Genesis / Project Checker / Build / QA).

Turns THOR from a "room system" into a governed software lifecycle: typed stage-containers, each with
its own brain + skills + mandate, moving a feature through Genesis → Build → QA → Verdict with a human
signature at each gate. LangGraph-shaped: nodes = stage-containers (Wall), edges = governed transitions,
state = the feature. Stages run inside the Wall (M1) under the Leash (M2), briefed via the Contract (M5),
coordinated by the Manager (M3), scheduled by the Scheduler (M4), and judged by the Engine (M6).

Files → PRD §2 sub-modules:
    skills.py      7.2 Skill Composer (floor + specialty; tag-driven; deterministic)
    anatomy.py     7.1 Stage Anatomy Framework (Input → Brain+Skills → Mandate → Edge-check → Output)
    stages.py      7.3 Genesis · 7.4 Project Checker · 7.5 Build · 7.6 QA
    transitions.py 7.7 Stage Transition Controller (SDLC order + the three signature gates)
    bridge.py      7.8 Findings & Ticket Bridge (bugs → DB; QA-fail → card → Signature 2 → ticket)
"""
