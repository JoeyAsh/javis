# Feature Spec: Voice Realism UX

## Status
Planned — awaiting implementation authorization

## Summary
Optimize the JARVIS voice interaction pipeline for sub-second perceived latency, natural conversation flow, and token efficiency. The goal is to make voice interactions feel like talking to a real human assistant rather than a chatbot.

## Goals
- Sub-second perceived latency from end-of-user-speech to JARVIS-speaking-first-word
- Interruptible speech (barge-in) with immediate TTS cutoff
- Natural disfluencies and acknowledgments that mask processing delays
- Minimal token burn through system prompt optimization and response caching
- Conversation flow that respects natural turn-taking patterns

## Non-Goals
- Emotion/mood simulation beyond voice prosody adjustments
- Voice cloning or custom voice training
- Real-time speech translation
- Multi-speaker detection or diarization
- Video/lip-sync integration

---

## Latency Pipeline Budget

Target: First audio output within ~1.0s of user utterance end.

| Stage | Target | Implementation |
|-------|--------|----------------|
| Wake word detection | 50ms | OpenWakeWord already optimized |
| STT partial result | 200ms | faster-whisper with streaming partials |
| Intent/route decision | 100ms | Local regex + lightweight classifier |
| Agent streaming start | 400ms | OpenClaw or Claude streaming API |
| TTS first byte | 250ms | Fish Audio streaming endpoint |
| **Total P50** | **~1.0s** | End-to-end target |
| **Total P90** | **<2.0s** | Acceptable worst case |

### Streaming Architecture

```
User speech ends
       |
       v
[STT: partial → final]  ─────────────────────────────┐
       |                                              |
       v                                              |
[Intent classifier]  ← <100ms decision               |
       |                                              |
       ├─ Cached response? ─────────────────────┐     |
       |                                        |     |
       v                                        v     |
[OpenClaw/Claude streaming] ──> [Sentence splitter]  |
       |                               |              |
       |                               v              |
       |                        [TTS queue]           |
       |                               |              |
       v                               v              |
[Full response complete]        [Audio playback starts]
```

---

## Streaming LLM to Streaming TTS

### Sentence Boundary Splitting

Split agent response on sentence boundaries; start TTS on first complete sentence while remaining tokens still generate.

```python
# src/audio/stream_splitter.py

import re
from typing import AsyncIterator

SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+(?=[A-ZÄÖÜ])|(?<=[.!?])$')

class StreamSplitter:
    """Split streaming LLM output into sentences for TTS pipelining."""

    def __init__(self, min_chars: int = 20, max_wait_ms: int = 500) -> None:
        """Initialize splitter.
        
        Args:
            min_chars: Minimum characters before attempting split
            max_wait_ms: Maximum ms to wait for sentence completion
        """
        self._min_chars = min_chars
        self._max_wait_ms = max_wait_ms
        self._buffer = ""

    async def process(
        self,
        token_stream: AsyncIterator[str],
    ) -> AsyncIterator[str]:
        """Process token stream and yield complete sentences.
        
        Args:
            token_stream: Async iterator of LLM tokens
            
        Yields:
            Complete sentences ready for TTS
        """
        async for token in token_stream:
            self._buffer += token
            
            # Check for sentence boundary
            if len(self._buffer) >= self._min_chars:
                match = SENTENCE_ENDINGS.search(self._buffer)
                if match:
                    sentence = self._buffer[:match.end()].strip()
                    self._buffer = self._buffer[match.end():].strip()
                    if sentence:
                        yield sentence
        
        # Yield remaining buffer
        if self._buffer.strip():
            yield self._buffer.strip()
        self._buffer = ""
```

### TTS Pipeline Integration

