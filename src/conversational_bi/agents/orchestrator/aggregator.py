"""Result aggregation for multi-agent queries."""

from dataclasses import dataclass, field
from typing import Any

import structlog

from conversational_bi.llm.openai_client import OpenAIClient

logger = structlog.get_logger()


@dataclass
class AgentResult:
    """Result from a single data agent."""

    agent_name: str
    success: bool
    text: str
    data: list[dict[str, Any]] | None = None
    error: str | None = None


@dataclass
class AggregatedResult:
    """Combined result from multiple agents."""

    success: bool
    response_text: str
    combined_data: list[dict[str, Any]] | None = None
    source_agents: list[str] = field(default_factory=list)


class ResultAggregator:
    """
    Aggregates results from multiple data agents.

    Handles:
    - Simple concatenation for independent results
    - Join operations for related data
    - Natural language synthesis of combined results
    """

    def __init__(self, llm_client: OpenAIClient):
        """
        Initialize the aggregator.

        Args:
            llm_client: OpenAI client for response synthesis.
        """
        self.llm = llm_client

    async def aggregate(
        self,
        results: list[AgentResult],
        original_query: str,
        join_strategy: str | None = None,
    ) -> AggregatedResult:
        """
        Aggregate results from multiple agents.

        Args:
            results: Results from individual agents.
            original_query: The user's original question.
            join_strategy: How to join data (e.g., "customer_id", "product_id").

        Returns:
            AggregatedResult with combined data and synthesized response.
        """
        # Check for failures
        failed = [r for r in results if not r.success]
        if len(failed) == len(results):
            return AggregatedResult(
                success=False,
                response_text="All data sources failed to respond.",
                source_agents=[r.agent_name for r in results],
            )

        successful = [r for r in results if r.success]

        # If only one result, return it directly
        if len(successful) == 1:
            result = successful[0]
            return AggregatedResult(
                success=True,
                response_text=result.text,
                combined_data=result.data,
                source_agents=[result.agent_name],
            )

        # Multiple results - need to combine
        if join_strategy:
            combined_data = self._join_data(
                [r.data for r in successful if r.data],
                join_strategy,
            )
        else:
            # Concatenate all data
            combined_data = []
            for r in successful:
                if r.data:
                    combined_data.extend(r.data)

        # Use LLM to synthesize natural language response
        response_text = await self.llm.synthesize_response(
            original_query=original_query,
            agent_results=[
                {
                    "agent": r.agent_name,
                    "text": r.text,
                    "row_count": len(r.data) if r.data else 0,
                }
                for r in successful
            ],
        )

        return AggregatedResult(
            success=True,
            response_text=response_text,
            combined_data=combined_data,
            source_agents=[r.agent_name for r in successful],
        )

    def _join_data(
        self,
        datasets: list[list[dict]],
        join_key: str,
    ) -> list[dict]:
        """
        Join multiple datasets on a common key.

        Performs an inner join on the specified key.

        Args:
            datasets: List of datasets to join.
            join_key: The key to join on.

        Returns:
            Joined dataset.
        """
        if len(datasets) < 2:
            return datasets[0] if datasets else []

        # Start with first dataset
        result = {row[join_key]: row.copy() for row in datasets[0] if join_key in row}

        # Join subsequent datasets
        for dataset in datasets[1:]:
            for row in dataset:
                key_value = row.get(join_key)
                if key_value and key_value in result:
                    # Merge row data
                    result[key_value].update(row)

        return list(result.values())
