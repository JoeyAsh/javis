# Feature Spec: Spotify Integration

## Summary
Integrate Spotify for music control and ambient awareness. Users can control playback via voice ("play some jazz", "pause the music", "skip this song") and see current track info in the NowPlayingPanel. The integration uses `spotipy` with OAuth2 PKCE flow for authentication.

## Goals
- Enable voice-controlled Spotify playback: play, pause, next, previous, volume
- Display current track info (title, artist, album, album art) in NowPlayingPanel
- Support device selection when multiple Spotify devices are available
- Implement OAuth2 PKCE flow (no client secret required)
- Poll Spotify state at configurable interval to keep UI in sync

## Non-Goals
- Playlist creation or modification
- Social features (sharing, collaborative playlists)
- Podcast-specific controls
- Lyrics display
- Offline playback (Spotify Premium streaming only)

## Prerequisites
- **Spotify Premium account** — required for playback control
- **Spotify Developer App** — user must create at https://developer.spotify.com/dashboard
- Active Spotify device (desktop app, mobile app, or web player)

---

## Architecture

### Backend Components

```
src/integrations/spotify/
  __init__.py
  client.py           # SpotifyClient - spotipy wrapper

src/brain/agents/
  spotify_agent.py    # SpotifyAgent - voice intent handler
```

### Frontend Components

```
frontend/src/
  components/panels/
    NowPlayingPanel.tsx
  hooks/
    useSpotify.ts
```

---

## Spotify Client (`src/integrations/spotify/client.py`)

### Interface

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class SpotifyTrack:
    """Current track information."""
    track_id: str
    name: str
    artist: str
    album: str
    album_art_url: str
    duration_ms: int
    progress_ms: int
    is_playing: bool

@dataclass
class SpotifyDevice:
    """Spotify playback device."""
    id: str
    name: str
    type: str  # "Computer", "Smartphone", "Speaker", etc.
    is_active: bool
    volume_percent: int

@dataclass
class SpotifyState:
    """Full playback state."""
    track: SpotifyTrack | None
    device: SpotifyDevice | None
    shuffle: bool
    repeat: str  # "off", "track", "context"

class SpotifyClient:
    """Async Spotify client wrapping spotipy."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize with config.

        Args:
            config: Spotify section from config.yaml
        """
        ...

    async def initialize(self) -> None:
        """Initialize OAuth and verify connection.

        Raises:
            SpotifyAuthError: If authentication fails
        """
        ...

    async def get_playback_state(self) -> SpotifyState | None:
        """Get current playback state.

        Returns:
            SpotifyState if playing, None if no active playback
        """
        ...

    async def play(self, context_uri: str | None = None, device_id: str | None = None) -> bool:
        """Start or resume playback.

        Args:
            context_uri: Optional Spotify URI (album, playlist, artist)
            device_id: Optional device to play on

        Returns:
            True if successful
        """
        ...

    async def pause(self) -> bool:
        """Pause playback."""
        ...

    async def next_track(self) -> bool:
        """Skip to next track."""
        ...

    async def previous_track(self) -> bool:
        """Skip to previous track."""
        ...

    async def set_volume(self, volume_percent: int) -> bool:
        """Set volume.

        Args:
            volume_percent: 0-100
        """
        ...

    async def search(self, query: str, types: list[str] = ["track"]) -> list[dict]:
        """Search Spotify catalog.

        Args:
            query: Search query
            types: Types to search (track, album, artist, playlist)

        Returns:
            List of search results
        """
        ...

    async def get_devices(self) -> list[SpotifyDevice]:
        """Get available playback devices."""
        ...

    async def transfer_playback(self, device_id: str) -> bool:
        """Transfer playback to another device."""
        ...

    def is_authenticated(self) -> bool:
        """Check if client has valid auth."""
        ...


class SpotifyAuthError(Exception):
    """Raised when Spotify authentication fails."""
    pass


class SpotifyPlaybackError(Exception):
    """Raised when playback control fails (e.g., no active device)."""
    pass
```

### OAuth2 PKCE Implementation

```python
import spotipy
from spotipy.oauth2 import SpotifyPKCE
from pathlib import Path
import os

SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-library-read",
    "user-read-recently-played",
    "playlist-read-private",
]

class SpotifyClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._client: spotipy.Spotify | None = None

        # OAuth config
        self._client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self._redirect_uri = os.getenv(
            "SPOTIFY_REDIRECT_URI",
            "http://localhost:8766/callback/spotify"
        )
        self._token_cache_path = Path(
            os.getenv("SPOTIFY_TOKEN_CACHE", "~/.jarvis/spotify_token.json")
        ).expanduser()

    async def initialize(self) -> None:
        if not self._client_id:
            raise SpotifyAuthError("SPOTIFY_CLIENT_ID not set")

        # Ensure cache directory exists
        self._token_cache_path.parent.mkdir(parents=True, exist_ok=True)

        # PKCE flow - no client secret needed
        auth_manager = SpotifyPKCE(
            client_id=self._client_id,
            redirect_uri=self._redirect_uri,
            scope=" ".join(SCOPES),
            cache_path=str(self._token_cache_path),
            open_browser=False,  # We'll handle auth flow ourselves
        )

        # Check for existing token
        if not auth_manager.get_cached_token():
            # Need to authenticate - log instructions
            auth_url = auth_manager.get_authorize_url()
            logger.info(f"Spotify auth required. Visit: {auth_url}")
            raise SpotifyAuthError(
                f"Please authenticate Spotify. Visit: {auth_url}"
            )

        self._client = spotipy.Spotify(auth_manager=auth_manager)

        # Verify connection
        try:
            self._client.current_user()
        except spotipy.SpotifyException as e:
            raise SpotifyAuthError(f"Failed to verify Spotify connection: {e}")
```

### Thread Safety

Spotipy is synchronous. Wrap in `asyncio.to_thread`:

```python
async def get_playback_state(self) -> SpotifyState | None:
    if not self._client:
        return None

    try:
        playback = await asyncio.to_thread(self._client.current_playback)
        if not playback or not playback.get("item"):
            return None

        item = playback["item"]
        device = playback.get("device")

        return SpotifyState(
            track=SpotifyTrack(
                track_id=item["id"],
                name=item["name"],
                artist=", ".join(a["name"] for a in item["artists"]),
                album=item["album"]["name"],
                album_art_url=item["album"]["images"][0]["url"] if item["album"]["images"] else "",
                duration_ms=item["duration_ms"],
                progress_ms=playback.get("progress_ms", 0),
                is_playing=playback.get("is_playing", False),
            ),
            device=SpotifyDevice(
                id=device["id"],
                name=device["name"],
                type=device["type"],
                is_active=device["is_active"],
                volume_percent=device["volume_percent"],
            ) if device else None,
            shuffle=playback.get("shuffle_state", False),
            repeat=playback.get("repeat_state", "off"),
        )
    except spotipy.SpotifyException as e:
        logger.error(f"Failed to get playback state: {e}")
        return None
```

---

## Spotify Agent (`src/brain/agents/spotify_agent.py`)

### Interface

```python
from brain.agents.base import BaseAgent, AgentResult

