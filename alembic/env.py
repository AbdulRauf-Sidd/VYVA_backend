"""
Alembic environment configuration.
"""
import os;
import sys;
import asyncio
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
# Import all models to ensure they are registered with SQLAlchemy
# from models import Base
from models import eleven_labs_batch_calls, eleven_labs_sessions, onboarding, organization, user
from core.config import settings
from core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    """Get database URL from settings, convert asyncpg to psycopg2 for Alembic."""
    return settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode using a sync engine."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # connect_args={"options": "-c search_path=public"}  # ensures correct schema
    )

    

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # version_table_schema="public"  # Alembic version table goes here
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
