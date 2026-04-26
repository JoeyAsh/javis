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

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from integrations.openclaw.ws_client import StreamChunk

from brain.agents.base import AgentResult, BaseAgent
from brain.agents.chat_agent import ChatAgent
from brain.agents.search_agent import SearchAgent
from brain.agents.spotify_agent import SpotifyAgent
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
# Spotify extended intents (SEARCH, QUEUE, PLAY_CONTEXT) run locally via
# SpotifyAgent — they never go through OpenClaw (issue #58).
_LOCAL_INTENTS: frozenset[Intent] = frozenset(
    {
        Intent.SYSTEM,
        Intent.WEB_SEARCH,
        Intent.SPOTIFY_SEARCH,
        Intent.SPOTIFY_QUEUE,
        Intent.SPOTIFY_PLAY_CONTEXT,
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
        spotify_client: Any = None,
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
            spotify_client: Optional SpotifyClient instance used to wire
                ``SpotifyAgent`` for the three Spotify extended intents.
                When ``None``, those intents fall through to the chat path.
        """
        self.claude_client = claude_client
        self.memory = memory
        self.tts_engine = tts_engine
        self.spotify_client = spotify_client

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
        SpotifyAgent is wired when a spotify_client is provided (issue #58).
        """
        self._agents = {
            "chat": ChatAgent(self.claude_client),
            "search": SearchAgent(self.claude_client),
            "system": SystemAgent(
                self.claude_client, memory=None, tts_engine=self.tts_engine
            ),
        }
        if self.spotify_client is not None:
            self._agents["spotify"] = SpotifyAgent(self.spotify_client)
            logger.info("SpotifyAgent wired into orchestrator")

    def set_tts_engine(self, tts_engine: Any) -> None:
        """Set the TTS engine on the shared ``SystemAgent`` (late binding)."""
        self.tts_engine = tts_engine
        if "system" in self._agents:
            self._agents["system"].tts_engine = tts_engine

    def set_spotify_client(self, spotify_client: Any) -> None:
        """Wire (or replace) the SpotifyAgent with a new client (late binding).

        Called from ``ws_server`` after Spotify initialisation completes,
        since Spotify init runs after orchestrator construction.

        Args:
            spotify_client: Authenticated SpotifyClient instance.
        """
        self.spotify_client = spotify_client
        if spotify_client is not None:
            self._agents["spotify"] = SpotifyAgent(spotify_client)
            logger.info("SpotifyAgent wired into orchestrator (late binding)")
        else:
            self._agents.pop("spotify", None)
            logger.info("SpotifyAgent removed from orchestrator")

    def set_preferred_spotify_device(self, device_id: str | None) -> None:
        """Forward the HUD's announced Spotify device ID to the SpotifyAgent.

        Called from ``ws_server`` when a ``spotify_device_announce`` WS message
        is received so that subsequent voice-path play commands target the HUD.

        Args:
            device_id: Spotify Connect device ID, or ``None`` to clear.
        """
        agent = self._agents.get("spotify")
        if agent is None:
            logger.debug(
                "set_preferred_spotify_device: SpotifyAgent not wired — ignoring"
            )
            return
        if device_id:
            logger.info(f"Orchestrator: preferred Spotify device set to {device_id!r}")
        else:
            logger.info("Orchestrator: preferred Spotify device cleared")
        agent.set_preferred_device(device_id)  # type: ignore[union-attr]

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
                # SpotifyAgent branches on task=intent_name, not the raw utterance.
                task_arg = (
                    intent_result.intent.value.upper()
                    if agent_name == "spotify"
                    else text
                )
                return await agent.run(task_arg, intent_result.params, language)
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
        from integrations.openclaw.ws_client import StreamChunk  # local import

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
                # SpotifyAgent branches on task=intent_name, not the raw utterance.
                task_arg = (
                    intent_result.intent.value.upper()
                    if agent_name == "spotify"
                    else text
                )
                result = await agent.run(task_arg, intent_result.params, language)
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

        from brain.claude_client import _with_language_hint  # local import

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

    PC_CONTROL and SMART_HOME are no longer in _LOCAL_INTENTS; they fall
    through to the OpenClaw chat path which calls MCP tools (issue #76).
    Spotify extended intents map to "spotify" (issue #58).
    """
    if intent == Intent.SYSTEM:
        return "system"
    if intent == Intent.WEB_SEARCH:
        return "search"
    if intent in (
        Intent.SPOTIFY_SEARCH,
        Intent.SPOTIFY_QUEUE,
        Intent.SPOTIFY_PLAY_CONTEXT,
    ):
        return "spotify"
    return "chat"
