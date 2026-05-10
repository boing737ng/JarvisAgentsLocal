"""Web fetch + distillation tool.
Fetches a URL, extracts clean text via trafilatura,
then uses the parser agent (qwen2.5:0.5b) to summarize if text is long.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx
import trafilatura

logger = logging.getLogger(__name__)

MAX_RAW_CHARS = 2000  # If content exceeds this, pass through parser agent


def fetch_raw(url: str, timeout: float = 15.0) -> Optional[str]:
    """Fetch URL and extract clean text using trafilatura."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        text = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        )
        return text
    except Exception as e:
        logger.warning("[web_fetch] Failed to fetch %s: %s", url, e)
        return None


def fetch_and_distill(url: str, topic: str = "") -> str:
    """
    Fetch a URL and return distilled content.
    If raw text is long, uses the parser agent to summarize it.
    """
    raw = fetch_raw(url)
    if not raw:
        return f"[Failed to fetch: {url}]"

    if len(raw) <= MAX_RAW_CHARS:
        return raw

    # Pass through parser agent for distillation
    try:
        from jarvis.agents.parser import ParserAgent
        agent = ParserAgent()
        summary = agent.summarize(raw, topic=topic)
        return summary
    except Exception as e:
        logger.warning("[web_fetch] Parser agent failed, truncating: %s", e)
        return raw[:MAX_RAW_CHARS] + "\n... [truncated]"
