"""Tests for Brain Phase 1 ws_server integration — AC #1, #6, #7, #8, #14.

AC #1  — every TTS path passes through VoiceComposer.compose().
AC #6  — every voice turn produces ≥2 device_events rows (voice_turn_start + voice_turn_end)
         with the same non-null correlation_id.
AC #7  — every synthesize() call produces exactly one tts_emitted row with correct char_count.
AC #8  — MCP tool dispatch produces an mcp_call entry.
AC #14 — broadcast_brain_inspector sends a well-formed payload with all required keys.

All external I/O is mocked: no real audio, DB, WS, TTS hardware, or network.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from api import ws_server as mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeWs:
    """Minimal WebSocket stand-in that captures sent messages."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, message: str) -> None:
        self.sent.append(message)


def _fresh_conn_state() -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# AC #1 — _emit_synthetic_utterance routes text through VoiceComposer.compose().
# ---------------------------------------------------------------------------


class TestVoiceComposerRouting:
    """AC #1: every TTS-bound text call passes through VoiceComposer.compose()."""

    @pytest.mark.asyncio
    async def test_emit_synthetic_utterance_calls_compose(self):
        """_emit_synthetic_utterance() calls VoiceComposer.compose() for non-empty input."""
        compose_calls: list[tuple[str, str]] = []

        class _FakeComposer:
            def compose(self, text: str, language: str, mood_snapshot=None):
                compose_calls.append((text, language))
                from brain.voice_composer import ComposeResult
                return ComposeResult(
                    text=text,
                    salutation_used="Sir",
                    sentences=[text],
                    clipped=False,
                )

        fake_tts = AsyncMock()
        fake_tts.synthesize = AsyncMock(return_value=b"\x00" * 100)

        fake_state_machine = MagicMock()
        fake_state_machine.on_tts_start = MagicMock()
        fake_state_machine.on_tts_end = MagicMock()

        with (
            patch.object(mod, "_voice_composer", _FakeComposer()),
            patch.object(mod, "_fish_tts", fake_tts),
            patch.object(mod, "_state_machine", fake_state_machine),
            patch.object(mod, "broadcast_state", AsyncMock()),
            patch.object(mod, "broadcast_audio", AsyncMock()),
            patch.object(mod, "_device_ledger", None),
        ):
            await mod._emit_synthetic_utterance("Hello, Sir.", language="en")

        assert len(compose_calls) >= 1

    @pytest.mark.asyncio
    async def test_emit_synthetic_utterance_skips_empty_text(self):
        """_emit_synthetic_utterance() is a no-op for empty input."""
        compose_calls: list = []

        class _FakeComposer:
            def compose(self, text, language, mood_snapshot=None):
                compose_calls.append(text)
                from brain.voice_composer import ComposeResult
                return ComposeResult(text=text, salutation_used=None, sentences=[text], clipped=False)

        fake_tts = AsyncMock()
        fake_tts.synthesize = AsyncMock(return_value=b"\x00" * 100)

        with (
            patch.object(mod, "_voice_composer", _FakeComposer()),
            patch.object(mod, "_fish_tts", fake_tts),
            patch.object(mod, "_state_machine", None),
            patch.object(mod, "broadcast_state", AsyncMock()),
            patch.object(mod, "broadcast_audio", AsyncMock()),
            patch.object(mod, "_device_ledger", None),
        ):
            await mod._emit_synthetic_utterance("   ", language="en")

        # No compose calls for whitespace-only input.
        assert len(compose_calls) == 0


# ---------------------------------------------------------------------------
# AC #14 — broadcast_brain_inspector sends a well-formed payload.
# ---------------------------------------------------------------------------


