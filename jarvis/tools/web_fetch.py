"""Web fetch + distillation tool.
Fetches a URL, extracts clean text via Jina AI (or trafilatura as fallback),
then uses the parser agent (qwen2.5:0.5b) to summarize if text is long.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MAX_RAW_CHARS = 2000  # Если текст длиннее, отдаем парсеру


def fetch_raw(url: str, timeout: float = 30.0) -> Optional[str]:
    """Fetch URL and extract clean text using Jina AI (bypasses bot protection)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # 1. Попытка через Jina (возвращает готовый Markdown текст, обходит защиты)
    try:
        jina_url = f"https://r.jina.ai/{url}"
        response = httpx.get(
            jina_url, headers=headers, timeout=timeout, follow_redirects=True
        )
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.warning(
            "[web_fetch] Jina AI failed for %s: %s. Trying direct fetch...", url, e
        )

    # 2. Фолбэк на прямой запрос + trafilatura (если Jina недоступна)
    try:
        response = httpx.get(
            url, headers=headers, timeout=timeout, follow_redirects=True
        )
        response.raise_for_status()
        import trafilatura

        text = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        )
        return text
    except Exception as e:
        logger.error("[web_fetch] Direct fetch also failed for %s: %s", url, e)
        return None


def fetch_and_distill(url: str, topic: str = "") -> str:
    """Fetch a URL and return distilled content."""
    raw = fetch_raw(url)
    if not raw:
        return f"[Failed to fetch: {url}]"

    if len(raw) <= MAX_RAW_CHARS:
        return raw

    try:
        from jarvis.agents.parser import ParserAgent

        agent = ParserAgent()
        summary = agent.summarize(raw, topic=topic)
        return summary
    except Exception as e:
        logger.warning("[web_fetch] Parser agent failed, truncating: %s", e)
        return raw[:MAX_RAW_CHARS] + "\n... [truncated]"
