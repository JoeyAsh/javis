"""Orchestrator for JARVIS.

Routes requests to appropriate subagents using Claude Opus.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from brain.agents.base import AgentResult, BaseAgent
from brain.agents.chat_agent import ChatAgent
from brain.agents.pc_agent import PcAgent
from brain.agents.search_agent import SearchAgent
from brain.agents.smart_home_agent import SmartHomeAgent
from brain.agents.system_agent import SystemAgent
from brain.claude_client import ClaudeClient
from brain.intent_parser import Intent, IntentResult
from brain.memory import ConversationMemory
from utils.config_loader import get_config
from utils.logger import get_logger

logger = get_logger("orchestrator")


@dataclass
class OrchestratorDecision:
    """Decision from the orchestrator."""

    agent: str  # "chat" | "pc" | "smart_home" | "search" | "system"
    task: str
    params: dict[str, Any] = field(default_factory=dict)
    requires_followup: bool = False
    reasoning: str = ""


ORCHESTRATOR_SYSTEM_PROMPT = """You are the JARVIS orchestrator. Your job is to route user requests to the appropriate agent.

Available agents:
- chat: General conversation, questions, advice
- pc: PC control (open/close apps, volume, screenshot, etc.)
- smart_home: Home automation (lights, thermostat, locks)
- search: Web search for factual information
- system: JARVIS system commands (change voice, reset memory, shutdown)

Rules:
1. NEVER answer the user directly - only route to an agent
2. Return JSON only, no explanation
3. Decompose multi-step requests into the FIRST step only
4. Use conversation context to resolve pronouns ("turn it off" -> last mentioned device)

Response format (JSON only):
{
  "agent": "chat|pc|smart_home|search|system",
  "task": "brief description of what the agent should do",
  "params": {"key": "value"},
  "requires_followup": false,
  "reasoning": "why this routing decision (for logging only)"
}"""


class Orchestrator:
    """Routes requests to appropriate subagents."""

    def __init__(
        self,
        claude_client: ClaudeClient,
        memory: ConversationMemory,
        tts_engine: Any = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            claude_client: Claude client for API calls
            memory: Conversation memory
            tts_engine: TTS engine for system agent
        """
        self.claude_client = claude_client
        self.memory = memory
        self.tts_engine = tts_engine

        # Load config
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

        # Initialize subagents
        self._agents: dict[str, BaseAgent] = {}
        self._init_agents()

    def _init_agents(self) -> None:
        """Initialize all subagents."""
        self._agents = {
            "chat": ChatAgent(self.claude_client, self.memory),
            "pc": PcAgent(self.claude_client),
            "smart_home": SmartHomeAgent(self.claude_client),
            "search": SearchAgent(self.claude_client),
            "system": SystemAgent(
                self.claude_client, self.memory, self.tts_engine
            ),
        }

    def set_tts_engine(self, tts_engine: Any) -> None:
        """Set the TTS engine (for late binding).

        Args:
            tts_engine: TTS engine instance
        """
        self.tts_engine = tts_engine
        if "system" in self._agents:
            self._agents["system"].tts_engine = tts_engine

    async def process(
        self,
        text: str,
        language: str,
        intent_result: IntentResult | None = None,
    ) -> AgentResult:
        """Process user input and return agent result.

        Args:
            text: User input text
            language: Detected language
            intent_result: Pre-classified intent (optional)

        Returns:
            AgentResult from the appropriate agent
        """
        # If we have a high-confidence intent, skip orchestrator
        if (
            self.skip_on_clear_intent
            and intent_result
            and intent_result.confidence > 0.7
            and intent_result.intent != Intent.CHAT
        ):
            return await self._route_direct(text, language, intent_result)

        # Use orchestrator for ambiguous/complex requests
        decision = await self._get_decision(text, language)

        if decision is None:
            # Fallback to chat
            logger.warning("Orchestrator decision failed, falling back to chat")
            return await self._agents["chat"].run(text, {}, language)

        logger.info(
            f"Orchestrator: {decision.agent} - {decision.task} "
            f"(reason: {decision.reasoning})"
        )

        return await self._execute_decision(decision, language)

    async def _route_direct(
        self, text: str, language: str, intent_result: IntentResult
    ) -> AgentResult:
        """Route directly to agent based on intent (skip orchestrator).

        Args:
            text: User input text
            language: Detected language
            intent_result: Classified intent

        Returns:
            AgentResult from the appropriate agent
        """
        intent_to_agent = {
            Intent.CHAT: "chat",
            Intent.PC_CONTROL: "pc",
            Intent.SMART_HOME: "smart_home",
            Intent.WEB_SEARCH: "search",
            Intent.SYSTEM: "system",
        }

        agent_name = intent_to_agent.get(intent_result.intent, "chat")
        agent = self._agents.get(agent_name, self._agents["chat"])

        logger.info(
            f"Direct routing: {agent_name} "
            f"(intent={intent_result.intent.value}, conf={intent_result.confidence:.2f})"
        )

        return await agent.run(text, intent_result.params, language)

    async def _get_decision(
        self, text: str, language: str
    ) -> OrchestratorDecision | None:
        """Get routing decision from orchestrator.

        Args:
            text: User input text
            language: Detected language

        Returns:
            OrchestratorDecision or None on failure
        """
        # Build context with conversation summary
        context = self.memory.get_summary(self.history_turns_for_orchestrator)

        prompt = f"""Recent conversation:
{context}

Current user request ({language}): {text}

Route this request to the appropriate agent. Respond with JSON only."""

        try:
            response = await self.claude_client.complete(
                prompt=prompt,
                system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
                model=self.orchestrator_model,
                max_tokens=self.orchestrator_max_tokens,
                temperature=0.3,
            )

            # Parse JSON response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()

            data = json.loads(response)

            return OrchestratorDecision(
                agent=data.get("agent", "chat"),
                task=data.get("task", text),
                params=data.get("params", {}),
                requires_followup=data.get("requires_followup", False),
                reasoning=data.get("reasoning", ""),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse orchestrator response: {e}")
            return None
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            return None

    async def _execute_decision(
        self, decision: OrchestratorDecision, language: str
    ) -> AgentResult:
        """Execute an orchestrator decision.

        Args:
            decision: Orchestrator decision
            language: Detected language

        Returns:
            AgentResult from the agent
        """
        agent = self._agents.get(decision.agent)

        if agent is None:
            logger.warning(f"Unknown agent: {decision.agent}, falling back to chat")
            agent = self._agents["chat"]

        return await agent.run(decision.task, decision.params, language)

    def get_agent(self, name: str) -> BaseAgent | None:
        """Get a specific agent by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None
        """
        return self._agents.get(name)