```python
# src/audio/tts_pipeline.py

import asyncio
from collections.abc import AsyncIterator

class TTSPipeline:
    """Pipeline streaming sentences to TTS with overlap."""

    def __init__(
        self,
        tts_client: "FishAudioClient",
        audio_player: "AudioPlayer",
    ) -> None:
        self._tts = tts_client
        self._player = audio_player
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=3)
        self._playing = False
        self._cancelled = False

    async def stream_sentences(
        self,
        sentences: AsyncIterator[str],
        voice_id: str,
    ) -> None:
        """Stream sentences through TTS to audio output.
        
        Starts playback on first sentence while generating subsequent ones.
        """
        self._cancelled = False
        
        # Start playback consumer
        playback_task = asyncio.create_task(self._playback_loop())
        
        try:
            async for sentence in sentences:
                if self._cancelled:
                    break
                
                # Generate TTS for sentence
                audio = await self._tts.synthesize_streaming(
                    text=sentence,
                    voice_id=voice_id,
                )
                
                # Queue for playback
                await self._queue.put(audio)
            
            # Signal end of stream
            await self._queue.put(None)
            await playback_task
            
        except asyncio.CancelledError:
            self._cancelled = True
            await self._queue.put(None)

    async def _playback_loop(self) -> None:
        """Consume audio queue and play."""
        while True:
            audio = await self._queue.get()
            if audio is None:
                break
            if self._cancelled:
                continue
            
            self._playing = True
            await self._player.play(audio)
            self._playing = False

    def cancel(self) -> None:
        """Cancel playback immediately (barge-in)."""
        self._cancelled = True
        self._player.stop()
        
        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    @property
    def is_playing(self) -> bool:
        return self._playing and not self._cancelled
```

---

## Barge-In / Interruption Handling

### Voice Activity Detection During TTS

```python
# src/audio/barge_in.py

import asyncio
from typing import Callable, Awaitable

class BargeInDetector:
    """Detect user speech during TTS playback and trigger interruption."""

    def __init__(
        self,
        vad: "VADDetector",
        tts_pipeline: "TTSPipeline",
        on_barge_in: Callable[[], Awaitable[None]],
        sensitivity_ms: int = 150,
    ) -> None:
        """Initialize barge-in detector.
        
        Args:
            vad: Voice Activity Detector instance
            tts_pipeline: TTS pipeline to cancel
            on_barge_in: Callback when barge-in detected
            sensitivity_ms: Minimum speech duration to trigger
        """
        self._vad = vad
        self._tts = tts_pipeline
        self._on_barge_in = on_barge_in
        self._sensitivity_ms = sensitivity_ms
        self._monitoring = False

    async def start_monitoring(self) -> None:
        """Start monitoring for user speech during TTS."""
        self._monitoring = True
        speech_start: float | None = None
        
        while self._monitoring and self._tts.is_playing:
            is_speech = await self._vad.is_speech()
            
            if is_speech:
                if speech_start is None:
                    speech_start = asyncio.get_event_loop().time()
                else:
                    duration_ms = (asyncio.get_event_loop().time() - speech_start) * 1000
                    if duration_ms >= self._sensitivity_ms:
                        # Barge-in detected
                        await self._handle_barge_in()
                        return
            else:
                speech_start = None
            
            await asyncio.sleep(0.05)  # 50ms polling

    async def _handle_barge_in(self) -> None:
        """Handle barge-in: cancel TTS, notify system."""
        # Target: <150ms from detection to silence
        self._tts.cancel()
        self._monitoring = False
        await self._on_barge_in()

    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self._monitoring = False
```

### Cancellation Token to Provider

```python
# When barge-in detected, send cancellation to agent
async def handle_barge_in():
    # Cancel ongoing OpenClaw query
    await openclaw_client.cancel_current_query()
    
    # Transition to listening state
    orb_state.set("listening")
    
    # Log for analytics
    logger.info("Barge-in detected, TTS cancelled")
```

---

## Backchannels During Long User Turns

### Pre-Cached Audio Blobs

Low-volume acknowledgment sounds during natural pauses in user speech.

