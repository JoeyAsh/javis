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

from dataclasses import dataclass
from typing import Any

from brain.agents.base import AgentResult, BaseAgent
from brain.agents.chat_agent import ChatAgent
from brain.agents.pc_agent import PcAgent
from brain.agents.smart_home_agent import SmartHomeAgent
from brain.agents.system_agent import SystemAgent
from brain.claude_client import ClaudeClient
from brain.intent_parser import Intent, IntentResult
from brain.memory_legacy import ConversationMemory
from utils.config_loader import get_config
from utils.logger import get_logger

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
_LOCAL_INTENTS: frozenset[Intent] = frozenset(
    {Intent.PC_CONTROL, Intent.SMART_HOME, Intent.SYSTEM}
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
        memory: ConversationMemory,
        tts_engine: Any = None,
    ) -> None:
        """Initialise the orchestrator.

        Args:
            claude_client: OpenClaw-backed client used for conversational
                turns (``chat()``). Local agents do not use it.
            memory: Legacy in-RAM conversation buffer. Kept so the
                ``reset memory`` system command still has something to
                clear; not consulted for LLM context — OpenClaw owns that.
            tts_engine: TTS engine handle passed through to ``SystemAgent``
                for voice-change commands.
        """
        self.claude_client = claude_client
        self.memory = memory
        self.tts_engine = tts_engine

        # Config — retained for backward compatibility, but the old
        # "orchestrator_model" / "skip_on_clear_intent" knobs no longer
        # affect routing: there is no routing LLM call any more.
        cfg = get_config()
        agents_config = cfg.get_section("agents")
        self.orchestrator_model = agents_config.get(
            "orchestrator_model", "claude-opus-4-5"
        )
        self.orchestrator_max_tokens = agents_config.get(
            "orchestrator_max_tokens", 150
        )
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

        ``SearchAgent`` is intentionally absent — factual lookups now land
        on the OpenClaw ``jarvis-main`` session via the chat path, which
        has direct access to the agent's own tools and long-term memory.
        """
        self._agents = {
            "chat": ChatAgent(self.claude_client, self.memory),
            "pc": PcAgent(self.claude_client),
            "smart_home": SmartHomeAgent(self.claude_client),
            "system": SystemAgent(
                self.claude_client, self.memory, self.tts_engine
            ),
        }

    def set_tts_engine(self, tts_engine: Any) -> None:
        """Set the TTS engine on the shared ``SystemAgent`` (late binding)."""
        self.tts_engine = tts_engine
        if "system" in self._agents:
            self._agents["system"].tts_engine = tts_engine

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
                return await agent.run(text, intent_result.params, language)
            logger.warning(
                f"Local intent {intent_result.intent.value} had no agent wired; "
                "falling back to chat path"
            )

        # --- Conversational path (single OpenClaw call) ---------------
        # Everything else — CHAT, WEB_SEARCH, ambiguous intents — now goes
        # straight to OpenClaw. The jarvis-main session owns persona, recall
        # and any tool use needed to answer factual questions.
        logger.info(
            "Chat dispatch: jarvis-main session"
            + (
                f" (intent={intent_result.intent.value}, "
                f"conf={intent_result.confidence:.2f})"
                if intent_result is not None
                else ""
            )
        )
        return await self._agents["chat"].run(text, {}, language)

    def get_agent(self, name: str) -> BaseAgent | None:
        """Return a specific agent by name (``chat`` / ``pc`` / …)."""
        return self._agents.get(name)


def _intent_to_agent_name(intent: Intent) -> str:
    """Map a classified intent to the local agent key."""
    if intent == Intent.PC_CONTROL:
        return "pc"
    if intent == Intent.SMART_HOME:
        return "smart_home"
    if intent == Intent.SYSTEM:
        return "system"
    return "chat"
