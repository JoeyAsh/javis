"""Unit tests for OpenClawClient.register_mcp_server and unregister_mcp_server.

All subprocess calls are mocked — no real CLI is spawned.

Covers:
- register_mcp_server: correct stdio-bridge argv shape (command/args, NOT url/headers)
- register_mcp_server: bridge args contain sys.executable + -m jarvis_mcp_bridge --url
- register_mcp_server: headers are passed via --headers JSON arg to bridge
- register_mcp_server: returns True on returncode 0
- register_mcp_server: returns False on non-zero returncode (graceful)
- register_mcp_server: returns False when CLI not found (_resolve_cli_argv → None)
- register_mcp_server: tolerates FileNotFoundError from create_subprocess_exec
- register_mcp_server: tolerates asyncio.TimeoutError
- register_mcp_server: tolerates generic unexpected exceptions
- unregister_mcp_server: correct argv, returns True on returncode 0
- unregister_mcp_server: returns False on non-zero returncode (graceful)
- unregister_mcp_server: returns False when CLI not found
- unregister_mcp_server: tolerates FileNotFoundError
- unregister_mcp_server: tolerates asyncio.TimeoutError
- unregister_mcp_server: tolerates generic unexpected exceptions
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.openclaw.client import OpenClawClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> OpenClawClient:
    """Return an OpenClawClient with minimal config."""
    return OpenClawClient(
        {
            "enabled": True,
            "gateway_url": "http://127.0.0.1:18789",
            "session_id": "jarvis-test",
            "thinking_level": "medium",
            "timeout_seconds": 10,
            "streaming_enabled": False,
        }
    )


def _make_mock_proc(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> AsyncMock:
    """Build a mock asyncio.subprocess.Process."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


# ---------------------------------------------------------------------------
# register_mcp_server — stdio-bridge shape (core invariant for this fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_mcp_server_uses_stdio_shape(client: OpenClawClient) -> None:
    """register_mcp_server sends command/args shape, NOT url/headers.

    The OpenClaw acpx plugin only accepts stdio-transport servers.  The JSON
    payload written to ``openclaw mcp set`` must have ``command`` and ``args``
    keys, never ``url``.  This test is the regression guard for the acpx schema
    incompatibility fixed in branch fix/openclaw-mcp-schema-acpx.
    """
    mock_proc = _make_mock_proc(returncode=0)
    captured: list[Any] = []

    async def fake_exec(*args: Any, **kwargs: Any) -> Any:
        captured.extend(args)
        return mock_proc

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await client.register_mcp_server("http://127.0.0.1:8767/sse", "jarvis")

    # The last positional arg is the JSON payload passed to ``openclaw mcp set``.
    json_payload = captured[-1]
    parsed = json.loads(json_payload)

    # Must have command and args — the stdio shape that acpx accepts.
    assert "command" in parsed, "Payload must contain 'command' (stdio shape)"
    assert "args" in parsed, "Payload must contain 'args' (stdio shape)"

    # Must NOT contain url/headers at the top level — that is the rejected HTTP shape.
    assert "url" not in parsed, "Payload must NOT contain 'url' (acpx rejects HTTP shape)"
    assert "headers" not in parsed, (
        "Headers must be encoded inside bridge args, not at the payload top level"
    )


@pytest.mark.asyncio
async def test_register_mcp_server_bridge_uses_sys_executable(client: OpenClawClient) -> None:
    """register_mcp_server uses sys.executable as the bridge command."""
    mock_proc = _make_mock_proc(returncode=0)
    captured: list[Any] = []

    async def fake_exec(*args: Any, **kwargs: Any) -> Any:
        captured.extend(args)
        return mock_proc

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await client.register_mcp_server("http://127.0.0.1:8767/sse", "jarvis")

    json_payload = captured[-1]
    parsed = json.loads(json_payload)
    assert parsed["command"] == sys.executable


@pytest.mark.asyncio
async def test_register_mcp_server_bridge_args_include_module_and_url(
    client: OpenClawClient,
) -> None:
    """register_mcp_server bridge args include -m jarvis_mcp_bridge and the SSE URL."""
    sse_url = "http://127.0.0.1:8767/sse"
    mock_proc = _make_mock_proc(returncode=0)
    captured: list[Any] = []

    async def fake_exec(*args: Any, **kwargs: Any) -> Any:
        captured.extend(args)
        return mock_proc

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await client.register_mcp_server(sse_url, "jarvis")

    json_payload = captured[-1]
    parsed = json.loads(json_payload)
    args: list[str] = parsed["args"]

    assert "-m" in args, "Bridge args must contain -m flag"
    assert "jarvis_mcp_bridge" in args, "Bridge args must contain module name"
    assert "--url" in args, "Bridge args must contain --url flag"
    url_idx = args.index("--url")
    assert args[url_idx + 1] == sse_url, "Bridge args must pass the SSE URL after --url"