```python
# src/audio/backchannels.py

import random
from pathlib import Path

BACKCHANNEL_PHRASES = {
    "de": ["mhm", "ja", "ok", "verstehe"],
    "en": ["mhm", "right", "ok", "I see"],
}

class BackchannelPlayer:
    """Play subtle acknowledgments during long user turns."""

    def __init__(
        self,
        audio_player: "AudioPlayer",
        cache_dir: Path,
        silence_threshold_ms: int = 1200,
        volume: float = 0.3,  # 30% of normal volume
    ) -> None:
        self._player = audio_player
        self._cache_dir = cache_dir
        self._silence_threshold = silence_threshold_ms / 1000
        self._volume = volume
        self._last_backchannel = 0.0
        self._min_interval = 3.0  # Minimum 3s between backchannels

    async def maybe_play(
        self,
        silence_duration: float,
        language: str,
    ) -> bool:
        """Maybe play a backchannel if conditions are met.
        
        Args:
            silence_duration: Duration of current silence in seconds
            language: Language code for phrase selection
            
        Returns:
            True if backchannel was played
        """
        import time
        now = time.time()
        
        # Check conditions
        if silence_duration < self._silence_threshold:
            return False
        if now - self._last_backchannel < self._min_interval:
            return False
        
        # Select and play
        phrase = random.choice(BACKCHANNEL_PHRASES.get(language, BACKCHANNEL_PHRASES["en"]))
        audio_path = self._cache_dir / f"{language}_{phrase}.wav"
        
        if audio_path.exists():
            await self._player.play(
                audio_path,
                volume=self._volume,
            )
            self._last_backchannel = now
            return True
        
        return False
```

---

## Thinking Fillers

### Pre-Cached Filler Phrases

Play a short neutral filler if agent response exceeds 800ms post-utterance.

```python
# src/audio/fillers.py

import asyncio
import random
from pathlib import Path

FILLER_PHRASES = {
    "de": ["Moment...", "Einen Augenblick...", "Lassen Sie mich sehen..."],
    "en": ["One moment...", "Let me see...", "Just a moment..."],
}

class FillerPlayer:
    """Play thinking fillers when response is delayed."""

    def __init__(
        self,
        audio_player: "AudioPlayer",
        cache_dir: Path,
        delay_threshold_ms: int = 800,
    ) -> None:
        self._player = audio_player
        self._cache_dir = cache_dir
        self._delay_threshold = delay_threshold_ms / 1000
        self._played = False

    async def wait_for_response_or_filler(
        self,
        response_event: asyncio.Event,
        language: str,
    ) -> None:
        """Wait for response; play filler if delayed.
        
        Args:
            response_event: Event that fires when response starts
            language: Language for filler phrase
        """
        self._played = False
        
        try:
            await asyncio.wait_for(
                response_event.wait(),
                timeout=self._delay_threshold,
            )
        except asyncio.TimeoutError:
            # Response delayed, play filler
            await self._play_filler(language)

    async def _play_filler(self, language: str) -> None:
        """Play a random filler phrase."""
        phrase = random.choice(FILLER_PHRASES.get(language, FILLER_PHRASES["en"]))
        audio_path = self._cache_dir / f"filler_{language}_{phrase.replace('...', '').strip().lower()}.wav"
        
        if audio_path.exists():
            await self._player.play(audio_path)
            self._played = True

    @property
    def filler_played(self) -> bool:
        return self._played
```

---

## Acknowledgment-First Pattern

### Quick Ack Before Substantive Response

For complex questions, emit a 1-word acknowledgment before the real response.

