"""OpenClaw client for JARVIS agent-runtime integration.

Provides async interface to OpenClaw gateway for:
- Agent queries with session management
- Message sending via OpenClaw channels
- Session history and management
- Health checks and diagnostics
- gog CLI bridge (Gmail, Calendar, Drive via the gog skill binary)

OpenClaw handles all agent routing, memory, and third-party integrations,
while JARVIS owns the voice pipeline and HUD.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator

import httpx

from utils.device import resolve_device_slug
from utils.logger import get_logger

if TYPE_CHECKING:
    from integrations.openclaw.ws_client import OpenClawWSClient, StreamChunk

logger = get_logger("openclaw_client")

# Absolute path to the stdio-bridge script.  Resolves at import time so a
# future file move surfaces immediately as an AssertionError rather than a
# silent subprocess crash.  client.py lives at src/integrations/openclaw/;
# the bridge is at src/jarvis_mcp_bridge.py — two parent hops up.
_BRIDGE_PY: str = (Path(__file__).resolve().parents[2] / "jarvis_mcp_bridge.py").as_posix()
assert Path(_BRIDGE_PY).is_file(), f"jarvis_mcp_bridge.py not found at {_BRIDGE_PY}"

_CLI_PATH_CACHE: str | None = None


def _resolve_cli_path() -> str | None:
    """Return the absolute path to the OpenClaw CLI (cached).

    Honors the ``OPENCLAW_CLI_PATH`` env-var override first, then falls back
    to ``shutil.which("openclaw")`` which correctly resolves Windows
    ``.cmd`` shims via PATHEXT.
    """
    global _CLI_PATH_CACHE
    if _CLI_PATH_CACHE is not None:
        return _CLI_PATH_CACHE
    override = os.environ.get("OPENCLAW_CLI_PATH")
    if override:
        _CLI_PATH_CACHE = override
        return override
    resolved = shutil.which("openclaw")
    if resolved:
        _CLI_PATH_CACHE = resolved
        return resolved
    return None


def _resolve_cli_argv() -> list[str] | None:
    """Return the argv prefix for spawning the OpenClaw CLI.

    On Windows, npm's global install ships a ``.cmd`` shim that delegates
    to ``node openclaw.mjs``. Spawning the ``.cmd`` through
    asyncio.create_subprocess_exec breaks on arguments containing newlines
    because Windows' cmd.exe treats ``\\n`` as a command separator. To
    avoid that, resolve to the underlying node script directly.
    """
    cli = _resolve_cli_path()
    if cli is None:
        return None
    if sys.platform == "win32" and cli.lower().endswith((".cmd", ".bat")):
        # Standard npm-global layout: <dir>\node_modules\openclaw\openclaw.mjs
        cli_dir = os.path.dirname(cli)
        script = os.path.join(cli_dir, "node_modules", "openclaw", "openclaw.mjs")
        node = shutil.which("node")
        if node and os.path.exists(script):
            return [node, script]
        logger.warning(
            f"Could not locate node+script for OpenClaw CLI wrapper {cli!r}; "
            "falling back to .cmd (may break on multiline messages)"
        )
    return [cli]


def _cli_subprocess_env() -> dict[str, str]:
    """Return an env dict for spawning the OpenClaw CLI.

    Strips OPENCLAW_GATEWAY_URL/PORT so the CLI uses its own
    ~/.openclaw/openclaw.json config and doesn't treat the env-var as a
    URL override (which requires --token on the CLI).
    """
    env = dict(os.environ)
    env.pop("OPENCLAW_GATEWAY_URL", None)
    env.pop("OPENCLAW_GATEWAY_PORT", None)
    # Allow plaintext WS to private LAN addresses (trusted network).
    env.setdefault("OPENCLAW_ALLOW_INSECURE_PRIVATE_WS", "1")
    return env


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


class GogNotInstalledError(Exception):
    """Raised when the gog CLI binary is not installed or not on PATH."""

    pass


class GogCommandError(Exception):
    """Raised when a gog CLI command exits with a non-zero status."""

    def __init__(self, message: str, spoken_message: str = "") -> None:
        """Initialise with a technical message and an optional TTS-friendly fallback."""
        super().__init__(message)
        self.spoken_message: str = spoken_message or message


# ---------------------------------------------------------------------------
# Module-level gog CLI helpers (no OpenClawClient instance needed)
# ---------------------------------------------------------------------------

_GOG_CLI_CACHE: str | None = None


def _resolve_gog_cli() -> str | None:
    """Return the absolute path to the ``gog`` binary (cached after first call)."""
    global _GOG_CLI_CACHE
    if _GOG_CLI_CACHE is not None:
        return _GOG_CLI_CACHE
    override = os.environ.get("GOG_CLI_PATH")
    if override:
        _GOG_CLI_CACHE = override
        return override
    resolved = shutil.which("gog")
    if resolved:
        _GOG_CLI_CACHE = resolved
        return resolved
    return None


async def run_gog(
    *args: str,
    timeout_seconds: float = 30.0,
    stdin_text: str | None = None,
) -> dict[str, Any] | list[Any]:
    """Execute a ``gog`` CLI command and return its parsed JSON output.

    Appends ``--json --no-input`` automatically.  All gog network calls are
    fully async via ``asyncio.create_subprocess_exec``.

    Args:
        *args: Positional CLI arguments, e.g. ``"gmail", "messages", "search",
            "is:unread in:inbox", "--max", "5"``.
        timeout_seconds: Maximum seconds to wait for the subprocess.
        stdin_text: Optional text piped to stdin (used for ``--body-file -``).

    Returns:
        Parsed JSON object (dict or list) from ``gog``'s stdout.

    Raises:
        GogNotInstalledError: When the ``gog`` binary cannot be found.
        GogCommandError: When ``gog`` exits with a non-zero return code.
        asyncio.TimeoutError: When the command exceeds ``timeout_seconds``.
    """
    gog_path = _resolve_gog_cli()
    if gog_path is None:
        raise GogNotInstalledError(
            "gog CLI not found. Install with: brew install steipete/tap/gogcli"
        )

    cmd: list[str] = [gog_path, *args, "--json", "--no-input"]
    logger.debug(f"gog: spawn {cmd!r}")

    stdin_pipe = asyncio.subprocess.PIPE if stdin_text is not None else asyncio.subprocess.DEVNULL
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=stdin_pipe,
    )

    stdin_bytes = stdin_text.encode() if stdin_text is not None else None
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=stdin_bytes),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise

    if proc.returncode != 0:
        err = stderr.decode().strip() or f"gog exited with code {proc.returncode}"
        raise GogCommandError(
            f"gog command failed ({proc.returncode}): {err}",
            spoken_message="Google-Dienst momentan nicht erreichbar.",
        )

    raw = stdout.decode().strip()
    if not raw:
        return {}
    return json.loads(raw)  # type: ignore[return-value]


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
                - session_id: Per-device session ID. If absent, derived as
                  ``jarvis-{device_slug}`` at startup with an INFO log
                  prompting the operator to pin it explicitly.
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

        # session_id has no hardcoded fallback.  If absent from config, derive
        # a slug-based default so single-machine installs work without config
        # changes, but prompt the operator to pin it for multi-device setups.
        _pinned_session = config.get("session_id")
        if _pinned_session:
            self._session_id: str = str(_pinned_session)
        else:
            _slug = resolve_device_slug()
            self._session_id = f"jarvis-{_slug}"
            logger.info(
                f"openclaw.session_id not set in config; defaulting to "
                f"'{self._session_id}'. Pin 'openclaw.session_id: {self._session_id}' "
                "in config/config.yaml for stable multi-device session isolation."
            )

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
        argv_base = _resolve_cli_argv()
        if argv_base is None:
            return False
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv_base,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_cli_subprocess_env(),
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
        logger.debug(
            f"query_agent raw: message_len={len(message)} message_preview={message[:60]!r} "
            f"thinking={think_level!r} session={session!r}"
        )

        # Use CLI for now; switch to REST when available. Flag name is
        # ``--session-id`` in the current OpenClaw CLI (>= 2026.4.x).
        argv_base = _resolve_cli_argv()
        if argv_base is None:
            raise OpenClawNotInstalledError(
                "OpenClaw CLI not found. Install with: npm install -g openclaw"
            )

        cmd = [
            *argv_base,
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
            sub_env = _cli_subprocess_env()
            logger.debug(
                f"CLI spawn: argv={cmd!r} parent_url={os.environ.get('OPENCLAW_GATEWAY_URL', '<unset>')!r} "
                f"sub_env_has_url={'OPENCLAW_GATEWAY_URL' in sub_env} sub_env_url={sub_env.get('OPENCLAW_GATEWAY_URL', '<stripped>')!r}"
            )
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=sub_env,
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

                if data is None:
                    logger.warning(
                        "OpenClaw CLI returned null — agent may have failed silently"
                    )
                    return AgentResponse(
                        text="",
                        session_id=session,
                        thinking_used=False,
                        tool_calls=[],
                        error="OpenClaw returned null response",
                    )

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
                if not text and isinstance(data, dict):
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

        argv_base = _resolve_cli_argv()
        if argv_base is None:
            raise OpenClawNotInstalledError(
                "OpenClaw CLI not found. Install with: npm install -g openclaw"
            )

        cmd = [
            *argv_base,
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
                env=_cli_subprocess_env(),
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

        argv_base = _resolve_cli_argv()
        if argv_base is None:
            return []

        cmd = [*argv_base, "sessions", "list", "--json"]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_cli_subprocess_env(),
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

        argv_base = _resolve_cli_argv()
        if argv_base is None:
            return []

        session = session_id or self._session_id
        cmd = [
            *argv_base,
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
                env=_cli_subprocess_env(),
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

        argv_base = _resolve_cli_argv()
        if argv_base is None:
            raise OpenClawNotInstalledError(
                "OpenClaw CLI not found. Install with: npm install -g openclaw"
            )

        session = session_id or self._session_id
        cmd = [*argv_base, "sessions", "reset", "--session", session]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_cli_subprocess_env(),
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

    async def register_mcp_server(
        self,
        url: str,
        name: str,
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Register a JARVIS MCP server definition with the OpenClaw CLI registry.

        Shells out to ``openclaw mcp set <name> '<json>'`` which saves the server
        definition into OpenClaw's config so the agent runtime can discover and
        invoke the tools.  Failure is non-fatal — JARVIS continues even when the
        CLI is absent or the gateway is offline.

        OpenClaw's acpx plugin (the Claude agent runtime) only accepts **stdio**-
        transport server entries (``command/args/env`` shape).  To satisfy that
        constraint without dropping the SSE server (which may have other consumers),
        we register a *stdio bridge* shim: acpx launches it as a subprocess and the
        bridge proxies JSON-RPC bidirectionally to JARVIS's SSE server.

        The bridge module lives at ``src/jarvis_mcp_bridge.py`` and is invoked as:

            ``<sys.executable> /abs/path/to/jarvis_mcp_bridge.py --url <sse_url> [--headers <json>]``

        The absolute path is used (rather than ``-m jarvis_mcp_bridge``) so the
        subprocess does not require ``PYTHONPATH=src`` — OpenClaw / acpx spawns
        the process in a clean environment that does not inherit JARVIS's sys.path.

        Args:
            url: Full SSE endpoint URL (e.g. ``http://127.0.0.1:8767/sse``).
            name: Server name as it will appear in ``openclaw mcp list``.
                  Must be explicit — no default (each device uses its own slug).
            headers: Optional HTTP headers forwarded to the SSE server by the bridge
                (e.g. ``{"Authorization": "Bearer token"}``).

        Returns:
            ``True`` if the command succeeded, ``False`` otherwise.
        """
        argv_base = _resolve_cli_argv()
        if argv_base is None:
            logger.warning(
                "register_mcp_server: OpenClaw CLI not found — MCP registration skipped"
            )
            return False

        # Build the bridge command.  sys.executable is the Python interpreter that
        # is currently running JARVIS — guaranteed to have the mcp SDK installed.
        # Use the absolute script path (_BRIDGE_PY) instead of -m jarvis_mcp_bridge
        # so the subprocess does not require PYTHONPATH=src to be set by the caller
        # (OpenClaw / acpx spawns the process without inheriting JARVIS's env).
        body: dict[str, Any] = {
            "command": sys.executable,
            "args": [_BRIDGE_PY, "--url", url],
        }
        if headers:
            body["args"].extend(["--headers", json.dumps(headers)])
        server_json = json.dumps(body)
        cmd = [*argv_base, "mcp", "set", name, server_json]
        logger.debug(f"register_mcp_server: spawn {cmd!r}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_cli_subprocess_env(),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=10.0,
            )
            if proc.returncode == 0:
                logger.info(
                    f"MCP server '{name}' registered with OpenClaw "
                    f"(stdio bridge → {url!r})"
                )
                return True
            err = stderr.decode().strip() or f"exit code {proc.returncode}"
            logger.warning(
                f"register_mcp_server: openclaw mcp set failed — {err}. "
                "JARVIS will continue without OpenClaw MCP registration."
            )
            return False
        except asyncio.TimeoutError:
            logger.warning(
                "register_mcp_server: CLI timed out — MCP registration skipped"
            )
            return False
        except FileNotFoundError:
            logger.warning(
                "register_mcp_server: OpenClaw CLI executable not found"
            )
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"register_mcp_server: unexpected error — {exc}. "
                "JARVIS will continue without OpenClaw MCP registration."
            )
            return False

    async def unregister_mcp_server(self, name: str) -> bool:
        """Remove the JARVIS MCP server definition from the OpenClaw CLI registry.

        Shells out to ``openclaw mcp unset <name>``.  Failure is non-fatal —
        a missing entry is not an error during shutdown.

        Args:
            name: Server name to remove from ``openclaw mcp list``.
                  Must be explicit — no default (each device uses its own slug).

        Returns:
            ``True`` if the command succeeded, ``False`` otherwise.
        """
        argv_base = _resolve_cli_argv()
        if argv_base is None:
            logger.debug(
                "unregister_mcp_server: OpenClaw CLI not found — nothing to clean up"
            )
            return False

        cmd = [*argv_base, "mcp", "unset", name]
        logger.debug(f"unregister_mcp_server: spawn {cmd!r}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_cli_subprocess_env(),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=10.0,
            )
            if proc.returncode == 0:
                logger.info(f"MCP server '{name}' unregistered from OpenClaw")
                return True
            err = stderr.decode().strip() or f"exit code {proc.returncode}"
            logger.debug(
                f"unregister_mcp_server: openclaw mcp unset returned non-zero — {err}"
            )
            return False
        except asyncio.TimeoutError:
            logger.debug("unregister_mcp_server: CLI timed out")
            return False
        except FileNotFoundError:
            logger.debug("unregister_mcp_server: OpenClaw CLI not found")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"unregister_mcp_server: {exc}")
            return False
