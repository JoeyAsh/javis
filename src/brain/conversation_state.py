"""Conversational state machine for JARVIS.

Tracks the voice-turn lifecycle: idle → listening → speaking → active_dialogue.
Used by the NarrationQueue to decide when it is safe to emit background TTS.
"""

from __future__ import annotations

import asyncio
from enum import Enum

from utils.logger import get_logger

logger = get_logger("conversation_state")

# How long (seconds) active_dialogue persists without a new user utterance.
_ACTIVE_DIALOGUE_TIMEOUT_S: float = 8.0
# Silence buffer (seconds) added between on_tts_end() and the state returning
# to idle, giving the user a moment to barge in without the drainer jumping in.
_TTS_SILENCE_BUFFER_S: float = 0.5


class ConversationState(str, Enum):
    """States of the JARVIS voice-turn lifecycle."""

    IDLE = "idle"
    LISTENING = "listening"  # mic open, wake-word armed
    SPEAKING = "speaking"  # JARVIS currently producing TTS
    ACTIVE_DIALOGUE = "active_dialogue"  # user spoke within the last N seconds


class ConversationStateMachine:
    """Lightweight finite-state machine for the JARVIS voice lifecycle.

    Transitions are driven by caller-invoked event methods; internal asyncio
    Tasks handle time-based exits (dialogue idle timeout and TTS silence
    buffer).
    """

    def __init__(
        self,
        active_dialogue_timeout_s: float = _ACTIVE_DIALOGUE_TIMEOUT_S,
        tts_silence_buffer_s: float = _TTS_SILENCE_BUFFER_S,
    ) -> None:
        """Initialise the state machine in the IDLE state.

        Args:
            active_dialogue_timeout_s: Seconds before active_dialogue reverts
                to idle when no new user utterance arrives.
            tts_silence_buffer_s: Seconds of silence after TTS ends before
                state reverts to idle.
        """
        self._state: ConversationState = ConversationState.IDLE
        self._active_dialogue_timeout_s = active_dialogue_timeout_s
        self._tts_silence_buffer_s = tts_silence_buffer_s

        # Event that fires whenever the machine enters IDLE — used by
        # wait_for_idle() and the NarrationQueue drainer.
        self._idle_event: asyncio.Event = asyncio.Event()
        self._idle_event.set()  # starts idle

        # Handles for cancellable background timeout tasks.
        self._dialogue_timeout_task: asyncio.Task[None] | None = None
        self._tts_silence_task: asyncio.Task[None] | None = None

    # -----------------------------------------------------------------------
    # Public state access
    # -----------------------------------------------------------------------

    @property
    def state(self) -> ConversationState:
        """Return the current conversation state."""
        return self._state

    @property
    def is_idle(self) -> bool:
        """Return True when state is IDLE."""
        return self._state == ConversationState.IDLE

    # -----------------------------------------------------------------------
    # Event methods (called by ws_server hooks)
    # -----------------------------------------------------------------------

    def on_wake_word(self) -> None:
        """Transition to LISTENING when wake word fires."""
        self._cancel_timeout_tasks()
        self._set_state(ConversationState.LISTENING)

    def on_user_utterance_finalized(self) -> None:
        """Transition to ACTIVE_DIALOGUE when STT finalizes a non-empty transcript."""
        self._cancel_timeout_tasks()
        self._set_state(ConversationState.ACTIVE_DIALOGUE)
        self._dialogue_timeout_task = asyncio.ensure_future(
            self._dialogue_idle_timeout_after(self._active_dialogue_timeout_s)
        )

    def on_tts_start(self) -> None:
        """Transition to SPEAKING when JARVIS starts TTS playback."""
        self._cancel_timeout_tasks()
        self._set_state(ConversationState.SPEAKING)

    def on_tts_end(self) -> None:
        """Schedule idle revert after TTS finishes (with silence buffer)."""
        self._cancel_timeout_tasks()
        self._tts_silence_task = asyncio.ensure_future(
            self._revert_to_idle_after(self._tts_silence_buffer_s)
        )

    def on_dialogue_idle_timeout(self) -> None:
        """Immediately revert from ACTIVE_DIALOGUE to IDLE."""
        self._cancel_timeout_tasks()
        self._set_state(ConversationState.IDLE)

    # -----------------------------------------------------------------------
    # Async helper
    # -----------------------------------------------------------------------

    async def wait_for_idle(self, timeout: float | None = None) -> bool:
        """Block until state is IDLE or timeout expires.

        Args:
            timeout: Maximum seconds to wait. None means wait indefinitely.

        Returns:
            True if the machine reached IDLE, False if timeout elapsed first.
        """
        if self._state == ConversationState.IDLE:
            return True
        try:
            await asyncio.wait_for(self._idle_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _set_state(self, new_state: ConversationState) -> None:
        if new_state == self._state:
            return
        logger.debug(f"ConversationState: {self._state.value} → {new_state.value}")
        self._state = new_state
        if new_state == ConversationState.IDLE:
            self._idle_event.set()
        else:
            self._idle_event.clear()

    def _cancel_timeout_tasks(self) -> None:
        for task in (self._dialogue_timeout_task, self._tts_silence_task):
            if task is not None and not task.done():
                task.cancel()
        self._dialogue_timeout_task = None
        self._tts_silence_task = None

    async def _revert_to_idle_after(self, delay_s: float) -> None:
        try:
            await asyncio.sleep(delay_s)
            self._set_state(ConversationState.IDLE)
        except asyncio.CancelledError:
            pass

    async def _dialogue_idle_timeout_after(self, delay_s: float) -> None:
        try:
            await asyncio.sleep(delay_s)
            if self._state == ConversationState.ACTIVE_DIALOGUE:
                logger.debug("Active dialogue timeout — reverting to idle")
                self._set_state(ConversationState.IDLE)
        except asyncio.CancelledError:
            pass
