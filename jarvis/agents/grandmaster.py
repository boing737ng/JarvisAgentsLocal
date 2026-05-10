"""Grandmaster agent: deep analysis via qwen3.5:27b."""
from __future__ import annotations

from jarvis.agents.base import BaseAgent


class GrandmasterAgent(BaseAgent):
    def __init__(self):
        super().__init__("grandmaster")

    def analyze(self, brief: str) -> str:
        """Perform deep analysis on the provided brief."""
        return self.invoke(brief)
