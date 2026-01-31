"""LLM prompts for the conversational BI application."""

from conversational_bi.llm.prompts.sql_generation import (
    BASE_SQL_PROMPT,
    CUSTOMERS_SQL_PROMPT,
    ORDERS_SQL_PROMPT,
    PRODUCTS_SQL_PROMPT,
)

__all__ = [
    "BASE_SQL_PROMPT",
    "CUSTOMERS_SQL_PROMPT",
    "ORDERS_SQL_PROMPT",
    "PRODUCTS_SQL_PROMPT",
]