class SpotifyAgent(BaseAgent):
    """Agent for Spotify music control."""

    def __init__(self, spotify_client: "SpotifyClient") -> None:
        super().__init__()
        self._spotify = spotify_client

    async def run(
        self,
        task: str,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult:
        """Execute Spotify command.

        Args:
            task: Full user request text
            params: Parsed parameters from intent parser
            language: Response language

        Returns:
            AgentResult with spoken response
        """
        ...
```

### Action Handlers

```python
async def _handle_play(self, params: dict, language: str) -> AgentResult:
    """Handle play/resume request."""
    query = params.get("query")

    if query:
        # Search and play
        results = await self._spotify.search(query)
        if not results:
            return self._no_results_response(query, language)

        # Play first result
        track = results[0]
        await self._spotify.play(context_uri=track["uri"])
        return AgentResult(
            spoken_response=self._format_playing(track, language),
            success=True,
        )
    else:
        # Resume playback
        await self._spotify.play()
        return AgentResult(
            spoken_response=self._resumed_response(language),
            success=True,
        )

async def _handle_pause(self, language: str) -> AgentResult:
    """Handle pause request."""
    await self._spotify.pause()
    return AgentResult(
        spoken_response="Paused." if language == "en" else "Pausiert.",
        success=True,
    )

async def _handle_next(self, language: str) -> AgentResult:
    """Handle skip request."""
    await self._spotify.next_track()
    state = await self._spotify.get_playback_state()
    if state and state.track:
        return AgentResult(
            spoken_response=self._format_now_playing(state.track, language),
            success=True,
        )
    return AgentResult(
        spoken_response="Next track." if language == "en" else "Nächster Titel.",
        success=True,
    )

async def _handle_previous(self, language: str) -> AgentResult:
    """Handle previous request."""
    await self._spotify.previous_track()
    return AgentResult(
        spoken_response="Previous track." if language == "en" else "Vorheriger Titel.",
        success=True,
    )

async def _handle_volume(self, params: dict, language: str) -> AgentResult:
    """Handle volume adjustment."""
    level = params.get("level")
    direction = params.get("direction")

    if level is not None:
        await self._spotify.set_volume(level)
        return AgentResult(
            spoken_response=f"Volume set to {level}%." if language == "en" else f"Lautstärke auf {level}%.",
            success=True,
        )
    elif direction == "up":
        state = await self._spotify.get_playback_state()
        new_vol = min(100, (state.device.volume_percent if state and state.device else 50) + 10)
        await self._spotify.set_volume(new_vol)
        return AgentResult(
            spoken_response=f"Volume up to {new_vol}%." if language == "en" else f"Lautstärke erhöht auf {new_vol}%.",
            success=True,
        )
    elif direction == "down":
        state = await self._spotify.get_playback_state()
        new_vol = max(0, (state.device.volume_percent if state and state.device else 50) - 10)
        await self._spotify.set_volume(new_vol)
        return AgentResult(
            spoken_response=f"Volume down to {new_vol}%." if language == "en" else f"Lautstärke reduziert auf {new_vol}%.",
            success=True,
        )

    return AgentResult(
        spoken_response="I didn't understand the volume command." if language == "en" else "Ich habe den Lautstärkebefehl nicht verstanden.",
        success=False,
    )
```

### Response Formatters

```python
def _format_now_playing(self, track: SpotifyTrack, language: str) -> str:
    if language == "de":
        return f"Jetzt läuft {track.name} von {track.artist}."
    return f"Now playing {track.name} by {track.artist}."

def _format_playing(self, track: dict, language: str) -> str:
    name = track["name"]
    artist = track["artists"][0]["name"]
    if language == "de":
        return f"Spiele {name} von {artist}."
    return f"Playing {name} by {artist}."

def _resumed_response(self, language: str) -> str:
    if language == "de":
        return "Wiedergabe fortgesetzt."
    return "Resuming playback."

def _no_results_response(self, query: str, language: str) -> str:
    if language == "de":
        return f"Ich konnte nichts für '{query}' finden."
    return f"I couldn't find anything for '{query}'."
```

---

## Intent Parser Updates

Add to `src/brain/intent_parser.py`:

```python
class Intent(Enum):
    # ... existing intents ...
    SPOTIFY = "spotify"

INTENT_KEYWORDS: dict[Intent, dict[str, list[str]]] = {
    # ... existing patterns ...
    Intent.SPOTIFY: {
        "en": [
            r"\bplay\s+(some\s+)?music\b",
            r"\bplay\s+(the\s+)?(song|track|album|artist|playlist)\b",
            r"\bpause\s+(the\s+)?music\b",
            r"\bstop\s+(the\s+)?music\b",
            r"\bskip\s+(this\s+)?(song|track)\b",
            r"\bnext\s+(song|track)\b",
            r"\bprevious\s+(song|track)\b",
            r"\bwhat('s|\s+is)\s+playing\b",
            r"\bcurrent\s+(song|track)\b",
            r"\bspotify\b",
            r"\bmusic\s+volume\b",
        ],
        "de": [
            r"\bspiel(e)?\s+(etwas\s+)?musik\b",
            r"\bspiel(e)?\s+(das\s+)?(lied|song|album|künstler|playlist)\b",
            r"\bmusik\s+(an)?halten\b",
            r"\bpausiere?\s+(die\s+)?musik\b",
            r"\bstopp(e)?\s+(die\s+)?musik\b",
            r"\büberspringen?\b",
            r"\bnächstes?\s+(lied|song)\b",
            r"\bvorheriges?\s+(lied|song)\b",
            r"\bwas\s+(läuft|spielt)\b",
            r"\baktuelles?\s+(lied|song)\b",
            r"\bspotify\b",
            r"\bmusik\s+lautstärke\b",
        ],
    },
}
```

### Parameter Extraction

```python
def _extract_spotify_params(self, text: str) -> dict[str, Any]:
    """Extract Spotify command parameters.

    Args:
        text: Lowercase user input

    Returns:
        Extracted parameters
    """
    params: dict[str, Any] = {"action": "unknown"}

    # Play commands
    if re.search(r"\b(play|spiel)\b", text):
        params["action"] = "play"
        # Extract what to play
        match = re.search(r"(?:play|spiele?)\s+(.+?)(?:\s+on|\s+by|$)", text)
        if match:
            query = match.group(1).strip()
            # Remove common filler words
            query = re.sub(r"^(some|the|das|die|der|etwas)\s+", "", query)
            if query and query not in ["music", "musik"]:
                params["query"] = query

    # Pause/stop
    elif re.search(r"\b(pause|stop|stopp|anhalten)\b", text):
        params["action"] = "pause"

    # Next/skip
    elif re.search(r"\b(next|skip|nächst|überspringen)\b", text):
        params["action"] = "next"

    # Previous
    elif re.search(r"\b(previous|vorherig|zurück)\b", text):
        params["action"] = "previous"

    # Volume
    elif re.search(r"\b(volume|lautstärke)\b", text):
        params["action"] = "volume"
        match = re.search(r"(\d+)\s*(%|percent|prozent)?", text)
        if match:
            params["level"] = int(match.group(1))
        elif re.search(r"\b(up|höher|lauter)\b", text):
            params["direction"] = "up"
        elif re.search(r"\b(down|niedriger|leiser)\b", text):
            params["direction"] = "down"

    # What's playing
    elif re.search(r"\b(what.*playing|was.*läuft|was.*spielt|current|aktuell)\b", text):
        params["action"] = "status"

    return params
```

---

## State Broadcast Loop

Add to `src/api/ws_server.py`:

```python
# Global
_spotify_client: SpotifyClient | None = None

async def _spotify_state_loop() -> None:
    """Background task to broadcast Spotify state."""
    global _spotify_client

    if not _spotify_client:
        return

    poll_interval = 5  # seconds, from config

    while True:
        try:
            state = await _spotify_client.get_playback_state()
            if state and state.track:
                payload = {
                    "playing": state.track.is_playing,
                    "track": state.track.name,
                    "artist": state.track.artist,
                    "album": state.track.album,
                    "album_art_url": state.track.album_art_url,
                    "progress_ms": state.track.progress_ms,
                    "duration_ms": state.track.duration_ms,
                    "device": state.device.name if state.device else "Unknown",
                }
                await _broadcast(json.dumps({
                    "type": "spotify_state",
                    "payload": payload,
                }))
        except Exception as e:
            logger.error(f"Error polling Spotify state: {e}")

        await asyncio.sleep(poll_interval)
```

---

## NowPlayingPanel (`frontend/src/components/panels/NowPlayingPanel.tsx`)

```typescript
import { useState, useEffect } from 'react';
import { PanelBase } from './PanelBase';
import { useSpotify } from '../../hooks/useSpotify';

export function NowPlayingPanel() {
  const { state, loading, error, sendCommand } = useSpotify();

  if (!state || !state.track) {
    return (
      <PanelBase title="NOW PLAYING" loading={loading} error={error}>
        <div style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
          No active playback
        </div>
      </PanelBase>
    );
  }

  const { track, artist, album, album_art_url, playing, progress_ms, duration_ms } = state;
  const progress = duration_ms > 0 ? (progress_ms / duration_ms) * 100 : 0;

  return (
    <PanelBase
      title="NOW PLAYING"
      icon={<MusicIcon />}
    >
      {/* Album art */}
      {album_art_url && (
        <img
          src={album_art_url}
          alt={album}
          style={{
            width: '100%',
            aspectRatio: '1',
            objectFit: 'cover',
            borderRadius: '2px',
            marginBottom: '12px',
          }}
        />
      )}

      {/* Track info */}
      <div style={{ marginBottom: '12px' }}>
        <div
          style={{
            fontSize: '14px',
            fontWeight: 500,
            color: 'var(--text)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {track}
        </div>
        <div
          style={{
            fontSize: '12px',
            color: 'var(--text-secondary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {artist}
        </div>
      </div>

      {/* Progress bar */}
      <div
        style={{
          height: '4px',
          background: 'var(--panel-border)',
          borderRadius: '2px',
          marginBottom: '12px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${progress}%`,
            height: '100%',
            background: 'var(--accent)',
            transition: 'width 1s linear',
          }}
        />
      </div>

      {/* Controls */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        <ControlButton onClick={() => sendCommand('prev')} icon={<PrevIcon />} />
        <ControlButton
          onClick={() => sendCommand(playing ? 'pause' : 'play')}
          icon={playing ? <PauseIcon /> : <PlayIcon />}
          primary
        />
        <ControlButton onClick={() => sendCommand('next')} icon={<NextIcon />} />
      </div>
    </PanelBase>
  );
}

interface ControlButtonProps {
  onClick: () => void;
  icon: React.ReactNode;
  primary?: boolean;
}

function ControlButton({ onClick, icon, primary }: ControlButtonProps) {
  return (
    <button
      onClick={onClick}
      style={{
        width: primary ? 40 : 32,
        height: primary ? 40 : 32,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: primary ? 'var(--accent)' : 'transparent',
        border: primary ? 'none' : '1px solid var(--panel-border)',
        borderRadius: '4px',
        color: primary ? 'var(--bg)' : 'var(--text)',
        cursor: 'pointer',
        transition: 'all 150ms',
      }}
    >
      {icon}
    </button>
  );
}

// SVG icons (simplified)
function MusicIcon() { return <svg>...</svg>; }
function PlayIcon() { return <svg>...</svg>; }
function PauseIcon() { return <svg>...</svg>; }
function NextIcon() { return <svg>...</svg>; }
function PrevIcon() { return <svg>...</svg>; }

export default NowPlayingPanel;
```

---

## useSpotify Hook (`frontend/src/hooks/useSpotify.ts`)

```typescript
import { useState, useEffect, useCallback } from 'react';
import { SpotifyState } from '../types';

interface UseSpotifyResult {
  state: SpotifyState | null;
  loading: boolean;
  error: string | null;
  sendCommand: (action: 'play' | 'pause' | 'next' | 'prev' | 'volume', value?: number) => void;
}

export function useSpotify(wsRef: React.RefObject<WebSocket | null>): UseSpotifyResult {
  const [state, setState] = useState<SpotifyState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ws = wsRef.current;
    if (!ws) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'spotify_state') {
          setState(msg.payload);
          setLoading(false);
          setError(null);
        }
      } catch {
        // Ignore binary messages
      }
    };

    ws.addEventListener('message', handleMessage);
    return () => ws.removeEventListener('message', handleMessage);
  }, [wsRef]);

  const sendCommand = useCallback(
    (action: 'play' | 'pause' | 'next' | 'prev' | 'volume', value?: number) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      ws.send(JSON.stringify({
        type: 'spotify_cmd',
        payload: { action, value },
      }));
    },
    [wsRef]
  );

  return { state, loading, error, sendCommand };
}
```

---

## Configuration

### config.yaml

```yaml
spotify:
  enabled: false              # Enable after OAuth setup
  poll_interval_seconds: 5    # How often to fetch playback state
  show_album_art: true        # Display album art in panel
