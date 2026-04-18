# Feature: Spotify Integration

## Status
Planned — awaiting implementation authorization

### What exists today (2026-04-18)
- `SPOTIFY_CLIENT_ID` populated in `.env`
- `frontend/src/components/panels/NowPlayingPanel.tsx` — fully built UI (compact + expanded modes, transport buttons, progress bar) consuming `NowPlayingTrack` from mock data
- `frontend/src/mock/nowPlayingMock.ts` — static mock track in use
- `NowPlayingTrack` type defined in `frontend/src/types.ts`
- Redirect URI `http://127.0.0.1:8766/oauth/spotify/callback` must be registered in Spotify Developer Dashboard (user action required before first run)

### What is NOT yet built
- `src/integrations/spotify/` package
- OAuth PKCE callback endpoint on the aiohttp HTTP server (:8766)
- Spotify state polling loop + WS broadcast
- `spotify_state` / `spotify_cmd` WS message types
- `useSpotify` hook wiring `NowPlayingPanel` to live WS data
- Voice command routing (intent + `src/brain/orchestrator.py` hookup)
- Config yaml section, `.env.example` additions, `requirements.txt` entry

---

## Goal
Enable JARVIS to display live Spotify playback state in the NowPlayingPanel and accept voice commands (play, pause, skip, volume, "what's playing") routed through the existing OpenClaw conversational path. The integration is intentionally split: OpenClaw handles all playback-control commands; JARVIS-native code handles OAuth token storage, state polling, and HUD data delivery.

## Scope

### In scope
- OAuth 2.0 PKCE flow: `SPOTIFY_CLIENT_ID` from `.env`, no client secret, token cached at `~/.jarvis/spotify_token.json`
- aiohttp HTTP callback handler at `GET /oauth/spotify/callback` on port 8766
- `SpotifyClient` (read-only polling): `get_playback_state()`, `is_authenticated()`, wrapping spotipy in `asyncio.to_thread`
- Background polling loop at configurable interval (default 5 s), broadcasting `spotify_state` WS frames to all connected clients
- `useSpotify` hook consuming `spotify_state` frames and sending `spotify_cmd` frames via the existing `wsRef` from `useWebSocket`
- Wire `NowPlayingPanel` to live data from `useSpotify` (replace `nowPlayingMock` default prop)
- Voice intent detection added to `src/brain/intent_parser.py` (`Intent.SPOTIFY`)
- Orchestrator routes `Intent.SPOTIFY` to the OpenClaw conversational path (already the fallthrough for non-local intents); spoken confirmation TTS via existing pipeline
- Unit tests for `SpotifyClient` (mocked spotipy) and `useSpotify` hook (mocked WS)

### Out of scope
- JARVIS-native playback control (play/pause/skip implementation) — OpenClaw Spotify skill handles this
- Device-selection UI — deferred
- Playlist browsing UI
- Album-art proxy / caching — panel loads `album_art_url` directly from Spotify CDN
- Podcast-specific controls
- Lyrics display
- Any WS `spotify_cmd` server-side handler beyond logging the receipt (control goes through voice → OpenClaw, not through panel button → backend → Spotify API directly in this iteration)

---

## User Flow

1. On first run, `SpotifyClient.initialize()` finds no cached token, generates the PKCE auth URL, and logs it. JARVIS broadcasts a `notification` WS frame instructing the user to visit the URL.
2. User visits the URL in a browser, grants permission, and is redirected to `http://127.0.0.1:8766/oauth/spotify/callback?code=…`.
3. The aiohttp callback handler exchanges the code via spotipy's `SpotifyPKCE.get_access_token()`, writes the token to `~/.jarvis/spotify_token.json`, and returns a plain HTML confirmation page.
4. `SpotifyClient` detects the now-valid token on the next polling tick, begins polling, and starts broadcasting `spotify_state` frames every 5 s.
5. `NowPlayingPanel` transitions from showing the mock track to showing live Spotify data.
6. User says "Hey JARVIS, skip this song." Orchestrator classifies `Intent.SPOTIFY` and routes to the OpenClaw conversational path; OpenClaw's Spotify skill handles the skip; on the next poll the updated state appears in the HUD.
7. Spotify playback is paused or closed: next poll returns `None`, a `spotify_state` frame with `playing: false` and empty track fields is broadcast, panel shows "No active playback."

---

## Architecture

### Modules touched

- **Backend — new:**
  - `src/integrations/spotify/__init__.py`
  - `src/integrations/spotify/client.py`
