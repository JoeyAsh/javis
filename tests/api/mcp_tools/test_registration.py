"""Tests for MCP tool registration integrity (Phase 4 / issue #76).

Verifies:
- After importing api.mcp_tools, list_registered_tools() returns exactly the
  15 tool names promised by the spec.
- Each tool entry carries non-empty name, description, and schema fields.
- Each tool's schema is valid JSON Schema (object type with a properties dict
  and an optional required list).
- list_registered_tools() output is JSON-serialisable.
"""

from __future__ import annotations

import json
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Expected tool set
# ---------------------------------------------------------------------------

EXPECTED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        # GitHub (4)
        "github_list_my_prs",
        "github_list_repo_issues",
        "github_get_pr_details",
        "github_get_ci_status",
        # GitLab (3)
        "gitlab_list_my_mrs",
        "gitlab_list_pipelines",
        "gitlab_get_pipeline_details",
        # Smart Home (3)
        "smart_home_list_entities",
        "smart_home_call_service",
        "smart_home_get_state",
        # PC Control (4)
        "pc_control_launch_app",
        "pc_control_set_volume",
        "pc_control_screenshot",
        "pc_control_focus_window",
        # System (1)
        "system_get_metrics",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tools() -> list[dict[str, Any]]:
    """Return the current tool list (autouse fixture already reloaded modules)."""
    from api.mcp_server import list_registered_tools

    return list_registered_tools()


# ---------------------------------------------------------------------------
# Test: exact tool set
# ---------------------------------------------------------------------------


def test_registration_returns_exactly_15_tools():
    """list_registered_tools() returns exactly 15 tools after full import."""
    tools = _get_tools()
    assert len(tools) == 15, (
        f"Expected 15 tools, got {len(tools)}: {sorted(t['name'] for t in tools)}"
    )


def test_registration_returns_expected_tool_names():
    """list_registered_tools() names match the Phase-4 spec exactly (set comparison)."""
    tools = _get_tools()
    actual_names = {t["name"] for t in tools}
    assert actual_names == EXPECTED_TOOL_NAMES, (
        f"Missing: {EXPECTED_TOOL_NAMES - actual_names}; "
        f"Unexpected: {actual_names - EXPECTED_TOOL_NAMES}"
    )


# ---------------------------------------------------------------------------
# Test: each entry has required non-empty metadata
# ---------------------------------------------------------------------------


def test_each_tool_has_non_empty_name():
    """Every registered tool entry has a non-empty 'name' field."""
    for tool in _get_tools():
        assert isinstance(tool["name"], str) and tool["name"].strip(), (
            f"Tool has empty/missing name: {tool!r}"
        )


def test_each_tool_has_non_empty_description():
    """Every registered tool entry has a non-empty 'description' field."""
    for tool in _get_tools():
        assert isinstance(tool["description"], str) and tool["description"].strip(), (
            f"Tool {tool['name']!r} has empty description"
        )


def test_each_tool_has_schema_field():
    """Every registered tool entry has a 'schema' field (dict)."""
    for tool in _get_tools():
        assert "schema" in tool and isinstance(tool["schema"], dict), (
            f"Tool {tool['name']!r} is missing a dict schema"
        )


# ---------------------------------------------------------------------------
# Test: JSON Schema validity
# ---------------------------------------------------------------------------


def test_each_tool_schema_has_object_type():
    """Every tool schema declares type='object'."""
    for tool in _get_tools():
        schema = tool["schema"]
        assert schema.get("type") == "object", (
            f"Tool {tool['name']!r} schema.type != 'object': {schema!r}"
        )


def test_each_tool_schema_has_properties_dict():
    """Every tool schema has a 'properties' key that is a dict."""
    for tool in _get_tools():
        schema = tool["schema"]
        assert "properties" in schema and isinstance(schema["properties"], dict), (
            f"Tool {tool['name']!r} schema missing dict 'properties': {schema!r}"
        )


def test_each_tool_schema_required_is_list_if_present():
    """If a tool schema has a 'required' key its value must be a list."""
    for tool in _get_tools():
        schema = tool["schema"]
        if "required" in schema:
            assert isinstance(schema["required"], list), (
                f"Tool {tool['name']!r} schema 'required' is not a list: {schema!r}"
            )


def test_tools_with_no_params_have_empty_required():
    """Tools that take no required params declare an empty 'required' list."""
    no_required_tools = {"pc_control_screenshot", "system_get_metrics"}
    tools_by_name = {t["name"]: t for t in _get_tools()}
    for name in no_required_tools:
        schema = tools_by_name[name]["schema"]
        required = schema.get("required", [])
        assert required == [], (
            f"Tool {name!r} should have no required params, got: {required!r}"
        )


def test_tools_with_required_params_list_them():
    """Tools that have required parameters declare them in schema.required."""
    required_params: dict[str, set[str]] = {
        "github_list_repo_issues": {"repo"},
        "github_get_pr_details": {"repo", "number"},
        "github_get_ci_status": {"repo", "ref"},
        "gitlab_list_pipelines": {"project_id"},
        "gitlab_get_pipeline_details": {"project_id", "pipeline_id"},
        "smart_home_get_state": {"entity_id"},
        "smart_home_call_service": {"domain", "service"},
        "pc_control_launch_app": {"name"},
        "pc_control_set_volume": {"level"},
        "pc_control_focus_window": {"title"},
    }
    tools_by_name = {t["name"]: t for t in _get_tools()}
    for tool_name, expected_required in required_params.items():
        schema = tools_by_name[tool_name]["schema"]
        actual_required = set(schema.get("required", []))
        assert expected_required == actual_required, (
            f"Tool {tool_name!r}: expected required={expected_required!r}, "
            f"got {actual_required!r}"
        )


# ---------------------------------------------------------------------------
# Test: JSON-serialisability
# ---------------------------------------------------------------------------


def test_each_tool_entry_is_json_serialisable():
    """list_registered_tools() output (without 'fn') is fully JSON-serialisable."""
    tools = _get_tools()
    try:
        serialised = json.dumps(tools)
    except TypeError as exc:
        pytest.fail(f"list_registered_tools() output is not JSON-serialisable: {exc}")

    parsed = json.loads(serialised)
    assert len(parsed) == len(tools)


def test_tool_entries_do_not_expose_callable():
    """The 'fn' key must not appear in list_registered_tools() output."""
    for tool in _get_tools():
        assert "fn" not in tool, (
            f"Tool {tool['name']!r} entry exposes 'fn' (callable leak)"
        )
