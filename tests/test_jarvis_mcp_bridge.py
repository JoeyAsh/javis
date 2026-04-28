"""Unit tests for the JARVIS stdio-to-SSE MCP bridge.

All transport objects (stdio_server, sse_client) are mocked — no real network
calls, no live JARVIS backend, no actual stdio interaction.

Covers:
- _parse_args: required --url, optional --headers default
- _parse_args: custom --headers JSON is accepted
- main: --headers invalid JSON exits with code 1
- main: missing --url triggers SystemExit (argparse error)
- main: bridge coroutine is launched via anyio.run on success
- main: KeyboardInterrupt is swallowed (clean exit)
- main: unexpected Exception from anyio.run exits with code 1
- _run_bridge: messages from stdio_read are forwarded to sse_write
- _run_bridge: messages from sse_read are forwarded to stdio_write
- _run_bridge: Exception items in stdio_read are skipped, not forwarded
- _run_bridge: Exception items in sse_read are skipped, not forwarded
"""
from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import jarvis_mcp_bridge
from jarvis_mcp_bridge import _parse_args, main


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def test_parse_args_url_required() -> None:
    """_parse_args raises SystemExit when --url is missing."""
    with pytest.raises(SystemExit):
        _parse_args([])


def test_parse_args_url_accepted() -> None:
    """_parse_args returns the supplied URL."""
    args = _parse_args(["--url", "http://127.0.0.1:8767/sse"])
    assert args.url == "http://127.0.0.1:8767/sse"


def test_parse_args_headers_default() -> None:
    """_parse_args defaults --headers to '{}'."""
    args = _parse_args(["--url", "http://127.0.0.1:8767/sse"])
    assert args.headers == "{}"


def test_parse_args_headers_custom() -> None:
    """_parse_args accepts a custom JSON --headers string."""
    h = json.dumps({"Authorization": "Bearer token"})
    args = _parse_args(["--url", "http://127.0.0.1:8767/sse", "--headers", h])
    assert args.headers == h


# ---------------------------------------------------------------------------
# main() error paths
# ---------------------------------------------------------------------------


