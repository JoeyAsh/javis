"""WebSocket and HTTP server for JARVIS.

Provides real-time communication between the backend and frontend clients.
Audio is now captured in the browser and streamed here as raw Int16 PCM.
The server handles wake word detection, Whisper STT, Claude orchestration,
and Fish Audio TTS — then streams the MP3 response back to the frontend.
"""

import asyncio
import base64
import json
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from aiohttp import web

from api.mcp_server import (
    get_sse_advertise_url,
    list_registered_tools,
    start_mcp_server,
    stop_mcp_server,
)
from utils.device import resolve_device_slug
from api.system_metrics import SystemMetrics, SystemMetricsCollector
from audio.fish_tts import FishTTSClient, FishTTSError, strip_markdown_for_tts
from audio.stream_splitter import StreamSplitter
from audio.stt import SpeechToText, create_stt_engine
from audio.wake_word import WakeWordDetector, create_wake_word_detector
from brain.conversation_mode import ConversationMode
from brain.conversation_state import ConversationState, ConversationStateMachine
from brain.memory import MemoryStore
from brain.intent_parser import Intent, IntentParser, get_intent_parser
from brain.narration_queue import NarrationQueue
from brain.quick_ack import QuickAckGenerator
from brain.orchestrator import Orchestrator
from brain.salutation import get_salutation
from integrations.openclaw import OpenClawClient
from integrations.spotify import SpotifyClient
from utils.logger import get_logger

logger = get_logger("ws_server")

# ---------------------------------------------------------------------------
# Device identity — resolved once at module startup
# ---------------------------------------------------------------------------

# Stable slug for this JARVIS instance (e.g. "laptop-paps").  Derived from
# JARVIS_DEVICE_NAME env var or sanitized hostname via resolve_device_slug().
_device_slug: str = resolve_device_slug()

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

# Conversational state machine and narration queue (#93 Phase 1).
_state_machine: ConversationStateMachine | None = None
_narration_queue: NarrationQueue | None = None
_narration_drainer_task: asyncio.Task[None] | None = None

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

# ---------------------------------------------------------------------------
# Phrase-cache hit / miss counters (Item 2: cache metrics)
# ---------------------------------------------------------------------------
# Module-level counters, incremented on every playback attempt.
# "hit"  = a file was found in cache and played.
# "miss" = cache was empty / language pool absent → silent skip.
_phrase_cache_stats: dict[str, int] = {
    "filler_hits": 0,
    "filler_misses": 0,
    "ack_hits": 0,
    "ack_misses": 0,
    "backchannel_hits": 0,
    "backchannel_misses": 0,
    "sleep_match_hits": 0,
}

# Background task handle for periodic metric logging.
_cache_stats_log_task: asyncio.Task[None] | None = None

# Spotify integration — client singleton and background task handle.
_spotify_client: SpotifyClient | None = None
_spotify_poller_task: asyncio.Task[None] | None = None
# Set to True by a scope-gated REST handler when SpotifyAuthError is raised
# (indicating the cached token lacks the new library/queue scopes).  Cleared
# after a successful authentication. The poller picks it up on the next tick
# and emits scope_upgrade_required=True in the WS spotify_state broadcast.
_spotify_scope_upgrade_pending: bool = False
# Cached device_id announced by the HUD via spotify_device_announce WS message.
# Set when the SDK reports ready=True; cleared on ready=False or disconnect.
_jarvis_spotify_device_id: str | None = None
# Sentinel used by play handlers to distinguish "key absent" from "key present but null".
_MISSING: object = object()


def get_narration_queue() -> "NarrationQueue | None":
    """Return the process-wide NarrationQueue singleton, or None if not initialised."""
    return _narration_queue


def get_spotify_client() -> SpotifyClient | None:
    """Return the process-wide SpotifyClient singleton, or None if not initialised."""
    return _spotify_client


def get_spotify_device_id() -> str | None:
    """Return the Spotify Connect device ID announced by the HUD, or None."""
    return _jarvis_spotify_device_id


# GitHub integration — poller singleton and aiohttp session handle.
_github_poller: Any = None  # GitHubPoller | None
_github_session: Any = None  # aiohttp.ClientSession | None

# GitLab integration — poller singleton and background task handle.
_gitlab_client: Any = None  # GitLabClient | None
_gitlab_poller: Any = None  # GitLabPoller | None
_gitlab_poller_task: asyncio.Task[None] | None = None

# System metrics collector + last snapshot (used for initial per-connection push)
_metrics_collector: SystemMetricsCollector | None = None
_metrics_task: asyncio.Task[None] | None = None
_last_metrics: SystemMetrics | None = None

# Calendar integration — poller task handle.
_calendar_poller_task: asyncio.Task[None] | None = None

# Per-connection state key — stored on the ws object via a dict keyed by ws id
_connection_state: dict[int, dict[str, Any]] = {}


def get_calendar_client() -> Any:
    """Lazy proxy for the GoogleCalendarClient singleton — importable and patchable.

    Wraps ``integrations.google.calendar_client.get_calendar_client`` so that
    tests can patch ``api.ws_server.get_calendar_client`` without reaching into
    the integration module.

    Returns:
        Shared ``GoogleCalendarClient`` instance.
    """
    from integrations.google.calendar_client import (  # noqa: PLC0415
        get_calendar_client as _get_cc,
    )

    return _get_cc()


def get_gmail_client(vip_senders: list[str] | None = None) -> Any:
    """Lazy proxy for the GmailClient singleton — importable and patchable.

    Wraps ``integrations.google.gmail_client.get_gmail_client`` so that tests
    can patch ``api.ws_server.get_gmail_client`` rather than needing to reach
    into the integration module.

    Args:
        vip_senders: Optional VIP sender list forwarded on first creation.

    Returns:
        Shared ``GmailClient`` instance.
    """
    from integrations.google.gmail_client import (  # noqa: PLC0415
        get_gmail_client as _get_gc,
    )

    return _get_gc(vip_senders=vip_senders)

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


async def broadcast_mail_state(
    messages: list[dict[str, Any]],
    unread_count: int,
) -> None:
    """Broadcast the current mail state to all connected clients.

    Args:
        messages: List of serialised ``MailMessage`` dicts (camelCase keys).
        unread_count: Total number of unread messages.
    """
    global _last_unread_count
    _last_unread_count = unread_count
    message = json.dumps(
        {
            "type": "mail_state",
            "payload": {
                "messages": messages,
                "unread_count": unread_count,
            },
        }
    )
    await _broadcast(message)


async def broadcast_calendar_state(
    events: list[dict[str, Any]],
    date_label: str,
) -> None:
    """Broadcast current calendar events to all connected clients.

    Args:
        events: List of serialised ``CalendarEvent`` dicts (camelCase keys).
        date_label: Human-readable date context label (e.g. ``"Today"``).
    """
    global _last_calendar_count
    _last_calendar_count = len(events)
    message = json.dumps(
        {
            "type": "calendar_state",
            "payload": {
                "events": events,
                "dateLabel": date_label,
            },
        }
    )
    await _broadcast(message)


async def _emit_synthetic_utterance(text: str, language: str = "de") -> None:
    """Synthesise ``text`` through Fish TTS and broadcast audio to all clients.

    Used as the ``tts_emit`` callback for the NarrationQueue so background
    narration items flow through the same Fish Audio → base64 → broadcast
    path as user-turn responses.

    Marks the conversation state machine as speaking / idle around the call
    so the queue drainer pauses correctly during playback.

    Args:
        text: Plain-text string to synthesise.
        language: Language hint (unused by Fish TTS but kept for future
            prosody/voice selection).
    """
    global _fish_tts, _state_machine

    if _fish_tts is None:
        logger.warning("_emit_synthetic_utterance: Fish TTS not initialised — skipping")
        return
    if not text.strip():
        return

    if _state_machine is not None:
        _state_machine.on_tts_start()
    try:
        from audio.fish_tts import FishTTSError, strip_markdown_for_tts  # noqa: PLC0415
        from audio.stream_splitter import StreamSplitter  # noqa: PLC0415

        splitter = StreamSplitter(min_chars=20, max_wait_ms=400)

        async def _single_token():
            yield text

        async for sentence in splitter.process(_single_token()):
            tts_text = strip_markdown_for_tts(sentence)
            if not tts_text.strip():
                continue
            try:
                audio_bytes = await _fish_tts.synthesize(tts_text)
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                await broadcast_state("speaking")
                await broadcast_audio(audio_b64, sentence)
            except FishTTSError as exc:
                logger.warning(f"_emit_synthetic_utterance TTS error: {exc}")

    except Exception as exc:
        logger.warning(f"_emit_synthetic_utterance failed: {exc}")
    finally:
        if _state_machine is not None:
            _state_machine.on_tts_end()


async def broadcast_calendar_op_preview(payload: dict[str, Any]) -> None:
    """Broadcast a calendar operation preview to all connected clients.

    Called before waiting for voice confirmation on create/update/delete.

    Args:
        payload: Dict with keys ``op``, ``title``, ``start``, ``end``,
            ``confirm_prompt``.
    """
    message = json.dumps({"type": "calendar_op_preview", "payload": payload})
    await _broadcast(message)


async def broadcast_calendar_op_done(payload: dict[str, Any]) -> None:
    """Broadcast the result of a calendar operation to all connected clients.

    Args:
        payload: Dict with keys ``op``, ``success`` (bool), optionally
            ``event_id`` and ``error``.
    """
    message = json.dumps({"type": "calendar_op_done", "payload": payload})
    await _broadcast(message)


async def broadcast_drive_result(files: list[dict[str, Any]], query: str = "") -> None:
    """Broadcast Drive search results to all connected clients.

    Fired after the orchestrator builds Drive context so the frontend can
    display results as a notification or panel. No poller — Drive state is
    always voice-triggered.

    Args:
        files: List of serialised ``DriveFile`` dicts with camelCase keys
            (``id``, ``name``, ``mimeType``, ``modifiedTime``, ``webViewLink``).
        query: The search query string that produced these results.
    """
    message = json.dumps(
        {
            "type": "drive_result",
            "payload": {
                "query": query,
                "files": files,
            },
        }
    )
    await _broadcast(message)


async def broadcast_email_draft_preview(payload: dict[str, Any]) -> None:
    """Broadcast an email draft preview to all connected clients.

    Args:
        payload: Dict with keys ``draft_id``, ``to``, ``subject``,
            ``body_preview``, ``created_at``.
    """
    message = json.dumps({"type": "email_draft_preview", "payload": payload})
    await _broadcast(message)


async def broadcast_email_send_done(payload: dict[str, Any]) -> None:
    """Broadcast the result of an email send attempt to all connected clients.

    Args:
        payload: Dict with keys ``draft_id``, ``success`` (bool), and
            optionally ``message_id`` or ``error``.
    """
    message = json.dumps({"type": "email_send_done", "payload": payload})
    await _broadcast(message)


async def broadcast_spotify_state(
    authenticated: bool,
    track: Any = None,
    scope_upgrade_required: bool = False,
) -> None:
    """Broadcast current Spotify playback state to all connected clients.

    Args:
        authenticated: Whether the Spotify client has a valid token.
        track: SpotifyTrackInfo instance, or None when nothing is playing.
        scope_upgrade_required: True when the token exists but lacks the
            scopes required by the new library/queue endpoints so the HUD
            can show a re-auth prompt.
    """
    from integrations.spotify.client import SpotifyTrackInfo  # noqa: PLC0415

    if track is not None and isinstance(track, SpotifyTrackInfo):
        payload: dict[str, Any] = {
            "authenticated": authenticated,
            "playing": track.is_playing,
            "title": track.name,
            "artist": track.artist,
            "album": track.album,
            "progress_ms": track.progress_ms,
            "duration_ms": track.duration_ms,
            "shuffle": track.shuffle,
            "repeat": track.repeat,
            "device": track.device_name,
            "scope_upgrade_required": scope_upgrade_required,
        }
        if track.album_art_url:
            payload["album_art_url"] = track.album_art_url
    else:
        payload = {
            "authenticated": authenticated,
            "playing": False,
            "title": "",
            "artist": "",
            "album": "",
            "progress_ms": 0,
            "duration_ms": 0,
            "shuffle": False,
            "repeat": "off",
            "device": "",
            "scope_upgrade_required": scope_upgrade_required,
        }

    message = json.dumps({"type": "spotify_state", "payload": payload})
    await _broadcast(message)


async def broadcast_github_state(payload: Any) -> None:
    """Broadcast GitHub state payload to all connected WebSocket clients.

    The payload is an instance of :class:`integrations.github.client.GitHubStatePayload`.
    Serialises the dataclass fields manually to avoid a dependency on ``dataclasses.asdict``
    for nested lists.

    Args:
        payload: A ``GitHubStatePayload`` instance from the GitHub poller.
    """
    body = {
        "prs": [
            {
                "id": pr.id,
                "repo": pr.repo,
                "title": pr.title,
                "author": pr.author,
                "html_url": pr.html_url,
                "updated_at": pr.updated_at,
            }
            for pr in payload.prs
        ],
        "issues": [
            {
                "id": issue.id,
                "repo": issue.repo,
                "title": issue.title,
                "html_url": issue.html_url,
                "updated_at": issue.updated_at,
            }
            for issue in payload.issues
        ],
        "ci": [
            {
                "repo": run.repo,
                "status": run.status,
                "ran_at": run.ran_at,
                "html_url": run.html_url,
            }
            for run in payload.ci
        ],
        "fetched_at": payload.fetched_at,
        "stale": payload.stale,
    }
    message = json.dumps({"type": "github_state", "payload": body})
    await _broadcast(message)


async def broadcast_gitlab_state(payload: Any) -> None:
    """Broadcast GitLab state payload to all connected WebSocket clients.

    The payload is a :class:`integrations.gitlab.client.GitLabState` instance.
    Serialises the dataclass fields manually to a ``gitlab_state`` WS frame.

    Args:
        payload: A ``GitLabState`` instance from the GitLab poller.
    """
    body = {
        "mrs": [
            {
                "id": mr.id,
                "iid": mr.iid,
                "title": mr.title,
                "source_branch": mr.source_branch,
                "web_url": mr.web_url,
                "author": mr.author,
                "created_at": mr.created_at,
                "draft": mr.draft,
            }
            for mr in payload.mrs
        ],
        "issues": [
            {
                "id": issue.id,
                "iid": issue.iid,
                "title": issue.title,
                "labels": issue.labels,
                "web_url": issue.web_url,
                "author": issue.author,
                "created_at": issue.created_at,
            }
            for issue in payload.issues
        ],
        "pipelines": [
            {
                "project": pipeline.project,
                "status": pipeline.status,
                "web_url": pipeline.web_url,
                "created_at": pipeline.created_at,
            }
            for pipeline in payload.pipelines
        ],
        "error": payload.error,
    }
    message = json.dumps({"type": "gitlab_state", "payload": body})
    await _broadcast(message)


