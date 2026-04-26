"""Unit tests for the ``run_gog`` helper in integrations.openclaw.client.

All ``asyncio.create_subprocess_exec`` calls are mocked via
``unittest.mock.AsyncMock`` so no real ``gog`` subprocess is ever spawned.

Covers acceptance criterion #8:
- Happy path: argv shape includes ``--json --no-input``; JSON stdout is parsed
- Non-zero exit code → GogCommandError with a meaningful spoken_message
- gog binary not found → GogNotInstalledError
- Timeout → asyncio.TimeoutError is re-raised (after killing the process)
- stdin_text is encoded and piped correctly
- Empty stdout returns {}
- stdin_pipe is DEVNULL when stdin_text is None
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(
    returncode: int = 0,
    stdout: bytes = b'{"messages": []}',
    stderr: bytes = b"",
) -> MagicMock:
    """Build a minimal mock Process object."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    return proc


# ---------------------------------------------------------------------------
# AC 8 — happy path: argv shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_gog_appends_json_and_no_input_flags():
    """run_gog appends --json and --no-input to the spawned argv."""
    proc = _make_proc(stdout=b'{"result": "ok"}')

    captured_cmd: list[str] = []

    async def fake_exec(*cmd, **kwargs):
        captured_cmd.extend(cmd)
        return proc

    with (
        patch(
            "integrations.openclaw.client._resolve_gog_cli",
            return_value="/usr/local/bin/gog",
        ),
        patch("asyncio.create_subprocess_exec", side_effect=fake_exec),
        patch(
            "asyncio.wait_for",
            new=AsyncMock(return_value=(b'{"result": "ok"}', b"")),
        ),
    ):
        from integrations.openclaw.client import run_gog

        result = await run_gog("gmail", "messages", "search", "is:unread")

    assert "/usr/local/bin/gog" in captured_cmd
    assert "gmail" in captured_cmd
    assert "messages" in captured_cmd
    assert "search" in captured_cmd
    assert "is:unread" in captured_cmd
    assert "--json" in captured_cmd
    assert "--no-input" in captured_cmd


@pytest.mark.asyncio
async def test_run_gog_parses_json_output():
    """run_gog parses the JSON stdout and returns a Python dict."""
    payload = {"messages": [{"id": "m1"}, {"id": "m2"}]}
    proc = _make_proc(stdout=json.dumps(payload).encode())

    async def fake_wait_for(coro, timeout=None):
        return await coro

    with (
        patch(
            "integrations.openclaw.client._resolve_gog_cli",
            return_value="/usr/local/bin/gog",
        ),
        patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
        patch("asyncio.wait_for", side_effect=fake_wait_for),
    ):
        from integrations.openclaw.client import run_gog

        result = await run_gog("gmail", "messages", "search", "is:unread")

    assert result == payload


@pytest.mark.asyncio
async def test_run_gog_returns_empty_dict_on_empty_stdout():
    """run_gog returns {} when gog produces no output."""
    proc = _make_proc(stdout=b"")

    async def fake_wait_for(coro, timeout=None):
        return await coro

    with (
        patch(
            "integrations.openclaw.client._resolve_gog_cli",
            return_value="/usr/local/bin/gog",
        ),
        patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
        patch("asyncio.wait_for", side_effect=fake_wait_for),
    ):
        from integrations.openclaw.client import run_gog

        result = await run_gog("calendar", "events", "primary")

    assert result == {}


# ---------------------------------------------------------------------------
# AC 8 — non-zero exit code → GogCommandError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_gog_raises_gog_command_error_on_nonzero_exit():
    """run_gog raises GogCommandError when gog exits with a non-zero return code."""
    from integrations.openclaw.client import GogCommandError

    proc = _make_proc(returncode=1, stdout=b"", stderr=b"authentication required")

    async def fake_wait_for(coro, timeout=None):
        return await coro

    with (
        patch(
            "integrations.openclaw.client._resolve_gog_cli",
            return_value="/usr/local/bin/gog",
        ),
        patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
        patch("asyncio.wait_for", side_effect=fake_wait_for),
    ):
        from integrations.openclaw.client import run_gog

        with pytest.raises(GogCommandError) as exc_info:
            await run_gog("gmail", "list")

    assert "1" in str(exc_info.value) or "authentication required" in str(exc_info.value)
    assert exc_info.value.spoken_message


