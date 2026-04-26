"""Spotify agent for JARVIS — handles library, search, queue, and context-play intents.

Handles three intents that go beyond simple transport commands:
  - SPOTIFY_PLAY_CONTEXT: fuzzy-match a playlist name and start it.
  - SPOTIFY_SEARCH: search for a track and play it immediately.
  - SPOTIFY_QUEUE: search for a track and add it to the queue.
"""

from __future__ import annotations

from typing import Any

from brain.agents.base import AgentResult, BaseAgent
from integrations.spotify.client import (
    SpotifyAuthError,
    SpotifyClient,
    SpotifyPlaylist,
    SpotifyPollError,
    SpotifyPremiumError,
)
from utils.logger import get_logger

logger = get_logger("agent.spotify")


# ---------------------------------------------------------------------------
# Bilingual response templates
# ---------------------------------------------------------------------------

_PLAY_CONTEXT_OK_EN = "Playing playlist: {name}."
_PLAY_CONTEXT_OK_DE = "Spiele Playlist: {name}."
_PLAY_CONTEXT_NOT_FOUND_EN = "Sorry, sir — I couldn't find a playlist matching \"{query}\"."
_PLAY_CONTEXT_NOT_FOUND_DE = "Tut mir leid, Sir — keine Playlist gefunden für \"{query}\"."

_SEARCH_PLAY_OK_EN = "Playing \"{track}\" by {artist}."
_SEARCH_PLAY_OK_DE = "Spiele \"{track}\" von {artist}."
_SEARCH_NO_RESULT_EN = "No results found for \"{query}\" on Spotify."
_SEARCH_NO_RESULT_DE = "Keine Ergebnisse für \"{query}\" auf Spotify gefunden."

_QUEUE_OK_EN = "Added \"{track}\" by {artist} to the queue."
_QUEUE_OK_DE = "\"{track}\" von {artist} zur Warteschlange hinzugefügt."
_QUEUE_NO_RESULT_EN = "Couldn't find \"{query}\" to add to the queue."
_QUEUE_NO_RESULT_DE = "Konnte \"{query}\" nicht für die Warteschlange finden."

_AUTH_ERROR_EN = "Spotify authentication required, sir. Please reconnect via the HUD."
_AUTH_ERROR_DE = "Spotify-Authentifizierung erforderlich, Sir. Bitte über das HUD neu verbinden."

_PREMIUM_ERROR_EN = "This Spotify feature requires a Premium account, sir."
_PREMIUM_ERROR_DE = "Diese Spotify-Funktion erfordert ein Premium-Konto, Sir."

_RATE_LIMITED_EN = "Spotify is rate-limiting requests right now, sir. Please try again shortly."
_RATE_LIMITED_DE = "Spotify drosselt die Anfragen gerade, Sir. Bitte in Kürze erneut versuchen."

_GENERIC_ERROR_EN = "Spotify ran into an issue, sir: {error}"
_GENERIC_ERROR_DE = "Spotify hat ein Problem gemeldet, Sir: {error}"


