"""Morning briefing agent for JARVIS.

Collects weather, calendar, commute, mail, and news in parallel and
synthesises a single spoken script + HUD payload.  Each data block is
fetched with an individual timeout; a failing block is silently skipped
so the overall briefing always completes.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any
from zoneinfo import ZoneInfo

from brain.agents.base import AgentResult, BaseAgent
from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("morning_briefing_agent")


class MorningBriefingAgent(BaseAgent):
    """Gather and narrate the daily morning briefing.

    Fetches five data blocks (weather, calendar, commute, mail, news) in
    parallel with a hard 5-second aggregate timeout.  Any block that fails
    or times out contributes ``None`` to the result — the briefing is always
    delivered, even if every block fails.
    """

    def __init__(self) -> None:
        """Initialise without any injected dependencies."""
        super().__init__()

    async def run(
        self,
        task: str,
        params: dict[str, Any],
        language: str,
    ) -> AgentResult:
        """Execute the morning briefing.

        Args:
            task: Original STT text (unused for content; kept for interface).
            params: Supports ``{"manual": True}`` to suppress the daily flag
                and change the greeting prefix.
            language: ``"de"`` or ``"en"``.

        Returns:
            ``AgentResult`` with spoken script, success flag, and structured
            HUD payload.
        """
        cfg = get_config()
        is_manual: bool = bool(params.get("manual", False))

        enabled: bool = bool(cfg.get("briefing.enabled", True))
        if not enabled:
            msg = (
                "Das Briefing ist deaktiviert."
                if language == "de"
                else "The briefing is disabled."
            )
            return AgentResult(spoken_response=msg, success=False, data={})

        tz_name: str = cfg.get("briefing.timezone", "Europe/Zurich")
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("Europe/Zurich")

        now = datetime.datetime.now(tz)
        generated_at = now.isoformat()

        # Gather all blocks with a global timeout.
        tasks = [
            self._fetch_weather(cfg, language),
            self._fetch_calendar(cfg, language, tz, now),
            self._fetch_commute(cfg),
            self._fetch_mail(cfg, language, tz, now),
            self._fetch_news(cfg),
        ]

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Morning briefing gather timed out after 5 s; using partial results")
            results = [None, None, None, None, None]

        # Unpack — each result is the block dict or None (or an Exception).
        weather_block: dict[str, Any] | None = _safe_block(results[0], "weather")
        events_block: list[dict[str, Any]] | None = _safe_block(results[1], "calendar")
        commute_block: dict[str, Any] | None = _safe_block(results[2], "commute")
        mails_block: list[dict[str, Any]] | None = _safe_block(results[3], "mail")
        headlines_block: list[dict[str, Any]] | None = _safe_block(results[4], "news")

        # Build HUD payload.
        payload: dict[str, Any] = {
            "weather": weather_block,
            "events": events_block or [],
            "commute": commute_block,
            "mails": mails_block or [],
            "headlines": headlines_block or [],
            "generatedAt": generated_at,
            "language": language,
        }

        # Broadcast to HUD before returning so the card lights up with TTS.
        await self._broadcast(payload)

        # Compose spoken script.
        script = self._compose_script(
            language=language,
            is_manual=is_manual,
            weather=weather_block,
            events=events_block,
            commute=commute_block,
            mails=mails_block,
            headlines=headlines_block,
        )

        return AgentResult(
            spoken_response=script,
            success=True,
            data={"payload": payload, "manual": is_manual},
        )

    # -----------------------------------------------------------------------
    # Block fetchers
    # -----------------------------------------------------------------------

    async def _fetch_weather(
        self, cfg: Any, language: str
    ) -> dict[str, Any] | None:
        """Fetch weather from Open-Meteo."""
        try:
            from integrations.weather.client import WeatherClient  # noqa: PLC0415

            lat: float = float(cfg.get("briefing.weather.location.lat", 47.37))
            lon: float = float(cfg.get("briefing.weather.location.lon", 8.54))
            client = WeatherClient()
            return await client.get_current_and_today(lat, lon, language=language)
        except Exception as exc:
            logger.warning(f"Weather block failed: {exc}")
            return None

    async def _fetch_calendar(
        self,
        cfg: Any,
        language: str,
        tz: ZoneInfo,
        now: datetime.datetime,
    ) -> list[dict[str, Any]] | None:
        """Fetch today's upcoming calendar events."""
        try:
            from integrations.google.calendar_client import (  # noqa: PLC0415
                CalendarClientError,
                get_calendar_client,
            )

            client = get_calendar_client()

            # Window: now → midnight tonight (local).
            midnight_local = now.replace(hour=23, minute=59, second=59, microsecond=0)
            midnight_utc = midnight_local.astimezone(datetime.timezone.utc)
            now_utc = now.astimezone(datetime.timezone.utc)

            events = await client.list_events(
                calendar_id="primary",
                start=now_utc,
                end=midnight_utc,
                max_results=5,
            )

            # Filter out events that have already ended.
            future_events = [e for e in events if e.end > now_utc][:2]
            if not future_events:
                return None

            result: list[dict[str, Any]] = []
            for evt in future_events:
                start_local = evt.start.astimezone(tz)
                result.append(
                    {
                        "start": evt.start.isoformat(),
                        "title": evt.title,
                        "startHHMM": start_local.strftime("%H:%M"),
                    }
                )
            return result
        except CalendarClientError as exc:
            logger.warning(f"Calendar block failed (CalendarClientError): {exc}")
            return None
        except Exception as exc:
            logger.warning(f"Calendar block failed: {exc}")
            return None

    async def _fetch_commute(self, cfg: Any) -> dict[str, Any] | None:
        """Fetch commute summary (stub for MVP)."""
        try:
            from integrations.commute.client import CommuteClient  # noqa: PLC0415

            from_addr: str = cfg.get("briefing.commute.from", "") or ""
            to_addr: str = cfg.get("briefing.commute.to", "") or ""

            if not from_addr.strip() or not to_addr.strip():
                return None

            mode: str = cfg.get("briefing.commute.mode", "auto") or "auto"
            client = CommuteClient()
            return await client.get_summary(from_=from_addr, to=to_addr, mode=mode)
        except Exception as exc:
            logger.warning(f"Commute block failed: {exc}")
            return None

    async def _fetch_mail(
        self,
        cfg: Any,
        language: str,
        tz: ZoneInfo,
        now: datetime.datetime,
    ) -> list[dict[str, Any]] | None:
        """Fetch important unread mails since local midnight."""
        try:
            from integrations.google.gmail_client import (  # noqa: PLC0415
                GmailClientError,
                get_gmail_client,
            )

            gmail_cfg = cfg.get_section("gmail") or {}
            if not gmail_cfg.get("enabled", False):
                return None

            max_items: int = int(cfg.get("briefing.mail.max_items", 3))
            vip_domains: list[str] = cfg.get("briefing.mail.vip_domains") or []
            vip_senders: list[str] = gmail_cfg.get("vip_senders", [])

            client = get_gmail_client(vip_senders=vip_senders)

            # Search: unread in inbox since local midnight.
            midnight_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
            midnight_utc = midnight_local.astimezone(datetime.timezone.utc)
            after_ts = int(midnight_utc.timestamp())

            query = (
                f"is:unread in:inbox after:{after_ts} "
                "-category:promotions -category:social"
            )
            messages = await client.search(query, max_results=20)

            if not messages:
                return None

            # Rank: IMPORTANT label first, then VIP domain, then recency.
            def _rank(msg: Any) -> tuple[int, int, float]:
                domain = msg.sender_email.split("@")[-1] if "@" in msg.sender_email else ""
                is_important = 0  # gog doesn't expose labels on search; treat all equal
                is_vip_domain = 1 if domain in vip_domains else 0
                ts = msg.received_at.timestamp() if msg.received_at else 0.0
                return (-is_important, -is_vip_domain, -ts)

            ranked = sorted(messages, key=_rank)[:max_items]

            result: list[dict[str, Any]] = []
            for msg in ranked:
                result.append(
                    {
                        "sender": msg.sender,
                        "subject": msg.subject,
                        "receivedAt": msg.received_at.isoformat(),
                    }
                )
            return result if result else None
        except GmailClientError as exc:
            logger.warning(f"Mail block failed (GmailClientError): {exc}")
            return None
        except Exception as exc:
            logger.warning(f"Mail block failed: {exc}")
            return None

    async def _fetch_news(self, cfg: Any) -> list[dict[str, Any]] | None:
        """Fetch top headlines from the configured RSS source."""
        try:
            from integrations.news.client import NewsClient  # noqa: PLC0415

            source_url: str = cfg.get(
                "briefing.news.source", "https://www.srf.ch/news/bnf/rss/1646"
            )
            max_items: int = int(cfg.get("briefing.news.max_items", 3))

            if not source_url:
                return None

            client = NewsClient()
            return await client.fetch_top_headlines(source_url, max_items=max_items)
        except Exception as exc:
            logger.warning(f"News block failed: {exc}")
            return None

    # -----------------------------------------------------------------------
    # HUD broadcast
    # -----------------------------------------------------------------------

    @staticmethod
    async def _broadcast(payload: dict[str, Any]) -> None:
        """Broadcast the briefing payload to the HUD via ws_server."""
        try:
            from api.ws_server import broadcast_morning_briefing  # noqa: PLC0415

            await broadcast_morning_briefing(payload)
        except Exception as exc:
            logger.warning(f"broadcast_morning_briefing failed: {exc}")

    # -----------------------------------------------------------------------
    # Script composition
    # -----------------------------------------------------------------------

    def _compose_script(
        self,
        language: str,
        is_manual: bool,
        weather: dict[str, Any] | None,
        events: list[dict[str, Any]] | None,
        commute: dict[str, Any] | None,
        mails: list[dict[str, Any]] | None,
        headlines: list[dict[str, Any]] | None,
    ) -> str:
        """Compose the spoken briefing script from available data blocks.

        Args:
            language: ``"de"`` or ``"en"``.
            is_manual: When ``True`` uses a neutral prefix instead of "Guten Morgen".
            weather: Weather dict or ``None``.
            events: List of event dicts or ``None``.
            commute: Commute dict or ``None``.
            mails: List of mail dicts or ``None``.
            headlines: List of headline dicts or ``None``.

        Returns:
            A single spoken-word string ready for TTS.
        """
        parts: list[str] = []

        de = language == "de"

        # Greeting prefix.
        if de:
            parts.append("Hier ist Ihr Briefing. " if is_manual else "Guten Morgen. ")
        else:
            parts.append("Here is your briefing. " if is_manual else "Good morning. ")

        has_any = bool(weather or events or commute or mails or headlines)
        if not has_any:
            if de:
                parts.append("Heute habe ich leider keine Daten zur Hand.")
            else:
                parts.append("I'm afraid I have no data available today.")
            return "".join(parts)

        # Weather block.
        if weather:
            label = "Zum Wetter: " if de else "Weather: "
            cond = weather.get("condition", "")
            high = weather.get("high", "")
            low = weather.get("low", "")
            loc = weather.get("location", "")
            if de:
                detail = (
                    f"Heute in {loc}: {cond}, Höchstwert {high} Grad, "
                    f"Tiefstwert {low} Grad."
                )
            else:
                detail = (
                    f"Today in {loc}: {cond}, high of {high} degrees, "
                    f"low of {low} degrees."
                )
            parts.append(label + detail + " ")

        # Calendar block.
        if events:
            label = "Ihre Termine: " if de else "Your schedule: "
            event_strs: list[str] = []
            for i, evt in enumerate(events):
                hhmm = evt.get("startHHMM", "")
                title = evt.get("title", "")
                if de:
                    event_strs.append(f"um {hhmm} {title}")
                else:
                    event_strs.append(f"at {hhmm} {title}")

            if len(event_strs) == 1:
                detail = event_strs[0] + "."
            else:
                connector = ", danach " if de else ", then "
                detail = event_strs[0] + connector + event_strs[1] + "."
            parts.append(label + detail + " ")

        # Commute block.
        if commute:
            label = "Auf der Strasse: " if de else "Commute: "
            summary = commute.get("summary", "")
            dur = commute.get("durationMinutes")
            if summary:
                detail = summary + "."
            elif dur is not None:
                detail = f"{dur} Minuten." if de else f"{dur} minutes."
            else:
                detail = "Keine Informationen." if de else "No information."
            parts.append(label + detail + " ")

        # Mail block.
        if mails:
            label = "Wichtige Mails: " if de else "Important mail: "
            mail_strs: list[str] = []
            for m in mails:
                sender = m.get("sender", "")
                subject = m.get("subject", "")
                if de:
                    mail_strs.append(f"{sender} zu „{subject}“")
                else:
                    mail_strs.append(f"{sender} on „{subject}“")
            detail = "; ".join(mail_strs) + "."
            parts.append(label + detail + " ")

        # Headlines block.
        if headlines:
            label = "Schlagzeilen: " if de else "Headlines: "
            titles = [h.get("title", "") for h in headlines if h.get("title")]
            detail = ". ".join(titles) + "."
            parts.append(label + detail)

        return "".join(parts).strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_block(result: Any, name: str) -> Any:
    """Return the result value, or ``None`` if it is an exception."""
    if isinstance(result, BaseException):
        logger.warning(f"Morning briefing block '{name}' raised: {result}")
        return None
    return result
