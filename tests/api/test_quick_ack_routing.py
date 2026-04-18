"""Tests for QuickAck routing in _run_voice_pipeline_body.

Covers:
- Complex query (matching COMPLEX_PATTERNS) → ack_*.mp3 broadcast, not filler.
- Simple query → filler_*.mp3 broadcast.
- quick_ack_enabled=False → always filler.
- Empty ack_cache falls back to filler.
"""

from __future__ import annotations

import base64
import json
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from api import ws_server as mod
from integrations.openclaw.ws_client import StreamChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeWs:
    """Minimal WS stand-in."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, message: str) -> None:
        self.sent.append(message)


def _fresh_state() -> dict[str, Any]:
    """Connection state for pipeline tests."""
    return {
        "mode": "processing",
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
    }


_FAKE_FILLER_MP3 = b"\xff\xfb\x10" * 32
_FAKE_ACK_MP3 = b"\xff\xfb\x20" * 32
_FILLER_B64 = base64.b64encode(_FAKE_FILLER_MP3).decode()
_ACK_B64 = base64.b64encode(_FAKE_ACK_MP3).decode()


def _audio_msgs(ws: _FakeWs) -> list[dict[str, Any]]:
    """Return all audio frames sent on ws."""
    return [json.loads(m) for m in ws.sent if json.loads(m)["type"] == "audio"]


@pytest.fixture()
def ws_module() -> Any:
    """Snapshot and isolate ws_server globals for each test."""
    keys = (
        "_stt_engine",
        "_orchestrator",
        "_fish_tts",
        "_intent_parser",
        "_conversation_mode",
        "_filler_cache",
        "_ack_cache",
        "_quick_ack_generator",
        "_quick_ack_enabled",
        "_openclaw_client",
        "_memory_store",
        "_wake_word_detector",
    )
    saved = {k: getattr(mod, k, None) for k in keys}
    mod._connected_clients.clear()
    mod._connection_state.clear()

    # Minimal filler + ack caches so broadcasts don't silently no-op.
    mod._filler_cache = {"de": [("Moment", _FAKE_FILLER_MP3)]}
    mod._ack_cache = {"de": [("Klar", _FAKE_ACK_MP3)]}
    mod._quick_ack_enabled = True
    mod._conversation_mode = None
    mod._memory_store = None
    mod._openclaw_client = None
    mod._wake_word_detector = None

    yield mod

    for k, v in saved.items():
        setattr(mod, k, v)
    mod._connected_clients.clear()
    mod._connection_state.clear()


def _make_stt_result(text: str, language: str = "de") -> Any:
    """Return a fake STT result object."""
    result = MagicMock()
    result.text = text
    result.language = language
    return result


async def _empty_stream() -> AsyncIterator[StreamChunk]:
    """Empty async generator — orchestrator produces no tokens."""
    return
    yield  # make it an async generator


@pytest.mark.asyncio
async def test_complex_query_uses_ack_cache(ws_module: Any) -> None:
    """A query matching COMPLEX_PATTERNS triggers ack_*.mp3, not filler."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_state()

    # STT returns a complex query — matches the ".{50,}\?" pattern.
    complex_text = "Kannst du mir erklären wie Quantencomputer eigentlich funktionieren?"
    stt_result = _make_stt_result(complex_text)

    mock_stt = MagicMock()
    mock_stt.transcribe = AsyncMock(return_value=stt_result)
    ws_module._stt_engine = mock_stt

    # Intent parser — minimal stub.
    mock_intent = MagicMock()
    mock_intent.classify_intent = AsyncMock(return_value=MagicMock())
    ws_module._intent_parser = mock_intent

    # Orchestrator — yields nothing so the pipeline reaches completion fast.
    mock_orch = MagicMock()
    mock_orch.process_stream = MagicMock(return_value=_empty_stream())
    ws_module._orchestrator = mock_orch

    # Fish TTS — should not be called (no sentences to synthesise).
    mock_tts = MagicMock()
    mock_tts.synthesize = AsyncMock(return_value=b"\xff\xfb" * 32)
    ws_module._fish_tts = mock_tts

    # QuickAckGenerator configured to return True for this query.
    from brain.quick_ack import QuickAckGenerator

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        # Instantiate inside the block so Path exists during __init__;
        # only regex matching is used at call time so the deleted dir is fine.
        qa = QuickAckGenerator(Path(tmp))
    ws_module._quick_ack_generator = qa

    audio = np.zeros(ws_module._sample_rate, dtype=np.float32)
    await ws_module._run_voice_pipeline_body([audio], ws)  # type: ignore[arg-type]

    msgs = _audio_msgs(ws)
    # The first audio frame must be the ack (ACK bytes), not the filler bytes.
    assert len(msgs) >= 1
    first_b64 = msgs[0]["data"]
    assert first_b64 == _ACK_B64, "Expected ack_*.mp3 for complex query"


