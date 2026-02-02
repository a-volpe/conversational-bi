"""Base class for data agents with config-driven SQL validation and execution."""

from abc import ABC
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg
import structlog

from conversational_bi.common.exceptions import QueryExecutionError
from conversational_bi.common.sql_validator import SQLValidator
from conversational_bi.config.loader import ConfigLoader, get_config_loader
from conversational_bi.llm.openai_client import OpenAIClient

logger = structlog.get_logger()


@dataclass
class QueryResult:
    """Result of a data query."""

    success: bool
    text: str
    data: list[dict[str, Any]] | None = None
    error: str | None = None


class BaseDataAgent(ABC):
    """
    Base class for config-driven data agents with SQL validation and execution.

    Loads configuration from YAML files and generates SQL using LLM.
    """

    def __init__(
        self,
        agent_name: str,
        db_pool: asyncpg.Pool,
        llm_client: OpenAIClient | None = None,
        config_loader: ConfigLoader | None = None,
    ):
        """
        Initialize the data agent.

        Args:
            agent_name: Name of the agent (e.g., 'customers', 'orders').
            db_pool: Database connection pool.
            llm_client: OpenAI client for SQL generation.
            config_loader: Configuration loader (uses global if not provided).
        """
        self.agent_name = agent_name
        self.db_pool = db_pool
        self.config_loader = config_loader or get_config_loader()

        # Load agent config
        self.agent_config = self.config_loader.load_agent_config(agent_name)

        # Extract table name and load schema
        self.table_name = self.agent_config["agent"]["table"]
        self.table_schema = self.config_loader.get_table_schema(self.table_name)

        # Get allowed columns from schema
        self.allowed_columns = [col["name"] for col in self.table_schema.get("columns", [])]

        # Setup SQL validator from config
        sql_validation = self.agent_config.get("sql_validation", {})
        self.sql_validator = SQLValidator(
            allowed_tables=sql_validation.get("allowed_tables", [self.table_name]),
            allowed_columns=self.allowed_columns,
        )

        # Initialize LLM client
        self.llm_client = llm_client
        if not self.llm_client:
            llm_config = self.config_loader.load_llm_config()
            self.llm_client = OpenAIClient(
                model=self.agent_config["llm"].get("model", llm_config.get("default_model", "gpt-5-mini")),
                temperature=self.agent_config["llm"].get("temperature"),
                reasoning_effort=self.agent_config["llm"].get("reasoning_effort", "low"),
            )

        # Build system prompt with column info
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build the system prompt from config with schema info."""
        prompt_template = self.agent_config["prompts"]["sql_generator"]
        column_info = self.config_loader.get_column_info_string(self.table_name)
        return prompt_template.replace("${COLUMN_INFO}", column_info)

    def get_agent_card(self) -> dict:
        """Get the A2A Agent Card for discovery."""
        config = self.agent_config["agent"]
        skills = self.agent_config.get("skills", [])

        return {
            "name": config["name"],
            "description": config.get("description", f"Data agent for {self.table_name}"),
            "url": f"http://localhost:{config['port']}/",
            "version": config.get("version", "1.0.0"),
            "defaultInputModes": ["text/plain", "application/json"],
            "defaultOutputModes": ["text/plain", "application/json"],
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
            },
            "skills": skills,
        }

    async def process_query(self, user_query: str) -> QueryResult:
        """
        Process a natural language query.

        Args:
            user_query: The user's question in natural language.

        Returns:
            QueryResult with success status, text response, and optional data.
        """
        try:
            logger.info(
                "processing_query",
                agent=self.agent_name,
                query=user_query[:100],
            )

            # Generate SQL from natural language
            sql_result = await self.llm_client.generate_sql(
                user_query=user_query,
                system_prompt=self._system_prompt,
                table_schema=self._get_table_schema_description(),
            )

            # Validate SQL for safety
            self.sql_validator.validate(sql_result.sql)

            # Execute the query
            data = await self._execute_query(sql_result.sql, sql_result.parameters)

            # Format response
            text = self._format_response(user_query, data, sql_result.explanation)

            return QueryResult(
                success=True,
                text=text,
                data=data,
            )

        except Exception as e:
            logger.error(
                "query_failed",
                agent=self.agent_name,
                error=str(e),
            )
            return QueryResult(
                success=False,
                text="",
                error=str(e),
            )

    def _get_table_schema_description(self) -> str:
        """Get table schema description for LLM context."""
        today = date.today().isoformat()
        lines = [f"Table: {self.table_name}", f"Today's date: {today}", "", "Columns:"]
        for col in self.table_schema.get("columns", []):
            desc = f"- {col['name']}: {col['type']}"
            if col.get("description"):
                desc += f" - {col['description']}"
            if col.get("allowed_values"):
                desc += f" [Values: {', '.join(col['allowed_values'])}]"
            lines.append(desc)

        lines.append("")
        lines.append("Use $1, $2, etc. for parameter placeholders.")
        lines.append("Parameters must be literal values (e.g., '2025-11-01'), NOT SQL expressions.")
        lines.append("Always use aggregate functions (COUNT, SUM, AVG) for summary queries.")

        return "\n".join(lines)

    async def _execute_query(
        self,
        sql: str,
        params: list[Any],
    ) -> list[dict[str, Any]]:
        """
        Execute SQL query against the database.

        Args:
            sql: The SQL query to execute.
            params: Parameter values for the query.

        Returns:
            List of result rows as dictionaries.

        Raises:
            QueryExecutionError: If the query fails.
        """
        try:
            # Convert ISO 8601 date strings to datetime objects for asyncpg
            converted_params = [self._convert_param(p) for p in params]
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(sql, *converted_params)
                return [self._serialize_row(row) for row in rows]
        except Exception as e:
            logger.error("sql_execution_failed", sql=sql[:100], error=str(e))
            raise QueryExecutionError(f"Query failed: {e}") from e

    def _convert_param(self, value: Any) -> Any:
        """Convert parameter values to types asyncpg expects."""
        if not isinstance(value, str):
            return value

        # Try parsing as integer (e.g., '10' for stock quantity)
        try:
            return int(value)
        except ValueError:
            pass

        # Try parsing as float (e.g., '99.99' for prices)
        try:
            return float(value)
        except ValueError:
            pass

        # Try parsing as ISO 8601 datetime with timezone offset (e.g., '2025-10-01T00:00:00+00:00')
        if "T" in value and ("+" in value or value.endswith("Z")):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Try parsing as ISO 8601 datetime without timezone (e.g., '2025-10-01T00:00:00')
        if "T" in value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass

        # Try parsing as date (e.g., '2025-10-01')
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass

        return value

    def _serialize_row(self, row: asyncpg.Record) -> dict[str, Any]:
        """Convert a database row to a JSON-serializable dict."""
        result = {}
        for key, value in dict(row).items():
            if isinstance(value, Decimal):
                result[key] = float(value)
            elif isinstance(value, UUID):
                result[key] = str(value)
            elif isinstance(value, (datetime, date)):
                result[key] = value.isoformat()
            else:
                result[key] = value
        return result

    def _format_response(
        self,
        query: str,
        data: list[dict[str, Any]],
        explanation: str,
    ) -> str:
        """
        Format query results into a text response.

        Args:
            query: The original user query.
            data: The query result data.
            explanation: SQL explanation from LLM.

        Returns:
            Formatted text response.
        """
        if not data:
            return "No results found."

        row_count = len(data)

        # For single aggregation results
        if row_count == 1 and len(data[0]) <= 3:
            values = ", ".join(f"{k}: {v}" for k, v in data[0].items())
            return f"Result: {values}"

        return f"Found {row_count} results. {explanation}"


# Concrete implementations for each data agent


class CustomersDataAgent(BaseDataAgent):
    """Data agent for the customers table."""

    def __init__(self, db_pool: asyncpg.Pool, **kwargs):
        super().__init__("customers", db_pool, **kwargs)


class OrdersDataAgent(BaseDataAgent):
    """Data agent for the orders table."""

    def __init__(self, db_pool: asyncpg.Pool, **kwargs):
        super().__init__("orders", db_pool, **kwargs)


class ProductsDataAgent(BaseDataAgent):
    """Data agent for the products table."""

    def __init__(self, db_pool: asyncpg.Pool, **kwargs):
        super().__init__("products", db_pool, **kwargs)
