"""Tests verifying Orchestrator state after Phase 4 (issue #76).

Phase 4 removes PcAgent and SmartHomeAgent from the orchestrator and instead
routes PC_CONTROL and SMART_HOME intents through the OpenClaw chat path, which
calls the corresponding MCP tools.

This test file verifies the new contracts:
- Intent.PC_CONTROL is NOT in _LOCAL_INTENTS.
- Intent.SMART_HOME is NOT in _LOCAL_INTENTS.
- Intent.SYSTEM and Intent.WEB_SEARCH remain in _LOCAL_INTENTS (regression guard).
- Orchestrator._agents does NOT have 'pc' or 'smart_home' keys.
- Orchestrator._agents DOES have 'chat', 'search', and 'system' keys.
- process() with Intent.PC_CONTROL dispatches to the chat agent (OpenClaw path).
- process() with Intent.SMART_HOME dispatches to the chat agent (OpenClaw path).
- _intent_to_agent_name does not map PC_CONTROL / SMART_HOME to local agents.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brain.agents.base import AgentResult
from brain.intent_parser import Intent, IntentResult
from brain.orchestrator import Orchestrator, _LOCAL_INTENTS, _intent_to_agent_name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orchestrator() -> Orchestrator:
    """Construct a minimal Orchestrator with all external deps mocked."""
    from brain.claude_client import ClaudeClient

    claude_mock = MagicMock(spec=ClaudeClient)
    claude_mock.openclaw = None

    with patch("brain.orchestrator.SystemAgent"), patch("brain.orchestrator.ChatAgent"), patch(
        "brain.orchestrator.SearchAgent"
    ):
        orch = Orchestrator(claude_client=claude_mock)

    return orch


def _intent_result(intent: Intent, confidence: float = 0.95) -> IntentResult:
    return IntentResult(
        intent=intent,
        confidence=confidence,
        params={},
        original_text="test utterance",
        language="en",
    )


# ---------------------------------------------------------------------------
# _LOCAL_INTENTS membership
# ---------------------------------------------------------------------------


def test_pc_control_not_in_local_intents():
    """Intent.PC_CONTROL must NOT be in _LOCAL_INTENTS after Phase 4."""
    assert Intent.PC_CONTROL not in _LOCAL_INTENTS, (
        "PC_CONTROL was found in _LOCAL_INTENTS — it should fall through to OpenClaw/MCP"
    )


def test_smart_home_not_in_local_intents():
    """Intent.SMART_HOME must NOT be in _LOCAL_INTENTS after Phase 4."""
    assert Intent.SMART_HOME not in _LOCAL_INTENTS, (
        "SMART_HOME was found in _LOCAL_INTENTS — it should fall through to OpenClaw/MCP"
    )


def test_system_still_in_local_intents():
    """Intent.SYSTEM must still be in _LOCAL_INTENTS (regression guard)."""
    assert Intent.SYSTEM in _LOCAL_INTENTS


def test_web_search_still_in_local_intents():
    """Intent.WEB_SEARCH must still be in _LOCAL_INTENTS (regression guard)."""
    assert Intent.WEB_SEARCH in _LOCAL_INTENTS


def test_local_intents_exactly_system_and_web_search():
    """_LOCAL_INTENTS contains exactly {SYSTEM, WEB_SEARCH} and nothing else."""
    assert _LOCAL_INTENTS == frozenset({Intent.SYSTEM, Intent.WEB_SEARCH}), (
        f"Unexpected _LOCAL_INTENTS contents: {_LOCAL_INTENTS}"
    )


# ---------------------------------------------------------------------------
# Orchestrator._agents dict
# ---------------------------------------------------------------------------


def test_orchestrator_agents_does_not_contain_pc_key():
    """Orchestrator._agents must not have a 'pc' key after Phase 4."""
    orch = _make_orchestrator()
    assert "pc" not in orch._agents, (
        "Found 'pc' key in _agents — PcAgent should have been removed"
    )


def test_orchestrator_agents_does_not_contain_smart_home_key():
    """Orchestrator._agents must not have a 'smart_home' key after Phase 4."""
    orch = _make_orchestrator()
    assert "smart_home" not in orch._agents, (
        "Found 'smart_home' key in _agents — SmartHomeAgent should have been removed"
    )


def test_orchestrator_agents_contains_chat_key():
    """Orchestrator._agents must contain 'chat' (ChatAgent for OpenClaw path)."""
    orch = _make_orchestrator()
    assert "chat" in orch._agents


def test_orchestrator_agents_contains_search_key():
    """Orchestrator._agents must contain 'search' (SearchAgent for WEB_SEARCH)."""
    orch = _make_orchestrator()
    assert "search" in orch._agents


def test_orchestrator_agents_contains_system_key():
    """Orchestrator._agents must contain 'system' (SystemAgent)."""
    orch = _make_orchestrator()
    assert "system" in orch._agents


def test_orchestrator_agents_has_exactly_three_keys():
    """Orchestrator._agents has exactly {chat, search, system} after Phase 4."""
    orch = _make_orchestrator()
    assert set(orch._agents.keys()) == {"chat", "search", "system"}, (
        f"Unexpected _agents keys: {set(orch._agents.keys())}"
    )


# ---------------------------------------------------------------------------
# _intent_to_agent_name
# ---------------------------------------------------------------------------


def test_intent_to_agent_name_pc_control_returns_chat():
    """_intent_to_agent_name(PC_CONTROL) returns 'chat' (falls through to OpenClaw)."""
    assert _intent_to_agent_name(Intent.PC_CONTROL) == "chat"


def test_intent_to_agent_name_smart_home_returns_chat():
    """_intent_to_agent_name(SMART_HOME) returns 'chat' (falls through to OpenClaw)."""
    assert _intent_to_agent_name(Intent.SMART_HOME) == "chat"


def test_intent_to_agent_name_system_returns_system():
    """_intent_to_agent_name(SYSTEM) still returns 'system'."""
    assert _intent_to_agent_name(Intent.SYSTEM) == "system"


def test_intent_to_agent_name_web_search_returns_search():
    """_intent_to_agent_name(WEB_SEARCH) still returns 'search'."""
    assert _intent_to_agent_name(Intent.WEB_SEARCH) == "search"


# ---------------------------------------------------------------------------
# Orchestrator.process() — PC_CONTROL routes to chat path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_pc_control_dispatches_to_chat_agent():
    """process() with Intent.PC_CONTROL (high confidence) dispatches to the chat agent."""
    from brain.claude_client import ClaudeClient

    claude_mock = MagicMock(spec=ClaudeClient)
    claude_mock.openclaw = None

    chat_run_calls: list[tuple] = []

    async def _chat_run(text: str, params: dict, language: str) -> AgentResult:
        chat_run_calls.append((text, params, language))
        return AgentResult(spoken_response="Opening Chrome.", success=True)

    mock_chat_agent = MagicMock()
    mock_chat_agent.run = _chat_run

    mock_system_agent = MagicMock()
    mock_search_agent = MagicMock()

    with patch("brain.orchestrator.ChatAgent", return_value=mock_chat_agent), patch(
        "brain.orchestrator.SystemAgent", return_value=mock_system_agent
    ), patch("brain.orchestrator.SearchAgent", return_value=mock_search_agent):
        orch = Orchestrator(claude_client=claude_mock)

    intent_result = _intent_result(Intent.PC_CONTROL, confidence=0.95)
    result = await orch.process(
        "Open Chrome", language="en", intent_result=intent_result
    )

    assert len(chat_run_calls) == 1, (
        "Expected chat agent to be called once for PC_CONTROL"
    )
    assert result.spoken_response == "Opening Chrome."
    assert result.success is True


@pytest.mark.asyncio
async def test_process_smart_home_dispatches_to_chat_agent():
    """process() with Intent.SMART_HOME (high confidence) dispatches to the chat agent."""
    from brain.claude_client import ClaudeClient

    claude_mock = MagicMock(spec=ClaudeClient)
    claude_mock.openclaw = None

    chat_run_calls: list[tuple] = []

    async def _chat_run(text: str, params: dict, language: str) -> AgentResult:
        chat_run_calls.append((text, params, language))
        return AgentResult(spoken_response="Turning off the lights.", success=True)

    mock_chat_agent = MagicMock()
    mock_chat_agent.run = _chat_run

    mock_system_agent = MagicMock()
    mock_search_agent = MagicMock()

    with patch("brain.orchestrator.ChatAgent", return_value=mock_chat_agent), patch(
        "brain.orchestrator.SystemAgent", return_value=mock_system_agent
    ), patch("brain.orchestrator.SearchAgent", return_value=mock_search_agent):
        orch = Orchestrator(claude_client=claude_mock)

    intent_result = _intent_result(Intent.SMART_HOME, confidence=0.90)
    result = await orch.process(
        "Turn off the lights", language="en", intent_result=intent_result
    )

    assert len(chat_run_calls) == 1, (
        "Expected chat agent to be called once for SMART_HOME"
    )
    assert result.spoken_response == "Turning off the lights."


@pytest.mark.asyncio
async def test_process_pc_control_does_not_call_system_or_search_agent():
    """process() with PC_CONTROL never calls the system or search agents."""
    from brain.claude_client import ClaudeClient

    claude_mock = MagicMock(spec=ClaudeClient)
    claude_mock.openclaw = None

    async def _chat_run(text: str, params: dict, language: str) -> AgentResult:
        return AgentResult(spoken_response="Done.", success=True)

    mock_chat_agent = MagicMock()
    mock_chat_agent.run = _chat_run
    mock_system_agent = MagicMock()
    mock_search_agent = MagicMock()

    with patch("brain.orchestrator.ChatAgent", return_value=mock_chat_agent), patch(
        "brain.orchestrator.SystemAgent", return_value=mock_system_agent
    ), patch("brain.orchestrator.SearchAgent", return_value=mock_search_agent):
        orch = Orchestrator(claude_client=claude_mock)

    await orch.process("open spotify", language="en", intent_result=_intent_result(Intent.PC_CONTROL))

    mock_system_agent.run.assert_not_called()
    mock_search_agent.run.assert_not_called()


@pytest.mark.asyncio
async def test_process_pc_control_low_confidence_also_uses_chat_agent():
    """process() with PC_CONTROL below threshold still uses chat (not a local agent)."""
    from brain.claude_client import ClaudeClient

    claude_mock = MagicMock(spec=ClaudeClient)
    claude_mock.openclaw = None

    chat_calls: list = []

    async def _chat_run(text: str, params: dict, language: str) -> AgentResult:
        chat_calls.append(text)
        return AgentResult(spoken_response="ok", success=True)

    mock_chat_agent = MagicMock()
    mock_chat_agent.run = _chat_run

    with patch("brain.orchestrator.ChatAgent", return_value=mock_chat_agent), patch(
        "brain.orchestrator.SystemAgent"
    ), patch("brain.orchestrator.SearchAgent"):
        orch = Orchestrator(claude_client=claude_mock)

    # Low confidence — below the 0.7 threshold, so it always goes to chat anyway.
    low_conf = _intent_result(Intent.PC_CONTROL, confidence=0.5)
    await orch.process("open something", language="en", intent_result=low_conf)

    assert len(chat_calls) == 1
