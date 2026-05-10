"""Visionary agent: image analysis via qwen3-vl:8b."""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from jarvis.core.config import get_agent
from jarvis.core.model_manager import model_manager
from jarvis.core.config import get_settings

logger = logging.getLogger(__name__)


class VisionaryAgent:
    def __init__(self):
        self.agent_name = "visionary"
        self.cfg = get_agent(self.agent_name)

    def analyze_image(self, image_path: str, question: str = "Describe this image in detail.") -> str:
        """Analyze an image file."""
        path = Path(image_path)
        if not path.exists():
            return f"[Error: Image not found: {image_path}]"

        logger.info("[visionary] Analyzing image: %s", image_path)
        model_manager.ensure_only(self.cfg.model, heavy=True)

        # Read and encode image
        image_data = base64.b64encode(path.read_bytes()).decode("utf-8")
        suffix = path.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif"}.get(suffix, "image/jpeg")

        settings = get_settings()
        llm = ChatOllama(
            model=self.cfg.model,
            base_url=settings.ollama_url,
            temperature=self.cfg.temperature,
            keep_alive=self.cfg.keep_alive,
        )

        system_prompt = self.cfg.load_prompt()
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(
            content=[
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}},
            ]
        ))

        try:
            response = llm.invoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            if str(self.cfg.keep_alive) in ("0", "0s"):
                model_manager.mark_unloaded(self.cfg.model)
            return content
        except Exception as e:
            logger.error("[visionary] Failed: %s", e)
            return f"[Error analyzing image: {e}]"
