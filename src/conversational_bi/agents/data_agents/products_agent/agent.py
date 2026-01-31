"""Products data agent implementation."""

import asyncpg

from conversational_bi.agents.data_agents.base_data_agent import BaseDataAgent
from conversational_bi.llm.openai_client import OpenAIClient
from conversational_bi.llm.prompts import PRODUCTS_SQL_PROMPT


class ProductsAgent(BaseDataAgent):
    """
    Data agent for the products table.

    Handles queries about product catalog, pricing, inventory, and categories.
    """

    ALLOWED_COLUMNS = [
        "product_id",
        "sku",
        "name",
        "category",
        "subcategory",
        "unit_price",
        "unit_cost",
        "stock_quantity",
        "is_active",
        "created_at",
        "updated_at",
    ]

    def __init__(self, db_pool: asyncpg.Pool, llm_client: OpenAIClient):
        """
        Initialize the products agent.

        Args:
            db_pool: Database connection pool.
            llm_client: OpenAI client for SQL generation.
        """
        super().__init__(
            db_pool=db_pool,
            llm_client=llm_client,
            table_name="products",
            allowed_columns=self.ALLOWED_COLUMNS,
        )

    def _get_system_prompt(self) -> str:
        """Return the system prompt for SQL generation."""
        return PRODUCTS_SQL_PROMPT

    def _get_table_schema(self) -> str:
        """Return the table schema description."""
        return """
        Table: products
        Columns:
        - product_id: UUID (primary key)
        - sku: VARCHAR(50) (unique)
        - name: VARCHAR(255)
        - category: VARCHAR(100) - values: 'Electronics', 'Clothing', 'Home & Garden', 'Sports', 'Books'
        - subcategory: VARCHAR(100)
        - unit_price: DECIMAL(10, 2)
        - unit_cost: DECIMAL(10, 2)
        - stock_quantity: INTEGER
        - is_active: BOOLEAN
        - created_at: TIMESTAMP WITH TIME ZONE
        - updated_at: TIMESTAMP WITH TIME ZONE

        Use $1, $2, etc. for parameter placeholders.
        Always use aggregate functions (COUNT, SUM, AVG) for summary queries.
        Margin = unit_price - unit_cost
        """


def create_products_agent_card(base_url: str = "http://localhost:8003") -> dict:
    """
    Create the Agent Card for the Products Data Agent.

    Args:
        base_url: Base URL where the agent is hosted.

    Returns:
        Agent Card as a dictionary.
    """
    return {
        "name": "Products Data Agent",
        "description": (
            "Specialized agent for product catalog analytics. "
            "Handles queries about product counts, pricing, margins, "
            "inventory levels, and category analysis."
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
                "id": "product_count",
                "name": "Product Catalog Stats",
                "description": "Count products by category, status, or other attributes",
                "tags": ["count", "products", "catalog"],
                "examples": [
                    "How many products do we have?",
                    "Products by category",
                    "How many active products in Electronics?",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain", "application/json"],
            },
            {
                "id": "category_stats",
                "name": "Category Analysis",
                "description": "Analyze products by category with pricing and margin metrics",
                "tags": ["category", "pricing", "margin"],
                "examples": [
                    "Average price by category",
                    "Which category has the highest margin?",
                    "Category breakdown with product counts",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["application/json"],
            },
            {
                "id": "inventory_status",
                "name": "Inventory Analysis",
                "description": "Analyze stock levels and identify low inventory",
                "tags": ["inventory", "stock", "products"],
                "examples": [
                    "Products with low stock",
                    "Total inventory value",
                    "Out of stock products",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain", "application/json"],
            },
            {
                "id": "product_search",
                "name": "Product Search",
                "description": "Search and list products by various criteria",
                "tags": ["search", "list", "products"],
                "examples": [
                    "List all Electronics products",
                    "Find products priced over $100",
                    "Show newest products",
                ],
                "inputModes": ["text/plain"],
                "outputModes": ["application/json"],
            },
        ],
    }
