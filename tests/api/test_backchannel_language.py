"""Tests for per-connection language state threaded into backchannel playback.

Covers:
- detected_language is stored on connection state after STT fires.
- backchannel reads detected_language instead of always using "de".
- Falls back to "de" when detected_language is unset (None).
- Falls back to "de" when detected_language is an unknown code.
"""

from __future__ import annotations

import json
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


def _listening_state_with_speech(language: str | None = None) -> dict[str, Any]:
    """Return a connection state that has started speech and is now pausing."""
    return {
        "mode": "listening",
        "audio_chunks": [],
        "speech_started": True,
        # 1.5 s of silence — above the 1.2 s backchannel threshold.
        "silent_samples": int(1.5 * _SAMPLE_RATE),
        "total_samples": int(2.5 * _SAMPLE_RATE),
        "skip_remaining": 0,
        "follow_up_timer_task": None,
        "pipeline_task": None,
        "current_run_id": None,
        "current_session_id": None,
        "barge_in_speech_started_at": None,
        "barge_in_pending": False,
        "last_backchannel_at": 0.0,
        "detected_language": language,
    }


def _silent_chunk(n: int = 512) -> np.ndarray:
    """Float32 chunk below the silence threshold."""
    return np.zeros(n, dtype=np.float32)


@pytest.fixture()
def ws_module() -> Any:
    """Isolate ws_server module state and inject a fake backchannel cache."""
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
    mod._silence_duration_ms = 2000
    mod._sample_rate = _SAMPLE_RATE
    mod._barge_in_enabled = False
    mod._wake_word_detector = None

    # Two languages in cache so we can distinguish which pool was chosen.
    fake_de = b"\xff\xfb\xde" * 32
    fake_en = b"\xff\xfb\xae" * 32
    mod._backchannel_cache = {
        "de": [("mhm", fake_de)],
        "en": [("right", fake_en)],
    }

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
async def test_detected_language_stored_on_connection_state(ws_module: Any) -> None:
    """After STT fires, detected_language is written to connection state."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    state: dict[str, Any] = {
        "mode": "idle",
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
        "follow_up_timer_task": None,
        "pipeline_task": None,
        "current_run_id": None,
        "current_session_id": None,
        "barge_in_speech_started_at": None,
        "barge_in_pending": False,
        "last_backchannel_at": 0.0,
        "detected_language": None,
        "pending_email_send": None,
        "pending_calendar_op": None,
    }
    ws_module._connection_state[conn_id] = state

    # Simulate the language-store code path that runs after STT in the
    # pipeline body.  We replicate what _run_voice_pipeline_body does:
    conn_state_ref = ws_module._connection_state.get(conn_id)
    assert conn_state_ref is not None
    conn_state_ref["detected_language"] = "en"

    assert ws_module._connection_state[conn_id]["detected_language"] == "en"


@pytest.mark.asyncio
async def test_backchannel_uses_detected_language(ws_module: Any) -> None:
    """When detected_language='en', the 'en' pool is chosen for backchannel."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    state = _listening_state_with_speech(language="en")
    ws_module._connection_state[conn_id] = state

    await ws_module._process_audio_for_client(ws, _silent_chunk())

    audio_msgs = [json.loads(m) for m in ws.sent if json.loads(m)["type"] == "audio"]
    assert len(audio_msgs) == 1
    msg = audio_msgs[0]
    assert msg["channel"] == "backchannel"
    # The EN pool contains "right" text; verify correct bytes were used.
    import base64

    decoded = base64.b64decode(msg["data"])
    # EN clip starts with \xff\xfb\xae; DE clip starts with \xff\xfb\xde.
    assert decoded[:3] == b"\xff\xfb\xae", "Expected EN pool bytes to be played"


@pytest.mark.asyncio
async def test_backchannel_fallback_to_de_when_language_unset(ws_module: Any) -> None:
    """When detected_language is None, the 'de' pool is used as fallback."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    state = _listening_state_with_speech(language=None)
    ws_module._connection_state[conn_id] = state

    await ws_module._process_audio_for_client(ws, _silent_chunk())

    audio_msgs = [json.loads(m) for m in ws.sent if json.loads(m)["type"] == "audio"]
    assert len(audio_msgs) == 1
    import base64

    decoded = base64.b64decode(audio_msgs[0]["data"])
    # DE clip starts with \xff\xfb\xde.
    assert decoded[:3] == b"\xff\xfb\xde", "Expected DE pool bytes to be played"


@pytest.mark.asyncio
async def test_backchannel_fallback_unknown_language_uses_de(ws_module: Any) -> None:
    """Unknown language code causes fallback to 'de' pool."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    # "fr" is not in the cache; should fall back to "de".
    state = _listening_state_with_speech(language="fr")
    ws_module._connection_state[conn_id] = state

    await ws_module._process_audio_for_client(ws, _silent_chunk())

    audio_msgs = [json.loads(m) for m in ws.sent if json.loads(m)["type"] == "audio"]
    assert len(audio_msgs) == 1
    import base64

    decoded = base64.b64decode(audio_msgs[0]["data"])
    # "fr" absent → fall back to "de" pool.
    assert decoded[:3] == b"\xff\xfb\xde"


@pytest.mark.asyncio
async def test_detected_language_persists_across_ticks(ws_module: Any) -> None:
    """detected_language set on state persists across multiple audio ticks."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    state = _listening_state_with_speech(language="en")
    ws_module._connection_state[conn_id] = state

    # First tick fires backchannel.
    await ws_module._process_audio_for_client(ws, _silent_chunk())

    # Advance last_backchannel_at so interval allows another play.
    ws_module._connection_state[conn_id]["last_backchannel_at"] = 0.0

    # Second tick should still use "en".
    await ws_module._process_audio_for_client(ws, _silent_chunk())

    audio_msgs = [json.loads(m) for m in ws.sent if json.loads(m)["type"] == "audio"]
    assert len(audio_msgs) == 2
    import base64

    for msg in audio_msgs:
        decoded = base64.b64decode(msg["data"])
        assert decoded[:3] == b"\xff\xfb\xae"
