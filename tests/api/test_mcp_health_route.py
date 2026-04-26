"""Unit tests for the GET /api/mcp/health route handler.

Uses a minimal aiohttp web.Application (no full ws_server bootstrap) and a
FakeRequest pattern identical to the one used by test_config_repos.py.

Covers:
- Empty registry → {"status": "ok", "tools": []}
- One registered tool → tool appears in the tools array
- AC #3 contract: each tool dict has name, description, schema keys
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Minimal aiohttp Request fake
# (No transport needed — mcp_health_handler does not check IP)
# ---------------------------------------------------------------------------


class _FakeRequest:
    """Minimal stand-in for aiohttp.web.Request."""

    method: str = "GET"


# ---------------------------------------------------------------------------
# Isolation: reset mcp_server singletons before each test
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
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_health_handler_empty_registry_returns_ok_with_empty_tools() -> None:
    """GET /api/mcp/health with empty registry returns 200 {status:ok, tools:[]}."""
    from api.ws_server import mcp_health_handler

    req = _FakeRequest()
    resp = await mcp_health_handler(req)  # type: ignore[arg-type]

    assert resp.status == 200
    body = json.loads(resp.body)
    assert body["status"] == "ok"
    assert body["tools"] == []


@pytest.mark.asyncio
async def test_mcp_health_handler_with_one_tool_returns_tool_in_list() -> None:
    """GET /api/mcp/health with one registered tool includes it in 'tools' array."""
    from api.mcp_server import register_tool
    from api.ws_server import mcp_health_handler

    @register_tool(
        name="my_tool",
        description="Does something useful",
        schema={"type": "object", "properties": {}, "required": []},
    )
    async def my_tool() -> None:
        pass

    req = _FakeRequest()
    resp = await mcp_health_handler(req)  # type: ignore[arg-type]

    assert resp.status == 200
    body = json.loads(resp.body)
    assert body["status"] == "ok"
    assert len(body["tools"]) == 1
    assert body["tools"][0]["name"] == "my_tool"


@pytest.mark.asyncio
async def test_mcp_health_handler_tool_entry_has_required_keys() -> None:
    """Each tool dict in the health response has name, description, schema keys (AC #3)."""
    from api.mcp_server import register_tool
    from api.ws_server import mcp_health_handler

    schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}

    @register_tool(name="ac3_tool", description="AC3 contract check", schema=schema)
    async def ac3_fn() -> None:
        pass

    req = _FakeRequest()
    resp = await mcp_health_handler(req)  # type: ignore[arg-type]

    body = json.loads(resp.body)
    entry = body["tools"][0]
    assert entry["name"] == "ac3_tool"
    assert entry["description"] == "AC3 contract check"
    assert entry["schema"] == schema
    # Callable must NOT leak through
    assert "fn" not in entry


@pytest.mark.asyncio
async def test_mcp_health_handler_multiple_tools_all_appear() -> None:
    """With multiple registered tools all are present in the health response."""
    from api.mcp_server import register_tool
    from api.ws_server import mcp_health_handler

    for i in range(3):
        register_tool(
            name=f"tool_{i}",
            description=f"Tool number {i}",
            schema={},
        )(lambda: None)

    req = _FakeRequest()
    resp = await mcp_health_handler(req)  # type: ignore[arg-type]

    body = json.loads(resp.body)
    names = {t["name"] for t in body["tools"]}
    assert names == {"tool_0", "tool_1", "tool_2"}


@pytest.mark.asyncio
async def test_mcp_health_handler_response_is_valid_json() -> None:
    """mcp_health_handler always returns parseable JSON."""
    from api.ws_server import mcp_health_handler

    req = _FakeRequest()
    resp = await mcp_health_handler(req)  # type: ignore[arg-type]

    # This should not raise
    body = json.loads(resp.body)
    assert isinstance(body, dict)
