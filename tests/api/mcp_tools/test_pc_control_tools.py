"""Unit tests for api/mcp_tools/pc_control_tools.py.

Mocks at the actions.pc_control boundary (_open_app, _set_volume, _screenshot)
and at the config boundary (_check_pc_control_available).
No real subprocess / hardware calls are made.

Covered:
- pc_control_launch_app: happy path, unknown-app error, RPi guard, disabled guard.
- pc_control_set_volume: happy path, clamping (< 0, > 100), failure path.
- pc_control_screenshot: happy path, failure path.
- pc_control_focus_window: happy path, no-window path, 'not available' error path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Guard helper
# ---------------------------------------------------------------------------


def _pc_available():
    """Patch _check_pc_control_available to be a no-op (PC is available)."""
    return patch("api.mcp_tools.pc_control_tools._check_pc_control_available")


def _pc_unavailable(message: str = "PC control not available"):
    """Patch _check_pc_control_available to raise RuntimeError."""
    return patch(
        "api.mcp_tools.pc_control_tools._check_pc_control_available",
        side_effect=RuntimeError(message),
    )


# ---------------------------------------------------------------------------
# pc_control_launch_app
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pc_control_launch_app_happy_path():
    """pc_control_launch_app returns {'app': name, 'result': msg} on success."""
    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._open_app",
        new=AsyncMock(return_value="Opened chrome"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_launch_app

        result = await pc_control_launch_app(name="chrome")

    assert result["app"] == "chrome"
    assert result["result"] == "Opened chrome"


@pytest.mark.asyncio
async def test_pc_control_launch_app_calls_open_app_with_correct_params():
    """pc_control_launch_app passes {'app': name} to _open_app."""
    call_recorder: list[dict] = []

    async def _record(params: dict) -> str:
        call_recorder.append(params)
        return "Opened code"

    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._open_app", new=_record
    ):
        from api.mcp_tools.pc_control_tools import pc_control_launch_app

        await pc_control_launch_app(name="code")

    assert call_recorder[0] == {"app": "code"}


@pytest.mark.asyncio
async def test_pc_control_launch_app_failure_response_raises_runtime():
    """pc_control_launch_app raises RuntimeError when _open_app returns 'Failed'."""
    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._open_app",
        new=AsyncMock(return_value="Failed to open unknown: file not found"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_launch_app

        with pytest.raises(RuntimeError, match="Failed"):
            await pc_control_launch_app(name="unknown_app")


@pytest.mark.asyncio
async def test_pc_control_launch_app_unknown_app_raises_runtime():
    """pc_control_launch_app raises RuntimeError when _open_app returns 'Unknown'."""
    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._open_app",
        new=AsyncMock(return_value="Unknown app: xyz"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_launch_app

        with pytest.raises(RuntimeError, match="Unknown"):
            await pc_control_launch_app(name="xyz")


@pytest.mark.asyncio
async def test_pc_control_launch_app_rpi_guard_raises_runtime():
    """pc_control_launch_app raises RuntimeError on Raspberry Pi."""
    with _pc_unavailable("PC control is not available on Raspberry Pi."):
        from api.mcp_tools.pc_control_tools import pc_control_launch_app

        with pytest.raises(RuntimeError, match="Raspberry Pi"):
            await pc_control_launch_app(name="chrome")


@pytest.mark.asyncio
async def test_pc_control_launch_app_disabled_raises_runtime():
    """pc_control_launch_app raises RuntimeError when PC control is disabled."""
    with _pc_unavailable("PC control is disabled (pc_control.enabled: false)."):
        from api.mcp_tools.pc_control_tools import pc_control_launch_app

        with pytest.raises(RuntimeError, match="disabled"):
            await pc_control_launch_app(name="chrome")


# ---------------------------------------------------------------------------
# pc_control_set_volume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pc_control_set_volume_happy_path():
    """pc_control_set_volume returns level and result dict on success."""
    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._set_volume",
        new=AsyncMock(return_value="Volume set to 50%"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_set_volume

        result = await pc_control_set_volume(level=50)

    assert result["level"] == 50
    assert result["result"] == "Volume set to 50%"


@pytest.mark.asyncio
async def test_pc_control_set_volume_clamps_below_zero():
    """pc_control_set_volume clamps levels below 0 to 0."""
    call_recorder: list[dict] = []

    async def _record(params: dict) -> str:
        call_recorder.append(params)
        return "Volume set to 0%"

    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._set_volume", new=_record
    ):
        from api.mcp_tools.pc_control_tools import pc_control_set_volume

        result = await pc_control_set_volume(level=-10)

    assert call_recorder[0]["level"] == 0
    assert result["level"] == 0


@pytest.mark.asyncio
async def test_pc_control_set_volume_clamps_above_100():
    """pc_control_set_volume clamps levels above 100 to 100."""
    call_recorder: list[dict] = []

    async def _record(params: dict) -> str:
        call_recorder.append(params)
        return "Volume set to 100%"

    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._set_volume", new=_record
    ):
        from api.mcp_tools.pc_control_tools import pc_control_set_volume

        result = await pc_control_set_volume(level=150)

    assert call_recorder[0]["level"] == 100
    assert result["level"] == 100


@pytest.mark.asyncio
async def test_pc_control_set_volume_failure_raises_runtime():
    """pc_control_set_volume raises RuntimeError when _set_volume returns 'Failed'."""
    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._set_volume",
        new=AsyncMock(return_value="Failed to set volume: pycaw not available"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_set_volume

        with pytest.raises(RuntimeError, match="Failed"):
            await pc_control_set_volume(level=50)


@pytest.mark.asyncio
async def test_pc_control_set_volume_not_available_raises_runtime():
    """pc_control_set_volume raises RuntimeError when result contains 'not available'."""
    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._set_volume",
        new=AsyncMock(return_value="Volume control not available on this system"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_set_volume

        with pytest.raises(RuntimeError, match="not available"):
            await pc_control_set_volume(level=30)


# ---------------------------------------------------------------------------
# pc_control_screenshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pc_control_screenshot_happy_path():
    """pc_control_screenshot returns {'result': path_string} on success."""
    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._screenshot",
        new=AsyncMock(return_value="Screenshot saved to Desktop/screenshot.png"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_screenshot

        result = await pc_control_screenshot()

    assert "result" in result
    assert "screenshot" in result["result"].lower()


@pytest.mark.asyncio
async def test_pc_control_screenshot_calls_screenshot_with_empty_params():
    """pc_control_screenshot calls _screenshot with an empty dict."""
    call_recorder: list[dict] = []

    async def _record(params: dict) -> str:
        call_recorder.append(params)
        return "Saved"

    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._screenshot", new=_record
    ):
        from api.mcp_tools.pc_control_tools import pc_control_screenshot

        await pc_control_screenshot()

    assert call_recorder[0] == {}


@pytest.mark.asyncio
async def test_pc_control_screenshot_failure_raises_runtime():
    """pc_control_screenshot raises RuntimeError when _screenshot returns 'failed'."""
    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._screenshot",
        new=AsyncMock(return_value="Screenshot failed: no display"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_screenshot

        with pytest.raises(RuntimeError, match="failed"):
            await pc_control_screenshot()


@pytest.mark.asyncio
async def test_pc_control_screenshot_not_available_raises_runtime():
    """pc_control_screenshot raises RuntimeError when result contains 'not available'."""
    with _pc_available(), patch(
        "api.mcp_tools.pc_control_tools._screenshot",
        new=AsyncMock(return_value="Screenshot not available in headless mode"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_screenshot

        with pytest.raises(RuntimeError, match="not available"):
            await pc_control_screenshot()


@pytest.mark.asyncio
async def test_pc_control_screenshot_rpi_guard_raises_runtime():
    """pc_control_screenshot raises RuntimeError on Raspberry Pi."""
    with _pc_unavailable("PC control is not available on Raspberry Pi."):
        from api.mcp_tools.pc_control_tools import pc_control_screenshot

        with pytest.raises(RuntimeError, match="Raspberry Pi"):
            await pc_control_screenshot()


# ---------------------------------------------------------------------------
# pc_control_focus_window
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pc_control_focus_window_happy_path():
    """pc_control_focus_window returns {'title': t, 'result': msg} on success."""
    with _pc_available(), patch(
        "asyncio.to_thread",
        new=AsyncMock(return_value="Focused window: 'VS Code'"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_focus_window

        result = await pc_control_focus_window(title="VS Code")

    assert result["title"] == "VS Code"
    assert "Focused" in result["result"]


@pytest.mark.asyncio
async def test_pc_control_focus_window_no_window_found_raises():
    """pc_control_focus_window raises RuntimeError when no window matches the title."""
    with _pc_available(), patch(
        "asyncio.to_thread",
        new=AsyncMock(return_value="No window found matching title: 'NonExistent'"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_focus_window

        with pytest.raises(RuntimeError, match="No window found"):
            await pc_control_focus_window(title="NonExistent")


@pytest.mark.asyncio
async def test_pc_control_focus_window_not_available_raises_runtime():
    """pc_control_focus_window raises RuntimeError when pywin32 is missing."""
    with _pc_available(), patch(
        "asyncio.to_thread",
        new=AsyncMock(return_value="pywin32 not available — cannot focus windows on Windows"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_focus_window

        with pytest.raises(RuntimeError, match="not available"):
            await pc_control_focus_window(title="SomeApp")


@pytest.mark.asyncio
async def test_pc_control_focus_window_failed_raises_runtime():
    """pc_control_focus_window raises RuntimeError when result contains 'failed'."""
    with _pc_available(), patch(
        "asyncio.to_thread",
        new=AsyncMock(return_value="AppleScript focus failed: timeout"),
    ):
        from api.mcp_tools.pc_control_tools import pc_control_focus_window

        with pytest.raises(RuntimeError, match="failed"):
            await pc_control_focus_window(title="App")


@pytest.mark.asyncio
async def test_pc_control_focus_window_rpi_guard_raises_runtime():
    """pc_control_focus_window raises RuntimeError on Raspberry Pi."""
    with _pc_unavailable("PC control is not available on Raspberry Pi."):
        from api.mcp_tools.pc_control_tools import pc_control_focus_window

        with pytest.raises(RuntimeError, match="Raspberry Pi"):
            await pc_control_focus_window(title="VS Code")