class SpotifyAgent(BaseAgent):
    """Agent for Spotify library / search / queue operations."""

    def __init__(self, spotify_client: SpotifyClient) -> None:
        """Initialise the Spotify agent.

        Args:
            spotify_client: Authenticated SpotifyClient instance.
        """
        super().__init__()
        self._client = spotify_client

    async def run(
        self, task: str, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Dispatch to the correct Spotify operation based on ``task``.

        Args:
            task: Intent name (e.g. ``"SPOTIFY_PLAY_CONTEXT"``).
            params: Parameters extracted by the intent parser.
                Expected keys vary by intent — see each handler.
            language: Response language (``"en"`` / ``"de"``).

        Returns:
            AgentResult with a bilingual spoken response.
        """
        try:
            if task == "SPOTIFY_PLAY_CONTEXT":
                return await self._handle_play_context(params, language)
            if task == "SPOTIFY_SEARCH":
                return await self._handle_search_play(params, language)
            if task == "SPOTIFY_QUEUE":
                return await self._handle_queue_add(params, language)

            # Unknown task — fall through with a polite no-op.
            logger.warning(f"SpotifyAgent received unknown task: {task!r}")
            return AgentResult(
                spoken_response=(
                    f"Ich weiß nicht, wie ich '{task}' ausführen soll, Sir."
                    if language == "de"
                    else f"I don't know how to handle '{task}', sir."
                ),
                success=False,
                data={"task": task},
            )
        except SpotifyAuthError as exc:
            logger.warning(f"SpotifyAgent auth error for task={task!r}: {exc}")
            msg = _AUTH_ERROR_DE if language == "de" else _AUTH_ERROR_EN
            return AgentResult(spoken_response=msg, success=False, data={"error": str(exc)})
        except SpotifyPremiumError as exc:
            logger.warning(f"SpotifyAgent premium error for task={task!r}: {exc}")
            msg = _PREMIUM_ERROR_DE if language == "de" else _PREMIUM_ERROR_EN
            return AgentResult(spoken_response=msg, success=False, data={"error": str(exc)})
        except SpotifyPollError as exc:
            logger.warning(f"SpotifyAgent rate-limit/poll error for task={task!r}: {exc}")
            msg = _RATE_LIMITED_DE if language == "de" else _RATE_LIMITED_EN
            return AgentResult(spoken_response=msg, success=False, data={"error": str(exc)})
        except Exception as exc:
            logger.error(f"SpotifyAgent unexpected error for task={task!r}: {exc}")
            tmpl = _GENERIC_ERROR_DE if language == "de" else _GENERIC_ERROR_EN
            msg = tmpl.format(error=str(exc))
            return AgentResult(spoken_response=msg, success=False, data={"error": str(exc)})

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------

    async def _handle_play_context(
        self, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Fuzzy-match a playlist and start playback.

        Args:
            params: Must contain ``"query"`` key with the playlist name hint.
            language: Response language.

        Returns:
            AgentResult with a spoken confirmation or not-found message.
        """
        query: str = params.get("query", "").strip()
        if not query:
            query = params.get("artist", "").strip()

        playlists = await self._client.list_playlists(limit=50)
        if not playlists:
            msg = (
                _PLAY_CONTEXT_NOT_FOUND_DE.format(query=query)
                if language == "de"
                else _PLAY_CONTEXT_NOT_FOUND_EN.format(query=query)
            )
            return AgentResult(
                spoken_response=msg, success=False, data={"query": query}
            )

        best = _fuzzy_match_playlist(query, playlists)
        if best is None:
            msg = (
                _PLAY_CONTEXT_NOT_FOUND_DE.format(query=query)
                if language == "de"
                else _PLAY_CONTEXT_NOT_FOUND_EN.format(query=query)
            )
            return AgentResult(
                spoken_response=msg, success=False, data={"query": query}
            )

        await self._client.play_context(best.uri)
        tmpl = _PLAY_CONTEXT_OK_DE if language == "de" else _PLAY_CONTEXT_OK_EN
        msg = tmpl.format(name=best.name)
        logger.info(f"SpotifyAgent: play_context → {best.name!r} ({best.uri})")
        return AgentResult(
            spoken_response=msg,
            success=True,
            data={"playlist_name": best.name, "playlist_uri": best.uri},
        )

    async def _handle_search_play(
        self, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Search for a track and play the top result immediately.

        Args:
            params: Must contain ``"query"`` key; ``"artist"`` key is appended
                to the query when present.
            language: Response language.

        Returns:
            AgentResult with a spoken confirmation or not-found message.
        """
        query = _build_search_query(params)
        results = await self._client.search(query, types=["track"], limit=10)

        if not results.tracks:
            msg = (
                _SEARCH_NO_RESULT_DE.format(query=query)
                if language == "de"
                else _SEARCH_NO_RESULT_EN.format(query=query)
            )
            return AgentResult(
                spoken_response=msg, success=False, data={"query": query}
            )

        top = results.tracks[0]
        await self._client.play_uris([top.uri])

        tmpl = _SEARCH_PLAY_OK_DE if language == "de" else _SEARCH_PLAY_OK_EN
        msg = tmpl.format(track=top.name, artist=top.artist)
        logger.info(
            f"SpotifyAgent: search+play → {top.name!r} by {top.artist!r} ({top.uri})"
        )
        return AgentResult(
            spoken_response=msg,
            success=True,
            data={"track_name": top.name, "artist": top.artist, "uri": top.uri},
        )

    async def _handle_queue_add(
        self, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Search for a track and add the top result to the queue.

        Args:
            params: Must contain ``"query"`` key; ``"artist"`` key is appended
                to the query when present.
            language: Response language.

        Returns:
            AgentResult with a spoken confirmation or not-found message.
        """
        query = _build_search_query(params)
        results = await self._client.search(query, types=["track"], limit=10)

        if not results.tracks:
            msg = (
                _QUEUE_NO_RESULT_DE.format(query=query)
                if language == "de"
                else _QUEUE_NO_RESULT_EN.format(query=query)
            )
            return AgentResult(
                spoken_response=msg, success=False, data={"query": query}
            )

        top = results.tracks[0]
        await self._client.add_to_queue(top.uri)

        tmpl = _QUEUE_OK_DE if language == "de" else _QUEUE_OK_EN
        msg = tmpl.format(track=top.name, artist=top.artist)
        logger.info(
            f"SpotifyAgent: queue_add → {top.name!r} by {top.artist!r} ({top.uri})"
        )
        return AgentResult(
            spoken_response=msg,
            success=True,
            data={"track_name": top.name, "artist": top.artist, "uri": top.uri},
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fuzzy_match_playlist(
    query: str, playlists: list[SpotifyPlaylist], min_ratio: float = 0.6
) -> SpotifyPlaylist | None:
    """Find the best-matching playlist for a given query string.

    First tries a case-insensitive substring match; falls back to a
    Levenshtein similarity ratio when no substring match is found.

    Args:
        query: User's playlist name hint.
        playlists: List of candidate playlists.
        min_ratio: Minimum Levenshtein ratio (0–1) to accept a fuzzy match.

    Returns:
        Best-matching SpotifyPlaylist, or None if no match exceeds the threshold.
    """
    query_lower = query.lower()

    # 1. Substring match (case-insensitive).
    for pl in playlists:
        if query_lower in pl.name.lower():
            logger.debug(f"Playlist substring match: {pl.name!r} for {query!r}")
            return pl

    # 2. Levenshtein ratio fallback.
    best_pl: SpotifyPlaylist | None = None
    best_ratio = 0.0
    for pl in playlists:
        ratio = _levenshtein_ratio(query_lower, pl.name.lower())
        if ratio > best_ratio:
            best_ratio = ratio
            best_pl = pl

    if best_ratio >= min_ratio and best_pl is not None:
        logger.debug(
            f"Playlist Levenshtein match: {best_pl.name!r} "
            f"(ratio={best_ratio:.2f}) for {query!r}"
        )
        return best_pl

    logger.debug(
        f"No playlist match found for {query!r} "
        f"(best_ratio={best_ratio:.2f}, threshold={min_ratio})"
    )
    return None


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Compute the Levenshtein similarity ratio between two strings.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Float in [0, 1]; 1.0 means identical strings.
    """
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    # dp[i][j] = edit distance between s1[:i] and s2[:j]
    dp = list(range(len2 + 1))
    for i in range(1, len1 + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, len2 + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp

    distance = dp[len2]
    max_len = max(len1, len2)
    return 1.0 - distance / max_len


def _build_search_query(params: dict[str, Any]) -> str:
    """Build a Spotify search query from intent params.

    Args:
        params: Intent parameters with optional ``"query"`` and ``"artist"`` keys.

    Returns:
        Composed search query string.
    """
    query: str = params.get("query", "").strip()
    artist: str = params.get("artist", "").strip()
    if artist and artist.lower() not in query.lower():
        query = f"{query} {artist}".strip()
    return query
