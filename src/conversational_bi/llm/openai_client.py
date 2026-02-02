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
