#!/usr/bin/env python3
"""Clone a voice profile for JARVIS.

This script copies a reference WAV file to the voices directory,
optionally applying pitch shifting.
"""

import argparse
import shutil
import sys
import wave
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile


def apply_pitch_shift(
    audio: np.ndarray, sample_rate: int, semitones: int
) -> np.ndarray:
    """Apply pitch shift to audio using scipy.

    Args:
        audio: Audio data as numpy array
        sample_rate: Sample rate in Hz
        semitones: Number of semitones to shift (negative = lower pitch)

    Returns:
        Pitch-shifted audio data
    """
    if semitones == 0:
        return audio

    # Calculate the pitch shift ratio
    ratio = 2 ** (semitones / 12.0)

    # Resample to shift pitch
    n_samples = int(len(audio) / ratio)
    shifted = signal.resample(audio, n_samples)

    # Resample back to original length to maintain duration
    result = signal.resample(shifted, len(audio))

    return result


def clone_voice(
    input_path: Path,
    output_name: str,
    pitch_shift: int = 0,
    voices_dir: Path | None = None,
) -> Path:
    """Clone a voice profile from a reference WAV file.

    Args:
        input_path: Path to input WAV file
        output_name: Name for the output profile (without .wav)
        pitch_shift: Pitch shift in semitones (negative = lower)
        voices_dir: Output directory for voices

    Returns:
        Path to the created voice profile
    """
    if voices_dir is None:
        voices_dir = Path(__file__).parent.parent / "voices"

    voices_dir.mkdir(exist_ok=True)

    output_path = voices_dir / f"{output_name}.wav"

    print(f"Cloning voice profile: {output_name}")
    print(f"  Input: {input_path}")
    print(f"  Output: {output_path}")

    if pitch_shift != 0:
        print(f"  Pitch shift: {pitch_shift} semitones")

        # Read input WAV
        sample_rate, audio = wavfile.read(input_path)

        # Convert to float for processing
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0

        # Handle stereo by converting to mono
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        # Apply pitch shift
        audio = apply_pitch_shift(audio, sample_rate, pitch_shift)

        # Normalize
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.9

        # Convert back to int16
        audio_int16 = (audio * 32767).astype(np.int16)

        # Write output WAV
        wavfile.write(output_path, sample_rate, audio_int16)

    else:
        # Simple copy without pitch shift
        shutil.copy2(input_path, output_path)

    print(f"  Voice profile created successfully!")

    return output_path


def main() -> None:
    """Main entry point for voice cloning CLI."""
    parser = argparse.ArgumentParser(
        description="Clone a voice profile for JARVIS TTS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clone a voice without modifications
  python clone_voice.py --input reference.wav --name my_voice

  # Clone with pitch shift (for Darth Vader-like effect)
  python clone_voice.py --input reference.wav --name darth_vader --pitch -4

  # Higher pitched voice
  python clone_voice.py --input reference.wav --name chipmunk --pitch 6
""",
    )

    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        required=True,
        help="Path to input reference WAV file (10-30 seconds of clear speech)",
    )

    parser.add_argument(
        "--name",
        "-n",
        type=str,
        required=True,
        help="Name for the voice profile (without .wav extension)",
    )

    parser.add_argument(
        "--pitch",
        "-p",
        type=int,
        default=0,
        help="Pitch shift in semitones (negative = lower, default: 0)",
    )

    args = parser.parse_args()

    # Validate input file
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not args.input.suffix.lower() == ".wav":
        print(f"Warning: Input file may not be a WAV file: {args.input}")

    # Validate name
    if not args.name.replace("_", "").replace("-", "").isalnum():
        print(
            f"Error: Profile name should only contain letters, numbers, "
            f"underscores, and hyphens: {args.name}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Clone the voice
    try:
        output_path = clone_voice(
            input_path=args.input,
            output_name=args.name,
            pitch_shift=args.pitch,
        )

        print()
        print("Voice profile ready!")
        print(f"To use this voice, set in config/config.yaml:")
        print(f"  tts:")
        print(f"    voice_profile: \"{args.name}\"")

        if args.pitch != 0:
            print(f"    pitch_shift: {args.pitch}")

    except Exception as e:
        print(f"Error cloning voice: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