async def _start_gitlab_poller(
    token: str,
    url: str,
    projects: list[str],
    poll_interval: int,
) -> None:
    """Initialise the GitLab client and start the background poller task.

    Creates a :class:`GitLabClient`, wraps it in a :class:`GitLabPoller`,
    and starts the poll loop as an ``asyncio.Task``.  Stores both the client
    and the task in module-level globals for teardown.

    Args:
        token: GitLab personal access token (``api`` + ``read_repository`` scopes).
        url: Base URL of the GitLab instance (normalised; trailing slash stripped).
        projects: List of project slugs or numeric IDs to watch pipelines for.
        poll_interval: Seconds between polling ticks.
    """
    global _gitlab_client, _gitlab_poller, _gitlab_poller_task

    from integrations.gitlab.client import GitLabClient  # noqa: PLC0415
    from integrations.gitlab.poller import GitLabPoller  # noqa: PLC0415

    _gitlab_client = GitLabClient(token=token, url=url, projects=projects)
    _gitlab_poller = GitLabPoller(client=_gitlab_client, interval_seconds=poll_interval)
    await _gitlab_poller.run(on_state=broadcast_gitlab_state)
    _gitlab_poller_task = _gitlab_poller._task
    logger.info(
        f"GitLab poller started (interval={poll_interval}s, "
        f"url={url}, projects={projects})"
    )


async def _start_github_poller(
    token: str,
    repos: list[str],
    poll_interval: int,
) -> None:
    """Initialise the GitHub client and start the background poller.

    Creates a dedicated ``aiohttp.ClientSession``, builds a :class:`GitHubClient`,
    wraps it in a :class:`GitHubPoller`, and calls ``poller.start()``.  Stores
    both the session and the poller in module-level globals for teardown.

    Args:
        token: Classic PAT for GitHub REST v3 (read scope).
        repos: Explicit repo whitelist for CI fetches and search scoping.
        poll_interval: Seconds between polling ticks.
    """
    global _github_poller, _github_session

    import aiohttp as _aiohttp  # noqa: PLC0415
    from integrations.github.client import GitHubClient  # noqa: PLC0415
    from integrations.github.poller import GitHubPoller  # noqa: PLC0415

    _github_session = _aiohttp.ClientSession()
    client = GitHubClient(token=token, session=_github_session)
    _github_poller = GitHubPoller(
        client=client,
        repos=repos,
        poll_interval=poll_interval,
        broadcast_fn=broadcast_github_state,
    )
    await _github_poller.start()
    logger.info(f"GitHub poller started (interval={poll_interval}s, repos={repos})")


async def _spotify_state_loop(client: SpotifyClient, interval_seconds: int) -> None:
    """Background poller: fetch Spotify state and broadcast to all clients.

    Polling stops gracefully when no active device is detected (to avoid
    burning API quota). A 429 rate-limit response backs off for one
    additional interval before retrying.

    On each tick the poller reads the module-level ``_spotify_scope_upgrade_pending``
    flag (set by scope-gated REST handlers when they receive a 401) and forwards
    it in the ``scope_upgrade_required`` field of the WS broadcast. The flag is
    cleared once the client re-authenticates successfully.

    Args:
        client: Initialised SpotifyClient instance.
        interval_seconds: Seconds between polling ticks.
    """
    global _spotify_scope_upgrade_pending

    from integrations.spotify.client import SpotifyAuthError, SpotifyPollError  # noqa: PLC0415

    logger.info(f"Spotify state poller started (interval={interval_seconds}s)")

    while True:
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("Spotify poller cancelled")
            return

        if not client.is_authenticated():
            await broadcast_spotify_state(
                authenticated=False,
                scope_upgrade_required=_spotify_scope_upgrade_pending,
            )
            continue

        try:
            track = await client.get_playback_state()
            # Clear scope-upgrade flag on successful poll (token is valid).
            if _spotify_scope_upgrade_pending:
                _spotify_scope_upgrade_pending = False
                logger.info("Spotify scope upgrade flag cleared after successful auth")
            await broadcast_spotify_state(
                authenticated=True,
                track=track,
                scope_upgrade_required=False,
            )
            if track is None:
                logger.debug("Spotify: no active device — poll returned None")
        except SpotifyAuthError as exc:
            logger.warning(f"Spotify auth error during poll: {exc}")
            await broadcast_spotify_state(
                authenticated=False,
                scope_upgrade_required=_spotify_scope_upgrade_pending,
            )
        except SpotifyPollError as exc:
            logger.warning(f"Spotify poll error (will retry): {exc}")
            # Extra back-off for rate limit — sleep an additional interval.
            try:
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                logger.info("Spotify poller cancelled during backoff")
                return
        except asyncio.CancelledError:
            logger.info("Spotify poller cancelled")
            return
        except Exception as exc:
            logger.error(f"Spotify poller unexpected error: {exc}")


async def spotify_oauth_start_handler(request: web.Request) -> web.Response:
    """Handle GET /oauth/spotify/start — redirect browser to Spotify's OAuth page.

    Registered on the HTTP server at :8766.  The frontend AuthPrompt
    VERBINDEN button opens this URL directly; the handler delegates PKCE
    challenge / scope / redirect_uri construction to
    :meth:`SpotifyClient.get_auth_url` and issues a 302 redirect so the
    browser lands on Spotify's authorize endpoint.

    Returns:
        302 redirect to the Spotify authorize URL, or 503 if the Spotify
        integration is not initialised.
    """
    if _spotify_client is None:
        return web.Response(
            status=503,
            content_type="text/html",
            text=(
                "<html><body><h2>Spotify client not ready.</h2>"
                "<p>The backend Spotify integration is not initialised.</p></body></html>"
            ),
        )

    auth_url = _spotify_client.get_auth_url()
    logger.info("Redirecting to Spotify OAuth URL")
    raise web.HTTPFound(location=auth_url)


async def spotify_oauth_callback_handler(request: web.Request) -> web.Response:
    """Handle GET /oauth/spotify/callback — exchange PKCE code for token.

    Registered on the HTTP server at :8766.  On success returns a plain
    HTML page that closes the browser tab.

    Args:
        request: Incoming aiohttp request with ``code`` query parameter.

    Returns:
        200 HTML confirmation page, or 400/503 error page.
    """
    global _spotify_client, _spotify_poller_task

    code = request.rel_url.query.get("code")

    if not code:
        return web.Response(
            status=400,
            content_type="text/html",
            text=(
                "<html><body><h2>Authorization failed.</h2>"
                "<p>No authorization code received from Spotify.</p></body></html>"
            ),
        )

    if _spotify_client is None:
        return web.Response(
            status=503,
            content_type="text/html",
            text=(
                "<html><body><h2>Spotify client not ready.</h2>"
                "<p>The backend Spotify integration is not initialised.</p></body></html>"
            ),
        )

    from utils.config_loader import get_config as _gcfg  # noqa: PLC0415
    from integrations.spotify.client import SpotifyAuthError  # noqa: PLC0415

    try:
        await _spotify_client.complete_auth(code)
    except SpotifyAuthError as exc:
        logger.error(f"Spotify OAuth callback failed: {exc}")
        return web.Response(
            status=400,
            content_type="text/html",
            text=(
                "<html><body><h2>Authorization code expired or already used.</h2>"
                f"<p>{exc}</p></body></html>"
            ),
        )

    logger.info("Spotify OAuth complete — starting state poller")

    # Clear the scope-upgrade flag now that we have a fresh token with the
    # full scope set.
    global _spotify_scope_upgrade_pending
    _spotify_scope_upgrade_pending = False

    # Start the poller if it isn't already running.
    if _spotify_poller_task is None or _spotify_poller_task.done():
        _cfg = _gcfg()
        spotify_cfg = _cfg.get_section("spotify") or {}
        poll_interval = int(spotify_cfg.get("poll_interval", 10))
        _spotify_poller_task = asyncio.create_task(
            _spotify_state_loop(_spotify_client, poll_interval)
        )
        logger.info(f"Spotify poller launched (interval={poll_interval}s)")

    # Notify the HUD.
    await broadcast_notification(
        notification_id="spotify-auth-ok",
        severity="info",
        title="Spotify verbunden",
        detail="Die Spotify-Authentifizierung war erfolgreich.",
    )

    return web.Response(
        status=200,
        content_type="text/html",
        text=(
            "<html><body><h2>Spotify connected. You can close this window.</h2>"
            "<script>setTimeout(()=>window.close(),2000);</script></body></html>"
        ),
    )


# ---------------------------------------------------------------------------
# Spotify REST API handlers — :8766  (/api/spotify/*)
# ---------------------------------------------------------------------------

def _spotify_json_error(status: int, body: dict[str, Any], **headers: str) -> web.Response:
    """Return a JSON error response with the given status and optional extra headers."""
    resp = web.Response(
        status=status,
        content_type="application/json",
        text=json.dumps(body),
    )
    for k, v in headers.items():
        resp.headers[k] = v
    return resp


def _spotify_scope_upgrade_pending_set() -> None:
    """Mark that a scope upgrade is needed and log it.

    Called by scope-gated REST handlers only on the stale-token path — i.e.
    when ``_spotify_client is not None`` but ``is_authenticated()`` returns
    False.  This means a token exists but lacks the library/queue scopes added
    in issue #58.  When ``_spotify_client is None`` (no token ever issued) the
    caller must NOT call this; the HUD should show the plain first-time auth
    prompt, not the scope-upgrade banner.  The flag is read by
    ``_spotify_state_loop`` on the next tick.
    """
    global _spotify_scope_upgrade_pending
    _spotify_scope_upgrade_pending = True
    logger.info("Spotify scope upgrade required — flagging for next WS broadcast")


def _spotify_handle_exception(
    exc: Exception, scope_gated: bool = False
) -> web.Response:
    """Map a Spotify exception to the appropriate HTTP error response.

    When ``scope_gated`` is True and the exception is a ``SpotifyAuthError``,
    the module-level ``_spotify_scope_upgrade_pending`` flag is set so the
    next ``_spotify_state_loop`` tick broadcasts ``scope_upgrade_required=True``.

    Args:
        exc: Exception from a SpotifyClient call.
        scope_gated: True for endpoints that require library/queue scopes
            beyond the basic playback set.

    Returns:
        aiohttp Response with correct status, JSON body, and headers.
    """
    global _spotify_scope_upgrade_pending

    from integrations.spotify.client import (  # noqa: PLC0415
        SpotifyAuthError,
        SpotifyPollError,
        SpotifyPremiumError,
    )

    if isinstance(exc, SpotifyAuthError):
        if scope_gated:
            _spotify_scope_upgrade_pending = True
            logger.info("Spotify scope upgrade required — flagging for next WS broadcast")
        return _spotify_json_error(401, {"error": "unauthenticated"})
    if isinstance(exc, SpotifyPremiumError):
        return _spotify_json_error(402, {"error": "premium_required"})
    if isinstance(exc, SpotifyPollError):
        retry_after = getattr(exc, "retry_after", None)
        body: dict[str, Any] = {"error": "rate_limited"}
        extra: dict[str, str] = {}
        if retry_after is not None:
            body["retryAfter"] = int(retry_after)
            extra["Retry-After"] = str(int(retry_after))
        return _spotify_json_error(429, body, **extra)
    return _spotify_json_error(500, {"error": str(exc)})


async def spotify_playlists_handler(request: web.Request) -> web.Response:
    """Handle GET /api/spotify/playlists — return user's playlists."""
    if _spotify_client is None or not _spotify_client.is_authenticated():
        if _spotify_client is not None:
            _spotify_scope_upgrade_pending_set()
        return _spotify_json_error(401, {"error": "unauthenticated"})
    try:
        limit = int(request.rel_url.query.get("limit", 50))
        offset = int(request.rel_url.query.get("offset", 0))
        playlists = await _spotify_client.list_playlists(limit=limit, offset=offset)
        items = [
            {
                "id": pl.id,
                "name": pl.name,
                "owner": pl.owner,
                "trackCount": pl.track_count,
                "uri": pl.uri,
            }
            for pl in playlists
        ]
        return web.Response(
            content_type="application/json",
            text=json.dumps({"items": items, "total": len(items), "offset": offset}),
        )
    except Exception as exc:
        return _spotify_handle_exception(exc, scope_gated=True)


async def spotify_playlist_tracks_handler(request: web.Request) -> web.Response:
    """Handle GET /api/spotify/playlists/{id}/tracks — return playlist tracks."""
    if _spotify_client is None or not _spotify_client.is_authenticated():
        if _spotify_client is not None:
            _spotify_scope_upgrade_pending_set()
        return _spotify_json_error(401, {"error": "unauthenticated"})
    playlist_id = request.match_info.get("id", "")
    try:
        limit = int(request.rel_url.query.get("limit", 100))
        offset = int(request.rel_url.query.get("offset", 0))
        tracks = await _spotify_client.playlist_tracks(
            playlist_id, limit=limit, offset=offset
        )
        items = [
            {
                "id": t.id,
                "name": t.name,
                "artist": t.artist,
                "album": t.album,
                "durationMs": t.duration_ms,
                "uri": t.uri,
            }
            for t in tracks
        ]
        return web.Response(
            content_type="application/json",
            text=json.dumps({"items": items, "total": len(items), "offset": offset}),
        )
    except Exception as exc:
        return _spotify_handle_exception(exc, scope_gated=True)


async def spotify_album_tracks_handler(request: web.Request) -> web.Response:
    """Handle GET /api/spotify/albums/{id}/tracks — return album tracks."""
    if _spotify_client is None or not _spotify_client.is_authenticated():
        if _spotify_client is not None:
            _spotify_scope_upgrade_pending_set()
        return _spotify_json_error(401, {"error": "unauthenticated"})
    album_id = request.match_info.get("id", "")
    try:
        limit = int(request.rel_url.query.get("limit", 50))
        offset = int(request.rel_url.query.get("offset", 0))
        tracks = await _spotify_client.album_tracks(album_id, limit=limit, offset=offset)
        items = [
            {
                "id": t.id,
                "name": t.name,
                "artist": t.artist,
                "album": t.album,
                "durationMs": t.duration_ms,
                "uri": t.uri,
            }
            for t in tracks
        ]
        return web.Response(
            content_type="application/json",
            text=json.dumps({"items": items, "total": len(items), "offset": offset}),
        )
    except Exception as exc:
        return _spotify_handle_exception(exc, scope_gated=True)


async def spotify_saved_tracks_handler(request: web.Request) -> web.Response:
    """Handle GET /api/spotify/me/tracks — return user's saved tracks."""
    if _spotify_client is None or not _spotify_client.is_authenticated():
        if _spotify_client is not None:
            _spotify_scope_upgrade_pending_set()
        return _spotify_json_error(401, {"error": "unauthenticated"})
    try:
        limit = int(request.rel_url.query.get("limit", 50))
        offset = int(request.rel_url.query.get("offset", 0))
        tracks = await _spotify_client.saved_tracks(limit=limit, offset=offset)
        items = [
            {
                "id": t.id,
                "name": t.name,
                "artist": t.artist,
                "album": t.album,
                "durationMs": t.duration_ms,
                "uri": t.uri,
            }
            for t in tracks
        ]
        return web.Response(
            content_type="application/json",
            text=json.dumps({"items": items, "total": len(items), "offset": offset}),
        )
    except Exception as exc:
        return _spotify_handle_exception(exc, scope_gated=True)