- **Backend — modified:**
  - `src/api/ws_server.py` — add `spotify_state_loop` background task, `spotify_cmd` incoming handler, OAuth callback route, `SpotifyClient` global
  - `src/brain/intent_parser.py` — add `Intent.SPOTIFY` enum value and keyword patterns
  - `src/brain/orchestrator.py` — no structural change; `Intent.SPOTIFY` is already not in `_LOCAL_INTENTS`, so it falls through to `ChatAgent` / OpenClaw automatically. One guard: if Spotify is not authenticated, intercept and return a spoken auth-prompt instead of routing to OpenClaw.
  - `src/main.py` — initialise `SpotifyClient`, pass to `start_ws_server`
  - `config/config.yaml` — add `spotify:` section
  - `.env.example` — add `SPOTIFY_CLIENT_ID`, `SPOTIFY_REDIRECT_URI`, token cache override comment
  - `requirements.txt` — add `spotipy`
- **Frontend — new:**
  - `frontend/src/hooks/useSpotify.ts`
- **Frontend — modified:**
  - `frontend/src/components/panels/NowPlayingPanel.tsx` — accept optional `liveTrack` prop from `useSpotify`; fall back to mock only when hook returns `null` (dev mode)
  - `frontend/src/types.ts` — extend `WsIncoming` union with `spotify_state`; add `WsOutgoing` variant `spotify_cmd`
- **Config keys added to `config/config.yaml`:**
  ```
  spotify.enabled
  spotify.poll_interval_seconds
  spotify.show_album_art
  ```
- **Env vars (`.env` / `.env.example`):**
  ```
  SPOTIFY_CLIENT_ID          # already populated
  SPOTIFY_REDIRECT_URI       # default: http://127.0.0.1:8766/oauth/spotify/callback
  SPOTIFY_TOKEN_CACHE        # optional override; default: ~/.jarvis/spotify_token.json
  ```

### Data flow

```
[Spotify API]
      |
      | spotipy.current_playback() — asyncio.to_thread
      v
[SpotifyClient.get_playback_state()]  (5 s poll)
      |
      v
[_spotify_state_loop() in ws_server.py]
      |  _broadcast(json) — existing _broadcast helper
      v
[WS frame: {"type":"spotify_state", "payload": SpotifyStatePayload}]
      |
      v
[useWebSocket (existing) — receives message]
      |
      v
[useSpotify hook — subscribes via wsRef message listener]
      |
      v
[NowPlayingPanel — re-renders with live NowPlayingTrack]


Voice control path:
[Wake word] → [STT] → [IntentParser: Intent.SPOTIFY]
      |
      v (not in _LOCAL_INTENTS → falls to ChatAgent)
[OpenClaw conversational path via ws_client.py]
      |
      v
[OpenClaw Spotify skill — executes play/pause/skip/volume]
      |
      v (next 5 s poll picks up new state)
[NowPlayingPanel updates]


Panel button path (Phase 1 scope):
[TransportButton click] → [useSpotify.sendCommand()]
      |
      v
[WS frame: {"type":"spotify_cmd", "payload": {action, value}}]
      |
      v
[ws_server spotify_cmd handler — logs receipt, no direct Spotify API call]
      NOTE: Panel buttons are wired for future use. In this iteration
      they send a WS frame but the backend does not act on it beyond
      logging. Voice is the authoritative control path.


OAuth path:
[SpotifyClient.initialize() — no cached token]
      |
      v
[PKCE auth URL generated → broadcast notification WS frame with URL]
      |
      v (user opens browser)
[GET /oauth/spotify/callback?code=… on :8766]
      |
      v
[aiohttp handler: SpotifyPKCE.get_access_token(code)]
      |
      v
[Token written to ~/.jarvis/spotify_token.json]
      |
      v
[HTML confirmation page returned to browser]
```

### Interfaces

**Python — `src/integrations/spotify/client.py`:**

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class SpotifyTrackInfo:
    track_id: str
    name: str
    artist: str
    album: str
    album_art_url: str
    duration_ms: int
    progress_ms: int
    is_playing: bool
    shuffle: bool
    repeat: str        # "off" | "track" | "context"
    device_name: str

class SpotifyAuthError(Exception): ...
class SpotifyPollError(Exception): ...

class SpotifyClient:
    def __init__(self, config: dict[str, Any]) -> None: ...
    async def initialize(self) -> None: ...
    async def get_playback_state(self) -> SpotifyTrackInfo | None: ...
    def is_authenticated(self) -> bool: ...
    def get_auth_url(self) -> str: ...
    async def complete_auth(self, code: str) -> None: ...
```

**Python — `src/api/ws_server.py` additions:**

```python
async def spotify_oauth_callback_handler(request: web.Request) -> web.Response: ...
# Registered as: http_app.router.add_get("/oauth/spotify/callback", spotify_oauth_callback_handler)

