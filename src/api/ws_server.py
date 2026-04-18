"""WebSocket and HTTP server for JARVIS.

Provides real-time communication between the backend and frontend clients.
Audio is now captured in the browser and streamed here as raw Int16 PCM.
The server handles wake word detection, Whisper STT, Claude orchestration,
and Fish Audio TTS — then streams the MP3 response back to the frontend.
"""

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from aiohttp import web

from api.system_metrics import SystemMetrics, SystemMetricsCollector
from audio.fish_tts import FishTTSClient, FishTTSError, strip_markdown_for_tts
from audio.stream_splitter import StreamSplitter
from audio.stt import SpeechToText, create_stt_engine
from audio.wake_word import WakeWordDetector, create_wake_word_detector
from brain.conversation_mode import ConversationMode
from brain.memory import MemoryStore
from brain.intent_parser import IntentParser, get_intent_parser
from brain.quick_ack import QuickAckGenerator
from brain.orchestrator import Orchestrator
from brain.salutation import get_salutation
from integrations.openclaw import OpenClawClient
from utils.logger import get_logger

logger = get_logger("ws_server")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

# Store connected WebSocket clients
_connected_clients: set[web.WebSocketResponse] = set()

# Event set the first time *any* client connects in this process lifetime.
# Stays set for the remainder of the process so consumers that await it
# after the fact still resolve immediately.
_first_client_event: asyncio.Event = asyncio.Event()


def first_client_event() -> asyncio.Event:
    """Return the event signalling the first-ever client connect.

    Lazily returns a fresh Event on the current loop if the module-level
    one was created on a different loop (e.g. across test runs).
    """
    return _first_client_event


# Shared pipeline components (set in start_ws_server)
#
# Session memory is owned by OpenClaw (keyed by ``session_id``). The local
# SQLite ``MemoryStore`` stays on as an append-only archive for transcript
# search / audit — nothing in the voice pipeline reads back from it during
# a turn. There is no more in-RAM ``ConversationMemory``.
_memory_store: MemoryStore | None = None
_openclaw_client: OpenClawClient | None = None
_tts_engine: Any = None  # kept for legacy set_voice_profile support
_fish_tts: FishTTSClient | None = None
_stt_engine: SpeechToText | None = None
_wake_word_detector: WakeWordDetector | None = None
_orchestrator: Orchestrator | None = None
_intent_parser: IntentParser | None = None

# Conversation-mode helper — arm/detect follow-up window + sleep phrases.
_conversation_mode: ConversationMode | None = None

# Persona config snapshot — read once at startup so the sleep-phrase closing
# line can pick a salutation without re-reading config per turn.
_persona_config: dict[str, Any] = {}

# Quick-ack filler cache: {lang: [(text, mp3_bytes), ...]} — loaded once at
# startup from ``data/voice_cache/filler_<lang>_*.mp3``. Playing pre-cached
# bytes lets the first audio arrive on the frontend within ~300 ms of STT
# finishing, even though the real LLM response takes 7–11 s.
_filler_cache: dict[str, list[tuple[str, bytes]]] = {}
# Pre-cached ack MP3s (ack_<lang>_*.mp3) — used for complex query acknowledgments.
_ack_cache: dict[str, list[tuple[str, bytes]]] = {}
# Pre-cached backchannel MP3s (backchannel_<lang>_*.mp3).
_backchannel_cache: dict[str, list[tuple[str, bytes]]] = {}

# Singleton QuickAckGenerator — lazy init mirrors _intent_parser pattern.
_quick_ack_generator: QuickAckGenerator | None = None

_start_time: float = time.time()

# System metrics collector + last snapshot (used for initial per-connection push)
_metrics_collector: SystemMetricsCollector | None = None
_metrics_task: asyncio.Task[None] | None = None
_last_metrics: SystemMetrics | None = None

# Per-connection state key — stored on the ws object via a dict keyed by ws id
_connection_state: dict[int, dict[str, Any]] = {}

# Audio pipeline configuration (populated from config in start_ws_server)
_silence_threshold: float = 500.0
_silence_duration_ms: int = 1500
_sample_rate: int = 16000

# Barge-in + backchannel config (populated from voice section at startup)
_barge_in_enabled: bool = True
# 150ms triggered on breath/keyboard noise; 400ms is the natural human-interruption floor.
_barge_in_sensitivity_ms: int = 400
# Dedicated RMS threshold for barge-in VAD — separate from _silence_threshold which
# governs end-of-turn detection. Default 0.02 keeps existing test fixtures stable.
_barge_in_vad_rms_threshold: float = 0.02
_backchannels_enabled: bool = True
_backchannel_silence_threshold_ms: int = 1200
_backchannel_min_interval_seconds: float = 3.0
_quick_ack_enabled: bool = True


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


async def broadcast_audio(
    audio_b64: str,
    text: str,
    channel: str | None = None,
) -> None:
    """Broadcast base64-encoded audio to all connected clients.

    Args:
        audio_b64: Base64-encoded MP3 audio.
        text: Response text (empty string for backchannels to skip transcript).
        channel: Optional channel tag (e.g. ``"backchannel"``). Frontend uses
            this to set lower playback volume for backchannel clips.
    """
    payload: dict[str, Any] = {"type": "audio", "data": audio_b64, "text": text}
    if channel is not None:
        payload["channel"] = channel
    message = json.dumps(payload)
    await _broadcast(message)


async def broadcast_barge_in() -> None:
    """Broadcast a barge-in event to all connected clients.

    Instructs the frontend to clear its audio queue and stop current playback.
    """
    message = json.dumps({"type": "barge_in"})
    await _broadcast(message)


async def broadcast_transcript(role: str, text: str) -> None:
    """Broadcast transcript entry to all connected clients and archive it.

    Every transcript turn is also persisted to the JARVIS ``events`` table
    in :class:`brain.memory.MemoryStore`. OpenClaw keeps the short-context
    conversational memory; the local DB keeps an append-only archive of
    every spoken turn for later recall features (voice-driven search,
    timeline views, audit).

    Args:
        role: Speaker role (``"user"`` or ``"jarvis"``).
        text: Transcript text.
    """
    message = json.dumps(
        {"type": "transcript", "payload": {"role": role, "text": text}}
    )
    await _broadcast(message)

    # Dual-write: archive to the local SQLite events log. Failures here
    # must never take down the voice pipeline, so we swallow exceptions
    # after logging.
    if _memory_store is not None:
        try:
            await _memory_store.record_event(
                event_type="transcript",
                source="voice",
                payload={"role": role, "text": text},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"MemoryStore record_event failed: {exc}")


