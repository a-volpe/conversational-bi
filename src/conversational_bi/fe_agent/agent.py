"""Frontend Agent using LangChain for flexible tool orchestration."""

from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from conversational_bi.config.loader import get_config_loader
from conversational_bi.fe_agent.tools.a2a_client import create_a2a_tools
from conversational_bi.fe_agent.tools.discovery import AgentDiscovery, DiscoveredAgent

logger = structlog.get_logger()


class FEAgent:
    """
    Frontend orchestrator agent using LangChain.

    Discovers remote data agents via A2A protocol and routes
    user queries to appropriate agents.
    """

    def __init__(self, config_loader=None):
        """
        Initialize the FE agent.

        Args:
            config_loader: Configuration loader (uses global if not provided)
        """
        self.config_loader = config_loader or get_config_loader()
        self.config = self.config_loader.load_fe_agent_config()
        self.llm_config = self.config_loader.load_llm_config()

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=self.config["llm"].get("model", self.llm_config.get("default_model", "gpt-4o")),
            temperature=self.config["llm"].get("temperature", 0.0),
            max_tokens=self.config["llm"].get("max_tokens", 4000),
        )

        # Agent discovery
        agent_urls = self.config["discovery"]["agent_urls"]
        self.discovery = AgentDiscovery(agent_urls)

        # Tools and chain (initialized after discovery)
        self.tools: list = []
        self.discovered_agents: list[DiscoveredAgent] = []
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize the agent by discovering remote agents.

        Must be called before processing queries.
        """
        if self._initialized:
            return

        # Discover remote data agents
        self.discovered_agents = await self.discovery.discover_all()

        if not self.discovered_agents:
            logger.warning("no_agents_discovered")
        else:
            logger.info(
                "agents_discovered",
                count=len(self.discovered_agents),
                names=[a.name for a in self.discovered_agents],
            )

        # Create tools for each discovered agent
        timeout = self.config["tools"]["query_agent"].get("timeout_seconds", 30)
        self.tools = create_a2a_tools(self.discovered_agents, timeout)

        # Bind tools to LLM
        if self.tools:
            self.llm_with_tools = self.llm.bind_tools(self.tools)
        else:
            self.llm_with_tools = self.llm

        self._initialized = True

    def _build_system_prompt(self) -> str:
        """Build the system prompt with discovered agent capabilities."""
        capabilities = self.discovery.get_capabilities_summary()

        base_prompt = self.config["prompts"].get("router", "")
        if "${AGENT_CAPABILITIES}" in base_prompt:
            return base_prompt.replace("${AGENT_CAPABILITIES}", capabilities)

        # Default system prompt if not configured
        return f"""You are a helpful business intelligence assistant.

You have access to the following data agents that can answer questions about business data:

{capabilities}

When a user asks a question:
1. Determine which agent(s) can best answer the question
2. Use the appropriate tool to query the agent
3. Synthesize the results into a clear, helpful answer

If a question requires data from multiple sources, query each relevant agent and combine the results.
Always provide specific numbers and insights when available.
If you cannot answer a question, explain what information is missing."""

    async def query(
        self,
        user_input: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """
        Process a user query through the agent.

        Args:
            user_input: The user's question
            chat_history: Optional list of previous messages

        Returns:
            Dict with 'response' and 'intermediate_steps'
        """
        if not self._initialized:
            await self.initialize()

        # Build messages
        messages = [("system", self._build_system_prompt())]

        # Add chat history
        if chat_history:
            for msg in chat_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(("human", content))
                elif role == "assistant":
                    messages.append(("ai", content))

        # Add current query
        messages.append(("human", user_input))

        # Create prompt
        prompt = ChatPromptTemplate.from_messages(messages)

        # Run the agent loop
        intermediate_steps = []
        max_iterations = 5
        iteration = 0

        current_messages = prompt.format_messages()

        while iteration < max_iterations:
            iteration += 1

            # Get LLM response
            response = await self.llm_with_tools.ainvoke(current_messages)

            # Check for tool calls
            if hasattr(response, "tool_calls") and response.tool_calls:
                # Add the AI response with tool calls to messages first
                current_messages.append(response)

                # Process each tool call and collect results
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_call_id = tool_call["id"]

                    logger.info(
                        "tool_call",
                        tool=tool_name,
                        args=tool_args,
                    )

                    # Find and execute the tool
                    tool_result = None
                    for tool in self.tools:
                        if tool.name == tool_name:
                            tool_result = await tool.ainvoke(tool_args)
                            break

                    if tool_result is None:
                        tool_result = f"Tool {tool_name} not found"

                    intermediate_steps.append({
                        "tool": tool_name,
                        "input": tool_args,
                        "output": tool_result,
                    })

                    # Add tool result as ToolMessage with matching tool_call_id
                    current_messages.append(
                        ToolMessage(content=str(tool_result), tool_call_id=tool_call_id)
                    )
            else:
                # No tool calls, return the response
                return {
                    "response": response.content,
                    "intermediate_steps": intermediate_steps,
                }

        # Max iterations reached
        return {
            "response": "I apologize, but I wasn't able to complete the analysis. Please try rephrasing your question.",
            "intermediate_steps": intermediate_steps,
        }

    async def get_available_agents(self) -> list[dict[str, Any]]:
        """Get information about available data agents."""
        if not self._initialized:
            await self.initialize()

        return [
            {
                "name": agent.name,
                "description": agent.description,
                "skills": agent.get_skill_names(),
            }
            for agent in self.discovered_agents
        ]