async def spotify_saved_albums_handler(request: web.Request) -> web.Response:
    """Handle GET /api/spotify/me/albums — return user's saved albums."""
    if _spotify_client is None or not _spotify_client.is_authenticated():
        if _spotify_client is not None:
            _spotify_scope_upgrade_pending_set()
        return _spotify_json_error(401, {"error": "unauthenticated"})
    try:
        limit = int(request.rel_url.query.get("limit", 50))
        offset = int(request.rel_url.query.get("offset", 0))
        raw_albums = await _spotify_client.saved_albums(limit=limit, offset=offset)
        # Remap snake_case client fields to camelCase for the frontend.
        albums = [
            {
                "id": a.get("id", ""),
                "name": a.get("name", ""),
                "artist": a.get("artist", ""),
                "uri": a.get("uri", ""),
                "trackCount": a.get("total_tracks", 0),
            }
            for a in raw_albums
        ]
        return web.Response(
            content_type="application/json",
            text=json.dumps({"items": albums, "total": len(albums), "offset": offset}),
        )
    except Exception as exc:
        return _spotify_handle_exception(exc, scope_gated=True)


async def spotify_search_handler(request: web.Request) -> web.Response:
    """Handle GET /api/spotify/search?q=&types= — search the Spotify catalogue."""
    if _spotify_client is None or not _spotify_client.is_authenticated():
        if _spotify_client is not None:
            _spotify_scope_upgrade_pending_set()
        return _spotify_json_error(401, {"error": "unauthenticated"})
    query = request.rel_url.query.get("q", "").strip()
    if not query:
        return _spotify_json_error(400, {"error": "missing query parameter 'q'"})
    types_raw = request.rel_url.query.get("types", "")
    types: list[str] | None = (
        [t.strip() for t in types_raw.split(",") if t.strip()] if types_raw else None
    )
    limit = int(request.rel_url.query.get("limit", 10))
    try:
        results = await _spotify_client.search(query, types=types, limit=limit)
        body = {
            "tracks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "artist": t.artist,
                    "album": t.album,
                    "durationMs": t.duration_ms,
                    "uri": t.uri,
                }
                for t in results.tracks
            ],
            "artists": [
                {
                    "id": a.get("id", ""),
                    "name": a.get("name", ""),
                    "uri": a.get("uri", ""),
                    "genres": a.get("genres", []),
                }
                for a in results.artists
            ],
            "albums": [
                {
                    "id": a.get("id", ""),
                    "name": a.get("name", ""),
                    "artist": a.get("artist", ""),
                    "uri": a.get("uri", ""),
                    "trackCount": a.get("total_tracks", 0),
                }
                for a in results.albums
            ],
            "playlists": [
                {
                    "id": pl.id,
                    "name": pl.name,
                    "owner": pl.owner,
                    "trackCount": pl.track_count,
                    "uri": pl.uri,
                }
                for pl in results.playlists
            ],
        }
        return web.Response(content_type="application/json", text=json.dumps(body))
    except Exception as exc:
        return _spotify_handle_exception(exc, scope_gated=True)


async def spotify_queue_get_handler(request: web.Request) -> web.Response:
    """Handle GET /api/spotify/queue — return current playback queue."""
    if _spotify_client is None or not _spotify_client.is_authenticated():
        if _spotify_client is not None:
            _spotify_scope_upgrade_pending_set()
        return _spotify_json_error(401, {"error": "unauthenticated"})
    try:
        queue = await _spotify_client.get_queue()
        items = [
            {
                "position": q.position,
                "name": q.name,
                "artist": q.artist,
                "uri": q.uri,
            }
            for q in queue
        ]
        return web.Response(
            content_type="application/json",
            text=json.dumps({"items": items, "total": len(items), "offset": 0}),
        )
    except Exception as exc:
        return _spotify_handle_exception(exc, scope_gated=True)


async def spotify_queue_post_handler(request: web.Request) -> web.Response:
    """Handle POST /api/spotify/queue — add a URI to the playback queue."""
    if _spotify_client is None or not _spotify_client.is_authenticated():
        if _spotify_client is not None:
            _spotify_scope_upgrade_pending_set()
        return _spotify_json_error(401, {"error": "unauthenticated"})
    try:
        body = await request.json()
        uri: str = body.get("uri", "").strip()
        if not uri:
            return _spotify_json_error(400, {"error": "missing 'uri' in request body"})
        await _spotify_client.add_to_queue(uri)
        return web.Response(content_type="application/json", text="{}")
    except json.JSONDecodeError:
        return _spotify_json_error(400, {"error": "invalid JSON body"})
    except Exception as exc:
        return _spotify_handle_exception(exc, scope_gated=True)


async def spotify_token_handler(request: web.Request) -> web.Response:
    """Handle GET /api/spotify/token — return a valid access token for the Web Playback SDK.

    Returns JSON ``{"access_token": "<str>", "expires_in": <int>}`` on success.
    The token is refreshed automatically when it has fewer than 60 seconds left.
    """
    from integrations.spotify.client import SpotifyAuthError  # noqa: PLC0415

    if _spotify_client is None or not _spotify_client.is_authenticated():
        if _spotify_client is not None:
            _spotify_scope_upgrade_pending_set()
        return _spotify_json_error(401, {"error": "unauthenticated"})
    try:
        access_token, expires_in = await _spotify_client.get_access_token()
        return web.Response(
            content_type="application/json",
            text=json.dumps({"access_token": access_token, "expires_in": expires_in}),
        )
    except SpotifyAuthError as exc:
        logger.warning(f"spotify_token_handler: auth error — {exc}")
        return _spotify_json_error(401, {"error": "unauthenticated"})
    except Exception as exc:
        logger.error(f"spotify_token_handler: unexpected error — {exc}")
        return _spotify_json_error(500, {"error": str(exc)})


async def spotify_play_context_handler(request: web.Request) -> web.Response:
    """Handle POST /api/spotify/play/context — start playback of a context URI."""
    if _spotify_client is None or not _spotify_client.is_authenticated():
        return _spotify_json_error(401, {"error": "unauthenticated"})
    try:
        body = await request.json()
        context_uri: str = body.get("contextUri", "") or body.get("context_uri", "")
        context_uri = context_uri.strip()
        if not context_uri:
            return _spotify_json_error(
                400, {"error": "missing 'contextUri' in request body"}
            )
        offset_uri: str | None = (
            body.get("offsetUri") or body.get("offset_uri") or None
        )
        raw_device_id = body.get("device_id", _MISSING)
        if raw_device_id is _MISSING or raw_device_id == "":
            device_id: str | None = get_spotify_device_id()
            if device_id is not None:
                logger.info(
                    f"spotify_play_context: defaulting to JARVIS device {device_id}"
                )
            else:
                logger.warning(
                    "spotify_play_context: no JARVIS device cached, falling back to"
                    " Spotify Connect default"
                )
        elif raw_device_id is None:
            device_id = None  # explicit null → honour Spotify Connect active device
        else:
            device_id = raw_device_id
        await _spotify_client.play_context(
            context_uri, offset_uri=offset_uri, device_id=device_id
        )
        return web.Response(content_type="application/json", text="{}")
    except json.JSONDecodeError:
        return _spotify_json_error(400, {"error": "invalid JSON body"})
    except Exception as exc:
        return _spotify_handle_exception(exc)


async def spotify_play_uris_handler(request: web.Request) -> web.Response:
    """Handle POST /api/spotify/play/uris — start playback of a list of URIs."""
    if _spotify_client is None or not _spotify_client.is_authenticated():
        return _spotify_json_error(401, {"error": "unauthenticated"})
    try:
        body = await request.json()
        uris: list[str] = body.get("uris", [])
        if not uris:
            return _spotify_json_error(400, {"error": "missing or empty 'uris' list"})
        raw_device_id = body.get("device_id", _MISSING)
        if raw_device_id is _MISSING or raw_device_id == "":
            device_id: str | None = get_spotify_device_id()
            if device_id is not None:
                logger.info(
                    f"spotify_play_uris: defaulting to JARVIS device {device_id}"
                )
            else:
                logger.warning(
                    "spotify_play_uris: no JARVIS device cached, falling back to"
                    " Spotify Connect default"
                )
        elif raw_device_id is None:
            device_id = None  # explicit null → honour Spotify Connect active device
        else:
            device_id = raw_device_id
        await _spotify_client.play_uris(uris, device_id=device_id)
        return web.Response(content_type="application/json", text="{}")
    except json.JSONDecodeError:
        return _spotify_json_error(400, {"error": "invalid JSON body"})
    except Exception as exc:
        return _spotify_handle_exception(exc)


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


async def broadcast_turn_timing(timing: dict[str, Any]) -> None:
    """Broadcast per-turn latency timing to all connected clients.

    Emitted at the end of each successful voice pipeline turn so the
    frontend LogPanel can render a Gantt-style waterfall diagram.

    Args:
        timing: Dict with keys ``turn_id``, ``audio_end_ts``,
            ``stt_done_ts``, ``llm_first_token_ts``, ``llm_done_ts``,
            ``tts_first_audio_ts``, ``tts_done_ts`` (all epoch ms floats).
    """
    message = json.dumps({"type": "turn_timing", "payload": timing})
    await _broadcast(message)


async def broadcast_narration_state() -> None:
    """Broadcast the current narration queue state to all connected clients.

    Emitted on every queue mutation: enqueue, dequeue, quiet-mode toggle,
    status update.  The frontend ``activity`` feature subscribes to
    ``narration_state`` messages to keep the Activity panel in sync.
    """
    if _narration_queue is None:
        return
    payload = _narration_queue.get_state_snapshot()
    message = json.dumps({"type": "narration_state", "payload": payload})
    await _broadcast(message)


async def broadcast_activity_panel() -> None:
    """Broadcast the per-source status snapshot to all connected clients.

    Emitted alongside :func:`broadcast_narration_state` so the Activity panel
    can display per-source progress without polling.
    """
    if _narration_queue is None:
        return
    message = json.dumps({
        "type": "activity_panel",
        "payload": {
            "sources": _narration_queue.get_source_statuses(),
            "history": _narration_queue.get_history(),
        },
    })
    await _broadcast(message)


async def _on_narration_queue_mutation() -> None:
    """Internal callback wired into NarrationQueue — fires both WS broadcasts."""
    await broadcast_narration_state()
    await broadcast_activity_panel()


async def broadcast_conversation_state(state: ConversationState, since: float) -> None:
    """Broadcast a conversation-state transition to all connected clients.

    Fires on every state transition emitted by the orchestrator's
    ConversationStateMachine, so the frontend can drive audio ducking
    deterministically without polling.

    Args:
        state: New ConversationState value.
        since: Epoch seconds when the transition happened.
    """
    if _state_machine is None:
        return
    payload = {
        "state": state.value,
        "since": datetime.fromtimestamp(since, tz=timezone.utc).isoformat(),
    }
    message = json.dumps({"type": "conversation_state", "payload": payload})
    await _broadcast(message)


async def _on_conversation_state_transition(state: ConversationState, since: float) -> None:
    """Private callback wired into ConversationStateMachine — fires conversation_state broadcast."""
    await broadcast_conversation_state(state, since)


# ---------------------------------------------------------------------------
# HTTP handlers: POST /api/jarvis/notify|status|quiet
# ---------------------------------------------------------------------------


async def jarvis_notify_handler(request: web.Request) -> web.Response:
    """Handle POST /api/jarvis/notify — enqueue a narration item from an HTTP caller.

    Accepts the same payload as the ``jarvis_notify`` MCP tool:
    ``{"title": str, "body": str|null, "severity": str, "source": str|null,
    "ttl_seconds": int}``.

    Returns JSON ``{"item_id": str, "queued_at": str, "channels": [...]}``.
    """
    from datetime import datetime, timezone  # noqa: PLC0415

    if _narration_queue is None:
        return web.json_response({"error": "NarrationQueue not initialised"}, status=503)

    try:
        data: dict[str, Any] = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    title: str = data.get("title", "")
    if not title:
        return web.json_response({"error": "'title' is required"}, status=400)

    body: str | None = data.get("body")
    severity: str = data.get("severity", "update")
    if severity not in {"info", "update", "urgent", "completion"}:
        severity = "update"
    source: str | None = data.get("source")
    ttl_seconds: float = float(data.get("ttl_seconds", 0))

    text = f"{title}: {body}" if body else title
    item_id = _narration_queue.enqueue(
        text=text,
        severity=severity,  # type: ignore[arg-type]
        source=source,
        ttl_seconds=ttl_seconds,
    )
    channels = _narration_queue._resolve_channels(severity)  # type: ignore[arg-type]

    logger.info(
        f"HTTP /api/jarvis/notify: [{severity}] {item_id!r}"
        + (f" source={source!r}" if source else "")
    )
    return web.json_response(
        {
            "item_id": item_id,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "channels": channels,
        }
    )


async def jarvis_status_handler(request: web.Request) -> web.Response:
    """Handle POST /api/jarvis/status — coalesce per-source progress status.

    Accepts ``{"source": str, "status": str, "message": str|null}``.
    Returns JSON ``{"source": str, "prior_status": str|null}``.
    """
    if _narration_queue is None:
        return web.json_response({"error": "NarrationQueue not initialised"}, status=503)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    source: str = data.get("source", "")
    if not source:
        return web.json_response({"error": "'source' is required"}, status=400)

    status: str = data.get("status", "in_progress")
    if status not in {"starting", "in_progress", "done", "blocked"}:
        status = "in_progress"
    message: str | None = data.get("message")

    prior = _narration_queue.set_source_status(
        source=source,
        status=status,  # type: ignore[arg-type]
        message=message,
    )
    prior_status: str | None = prior.status if prior is not None else None

    logger.info(f"HTTP /api/jarvis/status: source={source!r} → {status!r}")
    return web.json_response({"source": source, "prior_status": prior_status})


async def jarvis_quiet_handler(request: web.Request) -> web.Response:
    """Handle POST /api/jarvis/quiet — toggle quiet mode.

    Accepts ``{"enabled": bool, "duration_minutes": int|null}``.
    Returns JSON ``{"quiet_until": str|null}``.
    """
    if _narration_queue is None:
        return web.json_response({"error": "NarrationQueue not initialised"}, status=503)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    enabled: bool = bool(data.get("enabled", False))
    duration_minutes_raw = data.get("duration_minutes")
    duration_minutes: int | None = (
        int(duration_minutes_raw) if duration_minutes_raw is not None else None
    )

    quiet_until = _narration_queue.set_quiet_mode(
        enabled=enabled,
        duration_minutes=duration_minutes,
    )
    quiet_until_iso: str | None = (
        quiet_until.isoformat() if quiet_until is not None else None
    )

    logger.info(
        f"HTTP /api/jarvis/quiet: enabled={enabled} quiet_until={quiet_until_iso}"
    )
    return web.json_response({"quiet_until": quiet_until_iso})


async def _broadcast(message: str) -> None:
    """Broadcast a message to all connected clients.

    Args:
        message: JSON string to broadcast
    """
    if not _connected_clients:
        return

    clients = list(_connected_clients)
    disconnected = set()
    for ws in clients:
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
# Online greeting — fire once per boot on first client connect
# ---------------------------------------------------------------------------

# Set to True as soon as the greeting task is scheduled so concurrent
# connects (e.g. HMR reconnects) cannot trigger a second greeting.
_greeting_played: bool = False

# Cached counts updated by the respective broadcast helpers so the greeting
# provider lambdas can read them synchronously without a live API call.
_last_unread_count: int | None = None
_last_calendar_count: int | None = None

# ---------------------------------------------------------------------------
# Gmail mail poller
# ---------------------------------------------------------------------------

# Task handle for the mail polling background coroutine.
_mail_poller_task: asyncio.Task[None] | None = None


