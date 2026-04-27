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
import logging
import socket
import sys
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from utils.device import load_device_identity, resolve_advertise_host
from utils.logger import get_logger

logger = get_logger("mcp_server")


def _strip_rich_handler() -> None:
    """Remove RichHandler instances that FastMCP.__init__ attaches.

    The intercept is already installed via setup_logger; once Rich is
    gone, all MCP log lines flow through loguru.
    """
    try:
        from rich.logging import RichHandler  # noqa: PLC0415
    except ImportError:
        return  # Rich isn't installed — nothing to strip
    root = logging.getLogger()
    before = len(root.handlers)
    root.handlers = [h for h in root.handlers if not isinstance(h, RichHandler)]
    removed = before - len(root.handlers)
    logger.debug(f"FastMCP RichHandler stripped (removed={removed})")


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

# Device context set at start_mcp_server time — used by the device://info resource.
_device_slug: str = "jarvis"
_device_sse_url: str = ""


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


async def start_mcp_server(config: dict[str, Any], device_slug: str) -> None:
    """Start the MCP SSE server and wire the tool registry into FastMCP.

    Reads ``mcp.enabled``, ``mcp.bind_host``, ``mcp.bind_port``.  If
    ``enabled`` is ``False`` the function returns immediately after a log
    message.  Any bind error is caught and logged as a warning so the JARVIS
    boot sequence continues even when the MCP port is unavailable.

    The server is named ``jarvis-{device_slug}`` so the MCP ``serverInfo.name``
    field identifies this instance uniquely to the OpenClaw agent runtime.

    This function does **not** block; the uvicorn server runs inside a
    background ``asyncio.Task`` stored in ``_server_task``.

    Args:
        config: The ``mcp`` section from ``config.yaml``.
        device_slug: Sanitized device identifier (e.g. ``"laptop-paps"``).
    """
    global _server, _server_task, _device_slug, _device_sse_url

    if not config.get("enabled", True):
        logger.info("MCP server disabled (mcp.enabled: false)")
        return

    _device_slug = device_slug

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
    advertise_host: str = resolve_advertise_host(config)

    # Resolve the advertised SSE URL now (used in device://info resource).
    _device_sse_url = f"http://{advertise_host}:{bind_port}/sse"

    mcp_name = f"jarvis-{device_slug}"
    instructions = (
        f"JARVIS MCP tools — host: {device_slug} ({sys.platform}). "
        "Route device-specific tools to this server."
    )

    logger.info(
        f"Starting MCP server '{mcp_name}' on {bind_host}:{bind_port} "
        f"(SSE transport, advertise: {advertise_host})..."
    )

    # If the advertise host differs from bind host (Tailscale scenario), try
    # binding on the advertise host; fall back to bind_host on socket errors.
    effective_bind = advertise_host if advertise_host != bind_host else bind_host

    try:
        _server = FastMCP(
            name=mcp_name,
            instructions=instructions,
            host=effective_bind,
            port=bind_port,
            log_level="WARNING",  # suppress uvicorn noise; loguru handles JARVIS logs
        )
        _strip_rich_handler()

        # Register the device://info resource so the OpenClaw agent can query
        # identity on demand via the standard MCP resources/read protocol.
        _register_device_info_resource(_server, device_slug, bind_port)

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
            f"MCP server listening on http://{effective_bind}:{bind_port}/sse "
            f"(name={mcp_name!r}, SSE transport)"
        )

    except OSError as exc:
        if effective_bind != bind_host:
            logger.error(
                f"MCP server failed to bind on {effective_bind}:{bind_port} — "
                f"falling back to {bind_host}: {exc}"
            )
            try:
                _server = FastMCP(
                    name=mcp_name,
                    instructions=instructions,
                    host=bind_host,
                    port=bind_port,
                    log_level="WARNING",
                )
                _strip_rich_handler()
                _register_device_info_resource(_server, device_slug, bind_port)
                for entry in _tool_registry.values():
                    _server.add_tool(
                        entry["fn"],
                        name=entry["name"],
                        description=entry["description"],
                    )
                _server_task = asyncio.create_task(
                    _run_server_task(_server),
                    name="mcp-server",
                )
                logger.info(
                    f"MCP server listening on http://{bind_host}:{bind_port}/sse "
                    f"(fallback bind, name={mcp_name!r})"
                )
            except Exception as fallback_exc:  # noqa: BLE001
                logger.warning(
                    f"MCP server failed to start on fallback bind — "
                    f"JARVIS will continue without MCP: {fallback_exc}"
                )
                _server = None
                _server_task = None
        else:
            logger.warning(
                f"MCP server failed to start — JARVIS will continue without MCP: {exc}"
            )
            _server = None
            _server_task = None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"MCP server failed to start — JARVIS will continue without MCP: {exc}"
        )
        _server = None
        _server_task = None


def _register_device_info_resource(
    server: FastMCP,
    device_slug: str,
    bind_port: int,
) -> None:
    """Register the ``device://info`` MCP resource on ``server``.

    Args:
        server: The FastMCP instance to register the resource on.
        device_slug: Sanitized device slug for this instance.
        bind_port: The MCP server port (for constructing the SSE URL).
    """

    @server.resource("device://info", mime_type="application/json")
    async def device_info_resource() -> str:
        """Return device identity JSON for the OpenClaw agent."""
        identity = load_device_identity()
        device_id: str = identity.get("deviceId", identity.get("id", ""))
        mcp_server_name = f"jarvis-{_device_slug}"
        payload = {
            "slug": _device_slug,
            "platform": sys.platform,
            "hostname": socket.gethostname(),
            "deviceId": device_id,
            "mcpServerName": mcp_server_name,
            "sseUrl": _device_sse_url,
        }
        return json.dumps(payload)


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
# SSE URL helpers
# ---------------------------------------------------------------------------


def get_sse_url(config: dict[str, Any]) -> str:
    """Return the full SSE endpoint URL using the bind host for this MCP server.

    Args:
        config: The ``mcp`` section from ``config.yaml``.

    Returns:
        URL string such as ``http://127.0.0.1:8767/sse``.
    """
    host: str = config.get("bind_host", "127.0.0.1")
    port: int = int(config.get("bind_port", 8767))
    return f"http://{host}:{port}/sse"


def get_sse_advertise_url(config: dict[str, Any]) -> str:
    """Return the advertised SSE endpoint URL for MCP registration with OpenClaw.

    Uses ``resolve_advertise_host`` (env var → config key → bind_host) so the
    URL reflects the Tailscale IP or MagicDNS hostname when configured.

    Args:
        config: The ``mcp`` section from ``config.yaml``.

    Returns:
        URL string such as ``http://laptop-paps.tailnet.ts.net:8767/sse``.
    """
    host: str = resolve_advertise_host(config)
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
    return json.dumps({"url": get_sse_advertise_url(config)})
