"""Spotify client for JARVIS — PKCE OAuth + playback-state polling.

Wraps ``spotipy.Spotify`` with PKCE auth (no client secret required).
All blocking spotipy calls are wrapped in ``asyncio.to_thread`` so the
event loop is never stalled.

Requires Spotify Premium for playback-state queries; this is enforced
by Spotify's API — JARVIS does not check it programmatically.

Token is cached at ``~/.jarvis/spotify_token.json`` (or the path set
by the ``SPOTIFY_TOKEN_CACHE`` env var / ``token_cache_path`` config key).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger("spotify_client")


class SpotifyAuthError(Exception):
    """Raised when Spotify PKCE authentication fails or is missing."""


class SpotifyPollError(Exception):
    """Raised when a Spotify API poll call fails (non-auth error)."""


@dataclass
class SpotifyTrackInfo:
    """Playback state snapshot returned by SpotifyClient.get_playback_state()."""

    track_id: str
    name: str
    artist: str
    album: str
    album_art_url: str
    duration_ms: int
    progress_ms: int
    is_playing: bool
    shuffle: bool
    repeat: str  # "off" | "track" | "context"
    device_name: str


class SpotifyClient:
    """Async wrapper around spotipy.Spotify with PKCE auth.

    All blocking spotipy calls run inside asyncio.to_thread to keep the
    event loop free.  Construct via dependency-injection; do not create
    a singleton by hand — ws_server owns the lifecycle.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialise the client from the ``spotify`` config section.

        Args:
            config: The ``spotify:`` section from config.yaml.
        """
        self._config = config

        # Resolve token cache path — env var wins, then config key, then default.
        raw_path = (
            os.environ.get("SPOTIFY_TOKEN_CACHE")
            or config.get("token_cache_path", "~/.jarvis/spotify_token.json")
        )
        self._token_cache_path: Path = Path(raw_path).expanduser()

        # Redirect URI — env var wins, then hardcoded default.
        self._redirect_uri: str = os.environ.get(
            "SPOTIFY_REDIRECT_URI",
            "http://127.0.0.1:8766/oauth/spotify/callback",
        )

        # Scopes — from config or a sensible default set.
        self._scopes: list[str] = config.get(
            "scopes",
            [
                "user-read-playback-state",
                "user-modify-playback-state",
                "user-read-currently-playing",
            ],
        )

        # Populated by initialize().
        self._pkce: Any = None  # spotipy.oauth2.SpotifyPKCE
        self._spotify: Any = None  # spotipy.Spotify
        self._authenticated: bool = False

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _get_client_id(self) -> str:
        """Return SPOTIFY_CLIENT_ID from env, raising if absent."""
        client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
        if not client_id:
            raise SpotifyAuthError(
                "SPOTIFY_CLIENT_ID is not set in the environment. "
                "Add it to .env before starting JARVIS with Spotify enabled."
            )
        return client_id

    def get_auth_url(self) -> str:
        """Return the PKCE authorization URL the user must visit.

        Returns:
            Fully qualified Spotify PKCE authorization URL.

        Raises:
            SpotifyAuthError: If the PKCE instance has not been created yet.
        """
        if self._pkce is None:
            raise SpotifyAuthError(
                "SpotifyClient not initialised — call initialize() first."
            )
        return self._pkce.get_authorize_url()

    def is_authenticated(self) -> bool:
        """Return True when a valid token is cached and the client is ready."""
        return self._authenticated

    async def initialize(self) -> None:
        """Initialise the PKCE flow and load any cached token.

        Creates the SpotifyPKCE instance, ensures the token cache directory
        exists, and attempts to load a cached token.  If no valid token is
        found, raises SpotifyAuthError — the caller should call get_auth_url()
        and present the URL to the user.

        Raises:
            SpotifyAuthError: When SPOTIFY_CLIENT_ID is missing or no
                cached token is found.
        """
        import spotipy
        import spotipy.oauth2

        client_id = self._get_client_id()

        # Ensure cache directory exists.
        self._token_cache_path.parent.mkdir(parents=True, exist_ok=True)

        scope_str = " ".join(self._scopes)
        self._pkce = spotipy.oauth2.SpotifyPKCE(
            client_id=client_id,
            redirect_uri=self._redirect_uri,
            scope=scope_str,
            cache_path=str(self._token_cache_path),
            open_browser=False,
        )

        # Attempt to load a cached token.
        try:
            token_info = await asyncio.to_thread(
                self._pkce.get_cached_token
            )
        except Exception as exc:
            raise SpotifyAuthError(
                f"Failed to read Spotify token cache: {exc}"
            ) from exc

        if token_info is None:
            raise SpotifyAuthError(
                "No cached Spotify token found. "
                f"Visit the auth URL to authenticate: {self.get_auth_url()}"
            )

        self._spotify = spotipy.Spotify(auth_manager=self._pkce)
        self._authenticated = True
        logger.info(
            f"Spotify client initialised (token cache: {self._token_cache_path})"
        )

    async def complete_auth(self, code: str) -> None:
        """Exchange a PKCE authorization code for tokens and cache them.

        Called by the OAuth callback handler after the user authorises the app.
        Creates/refreshes the PKCE instance before exchanging the code so the
        client is usable even when initialize() has not yet succeeded.

        Args:
            code: The one-time authorization code from the callback query string.

        Raises:
            SpotifyAuthError: When the code exchange fails.
        """
        import spotipy
        import spotipy.oauth2

        client_id = self._get_client_id()
        self._token_cache_path.parent.mkdir(parents=True, exist_ok=True)

        scope_str = " ".join(self._scopes)

        if self._pkce is None:
            self._pkce = spotipy.oauth2.SpotifyPKCE(
                client_id=client_id,
                redirect_uri=self._redirect_uri,
                scope=scope_str,
                cache_path=str(self._token_cache_path),
                open_browser=False,
            )

        try:
            await asyncio.to_thread(self._pkce.get_access_token, code)
        except Exception as exc:
            raise SpotifyAuthError(
                f"Spotify PKCE token exchange failed: {exc}"
            ) from exc

        self._spotify = spotipy.Spotify(auth_manager=self._pkce)
        self._authenticated = True
        logger.info(
            f"Spotify OAuth complete — token cached at {self._token_cache_path}"
        )

    # ------------------------------------------------------------------
    # Playback polling
    # ------------------------------------------------------------------

    async def get_playback_state(self) -> SpotifyTrackInfo | None:
        """Poll Spotify for the current playback state.

        Returns None when no device is active or playback has stopped.
        Auto-refreshes the token via SpotifyPKCE when it expires.

        Returns:
            SpotifyTrackInfo snapshot, or None when nothing is playing.

        Raises:
            SpotifyPollError: On non-auth API errors (rate limit, 5xx, etc.)
                after the error has been logged.
        """
        if self._spotify is None or not self._authenticated:
            return None

        try:
            data: dict[str, Any] | None = await asyncio.to_thread(
                self._spotify.current_playback
            )
        except Exception as exc:
            import spotipy

            if isinstance(exc, spotipy.SpotifyException):
                if exc.http_status == 401:
                    # Token likely revoked — mark unauthenticated.
                    self._authenticated = False
                    raise SpotifyAuthError(
                        f"Spotify token revoked or expired: {exc}"
                    ) from exc
                if exc.http_status == 429:
                    logger.warning(f"Spotify rate-limited (429) — backing off: {exc}")
                    raise SpotifyPollError(f"Rate limited: {exc}") from exc
                raise SpotifyPollError(f"Spotify API error: {exc}") from exc
            raise SpotifyPollError(f"Unexpected poll error: {exc}") from exc

        if data is None:
            return None

        item = data.get("item")
        if item is None:
            return None

        # Extract artist names.
        artists = item.get("artists", [])
        artist_str = ", ".join(a.get("name", "") for a in artists)

        # Extract album art (first image, largest).
        images = item.get("album", {}).get("images", [])
        album_art = images[0].get("url", "") if images else ""

        device = data.get("device", {})

        # Normalise repeat_state → "off" | "track" | "context"
        repeat_raw = data.get("repeat_state", "off")
        repeat_map = {"off": "off", "track": "track", "context": "context"}
        repeat = repeat_map.get(repeat_raw, "off")

        return SpotifyTrackInfo(
            track_id=item.get("id", ""),
            name=item.get("name", ""),
            artist=artist_str,
            album=item.get("album", {}).get("name", ""),
            album_art_url=album_art,
            duration_ms=int(item.get("duration_ms", 0)),
            progress_ms=int(data.get("progress_ms") or 0),
            is_playing=bool(data.get("is_playing", False)),
            shuffle=bool(data.get("shuffle_state", False)),
            repeat=repeat,
            device_name=device.get("name", ""),
        )

    # ------------------------------------------------------------------
    # Playback control  (Phase 1 — direct API calls per authorised decisions)
    # ------------------------------------------------------------------

    async def play(self) -> None:
        """Resume or start playback on the active device."""
        if self._spotify is None:
            return
        await asyncio.to_thread(self._spotify.start_playback)
        logger.debug("Spotify: play")

    async def pause(self) -> None:
        """Pause playback on the active device."""
        if self._spotify is None:
            return
        await asyncio.to_thread(self._spotify.pause_playback)
        logger.debug("Spotify: pause")

    async def next_track(self) -> None:
        """Skip to the next track."""
        if self._spotify is None:
            return
        await asyncio.to_thread(self._spotify.next_track)
        logger.debug("Spotify: next_track")

    async def previous_track(self) -> None:
        """Skip to the previous track."""
        if self._spotify is None:
            return
        await asyncio.to_thread(self._spotify.previous_track)
        logger.debug("Spotify: previous_track")

    async def set_volume(self, pct: int) -> None:
        """Set the playback volume.

        Args:
            pct: Volume percentage (0–100).
        """
        if self._spotify is None:
            return
        pct = max(0, min(100, pct))
        await asyncio.to_thread(self._spotify.volume, pct)
        logger.debug(f"Spotify: set_volume({pct})")

    async def get_devices(self) -> list[dict[str, Any]]:
        """Return the list of available Spotify Connect devices.

        Returns:
            List of device dicts from the Spotify Web API.
        """
        if self._spotify is None:
            return []
        result = await asyncio.to_thread(self._spotify.devices)
        return result.get("devices", []) if result else []

    async def transfer_playback(self, device_id: str) -> None:
        """Transfer playback to a specific device.

        Args:
            device_id: Spotify Connect device ID.
        """
        if self._spotify is None:
            return
        await asyncio.to_thread(
            self._spotify.transfer_playback, device_id, force_play=True
        )
        logger.debug(f"Spotify: transfer_playback({device_id})")
