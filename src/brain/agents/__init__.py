"""Subagent modules for JARVIS.

``SearchAgent`` used to live here but was deleted alongside the routing
LLM hop: factual lookups now land directly on the OpenClaw ``jarvis-main``
session via :class:`brain.agents.chat_agent.ChatAgent`.
"""

from brain.agents.base import AgentResult, BaseAgent
from brain.agents.chat_agent import ChatAgent
from brain.agents.pc_agent import PcAgent
from brain.agents.smart_home_agent import SmartHomeAgent
from brain.agents.system_agent import SystemAgent

__all__ = [
    "AgentResult",
    "BaseAgent",
    "ChatAgent",
    "PcAgent",
    "SmartHomeAgent",
    "SystemAgent",
]
