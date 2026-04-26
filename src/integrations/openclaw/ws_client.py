"""Persistent WebSocket client for the OpenClaw gateway.

Wraps the gateway's Ed25519-authenticated WS protocol into an async
streaming interface.  A single persistent connection is maintained and
auto-reconnected on drop; concurrent agent turns are multiplexed over
that single connection via per-run asyncio queues.

Usage::

    client = OpenClawWSClient(
        gateway_url="ws://127.0.0.1:18789",
        agent_id="main",
    )
    await client.connect()

    async for chunk in client.query_agent_stream("Hello", session_id="jarvis-main"):
        print(chunk.new_text, end="", flush=True)

    await client.close()
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from utils.logger import get_logger

logger = get_logger("openclaw_ws_client")

# ── Constants ──────────────────────────────────────────────────────────────────

_OPENCLAW_STATE_DIR = Path.home() / ".openclaw"
_DEVICE_FILE = _OPENCLAW_STATE_DIR / "identity" / "device.json"
_CONFIG_FILE = _OPENCLAW_STATE_DIR / "openclaw.json"

_PROTOCOL_VERSION = 3
_CLIENT_ID = "gateway-client"
_CLIENT_MODE = "backend"
_CLIENT_VERSION = "jarvis/1.0"

# Scopes must be in this exact order (matches CLI_DEFAULT_OPERATOR_SCOPES in TS source).
_OPERATOR_SCOPES = [
    "operator.admin",
    "operator.read",
    "operator.write",
    "operator.approvals",
    "operator.pairing",
    "operator.talk.secrets",
]

# The 12-byte SPKI prefix wrapping an Ed25519 raw public key in DER SPKI format.
_ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")

# Default patience before the first delta arrives (covers thinking + tool-calls).
_TIME_TO_FIRST_TOKEN_S = 60.0
# Default patience between deltas after streaming has begun.
_INTER_DELTA_TIMEOUT_S = 20.0

# Reconnect backoff parameters.
_RECONNECT_INITIAL_S = 1.0
_RECONNECT_MAX_S = 30.0


# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass
class StreamChunk:
    """Single streaming chunk yielded by :meth:`OpenClawWSClient.query_agent_stream`.

    Attributes:
        type: ``"delta"`` for incremental text, ``"final"`` for the complete
            response, ``"error"`` when something went wrong,
            ``"tool_started"`` when a tool call begins (synthetic),
            ``"tool_finished"`` when a tool call ends (synthetic).
        run_id: Identifies the turn this chunk belongs to.
        new_text: *Incremental* text added since the previous chunk.
        full_text: Cumulative text received so far (all deltas combined).
        error: Error message when ``type == "error"``; ``None`` otherwise.
        tool_name: Tool name for ``tool_started`` / ``tool_finished`` chunks.
            ``None`` for all other chunk types.
        tool_summary: Short human-readable label for the tool call.
            ``None`` for all other chunk types.

    Note on tool events:
        The OpenClaw gateway does NOT expose real-time tool-call events to
        operator WS connections — tool events (`stream="tool"`) are only
        delivered to the embedded control UI.  ``tool_started`` /
        ``tool_finished`` chunks are therefore **synthetic**: emitted by
        the consumer pipeline when the TTFT delay exceeds a threshold
        (typically 2 s), which reliably correlates with tool use.
    """

    type: str  # "delta" | "final" | "error" | "tool_started" | "tool_finished"
    run_id: str
    new_text: str
    full_text: str
    error: str | None = None
    tool_name: str | None = None
    tool_summary: str | None = None


# ── Crypto helpers ─────────────────────────────────────────────────────────────


def _b64url_encode(data: bytes) -> str:
    """Base64url-encode bytes without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _public_key_raw_b64url(public_key_pem: str) -> str:
    """Extract the 32-byte raw Ed25519 public key from PEM and return as base64url."""
    key: Ed25519PublicKey = serialization.load_pem_public_key(public_key_pem.encode())  # type: ignore[assignment]
    spki = key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    raw = (
        spki[len(_ED25519_SPKI_PREFIX) :]
        if spki[: len(_ED25519_SPKI_PREFIX)] == _ED25519_SPKI_PREFIX
        else spki
    )
    return _b64url_encode(raw)


