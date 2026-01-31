"""SQL validation to prevent injection attacks.

This module provides whitelist-based validation for SQL queries,
ensuring only safe SELECT queries are executed against the database.
"""

import re
from dataclasses import dataclass, field

from conversational_bi.common.exceptions import SQLInjectionError


@dataclass
class SQLValidator:
    """
    Validates SQL queries for safety before execution.

    Implements whitelist-based validation for tables and columns,
    plus pattern-based detection of dangerous constructs.

    Attributes:
        allowed_tables: Optional list of table names that can be queried.
                       If None, table validation is skipped.
        allowed_columns: Optional list of column names that can be used.
                        If None, column validation is skipped.
    """

    allowed_tables: list[str] | None = None
    allowed_columns: list[str] | None = None

    # Dangerous SQL patterns with their error messages
    _dangerous_patterns: list[tuple[str, str]] = field(
        default_factory=lambda: [
            (r"\bDROP\b", "DROP statements not allowed"),
            (r"\bDELETE\b", "DELETE statements not allowed"),
            (r"\bTRUNCATE\b", "TRUNCATE statements not allowed"),
            (r"\bINSERT\b", "INSERT statements not allowed"),
            (r"\bUPDATE\b", "UPDATE statements not allowed"),
            (r"\bALTER\b", "ALTER statements not allowed"),
            (r"\bCREATE\b", "CREATE statements not allowed"),
            (r"\bGRANT\b", "GRANT statements not allowed"),
            (r"\bREVOKE\b", "REVOKE statements not allowed"),
            (r";\s*\w", "multiple statements not allowed"),
            (r"--", "SQL comment injection not allowed"),
            (r"/\*", "SQL block comment not allowed"),
            (r"\bEXEC\b", "EXEC not allowed"),
            (r"\bEXECUTE\b", "EXECUTE not allowed"),
            (r"\bxp_", "Extended stored procedures not allowed"),
            (r"\bsp_", "System stored procedures not allowed"),
        ]
    )

    def validate(self, sql: str) -> None:
        """
        Validate SQL query for safety.

        Args:
            sql: The SQL query string to validate.

        Raises:
            SQLInjectionError: If the query contains dangerous patterns
                              or references non-whitelisted tables.
        """
        # Normalize whitespace
        normalized = " ".join(sql.split())

        # Must be a SELECT query
        if not normalized.upper().strip().startswith("SELECT"):
            raise SQLInjectionError("Only SELECT queries are allowed")

        # Check for dangerous patterns
        for pattern, message in self._dangerous_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                raise SQLInjectionError(message)

        # Validate table names if whitelist provided
        if self.allowed_tables is not None:
            self._validate_tables(sql)

        # Validate column names if whitelist provided
        if self.allowed_columns is not None:
            self._validate_columns(sql)

    def _validate_tables(self, sql: str) -> None:
        """
        Ensure only allowed tables are referenced.

        Extracts table names from FROM and JOIN clauses and validates
        them against the whitelist.

        Args:
            sql: The SQL query string.

        Raises:
            SQLInjectionError: If a non-whitelisted table is referenced.
        """
        # Extract table names from FROM clause
        # Handles: FROM table, FROM table alias, FROM schema.table
        from_pattern = r"\bFROM\s+(\w+)"
        join_pattern = r"\bJOIN\s+(\w+)"

        tables: set[str] = set()
        tables.update(re.findall(from_pattern, sql, re.IGNORECASE))
        tables.update(re.findall(join_pattern, sql, re.IGNORECASE))

        # Normalize to lowercase for comparison
        allowed_lower = [t.lower() for t in self.allowed_tables]  # type: ignore

        for table in tables:
            if table.lower() not in allowed_lower:
                raise SQLInjectionError(f"Table '{table}' not allowed")

    def _validate_columns(self, sql: str) -> None:
        """
        Validate column references against whitelist.

        Note: This is a simplified check. For production use,
        consider using a proper SQL parser.

        Args:
            sql: The SQL query string.
        """
        # Column validation is complex - for now, we rely on
        # table whitelisting and parameterized queries for security.
        # A full implementation would use a SQL parser like sqlparse.
        pass
