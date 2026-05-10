"""Parser agent: summarizes raw web content using qwen2.5:0.5b."""
from __future__ import annotations

from jarvis.agents.base import BaseAgent


class ParserAgent(BaseAgent):
    def __init__(self):
        super().__init__("parser")

    def summarize(self, raw_text: str, topic: str = "") -> str:
        """Distill raw text into bullet-point facts."""
        if topic:
            prompt = f"Topic: {topic}\n\nText to summarize:\n{raw_text[:8000]}"
        else:
            prompt = f"Summarize the key facts from this text:\n{raw_text[:8000]}"
        return self.invoke(prompt)
