#!/usr/bin/env python3
"""Download or generate voice profiles for JARVIS.

This script generates placeholder voice WAV files for testing.
In production, you would replace these with actual voice samples.
"""

import struct
import sys
import wave
from pathlib import Path

import numpy as np


def generate_tone_wav(
    filepath: Path,
    duration: float = 3.0,
    frequency: float = 220.0,
    sample_rate: int = 16000,
) -> None:
    """Generate a WAV file with a simple tone.

    Args:
        filepath: Path to save the WAV file
        duration: Duration in seconds
        frequency: Tone frequency in Hz
        sample_rate: Sample rate in Hz
    """
    print(f"Generating {filepath.name}...")

    # Generate samples
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)

    # Generate a gentle tone with harmonics for a richer sound
    audio = (
        np.sin(2 * np.pi * frequency * t) * 0.5
        + np.sin(2 * np.pi * frequency * 2 * t) * 0.25
        + np.sin(2 * np.pi * frequency * 3 * t) * 0.125
    )

    # Apply fade in/out to avoid clicks
    fade_samples = int(sample_rate * 0.1)
    audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
    audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)

    # Normalize and convert to int16
    audio = (audio / np.max(np.abs(audio)) * 0.8 * 32767).astype(np.int16)

    # Write WAV file
    with wave.open(str(filepath), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio.tobytes())

    print(f"  Created: {filepath} ({duration}s, {sample_rate}Hz)")


def generate_chime_wav(filepath: Path, sample_rate: int = 22050) -> None:
    """Generate a pleasant activation chime sound.

    Args:
        filepath: Path to save the WAV file
        sample_rate: Sample rate in Hz
    """
    print(f"Generating {filepath.name}...")

    duration = 0.3
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)

    # Two-tone chime (A5 and E6)
    freq1 = 880
    freq2 = 1320

    # Generate tones with envelope
    envelope = np.exp(-t * 6)

    tone1 = np.sin(2 * np.pi * freq1 * t) * envelope
    tone2 = np.sin(2 * np.pi * freq2 * t) * envelope * 0.7

    # Mix tones
    audio = (tone1 + tone2) * 0.5

    # Normalize and convert to int16
    audio = (audio / np.max(np.abs(audio)) * 0.8 * 32767).astype(np.int16)

    # Write WAV file
    with wave.open(str(filepath), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio.tobytes())

    print(f"  Created: {filepath} ({duration}s, {sample_rate}Hz)")


def main() -> None:
    """Generate placeholder voice profiles."""
    # Determine voices directory
    script_dir = Path(__file__).parent
    voices_dir = script_dir.parent / "voices"

    # Create directory if needed
    voices_dir.mkdir(exist_ok=True)

    print("JARVIS Voice Profile Generator")
    print("=" * 40)
    print(f"Output directory: {voices_dir}")
    print()

    # Generate main JARVIS voice profile
    jarvis_path = voices_dir / "jarvis.wav"
    if not jarvis_path.exists():
        generate_tone_wav(jarvis_path, duration=3.0, frequency=220.0)
    else:
        print(f"Skipping {jarvis_path.name} (already exists)")

    # Generate Darth Vader voice profile (lower pitch)
    vader_path = voices_dir / "darth_vader.wav"
    if not vader_path.exists():
        generate_tone_wav(vader_path, duration=3.0, frequency=150.0)
    else:
        print(f"Skipping {vader_path.name} (already exists)")

    # Generate activation chime
    chime_path = voices_dir / "chime.wav"
    if not chime_path.exists():
        generate_chime_wav(chime_path)
    else:
        print(f"Skipping {chime_path.name} (already exists)")

    print()
    print("Voice profile generation complete!")
    print()
    print("NOTE: These are placeholder audio files for testing.")
    print("For production use, replace them with actual voice samples:")
    print("  - jarvis.wav: 10-30 seconds of clear speech for voice cloning")
    print("  - Record in a quiet environment at 16kHz or higher")
    print()
    print("To create a custom voice profile, use:")
    print("  python scripts/clone_voice.py --input your_sample.wav --name custom")


if __name__ == "__main__":
    main()