def _email_message_to_dict(msg: Any) -> dict[str, Any]:
    """Serialise an ``EmailMessage`` dataclass to a camelCase frontend dict.

    Key names match the ``MailMessage`` TypeScript type in ``frontend/src/types.ts``:
    ``preview`` (not ``snippet``) and ``unread`` (not ``isUnread``).
    """
    return {
        "id": msg.id,
        "threadId": msg.thread_id,
        "subject": msg.subject,
        "sender": msg.sender,
        "senderEmail": msg.sender_email,
        "recipient": msg.recipient,
        "receivedAt": msg.received_at.isoformat(),
        "preview": msg.snippet,
        "unread": msg.is_unread,
        "isVip": msg.is_vip,
    }


async def _start_mail_poller(poll_interval: int, vip_senders: list[str]) -> None:
    """Background coroutine that polls Gmail and broadcasts ``mail_state``.

    Runs indefinitely until cancelled.  Backs off to ``3 * poll_interval``
    after three consecutive failures, then resets on the next success.

    Args:
        poll_interval: Normal interval between polls in seconds.
        vip_senders: VIP sender list forwarded to the Gmail client.
    """
    from integrations.google.gmail_client import GmailClientError  # noqa: PLC0415

    logger.info(f"Mail poller started (interval={poll_interval}s)")
    consecutive_failures = 0
    backoff_interval = poll_interval * 3

    while True:
        try:
            # Wait for at least one client to be connected before polling.
            await asyncio.wait_for(_first_client_event.wait(), timeout=300)
        except asyncio.TimeoutError:
            logger.debug("Mail poller: no client connected yet, waiting...")
            continue

        sleep_secs = backoff_interval if consecutive_failures >= 3 else poll_interval
        await asyncio.sleep(sleep_secs)

        try:
            # Auth is managed by gog's own token store (gog auth add).
            # No JARVIS-side OAuth gate needed after migration to gog (ADR-0001).
            client = get_gmail_client(vip_senders=vip_senders)
            messages = await client.list_unread(max_results=5)
            unread_count = await client.get_unread_count()

            serialised = [_email_message_to_dict(m) for m in messages]
            await broadcast_mail_state(serialised, unread_count)
            logger.debug(f"Mail state broadcast: {unread_count} unread, {len(messages)} msgs")
            consecutive_failures = 0

        except GmailClientError as exc:
            consecutive_failures += 1
            logger.warning(
                f"Mail poller: Gmail error (failure #{consecutive_failures}): {exc}"
            )
        except asyncio.CancelledError:
            logger.info("Mail poller cancelled")
            return
        except Exception as exc:
            consecutive_failures += 1
            logger.error(f"Mail poller: unexpected error (failure #{consecutive_failures}): {exc}")


# Per-connection email confirmation state key.
# Stored under ``_connection_state[conn_id]["pending_email_send"]`` as a dict:
# {"draft_id": str, "to": str, "subject": str, "confirm_event": asyncio.Event}
# or None when no confirmation is pending.


_CONFIRM_RE = __import__("re").compile(
    r"\b(ja|senden|bestätige|confirm|yes|send\s+it|go\s+ahead)\b",
    __import__("re").IGNORECASE,
)
_CANCEL_RE = __import__("re").compile(
    r"\b(nein|abbrechen|stop|cancel|nicht\s+senden|abort)\b",
    __import__("re").IGNORECASE,
)


async def _handle_email_confirm(
    ws: web.WebSocketResponse,
    text: str,
) -> bool:
    """Check whether ``text`` is a pending email confirmation or cancellation.

    Called from ``_run_voice_pipeline_body`` immediately after STT, before
    any other processing. If ``pending_email_send`` is set on the connection,
    the turn is inspected against the confirm / cancel word lists:

    - Confirm match → ``send_draft()`` fires, ``pending_email_send`` cleared,
      ``email_send_done`` broadcast, returns ``True`` (turn consumed).
    - Cancel match → ``delete_draft()`` fires, state cleared, returns ``True``.
    - Timeout (``created_at`` older than config ``send_confirm_timeout_seconds``)
      → state cleared, notification broadcast, returns ``False`` so the utterance
      is processed as a fresh turn.
    - Ambiguous → state kept, returns ``False`` (pipeline re-reads draft summary).

    Args:
        ws: The WebSocket connection.
        text: STT transcript of the current turn.

    Returns:
        ``True`` when the turn was consumed by the confirmation machine,
        ``False`` otherwise.
    """
    conn_id = id(ws)
    state = _connection_state.get(conn_id)
    if state is None:
        return False

    pending: dict[str, Any] | None = state.get("pending_email_send")
    if pending is None:
        return False

    # --- Timeout check -------------------------------------------------------
    from utils.config_loader import get_config as _get_cfg  # noqa: PLC0415

    _gmail_cfg = _get_cfg().get_section("gmail") or {}
    timeout_secs: float = float(_gmail_cfg.get("send_confirm_timeout_seconds", 60))
    created_at: float = pending.get("created_at", 0.0)
    if time.time() - created_at > timeout_secs:
        draft_id_exp: str = pending.get("draft_id", "")
        logger.info(
            f"Email confirm window expired for draft_id={draft_id_exp} "
            f"(>{timeout_secs:.0f}s) — clearing pending state"
        )
        state["pending_email_send"] = None
        try:
            await get_gmail_client().delete_draft(draft_id_exp)
        except Exception as _del_exc:
            logger.warning("Draft cleanup on timeout failed: %s", _del_exc)
        await broadcast_email_send_done({"draft_id": draft_id_exp, "success": False})
        await broadcast_notification(
            notification_id=f"email-timeout-{draft_id_exp}",
            severity="info",
            title="E-Mail-Entwurf abgelaufen",
            detail="Das Bestätigungsfenster ist abgelaufen. Die Anfrage wurde nicht gesendet.",
        )
        return False  # let the utterance be processed as a normal turn

    text_lower = text.lower().strip()
    draft_id: str = pending["draft_id"]
    to: str = pending.get("to", "")

    if _CONFIRM_RE.search(text_lower):
        logger.info(f"Email confirmation received for draft_id={draft_id}")
        state["pending_email_send"] = None

        try:
            client = get_gmail_client()
            message_id = await client.send_draft(draft_id)
            await broadcast_email_send_done(
                {"draft_id": draft_id, "success": True, "message_id": message_id}
            )
            await broadcast_notification(
                notification_id=f"email-sent-{draft_id}",
                severity="info",
                title=f"E-Mail an {to} gesendet",
                detail="Die Nachricht wurde erfolgreich übermittelt.",
            )
            logger.info(f"Email sent successfully: message_id={message_id}")

        except Exception as exc:
            err_msg = str(exc)
            logger.error(f"Email send failed after confirmation: {err_msg}")
            await broadcast_email_send_done(
                {"draft_id": draft_id, "success": False, "error": err_msg}
            )
            # Attempt to clean up the draft on failure — non-fatal.
            try:
                await get_gmail_client().delete_draft(draft_id)
            except Exception as _del_exc:
                logger.warning("Draft cleanup failed after send error: %s", _del_exc)

        return True

    if _CANCEL_RE.search(text_lower):
        logger.info(f"Email send cancelled for draft_id={draft_id}")
        state["pending_email_send"] = None

        try:
            await get_gmail_client().delete_draft(draft_id)
        except Exception as exc:
            logger.warning(f"Could not delete draft {draft_id} on cancel: {exc}")

        await broadcast_email_send_done({"draft_id": draft_id, "success": False})
        return True

    # Ambiguous turn — leave pending state intact and return False so the
    # turn is forwarded to the voice pipeline (which will re-read the summary).
    logger.debug(
        f"Email confirm: ambiguous turn for draft_id={draft_id} — keeping window open"
    )
    return False


# ---------------------------------------------------------------------------
# Calendar confirmation state
# ---------------------------------------------------------------------------

# Per-connection calendar op state key.
# Stored under ``_connection_state[conn_id]["pending_calendar_op"]`` as a dict:
# {"op": "create"|"update"|"delete", "title": str, "start": str, "end": str,
#  "event_id": str | None, "created_at": float}
# or None when no confirmation is pending.

_CALENDAR_CONFIRM_RE = __import__("re").compile(
    r"\b(ja|ja bitte|bestätige|confirm|yes|go\s+ahead|do\s+it|ok)\b",
    __import__("re").IGNORECASE,
)
_CALENDAR_CANCEL_RE = __import__("re").compile(
    r"\b(nein|abbrechen|stopp?|cancel|nicht|abort|vergiss\s+es|nevermind)\b",
    __import__("re").IGNORECASE,
)


async def _handle_calendar_confirm(
    ws: web.WebSocketResponse,
    text: str,
) -> bool:
    """Check whether ``text`` is a pending calendar operation confirmation.

    Called from ``_run_voice_pipeline_body`` immediately after STT, after
    the email confirmation gate. If ``pending_calendar_op`` is set on the
    connection, the turn is inspected against confirm / cancel word lists:

    - Confirm match → fires the actual calendar API call, clears pending state,
      broadcasts ``calendar_op_done{success:true}``, returns ``True``.
    - Cancel match → discards op, broadcasts ``calendar_op_done{success:false}``,
      returns ``True``.
    - Timeout (older than ``op_confirm_timeout_seconds``) → clears state,
      broadcasts ``calendar_op_done{success:false}``, returns ``False`` so
      the utterance is processed as a normal turn.
    - Ambiguous → state kept, returns ``False``.

    Args:
        ws: The WebSocket connection.
        text: STT transcript of the current turn.

    Returns:
        ``True`` when the turn was consumed by the calendar confirmation machine,
        ``False`` otherwise.
    """
    conn_id = id(ws)
    state = _connection_state.get(conn_id)
    if state is None:
        return False

    pending: dict[str, Any] | None = state.get("pending_calendar_op")
    if pending is None:
        return False

    # --- Timeout check -------------------------------------------------------
    from utils.config_loader import get_config as _get_cfg  # noqa: PLC0415

    _cal_cfg = _get_cfg().get_section("calendar") or {}
    timeout_secs: float = float(_cal_cfg.get("op_confirm_timeout_seconds", 60))
    created_at: float = pending.get("created_at", 0.0)
    op: str = pending.get("op", "create")

    if time.time() - created_at > timeout_secs:
        logger.info(
            f"Calendar confirm window expired for op={op!r} "
            f"(>{timeout_secs:.0f}s) — clearing pending state"
        )
        state["pending_calendar_op"] = None
        await broadcast_calendar_op_done({"op": op, "success": False, "error": "timeout"})
        await broadcast_notification(
            notification_id=f"calendar-timeout-{op}",
            severity="info",
            title="Kalender-Aktion abgelaufen",
            detail="Das Bestätigungsfenster ist abgelaufen. Die Aktion wurde nicht ausgeführt.",
        )
        return False  # let the utterance be processed normally

    text_lower = text.lower().strip()
    event_id: str | None = pending.get("event_id")
    title: str = pending.get("title", "")
    start_iso: str = pending.get("start", "")
    end_iso: str = pending.get("end", "")

    if _CALENDAR_CONFIRM_RE.search(text_lower):
        logger.info(f"Calendar {op} confirmation received: title={title!r}")
        state["pending_calendar_op"] = None

        from integrations.google.calendar_client import CalendarClientError  # noqa: PLC0415

        try:
            client = get_calendar_client()

            if op == "create":
                from datetime import datetime  # noqa: PLC0415

                start_dt = datetime.fromisoformat(start_iso)
                end_dt = datetime.fromisoformat(end_iso)
                created_evt = await client.create_event(
                    title=title, start=start_dt, end=end_dt
                )
                await broadcast_calendar_op_done(
                    {"op": "create", "success": True, "event_id": created_evt.id}
                )
                await _force_calendar_state_refresh()
                logger.info(f"Calendar event created: id={created_evt.id!r}")

            elif op == "update" and event_id:
                from datetime import datetime  # noqa: PLC0415

                start_dt = datetime.fromisoformat(start_iso) if start_iso else None
                end_dt = datetime.fromisoformat(end_iso) if end_iso else None
                updated_evt = await client.update_event(
                    event_id=event_id,
                    title=title if title else None,
                    start=start_dt,
                    end=end_dt,
                )
                await broadcast_calendar_op_done(
                    {"op": "update", "success": True, "event_id": updated_evt.id}
                )
                await _force_calendar_state_refresh()

            elif op == "delete" and event_id:
                await client.delete_event(event_id=event_id)
                await broadcast_calendar_op_done(
                    {"op": "delete", "success": True, "event_id": event_id}
                )
                await _force_calendar_state_refresh()

            else:
                raise ValueError(f"Unsupported calendar op or missing event_id: {op}")

        except CalendarClientError as exc:
            err_msg = str(exc)
            logger.error(f"Calendar {op} failed after confirmation: {err_msg}")
            await broadcast_calendar_op_done({"op": op, "success": False, "error": err_msg})
        except Exception as exc:
            err_msg = str(exc)
            logger.error(f"Calendar {op} unexpected error: {err_msg}")
            await broadcast_calendar_op_done({"op": op, "success": False, "error": err_msg})

        return True

    if _CALENDAR_CANCEL_RE.search(text_lower):
        logger.info(f"Calendar {op} cancelled for title={title!r}")
        state["pending_calendar_op"] = None
        await broadcast_calendar_op_done({"op": op, "success": False})
        return True

    # Ambiguous — leave pending state intact.
    logger.debug(
        f"Calendar confirm: ambiguous turn for op={op!r} — keeping window open"
    )
    return False


async def _force_calendar_state_refresh() -> None:
    """Fetch and broadcast a fresh calendar state immediately after a write.

    Called after confirmed create/update/delete so the AgendaPanel reflects
    the change before the next scheduled poll tick.
    """
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    from utils.config_loader import get_config as _get_cfg  # noqa: PLC0415

    try:
        _cal_cfg = _get_cfg().get_section("calendar") or {}
        lookahead_hours = int(_cal_cfg.get("lookahead_hours", 48))
        max_results = int(_cal_cfg.get("max_events_per_query", 20))
        now = datetime.now(timezone.utc)
        events = await get_calendar_client().list_events(
            start=now,
            end=now + timedelta(hours=lookahead_hours),
            max_results=max_results,
        )
        serialised = [_calendar_event_to_dict(evt) for evt in events]
        await broadcast_calendar_state(serialised, "Aktuell")
    except Exception as exc:
        logger.warning(f"Calendar state refresh after write failed: {exc}")


def _calendar_event_to_dict(evt: Any) -> dict[str, Any]:
    """Serialise a ``CalendarEvent`` to a camelCase frontend dict."""
    return {
        "id": evt.id,
        "title": evt.title,
        "start": evt.start.isoformat(),
        "end": evt.end.isoformat(),
        "allDay": evt.all_day,
        "location": evt.location,
        "calendar": evt.calendar_id,
    }


