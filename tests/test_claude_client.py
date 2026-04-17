"""Tests for the LLM client module (OpenClaw-backed).

The legacy Anthropic SDK path was retired in favour of OpenClaw's agent
runtime (see ``.tmp/features/openclaw-integration.md``). These tests
cover the new behaviour:

- ``chat`` routes through ``OpenClawClient.query_agent`` on the main
  session id (persona + memory owned by OpenClaw).
- ``complete`` and ``chat_with_json`` use ephemeral utility session ids
  so they don't pollute conversational memory.
- Errors surface as localised spoken fallbacks.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from integrations.openclaw import AgentResponse
from src.brain.claude_client import (
    FALLBACK_RESPONSES,
    JARVIS_SYSTEM_PROMPT,
    ClaudeClient,
    create_claude_client,
)


def _make_response(
    text: str = "Hello, sir. How may I assist you?",
    session_id: str = "jarvis-main",
    error: str | None = None,
) -> AgentResponse:
    """Helper — build a plausible ``AgentResponse`` for mocking."""
    return AgentResponse(
        text=text,
        session_id=session_id,
        thinking_used=False,
        tool_calls=[],
        error=error,
    )


@pytest.fixture
def mock_openclaw():
    """Return a mocked ``OpenClawClient`` with a stub ``query_agent``."""
    mock = MagicMock()
    mock.gateway_url = "http://127.0.0.1:18789"
    mock.session_id = "jarvis-main"
    mock.initialize = AsyncMock(return_value=None)
    mock.close = AsyncMock(return_value=None)
    mock.query_agent = AsyncMock(return_value=_make_response())
    mock.get_offline_fallback_message = MagicMock(
        side_effect=lambda lang: (
            "Sir, ich habe Schwierigkeiten, das OpenClaw-Gateway zu erreichen."
            if lang == "de"
            else "Sir, I'm having trouble reaching the OpenClaw gateway."
        )
    )
    return mock


@pytest_asyncio.fixture
async def claude_client(mock_openclaw):
    """Return a ready-to-use :class:`ClaudeClient` with mocked OpenClaw."""
    client = ClaudeClient(
        api_key="ignored",
        model="claude-sonnet-4-6",
        max_tokens=300,
        temperature=0.7,
        openclaw_client=mock_openclaw,
    )
    await client.initialize()
    return client


class TestClaudeClientChat:
    """Tests for the conversational ``chat`` path."""

    @pytest.mark.asyncio
    async def test_chat_calls_openclaw_query_agent(
        self, claude_client, mock_openclaw
    ):
        """chat() delegates to OpenClaw's agent runtime."""
        await claude_client.chat("Hello", language="en")

        mock_openclaw.query_agent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_returns_openclaw_text(
        self, claude_client, mock_openclaw
    ):
        """chat() returns the agent text verbatim."""
        mock_openclaw.query_agent.return_value = _make_response(
            text="Quite so, sir."
        )

        response = await claude_client.chat("Hello", language="en")

        assert response == "Quite so, sir."

    @pytest.mark.asyncio
    async def test_chat_uses_main_session_by_default(
        self, claude_client, mock_openclaw
    ):
        """Conversational turns travel on the main session (None -> default)."""
        await claude_client.chat("Hello", language="en")

        call = mock_openclaw.query_agent.await_args
        assert call.kwargs.get("session_id") is None

    @pytest.mark.asyncio
    async def test_chat_injects_language_hint_de(
        self, claude_client, mock_openclaw
    ):
        """German requests are hinted so OpenClaw mirrors the language."""
        await claude_client.chat("Hallo", language="de")

        call = mock_openclaw.query_agent.await_args
        message = call.kwargs["message"]
        assert "[respond in German]" in message
        assert "Hallo" in message

    @pytest.mark.asyncio
    async def test_chat_injects_language_hint_en(
        self, claude_client, mock_openclaw
    ):
        """English requests are hinted so OpenClaw mirrors the language."""
        await claude_client.chat("Hello", language="en")

        call = mock_openclaw.query_agent.await_args
        message = call.kwargs["message"]
        assert "[respond in English]" in message

    @pytest.mark.asyncio
    async def test_chat_error_returns_fallback_en(
        self, claude_client, mock_openclaw
    ):
        """OpenClaw errors surface as a spoken offline fallback (EN)."""
        mock_openclaw.query_agent.return_value = _make_response(
            text="",
            error="connection refused",
        )

        response = await claude_client.chat("Hello", language="en")

        assert "OpenClaw gateway" in response or response in FALLBACK_RESPONSES.values()

    @pytest.mark.asyncio
    async def test_chat_error_returns_fallback_de(
        self, claude_client, mock_openclaw
    ):
        """OpenClaw errors surface as a spoken offline fallback (DE)."""
        mock_openclaw.query_agent.return_value = _make_response(
            text="",
            error="timeout",
        )

        response = await claude_client.chat("Hallo", language="de")

        assert "OpenClaw-Gateway" in response or response in FALLBACK_RESPONSES.values()

    @pytest.mark.asyncio
    async def test_chat_ignores_legacy_history_argument(
        self, claude_client, mock_openclaw
    ):
        """``history`` is accepted for compat but not forwarded.

        OpenClaw owns session history via ``session_id``.
        """
        history = [{"role": "user", "content": "older turn"}]

        await claude_client.chat("Hello", language="en", history=history)

        call = mock_openclaw.query_agent.await_args
        assert "older turn" not in call.kwargs["message"]

    @pytest.mark.asyncio
    async def test_chat_ignores_legacy_system_prompt_argument(
        self, claude_client, mock_openclaw
    ):
        """``system_prompt`` is accepted for compat but not forwarded.

        Persona is owned by OpenClaw (``SOUL.md``).
        """
        await claude_client.chat(
            "Hello",
            language="en",
            system_prompt="You are a pirate.",
        )

        call = mock_openclaw.query_agent.await_args
        assert "pirate" not in call.kwargs["message"]


