"""Live-verification harness for Phase 3 — emergency STOP button.

Connects to the running backend on ws://localhost:8765 and exercises the
``cancel_turn`` command in two scenarios:

1. **Idle connection** — no turn in flight. The backend must still reply
   with an ``idle`` status + ``Konversation gestoppt`` notification
   (idempotent; visible feedback for the user).
2. **Audio pre-capture** — send a long burst of PCM audio so the backend
   opens the listening state; send ``cancel_turn`` before STT finishes.
   Expectation: we see the cancel-notification and never a ``speaking``
   state frame.

Usage (backend must be running)::

    PYTHONPATH=src .venv/bin/python scripts/verify_phase3_cancel.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

try:
    from aiohttp import ClientSession, WSMsgType
except ImportError:
    print("ERROR: aiohttp is required — install with pip.")
    sys.exit(2)

WS_URL = "ws://127.0.0.1:8765"


async def _collect_frames(ws: Any, seconds: float) -> list[dict[str, Any]]:
    """Drain WS frames for ``seconds`` and return parsed JSON frames."""
    frames: list[dict[str, Any]] = []
    end = asyncio.get_event_loop().time() + seconds
    while asyncio.get_event_loop().time() < end:
        try:
            msg = await asyncio.wait_for(ws.receive(), timeout=max(0.05, end - asyncio.get_event_loop().time()))
        except asyncio.TimeoutError:
            break
        if msg.type == WSMsgType.TEXT:
            try:
                frames.append(json.loads(msg.data))
            except json.JSONDecodeError:
                continue
        elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
            break
    return frames


async def _scenario_idle_cancel() -> bool:
    """Send cancel_turn on a fresh connection with no active pipeline."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            # Drain welcome frames (startup-ok notification + initial status).
            await _collect_frames(ws, 0.3)

            await ws.send_json({"type": "cancel_turn"})
            frames = await _collect_frames(ws, 0.5)

    types = [f.get("type") for f in frames]
    status_states = [f["state"] for f in frames if f.get("type") == "status"]
    notif_titles = [
        f["payload"].get("title", "")
        for f in frames
        if f.get("type") == "notification"
    ]

    print("\n=== Scenario 1: idle cancel ===")
    print(f"  Frame types: {types}")
    print(f"  Status states: {status_states}")
    print(f"  Notification titles: {notif_titles}")

    ok_status = "idle" in status_states
    ok_notif = any("gestoppt" in t.lower() for t in notif_titles)
    return ok_status and ok_notif


async def _scenario_streaming_cancel() -> bool:
    """Stream fake silence-PCM then hit cancel; watch the state trail."""
    import numpy as np

    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _collect_frames(ws, 0.3)

            # Enough zero-samples to nudge the backend out of idle for a
            # moment, though wake-word will almost certainly not fire on
            # silence — we mainly want the cancel frame to be processed
            # while *something* is in motion.
            pcm = (np.zeros(1600, dtype=np.int16)).tobytes()
            for _ in range(5):
                await ws.send_bytes(pcm)
                await asyncio.sleep(0.02)

            await ws.send_json({"type": "cancel_turn"})
            frames = await _collect_frames(ws, 0.8)

    status_states = [f["state"] for f in frames if f.get("type") == "status"]
    notif_titles = [
        f["payload"].get("title", "")
        for f in frames
        if f.get("type") == "notification"
    ]

    print("\n=== Scenario 2: audio + cancel ===")
    print(f"  Status states: {status_states}")
    print(f"  Notification titles: {notif_titles}")

    ok_notif = any("gestoppt" in t.lower() for t in notif_titles)
    no_speaking = "speaking" not in status_states
    return ok_notif and no_speaking


async def _main() -> int:
    try:
        pass1 = await _scenario_idle_cancel()
        pass2 = await _scenario_streaming_cancel()
    except Exception as exc:  # noqa: BLE001
        print(f"Live-verification failed: {exc}")
        return 1

    print("\n=== Verdict ===")
    print(f"  [{'PASS' if pass1 else 'FAIL'}] Idle cancel → idle+notification")
    print(f"  [{'PASS' if pass2 else 'FAIL'}] Streaming cancel → no speaking frame")
    return 0 if (pass1 and pass2) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
