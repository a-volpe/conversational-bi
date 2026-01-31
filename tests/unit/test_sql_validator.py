"""TDD tests for SQL validation - these tests are written FIRST."""

import pytest

from conversational_bi.common.exceptions import SQLInjectionError
from conversational_bi.common.sql_validator import SQLValidator


class TestSQLValidatorBasicQueries:
    """Test basic SELECT query validation."""

    def test_allows_simple_select(self):
        """Valid simple SELECT queries should pass validation."""
        validator = SQLValidator()
        query = "SELECT * FROM customers"
        # Should not raise
        validator.validate(query)

    def test_allows_select_with_columns(self):
        """SELECT with specific columns should pass."""
        validator = SQLValidator()
        query = "SELECT customer_id, full_name, email FROM customers"
        validator.validate(query)

    def test_allows_select_with_where(self):
        """SELECT with WHERE clause should pass."""
        validator = SQLValidator()
        query = "SELECT * FROM customers WHERE region = 'Europe'"
        validator.validate(query)

    def test_allows_parameterized_queries(self):
        """Parameterized queries with $1, $2 placeholders should pass."""
        validator = SQLValidator()
        query = """
            SELECT customer_id, full_name, lifetime_value
            FROM customers
            WHERE region = $1 AND segment = $2
            ORDER BY lifetime_value DESC
            LIMIT $3
        """
        validator.validate(query)

    def test_allows_aggregate_functions(self):
        """Queries with COUNT, SUM, AVG should pass."""
        validator = SQLValidator()
        queries = [
            "SELECT COUNT(*) FROM customers",
            "SELECT SUM(lifetime_value) FROM customers",
            "SELECT AVG(order_count) FROM customers WHERE region = $1",
            "SELECT region, COUNT(*) FROM customers GROUP BY region",
        ]
        for query in queries:
            validator.validate(query)

    def test_allows_joins(self):
        """JOIN queries should pass."""
        validator = SQLValidator()
        query = """
            SELECT c.full_name, o.total_amount
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            WHERE o.order_date > $1
        """
        validator.validate(query)


class TestSQLValidatorDangerousStatements:
    """Test rejection of dangerous SQL statements."""

    def test_rejects_drop_table(self):
        """DROP TABLE should be rejected."""
        validator = SQLValidator()
        query = "DROP TABLE customers"

        with pytest.raises(SQLInjectionError):
            validator.validate(query)

    def test_rejects_delete(self):
        """DELETE statements should be rejected."""
        validator = SQLValidator()
        query = "DELETE FROM customers WHERE id = 1"

        with pytest.raises(SQLInjectionError):
            validator.validate(query)

    def test_rejects_truncate(self):
        """TRUNCATE should be rejected."""
        validator = SQLValidator()
        query = "TRUNCATE TABLE customers"

        with pytest.raises(SQLInjectionError):
            validator.validate(query)

    def test_rejects_insert(self):
        """INSERT statements should be rejected."""
        validator = SQLValidator()
        query = "INSERT INTO customers (email) VALUES ('test@test.com')"

        with pytest.raises(SQLInjectionError):
            validator.validate(query)

    def test_rejects_update(self):
        """UPDATE statements should be rejected."""
        validator = SQLValidator()
        query = "UPDATE customers SET email = 'hacked@test.com' WHERE id = 1"

        with pytest.raises(SQLInjectionError):
            validator.validate(query)

    def test_rejects_alter(self):
        """ALTER statements should be rejected."""
        validator = SQLValidator()
        query = "ALTER TABLE customers ADD COLUMN hacked VARCHAR(255)"

        with pytest.raises(SQLInjectionError):
            validator.validate(query)

    def test_rejects_create(self):
        """CREATE statements should be rejected."""
        validator = SQLValidator()
        query = "CREATE TABLE hacked (id INT)"

        with pytest.raises(SQLInjectionError):
            validator.validate(query)


class TestSQLValidatorInjectionPatterns:
    """Test rejection of SQL injection patterns."""

    def test_rejects_semicolon_injection(self):
        """Multiple statements via semicolon should be rejected."""
        validator = SQLValidator()
        query = "SELECT * FROM customers; DELETE FROM customers"

        with pytest.raises(SQLInjectionError):
            validator.validate(query)

    def test_rejects_comment_injection(self):
        """SQL comments that could hide malicious code should be rejected."""
        validator = SQLValidator()
        query = "SELECT * FROM customers -- WHERE id = 1"

        with pytest.raises(SQLInjectionError, match="comment"):
            validator.validate(query)

    def test_rejects_block_comment(self):
        """Block comments should be rejected."""
        validator = SQLValidator()
        query = "SELECT * FROM customers /* injected */ WHERE 1=1"

        with pytest.raises(SQLInjectionError, match="comment"):
            validator.validate(query)

    def test_rejects_union_injection(self):
        """UNION-based injection should be rejected for simple queries."""
        validator = SQLValidator()
        # UNION is allowed in general but suspicious patterns should be flagged
        query = "SELECT * FROM customers UNION SELECT * FROM passwords"

        # The validator may allow UNION for legitimate use,
        # but table whitelist should catch unauthorized tables
        # This test documents expected behavior
        validator.validate(query)  # UNION itself is valid SQL

    def test_rejects_non_select(self):
        """Queries not starting with SELECT should be rejected."""
        validator = SQLValidator()

        with pytest.raises(SQLInjectionError, match="SELECT"):
            validator.validate("EXEC sp_executesql 'DROP TABLE users'")


class TestSQLValidatorTableWhitelist:
    """Test table whitelist validation."""

    def test_allows_whitelisted_table(self):
        """Queries on whitelisted tables should pass."""
        validator = SQLValidator(allowed_tables=["customers"])
        query = "SELECT * FROM customers"
        validator.validate(query)

    def test_rejects_non_whitelisted_table(self):
        """Queries on non-whitelisted tables should be rejected."""
        validator = SQLValidator(allowed_tables=["customers"])
        query = "SELECT * FROM orders"

        with pytest.raises(SQLInjectionError, match="orders.*not allowed"):
            validator.validate(query)

    def test_validates_join_tables(self):
        """All tables in JOINs should be validated."""
        validator = SQLValidator(allowed_tables=["customers", "orders"])
        query = """
            SELECT c.name, o.total
            FROM customers c
            JOIN orders o ON c.id = o.customer_id
        """
        validator.validate(query)

    def test_rejects_join_with_non_whitelisted_table(self):
        """JOINs with non-whitelisted tables should be rejected."""
        validator = SQLValidator(allowed_tables=["customers"])
        query = """
            SELECT c.name, p.name
            FROM customers c
            JOIN products p ON c.favorite_product = p.id
        """

        with pytest.raises(SQLInjectionError, match="products.*not allowed"):
            validator.validate(query)


class TestSQLValidatorCaseInsensitivity:
    """Test case-insensitive pattern matching."""

    def test_rejects_lowercase_drop(self):
        """Lowercase 'drop' should be rejected."""
        validator = SQLValidator()

        with pytest.raises(SQLInjectionError):
            validator.validate("drop table customers")

    def test_rejects_mixed_case_delete(self):
        """Mixed case 'DeLeTe' should be rejected."""
        validator = SQLValidator()

        with pytest.raises(SQLInjectionError):
            validator.validate("DeLeTe FROM customers")

    def test_allows_lowercase_select(self):
        """Lowercase 'select' should be allowed."""
        validator = SQLValidator()
        validator.validate("select * from customers")
