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


class SpotifyPremiumError(Exception):
    """Raised when the Spotify API returns 403 (Premium required)."""


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


@dataclass
class SpotifyPlaylist:
    """A Spotify playlist summary."""

    id: str
    name: str
    owner: str
    track_count: int
    uri: str


@dataclass
class SpotifyTrackResult:
    """A Spotify track from search or library results."""

    id: str
    name: str
    artist: str
    album: str
    duration_ms: int
    uri: str


@dataclass
class SpotifySearchResults:
    """Aggregated results from a Spotify search."""

    tracks: list[SpotifyTrackResult]
    artists: list[dict[str, Any]]
    albums: list[dict[str, Any]]
    playlists: list[SpotifyPlaylist]


@dataclass
class SpotifyQueueItem:
    """A single entry in the Spotify playback queue."""

    position: int
    name: str
    artist: str
    uri: str


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
    # Internal error-mapping helper
    # ------------------------------------------------------------------

    def _map_spotipy_exception(self, exc: Exception) -> Exception:
        """Map a spotipy exception to the appropriate JARVIS error type.

        Args:
            exc: The caught exception from a spotipy call.

        Returns:
            A mapped JARVIS exception (SpotifyAuthError, SpotifyPremiumError,
            SpotifyPollError).
        """
        import spotipy

        if isinstance(exc, spotipy.SpotifyException):
            if exc.http_status == 401:
                self._authenticated = False
                return SpotifyAuthError(f"Spotify token revoked or expired: {exc}")
            if exc.http_status == 403:
                return SpotifyPremiumError(
                    f"Spotify Premium required for this action: {exc}"
                )
            if exc.http_status == 429:
                retry_after = getattr(exc, "headers", {}) or {}
                if isinstance(retry_after, dict):
                    ra_val = retry_after.get("Retry-After")
                else:
                    ra_val = None
                if ra_val:
                    logger.warning(
                        f"Spotify rate-limited (429) — retry-after={ra_val}s: {exc}"
                    )
                else:
                    logger.warning(f"Spotify rate-limited (429): {exc}")
                poll_err = SpotifyPollError(f"Rate limited: {exc}")
                # Attach retry_after for callers that need to surface it.
                poll_err.retry_after = ra_val  # type: ignore[attr-defined]
                return poll_err
            return SpotifyPollError(f"Spotify API error ({exc.http_status}): {exc}")
        return SpotifyPollError(f"Unexpected Spotify error: {exc}")

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

    # ------------------------------------------------------------------
    # Library — playlists, saved tracks, saved albums
    # ------------------------------------------------------------------

    async def list_playlists(
        self, limit: int = 50, offset: int = 0
    ) -> list[SpotifyPlaylist]:
        """Return the current user's playlists.

        Args:
            limit: Maximum number of playlists to return (1–50).
            offset: Pagination offset.

        Returns:
            List of SpotifyPlaylist dataclasses.

        Raises:
            SpotifyAuthError: When not authenticated.
            SpotifyPremiumError: When the API returns 403.
            SpotifyPollError: On rate-limit or other API errors.
        """
        if self._spotify is None:
            raise SpotifyAuthError("Spotify client not initialised.")

        try:
            result = await asyncio.to_thread(
                self._spotify.current_user_playlists, limit=limit, offset=offset
            )
        except Exception as exc:
            raise self._map_spotipy_exception(exc) from exc

        playlists: list[SpotifyPlaylist] = []
        for item in (result or {}).get("items", []):
            if item is None:
                continue
            playlists.append(
                SpotifyPlaylist(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    owner=item.get("owner", {}).get("display_name", ""),
                    track_count=item.get("tracks", {}).get("total", 0),
                    uri=item.get("uri", ""),
                )
            )
        logger.debug(f"Spotify: list_playlists → {len(playlists)} items")
        return playlists

    async def playlist_tracks(
        self, playlist_id: str, limit: int = 100, offset: int = 0
    ) -> list[SpotifyTrackResult]:
        """Return the tracks of a specific playlist.

        Args:
            playlist_id: Spotify playlist ID.
            limit: Maximum number of tracks to return (1–100).
            offset: Pagination offset.

        Returns:
            List of SpotifyTrackResult dataclasses.

        Raises:
            SpotifyAuthError: When not authenticated.
            SpotifyPremiumError: When the API returns 403.
            SpotifyPollError: On rate-limit or other API errors.
        """
        if self._spotify is None:
            raise SpotifyAuthError("Spotify client not initialised.")

        try:
            result = await asyncio.to_thread(
                self._spotify.playlist_tracks,
                playlist_id,
                limit=limit,
                offset=offset,
            )
        except Exception as exc:
            raise self._map_spotipy_exception(exc) from exc

        return _extract_tracks_from_items((result or {}).get("items", []))

    async def album_tracks(
        self, album_id: str, limit: int = 50, offset: int = 0
    ) -> list[SpotifyTrackResult]:
        """Return the tracks of a specific album.

        Args:
            album_id: Spotify album ID.
            limit: Maximum number of tracks to return (1–50).
            offset: Pagination offset.

        Returns:
            List of SpotifyTrackResult dataclasses.

        Raises:
            SpotifyAuthError: When not authenticated.
            SpotifyPremiumError: When the API returns 403.
            SpotifyPollError: On rate-limit or other API errors.
        """
        if self._spotify is None:
            raise SpotifyAuthError("Spotify client not initialised.")

        try:
            result = await asyncio.to_thread(
                self._spotify.album_tracks, album_id, limit=limit, offset=offset
            )
        except Exception as exc:
            raise self._map_spotipy_exception(exc) from exc

        tracks: list[SpotifyTrackResult] = []
        for item in (result or {}).get("items", []):
            if item is None:
                continue
            artists = item.get("artists", [])
            artist_str = ", ".join(a.get("name", "") for a in artists)
            tracks.append(
                SpotifyTrackResult(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    artist=artist_str,
                    album="",  # album_tracks endpoint does not return album name per track
                    duration_ms=int(item.get("duration_ms", 0)),
                    uri=item.get("uri", ""),
                )
            )
        logger.debug(f"Spotify: album_tracks({album_id}) → {len(tracks)} items")
        return tracks

    async def saved_tracks(
        self, limit: int = 50, offset: int = 0
    ) -> list[SpotifyTrackResult]:
        """Return the current user's saved (liked) tracks.

        Args:
            limit: Maximum number of tracks to return (1–50).
            offset: Pagination offset.

        Returns:
            List of SpotifyTrackResult dataclasses.

        Raises:
            SpotifyAuthError: When not authenticated.
            SpotifyPremiumError: When the API returns 403.
            SpotifyPollError: On rate-limit or other API errors.
        """
        if self._spotify is None:
            raise SpotifyAuthError("Spotify client not initialised.")

        try:
            result = await asyncio.to_thread(
                self._spotify.current_user_saved_tracks, limit=limit, offset=offset
            )
        except Exception as exc:
            raise self._map_spotipy_exception(exc) from exc

        return _extract_tracks_from_items((result or {}).get("items", []))

    async def saved_albums(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Return the current user's saved albums as raw dicts.

        Args:
            limit: Maximum number of albums to return (1–50).
            offset: Pagination offset.

        Returns:
            List of raw album dicts from the Spotify Web API.

        Raises:
            SpotifyAuthError: When not authenticated.
            SpotifyPremiumError: When the API returns 403.
            SpotifyPollError: On rate-limit or other API errors.
        """
        if self._spotify is None:
            raise SpotifyAuthError("Spotify client not initialised.")

        try:
            result = await asyncio.to_thread(
                self._spotify.current_user_saved_albums, limit=limit, offset=offset
            )
        except Exception as exc:
            raise self._map_spotipy_exception(exc) from exc

        albums: list[dict[str, Any]] = []
        for item in (result or {}).get("items", []):
            if item is None:
                continue
            album = item.get("album", item)
            albums.append(
                {
                    "id": album.get("id", ""),
                    "name": album.get("name", ""),
                    "artist": ", ".join(
                        a.get("name", "") for a in album.get("artists", [])
                    ),
                    "total_tracks": album.get("total_tracks", 0),
                    "uri": album.get("uri", ""),
                    "release_date": album.get("release_date", ""),
                }
            )
        logger.debug(f"Spotify: saved_albums → {len(albums)} items")
        return albums

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 10,
    ) -> SpotifySearchResults:
        """Search the Spotify catalogue.

        Args:
            query: Free-text search query.
            types: List of search types; defaults to
                ``["track", "artist", "album", "playlist"]``.
            limit: Maximum results per type (1–50).

        Returns:
            SpotifySearchResults with typed buckets.

        Raises:
            SpotifyAuthError: When not authenticated.
            SpotifyPremiumError: When the API returns 403.
            SpotifyPollError: On rate-limit or other API errors.
        """
        if self._spotify is None:
            raise SpotifyAuthError("Spotify client not initialised.")

        search_types = types or ["track", "artist", "album", "playlist"]
        type_str = ",".join(search_types)

        try:
            result = await asyncio.to_thread(
                self._spotify.search, query, limit=limit, type=type_str
            )
        except Exception as exc:
            raise self._map_spotipy_exception(exc) from exc

        result = result or {}

        # --- tracks ---
        track_items = result.get("tracks", {}).get("items", [])
        tracks: list[SpotifyTrackResult] = []
        for item in track_items:
            if item is None:
                continue
            artists = item.get("artists", [])
            artist_str = ", ".join(a.get("name", "") for a in artists)
            tracks.append(
                SpotifyTrackResult(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    artist=artist_str,
                    album=item.get("album", {}).get("name", ""),
                    duration_ms=int(item.get("duration_ms", 0)),
                    uri=item.get("uri", ""),
                )
            )

        # --- artists ---
        artist_items = result.get("artists", {}).get("items", [])
        artists_out: list[dict[str, Any]] = [
            {
                "id": a.get("id", ""),
                "name": a.get("name", ""),
                "uri": a.get("uri", ""),
                "genres": a.get("genres", []),
            }
            for a in artist_items
            if a is not None
        ]

        # --- albums ---
        album_items = result.get("albums", {}).get("items", [])
        albums_out: list[dict[str, Any]] = [
            {
                "id": a.get("id", ""),
                "name": a.get("name", ""),
                "artist": ", ".join(ar.get("name", "") for ar in a.get("artists", [])),
                "uri": a.get("uri", ""),
                "release_date": a.get("release_date", ""),
                "total_tracks": a.get("total_tracks", 0),
            }
            for a in album_items
            if a is not None
        ]

        # --- playlists ---
        playlist_items = result.get("playlists", {}).get("items", [])
        playlists: list[SpotifyPlaylist] = [
            SpotifyPlaylist(
                id=p.get("id", ""),
                name=p.get("name", ""),
                owner=p.get("owner", {}).get("display_name", ""),
                track_count=p.get("tracks", {}).get("total", 0),
                uri=p.get("uri", ""),
            )
            for p in playlist_items
            if p is not None
        ]

        logger.debug(
            f"Spotify: search({query!r}) → "
            f"{len(tracks)} tracks, {len(artists_out)} artists, "
            f"{len(albums_out)} albums, {len(playlists)} playlists"
        )
        return SpotifySearchResults(
            tracks=tracks,
            artists=artists_out,
            albums=albums_out,
            playlists=playlists,
        )

    # ------------------------------------------------------------------
    # Queue
    # ------------------------------------------------------------------

    async def get_queue(self) -> list[SpotifyQueueItem]:
        """Return the current user's playback queue.

        Returns:
            List of SpotifyQueueItem (position 0 = next up).

        Raises:
            SpotifyAuthError: When not authenticated.
            SpotifyPremiumError: When the API returns 403.
            SpotifyPollError: On rate-limit or other API errors.
        """
        if self._spotify is None:
            raise SpotifyAuthError("Spotify client not initialised.")

        try:
            result = await asyncio.to_thread(self._spotify.queue)
        except Exception as exc:
            raise self._map_spotipy_exception(exc) from exc

        queue_items: list[SpotifyQueueItem] = []
        for i, item in enumerate((result or {}).get("queue", [])):
            if item is None:
                continue
            artists = item.get("artists", [])
            artist_str = ", ".join(a.get("name", "") for a in artists)
            queue_items.append(
                SpotifyQueueItem(
                    position=i,
                    name=item.get("name", ""),
                    artist=artist_str,
                    uri=item.get("uri", ""),
                )
            )
        logger.debug(f"Spotify: get_queue → {len(queue_items)} items")
        return queue_items

    async def add_to_queue(self, uri: str) -> None:
        """Add a track (or episode) URI to the playback queue.

        Args:
            uri: Spotify URI to enqueue (e.g. ``spotify:track:<id>``).

        Raises:
            SpotifyAuthError: When not authenticated.
            SpotifyPremiumError: When the API returns 403.
            SpotifyPollError: On rate-limit or other API errors.
        """
        if self._spotify is None:
            raise SpotifyAuthError("Spotify client not initialised.")

        try:
            await asyncio.to_thread(self._spotify.add_to_queue, uri)
        except Exception as exc:
            raise self._map_spotipy_exception(exc) from exc

        logger.debug(f"Spotify: add_to_queue({uri!r})")

    # ------------------------------------------------------------------
    # Context / URI playback
    # ------------------------------------------------------------------

    async def play_context(
        self,
        context_uri: str,
        offset_uri: str | None = None,
        device_id: str | None = None,
    ) -> None:
        """Start playback of a Spotify context (album, playlist, artist).

        Args:
            context_uri: Spotify context URI
                (e.g. ``spotify:playlist:<id>``).
            offset_uri: Optional track URI to start from within the context.
            device_id: Optional Spotify Connect device ID to target.
                When ``None``, Spotify targets the currently active device.

        Raises:
            SpotifyAuthError: When not authenticated.
            SpotifyPremiumError: When the API returns 403.
            SpotifyPollError: On rate-limit or other API errors.
        """
        if self._spotify is None:
            raise SpotifyAuthError("Spotify client not initialised.")

        kwargs: dict[str, Any] = {"context_uri": context_uri}
        if offset_uri:
            kwargs["offset"] = {"uri": offset_uri}
        if device_id:
            kwargs["device_id"] = device_id

        try:
            await asyncio.to_thread(self._spotify.start_playback, **kwargs)
        except Exception as exc:
            raise self._map_spotipy_exception(exc) from exc

        logger.debug(
            f"Spotify: play_context({context_uri!r}, offset={offset_uri!r},"
            f" device_id={device_id!r})"
        )

    async def play_uris(self, uris: list[str], device_id: str | None = None) -> None:
        """Start playback of an explicit list of track URIs.

        Args:
            uris: List of Spotify track URIs to play.
            device_id: Optional Spotify Connect device ID to target.
                When ``None``, Spotify targets the currently active device.

        Raises:
            SpotifyAuthError: When not authenticated.
            SpotifyPremiumError: When the API returns 403.
            SpotifyPollError: On rate-limit or other API errors.
        """
        if self._spotify is None:
            raise SpotifyAuthError("Spotify client not initialised.")

        if not uris:
            logger.warning("Spotify: play_uris called with empty list — no-op")
            return

        kwargs: dict[str, Any] = {"uris": uris}
        if device_id:
            kwargs["device_id"] = device_id

        try:
            await asyncio.to_thread(self._spotify.start_playback, **kwargs)
        except Exception as exc:
            raise self._map_spotipy_exception(exc) from exc

        logger.debug(f"Spotify: play_uris({uris!r}, device_id={device_id!r})")

    async def get_access_token(self) -> tuple[str, int]:
        """Return a valid PKCE access token and its remaining TTL in seconds.

        Reads the cached token from the PKCE instance.  When the token has
        fewer than 60 seconds left before expiry, a refresh is triggered via
        the PKCE flow before returning.

        Returns:
            A ``(access_token, expires_in_seconds)`` tuple.

        Raises:
            SpotifyAuthError: When no PKCE instance is available, no token is
                cached, or the token cannot be refreshed.
        """
        import time

        if self._pkce is None:
            raise SpotifyAuthError(
                "SpotifyClient not initialised — call initialize() first."
            )

        try:
            token_info: dict[str, Any] | None = await asyncio.to_thread(
                self._pkce.get_cached_token
            )
        except Exception as exc:
            raise SpotifyAuthError(f"Failed to read Spotify token cache: {exc}") from exc

        if token_info is None:
            raise SpotifyAuthError("No cached Spotify token — user must authenticate first.")

        access_token: str = token_info.get("access_token", "")
        expires_at: float = float(token_info.get("expires_at", 0))
        now = time.time()
        remaining = expires_at - now

        if remaining < 60:
            # Refresh the token via PKCE.
            logger.info("Spotify access token expiring soon — refreshing")
            try:
                refreshed: dict[str, Any] | None = await asyncio.to_thread(
                    self._pkce.refresh_access_token,
                    token_info.get("refresh_token", ""),
                )
            except Exception as exc:
                raise SpotifyAuthError(f"Spotify token refresh failed: {exc}") from exc

            if refreshed is None:
                raise SpotifyAuthError("Spotify token refresh returned no data.")

            access_token = refreshed.get("access_token", "")
            expires_at = float(refreshed.get("expires_at", 0))
            remaining = expires_at - time.time()

        if not access_token:
            raise SpotifyAuthError("Spotify access token is empty after refresh attempt.")

        expires_in = max(0, int(remaining))
        logger.debug(f"Spotify: get_access_token — expires_in={expires_in}s")
        return access_token, expires_in


# ------------------------------------------------------------------
# Module-level helper
# ------------------------------------------------------------------


def _extract_tracks_from_items(items: list[Any]) -> list[SpotifyTrackResult]:
    """Extract SpotifyTrackResult list from Spotify API items array.

    Handles both raw track objects and wrapped ``{track: {...}}`` objects
    (as returned by saved_tracks and playlist_tracks endpoints).

    Args:
        items: Raw items list from the Spotify Web API response.

    Returns:
        List of SpotifyTrackResult dataclasses.
    """
    tracks: list[SpotifyTrackResult] = []
    for item in items:
        if item is None:
            continue
        # playlist_tracks / saved_tracks wrap the track under "track" key.
        track = item.get("track", item) if isinstance(item, dict) else item
        if track is None:
            continue
        artists = track.get("artists", [])
        artist_str = ", ".join(a.get("name", "") for a in artists)
        tracks.append(
            SpotifyTrackResult(
                id=track.get("id", ""),
                name=track.get("name", ""),
                artist=artist_str,
                album=track.get("album", {}).get("name", ""),
                duration_ms=int(track.get("duration_ms", 0)),
                uri=track.get("uri", ""),
            )
        )
    return tracks
