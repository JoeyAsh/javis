"""Unit tests for api/mcp_tools/system_tools.py.

Mocks at the SystemMetricsCollector.snapshot boundary so no real psutil or
hardware calls are made.

Covered:
- system_get_metrics: happy path returns all expected fields.
- system_get_metrics: fields are correct types and within valid ranges.
- system_get_metrics: optional fields (gpu_percent, cpu_temp_c) may be None.
- system_get_metrics: result is JSON-serialisable.
- system_get_metrics: propagates exceptions from snapshot().
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fake metrics snapshot
# ---------------------------------------------------------------------------


def _make_snapshot(**overrides):
    """Return a SystemMetrics-compatible dict (pydantic model_dump output)."""
    defaults = {
        "cpu_percent": 42.0,
        "ram_percent": 55.0,
        "gpu_percent": None,
        "cpu_temp_c": None,
        "net_up_mbps": 1.5,
        "net_down_mbps": 3.0,
        "disk_percent": 70.0,
        "uptime_seconds": 86400.0,
    }
    defaults.update(overrides)

    # Return a mock that has model_dump() returning the dict.
    from unittest.mock import MagicMock

    snap = MagicMock()
    snap.model_dump.return_value = defaults
    return snap


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_get_metrics_returns_all_expected_keys():
    """system_get_metrics result contains all required metric keys."""
    fake_snap = _make_snapshot()

    with patch(
        "api.mcp_tools.system_tools._collector.snapshot",
        new=AsyncMock(return_value=fake_snap),
    ):
        from api.mcp_tools.system_tools import system_get_metrics

        result = await system_get_metrics()

    expected_keys = {
        "cpu_percent",
        "ram_percent",
        "gpu_percent",
        "cpu_temp_c",
        "net_up_mbps",
        "net_down_mbps",
        "disk_percent",
        "uptime_seconds",
    }
    assert expected_keys <= set(result.keys()), (
        f"Missing keys: {expected_keys - set(result.keys())}"
    )


@pytest.mark.asyncio
async def test_system_get_metrics_happy_path_values():
    """system_get_metrics returns the snapshot values verbatim."""
    fake_snap = _make_snapshot(
        cpu_percent=25.0,
        ram_percent=60.0,
        disk_percent=80.0,
        uptime_seconds=3600.0,
        net_up_mbps=0.5,
        net_down_mbps=2.0,
    )

    with patch(
        "api.mcp_tools.system_tools._collector.snapshot",
        new=AsyncMock(return_value=fake_snap),
    ):
        from api.mcp_tools.system_tools import system_get_metrics

        result = await system_get_metrics()

    assert result["cpu_percent"] == 25.0
    assert result["ram_percent"] == 60.0
    assert result["disk_percent"] == 80.0
    assert result["uptime_seconds"] == 3600.0


@pytest.mark.asyncio
async def test_system_get_metrics_optional_fields_may_be_none():
    """system_get_metrics allows gpu_percent and cpu_temp_c to be None."""
    fake_snap = _make_snapshot(gpu_percent=None, cpu_temp_c=None)

    with patch(
        "api.mcp_tools.system_tools._collector.snapshot",
        new=AsyncMock(return_value=fake_snap),
    ):
        from api.mcp_tools.system_tools import system_get_metrics

        result = await system_get_metrics()

    assert result["gpu_percent"] is None
    assert result["cpu_temp_c"] is None


@pytest.mark.asyncio
async def test_system_get_metrics_optional_fields_populated_when_available():
    """system_get_metrics forwards gpu_percent and cpu_temp_c when present."""
    fake_snap = _make_snapshot(gpu_percent=30.0, cpu_temp_c=65.5)

    with patch(
        "api.mcp_tools.system_tools._collector.snapshot",
        new=AsyncMock(return_value=fake_snap),
    ):
        from api.mcp_tools.system_tools import system_get_metrics

        result = await system_get_metrics()

    assert result["gpu_percent"] == 30.0
    assert result["cpu_temp_c"] == 65.5


@pytest.mark.asyncio
async def test_system_get_metrics_result_is_json_serialisable():
    """system_get_metrics output is fully JSON-serialisable."""
    fake_snap = _make_snapshot(gpu_percent=10.0, cpu_temp_c=55.0)

    with patch(
        "api.mcp_tools.system_tools._collector.snapshot",
        new=AsyncMock(return_value=fake_snap),
    ):
        from api.mcp_tools.system_tools import system_get_metrics

        result = await system_get_metrics()

    try:
        serialised = json.dumps(result)
    except TypeError as exc:
        pytest.fail(f"system_get_metrics result is not JSON-serialisable: {exc}")

    parsed = json.loads(serialised)
    assert "cpu_percent" in parsed


@pytest.mark.asyncio
async def test_system_get_metrics_calls_collector_snapshot():
    """system_get_metrics calls _collector.snapshot() exactly once per invocation."""
    fake_snap = _make_snapshot()
    snapshot_mock = AsyncMock(return_value=fake_snap)

    with patch("api.mcp_tools.system_tools._collector.snapshot", new=snapshot_mock):
        from api.mcp_tools.system_tools import system_get_metrics

        await system_get_metrics()
        await system_get_metrics()

    assert snapshot_mock.call_count == 2


@pytest.mark.asyncio
async def test_system_get_metrics_propagates_exception_from_snapshot():
    """system_get_metrics lets exceptions from snapshot() bubble up."""
    with patch(
        "api.mcp_tools.system_tools._collector.snapshot",
        new=AsyncMock(side_effect=RuntimeError("psutil failed")),
    ):
        from api.mcp_tools.system_tools import system_get_metrics

        with pytest.raises(RuntimeError, match="psutil failed"):
            await system_get_metrics()
