"""Spotify integration package for JARVIS.

Exports the SpotifyClient, SpotifyError base class, and the module-level
factory function for constructing a shared client instance.
"""

from __future__ import annotations

from integrations.spotify.client import (
    SpotifyAuthError,
    SpotifyClient,
    SpotifyPlaylist,
    SpotifyPollError,
    SpotifyPremiumError,
    SpotifyQueueItem,
    SpotifySearchResults,
    SpotifyTrackInfo,
    SpotifyTrackResult,
)

__all__ = [
    "SpotifyAuthError",
    "SpotifyClient",
    "SpotifyPlaylist",
    "SpotifyPollError",
    "SpotifyPremiumError",
    "SpotifyQueueItem",
    "SpotifySearchResults",
    "SpotifyTrackInfo",
    "SpotifyTrackResult",
    "get_spotify_client",
]

# Module-level singleton — set by ws_server after initialize() succeeds.
_client: SpotifyClient | None = None


def get_spotify_client() -> SpotifyClient | None:
    """Return the module-level SpotifyClient singleton, or None if not initialised."""
    return _client
