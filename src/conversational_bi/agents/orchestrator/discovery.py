"""Agent discovery service for the orchestrator."""

from dataclasses import dataclass, field

import httpx
import structlog

from conversational_bi.common.exceptions import AgentDiscoveryError

logger = structlog.get_logger()


@dataclass
class DiscoveredAgent:
    """Represents a discovered data agent."""

    name: str
    description: str
    base_url: str
    skills: list[dict]
    is_healthy: bool = True


class AgentDiscoveryService:
    """
    Discovers and maintains registry of available data agents.

    Agents are discovered via their well-known Agent Card endpoints.
    """

    WELL_KNOWN_PATH = "/.well-known/agent-card.json"

    def __init__(self, agent_urls: list[str]):
        """
        Initialize with list of known agent base URLs.

        Args:
            agent_urls: List of base URLs for data agents
                       e.g., ["http://localhost:8001", "http://localhost:8002"]
        """
        self.agent_urls = agent_urls
        self._agents: dict[str, DiscoveredAgent] = {}
        self._http_client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AgentDiscoveryService":
        self._http_client = httpx.AsyncClient(timeout=10.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._http_client:
            await self._http_client.aclose()

    async def discover_all(self) -> list[DiscoveredAgent]:
        """
        Discover all configured agents by fetching their Agent Cards.

        Returns:
            List of discovered agents with their capabilities.
        """
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=10.0)

        discovered = []

        for base_url in self.agent_urls:
            try:
                agent = await self._discover_agent(base_url)
                if agent:
                    discovered.append(agent)
                    self._agents[agent.name] = agent
                    logger.info(
                        "agent_discovered",
                        name=agent.name,
                        skills=[s["id"] for s in agent.skills],
                    )
            except Exception as e:
                logger.warning(
                    "agent_discovery_failed",
                    url=base_url,
                    error=str(e),
                )

        if not discovered:
            raise AgentDiscoveryError("No agents discovered")

        return discovered

    async def _discover_agent(self, base_url: str) -> DiscoveredAgent | None:
        """Fetch Agent Card from a single agent."""
        card_url = f"{base_url.rstrip('/')}{self.WELL_KNOWN_PATH}"

        response = await self._http_client.get(card_url)
        response.raise_for_status()

        card_data = response.json()

        return DiscoveredAgent(
            name=card_data.get("name", "Unknown"),
            description=card_data.get("description", ""),
            base_url=base_url,
            skills=card_data.get("skills", []),
        )

    def get_agent_for_skill(self, skill_id: str) -> DiscoveredAgent | None:
        """Find agent that has a specific skill."""
        for agent in self._agents.values():
            if any(s["id"] == skill_id for s in agent.skills):
                return agent
        return None

    def get_agents_by_tag(self, tag: str) -> list[DiscoveredAgent]:
        """Find all agents with skills matching a tag."""
        matching = []
        for agent in self._agents.values():
            if any(tag in s.get("tags", []) for s in agent.skills):
                matching.append(agent)
        return matching

    def get_all_skills(self) -> list[dict]:
        """Get all available skills across all agents."""
        skills = []
        for agent in self._agents.values():
            for skill in agent.skills:
                skills.append({
                    "agent": agent.name,
                    "skill_id": skill["id"],
                    "skill_name": skill.get("name", skill["id"]),
                    "description": skill.get("description", ""),
                    "examples": skill.get("examples", []),
                })
        return skills

    def get_agent_by_name(self, name: str) -> DiscoveredAgent | None:
        """Get agent by name."""
        return self._agents.get(name)

    @property
    def agents(self) -> dict[str, DiscoveredAgent]:
        """Get all discovered agents."""
        return self._agents
