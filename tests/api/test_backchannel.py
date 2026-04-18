"""Tests for backchannel injection in _process_audio_for_client.

Covers:
- After speech starts and silence crosses backchannel_silence_threshold_ms
  (but has not reached end-of-turn), one audio broadcast with
  channel="backchannel" and empty text is sent.
- The 3 s minimum interval prevents a second backchannel immediately after.
- backchannels_enabled=False disables the feature.
"""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

from api import ws_server as mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeWs:
    """Minimal WS stand-in."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, message: str) -> None:
        self.sent.append(message)


_SAMPLE_RATE = 16000
# 1 s of audio at 16 kHz
_BLOCK = _SAMPLE_RATE


def _fresh_listening_state_with_speech() -> dict[str, Any]:
    """Connection state mid-utterance: speech started, now pausing."""
    return {
        "mode": "listening",
        "audio_chunks": [],
        "speech_started": True,
        # 1.3 s of silence (above 1200 ms backchannel threshold)
        "silent_samples": int(1.3 * _SAMPLE_RATE),
        "total_samples": int(2.0 * _SAMPLE_RATE),
        "skip_remaining": 0,
        "follow_up_timer_task": None,
        "pipeline_task": None,
        "current_run_id": None,
        "current_session_id": None,
        "barge_in_speech_started_at": None,
        "barge_in_pending": False,
        "last_backchannel_at": 0.0,
    }


def _silent_chunk(n: int = 512) -> np.ndarray:
    """Float32 chunk below the silence threshold."""
    return np.zeros(n, dtype=np.float32)


@pytest.fixture()
def ws_module() -> Any:
    """Isolate ws_server module state."""
    orig_clients = set(mod._connected_clients)
    orig_state = dict(mod._connection_state)
    orig_bc_enabled = mod._backchannels_enabled
    orig_bc_thresh = mod._backchannel_silence_threshold_ms
    orig_bc_interval = mod._backchannel_min_interval_seconds
    orig_silence = mod._silence_threshold
    orig_silence_dur = mod._silence_duration_ms
    orig_sample_rate = mod._sample_rate
    orig_bc_cache = dict(mod._backchannel_cache)
    orig_barge = mod._barge_in_enabled
    orig_wake = mod._wake_word_detector

    mod._backchannels_enabled = True
    mod._backchannel_silence_threshold_ms = 1200
    mod._backchannel_min_interval_seconds = 3.0
    mod._silence_threshold = 300.0
    mod._silence_duration_ms = 1500
    mod._sample_rate = _SAMPLE_RATE
    mod._barge_in_enabled = False  # keep barge-in out of the way
    mod._wake_word_detector = None

    # Inject a minimal fake backchannel cache (1 de entry).
    fake_mp3 = b"\xff\xfb\x00" * 64  # fake MP3 bytes
    mod._backchannel_cache = {"de": [("mhm", fake_mp3)]}

    mod._connected_clients.clear()
    mod._connection_state.clear()

    yield mod

    mod._backchannels_enabled = orig_bc_enabled
    mod._backchannel_silence_threshold_ms = orig_bc_thresh
    mod._backchannel_min_interval_seconds = orig_bc_interval
    mod._silence_threshold = orig_silence
    mod._silence_duration_ms = orig_silence_dur
    mod._sample_rate = orig_sample_rate
    mod._backchannel_cache = orig_bc_cache
    mod._barge_in_enabled = orig_barge
    mod._wake_word_detector = orig_wake
    mod._connected_clients.clear()
    mod._connection_state.clear()
    mod._connected_clients.update(orig_clients)
    mod._connection_state.update(orig_state)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backchannel_fires_in_long_pause(ws_module: Any) -> None:
    """Silent chunk crossing threshold broadcasts audio with channel=backchannel."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    state = _fresh_listening_state_with_speech()
    ws_module._connection_state[conn_id] = state

    chunk = _silent_chunk()
    await ws_module._process_audio_for_client(ws, chunk)

    # Exactly one audio message with channel=backchannel and empty text.
    audio_msgs = [json.loads(m) for m in ws.sent if json.loads(m)["type"] == "audio"]
    assert len(audio_msgs) == 1
    msg = audio_msgs[0]
    assert msg["channel"] == "backchannel"
    assert msg["text"] == ""
    assert msg["data"]  # base64 non-empty


@pytest.mark.asyncio
async def test_backchannel_interval_suppresses_second_play(ws_module: Any) -> None:
    """A second backchannel fired immediately after the first is suppressed."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    state = _fresh_listening_state_with_speech()
    ws_module._connection_state[conn_id] = state

    # Fire once.
    await ws_module._process_audio_for_client(ws, _silent_chunk())

    # Collect count after first tick.
    audio_before = sum(1 for m in ws.sent if json.loads(m)["type"] == "audio")
    assert audio_before == 1

    # Fire again immediately — interval (3 s) has not elapsed.
    await ws_module._process_audio_for_client(ws, _silent_chunk())

    audio_after = sum(1 for m in ws.sent if json.loads(m)["type"] == "audio")
    assert audio_after == 1  # no second broadcast


@pytest.mark.asyncio
async def test_backchannel_disabled_flag(ws_module: Any) -> None:
    """backchannels_enabled=False prevents any backchannel broadcast."""
    ws_module._backchannels_enabled = False

    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_listening_state_with_speech()

    await ws_module._process_audio_for_client(ws, _silent_chunk())

    audio_msgs = [m for m in ws.sent if json.loads(m)["type"] == "audio"]
    assert len(audio_msgs) == 0


@pytest.mark.asyncio
async def test_backchannel_not_fired_before_speech(ws_module: Any) -> None:
    """Backchannels must only fire after speech has started."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    state = _fresh_listening_state_with_speech()
    # Override: no speech yet
    state["speech_started"] = False
    ws_module._connection_state[conn_id] = state

    await ws_module._process_audio_for_client(ws, _silent_chunk())

    audio_msgs = [m for m in ws.sent if json.loads(m)["type"] == "audio"]
    assert len(audio_msgs) == 0


@pytest.mark.asyncio
async def test_backchannel_empty_cache_no_broadcast(ws_module: Any) -> None:
    """Empty _backchannel_cache must not broadcast anything and must not raise."""
    ws_module._backchannel_cache = {}

    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_listening_state_with_speech()

    # Must not raise even though the cache is completely empty.
    await ws_module._process_audio_for_client(ws, _silent_chunk())

    audio_msgs = [m for m in ws.sent if json.loads(m)["type"] == "audio"]
    assert len(audio_msgs) == 0


@pytest.mark.asyncio
async def test_backchannel_falls_back_to_first_available_language(ws_module: Any) -> None:
    """When the requested language is absent, the implementation falls back to any
    available language pool rather than silently skipping.

    Behavior (from _maybe_play_backchannel):
      1. Try exact language match.
      2. Try "de" key.
      3. Fall back to next(iter(cache.values())) — the first available pool.
    With cache = {"en": [...]}, requesting "de" hits step 3 and returns "en" clips.
    """
    fake_mp3 = b"\xff\xfb\x00" * 64
    ws_module._backchannel_cache = {"en": [("yeah", fake_mp3)]}

    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_listening_state_with_speech()

    # _process_audio_for_client always calls _maybe_play_backchannel with "de".
    # Since "de" is absent but "en" is present, the fallback must fire.
    await ws_module._process_audio_for_client(ws, _silent_chunk())

    audio_msgs = [json.loads(m) for m in ws.sent if json.loads(m)["type"] == "audio"]
    assert len(audio_msgs) == 1
    assert audio_msgs[0]["channel"] == "backchannel"
