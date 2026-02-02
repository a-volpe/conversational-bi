"""Products data agent implementation.

NOTE: This module provides backward compatibility. The production code uses
ProductsDataAgent from base_data_agent.py which is config-driven.
"""

from conversational_bi.agents.data_agents.base_data_agent import ProductsDataAgent

# Re-export for backward compatibility
__all__ = ["ProductsAgent"]

# Alias for backward compatibility
ProductsAgent = ProductsDataAgent
