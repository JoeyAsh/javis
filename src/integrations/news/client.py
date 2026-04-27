"""RSS news adapter for JARVIS.

Uses ``aiohttp`` for HTTP and stdlib ``xml.etree.ElementTree`` for RSS parsing.
No new dependencies required.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import aiohttp

from utils.logger import get_logger

logger = get_logger("news_client")


class NewsClient:
    """Async RSS news adapter backed by ``aiohttp`` and stdlib XML.

    No API key or additional dependencies required.
    """

    async def fetch_top_headlines(
        self,
        source_url: str,
        max_items: int = 3,
    ) -> list[dict[str, Any]] | None:
        """Fetch top headlines from an RSS feed URL.

        Args:
            source_url: Full URL of the RSS feed (e.g. SRF news RSS endpoint).
            max_items: Maximum number of items to return.

        Returns:
            List of dicts with keys ``title``, ``url``, ``publishedAt``
            (ISO string or ``None``); or ``None`` on error.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    source_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={"User-Agent": "JARVIS/1.0 (RSS reader)"},
                ) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"RSS feed returned HTTP {resp.status}: {source_url}"
                        )
                        return None
                    raw_xml = await resp.text()
        except aiohttp.ClientError as exc:
            logger.warning(f"RSS fetch failed ({source_url}): {exc}")
            return None
        except Exception as exc:
            logger.warning(f"Unexpected error fetching RSS ({source_url}): {exc}")
            return None

        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError as exc:
            logger.warning(f"Failed to parse RSS XML ({source_url}): {exc}")
            return None

        # Support both RSS 2.0 (channel/item) and Atom (entry).
        items: list[dict[str, Any]] = []
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # Try RSS 2.0 first.
        channel = root.find("channel")
        if channel is not None:
            for item in channel.findall("item"):
                title_el = item.find("title")
                link_el = item.find("link")
                pub_el = item.find("pubDate")

                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                url = link_el.text.strip() if link_el is not None and link_el.text else None
                pub_date: str | None = None
                if pub_el is not None and pub_el.text:
                    pub_date = _rss_date_to_iso(pub_el.text.strip())

                if title:
                    items.append({"title": title, "url": url, "publishedAt": pub_date})
                if len(items) >= max_items:
                    break
        else:
            # Try Atom.
            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                link_el = entry.find("atom:link", ns)
                updated_el = entry.find("atom:updated", ns)

                title = (
                    title_el.text.strip()
                    if title_el is not None and title_el.text
                    else ""
                )
                url = link_el.get("href") if link_el is not None else None
                pub_date = (
                    updated_el.text.strip()
                    if updated_el is not None and updated_el.text
                    else None
                )

                if title:
                    items.append({"title": title, "url": url, "publishedAt": pub_date})
                if len(items) >= max_items:
                    break

        if not items:
            logger.warning(f"No items parsed from RSS feed: {source_url}")
            return None

        return items[:max_items]


def _rss_date_to_iso(rss_date: str) -> str | None:
    """Convert an RFC-2822 RSS pubDate string to ISO-8601, best-effort."""
    from email.utils import parsedate_to_datetime

    try:
        dt = parsedate_to_datetime(rss_date)
        return dt.isoformat()
    except Exception:
        return rss_date  # Return raw string as fallback rather than None.
