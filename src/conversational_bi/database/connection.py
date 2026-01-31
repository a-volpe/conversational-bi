"""Database connection management for Neon PostgreSQL."""

import asyncpg
import structlog

from conversational_bi.common.config import get_settings

logger = structlog.get_logger()


class DatabasePool:
    """
    Manages async connection pool to Neon PostgreSQL.

    Usage:
        async with DatabasePool() as pool:
            async with pool.connection() as conn:
                result = await conn.fetch("SELECT * FROM customers")
    """

    def __init__(self, dsn: str | None = None, min_size: int = 2, max_size: int = 10):
        """
        Initialize database pool configuration.

        Args:
            dsn: Database connection string. Defaults to settings.database_url.
            min_size: Minimum number of connections in the pool.
            max_size: Maximum number of connections in the pool.
        """
        self._dsn = dsn or get_settings().database_url
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def __aenter__(self) -> "DatabasePool":
        """Create connection pool on context entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close connection pool on context exit."""
        await self.close()

    async def connect(self) -> None:
        """
        Initialize the connection pool.

        Raises:
            ConnectionError: If unable to connect to the database.
        """
        try:
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
                # Neon-specific: enable SSL
                ssl="require" if "neon.tech" in self._dsn else None,
            )
            logger.info("database_pool_created", min_size=self._min_size, max_size=self._max_size)
        except Exception as e:
            logger.error("database_connection_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to database: {e}") from e

    async def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("database_pool_closed")

    @property
    def pool(self) -> asyncpg.Pool:
        """Get the underlying connection pool."""
        if self._pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")
        return self._pool

    def connection(self):
        """
        Get a connection from the pool.

        Returns:
            Context manager that yields a database connection.

        Usage:
            async with db.connection() as conn:
                result = await conn.fetch("SELECT * FROM table")
        """
        return self.pool.acquire()


# Global pool instance for convenience
_global_pool: DatabasePool | None = None


async def get_db_pool() -> DatabasePool:
    """
    Get or create the global database pool.

    Returns:
        The global DatabasePool instance.
    """
    global _global_pool
    if _global_pool is None:
        _global_pool = DatabasePool()
        await _global_pool.connect()
    return _global_pool


async def close_db_pool() -> None:
    """Close the global database pool."""
    global _global_pool
    if _global_pool:
        await _global_pool.close()
        _global_pool = None
