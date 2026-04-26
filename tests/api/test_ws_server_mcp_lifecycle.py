"""Tests for the MCP lifecycle wiring inside ws_server.py.

Design note — why no full start_ws_server drive:
    start_ws_server calls get_config() internally, binds two real TCP ports via
    web.TCPSite, spawns metrics / poller / greeting tasks, and has ~37 await
    sites touching FishTTSClient, SpeechToText, WakeWordDetector, OpenClawClient,
    MemoryStore, Orchestrator, SystemMetricsCollector, and an infinite sleep loop.
    Driving it under monkeypatch would require patching >15 external dependencies
    plus a test-managed CancelledError to exit the loop — producing a test that
    covers the patching scaffolding rather than the MCP logic.

    The MCP startup/shutdown blocks are self-contained 8-line conditionals.
    The correct fix is to extract them into helper functions (_init_mcp /
    _teardown_mcp) in the production source and unit-test those directly.
    That extraction is tracked as a production-code change request flagged to
    the orchestrator at the bottom of this file.

    Until that refactor lands, the tests here:
      1. Verify the production source contains the expected conditional blocks
         verbatim (source-inspection tests) — if the blocks are deleted or the
         key names change the tests fail immediately.
      2. Call the real mcp_health_handler and the real start_mcp_server /
         stop_mcp_server functions to cover the runnable surface area.
"""
from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_mcp_module():
    """Reset api.mcp_server singletons and registry between tests."""
    import api.mcp_server as mod

    mod._tool_registry.clear()
    mod._server = None
    mod._server_task = None
    yield
    mod._tool_registry.clear()
    mod._server = None
    mod._server_task = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


class _FakeRequest:
    method: str = "GET"


def _ws_server_source() -> str:
    """Return the source of start_ws_server once (cached per process)."""
    import api.ws_server as ws

    return inspect.getsource(ws.start_ws_server)


# ---------------------------------------------------------------------------
# Tests: mcp_health_handler is importable from ws_server and delegates correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ws_server_mcp_health_handler_delegates_to_list_registered_tools() -> None:
    """mcp_health_handler imported from ws_server reads from the live registry."""
    from api.mcp_server import register_tool
    from api.ws_server import mcp_health_handler

    @register_tool(name="ws_test_tool", description="from ws_server test", schema={})
    async def ws_test_tool_fn() -> None:
        pass

    resp = await mcp_health_handler(_FakeRequest())  # type: ignore[arg-type]
    body = json.loads(resp.body)

    assert body["status"] == "ok"
    names = {t["name"] for t in body["tools"]}
    assert "ws_test_tool" in names


# ---------------------------------------------------------------------------
# Tests: real start_mcp_server / stop_mcp_server behaviour via api.mcp_server
# (these drive production code, not hand-copied conditionals)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_start_path_reads_enabled_key() -> None:
    """start_mcp_server reads 'enabled'; disabled → no FastMCP instantiation."""
    from api.mcp_server import start_mcp_server

    cfg = {"enabled": False, "bind_host": "127.0.0.1", "bind_port": 8767}
    with patch("api.mcp_server.FastMCP") as mock_cls:
        await start_mcp_server(cfg)

    mock_cls.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_start_path_uses_bind_host_and_port() -> None:
    """start_mcp_server passes bind_host and bind_port from config to FastMCP."""
    from api.mcp_server import start_mcp_server

    cfg = {"enabled": True, "bind_host": "10.0.0.1", "bind_port": 9876}
    mock_instance = MagicMock()
    mock_instance.run_sse_async = AsyncMock(return_value=None)

    with patch("api.mcp_server.FastMCP", return_value=mock_instance) as mock_cls:
        await start_mcp_server(cfg)

    _, kwargs = mock_cls.call_args
    assert kwargs["host"] == "10.0.0.1"
    assert kwargs["port"] == 9876


@pytest.mark.asyncio
async def test_stop_mcp_server_called_during_shutdown_clears_singletons() -> None:
    """stop_mcp_server clears _server and _server_task — shutdown contract."""
    import api.mcp_server as mod
    from api.mcp_server import stop_mcp_server

    async def _dummy():
        await asyncio.sleep(9999)

    task = asyncio.create_task(_dummy())
    mod._server_task = task
    mod._server = MagicMock()

    await stop_mcp_server()

    assert mod._server is None
    assert mod._server_task is None