async def _spotify_state_loop(client: SpotifyClient, interval_seconds: int) -> None: ...
# Started as asyncio.create_task in start_ws_server after SpotifyClient.initialize() succeeds
```

**WebSocket messages — new variants:**

`WsIncoming` additions (server → client):
```typescript
// Broadcast every poll_interval_seconds.
// payload mirrors NowPlayingTrack with an extra `authenticated` flag.
| {
    type: 'spotify_state';
    payload: {
      authenticated: boolean;
      playing: boolean;
      title: string;
      artist: string;
      album: string;
      album_art_url: string;   // empty string when no art
      progress_ms: number;
      duration_ms: number;
      shuffle: boolean;
      repeat: 'off' | 'all' | 'one';
      device: string;
    };
  }
```

`WsOutgoing` additions (client → server):
```typescript
| {
    type: 'spotify_cmd';
    payload: {
      action: 'play' | 'pause' | 'next' | 'prev' | 'volume';
      value?: number;   // volume level 0-100
    };
  }
```

**REST endpoints — new:**
```
GET /oauth/spotify/callback
  Query params: code (string), state (string, ignored)
  On success: 200 text/html — "Spotify connected. You can close this window."
  On missing code: 400 text/html — "Authorization failed."
```

**Frontend — `frontend/src/hooks/useSpotify.ts`:**
```typescript
export interface UseSpotifyResult {
  track: NowPlayingTrack | null;
  authenticated: boolean;
  sendCommand: (action: 'play' | 'pause' | 'next' | 'prev' | 'volume', value?: number) => void;
}