@pytest.mark.asyncio
async def test_register_mcp_server_headers_in_bridge_args(client: OpenClawClient) -> None:
    """register_mcp_server encodes headers as --headers JSON inside the bridge args."""
    sse_url = "http://127.0.0.1:8767/sse"
    hdrs = {"Authorization": "Bearer secret"}
    mock_proc = _make_mock_proc(returncode=0)
    captured: list[Any] = []

    async def fake_exec(*args: Any, **kwargs: Any) -> Any:
        captured.extend(args)
        return mock_proc

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await client.register_mcp_server(sse_url, "jarvis", headers=hdrs)

    json_payload = captured[-1]
    parsed = json.loads(json_payload)
    args: list[str] = parsed["args"]

    assert "--headers" in args, "Bridge args must contain --headers when headers are supplied"
    h_idx = args.index("--headers")
    decoded_headers = json.loads(args[h_idx + 1])
    assert decoded_headers == hdrs

    # Headers must NOT leak to the top-level payload key.
    assert "headers" not in parsed


@pytest.mark.asyncio
async def test_register_mcp_server_no_headers_arg_when_empty(client: OpenClawClient) -> None:
    """register_mcp_server omits --headers from bridge args when no headers are given."""
    mock_proc = _make_mock_proc(returncode=0)
    captured: list[Any] = []

    async def fake_exec(*args: Any, **kwargs: Any) -> Any:
        captured.extend(args)
        return mock_proc

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await client.register_mcp_server("http://127.0.0.1:8767/sse", "jarvis", headers=None)

    json_payload = captured[-1]
    parsed = json.loads(json_payload)
    assert "--headers" not in parsed["args"]


# ---------------------------------------------------------------------------
# register_mcp_server — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_mcp_server_returns_true_on_success(client: OpenClawClient) -> None:
    """register_mcp_server returns True when subprocess exits with returncode 0."""
    mock_proc = _make_mock_proc(returncode=0)

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.register_mcp_server("http://127.0.0.1:8767/sse", "jarvis")

    assert result is True


@pytest.mark.asyncio
async def test_register_mcp_server_custom_name_in_argv(client: OpenClawClient) -> None:
    """register_mcp_server uses the custom name argument in the command."""
    mock_proc = _make_mock_proc(returncode=0)
    captured: list[Any] = []

    async def fake_exec(*args: Any, **kwargs: Any) -> Any:
        captured.extend(args)
        return mock_proc

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await client.register_mcp_server("http://127.0.0.1:8767/sse", "custom-server")

    assert "custom-server" in captured


# ---------------------------------------------------------------------------
# register_mcp_server — failure paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_mcp_server_returns_false_on_nonzero_returncode(
    client: OpenClawClient,
) -> None:
    """register_mcp_server returns False when subprocess exits with nonzero code."""
    mock_proc = _make_mock_proc(returncode=1, stderr=b"command not found")

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.register_mcp_server("http://127.0.0.1:8767/sse", "jarvis")

    assert result is False


@pytest.mark.asyncio
async def test_register_mcp_server_returns_false_when_cli_not_found(
    client: OpenClawClient,
) -> None:
    """register_mcp_server returns False gracefully when CLI is not installed."""
    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=None):
        result = await client.register_mcp_server("http://127.0.0.1:8767/sse", "jarvis")

    assert result is False


@pytest.mark.asyncio
async def test_register_mcp_server_tolerates_file_not_found_error(
    client: OpenClawClient,
) -> None:
    """register_mcp_server returns False when exec raises FileNotFoundError."""
    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch(
            "asyncio.create_subprocess_exec", side_effect=FileNotFoundError("no such file")
        ):
            result = await client.register_mcp_server("http://127.0.0.1:8767/sse", "jarvis")

    assert result is False


@pytest.mark.asyncio
async def test_register_mcp_server_tolerates_timeout_error(
    client: OpenClawClient,
) -> None:
    """register_mcp_server returns False on asyncio.TimeoutError."""
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                result = await client.register_mcp_server("http://127.0.0.1:8767/sse", "jarvis")

    assert result is False


