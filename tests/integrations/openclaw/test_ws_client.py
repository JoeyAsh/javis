"""Unit tests for OpenClawWSClient.

Tests cover:
- Handshake + connection (mocked WS server)
- Session subscription
- query_agent_stream yields delta then final chunks
- Cumulative → incremental text conversion
- abort sends chat.abort and terminates stream
- Reconnect on connection drop
- Subprocess fallback when WS unavailable (via OpenClawClient.query_agent_stream)
- StreamChunk tool fields (tool_name, tool_summary) default to None
- StreamChunk tool_started / tool_finished constructors
- Gateway does NOT emit real-time tool events to operator WS connections
  (verified via live probe: tool events are only sent to control-UI sessions;
   synthetic tool hints are emitted by the pipeline layer based on TTFT timing)

All WS interactions are mocked — no live gateway is required.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.openclaw.ws_client import (
    OpenClawWSClient,
    StreamChunk,
    _b64url_encode,
    _build_device_auth_payload_v3,
    _extract_text,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_event(event: str, payload: dict[str, Any]) -> str:
    """Serialise a gateway event frame."""
    return json.dumps({"event": event, "seq": 1, "payload": payload})


def _make_res(req_id: str, ok: bool, payload: dict[str, Any]) -> str:
    """Serialise a gateway response frame."""
    return json.dumps({"type": "res", "id": req_id, "ok": ok, "payload": payload})


def _chat_delta(run_id: str, text: str) -> str:
    """Serialise a chat delta event."""
    return _make_event(
        "chat",
        {
            "runId": run_id,
            "sessionKey": "agent:main:explicit:test",
            "seq": 1,
            "state": "delta",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            },
        },
    )


def _chat_final(run_id: str, text: str) -> str:
    """Serialise a chat final event."""
    return _make_event(
        "chat",
        {
            "runId": run_id,
            "sessionKey": "agent:main:explicit:test",
            "seq": 9,
            "state": "final",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            },
        },
    )


def _chat_error(run_id: str, msg: str) -> str:
    """Serialise a chat error event."""
    return _make_event(
        "chat",
        {
            "runId": run_id,
            "sessionKey": "agent:main:explicit:test",
            "seq": 2,
            "state": "error",
            "errorMessage": msg,
        },
    )


# ── Unit tests for pure helpers ────────────────────────────────────────────────


class TestCryptoHelpers:
    """Tests for crypto / encoding helpers."""

    def test_b64url_encode_no_padding(self) -> None:
        """b64url_encode never emits '=' padding characters."""
        result = _b64url_encode(b"\xff" * 32)
        assert "=" not in result

    def test_build_device_auth_payload_v3_format(self) -> None:
        """Payload string has the correct pipe-delimited v3 format."""
        payload = _build_device_auth_payload_v3(
            device_id="dev123",
            client_id="gateway-client",
            client_mode="backend",
            role="operator",
            scopes=["operator.admin", "operator.read"],
            signed_at_ms=1000,
            token="tok",
            nonce="nonce1",
            platform="linux",
        )
        parts = payload.split("|")
        assert parts[0] == "v3"
        assert parts[1] == "dev123"
        assert parts[4] == "operator"
        assert parts[5] == "operator.admin,operator.read"
        assert parts[7] == "tok"
        assert parts[8] == "nonce1"

    def test_extract_text_from_payload(self) -> None:
        """_extract_text pulls text from the content block correctly."""
        payload = {
            "message": {
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "thinking", "text": "ignored"},
                ]
            }
        }
        assert _extract_text(payload) == "Hello"

    def test_extract_text_returns_empty_on_missing(self) -> None:
        """_extract_text returns empty string when message/content is absent."""
        assert _extract_text({}) == ""


# ── Tests using mocked WS ──────────────────────────────────────────────────────


class MockWS:
    """Minimal mock for a websockets connection object."""

    def __init__(self, frames: list[str]) -> None:
        self._frames = list(frames)
        self._sent: list[str] = []
        self.closed = False

    async def recv(self) -> str:
        if self._frames:
            return self._frames.pop(0)
        raise EOFError("No more frames")

    async def send(self, data: str) -> None:
        self._sent.append(data)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        if not self._frames:
            raise StopAsyncIteration
        return self._frames.pop(0)


def _make_connect_mock_ws(run_id: str, full_texts: list[str]) -> MockWS:
    """Build a MockWS pre-loaded with a full handshake + stream flow."""
    challenge = json.dumps(
        {"event": "connect.challenge", "payload": {"nonce": "nonce-abc"}}
    )
    # connect response — id will be whatever the client generates; we match by injecting
    # a placeholder that the test accepts.
    connect_res_placeholder = "__CONNECT_RES__"

    delta_frames = [_chat_delta(run_id, t) for t in full_texts[:-1]]
    final_frame = _chat_final(run_id, full_texts[-1])
    subscribe_res = json.dumps(
        {
            "type": "res",
            "id": "__SUB_ID__",
            "ok": True,
            "payload": {"subscribed": True},
        }
    )
    agent_res = json.dumps(
        {
            "type": "res",
            "id": "__AGENT_ID__",
            "ok": True,
            "payload": {"status": "accepted", "runId": run_id},
        }
    )
    return MockWS(
        [challenge, connect_res_placeholder, subscribe_res, agent_res]
        + delta_frames
        + [final_frame]
    )


@pytest.fixture
def fake_identity(tmp_path):
    """Create a fake device identity and config; patch the loader functions."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    private_key = Ed25519PrivateKey.generate()
    pub = private_key.public_key()
    priv_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub_pem = pub.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    return {
        "deviceId": "test-device-id",
        "privateKeyPem": priv_pem,
        "publicKeyPem": pub_pem,
    }


