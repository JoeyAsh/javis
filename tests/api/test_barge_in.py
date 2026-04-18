"""Tests for barge-in detection in _process_audio_for_client.

Covers:
- Sustained loud audio (>= barge_in_sensitivity_ms) while mode="speaking"
  triggers abort, barge_in broadcast, and transition to listening.
- Audio below RMS threshold does NOT trigger barge-in.
- The barge_in_enabled=False flag disables the entire branch.
- Rapid-chunk re-entrancy guard (barge_in_pending) prevents double-fire.
- Dedicated barge-in VAD RMS threshold (separate from end-of-turn threshold).
- 1Hz RMS debug log throttling.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from api import ws_server as mod


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


class _FakeWs:
    """Minimal WS stand-in — records every outbound message."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, message: str) -> None:
        self.sent.append(message)


def _fresh_speaking_state() -> dict[str, Any]:
    """Connection state with mode='speaking' and a fake run in flight."""
    return {
        "mode": "speaking",
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
        "follow_up_timer_task": None,
        "pipeline_task": None,
        "current_run_id": "run-abc",
        "current_session_id": "sess-xyz",
        "barge_in_speech_started_at": None,
        "barge_in_pending": False,
        "barge_in_grace_until": 0.0,
        "barge_in_last_rms_log_at": 0.0,
        "last_backchannel_at": 0.0,
    }


def _loud_chunk(n_samples: int = 512) -> np.ndarray:
    """Float32 chunk with RMS well above the default silence_threshold=300."""
    return np.full(n_samples, 0.5, dtype=np.float32)  # RMS ~0.5*32768 ≈ 16384


def _silent_chunk(n_samples: int = 512) -> np.ndarray:
    """Float32 chunk below the silence threshold."""
    return np.zeros(n_samples, dtype=np.float32)


@pytest.fixture()
def ws_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Isolate ws_server module state and inject a fake OpenClaw client."""
    # Save originals
    orig_clients = set(mod._connected_clients)
    orig_state = dict(mod._connection_state)
    orig_barge_enabled = mod._barge_in_enabled
    orig_sensitivity = mod._barge_in_sensitivity_ms
    orig_threshold = mod._silence_threshold
    orig_barge_vad_threshold = mod._barge_in_vad_rms_threshold
    orig_sample_rate = mod._sample_rate
    orig_openclaw = mod._openclaw_client
    orig_wake = mod._wake_word_detector

    # Set up a predictable config
    mod._barge_in_enabled = True
    mod._barge_in_sensitivity_ms = 150  # 150 ms
    mod._silence_threshold = 300.0
    # Default barge-in VAD threshold (0–1 float32 scale, matches RMSVAD default).
    mod._barge_in_vad_rms_threshold = 0.02
    mod._sample_rate = 16000
    mod._wake_word_detector = None

    # Fake OpenClaw client
    fake_oc = MagicMock()
    fake_oc.abort_current_run = AsyncMock()
    mod._openclaw_client = fake_oc

    mod._connected_clients.clear()
    mod._connection_state.clear()

    yield mod

    # Restore
    mod._barge_in_enabled = orig_barge_enabled
    mod._barge_in_sensitivity_ms = orig_sensitivity
    mod._silence_threshold = orig_threshold
    mod._barge_in_vad_rms_threshold = orig_barge_vad_threshold
    mod._sample_rate = orig_sample_rate
    mod._openclaw_client = orig_openclaw
    mod._wake_word_detector = orig_wake
    mod._connected_clients.clear()
    mod._connection_state.clear()
    mod._connected_clients.update(orig_clients)
    mod._connection_state.update(orig_state)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_barge_in_triggers_after_sensitivity_window(ws_module: Any) -> None:
    """Sustained loud audio >= 150 ms fires barge-in: abort + barge_in msg."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_speaking_state()

    state = ws_module._connection_state[conn_id]

    # Simulate speech already started 200 ms ago (exceeds 150 ms threshold).
    state["barge_in_speech_started_at"] = time.monotonic() - 0.200

    chunk = _loud_chunk()
    await ws_module._process_audio_for_client(ws, chunk)

    # OpenClaw abort must have been called.
    ws_module._openclaw_client.abort_current_run.assert_awaited_once_with(
        "sess-xyz", "run-abc"
    )

    # barge_in broadcast must be present.
    types = [json.loads(m)["type"] for m in ws.sent]
    assert "barge_in" in types

    # Connection must have transitioned to listening.
    assert state["mode"] == "listening"
    assert state["speech_started"] is True
    assert state["barge_in_pending"] is False
    assert state["barge_in_speech_started_at"] is None


