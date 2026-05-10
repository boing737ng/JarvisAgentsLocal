"""Factory for ChatOllama instances with memory management."""
from __future__ import annotations

import logging
from typing import Optional

from langchain_ollama import ChatOllama, OllamaEmbeddings

from jarvis.core.config import AgentConfig, get_settings

logger = logging.getLogger(__name__)


def make_llm(agent_cfg: AgentConfig, format: Optional[str] = None) -> ChatOllama:
    """Create a ChatOllama instance from agent config."""
    settings = get_settings()
    kwargs = dict(
        model=agent_cfg.model,
        base_url=settings.ollama_url,
        temperature=agent_cfg.temperature,
        keep_alive=agent_cfg.keep_alive,
    )
    if format:
        kwargs["format"] = format
    return ChatOllama(**kwargs)


def make_embeddings(model: Optional[str] = None, keep_alive: Optional[str] = None) -> OllamaEmbeddings:
    """Create OllamaEmbeddings instance."""
    settings = get_settings()
    return OllamaEmbeddings(
        model=model or settings.memory.embedding_model,
        base_url=settings.ollama_url,
        # keep_alive not directly supported in OllamaEmbeddings constructor
        # but we handle it via model_manager
    )