```

### .env.example

```bash
# Spotify OAuth2 (PKCE - no client secret needed)
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_REDIRECT_URI=http://localhost:8766/callback/spotify
# Token cache (default: ~/.jarvis/spotify_token.json)
# SPOTIFY_TOKEN_CACHE=~/.jarvis/spotify_token.json
```

---

## OAuth Callback Handler

Add callback endpoint to `src/api/ws_server.py`:

```python
async def spotify_callback_handler(request: web.Request) -> web.Response:
    """Handle Spotify OAuth callback.

    Args:
        request: aiohttp request with authorization code

    Returns:
        Success page or error
    """
    code = request.query.get("code")
    if not code:
        return web.Response(text="Authorization failed", status=400)

    # The SpotifyClient's auth manager handles the code exchange
    # Redirect user to confirmation page
    return web.Response(
        text="Spotify connected! You can close this window.",
        content_type="text/html",
    )
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | SpotifyClient initializes with valid OAuth token | Unit test with mocked spotipy |
| 2 | "Play some jazz" triggers search and playback | Integration test |
| 3 | "Pause the music" pauses playback | Integration test |
| 4 | "Skip this song" advances to next track | Integration test |
| 5 | "What's playing" returns current track info | Integration test |
| 6 | NowPlayingPanel displays track, artist, album art | Visual inspection |
| 7 | Play/pause button toggles correctly | Visual inspection |
| 8 | Progress bar updates every poll interval | Visual inspection |
| 9 | German voice commands work ("Spiele Musik") | Integration test |
| 10 | spotify_state WS message broadcasts every 5s | Unit test |
| 11 | No crash when Spotify not authenticated | Integration test |
| 12 | Graceful handling when no active device | Integration test |
| 13 | OAuth PKCE flow completes successfully | Manual test |
| 14 | Token refresh works automatically | Integration test with mocked expired token |

