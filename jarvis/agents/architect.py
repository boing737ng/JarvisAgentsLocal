"""Architect agent: deep planning using deepseek-r1:14b."""
from __future__ import annotations

from jarvis.agents.base import BaseAgent


class ArchitectAgent(BaseAgent):
    def __init__(self):
        super().__init__("architect")

    def plan(self, task: str) -> str:
        """Create a detailed algorithmic plan for the given task."""
        return self.invoke(task)
