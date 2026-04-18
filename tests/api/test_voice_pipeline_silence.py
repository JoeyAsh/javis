"""Tests for end-of-utterance silence detection in _process_audio_for_client.

Verifies that the live silence-end-of-turn duration is driven by
``audio.silence_duration_ms`` (stored as ``_silence_duration_ms`` in ws_server),
NOT by ``voice.silence_threshold_ms`` (which is dead config never read in production).

At 1500ms (16000 Hz sample rate) = 24000 samples needed to fire end-of-turn.

Covers:
- A 1.0-second silence gap (16000 samples) after speech starts does NOT trigger
  end-of-turn under the 1500ms config.
- A 1.6-second silence gap (25600 samples) DOES trigger end-of-turn.
- The pipeline task is created when end-of-turn fires.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from api import ws_server as mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeWs:
    """Minimal WS stand-in that records outbound messages."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, message: str) -> None:
        """Record outbound message."""
        self.sent.append(message)


def _speech_chunk(n_samples: int = 512) -> np.ndarray:
    """Float32 chunk with RMS well above _silence_threshold (300 int16 scale → ~0.009 normalised).

    Value 0.5 gives RMS 0.5 * 32768 = 16384 in int16 scale — clearly above 300.
    """
    return np.full(n_samples, 0.5, dtype=np.float32)


def _silent_chunk(n_samples: int = 512) -> np.ndarray:
    """Float32 chunk below silence threshold."""
    return np.zeros(n_samples, dtype=np.float32)


def _fresh_listening_state() -> dict[str, Any]:
    """Connection state in listening mode, speech already started."""
    return {
        "mode": "listening",
        "audio_chunks": [],
        "speech_started": True,  # pre-populate: user has already spoken
        "silent_samples": 0,
        "total_samples": 8000,  # 0.5s of prior speech at 16 kHz
        "skip_remaining": 0,
        "follow_up_timer_task": None,
        "pipeline_task": None,
        "current_run_id": None,
        "current_session_id": None,
        "barge_in_speech_started_at": None,
        "barge_in_pending": False,
        "barge_in_grace_until": 0.0,
        "barge_in_last_rms_log_at": 0.0,
        "last_backchannel_at": 0.0,
    }


@pytest.fixture()
def ws_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Isolate ws_server module globals for silence-detection tests."""
    orig_clients = set(mod._connected_clients)
    orig_state = dict(mod._connection_state)
    orig_silence_threshold = mod._silence_threshold
    orig_silence_duration_ms = mod._silence_duration_ms
    orig_sample_rate = mod._sample_rate
    orig_barge_enabled = mod._barge_in_enabled
    orig_backchannels = mod._backchannels_enabled
    orig_openclaw = mod._openclaw_client
    orig_wake = mod._wake_word_detector
    orig_conv_mode = mod._conversation_mode

    # Pin to deterministic values matching the 1500ms production config.
    mod._silence_threshold = 300.0  # int16-scale RMS threshold
    mod._silence_duration_ms = 1500  # 1500ms = 24000 samples at 16kHz
    mod._sample_rate = 16000
    mod._barge_in_enabled = False  # disable barge-in to isolate silence branch
    mod._backchannels_enabled = False  # disable backchannels for simplicity
    mod._wake_word_detector = None
    mod._conversation_mode = None

    fake_oc = MagicMock()
    fake_oc.abort_current_run = AsyncMock()
    mod._openclaw_client = fake_oc

    mod._connected_clients.clear()
    mod._connection_state.clear()

    yield mod

    mod._silence_threshold = orig_silence_threshold
    mod._silence_duration_ms = orig_silence_duration_ms
    mod._sample_rate = orig_sample_rate
    mod._barge_in_enabled = orig_barge_enabled
    mod._backchannels_enabled = orig_backchannels
    mod._openclaw_client = orig_openclaw
    mod._wake_word_detector = orig_wake
    mod._conversation_mode = orig_conv_mode
    mod._connected_clients.clear()
    mod._connection_state.clear()
    mod._connected_clients.update(orig_clients)
    mod._connection_state.update(orig_state)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_1s_silence_does_not_trigger_end_of_turn(ws_module: Any) -> None:
    """A 1.0-second silence (16000 samples) does NOT fire end-of-turn at 1500ms threshold."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_listening_state()
    state = ws_module._connection_state[conn_id]

    # Feed 1.0s worth of silence in 512-sample chunks.
    # 16000 samples / 512 = 31.25 → 31 full chunks = 15872 samples (~0.99s).
    silence_samples_1s = 16000
    chunks_to_feed = silence_samples_1s // 512  # 31 chunks

    pipeline_created = False

    async def _fake_pipeline(*_a: Any, **_kw: Any) -> None:
        nonlocal pipeline_created
        pipeline_created = True

    with patch("api.ws_server._run_voice_pipeline", _fake_pipeline):
        for _ in range(chunks_to_feed):
            state["silent_samples"] += 512  # manually accumulate (no real chunk processing)

        # Verify silence is below 24000 sample threshold.
        assert state["silent_samples"] < 24000, (
            f"Expected < 24000 silent samples, got {state['silent_samples']}"
        )

        # Feed one chunk via the real handler to confirm it doesn't fire.
        state["silent_samples"] = 15872  # ~0.99s, below 24000
        chunk = _silent_chunk()
        await ws_module._process_audio_for_client(ws, chunk)

    assert not pipeline_created, "Pipeline fired too early on <1s silence"
    assert state["mode"] == "listening"


