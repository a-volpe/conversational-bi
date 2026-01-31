"""Orchestrator agent for coordinating data agents."""

import asyncio
from dataclasses import dataclass

import httpx
import structlog

from conversational_bi.agents.orchestrator.aggregator import (
    AgentResult,
    AggregatedResult,
    ResultAggregator,
)
from conversational_bi.agents.orchestrator.discovery import (
    AgentDiscoveryService,
    DiscoveredAgent,
)
from conversational_bi.common.config import get_settings
from conversational_bi.common.exceptions import AgentCommunicationError
from conversational_bi.llm.openai_client import OpenAIClient

logger = structlog.get_logger()


@dataclass
class QueryPlan:
    """Plan for executing a user query."""

    agents: list[DiscoveredAgent]
    sub_queries: list[str]
    join_strategy: str | None = None
    original_query: str = ""


class OrchestratorAgent:
    """
    Frontend orchestrator agent.

    Coordinates query planning, agent communication, and result aggregation.
    """

    def __init__(
        self,
        llm_client: OpenAIClient | None = None,
        agent_urls: list[str] | None = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            llm_client: OpenAI client for query analysis and synthesis.
            agent_urls: List of data agent URLs. Defaults to settings.
        """
        settings = get_settings()
        self.llm = llm_client or OpenAIClient()
        self.agent_urls = agent_urls or settings.data_agent_urls
        self.discovery = AgentDiscoveryService(self.agent_urls)
        self.aggregator = ResultAggregator(self.llm)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the orchestrator by discovering agents."""
        if not self._initialized:
            await self.discovery.discover_all()
            self._initialized = True
            logger.info(
                "orchestrator_initialized",
                agents=list(self.discovery.agents.keys()),
            )

    async def process_query(self, user_query: str) -> AggregatedResult:
        """
        Process a user query by coordinating with data agents.

        Args:
            user_query: The user's natural language question.

        Returns:
            AggregatedResult with combined response and data.
        """
        # Ensure agents are discovered
        await self.initialize()

        logger.info("orchestrator_query_received", query=user_query[:100])

        # Create query plan
        plan = await self._create_plan(user_query)

        # Execute queries against data agents
        results = await self._execute_plan(plan)

        # Aggregate results
        aggregated = await self.aggregator.aggregate(
            results=results,
            original_query=user_query,
            join_strategy=plan.join_strategy,
        )

        logger.info(
            "orchestrator_query_completed",
            success=aggregated.success,
            sources=aggregated.source_agents,
        )

        return aggregated

    async def _create_plan(self, user_query: str) -> QueryPlan:
        """
        Create an execution plan for the query.

        Uses LLM to analyze the query and map to agent skills.
        """
        # Get all available skills
        available_skills = self.discovery.get_all_skills()

        # Analyze query
        analysis = await self.llm.analyze_query(
            user_query=user_query,
            available_skills=available_skills,
        )

        # Map skills to agents
        agents = []
        sub_queries = []

        for mapping in analysis.skill_mappings:
            agent = self.discovery.get_agent_for_skill(mapping.skill_id)
            if agent and agent not in agents:
                agents.append(agent)
                sub_queries.append(mapping.sub_query)

        if not agents:
            # Fallback: send to all agents
            logger.warning("no_skill_match", query=user_query[:50])
            agents = list(self.discovery.agents.values())
            sub_queries = [user_query] * len(agents)

        return QueryPlan(
            agents=agents,
            sub_queries=sub_queries,
            join_strategy=analysis.join_strategy if analysis.requires_cross_join else None,
            original_query=user_query,
        )

    async def _execute_plan(self, plan: QueryPlan) -> list[AgentResult]:
        """Execute sub-queries against data agents in parallel."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = [
                self._query_agent(client, agent, sub_query)
                for agent, sub_query in zip(plan.agents, plan.sub_queries)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Convert exceptions to error results
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append(
                        AgentResult(
                            agent_name=plan.agents[i].name,
                            success=False,
                            text="",
                            error=str(result),
                        )
                    )
                else:
                    processed_results.append(result)

            return processed_results

    async def _query_agent(
        self,
        client: httpx.AsyncClient,
        agent: DiscoveredAgent,
        query: str,
    ) -> AgentResult:
        """Send query to a data agent via A2A protocol."""
        endpoint = f"{agent.base_url.rstrip('/')}/a2a/tasks/send"

        # Create A2A request
        request_body = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tasks/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": query}],
                }
            },
        }

        try:
            response = await client.post(endpoint, json=request_body)
            response.raise_for_status()

            result_data = response.json()

            # Check for JSON-RPC error
            if "error" in result_data:
                return AgentResult(
                    agent_name=agent.name,
                    success=False,
                    text="",
                    error=result_data["error"].get("message", "Unknown error"),
                )

            # Extract result from response
            task_result = result_data.get("result", {})
            artifacts = task_result.get("artifacts", [])

            text = ""
            data = None

            for artifact in artifacts:
                for part in artifact.get("parts", []):
                    if part.get("type") == "text":
                        text = part.get("text", "")
                    elif part.get("type") == "data":
                        data = part.get("data", {}).get("rows", [])

            return AgentResult(
                agent_name=agent.name,
                success=True,
                text=text,
                data=data,
            )

        except httpx.HTTPError as e:
            logger.error("agent_request_failed", agent=agent.name, error=str(e))
            raise AgentCommunicationError(f"Failed to contact {agent.name}: {e}") from e


def create_orchestrator_agent_card(base_url: str = "http://localhost:8000") -> dict:
    """Create the Agent Card for the Orchestrator Agent."""
    return {
        "name": "BI Orchestrator Agent",
        "description": (
            "Frontend orchestrator for conversational BI. "
            "Coordinates multiple data agents to answer complex business questions."
        ),
        "url": f"{base_url}/",
        "version": "1.0.0",
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": [
            {
                "id": "natural_language_query",
                "name": "Natural Language Query",
                "description": "Answer business questions in natural language",
                "tags": ["query", "bi", "analytics"],
                "examples": [
                    "What is our total revenue this month?",
                    "How many customers do we have in Europe?",
                    "Show me the top 10 products by sales",
                ],
            },
            {
                "id": "cross_table_analysis",
                "name": "Cross-Table Analysis",
                "description": "Analyze data across multiple tables",
                "tags": ["join", "cross-table", "analytics"],
                "examples": [
                    "Which customer segment generates the most revenue?",
                    "What products are most popular in Europe?",
                ],
            },
        ],
    }
