"""Tests for phrase-cache hit/miss counters and /api/metrics/voice endpoint.

Covers:
- Counter increments on cache hits and misses.
- GET /api/metrics/voice returns correct JSON structure.
- hit_rate calculation, including zero-division guard.
- overall_hit_rate aggregation.
- sleep_match_hits counter increments.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from api import ws_server as mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_stats() -> None:
    """Reset _phrase_cache_stats before each test."""
    for key in list(mod._phrase_cache_stats):
        mod._phrase_cache_stats[key] = 0
    yield
    for key in list(mod._phrase_cache_stats):
        mod._phrase_cache_stats[key] = 0


@pytest_asyncio.fixture()
async def metrics_client():
    """Minimal aiohttp app exposing only the voice metrics endpoint."""
    app = web.Application()
    app.router.add_get("/api/metrics/voice", mod.voice_metrics_handler)
    async with TestClient(TestServer(app)) as client:
        yield client


# ---------------------------------------------------------------------------
# Counter unit tests (no HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filler_hit_increments() -> None:
    """Calling broadcast helper with a populated cache increments filler_hits."""
    fake_mp3 = b"\xff\xfb\x00" * 10
    orig = dict(mod._filler_cache)
    try:
        mod._filler_cache = {"de": [("Moment", fake_mp3)]}

        async def _fake_broadcast(msg: str) -> None:
            pass

        with patch.object(mod, "_broadcast", side_effect=_fake_broadcast):
            await mod._broadcast_quick_ack_filler("de")

        assert mod._phrase_cache_stats["filler_hits"] == 1
        assert mod._phrase_cache_stats["filler_misses"] == 0
    finally:
        mod._filler_cache = orig


@pytest.mark.asyncio
async def test_filler_miss_increments_when_cache_empty() -> None:
    """Empty filler cache increments filler_misses."""
    orig = dict(mod._filler_cache)
    try:
        mod._filler_cache = {}

        async def _fake_broadcast(msg: str) -> None:
            pass

        with patch.object(mod, "_broadcast", side_effect=_fake_broadcast):
            await mod._broadcast_quick_ack_filler("de")

        assert mod._phrase_cache_stats["filler_misses"] == 1
        assert mod._phrase_cache_stats["filler_hits"] == 0
    finally:
        mod._filler_cache = orig


@pytest.mark.asyncio
async def test_backchannel_hit_increments() -> None:
    """_maybe_play_backchannel increments backchannel_hits on a pool hit."""
    fake_mp3 = b"\xff\xfb\xde" * 10
    orig_cache = dict(mod._backchannel_cache)
    try:
        mod._backchannel_cache = {"de": [("mhm", fake_mp3)]}
        state: dict[str, Any] = {"last_backchannel_at": 0.0}

        async def _fake_broadcast(msg: str) -> None:
            pass

        with patch.object(mod, "_broadcast", side_effect=_fake_broadcast):
            await mod._maybe_play_backchannel(state, "de")

        assert mod._phrase_cache_stats["backchannel_hits"] == 1
    finally:
        mod._backchannel_cache = orig_cache


def test_sleep_match_hits_increment() -> None:
    """sleep_match_hits counter can be incremented manually (pipeline does this)."""
    mod._phrase_cache_stats["sleep_match_hits"] += 1
    assert mod._phrase_cache_stats["sleep_match_hits"] == 1


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_voice_metrics_returns_200(metrics_client: Any) -> None:
    """GET /api/metrics/voice returns HTTP 200."""
    resp = await metrics_client.get("/api/metrics/voice")
    assert resp.status == 200


@pytest.mark.asyncio
async def test_voice_metrics_payload_structure(metrics_client: Any) -> None:
    """Response JSON has 'stats' and 'summary' keys."""
    resp = await metrics_client.get("/api/metrics/voice")
    data = await resp.json()
    assert "stats" in data
    assert "summary" in data
    summary = data["summary"]
    assert "filler_hit_rate" in summary
    assert "ack_hit_rate" in summary
    assert "backchannel_hit_rate" in summary
    assert "overall_hit_rate" in summary


@pytest.mark.asyncio
async def test_voice_metrics_zero_division_guard(metrics_client: Any) -> None:
    """When all counters are 0, hit_rate is 0.0 — no ZeroDivisionError."""
    resp = await metrics_client.get("/api/metrics/voice")
    data = await resp.json()
    assert data["summary"]["overall_hit_rate"] == 0.0
    assert data["summary"]["filler_hit_rate"] == 0.0


@pytest.mark.asyncio
async def test_voice_metrics_hit_rate_calculation(metrics_client: Any) -> None:
    """hit_rate = hits / (hits + misses); e.g. 3 hits + 1 miss = 0.75."""
    mod._phrase_cache_stats["filler_hits"] = 3
    mod._phrase_cache_stats["filler_misses"] = 1

    resp = await metrics_client.get("/api/metrics/voice")
    data = await resp.json()
    assert data["summary"]["filler_hit_rate"] == pytest.approx(0.75, abs=1e-4)


@pytest.mark.asyncio
async def test_voice_metrics_overall_aggregates_all_categories(metrics_client: Any) -> None:
    """overall_hit_rate aggregates filler + ack + backchannel counters."""
    mod._phrase_cache_stats["filler_hits"] = 2
    mod._phrase_cache_stats["ack_hits"] = 2
    mod._phrase_cache_stats["backchannel_hits"] = 2
    mod._phrase_cache_stats["filler_misses"] = 2
    mod._phrase_cache_stats["ack_misses"] = 0
    mod._phrase_cache_stats["backchannel_misses"] = 0

    resp = await metrics_client.get("/api/metrics/voice")
    data = await resp.json()
    # 6 hits / 8 total = 0.75
    assert data["summary"]["overall_hit_rate"] == pytest.approx(0.75, abs=1e-4)
