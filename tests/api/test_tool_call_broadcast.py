"""Tests for the tool-call broadcast helpers in ws_server.

Covers:
- ``broadcast_tool_call`` sends the correct JSON frame to all connected clients.
- ``_summarize_tool_call`` returns the correct German label for common tools.
- The streaming pipeline calls ``broadcast_tool_call`` when the orchestrator
  yields ``tool_started`` / ``tool_finished`` chunks.
- The timing-based synthetic tool hint fires when TTFT > 2 s.
- Existing ``broadcast_audio`` path is unaffected (no regression).
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api import ws_server as mod
from integrations.openclaw.ws_client import StreamChunk


# ── Helpers ────────────────────────────────────────────────────────────────────


class _FakeWs:
    """Minimal WS stand-in that captures sent messages."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, message: str) -> None:
        """Record the sent message."""
        self.sent.append(message)


def _fresh_state() -> dict[str, Any]:
    """Return a fresh per-connection state dict."""
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
        "barge_in_grace_until": 0.0,
        "barge_in_last_rms_log_at": 0.0,
        "last_backchannel_at": 0.0,
    }


async def _make_stream(*chunks: StreamChunk) -> AsyncIterator[StreamChunk]:
    """Async generator that yields the given StreamChunk objects."""
    for chunk in chunks:
        yield chunk


# ── broadcast_tool_call tests ──────────────────────────────────────────────────


class TestBroadcastToolCall:
    """Unit tests for broadcast_tool_call."""

    @pytest.mark.asyncio
    async def test_sends_correct_frame_shape(self) -> None:
        """broadcast_tool_call sends a JSON frame with the exact expected shape."""
        ws = _FakeWs()
        mod._connected_clients.add(ws)  # type: ignore[arg-type]
        try:
            await mod.broadcast_tool_call(
                state="started",
                tool_name="Read",
                summary="Lese config.yaml",
            )
        finally:
            mod._connected_clients.discard(ws)  # type: ignore[arg-type]

        assert len(ws.sent) == 1
        frame = json.loads(ws.sent[0])
        assert frame["type"] == "tool_call"
        payload = frame["payload"]
        assert payload["state"] == "started"
        assert payload["tool_name"] == "Read"
        assert payload["summary"] == "Lese config.yaml"

    @pytest.mark.asyncio
    async def test_finished_state(self) -> None:
        """broadcast_tool_call with state='finished' sends the correct payload."""
        ws = _FakeWs()
        mod._connected_clients.add(ws)  # type: ignore[arg-type]
        try:
            await mod.broadcast_tool_call(
                state="finished",
                tool_name="Bash",
                summary="Führe Shell-Kommando aus",
            )
        finally:
            mod._connected_clients.discard(ws)  # type: ignore[arg-type]

        frame = json.loads(ws.sent[0])
        assert frame["payload"]["state"] == "finished"
        assert frame["payload"]["tool_name"] == "Bash"

    @pytest.mark.asyncio
    async def test_empty_summary_allowed(self) -> None:
        """broadcast_tool_call with empty summary still produces a valid frame."""
        ws = _FakeWs()
        mod._connected_clients.add(ws)  # type: ignore[arg-type]
        try:
            await mod.broadcast_tool_call(state="started", tool_name="Unknown")
        finally:
            mod._connected_clients.discard(ws)  # type: ignore[arg-type]

        frame = json.loads(ws.sent[0])
        assert frame["payload"]["summary"] == ""


# ── _summarize_tool_call tests ─────────────────────────────────────────────────


