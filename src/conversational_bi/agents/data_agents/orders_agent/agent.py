"""Orders data agent implementation."""

import asyncpg

from conversational_bi.agents.data_agents.base_data_agent import BaseDataAgent
from conversational_bi.llm.openai_client import OpenAIClient
from conversational_bi.llm.prompts import ORDERS_SQL_PROMPT


class OrdersAgent(BaseDataAgent):
    """
    Data agent for the orders table.

    Handles queries about revenue, order counts, trends, and performance.
    """

    ALLOWED_COLUMNS = [
        "order_id",
        "customer_id",
        "product_id",
        "quantity",
        "unit_price",
        "total_amount",
        "discount",
        "order_date",
        "status",
        "ship_date",
        "ship_region",
    ]

    def __init__(self, db_pool: asyncpg.Pool, llm_client: OpenAIClient):
        """
        Initialize the orders agent.

        Args:
            db_pool: Database connection pool.
            llm_client: OpenAI client for SQL generation.
        """
        super().__init__(
            db_pool=db_pool,
            llm_client=llm_client,
            table_name="orders",
            allowed_columns=self.ALLOWED_COLUMNS,
        )

    def _get_system_prompt(self) -> str:
        """Return the system prompt for SQL generation."""
        return ORDERS_SQL_PROMPT

    def _get_table_schema(self) -> str:
        """Return the table schema description."""
        return """
        Table: orders
        Columns:
        - order_id: UUID (primary key)
        - customer_id: UUID (foreign key to customers)
        - product_id: UUID (foreign key to products)
        - quantity: INTEGER
        - unit_price: DECIMAL(10, 2)
        - total_amount: DECIMAL(12, 2)
        - discount: DECIMAL(5, 2)
        - order_date: TIMESTAMP WITH TIME ZONE
        - status: VARCHAR(50) - values: 'pending', 'shipped', 'delivered', 'cancelled'
        - ship_date: TIMESTAMP WITH TIME ZONE
        - ship_region: VARCHAR(100)

        Use $1, $2, etc. for parameter placeholders.
        Always use aggregate functions (COUNT, SUM, AVG) for summary queries.
        """


def create_orders_agent_card(base_url: str = "http://localhost:8002") -> dict:
    """
    Create the Agent Card for the Orders Data Agent.

    Args:
        base_url: Base URL where the agent is hosted.

    Returns:
        Agent Card as a dictionary.
    """
    return {
        "name": "Orders Data Agent",
        "description": (
            "Specialized agent for order and revenue analytics. "
            "Handles queries about revenue totals, order counts, trends, "
            "and fulfillment status."
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
                "id": "revenue_total",
                "name": "Revenue Analysis",
                "description": "Calculate total revenue with optional filters by period, status, or region",
                "tags": ["revenue", "orders", "aggregation"],
                "examples": [
                    "What is our total revenue?",
                    "Revenue for Q4 2024",
                    "Total revenue from delivered orders",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain", "application/json"],
            },
            {
                "id": "order_trends",
                "name": "Order Trends",
                "description": "Time-series analysis of order volumes and revenue",
                "tags": ["trends", "time-series", "orders"],
                "examples": [
                    "Show monthly order counts",
                    "Revenue trend over the last 6 months",
                    "Daily order volume this week",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["application/json"],
            },
            {
                "id": "avg_order_value",
                "name": "Average Order Value",
                "description": "Calculate average order value with optional grouping",
                "tags": ["aov", "orders", "aggregation"],
                "examples": [
                    "What is our average order value?",
                    "AOV by customer segment",
                    "Average order size by product category",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain", "application/json"],
            },
            {
                "id": "order_status",
                "name": "Order Status Analysis",
                "description": "Analyze orders by fulfillment status",
                "tags": ["status", "orders", "fulfillment"],
                "examples": [
                    "How many orders are pending?",
                    "Orders by status",
                    "Unfulfilled orders older than 7 days",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain", "application/json"],
            },
        ],
    }
