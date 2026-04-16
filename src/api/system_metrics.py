"""Async system metrics collector.

Collects CPU/RAM/GPU/temperature/network/disk/uptime metrics using
``psutil`` (and optionally ``GPUtil`` for NVIDIA GPU utilisation) and
exposes them through an async tick loop suitable for WebSocket
broadcasting.

All ``psutil`` calls are wrapped in ``asyncio.to_thread`` so the event
loop never blocks on hardware I/O.  External dependencies degrade
gracefully — if ``GPUtil`` is missing or no GPU is available,
``gpu_percent`` is simply ``None``.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

import psutil
from pydantic import BaseModel, Field

from utils.logger import get_logger

logger = get_logger("system_metrics")


# ---------------------------------------------------------------------------
# Optional GPUtil import
# ---------------------------------------------------------------------------

try:  # pragma: no cover - import-time branch
    import GPUtil  # type: ignore[import-not-found]

    _GPUTIL_AVAILABLE = True
except Exception:  # noqa: BLE001 - any import failure → graceful fallback
    GPUtil = None  # type: ignore[assignment]
    _GPUTIL_AVAILABLE = False


# Sensor keys checked for CPU temperature, in order of preference.
_CPU_TEMP_KEYS: tuple[str, ...] = ("coretemp", "k10temp", "cpu_thermal", "acpitz")


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------


class SystemMetrics(BaseModel):
    """Structured system metrics snapshot broadcast to clients."""

    cpu_percent: float = Field(ge=0.0, le=100.0)
    ram_percent: float = Field(ge=0.0, le=100.0)
    gpu_percent: float | None = None
    cpu_temp_c: float | None = None
    net_up_mbps: float = Field(ge=0.0)
    net_down_mbps: float = Field(ge=0.0)
    disk_percent: float = Field(ge=0.0, le=100.0)
    uptime_seconds: float = Field(ge=0.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_cpu_temp() -> float | None:
    """Return CPU temperature in Celsius, or ``None`` if unavailable.

    Tries a handful of common sensor keys reported by
    ``psutil.sensors_temperatures()`` (Linux).
    """
    sensors_fn = getattr(psutil, "sensors_temperatures", None)
    if sensors_fn is None:
        return None

    try:
        temps: dict[str, Any] = sensors_fn()
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"sensors_temperatures failed: {exc}")
        return None

    if not temps:
        return None

    for key in _CPU_TEMP_KEYS:
        entries = temps.get(key)
        if not entries:
            continue
        for entry in entries:
            current = getattr(entry, "current", None)
            if current is not None:
                return float(current)

    # Fallback: first entry we can read.
    for entries in temps.values():
        if not entries:
            continue
        for entry in entries:
            current = getattr(entry, "current", None)
            if current is not None:
                return float(current)

    return None


def _read_gpu_percent() -> float | None:
    """Return NVIDIA GPU load as a 0–100 percentage, or ``None``."""
    if not _GPUTIL_AVAILABLE or GPUtil is None:
        return None

    try:
        gpus = GPUtil.getGPUs()
    except Exception as exc:  # noqa: BLE001 - nvidia-smi missing / driver errors
        logger.debug(f"GPUtil.getGPUs failed: {exc}")
        return None

    if not gpus:
        return None

    try:
        # GPUtil reports load as 0.0–1.0.
        return float(gpus[0].load) * 100.0
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Reading GPU load failed: {exc}")
        return None


def _read_net_counters() -> tuple[int, int]:
    """Return ``(bytes_sent, bytes_recv)`` for aggregate network I/O."""
    counters = psutil.net_io_counters()
    return int(counters.bytes_sent), int(counters.bytes_recv)


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------


class SystemMetricsCollector:
    """Periodic async collector for :class:`SystemMetrics`.

    Use :meth:`snapshot` for a one-shot reading, or :meth:`run` to drive
    a long-running broadcast loop.  The loop can be cancelled cleanly
    via :meth:`stop`.
    """

    def __init__(self, interval_seconds: float = 2.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

        self.interval_seconds = float(interval_seconds)
        self._stop_event = asyncio.Event()
        self._boot_time: float = float(psutil.boot_time())
        self._last_net: tuple[int, int] | None = None
        self._last_net_at: float | None = None

    # ----- Public API ---------------------------------------------------

    async def snapshot(self) -> SystemMetrics:
        """Return a fresh :class:`SystemMetrics` reading.

        All blocking ``psutil`` calls are offloaded to a worker thread.
        The first call seeds the network baseline; it reports
        ``net_up_mbps = net_down_mbps = 0.0`` until a second sample has
        been taken.
        """
        cpu_percent = await asyncio.to_thread(psutil.cpu_percent, None)
        ram_percent = await asyncio.to_thread(lambda: psutil.virtual_memory().percent)
        disk_percent = await asyncio.to_thread(lambda: psutil.disk_usage("/").percent)
        cpu_temp = await asyncio.to_thread(_read_cpu_temp)
        gpu_percent = await asyncio.to_thread(_read_gpu_percent)
        net_sent, net_recv = await asyncio.to_thread(_read_net_counters)

        now = time.time()
        up_mbps = 0.0
        down_mbps = 0.0
        if self._last_net is not None and self._last_net_at is not None:
            delta_t = max(now - self._last_net_at, 1e-6)
            d_sent = max(net_sent - self._last_net[0], 0)
            d_recv = max(net_recv - self._last_net[1], 0)
            # bytes/s → megabits/s  (×8 / 1_000_000)
            up_mbps = (d_sent * 8.0) / (delta_t * 1_000_000.0)
            down_mbps = (d_recv * 8.0) / (delta_t * 1_000_000.0)

        self._last_net = (net_sent, net_recv)
        self._last_net_at = now

        uptime_seconds = max(now - self._boot_time, 0.0)

        return SystemMetrics(
            cpu_percent=float(cpu_percent),
            ram_percent=float(ram_percent),
            gpu_percent=gpu_percent,
            cpu_temp_c=cpu_temp,
            net_up_mbps=float(up_mbps),
            net_down_mbps=float(down_mbps),
            disk_percent=float(disk_percent),
            uptime_seconds=float(uptime_seconds),
        )

    async def run(
        self,
        on_snapshot: Callable[[SystemMetrics], Awaitable[None]],
    ) -> None:
        """Run the collection loop until :meth:`stop` is called.

        Each iteration captures a snapshot and awaits ``on_snapshot``.
        Errors in the callback are logged but do not kill the loop.
        """
        self._stop_event.clear()
        logger.info(
            f"SystemMetricsCollector started "
            f"(interval={self.interval_seconds}s, "
            f"gputil={_GPUTIL_AVAILABLE})"
        )

        try:
            while not self._stop_event.is_set():
                try:
                    snap = await self.snapshot()
                    await on_snapshot(snap)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"system_metrics tick failed: {exc}")

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.interval_seconds,
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.info("SystemMetricsCollector cancelled")
            raise
        finally:
            logger.info("SystemMetricsCollector stopped")

    async def stop(self) -> None:
        """Signal :meth:`run` to exit on its next iteration."""
        self._stop_event.set()
