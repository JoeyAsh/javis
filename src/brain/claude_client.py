"""Claude API client for JARVIS.

Wraps the Anthropic Python SDK with JARVIS personality and error handling.
"""

import asyncio
from typing import Any

from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("claude_client")

# JARVIS personality system prompt
JARVIS_SYSTEM_PROMPT = """You are JARVIS (Just A Rather Very Intelligent System).
Calm, precise, slightly formal, dry wit. Address user as "sir" or "ma'am".
Respond in 1-3 sentences unless asked for detail.
Always respond in the same language the user spoke. Briefly confirm actions."""

# Fallback responses for error cases
FALLBACK_RESPONSES = {
    "en": "I apologize, sir, but I'm experiencing technical difficulties. Please try again in a moment.",
    "de": "Ich bitte um Entschuldigung, aber ich habe momentan technische Schwierigkeiten. Bitte versuchen Sie es in einem Moment erneut.",
}


class ClaudeClient:
    """Client for Claude API with JARVIS personality."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 300,
        temperature: float = 0.7,
    ) -> None:
        """Initialize the Claude client.

        Args:
            api_key: Anthropic API key. If None, loads from config.
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Response temperature (0-1)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client: Any = None

        # Load API key
        if api_key:
            self._api_key = api_key
        else:
            cfg = get_config()
            self._api_key = cfg.get("anthropic_api_key", "")

    async def initialize(self) -> None:
        """Initialize the Anthropic client."""
        try:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
            logger.info(f"Claude client initialized with model: {self.model}")

        except ImportError:
            logger.error("anthropic package not installed. Run: pip install anthropic")
            raise

    async def chat(
        self,
        message: str,
        language: str = "en",
        history: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Send a message to Claude and get a response.

        Args:
            message: User message
            language: Response language (en, de)
            history: Optional conversation history
            system_prompt: Optional custom system prompt

        Returns:
            Claude's response text
        """
        if self._client is None:
            await self.initialize()

        # Build system prompt with language instruction
        if system_prompt:
            full_system = system_prompt
        else:
            full_system = JARVIS_SYSTEM_PROMPT

        if language == "de":
            full_system += "\n\nRespond in German (Deutsch)."
        else:
            full_system += "\n\nRespond in English."

        # Build messages array
        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=full_system,
                messages=messages,
            )

            # Extract text from response
            if response.content and len(response.content) > 0:
                text = response.content[0].text
                logger.debug(f"Claude response: {text[:100]}...")
                return text
            else:
                logger.warning("Empty response from Claude")
                return FALLBACK_RESPONSES.get(language, FALLBACK_RESPONSES["en"])

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return FALLBACK_RESPONSES.get(language, FALLBACK_RESPONSES["en"])

    async def chat_with_json(
        self,
        message: str,
        system_prompt: str,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Send a message expecting JSON response.

        Args:
            message: User message
            system_prompt: System prompt (should instruct JSON output)
            max_tokens: Override max tokens

        Returns:
            Parsed JSON response or empty dict on error
        """
        if self._client is None:
            await self.initialize()

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                temperature=0.3,  # Lower temperature for structured output
                system=system_prompt,
                messages=[{"role": "user", "content": message}],
            )

            if response.content and len(response.content) > 0:
                text = response.content[0].text

                # Parse JSON from response
                import json

                # Try to find JSON in the response
                text = text.strip()
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

                return json.loads(text)
            else:
                return {}

        except Exception as e:
            logger.error(f"Claude API error (JSON mode): {e}")
            return {}

    async def complete(
        self,
        prompt: str,
        system_prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Low-level completion with custom parameters.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            model: Override model
            max_tokens: Override max tokens
            temperature: Override temperature

        Returns:
            Response text
        """
        if self._client is None:
            await self.initialize()

        try:
            response = await self._client.messages.create(
                model=model or self.model,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )

            if response.content and len(response.content) > 0:
                return response.content[0].text
            return ""

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return ""


async def create_claude_client(config: dict[str, Any] | None = None) -> ClaudeClient:
    """Factory function to create Claude client.

    Args:
        config: Optional Claude configuration. If None, loads from global config.

    Returns:
        Configured ClaudeClient instance
    """
    if config is None:
        cfg = get_config()
        config = cfg.get_section("claude")

    client = ClaudeClient(
        model=config.get("model", "claude-sonnet-4-6"),
        max_tokens=config.get("max_tokens", 300),
        temperature=config.get("temperature", 0.7),
    )

    await client.initialize()
    return client