class TestOpenClawWSClientUnit:
    """Unit tests for OpenClawWSClient using patched WS and identity loaders."""

    @pytest.mark.asyncio
    async def test_dispatch_delta_computes_new_text(self, fake_identity) -> None:
        """Dispatch correctly computes incremental new_text from cumulative text."""
        client = OpenClawWSClient("ws://127.0.0.1:18789")
        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        client._pending_runs[run_id] = queue

        # First delta: full_text = "Hello "
        payload1 = {
            "runId": run_id,
            "sessionKey": "agent:main:explicit:test",
            "state": "delta",
            "message": {"content": [{"type": "text", "text": "Hello "}]},
        }
        await client._dispatch({"event": "chat", "payload": payload1})
        chunk1 = await queue.get()
        assert chunk1.type == "delta"
        assert chunk1.full_text == "Hello "
        assert chunk1.new_text == "Hello "

        # Second delta: full_text = "Hello World"
        payload2 = {
            "runId": run_id,
            "sessionKey": "agent:main:explicit:test",
            "state": "delta",
            "message": {"content": [{"type": "text", "text": "Hello World"}]},
        }
        await client._dispatch({"event": "chat", "payload": payload2})
        chunk2 = await queue.get()
        assert chunk2.type == "delta"
        assert chunk2.full_text == "Hello World"
        assert chunk2.new_text == "World"  # only the incremental part

    @pytest.mark.asyncio
    async def test_dispatch_final_emits_final_chunk(self, fake_identity) -> None:
        """Dispatch emits a final chunk when state == 'final'."""
        client = OpenClawWSClient("ws://127.0.0.1:18789")
        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        client._pending_runs[run_id] = queue

        payload = {
            "runId": run_id,
            "sessionKey": "agent:main:explicit:test",
            "state": "final",
            "message": {"content": [{"type": "text", "text": "Complete answer."}]},
        }
        await client._dispatch({"event": "chat", "payload": payload})
        chunk = await queue.get()
        assert chunk.type == "final"
        assert chunk.full_text == "Complete answer."

    @pytest.mark.asyncio
    async def test_dispatch_error_emits_error_chunk(self, fake_identity) -> None:
        """Dispatch emits error chunk when state == 'error'."""
        client = OpenClawWSClient("ws://127.0.0.1:18789")
        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        client._pending_runs[run_id] = queue

        payload = {
            "runId": run_id,
            "sessionKey": "agent:main:explicit:test",
            "state": "error",
            "errorMessage": "Something went wrong",
        }
        await client._dispatch({"event": "chat", "payload": payload})
        chunk = await queue.get()
        assert chunk.type == "error"
        assert chunk.error == "Something went wrong"

    @pytest.mark.asyncio
    async def test_dispatch_tick_is_ignored(self) -> None:
        """Tick events are silently discarded."""
        client = OpenClawWSClient("ws://127.0.0.1:18789")
        # No queues registered; dispatch should return without error.
        await client._dispatch({"event": "tick"})

    @pytest.mark.asyncio
    async def test_dispatch_unknown_run_id_is_ignored(self) -> None:
        """Events for unknown run IDs are silently dropped."""
        client = OpenClawWSClient("ws://127.0.0.1:18789")
        payload = {
            "runId": "unknown-run",
            "sessionKey": "agent:main:explicit:test",
            "state": "delta",
            "message": {"content": [{"type": "text", "text": "X"}]},
        }
        # Should not raise even without a matching queue.
        await client._dispatch({"event": "chat", "payload": payload})

    @pytest.mark.asyncio
    async def test_cumulative_incremental_sum(self, fake_identity) -> None:
        """Sum of all new_text lengths equals length of the final full_text."""
        client = OpenClawWSClient("ws://127.0.0.1:18789")
        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        client._pending_runs[run_id] = queue

        words = ["Hello", "Hello World", "Hello World foo", "Hello World foo bar"]
        for i, text in enumerate(words):
            state = "final" if i == len(words) - 1 else "delta"
            payload = {
                "runId": run_id,
                "sessionKey": "agent:main:explicit:test",
                "state": state,
                "message": {"content": [{"type": "text", "text": text}]},
            }
            await client._dispatch({"event": "chat", "payload": payload})

        chunks: list[StreamChunk] = []
        while not queue.empty():
            chunks.append(await queue.get())

        total_new = sum(len(c.new_text) for c in chunks)
        assert total_new == len(words[-1])

    @pytest.mark.asyncio
    async def test_abort_injects_error_chunk(self) -> None:
        """abort() puts a synthetic error chunk into the pending queue."""
        client = OpenClawWSClient("ws://127.0.0.1:18789")
        client._connected = True
        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        client._pending_runs[run_id] = queue

        # Mock _send to avoid actual WS calls.
        client._send = AsyncMock()

        await client.abort("test-session", run_id)

        chunk = await queue.get()
        assert chunk.type == "error"
        assert chunk.error == "aborted"

        # Verify chat.abort was sent.
        client._send.assert_awaited_once()
        sent_frame = json.loads(client._send.call_args[0][0])
        assert sent_frame["method"] == "chat.abort"
        assert sent_frame["params"]["runId"] == run_id

    @pytest.mark.asyncio
    async def test_close_drains_pending_queues(self) -> None:
        """close() injects connection_closed errors into all pending queues."""
        client = OpenClawWSClient("ws://127.0.0.1:18789")
        client._connected = True

        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        client._pending_runs[run_id] = queue

        mock_ws = MagicMock()
        mock_ws.close = AsyncMock()
        client._ws = mock_ws

        await client.close()

        chunk = await queue.get()
        assert chunk.type == "error"
        assert chunk.error == "connection_closed"

    @pytest.mark.asyncio
    async def test_close_drains_pending_queues_with_prev_texts(self) -> None:
        """close() does not raise AttributeError when _prev_texts has an entry mid-stream."""
        client = OpenClawWSClient("ws://127.0.0.1:18789")
        client._connected = True

        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        client._pending_runs[run_id] = queue
        # Simulate mid-stream state: a delta was already dispatched.
        client._prev_texts[run_id] = "Hello "

        mock_ws = MagicMock()
        mock_ws.close = AsyncMock()
        client._ws = mock_ws

        # Must not raise AttributeError.
        await client.close()

        # Consumer receives the connection_closed sentinel, not an exception.
        chunk = await queue.get()
        assert chunk.type == "error"
        assert chunk.error == "connection_closed"

        # Both dicts must be cleared.
        assert run_id not in client._pending_runs
        assert run_id not in client._prev_texts