@pytest.mark.asyncio
async def test_register_mcp_server_tolerates_generic_exception(
    client: OpenClawClient,
) -> None:
    """register_mcp_server returns False on unexpected generic exceptions."""
    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch(
            "asyncio.create_subprocess_exec", side_effect=RuntimeError("unexpected crash")
        ):
            result = await client.register_mcp_server("http://127.0.0.1:8767/sse", "jarvis")

    assert result is False


# ---------------------------------------------------------------------------
# unregister_mcp_server — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unregister_mcp_server_returns_true_on_success(client: OpenClawClient) -> None:
    """unregister_mcp_server returns True when subprocess exits with returncode 0."""
    mock_proc = _make_mock_proc(returncode=0)

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.unregister_mcp_server("jarvis")

    assert result is True


@pytest.mark.asyncio
async def test_unregister_mcp_server_spawns_correct_argv(client: OpenClawClient) -> None:
    """unregister_mcp_server calls openclaw mcp unset <name>."""
    captured: list[Any] = []

    async def _communicate():
        return (b"", b"")

    # Use a plain MagicMock for the proc; assign the coroutine function directly
    # to avoid AsyncMock's internal GC warning on Python 3.13.
    proc = MagicMock()
    proc.returncode = 0
    proc.communicate = _communicate

    async def fake_exec(*args: Any, **kwargs: Any) -> Any:
        captured.extend(args)
        return proc

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await client.unregister_mcp_server("jarvis")

    assert captured[0] == "openclaw"
    assert "mcp" in captured
    assert "unset" in captured
    assert "jarvis" in captured


@pytest.mark.asyncio
async def test_unregister_mcp_server_explicit_name_appears_in_argv(
    client: OpenClawClient,
) -> None:
    """unregister_mcp_server forwards the supplied name into the openclaw mcp unset argv.

    Post-#88: each device registers as 'jarvis-<slug>' so the caller always passes
    an explicit name; there is no longer a bare 'jarvis' default.
    """
    captured: list[Any] = []

    async def _communicate():
        return (b"", b"")

    proc = MagicMock()
    proc.returncode = 0
    proc.communicate = _communicate

    async def fake_exec(*args: Any, **kwargs: Any) -> Any:
        captured.extend(args)
        return proc

    device_name = "jarvis-test-laptop"
    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await client.unregister_mcp_server(name=device_name)

    assert device_name in captured
    assert "unset" in captured


# ---------------------------------------------------------------------------
# unregister_mcp_server — failure paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unregister_mcp_server_returns_false_on_nonzero_returncode(
    client: OpenClawClient,
) -> None:
    """unregister_mcp_server returns False when subprocess exits with nonzero code."""
    mock_proc = _make_mock_proc(returncode=1, stderr=b"entry not found")

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.unregister_mcp_server("jarvis")

    assert result is False


@pytest.mark.asyncio
async def test_unregister_mcp_server_returns_false_when_cli_not_found(
    client: OpenClawClient,
) -> None:
    """unregister_mcp_server returns False gracefully when CLI is not installed."""
    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=None):
        result = await client.unregister_mcp_server("jarvis")

    assert result is False


@pytest.mark.asyncio
async def test_unregister_mcp_server_tolerates_file_not_found_error(
    client: OpenClawClient,
) -> None:
    """unregister_mcp_server returns False when exec raises FileNotFoundError."""
    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch(
            "asyncio.create_subprocess_exec", side_effect=FileNotFoundError("no such file")
        ):
            result = await client.unregister_mcp_server("jarvis")

    assert result is False


@pytest.mark.asyncio
async def test_unregister_mcp_server_tolerates_timeout_error(
    client: OpenClawClient,
) -> None:
    """unregister_mcp_server returns False on asyncio.TimeoutError."""
    # Use MagicMock proc (not AsyncMock) — wait_for is patched to raise before
    # communicate is ever called, so no coroutine is created.
    proc = MagicMock()
    proc.returncode = 0

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                result = await client.unregister_mcp_server("jarvis")

    assert result is False


@pytest.mark.asyncio
async def test_unregister_mcp_server_tolerates_generic_exception(
    client: OpenClawClient,
) -> None:
    """unregister_mcp_server returns False on unexpected generic exceptions."""
    # Use a plain Exception subclass (not AsyncMock) so no coroutine is created
    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch(
            "asyncio.create_subprocess_exec", side_effect=OSError("disk full")
        ):
            result = await client.unregister_mcp_server("jarvis")

    assert result is False
