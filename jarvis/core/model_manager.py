"""Model Manager — singleton that enforces single-model-in-RAM policy."""
from __future__ import annotations

import logging
import threading
from typing import Optional

import httpx

from jarvis.core.config import get_settings

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Singleton that tracks which model is currently loaded in Ollama.
    Before loading a new heavy model, it forcibly unloads the previous one
    by sending keep_alive=0 to the Ollama API.
    """

    _instance: Optional["ModelManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "ModelManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._current_model: Optional[str] = None
                    cls._instance._model_lock = threading.Lock()
        return cls._instance

    @property
    def current_model(self) -> Optional[str]:
        return self._current_model

    def unload(self, model: str) -> bool:
        """Forcibly unload a model from Ollama memory."""
        settings = get_settings()
        url = f"{settings.ollama_url}/api/generate"
        try:
            resp = httpx.post(
                url,
                json={"model": model, "keep_alive": 0, "prompt": ""},
                timeout=15.0,
            )
            resp.raise_for_status()
            logger.info("[model_manager] Unloaded: %s", model)
            return True
        except Exception as e:
            logger.warning("[model_manager] Failed to unload %s: %s", model, e)
            return False

    def unload_all(self) -> None:
        """Unload all currently loaded models (queries /api/ps)."""
        settings = get_settings()
        try:
            resp = httpx.get(f"{settings.ollama_url}/api/ps", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            for m in models:
                self.unload(m)
            with self._model_lock:
                self._current_model = None
        except Exception as e:
            logger.warning("[model_manager] Failed to list running models: %s", e)

    def ensure_only(self, target_model: str, heavy: bool = False) -> None:
        """
        Ensure only `target_model` is in RAM.
        If `heavy=True`, unload any other model first.
        For lightweight models (orchestrator, parser) called often,
        set heavy=False to avoid constant churn.
        """
        with self._model_lock:
            if heavy and self._current_model and self._current_model != target_model:
                logger.info(
                    "[model_manager] Evicting %s before loading %s",
                    self._current_model,
                    target_model,
                )
                self.unload(self._current_model)
            self._current_model = target_model

    def mark_unloaded(self, model: str) -> None:
        """Call this after keep_alive=0 response to update tracking."""
        with self._model_lock:
            if self._current_model == model:
                self._current_model = None

    def list_running(self) -> list[dict]:
        """Query Ollama for currently loaded models."""
        settings = get_settings()
        try:
            resp = httpx.get(f"{settings.ollama_url}/api/ps", timeout=10.0)
            resp.raise_for_status()
            return resp.json().get("models", [])
        except Exception as e:
            logger.warning("[model_manager] Cannot list running models: %s", e)
            return []


# Global singleton instance
model_manager = ModelManager()
