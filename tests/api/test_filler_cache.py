"""Tests for the quick-ack filler cache loading + broadcast helpers.

Covers:
- ``_load_filler_cache`` parses ``filler_<lang>_<slug>.mp3`` files,
  groups them by language, and skips empty / malformed entries.
- ``_broadcast_quick_ack_filler`` emits a ``{type:"audio",...}`` frame
  with a random cache entry; gracefully no-ops on empty cache.
- The broadcast falls back to German when the requested language has
  no cache entries.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest

from api import ws_server as mod


class _FakeWs:
    """Minimal WS stand-in that records every ``send_str`` payload."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, message: str) -> None:
        self.sent.append(message)


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary voice_cache directory with two fake filler MP3s."""
    de_dir = tmp_path / "voice_cache"
    de_dir.mkdir()
    (de_dir / "filler_de_moment.mp3").write_bytes(b"ID3" + b"\x00" * 200)
    (de_dir / "filler_en_one_second.mp3").write_bytes(b"ID3" + b"\x00" * 180)
    # Empty file — must be skipped.
    (de_dir / "filler_de_bogus.mp3").write_bytes(b"")
    # Malformed filename — must be skipped.
    (de_dir / "filler_bogus.mp3").write_bytes(b"ID3" + b"\x00" * 50)
    # Non-filler file — must be ignored.
    (de_dir / "ack_de_klar.mp3").write_bytes(b"ID3" + b"\x00" * 50)
    return de_dir


class TestLoadFillerCache:
    """Unit tests for :func:`api.ws_server._load_filler_cache`."""

    def test_loads_valid_files(self, tmp_cache_dir: Path) -> None:
        cache = mod._load_filler_cache(tmp_cache_dir)

        assert set(cache.keys()) == {"de", "en"}
        assert len(cache["de"]) == 1
        assert len(cache["en"]) == 1
        de_text, de_bytes = cache["de"][0]
        assert de_text == "Moment"
        assert de_bytes.startswith(b"ID3")

    def test_skips_empty_files(self, tmp_cache_dir: Path) -> None:
        cache = mod._load_filler_cache(tmp_cache_dir)
        # The empty filler_de_bogus.mp3 must not pollute the cache.
        texts = [t for t, _b in cache["de"]]
        assert "Bogus" not in texts

    def test_missing_directory_returns_empty(self, tmp_path: Path) -> None:
        cache = mod._load_filler_cache(tmp_path / "nonexistent")
        assert cache == {}

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        cache = mod._load_filler_cache(empty)
        assert cache == {}

    def test_display_text_capitalised(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "vc"
        cache_dir.mkdir()
        (cache_dir / "filler_en_just_a_moment.mp3").write_bytes(b"ID3" + b"\x00" * 100)
        cache = mod._load_filler_cache(cache_dir)
        assert cache["en"][0][0] == "Just a moment"


class TestBroadcastQuickAckFiller:
    """Integration tests for the filler broadcast helper."""

    @pytest.fixture(autouse=True)
    def _reset(self) -> Any:
        """Reset the module-level filler cache + client set between tests."""
        saved_cache = mod._filler_cache
        saved_clients = set(mod._connected_clients)
        mod._filler_cache = {}
        mod._connected_clients.clear()
        try:
            yield
        finally:
            mod._filler_cache = saved_cache
            mod._connected_clients.clear()
            mod._connected_clients.update(saved_clients)

    @pytest.mark.asyncio
    async def test_broadcast_emits_audio_frame(self) -> None:
        mod._filler_cache = {"de": [("Moment", b"\xff\xfb\x00" * 400)]}
        ws = _FakeWs()
        mod._connected_clients.add(ws)

        await mod._broadcast_quick_ack_filler("de")

        assert ws.sent, "expected an audio frame to be broadcast"
        frame = json.loads(ws.sent[0])
        assert frame["type"] == "audio"
        assert frame["text"] == "Moment"
        # The base64 payload must decode back to the original bytes.
        assert base64.b64decode(frame["data"]) == b"\xff\xfb\x00" * 400

    @pytest.mark.asyncio
    async def test_empty_cache_is_noop(self) -> None:
        mod._filler_cache = {}
        ws = _FakeWs()
        mod._connected_clients.add(ws)

        await mod._broadcast_quick_ack_filler("de")

        assert ws.sent == []

    @pytest.mark.asyncio
    async def test_language_fallback_to_de(self) -> None:
        """Unknown language falls back to the DE pool when present."""
        mod._filler_cache = {"de": [("Moment", b"de-bytes")]}
        ws = _FakeWs()
        mod._connected_clients.add(ws)

        await mod._broadcast_quick_ack_filler("fr")

        assert ws.sent
        frame = json.loads(ws.sent[0])
        assert frame["text"] == "Moment"

    @pytest.mark.asyncio
    async def test_language_fallback_to_any(self) -> None:
        """When DE is also missing, falls back to any available pool."""
        mod._filler_cache = {"en": [("Right", b"en-bytes")]}
        ws = _FakeWs()
        mod._connected_clients.add(ws)

        await mod._broadcast_quick_ack_filler("fr")

        assert ws.sent
        frame = json.loads(ws.sent[0])
        assert frame["text"] == "Right"
