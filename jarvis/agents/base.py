"""Base agent wrapper: load → invoke → unload."""
from __future__ import annotations

import logging
from typing import Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from jarvis.core.config import AgentConfig, get_agent
from jarvis.core.model_manager import model_manager
from jarvis.core.ollama_client import make_llm

logger = logging.getLogger(__name__)

# Heavy models that must be evicted before loading another
HEAVY_MODELS = {
    "deepseek-r1:14b",
    "qwen3.5:27b",
    "qwen3-vl:8b",
}


class BaseAgent:
    """Base class for all Jarvis agents."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.cfg: AgentConfig = get_agent(agent_name)
        self._system_prompt: Optional[str] = None

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = self.cfg.load_prompt()
        return self._system_prompt

    def _is_heavy(self) -> bool:
        return self.cfg.model in HEAVY_MODELS

    def _prepare_messages(self, user_content: str) -> list[BaseMessage]:
        messages = []
        if self.system_prompt:
            messages.append(SystemMessage(content=self.system_prompt))
        messages.append(HumanMessage(content=user_content))
        return messages

    def invoke(self, user_content: str, format: Optional[str] = None, **kwargs) -> str:
        """Invoke the agent and return the response text."""
        logger.info(
            "[%s] Invoking model: %s (keep_alive=%s)",
            self.agent_name,
            self.cfg.model,
            self.cfg.keep_alive,
        )

        # Memory management: evict other heavy model if needed
        model_manager.ensure_only(self.cfg.model, heavy=self._is_heavy())

        llm = make_llm(self.cfg, format=format)
        messages = self._prepare_messages(user_content)

        try:
            response = llm.invoke(messages)
            content = response.content if hasattr(response, "content") else str(response)

            # If keep_alive=0, mark as unloaded
            if str(self.cfg.keep_alive) in ("0", "0s"):
                model_manager.mark_unloaded(self.cfg.model)
                logger.info("[%s] Model unloaded (keep_alive=0): %s", self.agent_name, self.cfg.model)

            return content
        except Exception as e:
            logger.error("[%s] Invocation failed: %s", self.agent_name, e)
            raise