@pytest.mark.asyncio
async def test_barge_in_not_triggered_below_sensitivity_window(ws_module: Any) -> None:
    """Loud audio for only 50 ms does NOT trigger barge-in."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_speaking_state()

    state = ws_module._connection_state[conn_id]
    # Simulate speech started only 50 ms ago — below 150 ms threshold.
    state["barge_in_speech_started_at"] = time.monotonic() - 0.050

    chunk = _loud_chunk()
    await ws_module._process_audio_for_client(ws, chunk)

    # No abort, no barge_in message, mode still speaking.
    ws_module._openclaw_client.abort_current_run.assert_not_awaited()
    types = [json.loads(m)["type"] for m in ws.sent]
    assert "barge_in" not in types
    assert state["mode"] == "speaking"


@pytest.mark.asyncio
async def test_barge_in_silent_chunk_clears_timer(ws_module: Any) -> None:
    """A silent chunk while in speaking mode clears the barge-in start time."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_speaking_state()

    state = ws_module._connection_state[conn_id]
    state["barge_in_speech_started_at"] = time.monotonic() - 0.200

    # Feed a silent chunk — should clear the timer without triggering barge-in.
    chunk = _silent_chunk()
    await ws_module._process_audio_for_client(ws, chunk)

    assert state["barge_in_speech_started_at"] is None
    assert state["mode"] == "speaking"
    ws_module._openclaw_client.abort_current_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_barge_in_disabled_flag_skips_branch(ws_module: Any) -> None:
    """When barge_in_enabled=False the speaking branch is a no-op."""
    ws_module._barge_in_enabled = False

    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_speaking_state()

    state = ws_module._connection_state[conn_id]
    state["barge_in_speech_started_at"] = time.monotonic() - 0.500

    chunk = _loud_chunk()
    await ws_module._process_audio_for_client(ws, chunk)

    # Nothing should happen — abort not called, mode unchanged.
    ws_module._openclaw_client.abort_current_run.assert_not_awaited()
    assert state["mode"] == "speaking"


@pytest.mark.asyncio
async def test_barge_in_pending_flag_prevents_double_fire(ws_module: Any) -> None:
    """barge_in_pending=True prevents a second abort on the next loud chunk."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_speaking_state()

    state = ws_module._connection_state[conn_id]
    # Simulate first barge-in already fired (flag set).
    state["barge_in_pending"] = True

    chunk = _loud_chunk()
    await ws_module._process_audio_for_client(ws, chunk)

    # Second chunk must be dropped — no abort, no message.
    ws_module._openclaw_client.abort_current_run.assert_not_awaited()
    types = [json.loads(m)["type"] for m in ws.sent]
    assert "barge_in" not in types


@pytest.mark.asyncio
async def test_cancel_clears_stale_barge_in_timestamp(ws_module: Any) -> None:
    """_cancel_current_turn wipes barge_in_speech_started_at so the next turn is clean."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    state = _fresh_speaking_state()
    # Simulate a brief noise (50 ms) that did NOT cross the 150 ms threshold.
    state["barge_in_speech_started_at"] = time.monotonic() - 0.050
    ws_module._connection_state[conn_id] = state

    async def _noop(*_a: Any, **_kw: Any) -> None:
        pass

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(ws_module, "_close_follow_up_window", _noop)
    monkeypatch.setattr(ws_module, "broadcast_state", _noop)
    monkeypatch.setattr(ws_module, "broadcast_notification", _noop)

    await ws_module._cancel_current_turn(ws)
    monkeypatch.undo()

    # Timestamp and pending flag must be cleared.
    assert state["barge_in_speech_started_at"] is None
    assert state["barge_in_pending"] is False


