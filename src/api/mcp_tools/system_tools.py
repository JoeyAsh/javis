"""MCP tool registrations for the ``system.*`` namespace.

Thin wrapper over :class:`api.system_metrics.SystemMetricsCollector`.
Returns a one-shot CPU/RAM/Disk/GPU/network/uptime snapshot.

Registered tools (1):
- ``system_get_metrics``
"""

from __future__ import annotations

from typing import Any

from api.mcp_server import register_tool
from api.system_metrics import SystemMetricsCollector
from utils.logger import get_logger

logger = get_logger("mcp_tools.system")

# A single shared collector instance so the net-counter baseline is seeded
# once and subsequent calls can produce meaningful bandwidth delta readings.
_collector = SystemMetricsCollector(interval_seconds=2.0)


@register_tool(
    name="system_get_metrics",
    description=(
        "Return a snapshot of the current system metrics: CPU usage, RAM usage, "
        "disk usage, GPU usage (if available), CPU temperature (if available), "
        "network throughput, and uptime."
    ),
    schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def system_get_metrics() -> dict[str, Any]:
    """Return a fresh CPU/RAM/Disk/GPU/network/uptime snapshot."""
    snap = await _collector.snapshot()
    result: dict[str, Any] = snap.model_dump()
    logger.debug(
        f"system_get_metrics: cpu={result['cpu_percent']}%, "
        f"ram={result['ram_percent']}%, "
        f"disk={result['disk_percent']}%"
    )
    return result
