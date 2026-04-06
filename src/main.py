"""Main entry point for JARVIS voice assistant.

Orchestrates wake word detection, speech recognition, intent processing,
and text-to-speech response generation.
"""

import asyncio
import signal
import sys
from typing import Any

import numpy as np
from dotenv import load_dotenv

from api.ws_server import (
    broadcast_state,
    broadcast_transcript,
    start_ws_server,
)
from audio.microphone import Microphone, create_microphone
from audio.stt import SpeechToText, create_stt_engine
from audio.tts import TTSEngine, create_tts_engine
from audio.wake_word import WakeWordDetector, create_wake_word_detector
from brain.claude_client import create_claude_client
from brain.intent_parser import IntentParser, get_intent_parser
from brain.memory import ConversationMemory
from brain.orchestrator import Orchestrator
from utils.config_loader import get_config
from utils.logger import get_logger, setup_logger

logger = get_logger("main")


class JarvisAssistant:
    """Main JARVIS assistant coordinator."""

    def __init__(self) -> None:
        """Initialize the assistant."""
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Components (initialized in setup)
        self.config: Any = None
        self.microphone: Microphone | None = None
        self.wake_word_detector: WakeWordDetector | None = None
        self.stt_engine: SpeechToText | None = None
        self.tts_engine: TTSEngine | None = None
        self.memory: ConversationMemory | None = None
        self.orchestrator: Orchestrator | None = None
        self.intent_parser: IntentParser | None = None

    async def setup(self) -> None:
        """Initialize all components."""
        # Load environment variables
        load_dotenv()

        # Load configuration
        self.config = get_config()

        # Setup logging
        log_config = self.config.get_section("logging")
        setup_logger(
            level=log_config.get("level", "INFO"),
            log_file=log_config.get("file"),
        )

        logger.info("Initializing JARVIS...")

        # Initialize TTS engine (pre-warm)
        logger.info("Loading TTS engine...")
        self.tts_engine = await create_tts_engine()

        # Speak startup message
        await self.tts_engine.speak("JARVIS online. All systems nominal.")

        # Initialize STT engine
        logger.info("Loading STT engine...")
        self.stt_engine = await create_stt_engine()

        # Initialize wake word detector
        logger.info("Loading wake word detector...")
        self.wake_word_detector = await create_wake_word_detector()

        # Initialize microphone
        logger.info("Initializing microphone...")
        self.microphone = await create_microphone()

        # Initialize conversation memory
        claude_config = self.config.get_section("claude")
        self.memory = ConversationMemory(
            max_turns=claude_config.get("max_history_turns", 10)
        )

        # Initialize Claude client
        logger.info("Initializing Claude client...")
        claude_client = await create_claude_client()

        # Initialize orchestrator
        self.orchestrator = Orchestrator(
            claude_client=claude_client,
            memory=self.memory,
            tts_engine=self.tts_engine,
        )

        # Initialize intent parser
        self.intent_parser = get_intent_parser()

        logger.info("JARVIS initialization complete")

    async def run(self) -> None:
        """Main run loop."""
        self._running = True
        audio_config = self.config.get_section("audio")
        silence_threshold = audio_config.get("silence_threshold", 500)
        silence_duration_ms = audio_config.get("silence_duration_ms", 1500)
        sample_rate = audio_config.get("sample_rate", 16000)

        # Calculate samples for silence duration
        silence_samples = int(silence_duration_ms * sample_rate / 1000)

        # Start microphone
        await self.microphone.start()

        logger.info("JARVIS is listening for wake word...")
        await broadcast_state("idle")

        try:
            while self._running and not self._shutdown_event.is_set():
                # Listen for wake word
                detected = await self._listen_for_wake_word()

                if not detected or self._shutdown_event.is_set():
                    continue

                # Wake word detected - start recording
                logger.info("Wake word detected, listening for command...")
                await broadcast_state("listening")

                # Record user speech until silence
                audio_data = await self._record_until_silence(
                    silence_threshold, silence_samples
                )

                if audio_data is None or len(audio_data) < sample_rate // 2:
                    # Too short or no audio
                    logger.debug("No speech detected, returning to idle")
                    await broadcast_state("idle")
                    continue

                # Transcribe speech
                await broadcast_state("thinking")
                result = await self.stt_engine.transcribe(audio_data)

                if not result.text.strip():
                    # Empty transcription
                    logger.debug("Empty transcription, returning to idle")
                    await broadcast_state("idle")
                    continue

                logger.info(f"User said ({result.language}): {result.text}")
                await broadcast_transcript("user", result.text)

                # Classify intent
                intent_result = await self.intent_parser.classify_intent(
                    result.text, result.language
                )

                # Process through orchestrator
                agent_result = await self.orchestrator.process(
                    text=result.text,
                    language=result.language,
                    intent_result=intent_result,
                )

                # Speak response
                await broadcast_state("speaking")
                await self.tts_engine.speak(agent_result.spoken_response)
                await broadcast_transcript("jarvis", agent_result.spoken_response)

                # Add to memory
                self.memory.add_turn(
                    role="user",
                    content=result.text,
                    language=result.language,
                )
                self.memory.add_turn(
                    role="assistant",
                    content=agent_result.spoken_response,
                    language=result.language,
                )

                # Return to idle
                await broadcast_state("idle")
                logger.info("Returning to idle, listening for wake word...")

        except asyncio.CancelledError:
            logger.info("Main loop cancelled")
        finally:
            await self.microphone.stop()

    async def _listen_for_wake_word(self) -> bool:
        """Listen for wake word in audio stream.

        Returns:
            True if wake word detected
        """
        self.wake_word_detector.reset()

        async for chunk in self.microphone.stream_audio():
            if self._shutdown_event.is_set():
                return False

            # Check for wake word
            detected = await self.wake_word_detector._process_chunk(chunk)
            if detected:
                await self.wake_word_detector.play_chime()
                return True

        return False

    async def _record_until_silence(
        self, threshold: float, silence_samples: int
    ) -> np.ndarray | None:
        """Record audio until silence is detected.

        Args:
            threshold: Silence threshold (RMS amplitude)
            silence_samples: Number of silent samples to trigger stop

        Returns:
            Recorded audio data or None
        """
        chunks: list[np.ndarray] = []
        silent_chunks = 0
        total_silent_samples = 0

        chunk_size = self.config.get("audio.chunk_size", 1024)

        async for chunk in self.microphone.stream_audio():
            if self._shutdown_event.is_set():
                return None

            chunks.append(chunk.flatten())

            # Calculate RMS amplitude
            rms = np.sqrt(np.mean(chunk**2)) * 32768  # Scale to int16 range

            if rms < threshold:
                total_silent_samples += len(chunk.flatten())
                if total_silent_samples >= silence_samples:
                    break
            else:
                total_silent_samples = 0

            # Safety limit: max 30 seconds of recording
            total_samples = sum(len(c) for c in chunks)
            if total_samples > 30 * 16000:
                logger.warning("Recording exceeded 30 seconds, stopping")
                break

        if not chunks:
            return None

        return np.concatenate(chunks)

    async def shutdown(self) -> None:
        """Gracefully shutdown JARVIS."""
        logger.info("Shutting down JARVIS...")
        self._running = False
        self._shutdown_event.set()

        if self.tts_engine:
            await self.tts_engine.speak("Shutting down. Goodbye, sir.")

        logger.info("JARVIS shutdown complete")


async def main() -> None:
    """Main entry point."""
    assistant = JarvisAssistant()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler() -> None:
        asyncio.create_task(assistant.shutdown())

    # Handle SIGINT (Ctrl+C) and SIGTERM
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

    try:
        # Initialize components
        await assistant.setup()

        # Start WebSocket server in background
        api_config = assistant.config.get_section("api")
        ws_task = asyncio.create_task(
            start_ws_server(api_config, assistant.memory, assistant.tts_engine)
        )

        # Run main loop
        await assistant.run()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        await assistant.shutdown()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        await assistant.shutdown()
        raise


if __name__ == "__main__":
    asyncio.run(main())
