#!/usr/bin/env python3
"""Generate pre-cached voice phrases for JARVIS.

Creates cached .wav files for fillers, backchannels, and acknowledgments
to enable low-latency voice responses.

Usage:
    PYTHONPATH=src python scripts/generate_voice_cache.py

Requires:
    - FISH_API_KEY environment variable
    - FISH_VOICE_ID environment variable
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

from audio.fish_tts import FishTTSClient
from utils.logger import get_logger, setup_logger

logger = get_logger("generate_voice_cache")

# Phrases to pre-cache, organized by category
PHRASES = {
    "ack": {
        "de": ["Klar", "Verstanden", "Gut", "Ja"],
        "en": ["Right", "Got it", "Sure", "Yes"],
    },
    "filler": {
        "de": ["Moment", "Einen Augenblick", "Lassen Sie mich sehen"],
        "en": ["One moment", "Let me see", "Just a moment"],
    },
    "backchannel": {
        "de": ["mhm", "ja", "ok", "verstehe"],
        "en": ["mhm", "right", "ok", "I see"],
    },
    "error": {
        "de": ["Es ist ein Fehler aufgetreten", "Das hat nicht funktioniert"],
        "en": ["An error occurred", "That didn't work"],
    },
}


async def generate_cache(
    tts_client: FishTTSClient,
    output_dir: Path,
    overwrite: bool = False,
) -> dict[str, int]:
    """Generate all cached voice phrases.

    Args:
        tts_client: Fish Audio client for synthesis.
        output_dir: Output directory for .wav files.
        overwrite: Whether to overwrite existing files.

    Returns:
        Dictionary with counts: {"generated": N, "skipped": M, "failed": P}
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = {"generated": 0, "skipped": 0, "failed": 0}

    for category, languages in PHRASES.items():
        for language, phrases in languages.items():
            for phrase in phrases:
                # Build filename
                safe_phrase = phrase.lower().replace(" ", "_").replace("...", "")
                filename = f"{category}_{language}_{safe_phrase}.wav"
                filepath = output_dir / filename

                if filepath.exists() and not overwrite:
                    logger.debug(f"Skipping existing: {filename}")
                    stats["skipped"] += 1
                    continue

                try:
                    logger.info(f"Generating: {filename} ({phrase})")
                    audio = await tts_client.synthesize(phrase)

                    # Fish Audio returns MP3, but we'll save as-is
                    # (rename to .mp3 if needed, or convert)
                    mp3_path = output_dir / filename.replace(".wav", ".mp3")
                    mp3_path.write_bytes(audio)

                    stats["generated"] += 1
                    logger.info(f"Generated: {mp3_path.name} ({len(audio)} bytes)")

                except Exception as e:
                    logger.error(f"Failed to generate {filename}: {e}")
                    stats["failed"] += 1

    return stats


async def main() -> int:
    """Main entry point."""
    load_dotenv()
    setup_logger(level="INFO")

    # Verify environment
    api_key = os.environ.get("FISH_API_KEY")
    voice_id = os.environ.get("FISH_VOICE_ID")

    if not api_key:
        logger.error("FISH_API_KEY environment variable not set")
        return 1

    if not voice_id:
        logger.warning("FISH_VOICE_ID not set, using default voice")

    # Initialize client
    tts_client = FishTTSClient(api_key=api_key, voice_id=voice_id)

    # Output directory
    output_dir = Path(__file__).parent.parent / "data" / "voice_cache"

    logger.info(f"Output directory: {output_dir}")
    logger.info("Starting voice cache generation...")

    # Generate cache
    stats = await generate_cache(tts_client, output_dir, overwrite=False)

    # Report
    logger.info("=" * 50)
    logger.info(f"Generated: {stats['generated']} files")
    logger.info(f"Skipped (existing): {stats['skipped']} files")
    logger.info(f"Failed: {stats['failed']} files")
    logger.info("=" * 50)

    if stats["failed"] > 0:
        return 1

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Generation cancelled")
        sys.exit(1)
