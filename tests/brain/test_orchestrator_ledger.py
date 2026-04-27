"""Tests for Orchestrator LEDGER_QUERY fast-path — AC #13.

Verifies that a LEDGER_QUERY intent never calls ClaudeClient.chat or
OpenClawClient.query_agent_stream, and that the returned narration
string is non-empty.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_claude_client():
    """Return a mock ClaudeClient whose chat() raises if called."""
    client = MagicMock()
    client.chat = AsyncMock(
        side_effect=AssertionError("ClaudeClient.chat must NOT be called for LEDGER_QUERY")
    )
    client.openclaw = None  # no OpenClaw in this test
    return client


async def _make_seeded_ledger(db_path: str):
    """Return an initialised DeviceLedger with pre-seeded events."""
    from brain.device_ledger import DeviceLedger

    dl = DeviceLedger(db_path=db_path)
    await dl.init()
    await dl.append("wake_word", "voice", {})
    await dl.append("voice_turn_start", "voice", {}, correlation_id="cid-1")
    await dl.append("tts_emitted", "voice", {"char_count": 80, "duration_ms": 2000})
    await dl.append("voice_turn_end", "voice", {}, correlation_id="cid-1")
    return dl


def _make_orchestrator(claude_client, device_ledger):
    """Construct an Orchestrator with mocked config and the given ledger."""
    from brain.orchestrator import Orchestrator

    cfg_mock = MagicMock()
    cfg_mock.get_section.return_value = {
        "orchestrator_model": "claude-opus-4-5",
        "orchestrator_max_tokens": 150,
        "skip_orchestrator_on_clear_intent": True,
        "history_turns_for_orchestrator": 3,
    }
    cfg_mock.get.return_value = "Europe/Zurich"

    with patch("brain.orchestrator.get_config", return_value=cfg_mock):
        orchestrator = Orchestrator(
            claude_client=claude_client,
            device_ledger=device_ledger,
        )
    return orchestrator


# ---------------------------------------------------------------------------
# AC #13 — LEDGER_QUERY fast-path: no LLM, non-empty narration.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ledger_query_does_not_call_claude_chat(tmp_path: Path, mock_claude_client):
    """AC #13: LEDGER_QUERY never calls ClaudeClient.chat."""
    from brain.intent_parser import Intent, IntentResult

    dl = await _make_seeded_ledger(str(tmp_path / "no_chat.db"))

    cfg_mock = MagicMock()
    cfg_mock.get_section.return_value = {
        "orchestrator_model": "claude-opus-4-5",
        "orchestrator_max_tokens": 150,
        "skip_orchestrator_on_clear_intent": True,
        "history_turns_for_orchestrator": 3,
    }
    cfg_mock.get.return_value = "Europe/Zurich"

    with patch("brain.orchestrator.get_config", return_value=cfg_mock):
        from brain.orchestrator import Orchestrator
        orch = Orchestrator(claude_client=mock_claude_client, device_ledger=dl)

    intent_result = IntentResult(
        intent=Intent.LEDGER_QUERY,
        confidence=0.85,
        original_text="what have you logged today",
        language="en",
    )
    result = await orch.process(
        "what have you logged today", language="en", intent_result=intent_result
    )

    # ClaudeClient.chat would have raised if called — we get here means it was not called.
    assert result.success is True


@pytest.mark.asyncio
async def test_ledger_query_narration_is_nonempty_en(tmp_path: Path, mock_claude_client):
    """AC #13: LEDGER_QUERY EN narration string is non-empty."""
    from brain.device_ledger import DeviceLedger
    from brain.intent_parser import Intent, IntentResult

    db_file = str(tmp_path / "nar_en.db")
    dl = DeviceLedger(db_path=db_file)
    await dl.init()

    cfg_mock = MagicMock()
    cfg_mock.get_section.return_value = {
        "orchestrator_model": "claude-opus-4-5",
        "orchestrator_max_tokens": 150,
        "skip_orchestrator_on_clear_intent": True,
        "history_turns_for_orchestrator": 3,
    }
    cfg_mock.get.return_value = "Europe/Zurich"

    with patch("brain.orchestrator.get_config", return_value=cfg_mock):
        from brain.orchestrator import Orchestrator
        orch = Orchestrator(claude_client=mock_claude_client, device_ledger=dl)

    intent_result = IntentResult(
        intent=Intent.LEDGER_QUERY,
        confidence=0.85,
        original_text="what have you logged today",
        language="en",
    )
    result = await orch.process(
        "what have you logged today", language="en", intent_result=intent_result
    )

    assert result.spoken_response.strip() != ""


