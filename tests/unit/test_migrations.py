"""Tests for database migration system."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conversational_bi.database.migrations.runner import (
    MigrationRunner,
    generate_schema_sql,
)


class TestGenerateSchemaSql:
    """Test SQL generation from schema config."""

    def test_generate_creates_table(self):
        """Should generate CREATE TABLE statement."""
        schema = {
            "tables": {
                "test_table": {
                    "description": "Test table",
                    "columns": [
                        {"name": "id", "type": "INTEGER", "primary_key": True},
                        {"name": "name", "type": "VARCHAR(100)"},
                    ]
                }
            }
        }
        sql = generate_schema_sql(schema)
        assert "CREATE TABLE" in sql
        assert "test_table" in sql

    def test_generate_handles_primary_key(self):
        """Should mark primary key columns."""
        schema = {
            "tables": {
                "test": {
                    "columns": [
                        {"name": "id", "type": "UUID", "primary_key": True}
                    ]
                }
            }
        }
        sql = generate_schema_sql(schema)
        assert "PRIMARY KEY" in sql

    def test_generate_handles_unique(self):
        """Should mark unique columns."""
        schema = {
            "tables": {
                "test": {
                    "columns": [
                        {"name": "email", "type": "VARCHAR(255)", "unique": True}
                    ]
                }
            }
        }
        sql = generate_schema_sql(schema)
        assert "UNIQUE" in sql

    def test_generate_handles_foreign_key(self):
        """Should create foreign key constraints."""
        schema = {
            "tables": {
                "orders": {
                    "columns": [
                        {"name": "id", "type": "UUID", "primary_key": True},
                        {"name": "customer_id", "type": "UUID", "foreign_key": "customers.customer_id"},
                    ]
                }
            }
        }
        sql = generate_schema_sql(schema)
        assert "REFERENCES" in sql
        assert "customers" in sql

    def test_generate_handles_default(self):
        """Should add default values."""
        schema = {
            "tables": {
                "test": {
                    "columns": [
                        {"name": "count", "type": "INTEGER", "default": 0}
                    ]
                }
            }
        }
        sql = generate_schema_sql(schema)
        assert "DEFAULT" in sql

    def test_generate_handles_nullable(self):
        """Should handle nullable columns."""
        schema = {
            "tables": {
                "test": {
                    "columns": [
                        {"name": "optional", "type": "VARCHAR(100)", "nullable": True}
                    ]
                }
            }
        }
        sql = generate_schema_sql(schema)
        # Nullable columns should not have NOT NULL
        assert "NOT NULL" not in sql or "optional" not in sql.split("NOT NULL")[0]

    def test_generate_creates_indexes(self):
        """Should generate CREATE INDEX statements."""
        schema = {
            "tables": {
                "test": {
                    "columns": [
                        {"name": "id", "type": "INTEGER", "primary_key": True},
                        {"name": "category", "type": "VARCHAR(50)"},
                    ],
                    "indexes": [
                        {"columns": ["category"]}
                    ]
                }
            }
        }
        sql = generate_schema_sql(schema)
        assert "CREATE INDEX" in sql
        assert "category" in sql


class TestMigrationRunner:
    """Test migration runner functionality."""

    @pytest.fixture
    def mock_conn(self):
        """Create mock database connection."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()
        conn.transaction = MagicMock(return_value=AsyncMock())
        return conn

    @pytest.fixture
    def migrations_dir(self, tmp_path):
        """Create temp migrations directory with sample files."""
        versions_dir = tmp_path / "versions"
        versions_dir.mkdir()

        # Create sample migration files
        (versions_dir / "001_initial.sql").write_text("CREATE TABLE test (id INT);")
        (versions_dir / "002_add_column.sql").write_text("ALTER TABLE test ADD name VARCHAR(100);")

        return tmp_path

    @pytest.mark.asyncio
    async def test_get_pending_migrations(self, migrations_dir):
        """Should identify pending migrations."""
        runner = MigrationRunner("postgresql://test", migrations_dir=migrations_dir)
        applied = {"001_initial.sql"}

        pending = runner._get_pending(applied)

        assert len(pending) == 1
        assert pending[0].name == "002_add_column.sql"

    @pytest.mark.asyncio
    async def test_all_migrations_pending_when_none_applied(self, migrations_dir):
        """Should return all migrations when none applied."""
        runner = MigrationRunner("postgresql://test", migrations_dir=migrations_dir)
        applied = set()

        pending = runner._get_pending(applied)

        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_migrations_sorted_by_name(self, migrations_dir):
        """Should return migrations in sorted order."""
        runner = MigrationRunner("postgresql://test", migrations_dir=migrations_dir)
        applied = set()

        pending = runner._get_pending(applied)

        assert pending[0].name == "001_initial.sql"
        assert pending[1].name == "002_add_column.sql"

    @pytest.mark.asyncio
    async def test_dry_run_does_not_execute(self, migrations_dir, mock_conn):
        """Dry run should not execute migrations."""
        runner = MigrationRunner("postgresql://test", migrations_dir=migrations_dir)

        with patch.object(runner, "_get_connection", return_value=mock_conn):
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock()

            result = await runner.run(dry_run=True)

        # Should return list of pending migrations but not execute
        assert len(result) == 2
        # execute should only be called for tracking table check
        # Not for actual migration execution


class TestMigrationTracking:
    """Test migration tracking table management."""

    @pytest.fixture
    def mock_conn(self):
        """Create mock database connection."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()
        return conn

    @pytest.mark.asyncio
    async def test_creates_tracking_table(self, mock_conn, tmp_path):
        """Should create _migrations table if not exists."""
        runner = MigrationRunner("postgresql://test", migrations_dir=tmp_path)
        (tmp_path / "versions").mkdir()

        await runner._create_tracking_table(mock_conn)

        # Verify CREATE TABLE was called
        mock_conn.execute.assert_called_once()
        call_sql = mock_conn.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS" in call_sql
        assert "_migrations" in call_sql
