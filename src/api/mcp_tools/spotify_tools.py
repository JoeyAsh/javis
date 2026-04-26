"""MCP tool registrations for the ``spotify_*`` namespace.

Exposes all Spotify playback capabilities as MCP tools so that OpenClaw —
not JARVIS locally — drives every voice-initiated Spotify action.  Each tool
resolves the in-process ``SpotifyClient`` singleton from ``ws_server`` and the
preferred device ID from the same module.

Registered tools (13):
- ``spotify_play_context``
- ``spotify_play_uris``
- ``spotify_pause``
- ``spotify_resume``
- ``spotify_next_track``
- ``spotify_previous_track``
- ``spotify_seek``
- ``spotify_set_volume``
- ``spotify_set_shuffle``
- ``spotify_set_repeat``
- ``spotify_search``
- ``spotify_add_to_queue``
- ``spotify_get_current_playback``
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import api.ws_server as ws_server
from api.mcp_server import register_tool
from integrations.spotify.client import (
    SpotifyAuthError,
    SpotifyClient,
    SpotifyPlaylist,
    SpotifyPollError,
    SpotifyPremiumError,
)
from utils.logger import get_logger

logger = get_logger("mcp_tools.spotify")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _auth_error_response() -> dict[str, Any]:
    """Build the structured auth-error response dict."""
    client = ws_server.get_spotify_client()
    auth_url = ""
    if client is not None:
        try:
            auth_url = client.get_auth_url()
        except SpotifyAuthError:
            auth_url = ""
    return {"ok": False, "error": "spotify_not_authenticated", "auth_url": auth_url}


def _check_client() -> dict[str, Any] | None:
    """Return an error dict when the client is absent or not authenticated, else None."""
    client = ws_server.get_spotify_client()
    if client is None or not client.is_authenticated():
        return _auth_error_response()
    return None


def _map_exception(exc: Exception) -> dict[str, Any]:
    """Map a caught exception to a structured error response dict.

    Covers SpotifyAuthError, SpotifyPremiumError, SpotifyPollError,
    and generic Exception.  Ordering matters: SpotifyPollError is inspected
    for 404 / no-active-device / 5xx markers BEFORE being labelled rate_limited.
    """
    if isinstance(exc, SpotifyAuthError):
        return _auth_error_response()
    if isinstance(exc, SpotifyPremiumError):
        return {"ok": False, "error": "spotify_premium_required"}
    if isinstance(exc, SpotifyPollError):
        msg = str(exc).lower()
        # 404 / no active device check comes FIRST.
        if "404" in msg or "no active device" in msg or "not found" in msg:
            return {"ok": False, "error": "spotify_no_active_device"}
        # 5xx server-side errors.
        for code in ("500", "502", "503", "504"):
            if code in msg:
                return {
                    "ok": False,
                    "error": "spotify_api_error",
                    "http_status": int(code),
                    "detail": str(exc)[:200],
                }
        # True rate-limit or other transient poll error.
        retry_after = getattr(exc, "retry_after", None)
        result: dict[str, Any] = {"ok": False, "error": "spotify_rate_limited"}
        if retry_after is not None:
            try:
                result["retry_after_seconds"] = int(retry_after)
            except (TypeError, ValueError):
                pass
        return result

    # Defensive: raw spotipy exception that bypassed _map_spotipy_exception.
    import spotipy  # noqa: PLC0415

    if isinstance(exc, spotipy.SpotifyException):
        if exc.http_status == 401:
            return _auth_error_response()
        if exc.http_status == 403:
            return {"ok": False, "error": "spotify_premium_required"}
        if exc.http_status == 404:
            return {"ok": False, "error": "spotify_no_active_device"}
        detail = str(exc)[:200]
        return {
            "ok": False,
            "error": "spotify_api_error",
            "http_status": exc.http_status,
            "detail": detail,
        }

    # Generic fallback — also catches 404-keyed messages from non-spotipy paths.
    msg = str(exc).lower()
    if "404" in msg or "no active device" in msg or "not found" in msg:
        return {"ok": False, "error": "spotify_no_active_device"}

    detail = str(exc)[:200]
    return {"ok": False, "error": "spotify_api_error", "detail": detail}


async def _play_with_device_warmup(
    client: SpotifyClient,
    device_id: str | None,
    play_call: Callable[[], Coroutine[Any, Any, None]],
) -> dict[str, Any] | None:
    """Try play_call once; on no-active-device, transfer + retry once.

    Returns None on success, or a structured error dict on definitive failure.
    """
    try:
        await play_call()
        return None
    except Exception as exc:
        err = _map_exception(exc)
        if err["error"] == "spotify_no_active_device" and device_id is not None:
            logger.debug(
                f"spotify: device {device_id!r} cold — transferring playback and retrying"
            )
            try:
                await client.transfer_playback(device_id)
                await asyncio.sleep(0.4)
                await play_call()
                return None
            except Exception as retry_exc:
                return _map_exception(retry_exc)
        return err


async def _device_warmup_simple(
    client: SpotifyClient,
    device_id: str | None,
    play_call: Callable[[], Coroutine[Any, Any, None]],
) -> dict[str, Any] | None:
    """Warmup helper for transport controls that don't take a device_id arg.

    Resolves device_id from ws_server when not provided, then delegates to
    _play_with_device_warmup.
    """
    resolved = device_id or ws_server.get_spotify_device_id()
    return await _play_with_device_warmup(client, resolved, play_call)


def _fuzzy_match_playlist(
    query: str, playlists: list[SpotifyPlaylist], min_ratio: float = 0.6
) -> SpotifyPlaylist | None:
    """Find the best-matching playlist for a given query string.

    First tries a case-insensitive substring match; falls back to a
    Levenshtein similarity ratio when no substring match is found.

    Args:
        query: User's playlist name hint.
        playlists: List of candidate playlists.
        min_ratio: Minimum Levenshtein ratio (0–1) to accept a fuzzy match.

    Returns:
        Best-matching SpotifyPlaylist, or None if no match exceeds the threshold.
    """
    query_lower = query.lower()

    # 1. Substring match (case-insensitive).
    for pl in playlists:
        if query_lower in pl.name.lower():
            logger.debug(f"Playlist substring match: {pl.name!r} for {query!r}")
            return pl

    # 2. Levenshtein ratio fallback.
    best_pl: SpotifyPlaylist | None = None
    best_ratio = 0.0
    for pl in playlists:
        ratio = _levenshtein_ratio(query_lower, pl.name.lower())
        if ratio > best_ratio:
            best_ratio = ratio
            best_pl = pl

    if best_ratio >= min_ratio and best_pl is not None:
        logger.debug(
            f"Playlist Levenshtein match: {best_pl.name!r} "
            f"(ratio={best_ratio:.2f}) for {query!r}"
        )
        return best_pl

    logger.debug(
        f"No playlist match found for {query!r} "
        f"(best_ratio={best_ratio:.2f}, threshold={min_ratio})"
    )
    return None


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Compute the Levenshtein similarity ratio between two strings.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Float in [0, 1]; 1.0 means identical strings.
    """
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    dp = list(range(len2 + 1))
    for i in range(1, len1 + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, len2 + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp

    distance = dp[len2]
    max_len = max(len1, len2)
    return 1.0 - distance / max_len


# ---------------------------------------------------------------------------
# MCP tool registrations
# ---------------------------------------------------------------------------


@register_tool(
    name="spotify_play_context",
    description=(
        "Start playback of a Spotify context (playlist, album, or artist) by URI or "
        "free-text name. When context_uri is a Spotify URI (starts with 'spotify:'), it "
        "is used directly. Otherwise the value is treated as a free-text playlist name "
        "and fuzzy-matched against the user's playlist library. Use offset_uri to start "
        "from a specific track within the context. Omit device_id to target the current "
        "JARVIS HUD device or the last active Spotify Connect device."
    ),
    schema={
        "type": "object",
        "properties": {
            "context_uri": {
                "type": "string",
                "description": (
                    "Spotify context URI (e.g. 'spotify:playlist:<id>') or a free-text "
                    "playlist name to fuzzy-match."
                ),
            },
            "offset_uri": {
                "type": "string",
                "description": "Optional track URI to start from within the context.",
            },
            "device_id": {
                "type": "string",
                "description": (
                    "Spotify Connect device ID; omit to use the JARVIS HUD device "
                    "or the last active device."
                ),
            },
        },
        "required": ["context_uri"],
    },
)
async def spotify_play_context(
    context_uri: str,
    offset_uri: str | None = None,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Start playback of a Spotify context (playlist, album, or artist)."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info("mcp_tool_call: spotify_play_context | outcome=spotify_not_authenticated")
        return auth_err

    resolved_device_id = device_id or ws_server.get_spotify_device_id()
    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    # Determine whether context_uri is a real URI or a free-text name.
    if context_uri.startswith("spotify:"):
        # Direct URI — play with warmup.
        err = await _play_with_device_warmup(
            client,
            resolved_device_id,
            lambda: client.play_context(
                context_uri, offset_uri=offset_uri, device_id=resolved_device_id
            ),
        )
        if err is not None:
            logger.warning(
                f"mcp_tool_call: spotify_play_context | uri={context_uri!r} | "
                f"outcome={err['error']}"
            )
            return err

        logger.info(
            f"mcp_tool_call: spotify_play_context | uri={context_uri!r} | outcome=ok"
        )
        return {"ok": True, "context_uri": context_uri}

    # Free-text name — fuzzy-match against the user's playlist library.
    query = context_uri.strip()
    try:
        playlists = await client.list_playlists(limit=50)
    except Exception as exc:
        err = _map_exception(exc)
        logger.warning(
            f"mcp_tool_call: spotify_play_context | query={query!r} | "
            f"outcome={err['error']} (list_playlists)"
        )
        return err

    best = _fuzzy_match_playlist(query, playlists)
    if best is None:
        logger.info(
            f"mcp_tool_call: spotify_play_context | query={query!r} | "
            "outcome=spotify_playlist_not_found"
        )
        return {"ok": False, "error": "spotify_playlist_not_found", "query": query}

    err = await _play_with_device_warmup(
        client,
        resolved_device_id,
        lambda: client.play_context(
            best.uri, offset_uri=offset_uri, device_id=resolved_device_id
        ),
    )
    if err is not None:
        logger.warning(
            f"mcp_tool_call: spotify_play_context | query={query!r} | "
            f"matched={best.name!r} | outcome={err['error']}"
        )
        return err

    logger.info(
        f"mcp_tool_call: spotify_play_context | query={query!r} | "
        f"matched={best.name!r} | uri={best.uri} | outcome=ok"
    )
    return {"ok": True, "playlist_name": best.name, "playlist_uri": best.uri}


@register_tool(
    name="spotify_play_uris",
    description=(
        "Start playback of an explicit list of Spotify track URIs. The tracks are played "
        "in order. Omit device_id to target the current JARVIS HUD device or the last "
        "active Spotify Connect device."
    ),
    schema={
        "type": "object",
        "properties": {
            "uris": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of Spotify track URIs to play (e.g. 'spotify:track:<id>').",
            },
            "device_id": {
                "type": "string",
                "description": (
                    "Spotify Connect device ID; omit to use the JARVIS HUD device "
                    "or the last active device."
                ),
            },
        },
        "required": ["uris"],
    },
)
async def spotify_play_uris(
    uris: list[str],
    device_id: str | None = None,
) -> dict[str, Any]:
    """Start playback of an explicit list of Spotify track URIs."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info("mcp_tool_call: spotify_play_uris | outcome=spotify_not_authenticated")
        return auth_err

    resolved_device_id = device_id or ws_server.get_spotify_device_id()
    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    err = await _play_with_device_warmup(
        client,
        resolved_device_id,
        lambda: client.play_uris(uris, device_id=resolved_device_id),
    )
    if err is not None:
        logger.warning(
            f"mcp_tool_call: spotify_play_uris | uris_count={len(uris)} | "
            f"outcome={err['error']}"
        )
        return err

    logger.info(
        f"mcp_tool_call: spotify_play_uris | uris_count={len(uris)} | outcome=ok"
    )
    return {"ok": True, "uris_played": uris}


@register_tool(
    name="spotify_pause",
    description=(
        "Pause Spotify playback on the current or specified device. Omit device_id to "
        "target the current JARVIS HUD device or the last active Spotify Connect device."
    ),
    schema={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": (
                    "Spotify Connect device ID; omit to use the JARVIS HUD device "
                    "or the last active device."
                ),
            },
        },
        "required": [],
    },
)
async def spotify_pause(device_id: str | None = None) -> dict[str, Any]:
    """Pause Spotify playback on the active device."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info("mcp_tool_call: spotify_pause | outcome=spotify_not_authenticated")
        return auth_err

    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    err = await _device_warmup_simple(client, device_id, client.pause)
    if err is not None:
        logger.warning(f"mcp_tool_call: spotify_pause | outcome={err['error']}")
        return err

    logger.info("mcp_tool_call: spotify_pause | outcome=ok")
    return {"ok": True}


@register_tool(
    name="spotify_resume",
    description=(
        "Resume (unpause) Spotify playback on the current or specified device. Omit "
        "device_id to target the current JARVIS HUD device or the last active Spotify "
        "Connect device."
    ),
    schema={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": (
                    "Spotify Connect device ID; omit to use the JARVIS HUD device "
                    "or the last active device."
                ),
            },
        },
        "required": [],
    },
)
async def spotify_resume(device_id: str | None = None) -> dict[str, Any]:
    """Resume Spotify playback on the active device."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info("mcp_tool_call: spotify_resume | outcome=spotify_not_authenticated")
        return auth_err

    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    err = await _device_warmup_simple(client, device_id, client.play)
    if err is not None:
        logger.warning(f"mcp_tool_call: spotify_resume | outcome={err['error']}")
        return err

    logger.info("mcp_tool_call: spotify_resume | outcome=ok")
    return {"ok": True}


@register_tool(
    name="spotify_next_track",
    description=(
        "Skip to the next track in the Spotify playback queue. Omit device_id to target "
        "the current JARVIS HUD device or the last active Spotify Connect device."
    ),
    schema={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": (
                    "Spotify Connect device ID; omit to use the JARVIS HUD device "
                    "or the last active device."
                ),
            },
        },
        "required": [],
    },
)
async def spotify_next_track(device_id: str | None = None) -> dict[str, Any]:
    """Skip to the next track in the Spotify queue."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info("mcp_tool_call: spotify_next_track | outcome=spotify_not_authenticated")
        return auth_err

    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    err = await _device_warmup_simple(client, device_id, client.next_track)
    if err is not None:
        logger.warning(f"mcp_tool_call: spotify_next_track | outcome={err['error']}")
        return err

    logger.info("mcp_tool_call: spotify_next_track | outcome=ok")
    return {"ok": True}