async def _start_calendar_poller(poll_interval: int) -> None:
    """Background coroutine that polls Google Calendar and broadcasts ``calendar_state``.

    Also publishes ``calendar_event_approaching`` events to the ``EventBus``
    when an event is within the configured reminder thresholds (10, 5, 1 min).
    Backs off to ``3 * poll_interval`` after three consecutive failures.

    Args:
        poll_interval: Normal interval between polls in seconds.
    """
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    from integrations.google.calendar_client import CalendarClientError  # noqa: PLC0415
    from utils.config_loader import get_config as _get_cfg  # noqa: PLC0415
    from utils.events import Event, EventBus  # noqa: PLC0415  # type annotations

    logger.info(f"Calendar poller started (interval={poll_interval}s)")
    consecutive_failures = 0
    backoff_interval = poll_interval * 3

    # Track which (event_id, threshold_minutes) pairs we've already fired
    # within this poller run so we don't spam reminders on every poll tick.
    _fired_reminders: set[tuple[str, int]] = set()

    event_bus: EventBus | None = None
    try:
        import main as _main_module  # noqa: PLC0415

        event_bus = getattr(_main_module, "event_bus", None)
    except Exception as _eb_exc:
        logger.warning(f"EventBus unavailable for calendar poller: {_eb_exc}")

    while True:
        try:
            # Wait for at least one client to be connected before polling.
            await asyncio.wait_for(_first_client_event.wait(), timeout=300)
        except asyncio.TimeoutError:
            logger.debug("Calendar poller: no client connected yet, waiting...")
            continue

        sleep_secs = backoff_interval if consecutive_failures >= 3 else poll_interval
        try:
            await asyncio.sleep(sleep_secs)
        except asyncio.CancelledError:
            logger.info("Calendar poller cancelled during sleep")
            return

        _cal_cfg = _get_cfg().get_section("calendar") or {}
        lookahead_hours = int(_cal_cfg.get("lookahead_hours", 48))
        max_results = int(_cal_cfg.get("max_events_per_query", 20))
        reminder_thresholds: list[int] = _cal_cfg.get("reminder_thresholds_minutes", [10, 5, 1])

        try:
            # Auth is managed by gog's own token store (gog auth add).
            # No JARVIS-side OAuth gate needed after migration to gog (ADR-0001).
            now = datetime.now(timezone.utc)
            client = get_calendar_client()
            events = await client.list_events(
                start=now,
                end=now + timedelta(hours=lookahead_hours),
                max_results=max_results,
            )

            # Build date label based on current time.
            hour = now.hour
            if hour < 12:
                date_label = "Heute Morgen"
            elif hour < 17:
                date_label = "Heute"
            else:
                date_label = "Heute Abend"

            serialised = [_calendar_event_to_dict(evt) for evt in events]
            await broadcast_calendar_state(serialised, date_label)
            logger.debug(
                f"Calendar state broadcast: {len(events)} events "
                f"(label={date_label!r})"
            )
            consecutive_failures = 0

            # Check approaching events and fire EventBus reminders.
            if event_bus is not None:
                for evt in events:
                    if evt.all_day:
                        continue
                    minutes_until = (evt.start - now).total_seconds() / 60.0
                    for threshold in reminder_thresholds:
                        # Fire when within [threshold - poll_interval/60, threshold] minutes.
                        tolerance = (poll_interval / 60.0) + 0.5
                        if abs(minutes_until - threshold) <= tolerance:
                            reminder_key = (evt.id, threshold)
                            if reminder_key not in _fired_reminders:
                                _fired_reminders.add(reminder_key)
                                logger.info(
                                    f"Calendar reminder: {evt.title!r} "
                                    f"in ~{threshold}min (actual={minutes_until:.1f})"
                                )
                                await event_bus.publish(
                                    Event(
                                        type="calendar_event_approaching",
                                        payload={
                                            "title": evt.title,
                                            "starts_in_minutes": threshold,
                                            "event_id": evt.id,
                                        },
                                    )
                                )

            # Prune stale fired-reminder keys (events that have passed).
            stale_ids = {eid for eid, _ in _fired_reminders} - {evt.id for evt in events}
            _fired_reminders = {
                key for key in _fired_reminders if key[0] not in stale_ids
            }

        except CalendarClientError as exc:
            consecutive_failures += 1
            logger.warning(
                f"Calendar poller: API error (failure #{consecutive_failures}): {exc}"
            )
        except asyncio.CancelledError:
            logger.info("Calendar poller cancelled")
            return
        except Exception as exc:
            consecutive_failures += 1
            logger.error(
                f"Calendar poller: unexpected error (failure #{consecutive_failures}): {exc}"
            )


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
    stat_key: str | None = None,
    channel: str | None = None,
) -> None:
    """Pick a random pre-cached MP3 from ``cache`` and broadcast it.

    Args:
        cache: Mapping of language → list of (display_text, mp3_bytes).
        language: Preferred language code.
        log_label: Label used in INFO log messages.
        stat_key: Prefix for ``_phrase_cache_stats`` counters
            (e.g. ``"filler"`` increments ``filler_hits`` / ``filler_misses``).
            When ``None`` no stats are updated.
        channel: Optional channel tag forwarded to :func:`broadcast_audio`.
            Pass ``"filler"`` for filler/quick-ack clips so the frontend can
            avoid forcing the orb into ``speaking`` state for non-speech audio.
    """
    import random

    if not cache:
        if stat_key:
            _phrase_cache_stats[f"{stat_key}_misses"] = (
                _phrase_cache_stats.get(f"{stat_key}_misses", 0) + 1
            )
        return

    pool = cache.get(language)
    if not pool:
        pool = cache.get("de") or next(iter(cache.values()), [])
    if not pool:
        if stat_key:
            _phrase_cache_stats[f"{stat_key}_misses"] = (
                _phrase_cache_stats.get(f"{stat_key}_misses", 0) + 1
            )
        return

    text, mp3_bytes = random.choice(pool)
    audio_b64 = base64.b64encode(mp3_bytes).decode("utf-8")
    logger.info(
        f"{log_label} broadcast: {text!r} ({len(mp3_bytes)} bytes, lang={language})"
    )
    if stat_key:
        _phrase_cache_stats[f"{stat_key}_hits"] = (
            _phrase_cache_stats.get(f"{stat_key}_hits", 0) + 1
        )
    await broadcast_audio(audio_b64, text, channel=channel)


async def _broadcast_quick_ack_filler(language: str) -> None:
    """Broadcast a random pre-cached filler MP3 — plays while LLM is running."""
    await _broadcast_from_cache(
        _filler_cache, language, "Filler", stat_key="filler", channel="filler"
    )


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
        _phrase_cache_stats["backchannel_misses"] = (
            _phrase_cache_stats.get("backchannel_misses", 0) + 1
        )
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
        _phrase_cache_stats["backchannel_misses"] = (
            _phrase_cache_stats.get("backchannel_misses", 0) + 1
        )
        return

    _text, mp3_bytes = random.choice(pool)
    audio_b64 = base64.b64encode(mp3_bytes).decode("utf-8")
    state["last_backchannel_at"] = now
    _phrase_cache_stats["backchannel_hits"] = (
        _phrase_cache_stats.get("backchannel_hits", 0) + 1
    )
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
    # Broadcast "follow_up" so the frontend orb can render conversation-mode
    # distinctly from a fresh "listening" state.  The barge-in path keeps its
    # own broadcast_state("listening") call — that one is intentionally unchanged.
    await broadcast_state("follow_up")

    timer = asyncio.create_task(_follow_up_expiry_task(conn_id, window))
    state["follow_up_timer_task"] = timer


async def _attempt_email_compose_draft(
    ws: web.WebSocketResponse,
    intent_result: Any,
    spoken_preview: str,
) -> None:
    """Create a Gmail draft from EMAIL_COMPOSE intent params and arm confirmation.

    Called after the OpenClaw streaming pipeline finishes for an EMAIL_COMPOSE
    turn. Extracts ``to``, ``subject``, and ``body`` from ``intent_result.params``,
    calls ``GmailClient.create_draft``, populates ``pending_email_send`` on the
    connection state, and broadcasts ``email_draft_preview``. If params are
    incomplete the user is notified via a spoken fallback instead.

    Args:
        ws: Active WebSocket connection — used to look up connection state.
        intent_result: Classified intent with ``to`` / ``subject`` / ``body``
            params extracted by the intent parser.
        spoken_preview: Full response text spoken by OpenClaw (used as the
            body preview when no explicit body param is present).
    """
    from integrations.google.gmail_client import GmailClientError  # noqa: PLC0415
    from utils.config_loader import get_config as _gcfg  # noqa: PLC0415

    conn_id = id(ws)
    conn_state = _connection_state.get(conn_id)
    if conn_state is None:
        return

    params = getattr(intent_result, "params", {}) or {}
    to: str = params.get("to", "").strip()
    subject: str = params.get("subject", "Kein Betreff").strip() or "Kein Betreff"
    # Use the subject hint as body when no explicit body is available.
    body: str = params.get("body", spoken_preview[:500]).strip() or spoken_preview[:500]

    if not to:
        logger.info(
            "EMAIL_COMPOSE: no recipient extracted from intent params — "
            "skipping draft creation (user needs to be more specific)"
        )
        return

    _gmail_cfg = _gcfg().get_section("gmail") or {}
    if not _gmail_cfg.get("enabled", False):
        return

    try:
        client = get_gmail_client(vip_senders=_gmail_cfg.get("vip_senders", []))
        draft = await client.create_draft(to=to, subject=subject, body=body)

        body_preview = body[:200]
        conn_state["pending_email_send"] = {
            "draft_id": draft.id,
            "to": to,
            "subject": subject,
            "body_preview": body_preview,
            "created_at": time.time(),
        }
        logger.info(
            f"EMAIL_COMPOSE draft created: draft_id={draft.id} to={to!r} "
            f"subject={subject!r}"
        )

        await broadcast_email_draft_preview(
            {
                "draft_id": draft.id,
                "to": to,
                "subject": subject,
                "body_preview": body_preview,
                "created_at": draft.created_at.isoformat(),
            }
        )

    except GmailClientError as exc:
        logger.error(f"EMAIL_COMPOSE draft creation failed: {exc}")
        # Non-fatal — the user turn was still processed, they just won't get
        # a confirmation prompt.


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

    # --- Per-turn timing instrumentation ---
    import uuid as _uuid  # noqa: PLC0415

    _turn_id = _uuid.uuid4().hex[:12]
    _t_audio_end = time.time() * 1000  # epoch ms

    # --- Transcribe ---
    await broadcast_state("thinking")

    if _stt_engine is None:
        logger.error("STT engine not initialised")
        await broadcast_state("idle")
        return

    result = await _stt_engine.transcribe(audio_data)
    _t_stt_done = time.time() * 1000  # epoch ms

    if not result.text.strip():
        logger.debug("Empty transcription, returning to idle")
        await broadcast_state("idle")
        return

    logger.info(f"User said ({result.language}): {result.text}")

    # Notify the conversation state machine that an utterance was finalised.
    if _state_machine is not None:
        _state_machine.on_user_utterance_finalized()

    # Item 1: store per-connection detected language so backchannel
    # playback during the *next* turn uses the right language pool.
    _conn_state_ref = _connection_state.get(id(ws))
    if _conn_state_ref is not None:
        _conn_state_ref["detected_language"] = result.language or "de"

    # Broadcast + archive the user turn immediately — we want the
    # archive to reflect reality even if the downstream LLM call fails.
    await broadcast_transcript("user", result.text)

    # --- Email confirmation gate ------------------------------------------
    # If there is a pending draft waiting for explicit verbal confirmation,
    # intercept this turn BEFORE sleep-phrase detection or the orchestrator.
    # Returns True when the turn was fully handled (sent or cancelled).
    if await _handle_email_confirm(ws, result.text):
        logger.info("Voice pipeline: turn consumed by email confirmation gate")
        await broadcast_state("idle")
        return

    # --- Calendar confirmation gate ---------------------------------------
    # If there is a pending calendar op (create/update/delete) waiting for
    # explicit verbal confirmation, intercept this turn before the orchestrator.
    # Returns True when the turn was fully handled (confirmed or cancelled).
    if await _handle_calendar_confirm(ws, result.text):
        logger.info("Voice pipeline: turn consumed by calendar confirmation gate")
        await broadcast_state("idle")
        return

    # --- Sleep-phrase short-circuit ---------------------------------------
    # If the user's utterance signals "we're done" ("danke", "thanks", ...),
    # skip the LLM round-trip entirely, speak a short closing line, and
    # return to idle WITHOUT arming a new follow-up window.
    if _conversation_mode is not None and _conversation_mode.detect_sleep_phrase(
        result.text, result.language
    ):
        _phrase_cache_stats["sleep_match_hits"] = (
            _phrase_cache_stats.get("sleep_match_hits", 0) + 1
        )
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
            await _broadcast_from_cache(
                _ack_cache, result.language, "QuickAck", stat_key="ack", channel="filler"
            )
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
    _t_llm_first_token_ms: float | None = None
    _t_tts_first_audio_ms: float | None = None
    # Threshold above which we assume a tool call is running during the silence
    # before the first text delta arrives (TTFT > this value → broadcast working).
    _TOOL_HINT_TTFT_S: float = 2.0
    _tool_hint_sent: bool = False

    # The StreamSplitter converts a stream of incremental tokens into
    # complete sentences suitable for TTS synthesis.
    splitter = StreamSplitter(min_chars=40, max_wait_ms=600)

    # --- Disfluency + prosody setup (Items 3 & 4) -------------------------
    from utils.config_loader import get_config as _get_cfg_vp  # noqa: PLC0415

    _vp_cfg = _get_cfg_vp().get_section("voice") or {}
    _disfluency_enabled: bool = bool(_vp_cfg.get("disfluencies_enabled", False))
    _disfluency_prob: float = float(_vp_cfg.get("disfluency_probability", 0.20))
    _prosody_enabled: bool = bool(_vp_cfg.get("prosody_enabled", True))

    from audio.disfluency import maybe_prepend_disfluency as _prepend_disfluency  # noqa: PLC0415
    from audio.prosody import get_prosody_hint as _get_prosody  # noqa: PLC0415

    _prosody_hint = _get_prosody(enabled=_prosody_enabled)
    _first_sentence_sent: bool = False  # track whether we've already prepended disfluency

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
                    nonlocal _t_llm_first_token_ms
                    if _t_llm_first_token_ms is None:
                        _t_llm_first_token_ms = time.time() * 1000
                    yield chunk.new_text
        except asyncio.CancelledError:
            raise

    try:
        async for sentence in splitter.process(_token_stream()):
            tts_text = strip_markdown_for_tts(sentence)
            if not tts_text.strip():
                continue

            # Item 3: prepend disfluency to the very first sentence only.
            if not _first_sentence_sent and _disfluency_enabled:
                tts_text = _prepend_disfluency(
                    tts_text,
                    result.language or "de",
                    enabled=True,
                    probability=_disfluency_prob,
                )
            _first_sentence_sent = True

            try:
                # Item 4: pass prosody_hint so Fish Audio adjusts speed.
                audio_bytes = await _fish_tts.synthesize(tts_text, prosody_hint=_prosody_hint)
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

                if not first_audio_sent:
                    first_audio_sent = True
                    _t_tts_first_audio_ms = time.time() * 1000
                    elapsed_ms = (time.monotonic() - t_stream_start) * 1000
                    logger.info(
                        f"First audio chunk sent {elapsed_ms:.0f}ms after stream start"
                    )
                    # Transition to "speaking" on first TTS chunk so barge-in
                    # detection in _process_audio_for_client activates.
                    if _state_machine is not None:
                        _state_machine.on_tts_start()
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
        if _state_machine is not None:
            _state_machine.on_tts_end()

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

    # --- EMAIL_COMPOSE: create draft + arm confirmation window -----------
    # When the intent is EMAIL_COMPOSE and no draft is already pending,
    # create a Gmail draft from the extracted params (to/subject from
    # intent_result) and set pending_email_send so the next turn is
    # intercepted by _handle_email_confirm before reaching the orchestrator.
    if (
        intent_result is not None
        and intent_result.intent == Intent.EMAIL_COMPOSE
        and conn_state is not None
        and conn_state.get("pending_email_send") is None
    ):
        await _attempt_email_compose_draft(ws, intent_result, full_response_text)

    # --- Emit turn-timing telemetry ---
    _t_llm_done = time.time() * 1000
    _t_tts_done = _t_llm_done  # tts stream finishes just before we reach here
    try:
        await broadcast_turn_timing(
            {
                "turn_id": _turn_id,
                "audio_end_ts": _t_audio_end,
                "stt_done_ts": _t_stt_done,
                "llm_first_token_ts": _t_llm_first_token_ms,
                "llm_done_ts": _t_llm_done,
                "tts_first_audio_ts": _t_tts_first_audio_ms,
                "tts_done_ts": _t_tts_done,
            }
        )
    except Exception as _tt_exc:  # noqa: BLE001
        logger.debug(f"turn_timing broadcast failed: {_tt_exc}")

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
            if _state_machine is not None:
                _state_machine.on_wake_word()
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
                # Use the STT-detected language stored after the previous
                # pipeline turn.  Falls back to "de" when not yet known.
                lang: str = state.get("detected_language") or "de"
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

    elif cmd_type == "spotify_cmd":
        await _handle_spotify_cmd(payload)

    elif cmd_type == "spotify_device_announce":
        await _handle_spotify_device_announce(payload)

    elif cmd_type == "start_listening":
        # Force the connection into listening mode, bypassing wake-word detection.
        # Used by the frontend's push-to-talk hook (issue #81).
        conn_id = id(ws)
        state = _connection_state.get(conn_id)
        if state is None:
            logger.warning("start_listening received but no connection state")
            return
        current_mode = state.get("mode", "idle")
        # Allow PTT activation only when idle or in follow-up window.
        # If we're already speaking / processing / listening, ignore — protects
        # against double-press and respects ongoing turns.
        if current_mode not in ("idle", "follow_up"):
            logger.debug(f"start_listening ignored — current mode is {current_mode!r}")
            return
        state["mode"] = "listening"
        state["audio_chunks"] = []
        state["speech_started"] = False
        state["silent_samples"] = 0
        state["total_samples"] = 0
        state["skip_remaining"] = 0
        if _wake_word_detector is not None:
            _wake_word_detector.reset()
        if _state_machine is not None:
            _state_machine.on_wake_word()  # treat PTT-start as a wake-word event for the state machine
        await broadcast_state("listening")
        logger.info(f"PTT: listening mode forced via start_listening command (was {current_mode!r})")

    elif cmd_type == "stop_listening":
        # PTT button released. If no speech was detected during the PTT session,
        # return to idle. If speech HAS started, leave the existing silence-
        # detector to finalise naturally (don't truncate mid-utterance).
        conn_id = id(ws)
        state = _connection_state.get(conn_id)
        if state is None:
            return
        if state.get("mode") == "listening" and not state.get("speech_started", False):
            state["mode"] = "idle"
            await broadcast_state("idle")
            logger.debug("PTT: stop_listening with no speech — returning to idle")
        # else: speech started, let the existing silence-detect path finalise the turn.

    else:
        logger.warning(f"Unknown command type: {cmd_type}")