---

## Files Created

| File | Purpose |
|------|---------|
| `src/integrations/spotify/__init__.py` | Package init |
| `src/integrations/spotify/client.py` | SpotifyClient |
| `src/brain/agents/spotify_agent.py` | SpotifyAgent |
| `frontend/src/components/panels/NowPlayingPanel.tsx` | Panel component |
| `frontend/src/hooks/useSpotify.ts` | Spotify state hook |
| `tests/integrations/spotify/test_client.py` | Client tests |
| `tests/brain/agents/test_spotify_agent.py` | Agent tests |

## Files Modified

| File | Change |
|------|--------|
| `src/brain/intent_parser.py` | Add SPOTIFY intent + keywords |
| `src/brain/orchestrator.py` | Register SpotifyAgent |
| `src/api/ws_server.py` | Add spotify_state_loop, spotify_cmd handler, callback endpoint |
| `src/main.py` | Initialize SpotifyClient |
| `config/config.yaml` | Add spotify section |
| `.env.example` | Add Spotify credentials |
| `requirements.txt` | Add spotipy |

---

## Dependencies

### pip packages
```
spotipy>=2.23.0
```

### External
- Spotify Developer App (user creates)
- Spotify Premium account (for playback control)

---

## Implementation Plan

### Batch 1 — Backend client
1. `code` → Create `src/integrations/spotify/__init__.py`
2. `code` → Create `src/integrations/spotify/client.py` with SpotifyClient
3. `test` → Create `tests/integrations/spotify/test_client.py`
4. `review` → Review batch 1

