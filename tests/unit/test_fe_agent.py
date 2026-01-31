"""Tests for the FE Agent with LangChain."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from conversational_bi.fe_agent.agent import FEAgent
from conversational_bi.fe_agent.tools.discovery import AgentDiscovery, DiscoveredAgent
from conversational_bi.fe_agent.tools.a2a_client import (
    create_a2a_tools,
    query_a2a_agent,
    _format_result_for_llm,
)


class TestDiscoveredAgent:
    """Test DiscoveredAgent dataclass."""

    def test_from_agent_card(self):
        """Should create agent from A2A card."""
        card = {
            "name": "Test Agent",
            "description": "A test agent",
            "version": "2.0.0",
            "skills": [
                {"id": "skill1", "name": "Skill One", "description": "First skill"},
                {"id": "skill2", "name": "Skill Two", "description": "Second skill"},
            ],
            "capabilities": {"streaming": False},
        }

        agent = DiscoveredAgent.from_agent_card(card, "http://localhost:8001/")

        assert agent.name == "Test Agent"
        assert agent.description == "A test agent"
        assert agent.base_url == "http://localhost:8001"  # Trailing slash removed
        assert agent.version == "2.0.0"
        assert len(agent.skills) == 2

    def test_get_skill_names(self):
        """Should return list of skill names."""
        agent = DiscoveredAgent(
            name="Test",
            description="Test",
            base_url="http://test",
            skills=[
                {"name": "Count", "id": "count"},
                {"name": "List", "id": "list"},
            ],
        )

        names = agent.get_skill_names()

        assert "Count" in names
        assert "List" in names

    def test_get_skill_descriptions(self):
        """Should format skills for prompts."""
        agent = DiscoveredAgent(
            name="Test",
            description="Test",
            base_url="http://test",
            skills=[
                {"name": "Count", "description": "Count items"},
            ],
        )

        desc = agent.get_skill_descriptions()

        assert "Count" in desc
        assert "Count items" in desc


class TestAgentDiscovery:
    """Test AgentDiscovery class."""

    @pytest.fixture
    def mock_agent_card(self):
        return {
            "name": "Customers Agent",
            "description": "Customer data agent",
            "version": "1.0.0",
            "skills": [{"id": "count", "name": "Count"}],
        }

    @pytest.mark.asyncio
    async def test_discover_all_success(self, mock_agent_card):
        """Should discover agents from URLs."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_agent_card
            mock_response.raise_for_status = MagicMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            discovery = AgentDiscovery(["http://localhost:8001"])
            agents = await discovery.discover_all()

            assert len(agents) == 1
            assert agents[0].name == "Customers Agent"

    @pytest.mark.asyncio
    async def test_discover_handles_failure(self):
        """Should handle discovery failures gracefully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection failed")
            )

            discovery = AgentDiscovery(["http://localhost:8001"])
            agents = await discovery.discover_all()

            assert len(agents) == 0

    def test_get_agent_by_name(self):
        """Should find agent by name."""
        discovery = AgentDiscovery([])
        discovery._discovered = [
            DiscoveredAgent(name="Customers Agent", description="", base_url="http://test"),
            DiscoveredAgent(name="Orders Agent", description="", base_url="http://test"),
        ]

        agent = discovery.get_agent_by_name("customers agent")

        assert agent is not None
        assert agent.name == "Customers Agent"

    def test_get_capabilities_summary(self):
        """Should generate capabilities summary."""
        discovery = AgentDiscovery([])
        discovery._discovered = [
            DiscoveredAgent(
                name="Test Agent",
                description="Test description",
                base_url="http://test",
                skills=[{"name": "Count", "description": "Count items"}],
            ),
        ]

        summary = discovery.get_capabilities_summary()

        assert "Test Agent" in summary
        assert "Test description" in summary
        assert "Count" in summary


class TestA2AClient:
    """Test A2A client functions."""

    @pytest.fixture
    def mock_agent(self):
        return DiscoveredAgent(
            name="Test Agent",
            description="Test",
            base_url="http://localhost:8001",
        )

    @pytest.mark.asyncio
    async def test_query_success(self, mock_agent):
        """Should handle successful query."""
        mock_response = {
            "jsonrpc": "2.0",
            "id": "1",
            "result": {
                "status": "completed",
                "artifacts": [
                    {
                        "parts": [
                            {"type": "text", "text": "Found 100 customers"},
                            {"type": "data", "data": {"rows": [{"count": 100}]}},
                        ]
                    }
                ],
            },
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=MagicMock(json=MagicMock(return_value=mock_response))
            )

            result = await query_a2a_agent(mock_agent, "How many customers?")

            assert result["success"] is True
            assert "100 customers" in result["text"]
            assert result["data"] is not None

    @pytest.mark.asyncio
    async def test_query_error_response(self, mock_agent):
        """Should handle error response from agent."""
        mock_response = {
            "jsonrpc": "2.0",
            "id": "1",
            "error": {"code": -32603, "message": "Internal error"},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=MagicMock(json=MagicMock(return_value=mock_response))
            )

            result = await query_a2a_agent(mock_agent, "Bad query")

            assert result["success"] is False
            assert "Internal error" in result["error"]

    @pytest.mark.asyncio
    async def test_query_timeout(self, mock_agent):
        """Should handle timeout."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            result = await query_a2a_agent(mock_agent, "Slow query")

            assert result["success"] is False
            assert "timed out" in result["error"]

    def test_format_result_success(self):
        """Should format successful result."""
        result = {
            "success": True,
            "text": "Found 100 items",
            "data": [{"id": 1}, {"id": 2}],
            "error": None,
        }

        formatted = _format_result_for_llm(result, "Test Agent")

        assert "Found 100 items" in formatted
        assert "2 rows" in formatted

    def test_format_result_error(self):
        """Should format error result."""
        result = {
            "success": False,
            "text": "",
            "data": None,
            "error": "Query failed",
        }

        formatted = _format_result_for_llm(result, "Test Agent")

        assert "Error" in formatted
        assert "Query failed" in formatted