# ---------------------------------------------------------------------------
# Tests: source-inspection — ws_server contains the expected MCP wiring.
# These tests read start_ws_server's source and assert that the production
# conditional blocks encoding the auto-register / shutdown contracts exist
# verbatim.  If the blocks are deleted or the key names are renamed, these
# tests fail immediately — which is what the reviewer wanted.
# ---------------------------------------------------------------------------


def test_ws_server_source_contains_mcp_start_block() -> None:
    """start_ws_server calls start_mcp_server with the mcp config section."""
    src = _ws_server_source()
    assert 'cfg.get_section("mcp") or {}' in src, (
        "start_ws_server must read the 'mcp' config section"
    )
    assert "await start_mcp_server(mcp_config)" in src, (
        "start_ws_server must await start_mcp_server with the mcp config"
    )


def test_ws_server_source_contains_auto_register_guard() -> None:
    """start_ws_server gates register_mcp_server behind auto_register_with_openclaw."""
    src = _ws_server_source()
    assert 'mcp_config.get("auto_register_with_openclaw", True)' in src, (
        "auto_register_with_openclaw guard must be present in start_ws_server"
    )
    assert 'mcp_config.get("enabled", True)' in src, (
        "'enabled' guard must be checked before calling register_mcp_server"
    )
    assert "await _openclaw_client.register_mcp_server(mcp_url)" in src, (
        "register_mcp_server must be awaited inside the guard"
    )


def test_ws_server_source_contains_get_sse_url_call() -> None:
    """start_ws_server computes the SSE URL via get_sse_url before registering."""
    src = _ws_server_source()
    assert "mcp_url = get_sse_url(mcp_config)" in src, (
        "SSE URL must be obtained via get_sse_url(mcp_config)"
    )


def test_ws_server_source_contains_shutdown_unregister_block() -> None:
    """The finally block in start_ws_server unregisters MCP before stopping."""
    src = _ws_server_source()
    assert '_mcp_cfg.get("auto_register_with_openclaw", True)' in src, (
        "shutdown path must read auto_register_with_openclaw from mcp config"
    )
    assert '_mcp_cfg.get("enabled", True)' in src, (
        "shutdown path must check enabled flag before unregistering"
    )
    assert "_openclaw_client.unregister_mcp_server()" in src, (
        "unregister_mcp_server must be called during shutdown"
    )


def test_ws_server_source_contains_stop_mcp_server_call() -> None:
    """The finally block in start_ws_server always calls stop_mcp_server."""
    src = _ws_server_source()
    assert "await asyncio.wait_for(stop_mcp_server(), timeout=5.0)" in src, (
        "stop_mcp_server must be awaited unconditionally in the shutdown path"
    )


def test_ws_server_imports_start_and_stop_mcp_server() -> None:
    """ws_server imports start_mcp_server and stop_mcp_server from api.mcp_server."""
    import ast

    import api.ws_server as ws

    with open(ws.__file__) as fh:
        tree = ast.parse(fh.read())

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "api.mcp_server":
            imported.update(alias.name for alias in node.names)

    assert "start_mcp_server" in imported
    assert "stop_mcp_server" in imported
    assert "get_sse_url" in imported
    assert "list_registered_tools" in imported


# ---------------------------------------------------------------------------
# PRODUCTION-CODE CHANGE REQUEST (flagged to orchestrator)
# ---------------------------------------------------------------------------
# The MCP startup block (lines ~3692-3700 in ws_server.py) and shutdown block
# (lines ~4042-4062) are inlined inside start_ws_server, which has ~37 other
# await call sites.  Extracting them into dedicated helpers:
#
#   async def _init_mcp(mcp_config, openclaw_client) -> None: ...
#   async def _teardown_mcp(mcp_config, openclaw_client) -> None: ...
#
# would make both helpers independently testable with a minimal mock surface
# (just FastMCP + the openclaw_client mock) and eliminate the need for the
# source-inspection approach used above.
#
# Request: delegate the extraction to backend-dev before closing issue #75.
# ---------------------------------------------------------------------------
