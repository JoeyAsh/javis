"""Unit tests for OpenClawClient.

Tests cover:
- Client initialization and configuration
- Health checks with mocked subprocess
- Agent queries with mocked responses
- Session management
- Error handling and graceful degradation

All subprocess calls are mocked to avoid external dependencies.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from integrations.openclaw import (
    AgentResponse,
    OpenClawClient,
    OpenClawConnectionError,
    OpenClawNotInstalledError,
    SessionInfo,
)


@pytest.fixture
def openclaw_config():
    """Provide default OpenClaw configuration."""
    return {
        "enabled": True,
        "gateway_url": "http://127.0.0.1:18789",
        "session_id": "jarvis-test",
        "thinking_level": "normal",
        "timeout_seconds": 10,
    }


@pytest.fixture
def disabled_config():
    """Provide disabled OpenClaw configuration."""
    return {
        "enabled": False,
        "gateway_url": "http://127.0.0.1:18789",
        "session_id": "jarvis-test",
    }


class TestOpenClawClientInitialization:
    """Tests for client initialization."""

    def test_init_sets_config(self, openclaw_config):
        """Test that init sets configuration values."""
        client = OpenClawClient(openclaw_config)

        assert client.gateway_url == "http://127.0.0.1:18789"
        assert client.session_id == "jarvis-test"
        assert client.is_enabled is True

    def test_init_with_defaults(self):
        """Test that init uses defaults for missing config."""
        with patch(
            "integrations.openclaw.client.resolve_device_slug", return_value="test-host"
        ):
            client = OpenClawClient({})

        assert client.gateway_url == "http://127.0.0.1:18789"
        assert client.session_id == "jarvis-test-host"
        # Default thinking level maps to a valid OpenClaw CLI value.
        assert client._thinking == "medium"
        assert client._timeout == 30

    def test_init_disabled(self, disabled_config):
        """Test that disabled config is respected."""
        client = OpenClawClient(disabled_config)

        assert client.is_enabled is False


class TestHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_is_healthy_returns_true_on_200(self, openclaw_config):
        """Health check returns True when gateway HTTP endpoint returns 200."""
        client = OpenClawClient(openclaw_config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_http = AsyncMock()
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False
        mock_http.get = AsyncMock(return_value=mock_response)

        with patch(
            "integrations.openclaw.client.httpx.AsyncClient", return_value=mock_http
        ):
            result = await client.is_healthy()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_healthy_returns_false_on_non_200(self, openclaw_config):
        """Health check returns False when gateway returns non-200."""
        client = OpenClawClient(openclaw_config)

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_http = AsyncMock()
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False
        mock_http.get = AsyncMock(return_value=mock_response)

        with patch(
            "integrations.openclaw.client.httpx.AsyncClient", return_value=mock_http
        ):
            result = await client.is_healthy()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_healthy_returns_false_on_connection_error(self, openclaw_config):
        """Health check returns False when gateway is unreachable."""
        import httpx

        client = OpenClawClient(openclaw_config)

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False
        mock_http.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch(
            "integrations.openclaw.client.httpx.AsyncClient", return_value=mock_http
        ):
            result = await client.is_healthy()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_healthy_returns_false_when_disabled(self, disabled_config):
        """Health check returns False when disabled (short-circuits)."""
        client = OpenClawClient(disabled_config)

        result = await client.is_healthy()

        assert result is False


class TestAgentQuery:
    """Tests for agent query functionality."""

    @pytest.mark.asyncio
    async def test_query_agent_returns_response(self, openclaw_config):
        """Test successful agent query."""
        client = OpenClawClient(openclaw_config)

        mock_response = {
            "response": "Hello, Sir. How may I assist?",
            "thinking_used": False,
            "tool_calls": [],
        }

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(
                return_value=(json.dumps(mock_response).encode(), b"")
            )
            mock_exec.return_value = mock_proc

            result = await client.query_agent("Hello")

            assert isinstance(result, AgentResponse)
            assert result.text == "Hello, Sir. How may I assist?"
            assert result.session_id == "jarvis-test"
            assert result.error is None

    @pytest.mark.asyncio
    async def test_query_agent_handles_error(self, openclaw_config):
        """Test agent query error handling."""
        client = OpenClawClient(openclaw_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 1
            mock_proc.communicate = AsyncMock(return_value=(b"", b"Connection failed"))
            mock_exec.return_value = mock_proc

            result = await client.query_agent("Hello")

            assert result.text == ""
            assert result.error == "Connection failed"

    @pytest.mark.asyncio
    async def test_query_agent_handles_timeout(self, openclaw_config):
        """Test agent query timeout handling."""
        client = OpenClawClient(openclaw_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_exec.return_value = mock_proc

            result = await client.query_agent("Hello")

            assert result.text == ""
            assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_query_agent_with_plain_text_response(self, openclaw_config):
        """Test agent query with non-JSON response."""
        client = OpenClawClient(openclaw_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(
                return_value=(b"Plain text response", b"")
            )
            mock_exec.return_value = mock_proc

            result = await client.query_agent("Hello")

            assert result.text == "Plain text response"
            assert result.error is None

    @pytest.mark.asyncio
    async def test_query_agent_respects_session_override(self, openclaw_config):
        """Test that session ID override is passed correctly."""
        client = OpenClawClient(openclaw_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(
                return_value=(json.dumps({"response": "OK"}).encode(), b"")
            )
            mock_exec.return_value = mock_proc

            result = await client.query_agent("Hello", session_id="custom-session")

            assert result.session_id == "custom-session"
            # Verify command included custom session (OpenClaw CLI flag is
            # ``--session-id``).
            call_args = mock_exec.call_args[0]
            assert "--session-id" in call_args
            session_idx = call_args.index("--session-id")
            assert call_args[session_idx + 1] == "custom-session"

    @pytest.mark.asyncio
    async def test_query_agent_when_disabled(self, disabled_config):
        """Test query returns error when disabled."""
        client = OpenClawClient(disabled_config)

        result = await client.query_agent("Hello")

        assert "disabled" in result.error.lower()
        assert "disabled" in result.text.lower()


class TestSessionManagement:
    """Tests for session management functionality."""

    @pytest.mark.asyncio
    async def test_list_sessions_returns_sessions(self, openclaw_config):
        """Test listing sessions."""
        client = OpenClawClient(openclaw_config)

        mock_response = {
            "sessions": [
                {
                    "id": "session-1",
                    "created_at": "2024-01-15T10:00:00Z",
                    "message_count": 5,
                    "model": "claude-sonnet",
                },
                {
                    "id": "session-2",
                    "created_at": "2024-01-14T10:00:00Z",
                    "message_count": 10,
                    "model": "claude-opus",
                },
            ]
        }

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(
                return_value=(json.dumps(mock_response).encode(), b"")
            )
            mock_exec.return_value = mock_proc

            sessions = await client.list_sessions()

            assert len(sessions) == 2
            assert isinstance(sessions[0], SessionInfo)
            assert sessions[0].session_id == "session-1"
            assert sessions[0].message_count == 5

    @pytest.mark.asyncio
    async def test_list_sessions_returns_empty_on_error(self, openclaw_config):
        """Test list sessions returns empty list on error."""
        client = OpenClawClient(openclaw_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = FileNotFoundError()

            sessions = await client.list_sessions()

            assert sessions == []

    @pytest.mark.asyncio
    async def test_get_session_history(self, openclaw_config):
        """Test getting session history."""
        client = OpenClawClient(openclaw_config)

        mock_response = {
            "messages": [
                {"role": "user", "text": "Hello"},
                {"role": "assistant", "text": "Hello, Sir"},
            ]
        }

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(
                return_value=(json.dumps(mock_response).encode(), b"")
            )
            mock_exec.return_value = mock_proc

            history = await client.get_session_history()

            assert len(history) == 2
            assert history[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_reset_session_returns_true_on_success(self, openclaw_config):
        """Test session reset returns True on success."""
        client = OpenClawClient(openclaw_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            result = await client.reset_session()

            assert result is True

    @pytest.mark.asyncio
    async def test_reset_session_returns_false_on_failure(self, openclaw_config):
        """Test session reset returns False on failure."""
        client = OpenClawClient(openclaw_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 1
            mock_proc.wait = AsyncMock(return_value=1)
            mock_exec.return_value = mock_proc

            result = await client.reset_session()

            assert result is False


class TestMessageSending:
    """Tests for message sending functionality."""

    @pytest.mark.asyncio
    async def test_send_message_returns_true_on_success(self, openclaw_config):
        """Test send message returns True on success."""
        client = OpenClawClient(openclaw_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            result = await client.send_message("whatsapp", "+1234567890", "Hello")

            assert result is True

    @pytest.mark.asyncio
    async def test_send_message_returns_false_on_failure(self, openclaw_config):
        """Test send message returns False on failure."""
        client = OpenClawClient(openclaw_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 1
            mock_proc.wait = AsyncMock(return_value=1)
            mock_exec.return_value = mock_proc

            result = await client.send_message("whatsapp", "+1234567890", "Hello")

            assert result is False


class TestFallbackMessages:
    """Tests for offline fallback messages."""

    def test_get_offline_fallback_message_english(self, openclaw_config):
        """Test English fallback message."""
        client = OpenClawClient(openclaw_config)

        message = client.get_offline_fallback_message("en")

        assert "OpenClaw gateway" in message
        assert "openclaw doctor" in message

    def test_get_offline_fallback_message_german(self, openclaw_config):
        """Test German fallback message."""
        client = OpenClawClient(openclaw_config)

        message = client.get_offline_fallback_message("de")

        assert "OpenClaw-Gateway" in message
        assert "openclaw doctor" in message

    def test_get_offline_fallback_message_defaults_to_english(self, openclaw_config):
        """Test fallback to English for unknown language."""
        client = OpenClawClient(openclaw_config)

        message = client.get_offline_fallback_message("unknown")

        assert "OpenClaw gateway" in message


class TestClientLifecycle:
    """Tests for client lifecycle management."""

    @pytest.mark.asyncio
    async def test_close_cleans_up_http_client(self, openclaw_config):
        """Test that close properly cleans up HTTP client."""
        client = OpenClawClient(openclaw_config)

        # Mock successful CLI check and health
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            await client.initialize()

        assert client._http is not None

        await client.close()

        assert client._http is None

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self, openclaw_config):
        """Test that close can be called multiple times."""
        client = OpenClawClient(openclaw_config)

        await client.close()
        await client.close()  # Should not raise