```python
# src/brain/quick_ack.py

import re

# Questions that warrant quick ack
COMPLEX_PATTERNS = [
    r"\b(explain|describe|tell me about|how does|why is|what is the difference)\b",
    r"\b(erklär|beschreib|erzähl|wie funktioniert|warum ist|was ist der unterschied)\b",
    r"\?.*\?",  # Multiple questions
]

ACK_PHRASES = {
    "de": ["Klar.", "Verstanden.", "Gut."],
    "en": ["Right.", "Got it.", "Sure."],
}

class QuickAckGenerator:
    """Generate quick acknowledgments for complex queries."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._patterns = [re.compile(p, re.IGNORECASE) for p in COMPLEX_PATTERNS]

    def should_ack(self, text: str) -> bool:
        """Check if query warrants quick ack."""
        return any(p.search(text) for p in self._patterns)

    def get_ack(self, language: str) -> tuple[str, Path]:
        """Get acknowledgment phrase and audio path.
        
        Returns:
            Tuple of (phrase, audio_path)
        """
        import random
        phrases = ACK_PHRASES.get(language, ACK_PHRASES["en"])
        phrase = random.choice(phrases)
        audio_path = self._cache_dir / f"ack_{language}_{phrase.lower().replace('.', '')}.wav"
        return phrase, audio_path
```

### Integration in Voice Pipeline

```python
async def handle_voice_input(text: str, language: str):
    # Check if quick ack needed
    if quick_ack.should_ack(text):
        phrase, audio_path = quick_ack.get_ack(language)
        if audio_path.exists():
            # Play ack immediately (<400ms target)
            await audio_player.play(audio_path)
    
    # Then process full response
    response = await orchestrator.process(text, language)
    await tts_pipeline.stream(response.text)
```

---

## Prosody Configuration

### Context-Aware Voice Settings

```python
# src/audio/prosody.py

from datetime import datetime
from enum import Enum

class VoiceMood(Enum):
    CALM = "calm"
    BRIGHT = "bright"
    SERIOUS = "serious"
    NEUTRAL = "neutral"

def get_voice_mood(
    orb_state: str,
    hour: int | None = None,
    error_context: bool = False,
) -> VoiceMood:
    """Determine voice mood based on context.
    
    Args:
        orb_state: Current orb visualization state
        hour: Hour of day (0-23), or None for current
        error_context: Whether responding to an error
        
    Returns:
        Appropriate voice mood
    """
    if hour is None:
        hour = datetime.now().hour
    
    # Error context overrides
    if error_context:
        return VoiceMood.SERIOUS
    
    # Time-based defaults
    if 6 <= hour < 10:
        return VoiceMood.BRIGHT  # Morning energy
    elif 22 <= hour or hour < 6:
        return VoiceMood.CALM  # Night calm
    else:
        return VoiceMood.NEUTRAL

def get_fish_audio_params(mood: VoiceMood) -> dict:
    """Map mood to Fish Audio API parameters.
    
    Returns:
        Dictionary of Fish Audio synthesis parameters
    """
    params = {
        VoiceMood.CALM: {
            "speed": 0.9,
            "pitch": -2,
            "volume": 0.8,
        },
        VoiceMood.BRIGHT: {
            "speed": 1.05,
            "pitch": 1,
            "volume": 1.0,
        },
        VoiceMood.SERIOUS: {
            "speed": 0.95,
            "pitch": -3,
            "volume": 0.9,
        },
        VoiceMood.NEUTRAL: {
            "speed": 1.0,
            "pitch": 0,
            "volume": 1.0,
        },
    }
    return params.get(mood, params[VoiceMood.NEUTRAL])
```

---

## Disfluencies (Opt-In)

### Natural Speech Imperfections

```yaml
# config.yaml
voice:
  natural_disfluencies: false  # Default off
  disfluency_rate: 0.1  # 10% of responses when enabled
  disfluency_phrases:
    de: ["also", "äh", "nun"]
    en: ["well", "um", "so"]
```

```python
# src/audio/disfluencies.py

import random

class DisfluencyInjector:
    """Inject natural disfluencies into responses."""

    def __init__(self, config: dict) -> None:
        self._enabled = config.get("natural_disfluencies", False)
        self._rate = config.get("disfluency_rate", 0.1)
        self._phrases = config.get("disfluency_phrases", {})

    def maybe_inject(self, text: str, language: str) -> str:
        """Maybe inject a disfluency at the start of response.
        
        Args:
            text: Original response text
            language: Language code
            
        Returns:
            Text with possible disfluency prepended
        """
        if not self._enabled:
            return text
        
        if random.random() > self._rate:
            return text
        
        phrases = self._phrases.get(language, self._phrases.get("en", []))
        if not phrases:
            return text
        
        disfluency = random.choice(phrases)
        return f"{disfluency}, {text}"
```

