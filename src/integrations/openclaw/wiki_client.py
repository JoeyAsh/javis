"""WikiClient — async read-only bridge to OpenClaw's memory-wiki RPC namespace.

Sends ``wiki.*`` RPC calls over the existing :class:`OpenClawWSClient` connection.
No second WebSocket connection is created; this client piggybacks on the
singleton gateway connection managed by :mod:`integrations.openclaw.ws_client`.

All public methods time out after 5 seconds and map errors to
:class:`WikiClientUnavailableError` so callers can return HTTP 503 cleanly.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from utils.logger import get_logger

if TYPE_CHECKING:
    from integrations.openclaw.ws_client import OpenClawWSClient

logger = get_logger("wiki_client")

# Per-call timeout — generous enough for a cold-start vault scan, tight enough
# to not block the brain_inspector broadcast cycle.
_RPC_TIMEOUT_S: float = 5.0


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass
class WikiHit:
    """A single search result returned by ``wiki.search``."""

    id: str
    title: str
    score: float
    excerpt: str
    updated_at: str


@dataclass
class WikiNote:
    """Full note content returned by ``wiki.get``."""

    id: str
    title: str
    body_md: str
    backlinks: list[str] = field(default_factory=list)
    updated_at: str = ""


@dataclass
class WikiStatus:
    """Vault status summary returned by ``wiki.status``."""

    initialised: bool
    note_count: int
    last_dream_cycle_at: str | None
    path: str | None = None
    render_mode: str | None = None


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class WikiClientUnavailableError(RuntimeError):
    """Raised when the wiki RPC is unavailable or returns an error."""


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------


class WikiClient:
    """Read-only async bridge to OpenClaw's ``wiki.*`` RPC namespace.

    Wraps the shared :class:`~integrations.openclaw.ws_client.OpenClawWSClient`
    gateway connection; no additional transport is opened.  All methods apply a
    5 s timeout and raise :class:`WikiClientUnavailableError` on any failure so
    callers can return HTTP 503 cleanly.

    Attributes:
        _ws_client: The shared OpenClaw WS client singleton.
    """

    def __init__(self, ws_client: OpenClawWSClient) -> None:
        """Initialise with the shared OpenClaw WS client.

        Args:
            ws_client: Already-constructed (and optionally connected)
                :class:`~integrations.openclaw.ws_client.OpenClawWSClient`
                singleton.  The WikiClient does not manage the connection
                lifecycle; callers must ensure ``ws_client.connect()`` has been
                awaited before issuing wiki calls.
        """
        self._ws_client = ws_client

    # ── Public API ──────────────────────────────────────────────────────────

    async def search(self, query: str, k: int = 6) -> list[WikiHit]:
        """Search the wiki vault and return up to *k* ranked hits.

        Args:
            query: Free-text search query.
            k: Maximum number of results to return (default 6).

        Returns:
            List of :class:`WikiHit` sorted by descending relevance score.
            May be empty when the vault is unseeded.

        Raises:
            WikiClientUnavailableError: On timeout, connection error, or RPC error.
        """
        try:
            result = await asyncio.wait_for(
                self._call("wiki.search", {"query": query, "maxResults": k}),
                timeout=_RPC_TIMEOUT_S,
            )
        except asyncio.TimeoutError as exc:
            raise WikiClientUnavailableError(
                f"wiki.search timed out after {_RPC_TIMEOUT_S}s"
            ) from exc
        except WikiClientUnavailableError:
            raise
        except Exception as exc:
            raise WikiClientUnavailableError(f"wiki.search failed: {exc}") from exc

        hits: list[WikiHit] = []
        for item in result if isinstance(result, list) else []:
            hits.append(
                WikiHit(
                    id=str(item.get("id") or item.get("path") or ""),
                    title=str(item.get("title") or ""),
                    score=float(item.get("score") or 0.0),
                    excerpt=str(item.get("snippet") or ""),
                    updated_at=str(item.get("updatedAt") or ""),
                )
            )
        return hits

    async def get(self, note_id: str) -> WikiNote:
        """Fetch a single note by its path/id.

        Args:
            note_id: The vault-relative path or ID of the note (as returned
                in :attr:`WikiHit.id`).

        Returns:
            :class:`WikiNote` with the full markdown body.

        Raises:
            WikiClientUnavailableError: On timeout, connection error, or when
                the note is not found (RPC error).
        """
        try:
            result = await asyncio.wait_for(
                self._call("wiki.get", {"lookup": note_id}),
                timeout=_RPC_TIMEOUT_S,
            )
        except asyncio.TimeoutError as exc:
            raise WikiClientUnavailableError(
                f"wiki.get timed out after {_RPC_TIMEOUT_S}s"
            ) from exc
        except WikiClientUnavailableError:
            raise
        except Exception as exc:
            raise WikiClientUnavailableError(f"wiki.get failed: {exc}") from exc

        if not isinstance(result, dict):
            raise WikiClientUnavailableError(
                f"wiki.get returned unexpected type: {type(result).__name__}"
            )

        return WikiNote(
            id=str(result.get("id") or result.get("path") or note_id),
            title=str(result.get("title") or ""),
            body_md=str(result.get("content") or ""),
            backlinks=[],
            updated_at=str(result.get("updatedAt") or ""),
        )

    async def status(self) -> WikiStatus:
        """Fetch the current vault status from the OpenClaw plugin.

        Returns:
            :class:`WikiStatus` reflecting the current vault state.

        Raises:
            WikiClientUnavailableError: On timeout, connection error, or RPC error.
        """
        try:
            result = await asyncio.wait_for(
                self._call("wiki.status", {}),
                timeout=_RPC_TIMEOUT_S,
            )
        except asyncio.TimeoutError as exc:
            raise WikiClientUnavailableError(
                f"wiki.status timed out after {_RPC_TIMEOUT_S}s"
            ) from exc
        except WikiClientUnavailableError:
            raise
        except Exception as exc:
            raise WikiClientUnavailableError(f"wiki.status failed: {exc}") from exc

        if not isinstance(result, dict):
            raise WikiClientUnavailableError(
                f"wiki.status returned unexpected type: {type(result).__name__}"
            )

        page_counts: dict[str, int] = result.get("pageCounts") or {}
        total_notes = sum(page_counts.values())
        vault_exists: bool = bool(result.get("vaultExists", False))

        return WikiStatus(
            initialised=vault_exists,
            note_count=total_notes,
            last_dream_cycle_at=None,  # memory-wiki does not expose dream cycle ts yet
            path=str(result.get("vaultPath") or ""),
            render_mode=str(result.get("renderMode") or ""),
        )

    async def obsidian_open(self, note_id: str) -> bool:
        """Request Obsidian to open the given vault path.

        Args:
            note_id: The vault-relative file path (``WikiHit.id``) to open.

        Returns:
            ``True`` when Obsidian accepted the open request.

        Raises:
            WikiClientUnavailableError: On timeout, connection error, or when
                Obsidian is not installed / not running.
        """
        try:
            await asyncio.wait_for(
                self._call("wiki.obsidian.open", {"path": note_id}),
                timeout=_RPC_TIMEOUT_S,
            )
            return True
        except asyncio.TimeoutError as exc:
            raise WikiClientUnavailableError(
                f"wiki.obsidian.open timed out after {_RPC_TIMEOUT_S}s"
            ) from exc
        except WikiClientUnavailableError:
            raise
        except Exception as exc:
            raise WikiClientUnavailableError(
                f"wiki.obsidian.open failed: {exc}"
            ) from exc

    # ── Internal RPC helper ─────────────────────────────────────────────────

    async def _call(self, method: str, params: dict[str, Any]) -> Any:
        """Send a gateway RPC and await the response.

        Uses the shared WS connection via a pending-RPC registry on the client.
        Falls back to :meth:`~integrations.openclaw.ws_client.OpenClawWSClient.call_rpc`
        which this module extends onto the client if not present.

        Args:
            method: Gateway RPC method name (e.g. ``"wiki.search"``).
            params: RPC parameter dict.

        Returns:
            The ``payload`` field from the gateway response.

        Raises:
            WikiClientUnavailableError: When the gateway is not connected or
                returns an error response.
        """
        if not self._ws_client.is_connected:
            try:
                await self._ws_client.connect()
            except Exception as exc:
                raise WikiClientUnavailableError(
                    f"Cannot connect to OpenClaw gateway: {exc}"
                ) from exc

        try:
            return await self._ws_client.call_rpc(method, params)
        except WikiClientUnavailableError:
            raise
        except Exception as exc:
            raise WikiClientUnavailableError(
                f"RPC {method!r} failed: {exc}"
            ) from exc
