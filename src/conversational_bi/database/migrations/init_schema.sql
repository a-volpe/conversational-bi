-- Conversational BI - Initial Schema
-- E-Commerce Analytics: Customers, Products, Orders

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- Table: customers
-- ============================================
CREATE TABLE IF NOT EXISTS customers (
    customer_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    full_name       VARCHAR(255) NOT NULL,
    region          VARCHAR(100) NOT NULL,  -- 'North America', 'Europe', 'Asia Pacific', 'Latin America'
    segment         VARCHAR(50) NOT NULL,   -- 'Consumer', 'Corporate', 'Small Business'
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    lifetime_value  DECIMAL(12, 2) DEFAULT 0.00,
    order_count     INTEGER DEFAULT 0,
    last_order_date TIMESTAMP WITH TIME ZONE,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_customers_region ON customers(region);
CREATE INDEX IF NOT EXISTS idx_customers_segment ON customers(segment);
CREATE INDEX IF NOT EXISTS idx_customers_created_at ON customers(created_at);

-- ============================================
-- Table: products
-- ============================================
CREATE TABLE IF NOT EXISTS products (
    product_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku             VARCHAR(50) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    category        VARCHAR(100) NOT NULL,  -- 'Electronics', 'Clothing', 'Home & Garden'
    subcategory     VARCHAR(100) NOT NULL,
    unit_price      DECIMAL(10, 2) NOT NULL,
    unit_cost       DECIMAL(10, 2) NOT NULL,
    stock_quantity  INTEGER DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_subcategory ON products(subcategory);

-- ============================================
-- Table: orders
-- ============================================
CREATE TABLE IF NOT EXISTS orders (
    order_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES customers(customer_id),
    product_id      UUID NOT NULL REFERENCES products(product_id),
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price      DECIMAL(10, 2) NOT NULL,
    total_amount    DECIMAL(12, 2) NOT NULL,
    discount        DECIMAL(5, 2) DEFAULT 0.00,
    order_date      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',  -- 'pending', 'shipped', 'delivered', 'cancelled'
    ship_date       TIMESTAMP WITH TIME ZONE,
    ship_region     VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_product_id ON orders(product_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- ============================================
-- Trigger: Update customers lifetime_value and order_count
-- ============================================
CREATE OR REPLACE FUNCTION update_customer_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        UPDATE customers
        SET
            lifetime_value = (
                SELECT COALESCE(SUM(total_amount), 0)
                FROM orders
                WHERE customer_id = NEW.customer_id
                AND status != 'cancelled'
            ),
            order_count = (
                SELECT COUNT(*)
                FROM orders
                WHERE customer_id = NEW.customer_id
                AND status != 'cancelled'
            ),
            last_order_date = (
                SELECT MAX(order_date)
                FROM orders
                WHERE customer_id = NEW.customer_id
            )
        WHERE customer_id = NEW.customer_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_customer_stats ON orders;
CREATE TRIGGER trg_update_customer_stats
AFTER INSERT OR UPDATE ON orders
FOR EACH ROW
EXECUTE FUNCTION update_customer_stats();
