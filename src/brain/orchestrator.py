"""Orchestrator for JARVIS.

Single-call voice pipeline: a fast local intent classifier decides whether
a turn is a **UI / local command** (PC control, smart-home, system commands
like reset / voice / shutdown) or a **conversational turn**. UI commands run
locally through their dedicated agents — no LLM involved. Conversational
turns go straight to OpenClaw via :meth:`ClaudeClient.chat` — one round-trip,
no routing-model hop.

This replaces the previous two-LLM design (routing model → subagent with its
own LLM call) with at most one LLM call per turn. Persona, factual lookups
and conversational context all live inside the OpenClaw ``jarvis-main``
session (``SOUL.md`` + session memory).
"""

from __future__ import annotations

import asyncio
import datetime
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from integrations.openclaw.ws_client import StreamChunk

if TYPE_CHECKING:
    from brain.conversation_state import ConversationStateMachine
    from brain.device_ledger import DeviceLedger
    from brain.narration_queue import NarrationQueue

from brain.agents.base import AgentResult, BaseAgent
from brain.agents.chat_agent import ChatAgent
from brain.agents.morning_briefing_agent import build_briefing_prompt
from brain.agents.quiet_mode_agent import QuietModeAgent
from brain.agents.search_agent import SearchAgent
from brain.agents.system_agent import SystemAgent
from brain.claude_client import ClaudeClient
from brain.intent_parser import Intent, IntentResult
from utils.config_loader import get_config
from utils.logger import get_logger

# Intents that need Gmail context injected before reaching OpenClaw.
_EMAIL_INTENTS: frozenset[Intent] = frozenset(
    {Intent.EMAIL_READ, Intent.EMAIL_SEARCH, Intent.EMAIL_COMPOSE}
)

# Intents that need Calendar context injected before reaching OpenClaw.
_CALENDAR_INTENTS: frozenset[Intent] = frozenset(
    {
        Intent.CALENDAR_LIST,
        Intent.CALENDAR_CREATE,
        Intent.CALENDAR_UPDATE,
        Intent.CALENDAR_DELETE,
    }
)

# Intents that need Drive context injected before reaching OpenClaw.
_DRIVE_INTENTS: frozenset[Intent] = frozenset({Intent.DRIVE_SEARCH})

logger = get_logger("orchestrator")

# Confidence threshold above which a local-intent classification is
# trusted enough to bypass the conversational path entirely.
_LOCAL_INTENT_CONFIDENCE = 0.7


@dataclass
class OrchestratorDecision:
    """Legacy decision record — kept so the module's public surface
    doesn't change (tests, diagnostics). No longer populated by an LLM
    routing hop — the orchestrator now decides locally.
    """

    agent: str
    task: str
    params: dict[str, Any]
    requires_followup: bool = False
    reasoning: str = ""


# Intents that can be handled locally without any LLM round-trip. Anything
# outside this set falls through to the conversational chat path (OpenClaw).
# PC_CONTROL and SMART_HOME are intentionally absent here: these intents now
# fall through to OpenClaw, which calls the corresponding MCP tools registered
# in api.mcp_tools (issue #76). SystemAgent is retained for shutdown,
# voice-change, and memory-reset — none of which have MCP equivalents.
# Spotify intents (SEARCH, QUEUE, PLAY_CONTEXT, and all transport intents)
# fall through to OpenClaw, which calls the spotify_* MCP tools (issue #87).
# QUIET_MODE_ON / QUIET_MODE_OFF are handled locally by QuietModeAgent (#93).
# WIKI_LOOKUP is handled locally when vault fast-path is enabled (#106).
_LOCAL_INTENTS: frozenset[Intent] = frozenset(
    {
        Intent.SYSTEM,
        Intent.WEB_SEARCH,
        Intent.GREETING,
        Intent.MORNING_BRIEFING,
        Intent.QUIET_MODE_ON,
        Intent.QUIET_MODE_OFF,
        Intent.LEDGER_QUERY,
        Intent.WIKI_LOOKUP,
    }
)


