"""Customers data agent implementation.

NOTE: This module provides backward compatibility. The production code uses
CustomersDataAgent from base_data_agent.py which is config-driven.
"""

from conversational_bi.agents.data_agents.base_data_agent import CustomersDataAgent

# Re-export for backward compatibility
__all__ = ["CustomersAgent", "create_customers_agent_card"]

# Alias for backward compatibility
CustomersAgent = CustomersDataAgent

# TODO: isn't working: need to pass also table schemas to the agent card for better discovery
def create_customers_agent_card(base_url: str = "http://localhost:8001") -> dict:
    """
    Create the Agent Card for the Customers Data Agent.

    NOTE: This function is deprecated. Use CustomersDataAgent.get_agent_card() instead.

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
