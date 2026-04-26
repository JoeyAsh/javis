"""Shared fixtures for api/mcp_tools tests.

The most important duty of this conftest is the autouse ``reset_tool_registry``
fixture: it clears ``api.mcp_server._tool_registry`` before every test and
force-reloads every mcp_tools sub-module after the clear, so each test starts
from a known, fully-populated (or intentionally empty) state.  Without this
guard, @register_tool decorators that run at import time would pollute all
subsequent tests in the same session.
"""

from __future__ import annotations

import importlib
import sys

import pytest


@pytest.fixture(autouse=True)
def reset_tool_registry():
    """Clear the MCP tool registry and reload tool modules before each test.

    Steps:
    1.  Clear ``_tool_registry`` (so stale registrations from a previous test
        cannot leak in).
    2.  Force-reload all ``api.mcp_tools.*`` sub-modules so their
        ``@register_tool`` decorators fire again against the now-empty
        registry.
    3.  Yield (test runs).
    4.  Clear registry again on teardown (belt-and-braces).
    """
    import api.mcp_server as mcp_server_mod

    # --- Setup ---
    mcp_server_mod._tool_registry.clear()
    mcp_server_mod._server = None
    mcp_server_mod._server_task = None

    # Reload each sub-module so decorators fire freshly.
    _submodule_names = [
        "api.mcp_tools.github_tools",
        "api.mcp_tools.gitlab_tools",
        "api.mcp_tools.smart_home_tools",
        "api.mcp_tools.pc_control_tools",
        "api.mcp_tools.system_tools",
        "api.mcp_tools",
    ]
    for name in _submodule_names:
        if name in sys.modules:
            importlib.reload(sys.modules[name])

    # If not yet imported, just do a fresh import to populate the registry.
    import api.mcp_tools  # noqa: F401

    yield

    # --- Teardown ---
    mcp_server_mod._tool_registry.clear()
    mcp_server_mod._server = None
    mcp_server_mod._server_task = None
