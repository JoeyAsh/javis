"""LLM client for JARVIS — OpenClaw-backed.

Despite the historical module name ``claude_client``, this module no longer
talks to the Anthropic SDK directly. All conversational turns and utility
LLM calls are routed through the OpenClaw gateway (``OpenClawClient``),
which owns authentication (``claude login``), persistent session memory,
and third-party integrations.

Two logical session lanes are used:

- **Conversational lane** — the shared session id from
  ``config.openclaw.session_id`` (default ``"jarvis-main"``). Persona and
  long-term memory live here; OpenClaw keeps context across turns and
  reads ``~/.openclaw/workspace/SOUL.md`` for the JARVIS persona.
- **Utility lane** — per-call ephemeral session ids
  (``jarvis-util-<purpose>``). Used for orchestrator routing decisions,
  search-result summarisation and other short, stateless JSON/text calls
  that must NOT pollute the main conversation memory.

The public ``ClaudeClient`` surface (``chat``, ``complete``,
``chat_with_json``) is preserved so that ``orchestrator.py``, ``agents/*``
and ``ws_server.py`` keep working without modification.
"""

from __future__ import annotations

import json
from typing import Any

from integrations.openclaw import AgentResponse, OpenClawClient
from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("claude_client")

# JARVIS personality system prompt. OpenClaw auto-loads
# ``~/.openclaw/workspace/SOUL.md`` at agent boot, so the persona block is
# intentionally NOT injected as a system prompt any more. We keep the
# constant exported for backward compatibility (tests, diagnostics) but
# it's no longer prepended to outbound requests — that would double-prompt.
JARVIS_SYSTEM_PROMPT = """You are JARVIS (Just A Rather Very Intelligent System), the AI assistant from Iron Man.
You have the personality of Tony Stark's AI: British butler elegance with understated dry wit.
Address the user as "sir" naturally and sparingly — not in every sentence.

CRITICAL RESPONSE RULES:
- ONE sentence is ideal. TWO is the absolute maximum for any spoken response. Never three.
- No markdown, no bullet points, no headers, no code blocks in voice responses.
- No filler phrases: never say "Absolutely", "Great question", "I'd be happy to", "Of course",
  "How can I help", "Is there anything else", "I apologize", or "As an AI".
- Confirm actions briefly: "Done, sir." / "On it." / "Will do, sir."
- Dry wit is welcome, but keep it sharp and brief.

Always respond in the same language the user spoke."""

# Fallback responses for error cases — used when OpenClaw errors mid-turn.
FALLBACK_RESPONSES: dict[str, str] = {
    "en": (
        "I apologize, sir, but I'm experiencing technical difficulties. "
        "Please try again in a moment."
    ),
    "de": (
        "Ich bitte um Entschuldigung, aber ich habe momentan technische "
        "Schwierigkeiten. Bitte versuchen Sie es in einem Moment erneut."
    ),
}


# Prefix for ephemeral utility session ids. Keeping them distinct from the
# main conversation session avoids polluting JARVIS's long-term memory
# with machine-formatted routing/JSON exchanges.
_UTILITY_SESSION_PREFIX = "jarvis-util"


