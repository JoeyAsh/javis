"""MCP tool registrations for the narration/notification namespace.

Registers three MCP tools that let background agents (Claude Code, etc.) push
notifications and status updates to the JARVIS narration queue:

  - ``jarvis_notify``          — enqueue a NarrationItem.
  - ``jarvis_set_status``      — coalesce per-source progress.
  - ``jarvis_set_quiet_mode``  — toggle quiet mode.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from api.mcp_server import register_tool
from utils.logger import get_logger

logger = get_logger("mcp_tools.narration")


def _get_narration_queue() -> Any:
    """Return the process-wide NarrationQueue from ws_server, or None."""
    try:
        from api.ws_server import get_narration_queue  # noqa: PLC0415

        return get_narration_queue()
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# jarvis_notify
# ---------------------------------------------------------------------------

_NOTIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Short title for the notification / narration item.",
        },
        "body": {
            "type": "string",
            "description": "Optional longer body text. When provided it is "
            "appended to the title with a colon separator.",
        },
        "severity": {
            "type": "string",
            "enum": ["info", "update", "urgent", "completion"],
            "description": (
                "Routing severity: info=HUD only; update=HUD+(optional voice); "
                "urgent=voice+HUD, bypasses quiet mode; completion=voice+HUD, batched."
            ),
        },
        "source": {
            "type": "string",
            "description": "Caller identifier used for rate limiting and batching "
            "(e.g. 'claude-code-91'). Optional.",
        },
        "ttl_seconds": {
            "type": "integer",
            "description": "Seconds until the item expires (0 = never).",
            "minimum": 0,
        },
    },
    "required": ["title"],
}


@register_tool(
    name="jarvis_notify",
    description=(
        "File a notification into the JARVIS narration queue. "
        "The item is narrated aloud (when voice-eligible and JARVIS is idle) "
        "and shown on the HUD activity panel immediately."
    ),
    schema=_NOTIFY_SCHEMA,
)
async def jarvis_notify(
    title: str,
    body: str | None = None,
    severity: str = "update",
    source: str | None = None,
    ttl_seconds: int = 0,
) -> dict[str, Any]:
    """Enqueue a NarrationItem from an external MCP caller.

    Args:
        title: Short notification title.
        body: Optional additional detail appended to title.
        severity: ``info``, ``update``, ``urgent``, or ``completion``.
        source: Optional caller identifier for rate limiting and batching.
        ttl_seconds: Item lifetime in seconds (0 = no expiry).

    Returns:
        Dict with ``item_id``, ``queued_at`` (ISO 8601), and ``channels``.
    """
    valid_severities = {"info", "update", "urgent", "completion"}
    if severity not in valid_severities:
        severity = "update"

    text = f"{title}: {body}" if body else title

    queue = _get_narration_queue()
    if queue is None:
        logger.warning("jarvis_notify: NarrationQueue not available — item dropped")
        return {
            "item_id": f"narr-{uuid.uuid4().hex[:8]}",
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "channels": [],
            "error": "NarrationQueue not initialised",
        }

    item_id = queue.enqueue(
        text=text,
        severity=severity,  # type: ignore[arg-type]
        source=source,
        ttl_seconds=float(ttl_seconds),
    )
    channels = queue._resolve_channels(severity)  # type: ignore[arg-type]

    logger.info(
        f"MCP jarvis_notify: [{severity}] {item_id!r}"
        + (f" source={source!r}" if source else "")
    )
    return {
        "item_id": item_id,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "channels": channels,
    }


# ---------------------------------------------------------------------------
# jarvis_set_status
# ---------------------------------------------------------------------------

_SET_STATUS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "source": {
            "type": "string",
            "description": "Caller / task identifier (e.g. 'claude-code-91').",
        },
        "status": {
            "type": "string",
            "enum": ["starting", "in_progress", "done", "blocked"],
            "description": "Current status of the background task.",
        },
        "message": {
            "type": "string",
            "description": "Optional human-readable status detail.",
        },
    },
    "required": ["source", "status"],
}


@register_tool(
    name="jarvis_set_status",
    description=(
        "Update the per-source progress status shown in the JARVIS HUD activity panel. "
        "Replaces any prior status from the same source. Does not enqueue a voice item."
    ),
    schema=_SET_STATUS_SCHEMA,
)
async def jarvis_set_status(
    source: str,
    status: str,
    message: str | None = None,
) -> dict[str, Any]:
    """Coalesce per-source progress status into the narration queue.

    Args:
        source: Unique caller identifier.
        status: One of ``starting``, ``in_progress``, ``done``, ``blocked``.
        message: Optional human-readable detail.

    Returns:
        Dict with ``source`` and ``prior_status`` (None if first update).
    """
    valid_statuses = {"starting", "in_progress", "done", "blocked"}
    if status not in valid_statuses:
        status = "in_progress"

    queue = _get_narration_queue()
    if queue is None:
        logger.warning("jarvis_set_status: NarrationQueue not available")
        return {"source": source, "prior_status": None, "error": "NarrationQueue not initialised"}

    prior = queue.set_source_status(
        source=source,
        status=status,  # type: ignore[arg-type]
        message=message,
    )
    prior_status: str | None = prior.status if prior is not None else None

    logger.info(f"MCP jarvis_set_status: source={source!r} → {status!r}")
    return {"source": source, "prior_status": prior_status}


# ---------------------------------------------------------------------------
# jarvis_set_quiet_mode
# ---------------------------------------------------------------------------

_SET_QUIET_MODE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "enabled": {
            "type": "boolean",
            "description": "True to enable quiet mode, False to disable it.",
        },
        "duration_minutes": {
            "type": "integer",
            "description": "How long to stay quiet (minutes). "
            "Omit to use the configured default (60 min).",
            "minimum": 1,
        },
    },
    "required": ["enabled"],
}


@register_tool(
    name="jarvis_set_quiet_mode",
    description=(
        "Enable or disable JARVIS quiet mode. While active, all narration items route "
        "to HUD only — except 'urgent' which still plays voice with a soft pre-roll. "
        "Enabling while already quiet replaces the timer (no stacking)."
    ),
    schema=_SET_QUIET_MODE_SCHEMA,
)
async def jarvis_set_quiet_mode(
    enabled: bool,
    duration_minutes: int | None = None,
) -> dict[str, Any]:
    """Toggle JARVIS quiet mode.

    Args:
        enabled: True to enter quiet mode, False to leave it.
        duration_minutes: Duration in minutes (None = use configured default).

    Returns:
        Dict with ``quiet_until`` (ISO 8601 string or None).
    """
    queue = _get_narration_queue()
    if queue is None:
        logger.warning("jarvis_set_quiet_mode: NarrationQueue not available")
        return {"quiet_until": None, "error": "NarrationQueue not initialised"}

    quiet_until = queue.set_quiet_mode(enabled=enabled, duration_minutes=duration_minutes)
    quiet_until_iso: str | None = quiet_until.isoformat() if quiet_until is not None else None

    logger.info(
        f"MCP jarvis_set_quiet_mode: enabled={enabled} quiet_until={quiet_until_iso}"
    )
    return {"quiet_until": quiet_until_iso}