@pytest.mark.asyncio
async def test_ledger_query_narration_is_nonempty_de(tmp_path: Path, mock_claude_client):
    """AC #13: LEDGER_QUERY DE narration string is non-empty."""
    from brain.device_ledger import DeviceLedger
    from brain.intent_parser import Intent, IntentResult

    db_file = str(tmp_path / "nar_de.db")
    dl = DeviceLedger(db_path=db_file)
    await dl.init()

    cfg_mock = MagicMock()
    cfg_mock.get_section.return_value = {
        "orchestrator_model": "claude-opus-4-5",
        "orchestrator_max_tokens": 150,
        "skip_orchestrator_on_clear_intent": True,
        "history_turns_for_orchestrator": 3,
    }
    cfg_mock.get.return_value = "Europe/Zurich"

    with patch("brain.orchestrator.get_config", return_value=cfg_mock):
        from brain.orchestrator import Orchestrator
        orch = Orchestrator(claude_client=mock_claude_client, device_ledger=dl)

    intent_result = IntentResult(
        intent=Intent.LEDGER_QUERY,
        confidence=0.85,
        original_text="was hast du heute aufgezeichnet",
        language="de",
    )
    result = await orch.process(
        "was hast du heute aufgezeichnet", language="de", intent_result=intent_result
    )

    assert result.spoken_response.strip() != ""


@pytest.mark.asyncio
async def test_ledger_query_narration_contains_sir(tmp_path: Path, mock_claude_client):
    """LEDGER_QUERY narration starts with 'Sir' (Decision 1 salutation)."""
    from brain.device_ledger import DeviceLedger
    from brain.intent_parser import Intent, IntentResult

    db_file = str(tmp_path / "sir.db")
    dl = DeviceLedger(db_path=db_file)
    await dl.init()

    cfg_mock = MagicMock()
    cfg_mock.get_section.return_value = {
        "orchestrator_model": "claude-opus-4-5",
        "orchestrator_max_tokens": 150,
        "skip_orchestrator_on_clear_intent": True,
        "history_turns_for_orchestrator": 3,
    }
    cfg_mock.get.return_value = "Europe/Zurich"

    with patch("brain.orchestrator.get_config", return_value=cfg_mock):
        from brain.orchestrator import Orchestrator
        orch = Orchestrator(claude_client=mock_claude_client, device_ledger=dl)

    intent_result = IntentResult(
        intent=Intent.LEDGER_QUERY,
        confidence=0.85,
        original_text="what have you logged today",
        language="en",
    )
    result = await orch.process(
        "what have you logged today", language="en", intent_result=intent_result
    )

    assert "Sir" in result.spoken_response


@pytest.mark.asyncio
async def test_ledger_query_no_openclaw_stream_called(tmp_path: Path):
    """AC #13: LEDGER_QUERY never calls query_agent_stream on OpenClawClient."""
    from brain.device_ledger import DeviceLedger
    from brain.intent_parser import Intent, IntentResult

    db_file = str(tmp_path / "oc.db")
    dl = DeviceLedger(db_path=db_file)
    await dl.init()

    # Mock an openclaw client that would raise if stream is called.
    openclaw_client = MagicMock()
    openclaw_client.query_agent_stream = AsyncMock(
        side_effect=AssertionError("query_agent_stream must NOT be called for LEDGER_QUERY")
    )

    claude_client = MagicMock()
    claude_client.chat = AsyncMock(
        side_effect=AssertionError("chat must NOT be called for LEDGER_QUERY")
    )
    claude_client.openclaw = openclaw_client

    cfg_mock = MagicMock()
    cfg_mock.get_section.return_value = {
        "orchestrator_model": "claude-opus-4-5",
        "orchestrator_max_tokens": 150,
        "skip_orchestrator_on_clear_intent": True,
        "history_turns_for_orchestrator": 3,
    }
    cfg_mock.get.return_value = "Europe/Zurich"

    with patch("brain.orchestrator.get_config", return_value=cfg_mock):
        from brain.orchestrator import Orchestrator
        orch = Orchestrator(claude_client=claude_client, device_ledger=dl)

    intent_result = IntentResult(
        intent=Intent.LEDGER_QUERY,
        confidence=0.85,
        original_text="what have you logged today",
        language="en",
    )

    # This must complete without raising AssertionError.
    result = await orch.process(
        "what have you logged today", language="en", intent_result=intent_result
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_ledger_query_below_confidence_threshold_falls_through(tmp_path: Path):
    """LEDGER_QUERY with confidence < 0.7 falls through to chat path (not local fast-path)."""
    from brain.device_ledger import DeviceLedger
    from brain.intent_parser import Intent, IntentResult

    db_file = str(tmp_path / "fallthrough.db")
    dl = DeviceLedger(db_path=db_file)
    await dl.init()

    chat_mock = AsyncMock(return_value="some chat response")
    claude_client = MagicMock()
    claude_client.chat = chat_mock
    claude_client.openclaw = None

    cfg_mock = MagicMock()
    cfg_mock.get_section.return_value = {
        "orchestrator_model": "claude-opus-4-5",
        "orchestrator_max_tokens": 150,
        "skip_orchestrator_on_clear_intent": True,
        "history_turns_for_orchestrator": 3,
    }
    cfg_mock.get.return_value = "Europe/Zurich"

    with patch("brain.orchestrator.get_config", return_value=cfg_mock):
        from brain.orchestrator import Orchestrator
        orch = Orchestrator(claude_client=claude_client, device_ledger=dl)

    # Low confidence intent — should fall through to chat.
    intent_result = IntentResult(
        intent=Intent.LEDGER_QUERY,
        confidence=0.3,  # below 0.7 threshold
        original_text="something",
        language="en",
    )
    await orch.process("something", language="en", intent_result=intent_result)
    # chat was called because the fast-path was skipped.
    chat_mock.assert_called_once()