def _sign_device_payload(private_key_pem: str, payload: str) -> str:
    """Sign a UTF-8 payload with an Ed25519 private key and return base64url signature."""
    key: Ed25519PrivateKey = serialization.load_pem_private_key(  # type: ignore[assignment]
        private_key_pem.encode(), password=None
    )
    return _b64url_encode(key.sign(payload.encode()))


def _build_device_auth_payload_v3(
    *,
    device_id: str,
    client_id: str,
    client_mode: str,
    role: str,
    scopes: list[str],
    signed_at_ms: int,
    token: str,
    nonce: str,
    platform: str,
    device_family: str = "",
) -> str:
    """Build the v3 device signature payload string.

    Matches the TS ``buildDeviceAuthPayloadV3`` exactly.  Scopes must be in
    the same order as the ``scopes`` array sent in the connect frame — the
    server re-builds the payload from the frame and verifies.
    """
    return "|".join(
        [
            "v3",
            device_id,
            client_id,
            client_mode,
            role,
            ",".join(scopes),
            str(signed_at_ms),
            token,
            nonce,
            platform,
            device_family,
        ]
    )


# ── Config loaders ─────────────────────────────────────────────────────────────


def _load_device_identity() -> dict[str, Any]:
    """Load device identity from ~/.openclaw/identity/device.json.

    Delegates to :func:`utils.device.load_device_identity` which provides
    error handling; kept here as a private alias for backwards compat with
    call sites inside this module.
    """
    from utils.device import load_device_identity  # noqa: PLC0415

    return load_device_identity()


def _load_gateway_token() -> str:
    """Load the shared gateway auth token from ~/.openclaw/openclaw.json."""
    try:
        cfg = json.loads(_CONFIG_FILE.read_text())
        token: str | None = cfg.get("gateway", {}).get("auth", {}).get("token")
        return token if token else ""
    except Exception as exc:
        logger.warning(f"Failed to load gateway token from {_CONFIG_FILE}: {exc}")
        return ""


# ── Protocol helpers ───────────────────────────────────────────────────────────


def _make_request(method: str, params: dict[str, Any]) -> tuple[str, str]:
    """Build a gateway request frame; return (frame_json, request_id)."""
    req_id = str(uuid.uuid4())
    frame = {"type": "req", "id": req_id, "method": method, "params": params}
    return json.dumps(frame), req_id


def _extract_text(payload: dict[str, Any]) -> str:
    """Extract assistant text from a chat event payload."""
    message_obj = payload.get("message") or {}
    content = message_obj.get("content") or []
    return "".join(blk.get("text", "") for blk in content if blk.get("type") == "text")


# ── TokenSource protocol ───────────────────────────────────────────────────────


class TokenSource:
    """Abstract source for gateway auth tokens (for injection in tests)."""

    def get_token(self) -> str:
        """Return the current bearer token."""
        raise NotImplementedError


# ── Main client ────────────────────────────────────────────────────────────────