class TestOpenClawWSClientFallback:
    """Tests for OpenClawClient.query_agent_stream fallback behaviour."""

    @pytest.mark.asyncio
    async def test_fallback_emits_single_final_chunk(self) -> None:
        """When WS is unavailable, query_agent_stream emits one final chunk."""
        from integrations.openclaw.client import OpenClawClient

        config = {
            "enabled": True,
            "gateway_url": "http://127.0.0.1:18789",
            "session_id": "jarvis-test",
            "thinking_level": "off",
            "timeout_seconds": 5,
            "streaming_enabled": False,  # disable WS
        }
        client = OpenClawClient(config)
        # ws_client is None since streaming_enabled=False
        assert client.ws_client is None

        mock_response_data = {
            "response": "Sir, I am operational.",
            "thinking_used": False,
            "tool_calls": [],
        }
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            import json as _json

            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(
                return_value=(_json.dumps(mock_response_data).encode(), b"")
            )
            mock_exec.return_value = mock_proc

            chunks: list[StreamChunk] = []
            async for chunk in client.query_agent_stream("hello"):
                chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].type == "final"
        assert "operational" in chunks[0].full_text

    @pytest.mark.asyncio
    async def test_fallback_error_emits_error_chunk(self) -> None:
        """When subprocess fails, query_agent_stream emits an error chunk."""
        from integrations.openclaw.client import OpenClawClient

        config = {
            "enabled": True,
            "gateway_url": "http://127.0.0.1:18789",
            "session_id": "jarvis-test",
            "thinking_level": "off",
            "timeout_seconds": 5,
            "streaming_enabled": False,
        }
        client = OpenClawClient(config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 1
            mock_proc.communicate = AsyncMock(return_value=(b"", b"CLI broken"))
            mock_exec.return_value = mock_proc

            chunks = []
            async for chunk in client.query_agent_stream("hello"):
                chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].type == "error"

    @pytest.mark.asyncio
    async def test_abort_current_run_no_op_when_ws_unavailable(self) -> None:
        """abort_current_run is a no-op when ws_client is None."""
        from integrations.openclaw.client import OpenClawClient

        config = {"enabled": True, "streaming_enabled": False}
        client = OpenClawClient(config)
        # Should not raise.
        await client.abort_current_run("jarvis-test", "some-run-id")


