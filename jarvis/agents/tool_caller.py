"""Tool caller agent: structured tool call parsing via llama3.1:8b."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from jarvis.agents.base import BaseAgent


class ToolCallerAgent(BaseAgent):
    def __init__(self):
        super().__init__("tool_caller")

    def parse_tool_call(self, user_request: str) -> Optional[Dict[str, Any]]:
        """Parse a user request into a structured tool call."""
        raw = self.invoke(user_request)
        try:
            # Try direct JSON parse
            return json.loads(raw)
        except json.JSONDecodeError:
            # Look for JSON object in the response
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None
