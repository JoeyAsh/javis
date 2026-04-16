"""WebSocket and HTTP server for JARVIS.

Provides real-time communication between the backend and frontend clients.
Audio is now captured in the browser and streamed here as raw Int16 PCM.
The server handles wake word detection, Whisper STT, Claude orchestration,
and Fish Audio TTS — then streams the MP3 response back to the frontend.
"""

import asyncio
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil
from aiohttp import web

from audio.fish_tts import FishTTSClient, FishTTSError, strip_markdown_for_tts
from audio.stt import SpeechToText, create_stt_engine
from audio.wake_word import WakeWordDetector, create_wake_word_detector
from brain.memory_legacy import ConversationMemory
from brain.intent_parser import IntentParser, get_intent_parser
from brain.orchestrator import Orchestrator
from utils.logger import get_logger

logger = get_logger("ws_server")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

# Store connected WebSocket clients
_connected_clients: set[web.WebSocketResponse] = set()

# Shared pipeline components (set in start_ws_server)
_memory: ConversationMemory | None = None
_tts_engine: Any = None  # kept for legacy set_voice_profile support
_fish_tts: FishTTSClient | None = None
_stt_engine: SpeechToText | None = None
_wake_word_detector: WakeWordDetector | None = None
_orchestrator: Orchestrator | None = None
_intent_parser: IntentParser | None = None

_start_time: float = time.time()

# Per-connection state key — stored on the ws object via a dict keyed by ws id
_connection_state: dict[int, dict[str, Any]] = {}

# Audio pipeline configuration (populated from config in start_ws_server)
_silence_threshold: float = 500.0
_silence_duration_ms: int = 1500
_sample_rate: int = 16000


# ---------------------------------------------------------------------------
# Broadcast helpers
# ---------------------------------------------------------------------------


async def broadcast_state(state: str) -> None:
    """Broadcast state change to all connected clients.

    Args:
        state: Current orb state (idle, listening, thinking, speaking)
    """
    message = json.dumps({"type": "status", "state": state})
    await _broadcast(message)


async def broadcast_audio(audio_b64: str, text: str) -> None:
    """Broadcast base64-encoded audio to all connected clients.

    Args:
        audio_b64: Base64-encoded MP3 audio
        text: Response text
    """
    message = json.dumps({"type": "audio", "data": audio_b64, "text": text})
    await _broadcast(message)


async def broadcast_transcript(role: str, text: str) -> None:
    """Broadcast transcript entry to all connected clients.

    Args:
        role: Speaker role (user or jarvis)
        text: Transcript text
    """
    message = json.dumps({"type": "transcript", "payload": {"role": role, "text": text}})
    await _broadcast(message)


