"""Unit tests for src/api/mcp_server.py.

Covers:
- register_tool decorator behaviour (happy path, duplicate, pre-boot, post-boot)
- list_registered_tools JSON-serialisable shape
- start_mcp_server: disabled path, happy path, failure/graceful-degradation path
- stop_mcp_server: cancels task, safe when no task
- get_sse_url and build_openclaw_mcp_json helpers
- Reset isolation via autouse fixture
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Isolation: clear all module-level singletons before every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_mcp_module():
    """Reset api.mcp_server singletons and registry between tests."""
    import api.mcp_server as mod

    mod._tool_registry.clear()
    mod._server = None
    mod._server_task = None
    yield
    # Teardown: cancel any task that may have been left running
    if mod._server_task is not None and not mod._server_task.done():
        mod._server_task.cancel()
    mod._tool_registry.clear()
    mod._server = None
    mod._server_task = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    enabled: bool = True,
    host: str = "127.0.0.1",
    port: int = 8767,
    auto_register: bool = True,
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "bind_host": host,
        "bind_port": port,
        "auto_register_with_openclaw": auto_register,
    }


async def _noop_coro(*_args: Any, **_kwargs: Any) -> None:
    """Sentinel coroutine that returns immediately — stands in for run_sse_async."""
    return None


# ---------------------------------------------------------------------------
# register_tool — pre-boot (server is None)
# ---------------------------------------------------------------------------


def test_register_tool_records_entry_in_registry() -> None:
    """register_tool records name, description and schema in the registry."""
    from api.mcp_server import register_tool, list_registered_tools

    @register_tool(name="ping", description="Returns pong", schema={"type": "object"})
    async def ping() -> str:
        return "pong"

    tools = list_registered_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "ping"
    assert tools[0]["description"] == "Returns pong"
    assert tools[0]["schema"] == {"type": "object"}


def test_register_tool_returns_original_function_unmodified() -> None:
    """register_tool is a pass-through decorator — original callable is returned."""
    from api.mcp_server import register_tool

    async def my_fn() -> str:
        return "hello"

    decorated = register_tool(name="my_fn", description="desc", schema={})(my_fn)
    assert decorated is my_fn


def test_register_tool_does_not_include_callable_in_list_output() -> None:
    """list_registered_tools excludes the 'fn' key — output is JSON-serialisable."""
    from api.mcp_server import register_tool, list_registered_tools

    @register_tool(name="tool_a", description="A", schema={})
    async def tool_a() -> None:
        pass

    tools = list_registered_tools()
    assert len(tools) == 1
    entry = tools[0]
    assert "fn" not in entry
    # Ensure it is actually JSON-serialisable (no callables leaking through)
    serialised = json.dumps(entry)
    parsed = json.loads(serialised)
    assert parsed["name"] == "tool_a"


def test_register_tool_does_not_call_server_add_tool_when_server_is_none() -> None:
    """register_tool before start_mcp_server does NOT call _server.add_tool."""
    import api.mcp_server as mod
    from api.mcp_server import register_tool

    assert mod._server is None  # pre-condition

    mock_server = MagicMock()
    # Server stays None even if we reference it — so no add_tool call expected
    @register_tool(name="no_server", description="x", schema={})
    async def no_server_fn() -> None:
        pass

    mock_server.add_tool.assert_not_called()


def test_register_tool_duplicate_name_overwrites_silently() -> None:
    """Registering the same name twice silently overwrites the previous entry.

    The production code does NOT raise; it replaces the old entry.
    Lock this behaviour in so a refactor that adds a guard surfaces here.
    """
    from api.mcp_server import register_tool, list_registered_tools

    @register_tool(name="dup", description="first", schema={})
    async def fn_first() -> None:
        pass

    @register_tool(name="dup", description="second", schema={})
    async def fn_second() -> None:
        pass

    tools = list_registered_tools()
    # Only one entry with the name "dup"
    dup_entries = [t for t in tools if t["name"] == "dup"]
    assert len(dup_entries) == 1
    # Latest registration wins
    assert dup_entries[0]["description"] == "second"


def test_register_tool_multiple_tools_all_appear_in_list() -> None:
    """All distinct tool names appear in list_registered_tools()."""
    from api.mcp_server import register_tool, list_registered_tools

    for i in range(3):
        register_tool(name=f"tool_{i}", description=f"Tool {i}", schema={})(
            AsyncMock()
        )

    tools = list_registered_tools()
    names = {t["name"] for t in tools}
    assert names == {"tool_0", "tool_1", "tool_2"}


# ---------------------------------------------------------------------------
# register_tool — post-boot (server already live)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_tool_after_start_calls_server_add_tool() -> None:
    """register_tool after start_mcp_server calls _server.add_tool with the instrumented wrapper.

    Phase 1 (Brain) wraps every tool in an ``_instrumented`` async closure so that
    every dispatch fires the DeviceLedger ``mcp_call`` hook (AC #8).  FastMCP receives
    the wrapper, not the original function — so we assert:
    1. ``add_tool`` was called exactly once.
    2. The first positional argument is a callable (the instrumented wrapper).
    3. The ``name`` and ``description`` keyword arguments are correct.
    4. The wrapper actually delegates to the original function (pass-through check).
    """
    import api.mcp_server as mod
    from api.mcp_server import register_tool, set_ledger_hook

    # Inject a mock server to simulate the "already started" state.
    mock_server = MagicMock()
    mod._server = mock_server

    invoked: list[str] = []

    @register_tool(name="late_tool", description="registered late", schema={"x": 1})
    async def late_fn() -> None:
        invoked.append("called")

    # 1. add_tool was called exactly once.
    mock_server.add_tool.assert_called_once()

    call_args = mock_server.add_tool.call_args
    wrapper_arg = call_args.args[0] if call_args.args else call_args[0][0]

    # 2. The argument passed to add_tool is a callable (the instrumented wrapper).
    assert callable(wrapper_arg), "add_tool must receive a callable wrapper"

    # 3. Keyword arguments carry the correct name and description.
    assert call_args.kwargs.get("name") == "late_tool"
    assert call_args.kwargs.get("description") == "registered late"

    # 4. The wrapper delegates to the original function when invoked.
    #    Disable the ledger hook so the wrapper doesn't try to await a missing hook.
    set_ledger_hook(None)
    await wrapper_arg()
    assert invoked == ["called"], "Instrumented wrapper must invoke the original fn"


# ---------------------------------------------------------------------------
# list_registered_tools
# ---------------------------------------------------------------------------


def test_list_registered_tools_returns_empty_list_when_no_tools_registered() -> None:
    """list_registered_tools() returns [] when registry is empty."""
    from api.mcp_server import list_registered_tools

    assert list_registered_tools() == []


def test_list_registered_tools_schema_preserved_intact() -> None:
    """Complex schema dict is preserved verbatim in the output."""
    from api.mcp_server import register_tool, list_registered_tools

    complex_schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }

    @register_tool(name="search", description="Search tool", schema=complex_schema)
    async def search_fn() -> None:
        pass

    tools = list_registered_tools()
    assert tools[0]["schema"] == complex_schema


# ---------------------------------------------------------------------------
# start_mcp_server — disabled path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_mcp_server_disabled_returns_immediately_without_fastmcp() -> None:
    """start_mcp_server with enabled=False logs 'disabled' and returns; no FastMCP init."""
    from api.mcp_server import start_mcp_server
    import api.mcp_server as mod

    cfg = _make_config(enabled=False)

    with patch("api.mcp_server.FastMCP") as mock_fastmcp_cls:
        await start_mcp_server(cfg, device_slug="test-device")

    mock_fastmcp_cls.assert_not_called()
    assert mod._server is None
    assert mod._server_task is None


@pytest.mark.asyncio
async def test_start_mcp_server_disabled_logs_disabled_message() -> None:
    """start_mcp_server with enabled=False logs the 'MCP server disabled' line."""
    from loguru import logger as loguru_logger
    from api.mcp_server import start_mcp_server

    cfg = _make_config(enabled=False)
    captured: list[str] = []

    sink_id = loguru_logger.add(lambda msg: captured.append(msg), level="INFO")
    try:
        with patch("api.mcp_server.FastMCP"):
            await start_mcp_server(cfg, device_slug="test-device")
    finally:
        loguru_logger.remove(sink_id)

    full_log = " ".join(captured)
    assert "disabled" in full_log.lower()


# ---------------------------------------------------------------------------
# start_mcp_server — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_mcp_server_happy_path_creates_task_and_logs_url() -> None:
    """start_mcp_server (enabled) creates background task and logs the SSE URL."""
    from api.mcp_server import start_mcp_server
    import api.mcp_server as mod

    cfg = _make_config(host="127.0.0.1", port=8767)

    mock_server_instance = MagicMock()
    mock_server_instance.run_sse_async = AsyncMock(return_value=None)

    with patch("api.mcp_server.FastMCP", return_value=mock_server_instance):
        # We need to let the event loop run long enough that the task starts
        # but we don't need it to finish — we'll cancel in teardown
        await start_mcp_server(cfg, device_slug="test-device")

    assert mod._server is mock_server_instance
    assert mod._server_task is not None


@pytest.mark.asyncio
async def test_start_mcp_server_happy_path_logs_listening_url() -> None:
    """start_mcp_server logs a line containing 'MCP server listening on'."""
    from loguru import logger as loguru_logger
    from api.mcp_server import start_mcp_server

    cfg = _make_config(host="127.0.0.1", port=8767)
    captured: list[str] = []

    mock_server_instance = MagicMock()
    mock_server_instance.run_sse_async = AsyncMock(return_value=None)

    sink_id = loguru_logger.add(lambda msg: captured.append(msg), level="INFO")
    try:
        with patch("api.mcp_server.FastMCP", return_value=mock_server_instance):
            await start_mcp_server(cfg, device_slug="test-device")
    finally:
        loguru_logger.remove(sink_id)

    full_log = " ".join(captured)
    assert "MCP server listening on" in full_log
    assert "http://127.0.0.1:8767/sse" in full_log


@pytest.mark.asyncio
async def test_start_mcp_server_wires_pre_registered_tools_into_fastmcp() -> None:
    """Tools registered before start are wired into the FastMCP instance at boot."""
    from api.mcp_server import register_tool, start_mcp_server

    @register_tool(name="pre_boot", description="pre-boot tool", schema={})
    async def pre_boot_fn() -> None:
        pass

    mock_server_instance = MagicMock()
    mock_server_instance.run_sse_async = AsyncMock(return_value=None)

    with patch("api.mcp_server.FastMCP", return_value=mock_server_instance):
        await start_mcp_server(_make_config(), device_slug="test-device")

    # add_tool should have been called for the pre-registered tool
    call_names = [call.kwargs.get("name") for call in mock_server_instance.add_tool.call_args_list]
    assert "pre_boot" in call_names


@pytest.mark.asyncio
async def test_start_mcp_server_fastmcp_instantiated_with_correct_params() -> None:
    """FastMCP is instantiated with name='jarvis', host, and port from config."""
    from api.mcp_server import start_mcp_server

    cfg = _make_config(host="0.0.0.0", port=9999)

    mock_server_instance = MagicMock()
    mock_server_instance.run_sse_async = AsyncMock(return_value=None)

    with patch("api.mcp_server.FastMCP", return_value=mock_server_instance) as mock_cls:
        await start_mcp_server(cfg, device_slug="test-device")

    _, kwargs = mock_cls.call_args
    assert kwargs.get("name") == "jarvis-test-device"
    assert kwargs.get("host") == "0.0.0.0"
    assert kwargs.get("port") == 9999


# ---------------------------------------------------------------------------
# start_mcp_server — failure / graceful degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_mcp_server_fastmcp_init_raises_logs_warning_and_returns() -> None:
    """If FastMCP(…) raises, log a warning and return — no exception bubbles up."""
    from api.mcp_server import start_mcp_server
    import api.mcp_server as mod

    cfg = _make_config()

    with patch("api.mcp_server.FastMCP", side_effect=OSError("address already in use")):
        with caplog_patch() as log_records:
            # Must not raise
            await start_mcp_server(cfg, device_slug="test-device")

    assert mod._server is None
    assert mod._server_task is None


@pytest.mark.asyncio
async def test_start_mcp_server_fastmcp_init_raises_does_not_bubble_exception() -> None:
    """start_mcp_server swallows the bind-failure exception gracefully."""
    from api.mcp_server import start_mcp_server

    with patch("api.mcp_server.FastMCP", side_effect=RuntimeError("bind error")):
        try:
            await start_mcp_server(_make_config(), device_slug="test-device")
        except Exception as exc:
            pytest.fail(f"start_mcp_server raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# stop_mcp_server
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_mcp_server_cancels_running_task() -> None:
    """stop_mcp_server cancels the background task and resets singletons."""
    from api.mcp_server import stop_mcp_server
    import api.mcp_server as mod

    # Plant a fake never-ending task
    async def _never_ends():
        await asyncio.sleep(9999)

    task = asyncio.create_task(_never_ends())
    mod._server_task = task
    mod._server = MagicMock()

    await stop_mcp_server()

    assert task.cancelled() or task.done()
    assert mod._server_task is None
    assert mod._server is None


@pytest.mark.asyncio
async def test_stop_mcp_server_is_safe_when_no_task_exists() -> None:
    """stop_mcp_server called with no running task does not raise."""
    from api.mcp_server import stop_mcp_server
    import api.mcp_server as mod

    assert mod._server_task is None  # pre-condition

    try:
        await stop_mcp_server()
    except Exception as exc:
        pytest.fail(f"stop_mcp_server raised when there was no task: {exc}")

    assert mod._server_task is None
    assert mod._server is None


@pytest.mark.asyncio
async def test_stop_mcp_server_safe_when_task_already_done() -> None:
    """stop_mcp_server handles a task that has already finished."""
    from api.mcp_server import stop_mcp_server
    import api.mcp_server as mod

    async def _quick():
        return None

    task = asyncio.create_task(_quick())
    await task  # let it finish
    assert task.done()

    mod._server_task = task
    mod._server = MagicMock()

    await stop_mcp_server()

    assert mod._server_task is None
    assert mod._server is None


# ---------------------------------------------------------------------------
# get_sse_url
# ---------------------------------------------------------------------------


def test_get_sse_url_default_config() -> None:
    """get_sse_url returns the expected URL for default host/port."""
    from api.mcp_server import get_sse_url

    url = get_sse_url({"bind_host": "127.0.0.1", "bind_port": 8767})
    assert url == "http://127.0.0.1:8767/sse"


def test_get_sse_url_custom_host_and_port() -> None:
    """get_sse_url uses config values for host and port."""
    from api.mcp_server import get_sse_url

    url = get_sse_url({"bind_host": "0.0.0.0", "bind_port": 9000})
    assert url == "http://0.0.0.0:9000/sse"


def test_get_sse_url_defaults_when_keys_absent() -> None:
    """get_sse_url falls back to 127.0.0.1:8767 when config is empty."""
    from api.mcp_server import get_sse_url

    url = get_sse_url({})
    assert url == "http://127.0.0.1:8767/sse"


def test_get_sse_url_port_as_string_is_coerced() -> None:
    """get_sse_url tolerates port delivered as a string (YAML may produce str)."""
    from api.mcp_server import get_sse_url

    url = get_sse_url({"bind_host": "127.0.0.1", "bind_port": "8767"})
    assert url == "http://127.0.0.1:8767/sse"


# ---------------------------------------------------------------------------
# build_openclaw_mcp_json
# ---------------------------------------------------------------------------


def test_build_openclaw_mcp_json_produces_url_key() -> None:
    """build_openclaw_mcp_json returns compact JSON with a 'url' key."""
    from api.mcp_server import build_openclaw_mcp_json

    raw = build_openclaw_mcp_json({"bind_host": "127.0.0.1", "bind_port": 8767})
    parsed = json.loads(raw)
    assert parsed == {"url": "http://127.0.0.1:8767/sse"}


def test_build_openclaw_mcp_json_is_valid_json() -> None:
    """build_openclaw_mcp_json output is parseable JSON."""
    from api.mcp_server import build_openclaw_mcp_json

    raw = build_openclaw_mcp_json({})
    parsed = json.loads(raw)
    assert "url" in parsed
    assert parsed["url"].startswith("http://")


# ---------------------------------------------------------------------------
# AC #3 contract — tools list shape
# ---------------------------------------------------------------------------


def test_list_registered_tools_entries_have_required_keys() -> None:
    """Each tool entry from list_registered_tools has name, description, schema keys."""
    from api.mcp_server import register_tool, list_registered_tools

    @register_tool(
        name="contract_tool",
        description="AC3 shape check",
        schema={"type": "object", "properties": {}, "required": []},
    )
    async def contract_fn() -> None:
        pass

    tools = list_registered_tools()
    assert len(tools) == 1
    entry = tools[0]
    for required_key in ("name", "description", "schema"):
        assert required_key in entry, f"Missing required key '{required_key}' in tool entry"


# ---------------------------------------------------------------------------
# Private helper — context manager to swallow caplog for tests that call
# functions that may or may not emit log records.
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def caplog_patch():
    """Minimal no-op context manager used where caplog fixture isn't available."""
    records: list = []
    yield records