@register_tool(
    name="spotify_previous_track",
    description=(
        "Skip to the previous track or restart the current track in Spotify. Omit "
        "device_id to target the current JARVIS HUD device or the last active Spotify "
        "Connect device."
    ),
    schema={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": (
                    "Spotify Connect device ID; omit to use the JARVIS HUD device "
                    "or the last active device."
                ),
            },
        },
        "required": [],
    },
)
async def spotify_previous_track(device_id: str | None = None) -> dict[str, Any]:
    """Skip to the previous track or restart the current track."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info(
            "mcp_tool_call: spotify_previous_track | outcome=spotify_not_authenticated"
        )
        return auth_err

    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    err = await _device_warmup_simple(client, device_id, client.previous_track)
    if err is not None:
        logger.warning(f"mcp_tool_call: spotify_previous_track | outcome={err['error']}")
        return err

    logger.info("mcp_tool_call: spotify_previous_track | outcome=ok")
    return {"ok": True}


@register_tool(
    name="spotify_seek",
    description=(
        "Seek to a specific position within the currently playing Spotify track. "
        "position_ms is the target position in milliseconds (0 = start of track). "
        "Omit device_id to target the current JARVIS HUD device or the last active "
        "Spotify Connect device."
    ),
    schema={
        "type": "object",
        "properties": {
            "position_ms": {
                "type": "integer",
                "minimum": 0,
                "description": "Target position in milliseconds within the current track.",
            },
            "device_id": {
                "type": "string",
                "description": (
                    "Spotify Connect device ID; omit to use the JARVIS HUD device "
                    "or the last active device."
                ),
            },
        },
        "required": ["position_ms"],
    },
)
async def spotify_seek(
    position_ms: int,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Seek to a position in milliseconds within the current Spotify track."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info("mcp_tool_call: spotify_seek | outcome=spotify_not_authenticated")
        return auth_err

    resolved_device_id = device_id or ws_server.get_spotify_device_id()
    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    err = await _play_with_device_warmup(
        client,
        resolved_device_id,
        lambda: client.seek(position_ms, device_id=resolved_device_id),
    )
    if err is not None:
        logger.warning(
            f"mcp_tool_call: spotify_seek | position_ms={position_ms} | "
            f"outcome={err['error']}"
        )
        return err

    logger.info(f"mcp_tool_call: spotify_seek | position_ms={position_ms} | outcome=ok")
    return {"ok": True, "position_ms": position_ms}


@register_tool(
    name="spotify_set_volume",
    description=(
        "Set the Spotify playback volume to a specific percentage (0–100). Use this "
        "for 'louder', 'quieter', or explicit volume commands. To adjust relative to "
        "current volume, first call spotify_get_current_playback to read the current "
        "volume, then compute the new value and call this tool. Omit device_id to "
        "target the current JARVIS HUD device or the last active Spotify Connect device."
    ),
    schema={
        "type": "object",
        "properties": {
            "volume_percent": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Desired volume level (0 = mute, 100 = maximum).",
            },
            "device_id": {
                "type": "string",
                "description": (
                    "Spotify Connect device ID; omit to use the JARVIS HUD device "
                    "or the last active device."
                ),
            },
        },
        "required": ["volume_percent"],
    },
)
async def spotify_set_volume(
    volume_percent: int,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Set the Spotify playback volume to the given percentage (0–100)."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info("mcp_tool_call: spotify_set_volume | outcome=spotify_not_authenticated")
        return auth_err

    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    # Clamp to valid range before forwarding.
    volume_percent = max(0, min(100, volume_percent))

    err = await _device_warmup_simple(
        client,
        device_id,
        lambda: client.set_volume(volume_percent),
    )
    if err is not None:
        logger.warning(
            f"mcp_tool_call: spotify_set_volume | pct={volume_percent} | "
            f"outcome={err['error']}"
        )
        return err

    logger.info(f"mcp_tool_call: spotify_set_volume | pct={volume_percent} | outcome=ok")
    return {"ok": True, "volume_percent": volume_percent}


@register_tool(
    name="spotify_set_shuffle",
    description=(
        "Enable or disable Spotify shuffle mode. When state is true, tracks play in "
        "random order; when false, they play in sequence. Omit device_id to target the "
        "current JARVIS HUD device or the last active Spotify Connect device."
    ),
    schema={
        "type": "object",
        "properties": {
            "state": {
                "type": "boolean",
                "description": "True to enable shuffle, false to disable.",
            },
            "device_id": {
                "type": "string",
                "description": (
                    "Spotify Connect device ID; omit to use the JARVIS HUD device "
                    "or the last active device."
                ),
            },
        },
        "required": ["state"],
    },
)
async def spotify_set_shuffle(
    state: bool,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Enable or disable Spotify shuffle mode."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info("mcp_tool_call: spotify_set_shuffle | outcome=spotify_not_authenticated")
        return auth_err

    resolved_device_id = device_id or ws_server.get_spotify_device_id()
    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    err = await _play_with_device_warmup(
        client,
        resolved_device_id,
        lambda: client.set_shuffle(state, device_id=resolved_device_id),
    )
    if err is not None:
        logger.warning(
            f"mcp_tool_call: spotify_set_shuffle | state={state} | "
            f"outcome={err['error']}"
        )
        return err

    logger.info(f"mcp_tool_call: spotify_set_shuffle | state={state} | outcome=ok")
    return {"ok": True, "shuffle": state}


@register_tool(
    name="spotify_set_repeat",
    description=(
        "Set the Spotify repeat mode. 'off' disables repeat entirely; 'track' repeats "
        "the current track indefinitely; 'context' repeats the current playlist or album. "
        "Omit device_id to target the current JARVIS HUD device or the last active "
        "Spotify Connect device."
    ),
    schema={
        "type": "object",
        "properties": {
            "state": {
                "type": "string",
                "enum": ["off", "track", "context"],
                "description": "Repeat mode: 'off', 'track', or 'context'.",
            },
            "device_id": {
                "type": "string",
                "description": (
                    "Spotify Connect device ID; omit to use the JARVIS HUD device "
                    "or the last active device."
                ),
            },
        },
        "required": ["state"],
    },
)
async def spotify_set_repeat(
    state: str,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Set the Spotify repeat mode to 'off', 'track', or 'context'."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info("mcp_tool_call: spotify_set_repeat | outcome=spotify_not_authenticated")
        return auth_err

    resolved_device_id = device_id or ws_server.get_spotify_device_id()
    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    # ValueError from invalid state is not a device-warmup candidate — propagate directly.
    try:
        err = await _play_with_device_warmup(
            client,
            resolved_device_id,
            lambda: client.set_repeat(state, device_id=resolved_device_id),
        )
    except ValueError as exc:
        logger.warning(f"mcp_tool_call: spotify_set_repeat | invalid state={state!r}: {exc}")
        return {
            "ok": False,
            "error": "spotify_api_error",
            "detail": str(exc)[:200],
        }

    if err is not None:
        logger.warning(
            f"mcp_tool_call: spotify_set_repeat | state={state!r} | "
            f"outcome={err['error']}"
        )
        return err

    logger.info(f"mcp_tool_call: spotify_set_repeat | state={state!r} | outcome=ok")
    return {"ok": True, "repeat": state}


@register_tool(
    name="spotify_search",
    description=(
        "Search the Spotify catalogue for tracks, albums, artists, and/or playlists. "
        "Returns ranked results in each requested category. Use this before "
        "spotify_play_uris when the user wants to play a specific track by name/artist "
        "rather than a playlist. The query is capped at 200 characters."
    ),
    schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Free-text search query (artist, track title, album name, etc.).",
            },
            "types": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["track", "album", "artist", "playlist"],
                },
                "description": (
                    "Categories to search. Defaults to all four types when omitted."
                ),
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum results per type (default 10).",
            },
        },
        "required": ["query"],
    },
)
async def spotify_search(
    query: str,
    types: list[str] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search the Spotify catalogue for tracks, albums, artists, and playlists."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info("mcp_tool_call: spotify_search | outcome=spotify_not_authenticated")
        return auth_err

    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    # Cap query length per spec.
    query = query[:200]

    search_types = types or ["track", "album", "artist", "playlist"]
    limit = max(1, min(50, limit))

    try:
        results = await client.search(query, types=search_types, limit=limit)
    except Exception as exc:
        err = _map_exception(exc)
        logger.warning(
            f"mcp_tool_call: spotify_search | query_len={len(query)} | "
            f"outcome={err['error']}"
        )
        return err

    tracks = [
        {"name": t.name, "artist": t.artist, "album": t.album, "uri": t.uri}
        for t in results.tracks
    ]
    playlists = [
        {"name": p.name, "owner": p.owner, "uri": p.uri}
        for p in results.playlists
    ]

    logger.info(
        f"mcp_tool_call: spotify_search | query_len={len(query)} | "
        f"tracks={len(tracks)} playlists={len(playlists)} | outcome=ok"
    )
    return {
        "ok": True,
        "tracks": tracks,
        "artists": results.artists,
        "albums": results.albums,
        "playlists": playlists,
    }


@register_tool(
    name="spotify_add_to_queue",
    description=(
        "Add a Spotify track or episode URI to the end of the current playback queue. "
        "Spotify requires an active playback session; if nothing is playing this will "
        "return an error. Omit device_id to target the current JARVIS HUD device or "
        "the last active Spotify Connect device."
    ),
    schema={
        "type": "object",
        "properties": {
            "uri": {
                "type": "string",
                "description": "Spotify URI to enqueue (e.g. 'spotify:track:<id>').",
            },
            "device_id": {
                "type": "string",
                "description": (
                    "Spotify Connect device ID; omit to use the JARVIS HUD device "
                    "or the last active device."
                ),
            },
        },
        "required": ["uri"],
    },
)
async def spotify_add_to_queue(
    uri: str,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Add a track or episode URI to the end of the Spotify playback queue."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info("mcp_tool_call: spotify_add_to_queue | outcome=spotify_not_authenticated")
        return auth_err

    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    err = await _device_warmup_simple(
        client,
        device_id,
        lambda: client.add_to_queue(uri),
    )
    if err is not None:
        logger.warning(
            f"mcp_tool_call: spotify_add_to_queue | uri={uri!r} | "
            f"outcome={err['error']}"
        )
        return err

    logger.info(f"mcp_tool_call: spotify_add_to_queue | uri={uri!r} | outcome=ok")
    return {"ok": True, "queued_uri": uri}


@register_tool(
    name="spotify_get_current_playback",
    description=(
        "Return the current Spotify playback state including track name, artist, album, "
        "progress, duration, volume, shuffle, repeat mode, and device name. Returns "
        "{'ok': true, 'playing': false} when no playback is active. Use this to read "
        "the current volume before computing a relative volume adjustment."
    ),
    schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def spotify_get_current_playback() -> dict[str, Any]:
    """Return the current Spotify playback state."""
    auth_err = _check_client()
    if auth_err is not None:
        logger.info(
            "mcp_tool_call: spotify_get_current_playback | "
            "outcome=spotify_not_authenticated"
        )
        return auth_err

    client = ws_server.get_spotify_client()
    if client is None:
        return _auth_error_response()

    try:
        state = await client.get_playback_state()
    except Exception as exc:
        err = _map_exception(exc)
        logger.warning(
            f"mcp_tool_call: spotify_get_current_playback | outcome={err['error']}"
        )
        return err

    if state is None:
        logger.info("mcp_tool_call: spotify_get_current_playback | outcome=ok (not playing)")
        return {"ok": True, "playing": False}

    logger.info(
        f"mcp_tool_call: spotify_get_current_playback | "
        f"track={state.name!r} | outcome=ok"
    )
    return {
        "ok": True,
        "playing": state.is_playing,
        "track_name": state.name,
        "artist": state.artist,
        "album": state.album,
        "progress_ms": state.progress_ms,
        "duration_ms": state.duration_ms,
        "shuffle": state.shuffle,
        "repeat": state.repeat,
        "device_name": state.device_name,
    }
