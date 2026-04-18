"""Tests for Spotify intent classification and orchestrator routing.

Verifies that:
- SPOTIFY_* intents are correctly classified by IntentParser for EN and DE.
- SPOTIFY_* intents are NOT in _LOCAL_INTENTS (they fall through to OpenClaw).
- The orchestrator does not hard-dispatch Spotify intents locally.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def parser():
    """Return a live IntentParser instance."""
    from brain.intent_parser import IntentParser

    return IntentParser()


# ---------------------------------------------------------------------------
# Intent.SPOTIFY_PAUSE — English + German
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_music_english(parser):
    """'Pause the music' classifies as SPOTIFY_PAUSE in English."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("Pause the music", language="en")
    assert result.intent == Intent.SPOTIFY_PAUSE
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_pause_spotify_english(parser):
    """'pause spotify' classifies as SPOTIFY_PAUSE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("pause spotify", language="en")
    assert result.intent == Intent.SPOTIFY_PAUSE


@pytest.mark.asyncio
async def test_stop_the_music_english(parser):
    """'Stop the music' classifies as SPOTIFY_PAUSE."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("Stop the music", language="en")
    assert result.intent == Intent.SPOTIFY_PAUSE


@pytest.mark.asyncio
async def test_pause_music_german(parser):
    """'Musik pausieren' classifies as SPOTIFY_PAUSE in German."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("Musik pausieren", language="de")
    assert result.intent == Intent.SPOTIFY_PAUSE
    assert result.confidence >= 0.7


@pytest.mark.asyncio
async def test_anhalten_german(parser):
    """'anhalten' classifies as SPOTIFY_PAUSE in German."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("anhalten", language="de")
    assert result.intent == Intent.SPOTIFY_PAUSE


# ---------------------------------------------------------------------------
# Intent.SPOTIFY_PLAY — English + German
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_music_english(parser):
    """'play music' classifies as SPOTIFY_PLAY."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("play music", language="en")
    assert result.intent == Intent.SPOTIFY_PLAY


@pytest.mark.asyncio
async def test_resume_playback_english(parser):
    """'resume playback' classifies as SPOTIFY_PLAY."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("resume playback", language="en")
    assert result.intent == Intent.SPOTIFY_PLAY


@pytest.mark.asyncio
async def test_musik_abspielen_german(parser):
    """'Musik abspielen' classifies as SPOTIFY_PLAY in German."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("Musik abspielen", language="de")
    assert result.intent == Intent.SPOTIFY_PLAY


# ---------------------------------------------------------------------------
# Intent.SPOTIFY_NEXT — English + German
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_next_song_english(parser):
    """'next song' classifies as SPOTIFY_NEXT."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("next song", language="en")
    assert result.intent == Intent.SPOTIFY_NEXT


@pytest.mark.asyncio
async def test_skip_track_english(parser):
    """'skip this track' classifies as SPOTIFY_NEXT."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("skip this track", language="en")
    assert result.intent == Intent.SPOTIFY_NEXT


@pytest.mark.asyncio
async def test_naechster_titel_german(parser):
    """'nächster Titel' classifies as SPOTIFY_NEXT in German."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("nächster Titel", language="de")
    assert result.intent == Intent.SPOTIFY_NEXT


@pytest.mark.asyncio
async def test_weiter_german(parser):
    """'weiter' classifies as SPOTIFY_NEXT in German."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("weiter", language="de")
    assert result.intent == Intent.SPOTIFY_NEXT


# ---------------------------------------------------------------------------
# Intent.SPOTIFY_PREV — English + German
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_previous_track_english(parser):
    """'previous track' classifies as SPOTIFY_PREV."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("previous track", language="en")
    assert result.intent == Intent.SPOTIFY_PREV


@pytest.mark.asyncio
async def test_vorheriger_song_german(parser):
    """'vorheriger Song' classifies as SPOTIFY_PREV in German."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("vorheriger Song", language="de")
    assert result.intent == Intent.SPOTIFY_PREV


# ---------------------------------------------------------------------------
# Intent.SPOTIFY_VOLUME — English + German
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_volume_up_english(parser):
    """'volume up' classifies as SPOTIFY_VOLUME."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("volume up", language="en")
    assert result.intent == Intent.SPOTIFY_VOLUME