### Batch 2 — Agent and intents
5. `code` → Update `src/brain/intent_parser.py` with SPOTIFY intent
6. `code` → Create `src/brain/agents/spotify_agent.py`
7. `code` → Update `src/brain/orchestrator.py` to register SpotifyAgent
8. `test` → Create `tests/brain/agents/test_spotify_agent.py`
9. `review` → Review batch 2

### Batch 3 — WS integration
10. `code` → Update `src/api/ws_server.py` with state loop and command handler
11. `code` → Update `src/main.py` to initialize SpotifyClient
12. `code` → Add callback endpoint for OAuth
13. `test` → Integration tests for WS messages
14. `review` → Review batch 3

### Batch 4 — Frontend
15. `design` → Create `frontend/src/hooks/useSpotify.ts`
16. `design` → Create `frontend/src/components/panels/NowPlayingPanel.tsx`
17. `test` → Frontend tests
18. `review` → Final review

---

## Open Questions — Partially Resolved

1. **Spotify Premium:** ✓ RESOLVED — User has Spotify Premium. Full playback controls enabled.

2. **Default device:** Still open — If multiple devices available, which should be default? First active? Or should JARVIS ask?

3. **Search specificity:** Still open — Should "play jazz" search for genre/mood, or try to find artist/album named "jazz"?

