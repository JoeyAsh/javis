"""MCP tool registrations for the ``pc_control.*`` namespace.

Thin wrappers over :mod:`actions.pc_control`.  Each handler maps to an
existing action in :func:`~actions.pc_control.execute_pc_action` and
returns a JSON-serialisable dict.

Registered tools (4):
- ``pc_control_launch_app``
- ``pc_control_set_volume``
- ``pc_control_screenshot``
- ``pc_control_focus_window``
"""

from __future__ import annotations

from typing import Any

from actions.pc_control import (
    APP_EXECUTABLES,
    _open_app,
    _screenshot,
    _set_volume,
)
from api.mcp_server import register_tool
from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("mcp_tools.pc_control")


# ---------------------------------------------------------------------------
# Internal guard
# ---------------------------------------------------------------------------


def _check_pc_control_available() -> None:
    """Raise RuntimeError if PC control is disabled or we're on an RPi."""
    cfg = get_config()
    if cfg.is_rpi:
        raise RuntimeError("PC control is not available on Raspberry Pi.")
    if not cfg.get("pc_control.enabled", True):
        raise RuntimeError("PC control is disabled (pc_control.enabled: false).")


# ---------------------------------------------------------------------------
# pc_control_launch_app
# ---------------------------------------------------------------------------


@register_tool(
    name="pc_control_launch_app",
    description=(
        "Launch an application by its canonical name. "
        f"Supported apps: {', '.join(sorted(APP_EXECUTABLES.keys()))}."
    ),
    schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": (
                    "App key to launch. Must be one of the supported app names "
                    "(e.g. 'chrome', 'code', 'spotify', 'discord')."
                ),
            },
        },
        "required": ["name"],
    },
)
async def pc_control_launch_app(name: str) -> dict[str, Any]:
    """Launch a whitelisted application by name."""
    _check_pc_control_available()
    result = await _open_app({"app": name})
    logger.debug(f"pc_control_launch_app({name!r}): {result}")
    if "Failed" in result or "Unknown" in result:
        raise RuntimeError(result)
    return {"app": name, "result": result}


# ---------------------------------------------------------------------------
# pc_control_set_volume
# ---------------------------------------------------------------------------


@register_tool(
    name="pc_control_set_volume",
    description="Set the system audio volume to an absolute level (0–100).",
    schema={
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Target volume level as a percentage (0 = mute, 100 = max).",
            },
        },
        "required": ["level"],
    },
)
async def pc_control_set_volume(level: int) -> dict[str, Any]:
    """Set system volume to the given percentage (0–100)."""
    _check_pc_control_available()
    clamped = max(0, min(100, level))
    result = await _set_volume({"level": clamped})
    logger.debug(f"pc_control_set_volume({clamped}): {result}")
    if "Failed" in result or "not available" in result:
        raise RuntimeError(result)
    return {"level": clamped, "result": result}


# ---------------------------------------------------------------------------
# pc_control_screenshot
# ---------------------------------------------------------------------------


@register_tool(
    name="pc_control_screenshot",
    description="Take a screenshot and save it to the Desktop.",
    schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def pc_control_screenshot() -> dict[str, Any]:
    """Capture a screenshot and return the saved file path."""
    _check_pc_control_available()
    result = await _screenshot({})
    logger.debug(f"pc_control_screenshot: {result}")
    if "failed" in result.lower() or "not available" in result.lower():
        raise RuntimeError(result)
    return {"result": result}


# ---------------------------------------------------------------------------
# pc_control_focus_window
# ---------------------------------------------------------------------------


@register_tool(
    name="pc_control_focus_window",
    description="Bring a window to the foreground by matching its title.",
    schema={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Substring of the window title to match (case-insensitive).",
            },
        },
        "required": ["title"],
    },
)
async def pc_control_focus_window(title: str) -> dict[str, Any]:
    """Focus the first window whose title contains the given substring."""
    _check_pc_control_available()
    import asyncio  # noqa: PLC0415

    def _focus_sync(title: str) -> str:
        import sys  # noqa: PLC0415

        if sys.platform == "win32":
            try:
                import ctypes  # noqa: PLC0415

                import win32con  # type: ignore[import-not-found]
                import win32gui  # type: ignore[import-not-found]

                def _enum_callback(hwnd: int, results: list[int]) -> bool:
                    if win32gui.IsWindowVisible(hwnd):
                        window_title = win32gui.GetWindowText(hwnd)
                        if title.lower() in window_title.lower():
                            results.append(hwnd)
                    return True

                found: list[int] = []
                win32gui.EnumWindows(_enum_callback, found)
                if not found:
                    return f"No window found matching title: {title!r}"
                hwnd = found[0]
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                window_text = win32gui.GetWindowText(hwnd)
                return f"Focused window: {window_text!r}"
            except ImportError:
                return "pywin32 not available — cannot focus windows on Windows"
        elif sys.platform == "darwin":
            try:
                import subprocess  # noqa: PLC0415

                script = (
                    f'tell application "System Events" to set frontmost of '
                    f'(first process whose name contains "{title}") to true'
                )
                subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
                return f"Focused window matching: {title!r}"
            except Exception as exc:  # noqa: BLE001
                return f"AppleScript focus failed: {exc}"
        else:
            try:
                import subprocess  # noqa: PLC0415

                result = subprocess.run(
                    ["wmctrl", "-a", title],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return f"Focused window matching: {title!r}"
                return f"wmctrl failed (rc={result.returncode}): {result.stderr.strip()}"
            except FileNotFoundError:
                return "wmctrl not found — install it with: sudo apt install wmctrl"

    result = await asyncio.to_thread(_focus_sync, title)
    logger.debug(f"pc_control_focus_window({title!r}): {result}")
    result_lower = result.lower()
    if any(
        s in result_lower
        for s in ("not available", "failed", "not found", "no window", "no matching")
    ):
        raise RuntimeError(result)
    return {"title": title, "result": result}
