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
from models import eleven_labs_batch_calls, eleven_labs_sessions, onboarding, organization, user, authentication, user_check_ins, medication, brain_coach, symptom_checker
from core.config import settings
from core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    """Get database URL from settings, convert asyncpg to psycopg2 for Alembic."""
    url = settings.database_url
    if not url:
        raise ValueError(
            "DATABASE_URL is not set. Please check your .env file or environment variables."
        )
    # Convert asyncpg driver to psycopg2 for Alembic (sync operations)
    if "+asyncpg" in url:
        url = url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    return url


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
    db_url = get_url()
    configuration["sqlalchemy.url"] = db_url

    try:
        connectable = engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            # connect_args={"options": "-c search_path=public"}  # ensures correct schema
        )
    except Exception as e:
        raise Exception(
            f"Failed to create database engine. "
            f"Please check your DATABASE_URL and ensure PostgreSQL is running. "
            f"Error: {str(e)}"
        ) from e

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                # version_table_schema="public"  # Alembic version table goes here
            )
            with context.begin_transaction():
                context.run_migrations()
    except Exception as e:
        raise Exception(
            f"Failed to connect to database. "
            f"Please verify:\n"
            f"1. PostgreSQL server is running\n"
            f"2. Database exists: {db_url.split('/')[-1] if '/' in db_url else 'unknown'}\n"
            f"3. Credentials are correct\n"
            f"4. psycopg2 is installed: pip install psycopg2-binary\n"
            f"Error: {str(e)}"
        ) from e


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