class Orchestrator:
    """Dispatches turns to local agents or to the OpenClaw chat path.

    No routing LLM call is ever made here. A high-confidence match for a
    local intent (PC / smart-home / system) runs the matching agent; every
    other turn is a single ``chat()`` call against OpenClaw.
    """

    def __init__(
        self,
        claude_client: ClaudeClient,
        memory: Any = None,
        tts_engine: Any = None,
        memory_store: Any = None,
        narration_queue: NarrationQueue | None = None,
        state_machine: ConversationStateMachine | None = None,
        device_ledger: DeviceLedger | None = None,
        wiki_client: Any = None,
    ) -> None:
        """Initialise the orchestrator.

        Args:
            claude_client: OpenClaw-backed client used for conversational
                turns (``chat()``). Local agents do not use it.
            memory: Legacy parameter. Retained for call-site compatibility;
                not consulted (OpenClaw owns session memory, and the local
                transcript archive is written directly via
                :class:`brain.memory.MemoryStore` from ``ws_server``).
            tts_engine: TTS engine handle passed through to ``SystemAgent``
                for voice-change commands.
            memory_store: Optional :class:`brain.memory.MemoryStore` instance
                used by ``_handle_greeting`` to read/write the daily-briefing
                played flag.
            narration_queue: Optional :class:`brain.narration_queue.NarrationQueue`
                used for streaming per-block briefing utterances. When provided
                the morning briefing emits an instant ack and streams blocks
                individually; when absent the legacy single-utterance path is used.
            state_machine: Optional :class:`brain.conversation_state.ConversationStateMachine`
                shared with the NarrationQueue and the WS server.
            device_ledger: Optional :class:`brain.device_ledger.DeviceLedger` for
                LEDGER_QUERY fast-path handler.
            wiki_client: Optional :class:`integrations.openclaw.wiki_client.WikiClient`
                for WIKI_LOOKUP fast-path handler (#106).
        """
        self.claude_client = claude_client
        self.memory = memory
        self.tts_engine = tts_engine
        self._memory_store: Any = memory_store
        self._narration_queue: NarrationQueue | None = narration_queue
        self._state_machine: ConversationStateMachine | None = state_machine
        self._device_ledger: DeviceLedger | None = device_ledger
        self._wiki_client: Any = wiki_client  # WikiClient | None

        # Config — retained for backward compatibility, but the old
        # "orchestrator_model" / "skip_on_clear_intent" knobs no longer
        # affect routing: there is no routing LLM call any more.
        cfg = get_config()
        agents_config = cfg.get_section("agents")
        self.orchestrator_model = agents_config.get(
            "orchestrator_model", "claude-opus-4-5"
        )
        self.orchestrator_max_tokens = agents_config.get("orchestrator_max_tokens", 150)
        self.skip_on_clear_intent = agents_config.get(
            "skip_orchestrator_on_clear_intent", True
        )
        self.history_turns_for_orchestrator = agents_config.get(
            "history_turns_for_orchestrator", 3
        )

        self._agents: dict[str, BaseAgent] = {}
        self._init_agents()

    def _init_agents(self) -> None:
        """Wire up local agents.

        PcAgent and SmartHomeAgent are intentionally omitted: those intents
        now fall through to OpenClaw → MCP tools (issue #76).
        SpotifyAgent is removed: all Spotify intents now fall through to
        OpenClaw → spotify_* MCP tools (issue #87).
        QuietModeAgent handles QUIET_MODE_ON / QUIET_MODE_OFF (#93 Phase 2).
        """
        self._agents = {
            "chat": ChatAgent(self.claude_client),
            "search": SearchAgent(self.claude_client),
            "system": SystemAgent(
                self.claude_client, memory=None, tts_engine=self.tts_engine
            ),
            "quiet_mode": QuietModeAgent(self._narration_queue),
        }

    def set_tts_engine(self, tts_engine: Any) -> None:
        """Set the TTS engine on the shared ``SystemAgent`` (late binding)."""
        self.tts_engine = tts_engine
        if "system" in self._agents:
            self._agents["system"].tts_engine = tts_engine

    async def _build_email_context(
        self,
        intent_result: IntentResult,
    ) -> str | None:
        """Fetch Gmail context and format it for injection into the prompt.

        Called only for EMAIL_READ / EMAIL_SEARCH / EMAIL_COMPOSE intents.
        Returns ``None`` when Gmail is disabled or the client call fails
        (the turn is still forwarded to OpenClaw without context rather
        than being aborted).

        Args:
            intent_result: Classified intent with extracted params.

        Returns:
            A short multi-line context string, or ``None`` on failure.
        """
        try:
            cfg = get_config()
            gmail_cfg = cfg.get_section("gmail") or {}
            if not gmail_cfg.get("enabled", False):
                return None

            from integrations.google.gmail_client import (  # noqa: PLC0415
                GmailClientError,
                get_gmail_client,
            )

            vip_senders: list[str] = gmail_cfg.get("vip_senders", [])
            client = get_gmail_client(vip_senders=vip_senders)

            intent = intent_result.intent
            params = intent_result.params
            max_results: int = int(gmail_cfg.get("max_unread_summary", 5))

            if intent == Intent.EMAIL_READ:
                messages = await client.list_unread(max_results=max_results)
                if not messages:
                    return "Context — unread emails: Keine ungelesenen E-Mails."
                lines = [f"Context — unread emails ({len(messages)} of recent):"]
                for msg in messages:
                    lines.append(
                        f"  • [{msg.received_at.strftime('%Y-%m-%d %H:%M')}]"
                        f" From: {msg.sender} <{msg.sender_email}>"
                        f" | Subject: {msg.subject}"
                        f" | Snippet: {msg.snippet[:80]}"
                    )
                return "\n".join(lines)

            elif intent == Intent.EMAIL_SEARCH:
                sender = params.get("sender", "")
                subject = params.get("subject", "")
                query_parts: list[str] = []
                if sender:
                    query_parts.append(f"from:{sender}")
                if subject:
                    query_parts.append(subject)
                query = " ".join(query_parts) if query_parts else "in:inbox"
                messages = await client.search(query, max_results=max_results)
                if not messages:
                    return f"Context — email search '{query}': Keine E-Mails gefunden."
                lines = [f"Context — email search results for '{query}':"]
                for msg in messages:
                    lines.append(
                        f"  • [{msg.received_at.strftime('%Y-%m-%d %H:%M')}]"
                        f" From: {msg.sender} <{msg.sender_email}>"
                        f" | Subject: {msg.subject}"
                        f" | Snippet: {msg.snippet[:80]}"
                    )
                return "\n".join(lines)

            elif intent == Intent.EMAIL_COMPOSE:
                to_hint = params.get("to", "")
                subject_hint = params.get("subject", "")
                parts = ["Context — email compose request:"]
                if to_hint:
                    parts.append(f"  Recipient hint: {to_hint}")
                if subject_hint:
                    parts.append(f"  Subject hint: {subject_hint}")
                parts.append(
                    "  NOTE: Draft an email and ask for explicit confirmation before sending."
                )
                return "\n".join(parts)

        except GmailClientError as exc:
            logger.warning(f"Gmail error during context build: {exc}")
        except Exception as exc:
            logger.warning(f"Unexpected error building email context: {exc}")

        return None

    async def _build_calendar_context(
        self,
        intent_result: IntentResult,
    ) -> str | None:
        """Fetch Calendar context and format it for injection into the prompt.

        Called for all four CALENDAR_* intents. Returns ``None`` when the
        calendar integration is disabled or the client call fails — the turn
        is still forwarded to OpenClaw without context.

        Args:
            intent_result: Classified intent with extracted params.

        Returns:
            A short multi-line context string, or ``None`` on failure.
        """
        try:
            cfg = get_config()
            cal_cfg = cfg.get_section("calendar") or {}
            if not cal_cfg.get("enabled", False):
                return None

            from datetime import datetime, timedelta, timezone  # noqa: PLC0415

            from integrations.google.calendar_client import (  # noqa: PLC0415
                CalendarClientError,
                get_calendar_client,
            )

            lookahead_hours: int = int(cal_cfg.get("lookahead_hours", 48))
            max_results: int = int(cal_cfg.get("max_events_per_query", 20))
            default_duration: int = int(cal_cfg.get("default_event_duration_minutes", 60))

            now = datetime.now(timezone.utc)
            window_end = now + timedelta(hours=lookahead_hours)

            client = get_calendar_client()
            events = await client.list_events(
                calendar_id="primary",
                start=now,
                end=window_end,
                max_results=max_results,
            )

            intent = intent_result.intent
            params = intent_result.params

            if intent == Intent.CALENDAR_LIST:
                if not events:
                    return "Context — calendar: Keine Termine in den nächsten 48 Stunden."
                lines = [f"Context — calendar ({len(events)} upcoming events in next 48h):"]
                for evt in events:
                    if evt.all_day:
                        time_label = "(all day)"
                    else:
                        time_label = evt.start.strftime("%Y-%m-%d %H:%M UTC")
                    loc_str = f" @ {evt.location}" if evt.location else ""
                    lines.append(f"  • [{time_label}] {evt.title}{loc_str} [id={evt.id}]")
                return "\n".join(lines)

            elif intent == Intent.CALENDAR_CREATE:
                # Inject context with current events + hint for date parsing.
                raw_text = params.get("raw_text", intent_result.original_text)
                title_hint = params.get("title", "")
                time_expr = params.get("time_expr", "")

                # Attempt to parse date/time from the original utterance.
                parsed_dt: datetime | None = None
                try:
                    import dateparser  # noqa: PLC0415

                    parsed_dt = dateparser.parse(
                        raw_text,
                        languages=["de", "en"],
                        settings={
                            "PREFER_DATES_FROM": "future",
                            "RETURN_AS_TIMEZONE_AWARE": True,
                        },
                    )
                except Exception as _dp_exc:
                    logger.debug(f"dateparser failed: {_dp_exc}")

                parts = [
                    "Context — calendar create request:",
                    f"  User said: {raw_text}",
                ]
                if title_hint:
                    parts.append(f"  Detected title: {title_hint}")
                if parsed_dt:
                    start_iso = parsed_dt.isoformat()
                    end_iso = (parsed_dt + timedelta(minutes=default_duration)).isoformat()
                    parts.append(f"  Parsed start: {start_iso}")
                    parts.append(f"  Suggested end: {end_iso} (default {default_duration}min)")
                elif time_expr:
                    parts.append(f"  Time expression: {time_expr} (could not parse fully)")
                else:
                    parts.append(
                        "  NOTE: Could not parse a specific date/time. "
                        "Ask the user to clarify, e.g. 'tomorrow at 2pm'."
                    )
                parts.append(
                    "  IMPORTANT: Extract the event title and start/end times "
                    "from the user's request, then confirm before creating."
                )
                return "\n".join(parts)

            elif intent in (Intent.CALENDAR_UPDATE, Intent.CALENDAR_DELETE):
                action = "update" if intent == Intent.CALENDAR_UPDATE else "delete"
                if not events:
                    return (
                        f"Context — calendar {action}: "
                        "No upcoming events found to modify."
                    )
                lines = [
                    f"Context — calendar {action} (upcoming events available to target):"
                ]
                for evt in events:
                    if evt.all_day:
                        time_label = "(all day)"
                    else:
                        time_label = evt.start.strftime("%Y-%m-%d %H:%M UTC")
                    lines.append(
                        f"  • [{time_label}] {evt.title} [id={evt.id}]"
                        + (f" (recurring)" if evt.is_recurring else "")
                    )
                lines.append(
                    f"  NOTE: Identify the target event, confirm the {action} "
                    "action with the user before executing."
                )
                if any(e.is_recurring for e in events):
                    lines.append(
                        "  NOTE: This only affects this occurrence, "
                        "not the full recurring series."
                    )
                return "\n".join(lines)

        except Exception as exc:
            logger.warning(f"Calendar context build failed: {exc}")

        return None

    async def _build_drive_context(
        self,
        intent_result: IntentResult,
    ) -> str | None:
        """Fetch Drive search results and format them for prompt injection.

        Called only for DRIVE_SEARCH intents. Returns ``None`` when Drive is
        disabled or the client call fails — the turn is still forwarded to
        OpenClaw without context rather than being aborted.

        Args:
            intent_result: Classified intent with extracted params.

        Returns:
            A short multi-line context string, or ``None`` on failure.
        """
        try:
            cfg = get_config()
            drive_cfg = cfg.get_section("drive") or {}
            if not drive_cfg.get("enabled", False):
                return None

            from integrations.google.drive_client import (  # noqa: PLC0415
                DriveClientError,
                get_drive_client,
            )

            max_results: int = int(drive_cfg.get("max_results", 10))
            preview_chars: int = int(drive_cfg.get("preview_content_chars", 500))
            scopes: list[str] = drive_cfg.get(
                "scopes", ["https://www.googleapis.com/auth/drive.readonly"]
            )

            client = get_drive_client(scopes=scopes)
            query_hint: str = intent_result.params.get("query", "")

            # Build a Drive query string from the hint.
            if query_hint:
                drive_query = f"fullText contains '{query_hint}' or name contains '{query_hint}'"
            else:
                # No hint — fall back to recent files.
                files = await client.list_recent(max_results=max_results)
                if not files:
                    return "Context — Drive: Keine Dateien gefunden."
                lines = [f"Context — Drive recent files ({len(files)} results):"]
                for f in files[:5]:
                    lines.append(
                        f"  • [{f.modified_time.strftime('%Y-%m-%d')}]"
                        f" {f.name} (id={f.id})"
                    )
                return "\n".join(lines)

            files = await client.search(drive_query, max_results=max_results)
            if not files:
                return (
                    f"Context — Drive search '{query_hint}': Keine Dateien gefunden."
                )

            lines = [f"Context — Drive search '{query_hint}' ({len(files)} results):"]
            for i, f in enumerate(files[:5]):
                lines.append(
                    f"  • [{f.modified_time.strftime('%Y-%m-%d')}]"
                    f" {f.name} (id={f.id})"
                    + (f" — {f.web_view_link}" if f.web_view_link else "")
                )
                # Inject content preview for the top-1 result only.
                if i == 0:
                    try:
                        content = await client.get_file_content(f.id)
                        if content:
                            snippet = content[:preview_chars].strip()
                            if len(content) > preview_chars:
                                snippet += "…"
                            lines.append(f"    Preview: {snippet}")
                    except DriveClientError as exc:
                        logger.debug("Drive content preview failed for {}: {}", f.id, exc)

            return "\n".join(lines)

        except DriveClientError as exc:
            logger.warning("Drive API error during context build: {}", exc)
        except Exception as exc:
            logger.warning("Unexpected error building Drive context: {}", exc)

        return None

    async def _handle_ledger_query(self, language: str) -> AgentResult:
        """Handle a LEDGER_QUERY intent without any LLM or OpenClaw round-trip.

        Queries DeviceLedger.count_since(today 00:00 local time) and returns
        a templated narration string.

        Args:
            language: Detected language (``"en"`` / ``"de"``).

        Returns:
            AgentResult with a spoken templated summary.
        """
        try:
            cfg = get_config()
            tz_name: str = cfg.get("briefing.timezone", "Europe/Zurich")
            try:
                tz = ZoneInfo(tz_name)
            except Exception:
                tz = ZoneInfo("Europe/Zurich")

            now_local = datetime.datetime.now(tz)
            today_midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            since_iso = today_midnight.astimezone(datetime.timezone.utc).isoformat()

            counts: dict[str, int] = {}
            if self._device_ledger is not None:
                counts = await self._device_ledger.count_since(since_iso)
            else:
                logger.warning("LEDGER_QUERY: DeviceLedger not attached to Orchestrator")

            tts = counts.get("tts_emitted", 0)
            ww = counts.get("wake_word", 0)
            mcp = counts.get("mcp_call", 0)
            vstart = counts.get("voice_turn_start", 0)

            if language == "de":
                text = (
                    f"Sir, heute habe ich {ww} Wake-Words, {vstart} Sprach-Turns, "
                    f"{tts} TTS-Ausgaben und {mcp} MCP-Aufrufe aufgezeichnet."
                )
            else:
                text = (
                    f"Sir, today I have logged {ww} wake words, {vstart} voice turns, "
                    f"{tts} TTS emissions, and {mcp} MCP calls."
                )
        except Exception as exc:
            logger.warning(f"LEDGER_QUERY handler error: {exc}")
            text = "Sir, the ledger is unavailable at the moment." if language == "en" else (
                "Sir, das Ledger ist gerade nicht verfügbar."
            )

        return AgentResult(spoken_response=text, success=True)

    async def _handle_wiki_lookup(
        self,
        intent_result: IntentResult,
        language: str,
    ) -> AgentResult | None:
        """Handle a WIKI_LOOKUP intent via the vault fast-path.

        Returns ``None`` to fall through to the OpenClaw slow-path when:
        - fast-path is disabled in config,
        - WikiClient is not attached,
        - vault is empty / unavailable,
        - no hit meets the minimum score threshold.

        Args:
            intent_result: Classified intent containing ``params["topic"]``.
            language: Detected language (``"en"`` / ``"de"``).

        Returns:
            :class:`AgentResult` with a templated spoken response, or ``None``
            to fall through to the OpenClaw agent.
        """
        from integrations.openclaw.wiki_client import WikiClientUnavailableError  # noqa: PLC0415

        cfg = get_config()
        vault_cfg = cfg.get_section("vault") or {}

        if not vault_cfg.get("fast_path_enabled", True):
            logger.debug("WIKI_LOOKUP: fast-path disabled in config — falling through")
            return None

        if self._wiki_client is None:
            logger.debug("WIKI_LOOKUP: no WikiClient attached — falling through")
            return None

        topic: str = intent_result.params.get("topic", "").strip()
        if not topic:
            logger.debug("WIKI_LOOKUP: empty topic extracted — falling through")
            return None

        min_score: float = float(vault_cfg.get("fast_path_min_score", 0.75))

        try:
            hits = await asyncio.wait_for(
                self._wiki_client.search(topic, k=6),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("WIKI_LOOKUP: search timed out — falling through")
            return None
        except WikiClientUnavailableError as exc:
            logger.warning(f"WIKI_LOOKUP: wiki unavailable — falling through: {exc}")
            return None
        except Exception as exc:
            logger.warning(f"WIKI_LOOKUP: unexpected error — falling through: {exc}")
            return None

        qualifying = [h for h in hits if h.score >= min_score]
        if not qualifying:
            logger.debug(
                f"WIKI_LOOKUP: no hits above threshold {min_score:.2f} for topic={topic!r}"
                " — falling through"
            )
            return None

        # Format top 1-3 hits into a narration template.
        top = qualifying[:3]
        if language == "de":
            if len(top) == 1:
                text = (
                    f"Über {topic} habe ich folgendes gefunden: {top[0].title}. "
                    f"{top[0].excerpt[:200]}" if top[0].excerpt else
                    f"Über {topic} habe ich eine Notiz mit dem Titel {top[0].title!r}."
                )
            else:
                titles = ", ".join(h.title for h in top)
                text = (
                    f"Über {topic} habe ich {len(top)} Einträge gefunden: {titles}. "
                    f"Hier der wichtigste: {top[0].excerpt[:200]}" if top[0].excerpt else
                    f"Über {topic} habe ich unter anderem: {titles}."
                )
        else:
            if len(top) == 1:
                text = (
                    f"About {topic}, I found the following: {top[0].title}. "
                    f"{top[0].excerpt[:200]}" if top[0].excerpt else
                    f"About {topic}, I have a note titled {top[0].title!r}."
                )
            else:
                titles = ", ".join(h.title for h in top)
                text = (
                    f"About {topic}, I found {len(top)} entries: {titles}. "
                    f"Top result: {top[0].excerpt[:200]}" if top[0].excerpt else
                    f"About {topic}, I found entries including: {titles}."
                )

        logger.info(
            f"WIKI_LOOKUP fast-path: topic={topic!r} hits={len(qualifying)} "
            f"top_score={top[0].score:.3f}"
        )
        return AgentResult(spoken_response=text, success=True)

    async def _handle_greeting(
        self,
        text: str,
        language: str,
    ) -> AgentResult | None:
        """Handle a GREETING intent: auto-trigger morning briefing once per day.

        Returns an ``AgentResult`` when the briefing fires; returns ``None``
        when the greeting should fall through to the normal chat path (briefing
        already delivered today).

        The time-gate (04:00–12:00 window) is intentionally absent — the spec
        says "first greeting of a given day", not "of a given morning". The
        daily flag alone gates re-firing.

        Args:
            text: Original STT text.
            language: Detected language (``"en"`` / ``"de"``).
        """
        import datetime as _dt
        from zoneinfo import ZoneInfo

        cfg = get_config()
        tz_name: str = cfg.get("briefing.timezone", "Europe/Zurich")
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("Europe/Zurich")

        now_local = _dt.datetime.now(tz)
        date_key = now_local.strftime("%Y-%m-%d")
        flag_key = f"morning_briefing_played_{date_key}"

        # Check daily flag via MemoryStore.
        if self._memory_store is not None:
            try:
                played = await self._memory_store.pref_get(flag_key)
                if played == "true" or played is True:
                    logger.debug(
                        f"Morning briefing already played today ({date_key}); "
                        "falling through to chat"
                    )
                    return None
            except Exception as exc:
                logger.warning(f"Could not read morning briefing flag from MemoryStore: {exc}")
        else:
            logger.warning(
                "No MemoryStore attached to Orchestrator — "
                "cannot check morning briefing daily flag; running briefing anyway"
            )

        logger.debug(
            f"[BRIEFING] Orchestrator dispatching: intent={Intent.GREETING.value}"
            f" → briefing prompt via OpenClaw (daily_flag={date_key})"
        )
        logger.info(f"Auto-triggering morning briefing for {date_key} (GREETING intent)")

        # Set the daily flag eagerly so the briefing does not re-fire if the
        # OpenClaw call fails mid-stream.
        if self._memory_store is not None:
            try:
                await self._memory_store.pref_set(flag_key, "true")
                logger.debug(f"Set morning briefing played flag (eager): {flag_key}")
            except Exception as exc:
                logger.warning(f"Could not set morning briefing flag: {exc}")

        # Signal the caller to invoke _dispatch_briefing by returning a special
        # AgentResult whose ``data`` carries the ``briefing_dispatch`` flag.
        ack_text = (
            "Guten Morgen, Sir. Einen Moment."
            if language == "de"
            else "Good morning, Sir. One moment."
        )
        return AgentResult(
            spoken_response=ack_text,
            success=True,
            data={"briefing_dispatch": True, "language": language},
        )

    async def _dispatch_briefing(self, language: str) -> AsyncIterator[StreamChunk]:
        """Yield an instant-ack chunk, then stream OpenClaw chat with the briefing prompt."""
        ack_text = "Einen Moment, Sir." if language == "de" else "One moment, Sir."
        yield StreamChunk(type="text", run_id="local", new_text=ack_text, full_text=ack_text)

        briefing_prompt = build_briefing_prompt(language)
        from brain.claude_client import _with_language_hint  # noqa: PLC0415

        openclaw = self.claude_client.openclaw
        if openclaw is None:
            response_text = await self.claude_client.chat(briefing_prompt, language=language)
            yield StreamChunk(
                type="final",
                run_id="briefing-fallback",
                new_text=response_text,
                full_text=response_text,
            )
            return

        prompt = _with_language_hint(briefing_prompt, language)
        async for chunk in openclaw.query_agent_stream(prompt):
            yield chunk

    async def process(
        self,
        text: str,
        language: str,
        intent_result: IntentResult | None = None,
    ) -> AgentResult:
        """Dispatch a single user turn.

        Fast path for high-confidence local intents; otherwise straight to
        OpenClaw via ``claude_client.chat``.

        Args:
            text: User input text (STT output).
            language: Detected language (``"en"`` / ``"de"``).
            intent_result: Pre-classified intent (optional).

        Returns:
            ``AgentResult`` ready for the TTS/broadcast stage.
        """
        # --- GREETING: may auto-trigger morning briefing ---------------
        if (
            intent_result is not None
            and intent_result.intent == Intent.GREETING
            and intent_result.confidence >= _LOCAL_INTENT_CONFIDENCE
        ):
            result = await self._handle_greeting(text, language)
            if result is not None:
                if result.data and result.data.get("briefing_dispatch"):
                    # Collect the briefing stream into a single spoken response.
                    lang = result.data.get("language", language)
                    parts: list[str] = []
                    async for chunk in self._dispatch_briefing(lang):
                        if chunk.new_text:
                            parts.append(chunk.new_text)
                    full = "".join(parts)
                    return AgentResult(spoken_response=full, success=True)
                return result
            # Fall through to chat path for greetings when briefing already played.

        # --- MORNING_BRIEFING: manual trigger (always runs, flag not set) --
        if (
            intent_result is not None
            and intent_result.intent == Intent.MORNING_BRIEFING
            and intent_result.confidence >= _LOCAL_INTENT_CONFIDENCE
        ):
            logger.info(
                "Local dispatch: morning_briefing via OpenClaw "
                f"(conf={intent_result.confidence:.2f})"
            )
            parts_mb: list[str] = []
            async for chunk in self._dispatch_briefing(language):
                if chunk.new_text:
                    parts_mb.append(chunk.new_text)
            return AgentResult(spoken_response="".join(parts_mb), success=True)

        # --- LEDGER_QUERY: local fast-path (no LLM, no OpenClaw) --------
        if (
            intent_result is not None
            and intent_result.intent == Intent.LEDGER_QUERY
            and intent_result.confidence >= _LOCAL_INTENT_CONFIDENCE
        ):
            logger.info(
                "Local dispatch: ledger_query fast-path "
                f"(conf={intent_result.confidence:.2f})"
            )
            return await self._handle_ledger_query(language)

        # --- WIKI_LOOKUP: fast-path vault search (no LLM, no OpenClaw) ---
        if (
            intent_result is not None
            and intent_result.intent == Intent.WIKI_LOOKUP
            and intent_result.confidence >= _LOCAL_INTENT_CONFIDENCE
        ):
            logger.info(
                "Local dispatch: wiki_lookup fast-path "
                f"(conf={intent_result.confidence:.2f})"
            )
            result_wl = await self._handle_wiki_lookup(intent_result, language)
            if result_wl is not None:
                return result_wl
            logger.info("WIKI_LOOKUP fast-path miss — falling through to OpenClaw")

        # --- Local UI / action commands -------------------------------
        if (
            intent_result is not None
            and intent_result.intent in _LOCAL_INTENTS
            and intent_result.confidence >= _LOCAL_INTENT_CONFIDENCE
        ):
            agent_name = _intent_to_agent_name(intent_result.intent)
            agent = self._agents.get(agent_name)
            if agent is not None:
                logger.info(
                    f"Local dispatch: {agent_name} "
                    f"(intent={intent_result.intent.value}, "
                    f"conf={intent_result.confidence:.2f})"
                )
                return await agent.run(text, intent_result.params, language)
            logger.warning(
                f"Local intent {intent_result.intent.value} had no agent wired; "
                "falling back to chat path"
            )

        # --- Conversational path (single OpenClaw call) ---------------
        # EMAIL intents fall through here too; we inject Gmail context into
        # the prompt text before forwarding to OpenClaw.
        logger.info(
            "Chat dispatch: jarvis-main session"
            + (
                f" (intent={intent_result.intent.value}, "
                f"conf={intent_result.confidence:.2f})"
                if intent_result is not None
                else ""
            )
        )

        prompt_text = text
        if intent_result is not None and intent_result.intent in _EMAIL_INTENTS:
            email_ctx = await self._build_email_context(intent_result)
            if email_ctx:
                prompt_text = f"{email_ctx}\n\nUser: {text}"
        elif intent_result is not None and intent_result.intent in _CALENDAR_INTENTS:
            cal_ctx = await self._build_calendar_context(intent_result)
            if cal_ctx:
                prompt_text = f"{cal_ctx}\n\nUser: {text}"
        elif intent_result is not None and intent_result.intent in _DRIVE_INTENTS:
            drive_ctx = await self._build_drive_context(intent_result)
            if drive_ctx:
                prompt_text = f"{drive_ctx}\n\nUser: {text}"

        return await self._agents["chat"].run(prompt_text, {}, language)

    async def process_stream(
        self,
        text: str,
        language: str,
        intent_result: IntentResult | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a single user turn through the agent pipeline.

        Local intents (PC / smart-home / system) run their dedicated agent
        and emit a single synthetic ``final`` chunk.  Conversational turns
        delegate to ``openclaw_client.query_agent_stream`` for true streaming.

        Args:
            text: User input text (STT output).
            language: Detected language (``"en"`` / ``"de"``).
            intent_result: Pre-classified intent (optional).

        Yields:
            :class:`~integrations.openclaw.ws_client.StreamChunk` objects.
        """
        # --- GREETING: may auto-trigger morning briefing (stream) ----------
        if (
            intent_result is not None
            and intent_result.intent == Intent.GREETING
            and intent_result.confidence >= _LOCAL_INTENT_CONFIDENCE
        ):
            result = await self._handle_greeting(text, language)
            if result is not None:
                if result.data and result.data.get("briefing_dispatch"):
                    lang = result.data.get("language", language)
                    async for chunk in self._dispatch_briefing(lang):
                        yield chunk
                    return
                yield StreamChunk(
                    type="final",
                    run_id="local",
                    new_text=result.spoken_response,
                    full_text=result.spoken_response,
                )
                return
            # Fall through to chat path if briefing already played today.

        # --- MORNING_BRIEFING: manual trigger (stream) ---------------------
        if (
            intent_result is not None
            and intent_result.intent == Intent.MORNING_BRIEFING
            and intent_result.confidence >= _LOCAL_INTENT_CONFIDENCE
        ):
            logger.info(
                "Local dispatch (stream): morning_briefing via OpenClaw "
                f"(conf={intent_result.confidence:.2f})"
            )
            async for chunk in self._dispatch_briefing(language):
                yield chunk
            return

        # --- LEDGER_QUERY: local fast-path (stream) ----------------------
        if (
            intent_result is not None
            and intent_result.intent == Intent.LEDGER_QUERY
            and intent_result.confidence >= _LOCAL_INTENT_CONFIDENCE
        ):
            logger.info(
                "Local dispatch (stream): ledger_query fast-path "
                f"(conf={intent_result.confidence:.2f})"
            )
            result_lq = await self._handle_ledger_query(language)
            yield StreamChunk(
                type="final",
                run_id="local",
                new_text=result_lq.spoken_response,
                full_text=result_lq.spoken_response,
            )
            return

        # --- WIKI_LOOKUP: fast-path vault search (no LLM, no OpenClaw) --
        if (
            intent_result is not None
            and intent_result.intent == Intent.WIKI_LOOKUP
            and intent_result.confidence >= _LOCAL_INTENT_CONFIDENCE
        ):
            logger.info(
                "Local dispatch (stream): wiki_lookup fast-path "
                f"(conf={intent_result.confidence:.2f})"
            )
            result_wl = await self._handle_wiki_lookup(intent_result, language)
            if result_wl is not None:
                yield StreamChunk(
                    type="final",
                    run_id="local",
                    new_text=result_wl.spoken_response,
                    full_text=result_wl.spoken_response,
                )
                return
            # Fall through to OpenClaw slow-path when fast-path returns None.
            logger.info("WIKI_LOOKUP fast-path miss — falling through to OpenClaw")

        # --- Local UI / action commands (no streaming, single result) ----
        if (
            intent_result is not None
            and intent_result.intent in _LOCAL_INTENTS
            and intent_result.confidence >= _LOCAL_INTENT_CONFIDENCE
        ):
            agent_name = _intent_to_agent_name(intent_result.intent)
            agent = self._agents.get(agent_name)
            if agent is not None:
                logger.info(
                    f"Local dispatch (stream): {agent_name} "
                    f"(intent={intent_result.intent.value}, "
                    f"conf={intent_result.confidence:.2f})"
                )
                result = await agent.run(text, intent_result.params, language)
                yield StreamChunk(
                    type="final",
                    run_id="local",
                    new_text=result.spoken_response,
                    full_text=result.spoken_response,
                )
                return
            logger.warning(
                f"Local intent {intent_result.intent.value} had no agent wired; "
                "falling back to chat path"
            )

        # --- Conversational path (OpenClaw WS streaming) -----------------
        # EMAIL intents fall through here; Gmail context is injected into the
        # prompt before streaming.
        logger.info(
            "Chat dispatch (stream): jarvis-main session"
            + (
                f" (intent={intent_result.intent.value}, "
                f"conf={intent_result.confidence:.2f})"
                if intent_result is not None
                else ""
            )
        )

        from brain.claude_client import _with_language_hint  # noqa: PLC0415

        prompt_text = text
        if intent_result is not None and intent_result.intent in _EMAIL_INTENTS:
            email_ctx = await self._build_email_context(intent_result)
            if email_ctx:
                prompt_text = f"{email_ctx}\n\nUser: {text}"
        elif intent_result is not None and intent_result.intent in _CALENDAR_INTENTS:
            cal_ctx = await self._build_calendar_context(intent_result)
            if cal_ctx:
                prompt_text = f"{cal_ctx}\n\nUser: {text}"
        elif intent_result is not None and intent_result.intent in _DRIVE_INTENTS:
            drive_ctx = await self._build_drive_context(intent_result)
            if drive_ctx:
                prompt_text = f"{drive_ctx}\n\nUser: {text}"

        openclaw = self.claude_client.openclaw
        if openclaw is None:
            # Fallback: run one-shot chat and emit final chunk.
            response_text = await self.claude_client.chat(prompt_text, language=language)
            yield StreamChunk(
                type="final",
                run_id="chat-fallback",
                new_text=response_text,
                full_text=response_text,
            )
            return

        prompt = _with_language_hint(prompt_text, language)
        async for chunk in openclaw.query_agent_stream(prompt):
            yield chunk

    def get_agent(self, name: str) -> BaseAgent | None:
        """Return a specific agent by name (``chat`` / ``pc`` / …)."""
        return self._agents.get(name)


def _intent_to_agent_name(intent: Intent) -> str:
    """Map a classified intent to the local agent key.

    PC_CONTROL, SMART_HOME, and all Spotify intents are not in _LOCAL_INTENTS;
    they fall through to the OpenClaw chat path which calls MCP tools
    (issue #76 for PC/home, issue #87 for Spotify).
    GREETING is not mapped here — it is handled by ``_handle_greeting`` in the
    orchestrator directly (may fall through to chat).
    QUIET_MODE_ON / QUIET_MODE_OFF route to the QuietModeAgent (#93 Phase 2).
    LEDGER_QUERY is handled directly by the orchestrator — no agent needed.
    """
    if intent == Intent.SYSTEM:
        return "system"
    if intent == Intent.WEB_SEARCH:
        return "search"
    if intent in (Intent.QUIET_MODE_ON, Intent.QUIET_MODE_OFF):
        return "quiet_mode"
    return "chat"
