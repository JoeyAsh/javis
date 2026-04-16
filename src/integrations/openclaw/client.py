"""OpenClaw client for JARVIS agent-runtime integration.

Provides async interface to OpenClaw gateway for:
- Agent queries with session management
- Message sending via OpenClaw channels
- Session history and management
- Health checks and diagnostics

OpenClaw handles all agent routing, memory, and third-party integrations,
while JARVIS owns the voice pipeline and HUD.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from typing import Any

import httpx

from utils.logger import get_logger

logger = get_logger("openclaw_client")


@dataclass
class AgentResponse:
    """Response from OpenClaw agent query."""

    text: str
    session_id: str
    thinking_used: bool
    tool_calls: list[dict[str, Any]]
    error: str | None = None


@dataclass
class SessionInfo:
    """OpenClaw session information."""

    session_id: str
    created_at: str
    message_count: int
    model: str


class OpenClawConnectionError(Exception):
    """Raised when OpenClaw gateway is not reachable."""

    pass


class OpenClawNotInstalledError(Exception):
    """Raised when OpenClaw CLI is not installed."""

    pass


class OpenClawClient:
    """Async client for OpenClaw gateway interaction.

    Uses OpenClaw CLI for communication. REST API support may be added
    when OpenClaw provides stable documentation.

    Attributes:
        gateway_url: URL of the OpenClaw gateway.
        session_id: Default session ID for queries.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize OpenClaw client.

        Args:
            config: openclaw section from config.yaml containing:
                - gateway_url: Gateway URL (default: http://127.0.0.1:18789)
                - session_id: Default session ID (default: jarvis-main)
                - thinking_level: Thinking level (default: normal)
                - timeout_seconds: Request timeout (default: 30)
        """
        self._config = config
        self._gateway_url = config.get("gateway_url", "http://127.0.0.1:18789")
        self._session_id = config.get("session_id", "jarvis-main")
        self._thinking = config.get("thinking_level", "normal")
        self._timeout = config.get("timeout_seconds", 30)
        self._http: httpx.AsyncClient | None = None
        self._enabled = config.get("enabled", True)

    @property
    def gateway_url(self) -> str:
        """Return the gateway URL."""
        return self._gateway_url

    @property
    def session_id(self) -> str:
        """Return the default session ID."""
        return self._session_id

    @property
    def is_enabled(self) -> bool:
        """Check if OpenClaw integration is enabled."""
        return self._enabled

    async def initialize(self) -> None:
        """Initialize client and verify gateway connection.

        Raises:
            OpenClawNotInstalledError: If OpenClaw CLI is not installed.
            OpenClawConnectionError: If gateway is not reachable.
        """
        if not self._enabled:
            logger.info("OpenClaw integration disabled in config")
            return

        logger.info(f"Initializing OpenClaw client (gateway: {self._gateway_url})")

        # Check if openclaw is installed
        if not await self._is_cli_available():
            raise OpenClawNotInstalledError(
                "OpenClaw CLI not found. Install with: npm install -g openclaw"
            )

        # Initialize HTTP client for potential REST API use
        self._http = httpx.AsyncClient(
            base_url=self._gateway_url,
            timeout=self._timeout,
        )

        # Verify gateway is running
        if not await self.is_healthy():
            logger.warning(
                f"OpenClaw gateway not reachable at {self._gateway_url}. "
                "Run 'openclaw onboard --install-daemon' to set up the daemon."
            )
            # Don't raise - allow graceful degradation
        else:
            logger.info("OpenClaw gateway connection verified")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http:
            await self._http.aclose()
            self._http = None
            logger.debug("OpenClaw client closed")

    async def _is_cli_available(self) -> bool:
        """Check if OpenClaw CLI is installed.

        Returns:
            True if openclaw command is available.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "openclaw",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            return proc.returncode == 0
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.debug(f"Error checking OpenClaw CLI: {e}")
            return False

    async def is_healthy(self) -> bool:
        """Check if OpenClaw gateway is running and healthy.

        Uses 'openclaw doctor' command to verify system health.

        Returns:
            True if gateway is healthy.
        """
        if not self._enabled:
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "openclaw",
                "doctor",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=10)
            return proc.returncode == 0
        except FileNotFoundError:
            logger.warning("OpenClaw CLI not found")
            return False
        except asyncio.TimeoutError:
            logger.warning("OpenClaw doctor timed out")
            return False
        except Exception as e:
            logger.warning(f"OpenClaw health check failed: {e}")
            return False

    async def query_agent(
        self,
        message: str,
        session_id: str | None = None,
        thinking: str | None = None,
    ) -> AgentResponse:
        """Query the OpenClaw agent.

        Args:
            message: User message to send.
            session_id: Session ID (default: configured session).
            thinking: Thinking level override ("none", "normal", "high").

        Returns:
            AgentResponse with text and metadata.
        """
        if not self._enabled:
            return AgentResponse(
                text="OpenClaw integration is disabled.",
                session_id=session_id or self._session_id,
                thinking_used=False,
                tool_calls=[],
                error="OpenClaw integration disabled",
            )

        session = session_id or self._session_id
        think_level = thinking or self._thinking

        logger.debug(f"Querying OpenClaw agent (session: {session})")

        # Use CLI for now; switch to REST when available
        cmd = [
            "openclaw",
            "agent",
            "--message",
            message,
            "--session",
            session,
            "--thinking",
            think_level,
            "--json",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout,
            )

            if proc.returncode != 0:
                error_msg = stderr.decode().strip() or "Unknown error"
                logger.error(f"OpenClaw agent query failed: {error_msg}")
                return AgentResponse(
                    text="",
                    session_id=session,
                    thinking_used=False,
                    tool_calls=[],
                    error=error_msg,
                )

            # Parse JSON response
            try:
                data = json.loads(stdout.decode())
                return AgentResponse(
                    text=data.get("response", data.get("text", "")),
                    session_id=session,
                    thinking_used=data.get("thinking_used", False),
                    tool_calls=data.get("tool_calls", []),
                )
            except json.JSONDecodeError:
                # Fallback: treat stdout as plain text
                return AgentResponse(
                    text=stdout.decode().strip(),
                    session_id=session,
                    thinking_used=False,
                    tool_calls=[],
                )

        except asyncio.TimeoutError:
            logger.error(f"OpenClaw agent query timed out after {self._timeout}s")
            return AgentResponse(
                text="",
                session_id=session,
                thinking_used=False,
                tool_calls=[],
                error="Request timed out",
            )
        except FileNotFoundError:
            logger.error("OpenClaw CLI not found")
            return AgentResponse(
                text="",
                session_id=session,
                thinking_used=False,
                tool_calls=[],
                error="OpenClaw CLI not installed",
            )
        except Exception as e:
            logger.error(f"OpenClaw agent query error: {e}")
            return AgentResponse(
                text="",
                session_id=session,
                thinking_used=False,
                tool_calls=[],
                error=str(e),
            )

    async def send_message(
        self,
        channel: str,
        to: str,
        text: str,
    ) -> bool:
        """Send a message via OpenClaw channel.

        Args:
            channel: Channel name (whatsapp, telegram, slack, etc.).
            to: Recipient identifier.
            text: Message text.

        Returns:
            True if sent successfully.
        """
        if not self._enabled:
            return False

        cmd = [
            "openclaw",
            "message",
            "send",
            "--channel",
            channel,
            "--to",
            to,
            "--message",
            text,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=self._timeout)
            success = proc.returncode == 0
            if success:
                logger.debug(f"Message sent via {channel} to {to}")
            else:
                logger.warning(f"Failed to send message via {channel}")
            return success
        except Exception as e:
            logger.error(f"Error sending message via {channel}: {e}")
            return False

    async def list_sessions(self) -> list[SessionInfo]:
        """List all active sessions.

        Returns:
            List of SessionInfo objects.
        """
        if not self._enabled:
            return []

        cmd = ["openclaw", "sessions", "list", "--json"]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout,
            )

            data = json.loads(stdout.decode())
            return [
                SessionInfo(
                    session_id=s["id"],
                    created_at=s.get("created_at", ""),
                    message_count=s.get("message_count", 0),
                    model=s.get("model", ""),
                )
                for s in data.get("sessions", [])
            ]
        except (json.JSONDecodeError, asyncio.TimeoutError, FileNotFoundError):
            return []
        except Exception as e:
            logger.warning(f"Error listing sessions: {e}")
            return []

    async def get_session_history(
        self,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get session conversation history.

        Args:
            session_id: Session to query (default: configured session).
            limit: Max messages to return.

        Returns:
            List of message dictionaries.
        """
        if not self._enabled:
            return []

        session = session_id or self._session_id
        cmd = [
            "openclaw",
            "sessions",
            "history",
            "--session",
            session,
            "--limit",
            str(limit),
            "--json",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout,
            )

            data = json.loads(stdout.decode())
            return data.get("messages", [])
        except (json.JSONDecodeError, asyncio.TimeoutError, FileNotFoundError):
            return []
        except Exception as e:
            logger.warning(f"Error getting session history: {e}")
            return []

    async def reset_session(self, session_id: str | None = None) -> bool:
        """Reset/clear a session.

        Args:
            session_id: Session to reset (default: configured session).

        Returns:
            True if reset successfully.
        """
        if not self._enabled:
            return False

        session = session_id or self._session_id
        cmd = ["openclaw", "sessions", "reset", "--session", session]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=self._timeout)
            success = proc.returncode == 0
            if success:
                logger.info(f"Session {session} reset")
            return success
        except Exception as e:
            logger.error(f"Error resetting session: {e}")
            return False

    def get_offline_fallback_message(self, language: str = "en") -> str:
        """Get a voice-friendly offline fallback message.

        Args:
            language: Language code.

        Returns:
            Fallback message for TTS.
        """
        messages = {
            "en": (
                "Sir, I'm having trouble reaching the OpenClaw gateway. "
                "Please verify the daemon is running with 'openclaw doctor'."
            ),
            "de": (
                "Sir, ich habe Schwierigkeiten, das OpenClaw-Gateway zu erreichen. "
                "Bitte prüfen Sie mit 'openclaw doctor', ob der Daemon läuft."
            ),
        }
        return messages.get(language, messages["en"])