---

**Status:** Planned — awaiting implementation authorization

---

## Revision 3 — Full OpenClaw Adoption (2026-04-16)

### Decisions Applied
1. **OpenClaw as full backbone** — Spotify control via OpenClaw
2. **State polling remains JARVIS-native** — HUD requires real-time playback state

### Integration Assessment
**OpenClaw PARTIALLY replaces this spec — control via OpenClaw, state polling native.**

### OpenClaw Coverage
| Feature | OpenClaw Capability | Coverage |
|---------|---------------------|----------|
| Play/pause/skip | Spotify skill | Full |
| Search and play | Spotify skill | Full |
| Volume control | Spotify skill | Full |
| Current playback state | Not exposed for polling | None |
| Device selection | TBD (verify) | Unknown |
| OAuth/auth | OpenClaw handles | Full |

### What JARVIS-Native Retains
1. **SpotifyClient (state polling only)** — HUD needs real-time playback state
2. **NowPlayingPanel** — HUD visualization with album art, progress bar
3. **State polling loop** — 5-second interval for playback state
4. **Voice UX** — "Now playing X by Y" spoken responses
5. **Panel controls** — Play/pause/next buttons (send to OpenClaw)

### What Is REMOVED (This Spec)
- ~~SpotifyAgent~~ — REMOVED (commands go to OpenClaw)
- ~~Playback control implementation~~ — REMOVED (OpenClaw handles)
- ~~OAuth PKCE implementation~~ — REMOVED (OpenClaw handles auth)

### Two-Layer Architecture
```
Layer 1 (OpenClaw): Playback control commands
  Voice: "Play jazz music"
         ↓
  [Orchestrator] → Forward to OpenClaw
         ↓
  [OpenClaw Spotify skill] → Playback starts

Layer 2 (JARVIS): State observation for HUD
  [SpotifyClient] → Poll spotipy.current_playback()
         ↓
  [WS broadcast] → spotify_state message
         ↓
  [NowPlayingPanel] → Displays track, artist, album art
```

### Files Created — REDUCED
| File | Purpose | Status |
|------|---------|--------|
| `src/integrations/spotify/__init__.py` | Package init | KEEP |
| `src/integrations/spotify/client.py` | SpotifyClient (polling only) | KEEP (simplified) |
| `src/brain/agents/spotify_agent.py` | SpotifyAgent | SKIP (OpenClaw) |
| `frontend/src/components/panels/NowPlayingPanel.tsx` | Panel component | KEEP |
| `frontend/src/hooks/useSpotify.ts` | Spotify state hook | KEEP |

### Files Modified — REDUCED
| File | Change | Status |
|------|--------|--------|
| `src/brain/intent_parser.py` | Add SPOTIFY intent | KEEP |
| `src/brain/orchestrator.py` | Route to OpenClaw | MODIFIED |
| `src/api/ws_server.py` | spotify_state_loop (read-only) | SIMPLIFIED |
| `config/config.yaml` | Spotify section | SIMPLIFIED |

### Config — Simplified
```yaml
spotify:
  enabled: true
  control_provider: "openclaw"
  state_polling: true
  poll_interval_seconds: 5
  show_album_art: true
```

### Implementation Reduction
**Original estimate:** 8-10 hours
**With OpenClaw:** 4-5 hours (state polling + HUD only)
**Reduction:** ~50%

### Prerequisites
- `openclaw-integration.md` — REQUIRED
- OpenClaw Spotify skill enabled in workspace

### Open Questions — Updated
1. **Device selection:** If OpenClaw Spotify skill doesn't support device selection, JARVIS can add thin wrapper — verify during implementation.
