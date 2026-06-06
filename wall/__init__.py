"""
THOR Module 1 — the Wall (Isolation Layer).

The sealed, disposable container where one cook does one task. Dumb about governance;
its only intelligence is structural: enforce isolation, force all traffic through the one
door, make the leash untouchable (PRD §1, Bible Pillar 1 / P4).

Sub-modules (PRD §2):
    1.1 Image Builder      -> image.Dockerfile + provisioner.build_image()
    1.2 Provisioner        -> provisioner.py
    1.3 Network Enforcer   -> network_enforcer.py   (day-one: network_disabled=True; :8001 one-door at M2)
    1.4 Mount Manager      -> mount_manager.py
    1.5 Lifecycle Controller -> lifecycle.py
    1.6 Identity Stamper   -> identity_stamper.py    (Ed25519 local signer stub)

Built UNGOVERNED (P7 / Rule 1): no THOR governance is applied to THOR's own construction.
The gate is stubbed "always approve"; progress is smoke-checked, not formally proven (Rule 2).
"""

__all__ = ["config", "provisioner", "mount_manager", "network_enforcer",
           "identity_stamper", "lifecycle"]
