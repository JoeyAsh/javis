"""MCP tool registrations for JARVIS.

Importing this package causes every sub-module to execute its
``@register_tool`` decorators, populating the ``_tool_registry`` in
``api.mcp_server`` before the FastMCP server announces its tool list.

Tool naming convention: flat snake_case with a namespace prefix, e.g.
``github_list_my_prs``.  OpenClaw sees the prefix as the namespace.
The Spotify namespace (#58) is intentionally absent here and will be
added in a separate PR.
"""

from api.mcp_tools import (  # noqa: F401
    github_tools,
    gitlab_tools,
    pc_control_tools,
    smart_home_tools,
    system_tools,
)

__all__ = [
    "github_tools",
    "gitlab_tools",
    "pc_control_tools",
    "smart_home_tools",
    "system_tools",
]