@pytest.mark.asyncio
async def test_lauter_german(parser):
    """'lauter machen' classifies as SPOTIFY_VOLUME in German."""
    from brain.intent_parser import Intent

    result = await parser.classify_intent("lauter machen", language="de")
    assert result.intent == Intent.SPOTIFY_VOLUME


# ---------------------------------------------------------------------------
# Negative check — unrelated utterances must NOT be Spotify intents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_my_email_not_spotify(parser):
    """'check my email' does not classify as any Spotify intent."""
    from brain.intent_parser import Intent

    _SPOTIFY_INTENTS = (
        Intent.SPOTIFY_PLAY,
        Intent.SPOTIFY_PAUSE,
        Intent.SPOTIFY_NEXT,
        Intent.SPOTIFY_PREV,
        Intent.SPOTIFY_VOLUME,
    )
    result = await parser.classify_intent("check my email", language="en")
    assert result.intent not in _SPOTIFY_INTENTS


@pytest.mark.asyncio
async def test_open_chrome_not_spotify(parser):
    """'open chrome' does not classify as any Spotify intent."""
    from brain.intent_parser import Intent

    _SPOTIFY_INTENTS = (
        Intent.SPOTIFY_PLAY,
        Intent.SPOTIFY_PAUSE,
        Intent.SPOTIFY_NEXT,
        Intent.SPOTIFY_PREV,
        Intent.SPOTIFY_VOLUME,
    )
    result = await parser.classify_intent("open chrome", language="en")
    assert result.intent not in _SPOTIFY_INTENTS


# ---------------------------------------------------------------------------
# Orchestrator: SPOTIFY_* not in _LOCAL_INTENTS
# ---------------------------------------------------------------------------


def test_spotify_intents_not_in_local_intents():
    """All SPOTIFY_* intents are absent from _LOCAL_INTENTS — they fall through to OpenClaw."""
    from brain.intent_parser import Intent
    from brain.orchestrator import _LOCAL_INTENTS

    spotify_intents = [
        Intent.SPOTIFY_PLAY,
        Intent.SPOTIFY_PAUSE,
        Intent.SPOTIFY_NEXT,
        Intent.SPOTIFY_PREV,
        Intent.SPOTIFY_VOLUME,
    ]
    for intent in spotify_intents:
        assert intent not in _LOCAL_INTENTS, (
            f"{intent.value} must NOT be in _LOCAL_INTENTS — it should fall through to OpenClaw"
        )


def test_pc_smart_home_system_still_in_local_intents():
    """Existing local intents (PC/smart-home/system) are unaffected by Spotify addition."""
    from brain.intent_parser import Intent
    from brain.orchestrator import _LOCAL_INTENTS

    assert Intent.PC_CONTROL in _LOCAL_INTENTS
    assert Intent.SMART_HOME in _LOCAL_INTENTS
    assert Intent.SYSTEM in _LOCAL_INTENTS


# ---------------------------------------------------------------------------
# Orchestrator: SPOTIFY_PAUSE routes to chat (OpenClaw) not a local agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spotify_intent_routes_to_chat_path():
    """process() with SPOTIFY_PAUSE routes to the chat agent (OpenClaw path)."""
    from brain.agents.base import AgentResult
    from brain.intent_parser import Intent, IntentResult
    from brain.orchestrator import Orchestrator

    mock_claude = MagicMock()

    orch = Orchestrator(claude_client=mock_claude)

    # Replace the chat agent with an async mock that records calls.
    chat_run_calls: list[tuple] = []

    async def _chat_run(text: str, params: dict, language: str) -> AgentResult:
        chat_run_calls.append((text, params, language))
        return AgentResult(spoken_response="Pausing music.", success=True)

    orch._agents["chat"].run = _chat_run  # type: ignore[method-assign]

    intent_result = IntentResult(
        intent=Intent.SPOTIFY_PAUSE,
        confidence=0.85,
        params={},
        original_text="pause the music",
        language="en",
    )

    result = await orch.process("pause the music", language="en", intent_result=intent_result)
    # Chat agent (OpenClaw path) must have been called — not any local agent.
    assert len(chat_run_calls) == 1
    assert result.spoken_response == "Pausing music."