class OpenClawWSClient:
    """Persistent async WebSocket client for the OpenClaw gateway.

    Maintains one long-lived connection, auto-reconnects on drop, and
    multiplexes concurrent agent turns via per-run queues.

    Attributes:
        gateway_url: WS URL of the gateway (e.g. ``ws://127.0.0.1:18789``).
        agent_id: Agent to target for ``agent`` RPC calls.
    """

    def __init__(
        self,
        gateway_url: str,
        agent_id: str = "main",
        token_source: TokenSource | None = None,
        session_key_prefix: str = "agent:main:explicit:",
        time_to_first_token_s: float = _TIME_TO_FIRST_TOKEN_S,
        inter_delta_timeout_s: float = _INTER_DELTA_TIMEOUT_S,
    ) -> None:
        """Initialise the WS client (does NOT connect yet — call :meth:`connect`).

        Args:
            gateway_url: WS URL of the OpenClaw gateway.
            agent_id: Agent ID used in ``agent`` RPC params.
            token_source: Optional injectable token source (used in tests).
            session_key_prefix: Canonical session key prefix used for subscribing.
            time_to_first_token_s: Seconds to wait for the first delta before
                emitting a stall error (covers thinking + tool-calls).
            inter_delta_timeout_s: Seconds to wait between deltas once streaming
                has begun before emitting a stall error.
        """
        self._gateway_url = gateway_url
        self._agent_id = agent_id
        self._token_source = token_source
        self._session_key_prefix = session_key_prefix
        self._time_to_first_token_s = time_to_first_token_s
        self._inter_delta_timeout_s = inter_delta_timeout_s

        self._ws: Any = None  # websockets connection object
        self._reader_task: asyncio.Task[None] | None = None
        self._connected = False
        self._closing = False

        # run_id → queue of StreamChunk — fans out from single reader task.
        self._pending_runs: dict[str, asyncio.Queue[StreamChunk]] = {}

        # run_id → cumulative full_text seen so far (used to compute new_text).
        self._prev_texts: dict[str, str] = {}

        # Session IDs we are currently subscribed to (resubscribe on reconnect).
        self._subscribed_sessions: set[str] = set()

        # Lock to serialise connect/reconnect so concurrent callers don't
        # race to open two WS connections.
        self._connect_lock: asyncio.Lock = asyncio.Lock()

    # ── Properties ─────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        """Return True if the WS connection is currently open."""
        return self._connected

    # ── Public API ──────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open a connection to the gateway and complete the handshake.

        Starts the background reader task.  Idempotent — if already
        connected, returns immediately.

        Raises:
            Exception: If the connection or handshake fails on the first attempt.
        """
        async with self._connect_lock:
            if self._connected:
                return
            await self._do_connect()

    async def close(self) -> None:
        """Close the WS connection and stop the reader task gracefully."""
        self._closing = True
        self._connected = False

        if self._reader_task is not None and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reader_task = None

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        # Drain all pending queues with an error so waiting consumers exit.
        for run_id, q in list(self._pending_runs.items()):
            await q.put(
                StreamChunk(
                    type="error",
                    run_id=run_id,
                    new_text="",
                    full_text="",
                    error="connection_closed",
                )
            )
        self._pending_runs.clear()
        self._prev_texts.clear()
        logger.info("OpenClaw WS client closed")

    async def query_agent_stream(
        self,
        message: str,
        session_id: str,
        thinking: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Send a message to the agent and stream response chunks.

        The gateway emits cumulative text; this method converts it to
        incremental ``new_text`` so callers only see the freshly added tokens.

        Args:
            message: User message text.
            session_id: Human-readable session label (e.g. ``"jarvis-main"``).
            thinking: Thinking level override (``"off"|"low"|"medium"|...``).

        Yields:
            :class:`StreamChunk` objects until the stream is complete or
            an error/abort occurs.

        Raises:
            RuntimeError: If not connected and reconnect fails.
        """
        if not self._connected:
            await self.connect()

        # Ensure we are subscribed to this session.
        await self._ensure_subscribed(session_id)

        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        self._pending_runs[run_id] = queue

        params: dict[str, Any] = {
            "message": message,
            "sessionId": session_id,
            "idempotencyKey": run_id,
        }
        if thinking:
            params["thinking"] = thinking

        frame, req_id = _make_request("agent", params)

        try:
            await self._send(frame)
            logger.debug(f"Agent turn sent run_id={run_id} session={session_id}")

            prev_full_text = ""
            got_first_delta: bool = False

            while True:
                timeout = (
                    self._inter_delta_timeout_s
                    if got_first_delta
                    else self._time_to_first_token_s
                )
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    phase = "mid_stream" if got_first_delta else "before_first_token"
                    logger.warning(
                        f"Stream stalled run_id={run_id} "
                        f"phase={phase} after {timeout}s"
                    )
                    err = StreamChunk(
                        type="error",
                        run_id=run_id,
                        new_text="",
                        full_text=prev_full_text,
                        error="stream_stalled",
                    )
                    yield err
                    break

                yield chunk

                if chunk.type in ("final", "error"):
                    break

                if not got_first_delta and chunk.type == "delta":
                    got_first_delta = True

                prev_full_text = chunk.full_text

        finally:
            self._pending_runs.pop(run_id, None)
            self._prev_texts.pop(run_id, None)

    async def abort(self, session_id: str, run_id: str) -> None:
        """Send a ``chat.abort`` RPC to cancel a running turn.

        Also injects a synthetic error chunk into the pending queue so the
        streaming consumer exits cleanly without waiting for the stall timeout.

        Args:
            session_id: Session the run belongs to.
            run_id: The run ID returned by :meth:`query_agent_stream`.
        """
        session_key = f"{self._session_key_prefix}{session_id}"
        frame, _ = _make_request(
            "chat.abort", {"sessionKey": session_key, "runId": run_id}
        )
        if self._connected:
            try:
                await self._send(frame)
                logger.info(f"Sent chat.abort for run_id={run_id}")
            except Exception as exc:
                logger.warning(f"chat.abort send failed: {exc}")

        # Inject synthetic error so the consumer loop exits.
        queue = self._pending_runs.get(run_id)
        if queue is not None:
            await queue.put(
                StreamChunk(
                    type="error",
                    run_id=run_id,
                    new_text="",
                    full_text="",
                    error="aborted",
                )
            )

    # ── Internal connection management ──────────────────────────────────────────

    async def _do_connect(self) -> None:
        """Open the WS, complete the handshake, and subscribe to all sessions.

        Starts the background reader task.
        """
        from websockets.asyncio.client import connect as ws_connect

        identity = _load_device_identity()
        device_id: str = identity["deviceId"]
        private_key_pem: str = identity["privateKeyPem"]
        public_key_pem: str = identity["publicKeyPem"]
        public_key_raw = _public_key_raw_b64url(public_key_pem)

        gateway_token = (
            self._token_source.get_token()
            if self._token_source
            else _load_gateway_token()
        )

        logger.info(f"Connecting to OpenClaw gateway at {self._gateway_url} …")
        ws = await ws_connect(self._gateway_url)

        # Step 1: receive connect.challenge
        raw = await ws.recv()
        challenge = json.loads(raw)
        if challenge.get("event") != "connect.challenge":
            await ws.close()
            raise RuntimeError(f"Expected connect.challenge, got: {challenge}")
        nonce: str = challenge["payload"]["nonce"]

        # Step 2: build signature and send connect
        role = "operator"
        signed_at_ms = int(time.time() * 1000)
        if sys.platform == "win32":
            platform = "win32"
        elif sys.platform == "darwin":
            platform = "darwin"
        else:
            platform = "linux"
        payload_str = _build_device_auth_payload_v3(
            device_id=device_id,
            client_id=_CLIENT_ID,
            client_mode=_CLIENT_MODE,
            role=role,
            scopes=_OPERATOR_SCOPES,
            signed_at_ms=signed_at_ms,
            token=gateway_token,
            nonce=nonce,
            platform=platform,
        )
        signature = _sign_device_payload(private_key_pem, payload_str)

        connect_params: dict[str, Any] = {
            "minProtocol": _PROTOCOL_VERSION,
            "maxProtocol": _PROTOCOL_VERSION,
            "client": {
                "id": _CLIENT_ID,
                "version": _CLIENT_VERSION,
                "mode": _CLIENT_MODE,
                "platform": platform,
            },
            "caps": [],
            "role": role,
            "scopes": _OPERATOR_SCOPES,
            "device": {
                "id": device_id,
                "publicKey": public_key_raw,
                "signature": signature,
                "signedAt": signed_at_ms,
                "nonce": nonce,
            },
        }
        if gateway_token:
            connect_params["auth"] = {"token": gateway_token}

        frame, connect_req_id = _make_request("connect", connect_params)
        await ws.send(frame)

        # Step 3: await connect response (may interleave tick/other events)
        resp = await self._recv_until(ws, connect_req_id, "connect")
        if not resp.get("ok"):
            await ws.close()
            raise RuntimeError(f"Gateway rejected connect: {resp}")

        protocol = resp.get("payload", {}).get("protocol", "?")
        logger.info(
            f"OpenClaw WS client connected to {self._gateway_url} "
            f"(protocol={protocol})"
        )

        self._ws = ws
        self._connected = True

        # Resubscribe to all tracked sessions (handles reconnect case).
        for session_id in list(self._subscribed_sessions):
            await self._subscribe_session(session_id)

        # Start background reader.
        self._reader_task = asyncio.create_task(
            self._reader_loop(), name="openclaw-ws-reader"
        )

    async def _reconnect_loop(self) -> None:
        """Attempt to reconnect with exponential backoff until success or close."""
        delay = _RECONNECT_INITIAL_S
        attempt = 0
        while not self._closing:
            attempt += 1
            logger.info(f"OpenClaw WS reconnect attempt #{attempt} in {delay:.1f}s …")
            await asyncio.sleep(delay)
            if self._closing:
                return
            try:
                async with self._connect_lock:
                    if not self._connected:
                        await self._do_connect()
                logger.info("OpenClaw WS reconnected successfully")
                return
            except Exception as exc:
                logger.warning(f"Reconnect attempt #{attempt} failed: {exc}")
                delay = min(delay * 2, _RECONNECT_MAX_S)

    # ── Background reader ───────────────────────────────────────────────────────

    async def _reader_loop(self) -> None:
        """Read WS frames in a loop and fan-out chat events to pending queues.

        On connection drop, clears state and schedules a reconnect unless
        the client is being closed intentionally.
        """
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                await self._dispatch(msg)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            if not self._closing:
                logger.warning(f"OpenClaw WS reader error: {exc}")

        if not self._closing:
            logger.info("OpenClaw WS connection lost — scheduling reconnect")
            self._connected = False
            self._ws = None
            # Drain pending with error so consumers don't hang.
            for run_id, q in list(self._pending_runs.items()):
                await q.put(
                    StreamChunk(
                        type="error",
                        run_id=run_id,
                        new_text="",
                        full_text="",
                        error="connection_lost",
                    )
                )
            self._pending_runs.clear()
            self._prev_texts.clear()
            asyncio.create_task(self._reconnect_loop(), name="openclaw-ws-reconnect")

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        """Route a single inbound WS frame to the appropriate handler."""
        event = msg.get("event")

        # Heartbeat — ignore.
        if event == "tick":
            return

        if event != "chat":
            return

        payload: dict[str, Any] = msg.get("payload", {})
        run_id: str | None = payload.get("runId")
        state: str = payload.get("state", "")

        if run_id is None:
            return

        queue = self._pending_runs.get(run_id)
        if queue is None:
            # Not our turn (could be a concurrent session from another client).
            return

        if state == "delta":
            full_text = _extract_text(payload)
            prev_text = self._prev_texts.get(run_id, "")
            new_text = full_text[len(prev_text) :]
            self._prev_texts[run_id] = full_text
            chunk = StreamChunk(
                type="delta",
                run_id=run_id,
                new_text=new_text,
                full_text=full_text,
            )
            await queue.put(chunk)

        elif state == "final":
            full_text = _extract_text(payload)
            prev_text = self._prev_texts.get(run_id, "")
            new_text = full_text[len(prev_text) :]
            self._prev_texts.pop(run_id, None)
            chunk = StreamChunk(
                type="final",
                run_id=run_id,
                new_text=new_text,
                full_text=full_text,
            )
            await queue.put(chunk)

        elif state == "error":
            self._prev_texts.pop(run_id, None)
            error_msg = (
                payload.get("errorMessage") or payload.get("errorKind") or "unknown"
            )
            chunk = StreamChunk(
                type="error",
                run_id=run_id,
                new_text="",
                full_text="",
                error=error_msg,
            )
            await queue.put(chunk)

    # ── Session subscription helpers ────────────────────────────────────────────

    async def _ensure_subscribed(self, session_id: str) -> None:
        """Subscribe to a session's chat events if not already subscribed."""
        if session_id in self._subscribed_sessions:
            return
        await self._subscribe_session(session_id)

    async def _subscribe_session(self, session_id: str) -> None:
        """Send a ``sessions.messages.subscribe`` RPC for ``session_id``."""
        session_key = f"{self._session_key_prefix}{session_id}"
        frame, req_id = _make_request(
            "sessions.messages.subscribe", {"key": session_key}
        )
        try:
            await self._send(frame)
            self._subscribed_sessions.add(session_id)
            logger.debug(f"Subscribed to session events: {session_key}")
        except Exception as exc:
            logger.warning(f"Failed to subscribe to {session_key}: {exc}")

    # ── Low-level send/recv ─────────────────────────────────────────────────────

    async def _send(self, frame: str) -> None:
        """Send a raw JSON frame over the WS connection."""
        if self._ws is None:
            raise RuntimeError("Not connected")
        await self._ws.send(frame)

    @staticmethod
    async def _recv_until(ws: Any, target_id: str, label: str = "?") -> dict[str, Any]:
        """Drain frames until the response for ``target_id`` arrives."""
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("id") == target_id:
                return msg
            event = msg.get("event", "")
            if event not in ("tick",):
                logger.debug(f"pre-{label} event: {event}")
        raise RuntimeError(f"WS closed before {label} response")