class ClaudeClient:
    """LLM client routed through the OpenClaw gateway.

    The class name is preserved for call-site compatibility — in reality
    every request lands on ``OpenClawClient.query_agent``. The Anthropic
    SDK is no longer touched at runtime.

    Attributes:
        model: Historical field, kept for logging/introspection. The
            actual model is selected by the OpenClaw gateway based on
            ``config.openclaw.agent_model``.
        max_tokens: Retained for backward-compatible tests. OpenClaw
            currently does not honour this — response length is shaped
            by the persona in SOUL.md and by turn-level prompt hints.
        temperature: Same note as ``max_tokens``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 300,
        temperature: float = 0.7,
        openclaw_client: OpenClawClient | None = None,
    ) -> None:
        """Initialise the LLM client.

        Args:
            api_key: Legacy parameter, ignored. Authentication is owned
                by the OpenClaw gateway (``claude login``).
            model: Informational only — recorded in logs. See the class
                docstring.
            max_tokens: Informational only.
            temperature: Informational only.
            openclaw_client: Pre-constructed OpenClaw client. If ``None``,
                a new one will be created from config during
                ``initialize()``.
        """
        del api_key  # No longer used; kept in signature for compatibility.
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._openclaw: OpenClawClient | None = openclaw_client
        self._owns_openclaw: bool = openclaw_client is None

    @property
    def openclaw(self) -> OpenClawClient | None:
        """Return the underlying OpenClaw client (or ``None`` pre-init)."""
        return self._openclaw

    async def initialize(self) -> None:
        """Initialise the underlying OpenClaw client.

        Creates an ``OpenClawClient`` from ``config.openclaw`` if one was
        not supplied at construction, and calls its ``initialize()`` so
        the gateway connection is verified (or degraded-gracefully if the
        daemon isn't running).
        """
        if self._openclaw is not None and not self._owns_openclaw:
            logger.debug("LLM client using pre-supplied OpenClaw client")
            return

        cfg = get_config()
        openclaw_config = cfg.get_section("openclaw")

        if self._openclaw is None:
            self._openclaw = OpenClawClient(openclaw_config)

        await self._openclaw.initialize()
        logger.info(
            f"LLM client ready (route=OpenClaw, gateway={self._openclaw.gateway_url}, "
            f"session={self._openclaw.session_id})"
        )

    async def close(self) -> None:
        """Close the underlying OpenClaw client if we own it."""
        if self._openclaw is not None and self._owns_openclaw:
            await self._openclaw.close()
            self._openclaw = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _query(
        self,
        message: str,
        session_id: str | None = None,
        thinking: str | None = None,
    ) -> AgentResponse:
        """Send a prompt to OpenClaw and return the raw ``AgentResponse``.

        Raises no exceptions — OpenClaw errors surface as ``response.error``.
        """
        if self._openclaw is None:
            await self.initialize()

        assert self._openclaw is not None  # for type-checker

        return await self._openclaw.query_agent(
            message=message,
            session_id=session_id,
            thinking=thinking,
        )

    def _utility_session_id(self, purpose: str) -> str:
        """Build an ephemeral session id for a utility call."""
        return f"{_UTILITY_SESSION_PREFIX}-{purpose}"

    def _fallback_text(self, language: str) -> str:
        """Return the localised spoken fallback message."""
        if self._openclaw is not None:
            return self._openclaw.get_offline_fallback_message(language)
        return FALLBACK_RESPONSES.get(language, FALLBACK_RESPONSES["en"])

    # ------------------------------------------------------------------
    # Public API — preserved for existing callers
    # ------------------------------------------------------------------

    async def chat(
        self,
        message: str,
        language: str = "en",
        history: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Send a conversational turn and return JARVIS's response.

        Routes through the main OpenClaw session so the agent runtime owns
        multi-turn memory. ``history`` and ``system_prompt`` are accepted
        for backward compatibility but ignored: OpenClaw stores its own
        history keyed by ``session_id`` and the persona lives in SOUL.md.

        Args:
            message: User message.
            language: Response language (``"en"``/``"de"``). Appended as a
                per-turn hint so OpenClaw answers in the right language.
            history: Ignored. Kept in signature for call-site compat.
            system_prompt: Ignored. Kept in signature for call-site compat.

        Returns:
            JARVIS's spoken response text, or a localised fallback on
            OpenClaw error.
        """
        del history, system_prompt  # Intentionally ignored — see docstring.

        prompt = _with_language_hint(message, language)
        response = await self._query(prompt)

        if response.error or not response.text:
            logger.error(
                f"OpenClaw chat error: {response.error or 'empty response'}"
            )
            return self._fallback_text(language)

        logger.debug(f"OpenClaw chat response: {response.text[:100]}...")
        return response.text

    async def complete(
        self,
        prompt: str,
        system_prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Run a narrow utility completion (routing, summarisation, etc.).

        Utility calls travel on an ephemeral session id so they don't leak
        into the main conversation memory. ``system_prompt`` is folded
        into the user message so OpenClaw (which ignores our system slot)
        still sees the instruction.

        Args:
            prompt: User prompt / payload.
            system_prompt: Instructional prompt. Prepended to ``prompt``.
            model: Historical override, ignored — OpenClaw picks the model.
            max_tokens: Historical override, ignored.
            temperature: Historical override, ignored.

        Returns:
            Response text, or empty string on OpenClaw error.
        """
        del model, max_tokens, temperature  # OpenClaw-governed now.

        composite = _compose_utility_prompt(system_prompt, prompt)
        session = self._utility_session_id("complete")
        response = await self._query(composite, session_id=session)

        if response.error:
            logger.error(f"OpenClaw complete error: {response.error}")
            return ""

        return response.text

    async def chat_with_json(
        self,
        message: str,
        system_prompt: str,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Utility completion expected to return JSON.

        Used by the orchestrator to parse routing decisions. Runs on the
        utility lane for the same reasons as ``complete()``.

        Args:
            message: User prompt / payload.
            system_prompt: Instructional prompt (should tell the model
                to return JSON only).
            max_tokens: Historical override, ignored.

        Returns:
            Parsed JSON object, or an empty dict on error / parse failure.
        """
        del max_tokens  # OpenClaw-governed.

        composite = _compose_utility_prompt(
            system_prompt + "\n\nReturn ONLY valid JSON, no prose, no code fence.",
            message,
        )
        session = self._utility_session_id("json")
        response = await self._query(composite, session_id=session)

        if response.error or not response.text:
            logger.error(
                f"OpenClaw chat_with_json error: {response.error or 'empty'}"
            )
            return {}

        text = response.text.strip()
        # Trim accidental code fences — OpenClaw sometimes wraps JSON.
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse OpenClaw JSON response: {exc}")
            return {}


# ----------------------------------------------------------------------
# Module helpers
# ----------------------------------------------------------------------


def _with_language_hint(message: str, language: str) -> str:
    """Append a terse language hint so OpenClaw answers in the right lang.

    SOUL.md already instructs JARVIS to mirror the user's language, but a
    one-line reminder is cheap insurance.
    """
    hint = "[respond in German]" if language == "de" else "[respond in English]"
    return f"{hint}\n\n{message}"


def _compose_utility_prompt(system_prompt: str, user_prompt: str) -> str:
    """Fold system + user prompts into a single payload for OpenClaw.

    OpenClaw's ``query_agent`` currently takes a single ``message``
    string; it does not expose a separate system slot. We bracket the
    instructional block so the model can tell them apart.
    """
    return (
        "[[SYSTEM INSTRUCTION]]\n"
        f"{system_prompt.strip()}\n"
        "[[END SYSTEM INSTRUCTION]]\n\n"
        f"{user_prompt.strip()}"
    )


async def create_claude_client(
    config: dict[str, Any] | None = None,
    openclaw_client: OpenClawClient | None = None,
) -> ClaudeClient:
    """Factory for :class:`ClaudeClient` — preserves historical signature.

    Args:
        config: Optional Claude configuration (for ``model`` metadata).
            If ``None``, loaded from the global config. The LLM route is
            always OpenClaw regardless of this value.
        openclaw_client: Inject an existing client (e.g. one shared by
            several subsystems). If ``None`` a fresh one is created.

    Returns:
        An initialised ``ClaudeClient`` ready for use.
    """
    if config is None:
        cfg = get_config()
        config = cfg.get_section("claude")

    client = ClaudeClient(
        model=config.get("model", "claude-sonnet-4-6"),
        max_tokens=config.get("max_tokens", 300),
        temperature=config.get("temperature", 0.7),
        openclaw_client=openclaw_client,
    )

    await client.initialize()
    return client
