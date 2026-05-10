"""Web search tool using DuckDuckGo (no API key required)."""

from __future__ import annotations

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def search(query: str, k: int = 5) -> List[Dict[str, str]]:
    """
    Search the web using DuckDuckGo.
    Returns list of dicts: [{title, url, snippet}, ...]
    """
    try:
        # ИСПРАВЛЕН ИМПОРТ: правильное название библиотеки
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            # max_results ограничивает выдачу
            for r in ddgs.text(query, max_results=k):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    }
                )
        logger.info("[web_search] Found %d results for: %s", len(results), query)
        return results
    except ImportError:
        logger.error("[web_search] Library missing. Run: pip install duckduckgo-search")
        return []
    except Exception as e:
        logger.error("[web_search] Search failed: %s", e)
        return
