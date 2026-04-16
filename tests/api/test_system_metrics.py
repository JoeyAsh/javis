"""Tests for ``src/api/system_metrics.py``.

All ``psutil`` / ``GPUtil`` calls are mocked.  No real hardware reads.
"""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure ``src`` is importable for the ``utils.logger`` resolution that
# ``system_metrics`` performs at import time.
_SRC = "src"
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from src.api import system_metrics as sm  # noqa: E402
from src.api.system_metrics import SystemMetrics, SystemMetricsCollector  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_psutil():
    """Patch all psutil attributes used by system_metrics with fakes."""
    with (
        patch.object(sm.psutil, "cpu_percent", return_value=12.5) as cpu,
        patch.object(
            sm.psutil,
            "virtual_memory",
            return_value=SimpleNamespace(percent=63.75),
        ) as mem,
        patch.object(
            sm.psutil,
            "disk_usage",
            return_value=SimpleNamespace(percent=41.0),
        ) as disk,
        patch.object(
            sm.psutil,
            "net_io_counters",
            return_value=SimpleNamespace(bytes_sent=0, bytes_recv=0),
        ) as net,
        patch.object(sm.psutil, "boot_time", return_value=1_000_000.0),
        patch.object(
            sm.psutil,
            "sensors_temperatures",
            return_value={
                "coretemp": [SimpleNamespace(current=54.0, label="")],
            },
        ) as temps,
    ):
        yield SimpleNamespace(
            cpu=cpu, mem=mem, disk=disk, net=net, temps=temps
        )


# ---------------------------------------------------------------------------
# snapshot()
# ---------------------------------------------------------------------------


class TestSnapshot:
    """Unit tests for ``SystemMetricsCollector.snapshot()``."""

    @pytest.mark.asyncio
    async def test_snapshot_returns_model(self, fake_psutil):
        """Returns a fully populated SystemMetrics instance."""
        with patch.object(sm, "_read_gpu_percent", return_value=37.5):
            collector = SystemMetricsCollector(interval_seconds=1.0)
            metrics = await collector.snapshot()

        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent == 12.5
        assert metrics.ram_percent == 63.75
        assert metrics.disk_percent == 41.0
        assert metrics.cpu_temp_c == 54.0
        assert metrics.gpu_percent == 37.5
        # First call seeds the net baseline — no delta available yet.
        assert metrics.net_up_mbps == 0.0
        assert metrics.net_down_mbps == 0.0
        assert metrics.uptime_seconds > 0.0

    @pytest.mark.asyncio
    async def test_snapshot_computes_network_delta(self, fake_psutil):
        """Second snapshot produces a positive Mbps reading."""
        with patch.object(sm, "_read_gpu_percent", return_value=None):
            collector = SystemMetricsCollector(interval_seconds=1.0)

            # First call seeds baseline.
            fake_psutil.net.return_value = SimpleNamespace(
                bytes_sent=1_000_000, bytes_recv=2_000_000
            )
            await collector.snapshot()

            # Advance fake counters ~ 1 MB up / 2 MB down.
            fake_psutil.net.return_value = SimpleNamespace(
                bytes_sent=2_000_000, bytes_recv=4_000_000
            )
            # Backdate the baseline timestamp so the delta-t is
            # deterministic enough to assert a lower bound on the
            # throughput figure.
            assert collector._last_net_at is not None
            collector._last_net_at -= 1.0

            second = await collector.snapshot()

        # Up: 1 MB in ~1 s → ~8 Mbps.  Allow slack for test jitter.
        assert second.net_up_mbps > 4.0
        assert second.net_down_mbps > 8.0

    @pytest.mark.asyncio
    async def test_snapshot_gpu_graceful_degradation(self, fake_psutil):
        """gpu_percent is None when GPUtil returns no GPUs."""
        with patch.object(sm, "_GPUTIL_AVAILABLE", True), patch.object(
            sm, "GPUtil", MagicMock(getGPUs=MagicMock(return_value=[]))
        ):
            collector = SystemMetricsCollector(interval_seconds=1.0)
            metrics = await collector.snapshot()

        assert metrics.gpu_percent is None

    @pytest.mark.asyncio
    async def test_snapshot_gpu_missing_module(self, fake_psutil):
        """gpu_percent is None when GPUtil isn't importable."""
        with patch.object(sm, "_GPUTIL_AVAILABLE", False), patch.object(
            sm, "GPUtil", None
        ):
            collector = SystemMetricsCollector(interval_seconds=1.0)
            metrics = await collector.snapshot()

        assert metrics.gpu_percent is None

    @pytest.mark.asyncio
    async def test_snapshot_gpu_raises_returns_none(self, fake_psutil):
        """Any GPUtil exception degrades to None rather than propagating."""
        broken = MagicMock(getGPUs=MagicMock(side_effect=RuntimeError("nvml")))
        with patch.object(sm, "_GPUTIL_AVAILABLE", True), patch.object(
            sm, "GPUtil", broken
        ):
            collector = SystemMetricsCollector(interval_seconds=1.0)
            metrics = await collector.snapshot()

        assert metrics.gpu_percent is None

    @pytest.mark.asyncio
    async def test_snapshot_temp_unavailable(self, fake_psutil):
        """cpu_temp_c is None when no sensors are reported."""
        fake_psutil.temps.return_value = {}
        with patch.object(sm, "_read_gpu_percent", return_value=None):
            collector = SystemMetricsCollector(interval_seconds=1.0)
            metrics = await collector.snapshot()

        assert metrics.cpu_temp_c is None

    @pytest.mark.asyncio
    async def test_snapshot_temp_fallback_key(self, fake_psutil):
        """Uses the k10temp key on AMD systems when coretemp is absent."""
        fake_psutil.temps.return_value = {
            "k10temp": [SimpleNamespace(current=66.125, label="Tctl")],
        }
        with patch.object(sm, "_read_gpu_percent", return_value=None):
            collector = SystemMetricsCollector(interval_seconds=1.0)
            metrics = await collector.snapshot()

        assert metrics.cpu_temp_c == 66.125


