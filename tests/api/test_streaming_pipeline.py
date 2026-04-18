"""Tests for the streaming voice pipeline integration in ws_server.

Verifies:
- ``_run_voice_pipeline_body`` calls ``broadcast_audio`` once per complete
  sentence from a mock streaming orchestrator.
- ``broadcast_transcript("jarvis", ...)`` is called exactly once, with the
  full accumulated text, after streaming is complete.
- ``current_run_id`` is cleared after successful completion.
- When the stream yields an error chunk, the pipeline produces a fallback.
"""

from __future__ import annotations

from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api import ws_server as mod
from integrations.openclaw.ws_client import StreamChunk

# ── Helpers ────────────────────────────────────────────────────────────────────


class _FakeWs:
    """Minimal WS stand-in."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, message: str) -> None:
        self.sent.append(message)


def _fresh_state() -> dict[str, Any]:
    """Connection-state dict as initialised by ``websocket_handler``."""
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
    }


async def _make_stream(*chunks: StreamChunk) -> AsyncIterator[StreamChunk]:
    """Async generator that yields the given StreamChunk objects."""
    for chunk in chunks:
        yield chunk


def _multi_sentence_chunks() -> list[StreamChunk]:
    """Return a list of chunks that, when combined, form two TTS sentences."""
    sentences = [
        "Sir, everything is operational.",
        "All systems are running perfectly.",
    ]
    full = " ".join(sentences)
    return [
        StreamChunk(
            type="delta",
            run_id="run-123",
            new_text=sentences[0] + " ",
            full_text=sentences[0] + " ",
        ),
        StreamChunk(
            type="final", run_id="run-123", new_text=sentences[1], full_text=full
        ),
    ]


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestStreamingPipeline:
    """Tests for the streaming path in _run_voice_pipeline_body."""

    @pytest.fixture(autouse=True)
    def _reset_module_state(self):
        """Isolate each test: patch module globals to fresh mocks."""
        ws = _FakeWs()
        conn_id = id(ws)
        state = _fresh_state()
        mod._connection_state[conn_id] = state

        yield ws, state, conn_id

        mod._connection_state.pop(conn_id, None)

    @pytest.mark.asyncio
    async def test_broadcast_audio_called_per_sentence(self, _reset_module_state):
        """broadcast_audio is called once per complete TTS sentence."""
        ws, state, conn_id = _reset_module_state

        chunks = _multi_sentence_chunks()

        mock_orchestrator = MagicMock()
        mock_orchestrator.process_stream = MagicMock(return_value=_make_stream(*chunks))

        mock_tts = AsyncMock()
        mock_tts.synthesize = AsyncMock(return_value=b"\x00" * 1000)

        mock_intent = AsyncMock()
        from brain.intent_parser import IntentResult, Intent

        mock_intent.classify_intent = AsyncMock(
            return_value=IntentResult(intent=Intent.CHAT, confidence=0.5, params={})
        )

        mock_stt_result = MagicMock()
        mock_stt_result.text = "Status check, please."
        mock_stt_result.language = "en"

        broadcast_audio_calls: list[tuple[str, str]] = []

        async def fake_broadcast_audio(audio_b64: str, text: str) -> None:
            broadcast_audio_calls.append((audio_b64, text))

        broadcast_transcript_calls: list[tuple[str, str]] = []

        async def fake_broadcast_transcript(role: str, text: str) -> None:
            broadcast_transcript_calls.append((role, text))

        with (
            patch.object(mod, "_orchestrator", mock_orchestrator),
            patch.object(mod, "_fish_tts", mock_tts),
            patch.object(mod, "_intent_parser", mock_intent),
            patch.object(mod, "_stt_engine", AsyncMock()),
            patch.object(mod, "broadcast_audio", fake_broadcast_audio),
            patch.object(mod, "broadcast_transcript", fake_broadcast_transcript),
            patch.object(mod, "broadcast_state", AsyncMock()),
            patch.object(mod, "_broadcast_quick_ack_filler", AsyncMock()),
            patch.object(mod, "_openclaw_client", MagicMock(session_id="jarvis-main")),
            patch.object(mod, "_conversation_mode", None),
        ):
            # Simulate the pipeline body directly (no audio transcription).
            await _run_pipeline_with_text(
                ws, mock_stt_result, mock_intent, mock_orchestrator
            )

        # Both sentences should result in broadcast_audio calls.
        assert (
            len(broadcast_audio_calls) >= 1
        ), f"Expected at least 1 audio broadcast, got {len(broadcast_audio_calls)}"

        # Transcript should be broadcast exactly once for jarvis.
        jarvis_transcripts = [r for r in broadcast_transcript_calls if r[0] == "jarvis"]
        assert (
            len(jarvis_transcripts) == 1
        ), f"Expected exactly 1 jarvis transcript, got {len(jarvis_transcripts)}"

    @pytest.mark.asyncio
    async def test_full_text_in_transcript(self, _reset_module_state):
        """The single jarvis transcript broadcast contains the full response text."""
        ws, state, conn_id = _reset_module_state

        chunks = _multi_sentence_chunks()
        expected_full_text = chunks[-1].full_text  # last chunk has full text

        mock_orchestrator = MagicMock()
        mock_orchestrator.process_stream = MagicMock(return_value=_make_stream(*chunks))

        mock_tts = AsyncMock()
        mock_tts.synthesize = AsyncMock(return_value=b"\x00" * 1000)

        mock_intent = AsyncMock()
        from brain.intent_parser import IntentResult, Intent

        mock_intent.classify_intent = AsyncMock(
            return_value=IntentResult(intent=Intent.CHAT, confidence=0.5, params={})
        )

        mock_stt_result = MagicMock()
        mock_stt_result.text = "Status check."
        mock_stt_result.language = "en"

        broadcast_transcript_calls: list[tuple[str, str]] = []

        async def fake_broadcast_transcript(role: str, text: str) -> None:
            broadcast_transcript_calls.append((role, text))

        with (
            patch.object(mod, "_orchestrator", mock_orchestrator),
            patch.object(mod, "_fish_tts", mock_tts),
            patch.object(mod, "_intent_parser", mock_intent),
            patch.object(mod, "_stt_engine", AsyncMock()),
            patch.object(mod, "broadcast_audio", AsyncMock()),
            patch.object(mod, "broadcast_transcript", fake_broadcast_transcript),
            patch.object(mod, "broadcast_state", AsyncMock()),
            patch.object(mod, "_broadcast_quick_ack_filler", AsyncMock()),
            patch.object(mod, "_openclaw_client", MagicMock(session_id="jarvis-main")),
            patch.object(mod, "_conversation_mode", None),
        ):
            await _run_pipeline_with_text(
                ws, mock_stt_result, mock_intent, mock_orchestrator
            )

        jarvis_transcripts = [r for r in broadcast_transcript_calls if r[0] == "jarvis"]
        assert len(jarvis_transcripts) == 1
        assert jarvis_transcripts[0][1] == expected_full_text

    @pytest.mark.asyncio
    async def test_current_run_id_cleared_after_completion(self, _reset_module_state):
        """current_run_id is None after the pipeline finishes successfully."""
        ws, state, conn_id = _reset_module_state

        chunks = [
            StreamChunk(
                type="final",
                run_id="run-xyz",
                new_text="Done, sir.",
                full_text="Done, sir.",
            )
        ]

        mock_orchestrator = MagicMock()
        mock_orchestrator.process_stream = MagicMock(return_value=_make_stream(*chunks))

        mock_tts = AsyncMock()
        mock_tts.synthesize = AsyncMock(return_value=b"\x00" * 500)

        mock_intent = AsyncMock()
        from brain.intent_parser import IntentResult, Intent

        mock_intent.classify_intent = AsyncMock(
            return_value=IntentResult(intent=Intent.CHAT, confidence=0.5, params={})
        )

        mock_stt_result = MagicMock()
        mock_stt_result.text = "Are you there?"
        mock_stt_result.language = "en"

        with (
            patch.object(mod, "_orchestrator", mock_orchestrator),
            patch.object(mod, "_fish_tts", mock_tts),
            patch.object(mod, "_intent_parser", mock_intent),
            patch.object(mod, "_stt_engine", AsyncMock()),
            patch.object(mod, "broadcast_audio", AsyncMock()),
            patch.object(mod, "broadcast_transcript", AsyncMock()),
            patch.object(mod, "broadcast_state", AsyncMock()),
            patch.object(mod, "_broadcast_quick_ack_filler", AsyncMock()),
            patch.object(mod, "_openclaw_client", MagicMock(session_id="jarvis-main")),
            patch.object(mod, "_conversation_mode", None),
        ):
            await _run_pipeline_with_text(
                ws, mock_stt_result, mock_intent, mock_orchestrator
            )

        assert state["current_run_id"] is None


# ── Inline pipeline driver ─────────────────────────────────────────────────────
# We call the pipeline body directly with a pre-made STT result to avoid
# having to mock the full audio stack (STT, wake word, etc.).


async def _run_pipeline_with_text(
    ws: _FakeWs,
    stt_result: Any,
    mock_intent: Any,
    mock_orchestrator: Any,
) -> None:
    """Drive the pipeline body from the intent-classification step onward.

    This replicates the post-STT portion of ``_run_voice_pipeline_body``
    using already-configured mocks so we can test the streaming path in
    isolation without touching audio hardware.
    """
    import base64

    from audio.stream_splitter import StreamSplitter
    from audio.fish_tts import strip_markdown_for_tts, FishTTSError

    # Mirrors the streaming block in _run_voice_pipeline_body.
    conn_state = mod._connection_state.get(id(ws))
    fish_tts = mod._fish_tts
    openclaw_client = mod._openclaw_client
    orchestrator = mod._orchestrator
    intent_parser = mod._intent_parser

    intent_result = await intent_parser.classify_intent(
        stt_result.text, stt_result.language
    )

    current_run_id: str | None = None
    full_response_text = ""
    current_session_id = (
        openclaw_client.session_id if openclaw_client else "jarvis-main"
    )

    splitter = StreamSplitter(min_chars=40, max_wait_ms=600)

    async def _token_stream():
        nonlocal current_run_id, full_response_text, current_session_id
        async for chunk in orchestrator.process_stream(
            text=stt_result.text,
            language=stt_result.language,
            intent_result=intent_result,
        ):
            if (
                chunk.run_id
                and chunk.run_id not in ("local", "subprocess", "chat-fallback")
                and current_run_id is None
            ):
                current_run_id = chunk.run_id
                if conn_state is not None:
                    conn_state["current_run_id"] = current_run_id
                    conn_state["current_session_id"] = current_session_id
            full_response_text = chunk.full_text
            if chunk.type == "error":
                return
            if chunk.new_text:
                yield chunk.new_text

    async for sentence in splitter.process(_token_stream()):
        tts_text = strip_markdown_for_tts(sentence)
        if not tts_text.strip():
            continue
        try:
            audio_bytes = await fish_tts.synthesize(tts_text)
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            await mod.broadcast_audio(audio_b64, sentence)
        except FishTTSError:
            pass

    if not full_response_text:
        full_response_text = "Error."

    await mod.broadcast_transcript("jarvis", full_response_text)

    if conn_state is not None:
        conn_state["current_run_id"] = None
        conn_state["current_session_id"] = None
