"""
THOR Module 5 — the Task Handoff Contract (the frozen six-message interface).

The narrow, frozen seam between the Manager (control plane) and rooms (execution plane). EXACTLY
six messages cross it; nothing else. The feature-slice (`/task/feature.json`) is the room's only
task source — one feature, read-only. Enforces Kind-C isolation (FR-4) and P5 (a room can knock
via `claim_done` but the protocol has NO field to self-certify — only the Manager's `result_decision`
is "done").

Files → PRD §2 sub-modules:
    messages.py    5.1 Message Schema + 5.5 Validator (Pydantic; the six messages; directions; version)
    slice_builder.py 5.2 Feature-Slice Builder (one feature, whitelisted fields, no catalog leak)
    transport.py   5.4 Transport Adapter — DockerExec (v1) + InProcess/REST (v1.1); same messages
    seam.py        5.3 Slice Mounter + 5.6 Claim Handler + 5.7 Amend Handler + idempotency + events
"""