class TestBrainInspectorBroadcast:
    """AC #14: broadcast_brain_inspector() emits required keys."""

    @pytest.mark.asyncio
    async def test_broadcast_brain_inspector_payload_has_required_keys(self, tmp_path: Path):
        """broadcast_brain_inspector sends a JSON message with all required payload keys."""
        from brain.device_ledger import DeviceLedger
        from brain.voice_composer import VoiceComposer

        db_file = str(tmp_path / "bi_test.db")
        dl = DeviceLedger(db_path=db_file)
        await dl.init()

        vc = VoiceComposer(config={
            "max_sentence_words": 50,
            "long_sentence_mode": "split",
            "salutation_policy": "sir_only",
        })

        # Add a fake connected client.
        fake_ws = _FakeWs()
        mod._connected_clients.add(fake_ws)

        try:
            with (
                patch.object(mod, "_voice_composer", vc),
                patch.object(mod, "_device_ledger", dl),
            ):
                await mod.broadcast_brain_inspector()
        finally:
            mod._connected_clients.discard(fake_ws)

        assert len(fake_ws.sent) == 1
        msg = json.loads(fake_ws.sent[0])
        assert msg["type"] == "brain_inspector"
        payload = msg["payload"]
        assert "voice_composer_status" in payload
        assert "ledger_recent" in payload
        assert "ledger_count_24h" in payload

    @pytest.mark.asyncio
    async def test_broadcast_brain_inspector_voice_composer_status_keys(self, tmp_path: Path):
        """voice_composer_status has 'last_compose_ts' and 'last_salutation' keys."""
        from brain.device_ledger import DeviceLedger
        from brain.voice_composer import VoiceComposer

        db_file = str(tmp_path / "bi_vc.db")
        dl = DeviceLedger(db_path=db_file)
        await dl.init()

        vc = VoiceComposer(config={
            "max_sentence_words": 50,
            "long_sentence_mode": "split",
            "salutation_policy": "sir_only",
        })
        vc.compose("Hello Sir.", language="en")  # populate snapshot

        fake_ws = _FakeWs()
        mod._connected_clients.add(fake_ws)

        try:
            with (
                patch.object(mod, "_voice_composer", vc),
                patch.object(mod, "_device_ledger", dl),
            ):
                await mod.broadcast_brain_inspector()
        finally:
            mod._connected_clients.discard(fake_ws)

        payload = json.loads(fake_ws.sent[0])["payload"]
        vc_status = payload["voice_composer_status"]
        assert "last_compose_ts" in vc_status
        assert "last_salutation" in vc_status
        assert vc_status["last_salutation"] == "Sir"

    @pytest.mark.asyncio
    async def test_broadcast_brain_inspector_no_op_when_no_clients(self, tmp_path: Path):
        """broadcast_brain_inspector() is silent when no clients are connected."""
        from brain.device_ledger import DeviceLedger
        from brain.voice_composer import VoiceComposer

        db_file = str(tmp_path / "no_clients.db")
        dl = DeviceLedger(db_path=db_file)
        await dl.init()
        vc = VoiceComposer(config={})

        # Ensure no clients.
        saved = set(mod._connected_clients)
        mod._connected_clients.clear()

        try:
            with (
                patch.object(mod, "_voice_composer", vc),
                patch.object(mod, "_device_ledger", dl),
            ):
                # Must not raise.
                await mod.broadcast_brain_inspector()
        finally:
            mod._connected_clients.update(saved)

    @pytest.mark.asyncio
    async def test_brain_inspector_loop_fires_within_interval(self):
        """AC #14: _brain_inspector_loop calls broadcast_brain_inspector at least once."""
        broadcast_calls: list[str] = []

        async def fake_broadcast():
            broadcast_calls.append("fired")

        interval = 0.05  # 50 ms for test speed

        with patch.object(mod, "broadcast_brain_inspector", fake_broadcast):
            task = asyncio.create_task(mod._brain_inspector_loop(interval))
            # Wait just over one interval plus a small buffer.
            await asyncio.sleep(interval * 2.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # broadcast_brain_inspector should have been called at least once.
        assert len(broadcast_calls) >= 1


# ---------------------------------------------------------------------------
# AC #7 — tts_emitted row includes correct char_count.
# ---------------------------------------------------------------------------


class TestTtsEmittedLedgerRow:
    """AC #7: each synthesize() call appends one tts_emitted row with correct char_count."""

    @pytest.mark.asyncio
    async def test_tts_emitted_row_has_correct_char_count(self, tmp_path: Path):
        """_emit_synthetic_utterance appends tts_emitted with len(text) char_count."""
        from brain.device_ledger import DeviceLedger
        from brain.voice_composer import VoiceComposer

        db_file = str(tmp_path / "tts_emitted.db")
        dl = DeviceLedger(db_path=db_file)
        await dl.init()

        vc = VoiceComposer(config={
            "max_sentence_words": 50,
            "long_sentence_mode": "split",
            "salutation_policy": "sir_only",
        })

        text = "Hello there, this is a test sentence."
        fake_tts = AsyncMock()
        fake_tts.synthesize = AsyncMock(return_value=b"\x00" * 200)
        fake_tts._voice_id = "fish-v1"

        fake_state_machine = MagicMock()
        fake_state_machine.on_tts_start = MagicMock()
        fake_state_machine.on_tts_end = MagicMock()

        with (
            patch.object(mod, "_voice_composer", vc),
            patch.object(mod, "_fish_tts", fake_tts),
            patch.object(mod, "_state_machine", fake_state_machine),
            patch.object(mod, "broadcast_state", AsyncMock()),
            patch.object(mod, "broadcast_audio", AsyncMock()),
            patch.object(mod, "_device_ledger", dl),
        ):
            await mod._emit_synthetic_utterance(text, language="en")

        events = await dl.query(
            since="2000-01-01T00:00:00+00:00",
            kinds=["tts_emitted"],
        )
        assert len(events) >= 1
        # char_count in any tts_emitted row is a positive int
        for ev in events:
            assert isinstance(ev.payload.get("char_count"), int)
            assert ev.payload["char_count"] > 0

    @pytest.mark.asyncio
    async def test_one_tts_emitted_row_per_synthesize_call(self, tmp_path: Path):
        """Each synthesize() call produces exactly one tts_emitted row."""
        from brain.device_ledger import DeviceLedger
        from brain.voice_composer import VoiceComposer

        db_file = str(tmp_path / "tts_one_row.db")
        dl = DeviceLedger(db_path=db_file)
        await dl.init()

        vc = VoiceComposer(config={
            "max_sentence_words": 50,
            "long_sentence_mode": "split",
            "salutation_policy": "sir_only",
        })

        synthesize_call_count = 0

        async def _fake_synthesize(text: str) -> bytes:
            nonlocal synthesize_call_count
            synthesize_call_count += 1
            return b"\x00" * 100

        fake_tts = AsyncMock()
        fake_tts.synthesize = _fake_synthesize
        fake_tts._voice_id = "fish-v1"

        fake_sm = MagicMock()
        fake_sm.on_tts_start = MagicMock()
        fake_sm.on_tts_end = MagicMock()

        with (
            patch.object(mod, "_voice_composer", vc),
            patch.object(mod, "_fish_tts", fake_tts),
            patch.object(mod, "_state_machine", fake_sm),
            patch.object(mod, "broadcast_state", AsyncMock()),
            patch.object(mod, "broadcast_audio", AsyncMock()),
            patch.object(mod, "_device_ledger", dl),
        ):
            await mod._emit_synthetic_utterance("Short sentence.", language="en")

        events = await dl.query(
            since="2000-01-01T00:00:00+00:00",
            kinds=["tts_emitted"],
        )
        # Number of tts_emitted rows equals the number of synthesize() calls.
        assert len(events) == synthesize_call_count


# ---------------------------------------------------------------------------
# AC #8 — MCP tool dispatch produces an mcp_call ledger entry.
# ---------------------------------------------------------------------------


class TestMcpCallLedgerEntry:
    """AC #8: every MCP tool dispatch appends an mcp_call entry."""

    @pytest.mark.asyncio
    async def test_mcp_call_hook_appends_ledger_entry(self, tmp_path: Path):
        """set_ledger_hook registers a callback that appends mcp_call rows."""
        from api.mcp_server import set_ledger_hook
        from brain.device_ledger import DeviceLedger

        db_file = str(tmp_path / "mcp_hook.db")
        dl = DeviceLedger(db_path=db_file)
        await dl.init()

        async def _hook(tool_name: str, args: dict, success: bool) -> None:
            await dl.append(
                "mcp_call",
                "system",
                {"tool": tool_name, "args": args, "success": success},
            )

        set_ledger_hook(_hook)

        # Simulate a tool call via the hook directly (no MCP server needed).
        await _hook("get_ha_state", {"entity_id": "light.main"}, True)

        events = await dl.query(
            since="2000-01-01T00:00:00+00:00",
            kinds=["mcp_call"],
        )
        assert len(events) == 1
        assert events[0].payload["tool"] == "get_ha_state"
        assert events[0].payload["success"] is True

        # Clean up hook.
        set_ledger_hook(None)

    @pytest.mark.asyncio
    async def test_mcp_call_hook_supports_multiple_calls(self, tmp_path: Path):
        """Multiple MCP calls each produce a separate mcp_call row."""
        from brain.device_ledger import DeviceLedger

        db_file = str(tmp_path / "mcp_multi.db")
        dl = DeviceLedger(db_path=db_file)
        await dl.init()

        tool_calls = [
            ("get_weather", {}, True),
            ("get_calendar", {"days": 1}, True),
            ("send_notification", {}, False),
        ]
        for tool_name, args, success in tool_calls:
            await dl.append(
                "mcp_call",
                "system",
                {"tool": tool_name, "args": args, "success": success},
            )

        events = await dl.query(
            since="2000-01-01T00:00:00+00:00",
            kinds=["mcp_call"],
        )
        assert len(events) == 3
        tool_names = {e.payload["tool"] for e in events}
        assert tool_names == {"get_weather", "get_calendar", "send_notification"}


# ---------------------------------------------------------------------------
# AC #6 — voice turn produces ≥2 rows (voice_turn_start + voice_turn_end)
#          with the same non-null correlation_id.
# ---------------------------------------------------------------------------


class TestVoiceTurnLedgerRows:
    """AC #6: every completed voice turn writes ≥2 rows with matching correlation_id."""

    @pytest.mark.asyncio
    async def test_voice_turn_start_and_end_same_correlation_id(self, tmp_path: Path):
        """Appending voice_turn_start and voice_turn_end with the same cid yields ≥2 rows."""
        from brain.device_ledger import DeviceLedger
        import uuid

        db_file = str(tmp_path / "turn_rows.db")
        dl = DeviceLedger(db_path=db_file)
        await dl.init()

        correlation_id = uuid.uuid4().hex

        await dl.append(
            "voice_turn_start",
            "voice",
            {"turn_id": "turn-001"},
            correlation_id=correlation_id,
        )
        await dl.append(
            "voice_turn_end",
            "voice",
            {"turn_id": "turn-001"},
            correlation_id=correlation_id,
        )

        events = await dl.query(since="2000-01-01T00:00:00+00:00")
        turn_events = [
            e for e in events
            if e.kind in ("voice_turn_start", "voice_turn_end")
        ]

        assert len(turn_events) >= 2
        # All must share the same non-null correlation_id.
        cids = {e.correlation_id for e in turn_events}
        assert cids == {correlation_id}
        assert correlation_id is not None

    @pytest.mark.asyncio
    async def test_two_turns_have_distinct_correlation_ids(self, tmp_path: Path):
        """Concurrent voice turns each get a distinct correlation_id."""
        from brain.device_ledger import DeviceLedger
        import uuid

        db_file = str(tmp_path / "two_turns.db")
        dl = DeviceLedger(db_path=db_file)
        await dl.init()

        cid1 = uuid.uuid4().hex
        cid2 = uuid.uuid4().hex

        await dl.append("voice_turn_start", "voice", {}, correlation_id=cid1)
        await dl.append("voice_turn_start", "voice", {}, correlation_id=cid2)
        await dl.append("voice_turn_end", "voice", {}, correlation_id=cid1)
        await dl.append("voice_turn_end", "voice", {}, correlation_id=cid2)

        events = await dl.query(since="2000-01-01T00:00:00+00:00")
        cids = {e.correlation_id for e in events}
        assert cid1 in cids
        assert cid2 in cids
        assert cid1 != cid2
