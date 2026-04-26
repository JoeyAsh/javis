"""Tests for Drive intent routing in IntentParser and Orchestrator.

Covers DRIVE_SEARCH intent classification (EN/DE), query extraction,
and _build_drive_context injection into the chat path.

All external I/O is mocked; no real Drive API or OAuth calls are made.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Intent parser — DRIVE_SEARCH classification
# ---------------------------------------------------------------------------


@pytest.fixture()
def parser():
    """Return a live IntentParser instance."""
    from brain.intent_parser import IntentParser

    return IntentParser()


@pytest.mark.asyncio
async def test_drive_search_english_keyword(parser):
    """'search in drive' classifies as DRIVE_SEARCH with conf >= 0.75."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("search in drive", language="en")
    assert result.intent == Intent.DRIVE_SEARCH
    assert result.confidence >= 0.75


@pytest.mark.asyncio
async def test_drive_search_english_find_doc(parser):
    """'find the document budget report' classifies as DRIVE_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("find the document budget report", language="en")
    assert result.intent == Intent.DRIVE_SEARCH


@pytest.mark.asyncio
async def test_drive_search_english_open_doc(parser):
    """'open doc quarterly review' classifies as DRIVE_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("open doc quarterly review", language="en")
    assert result.intent == Intent.DRIVE_SEARCH


@pytest.mark.asyncio
async def test_drive_search_german_suche_in_drive(parser):
    """'suche in drive' classifies as DRIVE_SEARCH (German)."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("suche in drive", language="de")
    assert result.intent == Intent.DRIVE_SEARCH
    assert result.confidence >= 0.75


@pytest.mark.asyncio
async def test_drive_search_german_finde_dokument(parser):
    """'finde das Dokument Jahresbericht' classifies as DRIVE_SEARCH (German)."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("finde das Dokument Jahresbericht", language="de")
    assert result.intent == Intent.DRIVE_SEARCH


@pytest.mark.asyncio
async def test_drive_search_extracts_query_hint(parser):
    """'find the document budget report' extracts 'budget report' as query."""
    result = await parser.classify_intent("find the document budget report", language="en")
    assert "query" in result.params
    assert result.params["query"]  # non-empty


@pytest.mark.asyncio
async def test_drive_search_unrelated_not_classified(parser):
    """'play some music' is NOT classified as DRIVE_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("play some music", language="en")
    assert result.intent != Intent.DRIVE_SEARCH


@pytest.mark.asyncio
async def test_drive_search_email_not_classified(parser):
    """'check my email' is NOT classified as DRIVE_SEARCH."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("check my email", language="en")
    assert result.intent != Intent.DRIVE_SEARCH


# ---------------------------------------------------------------------------
# Orchestrator — _build_drive_context
# ---------------------------------------------------------------------------


def _make_drive_file(
    file_id: str = "f1",
    name: str = "Test Doc",
    mime_type: str = "application/vnd.google-apps.document",
    modified_time_str: str = "2024-06-15T09:00:00+00:00",
    web_view_link: str = "https://docs.google.com/document/d/f1/edit",
):
    """Build a DriveFile fixture."""
    from datetime import datetime, timezone

    from integrations.google.drive_client import DriveFile

    return DriveFile(
        id=file_id,
        name=name,
        mime_type=mime_type,
        modified_time=datetime.fromisoformat(modified_time_str),
        web_view_link=web_view_link,
    )


def _make_orchestrator() -> Any:
    """Build a minimal Orchestrator with mocked ClaudeClient."""
    from brain.claude_client import ClaudeClient
    from brain.orchestrator import Orchestrator

    claude_mock = MagicMock(spec=ClaudeClient)
    claude_mock.openclaw = None

    # Phase 4 (issue #76): PcAgent and SmartHomeAgent are no longer imported by
    # orchestrator.py, so patching them would raise AttributeError.  Only the
    # agents that are still wired remain patchable.
    with patch("brain.orchestrator.SystemAgent"), patch("brain.orchestrator.ChatAgent"), patch(
        "brain.orchestrator.SearchAgent"
    ):
        orch = Orchestrator(claude_client=claude_mock)

    return orch


@pytest.mark.asyncio
async def test_build_drive_context_disabled_returns_none():
    """_build_drive_context returns None when drive.enabled is False."""
    from brain.intent_parser import Intent, IntentResult

    orch = _make_orchestrator()

    drive_cfg = {"enabled": False, "max_results": 10, "preview_content_chars": 500}
    mock_config = MagicMock()
    mock_config.get_section.return_value = drive_cfg

    intent_result = IntentResult(
        intent=Intent.DRIVE_SEARCH,
        confidence=0.85,
        params={"query": "budget report"},
        original_text="find the document budget report",
    )

    with patch("brain.orchestrator.get_config", return_value=mock_config):
        ctx = await orch._build_drive_context(intent_result)

    assert ctx is None


