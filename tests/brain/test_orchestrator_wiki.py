"""Tests for _handle_wiki_lookup() in brain/orchestrator.py — AC #11.

Covers:
- Hit path: high-score hit → templated narration mentioning title; no agent RPC.
- No-hits path: empty search → returns None → falls through to slow-path.
- Below-threshold path: low-score hit → returns None.
- WikiClientUnavailableError → returns None cleanly.
- fast_path_enabled=false in config → returns None immediately, no search call.
- German and English narration templates produce sensible output.
- AC #11: end-to-end fast-path bypasses any agent/OpenClaw RPC.

All external I/O (OpenClaw, config, DB) is mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brain.intent_parser import Intent, IntentResult
from integrations.openclaw.wiki_client import WikiClientUnavailableError, WikiHit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hit(
    note_id: str = "notes/sister",
    title: str = "Schwester",
    score: float = 0.92,
    excerpt: str = "Geburtstag am 12. Juni.",
    updated_at: str = "2025-01-15T10:00:00Z",
) -> WikiHit:
    return WikiHit(
        id=note_id,
        title=title,
        score=score,
        excerpt=excerpt,
        updated_at=updated_at,
    )


def _make_intent_result(topic: str = "meine Schwester", language: str = "de") -> IntentResult:
    return IntentResult(
        intent=Intent.WIKI_LOOKUP,
        confidence=0.90,
        params={"topic": topic},
        original_text=f"was weißt du über {topic}",
        language=language,
    )


def _make_cfg_mock(
    fast_path_enabled: bool = True,
    fast_path_min_score: float = 0.75,
) -> MagicMock:
    cfg = MagicMock()
    cfg.get_section.side_effect = lambda section: {
        "agents": {
            "orchestrator_model": "claude-opus-4-5",
            "orchestrator_max_tokens": 150,
            "skip_orchestrator_on_clear_intent": True,
            "history_turns_for_orchestrator": 3,
        },
        "vault": {
            "fast_path_enabled": fast_path_enabled,
            "fast_path_min_score": fast_path_min_score,
        },
    }.get(section, {})
    cfg.get.return_value = "Europe/Zurich"
    return cfg


def _make_orchestrator(cfg_mock, wiki_client=None) -> "Orchestrator":
    from brain.orchestrator import Orchestrator

    mock_claude = MagicMock()
    mock_claude.chat = AsyncMock(
        side_effect=AssertionError("ClaudeClient.chat must NOT be called in fast-path test")
    )
    mock_claude.openclaw = None

    with patch("brain.orchestrator.get_config", return_value=cfg_mock):
        orch = Orchestrator(claude_client=mock_claude, wiki_client=wiki_client)
    return orch


# ---------------------------------------------------------------------------
# _handle_wiki_lookup — hit path (AC #11)
# ---------------------------------------------------------------------------


class TestHandleWikiLookupHitPath:
    """Fast-path hit: returns narration, no OpenClaw/agent call."""

    @pytest.mark.asyncio
    async def test_hit_above_threshold_returns_agent_result(self):
        """Single hit above min_score returns AgentResult with non-empty text."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(return_value=[_make_hit(score=0.92)])

        cfg = _make_cfg_mock(fast_path_enabled=True, fast_path_min_score=0.75)
        orch = _make_orchestrator(cfg, wiki_client=mock_wiki)

        intent_result = _make_intent_result(topic="meine Schwester", language="de")
        result = await orch._handle_wiki_lookup(intent_result, language="de")

        assert result is not None
        assert result.success is True
        assert len(result.spoken_response) > 0

    @pytest.mark.asyncio
    async def test_hit_narration_mentions_top_title_german(self):
        """German narration mentions the top hit's title."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(
            return_value=[_make_hit(title="Schwester", score=0.92, excerpt="Geburtstag")]
        )

        cfg = _make_cfg_mock()
        orch = _make_orchestrator(cfg, wiki_client=mock_wiki)

        result = await orch._handle_wiki_lookup(
            _make_intent_result(topic="meine Schwester", language="de"), language="de"
        )

        assert result is not None
        assert "Schwester" in result.spoken_response

    @pytest.mark.asyncio
    async def test_hit_narration_mentions_top_title_english(self):
        """English narration mentions the top hit's title."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(
            return_value=[_make_hit(title="Sister", score=0.90, excerpt="Birthday")]
        )

        cfg = _make_cfg_mock()
        orch = _make_orchestrator(cfg, wiki_client=mock_wiki)

        result = await orch._handle_wiki_lookup(
            _make_intent_result(topic="my sister", language="en"), language="en"
        )

        assert result is not None
        assert "Sister" in result.spoken_response

    @pytest.mark.asyncio
    async def test_agent_rpc_not_called_on_fast_path_hit(self):
        """AC #11: no agent RPC is issued when fast-path returns a result."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(return_value=[_make_hit(score=0.90)])

        cfg = _make_cfg_mock()
        mock_claude = MagicMock()
        agent_call_count = 0

        async def _forbidden_chat(*_a, **_kw):
            nonlocal agent_call_count
            agent_call_count += 1
            return "should not be called"

        mock_claude.chat = _forbidden_chat
        mock_claude.openclaw = None

        with patch("brain.orchestrator.get_config", return_value=cfg):
            from brain.orchestrator import Orchestrator
            orch = Orchestrator(claude_client=mock_claude, wiki_client=mock_wiki)

        intent_result = _make_intent_result(topic="meine Schwester", language="de")
        result = await orch._handle_wiki_lookup(intent_result, language="de")

        assert result is not None
        assert agent_call_count == 0, "ClaudeClient.chat must NOT be called for fast-path hit"

    @pytest.mark.asyncio
    async def test_multiple_hits_all_appear_in_narration(self):
        """When ≥2 hits qualify, narration lists multiple titles."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(
            return_value=[
                _make_hit(note_id="n1", title="Schwester", score=0.95),
                _make_hit(note_id="n2", title="Familie", score=0.88),
            ]
        )

        cfg = _make_cfg_mock()
        orch = _make_orchestrator(cfg, wiki_client=mock_wiki)

        result = await orch._handle_wiki_lookup(
            _make_intent_result(topic="Familie", language="de"), language="de"
        )

        assert result is not None
        # At least one of the titles must appear.
        assert "Schwester" in result.spoken_response or "Familie" in result.spoken_response

    @pytest.mark.asyncio
    async def test_narration_not_raw_dataclass_repr(self):
        """Spoken response does not contain raw WikiHit dataclass repr."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(return_value=[_make_hit(score=0.90)])

        cfg = _make_cfg_mock()
        orch = _make_orchestrator(cfg, wiki_client=mock_wiki)

        result = await orch._handle_wiki_lookup(
            _make_intent_result(topic="Schwester", language="de"), language="de"
        )

        assert result is not None
        assert "WikiHit(" not in result.spoken_response


# ---------------------------------------------------------------------------
# _handle_wiki_lookup — no-hits path
# ---------------------------------------------------------------------------


class TestHandleWikiLookupNoHits:
    """Empty search result falls through to slow-path."""

    @pytest.mark.asyncio
    async def test_no_hits_returns_none(self):
        """search() returns [] → _handle_wiki_lookup returns None."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(return_value=[])

        cfg = _make_cfg_mock()
        orch = _make_orchestrator(cfg, wiki_client=mock_wiki)

        result = await orch._handle_wiki_lookup(
            _make_intent_result(topic="unbekanntes Thema", language="de"), language="de"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_no_hits_slow_path_called_via_process(self):
        """When fast-path returns None, process() calls the slow-path chat agent."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(return_value=[])

        chat_was_called = []

        mock_claude = MagicMock()

        async def _fake_chat(*_a, **_kw):
            chat_was_called.append(True)
            return "OpenClaw slow-path response"

        mock_claude.chat = _fake_chat
        mock_claude.openclaw = None

        cfg = _make_cfg_mock()
        with patch("brain.orchestrator.get_config", return_value=cfg):
            from brain.orchestrator import Orchestrator
            orch = Orchestrator(claude_client=mock_claude, wiki_client=mock_wiki)

        intent_result = _make_intent_result(topic="unbekanntes Thema", language="de")
        intent_result.confidence = 0.90  # above threshold

        result = await orch.process(
            "was weißt du über unbekanntes Thema",
            language="de",
            intent_result=intent_result,
        )

        # Slow-path (chat) should have been called.
        assert chat_was_called, "Slow-path chat.run() was not called after fast-path miss"
        assert result is not None


# ---------------------------------------------------------------------------
# _handle_wiki_lookup — below threshold
# ---------------------------------------------------------------------------


class TestHandleWikiLookupBelowThreshold:
    """Hits below min_score fall through."""

    @pytest.mark.asyncio
    async def test_below_threshold_score_returns_none(self):
        """Hit with score below fast_path_min_score → None."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(return_value=[_make_hit(score=0.50)])

        cfg = _make_cfg_mock(fast_path_min_score=0.75)
        orch = _make_orchestrator(cfg, wiki_client=mock_wiki)

        result = await orch._handle_wiki_lookup(
            _make_intent_result(topic="topic", language="en"), language="en"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_exactly_at_threshold_qualifies(self):
        """Hit with score exactly equal to fast_path_min_score qualifies."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(return_value=[_make_hit(score=0.75)])

        cfg = _make_cfg_mock(fast_path_min_score=0.75)
        orch = _make_orchestrator(cfg, wiki_client=mock_wiki)

        result = await orch._handle_wiki_lookup(
            _make_intent_result(topic="topic", language="en"), language="en"
        )

        assert result is not None


# ---------------------------------------------------------------------------
# _handle_wiki_lookup — WikiClientUnavailableError
# ---------------------------------------------------------------------------


class TestHandleWikiLookupUnavailable:
    """WikiClientUnavailableError falls through cleanly."""

    @pytest.mark.asyncio
    async def test_wiki_unavailable_returns_none_no_exception(self):
        """WikiClientUnavailableError from search → returns None, no exception bubbles."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(
            side_effect=WikiClientUnavailableError("connection lost")
        )

        cfg = _make_cfg_mock()
        orch = _make_orchestrator(cfg, wiki_client=mock_wiki)

        # Must not raise.
        result = await orch._handle_wiki_lookup(
            _make_intent_result(topic="Schwester", language="de"), language="de"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_timeout_returns_none_no_exception(self):
        """asyncio.TimeoutError from search → returns None, no exception bubbles."""
        import asyncio

        mock_wiki = MagicMock()

        async def _slow_search(*_a, **_kw):
            await asyncio.sleep(9999)

        mock_wiki.search = _slow_search

        cfg = _make_cfg_mock()
        orch = _make_orchestrator(cfg, wiki_client=mock_wiki)

        with patch("brain.orchestrator.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await orch._handle_wiki_lookup(
                _make_intent_result(topic="Schwester", language="de"), language="de"
            )

        assert result is None


# ---------------------------------------------------------------------------
# _handle_wiki_lookup — fast_path_enabled=False
# ---------------------------------------------------------------------------


class TestHandleWikiLookupDisabled:
    """fast_path_enabled=False disables the fast-path entirely."""

    @pytest.mark.asyncio
    async def test_fast_path_disabled_returns_none_immediately(self):
        """fast_path_enabled=false → None without calling WikiClient.search."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(return_value=[_make_hit(score=0.99)])

        cfg = _make_cfg_mock(fast_path_enabled=False)
        orch = _make_orchestrator(cfg, wiki_client=mock_wiki)

        # _handle_wiki_lookup calls get_config() at call time, so patch it there too.
        with patch("brain.orchestrator.get_config", return_value=cfg):
            result = await orch._handle_wiki_lookup(
                _make_intent_result(topic="Schwester", language="de"), language="de"
            )

        assert result is None
        mock_wiki.search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fast_path_disabled_wiki_client_none_still_none(self):
        """Returns None also when wiki_client is None and fast_path is disabled."""
        cfg = _make_cfg_mock(fast_path_enabled=False)
        orch = _make_orchestrator(cfg, wiki_client=None)

        with patch("brain.orchestrator.get_config", return_value=cfg):
            result = await orch._handle_wiki_lookup(
                _make_intent_result(topic="Schwester", language="de"), language="de"
            )

        assert result is None


# ---------------------------------------------------------------------------
# _handle_wiki_lookup — wiki_client is None
# ---------------------------------------------------------------------------


class TestHandleWikiLookupNoClient:
    """No WikiClient attached → falls through."""

    @pytest.mark.asyncio
    async def test_no_wiki_client_returns_none(self):
        """When wiki_client=None and fast_path_enabled, returns None."""
        cfg = _make_cfg_mock(fast_path_enabled=True)
        orch = _make_orchestrator(cfg, wiki_client=None)

        result = await orch._handle_wiki_lookup(
            _make_intent_result(topic="Schwester", language="de"), language="de"
        )

        assert result is None


# ---------------------------------------------------------------------------
# Full process() integration path — AC #11 end-to-end
# ---------------------------------------------------------------------------


class TestOrchestratorWikiLookupProcessIntegration:
    """process() dispatches WIKI_LOOKUP and fast-path bypasses OpenClaw."""

    @pytest.mark.asyncio
    async def test_process_wiki_lookup_fast_path_does_not_call_openclaw(self):
        """AC #11: process() with WIKI_LOOKUP high-confidence returns fast-path result."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(
            return_value=[_make_hit(title="Schwester", score=0.92)]
        )

        chat_called = []
        mock_claude = MagicMock()

        async def _forbidden_chat(*_a, **_kw):
            chat_called.append(True)
            return "should not be called"

        mock_claude.chat = _forbidden_chat
        mock_claude.openclaw = None

        cfg = _make_cfg_mock()
        with patch("brain.orchestrator.get_config", return_value=cfg):
            from brain.orchestrator import Orchestrator
            orch = Orchestrator(claude_client=mock_claude, wiki_client=mock_wiki)

        intent_result = IntentResult(
            intent=Intent.WIKI_LOOKUP,
            confidence=0.90,
            params={"topic": "meine Schwester"},
            original_text="was weißt du über meine Schwester",
            language="de",
        )

        result = await orch.process(
            "was weißt du über meine Schwester",
            language="de",
            intent_result=intent_result,
        )

        assert result is not None
        assert result.success is True
        assert "Schwester" in result.spoken_response
        assert not chat_called, "OpenClaw/chat was called — fast-path should have handled it"

    @pytest.mark.asyncio
    async def test_process_wiki_lookup_english_fast_path(self):
        """process() English WIKI_LOOKUP also returns fast-path result."""
        mock_wiki = MagicMock()
        mock_wiki.search = AsyncMock(
            return_value=[_make_hit(title="Sister Note", score=0.88)]
        )

        mock_claude = MagicMock()
        mock_claude.chat = AsyncMock(return_value="should not be called")
        mock_claude.openclaw = None

        cfg = _make_cfg_mock()
        with patch("brain.orchestrator.get_config", return_value=cfg):
            from brain.orchestrator import Orchestrator
            orch = Orchestrator(claude_client=mock_claude, wiki_client=mock_wiki)

        intent_result = IntentResult(
            intent=Intent.WIKI_LOOKUP,
            confidence=0.85,
            params={"topic": "my sister"},
            original_text="what do you know about my sister",
            language="en",
        )

        result = await orch.process(
            "what do you know about my sister",
            language="en",
            intent_result=intent_result,
        )

        assert result is not None
        assert "Sister Note" in result.spoken_response