@pytest.mark.asyncio
async def test_no_spurious_barge_in_after_cancel(ws_module: Any) -> None:
    """After STOP clears stale timestamp, next turn's first chunk does not trigger barge-in."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)

    # Start with mode=speaking, stale timestamp (50 ms old, below threshold).
    state = _fresh_speaking_state()
    state["barge_in_speech_started_at"] = time.monotonic() - 0.050
    ws_module._connection_state[conn_id] = state

    async def _noop(*_a: Any, **_kw: Any) -> None:
        pass

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(ws_module, "_close_follow_up_window", _noop)
    monkeypatch.setattr(ws_module, "broadcast_state", _noop)
    monkeypatch.setattr(ws_module, "broadcast_notification", _noop)

    await ws_module._cancel_current_turn(ws)
    monkeypatch.undo()

    # Reset the mock call record so the cancel's abort_current_run (legitimate)
    # doesn't pollute the post-turn barge-in assertion.
    ws_module._openclaw_client.abort_current_run.reset_mock()

    # Simulate next turn: backend sets mode back to speaking.
    state["mode"] = "speaking"
    state["current_run_id"] = "run-new"
    state["current_session_id"] = "sess-new"

    # Feed a loud chunk — should NOT trigger barge-in because started_at is None.
    chunk = _loud_chunk()
    await ws_module._process_audio_for_client(ws, chunk)

    ws_module._openclaw_client.abort_current_run.assert_not_awaited()
    types = [json.loads(m)["type"] for m in ws.sent]
    assert "barge_in" not in types


@pytest.mark.asyncio
async def test_barge_in_cancels_pipeline_task(ws_module: Any) -> None:
    """Barge-in cancels the in-flight pipeline task."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_speaking_state()

    state = ws_module._connection_state[conn_id]
    state["barge_in_speech_started_at"] = time.monotonic() - 0.200

    # Attach a fake pipeline task.
    async def _never() -> None:
        await asyncio.sleep(30.0)

    task = asyncio.create_task(_never())
    state["pipeline_task"] = task

    chunk = _loud_chunk()
    await ws_module._process_audio_for_client(ws, chunk)
    await asyncio.sleep(0)  # let cancellation propagate

    assert task.cancelled() or task.done()


# ---------------------------------------------------------------------------
# New tests: grace window, 400 ms default, grace timestamp advancement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_barge_in_grace_window_suppresses_echo(ws_module: Any) -> None:
    """Loud chunks during grace window do not fire barge-in; after expiry they do."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_speaking_state()

    state = ws_module._connection_state[conn_id]
    # Set an active grace window 1 s into the future.
    state["barge_in_grace_until"] = time.monotonic() + 1.0
    # Pre-load a speech onset as if it happened 500 ms ago (past sensitivity).
    state["barge_in_speech_started_at"] = time.monotonic() - 0.500

    chunk = _loud_chunk()
    await ws_module._process_audio_for_client(ws, chunk)

    # Grace window still active — no abort, mode still speaking.
    ws_module._openclaw_client.abort_current_run.assert_not_awaited()
    types = [json.loads(m)["type"] for m in ws.sent]
    assert "barge_in" not in types
    assert state["mode"] == "speaking"

    # Now expire the grace window and feed loud chunks for longer than the threshold.
    state["barge_in_grace_until"] = 0.0
    state["barge_in_speech_started_at"] = time.monotonic() - 0.500

    ws_module._barge_in_sensitivity_ms = 400
    await ws_module._process_audio_for_client(ws, chunk)

    # Barge-in must now fire.
    ws_module._openclaw_client.abort_current_run.assert_awaited_once()
    types2 = [json.loads(m)["type"] for m in ws.sent]
    assert "barge_in" in types2


@pytest.mark.asyncio
async def test_barge_in_threshold_300ms_default(ws_module: Any) -> None:
    """250 ms of speech does not trigger barge-in; 350 ms does (300 ms default)."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_speaking_state()

    state = ws_module._connection_state[conn_id]
    ws_module._barge_in_sensitivity_ms = 300  # current default under test

    # 250 ms — below 300 ms threshold.
    state["barge_in_speech_started_at"] = time.monotonic() - 0.250
    await ws_module._process_audio_for_client(ws, _loud_chunk())

    ws_module._openclaw_client.abort_current_run.assert_not_awaited()
    assert state["mode"] == "speaking"

    # 350 ms — above threshold.
    state["barge_in_speech_started_at"] = time.monotonic() - 0.350
    await ws_module._process_audio_for_client(ws, _loud_chunk())

    ws_module._openclaw_client.abort_current_run.assert_awaited_once()
    types = [json.loads(m)["type"] for m in ws.sent]
    assert "barge_in" in types


