"""Tests for SearchAgent — web search via OpenClaw.

Covers:
- Happy path EN/DE: OpenClaw returns a non-empty text response.
- Prompt template selection: DE utterances use the German template.
- Empty/missing params["query"] falls back to the task string.
- AgentResponse with error set returns the spoken fallback.
- AgentResponse with empty text returns the spoken fallback.
- query_agent raises an unexpected exception → graceful fallback.
- openclaw attribute is None → graceful fallback.
- openclaw.is_enabled is False → graceful fallback.
- Exact prompt format (substring assertions).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brain.agents.base import AgentResult
from brain.agents.search_agent import SearchAgent, _FALLBACK_DE, _FALLBACK_EN
from integrations.openclaw import AgentResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(text: str = "", error: str | None = None) -> AgentResponse:
    """Build a minimal AgentResponse for mocking."""
    return AgentResponse(
        text=text,
        session_id="jarvis-main",
        thinking_used=False,
        tool_calls=[],
        error=error,
    )


def _make_agent(query_agent_return: AgentResponse | None = None) -> tuple[SearchAgent, MagicMock]:
    """Return a SearchAgent wired to a mocked ClaudeClient.

    The mock ``openclaw`` attribute has ``is_enabled = True`` and
    ``query_agent`` returning ``query_agent_return`` (or a generic success
    response when ``None``).
    """
    if query_agent_return is None:
        query_agent_return = _make_response(text="Default mocked text.")

    mock_openclaw = MagicMock()
    mock_openclaw.is_enabled = True
    mock_openclaw.query_agent = AsyncMock(return_value=query_agent_return)

    mock_claude = MagicMock()
    mock_claude.openclaw = mock_openclaw

    with patch("utils.config_loader.get_config") as mock_cfg:
        mock_cfg.return_value.get_section.return_value = {
            "subagent_model": "claude-sonnet-4-6",
            "action_max_tokens": 100,
        }
        agent = SearchAgent(claude_client=mock_claude)

    return agent, mock_openclaw


# ---------------------------------------------------------------------------
# Happy path — English
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_happy_path_english_returns_openclaw_text():
    """EN happy path: spoken_response equals the OpenClaw text, success=True."""
    expected_text = "Bohemian Rhapsody is by Queen."
    agent, mock_openclaw = _make_agent(
        query_agent_return=_make_response(text=expected_text)
    )

    result = await agent.run(
        task="Who made Bohemian Rhapsody?",
        params={"query": "Bohemian Rhapsody artist"},
        language="en",
    )

    assert isinstance(result, AgentResult)
    assert result.success is True
    assert result.spoken_response == expected_text
    mock_openclaw.query_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_happy_path_english_passes_query_in_data():
    """EN happy path: the query string is stored in result.data."""
    agent, _ = _make_agent(
        query_agent_return=_make_response(text="Paris is the capital of France.")
    )

    result = await agent.run(
        task="",
        params={"query": "capital of France"},
        language="en",
    )

    assert result.success is True
    assert result.data.get("query") == "capital of France"


# ---------------------------------------------------------------------------
# Happy path — German
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_happy_path_german_returns_openclaw_text():
    """DE happy path: spoken_response equals the OpenClaw text, success=True."""
    expected_text = "Bohemian Rhapsody stammt von Queen."
    agent, mock_openclaw = _make_agent(
        query_agent_return=_make_response(text=expected_text)
    )

    result = await agent.run(
        task="Wer hat Bohemian Rhapsody gemacht?",
        params={"query": "Bohemian Rhapsody Künstler"},
        language="de",
    )

    assert result.success is True
    assert result.spoken_response == expected_text


@pytest.mark.asyncio
async def test_run_german_uses_german_prompt_template():
    """DE: the prompt passed to query_agent contains the German template marker."""
    agent, mock_openclaw = _make_agent(
        query_agent_return=_make_response(text="Ergebnis.")
    )

    await agent.run(
        task="Suche etwas",
        params={"query": "aktuelles Wetter in München"},
        language="de",
    )

    call_args = mock_openclaw.query_agent.await_args
    prompt_sent: str = call_args.args[0] if call_args.args else call_args.kwargs.get("message", "")
    assert "Suche im Web nach" in prompt_sent


@pytest.mark.asyncio
async def test_run_english_does_not_use_german_prompt_template():
    """EN: the German template marker must NOT appear in the English prompt."""
    agent, mock_openclaw = _make_agent(
        query_agent_return=_make_response(text="Result.")
    )

    await agent.run(
        task="Search something",
        params={"query": "weather in Munich"},
        language="en",
    )

    call_args = mock_openclaw.query_agent.await_args
    prompt_sent: str = call_args.args[0] if call_args.args else call_args.kwargs.get("message", "")
    assert "Search the web for" in prompt_sent
    assert "Suche im Web nach" not in prompt_sent


# ---------------------------------------------------------------------------
# Prompt format assertions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_english_prompt_contains_query():
    """The English prompt embeds the query string verbatim."""
    query = "population of Tokyo"
    agent, mock_openclaw = _make_agent(
        query_agent_return=_make_response(text="Tokyo has about 14 million people.")
    )

    await agent.run(task="", params={"query": query}, language="en")

    call_args = mock_openclaw.query_agent.await_args
    prompt_sent: str = call_args.args[0] if call_args.args else call_args.kwargs.get("message", "")
    assert query in prompt_sent


@pytest.mark.asyncio
async def test_run_german_prompt_contains_query():
    """The German prompt embeds the query string verbatim."""
    query = "Einwohnerzahl von Tokio"
    agent, mock_openclaw = _make_agent(
        query_agent_return=_make_response(text="Tokio hat etwa 14 Millionen Einwohner.")
    )

    await agent.run(task="", params={"query": query}, language="de")

    call_args = mock_openclaw.query_agent.await_args
    prompt_sent: str = call_args.args[0] if call_args.args else call_args.kwargs.get("message", "")
    assert query in prompt_sent


# ---------------------------------------------------------------------------
# Fallback: empty/missing params["query"] uses task string
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_empty_query_param_falls_back_to_task():
    """When params['query'] is empty, the task string is used as the query."""
    task_text = "Who is Alan Turing?"
    agent, mock_openclaw = _make_agent(
        query_agent_return=_make_response(text="Alan Turing was a mathematician.")
    )

    result = await agent.run(task=task_text, params={"query": ""}, language="en")

    assert result.success is True
    call_args = mock_openclaw.query_agent.await_args
    prompt_sent: str = call_args.args[0] if call_args.args else call_args.kwargs.get("message", "")
    assert task_text in prompt_sent


@pytest.mark.asyncio
async def test_run_missing_query_key_falls_back_to_task():
    """When params has no 'query' key at all, the task string is used."""
    task_text = "What is the Pythagorean theorem?"
    agent, mock_openclaw = _make_agent(
        query_agent_return=_make_response(text="a² + b² = c².")
    )

    result = await agent.run(task=task_text, params={}, language="en")

    assert result.success is True
    call_args = mock_openclaw.query_agent.await_args
    prompt_sent: str = call_args.args[0] if call_args.args else call_args.kwargs.get("message", "")
    assert task_text in prompt_sent


@pytest.mark.asyncio
async def test_run_none_query_falls_back_to_task():
    """When params['query'] is None (falsy), the task string is used."""
    task_text = "What is Schrödinger's cat?"
    agent, mock_openclaw = _make_agent(
        query_agent_return=_make_response(text="A thought experiment.")
    )

    result = await agent.run(task=task_text, params={"query": None}, language="en")

    assert result.success is True
    call_args = mock_openclaw.query_agent.await_args
    prompt_sent: str = call_args.args[0] if call_args.args else call_args.kwargs.get("message", "")
    assert task_text in prompt_sent


@pytest.mark.asyncio
async def test_run_both_empty_task_and_query_returns_fallback_en():
    """When both task and params['query'] are empty/falsy, return the EN fallback."""
    agent, mock_openclaw = _make_agent()

    result = await agent.run(task="", params={}, language="en")

    assert result.success is False
    assert result.spoken_response == _FALLBACK_EN
    mock_openclaw.query_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_both_empty_task_and_query_returns_fallback_de():
    """When both task and params['query'] are empty/falsy, return the DE fallback."""
    agent, mock_openclaw = _make_agent()

    result = await agent.run(task="", params={}, language="de")

    assert result.success is False
    assert result.spoken_response == _FALLBACK_DE
    mock_openclaw.query_agent.assert_not_awaited()


# ---------------------------------------------------------------------------
# OpenClaw returns error or empty text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_openclaw_returns_connection_error_en():
    """EN: AgentResponse.error != None → graceful spoken fallback, success=False."""
    agent, _ = _make_agent(
        query_agent_return=_make_response(text="", error="connection error")
    )

    result = await agent.run(task="", params={"query": "test"}, language="en")

    assert result.success is False
    assert result.spoken_response == _FALLBACK_EN


@pytest.mark.asyncio
async def test_run_openclaw_returns_connection_error_de():
    """DE: AgentResponse.error != None → German spoken fallback, success=False."""
    agent, _ = _make_agent(
        query_agent_return=_make_response(text="", error="connection error")
    )

    result = await agent.run(task="", params={"query": "test"}, language="de")

    assert result.success is False
    assert result.spoken_response == _FALLBACK_DE


@pytest.mark.asyncio
async def test_run_openclaw_returns_empty_text_en():
    """EN: AgentResponse.text is blank (no error) → EN fallback, success=False."""
    agent, _ = _make_agent(
        query_agent_return=_make_response(text="   ", error=None)
    )

    result = await agent.run(task="", params={"query": "test"}, language="en")

    assert result.success is False
    assert result.spoken_response == _FALLBACK_EN


@pytest.mark.asyncio
async def test_run_openclaw_returns_empty_text_de():
    """DE: AgentResponse.text is blank → DE fallback, success=False."""
    agent, _ = _make_agent(
        query_agent_return=_make_response(text="", error=None)
    )

    result = await agent.run(task="", params={"query": "test"}, language="de")

    assert result.success is False
    assert result.spoken_response == _FALLBACK_DE


@pytest.mark.asyncio
async def test_run_openclaw_error_data_contains_error_key():
    """When OpenClaw returns an error, result.data['error'] records it."""
    error_msg = "timeout after 10s"
    agent, _ = _make_agent(
        query_agent_return=_make_response(text="", error=error_msg)
    )

    result = await agent.run(task="", params={"query": "test"}, language="en")

    assert result.data.get("error") == error_msg


# ---------------------------------------------------------------------------
# query_agent raises unexpected exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_query_agent_raises_exception_en():
    """Unexpected RuntimeError from query_agent → EN spoken fallback, success=False."""
    mock_openclaw = MagicMock()
    mock_openclaw.is_enabled = True
    mock_openclaw.query_agent = AsyncMock(side_effect=RuntimeError("network down"))

    mock_claude = MagicMock()
    mock_claude.openclaw = mock_openclaw

    with patch("utils.config_loader.get_config") as mock_cfg:
        mock_cfg.return_value.get_section.return_value = {
            "subagent_model": "claude-sonnet-4-6",
            "action_max_tokens": 100,
        }
        agent = SearchAgent(claude_client=mock_claude)

    result = await agent.run(task="", params={"query": "test"}, language="en")

    assert result.success is False
    assert result.spoken_response == _FALLBACK_EN


@pytest.mark.asyncio
async def test_run_query_agent_raises_exception_de():
    """Unexpected exception from query_agent → DE spoken fallback."""
    mock_openclaw = MagicMock()
    mock_openclaw.is_enabled = True
    mock_openclaw.query_agent = AsyncMock(side_effect=ConnectionError("lost connection"))

    mock_claude = MagicMock()
    mock_claude.openclaw = mock_openclaw

    with patch("utils.config_loader.get_config") as mock_cfg:
        mock_cfg.return_value.get_section.return_value = {
            "subagent_model": "claude-sonnet-4-6",
            "action_max_tokens": 100,
        }
        agent = SearchAgent(claude_client=mock_claude)

    result = await agent.run(task="", params={"query": "Wetter"}, language="de")

    assert result.success is False
    assert result.spoken_response == _FALLBACK_DE


@pytest.mark.asyncio
async def test_run_exception_data_contains_error_message():
    """Exception message is recorded in result.data['error']."""
    exc_msg = "ECONNRESET"
    mock_openclaw = MagicMock()
    mock_openclaw.is_enabled = True
    mock_openclaw.query_agent = AsyncMock(side_effect=OSError(exc_msg))

    mock_claude = MagicMock()
    mock_claude.openclaw = mock_openclaw

    with patch("utils.config_loader.get_config") as mock_cfg:
        mock_cfg.return_value.get_section.return_value = {
            "subagent_model": "claude-sonnet-4-6",
            "action_max_tokens": 100,
        }
        agent = SearchAgent(claude_client=mock_claude)

    result = await agent.run(task="", params={"query": "test"}, language="en")

    assert exc_msg in result.data.get("error", "")


# ---------------------------------------------------------------------------
# openclaw is None or disabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_openclaw_none_returns_fallback_en():
    """When claude_client.openclaw is None, EN fallback is returned."""
    mock_claude = MagicMock()
    mock_claude.openclaw = None

    with patch("utils.config_loader.get_config") as mock_cfg:
        mock_cfg.return_value.get_section.return_value = {
            "subagent_model": "claude-sonnet-4-6",
            "action_max_tokens": 100,
        }
        agent = SearchAgent(claude_client=mock_claude)

    result = await agent.run(task="", params={"query": "test"}, language="en")

    assert result.success is False
    assert result.spoken_response == _FALLBACK_EN


@pytest.mark.asyncio
async def test_run_openclaw_none_returns_fallback_de():
    """When claude_client.openclaw is None, DE fallback is returned."""
    mock_claude = MagicMock()
    mock_claude.openclaw = None

    with patch("utils.config_loader.get_config") as mock_cfg:
        mock_cfg.return_value.get_section.return_value = {
            "subagent_model": "claude-sonnet-4-6",
            "action_max_tokens": 100,
        }
        agent = SearchAgent(claude_client=mock_claude)

    result = await agent.run(task="", params={"query": "Wetter"}, language="de")

    assert result.success is False
    assert result.spoken_response == _FALLBACK_DE


@pytest.mark.asyncio
async def test_run_openclaw_disabled_returns_fallback_en():
    """When openclaw.is_enabled is False, EN fallback is returned, query_agent not called."""
    mock_openclaw = MagicMock()
    mock_openclaw.is_enabled = False
    mock_openclaw.query_agent = AsyncMock()

    mock_claude = MagicMock()
    mock_claude.openclaw = mock_openclaw

    with patch("utils.config_loader.get_config") as mock_cfg:
        mock_cfg.return_value.get_section.return_value = {
            "subagent_model": "claude-sonnet-4-6",
            "action_max_tokens": 100,
        }
        agent = SearchAgent(claude_client=mock_claude)

    result = await agent.run(task="", params={"query": "test"}, language="en")

    assert result.success is False
    assert result.spoken_response == _FALLBACK_EN
    mock_openclaw.query_agent.assert_not_awaited()


# ---------------------------------------------------------------------------
# session_id is propagated in result.data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_success_data_contains_session_id():
    """On success, result.data['session_id'] echoes the response session_id."""
    agent, _ = _make_agent(
        query_agent_return=AgentResponse(
            text="Some answer.",
            session_id="jarvis-main",
            thinking_used=False,
            tool_calls=[],
            error=None,
        )
    )

    result = await agent.run(task="", params={"query": "test"}, language="en")

    assert result.success is True
    assert result.data.get("session_id") == "jarvis-main"


# ---------------------------------------------------------------------------
# Whitespace stripping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_strips_leading_trailing_whitespace():
    """spoken_response has whitespace stripped from the OpenClaw text."""
    agent, _ = _make_agent(
        query_agent_return=_make_response(text="  The answer.  \n")
    )

    result = await agent.run(task="", params={"query": "question"}, language="en")

    assert result.success is True
    assert result.spoken_response == "The answer."