---

## Response Length Control

### System Prompt Modifier

```python
# src/brain/response_length.py

CONCISE_MODIFIER = """
RESPONSE LENGTH: Keep responses to 2 sentences or fewer unless the user explicitly 
asks for detail (phrases like "erklär mir mehr", "tell me more", "details bitte", 
"expand on that"). When detail is requested, you may use up to 5 sentences.
"""

DETAIL_TRIGGERS = [
    r"\b(more detail|expand|elaborate|tell me more|explain more)\b",
    r"\b(mehr detail|erklär mir mehr|details bitte|genauer)\b",
]

class ResponseLengthController:
    """Control response length based on user requests."""

    def __init__(self) -> None:
        self._detail_patterns = [re.compile(p, re.IGNORECASE) for p in DETAIL_TRIGGERS]
        self._detail_mode = False

    def check_detail_request(self, text: str) -> bool:
        """Check if user is requesting more detail."""
        self._detail_mode = any(p.search(text) for p in self._detail_patterns)
        return self._detail_mode

    def get_length_modifier(self) -> str:
        """Get system prompt modifier for current mode."""
        if self._detail_mode:
            return ""  # No restriction in detail mode
        return CONCISE_MODIFIER
```

---

## Pre-Cached Phrase Library

### Generation Script

```python
# scripts/generate_voice_cache.py

import asyncio
from pathlib import Path

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
    tts_client: "FishAudioClient",
    voice_id: str,
    output_dir: Path,
) -> None:
    """Generate all cached voice phrases.
    
    Args:
        tts_client: Fish Audio client
        voice_id: Voice ID to use
        output_dir: Output directory for .wav files
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for category, languages in PHRASES.items():
        for language, phrases in languages.items():
            for phrase in phrases:
                filename = f"{category}_{language}_{phrase.lower().replace(' ', '_')}.wav"
                filepath = output_dir / filename
                
                if filepath.exists():
                    continue
                
                audio = await tts_client.synthesize(
                    text=phrase,
                    voice_id=voice_id,
                )
                filepath.write_bytes(audio)
                print(f"Generated: {filename}")

if __name__ == "__main__":
    # Run at install time or first startup
    asyncio.run(generate_cache(...))
```

---

## Token Efficiency

### System Prompt Budget

```python
# src/brain/persona.py

import tiktoken

MAX_SYSTEM_TOKENS = 500

def validate_persona_prompt(prompt: str) -> bool:
    """Validate that persona prompt is under token budget.
    
    Args:
        prompt: System prompt to validate
        
    Returns:
        True if under budget
        
    Raises:
        ValueError: If over budget
    """
    enc = tiktoken.encoding_for_model("claude-3-sonnet")
    token_count = len(enc.encode(prompt))
    
    if token_count > MAX_SYSTEM_TOKENS:
        raise ValueError(
            f"Persona prompt exceeds budget: {token_count} > {MAX_SYSTEM_TOKENS} tokens"
        )
    
    return True
```

### Conversation History Pruning

