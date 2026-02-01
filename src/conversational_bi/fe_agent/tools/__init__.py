"""FE Agent tools for A2A communication."""

from conversational_bi.fe_agent.tools.a2a_client import create_a2a_tools
from conversational_bi.fe_agent.tools.discovery import AgentDiscovery, DiscoveredAgent

__all__ = ["AgentDiscovery", "DiscoveredAgent", "create_a2a_tools"]