@pytest.mark.asyncio
async def test_1p6s_silence_triggers_end_of_turn(ws_module: Any) -> None:
    """A 1.6-second silence (25600 samples) fires end-of-turn at 1500ms threshold."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_listening_state()
    state = ws_module._connection_state[conn_id]

    # Pre-load silent_samples to 25088 (just above 24000 threshold).
    state["silent_samples"] = 25088  # > 24000 = 1500ms * 16000 / 1000

    pipeline_created = False
    captured_chunks: list[Any] = []

    async def _fake_pipeline(chunks: list[Any], _ws: Any) -> None:
        nonlocal pipeline_created
        pipeline_created = True
        captured_chunks.extend(chunks)

    with patch("api.ws_server._run_voice_pipeline", _fake_pipeline):
        chunk = _silent_chunk()
        await ws_module._process_audio_for_client(ws, chunk)
        # Allow the asyncio task to start.
        await asyncio.sleep(0)

    assert pipeline_created, "Pipeline did not fire after 1.6s silence"


@pytest.mark.asyncio
async def test_silence_duration_ms_is_the_live_knob(ws_module: Any) -> None:
    """Confirm _silence_duration_ms (audio.silence_duration_ms) governs end-of-turn.

    voice.silence_threshold_ms is dead config. The production code path at
    ws_server.py line ~1016 reads: silence_samples = int(_silence_duration_ms * _sample_rate / 1000).
    This test verifies that changing _silence_duration_ms changes the threshold.
    """
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_listening_state()
    state = ws_module._connection_state[conn_id]

    # Override to 2000ms → threshold = 32000 samples.
    ws_module._silence_duration_ms = 2000
    # 25600 samples (~1.6s) should NOT fire under a 2000ms threshold.
    state["silent_samples"] = 25600

    pipeline_created = False

    async def _fake_pipeline(*_a: Any, **_kw: Any) -> None:
        nonlocal pipeline_created
        pipeline_created = True

    with patch("api.ws_server._run_voice_pipeline", _fake_pipeline):
        chunk = _silent_chunk()
        await ws_module._process_audio_for_client(ws, chunk)
        await asyncio.sleep(0)

    assert not pipeline_created, (
        "Pipeline should not fire at 1.6s silence when threshold is 2000ms"
    )
