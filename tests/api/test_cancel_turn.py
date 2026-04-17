"""Tests for the Phase 3 emergency-stop path.

Covers:
- ``_handle_command({"type": "cancel_turn"}, ws)`` aborts the tracked
  pipeline task for that connection, broadcasts ``status=idle`` and a
  ``Konversation gestoppt`` notification.
- A cancelled ``_run_voice_pipeline`` coroutine does NOT produce a
  ``status=speaking`` or ``audio`` frame — the late result is dropped.
- Cancellation is idempotent: firing ``cancel_turn`` twice does not
  crash even when no task is in flight.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from api import ws_server as mod


class _FakeWs:
    """Minimal WS stand-in — records every outbound message."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, message: str) -> None:
        self.sent.append(message)


def _fresh_state() -> dict[str, Any]:
    """Return a connection-state dict matching ``websocket_handler``'s init."""
    return {
        "mode": "processing",
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
        "follow_up_timer_task": None,
        "pipeline_task": None,
    }


@pytest.fixture
def ws_module() -> Any:
    """Snapshot ws_server module state around each test for isolation."""
    keys = (
        "_conversation_mode",
        "_wake_word_detector",
        "_fish_tts",
        "_stt_engine",
        "_orchestrator",
        "_intent_parser",
    )
    saved = {k: getattr(mod, k, None) for k in keys}
    mod._connected_clients.clear()
    mod._connection_state.clear()
    try:
        yield mod
    finally:
        for k, v in saved.items():
            setattr(mod, k, v)
        mod._connected_clients.clear()
        mod._connection_state.clear()


@pytest.mark.asyncio
async def test_cancel_turn_aborts_tracked_task(ws_module: Any) -> None:
    """Firing cancel_turn while a pipeline task is running aborts it."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_state()

    # Build a long-running fake pipeline task that would otherwise never
    # resolve within the test timeout.
    async def _never() -> None:
        await asyncio.sleep(30.0)

    task = asyncio.create_task(_never())
    ws_module._connection_state[conn_id]["pipeline_task"] = task

    await ws_module._handle_command({"type": "cancel_turn"}, ws)  # type: ignore[arg-type]

    # Give the event loop one tick to propagate cancellation.
    await asyncio.sleep(0)

    assert task.cancelled() or task.done()
    # The HUD sees idle + the cancel notification.
    frame_types = [json.loads(m).get("type") for m in ws.sent]
    assert "status" in frame_types
    assert "notification" in frame_types

    notif = next(
        json.loads(m) for m in ws.sent if json.loads(m)["type"] == "notification"
    )
    assert notif["payload"]["id"] == "voice-cancel"
    assert "gestoppt" in notif["payload"]["title"].lower()


@pytest.mark.asyncio
async def test_cancel_turn_idempotent_no_active_task(ws_module: Any) -> None:
    """cancel_turn is safe to send when nothing is in flight."""
    ws = _FakeWs()
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[id(ws)] = _fresh_state()

    await ws_module._handle_command({"type": "cancel_turn"}, ws)  # type: ignore[arg-type]
    # Sending again must also not raise.
    await ws_module._handle_command({"type": "cancel_turn"}, ws)  # type: ignore[arg-type]

    # Even without an active task, the HUD still gets the confirmation
    # notification — users expect visible feedback that STOP registered.
    frame_types = [json.loads(m).get("type") for m in ws.sent]
    assert frame_types.count("notification") >= 1
    assert frame_types.count("status") >= 1


@pytest.mark.asyncio
async def test_cancel_turn_drops_late_tts(ws_module: Any) -> None:
    """When cancelled, _run_voice_pipeline does not broadcast TTS audio.

    Feeds a real pipeline task with a long-running STT stub. Cancels it
    before STT resolves and checks that no ``audio`` / ``speaking`` frame
    landed on the connection.
    """
    import numpy as np

    ws = _FakeWs()
    ws_module._connected_clients.add(ws)
    conn_id = id(ws)
    ws_module._connection_state[conn_id] = _fresh_state()

    # Long-running STT; cancellation interrupts it.
    class _SlowSTT:
        async def transcribe(self, _audio: Any) -> Any:
            await asyncio.sleep(30.0)
            return None  # pragma: no cover

    ws_module._stt_engine = _SlowSTT()  # type: ignore[assignment]
    ws_module._conversation_mode = None

    chunk = np.zeros(ws_module._sample_rate, dtype=np.float32)
    task = asyncio.create_task(ws_module._run_voice_pipeline([chunk], ws))  # type: ignore[arg-type]
    ws_module._connection_state[conn_id]["pipeline_task"] = task

    # Let the pipeline reach the await in STT.
    await asyncio.sleep(0.02)

    # Fire cancel.
    await ws_module._handle_command({"type": "cancel_turn"}, ws)  # type: ignore[arg-type]

    # Pipeline task resolves without raising (CancelledError is swallowed).
    await asyncio.wait_for(task, timeout=1.0)

    # No TTS audio frame should ever have been sent.
    types = [json.loads(m).get("type") for m in ws.sent]
    assert "audio" not in types
    # And the `thinking` state flipped to `idle` — never to `speaking`.
    status_states = [
        json.loads(m)["state"]
        for m in ws.sent
        if json.loads(m).get("type") == "status"
    ]
    assert "speaking" not in status_states
    assert "idle" in status_states
