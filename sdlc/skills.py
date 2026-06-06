"""
Sub-module 7.2 — Skill Composer. Resolves the skill model (Bible §10.4):

  FLOOR skills load in EVERY Build and QA stage, always, regardless of task_type (FR-16): security,
  code-review, testing-discipline, error-handling. These are the non-negotiable baseline — so the
  dangerous-to-miss competencies (e.g. security on a login feature) are NEVER absent; the scariest
  skill-selection failure is eliminated by making the critical ones floors.

  SPECIALTY skills are composed per feature from its capability_tags. Getting selection wrong is
  low-cost because the floor always protects the critical cases.

Governed selection (FR-17): tags are proposed at Genesis, ratified by the human in plan approval, and
composed DETERMINISTICALLY here — the agent never picks its own skills (P1).
"""
from __future__ import annotations

from dataclasses import dataclass

# Always-on baseline for Build/QA (FR-16). Sentinel verifies these loaded (loadedness, P9).
FLOOR_SKILLS = ("security", "code-review", "testing-discipline", "error-handling")

# capability_tag -> specialty skill bundle (a swappable registry; Bernstein-style catalog).
SPECIALTY_REGISTRY: dict[str, tuple[str, ...]] = {
    "ui-form": ("ux", "accessibility", "visual-regression"),
    "auth": ("security-deep", "session-mgmt"),
    "high-traffic": ("load-testing", "perf"),
    "ml": ("ml-eval", "data-validation"),
    "api": ("api-design", "api-contract"),
    "database": ("schema-design", "migration-safety"),
    "infra": ("devops", "iac-security"),
}


@dataclass
class SkillBundle:
    task_type: str
    capability_tags: tuple[str, ...]
    floor: tuple[str, ...]
    specialty: tuple[str, ...]

    @property
    def all_skills(self) -> tuple[str, ...]:
        return self.floor + self.specialty


def compose(task_type: str, capability_tags) -> SkillBundle:
    """Deterministically compose a stage's brain: floor (always) + specialty (by ratified tags)."""
    specialty: list[str] = []
    for tag in capability_tags:
        for s in SPECIALTY_REGISTRY.get(tag, ()):
            if s not in specialty:
                specialty.append(s)
    return SkillBundle(task_type=task_type, capability_tags=tuple(capability_tags),
                       floor=FLOOR_SKILLS, specialty=tuple(sorted(specialty)))


def known_tag(tag: str) -> bool:
    return tag in SPECIALTY_REGISTRY
