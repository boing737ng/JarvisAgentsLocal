"""Orchestrator agent: routes tasks to specialist agents."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from jarvis.agents.base import BaseAgent

logger = logging.getLogger(__name__)

VALID_ROUTES = {"respond", "research", "plan", "code", "recall", "vision", "finalize"}


class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__("orchestrator")

    def route(self, user_message: str, context: str = "") -> Dict[str, Any]:
        """
        Determine what to do next. Returns parsed JSON with keys:
        thinking, next_agent, message, task_context
        """
        content = user_message
        if context:
            content = f"Context from previous steps:\n{context}\n\nUser request: {user_message}"

        raw = self.invoke(content, format="json")

        # Try to extract JSON from response
        try:
            # Strip markdown code fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned).strip()

            # Try parsing the whole response first (fast path)
            parsed = json.loads(cleaned)
            if "next_agent" in parsed:
                return parsed

            # next_agent might be nested — look for it
            json_match = re.search(r'\{[^{}]*"next_agent"[^{}]*\}', cleaned, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            # Broader search with nested objects allowed
            json_match2 = re.search(r'\{.*?"next_agent".*?\}', cleaned, re.DOTALL)
            if json_match2:
                return json.loads(json_match2.group())

            return parsed  # return what we parsed even without next_agent
        except (json.JSONDecodeError, AttributeError):
            # Fallback: try to determine intent from text
            logger.warning("[orchestrator] Could not parse JSON response, falling back.\nRaw: %s", raw[:200])
            route = "respond"
            raw_lower = raw.lower()
            if any(w in raw_lower for w in ["search", "find", "look up", "research"]):
                route = "research"
            elif any(w in raw_lower for w in ["code", "write", "script", "program"]):
                route = "code"
            elif any(w in raw_lower for w in ["remember", "recall", "memory"]):
                route = "recall"

            return {
                "thinking": "",
                "next_agent": route,
                "message": raw,
                "task_context": user_message,
            }
