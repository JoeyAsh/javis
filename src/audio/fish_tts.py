"""Fish Audio cloud TTS integration for JARVIS.

Sends text to Fish Audio API and returns MP3 audio bytes.

Prosody support: ``FishTTSClient.synthesize()`` accepts an optional
``prosody_hint`` dict with keys ``speed`` (float) and ``energy`` (str).
Fish Audio's REST API supports ``speed`` natively; the ``energy`` key is
informational and is logged at startup rather than sent to the API.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any

import httpx

from utils.logger import get_logger

if TYPE_CHECKING:
    from audio.prosody import ProsodyHint

logger = get_logger("fish_tts")

# Set once at startup so we only log the inert-energy warning once.
_prosody_energy_warned: bool = False

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
        self._client: httpx.AsyncClient | None = None

        if not self._api_key:
            logger.warning("FISH_API_KEY not set — Fish TTS will fail at runtime")

    async def _get_client(self) -> httpx.AsyncClient:
        """Return the shared httpx client, creating it lazily on first call."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def aclose(self) -> None:
        """Close the shared httpx client and release its resources. Idempotent."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def synthesize(
        self,
        text: str,
        prosody_hint: "ProsodyHint | None" = None,
    ) -> bytes:
        """Synthesize text to MP3 audio bytes via Fish Audio API.

        Args:
            text: Text to synthesize.
            prosody_hint: Optional prosody hint dict with ``speed`` (float)
                and ``energy`` (str) keys produced by
                :func:`audio.prosody.get_prosody_hint`.  When provided,
                ``speed`` is forwarded to the Fish Audio API.  The
                ``energy`` key is informational only — Fish Audio has no
                direct energy/mood parameter, so it is acknowledged via a
                one-time startup log rather than sent to the API.

        Returns:
            MP3 audio bytes.

        Raises:
            FishTTSError: On API error or non-2xx response.
        """
        global _prosody_energy_warned

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

        if prosody_hint is not None:
            speed = prosody_hint.get("speed")
            if speed is not None and speed != 1.0:
                payload["speed"] = float(speed)

            energy = prosody_hint.get("energy")
            if energy and energy != "neutral" and not _prosody_energy_warned:
                logger.info(
                    f"Prosody energy={energy!r} is inert for Fish Audio "
                    "(API has no mood/energy parameter — speed applied only)"
                )
                _prosody_energy_warned = True

        try:
            client = await self._get_client()
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
