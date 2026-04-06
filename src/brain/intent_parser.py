"""Intent parser for JARVIS.

Classifies user intents using keyword matching without LLM calls.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from utils.logger import get_logger

logger = get_logger("intent_parser")


class Intent(Enum):
    """User intent categories."""

    CHAT = "chat"
    PC_CONTROL = "pc_control"
    SMART_HOME = "smart_home"
    WEB_SEARCH = "web_search"
    SYSTEM = "system"


@dataclass
class IntentResult:
    """Result of intent classification."""

    intent: Intent
    confidence: float
    params: dict[str, Any] = field(default_factory=dict)
    original_text: str = ""
    language: str = "en"


# Keyword patterns for intent classification
INTENT_KEYWORDS: dict[Intent, dict[str, list[str]]] = {
    Intent.PC_CONTROL: {
        "en": [
            r"\bopen\b",
            r"\blaunch\b",
            r"\bstart\b",
            r"\bclose\b",
            r"\bquit\b",
            r"\bkill\b",
            r"\bvolume\b",
            r"\bmute\b",
            r"\bunmute\b",
            r"\bscreenshot\b",
            r"\btype\b",
            r"\bbrightness\b",
            r"\bshutdown\s+computer\b",
            r"\brestart\s+computer\b",
            r"\block\s+screen\b",
        ],
        "de": [
            r"\böffne\b",
            r"\bstarte\b",
            r"\bschließe?\b",
            r"\bbeende\b",
            r"\blautstärke\b",
            r"\bstumm\b",
            r"\bscreenshot\b",
            r"\bbildschirmfoto\b",
            r"\bhelligkeit\b",
            r"\bcomputer\s+herunterfahren\b",
        ],
    },
    Intent.SMART_HOME: {
        "en": [
            r"\blights?\b",
            r"\bthermostat\b",
            r"\btemperature\b",
            r"\block\b",
            r"\bunlock\b",
            r"\bgarage\b",
            r"\bdoor\b",
            r"\bswitch\b",
            r"\bturn\s+on\b",
            r"\bturn\s+off\b",
            r"\bdim\b",
            r"\bbright(en|er)?\b",
        ],
        "de": [
            r"\blicht(er)?\b",
            r"\blampe(n)?\b",
            r"\bthermostat\b",
            r"\btemperatur\b",
            r"\bheizung\b",
            r"\bschloss\b",
            r"\btür\b",
            r"\bein(schalten)?\b",
            r"\baus(schalten)?\b",
            r"\bdimmen\b",
        ],
    },
    Intent.WEB_SEARCH: {
        "en": [
            r"\bsearch\s+(for\s+)?\b",
            r"\blook\s+up\b",
            r"\bfind\s+(out|information)\b",
            r"\bwhat\s+is\b",
            r"\bwho\s+is\b",
            r"\bwhen\s+(was|is|did)\b",
            r"\bwhere\s+is\b",
            r"\bhow\s+(to|do|does|many|much)\b",
            r"\bwhy\s+(is|do|does|did)\b",
            r"\bgoogle\b",
            r"\blook\s+it\s+up\b",
        ],
        "de": [
            r"\bsuche?\b",
            r"\brecherchiere\b",
            r"\bfinde\b",
            r"\bwas\s+ist\b",
            r"\bwer\s+ist\b",
            r"\bwann\s+(war|ist)\b",
            r"\bwo\s+ist\b",
            r"\bwie\s+(viel|viele|geht)\b",
            r"\bwarum\b",
            r"\bgoogle\b",
        ],
    },
    Intent.SYSTEM: {
        "en": [
            r"\bshutdown\s+jarvis\b",
            r"\bturn\s+off\s+jarvis\b",
            r"\bstop\s+jarvis\b",
            r"\bchange\s+(your\s+)?voice\b",
            r"\bswitch\s+voice\b",
            r"\breset\s+(conversation|memory|chat)\b",
            r"\bclear\s+(conversation|memory|chat)\b",
            r"\bforget\s+everything\b",
            r"\blist\s+voices\b",
            r"\bwhat\s+voices\b",
            r"\bavailable\s+voices\b",
        ],
        "de": [
            r"\bjarvis\s+(aus|beenden|stopp)\b",
            r"\bstimme\s+(ändern|wechseln)\b",
            r"\bwechsel(e|n)?\s+(die\s+)?stimme\b",
            r"\bgespräch\s+(zurücksetzen|löschen)\b",
            r"\bvergiss\s+alles\b",
            r"\bspeicher\s+löschen\b",
            r"\bwelche\s+stimmen\b",
        ],
    },
}

# App name aliases for PC control
APP_ALIASES: dict[str, str] = {
    # English
    "chrome": "chrome",
    "google chrome": "chrome",
    "browser": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "spotify": "spotify",
    "music": "spotify",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "code": "code",
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "explorer": "explorer",
    "file explorer": "explorer",
    "files": "explorer",
    "terminal": "cmd",
    "command prompt": "cmd",
    "powershell": "powershell",
    "discord": "discord",
    "slack": "slack",
    "teams": "teams",
    "microsoft teams": "teams",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    # German
    "rechner": "calc",
    "taschenrechner": "calc",
    "editor": "notepad",
    "musik": "spotify",
    "dateien": "explorer",
    "datei-explorer": "explorer",
}


class IntentParser:
    """Parser for classifying user intents."""

    def __init__(self) -> None:
        """Initialize the intent parser."""
        self._compiled_patterns: dict[Intent, dict[str, list[re.Pattern[str]]]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        for intent, lang_patterns in INTENT_KEYWORDS.items():
            self._compiled_patterns[intent] = {}
            for lang, patterns in lang_patterns.items():
                self._compiled_patterns[intent][lang] = [
                    re.compile(p, re.IGNORECASE) for p in patterns
                ]

    async def classify_intent(
        self, text: str, language: str = "en"
    ) -> IntentResult:
        """Classify user intent from text.

        Args:
            text: User input text
            language: Detected language (en, de)

        Returns:
            IntentResult with intent, confidence, and parameters
        """
        text_lower = text.lower().strip()

        if not text_lower:
            return IntentResult(
                intent=Intent.CHAT,
                confidence=0.0,
                original_text=text,
                language=language,
            )

        # Check each intent category
        best_intent = Intent.CHAT
        best_confidence = 0.0
        params: dict[str, Any] = {}

        for intent in [
            Intent.SYSTEM,
            Intent.PC_CONTROL,
            Intent.SMART_HOME,
            Intent.WEB_SEARCH,
        ]:
            confidence, extracted_params = self._match_intent(
                text_lower, intent, language
            )
            if confidence > best_confidence:
                best_confidence = confidence
                best_intent = intent
                params = extracted_params

        # If no strong match, default to CHAT
        if best_confidence < 0.3:
            best_intent = Intent.CHAT
            best_confidence = 1.0 - best_confidence  # Higher confidence for chat

        logger.debug(
            f"Intent: {best_intent.value} (conf={best_confidence:.2f}) "
            f"params={params}"
        )

        return IntentResult(
            intent=best_intent,
            confidence=best_confidence,
            params=params,
            original_text=text,
            language=language,
        )

    def _match_intent(
        self, text: str, intent: Intent, language: str
    ) -> tuple[float, dict[str, Any]]:
        """Match text against intent patterns.

        Args:
            text: Lowercase user text
            intent: Intent to check
            language: Language code

        Returns:
            Tuple of (confidence, extracted_params)
        """
        patterns = self._compiled_patterns.get(intent, {})
        lang_patterns = patterns.get(language, [])
        en_patterns = patterns.get("en", [])  # Fallback to English

        all_patterns = lang_patterns + (en_patterns if language != "en" else [])

        match_count = 0
        params: dict[str, Any] = {}

        for pattern in all_patterns:
            if pattern.search(text):
                match_count += 1

        if match_count == 0:
            return 0.0, params

        # Calculate confidence based on match count
        confidence = min(1.0, 0.4 + (match_count * 0.2))

        # Extract parameters based on intent
        if intent == Intent.PC_CONTROL:
            params = self._extract_pc_params(text)
        elif intent == Intent.SMART_HOME:
            params = self._extract_smart_home_params(text)
        elif intent == Intent.WEB_SEARCH:
            params = self._extract_search_params(text)
        elif intent == Intent.SYSTEM:
            params = self._extract_system_params(text)

        return confidence, params

    def _extract_pc_params(self, text: str) -> dict[str, Any]:
        """Extract parameters for PC control intents.

        Args:
            text: Lowercase user text

        Returns:
            Extracted parameters
        """
        params: dict[str, Any] = {"action": "unknown"}

        # Detect action type
        if re.search(r"\b(open|launch|start|öffne|starte)\b", text):
            params["action"] = "open_app"
            # Extract app name
            for alias, app in APP_ALIASES.items():
                if alias in text:
                    params["app"] = app
                    params["app_display"] = alias
                    break

        elif re.search(r"\b(close|quit|kill|schließe?|beende)\b", text):
            params["action"] = "close_app"
            for alias, app in APP_ALIASES.items():
                if alias in text:
                    params["app"] = app
                    break

        elif re.search(r"\b(volume|lautstärke)\b", text):
            params["action"] = "set_volume"
            # Extract volume level
            match = re.search(r"(\d+)\s*(%|percent|prozent)?", text)
            if match:
                params["level"] = int(match.group(1))
            elif re.search(r"\b(up|höher|lauter)\b", text):
                params["direction"] = "up"
            elif re.search(r"\b(down|niedriger|leiser)\b", text):
                params["direction"] = "down"

        elif re.search(r"\b(mute|stumm)\b", text):
            params["action"] = "mute_toggle"

        elif re.search(r"\b(screenshot|bildschirmfoto)\b", text):
            params["action"] = "screenshot"

        elif re.search(r"\btype\b", text):
            params["action"] = "type_text"
            # Extract text to type (everything after "type")
            match = re.search(r"\btype\s+(.+)", text)
            if match:
                params["text"] = match.group(1)

        return params

    def _extract_smart_home_params(self, text: str) -> dict[str, Any]:
        """Extract parameters for smart home intents.

        Args:
            text: Lowercase user text

        Returns:
            Extracted parameters
        """
        params: dict[str, Any] = {"action": "unknown", "domain": "light"}

        # Detect domain
        if re.search(r"\b(lights?|licht|lampe)\b", text):
            params["domain"] = "light"
        elif re.search(r"\b(thermostat|temperature|temperatur|heizung)\b", text):
            params["domain"] = "climate"
        elif re.search(r"\b(lock|schloss)\b", text):
            params["domain"] = "lock"

        # Detect action
        if re.search(r"\b(turn\s+on|ein(schalten)?|an)\b", text):
            params["action"] = "turn_on"
        elif re.search(r"\b(turn\s+off|aus(schalten)?)\b", text):
            params["action"] = "turn_off"
        elif re.search(r"\b(toggle|umschalten)\b", text):
            params["action"] = "toggle"
        elif re.search(r"\b(dim|dimmen)\b", text):
            params["action"] = "dim"
            match = re.search(r"(\d+)\s*(%|percent|prozent)?", text)
            if match:
                params["brightness"] = int(match.group(1))
        elif re.search(r"\b(lock|abschließen)\b", text):
            params["action"] = "lock"
        elif re.search(r"\b(unlock|aufschließen)\b", text):
            params["action"] = "unlock"
        elif re.search(r"\b(set|stelle?)\s*(to|auf)?\s*(\d+)", text):
            params["action"] = "set_temperature"
            match = re.search(r"(\d+)", text)
            if match:
                params["temperature"] = int(match.group(1))

        # Try to extract room/entity name
        room_patterns = [
            r"(living\s*room|wohnzimmer)",
            r"(bedroom|schlafzimmer)",
            r"(kitchen|küche)",
            r"(bathroom|bad|badezimmer)",
            r"(office|büro|arbeitszimmer)",
            r"(garage|garage)",
            r"(hall|flur)",
        ]
        for pattern in room_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                params["room"] = match.group(1).lower().replace(" ", "_")
                break

        return params

    def _extract_search_params(self, text: str) -> dict[str, Any]:
        """Extract parameters for web search intents.

        Args:
            text: Lowercase user text

        Returns:
            Extracted parameters
        """
        params: dict[str, Any] = {}

        # Remove common search prefixes
        query = text
        prefixes = [
            r"^(search\s+(for\s+)?)",
            r"^(look\s+up\s+)",
            r"^(find\s+(out\s+)?)",
            r"^(what\s+is\s+(a\s+|an\s+|the\s+)?)",
            r"^(who\s+is\s+)",
            r"^(suche?\s+(nach\s+)?)",
            r"^(was\s+ist\s+(ein\s+|eine\s+)?)",
            r"^(wer\s+ist\s+)",
            r"^(google\s+)",
        ]
        for prefix in prefixes:
            query = re.sub(prefix, "", query, flags=re.IGNORECASE)

        params["query"] = query.strip()
        return params

    def _extract_system_params(self, text: str) -> dict[str, Any]:
        """Extract parameters for system intents.

        Args:
            text: Lowercase user text

        Returns:
            Extracted parameters
        """
        params: dict[str, Any] = {"action": "unknown"}

        if re.search(r"\b(shutdown|turn\s+off|stop|beenden|aus)\s+jarvis\b", text):
            params["action"] = "shutdown"
        elif re.search(r"\b(change|switch|wechsel|änder)\s*(your\s+|die\s+)?voice|stimme\b", text):
            params["action"] = "change_voice"
            # Try to extract voice name
            match = re.search(r"\bto\s+(\w+)", text) or re.search(r"\bzu\s+(\w+)", text)
            if match:
                params["voice"] = match.group(1)
        elif re.search(r"\b(reset|clear|löschen|zurücksetzen|vergiss)\b", text):
            params["action"] = "reset_memory"
        elif re.search(r"\b(list|what|available|welche)\s*(voices?|stimmen)\b", text):
            params["action"] = "list_voices"

        return params


# Global parser instance
_parser: IntentParser | None = None


def get_intent_parser() -> IntentParser:
    """Get the global intent parser instance.

    Returns:
        IntentParser instance
    """
    global _parser
    if _parser is None:
        _parser = IntentParser()
    return _parser
