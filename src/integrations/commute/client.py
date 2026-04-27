"""Commute adapter stub for JARVIS.

MVP stub — always returns ``None`` so the morning briefing skips the commute
block gracefully. A future implementer should replace ``get_summary`` with a
real provider call (SBB OpenData or Google Directions).
"""

from __future__ import annotations

from typing import Any

from utils.logger import get_logger

logger = get_logger("commute_client")


class CommuteClient:
    """Async commute adapter.

    Returns commute summary dicts that the ``MorningBriefingAgent`` can
    embed in the HUD payload. Currently a stub — see the TODO below.
    """

    async def get_summary(
        self,
        from_: str,
        to: str,
        mode: str = "auto",
    ) -> dict[str, Any] | None:
        """Return a commute summary between two locations.

        Args:
            from_: Origin address or place name.
            to: Destination address or place name.
            mode: Transport mode hint (``"auto"``, ``"transit"``,
                ``"driving"``, ``"cycling"``).

        Returns:
            Dict with commute info, or ``None`` when unavailable.
        """
        # TODO: integrate SBB OpenData API or Google Directions API.
        # Expected return shape when implemented:
        # {
        #   "durationMinutes": int,
        #   "departureTime": iso_str,
        #   "arrivalTime": iso_str,
        #   "mode": str,
        #   "summary": str,  # e.g. "S3 → S8, 32 min"
        # }
        logger.debug(f"CommuteClient.get_summary called ({from_} → {to}, mode={mode}); stub")
        return None
