"""Tests for the intent parser module."""

import pytest

from src.brain.intent_parser import Intent, IntentParser, IntentResult, get_intent_parser


@pytest.fixture
def intent_parser():
    """Return an IntentParser instance."""
    return IntentParser()


class TestIntentParser:
    """Tests for IntentParser class."""

    # PC Control Tests - English
    @pytest.mark.asyncio
    async def test_pc_control_open_chrome_en(self, intent_parser):
        """Test 'open chrome' is classified as PC_CONTROL."""
        result = await intent_parser.classify_intent("open chrome", "en")
        assert result.intent == Intent.PC_CONTROL
        assert result.params.get("action") == "open_app"
        assert result.params.get("app") == "chrome"

    @pytest.mark.asyncio
    async def test_pc_control_set_volume_en(self, intent_parser):
        """Test 'set volume to 50' is classified as PC_CONTROL."""
        result = await intent_parser.classify_intent("set volume to 50", "en")
        assert result.intent == Intent.PC_CONTROL
        assert result.params.get("action") == "set_volume"
        assert result.params.get("level") == 50

    @pytest.mark.asyncio
    async def test_pc_control_screenshot_en(self, intent_parser):
        """Test 'take a screenshot' is classified as PC_CONTROL."""
        result = await intent_parser.classify_intent("take a screenshot", "en")
        assert result.intent == Intent.PC_CONTROL
        assert result.params.get("action") == "screenshot"

    @pytest.mark.asyncio
    async def test_pc_control_close_app_en(self, intent_parser):
        """Test 'close notepad' is classified as PC_CONTROL."""
        result = await intent_parser.classify_intent("close notepad", "en")
        assert result.intent == Intent.PC_CONTROL
        assert result.params.get("action") == "close_app"

    # PC Control Tests - German
    @pytest.mark.asyncio
    async def test_pc_control_open_spotify_de(self, intent_parser):
        """Test 'öffne spotify' is classified as PC_CONTROL."""
        result = await intent_parser.classify_intent("öffne spotify", "de")
        assert result.intent == Intent.PC_CONTROL
        assert result.params.get("action") == "open_app"

    @pytest.mark.asyncio
    async def test_pc_control_volume_de(self, intent_parser):
        """Test 'lautstärke 30' is classified as PC_CONTROL."""
        result = await intent_parser.classify_intent("lautstärke auf 30", "de")
        assert result.intent == Intent.PC_CONTROL
        assert result.params.get("action") == "set_volume"

    # Smart Home Tests - English
    @pytest.mark.asyncio
    async def test_smart_home_lights_on_en(self, intent_parser):
        """Test 'turn on the lights' is classified as SMART_HOME."""
        result = await intent_parser.classify_intent("turn on the lights", "en")
        assert result.intent == Intent.SMART_HOME
        assert result.params.get("action") == "turn_on"
        assert result.params.get("domain") == "light"

    @pytest.mark.asyncio
    async def test_smart_home_temperature_en(self, intent_parser):
        """Test 'set temperature to 22' is classified as SMART_HOME."""
        result = await intent_parser.classify_intent("set temperature to 22", "en")
        assert result.intent == Intent.SMART_HOME
        assert result.params.get("domain") == "climate"

    @pytest.mark.asyncio
    async def test_smart_home_lock_en(self, intent_parser):
        """Test 'lock the door' is classified as SMART_HOME."""
        result = await intent_parser.classify_intent("lock the door", "en")
        assert result.intent == Intent.SMART_HOME
        assert result.params.get("action") == "lock"

    # Smart Home Tests - German
    @pytest.mark.asyncio
    async def test_smart_home_lights_de(self, intent_parser):
        """Test 'licht an' is classified as SMART_HOME."""
        result = await intent_parser.classify_intent("licht an", "de")
        assert result.intent == Intent.SMART_HOME
        assert result.params.get("domain") == "light"

    # Web Search Tests - English
    @pytest.mark.asyncio
    async def test_search_python_en(self, intent_parser):
        """Test 'search for python tutorials' is classified as WEB_SEARCH."""
        result = await intent_parser.classify_intent("search for python tutorials", "en")
        assert result.intent == Intent.WEB_SEARCH
        assert "python tutorials" in result.params.get("query", "")

    @pytest.mark.asyncio
    async def test_search_what_is_en(self, intent_parser):
        """Test 'what is the capital of France' is classified as WEB_SEARCH."""
        result = await intent_parser.classify_intent("what is the capital of France", "en")
        assert result.intent == Intent.WEB_SEARCH

    # Web Search Tests - German
    @pytest.mark.asyncio
    async def test_search_weather_de(self, intent_parser):
        """Test 'suche nach wetter berlin' is classified as WEB_SEARCH."""
        result = await intent_parser.classify_intent("suche nach wetter berlin", "de")
        assert result.intent == Intent.WEB_SEARCH

    # System Tests - English
    @pytest.mark.asyncio
    async def test_system_shutdown_en(self, intent_parser):
        """Test 'shutdown jarvis' is classified as SYSTEM."""
        result = await intent_parser.classify_intent("shutdown jarvis", "en")
        assert result.intent == Intent.SYSTEM
        assert result.params.get("action") == "shutdown"

    @pytest.mark.asyncio
    async def test_system_change_voice_en(self, intent_parser):
        """Test 'change voice' is classified as SYSTEM."""
        result = await intent_parser.classify_intent("change voice", "en")
        assert result.intent == Intent.SYSTEM
        assert result.params.get("action") == "change_voice"

    @pytest.mark.asyncio
    async def test_system_reset_memory_en(self, intent_parser):
        """Test 'reset memory' is classified as SYSTEM."""
        result = await intent_parser.classify_intent("reset memory", "en")
        assert result.intent == Intent.SYSTEM
        assert result.params.get("action") == "reset_memory"

    # System Tests - German
    @pytest.mark.asyncio
    async def test_system_voice_de(self, intent_parser):
        """Test 'stimme wechseln' is classified as SYSTEM."""
        result = await intent_parser.classify_intent("stimme wechseln", "de")
        assert result.intent == Intent.SYSTEM

    # Chat Tests - English
    @pytest.mark.asyncio
    async def test_chat_hello_en(self, intent_parser):
        """Test 'hello jarvis' is classified as CHAT."""
        result = await intent_parser.classify_intent("hello jarvis", "en")
        assert result.intent == Intent.CHAT

    @pytest.mark.asyncio
    async def test_chat_time_en(self, intent_parser):
        """Test 'what time is it' is classified as CHAT or WEB_SEARCH."""
        # This could be chat or search depending on implementation
        result = await intent_parser.classify_intent("what time is it", "en")
        assert result.intent in [Intent.CHAT, Intent.WEB_SEARCH]

    @pytest.mark.asyncio
    async def test_chat_joke_en(self, intent_parser):
        """Test 'tell me a joke' is classified as CHAT."""
        result = await intent_parser.classify_intent("tell me a joke", "en")
        assert result.intent == Intent.CHAT

    # Chat Tests - German
    @pytest.mark.asyncio
    async def test_chat_hello_de(self, intent_parser):
        """Test 'hallo' is classified as CHAT."""
        result = await intent_parser.classify_intent("hallo", "de")
        assert result.intent == Intent.CHAT

    # Edge Cases
    @pytest.mark.asyncio
    async def test_empty_string(self, intent_parser):
        """Test empty string returns CHAT with low confidence."""
        result = await intent_parser.classify_intent("", "en")
        assert result.intent == Intent.CHAT
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_whitespace_only(self, intent_parser):
        """Test whitespace-only string returns CHAT with low confidence."""
        result = await intent_parser.classify_intent("   ", "en")
        assert result.intent == Intent.CHAT
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_mixed_language(self, intent_parser):
        """Test mixed language input is handled."""
        result = await intent_parser.classify_intent("open the Licht", "en")
        # Should recognize at least one keyword
        assert result.intent in [Intent.PC_CONTROL, Intent.SMART_HOME, Intent.CHAT]


class TestIntentResult:
    """Tests for IntentResult dataclass."""

    def test_intent_result_fields(self):
        """Test IntentResult has expected fields."""
        result = IntentResult(
            intent=Intent.PC_CONTROL,
            confidence=0.85,
            params={"action": "open_app", "app": "chrome"},
            original_text="open chrome",
            language="en",
        )

        assert result.intent == Intent.PC_CONTROL
        assert result.confidence == 0.85
        assert result.params["action"] == "open_app"
        assert result.original_text == "open chrome"
        assert result.language == "en"


class TestGetIntentParser:
    """Tests for get_intent_parser singleton."""

    def test_returns_same_instance(self):
        """Test that get_intent_parser returns singleton."""
        parser1 = get_intent_parser()
        parser2 = get_intent_parser()

        assert parser1 is parser2


class TestIntentEnum:
    """Tests for Intent enum."""

    def test_all_intents_defined(self):
        """Test all expected intents are defined."""
        assert Intent.CHAT.value == "chat"
        assert Intent.PC_CONTROL.value == "pc_control"
        assert Intent.SMART_HOME.value == "smart_home"
        assert Intent.WEB_SEARCH.value == "web_search"
        assert Intent.SYSTEM.value == "system"
