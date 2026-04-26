"""Tests for Orchestrator Spotify extended intent routing (issue #58).

Verifies:
- The three new Spotify intents are in _LOCAL_INTENTS.
- All three intents dispatch to SpotifyAgent with the intent name as task.
- set_spotify_client() wires SpotifyAgent into _agents['spotify'].
- Missing spotify agent falls back gracefully to chat path.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_claude() -> MagicMock:
    mock = MagicMock()
    mock.openclaw = None
    return mock


def _make_mock_spotify_client() -> MagicMock:
    mock = MagicMock()
    mock.is_authenticated.return_value = True
    return mock


# ---------------------------------------------------------------------------
# _LOCAL_INTENTS — new Spotify intents are present
# ---------------------------------------------------------------------------


def test_spotify_search_in_local_intents():
    """Intent.SPOTIFY_SEARCH is in _LOCAL_INTENTS."""
    from brain.intent_parser import Intent
    from brain.orchestrator import _LOCAL_INTENTS

    assert Intent.SPOTIFY_SEARCH in _LOCAL_INTENTS


def test_spotify_queue_in_local_intents():
    """Intent.SPOTIFY_QUEUE is in _LOCAL_INTENTS."""
    from brain.intent_parser import Intent
    from brain.orchestrator import _LOCAL_INTENTS

    assert Intent.SPOTIFY_QUEUE in _LOCAL_INTENTS


def test_spotify_play_context_in_local_intents():
    """Intent.SPOTIFY_PLAY_CONTEXT is in _LOCAL_INTENTS."""
    from brain.intent_parser import Intent
    from brain.orchestrator import _LOCAL_INTENTS

    assert Intent.SPOTIFY_PLAY_CONTEXT in _LOCAL_INTENTS


def test_old_transport_intents_not_in_local_intents():
    """SPOTIFY_PLAY/PAUSE/NEXT/PREV/VOLUME are NOT in _LOCAL_INTENTS (fall to OpenClaw)."""
    from brain.intent_parser import Intent
    from brain.orchestrator import _LOCAL_INTENTS

    for intent in (
        Intent.SPOTIFY_PLAY,
        Intent.SPOTIFY_PAUSE,
        Intent.SPOTIFY_NEXT,
        Intent.SPOTIFY_PREV,
        Intent.SPOTIFY_VOLUME,
    ):
        assert intent not in _LOCAL_INTENTS, f"{intent.value} must not be in _LOCAL_INTENTS"


# ---------------------------------------------------------------------------
# _intent_to_agent_name
# ---------------------------------------------------------------------------


def test_spotify_search_maps_to_spotify_agent():
    """_intent_to_agent_name(SPOTIFY_SEARCH) → 'spotify'."""
    from brain.intent_parser import Intent
    from brain.orchestrator import _intent_to_agent_name

    assert _intent_to_agent_name(Intent.SPOTIFY_SEARCH) == "spotify"


def test_spotify_queue_maps_to_spotify_agent():
    """_intent_to_agent_name(SPOTIFY_QUEUE) → 'spotify'."""
    from brain.intent_parser import Intent
    from brain.orchestrator import _intent_to_agent_name

    assert _intent_to_agent_name(Intent.SPOTIFY_QUEUE) == "spotify"


def test_spotify_play_context_maps_to_spotify_agent():
    """_intent_to_agent_name(SPOTIFY_PLAY_CONTEXT) → 'spotify'."""
    from brain.intent_parser import Intent
    from brain.orchestrator import _intent_to_agent_name

    assert _intent_to_agent_name(Intent.SPOTIFY_PLAY_CONTEXT) == "spotify"


# ---------------------------------------------------------------------------
# Orchestrator construction — SpotifyAgent wired when spotify_client provided
# ---------------------------------------------------------------------------


def test_orchestrator_wires_spotify_agent_on_construction():
    """Orchestrator._agents['spotify'] is a SpotifyAgent when spotify_client provided."""
    from brain.agents.spotify_agent import SpotifyAgent
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    mock_spotify = _make_mock_spotify_client()

    orch = Orchestrator(claude_client=mock_claude, spotify_client=mock_spotify)

    assert "spotify" in orch._agents
    assert isinstance(orch._agents["spotify"], SpotifyAgent)


def test_orchestrator_no_spotify_agent_without_client():
    """Orchestrator._agents has no 'spotify' key when spotify_client=None."""
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    orch = Orchestrator(claude_client=mock_claude, spotify_client=None)

    assert "spotify" not in orch._agents


# ---------------------------------------------------------------------------
# set_spotify_client — late binding
# ---------------------------------------------------------------------------


def test_set_spotify_client_wires_agent():
    """set_spotify_client() adds SpotifyAgent to _agents['spotify']."""
    from brain.agents.spotify_agent import SpotifyAgent
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    orch = Orchestrator(claude_client=mock_claude, spotify_client=None)
    assert "spotify" not in orch._agents

    mock_spotify = _make_mock_spotify_client()
    orch.set_spotify_client(mock_spotify)

    assert "spotify" in orch._agents
    assert isinstance(orch._agents["spotify"], SpotifyAgent)


def test_set_spotify_client_none_removes_agent():
    """set_spotify_client(None) removes SpotifyAgent from _agents."""
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    mock_spotify = _make_mock_spotify_client()
    orch = Orchestrator(claude_client=mock_claude, spotify_client=mock_spotify)
    assert "spotify" in orch._agents

    orch.set_spotify_client(None)

    assert "spotify" not in orch._agents


# ---------------------------------------------------------------------------
# process() — dispatch to SpotifyAgent with intent name as task arg
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_spotify_search_dispatches_to_spotify_agent():
    """process() with SPOTIFY_SEARCH dispatches to SpotifyAgent with task='SPOTIFY_SEARCH'."""
    from brain.agents.base import AgentResult
    from brain.intent_parser import Intent, IntentResult
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    mock_spotify = _make_mock_spotify_client()

    orch = Orchestrator(claude_client=mock_claude, spotify_client=mock_spotify)

    agent_calls: list[tuple] = []

    async def _fake_run(task: str, params: dict, language: str) -> AgentResult:
        agent_calls.append((task, params, language))
        return AgentResult(spoken_response="Playing Song.", success=True)

    orch._agents["spotify"].run = _fake_run  # type: ignore[method-assign]

    intent_result = IntentResult(
        intent=Intent.SPOTIFY_SEARCH,
        confidence=0.9,
        params={"query": "Midnight City"},
        original_text="search for Midnight City on spotify",
        language="en",
    )

    result = await orch.process("search for Midnight City on spotify", "en", intent_result)

    assert len(agent_calls) == 1
    task, params, lang = agent_calls[0]
    assert task == "SPOTIFY_SEARCH"
    assert params["query"] == "Midnight City"
    assert lang == "en"
    assert result.spoken_response == "Playing Song."


@pytest.mark.asyncio
async def test_process_spotify_queue_dispatches_to_spotify_agent():
    """process() with SPOTIFY_QUEUE dispatches to SpotifyAgent with task='SPOTIFY_QUEUE'."""
    from brain.agents.base import AgentResult
    from brain.intent_parser import Intent, IntentResult
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    mock_spotify = _make_mock_spotify_client()

    orch = Orchestrator(claude_client=mock_claude, spotify_client=mock_spotify)

    agent_calls: list[tuple] = []

    async def _fake_run(task: str, params: dict, language: str) -> AgentResult:
        agent_calls.append((task, params, language))
        return AgentResult(spoken_response="Added to queue.", success=True)

    orch._agents["spotify"].run = _fake_run  # type: ignore[method-assign]

    intent_result = IntentResult(
        intent=Intent.SPOTIFY_QUEUE,
        confidence=0.9,
        params={"query": "Begin Again"},
        original_text="add Begin Again to the queue",
        language="en",
    )

    await orch.process("add Begin Again to the queue", "en", intent_result)

    assert agent_calls[0][0] == "SPOTIFY_QUEUE"


@pytest.mark.asyncio
async def test_process_spotify_play_context_dispatches_to_spotify_agent():
    """process() with SPOTIFY_PLAY_CONTEXT dispatches task='SPOTIFY_PLAY_CONTEXT'."""
    from brain.agents.base import AgentResult
    from brain.intent_parser import Intent, IntentResult
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    mock_spotify = _make_mock_spotify_client()

    orch = Orchestrator(claude_client=mock_claude, spotify_client=mock_spotify)

    agent_calls: list[tuple] = []

    async def _fake_run(task: str, params: dict, language: str) -> AgentResult:
        agent_calls.append((task, params, language))
        return AgentResult(spoken_response="Playing playlist.", success=True)

    orch._agents["spotify"].run = _fake_run  # type: ignore[method-assign]

    intent_result = IntentResult(
        intent=Intent.SPOTIFY_PLAY_CONTEXT,
        confidence=0.9,
        params={"query": "Coding Sessions"},
        original_text="play the playlist Coding Sessions",
        language="en",
    )

    await orch.process("play the playlist Coding Sessions", "en", intent_result)

    assert agent_calls[0][0] == "SPOTIFY_PLAY_CONTEXT"


@pytest.mark.asyncio
async def test_process_spotify_search_without_agent_falls_back_to_chat():
    """SPOTIFY_SEARCH without wired SpotifyAgent falls back to the chat agent."""
    from brain.agents.base import AgentResult
    from brain.intent_parser import Intent, IntentResult
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    orch = Orchestrator(claude_client=mock_claude, spotify_client=None)

    chat_calls: list[tuple] = []

    async def _chat_run(text: str, params: dict, language: str) -> AgentResult:
        chat_calls.append((text, params, language))
        return AgentResult(spoken_response="Chat response", success=True)

    orch._agents["chat"].run = _chat_run  # type: ignore[method-assign]

    intent_result = IntentResult(
        intent=Intent.SPOTIFY_SEARCH,
        confidence=0.9,
        params={"query": "test"},
        original_text="search for test on spotify",
        language="en",
    )

    result = await orch.process("search for test on spotify", "en", intent_result)

    # With no spotify agent wired, falls through to chat path.
    assert len(chat_calls) == 1
    assert result.spoken_response == "Chat response"


# ---------------------------------------------------------------------------
# DE language — intent name still passed in UPPER_CASE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_de_spotify_search_task_is_uppercased():
    """SpotifyAgent receives task in UPPER_CASE even for DE utterances."""
    from brain.agents.base import AgentResult
    from brain.intent_parser import Intent, IntentResult
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    mock_spotify = _make_mock_spotify_client()

    orch = Orchestrator(claude_client=mock_claude, spotify_client=mock_spotify)

    agent_calls: list[tuple] = []

    async def _fake_run(task: str, params: dict, language: str) -> AgentResult:
        agent_calls.append((task, params, language))
        return AgentResult(spoken_response="Spiele Song.", success=True)

    orch._agents["spotify"].run = _fake_run  # type: ignore[method-assign]

    intent_result = IntentResult(
        intent=Intent.SPOTIFY_SEARCH,
        confidence=0.9,
        params={"query": "Midnight City"},
        original_text="suche Midnight City auf Spotify",
        language="de",
    )

    await orch.process("suche Midnight City auf Spotify", "de", intent_result)

    assert agent_calls[0][0] == "SPOTIFY_SEARCH"
    assert agent_calls[0][2] == "de"


# ---------------------------------------------------------------------------
# set_preferred_spotify_device (issue #84)
# ---------------------------------------------------------------------------


def test_set_preferred_spotify_device_forwards_to_agent():
    """set_preferred_spotify_device('abc') forwards to SpotifyAgent.set_preferred_device."""
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    mock_spotify = _make_mock_spotify_client()

    orch = Orchestrator(claude_client=mock_claude, spotify_client=mock_spotify)
    agent = orch._agents["spotify"]

    orch.set_preferred_spotify_device("abc-device-id")

    assert agent.preferred_device_id == "abc-device-id"


def test_set_preferred_spotify_device_none_clears_agent():
    """set_preferred_spotify_device(None) clears SpotifyAgent.preferred_device_id."""
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    mock_spotify = _make_mock_spotify_client()

    orch = Orchestrator(claude_client=mock_claude, spotify_client=mock_spotify)
    # First set a value, then clear it.
    orch.set_preferred_spotify_device("abc-device-id")
    orch.set_preferred_spotify_device(None)

    assert orch._agents["spotify"].preferred_device_id is None


def test_set_preferred_spotify_device_no_op_without_agent():
    """set_preferred_spotify_device does not raise when SpotifyAgent is not wired."""
    from brain.orchestrator import Orchestrator

    mock_claude = _make_mock_claude()
    orch = Orchestrator(claude_client=mock_claude, spotify_client=None)
    assert "spotify" not in orch._agents

    # Must not raise.
    orch.set_preferred_spotify_device("some-id")
