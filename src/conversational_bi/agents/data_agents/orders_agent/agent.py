"""Orders data agent implementation.

NOTE: This module provides backward compatibility. The production code uses
OrdersDataAgent from base_data_agent.py which is config-driven.
"""

from conversational_bi.agents.data_agents.base_data_agent import OrdersDataAgent

# Re-export for backward compatibility
__all__ = ["OrdersAgent"]

# Alias for backward compatibility
OrdersAgent = OrdersDataAgent
