"""Coder agent: writes Python code using qwen2.5-coder:7b."""
from __future__ import annotations

import re

from jarvis.agents.base import BaseAgent


class CoderAgent(BaseAgent):
    def __init__(self):
        super().__init__("coder")

    def write_code(self, task: str, plan: str = "") -> str:
        """Write Python code for the given task (optionally using architect's plan)."""
        if plan:
            prompt = f"Implement the following plan as Python code:\n\n{plan}\n\nTask: {task}"
        else:
            prompt = f"Write Python code for: {task}"
        raw = self.invoke(prompt)
        return self._extract_code(raw)

    def fix_code(self, code: str, error: str, task: str = "") -> str:
        """Fix code given an error message."""
        prompt = (
            f"This Python code has an error:\n\n```python\n{code}\n```\n\n"
            f"Error output:\n{error}\n\n"
            f"Fix the code. Return ONLY the corrected Python code."
        )
        if task:
            prompt = f"Original task: {task}\n\n" + prompt
        raw = self.invoke(prompt)
        return self._extract_code(raw)

    @staticmethod
    def _extract_code(text: str) -> str:
        """Extract Python code from markdown code blocks if present."""
        # Try ```python ... ``` blocks first
        pattern = r"```(?:python)?\n?(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return matches[0].strip()
        # Return as-is if no code blocks found
        return text.strip()