async def _handle_spotify_cmd(payload: dict[str, Any]) -> None:
    """Handle an incoming ``spotify_cmd`` WebSocket message.

    Phase 1: dispatches play/pause/next/prev/volume directly to the
    SpotifyClient when one is initialised and authenticated.  Unknown
    actions are logged as warnings.

    Args:
        payload: ``{"action": str, "value": optional int}``
    """
    action = payload.get("action", "")
    value = payload.get("value")
    logger.info(f"spotify_cmd received: action={action!r} value={value!r}")

    if _spotify_client is None or not _spotify_client.is_authenticated():
        logger.warning("spotify_cmd received but client not authenticated — ignoring")
        return

    try:
        if action == "play":
            await _spotify_client.play()
        elif action == "pause":
            await _spotify_client.pause()
        elif action == "next":
            await _spotify_client.next_track()
        elif action == "prev":
            await _spotify_client.previous_track()
        elif action == "volume":
            if value is not None:
                await _spotify_client.set_volume(int(value))
            else:
                logger.warning("spotify_cmd volume received without 'value' field")
        else:
            logger.warning(f"Unknown spotify_cmd action: {action!r}")
    except Exception as exc:
        logger.error(f"spotify_cmd action={action!r} failed: {exc}")


async def _handle_spotify_device_announce(payload: dict[str, Any]) -> None:
    """Handle a ``spotify_device_announce`` WebSocket message from the HUD SDK.

    When ``ready`` is ``True`` the HUD's Web Playback SDK device is registered
    and the device_id is stored in ``_jarvis_spotify_device_id`` so the voice
    path can target it.  When ``ready`` is ``False`` the slot is cleared.

    Args:
        payload: ``{"device_id": str, "name": str, "ready": bool}``
    """
    global _jarvis_spotify_device_id

    device_id: str = payload.get("device_id", "")
    name: str = payload.get("name", "JARVIS")
    ready: bool = bool(payload.get("ready", False))

    # Log first 8 chars of device_id to avoid leaking the full token-like ID.
    short_id = device_id[:8] if device_id else ""
    logger.info(
        f"Spotify device announce: {name!r} device_id={short_id!r}... ready={ready}"
    )

    if ready:
        _jarvis_spotify_device_id = device_id
    else:
        _jarvis_spotify_device_id = None


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
# Online greeting helpers
# ---------------------------------------------------------------------------


async def _play_online_greeting() -> None:
    """Background task: synthesise and broadcast the JARVIS online greeting.

    Waits ``greeting.delay_seconds`` (default 0.8 s) so the HUD can finish
    wiring its WebSocket subscriptions before the audio frame arrives.
    Catches all exceptions — never crashes startup over a greeting failure.
    """
    from utils.config_loader import get_config as _get_cfg_og  # noqa: PLC0415

    try:
        _og_cfg = _get_cfg_og()
        greeting_cfg = _og_cfg.get_section("greeting") or {}
        if not greeting_cfg.get("enabled", True):
            return

        delay = float(greeting_cfg.get("delay_seconds", 0.8))
        mode = str(greeting_cfg.get("mode", "status"))

        await asyncio.sleep(delay)

        if _fish_tts is None or not _fish_tts._api_key:
            logger.warning("Online greeting skipped — Fish TTS not configured")
            return

        # --- Resolve salutation and language --------------------------------
        salutation = get_salutation(_persona_config) if _persona_config else "Sir"
        persona_section = _og_cfg.get_section("persona") or {}
        language = str(persona_section.get("default_language", "en"))
        # Fall back to config-level language key used elsewhere in the codebase.
        if language not in ("en", "de"):
            language = "en"

        # --- Collect runtime context ----------------------------------------
        from brain.online_greeting import (  # noqa: PLC0415
            GreetingContext,
            collect_greeting_context,
            render_greeting_text,
        )

        if mode == "static":
            # Minimal path — no data collection.
            _lang_is_de = language == "de"
            if _lang_is_de:
                text = f"Bin online, {salutation}. Alles bereit."
            else:
                text = f"Online, {salutation}. All systems nominal."
        else:
            # "status" mode — best-effort collect runtime state.
            async def _mail_provider() -> int | None:
                return _last_unread_count

            async def _calendar_provider() -> int | None:
                return _last_calendar_count

            async def _github_provider() -> int | None:
                if _github_poller is not None and _github_poller.last_state is not None:
                    return len(_github_poller.last_state.prs)
                return None

            async def _openclaw_provider() -> bool:
                if _openclaw_client is not None:
                    return await _openclaw_client.is_healthy()
                return False

            async def _metrics_provider() -> tuple[bool, bool]:
                if _last_metrics is not None:
                    cpu_ok = _last_metrics.cpu_percent < 80.0
                    ram_ok = _last_metrics.ram_percent < 90.0
                    return cpu_ok, ram_ok
                return True, True

            ctx = await collect_greeting_context(
                salutation=salutation,
                language=language,
                mail_state_provider=_mail_provider,
                calendar_state_provider=_calendar_provider,
                github_state_provider=_github_provider,
                openclaw_health_check=_openclaw_provider,
                system_metrics_provider=_metrics_provider,
            )
            text = render_greeting_text(ctx)

        # --- Synthesise and broadcast ----------------------------------------
        await broadcast_state("speaking")
        try:
            audio_bytes = await _fish_tts.synthesize(text)
        except FishTTSError as exc:
            logger.warning(f"Online greeting TTS failed: {exc}")
            await broadcast_state("idle")
            return

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        await broadcast_audio(audio_b64, text, channel="speech")
        logger.info(f"Greeting played: '{text}' ({len(audio_bytes)} bytes)")

        # Reset orb to idle — no fixed sleep needed; the pipeline follows the
        # same pattern as _run_voice_pipeline_body which broadcasts idle after
        # the audio is sent (the frontend controls actual playback duration).
        await broadcast_state("idle")

    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Online greeting failed — skipping: {exc}")
        # Best-effort idle reset so the orb doesn't stay stuck on "speaking".
        try:
            await broadcast_state("idle")
        except Exception:  # noqa: BLE001
            pass


