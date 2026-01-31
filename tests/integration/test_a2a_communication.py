"""Integration tests for A2A protocol communication."""

import pytest
import pytest_asyncio
import httpx

from conversational_bi.agents.base.a2a_server import A2AServer
from conversational_bi.agents.data_agents.customers_agent.agent import (
    create_customers_agent_card,
)


class TestA2AServerDiscovery:
    """Test A2A agent discovery via Agent Card."""

    @pytest.fixture
    def agent_card(self):
        """Sample agent card for testing."""
        return create_customers_agent_card("http://localhost:9999")

    @pytest.fixture
    def mock_handler(self):
        """Mock query handler."""
        async def handler(query: str):
            from conversational_bi.agents.data_agents.base_data_agent import QueryResult
            return QueryResult(
                success=True,
                text=f"Processed: {query}",
                data=[{"result": "test"}],
            )
        return handler

    @pytest.fixture
    def server(self, agent_card, mock_handler):
        """Create A2A server for testing."""
        return A2AServer(agent_card, mock_handler)

    @pytest.mark.asyncio
    async def test_agent_card_endpoint(self, server, agent_card):
        """Well-known endpoint should return agent card."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app)
        ) as client:
            response = await client.get(
                "http://test/.well-known/agent-card.json"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == agent_card["name"]
        assert "skills" in data

    @pytest.mark.asyncio
    async def test_health_endpoint(self, server, agent_card):
        """Health endpoint should return status."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app)
        ) as client:
            response = await client.get("http://test/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestA2ATaskHandling:
    """Test A2A task/send endpoint."""

    @pytest.fixture
    def mock_handler(self):
        """Mock query handler that returns structured data."""
        async def handler(query: str):
            from conversational_bi.agents.data_agents.base_data_agent import QueryResult
            return QueryResult(
                success=True,
                text=f"Found 100 results for: {query}",
                data=[{"id": 1, "value": "test"}],
            )
        return handler

    @pytest.fixture
    def server(self, mock_handler):
        """Create server with mock handler."""
        card = create_customers_agent_card()
        return A2AServer(card, mock_handler)

    @pytest.mark.asyncio
    async def test_task_send_valid_request(self, server):
        """Valid task/send request should return results."""
        request_body = {
            "jsonrpc": "2.0",
            "id": "test-1",
            "method": "tasks/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": "How many customers?"}],
                }
            },
        }

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app)
        ) as client:
            response = await client.post(
                "http://test/a2a/tasks/send",
                json=request_body,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == "test-1"
        assert "result" in data
        assert data["result"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_task_send_returns_artifacts(self, server):
        """Response should include artifacts with data."""
        request_body = {
            "jsonrpc": "2.0",
            "id": "test-2",
            "method": "tasks/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": "List customers"}],
                }
            },
        }

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app)
        ) as client:
            response = await client.post(
                "http://test/a2a/tasks/send",
                json=request_body,
            )

        data = response.json()
        artifacts = data["result"]["artifacts"]
        assert len(artifacts) > 0

        # Should have text and data parts
        parts = artifacts[0]["parts"]
        part_types = [p["type"] for p in parts]
        assert "text" in part_types
        assert "data" in part_types

    @pytest.mark.asyncio
    async def test_task_send_invalid_jsonrpc(self, server):
        """Invalid JSON-RPC version should return error."""
        request_body = {
            "jsonrpc": "1.0",  # Invalid version
            "id": "test-3",
            "method": "tasks/send",
            "params": {},
        }

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app)
        ) as client:
            response = await client.post(
                "http://test/a2a/tasks/send",
                json=request_body,
            )

        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_task_send_unknown_method(self, server):
        """Unknown method should return error."""
        request_body = {
            "jsonrpc": "2.0",
            "id": "test-4",
            "method": "unknown/method",
            "params": {},
        }

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app)
        ) as client:
            response = await client.post(
                "http://test/a2a/tasks/send",
                json=request_body,
            )

        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_task_send_missing_text(self, server):
        """Request without text should return error."""
        request_body = {
            "jsonrpc": "2.0",
            "id": "test-5",
            "method": "tasks/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [],  # No text part
                }
            },
        }

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.app)
        ) as client:
            response = await client.post(
                "http://test/a2a/tasks/send",
                json=request_body,
            )

        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32602


class TestAgentDiscoveryService:
    """Test agent discovery from orchestrator side."""

    @pytest.fixture
    def mock_server(self):
        """Create a mock A2A server."""
        async def handler(query: str):
            from conversational_bi.agents.data_agents.base_data_agent import QueryResult
            return QueryResult(success=True, text="OK", data=[])

        card = create_customers_agent_card("http://localhost:9999")
        return A2AServer(card, handler)

    @pytest.mark.asyncio
    async def test_discover_agent_from_url(self, mock_server):
        """Should be able to discover agent via HTTP."""
        from conversational_bi.agents.orchestrator.discovery import AgentDiscoveryService

        # We need to mock the HTTP call since we're not running a real server
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mock_server.app)
        ) as client:
            response = await client.get(
                "http://test/.well-known/agent-card.json"
            )

        card = response.json()
        assert card["name"] == "Customers Data Agent"
        assert len(card["skills"]) > 0
