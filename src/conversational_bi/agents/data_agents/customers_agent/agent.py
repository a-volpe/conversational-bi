"""Customers data agent implementation.

NOTE: This module provides backward compatibility. The production code uses
CustomersDataAgent from base_data_agent.py which is config-driven.
"""

from conversational_bi.agents.data_agents.base_data_agent import CustomersDataAgent

# Re-export for backward compatibility
__all__ = ["CustomersAgent"]

# Alias for backward compatibility
CustomersAgent = CustomersDataAgent
