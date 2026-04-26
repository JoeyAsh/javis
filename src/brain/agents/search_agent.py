"""Web search agent for JARVIS — delegates to OpenClaw's search extension."""

from __future__ import annotations

from typing import Any

from brain.agents.base import AgentResult, BaseAgent
from brain.claude_client import ClaudeClient
from utils.logger import get_logger

logger = get_logger("agent.search")

# Spoken fallbacks when OpenClaw is unreachable or returns an empty response.
_FALLBACK_DE = "Web-Suche aktuell nicht möglich, Sir."
_FALLBACK_EN = "Web search currently unavailable, sir."

# Prompt templates — placeholders: {query}
_PROMPT_DE = (
    "Suche im Web nach: {query}. "
    "Antworte mit einer knappen Zusammenfassung von 1–2 Sätzen, "
    "die für die Sprachausgabe geeignet ist. "
    "Nenne die Quelle, wenn du dir sicher bist."
)
_PROMPT_EN = (
    "Search the web for: {query}. "
    "Reply with a concise 1–2 sentence answer suitable for spoken delivery, "
    "citing the source if confident."
)


class SearchAgent(BaseAgent):
    """Agent for web search via the OpenClaw search extension."""

    def __init__(self, claude_client: ClaudeClient) -> None:
        """Initialise the search agent.

        Args:
            claude_client: OpenClaw-backed LLM client whose ``openclaw``
                property exposes the raw ``OpenClawClient``.
        """
        super().__init__()
        self.claude_client = claude_client

    async def run(
        self, task: str, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Execute a web search via OpenClaw.

        Args:
            task: Original user utterance (unused — the structured query from
                ``params`` is preferred; ``task`` acts as a fallback).
            params: Parameters extracted by the intent parser.  Expected key:
                ``"query"`` — the search query string.
            language: Response language (``"en"`` / ``"de"``).

        Returns:
            ``AgentResult`` with a 1–2 sentence spoken summary, or a graceful
            spoken fallback when OpenClaw is unavailable or returns an error.
        """
        query: str = params.get("query", "") or task
        if not query:
            fallback = _FALLBACK_DE if language == "de" else _FALLBACK_EN
            return AgentResult(
                spoken_response=fallback,
                success=False,
                data={"reason": "no_query"},
            )

        openclaw = self.claude_client.openclaw
        if openclaw is None or not openclaw.is_enabled:
            logger.warning("SearchAgent: OpenClaw client unavailable")
            fallback = _FALLBACK_DE if language == "de" else _FALLBACK_EN
            return AgentResult(
                spoken_response=fallback,
                success=False,
                data={"reason": "openclaw_disabled"},
            )

        prompt_template = _PROMPT_DE if language == "de" else _PROMPT_EN
        prompt = prompt_template.format(query=query)
        logger.info(f"SearchAgent: querying OpenClaw for '{query}'")
        logger.debug(f"SearchAgent prompt: {prompt!r}")

        try:
            resp = await openclaw.query_agent(prompt)
        except Exception as exc:
            logger.error(f"SearchAgent: unexpected error calling OpenClaw: {exc}")
            fallback = _FALLBACK_DE if language == "de" else _FALLBACK_EN
            return AgentResult(
                spoken_response=fallback,
                success=False,
                data={"error": str(exc)},
            )

        if resp.error or not resp.text.strip():
            logger.warning(
                f"SearchAgent: OpenClaw returned error/empty — "
                f"error={resp.error!r} text_len={len(resp.text)}"
            )
            fallback = _FALLBACK_DE if language == "de" else _FALLBACK_EN
            return AgentResult(
                spoken_response=fallback,
                success=False,
                data={"error": resp.error, "query": query},
            )

        logger.debug(f"SearchAgent result preview: {resp.text[:120]!r}")
        return AgentResult(
            spoken_response=resp.text.strip(),
            success=True,
            data={"query": query, "session_id": resp.session_id},
        )
