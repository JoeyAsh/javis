"""WebSocket and HTTP server for JARVIS.

Provides real-time communication between the backend and frontend clients.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import psutil
from aiohttp import web

from src.brain.memory import ConversationMemory
from src.utils.logger import get_logger

logger = get_logger("ws_server")

# Store connected WebSocket clients
_connected_clients: set[web.WebSocketResponse] = set()

# Store global references for broadcasting
_memory: ConversationMemory | None = None
_tts_engine: Any = None
_system_agent: Any = None
_start_time: float = time.time()


async def broadcast_state(state: str) -> None:
    """Broadcast state change to all connected clients.

    Args:
        state: Current orb state (idle, listening, thinking, speaking)
    """
    message = json.dumps({"type": "state", "payload": state})
    await _broadcast(message)


async def broadcast_transcript(role: str, text: str) -> None:
    """Broadcast transcript entry to all connected clients.

    Args:
        role: Speaker role (user or jarvis)
        text: Transcript text
    """
    message = json.dumps({"type": "transcript", "payload": {"role": role, "text": text}})
    await _broadcast(message)


async def broadcast_system_metrics() -> None:
    """Broadcast system metrics to all connected clients."""
    uptime_seconds = int(time.time() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        uptime_str = f"{hours}h {minutes}m"
    elif minutes > 0:
        uptime_str = f"{minutes}m {seconds}s"
    else:
        uptime_str = f"{seconds}s"

    message = json.dumps({
        "type": "system",
        "payload": {
            "cpu": psutil.cpu_percent(interval=None),
            "mem": psutil.virtual_memory().percent,
            "uptime": uptime_str,
        },
    })
    await _broadcast(message)


async def _broadcast(message: str) -> None:
    """Broadcast a message to all connected clients.

    Args:
        message: JSON string to broadcast
    """
    if not _connected_clients:
        return

    disconnected = set()
    for ws in _connected_clients:
        try:
            await ws.send_str(message)
        except Exception as e:
            logger.warning(f"Failed to send to client: {e}")
            disconnected.add(ws)

    # Clean up disconnected clients
    _connected_clients.difference_update(disconnected)


async def _system_metrics_loop() -> None:
    """Background task to broadcast system metrics every 5 seconds."""
    while True:
        try:
            await broadcast_system_metrics()
        except Exception as e:
            logger.error(f"Error broadcasting system metrics: {e}")
        await asyncio.sleep(5)


async def _handle_command(data: dict[str, Any]) -> None:
    """Handle incoming WebSocket command.

    Args:
        data: Parsed command data
    """
    global _memory, _tts_engine, _system_agent

    cmd_type = data.get("type")
    payload = data.get("payload", {})

    if cmd_type == "set_voice":
        profile = payload.get("profile")
        if profile and _tts_engine:
            try:
                if hasattr(_tts_engine, "set_voice_profile"):
                    _tts_engine.set_voice_profile(profile)
                    logger.info(f"Voice profile changed to: {profile}")
            except Exception as e:
                logger.error(f"Failed to change voice profile: {e}")

    elif cmd_type == "reset":
        if _memory:
            _memory.clear()
            logger.info("Memory cleared via WebSocket command")

    else:
        logger.warning(f"Unknown command type: {cmd_type}")


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """Handle WebSocket connections.

    Args:
        request: aiohttp request object

    Returns:
        WebSocket response
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    _connected_clients.add(ws)
    logger.info(f"Client connected. Total clients: {len(_connected_clients)}")

    # Send initial state
    await ws.send_str(json.dumps({"type": "state", "payload": "idle"}))
    await broadcast_system_metrics()

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await _handle_command(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {msg.data}")
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")
    finally:
        _connected_clients.discard(ws)
        logger.info(f"Client disconnected. Total clients: {len(_connected_clients)}")

    return ws


async def voices_handler(request: web.Request) -> web.Response:
    """Handle GET /voices endpoint.

    Args:
        request: aiohttp request object

    Returns:
        JSON response with list of voice profiles
    """
    voices_dir = Path(__file__).parent.parent.parent / "voices"
    voices = []

    if voices_dir.exists():
        for wav_file in voices_dir.glob("*.wav"):
            if wav_file.name != "chime.wav":
                voices.append(wav_file.name)

    return web.json_response(voices)


async def start_ws_server(
    config: dict[str, Any],
    memory: ConversationMemory,
    tts_engine: Any,
) -> None:
    """Start the WebSocket and HTTP server.

    Args:
        config: API configuration section
        memory: Conversation memory instance
        tts_engine: TTS engine instance
    """
    global _memory, _tts_engine, _start_time

    _memory = memory
    _tts_engine = tts_engine
    _start_time = time.time()

    ws_port = config.get("ws_port", 8765)
    http_port = config.get("http_port", 8766)
    cors_origins = config.get("cors_origins", ["http://localhost:5173"])

    # Create aiohttp application for WebSocket
    ws_app = web.Application()
    ws_app.router.add_get("/", websocket_handler)
    ws_app.router.add_get("/ws", websocket_handler)

    # Create aiohttp application for HTTP
    http_app = web.Application()
    http_app.router.add_get("/voices", voices_handler)

    # Add CORS headers
    @web.middleware
    async def cors_middleware(request: web.Request, handler: Any) -> web.Response:
        if request.method == "OPTIONS":
            response = web.Response()
        else:
            response = await handler(request)

        origin = request.headers.get("Origin", "")
        if origin in cors_origins or "*" in cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"

        return response

    http_app.middlewares.append(cors_middleware)
    http_app.router.add_get("/voices", voices_handler)

    # Start WebSocket server
    ws_runner = web.AppRunner(ws_app)
    await ws_runner.setup()
    ws_site = web.TCPSite(ws_runner, "0.0.0.0", ws_port)
    await ws_site.start()
    logger.info(f"WebSocket server started on port {ws_port}")

    # Start HTTP server
    http_runner = web.AppRunner(http_app)
    await http_runner.setup()
    http_site = web.TCPSite(http_runner, "0.0.0.0", http_port)
    await http_site.start()
    logger.info(f"HTTP server started on port {http_port}")

    # Start system metrics broadcast loop
    asyncio.create_task(_system_metrics_loop())

    # Keep running
    while True:
        await asyncio.sleep(3600)