# ---------------------------------------------------------------------------
# New tests: differentiated stall timeouts
# ---------------------------------------------------------------------------


class TestStallTimeouts:
    """Verify before-first-token vs mid-stream timeout phases."""

    @pytest.mark.asyncio
    async def test_time_to_first_token_uses_long_timeout(self) -> None:
        """No stall fires at 25 s before first delta; stall fires after 65 s."""
        client = OpenClawWSClient(
            "ws://127.0.0.1:18789",
            time_to_first_token_s=60.0,
            inter_delta_timeout_s=20.0,
        )
        client._connected = True
        client._send = AsyncMock()

        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        client._pending_runs[run_id] = queue
        client._subscribed_sessions.add("test-session")

        # Simulate 25 s without any delta — should time out only at 60 s.
        # We replace asyncio.wait_for with a version that raises TimeoutError
        # only when the given timeout >= 60 (i.e. the first-token gate).
        timeout_seen: list[float] = []

        async def _fake_wait_for(coro, timeout):  # type: ignore[no-untyped-def]
            timeout_seen.append(timeout)
            # Always raise on first call to simulate stall.
            raise asyncio.TimeoutError()

        with patch("integrations.openclaw.ws_client.asyncio.wait_for", _fake_wait_for):
            # Also patch _ensure_subscribed and _send to avoid real IO.
            client._ensure_subscribed = AsyncMock()  # type: ignore[method-assign]
            chunks: list[StreamChunk] = []
            async for chunk in client.query_agent_stream("hello", "test-session"):
                chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].type == "error"
        assert chunks[0].error == "stream_stalled"
        # The timeout used must be the long one (60 s), not 20 s.
        assert timeout_seen[0] == 60.0

    @pytest.mark.asyncio
    async def test_inter_delta_uses_short_timeout(self) -> None:
        """After one delta arrives, stall fires with the short inter-delta timeout."""
        client = OpenClawWSClient(
            "ws://127.0.0.1:18789",
            time_to_first_token_s=60.0,
            inter_delta_timeout_s=20.0,
        )
        client._connected = True
        client._send = AsyncMock()

        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        client._pending_runs[run_id] = queue
        client._subscribed_sessions.add("test-session")

        # Pre-load one real delta so got_first_delta flips to True.
        await queue.put(
            StreamChunk(type="delta", run_id=run_id, new_text="hello", full_text="hello")
        )

        call_count = 0

        async def _fake_wait_for(coro, timeout):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: return the pre-loaded delta from the real queue.
                return await queue.get()
            # Second call: simulate inter-delta stall.
            raise asyncio.TimeoutError()

        timeout_on_second_call: list[float] = []
        _original_wait_for = asyncio.wait_for

        async def _instrumented_wait_for(coro, timeout):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return await queue.get()
            timeout_on_second_call.append(timeout)
            raise asyncio.TimeoutError()

        with patch(
            "integrations.openclaw.ws_client.asyncio.wait_for",
            _instrumented_wait_for,
        ):
            client._ensure_subscribed = AsyncMock()  # type: ignore[method-assign]
            chunks: list[StreamChunk] = []
            async for chunk in client.query_agent_stream("hello", "test-session"):
                chunks.append(chunk)

        # Should have the delta chunk + the stall error chunk.
        assert len(chunks) == 2
        assert chunks[0].type == "delta"
        assert chunks[1].type == "error"
        assert chunks[1].error == "stream_stalled"
        # Timeout on second call must be the short inter-delta value.
        assert timeout_on_second_call[0] == 20.0