export function useSpotify(
  wsRef: React.RefObject<WebSocket | null>
): UseSpotifyResult
```

### External dependencies

- `spotipy>=2.23.0` (pip) — OAuth PKCE + playback state polling
- Spotify Developer App with redirect URI registered (user setup, documented in Manual Verification)
- Spotify Premium account (required for active-device state; confirmed)

---

## Edge Cases & Failure Modes

- **No cached token on startup** → `initialize()` raises `SpotifyAuthError`, `_spotify_state_loop` is not started. Backend logs auth URL, broadcasts `notification` frame with URL to frontend. Polling resumes after `complete_auth()` succeeds (triggered by OAuth callback).
- **Token expired between polls** → spotipy's `SpotifyPKCE` auto-refreshes silently. If refresh fails (revoked app access), `get_playback_state()` raises `spotipy.SpotifyException`; caught, logged, broadcast `spotify_state` with `authenticated: false`.
- **No active Spotify device** → `current_playback()` returns `None`. Broadcast `spotify_state` with `playing: false`, empty title/artist/album. Panel shows "No active playback." No error surfaced.
- **Spotify app not running / no Premium** → Same as above — no active device.
- **`SPOTIFY_CLIENT_ID` missing from `.env`** → `initialize()` raises immediately with a clear message; backend logs warning and skips Spotify entirely (`spotify.enabled` remains irrelevant).
- **OAuth callback received but `SpotifyClient` not initialised** → Handler returns 503 with message "Spotify client not ready."
- **OAuth callback code already consumed (double-redirect)** → spotipy raises on `get_access_token`; handler returns 400 "Authorization code expired or already used."
- **Poll interval network error (Spotify API rate limit / 5xx)** → `SpotifyPollError` caught in loop, one warning log, sleep for `poll_interval_seconds`, retry. No WS broadcast on error (stale data remains on frontend; no confusing empty-state flash).
- **Frontend receives `spotify_state` while WS reconnecting** → hook initialises `track` as `null`; panel shows mock data (dev fallback) until first live frame arrives.
- **Panel transport button pressed when WS disconnected** → `sendCommand` no-ops (checks `ws.readyState !== WebSocket.OPEN`).
- **`~/.jarvis/` directory does not exist** → `initialize()` calls `token_cache_path.parent.mkdir(parents=True, exist_ok=True)` before constructing `SpotifyPKCE`.
- **RPi 4 / low-memory target** → spotipy call is wrapped in `asyncio.to_thread`; no blocking of the asyncio event loop. Poll interval default of 5 s is conservative enough for RPi.
- **`spotify.enabled: false` in config** → `SpotifyClient` is not instantiated; `_spotify_state_loop` is not started; routes and WS handlers are still registered (no-op responses). This allows the server to boot without credentials.

---

## Acceptance Criteria

1. When `SPOTIFY_CLIENT_ID` is set and a valid token exists in `~/.jarvis/spotify_token.json`, `SpotifyClient.initialize()` completes without raising.
2. When no token exists, `SpotifyClient.initialize()` raises `SpotifyAuthError` and `get_auth_url()` returns a non-empty PKCE URL.
3. `GET /oauth/spotify/callback?code=<valid_code>` returns HTTP 200 with an HTML body containing "Spotify connected".
4. `GET /oauth/spotify/callback` with no `code` parameter returns HTTP 400.
5. `SpotifyClient.get_playback_state()` returns a `SpotifyTrackInfo` dataclass when a track is playing, and `None` when no active playback.
6. `SpotifyClient.get_playback_state()` does not block the asyncio event loop (wraps spotipy in `asyncio.to_thread`).
7. The backend broadcasts a `{"type":"spotify_state"}` WS frame at each poll interval when authenticated; the payload matches the `SpotifyStatePayload` schema.
8. When Spotify is not authenticated, a `{"type":"spotify_state", "payload": {"authenticated": false}}` frame is broadcast (no track data sent).
9. `useSpotify` hook returns `track: null` initially, then a populated `NowPlayingTrack` after the first `spotify_state` frame arrives.
10. `NowPlayingPanel` renders live `title`, `artist`, `album`, `progressMs`, `durationMs`, and `playing` fields from the `useSpotify` hook.
11. `NowPlayingPanel` renders the fallback state ("No active playback" or equivalent) when `useSpotify` returns `track: null`.
12. Voice utterance "Pause the music" is classified as `Intent.SPOTIFY` by `IntentParser` in both `en` and `de` variants.
13. `Intent.SPOTIFY` is absent from `_LOCAL_INTENTS` in `orchestrator.py`, confirming it falls through to the OpenClaw path.
14. The backend boots cleanly when `spotify.enabled: false` in `config.yaml` and `SPOTIFY_CLIENT_ID` is absent from `.env`.
15. All new Python modules pass `pytest` with external spotipy calls mocked via `unittest.mock.patch`.

---

## Implementation Plan

Steps 1–6 are parallelisable (backend and frontend can proceed independently). Steps 7–9 are sequential and depend on both tracks completing.

1. `backend-dev` → create `src/integrations/spotify/__init__.py` (empty package init) and `src/integrations/spotify/client.py` implementing `SpotifyClient`, `SpotifyTrackInfo`, `SpotifyAuthError`, `SpotifyPollError` per the interfaces above. Use `asyncio.to_thread` for all spotipy calls. Token cache path: `Path(os.getenv("SPOTIFY_TOKEN_CACHE", "~/.jarvis/spotify_token.json")).expanduser()`. Redirect URI: `os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8766/oauth/spotify/callback")`.
2. `backend-dev` → add `Intent.SPOTIFY` to `src/brain/intent_parser.py`: enum value, `en` + `de` keyword patterns covering play/pause/skip/volume/status utterances.
3. `backend-dev` → add to `src/api/ws_server.py`: (a) `_spotify_client: SpotifyClient | None` global, (b) `spotify_oauth_callback_handler` aiohttp handler registered as `http_app.router.add_get("/oauth/spotify/callback", ...)`, (c) `_spotify_state_loop` background task, (d) incoming `spotify_cmd` frame handler (log-only in Phase 1), (e) wire startup in `start_ws_server`: construct `SpotifyClient` when `spotify.enabled`, call `initialize()` in try/except (log + notify on auth failure), launch `_spotify_state_loop` task.
4. `backend-dev` → update `src/main.py` to pass spotify config into `start_ws_server` (if not already forwarded via the config dict) and add `spotipy>=2.23.0` to `requirements.txt`. Add `spotify:` block to `config/config.yaml` and Spotify vars to `.env.example`.
5. `frontend-dev` → extend `frontend/src/types.ts`: add `spotify_state` to `WsIncoming` union; add `spotify_cmd` to `WsOutgoing` union.
6. `frontend-dev` → create `frontend/src/hooks/useSpotify.ts` implementing `UseSpotifyResult`, subscribing to `spotify_state` frames via `wsRef`, and exposing `sendCommand`.
7. `frontend-dev` → update `frontend/src/components/panels/NowPlayingPanel.tsx`: import `useSpotify`, call it with `wsRef` (prop-drilled or via context — see Open Questions), map `SpotifyStatePayload` fields to `NowPlayingTrack`, replace the `nowPlayingMock` default prop fallback with live data. Add "No active playback" empty state. Wire `TransportButton` `onClick` handlers to `useSpotify.sendCommand`.
8. `tester` → write `tests/integrations/spotify/test_client.py`: unit tests for `initialize()` with valid cached token (mock `SpotifyPKCE`), `initialize()` with no token (assert `SpotifyAuthError`), `get_playback_state()` with playback active (assert `SpotifyTrackInfo` fields), `get_playback_state()` with `None` API response, `complete_auth()` happy path, network error in `get_playback_state()` (assert `None` return). Mock all spotipy calls.
9. `tester` → write `tests/api/test_spotify_ws.py`: test that `_spotify_state_loop` broadcasts correctly shaped `spotify_state` frames; test OAuth callback handler for 200/400 paths; test `spotify_cmd` incoming handler logs receipt without raising.
10. `tester` → write `frontend/src/hooks/__tests__/useSpotify.test.ts` (Vitest + RTL): mock WS message dispatch, assert `track` transitions from `null` to populated `NowPlayingTrack`, assert `sendCommand` sends correct `spotify_cmd` frame, assert unauthenticated `spotify_state` leaves `track: null`.
11. `reviewer` → review entire batch against this spec, checking: aiohttp-only (no FastAPI), no blocking calls in event loop, `asyncio.to_thread` present, token cache path expansion, `_LOCAL_INTENTS` unchanged, `WsIncoming`/`WsOutgoing` types consistent, panel fallback state present.