async def broadcast_system_metrics() -> None:
    """Broadcast system metrics to all connected clients."""
    uptime_seconds = int(time.time() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        uptime_str = f"{hours}h {minutes}m"
    elif minutes > 0:
        uptime_str = f"{minutes}m {seconds}s"
    else:
        uptime_str = f"{seconds}s"

    message = json.dumps({
        "type": "system",
        "payload": {
            "cpu": psutil.cpu_percent(interval=None),
            "mem": psutil.virtual_memory().percent,
            "uptime": uptime_str,
        },
    })
    await _broadcast(message)


async def _broadcast(message: str) -> None:
    """Broadcast a message to all connected clients.

    Args:
        message: JSON string to broadcast
    """
    if not _connected_clients:
        return

    disconnected = set()
    for ws in _connected_clients:
        try:
            await ws.send_str(message)
        except Exception as e:
            logger.warning(f"Failed to send to client: {e}")
            disconnected.add(ws)

    _connected_clients.difference_update(disconnected)


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------


async def _system_metrics_loop() -> None:
    """Background task to broadcast system metrics every 5 seconds."""
    while True:
        try:
            await broadcast_system_metrics()
        except Exception as e:
            logger.error(f"Error broadcasting system metrics: {e}")
        await asyncio.sleep(5)


# ---------------------------------------------------------------------------
# Audio pipeline helpers
# ---------------------------------------------------------------------------


def _rms(chunk: np.ndarray) -> float:
    """Compute RMS amplitude scaled to 0–32768.

    Args:
        chunk: Float32 or Int16 audio samples.

    Returns:
        RMS amplitude in int16 scale.
    """
    arr = chunk.astype(np.float32)
    if arr.max() <= 1.0:
        return float(np.sqrt(np.mean(arr**2)) * 32768)
    return float(np.sqrt(np.mean(arr**2)))


def _pcm_bytes_to_float32(data: bytes) -> np.ndarray:
    """Convert raw Int16 PCM bytes to float32 numpy array.

    Args:
        data: Raw bytes in int16 little-endian format.

    Returns:
        Float32 array normalised to [-1, 1].
    """
    int16 = np.frombuffer(data, dtype=np.int16)
    return int16.astype(np.float32) / 32768.0


async def _run_voice_pipeline(
    audio_chunks: list[np.ndarray],
    ws: web.WebSocketResponse,
) -> None:
    """Run the full STT → LLM → TTS pipeline on collected audio chunks.

    Broadcasts thinking/speaking states and the final MP3 audio.

    Args:
        audio_chunks: List of float32 audio chunks to transcribe.
        ws: The WebSocket connection that triggered this pipeline run
            (used only for logging; broadcasts go to all clients).
    """
    global _memory, _fish_tts, _stt_engine, _orchestrator, _intent_parser

    if not audio_chunks:
        logger.debug("No audio chunks for pipeline, returning to idle")
        await broadcast_state("idle")
        return

    audio_data = np.concatenate(audio_chunks)

    # Need at least 0.5 s of audio
    if len(audio_data) < _sample_rate // 2:
        logger.debug("Audio too short, returning to idle")
        await broadcast_state("idle")
        return

    # --- Transcribe ---
    await broadcast_state("thinking")

    if _stt_engine is None:
        logger.error("STT engine not initialised")
        await broadcast_state("idle")
        return

    result = await _stt_engine.transcribe(audio_data)

    if not result.text.strip():
        logger.debug("Empty transcription, returning to idle")
        await broadcast_state("idle")
        return

    logger.info(f"User said ({result.language}): {result.text}")

    # --- Intent classification + orchestration ---
    if _intent_parser is None or _orchestrator is None:
        logger.error("Orchestrator not initialised")
        await broadcast_state("idle")
        return

    intent_result = await _intent_parser.classify_intent(result.text, result.language)

    try:
        agent_result = await _orchestrator.process(
            text=result.text,
            language=result.language,
            intent_result=intent_result,
        )
        response_text = agent_result.spoken_response
    except Exception as exc:
        logger.error(f"Orchestrator error: {exc}")
        response_text = "Entschuldigung, es gab einen Fehler."

    logger.info(f"JARVIS: {response_text}")

    # --- TTS synthesis ---
    await broadcast_state("speaking")

    if _fish_tts is None:
        logger.error("Fish TTS not initialised")
        await broadcast_state("idle")
        return

    tts_text = strip_markdown_for_tts(response_text)

    try:
        audio_bytes = await _fish_tts.synthesize(tts_text)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        await broadcast_audio(audio_b64, response_text)

        # Wait for estimated playback duration before returning to idle.
        # Frontend will also transition to idle when playback finishes,
        # but we use this to gate the next wake word detection cycle
        # (pipeline is serialised per connection via _connection_state).
        play_duration = max(1.5, len(audio_bytes) / 2000)
        await asyncio.sleep(play_duration)

    except FishTTSError as exc:
        logger.error(f"Fish TTS error: {exc}")

    # --- Update memory ---
    if _memory:
        _memory.add_turn(role="user", content=result.text, language=result.language)
        _memory.add_turn(
            role="assistant", content=response_text, language=result.language
        )

    await broadcast_state("idle")
    logger.info("Voice pipeline complete, returning to idle")


# ---------------------------------------------------------------------------
# Per-connection audio processing coroutine
# ---------------------------------------------------------------------------


async def _process_audio_for_client(
    ws: web.WebSocketResponse,
    chunk: np.ndarray,
) -> None:
    """Process a single incoming audio chunk for a client connection.

    State machine per connection:
      IDLE      → feed chunk to wake word detector
      LISTENING → collect chunks until silence, then run pipeline

    Args:
        ws: The client WebSocket.
        chunk: Float32 16 kHz mono audio chunk.
    """
    conn_id = id(ws)
    state = _connection_state.get(conn_id)
    if state is None:
        return  # connection cleaned up

    mode = state["mode"]  # "idle" | "listening" | "processing"

    if mode == "processing":
        # Pipeline is running — drop incoming chunks to avoid re-trigger
        return

    if mode == "idle":
        # Feed to wake word detector
        if _wake_word_detector is None:
            return

        detected = await _wake_word_detector._process_chunk(chunk)
        if detected:
            logger.info("Wake word detected via browser audio")
            state["mode"] = "listening"
            state["audio_chunks"] = []
            state["speech_started"] = False
            state["silent_samples"] = 0
            state["total_samples"] = 0
            state["skip_remaining"] = 3  # skip ~0.2 s to clear wake word tail
            _wake_word_detector.reset()
            await broadcast_state("listening")

    elif mode == "listening":
        silence_samples = int(_silence_duration_ms * _sample_rate / 1000)

        # Skip first N chunks after wake word detection
        if state["skip_remaining"] > 0:
            state["skip_remaining"] -= 1
            return

        state["audio_chunks"].append(chunk)
        rms = _rms(chunk)
        total_samples = state["total_samples"] + len(chunk)
        state["total_samples"] = total_samples

        if rms > _silence_threshold:
            state["speech_started"] = True
            state["silent_samples"] = 0
        else:
            state["silent_samples"] += len(chunk)

        # After speech started, stop when we have enough silence
        if state["speech_started"] and state["silent_samples"] >= silence_samples:
            logger.debug("Silence detected after speech — starting pipeline")
            state["mode"] = "processing"
            chunks = list(state["audio_chunks"])
            state["audio_chunks"] = []
            asyncio.create_task(_run_voice_pipeline(chunks, ws))
            # Pipeline will broadcast_state("idle") when done; reset mode here
            # so new wake word detection can begin immediately after
            state["mode"] = "idle"
            return

        # Timeout: no speech in 5 s
        if not state["speech_started"] and total_samples > 5 * _sample_rate:
            logger.debug("No speech detected in 5 seconds, returning to idle")
            state["mode"] = "idle"
            state["audio_chunks"] = []
            await broadcast_state("idle")
            return

        # Max recording: 15 s
        if total_samples > 15 * _sample_rate:
            logger.warning("Recording exceeded 15 seconds — forcing pipeline")
            state["mode"] = "processing"
            chunks = list(state["audio_chunks"])
            state["audio_chunks"] = []
            asyncio.create_task(_run_voice_pipeline(chunks, ws))
            state["mode"] = "idle"


# ---------------------------------------------------------------------------
# Command handler
# ---------------------------------------------------------------------------


async def _handle_command(data: dict[str, Any]) -> None:
    """Handle incoming JSON WebSocket command.

    Args:
        data: Parsed command data
    """
    global _memory, _tts_engine

    cmd_type = data.get("type")
    payload = data.get("payload", {})

    if cmd_type == "set_voice":
        profile = payload.get("profile")
        if profile and _tts_engine:
            try:
                if hasattr(_tts_engine, "set_voice_profile"):
                    _tts_engine.set_voice_profile(profile)
                    logger.info(f"Voice profile changed to: {profile}")
            except Exception as e:
                logger.error(f"Failed to change voice profile: {e}")

    elif cmd_type == "reset":
        if _memory:
            _memory.clear()
            logger.info("Memory cleared via WebSocket command")

    else:
        logger.warning(f"Unknown command type: {cmd_type}")


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """Handle WebSocket connections.

    Accepts both JSON control messages and binary PCM audio frames from the
    browser mic stream.

    Args:
        request: aiohttp request object

    Returns:
        WebSocket response
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    conn_id = id(ws)
    _connected_clients.add(ws)
    _connection_state[conn_id] = {
        "mode": "idle",  # "idle" | "listening" | "processing"
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
    }
    if _wake_word_detector:
        _wake_word_detector.reset()

    logger.info(f"Client connected. Total clients: {len(_connected_clients)}")

    # Send initial state
    await ws.send_str(json.dumps({"type": "status", "state": "idle"}))
    await broadcast_system_metrics()

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await _handle_command(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {msg.data}")

            elif msg.type == web.WSMsgType.BINARY:
                # Raw Int16 PCM audio from the browser mic
                try:
                    chunk = _pcm_bytes_to_float32(msg.data)
                    if chunk.size > 0:
                        await _process_audio_for_client(ws, chunk)
                except Exception as exc:
                    logger.error(f"Error processing audio chunk: {exc}")

            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")

    finally:
        _connected_clients.discard(ws)
        _connection_state.pop(conn_id, None)
        logger.info(f"Client disconnected. Total clients: {len(_connected_clients)}")

    return ws


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------


async def voices_handler(request: web.Request) -> web.Response:
    """Handle GET /voices endpoint.

    Args:
        request: aiohttp request object

    Returns:
        JSON response with list of voice profiles
    """
    voices_dir = Path(__file__).parent.parent.parent / "voices"
    voices = []

    if voices_dir.exists():
        for wav_file in voices_dir.glob("*.wav"):
            if wav_file.name != "chime.wav":
                voices.append(wav_file.name)

    return web.json_response(voices)


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------


async def start_ws_server(
    config: dict[str, Any],
    memory: ConversationMemory,
    tts_engine: Any,
) -> None:
    """Start the WebSocket and HTTP server and initialise the voice pipeline.

    Args:
        config: API configuration section
        memory: Conversation memory instance
        tts_engine: Unused (kept for API compatibility). Fish TTS is
            initialised internally.
    """
    global _memory, _tts_engine, _fish_tts, _stt_engine, _wake_word_detector
    global _orchestrator, _intent_parser, _start_time
    global _silence_threshold, _silence_duration_ms, _sample_rate

    from dotenv import load_dotenv

    from brain.claude_client import create_claude_client
    from utils.config_loader import get_config

    load_dotenv()
    cfg = get_config()

    _memory = memory
    _tts_engine = tts_engine
    _start_time = time.time()

    # Audio config
    audio_config = cfg.get_section("audio")
    _silence_threshold = float(audio_config.get("silence_threshold", 500))
    _silence_duration_ms = int(audio_config.get("silence_duration_ms", 1500))
    _sample_rate = int(audio_config.get("sample_rate", 16000))

    # Initialise voice pipeline components
    logger.info("Initialising Fish Audio TTS...")
    _fish_tts = FishTTSClient()

    logger.info("Loading STT engine...")
    _stt_engine = await create_stt_engine()

    logger.info("Loading wake word detector...")
    _wake_word_detector = await create_wake_word_detector()

    # Claude client + orchestrator
    logger.info("Initialising Claude client...")
    claude_client = await create_claude_client()

    if _memory is None:
        claude_config = cfg.get_section("claude")
        from brain.memory_legacy import ConversationMemory as _CM

        _memory = _CM(max_turns=claude_config.get("max_history_turns", 10))

    _orchestrator = Orchestrator(
        claude_client=claude_client,
        memory=_memory,
        tts_engine=None,
    )

    _intent_parser = get_intent_parser()

    logger.info("Voice pipeline components ready")

    # Server ports and CORS
    ws_port = config.get("ws_port", 8765)
    http_port = config.get("http_port", 8766)
    cors_origins = config.get("cors_origins", ["http://localhost:5173"])

    # WebSocket application
    ws_app = web.Application()
    ws_app.router.add_get("/", websocket_handler)
    ws_app.router.add_get("/ws", websocket_handler)

    # CORS middleware for HTTP app
    @web.middleware
    async def cors_middleware(request: web.Request, handler: Any) -> web.Response:
        if request.method == "OPTIONS":
            response = web.Response()
        else:
            response = await handler(request)

        origin = request.headers.get("Origin", "")
        if origin in cors_origins or "*" in cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"

        return response

    http_app = web.Application(middlewares=[cors_middleware])
    http_app.router.add_get("/voices", voices_handler)

    # Start WebSocket server
    ws_runner = web.AppRunner(ws_app)
    await ws_runner.setup()
    ws_site = web.TCPSite(ws_runner, "0.0.0.0", ws_port)
    await ws_site.start()
    logger.info(f"WebSocket server started on port {ws_port}")

    # Start HTTP server
    http_runner = web.AppRunner(http_app)
    await http_runner.setup()
    http_site = web.TCPSite(http_runner, "0.0.0.0", http_port)
    await http_site.start()
    logger.info(f"HTTP server started on port {http_port}")

    # Background metrics broadcast
    asyncio.create_task(_system_metrics_loop())

    # Keep running
    while True:
        await asyncio.sleep(3600)