# ---------------------------------------------------------------------------
# Tests for StreamChunk tool fields (Step 2 of tool-event spec)
# ---------------------------------------------------------------------------


class TestStreamChunkToolFields:
    """Tests for the new tool_name / tool_summary fields on StreamChunk.

    Background: The OpenClaw gateway does NOT expose real-time tool events to
    operator WS connections.  ``tool_started`` / ``tool_finished`` StreamChunk
    variants are synthetic — emitted by the ws_server pipeline when TTFT exceeds
    a threshold.  These tests verify the dataclass contract.
    """

    def test_default_tool_fields_are_none(self) -> None:
        """Regular delta chunks have None for tool_name and tool_summary."""
        chunk = StreamChunk(
            type="delta",
            run_id="run-abc",
            new_text="Hello",
            full_text="Hello",
        )
        assert chunk.tool_name is None
        assert chunk.tool_summary is None
        assert chunk.error is None

    def test_tool_started_chunk_fields(self) -> None:
        """tool_started chunk carries tool_name and tool_summary."""
        chunk = StreamChunk(
            type="tool_started",
            run_id="run-t",
            new_text="",
            full_text="",
            tool_name="Read",
            tool_summary="Lese config.yaml",
        )
        assert chunk.type == "tool_started"
        assert chunk.tool_name == "Read"
        assert chunk.tool_summary == "Lese config.yaml"
        assert chunk.error is None

    def test_tool_finished_chunk_fields(self) -> None:
        """tool_finished chunk carries tool_name and empty summary."""
        chunk = StreamChunk(
            type="tool_finished",
            run_id="run-t",
            new_text="",
            full_text="",
            tool_name="Bash",
            tool_summary="",
        )
        assert chunk.type == "tool_finished"
        assert chunk.tool_name == "Bash"
        assert chunk.tool_summary == ""

    def test_error_chunk_tool_fields_default_none(self) -> None:
        """Error chunks have None tool fields (no tool context on errors)."""
        chunk = StreamChunk(
            type="error",
            run_id="run-e",
            new_text="",
            full_text="",
            error="connection_lost",
        )
        assert chunk.tool_name is None
        assert chunk.tool_summary is None

    @pytest.mark.asyncio
    async def test_dispatch_ignores_non_chat_non_tick_events(self) -> None:
        """_dispatch silently ignores events with event != 'chat' (e.g. 'agent').

        The gateway emits 'agent' events with stream='tool' only to connections
        in toolEventRecipients (control-UI).  Our operator connection never
        receives these, and _dispatch should not raise when they arrive.
        """
        client = OpenClawWSClient("ws://127.0.0.1:18789")
        # session.tool event — not a chat event
        session_tool_msg = {
            "event": "session.tool",
            "seq": 5,
            "payload": {
                "runId": "some-run",
                "stream": "tool",
                "data": {"phase": "start", "name": "bash"},
            },
        }
        # Should not raise, should not enqueue anything.
        await client._dispatch(session_tool_msg)
        assert len(client._pending_runs) == 0

    @pytest.mark.asyncio
    async def test_dispatch_agent_stream_tool_is_ignored(self) -> None:
        """_dispatch ignores 'agent' events (stream='tool'); no queue entry added."""
        client = OpenClawWSClient("ws://127.0.0.1:18789")
        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[StreamChunk] = asyncio.Queue()
        client._pending_runs[run_id] = queue

        agent_tool_msg = {
            "event": "agent",
            "seq": 3,
            "payload": {
                "runId": run_id,
                "stream": "tool",
                "data": {"phase": "start", "name": "bash", "title": "Running bash"},
            },
        }
        await client._dispatch(agent_tool_msg)

        # Queue must remain empty — tool events are not dispatched.
        assert queue.empty()
