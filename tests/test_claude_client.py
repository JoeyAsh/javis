"""Tests for the Claude API client module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.brain.claude_client import (
    FALLBACK_RESPONSES,
    JARVIS_SYSTEM_PROMPT,
    ClaudeClient,
    create_claude_client,
)


@pytest.fixture
def mock_anthropic():
    """Mock the anthropic module."""
    with patch("anthropic.AsyncAnthropic") as mock_class:
        mock_client = AsyncMock()

        # Create mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello, sir. How may I assist you?")]

        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_class.return_value = mock_client

        yield mock_client


@pytest.fixture
def claude_client(mock_config):
    """Return a ClaudeClient instance for testing."""
    return ClaudeClient(
        api_key="test-api-key",
        model="claude-sonnet-4-6",
        max_tokens=300,
        temperature=0.7,
    )


class TestClaudeClient:
    """Tests for ClaudeClient class."""

    @pytest.mark.asyncio
    async def test_chat_includes_jarvis_system_prompt(
        self, claude_client, mock_anthropic
    ):
        """Test that chat() includes JARVIS system prompt in API call."""
        claude_client._client = mock_anthropic

        await claude_client.chat("Hello", language="en")

        # Verify the API was called
        mock_anthropic.messages.create.assert_called_once()

        # Get the call arguments
        call_kwargs = mock_anthropic.messages.create.call_args[1]

        # System prompt should contain JARVIS prompt
        assert JARVIS_SYSTEM_PROMPT in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_language_injected_into_system_prompt_english(
        self, claude_client, mock_anthropic
    ):
        """Test that English language instruction is injected."""
        claude_client._client = mock_anthropic

        await claude_client.chat("Hello", language="en")

        call_kwargs = mock_anthropic.messages.create.call_args[1]
        assert "Respond in English" in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_language_injected_into_system_prompt_german(
        self, claude_client, mock_anthropic
    ):
        """Test that German language instruction is injected."""
        claude_client._client = mock_anthropic

        await claude_client.chat("Hallo", language="de")

        call_kwargs = mock_anthropic.messages.create.call_args[1]
        assert "Respond in German" in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_api_error_returns_fallback_en(self, claude_client, mock_anthropic):
        """Test that APIError returns spoken fallback string in English."""
        claude_client._client = mock_anthropic
        mock_anthropic.messages.create.side_effect = Exception("API Error")

        result = await claude_client.chat("Hello", language="en")

        assert result == FALLBACK_RESPONSES["en"]
        assert "technical difficulties" in result

    @pytest.mark.asyncio
    async def test_api_error_returns_fallback_de(self, claude_client, mock_anthropic):
        """Test that APIError returns spoken fallback string in German."""
        claude_client._client = mock_anthropic
        mock_anthropic.messages.create.side_effect = Exception("API Error")

        result = await claude_client.chat("Hallo", language="de")

        assert result == FALLBACK_RESPONSES["de"]
        assert "technische Schwierigkeiten" in result

    @pytest.mark.asyncio
    async def test_rate_limit_error_returns_fallback(
        self, claude_client, mock_anthropic
    ):
        """Test that RateLimitError returns spoken fallback string."""
        claude_client._client = mock_anthropic

        # Simulate rate limit error
        mock_anthropic.messages.create.side_effect = Exception("Rate limit exceeded")

        result = await claude_client.chat("Hello", language="en")

        # Should return fallback, not raise
        assert result == FALLBACK_RESPONSES["en"]

    @pytest.mark.asyncio
    async def test_conversation_history_passed_correctly(
        self, claude_client, mock_anthropic
    ):
        """Test that conversation history is passed correctly to API."""
        claude_client._client = mock_anthropic

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hello, sir."},
        ]

        await claude_client.chat("How are you?", history=history)

        call_kwargs = mock_anthropic.messages.create.call_args[1]
        messages = call_kwargs["messages"]

        # History should be included plus new message
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hello, sir."
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == "How are you?"

    @pytest.mark.asyncio
    async def test_empty_response_returns_fallback(
        self, claude_client, mock_anthropic
    ):
        """Test that empty API response returns fallback."""
        claude_client._client = mock_anthropic

        mock_response = MagicMock()
        mock_response.content = []
        mock_anthropic.messages.create.return_value = mock_response

        result = await claude_client.chat("Hello", language="en")

        assert result == FALLBACK_RESPONSES["en"]

    @pytest.mark.asyncio
    async def test_custom_system_prompt(self, claude_client, mock_anthropic):
        """Test that custom system prompt overrides default."""
        claude_client._client = mock_anthropic

        custom_prompt = "You are a helpful assistant."

        await claude_client.chat(
            "Hello",
            language="en",
            system_prompt=custom_prompt,
        )

        call_kwargs = mock_anthropic.messages.create.call_args[1]

        # Should use custom prompt, not JARVIS prompt
        assert custom_prompt in call_kwargs["system"]


class TestChatWithJson:
    """Tests for chat_with_json method."""

    @pytest.mark.asyncio
    async def test_returns_parsed_json(self, claude_client, mock_anthropic):
        """Test that valid JSON response is parsed."""
        claude_client._client = mock_anthropic

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"key": "value"}')]
        mock_anthropic.messages.create.return_value = mock_response

        result = await claude_client.chat_with_json(
            "Return JSON",
            system_prompt="Return valid JSON",
        )

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_handles_json_in_code_block(self, claude_client, mock_anthropic):
        """Test that JSON wrapped in code block is parsed."""
        claude_client._client = mock_anthropic

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='```json\n{"key": "value"}\n```')]
        mock_anthropic.messages.create.return_value = mock_response

        result = await claude_client.chat_with_json(
            "Return JSON",
            system_prompt="Return valid JSON",
        )

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_on_error(self, claude_client, mock_anthropic):
        """Test that errors return empty dict."""
        claude_client._client = mock_anthropic
        mock_anthropic.messages.create.side_effect = Exception("Error")

        result = await claude_client.chat_with_json(
            "Return JSON",
            system_prompt="Return valid JSON",
        )

        assert result == {}


class TestComplete:
    """Tests for complete method."""

    @pytest.mark.asyncio
    async def test_uses_custom_model(self, claude_client, mock_anthropic):
        """Test that custom model is used when specified."""
        claude_client._client = mock_anthropic

        await claude_client.complete(
            prompt="Test",
            system_prompt="Test system",
            model="claude-opus-4-5",
        )

        call_kwargs = mock_anthropic.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-opus-4-5"

    @pytest.mark.asyncio
    async def test_uses_custom_max_tokens(self, claude_client, mock_anthropic):
        """Test that custom max_tokens is used."""
        claude_client._client = mock_anthropic

        await claude_client.complete(
            prompt="Test",
            system_prompt="Test system",
            max_tokens=150,
        )

        call_kwargs = mock_anthropic.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 150

    @pytest.mark.asyncio
    async def test_uses_custom_temperature(self, claude_client, mock_anthropic):
        """Test that custom temperature is used."""
        claude_client._client = mock_anthropic

        await claude_client.complete(
            prompt="Test",
            system_prompt="Test system",
            temperature=0.3,
        )

        call_kwargs = mock_anthropic.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 0.3


class TestCreateClaudeClient:
    """Tests for create_claude_client factory function."""

    @pytest.mark.asyncio
    async def test_creates_client_with_config(self, mock_config, mock_anthropic):
        """Test that factory creates client with correct config."""
        config = mock_config["claude"].copy()

        with patch("src.brain.claude_client.ClaudeClient.initialize", new_callable=AsyncMock):
            client = await create_claude_client(config)

            assert isinstance(client, ClaudeClient)
            assert client.model == "claude-sonnet-4-6"
            assert client.max_tokens == 300
            assert client.temperature == 0.7
