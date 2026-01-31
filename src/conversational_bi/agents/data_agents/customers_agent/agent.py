"""Customers data agent implementation."""

import asyncpg

from conversational_bi.agents.data_agents.base_data_agent import BaseDataAgent
from conversational_bi.llm.openai_client import OpenAIClient
from conversational_bi.llm.prompts import CUSTOMERS_SQL_PROMPT


class CustomersAgent(BaseDataAgent):
    """
    Data agent for the customers table.

    Handles queries about customer counts, segmentation, lifetime value,
    regional distribution, and customer trends over time.
    """

    ALLOWED_COLUMNS = [
        "customer_id",
        "email",
        "full_name",
        "region",
        "segment",
        "created_at",
        "lifetime_value",
        "order_count",
        "last_order_date",
        "is_active",
    ]

    def __init__(self, db_pool: asyncpg.Pool, llm_client: OpenAIClient):
        """
        Initialize the customers agent.

        Args:
            db_pool: Database connection pool.
            llm_client: OpenAI client for SQL generation.
        """
        super().__init__(
            db_pool=db_pool,
            llm_client=llm_client,
            table_name="customers",
            allowed_columns=self.ALLOWED_COLUMNS,
        )

    def _get_system_prompt(self) -> str:
        """Return the system prompt for SQL generation."""
        return CUSTOMERS_SQL_PROMPT

    def _get_table_schema(self) -> str:
        """Return the table schema description."""
        return """
        Table: customers
        Columns:
        - customer_id: UUID (primary key)
        - email: VARCHAR(255) (unique)
        - full_name: VARCHAR(255)
        - region: VARCHAR(100) - values: 'North America', 'Europe', 'Asia Pacific', 'Latin America'
        - segment: VARCHAR(50) - values: 'Consumer', 'Corporate', 'Small Business'
        - created_at: TIMESTAMP WITH TIME ZONE
        - lifetime_value: DECIMAL(12, 2)
        - order_count: INTEGER
        - last_order_date: TIMESTAMP WITH TIME ZONE
        - is_active: BOOLEAN

        Use $1, $2, etc. for parameter placeholders.
        Always use aggregate functions (COUNT, SUM, AVG) for summary queries.
        """


def create_customers_agent_card(base_url: str = "http://localhost:8001") -> dict:
    """
    Create the Agent Card for the Customers Data Agent.

    This card is discoverable at: {base_url}/.well-known/agent-card.json

    Args:
        base_url: Base URL where the agent is hosted.

    Returns:
        Agent Card as a dictionary.
    """
    return {
        "name": "Customers Data Agent",
        "description": (
            "Specialized agent for customer data analytics. "
            "Handles queries about customer counts, segmentation, lifetime value, "
            "regional distribution, and customer trends over time."
        ),
        "url": f"{base_url}/",
        "version": "1.0.0",
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": [
            {
                "id": "customer_count",
                "name": "Customer Count",
                "description": "Count customers with optional filtering by region, segment, or date range",
                "tags": ["count", "customers", "aggregation"],
                "examples": [
                    "How many customers do we have?",
                    "Count customers in Europe",
                    "How many Corporate segment customers joined this year?",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain", "application/json"],
            },
            {
                "id": "customer_lifetime_value",
                "name": "Customer Lifetime Value Analysis",
                "description": "Analyze customer lifetime value (LTV) by segment, region, or cohort",
                "tags": ["ltv", "revenue", "customers", "aggregation"],
                "examples": [
                    "What is the average customer lifetime value?",
                    "Show LTV by customer segment",
                    "Top 10 customers by lifetime value",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain", "application/json"],
            },
            {
                "id": "customer_trends",
                "name": "Customer Trends",
                "description": "Time-series analysis of customer acquisition, churn, and activity",
                "tags": ["trends", "time-series", "customers"],
                "examples": [
                    "Show new customer sign-ups by month",
                    "Customer growth trend over the last year",
                    "When do we get the most new customers?",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["application/json"],
            },
            {
                "id": "customer_list",
                "name": "Customer List",
                "description": "Retrieve filtered list of customers with their details",
                "tags": ["list", "customers", "details"],
                "examples": [
                    "List all customers from Asia Pacific",
                    "Show inactive customers",
                    "Get customer IDs for Corporate segment",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["application/json"],
            },
        ],
    }
