"""Memory tool: high-level API wrapping ChromaDB store."""
from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

NAMESPACES = ("notes", "web", "code_snippets", "conversations")


class MemoryStore:
    """High-level memory interface backed by ChromaDB."""

    def __init__(self):
        from jarvis.memory.chroma_store import ChromaStore
        self._store = ChromaStore()

    def add(
        self,
        text: str,
        namespace: str = "notes",
        metadata: Optional[dict] = None,
    ) -> str:
        """Add text to memory in given namespace."""
        if namespace not in NAMESPACES:
            namespace = "notes"
        try:
            doc_id = self._store.add(text, namespace=namespace, metadata=metadata or {})
            logger.info("[memory] Stored %d chars in namespace '%s'", len(text), namespace)
            return doc_id
        except Exception as e:
            logger.error("[memory] Failed to add: %s", e)
            return ""

    def query(
        self,
        text: str,
        namespace: str = "notes",
        k: int = 5,
    ) -> List[str]:
        """Query memory for similar content."""
        try:
            results = self._store.query(text, namespace=namespace, k=k)
            logger.info("[memory] Found %d results in '%s'", len(results), namespace)
            return results
        except Exception as e:
            logger.error("[memory] Query failed: %s", e)
            return []

    def query_all_namespaces(self, text: str, k: int = 3) -> List[str]:
        """Query across all namespaces."""
        results = []
        for ns in NAMESPACES:
            results.extend(self.query(text, namespace=ns, k=k))
        return results[:k * 2]


# Singleton instance
_memory_store: MemoryStore | None = None


def get_memory() -> MemoryStore:
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
