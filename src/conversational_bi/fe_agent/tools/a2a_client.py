"""A2A client tools for LangChain agent."""

from typing import Any

import httpx
import structlog
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from conversational_bi.fe_agent.tools.discovery import DiscoveredAgent

logger = structlog.get_logger()


class A2AQueryInput(BaseModel):
    """Input schema for A2A query tool."""

    query: str = Field(description="The natural language query to send to the agent")


async def query_a2a_agent(
    agent: DiscoveredAgent,
    query: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Query a remote agent via A2A protocol.

    Args:
        agent: The discovered agent to query
        query: Natural language query
        timeout: Request timeout in seconds

    Returns:
        Dict with 'success', 'text', 'data', and 'error' keys
    """
    url = f"{agent.base_url}/a2a/tasks/send"

    request_body = {
        "jsonrpc": "2.0",
        "id": "fe-agent-1",
        "method": "tasks/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": query}],
            }
        },
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=request_body)
            result = response.json()

            if "error" in result:
                error_msg = result["error"].get("message", "Unknown error")
                logger.warning(
                    "a2a_query_error",
                    agent=agent.name,
                    error=error_msg,
                )
                return {
                    "success": False,
                    "text": "",
                    "data": None,
                    "error": f"Agent error: {error_msg}",
                }

            # Extract text and data from artifacts
            artifacts = result.get("result", {}).get("artifacts", [])
            text_parts = []
            data_parts = []

            for artifact in artifacts:
                for part in artifact.get("parts", []):
                    if part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif part.get("type") == "data":
                        rows = part.get("data", {}).get("rows", [])
                        data_parts.extend(rows)

            return {
                "success": True,
                "text": "\n".join(text_parts),
                "data": data_parts if data_parts else None,
                "error": None,
            }

    except httpx.TimeoutException:
        logger.error("a2a_query_timeout", agent=agent.name, url=url)
        return {
            "success": False,
            "text": "",
            "data": None,
            "error": f"Request to {agent.name} timed out",
        }
    except Exception as e:
        logger.error("a2a_query_failed", agent=agent.name, error=str(e))
        return {
            "success": False,
            "text": "",
            "data": None,
            "error": f"Failed to query {agent.name}: {str(e)}",
        }


def _format_result_for_llm(result: dict[str, Any], agent_name: str) -> str:
    """Format A2A result for LLM consumption."""
    if not result["success"]:
        return f"Error from {agent_name}: {result['error']}"

    output = []
    if result["text"]:
        output.append(result["text"])

    if result["data"]:
        data = result["data"]
        if len(data) <= 10:
            # Show all rows for small results
            output.append(f"Data ({len(data)} rows):")
            for row in data:
                output.append(f"  {row}")
        else:
            # Summarize large results
            output.append(f"Data ({len(data)} rows, showing first 5):")
            for row in data[:5]:
                output.append(f"  {row}")
            output.append("  ...")

    return "\n".join(output) if output else "No results returned"


def create_a2a_tools(
    agents: list[DiscoveredAgent],
    timeout: float = 30.0,
) -> list[StructuredTool]:
    """
    Create LangChain tools for each discovered A2A agent.

    Args:
        agents: List of discovered agents
        timeout: Request timeout for each agent

    Returns:
        List of LangChain StructuredTool instances
    """
    tools = []

    for agent in agents:
        # Create async query function bound to this agent
        async def _query(query: str, _agent: DiscoveredAgent = agent) -> str:
            result = await query_a2a_agent(_agent, query, timeout)
            return _format_result_for_llm(result, _agent.name)

        # Create tool name from agent name
        tool_name = f"query_{agent.name.lower().replace(' ', '_').replace('-', '_')}"

        # Build description from agent info
        skill_summary = ", ".join(agent.get_skill_names()[:3])
        description = (
            f"Query the {agent.name}. {agent.description} "
            f"Capabilities include: {skill_summary}."
        )

        tool = StructuredTool.from_function(
            coroutine=_query,
            name=tool_name,
            description=description,
            args_schema=A2AQueryInput,
        )
        tools.append(tool)

    return tools