```python
# src/brain/history_pruning.py

from dataclasses import dataclass

@dataclass
class PruningConfig:
    full_turns_to_keep: int = 5
    summarized_turns_to_keep: int = 10
    summary_model: str = "claude-haiku"
    max_summary_tokens: int = 100

class HistoryPruner:
    """Prune conversation history for token efficiency."""

    def __init__(self, config: PruningConfig) -> None:
        self._config = config

    async def prune(
        self,
        history: list[dict],
        summarizer: "Callable",
    ) -> list[dict]:
        """Prune history, summarizing older turns.
        
        Args:
            history: Full conversation history
            summarizer: Function to summarize turns
            
        Returns:
            Pruned history with summaries
        """
        if len(history) <= self._config.full_turns_to_keep:
            return history
        
        # Keep recent turns in full
        recent = history[-self._config.full_turns_to_keep:]
        
        # Summarize older turns
        older = history[:-self._config.full_turns_to_keep]
        if older:
            summary = await summarizer(
                older,
                max_tokens=self._config.max_summary_tokens,
                model=self._config.summary_model,
            )
            summarized = [{"role": "system", "content": f"[Earlier conversation summary: {summary}]"}]
            return summarized + recent
        
        return recent
```

### Model Tiering

```python
# src/brain/model_tiering.py

class ModelTiering:
    """Route queries to appropriate model tier."""

    CHEAP_MODEL = "claude-haiku"  # For intent routing, acks
    FLAGSHIP_MODEL = "claude-sonnet-4-6"  # For substantive answers

    def __init__(self) -> None:
        pass

    def get_model_for_task(self, task: str) -> str:
        """Select model based on task type.
        
        Args:
            task: Task identifier
            
        Returns:
            Model identifier
        """
        cheap_tasks = {"intent_routing", "ack_generation", "summary"}
        
        if task in cheap_tasks:
            return self.CHEAP_MODEL
        
        return self.FLAGSHIP_MODEL
```

### Response Caching

```python
# src/brain/response_cache.py

import hashlib
import time
from collections import OrderedDict

class ResponseCache:
    """Cache recent intent+params → response mappings."""

    def __init__(
        self,
        max_size: int = 100,
        ttl_seconds: int = 60,
    ) -> None:
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def _make_key(self, intent: str, params: dict) -> str:
        """Create cache key from intent and params."""
        content = f"{intent}:{sorted(params.items())}"
        return hashlib.md5(content.encode()).hexdigest()

    def get(self, intent: str, params: dict) -> str | None:
        """Get cached response if available and fresh.
        
        Returns:
            Cached response or None
        """
        key = self._make_key(intent, params)
        
        if key not in self._cache:
            return None
        
        response, timestamp = self._cache[key]
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None
        
        # Move to end (LRU)
        self._cache.move_to_end(key)
        return response

    def set(self, intent: str, params: dict, response: str) -> None:
        """Cache a response."""
        key = self._make_key(intent, params)
        self._cache[key] = (response, time.time())
        
        # Enforce max size
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
```

---

## Conversation Flow Tuning

### End-of-Turn Detection

```python
# src/audio/turn_detection.py

from dataclasses import dataclass

@dataclass
class TurnDetectionConfig:
    silence_threshold_ms: int = 800
    use_prosodic_hints: bool = True
    falling_pitch_threshold: float = -0.15  # Hz/ms

class TurnDetector:
    """Detect end of user turn using multiple signals."""

    def __init__(
        self,
        config: TurnDetectionConfig,
        vad: "VADDetector",
    ) -> None:
        self._config = config
        self._vad = vad

    async def is_turn_complete(
        self,
        silence_duration_ms: float,
        stt_is_final: bool,
        pitch_slope: float | None = None,
    ) -> bool:
        """Determine if user turn is complete.
        
        Args:
            silence_duration_ms: Current silence duration
            stt_is_final: Whether STT flagged this as final
            pitch_slope: Pitch slope if prosodic analysis available
            
        Returns:
            True if turn appears complete
        """
        # STT final flag is strong signal
        if stt_is_final and silence_duration_ms >= 400:
            return True
        
        # Silence threshold
        if silence_duration_ms >= self._config.silence_threshold_ms:
            return True
        
        # Prosodic hint: falling pitch suggests statement end
        if (
            self._config.use_prosodic_hints
            and pitch_slope is not None
            and pitch_slope < self._config.falling_pitch_threshold
            and silence_duration_ms >= 400
        ):
            return True
        
        return False
```

### Overlapping Speech Handling