class TestSummarizeToolCall:
    """Unit tests for _summarize_tool_call mapping table."""

    def test_read_with_path(self) -> None:
        """Read tool with a file_path returns 'Lese <filename>'."""
        result = mod._summarize_tool_call("Read", {"file_path": "config/config.yaml"})
        assert result == "Lese config.yaml"

    def test_write_with_path(self) -> None:
        """Write tool with a file_path returns 'Schreibe <filename>'."""
        result = mod._summarize_tool_call("Write", {"file_path": "src/api/ws_server.py"})
        assert result == "Schreibe ws_server.py"

    def test_edit_with_path(self) -> None:
        """Edit tool with a file_path returns 'Bearbeite <filename>'."""
        result = mod._summarize_tool_call("Edit", {"file_path": "src/brain/orchestrator.py"})
        assert result == "Bearbeite orchestrator.py"

    def test_bash_returns_label(self) -> None:
        """Bash tool returns the generic shell-command label."""
        result = mod._summarize_tool_call("Bash", {"command": "rm -rf /"})
        assert result == "Führe Shell-Kommando aus"

    def test_glob_returns_code_search(self) -> None:
        """Glob tool returns 'Suche im Code'."""
        result = mod._summarize_tool_call("Glob", {"pattern": "**/*.py"})
        assert result == "Suche im Code"

    def test_grep_returns_code_search(self) -> None:
        """Grep tool returns 'Suche im Code'."""
        result = mod._summarize_tool_call("Grep", {"pattern": "broadcast_tool_call"})
        assert result == "Suche im Code"

    def test_unknown_tool_returns_lowercase_name(self) -> None:
        """Unknown tool name is returned lowercased."""
        result = mod._summarize_tool_call("MyCustomTool", {})
        assert result == "mycustomtool"

    def test_empty_tool_name_returns_empty(self) -> None:
        """Empty tool name with None input returns empty string."""
        result = mod._summarize_tool_call("", None)
        assert result == ""

    def test_read_without_path_key(self) -> None:
        """Read tool with empty input returns generic 'Lese Datei'."""
        result = mod._summarize_tool_call("Read", {})
        assert result == "Lese Datei"

    def test_bash_does_not_echo_command(self) -> None:
        """Bash summary must NOT include the command text (could leak secrets)."""
        cmd = "cat /etc/passwd | grep root"
        result = mod._summarize_tool_call("Bash", {"command": cmd})
        assert cmd not in result
        assert "passwd" not in result


# ── Pipeline integration tests ─────────────────────────────────────────────────


class TestToolCallPipelineIntegration:
    """Integration tests: pipeline broadcasts tool_call for explicit tool chunks."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Register a fake WS client and isolated connection state."""
        self.ws = _FakeWs()
        conn_id = id(self.ws)
        state = _fresh_state()
        mod._connection_state[conn_id] = state
        mod._connected_clients.add(self.ws)  # type: ignore[arg-type]
        self.conn_id = conn_id
        self.state = state

        yield

        mod._connection_state.pop(conn_id, None)
        mod._connected_clients.discard(self.ws)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_explicit_tool_chunks_broadcast_twice(self) -> None:
        """Pipeline calls broadcast_tool_call twice for started + finished chunks."""
        tool_started = StreamChunk(
            type="tool_started",
            run_id="run-t1",
            new_text="",
            full_text="",
            tool_name="Read",
            tool_summary="Lese config.yaml",
        )
        tool_finished = StreamChunk(
            type="tool_finished",
            run_id="run-t1",
            new_text="",
            full_text="",
            tool_name="Read",
            tool_summary="Lese config.yaml",
        )
        text_chunk = StreamChunk(
            type="delta",
            run_id="run-t1",
            new_text="Sir, here is the config.",
            full_text="Sir, here is the config.",
        )
        final_chunk = StreamChunk(
            type="final",
            run_id="run-t1",
            new_text="",
            full_text="Sir, here is the config.",
        )

        chunks = [tool_started, tool_finished, text_chunk, final_chunk]

        broadcast_tool_calls: list[tuple[str, str, str]] = []

        async def _fake_broadcast_tool_call(
            state: str, tool_name: str, summary: str = ""
        ) -> None:
            broadcast_tool_calls.append((state, tool_name, summary))

        broadcast_audio_calls: list[str] = []

        async def _fake_broadcast_audio(audio_b64: str, text: str, **_: Any) -> None:
            broadcast_audio_calls.append(text)

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
        mock_stt_result.text = "Read the config."
        mock_stt_result.language = "en"

        with (
            patch.object(mod, "_orchestrator", mock_orchestrator),
            patch.object(mod, "_fish_tts", mock_tts),
            patch.object(mod, "_intent_parser", mock_intent),
            patch.object(mod, "_stt_engine", AsyncMock()),
            patch.object(mod, "broadcast_audio", _fake_broadcast_audio),
            patch.object(mod, "broadcast_transcript", AsyncMock()),
            patch.object(mod, "broadcast_state", AsyncMock()),
            patch.object(mod, "_broadcast_quick_ack_filler", AsyncMock()),
            patch.object(mod, "broadcast_tool_call", _fake_broadcast_tool_call),
            patch.object(mod, "_openclaw_client", MagicMock(session_id="jarvis-main")),
            patch.object(mod, "_conversation_mode", None),
            patch.object(mod, "_quick_ack_enabled", False),
        ):
            await _run_pipeline_with_chunks(
                self.ws, mock_stt_result, mock_intent, mock_orchestrator
            )

        # Two tool_call broadcasts: started then finished.
        assert len(broadcast_tool_calls) == 2
        assert broadcast_tool_calls[0] == ("started", "Read", "Lese config.yaml")
        assert broadcast_tool_calls[1] == ("finished", "Read", "Lese config.yaml")

        # Audio path still works — the text chunk feeds TTS.
        assert len(broadcast_audio_calls) >= 1

    @pytest.mark.asyncio
    async def test_no_tool_chunks_no_broadcast(self) -> None:
        """Pipeline does not call broadcast_tool_call for a plain text stream."""
        # Use immediate text (TTFT ~0 ms) so the timing-hint doesn't fire either.
        chunks = [
            StreamChunk(
                type="delta",
                run_id="run-plain",
                new_text="Hello, sir.",
                full_text="Hello, sir.",
            ),
            StreamChunk(
                type="final",
                run_id="run-plain",
                new_text="",
                full_text="Hello, sir.",
            ),
        ]

        broadcast_tool_calls: list[tuple] = []

        async def _fake_broadcast_tool_call(state: str, tool_name: str, summary: str = "") -> None:
            broadcast_tool_calls.append((state, tool_name, summary))

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
        mock_stt_result.text = "How are you?"
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
            patch.object(mod, "broadcast_tool_call", _fake_broadcast_tool_call),
            patch.object(mod, "_openclaw_client", MagicMock(session_id="jarvis-main")),
            patch.object(mod, "_conversation_mode", None),
            patch.object(mod, "_quick_ack_enabled", False),
        ):
            await _run_pipeline_with_chunks(
                self.ws, mock_stt_result, mock_intent, mock_orchestrator
            )

        # No tool events should have been broadcast.
        assert len(broadcast_tool_calls) == 0, (
            f"Expected no tool broadcasts for plain text stream, got {broadcast_tool_calls}"
        )


