"""Shared pytest fixtures for all tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for unit tests."""
    client = AsyncMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content="Mocked response",
                    function_call=None,
                    tool_calls=None,
                )
            )
        ]
    )
    return client


@pytest_asyncio.fixture
async def mock_db_pool():
    """Mock database connection pool for unit tests."""
    pool = AsyncMock()

    # Mock connection context manager
    conn = AsyncMock()
    conn.fetch.return_value = [{"count": 100}]
    conn.fetchrow.return_value = {"total": 1500.00}
    conn.fetchval.return_value = 100

    # Setup context manager
    pool.acquire.return_value.__aenter__.return_value = conn
    pool.acquire.return_value.__aexit__.return_value = None

    return pool


@pytest.fixture
def sample_customers_data():
    """Sample customer data for testing."""
    return [
        {
            "customer_id": "abc-123",
            "email": "john@example.com",
            "full_name": "John Doe",
            "region": "Europe",
            "segment": "Corporate",
            "lifetime_value": 1500.00,
            "order_count": 5,
        },
        {
            "customer_id": "def-456",
            "email": "jane@example.com",
            "full_name": "Jane Smith",
            "region": "North America",
            "segment": "Consumer",
            "lifetime_value": 750.00,
            "order_count": 3,
        },
    ]


@pytest.fixture
def sample_orders_data():
    """Sample order data for testing."""
    return [
        {
            "order_id": "ord-001",
            "customer_id": "abc-123",
            "product_id": "prod-001",
            "quantity": 2,
            "total_amount": 500.00,
            "status": "delivered",
        },
        {
            "order_id": "ord-002",
            "customer_id": "abc-123",
            "product_id": "prod-002",
            "quantity": 1,
            "total_amount": 250.00,
            "status": "shipped",
        },
    ]


@pytest.fixture
def sample_products_data():
    """Sample product data for testing."""
    return [
        {
            "product_id": "prod-001",
            "sku": "ELEC-001",
            "name": "Laptop Pro",
            "category": "Electronics",
            "subcategory": "Computers",
            "unit_price": 1200.00,
            "stock_quantity": 50,
        },
        {
            "product_id": "prod-002",
            "sku": "ELEC-002",
            "name": "Wireless Mouse",
            "category": "Electronics",
            "subcategory": "Accessories",
            "unit_price": 45.00,
            "stock_quantity": 200,
        },
    ]