@pytest.mark.asyncio
async def test_run_gog_command_error_includes_stderr_in_message():
    """GogCommandError message includes stderr text when available."""
    from integrations.openclaw.client import GogCommandError

    proc = _make_proc(returncode=2, stdout=b"", stderr=b"quota exceeded")

    async def fake_wait_for(coro, timeout=None):
        return await coro

    with (
        patch(
            "integrations.openclaw.client._resolve_gog_cli",
            return_value="/usr/local/bin/gog",
        ),
        patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
        patch("asyncio.wait_for", side_effect=fake_wait_for),
    ):
        from integrations.openclaw.client import run_gog

        with pytest.raises(GogCommandError) as exc_info:
            await run_gog("drive", "search", "query")

    assert "quota exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_run_gog_command_error_fallback_message_when_no_stderr():
    """GogCommandError uses 'gog exited with code N' when stderr is empty."""
    from integrations.openclaw.client import GogCommandError

    proc = _make_proc(returncode=3, stdout=b"", stderr=b"")

    async def fake_wait_for(coro, timeout=None):
        return await coro

    with (
        patch(
            "integrations.openclaw.client._resolve_gog_cli",
            return_value="/usr/local/bin/gog",
        ),
        patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
        patch("asyncio.wait_for", side_effect=fake_wait_for),
    ):
        from integrations.openclaw.client import run_gog

        with pytest.raises(GogCommandError) as exc_info:
            await run_gog("docs", "cat", "file_id")

    assert "3" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC 8 — gog binary not found → GogNotInstalledError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_gog_raises_not_installed_when_binary_missing():
    """run_gog raises GogNotInstalledError when _resolve_gog_cli returns None."""
    from integrations.openclaw.client import GogNotInstalledError

    with patch(
        "integrations.openclaw.client._resolve_gog_cli",
        return_value=None,
    ):
        from integrations.openclaw.client import run_gog

        with pytest.raises(GogNotInstalledError) as exc_info:
            await run_gog("gmail", "list")

    assert "gog" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# AC 8 — timeout → asyncio.TimeoutError re-raised, process killed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_gog_kills_process_and_reraises_on_timeout():
    """run_gog kills the subprocess and re-raises asyncio.TimeoutError on timeout."""
    proc = MagicMock()
    proc.kill = MagicMock()

    async def fake_wait_for(coro, timeout=None):
        raise asyncio.TimeoutError

    with (
        patch(
            "integrations.openclaw.client._resolve_gog_cli",
            return_value="/usr/local/bin/gog",
        ),
        patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
        patch("asyncio.wait_for", side_effect=fake_wait_for),
    ):
        from integrations.openclaw.client import run_gog

        with pytest.raises(asyncio.TimeoutError):
            await run_gog("gmail", "list", timeout_seconds=0.001)

    proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# AC 8 — stdin_text piping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_gog_pipes_stdin_text_when_provided():
    """run_gog encodes stdin_text and passes it to communicate()."""
    payload = {"id": "draft_001"}
    proc = MagicMock()
    proc.returncode = 0
    received_stdin: list[bytes | None] = []

    async def fake_communicate(input: bytes | None = None):
        received_stdin.append(input)
        return (json.dumps(payload).encode(), b"")

    proc.communicate = fake_communicate

    async def fake_wait_for(coro, timeout=None):
        return await coro

    with (
        patch(
            "integrations.openclaw.client._resolve_gog_cli",
            return_value="/usr/local/bin/gog",
        ),
        patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)),
        patch("asyncio.wait_for", side_effect=fake_wait_for),
    ):
        from integrations.openclaw.client import run_gog

        result = await run_gog("gmail", "drafts", "create", stdin_text="Email body text")

    assert len(received_stdin) == 1
    assert received_stdin[0] == b"Email body text"
    assert result == payload


@pytest.mark.asyncio
async def test_run_gog_uses_devnull_when_stdin_text_is_none():
    """run_gog uses DEVNULL for stdin when stdin_text is None."""
    proc = _make_proc(stdout=b"{}")
    captured_kwargs: list[dict] = []

    async def fake_exec(*cmd, **kwargs):
        captured_kwargs.append(kwargs)
        return proc

    async def fake_wait_for(coro, timeout=None):
        return await coro

    with (
        patch(
            "integrations.openclaw.client._resolve_gog_cli",
            return_value="/usr/local/bin/gog",
        ),
        patch("asyncio.create_subprocess_exec", side_effect=fake_exec),
        patch("asyncio.wait_for", side_effect=fake_wait_for),
    ):
        from integrations.openclaw.client import run_gog

        await run_gog("calendar", "events", "primary")

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0]["stdin"] == asyncio.subprocess.DEVNULL


# ---------------------------------------------------------------------------
# _resolve_gog_cli caching
# ---------------------------------------------------------------------------


def test_resolve_gog_cli_uses_env_override():
    """_resolve_gog_cli uses GOG_CLI_PATH env var when set."""
    import integrations.openclaw.client as mod

    original_cache = mod._GOG_CLI_CACHE
    mod._GOG_CLI_CACHE = None  # reset cache

    try:
        with patch.dict("os.environ", {"GOG_CLI_PATH": "/custom/path/gog"}):
            path = mod._resolve_gog_cli()
        assert path == "/custom/path/gog"
    finally:
        mod._GOG_CLI_CACHE = original_cache


def test_resolve_gog_cli_returns_none_when_not_found():
    """_resolve_gog_cli returns None when gog is not on PATH and GOG_CLI_PATH unset."""
    import integrations.openclaw.client as mod

    original_cache = mod._GOG_CLI_CACHE
    mod._GOG_CLI_CACHE = None

    try:
        with (
            patch.dict("os.environ", {}, clear=False),
            patch("shutil.which", return_value=None),
            patch.dict("os.environ", {"GOG_CLI_PATH": ""}, clear=False),
        ):
            # Remove GOG_CLI_PATH from env
            import os

            env_backup = os.environ.pop("GOG_CLI_PATH", None)
            try:
                path = mod._resolve_gog_cli()
            finally:
                if env_backup is not None:
                    os.environ["GOG_CLI_PATH"] = env_backup
    finally:
        mod._GOG_CLI_CACHE = original_cache

    # When shutil.which returns None, path should be None
    assert path is None
