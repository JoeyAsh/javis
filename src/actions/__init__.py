"""Action handler modules for JARVIS."""

from actions.pc_control import execute_pc_action
from actions.smart_home import execute_home_action
from actions.web_search import execute_web_search
from actions.system_actions import SystemActions

__all__ = [
    "execute_pc_action",
    "execute_home_action",
    "execute_web_search",
    "SystemActions",
]
