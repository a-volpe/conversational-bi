"""Products data agent implementation.

NOTE: This module provides backward compatibility. The production code uses
ProductsDataAgent from base_data_agent.py which is config-driven.
"""

from conversational_bi.agents.data_agents.base_data_agent import ProductsDataAgent

# Re-export for backward compatibility
__all__ = ["ProductsAgent", "create_products_agent_card"]

# Alias for backward compatibility
ProductsAgent = ProductsDataAgent


def create_products_agent_card(base_url: str = "http://localhost:8003") -> dict:
    """
    Create the Agent Card for the Products Data Agent.

    NOTE: This function is deprecated. Use ProductsDataAgent.get_agent_card() instead.

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
