"""Online greeting — JARVIS announces himself when the first client connects.

Generates a short status-report sentence from currently-available runtime
state (calendar, mail, system, openclaw) and produces a TTS audio frame on
the fly.  Fired exactly once per backend boot.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger("online_greeting")


@dataclass
class GreetingContext:
    """Runtime data gathered just before the greeting is spoken."""

    salutation: str  # e.g. "Sir" / "Johannes"
    language: str  # "en" | "de"
    unread_mail: int | None  # None = data not available
    calendar_today: int | None
    open_prs: int | None
    openclaw_reachable: bool
    cpu_ok: bool  # True if cpu < 80 %
    ram_ok: bool  # True if ram < 90 %


def render_greeting_text(ctx: GreetingContext) -> str:
    """Build a single short German/English sentence from ctx values.

    Rules:
    - Always lead with "Online" + salutation.
    - Append at most TWO data clauses (most-relevant first: mail > calendar > prs)
      — skip clauses where the data is None or zero.
    - Always close with "All systems nominal" / "Alles bereit" — UNLESS
      openclaw_reachable=False or cpu_ok=False or ram_ok=False, then
      replace with the specific concern.
    - Total sentence < 25 words; plain prose, no markdown.
    """
    is_de = ctx.language == "de"

    # --- Opening -----------------------------------------------------------
    if is_de:
        parts = [f"Bin online, {ctx.salutation}."]
    else:
        parts = [f"Online, {ctx.salutation}."]

    # --- Up to two data clauses (mail > calendar > prs) --------------------
    clauses_added = 0

    if ctx.unread_mail is not None and ctx.unread_mail > 0 and clauses_added < 2:
        if is_de:
            parts.append(
                f"{ctx.unread_mail} ungelesene"
                f" {'Mail' if ctx.unread_mail == 1 else 'Mails'}."
            )
        else:
            noun = "email" if ctx.unread_mail == 1 else "emails"
            parts.append(f"{ctx.unread_mail} unread {noun}.")
        clauses_added += 1

    if ctx.calendar_today is not None and ctx.calendar_today > 0 and clauses_added < 2:
        if is_de:
            parts.append(
                f"{ctx.calendar_today}"
                f" {'Termin' if ctx.calendar_today == 1 else 'Termine'} heute."
            )
        else:
            noun = "event" if ctx.calendar_today == 1 else "events"
            parts.append(f"{ctx.calendar_today} calendar {noun} today.")
        clauses_added += 1

    if ctx.open_prs is not None and ctx.open_prs > 0 and clauses_added < 2:
        if is_de:
            parts.append(
                f"{ctx.open_prs} offene"
                f" {'Pull-Request' if ctx.open_prs == 1 else 'Pull-Requests'}."
            )
        else:
            noun = "pull request" if ctx.open_prs == 1 else "pull requests"
            parts.append(f"{ctx.open_prs} open {noun}.")
        clauses_added += 1

    # --- Closing / concern -------------------------------------------------
    if not ctx.openclaw_reachable:
        if is_de:
            parts.append("Hinweis: Gateway nicht erreichbar.")
        else:
            parts.append("Note: gateway unreachable.")
    elif not ctx.cpu_ok:
        if is_de:
            parts.append("Hinweis: CPU unter Last.")
        else:
            parts.append("Note: CPU under load.")
    elif not ctx.ram_ok:
        if is_de:
            parts.append("Hinweis: RAM unter Last.")
        else:
            parts.append("Note: RAM under load.")
    else:
        if is_de:
            parts.append("Alle Systeme nominal.")
        else:
            parts.append("All systems nominal.")

    return " ".join(parts)


async def collect_greeting_context(
    *,
    salutation: str,
    language: str,
    mail_state_provider: Callable[[], Awaitable[int | None]] | None,
    calendar_state_provider: Callable[[], Awaitable[int | None]] | None,
    github_state_provider: Callable[[], Awaitable[int | None]] | None,
    openclaw_health_check: Callable[[], Awaitable[bool]] | None,
    system_metrics_provider: Callable[[], Awaitable[tuple[bool, bool]]] | None,
) -> GreetingContext:
    """Best-effort collect runtime state for the greeting.

    Each provider is wrapped in its own try/except — never raises, falls
    back to None / safe defaults so the greeting always renders something.
    """
    unread_mail: int | None = None
    calendar_today: int | None = None
    open_prs: int | None = None
    openclaw_reachable: bool = True
    cpu_ok: bool = True
    ram_ok: bool = True

    if mail_state_provider is not None:
        try:
            unread_mail = await mail_state_provider()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Greeting: mail provider failed: {exc}")

    if calendar_state_provider is not None:
        try:
            calendar_today = await calendar_state_provider()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Greeting: calendar provider failed: {exc}")

    if github_state_provider is not None:
        try:
            open_prs = await github_state_provider()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Greeting: github provider failed: {exc}")

    if openclaw_health_check is not None:
        try:
            openclaw_reachable = await openclaw_health_check()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Greeting: openclaw health check failed: {exc}")
            openclaw_reachable = False

    if system_metrics_provider is not None:
        try:
            cpu_ok, ram_ok = await system_metrics_provider()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Greeting: system metrics provider failed: {exc}")

    return GreetingContext(
        salutation=salutation,
        language=language,
        unread_mail=unread_mail,
        calendar_today=calendar_today,
        open_prs=open_prs,
        openclaw_reachable=openclaw_reachable,
        cpu_ok=cpu_ok,
        ram_ok=ram_ok,
    )
