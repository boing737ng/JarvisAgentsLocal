"""ChromaDB persistent vector store for Jarvis long-term memory."""
from __future__ import annotations

import hashlib
import logging
import time
from typing import List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from jarvis.core.config import get_settings
from jarvis.core.ollama_client import make_embeddings

logger = logging.getLogger(__name__)


class ChromaStore:
    """Persistent ChromaDB store with Ollama embeddings."""

    def __init__(self):
        settings = get_settings()
        chroma_path = settings.chroma_path()
        chroma_path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(chroma_path),
        )
        self._embeddings = make_embeddings(
            model=settings.memory.embedding_model,
        )
        # Cache of collection objects
        self._collections: dict[str, chromadb.Collection] = {}

    def _get_collection(self, namespace: str) -> chromadb.Collection:
        if namespace not in self._collections:
            self._collections[namespace] = self._client.get_or_create_collection(
                name=namespace,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[namespace]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)

    def add(self, text: str, namespace: str = "notes", metadata: dict | None = None) -> str:
        """Add a document to the store. Returns the document ID."""
        collection = self._get_collection(namespace)

        # Generate deterministic ID
        doc_id = hashlib.sha256(f"{namespace}:{time.time()}:{text[:100]}".encode()).hexdigest()[:16]

        embedding = self._embed([text])[0]
        # ChromaDB requires metadata to have at least one key if provided
        safe_metadata = metadata or {}
        safe_metadata["_source"] = "jarvis"  # ensure non-empty

        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[safe_metadata],
        )
        return doc_id

    def query(self, text: str, namespace: str = "notes", k: int = 5) -> List[str]:
        """Query for similar documents. Returns list of document texts."""
        collection = self._get_collection(namespace)

        # Check if collection has documents
        count = collection.count()
        if count == 0:
            return []

        k = min(k, count)
        embedding = self._embed([text])[0]

        results = collection.query(
            query_embeddings=[embedding],
            n_results=k,
        )

        docs = results.get("documents", [[]])[0]
        return docs
