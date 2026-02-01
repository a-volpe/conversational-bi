"""Agent discovery via A2A protocol."""

import os
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

# LangSmith tracing (enabled via LANGCHAIN_TRACING_V2=true)
_langsmith_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
if _langsmith_enabled:
    from langsmith import traceable
else:
    def traceable(*args, **kwargs):  # type: ignore[misc]
        def decorator(func):
            return func
        return decorator if not args or callable(args[0]) is False else args[0]

logger = structlog.get_logger()


@dataclass
class DiscoveredAgent:
    """Represents a discovered A2A agent."""

    name: str
    description: str
    base_url: str
    version: str = "1.0.0"
    skills: list[dict[str, Any]] = field(default_factory=list)
    capabilities: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_agent_card(cls, card: dict, base_url: str) -> "DiscoveredAgent":
        """Create from an A2A agent card."""
        return cls(
            name=card.get("name", "Unknown Agent"),
            description=card.get("description", ""),
            base_url=base_url.rstrip("/"),
            version=card.get("version", "1.0.0"),
            skills=card.get("skills", []),
            capabilities=card.get("capabilities", {}),
        )

    def get_skill_names(self) -> list[str]:
        """Get list of skill names."""
        return [s.get("name", s.get("id", "")) for s in self.skills]

    def get_skill_descriptions(self) -> str:
        """Get formatted skill descriptions for prompts."""
        lines = []
        for skill in self.skills:
            name = skill.get("name", skill.get("id", "unknown"))
            desc = skill.get("description", "")
            lines.append(f"  - {name}: {desc}")
        return "\n".join(lines)


class AgentDiscovery:
    """
    Discovers A2A agents from configured URLs.

    Fetches agent cards from /.well-known/agent-card.json endpoints.
    """

    def __init__(
        self,
        agent_urls: list[str],
        timeout: float = 10.0,
    ):
        """
        Initialize agent discovery.

        Args:
            agent_urls: List of base URLs for data agents
            timeout: HTTP request timeout in seconds
        """
        self.agent_urls = agent_urls
        self.timeout = timeout
        self._discovered: list[DiscoveredAgent] = []


    #TODO: from langsmith trace seems it discovers agents twice
    @traceable(name="discover_agents", run_type="chain")
    async def discover_all(self) -> list[DiscoveredAgent]:
        """
        Discover all configured agents.

        Returns:
            List of discovered agents
        """
        self._discovered = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for url in self.agent_urls:
                try:
                    agent = await self._discover_agent(client, url)
                    if agent:
                        self._discovered.append(agent)
                        logger.info(
                            "agent_discovered",
                            name=agent.name,
                            url=url,
                            skills=len(agent.skills),
                        )
                except Exception as e:
                    logger.warning(
                        "agent_discovery_failed",
                        url=url,
                        error=str(e),
                    )

        return self._discovered

    async def _discover_agent(
        self,
        client: httpx.AsyncClient,
        base_url: str,
    ) -> DiscoveredAgent | None:
        """Discover a single agent from its base URL."""
        card_url = f"{base_url.rstrip('/')}/.well-known/agent-card.json"

        response = await client.get(card_url)
        response.raise_for_status()

        card = response.json()
        return DiscoveredAgent.from_agent_card(card, base_url)

    @property
    def agents(self) -> list[DiscoveredAgent]:
        """Get list of discovered agents."""
        return self._discovered

    def get_agent_by_name(self, name: str) -> DiscoveredAgent | None:
        """Find agent by name (case-insensitive)."""
        name_lower = name.lower()
        for agent in self._discovered:
            if agent.name.lower() == name_lower:
                return agent
        return None

    def get_capabilities_summary(self) -> str:
        """Get a summary of all agent capabilities for prompts."""
        lines = []
        for agent in self._discovered:
            lines.append(f"**{agent.name}**: {agent.description}")
            lines.append(agent.get_skill_descriptions())
            lines.append("")
        return "\n".join(lines)
