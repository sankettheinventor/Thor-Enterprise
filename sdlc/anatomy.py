"""
Sub-module 7.1 — Stage Anatomy Framework. The shared 5-part skeleton EVERY stage implements
(FR-1): Input → Brain+Skills → Mandate → Edge-check → Output. This uniformity is the source of
extensibility (FR-14): a new stage type is just the anatomy + a skill set + transition edges, and
NO existing stage changes (AC-9). One skeleton, not four bespoke designs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .skills import SkillBundle, compose


class Stage(ABC):
    """Base for every stage (Genesis, Checker, Build, QA, and any future stage)."""

    #: stage type name; also the Wall task_type for Build/QA/Checker/Genesis
    name: str = "stage"

    def __init__(self, task_type: str | None = None, capability_tags=()) -> None:
        self.task_type = task_type or self.name
        self.capability_tags = tuple(capability_tags)
        self.brain: SkillBundle | None = None

    # 2. Brain + Skills — composed from floor + specialty (the Skill Composer)
    def compose_brain(self) -> SkillBundle:
        self.brain = compose(self.task_type, self.capability_tags)
        return self.brain

    # 3. Mandate — the one job (documented per stage)
    @abstractmethod
    def mandate(self) -> str: ...

    # 4. Edge-check — what THOR verifies before work leaves this stage
    @abstractmethod
    def edge_check(self, output: dict) -> tuple[bool, str]: ...

    # the orchestration: input -> brain -> run -> edge-check -> output
    @abstractmethod
    def run(self, **inputs) -> dict: ...

    def execute(self, **inputs) -> dict:
        """Run the stage through the full anatomy; returns its output (with edge-check result)."""
        self.compose_brain()
        out = self.run(**inputs)
        ok, why = self.edge_check(out)
        out["_edge_ok"] = ok
        out["_edge_reason"] = why
        out["_skills"] = list(self.brain.all_skills)
        return out
