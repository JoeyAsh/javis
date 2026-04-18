#!/usr/bin/env python3
"""Smoke test for the JARVIS voice pipeline over WebSocket.

Connects to the JARVIS backend, drives a turn via the text-transcript path,
and asserts that at least one ``status=speaking`` frame and one ``audio``
frame arrive within 15 s.

Usage (backend must be running):
    PYTHONPATH=src .venv/bin/python scripts/voice_pipeline_smoke.py

Exit codes:
    0 — pipeline produced speaking + audio frames as expected.
    1 — assertion failed or timeout reached.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

import websockets  # type: ignore[import]

WS_URL = "ws://127.0.0.1:8765"
TIMEOUT_S = 15.0
TRANSCRIPT_FRAME = json.dumps(
    {"type": "transcript", "text": "Was ist 2 plus 2?", "isFinal": True}
)


async def run_smoke() -> None:
    """Connect, send a typed transcript turn, and assert pipeline response."""
    print(f"[smoke] Connecting to {WS_URL} …")

    async with websockets.connect(WS_URL) as ws:
        print("[smoke] Connected.")

        # Wait for the initial idle status frame before sending the turn.
        initial = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
        print(f"[smoke] Initial frame: {initial}")

        # Send the typed query.
        await ws.send(TRANSCRIPT_FRAME)
        print(f"[smoke] Sent: {TRANSCRIPT_FRAME[:80]}")

        got_speaking = False
        got_audio = False

        deadline = time.monotonic() + TIMEOUT_S

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 2.0))
            except asyncio.TimeoutError:
                continue

            try:
                msg: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[smoke] Non-JSON frame: {raw[:80]}")
                continue

            msg_type = msg.get("type")
            print(f"[smoke] Received: type={msg_type}", end="")

            if msg_type == "status":
                print(f" state={msg.get('state')}")
                if msg.get("state") == "speaking":
                    got_speaking = True
            elif msg_type == "audio":
                data_len = len(msg.get("data", ""))
                print(f" data_len={data_len} text={msg.get('text', '')[:40]!r}")
                if data_len > 0:
                    got_audio = True
            else:
                print()

            if got_speaking and got_audio:
                break

        if not got_speaking:
            print("[smoke] FAIL: no status=speaking frame received")
            sys.exit(1)
        if not got_audio:
            print("[smoke] FAIL: no audio frame received")
            sys.exit(1)

        print("[smoke] PASS: received status=speaking + audio frames.")


def main() -> None:
    """Entry point."""
    try:
        asyncio.run(run_smoke())
    except Exception as exc:
        print(f"[smoke] ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
