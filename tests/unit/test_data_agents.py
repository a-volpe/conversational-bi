"""Tests for config-driven data agents."""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from conversational_bi.agents.data_agents.base_data_agent import (
    CustomersDataAgent,
    OrdersDataAgent,
    ProductsDataAgent,
    QueryResult,
)


class TestQueryResult:
    """Test QueryResult dataclass."""

    def test_success_result(self):
        """Should create successful result."""
        result = QueryResult(
            success=True,
            text="Found 10 results",
            data=[{"id": 1, "name": "test"}],
        )
        assert result.success is True
        assert result.text == "Found 10 results"
        assert len(result.data) == 1
        assert result.error is None

    def test_error_result(self):
        """Should create error result."""
        result = QueryResult(
            success=False,
            text="",
            error="Query failed",
        )
        assert result.success is False
        assert result.error == "Query failed"


class TestBaseDataAgent:
    """Test BaseDataAgent config-driven behavior."""

    @pytest.fixture
    def mock_db_pool(self):
        """Create mock database pool."""
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=AsyncMock())
        return pool

    @pytest.fixture
    def mock_config_loader(self, tmp_path):
        """Create mock config loader."""
        loader = MagicMock()

        # Mock agent config
        loader.load_agent_config.return_value = {
            "agent": {
                "name": "Test Agent",
                "description": "Test agent description",
                "version": "1.0.0",
                "port": 8001,
                "table": "customers",
            },
            "llm": {
                "model": "gpt-4o",
                "temperature": 0.0,
            },
            "prompts": {
                "sql_generator": "Generate SQL. ${COLUMN_INFO}"
            },
            "sql_validation": {
                "allowed_tables": ["customers"],
            },
            "skills": [
                {"id": "count", "name": "Count", "description": "Count items"}
            ],
        }

        # Mock schema
        loader.get_table_schema.return_value = {
            "description": "Customer data",
            "columns": [
                {"name": "customer_id", "type": "UUID", "primary_key": True},
                {"name": "email", "type": "VARCHAR(255)", "unique": True},
                {"name": "region", "type": "VARCHAR(100)", "allowed_values": ["North America", "Europe"]},
            ],
        }

        loader.get_column_info_string.return_value = """- customer_id (UUID) [PRIMARY KEY]
- email (VARCHAR(255)) [UNIQUE]
- region (VARCHAR(100)) [Values: North America, Europe]"""

        loader.load_llm_config.return_value = {
            "default_model": "gpt-4o",
        }

        return loader

    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = MagicMock()
        client.generate_sql = AsyncMock()
        return client

    def test_agent_card_generation(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Should generate valid agent card from config."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        card = agent.get_agent_card()

        assert card["name"] == "Test Agent"
        assert card["version"] == "1.0.0"
        assert "skills" in card
        assert len(card["skills"]) == 1

    def test_system_prompt_includes_columns(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """System prompt should include column info from schema."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        # The system prompt should have column info substituted
        assert "customer_id" in agent._system_prompt
        assert "email" in agent._system_prompt

    def test_allowed_columns_from_schema(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Allowed columns should be extracted from schema."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        assert "customer_id" in agent.allowed_columns
        assert "email" in agent.allowed_columns
        assert "region" in agent.allowed_columns

    @pytest.mark.asyncio
    async def test_process_query_success(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Should process query and return result."""
        # Setup mock SQL result
        sql_result = MagicMock()
        sql_result.sql = "SELECT COUNT(*) as count FROM customers"
        sql_result.parameters = []
        sql_result.explanation = "Count all customers"
        mock_llm_client.generate_sql.return_value = sql_result

        # Setup mock DB response
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[{"count": 100}])
        mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db_pool.acquire.return_value.__aexit__ = AsyncMock()

        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        result = await agent.process_query("How many customers?")

        assert result.success is True
        assert "count" in result.text.lower() or "100" in result.text

    @pytest.mark.asyncio
    async def test_process_query_handles_error(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Should handle errors gracefully."""
        mock_llm_client.generate_sql.side_effect = Exception("LLM error")

        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        result = await agent.process_query("Invalid query")

        assert result.success is False
        assert result.error is not None
        assert "LLM error" in result.error

    def test_format_response_no_results(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Should format empty results appropriately."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        response = agent._format_response("test query", [], "explanation")
        assert "No results" in response

    def test_format_response_single_aggregation(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Should format single aggregation result."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        response = agent._format_response(
            "count query",
            [{"count": 100}],
            "explanation",
        )
        assert "100" in response

    def test_format_response_multiple_rows(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Should format multiple row results."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        response = agent._format_response(
            "list query",
            [{"id": 1}, {"id": 2}, {"id": 3}],
            "Found matching records",
        )
        assert "3 results" in response


class TestParamConversion:
    """Test parameter conversion for asyncpg compatibility."""

    @pytest.fixture
    def mock_db_pool(self):
        """Create mock database pool."""
        return MagicMock()

    @pytest.fixture
    def mock_config_loader(self):
        """Create mock config loader."""
        loader = MagicMock()
        loader.load_agent_config.return_value = {
            "agent": {"name": "Test Agent", "port": 8001, "table": "customers"},
            "llm": {"model": "gpt-4o", "temperature": 0.0},
            "prompts": {"sql_generator": "Generate SQL. ${COLUMN_INFO}"},
            "sql_validation": {"allowed_tables": ["customers"]},
            "skills": [],
        }
        loader.get_table_schema.return_value = {
            "columns": [{"name": "id", "type": "UUID"}]
        }
        loader.get_column_info_string.return_value = "- id (UUID)"
        loader.load_llm_config.return_value = {"default_model": "gpt-4o"}
        return loader

    @pytest.fixture
    def mock_llm_client(self):
        return MagicMock()

    def test_convert_iso_datetime_with_z(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Should convert ISO 8601 datetime with Z suffix to datetime object."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        result = agent._convert_param("2025-10-01T00:00:00Z")
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 10
        assert result.day == 1

    def test_convert_iso_datetime_without_z(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Should convert ISO 8601 datetime without Z suffix."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        result = agent._convert_param("2025-10-01T14:30:00")
        assert isinstance(result, datetime)
        assert result.hour == 14
        assert result.minute == 30

    def test_convert_date_only(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Should convert date-only string to date object."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        result = agent._convert_param("2025-10-01")
        assert isinstance(result, date)
        assert not isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 10
        assert result.day == 1

    def test_convert_non_date_string(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Should leave non-date strings unchanged."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        result = agent._convert_param("North America")
        assert result == "North America"

    def test_convert_non_string_values(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """Should leave non-string values unchanged."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )

        assert agent._convert_param(100) == 100
        assert agent._convert_param(3.14) == 3.14
        assert agent._convert_param(None) is None


class TestConcreteAgents:
    """Test concrete agent implementations."""

    @pytest.fixture
    def mock_db_pool(self):
        """Create mock database pool."""
        return MagicMock()

    @pytest.fixture
    def mock_config_loader(self):
        """Create mock config loader that returns appropriate config for each agent."""
        loader = MagicMock()

        def load_agent_config(name):
            return {
                "agent": {
                    "name": f"{name.capitalize()} Agent",
                    "description": f"Agent for {name}",
                    "version": "1.0.0",
                    "port": 8001 if name == "customers" else (8002 if name == "orders" else 8003),
                    "table": name,
                },
                "llm": {"model": "gpt-4o", "temperature": 0.0},
                "prompts": {"sql_generator": "Generate SQL. ${COLUMN_INFO}"},
                "sql_validation": {"allowed_tables": [name]},
                "skills": [],
            }

        loader.load_agent_config.side_effect = load_agent_config
        loader.get_table_schema.return_value = {
            "columns": [{"name": "id", "type": "UUID", "primary_key": True}]
        }
        loader.get_column_info_string.return_value = "- id (UUID)"
        loader.load_llm_config.return_value = {"default_model": "gpt-4o"}

        return loader

    @pytest.fixture
    def mock_llm_client(self):
        return MagicMock()

    def test_customers_agent_initializes(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """CustomersDataAgent should initialize correctly."""
        agent = CustomersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )
        assert agent.agent_name == "customers"
        assert agent.table_name == "customers"

    def test_orders_agent_initializes(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """OrdersDataAgent should initialize correctly."""
        agent = OrdersDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )
        assert agent.agent_name == "orders"
        assert agent.table_name == "orders"

    def test_products_agent_initializes(self, mock_db_pool, mock_config_loader, mock_llm_client):
        """ProductsDataAgent should initialize correctly."""
        agent = ProductsDataAgent(
            mock_db_pool,
            llm_client=mock_llm_client,
            config_loader=mock_config_loader,
        )
        assert agent.agent_name == "products"
        assert agent.table_name == "products"
