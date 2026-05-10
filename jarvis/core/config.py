"""Configuration loader: YAML → Pydantic models."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ── Settings model ────────────────────────────────────────────────────────────
class DockerSettings(BaseModel):
    sandbox_image: str = "jarvis-sandbox:latest"
    sandbox_dockerfile: str = "docker/sandbox.Dockerfile"
    mem_limit: str = "1g"
    cpu_quota: int = 50000
    timeout_seconds: int = 30
    workspace_mount: str = "/work"


class MemorySettings(BaseModel):
    max_results: int = 5
    chunk_size: int = 512
    embedding_model: str = "nomic-embed-text-v2-moe"
    embedding_keep_alive: str = "5m"


class GraphSettings(BaseModel):
    max_iterations: int = 10


class Settings(BaseModel):
    ollama_url: str = "http://localhost:11434"
    workspace_dir: str = "workspace"
    chroma_dir: str = "data/chroma"
    log_level: str = "INFO"
    docker: DockerSettings = Field(default_factory=DockerSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    graph: GraphSettings = Field(default_factory=GraphSettings)

    def workspace_path(self) -> Path:
        return PROJECT_ROOT / self.workspace_dir

    def chroma_path(self) -> Path:
        return PROJECT_ROOT / self.chroma_dir


# ── Agent config model ────────────────────────────────────────────────────────
class AgentConfig(BaseModel):
    model: str
    keep_alive: str = "5m"
    temperature: float = 0.3
    prompt_file: str = ""
    tools: list[str] = Field(default_factory=list)

    def load_prompt(self) -> str:
        if not self.prompt_file:
            return ""
        prompt_path = PROJECT_ROOT / "config" / "prompts" / self.prompt_file
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return ""


# ── Loader ────────────────────────────────────────────────────────────────────
_settings: Settings | None = None
_agents: dict[str, AgentConfig] | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        path = PROJECT_ROOT / "config" / "settings.yaml"
        data = _load_yaml(path) if path.exists() else {}
        # Allow env var override for ollama_url
        if "JARVIS_OLLAMA_URL" in os.environ:
            data["ollama_url"] = os.environ["JARVIS_OLLAMA_URL"]
        if "JARVIS_LOG_LEVEL" in os.environ:
            data["log_level"] = os.environ["JARVIS_LOG_LEVEL"]
        _settings = Settings(**data)
    return _settings


def get_agents() -> dict[str, AgentConfig]:
    global _agents
    if _agents is None:
        path = PROJECT_ROOT / "config" / "agents.yaml"
        data = _load_yaml(path) if path.exists() else {}
        _agents = {name: AgentConfig(**cfg) for name, cfg in data.items()}
    return _agents


def get_agent(name: str) -> AgentConfig:
    agents = get_agents()
    if name not in agents:
        raise KeyError(f"Unknown agent: {name!r}. Available: {list(agents)}")
    return agents[name]
