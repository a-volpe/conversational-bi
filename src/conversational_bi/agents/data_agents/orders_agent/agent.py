"""Orders data agent implementation.

NOTE: This module provides backward compatibility. The production code uses
OrdersDataAgent from base_data_agent.py which is config-driven.
"""

from conversational_bi.agents.data_agents.base_data_agent import OrdersDataAgent

# Re-export for backward compatibility
__all__ = ["OrdersAgent", "create_orders_agent_card"]

# Alias for backward compatibility
OrdersAgent = OrdersDataAgent


def create_orders_agent_card(base_url: str = "http://localhost:8002") -> dict:
    """
    Create the Agent Card for the Orders Data Agent.

    NOTE: This function is deprecated. Use OrdersDataAgent.get_agent_card() instead.

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