@pytest.mark.asyncio
async def test_build_drive_context_with_query_includes_files():
    """_build_drive_context injects search results into context string."""
    from brain.intent_parser import Intent, IntentResult

    orch = _make_orchestrator()

    files = [
        _make_drive_file("f1", "Budget Report 2024"),
        _make_drive_file("f2", "Q3 Financials"),
    ]

    drive_cfg = {
        "enabled": True,
        "max_results": 10,
        "preview_content_chars": 500,
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
    }
    mock_config = MagicMock()
    mock_config.get_section.return_value = drive_cfg

    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=files)
    mock_client.get_file_content = AsyncMock(return_value="This is the file content preview.")

    intent_result = IntentResult(
        intent=Intent.DRIVE_SEARCH,
        confidence=0.85,
        params={"query": "budget report"},
        original_text="find the document budget report",
    )

    with (
        patch("brain.orchestrator.get_config", return_value=mock_config),
        patch("integrations.google.drive_client.get_drive_client", return_value=mock_client),
        patch("brain.orchestrator.get_config", return_value=mock_config),
    ):
        ctx = await orch._build_drive_context(intent_result)

    assert ctx is not None
    assert "budget report" in ctx
    assert "Budget Report 2024" in ctx


@pytest.mark.asyncio
async def test_build_drive_context_no_query_uses_list_recent():
    """_build_drive_context calls list_recent when no query hint is present."""
    from brain.intent_parser import Intent, IntentResult

    orch = _make_orchestrator()

    files = [_make_drive_file("r1", "Recent File")]

    drive_cfg = {
        "enabled": True,
        "max_results": 10,
        "preview_content_chars": 500,
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
    }
    mock_config = MagicMock()
    mock_config.get_section.return_value = drive_cfg

    mock_client = MagicMock()
    mock_client.list_recent = AsyncMock(return_value=files)

    intent_result = IntentResult(
        intent=Intent.DRIVE_SEARCH,
        confidence=0.80,
        params={},  # no query hint
        original_text="show my drive files",
    )

    with (
        patch("brain.orchestrator.get_config", return_value=mock_config),
        patch("integrations.google.drive_client.get_drive_client", return_value=mock_client),
    ):
        ctx = await orch._build_drive_context(intent_result)

    assert ctx is not None
    mock_client.list_recent.assert_awaited_once()
    assert "Recent File" in ctx


@pytest.mark.asyncio
async def test_build_drive_context_empty_search_returns_empty_message():
    """_build_drive_context returns a 'not found' string when search yields nothing."""
    from brain.intent_parser import Intent, IntentResult

    orch = _make_orchestrator()

    drive_cfg = {
        "enabled": True,
        "max_results": 10,
        "preview_content_chars": 500,
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
    }
    mock_config = MagicMock()
    mock_config.get_section.return_value = drive_cfg

    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=[])

    intent_result = IntentResult(
        intent=Intent.DRIVE_SEARCH,
        confidence=0.85,
        params={"query": "nonexistent xyz"},
        original_text="find the document nonexistent xyz",
    )

    with (
        patch("brain.orchestrator.get_config", return_value=mock_config),
        patch("integrations.google.drive_client.get_drive_client", return_value=mock_client),
    ):
        ctx = await orch._build_drive_context(intent_result)

    assert ctx is not None
    assert "nonexistent xyz" in ctx
    assert "gefunden" in ctx.lower() or "not found" in ctx.lower() or "keine" in ctx.lower()


@pytest.mark.asyncio
async def test_build_drive_context_on_api_error_returns_none():
    """_build_drive_context returns None (not raises) when the API call fails."""
    from integrations.google.drive_client import DriveClientError
    from brain.intent_parser import Intent, IntentResult

    orch = _make_orchestrator()

    drive_cfg = {
        "enabled": True,
        "max_results": 10,
        "preview_content_chars": 500,
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
    }
    mock_config = MagicMock()
    mock_config.get_section.return_value = drive_cfg

    mock_client = MagicMock()
    mock_client.search = AsyncMock(side_effect=DriveClientError("quota exceeded"))

    intent_result = IntentResult(
        intent=Intent.DRIVE_SEARCH,
        confidence=0.85,
        params={"query": "anything"},
        original_text="search in drive anything",
    )

    with (
        patch("brain.orchestrator.get_config", return_value=mock_config),
        patch("integrations.google.drive_client.get_drive_client", return_value=mock_client),
    ):
        ctx = await orch._build_drive_context(intent_result)

    assert ctx is None


@pytest.mark.asyncio
async def test_build_drive_context_truncates_content_preview():
    """_build_drive_context truncates file content to preview_content_chars."""
    from brain.intent_parser import Intent, IntentResult

    orch = _make_orchestrator()

    files = [_make_drive_file("f1", "Long Document")]

    preview_chars = 50
    long_content = "A" * 500  # much longer than preview_chars

    drive_cfg = {
        "enabled": True,
        "max_results": 10,
        "preview_content_chars": preview_chars,
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
    }
    mock_config = MagicMock()
    mock_config.get_section.return_value = drive_cfg

    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=files)
    mock_client.get_file_content = AsyncMock(return_value=long_content)

    intent_result = IntentResult(
        intent=Intent.DRIVE_SEARCH,
        confidence=0.85,
        params={"query": "long document"},
        original_text="find the document long document",
    )

    with (
        patch("brain.orchestrator.get_config", return_value=mock_config),
        patch("integrations.google.drive_client.get_drive_client", return_value=mock_client),
    ):
        ctx = await orch._build_drive_context(intent_result)

    assert ctx is not None
    # The ellipsis marker should be present indicating truncation.
    assert "…" in ctx
    # The full long content should NOT appear.
    assert "A" * (preview_chars + 1) not in ctx
