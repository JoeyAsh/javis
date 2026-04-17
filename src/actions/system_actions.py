"""System actions for JARVIS.

Historical home of the ``SystemActions`` helper that the old monolithic
agent referenced. With the single-call pipeline, system-level commands
(voice change, memory reset, shutdown) are handled directly by
:class:`brain.agents.system_agent.SystemAgent` without a middleman class.

The ``get_system_info`` helper is kept — it's a cheap psutil snapshot used
by the HUD status text. Nothing else in the project references this module.
"""

from __future__ import annotations

import time
from typing import Any

import psutil


async def get_system_info() -> dict[str, Any]:
    """Get current system information.

    Returns:
        Dictionary with ``cpu``, ``mem``, ``uptime`` (``Xh Ym`` string) and
        ``uptime_seconds`` for callers that want the raw value.
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    boot_time = psutil.boot_time()

    uptime_seconds = int(time.time() - boot_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60

    uptime_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    return {
        "cpu": round(cpu_percent, 1),
        "mem": round(memory.percent, 1),
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
    }
