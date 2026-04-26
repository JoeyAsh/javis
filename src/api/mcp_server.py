"""MCP server bootstrap for JARVIS.

Wraps the official MCP Python SDK (FastMCP) and exposes JARVIS-native capabilities
to the OpenClaw agent runtime over SSE transport on a loopback TCP port.

Phase 3 — infrastructure only.  No tools are registered here.
Phase 4 (issue #76) and Spotify (issue #58) will import ``register_tool`` and
populate the registry.

Transport choice: SSE (HTTP Server-Sent Events) via FastMCP's built-in uvicorn
runner.  The SSE endpoint is ``http://<host>:<port>/sse``; the message post-back
endpoint is ``http://<host>:<port>/messages/``.  OpenClaw registers this server
as ``{"url": "http://<host>:<port>/sse"}`` in its MCP config, which matches its
SSE transport shape documented in ``D:/Repos/openclaw/docs/cli/mcp.md``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from utils.logger import get_logger

logger = get_logger("mcp_server")

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_server: FastMCP | None = None
_server_task: asyncio.Task[None] | None = None

# Registry keyed by tool name.  Populated by @register_tool before the server
# starts.  The FastMCP instance is configured with the same functions at
# start_mcp_server time, so this dict is the single source of truth for
# list_registered_tools().
_tool_registry: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Public decorator
# ---------------------------------------------------------------------------


def register_tool(
    name: str,
    description: str,
    schema: dict[str, Any],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that records an async tool function in the in-process registry.

    The decorated function is stored alongside its metadata so that
    ``start_mcp_server`` can wire it into the live FastMCP instance at boot
    time.  Tools registered **after** ``start_mcp_server`` has been called will
    be added directly to the running server as well.

    Args:
        name: Unique tool name (snake_case, no spaces).
        description: Human-readable description shown to the LLM.
        schema: JSON-Schema-style ``inputSchema`` dict describing the tool's
            parameters.  Pass ``{}`` for tools that take no arguments.

    Returns:
        The original function unmodified (decorator pass-through).

    Example::

        @register_tool(
            name="ping",
            description="Returns pong",
            schema={"type": "object", "properties": {}, "required": []},
        )
        async def ping() -> str:
            return "pong"
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in _tool_registry:
            logger.warning(
                f"register_tool: name {name!r} is already registered — overwriting previous entry"
            )
        entry: dict[str, Any] = {
            "name": name,
            "description": description,
            "schema": schema,
            "fn": fn,
        }
        _tool_registry[name] = entry
        logger.debug(f"MCP tool registered in registry: {name!r}")

        # If the server is already running, add the tool live.
        if _server is not None:
            _server.add_tool(fn, name=name, description=description)
            logger.debug(f"MCP tool wired into live FastMCP instance: {name!r}")

        return fn

    return decorator


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


async def start_mcp_server(config: dict[str, Any]) -> None:
    """Start the MCP SSE server and wire the tool registry into FastMCP.

    Reads ``mcp.enabled``, ``mcp.bind_host``, ``mcp.bind_port``.  If
    ``enabled`` is ``False`` the function returns immediately after a log
    message.  Any bind error is caught and logged as a warning so the JARVIS
    boot sequence continues even when the MCP port is unavailable.

    This function does **not** block; the uvicorn server runs inside a
    background ``asyncio.Task`` stored in ``_server_task``.

    Args:
        config: The ``mcp`` section from ``config.yaml``.
    """
    global _server, _server_task

    if not config.get("enabled", True):
        logger.info("MCP server disabled (mcp.enabled: false)")
        return

    # ---------------------------------------------------------------------------
    # Phase-4 tool registrations (issue #76).
    # Import triggers all @register_tool decorators so the registry is fully
    # populated before FastMCP reads it below.  Placed here (lazy import) to
    # avoid a circular-import between api.mcp_server and api.mcp_tools at
    # module-init time.  Spotify tools (#58) land in a separate PR.
    # ---------------------------------------------------------------------------
    try:
        import api.mcp_tools  # noqa: F401, PLC0415
    except Exception as _mcp_tools_exc:  # noqa: BLE001
        logger.error(
            f"Failed to import api.mcp_tools — MCP tools will not be registered: "
            f"{_mcp_tools_exc}"
        )

    bind_host: str = config.get("bind_host", "127.0.0.1")
    bind_port: int = int(config.get("bind_port", 8767))

    logger.info(f"Starting MCP server on {bind_host}:{bind_port} (SSE transport)...")

    try:
        _server = FastMCP(
            name="jarvis",
            host=bind_host,
            port=bind_port,
            log_level="WARNING",  # suppress uvicorn noise; loguru handles JARVIS logs
        )

        # Wire all tools that were registered before the server started.
        for entry in _tool_registry.values():
            _server.add_tool(
                entry["fn"],
                name=entry["name"],
                description=entry["description"],
            )
            logger.debug(f"MCP tool wired into FastMCP at startup: {entry['name']!r}")

        # Run the SSE server in a background task so we don't block the caller.
        _server_task = asyncio.create_task(
            _run_server_task(_server),
            name="mcp-server",
        )

        logger.info(
            f"MCP server listening on http://{bind_host}:{bind_port}/sse (SSE transport)"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"MCP server failed to start — JARVIS will continue without MCP: {exc}"
        )
        _server = None
        _server_task = None


async def _run_server_task(server: FastMCP) -> None:
    """Background coroutine that runs the FastMCP SSE uvicorn server."""
    try:
        await server.run_sse_async()
    except asyncio.CancelledError:
        logger.info("MCP server task cancelled — shutting down")
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(f"MCP server task crashed: {exc}")


async def stop_mcp_server() -> None:
    """Cancel the MCP server background task and clean up singletons.

    Safe to call even when the server was never started or already stopped.
    """
    global _server, _server_task

    if _server_task is not None and not _server_task.done():
        _server_task.cancel()
        try:
            await _server_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        logger.info("MCP server stopped")

    _server_task = None
    _server = None


# ---------------------------------------------------------------------------
# Introspection helper
# ---------------------------------------------------------------------------


def list_registered_tools() -> list[dict[str, Any]]:
    """Return a JSON-serialisable snapshot of the current tool registry.

    Each item contains ``name``, ``description``, and ``schema``.  The
    callable (``fn``) is excluded from the output.

    Returns:
        List of tool metadata dicts, one per registered tool.
    """
    return [
        {
            "name": entry["name"],
            "description": entry["description"],
            "schema": entry["schema"],
        }
        for entry in _tool_registry.values()
    ]


# ---------------------------------------------------------------------------
# SSE URL helper
# ---------------------------------------------------------------------------


def get_sse_url(config: dict[str, Any]) -> str:
    """Return the full SSE endpoint URL for this MCP server.

    Args:
        config: The ``mcp`` section from ``config.yaml``.

    Returns:
        URL string such as ``http://127.0.0.1:8767/sse``.
    """
    host: str = config.get("bind_host", "127.0.0.1")
    port: int = int(config.get("bind_port", 8767))
    return f"http://{host}:{port}/sse"


# ---------------------------------------------------------------------------
# OpenClaw registration JSON helper
# ---------------------------------------------------------------------------


def build_openclaw_mcp_json(config: dict[str, Any]) -> str:
    """Return the JSON string suitable for ``openclaw mcp set jarvis <json>``.

    Produces ``{"url": "<sse_url>"}`` which OpenClaw's SSE transport shape
    expects (see ``D:/Repos/openclaw/docs/cli/mcp.md``, section
    "SSE / HTTP transport").

    Args:
        config: The ``mcp`` section from ``config.yaml``.

    Returns:
        Compact JSON string.
    """
    return json.dumps({"url": get_sse_url(config)})
