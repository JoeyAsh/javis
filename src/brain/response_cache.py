"""Response caching for JARVIS.

Cache recent intent+params -> response mappings to avoid
redundant LLM calls for identical requests.

Example usage:
    from brain.response_cache import ResponseCache

    cache = ResponseCache(max_size=100, ttl_seconds=60)

    # Check cache before LLM call
    cached = cache.get("time_query", {"format": "12h"})
    if cached:
        return cached

    # After LLM call, cache the response
    cache.set("time_query", {"format": "12h"}, response)
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from typing import Any

from utils.logger import get_logger

logger = get_logger("response_cache")


class ResponseCache:
    """Cache recent intent+params -> response mappings.

    Uses LRU eviction and TTL expiration for cache management.

    Attributes:
        max_size: Maximum cache entries.
        ttl_seconds: Time-to-live for entries.
        hit_count: Number of cache hits.
        miss_count: Number of cache misses.
    """

    def __init__(
        self,
        max_size: int = 100,
        ttl_seconds: int = 60,
    ) -> None:
        """Initialize response cache.

        Args:
            max_size: Maximum number of entries to cache.
            ttl_seconds: Time-to-live for cache entries.
        """
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hit_count = 0
        self._miss_count = 0

    @property
    def max_size(self) -> int:
        """Return maximum cache size."""
        return self._max_size

    @property
    def ttl_seconds(self) -> int:
        """Return TTL in seconds."""
        return self._ttl

    @property
    def hit_count(self) -> int:
        """Return cache hit count."""
        return self._hit_count

    @property
    def miss_count(self) -> int:
        """Return cache miss count."""
        return self._miss_count

    @property
    def hit_rate(self) -> float:
        """Return cache hit rate (0-1)."""
        total = self._hit_count + self._miss_count
        if total == 0:
            return 0.0
        return self._hit_count / total

    @property
    def size(self) -> int:
        """Return current cache size."""
        return len(self._cache)

    def _make_key(self, intent: str, params: dict[str, Any]) -> str:
        """Create cache key from intent and params.

        Args:
            intent: Intent identifier.
            params: Intent parameters.

        Returns:
            Hash-based cache key.
        """
        # Sort params for consistent ordering
        sorted_items = sorted(params.items())
        content = f"{intent}:{sorted_items}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, intent: str, params: dict[str, Any]) -> str | None:
        """Get cached response if available and fresh.

        Args:
            intent: Intent identifier.
            params: Intent parameters.

        Returns:
            Cached response or None if not found/expired.
        """
        key = self._make_key(intent, params)

        if key not in self._cache:
            self._miss_count += 1
            return None

        response, timestamp = self._cache[key]

        # Check expiration
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            self._miss_count += 1
            logger.debug(f"Cache miss (expired): {intent}")
            return None

        # Move to end (LRU)
        self._cache.move_to_end(key)
        self._hit_count += 1
        logger.debug(f"Cache hit: {intent}")
        return response

    def set(self, intent: str, params: dict[str, Any], response: str) -> None:
        """Cache a response.

        Args:
            intent: Intent identifier.
            params: Intent parameters.
            response: Response to cache.
        """
        key = self._make_key(intent, params)
        self._cache[key] = (response, time.time())

        # Enforce max size (LRU eviction)
        while len(self._cache) > self._max_size:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug(f"Cache evicted: {evicted_key[:8]}...")

        logger.debug(f"Cached response for: {intent}")

    def invalidate(self, intent: str, params: dict[str, Any]) -> bool:
        """Invalidate a specific cache entry.

        Args:
            intent: Intent identifier.
            params: Intent parameters.

        Returns:
            True if entry was removed.
        """
        key = self._make_key(intent, params)
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared.
        """
        count = len(self._cache)
        self._cache.clear()
        self._hit_count = 0
        self._miss_count = 0
        logger.info(f"Cache cleared: {count} entries")
        return count

    def cleanup_expired(self) -> int:
        """Remove expired entries.

        Returns:
            Number of entries removed.
        """
        now = time.time()
        expired = [
            key for key, (_, timestamp) in self._cache.items()
            if now - timestamp > self._ttl
        ]

        for key in expired:
            del self._cache[key]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired entries")

        return len(expired)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": self.hit_rate,
            "ttl_seconds": self._ttl,
        }
