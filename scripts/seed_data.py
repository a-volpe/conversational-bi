#!/usr/bin/env python
"""
Seed the database with sample data for development/testing.

Usage:
    python scripts/seed_data.py

Environment:
    DATABASE_URL: PostgreSQL connection string (required)
    SEED_CUSTOMERS: Number of customers to create (default: 100)
    SEED_ORDERS: Number of orders to create (default: 500)
"""

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import asyncpg

# Sample data configuration
REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America"]
SEGMENTS = ["Consumer", "Corporate", "Small Business"]
CATEGORIES = ["Electronics", "Clothing", "Home & Garden", "Sports", "Books"]
ORDER_STATUSES = ["pending", "shipped", "delivered", "cancelled"]

PRODUCTS_DATA = [
    ("Electronics", "Smartphones", "Smartphone Pro X", 999.99, 650.00),
    ("Electronics", "Smartphones", "Smartphone Lite", 499.99, 300.00),
    ("Electronics", "Laptops", "UltraBook 15", 1299.99, 850.00),
    ("Electronics", "Laptops", "Gaming Laptop", 1799.99, 1200.00),
    ("Electronics", "Accessories", "Wireless Earbuds", 149.99, 60.00),
    ("Clothing", "Men", "Premium T-Shirt", 49.99, 15.00),
    ("Clothing", "Men", "Casual Jeans", 79.99, 25.00),
    ("Clothing", "Women", "Summer Dress", 89.99, 30.00),
    ("Clothing", "Women", "Designer Handbag", 299.99, 100.00),
    ("Clothing", "Kids", "Kids Sneakers", 59.99, 20.00),
    ("Home & Garden", "Furniture", "Office Chair", 249.99, 120.00),
    ("Home & Garden", "Furniture", "Standing Desk", 449.99, 200.00),
    ("Home & Garden", "Kitchen", "Coffee Maker", 129.99, 50.00),
    ("Home & Garden", "Garden", "Garden Tool Set", 89.99, 35.00),
    ("Sports", "Fitness", "Yoga Mat Premium", 49.99, 15.00),
    ("Sports", "Fitness", "Dumbbell Set", 199.99, 80.00),
    ("Sports", "Outdoor", "Camping Tent", 299.99, 120.00),
    ("Sports", "Team Sports", "Basketball", 29.99, 10.00),
    ("Books", "Fiction", "Bestseller Novel", 24.99, 8.00),
    ("Books", "Non-Fiction", "Business Guide", 34.99, 12.00),
]

FIRST_NAMES = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa", "William", "Jennifer"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Martinez", "Wilson"]


async def seed_database(dsn: str, num_customers: int = 100, num_orders: int = 500):
    """Seed the database with sample data."""
    ssl = "require" if "neon.tech" in dsn else None
    conn = await asyncpg.connect(dsn=dsn, ssl=ssl)

    try:
        # Check if data already exists
        count = await conn.fetchval("SELECT COUNT(*) FROM customers")
        if count > 0:
            print(f"Database already has {count} customers. Use --force to reseed.")
            return

        print("Seeding products...")
        product_ids = await seed_products(conn)
        print(f"  Created {len(product_ids)} products")

        print("Seeding customers...")
        customer_ids = await seed_customers(conn, num_customers)
        print(f"  Created {len(customer_ids)} customers")

        print("Seeding orders...")
        await seed_orders(conn, customer_ids, product_ids, num_orders)
        print(f"  Created {num_orders} orders")

        print("\nSeeding complete!")

    finally:
        await conn.close()


async def seed_products(conn: asyncpg.Connection) -> list[str]:
    """Insert sample products and return their IDs."""
    product_ids = []

    for i, (category, subcategory, name, price, cost) in enumerate(PRODUCTS_DATA):
        product_id = str(uuid4())
        sku = f"SKU-{category[:3].upper()}-{i+1:04d}"

        await conn.execute(
            """
            INSERT INTO products (product_id, sku, name, category, subcategory, unit_price, unit_cost, stock_quantity, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (sku) DO NOTHING
            """,
            product_id,
            sku,
            name,
            category,
            subcategory,
            Decimal(str(price)),
            Decimal(str(cost)),
            random.randint(10, 500),
            True,
        )
        product_ids.append(product_id)

    return product_ids


async def seed_customers(conn: asyncpg.Connection, count: int) -> list[str]:
    """Insert sample customers and return their IDs."""
    customer_ids = []
    base_date = datetime.now() - timedelta(days=730)  # 2 years ago

    for i in range(count):
        customer_id = str(uuid4())
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        email = f"{first_name.lower()}.{last_name.lower()}.{i}@example.com"

        created_at = base_date + timedelta(days=random.randint(0, 730))

        await conn.execute(
            """
            INSERT INTO customers (customer_id, email, full_name, region, segment, created_at, lifetime_value, order_count, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (email) DO NOTHING
            """,
            customer_id,
            email,
            f"{first_name} {last_name}",
            random.choice(REGIONS),
            random.choice(SEGMENTS),
            created_at,
            Decimal("0.00"),
            0,
            random.random() > 0.1,  # 90% active
        )
        customer_ids.append(customer_id)

    return customer_ids


async def seed_orders(
    conn: asyncpg.Connection,
    customer_ids: list[str],
    product_ids: list[str],
    count: int,
) -> None:
    """Insert sample orders and update customer stats."""
    base_date = datetime.now() - timedelta(days=365)  # 1 year ago
    customer_stats = {}  # Track LTV and order count per customer

    for _ in range(count):
        order_id = str(uuid4())
        customer_id = random.choice(customer_ids)
        product_id = random.choice(product_ids)

        quantity = random.randint(1, 5)
        unit_price = Decimal(str(random.uniform(20, 500))).quantize(Decimal("0.01"))
        total_amount = unit_price * quantity

        order_date = base_date + timedelta(days=random.randint(0, 365))
        status = random.choices(
            ORDER_STATUSES,
            weights=[0.1, 0.2, 0.65, 0.05],  # Most orders delivered
        )[0]

        await conn.execute(
            """
            INSERT INTO orders (order_id, customer_id, product_id, quantity, unit_price, total_amount, order_date, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            order_id,
            customer_id,
            product_id,
            quantity,
            unit_price,
            total_amount,
            order_date,
            status,
        )

        # Track stats for customer update
        if customer_id not in customer_stats:
            customer_stats[customer_id] = {"ltv": Decimal("0"), "count": 0, "last_date": None}

        if status != "cancelled":
            customer_stats[customer_id]["ltv"] += total_amount
            customer_stats[customer_id]["count"] += 1
            if customer_stats[customer_id]["last_date"] is None or order_date > customer_stats[customer_id]["last_date"]:
                customer_stats[customer_id]["last_date"] = order_date

    # Update customer stats
    for customer_id, stats in customer_stats.items():
        await conn.execute(
            """
            UPDATE customers
            SET lifetime_value = $2, order_count = $3, last_order_date = $4
            WHERE customer_id = $1
            """,
            customer_id,
            stats["ltv"],
            stats["count"],
            stats["last_date"],
        )


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("Error: DATABASE_URL not set.")
        sys.exit(1)

    num_customers = int(os.environ.get("SEED_CUSTOMERS", 100))
    num_orders = int(os.environ.get("SEED_ORDERS", 500))

    print(f"Seeding database with {num_customers} customers and {num_orders} orders...")
    asyncio.run(seed_database(dsn, num_customers, num_orders))


if __name__ == "__main__":
    main()