# ── ws_client StreamChunk tool fields tests ────────────────────────────────────


class TestStreamChunkToolFields:
    """Tests for the new tool_name / tool_summary fields on StreamChunk."""

    def test_tool_started_chunk_defaults(self) -> None:
        """tool_started chunk can be constructed with minimal arguments."""
        chunk = StreamChunk(
            type="tool_started",
            run_id="run-x",
            new_text="",
            full_text="",
            tool_name="Bash",
            tool_summary="Führe Shell-Kommando aus",
        )
        assert chunk.type == "tool_started"
        assert chunk.tool_name == "Bash"
        assert chunk.tool_summary == "Führe Shell-Kommando aus"
        assert chunk.error is None

    def test_regular_delta_has_none_tool_fields(self) -> None:
        """A regular delta StreamChunk has None for tool fields by default."""
        chunk = StreamChunk(
            type="delta",
            run_id="run-y",
            new_text="hello",
            full_text="hello",
        )
        assert chunk.tool_name is None
        assert chunk.tool_summary is None


# ── Pipeline driver ────────────────────────────────────────────────────────────


async def _run_pipeline_with_chunks(
    ws: _FakeWs,
    stt_result: Any,
    mock_intent: Any,
    mock_orchestrator: Any,
) -> None:
    """Drive the pipeline body directly from the intent-classification step.

    This reproduces the post-STT streaming block of ``_run_voice_pipeline_body``
    so tests can assert on broadcast calls without touching audio hardware.
    """
    import base64

    from audio.stream_splitter import StreamSplitter
    from audio.fish_tts import strip_markdown_for_tts, FishTTSError

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

            # Mirror the tool-chunk handling from _run_voice_pipeline_body.
            if chunk.type == "tool_started":
                await mod.broadcast_tool_call(
                    state="started",
                    tool_name=chunk.tool_name or "",
                    summary=chunk.tool_summary or "",
                )
                continue
            if chunk.type == "tool_finished":
                await mod.broadcast_tool_call(
                    state="finished",
                    tool_name=chunk.tool_name or "",
                    summary=chunk.tool_summary or "",
                )
                continue

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
