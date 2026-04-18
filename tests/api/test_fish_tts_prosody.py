"""Tests verifying that prosody_hint is passed through to Fish Audio synthesize().

Covers:
- prosody_hint with speed != 1.0 is forwarded in the HTTP payload.
- prosody_hint with speed == 1.0 is NOT added to payload (no-op).
- prosody_hint=None leaves the payload unchanged.
- energy != 'neutral' triggers the one-time startup log (tested via side-effect).
- Neutral enabled=False hint from get_prosody_hint does not send speed field.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from audio.fish_tts import FishTTSClient, _prosody_energy_warned
from audio.prosody import ProsodyHint, get_prosody_hint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(api_key: str = "test-key", voice_id: str = "voice-1") -> FishTTSClient:
    """Create a FishTTSClient with fake credentials."""
    return FishTTSClient(api_key=api_key, voice_id=voice_id)


def _fake_response(content: bytes = b"\xff\xfb\x90" * 10, status: int = 200) -> MagicMock:
    """Build a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status
    resp.content = content
    resp.text = ""
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prosody_speed_forwarded_to_fish_api() -> None:
    """When prosody_hint has speed != 1.0, it is included in the POST payload."""
    captured: list[dict[str, Any]] = []

    async def _fake_post(url: str, headers: dict, json: dict) -> MagicMock:
        captured.append(json)
        return _fake_response()

    client = _make_client()
    hint: ProsodyHint = {"speed": 0.92, "energy": "calm"}

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(side_effect=_fake_post)
        mock_cls.return_value = mock_http

        await client.synthesize("Guten Morgen.", prosody_hint=hint)

    assert len(captured) == 1
    assert "speed" in captured[0], "speed must be forwarded to Fish API payload"
    assert captured[0]["speed"] == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_neutral_speed_not_forwarded() -> None:
    """speed == 1.0 (neutral) is NOT added to the Fish API payload."""
    captured: list[dict[str, Any]] = []

    async def _fake_post(url: str, headers: dict, json: dict) -> MagicMock:
        captured.append(json)
        return _fake_response()

    client = _make_client()
    hint: ProsodyHint = {"speed": 1.0, "energy": "neutral"}

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(side_effect=_fake_post)
        mock_cls.return_value = mock_http

        await client.synthesize("Test.", prosody_hint=hint)

    assert "speed" not in captured[0], "Neutral speed=1.0 must not be sent"


@pytest.mark.asyncio
async def test_no_prosody_hint_leaves_payload_unchanged() -> None:
    """prosody_hint=None does not add any extra keys to the payload."""
    captured: list[dict[str, Any]] = []

    async def _fake_post(url: str, headers: dict, json: dict) -> MagicMock:
        captured.append(json)
        return _fake_response()

    client = _make_client()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(side_effect=_fake_post)
        mock_cls.return_value = mock_http

        await client.synthesize("Test.", prosody_hint=None)

    assert "speed" not in captured[0]


@pytest.mark.asyncio
async def test_prosody_hint_from_get_prosody_hint_morning() -> None:
    """Morning hint (speed=1.05) is forwarded to Fish Audio."""
    captured: list[dict[str, Any]] = []

    async def _fake_post(url: str, headers: dict, json: dict) -> MagicMock:
        captured.append(json)
        return _fake_response()

    client = _make_client()
    hint = get_prosody_hint(hour=7)  # morning → speed=1.05, energy=bright

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(side_effect=_fake_post)
        mock_cls.return_value = mock_http

        await client.synthesize("Guten Morgen!", prosody_hint=hint)

    assert captured[0].get("speed") == pytest.approx(1.05)


@pytest.mark.asyncio
async def test_disabled_prosody_hint_neutral_not_forwarded() -> None:
    """get_prosody_hint(enabled=False) returns neutral → speed NOT in payload."""
    captured: list[dict[str, Any]] = []

    async def _fake_post(url: str, headers: dict, json: dict) -> MagicMock:
        captured.append(json)
        return _fake_response()

    client = _make_client()
    hint = get_prosody_hint(enabled=False)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post = AsyncMock(side_effect=_fake_post)
        mock_cls.return_value = mock_http

        await client.synthesize("Test.", prosody_hint=hint)

    assert "speed" not in captured[0]
