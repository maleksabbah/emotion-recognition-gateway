"""
Alembic environment — async-aware.

Reads DATABASE_URL from app.Config and target_metadata from app.Entities.Base.
Supports both online (live DB) and offline (SQL emit) modes.

Usage:
    # Generate a migration after entity changes
    alembic revision --autogenerate -m "add some_column to users"

    # Apply migrations
    alembic upgrade head

    # Roll back one revision
    alembic downgrade -1
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Alembic Config object — gives access to .ini values
config = context.config

# Configure Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Inject DB URL from app config ──────────────────────
from app.Config import GATEWAY_DB_URL
config.set_main_option("sqlalchemy.url", GATEWAY_DB_URL)

# ── Target metadata for autogenerate ───────────────────
# Importing Entities triggers registration of every model on Base.metadata.
from app.Entities import Base  # noqa: E402
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — emit SQL to stdout without connecting.

    Useful for generating SQL scripts to apply manually in production.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure context with a live connection, then run migrations."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connect to the DB and apply."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())