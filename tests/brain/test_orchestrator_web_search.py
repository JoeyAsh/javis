"""Tests for Orchestrator routing of WEB_SEARCH intents.

Verifies:
- Intent.WEB_SEARCH is present in _LOCAL_INTENTS.
- _intent_to_agent_name(WEB_SEARCH) returns "search".
- A "search" agent is registered under that key.
- Orchestrator.process() routes WEB_SEARCH through SearchAgent.
- Orchestrator.process_stream() routes WEB_SEARCH and emits a StreamChunk.
- Low-confidence WEB_SEARCH falls through to the chat path (not SearchAgent).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brain.agents.base import AgentResult
from brain.intent_parser import Intent, IntentResult
from brain.orchestrator import Orchestrator, _LOCAL_INTENTS, _intent_to_agent_name
from integrations.openclaw import AgentResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_openclaw_mock(text: str = "Web result.", error: str | None = None) -> MagicMock:
    """Return a mocked OpenClawClient that answers query_agent."""
    mock = MagicMock()
    mock.is_enabled = True
    mock.query_agent = AsyncMock(
        return_value=AgentResponse(
            text=text,
            session_id="jarvis-main",
            thinking_used=False,
            tool_calls=[],
            error=error,
        )
    )
    mock.get_offline_fallback_message = MagicMock(return_value="Offline fallback.")
    return mock


def _make_orchestrator(openclaw_text: str = "Web result.") -> tuple[Orchestrator, MagicMock]:
    """Return an Orchestrator with a mocked ClaudeClient backed by a mocked OpenClaw."""
    mock_openclaw = _make_openclaw_mock(text=openclaw_text)

    mock_claude = MagicMock()
    mock_claude.openclaw = mock_openclaw

    with patch("utils.config_loader.get_config") as mock_cfg:
        mock_cfg.return_value.get_section.return_value = {
            "orchestrator_model": "claude-opus-4-5",
            "subagent_model": "claude-sonnet-4-6",
            "orchestrator_max_tokens": 150,
            "action_max_tokens": 100,
            "skip_orchestrator_on_clear_intent": True,
            "history_turns_for_orchestrator": 3,
        }
        orch = Orchestrator(claude_client=mock_claude)

    return orch, mock_openclaw


def _web_search_intent(
    query: str = "population of Tokyo",
    confidence: float = 0.9,
    language: str = "en",
) -> IntentResult:
    """Build a WEB_SEARCH IntentResult."""
    return IntentResult(
        intent=Intent.WEB_SEARCH,
        confidence=confidence,
        params={"query": query},
        original_text=query,
        language=language,
    )


# ---------------------------------------------------------------------------
# Static assertions — no async needed
# ---------------------------------------------------------------------------


def test_web_search_in_local_intents():
    """Intent.WEB_SEARCH must be in _LOCAL_INTENTS."""
    assert Intent.WEB_SEARCH in _LOCAL_INTENTS


def test_intent_to_agent_name_returns_search():
    """_intent_to_agent_name maps WEB_SEARCH to 'search'."""
    assert _intent_to_agent_name(Intent.WEB_SEARCH) == "search"


def test_search_agent_registered_in_orchestrator():
    """Orchestrator wires a 'search' agent on construction."""
    orch, _ = _make_orchestrator()
    assert "search" in orch._agents
    from brain.agents.search_agent import SearchAgent
    assert isinstance(orch._agents["search"], SearchAgent)


def test_system_still_in_local_intents():
    """Intent.SYSTEM remains a local intent after Phase 4 (WEB_SEARCH addition unaffected)."""
    # Phase 4 (issue #76) removed PC_CONTROL and SMART_HOME from _LOCAL_INTENTS.
    # Only SYSTEM and WEB_SEARCH remain.  This test is the regression guard for
    # the WEB_SEARCH feature specifically.
    assert Intent.SYSTEM in _LOCAL_INTENTS
    # PC_CONTROL and SMART_HOME now fall through to OpenClaw → MCP tools.
    assert Intent.PC_CONTROL not in _LOCAL_INTENTS
    assert Intent.SMART_HOME not in _LOCAL_INTENTS


# ---------------------------------------------------------------------------
# Orchestrator.process() — WEB_SEARCH path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_web_search_routes_through_search_agent():
    """process() with WEB_SEARCH calls the search agent, not the chat agent."""
    orch, mock_openclaw = _make_orchestrator(openclaw_text="Tokyo has 14 million people.")

    search_calls: list[tuple] = []

    async def _search_run(text: str, params: dict, language: str) -> AgentResult:
        search_calls.append((text, params, language))
        return AgentResult(
            spoken_response="Tokyo has 14 million people.",
            success=True,
        )

    orch._agents["search"].run = _search_run  # type: ignore[method-assign]

    intent_result = _web_search_intent(query="population of Tokyo")
    result = await orch.process(
        "What is the population of Tokyo?",
        language="en",
        intent_result=intent_result,
    )

    assert len(search_calls) == 1
    assert result.spoken_response == "Tokyo has 14 million people."
    assert result.success is True


@pytest.mark.asyncio
async def test_process_web_search_passes_params_to_search_agent():
    """process() forwards intent_result.params to the search agent."""
    orch, _ = _make_orchestrator()

    received_params: list[dict] = []

    async def _search_run(text: str, params: dict, language: str) -> AgentResult:
        received_params.append(params)
        return AgentResult(spoken_response="OK", success=True)

    orch._agents["search"].run = _search_run  # type: ignore[method-assign]

    query = "speed of light"
    intent_result = _web_search_intent(query=query)
    await orch.process("search for speed of light", language="en", intent_result=intent_result)

    assert len(received_params) == 1
    assert received_params[0].get("query") == query


@pytest.mark.asyncio
async def test_process_web_search_does_not_call_chat_agent():
    """process() with WEB_SEARCH must NOT invoke the chat agent."""
    orch, _ = _make_orchestrator()

    chat_calls: list[tuple] = []

    async def _chat_run(text: str, params: dict, language: str) -> AgentResult:
        chat_calls.append((text, params, language))
        return AgentResult(spoken_response="Chat response", success=True)

    async def _search_run(text: str, params: dict, language: str) -> AgentResult:
        return AgentResult(spoken_response="Search response", success=True)

    orch._agents["chat"].run = _chat_run  # type: ignore[method-assign]
    orch._agents["search"].run = _search_run  # type: ignore[method-assign]

    intent_result = _web_search_intent()
    await orch.process("search for something", language="en", intent_result=intent_result)

    assert chat_calls == []


@pytest.mark.asyncio
async def test_process_web_search_german_language_forwarded():
    """process() forwards the language='de' argument to the search agent."""
    orch, _ = _make_orchestrator()

    received_languages: list[str] = []

    async def _search_run(text: str, params: dict, language: str) -> AgentResult:
        received_languages.append(language)
        return AgentResult(spoken_response="DE Ergebnis", success=True)

    orch._agents["search"].run = _search_run  # type: ignore[method-assign]

    intent_result = _web_search_intent(query="Wetter in München", language="de")
    await orch.process("such Wetter in München", language="de", intent_result=intent_result)

    assert received_languages == ["de"]


@pytest.mark.asyncio
async def test_process_low_confidence_web_search_falls_through_to_chat():
    """WEB_SEARCH with confidence < 0.7 falls through to the chat/OpenClaw path."""
    orch, mock_openclaw = _make_orchestrator()

    chat_calls: list[tuple] = []

    async def _chat_run(text: str, params: dict, language: str) -> AgentResult:
        chat_calls.append((text, params, language))
        return AgentResult(spoken_response="Chatted response", success=True)

    orch._agents["chat"].run = _chat_run  # type: ignore[method-assign]

    # Confidence below the 0.7 threshold
    low_conf_intent = IntentResult(
        intent=Intent.WEB_SEARCH,
        confidence=0.4,
        params={"query": "something"},
        original_text="something",
        language="en",
    )
    await orch.process("something", language="en", intent_result=low_conf_intent)

    assert len(chat_calls) == 1


# ---------------------------------------------------------------------------
# Orchestrator.process_stream() — WEB_SEARCH path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_stream_web_search_emits_final_chunk():
    """process_stream() with WEB_SEARCH emits exactly one StreamChunk(type='final')."""
    from integrations.openclaw.ws_client import StreamChunk

    orch, _ = _make_orchestrator()

    async def _search_run(text: str, params: dict, language: str) -> AgentResult:
        return AgentResult(
            spoken_response="Tokyo has about 14 million people.",
            success=True,
        )

    orch._agents["search"].run = _search_run  # type: ignore[method-assign]

    intent_result = _web_search_intent(query="population of Tokyo")

    chunks: list[StreamChunk] = []
    async for chunk in orch.process_stream(
        "population of Tokyo", language="en", intent_result=intent_result
    ):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert chunks[0].type == "final"
    assert "14 million" in chunks[0].full_text


@pytest.mark.asyncio
async def test_process_stream_web_search_chunk_run_id_is_local():
    """The synthetic chunk from a local-agent dispatch has run_id='local'."""
    orch, _ = _make_orchestrator()

    async def _search_run(text: str, params: dict, language: str) -> AgentResult:
        return AgentResult(spoken_response="Some answer.", success=True)

    orch._agents["search"].run = _search_run  # type: ignore[method-assign]

    intent_result = _web_search_intent()
    chunks = [
        chunk
        async for chunk in orch.process_stream(
            "search query", language="en", intent_result=intent_result
        )
    ]

    assert chunks[0].run_id == "local"


@pytest.mark.asyncio
async def test_process_stream_web_search_does_not_call_chat_agent():
    """process_stream() with WEB_SEARCH must NOT call the chat agent."""
    orch, _ = _make_orchestrator()

    chat_calls: list = []

    async def _chat_run(text: str, params: dict, language: str) -> AgentResult:
        chat_calls.append((text, params, language))
        return AgentResult(spoken_response="Chat", success=True)

    async def _search_run(text: str, params: dict, language: str) -> AgentResult:
        return AgentResult(spoken_response="Search", success=True)

    orch._agents["chat"].run = _chat_run  # type: ignore[method-assign]
    orch._agents["search"].run = _search_run  # type: ignore[method-assign]

    intent_result = _web_search_intent()
    _ = [
        c
        async for c in orch.process_stream(
            "search query", language="en", intent_result=intent_result
        )
    ]

    assert chat_calls == []


@pytest.mark.asyncio
async def test_process_stream_web_search_new_text_matches_full_text():
    """The synthetic StreamChunk has new_text == full_text (single-shot response)."""
    orch, _ = _make_orchestrator()
    answer = "Python was created by Guido van Rossum."

    async def _search_run(text: str, params: dict, language: str) -> AgentResult:
        return AgentResult(spoken_response=answer, success=True)

    orch._agents["search"].run = _search_run  # type: ignore[method-assign]

    intent_result = _web_search_intent(query="who created Python")
    chunks = [
        c
        async for c in orch.process_stream(
            "who created Python", language="en", intent_result=intent_result
        )
    ]

    assert chunks[0].new_text == answer
    assert chunks[0].full_text == answer
