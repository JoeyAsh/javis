"""Unit tests for orchestrator calendar intent + context injection.

Covers acceptance criteria 10 (intent classification) and the
``_build_calendar_context`` method's output shapes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brain.intent_parser import Intent, IntentParser, IntentResult


# ---------------------------------------------------------------------------
# Intent classification (AC 10)
# ---------------------------------------------------------------------------


@pytest.fixture()
def parser() -> IntentParser:
    """Return a fresh IntentParser."""
    return IntentParser()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,language",
    [
        ("What's on my calendar today?", "en"),
        ("What do I have tomorrow?", "en"),
        ("show my calendar", "en"),
        ("Was steht morgen an?", "de"),
        ("Habe ich heute Termine?", "de"),
        ("zeig mir meinen Kalender", "de"),
    ],
)
async def test_calendar_list_intent(
    parser: IntentParser, text: str, language: str
) -> None:
    """CALENDAR_LIST classified with confidence ≥ 0.7 in both EN and DE."""
    result = await parser.classify_intent(text, language)
    assert result.intent == Intent.CALENDAR_LIST, (
        f"Expected CALENDAR_LIST for {text!r}, got {result.intent}"
    )
    assert result.confidence >= 0.7, (
        f"Expected confidence ≥ 0.7, got {result.confidence}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,language",
    [
        ("Schedule a team standup Friday at 10am", "en"),
        ("Create a meeting with Bob tomorrow at 2pm", "en"),
        ("Add a dentist appointment to my calendar", "en"),
        ("Termin erstellen Montag um 9 Uhr", "de"),
        ("Füge einen Termin hinzu", "de"),
        ("plane ein Meeting morgen", "de"),
    ],
)
async def test_calendar_create_intent(
    parser: IntentParser, text: str, language: str
) -> None:
    """CALENDAR_CREATE classified with confidence ≥ 0.7 in both EN and DE."""
    result = await parser.classify_intent(text, language)
    assert result.intent == Intent.CALENDAR_CREATE, (
        f"Expected CALENDAR_CREATE for {text!r}, got {result.intent}"
    )
    assert result.confidence >= 0.7


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,language",
    [
        ("Move the meeting to 3pm", "en"),
        ("Reschedule the standup to next Friday", "en"),
        ("Verschiebe den Termin auf morgen", "de"),
    ],
)
async def test_calendar_update_intent(
    parser: IntentParser, text: str, language: str
) -> None:
    """CALENDAR_UPDATE classified with confidence ≥ 0.7."""
    result = await parser.classify_intent(text, language)
    assert result.intent == Intent.CALENDAR_UPDATE, (
        f"Expected CALENDAR_UPDATE for {text!r}, got {result.intent}"
    )
    assert result.confidence >= 0.7


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,language",
    [
        ("Cancel my 9am standup", "en"),
        ("Delete the meeting with Bob", "en"),
        ("Termin löschen", "de"),
        ("Den Termin absagen", "de"),
    ],
)
async def test_calendar_delete_intent(
    parser: IntentParser, text: str, language: str
) -> None:
    """CALENDAR_DELETE classified with confidence ≥ 0.7."""
    result = await parser.classify_intent(text, language)
    assert result.intent == Intent.CALENDAR_DELETE, (
        f"Expected CALENDAR_DELETE for {text!r}, got {result.intent}"
    )
    assert result.confidence >= 0.7


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,language",
    [
        ("What time is it?", "en"),
        ("Play some music", "en"),
        ("Turn off the lights", "en"),
        ("Wie geht es dir?", "de"),
    ],
)
async def test_non_calendar_not_matched(
    parser: IntentParser, text: str, language: str
) -> None:
    """Non-calendar utterances do not match calendar intents."""
    result = await parser.classify_intent(text, language)
    assert result.intent not in (
        Intent.CALENDAR_LIST,
        Intent.CALENDAR_CREATE,
        Intent.CALENDAR_UPDATE,
        Intent.CALENDAR_DELETE,
    ), f"Unexpected calendar match for {text!r}: {result.intent}"


# ---------------------------------------------------------------------------
# _build_calendar_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_calendar_context_list_with_events() -> None:
    """_build_calendar_context returns formatted event list for CALENDAR_LIST."""
    from brain.orchestrator import Orchestrator
    from brain.intent_parser import IntentResult

    mock_client = MagicMock()
    mock_client.list_events = AsyncMock(
        return_value=[
            _make_calendar_event("evt1", "Standup", False),
            _make_calendar_event("evt2", "Lunch", False),
        ]
    )

    with (
        patch("brain.orchestrator.get_config", return_value=_mock_config()),
        patch(
            "brain.orchestrator.get_calendar_client",
            return_value=mock_client,
            create=True,
        ),
    ):
        orch = _make_orchestrator()
        intent_result = IntentResult(
            intent=Intent.CALENDAR_LIST,
            confidence=0.9,
            original_text="What's on my calendar today?",
            language="en",
        )

        # Patch the internal import
        with patch(
            "integrations.google.calendar_client.get_calendar_client",
            return_value=mock_client,
        ):
            ctx = await orch._build_calendar_context(intent_result)

    assert ctx is not None
    assert "Standup" in ctx
    assert "Lunch" in ctx
    assert "Context" in ctx


@pytest.mark.asyncio
async def test_build_calendar_context_disabled_returns_none() -> None:
    """_build_calendar_context returns None when calendar.enabled is False."""
    from brain.orchestrator import Orchestrator
    from brain.intent_parser import IntentResult

    with patch(
        "brain.orchestrator.get_config",
        return_value=_mock_config(calendar_enabled=False),
    ):
        orch = _make_orchestrator()
        result = await orch._build_calendar_context(
            IntentResult(intent=Intent.CALENDAR_LIST, confidence=0.9)
        )

    assert result is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_calendar_event(event_id: str, title: str, all_day: bool):
    """Build a minimal CalendarEvent-like object."""
    from integrations.google.calendar_client import CalendarEvent

    now = datetime(2026, 4, 18, 9, 0, tzinfo=timezone.utc)
    return CalendarEvent(
        id=event_id,
        calendar_id="primary",
        title=title,
        start=now,
        end=now + timedelta(hours=1),
        all_day=all_day,
        location=None,
        description=None,
        attendees=[],
        is_recurring=False,
    )


def _mock_config(calendar_enabled: bool = True) -> MagicMock:
    cfg = MagicMock()
    cfg.get_section.side_effect = lambda section: {
        "calendar": {
            "enabled": calendar_enabled,
            "lookahead_hours": 48,
            "max_events_per_query": 20,
            "default_event_duration_minutes": 60,
        },
        "agents": {
            "orchestrator_model": "claude-opus-4-5",
            "orchestrator_max_tokens": 150,
            "skip_orchestrator_on_clear_intent": True,
            "history_turns_for_orchestrator": 3,
        },
    }.get(section, {})
    return cfg


def _make_orchestrator():
    from brain.orchestrator import Orchestrator

    mock_claude = MagicMock()
    mock_claude.openclaw = None
    orch = Orchestrator(claude_client=mock_claude)
    return orch