def _schedule_online_greeting_if_needed() -> None:
    """Schedule the greeting background task if not already done this boot."""
    global _greeting_played
    if _greeting_played:
        return
    _greeting_played = True
    asyncio.ensure_future(_play_online_greeting())


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
        # Email confirmation pending state — set when JARVIS has read back a
        # draft and is waiting for an explicit confirm/cancel utterance.
        "pending_email_send": None,
        # Calendar operation pending state — set when JARVIS proposes a
        # create/update/delete and is waiting for verbal confirmation.
        "pending_calendar_op": None,
        # STT-detected language from the most recent successful pipeline run.
        # Used by backchannel playback so language-specific clips are played.
        # Defaults to None; "de" is used as fallback when unset.
        "detected_language": None,
    }
    if _wake_word_detector:
        _wake_word_detector.reset()

    logger.info(f"Client connected. Total clients: {len(_connected_clients)}")

    # Send initial state
    await ws.send_str(json.dumps({"type": "status", "state": "idle"}))
    await broadcast_system_metrics()

    # Push device identity so the HUD can render the DeviceBadge immediately.
    await ws.send_str(
        json.dumps(
            {
                "type": "device_info",
                "payload": {
                    "slug": _device_slug,
                    "platform": sys.platform,
                    "hostname": socket.gethostname(),
                },
            }
        )
    )

    # Per-client "welcome" notification — stable id ensures the frontend
    # dedups across reconnects within the same session, yet a fresh
    # browser tab always sees the HUD pipe is live.
    from datetime import datetime, timezone

    # Fetch unread count for the welcome context line — only if Google
    # OAuth is already done (cached token). Do NOT trigger the interactive
    # flow here, that would block the connection for up to 120 s while the
    # user isn't looking, and wedge the audio pipeline in the meantime.
    _welcome_unread_ctx = ""
    try:
        from utils.config_loader import get_config as _get_cfg

        _gmail_cfg = _get_cfg().get_section("gmail") or {}
        if _gmail_cfg.get("enabled", False):
            from integrations.google.gmail_client import get_gmail_client as _get_gc

            # Auth is managed by gog's own token store — no JARVIS-side gate needed.
            _uc = await asyncio.wait_for(
                _get_gc(
                    vip_senders=_gmail_cfg.get("vip_senders", [])
                ).get_unread_count(),
                timeout=3.0,
            )
            _welcome_unread_ctx = f" {_uc} ungelesene E-Mail(s)."
    except Exception as _wexc:
        logger.debug(f"Welcome unread count fetch skipped: {_wexc}")

    await ws.send_str(
        json.dumps(
            {
                "type": "notification",
                "payload": {
                    "id": "startup-ok",
                    "severity": "info",
                    "title": "JARVIS online",
                    "detail": (
                        "Voice-Pipeline, OpenClaw-Gateway und HUD verbunden."
                        + _welcome_unread_ctx
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
        )
    )

    # Push cached GitHub state immediately if available.
    if _github_poller is not None and _github_poller.last_state is not None:
        try:
            await broadcast_github_state(_github_poller.last_state)
        except Exception as _gh_exc:  # noqa: BLE001
            logger.debug(f"GitHub on-connect push failed: {_gh_exc}")

    # Push cached GitLab state immediately if available.
    if _gitlab_poller is not None and _gitlab_poller.last_state is not None:
        try:
            await broadcast_gitlab_state(_gitlab_poller.last_state)
        except Exception as _gl_exc:  # noqa: BLE001
            logger.debug(f"GitLab on-connect push failed: {_gl_exc}")

    # Replay buffered log lines to the newly connected client.
    try:
        from utils.logger import get_log_buffer as _get_log_buf  # noqa: PLC0415

        for _log_entry in _get_log_buf():
            await ws.send_str(
                json.dumps({"type": "log_line", "payload": _log_entry})
            )
    except Exception as _log_replay_exc:  # noqa: BLE001
        logger.debug(f"Log buffer replay failed: {_log_replay_exc}")

    # Mark the first-client event so other subsystems (scheduler, tests)
    # can still observe "at least one client has been here".
    if not _first_client_event.is_set():
        _first_client_event.set()

    # --- Online greeting: fire once per boot on the first client connect ---
    # Guard with _greeting_played so HMR reconnects don't trigger again.
    _schedule_online_greeting_if_needed()

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


async def health_handler(request: web.Request) -> web.Response:
    """Handle GET /health — lightweight liveness probe for controllers/monitors."""
    return web.json_response({"status": "ok"})


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
# /notify/wife — Ezgi WhatsApp inbound TTS notification endpoint
# ---------------------------------------------------------------------------

# SOUL.md persona extract cached at first handler call — avoids re-reading on
# every request. Only the sections relevant to spoken announcements are kept;
# the DM Auto-Reply Policy table is excluded (irrelevant for TTS generation).
_soul_extract_cache: str | None = None
_SOUL_MD_PATH: Path = Path.home() / ".openclaw" / "workspace" / "SOUL.md"
_SOUL_SECTIONS_WANTED = {
    "## Core Directives",
    "## Response Style",
    "## Language Handling",
    "## Voice Context",
}
_SOUL_SECTION_STOP = "## DM Auto-Reply Policy"


def _load_soul_extract() -> str:
    """Read SOUL.md and return only the announcement-relevant sections."""
    global _soul_extract_cache
    if _soul_extract_cache is not None:
        return _soul_extract_cache
    try:
        raw = _SOUL_MD_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(f"notify_wife: Could not read SOUL.md: {exc}")
        return ""
    lines = raw.splitlines()
    collecting = False
    result: list[str] = []
    current_section: str | None = None
    for line in lines:
        stripped = line.strip()
        # Check if we hit a stop section
        if stripped == _SOUL_SECTION_STOP:
            break
        # Check if line is a section header we want
        is_h2 = stripped.startswith("## ")
        if is_h2:
            current_section = stripped
            collecting = current_section in _SOUL_SECTIONS_WANTED
        if collecting:
            result.append(line)
    _soul_extract_cache = "\n".join(result).strip()
    return _soul_extract_cache


async def _generate_wife_announcement(bodies: list[str], cfg_wife: dict[str, Any]) -> str:
    """Call the Anthropic API to produce a single spoken announcement sentence.

    Args:
        bodies: List of (already truncated) message body strings.
        cfg_wife: The ``notifications.wife`` config dict.

    Returns:
        A TTS-friendly announcement sentence, or the configured fallback on error.
    """
    import os  # noqa: PLC0415
    import anthropic as _anthropic  # noqa: PLC0415

    fallback = str(cfg_wife.get("fallback_text", "Sir, Ihre Frau hat Ihnen eine Nachricht geschickt."))
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("notify_wife: ANTHROPIC_API_KEY not set — using fallback text")
        return fallback

    model = str(cfg_wife.get("announcement_model", "claude-sonnet-4-6"))
    soul_extract = _load_soul_extract()
    system_prompt = (
        "You are JARVIS. Produce a single-sentence spoken announcement for Johannes "
        "— no markdown, no lists, TTS-friendly, < 40 words.\n\n"
        + soul_extract
    )

    non_empty = [b for b in bodies if b.strip()]
    all_empty = len(non_empty) == 0

    if all_empty:
        user_prompt = (
            "Ihre Frau Ezgi hat Johannes während einer Abwesenheit ein Foto/Video/"
            "eine Sprachnachricht via WhatsApp geschickt. Formulieren Sie eine kurze "
            "Ansage (ein Satz, TTS-tauglich, keine Markdown-Formatierung) für Johannes."
        )
    elif len(non_empty) == 1:
        user_prompt = (
            f"Ihre Frau Ezgi hat Johannes während einer Abwesenheit eine WhatsApp-Nachricht"
            f" geschickt: «{non_empty[0]}». Formulieren Sie eine kurze Ansage "
            f"(ein Satz, TTS-tauglich, keine Markdown-Formatierung) für Johannes, "
            f"um ihn zu informieren."
        )
    else:
        numbered = "\n".join(f"{i + 1}. {b}" for i, b in enumerate(non_empty))
        # Bound the total joined length to keep the prompt reasonable
        if len(numbered) > 600:
            numbered = numbered[:600] + "…"
        user_prompt = (
            f"Ihre Frau Ezgi hat Johannes mehrere WhatsApp-Nachrichten während einer "
            f"Abwesenheit geschickt:\n{numbered}\n"
            f"Fassen Sie das in einem einzigen Satz zusammen (TTS-tauglich, keine "
            f"Markdown-Formatierung)."
        )

    try:
        client = _anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=model,
            max_tokens=80,
            temperature=0.7,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"notify_wife: Anthropic API error, using fallback: {exc}")
        return fallback


async def notify_wife_handler(request: web.Request) -> web.Response:
    """Handle POST /notify/wife — play a TTS announcement for an Ezgi WhatsApp message.

    Accepts both single-message and batched payloads from the ezgi-notifier hook.
    Validates sender_id against the configured allowlist, generates a spoken announcement
    via the Anthropic API, synthesizes it via Fish Audio TTS, and broadcasts the MP3
    to all connected WebSocket clients on the ``notification`` channel.
    """
    import uuid  # noqa: PLC0415
    from utils.config_loader import get_config as _gcfg  # noqa: PLC0415

    utterance_id = str(uuid.uuid4())

    # --- Parse body -----------------------------------------------------------
    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"notify_wife: Invalid JSON body: {exc}")
        return web.json_response({"accepted": False, "error": "invalid JSON"}, status=400)

    sender_id: str = payload.get("sender_id", "")
    sender_label: str = payload.get("sender_label", "")

    # Normalise to batch format
    if "messages" in payload:
        raw_messages: list[dict[str, Any]] = payload.get("messages", [])
    else:
        # Single-message shape
        raw_messages = [
            {
                "body": payload.get("body", ""),
                "timestamp": payload.get("timestamp", ""),
                "message_id": payload.get("message_id", utterance_id),
            }
        ]

    # --- Config ---------------------------------------------------------------
    cfg = _gcfg()
    cfg_wife: dict[str, Any] = (cfg.get_section("notifications") or {}).get("wife", {})
    allowed_sender = str(cfg_wife.get("sender_id", "+41765005527"))
    enabled = bool(cfg_wife.get("enabled", True))
    max_body_chars = int(cfg_wife.get("max_body_chars", 200))
    fallback_text = str(cfg_wife.get("fallback_text", "Sir, Ihre Frau hat Ihnen eine Nachricht geschickt."))

    # --- Validate sender_id ---------------------------------------------------
    if sender_id != allowed_sender:
        logger.warning(
            f"notify_wife: Rejected sender_id={sender_id!r} (allowed: {allowed_sender!r})"
        )
        return web.json_response(
            {"accepted": False, "error": "sender_id not in allowlist"}, status=403
        )

    # --- Feature flag ---------------------------------------------------------
    if not enabled:
        logger.info("notify_wife: feature disabled via config — skipping")
        return web.json_response(
            {"accepted": True, "utterance_id": None, "skipped": "disabled"}, status=200
        )

    # --- Truncate bodies ------------------------------------------------------
    bodies: list[str] = []
    for msg in raw_messages:
        body = str(msg.get("body", ""))
        if len(body) > max_body_chars:
            body = body[:max_body_chars] + "…"
        bodies.append(body)

    message_ids = [str(m.get("message_id", "")) for m in raw_messages]
    logger.info(
        f"notify_wife: accepted sender={sender_label!r} ({sender_id}), "
        f"utterance_id={utterance_id}, messages={len(bodies)}, "
        f"message_ids={message_ids}"
    )

    # --- Generate announcement text -------------------------------------------
    utterance = await _generate_wife_announcement(bodies, cfg_wife)
    logger.info(f"notify_wife: utterance_id={utterance_id}, text={utterance!r}")

    # --- Synthesize TTS -------------------------------------------------------
    if _fish_tts is None:
        logger.warning(f"notify_wife: _fish_tts is None — TTS unavailable, utterance_id={utterance_id}")
        return web.json_response(
            {"accepted": True, "utterance_id": utterance_id, "tts": "failed"}, status=200
        )

    try:
        tts_text = strip_markdown_for_tts(utterance)
        audio_bytes = await _fish_tts.synthesize(tts_text)
    except FishTTSError as exc:
        logger.error(f"notify_wife: FishTTSError — {exc}, utterance_id={utterance_id}")
        return web.json_response(
            {"accepted": True, "utterance_id": utterance_id, "tts": "failed"}, status=200
        )

    # --- Broadcast to WebSocket clients ---------------------------------------
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    await broadcast_audio(audio_b64, utterance, channel="notification")
    logger.info(f"notify_wife: broadcast complete, utterance_id={utterance_id}")

    return web.json_response({"accepted": True, "utterance_id": utterance_id}, status=200)


# ---------------------------------------------------------------------------
# /api/config/repos — GET + POST (localhost-only)
# ---------------------------------------------------------------------------

# Path to the config file — resolved relative to this file so it works
# regardless of CWD.
_CONFIG_YAML_PATH: Path = Path(__file__).parent.parent.parent / "config" / "config.yaml"


def _is_loopback(request: web.Request) -> bool:
    """Return True if the request originates from a loopback address."""
    peer = request.transport
    if peer is None:
        return False
    peername = peer.get_extra_info("peername")
    if peername is None:
        return False
    host = peername[0] if isinstance(peername, (list, tuple)) else str(peername)
    return host in {"127.0.0.1", "::1", "localhost"}


async def voice_metrics_handler(request: web.Request) -> web.Response:
    """GET /api/metrics/voice — phrase-cache hit/miss statistics.

    Returns a JSON object with raw counters plus a computed ``hit_rate``
    for each tracked cache category.  Safe to call at any time; counters
    are module-level and accumulate for the process lifetime.

    Returns:
        200 JSON with ``stats`` (raw counters) and ``summary`` (per-category
        hit rates and an aggregate ``overall_hit_rate``).
    """
    stats = dict(_phrase_cache_stats)

    def _rate(hits_key: str, misses_key: str) -> float:
        hits = stats.get(hits_key, 0)
        misses = stats.get(misses_key, 0)
        total = hits + misses
        return round(hits / total, 4) if total > 0 else 0.0

    summary = {
        "filler_hit_rate": _rate("filler_hits", "filler_misses"),
        "ack_hit_rate": _rate("ack_hits", "ack_misses"),
        "backchannel_hit_rate": _rate("backchannel_hits", "backchannel_misses"),
    }

    total_hits = (
        stats.get("filler_hits", 0)
        + stats.get("ack_hits", 0)
        + stats.get("backchannel_hits", 0)
    )
    total_misses = (
        stats.get("filler_misses", 0)
        + stats.get("ack_misses", 0)
        + stats.get("backchannel_misses", 0)
    )
    overall_total = total_hits + total_misses
    summary["overall_hit_rate"] = (
        round(total_hits / overall_total, 4) if overall_total > 0 else 0.0
    )

    return web.json_response({"stats": stats, "summary": summary})


async def _cache_stats_log_loop(interval_seconds: float) -> None:
    """Background coroutine: log phrase-cache hit/miss summary periodically.

    Args:
        interval_seconds: Seconds between log emissions.
    """
    while True:
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.info("Cache-stats log loop cancelled")
            return

        stats = _phrase_cache_stats
        total_hits = (
            stats.get("filler_hits", 0)
            + stats.get("ack_hits", 0)
            + stats.get("backchannel_hits", 0)
        )
        total_misses = (
            stats.get("filler_misses", 0)
            + stats.get("ack_misses", 0)
            + stats.get("backchannel_misses", 0)
        )
        overall_total = total_hits + total_misses
        hit_rate = round(total_hits / overall_total, 3) if overall_total > 0 else 0.0
        logger.info(
            f"[cache-stats] filler={stats.get('filler_hits', 0)}h/"
            f"{stats.get('filler_misses', 0)}m "
            f"ack={stats.get('ack_hits', 0)}h/{stats.get('ack_misses', 0)}m "
            f"bc={stats.get('backchannel_hits', 0)}h/"
            f"{stats.get('backchannel_misses', 0)}m "
            f"sleep={stats.get('sleep_match_hits', 0)} "
            f"overall_hit_rate={hit_rate:.1%}"
        )


# ── Default location fallback (Berlin) ─────────────────────────────────────
_DEFAULT_LATITUDE = 52.52
_DEFAULT_LONGITUDE = 13.41


async def config_location_handler(request: web.Request) -> web.Response:
    """GET /api/config/location — return latitude/longitude from config.yaml.

    Returns:
        JSON ``{latitude: float, longitude: float}``
    """
    try:
        from ruamel.yaml import YAML  # noqa: PLC0415

        yaml = YAML()
        yaml.preserve_quotes = True
        with _CONFIG_YAML_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.load(fh)

        loc = (data or {}).get("location") or {}
        latitude = float(loc.get("latitude", _DEFAULT_LATITUDE))
        longitude = float(loc.get("longitude", _DEFAULT_LONGITUDE))

        return web.json_response({"latitude": latitude, "longitude": longitude})
    except Exception as exc:  # noqa: BLE001
        return web.json_response(
            {"latitude": _DEFAULT_LATITUDE, "longitude": _DEFAULT_LONGITUDE},
        )


async def mcp_health_handler(request: web.Request) -> web.Response:
    """GET /api/mcp/health — return MCP server status and registered tools.

    Returns:
        JSON ``{"status": "ok", "tools": [...]}`` where ``tools`` is the list
        of currently registered tool metadata dicts.
    """
    return web.json_response({"status": "ok", "tools": list_registered_tools()})


async def config_repos_get_handler(request: web.Request) -> web.Response:
    """GET /api/config/repos — return current github.repos and gitlab.projects.

    Localhost-only: rejects requests from non-loopback IPs with 403.

    Returns:
        JSON ``{github: [...], gitlab: [...]}``
    """
    if not _is_loopback(request):
        return web.Response(status=403, text="Forbidden: localhost only")

    try:
        from ruamel.yaml import YAML  # noqa: PLC0415

        yaml = YAML()
        yaml.preserve_quotes = True
        with _CONFIG_YAML_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.load(fh)

        github_repos: list[str] = []
        gitlab_repos: list[str] = []

        if data:
            gh_section = data.get("github") or {}
            gl_section = data.get("gitlab") or {}
            github_repos = list(gh_section.get("repos") or [])
            gitlab_repos = list(gl_section.get("projects") or [])

        return web.json_response({"github": github_repos, "gitlab": gitlab_repos})
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[config_repos] GET failed: {exc}")
        return web.Response(status=500, text=str(exc))


async def config_repos_post_handler(request: web.Request) -> web.Response:
    """POST /api/config/repos — update github.repos and gitlab.projects.

    Localhost-only. Reads the existing config, updates only the repo lists,
    writes back using ruamel.yaml so comments are preserved.

    Body: JSON ``{github: [...], gitlab: [...]}``
    """
    if not _is_loopback(request):
        return web.Response(status=403, text="Forbidden: localhost only")

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return web.Response(status=400, text="Invalid JSON body")

    if not isinstance(body, dict):
        return web.Response(status=400, text="Body must be a JSON object")

    github_list = body.get("github")
    gitlab_list = body.get("gitlab")
    if not isinstance(github_list, list) or not isinstance(gitlab_list, list):
        return web.Response(status=400, text="Fields 'github' and 'gitlab' must be arrays")

    # Validate: all items must be non-empty strings
    for item in github_list + gitlab_list:
        if not isinstance(item, str) or not item.strip():
            return web.Response(status=400, text="All repo entries must be non-empty strings")

    try:
        from ruamel.yaml import YAML  # noqa: PLC0415

        yaml = YAML()
        yaml.preserve_quotes = True
        with _CONFIG_YAML_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.load(fh)

        if data is None:
            return web.Response(status=500, text="Config file is empty or invalid")

        if "github" not in data or data["github"] is None:
            data["github"] = {}
        if "gitlab" not in data or data["gitlab"] is None:
            data["gitlab"] = {}

        data["github"]["repos"] = github_list
        data["gitlab"]["projects"] = gitlab_list

        with _CONFIG_YAML_PATH.open("w", encoding="utf-8") as fh:
            yaml.dump(data, fh)

        logger.info(
            f"[config_repos] Updated github.repos={github_list}, "
            f"gitlab.projects={gitlab_list}"
        )
        return web.json_response({"ok": True})
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[config_repos] POST failed: {exc}")
        return web.Response(status=500, text=str(exc))


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
    global _quick_ack_enabled, _mail_poller_task
    global _spotify_client, _spotify_poller_task
    global _github_poller, _github_session
    global _gitlab_client, _gitlab_poller, _gitlab_poller_task
    global _calendar_poller_task, _cache_stats_log_task
    global _greeting_played, _last_unread_count, _last_calendar_count
    global _state_machine, _narration_queue, _narration_drainer_task

    # Reset per-boot greeting flag so tests / re-initialisation get a fresh
    # greeting each time start_ws_server is called.
    _greeting_played = False
    _last_unread_count = None
    _last_calendar_count = None

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
    try:
        _stt_engine = await create_stt_engine()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"STT engine unavailable — voice input disabled: {exc}")
        _stt_engine = None

    logger.info("Loading wake word detector...")
    try:
        _wake_word_detector = await create_wake_word_detector()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Wake word detector unavailable — wake word disabled: {exc}")
        _wake_word_detector = None

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

    # --- MCP server (tool provider for OpenClaw agent runtime) ---
    mcp_config = cfg.get_section("mcp") or {}

    # Operator hygiene prompt: always remind about the legacy "jarvis" entry.
    logger.info(
        "Legacy 'jarvis' MCP entry may exist. Remove with: openclaw mcp unset jarvis"
    )
    logger.info(
        f"Paste the following into ~/.openclaw/workspace/TOOLS.md to register this "
        f"device in the agent's fleet registry:\n"
        f"## Device: {_device_slug}\n"
        f"- MCP server name: jarvis-{_device_slug}\n"
        f"- Platform: {sys.platform}\n"
        f"- SSE URL: {get_sse_advertise_url(mcp_config)}\n"
        f"- Session ID: jarvis-{_device_slug}"
    )

    await start_mcp_server(mcp_config, device_slug=_device_slug)
    if (
        mcp_config.get("auto_register_with_openclaw", True)
        and mcp_config.get("enabled", True)
        and _openclaw_client is not None
    ):
        mcp_url = get_sse_advertise_url(mcp_config)
        mcp_name = f"jarvis-{_device_slug}"
        _openclaw_headers = mcp_config.get("openclaw_headers") or {}
        await _openclaw_client.register_mcp_server(
            url=mcp_url,
            name=mcp_name,
            headers=_openclaw_headers if _openclaw_headers else None,
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

    # Conversation state machine + narration queue (#93 Phase 1 + 2).
    narration_cfg = cfg.get_section("narration") or {}
    rate_cfg: dict[str, Any] = narration_cfg.get("per_source_rate_limit") or {}
    _state_machine = ConversationStateMachine(on_transition=_on_conversation_state_transition)
    _narration_queue = NarrationQueue(
        state_machine=_state_machine,
        tts_emit=_emit_synthetic_utterance,
        update_voice=bool(narration_cfg.get("update_voice", False)),
        urgent_max_wait_seconds=float(narration_cfg.get("urgent_max_wait_seconds", 30)),
        completion_batch_seconds=float(narration_cfg.get("completion_batch_seconds", 10)),
        rate_limit_items=int(rate_cfg.get("items", 6)),
        rate_limit_window_seconds=float(rate_cfg.get("window_seconds", 60)),
        quiet_mode_default_minutes=int(narration_cfg.get("quiet_mode_default_minutes", 60)),
        on_queue_mutation=_on_narration_queue_mutation,
    )
    _narration_queue.start()
    _narration_drainer_task = None  # task handle is owned by NarrationQueue.start()

    _orchestrator = Orchestrator(
        claude_client=claude_client,
        memory=None,
        tts_engine=None,
        memory_store=_memory_store,
        narration_queue=_narration_queue,
        state_machine=_state_machine,
    )

    _intent_parser = get_intent_parser()

    logger.info("Voice pipeline components ready")

    # Server ports, host and CORS
    ws_port = config.get("ws_port", 8765)
    http_port = config.get("http_port", 8766)
    # Default is loopback — JARVIS is a personal assistant; exposing to 0.0.0.0
    # with no authentication is a security risk. Override in config.yaml only
    # if you deliberately want LAN/WAN exposure and have added auth.
    host = config.get("host", "127.0.0.1")
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
    http_app.router.add_get("/health", health_handler)
    http_app.router.add_get("/voices", voices_handler)
    http_app.router.add_post("/notify/wife", notify_wife_handler)
    http_app.router.add_get("/oauth/spotify/start", spotify_oauth_start_handler)
    http_app.router.add_get("/oauth/spotify/callback", spotify_oauth_callback_handler)
    http_app.router.add_get("/api/config/repos", config_repos_get_handler)
    http_app.router.add_post("/api/config/repos", config_repos_post_handler)
    http_app.router.add_get("/api/metrics/voice", voice_metrics_handler)
    http_app.router.add_get("/api/config/location", config_location_handler)
    http_app.router.add_get("/api/mcp/health", mcp_health_handler)
    # Spotify library / search / queue REST endpoints
    http_app.router.add_get("/api/spotify/playlists", spotify_playlists_handler)
    http_app.router.add_get(
        "/api/spotify/playlists/{id}/tracks", spotify_playlist_tracks_handler
    )
    http_app.router.add_get(
        "/api/spotify/albums/{id}/tracks", spotify_album_tracks_handler
    )
    http_app.router.add_get("/api/spotify/me/tracks", spotify_saved_tracks_handler)
    http_app.router.add_get("/api/spotify/me/albums", spotify_saved_albums_handler)
    http_app.router.add_get("/api/spotify/search", spotify_search_handler)
    http_app.router.add_get("/api/spotify/queue", spotify_queue_get_handler)
    http_app.router.add_post("/api/spotify/queue", spotify_queue_post_handler)
    http_app.router.add_post("/api/spotify/play/context", spotify_play_context_handler)
    http_app.router.add_post("/api/spotify/play/uris", spotify_play_uris_handler)
    http_app.router.add_get("/api/spotify/token", spotify_token_handler)
    # Narration / activity endpoints (#93 Phase 2)
    http_app.router.add_post("/api/jarvis/notify", jarvis_notify_handler)
    http_app.router.add_post("/api/jarvis/status", jarvis_status_handler)
    http_app.router.add_post("/api/jarvis/quiet", jarvis_quiet_handler)

    # Start WebSocket server
    ws_runner = web.AppRunner(ws_app)
    await ws_runner.setup()
    ws_site = web.TCPSite(ws_runner, host, ws_port)
    await ws_site.start()
    logger.info(f"WebSocket server started on {host}:{ws_port}")

    # Start HTTP server
    http_runner = web.AppRunner(http_app)
    await http_runner.setup()
    http_site = web.TCPSite(http_runner, host, http_port)
    await http_site.start()
    logger.info(f"HTTP server started on {host}:{http_port}")

    # Log-panel sink — wire loguru → WS broadcast when feature is enabled.
    log_panel_cfg = cfg.get_section("log_panel") or {}
    if log_panel_cfg.get("enabled", True):
        from utils.logger import register_ws_broadcast as _register_log_sink  # noqa: PLC0415

        _log_max_buf = int(log_panel_cfg.get("max_buffer_lines", 500))
        _register_log_sink(_broadcast, _log_max_buf)
        logger.info(f"Log-panel WS sink registered (max_buffer_lines={_log_max_buf})")

    # Background metrics broadcast — 2 s interval via SystemMetricsCollector.
    _metrics_collector = SystemMetricsCollector(interval_seconds=2.0)
    _metrics_task = asyncio.create_task(_metrics_collector.run(_on_metrics_snapshot))

    # Phrase-cache stats logger — logs a summary every N seconds.
    _cache_log_interval = float(
        voice_config.get("cache_stats_log_interval_seconds", 300)
    )
    _cache_stats_log_task = asyncio.create_task(
        _cache_stats_log_loop(_cache_log_interval)
    )
    logger.info(f"Phrase-cache stats logger started (interval={_cache_log_interval:.0f}s)")

    # Gmail mail poller — start only when gmail.enabled is true.
    gmail_cfg = cfg.get_section("gmail") or {}
    if gmail_cfg.get("enabled", False):
        _gmail_poll_interval = int(gmail_cfg.get("poll_interval_seconds", 120))
        _gmail_vip_senders: list[str] = gmail_cfg.get("vip_senders", [])
        _mail_poller_task = asyncio.create_task(
            _start_mail_poller(_gmail_poll_interval, _gmail_vip_senders)
        )
        logger.info(f"Gmail mail poller registered (interval={_gmail_poll_interval}s)")

    # Calendar poller — start only when calendar.enabled is true.
    global _calendar_poller_task
    cal_cfg = cfg.get_section("calendar") or {}
    if cal_cfg.get("enabled", False):
        _cal_poll_interval = int(cal_cfg.get("poll_interval_seconds", 60))
        _calendar_poller_task = asyncio.create_task(
            _start_calendar_poller(_cal_poll_interval)
        )
        logger.info(f"Calendar poller registered (interval={_cal_poll_interval}s)")

    # Spotify integration — initialise client when enabled.
    from integrations.spotify.client import SpotifyAuthError  # noqa: PLC0415

    spotify_cfg = cfg.get_section("spotify") or {}
    if spotify_cfg.get("enabled", False):
        _spotify_client = SpotifyClient(spotify_cfg)
        try:
            await _spotify_client.initialize()
            # After successful initialisation, compare the cached token's scopes
            # against the configured set. If the token predates the `streaming`
            # scope (added for the Web Playback SDK), flag a scope upgrade so the
            # HUD shows the "neue Berechtigungen erforderlich" banner immediately.
            _configured_scopes = set(spotify_cfg.get("scopes", []))
            _token_scopes = _spotify_client.cached_scopes()
            if _token_scopes and not _configured_scopes.issubset(_token_scopes):
                _missing = _configured_scopes - _token_scopes
                logger.info(
                    f"Spotify scopes updated — user must re-authenticate via VERBINDEN "
                    f"(missing in cached token: {sorted(_missing)})"
                )
                _spotify_scope_upgrade_pending = True
            poll_interval_s = int(spotify_cfg.get("poll_interval", 10))
            _spotify_poller_task = asyncio.create_task(
                _spotify_state_loop(_spotify_client, poll_interval_s)
            )
            logger.info(
                f"Spotify client ready — poller started (interval={poll_interval_s}s)"
            )
        except SpotifyAuthError as _sp_exc:
            logger.warning(
                f"Spotify auth required — no token cached: {_sp_exc}. "
                f"Auth URL: {_spotify_client.get_auth_url()}"
            )
            await broadcast_notification(
                notification_id="spotify-auth-required",
                severity="info",
                title="Spotify-Authentifizierung erforderlich",
                detail=(
                    "Bitte besuche die Auth-URL im Browser um Spotify zu verbinden. "
                    f"URL: {_spotify_client.get_auth_url()}"
                ),
            )
            # Even without a cached token, run the poller — it broadcasts
            # `authenticated: false` so the HUD renders AuthPrompt; the OAuth
            # callback will rebuild the client and start a fresh poller.
            await broadcast_spotify_state(authenticated=False, scope_upgrade_required=False)
            poll_interval_s = int(spotify_cfg.get("poll_interval", 10))
            _spotify_poller_task = asyncio.create_task(
                _spotify_state_loop(_spotify_client, poll_interval_s)
            )
        except Exception as _sp_exc:
            logger.error(f"Spotify client initialisation failed: {_sp_exc}")
    else:
        logger.info("Spotify integration disabled (spotify.enabled: false)")

    # GitHub integration — token-gated; skipped silently when token absent.
    import os as _os  # noqa: PLC0415

    github_cfg = cfg.get_section("github") or {}
    _github_token = _os.environ.get("GITHUB_TOKEN", "").strip()
    if github_cfg.get("enabled", False) and _github_token:
        _gh_repos: list[str] = github_cfg.get("repos", [])
        _gh_interval = int(github_cfg.get("poll_interval_seconds", 60))
        try:
            await _start_github_poller(
                token=_github_token,
                repos=_gh_repos,
                poll_interval=_gh_interval,
            )
        except Exception as _gh_exc:
            logger.error(f"GitHub poller initialisation failed: {_gh_exc}")
    elif github_cfg.get("enabled", False) and not _github_token:
        logger.info(
            "GitHub integration enabled but GITHUB_TOKEN is absent — poller skipped"
        )
    else:
        logger.debug("GitHub integration disabled (github.enabled: false)")

    # GitLab integration — token-gated; skipped silently when token absent.
    gitlab_cfg = cfg.get_section("gitlab") or {}
    _gitlab_token = _os.environ.get("GITLAB_TOKEN", "").strip()
    # GITLAB_URL env var overrides config.gitlab.url
    _gitlab_url = (
        _os.environ.get("GITLAB_URL", "").strip()
        or gitlab_cfg.get("url", "https://gitlab.com")
    )
    if gitlab_cfg.get("enabled", False) and _gitlab_token:
        _gl_projects: list[str] = gitlab_cfg.get("projects", [])
        _gl_interval = int(gitlab_cfg.get("poll_interval_seconds", 60))
        try:
            await _start_gitlab_poller(
                token=_gitlab_token,
                url=_gitlab_url,
                projects=_gl_projects,
                poll_interval=_gl_interval,
            )
        except Exception as _gl_exc:
            logger.error(f"GitLab poller initialisation failed: {_gl_exc}")
    elif gitlab_cfg.get("enabled", False) and not _gitlab_token:
        logger.info(
            "GitLab integration enabled but GITLAB_TOKEN is absent — poller skipped"
        )
    else:
        logger.debug("GitLab integration disabled (gitlab.enabled: false)")

    # Keep running until cancelled (e.g. SIGINT from main.py).
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("WebSocket server cancelled — shutting down...")
        raise
    finally:
        # Stop the NarrationQueue drainer task.
        if _narration_queue is not None:
            _narration_queue.stop()

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

        # Cancel the phrase-cache stats logger task.
        if _cache_stats_log_task is not None and not _cache_stats_log_task.done():
            _cache_stats_log_task.cancel()
            try:
                await _cache_stats_log_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        _cache_stats_log_task = None

        # Cancel the mail poller task if running.
        if _mail_poller_task is not None and not _mail_poller_task.done():
            _mail_poller_task.cancel()
            try:
                await _mail_poller_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        _mail_poller_task = None

        # Cancel the calendar poller task if running.
        if _calendar_poller_task is not None and not _calendar_poller_task.done():
            _calendar_poller_task.cancel()
            try:
                await _calendar_poller_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        _calendar_poller_task = None

        # Cancel the Spotify poller task if running.
        if _spotify_poller_task is not None and not _spotify_poller_task.done():
            _spotify_poller_task.cancel()
            try:
                await _spotify_poller_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        _spotify_poller_task = None

        # Stop the GitHub poller and close its aiohttp session.
        if _github_poller is not None:
            try:
                await _github_poller.stop()
            except Exception as _gh_exc:  # noqa: BLE001
                logger.warning(f"GitHub poller stop failed: {_gh_exc}")
        _github_poller = None
        if _github_session is not None:
            try:
                await _github_session.close()
            except Exception as _gh_exc:  # noqa: BLE001
                logger.warning(f"GitHub session close failed: {_gh_exc}")
        _github_session = None

        # Stop the GitLab poller task.
        if _gitlab_poller is not None:
            try:
                await _gitlab_poller.stop()
            except Exception as _gl_exc:  # noqa: BLE001
                logger.warning(f"GitLab poller stop failed: {_gl_exc}")
        _gitlab_poller = None
        _gitlab_client = None
        if _gitlab_poller_task is not None and not _gitlab_poller_task.done():
            _gitlab_poller_task.cancel()
            try:
                await _gitlab_poller_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        _gitlab_poller_task = None

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

        # Close Fish TTS persistent httpx client.
        if _fish_tts is not None:
            try:
                await _fish_tts.aclose()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Fish TTS client close failed: {exc}")

        # Unregister JARVIS from OpenClaw MCP registry + stop MCP server.
        _mcp_cfg = cfg.get_section("mcp") or {}
        if (
            _mcp_cfg.get("auto_register_with_openclaw", True)
            and _mcp_cfg.get("enabled", True)
            and _openclaw_client is not None
        ):
            try:
                await asyncio.wait_for(
                    _openclaw_client.unregister_mcp_server(
                        name=f"jarvis-{_device_slug}"
                    ),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.debug("MCP unregister timed out — skipping")
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"MCP unregister error (non-fatal): {exc}")
        try:
            await asyncio.wait_for(stop_mcp_server(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("MCP server stop timed out after 5 s")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"MCP server stop failed: {exc}")

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