async def broadcast_tool_call(
    state: str,
    tool_name: str,
    summary: str = "",
) -> None:
    """Broadcast a tool-call event to all connected clients.

    Informs the frontend that JARVIS is actively running a tool (e.g. reading
    a file, executing a shell command) so the orb can show a ``working`` state
    instead of remaining visually idle during the thinking gap.

    Args:
        state: ``"started"`` when a tool call begins, ``"finished"`` when it ends.
        tool_name: Raw tool name (e.g. ``"Read"``, ``"Bash"``).
        summary: Short human-readable German label for the action, or empty string.
    """
    message = json.dumps(
        {
            "type": "tool_call",
            "payload": {
                "state": state,
                "tool_name": tool_name,
                "summary": summary,
            },
        }
    )
    await _broadcast(message)


def _summarize_tool_call(tool_name: str, tool_input: dict[str, Any] | None) -> str:
    """Return a short German-language label for a tool call.

    Args:
        tool_name: Raw tool name from the stream chunk.
        tool_input: Optional input parameters dict; may be ``None`` or empty.

    Returns:
        Human-readable German label, or empty string for unknown tools.
    """
    inp = tool_input or {}
    name_lower = (tool_name or "").lower()

    if name_lower == "read":
        path = str(inp.get("file_path") or inp.get("path") or "")
        segment = path.split("/")[-1] if path else ""
        return f"Lese {segment}" if segment else "Lese Datei"

    if name_lower == "write":
        path = str(inp.get("file_path") or inp.get("path") or "")
        segment = path.split("/")[-1] if path else ""
        return f"Schreibe {segment}" if segment else "Schreibe Datei"

    if name_lower == "edit":
        path = str(inp.get("file_path") or inp.get("path") or "")
        segment = path.split("/")[-1] if path else ""
        return f"Bearbeite {segment}" if segment else "Bearbeite Datei"

    if name_lower == "bash":
        return "Führe Shell-Kommando aus"

    if name_lower in ("glob", "grep"):
        return "Suche im Code"

    if name_lower == "multiedit":
        return "Bearbeite Dateien"

    if name_lower == "notebookedit":
        return "Bearbeite Notebook"

    if name_lower == "todowrite":
        return "Aktualisiere Aufgabenliste"

    if name_lower == "webfetch":
        return "Lade Webseite"

    if name_lower == "websearch":
        return "Suche im Web"

    if tool_name:
        return tool_name.lower()

    return ""


async def broadcast_conversation_mode(
    active: bool,
    seconds_remaining: float,
) -> None:
    """Broadcast the current conversation-mode follow-up state.

    Sent whenever the follow-up window is armed (after a successful voice
    turn) and again when it expires or is closed by a sleep phrase. The
    HUD orb uses this to show a subtle pulse + 5 s countdown ring.

    Args:
        active: ``True`` while the follow-up window is open.
        seconds_remaining: Seconds left in the window, ``0.0`` when closed.
    """
    message = json.dumps(
        {
            "type": "conversation_mode",
            "payload": {
                "active": active,
                "seconds_remaining": max(0.0, float(seconds_remaining)),
            },
        }
    )
    await _broadcast(message)


async def broadcast_notification(
    notification_id: str,
    severity: str,
    title: str,
    detail: str = "",
    timestamp: str | None = None,
) -> None:
    """Broadcast a HUD notification to all connected clients.

    Args:
        notification_id: Stable id (used for client-side dedup).
        severity: One of ``info`` / ``warning`` / ``urgent``.
        title: Short headline shown prominently.
        detail: Optional longer body text.
        timestamp: ISO-8601 UTC; if ``None`` the server stamps it.
    """
    from datetime import datetime, timezone

    ts = timestamp or datetime.now(timezone.utc).isoformat()
    message = json.dumps(
        {
            "type": "notification",
            "payload": {
                "id": notification_id,
                "severity": severity,
                "title": title,
                "detail": detail,
                "timestamp": ts,
            },
        }
    )
    logger.info(
        f"Broadcast notification id={notification_id} sev={severity} "
        f"title='{title}' to {len(_connected_clients)} clients"
    )
    await _broadcast(message)