---

## Manual Verification

```bash
# 1. Register redirect URI in Spotify Developer Dashboard
#    https://developer.spotify.com/dashboard → your app → Edit Settings
#    Add: http://127.0.0.1:8766/oauth/spotify/callback

# 2. Ensure .env has SPOTIFY_CLIENT_ID populated
grep SPOTIFY_CLIENT_ID .env

# 3. Start backend
PYTHONPATH=src .venv/bin/python -m main

# 4. Watch for the auth URL in logs (first run, no token cache)
#    Expected log line:
#    "Spotify auth required. Visit: https://accounts.spotify.com/authorize?..."

# 5. Visit the URL in a browser, authenticate, watch for the callback:
#    Browser should show: "Spotify connected. You can close this window."
#    Backend log: "Spotify OAuth complete — token cached at ~/.jarvis/spotify_token.json"

# 6. Start a track in any Spotify client (desktop/mobile/web)
#    Within 5 s, check the NowPlayingPanel in the HUD (http://localhost:5173)
#    Expected: live track title, artist, album monogram, progress bar moving

# 7. Voice test: say "Hey JARVIS, pause the music"
#    Expected: OpenClaw Spotify skill pauses; next poll → NowPlayingPanel shows pause icon

# 8. Voice test (German): "JARVIS, nächster Titel"
#    Expected: skip occurs; HUD updates within 5 s

# 9. Close Spotify entirely, wait one poll interval
#    Expected: NowPlayingPanel shows "No active playback" or empty-state UI

# 10. Confirm no blocking: during a poll, the WS audio pipeline must remain responsive
#     (send a voice command mid-poll — it should not stall)
```

---

## Open Questions

1. **`wsRef` access in `NowPlayingPanel`**: `useWebSocket` exposes `wsRef` at the App level. The panel needs it to call `useSpotify`. Options: (a) prop-drill `wsRef` from App → panel container → `NowPlayingPanel`, (b) expose a `subscribeSpotify` callback from `useWebSocket` similar to existing `subscribeSystem`/`subscribeNotifications`, (c) React context. Recommend option (b) — it is consistent with the existing subscription pattern and avoids new context boilerplate. Dev agent should confirm with the orchestrator before implementing.

2. **Phase 1 panel buttons — backend no-op**: Transport buttons send `spotify_cmd` frames, but the backend does not act on them (control is voice-only via OpenClaw). Is this acceptable UX for the first iteration, or should at least play/pause be wired to a direct Spotify API call? If direct wiring is wanted, `SpotifyClient` needs `play()`, `pause()`, `next_track()`, `previous_track()`, and the `spotify_cmd` handler must call them — scope expands by roughly one backend step.

3. **Album art in NowPlayingPanel expanded view**: The current implementation uses `track.monogram` (text initials) as the art placeholder. When a live `album_art_url` is available, should the panel render an `<img>` tag instead of the monogram box? `NowPlayingTrack` type does not have `albumArtUrl`; adding it requires a type extension and a conditional render. Recommend yes — add `albumArtUrl?: string` to `NowPlayingTrack` and render `<img>` when present, monogram as fallback.

4. **`spotify.enabled` guard in server startup**: If `SpotifyClient.initialize()` fails (no token), should the poll loop be retried on a backoff schedule (e.g., every 60 s until auth succeeds), or only re-attempted when `complete_auth()` is called via the OAuth callback? Recommend callback-triggered retry only — avoids log spam and the callback path is the explicit intent signal.
