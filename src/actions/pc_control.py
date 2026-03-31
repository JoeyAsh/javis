"""PC control actions for JARVIS.

Handles opening/closing apps, volume control, screenshots, etc.
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from src.utils.config_loader import get_config
from src.utils.logger import get_logger

logger = get_logger("pc_control")

# App name to executable mapping
APP_EXECUTABLES: dict[str, dict[str, str]] = {
    "chrome": {
        "win32": "chrome",
        "linux": "google-chrome",
        "darwin": "Google Chrome",
    },
    "firefox": {
        "win32": "firefox",
        "linux": "firefox",
        "darwin": "Firefox",
    },
    "msedge": {
        "win32": "msedge",
        "linux": "microsoft-edge",
        "darwin": "Microsoft Edge",
    },
    "spotify": {
        "win32": "spotify",
        "linux": "spotify",
        "darwin": "Spotify",
    },
    "code": {
        "win32": "code",
        "linux": "code",
        "darwin": "Visual Studio Code",
    },
    "notepad": {
        "win32": "notepad",
        "linux": "gedit",
        "darwin": "TextEdit",
    },
    "calc": {
        "win32": "calc",
        "linux": "gnome-calculator",
        "darwin": "Calculator",
    },
    "explorer": {
        "win32": "explorer",
        "linux": "nautilus",
        "darwin": "Finder",
    },
    "cmd": {
        "win32": "cmd",
        "linux": "gnome-terminal",
        "darwin": "Terminal",
    },
    "powershell": {
        "win32": "powershell",
        "linux": "gnome-terminal",
        "darwin": "Terminal",
    },
    "discord": {
        "win32": "discord",
        "linux": "discord",
        "darwin": "Discord",
    },
    "slack": {
        "win32": "slack",
        "linux": "slack",
        "darwin": "Slack",
    },
    "teams": {
        "win32": "teams",
        "linux": "teams",
        "darwin": "Microsoft Teams",
    },
    "winword": {
        "win32": "winword",
        "linux": "libreoffice --writer",
        "darwin": "Microsoft Word",
    },
    "excel": {
        "win32": "excel",
        "linux": "libreoffice --calc",
        "darwin": "Microsoft Excel",
    },
    "powerpnt": {
        "win32": "powerpnt",
        "linux": "libreoffice --impress",
        "darwin": "Microsoft PowerPoint",
    },
    "outlook": {
        "win32": "outlook",
        "linux": "thunderbird",
        "darwin": "Microsoft Outlook",
    },
}


async def execute_pc_action(params: dict[str, Any]) -> str:
    """Execute a PC control action.

    Args:
        params: Action parameters including 'action' key

    Returns:
        Result message
    """
    cfg = get_config()

    # Check if running on Raspberry Pi
    if cfg.is_rpi:
        return "PC control not available on Raspberry Pi"

    # Check if PC control is enabled
    if not cfg.get("pc_control.enabled", True):
        return "PC control is disabled"

    action = params.get("action", "unknown")

    action_handlers = {
        "open_app": _open_app,
        "close_app": _close_app,
        "set_volume": _set_volume,
        "mute_toggle": _mute_toggle,
        "screenshot": _screenshot,
        "type_text": _type_text,
    }

    handler = action_handlers.get(action)
    if handler:
        return await handler(params)
    else:
        return f"Unknown action: {action}"


async def _open_app(params: dict[str, Any]) -> str:
    """Open an application.

    Args:
        params: Parameters with 'app' key

    Returns:
        Result message
    """
    app = params.get("app")
    if not app:
        return "No application specified"

    platform = sys.platform
    loop = asyncio.get_event_loop()

    def open_sync() -> str:
        try:
            app_info = APP_EXECUTABLES.get(app, {})
            executable = app_info.get(platform, app)

            if platform == "win32":
                # Windows: use start command
                subprocess.Popen(
                    f"start {executable}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif platform == "darwin":
                # macOS: use open command
                subprocess.Popen(
                    ["open", "-a", executable],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                # Linux: direct execution
                subprocess.Popen(
                    executable.split(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            logger.info(f"Opened application: {app}")
            return f"Opened {app}"

        except Exception as e:
            logger.error(f"Failed to open {app}: {e}")
            return f"Failed to open {app}: {e}"

    return await loop.run_in_executor(None, open_sync)


async def _close_app(params: dict[str, Any]) -> str:
    """Close an application.

    Args:
        params: Parameters with 'app' key

    Returns:
        Result message
    """
    app = params.get("app")
    if not app:
        return "No application specified"

    loop = asyncio.get_event_loop()

    def close_sync() -> str:
        try:
            import psutil

            app_info = APP_EXECUTABLES.get(app, {})
            executable = app_info.get(sys.platform, app)

            # Find and terminate processes
            terminated = False
            for proc in psutil.process_iter(["name"]):
                try:
                    proc_name = proc.info["name"].lower()
                    if executable.lower() in proc_name or app.lower() in proc_name:
                        proc.terminate()
                        terminated = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if terminated:
                logger.info(f"Closed application: {app}")
                return f"Closed {app}"
            else:
                return f"{app} is not running"

        except ImportError:
            return "psutil not available"
        except Exception as e:
            logger.error(f"Failed to close {app}: {e}")
            return f"Failed to close {app}: {e}"

    return await loop.run_in_executor(None, close_sync)


async def _set_volume(params: dict[str, Any]) -> str:
    """Set system volume.

    Args:
        params: Parameters with 'level' (0-100) or 'direction' (up/down)

    Returns:
        Result message
    """
    level = params.get("level")
    direction = params.get("direction")

    loop = asyncio.get_event_loop()

    def set_vol_sync() -> str:
        try:
            if sys.platform == "win32":
                return _set_volume_windows(level, direction)
            else:
                return _set_volume_linux(level, direction)
        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            return f"Failed to set volume: {e}"

    return await loop.run_in_executor(None, set_vol_sync)


def _set_volume_windows(level: int | None, direction: str | None) -> str:
    """Set volume on Windows using pycaw.

    Args:
        level: Volume level (0-100)
        direction: Volume direction (up/down)

    Returns:
        Result message
    """
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        current = volume.GetMasterVolumeLevelScalar()

        if level is not None:
            new_level = max(0, min(100, level)) / 100.0
            volume.SetMasterVolumeLevelScalar(new_level, None)
            return f"Volume set to {level}%"

        elif direction == "up":
            new_level = min(1.0, current + 0.1)
            volume.SetMasterVolumeLevelScalar(new_level, None)
            return f"Volume increased to {int(new_level * 100)}%"

        elif direction == "down":
            new_level = max(0.0, current - 0.1)
            volume.SetMasterVolumeLevelScalar(new_level, None)
            return f"Volume decreased to {int(new_level * 100)}%"

        return f"Current volume: {int(current * 100)}%"

    except ImportError:
        return "pycaw not available (Windows only)"


def _set_volume_linux(level: int | None, direction: str | None) -> str:
    """Set volume on Linux using amixer.

    Args:
        level: Volume level (0-100)
        direction: Volume direction (up/down)

    Returns:
        Result message
    """
    try:
        if level is not None:
            subprocess.run(
                ["amixer", "set", "Master", f"{level}%"],
                capture_output=True,
                check=True,
            )
            return f"Volume set to {level}%"

        elif direction == "up":
            subprocess.run(
                ["amixer", "set", "Master", "10%+"],
                capture_output=True,
                check=True,
            )
            return "Volume increased"

        elif direction == "down":
            subprocess.run(
                ["amixer", "set", "Master", "10%-"],
                capture_output=True,
                check=True,
            )
            return "Volume decreased"

        return "Volume unchanged"

    except subprocess.CalledProcessError as e:
        return f"amixer error: {e}"
    except FileNotFoundError:
        return "amixer not found"


async def _mute_toggle(params: dict[str, Any]) -> str:
    """Toggle system mute.

    Args:
        params: Unused

    Returns:
        Result message
    """
    loop = asyncio.get_event_loop()

    def toggle_sync() -> str:
        try:
            if sys.platform == "win32":
                return _mute_toggle_windows()
            else:
                return _mute_toggle_linux()
        except Exception as e:
            logger.error(f"Failed to toggle mute: {e}")
            return f"Failed to toggle mute: {e}"

    return await loop.run_in_executor(None, toggle_sync)


def _mute_toggle_windows() -> str:
    """Toggle mute on Windows."""
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        current_mute = volume.GetMute()
        volume.SetMute(not current_mute, None)

        return "Audio muted" if not current_mute else "Audio unmuted"

    except ImportError:
        return "pycaw not available"


def _mute_toggle_linux() -> str:
    """Toggle mute on Linux."""
    try:
        subprocess.run(
            ["amixer", "set", "Master", "toggle"],
            capture_output=True,
            check=True,
        )
        return "Audio toggled"
    except subprocess.CalledProcessError as e:
        return f"amixer error: {e}"
    except FileNotFoundError:
        return "amixer not found"


async def _screenshot(params: dict[str, Any]) -> str:
    """Take a screenshot.

    Args:
        params: Unused

    Returns:
        Result message with file path
    """
    loop = asyncio.get_event_loop()

    def screenshot_sync() -> str:
        try:
            import pyautogui

            # Determine save location
            if sys.platform == "win32":
                desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
            else:
                desktop = Path.home() / "Desktop"

            if not desktop.exists():
                desktop = Path.home()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = desktop / f"screenshot_{timestamp}.png"

            # Take screenshot
            screenshot = pyautogui.screenshot()
            screenshot.save(str(filename))

            logger.info(f"Screenshot saved: {filename}")
            return f"Screenshot saved to {filename}"

        except ImportError:
            return "pyautogui not available"
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return f"Screenshot failed: {e}"

    return await loop.run_in_executor(None, screenshot_sync)


async def _type_text(params: dict[str, Any]) -> str:
    """Type text using keyboard.

    Args:
        params: Parameters with 'text' key

    Returns:
        Result message
    """
    text = params.get("text", "")
    if not text:
        return "No text to type"

    loop = asyncio.get_event_loop()

    def type_sync() -> str:
        try:
            import pyautogui

            # Small delay before typing
            pyautogui.sleep(0.5)
            pyautogui.typewrite(text, interval=0.02)

            logger.info(f"Typed text: {text[:50]}...")
            return "Text typed"

        except ImportError:
            return "pyautogui not available"
        except Exception as e:
            logger.error(f"Type text failed: {e}")
            return f"Type text failed: {e}"

    return await loop.run_in_executor(None, type_sync)