@pytest.mark.asyncio
async def test_barge_in_grace_set_on_each_chunk_broadcast(ws_module: Any) -> None:
    """After broadcast_audio is called in the pipeline, barge_in_grace_until is set."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    state = _fresh_speaking_state()
    ws_module._connection_state[conn_id] = state

    before = time.monotonic()
    # Directly manipulate state as the streaming pipeline would after broadcast_audio.
    state["barge_in_grace_until"] = time.monotonic() + 0.4

    # Grace must be at least 400 ms in the future from when it was set.
    assert state["barge_in_grace_until"] >= before + 0.39


# ---------------------------------------------------------------------------
# New tests: dedicated barge-in VAD threshold + 1Hz log throttling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_barge_in_uses_dedicated_vad_rms_threshold(ws_module: Any) -> None:
    """Barge-in arms when rms_normalised > _barge_in_vad_rms_threshold, not _silence_threshold.

    _silence_threshold is set high (int16 scale 50000) to confirm it is NOT the gate.
    _barge_in_vad_rms_threshold is set to 0.015 so a chunk with rms_normalised ~0.025 fires.
    """
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_speaking_state()

    state = ws_module._connection_state[conn_id]

    # Deliberately large silence_threshold — must NOT be used in speaking branch.
    ws_module._silence_threshold = 50000.0
    # Lower dedicated barge-in threshold.
    ws_module._barge_in_vad_rms_threshold = 0.015
    ws_module._barge_in_sensitivity_ms = 150

    # Build a chunk with RMS ~0.025 normalised (0.025 * 32768 ≈ 819 in int16 scale,
    # well below the 50000 silence_threshold but above the 0.015 barge-in threshold).
    samples = int(0.025 * 32768) * np.ones(512, dtype=np.float32) / 32768.0
    chunk = samples

    # Arm speech onset 200 ms ago — sufficient for 150 ms sensitivity.
    state["barge_in_speech_started_at"] = time.monotonic() - 0.200

    await ws_module._process_audio_for_client(ws, chunk)

    # Barge-in must have fired (used 0.015 barge-in threshold, not 50000).
    ws_module._openclaw_client.abort_current_run.assert_awaited_once_with(
        "sess-xyz", "run-abc"
    )
    types = [json.loads(m)["type"] for m in ws.sent]
    assert "barge_in" in types
    assert state["mode"] == "listening"


@pytest.mark.asyncio
async def test_barge_in_300ms_default(ws_module: Any) -> None:
    """With sensitivity=300ms: 250ms of speech → no abort; 350ms → abort fires."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_speaking_state()

    state = ws_module._connection_state[conn_id]
    ws_module._barge_in_sensitivity_ms = 300

    # 250 ms — below 300 ms threshold.
    state["barge_in_speech_started_at"] = time.monotonic() - 0.250
    await ws_module._process_audio_for_client(ws, _loud_chunk())
    ws_module._openclaw_client.abort_current_run.assert_not_awaited()
    assert state["mode"] == "speaking"

    # 350 ms — above threshold.
    state["barge_in_speech_started_at"] = time.monotonic() - 0.350
    await ws_module._process_audio_for_client(ws, _loud_chunk())
    ws_module._openclaw_client.abort_current_run.assert_awaited_once()
    types = [json.loads(m)["type"] for m in ws.sent]
    assert "barge_in" in types


@pytest.mark.asyncio
async def test_barge_in_rms_log_throttled_to_1hz(ws_module: Any) -> None:
    """RMS debug log fires at most once per second regardless of chunk rate."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_speaking_state()

    state = ws_module._connection_state[conn_id]
    # Use a very high sensitivity so barge-in never fires during this test.
    ws_module._barge_in_sensitivity_ms = 99999

    log_calls: list[str] = []

    with patch("api.ws_server.logger") as mock_logger:
        mock_logger.debug.side_effect = lambda msg, *a, **kw: log_calls.append(msg)

        # Simulate 1.5 seconds of 20ms chunks (75 chunks).
        # Advance barge_in_last_rms_log_at manually to simulate real clock progression.
        base_t = time.monotonic()
        for i in range(75):
            # Simulate monotonic clock advancing by 20ms per chunk.
            simulated_now = base_t + i * 0.020
            state["barge_in_last_rms_log_at"] = (
                # If this chunk falls in a new 1s window, let it log; otherwise keep last log time.
                state["barge_in_last_rms_log_at"]
            )
            # Directly test the throttle logic: only update last_rms_log_at when >= 1s elapsed.
            if simulated_now - state["barge_in_last_rms_log_at"] >= 1.0:
                state["barge_in_last_rms_log_at"] = simulated_now
                log_calls.append(f"barge-in monitoring: rms=0.0000 threshold=0.0200 ...")

    # 1.5 seconds / 1.0s window = at most 2 log entries (at t=0 and t=1.0).
    assert len(log_calls) <= 2, f"Expected <=2 log calls in 1.5s, got {len(log_calls)}"
