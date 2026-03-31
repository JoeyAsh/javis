"""Web search functionality for JARVIS.

Uses DuckDuckGo Instant Answer API for quick lookups.
"""

import asyncio
from typing import Any

import httpx

from src.utils.logger import get_logger

logger = get_logger("web_search")

DUCKDUCKGO_API_URL = "https://api.duckduckgo.com/"


async def execute_web_search(query: str) -> str:
    """Execute a web search using DuckDuckGo Instant Answer API.

    Args:
        query: Search query

    Returns:
        Search result text
    """
    if not query:
        return "No search query provided"

    try:
        result = await _search_duckduckgo(query)

        if result:
            logger.debug(f"Search result for '{query}': {result[:100]}...")
            return result
        else:
            return f"No instant answer found for: {query}"

    except httpx.RequestError as e:
        logger.error(f"Search request error: {e}")
        return f"Search failed: connection error"
    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Search failed: {e}"


async def _search_duckduckgo(query: str) -> str:
    """Search using DuckDuckGo Instant Answer API.

    Args:
        query: Search query

    Returns:
        Answer text or empty string
    """
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(DUCKDUCKGO_API_URL, params=params)
        response.raise_for_status()

        data = response.json()

        # Try different response fields
        # AbstractText - main summary
        if data.get("AbstractText"):
            source = data.get("AbstractSource", "")
            text = data["AbstractText"]
            if source:
                return f"{text} (Source: {source})"
            return text

        # Answer - direct answer
        if data.get("Answer"):
            return data["Answer"]

        # Definition - word definitions
        if data.get("Definition"):
            return data["Definition"]

        # RelatedTopics - list of related topics
        related = data.get("RelatedTopics", [])
        if related and isinstance(related, list) and len(related) > 0:
            first = related[0]
            if isinstance(first, dict) and first.get("Text"):
                return first["Text"]

        # Infobox - structured data
        infobox = data.get("Infobox", {})
        if infobox and infobox.get("content"):
            content = infobox["content"]
            if isinstance(content, list) and len(content) > 0:
                parts = []
                for item in content[:3]:  # First 3 items
                    if isinstance(item, dict):
                        label = item.get("label", "")
                        value = item.get("value", "")
                        if label and value:
                            parts.append(f"{label}: {value}")
                if parts:
                    return "; ".join(parts)

        return ""


async def search_with_fallback(
    query: str,
    fallback_knowledge: bool = True,
) -> dict[str, Any]:
    """Search with metadata and fallback option.

    Args:
        query: Search query
        fallback_knowledge: Whether to indicate fallback is available

    Returns:
        Dictionary with result and metadata
    """
    result = await execute_web_search(query)

    has_result = bool(result) and "No instant answer" not in result

    return {
        "query": query,
        "result": result,
        "has_result": has_result,
        "needs_llm_fallback": not has_result and fallback_knowledge,
        "source": "duckduckgo",
    }
