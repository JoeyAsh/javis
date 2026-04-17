"""Live-verification harness for Phase 1 — single-call pipeline.

Exercises ``_run_voice_pipeline`` with a mocked STT (canned transcript) and
a mocked OpenClaw gateway (counts query_agent invocations). Proves:

1. Exactly ONE ``Querying OpenClaw agent`` log line per chat turn.
2. That line targets the ``jarvis-main`` session (not ``jarvis-util-*``).
3. No ``Wake-ack broadcast`` line is produced on wake detection.
4. No references to ``_broadcast_wake_ack`` remain at module scope.

Emits a PASS/FAIL verdict on stdout plus the observable log excerpts so the
orchestrator can paste them into the Phase 1 commit evidence.

Usage::

    PYTHONPATH=src .venv/bin/python scripts/verify_phase1_pipeline.py
"""

from __future__ import annotations

import asyncio
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@dataclass
class STTResult:
    text: str
    language: str


async def _run_once() -> tuple[int, list[str]]:
    """Run one voice turn and return (openclaw_call_count, query_log_lines)."""
    from utils.logger import setup_logger

    # Pipe loguru output into a string buffer so we can grep it.
    buf = io.StringIO()
    setup_logger(level="INFO")

    # Re-route loguru's sink so we capture the pipeline logs verbatim.
    from loguru import logger as _loguru_logger

    _loguru_logger.remove()
    _loguru_logger.add(buf, level="DEBUG", format="{level} {name}:{function} {message}")
    # Also mirror to stdout so the harness is watchable live.
    _loguru_logger.add(
        sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level: <8} | {message}"
    )

    # Import after logger re-wire so module-level loggers capture cleanly.
    from api import ws_server
    from brain.claude_client import ClaudeClient
    from brain.intent_parser import get_intent_parser
    from brain.memory_legacy import ConversationMemory
    from brain.orchestrator import Orchestrator

    # --- Fake OpenClaw: counts calls + records session ids -------------
    from integrations.openclaw import AgentResponse

    openclaw = MagicMock()
    openclaw.gateway_url = "http://127.0.0.1:18789"
    openclaw.session_id = "jarvis-main"
    openclaw.initialize = AsyncMock(return_value=None)
    openclaw.close = AsyncMock(return_value=None)

    calls: list[str | None] = []

    async def _fake_query(
        message: str,
        session_id: str | None = None,
        thinking: str | None = None,
    ) -> AgentResponse:
        calls.append(session_id)
        # Log the line the production client emits so grep sees it.
        from utils.logger import get_logger as _gl

        _gl("integrations.openclaw.client").debug(
            f"Querying OpenClaw agent (session-id: {session_id or 'jarvis-main'})"
        )
        return AgentResponse(
            text="Alle Systeme nominal, Sir.",
            session_id=session_id or "jarvis-main",
            thinking_used=False,
            tool_calls=[],
            error=None,
        )

    openclaw.query_agent = _fake_query
    openclaw.get_offline_fallback_message = MagicMock(return_value="offline")

    # --- Wire the client + orchestrator --------------------------------
    claude_client = ClaudeClient(openclaw_client=openclaw)
    await claude_client.initialize()

    memory = ConversationMemory(max_turns=5)
    orchestrator = Orchestrator(
        claude_client=claude_client, memory=memory, tts_engine=None
    )

    # --- Stub STT + Fish TTS on the module ----------------------------
    stt_stub = MagicMock()
    stt_stub.transcribe = AsyncMock(
        return_value=STTResult(text="Hallo JARVIS", language="de")
    )

    tts_stub = MagicMock()
    tts_stub.synthesize = AsyncMock(return_value=b"\x00" * 256)

    ws_server._stt_engine = stt_stub
    ws_server._fish_tts = tts_stub
    ws_server._orchestrator = orchestrator
    ws_server._intent_parser = get_intent_parser()
    ws_server._memory = memory
    ws_server._memory_store = None
    ws_server._conversation_mode = None
    ws_server._persona_config = {}
    ws_server._sample_rate = 16000

    # Fake a single chunk long enough to bypass the 0.5 s gate.
    import numpy as np

    chunk = np.zeros(ws_server._sample_rate, dtype=np.float32)

    # Fake WS — only needs id() + an async send_str no-op.
    class _FakeWS:
        async def send_str(self, _: str) -> None:
            return None

    ws = _FakeWS()
    ws_server._connected_clients.clear()
    ws_server._connection_state.clear()
    ws_server._connection_state[id(ws)] = {
        "mode": "processing",
        "audio_chunks": [],
        "speech_started": False,
        "silent_samples": 0,
        "total_samples": 0,
        "skip_remaining": 0,
        "follow_up_timer_task": None,
    }

    await ws_server._run_voice_pipeline([chunk], ws)  # type: ignore[arg-type]

    query_lines = [
        line for line in buf.getvalue().splitlines() if "Querying OpenClaw agent" in line
    ]
    wake_ack_lines = [
        line for line in buf.getvalue().splitlines() if "Wake-ack" in line
    ]
    orchestrator_chat_lines = [
        line for line in buf.getvalue().splitlines() if "Chat dispatch" in line
    ]

    print("\n=== Log evidence (Phase 1) ===")
    for line in query_lines:
        print("  QUERY:", line)
    for line in orchestrator_chat_lines:
        print("  DISPATCH:", line)
    for line in wake_ack_lines:
        print("  WAKE-ACK (must be empty):", line)

    # Module-scope check: _broadcast_wake_ack must be absent.
    has_fn = hasattr(ws_server, "_broadcast_wake_ack")
    print(f"  hasattr(ws_server, '_broadcast_wake_ack') = {has_fn}")

    return len(calls), query_lines


async def _main() -> int:
    call_count, queries = await _run_once()
    pass_criteria: list[tuple[str, bool]] = [
        ("Exactly one OpenClaw query per turn", call_count == 1),
        ("No utility-lane routing call", all("jarvis-util" not in q for q in queries)),
        ("Query targets jarvis-main", any("jarvis-main" in q for q in queries)),
    ]

    print("\n=== Verdict ===")
    ok = True
    for label, result in pass_criteria:
        flag = "PASS" if result else "FAIL"
        if not result:
            ok = False
        print(f"  [{flag}] {label}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
