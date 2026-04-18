"""OpenClaw integration package for JARVIS.

OpenClaw serves as the agent-runtime backbone, handling:
- Agent routing and tool execution
- Conversational memory and context
- Third-party integrations (Gmail, Spotify, GitHub, etc.)

JARVIS retains ownership of:
- Voice pipeline (wake word, STT, TTS)
- 3D orb HUD and panel system
- Govee LED integration (no OpenClaw skill)
- Voice UX (barge-in, fillers, streaming)

Example usage:
    from integrations.openclaw import OpenClawClient

    client = OpenClawClient(config["openclaw"])
    await client.initialize()

    # Query the agent
    response = await client.query_agent("What's the weather today?")
    print(response.text)

    # Check health
    if not await client.is_healthy():
        logger.warning("OpenClaw daemon not running")

    await client.close()
"""

from integrations.openclaw.client import (
    AgentResponse,
    OpenClawClient,
    OpenClawConnectionError,
    OpenClawNotInstalledError,
    SessionInfo,
)
from integrations.openclaw.ws_client import OpenClawWSClient, StreamChunk

__all__ = [
    "OpenClawClient",
    "OpenClawWSClient",
    "StreamChunk",
    "AgentResponse",
    "SessionInfo",
    "OpenClawConnectionError",
    "OpenClawNotInstalledError",
]
