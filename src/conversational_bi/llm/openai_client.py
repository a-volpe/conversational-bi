"""OpenAI API client wrapper for the conversational BI application."""

from dataclasses import dataclass
from typing import Any

import structlog
from openai import AsyncOpenAI

from conversational_bi.common.config import get_settings
from conversational_bi.common.exceptions import LLMError

logger = structlog.get_logger()


@dataclass
class SQLGenerationResult:
    """Result of SQL generation from natural language."""

    sql: str
    parameters: list[Any]
    explanation: str = ""


@dataclass
class QueryAnalysisResult:
    """Result of analyzing a user query for routing."""

    @dataclass
    class SkillMapping:
        skill_id: str
        sub_query: str
        confidence: float

    skill_mappings: list[SkillMapping]
    requires_cross_join: bool
    join_strategy: str | None


class OpenAIClient:
    """
    Async client for OpenAI API interactions.

    Provides methods for SQL generation, query analysis, and response synthesis.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-5-mini",
        temperature: float | None = None,
        reasoning_effort: str = "low",
    ):
        """
        Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key. Defaults to settings.openai_api_key.
            model: Model to use for completions.
            temperature: Temperature for completions (0.0-2.0). Not supported for GPT-5 models.
            reasoning_effort: Reasoning effort for GPT-5 models (low, medium, high).
        """
        self._api_key = api_key or get_settings().openai_api_key
        self._model = model
        self._temperature = temperature
        self._reasoning_effort = reasoning_effort
        self._client = AsyncOpenAI(api_key=self._api_key)

    def _is_gpt5_model(self) -> bool:
        """Check if the current model is a GPT-5 series model."""
        return self._model.startswith("gpt-5")

    def _get_model_params(self) -> dict[str, Any]:
        """Get model-specific parameters for API calls."""
        if self._is_gpt5_model():
            return {"reasoning_effort": self._reasoning_effort}
        return {"temperature": self._temperature if self._temperature is not None else 0.0}

    async def generate_sql(
        self,
        user_query: str,
        system_prompt: str,
        table_schema: str,
    ) -> SQLGenerationResult:
        """
        Generate SQL from natural language query.

        Args:
            user_query: The user's natural language question.
            system_prompt: System prompt with instructions for SQL generation.
            table_schema: The database schema context.

        Returns:
            SQLGenerationResult with the generated SQL and parameters.

        Raises:
            LLMError: If the API call fails.
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Table Schema:\n{table_schema}\n\nQuestion: {user_query}",
                },
            ]

            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                **self._get_model_params(),
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "execute_sql",
                            "description": "Execute a SQL query against the database",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "sql": {
                                        "type": "string",
                                        "description": "The SQL SELECT query to execute",
                                    },
                                    "parameters": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Parameter values for $1, $2, etc.",
                                    },
                                    "explanation": {
                                        "type": "string",
                                        "description": "Brief explanation of what the query does",
                                    },
                                },
                                "required": ["sql", "parameters"],
                            },
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": "execute_sql"}},
            )

            # Extract function call result
            tool_call = response.choices[0].message.tool_calls[0]
            import json

            args = json.loads(tool_call.function.arguments)

            logger.info(
                "sql_generated",
                query=user_query[:50],
                sql=args["sql"][:100],
            )

            return SQLGenerationResult(
                sql=args["sql"],
                parameters=args.get("parameters", []),
                explanation=args.get("explanation", ""),
            )

        except Exception as e:
            logger.error("sql_generation_failed", error=str(e))
            raise LLMError(f"Failed to generate SQL: {e}") from e

    async def analyze_query(
        self,
        user_query: str,
        available_skills: list[dict],
    ) -> QueryAnalysisResult:
        """
        Analyze user query to determine which agents/skills to use.

        Args:
            user_query: The user's natural language question.
            available_skills: List of available skills from discovered agents.

        Returns:
            QueryAnalysisResult with skill mappings and join strategy.

        Raises:
            LLMError: If the API call fails.
        """
        try:
            skills_context = "\n".join(
                f"- {s['skill_id']} ({s['agent']}): {s['description']}"
                for s in available_skills
            )

            messages = [
                {
                    "role": "system",
                    "content": """You are a query router for a BI system. Analyze the user's question
                    and determine which data agents/skills are needed to answer it.

                    Consider:
                    1. Which tables/data sources are needed
                    2. Whether data from multiple sources needs to be joined
                    3. What the appropriate join key would be

                    Return your analysis as a structured response.""",
                },
                {
                    "role": "user",
                    "content": f"Available skills:\n{skills_context}\n\nQuestion: {user_query}",
                },
            ]

            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                **self._get_model_params(),
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "route_query",
                            "description": "Route query to appropriate data agents",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "skill_mappings": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "skill_id": {"type": "string"},
                                                "sub_query": {"type": "string"},
                                                "confidence": {"type": "number"},
                                            },
                                        },
                                    },
                                    "requires_cross_join": {"type": "boolean"},
                                    "join_strategy": {
                                        "type": "string",
                                        "description": "Join key if cross-join needed",
                                    },
                                },
                                "required": ["skill_mappings", "requires_cross_join"],
                            },
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": "route_query"}},
            )

            tool_call = response.choices[0].message.tool_calls[0]
            import json

            args = json.loads(tool_call.function.arguments)

            logger.info(
                "query_analyzed",
                query=user_query[:50],
                skills=[m["skill_id"] for m in args["skill_mappings"]],
            )

            return QueryAnalysisResult(
                skill_mappings=[
                    QueryAnalysisResult.SkillMapping(
                        skill_id=m["skill_id"],
                        sub_query=m["sub_query"],
                        confidence=m.get("confidence", 1.0),
                    )
                    for m in args["skill_mappings"]
                ],
                requires_cross_join=args["requires_cross_join"],
                join_strategy=args.get("join_strategy"),
            )

        except Exception as e:
            logger.error("query_analysis_failed", error=str(e))
            raise LLMError(f"Failed to analyze query: {e}") from e

    async def synthesize_response(
        self,
        original_query: str,
        agent_results: list[dict],
    ) -> str:
        """
        Synthesize natural language response from agent results.

        Args:
            original_query: The user's original question.
            agent_results: Results from data agents.

        Returns:
            Natural language response summarizing the results.

        Raises:
            LLMError: If the API call fails.
        """
        try:
            results_context = "\n".join(
                f"- {r['agent']}: {r['text']} ({r['row_count']} rows)"
                for r in agent_results
            )

            messages = [
                {
                    "role": "system",
                    "content": """You are a BI assistant. Synthesize the data results
                    into a clear, concise natural language response. Include key numbers
                    and insights. Be direct and factual.""",
                },
                {
                    "role": "user",
                    "content": f"Question: {original_query}\n\nResults:\n{results_context}",
                },
            ]

            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                **self._get_model_params(),
            )

            return response.choices[0].message.content or "Unable to generate response."

        except Exception as e:
            logger.error("response_synthesis_failed", error=str(e))
            raise LLMError(f"Failed to synthesize response: {e}") from e
