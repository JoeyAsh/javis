"""Unit + integration tests for :mod:`brain.conversation_mode`.

Covers:
- Window arming / expiry via wall-clock monkey-patching.
- Sleep-phrase detection (case-insensitive, word-boundary, DE + EN).
- ``closing_phrase`` salutation interpolation.
- ``from_config`` merging of sleep + closing phrase lists with defaults.
- ``api.ws_server._arm_follow_up_window`` broadcasts the expected
  ``conversation_mode`` WS message and transitions the connection.
- Sleep-phrase short-circuit in ``_run_voice_pipeline`` closes the
  window cleanly instead of re-arming.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

from brain.conversation_mode import ConversationMode


class TestWindowLifecycle:
    """Window arming, in_window flag, and expiry behaviour."""

    def test_begin_window_flips_in_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Arming flips ``in_window`` True; expiry flips it False."""
        now = {"t": 1000.0}
        monkeypatch.setattr(
            "brain.conversation_mode.time.time", lambda: now["t"]
        )

        cm = ConversationMode(window_seconds=5.0)
        assert cm.in_window() is False

        cm.begin_window()
        assert cm.in_window() is True
        assert cm.seconds_remaining() == pytest.approx(5.0, abs=0.01)

        # Halfway through the window
        now["t"] = 1002.5
        assert cm.in_window() is True
        assert cm.seconds_remaining() == pytest.approx(2.5, abs=0.01)

        # Past the window
        now["t"] = 1006.0
        assert cm.in_window() is False
        assert cm.seconds_remaining() == 0.0

    def test_disabled_window_never_arms(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With ``enabled=False``, begin_window is a no-op."""
        monkeypatch.setattr(
            "brain.conversation_mode.time.time", lambda: 1000.0
        )
        cm = ConversationMode(window_seconds=5.0, enabled=False)

        cm.begin_window()

        assert cm.in_window() is False
        assert cm.seconds_remaining() == 0.0

    def test_end_window_closes_immediately(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """end_window() drops the deadline to 0 even mid-window."""
        now = {"t": 1000.0}
        monkeypatch.setattr(
            "brain.conversation_mode.time.time", lambda: now["t"]
        )

        cm = ConversationMode(window_seconds=10.0)
        cm.begin_window()
        now["t"] = 1002.0  # still inside

        cm.end_window()

        assert cm.in_window() is False
        assert cm.seconds_remaining() == 0.0


class TestSleepPhraseDetection:
    """Sleep phrase matching — case-insensitive, word-boundary, both langs."""

    def test_exact_match_de(self) -> None:
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("danke", "de") is True
        assert cm.detect_sleep_phrase("Danke.", "de") is True
        assert cm.detect_sleep_phrase("  DANKE ", "de") is True

    def test_exact_match_en(self) -> None:
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("thanks", "en") is True
        assert cm.detect_sleep_phrase("Bye.", "en") is True

    def test_word_boundary_avoids_partial_match(self) -> None:
        """``dankbar`` ('grateful') must not trigger a ``danke`` match."""
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("dankbar bin ich", "de") is False

    def test_whole_word_embedded_match(self) -> None:
        """A sleep phrase embedded as a whole word still matches."""
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("okay, danke nochmal", "de") is True

    def test_empty_text_returns_false(self) -> None:
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("", "de") is False
        assert cm.detect_sleep_phrase("   ", "de") is False

    def test_unknown_language_falls_back_to_combined(self) -> None:
        """Unknown language codes fall back to DE + EN union."""
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("thanks", "xx") is True
        assert cm.detect_sleep_phrase("danke", "xx") is True
        assert cm.detect_sleep_phrase("hello world", "xx") is False

    def test_non_sleep_phrase_returns_false(self) -> None:
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("was ist das wetter", "de") is False
        assert cm.detect_sleep_phrase("what's the weather", "en") is False


class TestSleepPhraseTerminalAndShortUtterance:
    """Regression suite: mid-sentence phrases must NOT trigger close.

    Rules enforced:
      1. Exact match → close.
      2. ≤ 4 tokens containing the phrase → close.
      3. Phrase at end of utterance → close.
      Otherwise → do NOT close.
    """

    # ---- cases that MUST match (return True) --------------------------------

    def test_standalone_danke(self) -> None:
        """Exact match, single token."""
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("danke", "de") is True

    def test_standalone_tschuess(self) -> None:
        """Exact match with trailing punctuation stripped."""
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("tschüss!", "de") is True

    def test_terminal_ok_jarvis_danke(self) -> None:
        """'danke' is the last token → terminal match."""
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("ok jarvis, danke", "de") is True

    def test_short_utterance_danke_dir(self) -> None:
        """2 tokens, phrase present → short-utterance match."""
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("danke dir", "de") is True

    def test_terminal_das_wars_tschuess(self) -> None:
        """Multi-word phrase terminal: 'das war's, tschüss'."""
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("das war's, tschüss", "de") is True

    def test_short_utterance_en_thanks_jarvis(self) -> None:
        """2-token EN utterance containing 'thanks'."""
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("thanks jarvis", "en") is True

    def test_terminal_en_phrase(self) -> None:
        """'ok, see you' — 'see you' is terminal."""
        cm = ConversationMode()
        assert cm.detect_sleep_phrase("ok, see you", "en") is True

    # ---- cases that must NOT match (return False) ---------------------------

    def test_no_match_danke_mid_long_de(self) -> None:
        """'danke' appears mid-sentence in a long DE utterance → no close."""
        cm = ConversationMode()
        assert (
            cm.detect_sleep_phrase(
                "Danke für die Info, kannst du noch das Licht anmachen?", "de"
            )
            is False
        )

    def test_no_match_danke_mid_long_de_variant(self) -> None:
        """Second DE long-utterance variant."""
        cm = ConversationMode()
        assert (
            cm.detect_sleep_phrase(
                "Danke, dass du mir das erklärst — kannst du mir noch was zeigen?", "de"
            )
            is False
        )

    def test_no_match_danke_mid_conjunction(self) -> None:
        """'Danke, und kannst du...' — phrase is not terminal, >4 tokens."""
        cm = ConversationMode()
        assert (
            cm.detect_sleep_phrase(
                "Danke, und kannst du die Lichter bitte einschalten?", "de"
            )
            is False
        )

    def test_no_match_thanks_mid_long_en(self) -> None:
        """'thanks' in the middle of a long EN sentence."""
        cm = ConversationMode()
        assert (
            cm.detect_sleep_phrase(
                "thanks for the update, can you also tell me the weather?", "en"
            )
            is False
        )

    def test_no_match_thanks_non_terminal_en(self) -> None:
        """'thanks' appears but is not terminal; utterance is long."""
        cm = ConversationMode()
        assert (
            cm.detect_sleep_phrase(
                "I was going to say thanks but actually wait", "en"
            )
            is False
        )


class TestClosingPhrase:
    """closing_phrase salutation interpolation."""

    def test_de_interpolates_salutation(self) -> None:
        cm = ConversationMode(
            closing_phrases={
                "de": ["Gern, {sal}."],
                "en": ["Anytime, {sal}."],
            }
        )
        assert cm.closing_phrase("de", "Johannes") == "Gern, Johannes."

    def test_en_interpolates_salutation(self) -> None:
        cm = ConversationMode(
            closing_phrases={
                "de": ["Gern, {sal}."],
                "en": ["Anytime, {sal}."],
            }
        )
        assert cm.closing_phrase("en", "Sir") == "Anytime, Sir."

    def test_unknown_language_falls_back_to_de(self) -> None:
        """Missing language key falls back to German pool."""
        cm = ConversationMode(
            closing_phrases={
                "de": ["Fallback, {sal}."],
                "en": [],
            }
        )
        assert cm.closing_phrase("fr", "Sir") == "Fallback, Sir."

    def test_empty_pool_returns_empty_string(self) -> None:
        cm = ConversationMode(closing_phrases={"de": [], "en": []})
        assert cm.closing_phrase("de", "Sir") == ""


class TestFromConfig:
    """``from_config`` merging behaviour."""

    def test_none_config_uses_defaults(self) -> None:
        cm = ConversationMode.from_config(None)
        assert cm.enabled is True
        assert cm.window_seconds == 18.0
        # Default DE list must contain the canonical 'danke'
        assert "danke" in cm.sleep_phrases["de"]
        # Default closing pool uses the {sal} template
        assert any("{sal}" in p for p in cm.closing_phrases["de"])

    def test_custom_window_seconds(self) -> None:
        cm = ConversationMode.from_config({"follow_up_window_seconds": 25})
        assert cm.window_seconds == 25.0

    def test_override_sleep_phrases_merges(self) -> None:
        """Supplied DE list replaces DE defaults; EN untouched."""
        cm = ConversationMode.from_config(
            {"sleep_phrases": {"de": ["alles klar"]}}
        )
        assert cm.sleep_phrases["de"] == ["alles klar"]
        # EN default preserved
        assert "thanks" in cm.sleep_phrases["en"]

    def test_override_closing_phrases_merges(self) -> None:
        cm = ConversationMode.from_config(
            {"closing_phrases": {"en": ["Cheers, {sal}."]}}
        )
        assert cm.closing_phrases["en"] == ["Cheers, {sal}."]
        # DE default preserved
        assert any("{sal}" in p for p in cm.closing_phrases["de"])

    def test_disabled_via_config(self) -> None:
        cm = ConversationMode.from_config({"enabled": False})
        assert cm.enabled is False

    def test_invalid_phrases_value_is_ignored(self) -> None:
        """Non-list phrase values are silently skipped, defaults kept."""
        cm = ConversationMode.from_config(
            {"sleep_phrases": {"de": "not-a-list"}}  # type: ignore[dict-item]
        )
        # DE default preserved because the value wasn't a list
        assert "danke" in cm.sleep_phrases["de"]


# ---------------------------------------------------------------------------
# Integration tests against ``api.ws_server`` follow-up wiring.
#
# These drive the real ws_server helpers (``_arm_follow_up_window``,
# ``_close_follow_up_window``, ``_follow_up_expiry_task``) using a fake
# WebSocket that captures the outbound frames. Nothing is mocked beyond
# the wire — the module-level state is reset via fixtures so tests do
# not leak into each other.
# ---------------------------------------------------------------------------


class _FakeWs:
    """Minimal WS stand-in — records every frame sent via ``send_str``."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_str(self, message: str) -> None:
        self.sent.append(message)


@pytest.fixture
def ws_server_module() -> Any:
    """Import ws_server lazily and reset module-level state between tests."""
    from api import ws_server as mod

    # Snapshot + restore the module globals we touch, so tests remain
    # hermetic and order-independent.
    keys = (
        "_conversation_mode",
        "_persona_config",
        "_wake_word_detector",
        "_fish_tts",
        "_stt_engine",
        "_orchestrator",
        "_intent_parser",
        "_filler_cache",
    )
    saved = {k: getattr(mod, k) for k in keys}
    mod._connected_clients.clear()
    mod._connection_state.clear()
    try:
        yield mod
    finally:
        for k, v in saved.items():
            setattr(mod, k, v)
        mod._connected_clients.clear()
        mod._connection_state.clear()


@pytest.mark.asyncio
async def test_arm_follow_up_broadcasts_conversation_mode_message(
    ws_server_module: Any,
) -> None:
    """Arming the follow-up window emits an active=true WS frame."""
    mod = ws_server_module
    mod._conversation_mode = ConversationMode(window_seconds=5.0)

    ws = _FakeWs()
    mod._connected_clients.add(ws)
    mod._connection_state[id(ws)] = {
        "mode": "processing",
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
        "follow_up_timer_task": None,
    }

    try:
        await mod._arm_follow_up_window(ws)  # type: ignore[arg-type]

        # Inspect the emitted frames: we expect a conversation_mode + a
        # listening status frame, both broadcast in this order.
        types = [json.loads(m).get("type") for m in ws.sent]
        assert "conversation_mode" in types
        assert "status" in types

        cm_frame = next(
            json.loads(m) for m in ws.sent if json.loads(m)["type"] == "conversation_mode"
        )
        assert cm_frame["payload"]["active"] is True
        assert cm_frame["payload"]["seconds_remaining"] == pytest.approx(5.0, abs=0.5)

        # Connection state flipped to follow_up, timer scheduled.
        state = mod._connection_state[id(ws)]
        assert state["mode"] == "follow_up"
        assert state["follow_up_timer_task"] is not None
    finally:
        # Cancel the expiry task so it doesn't leak into the next test.
        state = mod._connection_state[id(ws)]
        timer = state.get("follow_up_timer_task")
        if timer is not None and not timer.done():
            timer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await timer


@pytest.mark.asyncio
async def test_close_follow_up_window_broadcasts_inactive(
    ws_server_module: Any,
) -> None:
    """Closing the window emits an active=false WS frame and resets mode."""
    mod = ws_server_module
    mod._conversation_mode = ConversationMode(window_seconds=5.0)

    ws = _FakeWs()
    mod._connected_clients.add(ws)
    mod._connection_state[id(ws)] = {
        "mode": "follow_up",
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
        "follow_up_timer_task": None,
    }
    mod._conversation_mode.begin_window()

    await mod._close_follow_up_window(id(ws), "sleep")

    frames = [json.loads(m) for m in ws.sent]
    cm_frames = [f for f in frames if f["type"] == "conversation_mode"]
    assert cm_frames, "expected at least one conversation_mode frame"
    assert cm_frames[-1]["payload"]["active"] is False
    assert cm_frames[-1]["payload"]["seconds_remaining"] == 0.0

    state = mod._connection_state[id(ws)]
    assert state["mode"] == "idle"
    assert mod._conversation_mode.in_window() is False


@pytest.mark.asyncio
async def test_follow_up_expiry_task_returns_to_idle(
    ws_server_module: Any,
) -> None:
    """Expiry task broadcasts idle + conversation_mode inactive when time is up."""
    mod = ws_server_module
    mod._conversation_mode = ConversationMode(window_seconds=0.05)

    ws = _FakeWs()
    mod._connected_clients.add(ws)
    mod._connection_state[id(ws)] = {
        "mode": "follow_up",
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
        "follow_up_timer_task": None,
    }
    mod._conversation_mode.begin_window()

    await mod._follow_up_expiry_task(id(ws), 0.05)

    frames = [json.loads(m) for m in ws.sent]
    # Last idle broadcast should appear
    status_frames = [f for f in frames if f["type"] == "status"]
    assert status_frames[-1]["state"] == "idle"
    # conversation_mode inactive also emitted
    cm_inactive = [
        f for f in frames
        if f["type"] == "conversation_mode" and f["payload"]["active"] is False
    ]
    assert cm_inactive


@pytest.mark.asyncio
async def test_sleep_phrase_short_circuits_pipeline(
    ws_server_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_run_voice_pipeline`` detects a sleep phrase and closes cleanly.

    Fakes STT to return ``"danke"``, fakes TTS to return short audio,
    and asserts: no orchestrator call, closing-line transcript is
    broadcast, connection ends in idle (no follow-up re-arm).
    """
    import numpy as np

    mod = ws_server_module
    mod._conversation_mode = ConversationMode(window_seconds=18.0)
    mod._persona_config = {"salutation_mode": "fixed", "salutation_pool": ["Sir"]}

    # Fake STT
    class _FakeSTT:
        async def transcribe(self, _audio: Any) -> SimpleNamespace:
            return SimpleNamespace(text="danke", language="de")

    mod._stt_engine = _FakeSTT()  # type: ignore[assignment]

    # Fake TTS
    class _FakeTTS:
        async def synthesize(self, _text: str, **_kwargs: Any) -> bytes:
            return b"\x00" * 4000

    mod._fish_tts = _FakeTTS()  # type: ignore[assignment]

    # Orchestrator must NEVER be called on a sleep phrase — trip a sentinel.
    called: dict[str, bool] = {"orchestrator": False}

    class _FakeOrchestrator:
        async def process(self, **_kwargs: Any) -> Any:
            called["orchestrator"] = True
            return SimpleNamespace(spoken_response="should-not-speak")

        async def process_stream(self, **_kwargs: Any):
            called["orchestrator"] = True
            from integrations.openclaw.ws_client import StreamChunk
            yield StreamChunk(type="final", run_id="local",
                              new_text="should-not-speak", full_text="should-not-speak")

    class _FakeIntent:
        async def classify_intent(self, _text: str, _lang: str) -> Any:
            return SimpleNamespace(intent="chat", confidence=1.0)

    mod._orchestrator = _FakeOrchestrator()  # type: ignore[assignment]
    mod._intent_parser = _FakeIntent()  # type: ignore[assignment]

    # Neutralise the playback sleep so the test doesn't stall 1.2 s.
    async def _fast_sleep(_s: float) -> None:
        return None

    monkeypatch.setattr(mod.asyncio, "sleep", _fast_sleep)

    ws = _FakeWs()
    mod._connected_clients.add(ws)
    mod._connection_state[id(ws)] = {
        "mode": "processing",
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
        "follow_up_timer_task": None,
        "pipeline_task": None,
        "current_run_id": None,
        "current_session_id": None,
    }

    # Feed enough synthetic audio for the length guard (>= 0.5 s at 16 kHz).
    chunks = [np.zeros(8000, dtype=np.float32), np.zeros(8000, dtype=np.float32)]
    await mod._run_voice_pipeline(chunks, ws)  # type: ignore[arg-type]

    # Orchestrator was bypassed.
    assert called["orchestrator"] is False

    # Frames: transcript (user) + transcript (jarvis closing) + speaking
    # + audio + idle. No follow_up arm afterward.
    frames = [json.loads(m) for m in ws.sent]
    jarvis_transcripts = [
        f for f in frames
        if f["type"] == "transcript" and f["payload"]["role"] == "jarvis"
    ]
    assert jarvis_transcripts, "expected a JARVIS closing-line transcript"
    assert "Sir" in jarvis_transcripts[0]["payload"]["text"]

    status_frames = [f for f in frames if f["type"] == "status"]
    assert status_frames[-1]["state"] == "idle"

    # No lingering follow_up state.
    assert mod._connection_state[id(ws)]["mode"] == "idle"
    assert mod._conversation_mode.in_window() is False


@pytest.mark.asyncio
async def test_successful_turn_arms_follow_up(
    ws_server_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-sleep-phrase turn ends with a follow-up window, not idle.

    Also asserts a quick-ack filler audio frame is broadcast *before* the
    real LLM response (mask of the 7-11 s LLM round-trip).
    """
    import numpy as np

    mod = ws_server_module
    mod._conversation_mode = ConversationMode(window_seconds=18.0)
    mod._persona_config = {"salutation_mode": "fixed", "salutation_pool": ["Sir"]}
    mod._filler_cache = {"de": [("Moment", b"FILLER-BYTES")]}

    class _FakeSTT:
        async def transcribe(self, _audio: Any) -> SimpleNamespace:
            return SimpleNamespace(text="was ist das wetter", language="de")

    class _FakeTTS:
        async def synthesize(self, _text: str, **_kwargs: Any) -> bytes:
            return b"REAL-AUDIO-BYTES" * 64

    class _FakeIntent:
        async def classify_intent(self, _text: str, _lang: str) -> Any:
            return SimpleNamespace(intent="chat", confidence=1.0)

    class _FakeOrchestrator:
        async def process(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(spoken_response="Es ist sonnig.")

        async def process_stream(self, **_kwargs: Any):
            from integrations.openclaw.ws_client import StreamChunk
            yield StreamChunk(
                type="final", run_id="local",
                new_text="Es ist sonnig.", full_text="Es ist sonnig.",
            )

    mod._stt_engine = _FakeSTT()  # type: ignore[assignment]
    mod._fish_tts = _FakeTTS()  # type: ignore[assignment]
    mod._intent_parser = _FakeIntent()  # type: ignore[assignment]
    mod._orchestrator = _FakeOrchestrator()  # type: ignore[assignment]
    mod._openclaw_client = SimpleNamespace(session_id="jarvis-main")  # type: ignore[assignment]

    async def _fast_sleep(_s: float) -> None:
        return None

    monkeypatch.setattr(mod.asyncio, "sleep", _fast_sleep)

    ws = _FakeWs()
    mod._connected_clients.add(ws)
    mod._connection_state[id(ws)] = {
        "mode": "processing",
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
        "follow_up_timer_task": None,
        "pipeline_task": None,
        "current_run_id": None,
        "current_session_id": None,
    }

    chunks = [np.zeros(8000, dtype=np.float32), np.zeros(8000, dtype=np.float32)]
    try:
        await mod._run_voice_pipeline(chunks, ws)  # type: ignore[arg-type]

        # Connection is in follow_up mode, window is armed, timer exists.
        state = mod._connection_state[id(ws)]
        assert state["mode"] == "follow_up"
        assert state["follow_up_timer_task"] is not None
        assert mod._conversation_mode.in_window() is True

        frames = [json.loads(m) for m in ws.sent]

        # Last conversation_mode frame is active=True
        cm_frames = [f for f in frames if f["type"] == "conversation_mode"]
        assert cm_frames[-1]["payload"]["active"] is True

        # At least two audio frames: the filler (broadcast first) + the real answer.
        audio_frames = [f for f in frames if f["type"] == "audio"]
        assert len(audio_frames) >= 2
        assert audio_frames[0]["text"] == "Moment"
        # The response sentence should appear in one of the subsequent audio frames.
        real_audio = [f for f in audio_frames[1:] if "sonnig" in f.get("text", "")]
        assert real_audio, "Expected a frame containing the TTS sentence 'Es ist sonnig.'"
    finally:
        timer = mod._connection_state[id(ws)].get("follow_up_timer_task")
        if timer is not None and not timer.done():
            timer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await timer