class TestCreateA2ATools:
    """Test tool creation."""

    def test_creates_tools_for_agents(self):
        """Should create a tool for each agent."""
        agents = [
            DiscoveredAgent(
                name="Customers Agent",
                description="Customer data",
                base_url="http://localhost:8001",
                skills=[{"name": "Count", "description": "Count customers"}],
            ),
            DiscoveredAgent(
                name="Orders Agent",
                description="Order data",
                base_url="http://localhost:8002",
                skills=[{"name": "Revenue", "description": "Calculate revenue"}],
            ),
        ]

        tools = create_a2a_tools(agents)

        assert len(tools) == 2
        assert tools[0].name == "query_customers_agent"
        assert tools[1].name == "query_orders_agent"

    def test_tool_has_description(self):
        """Tool should have meaningful description."""
        agents = [
            DiscoveredAgent(
                name="Test Agent",
                description="Test description",
                base_url="http://test",
                skills=[{"name": "Skill1"}, {"name": "Skill2"}],
            ),
        ]

        tools = create_a2a_tools(agents)

        assert "Test Agent" in tools[0].description
        assert "Test description" in tools[0].description


class TestFEAgent:
    """Test FEAgent class."""

    @pytest.fixture
    def mock_config_loader(self):
        loader = MagicMock()
        loader.load_fe_agent_config.return_value = {
            "llm": {"model": "gpt-4o", "temperature": 0.0, "max_tokens": 4000},
            "prompts": {"router": "You are a BI assistant. ${AGENT_CAPABILITIES}"},
            "discovery": {"agent_urls": ["http://localhost:8001"]},
            "tools": {"query_agent": {"timeout_seconds": 30}},
        }
        loader.load_llm_config.return_value = {"default_model": "gpt-4o"}
        return loader

    def test_initialization(self, mock_config_loader):
        """Should initialize with config."""
        agent = FEAgent(config_loader=mock_config_loader)

        assert agent.llm is not None
        assert agent._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_discovers_agents(self, mock_config_loader):
        """Initialize should discover remote agents."""
        agent = FEAgent(config_loader=mock_config_loader)

        mock_discovered = [
            DiscoveredAgent(
                name="Test Agent",
                description="Test",
                base_url="http://test",
                skills=[],
            )
        ]

        with patch.object(agent.discovery, "discover_all", return_value=mock_discovered):
            await agent.initialize()

            assert agent._initialized is True
            assert len(agent.discovered_agents) == 1

    @pytest.mark.asyncio
    async def test_get_available_agents(self, mock_config_loader):
        """Should return info about available agents."""
        agent = FEAgent(config_loader=mock_config_loader)
        agent._initialized = True
        agent.discovered_agents = [
            DiscoveredAgent(
                name="Test Agent",
                description="Test description",
                base_url="http://test",
                skills=[{"name": "Count"}],
            )
        ]

        agents = await agent.get_available_agents()

        assert len(agents) == 1
        assert agents[0]["name"] == "Test Agent"
        assert "Count" in agents[0]["skills"]