```python
# src/brain/speech_queue.py

import asyncio
from collections import deque

class SpeechQueue:
    """Queue user utterances that arrive during JARVIS thinking state."""

    def __init__(self, max_queue: int = 3) -> None:
        self._queue: deque[str] = deque(maxlen=max_queue)
        self._lock = asyncio.Lock()

    async def add(self, utterance: str) -> None:
        """Add utterance to queue."""
        async with self._lock:
            self._queue.append(utterance)

    async def pop(self) -> str | None:
        """Get next queued utterance."""
        async with self._lock:
            return self._queue.popleft() if self._queue else None

    async def has_pending(self) -> bool:
        """Check if there are pending utterances."""
        async with self._lock:
            return len(self._queue) > 0

    async def clear(self) -> None:
        """Clear all pending utterances."""
        async with self._lock:
            self._queue.clear()
```

---

## Configuration

### config.yaml Section

```yaml
voice:
  # Latency targets
  first_audio_target_ms: 1000
  p90_latency_target_ms: 2000
  
  # Streaming
  sentence_split_min_chars: 20
  tts_queue_size: 3
  
  # Barge-in
  barge_in_enabled: true
  barge_in_sensitivity_ms: 150
  
  # Backchannels
  backchannels_enabled: true
  backchannel_silence_threshold_ms: 1200
  backchannel_volume: 0.3
  backchannel_min_interval_seconds: 3
  
  # Fillers
  thinking_filler_enabled: true
  thinking_filler_delay_ms: 800
  
  # Quick ack
  quick_ack_enabled: true
  quick_ack_target_ms: 400
  
  # Prosody
  prosody_context_aware: true
  
  # Disfluencies
  natural_disfluencies: false
  disfluency_rate: 0.1
  
  # Response length
  default_response_sentences: 2
  detail_mode_sentences: 5
  
  # Token efficiency
  system_prompt_max_tokens: 500
  history_full_turns: 5
  history_summarized_turns: 10
  response_cache_ttl_seconds: 60
  response_cache_max_size: 100
  
  # Turn detection
  silence_threshold_ms: 800
  use_prosodic_hints: true
  
  # Phrase cache
  cache_directory: "data/voice_cache"
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | P50 time from user-utterance-end to JARVIS-first-audio <= 1.2s | Performance test |
| 2 | P90 time from user-utterance-end to JARVIS-first-audio <= 2.0s | Performance test |
| 3 | Barge-in: user-speech-detected-to-TTS-silence <= 150ms | Performance test |
| 4 | Cached ack/filler coverage: >= 90% of conversations start with cached audio | Analytics |
| 5 | Token usage per average turn <= 40% below naive full-history approach | Unit test |
| 6 | System prompt stays under 500 tokens | Linter test |
| 7 | Streaming TTS starts on first sentence, not full response | Integration test |
| 8 | Backchannels play during user pauses > 1.2s | Integration test |
| 9 | Fillers play when response delayed > 800ms | Integration test |
| 10 | Quick acks play for complex queries < 400ms | Integration test |
| 11 | Prosody adjusts based on time of day | Unit test |
| 12 | Response caching reuses identical intent+params | Unit test |
| 13 | History pruning summarizes old turns | Unit test |
| 14 | Voice phrase cache generated at first run | Integration test |
| 15 | User study: "feels human" >= 4/5 on 5-point scale | Manual verification |

---

## Files Created

| File | Purpose |
|------|---------|
| `src/audio/stream_splitter.py` | Sentence boundary splitting |
| `src/audio/tts_pipeline.py` | Streaming TTS pipeline |
| `src/audio/barge_in.py` | Barge-in detection |
| `src/audio/backchannels.py` | Backchannel player |
| `src/audio/fillers.py` | Thinking filler player |
| `src/audio/prosody.py` | Prosody configuration |
| `src/audio/disfluencies.py` | Disfluency injection |
| `src/audio/turn_detection.py` | End-of-turn detection |
| `src/brain/quick_ack.py` | Quick acknowledgment generator |
| `src/brain/response_length.py` | Response length control |
| `src/brain/history_pruning.py` | Conversation history pruning |
| `src/brain/model_tiering.py` | Model tier selection |
| `src/brain/response_cache.py` | Response caching |
| `src/brain/speech_queue.py` | Overlapping speech queue |
| `scripts/generate_voice_cache.py` | Pre-cached phrase generator |
| `data/voice_cache/` | Cached audio files (generated) |
| `tests/audio/test_*.py` | Audio module tests |
| `tests/brain/test_*.py` | Brain module tests |

## Files Modified

| File | Change |
|------|--------|
| `src/audio/__init__.py` | Export new modules |
| `src/brain/persona.py` | Add token budget validation |
| `src/main.py` | Initialize voice realism components |
| `src/api/ws_server.py` | Integrate streaming and barge-in |
| `config/config.yaml` | Add voice section |

---

## Implementation Plan

### Batch 1 — Streaming Pipeline
1. `code` -> Create `src/audio/stream_splitter.py`
2. `code` -> Create `src/audio/tts_pipeline.py`
3. `test` -> Unit tests for streaming components
4. `review` -> Review batch 1

### Batch 2 — Barge-In and Interruption
5. `code` -> Create `src/audio/barge_in.py`
6. `code` -> Create `src/audio/turn_detection.py`
7. `test` -> Integration tests for barge-in
8. `review` -> Review batch 2

### Batch 3 — Natural Conversation Elements
9. `code` -> Create `src/audio/backchannels.py`
10. `code` -> Create `src/audio/fillers.py`
11. `code` -> Create `src/brain/quick_ack.py`
12. `test` -> Integration tests
13. `review` -> Review batch 3

### Batch 4 — Token Efficiency
14. `code` -> Create `src/brain/response_cache.py`
15. `code` -> Create `src/brain/history_pruning.py`
16. `code` -> Create `src/brain/model_tiering.py`
17. `code` -> Update `src/brain/persona.py` with token validation
18. `test` -> Unit tests for efficiency modules
19. `review` -> Review batch 4

### Batch 5 — Voice Cache and Prosody
20. `code` -> Create `scripts/generate_voice_cache.py`
21. `code` -> Create `src/audio/prosody.py`
22. `code` -> Create `src/audio/disfluencies.py`
23. `test` -> Integration tests
24. `review` -> Review batch 5

### Batch 6 — Integration
25. `code` -> Update `src/main.py` with initialization
26. `code` -> Update `config/config.yaml`
27. `test` -> End-to-end latency tests
28. `review` -> Final review

---

## Open Questions

1. **STT provider evaluation:** Which STT provider for absolute lowest German latency — keep faster-whisper or evaluate Deepgram / AssemblyAI / ElevenLabs STT?
   - **Recommendation:** Keep faster-whisper for MVP (local, low latency); benchmark alternatives in Phase B.

2. **TTS provider consolidation:** Stay on Fish Audio (German quality + streaming verified), or consolidate on ElevenLabs since OpenClaw uses it?
   - **Recommendation:** Stay on Fish Audio for German quality requirement.

3. **Max acceptable filler rate:** One filler every N turns before it feels fake?
   - **Recommendation:** Max 1 filler per 3 turns; implement rate limiting.

4. **Disfluencies default:** Opt-in or opt-out for disfluencies?
   - **Recommendation:** Opt-in (default off); may sound off-brand for JARVIS persona.

5. **Prosodic analysis:** Add pitch slope detection for better end-of-turn, or rely on silence + STT final only?
   - **Recommendation:** Implement prosodic hints if cheap library available (e.g., librosa); otherwise silence + STT is sufficient.

---

## Dependencies

### pip packages
```
tiktoken>=0.5.0  # For token counting
```

### Optional (for prosodic analysis)
```
librosa>=0.10.0  # For pitch extraction
```

---

**Status:** Planned — awaiting implementation authorization