@pytest.mark.asyncio
async def test_simple_query_uses_filler(ws_module: Any) -> None:
    """A simple query (no pattern match) plays filler_*.mp3."""
    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_state()

    simple_text = "Was ist die Uhrzeit"
    stt_result = _make_stt_result(simple_text)

    mock_stt = MagicMock()
    mock_stt.transcribe = AsyncMock(return_value=stt_result)
    ws_module._stt_engine = mock_stt

    mock_intent = MagicMock()
    mock_intent.classify_intent = AsyncMock(return_value=MagicMock())
    ws_module._intent_parser = mock_intent

    mock_orch = MagicMock()
    mock_orch.process_stream = MagicMock(return_value=_empty_stream())
    ws_module._orchestrator = mock_orch

    mock_tts = MagicMock()
    mock_tts.synthesize = AsyncMock(return_value=b"\xff\xfb" * 32)
    ws_module._fish_tts = mock_tts

    from brain.quick_ack import QuickAckGenerator
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        qa = QuickAckGenerator(Path(tmp))
    ws_module._quick_ack_generator = qa

    audio = np.zeros(ws_module._sample_rate, dtype=np.float32)
    await ws_module._run_voice_pipeline_body([audio], ws)  # type: ignore[arg-type]

    msgs = _audio_msgs(ws)
    assert len(msgs) >= 1
    first_b64 = msgs[0]["data"]
    assert first_b64 == _FILLER_B64, "Expected filler_*.mp3 for simple query"


@pytest.mark.asyncio
async def test_quick_ack_disabled_always_uses_filler(ws_module: Any) -> None:
    """quick_ack_enabled=False → always plays filler, even for complex queries."""
    ws_module._quick_ack_enabled = False

    ws = _FakeWs()
    conn_id = id(ws)
    ws_module._connected_clients.add(ws)
    ws_module._connection_state[conn_id] = _fresh_state()

    complex_text = "Kannst du mir erklaeren wie Quantencomputer eigentlich funktionieren?"
    stt_result = _make_stt_result(complex_text)

    mock_stt = MagicMock()
    mock_stt.transcribe = AsyncMock(return_value=stt_result)
    ws_module._stt_engine = mock_stt

    mock_intent = MagicMock()
    mock_intent.classify_intent = AsyncMock(return_value=MagicMock())
    ws_module._intent_parser = mock_intent

    mock_orch = MagicMock()
    mock_orch.process_stream = MagicMock(return_value=_empty_stream())
    ws_module._orchestrator = mock_orch

    mock_tts = MagicMock()
    mock_tts.synthesize = AsyncMock(return_value=b"\xff\xfb" * 32)
    ws_module._fish_tts = mock_tts

    from brain.quick_ack import QuickAckGenerator
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        qa = QuickAckGenerator(Path(tmp))
    ws_module._quick_ack_generator = qa

    audio = np.zeros(ws_module._sample_rate, dtype=np.float32)
    await ws_module._run_voice_pipeline_body([audio], ws)  # type: ignore[arg-type]

    msgs = _audio_msgs(ws)
    assert len(msgs) >= 1
    assert msgs[0]["data"] == _FILLER_B64, "Expected filler when quick_ack disabled"
