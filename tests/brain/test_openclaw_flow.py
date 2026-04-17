"""End-to-end integration tests for the OpenClaw-backed LLM flow.

These tests exercise the public ``ClaudeClient`` surface that the voice
pipeline (``ChatAgent``, ``Orchestrator``) consumes, with a mocked
OpenClaw client. The goal is to catch regressions where:

- A turn stops reaching ``query_agent`` (e.g. refactor to a different
  backend).
- The main conversational session id drifts from the configured
  ``config.openclaw.session_id`` (which would silently fragment memory).
- Offline fallback paths disappear.

No subprocesses or network I/O.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from brain.agents.chat_agent import ChatAgent
from brain.claude_client import ClaudeClient
from brain.memory_legacy import ConversationMemory
from integrations.openclaw import AgentResponse


def _response(text: str, session_id: str = "jarvis-main", error: str | None = None) -> AgentResponse:
    """Build a minimal ``AgentResponse`` for mocking."""
    return AgentResponse(
        text=text,
        session_id=session_id,
        thinking_used=False,
        tool_calls=[],
        error=error,
    )


@pytest.fixture
def mock_openclaw() -> MagicMock:
    """Mocked ``OpenClawClient`` that records every call."""
    mock = MagicMock()
    mock.gateway_url = "http://127.0.0.1:18789"
    mock.session_id = "jarvis-main"
    mock.initialize = AsyncMock(return_value=None)
    mock.close = AsyncMock(return_value=None)
    mock.query_agent = AsyncMock(return_value=_response("Quite so, sir."))
    mock.get_offline_fallback_message = MagicMock(
        side_effect=lambda lang: (
            "Sir, ich habe Schwierigkeiten, das OpenClaw-Gateway zu erreichen."
            if lang == "de"
            else "Sir, I'm having trouble reaching the OpenClaw gateway."
        )
    )
    return mock


@pytest_asyncio.fixture
async def claude_client(mock_openclaw) -> ClaudeClient:
    """Real ``ClaudeClient`` with a mocked OpenClaw backend."""
    client = ClaudeClient(openclaw_client=mock_openclaw)
    await client.initialize()
    return client


class TestTurnRoundTrip:
    """A full voice turn lands on ``query_agent`` and the text comes back."""

    @pytest.mark.asyncio
    async def test_chat_agent_returns_openclaw_text(
        self, claude_client, mock_openclaw
    ):
        """ChatAgent.run() → ClaudeClient.chat() → OpenClaw → spoken response."""
        mock_openclaw.query_agent.return_value = _response(
            text="All systems nominal, sir."
        )

        agent = ChatAgent(
            claude_client=claude_client,
            memory=ConversationMemory(max_turns=5),
        )

        result = await agent.run(
            task="Status report please.",
            params={},
            language="en",
        )

        assert result.success is True
        assert result.spoken_response == "All systems nominal, sir."
        mock_openclaw.query_agent.assert_awaited_once()


class TestOfflineFallback:
    """OpenClaw errors collapse to a localised spoken fallback."""

    @pytest.mark.asyncio
    async def test_chat_returns_german_fallback_on_error(
        self, claude_client, mock_openclaw
    ):
        """When OpenClaw reports an error, the DE fallback is spoken."""
        mock_openclaw.query_agent.return_value = _response(
            text="",
            error="gateway unreachable",
        )

        response = await claude_client.chat("Hallo JARVIS", language="de")

        assert "OpenClaw-Gateway" in response
        # The HUD remains up; nothing was raised.

    @pytest.mark.asyncio
    async def test_chat_returns_english_fallback_on_error(
        self, claude_client, mock_openclaw
    ):
        """English fallback is returned for English turns."""
        mock_openclaw.query_agent.return_value = _response(
            text="",
            error="gateway unreachable",
        )

        response = await claude_client.chat("Hello JARVIS", language="en")

        assert "OpenClaw gateway" in response

    @pytest.mark.asyncio
    async def test_chat_agent_survives_openclaw_exception(
        self, claude_client, mock_openclaw
    ):
        """Exceptions from OpenClaw do not crash the ChatAgent."""
        mock_openclaw.query_agent.side_effect = RuntimeError("boom")

        agent = ChatAgent(
            claude_client=claude_client,
            memory=ConversationMemory(max_turns=5),
        )

        result = await agent.run(
            task="Still there?",
            params={},
            language="en",
        )

        # Agent returns a structured failure rather than propagating.
        assert result.success is False
        assert "boom" in str(result.data.get("error", ""))


class TestSessionIdPinning:
    """Conversational turns MUST target the main session id; utility calls MUST NOT."""

    @pytest.mark.asyncio
    async def test_chat_uses_default_session(
        self, claude_client, mock_openclaw
    ):
        """chat() leaves ``session_id`` unset so OpenClaw uses its default.

        The OpenClaw client resolves ``None`` to ``config.openclaw.session_id``
        (default ``"jarvis-main"``). This is the whole point of routing
        conversational turns through OpenClaw — persistent memory keyed on
        that session.
        """
        await claude_client.chat("Hello", language="en")

        call = mock_openclaw.query_agent.await_args
        assert call.kwargs.get("session_id") is None

    @pytest.mark.asyncio
    async def test_complete_uses_utility_session(
        self, claude_client, mock_openclaw
    ):
        """Utility calls carry a distinct, ephemeral session id.

        Routing decisions, JSON extraction and search summarisation must
        not pollute the main conversation history.
        """
        await claude_client.complete(
            prompt="route this",
            system_prompt="you are a router",
        )

        call = mock_openclaw.query_agent.await_args
        session = call.kwargs.get("session_id") or ""
        assert session.startswith("jarvis-util-")
        assert session != "jarvis-main"

    @pytest.mark.asyncio
    async def test_json_uses_utility_session(
        self, claude_client, mock_openclaw
    ):
        """chat_with_json shares the utility session policy."""
        mock_openclaw.query_agent.return_value = _response(text='{"ok": true}')

        await claude_client.chat_with_json(
            "give me JSON",
            system_prompt="return JSON",
        )

        call = mock_openclaw.query_agent.await_args
        session = call.kwargs.get("session_id") or ""
        assert session.startswith("jarvis-util-")

    @pytest.mark.asyncio
    async def test_openclaw_client_reads_configured_session_id(
        self, mock_openclaw
    ):
        """Sanity check — the client surfaces the pinned session id.

        The ClaudeClient relies on OpenClaw's ``session_id`` property
        staying in sync with ``config.openclaw.session_id``.
        """
        mock_openclaw.session_id = "jarvis-main"
        client = ClaudeClient(openclaw_client=mock_openclaw)
        await client.initialize()

        assert client.openclaw is mock_openclaw
        assert client.openclaw.session_id == "jarvis-main"
