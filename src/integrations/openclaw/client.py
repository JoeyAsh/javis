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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncIterator

import httpx

from utils.logger import get_logger

if TYPE_CHECKING:
    from integrations.openclaw.ws_client import OpenClawWSClient, StreamChunk

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

    # OpenClaw CLI accepts: off | minimal | low | medium | high | xhigh.
    # We keep the historical config alias "normal" mapped to the nearest
    # valid level so existing configs don't need to change.
    _THINKING_ALIASES: dict[str, str] = {
        "normal": "medium",
        "none": "off",
    }
    _THINKING_VALID: set[str] = {
        "off",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize OpenClaw client.

        Args:
            config: openclaw section from config.yaml containing:
                - gateway_url: Gateway URL (default: http://127.0.0.1:18789)
                - session_id: Default session ID (default: jarvis-main)
                - thinking_level: Thinking level. Accepts the OpenClaw
                  CLI's levels (``off|minimal|low|medium|high|xhigh``)
                  and legacy aliases (``normal`` → ``medium``,
                  ``none`` → ``off``). Default: ``medium``.
                - timeout_seconds: Request timeout (default: 30)
                - streaming_enabled: Use persistent WS streaming (default: True)
                - ws_reconnect_max_seconds: WS reconnect backoff cap (default: 30)
        """
        self._config = config
        self._gateway_url = config.get("gateway_url", "http://127.0.0.1:18789")
        self._session_id = config.get("session_id", "jarvis-main")
        self._thinking = self._normalize_thinking(
            config.get("thinking_level", "medium")
        )
        self._timeout = config.get("timeout_seconds", 30)
        self._http: httpx.AsyncClient | None = None
        self._enabled = config.get("enabled", True)
        self._streaming_enabled = config.get("streaming_enabled", True)
        self.ws_client: OpenClawWSClient | None = None

    @classmethod
    def _normalize_thinking(cls, level: str) -> str:
        """Map legacy thinking aliases onto OpenClaw's current vocabulary.

        Unknown values fall back to ``medium`` with a warning.
        """
        level = (level or "medium").strip().lower()
        if level in cls._THINKING_VALID:
            return level
        if level in cls._THINKING_ALIASES:
            return cls._THINKING_ALIASES[level]
        logger.warning(
            f"Unknown OpenClaw thinking level '{level}', defaulting to 'medium'"
        )
        return "medium"

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

        # Optionally set up a persistent WS client for streaming.
        if self._streaming_enabled and self._enabled:
            await self._init_ws_client()

    async def close(self) -> None:
        """Close HTTP client and WS client."""
        if self.ws_client is not None:
            try:
                await self.ws_client.close()
            except Exception as exc:
                logger.warning(f"WS client close error: {exc}")
            self.ws_client = None

        if self._http:
            await self._http.aclose()
            self._http = None
            logger.debug("OpenClaw client closed")

    async def _init_ws_client(self) -> None:
        """Attempt to connect the persistent WS client; log and continue on failure."""
        from integrations.openclaw.ws_client import OpenClawWSClient

        ws_url = self._gateway_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        try:
            self.ws_client = OpenClawWSClient(
                gateway_url=ws_url,
                agent_id="main",
                time_to_first_token_s=self._config.get(
                    "stream_time_to_first_token_seconds", 60
                ),
                inter_delta_timeout_s=self._config.get(
                    "stream_inter_delta_timeout_seconds", 20
                ),
            )
            await self.ws_client.connect()
            logger.info(f"OpenClaw WS streaming client connected to {ws_url}")
        except Exception as exc:
            logger.warning(
                f"OpenClaw WS client failed to connect ({exc}); "
                "falling back to subprocess mode"
            )
            self.ws_client = None

    async def query_agent_stream(
        self,
        message: str,
        session_id: str | None = None,
        thinking: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream agent response chunks.

        Delegates to the persistent WS client when available; otherwise
        calls :meth:`query_agent` and wraps the result in a single
        ``final`` :class:`~integrations.openclaw.ws_client.StreamChunk`.

        Args:
            message: User message.
            session_id: Session ID (default: configured session).
            thinking: Thinking level override.

        Yields:
            :class:`~integrations.openclaw.ws_client.StreamChunk` objects.
        """
        from integrations.openclaw.ws_client import StreamChunk  # local import

        session = session_id or self._session_id

        if self.ws_client is not None and self.ws_client.is_connected:
            think_level = (
                self._normalize_thinking(thinking) if thinking else self._thinking
            )
            async for chunk in self.ws_client.query_agent_stream(
                message, session_id=session, thinking=think_level
            ):
                yield chunk
            return

        # Fallback: one-shot subprocess call → single final chunk.
        logger.debug("WS streaming unavailable — falling back to subprocess query")
        response = await self.query_agent(
            message, session_id=session, thinking=thinking
        )

        if response.error:
            yield StreamChunk(
                type="error",
                run_id="subprocess",
                new_text="",
                full_text="",
                error=response.error,
            )
        else:
            yield StreamChunk(
                type="final",
                run_id="subprocess",
                new_text=response.text,
                full_text=response.text,
            )

    async def abort_current_run(self, session_id: str, run_id: str) -> None:
        """Abort a running agent turn via the WS gateway.

        No-op if the WS client is not available.

        Args:
            session_id: Session containing the run.
            run_id: The run ID to abort.
        """
        if self.ws_client is not None and self.ws_client.is_connected:
            await self.ws_client.abort(session_id, run_id)
        else:
            logger.debug(
                f"abort_current_run: WS unavailable — no-op for run_id={run_id}"
            )

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
        """Check if OpenClaw gateway is running and reachable.

        Pings the gateway HTTP endpoint directly instead of shelling out to
        `openclaw doctor` — doctor runs full diagnostics (slow, seconds-long)
        while a simple HTTP HEAD / GET returns immediately. The gateway
        returns HTTP 200 on the root path when it is up.

        Returns:
            True if the gateway responds with HTTP 200 within 2 s.
        """
        if not self._enabled:
            return False

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(self._gateway_url)
                return response.status_code == 200
        except httpx.RequestError as e:
            logger.debug(f"OpenClaw gateway unreachable: {e}")
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
        think_level = self._normalize_thinking(thinking) if thinking else self._thinking

        logger.debug(f"Querying OpenClaw agent (session-id: {session})")

        # Use CLI for now; switch to REST when available. Flag name is
        # ``--session-id`` in the current OpenClaw CLI (>= 2026.4.x).
        cmd = [
            "openclaw",
            "agent",
            "--message",
            message,
            "--session-id",
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

            # Parse JSON response.
            #
            # OpenClaw CLI >= 2026.4.x returns a run envelope:
            #   { runId, status, summary,
            #     result: { payloads: [ { text, mediaUrl } ],
            #               meta: { finalAssistantVisibleText, ... } } }
            # Older versions (kept for defensive compatibility) returned a
            # flat { response|text, thinking_used, tool_calls } shape.
            try:
                data = json.loads(stdout.decode())

                # New envelope — prefer `meta.finalAssistantVisibleText`
                # (already post-processed / visible to user); fall back to
                # concatenated payload texts.
                text = ""
                result = data.get("result") if isinstance(data, dict) else None
                if isinstance(result, dict):
                    meta = result.get("meta") or {}
                    if isinstance(meta, dict):
                        text = (
                            meta.get("finalAssistantVisibleText")
                            or meta.get("finalAssistantRawText")
                            or ""
                        )
                    if not text:
                        payloads = result.get("payloads") or []
                        if isinstance(payloads, list):
                            text = "\n".join(
                                p.get("text", "")
                                for p in payloads
                                if isinstance(p, dict) and p.get("text")
                            )

                # Legacy fallback for older CLIs / mocks.
                if not text:
                    text = data.get("response") or data.get("text") or ""

                return AgentResponse(
                    text=text,
                    session_id=session,
                    thinking_used=bool(data.get("thinking_used", False)),
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