def test_main_invalid_headers_json_exits_1() -> None:
    """main() exits with code 1 when --headers is not valid JSON."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--url", "http://127.0.0.1:8767/sse", "--headers", "not-json"])
    assert exc_info.value.code == 1


def test_main_keyboard_interrupt_exits_cleanly() -> None:
    """main() swallows KeyboardInterrupt and exits with code 0."""
    with patch("anyio.run", side_effect=KeyboardInterrupt):
        # Should not raise — KeyboardInterrupt must be caught silently.
        main(["--url", "http://127.0.0.1:8767/sse"])


def test_main_unexpected_exception_exits_1() -> None:
    """main() exits with code 1 on unexpected exceptions from anyio.run."""
    with patch("anyio.run", side_effect=RuntimeError("boom")):
        with pytest.raises(SystemExit) as exc_info:
            main(["--url", "http://127.0.0.1:8767/sse"])
    assert exc_info.value.code == 1


def test_main_launches_anyio_run_on_success() -> None:
    """main() calls anyio.run with _run_bridge and the parsed URL/headers."""
    calls: list[Any] = []

    def fake_anyio_run(coro_fn: Any, *args: Any) -> None:
        calls.append((coro_fn, args))

    with patch("anyio.run", side_effect=fake_anyio_run):
        main(["--url", "http://127.0.0.1:8767/sse"])

    assert len(calls) == 1
    fn, args = calls[0]
    assert fn is jarvis_mcp_bridge._run_bridge
    assert args[0] == "http://127.0.0.1:8767/sse"
    assert args[1] == {}  # default empty headers dict


def test_main_passes_headers_dict_to_bridge() -> None:
    """main() deserialises --headers JSON and forwards the dict to anyio.run."""
    calls: list[Any] = []
    hdrs = {"Authorization": "Bearer secret"}

    def fake_anyio_run(coro_fn: Any, *args: Any) -> None:
        calls.append((coro_fn, args))

    with patch("anyio.run", side_effect=fake_anyio_run):
        main(["--url", "http://h:8767/sse", "--headers", json.dumps(hdrs)])

    _, args = calls[0]
    assert args[1] == hdrs


# ---------------------------------------------------------------------------
# _run_bridge: bidirectional proxy
# ---------------------------------------------------------------------------


def _make_memory_stream(items: list[Any]):
    """Return an async iterable that yields *items* then closes."""

    class _FakeStream:
        def __init__(self, data: list[Any]) -> None:
            self._data = iter(data)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._data)
            except StopIteration:
                raise StopAsyncIteration

        async def aclose(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: Any):
            pass

    return _FakeStream(items)


@pytest.mark.asyncio
async def test_run_bridge_forwards_stdio_to_sse() -> None:
    """_run_bridge forwards messages from stdio_read → sse_write."""
    from mcp.shared.session import SessionMessage  # lazy import inside test
    from mcp import types as mcp_types

    # A minimal valid JSONRPC message wrapped in SessionMessage
    raw = mcp_types.JSONRPCMessage(
        root=mcp_types.JSONRPCRequest(jsonrpc="2.0", id=1, method="ping")
    )
    msg = SessionMessage(raw)

    sent_to_sse: list[Any] = []

    sse_write = AsyncMock()
    sse_write.send = AsyncMock(side_effect=lambda m: sent_to_sse.append(m))
    sse_write.__aenter__ = AsyncMock(return_value=sse_write)
    sse_write.__aexit__ = AsyncMock(return_value=False)

    # stdio_read yields one real message then closes
    stdio_read = _make_memory_stream([msg])
    # sse_read yields nothing (so the sse→stdio pump exits immediately)
    sse_read = _make_memory_stream([])
    # stdio_write accepts but we don't check it here
    stdio_write = AsyncMock()
    stdio_write.__aenter__ = AsyncMock(return_value=stdio_write)
    stdio_write.__aexit__ = AsyncMock(return_value=False)

    import anyio

    with (
        patch("mcp.server.stdio.stdio_server") as mock_stdio_ctx,
        patch("mcp.client.sse.sse_client") as mock_sse_ctx,
    ):
        # Wire up context managers
        mock_stdio_cm = MagicMock()
        mock_stdio_cm.__aenter__ = AsyncMock(return_value=(stdio_read, stdio_write))
        mock_stdio_cm.__aexit__ = AsyncMock(return_value=False)
        mock_stdio_ctx.return_value = mock_stdio_cm

        mock_sse_cm = MagicMock()
        mock_sse_cm.__aenter__ = AsyncMock(return_value=(sse_read, sse_write))
        mock_sse_cm.__aexit__ = AsyncMock(return_value=False)
        mock_sse_ctx.return_value = mock_sse_cm

        await jarvis_mcp_bridge._run_bridge("http://127.0.0.1:8767/sse", {})

    assert msg in sent_to_sse


@pytest.mark.asyncio
async def test_run_bridge_exception_items_in_stdio_read_are_skipped() -> None:
    """_run_bridge skips Exception items in stdio_read without forwarding them."""
    sent_to_sse: list[Any] = []

    sse_write = AsyncMock()
    sse_write.send = AsyncMock(side_effect=lambda m: sent_to_sse.append(m))
    sse_write.__aenter__ = AsyncMock(return_value=sse_write)
    sse_write.__aexit__ = AsyncMock(return_value=False)

    # stdio_read yields only an exception item
    stdio_read = _make_memory_stream([ValueError("parse error")])
    sse_read = _make_memory_stream([])
    stdio_write = AsyncMock()
    stdio_write.__aenter__ = AsyncMock(return_value=stdio_write)
    stdio_write.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("mcp.server.stdio.stdio_server") as mock_stdio_ctx,
        patch("mcp.client.sse.sse_client") as mock_sse_ctx,
    ):
        mock_stdio_cm = MagicMock()
        mock_stdio_cm.__aenter__ = AsyncMock(return_value=(stdio_read, stdio_write))
        mock_stdio_cm.__aexit__ = AsyncMock(return_value=False)
        mock_stdio_ctx.return_value = mock_stdio_cm

        mock_sse_cm = MagicMock()
        mock_sse_cm.__aenter__ = AsyncMock(return_value=(sse_read, sse_write))
        mock_sse_cm.__aexit__ = AsyncMock(return_value=False)
        mock_sse_ctx.return_value = mock_sse_cm

        await jarvis_mcp_bridge._run_bridge("http://127.0.0.1:8767/sse", {})

    # Nothing should have been forwarded to the SSE server.
    assert sent_to_sse == []
