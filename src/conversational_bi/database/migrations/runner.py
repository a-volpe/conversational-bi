"""Database migration runner - executes manually via script."""

from pathlib import Path
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger()

# Default migrations directory
DEFAULT_MIGRATIONS_DIR = Path(__file__).parent


def generate_schema_sql(schema: dict[str, Any]) -> str:
    """
    Generate SQL DDL from schema configuration.

    Args:
        schema: Schema configuration dictionary from schema.yaml

    Returns:
        SQL string with CREATE TABLE and CREATE INDEX statements
    """
    statements = []
    tables = schema.get("tables", {})

    for table_name, table_def in tables.items():
        columns = table_def.get("columns", [])
        indexes = table_def.get("indexes", [])

        # Build column definitions
        col_defs = []
        foreign_keys = []

        for col in columns:
            parts = [col["name"], col["type"]]

            if col.get("primary_key"):
                parts.append("PRIMARY KEY")
            elif col.get("unique"):
                parts.append("UNIQUE")

            # Handle NOT NULL (columns are NOT NULL by default unless nullable=True)
            if not col.get("nullable", False) and not col.get("primary_key"):
                parts.append("NOT NULL")

            if "default" in col:
                default_val = col["default"]
                if isinstance(default_val, str) and default_val.upper() in (
                    "CURRENT_TIMESTAMP", "NOW()", "TRUE", "FALSE"
                ):
                    parts.append(f"DEFAULT {default_val}")
                elif isinstance(default_val, bool):
                    parts.append(f"DEFAULT {str(default_val).upper()}")
                elif isinstance(default_val, (int, float)):
                    parts.append(f"DEFAULT {default_val}")
                else:
                    parts.append(f"DEFAULT '{default_val}'")

            col_defs.append("    " + " ".join(parts))

            # Track foreign keys
            if col.get("foreign_key"):
                ref_table, ref_col = col["foreign_key"].split(".")
                foreign_keys.append(
                    f"    FOREIGN KEY ({col['name']}) REFERENCES {ref_table}({ref_col})"
                )

        # Add foreign key constraints
        col_defs.extend(foreign_keys)

        # Build CREATE TABLE statement
        create_table = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
        create_table += ",\n".join(col_defs)
        create_table += "\n);"

        statements.append(create_table)

        # Build CREATE INDEX statements
        for idx in indexes:
            idx_columns = idx.get("columns", [])
            if idx_columns:
                idx_name = f"idx_{table_name}_{'_'.join(idx_columns)}"
                idx_cols = ", ".join(idx_columns)
                statements.append(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} ({idx_cols});"
                )

    return "\n\n".join(statements)


class MigrationRunner:
    """Runs SQL migrations from version files."""

    def __init__(
        self,
        dsn: str,
        migrations_dir: Path | None = None,
    ):
        """
        Initialize the migration runner.

        Args:
            dsn: Database connection string
            migrations_dir: Directory containing migrations. Defaults to module directory.
        """
        self.dsn = dsn
        self.migrations_dir = Path(migrations_dir) if migrations_dir else DEFAULT_MIGRATIONS_DIR
        self.versions_dir = self.migrations_dir / "versions"

    async def _get_connection(self) -> asyncpg.Connection:
        """Create a database connection."""
        # Handle Neon SSL
        ssl = "require" if "neon.tech" in self.dsn else None
        return await asyncpg.connect(dsn=self.dsn, ssl=ssl)

    async def run(self, dry_run: bool = False) -> list[str]:
        """
        Execute pending migrations.

        Args:
            dry_run: If True, list pending migrations without executing

        Returns:
            List of executed (or would-be-executed) migration names
        """
        conn = await self._get_connection()

        try:
            # Ensure tracking table exists
            if not dry_run:
                await self._create_tracking_table(conn)

            # Get applied migrations
            applied = await self._get_applied(conn) if not dry_run else set()

            # Find pending migrations
            pending = self._get_pending(applied)

            if not pending:
                logger.info("No pending migrations")
                return []

            # Execute each migration
            executed = []
            for migration_file in pending:
                if dry_run:
                    logger.info("Would run", migration=migration_file.name)
                    executed.append(migration_file.name)
                else:
                    await self._execute_migration(conn, migration_file)
                    executed.append(migration_file.name)
                    logger.info("Executed", migration=migration_file.name)

            return executed

        finally:
            await conn.close()

    async def _create_tracking_table(self, conn: asyncpg.Connection) -> None:
        """Create the migrations tracking table if it doesn't exist."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

    async def _get_applied(self, conn: asyncpg.Connection) -> set[str]:
        """Get set of already-applied migration names."""
        rows = await conn.fetch("SELECT name FROM _migrations")
        return {row["name"] for row in rows}

    def _get_pending(self, applied: set[str]) -> list[Path]:
        """Get list of pending migration files in sorted order."""
        if not self.versions_dir.exists():
            return []

        all_migrations = sorted(self.versions_dir.glob("*.sql"))
        return [m for m in all_migrations if m.name not in applied]

    async def _execute_migration(
        self,
        conn: asyncpg.Connection,
        migration_file: Path,
    ) -> None:
        """Execute a single migration file."""
        sql = migration_file.read_text(encoding="utf-8")

        async with conn.transaction():
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO _migrations (name) VALUES ($1)",
                migration_file.name,
            )


async def run_migrations(dsn: str, dry_run: bool = False) -> list[str]:
    """
    Convenience function to run migrations.

    Args:
        dsn: Database connection string
        dry_run: If True, list pending migrations without executing

    Returns:
        List of executed migration names
    """
    runner = MigrationRunner(dsn)
    return await runner.run(dry_run=dry_run)
