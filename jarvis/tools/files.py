"""File tools: read/write/list within workspace directory."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from jarvis.core.config import get_settings

logger = logging.getLogger(__name__)


def _safe_path(relative_path: str) -> Path:
    """Resolve a path relative to workspace, preventing path traversal."""
    workspace = get_settings().workspace_path()
    workspace.mkdir(parents=True, exist_ok=True)
    resolved = (workspace / relative_path).resolve()
    # Security: ensure the resolved path stays within workspace
    if not str(resolved).startswith(str(workspace.resolve())):
        raise ValueError(f"Path traversal attempt blocked: {relative_path}")
    return resolved


def read_file(path: str) -> str:
    """Read a file from workspace."""
    try:
        full_path = _safe_path(path)
        if not full_path.exists():
            return f"[Error: File not found: {path}]"
        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"[Error reading {path}: {e}]"


def write_file(path: str, content: str) -> str:
    """Write content to a file in workspace."""
    try:
        full_path = _safe_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        logger.info("[files] Wrote %d chars to %s", len(content), path)
        return f"[OK: Written to {path}]"
    except Exception as e:
        return f"[Error writing {path}: {e}]"


def list_files(directory: str = ".") -> List[str]:
    """List files in a workspace directory."""
    try:
        full_path = _safe_path(directory)
        if not full_path.exists():
            return []
        return [
            str(p.relative_to(get_settings().workspace_path()))
            for p in sorted(full_path.rglob("*"))
            if p.is_file()
        ]
    except Exception as e:
        logger.warning("[files] List failed for %s: %s", directory, e)
        return []
