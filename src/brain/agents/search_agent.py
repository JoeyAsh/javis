"""Search agent for JARVIS - handles web searches."""

from typing import Any

from src.actions.web_search import execute_web_search
from src.brain.agents.base import AgentResult, BaseAgent
from src.brain.claude_client import ClaudeClient
from src.utils.logger import get_logger

logger = get_logger("agent.search")

SEARCH_SUMMARIZE_PROMPT = """You are JARVIS summarizing search results.
Be concise (1-2 sentences). Maintain JARVIS personality.
If the search returned no results, answer from your own knowledge if possible.
Always respond in the same language as the user's query."""


class SearchAgent(BaseAgent):
    """Agent for web search and information retrieval."""

    def __init__(self, claude_client: ClaudeClient) -> None:
        """Initialize the search agent.

        Args:
            claude_client: Claude client for API calls
        """
        super().__init__()
        self.claude_client = claude_client

    async def run(
        self, task: str, params: dict[str, Any], language: str
    ) -> AgentResult:
        """Execute a web search.

        Args:
            task: Search query or task description
            params: Search parameters (query)
            language: Response language

        Returns:
            AgentResult with search summary
        """
        try:
            # Get search query
            query = params.get("query", task)

            # Execute web search
            search_result = await execute_web_search(query)

            # Summarize results with Claude
            response = await self._summarize_results(query, search_result, language)

            return AgentResult(
                spoken_response=response,
                success=True,
                data={"query": query, "raw_result": search_result},
            )

        except Exception as e:
            logger.error(f"Search agent error: {e}")
            return AgentResult(
                spoken_response=self._format_error_response(str(e), language),
                success=False,
                data={"error": str(e)},
            )

    async def _summarize_results(
        self, query: str, search_result: str, language: str
    ) -> str:
        """Summarize search results using Claude.

        Args:
            query: Original search query
            search_result: Raw search result
            language: Response language

        Returns:
            Summarized response
        """
        system_prompt = SEARCH_SUMMARIZE_PROMPT
        system_prompt += f"\n\n{self._get_language_instruction(language)}"

        prompt = f"""User query: {query}

Search results:
{search_result}

Provide a concise answer to the user's query."""

        response = await self.claude_client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=0.5,
        )

        if not response:
            # Fallback if Claude fails
            if language == "de":
                response = f"Ich habe folgendes gefunden: {search_result[:200]}"
            else:
                response = f"I found the following: {search_result[:200]}"

        return response