def _format_uptime(seconds: float) -> str:
    """Format uptime as ``HH:MM:SS`` (no cap on hours)."""
    total = max(int(seconds), 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _metrics_to_payload(metrics: SystemMetrics) -> dict[str, Any]:
    """Build the outbound WebSocket payload for a metrics snapshot.

    Keeps the legacy ``cpu``/``mem``/``uptime`` fields so existing
    consumers don't break, and adds the extended fields alongside.
    """
    return {
        # Legacy fields — preserved for backward compatibility.
        "cpu": metrics.cpu_percent,
        "mem": metrics.ram_percent,
        "uptime": _format_uptime(metrics.uptime_seconds),
        # Extended fields.
        "gpu": metrics.gpu_percent,
        "cpu_temp": metrics.cpu_temp_c,
        "net_up": metrics.net_up_mbps,
        "net_down": metrics.net_down_mbps,
        "disk": metrics.disk_percent,
    }


async def broadcast_system_metrics(metrics: SystemMetrics | None = None) -> None:
    """Broadcast a system metrics snapshot to all connected clients.

    If ``metrics`` is ``None``, the most recent snapshot captured by the
    background collector is used (or a fresh ad-hoc one if none exists
    yet, e.g. on initial client connect before the first tick).
    """
    global _last_metrics

    snapshot = metrics
    if snapshot is None:
        snapshot = _last_metrics
    if snapshot is None and _metrics_collector is not None:
        try:
            snapshot = await _metrics_collector.snapshot()
            _last_metrics = snapshot
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Ad-hoc metrics snapshot failed: {exc}")
            snapshot = None

    if snapshot is None:
        return

    _last_metrics = snapshot
    message = json.dumps({"type": "system", "payload": _metrics_to_payload(snapshot)})
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


async def _on_metrics_snapshot(metrics: SystemMetrics) -> None:
    """Collector callback — broadcast each fresh snapshot to clients."""
    global _last_metrics
    _last_metrics = metrics
    await broadcast_system_metrics(metrics)


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


def _load_voice_cache(
    cache_dir: Path, prefix: str
) -> dict[str, list[tuple[str, bytes]]]:
    """Load all ``<prefix>_<lang>_<slug>.mp3`` files from ``cache_dir``.

    Returns a map from language code to a list of ``(display_text, mp3_bytes)``
    tuples. Missing directory or missing files is a warning, not an error —
    callers simply skip broadcasts in that case.
    """
    cache: dict[str, list[tuple[str, bytes]]] = {}
    if not cache_dir.exists():
        logger.warning(f"Voice cache directory not found: {cache_dir}")
        return cache

    for path in sorted(cache_dir.glob(f"{prefix}_*.mp3")):
        stem = path.stem  # e.g. "filler_de_einen_augenblick"
        # Strip the prefix explicitly so prefixes that contain underscores
        # themselves still split cleanly into (lang, slug).
        rest = stem[len(prefix) + 1 :] if stem.startswith(prefix + "_") else ""
        parts = rest.split("_", 1)
        if len(parts) < 2:
            logger.debug(f"Skipping unrecognised voice cache file: {path.name}")
            continue
        lang, slug = parts[0], parts[1]
        display = slug.replace("_", " ").strip().capitalize()
        try:
            data = path.read_bytes()
        except OSError as exc:
            logger.warning(f"Failed to read {path}: {exc}")
            continue
        if not data:
            logger.warning(f"Cache file is empty, skipping: {path}")
            continue
        cache.setdefault(lang, []).append((display, data))

    total = sum(len(v) for v in cache.values())
    if total == 0:
        logger.warning(
            f"No '{prefix}_*.mp3' files found in {cache_dir} — '{prefix}' broadcasts disabled"
        )
    else:
        langs = ", ".join(f"{k}={len(v)}" for k, v in cache.items())
        logger.info(f"Loaded {total} '{prefix}' phrases ({langs})")
    return cache


def _load_filler_cache(cache_dir: Path) -> dict[str, list[tuple[str, bytes]]]:
    """Backwards-compatible wrapper — delegates to :func:`_load_voice_cache`."""
    return _load_voice_cache(cache_dir, "filler")


async def _broadcast_from_cache(
    cache: dict[str, list[tuple[str, bytes]]],
    language: str,
    log_label: str,
) -> None:
    """Pick a random pre-cached MP3 from ``cache`` and broadcast it."""
    import random

    if not cache:
        return

    pool = cache.get(language)
    if not pool:
        pool = cache.get("de") or next(iter(cache.values()), [])
    if not pool:
        return

    text, mp3_bytes = random.choice(pool)
    audio_b64 = base64.b64encode(mp3_bytes).decode("utf-8")
    logger.info(
        f"{log_label} broadcast: {text!r} ({len(mp3_bytes)} bytes, lang={language})"
    )
    await broadcast_audio(audio_b64, text)


async def _broadcast_quick_ack_filler(language: str) -> None:
    """Broadcast a random pre-cached filler MP3 — plays while LLM is running."""
    await _broadcast_from_cache(_filler_cache, language, "Filler")


async def _maybe_play_backchannel(
    state: dict[str, Any],
    language: str,
) -> None:
    """Broadcast a backchannel clip if the minimum interval has elapsed.

    BackchannelPlayer's API requires an external audio player object that
    doesn't exist in the WS pipeline — we implement the interval/cache logic
    inline here and broadcast via the existing audio pipeline instead.

    Args:
        state: Per-connection state dict; tracks ``last_backchannel_at``.
        language: Language code (``"de"`` / ``"en"``).
    """
    import random

    if not _backchannel_cache:
        return

    now = time.monotonic()
    last = state.get("last_backchannel_at", 0.0)
    if now - last < _backchannel_min_interval_seconds:
        return

    pool = _backchannel_cache.get(language)
    if not pool:
        pool = _backchannel_cache.get("de") or next(
            iter(_backchannel_cache.values()), []
        )
    if not pool:
        return

    _text, mp3_bytes = random.choice(pool)
    audio_b64 = base64.b64encode(mp3_bytes).decode("utf-8")
    state["last_backchannel_at"] = now
    logger.info(f"Backchannel broadcast ({language}, {len(mp3_bytes)} bytes)")
    # Empty text so the transcript panel doesn't render a "mhm" entry.
    await broadcast_audio(audio_b64, "", channel="backchannel")


async def _close_follow_up_window(conn_id: int, reason: str) -> None:
    """Close the follow-up window for ``conn_id`` and notify clients.

    Safe to call even if no window is currently armed. Cancels any pending
    expiry task, resets connection mode to idle, and broadcasts the
    "conversation_mode inactive" signal to the HUD.

    Args:
        conn_id: Identifier returned by ``id(ws)``.
        reason: Short log tag (``"expired"`` / ``"sleep"`` / ``"cleanup"``).
    """
    state = _connection_state.get(conn_id)
    if state is None:
        return

    timer = state.get("follow_up_timer_task")
    if timer is not None and not timer.done():
        timer.cancel()
    state["follow_up_timer_task"] = None

    if state.get("mode") == "follow_up":
        state["mode"] = "idle"
        state["audio_chunks"] = []
        state["speech_started"] = False
        state["silent_samples"] = 0
        state["total_samples"] = 0

    if _conversation_mode is not None:
        _conversation_mode.end_window()

    logger.debug(f"Follow-up window closed ({reason}) for conn {conn_id}")
    await broadcast_conversation_mode(active=False, seconds_remaining=0.0)


async def _follow_up_expiry_task(conn_id: int, window_seconds: float) -> None:
    """Sleep for ``window_seconds``, then close the follow-up window.

    Cancelled by ``_process_audio_for_client`` as soon as speech starts
    inside the window, or by ``_close_follow_up_window`` on a sleep-phrase
    close. On natural expiry, broadcasts the idle transition so the HUD
    returns the orb to its baseline pulse.
    """
    try:
        await asyncio.sleep(window_seconds)
    except asyncio.CancelledError:
        return

    state = _connection_state.get(conn_id)
    if state is None or state.get("mode") != "follow_up":
        return

    logger.info(f"Follow-up window expired after {window_seconds:.1f}s — back to idle")
    await _close_follow_up_window(conn_id, "expired")
    await broadcast_state("idle")


async def _arm_follow_up_window(ws: web.WebSocketResponse) -> None:
    """Arm a follow-up window for the connection behind ``ws``.

    Transitions the connection to the ``follow_up`` mode, starts the
    expiry timer, broadcasts the state so the HUD keeps pulsing and so
    ``_process_audio_for_client`` routes incoming audio as a continuation.

    Silently no-ops if conversation mode is disabled or the connection
    state has vanished (client closed mid-pipeline).
    """
    if _conversation_mode is None or not _conversation_mode.enabled:
        return

    conn_id = id(ws)
    state = _connection_state.get(conn_id)
    if state is None:
        return

    _conversation_mode.begin_window()
    state["mode"] = "follow_up"
    state["audio_chunks"] = []
    state["speech_started"] = False
    state["silent_samples"] = 0
    state["total_samples"] = 0
    state["skip_remaining"] = 0

    # Reset wake-word detector so the next idle transition is clean.
    if _wake_word_detector is not None:
        _wake_word_detector.reset()

    window = _conversation_mode.window_seconds
    logger.info(f"Follow-up window armed for {window:.1f}s")
    await broadcast_conversation_mode(active=True, seconds_remaining=window)
    # Keep broadcasting "listening" so the frontend orb stays lit during
    # the follow-up window (a new wake word is not required inside it).
    await broadcast_state("listening")

    timer = asyncio.create_task(_follow_up_expiry_task(conn_id, window))
    state["follow_up_timer_task"] = timer


async def _run_voice_pipeline(
    audio_chunks: list[np.ndarray],
    ws: web.WebSocketResponse,
) -> None:
    """Run the full STT → LLM → TTS pipeline on collected audio chunks.

    Broadcasts thinking/speaking states and the final MP3 audio. On a
    successful turn, arms a follow-up window so the user can continue
    without a new wake word. Natural "sleep" phrases ("danke", "thanks",
    ...) short-circuit the LLM call and speak a warm closing line instead.

    Cancellable: if the caller cancels this task (STOP button → ``cancel_turn``
    command → ``task.cancel()``), the coroutine swallows the
    ``CancelledError`` cleanly and does not emit any further audio /
    transcript frames. The ``_cancel_current_turn`` helper owns the
    user-visible idle + notification broadcasts.

    Args:
        audio_chunks: List of float32 audio chunks to transcribe.
        ws: The WebSocket connection that triggered this pipeline run
            (used for follow-up window arming + logging; audio broadcasts
            fan out to all clients).
    """
    try:
        await _run_voice_pipeline_body(audio_chunks, ws)
    except asyncio.CancelledError:
        logger.info("Voice pipeline cancelled — discarding any in-flight result")
        # Don't re-raise: the cancel initiator (``_cancel_current_turn``)
        # already broadcast the idle + notification. Re-raising would
        # propagate a bare CancelledError out of the asyncio task and
        # log a noisy "Task was destroyed" message.
        return
    finally:
        conn_state = _connection_state.get(id(ws))
        if conn_state is not None:
            conn_state["pipeline_task"] = None


async def _run_voice_pipeline_body(
    audio_chunks: list[np.ndarray],
    ws: web.WebSocketResponse,
) -> None:
    """Actual pipeline body — wrapped by :func:`_run_voice_pipeline` for
    cancellation safety. Do not call directly.
    """
    global _fish_tts, _stt_engine, _orchestrator, _intent_parser

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

    # Broadcast + archive the user turn immediately — we want the
    # archive to reflect reality even if the downstream LLM call fails.
    await broadcast_transcript("user", result.text)

    # --- Sleep-phrase short-circuit ---------------------------------------
    # If the user's utterance signals "we're done" ("danke", "thanks", ...),
    # skip the LLM round-trip entirely, speak a short closing line, and
    # return to idle WITHOUT arming a new follow-up window.
    if _conversation_mode is not None and _conversation_mode.detect_sleep_phrase(
        result.text, result.language
    ):
        salutation = get_salutation(_persona_config) if _persona_config else "Sir"
        closing = _conversation_mode.closing_phrase(result.language, salutation)
        logger.info(f"Sleep phrase detected — closing with: {closing!r}")

        # Close any currently armed window (guards against a follow-up turn
        # that ends with "danke" — we end the session cleanly).
        await _close_follow_up_window(id(ws), "sleep")

        await broadcast_transcript("jarvis", closing)
        await broadcast_state("speaking")

        if _fish_tts is not None and closing:
            try:
                audio_bytes = await _fish_tts.synthesize(
                    strip_markdown_for_tts(closing)
                )
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                await broadcast_audio(audio_b64, closing)
                play_duration = max(1.2, len(audio_bytes) / 2000)
                await asyncio.sleep(play_duration)
            except FishTTSError as exc:
                logger.error(f"Fish TTS error during sleep close: {exc}")

        # Memory: session history is owned by OpenClaw, the local archive
        # is written by ``broadcast_transcript`` above. Nothing to do here.

        # Force the connection back to idle — _close_follow_up_window only
        # resets mode when the previous mode was follow_up, but a sleep
        # phrase may also arrive on the very first turn (mode=processing).
        sleep_state = _connection_state.get(id(ws))
        if sleep_state is not None:
            sleep_state["mode"] = "idle"
            sleep_state["audio_chunks"] = []
            sleep_state["speech_started"] = False
            sleep_state["silent_samples"] = 0
            sleep_state["total_samples"] = 0

        await broadcast_state("idle")
        logger.info("Voice pipeline complete (closed by sleep phrase)")
        return

    # --- Quick-ack filler -------------------------------------------------
    # Play a short pre-cached clip so the frontend has audio within ~300 ms of
    # STT finishing, masking the 7-11 s OpenClaw round-trip. For complex queries
    # (explain/describe/...) we use a smarter ack_*.mp3 instead of the generic
    # filler_*.mp3 — same delivery path, better UX signal.
    if _quick_ack_enabled and _quick_ack_generator is not None and _ack_cache:
        if _quick_ack_generator.should_ack(result.text):
            await _broadcast_from_cache(_ack_cache, result.language, "QuickAck")
        else:
            await _broadcast_quick_ack_filler(result.language)
    else:
        await _broadcast_quick_ack_filler(result.language)

    # --- Intent classification + streaming orchestration ---
    if _intent_parser is None or _orchestrator is None:
        logger.error("Orchestrator not initialised")
        await broadcast_state("idle")
        return

    if _fish_tts is None:
        logger.error("Fish TTS not initialised")
        await broadcast_state("idle")
        return

    intent_result = await _intent_parser.classify_intent(result.text, result.language)

    # Track the current run so _cancel_current_turn can abort it.
    conn_state = _connection_state.get(id(ws))
    current_run_id: str | None = None
    current_session_id: str = (
        _openclaw_client.session_id if _openclaw_client else "jarvis-main"
    )

    full_response_text = ""
    first_audio_sent = False
    t_stream_start = time.monotonic()
    # Threshold above which we assume a tool call is running during the silence
    # before the first text delta arrives (TTFT > this value → broadcast working).
    _TOOL_HINT_TTFT_S: float = 2.0
    _tool_hint_sent: bool = False

    # The StreamSplitter converts a stream of incremental tokens into
    # complete sentences suitable for TTS synthesis.
    splitter = StreamSplitter(min_chars=40, max_wait_ms=600)

    async def _token_stream():
        """Yield incremental new_text tokens from the orchestrator stream."""
        nonlocal current_run_id, full_response_text, current_session_id
        nonlocal _tool_hint_sent
        try:
            async for chunk in _orchestrator.process_stream(
                text=result.text,
                language=result.language,
                intent_result=intent_result,
            ):
                # Capture run_id on first chunk so abort can reference it.
                if (
                    chunk.run_id
                    and chunk.run_id not in ("local", "subprocess", "chat-fallback")
                    and current_run_id is None
                ):
                    current_run_id = chunk.run_id
                    if conn_state is not None:
                        conn_state["current_run_id"] = current_run_id
                        conn_state["current_session_id"] = current_session_id

                # Handle synthetic tool-call chunks emitted by the orchestrator.
                if chunk.type == "tool_started":
                    _tool_hint_sent = True
                    await broadcast_tool_call(
                        state="started",
                        tool_name=chunk.tool_name or "",
                        summary=chunk.tool_summary or "",
                    )
                    logger.debug(
                        f"Tool-call started: {chunk.tool_name!r} — {chunk.tool_summary!r}"
                    )
                    continue

                if chunk.type == "tool_finished":
                    await broadcast_tool_call(
                        state="finished",
                        tool_name=chunk.tool_name or "",
                        summary=chunk.tool_summary or "",
                    )
                    logger.debug(f"Tool-call finished: {chunk.tool_name!r}")
                    continue

                full_response_text = chunk.full_text
                if chunk.type == "error":
                    logger.error(f"Stream error from orchestrator: {chunk.error}")
                    return

                # Timing-based tool-hint: if the first text token arrives after a
                # long silence, we know the agent was doing tool work. Emit a
                # synthetic tool_started + tool_finished pair so the frontend orb
                # transitions to "working" even though the orchestrator didn't emit
                # explicit tool chunks (the gateway doesn't expose real-time tool
                # events to operator WS connections).
                if chunk.new_text and not _tool_hint_sent:
                    elapsed = time.monotonic() - t_stream_start
                    if elapsed > _TOOL_HINT_TTFT_S:
                        _tool_hint_sent = True
                        summary = _summarize_tool_call("", None)
                        await broadcast_tool_call(
                            state="started", tool_name="", summary=summary
                        )
                        await broadcast_tool_call(
                            state="finished", tool_name="", summary=summary
                        )
                        logger.debug(
                            f"Synthetic tool hint emitted after {elapsed:.1f}s TTFT"
                        )

                if chunk.new_text:
                    yield chunk.new_text
        except asyncio.CancelledError:
            raise

    try:
        async for sentence in splitter.process(_token_stream()):
            tts_text = strip_markdown_for_tts(sentence)
            if not tts_text.strip():
                continue

            try:
                audio_bytes = await _fish_tts.synthesize(tts_text)
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

                if not first_audio_sent:
                    first_audio_sent = True
                    elapsed_ms = (time.monotonic() - t_stream_start) * 1000
                    logger.info(
                        f"First audio chunk sent {elapsed_ms:.0f}ms after stream start"
                    )
                    # Transition to "speaking" on first TTS chunk so barge-in
                    # detection in _process_audio_for_client activates.
                    await broadcast_state("speaking")
                    if conn_state is not None:
                        conn_state["mode"] = "speaking"

                await broadcast_audio(audio_b64, sentence)
                # Set echo grace window so the barge-in detector ignores any
                # microphone bleed of this TTS chunk (no AEC during playback).
                if conn_state is not None:
                    conn_state["barge_in_grace_until"] = time.monotonic() + 0.4
            except FishTTSError as exc:
                logger.error(f"Fish TTS error on sentence: {exc}")

    except asyncio.CancelledError:
        logger.info("Streaming voice pipeline cancelled mid-stream")
        raise
    finally:
        # Always reset mode away from "speaking" when the stream ends,
        # regardless of whether it completed normally or was cancelled.
        if conn_state is not None and conn_state.get("mode") == "speaking":
            conn_state["mode"] = "idle"

    # Flush any remainder that didn't get yielded by the splitter before the
    # final event.  (The splitter's process() already handles this internally,
    # but full_response_text may have grown past the last yield.)

    if not full_response_text:
        logger.warning("No response text received from orchestrator")
        full_response_text = "Entschuldigung, es gab einen Fehler."
        if not first_audio_sent:
            try:
                audio_bytes = await _fish_tts.synthesize(
                    strip_markdown_for_tts(full_response_text)
                )
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                await broadcast_state("speaking")
                await broadcast_audio(audio_b64, full_response_text)
            except FishTTSError as exc:
                logger.error(f"Fish TTS fallback error: {exc}")

    logger.info(f"JARVIS: {full_response_text}")

    # Broadcast full transcript once, after streaming is complete.
    # This is the "full-text-at-end" strategy — simpler than incremental
    # transcript updates, and means the HUD transcript always shows the
    # complete response rather than partial sentences.
    await broadcast_transcript("jarvis", full_response_text)

    # Clear run tracking after successful completion.
    if conn_state is not None:
        conn_state["current_run_id"] = None
        conn_state["current_session_id"] = None

    # Memory: OpenClaw owns the conversational session; the local archive
    # was already written by the ``broadcast_transcript`` calls above.

    # --- Arm follow-up window (or go straight to idle) ------------------
    # After a successful turn, keep the mic open for a short window so the
    # user can continue speaking without repeating the wake word. Sleep
    # phrases short-circuit earlier in this function and never reach here.
    if _conversation_mode is not None and _conversation_mode.enabled:
        await _arm_follow_up_window(ws)
        logger.info("Voice pipeline complete, follow-up window armed")
    else:
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
      IDLE       → feed chunk to wake word detector
      LISTENING  → collect chunks until silence, then run pipeline
      FOLLOW_UP  → same as listening, but with a ``window_seconds`` pre-
                   speech timeout instead of 5 s — wake word not required.
                   On speech start the expiry timer is cancelled.

    Args:
        ws: The client WebSocket.
        chunk: Float32 16 kHz mono audio chunk.
    """
    conn_id = id(ws)
    state = _connection_state.get(conn_id)
    if state is None:
        return  # connection cleaned up

    mode = state[
        "mode"
    ]  # "idle" | "listening" | "follow_up" | "processing" | "speaking"

    if mode == "processing":
        # Pipeline is running — drop incoming chunks to avoid re-trigger
        return

    # ---- Barge-in detection ------------------------------------------------
    # When JARVIS is speaking, monitor incoming audio for sustained speech that
    # exceeds the configured sensitivity threshold. On detection: abort the
    # in-flight OpenClaw run, cancel the pipeline task, notify the frontend to
    # clear its audio queue, then fall through to collecting audio for the new
    # turn (same as entering listening mode from follow_up).
    if mode == "speaking":
        if not _barge_in_enabled:
            return

        # Re-entrancy guard: a batch of loud chunks must not fire abort twice.
        if state.get("barge_in_pending"):
            return

        now = time.monotonic()
        grace_until: float = state.get("barge_in_grace_until", 0.0)

        rms = _rms(chunk)

        # Normalise RMS to 0–1 float32 scale for barge-in comparison.
        # _rms() returns int16-scale values (0–32768); _barge_in_vad_rms_threshold
        # is stored in 0–1 scale (matching RMSVAD in src/audio/barge_in.py).
        rms_normalised = rms / 32768.0

        # 1Hz RMS debug telemetry — log current amplitude vs threshold every second so
        # barge-in issues can be diagnosed from the log without a code change.
        last_rms_log_at: float = state.get("barge_in_last_rms_log_at", 0.0)
        if now - last_rms_log_at >= 1.0:
            grace_remaining_ms = max(0.0, (grace_until - now) * 1000)
            sustained_ms = (
                (now - state["barge_in_speech_started_at"]) * 1000
                if state.get("barge_in_speech_started_at") is not None
                else 0.0
            )
            logger.debug(
                f"barge-in monitoring: rms={rms_normalised:.4f} threshold={_barge_in_vad_rms_threshold:.4f}"
                f" grace_remaining_ms={grace_remaining_ms:.0f} sustained_ms={sustained_ms:.0f}"
            )
            state["barge_in_last_rms_log_at"] = now

        # Use the dedicated barge-in VAD threshold (separate from _silence_threshold
        # which governs end-of-turn detection in listening/follow_up mode).
        # Compare normalised (0–1) RMS against the 0–1 config threshold.
        if rms_normalised > _barge_in_vad_rms_threshold:
            if state.get("barge_in_speech_started_at") is None:
                state["barge_in_speech_started_at"] = now
        else:
            state["barge_in_speech_started_at"] = None

        # Echo grace window: if we are still inside the post-TTS grace period,
        # discard any speech onset detected during that window and skip the
        # barge-in check entirely.  This prevents the mic from picking up
        # JARVIS's own playback as a user interruption before AEC can act.
        if now < grace_until:
            state["barge_in_speech_started_at"] = None
            return

        started_at: float | None = state.get("barge_in_speech_started_at")
        # If speech onset was recorded during the grace window (started_at
        # predates grace expiry), treat it as echo and discard.
        if started_at is not None and started_at < grace_until:
            state["barge_in_speech_started_at"] = None
            started_at = None

        if started_at is not None:
            sustained_ms = (now - started_at) * 1000
            if sustained_ms >= _barge_in_sensitivity_ms:
                state["barge_in_pending"] = True
                run_id = state.get("current_run_id")
                session_id = state.get("current_session_id")
                grace_remaining_ms = max(0.0, (grace_until - now) * 1000)
                logger.info(
                    f"Barge-in abort: sustained_ms={sustained_ms:.0f} "
                    f"grace_remaining_ms={grace_remaining_ms:.0f} "
                    f"run_id={run_id}"
                )

                # Abort OpenClaw turn.
                if run_id and session_id and _openclaw_client is not None:
                    try:
                        await _openclaw_client.abort_current_run(session_id, run_id)
                    except Exception as exc:
                        logger.warning(f"Barge-in abort failed: {exc}")

                # Cancel the in-flight pipeline task.
                task = state.get("pipeline_task")
                if task is not None and not task.done():
                    task.cancel()

                # Notify frontend to clear audio queue + stop current clip.
                await broadcast_barge_in()

                # Transition straight into listening so the user's utterance
                # is captured without a new wake word.
                state["mode"] = "listening"
                state["audio_chunks"] = [chunk]  # include this loud chunk
                state["speech_started"] = True
                state["silent_samples"] = 0
                state["total_samples"] = len(chunk)
                state["skip_remaining"] = 0
                state["barge_in_pending"] = False
                state["barge_in_speech_started_at"] = None
                state["barge_in_grace_until"] = 0.0
                state["current_run_id"] = None
                state["current_session_id"] = None
                await broadcast_state("listening")
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

    elif mode in ("listening", "follow_up"):
        silence_samples = int(_silence_duration_ms * _sample_rate / 1000)
        is_follow_up = mode == "follow_up"

        # Skip first N chunks after wake word detection (only in listening;
        # follow_up has no wake-word tail to discard).
        if state["skip_remaining"] > 0:
            state["skip_remaining"] -= 1
            return

        state["audio_chunks"].append(chunk)
        rms = _rms(chunk)
        total_samples = state["total_samples"] + len(chunk)
        state["total_samples"] = total_samples

        if rms > _silence_threshold:
            if is_follow_up and not state["speech_started"]:
                # First speech inside the follow-up window — cancel the
                # expiry timer so we don't return to idle mid-utterance.
                timer = state.get("follow_up_timer_task")
                if timer is not None and not timer.done():
                    timer.cancel()
                state["follow_up_timer_task"] = None
                logger.info("Follow-up continuation — speech detected in window")
                # Tell the HUD to drop the follow-up countdown ring — the
                # user has started speaking, so the wait-phase is over.
                await broadcast_conversation_mode(active=False, seconds_remaining=0.0)
            state["speech_started"] = True
            state["silent_samples"] = 0
        else:
            state["silent_samples"] += len(chunk)

        # Backchannel window: user has started speaking and is now pausing, but
        # not yet long enough to trigger end-of-turn. Play a low-volume "mhm"
        # to signal JARVIS is listening. BackchannelPlayer requires an external
        # audio player; we reuse the broadcast pipeline inline instead.
        if (
            _backchannels_enabled
            and state["speech_started"]
            and rms <= _silence_threshold
        ):
            silence_duration_s = state["silent_samples"] / _sample_rate
            eot_threshold_s = _silence_duration_ms / 1000
            backchannel_threshold_s = _backchannel_silence_threshold_ms / 1000
            if backchannel_threshold_s <= silence_duration_s < eot_threshold_s:
                lang = "de"  # TODO(language): per-connection language tracking — currently pinned to "de" because STT result language is only available inside _run_voice_pipeline_body. Threading it through requires connection-state plumbing.
                await _maybe_play_backchannel(state, lang)

        # After speech started, stop when we have enough silence
        if state["speech_started"] and state["silent_samples"] >= silence_samples:
            logger.debug("Silence detected after speech — starting pipeline")
            state["mode"] = "processing"
            chunks = list(state["audio_chunks"])
            state["audio_chunks"] = []
            state["pipeline_task"] = asyncio.create_task(
                _run_voice_pipeline(chunks, ws)
            )
            # Pipeline arms the next state (follow_up on success, idle on
            # sleep-close / failure). Reset intermediate mode here.
            state["mode"] = "idle"
            return

        # Pre-speech timeout: 10 s in listening, window_seconds in follow_up.
        pre_speech_timeout_samples = (
            int(
                (_conversation_mode.window_seconds if _conversation_mode else 18.0)
                * _sample_rate
            )
            if is_follow_up
            else 10 * _sample_rate
        )
        if not state["speech_started"] and total_samples > pre_speech_timeout_samples:
            if is_follow_up:
                # The expiry task handles the idle broadcast — here we just
                # tidy up the state in case the task fired slightly earlier.
                logger.debug("Follow-up pre-speech timeout — closing window")
                await _close_follow_up_window(conn_id, "expired")
                await broadcast_state("idle")
            else:
                logger.debug("No speech detected in 10 seconds, returning to idle")
                state["mode"] = "idle"
                state["audio_chunks"] = []
                await broadcast_state("idle")
            return

        # No hard max-recording cap — rely on VAD silence detection to close the utterance.


# ---------------------------------------------------------------------------
# Command handler
# ---------------------------------------------------------------------------


async def _handle_command(
    data: dict[str, Any],
    ws: web.WebSocketResponse,
) -> None:
    """Handle an incoming JSON WebSocket command.

    Args:
        data: Parsed command data (``{"type": "...", "payload": {...}}``).
        ws: The client connection — used to scope per-connection actions
            (e.g. ``cancel_turn`` only aborts the caller's pipeline).
    """
    global _tts_engine

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
        # Session memory is owned by OpenClaw; the local archive
        # (``MemoryStore``) is append-only and must not be wiped by a
        # UI click. Acknowledge the command in the log and no-op.
        logger.info("Memory-reset command received (no-op; OpenClaw owns memory)")

    elif cmd_type == "cancel_turn":
        await _cancel_current_turn(ws)

    else:
        logger.warning(f"Unknown command type: {cmd_type}")


async def _cancel_current_turn(ws: web.WebSocketResponse) -> None:
    """Abort the in-flight voice turn for ``ws`` (idempotent).

    Cancels any outstanding ``_run_voice_pipeline`` task tracked on the
    connection, closes an active follow-up window, resets the connection
    state to idle and broadcasts both a ``status=idle`` frame and an info
    notification so the HUD can confirm the stop visually.
    """
    conn_id = id(ws)
    state = _connection_state.get(conn_id)
    if state is None:
        logger.debug("cancel_turn received but no connection state — dropping")
        return

    task: asyncio.Task[Any] | None = state.get("pipeline_task")
    had_task = task is not None and not task.done()

    if had_task:
        logger.info("Cancel-turn received; aborting pipeline")
        assert task is not None
        task.cancel()
    else:
        logger.info("Cancel-turn received; no active pipeline task")

    # Abort the in-flight OpenClaw WS turn so the gateway stops streaming.
    run_id: str | None = state.get("current_run_id")
    session_id_str: str | None = state.get("current_session_id")
    if run_id and session_id_str and _openclaw_client is not None:
        try:
            await _openclaw_client.abort_current_run(session_id_str, run_id)
            logger.info(f"Sent WS abort for run_id={run_id}")
        except Exception as exc:
            logger.warning(f"WS abort failed: {exc}")

    # Close any armed follow-up window before we reset state.
    await _close_follow_up_window(conn_id, "user_cancelled")

    # Reset per-connection state so the next wake word starts fresh.
    state["mode"] = "idle"
    state["audio_chunks"] = []
    state["speech_started"] = False
    state["silent_samples"] = 0
    state["total_samples"] = 0
    state["skip_remaining"] = 0
    state["pipeline_task"] = None
    state["current_run_id"] = None
    state["current_session_id"] = None
    state["barge_in_speech_started_at"] = None
    state["barge_in_pending"] = False
    state["barge_in_grace_until"] = 0.0
    state["barge_in_last_rms_log_at"] = 0.0

    if _wake_word_detector is not None:
        _wake_word_detector.reset()

    await broadcast_state("idle")

    # Stable notification id so client-side dedup collapses repeated
    # cancels — the HUD shows a single "Konversation gestoppt" toast
    # even if the user mashes STOP.
    await broadcast_notification(
        notification_id="voice-cancel",
        severity="info",
        title="Konversation gestoppt",
        detail="Die laufende Anfrage wurde abgebrochen.",
    )


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
        "mode": "idle",  # "idle" | "listening" | "follow_up" | "processing" | "speaking"
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
        # Async task driving the follow-up expiry — cancelled as soon as
        # speech is detected inside the window or a sleep phrase closes it.
        "follow_up_timer_task": None,
        # Async task running the voice pipeline for this connection. Set
        # when speech ends and silence is detected; cleared when the
        # pipeline returns or is cancelled via the STOP UI button.
        "pipeline_task": None,
        # Current streaming run ID and session — set by the pipeline while
        # an OpenClaw WS turn is in flight so _cancel_current_turn can abort.
        "current_run_id": None,
        "current_session_id": None,
        # Barge-in tracking: timestamp when sustained speech began (None if
        # currently silent), plus a flag to prevent double-firing.
        "barge_in_speech_started_at": None,
        "barge_in_pending": False,
        # Throttle: monotonic timestamp of the last 1Hz RMS debug log emission.
        "barge_in_last_rms_log_at": 0.0,
        # Echo grace window: barge-in is suppressed until this monotonic
        # timestamp expires (set after each TTS chunk broadcast to avoid
        # the mic picking up JARVIS's own audio before AEC can act).
        "barge_in_grace_until": 0.0,
        # Backchannel: monotonic timestamp of last broadcast clip.
        "last_backchannel_at": 0.0,
    }
    if _wake_word_detector:
        _wake_word_detector.reset()

    logger.info(f"Client connected. Total clients: {len(_connected_clients)}")

    # Send initial state
    await ws.send_str(json.dumps({"type": "status", "state": "idle"}))
    await broadcast_system_metrics()

    # Per-client "welcome" notification — stable id ensures the frontend
    # dedups across reconnects within the same session, yet a fresh
    # browser tab always sees the HUD pipe is live.
    from datetime import datetime, timezone

    await ws.send_str(
        json.dumps(
            {
                "type": "notification",
                "payload": {
                    "id": "startup-ok",
                    "severity": "info",
                    "title": "JARVIS online",
                    "detail": ("Voice-Pipeline, OpenClaw-Gateway und HUD verbunden."),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
        )
    )

    # Mark the first-client event so other subsystems (scheduler, tests)
    # can still observe "at least one client has been here".
    if not _first_client_event.is_set():
        _first_client_event.set()

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await _handle_command(data, ws)
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
        # Cancel any pending follow-up timer so the background task doesn't
        # fire into a vanished connection.
        await _close_follow_up_window(conn_id, "cleanup")
        # Cancel any in-flight pipeline task for this connection so its
        # late audio broadcast doesn't land on a closed socket.
        _state_snapshot = _connection_state.get(conn_id)
        if _state_snapshot is not None:
            _pending_task = _state_snapshot.get("pipeline_task")
            if _pending_task is not None and not _pending_task.done():
                _pending_task.cancel()
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
    memory: Any = None,
    tts_engine: Any = None,
) -> None:
    """Start the WebSocket and HTTP server and initialise the voice pipeline.

    Args:
        config: API configuration section.
        memory: Legacy parameter; ignored. OpenClaw owns session memory,
            and the local archive (:class:`brain.memory.MemoryStore`) is
            initialised internally. Kept in the signature for call-site
            compat with older integrations.
        tts_engine: Unused (kept for API compatibility). Fish TTS is
            initialised internally.
    """
    global _memory_store, _openclaw_client, _tts_engine, _fish_tts
    global _stt_engine, _wake_word_detector
    global _orchestrator, _intent_parser, _start_time
    global _silence_threshold, _silence_duration_ms, _sample_rate
    global _metrics_collector, _metrics_task
    global _conversation_mode, _persona_config
    global _filler_cache, _ack_cache, _backchannel_cache, _quick_ack_generator
    global _barge_in_enabled, _barge_in_sensitivity_ms, _barge_in_vad_rms_threshold
    global _backchannels_enabled, _backchannel_silence_threshold_ms, _backchannel_min_interval_seconds
    global _quick_ack_enabled

    from dotenv import load_dotenv

    from brain.claude_client import create_claude_client
    from utils.config_loader import get_config

    del memory  # Ignored — see docstring.

    load_dotenv()
    cfg = get_config()

    _tts_engine = tts_engine
    _start_time = time.time()

    # Conversation mode — follow-up window + sleep-phrase detection.
    voice_config = cfg.get_section("voice") or {}
    _conversation_mode = ConversationMode.from_config(
        voice_config.get("conversation_mode")
    )
    if _conversation_mode.enabled:
        logger.info(
            "Conversation mode enabled — follow-up window: "
            f"{_conversation_mode.window_seconds:.1f}s"
        )
    else:
        logger.info("Conversation mode disabled — wake word required every turn")

    # Persona snapshot for sleep-phrase closing salutations.
    _persona_config = cfg.get_section("persona") or {}

    # Barge-in + backchannel + quick-ack feature flags from voice config.
    _barge_in_enabled = bool(voice_config.get("barge_in_enabled", True))
    _barge_in_sensitivity_ms = int(voice_config.get("barge_in_sensitivity_ms", 400))
    _barge_in_vad_rms_threshold = float(
        voice_config.get("barge_in_vad_rms_threshold", 0.02)
    )
    _backchannels_enabled = bool(voice_config.get("backchannels_enabled", True))
    _backchannel_silence_threshold_ms = int(
        voice_config.get("backchannel_silence_threshold_ms", 1200)
    )
    _backchannel_min_interval_seconds = float(
        voice_config.get("backchannel_min_interval_seconds", 3.0)
    )
    _quick_ack_enabled = bool(voice_config.get("quick_ack_enabled", True))

    # Load voice cache prefixes. Path defaults to ``data/voice_cache``;
    # override via ``voice.cache_directory``.
    filler_dir_str = voice_config.get("cache_directory", "data/voice_cache")
    filler_dir = Path(filler_dir_str)
    if not filler_dir.is_absolute():
        filler_dir = Path.cwd() / filler_dir
    _filler_cache = _load_voice_cache(filler_dir, "filler")
    _ack_cache = _load_voice_cache(filler_dir, "ack")
    _backchannel_cache = _load_voice_cache(filler_dir, "backchannel")

    # Lazy-init QuickAckGenerator singleton (cache_dir is for wav lookup; we
    # use _ack_cache bytes directly, so the dir is only used by has_cached_audio).
    _quick_ack_generator = QuickAckGenerator(filler_dir)

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

    # --- OpenClaw health check (fail-fast at startup) ---
    # All LLM traffic now routes through the OpenClaw gateway. If the
    # daemon is not reachable there is no fallback path (the user asked
    # for `claude login` only — no Anthropic SDK at runtime). We log
    # loudly but do NOT hard-exit: the HUD must still come up so the
    # user gets a visible "offline" notification instead of a silent
    # dead backend.
    openclaw_config = cfg.get_section("openclaw")
    _openclaw_client = OpenClawClient(openclaw_config)
    try:
        await _openclaw_client.initialize()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"OpenClaw client init failed: {exc}")

    if await _openclaw_client.is_healthy():
        logger.info(
            f"OpenClaw gateway reachable — LLM path: OpenClaw "
            f"(session={_openclaw_client.session_id})"
        )
    else:
        logger.critical(
            "OpenClaw gateway NOT reachable — conversational turns will "
            "fall back to spoken offline message. Run "
            "'openclaw doctor' to diagnose."
        )

    # --- Memory store (archive of transcripts / events) ---
    memory_cfg = cfg.get_section("memory")
    if memory_cfg.get("enabled", True):
        _memory_store = MemoryStore(db_path=memory_cfg.get("db_path", "data/jarvis.db"))
        try:
            await _memory_store.initialize()
            logger.info(
                f"MemoryStore initialised (archive path: {_memory_store.db_path})"
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"MemoryStore init failed — archiving disabled: {exc}")
            _memory_store = None

    # LLM client (OpenClaw-backed) + orchestrator
    logger.info("Initialising LLM client (OpenClaw-backed)...")
    claude_client = await create_claude_client(openclaw_client=_openclaw_client)

    _orchestrator = Orchestrator(
        claude_client=claude_client,
        memory=None,
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

    # Background metrics broadcast — 2 s interval via SystemMetricsCollector.
    _metrics_collector = SystemMetricsCollector(interval_seconds=2.0)
    _metrics_task = asyncio.create_task(_metrics_collector.run(_on_metrics_snapshot))

    # Keep running until cancelled (e.g. SIGINT from main.py).
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("WebSocket server cancelled — shutting down...")
        raise
    finally:
        # Clean teardown of the metrics collector.
        if _metrics_collector is not None:
            await _metrics_collector.stop()
        if _metrics_task is not None and not _metrics_task.done():
            _metrics_task.cancel()
            try:
                await _metrics_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        _metrics_collector = None
        _metrics_task = None

        # Cancel any in-flight pipeline tasks before closing clients so
        # aiohttp handler coroutines aren't blocked waiting on them.
        _pending_pipeline_tasks: list[asyncio.Task[Any]] = [
            state["pipeline_task"]
            for state in _connection_state.values()
            if state.get("pipeline_task") is not None
            and not state["pipeline_task"].done()
        ]
        if _pending_pipeline_tasks:
            for _pt in _pending_pipeline_tasks:
                _pt.cancel()
            await asyncio.gather(*_pending_pipeline_tasks, return_exceptions=True)

        # Force-close all connected WebSocket clients before runner cleanup.
        # aiohttp's AppRunner.cleanup() waits for active handler coroutines;
        # closing the sockets first lets those handlers exit promptly.
        _clients_to_close = list(_connected_clients)
        for _ws in _clients_to_close:
            try:
                await _ws.close(code=1001, message=b"shutdown")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Error closing client WS during shutdown: {exc}")
        _connected_clients.clear()

        # Tear down aiohttp runners — each wrapped in a per-step timeout so
        # even a stalled cleanup can't block shutdown indefinitely.
        try:
            await asyncio.wait_for(ws_runner.cleanup(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("ws_runner cleanup timed out after 5 s — forcing shutdown")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"ws_runner cleanup failed: {exc}")
        try:
            await asyncio.wait_for(http_runner.cleanup(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("http_runner cleanup timed out after 5 s — forcing shutdown")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"http_runner cleanup failed: {exc}")

        # Close OpenClaw + MemoryStore.
        if _openclaw_client is not None:
            try:
                await asyncio.wait_for(_openclaw_client.close(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("OpenClaw client close timed out after 5 s")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"OpenClaw client close failed: {exc}")
        if _memory_store is not None:
            try:
                await asyncio.wait_for(_memory_store.close(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("MemoryStore close timed out after 5 s")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"MemoryStore close failed: {exc}")