# ---------------------------------------------------------------------------
# run() / stop()
# ---------------------------------------------------------------------------


class TestRunLoop:
    """Tests for the periodic ``run`` loop."""

    @pytest.mark.asyncio
    async def test_run_invokes_callback_repeatedly(self, fake_psutil):
        """Callback fires ~N times for ~N*interval seconds of runtime."""
        collector = SystemMetricsCollector(interval_seconds=0.05)

        received: list[SystemMetrics] = []

        async def on_snap(m: SystemMetrics) -> None:
            received.append(m)
            if len(received) >= 3:
                await collector.stop()

        with patch.object(sm, "_read_gpu_percent", return_value=None):
            await asyncio.wait_for(collector.run(on_snap), timeout=2.0)

        assert len(received) >= 3
        for snap in received:
            assert isinstance(snap, SystemMetrics)

    @pytest.mark.asyncio
    async def test_run_stops_promptly(self, fake_psutil):
        """stop() makes the loop exit without waiting for the next tick."""
        collector = SystemMetricsCollector(interval_seconds=5.0)
        callback = AsyncMock()

        with patch.object(sm, "_read_gpu_percent", return_value=None):
            task = asyncio.create_task(collector.run(callback))
            # Give it a moment to fire the first snapshot.
            await asyncio.sleep(0.1)
            await collector.stop()
            await asyncio.wait_for(task, timeout=1.0)

        assert callback.await_count >= 1

    @pytest.mark.asyncio
    async def test_run_tolerates_callback_errors(self, fake_psutil):
        """A raising callback does not kill the loop."""
        collector = SystemMetricsCollector(interval_seconds=0.02)
        calls = {"n": 0}

        async def on_snap(_: SystemMetrics) -> None:
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("boom")
            await collector.stop()

        with patch.object(sm, "_read_gpu_percent", return_value=None):
            await asyncio.wait_for(collector.run(on_snap), timeout=2.0)

        assert calls["n"] >= 3


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def test_interval_must_be_positive():
    with pytest.raises(ValueError):
        SystemMetricsCollector(interval_seconds=0)
    with pytest.raises(ValueError):
        SystemMetricsCollector(interval_seconds=-1.0)
