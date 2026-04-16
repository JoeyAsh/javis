"""Fish Audio cloud TTS integration for JARVIS.

Sends text to Fish Audio API and returns MP3 audio bytes.
"""

import os
import re
from typing import Any

import httpx

from utils.logger import get_logger

logger = get_logger("fish_tts")

FISH_API_URL = "https://api.fish.audio/v1/tts"

# Filler phrases that JARVIS should never say
_BANNED_PHRASES = re.compile(
    r"\b(absolutely|great question|i'?d be happy to|of course|how can i help|"
    r"is there anything else|i apologize|as an ai|certainly|sure thing)\b",
    re.IGNORECASE,
)


def strip_markdown_for_tts(text: str) -> str:
    """Remove markdown formatting and filler phrases from text before TTS.

    Args:
        text: Raw response text that may contain markdown.

    Returns:
        Clean plain text safe for speech synthesis.
    """
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline backticks
    text = re.sub(r"`[^`]*`", "", text)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    # Remove headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Convert links to text only
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove bullet/numbered list markers
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Replace multiple newlines with a period + space
    text = re.sub(r"\n{2,}", ". ", text)
    # Replace single newlines with a space
    text = re.sub(r"\n", " ", text)
    # Remove banned filler phrases
    text = _BANNED_PHRASES.sub("", text)
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text).strip()
    return text


class FishTTSError(Exception):
    """Raised when Fish Audio API call fails."""


class FishTTSClient:
    """Client for Fish Audio cloud TTS API."""

    def __init__(
        self,
        api_key: str | None = None,
        voice_id: str | None = None,
        format: str = "mp3",
    ) -> None:
        """Initialize Fish TTS client.

        Args:
            api_key: Fish Audio API key. Falls back to FISH_API_KEY env var.
            voice_id: Reference voice ID. Falls back to FISH_VOICE_ID env var.
            format: Audio format to request (default: mp3).
        """
        self._api_key = api_key or os.environ.get("FISH_API_KEY", "")
        self._voice_id = voice_id or os.environ.get("FISH_VOICE_ID", "")
        self._format = format

        if not self._api_key:
            logger.warning("FISH_API_KEY not set — Fish TTS will fail at runtime")

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to MP3 audio bytes via Fish Audio API.

        Args:
            text: Text to synthesize.

        Returns:
            MP3 audio bytes.

        Raises:
            FishTTSError: On API error or non-2xx response.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "text": text,
            "format": self._format,
        }
        if self._voice_id:
            payload["reference_id"] = self._voice_id

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(FISH_API_URL, headers=headers, json=payload)

            if response.status_code != 200:
                raise FishTTSError(
                    f"Fish Audio API error {response.status_code}: {response.text[:200]}"
                )

            audio_bytes = response.content
            logger.debug(f"Fish TTS: synthesized {len(audio_bytes)} bytes for text: {text[:60]!r}")
            return audio_bytes

        except httpx.RequestError as exc:
            raise FishTTSError(f"Fish Audio request failed: {exc}") from exc
