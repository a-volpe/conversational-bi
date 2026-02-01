#!/usr/bin/env python
"""
Run database migrations manually.

Usage:
    python scripts/migrate_db.py              # Run pending migrations
    python scripts/migrate_db.py --dry-run    # Show pending without executing

Environment:
    DATABASE_URL: PostgreSQL connection string (required)
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Load .env file from project root
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from conversational_bi.database.migrations.runner import MigrationRunner


def main():
    parser = argparse.ArgumentParser(
        description="Run database migrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show pending migrations without executing",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Database connection string (default: $DATABASE_URL)",
    )
    args = parser.parse_args()

    if not args.database_url:
        print("Error: DATABASE_URL not set. Provide via --database-url or environment.")
        sys.exit(1)

    try:
        executed = asyncio.run(run_migrations(args.database_url, args.dry_run))

        if args.dry_run:
            if executed:
                print(f"\nWould execute {len(executed)} migration(s):")
                for name in executed:
                    print(f"  - {name}")
            else:
                print("No pending migrations.")
        else:
            if executed:
                print(f"\nExecuted {len(executed)} migration(s):")
                for name in executed:
                    print(f"  - {name}")
            else:
                print("No pending migrations.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


async def run_migrations(dsn: str, dry_run: bool = False) -> list[str]:
    """Run migrations using the MigrationRunner."""
    runner = MigrationRunner(dsn)
    return await runner.run(dry_run=dry_run)


if __name__ == "__main__":
    main()
