"""JARVIS MCP stdio-to-SSE bridge.

The OpenClaw acpx plugin (which drives the Claude agent runtime) only accepts
stdio-transport MCP servers (``command/args/env`` shape).  JARVIS runs its MCP
server over SSE (``http://<host>:8767/sse``), which acpx rejects at validation
time with "Invalid MCP configuration: ... Does not adhere to MCP server
configuration schema".

This module is the bridge: acpx launches it as a subprocess
(``python -m jarvis_mcp_bridge --url http://...``), it connects to the running
JARVIS SSE server and proxies all JSON-RPC frames bidirectionally over stdin/
stdout.  The SSE server continues to exist unchanged so any other consumer
(curl, direct inspection) keeps working.

Usage (by OpenClaw / acpx — never called manually):

    python -m jarvis_mcp_bridge --url http://127.0.0.1:8767/sse
    python -m jarvis_mcp_bridge --url http://host:8767/sse --headers '{"Authorization":"Bearer tok"}'

The process exits when either stdin closes or the SSE connection drops.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

import anyio

# Suppress noisy httpx / anyio debug lines that would corrupt the stdio channel.
logging.disable(logging.WARNING)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the bridge process."""
    parser = argparse.ArgumentParser(
        prog="jarvis_mcp_bridge",
        description="Proxy stdio JSON-RPC ↔ JARVIS SSE MCP server.",
        add_help=True,
    )
    parser.add_argument(
        "--url",
        required=True,
        metavar="SSE_URL",
        help="SSE endpoint of the JARVIS MCP server (e.g. http://127.0.0.1:8767/sse).",
    )
    parser.add_argument(
        "--headers",
        default="{}",
        metavar="JSON",
        help='Optional JSON object of HTTP headers forwarded to the SSE server.',
    )
    return parser.parse_args(argv)


async def _run_bridge(sse_url: str, extra_headers: dict[str, Any]) -> None:
    """Open both transports and pump messages bidirectionally until EOF.

    Args:
        sse_url: The JARVIS MCP SSE endpoint.
        extra_headers: HTTP headers to attach to the SSE handshake request.
    """
    from mcp.client.sse import sse_client  # noqa: PLC0415
    from mcp.server.stdio import stdio_server  # noqa: PLC0415

    async with stdio_server() as (stdio_read, stdio_write):
        async with sse_client(url=sse_url, headers=extra_headers or None) as (
            sse_read,
            sse_write,
        ):
            async with anyio.create_task_group() as tg:
                # Forward messages from the acpx caller (stdio) → JARVIS SSE server.
                async def _stdio_to_sse() -> None:
                    """Pump acpx → JARVIS."""
                    async with sse_write:
                        async for message in stdio_read:
                            if isinstance(message, Exception):
                                # Parse error from stdio — log to stderr and skip.
                                sys.stderr.write(
                                    f"jarvis_mcp_bridge: parse error from stdin: {message}\n"
                                )
                                sys.stderr.flush()
                                continue
                            await sse_write.send(message)

                # Forward responses from JARVIS SSE server → acpx caller (stdio).
                async def _sse_to_stdio() -> None:
                    """Pump JARVIS → acpx."""
                    async with stdio_write:
                        async for message in sse_read:
                            if isinstance(message, Exception):
                                sys.stderr.write(
                                    f"jarvis_mcp_bridge: error from SSE server: {message}\n"
                                )
                                sys.stderr.flush()
                                continue
                            await stdio_write.send(message)

                tg.start_soon(_stdio_to_sse)
                tg.start_soon(_sse_to_stdio)


def main(argv: list[str] | None = None) -> None:
    """Entry point: parse args and run the bridge."""
    args = _parse_args(argv)

    try:
        headers: dict[str, Any] = json.loads(args.headers)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"jarvis_mcp_bridge: --headers is not valid JSON: {exc}\n")
        sys.exit(1)

    try:
        anyio.run(_run_bridge, args.url, headers)
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"jarvis_mcp_bridge: fatal error: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