class TestClaudeClientComplete:
    """Tests for ``complete`` (utility completions)."""

    @pytest.mark.asyncio
    async def test_complete_uses_utility_session(
        self, claude_client, mock_openclaw
    ):
        """Utility calls run on a ``jarvis-util-*`` session id."""
        await claude_client.complete(
            prompt="Route this request",
            system_prompt="You are a router",
        )

        call = mock_openclaw.query_agent.await_args
        assert call.kwargs["session_id"].startswith("jarvis-util-")

    @pytest.mark.asyncio
    async def test_complete_folds_system_prompt_into_message(
        self, claude_client, mock_openclaw
    ):
        """System prompt is wrapped into the user payload (no API system slot)."""
        await claude_client.complete(
            prompt="the user ask",
            system_prompt="instruction block",
        )

        call = mock_openclaw.query_agent.await_args
        message = call.kwargs["message"]
        assert "instruction block" in message
        assert "the user ask" in message
        assert "[[SYSTEM INSTRUCTION]]" in message

    @pytest.mark.asyncio
    async def test_complete_returns_empty_on_error(
        self, claude_client, mock_openclaw
    ):
        """Errors surface as an empty string (orchestrator handles the fallback)."""
        mock_openclaw.query_agent.return_value = _make_response(
            text="",
            error="gateway 503",
        )

        result = await claude_client.complete(
            prompt="x",
            system_prompt="y",
        )

        assert result == ""


class TestClaudeClientJson:
    """Tests for ``chat_with_json``."""

    @pytest.mark.asyncio
    async def test_returns_parsed_json(
        self, claude_client, mock_openclaw
    ):
        """Plain-JSON responses parse cleanly."""
        mock_openclaw.query_agent.return_value = _make_response(
            text='{"key": "value"}'
        )

        result = await claude_client.chat_with_json(
            "Return JSON",
            system_prompt="Return valid JSON",
        )

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_handles_json_in_code_block(
        self, claude_client, mock_openclaw
    ):
        """Accidental code fences are stripped before parsing."""
        mock_openclaw.query_agent.return_value = _make_response(
            text='```json\n{"key": "value"}\n```'
        )

        result = await claude_client.chat_with_json(
            "Return JSON",
            system_prompt="Return valid JSON",
        )

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_error(
        self, claude_client, mock_openclaw
    ):
        """OpenClaw errors collapse into an empty dict."""
        mock_openclaw.query_agent.return_value = _make_response(
            text="",
            error="oops",
        )

        result = await claude_client.chat_with_json(
            "Return JSON",
            system_prompt="Return valid JSON",
        )

        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_parse_error(
        self, claude_client, mock_openclaw
    ):
        """Non-JSON responses collapse into an empty dict."""
        mock_openclaw.query_agent.return_value = _make_response(
            text="not really JSON at all"
        )

        result = await claude_client.chat_with_json(
            "Return JSON",
            system_prompt="Return valid JSON",
        )

        assert result == {}


class TestCreateClaudeClient:
    """Tests for the factory function."""

    @pytest.mark.asyncio
    async def test_creates_client_from_config(
        self, mock_config, mock_openclaw
    ):
        """Factory produces a ``ClaudeClient`` reusing the injected OpenClaw."""
        config = mock_config["claude"].copy()

        client = await create_claude_client(
            config=config,
            openclaw_client=mock_openclaw,
        )

        assert isinstance(client, ClaudeClient)
        assert client.model == "claude-sonnet-4-6"
        assert client.max_tokens == 300
        assert client.temperature == 0.7
        assert client.openclaw is mock_openclaw


class TestPersonaConstants:
    """The legacy JARVIS persona constants must still be exported.

    External callers (tests, docs/diagnostics) reference them. The
    production path no longer injects them because OpenClaw owns the
    persona via SOUL.md.
    """

    def test_jarvis_prompt_constant_exported(self):
        assert "JARVIS" in JARVIS_SYSTEM_PROMPT

    def test_fallback_responses_cover_en_and_de(self):
        assert "en" in FALLBACK_RESPONSES
        assert "de" in FALLBACK_RESPONSES


class TestPersonaNotInjectedIntoOpenClaw:
    """Regression — persona must NOT leak into every chat turn."""

    @pytest.mark.asyncio
    async def test_chat_message_does_not_contain_persona(
        self, claude_client, mock_openclaw
    ):
        """SOUL.md owns persona; we must not double-prompt."""
        await claude_client.chat("Hello", language="en")

        call = mock_openclaw.query_agent.await_args
        message = call.kwargs["message"]

        # None of the highly-identifiable persona strings should appear.
        assert "British butler elegance" not in message
        assert "Tony Stark" not in message


# Keep an instance of ``patch`` referenced so import-time side-effect
# detectors don't flag the unused import.
_ = patch
