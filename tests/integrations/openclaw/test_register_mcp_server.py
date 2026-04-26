"""Unit tests for OpenClawClient.register_mcp_server and unregister_mcp_server.

All subprocess calls are mocked — no real CLI is spawned.

Covers:
- register_mcp_server: correct argv, returns True on returncode 0
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
# register_mcp_server — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_mcp_server_returns_true_on_success(client: OpenClawClient) -> None:
    """register_mcp_server returns True when subprocess exits with returncode 0."""
    mock_proc = _make_mock_proc(returncode=0)

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            result = await client.register_mcp_server("http://127.0.0.1:8767/sse", "jarvis")

    assert result is True


@pytest.mark.asyncio
async def test_register_mcp_server_spawns_correct_argv(client: OpenClawClient) -> None:
    """register_mcp_server calls openclaw mcp set <name> <json>."""
    mock_proc = _make_mock_proc(returncode=0)
    captured: list[Any] = []

    async def fake_exec(*args: Any, **kwargs: Any) -> Any:
        captured.extend(args)
        return mock_proc

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await client.register_mcp_server("http://127.0.0.1:8767/sse", "jarvis")

    assert captured[0] == "openclaw"
    assert "mcp" in captured
    assert "set" in captured
    assert "jarvis" in captured
    # The JSON payload must include the url key
    json_payload = captured[-1]
    parsed = json.loads(json_payload)
    assert parsed == {"url": "http://127.0.0.1:8767/sse"}


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
async def test_unregister_mcp_server_default_name_is_jarvis(client: OpenClawClient) -> None:
    """unregister_mcp_server defaults to name='jarvis' when not specified."""
    captured: list[Any] = []

    async def _communicate():
        return (b"", b"")

    proc = MagicMock()
    proc.returncode = 0
    proc.communicate = _communicate

    async def fake_exec(*args: Any, **kwargs: Any) -> Any:
        captured.extend(args)
        return proc

    with patch("integrations.openclaw.client._resolve_cli_argv", return_value=["openclaw"]):
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await client.unregister_mcp_server()  # no name arg

    assert "jarvis" in captured


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
